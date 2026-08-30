# School Bell dashboard

The School Bell content pack installs this dashboard automatically. Use this
reference to build one manually or customize the installed dashboard.

Create a dashboard named **School Bell Overview**, select the **School Bell**
stream and use a default time range of 24 hours. Every widget has its own query,
so the dashboard search bar remains available as an additional device, school
or zone filter.

`max(timestamp)` means metric function `max` with field `timestamp`. Use
descending order for tables containing that metric.

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
| GPIO activity | `sb_event:(gpio_activated OR gpio_deactivated)` | Data table | Rows: `sb_device_id`, `sb_event`, `sb_gpio_state`, `sb_gpio_pins`; metric: `count()`; range: 24 hours |
| Remote triggers | `sb_event:remote_trigger` | Data table | Rows: `sb_device_id`, `sb_remote_host`, `sb_status`; metrics: `count()`, `max(sb_duration_seconds)`; range: 7 days |
| Recent events | `sb_application:school-bell` | Message table | Columns: `timestamp`, `sb_device_id`, `sb_event`, `sb_status`, `sb_message`; range: 24 hours |
| Configuration revisions | `sb_event:schedule_loaded` | Data table | Rows: `sb_device_id`, `sb_config_hash_short`; metric: `max(timestamp)`; range: 30 days |
| Schedule revisions | `sb_event:schedule_loaded` | Data table | Rows: `sb_schedule_hash_short`, `sb_device_id`; metric: `max(timestamp)`; range: 30 days |
| Schedule inventory | `sb_event:schedule_entry_loaded` | Data table | Rows: `sb_device_id`, `sb_weekday`, `sb_local_time`, `sb_wav_key`, `sb_schedule_entry_id`; metric: `max(timestamp)`; range: 30 days |
| Duplicate executions | `sb_event:bell_ring AND sb_trigger_id:*` | Data table | Row: `sb_trigger_id`; metrics: `count()`, `cardinality(sb_device_id)`; range: 7 days; investigate rows with count greater than 1 |
| Planned failures | `sb_trigger_id:* AND sb_status:failure` | Data table | Rows: `sb_device_id`, `sb_trigger_id`, `sb_event`, `sb_error_category`; metric: `count()`; range: 7 days |

Place the two single-number widgets at the top, followed by the heartbeat and
version tables. Put the ring chart across the full dashboard width. The failure
and recent-event tables belong at the bottom because they are primarily used
for investigation.

## Filters and alerts

Useful temporary filters in the dashboard search bar are:

```text
sb_device_id:vito-bell-01
sb_label_school:vito
sb_label_zone:main
sb_schedule_hash:a54d...
sb_schedule_entry_id:4c81...
sb_trigger_id:83f2...
```

To inspect all local and remote results belonging to one planned execution,
filter on its `sb_trigger_id`.

The content pack includes these aggregation event definitions:

- **Duplicate bell execution** uses
  `sb_event:bell_ring AND sb_trigger_id:*`, groups by `sb_trigger_id` and
  triggers when `count()` is greater than 1.
- **Planned bell failed** uses
  `sb_event:bell_ring AND sb_status:failure AND sb_trigger_id:*` and groups by
  `sb_device_id` and `sb_trigger_id`.

Graylog can compare received executions with `schedule_entry_loaded`, but a
completely absent execution produces no message to aggregate. A strict
missing-bell alert needs a central expected-execution generator or Graylog
event correlation that combines the schedule inventory with calendar dates
and checks for the expected `trigger_id`. A zero-result message aggregation is
not sufficient unless it is scheduled separately for every expected bell.

The **Bells reporting** number counts devices that sent a heartbeat in the last
10 minutes. With the default five-minute heartbeat this tolerates one missed
message. It is a quick overview rather than an offline alert.

For an offline-device alert, create an event definition that checks whether a
device has produced a message within the expected interval. Group the
aggregation by `sb_device_id` and alert when the latest Graylog `timestamp` is
too old.

Useful alert queries include:

```text
sb_application:school-bell AND sb_status:failure
sb_application:school-bell AND sb_event:audio_error
sb_application:school-bell AND sb_event:calendar_error
sb_application:school-bell AND sb_event:service_started
sb_application:school-bell AND sb_event:remote_trigger AND sb_status:failure
sb_application:school-bell AND sb_event:gpio_deactivated AND sb_status:failure
```

To find version drift, create a table grouped by `sb_device_id` and
`sb_version`, or search for devices not running the expected version:

```text
sb_application:school-bell AND NOT sb_version:1.2.3
```

## Create widgets in Graylog 7

Create a widget with **Create (+) → Aggregation**, open **Edit**, enter its
widget-specific query, and configure Visualization, Grouping and Metrics
according to the table above. Set the widget stream to **School Bell**, preview
it and select **Update widget**.

Official references:

- [Graylog REST API](https://go2docs.graylog.org/current/setting_up_graylog/rest_api.html)
- [Graylog dashboards](https://go2docs.graylog.org/current/interacting_with_your_log_data/dashboards.html)
- [Graylog widgets](https://go2docs.graylog.org/current/interacting_with_your_log_data/widgets.html)
