import json
import logging
import sys

import pytest

import school_bell.main as main_module
from school_bell.identifiers import content_hash


def test_main_hashes_supplied_json_before_adding_runtime_fields(monkeypatch):
    supplied = {
        'schedule': {'Mon': {'8:30': 0}},
        'wav': {'0': 'bell.wav'},
        'monitoring': {'syslog': {'host': 'graylog.example.com'}},
    }
    created = {}

    class FakeSchoolBell:
        def __init__(self, **config):
            created.update(config)

        def run_schedule(self):
            return True

        def close(self):
            return None

    monkeypatch.setattr(main_module, 'SchoolBell', FakeSchoolBell)
    monkeypatch.setattr(
        main_module, '_configure_startup_monitoring', lambda *args: None
    )
    monkeypatch.setattr(
        sys, 'argv', ['school-bell', json.dumps(supplied, indent=4)]
    )

    main_module.main()

    assert created['config_hash'] == content_hash(supplied)
    assert created['schedule_hash'] == content_hash(supplied['schedule'])
    assert created['debug'] is False
    assert created['test'] is False
    assert content_hash(created) != created['config_hash']


class _RecordHandler(logging.Handler):
    def __init__(self, records):
        super().__init__()
        self.records = records

    def emit(self, record):
        self.records.append(record)


def _capture_startup_events(monkeypatch):
    records = []
    handler = _RecordHandler(records)

    def configure(logger, config):
        logger.addHandler(handler)
        return handler

    monkeypatch.setattr(
        main_module, '_configure_startup_monitoring', configure
    )
    return records, handler


def test_configuration_validation_failure_is_reported_centrally(monkeypatch):
    records, handler = _capture_startup_events(monkeypatch)
    supplied = {
        'schedule': {},
        'monitoring': {'syslog': {'host': 'graylog.example.com'}},
    }
    monkeypatch.setattr(sys, 'argv', ['school-bell', json.dumps(supplied)])

    try:
        with pytest.raises(KeyError, match="'wav'"):
            main_module.main()
    finally:
        logging.getLogger('school-bell').removeHandler(handler)

    event = next(r for r in records if r.event == 'startup_failed')
    assert event.status == 'failure'
    assert event.fields['exception_type'] == 'KeyError'
    assert event.fields['startup_phase'] == 'configuration_validation'
    assert event.fields['error_message']


def test_school_bell_initialization_failure_is_reported_and_reraised(
    monkeypatch,
):
    records, handler = _capture_startup_events(monkeypatch)

    class FailingSchoolBell:
        def __init__(self, **config):
            raise ValueError('Invalid schedule time')

    monkeypatch.setattr(main_module, 'SchoolBell', FailingSchoolBell)
    monkeypatch.setattr(
        sys,
        'argv',
        ['school-bell', json.dumps({'schedule': {}, 'wav': {}})],
    )

    try:
        with pytest.raises(ValueError, match='Invalid schedule time'):
            main_module.main()
    finally:
        logging.getLogger('school-bell').removeHandler(handler)

    event = next(r for r in records if r.event == 'startup_failed')
    assert event.fields == {
        'exception_type': 'ValueError',
        'startup_phase': 'service_initialization',
        'error_message': 'Invalid schedule time',
    }


def test_startup_event_redacts_sensitive_configuration(monkeypatch):
    records, handler = _capture_startup_events(monkeypatch)
    secret = 'do-not-log-this-token'

    class FailingSchoolBell:
        def __init__(self, **config):
            raise RuntimeError(f'component rejected token={secret}')

    monkeypatch.setattr(main_module, 'SchoolBell', FailingSchoolBell)
    monkeypatch.setattr(
        sys,
        'argv',
        ['school-bell', json.dumps({
            'schedule': {},
            'wav': {},
            'monitoring': {
                'token': secret,
                'syslog': {'host': 'graylog.example.com'},
            },
        })],
    )

    try:
        with pytest.raises(RuntimeError):
            main_module.main()
    finally:
        logging.getLogger('school-bell').removeHandler(handler)

    event = next(r for r in records if r.event == 'startup_failed')
    assert secret not in event.getMessage()
    assert secret not in json.dumps(event.fields)
    assert '[REDACTED]' in event.fields['error_message']


def test_logging_failure_does_not_replace_startup_exception(monkeypatch):
    class BrokenHandler(logging.Handler):
        def emit(self, record):
            if getattr(record, 'event', None) == 'startup_failed':
                raise OSError('logging failed')

    handler = BrokenHandler()

    def configure(logger, config):
        logger.addHandler(handler)

    monkeypatch.setattr(
        main_module, '_configure_startup_monitoring', configure
    )
    monkeypatch.setattr(
        sys, 'argv', ['school-bell', json.dumps({'schedule': {}})]
    )

    try:
        with pytest.raises(KeyError, match="'wav'"):
            main_module.main()
    finally:
        logging.getLogger('school-bell').removeHandler(handler)
