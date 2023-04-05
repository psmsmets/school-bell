#!/usr/bin/python3

# absolute imports
import argparse
import calendar
import json
import logging
import os
import schedule
import sys
import tempfile
from gpiozero import Buzzer
from subprocess import Popen, PIPE
from time import sleep
from threading import Thread

# Relative imports
try:
    from .version import version
except (ValueError, ModuleNotFoundError):
    version = "VERSION-NOT-FOUND"

# Check platform and set wav player
if sys.platform in ("linux", "linux2"):
    _play = "/usr/bin/aplay"
    _play_test = [_play, '-d', '1']
elif sys.platform == "darwin":
    _play = "/usr/bin/afplay"
    _play_test = [_play, '-t', '1']
elif sys.platform in ("win32", "win64"):
    raise NotImplementedError('school_bell.py does not work on Windows')


def is_raspberry_pi():
    """Checks if the device is a Rasperry Pi
    """
    if not os.path.exists("/proc/device-tree/model"):
        return False
    with open("/proc/device-tree/model") as f:
        model = f.read()
    return model.startswith("Raspberry Pi")


def init_logger(prog=None, debug=False):
    """Create the logger object
    """
    # create logger
    logger = logging.getLogger(prog or 'school-bell')

    # log to stdout
    streamHandler = logging.StreamHandler(sys.stdout)
    streamHandler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    logger.addHandler(streamHandler)

    # set logger level
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    return logger


def system_call(command: list, log: logging.Logger = None, **kwargs):
    """Execute a system call. Returns `True` on success.
    """
    if not isinstance(command, list):
        raise TypeError("command should be a list!")
    log = log if isinstance(log, logging.Logger) else init_logger(debug=True)

    log.debug(' '.join(command))

    p = Popen(command, stdout=PIPE, stderr=PIPE, **kwargs)

    output, error = p.communicate()

    log.debug(output.decode("utf-8"))

    if p.returncode != 0:
        log.error(error.decode("utf-8"))

    return p.returncode == 0


def play(wav: str, log: logging.Logger, test: bool = False):
    """Play the school bell. Returns `True` on success.
    """
    return system_call(_play_test + [wav] if test else [_play, wav], log)


def ring(wav, buzzer, trigger, log):
    """Ring the school bell
    """
    log.info("ring!")

    threads = []
    for remote, command in trigger.items():
        threads.append(Thread(target=remote_ring,
                              args=(remote, [command, wav, '&'], log)))
    threads.append(Thread(target=play, args=(wav, log)))

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


class DemoConfig(argparse.Action):
    """Argparse action to print a demo JSON configuration
    """
    def __call__(self, parser, namespace, values, option_string=None):
        demo = os.path.join(
            sys.exec_prefix, 'share', 'school-bell', 'config.json'
        )
        with open(demo, "r") as demo_config:
            print(json.dumps(json.load(demo_config), indent=4))
        sys.exit()


class SelfUpdate(argparse.Action):
    """Argparse action to self-update the school-bell code from git.
    """
    def __call__(self, parser, namespace, values, option_string=None):

        with tempfile.TemporaryDirectory() as tmp:

            log = init_logger(debug=True)
            git = 'https://github.com/psmsmets/school-bell.git'
            src = os.path.join(tmp, 'school-bell')

            if system_call(['git', 'clone', git, tmp], log):
                system_call(['pip', 'install', '--src', src, '.'], log)

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
        help=('Play a wav to test the audio by specifying the key from '
              'JSON configuration (default: %(default)s)')
    )
    parser.add_argument(
        '--debug', action='store_true', default=False,
        help='Make the operation a lot more talkative'
    )
    parser.add_argument(
        '--demo', action=DemoConfig, nargs=0,
        help='Print the demo JSON configuration and exit'
    )
    parser.add_argument(
        '--test', action='store_true', default=False,
        help=('Play one second samples of each wav file at startup '
              '(default: %(default)s)')
    )
    parser.add_argument(
        '--update', action=SelfUpdate, nargs=0,
        help='Update %(prog)s from git'
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

    # get root
    root = args.config['root'] if 'root' in args.config else ''
    log.info(f"root = {root}")

    # test by playing a single wav
    if args.play:
        wav = args.config['wav'][args.test]
        log.info(f"test = {wav}")
        root_wav = os.path.expandvars(os.path.join(root, wav))
        if not play(root_wav, log, test=False):
            err = f"Could not play {wav}!"
            log.error(err)
            raise RuntimeError(err)
        raise SystemExit("test completed")

    # verify all wav
    if args.test:
        log.info("wav =")
        for key, wav in args.config['wav'].items():
            log.info(f"  {key}: {wav}")
            root_wav = os.path.expandvars(os.path.join(root, wav))
            if not os.path.isfile(root_wav):
                err = f"File '{root_wav}' not found!"
                log.error(err)
                raise FileNotFoundError(err)
            if not play(root_wav, log, test=True):
                err = f"Could not play {root_wav}!"
                log.error(err)
                raise RuntimeError(err)
    else:
        log.warning("wav files not tested at startup")

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
    def _ring(wav):
        ring(wav, buzzer, trigger, log)

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
            eval(f"schedule.every().{day_name}.at(\"{time}\").do(_ring, wav)")

    # run schedule
    log.info('Schedule started')
    while True:
        schedule.run_pending()
        sleep(.5)


if __name__ == "__main__":
    main()
