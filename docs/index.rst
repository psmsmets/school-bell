School Bell
===========

Run scheduled audio and GPIO signals reliably—even when the network or central
management is unavailable. Each School Bell node stores its configuration and
schedule locally and operates autonomously.

.. grid:: 1 2 2 3
   :gutter: 2

   .. grid-item-card:: Install a bell
      :link: installation
      :link-type: doc

      Set up Python, install School Bell and prepare a node for its first run.

   .. grid-item-card:: Configure schedules
      :link: configuration
      :link-type: doc

      Create and validate configuration, schedules, manual bells and monitoring.

   .. grid-item-card:: Deploy multiple bells
      :link: deployment
      :link-type: doc

      Roll out and manage School Bell nodes consistently with Ansible.

Quick start
-----------

Install School Bell, copy the example configuration and validate it before
starting the service:

.. code-block:: console

   $ python -m pip install .
   $ cp config.example.json config.json
   $ school-bell --config config.json --check

New to the project? Read :doc:`architecture` to understand which components
run locally and which central services are optional.

Explore the documentation
-------------------------

.. grid:: 1 2 2 2
   :gutter: 2

   .. grid-item-card:: Understand the system
      :link: architecture
      :link-type: doc

      Architecture, autonomous operation and the role of central management.

   .. grid-item-card:: Prepare the infrastructure
      :link: networking
      :link-type: doc

      Network access, NTP, outage behavior and audio hardware requirements.

   .. grid-item-card:: Operate and monitor
      :link: MONITORING
      :link-type: doc

      Health reporting, diagnostics and day-to-day operation.

   .. grid-item-card:: Solve a problem
      :link: troubleshooting
      :link-type: doc

      Diagnose startup, scheduling, connectivity and audio problems.

.. toctree::
   :maxdepth: 2
   :caption: Concepts
   :hidden:

   architecture

.. toctree::
   :maxdepth: 2
   :caption: Get started
   :hidden:

   installation
   configuration
   deployment

.. toctree::
   :maxdepth: 2
   :caption: Operations
   :hidden:

   networking
   MONITORING
   ALSA
   troubleshooting

.. toctree::
   :maxdepth: 1
   :caption: Project
   :hidden:

   changelog
