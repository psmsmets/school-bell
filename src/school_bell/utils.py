#!/usr/bin/python3

# absolute imports
import logging
import os
import sys
from datetime import datetime, date
from subprocess import Popen, PIPE, TimeoutExpired


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
    if not any(
        getattr(handler, '_school_bell_stream', False)
        for handler in logger.handlers
    ):
        streamHandler = logging.StreamHandler(sys.stdout)
        streamHandler._school_bell_stream = True
        streamHandler.setFormatter(logging.Formatter(
            "%(levelname)s: %(message)s"
            # "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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

    timeout = kwargs.pop('timeout', None)
    p = Popen(command, stdout=PIPE, stderr=PIPE, **kwargs)

    try:
        output, error = p.communicate(timeout=timeout)
    except TimeoutExpired:
        p.kill()
        output, error = p.communicate()
        log.error(
            'Command timed out after %s seconds: %s',
            timeout, ' '.join(command),
        )
        return False

    if output:
        log.debug(output.decode("utf-8"))

    if p.returncode != 0:
        log.error(error.decode("utf-8"))

    return p.returncode == 0


def to_datetime(value: str, fmt: str = None):
    """Convert a datetime string to a `datetime.datetime` object.
    """
    if isinstance(value, datetime):
        return value
    elif isinstance(value, str):
        return datetime.strptime(value, fmt or '%Y-%m-%d %H:%M:%S.%f')
    else:
        raise TypeError('to_datetime requires a datetime string!')


def to_date(value: str, fmt: str = None):
    """Convert a date string to a `datetime.date` object.
    """
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    elif isinstance(value, str):
        return datetime.strptime(value, fmt or '%Y-%m-%d').date()
    else:
        raise TypeError('to_date requires a date string!')
