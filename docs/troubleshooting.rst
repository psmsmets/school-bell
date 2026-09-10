Troubleshooting
===============

Start with these commands:

.. code-block:: console

   school-bell /home/pi/schema.json --check
   systemctl status school-bell.service
   journalctl -u school-bell.service -n 100 --no-pager
   timedatectl status

Configuration errors
--------------------

Pydantic reports the complete nested path of invalid fields. Correct every
reported error and rerun ``--check``. Unknown fields are rejected; do not remove
one without confirming whether it is a misspelling. ``config_hash`` and
``schedule_hash`` are generated values and must not appear in the JSON.

Service does not start
----------------------

Confirm that the systemd ``ExecStart`` path, configuration path and service
user match the installation. Check that the virtual environment uses Python
3.11 or newer:

.. code-block:: console

   /home/pi/.local/bin/python --version
   /home/pi/.local/bin/school-bell --version

Audio is silent
---------------

Verify the file and ALSA device outside School Bell, then use ``--test`` only
when activating the real output is safe:

.. code-block:: console

   aplay -l
   aplay -L
   aplay /home/pi/samples/bell.wav
   school-bell /home/pi/schema.json --test

See :doc:`ALSA` for device selection, mixers and multi-zone examples.

GPIO does not switch
--------------------

Check BCM pin numbering, relay polarity, power and service-user permissions.
Active-low relay boards require ``"buzz_active_high": false``. Never diagnose
relay wiring with a live high-voltage or bell circuit attached. The pin-number
explanation, Waveshare mapping and safe test sequence are in :doc:`GPIO`.

Bells ring at the wrong time
----------------------------

Check all three sources of time information:

.. code-block:: console

   date --iso-8601=seconds
   timedatectl status
   grep timezone /home/pi/schema.json

The system clock must be synchronized and ``timezone`` must match the intended
local schedule. See :doc:`networking` for behavior during NTP outages.

Monitoring is missing
---------------------

Local scheduling can be healthy even when monitoring is unavailable. Check DNS,
routing, firewall rules, syslog protocol and port, then inspect local journal
events. For HTTP status, verify the bind address and token as described in
:doc:`MONITORING`.

Remote trigger fails
--------------------

For SSH, test key authentication as the School Bell service user and confirm
the remote command. For webhooks, verify TLS at the reverse proxy, the bearer
token, request body and rate limit. A failed remote manual action should not
delay or change its local bell action.

Calendar data is unavailable
----------------------------

Run ``--check`` to test OpenHolidays and iCalendar parsing. Verify DNS, TLS,
proxy and firewall access. Calendar URLs may contain secrets and are therefore
redacted from normal errors; test them carefully without publishing them in
logs or issue reports.
