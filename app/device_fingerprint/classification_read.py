"""Read retained Task-04 classifications from the dedicated Classification SQLite."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, TypeVar

from .artifact_content import ArtifactContent, ArtifactRef
from .classification_persistence import ClassificationCoreRecord, ClassificationPersistenceError
from .models import DeviceFingerprintValidationError
from .validation import parse_utc, validate_mac, validate_site_id, validate_uuid


@dataclass(frozen=True, slots=True)
class ClassificationReadRecord:
    core: ClassificationCoreRecord
    result: ArtifactContent


@dataclass(frozen=True, slots=True)
class ClassificationHistoryCursor:
    classified_at_utc: str
    classification_id: str


@dataclass(frozen=True, slots=True)
class ClassificationHistoryPage:
    items: tuple[ClassificationReadRecord, ...]
    next_cursor: ClassificationHistoryCursor | None


_T = TypeVar("_T")
MAX_PRODUCTION_READ_MACS = 250


def _uuid_v4(value: object) -> str:
    canonical = validate_uuid(value)
    if uuid.UUID(canonical).version != 4:
        raise DeviceFingerprintValidationError("Invalid UUIDv4")
    return canonical


def _reference(artifact_id: object, digest: object, expected_type: str) -> ArtifactRef:
    reference = ArtifactRef(artifact_id, digest)
    if not reference.artifact_id.startswith(f"{expected_type}:v1:sha256:"):
        raise DeviceFingerprintValidationError("Invalid classification artifact reference")
    return reference


class DeviceFingerprintClassificationReadService:
    def __init__(self, classification_database_path: str | Path) -> None:
        self._database_path = Path(classification_database_path).resolve(strict=False)

    def _read(self, operation: Callable[[sqlite3.Connection], _T]) -> _T:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                f"{self._database_path.as_uri()}?mode=ro", uri=True, isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN")
            return operation(connection)
        except (sqlite3.Error, DeviceFingerprintValidationError, KeyError, TypeError,
                ValueError, UnicodeError, AttributeError, RecursionError, OverflowError) as exc:
            raise ClassificationPersistenceError("persistence_unavailable") from exc
        finally:
            if connection is not None:
                try:
                    if connection.in_transaction:
                        connection.rollback()
                finally:
                    connection.close()

    @staticmethod
    def _record(connection: sqlite3.Connection, row: sqlite3.Row, *,
                retained_results: Mapping[str, sqlite3.Row] | None = None) -> ClassificationReadRecord:
        core = ClassificationCoreRecord(**dict(row))
        _uuid_v4(core.classification_id)
        if validate_site_id(core.site_id) != core.site_id:
            raise DeviceFingerprintValidationError("Noncanonical Site identifier")
        if validate_mac(core.observed_mac) != core.observed_mac:
            raise DeviceFingerprintValidationError("Noncanonical MAC")
        parse_utc(core.classified_at_utc)
        if core.execution_context not in {"PRODUCTION", "PRE_ACCEPTANCE_CANDIDATE"}:
            raise DeviceFingerprintValidationError("Invalid execution context")
        if core.execution_context == "PRODUCTION":
            _uuid_v4(core.runtime_profile_activation_record_id)
        elif core.runtime_profile_activation_record_id is not None:
            raise DeviceFingerprintValidationError("Invalid acceptance activation")

        for artifact_id, digest, artifact_type in (
            (core.classification_runtime_profile_id, core.classification_runtime_profile_digest,
             "ClassificationRuntimeProfile"),
            (core.foundation_runtime_profile_id, core.foundation_runtime_profile_digest,
             "FoundationRuntimeProfile"),
            (core.classification_request_manifest_id, core.classification_request_manifest_digest,
             "ClassificationRequestManifest"),
            (core.snapshot_record_id, core.snapshot_record_digest, "SnapshotRecord"),
            (core.classification_retention_policy_id, core.classification_retention_policy_digest,
             "ClassificationRetentionPolicy"),
        ):
            _reference(artifact_id, digest, artifact_type)
        result_ref = _reference(core.classification_result_id, core.classification_result_digest,
                                "ClassificationResult")
        stored = (retained_results.get(result_ref.artifact_id) if retained_results is not None
                  else connection.execute(
                      "SELECT artifact_id, artifact_type, content_sha256, semantic_payload_json "
                      "FROM artifacts WHERE artifact_id=?", (result_ref.artifact_id,),
                  ).fetchone())
        if stored is None or stored["artifact_type"] != "ClassificationResult":
            raise ClassificationPersistenceError("persistence_unavailable")
        result = ArtifactContent(
            stored["artifact_type"], 1, stored["semantic_payload_json"],
            stored["content_sha256"], stored["artifact_id"],
        )
        result_ref.resolve(result, "ClassificationResult")
        if result.semantic_payload["classification_request_digest"] != (
                core.classification_request_manifest_digest):
            raise DeviceFingerprintValidationError("Classification request digest mismatch")
        return ClassificationReadRecord(core, result)

    def get_by_id(self, classification_id: str) -> ClassificationReadRecord | None:
        identity = _uuid_v4(classification_id)

        def select(connection: sqlite3.Connection) -> ClassificationReadRecord | None:
            row = connection.execute(
                "SELECT * FROM classifications WHERE classification_id=?", (identity,),
            ).fetchone()
            return None if row is None else self._record(connection, row)

        return self._read(select)

    def get_current(self, site_id: str, observed_mac: str) -> ClassificationReadRecord | None:
        site = validate_site_id(site_id)
        mac = validate_mac(observed_mac)

        def select(connection: sqlite3.Connection) -> ClassificationReadRecord | None:
            row = connection.execute(
                "SELECT * FROM classifications WHERE site_id=? AND observed_mac=? "
                "ORDER BY classified_at_utc DESC, classification_id DESC LIMIT 1",
                (site, mac),
            ).fetchone()
            return None if row is None else self._record(connection, row)

        return self._read(select)

    def get_current_production(self, site_id: str, observed_mac: str) -> ClassificationReadRecord | None:
        mac = validate_mac(observed_mac)
        return self.get_current_production_many(site_id, (mac,))[mac]

    def get_current_production_many(
        self, site_id: str, observed_macs: list[str] | tuple[str, ...],
    ) -> dict[str, ClassificationReadRecord | None]:
        """Two bounded SELECTs in one readonly snapshot; candidate runs never shadow production."""
        site = validate_site_id(site_id)
        if (not isinstance(observed_macs, (list, tuple))
                or len(observed_macs) > MAX_PRODUCTION_READ_MACS):
            raise DeviceFingerprintValidationError("Invalid production classification batch")
        macs = tuple(sorted({validate_mac(mac) for mac in observed_macs}))
        if not macs:
            return {}

        def select(connection: sqlite3.Connection) -> dict[str, ClassificationReadRecord | None]:
            slots = ','.join('?' for _ in macs)
            rows = connection.execute(
                "SELECT * FROM classifications AS current WHERE site_id=? "
                "AND execution_context='PRODUCTION' AND observed_mac IN (" + slots + ") "
                "AND NOT EXISTS (SELECT 1 FROM classifications AS newer "
                "WHERE newer.site_id=current.site_id AND newer.observed_mac=current.observed_mac "
                "AND newer.execution_context='PRODUCTION' AND "
                "(newer.classified_at_utc>current.classified_at_utc OR "
                "(newer.classified_at_utc=current.classified_at_utc "
                "AND newer.classification_id>current.classification_id))) "
                "ORDER BY observed_mac", (site, *macs),
            ).fetchall()
            results: dict[str, ClassificationReadRecord | None] = dict.fromkeys(macs)
            if not rows:
                return results
            artifact_ids = tuple(sorted({row['classification_result_id'] for row in rows}))
            artifacts = connection.execute(
                "SELECT artifact_id, artifact_type, content_sha256, semantic_payload_json "
                "FROM artifacts WHERE artifact_id IN (" + ','.join('?' for _ in artifact_ids) + ")",
                artifact_ids,
            ).fetchall()
            retained = {row['artifact_id']: row for row in artifacts}
            for row in rows:
                record = self._record(connection, row, retained_results=retained)
                if record.core.site_id != site or record.core.execution_context != "PRODUCTION":
                    raise DeviceFingerprintValidationError("Invalid production classification scope")
                results[record.core.observed_mac] = record
            return results

        return self._read(select)

    def list_history(
        self, site_id: str, observed_mac: str, from_utc: str, to_utc: str, *,
        limit: int = 100, cursor: ClassificationHistoryCursor | None = None,
    ) -> ClassificationHistoryPage:
        site = validate_site_id(site_id)
        mac = validate_mac(observed_mac)
        if parse_utc(from_utc) >= parse_utc(to_utc):
            raise DeviceFingerprintValidationError("Invalid classification history window")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise DeviceFingerprintValidationError("Invalid classification history limit")
        if cursor is not None:
            if not isinstance(cursor, ClassificationHistoryCursor):
                raise DeviceFingerprintValidationError("Invalid classification history cursor")
            parse_utc(cursor.classified_at_utc)
            _uuid_v4(cursor.classification_id)

        def select(connection: sqlite3.Connection) -> ClassificationHistoryPage:
            parameters: list[object] = [site, mac, from_utc, to_utc]
            query = (
                "SELECT * FROM classifications WHERE site_id=? AND observed_mac=? "
                "AND classified_at_utc>=? AND classified_at_utc<?"
            )
            if cursor is not None:
                query += (" AND (classified_at_utc>? OR "
                          "(classified_at_utc=? AND classification_id>?))")
                parameters.extend((cursor.classified_at_utc, cursor.classified_at_utc,
                                   cursor.classification_id))
            query += " ORDER BY classified_at_utc ASC, classification_id ASC LIMIT ?"
            parameters.append(limit + 1)
            rows = connection.execute(query, parameters).fetchall()
            items = tuple(self._record(connection, row) for row in rows[:limit])
            next_cursor = None
            if len(rows) > limit:
                last = items[-1].core
                next_cursor = ClassificationHistoryCursor(last.classified_at_utc,
                                                          last.classification_id)
            return ClassificationHistoryPage(items, next_cursor)

        return self._read(select)
