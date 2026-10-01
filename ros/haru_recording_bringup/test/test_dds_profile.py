import xml.etree.ElementTree as ET
import pytest
from haru_recording_bringup.dds_profile import udp_profile

NS = {'d': 'http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles'}

def test_isolates_interfaces_and_preserves_ros_qos():
    root = ET.fromstring(udp_profile('192.0.2.1', ['192.0.2.2', '192.0.2.2']))
    assert [x.text for x in root.findall('.//d:interfaceWhiteList/d:address', NS)] == ['127.0.0.1', '192.0.2.1']
    assert len(root.findall('.//d:initialPeersList/d:locator', NS)) == 2
    assert root.find('.//d:useBuiltinTransports', NS).text == 'false'
    assert root.find('.//d:heartbeatPeriod/d:nanosec', NS).text == '20000000'
    assert root.find('.//d:receiveBufferSize', NS) is None
    # Never override captured reliability, history, durability or publication mode.
    assert root.find('.//d:qos', NS) is None

def test_explicit_buffers_and_duration_normalization():
    root = ET.fromstring(udp_profile('192.0.2.1', ['192.0.2.2'], heartbeat_ms=1000, buffer_bytes=4194304))
    assert root.find('.//d:heartbeatPeriod/d:sec', NS).text == '1'
    assert root.find('.//d:heartbeatPeriod/d:nanosec', NS).text == '0'
    assert root.find('.//d:receiveBufferSize', NS).text == '4194304'

@pytest.mark.parametrize('address,peers,kwargs', [
    ('0.0.0.0', ['192.0.2.2'], {}), ('192.0.2.1', [], {}),
    ('192.0.2.1', ['224.0.0.1'], {}), ('::1', ['192.0.2.2'], {}),
    ('192.0.2.1', ['192.0.2.2'], {'heartbeat_ms':0}),
    ('192.0.2.1', ['192.0.2.2'], {'buffer_bytes':True}),
    ('192.0.2.1', ['192.0.2.2'], {'datagram_bytes':100000}),
])
def test_invalid_profiles_fail_before_configuration(address, peers, kwargs):
    with pytest.raises(ValueError):
        udp_profile(address, peers, **kwargs)
