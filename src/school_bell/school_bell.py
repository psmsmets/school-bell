#!/usr/bin/python3

# absolute imports
import calendar
import copy
import datetime
import os
import re
import requests
import schedule
import socket
import sys
from gpiozero import Buzzer
from logging import Logger
from threading import RLock, Thread
from time import monotonic, sleep
from typing import List, Union

# Relative imports
from .openholidays import OpenHolidays, is_holiday
from .monitoring import (
    StatusServer,
    configure_remote_syslog,
    get_systemd_status,
    log_event,
)
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
        buzz_gpio: Union[int, List[int]] = None,
        buzz_active_high: bool = True,
        timeout: int = None,
        holidays: str = None,
        trigger: dict = None,
        debug: bool = None,
        prog: str = None,
        info: str = None,
        monitoring: dict = None,
    ):
        """Initialize the SchoolBell object
        """

        # Preamble
        prog = prog or 'school-bell'
        info = info or 'Python-scheduled ringing of a school bell.'
        if monitoring is not None and not isinstance(monitoring, dict):
            raise TypeError('monitoring should be a dictionary!')

        self.__started_at = datetime.datetime.now(datetime.timezone.utc)
        self.__hostname = socket.gethostname()
        self.__state_lock = RLock()
        self.__scheduler_running = False
        self.__last_ring = None
        self.__last_error = None
        self.__monitoring = monitoring or {}
        self.__device_id = self.__monitoring.get(
            'device_id', self.__hostname
        )
        if not isinstance(self.__device_id, str) or not self.__device_id:
            raise ValueError('monitoring.device_id should be a non-empty string!')
        self.__monitoring_labels = self.__monitoring.get('labels', {})
        if not isinstance(self.__monitoring_labels, dict):
            raise TypeError('monitoring.labels should be a dictionary!')
        if any(
            re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', str(key)) is None
            for key in self.__monitoring_labels
        ):
            raise ValueError(
                'monitoring label names should contain letters, numbers and '
                'underscores, and start with a letter!'
            )
        self.__monitoring_server = None
        self.__remote_syslog_handler = None
        self.__schedule_config = copy.deepcopy(schedule or {})
        self.__logger = init_logger(prog, debug or False)
        try:
            self.__remote_syslog_handler = configure_remote_syslog(
                logger=self.__logger,
                config=self.__monitoring.get('syslog'),
                version=self.reported_version,
                hostname=self.__hostname,
                device_id=self.__device_id,
                labels=self.__monitoring_labels,
            )
        except (TypeError, ValueError) as err:
            self.__logger.error('Remote syslog disabled: %s', err)
        self.__alsa = sys.platform != "darwin"
        self.log.info(info)
        self.log.info(f"version = {version}")

        # Init
        self.__holidays_last_update = None

        self.root = root or None
        self.test = test or False
        self.device = device or None
        if not isinstance(buzz_active_high, bool):
            raise TypeError('buzz_active_high should be a boolean!')
        self.__buzz_active_high = buzz_active_high
        self.buzzer = buzz_gpio
        self.timeout = timeout or 10
        self.openholidays = holidays or None
        self.trigger = trigger or dict()
        self.wav = wav or dict()

        # Create schedule
        self.create_schedule(schedule)
        self.__schedule_loaded = isinstance(schedule, dict)
        log_event(
            self.log,
            'schedule_loaded',
            scheduled_jobs=self.scheduled_jobs,
        )
        self._start_monitoring()
        self._configure_heartbeat()
        log_event(self.log, 'service_started')

    @property
    def reported_version(self) -> str:
        """Return a stable version value for monitoring clients."""
        if not version or version.startswith('VERSION-NOT-FOUND'):
            return 'unknown'
        return version

    @property
    def scheduled_jobs(self) -> int:
        """Return the number of configured bell jobs."""
        return sum(
            len(times) for times in self.__schedule_config.values()
            if isinstance(times, dict)
        )

    def _start_monitoring(self):
        config = self.__monitoring.get('status')
        if not config:
            return
        if not isinstance(config, dict):
            self.log.error(
                'HTTP monitoring disabled: monitoring.status should be a '
                'dictionary!'
            )
            return
        if not config.get('enabled', False):
            return

        host = config.get('host', '127.0.0.1')
        try:
            port = int(config.get('port', 8080))
            self.__monitoring_server = StatusServer(
                host=host,
                port=port,
                status_provider=self.monitoring_status,
                health_provider=self.monitoring_health,
                logger=self.log,
                token=config.get('token'),
            ).start()
            bound_host, bound_port = self.__monitoring_server.address[:2]
            self.log.info(
                'Monitoring status endpoint listening on %s:%s',
                bound_host, bound_port
            )
        except (OSError, TypeError, ValueError) as err:
            self.log.error(
                'Unable to start monitoring status endpoint on %s: %s',
                host, err
            )
            log_event(
                self.log,
                'health_status',
                status='failure',
                endpoint='http',
                error_category='monitoring_bind_error',
            )

    def _configure_heartbeat(self):
        if not self.__monitoring.get('syslog'):
            return
        try:
            heartbeat_interval = int(
                self.__monitoring.get('heartbeat_interval', 300)
            )
            if heartbeat_interval <= 0:
                raise ValueError
        except (TypeError, ValueError):
            self.log.error(
                'Invalid monitoring heartbeat interval; using 300 seconds.'
            )
            heartbeat_interval = 300
        schedule.every(heartbeat_interval).seconds.do(
            self._emit_health_status
        )

    def monitoring_status(self) -> dict:
        """Return current application state without exposing credentials."""
        with self.__state_lock:
            uptime = datetime.datetime.now(
                datetime.timezone.utc
            ) - self.__started_at
            payload = {
                'service': 'school-bell',
                'status': (
                    'running' if self.__scheduler_running else 'starting'
                ),
                'version': self.reported_version,
                'hostname': self.__hostname,
                'device_id': self.__device_id,
                'labels': copy.deepcopy(self.__monitoring_labels),
                'started_at': self.__started_at.isoformat(),
                'uptime_seconds': int(uptime.total_seconds()),
                'schedule_loaded': self.__schedule_loaded,
                'scheduled_jobs': self.scheduled_jobs,
                'schedule': copy.deepcopy(self.__schedule_config),
                'trigger_hosts': sorted(self.trigger.keys()),
                'gpio_pins': list(self.__buzzer_pins),
                'gpio_active_high': self.__buzz_active_high,
                'last_ring': copy.deepcopy(self.__last_ring),
                'last_error': copy.deepcopy(self.__last_error),
            }

        status_config = self.__monitoring.get('status', {})
        if status_config.get('include_systemd', True):
            payload['systemd'] = get_systemd_status()
        return payload

    def monitoring_health(self):
        """Return an HTTP health result and its JSON payload."""
        with self.__state_lock:
            healthy = self.__scheduler_running and self.__last_error is None
        return healthy, {'status': 'ok' if healthy else 'unhealthy'}

    @property
    def monitoring_address(self):
        """Return the bound monitoring address, primarily for diagnostics."""
        if self.__monitoring_server is None:
            return None
        return self.__monitoring_server.address

    def _emit_health_status(self):
        """Emit a heartbeat used to detect silent/offline devices."""
        healthy, _ = self.monitoring_health()
        log_event(
            self.log,
            'health_status',
            status='success' if healthy else 'failure',
            uptime_seconds=int((
                datetime.datetime.now(datetime.timezone.utc) -
                self.__started_at
            ).total_seconds()),
            scheduled_jobs=self.scheduled_jobs,
        )
        return healthy

    def close(self):
        """Stop monitoring resources cleanly."""
        for buzzer in getattr(self, '_SchoolBell__buzzer', []):
            buzzer.off()
        log_event(self.log, 'service_stopped')
        if self.__monitoring_server is not None:
            self.__monitoring_server.stop()
            self.__monitoring_server = None
        if self.__remote_syslog_handler is not None:
            self.log.removeHandler(self.__remote_syslog_handler)
            self.__remote_syslog_handler.close()
            self.__remote_syslog_handler = None

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
                self.__device = value
            except ValueError as err:
                self.log.error(err)

    @property
    def buzzer(self):
        """Get the buzzer object.
        """
        return self.__buzzer

    @property
    def buzz_active_high(self):
        """Return whether a logical on state drives the GPIO high."""
        return self.__buzz_active_high

    @buzzer.setter
    def buzzer(self, gpio_pins: Union[int, List[int]]):
        self.log.info(f"buzzer = {gpio_pins or False}")
        self.log.info(f"buzzer active high = {self.__buzz_active_high}")

        if gpio_pins is None:
            gpio_pins = []
        elif isinstance(gpio_pins, int) and not isinstance(gpio_pins, bool):
            gpio_pins = [gpio_pins]
        elif not (
            isinstance(gpio_pins, list) and
            all(isinstance(pin, int) and not isinstance(pin, bool)
                for pin in gpio_pins)
        ):
            raise TypeError(
                "buzz_gpio should be an integer or a list of integers!"
            )

        self.__buzzer = []
        self.__buzzer_pins = gpio_pins
        if not gpio_pins:
            return

        if is_raspberry_pi():
            try:
                self.__buzzer = [
                    Buzzer(
                        pin,
                        active_high=self.__buzz_active_high,
                        initial_value=False,
                    )
                    for pin in gpio_pins
                ]
                for buzzer in self.__buzzer:
                    self.log.debug(f"  {buzzer}")
                if self.test:
                    self.test_buzzers()
            except Exception as err:
                self.log.error(err)
                raise
        else:
            self.log.warning("Host is not a Raspberry Pi: buzzer disabled!")

    def test_buzzers(self, duration: float = 1.0) -> bool:
        """Test each configured GPIO output sequentially.

        All outputs are returned to their inactive state, including when the
        test is interrupted.
        """
        if not self.buzzer:
            self.log.info("No GPIO pins configured: GPIO test skipped.")
            return True

        self.log.info("Testing configured GPIO pins...")
        total = len(self.buzzer)

        try:
            for index, (pin, buzzer) in enumerate(
                zip(self.__buzzer_pins, self.buzzer), start=1
            ):
                self.log.info(f"Testing GPIO {pin} ({index}/{total})")
                try:
                    self._set_gpio_state(True, [pin], [buzzer])
                    sleep(duration)
                finally:
                    self._set_gpio_state(False, [pin], [buzzer])
        finally:
            for buzzer in self.buzzer:
                buzzer.off()

        self.log.info("GPIO test completed.")
        log_event(
            self.log,
            'gpio_test',
            gpio_pins=list(self.__buzzer_pins),
            gpio_active_high=self.__buzz_active_high,
        )
        return True

    def _set_gpio_state(
        self,
        active: bool,
        pins: list = None,
        buzzers: list = None,
    ) -> None:
        """Switch GPIO outputs and emit a structured state event."""
        pins = list(self.__buzzer_pins if pins is None else pins)
        buzzers = list(self.buzzer if buzzers is None else buzzers)
        event = 'gpio_activated' if active else 'gpio_deactivated'
        state = 'active' if active else 'inactive'
        operation = 'on' if active else 'off'

        error = None
        for buzzer in buzzers:
            try:
                getattr(buzzer, operation)()
            except Exception as err:
                error = error or err
                if active:
                    break

        if error is not None:
            log_event(
                self.log,
                event,
                status='failure',
                level=40,
                gpio_pins=pins,
                gpio_active_high=self.__buzz_active_high,
                gpio_state='unknown',
                error_category=(
                    'gpio_activation_error' if active
                    else 'gpio_deactivation_error'
                ),
            )
            raise error

        log_event(
            self.log,
            event,
            gpio_pins=pins,
            gpio_active_high=self.__buzz_active_high,
            gpio_state=state,
        )

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
    def test(self) -> bool:
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
    def timeout(self) -> int:
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
    def openholidays(self, groupCode: str):
        """Set the OpenHolidays object by the holiday group code.
        """
        self.__openholidays = None
        self.__holidays = list()
        self.__holidays_last_update = None
        self.__ref_date = None
        self.log.info(f"holidays = {groupCode or False}")

        if groupCode is None:
            return
        elif isinstance(groupCode, str):
            self.__openholidays = OpenHolidays(
                countryIsoCode=groupCode.split('-')[0],
                languageIsoCode=groupCode.split('-')[1],
                groupCode=groupCode
            )
            self._request_holidays()
            schedule.every().day.at("00:00").do(self._request_holidays)
        else:
            raise TypeError("holidays groupCode should be of type str!")

    @property
    def holidays(self) -> list:
        """Get the list with holidays.
        """
        return self.__holidays

    def _request_holidays(self, days: int = None, **kwargs) -> bool:
        """Internal function to request school and public holidays using the
        OpenHolidays API.
        """
        if not self.openholidays:
            return

        startDate = datetime.date.today()
        endDate = startDate + datetime.timedelta(days=days or 180)

        self.log.info(f"request holidays from {startDate} until {endDate}")
        try:
            self.__holidays = self.openholidays.holidays(
                str(startDate), str(endDate),
                timeout=self.timeout,
                **kwargs
            )
            self.__holidays_last_update = startDate
            self.log.debug("holidays request completed.")
            return True
        except requests.exceptions.RequestException as err:
            self.log.warning("holidays request failed. Last update on {}"
                             .format(self.__holidays_last_update))
            self.log.debug(err)
            return False

    def is_holiday(self, date: datetime.date = None) -> bool:
        """Returns `True` if `date` is a school or public holiday.
        """

        if self.openholidays is None:
            return

        date = date or datetime.date.today()
        self.log.debug(f"verify if {date} is a holiday")

        if self.__ref_date == date:
            self.log.debug("  return holiday status from cache")
            return self.__is_holiday

        if not self.holidays:
            self.log.debug("  no holiday list found -> request")
            if not self._request_holidays():
                return False

        self.log.debug("  lookup holiday in cached list and store response")
        self.__is_holiday = is_holiday(date, self.holidays)
        self.__ref_date = date

        return self.__is_holiday

    @property
    def wav(self) -> dict:
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
            self.log.info(f"  {key}: {wav}")
            self.add_wav(key, wav)
        if not self.test:
            self.log.warning("wav audio files not not actually played "
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

    def get_wav(self, key: str, root: str = None) -> str:
        """Get a local WAVE audio file given the key.
        """
        root = self.root if root is None else root
        try:
            wav = self.wav[str(key)]
        except KeyError:
            err = f"WAVE key \"{key}\" is not related to any sample!"
            self.log.error(err)
            raise KeyError(err)
        return os.path.expandvars(os.path.join(root, wav) if root else wav)

    def get_remote_wav(self, host: str, key: str) -> str:
        """Get a remote WAVE audio file given the host and key.
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
            err = f"WAVE key \"{key}\" is not related to any sample!"
            self.log.error(err)
            raise KeyError(err)
        return os.path.expandvars(os.path.join(root, wav))

    @property
    def trigger(self) -> dict:
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

    def play(self, key: str, test: bool = False, device: str = None) -> bool:
        """Play a WAVE audio file given the key.
        Returns `True` on success.
        """
        wav = self.get_wav(key)
        self.log.info(f"play wav = {key}: {os.path.basename(wav)}")

        success = _play(
            wav=wav,
            test=test,
            device=device or self.device,
            logger=self.log
        )
        if not success:
            err = f"Could not play WAVE audio file {wav}!"
            self.log.error(err)
            log_event(
                self.log,
                'audio_error',
                status='failure',
                level=40,
                wav_key=str(key),
                error_category='audio_playback_error',
            )
            raise RuntimeError(err)
        self.log.info("Play completed successfully.")
        return True

    def play_remote(self, host: str, key: str, test: bool = False,
                    timeout: int = None):
        """Play a remote WAVE audio file given the host and key.
        Returns `True` on success.
        """
        wav = self.get_remote_wav(host, key)
        self.log.info(f"play remote wav {key}: {os.path.basename(wav)}")

        success = self._play_remote_monitored(
            host=host,
            key=key,
            wav=wav,
            test=test,
            timeout=timeout or self.timeout,
        )

        if not success:
            err = f"Could not play remote WAVE audio file \"{wav}\"!"
            self.log.error(err)
            raise RuntimeError(err)
        self.log.info("Play remote completed successfully.")
        return True

    def _play_remote_monitored(
        self,
        host: str,
        key: str,
        wav: str,
        test: bool = False,
        timeout: int = None,
    ) -> bool:
        """Play remotely and report one structured result event."""
        started = monotonic()
        fields = {
            'remote_host': str(host),
            'wav_key': str(key),
        }
        try:
            success = _play_remote(
                host=host,
                wav=wav,
                test=test,
                timeout=timeout or self.timeout,
                logger=self.log,
            )
        except Exception:
            fields['duration_seconds'] = round(monotonic() - started, 3)
            log_event(
                self.log,
                'remote_trigger',
                status='failure',
                level=40,
                error_category='remote_trigger_error',
                **fields,
            )
            raise

        fields['duration_seconds'] = round(monotonic() - started, 3)
        if success:
            log_event(self.log, 'remote_trigger', **fields)
        else:
            log_event(
                self.log,
                'remote_trigger',
                status='failure',
                level=40,
                error_category='remote_trigger_error',
                **fields,
            )
        return success

    def ring(self, key: str, **kwargs) -> bool:
        """Ring the school bell.
        Returns `True` on success.
        """

        if self.is_holiday():
            self.log.info("today is a holiday, no need to ring!")
            with self.__state_lock:
                self.__last_ring = {
                    'time': datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    'key': str(key),
                    'status': 'skipped',
                    'skip_reason': 'holiday',
                }
            log_event(
                self.log,
                'bell_skipped_holiday',
                status='skipped',
                wav_key=str(key),
                skip_reason='holiday',
            )
            return False

        wav = self.get_wav(key)

        self.log.info(f"ring {key}: {os.path.basename(wav)}")

        operations = []
        for host, root in self.trigger.items():
            remote_wav = self.get_wav(key, root)
            operations.append(
                (self._play_remote_monitored,
                 (host, str(key), remote_wav, False, self.timeout))
            )
        operations.append(
            (_play, (wav, False, self.device, self.log))
        )
        results = [False] * len(operations)
        threads = [
            Thread(
                target=_capture_result,
                args=(results, index, function, arguments)
            )
            for index, (function, arguments) in enumerate(operations)
        ]

        try:
            if self.buzzer:
                self.log.debug(".. buzzer on")
                self._set_gpio_state(True)

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            if not all(results):
                raise RuntimeError('One or more audio outputs failed!')
        except Exception as err:
            with self.__state_lock:
                self.__last_error = {
                    'time': datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    'category': 'bell_error',
                    'message': str(err),
                }
            log_event(
                self.log,
                'audio_error',
                status='failure',
                level=40,
                wav_key=str(key),
                error_category='audio_playback_error',
            )
            log_event(
                self.log,
                'bell_ring',
                status='failure',
                level=40,
                wav_key=str(key),
                gpio_pins=list(self.__buzzer_pins),
                gpio_active_high=self.__buzz_active_high,
                error_category='bell_error',
            )
            raise
        finally:
            if self.buzzer:
                self.log.debug(".. buzzer off")
                self._set_gpio_state(False)

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.__state_lock:
            self.__last_ring = {
                'time': now,
                'key': str(key),
                'status': 'success',
            }
            self.__last_error = None
        log_event(
            self.log,
            'bell_ring',
            wav_key=str(key),
            gpio_pins=list(self.__buzzer_pins),
            gpio_active_high=self.__buzz_active_high,
        )

        self.log.debug(".. done")
        return True

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

    def run_schedule(self, _test_mode: bool = False):
        """
        """
        with self.__state_lock:
            self.__scheduler_running = True
        self._emit_health_status()
        try:
            if _test_mode:
                self.log.info('Start schedule in test mode.')
                schedule.run_all(delay_seconds=10)
                return True
            else:
                self.log.info('Start schedule.')
                while True:
                    schedule.run_pending()
                    sleep(.2)
        finally:
            with self.__state_lock:
                self.__scheduler_running = False


def _ssh(self, host: str, timeout: int = 10):
    """Internal function wrapping the ssh command.
    """
    return ["/usr/bin/ssh",
            "-t",
            "-o", f"ConnectTimeout={timeout}",
            "-o", "StrictHostKeyChecking=no",
            host]


def _capture_result(results: list, index: int, function, arguments: tuple):
    """Capture a worker result without losing failures inside a thread."""
    try:
        results[index] = bool(function(*arguments))
    except Exception:
        results[index] = False


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
