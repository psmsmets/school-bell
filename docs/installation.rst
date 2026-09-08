Installation
============

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

Manual installation
-------------------

Install the operating-system packages:

.. code-block:: console

   sudo apt update
   sudo apt install -y alsa-utils python3 python3-pip python3-venv

Verify the Python version before creating the environment:

.. code-block:: console

   python3 --version

Create an isolated environment and install School Bell:

.. code-block:: console

   python3 -m venv /home/pi/.local
   /home/pi/.local/bin/python -m pip install --upgrade pip
   /home/pi/.local/bin/python -m pip install \
       git+https://github.com/psmsmets/school-bell.git

The included Ansible setup uses the same ``/home/pi/.local`` environment by
default. The ``py3`` prompt configured by Ansible is only a shell prompt label;
it is not part of the path.

Initial verification
--------------------

Check the executable and configuration before starting a service:

.. code-block:: console

   /home/pi/.local/bin/school-bell --version
   /home/pi/.local/bin/school-bell /home/pi/schema.json --check

``--check`` validates configuration, WAVE files and configured external
calendar services without playing audio, changing GPIO outputs, opening HTTP
listeners or starting the scheduler.

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

Upgrading
---------

Validate the existing configuration against the new release before restarting.
Back up the configuration and retain a known working package version so the
deployment can be rolled back. Python virtual environments are tied to their
interpreter; recreate an environment after a major Python upgrade instead of
assuming an old one remains usable.
