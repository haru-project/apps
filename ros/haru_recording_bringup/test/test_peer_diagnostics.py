import time
from haru_recording_bringup.load_peer import publish_stream


def test_publisher_cpu_does_not_count_time_blocked_in_publish():
    class SlowPublisher:
        def publish(self, data):
            assert isinstance(data, bytes)
            time.sleep(.01)
    result=publish_stream([SlowPublisher(),SlowPublisher()],{'message_type':'image','hz':100,'seconds':.02,'payload_bytes':4096})
    assert len(result['expected'][93])==len(result['expected'][94])==2
    assert len(result['lateness'])==4
    assert result['phase_seconds']['dds_publish']>=.04
    assert result['elapsed']-result['cpu_seconds']['publisher_thread']>=.035
    assert result['cpu_seconds']['publisher_thread']>=0
    assert result['cpu_seconds']['peer_process']>=0
