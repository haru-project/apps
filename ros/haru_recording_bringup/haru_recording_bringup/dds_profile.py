"""Explicit, opt-in Fast DDS UDP settings for cross-host recording validation."""
import ipaddress
import xml.etree.ElementTree as ET


def udp_profile(address, peers, *, heartbeat_ms=20, buffer_bytes=None, datagram_bytes=1200):
    def unicast(value):
        ip = ipaddress.IPv4Address(value)
        if ip.is_multicast or ip.is_unspecified or str(ip) == '255.255.255.255':
            raise ValueError('An IPv4 unicast address is required')
        return str(ip)
    address = unicast(address)
    peers = sorted(set(unicast(peer) for peer in peers))
    if not peers:
        raise ValueError('At least one peer is required')
    for value, low, high, name in ((heartbeat_ms, 1, 1000, 'heartbeat_ms'),
                                  (buffer_bytes, 65536, 134217728, 'buffer_bytes'),
                                  (datagram_bytes, 512, 65000, 'datagram_bytes')):
        if value is None and name == 'buffer_bytes':
            continue
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{name} must be an integer in [{low}, {high}]')
    root = ET.Element('profiles', xmlns='http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles')
    transport = ET.SubElement(ET.SubElement(root, 'transport_descriptors'), 'transport_descriptor')
    def field(parent, name, value):
        ET.SubElement(parent, name).text = str(value)
    field(transport, 'transport_id', 'recording_udp')
    field(transport, 'type', 'UDPv4')
    whitelist = ET.SubElement(transport, 'interfaceWhiteList')
    for ip in sorted({'127.0.0.1', address}):
        field(whitelist, 'address', ip)
    for name, value in (('maxInitialPeersRange', 16), ('maxMessageSize', datagram_bytes),
                        ('sendBufferSize', buffer_bytes), ('receiveBufferSize', buffer_bytes)):
        if value is not None:
            field(transport, name, value)
    participant = ET.SubElement(root, 'participant', profile_name='recording_udp', is_default_profile='true')
    rtps = ET.SubElement(participant, 'rtps')
    builtin = ET.SubElement(rtps, 'builtin')
    initial = ET.SubElement(builtin, 'initialPeersList')
    for ip in sorted({'127.0.0.1', *peers}):
        field(ET.SubElement(ET.SubElement(initial, 'locator'), 'udpv4'), 'address', ip)
    ET.SubElement(ET.SubElement(ET.SubElement(builtin, 'metatrafficUnicastLocatorList'), 'locator'), 'udpv4')
    field(rtps, 'useBuiltinTransports', 'false')
    field(ET.SubElement(rtps, 'userTransports'), 'transport_id', 'recording_udp')
    writer = ET.SubElement(root, 'data_writer', profile_name='recording_repair', is_default_profile='true')
    period = ET.SubElement(ET.SubElement(writer, 'times'), 'heartbeatPeriod')
    field(period, 'sec', heartbeat_ms // 1000)
    field(period, 'nanosec', heartbeat_ms % 1000 * 1000000)
    ET.indent(root)
    return ET.tostring(root, encoding='unicode') + '\n'
