"""Authenticated HTTP endpoint for externally triggered bell signals."""

import hmac
import json
import logging
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from time import monotonic
from urllib.parse import urlsplit

from .monitoring import log_event


class _WebhookHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class FixedWindowRateLimiter:
    """Bound requests per client within a rolling time window."""

    def __init__(self, requests: int, window_seconds: int, clock=monotonic):
        self.requests = requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._entries = defaultdict(deque)
        self._lock = Lock()

    def allow(self, client: str):
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            entries = self._entries[client]
            while entries and entries[0] <= cutoff:
                entries.popleft()
            if len(entries) >= self.requests:
                retry_after = max(1, int(entries[0] + self.window_seconds - now))
                return False, retry_after
            entries.append(now)
        return True, None


class WebhookServer:
    """Serve the authenticated ``POST /bell`` endpoint."""

    def __init__(
        self,
        host: str,
        port: int,
        token: str,
        bell_provider,
        logger: logging.Logger,
        rate_limit: int = 10,
        rate_window: int = 60,
    ):
        self.logger = logger
        self.token = token
        self.bell_provider = bell_provider
        self.rate_limiter = FixedWindowRateLimiter(
            rate_limit, rate_window
        )
        self._server = _WebhookHTTPServer(
            (host, int(port)), self._handler_class()
        )
        self._server.webhook_service = self
        self._thread = Thread(
            target=self._server.serve_forever,
            name='school-bell-webhook',
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
            server_version = 'SchoolBellWebhook/1'

            def _json(self, status, payload, extra_headers=None):
                body = json.dumps(payload).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                for name, value in (extra_headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def _reject(self, status, error, reason, headers=None):
                log_event(
                    self.server.webhook_service.logger,
                    'webhook_request_rejected',
                    status='rejected',
                    level=logging.WARNING,
                    rejection_reason=reason,
                    http_status=status,
                )
                self._json(status, {'error': error}, headers)

            def _authorized(self):
                service = self.server.webhook_service
                supplied = self.headers.get('Authorization', '')
                return hmac.compare_digest(
                    supplied, f'Bearer {service.token}'
                )

            def _payload(self):
                content_type = self.headers.get('Content-Type', '')
                if content_type.split(';', 1)[0].strip() != 'application/json':
                    return None
                try:
                    length = int(self.headers.get('Content-Length', ''))
                except ValueError:
                    return None
                if length <= 0 or length > 4096:
                    return None
                try:
                    payload = json.loads(self.rfile.read(length))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return None
                if not isinstance(payload, dict) or set(payload) != {'wav_key'}:
                    return None
                if isinstance(payload['wav_key'], bool) or not isinstance(
                    payload['wav_key'], (str, int)
                ):
                    return None
                return payload

            def do_POST(self):
                if urlsplit(self.path).path != '/bell':
                    self._json(404, {'error': 'not found'})
                    return
                if not self._authorized():
                    self._reject(
                        401, 'unauthorized', 'authentication_failed',
                        {'WWW-Authenticate': 'Bearer'},
                    )
                    return
                service = self.server.webhook_service
                allowed, retry_after = service.rate_limiter.allow(
                    self.client_address[0]
                )
                if not allowed:
                    self._reject(
                        429, 'rate limit exceeded', 'rate_limited',
                        {'Retry-After': str(retry_after)},
                    )
                    return
                payload = self._payload()
                if payload is None:
                    self._reject(400, 'invalid request', 'invalid_input')
                    return
                status, response = service.bell_provider(
                    str(payload['wav_key'])
                )
                self._json(status, response)

            def _method_not_allowed(self):
                self._json(
                    405, {'error': 'method not allowed'}, {'Allow': 'POST'}
                )

            do_GET = _method_not_allowed
            do_PUT = _method_not_allowed
            do_PATCH = _method_not_allowed
            do_DELETE = _method_not_allowed

            def log_message(self, fmt, *args):
                self.server.webhook_service.logger.debug(fmt, *args)

        return Handler
