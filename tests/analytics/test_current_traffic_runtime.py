from __future__ import annotations

import logging

import app.analytics.runtime as runtime_module
from app.analytics.current_traffic import CurrentTrafficReadService
from app.settings_control.features import AdminFeaturePlanV1
from app.settings_control.models import ResolvedSettingsSnapshot
from tests.analytics.test_runtime import _settings, _sources


def test_runtime_exposes_optional_current_traffic_without_readiness_change(
    analytics_stack,
):
    observation, visit, registry = _sources(analytics_stack)
    settings = _settings()
    feature_plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, settings, {}, {}, {}))
    runtime = runtime_module.create_analytics_runtime(
        settings, observation, visit, registry, logging.getLogger("test"), feature_plan=feature_plan
    )
    assert runtime.feature_plan is feature_plan and runtime.historical_source_mode == "base"
    assert runtime.state == "active"
    assert isinstance(runtime.current_traffic_service, CurrentTrafficReadService)
    assert runtime.live_health_payload()[0] is True


def test_traffic_construction_failure_is_fail_open(
    analytics_stack, monkeypatch
):
    observation, visit, registry = _sources(analytics_stack)

    class ExplodingTraffic:
        def __init__(self, gateway):
            raise RuntimeError("traffic only")

    monkeypatch.setattr(runtime_module, "CurrentTrafficReadService", ExplodingTraffic)
    settings = _settings()
    feature_plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, settings, {}, {}, {}))
    runtime = runtime_module.create_analytics_runtime(
        settings, observation, visit, registry, logging.getLogger("test"), feature_plan=feature_plan
    )
    assert runtime.feature_plan is feature_plan and runtime.historical_source_mode == "base"
    assert runtime.state == "active"
    assert runtime.current_traffic_service is None
    assert runtime.quality_service is not None
    assert runtime.wireless_service is not None
    assert runtime.visit_service is not None
    assert runtime.live_health_payload()[0] is True
