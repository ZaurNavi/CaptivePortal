"""Manual Evidence-only RAM snapshot audit. Never imported by service startup."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
import uuid
from datetime import datetime, timezone

from . import validation as v
from .models import DeviceFingerprintStorageCorrupt, DeviceFingerprintStorageUnavailable, DeviceFingerprintWriterUnavailable
from .repository import DeviceFingerprintRepository, _existing_file_target, writer_lock

STORE_ID = "fingerprint_evidence"
STATUS_PATH = Path("/opt/CaptivePortal/data/audit-status/fingerprint_evidence.json")
CONTRACT = "db_audit_status.v1"
METHOD = "sqlite_backup_memory_t3_v1"
BACKUP_PAGES = 256
BACKUP_SLEEP = 0.05
RUN_SECONDS = 7200
REPORT_MAX = 32768
MAX_INT = 9223372036854775807
GIB = 1024 ** 3
RESOURCE_OBSERVATION_SECONDS = .25


class AuditStop(Exception):
    def __init__(self, category):
        self.category = category
        super().__init__(category)


def utc():
    return v.format_utc(datetime.now(timezone.utc))


def checked(value):
    if type(value) is not int or not 0 <= value <= MAX_INT:
        raise AuditStop("resource_deferred")
    return value


def memory_admission(image, facts):
    """Frozen LAB R1 profile; no automatic threshold reduction or disk fallback."""
    image = checked(image)
    if not isinstance(facts, dict) or not {"mem_total","mem_available","swap_active","cgroup_headroom","address_headroom","containment"} <= facts.keys():
        raise AuditStop("resource_deferred")
    total, available = checked(facts["mem_total"]), checked(facts["mem_available"])
    if not 0 < available <= total or facts["swap_active"] is not False:
        raise AuditStop("resource_deferred")
    reserve = max(2 * GIB, (15 * total + 99) // 100)
    required = checked((9 * image + 3) // 4 + reserve)
    headrooms = [available]
    for name in ("cgroup_headroom", "address_headroom"):
        if facts[name] is not None:
            headrooms.append(checked(facts[name]))
    if facts["containment"] is not True or min(headrooms) < required:
        raise AuditStop("resource_deferred")
    return dict(profile="lab_ram_r1_2_25_reserve_v1", image_bytes=image,
                reserve_bytes=reserve, required_available=required, headroom=min(headrooms))


def resource_facts():
    """Measure quiet counters over a real interval, never infer absent activity."""
    try:
        first = _resource_snapshot()
        started = time.monotonic()
        time.sleep(RESOURCE_OBSERVATION_SECONDS)
        second = _resource_snapshot()
        elapsed = time.monotonic() - started
        if not RESOURCE_OBSERVATION_SECONDS <= elapsed <= RUN_SECONDS:
            raise AuditStop("resource_deferred")
        activity = {}
        for name, keys in (("swap_counters", ("pswpin", "pswpout")),
                           ("reclaim_counters", ("pgscan_direct", "pgsteal_direct"))):
            deltas = []
            for key in keys:
                before, after = checked(first[name][key]), checked(second[name][key])
                if after < before: raise AuditStop("resource_deferred")
                deltas.append(after - before)
            activity[name] = any(deltas)
        second["swap_active"] = activity["swap_counters"]
        if second["swap_active"] or activity["reclaim_counters"]:
            raise AuditStop("resource_deferred")
        if first["containment"] is not True or second["containment"] is not True:
            raise AuditStop("resource_deferred")
        second["observation_interval_seconds"] = elapsed
        return second
    except AuditStop: raise
    except Exception: raise AuditStop("resource_deferred") from None


def _resource_snapshot():
    """Fail closed outside qualified Linux containment; never changes OS limits."""
    if os.name != "posix" or not Path("/proc/self/status").is_file():
        raise AuditStop("resource_deferred")
    import resource
    def fields(path):
        result = {}
        for line in Path(path).read_text(encoding="ascii").splitlines():
            key, _, value = line.partition(":")
            if value.strip().endswith(" kB"):
                result[key] = checked(int(value.split()[0]) * 1024)
        return result
    memory, process = fields("/proc/meminfo"), fields("/proc/self/status")
    swaps, reclaim = {}, {}
    for line in Path("/proc/vmstat").read_text(encoding="ascii").splitlines():
        name, value = line.split()
        if name in {"pswpin", "pswpout"}: swaps[name] = checked(int(value))
        if name in {"pgscan_direct", "pgsteal_direct"}: reclaim[name] = checked(int(value))
    if len(swaps) != 2 or len(reclaim) != 2: raise AuditStop("resource_deferred")
    memberships = Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
    paths = [line[3:] for line in memberships if line.startswith("0::")]
    if len(paths) != 1 or ".." in Path(paths[0]).parts: raise AuditStop("resource_deferred")
    group = Path("/sys/fs/cgroup") / paths[0].lstrip("/")
    # Include every hierarchical limit, not only the leaf cgroup.
    headroom = None
    for directory in (group, *group.parents):
        if directory == Path("/sys/fs"): break
        maximum = (directory / "memory.max").read_text(encoding="ascii").strip()
        current = checked(int((directory / "memory.current").read_text(encoding="ascii")))
        if maximum != "max":
            room = max(0, checked(int(maximum)) - current)
            headroom = room if headroom is None else min(headroom, room)
    soft, _hard = resource.getrlimit(resource.RLIMIT_AS)
    address = max(0, soft - process["VmSize"]) if 0 < soft < MAX_INT else None
    def pressure(name):
        path = Path("/proc/pressure") / name
        return path.read_text(encoding="ascii")[:512] if path.exists() else None
    return dict(mem_total=memory["MemTotal"], mem_available=memory["MemAvailable"],
        swap_counters=swaps, reclaim_counters=reclaim, cgroup_headroom=headroom, address_headroom=address,
        containment=headroom is not None or address is not None,
        peak_rss_bytes=process["VmHWM"], memory_psi=pressure("memory"), io_psi=pressure("io"))


def _protected(path, directory=False):
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not (stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)):
        raise AuditStop("unsafe_path")
    if os.name == "posix":
        if metadata.st_uid not in {0, os.geteuid()} or metadata.st_mode & (0o022 if directory else 0o077):
            # A root-owned sticky ancestor (e.g. /tmp for disposable fixtures)
            # cannot authorize another user to replace our protected child.
            if not (directory and metadata.st_uid == 0 and metadata.st_mode & stat.S_ISVTX):
                raise AuditStop("unsafe_path")
    return metadata


def protected_parent(path):
    if not path.is_absolute(): raise AuditStop("unsafe_path")
    for parent in (path.parent, *path.parent.parents): _protected(parent, True)


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError("duplicate member")
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError("nonfinite value")


def _status_read_descriptor(path):
    return os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))


class StatusStore:
    def __init__(self, path=STATUS_PATH):
        self.path = Path(path)

    def read(self):
        protected_parent(self.path)
        try:
            _protected(self.path)
        except FileNotFoundError:
            return dict(audit_contract_version=CONTRACT, last_attempt=dict(status="never_run"), last_verified_success=None)
        descriptor = _status_read_descriptor(self.path)
        with os.fdopen(descriptor, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode): raise AuditStop("report_unavailable")
            raw = handle.read(REPORT_MAX + 1)
        if len(raw) > REPORT_MAX: raise AuditStop("report_unavailable")
        try:
            value = json.loads(raw, object_pairs_hook=_json_pairs, parse_constant=_nonfinite)
            if (set(value) != {"audit_contract_version", "last_attempt", "last_verified_success"}
                    or value["audit_contract_version"] != CONTRACT or not isinstance(value["last_attempt"], dict)
                    or value["last_verified_success"] is not None and not isinstance(value["last_verified_success"], dict)):
                raise ValueError()
            for attempt in (value["last_attempt"], value["last_verified_success"]):
                if attempt is None: continue
                if attempt.get("status") == "never_run" and attempt is value["last_attempt"]: continue
                if (attempt.get("status") not in {"queued","running","passed","failed","incomplete","stale"}
                        or attempt.get("store_id") != STORE_ID or attempt.get("audit_contract_version") != CONTRACT
                        or attempt.get("audit_method_version") != METHOD): raise ValueError()
                v.validate_uuid(attempt.get("run_id"))
            if value["last_verified_success"] is not None and value["last_verified_success"].get("status") != "passed": raise ValueError()
            return value
        except (ValueError, TypeError): raise AuditStop("report_unavailable") from None

    def write(self, value):
        protected_parent(self.path)
        if self.path.exists() or self.path.is_symlink(): _protected(self.path)
        raw = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode()
        if len(raw) > REPORT_MAX: raise AuditStop("report_unavailable")
        temporary = self.path.with_name("." + self.path.name + "." + str(uuid.uuid4()) + ".tmp")
        descriptor = None
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                handle.write(raw); handle.flush(); os.fsync(handle.fileno())
            # Native Windows rename can transiently refuse an open monitoring
            # reader. Retry ONLY that sharing/access refusal, <=70 ms total;
            # persistent refusal remains report failure, never fake success.
            for attempt in range(8):
                try:
                    if self.path.exists() or self.path.is_symlink(): _protected(self.path)
                    os.replace(temporary, self.path)
                    break
                except PermissionError as exc:
                    if os.name != "nt" or getattr(exc, "winerror", None) not in {5,32,33} or attempt == 7:
                        raise
                    time.sleep(.01)
            if os.name == "posix":
                directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try: os.fsync(directory)
                finally: os.close(directory)
        finally:
            if descriptor is not None: os.close(descriptor)
            if temporary.exists(): temporary.unlink()  # Only our O_EXCL run-owned temp.


def _identity(path):
    try: _existing_file_target(path, error_type=DeviceFingerprintStorageUnavailable, label="audit source")
    except DeviceFingerprintStorageUnavailable: raise AuditStop("source_unavailable") from None
    protected_parent(path)
    metadata = path.lstat()
    if os.name == "posix" and (metadata.st_uid not in {0, os.geteuid()} or metadata.st_mode & 0o022):
        raise AuditStop("unsafe_path")
    if metadata.st_nlink != 1: raise AuditStop("unsafe_path")
    return dict(device=metadata.st_dev, inode=metadata.st_ino, bytes=checked(metadata.st_size))


def _sidecars(source):
    result = {}
    for suffix in ("-wal", "-shm"):
        try:
            metadata = Path(str(source)+suffix).lstat()
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or
                    os.name == "posix" and (metadata.st_uid not in {0, os.geteuid()} or metadata.st_mode & 0o022)):
                raise AuditStop("unsafe_path")
            result[suffix] = checked(metadata.st_size)
        except FileNotFoundError: result[suffix] = 0
    return result


def validate_snapshot(connection, guard, domain_started=lambda: None):
    """Full T3 on completed RAM snapshot only; stream rows, never retain PII."""
    DeviceFingerprintRepository._validate_runtime_connection(connection)
    count, bad = 0, False
    for row in connection.execute("PRAGMA integrity_check"):
        count += 1
        bad |= tuple(row) != ("ok",)
        guard()
    if count != 1 or bad: raise AuditStop("integrity_suspect")
    tables = ("device_fingerprint_evidence", "device_fingerprint_source_health_events")
    applicable = any(list(connection.execute(f"PRAGMA foreign_key_list({table})")) for table in tables)
    if applicable:
        violations = 0
        for _row in connection.execute("PRAGMA foreign_key_check"):
            violations += 1; guard()
        if violations: raise AuditStop("integrity_suspect")
    domain_started()
    allocator = DeviceFingerprintRepository._validate_storage_state(connection)
    totals = {}
    for table in tables:
        # Canonical immutable identities + digest consistency, not a newly
        # invented current producer authorization or historical age policy.
        if table == tables[0]:
            too_large = connection.execute(f"SELECT 1 FROM {table} NOT INDEXED WHERE length(CAST(payload_json AS BLOB))>65536 LIMIT 1").fetchone()
            if too_large: raise AuditStop("integrity_suspect")
        totals[table] = 0
        for row in connection.execute(f"SELECT * FROM {table} NOT INDEXED"):
            guard(); row = dict(row); totals[table] += 1
            if type(row["ingest_sequence"]) is not int or not 1 <= row["ingest_sequence"] <= allocator:
                raise AuditStop("integrity_suspect")
            for name in ("producer_id", "capture_source_id"): v.validate_machine_id(row[name])
            v.validate_site_id(row["site_id"]); v.validate_source_kind(row["source_kind"])
            for name in ("observed_at", "ingested_at"): v.parse_utc(row[name])
            if table == tables[0]:
                v.validate_uuid(row["evidence_id"]); v.validate_uuid(row["source_event_id"])
                v.validate_nullable_machine_id(row["source_subtype"])
                v.validate_machine_id(row["extractor_name"]); v.validate_version(row["extractor_version"])
                v.validate_feature_schema_version(row["feature_schema_version"])
                if row["rule_version"] is not None: v.validate_version(row["rule_version"])
                if v.validate_mac(row["observed_mac"]) != row["observed_mac"] or v.validate_ip(row["observed_ip"]) != row["observed_ip"]:
                    raise AuditStop("integrity_suspect")
                v.validate_quality(row["quality_state"])
                payload = json.loads(row["payload_json"])
                if not isinstance(payload, dict) or v.canonical_json(payload) != row["payload_json"] or v.canonical_sha256(row["payload_json"]) != row["payload_sha256"]:
                    raise AuditStop("integrity_suspect")
            else:
                v.validate_uuid(row["source_health_id"]); v.validate_uuid(row["source_health_event_id"])
                v.validate_health_status(row["status"]); v.validate_reason_code(row["reason_code"])
                names = ("producer_id", "source_health_event_id", "site_id", "capture_source_id", "source_kind", "status", "reason_code", "observed_at")
                if v.canonical_sha256(v.canonical_json({key:row[key] for key in names})) != row["content_sha256"]:
                    raise AuditStop("integrity_suspect")
    collision = connection.execute("SELECT 1 FROM device_fingerprint_evidence AS e JOIN device_fingerprint_source_health_events AS h ON e.ingest_sequence=h.ingest_sequence LIMIT 1").fetchone()
    if collision: raise AuditStop("integrity_suspect")
    return dict(integrity="ok", foreign_keys="checked" if applicable else "not_applicable", domain="passed", rows=totals)


class EvidenceAuditor:
    """Dependencies are injectable for disposable focused fixtures, not CLI paths."""
    def __init__(self, source, *, status=None, resources=resource_facts, connect=sqlite3.connect,
                 monotonic=time.monotonic, now=utc, canceled=lambda: False, source_commit=None):
        self.source = Path(source)
        self.store = status or StatusStore()
        self.resources, self.connect, self.clock = resources, connect, monotonic
        self.now, self.canceled, self.source_commit = now, canceled, source_commit

    def run(self):
        try:
            protected_parent(self.store.path)
            lock_path = self.store.path.with_suffix(".audit.lock")
            if lock_path.exists() or lock_path.is_symlink():
                metadata = lock_path.lstat()
                if not stat.S_ISREG(metadata.st_mode) or (os.name == "posix" and
                        (metadata.st_uid not in {0, os.geteuid()} or metadata.st_mode & 0o022)):
                    raise AuditStop("unsafe_path")
            with writer_lock(str(lock_path)):
                return self._locked_run()
        except DeviceFingerprintWriterUnavailable:
            return dict(status="incomplete", category_code="already_running"), 2
        except Exception:
            return dict(status="incomplete", category_code="report_unavailable"), 5

    def _locked_run(self):
        prior = self.store.read()
        recovered = None
        if prior["last_attempt"].get("status") == "running":
            prior["last_attempt"].update(status="incomplete", category_code="previous_owner_interrupted", finished_at_utc=self.now())
            recovered = {key:prior["last_attempt"].get(key) for key in ("run_id", "status", "category_code", "finished_at_utc")}
            self.store.write(prior)
        started = self.clock()
        record = dict(store_id=STORE_ID, run_id=str(uuid.uuid4()), trigger="manual", status="running", stage="preflight",
            created_at_utc=self.now(), started_at_utc=self.now(), finished_at_utc=None, snapshot_at_utc=None,
            source_path_identity=None, database_generation_id=None, snapshot_last_ingest_sequence=None,
            sqlite_version=sqlite3.sqlite_version, audit_contract_version=CONTRACT, source_commit=self.source_commit,
            audit_method_version=METHOD, duration_seconds=0, category_code=None, check_summary={}, schedule_policy_id=None,
            report_written_at_utc=self.now(), source_page_count=None, source_page_size=None,
            backup_progress_summary=dict(steps=0, remaining=None, total=None, restarts=0, completed=False), memory_admission_summary=None,
            peak_rss_bytes=None, logical_snapshot_bytes=None, snapshot_wal_state=None,
            clock_confidence="host_utc_unattested_monotonic_duration", lock_owner=dict(pid=os.getpid()),
            snapshot_time_semantics="backup_completion_observation_not_start_time", directory_fsync=os.name == "posix")
        record["previous_attempt_recovery"] = recovered
        document = dict(audit_contract_version=CONTRACT, last_attempt=record, last_verified_success=prior["last_verified_success"])
        self.store.write(document)
        source = destination = None
        last_probe, last_facts, image, stop = [-float("inf")], [None], [0], [None]
        def guard(force=False):
            if self.canceled(): raise AuditStop("canceled")
            if self.clock() - started >= RUN_SECONDS: raise AuditStop("deadline")
            if force or self.clock() - last_probe[0] >= .25:
                try:
                    facts = self.resources()
                    if self.canceled(): raise AuditStop("canceled")
                    if self.clock() - started >= RUN_SECONDS: raise AuditStop("deadline")
                    summary = memory_admission(image[0], facts)
                    for name, keys in (("swap_counters", ("pswpin","pswpout")), ("reclaim_counters", ("pgscan_direct","pgsteal_direct"))):
                        for key in keys: checked(facts[name][key])
                except AuditStop: raise
                except Exception: raise AuditStop("resource_deferred") from None
                if last_facts[0] is not None and any(facts["swap_counters"][key] != last_facts[0]["swap_counters"][key] for key in ("pswpin", "pswpout")):
                    raise AuditStop("resource_deferred")
                if last_facts[0] is not None and any(facts["reclaim_counters"][key] != last_facts[0]["reclaim_counters"][key] for key in ("pgscan_direct", "pgsteal_direct")):
                    raise AuditStop("resource_deferred")
                record["memory_admission_summary"] = summary
                peak = checked(facts["peak_rss_bytes"])
                record["peak_rss_bytes"] = max(record["peak_rss_bytes"] or 0, peak)
                record["resource_observation"] = {key:facts.get(key) for key in ("swap_counters", "reclaim_counters", "memory_psi", "io_psi", "observation_interval_seconds")}
                last_facts[0], last_probe[0] = facts, self.clock()
        def progress_handler():
            try: guard(); return 0
            except AuditStop as exc: stop[0] = exc.category; return 1
        def backup_progress(code, remaining, total):
            if code in {5,6}: raise AuditStop("sqlite_busy")
            if code not in {0,101}: raise AuditStop("backup_incomplete")
            required_image = checked(total * record["source_page_size"])
            grew = required_image > image[0]
            image[0] = max(image[0], required_image)
            guard(grew)
            progress = record["backup_progress_summary"]
            if progress["remaining"] is not None and remaining > progress["remaining"]: progress["restarts"] += 1
            progress.update(steps=progress["steps"]+1, remaining=checked(remaining), total=checked(total), completed=code == 101)
        exit_code = 4
        try:
            identity = _identity(self.source)
            _sidecars(self.source)
            record["source_path_identity"] = dict(path=str(self.source), **identity)
            source = self.connect(self.source.as_uri() + "?mode=ro", uri=True, timeout=.5, isolation_level=None)
            source.row_factory = sqlite3.Row
            if any(_identity(self.source)[key] != identity[key] for key in ("device", "inode")): raise AuditStop("source_changed")
            source.execute("PRAGMA query_only=ON")
            source.execute("PRAGMA busy_timeout=500")
            DeviceFingerprintRepository._validate_runtime_connection(source)
            size = source.execute("PRAGMA page_size").fetchone()[0]
            count = checked(source.execute("PRAGMA page_count").fetchone()[0])
            if type(size) is not int or size not in {512,1024,2048,4096,8192,16384,32768,65536}: raise AuditStop("page_size")
            image[0] = max(checked(count * size), identity["bytes"])
            record.update(stage="memory_admission", source_page_count=count, source_page_size=size)
            sides = _sidecars(self.source)
            record["snapshot_wal_state"] = dict(source_sidecar_lengths=sides, native_ro_sidecars_possible=True)
            guard(True)
            # Each real probe already spans a measured quiet-counter interval;
            # this additional force check also revalidates available headroom.
            guard(True)
            destination = self.connect(":memory:", isolation_level=None)
            destination.row_factory = sqlite3.Row
            destination.execute(f"PRAGMA page_size={size}")
            if destination.execute("PRAGMA page_size").fetchone()[0] != size: raise AuditStop("page_size")
            record["stage"] = "backup"; self.store.write(document)
            source.backup(destination, pages=BACKUP_PAGES, progress=backup_progress, sleep=BACKUP_SLEEP)
            if record["backup_progress_summary"]["remaining"] != 0 or not record["backup_progress_summary"]["completed"]: raise AuditStop("backup_incomplete")
            if any(_identity(self.source)[key] != identity[key] for key in ("device", "inode")): raise AuditStop("source_changed")
            record["snapshot_at_utc"] = self.now()
            destination.execute("PRAGMA query_only=ON")
            # All scratch state belongs to the admitted private RAM connection.
            destination.execute("PRAGMA temp_store=MEMORY")
            destination.set_progress_handler(progress_handler, 10000)
            guard(True)
            if destination.execute("PRAGMA page_size").fetchone()[0] != size: raise AuditStop("page_size")
            record["logical_snapshot_bytes"] = checked(destination.execute("PRAGMA page_count").fetchone()[0] * size)
            DeviceFingerprintRepository._validate_runtime_connection(destination)
            watermark = DeviceFingerprintRepository.read_ingest_watermark(destination)
            record.update(database_generation_id=watermark["database_generation_id"], snapshot_last_ingest_sequence=watermark["max_committed_ingest_sequence"], stage="integrity")
            self.store.write(document)
            def domain_started():
                record["stage"] = "domain"; self.store.write(document)
            record["check_summary"] = validate_snapshot(destination, guard, domain_started)
            guard(True)
            record.update(stage="complete", status="passed", category_code="snapshot_passed")
            exit_code = 0
        except (DeviceFingerprintStorageCorrupt, v.DeviceFingerprintValidationError, ValueError, TypeError):
            record.update(status="failed", category_code="integrity_suspect")
        except AuditStop as exc:
            record.update(status="failed" if exc.category == "integrity_suspect" else "incomplete", category_code=exc.category)
            exit_code = 3 if exc.category == "resource_deferred" else 4
        except sqlite3.DatabaseError as exc:
            raw_code = getattr(exc, "sqlite_errorcode", None)
            code = raw_code & 255 if type(raw_code) is int else 0
            corrupt = code in {11,26} or code == 0 and str(exc).lower() in {"database disk image is malformed", "file is not a database"}
            record.update(status="failed" if corrupt else "incomplete", category_code="integrity_suspect" if corrupt else stop[0] or "sqlite_unavailable")
            exit_code = 3 if record["category_code"] == "resource_deferred" else 4
        except MemoryError:
            record.update(status="incomplete", category_code="resource_deferred"); exit_code = 3
        except Exception:
            record.update(status="incomplete", category_code="audit_unavailable")
        finally:
            for connection in (destination, source):
                if connection is not None:
                    try: connection.set_progress_handler(None, 0); connection.close()
                    except Exception:
                        record["cleanup_error"] = True
                        if record["status"] != "failed": record.update(status="incomplete", category_code="cleanup_unavailable")
                        exit_code = 4
        if record["status"] != "passed" and exit_code == 0: exit_code = 4
        record.update(finished_at_utc=self.now(), report_written_at_utc=self.now(), duration_seconds=round(max(0, self.clock()-started), 3))
        if record["status"] == "passed": document["last_verified_success"] = copy.deepcopy(record)
        try: self.store.write(document)
        except Exception: return dict(status="incomplete", category_code="report_unavailable"), 5
        return record, exit_code
