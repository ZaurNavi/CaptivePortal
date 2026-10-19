"""Offline libpcap and isolated-netns kernel admission for Issue 244.

Never open a packet socket in the host network namespace. Kernel case requires
root/CAP_NET_RAW and creates its own namespace before constructing any sockets.
"""
import ctypes
import ctypes.util
import os
from pathlib import Path
import select
import shutil
import socket
import struct
import subprocess
import sys
import tempfile

import pytest

from app.device_fingerprint_sensor import capture_filter as bpf
from app.device_fingerprint_sensor.config import parse_guest_cidrs


def packet(source='10.50.1.2', *, destination='198.51.100.2', flags=2, udp=None, ipv6=False):
    ethernet = b'\xff' * 6 + b'\x02\x00\x00\x00\x00\x01' + (b'\x86\xdd' if ipv6 else b'\x08\x00')
    if udp is None:
        payload = struct.pack('!HHIIBBHHH', 12345, 443, 1, 0, 0x50, flags, 1024, 0, 0)
        proto = 6
    else:
        payload = struct.pack('!HHHH', *udp, 8, 0)
        proto = 17
    if ipv6:
        header = struct.pack('!IHBB16s16s', 6 << 28, len(payload), proto, 64,
                             socket.inet_pton(socket.AF_INET6, '2001:db8::1'), socket.inet_pton(socket.AF_INET6, '2001:db8::2'))
    else:
        header = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20 + len(payload), 1, 0, 64, proto, 0,
                             socket.inet_aton(source), socket.inet_aton(destination))
    return ethernet + header + payload


def vectors():
    return [
        ('guest_syn', packet(), True),
        ('last_guest_syn', packet('10.50.31.254'), True),
        ('outside_syn', packet('10.50.32.1'), False),
        ('destination_only_guest_syn', packet('192.0.2.1', destination='10.50.1.2'), False),
        ('old_scope_syn', packet('192.168.8.2'), False),
        ('guest_ack', packet(flags=16), False),
        ('guest_syn_ack', packet(flags=18), False),
        ('guest_fin', packet(flags=1), False),
        ('ordinary_udp', packet(udp=(1234, 443)), False),
        ('dhcp67_outside_scope', packet('192.0.2.1', udp=(68, 67)), True),
        ('dhcp68_outside_scope', packet('192.0.2.1', udp=(67, 68)), True),
        ('ipv6_tcp', packet(ipv6=True), False),
        ('dhcpv6', packet(udp=(546, 547), ipv6=True), False),
    ]


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux native libpcap BPF packet classification contract')
@pytest.mark.parametrize('scope', ['10.50.0.0/19', '192.168.8.0/22,10.50.0.0/19',
    ','.join(f'10.{i}.0.0/16' for i in range(16))])
def test_real_offline_compiled_filter_packet_matrix(scope):
    assert ctypes.util.find_library('pcap'), 'mandatory LAB libpcap is missing'
    networks = parse_guest_cidrs(scope)
    class Timeval(ctypes.Structure):
        _fields_ = [('tv_sec', ctypes.c_long), ('tv_usec', ctypes.c_long)]
    class Header(ctypes.Structure):
        _fields_ = [('ts', Timeval), ('caplen', ctypes.c_uint32), ('length', ctypes.c_uint32)]
    cases = vectors()
    if len(networks) == 2:
        cases = [(name, data, True if name == 'old_scope_syn' else expected) for name, data, expected in cases]
    elif len(networks) == 16:
        cases = [(name, data, name.startswith('dhcp') and name != 'dhcpv6') for name, data, _ in cases]
        cases += [(f'net_{i}', packet(f'10.{i}.1.2'), True) for i in range(16)]
        cases += [('net_17', packet('10.16.1.2'), False)]
    with bpf._compiled_filter(bpf.render_raw_capture_filter(networks)) as (pcap, program):
        pcap.pcap_offline_filter.argtypes = [ctypes.POINTER(bpf._BpfProgram), ctypes.POINTER(Header), ctypes.c_void_p]
        pcap.pcap_offline_filter.restype = ctypes.c_uint
        for name, data, expected in cases:
            header = Header(Timeval(0, 0), len(data), len(data))
            buffer = ctypes.create_string_buffer(data)
            assert bool(pcap.pcap_offline_filter(ctypes.byref(program), ctypes.byref(header), buffer)) is expected, name


def _isolated_kernel_probe(parent_namespace):
    # This assertion precedes *every* socket construction, even on probe failure.
    assert os.readlink('/proc/self/ns/net') != parent_namespace
    subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True, capture_output=True)
    from app.device_fingerprint_sensor.capture import RawCapture
    networks = parse_guest_cidrs('10.50.0.0/19')
    directory = Path(tempfile.mkdtemp(prefix='issue244-kernel-', dir='/run'))
    artifact = directory / 'raw-capture.bpf'
    artifact.write_bytes(bpf.render_raw_capture_filter(networks).encode() + b'\n')
    artifact.chmod(0o600)
    bpf.DEPLOYED_FILTER_PATH = artifact
    sender = None
    owner = None
    events = []
    try:
        sender = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3))
        sender.bind(('lo', 3))
        class Wrapped:
            def __init__(self, raw): self.raw = raw
            def settimeout(self, value): return self.raw.settimeout(value)
            def setsockopt(self, *args): return self.raw.setsockopt(*args)
            def fileno(self): return self.raw.fileno()
            def bind(self, address):
                assert owner.socket is None and address == ('lo', 3)
                # Linux SO_GET_FILTER reports installed instruction count; before bind.
                count = ctypes.c_uint(4096)
                code = (bpf._BpfInsn * 4096)()
                libc = ctypes.CDLL(None, use_errno=True)
                assert libc.getsockopt(self.fileno(), socket.SOL_SOCKET, 26, code, ctypes.byref(count)) == 0
                assert 0 < count.value <= 4096
                events.append('attached_before_bind')
                self.raw.bind(address)
                assert self.raw.getsockname()[1] == 3  # Python AF_PACKET tuple is host-order.
                events.append('bind_protocol_3')
            def close(self): return self.raw.close()
            def recvmsg(self, *args): return self.raw.recvmsg(*args)
        def factory(family, kind, protocol):
            assert (family, kind, protocol) == (socket.AF_PACKET, socket.SOCK_RAW, 0)
            raw = socket.socket(family, kind, protocol)
            try:
                assert raw.getsockname()[1] == 0 and owner.socket is None
                sender.send(packet())
                assert not select.select([raw], [], [], 0.05)[0], 'protocol-zero socket received before attach'
                events.append('protocol_zero_no_receive')
                return Wrapped(raw)
            except BaseException:
                raw.close()
                raise
        owner = RawCapture('lo', networks, socket_factory=factory)
        owner.open()
        assert events == ['protocol_zero_no_receive', 'attached_before_bind', 'bind_protocol_3']
        raw = owner.socket.raw
        received = []
        for name, data, expected in vectors():
            while select.select([raw], [], [], 0)[0]: raw.recv(65535)
            sender.send(data)
            ready = bool(select.select([raw], [], [], 0.05)[0])
            assert ready is expected, name
            if ready:
                delivered, timestamp, observed = owner.receive()
                assert delivered == data and timestamp > 0 and observed.endswith('Z'), name
            received.append((name, ready))
        print('PROTOCOL_ZERO_ATTACH_BIND_ABI=PASS; PACKET_MATRIX=' + repr(received))
    finally:
        if owner is not None: owner.close()
        if sender is not None: sender.close()
        shutil.rmtree(directory)


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux isolated network namespace / CAP_NET_RAW kernel contract')
def test_real_kernel_protocol_zero_attach_before_bind_and_packet_filtering():
    if os.geteuid() != 0:
        pytest.skip('isolated netns CAP_NET_RAW requires root; executed by root LAB suite')
    result = subprocess.run(['unshare', '-n', '--', sys.executable, '-B', '-c',
        'from tests.device_fingerprint_sensor.test_bpf_linux_integration import _isolated_kernel_probe; '
        '_isolated_kernel_probe(' + repr(os.readlink('/proc/self/ns/net')) + ')'],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PROTOCOL_ZERO_ATTACH_BIND_ABI=PASS' in result.stdout
    print(result.stdout)
