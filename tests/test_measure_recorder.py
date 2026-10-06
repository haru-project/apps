"""Runnable with python3 tests/test_measure_recorder.py (no ROS installation needed)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('measure', Path(__file__).parents[1] / 'scripts/measure_recorder.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_throughput_and_delivery_gaps():
    assert module.summarize([], 5)['messages_per_second'] == 0
    result = module.summarize([(0., 100), (.1, 200), (.4, 300)], 2)
    assert result['messages_per_second'] == 1.5
    assert result['serialized_bytes_per_second'] == 300
    assert abs(result['p95_gap_seconds'] - .3) < 1e-9
    assert module.observe('/perception/sensor/audio/zoom_h8', ['strawberry_ros_msgs/msg/AudioInt'])
    assert module.observe('/perception/sensor/camera/rgb/ffmpeg', ['ffmpeg_image_transport_msgs/msg/FFMPEGPacket'])
    assert not module.observe('/perception/proc/faces/debug_image', ['sensor_msgs/msg/Image'])
    assert not module.observe('/haru_recorder/coordinator/status', ['haru_recorder_msgs/msg/RecorderStatus'])


if __name__ == '__main__':
    test_throughput_and_delivery_gaps()
    print('Recorder measurement checks passed')
