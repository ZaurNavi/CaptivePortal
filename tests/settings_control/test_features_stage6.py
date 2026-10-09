"""Stage-6 preferences, graph and shared validation boundaries (disposable only)."""
import json
import logging
import uuid
from types import SimpleNamespace

import pytest

from app.admin_web.models import AdminPrincipal
from app.settings_control.bootstrap import bootstrap_settings_control
from app.settings_control.definitions import SettingsDefinitionRegistry
from app.settings_control.features import AdminFeaturePlanV1
from app.settings_control.models import ResolvedSettingsSnapshot, SettingsError
from app.settings_control.resolver import resolve_settings
from tests.admin_web.conftest import enabled_settings, SITE_ID
from . import CONTROLLER_BASE


def plan(values, generation=None):
    return AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(generation, values, {}, {}, {}))


def adopt(boot):
    runtime = SimpleNamespace(feature_plan=boot.feature_plan)
    analytics = SimpleNamespace(feature_plan=boot.feature_plan, historical_source_mode="base")
    boot.activation_service.adopt(boot.runtime_settings, runtime, analytics, feature_plan=boot.feature_plan)


def mutate(boot, changes, domain="features", generation=None, key=None):
    return boot.admin_context.mutation_service.mutate(json.dumps({"changes": changes}),
        principal=AdminPrincipal("operator"), source_ip="127.0.0.1", request_id=str(uuid.uuid4()),
        idempotency_key=key or str(uuid.uuid4()),
        expected_generation=boot.admin_context.read_service.repository.configured()[0] if generation is None else generation,
        domain=domain)


def bootstrap(tmp_path, **values):
    base = {**CONTROLLER_BASE, "web_admin_settings_enabled": "true", "settings_db_path": str(tmp_path / "settings.sqlite3"), **values}
    return bootstrap_settings_control(base_settings=base, explicit_environment_names=set(), logger=logging.getLogger("features-test"))


def test_registry_exact_metadata_and_scope():
    registry = SettingsDefinitionRegistry()
    assert [len(registry.for_domain(domain)) for domain in ("general", "controller", "portal", "features")] == [12, 3, 14, 17]
    assert len(tuple(registry)) == 46
    assert [item.feature_id for item in registry.for_domain("features")] == [
        "home.live", "home.traffic", "home.activity", "home.health", "traffic.root", "traffic.history",
        "traffic.statistics", "traffic.peak", "traffic.by_ap", "traffic.independent_ranges", "traffic.ap_share",
        "traffic.online_guests", "traffic.completed_sessions", "traffic.evidence", "traffic.projection_read",
        "devices.list_context", "devices.current_context"]
    for item in registry.for_domain("features"):
        assert item.repository_default_value == "false"
        assert item.value_type == "string" and item.public_value_type == "boolean"
        assert item.presentation_type == "boolean_toggle"
        assert item.scope_type == "global" and item.secret_class == "normal" and item.editable
        assert item.settings_dict_key == item.key.lower() and item.environment_variable_name == item.key
        assert item.apply_requirement == "main_service_restart" and item.activation_target == "captive-portal.service"
    assert registry.get("WEB_ADMIN_HOME_AP_24H_ENABLED") is None
    assert registry.get("TRAFFIC_PROJECTION_ENABLED") is None


@pytest.mark.parametrize("child,parent", [
    ("home.traffic", "HOME_LIVE"), ("home.activity", "HOME_LIVE"),
    ("traffic.history", "TRAFFIC"), ("traffic.statistics", "TRAFFIC_HISTORY"),
    ("traffic.peak", "TRAFFIC_STATISTICS"), ("traffic.by_ap", "TRAFFIC_HISTORY"),
    ("traffic.independent_ranges", "TRAFFIC_HISTORY"), ("traffic.ap_share", "TRAFFIC_INDEPENDENT_RANGES"),
    ("traffic.projection_read", "TRAFFIC_HISTORY"), ("traffic.online_guests", "TRAFFIC"),
    ("traffic.completed_sessions", "TRAFFIC"), ("traffic.evidence", "TRAFFIC"),
])
def test_parent_false_child_true_preserved(child, parent):
    registry = SettingsDefinitionRegistry()
    values = {item.settings_dict_key: "true" for item in registry.for_domain("features")}
    values["web_admin_" + parent.lower() + "_enabled"] = "false"
    result = plan(values)
    assert result.configured_state(child) == "dormant_parent_disabled"
    assert result.blocked_by[child] == ("WEB_ADMIN_" + parent + "_ENABLED",)
    values["web_admin_" + parent.lower() + "_enabled"] = "true"
    assert plan(values).enabled(child)


def test_blocking_ancestors_order_and_immutable_snapshot():
    result = plan({"web_admin_traffic_peak_enabled": "true"}, 7)
    assert result.blocked_by["traffic.peak"] == ("WEB_ADMIN_TRAFFIC_ENABLED", "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED", "WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED")
    assert result.generation_id == 7
    with pytest.raises(TypeError):
        result.configured_values["WEB_ADMIN_TRAFFIC_ENABLED"] = True


@pytest.mark.parametrize("bad", [True, 1, None, "TRUE", " true", "false ", "1"])
def test_invalid_base_never_hidden_by_override(bad):
    with pytest.raises(SettingsError, match="validation_failed"):
        resolve_settings({**CONTROLLER_BASE, "web_admin_traffic_enabled": bad}, set(), {"WEB_ADMIN_TRAFFIC_ENABLED": "true"}, 1)


def test_sources_and_clear_override_and_no_cascade(tmp_path):
    base = {**CONTROLLER_BASE, "web_admin_traffic_history_enabled": "true", "web_admin_traffic_enabled": "true"}
    snapshot = resolve_settings(base, {"WEB_ADMIN_TRAFFIC_HISTORY_ENABLED"}, {}, 0)
    assert snapshot.base_source_by_key["WEB_ADMIN_TRAFFIC_HISTORY_ENABLED"] == "environment"
    boot = bootstrap(tmp_path)
    adopt(boot)
    mutate(boot, [{"key": "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED", "operation": "set", "value": True}])
    mutate(boot, [{"key": "WEB_ADMIN_TRAFFIC_ENABLED", "operation": "set", "value": False}])
    repo = boot.admin_context.read_service.repository
    with repo.transaction() as db:
        assert repo.overrides(db, 2) == {"WEB_ADMIN_TRAFFIC_HISTORY_ENABLED": "true", "WEB_ADMIN_TRAFFIC_ENABLED": "false"}
        assert [row[0] for row in db.execute("SELECT setting_key FROM settings_mutation_audit WHERE generation_id=2")] == ["WEB_ADMIN_TRAFFIC_ENABLED"]
    rows = boot.admin_context.read_service.read_features()["features"]
    history = next(row for row in rows if row["feature_id"] == "traffic.history")
    assert history["configured_feature_state"] == "dormant_parent_disabled"
    assert history["effective_value"] is False and history["pending_value"] is True
    assert history["configured_source"] == "persisted_override"
    result = mutate(boot, [{"key": "WEB_ADMIN_TRAFFIC_ENABLED", "operation": "clear_override"}])
    assert result.body["changed_keys"] == ["WEB_ADMIN_TRAFFIC_ENABLED"]
    assert result.body["resource"] == {"type": "admin_product_features", "scope": "installation"}
    assert "settings" not in result.body and "features" not in result.body


def test_secret_isolation_noop_replay_and_common_cas(tmp_path, monkeypatch):
    boot = bootstrap(tmp_path)
    adopt(boot)
    service = boot.admin_context.mutation_service
    monkeypatch.setattr(service.secret_repository, "resolve", lambda *_: pytest.fail("secret resolve"))
    key = str(uuid.uuid4())
    changes = [{"key": "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED", "operation": "clear_override"}]
    original = mutate(boot, changes, generation=0, key=key)
    assert original.status == 200 and original.body["changed"] is False
    mutate(boot, [{"key": "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED", "operation": "set", "value": True}])
    replay = mutate(boot, changes, generation=0, key=key)
    assert replay == original
    with pytest.raises(SettingsError, match="idempotency_conflict"):
        mutate(boot, [{"key": "WEB_ADMIN_TRAFFIC_ENABLED", "operation": "set", "value": False}], key=key)
    with pytest.raises(SettingsError, match="stale_generation"):
        mutate(boot, changes, generation=0)
    model = boot.admin_context.read_service.read_features()
    assert len(model["features"]) == 17
    assert model["pending_setting_count"] == 1


@pytest.mark.parametrize("domain", ["startup", "general", "controller", "portal", "features"])
@pytest.mark.parametrize("admin,child,parent,valid,expected", [
    (False, True, True, True, True),  # A
    (False, True, True, False, True), # B
    (False, False, True, False, True),# C
    (True, False, True, False, True), # D
    (True, True, False, False, True), # E
    (True, True, True, True, True),   # F
    (True, True, True, False, False), # G
])
def test_outer_admin_matrix_all_candidate_paths(tmp_path, domain, admin, child, parent, valid, expected):
    values = enabled_settings(web_admin_enabled="true" if admin else "false",
        web_admin_home_live_enabled="true" if parent else "false",
        web_admin_home_activity_enabled="true" if child else "false",
        web_admin_home_activity_site_context_json=json.dumps({SITE_ID: {"timezone": "UTC", "visits_coverage_from_utc": None, "traffic_coverage_from_utc": None}}) if valid else "broken",
        current_state_enabled="true", current_state_site_ids=SITE_ID, current_state_client_ssids_json='["Guest"]')
    if domain == "startup":
        if expected:
            bootstrap(tmp_path, **values)
        else:
            with pytest.raises(SettingsError, match="validation_failed"):
                bootstrap(tmp_path, **values)
        return
    boot = bootstrap(tmp_path)
    boot.admin_context.read_service.base_settings = {**CONTROLLER_BASE, **values}
    changes = {"general": [{"key": "WEB_ADMIN_DEVICE_PAGE_SIZE", "operation": "set", "value": 120}],
        "controller": [{"key": "OMADA_ID", "operation": "set", "value": "new-installation"}],
        "portal": [{"key": "PORTAL_UI_TITLE_EN", "operation": "set", "value": "Guest"}],
        "features": [{"key": "WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED", "operation": "set", "value": True}]}[domain]
    if expected:
        assert mutate(boot, changes, domain).status == 201
    else:
        with pytest.raises(SettingsError, match="validation_failed"):
            mutate(boot, changes, domain)


def test_later_outer_gate_enable_rejects_bad_retained_preference(tmp_path):
    values = dict(web_admin_enabled="false", web_admin_home_health_enabled="true", web_admin_home_health_request_timeout_seconds="bad")
    boot = bootstrap(tmp_path, **values)
    assert boot.feature_plan.enabled("home.health")
    with pytest.raises(SettingsError, match="validation_failed"):
        bootstrap(tmp_path, **{**values, **enabled_settings(), "web_admin_enabled": "true"})
    assert boot.admin_context.read_service.repository.configured() == (0, {})


@pytest.mark.parametrize("changes", [
    [{"key": "WEB_ADMIN_TRAFFIC_ENABLED", "operation": "set", "value": "true"}],
    [{"key": "WEB_ADMIN_TRAFFIC_ENABLED", "operation": "set", "value": 1}],
    [{"key": "WEB_ADMIN_ENABLED", "operation": "set", "value": True}],
    [{"key": "WEB_ADMIN_TRAFFIC_ENABLED", "operation": "clear_override", "value": False}],
    [{"key": "WEB_ADMIN_TRAFFIC_ENABLED", "operation": "set", "value": True}] * 2,
])
def test_feature_mutation_closed_boolean_shape(changes):
    from app.settings_control.services import parse_changes
    with pytest.raises(SettingsError, match="invalid_request"):
        parse_changes(json.dumps({"changes": changes}), domain="features")


@pytest.mark.parametrize("mismatch", ["submitted", "admin", "analytics", "generation"])
def test_adoption_fails_closed_on_plan_identity_mismatch(tmp_path, mismatch):
    from dataclasses import replace
    boot = bootstrap(tmp_path)
    other = plan(dict(boot.runtime_settings), boot.resolved_snapshot.generation_id)
    supplied = replace(boot.feature_plan, generation_id=99) if mismatch == "generation" else other if mismatch == "submitted" else boot.feature_plan
    admin = SimpleNamespace(feature_plan=other if mismatch == "admin" else boot.feature_plan)
    analytics = SimpleNamespace(feature_plan=other if mismatch == "analytics" else boot.feature_plan, historical_source_mode="base")
    with pytest.raises(SettingsError, match="settings_activation_failed"):
        boot.activation_service.adopt(boot.runtime_settings, admin, analytics, feature_plan=supplied)
    with boot.admin_context.read_service.repository.transaction() as db:
        assert boot.admin_context.read_service.repository.effective(db) is None
        assert db.execute("SELECT safe_error_code FROM settings_activation_events ORDER BY event_id DESC LIMIT 1").fetchone()[0] == "features_configuration_adoption_failed"


@pytest.mark.parametrize("values", [
    {"web_admin_home_activity_enabled": "true", "current_state_enabled": "false"},
    {"web_admin_home_activity_enabled": "true", "current_state_site_ids": ""},
    {"web_admin_device_list_context_enabled": "true", "web_admin_device_list_context_cursor_secret": "bad"},
    {"web_admin_home_health_enabled": "true", "web_admin_home_health_request_timeout_seconds": 10},
    {"web_admin_traffic_enabled": "true", "web_admin_traffic_request_timeout_seconds": 10},
    {"web_admin_traffic_enabled": "true", "web_admin_traffic_history_enabled": "true",
     "web_admin_traffic_projection_read_enabled": "true", "traffic_projection_db_path": "relative"},
])
def test_graph_enabled_supporting_prerequisite_failures_are_safe(tmp_path, values):
    settings = enabled_settings(web_admin_home_live_enabled="true", current_state_enabled="true",
        current_state_site_ids=SITE_ID, current_state_client_ssids_json='["Guest"]',
        web_admin_home_activity_site_context_json=json.dumps({SITE_ID: {"timezone": "UTC",
            "visits_coverage_from_utc": None, "traffic_coverage_from_utc": None}}))
    with pytest.raises(SettingsError, match="validation_failed") as error:
        bootstrap(tmp_path, **{**settings, **values})
    assert error.value.status == 422
    assert all(detail["reason"] == "configuration_prerequisite_invalid" for detail in error.value.details)


def test_optional_sources_outage_is_not_adoption_failure(tmp_path):
    from app.admin_web import create_admin_web_runtime
    values = enabled_settings(web_admin_home_live_enabled="true", web_admin_home_activity_enabled="true",
        web_admin_home_health_enabled="true", current_state_enabled="true",
        current_state_site_ids=SITE_ID, current_state_client_ssids_json='["Guest"]',
        web_admin_home_activity_site_context_json=json.dumps({SITE_ID: {"timezone": "UTC",
            "visits_coverage_from_utc": None, "traffic_coverage_from_utc": None}}))
    boot = bootstrap(tmp_path, **values)
    runtime = create_admin_web_runtime(boot.runtime_settings, None, None, None, None,
        logging.getLogger("outage"), feature_plan=boot.feature_plan, settings_control=boot.admin_context)
    assert runtime.query_service is None
    assert runtime.home_activity_config.enabled and runtime.home_health_config.enabled
    boot.activation_service.adopt(boot.runtime_settings, runtime,
        SimpleNamespace(feature_plan=boot.feature_plan, historical_source_mode="base"),
        feature_plan=boot.feature_plan)
    assert boot.admin_context.read_service._adopted


def test_general_consumer_and_other_domain_pending_semantics(tmp_path):
    boot = bootstrap(tmp_path, **enabled_settings(web_admin_home_traffic_enabled="true"))
    from app.admin_web import create_admin_web_runtime
    runtime = create_admin_web_runtime(boot.runtime_settings, None, None, None, None,
        logging.getLogger("consumers"), feature_plan=boot.feature_plan, settings_control=boot.admin_context)
    boot.activation_service.adopt(boot.runtime_settings, runtime,
        SimpleNamespace(feature_plan=boot.feature_plan, historical_source_mode="base"), feature_plan=boot.feature_plan)
    model = boot.admin_context.read_service.read()
    for key in ("WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS", "WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE",
        "WEB_ADMIN_CURRENT_STATE_PAGE_SIZE", "WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS", "WEB_ADMIN_TRAFFIC_REFRESH_SECONDS",
        "WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS", "WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS"):
        row = next(row for row in model["settings"] if row["key"] == key)
        assert row["consumer_state"] == "consumer_disabled" and row["effective_value"] is None
    mutate(boot, [{"key": "PORTAL_UI_TITLE_EN", "operation": "set", "value": "Changed"}], "portal")
    features = boot.admin_context.read_service.read_features()
    assert features["restart_required"] and features["pending_setting_count"] == 0


@pytest.mark.parametrize("domain", ["startup", "general", "controller", "portal", "features"])
def test_later_enabled_admin_revalidates_retained_preferences_all_paths(tmp_path, domain):
    values = enabled_settings(web_admin_enabled="false", web_admin_home_health_request_timeout_seconds="bad")
    boot = bootstrap(tmp_path, **values)
    mutate(boot, [{"key": "WEB_ADMIN_HOME_HEALTH_ENABLED", "operation": "set", "value": True}])
    repository = boot.admin_context.read_service.repository
    before = repository.configured()
    enabled = {**values, "web_admin_enabled": "true"}
    with pytest.raises(SettingsError, match="validation_failed"):
        if domain == "startup":
            bootstrap(tmp_path, **enabled)
        else:
            boot.admin_context.read_service.base_settings = {**CONTROLLER_BASE, **enabled}
            changes = {
                "general": [{"key": "WEB_ADMIN_DEVICE_PAGE_SIZE", "operation": "set", "value": 120}],
                "controller": [{"key": "OMADA_ID", "operation": "set", "value": "other"}],
                "portal": [{"key": "PORTAL_UI_TITLE_EN", "operation": "set", "value": "Guest changed"}],
                "features": [{"key": "WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED", "operation": "set", "value": True}],
            }[domain]
            mutate(boot, changes, domain)
    assert repository.configured() == before
    with repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM settings_generations").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM settings_mutation_audit").fetchone()[0] == 1


@pytest.mark.parametrize("damage", ["wrong_mode", "list_config", "list_codec", "activity_config", "health_config"])
def test_graph_enabled_structural_adoption_checks(tmp_path, damage):
    from app.admin_web import create_admin_web_runtime
    values = enabled_settings(web_admin_home_live_enabled="true", web_admin_home_activity_enabled="true",
        web_admin_home_health_enabled="true", web_admin_device_list_context_enabled="true",
        web_admin_device_list_context_cursor_secret="ab" * 32, current_state_enabled="true",
        current_state_site_ids=SITE_ID, current_state_client_ssids_json='["Guest"]',
        web_admin_home_activity_site_context_json=json.dumps({SITE_ID: {"timezone": "UTC",
            "visits_coverage_from_utc": None, "traffic_coverage_from_utc": None}}))
    boot = bootstrap(tmp_path, **values)
    runtime = create_admin_web_runtime(boot.runtime_settings, None, None, None, None,
        logging.getLogger("structural"), feature_plan=boot.feature_plan, settings_control=boot.admin_context)
    attributes = {"list_config": "device_list_context_config", "list_codec": "device_list_context_cursor_codec",
                  "activity_config": "home_activity_config", "health_config": "home_health_config"}
    if damage in attributes:
        setattr(runtime, attributes[damage], None)
    analytics = SimpleNamespace(feature_plan=boot.feature_plan,
        historical_source_mode="projection" if damage == "wrong_mode" else "base")
    with pytest.raises(SettingsError, match="settings_activation_failed"):
        boot.activation_service.adopt(boot.runtime_settings, runtime, analytics, feature_plan=boot.feature_plan)
    assert not boot.admin_context.read_service._adopted


def test_features_with_retained_managed_secret_need_no_key_or_decryption(tmp_path, monkeypatch):
    from app.settings_control.repository import SettingsRepository
    from app.settings_control.services import SettingsReadService, SettingsMutationService
    from app.settings_control.controller_secret import ControllerSecretRepository, binding
    from .stage4_helpers import DisposableFilesystem
    from .test_schema_v5_features import populated_v4
    path = tmp_path / "settings.sqlite3"
    populated_v4(path)
    repository = SettingsRepository(path)
    generation, overrides = repository.configured()
    base = {key: value for key, value in CONTROLLER_BASE.items() if key != "client_secret"}
    snapshot = resolve_settings(base, set(), overrides, generation)
    selected = AdminFeaturePlanV1.from_snapshot(snapshot)
    read = SettingsReadService(repository, base, set(), snapshot, feature_plan=selected)
    filesystem = DisposableFilesystem()
    filesystem.key_valid = False
    secrets = ControllerSecretRepository(repository, filesystem)
    def forbidden(*_args, **_kwargs):
        pytest.fail("Features touched managed-secret read/key boundary")
    monkeypatch.setattr(secrets, "resolve", forbidden)
    monkeypatch.setattr(secrets, "keys", forbidden)
    monkeypatch.setattr(filesystem, "load_master_key", forbidden)
    monkeypatch.setattr("app.settings_control.controller_secret.decrypt_secret", forbidden)
    service = SettingsMutationService(repository, read)
    service.secret_repository = secrets
    assert len(read.read_features()["features"]) == 17
    result = service.mutate(json.dumps({"changes": [{"key": "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED",
        "operation": "set", "value": True}]}), principal=AdminPrincipal("operator"),
        source_ip="local", request_id="r", idempotency_key=str(uuid.uuid4()),
        expected_generation=generation, domain="features")
    assert result.status == 201
    with repository.transaction() as db:
        assert binding(db, result.body["configured_generation"]) == binding(db, generation)
    assert filesystem.key_reads == 0


@pytest.mark.parametrize("settings_enabled", [False, True])
def test_bootstrap_builds_exactly_one_startup_plan(tmp_path, monkeypatch, settings_enabled):
    original = AdminFeaturePlanV1.from_snapshot.__func__
    built = []
    def counted(cls, snapshot, registry=None):
        result = original(cls, snapshot, registry)
        built.append(result)
        return result
    monkeypatch.setattr(AdminFeaturePlanV1, "from_snapshot", classmethod(counted))
    boot = bootstrap(tmp_path, web_admin_settings_enabled="true" if settings_enabled else "false")
    assert built == [boot.feature_plan]
    assert boot.feature_plan.generation_id == boot.resolved_snapshot.generation_id
    if settings_enabled:
        assert boot.activation_service.feature_plan is boot.feature_plan
        assert boot.admin_context.read_service.feature_plan is boot.feature_plan


@pytest.mark.parametrize("target,parents,broken", [
    ("HOME_ACTIVITY", ("HOME_LIVE",), {"current_state_enabled": "false"}),
    ("HOME_ACTIVITY", ("HOME_LIVE",), {"current_state_site_ids": ""}),
    ("HOME_HEALTH", (), {"web_admin_home_health_request_timeout_seconds": "bad"}),
    ("DEVICE_LIST_CONTEXT", (), {"web_admin_device_list_context_cursor_secret": "bad"}),
    ("TRAFFIC_PROJECTION_READ", ("TRAFFIC", "TRAFFIC_HISTORY"), {"traffic_projection_db_path": "relative"}),
])
def test_features_mutation_rejects_invalid_enabled_prerequisites(tmp_path, monkeypatch, target, parents, broken):
    settings = enabled_settings(current_state_enabled="true", current_state_site_ids=SITE_ID,
        current_state_client_ssids_json='["Guest"]', observation_site_ids=SITE_ID,
        web_admin_home_activity_site_context_json=json.dumps({SITE_ID: {"timezone": "UTC",
            "visits_coverage_from_utc": None, "traffic_coverage_from_utc": None}}))
    boot = bootstrap(tmp_path, **{**settings, **broken})
    service = boot.admin_context.mutation_service
    def forbidden(*_args, **_kwargs):
        pytest.fail("Features used Portal validation or Controller secret boundary")
    monkeypatch.setattr(service.validation, "validate_portal_candidate", forbidden)
    monkeypatch.setattr(service.secret_repository, "resolve", forbidden)
    monkeypatch.setattr(service.secret_repository, "keys", forbidden)
    monkeypatch.setattr("app.settings_control.controller_secret.decrypt_secret", forbidden)
    changes = [{"key": "WEB_ADMIN_" + feature + "_ENABLED", "operation": "set", "value": True}
               for feature in (*parents, target)]
    with pytest.raises(SettingsError, match="validation_failed") as error:
        mutate(boot, changes)
    assert error.value.status == 422
    assert all(detail["reason"] == "configuration_prerequisite_invalid" for detail in error.value.details)
    repository = boot.admin_context.read_service.repository
    assert repository.configured() == (0, {})
    with repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM settings_generations").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM settings_mutation_audit").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM settings_idempotency").fetchone()[0] == 0


def test_features_validation_uses_own_candidate_plan(tmp_path, monkeypatch):
    from app.settings_control.validation import SettingsValidationService
    assert SettingsValidationService.validate_features_candidate is not SettingsValidationService.validate_portal_candidate
    boot = bootstrap(tmp_path, **enabled_settings())
    original = AdminFeaturePlanV1.from_snapshot.__func__
    built = []
    def counted(cls, snapshot, registry=None):
        result = original(cls, snapshot, registry)
        built.append(result)
        return result
    def forbidden(*_args, **_kwargs):
        pytest.fail("Features used Portal validation or resolved a secret")
    monkeypatch.setattr(AdminFeaturePlanV1, "from_snapshot", classmethod(counted))
    monkeypatch.setattr(boot.admin_context.mutation_service.validation, "validate_portal_candidate", forbidden)
    monkeypatch.setattr(boot.admin_context.mutation_service.secret_repository, "resolve", forbidden)
    result = mutate(boot, [{"key": "WEB_ADMIN_HOME_HEALTH_ENABLED", "operation": "set", "value": True}])
    assert result.status == 201 and len(built) == 1
    assert built[0].enabled("home.health")
    assert not boot.feature_plan.enabled("home.health")
