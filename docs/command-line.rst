Command-line reference
======================

The ``school-bell`` command accepts a JSON object or the path to a JSON file:

.. code-block:: console

   $ school-bell CONFIG [OPTIONS]

Use the configuration file explicitly in scripts and services. Examples on
this page use ``/home/pi/schema.json``.

Run the scheduler
-----------------

With no action option, School Bell validates the configuration, initializes
the configured integrations and runs the local schedule:

.. code-block:: console

   $ school-bell /home/pi/schema.json

Diagnostic and one-off actions
------------------------------

``--check``
   Validate configuration, local WAVE files, OpenHolidays and the public
   iCalendar feed. It does not play audio, switch GPIO, contact remote bells,
   start HTTP listeners or run the scheduler. It prints ``OK``, ``WARNING``,
   ``ERROR`` and ``NOT CONFIGURED`` results. Exit status zero means all
   required checks succeeded; non-zero means at least one check failed.

``--play WAV_KEY``
   Play one configured local WAVE key and exit. This deliberate manual action
   bypasses calendar suppression and does not invoke top-level remote trigger
   destinations.

``--test``
   Exercise real hardware during initialization: activate every configured
   legacy or key-specific relay output sequentially for one second and test
   every configured WAVE file. Disconnect the external bell circuit and use a
   safe audio level first. ``--check`` remains non-destructive when both flags
   are supplied.

``--debug``
   Enable verbose local logging. It can reveal hostnames and operational
   details, so retain logs according to local policy.

Generate examples and inspect the version
-----------------------------------------

``--demo-config``
   Print a complete example configuration and exit. Redirect it to a file and
   remove unused optional integrations before the first run.

   .. code-block:: console

      $ school-bell --demo-config > /home/pi/schema.json

``--demo-service``
   Print a basic systemd unit for the current user and exit. Managed
   installations should use the supplied Ansible playbooks instead.

``--version``
   Print the installed School Bell version and exit.

``--help``
   Print the authoritative option summary for the installed version.

Self-update
-----------

``--update [REVISION]`` installs School Bell from GitHub using ``pip`` and
exits. With no revision it follows ``main``. This is retained for simple,
unmanaged installations, but it does not provide the configuration-preserving
checks, pinning and controlled rollout of :doc:`deployment`.

Do not use ``--update`` on an Ansible-managed production node. Select an exact
tested release or commit with ``ansible/update.yml`` instead.

GPIO configuration
------------------

Relay pins are configured through legacy ``buzz_gpio``/``buzz_active_high`` or
the key-specific ``relays`` list in JSON. There is no command-line GPIO
override. This keeps the validated configuration, runtime behavior and
reported configuration hash aligned. See :doc:`GPIO` for wiring and testing.
