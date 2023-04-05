*************************************
School Bell
*************************************

Python scheduled ringing of the school bell.


Setup
=====

See the guide_ how to configure a Raspberry Pi and Python 3.9 virtual environment from scratch.

.. _guide: GUIDE.rst

Install the local Python package using ``pip``.

.. code-block:: bash

    pip install .


Usage
=====

Type ``school-bell --help`` for the usage.


.. code-block::

    usage: school-bell [-h] [-b [..]] [--debug] [--demo] [--version] config

    Python scheduled ringing of the school bell.

    positional arguments:
      config                JSON configuration (string or file)

    optional arguments:
      -h, --help            show this help message and exit
      -b [..], --buzz [..]  Buzz via RPi GPIO while the WAV audio file plays (default: False)
      -p [..], --play [..]  Play a wav to test the audio by specifying the key from JSON configuration (default: False)
      --debug               Make the operation a lot more talkative
      --demo                Print the demo JSON configuration and exit
      --test                Play one second samples of each wav file at startup
      --update              Update school-bell from git
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
            "Fri": {"08:30": 0, "12:00": 0, "15:00": 0}
        },
        "trigger": {
            "pibell2": "/usr/bin/aplay"
        },
        "wav": {
            "0": "samples/SchoolBell-SoundBible.com-449398625.wav",
            "1": "samples/ClassBell-SoundBible.com-1426436341.wav"
        },
        "root": "${HOME}"
    }

The remote trigger requires an ``ssh-key`` to connect to the remote host!

Generate a new ``ssh-key`` named ``school-bell`` in ``${HOME}/.ssh/id_school_bell`` and upload it to the Raspberry Pi with hostname ``pibell2``

.. code-block:: sh

    ssh-keygen -t rsa -b 4096 -C "school-bell" -N "" -f ${HOME}/.ssh/id_school_bell
    ssh-copy-id -f -i${HOME}/.ssh/id_school_bell pi@pibell2.local

Add the following configuration for ``pibell2`` to ``~/.ssh/config``:

.. code-block:: sh

    Host pibell2
        HostName pibell2.local
        User pi
        ForwardX11 no
        PreferredAuthentications publickey
        IdentityFile ~/.ssh/id_school_bell


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
                 └─1192 /home/pi/.local/bin/python3 /home/pi/.local/bin/school-bell /home/pi/school-bell.json --debug

    Feb 23 15:21:28 pibell school-bell[1192]: 2022-02-23 15:21:28,933 - school bell - INFO - Schedule started


Logs are handled via ``syslog``. Show all logs of today:

.. code-block:: sh

    journalctl -u school-bell --since=today


Licensing
=========

The source code for school-bell is licensed under MIT that can be found under the LICENSE file.

Pieter Smets © 2023. All rights reserved.
