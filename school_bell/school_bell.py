#!/usr/bin/python3

# absolute imports
import calendar
import json
import logging
import os
import schedule
import sys
from argparse import ArgumentParser
from gpiozero import Buzzer
from subprocess import Popen, PIPE
from time import sleep

# Relative imports
try:
    from .version import version
except (ValueError, ModuleNotFoundError):
    version = "VERSION-NOT-FOUND"

# Check platform
if sys.platform in ("linux", "linux2"):
    _play = "/usr/bin/aplay"
elif sys.platform == "darwin":
    _play = "/usr/bin/afplay"
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


def ring(wav, buzzer, trigger, log):
    """Ring the school bell
    """
    log.info("ring!")
    log.debug(' '.join([_play, wav]))

    for remote, command in trigger.items():
        remote_ring(remote, command, log)

    if buzzer:
        buzzer.on()

    p = Popen([_play, wav], stdout=PIPE, stderr=PIPE)

    output, error = p.communicate()

    if buzzer:
        buzzer.off()

    log.debug(output.decode("utf-8"))

    if p.returncode != 0:
        log.error(error.decode("utf-8"))

    return p.returncode == 0


def remote_ring(remote, command, log):
    """Remote ring trigger
    """
    log.info(f"remote ring {remote}!")
    log.debug(' '.join(['/usr/bin/ssh', remote, f"'{command}'"]))

    p = Popen(["/usr/bin/ssh", remote, f"'{command}'"],
              stdout=PIPE, stderr=PIPE)

    output, error = p.communicate()

    log.debug(output.decode("utf-8"))

    if p.returncode != 0:
        log.error(error.decode("utf-8"))

    return p.returncode == 0


def test_remote_trigger(trigger, log):
    """Test remote ring triggers
    """
    for remote in list(trigger.keys()):

        success = remote_ring(remote, trigger[remote], log)

        if not success:
            log.warning(f"remote ring test for {remote} failed!")
            trigger.pop(remote)

    return trigger


def main():
    """Main script function.
    """
    # arguments
    parser = ArgumentParser(
        prog='school-bell',
        description=('Python scheduled ringing of the school bell.'),
    )
    parser.add_argument(
        '-a', '--wav', metavar='..', type=str, default=None,
        help='WAV audio file'
    )
    parser.add_argument(
        '-b', '--buzz', metavar='..', type=int, nargs='?',
        default=False, const=17,
        help='Buzz via RPi GPIO while the WAV audio file plays'
    )
    parser.add_argument(
        '-c', '--config', metavar='..', type=str, default='config.json',
        help='JSON configuration file'
    )
    parser.add_argument(
        '--debug', action='store_true', default=False,
        help='Make the operation a lot more talkative'
    )
    parser.add_argument(
        '--version', action='version', version=version,
        help='Print the version and exit'
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
            args.config = dict()

    # set wav file
    if 'wav' in args.config:
        args.wav = args.config['wav']
    args.wav = args.wav or 'SchoolBell-SoundBible.com-449398625.wav'
    if not os.path.isfile(args.wav):
        wav = os.path.join(sys.exec_prefix, 'share', 'school-bell', args.wav)
        if os.path.isfile(wav):
            args.wav = wav
        else:
            log.error(f"{args.wav} not found!")
            raise FileNotFoundError(f"{args.wav} not found!")
    log.info(f"wav = {args.wav}")

    # buzzer?
    buzzer = False
    log.info(f"buzzer = {args.buzz}")
    if args.buzz:
        if is_raspberry_pi():
            buzzer = Buzzer(args.buzz)
        else:
            log.warning("Host is not a Raspberry Pi: buzzer disabled!")

    # test remote triggers
    log.info(f"trigger = {'trigger' in args.config}")
    trigger = test_remote_trigger(
        args.config['trigger'] if 'trigger' in args.config else dict(), log
    )

    # ring wrapper
    def _ring():
        ring(args.wav, buzzer, trigger, log)

    # create schedule
    log.debug("schedule =")
    for day, times in args.config['schedule'].items():
        day_num = list(calendar.day_abbr).index(day)
        day_name = calendar.day_name[day_num].lower()
        for time in times:
            log.debug(f"  ring every {day} at {time}")
            eval(f"schedule.every().{day_name}.at(\"{time}\").do(_ring)")

    # run schedule
    log.info('Schedule started')
    while True:
        schedule.run_pending()
        sleep(.5)


if __name__ == "__main__":
    main()
