Configuration
=============

School Bell accepts a JSON object directly or a path to a JSON file. The
configuration is validated completely before the service is initialized.
Unknown fields are rejected and errors include their full nested path.

This page explains how to build and maintain a configuration. Use the
:doc:`configuration-reference` when you need the type, default and meaning of
every available parameter. The :doc:`schema` page describes machine-readable
validation for editors, CI and deployment tooling.

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

How the configuration fits together
------------------------------------

A useful way to read the file is as four layers:

#. ``schedule`` decides **when** a bell should ring and selects a key.
#. ``wav`` translates that key into a local WAVE filename.
#. output settings decide **where** it rings: ALSA, GPIO and optional remote
   bells.
#. optional integrations suppress bells, accept manual triggers or report
   health without becoming a dependency for normal local scheduling.

For example, ``"Mon": {"08:30": "lesson"}`` selects the ``lesson`` entry
from ``wav`` every Monday at 08:30 in the configured timezone. If ``root`` is
``/home/pi/samples`` and ``wav.lesson`` is ``bell.wav``, School Bell plays
``/home/pi/samples/bell.wav``.

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
``false`` for active-low relay boards. See :doc:`GPIO` before selecting pins or
connecting a relay.

``manual_bell`` configures one physical input button. Its ``gpio`` cannot also
be an output, and its ``wav_key`` must exist. ``mode`` is ``once`` or ``hold``;
``pull`` is ``up``, ``down`` or ``floating``. Optional ``remote_bells`` entries
use SSH or authenticated HTTP webhooks. :doc:`GPIO` includes the basic button
wiring and test procedure.

The top-level ``trigger`` mapping configures legacy SSH destinations. The
``webhook`` section can expose an authenticated ``POST /bell`` endpoint. Bind
the built-in HTTP server to localhost and use a TLS reverse proxy before
exposing it to an untrusted network.

Monitoring
----------

The optional ``monitoring`` object configures device identity, labels,
heartbeat events, remote syslog and read-only HTTP status endpoints. See
:doc:`MONITORING` for examples and security considerations.

Choosing optional integrations
------------------------------

Start with only ``schedule``, ``wav``, ``root`` and ``timezone``. Add one
integration at a time and run ``--check`` after every change. A typical order
is:

#. confirm local WAVE playback;
#. add GPIO relay outputs if the installation uses them;
#. add holiday or calendar suppression;
#. add a physical manual button or authenticated webhook;
#. add monitoring and verify Graylog or the HTTP health endpoint.

This keeps faults easy to locate and ensures the autonomous local path works
before central services are introduced.

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
