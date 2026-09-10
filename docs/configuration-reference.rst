Configuration reference
=======================

This page lists every value accepted in the JSON configuration. Only
``schedule`` and ``wav`` are required. All objects reject unknown fields, so a
misspelled name produces a validation error instead of being silently ignored.

Complete example
----------------

The example deliberately includes every optional section. Replace addresses,
GPIO pins, credentials and filenames for the installation. Secrets shown here
are placeholders.

.. code-block:: json

   {
       "schedule": {
           "Mon": {"08:30": "lesson", "12:00": "break"},
           "Tue": {"08:30": "lesson"}
       },
       "wav": {
           "lesson": "school-bell.wav",
           "break": "break-bell.wav"
       },
       "root": "/home/pi/samples",
       "device": "plughw:CARD=Device,DEV=0",
       "buzz_gpio": [20, 26],
       "buzz_active_high": true,
       "timeout": 10,
       "holidays": "BE-NL",
       "trigger": {
           "pibell2.local": "/home/pi/samples"
       },
       "timezone": "Europe/Brussels",
       "disable_calendar": "https://example.com/calendar.ics",
       "manual_bell": {
           "gpio": 17,
           "wav_key": "lesson",
           "mode": "once",
           "pull": "up",
           "bounce_time": 0.05,
           "remote_bells": [
               {
                   "transport": "ssh",
                   "host": "pibell2.local",
                   "user": "pi",
                   "command": ["/usr/local/bin/manual-bell"],
                   "timeout": 10
               },
               {
                   "transport": "webhook",
                   "url": "https://pibell3.example.com/bell",
                   "headers": {"X-Site": "main"},
                   "auth": {
                       "type": "bearer",
                       "token": "replace-with-remote-token"
                   },
                   "timeout": 5
               }
           ]
       },
       "webhook": {
           "enabled": true,
           "host": "127.0.0.1",
           "port": 8081,
           "token": "replace-with-a-long-random-token",
           "rate_limit": 10,
           "rate_window": 60
       },
       "monitoring": {
           "device_id": "main-bell-01",
           "labels": {"school": "example", "zone": "main"},
           "heartbeat_interval": 300,
           "syslog": {
               "host": "graylog.example.com",
               "port": 1514,
               "protocol": "udp",
               "facility": "daemon"
           },
           "status": {
               "enabled": true,
               "host": "0.0.0.0",
               "port": 8080,
               "token": "replace-with-a-monitoring-token",
               "include_systemd": true
           }
       }
   }

Top-level fields
----------------

``schedule`` (object, required)
   Maps three-letter English weekday abbreviations (``Mon`` through ``Sun``)
   to local times and WAVE keys. Times accept ``HH:MM`` or ``HH:MM:SS``. Every
   selected key must exist in ``wav``.

``wav`` (object, required)
   Maps reusable string keys to WAVE filenames. Relative filenames are joined
   to ``root``. Numeric keys and schedule references from older files remain
   accepted, but strings are the canonical form.

``root`` (string or null, default ``null``)
   Base directory for WAVE files. Environment variables such as ``${HOME}``
   are expanded. Prefer an absolute path in managed deployments.

``device`` (string or null, default ``null``)
   ALSA device passed to ``aplay -D``. When omitted, ALSA's default output is
   used. See :doc:`ALSA` for discovering and testing a device name.

``buzz_gpio`` (integer, array of integers, or null; default ``null``)
   One BCM GPIO number or multiple output pins. Outputs are activated while
   the WAVE file plays. The physical manual-button pin cannot reuse one of
   these outputs. See :doc:`GPIO` for pin numbering and relay wiring.

``buzz_active_high`` (boolean, default ``true``)
   ``true`` drives the configured outputs high while ringing; ``false`` is for
   active-low relay boards. Confirm the safe inactive state before connecting
   a real bell circuit.

``timeout`` (integer or null, effective default 10 seconds)
   General timeout used by OpenHolidays and legacy SSH remote playback.
   Historical numeric strings are accepted. Use a positive value in new files.

``holidays`` (string or null, default ``null``)
   OpenHolidays country/language group in ``COUNTRY-LANGUAGE`` form, for
   example ``BE-NL``. A matching public or school holiday suppresses scheduled
   ringing. It does not block a manual bell. See :doc:`calendars` for refresh
   and outage behavior.

``trigger`` (object or null, default ``null``)
   Legacy remote playback mapping. Each key is an SSH host and each value is
   the WAVE root on that host. Scheduled bells are also sent to these hosts.
   Configure key-based SSH access and test it without an interactive prompt;
   see :doc:`remote-bells`.

``timezone`` (string, default ``Europe/Brussels``)
   IANA timezone used for schedule evaluation and monitoring timestamps, such
   as ``Europe/Brussels``. The operating-system clock must also be synchronized.

``disable_calendar`` (HTTP(S) URL or null, default ``null``)
   iCalendar feed containing periods during which scheduled bells are
   suppressed. Calendar URLs can contain credentials and should be handled as
   secrets. Manual bells do not respect this suppression. Supported event
   types and provider instructions are described in :doc:`calendars`.

``manual_bell`` (object or null, default ``null``)
   Physical GPIO input and the optional remote actions associated with it.

``webhook`` (object or null, default ``null``)
   Authenticated inbound HTTP endpoint for remotely ringing this node.

``monitoring`` (object or null, default ``null``)
   Structured remote syslog, device identity, labels, heartbeats and read-only
   HTTP health/status endpoints.

Physical manual bell
--------------------

``manual_bell.gpio`` (integer, required)
   BCM GPIO input connected to the button. It must differ from every
   ``buzz_gpio`` output. See :doc:`GPIO` for a pull-up wiring example.

``manual_bell.wav_key`` (string, required)
   Entry from ``wav`` to play when the button is pressed.

``manual_bell.mode`` (``once`` or ``hold``, default ``once``)
   ``once`` plays the complete signal per press. ``hold`` stops playback when
   the button is released.

``manual_bell.pull`` (``up``, ``down`` or ``floating``, default ``up``)
   Configures the gpiozero input pull resistor. ``floating`` should only be
   used when the circuit provides an external resistor.

``manual_bell.bounce_time`` (number >= 0, default ``0.05``)
   Button debounce time in seconds.

``manual_bell.remote_bells`` (array, default empty)
   Best-effort SSH or webhook actions started by this physical button. Failure
   of a remote action does not turn the central service into a runtime
   dependency for the local bell.

Remote SSH entry
~~~~~~~~~~~~~~~~

``transport``
   ``ssh``. It may be omitted for compatibility because SSH is the default.

``host``
   Required non-empty hostname or address.

``user``
   Optional SSH username.

``command``
   Required command as a string or argument array. An argument array avoids
   ambiguity and is recommended.

``timeout``
   Positive integer in seconds; default ``10``.

Remote webhook entry
~~~~~~~~~~~~~~~~~~~~

``transport``
   Required value ``webhook``.

``url``
   Required HTTP(S) endpoint URL.

``headers``
   Optional string-to-string object for additional request headers; default
   empty. Do not duplicate credentials unnecessarily.

``auth``
   Optional authentication object. Bearer authentication requires
   ``{"type": "bearer", "token": "..."}``. Basic authentication requires
   ``{"type": "basic", "username": "...", "password": "..."}``. Fields
   belonging to the other authentication type are rejected.

``timeout``
   Positive number in seconds; default ``5``.

Inbound webhook
---------------

``webhook.enabled`` (boolean, default ``false``)
   Starts the ``POST /bell`` service when true.

``webhook.host`` (string, default ``127.0.0.1``)
   Bind address. Keep the loopback default when a reverse proxy provides TLS.
   ``0.0.0.0`` exposes the endpoint on all network interfaces.

``webhook.port`` (integer 0–65535, default ``8081``)
   Listening TCP port. Port ``0`` is mainly useful in tests because the OS
   selects an available port.

``webhook.token`` (string or null, default ``null``)
   Required, non-empty bearer token when enabled.

``webhook.rate_limit`` (positive integer, default ``10``)
   Maximum accepted requests from one client during ``rate_window``.

``webhook.rate_window`` (positive integer, default ``60``)
   Rate-limit window in seconds.

The request must use ``Content-Type: application/json``, provide
``Authorization: Bearer <token>`` and contain exactly one value:

.. code-block:: json

   {"wav_key": "lesson"}

See :doc:`remote-bells` for a complete request, response codes and reverse
proxy guidance.

Monitoring
----------

``monitoring.device_id`` (string or null, default hostname)
   Stable unique identity shown in events and HTTP responses. Configure it
   explicitly if a renamed or replaced Pi must retain the same identity.

``monitoring.labels`` (object, default empty)
   Additional metadata such as school, site or zone. Names must start with a
   letter and contain only letters, numbers and underscores. Event fields are
   emitted with a ``label_`` prefix and become ``sb_label_*`` after the supplied
   Graylog pipeline.

``monitoring.heartbeat_interval`` (positive integer, default ``300``)
   Seconds between ``health_status`` events.

``monitoring.syslog`` (object or null, default ``null``)
   Destination for structured events. Its fields are ``host`` (required),
   ``port`` (0–65535, default ``514``), ``protocol`` (``udp`` or ``tcp``,
   default ``udp``) and ``facility`` (known syslog facility, default
   ``daemon``).

``monitoring.status`` (object or null, default ``null``)
   Read-only HTTP service. Fields are ``enabled`` (default ``false``), ``host``
   (default ``127.0.0.1``), ``port`` (0–65535, default ``8080``), optional
   bearer ``token``, and ``include_systemd`` (default ``true``). Binding to a
   network interface without a token is only suitable for a trusted network.

Values that do not belong in JSON
---------------------------------

``debug``, ``test``, ``check``, ``prog``, ``info``, ``config_hash`` and
``schedule_hash`` are runtime values. They are intentionally rejected as
configuration input. Use the command-line flags for diagnostics; revision
hashes are always calculated from the original JSON.
