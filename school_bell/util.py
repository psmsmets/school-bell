#!/usr/bin/python3

# absolute imports
import logging
import os
import sys
from datetime import date
from subprocess import Popen, PIPE

# Relative imports
from .openholidays import OpenHolidays


__all__ = ['init_logger', 'is_raspberry_pi', 'system_call', 'today_is_holiday']


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


def is_raspberry_pi():
    """Checks if the device is a Rasperry Pi
    """
    if not os.path.exists("/proc/device-tree/model"):
        return False
    with open("/proc/device-tree/model") as f:
        model = f.read()
    return model.startswith("Raspberry Pi")


__holidays = OpenHolidays()


def today_is_holiday(subdivisionCode: str, timeout = None):
    """Returns `True` if the current day is either a public or school holiday.
    Consecutive identical requests are returned from cache.
    """

    if not subdivisionCode:
        return False

    return __holidays.isHoliday(
        date=f"{date.today()}",
        countryIsoCode=subdivisionCode.split('-')[1],
        languageIsoCode=subdivisionCode.split('-')[0],
        subdivisionCode=subdivisionCode,
        timeout=timeout
    )


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
