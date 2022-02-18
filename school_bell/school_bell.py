#!/usr/bin/python3

import logging
import schedule
import sys
import time
from argparse import ArgumentParser
from subprocess import Popen, PIPE


def init_logger(debug):
    """Create the logger object
    """
    # create logger
    logger = logging.getLogger('school bell')

    # log to stdout
    streamHandler = logging.StreamHandler(sys.stdout)
    streamHandler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(streamHandler)

    # set logger level
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    return logger


def ring(wav, logger):
    """Ring the school bell
    """
    logger.info('ring!')

    p = Popen(['aplay', '--nonblock', '--quiet', wav],
              stdout=PIPE, stderr=PIPE)

    out, err = p.communicate()
    if p.returncode != 0:
        logger.error(err)


def main():
    """Main script function.
    """
    # arguments
    parser = ArgumentParser(
        prog='schoolbell',
        description=('Sensorboard serial readout with data storage'
                     'in a local influx database.'),
    )
    parser.add_argument(
        '-a', '--wav', metavar='..', type=str, default='schoolbell.wav',
        help='Path to school bell audio file (.wav!)'
    )
    parser.add_argument(
        '-i', '--ini', metavar='..', type=str, default='config.ini',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--debug', action='store_true', default=False,
        help='Make the operation a lot more talkative'
    )
    parser.add_argument(
        '--version', action='version', version='0.1',
        help='Print the version and exit'
    )

    # parse arguments
    args = parser.parse_args()

    # create logger
    logger = init_logger(args.debug)

    # create schedule
    schedule.every().minute.at(":17").do(ring, args.wav, logger)
    schedule.every().day.at("19:38:05").do(ring, args.wav, logger)

    # run schedule
    logger.info('Schedule started')
    while True:
        schedule.run_pending()
        time.sleep(.5)


if __name__ == "__main__":
    main()
