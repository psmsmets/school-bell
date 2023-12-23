#!/usr/bin/python3

# absolute imports
import argparse
import calendar
import json
import logging
import pkgutil
import os
import schedule
import sys
from gpiozero import Buzzer
from time import sleep
from threading import Thread

# Relative imports
try:
    from .version import version
except (ValueError, ModuleNotFoundError, SyntaxError):
    version = "VERSION-NOT-FOUND"
from .utils import init_logger, is_raspberry_pi, system_call, today_is_holiday

# Set path of demo files
share = os.path.join(sys.exec_prefix, 'share', 'school-bell')
if not os.path.exists(share):
    share = os.path.join(
        os.path.dirname(pkgutil.get_loader("school_bell").get_filename()),
        '..'
    )

# Check platform and set wav player
if sys.platform in ("linux", "linux2"):
    _play = ["/usr/bin/aplay"]
    _play_test = _play + ['-d', '1']
    _alsa = True
elif sys.platform == "darwin":
    _play = ["/usr/bin/afplay"]
    _play_test = _play + ['-t', '1']
    _alsa = False
elif sys.platform in ("win32", "win64"):
    raise NotImplementedError('school_bell.py does not work on Windows')


def play(wav: str, device: str, log: logging.Logger, test: bool = False):
    """Play the school bell. Returns `True` on success.
    """
    cmd = _play_test if test else _play
    cmd = cmd + ['-D', device, wav] if (_alsa and device) else cmd + [wav]

    # log.debug(f"system_call = {cmd}")

    return system_call(cmd, log)


def ring(key, wav, buzzer, trigger, device, holidays, timeout, log):
    """Ring the school bell
    """

    # check if current day is not a public/school holiday!
    if today_is_holiday(holidays, timeout, log):
        log.info("today is a holiday, no need to ring!")
        return

    log.info(f"ring {key}={os.path.basename(wav)}!")

    threads = []
    for remote, command in trigger.items():
        threads.append(Thread(target=remote_ring,
                              args=(remote, [command, wav, '&'], log)))
    threads.append(Thread(target=play, args=(wav, device, log)))

    if buzzer:
        buzzer.on()

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    if buzzer:
        buzzer.off()


def remote_ring(host: str, command: list, log: logging.Logger):
    """Remote ring over ssh. Returns `True` on success.
    """
    ssh = ["/usr/bin/ssh",
           "-t",
           "-o", "ConnectTimeout=1",
           "-o", "StrictHostKeyChecking=no",
           host]
    return system_call(ssh + command, log)


def test_remote_trigger(trigger, log):
    """Test remote ring triggers. Returns the filtered trigger dictionary.
    """
    for remote in list(trigger.keys()):

        if remote_ring(remote, [trigger[remote], "--help"], log):
            log.info(f"  remote ring {remote}")

        else:
            log.warning(f"remote ring test for {remote} failed!")
            trigger.pop(remote)

    return trigger


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


def main():
    """Main script function.
    """

    prog = 'school-bell'
    info = 'Python scheduled ringing of the school bell.'

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
        help=('Play one second samples of each WAVE audio file from '
              'the JSON configuration at startup '
              '(default: %(default)s)')
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

    # create logger object
    log = init_logger(prog, args.debug)

    # header
    log.info(info)
    log.info(f"version = {version}")

    # parse json config
    log.info(f"config = {args.config}")
    if os.path.isfile(os.path.expandvars(args.config)):
        with open(os.path.expandvars(args.config)) as f:
            args.config = json.load(f)
    else:
        try:
            args.config = json.loads(args.config)
        except json.decoder.JSONDecodeError:
            err = "JSON configuration should be a string or file!"
            log.error(err)
            raise RuntimeError(err)
    log.info(f"play = {_play}")

    # check if all arguments are present
    for key in ('schedule', 'trigger', 'wav'):
        if key not in args.config:
            err = f"JSON config should contain the dictionary '{key}'!"
            log.error(err)
            raise KeyError(err)
        if not isinstance(args.config[key], dict):
            err = f"JSON config '{key}' should be a dictionary!"
            log.error(err)
            raise TypeError(err)

    # get expanded root
    root = os.path.expandvars(
        args.config['root'] if 'root' in args.config else ''
    )
    log.info(f"root = {root}")

    # get alsa hardware output device (linux only)
    device = args.config['device'] if 'device' in args.config else None
    log.info(f"alsa output device = {device}")

    # get openholidays subdivision code and timeout
    holidays = args.config['holidays'] if 'holidays' in args.config else False
    timeout = args.config['timeout'] if 'timeout' in args.config else None
    log.info(f"openholidays api subdivision code = {holidays}")
    log.info(f"openholidays api request timeout = {timeout}")

    # test by playing a single wav
    if args.play:
        wav = args.config['wav'][args.play]
        log.info(f"play = {wav}")
        root_wav = os.path.expandvars(os.path.join(root, wav))
        if not play(root_wav, device, log, test=False):
            err = f"Could not play {wav}!"
            log.error(err)
            raise RuntimeError(err)
        log.info("Play completed succesfully.")
        raise SystemExit()

    # verify all wav
    log.info("wav =")
    for key, wav in args.config['wav'].items():
        log.info(f"  {key}: {wav}")
        root_wav = os.path.expandvars(os.path.join(root, wav))
        if not os.path.isfile(root_wav):
            err = f"File '{root_wav}' not found!"
            log.error(err)
            raise FileNotFoundError(err)
        if args.test:
            if not play(root_wav, device, log, test=True):
                err = f"Could not play {root_wav}!"
                log.error(err)
                raise RuntimeError(err)
    if not args.test:
        log.warning("wav audio files not not played to test "
                    "(run with option --test instead)")

    # verify remote triggers
    log.info("trigger =")
    trigger = test_remote_trigger(
        args.config['trigger'] if 'trigger' in args.config else dict(), log
    )

    # buzz?
    buzzer = False
    log.info(f"buzzer = {args.buzz}")
    if args.buzz:
        if is_raspberry_pi():
            buzzer = Buzzer(args.buzz)
        else:
            log.warning("Host is not a Raspberry Pi: buzzer disabled!")

    # ring wrapper
    def _ring(key, wav):
        ring(key, wav, buzzer, trigger, device, holidays, timeout, log)

    # create schedule
    log.info("schedule =")
    for day, times in args.config['schedule'].items():
        day_num = list(calendar.day_abbr).index(day)
        day_name = calendar.day_name[day_num].lower()
        for time, wav_key in times.items():
            log.info(f"  ring every {day} at {time} with {wav_key}")
            try:
                wav = os.path.join(root, args.config['wav'][f"{wav_key}"])
            except KeyError:
                err = f"wav key {wav_key} is not related to any sample!"
                log.error(err)
                raise KeyError(err)
            eval(
                "schedule.every().{}.at(\"{}\").do(_ring, wav_key, wav)"
                .format(day_name, time)
            )

    # run schedule
    log.info('Schedule started')
    while True:
        schedule.run_pending()
        sleep(.2)


if __name__ == "__main__":
    main()
