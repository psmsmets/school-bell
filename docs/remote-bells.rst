Remote bells and webhooks
=========================

School Bell supports three different remote-control paths. Choose the smallest
one that matches the installation:

.. list-table::
   :header-rows: 1
   :widths: 36 64

   * - Feature
     - Purpose
   * - Top-level ``trigger``
     - Copy every scheduled signal to another Linux bell over SSH.
   * - ``manual_bell.remote_bells``
     - Start best-effort SSH commands or webhooks when the physical button is
       pressed.
   * - Top-level ``webhook``
     - Accept authenticated requests that ring this node locally.

Remote connectivity is optional. A failed remote action is logged but does not
make a correctly configured local bell dependent on a central service.

Prepare SSH access
------------------

SSH actions must work non-interactively as the School Bell service user. On
the sending Pi, create a dedicated key and copy its public key to the receiving
Pi:

.. code-block:: console

   $ ssh-keygen -t ed25519 -C school-bell -f /home/pi/.ssh/id_school_bell
   $ ssh-copy-id -i /home/pi/.ssh/id_school_bell.pub pi@pibell-yard.local

Protect the private key and do not commit it. A service cannot answer a key
passphrase prompt, so use a deliberately protected service key and restrict
the receiving account and network access appropriately.

Create ``/home/pi/.ssh/config`` on the sender:

.. code-block:: text

   Host pibell-yard
       HostName pibell-yard.local
       User pi
       IdentityFile /home/pi/.ssh/id_school_bell
       IdentitiesOnly yes
       PreferredAuthentications publickey

Connect once and verify the host identity before unattended operation:

.. code-block:: console

   $ ssh pibell-yard /usr/bin/aplay --help

Run this test as the same account used by ``school-bell.service``. It must
complete without asking for a password, passphrase or host confirmation.

.. warning::

   The current built-in SSH command disables strict host-key checking for
   compatibility with unattended installations. Register and verify the host
   yourself, restrict the dedicated key on the receiving Pi, and only use SSH
   triggering over a trusted management network. Host-key pinning should be
   added before treating an untrusted network as safe.

Mirror scheduled signals over SSH
---------------------------------

The legacy top-level ``trigger`` mapping sends every scheduled signal to each
listed host. Its value is the WAVE directory on that remote host:

.. code-block:: json

   {
     "trigger": {
       "pibell-yard": "/home/pi/samples"
     }
   }

The remote directory must contain the same WAVE filenames selected by the
local ``wav`` mapping, and ``/usr/bin/aplay`` must be available remotely. Test
every destination before adding it to a production schedule.

Remote actions from a physical button
-------------------------------------

``manual_bell.remote_bells`` can execute a specific SSH command or call an
HTTP(S) webhook when the physical input is accepted:

.. code-block:: json

   {
     "manual_bell": {
       "gpio": 17,
       "wav_key": "lesson",
       "remote_bells": [
         {
           "transport": "ssh",
           "host": "pibell-yard.local",
           "user": "pi",
           "command": ["/usr/local/bin/manual-bell"],
           "timeout": 10
         },
         {
           "transport": "webhook",
           "url": "https://remote-bell.example.com/bell",
           "auth": {
             "type": "bearer",
             "token": "replace-with-remote-token"
           },
           "timeout": 5
         }
       ]
     }
   }

These actions start in background threads and do not delay the local signal.
Their success or failure is reported as ``manual_remote_trigger``. A failed
remote action does not undo or change the local result.

Expose a bell webhook
---------------------

Enable the authenticated endpoint on the receiving node:

.. code-block:: json

   {
     "webhook": {
       "enabled": true,
       "host": "127.0.0.1",
       "port": 8081,
       "token": "replace-with-a-long-random-token",
       "rate_limit": 10,
       "rate_window": 60
     }
   }

The built-in server provides plain HTTP. Keep it on ``127.0.0.1`` and expose
it through a TLS reverse proxy such as nginx, Caddy or Apache. Configure
certificate validation, request-size limits and trusted-network access at the
proxy. Never expose the built-in port directly to an untrusted network.

Send exactly one configured WAVE key:

.. code-block:: console

   $ curl -X POST https://bell.example.com/bell \
       -H 'Authorization: Bearer replace-with-a-long-random-token' \
       -H 'Content-Type: application/json' \
       --data '{"wav_key":"lesson"}'

=================  ==========================================================
HTTP status        Meaning
=================  ==========================================================
``202``            The local signal was accepted.
``400``            The JSON or ``wav_key`` is invalid.
``401``            Bearer authentication failed.
``404``            The request path is not ``/bell``.
``405``            The endpoint only accepts ``POST``.
``409``            Another signal is already active.
``429``            The per-client rate limit was exceeded.
``503``            Local playback failed.
=================  ==========================================================

Responses contain keys and status information, never sample paths. Webhook
signals are manual overrides: they do not respect holiday or disable-calendar
suppression and they do not automatically invoke the legacy top-level SSH
``trigger`` destinations.

Verify and diagnose
-------------------

#. Run ``school-bell /home/pi/schema.json --check`` on every node.
#. Test local audio and GPIO before adding a remote path.
#. Test SSH as the systemd service user or test the webhook through its final
   TLS URL.
#. Trigger one bell while another signal is active and confirm the expected
   ``409`` or skipped event.
#. Inspect ``journalctl`` and the Graylog ``manual_remote_trigger``,
   ``remote_trigger`` or ``webhook_*`` events.

See :doc:`configuration-reference` for every field and :doc:`networking` for
firewall and outage behavior.
