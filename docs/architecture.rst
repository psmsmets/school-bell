Architecture
============

School Bell uses a decentralized architecture. Every bell node owns the data
and resources needed for its normal operation:

.. code-block:: text

   Optional central services                 Autonomous bell node

   Ansible / configuration  ──────────────►  local config.json
   NTP server               ──────────────►  system clock
   Graylog / syslog         ◄──────────────  monitoring events
   diagnostics / triggers   ◄─────────────►  optional HTTP or SSH
                                               │
                                               ├── local scheduler
                                               ├── local WAVE files
                                               ├── ALSA output
                                               └── GPIO relays and button

Autonomous operation
--------------------

The schedule is loaded from local configuration when School Bell starts. Jobs
are evaluated by the local process using the configured timezone. Playback and
GPIO activation use local resources. A permanent connection to an Ansible
controller, Graylog server, cloud service or other bell is not required.

If central connectivity is lost, a running and correctly configured node keeps
following the schedule it already loaded. Configuration changes made centrally
do not take effect until they have been deployed to the node and the service
has loaded them.

Local runtime requirements
--------------------------

Normal scheduled operation depends on:

* a running School Bell service;
* a valid local configuration and schedule;
* available local WAVE files;
* a sufficiently accurate system clock;
* working ALSA and GPIO devices when configured.

Central capabilities
--------------------

Central services add management and visibility, but are separate from the
local scheduling path:

* Ansible installs software and deploys configuration;
* syslog or Graylog receives structured events;
* HTTP status endpoints expose current node health;
* SSH and webhooks can trigger or coordinate bells;
* administrators can run diagnostics and maintenance remotely.

Failure boundaries
------------------

Remote monitoring failures do not stop local scheduling. A failed remote
manual trigger does not change the result of its local bell action. Failed
OpenHolidays or disable-calendar refreshes are handled without making the
schedule depend permanently on those services. See :doc:`networking` for the
exact outage behavior and limitations.

Service lifecycle
-----------------

At startup School Bell parses the original JSON, calculates revision hashes,
validates and normalizes the configuration with Pydantic, and only then
initializes runtime components. Runtime-only values such as debug flags and
hashes are not configuration input.

The process stores its active schedule in memory. Editing the JSON file alone
does not reload it; validate the file and restart the service deliberately.
