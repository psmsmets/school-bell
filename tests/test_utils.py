# content of test_utils.py
from school_bell import utils
from datetime import datetime, date


def test_init_logger():
    assert isinstance(utils.init_logger(), utils.logging.Logger)


def test_system_call():
    assert utils.system_call(['echo', 'Hello, World']) is True


def test_to_datetime():
    fmt = '%Y-%m-%d %H:%M:%S.%f'
    now = datetime.now()
    assert now.strftime(fmt) == str(now)
    assert now == utils.to_datetime(str(now))


def test_to_date():
    fmt = '%Y-%m-%d'
    today = date.today()
    assert today.strftime(fmt) == str(today)
    assert today == utils.to_date(str(today))
