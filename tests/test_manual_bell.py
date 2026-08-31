from os import getcwd
from threading import Event, Thread

import pytest

import school_bell.manual_bell as manual_module
import school_bell.school_bell as bell_module
from school_bell.manual_bell import ManualBellInput
from school_bell.school_bell import SchoolBell


class FakeButton:
    instances = []

    def __init__(self, pin, pull_up=True, bounce_time=None):
        self.pin = pin
        self.pull_up = pull_up
        self.bounce_time = bounce_time
        self.when_pressed = None
        self.when_released = None
        self.closed = False
        self.instances.append(self)

    def press(self):
        self.when_pressed()

    def release(self):
        if self.when_released is not None:
            self.when_released()

    def close(self):
        self.closed = True


class FakeRelay:
    def __init__(self, pin, **_kwargs):
        self.pin = pin
        self.on_calls = 0
        self.off_calls = 0

    def on(self):
        self.on_calls += 1

    def off(self):
        self.off_calls += 1


@pytest.fixture
def gpio(monkeypatch):
    FakeButton.instances = []
    monkeypatch.setattr(manual_module, 'Button', FakeButton)
    monkeypatch.setattr(bell_module, 'is_raspberry_pi', lambda: True)
    monkeypatch.setattr(bell_module, 'Buzzer', FakeRelay)


@pytest.fixture
def events(monkeypatch):
    captured = []

    def capture(_logger, event, status='success', level=20,
                message=None, **fields):
        captured.append({'event': event, 'status': status, **fields})

    monkeypatch.setattr(bell_module, 'log_event', capture)
    return captured


def bell(**kwargs):
    return SchoolBell(
        schedule={},
        wav={'0': 'ClassBell-SoundBible.com-1426436341.wav'},
        root=f'{getcwd()}/samples',
        **kwargs,
    )


def test_single_button_configuration_and_debounce(gpio, monkeypatch):
    monkeypatch.setattr(bell_module, '_play', lambda *args: True)
    obj = bell(manual_bell={
        'gpio': 17, 'wav_key': '0', 'mode': 'once',
        'pull': 'down', 'bounce_time': .08,
    })
    button = FakeButton.instances[0]
    assert button.pin == 17
    assert button.pull_up is False
    assert button.bounce_time == .08
    assert button.when_pressed is not None
    assert button.when_released is None
    obj.close()
    assert button.closed is True


def test_once_button_plays_complete_signal(gpio, events, monkeypatch):
    completed = Event()
    monkeypatch.setattr(
        bell_module, '_play',
        lambda *args: completed.set() or True,
    )
    obj = bell(manual_bell={
        'gpio': 17, 'wav_key': '0', 'mode': 'once'
    })
    FakeButton.instances[0].press()
    assert completed.wait(1)
    obj.close()
    assert any(e['event'] == 'manual_bell_triggered' for e in events)
    assert any(e['event'] == 'manual_bell_completed' for e in events)


def test_hold_button_release_cancels_and_releases_relays(
    gpio, events, monkeypatch
):
    waiting = Event()

    class Playback:
        def wait(self, cancel_event):
            waiting.set()
            assert cancel_event.wait(1)
            return True, True

        def stop(self):
            pass

    monkeypatch.setattr(
        bell_module, '_start_playback', lambda *args: Playback()
    )
    obj = bell(
        buzz_gpio=27,
        manual_bell={'gpio': 17, 'wav_key': '0', 'mode': 'hold'},
    )
    button = FakeButton.instances[0]
    button.press()
    assert waiting.wait(1)
    button.release()
    obj.close()
    relay = obj.buzzer[0]
    assert relay.on_calls == 1
    assert relay.off_calls >= 1
    assert any(e['event'] == 'manual_bell_cancelled' for e in events)


def test_concurrent_trigger_is_ignored(events, monkeypatch):
    started = Event()
    finish = Event()

    def blocking_play(*_args):
        started.set()
        assert finish.wait(1)
        return True

    monkeypatch.setattr(bell_module, '_play', blocking_play)
    obj = bell()
    first = Thread(target=obj.trigger_bell, args=('0', 'scheduled'))
    first.start()
    assert started.wait(1)
    assert obj.trigger_bell(
        '0', source='manual_gpio', respect_calendar=False,
        include_remote=False,
    ) is False
    finish.set()
    first.join(1)
    assert not first.is_alive()
    ignored = next(e for e in events if e['event'] == 'bell_trigger_ignored')
    assert ignored['reason'] == 'bell_active'
    assert ignored['active_trigger_source'] == 'scheduled'


def test_remote_trigger_cannot_overlap_active_manual_signal(
    events, monkeypatch
):
    started = Event()
    finish = Event()
    remote_calls = []

    def blocking_play(*_args):
        started.set()
        assert finish.wait(1)
        return True

    monkeypatch.setattr(bell_module, '_play', blocking_play)
    monkeypatch.setattr(
        bell_module, '_play_remote',
        lambda **kwargs: remote_calls.append(kwargs) or True,
    )
    obj = bell()
    manual = Thread(target=obj.trigger_bell, kwargs={
        'key': '0', 'source': 'manual_gpio',
        'respect_calendar': False, 'include_remote': False,
    })
    manual.start()
    assert started.wait(1)
    assert obj.play_remote('bell-02', '0') is False
    assert remote_calls == []
    finish.set()
    manual.join(1)
    assert any(e['event'] == 'bell_trigger_ignored' for e in events)


def test_manual_failure_is_reported_and_relay_is_released(
    gpio, events, monkeypatch
):
    monkeypatch.setattr(bell_module, '_play', lambda *_args: False)
    obj = bell(buzz_gpio=27)
    with pytest.raises(RuntimeError, match='audio outputs failed'):
        obj.trigger_bell(
            '0', source='manual_gpio', respect_calendar=False,
            include_remote=False,
        )
    relay = obj.buzzer[0]
    assert relay.on_calls == 1
    assert relay.off_calls == 1
    failure = next(e for e in events if e['event'] == 'manual_bell_failed')
    assert failure['status'] == 'failure'
    assert failure['error_category'] == 'manual_bell_error'


@pytest.mark.parametrize('pull,pull_up', [
    ('up', True), ('down', False), ('floating', None),
])
def test_pull_modes(pull, pull_up, monkeypatch):
    FakeButton.instances = []
    monkeypatch.setattr(manual_module, 'Button', FakeButton)
    item = ManualBellInput(
        {'gpio': 17, 'wav_key': '0', 'pull': pull},
        trigger=lambda *_args, **_kwargs: True,
        logger=bell_module.init_logger('manual-test'),
    )
    assert item.button.pull_up is pull_up
    item.close()


def test_input_pin_cannot_be_relay_output():
    with pytest.raises(ValueError, match='buzz_gpio'):
        ManualBellInput.validate(
            {'gpio': 17, 'wav_key': '0'}, output_pins=[17]
        )
