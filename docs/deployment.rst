Deploying with Ansible
======================

Ansible lets one administrator prepare and maintain several bell nodes from a
controller computer. The controller connects to each Raspberry Pi over SSH and
runs the supplied playbooks. It is **not** a central runtime service: after
deployment, every bell keeps its program, sounds, configuration and schedule
locally.

When Ansible is useful
----------------------

For one experimental bell, the manual installation is easy to follow. Ansible
becomes useful when the same safe process must be repeated, when versions must
be pinned, or when configurations need backups and controlled rollout.

Terminology used below:

``controller``
   The administrator's Linux or macOS computer where Ansible and this
   repository are installed.

``managed node``
   A Raspberry Pi running School Bell.

``inventory``
   A text file listing nodes and connection details.

``playbook``
   A supplied YAML procedure such as ``install.yml`` or ``backup.yml``.

Prerequisites
-------------

Each Pi must already have Raspberry Pi OS, Python 3.11 or newer, network
connectivity, SSH access and a user that can use ``sudo``. From the controller,
SSH should work without an interactive host-key or password question during a
playbook run. Use SSH keys and protect the private key.

On the controller, install Git and Ansible, then obtain the project:

.. code-block:: console

   git clone https://github.com/psmsmets/school-bell.git
   cd school-bell
   ansible --version

Create an inventory
-------------------

Create a file named ``inventory`` on the controller:

.. code-block:: ini

   [school_bells]
   pibell-main ansible_host=192.0.2.41 ansible_user=pi
   pibell-yard ansible_host=192.0.2.42 ansible_user=pi

   [school_bells:vars]
   ansible_ssh_private_key_file=~/.ssh/id_example
   ansible_ssh_common_args='-o PreferredAuthentications=publickey'

Test both SSH and privilege escalation before changing anything:

.. code-block:: console

   ansible -i inventory school_bells -m ping
   ansible -i inventory school_bells -b -m command -a 'python3 --version'

If sudo needs a password, add ``--ask-become-pass`` to Ansible commands. Keep
passwords and tokens in Ansible Vault or another secrets system, not in a
committed inventory.

First installation
------------------

The initial setup is deliberately split into two runs:

.. code-block:: console

   ansible-playbook -i inventory ansible/init.yml --limit pibell-main
   ansible-playbook -i inventory ansible/install.yml --limit pibell-main \
     -e school_bell_version=YOUR_TESTED_TAG_OR_COMMIT

``init.yml`` updates Raspberry Pi OS, installs build and Python packages,
expands the filesystem, creates ``/home/pi/.local`` as a virtual environment
and reboots. ``install.yml`` installs the requested School Bell revision and
GPIO backend, copies the sample sounds, installs a configuration when none
exists, and enables the systemd service.

Start with one node. Verify audio, GPIO, schedule, reboot behavior and logs
before changing ``--limit`` to the entire ``school_bells`` group. Replace the
example tag above with the release, branch or exact commit you have tested. An
exact commit gives the most reproducible test deployment.

Device-specific configuration
-----------------------------

Store each candidate JSON file on the controller, for example
``configs/pibell-main.json``. Check its JSON structure and then deploy it
explicitly:

.. code-block:: console

   python -m json.tool configs/pibell-main.json >/dev/null
   ansible-playbook -i inventory ansible/configure.yml \
     --limit pibell-main \
     -e school_bell_config_src="$PWD/configs/pibell-main.json"

``configure.yml`` requires a source file, checks that it is a JSON object,
keeps Ansible's timestamped backup beside the previous remote file and only
restarts the service when the content changes. Always use ``--limit`` for a
device-specific schedule so it cannot accidentally reach every school bell.

The playbook's controller-side check is intentionally basic. Use the generated
:doc:`schema` for complete model validation before deployment. A full
``school-bell ... --check`` also expects the configured local WAVE files and
network integrations, so run it on the node after copying the candidate—or on
a staging environment that mirrors those resources—before the production
restart window.

Updating code without changing schedules
----------------------------------------

Use ``update.yml`` to install another application revision:

.. code-block:: console

   ansible-playbook -i inventory ansible/update.yml \
     --limit pibell-yard \
     -e school_bell_version=YOUR_TESTED_TAG_OR_COMMIT

If ``pibell-yard`` is configured as a host in ``~/.ssh/config``, it can also be
updated without an inventory file. The trailing comma makes it an inline host
list:

.. code-block:: console

   ansible-playbook -i pibell-yard, ansible/update.yml \
     -e school_bell_version=YOUR_TESTED_TAG_OR_COMMIT

The playbook records the SHA-256 checksum of ``schema.json`` before updating
and refuses the restart if that configuration changed. It never uploads a demo
or controller-side configuration. This separates a software update from a
schedule change.

``install.yml`` also preserves an existing configuration by default. Forced
replacement is available for deliberate reinstallations, but regular schedule
changes should use ``configure.yml`` because its intent is clearer.

Optional HTTPS webhooks
-----------------------

HTTPS is deliberately separate from the normal installation. First configure
internal DNS A records and enable the built-in webhook on ``127.0.0.1``. Issue
one certificate per hostname from a controlled internal CA. Store the CA
private key outside the repository and never copy it to a bell node.

Add the HTTPS hostname to the inventory and set controller-side certificate
paths in encrypted host variables:

.. code-block:: ini

   [school_bells]
   pibell-main ansible_host=192.0.2.41 caddy_hostname=pibell-main.school-bell.internal
   pibell-yard ansible_host=192.0.2.42 caddy_hostname=pibell-yard.school-bell.internal

.. code-block:: yaml

   # host_vars/pibell-yard.yml
   school_bell_caddy_ca_cert_src: /secure/pki/root.crt
   school_bell_caddy_cert_src: /secure/pki/pibell-yard-fullchain.crt
   school_bell_caddy_key_src: /secure/pki/pibell-yard.key

If internal DNS is unavailable, an optional fallback can be placed in host
variables:

.. code-block:: yaml

   school_bell_caddy_hosts:
     - address: 192.0.2.41
       hostname: pibell-main.school-bell.internal
     - address: 192.0.2.42
       hostname: pibell-yard.school-bell.internal

This maintains a marked ``/etc/hosts`` block and also updates the Debian
cloud-init hosts template when present. Leave the list empty when internal DNS
is reliable.

The certificate must include ``caddy_hostname`` as a DNS subject alternative
name. When an intermediate CA signed it, the certificate source must contain
the leaf followed by its intermediate chain. Protect inventory and leaf keys
with appropriate controller permissions; Ansible copies each key as
``root:caddy`` with mode ``0640``.

Roll out one node first:

.. code-block:: console

   ansible-playbook -i inventory ansible/caddy.yml --limit pibell-yard

The playbook refuses to continue unless the School Bell configuration already
enables the webhook on loopback. It installs the official Caddy repository,
Caddy, ``bind9-dnsutils``, the host certificate and the public CA. It also adds
``REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt`` as a systemd drop-in
because Python ``requests`` may not otherwise use locally installed roots.

Verification resolves the configured hostname, checks the certificate name,
confirms that systemd loaded the CA bundle setting, expects a safe ``405``
response from ``GET /bell``, and repeats that request with the same virtual
environment and service account used by School Bell. The playbook never sends
``POST /bell`` and therefore does not ring a bell.

Configure remote webhook URLs without the backend port:

.. code-block:: text

   https://pibell-yard.school-bell.internal/bell

See :ref:`expose-bell-webhook` for the manual procedure and troubleshooting.

Backup and restore
------------------

Download every selected node's configuration to the controller:

.. code-block:: console

   ansible-playbook -i inventory ansible/backup.yml --limit school_bells

Backups are grouped under
``backups/<UTC-timestamp>/<inventory-hostname>/schema.json``. Add
``-e school_bell_backup_samples=true`` to include the local ``samples`` folder.
The playbook does not modify managed nodes and refuses to overwrite an existing
backup directory.

Restore is guarded because it changes live nodes. It requires a timestamp, an
explicit target other than ``all`` and confirmation:

.. code-block:: console

   ansible-playbook -i inventory ansible/restore.yml \
     --limit pibell-main \
     -e school_bell_backup_timestamp=20260831T120000Z \
     -e school_bell_restore_confirm=true

Configuration is restored by default. To restore samples too, add
``-e school_bell_restore_samples=true``. To restore only samples, additionally
set ``-e school_bell_restore_config=false``. The playbook validates that the
requested backup material exists before changing the node.

Playbook overview
-----------------

=================  ==========================================================
Playbook           Purpose
=================  ==========================================================
``init.yml``       One-time OS preparation, virtual environment and reboot.
``install.yml``    Install code, samples, service and an initial configuration.
``configure.yml``  Intentionally replace a configuration and restart on change.
``update.yml``     Update code while proving the configuration was preserved.
``backup.yml``     Download configuration and optionally samples.
``restore.yml``    Guarded restore of configuration and/or samples.
``restart.yml``    Explicitly restart and enable the systemd service.
``caddy.yml``      Optionally deploy and verify HTTPS webhook termination.
=================  ==========================================================

Common variables
----------------

``school_bell_user``
   Service account; default ``pi``. Its home and primary group are discovered
   on the node.

``school_bell_repository``
   Git repository URL; defaults to the official School Bell repository.

``school_bell_version``
   Branch, tag or commit to install; default ``main``. Pin a tested tag or
   commit for production.

``school_bell_config_src``
   Controller-side JSON file. ``configure.yml`` requires it; a fresh install
   otherwise uses ``ansible/files/schema.json``.

``school_bell_config_name``
   Filename in the service user's home; default ``schema.json``.

``school_bell_force_reinstall``
   Default ``false``. With ``install.yml``, explicitly permits replacement and
   backup of an existing configuration. Prefer ``configure.yml`` for normal
   changes.

``school_bell_debug`` and ``school_bell_test``
   Default ``false``. Add the corresponding startup flags to the systemd unit.
   ``school_bell_test`` activates real outputs at startup and should not remain
   enabled on a live installation.

The repository's `Ansible playbook guide`_ contains additional command variants
and the exact safety behavior implemented by each playbook.

.. _Ansible playbook guide: https://github.com/psmsmets/school-bell/blob/main/ansible/README.md

Verify a deployment
-------------------

After each rollout, check at least one node directly:

.. code-block:: console

   ssh pi@pibell-main
   /home/pi/.local/bin/school-bell /home/pi/schema.json --check
   systemctl status school-bell.service
   journalctl -u school-bell.service -n 100 --no-pager

Also verify the expected version and fresh heartbeat in Graylog when monitoring
is configured. Deployment success alone does not prove that an amplifier,
speaker, relay or clock is working.
