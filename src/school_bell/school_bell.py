#!/usr/bin/python3

# absolute imports
import calendar
import datetime
import os
import re
import requests
import schedule
import sys
from gpiozero import Buzzer
from logging import Logger
from threading import Thread
from time import sleep

# Relative imports
from .openholidays import OpenHolidays, is_holiday
from .utils import init_logger, is_raspberry_pi, system_call
try:
    from .version import version
except (ValueError, ModuleNotFoundError, SyntaxError):
    version = "VERSION-NOT-FOUND"


__all__ = ['SchoolBell']


# Check platform and set wav player
if sys.platform in ("win32", "win64"):
    raise NotImplementedError("school_bell does not run on Windows")
elif sys.platform == "darwin":
    __alsa = False
    __play = ["/usr/bin/afplay"]
    __play_test = __play + ['-t', '1']
else:
    __alsa = True
    __play = ["/usr/bin/aplay"]
    __play_test = __play + ['-d', '1']


class SchoolBell(object):
    """Python scheduling of the school bell.
    """

    def __init__(
        self,
        schedule: dict,
        wav: dict,
        root: str = None,
        test: bool = None,
        device: str = None,
        buzz_gpio: int = None,
        timeout: int = None,
        holidays: str = None,
        trigger: dict = None,
        debug: bool = None,
        prog: str = None,
        info: str = None,
    ):
        """Initialize the SchoolBell object
        """

        # Preamble
        prog = prog or 'school-bell'
        info = info or 'Python-scheduled ringing of a school bell.'
        self.__logger = init_logger(prog, debug or False)
        self.__alsa = sys.platform != "darwin"
        self.log.info(info)
        self.log.info(f"version = {version}")

        # Init
        self.root = root or None
        self.test = test or False
        self.device = device or None
        self.buzzer = buzz_gpio or None
        self.timeout = timeout or 10
        self.openholidays = holidays or None
        self.trigger = trigger or dict()
        self.wav = wav or dict()

        # Create schedule
        self.create_schedule(schedule)

    @property
    def device(self):
        """Internal property to the alsa device.
        """
        return self.__device if self.__alsa else None

    @device.setter
    def device(self, value: str):
        """Internal property to the alsa device.
        """
        if self.__alsa:
            self.log.info(f"alsa device = {value}")
            try:
                self.__device = str(value)
            except ValueError as err:
                self.log.error(err)

    @property
    def buzzer(self):
        """Get the buzzer object.
        """
        return self.__buzzer

    @buzzer.setter
    def buzzer(self, gpio_pin: int):
        self.log.info(f"buzzer = {gpio_pin or False}")
        self.__buzzer = False
        if isinstance(gpio_pin, int):
            if is_raspberry_pi():
                try:
                    self.__buzzer = Buzzer(gpio_pin)
                    self.log.debug(f"  {self.__buzzer}")
                except Exception as err:
                    self.log.error(err)
                    raise Exception(err)
            else:
                self.log.warning("Host is not a Raspberry Pi:"
                                 " buzzer disabled!")

    @property
    def log(self):
        """Get the logger object.
        """
        return self.__logger

    @property
    def root(self):
        """Get the root directory.
        """
        return self.__root

    @root.setter
    def root(self, value: str):
        """Set the root directory.
        """
        self.log.info(f"root = {value}")
        path = os.path.expandvars(value or '')
        if os.path.isdir(path):
            self.__root = value
        else:
            err = f"Root directory \"{value}\" does not exist!"
            self.log.error(err)
            raise FileNotFoundError(err)

    @property
    def test(self):
        """Get the test status.
        """
        return self.__test

    @test.setter
    def test(self, value: bool):
        """Set the test status.
        """
        self.log.info(f"test = {value}")
        try:
            self.__test = bool(value)
        except ValueError as err:
            self.log.error(err)

    @property
    def timeout(self):
        """Get the timeout value.
        """
        return self.__timeout

    @timeout.setter
    def timeout(self, value: int):
        """Set the timeout value.
        """
        self.log.info(f"timeout = {value}")
        try:
            self.__timeout = int(value)
        except ValueError as err:
            self.log.error(err)

    @property
    def openholidays(self):
        """Get the OpenHolidays object.
        """
        return self.__openholidays

    @openholidays.setter
    def openholidays(self, subdivisionCode: str):
        """Set the OpenHolidays object by the subdivision code.
        """
        self.__openholidays = None
        self.__holidays = list()
        self.log.info(f"holidays = {subdivisionCode or False}")

        if subdivisionCode is None:
            return
        elif isinstance(subdivisionCode, str):
            self.__openholidays = OpenHolidays(
                countryIsoCode=subdivisionCode.split('-')[1],
                languageIsoCode=subdivisionCode.split('-')[0],
                subdivisionCode=subdivisionCode
            )
            self._request_holidays()
            schedule.every().day.at("00:00").do(self._request_holidays)
        else:
            raise TypeError("holidays subdivisionCode should be of type str!")

    @property
    def holidays(self):
        """Get the list with holidays.
        """
        return self.__holidays

    def _request_holidays(self, days: int = None, **kwargs):
        """Internal function to request school and public holidays using the
        OpenHolidays API.
        """
        if not hasattr(self, '__holidays_last_update'):
            self.__holidays_last_update = None
        startDate = datetime.date.today()
        endDate = startDate + datetime.timedelta(days=days or 180)
        self.log.debug(f"request holidays from {startDate} until {endDate}")
        try:
            self.__holidays = self.openholidays.holidays(
                str(startDate), str(endDate),
                timeout=self.timeout,
                **kwargs
            )
            self.__holidays_last_update = startDate
            self.log.debug("holidays request completed.")
            return True
        except requests.exceptions.RequestException as e:
            self.log.debug(f"holidays request failed. Last update on "
                            "{self.__holidays_last_update}")
            self.log.error(e)
            return False

    def is_holiday(self):
        """Returns `True` if today is a school or public holiday.
        """

        if self.openholidays is None:
            return False

        today = datetime.date.today()
        self.log.debug(f"verify if {today} is a holiday")

        if not hasattr(self, '__ref_date'):
            # self.log.debug("  initiate holiday status cache attribute")
            self.__ref_date = None

        if self.__ref_date == today:
            # self.log.debug("  return holiday status from cache")
            return self.__is_holiday

        if not self.holidays:
            # self.log.debug("  no holiday list found -> request")
            if not self._request_holidays():
                return False

        # self.log.debug("  lookup in cached holiday list and store response")
        self.__is_holiday = is_holiday(today, self.holidays)
        self.__ref_date = today

        return self.__is_holiday

    @property
    def wav(self):
        """Get the wav dictionary.
        """
        return self.__wav

    @wav.setter
    def wav(self, value: dict):
        """Set the wav dictionary.
        """
        if not hasattr(self, '__wav'):
            self.__wav = dict()

        if not (isinstance(value, dict) and len(value) != 0):
            return

        self.log.info("wav =")
        for key, wav in value.items():
            self.log.info(f"  \"{key}\": \"{wav}\"")
            self.add_wav(key, wav)
        if not self.test:
            self.log.warning("wav audio files not not played to test "
                             "(run with option --test instead)")

    def add_wav(self, key: str, value: str):
        """Add a wav to the dictionary.
        """
        wav = os.path.expandvars(os.path.join(self.root, value))
        if not os.path.isfile(wav):
            err = f"File \"{wav}\" not found!"
            self.log.error(err)
            raise FileNotFoundError(err)
        if self.test:
            if not _play(wav, True, self.device, self.log):
                err = f"Could not play \"{wav}\"!"
                self.log.error(err)
                raise RuntimeError(err)
        try:
            self.__wav[str(key)] = str(value)
        except Exception as err:
            self.log.error(err)
            raise Exception(err)

    def get_wav(self, key: str, root: str = None):
        """Get a local wav given the key.
        """
        root = self.root if root is None else root
        try:
            wav = self.wav[str(key)]
        except KeyError:
            err = f"wav key \"{key}\" is not related to any sample!"
            self.log.error(err)
            raise KeyError(err)
        return os.path.expandvars(os.path.join(root, wav) if root else wav)

    def get_remote_wav(self, host: str, key: str):
        """Get a remote wav given the host and key.
        """
        try:
            root = self.__trigger[str(host)]
        except KeyError:
            err = f"host \"{host}\" is not related to remote trigger!"
            self.log.error(err)
            raise KeyError(err)
        try:
            wav = self.wav[str(key)]
        except KeyError:
            err = f"wav key \"{key}\" is not related to any sample!"
            self.log.error(err)
            raise KeyError(err)
        return os.path.expandvars(os.path.join(root, wav))

    @property
    def trigger(self):
        """Get the remote linux devices to trigger over ssh.
        """
        return self.__trigger

    @trigger.setter
    def trigger(self, value: list = None):
        """Set the remote linux devices to trigger over ssh.
        """
        if not hasattr(self, '__trigger'):
            self.__trigger = dict()

        if not (isinstance(value, list) and len(value) != 0):
            return

        self.log.info("trigger =")

        for host, root in value:
            self.log.info(f"  remote ring {host}")
            self.add_trigger(host, root)

    def add_trigger(self, host: str, root: str = None):
        """Add a remote linux device to trigger over ssh.
        """
        root = root or ''
        cmd = self._ssh(host) + ["/usr/bin/aplay", "--help"]
        if not system_call(cmd, self.log):
            err = f"remote ring test for {host} failed!"
            self.log.error(err)
            raise RuntimeError(err)
        try:
            self.__trigger[str(host)] = str(root)
        except Exception as err:
            self.log.error(err)
            raise Exception(err)

    def play(self, key: str, test: bool = False, device: str = None):
        """Play a wav given the key.
        """
        wav = self.get_wav(key)
        self.log.info(f"play wav = \"{key}\": \"{os.path.basename(wav)}\"")

        success = _play(
            wav=wav,
            test=test,
            device=device or self.device,
            logger=self.log
        )
        if not success:
            err = f"Could not play wav {wav}!"
            self.log.error(err)
            raise RuntimeError(err)
        self.log.info("Play completed successfully.")

    def play_remote(self, host: str, key: str, test: bool = False,
                    timeout: int = None):
        """Play a remote wav given the host and key.
        """
        wav = self.get_remote_wav(host, key)
        self.log.info(f"play remote wav \"{key}\": \"{os.path.basename(wav)}\"")

        success = _play_remote(
            host=host,
            wav=wav,
            test=test,
            timeout=timeout or self.timeout,
            logger=self.log
        )

        if not success:
            err = f"Could not play remote wav \"{wav}\"!"
            self.log.error(err)
            raise RuntimeError(err)
        self.log.info("Play remote completed successfully.")

    def ring(self, key: str, **kwargs):
        """Ring the school bell
        """

        if self.is_holiday():
            self.log.info("today is a holiday, no need to ring!")
            return

        wav = self.get_wav(key)

        self.log.info(f"ring \"{key}\": \"{os.path.basename(wav)}\"")

        threads = []
        for host, root in self.trigger.items():
            remote_wav = self.get_wav(key, root)
            threads.append(
                Thread(
                    target=_play_remote,
                    args=(host, remote_wav, False, self.timeout, self.log)
                )
            )
        threads.append(
            Thread(
                target=_play,
                args=(wav, False, self.device, self.log)
            )
        )

        if self.buzzer:
            self.log.debug(".. buzzer on")
            self.buzzer.on()

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        if self.buzzer:
            self.log.debug(".. buzzer off")
            self.buzzer.off()

        self.log.debug(".. done")

    def create_schedule(self, value: dict = None, **kwargs):
        """Create a schedule
        """
        if not (isinstance(value, dict) and len(value) != 0):
            return

        self.log.info("schedule =")
        for day, times in value.items():
            day = day.capitalize()

            if not _validate_day(day, **kwargs):
                continue

            day_num = list(calendar.day_abbr).index(day)
            day_name = calendar.day_name[day_num].lower()

            for time, key in times.items():

                if not _validate_time(time, **kwargs):
                    continue

                self.log.info(f"  ring every {day} at {time} with \"{key}\"")

                wav = self.get_wav(key)

                if not os.path.isfile(wav):
                    err = f"File '{wav}' not found!"
                    self.log.error(err)
                    raise FileNotFoundError(err)

                eval(
                    "schedule.every().{}.at(\"{}\").do(self.ring, key)"
                    .format(day_name, time)
                )

    def run_schedule(self):
        """
        """
        self.log.info('Start schedule.')
        while True:
            schedule.run_pending()
            sleep(.2)


def _ssh(self, host: str, timeout: int = 10):
    """Internal function wrapping the ssh command.
    """
    return ["/usr/bin/ssh",
            "-t",
            "-o", f"ConnectTimeout={timeout}",
            "-o", "StrictHostKeyChecking=no",
            host]


def _play_remote(host: str, wav: str, test: bool = False, timeout: int = None,
                 logger: Logger = None):
    """Internal function to play a remove wav file over ssh. Returns `True` on
    success.
    """
    cmd = _ssh(host, timeout) + __play_test if test else __play + [wav, "&"]

    return system_call(cmd, logger)


def _play(wav: str, test: bool = False, device: str = None,
          logger: Logger = None):
    """Internal function to play a wav file. Returns `True` on success.
    """
    cmd = __play_test if test else __play

    if __alsa and device:
        cmd = cmd + ['-D', device, wav]
    else:
        cmd = cmd + [wav]

    return system_call(cmd, logger)


def _validate_day(day: str, raise_on_error: bool = False):
    """Validate the input day abbrev string. Returns `True` on success.
    """
    days = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')

    if day in days:
        return True

    err = (f"Day abbrivation \"{day}\" is invalid! "
           "Please provide any of \"{days.join{'|'}}\".")

    if raise_on_error:
        raise ValueError(err)

    return False


def _validate_time(time: str, raise_on_error: bool = False):
    """Validate the input time string. Returns `True` on success.
    """
    pattern = ("^(([0-1]{0,1}[0-9])|(2[0-3]))"
               "(:[0-5]{0,1}[0-9])"
               "(:[0-5]{0,1}[0-9]){0,1}$")

    if re.match(pattern, time):
        return True

    err = f"Time \"{time}\" is invalid! Please use the format \"HH:MM[:SS]\""

    if raise_on_error:
        raise ValueError(err)

    return False
