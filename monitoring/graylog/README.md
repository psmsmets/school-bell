# Graylog setup for School Bell

This directory configures one central Graylog syslog input for any number of
School Bell Raspberry Pis. The device ID defaults to the hostname. Set
`monitoring.device_id` only when a separate, stable monitoring identity is
needed.

## 1. Configure each Raspberry Pi

Add `monitoring` at the top level of `/home/pi/schema.json`, next to
`schedule`, `wav`, `buzz_gpio`, and the other School Bell settings:

```json
{
  "root": "/home/pi/samples",
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

## 5. Graylog 7 dashboard

Create a dashboard named **School Bell Overview** and select the School Bell
stream. Use a default time range of 24 hours. Every widget has its own query,
so the dashboard search bar can still be used as a temporary additional filter
for a device, school or zone.

Add the following widgets. `max(timestamp)` means metric function `max` with
field `timestamp`; use descending order for all tables containing that metric.

| Widget | Widget query | Visualization | Grouping and metric |
|---|---|---|---|
| Bells reporting | `sb_event:health_status` | Single number | `cardinality(sb_device_id)`; relative range: 10 minutes |
| Failed events | `sb_status:failure` | Single number | `count()`; relative range: 24 hours |
| Last heartbeat per bell | `sb_event:health_status` | Data table | Rows: `sb_device_id`, `sb_status`, `sb_version`; metric: `max(timestamp)`; range: 24 hours |
| Installed versions | `sb_event:health_status` | Data table | Rows: `sb_version`, `sb_device_id`; metric: `max(timestamp)`; range: 24 hours |
| Successful rings | `sb_event:bell_ring AND sb_status:success` | Bar chart | Row: `timestamp` with automatic interval; series/group: `sb_device_id`; metric: `count()`; range: 7 days |
| Last successful ring | `sb_event:bell_ring AND sb_status:success` | Data table | Row: `sb_device_id`; metric: `max(timestamp)`; range: 7 days |
| Failures by bell and type | `sb_status:failure` | Data table | Rows: `sb_device_id`, `sb_event`, `sb_error_category`; metric: `count()`; range: 7 days |
| Skipped bells | `sb_status:skipped` | Data table | Rows: `sb_device_id`, `sb_event`, `sb_skip_reason`; metric: `count()`; range: 7 days |
| Service restarts | `sb_event:service_started` | Data table | Row: `sb_device_id`; metrics: `count()`, `max(timestamp)`; range: 7 days |
| Recent events | `sb_application:school-bell` | Message table | Columns: `timestamp`, `sb_device_id`, `sb_event`, `sb_status`, `sb_message`; range: 24 hours |

Place the two single-number widgets at the top, followed by the heartbeat and
version tables. Put the ring chart across the full dashboard width. The failure
and recent-event tables belong at the bottom because they are primarily used
for investigation.

Useful temporary filters in the dashboard search bar are:

```text
sb_device_id:vito-bell-01
sb_label_school:vito
sb_label_zone:main
```

The **Bells reporting** number counts devices that sent a heartbeat in the last
10 minutes. With the default five-minute heartbeat this tolerates one missed
message. It is a quick overview, not yet an offline alert; create the event
definition below for notifications.

For an offline-device alert, create an event definition that checks whether a
device has not produced any message within the expected interval. Graylog's
exact event-definition workflow varies by version; group the aggregation by
`sb_device_id` and alert when the latest Graylog `timestamp` is too old.

Useful alert queries include:

```text
sb_application:school-bell AND sb_status:failure
sb_application:school-bell AND sb_event:audio_error
sb_application:school-bell AND sb_event:calendar_error
sb_application:school-bell AND sb_event:service_started
```

To find version drift, create a table grouped by `sb_device_id` and
`sb_version`, or
search for devices not running the expected version:

```text
sb_application:school-bell AND NOT sb_version:1.2.3
```

In Graylog 7, create a widget with **Create (+) → Aggregation**, open **Edit**,
enter its widget-specific query, and configure Visualization, Grouping and
Metrics according to the table above. Set the widget's stream to **School
Bell**, preview it and select **Update widget**. See the official [dashboard documentation](https://go2docs.graylog.org/current/interacting_with_your_log_data/dashboards.html)
and [widget documentation](https://go2docs.graylog.org/current/interacting_with_your_log_data/widgets.html).

Official references:

- [Graylog REST API](https://go2docs.graylog.org/current/setting_up_graylog/rest_api.html)
- [Graylog dashboards](https://go2docs.graylog.org/current/interacting_with_your_log_data/dashboards.html)
- [Graylog widgets](https://go2docs.graylog.org/current/interacting_with_your_log_data/widgets.html)
