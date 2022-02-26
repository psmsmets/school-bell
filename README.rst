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


.. code-block::

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
            "Mon": {"08:30": 0, "12:00": 0, "15:00": 0},
            "Tue": {"08:30": 0, "12:00": 0, "15:00": 0},
            "Wed": {"08:30": 0, "12:00": 0},
            "Thu": {"08:30": 0, "12:00": 0, "15:00": 0},
            "Fri": {"08:30": 0, "12:00": 0, "15:00": 0},
        },
        "trigger": {
            "pi@10.10.70.121": "aplay"
        },
        "wav": {
            "0": "samples/SchoolBell-SoundBible.com-449398625.wav",
            "1": "samples/ClassBell-SoundBible.com-1426436341.wav"
        }
    }

The remote trigger requires an ``ssh-key`` to connect to the remote host!


Systemd service
===============

Create a systemd service of the school-bell. An example service is given in ``school-bell.service`` for user ``pi`` with the configuration in ``~/school-bell.json``.

.. code-block:: sh

    sudo cp school-bell.service /etc/systemd/system
    sudo systemctl daemon-reload
    sudo systemctl enable school-bell    
    sudo systemctl start school-bell


Check the status of the ``school-bell`` service

.. code-block:: sh

    $ systemctl status school-bell
    ● school-bell.service - Scheduled school bell
         Loaded: loaded (/etc/systemd/system/school-bell.service; enabled; vendor preset: enabled)
         Active: active (running) since Wed 2022-02-23 15:21:25 CET; 17s ago
       Main PID: 1192 (school-bell)
          Tasks: 1 (limit: 840)
            CPU: 762ms
         CGroup: /system.slice/school-bell.service
                 └─1192 /home/pi/.local/bin/python3 /home/pi/.local/bin/school-bell -c /home/pi/schoolbell.json --debug

    Feb 23 15:21:28 pibell schoolbell[1192]: 2022-02-23 15:21:28,933 - school bell - INFO - Schedule started


Logs are handled via ``syslog``. Show all logs of today:

.. code-block:: sh

    journalctl -u school-bell --since=today
    

Configure a RPi
===============

See guide_ how to configure a Raspberry Pi scratch.

.. _guide: RPi-setup.rst


Licensing
=========

The source code for school-bell is licensed under MIT that can be found under the LICENSE file.

Pieter Smets © 2022. All rights reserved.
