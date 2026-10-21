"""Disposable, bounded two-store metadata; no database content or health claim."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import stat
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

SCHEMA = "captivprod.ops.sensor-metadata.v1"
SCHEMA_V2 = "captivprod.ops.sensor-metadata.v2"
UNIT = "fingerprint-sensor.service"
DIRECTORY = "/run/captiveportal-operations"
CHILD = "sensor"
REPORT = "metadata.json"
LIMIT = 4096
INTERVAL = 60.0
TTL = 180.0
BUDGET = 0.05
MAXIMUM = (1 << 53) - 1
COMPONENTS = {"network_attribution": {"main": "", "wal": "-wal", "shm": "-shm"},
              "sensor_spool": {"main": "", "wal": "-wal", "shm": "-shm", "journal": "-journal"}}
REASONS = frozenset({"permission_denied", "unsafe_file", "stat_unavailable", "sample_timeout",
                     "identity_collision", "source_disabled"})


class MetadataUnavailable(ValueError):
    pass


def require(condition):
    if not condition:
        raise MetadataUnavailable()


def integer(value, maximum=MAXIMUM, minimum=0):
    return type(value) is int and minimum <= value <= maximum


def boot_ns():
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME) if hasattr(time, "CLOCK_BOOTTIME") else time.monotonic_ns()


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_stamp(value):
    require(type(value) is str and len(value) == 24)
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    require(stamp(parsed) == value)
    return parsed


def _bounded_proc(path, limit, owner=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and (owner is None or info.st_uid == owner))
        raw = os.read(fd, limit + 1)
        require(len(raw) <= limit)
        return raw
    finally:
        os.close(fd)


def process_identity(pid, uid):
    require(sys.platform == "linux" and integer(pid, (1 << 31) - 1, 1))
    boot = _bounded_proc("/proc/sys/kernel/random/boot_id", 40).decode("ascii").strip()
    require(str(uuid.UUID(boot)) == boot)
    fields = _bounded_proc(f"/proc/{pid}/stat", 4096, uid).rsplit(b") ", 1)[1].split()
    started = int(fields[19])
    require(integer(started, minimum=1))
    return {"boot_id": boot, "pid": pid, "start_ticks": started}


def _tmpfs(fd):
    require(sys.platform == "linux")
    # fstatfs writes at most the native Linux struct statfs into this oversized
    # aligned buffer. Only f_type is used; no mount-table scan or shell probe.
    buffer = (ctypes.c_long * 64)()
    call = ctypes.CDLL(None, use_errno=True).fstatfs
    call.argtypes, call.restype = [ctypes.c_int, ctypes.c_void_p], ctypes.c_int
    require(call(fd, ctypes.byref(buffer)) == 0 and buffer[0] == 0x01021994)


@dataclass(frozen=True)
class Channel:
    sensor_uid: int
    reader_gid: int
    directory: str = DIRECTORY

    def open(self):
        require(sys.platform == "linux")
        parts = self.directory.split("/")
        require(parts[0] == "" and 1 < len(parts) <= 16 and all(p and p not in {".", ".."} for p in parts[1:]))
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            root = os.fstat(fd)
            require(root.st_uid == 0 and not root.st_mode & 0o022)
            for part in parts[1:]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                os.close(fd)
                fd = next_fd
                info = os.fstat(fd)
                require(info.st_uid == 0 and not info.st_mode & 0o022)
            _tmpfs(fd)
            child = os.open(CHILD, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            try:
                info = os.fstat(child)
                require(info.st_uid == self.sensor_uid and info.st_gid == self.reader_gid
                        and stat.S_IMODE(info.st_mode) == 0o2750)
            except BaseException:
                os.close(child)
                raise
            return child
        finally:
            os.close(fd)

    def validate_file(self, info):
        require(stat.S_ISREG(info.st_mode) and info.st_uid == self.sensor_uid
                and info.st_gid == self.reader_gid and stat.S_IMODE(info.st_mode) == 0o640
                and info.st_nlink == 1 and 0 <= info.st_size <= LIMIT)


def configured_channel():
    import grp
    import pwd
    account = pwd.getpwnam("fingerprint-sensor")
    uid = account.pw_uid
    gid = grp.getgrnam("captiveportal-ops-reader").gr_gid
    require(uid > 0 and gid > 0 and gid != account.pw_gid)
    return Channel(uid, gid)


def unknown(reason):
    return {"presence": "unknown", "bytes": None, "reason": reason}


def collect_components(paths, uid, *, deadline, monotonic=time.monotonic, cancel=None, lstat=os.lstat):
    require(set(paths) == set(COMPONENTS))
    stores, identities = {}, {}
    for identity, components in COMPONENTS.items():
        stores[identity] = {}
        path = paths[identity]
        require(path is None or (type(path) is str and path.startswith("/") and "\0" not in path and len(path) <= 4096))
        for component, suffix in components.items():
            row = unknown("source_disabled") if path is None else unknown("sample_timeout")
            if path is not None and monotonic() < deadline and not (cancel and cancel.is_set()):
                try:
                    info = lstat(path + suffix)
                    if monotonic() >= deadline or (cancel and cancel.is_set()):
                        pass
                    elif (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_nlink != 1 or not integer(info.st_size)):
                        row = unknown("unsafe_file")
                    else:
                        row = {"presence": "present", "bytes": info.st_size, "reason": None}
                        identities.setdefault((info.st_dev, info.st_ino), []).append((identity, component))
                except FileNotFoundError:
                    row = {"presence": "absent", "bytes": 0, "reason": None}
                except PermissionError:
                    row = unknown("permission_denied")
                except OSError:
                    row = unknown("stat_unavailable")
            stores[identity][component] = row
    for aliases in identities.values():
        if len(aliases) > 1:
            for identity, component in aliases:
                stores[identity][component] = unknown("identity_collision")
    return stores


def decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= LIMIT)
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    def constant(_value):
        raise MetadataUnavailable()
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    require(type(value) is dict)
    v2 = value.get("schema_version") == SCHEMA_V2
    require(set(value) == {"schema_version", "producer_unit", "producer", "epoch", "sequence",
        "sample_time_utc", "sample_boottime_ns", "source_status", "stores"} | ({"application_health"} if v2 else set()))
    require(value["schema_version"] in {SCHEMA, SCHEMA_V2} and value["producer_unit"] == UNIT)
    if v2:
        from app.operations_health import validate
        validate(value["application_health"], UNIT)
    producer = value["producer"]
    require(type(producer) is dict and set(producer) == {"boot_id", "pid", "start_ticks"})
    require(type(producer["boot_id"]) is str and str(uuid.UUID(producer["boot_id"])) == producer["boot_id"])
    require(integer(producer["pid"], (1 << 31)-1, 1) and integer(producer["start_ticks"], minimum=1))
    require(type(value["epoch"]) is str and str(uuid.UUID(value["epoch"])) == value["epoch"])
    require(integer(value["sequence"], minimum=1) and integer(value["sample_boottime_ns"], (1 << 63)-1))
    parse_stamp(value["sample_time_utc"])
    require(type(value["stores"]) is dict and set(value["stores"]) == set(COMPONENTS))
    partial = False
    for identity, components in COMPONENTS.items():
        rows = value["stores"][identity]
        require(type(rows) is dict and set(rows) == set(components))
        for row in rows.values():
            require(type(row) is dict and set(row) == {"presence", "bytes", "reason"})
            presence = row["presence"]
            require(type(presence) is str and presence in {"present", "absent", "unknown"})
            if presence == "unknown":
                require(row["bytes"] is None and type(row["reason"]) is str and row["reason"] in REASONS)
                partial = True
            else:
                require(integer(row["bytes"]) and row["reason"] is None and (presence != "absent" or row["bytes"] == 0))
    require(value["source_status"] == ("partial" if partial else "complete"))
    return value


class SensorMetadataPublisher:
    def __init__(self, paths, *, channel=configured_channel, monotonic=time.monotonic,
                 now=lambda: datetime.now(timezone.utc), boottime=boot_ns, identity=process_identity, enabled=None,
                 health_provider=None):
        self.paths = dict(paths)
        self.channel, self.monotonic, self.now, self.boottime, self.identity = channel, monotonic, now, boottime, identity
        self.epoch, self.sequence, self.last_attempt = str(uuid.uuid4()), 0, None
        self.lock = threading.Lock()
        self.health_provider = health_provider
        # The SAME existing Operations startup flag; no second enable switch.
        # Sensor's deployment environment must explicitly opt in too.
        self.enabled = os.environ.get("WEB_ADMIN_DB_SERVICES_ENABLED", "false") == "true" if enabled is None else enabled is True

    def publish(self, cancel, *, health=None):
        if not self.enabled or cancel.is_set() or not self.lock.acquire(blocking=False):
            return False
        directory, fd, temporary = None, None, None
        try:
            tick = self.monotonic()
            if self.last_attempt is not None and tick - self.last_attempt < INTERVAL:
                return False
            self.last_attempt = tick
            deadline = tick + BUDGET
            channel = self.channel()
            require(os.geteuid() == channel.sensor_uid)
            directory = channel.open()
            producer = self.identity(os.getpid(), channel.sensor_uid)
            stores = collect_components(self.paths, channel.sensor_uid, deadline=deadline,
                monotonic=self.monotonic, cancel=cancel)
            self.sequence += 1
            value = dict(schema_version=SCHEMA, producer_unit=UNIT, producer=producer, epoch=self.epoch,
                sequence=self.sequence, sample_time_utc=stamp(self.now()), sample_boottime_ns=self.boottime(),
                source_status="partial" if any(r["presence"] == "unknown" for rows in stores.values() for r in rows.values()) else "complete",
                stores=stores)
            if health is None and self.health_provider is not None:
                health = self.health_provider()
            if health is not None:
                value.update(schema_version=SCHEMA_V2, application_health=health)
            raw = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
            decode(raw)
            require(not cancel.is_set() and self.monotonic() < deadline)
            try:
                existing = os.stat(REPORT, dir_fd=directory, follow_symlinks=False)
                channel.validate_file(existing)
                require(existing.st_dev == os.fstat(directory).st_dev)
            except FileNotFoundError:
                pass
            temporary = ".metadata-" + uuid.uuid4().hex
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         0o640, dir_fd=directory)
            channel.validate_file(os.fstat(fd))
            require(os.write(fd, raw) == len(raw))
            os.close(fd)
            fd = None
            require(not cancel.is_set() and self.monotonic() < deadline)
            os.replace(temporary, REPORT, src_dir_fd=directory, dst_dir_fd=directory)
            temporary = None
            return True
        except Exception:
            return False
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if temporary is not None and directory is not None:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except OSError:
                    pass
            if directory is not None:
                try:
                    os.close(directory)
                except OSError:
                    pass
            self.lock.release()


class SensorMetadataReader:
    def __init__(self, *, channel=configured_channel, boottime=boot_ns, identity=process_identity):
        self.channel, self.boottime, self.identity = channel, boottime, identity
        self.last = None

    def read(self, service, now, *, deadline, monotonic=time.monotonic, cancel=None):
        directory, fd = None, None
        try:
            require(not (cancel and cancel.is_set()) and monotonic() < deadline)
            require(service["operational_state"] == "running" and service["main_pid"] is not None)
            channel = self.channel()
            directory = channel.open()
            fd = os.open(REPORT, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
            before = os.fstat(fd)
            channel.validate_file(before)
            require(before.st_dev == os.fstat(directory).st_dev)
            raw = os.read(fd, LIMIT + 1)
            after = os.fstat(fd)
            channel.validate_file(after)
            require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns))
            current = os.stat(REPORT, dir_fd=directory, follow_symlinks=False)
            channel.validate_file(current)
            require((before.st_dev, before.st_ino) == (current.st_dev, current.st_ino) and len(raw) == before.st_size)
            value = decode(raw)
            producer = self.identity(service["main_pid"], channel.sensor_uid)
            require(value["producer"] == producer)
            require(value["sample_boottime_ns"] >= producer["start_ticks"] * 1_000_000_000 // os.sysconf("SC_CLK_TCK"))
            sampled = parse_stamp(value["sample_time_utc"])
            require(sampled >= datetime.fromisoformat(service["started_at_utc"].replace("Z", "+00:00")))
            age = (now - sampled).total_seconds()
            boot_age = (self.boottime() - value["sample_boottime_ns"]) / 1_000_000_000
            require(age >= 0 and boot_age >= 0 and abs(age - boot_age) <= 5)
            digest = hashlib.sha256(raw).digest()
            if self.last is not None and self.last[0] == producer:
                require(value["epoch"] == self.last[1] and value["sequence"] >= self.last[2])
                require(sampled >= self.last[4] and value["sample_boottime_ns"] >= self.last[5])
                if value["sequence"] == self.last[2]:
                    require(digest == self.last[3])
            require(monotonic() < deadline and not (cancel and cancel.is_set()))
            if max(age, boot_age) > TTL:
                return {"status": "stale", "reason": "metadata_stale", "stores": None}
            self.last = producer, value["epoch"], value["sequence"], digest, sampled, value["sample_boottime_ns"]
            return {"status": "fresh", "reason": None, "stores": value["stores"],
                    "expires_boottime_ns": value["sample_boottime_ns"] + int(TTL * 1_000_000_000),
                    **({"health": value["application_health"], "observed_at": value["sample_time_utc"],
                        "age": max(age, boot_age), "producer": producer} if "application_health" in value else {})}
        except Exception:
            return {"status": "unknown", "reason": "metadata_unavailable", "stores": None}
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if directory is not None:
                try:
                    os.close(directory)
                except OSError:
                    pass
