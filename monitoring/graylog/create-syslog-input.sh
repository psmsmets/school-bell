#!/bin/sh
set -eu

: "${GRAYLOG_URL:?Set GRAYLOG_URL, for example https://graylog.example.com}"
: "${GRAYLOG_TOKEN:?Set GRAYLOG_TOKEN to a Graylog API token}"

protocol=$(printf '%s' "${GRAYLOG_PROTOCOL:-udp}" | tr '[:upper:]' '[:lower:]')
port=${GRAYLOG_INPUT_PORT:-1514}
bind_address=${GRAYLOG_BIND_ADDRESS:-0.0.0.0}

case "$protocol" in
  udp)
    input_type=org.graylog2.inputs.syslog.udp.SyslogUDPInput
    ;;
  tcp)
    input_type=org.graylog2.inputs.syslog.tcp.SyslogTCPInput
    ;;
  *)
    echo "GRAYLOG_PROTOCOL must be udp or tcp" >&2
    exit 2
    ;;
esac

payload=$(printf '%s' "{
  \"title\": \"School Bell Syslog ${protocol}\",
  \"type\": \"${input_type}\",
  \"global\": true,
  \"configuration\": {
    \"bind_address\": \"${bind_address}\",
    \"port\": ${port},
    \"recv_buffer_size\": 1048576,
    \"number_worker_threads\": 2,
    \"allow_override_date\": true,
    \"store_full_message\": false,
    \"expand_structured_data\": false
  }
}")

curl --fail-with-body --silent --show-error \
  --user "${GRAYLOG_TOKEN}:token" \
  --header 'Content-Type: application/json' \
  --header 'X-Requested-By: school-bell' \
  --data "$payload" \
  "${GRAYLOG_URL%/}/api/system/inputs"
printf '\n'

