# content of test_school_bell.py
from os import getcwd
import pytest
import school_bell.school_bell as school_bell_module
from school_bell.school_bell import SchoolBell, _validate_day, _validate_time


def create_args(device):
    return {
        'schedule': {
            'Wed': {
                '08:30': '0',
                '10:30': '1'
            }
        },
        'wav': {
            '0': 'ClassBell-SoundBible.com-1426436341.wav',
            '1': 'SchoolBell-SoundBible.com-449398625.wav'
        },
        'root': f"{getcwd()}/samples",
        'device': device,
        'test': True,
        'timeout': 10,
        'holidays': 'BE-NL',
        'debug': True,
    }


def test_validate_day():
    assert _validate_day('Mon') is True
    assert _validate_day('Tue') is True
    assert _validate_day('Wed') is True
    assert _validate_day('Thu') is True
    assert _validate_day('Fri') is True
    assert _validate_day('Sat') is True
    assert _validate_day('Sun') is True


def test_validate_time():
    assert _validate_time("0:0") is True
    assert _validate_time("00:00") is True
    assert _validate_time("9:9") is True
    assert _validate_time("23:59") is True
    assert _validate_time("24:00") is False
    assert _validate_time("23:60") is False
    assert _validate_time("99:99") is False
    assert _validate_time("00:00:00") is True
    assert _validate_time("00:00:59") is True
    assert _validate_time("00:00:60") is False


class FakeBuzzer:
    instances = []
    events = []

    def __init__(self, pin, active_high=True, initial_value=False):
        self.pin = pin
        self.active_high = active_high
        self.initial_value = initial_value
        self.on_calls = 0
        self.off_calls = 0
        self.instances.append(self)

    def on(self):
        self.on_calls += 1
        self.events.append((self.pin, "on"))

    def off(self):
        self.off_calls += 1
        self.events.append((self.pin, "off"))


@pytest.fixture
def fake_buzzers(monkeypatch):
    FakeBuzzer.instances = []
    FakeBuzzer.events = []
    monkeypatch.setattr(school_bell_module, "is_raspberry_pi", lambda: True)
    monkeypatch.setattr(school_bell_module, "Buzzer", FakeBuzzer)


@pytest.fixture
def structured_events(monkeypatch):
    events = []

    def capture(_logger, event, status='success', level=20,
                message=None, **fields):
        events.append({
            'event': event,
            'status': status,
            'level': level,
            **fields,
        })

    monkeypatch.setattr(school_bell_module, 'log_event', capture)
    return events


def create_buzzer(gpio_pins):
    return SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        buzz_gpio=gpio_pins,
    ).buzzer


def test_single_buzzer_is_backwards_compatible(fake_buzzers):
    buzzers = create_buzzer(17)
    assert [buzzer.pin for buzzer in buzzers] == [17]


def test_multiple_buzzers(fake_buzzers):
    buzzers = create_buzzer([17, 27])
    assert [buzzer.pin for buzzer in buzzers] == [17, 27]


@pytest.mark.parametrize('active_high', [True, False])
def test_buzzer_polarity_and_safe_initial_state(active_high, fake_buzzers):
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        buzz_gpio=[17, 27],
        buzz_active_high=active_high,
    )

    assert bell.buzz_active_high is active_high
    assert all(
        buzzer.active_high is active_high for buzzer in bell.buzzer
    )
    assert all(buzzer.initial_value is False for buzzer in bell.buzzer)


@pytest.mark.parametrize('active_high', [None, 0, 1, 'false'])
def test_invalid_buzzer_polarity(active_high, fake_buzzers):
    with pytest.raises(TypeError, match='buzz_active_high'):
        SchoolBell(
            schedule={},
            wav={},
            root=f"{getcwd()}/samples",
            buzz_gpio=17,
            buzz_active_high=active_high,
        )


def test_close_returns_relays_to_inactive_state(fake_buzzers):
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        buzz_gpio=[17, 27],
        buzz_active_high=False,
    )

    for buzzer in bell.buzzer:
        buzzer.on()
    bell.close()

    assert all(buzzer.off_calls == 1 for buzzer in bell.buzzer)


def test_multiple_buzzers_switch_together(fake_buzzers, monkeypatch):
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        buzz_gpio=[17, 27],
    )
    monkeypatch.setattr(bell, "is_holiday", lambda: False)
    monkeypatch.setattr(bell, "get_wav", lambda key, root=None: "bell.wav")
    monkeypatch.setattr(school_bell_module, "_play", lambda *args: True)

    assert bell.ring("0") is True
    assert [buzzer.on_calls for buzzer in bell.buzzer] == [1, 1]
    assert [buzzer.off_calls for buzzer in bell.buzzer] == [1, 1]


def test_gpio_events_include_state_and_cleanup_after_error(
    fake_buzzers, structured_events, monkeypatch
):
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        buzz_gpio=[17, 27],
        buzz_active_high=False,
    )
    monkeypatch.setattr(bell, 'is_holiday', lambda: False)
    monkeypatch.setattr(bell, 'get_wav', lambda key, root=None: 'bell.wav')
    monkeypatch.setattr(school_bell_module, '_play', lambda *args: False)

    with pytest.raises(RuntimeError, match='audio outputs failed'):
        bell.ring('0')

    gpio_events = [
        event for event in structured_events
        if event['event'].startswith('gpio_')
    ]
    assert gpio_events == [
        {
            'event': 'gpio_activated',
            'status': 'success',
            'level': 20,
            'gpio_pins': [17, 27],
            'gpio_active_high': False,
            'gpio_state': 'active',
        },
        {
            'event': 'gpio_deactivated',
            'status': 'success',
            'level': 20,
            'gpio_pins': [17, 27],
            'gpio_active_high': False,
            'gpio_state': 'inactive',
        },
    ]


def test_gpio_activation_failure_emits_failure_and_cleanup_events(
    fake_buzzers, structured_events, monkeypatch
):
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        buzz_gpio=[17, 27],
        buzz_active_high=False,
    )
    monkeypatch.setattr(bell, 'is_holiday', lambda: False)
    monkeypatch.setattr(bell, 'get_wav', lambda key, root=None: 'bell.wav')

    def fail_activation():
        raise RuntimeError('GPIO unavailable')

    monkeypatch.setattr(bell.buzzer[0], 'on', fail_activation)

    with pytest.raises(RuntimeError, match='GPIO unavailable'):
        bell.ring('0')

    gpio_events = [
        event for event in structured_events
        if event['event'].startswith('gpio_')
    ]
    assert gpio_events[0]['event'] == 'gpio_activated'
    assert gpio_events[0]['status'] == 'failure'
    assert gpio_events[0]['gpio_state'] == 'unknown'
    assert gpio_events[0]['error_category'] == 'gpio_activation_error'
    assert gpio_events[-1]['event'] == 'gpio_deactivated'
    assert gpio_events[-1]['status'] == 'success'
    assert gpio_events[-1]['gpio_state'] == 'inactive'


@pytest.mark.parametrize('success', [True, False])
def test_remote_trigger_events_report_success_and_failure(
    success, structured_events, monkeypatch
):
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
    )
    monkeypatch.setattr(
        bell, 'get_remote_wav', lambda host, key: '/remote/bell.wav'
    )
    monkeypatch.setattr(
        school_bell_module, '_play_remote', lambda **kwargs: success
    )
    times = iter([10.0, 10.25])
    monkeypatch.setattr(school_bell_module, 'monotonic', lambda: next(times))

    if success:
        assert bell.play_remote('pibell-02', '1') is True
    else:
        with pytest.raises(RuntimeError, match='remote WAVE'):
            bell.play_remote('pibell-02', '1')

    event = next(
        event for event in structured_events
        if event['event'] == 'remote_trigger'
    )
    assert event['remote_host'] == 'pibell-02'
    assert event['wav_key'] == '1'
    assert event['duration_seconds'] == 0.25
    assert event['status'] == ('success' if success else 'failure')
    if success:
        assert 'error_category' not in event
    else:
        assert event['error_category'] == 'remote_trigger_error'


def test_scheduled_ring_emits_remote_trigger_event(
    structured_events, monkeypatch
):
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
    )
    bell.trigger['pibell-02'] = '/remote/samples'
    monkeypatch.setattr(bell, 'is_holiday', lambda: False)
    monkeypatch.setattr(bell, 'get_wav', lambda key, root=None: 'bell.wav')
    monkeypatch.setattr(school_bell_module, '_play', lambda *args: True)
    monkeypatch.setattr(
        school_bell_module, '_play_remote', lambda **kwargs: True
    )

    assert bell.ring('0') is True

    event = next(
        event for event in structured_events
        if event['event'] == 'remote_trigger'
    )
    assert event['remote_host'] == 'pibell-02'
    assert event['wav_key'] == '0'
    assert event['status'] == 'success'


def test_scheduled_events_share_revision_and_trigger_context(
    structured_events, monkeypatch
):
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        config_hash='config-a',
        schedule_hash='schedule-a',
        monitoring={'device_id': 'bell-01'},
    )
    bell.trigger['pibell-02'] = '/remote/samples'
    monkeypatch.setattr(bell, 'is_holiday', lambda: False)
    monkeypatch.setattr(bell, 'get_wav', lambda key, root=None: 'bell.wav')
    monkeypatch.setattr(school_bell_module, '_play', lambda *args: True)
    monkeypatch.setattr(
        school_bell_module, '_play_remote', lambda **kwargs: True
    )
    context = {
        'schedule_entry_id': 'entry-a',
        'weekday': 'Monday',
        'local_time': '08:30:00',
    }

    assert bell.ring('0', _schedule_context=context) is True

    related = [
        event for event in structured_events
        if event['event'] in ('remote_trigger', 'bell_ring')
    ]
    assert len(related) == 2
    assert {event['trigger_id'] for event in related} == {
        related[0]['trigger_id']
    }
    for event in related:
        assert event['config_hash'] == 'config-a'
        assert event['schedule_hash'] == 'schedule-a'
        assert event['config_hash_short'] == 'config-a'
        assert event['schedule_hash_short'] == 'schedule-a'
        assert event['schedule_entry_id'] == 'entry-a'
        assert event['planned_at']
        assert event['local_date']
        assert event['weekday'] == 'Monday'
        assert event['timezone']
        assert 'schedule_entry_id_short' not in event
        assert 'trigger_id_short' not in event


def test_holiday_skip_contains_scheduled_context(
    structured_events, monkeypatch
):
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        config_hash='config-a',
        schedule_hash='schedule-a',
        monitoring={'device_id': 'bell-01'},
    )
    monkeypatch.setattr(bell, 'is_holiday', lambda: True)

    assert bell.ring('0', _schedule_context={
        'schedule_entry_id': 'entry-a',
        'weekday': 'Monday',
        'local_time': '08:30:00',
    }) is False

    event = next(
        event for event in structured_events
        if event['event'] == 'bell_skipped_holiday'
    )
    assert event['trigger_id']
    assert event['schedule_entry_id'] == 'entry-a'
    assert event['config_hash'] == 'config-a'
    assert event['config_hash_short'] == 'config-a'


def test_schedule_entry_event_uses_canonical_day_time_and_wav_key(
    structured_events
):
    school_bell_module.schedule.clear()
    try:
        bell = SchoolBell(
            schedule={'Mon': {'8:30': 0}},
            wav={'0': 'ClassBell-SoundBible.com-1426436341.wav'},
            root=f"{getcwd()}/samples",
            config_hash='config-a',
            schedule_hash='schedule-a',
        )
    finally:
        school_bell_module.schedule.clear()

    event = next(
        event for event in structured_events
        if event['event'] == 'schedule_entry_loaded'
    )
    assert event['weekday'] == 'Monday'
    assert event['local_time'] == '08:30:00'
    assert event['wav_key'] == '0'
    assert event['schedule_entry_id']
    assert event['config_hash'] == 'config-a'
    assert event['schedule_hash'] == 'schedule-a'
    assert event['config_hash_short'] == 'config-a'
    assert event['schedule_hash_short'] == 'schedule-a'
    bell.close()


def test_ring_fails_when_audio_output_fails(monkeypatch):
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        monitoring={'status': {'include_systemd': False}},
    )
    monkeypatch.setattr(bell, "is_holiday", lambda: False)
    monkeypatch.setattr(bell, "get_wav", lambda key, root=None: "bell.wav")
    monkeypatch.setattr(school_bell_module, "_play", lambda *args: False)

    with pytest.raises(RuntimeError, match="audio outputs failed"):
        bell.ring("0")

    assert bell.monitoring_status()['last_error']['category'] == 'bell_error'


@pytest.mark.parametrize("gpio_pins", [17, [17, 27]])
def test_buzzers_at_startup(gpio_pins, fake_buzzers, monkeypatch):
    monkeypatch.setattr(school_bell_module, "sleep", lambda duration: None)

    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        buzz_gpio=gpio_pins,
        test=True,
    )

    pins = gpio_pins if isinstance(gpio_pins, list) else [gpio_pins]
    assert [event for event in FakeBuzzer.events if event[1] == "on"] == [
        (pin, "on") for pin in pins
    ]
    assert all(buzzer.off_calls >= 1 for buzzer in bell.buzzer)


def test_buzzer_test_is_sequential(fake_buzzers, monkeypatch):
    durations = []
    monkeypatch.setattr(
        school_bell_module, "sleep", lambda duration: durations.append(duration)
    )

    SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        buzz_gpio=[17, 27],
        test=True,
    )

    assert FakeBuzzer.events[:4] == [
        (17, "on"),
        (17, "off"),
        (27, "on"),
        (27, "off"),
    ]
    assert durations == [1.0, 1.0]


@pytest.mark.parametrize("exception_type", [RuntimeError, KeyboardInterrupt])
def test_buzzer_test_cleans_up_after_error(
    exception_type, fake_buzzers, monkeypatch
):
    def fail(_duration):
        raise exception_type("test interruption")

    monkeypatch.setattr(school_bell_module, "sleep", fail)

    with pytest.raises(exception_type, match="test interruption"):
        SchoolBell(
            schedule={},
            wav={},
            root=f"{getcwd()}/samples",
            buzz_gpio=[17, 27],
            test=True,
        )

    assert all(buzzer.off_calls >= 1 for buzzer in FakeBuzzer.instances)


def test_buzzer_test_without_configured_pins(fake_buzzers):
    bell = SchoolBell(
        schedule={},
        wav={},
        root=f"{getcwd()}/samples",
        test=True,
    )

    assert bell.test_buzzers() is True


@pytest.mark.parametrize("gpio_pins", [True, "17", [17, "27"]])
def test_invalid_buzzer_pins(gpio_pins, fake_buzzers):
    with pytest.raises(TypeError):
        create_buzzer(gpio_pins)


def test_school_bell(device):
    bell = SchoolBell(**create_args(device))
    assert bell.play(0) is True
    assert bell.ring(1) != bell.is_holiday()
    assert bell.run_schedule(_test_mode=True) is True
