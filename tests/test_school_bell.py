# content of test_school_bell.py
from school_bell.school_bell import SchoolBell, _validate_day, _validate_time


def test_validate_day():
    assert _validate_day('Mon') is True
    assert _validate_day('Tue') is True
    assert _validate_day('Wed') is True
    assert _validate_day('Thu') is True
    assert _validate_day('Fri') is True
    assert _validate_day('Sat') is True
    assert _validate_day('Sun') is True


def test_validate_day():
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
