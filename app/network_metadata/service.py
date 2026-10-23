"""One bounded auxiliary loop. Durable block precedes every source transition."""
import os
import hashlib
import threading
import time
from .health import HealthController
from .models import (RecordOutcome, NetworkMetadataStorageUnavailable, NetworkMetadataStorageCorrupt,
                     NetworkMetadataStorageLimit, NetworkMetadataValidationError)
from .normalizer import normalize_record
from .retention import RetentionPolicy
from .source import (BinarySourceReader, host_boot_id, physical_identity, continuity_anchor,
                     anchor_matches, decide_startup_generation)
from .validation import canonical_uuid


class _SourceUnavailable(NetworkMetadataStorageUnavailable):
    """Private distinction between physical source I/O and store I/O."""


def _source_continuity_anchor(fd, offset):
    try:
        return continuity_anchor(fd, offset)
    except NetworkMetadataStorageUnavailable:
        raise _SourceUnavailable() from None


def _source_anchor_matches(fd, checkpoint):
    try:
        return anchor_matches(fd, checkpoint)
    except NetworkMetadataStorageUnavailable:
        raise _SourceUnavailable() from None


class NetworkMetadataService:
    def __init__(self, config, repository, identity, capture_adapter, *, monotonic=time.monotonic,
                 boot_id_provider=host_boot_id, source_opener=None, stop_event=None):
        self.config, self.repository, self.identity, self.capture_adapter = config, repository, identity, capture_adapter
        self.monotonic, self.boot_id_provider = monotonic, boot_id_provider
        self.source_opener = source_opener or (lambda path: os.open(path, os.O_RDONLY | os.O_NONBLOCK))
        self.stop_event = stop_event or threading.Event()
        self.health = HealthController(config.capture_scope_binding.capture_source_id)
        self.fd = self.reader = None
        self.run_id = self.boot_id = None
        self.started = self.storage_failed = False
        self.last_health_tick = self.last_retention_tick = 0
        from app.operations_app_health import HealthPublisher
        from app.operations_health import NI01_UNIT
        self._app_health = HealthPublisher(NI01_UNIT, monotonic=monotonic)
        if config.telemetry_aggregation_enabled and repository.telemetry is not None:
            repository.telemetry.enable_aggregation(monotonic=monotonic)

    def stop(self):
        self.stop_event.set()

    def _publish_app_health(self, *, stopping=False):
        from app.operations_health import owner_health, NI01_UNIT
        try:
            value = (dict(state='unknown', reason='source_stopping') if stopping
                     else owner_health(NI01_UNIT, self.health))
            self._app_health.publish(value, force=stopping)
        except Exception:pass

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
        self.fd = self.reader = None

    def startup(self):
        repo = self.repository
        if repo.connection is None:
            repo.initialize()
        RetentionPolicy(repo).run()
        generation, checkpoint = repo.load_active()
        repo.persist_binding(self.config.capture_scope_binding)
        self.run_id = repo.create_ingest_run(self.identity)
        self.health.reload(repo)
        self.health.set_capture(*self.capture_adapter.evaluate(self.config.capture_scope_binding, repo.clock()))
        if generation and generation.processing_state == "blocked":
            self.health.block(generation.blocked_reason_code)
            self.health.committed_offset = checkpoint.committed_byte_offset
            try:
                repo.persist_health(self.health, generation)
            except NetworkMetadataStorageUnavailable:
                self.storage_failed = True
            # No source open/stat/read, boot lookup or ordinary lifecycle in this path.
        else:
            try:
                self.boot_id = canonical_uuid(self.boot_id_provider())
            except (NetworkMetadataStorageUnavailable, NetworkMetadataValidationError):
                repo.emit("storage_unavailable", reason_code="host_boot_id_unavailable")
                raise NetworkMetadataStorageUnavailable() from None
            repo.persist_health(self.health, generation)
            try:
                self._lifecycle(startup=True)
            except (OSError, _SourceUnavailable):
                self.health.unavailable("source_unavailable", source=True)
                repo.persist_health(self.health, repo.load_active()[0])
        self.started = True
        self.last_health_tick = self.last_retention_tick = self.monotonic()
        if not self.storage_failed:
            repo.wal_maintenance(retention_ran=True)
        repo.emit("service_started", ingest_run_id=self.run_id, artifact_sha=self.identity.artifact_sha,
                  artifact_tree=self.identity.artifact_tree, service_name="network-metadata.service",
                  process_started_at=self.identity.process_started_at)
        self._publish_app_health()

    def _path_info(self):
        try:
            info = os.stat(self.config.source_path)
            physical_identity(info)
            return info
        except FileNotFoundError:
            return None
        except (OSError, NetworkMetadataValidationError):
            raise _SourceUnavailable() from None

    def _open(self):
        try:
            fd = self.source_opener(self.config.source_path)
            info = os.fstat(fd)
            physical_identity(info)
            return fd, info
        except (OSError, NetworkMetadataValidationError):
            if "fd" in locals():
                os.close(fd)
            raise _SourceUnavailable() from None

    def _lifecycle(self, *, startup=False):
        repo = self.repository
        generation, checkpoint = repo.load_active()
        if generation and generation.processing_state == "blocked":
            self.health.block(generation.blocked_reason_code)
            return
        if generation and generation.host_boot_id != self.boot_id:
            # Close pre-reboot authority durably before any current-source I/O.
            self.close()
            generation, checkpoint = repo.transition_generation(
                binding=self.config.capture_scope_binding, boot_id=self.boot_id, physical=None,
                close_reason="host_reboot_source_lost", gap=True,
                end=checkpoint.committed_byte_offset)
            self.health.committed_offset = None
        current = self._path_info()
        if current is None:
            # Absence is not terminal: retain authority but pause all source ingest.
            self.health.unavailable("source_absent", source=True)
            repo.persist_health(self.health, generation)
            repo.emit("source_absent", reason_code="source_absent")
            return
        if self.fd is not None:
            owned = os.fstat(self.fd)
            if owned.st_size < max(checkpoint.committed_byte_offset, self.reader.scan_offset):
                return self._replace("observed_truncation", True, current)
            if physical_identity(current) != (generation.st_dev, generation.st_ino):
                # The old descriptor remains authoritative until drained to physical EOF.
                if not self.reader.at_eof:
                    if "source_absent" in self.health.local_reasons:
                        self.health.source_available()
                    return
                end = self.reader.scan_offset
                tail = self.reader.record_start if self.reader.tail_length else None
                return self._replace("source_rotated_live", False, current, end=end, tail_start=tail)
            if not _source_anchor_matches(self.fd, checkpoint):
                return self._replace("continuity_anchor_mismatch", True, current)
            if generation.capture_scope_binding_digest != self.config.capture_scope_binding.binding_digest:
                anchor = _source_continuity_anchor(self.fd, checkpoint.committed_byte_offset)
                generation, checkpoint = repo.transition_generation(binding=self.config.capture_scope_binding,
                    boot_id=self.boot_id, physical=physical_identity(current), start=checkpoint.committed_byte_offset,
                    anchor=anchor, close_reason="capture_scope_binding_changed")
                self.reader.reset(checkpoint.committed_byte_offset)
                self.health.set_capture(*self.capture_adapter.evaluate(self.config.capture_scope_binding, repo.clock()))
            if "source_absent" in self.health.local_reasons:
                self.reader.reset(checkpoint.committed_byte_offset)
                self.health.source_available()
            return
        # Stat alone proves these terminal discontinuities, before any new open.
        if generation is not None:
            if physical_identity(current) != (generation.st_dev, generation.st_ino):
                return self._replace("source_replaced_while_reader_down", True, current)
            if current.st_size < checkpoint.committed_byte_offset:
                return self._replace("observed_truncation", True, current)
        fd, info = self._open()
        try:
            continuity = generation is None or (physical_identity(info) == (generation.st_dev, generation.st_ino)
                and info.st_size >= checkpoint.committed_byte_offset and _source_anchor_matches(fd, checkpoint))
            decision = decide_startup_generation(generation, checkpoint, self.boot_id, info,
                                                  self.config.capture_scope_binding, continuity=continuity)
            gap_for_health = decision.coverage_gap_possible or (
                generation is None and repo.latest_closed_generation_gap_possible())
            if decision.action in {"open", "replace", "cutover"}:
                anchor = _source_continuity_anchor(fd, decision.start_offset)
                generation, checkpoint = repo.transition_generation(binding=self.config.capture_scope_binding,
                    boot_id=self.boot_id, physical=physical_identity(info), start=decision.start_offset, anchor=anchor,
                    close_reason=decision.close_reason, gap=decision.coverage_gap_possible)
            self.fd = fd
            self.reader = BinarySourceReader(fd, max_record_bytes=self.config.max_record_bytes,
                                             offset=checkpoint.committed_byte_offset)
            self.health.source_available(gap=gap_for_health)
            self.health.committed_offset = checkpoint.committed_byte_offset
            self.health.set_capture(*self.capture_adapter.evaluate(self.config.capture_scope_binding, repo.clock()))
            repo.persist_health(self.health, generation)
        except BaseException:
            if self.fd != fd:
                os.close(fd)
            raise

    def _replace(self, reason, gap, current, *, end=None, tail_start=None):
        repo = self.repository
        # A proven old namespace terminates independently of replacement availability.
        # Its final tail and checkpoint deletion commit together, before fd release.
        repo.transition_generation(binding=self.config.capture_scope_binding, boot_id=self.boot_id,
            physical=None, close_reason=reason, gap=gap, end=end, tail_start=tail_start)
        self.close()
        self.health.committed_offset = None
        if tail_start is not None:
            self.health.observe_source(RecordOutcome(tail_start, end, end - tail_start, "partial_final_record"))
        if current is None:
            self.health.unavailable("source_absent", source=True)
            repo.persist_health(self.health, None)
            return
        # The ordinary open path starts at 0 and consults durable closed-gap lineage.
        return self._lifecycle()

    def _coalescing_source(self, generation, checkpoint):
        """Read-only lifecycle probe; never transition while a prefix is buffered."""
        try:
            owned = os.fstat(self.fd)
            if (physical_identity(owned) != (generation.st_dev, generation.st_ino)
                    or owned.st_size < checkpoint.committed_byte_offset
                    or not _source_anchor_matches(self.fd, checkpoint)):
                raise _SourceUnavailable()
            current = self._path_info()
            closing = (current is None or physical_identity(current) != (generation.st_dev, generation.st_ino)
                       or owned.st_size < self.reader.scan_offset
                       or generation.capture_scope_binding_digest != self.config.capture_scope_binding.binding_digest)
            return owned.st_size, closing
        except (OSError, NetworkMetadataValidationError):
            raise _SourceUnavailable() from None

    def _verify_buffered_prefix(self, records, generation, checkpoint):
        """Do not commit vanished/rewritten transient bytes as a successful prefix."""
        self._coalescing_source(generation, checkpoint)
        try:
            for record in records:
                position, checksum = record.start, hashlib.sha256()
                payload_end = record.end - 1
                while position < payload_end:
                    data = os.pread(self.fd, min(65536, payload_end - position), position)
                    if not data:
                        raise OSError
                    checksum.update(data)
                    position += len(data)
                if (os.pread(self.fd, 1, payload_end) != b"\n"
                        or checksum.hexdigest() != record.source_record_sha256):
                    raise OSError
        except OSError:
            raise _SourceUnavailable() from None

    def _coalesced_records(self, generation, checkpoint):
        # Start the deadline at the first complete record, not an empty/partial read.
        reader = self.reader
        records = reader.read_batch(1, self.config.batch_max_bytes,
                                    retained_limit=self.config.batch_max_bytes)
        if not records:
            return records
        if records[0].data is None:
            # Oversized records keep the existing standalone hash/fault path,
            # with no delay or retained payload coalescing.
            return records
        deadline = self.monotonic() + self.config.ingest_coalesce_max_ms / 1000
        retained = sum(item.byte_length for item in records if item.data is not None)
        while records[-1].data is not None and len(records) < self.config.batch_max_records:
            size, closing = self._coalescing_source(generation, checkpoint)
            if closing or self.stop_event.is_set() or self.monotonic() >= deadline:
                break
            remaining = self.config.batch_max_bytes - retained
            if remaining <= reader.retained_unfinished_bytes:
                break
            # Fill the immediately available prefix before considering a wait.
            extra = reader.read_batch(self.config.batch_max_records - len(records), remaining,
                                      retained_limit=remaining)
            if extra and extra[0].data is None:
                # The legacy oversized-record fault is a standalone batch,
                # never appended to a previously buffered ordinary prefix.
                reader.reset(extra[0].start)
                break
            records.extend(extra)
            retained += sum(item.byte_length for item in extra if item.data is not None)
            if (len(records) >= self.config.batch_max_records or retained >= self.config.batch_max_bytes
                    or records[-1].data is None):
                break
            size, closing = self._coalescing_source(generation, checkpoint)
            remaining_time = deadline - self.monotonic()
            if (closing or self.stop_event.is_set() or remaining_time <= 0
                    or size - checkpoint.committed_byte_offset >= 4194304
                    or retained + reader.retained_unfinished_bytes >= self.config.batch_max_bytes):
                break
            # No BEGIN, write lock, background thread or adaptive pacing here.
            self.stop_event.wait(min(remaining_time, .01))
        self._verify_buffered_prefix(records, generation, checkpoint)
        return records

    def poll_once(self):
        if not self.started:
            self.startup()
        repo = self.repository
        did_work = False
        poll_health_id = self.health.last_snapshot.health_id if self.health.last_snapshot else None
        try:
            if self.storage_failed:
                repo.recover()
                generation, checkpoint = repo.load_active()
                if self.reader is not None and checkpoint:
                    self.reader.reset(checkpoint.committed_byte_offset)
                self.health.reload(repo)
                self.health.local_reasons.discard("storage_unavailable")
                self.health.ingest = "unknown"
                if generation and generation.processing_state == "blocked":
                    self.health.block(generation.blocked_reason_code)
                repo.persist_health(self.health, generation)
                self.storage_failed = False
            if repo.capacity_halted:
                # No source-generation/checkpoint mutation before physical-cap recovery.
                repo.ensure_headroom()
            try:
                try:
                    self._lifecycle()
                except OSError:
                    raise _SourceUnavailable() from None
                generation, checkpoint = repo.load_active()
                blocked = generation is not None and generation.processing_state == "blocked"
                if not blocked and self.reader is not None and "source_absent" not in self.health.local_reasons:
                    repo.ensure_headroom()
                    try:
                        if self.config.ingest_coalesce_enabled:
                            records = self._coalesced_records(generation, checkpoint)
                        else:
                            records = self.reader.read_batch(self.config.batch_max_records, self.config.batch_max_bytes)
                    except NetworkMetadataStorageUnavailable:
                        raise _SourceUnavailable() from None
                    if self.health.local_reasons & {"source_absent", "source_unavailable"} and (
                            "source_absent" not in self.health.local_reasons or self._path_info() is not None):
                        self.health.source_available()
                    if records:
                        all_new = self.config.io_hotpath_v1_enabled and repo.identity_range_empty(
                            generation.source_generation_id, records[0].start, records[-1].start)
                        outcomes = []
                        for record in records:
                            result = (normalize_record(record.data, source_generation_id=generation.source_generation_id,
                                start=record.start, end=record.end, binding=self.config.capture_scope_binding,
                                source_record_sha256=record.source_record_sha256) if record.data is not None
                                else RecordOutcome(record.start, record.end, record.byte_length, "record_too_large",
                                    source_record_sha256=record.source_record_sha256))
                            outcomes.append(result)
                            if not all_new and repo.identity_outcome(generation.source_generation_id, result) in {
                                "source_record_identity_conflict", "normalizer_determinism_conflict", "replay_identity_evidence_expired"}:
                                break
                        repo.ingest_batch(outcomes, self.run_id, self.health,
                            lambda offset: _source_continuity_anchor(self.fd, offset))
                        did_work = True
                        generation, checkpoint = repo.load_active()
                        if generation.processing_state == "blocked":
                            self.close()
                        if repo.capacity_halted:
                            raise NetworkMetadataStorageLimit()
            except _SourceUnavailable:
                # Source failure skips this poll's ingest, never store housekeeping.
                self.health.unavailable("source_unavailable", source=True)
                generation, checkpoint = repo.load_active()
                if self.reader and checkpoint:
                    self.reader.reset(checkpoint.committed_byte_offset)
                repo.persist_health(self.health, generation)
                did_work = False
            tick = self.monotonic()
            if tick - self.last_health_tick >= 60:
                self.health.set_capture(*self.capture_adapter.evaluate(self.config.capture_scope_binding, repo.clock()))
                self.health.heartbeat(source_available=self.reader is not None and not self.health.local_reasons & {
                    "source_absent", "source_unavailable"},
                    blocked_reason=generation.blocked_reason_code if generation and generation.processing_state == "blocked" else None)
                # A due snapshot already written by this poll's transition serves
                # the same heartbeat unless the refreshed state/reasons change.
                repo.persist_health(self.health, generation, force=(
                    self.health.last_snapshot is None or self.health.last_snapshot.health_id == poll_health_id))
                repo.emit("health_heartbeat", metadata_ingest_health=self.health.ingest)
                self.last_health_tick = tick
            else:
                repo.persist_health(self.health, generation)
            retained = tick - self.last_retention_tick >= 3600
            if retained:
                RetentionPolicy(repo).run()
                self.last_retention_tick = tick
            repo.wal_maintenance(retention_ran=retained)
        except NetworkMetadataStorageCorrupt:
            # Native fatal outcome, not a report-driven probe or state rewrite.
            try:self._app_health.publish(dict(state='unavailable', reason='source_unavailable'))
            except Exception:pass
            raise
        except NetworkMetadataStorageLimit:
            self.health.unavailable("storage_capacity_headroom_exhausted")
            if self.reader is not None:
                self.reader.reset(repo.load_active()[1].committed_byte_offset)
            # Diagnostics are permitted only if the full transaction reservation fits.
            if repo.footprint()["combined"] + max(16777216, 8 * self.config.batch_max_bytes) <= self.config.max_db_bytes:
                repo.persist_health(self.health, repo.load_active()[0])
        except NetworkMetadataStorageUnavailable:
            self.storage_failed = True
            self.health.unavailable("storage_unavailable")
            repo.emit("storage_unavailable", reason_code="storage_unavailable")
        self._publish_app_health()
        return did_work

    def run_forever(self):
        try:
            self.startup()
            while not self.stop_event.is_set():
                work = self.poll_once()
                if self.config.telemetry_aggregation_enabled and self.repository.telemetry is not None:
                    self.repository.telemetry.flush_due()
                if not work:
                    self.stop_event.wait(self.config.poll_interval_seconds)
        finally:
            self._publish_app_health(stopping=True)
            self.close()
            self.repository.emit("service_stopped", ingest_run_id=self.run_id)
