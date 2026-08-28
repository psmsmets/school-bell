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

    def __init__(self, pin):
        self.pin = pin
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
