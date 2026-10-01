"""Benchmark message generation and optional SSH-controlled ROS test peer."""
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import selectors
import shlex
import subprocess
import threading
import time


def message_class(kind):
    if kind == 'image':
        from sensor_msgs.msg import Image
        return Image
    from std_msgs.msg import String
    return String


def canonical(data,kind):
    from rclpy.serialization import deserialize_message,serialize_message
    message=deserialize_message(data,message_class(kind))
    if kind=='image':
        # CDR padding in Image's variable-length header is not a message field
        # and reserialization does not guarantee deterministic padding bytes.
        header=[message.header.stamp.sec,message.header.stamp.nanosec,message.header.frame_id,message.height,message.width,message.encoding,message.is_bigendian,message.step]
        return hashlib.sha256(json.dumps(header,separators=(',',':')).encode()+b'\0'+bytes(message.data)).hexdigest()
    return hashlib.sha256(serialize_message(message)).hexdigest()


def publish_stream(publishers,configuration):
    from rclpy.serialization import serialize_message
    kind=configuration['message_type'];cls=message_class(kind)
    hz=configuration['hz'];count=int(hz*configuration['seconds'])
    expected={93:[],94:[]};sent={};lateness=[];random_data=random.Random(42)
    phases={name:0. for name in ('message_generation','serialization_and_hash','dds_publish')}
    started=time.monotonic();thread_cpu_started=time.thread_time();process_cpu_started=time.process_time()
    for i in range(count):
        due=started+i/hz;time.sleep(max(0.,due-time.monotonic()))
        for domain,pub in zip((93,94),publishers):
            phase_started=time.monotonic()
            prefix=f'{domain}:{i:09d}:';length=configuration['payload_bytes']-len(prefix)
            body=base64.b64encode(random_data.randbytes((length+3)*3//4)).decode()[:length]
            content=prefix+body
            message=(cls(height=1,width=len(content),encoding='mono8',step=len(content),data=content.encode()) if kind=='image' else cls(data=content))
            phases['message_generation']+=time.monotonic()-phase_started
            phase_started=time.monotonic()
            data=serialize_message(message);key=canonical(data,kind)
            phases['serialization_and_hash']+=time.monotonic()-phase_started
            expected[domain].append(key);sent[key]=time.time_ns()
            lateness.append(max(0.,time.monotonic()-due))
            phase_started=time.monotonic();pub.publish(data)
            phases['dds_publish']+=time.monotonic()-phase_started
    return {'expected':expected,'sent':sent,'lateness':lateness,'elapsed':time.monotonic()-started,'phase_seconds':phases,'cpu_seconds':{'publisher_thread':time.thread_time()-thread_cpu_started,'peer_process':time.process_time()-process_cpu_started}}


def host_evidence():
    evidence={'peer_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'hostname':platform.node(),'platform':platform.platform(),'time_ns':time.time_ns()}
    for name,path in [('boot_id','/proc/sys/kernel/random/boot_id'),('network_counters','/proc/net/dev'),('protocol_counters','/proc/net/snmp'),('extended_protocol_counters','/proc/net/netstat'),('udp_sockets','/proc/net/udp'),('receive_buffer_max','/proc/sys/net/core/rmem_max'),('send_buffer_max','/proc/sys/net/core/wmem_max'),('cpu_pressure','/proc/pressure/cpu'),('memory_pressure','/proc/pressure/memory'),('io_pressure','/proc/pressure/io')]:
        try:evidence[name]=Path(path).read_text()
        except OSError:evidence[name]=None
    try:
        result=subprocess.run(['chronyc','tracking'],capture_output=True,text=True,timeout=2)
        evidence['chrony_tracking']=result.stdout if result.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):evidence['chrony_tracking']=None
    return evidence


class RemotePeer:
    def __init__(self,host,workspace,local=False):
        command=[str(Path(workspace)/'ws'),'ros2','run','haru_recording_bringup','recording_load_test.py','--peer']
        if not local:
            if not host or host.startswith('-'):raise ValueError('Invalid remote host')
            command=['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=10',host,shlex.join(command)]
        self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=False)
        # Drain logs continuously so a full stderr pipe cannot block ROS.
        self.errors=bytearray()
        def drain():
            for block in iter(lambda:self.process.stderr.read(4096),b''):
                self.errors.extend(block)
                if len(self.errors)>65536:del self.errors[:-65536]
        self.drain=threading.Thread(target=drain,daemon=True);self.drain.start()
        self.buffer=b''
    def call(self,operation,payload=None,timeout=30):
        self.process.stdin.write((json.dumps({'operation':operation,'payload':payload or {}})+'\n').encode());self.process.stdin.flush()
        deadline=time.monotonic()+timeout
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout,selectors.EVENT_READ)
            while time.monotonic()<deadline:
                while b'\n' in self.buffer:
                    line,self.buffer=self.buffer.split(b'\n',1)
                    if not line.startswith(b'HARU_PEER '):continue
                    result=json.loads(line[len(b'HARU_PEER '):])
                    if 'error' in result:raise RuntimeError(result['error'])
                    return result['result']
                if not selector.select(max(0.,deadline-time.monotonic())):break
                chunk=os.read(self.process.stdout.fileno(),65536)
                if not chunk:raise RuntimeError('Peer exited: '+self.errors.decode(errors='replace'))
                self.buffer+=chunk
        raise TimeoutError('Test peer did not complete '+operation)
    def close(self):
        # EOF lets the remote peer destroy only the nodes it created.
        if self.process.stdin:self.process.stdin.close()
        try:self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=5)


def serve():
    import sys
    import rclpy
    from rclpy.context import Context
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import QoSProfile,ReliabilityPolicy
    objects=[];publishers=[];received={95:[],96:[]};configuration={}
    def node(domain,name):
        context=Context();rclpy.init(context=context,domain_id=domain)
        n=rclpy.create_node(name,context=context,enable_rosout=False,start_parameter_services=False)
        executor=SingleThreadedExecutor(context=context);executor.add_node(n)
        thread=threading.Thread(target=executor.spin,daemon=True);thread.start();objects.append((context,n,executor,thread));return n
    try:
        for line in sys.stdin:
            try:
                request=json.loads(line);op=request['operation'];payload=request['payload']
                if op=='evidence':result=host_evidence()
                elif op=='preflight':
                    first=len(objects)
                    try:
                        checks={d:node(d,'load_preflight') for d in (93,94,95,96)}
                        time.sleep(3)
                        result={str(d):n.get_node_names_and_namespaces() for d,n in checks.items()}
                        for d,n in checks.items():
                            names=n.get_node_names_and_namespaces()
                            allowed={(n.get_name(),n.get_namespace()),(f'haru_launch_client_{d}','/')}
                            if any(name not in allowed or names.count(name)>1 for name in names):raise RuntimeError(f'Remote domain {d} is occupied: {names}')
                    finally:
                        for context,n,executor,thread in objects[first:]:
                            executor.shutdown();thread.join();n.destroy_node();context.shutdown()
                        del objects[first:]
                elif op=='configure':
                    configuration=payload
                    qos=QoSProfile(depth=1000,reliability=ReliabilityPolicy.RELIABLE if payload['reliability']=='reliable' else ReliabilityPolicy.BEST_EFFORT)
                    for domain in (93,94):publishers.append(node(domain,'load_source').create_publisher(message_class(payload['message_type']),'/load/shared',qos))
                    result={}
                elif op=='ready':result=all(pub.get_subscription_count()>=(2 if i==0 else 1) for i,pub in enumerate(publishers))
                elif op=='publish':result=publish_stream(publishers,configuration)
                elif op=='observe':
                    for domain in (95,96):node(domain,'load_observer').create_subscription(message_class(configuration['message_type']),'/load/shared',lambda data,d=domain:received[d].append((data,time.time_ns())),qos,raw=True)
                    result={}
                elif op=='results':
                    # Hash after reception, outside subscriber callbacks.
                    result={str(d):[(canonical(data,configuration['message_type']),hashlib.sha256(data).hexdigest(),stamp) for data,stamp in list(rows)] for d,rows in received.items()}
                else:raise ValueError('Unknown peer operation')
                print('HARU_PEER '+json.dumps({'result':result}),flush=True)
            except Exception as exc:print('HARU_PEER '+json.dumps({'error':str(exc)}),flush=True)
    finally:
        for context,n,executor,thread in objects:
            executor.shutdown();thread.join();n.destroy_node();context.shutdown()
