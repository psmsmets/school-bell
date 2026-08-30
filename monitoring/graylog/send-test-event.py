#!/usr/bin/python3

"""Send a School Bell JSON event to a Graylog syslog input."""

import argparse
import hashlib
import json
import socket
from datetime import datetime, timezone

import pytz


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('host')
    parser.add_argument('port', type=int)
    parser.add_argument('--protocol', choices=('udp', 'tcp'), default='udp')
    parser.add_argument('--device-id', required=True)
    parser.add_argument('--hostname', required=True)
    parser.add_argument('--version', default='test')
    args = parser.parse_args()

    planned = datetime.now(pytz.timezone('Europe/Brussels')).replace(
        hour=8, minute=30, second=0, microsecond=0
    ).isoformat()
    planned_at = planned
    weekday = datetime.fromisoformat(planned_at).strftime('%A')
    schedule_entry_id = hashlib.sha256(
        json.dumps(
            [weekday, '08:30:00', '0'], separators=(',', ':')
        ).encode('utf-8')
    ).hexdigest()
    trigger_id = hashlib.sha256(
        json.dumps([
            args.device_id,
            'test-schedule-hash',
            schedule_entry_id,
            planned_at,
        ], separators=(',', ':')).encode('utf-8')
    ).hexdigest()

    payload = {
        'application': 'school-bell',
        'hostname': args.hostname,
        'device_id': args.device_id,
        'version': args.version,
        'event': 'bell_ring',
        'status': 'success',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'level': 'info',
        'message': 'Graylog test event',
        'config_hash': 'test-config-hash',
        'config_hash_short': 'test-config-',
        'schedule_hash': 'test-schedule-hash',
        'schedule_hash_short': 'test-schedul',
        'schedule_entry_id': schedule_entry_id,
        'trigger_id': trigger_id,
        'planned_at': planned_at,
        'local_date': planned_at[:10],
        'weekday': weekday,
        'timezone': 'Europe/Brussels',
        'wav_key': '0',
    }
    json_message = json.dumps(
        payload, separators=(',', ':')
    )
    # Match Python's SysLogHandler for facility=daemon (3), severity=info (6).
    # PRI = facility * 8 + severity = 30.
    syslog_timestamp = datetime.now(
        timezone.utc
    ).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    message = (
        f'<30>1 {syslog_timestamp} {args.hostname} school-bell '
        f'- bell_ring - {json_message}'
    ).encode('utf-8')
    socktype = socket.SOCK_DGRAM if args.protocol == 'udp' else socket.SOCK_STREAM

    with socket.socket(socket.AF_INET, socktype) as connection:
        if args.protocol == 'tcp':
            connection.connect((args.host, args.port))
            connection.sendall(message + b'\x00')
        else:
            connection.sendto(message, (args.host, args.port))

    print(json.dumps(payload, indent=2))


if __name__ == '__main__':
    main()
