"""Real Classification SQLite coverage for the internal Task-04 read boundary."""

from __future__ import annotations

import inspect
import sqlite3
import uuid
from datetime import timedelta

import pytest

from app.device_fingerprint.classification_persistence import (
    ClassificationPersistenceError, DeviceFingerprintClassificationStore, _CORE_FIELDS,
)
from app.device_fingerprint.classification_read import (
    ClassificationHistoryCursor, ClassificationHistoryPage,
    DeviceFingerprintClassificationReadService,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.validation import format_utc, parse_utc
from tests.device_fingerprint import SITE
from tests.device_fingerprint_task04_04d_persistence.test_classification_persistence import (
    persist_candidate, real_preacceptance_setup, real_production_setup, setup,
)
from tests.device_fingerprint_task04_04d_request.test_request_assembly import TIME
from tests.device_fingerprint_task04_t01.test_snapshot_service import MAC


def _read(store):
    return DeviceFingerprintClassificationReadService(store.database_path)


def _persisted(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    core = persist_candidate(store, assembly, retention)
    return store, assembly, core, _read(store)


def _mutate(store, statement, parameters=()):
    with sqlite3.connect(store.database_path) as connection:
        connection.execute(statement, parameters)


def _expect_unavailable(call):
    with pytest.raises(ClassificationPersistenceError) as caught:
        call()
    assert caught.value.reason_code == "persistence_unavailable"


def _time(seconds):
    return format_utc(parse_utc(TIME) + timedelta(seconds=seconds))


def test_empty_current_and_history_use_initialized_classification_database(tmp_path):
    store, _, _, _ = setup(tmp_path)
    service = _read(store)
    assert service.get_current(SITE, MAC) is None
    assert service.list_history(SITE, MAC, _time(-1), _time(1)) == (
        ClassificationHistoryPage((), None))


def test_current_returns_exact_retained_result_without_recomputation(tmp_path, monkeypatch):
    store, assembly, core, service = _persisted(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Normal read must not recompute")

    monkeypatch.setattr(DeviceFingerprintClassificationStore, "replay_level_b", forbidden)
    monkeypatch.setattr("app.device_fingerprint.fusion.fuse_classification", forbidden)
    monkeypatch.setattr(
        "app.device_fingerprint.request_assembly.DeviceFingerprintRequestAssembly.run", forbidden,
        raising=False,
    )
    record = service.get_current(SITE, MAC)
    assert record.core == core
    assert record.result.artifact_id == assembly.classification_result.artifact_id
    assert record.result.content_sha256 == assembly.classification_result.content_sha256
    assert record.result.semantic_payload_json == assembly.classification_result.semantic_payload_json


def test_site_isolation_and_accepted_mac_spelling(tmp_path):
    store, _, core, service = _persisted(tmp_path)
    site_b = "a" * 24 if SITE != "a" * 24 else "b" * 24
    with sqlite3.connect(store.database_path) as connection:
        connection.row_factory = sqlite3.Row
        original = dict(connection.execute(
            "SELECT * FROM classifications WHERE classification_id=?", (core.classification_id,),
        ).fetchone())
        original["classification_id"] = str(uuid.uuid4())
        original["site_id"] = site_b
        connection.execute(
            f"INSERT INTO classifications ({','.join(_CORE_FIELDS)}) "
            f"VALUES ({','.join('?' for _ in _CORE_FIELDS)})",
            tuple(original[name] for name in _CORE_FIELDS),
        )
    assert service.get_current(SITE, MAC).core.classification_id == core.classification_id
    assert service.get_current(site_b, MAC).core.site_id == site_b
    assert service.get_current(SITE, MAC.lower().replace(":", "-")).core == core


def test_current_uses_descending_timestamp_and_uuid_tie_break(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    stored = []
    for second in (0, 1, 1, -1):
        store._clock = lambda second=second: _time(second)
        stored.append(persist_candidate(store, assembly, retention))
    expected = max(stored, key=lambda core: (core.classified_at_utc, core.classification_id))
    assert _read(store).get_current(SITE, MAC).core == expected


def test_history_half_open_order_and_three_page_keyset_with_same_timestamp(tmp_path):
    store, _, assembly, retention = setup(tmp_path)
    stored = []
    for second in (0, 0, 1, 1, 2, 3):
        store._clock = lambda second=second: _time(second)
        stored.append(persist_candidate(store, assembly, retention))
    service = _read(store)
    expected = sorted(stored[:-1], key=lambda core: (core.classified_at_utc,
                                                     core.classification_id))
    cursor = None
    seen = []
    pages = []
    while True:
        page = service.list_history(SITE, MAC, _time(0), _time(3), limit=2, cursor=cursor)
        pages.append(page)
        seen.extend(record.core for record in page.items)
        if page.next_cursor is None:
            break
        assert page.next_cursor == ClassificationHistoryCursor(
            page.items[-1].core.classified_at_utc, page.items[-1].core.classification_id)
        cursor = page.next_cursor
    assert len(pages) == 3
    assert seen == expected
    assert len({core.classification_id for core in seen}) == len(seen)
    complete = service.list_history(SITE, MAC, _time(0), _time(3), limit=500)
    assert [record.core for record in complete.items] == seen
    assert complete.next_cursor is None
    assert service.list_history(SITE, MAC, _time(1), _time(2)).items == tuple(
        record for record in complete.items
        if record.core.classified_at_utc == _time(1))


@pytest.mark.parametrize("cursor", [
    "not-a-cursor",
    ClassificationHistoryCursor("bad", "11111111-1111-4111-8111-111111111111"),
    ClassificationHistoryCursor(TIME, "bad"),
    ClassificationHistoryCursor(TIME, "11111111-1111-1111-8111-111111111111"),
    ClassificationHistoryCursor(TIME, "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"),
])
def test_invalid_cursor_is_caller_validation_error(tmp_path, cursor):
    store, _, _, _ = setup(tmp_path)
    with pytest.raises(DeviceFingerprintValidationError):
        _read(store).list_history(SITE, MAC, _time(-1), _time(1), cursor=cursor)


@pytest.mark.parametrize("start,end", [(TIME, TIME), (_time(1), TIME)])
def test_invalid_range_is_caller_validation_error(tmp_path, start, end):
    store, _, _, _ = setup(tmp_path)
    with pytest.raises(DeviceFingerprintValidationError):
        _read(store).list_history(SITE, MAC, start, end)


@pytest.mark.parametrize("limit", [0, 501, True, "100"])
def test_invalid_limit_is_caller_validation_error(tmp_path, limit):
    store, _, _, _ = setup(tmp_path)
    with pytest.raises(DeviceFingerprintValidationError):
        _read(store).list_history(SITE, MAC, _time(-1), _time(1), limit=limit)


@pytest.mark.parametrize("site,mac", [("bad", MAC), (SITE, "not-a-mac")])
def test_invalid_identity_is_caller_validation_error(tmp_path, site, mac):
    store, _, _, _ = setup(tmp_path)
    with pytest.raises(DeviceFingerprintValidationError):
        _read(store).get_current(site, mac)


def test_missing_result_artifact_fails_closed(tmp_path):
    store, _, core, service = _persisted(tmp_path)
    _mutate(store, "DELETE FROM artifacts WHERE artifact_id=?", (core.classification_result_id,))
    _expect_unavailable(lambda: service.get_current(SITE, MAC))
    _expect_unavailable(lambda: service.list_history(SITE, MAC, _time(-1), _time(1)))


def test_core_and_result_use_one_read_transaction_under_concurrent_gc(tmp_path, monkeypatch):
    store, _, core, service = _persisted(tmp_path)
    with sqlite3.connect(store.database_path) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    original = DeviceFingerprintClassificationReadService._record

    def delete_after_core_selection(connection, row):
        with sqlite3.connect(store.database_path) as writer:
            writer.execute("DELETE FROM artifacts WHERE artifact_id=?",
                           (core.classification_result_id,))
        return original(connection, row)

    monkeypatch.setattr(DeviceFingerprintClassificationReadService, "_record",
                        staticmethod(delete_after_core_selection))
    assert service.get_current(SITE, MAC).core == core
    monkeypatch.setattr(DeviceFingerprintClassificationReadService, "_record",
                        staticmethod(original))
    _expect_unavailable(lambda: service.get_current(SITE, MAC))


@pytest.mark.parametrize("column", ["classification_result_digest", "classification_result_id"])
def test_wrong_result_identity_fails_closed(tmp_path, column):
    store, _, core, service = _persisted(tmp_path)
    value = "0" * 64 if column.endswith("digest") else (
        "ClassificationResult:v1:sha256:" + "0" * 64)
    _mutate(store, f"UPDATE classifications SET {column}=? WHERE classification_id=?",
            (value, core.classification_id))
    _expect_unavailable(lambda: service.get_current(SITE, MAC))


def test_corrupt_result_bytes_and_wrong_type_fail_closed(tmp_path):
    for mutation in ("semantic_payload_json", "artifact_type"):
        case = tmp_path / mutation
        case.mkdir()
        store, _, core, service = _persisted(case)
        value = b'{"corrupt":true}' if mutation == "semantic_payload_json" else "Other"
        _mutate(store, f"UPDATE artifacts SET {mutation}=? WHERE artifact_id=?",
                (value, core.classification_result_id))
        _expect_unavailable(lambda: service.get_current(SITE, MAC))


def test_core_and_result_request_digest_mismatch_fails_closed(tmp_path):
    store, _, core, service = _persisted(tmp_path)
    new_digest = "0" * 64
    new_id = "ClassificationRequestManifest:v1:sha256:" + new_digest
    _mutate(store, "UPDATE classifications SET classification_request_manifest_id=?, "
            "classification_request_manifest_digest=? WHERE classification_id=?",
            (new_id, new_digest, core.classification_id))
    _expect_unavailable(lambda: service.get_current(SITE, MAC))


@pytest.mark.parametrize("column,value", [
    ("site_id", "bad"),
    ("observed_mac", "bad"),
    ("classification_id", "not-a-uuid"),
    ("classified_at_utc", "bad"),
    ("execution_context", "BROKEN"),
    ("runtime_profile_activation_record_id", "11111111-1111-4111-8111-111111111111"),
    ("classification_runtime_profile_digest", "0" * 64),
])
def test_malformed_core_fails_closed(tmp_path, column, value):
    store, _, core, service = _persisted(tmp_path)
    with sqlite3.connect(store.database_path) as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(f"UPDATE classifications SET {column}=? WHERE classification_id=?",
                           (value, core.classification_id))
    _expect_unavailable(lambda: service._read(lambda connection: service._record(
        connection, connection.execute("SELECT * FROM classifications LIMIT 1").fetchone())))


def test_pre_acceptance_database_is_read_without_production_relabel(tmp_path):
    store, _, candidate, retention, foundation_admission = real_preacceptance_setup(tmp_path)
    core = store.persist(candidate, retention_policy=retention,
                         pre_acceptance_foundation_runtime_profile_admission_manifest=(
                             foundation_admission))
    record = _read(store).get_current(SITE, MAC)
    assert record.core == core
    assert record.core.execution_context == "PRE_ACCEPTANCE_CANDIDATE"
    assert record.core.runtime_profile_activation_record_id is None


def test_real_production_database_is_read_without_control_plane(tmp_path):
    store, _, assembly, retention, _, _ = real_production_setup(tmp_path)
    core = store.persist(assembly, retention_policy=retention)
    store._control = None
    record = _read(store).get_current(SITE, MAC)
    assert record.core == core
    assert record.core.execution_context == "PRODUCTION"
    assert record.core.runtime_profile_activation_record_id is not None


def test_missing_database_is_not_created(tmp_path):
    missing = tmp_path / "missing.sqlite"
    service = DeviceFingerprintClassificationReadService(missing)
    _expect_unavailable(lambda: service.get_current(SITE, MAC))
    assert not missing.exists()


def _clone_core(store, original, **changes):
    with sqlite3.connect(store.database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = dict(connection.execute("SELECT * FROM classifications WHERE classification_id=?",
                                      (original.classification_id,)).fetchone())
        row.update(classification_id=str(uuid.uuid4()), **changes)
        connection.execute(f"INSERT INTO classifications ({','.join(_CORE_FIELDS)}) "
                           f"VALUES ({','.join('?' for _ in _CORE_FIELDS)})",
                           tuple(row[field] for field in _CORE_FIELDS))
    return row


def test_production_batch_filters_candidates_orders_latest_and_is_site_scoped(tmp_path, monkeypatch):
    import hashlib
    store, _, assembly, retention, _, _ = real_production_setup(tmp_path)
    first = store.persist(assembly, retention_policy=retention)
    same_time = [_clone_core(store, first, classified_at_utc=_time(1)) for _ in range(2)]
    candidate = _clone_core(store, first, execution_context="PRE_ACCEPTANCE_CANDIDATE",
                           runtime_profile_activation_record_id=None, classified_at_utc=_time(2))
    other_mac = "00:11:22:33:44:55"
    other = _clone_core(store, first, observed_mac=other_mac)
    site_b = "f" * 24
    other_site = _clone_core(store, first, site_id=site_b, classified_at_utc=_time(5))
    reader = _read(store)
    expected = max(same_time, key=lambda row: row["classification_id"])
    assert reader.get_current(SITE, MAC).core.classification_id == candidate["classification_id"]
    assert reader.get_current_production(SITE, MAC).core.classification_id == expected["classification_id"]
    assert reader.get_current_production(site_b, MAC).core.classification_id == other_site["classification_id"]
    before = hashlib.sha256(store.database_path.read_bytes()).hexdigest()
    connect = sqlite3.connect
    opens, statements = [], []
    def counted(*args, **kwargs):
        opens.append((args, kwargs))
        connection = connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection
    monkeypatch.setattr(sqlite3, "connect", counted)
    def forbidden(*_args, **_kwargs):
        pytest.fail("Batch used an individual current read")
    monkeypatch.setattr(reader, "get_current", forbidden)
    monkeypatch.setattr(reader, "get_current_production", forbidden)
    result = reader.get_current_production_many(SITE, (MAC, MAC.lower().replace(":", "-"), other_mac,
                                                       "00:00:00:00:00:00"))
    assert len(result) == 3
    assert result[MAC].core.classification_id == expected["classification_id"]
    assert result[other_mac].core.classification_id == other["classification_id"]
    assert result["00:00:00:00:00:00"] is None
    assert len(opens) == 1 and "mode=ro" in opens[0][0][0]
    assert statements.count("BEGIN") == 1
    assert len([statement for statement in statements if statement.startswith("SELECT")]) == 2
    assert hashlib.sha256(store.database_path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("macs", ["AA:BB:CC:DD:EE:FF", ["bad"], [MAC] * 251, None])
def test_production_batch_rejects_invalid_or_unbounded_input_before_open(tmp_path, macs, monkeypatch):
    reader = DeviceFingerprintClassificationReadService(tmp_path / "never-created.sqlite")
    monkeypatch.setattr(reader, "_read", lambda _operation: pytest.fail("Invalid batch opened DB"))
    with pytest.raises(DeviceFingerprintValidationError):
        reader.get_current_production_many(SITE, macs)
    with pytest.raises(DeviceFingerprintValidationError):
        reader.get_current_production_many("invalid-site", (MAC,))
    assert reader.get_current_production_many(SITE, ()) == {}


def test_candidate_only_is_no_production_and_corrupt_production_fails_closed(tmp_path):
    store, _, core, reader = _persisted(tmp_path)
    assert reader.get_current_production(SITE, MAC) is None
    assert reader.get_current_production_many(SITE, (MAC,)) == {MAC: None}
    _mutate(store, "UPDATE classifications SET execution_context='PRODUCTION', "
            "runtime_profile_activation_record_id=?", (str(uuid.uuid4()),))
    assert reader.get_current_production(SITE, MAC).core.execution_context == "PRODUCTION"
    _mutate(store, "DELETE FROM artifacts WHERE artifact_id=?", (core.classification_result_id,))
    _expect_unavailable(lambda: reader.get_current_production_many(SITE, (MAC,)))
    _expect_unavailable(lambda: DeviceFingerprintClassificationReadService(tmp_path / "missing-production.sqlite")
                        .get_current_production(SITE, MAC))


@pytest.mark.parametrize("column,value", [
    ("semantic_payload_json", b'{"corrupt":true}'), ("artifact_type", "Other"),
])
def test_production_batch_retains_exact_artifact_integrity_checks(tmp_path, column, value):
    store, _, assembly, retention, _, _ = real_production_setup(tmp_path)
    core = store.persist(assembly, retention_policy=retention)
    _mutate(store, f"UPDATE artifacts SET {column}=? WHERE artifact_id=?",
            (value, core.classification_result_id))
    _expect_unavailable(lambda: _read(store).get_current_production_many(SITE, (MAC,)))


def test_required_history_index_columns_and_read_only_source_boundary(tmp_path):
    store, _, _, _ = setup(tmp_path)
    with sqlite3.connect(store.database_path) as connection:
        names = {row[1] for row in connection.execute("PRAGMA index_list(classifications)")}
        assert "idx_classifications_device_history_v1" in names
        columns = [row[2] for row in connection.execute(
            "PRAGMA index_info(idx_classifications_device_history_v1)")]
    assert columns == ["site_id", "observed_mac", "classified_at_utc", "classification_id"]
    source = inspect.getsource(__import__(
        "app.device_fingerprint.classification_read", fromlist=["*"]))
    for forbidden in (
        "DeviceFingerprintReadService", "DeviceFingerprintRepository",
        "DeviceFingerprintControlPlaneStore", "DeviceFingerprintRequestAssembly",
        "fuse_classification", "replay_level_b", "app.admin_web", "BEGIN IMMEDIATE",
        "INSERT INTO", "UPDATE ", "DELETE FROM", "REPLACE INTO", "CREATE TABLE",
    ):
        assert forbidden not in source
    assert "mode=ro" in source
    assert 'connection.execute("BEGIN")' in source
