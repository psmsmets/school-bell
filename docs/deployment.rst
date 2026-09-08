Deployment
==========

The ``ansible`` directory contains playbooks for initializing, installing,
updating, configuring, backing up, restoring and restarting bell nodes. Ansible
is a deployment tool, not a runtime controller: nodes continue using their
local configuration when the controller is offline.

Playbook roles
--------------

``init.yml``
   Prepares the host, installs system packages and creates the Python virtual
   environment at ``/home/pi/.local`` by default.

``install.yml``
   Installs School Bell and the GPIO backend, copies samples and configuration,
   and installs the systemd unit.

``update.yml``
   Updates application code while verifying that the local configuration was
   preserved.

``configure.yml``
   Deploys an intentional configuration change.

``backup.yml`` and ``restore.yml``
   Back up and recover local service data.

``restart.yml``
   Restarts the service explicitly.

The detailed variables and commands remain in the `Ansible playbook guide`_.

.. _Ansible playbook guide: https://github.com/psmsmets/school-bell/blob/main/ansible/README.md

Recommended workflow
--------------------

#. Pin ``school_bell_version`` to a tested tag or commit.
#. Back up the target node.
#. Validate the candidate JSON in CI or on a staging node.
#. Deploy to one node first.
#. Run the installed executable with ``--check``.
#. Restart and verify local service health and monitoring.
#. Roll out to the remaining nodes.

Do not make normal ringing dependent on the Ansible controller. Schedules,
samples and executable code must be present locally before a node is considered
ready.

Python upgrades
---------------

School Bell 1.0 requires Python 3.11 or newer. Ansible creates its environment
with the target's ``/usr/bin/python3``. Verify that interpreter before running
``init.yml``. Because the current playbook preserves an existing
``/home/pi/.local`` environment, recreate it deliberately when the operating
system's Python changes incompatibly.

Configuration safety
--------------------

Install and update operations preserve an existing configuration unless forced
replacement was requested. Use ``configure.yml`` for intentional changes.
Treat calendar URLs, webhook tokens and remote credentials as secrets, restrict
file permissions and avoid printing them in CI logs.
