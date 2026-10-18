"""Synthetic retained observations: no capture, classification or real device data."""
import hashlib
import sqlite3
from datetime import datetime, timezone

import pytest

from app.analytics.source_gateway import AnalyticsQueryDeadlineExceeded, QueryDeadline
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.schema import SCHEMA_SQL
from app.device_fingerprint.validation import canonical_json

SITE = "0123456789abcdef01234567"
MAC = "02:00:00:00:00:01"
AS_OF = "2026-10-18T00:00:00.000Z"
FIRST = "2026-10-01T00:00:00.000Z"


def portal(version=1, **changes):
    if version == 2:
        value = dict(model_family="Nokia G21", os_major=13, form_factor_mobile=True,
                     form_factor_tablet=False, form_factor_desktop=False,
                     model_source="sec_ch_ua_model", os_major_source="sec_ch_ua_platform_version",
                     form_factors_source="sec_ch_ua_form_factors")
    else:
        value = dict(platform_family="android", mobile_boolean=True,
                     browser_runtime_family="chromium", webview_or_captive_context=None,
                     model_family="Nokia G21", os_major=13, platform_source="user_agent",
                     mobile_source="user_agent", runtime_source="user_agent", context_source=None,
                     model_source="user_agent", os_major_source="user_agent", ua_present=True,
                     sec_ch_ua_present=False, sec_ch_ua_platform_present=False, sec_ch_ua_mobile_present=False)
    return value | changes


@pytest.fixture
def retained(tmp_path):
    path = tmp_path / "synthetic.sqlite3"
    db = sqlite3.connect(path)
    db.executescript(SCHEMA_SQL)
    sequence = 0

    def add(payload=None, *, kind="portal_headers", version=1,
            at="2026-10-17T10:00:00.000Z", site=SITE, mac=MAC,
            raw=None, digest=None, quality="valid"):
        nonlocal sequence
        sequence += 1
        identity = f"{sequence:08x}-1111-4111-8111-111111111111"
        text = raw if raw is not None else canonical_json(payload if payload is not None else portal())
        sha = digest or hashlib.sha256(text.encode()).hexdigest()
        db.execute("INSERT INTO device_fingerprint_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (identity, "synthetic", identity, kind, None, "synthetic", "1", version,
                    None, site, "synthetic", at, mac, None, "P1", quality, text, sha, at, sequence))
        db.commit()
    yield path, db, add
    db.close()


def read(path, **kwargs):
    return DeviceFingerprintReadService(str(path), retention_days=30).latest_observed_hints(
        SITE, MAC, site_first_seen_at=FIRST, as_of_utc=AS_OF,
        deadline=QueryDeadline.after(5), **kwargs)


@pytest.mark.parametrize("version", [1, 2])
def test_A01_A02_exact_portal_and_no_platform_synthesis(retained, version):
    path, _, add = retained
    add(portal(version), version=version)
    hints = read(path)
    assert hints["reported_model"]["value"] == "Nokia G21"
    assert hints["reported_os"]["os_major"] == 13
    assert hints["reported_os"]["platform_family"] == ("android" if version == 1 else None)
    assert hints["sources"][0]["fields"] == portal(version)


def test_A03_independent_values_keep_record_provenance(retained):
    path, _, add = retained
    add(portal(), at="2026-10-16T00:00:00.000Z")
    add(portal(2, model_family=None, model_source=None), version=2)
    hints = read(path)
    assert hints["reported_model"]["observed_at_utc"] == "2026-10-16T00:00:00.000Z"
    assert hints["reported_model"]["schema"] == "portal_headers/1"
    assert hints["reported_os"]["schema"] == "portal_headers/2"
    assert hints["reported_os"]["platform_family"] is None


@pytest.mark.parametrize("raw,version", [('{"x":1,"x":2}', 1), ('{bad', 1),
                                         (' {}', 1), ('{}', 999), ('{}', 1)])
def test_A10_A11_latest_bad_or_unsupported_never_uses_older_portal(retained, raw, version):
    path, _, add = retained
    add(portal(), at="2026-10-16T00:00:00.000Z")
    add(raw=raw, version=version)
    hints = read(path)
    assert hints["reported_model"] is None and hints["reported_os"] is None
    assert hints["sources"][0]["state"] == ("unsupported" if version == 999 else "unavailable")


def test_A08_A09_identity_retention_asof_and_total_cap(retained):
    path, _, add = retained
    add(portal(), site="1123456789abcdef01234567")
    add(portal(), mac="02:00:00:00:00:02")
    add(portal(), at="2026-09-30T23:59:59.999Z")
    add(portal(), at=AS_OF)
    assert read(path)["state"] == "no_evidence"
    add(portal(), at=FIRST)
    assert read(path)["state"] == "observed"
    for number in range(257):
        add(portal(model_family=f"Synthetic {number}"))
    result = read(path)
    assert result["reported_model"]["value"] == "Synthetic 256"
    assert len(result["sources"]) == 5


def test_A15_one_indexed_read_no_writes_and_hard_256(retained, monkeypatch):
    from app.device_fingerprint import read_service
    path, _, add = retained
    for _ in range(257):
        add(portal())
    statements, connections = [], []
    real_open = read_service.open_read_only

    def traced(path):
        connection = real_open(path)
        connection.set_trace_callback(statements.append)
        connections.append(connection)
        return connection
    monkeypatch.setattr(read_service, "open_read_only", traced)
    before = path.read_bytes()
    result = read(path)
    assert result["state"] == "observed"
    assert len(connections) == 1
    selects = [sql for sql in statements if sql.startswith("SELECT")]
    assert len(selects) == 1 and "LIMIT 256" in selects[0]
    assert not any(sql.startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "BEGIN")) for sql in statements)
    assert path.read_bytes() == before
    with sqlite3.connect(path) as plan_db:
        plan = plan_db.execute("EXPLAIN QUERY PLAN " + selects[0]).fetchall()
    assert "idx_df_evidence_site_mac_time" in repr(plan)
    assert "TEMP B-TREE" not in repr(plan)
    with pytest.raises(sqlite3.ProgrammingError):
        connections[0].execute("SELECT 1")


def test_A12_deadline_is_checked_before_connection(retained, monkeypatch):
    from app.device_fingerprint import read_service
    path, _, _ = retained
    monkeypatch.setattr(read_service, "open_read_only", lambda _: pytest.fail("must not open"))
    reader = DeviceFingerprintReadService(str(path), retention_days=30)
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        reader.latest_observed_hints(SITE, MAC, site_first_seen_at=FIRST, as_of_utc=AS_OF,
                                     deadline=QueryDeadline.after(0))


def test_A10_bad_hash_size_and_unsupported_independent_sources(retained):
    from tests.device_fingerprint.test_network_schemas import tls, quic
    path, _, add = retained
    add(portal(), digest="a" * 64)
    add(tls(), kind="tls_client")
    add(quic(), kind="quic_client", version=999)
    hints = read(path)
    assert hints["state"] == "observed"
    assert [group["state"] for group in hints["sources"]] == [
        "unavailable", "not_observed_in_bounded_window", "not_observed_in_bounded_window", "observed", "unsupported"]
    add(raw='{"oversized":"' + "a" * 65536 + '"}')
    assert read(path)["sources"][0]["state"] == "unavailable"


@pytest.mark.parametrize("tcp_version", [1, 2])
def test_A04_A05_A06_A07_full_five_groups_exact_fields(retained, tcp_version):
    from tests.device_fingerprint.test_network_schemas import tls, quic, tcp_v2
    path, _, add = retained
    dhcp = dict(message_type="discover", parameter_request_list=[1, 3, 6], option_order=[53, 55],
                vendor_class="Synthetic", client_identifier_kind="opaque", maximum_message_size=None,
                rapid_commit_requested=False, capport_requested=True, ipv6_only_preferred_requested=False,
                hostname_present=True)
    tcp = (dict(ip_version=4, observed_ttl=0, tcp_window=0, mss=0, window_scale=0,
                sack_permitted=False, timestamps_present=False, tcp_option_order=[]) if tcp_version == 1
           else tcp_v2(tcp_header_length_bytes=60, tcp_option_records=[dict(
               record_type="nop", kind=1, declared_length=None, available_value_length=0,
               structure_state="well_formed") for _ in range(40)]))
    payloads = [portal(), dhcp, tcp, tls(), quic()]
    kinds = ["portal_headers", "dhcp", "tcp_syn", "tls_client", "quic_client"]
    for kind, payload in zip(kinds, payloads):
        add(payload, kind=kind, version=tcp_version if kind == "tcp_syn" else 1, quality="degraded")
    hints = read(path)
    assert [group["source_kind"] for group in hints["sources"]] == kinds
    for group, payload in zip(hints["sources"], payloads):
        assert group["fields"] == payload
        assert group["quality_state"] == "degraded"
        assert group["observed_at_utc"] == "2026-10-17T10:00:00.000Z"
    assert [group["origin_category"] for group in hints["sources"]] == [
        "client_reported", "client_reported", "network_observed", "network_observed", "network_observed"]
    assert len(canonical_json(hints).encode()) < 65536


def test_A09_cap_excludes_257th_field_and_source(retained, monkeypatch):
    from app.device_fingerprint import read_service
    from tests.device_fingerprint.test_network_schemas import tls
    path, _, add = retained
    add(tls(), kind="tls_client", at="2026-10-16T00:00:00.000Z")
    add(portal(), at="2026-10-16T01:00:00.000Z")
    for _ in range(256):
        add(portal(2, model_family=None, model_source=None), version=2)
    calls = []
    real_verify = read_service.verify_persisted_payload
    def counted(*args):
        calls.append(len(args[2].encode()))
        return real_verify(*args)
    monkeypatch.setattr(read_service, "verify_persisted_payload", counted)
    hints = read(path)
    assert len(calls) == 256 and sum(calls) <= 256 * 65536
    assert hints["reported_model"] is None
    assert hints["sources"][3]["state"] == "not_observed_in_bounded_window"


def test_A08_retention_and_first_seen_lower_bound_is_inclusive(retained):
    path, _, add = retained
    add(portal(), at="2026-09-17T23:59:59.999Z")
    reader = DeviceFingerprintReadService(str(path), retention_days=30)
    kwargs = dict(site_first_seen_at="2026-01-01T00:00:00.000Z", as_of_utc=AS_OF,
                  deadline=QueryDeadline.after(5))
    assert reader.latest_observed_hints(SITE, MAC, **kwargs)["state"] == "no_evidence"
    add(portal(), at="2026-09-18T00:00:00.000Z")
    assert reader.latest_observed_hints(SITE, MAC, **kwargs)["reported_model"]["value"] == "Nokia G21"


def test_A12_materialization_checks_deadline_and_closes_connection(retained, monkeypatch):
    from app.device_fingerprint import read_service
    path, _, add = retained
    add(portal())
    clock = [0.0]
    deadline = QueryDeadline.after(2, monotonic=lambda: clock[0])
    original = read_service.verify_persisted_payload
    def expiry(*args):
        verified = original(*args)
        clock[0] = 3.0
        return verified
    monkeypatch.setattr(read_service, "verify_persisted_payload", expiry)
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        DeviceFingerprintReadService(str(path), retention_days=30).latest_observed_hints(
            SITE, MAC, site_first_seen_at=FIRST, as_of_utc=AS_OF, deadline=deadline)


@pytest.mark.parametrize("version", [1, 2])
def test_A03_portal_search_stops_at_corrupt_or_unsupported_candidate(retained, version):
    path, _, add = retained
    add(portal(), at="2026-10-15T00:00:00.000Z")
    add(raw="{}", version=999 if version == 2 else 1, at="2026-10-16T00:00:00.000Z")
    add(portal(2, model_family=None, model_source=None), version=2)
    hints = read(path)
    assert hints["sources"][0]["state"] == ("unsupported" if version == 2 else "unavailable")
    assert hints["reported_model"] is hints["reported_os"] is None


@pytest.mark.parametrize("changes", [{"site_id": "bad"}, {"observed_mac": "bad"},
                                     {"site_first_seen_at": "bad"}, {"as_of_utc": "bad"}])
def test_A08_invalid_identity_and_time_fail_before_sql(retained, monkeypatch, changes):
    from app.device_fingerprint import read_service
    from app.device_fingerprint.models import DeviceFingerprintValidationError
    path, _, _ = retained
    monkeypatch.setattr(read_service, "open_read_only", lambda _: pytest.fail("invalid boundary must not open DB"))
    kwargs = dict(site_id=SITE, observed_mac=MAC, site_first_seen_at=FIRST, as_of_utc=AS_OF,
                  deadline=QueryDeadline.after(5)) | changes
    with pytest.raises(DeviceFingerprintValidationError):
        DeviceFingerprintReadService(str(path), retention_days=30).latest_observed_hints(**kwargs)


@pytest.mark.parametrize("active_writer", [False, True], ids=["checkpointed", "active_committed_wal"])
def test_A15_wal_read_preserves_application_bytes_schema_and_readonly_boundary(retained, monkeypatch, active_writer):
    """Native coordination sidecars are allowed; application changes are not."""
    from app.device_fingerprint import read_service
    path, db, add = retained
    assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    schema_sql = "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
    schema_before = tuple(db.execute(schema_sql))
    if active_writer:
        add(portal())
        assert db.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == 1
    else:
        db.close()  # Normal writer shutdown; no manual checkpoint/sidecar handling.
    before_files = {item.name for item in path.parent.iterdir()}
    if not active_writer:
        assert before_files == {path.name}
    wal = path.with_name(path.name + "-wal")
    wal_before = wal.read_bytes() if wal.exists() else None
    if active_writer:
        assert wal_before  # Committed data really resides in a live WAL.
    digest = lambda data: hashlib.sha256(data).hexdigest()
    main_before = digest(path.read_bytes())
    statements, connections = [], []
    existing_open = read_service.open_read_only

    def traced_open(db_path):
        connection = existing_open(db_path)
        connection.set_trace_callback(statements.append)
        connections.append(connection)
        return connection
    monkeypatch.setattr(read_service, "open_read_only", traced_open)

    def assert_readonly(main_after, schema_after, sql):
        assert main_after == main_before
        assert schema_after == schema_before
        assert len(sql) == 1 and sql[0].lstrip().upper().startswith("SELECT ")

    hints = read(path)
    assert hints["state"] == ("observed" if active_writer else "no_evidence")
    if active_writer:
        assert hints["reported_model"]["value"] == "Nokia G21"
        assert wal.read_bytes() == wal_before  # No new application WAL frames.
        assert not db.in_transaction
        assert db.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == 1
    elif wal.exists():
        assert wal.read_bytes() == b""  # Empty native WAL, no transaction frames.
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError):
        connections[0].execute("SELECT 1")
    audit = existing_open(str(path))
    try:
        schema_after = tuple(tuple(row) for row in audit.execute(schema_sql))
        assert_readonly(digest(path.read_bytes()), schema_after, statements)
        with pytest.raises(sqlite3.OperationalError, match="readonly|read-only"):
            audit.execute("DELETE FROM device_fingerprint_evidence")
        assert audit.total_changes == 0
    finally:
        audit.close()
    allowed_files = before_files | {path.name + "-wal", path.name + "-shm"}
    assert {item.name for item in path.parent.iterdir()} <= allowed_files
    assert digest(path.read_bytes()) == main_before
    # Canaries exercise the same invariant, not a weaker secondary assertion.
    canary = path.parent / "synthetic-mutated-main.sqlite3"
    canary.write_bytes(path.read_bytes() + b"negative-main-byte-canary")
    with pytest.raises(AssertionError):
        assert_readonly(digest(canary.read_bytes()), schema_after, statements)
    with pytest.raises(AssertionError):
        assert_readonly(main_before, schema_after, statements + ["INSERT INTO synthetic VALUES (1)"])
    with pytest.raises(AssertionError):
        assert_readonly(main_before, schema_after + (("table", "unexpected", "unexpected", "CREATE TABLE unexpected(x)"),), statements)
