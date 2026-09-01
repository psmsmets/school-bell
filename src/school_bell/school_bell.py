#!/usr/bin/python3

# absolute imports
import calendar
import copy
import datetime
import os
import re
import requests
import schedule as schedule_module
import pytz
import socket
import sys
from gpiozero import Buzzer
from logging import Logger
from threading import Event, Lock, RLock, Thread
from time import monotonic, sleep
from typing import List, Union

# Relative imports
from .openholidays import OpenHolidays, is_holiday
from .disable_calendar import DisableCalendar
from .identifiers import schedule_entry_id, short_hash, trigger_id
from .monitoring import (
    StatusServer,
    configure_remote_syslog,
    get_systemd_status,
    log_event,
)
from .manual_bell import ManualBellInput
from .playback import AudioPlayback, playback_command
from .utils import init_logger, is_raspberry_pi, system_call
try:
    from .version import version
except (ValueError, ModuleNotFoundError, SyntaxError):
    version = "VERSION-NOT-FOUND"


__all__ = ['SchoolBell']

# Retain the module attribute used by existing callers and tests.
schedule = schedule_module


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
        config_hash: str = None,
        schedule_hash: str = None,
        timezone: str = 'Europe/Brussels',
        disable_calendar: str = None,
        manual_bell: dict = None,
        check: bool = False,
    ):
        """Initialize the SchoolBell object
        """

        # Preamble
        prog = prog or 'school-bell'
        info = info or 'Python-scheduled ringing of a school bell.'
        if monitoring is not None and not isinstance(monitoring, dict):
            raise TypeError('monitoring should be a dictionary!')

        self.__check = bool(check)
        self.__started_at = datetime.datetime.now(datetime.timezone.utc)
        self.__hostname = socket.gethostname()
        self.__state_lock = RLock()
        self.__bell_lock = Lock()
        self.__active_bell = None
        self.__active_playback = None
        self.__manual_bell = None
        self.__scheduler_running = False
        self.__last_ring = None
        self.__last_error = None
        self.__monitoring = monitoring or {}
        self.__config_hash = config_hash
        self.__schedule_hash = schedule_hash
        try:
            self.__timezone = pytz.timezone(timezone)
        except (pytz.UnknownTimeZoneError, AttributeError):
            raise ValueError(f'Unknown timezone: {timezone}')
        self.__timezone_name = timezone
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
        if self.__check:
            # Check mode prints its own stable, concise result lines.
            self.__logger.disabled = True
        try:
            if not self.__check:
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
        self._configure_disable_calendar(disable_calendar)
        self.trigger = {} if trigger is None else trigger
        self.wav = wav or dict()

        self._configure_manual_bell(manual_bell)

        # Create schedule
        self.create_schedule(schedule)
        self.__schedule_loaded = isinstance(schedule, dict)
        log_event(
            self.log,
            'schedule_loaded',
            scheduled_jobs=self.scheduled_jobs,
            **self._revision_fields(),
        )
        if not self.__check:
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

    def _revision_fields(self) -> dict:
        """Return configured revision identifiers when available."""
        fields = {
            key: value for key, value in {
                'config_hash': self.__config_hash,
                'schedule_hash': self.__schedule_hash,
            }.items() if value is not None
        }
        if self.__config_hash is not None:
            fields['config_hash_short'] = short_hash(self.__config_hash)
        if self.__schedule_hash is not None:
            fields['schedule_hash_short'] = short_hash(self.__schedule_hash)
        return fields

    def _execution_fields(self, context: dict = None) -> dict:
        """Create stable fields for one scheduled execution."""
        fields = self._revision_fields()
        if not context:
            return fields

        now = datetime.datetime.now(self.__timezone)
        hour, minute, second = map(int, context['local_time'].split(':'))
        weekday_number = list(calendar.day_name).index(context['weekday'])
        planned_date = now.date() - datetime.timedelta(
            days=(now.weekday() - weekday_number) % 7
        )
        planned = self.__timezone.localize(
            datetime.datetime.combine(
                planned_date, datetime.time(hour, minute, second)
            )
        )
        planned_at = planned.isoformat()
        fields.update({
            'schedule_entry_id': context['schedule_entry_id'],
            'planned_at': planned_at,
            'local_date': planned.date().isoformat(),
            'weekday': context['weekday'],
            'timezone': self.__timezone_name,
        })
        if self.__schedule_hash is not None:
            fields['trigger_id'] = trigger_id(
                self.__device_id,
                self.__schedule_hash,
                context['schedule_entry_id'],
                planned_at,
            )
        return fields

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
                'active_bell': copy.deepcopy(self.__active_bell),
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
        if self.__manual_bell is not None:
            self.__manual_bell.close()
            self.__manual_bell = None
        playback = self.__active_playback
        if playback is not None:
            playback.stop()
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

    def _configure_manual_bell(self, config: dict = None):
        """Configure the optional single physical trigger button."""
        if config is None:
            return
        validated = ManualBellInput.validate(config, self.__buzzer_pins)
        if validated['wav_key'] not in self.wav:
            raise KeyError(
                'manual_bell.wav_key is not related to any sample!'
            )
        if self.__check:
            return
        if not is_raspberry_pi():
            self.log.warning(
                'Host is not a Raspberry Pi: manual bell button disabled!'
            )
            return
        self.__manual_bell = ManualBellInput(
            validated,
            trigger=self.trigger_bell,
            logger=self.log,
            output_pins=self.__buzzer_pins,
        )
        self.log.info(
            'manual bell = GPIO %s (%s)',
            validated['gpio'], validated['mode']
        )

    def _configure_disable_calendar(self, url: str = None):
        """Configure startup and daily refresh of a public calendar."""
        self.__disable_calendar = None
        if not url:
            return
        self.log.info('Public calendar configured.')
        self.__disable_calendar = DisableCalendar(
            url,
            timezone=self.__timezone_name,
            timeout=self.timeout,
            logger=self.log,
        )
        if self.__check:
            return
        self.__disable_calendar.refresh()
        schedule_module.every().day.at(
            '00:05', self.__timezone_name
        ).do(self.__disable_calendar.refresh)

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
        if self.__check:
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
            if self.__check:
                return
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
        except (requests.exceptions.RequestException, ValueError):
            self.log.warning(
                "holidays unavailable; local bell scheduling remains active. "
                "Last update on %s",
                self.__holidays_last_update,
            )
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
    def trigger(self, value: dict = None):
        """Set the remote linux devices to trigger over ssh.
        """
        if not hasattr(self, '__trigger'):
            self.__trigger = dict()

        if value is None:
            return
        if not isinstance(value, dict):
            raise TypeError('trigger should be a dictionary!')

        invalid = [
            (host, root) for host, root in value.items()
            if not isinstance(host, str) or not host.strip()
            or not isinstance(root, str)
        ]
        if invalid:
            raise ValueError(
                'trigger should map non-empty host strings to root strings!'
            )
        if not value:
            return

        self.log.info("trigger =")

        for host, root in value.items():
            self.log.info(f"  remote ring {host}")
            if self.__check:
                self.__trigger[str(host)] = str(root)
            else:
                self.add_trigger(host, root)

    def add_trigger(self, host: str, root: str = None):
        """Add a remote linux device to trigger over ssh.
        """
        root = root or ''
        cmd = _ssh(host, self.timeout) + ["/usr/bin/aplay", "--help"]
        if not system_call(cmd, self.log, timeout=self.timeout):
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
        if not test and device is None:
            return self.trigger_bell(
                key,
                source='manual',
                respect_calendar=False,
                include_remote=False,
            )

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
        fields = {
            'trigger_source': 'remote',
            'remote_host': str(host),
            'wav_key': str(key),
        }
        if not self.__bell_lock.acquire(blocking=False):
            with self.__state_lock:
                active = copy.deepcopy(self.__active_bell)
            log_event(
                self.log, 'bell_trigger_ignored', status='skipped',
                reason='bell_active',
                active_trigger_source=(active or {}).get('source'),
                **fields,
            )
            return False
        with self.__state_lock:
            self.__active_bell = {
                'source': 'remote', 'wav_key': str(key),
                'remote_host': str(host),
                'started_at': datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            }
        try:
            wav = self.get_remote_wav(host, key)
            self.log.info(
                'play remote wav %s: %s', key, os.path.basename(wav)
            )
            success = self._play_remote_monitored(
                host=host, key=key, wav=wav, test=test,
                timeout=timeout or self.timeout,
            )
            if not success:
                raise RuntimeError(
                    f'Could not play remote WAVE audio file "{wav}"!'
                )
            self.log.info('Play remote completed successfully.')
            return True
        finally:
            with self.__state_lock:
                self.__active_bell = None
            self.__bell_lock.release()

    def _play_remote_monitored(
        self,
        host: str,
        key: str,
        wav: str,
        test: bool = False,
        timeout: int = None,
        event_fields: dict = None,
    ) -> bool:
        """Play remotely and report one structured result event."""
        started = monotonic()
        fields = {
            'remote_host': str(host),
            'wav_key': str(key),
            **(event_fields or {}),
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
        """Ring from the schedule while preserving the public API."""
        event_fields = self._execution_fields(
            kwargs.pop('_schedule_context', None)
        )
        return self.trigger_bell(
            key, source='scheduled', event_fields=event_fields, **kwargs
        )

    def trigger_bell(
        self, key: str, source: str, mode: str = 'once',
        cancel_event: Event = None, respect_calendar: bool = True,
        include_remote: bool = True, event_fields: dict = None,
        source_gpio: int = None,
    ) -> bool:
        """Run one exclusive bell signal from any current or future source."""
        key = str(key)
        event_fields = dict(event_fields or {})
        source_fields = {
            'trigger_source': source, 'wav_key': key, 'mode': mode,
            **event_fields,
        }
        if source_gpio is not None:
            source_fields['source_gpio'] = source_gpio
        if source == 'manual_gpio':
            log_event(self.log, 'manual_bell_triggered', **source_fields)
        if mode not in ('once', 'hold'):
            raise ValueError('Bell mode should be once or hold!')
        if not self.__bell_lock.acquire(blocking=False):
            with self.__state_lock:
                active = copy.deepcopy(self.__active_bell)
            log_event(
                self.log, 'bell_trigger_ignored', status='skipped',
                reason='bell_active',
                active_trigger_source=(active or {}).get('source'),
                **source_fields,
            )
            return False

        started = monotonic()
        with self.__state_lock:
            self.__active_bell = {
                'source': source, 'wav_key': key, 'mode': mode,
                'started_at': datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            }
        try:
            if respect_calendar and self._skip_disabled_bell(
                key, event_fields
            ):
                return False
            cancelled = self._execute_bell(
                key, mode, cancel_event, include_remote, event_fields
            )
            if source == 'manual_gpio':
                log_event(
                    self.log,
                    ('manual_bell_cancelled' if cancelled
                     else 'manual_bell_completed'),
                    status='cancelled' if cancelled else 'success',
                    duration_seconds=round(monotonic() - started, 3),
                    reason='button_released' if cancelled else None,
                    **source_fields,
                )
            return True
        except Exception as err:
            if source == 'manual_gpio':
                log_event(
                    self.log, 'manual_bell_failed', status='failure',
                    level=40,
                    duration_seconds=round(monotonic() - started, 3),
                    error_category='manual_bell_error', error=str(err),
                    **source_fields,
                )
            raise
        finally:
            with self.__state_lock:
                self.__active_bell = None
            self.__bell_lock.release()

    def _execute_bell(
        self, key: str, mode: str, cancel_event: Event,
        include_remote: bool, event_fields: dict,
    ) -> bool:
        """Execute an accepted bell request and return its cancel state."""
        wav = self.get_wav(key)
        self.log.info('ring %s: %s', key, os.path.basename(wav))
        operations = []
        if include_remote:
            for host, root in self.trigger.items():
                operations.append((
                    self._play_remote_monitored,
                    (host, key, self.get_wav(key, root), False,
                     self.timeout, event_fields),
                ))
        results = [False] * len(operations)
        threads = [
            Thread(target=_capture_result,
                   args=(results, index, function, arguments))
            for index, (function, arguments) in enumerate(operations)
        ]
        cancelled = False
        try:
            if self.buzzer:
                self._set_gpio_state(True)
            for thread in threads:
                thread.start()
            if mode == 'hold':
                playback = _start_playback(wav, self.device, self.log)
                self.__active_playback = playback
                local_success, cancelled = playback.wait(cancel_event)
            else:
                local_success = _play(wav, False, self.device, self.log)
            for thread in threads:
                thread.join()
            if not local_success or not all(results):
                raise RuntimeError('One or more audio outputs failed!')
        except Exception as err:
            with self.__state_lock:
                self.__last_error = {
                    'time': datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    'category': 'bell_error', 'message': str(err),
                }
            log_event(
                self.log, 'audio_error', status='failure', level=40,
                wav_key=key, error_category='audio_playback_error',
                **event_fields,
            )
            log_event(
                self.log, 'bell_ring', status='failure', level=40,
                wav_key=key, gpio_pins=list(self.__buzzer_pins),
                gpio_active_high=self.__buzz_active_high,
                error_category='bell_error', **event_fields,
            )
            raise
        finally:
            self.__active_playback = None
            if self.buzzer:
                self._set_gpio_state(False)
        with self.__state_lock:
            self.__last_ring = {
                'time': datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
                'key': key,
                'status': 'cancelled' if cancelled else 'success',
            }
            self.__last_error = None
        log_event(
            self.log, 'bell_ring',
            status='cancelled' if cancelled else 'success', wav_key=key,
            gpio_pins=list(self.__buzzer_pins),
            gpio_active_high=self.__buzz_active_high, **event_fields,
        )
        return cancelled

    def _skip_disabled_bell(self, key: str, event_fields: dict) -> bool:
        """Record a holiday or public-calendar skip when applicable."""
        if self.is_holiday():
            self.log.info("today is a holiday, no need to ring!")
            self._record_bell_skip(key, 'holiday')
            log_event(
                self.log,
                'bell_skipped_holiday',
                status='skipped',
                wav_key=key,
                skip_reason='holiday',
                **event_fields,
            )
            return True

        calendar_event = None
        if self.__disable_calendar is not None:
            calendar_event = self.__disable_calendar.blocking_event()
        if calendar_event is None:
            return False

        summary = calendar_event['summary']
        local_now = datetime.datetime.now(self.__timezone)
        if calendar_event['all_day']:
            self.log.info(
                'Bell disabled for %s by public calendar event: %s',
                local_now.date().isoformat(), summary
            )
        else:
            self.log.info(
                'Bell disabled at %s by public calendar event: %s',
                local_now.isoformat(), summary
            )
        self._record_bell_skip(
            key,
            'public_calendar',
            calendar_event_summary=summary,
        )
        log_event(
            self.log,
            'bell_skipped_calendar',
            status='skipped',
            wav_key=key,
            skip_reason='public_calendar',
            calendar_event_summary=summary,
            calendar_event_all_day=calendar_event['all_day'],
            **event_fields,
        )
        return True

    def _record_bell_skip(self, key: str, reason: str, **fields):
        """Store the common monitoring state for a skipped bell."""
        with self.__state_lock:
            self.__last_ring = {
                'time': datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
                'key': key,
                'status': 'skipped',
                'skip_reason': reason,
                **fields,
            }

    def create_schedule(self, value: dict = None, **kwargs):
        """Create a schedule
        """
        if not (isinstance(value, dict) and len(value) != 0):
            return

        # Validate the complete configuration before registering any jobs. This
        # keeps schedule loading atomic when a later entry is invalid.
        validated_entries = []
        for configured_day, times in value.items():
            if not isinstance(configured_day, str):
                raise ValueError(
                    f'Invalid weekday at schedule[{configured_day!r}]: '
                    f'{configured_day!r}'
                )

            day = configured_day.capitalize()
            if not _validate_day(day):
                raise ValueError(
                    f'Invalid weekday at schedule[{configured_day!r}]: '
                    f'{configured_day!r}. Expected one of Mon, Tue, Wed, Thu, '
                    'Fri, Sat, Sun.'
                )

            day_num = list(calendar.day_abbr).index(day)
            for configured_time, key in times.items():
                if (
                    not isinstance(configured_time, str)
                    or not _validate_time(configured_time)
                ):
                    raise ValueError(
                        f'Invalid time at '
                        f'schedule[{configured_day!r}]'
                        f'[{configured_time!r}]: {configured_time!r}. '
                        'Expected HH:MM[:SS].'
                    )
                validated_entries.append(
                    (day, day_num, configured_time, key)
                )

        self.log.info("schedule =")
        for day, day_num, time, key in validated_entries:
            day_name = calendar.day_name[day_num].lower()

            time_parts = [int(part) for part in time.split(':')]
            if len(time_parts) == 2:
                time_parts.append(0)
            canonical_time = datetime.time(*time_parts).isoformat()
            canonical_weekday = calendar.day_name[day_num]
            entry_id = schedule_entry_id(
                canonical_weekday, canonical_time, str(key)
            )
            context = {
                'schedule_entry_id': entry_id,
                'weekday': canonical_weekday,
                'local_time': canonical_time,
            }

            self.log.info(f"  ring every {day} at {time} with \"{key}\"")

            wav = self.get_wav(key)

            if not os.path.isfile(wav):
                err = f"File '{wav}' not found!"
                self.log.error(err)
                raise FileNotFoundError(err)

            if self.__check:
                continue

            getattr(schedule.every(), day_name).at(
                canonical_time, self.__timezone_name
            ).do(
                self.ring,
                str(key),
                _schedule_context=context,
            )
            log_event(
                self.log,
                'schedule_entry_loaded',
                schedule_entry_id=entry_id,
                weekday=canonical_weekday,
                local_time=canonical_time,
                wav_key=str(key),
                **self._revision_fields(),
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
    remote_command = __play_test if test else __play + [wav, "&"]
    cmd = _ssh(host, timeout) + remote_command

    return system_call(cmd, logger, timeout=timeout)


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


def _start_playback(wav: str, device: str = None, logger: Logger = None):
    """Start controllable local playback used by hold-mode triggers."""
    command = playback_command(
        wav=wav,
        player=__play,
        test_player=__play_test,
        alsa=__alsa,
        device=device,
    )
    return AudioPlayback(command, logger).start()


def _validate_day(day: str, raise_on_error: bool = False):
    """Validate the input day abbrev string. Returns `True` on success.
    """
    days = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')

    if day in days:
        return True

    err = (
        f'Day abbreviation "{day}" is invalid! '
        f'Please provide any of "{"|".join(days)}".'
    )

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
