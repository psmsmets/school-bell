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
    def __init__(self, pin):
        self.pin = pin
        self.on_calls = 0
        self.off_calls = 0

    def on(self):
        self.on_calls += 1

    def off(self):
        self.off_calls += 1


@pytest.fixture
def fake_buzzers(monkeypatch):
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


@pytest.mark.parametrize("gpio_pins", [True, "17", [17, "27"]])
def test_invalid_buzzer_pins(gpio_pins, fake_buzzers):
    with pytest.raises(TypeError):
        create_buzzer(gpio_pins)


def test_school_bell(device):
    bell = SchoolBell(**create_args(device))
    assert bell.play(0) is True
    assert bell.ring(1) != bell.is_holiday()
    assert bell.run_schedule(_test_mode=True) is True
