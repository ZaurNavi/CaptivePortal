"""Read-only interface preflight and passive AF_PACKET capture."""

from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.device_fingerprint.validation import format_utc

from .capture_filter import attach_frozen_filter
from .models import SensorPreflightError

SO_TIMESTAMPNS = getattr(socket, "SO_TIMESTAMPNS", 35)
RECEIVE_POLL_SECONDS = 1.0


class InterfacePreflight:
    def __init__(self, interface: str = "enp8s0", *, sys_root: Path = Path("/sys"),
                 proc_root: Path = Path("/proc"), runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> None:
        self.interface = interface
        self.sys_root = sys_root
        self.proc_root = proc_root
        self.runner = runner

    def validate(self) -> None:
        try:
            self._validate()
        except SensorPreflightError:
            raise
        except Exception as exc:
            raise SensorPreflightError("capture_interface_unavailable") from exc

    def _validate(self) -> None:
        if self.interface != "enp8s0":
            self._fail()
        net = self.sys_root / "class" / "net" / self.interface
        if not net.exists() or self._read(net / "operstate") != "up":
            self._fail()
        if (net / "master").exists() or (net / "master").is_symlink():
            self._fail()
        addresses = self._json(["ip", "-j", "address", "show", "dev", self.interface])
        if len(addresses) != 1 or any(item.get("family") in {"inet", "inet6"} for item in addresses[0].get("addr_info", [])):
            self._fail()
        for family in ([], ["-6"]):
            routes = self._json(["ip", *family, "-j", "route", "show", "default", "dev", self.interface])
            if routes:
                self._fail()
        if self._read(self.proc_root / "sys" / "net" / "ipv4" / "conf" / self.interface / "forwarding") != "0":
            self._fail()
        if self._read(self.proc_root / "sys" / "net" / "ipv6" / "conf" / self.interface / "forwarding") != "0":
            self._fail()
        for key in ("dhcp4", "dhcp6"):
            output = self._run(["netplan", "get", f"ethernets.{self.interface}.{key}"])
            if output.stdout.strip().lower() != "false":
                self._fail()
        self._active_dhcp_defense()
        try:
            active = self.runner(["systemctl", "is-active", "NetworkManager"], capture_output=True, text=True, check=False)
        except FileNotFoundError:
            active = None
        if active is not None and active.returncode == 0 and active.stdout.strip() == "active":
            profiles = self._run(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"])
            if any(line.rsplit(":", 1)[-1] == self.interface for line in profiles.stdout.splitlines() if line):
                self._fail()

    def _active_dhcp_defense(self) -> None:
        try:
            entries = tuple(self.proc_root.iterdir())
        except OSError:
            self._fail()
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                tokens = (entry / "cmdline").read_bytes().split(b"\0")
                decoded = [token.decode("utf-8", "strict") for token in tokens if token]
            except FileNotFoundError:
                continue
            except (OSError, UnicodeDecodeError):
                self._fail()
            if not decoded:
                continue
            executable = os.path.basename(decoded[0])
            interface_argument = any(token == self.interface or token == f"--interface={self.interface}" for token in decoded[1:])
            if executable in {"dhclient", "dhcpcd", "udhcpc"} and interface_argument:
                self._fail()

    def _json(self, command: list[str]) -> object:
        output = self._run(command)
        try:
            return json.loads(output.stdout)
        except (TypeError, ValueError):
            self._fail()

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        result = self.runner(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self._fail()
        return result

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="ascii").strip()
        except OSError as exc:
            raise SensorPreflightError("capture_interface_unavailable") from exc

    @staticmethod
    def _fail() -> None:
        raise SensorPreflightError("capture_interface_unavailable")


class RawCapture:
    def __init__(self, interface: str, *, socket_factory=socket.socket) -> None:
        self.interface = interface
        self._socket_factory = socket_factory
        self.socket: socket.socket | None = None

    def open(self) -> None:
        raw = self._socket_factory(
            socket.AF_PACKET,
            socket.SOCK_RAW,
            socket.htons(0x0003),
        )
        try:
            raw.settimeout(RECEIVE_POLL_SECONDS)
            raw.setsockopt(socket.SOL_SOCKET, SO_TIMESTAMPNS, 1)
            attach_frozen_filter(raw)
            raw.bind((self.interface, 0))
        except Exception:
            raw.close()
            raise
        self.socket = raw

    def receive(self, size: int = 65535) -> tuple[bytes, int, str] | None:
        if self.socket is None:
            raise RuntimeError("capture is closed")
        try:
            data, ancillary, flags, _address = self.socket.recvmsg(size, 256)
        except (socket.timeout, TimeoutError):
            return None
        if flags & getattr(socket, "MSG_TRUNC", 0):
            raise SensorPreflightError("raw_frame_truncated")
        timestamp_ns = None
        for level, kind, payload in ancillary:
            if level == socket.SOL_SOCKET and kind == SO_TIMESTAMPNS and len(payload) >= 16:
                seconds, nanos = struct.unpack("qq", payload[:16])
                timestamp_ns = seconds * 1_000_000_000 + nanos
                break
        if timestamp_ns is None:
            raise SensorPreflightError("kernel_timestamp_unavailable")
        observed = format_utc(datetime.fromtimestamp(timestamp_ns / 1_000_000_000, timezone.utc))
        return data, timestamp_ns, observed

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None
