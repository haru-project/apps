#!/usr/bin/env python3
"""Run serial, isolated release checks and retain commands, logs and evidence.

Run from this workspace with ./ws python3 scripts/qualify-recording-release.py.
This checks a local release candidate. A passing result is not deployment approval.
"""
import argparse
import fcntl
import json
import math
from pathlib import Path
import subprocess
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,default=Path.cwd())
    parser.add_argument('--max-publisher-lateness-ms',type=float)
    parser.add_argument('--max-arrival-error-ms',type=float)
    parser.add_argument('--p99-arrival-error-ms',type=float)
    parser.add_argument('--remote-host')
    parser.add_argument('--remote-workspace',default='/home/levko/haru_recording_ws')
    args=parser.parse_args()
    for value in (args.max_arrival_error_ms,args.p99_arrival_error_ms,args.max_publisher_lateness_ms):
        if value is not None and (not math.isfinite(value) or value<=0):parser.error('Timing limits must be finite and positive')
    timing_args=[]
    for flag,value in (('--max-publisher-lateness-ms',args.max_publisher_lateness_ms),('--max-arrival-error-ms',args.max_arrival_error_ms),('--p99-arrival-error-ms',args.p99_arrival_error_ms)):
        if value is not None:timing_args.extend([flag,str(value)])
    root=args.workspace.resolve()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    lock=(root/'data/release-qualification.lock');lock.parent.mkdir(exist_ok=True)
    with lock.open('w') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        report={'schema':'haru.release_qualification.v1','status':'running','steps':[],
                'deployment_validation':'pending','sources':{},'started_at':time.time()}
        for name in ('.','src/haru-recorder','src/haru-viz','src/haru-domain-bridge'):
            report['sources'][name]={key:subprocess.check_output(['git',*command],cwd=root/name,text=True).strip() for key,command in [('commit',['rev-parse','HEAD']),('changes',['status','--porcelain'])]}
        def save():
            (output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
        def run(name,command,cwd=root,timeout=900):
            row={'name':name,'command':command,'cwd':str(cwd),'started_at':time.time()};report['steps'].append(row);save()
            print(name,flush=True)
            with (output/(name+'.log')).open('w') as log:
                result=subprocess.run(command,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
            row.update(exit_code=result.returncode,elapsed_seconds=time.time()-row['started_at']);save()
            if result.returncode:raise RuntimeError(name+' failed; see its log')
        try:
            run('build',['./ws','colcon','build','--base-paths','src','--packages-select','haru_recorder','haru_viz','haru_recording_bringup'])
            # All DDS tests below share 93–96 and run serially. Refuse occupied domains.
            run('empty-domains',['./ws','python3','-c',"from haru_recorder.coordinator import DomainTransport; import time; t=DomainTransport(); [t.get(d) for d in (93,94,95,96)]; time.sleep(3); bad={d:n.get_node_names_and_namespaces() for d,(_,n,*_) in t.domains.items() if n.get_node_names_and_namespaces()!=[(n.get_name(),n.get_namespace())]}; t.close(); assert not bad,bad"])
            run('disk-reserve',['./ws','python3','-c',"import shutil,json; s=shutil.disk_usage('.'); reserve=max(5*1024**3,s.total//20); print(json.dumps({'available_bytes':s.free,'worker_reserve_bytes':reserve})); assert s.free>reserve, 'Insufficient space for the native worker disk reserve'"])
            run('arrival-acceptance-tests',['./ws','python3','-m','pytest','-q','src/haru_recording_bringup/test/test_replay_acceptance.py'])
            tests=['test_worker_lock','test_capture_policy','test_replay_history','test_coordinated_replay','test_bridge_capture','test_manifest_contracts','test_recording_metrics','test_launch_records','test_library_replay_ros_journey','test_native_playback_inspection','test_runtime_provenance','test_library_contracts','test_library','test_library_cloud','test_inspector','test_bundle','test_transfers','test_cloud_transfer']
            run('recorder-tests',['./ws','python3','-m','pytest','-q',*[f'src/haru-recorder/packages/haru_recorder/test/{name}.py' for name in tests]],timeout=900)
            run('ui-typecheck',['npm','--workspace','apps/ui','run','typecheck'],cwd=root/'src/haru-viz')
            run('ui-tests',['npm','--workspace','apps/ui','run','test','--','--reporter=dot','src/shell/ReplayPanel.test.tsx','src/shell/RecordingLibraryPanel.test.tsx','src/shell/Footer.test.tsx','src/shell/RecordingMetricsPanel.test.tsx','src/shell/LaunchRecordsPanel.test.tsx','src/shell/CaptureProfileSelector.test.tsx','src/shell/RosDiscoveryPanel.test.tsx','src/shell/StackCaptureSelector.test.tsx'],cwd=root/'src/haru-viz')
            for name,extra in [('large-normal',['--hz','500','--payload-bytes','16384','--replay-rate','1']),('large-fast-peer',['--hz','500','--payload-bytes','16384','--replay-rate','4','--peer-local']),('image-peer',['--hz','100','--payload-bytes','65536','--message-type','image','--peer-local'])]:
                run(name,['./ws','ros2','run','haru_recording_bringup','recording_load_test.py','--output',str(output/name),'--seconds','10',*extra,*timing_args])
            if args.remote_host:
                run('remote-image',['./ws','ros2','run','haru_recording_bringup','recording_load_test.py','--output',str(output/'remote-image'),'--seconds','10','--hz','100','--payload-bytes','65536','--message-type','image','--remote-host',args.remote_host,'--remote-workspace',args.remote_workspace,*timing_args])
                result=json.loads((output/'remote-image/load-report.json').read_text())
                if not result.get('distinct_hosts'):raise RuntimeError('Remote test did not establish distinct hosts')
                report['deployment_validation']='two_host_synthetic_passed; real_sensor_transport_and_network_fault_tests_pending'
            report['status']='local_passed'
        except Exception as exc:
            report.update(status='failed',error=str(exc));raise
        finally:
            report['finished_at']=time.time();save()


if __name__=='__main__':main()
