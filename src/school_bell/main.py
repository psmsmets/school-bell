#!/usr/bin/python3

# absolute imports
import argparse
import json
import pkgutil
import os
import sys

# Relative imports
try:
    from .version import version
except (ValueError, ModuleNotFoundError, SyntaxError):
    version = "VERSION-NOT-FOUND"
from .utils import init_logger, system_call
from .school_bell import SchoolBell

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

    # parse config
    if os.path.isfile(os.path.expandvars(args.config)):
        with open(os.path.expandvars(args.config)) as f:
            args.config = json.load(f)
    else:
        try:
            args.config = json.loads(args.config)
        except json.decoder.JSONDecodeError:
            err = "JSON configuration should be a string or file!"
            raise RuntimeError(err)

    # check if all main arguments are present and of the correct type
    for key in ('schedule', 'wav'):
        if key not in args.config:
            err = f"JSON config should contain the dictionary '{key}'!"
            raise KeyError(err)
        if not isinstance(args.config[key], dict):
            err = f"JSON config '{key}' should be a dictionary!"
            raise TypeError(err)

    # add some extra config keys
    args.config['test'] = args.test
    args.config['debug'] = args.debug
    args.config['prog'] = prog
    args.config['info'] = info

    # play a test file or run the schedule
    if args.play:
        args.config.pop('schedule', False)
        args.config.pop('trigger', False)
        obj = SchoolBell(**args.config)
        obj.play(args.play)
        raise SystemExit()
    else:
        obj = SchoolBell(**args.config)
        obj.run_schedule()


if __name__ == "__main__":
    main()
