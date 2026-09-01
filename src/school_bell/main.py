#!/usr/bin/python3

# absolute imports
import argparse
import datetime
import json
import pkgutil
import os
import re
import socket
import sys

# Relative imports
try:
    from .version import version
except (ValueError, ModuleNotFoundError, SyntaxError):
    version = "VERSION-NOT-FOUND"
from .utils import init_logger, system_call
from .school_bell import SchoolBell
from .identifiers import content_hash
from .monitoring import configure_remote_syslog
from .disable_calendar import DisableCalendar
from .openholidays import OpenHolidays

# Set path of demo files
share = os.path.join(sys.exec_prefix, 'share', 'school-bell')
if not os.path.exists(share):
    share = os.path.join(
        os.path.dirname(pkgutil.get_loader("school_bell").get_filename()),
        '../..'
    )


class DemoService(argparse.Action):
    """Argparse action to print a demo systemctl service
    """
    def __call__(self, parser, namespace, values, option_string=None):
        demo = os.path.join(share, 'demo.service')
        with open(demo, "r") as demo_service:
            service = demo_service.read()
            print(service.format(
                BIN=os.path.join(sys.exec_prefix, 'bin', 'school-bell'),
                CONFIG=os.path.expandvars(
                    os.path.join('$HOME', 'school-bell.json')
                ),
                HOME=os.path.expandvars('$HOME'),
                GROUP=os.getlogin(),
                USER=os.getlogin(),
            ))
        sys.exit()


class DemoConfig(argparse.Action):
    """Argparse action to print a demo JSON configuration
    """
    def __call__(self, parser, namespace, values, option_string=None):
        demo = os.path.join(share, 'demo.json')
        with open(demo, "r") as demo_config:
            print(json.dumps(json.load(demo_config), indent=4))
        sys.exit()


class SelfUpdate(argparse.Action):
    """Argparse action to self-update the school-bell code from git.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        branch = values or 'main'
        log = init_logger(debug=True)
        system_call([
            'pip',
            'install',
            f"git+https://github.com/psmsmets/school-bell.git@{branch}"
        ], log)
        log.info('school-bell updated.')
        sys.exit()


_SENSITIVE_KEY = re.compile(
    r'(?:password|passwd|secret|token|api[_-]?key|credential|auth)', re.I
)


def _sensitive_values(config):
    """Return configured secret values used only for error redaction."""
    values = set()

    def visit(value, sensitive=False):
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, sensitive or bool(_SENSITIVE_KEY.search(str(key))))
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child, sensitive)
        elif sensitive and value not in (None, ''):
            values.add(str(value))

    visit(config)
    if isinstance(config, dict) and config.get('disable_calendar'):
        # Published calendar URLs commonly embed bearer-like credentials.
        values.add(str(config['disable_calendar']))
    return values


def _safe_startup_message(error, config=None):
    """Create a bounded error description with configured secrets removed."""
    message = str(error).replace('\r', ' ').replace('\n', ' ').strip()
    for secret in sorted(_sensitive_values(config), key=len, reverse=True):
        message = message.replace(secret, '[REDACTED]')
    message = re.sub(
        r'(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+',
        r'\1=[REDACTED]',
        message,
    )
    return (message or 'No error details available')[:500]


def _configure_startup_monitoring(logger, config):
    """Best-effort remote logging setup from a parsed configuration."""
    if not isinstance(config, dict):
        return None
    monitoring = config.get('monitoring')
    if not isinstance(monitoring, dict):
        return None
    device_id = monitoring.get('device_id')
    if not isinstance(device_id, str) or not device_id:
        device_id = socket.gethostname()
    labels = monitoring.get('labels')
    if not isinstance(labels, dict):
        labels = None
    return configure_remote_syslog(
        logger=logger,
        config=monitoring.get('syslog'),
        version=(
            'unknown' if not version or version.startswith('VERSION-NOT-FOUND')
            else version
        ),
        hostname=socket.gethostname(),
        device_id=device_id,
        labels=labels,
    )


def _report_startup_failure(logger, error, phase, config=None):
    """Report a startup error without allowing logging to replace it."""
    safe_message = _safe_startup_message(error, config)
    try:
        logger.error(
            'Startup failed during %s: %s',
            phase,
            safe_message,
            exc_info=True,
            extra={
                'event': 'startup_failed',
                'status': 'failure',
                'fields': {
                    'exception_type': type(error).__name__,
                    'startup_phase': phase,
                    'error_message': safe_message,
                },
            },
        )
    except Exception as logging_error:
        # A broken monitoring destination must never obscure the root cause.
        try:
            sys.stderr.write(
                'WARNING: Unable to log startup failure: '
                f'{type(logging_error).__name__}\n'
            )
        except Exception:
            pass


def _warn_monitoring_unavailable(logger, error, config):
    """Keep a monitoring warning from changing startup control flow."""
    try:
        logger.warning(
            'Startup remote syslog unavailable; local logging remains '
            'active: %s', _safe_startup_message(error, config)
        )
    except Exception:
        pass


def _load_config(value):
    """Load a JSON configuration string or file."""
    if os.path.isfile(os.path.expandvars(value)):
        with open(os.path.expandvars(value)) as config_file:
            return json.load(config_file)
    try:
        return json.loads(value)
    except json.decoder.JSONDecodeError:
        raise RuntimeError(
            'JSON configuration should be a string or file!'
        )


def _validate_config(config):
    """Validate the top-level configuration required by the entrypoint."""
    if not isinstance(config, dict):
        raise TypeError('JSON config should be a dictionary!')
    for key in ('schedule', 'wav'):
        if key not in config:
            raise KeyError(
                f"JSON config should contain the dictionary '{key}'!"
            )
        if not isinstance(config[key], dict):
            raise TypeError(f"JSON config '{key}' should be a dictionary!")


def _initialize_service(args, logger, prog, info):
    """Parse, validate and initialize behind one startup error boundary."""
    config = None
    phase = 'configuration_parsing'
    try:
        config = _load_config(args.config)

        # Remote monitoring becomes available immediately after parsing,
        # before any configuration or SchoolBell validation can fail.
        try:
            _configure_startup_monitoring(logger, config)
        except Exception as monitoring_error:
            _warn_monitoring_unavailable(logger, monitoring_error, config)

        phase = 'configuration_validation'
        _validate_config(config)

        # Hash supplied JSON before adding command-line/runtime-only values.
        config['config_hash'] = content_hash(config)
        config['schedule_hash'] = content_hash(config['schedule'])
        # --check always remains non-operational, even if combined with
        # hardware-oriented command-line flags.
        config['test'] = args.test and not args.check
        config['check'] = args.check
        config['debug'] = args.debug
        config['prog'] = f'{prog}.check-internal' if args.check else prog
        config['info'] = info

        phase = 'service_initialization'
        return SchoolBell(**config)
    except Exception as error:
        _report_startup_failure(logger, error, phase, config)
        raise


def _check_configuration(args, logger, prog, info):
    """Validate configuration and resources without operational side effects."""
    try:
        obj = _initialize_service(args, logger, prog, info)
    except Exception as error:
        config = None
        try:
            config = _load_config(args.config)
        except Exception:
            pass
        print('ERROR: Configuration: '
              f'{_safe_startup_message(error, config)}')
        return 1

    config = _load_config(args.config)
    timeout = int(config.get('timeout') or 10)
    failed = False
    try:
        print('OK: Configuration is valid.')
        print(f'OK: {len(config["wav"])} configured WAVE file(s) exist.')

        holidays = config.get('holidays')
        if holidays:
            try:
                country, language = holidays.split('-', 1)
                client = OpenHolidays(
                    countryIsoCode=country,
                    languageIsoCode=language,
                    groupCode=holidays,
                )
                today = datetime.date.today()
                values = client.holidays(
                    str(today), str(today + datetime.timedelta(days=180)),
                    timeout=timeout,
                )
                if not isinstance(values, list):
                    raise ValueError('API response is not a holiday list')
                print(f'OK: OpenHolidays returned {len(values)} holiday(s).')
            except Exception as error:
                failed = True
                print('ERROR: OpenHolidays could not be retrieved and parsed '
                      f'({type(error).__name__}).')
        else:
            print('NOT CONFIGURED: OpenHolidays.')

        calendar_url = config.get('disable_calendar')
        if calendar_url:
            calendar = DisableCalendar(
                calendar_url,
                timezone=config.get('timezone', 'Europe/Brussels'),
                timeout=timeout,
            )
            if calendar.refresh():
                print('OK: Disable calendar parsed successfully.')
            else:
                failed = True
                print('ERROR: Disable calendar could not be retrieved and parsed.')
        else:
            print('NOT CONFIGURED: Disable calendar.')
    finally:
        obj.close()
    return 1 if failed else 0


def main():
    """Main script function.
    """

    prog = 'school-bell'
    info = 'Python-scheduled ringing of a school bell.'

    # arguments
    parser = argparse.ArgumentParser(prog=prog, description=info)
    parser.add_argument(
        '-b', '--buzz', metavar='..', type=int, nargs='?',
        default=False, const=17,
        help=('Buzz via RPi GPIO while the WAV audio file plays '
              '(default: %(default)s)')
    )
    parser.add_argument(
        '-p', '--play', metavar='..', type=str, nargs='?',
        default=False,
        help=('Play a WAV audio file by specifying the key from '
              'the JSON configuration and exit '
              '(default: %(default)s)')
    )
    parser.add_argument(
        '--debug', action='store_true',
        default=False,
        help='Make the operation a lot more talkative'
    )
    parser.add_argument(
        '--demo-config', action=DemoConfig, nargs=0,
        help='Print the demo JSON configuration and exit'
    )
    parser.add_argument(
        '--demo-service', action=DemoService, nargs=0,
        help='Print the demo systemctl service for the current user and exit'
    )
    parser.add_argument(
        '--test', action='store_true',
        default=False,
        help=('Test each configured GPIO pin and play one second of each '
              'WAVE audio file at startup '
              '(default: %(default)s)')
    )
    parser.add_argument(
        '--check', action='store_true',
        default=False,
        help=('Validate configuration, files and external services without '
              'starting the scheduler or activating bells')
    )
    parser.add_argument(
        '--update', action=SelfUpdate, metavar='..', nargs='?', type=str,
        default='main',
        help=('Update %(prog)s from git. Optionally set the branch '
              '(default: %(default)s)')
    )
    parser.add_argument(
        '--version', action='version', version=version,
        help='Print the version and exit'
    )
    parser.add_argument(
        'config', type=str, help='JSON configuration (string or file)'
    )

    # parse arguments
    args = parser.parse_args()

    logger = init_logger(prog, args.debug)
    if args.check:
        return _check_configuration(args, logger, prog, info)
    obj = _initialize_service(args, logger, prog, info)

    # play a test file or run the schedule
    try:
        if args.play:
            obj.play(args.play)
        else:
            obj.run_schedule()
    finally:
        obj.close()


if __name__ == "__main__":
    raise SystemExit(main())
