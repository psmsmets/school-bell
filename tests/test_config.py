import json

import pytest
from pydantic import ValidationError

from school_bell.config import config_json_schema, validate_config


def minimal_config():
    return {
        'schedule': {'Mon': {'08:30': '0'}},
        'wav': {'0': 'bell.wav'},
    }


def test_minimal_configuration_is_valid():
    config = validate_config(minimal_config())

    assert config.schedule == {'Mon': {'08:30': '0'}}
    assert config.timezone == 'Europe/Brussels'


def test_root_value_must_be_a_configuration_object():
    with pytest.raises(ValidationError) as error:
        validate_config([])

    assert error.value.errors()[0]['loc'] == ()


def test_demo_configuration_is_valid():
    with open('demo.json') as demo_file:
        config = validate_config(json.load(demo_file))

    assert config.manual_bell.wav_key == '0'
    assert config.webhook.enabled is False


def test_legacy_representations_remain_supported():
    supplied = minimal_config()
    supplied.update({
        'schedule': {'mon': {'8:30': 0}},
        'timeout': '10',
        'manual_bell': {
            'gpio': 17,
            'wav_key': 0,
            'mode': 'ONCE',
            'pull': 'UP',
            'bounce_time': '0.05',
            'remote_bells': [{
                'host': 'bell.local',
                'command': 'ring',
                'timeout': '5',
            }],
        },
        'monitoring': {
            'heartbeat_interval': '300',
            'syslog': {
                'host': 'graylog.local',
                'port': '1514',
                'protocol': 'UDP',
            },
        },
    })

    config = validate_config(supplied)

    assert config.schedule == {'mon': {'8:30': '0'}}
    assert config.timeout == 10
    assert config.manual_bell.wav_key == '0'
    assert config.manual_bell.remote_bells[0].transport == 'ssh'
    assert config.monitoring.syslog.protocol == 'udp'


@pytest.mark.parametrize('missing', ['schedule', 'wav'])
def test_required_fields_are_reported(missing):
    supplied = minimal_config()
    del supplied[missing]

    with pytest.raises(ValidationError) as error:
        validate_config(supplied)

    assert error.value.errors()[0]['loc'] == (missing,)


def test_type_errors_are_strict():
    supplied = minimal_config()
    supplied['buzz_active_high'] = 1

    with pytest.raises(ValidationError) as error:
        validate_config(supplied)

    assert error.value.errors()[0]['loc'] == ('buzz_active_high',)


def test_unknown_fields_are_rejected_at_every_level():
    supplied = minimal_config()
    supplied['monitoring'] = {
        'status': {'enabled': True, 'unknown': 'value'}
    }

    with pytest.raises(ValidationError) as error:
        validate_config(supplied)

    assert error.value.errors()[0]['loc'] == (
        'monitoring', 'status', 'unknown'
    )


def test_invalid_nested_configuration_has_precise_path():
    supplied = minimal_config()
    supplied['manual_bell'] = {
        'gpio': 17,
        'wav_key': '0',
        'remote_bells': [{
            'transport': 'webhook',
            'url': 'https://bell.local/bell',
            'timeout': 0,
        }],
    }

    with pytest.raises(ValidationError) as error:
        validate_config(supplied)

    assert error.value.errors()[0]['loc'] == (
        'manual_bell', 'remote_bells', 0, 'webhook', 'timeout'
    )


def test_runtime_values_are_not_configuration_fields():
    for field in ('debug', 'test', 'prog', 'config_hash', 'schedule_hash'):
        supplied = minimal_config()
        supplied[field] = 'not user controlled'
        with pytest.raises(ValidationError) as error:
            validate_config(supplied)
        assert error.value.errors()[0]['loc'] == (field,)


def test_cross_field_references_are_validated():
    supplied = minimal_config()
    supplied['manual_bell'] = {'gpio': 17, 'wav_key': 'missing'}

    with pytest.raises(ValidationError, match='manual_bell.wav_key'):
        validate_config(supplied)


def test_key_specific_relays_normalize_single_and_numeric_wav_keys():
    supplied = minimal_config()
    supplied['wav']['1'] = 'workshop.wav'
    supplied['relays'] = [
        {'gpio': 26, 'wav_keys': '0', 'active_high': False},
        {'gpio': 20, 'wav_keys': [0, '1']},
    ]

    config = validate_config(supplied)

    assert config.relays[0].wav_keys == ['0']
    assert config.relays[0].active_high is False
    assert config.relays[1].wav_keys == ['0', '1']
    assert config.relays[1].active_high is True


@pytest.mark.parametrize(
    'relays, message',
    [
        ([{'gpio': 26, 'wav_keys': []}], 'at least one WAVE key'),
        ([{'gpio': 26, 'wav_keys': ['missing']}], 'unknown WAV key'),
        (
            [
                {'gpio': 26, 'wav_keys': '0'},
                {'gpio': 26, 'wav_keys': '0'},
            ],
            'unique GPIO pins',
        ),
    ],
)
def test_invalid_key_specific_relays_are_rejected(relays, message):
    supplied = minimal_config()
    supplied['relays'] = relays

    with pytest.raises(ValidationError, match=message):
        validate_config(supplied)


def test_legacy_and_key_specific_relays_cannot_be_combined():
    supplied = minimal_config()
    supplied['buzz_gpio'] = 17
    supplied['relays'] = [{'gpio': 26, 'wav_keys': '0'}]

    with pytest.raises(ValidationError, match='cannot be combined'):
        validate_config(supplied)


def test_manual_input_cannot_reuse_key_specific_relay_pin():
    supplied = minimal_config()
    supplied['relays'] = [{'gpio': 26, 'wav_keys': '0'}]
    supplied['manual_bell'] = {'gpio': 26, 'wav_key': '0'}

    with pytest.raises(ValidationError, match='must not also be a relay'):
        validate_config(supplied)


def test_json_schema_forbids_unknown_fields():
    schema = config_json_schema()

    assert schema['additionalProperties'] is False
    assert set(schema['required']) == {'schedule', 'wav'}
