# School Bell monitoring

School Bell supports two independent, optional monitoring mechanisms:

- structured events sent to a central syslog or Graylog server;
- a read-only HTTP service on every Raspberry Pi with `/status` and `/health`.

Structured events include relay activation and deactivation as well as every
remote trigger. Graylog can therefore filter on `gpio_activated`,
`gpio_deactivated`, and `remote_trigger` without parsing human-readable log
messages.

Add `monitoring` at the top level of `/home/pi/schema.json`:

```json
{
  "monitoring": {
    "labels": {
      "school": "vito",
      "zone": "main"
    },
    "heartbeat_interval": 300,
    "syslog": {
      "host": "192.168.88.90",
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
```

`device_id` defaults to the Raspberry Pi hostname. Set
`monitoring.device_id` explicitly only when the monitoring identity must remain
stable after renaming or replacing the Pi. Use a unique hostname or explicit
device ID for every bell. Labels are optional and provide stable metadata for
filtering by school, site or zone.

The top-level `timezone` setting controls schedule evaluation and the timezone
recorded in planned bell events. Configuration and schedule hashes are derived
from canonical JSON before runtime-only command-line values are added. Raw
configuration and monitoring credentials are not emitted. Short hashes contain
the first 12 hexadecimal characters for display only; use complete hashes for
exact comparison and automation. `schedule_entry_loaded` events provide the
weekday/time/WAV inventory of the configured schedule.

Restart the service after changing the configuration:

```sh
sudo systemctl restart school-bell.service
sudo journalctl -u school-bell.service -n 50 --no-pager
```

Query the HTTP service with:

```sh
curl -H 'Authorization: Bearer replace-with-a-secret' \
  http://pibell-vito-01:8080/status
curl -H 'Authorization: Bearer replace-with-a-secret' \
  http://pibell-vito-01:8080/health
```

`/status` returns the application version, uptime, schedule, GPIO pins, last
ring, last error, and optionally a safe subset of systemd state. `/health`
returns HTTP 200 while the scheduler is healthy and HTTP 503 otherwise.

See [`graylog/README.md`](graylog/README.md) for the shared input, pipeline,
test sender, multi-device dashboard, and alert setup. The complete feature
reference is in [`../docs/MONITORING.rst`](../docs/MONITORING.rst).
