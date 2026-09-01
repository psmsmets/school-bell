*************************************
School Bell
*************************************

|Maintenance yes| |MIT license| |made-with-python| |Workflow status|

.. |Maintenance yes| image:: https://img.shields.io/badge/Maintained%3F-yes-green.svg
.. |MIT license| image:: https://img.shields.io/badge/License-MIT-blue.svg
.. |made-with-python| image:: https://img.shields.io/badge/Made%20with-Python-1f425f.svg
.. |Workflow status| image:: https://github.com/psmsmets/school-bell/actions/workflows/tests.yml/badge.svg

Python-scheduled ringing of a school bell. 

A Python-wrapper to the `OpenHolidays API`_ is used to 
optionally disable ringing on public and school holidays. 
Check the `Live Status`_ of the online service.

.. _OpenHolidays API: https://www.openholidaysapi.org/en/api/
.. _Live Status: https://openpotato.github.io/uptime/


Setup
=====

See the guide_ how to configure a Raspberry Pi and Python 3.13 virtual environment from scratch.
For managed Raspberry Pi deployments, see the `Ansible playbook guide`_. It
documents how application installs and updates preserve an existing
``schema.json``, and how to deploy a schedule intentionally.

.. _guide: docs/GUIDE.rst
.. _Ansible playbook guide: ansible/README.md

Install the Python package using ``pip``.

.. code-block:: bash

    pip install git+https://github.com/psmsmets/school-bell.git


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
      -b [..], --buzz [..]  Buzz via RPi GPIO while the WAVE audio file plays
                            (default: False)
      -p [..], --play [..]  Play a WAVE audio file by specifying the key from the
                            JSON configuration and exit (default: False)
      --debug               Make the operation a lot more talkative
      --demo-config         Print the demo JSON configuration and exit
      --demo-service        Print the demo systemctl service for the current user and exit
      --test                Test each configured GPIO pin and play one second of
                            each WAVE audio file at startup (default: False)
      --check               Validate configuration, files and external services
                            without starting the scheduler or activating bells
      --update [..]         Update school-bell from git. Optionally set the branch (default: main)
      --version             Print the version and exit


Testing
-------

Run the complete test suite from the repository root. Pytest imports
``school_bell`` directly from the local ``src`` directory, so an editable
installation is not required. External HTTP services are mocked and the suite
can run without internet access.

.. code-block:: sh

    pytest


Configuration (JSON)
====================

Configuration file
------------------

Pass the JSON configuration as a string or as the path to a file such as
``schema.json``. Run ``school-bell --demo-config`` to print a complete example.
The following configuration shows the main scheduling and audio settings:

.. code-block:: JSON

    {
        "timezone": "Europe/Brussels",
        "schedule": {
            "Mon": {"08:30": 0, "12:00": 0, "15:00": 0},
            "Tue": {"08:30": 0, "12:00": 0, "15:00": 0},
            "Wed": {"08:30": 0, "12:00": 0},
            "Thu": {"08:30": 0, "12:00": 0, "15:00": 0},
            "Fri": {"08:30": 0, "12:00": 0, "15:00": 0}
        },
        "trigger": {
            "pibell2": "${HOME}/samples"
        },
        "wav": {
            "0": "SchoolBell-SoundBible.com-449398625.wav",
            "1": "ClassBell-SoundBible.com-1426436341.wav"
        },
        "root": "${HOME}/samples",
        "device": "Headphones",
        "holidays": "BE-NL",
        "disable_calendar": "https://example.com/public-calendar.ics",
        "timeout": 10
    }

Schedule and audio
------------------

The main settings are:

====================  ========================================================
Setting               Purpose
====================  ========================================================
``schedule``          Maps weekdays and local times to keys from ``wav``.
``wav``               Maps sample keys to WAVE filenames.
``root``              Base directory for local WAVE files.
``device``            Optional ALSA playback device.
``timezone``          Timezone used to evaluate the schedule.
``timeout``           Timeout in seconds for network and SSH operations.
``disable_calendar``  Optional public iCalendar URL with periods during which
                      bells are disabled.
====================  ========================================================

GPIO relays
-----------

The optional ``buzz_gpio`` setting activates a relay while the bell audio is
playing. It accepts a single GPIO pin for backwards compatibility, or a list
of GPIO pins to switch multiple relays simultaneously:

.. code-block:: JSON

    {"buzz_gpio": 17}

.. code-block:: JSON

    {
        "buzz_gpio": [26, 20, 21],
        "buzz_active_high": false
    }

These are the BCM GPIO numbers for channels 1, 2 and 3 of the
`Waveshare RPi Relay Board`_. The corresponding labels printed on the board
are P25, P28 and P29; those labels use wiringPi numbering rather than BCM
numbering. See `Raspberry Pi GPIO Pinout`_ for an overview of the physical and
BCM pin numbering.

The Waveshare board uses active-low relay inputs, so set
``buzz_active_high`` to ``false``. School Bell then drives the GPIO high while
idle and low only while ringing. Other relay boards can retain the default
``true`` value when they use active-high inputs. Outputs are initialized and
returned to their logical inactive state.

For fail-safe wiring, connect the bell circuit through the relay's ``COM`` and
``NO`` (normally open) contacts. Software polarity cannot prevent ringing on
power loss when the circuit uses the normally closed contact or when external
hardware pulls an unpowered input into its active state. Verify the actual
contacts with the bell disconnected before deployment.

.. _Waveshare RPi Relay Board: https://www.waveshare.com/wiki/RPi_Relay_Board
.. _Raspberry Pi GPIO Pinout: https://pinout.xyz/

Testing GPIO and audio
----------------------

Run with ``--test`` to activate each configured ``buzz_gpio`` output
sequentially for one second. Every output is returned to its inactive state
before the next pin is tested. The configured WAVE samples are tested as well.

.. code-block:: sh

    school-bell schema.json --test

Non-destructive health check
----------------------------

Use ``--check`` for automated, remote, or pre-deployment validation:

.. code-block:: sh

    school-bell schema.json --check

The command validates the complete active configuration and confirms that all
configured WAVE files exist. If ``holidays`` is configured, it retrieves and
parses the OpenHolidays response and reports the number of holidays returned.
If ``disable_calendar`` is configured, it downloads and parses the iCalendar
document. Network requests use the configured ``timeout`` and are not retried
indefinitely. Calendar URLs are never included in command output or logs,
because these URLs often contain credentials or access tokens.

Each applicable result is labelled ``OK``, ``WARNING``, ``ERROR``, or
``NOT CONFIGURED``. Exit status 0 means every required check succeeded; a
non-zero status means the configuration, a local resource, or an external
service could not be validated.

Unlike ``--test``, ``--check`` never plays audio, changes a GPIO output,
contacts remote bells, starts monitoring listeners, or starts/registers the
scheduler. ``--test`` remains the explicit hardware-oriented test and may ring
outputs and play samples.

Manual bell button
------------------

One optional physical push button can trigger a configured WAVE sample:

.. code-block:: JSON

    {
        "manual_bell": {
            "gpio": 17,
            "wav_key": "0",
            "mode": "once",
            "pull": "up",
            "bounce_time": 0.05
        }
    }

``mode`` is either ``once`` (finish the complete sample after a press) or
``hold`` (stop when the button is released, with the sample duration as the
maximum). ``pull`` accepts ``up``, ``down`` or ``floating`` and
``bounce_time`` is the debounce interval in seconds. The input GPIO must not
also be configured as a ``buzz_gpio`` relay output.

Manual signals are deliberate local overrides and are therefore not blocked
by the holiday or disable calendars. Only one bell signal can be active at a
time; concurrent scheduled or manual requests are ignored and logged. The
same internal trigger coordinator can be used by future control interfaces
without bypassing this exclusivity rule.

Holiday calendar
----------------

The optional ``holidays`` setting accepts an `OpenHolidays group code`_.
For example, ``BE-NL`` selects the Dutch-language school-holiday group in
Belgium. When configured, ringing is disabled during public and school
holidays returned for that group.

.. _OpenHolidays group code: https://www.openholidaysapi.org/en/api/

Public disable calendar
-----------------------

The optional ``disable_calendar`` setting accepts a public iCalendar
(``.ics``) URL published by services such as Google Calendar or Outlook:

.. code-block:: JSON

    {
        "timezone": "Europe/Brussels",
        "disable_calendar": "https://example.com/public-calendar.ics"
    }

Every non-cancelled calendar event disables scheduled bells during its
effective period. An all-day event disables the complete local day. Timed
events disable only bells whose scheduled time falls within the event, and
events may span several hours or days. Recurring events, excluded dates and
modified or cancelled occurrences are respected. Event end times are
exclusive, as defined by iCalendar.

The calendar is downloaded when School Bell starts and refreshed every day.
After a failed refresh, the last successfully parsed in-memory calendar is
kept. If no successful download is available, School Bell logs a warning and
continues ringing normally. The published URL is never included in logs
because it may contain a private access token.

To obtain a URL, publish or share the calendar from the calendar provider and
copy its public iCalendar/ICS link. In Google Calendar this is the public or
secret iCal address under *Integrate calendar*. In Outlook, publish the
calendar and copy the generated ICS link. Anyone who obtains such a URL may
be able to read the published calendar, so restrict event details and sharing
permissions appropriately. See the provider instructions for `Google
Calendar sharing`_ and `Outlook calendar publishing`_.

The ``disable_calendar`` check complements ``holidays``: either a returned
holiday or a matching calendar event is sufficient to skip the bell. Omit
``disable_calendar`` or set it to an empty string to disable this feature.

.. _Google Calendar sharing: https://support.google.com/calendar/answer/37083
.. _Outlook calendar publishing: https://support.microsoft.com/office/share-your-calendar-in-outlook-on-the-web-7ecef8ae-139c-40d9-bae2-a23977ee58d5

Remote triggers
---------------

The ``trigger`` setting maps remote SSH hosts to their WAVE root directory.
A remote trigger requires an SSH key to connect to the remote host.

Generate a new SSH key named ``school-bell`` in
``${HOME}/.ssh/id_school_bell`` and upload it to the Raspberry Pi with hostname
``pibell2``:

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

Monitoring
----------

School Bell can forward structured events from multiple Raspberry Pis to a
central syslog or Graylog server and expose optional ``/status`` and ``/health``
HTTP endpoints. See the `monitoring guide`_.

.. _monitoring guide: monitoring/README.md


Systemd service
===============

Create a systemd service of the school-bell. An example service is given by the command ``school-bell --demo-service`` for the current user with the configuration in ``${HOME}/school-bell.json``. The service can be modified if needed.

.. code-block:: sh

    school-bell --demo-service | sudo tee /etc/systemd/system/school-bell.service
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

The source code for school-bell is open-source and licensed under MIT_.

.. _MIT: https://raw.githubusercontent.com/psmsmets/school-bell/main/LICENSE

Pieter Smets © 2022 - 2026. All rights reserved.
