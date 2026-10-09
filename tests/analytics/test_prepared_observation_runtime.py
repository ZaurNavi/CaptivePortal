"""Regression for pre-adoption Analytics/Admin composition from local reads."""
import logging
import threading

import pytest

from app.admin_web import create_admin_web_runtime
from app.admin_web.home_ap_24h_telemetry import create_home_ap_24h_telemetry_worker
from app.current_state.runtime import create_current_state_runtime
from app.observations.runtime import ObservationFoundationRuntime
from app.observations.telemetry import ObservationTelemetry
from app.analytics.runtime import create_analytics_runtime
from app.settings_control.features import AdminFeaturePlanV1
from app.settings_control.models import ResolvedSettingsSnapshot
from tests.admin_web.conftest import enabled_settings
from tests.observations.test_read_boundary_preparation import ProviderSpy, workers
from tests.observations.test_runtime import Telemetry
from .test_runtime import _settings, _sources, SITE


def local_observation(stack):
    provider, telemetry = ProviderSpy(), Telemetry()
    runtime = ObservationFoundationRuntime(config=stack.observations.config, provider=provider,
        telemetry=ObservationTelemetry(telemetry, logging.getLogger("fix2-observation")),
        logger=logging.getLogger("fix2-observation"))
    return runtime, provider, telemetry


@pytest.mark.parametrize("prepared", [False, True])
def test_analytics_requires_explicit_preparation_without_starting_workers(analytics_stack, monkeypatch, prepared):
    observation, provider, _ = local_observation(analytics_stack)
    _, visit, registry = _sources(analytics_stack)
    for worker in workers(observation):
        monkeypatch.setattr(worker, "start", lambda: pytest.fail("pre-adoption worker start"))
    if prepared:
        assert observation.prepare_read_boundary() is True
    before = tuple(thread.ident for thread in threading.enumerate())
    settings = _settings()
    feature_plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, settings, {}, {}, {}))
    analytics = create_analytics_runtime(settings, observation, visit, registry, logging.getLogger("fix2-analytics"),
        feature_plan=feature_plan)
    assert analytics.feature_plan is feature_plan and analytics.historical_source_mode == "base"
    assert analytics.state == ("active" if prepared else "unavailable")
    assert analytics.source_health["observations"].available is prepared
    if prepared:
        assert analytics.source_health["observations"].query_only is True
        assert analytics.source_health["observations"].actual_schema_version == 1
    assert observation.state == "disabled"
    assert all(not worker.running for worker in workers(observation))
    assert tuple(thread.ident for thread in threading.enumerate()) == before
    assert provider.calls == []


def test_prepared_read_boundary_still_requires_exact_source_schema(analytics_stack):
    observation, provider, _ = local_observation(analytics_stack)
    _, visit, registry = _sources(analytics_stack)
    assert observation.prepare_read_boundary() is True
    with observation.repository._connect() as connection:
        connection.execute("PRAGMA user_version=999")
    settings = _settings()
    feature_plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, settings, {}, {}, {}))
    analytics = create_analytics_runtime(settings, observation, visit, registry, logging.getLogger("fix2-schema"),
        feature_plan=feature_plan)
    assert analytics.feature_plan is feature_plan and analytics.historical_source_mode == "base"
    assert analytics.state == "unavailable"
    assert not analytics.source_health["observations"].available
    assert analytics.source_health["observations"].actual_schema_version == 999
    assert provider.calls == []


def test_prepared_observation_restores_admin_home_ap24_and_telemetry(analytics_stack, tmp_path, caplog):
    observation, provider, _ = local_observation(analytics_stack)
    _, visit, registry = _sources(analytics_stack)
    settings = {**_settings(), **enabled_settings(),
        "web_admin_home_ap_24h_enabled": "true",
        "web_admin_home_ap_24h_telemetry_enabled": "true",
        "current_state_enabled": "true", "current_state_site_ids": SITE,
        "current_state_client_ssids_json": '["synthetic-guest"]',
        "current_state_db_path": str(tmp_path / "data" / "current.sqlite3")}
    current = create_current_state_runtime(settings, provider, Telemetry())
    assert current.state == "disabled" and current.read_service is not None
    assert observation.prepare_read_boundary() is True
    feature_plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, settings, {}, {}, {}))
    analytics = create_analytics_runtime(settings, observation, visit, registry, logging.getLogger("fix2-admin"),
        feature_plan=feature_plan)
    assert analytics.feature_plan is feature_plan and analytics.historical_source_mode == "base"
    assert analytics.state == "active"
    admin = create_admin_web_runtime(settings, analytics, registry, visit.read_service,
        analytics._source_services["observations"], logging.getLogger("fix2-admin"),
        current_state_read_service=current.read_service, current_state_runtime=current,
        observation_runtime=observation, feature_plan=feature_plan)
    assert admin.feature_plan is feature_plan
    assert admin.state == "active" and admin.query_service is not None
    assert all(source is not None for source in (registry, visit.read_service, analytics._source_services["observations"]))
    assert admin.home_ap_24h_state == "active" and admin.home_ap_24h_service is not None
    telemetry = type("HealthyTelemetry", (), {
        "enabled": True, "available": True, "safe_emit_system": lambda *_args, **_kwargs: True})()
    worker = create_home_ap_24h_telemetry_worker(settings, admin_runtime=admin,
        telemetry=telemetry, logger=logging.getLogger("fix2-telemetry"))
    assert worker is not None and worker._thread is None
    assert "admin.home_ap_24h_composition_failed" not in caplog.text
    assert "admin.home_ap_24h_telemetry_composition_failed" not in caplog.text
    assert observation.state == current.state == "disabled"
    assert all(not item.running for item in workers(observation))
    assert provider.calls == []
