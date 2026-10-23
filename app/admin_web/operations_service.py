"""Bounded on-demand, metadata-only Operations snapshots. No durable writes."""

from __future__ import annotations

import copy
import json
import os
import selectors
import stat
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath

from .operations_inventory import SERVICES, STORES, topology_snapshot
from .sensor_metadata import SensorMetadataReader, SENSOR_STORES, project_store
from app.device_fingerprint_sensor.operations_metadata import boot_ns
from .operations_health import SensorHealthEvidence, project as project_health, sensor_store_metadata
from app.operations_health import unknown_evidence
from app.network_metadata_projection.operations_health import HealthReader, PROVENANCE
from app.operations_health import NI02_UNIT
from app.operations_health import OWNER_SERVICES, SENSOR_UNIT, CORE_UNIT, SURICATA_UNIT, validate, validate_local
from app.device_fingerprint_sensor.operations_metadata import parse_stamp, TTL
from app.operations_app_health import HealthReader as OwnerHealthReader
from .operations_verification import OwnerChecks
from app.operations_verification import opaque_identity,project as project_verification

API_VERSION = "admin.operations.db-services.v1"
API_VERSION_V2 = "admin.operations.db-services.v2"
RESAMPLE_SECONDS = 30.0
STALE_SECONDS = 90.0
FIRST_WAIT_SECONDS = 0.250
SAMPLE_SECONDS = 2.0
FS_SECONDS = 1.0
SYSTEMD_SECONDS = 0.75
STDOUT_LIMIT = 16384
STDERR_LIMIT = 1024
RESPONSE_LIMIT = 48000
PROPERTIES = ("Id", "LoadState", "ActiveState", "SubState", "MainPID", "NRestarts",
              "ExecMainStartTimestamp", "UnitFileState")
SYSTEMD_ARGV = ("/usr/bin/systemctl", "--no-pager", "show", "--property=" + ",".join(PROPERTIES),
                *(service.unit for service in SERVICES))
SYSTEMD_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "TZ": "UTC",
               "SYSTEMD_COLORS": "0", "SYSTEMD_PAGER": "cat"}


class OperationsError(ValueError):
    def __init__(self, code="operations_unavailable"):
        super().__init__(code)
        self.code = code


def utc_now():
    return datetime.now(timezone.utc)


def timestamp(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def acquire_systemd(cancel=None):
    """Drain bounded pipes before parsing; fail closed on non-POSIX hosts."""
    if os.name != "posix":
        raise OperationsError()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": STDOUT_LIMIT, "stderr": STDERR_LIMIT}
    process = None
    try:
        process = subprocess.Popen(SYSTEMD_ARGV, shell=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=SYSTEMD_ENV, bufsize=0)
        deadline = time.monotonic() + SYSTEMD_SECONDS
        with selectors.DefaultSelector() as selector:
            for name in buffers:
                stream = getattr(process, name)
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0 or (cancel is not None and cancel.is_set()):
                    raise OperationsError()
                for key, _events in selector.select(remaining):
                    name = key.data
                    chunk = os.read(key.fd, min(4096, limits[name] + 1 - len(buffers[name])))
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        buffers[name].extend(chunk)
                        if len(buffers[name]) > limits[name]:
                            raise OperationsError()
            remaining = deadline - time.monotonic()
            if remaining <= 0 or process.wait(timeout=remaining) != 0:
                raise OperationsError()
        return bytes(buffers["stdout"]).decode("utf-8", errors="strict")
    except (OSError, ValueError, subprocess.SubprocessError, UnicodeError):
        raise OperationsError() from None
    finally:
        if process is not None:
            if process.poll() is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            # If the kernel itself cannot reap this process, keep this sole
            # worker occupied; never start a replacement sampler/subprocess.
            process.wait()
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()


def parse_systemd(text):
    """Isolate each systemd 249 record; never echo unknown values."""
    if type(text) is not str or len(text.encode("utf-8")) > STDOUT_LIMIT:
        raise OperationsError()
    known = {s.unit for s in SERVICES}
    records, invalid = {}, set()
    for block in text.strip().split("\n\n"):
        values, duplicate = {}, False
        for line in block.splitlines():
            key, separator, value = line.partition("=")
            if not separator or key not in PROPERTIES or key in values or len(value) > 128:
                duplicate = True
            else:
                values[key] = value
        unit = values.get("Id")
        if unit not in known:
            continue
        if unit in records or duplicate or set(values) != set(PROPERTIES):
            invalid.add(unit)
        records[unit] = values
    for unit in invalid:
        records.pop(unit, None)
    return records


def _integer(value, maximum):
    if type(value) is not str or not value.isascii() or not value.isdecimal() or len(value) > 20:
        return None
    number = int(value)
    return number if 0 <= number <= maximum else None


def service_row(item, intent, record, now):
    row = dict(id=item.id, label=item.label, unit=item.unit, role=item.role,
        expected_mode=intent, operational_state="unknown", application_health="unknown",
        active_state=None, sub_state=None, main_pid=None, n_restarts=None,
        started_at_utc=None, uptime_seconds=None, sampled_at_utc=timestamp(now),
        reason_code="probe_unavailable")
    if record is None:
        return row
    load, active, sub = (record.get(k) for k in ("LoadState", "ActiveState", "SubState"))
    if (load not in {"loaded", "not-found", "error", "masked", "bad-setting", "stub", "merged"}
            or active not in {"active", "inactive", "failed", "activating", "deactivating", "reloading"}
            or sub not in {"running", "exited", "dead", "failed", "start", "start-pre", "start-post",
                           "stop", "stop-sigterm", "stop-sigkill", "auto-restart", "reload"}):
        return row
    pid = _integer(record.get("MainPID"), 2147483647)
    restarts = _integer(record.get("NRestarts"), 9223372036854775807)
    if pid is None or restarts is None:
        return row
    row.update(active_state=active, sub_state=sub, n_restarts=restarts, reason_code=None)
    started = None
    raw_start = record.get("ExecMainStartTimestamp", "")
    try:
        started = datetime.strptime(raw_start, "%a %Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    running = load == "loaded" and active == "active" and pid > 0 and started is not None and started <= now
    if running:
        row.update(main_pid=pid, started_at_utc=timestamp(started), uptime_seconds=int((now - started).total_seconds()))
    if intent == "unknown":
        row["reason_code"] = "intent_unknown"
    elif intent in {"disabled", "maintenance"}:
        if running:
            row.update(operational_state="degraded", reason_code="unexpected_running")
        elif active in {"inactive", "failed"} and pid == 0:
            row.update(operational_state="disabled", reason_code="configured_disabled")
        else:
            row["reason_code"] = "probe_unavailable"
    elif load == "not-found":
        row.update(operational_state="failed", reason_code="unit_unavailable")
    elif active == "failed":
        row.update(operational_state="failed", reason_code="unit_failed")
    elif load == "loaded" and active == "inactive" and pid == 0:
        row.update(operational_state="stopped", reason_code="expected_stopped")
    elif running:
        row["operational_state"] = "running"
    else:
        row["reason_code"] = "probe_unavailable"
    return row


def store_row(item, intent, path, now, lstat, *, deadline, monotonic, cancel, identity_available=True):
    row = dict(id=item.id, label=item.label, filename=PurePosixPath(path).name,
        purpose=item.purpose, writer_owner_component_ids=list(item.writers), writer_service_ids=list(item.services),
        reader_service_ids=list(item.readers), store_kind=item.kind, expected_mode=intent,
        operational_state="unknown", file_presence="unknown", main_file_bytes=None,
        wal_bytes=None, shm_bytes=None, total_footprint_bytes=None, schema_expected_version=None,
        schema_observed_version=None, health_evidence="none", health_checked_at_utc=None,
        sampled_at_utc=timestamp(now), reason_code=None)
    identities, presence, reasons = [], [], []
    for suffix, key in (("", "main_file_bytes"), ("-wal", "wal_bytes"), ("-shm", "shm_bytes")):
        state, size, identity, reason = "unknown", None, None, None
        if cancel.is_set() or monotonic() >= deadline:
            reason = "sample_timeout"
        else:
            try:
                metadata = lstat(path + suffix)
                if monotonic() >= deadline:
                    reason = "sample_timeout"
                elif stat.S_ISLNK(metadata.st_mode):
                    reason = "symlink_file"
                elif not stat.S_ISREG(metadata.st_mode):
                    reason = "nonregular_file"
                elif type(metadata.st_size) is not int or not 0 <= metadata.st_size <= 9223372036854775807:
                    reason = "stat_unavailable"
                else:
                    state, size = "present", metadata.st_size
                    if identity_available:
                        identity = (metadata.st_dev, metadata.st_ino)
            except FileNotFoundError:
                state, size = "absent", 0
            except PermissionError:
                reason = "metadata_permission_boundary" if item.id in {"network_attribution", "sensor_spool"} else "stat_unavailable"
            except OSError:
                reason = "stat_unavailable"
        row[key] = size
        identities.append(identity)
        presence.append(state)
        reasons.append(reason)
    row["file_presence"] = presence[0]
    sizes = [row[k] for k in ("main_file_bytes", "wal_bytes", "shm_bytes")]
    if all(type(value) is int and value >= 0 for value in sizes):
        row["total_footprint_bytes"] = sum(sizes)
    main_reason = reasons[0]
    if main_reason in {"symlink_file", "nonregular_file"}:
        row.update(operational_state="unavailable", reason_code=main_reason)
    elif "unknown" in presence:
        row["reason_code"] = next((r for r in reasons if r), "stat_unavailable")
        if presence[0] == "present":
            row["operational_state"] = "disabled" if intent == "optional_disabled" else "present_unverified" if intent == "expected" else "unknown"
    elif intent == "unknown":
        row["reason_code"] = "intent_unknown"
    elif presence[0] == "absent":
        row.update(operational_state="not_provisioned" if intent == "optional_disabled" else "unavailable",
                   reason_code="orphan_sidecar_possible" if "present" in presence[1:] else "configured_disabled" if intent == "optional_disabled" else "file_missing")
    elif intent == "optional_disabled":
        row.update(operational_state="disabled", reason_code="configured_disabled")
    else:
        row.update(operational_state="present_unverified", reason_code="not_attested")
    return row, identities, any(reasons)


def summarize(services, databases):
    service_counts = {state: sum(r["operational_state"] == state for r in services)
                      for state in ("running", "degraded", "failed", "stopped", "disabled")}
    service_counts.update(registered=len(services), expected_running=sum(r["expected_mode"] == "run" for r in services),
                          unknown_or_stale=sum(r["operational_state"] in {"unknown", "stale"} for r in services))
    db_counts = {state: sum(r["operational_state"] == state for r in databases)
                 for state in ("available", "present_unverified", "disabled", "not_provisioned", "degraded", "unavailable", "incompatible")}
    db_counts.update(registered=len(databases), unknown_or_stale=sum(r["operational_state"] in {"unknown", "stale"} for r in databases))
    unknown = sum(r["total_footprint_bytes"] is None for r in databases)
    storage = dict(known_footprint_bytes=sum(r["total_footprint_bytes"] or 0 for r in databases),
        total_complete=unknown == 0, unknown_store_count=unknown,
        coverage="complete" if unknown == 0 else "unknown" if unknown == len(databases) else "partial")
    established = sum(r["operational_state"] in {"degraded", "failed"} or
                      (r["operational_state"] == "stopped" and r["expected_mode"] == "run") for r in services)
    established += sum(r["operational_state"] in {"degraded", "unavailable", "incompatible"} for r in databases)
    return dict(services=service_counts, databases=db_counts, storage=storage,
                problems=dict(established=established, unknown_or_stale=service_counts["unknown_or_stale"] + db_counts["unknown_or_stale"]))


class AdminOperationsReadService:
    def __init__(self, inventory, *, acquire=acquire_systemd, lstat=os.lstat, monotonic=time.monotonic, now=utc_now,
                 sensor_metadata=None, ni02_health=None,owner_checks=None,owner_health_readers=None,core_snapshot=None):
        self.inventory, self._acquire, self._lstat = inventory, acquire, lstat
        self._monotonic, self._now = monotonic, now
        self._sensor_metadata = sensor_metadata if sensor_metadata is not None else SensorMetadataReader()
        self._sensor_health = SensorHealthEvidence(self._sensor_metadata)
        self._ni02_report = ni02_health if ni02_health is not None else HealthReader()
        self._ni02_health = SensorHealthEvidence(self._ni02_report,unit=NI02_UNIT,source=PROVENANCE)
        self._owner_health_readers = (owner_health_readers if owner_health_readers is not None
            else {key: OwnerHealthReader(unit) for key, unit in OWNER_SERVICES.items()})
        self._owner_health = {key: SensorHealthEvidence(self._owner_health_readers[key], unit=unit, source=PROVENANCE)
            for key, unit in OWNER_SERVICES.items()}
        self._owner_checks=owner_checks if owner_checks is not None else OwnerChecks()
        self._core_snapshot = core_snapshot
        self._condition = threading.Condition()
        self._cancel = threading.Event()
        self._busy = False
        self._last_attempt = None
        self._cache = None
        self._failed = False

    def set_core_snapshot_provider(self, provider):
        self._core_snapshot = provider

    @staticmethod
    def _local_record(health, source, observed, now, expiry):
        return dict(evidence=dict(state=health['state'], source=source, reason=health['reason'],
            observed_at=timestamp(observed), received_at=timestamp(now),
            age=(now-observed).total_seconds(), ttl=int(TTL)), expires=expiry)

    def _suricata_health(self, report, sensor, suricata, now):
        unknown = dict(evidence=unknown_evidence(), expires=None)
        try:
            if suricata['operational_state'] != 'running':return unknown
            if report.get('status') == 'stale':
                unknown['evidence'].update(state='stale', reason='report_stale')
                return unknown
            if report.get('status') != 'fresh' or sensor['operational_state'] != 'running':return unknown
            health = validate(report['health'], SENSOR_UNIT)
            if report['producer']['pid'] != sensor['main_pid']:return unknown
            observed = parse_stamp(report['observed_at'])
            age = (now-observed).total_seconds()
            if not 0 <= age <= TTL or boot_ns() > report['expires_boottime_ns']:return unknown
            # A Sensor observation before a newly started Suricata is not proof of that incarnation.
            if observed < parse_stamp(suricata['started_at_utc']):return unknown
            state = health['dependencies']['suricata']
            mapped = validate_local(dict(state='healthy' if state else 'unavailable',
                reason='source_ready' if state else 'source_unavailable'), SURICATA_UNIT)
            return self._local_record(mapped, 'observed_via_sensor', observed, now, report['expires_boottime_ns'])
        except Exception:return unknown

    def _core_health(self, service, now):
        try:
            if self._core_snapshot is None or service['operational_state'] != 'running' or service['main_pid'] != os.getpid():
                raise ValueError()
            value = self._core_snapshot(now)
            health = validate_local(value['health'], CORE_UNIT)
            observed = value['observed_at']; age = (now-observed).total_seconds()
            if not 0 <= age <= TTL:raise ValueError()
            return self._local_record(health, 'portal_in_process', observed, now,
                boot_ns()+int((TTL-age)*1e9))
        except Exception:return dict(evidence=unknown_evidence(), expires=None)

    def close(self):
        with self._condition:
            self._cancel.set()
            self._condition.notify_all()

    def read(self, request_id, *, version=1):
        if version not in (1, 2):
            raise OperationsError()
        with self._condition:
            now = self._monotonic()
            if self._cancel.is_set():
                raise OperationsError()
            if not self._busy and (self._last_attempt is None or now - self._last_attempt >= RESAMPLE_SECONDS):
                self._last_attempt, self._busy, self._failed = now, True, False
                worker = threading.Thread(target=self._run, name="admin_operations_sample", daemon=True)
                try:
                    worker.start()
                except RuntimeError:
                    self._busy, self._failed = False, True
            if self._cache is None and self._busy:
                deadline = time.monotonic() + FIRST_WAIT_SECONDS
                while self._cache is None and self._busy and not self._cancel.is_set():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    self._condition.wait(remaining)
            if self._cancel.is_set() or self._cache is None:
                raise OperationsError("snapshot_pending" if self._busy else "operations_unavailable")
            sample, started_mono = self._cache
            result = copy.deepcopy(sample)
            age = max(0.0, self._monotonic() - started_mono)
        source_expiry = result.pop("_sensor_expires_boottime_ns", None)
        health_records = result.pop("_health_records", {})
        sensor_report = result.pop("_sensor_report", {})
        check_records=result.pop('_verification_records',{})
        if source_expiry is not None and boot_ns() > source_expiry:
            for row in result["databases"]:
                if row["id"] in SENSOR_STORES:
                    row.update(operational_state="stale", file_presence="unknown", main_file_bytes=None,
                        wal_bytes=None, shm_bytes=None, total_footprint_bytes=None, reason_code="metadata_stale")
            result["snapshot_state"] = "partial"
        stale = age > STALE_SECONDS
        if stale:
            for row in result["services"]:
                row.update(operational_state="stale", application_health="stale", reason_code="sample_stale")
            for row in result["databases"]:
                row.update(operational_state="stale", reason_code="sample_stale")
            result["snapshot_state"] = "partial"
        result.update(api_version=API_VERSION, request_id=request_id, scope="global",
            generated_at_utc=timestamp(self._now()), freshness_seconds=round(age, 3),
            sample_status="stale" if stale else "fresh")
        result["summary"] = summarize(result["services"], result["databases"])
        result["topology"] = topology_snapshot()
        if version == 2:
            result["api_version"] = API_VERSION_V2
            for row in result["services"]:
                record = health_records.get(row["id"])
                evidence = project_health(record, stale=stale, boottime=boot_ns) if record else unknown_evidence()
                row.update(application_health=evidence["state"], application_health_evidence=evidence)
            for row in result["databases"]:
                record=check_records.get(row['id'])
                expires=None if record is None else record['expires']
                expired=expires is not None and boot_ns()>expires
                row['store_verification']=project_verification(row['id'],record,
                    None if record is None else record['current_id'],intent=row['expected_mode'],
                    source_current=record is not None and record['source_current'],
                    stale=stale or expired,
                    binding_current=not stale and (row['id'] not in SENSOR_STORES or
                        record is not None and record['source_current'] and not expired and row['file_presence']=='present'))
                row["metadata_evidence"], row["journal_bytes"] = (
                    sensor_store_metadata(sensor_report, row["id"], boottime=boot_ns) if row["id"] in SENSOR_STORES
                    else (dict(source="sampler_lstat", state="stale" if stale else "fresh",
                               age=round(age, 3), ttl=int(STALE_SECONDS)), None))
                if row["file_presence"] == "unknown":
                    row["metadata_evidence"]["state"] = "unknown"
            result["summary"]["application_health"] = {state: sum(row["application_health"] == state for row in result["services"])
                for state in ("healthy", "degraded", "unavailable", "unknown", "stale")}
            result["summary"]["problems"] = dict(
                established=sum(r["operational_state"] in {"degraded", "failed"}
                    or r["operational_state"] == "stopped" and r["expected_mode"] == "run"
                    or r["application_health"] in {"degraded", "unavailable"} for r in result["services"])
                    + sum(r["operational_state"] in {"degraded", "unavailable", "incompatible"} for r in result["databases"]),
                unknown_or_stale=sum(r["operational_state"] in {"unknown", "stale"}
                    or r["application_health"] in {"unknown", "stale"} for r in result["services"])
                    + result["summary"]["databases"]["unknown_or_stale"])
        if len(json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")) > RESPONSE_LIMIT:
            raise OperationsError()
        return result

    def _run(self):
        try:
            started = self._monotonic()
            snapshot = self._collect(started)
            with self._condition:
                if not self._cancel.is_set():
                    self._cache = snapshot, started
        except Exception:
            with self._condition:
                self._failed = True
        finally:
            with self._condition:
                self._last_attempt = self._monotonic()
                self._busy = False
                self._condition.notify_all()

    def _collect(self, started):
        began = self._now()
        failures = []
        def failure(source, identity, code):
            if len(failures) < 32:
                failures.append(dict(source=source, id=identity, code=code))
        try:
            records = parse_systemd(self._acquire(self._cancel))
        except Exception:
            records = {}
        services = [service_row(s, self.inventory.service_intents[s.id], records.get(s.unit), self._now()) for s in SERVICES]
        for row in services:
            if row["reason_code"] == "probe_unavailable":
                failure("service_state", row["id"], "probe_unavailable")
        deadline = min(started + SAMPLE_SECONDS, self._monotonic() + FS_SECONDS)
        sensor = next(row for row in services if row["id"] == "fingerprint_sensor")
        try:
            sensor_report = self._sensor_metadata.read(sensor, self._now(), deadline=deadline,
                monotonic=self._monotonic, cancel=self._cancel)
        except Exception:
            sensor_report = {"status": "unknown", "reason": "metadata_unavailable", "stores": None}
        if type(sensor_report) is not dict or sensor_report.get("status") not in {"fresh", "stale", "unknown"}:
            sensor_report = {"status": "unknown", "reason": "metadata_unavailable", "stores": None}
        expiry = sensor_report.get("expires_boottime_ns")
        if sensor_report["status"] == "fresh" and (type(expiry) is not int or expiry < 0):
            sensor_report = {"status": "unknown", "reason": "metadata_unavailable", "stores": None}
            expiry = None
        health_records = {"fingerprint_sensor": self._sensor_health.collect(sensor_report, sensor, self._now())}
        suricata = next(row for row in services if row['id'] == 'fingerprint_suricata')
        health_records['fingerprint_suricata'] = self._suricata_health(sensor_report, sensor, suricata, self._now())
        core = next(row for row in services if row['id'] == 'portal_core')
        health_records['portal_core'] = self._core_health(core, self._now())
        ni02 = next(row for row in services if row["id"] == "network_metadata_projection")
        try:
            ni02_report = self._ni02_report.read(ni02,self._now(),deadline=deadline,monotonic=self._monotonic,cancel=self._cancel)
        except Exception:
            ni02_report = dict(status="unknown")
        health_records["network_metadata_projection"] = self._ni02_health.collect(ni02_report,ni02,self._now())
        # Existing sampler only: consume owner memory reports, never initiate
        # owner checks/SQLite work from an Admin request.
        for key in OWNER_SERVICES:
            row = next(row for row in services if row['id'] == key)
            try:
                report = self._owner_health_readers[key].read(row,self._now(),deadline=deadline,
                    monotonic=self._monotonic,cancel=self._cancel)
            except Exception:report = dict(status='unknown')
            health_records[key] = self._owner_health[key].collect(report,row,self._now())
        verification=self._owner_checks.collect(services,sensor_report,ni02_report,self._now(),
            deadline=deadline,monotonic=self._monotonic,cancel=self._cancel)
        databases, storage_ids = [], {}
        sampled_files = {}
        def sample_file(path):
            if path not in sampled_files:
                try:
                    sampled_files[path] = self._lstat(path)
                except OSError as exc:
                    sampled_files[path] = exc
            value = sampled_files[path]
            if isinstance(value, OSError):
                raise value
            return value
        for item in STORES:
            if item.id in SENSOR_STORES:
                row, partial = project_store(item, self.inventory.store_intents[item.id], self.inventory.paths[item.id],
                    self._now(), sensor_report, store_row, deadline=deadline, monotonic=self._monotonic, cancel=self._cancel)
                identities = []
            else:
                row, identities, partial = store_row(item, self.inventory.store_intents[item.id], self.inventory.paths[item.id],
                    self._now(), sample_file, deadline=deadline, monotonic=self._monotonic, cancel=self._cancel)
            databases.append(row)
            if item.id in verification:
                current_id=(verification[item.id]['row']['observed_store_id'] if item.id in SENSOR_STORES
                    else opaque_identity(sampled_files[self.inventory.paths[item.id]])
                    if not isinstance(sampled_files.get(self.inventory.paths[item.id]),(OSError,type(None))) else None)
                verification[item.id]['current_id']=current_id if row['file_presence']=='present' else None
            if partial:
                failure("db_stat", row["id"], row["reason_code"] or "stat_unavailable")
            for identity in identities:
                if identity is not None:
                    storage_ids.setdefault(identity, set()).add(item.id)
        collisions = set().union(*(ids for ids in storage_ids.values() if len(ids) > 1)) if storage_ids else set()
        for row in databases:
            if row["id"] in collisions:
                row.update(operational_state="unknown", file_presence="unknown", main_file_bytes=None,
                           wal_bytes=None, shm_bytes=None, total_footprint_bytes=None, reason_code="storage_collision")
                failure("inventory", row["id"], "storage_collision")
                if row['id'] in verification:verification[row['id']]['current_id']=None
        # A successful absence is evidence too; all unknowns are not a snapshot.
        if not any(r["reason_code"] != "probe_unavailable" for r in services) and not any(r["file_presence"] != "unknown" for r in databases):
            raise OperationsError()
        return dict(snapshot_state="partial" if failures else "complete", sampling_started_at_utc=timestamp(began),
                    sampling_completed_at_utc=timestamp(self._now()), services=services, databases=databases,
                    partial_failures=failures, _sensor_expires_boottime_ns=expiry,
                    _health_records=health_records, _sensor_report=sensor_report,_verification_records=verification)
