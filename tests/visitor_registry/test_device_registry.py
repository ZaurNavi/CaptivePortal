from __future__ import annotations

import json
import os
import socket
import sqlite3
import threading
import time
from copy import deepcopy
from pathlib import Path

import pytest

from app.visitor_registry import cli as registry_cli
from app.visitor_registry import registry_config as registry_config_module
from app.visitor_registry import registry_reader as registry_reader_module
from app.visitor_registry.device_ids import (
    VISITOR_DEVICE_NAMESPACE,
    build_device_id,
)
from app.visitor_registry.registry_config import (
    RegistryConfigError,
    ensure_registry_parent,
    registry_config_from_settings,
)
from app.visitor_registry.registry_models import (
    ApplyOutcome,
    DecisionKind,
    RegistryConfig,
    RegistrySchemaError,
    SourceLineRecord,
)
from app.visitor_registry.registry_reader import (
    VisitorRegistryReader,
    source_checkpoint,
    source_identity,
    strict_json_object,
)
from app.visitor_registry.registry_repository import (
    VisitorRegistryRepository,
)
from app.visitor_registry.registry_service import (
    VisitorRegistryService,
    canonical_event_sha256,
    normalize_timestamp,
)
from app.visitor_registry.registry_telemetry import (
    VisitorRegistryTelemetry,
)
from app.visitor_registry.registry_worker import (
    UnavailableVisitorRegistry,
    VisitorRegistryWorker,
    create_visitor_registry,
)
from app.visitor_registry.snapshot_ids import build_snapshot_id


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "visitor_snapshot_captured_production_anonymized.json"
)
ALREADY_AUTHORIZED_FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "visitor_snapshot_captured_production_already_authorized_anonymized.json"
)


class CaptureTelemetry:
    def __init__(self):
        self.events = []

    def safe_emit_system(self, event, level, **fields):
        self.events.append({
            "event": event,
            "level": level,
            **fields,
        })
        return True


def settings(tmp_path: Path, **updates):
    values = {
        "visitor_registry_enabled": "true",
        "visitor_registry_db_path": str(
            tmp_path / "data" / "visitor_registry.sqlite3"
        ),
        "visitor_registry_scan_interval_seconds": "5",
        "visitor_registry_shutdown_timeout_seconds": "10",
        "visitor_registry_max_line_bytes": "4194304",
        "visitor_snapshot_log_file": str(
            tmp_path / "logs" / "visitor_snapshots.log"
        ),
        "visitor_snapshot_rotation_backup_count": "20",
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_db_path": str(tmp_path / "portal.db"),
        "public_traffic_db_path": str(tmp_path / "traffic.db"),
        "auth_telemetry_log_path": str(tmp_path / "auth.log"),
        "omada_webhook_log_file": str(tmp_path / "webhook.log"),
        "omada_webhook_normalized_log_file": str(
            tmp_path / "normalized.log"
        ),
    }
    values.update(updates)
    return values


def registry_config(tmp_path: Path, **updates) -> RegistryConfig:
    data = tmp_path / "data"
    logs = tmp_path / "logs"
    _mkdir_private(data)
    _mkdir_private(logs)
    return registry_config_from_settings(settings(tmp_path, **updates))


def _mkdir_private(path: Path) -> None:
    path.mkdir(mode=0o750, exist_ok=True)
    if os.name == "posix":
        path.chmod(0o750)


def fixture_event() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def event_for(
    *,
    session_id: str,
    mac: str = "02:11:22:33:44:55",
    authorized_at: str = "2026-07-30T11:00:00.000Z",
    captured_at: str = "2026-07-30T11:00:01.000Z",
    hostname: str | None = "fixture-android",
    ssid: str | None = "Zefer_Parki",
    site_id: str = "fixture-site-001",
) -> dict:
    event = fixture_event()
    event["auth_session_id"] = session_id
    event["requested_mac"] = mac
    event["client"]["mac"] = mac
    event["raw_controller_snapshot"]["mac"] = mac
    event["snapshot_id"] = build_snapshot_id(session_id, mac)
    event["authorized_at"] = authorized_at
    event["captured_at"] = captured_at
    event["client"]["hostname"] = hostname
    event["client"]["ssid"] = ssid
    event["site_id"] = site_id
    return event


def deeply_nested_unknown_value(depth: int = 550) -> dict:
    value = {"preserved": True}
    for _ in range(depth):
        value = {"nested": value}
    return value


def make_stack(
    tmp_path: Path,
    *,
    max_line_bytes=4_194_304,
    **updates,
):
    config = registry_config(
        tmp_path,
        visitor_registry_max_line_bytes=str(max_line_bytes),
        **updates,
    )
    service = VisitorRegistryService(config.timezone_name)
    repository = VisitorRegistryRepository(config)
    repository.initialize(service.now_iso())
    captured = CaptureTelemetry()
    telemetry = VisitorRegistryTelemetry(
        telemetry_provider=lambda: captured
    )
    reader = VisitorRegistryReader(
        config=config,
        repository=repository,
        service=service,
        telemetry=telemetry,
    )
    return config, service, repository, reader, captured


def append_event(path: str, event: dict, *, newline=True):
    with open(path, "ab") as stream:
        stream.write(
            json.dumps(
                event,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if newline:
            stream.write(b"\n")


def test_registry_is_disabled_by_default_until_separate_activation(tmp_path):
    value = settings(tmp_path)
    value.pop("visitor_registry_enabled")
    assert registry_config_from_settings(value).enabled is False


def test_enabled_factory_migrates_without_starting_thread(tmp_path):
    _mkdir_private(tmp_path / "data")
    _mkdir_private(tmp_path / "logs")
    captured = CaptureTelemetry()
    telemetry = VisitorRegistryTelemetry(
        telemetry_provider=lambda: captured
    )

    registry = create_visitor_registry(
        settings(tmp_path),
        telemetry=telemetry,
    )

    assert isinstance(registry, VisitorRegistryWorker)
    assert registry.running is False
    assert Path(registry.config.db_path).is_file()
    assert [
        item["event"] for item in captured.events
    ] == ["visitor_registry_migration_completed"]


def test_corrupt_database_is_preserved_and_factory_remains_fail_open(
    tmp_path,
):
    data = tmp_path / "data"
    logs = tmp_path / "logs"
    _mkdir_private(data)
    _mkdir_private(logs)
    database = data / "visitor_registry.sqlite3"
    evidence = b"not-a-sqlite-database"
    database.write_bytes(evidence)
    captured = CaptureTelemetry()

    registry = create_visitor_registry(
        settings(tmp_path),
        telemetry=VisitorRegistryTelemetry(
            telemetry_provider=lambda: captured
        ),
    )

    assert isinstance(registry, UnavailableVisitorRegistry)
    assert database.read_bytes() == evidence
    names = [item["event"] for item in captured.events]
    assert "visitor_registry_corrupt_database" in names
    assert "visitor_registry_unavailable" in names


def test_disabled_config_ignores_unused_invalid_values(tmp_path):
    config = registry_config_from_settings({
        "visitor_registry_enabled": "false",
        "visitor_registry_db_path": "",
        "visitor_snapshot_log_file": "",
        "visitor_snapshot_rotation_backup_count": "bad",
        "portal_counter_timezone": "bad",
        "visitor_registry_scan_interval_seconds": "bad",
        "visitor_registry_shutdown_timeout_seconds": "bad",
        "visitor_registry_max_line_bytes": "bad",
    })
    assert config.enabled is False


@pytest.mark.parametrize("error", [OSError("denied"), RuntimeError("loop")])
def test_path_validation_failures_are_normalized_as_config_errors(
    tmp_path,
    monkeypatch,
    error,
):
    def fail_resolve(self, *args, **kwargs):
        raise error

    monkeypatch.setattr(Path, "resolve", fail_resolve)

    with pytest.raises(
        RegistryConfigError,
        match="path validation failed",
    ):
        registry_config_from_settings(settings(tmp_path))


@pytest.mark.parametrize(
    "key,value",
    [
        ("visitor_registry_scan_interval_seconds", "0"),
        ("visitor_registry_shutdown_timeout_seconds", "-1"),
        ("visitor_registry_max_line_bytes", "0"),
        ("visitor_snapshot_rotation_backup_count", "-1"),
        ("visitor_snapshot_rotation_backup_count", "no"),
        ("portal_counter_timezone", "Not/A_Timezone"),
    ],
)
def test_enabled_config_rejects_invalid_values(tmp_path, key, value):
    with pytest.raises(RegistryConfigError):
        registry_config_from_settings(settings(tmp_path, **{key: value}))


def test_zero_snapshot_rotation_backup_count_is_accepted(tmp_path):
    config = registry_config(
        tmp_path,
        visitor_snapshot_rotation_backup_count="0",
    )

    assert config.source_backup_count == 0


def test_zero_snapshot_rotation_backup_count_reads_only_active_log(
    tmp_path,
):
    config, _, repository, reader, _ = make_stack(
        tmp_path,
        visitor_snapshot_rotation_backup_count="0",
    )
    append_event(
        f"{config.source_log_path}.1",
        event_for(
            session_id="rotated",
            mac="02:11:22:33:44:66",
        ),
    )
    append_event(
        config.source_log_path,
        event_for(session_id="active"),
    )

    assert reader.scan().complete
    assert repository.get_device_by_mac(
        "02:11:22:33:44:55"
    ) is not None
    assert repository.get_device_by_mac(
        "02:11:22:33:44:66"
    ) is None


@pytest.mark.parametrize(
    "collision_key",
    [
        "visitor_snapshot_log_file",
        "portal_counter_db_path",
        "public_traffic_db_path",
        "auth_telemetry_log_path",
        "omada_webhook_log_file",
        "omada_webhook_normalized_log_file",
    ],
)
def test_database_path_rejects_configured_file_collisions(
    tmp_path,
    collision_key,
):
    db_path = str(tmp_path / "registry.sqlite3")
    with pytest.raises(RegistryConfigError, match="conflicts"):
        registry_config_from_settings(settings(
            tmp_path,
            visitor_registry_db_path=db_path,
            **{collision_key: db_path},
        ))


def test_external_missing_parent_is_not_created(tmp_path):
    config = registry_config(
        tmp_path,
        visitor_registry_db_path=str(
            tmp_path / "missing" / "outside.sqlite3"
        ),
    )
    with pytest.raises(RegistryConfigError):
        ensure_registry_parent(config)
    assert not (tmp_path / "missing").exists()


def test_public_web_tree_and_rotated_journal_collisions_are_rejected(
    tmp_path,
):
    public_db = (
        Path(__file__).parents[2]
        / "app"
        / "web"
        / "static"
        / "visitor_registry.sqlite3"
    )
    with pytest.raises(RegistryConfigError, match="public"):
        registry_config_from_settings(settings(
            tmp_path,
            visitor_registry_db_path=str(public_db),
        ))

    rotated = f"{settings(tmp_path)['visitor_snapshot_log_file']}.1"
    with pytest.raises(RegistryConfigError, match="conflicts"):
        registry_config_from_settings(settings(
            tmp_path,
            visitor_registry_db_path=rotated,
        ))


def test_existing_hardlink_collision_is_rejected_by_file_identity(
    tmp_path,
):
    data = tmp_path / "data"
    logs = tmp_path / "logs"
    _mkdir_private(data)
    _mkdir_private(logs)
    source = logs / "visitor_snapshots.log"
    source.write_text("", encoding="utf-8")
    database_alias = data / "visitor_registry.sqlite3"
    os.link(source, database_alias)

    with pytest.raises(RegistryConfigError, match="conflicts"):
        registry_config_from_settings(settings(
            tmp_path,
            visitor_registry_db_path=str(database_alias),
            visitor_snapshot_log_file=str(source),
        ))


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory mode only")
def test_approved_missing_parent_is_created_with_0750(
    tmp_path,
    monkeypatch,
):
    allowed = tmp_path / "approved-data"
    monkeypatch.setattr(
        registry_config_module,
        "ALLOWED_AUTO_CREATE_ROOT",
        allowed,
    )
    config = registry_config_from_settings(settings(
        tmp_path,
        visitor_registry_db_path=str(
            allowed / "nested" / "visitor_registry.sqlite3"
        ),
    ))

    ensure_registry_parent(config)

    parent = allowed / "nested"
    assert parent.is_dir()
    assert (parent.stat().st_mode & 0o777) == 0o750


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory mode only")
@pytest.mark.parametrize(
    ("mode", "accepted"),
    [
        (0o777, False),
        (0o755, False),
        (0o750, True),
        (0o700, True),
    ],
)
def test_existing_registry_parent_requires_private_posix_mode(
    tmp_path,
    mode,
    accepted,
):
    parent = tmp_path / f"mode-{mode:o}"
    parent.mkdir()
    parent.chmod(mode)
    config = registry_config_from_settings(settings(
        tmp_path,
        visitor_registry_db_path=str(parent / "registry.sqlite3"),
    ))

    if accepted:
        ensure_registry_parent(config)
    else:
        with pytest.raises(RegistryConfigError, match="permissions"):
            ensure_registry_parent(config)


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink only")
@pytest.mark.parametrize("target_kind", ["temporary", "public_tree"])
def test_existing_database_symlink_is_rejected(
    tmp_path,
    target_kind,
):
    data = tmp_path / "data"
    _mkdir_private(data)
    database = data / "visitor_registry.sqlite3"
    if target_kind == "temporary":
        unsafe = tmp_path / "unsafe"
        unsafe.mkdir()
        unsafe.chmod(0o777)
        target = unsafe / "actual.sqlite3"
        target.touch()
    else:
        target = (
            Path(__file__).parents[2]
            / "app"
            / "web"
            / "static"
        )
    database.symlink_to(target, target_is_directory=target.is_dir())
    with pytest.raises(RegistryConfigError):
        config = registry_config_from_settings(settings(
            tmp_path,
            visitor_registry_db_path=str(database),
        ))
        ensure_registry_parent(config)


def test_existing_database_directory_is_rejected(tmp_path):
    database = tmp_path / "database-directory"
    _mkdir_private(database)
    config = registry_config_from_settings(settings(
        tmp_path,
        visitor_registry_db_path=str(database),
    ))

    with pytest.raises(RegistryConfigError, match="regular file"):
        ensure_registry_parent(config)


@pytest.mark.skipif(os.name != "posix", reason="POSIX FIFO only")
def test_existing_database_fifo_is_rejected(tmp_path):
    data = tmp_path / "data"
    _mkdir_private(data)
    database = data / "visitor_registry.sqlite3"
    os.mkfifo(database)
    config = registry_config_from_settings(settings(
        tmp_path,
        visitor_registry_db_path=str(database),
    ))

    with pytest.raises(RegistryConfigError, match="regular file"):
        ensure_registry_parent(config)


def test_existing_regular_database_file_is_accepted(tmp_path):
    data = tmp_path / "data"
    _mkdir_private(data)
    database = data / "visitor_registry.sqlite3"
    database.touch()
    config = registry_config_from_settings(settings(
        tmp_path,
        visitor_registry_db_path=str(database),
    ))

    ensure_registry_parent(config)


def test_device_namespace_and_mac_formats_are_stable():
    assert str(VISITOR_DEVICE_NAMESPACE) == (
        "afca1c95-15b2-446d-b10d-ab47f0090b76"
    )
    expected = build_device_id("02:11:22:33:44:55")
    assert build_device_id("02-11-22-33-44-55") == expected
    assert build_device_id("0211.2233.4455") == expected


def test_fixture_is_accepted_and_unknown_client_fields_are_retained():
    service = VisitorRegistryService("Asia/Baku")
    decision = service.decide(fixture_event())
    assert decision.kind is DecisionKind.STORE
    assert decision.snapshot is not None
    assert decision.snapshot.mac == "02:11:22:33:44:55"
    assert decision.snapshot.portal_client_ip == "192.0.2.27"
    client = json.loads(decision.snapshot.client_json)
    assert client["future_unknown_field"] == {"preserved": True}


@pytest.mark.parametrize(
    ("section", "json_column"),
    [
        ("client", "client_json"),
        ("auth_context", "auth_context_json"),
        (
            "raw_controller_snapshot",
            "raw_controller_snapshot_json",
        ),
    ],
)
def test_deep_unknown_captured_fields_are_stored_without_recursion(
    tmp_path,
    section,
    json_column,
):
    config, service, repository, reader, captured = make_stack(tmp_path)
    event = fixture_event()
    event[section]["future_unknown_field"] = (
        deeply_nested_unknown_value()
    )
    append_event(config.source_log_path, event)
    worker = VisitorRegistryWorker(
        repository=repository,
        service=service,
        reader=reader,
        telemetry=VisitorRegistryTelemetry(
            telemetry_provider=lambda: captured
        ),
    )

    worker.run_once()

    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        config.source_log_path
    ).stat().st_size
    assert repository.get_status(True).registry_state == "ready"
    with sqlite3.connect(config.db_path) as connection:
        stored_json = connection.execute(
            f"SELECT {json_column} FROM device_snapshots"
        ).fetchone()[0]
    current = json.loads(stored_json)["future_unknown_field"]
    for _ in range(550):
        current = current["nested"]
    assert current == {"preserved": True}


@pytest.mark.parametrize(
    "fixture_path",
    [FIXTURE, ALREADY_AUTHORIZED_FIXTURE],
)
def test_production_fixtures_are_accepted_and_contain_no_secret_keys(
    fixture_path,
):
    event = json.loads(fixture_path.read_text(encoding="utf-8"))
    decision = VisitorRegistryService("Asia/Baku").decide(event)
    assert decision.kind is DecisionKind.STORE
    assert decision.snapshot is not None
    assert decision.snapshot.portal_ssid is None
    assert decision.snapshot.portal_ap_mac is None
    if fixture_path == ALREADY_AUTHORIZED_FIXTURE:
        assert decision.snapshot.auth_final_reason == "ALREADY_AUTHORIZED"
        assert decision.snapshot.authorization_attempt == 0

    forbidden = {
        "accesstoken",
        "access_token",
        "clientsecret",
        "client_secret",
        "authorization",
        "cookie",
        "password",
        "ssidpassword",
    }

    def keys(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                yield key.casefold()
                yield from keys(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from keys(nested)

    assert forbidden.isdisjoint(keys(event))
    mixed_case_keys = set(keys({
        "nested": {
            "Authorization": "secret",
            "Password": "secret",
            "Cookie": "secret",
            "AccessToken": "secret",
        },
    }))
    assert {
        "authorization",
        "password",
        "cookie",
        "accesstoken",
    }.issubset(forbidden.intersection(mixed_case_keys))


def test_timestamp_offsets_normalize_to_milliseconds_utc():
    assert normalize_timestamp("2026-07-30T15:00:00.123456+04:00") == (
        "2026-07-30T11:00:00.123Z"
    )
    with pytest.raises(ValueError):
        normalize_timestamp("2026-07-30T15:00:00")


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (
            lambda item: item.pop("authorized_at"),
            "missing_required_field",
        ),
        (
            lambda item: item.__setitem__("attempts", True),
            "invalid_field_type",
        ),
        (
            lambda item: item.__setitem__("attempts", -1),
            "invalid_field_range",
        ),
        (
            lambda item: item.__setitem__("authorized_at", "naive"),
            "invalid_field_format",
        ),
        (
            lambda item: item["auth_context"].__setitem__(
                "auth_final_reason",
                "UNKNOWN",
            ),
            "invalid_field_value",
        ),
        (
            lambda item: item["client"].__setitem__(
                "mac",
                "02:AA:BB:CC:DD:EE",
            ),
            "client_mac_mismatch",
        ),
        (
            lambda item: item.__setitem__(
                "snapshot_id",
                "00000000-0000-4000-8000-000000000000",
            ),
            "snapshot_id_mismatch",
        ),
        (
            lambda item: item.__setitem__("schema_version", 2),
            "unsupported_schema_version",
        ),
    ],
)
def test_closed_skip_reason_contract(mutate, reason):
    event = fixture_event()
    mutate(event)
    decision = VisitorRegistryService("Asia/Baku").decide(event)
    assert decision.kind is DecisionKind.SKIP
    assert decision.skip_reason == reason


@pytest.mark.parametrize("snapshot_id", [None, "", "not-a-uuid", 3])
def test_unusable_snapshot_id_advances_without_processed_decision(
    snapshot_id,
):
    event = fixture_event()
    event["snapshot_id"] = snapshot_id
    decision = VisitorRegistryService("Asia/Baku").decide(event)
    assert decision.kind is DecisionKind.ADVANCE
    assert decision.snapshot_id is None
    assert decision.warning_reason is not None


def test_non_target_event_is_only_advanced():
    event = fixture_event()
    event["event"] = "visitor.client_snapshot.failed"
    decision = VisitorRegistryService("Asia/Baku").decide(event)
    assert decision.kind is DecisionKind.ADVANCE
    assert decision.warning_reason is None


def test_auth_context_is_strict_and_canonicalized():
    event = fixture_event()
    event["auth_context"]["client_ip"] = "2001:0db8::1"
    event["auth_context"]["portal_ap_mac"] = "02-aa-bb-cc-dd-ee"
    decision = VisitorRegistryService("Asia/Baku").decide(event)
    assert decision.snapshot.portal_client_ip == "2001:db8::1"
    assert decision.snapshot.portal_ap_mac == "02:AA:BB:CC:DD:EE"


@pytest.mark.parametrize(
    "field",
    [
        "client_ip",
        "portal_ssid",
        "portal_ap_mac",
        "portal_radio_id",
        "auth_run_number",
        "authorization_attempt",
        "auth_final_reason",
        "retry_request_id",
    ],
)
def test_every_auth_context_key_is_required(field):
    event = fixture_event()
    event["auth_context"].pop(field)
    decision = VisitorRegistryService("Asia/Baku").decide(event)
    assert decision.kind is DecisionKind.SKIP
    assert decision.skip_reason == "missing_required_field"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("radio_id", True, "invalid_field_type"),
        ("traffic_down", -1, "invalid_field_range"),
        ("auth_status", 2**80, "invalid_field_range"),
        ("ip", "999.1.1.1", "invalid_field_format"),
        ("ap_mac", "not-a-mac", "invalid_field_format"),
    ],
)
def test_known_client_fields_are_strict(field, value, reason):
    event = fixture_event()
    event["client"][field] = value
    decision = VisitorRegistryService("Asia/Baku").decide(event)
    assert decision.kind is DecisionKind.SKIP
    assert decision.skip_reason == reason


def test_strict_json_rejects_duplicate_keys_constants_and_root_array():
    with pytest.raises(ValueError):
        strict_json_object('{"a":1,"a":2}')
    with pytest.raises(ValueError):
        strict_json_object('{"a":NaN}')
    with pytest.raises(ValueError):
        strict_json_object("[]")
    with pytest.raises(ValueError):
        strict_json_object('{"a":"\\ud800"}')


@pytest.mark.parametrize("number", ["1e400", "-1e400"])
def test_strict_json_rejects_numeric_overflow(number):
    with pytest.raises(ValueError, match="unsafe scalar"):
        strict_json_object(f'{{"value":{number}}}')


def test_deep_json_never_exposes_recursion_error(monkeypatch):
    value: object = "\ud800"
    for _ in range(1_500):
        value = {"nested": value}
    monkeypatch.setattr(
        registry_reader_module.json,
        "loads",
        lambda *args, **kwargs: value,
    )

    with pytest.raises(ValueError, match="unsafe scalar"):
        strict_json_object('{"placeholder":true}')


def test_numeric_overflow_line_advances_and_next_event_is_processed(
    tmp_path,
):
    config, service, repository, reader, captured = make_stack(tmp_path)
    Path(config.source_log_path).write_bytes(b'{"value":1e400}\n')
    append_event(config.source_log_path, fixture_event())
    worker = VisitorRegistryWorker(
        repository=repository,
        service=service,
        reader=reader,
        telemetry=VisitorRegistryTelemetry(
            telemetry_provider=lambda: captured
        ),
    )

    worker.run_once()

    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        config.source_log_path
    ).stat().st_size
    assert repository.get_device_by_mac(
        "02:11:22:33:44:55"
    )["snapshot_count"] == 1
    assert repository.get_status(True).registry_state == "ready"
    assert any(
        item["event"] == "visitor_registry_invalid_json_line"
        for item in captured.events
    )


def test_deep_malformed_line_advances_and_next_event_is_processed(
    tmp_path,
):
    config, service, repository, reader, captured = make_stack(tmp_path)
    event = fixture_event()
    deep_line = (
        ('{"nested":' * 1_500)
        + '"\\ud800"'
        + ("}" * 1_500)
        + "\n"
    )
    Path(config.source_log_path).write_text(
        deep_line,
        encoding="utf-8",
    )
    append_event(config.source_log_path, event)
    worker = VisitorRegistryWorker(
        repository=repository,
        service=service,
        reader=reader,
        telemetry=VisitorRegistryTelemetry(
            telemetry_provider=lambda: captured
        ),
    )

    worker.run_once()

    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        config.source_log_path
    ).stat().st_size
    assert repository.get_device_by_mac(
        "02:11:22:33:44:55"
    )["snapshot_count"] == 1
    assert repository.get_status(True).registry_state == "ready"
    assert any(
        item["event"] == "visitor_registry_invalid_json_line"
        for item in captured.events
    )


def test_event_hash_ignores_key_order_and_whitespace():
    first = {"b": [2], "a": 1}
    second = json.loads('{\n "a":1, "b":[2]\n}')
    assert canonical_event_sha256(first) == canonical_event_sha256(
        second
    )


def test_schema_and_singleton_are_created(tmp_path):
    config, service, repository, _, _ = make_stack(tmp_path)
    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        state = connection.execute(
            """
            SELECT state, initial_backfill_completed,
                   initial_backfill_completed_at
            FROM registry_state
            WHERE singleton_id = 1
            """
        ).fetchone()
    assert state == ("initializing", 0, None)
    assert repository.get_status(True).database_ready


def test_startup_rejects_singleton_with_invalid_runtime_state(tmp_path):
    config, service, repository, _, _ = make_stack(tmp_path)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "UPDATE registry_state SET state = 'invalid-state'"
        )

    with pytest.raises(
        RegistrySchemaError,
        match="state singleton is invalid",
    ):
        repository.initialize(service.now_iso())


@pytest.mark.parametrize(
    "failure_stage",
    [
        "before_registry_state_insert",
        "after_registry_state_insert",
    ],
)
def test_schema_migration_is_atomic_across_singleton_insert(
    tmp_path,
    monkeypatch,
    failure_stage,
):
    config = registry_config(tmp_path)
    repository = VisitorRegistryRepository(config)

    def fail_at(stage):
        if stage == failure_stage:
            raise sqlite3.OperationalError("injected migration failure")

    monkeypatch.setattr(repository, "_migration_checkpoint", fail_at)

    with pytest.raises(sqlite3.OperationalError):
        repository.initialize("2026-07-30T11:00:00.000Z")

    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0] == 0
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert not tables.intersection({
        "visitor_devices",
        "device_snapshots",
        "processed_snapshot_events",
        "reader_state",
        "registry_state",
    })


def test_schema_pragmas_migration_idempotency_and_required_checks(
    tmp_path,
):
    config, service, repository, _, _ = make_stack(tmp_path)
    assert repository.initialize(service.now_iso()) is False
    with repository._connect() as connection:
        assert connection.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0].lower() == "wal"
        assert connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0] == 1
        assert connection.execute(
            "PRAGMA busy_timeout"
        ).fetchone()[0] == 250

    append_event(config.source_log_path, fixture_event())
    reader = VisitorRegistryReader(
        config=config,
        repository=repository,
        service=service,
        telemetry=VisitorRegistryTelemetry(
            telemetry_provider=lambda: CaptureTelemetry()
        ),
    )
    assert reader.scan().complete
    with sqlite3.connect(config.db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE visitor_devices SET snapshot_count = -1"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                UPDATE registry_state
                SET initial_backfill_completed = 1,
                    initial_backfill_completed_at = NULL
                """
            )


def test_global_snapshot_count_audit_is_deferred_from_startup(
    tmp_path,
):
    config, service, repository, reader, _ = make_stack(tmp_path)
    append_event(config.source_log_path, fixture_event())
    assert reader.scan().complete
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(
            "UPDATE visitor_devices SET snapshot_count = 2"
        )

    assert repository.initialize(service.now_iso()) is False
    with pytest.raises(
        RegistrySchemaError,
        match="snapshot_count invariant",
    ):
        repository.run_full_audit()


@pytest.mark.parametrize("previous_state", ["ready", "stopping"])
def test_worker_persists_initializing_while_full_audit_is_pending(
    tmp_path,
    monkeypatch,
    previous_state,
):
    config, service, repository, reader, captured = make_stack(tmp_path)
    repository.set_state(
        previous_state,
        None,
        service.now_iso(),
    )
    audit_started = threading.Event()
    release_audit = threading.Event()

    def blocking_audit():
        audit_started.set()
        release_audit.wait(1)

    monkeypatch.setattr(repository, "run_full_audit", blocking_audit)
    worker = VisitorRegistryWorker(
        repository=repository,
        service=service,
        reader=reader,
        telemetry=VisitorRegistryTelemetry(
            telemetry_provider=lambda: captured
        ),
    )

    assert worker.start() is True
    assert audit_started.wait(0.2)
    status = repository.get_status(True)
    assert status.registry_state == "initializing"
    assert status.state_reason == "full_audit_pending"

    release_audit.set()
    deadline = time.monotonic() + 1
    while (
        repository.get_status(True).registry_state != "ready"
        and time.monotonic() < deadline
    ):
        time.sleep(0.005)
    assert repository.get_status(True).registry_state == "ready"
    worker.stop(0.2, final_scan=False)

    assert repository.get_status(True).registry_state == "stopping"


def test_user_version_one_with_incomplete_schema_is_preserved(
    tmp_path,
):
    config = registry_config(tmp_path)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(
            "CREATE TABLE visitor_devices (device_id INTEGER)"
        )
        connection.execute("PRAGMA user_version=1")
    before = Path(config.db_path).stat().st_size

    with pytest.raises(RegistrySchemaError):
        VisitorRegistryRepository(config).initialize(
            "2026-07-30T11:00:00.000Z"
        )

    assert Path(config.db_path).exists()
    assert Path(config.db_path).stat().st_size == before


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode only")
def test_registry_database_uses_0640_on_posix(tmp_path):
    config, *_ = make_stack(tmp_path)
    assert (os.stat(config.db_path).st_mode & 0o777) == 0o640


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode only")
def test_registry_parent_blocks_other_access_to_database_wal_and_shm(
    tmp_path,
):
    config, *_ = make_stack(tmp_path)
    parent = Path(config.db_path).parent
    connection = sqlite3.connect(config.db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE registry_state SET updated_at = updated_at"
        )
        assert (parent.stat().st_mode & 0o007) == 0
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{config.db_path}{suffix}")
            if path.exists():
                assert parent in path.parents
    finally:
        connection.rollback()
        connection.close()


def test_future_and_partial_schemas_are_preserved_and_rejected(tmp_path):
    data = tmp_path / "data"
    logs = tmp_path / "logs"
    _mkdir_private(data)
    _mkdir_private(logs)
    config = registry_config(tmp_path)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute("PRAGMA user_version=2")
    with pytest.raises(RegistrySchemaError):
        VisitorRegistryRepository(config).initialize(
            "2026-07-30T11:00:00.000Z"
        )
    with sqlite3.connect(config.db_path) as connection:
        connection.execute("PRAGMA user_version=0")
        connection.execute("CREATE TABLE visitor_devices (id TEXT)")
    with pytest.raises(RegistrySchemaError):
        VisitorRegistryRepository(config).initialize(
            "2026-07-30T11:00:00.000Z"
        )


def test_reader_stores_fixture_and_creates_card(tmp_path):
    config, _, repository, reader, telemetry = make_stack(tmp_path)
    append_event(config.source_log_path, fixture_event())
    result = reader.scan()
    assert result.complete
    device = repository.get_device_by_mac("02:11:22:33:44:55")
    assert device["snapshot_count"] == 1
    assert device["last_ssid"] == "Zefer_Parki"
    assert any(
        item["event"] == "visitor_registry_snapshot_stored"
        for item in telemetry.events
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX source types only")
def test_directory_source_candidate_is_ignored_without_scan_failure(
    tmp_path,
):
    config, _, repository, reader, _ = make_stack(tmp_path)
    Path(config.source_log_path).mkdir()

    result = reader.scan()

    assert result.complete
    assert result.reason is None
    assert repository.get_reader_states() == {}


@pytest.mark.skipif(os.name != "posix", reason="POSIX FIFO only")
def test_fifo_source_candidate_does_not_block_and_is_ignored(tmp_path):
    config, _, repository, reader, _ = make_stack(tmp_path)
    os.mkfifo(config.source_log_path)

    started = time.monotonic()
    result = reader.scan()
    elapsed = time.monotonic() - started

    assert elapsed < 0.5
    assert result.complete
    assert result.reason is None
    assert repository.get_reader_states() == {}


@pytest.mark.skipif(
    os.name != "posix" or not hasattr(socket, "AF_UNIX"),
    reason="Unix socket only",
)
def test_unix_socket_source_candidate_is_ignored(tmp_path):
    config, _, repository, reader, _ = make_stack(tmp_path)
    source_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        source_socket.bind(config.source_log_path)
        result = reader.scan()
    finally:
        source_socket.close()

    assert result.complete
    assert result.reason is None
    assert repository.get_reader_states() == {}


@pytest.mark.skipif(os.name != "posix", reason="POSIX device only")
def test_device_source_candidate_is_ignored(tmp_path):
    _, _, repository, reader, _ = make_stack(
        tmp_path,
        visitor_snapshot_log_file="/dev/null",
    )

    result = reader.scan()

    assert result.complete
    assert result.reason is None
    assert repository.get_reader_states() == {}


def test_same_mac_across_ssids_and_sites_is_one_card(tmp_path):
    config, _, repository, reader, _ = make_stack(tmp_path)
    first = event_for(session_id="one", ssid="Welcome", site_id="A")
    second = event_for(
        session_id="two",
        ssid="Zefer_Parki",
        site_id="B",
        authorized_at="2026-07-30T12:00:00.000Z",
        captured_at="2026-07-30T12:00:01.000Z",
    )
    append_event(config.source_log_path, first)
    append_event(config.source_log_path, second)
    assert reader.scan().complete
    device = repository.get_device_by_mac("02:11:22:33:44:55")
    assert device["snapshot_count"] == 2
    assert device["last_ssid"] == "Zefer_Parki"
    assert device["last_site_id"] == "B"


def test_out_of_order_profile_and_current_network_semantics(tmp_path):
    config, _, repository, reader, _ = make_stack(tmp_path)
    newest = event_for(
        session_id="new",
        authorized_at="2026-07-30T13:00:00.000Z",
        captured_at="2026-07-30T13:00:01.000Z",
        hostname=None,
        ssid=None,
        site_id="new-site",
    )
    oldest = event_for(
        session_id="old",
        authorized_at="2026-07-30T10:00:00.000Z",
        captured_at="2026-07-30T10:00:01.000Z",
        hostname="older-hostname",
        ssid="old-ssid",
        site_id="old-site",
    )
    append_event(config.source_log_path, newest)
    append_event(config.source_log_path, oldest)
    assert reader.scan().complete
    device = repository.get_device_by_mac("02:11:22:33:44:55")
    assert device["first_seen_at"] == "2026-07-30T10:00:00.000Z"
    assert device["last_seen_at"] == "2026-07-30T13:00:00.000Z"
    assert device["last_known_hostname"] == "older-hostname"
    assert device["last_ssid"] is None
    assert device["last_site_id"] == "new-site"
    assert device["snapshot_count"] == 2


def test_newer_profile_value_wins_and_whitespace_does_not_erase(tmp_path):
    config, _, repository, reader, _ = make_stack(tmp_path)
    old = event_for(session_id="old", hostname="old-host")
    new = event_for(
        session_id="new",
        authorized_at="2026-07-30T12:00:00.000Z",
        captured_at="2026-07-30T12:00:01.000Z",
        hostname="  ",
    )
    append_event(config.source_log_path, old)
    append_event(config.source_log_path, new)
    assert reader.scan().complete
    device = repository.get_device_by_mac("02:11:22:33:44:55")
    assert device["last_known_hostname"] == "old-host"


def test_whitespace_profile_is_absent_but_preserved_in_client_json(
    tmp_path,
):
    config, _, repository, reader, _ = make_stack(tmp_path)
    append_event(
        config.source_log_path,
        event_for(session_id="whitespace", hostname="\t  "),
    )
    assert reader.scan().complete
    device = repository.get_device_by_mac("02:11:22:33:44:55")
    assert device["last_known_hostname"] is None
    with sqlite3.connect(config.db_path) as connection:
        client_json = connection.execute(
            "SELECT client_json FROM device_snapshots"
        ).fetchone()[0]
    assert json.loads(client_json)["hostname"] == "\t  "


def test_equal_timestamp_current_snapshot_uses_snapshot_id_tiebreak(
    tmp_path,
):
    config, _, repository, reader, _ = make_stack(tmp_path)
    events = [
        event_for(session_id="tie-a"),
        event_for(session_id="tie-b"),
    ]
    for item in events:
        append_event(config.source_log_path, item)
    assert reader.scan().complete
    device = repository.get_device_by_mac("02:11:22:33:44:55")
    assert device["current_snapshot_id"] == max(
        item["snapshot_id"] for item in events
    )


def test_duplicate_and_conflict_do_not_change_history(tmp_path):
    config, _, repository, reader, telemetry = make_stack(tmp_path)
    event = fixture_event()
    append_event(config.source_log_path, event)
    append_event(config.source_log_path, deepcopy(event))
    conflict = deepcopy(event)
    conflict["client"]["hostname"] = "conflicting"
    append_event(config.source_log_path, conflict)
    assert reader.scan().complete
    device = repository.get_device_by_mac("02:11:22:33:44:55")
    assert device["snapshot_count"] == 1
    assert any(
        item["event"] == "visitor_registry_duplicate_ignored"
        for item in telemetry.events
    )
    assert any(
        item["event"] == "visitor_registry_snapshot_id_conflict"
        for item in telemetry.events
    )


def test_line_transaction_rolls_back_all_entities_and_offset(tmp_path):
    config, service, repository, _, _ = make_stack(tmp_path)
    decision = service.decide(fixture_event())
    record = SourceLineRecord(
        "1:transaction",
        config.source_log_path,
        0,
        100,
        100,
        "checkpoint",
        service.now_iso(),
    )
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_snapshot_insert
            BEFORE INSERT ON device_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'synthetic write failure');
            END
            """
        )
    with pytest.raises(sqlite3.IntegrityError):
        repository.apply_source_line(record, decision)
    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM visitor_devices"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM device_snapshots"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM processed_snapshot_events"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM reader_state"
        ).fetchone()[0] == 0
        connection.execute("DROP TRIGGER fail_snapshot_insert")
    assert repository.apply_source_line(
        record,
        decision,
    ).outcome is ApplyOutcome.STORED


def test_locked_database_keeps_offset_for_exact_retry(tmp_path):
    config, service, _, _, _ = make_stack(tmp_path)
    repository = VisitorRegistryRepository(
        config,
        busy_timeout_ms=1,
    )
    decision = service.decide(fixture_event())
    record = SourceLineRecord(
        "1:locked",
        config.source_log_path,
        0,
        100,
        100,
        "checkpoint",
        service.now_iso(),
    )
    blocker = sqlite3.connect(config.db_path)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError):
            repository.apply_source_line(record, decision)
    finally:
        blocker.rollback()
        blocker.close()

    assert repository.get_reader_states() == {}
    assert repository.apply_source_line(
        record,
        decision,
    ).outcome is ApplyOutcome.STORED
    assert repository.get_device_by_mac(
        "02:11:22:33:44:55"
    )["snapshot_count"] == 1


def test_skipped_event_is_final(tmp_path):
    config, service, repository, _, _ = make_stack(tmp_path)
    event = fixture_event()
    event["attempts"] = -1
    decision = service.decide(event)
    record = SourceLineRecord(
        "1:1",
        config.source_log_path,
        0,
        10,
        10,
        "checkpoint",
        service.now_iso(),
    )
    first = repository.apply_source_line(record, decision)
    second = repository.apply_source_line(record, decision)
    assert first.outcome is ApplyOutcome.SKIPPED
    assert second.outcome is ApplyOutcome.DUPLICATE
    assert repository.get_device_by_mac(
        "02:11:22:33:44:55"
    ) is None


def test_conflicting_valid_event_cannot_replace_final_skipped_id(
    tmp_path,
):
    config, service, repository, _, _ = make_stack(tmp_path)
    invalid = fixture_event()
    invalid["attempts"] = -1
    valid = fixture_event()
    record = SourceLineRecord(
        "1:skipped-conflict",
        config.source_log_path,
        0,
        10,
        10,
        "checkpoint",
        service.now_iso(),
    )
    assert repository.apply_source_line(
        record,
        service.decide(invalid),
    ).outcome is ApplyOutcome.SKIPPED

    conflict = repository.apply_source_line(
        record,
        service.decide(valid),
    )

    assert conflict.outcome is ApplyOutcome.CONFLICT
    assert repository.get_device_by_mac(
        "02:11:22:33:44:55"
    ) is None


def test_malformed_and_invalid_utf8_advance_without_processed_rows(
    tmp_path,
):
    config, _, repository, reader, telemetry = make_stack(tmp_path)
    with open(config.source_log_path, "wb") as stream:
        stream.write(b'{"broken":}\n')
        stream.write(b"\xff\xfe\n")
    assert reader.scan().complete
    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM processed_snapshot_events"
        ).fetchone()[0] == 0
        offset = connection.execute(
            "SELECT source_offset FROM reader_state"
        ).fetchone()[0]
    assert offset == Path(config.source_log_path).stat().st_size
    names = {item["event"] for item in telemetry.events}
    assert "visitor_registry_invalid_json_line" in names
    assert "visitor_registry_invalid_utf8_line" in names


def test_oversized_line_is_discarded_and_next_line_is_processed(tmp_path):
    config, _, repository, reader, telemetry = make_stack(
        tmp_path,
        max_line_bytes=4096,
    )
    with open(config.source_log_path, "wb") as stream:
        stream.write(b'{"large":"' + (b"x" * 5000) + b'"}\n')
    append_event(config.source_log_path, fixture_event())
    assert reader.scan().complete
    assert repository.get_device_by_mac(
        "02:11:22:33:44:55"
    )["snapshot_count"] == 1
    assert any(
        item["event"] == "visitor_registry_line_too_large"
        for item in telemetry.events
    )


def test_shutdown_interrupts_oversized_discard_without_advancing_offset(
    tmp_path,
):
    config, _, repository, reader, _ = make_stack(
        tmp_path,
        max_line_bytes=512,
    )
    Path(config.source_log_path).write_bytes(b"x" * 200_000)
    checks = 0

    def should_stop():
        nonlocal checks
        checks += 1
        return checks >= 4

    result = reader.scan(should_stop=should_stop)

    assert not result.complete
    assert result.reason == "shutdown"
    assert repository.get_reader_states() == {}


def test_final_scan_deadline_preserves_offset_for_restart(
    tmp_path,
    monkeypatch,
):
    config, service, repository, reader, captured = make_stack(tmp_path)
    append_event(config.source_log_path, fixture_event())
    line_read_started = threading.Event()
    original_read = registry_reader_module._read_bounded_line

    def wait_for_deadline(
        stream,
        max_line_bytes,
        *,
        should_stop=None,
    ):
        line_read_started.set()
        while should_stop is None or not should_stop():
            time.sleep(0.001)
        return registry_reader_module._LineRead(
            data=None,
            offset_end=stream.tell(),
            has_newline=False,
            oversized=False,
            eof_without_data=False,
            interrupted=True,
        )

    monkeypatch.setattr(
        registry_reader_module,
        "_read_bounded_line",
        wait_for_deadline,
    )
    worker = VisitorRegistryWorker(
        repository=repository,
        service=service,
        reader=reader,
        telemetry=VisitorRegistryTelemetry(
            telemetry_provider=lambda: captured
        ),
    )
    repository.mark_backfill_completed(service.now_iso())
    worker._full_audit_completed = True

    started = time.monotonic()
    worker.stop(0.05, final_scan=True)
    elapsed = time.monotonic() - started

    assert line_read_started.is_set()
    assert elapsed < 0.2
    assert worker._stop_completed is True
    assert repository.get_reader_states() == {}
    names = [item["event"] for item in captured.events]
    assert names.count("visitor_registry_shutdown_timeout") == 1
    assert names.count("visitor_registry_stopped") == 1

    worker.stop(0.05, final_scan=True)
    names = [item["event"] for item in captured.events]
    assert names.count("visitor_registry_shutdown_timeout") == 1
    assert names.count("visitor_registry_stopped") == 1

    monkeypatch.setattr(
        registry_reader_module,
        "_read_bounded_line",
        original_read,
    )
    assert reader.scan().complete
    assert repository.get_device_by_mac(
        "02:11:22:33:44:55"
    )["snapshot_count"] == 1
    state = next(iter(repository.get_reader_states().values()))
    assert state.source_offset == Path(
        config.source_log_path
    ).stat().st_size


def test_partial_line_waits_for_newline_without_degrading(tmp_path):
    config, _, repository, reader, _ = make_stack(tmp_path)
    append_event(config.source_log_path, fixture_event(), newline=False)
    first = reader.scan()
    assert first.complete
    assert first.pending_partial_line
    assert repository.get_device_by_mac(
        "02:11:22:33:44:55"
    ) is None
    with open(config.source_log_path, "ab") as stream:
        stream.write(b"\n")
    assert reader.scan().complete
    assert repository.get_device_by_mac(
        "02:11:22:33:44:55"
    )["snapshot_count"] == 1


def test_checkpoint_detects_same_inode_truncate_and_regrow(tmp_path):
    config, _, repository, reader, telemetry = make_stack(tmp_path)
    initial = event_for(session_id="initial")
    append_event(config.source_log_path, initial)
    assert reader.scan().complete
    old_offset = Path(config.source_log_path).stat().st_size

    new_events = [
        event_for(
            session_id=f"replacement-{index}",
            authorized_at=f"2026-07-30T1{index}:00:00.000Z",
            captured_at=f"2026-07-30T1{index}:00:01.000Z",
        )
        for index in (2, 3)
    ]
    with open(config.source_log_path, "wb") as stream:
        for item in new_events:
            stream.write(
                json.dumps(item, separators=(",", ":")).encode()
                + b"\n"
            )
    assert Path(config.source_log_path).stat().st_size > old_offset
    assert reader.scan().complete
    device = repository.get_device_by_mac("02:11:22:33:44:55")
    assert device["snapshot_count"] == 3
    assert any(
        item["event"] == "visitor_registry_source_restarted"
        for item in telemetry.events
    )


def test_retired_identity_seen_as_active_restarts_at_zero(tmp_path):
    config, service, repository, reader, telemetry = make_stack(tmp_path)
    append_event(config.source_log_path, event_for(session_id="first"))
    assert reader.scan().complete
    path = Path(config.source_log_path)
    identity = source_identity(path.stat())
    state = repository.get_reader_states()[identity]
    with path.open("rb") as stream:
        checkpoint = source_checkpoint(stream, state.source_offset)
    repository.observe_source(
        source_identity=identity,
        source_path=str(path),
        source_offset=state.source_offset,
        last_observed_size=path.stat().st_size,
        source_checkpoint=checkpoint,
        retired_completed=True,
        missing_warning_emitted=False,
        now_utc=service.now_iso(),
    )
    append_event(config.source_log_path, event_for(session_id="second"))
    assert reader.scan().complete
    device = repository.get_device_by_mac("02:11:22:33:44:55")
    assert device["snapshot_count"] == 2
    assert any(
        item["event"] == "visitor_registry_source_reused"
        for item in telemetry.events
    )


def test_temporarily_missing_inode_resumes_after_checkpoint_match(tmp_path):
    config, _, repository, reader, telemetry = make_stack(tmp_path)
    append_event(config.source_log_path, event_for(session_id="first"))
    assert reader.scan().complete
    active = Path(config.source_log_path)
    hidden = tmp_path / "temporarily-hidden"
    active.rename(hidden)
    missing = reader.scan()
    assert not missing.complete
    append_event(str(hidden), event_for(session_id="second"))
    hidden.rename(active)
    assert reader.scan().complete
    device = repository.get_device_by_mac("02:11:22:33:44:55")
    assert device["snapshot_count"] == 2
    assert len([
        item
        for item in telemetry.events
        if item["event"] == "visitor_registry_old_inode_missing"
    ]) == 1


def test_same_inode_under_rotation_alias_and_active_is_processed_once(
    tmp_path,
):
    config, _, repository, reader, _ = make_stack(tmp_path)
    active = Path(config.source_log_path)
    append_event(str(active), fixture_event())
    rotated = Path(f"{config.source_log_path}.1")
    os.link(active, rotated)

    assert reader.scan().complete

    device = repository.get_device_by_mac("02:11:22:33:44:55")
    assert device["snapshot_count"] == 1
    states = repository.get_reader_states()
    assert len(states) == 1
    state = next(iter(states.values()))
    assert Path(state.source_path) == active
    assert state.retired_completed is False


def test_rotations_are_processed_from_oldest_to_active(tmp_path):
    config, _, _, reader, _ = make_stack(tmp_path)
    paths = [
        Path(f"{config.source_log_path}.2"),
        Path(f"{config.source_log_path}.1"),
        Path(config.source_log_path),
    ]
    for index, path in enumerate(paths):
        append_event(
            str(path),
            event_for(session_id=f"rotation-{index}"),
        )

    assert reader.scan().complete

    with sqlite3.connect(config.db_path) as connection:
        observed = [
            Path(row[0])
            for row in connection.execute(
                """
                SELECT source_path
                FROM processed_snapshot_events
                ORDER BY rowid
                """
            )
        ]
    assert observed == paths


def test_completed_rotated_inode_state_is_removed_after_file_disappears(
    tmp_path,
):
    config, _, repository, reader, _ = make_stack(tmp_path)
    rotated = Path(f"{config.source_log_path}.1")
    append_event(str(rotated), fixture_event())
    assert reader.scan().complete
    identity = source_identity(rotated.stat())
    assert repository.get_reader_states()[identity].retired_completed

    rotated.unlink()
    assert reader.scan().complete
    assert identity not in repository.get_reader_states()


def test_partial_rotated_file_is_never_marked_completed(tmp_path):
    config, _, repository, reader, _ = make_stack(tmp_path)
    rotated = Path(f"{config.source_log_path}.1")
    append_event(str(rotated), fixture_event(), newline=False)

    result = reader.scan()

    assert result.complete
    assert result.pending_partial_line
    state = repository.get_reader_states()[
        source_identity(rotated.stat())
    ]
    assert state.source_offset == 0
    assert state.retired_completed is False


def test_checkpoint_is_stable_and_includes_offset(tmp_path):
    path = tmp_path / "source"
    path.write_bytes(b"abc\ndef\n")
    with path.open("rb") as stream:
        zero = source_checkpoint(stream, 0)
        first = source_checkpoint(stream, 4)
        repeated = source_checkpoint(stream, 4)
    assert zero != first
    assert first == repeated


def test_read_only_cli_lists_cards_and_never_exposes_raw_json(
    tmp_path,
    monkeypatch,
    capsys,
):
    config, _, repository, reader, _ = make_stack(tmp_path)
    append_event(config.source_log_path, fixture_event())
    assert reader.scan().complete
    repository.mark_backfill_completed("2026-07-30T11:01:00.000Z")
    monkeypatch.setattr(
        registry_cli,
        "get_settings",
        lambda: settings(tmp_path),
    )

    assert registry_cli.main(["status", "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["configured_enabled"] is True
    assert status["available"] is True
    assert status["database_exists"] is True
    assert status["database_ready"] is True
    assert status["db_path"] == config.db_path
    assert status["source_log_path"] == config.source_log_path
    assert status["missing_inode_warning_count"] == 0

    assert registry_cli.main(["list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert len(listed["devices"]) == 1
    device_id = listed["devices"][0]["device_id"]

    assert registry_cli.main([
        "show",
        "--device-id",
        device_id,
        "--json",
    ]) == 0
    shown_text = capsys.readouterr().out
    shown = json.loads(shown_text)
    assert shown["device"]["mac"] == "02:11:22:33:44:55"
    assert shown["device"]["last_active"] is True
    assert shown["recent_snapshots"][0]["active"] is True
    assert shown["partial"] is False
    assert "raw_controller_snapshot" not in shown_text
    assert "client_json" not in shown_text
    assert "auth_context_json" not in shown_text


def test_cli_stats_use_authorized_at_local_day_and_report_partial(
    tmp_path,
    monkeypatch,
    capsys,
):
    config, _, _, reader, _ = make_stack(tmp_path)
    append_event(
        config.source_log_path,
        event_for(
            session_id="stats-session",
            authorized_at="2026-07-29T20:00:00.000Z",
        ),
    )
    assert reader.scan().complete
    monkeypatch.setattr(
        registry_cli,
        "get_settings",
        lambda: settings(tmp_path),
    )

    assert registry_cli.main([
        "stats",
        "--date",
        "2026-07-30",
        "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["local_date"] == "2026-07-30"
    assert payload["new_devices"] == 1
    assert payload["authorized_devices"] == 1
    assert payload["snapshots"] == 1
    assert payload["partial"] is True


def test_cli_stats_keep_portal_timezone_when_registry_is_disabled(
    tmp_path,
    monkeypatch,
    capsys,
):
    config, _, _, reader, _ = make_stack(tmp_path)
    append_event(
        config.source_log_path,
        event_for(
            session_id="disabled-stats-session",
            authorized_at="2026-07-29T20:00:00.000Z",
        ),
    )
    assert reader.scan().complete
    disabled_settings = settings(
        tmp_path,
        visitor_registry_enabled="false",
        portal_counter_timezone="Asia/Baku",
    )
    monkeypatch.setattr(
        registry_cli,
        "get_settings",
        lambda: disabled_settings,
    )

    assert registry_cli.main([
        "stats",
        "--date",
        "2026-07-30",
        "--json",
    ]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["timezone"] == "Asia/Baku"
    assert payload["snapshots"] == 1


@pytest.mark.parametrize(
    "arguments",
    [
        ["--mac", "02-11-22-33-44-55"],
        ["--hostname", "FIXTURE-AND"],
        ["--ip", "192.0.2.27"],
        ["--ssid", "Zefer_Parki"],
        ["--ap-mac", "02-aa-bb-cc-dd-ee"],
        ["--device-type", "ANDROID"],
        ["--controller-client-id", "prod-anon-client-001"],
        ["--seen-from", "2026-07-30T14:59:59+04:00"],
        ["--seen-to", "2026-07-30T15:00:01+04:00"],
    ],
)
def test_cli_card_filters_use_current_fields(
    tmp_path,
    monkeypatch,
    capsys,
    arguments,
):
    config, _, _, reader, _ = make_stack(tmp_path)
    append_event(config.source_log_path, fixture_event())
    assert reader.scan().complete
    monkeypatch.setattr(
        registry_cli,
        "get_settings",
        lambda: settings(tmp_path),
    )

    assert registry_cli.main([
        "list",
        *arguments,
        "--json",
    ]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert len(payload["devices"]) == 1


def test_hostname_filter_treats_sql_wildcards_as_literal(
    tmp_path,
    monkeypatch,
    capsys,
):
    config, _, _, reader, _ = make_stack(tmp_path)
    append_event(config.source_log_path, fixture_event())
    assert reader.scan().complete
    monkeypatch.setattr(
        registry_cli,
        "get_settings",
        lambda: settings(tmp_path),
    )

    assert registry_cli.main([
        "list",
        "--hostname",
        "%",
        "--json",
    ]) == 0

    assert json.loads(capsys.readouterr().out)["devices"] == []


def test_cli_missing_database_status_and_bad_arguments(
    tmp_path,
    monkeypatch,
    capsys,
):
    data = tmp_path / "data"
    logs = tmp_path / "logs"
    _mkdir_private(data)
    _mkdir_private(logs)
    monkeypatch.setattr(
        registry_cli,
        "get_settings",
        lambda: settings(tmp_path),
    )
    assert registry_cli.main(["status", "--json"]) == 0
    missing = json.loads(capsys.readouterr().out)
    assert missing["available"] is False
    assert missing["database_exists"] is False
    assert missing["db_path"] == str(
        data / "visitor_registry.sqlite3"
    )
    assert missing["source_log_path"] == str(
        logs / "visitor_snapshots.log"
    )
    assert missing["missing_inode_warning_count"] == 0
    assert missing["partial"] is True
    assert not (data / "visitor_registry.sqlite3").exists()

    assert registry_cli.main([
        "list",
        "--unknown-option",
        "--json",
    ]) == 2
    argument_error = json.loads(capsys.readouterr().out)
    assert argument_error["exit_code"] == 2

    config, _, _, reader, _ = make_stack(tmp_path)
    append_event(config.source_log_path, fixture_event())
    assert reader.scan().complete
    assert registry_cli.main([
        "list",
        "--limit",
        "0",
        "--json",
    ]) == 2
    invalid = json.loads(capsys.readouterr().out)
    assert invalid["exit_code"] == 2


def test_cli_status_rejects_database_directory_as_runtime_error(
    tmp_path,
    monkeypatch,
    capsys,
):
    database = tmp_path / "database-directory"
    _mkdir_private(database)
    configured = settings(
        tmp_path,
        visitor_registry_db_path=str(database),
    )
    config = registry_config_from_settings(configured)
    repository = VisitorRegistryRepository(config)

    with pytest.raises(RegistryConfigError, match="regular file"):
        repository.get_status(True)

    monkeypatch.setattr(
        registry_cli,
        "get_settings",
        lambda: configured,
    )
    assert registry_cli.main(["status", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["exit_code"] == 1
    assert "regular file" in payload["error"]
    assert "database_absent" not in payload["error"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX FIFO only")
def test_cli_status_rejects_fifo_without_blocking(
    tmp_path,
    monkeypatch,
    capsys,
):
    data = tmp_path / "data"
    _mkdir_private(data)
    database = data / "visitor_registry.sqlite3"
    os.mkfifo(database)
    monkeypatch.setattr(
        registry_cli,
        "get_settings",
        lambda: settings(
            tmp_path,
            visitor_registry_db_path=str(database),
        ),
    )

    started = time.monotonic()
    assert registry_cli.main(["status", "--json"]) == 1
    elapsed = time.monotonic() - started

    payload = json.loads(capsys.readouterr().out)
    assert elapsed < 0.5
    assert payload["exit_code"] == 1
    assert "regular file" in payload["error"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink only")
@pytest.mark.parametrize("target_kind", ["dangling", "directory"])
def test_cli_status_rejects_database_symlink(
    tmp_path,
    monkeypatch,
    capsys,
    target_kind,
):
    data = tmp_path / "data"
    _mkdir_private(data)
    database = data / "visitor_registry.sqlite3"
    target = tmp_path / "symlink-target"
    if target_kind == "directory":
        _mkdir_private(target)
    database.symlink_to(
        target,
        target_is_directory=target_kind == "directory",
    )
    monkeypatch.setattr(
        registry_cli,
        "get_settings",
        lambda: settings(
            tmp_path,
            visitor_registry_db_path=str(database),
        ),
    )

    assert registry_cli.main(["status", "--json"]) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["exit_code"] == 1
    assert "symlink" in payload["error"]


def test_cli_status_works_when_disabled_unused_settings_are_invalid(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        registry_cli,
        "get_settings",
        lambda: {
            "visitor_registry_enabled": "false",
            "visitor_registry_db_path": "",
            "visitor_snapshot_log_file": "",
            "portal_counter_timezone": "invalid",
        },
    )

    assert registry_cli.main(["status", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["configured_enabled"] is False
    assert payload["database_exists"] is False
    assert payload["registry_state"] == "disabled"
