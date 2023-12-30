#!/usr/bin/python3

# absolute imports
import logging
import os
import sys
from datetime import datetime
from subprocess import Popen, PIPE


__all__ = ['init_logger', 'is_raspberry_pi', 'system_call',
           'to_datetime', 'to_date']


def init_logger(
    prog=None, debug=False
):
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


def system_call(
    command: list, log: logging.Logger = None,
    **kwargs
):
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


def to_datetime(value: str, fmt: str = None):
    """Convert a datetime string to a `datetime.datetime` object.
    """
    return datetime.strptime(value, fmt or '%Y-%m-%d %H:%M:%S.%f')


def to_date(value: str, fmt: str = None):
    """Convert a date string to a `datetime.date` object.
    """
    return datetime.strptime(value, fmt or '%Y-%m-%d').date()
