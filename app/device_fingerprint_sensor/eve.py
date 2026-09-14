"""Bounded Unix-datagram receiver for minimized Suricata EVE."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any

RECEIVE_POLL_SECONDS = 1.0


class EveReceiver:
    def __init__(self, path: str, *, max_datagram_bytes: int = 262144, socket_factory=socket.socket) -> None:
        self.path = Path(path)
        self.max_datagram_bytes = max_datagram_bytes
        self._socket_factory = socket_factory
        self.socket: socket.socket | None = None
        self.truncated = 0
        self.invalid = 0

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        os.chmod(self.path.parent, 0o750)
        if os.name == "posix":
            import grp
            os.chown(self.path.parent, -1, grp.getgrnam("fingerprint-eve").gr_gid)
        if self.path.exists() or self.path.is_socket():
            self.path.unlink()
        server = self._socket_factory(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            server.settimeout(RECEIVE_POLL_SECONDS)
            server.bind(str(self.path))
            os.chmod(self.path, 0o660)
            if os.name == "posix":
                import grp
                os.chown(self.path, -1, grp.getgrnam("fingerprint-eve").gr_gid)
        except Exception:
            server.close()
            raise
        self.socket = server

    def receive(self) -> dict[str, Any] | None:
        if self.socket is None:
            raise RuntimeError("EVE receiver is closed")
        try:
            data, _ancillary, flags, _address = self.socket.recvmsg(self.max_datagram_bytes + 1, 0)
        except (socket.timeout, TimeoutError):
            return None
        if flags & getattr(socket, "MSG_TRUNC", 0) or len(data) > self.max_datagram_bytes:
            self.truncated += 1
            return None
        try:
            value = json.loads(data.decode("utf-8", "strict"))
        except (UnicodeDecodeError, ValueError):
            self.invalid += 1
            return None
        if not isinstance(value, dict):
            self.invalid += 1
            return None
        return value

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
