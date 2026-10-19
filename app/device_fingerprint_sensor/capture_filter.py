"""Fixed-grammar site BPF, strict installed bytes and pre-activation attach."""

from __future__ import annotations

import ctypes
import ctypes.util
from contextlib import contextmanager
import ipaddress
import os
import socket
import stat
from pathlib import Path

from .models import SensorError
from .config import GUEST_CIDRS, parse_guest_cidrs, validate_guest_cidrs

DLT_EN10MB = 1
SO_ATTACH_FILTER = 26
RAW_CAPTURE_FILTER = (
    "(udp and (port 67 or port 68)) or "
    "(src net 192.168.8.0/22 and tcp[tcpflags] & (tcp-syn|tcp-ack) == tcp-syn)"
)
DEPLOYED_FILTER_PATH = Path("/etc/captive-portal/device-fingerprint/raw-capture.bpf")
DEFAULT_GUEST_CIDRS = parse_guest_cidrs(GUEST_CIDRS)


def render_raw_capture_filter(guest_cidrs: tuple[ipaddress.IPv4Network, ...]) -> str:
    networks = sorted(validate_guest_cidrs(guest_cidrs), key=lambda value: (int(value.network_address), value.prefixlen))
    source = " or ".join("src net " + str(value) for value in networks)
    if len(networks) > 1:
        source = "(" + source + ")"
    return "(udp and (port 67 or port 68)) or (" + source + " and tcp[tcpflags] & (tcp-syn|tcp-ack) == tcp-syn)"


def verify_filter_bytes(raw: bytes, guest_cidrs: tuple[ipaddress.IPv4Network, ...]) -> str:
    """Pure offline comparison, not an authorization to attach a socket."""
    expected = render_raw_capture_filter(guest_cidrs)
    encoded = expected.encode("ascii")
    if type(raw) is not bytes or raw not in (encoded, encoded + b"\n"):
        raise SensorError("raw capture filter artifact is invalid")
    return expected


def _identity(info):
    return info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink


def _trusted(info, *, directory=False):
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or (not directory and info.st_nlink != 1):
        raise SensorError("raw capture filter artifact is untrusted")


def _read_deployed_bytes(maximum: int) -> bytes:
    """Only the fixed runtime path; all openat ancestors pinned until read ends."""
    if os.name != "posix":
        raise SensorError("raw capture filter artifact is unavailable")
    path = DEPLOYED_FILTER_PATH
    if not path.is_absolute() or ".." in path.parts or str(path) != path.as_posix():
        raise SensorError("raw capture filter artifact is untrusted")
    opened = []; links = []
    try:
        parent = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        opened.append(parent); _trusted(os.fstat(parent), directory=True)
        for name in path.parts[1:-1]:
            before = os.stat(name, dir_fd=parent, follow_symlinks=False); _trusted(before, directory=True)
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            opened.append(child)
            if _identity(before) != _identity(os.fstat(child)):
                raise SensorError("raw capture filter artifact is untrusted")
            links.append((parent, name, _identity(before))); parent = child
        before = os.stat(path.name, dir_fd=parent, follow_symlinks=False); _trusted(before)
        if before.st_size > maximum:
            raise SensorError("raw capture filter artifact is invalid")
        fd = os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
        opened.append(fd)
        if _identity(before) != _identity(os.fstat(fd)):
            raise SensorError("raw capture filter artifact is untrusted")
        raw = bytearray()
        while len(raw) <= maximum:
            block = os.read(fd, maximum + 1 - len(raw))
            if not block: break
            raw.extend(block)
        after = os.fstat(fd)
        for current in (after, os.stat(path.name, dir_fd=parent, follow_symlinks=False)):
            if (_identity(current), current.st_size, current.st_mtime_ns, current.st_ctime_ns) != (
                    _identity(before), before.st_size, before.st_mtime_ns, before.st_ctime_ns):
                raise SensorError("raw capture filter artifact changed")
        if len(raw) != before.st_size or len(raw) > maximum:
            raise SensorError("raw capture filter artifact is invalid")
        for directory_fd, name, expected in links:
            if _identity(os.stat(name, dir_fd=directory_fd, follow_symlinks=False)) != expected:
                raise SensorError("raw capture filter artifact changed")
        return bytes(raw)
    finally:
        for fd in reversed(opened): os.close(fd)


class _BpfInsn(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]


class _BpfProgram(ctypes.Structure):
    _fields_ = [("bf_len", ctypes.c_uint), ("bf_insns", ctypes.POINTER(_BpfInsn))]


class _SockFprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(_BpfInsn))]


def load_deployed_filter(guest_cidrs=DEFAULT_GUEST_CIDRS) -> str:
    expected = render_raw_capture_filter(guest_cidrs)
    try:
        raw = _read_deployed_bytes(len(expected) + 1)
        return verify_filter_bytes(raw, guest_cidrs)
    except (OSError, ValueError):
        raise SensorError("raw capture filter artifact is unavailable") from None


def attach_frozen_filter(raw_socket: socket.socket, guest_cidrs=DEFAULT_GUEST_CIDRS) -> int:
    expression = render_raw_capture_filter(guest_cidrs)
    if load_deployed_filter(guest_cidrs) != expression:
        raise SensorError("raw capture filter is invalid")
    with _compiled_filter(expression) as (_pcap, program):
        copied = (_BpfInsn * program.bf_len)(*[program.bf_insns[index] for index in range(program.bf_len)])
        fprog = _SockFprog(program.bf_len, ctypes.cast(copied, ctypes.POINTER(_BpfInsn)))
        libc = ctypes.CDLL(None, use_errno=True)
        result = libc.setsockopt(raw_socket.fileno(), socket.SOL_SOCKET, SO_ATTACH_FILTER, ctypes.byref(fprog), ctypes.sizeof(fprog))
        if result != 0:
            raise OSError(ctypes.get_errno(), "SO_ATTACH_FILTER failed")
        return int(program.bf_len)


@contextmanager
def _compiled_filter(expression: str):
    """Private offline compiler; never attaches an unverified expression."""
    pcap_name = ctypes.util.find_library("pcap")
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
        if not 0 < program.bf_len <= 4096 or not program.bf_insns:
            raise SensorError("raw capture filter is invalid")
        yield pcap, program
    finally:
        pcap.pcap_freecode(ctypes.byref(program))
        pcap.pcap_close(handle)
