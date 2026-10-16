"""VLAN60 Native-SPAN raw BPF acceptance; no traffic is injected on physical NIC."""
import ctypes
import ctypes.util
import ipaddress
from pathlib import Path
import struct
import tempfile
import unittest

from app.device_fingerprint_sensor.capture_filter import RAW_CAPTURE_FILTER, load_deployed_filter
from app.device_fingerprint_sensor.models import SensorError

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "deploy/device-fingerprint/raw-capture.bpf"

class BpfInsn(ctypes.Structure):
    _fields_ = [("code",ctypes.c_ushort),("jt",ctypes.c_ubyte),("jf",ctypes.c_ubyte),("k",ctypes.c_uint32)]

class Program(ctypes.Structure):
    _fields_ = [("len",ctypes.c_uint),("insns",ctypes.POINTER(BpfInsn))]

class Timeval(ctypes.Structure):
    _fields_ = [("tv_sec",ctypes.c_long),("tv_usec",ctypes.c_long)]

class PcapHeader(ctypes.Structure):
    _fields_ = [("ts",Timeval),("caplen",ctypes.c_uint32),("length",ctypes.c_uint32)]

def frame(src, dst, proto, sport=0, dport=0, *, flags=2, vlan=None, second_vlan=None):
    if proto == 17:
        transport = struct.pack("!HHHH", sport, dport, 8, 0)
    else:
        transport = struct.pack("!HHIIHHHH", sport, dport, 0, 0, 0x5000 | flags, 4096, 0, 0)
    length = 20 + len(transport)
    ip4 = struct.pack("!BBHHHBBH4s4s", 0x45, 0, length, 1, 0, 64, proto, 0,
                      ipaddress.IPv4Address(src).packed, ipaddress.IPv4Address(dst).packed)
    eth = b"\x02\x00\x00\x00\x00\x01" + b"\x02\x00\x00\x00\x00\x02"
    if vlan is None:
        eth += struct.pack("!H", 0x0800)
    elif second_vlan is None:
        eth += struct.pack("!HHH", 0x8100, vlan, 0x0800)
    else:
        eth += struct.pack("!HHHHH", 0x88a8, vlan, 0x8100, second_vlan, 0x0800)
    return eth + ip4 + transport

class TestVlan60FrozenBpf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lib=ctypes.util.find_library("pcap")
        if not lib:raise unittest.SkipTest("libpcap missing")
        cls.pcap=ctypes.CDLL(lib)
        cls.pcap.pcap_open_dead.argtypes=[ctypes.c_int,ctypes.c_int]
        cls.pcap.pcap_open_dead.restype=ctypes.c_void_p
        cls.pcap.pcap_compile.argtypes=[ctypes.c_void_p,ctypes.POINTER(Program),ctypes.c_char_p,ctypes.c_int,ctypes.c_uint32]
        cls.pcap.pcap_compile.restype=ctypes.c_int
        cls.pcap.pcap_offline_filter.argtypes=[ctypes.POINTER(Program),ctypes.POINTER(PcapHeader),ctypes.POINTER(ctypes.c_ubyte)]
        cls.pcap.pcap_offline_filter.restype=ctypes.c_int
        cls.pcap.pcap_freecode.argtypes=[ctypes.POINTER(Program)]
        cls.pcap.pcap_close.argtypes=[ctypes.c_void_p]
        cls.handle=cls.pcap.pcap_open_dead(1,65535)
        assert cls.handle
        cls.program=Program()
        err=cls.pcap.pcap_compile(cls.handle,ctypes.byref(cls.program),RAW_CAPTURE_FILTER.encode(),1,0xffffffff)
        assert err==0,"Actual libpcap rejects canonical BPF"

    @classmethod
    def tearDownClass(cls):
        if getattr(cls,"handle",None):
            cls.pcap.pcap_freecode(ctypes.byref(cls.program))
            cls.pcap.pcap_close(cls.handle)

    def admits(self,packet):
        hdr=PcapHeader(Timeval(0,0),len(packet),len(packet))
        buf=(ctypes.c_ubyte*len(packet)).from_buffer_copy(packet)
        return self.pcap.pcap_offline_filter(ctypes.byref(self.program),ctypes.byref(hdr),buf) != 0

    def test_artifact_exact_and_guarded(self):
        self.assertEqual(ARTIFACT.read_text().strip(), RAW_CAPTURE_FILTER)
        self.assertIn("src net 10.50.0.0/19",RAW_CAPTURE_FILTER)
        self.assertNotIn("192.168.8.0/22",RAW_CAPTURE_FILTER)
        self.assertEqual(load_deployed_filter(ARTIFACT),RAW_CAPTURE_FILTER)
        with tempfile.TemporaryDirectory() as d:
            wrong=Path(d)/"raw-capture.bpf"
            wrong.write_text(RAW_CAPTURE_FILTER+" or ip")
            with self.assertRaises(SensorError):
                load_deployed_filter(wrong)

    def test_native_untagged_dhcp_positive(self):
        self.assertTrue(self.admits(frame("0.0.0.0","255.255.255.255",17,68,67)))
        self.assertTrue(self.admits(frame("10.50.0.50","255.255.255.255",17,68,67)))
        self.assertTrue(self.admits(frame("10.50.0.1","255.255.255.255",17,67,68)))

    def test_native_untagged_tcp_syn_positive(self):
        self.assertTrue(self.admits(frame("10.50.0.50","1.1.1.1",6,12345,443,flags=2)))
        self.assertTrue(self.admits(frame("10.50.31.254","8.8.8.8",6,32100,443,flags=2)))

    def test_legacy_tcp_and_other_negative(self):
        self.assertFalse(self.admits(frame("192.168.9.60","8.8.8.8",6,12345,443,flags=2)))
        self.assertFalse(self.admits(frame("192.168.0.60","8.8.8.8",6,12345,443,flags=2)))
        self.assertFalse(self.admits(frame("10.50.0.50","1.1.1.1",6,12345,443,flags=16)))
        self.assertFalse(self.admits(frame("192.168.9.60","8.8.8.8",17,12345,443)))

    def test_tagged_traffic_excluded_in_native_span_contract(self):
        for vlan in (10,20,60,999):
            self.assertFalse(self.admits(frame("0.0.0.0","255.255.255.255",17,68,67,vlan=vlan)))
            self.assertFalse(self.admits(frame("10.50.0.50","1.1.1.1",6,12345,443,vlan=vlan)))
        self.assertFalse(self.admits(frame("0.0.0.0","255.255.255.255",17,68,67,vlan=60,second_vlan=20)))

    def test_dhcp_bootstrap_requires_vlan60_only_mirror(self):
        # Untagged legacy DHCP is L2-indistinguishable; only VLAN60-only SPAN isolates it.
        self.assertTrue(self.admits(frame("0.0.0.0","255.255.255.255",17,68,67)))

if __name__ == "__main__":
    unittest.main()
