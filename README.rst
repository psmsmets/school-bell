School Bell
===========

|Maintenance yes| |MIT license| |made-with-python| |Workflow status|

.. |Maintenance yes| image:: https://img.shields.io/badge/Maintained%3F-yes-green.svg
.. |MIT license| image:: https://img.shields.io/badge/License-MIT-blue.svg
.. |made-with-python| image:: https://img.shields.io/badge/Made%20with-Python-1f425f.svg
.. |Workflow status| image:: https://github.com/psmsmets/school-bell/actions/workflows/tests.yml/badge.svg

School Bell schedules WAVE audio and optional GPIO relay outputs on Linux
devices such as Raspberry Pis. Each bell stores its configuration, schedule and
audio locally. Central deployment, monitoring and remote triggers are optional:
a correctly configured bell continues following its local schedule when its
connection to central services is unavailable.

Features
--------

* autonomous, timezone-aware local scheduling;
* WAVE playback through ALSA and optional GPIO relay outputs;
* public- and school-holiday suppression through OpenHolidays;
* optional iCalendar suppression periods;
* manual GPIO, SSH and authenticated webhook triggers;
* optional structured syslog and HTTP health monitoring;
* repeatable Raspberry Pi deployment with Ansible.

Requirements
------------

School Bell requires Python 3.11 or newer. Linux deployments require ALSA, and
GPIO deployments require supported Raspberry Pi hardware and an ``lgpio`` pin
factory. Accurate system time is essential; provide access to an online or
local NTP server.

Installation
------------

Install the latest release from GitHub in a virtual environment:

.. code-block:: console

   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install git+https://github.com/psmsmets/school-bell.git

For managed Raspberry Pi installations, use the included `Ansible playbooks`_.

.. _Ansible playbooks: ansible/README.md

Quick start
-----------

Create ``school-bell.json`` and place ``bell.wav`` in the same directory:

.. code-block:: json

   {
       "schedule": {
           "Mon": {"08:30": "0"},
           "Tue": {"08:30": "0"}
       },
       "wav": {
           "0": "bell.wav"
       },
       "root": ".",
       "timezone": "Europe/Brussels"
   }

Validate the configuration and local resources without activating outputs:

.. code-block:: console

   school-bell school-bell.json --check

Start the scheduler:

.. code-block:: console

   school-bell school-bell.json

Use ``school-bell --demo-config`` for a complete example and
``school-bell --help`` for all command-line options.

Documentation
-------------

The complete documentation is in `docs/index.rst`_ and covers architecture,
installation, configuration, deployment, networking, monitoring, audio and
troubleshooting. It can be built locally with Sphinx and does not depend on a
hosted documentation service.

.. _docs/index.rst: docs/index.rst

Development
-----------

Run the test suite from the repository root:

.. code-block:: console

   python -m pip install -e '.[test]'
   pytest

Build the documentation with warnings treated as errors:

.. code-block:: console

   python -m pip install -e '.[docs]'
   sphinx-build -W --keep-going docs docs/_build/html

License
-------

School Bell is licensed under the MIT License_.

.. _License: LICENSE
