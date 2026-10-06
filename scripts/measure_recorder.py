#!/usr/bin/env python3
"""Run in the recorder image: measure the same ROS traffic with off/default/full_perception.

Writes evidence locally. Never invokes playback or cloud APIs.
"""
import argparse
import importlib
import json
import math
import time
import uuid
from pathlib import Path


def summarize(samples, elapsed):
    gaps = [b[0] - a[0] for a, b in zip(samples, samples[1:])]
    return {
        "messages": len(samples),
        "messages_per_second": len(samples) / elapsed,
        "serialized_bytes_per_second": sum(size for _, size in samples) / elapsed,
        "max_gap_seconds": max(gaps, default=0),
        "p95_gap_seconds": sorted(gaps)[math.ceil(len(gaps) * .95) - 1] if gaps else 0,
    }


def host_sample():
    cpu = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    mem = dict((key.rstrip(':'), int(value.split()[0])) for key, value in
               (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines()))
    return {"at": time.time(), "cpu_ticks": cpu, "available_kib": mem['MemAvailable'],
            "swap_used_kib": mem['SwapTotal'] - mem['SwapFree'],
            "pressure": {name: Path('/proc/pressure/' + name).read_text()
                         for name in ('cpu', 'memory', 'io')}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', choices=['off', 'idle', 'default', 'full_perception'], required=True)
    p.add_argument('--seconds', type=float, default=60)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--domains', type=int, nargs='+', default=[0, 200])
    p.add_argument('--control-domain', type=int, default=0)
    a = p.parse_args()
    if not math.isfinite(a.seconds) or a.seconds <= 0:
        p.error('seconds must be finite and positive')
    if any(not 0 <= d <= 232 for d in [*a.domains, a.control_domain]):
        p.error('domain IDs must be between 0 and 232')
    a.output.mkdir(parents=True, exist_ok=False)
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import qos_profile_sensor_data
    from rosidl_runtime_py.convert import message_to_ordereddict
    from rosidl_runtime_py.utilities import get_message
    from haru_recorder_msgs.msg import CaptureSelection
    srv = importlib.import_module('haru_recorder_msgs.srv')
    contexts, nodes, executors, subscriptions = [], {}, {}, []
    report = {"profile": a.profile, "domains": a.domains, "status": "running"}
    recording_id = None
    samples, measuring = {}, False
    for domain in sorted(set([*a.domains, a.control_domain])):
        context = rclpy.Context()
        rclpy.init(context=context, domain_id=domain)
        contexts.append(context)
        nodes[domain] = rclpy.create_node('recorder_perf_observer', context=context,
                                        enable_rosout=False, start_parameter_services=False)
        executors[domain] = SingleThreadedExecutor(context=context)
        executors[domain].add_node(nodes[domain])
    node = nodes[a.control_domain]

    def spin():
        for executor in executors.values():
            executor.spin_once(timeout_sec=0)
        time.sleep(.0005)

    def call(kind, path, **fields):
        client = node.create_client(getattr(srv, kind), '/haru_recorder/coordinator/' + path)
        try:
            if not client.wait_for_service(timeout_sec=15):
                raise RuntimeError('Service unavailable: ' + path)
            future = client.call_async(getattr(srv, kind).Request(**fields))
            end = time.monotonic() + 60
            while not future.done() and time.monotonic() < end:
                spin()
            result = future.result() if future.done() else None
            if result is None or not result.success:
                raise RuntimeError(path + ': ' + (result.message if result else 'timeout'))
            return result
        finally:
            node.destroy_client(client)

    def wait_state(wanted):
        end = time.monotonic() + 180
        while time.monotonic() < end:
            status = call('GetRecorderStatus', 'status/get').status
            row = next((r for r in status.recordings if r.id == recording_id), None)
            if row and row.capture_state in wanted:
                return row
            if row and row.capture_state in ('failed', 'error'):
                raise RuntimeError(str(row))
            spin()
        raise RuntimeError('Timed out waiting for recording state ' + str(wanted))

    try:
        # Observe compressed sensors and low-bandwidth outputs, identically in every window.
        # ponytail: arrival gaps measure delivery continuity; add timestamp probes for end-to-end latency.
        end = time.monotonic() + 10
        while time.monotonic() < end:
            spin()
        graphs = {str(d): n.get_topic_names_and_types() for d, n in nodes.items()}
        report['graphs'] = graphs
        for domain, n in nodes.items():
            for topic, types in graphs[str(domain)]:
                if (topic.startswith('/haru_recorder') or topic in ('/rosout', '/parameter_events')
                        or len(types) != 1):
                    continue
                if '/sensor/' in topic and not topic.endswith(('/ffmpeg', '/zdepth', '/opus', '/flac', '/compressed', '/state')):
                    continue
                key = str(domain) + ':' + topic
                samples[key] = []
                def receive(data, key=key):
                    if measuring:
                        samples[key].append((time.monotonic(), len(data)))
                try:
                    subscriptions.append(n.create_subscription(get_message(types[0]), topic, receive,
                                                               qos_profile_sensor_data, raw=True))
                except (ImportError, AttributeError, RuntimeError) as error:
                    report.setdefault('observer_gaps', {})[key] = str(error)
        if a.profile != 'off':
            call('CancelDiscovery', 'discovery/cancel')
            call('StartDiscovery', 'discovery/start', domains=a.domains, dwell_seconds=5., stop_on_robot=False)
            end = time.monotonic() + 60
            while time.monotonic() < end:
                catalog = call('GetCaptureCatalog', 'selection/catalog').catalog
                if catalog.scan_state == 2:
                    break
                spin()
            else:
                raise RuntimeError('Discovery did not complete')
            report['catalog'] = message_to_ordereddict(catalog)
            if a.profile != 'idle':
                selection = CaptureSelection(profile_catalog_revision=catalog.revision,
                                             profile=a.profile, default_domain=a.domains[0])
                plan = call('ResolveCaptureSelection', 'selection/resolve', selection=selection, prepare_workers=True).plan
                report['plan'] = message_to_ordereddict(plan)
                if plan.missing_worker_domains:
                    raise RuntimeError('Missing workers: ' + str(plan.missing_worker_domains))
                recording_id = 'perf-' + a.profile + '-' + uuid.uuid4().hex[:8]
                call('StartRecording', 'start', recording_id=recording_id, request_id=uuid.uuid4().hex, selection=selection)
                wait_state({'recording'})
        end = time.monotonic() + 10
        while time.monotonic() < end:
            spin()
        before = host_sample()
        started = time.monotonic()
        measuring = True
        while time.monotonic() - started < a.seconds:
            spin()
        measuring = False
        elapsed = time.monotonic() - started
        after = host_sample()
        ticks = [b - x for x, b in zip(before['cpu_ticks'], after['cpu_ticks'])]
        report.update(elapsed_seconds=elapsed, host_before=before, host_after=after,
                      host_cpu_busy_percent=100 * (1 - (ticks[3] + ticks[4]) / sum(ticks)),
                      host_iowait_percent=100 * ticks[4] / sum(ticks),
                      topics={k: summarize(v, elapsed) for k, v in samples.items()}, status='measured')
    except BaseException as error:
        report.update(status='failed', error=str(error))
        raise
    finally:
        if recording_id:
            finalization_started = time.monotonic()
            try:
                call('StopRecording', 'stop', recording_id=recording_id, request_id=uuid.uuid4().hex)
                recording = wait_state({'stopped'})
                report['recording'] = message_to_ordereddict(recording)
                if not recording.coverage_complete or recording.coverage_gaps:
                    report['status'] = 'incomplete_coverage'
            except Exception as error:
                report['cleanup_error'] = str(error)
                report['status'] = 'failed'
            report['finalization_seconds'] = time.monotonic() - finalization_started
        (a.output / 'measurement.json').write_text(json.dumps(report, indent=2) + '\n')
        for executor in executors.values():
            executor.shutdown()
        for n in nodes.values():
            n.destroy_node()
        for context in contexts:
            rclpy.shutdown(context=context)
    print(json.dumps({k: report[k] for k in ('profile', 'status', 'host_cpu_busy_percent') if k in report}))
    return 0 if report['status'] == 'measured' else 1


if __name__ == '__main__':
    raise SystemExit(main())
