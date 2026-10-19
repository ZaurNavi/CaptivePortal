"""Bounded private UNIX stream frames; no path-bearing public request."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import stat
import struct
import time

from . import contracts as c

COORDINATOR_SOCKET = "/run/captive-portal/db-audit/coordinator.sock"


def peer_scope(connection,allowed_uids):
    if os.name!="posix" or not hasattr(socket,"SO_PEERCRED") or connection.family!=socket.AF_UNIX:
        raise c.CoordinatorError("unauthorized")
    try:pid,uid,gid=struct.unpack("3i",connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
    except (OSError,ValueError):raise c.CoordinatorError("unauthorized") from None
    if uid not in allowed_uids or pid<=0:raise c.CoordinatorError("unauthorized")
    return c.scope(uid)


def receive(connection,*,limit=c.MAX_FRAME,seconds=1.0):
    deadline=time.monotonic()+seconds
    def exact(length):
        value=bytearray()
        while len(value)<length:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise c.CoordinatorError("invalid_request")
            connection.settimeout(remaining)
            chunk=connection.recv(length-len(value))
            if not chunk:raise c.CoordinatorError("invalid_request")
            value.extend(chunk)
        return bytes(value)
    try:
        length=struct.unpack("!I",exact(4))[0]
        if not 0<length<=limit:raise c.CoordinatorError("invalid_request")
        return c.decode(exact(length),limit)
    except (OSError,ValueError):raise c.CoordinatorError("invalid_request") from None


def send(connection,value,*,limit=c.MAX_FRAME):
    raw=c.encode(value,limit)
    connection.settimeout(1.0)
    connection.sendall(struct.pack("!I",len(raw))+raw)


def submit_request(value, *, _socket_path=COORDINATOR_SOCKET):
    """Submit ONLY; fixed operational path, no source configuration/fallback.

    Private socket keyword is a disposable test seam, not a CLI/env override.
    """
    c.request(value)
    if value["op"] != "submit": raise c.CoordinatorError("invalid_request")
    remote_error = False
    try:
        if os.name != "posix" or not hasattr(socket, "SO_PEERCRED"):
            raise c.CoordinatorError("coordinator_unavailable")
        if _socket_path==COORDINATOR_SOCKET:
            from .operator_cli import request as operational_request
            reply=operational_request(value)
        else:
            # Existing private disposable G1 seam, never a CLI path override.
            from .locks import protected_parent
            path = protected_parent(Path(_socket_path), os.geteuid())
            metadata = path.lstat()
            if (not stat.S_ISSOCK(metadata.st_mode) or metadata.st_mode & 0o077
                    or metadata.st_uid not in {0, os.geteuid()}):
                raise c.CoordinatorError("coordinator_unavailable")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(1.0)
                connection.connect(str(path))
                peer_scope(connection, {0, os.geteuid()})
                send(connection, value)
                reply = receive(connection)
        if type(reply) is dict and set(reply) == {"error"}:
            remote_error = True
            raise c.CoordinatorError(reply["error"])
        c.closed(reply, {"status", "job"})
        if reply["status"] not in {"queued", "duplicate"} or type(reply["job"]) is not dict:
            raise c.CoordinatorError("coordinator_unavailable")
        c.identifier(reply["job"].get("job_id"))
        if reply["job"].get("store_id") != value["store_id"]:
            raise c.CoordinatorError("coordinator_unavailable")
        return dict(store_id=value["store_id"], status=reply["status"], job_id=reply["job"]["job_id"])
    except c.CoordinatorError as error:
        if remote_error and error.code in {"store_busy", "queue_full", "invalid_request"}:
            raise
        raise c.CoordinatorError("coordinator_unavailable") from None
    except (OSError, ValueError, KeyError, TypeError):
        raise c.CoordinatorError("coordinator_unavailable") from None
