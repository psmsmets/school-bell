# content of test_utils.py
from school_bell import utils
from datetime import date


def test_init_logger():
    assert isinstance(utils.init_logger(), utils.logging.Logger)


def test_system_call():
    assert utils.system_call(['echo', 'Hello, World']) is True


def test_today_is_holiday():
    today = f"{date.today()}"
    oh = utils.OpenHolidays('BE', 'NL', 'NL-BE')
    assert utils.today_is_holiday('NL-BE') == oh.isHoliday(today)
