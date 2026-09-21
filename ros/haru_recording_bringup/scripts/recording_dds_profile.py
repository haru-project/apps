#!/usr/bin/env python3
"""Generate an opt-in Fast DDS profile; never changes host or ROS configuration."""
import argparse
from pathlib import Path
import sys
from haru_recording_bringup.dds_profile import udp_profile

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address', required=True, help='Local IPv4 interface address')
    parser.add_argument('--peer', action='append', required=True, help='Peer IPv4 address; repeat for multiple hosts')
    parser.add_argument('--heartbeat-ms', type=int, default=20)
    parser.add_argument('--buffer-bytes', type=int, help='Optional DDS socket buffer size; otherwise keep middleware defaults')
    parser.add_argument('--datagram-bytes', type=int, default=1200)
    args = parser.parse_args()
    try:
        profile = udp_profile(args.address, args.peer, heartbeat_ms=args.heartbeat_ms,
                              buffer_bytes=args.buffer_bytes, datagram_bytes=args.datagram_bytes)
    except ValueError as exc:
        parser.error(str(exc))
    for setting in ('rmem_max', 'wmem_max'):
        try:
            limit = int(Path('/proc/sys/net/core', setting).read_text())
        except (OSError, ValueError):
            print(f'Cannot verify net.core.{setting}; check on this host before testing.', file=sys.stderr)
        else:
            if args.buffer_bytes is not None and limit < args.buffer_bytes:
                print(f'net.core.{setting}={limit} is below requested {args.buffer_bytes}; socket buffers may be capped.', file=sys.stderr)
    print(profile, end='')
