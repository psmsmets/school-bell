import json
import logging
import socket
import urllib.error
import urllib.request
from os import getcwd
from threading import Event, Thread
from types import SimpleNamespace

import pytest

import school_bell.monitoring as monitoring_module
import school_bell.school_bell as school_bell_module
from school_bell.monitoring import (
    StatusServer,
    StructuredSyslogFormatter,
    configure_remote_syslog,
    get_systemd_status,
)
from school_bell.school_bell import SchoolBell


def test_structured_syslog_contains_graylog_fields():
    formatter = StructuredSyslogFormatter(
        application='school-bell',
        hostname='pibell-01',
        device_id='vito-bell-01',
        version='1.2.3',
        labels={'school': 'vito', 'zone': 'main'},
    )
    record = logging.LogRecord(
        name='school-bell',
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='Bell completed',
        args=(),
        exc_info=None,
    )
    record.event = 'bell_ring'
    record.status = 'success'
    record.fields = {'wav_key': '0', 'gpio_pins': [26, 20]}

    formatted = formatter.format(record)
    payload = json.loads(formatted.split(' ', 7)[7])

    assert formatted.startswith('1 ')
    assert ' pibell-01 school-bell - bell_ring - ' in formatted
    assert payload['application'] == 'school-bell'
    assert payload['hostname'] == 'pibell-01'
    assert payload['device_id'] == 'vito-bell-01'
    assert payload['version'] == '1.2.3'
    assert payload['event'] == 'bell_ring'
    assert payload['status'] == 'success'
    assert payload['label_school'] == 'vito'
    assert payload['label_zone'] == 'main'
    assert payload['gpio_pins'] == [26, 20]
    assert payload['timestamp']


@pytest.mark.parametrize(
    'protocol, socktype',
    [('udp', socket.SOCK_DGRAM), ('tcp', socket.SOCK_STREAM)],
)
def test_configure_remote_syslog_protocol(
    protocol, socktype, monkeypatch
):
    created = {}

    class FakeSyslogHandler(logging.Handler):
        def __init__(self, address, facility, socktype):
            super().__init__()
            created.update({
                'address': address,
                'facility': facility,
                'socktype': socktype,
            })

    monkeypatch.setattr(
        monitoring_module, 'ResilientSysLogHandler', FakeSyslogHandler
    )
    logger = logging.getLogger(f'test-syslog-{protocol}')

    handler = configure_remote_syslog(
        logger,
        {
            'host': 'graylog.example.com',
            'port': 1514,
            'protocol': protocol,
            'facility': 'daemon',
        },
        version='1.2.3',
        hostname='pibell-01',
    )

    assert handler is not None
    assert created == {
        'address': ('graylog.example.com', 1514),
        'facility': 'daemon',
        'socktype': socktype,
    }
    logger.removeHandler(handler)


def test_unavailable_remote_syslog_does_not_raise(monkeypatch):
    class UnavailableHandler:
        def __init__(self, *args, **kwargs):
            raise OSError('unavailable')

    monkeypatch.setattr(
        monitoring_module, 'ResilientSysLogHandler', UnavailableHandler
    )

    assert configure_remote_syslog(
        logging.getLogger('test-unavailable-syslog'),
        {'host': 'graylog.example.com', 'protocol': 'tcp'},
        version='1.2.3',
    ) is None


def test_invalid_monitoring_does_not_stop_school_bell():
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f'{getcwd()}/samples',
        monitoring={
            'syslog': {'protocol': 'invalid'},
            'status': {'enabled': True, 'port': 'invalid'},
            'heartbeat_interval': 'invalid',
        },
    )
    try:
        assert bell.monitoring_address is None
        assert bell.monitoring_status()['service'] == 'school-bell'
    finally:
        bell.close()


def _request(server, path, token=None, method='GET'):
    host, port = server.address[:2]
    request = urllib.request.Request(
        f'http://{host}:{port}{path}', method=method
    )
    if token:
        request.add_header('Authorization', f'Bearer {token}')
    try:
        response = urllib.request.urlopen(request, timeout=2)
        return response.status, json.load(response)
    except urllib.error.HTTPError as err:
        return err.code, json.load(err)


@pytest.fixture
def status_server():
    server = StatusServer(
        host='127.0.0.1',
        port=0,
        status_provider=lambda: {
            'service': 'school-bell',
            'version': '1.2.3',
        },
        health_provider=lambda: (True, {'status': 'ok'}),
        logger=logging.getLogger('test-status-server'),
    ).start()
    yield server
    server.stop()


def test_status_and_health_endpoints(status_server):
    status_code, status = _request(status_server, '/status')
    health_code, health = _request(status_server, '/health')

    assert status_code == 200
    assert status == {'service': 'school-bell', 'version': '1.2.3'}
    assert health_code == 200
    assert health == {'status': 'ok'}


def test_unhealthy_endpoint_returns_503():
    server = StatusServer(
        host='127.0.0.1',
        port=0,
        status_provider=dict,
        health_provider=lambda: (False, {'status': 'unhealthy'}),
        logger=logging.getLogger('test-unhealthy-server'),
    ).start()
    try:
        status_code, payload = _request(server, '/health')
        assert status_code == 503
        assert payload == {'status': 'unhealthy'}
    finally:
        server.stop()


def test_status_endpoint_bearer_authentication():
    server = StatusServer(
        host='127.0.0.1',
        port=0,
        status_provider=lambda: {'status': 'running'},
        health_provider=lambda: (True, {'status': 'ok'}),
        logger=logging.getLogger('test-auth-server'),
        token='monitor-secret',
    ).start()
    try:
        unauthorized, _ = _request(server, '/status')
        authorized, payload = _request(
            server, '/status', token='monitor-secret'
        )
        assert unauthorized == 401
        assert authorized == 200
        assert payload == {'status': 'running'}
        assert 'monitor-secret' not in json.dumps(payload)
    finally:
        server.stop()


def test_status_endpoint_is_read_only(status_server):
    status_code, payload = _request(
        status_server, '/status', method='POST'
    )
    assert status_code == 405
    assert payload == {'error': 'method not allowed'}


def test_systemd_status_uses_safe_selected_properties():
    def runner(command, **kwargs):
        assert command[:3] == [
            'systemctl', 'show', 'school-bell.service'
        ]
        assert kwargs['timeout'] == 2
        return SimpleNamespace(
            returncode=0,
            stdout=(
                'LoadState=loaded\nActiveState=active\nSubState=running\n'
                'MainPID=1234\nExecMainStatus=0\nNRestarts=2\n'
            ),
        )

    assert get_systemd_status(runner=runner) == {
        'available': True,
        'load_state': 'loaded',
        'active_state': 'active',
        'sub_state': 'running',
        'main_pid': 1234,
        'exit_status': 0,
        'restart_count': 2,
    }


def test_school_bell_status_supports_multiple_devices():
    bell = SchoolBell(
        schedule={'Mon': {}},
        wav={},
        root=f'{getcwd()}/samples',
        monitoring={
            'device_id': 'vito-bell-01',
            'labels': {'school': 'vito', 'zone': 'main'},
            'status': {'include_systemd': False},
        },
    )
    try:
        payload = bell.monitoring_status()
        assert payload['device_id'] == 'vito-bell-01'
        assert payload['labels'] == {'school': 'vito', 'zone': 'main'}
        assert payload['schedule'] == {'Mon': {}}
        assert 'monitoring' not in payload
        assert 'systemd' not in payload
    finally:
        bell.close()


def test_status_remains_responsive_while_audio_plays(monkeypatch):
    audio_started = Event()
    release_audio = Event()

    def blocking_audio(*args):
        audio_started.set()
        release_audio.wait(timeout=2)
        return True

    monkeypatch.setattr(school_bell_module, '_play', blocking_audio)
    bell = SchoolBell(
        schedule={},
        wav={'0': 'ClassBell-SoundBible.com-1426436341.wav'},
        root=f'{getcwd()}/samples',
        monitoring={
            'status': {
                'enabled': True,
                'host': '127.0.0.1',
                'port': 0,
                'include_systemd': False,
            },
        },
    )
    ringing = Thread(target=bell.ring, args=('0',))
    try:
        ringing.start()
        assert audio_started.wait(timeout=1)
        host, port = bell.monitoring_address[:2]
        response = urllib.request.urlopen(
            f'http://{host}:{port}/status', timeout=1
        )
        assert response.status == 200
        assert json.load(response)['service'] == 'school-bell'
    finally:
        release_audio.set()
        ringing.join(timeout=2)
        bell.close()
