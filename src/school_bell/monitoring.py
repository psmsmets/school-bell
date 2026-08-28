#!/usr/bin/python3

"""Remote syslog and HTTP monitoring support for School Bell."""

import hmac
import json
import logging
import logging.handlers
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit


__all__ = [
    'StatusServer',
    'StructuredSyslogFormatter',
    'configure_remote_syslog',
    'get_systemd_status',
    'log_event',
]


class StructuredSyslogFormatter(logging.Formatter):
    """Format log records as compact JSON for indexing in Graylog."""

    def __init__(
        self,
        application: str,
        hostname: str,
        version: str,
        device_id: str = None,
        labels: dict = None,
    ):
        super().__init__()
        self.application = application
        self.hostname = hostname
        self.version = version
        self.device_id = device_id or hostname
        self.labels = labels or {}

    def format(self, record: logging.LogRecord) -> str:
        status = getattr(record, 'status', None)
        if status is None:
            status = 'failure' if record.levelno >= logging.ERROR else 'info'

        payload = {
            'application': self.application,
            'hostname': self.hostname,
            'device_id': self.device_id,
            'version': self.version,
            'event': getattr(record, 'event', 'log'),
            'status': status,
            'timestamp': datetime.fromtimestamp(
                record.created, timezone.utc
            ).isoformat(),
            'level': record.levelname.lower(),
            'message': record.getMessage(),
        }
        for key, value in self.labels.items():
            payload[f'label_{key}'] = value
        for key, value in getattr(record, 'fields', {}).items():
            if key not in payload:
                payload[key] = value

        message = json.dumps(
            payload, separators=(',', ':'), default=str
        )
        # SysLogHandler adds PRI. Supply the remaining RFC5424 header so
        # Graylog can identify the hostname instead of treating JSON as source.
        syslog_timestamp = datetime.fromtimestamp(
            record.created, timezone.utc
        ).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        message_id = str(payload['event']).replace(' ', '_')
        return (
            f'1 {syslog_timestamp} {self.hostname} {self.application} '
            f'- {message_id} - {message}'
        )


class ResilientSysLogHandler(logging.handlers.SysLogHandler):
    """Keep remote logging failures from interrupting or flooding the app."""

    error_interval = 300

    def __init__(self, *args, **kwargs):
        self._last_error = 0.0
        super().__init__(*args, **kwargs)

    def handleError(self, record):
        now = time.monotonic()
        if now - self._last_error >= self.error_interval:
            self._last_error = now
            sys.stderr.write(
                'WARNING: Unable to send log record to remote syslog server.\n'
            )


def configure_remote_syslog(
    logger: logging.Logger,
    config: dict,
    version: str,
    hostname: str = None,
    device_id: str = None,
    labels: dict = None,
):
    """Attach an optional UDP or TCP remote syslog handler.

    A connection or configuration failure is logged locally and does not stop
    the application.
    """
    if not config:
        return None
    if not isinstance(config, dict):
        raise TypeError('monitoring.syslog should be a dictionary!')

    host = config.get('host')
    if not host:
        raise ValueError('monitoring.syslog.host is required!')

    port = int(config.get('port', 514))
    protocol = str(config.get('protocol', 'udp')).lower()
    if protocol not in ('udp', 'tcp'):
        raise ValueError('monitoring.syslog.protocol should be udp or tcp!')

    facility = config.get('facility', 'daemon')
    if facility not in logging.handlers.SysLogHandler.facility_names:
        raise ValueError(f'Unknown syslog facility: {facility}')
    socktype = socket.SOCK_DGRAM if protocol == 'udp' else socket.SOCK_STREAM
    try:
        handler = ResilientSysLogHandler(
            address=(host, port), facility=facility, socktype=socktype
        )
    except (OSError, ValueError) as err:
        logger.warning(
            'Remote syslog unavailable; local logging remains active: %s', err
        )
        return None

    handler.setFormatter(StructuredSyslogFormatter(
        application='school-bell',
        hostname=hostname or socket.gethostname(),
        version=version,
        device_id=device_id,
        labels=labels,
    ))
    logger.addHandler(handler)
    logger.info(
        'Remote syslog enabled: %s:%s via %s',
        host, port, protocol.upper()
    )
    return handler


def log_event(
    logger: logging.Logger,
    event: str,
    status: str = 'success',
    level: int = logging.INFO,
    message: str = None,
    **fields,
):
    """Write a normal log record with stable structured event fields."""
    logger.log(
        level,
        message or event.replace('_', ' '),
        extra={'event': event, 'status': status, 'fields': fields},
    )


def get_systemd_status(
    service: str = 'school-bell.service',
    runner=subprocess.run,
) -> dict:
    """Return a safe, structured subset of ``systemctl show``."""
    properties = {
        'LoadState': 'load_state',
        'ActiveState': 'active_state',
        'SubState': 'sub_state',
        'MainPID': 'main_pid',
        'ExecMainStartTimestamp': 'started_at',
        'ExecMainStatus': 'exit_status',
        'NRestarts': 'restart_count',
    }
    command = ['systemctl', 'show', service, '--no-pager']
    command.extend(f'--property={name}' for name in properties)

    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {'available': False}

    if result.returncode != 0:
        return {'available': False}

    status = {'available': True}
    integers = {'MainPID', 'ExecMainStatus', 'NRestarts'}
    for line in result.stdout.splitlines():
        name, separator, value = line.partition('=')
        if not separator or name not in properties:
            continue
        if name in integers:
            try:
                value = int(value)
            except ValueError:
                pass
        status[properties[name]] = value
    return status


class _MonitoringHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class StatusServer:
    """Run read-only status and health endpoints in a background thread."""

    def __init__(
        self,
        host: str,
        port: int,
        status_provider,
        health_provider,
        logger: logging.Logger,
        token: str = None,
    ):
        self.logger = logger
        self.token = token
        self.status_provider = status_provider
        self.health_provider = health_provider
        self._server = _MonitoringHTTPServer(
            (host, int(port)), self._handler_class()
        )
        self._server.status_service = self
        self._thread = Thread(
            target=self._server.serve_forever,
            name='school-bell-monitoring',
            daemon=True,
        )

    @property
    def address(self):
        return self._server.server_address

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        if self._thread.is_alive():
            self._server.shutdown()
            self._thread.join(timeout=3)
        self._server.server_close()

    def _handler_class(self):  # noqa: C901
        class Handler(BaseHTTPRequestHandler):
            server_version = 'SchoolBellMonitoring/1'

            def _authorized(self):
                service = self.server.status_service
                if not service.token:
                    return True
                supplied = self.headers.get('Authorization', '')
                expected = f'Bearer {service.token}'
                return hmac.compare_digest(supplied, expected)

            def _json(self, status, payload, extra_headers=None):
                body = json.dumps(payload, default=str).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                for name, value in (extra_headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if not self._authorized():
                    self._json(
                        401,
                        {'error': 'unauthorized'},
                        {'WWW-Authenticate': 'Bearer'},
                    )
                    return

                service = self.server.status_service
                path = urlsplit(self.path).path
                if path == '/status':
                    self._json(200, service.status_provider())
                elif path == '/health':
                    healthy, payload = service.health_provider()
                    self._json(200 if healthy else 503, payload)
                else:
                    self._json(404, {'error': 'not found'})

            def _method_not_allowed(self):
                self._json(
                    405, {'error': 'method not allowed'}, {'Allow': 'GET'}
                )

            do_POST = _method_not_allowed
            do_PUT = _method_not_allowed
            do_PATCH = _method_not_allowed
            do_DELETE = _method_not_allowed

            def log_message(self, fmt, *args):
                self.server.status_service.logger.debug(fmt, *args)

        return Handler
