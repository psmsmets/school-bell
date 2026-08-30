import json
import sys

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
        sys, 'argv', ['school-bell', json.dumps(supplied, indent=4)]
    )

    main_module.main()

    assert created['config_hash'] == content_hash(supplied)
    assert created['schedule_hash'] == content_hash(supplied['schedule'])
    assert created['debug'] is False
    assert created['test'] is False
    assert content_hash(created) != created['config_hash']
