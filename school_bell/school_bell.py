#!/usr/bin/python3

# absolute imports
import argparse
import calendar
import json
import logging
import os
import schedule
import sys
from gpiozero import Buzzer
from subprocess import Popen, PIPE
from time import sleep

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


def init_logger(debug):
    """Create the logger object
    """
    # create logger
    logger = logging.getLogger("school bell")

    # log to stdout
    streamHandler = logging.StreamHandler(sys.stdout)
    streamHandler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    logger.addHandler(streamHandler)

    # set logger level
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    return logger


def system_call(command: list, log: logging.Logger):
    """Execute a system call. Returns `True` on success.
    """
    log.debug(' '.join(command))

    p = Popen(command, stdout=PIPE, stderr=PIPE)

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

    for remote, command in trigger.items():
        remote_ring(remote, [command, wav], log)

    if buzzer:
        buzzer.on()

    play(wav, log)

    if buzzer:
        buzzer.off()


def remote_ring(remote: str, command: list, log: logging.Logger):
    """Remote ring over ssh. Returns `True` on success.
    """
    return system_call(
        ['/usr/bin/ssh', '-o', 'ConnectTimeout=1', remote] + command,
        log
    )


def test_remote_trigger(trigger, log):
    """Test remote ring triggers. Returns the filtered trigger dictionary.
    """
    for remote in list(trigger.keys()):

        if remote_ring(remote, [trigger[remote], '--help'], log):
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


def main():
    """Main script function.
    """
    # arguments
    parser = argparse.ArgumentParser(
        prog='school-bell',
        description=('Python scheduled ringing of the school bell.'),
    )
    parser.add_argument(
        '-b', '--buzz', metavar='..', type=int, nargs='?',
        default=False, const=17,
        help=('Buzz via RPi GPIO while the WAV audio file plays '
              '(default: %(default)s)')
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
        '--version', action='version', version=version,
        help='Print the version and exit'
    )
    parser.add_argument(
        'config', type=str, help='JSON configuration (string or file)'
    )

    # parse arguments
    args = parser.parse_args()

    # create logger object
    log = init_logger(args.debug)

    # parse json config
    log.info(f"config = {args.config}")
    if os.path.isfile(args.config):
        with open(args.config) as f:
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

    # verify wav
    log.info("wav =")
    for key, wav in args.config['wav'].items():
        log.info(f"  {key}: {wav}")
        root_wav = os.path.join(root, wav)
        if not os.path.isfile(root_wav):
            err = f"File '{root_wav}' not found!"
            log.error(err)
            raise FileNotFoundError(err)
        if not play(root_wav, log, test=True):
            err = f"could not play {wav}!"
            log.error(err)
            raise RuntimeError(err)

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
