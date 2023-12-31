# -*- coding: utf-8 -*-
"""
school_bell

Python scheduled ringing of the school bell

:author:
    Pieter Smets (mail@pietersmets.be)

:copyright:
    Pieter Smets (mail@pietersmets.be)

:license:
    This code is distributed under the terms of the
    MIT that can be found under the LICENSE file.
"""

# Import main modules
from . import utils, openholidays, main

# Import SchoolBell class
from .school_bell import SchoolBell

# Make only a selection available to __all__ to not clutter the namespace
# Maybe also to discourage the use of `from xcorr import *`.
__all__ = ['SchoolBell', 'utils', 'openholidays', 'main']

# Version
try:
    # - Released versions just tags:       1.10.0
    # - GitHub commits add .dev#+hash:     1.10.1.dev3+g973038c
    # - Uncom. changes add timestamp: 1.10.1.dev3+g973038c.d20191022
    from .version import version as __version__
except ImportError:
    # If it was not installed, then we don't know the version.
    # We could throw a warning here, but this case *should* be
    # rare. empymod should be installed properly!
    from datetime import datetime
    __version__ = 'unknown-'+datetime.today().strftime('%Y%m%d')
