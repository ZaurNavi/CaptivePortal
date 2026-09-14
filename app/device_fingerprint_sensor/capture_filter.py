"""Compile the frozen raw-capture expression with libpcap and attach it."""

from __future__ import annotations

import ctypes
import ctypes.util
import socket
from pathlib import Path

from .models import SensorError

DLT_EN10MB = 1
SO_ATTACH_FILTER = 26
RAW_CAPTURE_FILTER = (
    "(udp and (port 67 or port 68)) or "
    "(src net 192.168.8.0/22 and tcp[tcpflags] & (tcp-syn|tcp-ack) == tcp-syn)"
)
DEPLOYED_FILTER_PATH = Path("/etc/captive-portal/device-fingerprint/raw-capture.bpf")


class _BpfInsn(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]


class _BpfProgram(ctypes.Structure):
    _fields_ = [("bf_len", ctypes.c_uint), ("bf_insns", ctypes.POINTER(_BpfInsn))]


class _SockFprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(_BpfInsn))]


def load_deployed_filter(path: Path = DEPLOYED_FILTER_PATH) -> str:
    try:
        value = path.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise SensorError("raw capture filter artifact is unavailable") from exc
    if value != RAW_CAPTURE_FILTER:
        raise SensorError("raw capture filter artifact is invalid")
    return value


def attach_frozen_filter(raw_socket: socket.socket, *, library: str | None = None,
                         expression: str | None = None) -> int:
    expression = load_deployed_filter() if expression is None else expression
    if expression != RAW_CAPTURE_FILTER:
        raise SensorError("raw capture filter is invalid")
    pcap_name = library or ctypes.util.find_library("pcap")
    if not pcap_name:
        raise SensorError("libpcap is unavailable")
    pcap = ctypes.CDLL(pcap_name)
    pcap.pcap_open_dead.argtypes = [ctypes.c_int, ctypes.c_int]
    pcap.pcap_open_dead.restype = ctypes.c_void_p
    pcap.pcap_compile.argtypes = [ctypes.c_void_p, ctypes.POINTER(_BpfProgram), ctypes.c_char_p, ctypes.c_int, ctypes.c_uint32]
    pcap.pcap_compile.restype = ctypes.c_int
    pcap.pcap_freecode.argtypes = [ctypes.POINTER(_BpfProgram)]
    pcap.pcap_close.argtypes = [ctypes.c_void_p]
    handle = pcap.pcap_open_dead(DLT_EN10MB, 65535)
    if not handle:
        raise SensorError("libpcap compile context is unavailable")
    program = _BpfProgram()
    try:
        if pcap.pcap_compile(handle, ctypes.byref(program), expression.encode("ascii"), 1, 0xFFFFFFFF) != 0:
            raise SensorError("raw capture filter compilation failed")
        if not 0 < program.bf_len <= 4096:
            raise SensorError("raw capture filter is invalid")
        copied = (_BpfInsn * program.bf_len)(*[program.bf_insns[index] for index in range(program.bf_len)])
        fprog = _SockFprog(program.bf_len, ctypes.cast(copied, ctypes.POINTER(_BpfInsn)))
        libc = ctypes.CDLL(None, use_errno=True)
        result = libc.setsockopt(raw_socket.fileno(), socket.SOL_SOCKET, SO_ATTACH_FILTER, ctypes.byref(fprog), ctypes.sizeof(fprog))
        if result != 0:
            raise OSError(ctypes.get_errno(), "SO_ATTACH_FILTER failed")
        return int(program.bf_len)
    finally:
        pcap.pcap_freecode(ctypes.byref(program))
        pcap.pcap_close(handle)
