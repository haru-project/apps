#!/usr/bin/env python3
"""Synthetic capture/bridge/replay benchmark; reserves isolated domains 93–96."""
import argparse
import base64
import random
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import shutil
import tempfile
import time
from types import SimpleNamespace

import rclpy
import rosbag2_py
from ament_index_python.packages import get_package_prefix
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rclpy.utilities import get_rmw_implementation_identifier
from rclpy.serialization import serialize_message, deserialize_message
from std_msgs.msg import String
from haru_recorder.capture_policy import CapturePolicy
from haru_recorder.coordinator import Coordinator, DomainTransport
from haru_recorder.discovery import graph_snapshot
from haru_recorder.provision import Provisioner
from haru_recorder.replay import Replay
from haru_recorder.store import Store
from haru_recording_bringup.replay_acceptance import arrival_acceptance, publisher_acceptance
from haru_recording_bringup.load_peer import RemotePeer,serve,message_class,canonical,publish_stream,host_evidence


def wait(predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.05)
    raise TimeoutError('ROS readiness/completion deadline exceeded')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def message_key(data):
    # DDS may append CDR alignment padding; compare message content independently.
    return digest(serialize_message(deserialize_message(data, String)))


def compare(expected, actual):
    wanted, got = Counter(expected), Counter(actual)
    return {'expected': len(expected), 'received': len(actual),
            'missing': sum((wanted-got).values()),
            'unexpected_or_duplicate': sum((got-wanted).values())}


def stats(values):
    values = sorted(values)
    return {key: values[min(len(values)-1, int((len(values)-1)*q))] if values else None
            for key, q in [('min', 0), ('p50', .5), ('p95', .95), ('p99', .99), ('max', 1)]}


def run(args):
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    transport = DomainTransport()
    store = Store(root)
    coordinator = Coordinator(store, transport)
    provision = Provisioner(transport, root, [], set())
    replay = Replay(store, transport)
    store.replay = replay
    nodes, bridge = [], None
    peer=None;offset_ns=0
    report = {'schema': 'haru.recording_load_test.v1', 'status': 'failed',
              'configuration': {'hz_per_domain': args.hz, 'seconds': args.seconds,
                                'payload_bytes': args.payload_bytes, 'reliability': args.reliability,
                                'message_type':args.message_type,'remote_host':args.remote_host,'peer_local':args.peer_local,'replay_rate': args.replay_rate, 'max_lateness_ms': args.max_lateness_ms, 'payload_pattern': 'seeded pseudorandom base64', 'domains': [93, 94, 95, 96]},
              'host': {'platform': platform.platform(), 'cpus': os.cpu_count(), 'rmw': get_rmw_implementation_identifier()}}
    try:
        # Refuse to attach to an existing experiment or worker.
        for d in (93, 94, 95, 96):
            transport.get(d)
        time.sleep(3)
        for d, (_, node, *_rest) in transport.domains.items():
            names = node.get_node_names_and_namespaces()
            if names != [(node.get_name(), node.get_namespace())]:
                raise RuntimeError(f'Domain {d} is occupied: {names}')
        report['local_before']=host_evidence()
        if args.remote_host or args.peer_local:
            peer=RemotePeer(args.remote_host,args.remote_workspace,args.peer_local)
            estimates=[]
            for _ in range(7):
                before=time.time_ns();remote=peer.call('evidence');after=time.time_ns()
                estimates.append({'offset_ns':remote['time_ns']-(before+after)//2,'round_trip_ns':after-before})
            best=min(estimates,key=lambda row:row['round_trip_ns']);offset_ns=best['offset_ns']
            report.update(remote_before=remote,clock_estimates=estimates,clock_offset_estimate_ns=offset_ns,clock_offset_uncertainty_ns=best['round_trip_ns']/2,distinct_hosts=bool(remote.get('boot_id') and report['local_before'].get('boot_id') and remote['boot_id']!=report['local_before']['boot_id']))
            if remote['peer_source_sha256']!=report['local_before']['peer_source_sha256']:raise RuntimeError('Test peer source differs between hosts; rebuild the matching workspace')
            report['remote_preflight']=peer.call('preflight')
            peer.call('configure',vars_for_peer(args))
        provision.prepare([93, 94])
        qos = QoSProfile(depth=1000, reliability=ReliabilityPolicy.RELIABLE
                         if args.reliability == 'reliable' else ReliabilityPolicy.BEST_EFFORT)
        pubs = []
        for d in (() if peer else (93, 94)):
            node = rclpy.create_node('load_source', context=transport.domains[d][0],
                                     enable_rosout=False, start_parameter_services=False)
            transport.domains[d][2].add_node(node)
            nodes.append((d, node))
            pubs.append(node.create_publisher(message_class(args.message_type), '/load/shared', qos))
        config = root/'bridge.yaml'
        config.write_text('name: load_bridge\nfrom_domain: 93\nto_domain: 94\ntopics:\n  /load/shared:\n    type: '+('sensor_msgs/msg/Image' if args.message_type=='image' else 'std_msgs/msg/String')+'\n')
        executable = Path(get_package_prefix('domain_bridge'))/'lib/domain_bridge/domain_bridge'
        with (root/'bridge.log').open('w') as log:
            bridge = subprocess.Popen([str(executable), str(config)], stdout=log, stderr=subprocess.STDOUT)
        wait(lambda: any(r['active'] for c in transport.routing.active() for r in c['routes']))
        wait(lambda: len(transport.domains[94][1].get_publishers_info_by_topic('/load/shared')) == 2)
        graph = {'scan_id': 'load-test', 'state': 'complete', 'domains':
                 {str(d): graph_snapshot(transport.domains[d][1], d) for d in (93, 94)}}
        policy = CapturePolicy(SimpleNamespace(snapshot=lambda: graph, profiles=lambda: {'classification': []}), transport)
        store.capture_policy = policy
        selection = {'revision': policy.catalog()['revision'], 'profile': 'full'}
        store.submit('load', 'start', 'start', {'capture_selection': selection})
        coordinator.tick()
        wait(lambda: all(transport.call(d, 'load', 'status', 'status', {}).get('ready') for d in (93, 94)))
        wait(lambda: peer.call('ready') if peer else all(p.get_subscription_count() >= (2 if i == 0 else 1) for i,p in enumerate(pubs)))
        time.sleep(.5)
        published=peer.call('publish',timeout=args.seconds+30) if peer else publish_stream(pubs,vars_for_peer(args))
        expected={int(d):v for d,v in published['expected'].items()}
        sent={k:stamp-offset_ns for k,stamp in published['sent'].items()}
        report['publish_elapsed_seconds']=published['elapsed']
        report['publisher_acceptance']=publisher_acceptance(published['lateness'],args.max_publisher_lateness_ms)
        report['publisher_phase_seconds']=published.get('phase_seconds',{})
        report['publisher_cpu_seconds']=published.get('cpu_seconds',{})
        report['publisher_schedule_lateness_seconds']=stats(published['lateness'])
        time.sleep(2)  # allow DDS and writer queues to drain before finalization
        store.submit('load', 'stop', 'stop', {})
        coordinator.tick()
        record = store.get('load')
        if record['capture_state'] != 'stopped':
            raise RuntimeError(f'Capture did not finalize: {record["capture_state"]}')
        report['coverage_complete'] = record.get('coverage_complete')
        report['coverage_errors'] = record.get('coverage_errors')
        captured = {93: [], 94: []}
        stamps = {}
        captured_raw = {}
        padding_changes = 0
        capture_latency = []
        for domain, children in record['children'].items():
            for child in children:
                inspection = tempfile.TemporaryDirectory(prefix='haru-load-inspect-')
                copied = Path(inspection.name)/'bag'
                shutil.copytree(Path(child['session_dir'])/'bag', copied)
                reader = rosbag2_py.SequentialCompressionReader()
                reader.open(rosbag2_py.StorageOptions(uri=str(copied), storage_id='mcap'), rosbag2_py.ConverterOptions('', ''))
                while reader.has_next():
                    topic, data, stamp = reader.read_next()
                    if topic != '/load/shared':
                        continue
                    key = canonical(data,args.message_type)
                    captured_raw[key] = digest(data)
                    padding_changes += digest(data) != key
                    captured[int(domain)].append(key)
                    stamps[key] = stamp
                    if key in sent:
                        capture_latency.append((stamp-sent[key])/1e9)
                del reader
                inspection.cleanup()
        report['capture_cdr_padding_changed'] = padding_changes if args.message_type=='string' else None
        report['payload_hash_policy']='Image fields and pixels' if args.message_type=='image' else 'canonical String serialization'
        report['capture'] = {str(d): compare(expected[d], captured[d]) for d in (93, 94)}
        report['capture_receive_latency_seconds'] = stats(capture_latency)
        report['capture_order_preserved'] = all(captured[d] == expected[d] for d in (93, 94))
        observed = {95: [], 96: []}
        arrivals = {95: {}, 96: {}}
        wire_mismatches = {95: 0, 96: 0}
        received_bytes = {95: [], 96: []}
        if peer:peer.call('observe')
        for d in (() if peer else (95, 96)):
            node = rclpy.create_node('load_observer', context=transport.domains[d][0],
                                     enable_rosout=False, start_parameter_services=False)
            transport.domains[d][2].add_node(node)
            nodes.append((d, node))
            def receive(data, d=d):
                received_bytes[d].append((data, time.monotonic()))
            node.create_subscription(message_class(args.message_type), '/load/shared', receive, qos, raw=True)
        prepared = replay.prepare('load', {'domain_map': {'93': 95, '94': 96}, 'allowed_nodes': ['/load_observer'], 'lateness_limit_seconds': args.max_lateness_ms/1000 if args.max_lateness_ms is not None else None})
        wait(lambda: all(p.get_subscription_count() == 1 for p in replay.publishers.values()))
        replay.command('rate', {'rate': args.replay_rate})
        start_wall=time.time_ns()
        start = time.monotonic()
        replay.command('start', {})
        wait(lambda: replay.status()['state'] in ('completed', 'failed'), args.seconds/args.replay_rate+30)
        time.sleep(2)
        report['replay'] = replay.status()
        # Keep observer callbacks light; verification must not throttle the subscriber.
        for d, rows in received_bytes.items():
            for data, arrival in rows:
                key = canonical(data,args.message_type)
                observed[d].append(key)
                arrivals[d][key] = arrival
                if digest(data) != captured_raw.get(key):
                    wire_mismatches[d] += 1
        if peer:
            for domain,rows in peer.call('results').items():
                d=int(domain)
                for key,raw_hash,stamp in rows:
                    observed[d].append(key);arrivals[d][key]=start+(stamp-offset_ns-start_wall)/1e9
                    wire_mismatches[d]+=raw_hash!=captured_raw.get(key)
            report['remote_after']=peer.call('evidence')
        report['local_after']=host_evidence()
        wanted = {95: captured[93], 96: captured[93]+captured[94]}
        report['replay_serialized_byte_mismatches'] = wire_mismatches
        report['replay_delivery'] = {str(d): compare(wanted[d], observed[d]) for d in (95, 96)}
        report['replay_arrival_schedule_error_seconds'] = {
            str(d): stats([arrival-start-(stamps[key]-prepared['timeline_origin_ns'])/1e9/args.replay_rate
                           for key, arrival in arrivals[d].items() if key in stamps]) for d in (95, 96)}
        report['replay_absolute_arrival_error_seconds']={str(d):stats([abs(arrival-start-(stamps[key]-prepared['timeline_origin_ns'])/1e9/args.replay_rate) for key,arrival in arrivals[d].items() if key in stamps]) for d in (95,96)}
        report['arrival_acceptance']=arrival_acceptance(report['replay_absolute_arrival_error_seconds'],args.max_arrival_error_ms,args.p99_arrival_error_ms,report.get('clock_offset_uncertainty_ns',0)/1e9)
        expected_sets = {d: set(keys) for d, keys in expected.items()}
        report['replay_order_preserved_per_stream'] = all(
            [key for key in observed[d] if key in expected_sets[source]] == captured[source]
            for d, source in ((95, 93), (96, 93), (96, 94)))
        checks = list(report['capture'].values())+list(report['replay_delivery'].values())
        if report['replay']['state'] != 'completed':
            raise RuntimeError('Replay failed: '+report['replay'].get('error',''))
        if any(wire_mismatches.values()):
            raise RuntimeError('Replay serialized bytes differ from captured bytes')
        if any(c['missing'] or c['unexpected_or_duplicate'] for c in checks):
            raise RuntimeError('Message loss, duplication or payload mismatch; see report')
        if report['replay']['state'] != 'completed' or not report['capture_order_preserved'] or not report['replay_order_preserved_per_stream']:
            raise RuntimeError('Replay failure or per-stream ordering mismatch')
        if record.get('coverage_complete') is False or record.get('coverage_errors'):
            raise RuntimeError('Recorder reported incomplete capture coverage')
        if not report['publisher_acceptance']['passed']:raise RuntimeError('Publisher schedule budget exceeded; see publisher_acceptance')
        if not report['arrival_acceptance']['passed']:raise RuntimeError('Subscriber arrival budget exceeded; see arrival_acceptance')
        report['status'] = 'passed'
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        if 'local_after' not in report:
            report['local_after'] = host_evidence()
        (root/'load-report.json').write_text(json.dumps(report, indent=2)+'\n')
        replay.close()
        if peer:peer.close()
        if bridge and bridge.poll() is None:
            bridge.terminate()
            bridge.wait(timeout=10)
        for d, node in nodes:
            transport.domains[d][2].remove_node(node)
            node.destroy_node()
        coordinator.pool.shutdown()
        transport.close()
        store.close()
        for proc in provision.processes.values():
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    print(json.dumps(report, indent=2))


def vars_for_peer(args):
    return {key:getattr(args,key) for key in ('hz','seconds','payload_bytes','reliability','message_type')}


if __name__ == '__main__':
    import sys
    if '--peer' in sys.argv:
        serve();sys.exit(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory for bags and report')
    parser.add_argument('--message-type',choices=['string','image'],default='string')
    parser.add_argument('--remote-host',help='SSH test host; the same workspace sources must already be installed there')
    parser.add_argument('--remote-workspace',default='/home/levko/haru_recording_ws')
    parser.add_argument('--peer-local',action='store_true',help='Exercise the peer protocol locally; does not validate multiple hosts')
    parser.add_argument('--hz', type=int, default=1000)
    parser.add_argument('--seconds', type=int, default=10)
    parser.add_argument('--payload-bytes', type=int, default=1024)
    parser.add_argument('--reliability', choices=['reliable', 'best_effort'], default='reliable')
    parser.add_argument('--max-publisher-lateness-ms',type=float,help='Fail if a source publish call starts later than its schedule budget')
    parser.add_argument('--max-arrival-error-ms',type=float,help='Fail if any subscriber absolute arrival error exceeds this budget')
    parser.add_argument('--p99-arrival-error-ms',type=float,help='Fail if per-domain p99 absolute arrival error exceeds this budget')
    parser.add_argument('--max-lateness-ms', type=float, help='Fail replay when scheduler wall-time lateness exceeds this limit')
    parser.add_argument('--replay-rate', type=float, choices=[1., 2., 4.], default=1.)
    args = parser.parse_args()
    if not (1 <= args.hz <= 10000 and 1 <= args.seconds <= 300 and 32 <= args.payload_bytes <= 1048576):
        parser.error('Require 1–10000 Hz, 1–300 seconds and 32–1048576 payload bytes')
    if args.max_lateness_ms is not None and (not math.isfinite(args.max_lateness_ms) or args.max_lateness_ms<=0):
        parser.error('--max-lateness-ms must be finite and positive')
    try:
        arrival_acceptance({},args.max_arrival_error_ms,args.p99_arrival_error_ms)
        publisher_acceptance([],args.max_publisher_lateness_ms)
    except ValueError as exc:parser.error(str(exc))
    run(args)
