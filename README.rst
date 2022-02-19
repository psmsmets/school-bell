*************************************
School Bell
*************************************

Python scheduled ringing of the school bell.

Installation
============

.. code-block:: bash

    pip install -e


Usage
=====

Type ``school-bell --help`` for the usage.


.. code-block:: bash

    usage: school-bell [-h] [-a ..] [-b [..]] [-c ..] [--debug] [--version]

    Python scheduled ringing of the school bell.

    optional arguments:
      -h, --help            show this help message and exit
      -a .., --wav ..       WAV audio file
      -b [..], --buzz [..]  Buzz via RPi GPIO while the WAV audio file plays
      -c .., --config ..    JSON configuration file
      --debug               Make the operation a lot more talkative
      --version             Print the version and exit


Configuration (JSON)
====================

.. code-block:: JSON

    {
        "schedule": {
            "Mon": ["08:30", "12:00", "15:00"],
            "Tue": ["08:30", "12:00", "15:00"],
            "Wed": ["08:30", "12:00"],
            "Thu": ["08:30", "12:00", "15:00"],
            "Fri": ["08:30", "12:00", "15:00"]
        },
        "trigger": {
            "pi@10.10.70.121": "aplay SchoolBell.wav &"
        },
        "wav": "SchoolBell-SoundBible.com-449398625.wav"
    }

The remote trigger requires an ``ssh-key`` to connect to the remote host!

Licensing
=========

The source code for school-bell is licensed under MIT that can be found under the LICENSE file.

Pieter Smets © 2022. All rights reserved.
