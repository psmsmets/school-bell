# content of test_school_bell.py
from os import getcwd
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
        'holidays': 'NL-BE',
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


def test_school_bell(device):
    bell = SchoolBell(**create_args(device))
    assert bell.play(0) is True
    assert bell.ring(1) != bell.is_holiday()
    assert bell.run_schedule(_test_mode=True) is True
