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

On a trusted local network, prefer a stable local IP address such as
``http://192.168.1.25:8081/bell`` when hostname or mDNS resolution adds
noticeable latency. A hostname is more readable and easier to renumber, but it
depends on reliable local name resolution. Using an IP address avoids that
lookup; it does not compensate for a slow HTTP response from the receiving
service.

.. _expose-bell-webhook:

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

Manual HTTPS with Caddy's local CA
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Caddy can provide HTTPS without a public domain or internet-facing service. It
creates a local certificate authority (CA), issues and renews the server
certificate, and proxies requests to School Bell over loopback. Install Caddy
using the `official installation instructions`_, then create or extend
``/etc/caddy/Caddyfile`` on the receiving node:

.. code-block:: text

   pibell-yard.school-bell.internal {
       tls internal
       request_body {
           max_size 4KB
       }
       reverse_proxy 127.0.0.1:8081
   }

Use a hostname that resolves to the receiving node from every sending node.
Create an A record in the internal DNS, for example
``pibell-yard.school-bell.internal`` pointing to the node's fixed DHCP address.
Do not create a CNAME whose target is an IP address. Avoid ``.local`` because
it is reserved for mDNS. A controlled ``/etc/hosts`` entry can be used as a
fallback, but internal DNS is preferable. The hostname in the webhook URL must
match the hostname in the Caddyfile.

Install DNS client tools when ``dig`` is not already available:

.. code-block:: console

   $ sudo apt install bind9-dnsutils
   $ dig +noall +answer pibell-yard.school-bell.internal A
   $ getent ahostsv4 pibell-yard.school-bell.internal

The answer must be an A record containing the fixed IPv4 address. If multiple
DNS servers are supplied through DHCP, every one of them must return the same
private record. Do not advertise a public resolver as a fallback for private
names.

Validate and load the configuration:

.. code-block:: console

   $ sudo caddy validate --config /etc/caddy/Caddyfile
   $ sudo systemctl reload caddy

When Caddy runs as a systemd service, its local root certificate is normally
stored at:

.. code-block:: text

   /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt

Install a copy of this *public* root certificate in the trust store of every
sending node. Do not copy any private key from Caddy's data directory. On a
Debian or Raspberry Pi OS sender, copy the certificate securely to the node and
run:

.. code-block:: console

   $ sudo install -m 0644 root.crt \
       /usr/local/share/ca-certificates/school-bell-caddy.crt
   $ sudo update-ca-certificates

Compare ``openssl x509 -noout -fingerprint -sha256`` output before and after
copying the root certificate. This verifies that the expected trust anchor is
being installed.

Python ``requests`` in the School Bell virtual environment may use its own CA
bundle instead of the operating-system store used by ``curl``. If ``curl``
succeeds but a remote bell reports ``SSLError``, add a systemd drop-in on the
sending node:

.. code-block:: console

   $ sudo systemctl edit school-bell

.. code-block:: ini

   [Service]
   Environment="REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt"

Then reload systemd and restart School Bell:

.. code-block:: console

   $ sudo systemctl daemon-reload
   $ sudo systemctl restart school-bell

The bearer token remains required after enabling HTTPS. Test the complete path
from a sending node, without disabling certificate verification:

.. code-block:: console

   $ curl -X POST https://pibell-yard.school-bell.internal/bell \
       -H 'Authorization: Bearer replace-with-a-long-random-token' \
       -H 'Content-Type: application/json' \
       --data '{"wav_key":"lesson"}'

Keep Caddy's data directory persistent because it contains the local CA. Back
up and protect it like other private key material. All proxied requests reach
the built-in rate limiter from the loopback address, so its limit is shared by
all clients using this proxy. The external URL uses the default HTTPS port 443;
do not retain the backend ``:8081`` port when changing a remote URL from HTTP
to HTTPS.

Automate Caddy with Ansible
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The optional ``ansible/caddy.yml`` playbook installs Caddy and DNS diagnostic
tools, deploys a host-specific certificate and key, installs the public CA in
the operating-system trust store, configures the School Bell systemd service
to use that store, and performs DNS, TLS and Python ``requests`` checks. HTTPS
is not enabled by ``init.yml`` or ``install.yml``.

For managed deployments, issue every node a separate certificate from one
controlled internal CA. Keep the CA private key outside the repository and off
the bell nodes. Supply only the public CA certificate and each node's own leaf
certificate and private key to the playbook. See :doc:`deployment` for the
inventory variables and rollout command. This differs deliberately from the
manual ``tls internal`` example: the manual procedure lets one Caddy instance
own its local CA, while the managed procedure uses centrally issued
certificates so no CA private key is distributed to bell nodes.

Send exactly one configured WAVE key:

.. code-block:: console

   $ curl -X POST https://bell.example.com/bell \
       -H 'Authorization: Bearer replace-with-a-long-random-token' \
       -H 'Content-Type: application/json' \
       --data '{"wav_key":"lesson"}'

=================  ==========================================================
HTTP status        Meaning
=================  ==========================================================
``202``            The local signal was accepted for background execution.
``400``            The JSON or ``wav_key`` is invalid.
``401``            Bearer authentication failed.
``404``            The request path is not ``/bell``.
``405``            The endpoint only accepts ``POST``.
``409``            Another signal is already active.
``429``            The per-client rate limit was exceeded.
``503``            Background execution could not be started.
=================  ==========================================================

Responses contain keys and status information, never sample paths. Webhook
signals return ``202`` immediately after atomic acceptance; playback completion
or failure is reported through the ``webhook_bell_*`` monitoring events. They
are manual overrides: they do not respect holiday or disable-calendar
suppression and they do not automatically invoke the legacy top-level SSH
``trigger`` destinations.

Verify and diagnose
-------------------

#. Run ``school-bell /home/pi/schema.json --check`` on every node. This checks
   remote configuration structure, but deliberately makes no remote SSH or
   webhook connection.
#. Test local audio and GPIO before adding a remote path.
#. Test SSH as the systemd service user or test the webhook through its final
   TLS URL.
#. If ``curl`` succeeds but the service reports ``SSLError``, inspect
   ``REQUESTS_CA_BUNDLE`` in ``systemctl show school-bell``.
#. Trigger one bell while another signal is active and confirm the expected
   ``409`` or skipped event.
#. Inspect ``journalctl`` and the Graylog ``manual_remote_trigger``,
   ``remote_trigger`` or ``webhook_*`` events.

See :doc:`configuration-reference` for every field and :doc:`networking` for
firewall and outage behavior.

.. _official installation instructions: https://caddyserver.com/docs/install
