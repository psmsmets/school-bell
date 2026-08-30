# Graylog setup for School Bell

This directory contains the Graylog-specific input helper, reusable content
pack, parsing rule, test sender and dashboard reference. See the parent
[`monitoring/README.md`](../README.md) for School Bell monitoring configuration,
device identity, the HTTP status service and service management.

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

## 1. Create the input

Create a Graylog access token with permission to manage inputs, then run:

```sh
export GRAYLOG_URL=https://graylog.example.com
export GRAYLOG_TOKEN=replace-with-api-token
export GRAYLOG_INPUT_PORT=1514
./monitoring/graylog/create-syslog-input.sh
```

The script creates a global UDP Syslog input. Set `GRAYLOG_PROTOCOL=tcp` for a
TCP input. Ensure the selected port is allowed by the Graylog host firewall and
make the School Bell Syslog host, port and protocol match this input.

## 2. Verify JSON parsing

The content pack connects its JSON parsing pipeline to the dedicated School
Bell stream. [`pipeline-rule.conf`](pipeline-rule.conf) contains the same rule
for reference or manual setup. Graylog 7 can retain the RFC 5424 message ID and
structured-data marker in `message` (for example `health_status - {...}`). The
rule strips everything before the first JSON opening brace and exposes the JSON
properties as searchable `sb_*` fields while retaining the original message.

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

The `_short` fields are intended for compact dashboard display. Use complete
hashes for exact Graylog filters, grouping, alerts and automation.

## 3. Send test events

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
