Installation
============

This chapter takes a new bell from an empty Raspberry Pi to a locally tested
School Bell service. You need basic command-line access, but no Python
programming knowledge. For several bells, first complete one node and then use
:doc:`deployment` to repeat the installation with Ansible.

Requirements
------------

School Bell requires Python 3.11 or newer. A typical Raspberry Pi deployment
also needs:

* Raspberry Pi OS or another supported Linux distribution;
* ALSA and ``aplay`` for WAVE playback;
* an ``lgpio``-compatible GPIO backend when GPIO is configured;
* network access during installation;
* online or local NTP for reliable clock synchronization.

Reference hardware
------------------

The reference platform for School Bell 1.0 is a Raspberry Pi 3B+ with 1 GB of
memory running the 64-bit edition of Raspberry Pi OS Lite. This is the
recommended setup for new installations. The Lite edition is sufficient for a
bell node; a desktop environment is not needed for normal operation. More
powerful hardware is generally unnecessary, so a modest model keeps hardware
and energy costs down.

School Bell is lightweight and is also known to run on older Raspberry Pi
models with 512 MB of memory. Other models are expected to work when they
provide Python 3.11 or newer, ALSA and the required GPIO interfaces, but they
are not part of a formal compatibility matrix. Raspberry Pi Zero models still
require more extensive testing and should therefore be treated as unverified
for production deployments.

Before you begin
----------------

Prepare the following:

* a Raspberry Pi, microSD card, power supply and wired or wireless network;
* an audio output or USB sound card, amplifier and speaker for the first test;
* Raspberry Pi OS Lite 64-bit written with Raspberry Pi Imager;
* a hostname, user account and SSH access configured in Raspberry Pi Imager;
* one short PCM WAVE file;
* the intended timezone and bell times.

Do the first test with a speaker at a safe volume. Do not connect mains voltage,
an existing school bell circuit or an amplifier's high-power output directly to
a Raspberry Pi GPIO pin. Use a correctly rated and electrically isolated relay
interface, installed by someone qualified for the circuit involved.

Prepare Raspberry Pi OS
-----------------------

Boot the Pi, connect over SSH and confirm its clock, OS and Python version:

.. code-block:: console

   ssh pi@pibell.local
   timedatectl status
   python3 --version

School Bell requires Python 3.11 or newer. Apply available operating-system
updates before installing it:

.. code-block:: console

   sudo apt update
   sudo apt full-upgrade -y
   sudo reboot

Reconnect after the reboot. Ensure NTP reports a synchronized clock before
relying on a schedule; see :doc:`networking` for local NTP and outage behavior.

Install one bell manually
-------------------------

Install the operating-system packages:

.. code-block:: console

   sudo apt update
   sudo apt install -y alsa-utils git python3 python3-pip python3-venv

Verify the Python version before creating the environment:

.. code-block:: console

   python3 --version

Clone the project, create an isolated environment and install School Bell:

.. code-block:: console

   git clone https://github.com/psmsmets/school-bell.git
   cd school-bell
   git checkout YOUR_TESTED_TAG_OR_COMMIT
   python3 -m venv /home/pi/.local
   /home/pi/.local/bin/python -m pip install --upgrade pip
   /home/pi/.local/bin/python -m pip install .

Replace ``YOUR_TESTED_TAG_OR_COMMIT`` with a release tag or exact commit that
you have tested. Do not follow a changing branch for a production bell.

The included Ansible setup uses the same ``/home/pi/.local`` environment by
default. The ``py3`` prompt configured by Ansible is only a shell prompt label;
it is not part of the path.

Prepare audio and configuration
-------------------------------

Copy the included test sounds and generate an editable example:

.. code-block:: console

   mkdir -p /home/pi/samples
   cp samples/*.wav /home/pi/samples/
   /home/pi/.local/bin/school-bell --demo-config > /home/pi/schema.json

Open ``/home/pi/schema.json`` in an editor. At minimum, review ``schedule``,
``wav``, ``root`` and ``timezone``. The generated example uses
``${HOME}/samples`` and the included audio files. It also demonstrates optional
remote bells, webhooks and internet calendars with placeholder addresses and
tokens; remove those sections for the first local test. See
:doc:`configuration` for the concepts and :doc:`configuration-reference` for
every available option.

Test the sound outside School Bell first:

.. code-block:: console

   aplay /home/pi/samples/SchoolBell-SoundBible.com-449398625.wav

If no sound is heard, solve that before continuing. :doc:`ALSA` explains device
selection, volume, USB sound cards and multiple audio zones.

Initial verification
--------------------

Check the executable and configuration before starting a service:

.. code-block:: console

   /home/pi/.local/bin/school-bell --version
   /home/pi/.local/bin/school-bell /home/pi/schema.json --check

``--check`` validates configuration, WAVE files and configured external
calendar services without playing audio, changing GPIO outputs, opening HTTP
listeners or starting the scheduler.

When the check succeeds, test one configured WAVE key without waiting for its
scheduled time:

.. code-block:: console

   /home/pi/.local/bin/school-bell /home/pi/schema.json --play 0

Only after audio works should you test GPIO with ``--test``. That flag plays a
short part of every configured sound and activates configured outputs, so
disconnect the real bell circuit until the test behavior is understood. See
:doc:`GPIO` for BCM pin numbering, supported relay polarity, the Waveshare
board pin mapping, button wiring and a safe commissioning procedure.

Systemd
-------

Generate a basic unit for the current user:

.. code-block:: console

   school-bell --demo-service | \
       sudo tee /etc/systemd/system/school-bell.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now school-bell.service

For production deployments, prefer the Ansible-generated unit described in
:doc:`deployment`. It sets the virtual-environment path and GPIO backend
explicitly.

Verify unattended operation
----------------------------

After installing the service, use:

.. code-block:: console

   systemctl status school-bell.service
   journalctl -u school-bell.service -n 100 --no-pager

Temporarily add a schedule entry a few minutes ahead, validate the file and
restart the service. Confirm the sound and any relay output, then restore the
real schedule. Finally reboot the Pi and verify that the service starts again.
Also test with central services disconnected: an already configured bell must
continue using its local schedule.

What to do next
---------------

* Configure the full schedule using :doc:`configuration`.
* Configure and test the selected audio output using :doc:`ALSA`.
* Connect and test relay outputs and a manual button using :doc:`GPIO`.
* Configure holiday and event exceptions using :doc:`calendars`.
* Connect bells safely using :doc:`remote-bells` when required.
* Read :doc:`networking` before placing the node on a restricted network.
* Use :doc:`deployment` to manage several nodes consistently.
* Add :doc:`MONITORING` only after local autonomous ringing works.

Upgrading
---------

Validate the existing configuration against the new release before restarting.
Back up the configuration and retain a known working package version so the
deployment can be rolled back. Python virtual environments are tied to their
interpreter; recreate an environment after a major Python upgrade instead of
assuming an old one remains usable.
