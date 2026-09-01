# content of test_utils.py
from school_bell import utils
from datetime import datetime, date
from subprocess import TimeoutExpired


def test_init_logger():
    assert isinstance(utils.init_logger(), utils.logging.Logger)


def test_system_call():
    assert utils.system_call(['echo', 'Hello, World']) is True


def test_system_call_kills_process_on_timeout(monkeypatch):
    class TimedOutProcess:
        returncode = None

        def __init__(self):
            self.communications = 0
            self.killed = False

        def communicate(self, timeout=None):
            self.communications += 1
            if self.communications == 1:
                assert timeout == 2
                raise TimeoutExpired(['slow-command'], timeout)
            return b'', b''

        def kill(self):
            self.killed = True

    process = TimedOutProcess()
    monkeypatch.setattr(utils, 'Popen', lambda *args, **kwargs: process)

    assert utils.system_call(['slow-command'], timeout=2) is False
    assert process.killed is True


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
