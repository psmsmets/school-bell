# Graylog setup for School Bell

This directory configures one central Graylog syslog input for any number of
School Bell Raspberry Pis. The device ID defaults to the hostname. Set
`monitoring.device_id` only when a separate, stable monitoring identity is
needed.

## Reusable content pack

[`school-bell-monitoring-content-pack.json`](school-bell-monitoring-content-pack.json)
installs the **School Bell Monitoring** content pack without parameters. It
contains the School Bell stream, an exact `application_name=school-bell`
stream rule, the JSON parsing pipeline and rule, the pipeline-to-stream
connection, the monitoring dashboard, and event definitions for duplicate
executions and failed planned bells.

The pack deliberately contains no Syslog input, input-specific routing rule,
notification, credential, or environment-specific setting. Before installing
it, configure any Graylog RFC 5424 UDP or TCP Syslog input to receive School
Bell events. Content-pack UUIDs in the file are portable dependency keys that
Graylog resolves to newly installed native entity IDs; the file contains no
fixed native Graylog object IDs.

## 1. Configure each Raspberry Pi

Add `monitoring` at the top level of `/home/pi/schema.json`, next to
`schedule`, `wav`, `buzz_gpio`, and the other School Bell settings:

```json
{
  "root": "/home/pi/samples",
  "timezone": "Europe/Brussels",
  "buzz_gpio": [26, 20],
  "buzz_active_high": false,
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

Use the address of the Graylog server for `host`, and make `port` and
`protocol` match the active Graylog Syslog input. Make every hostname unique,
or configure an explicit unique `device_id` if hostnames are not a suitable
stable identity. Labels are optional, but make dashboard filtering per school,
site, or zone easier.

`timezone` controls both schedule evaluation and the timezone recorded in
planned bell events. The default is `Europe/Brussels`; configuring it
explicitly makes the intended wall-clock schedule unambiguous.

The `status` section enables the optional read-only web service on the Pi.
Binding it to `0.0.0.0` makes it reachable over the network, so use a bearer
token and restrict port 8080 to the management network where possible. Check
both endpoints with:

```sh
curl -H 'Authorization: Bearer replace-with-a-secret' \
  http://pibell-vito-01:8080/status
curl -H 'Authorization: Bearer replace-with-a-secret' \
  http://pibell-vito-01:8080/health
```

`/status` returns the version, uptime, schedule, GPIO pins, last ring, last
error, and an optional safe subset of systemd state. `/health` returns HTTP 200
while the scheduler is healthy and HTTP 503 when it is unhealthy. Omit the
complete `status` section to disable the web service.

Restart School Bell after changing the configuration:

```sh
sudo systemctl restart school-bell.service
sudo journalctl -u school-bell.service -n 50 --no-pager
```

With the default interval, a `health_status` heartbeat should appear in
Graylog within five minutes.

## 2. Create the input

Create a Graylog access token with permission to manage inputs, then run:

```sh
export GRAYLOG_URL=https://graylog.example.com
export GRAYLOG_TOKEN=replace-with-api-token
export GRAYLOG_INPUT_PORT=1514
./monitoring/graylog/create-syslog-input.sh
```

The script creates a global UDP Syslog input. Set `GRAYLOG_PROTOCOL=tcp` for a
TCP input. Ensure the selected port is allowed by the Graylog host firewall.

## 3. Extract the JSON fields

Create a pipeline in Graylog, add the rule from
[`pipeline-rule.conf`](pipeline-rule.conf), and connect the pipeline to the
dedicated School Bell stream. Graylog 7 retains the RFC5424 message ID and
structured-data marker in `message` (for example `health_status - {...}`). The
rule recognizes `application_name=school-bell`, strips everything before the
first JSON opening brace, and turns the remaining JSON stored in
the syslog `message` field into directly searchable Graylog fields. Extracted
fields use the `sb_` prefix to avoid conflicts with Graylog's reserved
`message`, `level`, and `timestamp` fields. The original syslog fields and raw
JSON message are deliberately retained alongside the extracted fields. This
makes troubleshooting the input and pipeline possible without losing the
original record.

The common query for all bells is:

```text
sb_application:school-bell
```

One device:

```text
sb_application:school-bell AND sb_device_id:vito-bell-01
```

One school:

```text
sb_application:school-bell AND sb_label_school:vito
```

Configuration and scheduled bell events also expose these separate fields:

```text
sb_config_hash
sb_config_hash_short
sb_schedule_hash
sb_schedule_hash_short
sb_schedule_entry_id
sb_trigger_id
sb_planned_at
sb_local_date
sb_weekday
sb_timezone
```

The hashes are calculated from canonical JSON before runtime-only command-line
values are added. No raw configuration or monitoring credentials are sent.
The `_short` fields contain the first 12 hexadecimal characters for compact
dashboard display only. Keep using the complete hashes for exact filters,
grouping, alerts and automation.
`schedule_entry_loaded` records form the searchable inventory of configured
weekday/time/WAV combinations.

## 4. Send test events

Test two simulated Raspberry Pis:

```sh
python3 monitoring/graylog/send-test-event.py graylog.example.com 1514 \
  --device-id vito-bell-01 --hostname pibell-vito-01
python3 monitoring/graylog/send-test-event.py graylog.example.com 1514 \
  --device-id aso-bell-01 --hostname pibell-aso-01
```

Add `--protocol tcp` when testing a TCP input.

The helper sends the same syslog priority as the application defaults:
facility `daemon` and severity `info` (PRI 30). Graylog should therefore show
`facility=daemon` and numeric `level=6` alongside the extracted `sb_` fields.
Both use an RFC5424 header, so Graylog's native `source` field contains the
Raspberry Pi hostname. Graylog 7 may retain RFC5424 metadata before the JSON in
`message`; the supplied pipeline strips it before parsing.

With the default heartbeat interval, a `health_status` event from each
configured School Bell should appear in Graylog within five minutes.

## 4. Dashboard

The content pack installs the **School Bell Overview** dashboard and its event
definitions. See [`DASHBOARD.md`](DASHBOARD.md) for the complete widget and
query reference when building or customizing a dashboard manually.
