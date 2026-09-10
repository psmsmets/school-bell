Changelog
=========

Entries through 0.9.2 were reconstructed from Git tags, pull requests and
commit history. Older releases did not include contemporary release notes, so
the descriptions below only summarize changes that can be verified from the
repository.

Unreleased
----------

Added
~~~~~

* Central Pydantic 2 validation for the complete JSON configuration.
* Precise nested configuration error paths and JSON Schema generation.
* Authenticated HTTP bell webhooks.
* Optional SSH and webhook actions for manual GPIO bells.
* Structured Sphinx documentation with architecture, networking, deployment,
  configuration, monitoring, ALSA and troubleshooting guides.
* Dedicated calendar, remote-bell, command-line and GPIO documentation with
  accessible architecture, wiring and Graylog flow diagrams.

Changed
~~~~~~~

* Python 3.11 is now the minimum supported version.
* Unknown configuration fields are rejected at every level.
* Existing documented legacy configuration representations are normalized
  explicitly.
* Configuration and schedule hashes are computed from original JSON before
  defaults or normalization. Runtime values are not configuration input.
* CI tests CPython 3.11 through 3.14, PyPy 3.11 and the Sphinx build.
* The obsolete Mopidy integration guide was removed.

Removed
~~~~~~~

* Removed the legacy ``-b``/``--buzz`` command-line GPIO override; configure
  relay outputs with ``buzz_gpio`` and ``buzz_active_high`` in JSON.

0.9.2 — 2026-09-02
------------------

* Fixed remote SSH trigger command construction.
* Made remote triggers opt-in and documented their configuration.

0.9.1 — 2026-09-01
------------------

* Added the non-destructive ``--check`` command.
* Reported startup failures through configured remote syslog.
* Made OpenHolidays startup failures non-fatal.
* Fixed dictionary-based remote triggers.
* Rejected invalid schedule entries before registering jobs.
* Made the test suite isolated and deterministic.

0.9.0 — 2026-09-01
------------------

* Added a manual GPIO bell input.
* Added scheduled-bell suppression through public iCalendar feeds.
* Added Ansible backup and restore playbooks.

0.8.6 — 2026-08-30
------------------

* Added a reusable Graylog content pack and dashboard documentation.

0.8.5 — 2026-08-30
------------------

* Added stable configuration, schedule, entry and execution identifiers.
* Added shortened hash values for display.

0.8.4 — 2026-08-29
------------------

* Prevented Ansible deployments from replacing existing configuration files.

0.8.3 — 2026-08-29
------------------

* Added structured monitoring events for GPIO activity and remote triggers.

0.8.2 — 2026-08-29
------------------

* Made active-high and active-low GPIO relay polarity configurable.

0.8.1 — 2026-08-29
------------------

* Improved preservation and deployment of School Bell configuration with
  Ansible.

0.8.0 — 2026-08-29
------------------

* Added structured remote syslog and HTTP status monitoring.
* Added Graylog documentation.
* Installed a supported gpiozero pin factory through Ansible.

0.7.0 — 2026-08-28
------------------

* Added production-oriented Ansible playbooks.
* Extended ``--test`` to exercise every configured GPIO output.

0.6.0 — 2026-08-28
------------------

* Added support for multiple GPIO relay pins.
* Modernized packaging with ``pyproject.toml`` and setuptools-scm.
* Updated deployment for Raspberry Pi OS Trixie.
* Fixed empty school-holiday responses and removed the obsolete Conda setup.

0.5.6 — 2024-04-16
------------------

* Added service restart delay and improved version reporting.

0.5.5 — 2024-01-08
------------------

* Improved log formatting for ``journalctl``.

0.5.4 — 2024-01-08
------------------

* Added date-specific holiday lookup and caching.

0.5.3 — 2024-01-03
------------------

* Fixed self-update to install the selected Git branch.

0.5.2 — 2024-01-03
------------------

* Added GitHub Actions tests across multiple Python versions.
* Improved application logging and naming conventions.

0.5.1 — 2024-01-01
------------------

* Added the initial pytest suite.

0.5.0 — 2024-01-01
------------------

* Reorganized the application around School Bell, OpenHolidays and scheduling
  classes.
* Added recurring holiday refresh, date parsing and improved WAVE management.

0.4.3 — 2023-12-23
------------------

* Fixed bell and OpenHolidays timeouts.
* Improved behavior without a default ALSA device and added early tests.

0.4.2 — 2023-10-04
------------------

This tag points to the same commit as 0.4.1; no additional repository changes
were found between these tags.

0.4.1 — 2023-10-04
------------------

* Fixed self-update and follow-up issues from the ALSA configuration release.

0.4.0 — 2023-10-04
------------------

* Added configurable request timeout and ALSA output device settings.
* Added test playback and improved ALSA device selection.

0.3.4 — 2023-09-21
------------------

* Added a configurable OpenHolidays request timeout.

0.3.3 — 2023-09-20
------------------

* Declared Requests and fixed setuptools-based versioning.

0.3.2 — 2023-09-20
------------------

* Updated documentation and code style.

0.3.1 — 2023-09-20
------------------

* Moved holiday support into a dedicated class.

0.3.0 — 2023-09-19
------------------

* Added public and school holiday support through OpenHolidays.

0.2.3 — 2023-04-26
------------------

* Added demo configuration and systemd-service generation.
* Added self-update and environment setup documentation.

0.2.2 — 2023-04-05
------------------

* Updated installation and usage documentation.

0.2.1 — 2023-04-05
------------------

* Added bell-testing and Mopidy integration documentation.

0.2.0 — 2023-04-02
------------------

* Added direct bell testing from the command line.

0.1.1 — 2022-05-01
------------------

* Added environment-variable expansion in paths and self-update support.

0.1.0-beta — 2022-03-02
-----------------------

* Moved scheduled execution to a background thread.

0.1.0-alpha — 2022-03-02
------------------------

* Added JSON schedules, WAVE samples, GPIO control and audio playback.
* Added remote SSH bell triggering, demo configuration and systemd files.
