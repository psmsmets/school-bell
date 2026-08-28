************************
Remote monitoring
************************

School Bell can send structured JSON events to a remote syslog server and
provide read-only HTTP status and health endpoints. Both features are
optional. Monitoring failures do not stop the bell scheduler.


Configuration
=============

Configure every Raspberry Pi with a unique ``device_id``. Labels make it easy
to group multiple bells by school, site or zone in Graylog.

.. code-block:: JSON

    {
        "monitoring": {
            "device_id": "vito-bell-01",
            "labels": {
                "school": "vito",
                "zone": "main"
            },
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
                "token": "replace-with-a-secret",
                "include_systemd": true
            }
        }
    }

``protocol`` accepts ``udp`` or ``tcp``. Local stdout/journal logging remains
active when remote syslog is configured. The complete monitoring token is
never returned by the API or included in structured events.

``heartbeat_interval`` is expressed in seconds and defaults to 300. Every
heartbeat contains the same ``device_id`` and labels, allowing Graylog to
detect one silent Raspberry Pi independently from all other bells.


Structured syslog
=================

Every remote record includes stable fields suitable for Graylog indexing:

.. code-block:: JSON

    {
        "application": "school-bell",
        "hostname": "pibell-vito-01",
        "device_id": "vito-bell-01",
        "version": "1.2.3",
        "event": "bell_ring",
        "status": "success",
        "timestamp": "2026-08-28T08:30:00+00:00",
        "level": "info",
        "message": "bell ring",
        "label_school": "vito",
        "label_zone": "main",
        "wav_key": "0",
        "gpio_pins": [26, 20]
    }

Stable event names include ``service_started``, ``service_stopped``,
``schedule_loaded``, ``bell_ring``, ``bell_skipped_holiday``, ``gpio_test``
and ``health_status``. Future calendar monitoring can add
``bell_skipped_calendar``, ``calendar_refresh`` and ``calendar_error`` without
changing the common fields.


HTTP API
========

The server runs in a background thread and only accepts ``GET`` requests.
Binding to ``0.0.0.0`` exposes it to the network. Prefer a firewall and bearer
token whenever the network is not fully trusted.

.. code-block:: sh

    curl -H 'Authorization: Bearer replace-with-a-secret' \
      http://pibell-vito-01.local:8080/status
    curl -H 'Authorization: Bearer replace-with-a-secret' \
      http://pibell-vito-01.local:8080/health

``/status`` returns the current version, device identity, uptime, schedule,
trigger hostnames, GPIO pins, last ring, last error and a selected structured
subset of ``systemctl show``. It never returns the full application
configuration, monitoring token or remote syslog settings.

``/health`` returns HTTP 200 while the scheduler is healthy and HTTP 503 when
it is not. A successful response is:

.. code-block:: JSON

    {"status": "ok"}


Graylog
=======

Ready-to-use helper files and dashboard instructions are in
``monitoring/graylog``. They assume one shared Graylog input for all Raspberry
Pis. Messages are distinguished and aggregated by ``device_id`` and may be
further grouped by fields such as ``label_school`` and ``label_zone``.
The supplied Graylog pipeline prefixes extracted fields with ``sb_`` to avoid
collisions with Graylog's reserved fields. For example, ``device_id`` becomes
``sb_device_id`` while Graylog's native ``timestamp`` remains unchanged. The
original syslog fields and raw JSON remain available for troubleshooting.
