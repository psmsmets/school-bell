Configuration
=============

School Bell accepts a JSON object directly or a path to a JSON file. The
configuration is validated completely before the service is initialized.
Unknown fields are rejected and errors include their full nested path.

Minimal configuration
---------------------

.. code-block:: json

   {
       "schedule": {
           "Mon": {"08:30": "0"}
       },
       "wav": {
           "0": "bell.wav"
       },
       "root": "/home/pi/samples",
       "timezone": "Europe/Brussels"
   }

Use ``school-bell --demo-config`` or the repository's ``demo.json`` for a
complete example.

Core fields
-----------

``schedule``
   Maps three-letter weekdays and ``HH:MM[:SS]`` local times to keys in
   ``wav``. WAV references should be strings.

``wav``
   Maps identifiers to WAVE filenames. Files are resolved relative to
   ``root``.

``root``
   Directory containing local audio files. Environment variables such as
   ``${HOME}`` are expanded at runtime.

``timezone``
   IANA timezone used to evaluate schedules. The default is
   ``Europe/Brussels``.

``timeout``
   Timeout in seconds for applicable network and SSH operations.

``holidays``
   Optional OpenHolidays country/language group such as ``BE-NL``.

``disable_calendar``
   Optional HTTP(S) iCalendar URL. Matching events suppress scheduled bells.

Outputs and triggers
--------------------

``device`` selects an ALSA playback device. ``buzz_gpio`` accepts one BCM GPIO
number or a list. ``buzz_active_high`` defaults to ``true``; set it to
``false`` for active-low relay boards.

``manual_bell`` configures one physical input button. Its ``gpio`` cannot also
be an output, and its ``wav_key`` must exist. ``mode`` is ``once`` or ``hold``;
``pull`` is ``up``, ``down`` or ``floating``. Optional ``remote_bells`` entries
use SSH or authenticated HTTP webhooks.

The top-level ``trigger`` mapping configures legacy SSH destinations. The
``webhook`` section can expose an authenticated ``POST /bell`` endpoint. Bind
the built-in HTTP server to localhost and use a TLS reverse proxy before
exposing it to an untrusted network.

Monitoring
----------

The optional ``monitoring`` object configures device identity, labels,
heartbeat events, remote syslog and read-only HTTP status endpoints. See
:doc:`MONITORING` for examples and security considerations.

Validation and normalization
----------------------------

Validate changes before deployment:

.. code-block:: console

   school-bell /home/pi/schema.json --check

Pydantic uses strict field types and rejects misspelled or unknown fields.
Documented historical forms remain accepted where their meaning is
unambiguous—for example integer WAV references, numeric strings and
case-insensitive option values. New configurations should use the canonical
forms shown in the examples.

``config_hash`` and ``schedule_hash`` are generated runtime metadata. They,
along with ``debug``, ``test``, ``check``, ``prog`` and ``info``, are not valid
JSON configuration fields. Hashes are calculated from the original parsed JSON
before defaults or normalization are applied.

Configuration lifecycle
-----------------------

Use this sequence for a controlled change:

#. edit the source configuration;
#. run ``--check`` against the candidate;
#. deploy it to the node;
#. verify the deployed checksum or content;
#. restart School Bell;
#. confirm ``schedule_loaded`` and health monitoring;
#. retain the previous configuration for rollback.

The Ansible playbooks preserve an existing configuration unless an intentional
replacement is requested. See :doc:`deployment`.
