import json
import urllib.error
import urllib.request
from os import getcwd
from threading import Event, Thread

import pytest

import school_bell.school_bell as bell_module
from school_bell.school_bell import SchoolBell


def _request(address, payload=None, token=None, method='POST'):
    host, port = address[:2]
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(
        f'http://{host}:{port}/bell', data=data, method=method
    )
    if token is not None:
        request.add_header('Authorization', f'Bearer {token}')
    if data is not None:
        request.add_header('Content-Type', 'application/json')
    try:
        response = urllib.request.urlopen(request, timeout=2)
        return response.status, json.load(response), response.headers
    except urllib.error.HTTPError as err:
        return err.code, json.load(err), err.headers


def _bell(**kwargs):
    return SchoolBell(
        schedule={},
        wav={'0': 'ClassBell-SoundBible.com-1426436341.wav'},
        root=f'{getcwd()}/samples',
        webhook={
            'enabled': True,
            'host': '127.0.0.1',
            'port': 0,
            'token': 'bell-secret',
            **kwargs,
        },
    )


def test_webhook_authentication_and_input_validation(monkeypatch):
    monkeypatch.setattr(bell_module, '_play', lambda *_args: True)
    bell = _bell()
    try:
        unauthorized, payload, headers = _request(
            bell.webhook_address, {'wav_key': '0'}
        )
        invalid, invalid_payload, _ = _request(
            bell.webhook_address, {'wav_key': '../bell.wav'}, 'bell-secret'
        )
        accepted, accepted_payload, _ = _request(
            bell.webhook_address, {'wav_key': '0'}, 'bell-secret'
        )
    finally:
        bell.close()

    assert unauthorized == 401
    assert payload == {'error': 'unauthorized'}
    assert headers['WWW-Authenticate'] == 'Bearer'
    assert invalid == 400
    assert invalid_payload == {'error': 'invalid wav_key'}
    assert accepted == 202
    assert accepted_payload == {'status': 'accepted', 'wav_key': '0'}
    assert 'bell.wav' not in json.dumps(accepted_payload)


@pytest.mark.parametrize('payload', [
    None,
    {},
    {'wav_key': True},
    {'wav_key': '0', 'path': '/tmp/bell.wav'},
])
def test_webhook_rejects_malformed_payload(payload, monkeypatch):
    monkeypatch.setattr(bell_module, '_play', lambda *_args: True)
    bell = _bell()
    try:
        status, response, _ = _request(
            bell.webhook_address, payload, 'bell-secret'
        )
    finally:
        bell.close()
    assert status == 400
    assert response == {'error': 'invalid request'}


def test_webhook_returns_conflict_while_bell_is_active(monkeypatch):
    started = Event()
    release = Event()

    def play(*_args):
        started.set()
        assert release.wait(2)
        return True

    monkeypatch.setattr(bell_module, '_play', play)
    bell = _bell()
    first_result = []
    first = Thread(target=lambda: first_result.append(_request(
        bell.webhook_address, {'wav_key': '0'}, 'bell-secret'
    )))
    try:
        first.start()
        assert started.wait(1)
        status, payload, _ = _request(
            bell.webhook_address, {'wav_key': '0'}, 'bell-secret'
        )
        assert status == 409
        assert payload == {'error': 'bell active'}
    finally:
        release.set()
        first.join(2)
        bell.close()
    assert first_result[0][0] == 202


def test_webhook_returns_503_when_playback_fails(monkeypatch):
    monkeypatch.setattr(bell_module, '_play', lambda *_args: False)
    bell = _bell()
    try:
        status, payload, _ = _request(
            bell.webhook_address, {'wav_key': '0'}, 'bell-secret'
        )
    finally:
        bell.close()
    assert status == 503
    assert payload == {'error': 'playback unavailable'}


def test_webhook_rate_limiting(monkeypatch):
    monkeypatch.setattr(bell_module, '_play', lambda *_args: True)
    bell = _bell(rate_limit=1, rate_window=30)
    try:
        first, _, _ = _request(
            bell.webhook_address, {'wav_key': '0'}, 'bell-secret'
        )
        limited, payload, headers = _request(
            bell.webhook_address, {'wav_key': '0'}, 'bell-secret'
        )
    finally:
        bell.close()
    assert first == 202
    assert limited == 429
    assert payload == {'error': 'rate limit exceeded'}
    assert int(headers['Retry-After']) > 0


def test_webhook_emits_lifecycle_events(monkeypatch):
    events = []

    def capture(_logger, event, status='success', level=20, **fields):
        events.append({'event': event, 'status': status, **fields})

    monkeypatch.setattr(bell_module, 'log_event', capture)
    monkeypatch.setattr(bell_module, '_play', lambda *_args: True)
    bell = _bell()
    try:
        status, _, _ = _request(
            bell.webhook_address, {'wav_key': '0'}, 'bell-secret'
        )
    finally:
        bell.close()
    assert status == 202
    assert any(e['event'] == 'webhook_bell_triggered' for e in events)
    assert any(e['event'] == 'webhook_bell_completed' for e in events)
