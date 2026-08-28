#!/usr/bin/python3

"""Send a School Bell JSON event to a Graylog syslog input."""

import argparse
import json
import socket
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('host')
    parser.add_argument('port', type=int)
    parser.add_argument('--protocol', choices=('udp', 'tcp'), default='udp')
    parser.add_argument('--device-id', required=True)
    parser.add_argument('--hostname', required=True)
    parser.add_argument('--version', default='test')
    args = parser.parse_args()

    payload = {
        'application': 'school-bell',
        'hostname': args.hostname,
        'device_id': args.device_id,
        'version': args.version,
        'event': 'health_status',
        'status': 'success',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'level': 'info',
        'message': 'Graylog test event',
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
        f'- health_status - {json_message}'
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
