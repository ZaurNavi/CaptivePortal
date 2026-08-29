from __future__ import annotations

import logging
import threading

from app.analytics.historical_traffic import HistoricalTrafficReadService
from app.analytics.runtime import create_analytics_runtime
from app.analytics.source_gateway import AnalyticsSourceGateway
from app.visit_lifecycle.read_service import VisitLifecycleReadService
from app.visitor_registry.registry_read_service import VisitorRegistryReadService
from app.visitor_registry.registry_service import VisitorRegistryService


SITE = "0123456789abcdef01234567"


def _settings(**overrides):
    values = {
        "analytics_foundation_enabled": "true",
        "analytics_wireless_enabled": "true",
        "analytics_visit_enabled": "true",
        "analytics_api_enabled": "true",
        "analytics_api_bearer_token": "x" * 32,
        "analytics_api_allowed_networks": "127.0.0.1/32,::1/128",
        "analytics_api_allowed_site_ids": SITE,
    }
    values.update(overrides)
    return values


def _sources(stack):
    observation = type("ObservationRuntime", (), {
        "state": "active", "repository": stack.observations,
    })()
    visit = type("VisitRuntime", (), {
        "state": "active",
        "read_service": VisitLifecycleReadService(stack.visits),
    })()
    registry = VisitorRegistryReadService(
        stack.registry, VisitorRegistryService("UTC"), configured_enabled=True,
    )
    return observation, visit, registry


def test_runtime_exposes_optional_historical_service_without_startup_query(
    analytics_stack, monkeypatch
):
    observation, visit, registry = _sources(analytics_stack)
    before = tuple(thread.ident for thread in threading.enumerate())

    def unexpected_query(*args, **kwargs):
        raise AssertionError("historical source query ran during composition")

    monkeypatch.setattr(
        AnalyticsSourceGateway, "historical_traffic_data", unexpected_query
    )
    runtime = create_analytics_runtime(
        _settings(), observation, visit, registry, logging.getLogger("test")
    )
    assert isinstance(runtime.historical_traffic_service, HistoricalTrafficReadService)
    assert tuple(thread.ident for thread in threading.enumerate()) == before


def test_historical_construction_failure_is_fail_open(analytics_stack, monkeypatch):
    observation, visit, registry = _sources(analytics_stack)

    def fail(*args, **kwargs):
        raise RuntimeError("controlled")

    monkeypatch.setattr(HistoricalTrafficReadService, "__init__", fail)
    runtime = create_analytics_runtime(
        _settings(), observation, visit, registry, logging.getLogger("test")
    )
    assert runtime.state == "active"
    assert runtime.historical_traffic_service is None
    assert runtime.current_traffic_service is not None
    assert runtime.home_activity_service is not None
    assert runtime.quality_service is not None
    assert runtime.wireless_service is not None
    assert runtime.visit_service is not None


def test_disabled_runtime_has_no_historical_service():
    runtime = create_analytics_runtime(
        _settings(analytics_foundation_enabled="false"),
        None, None, None, logging.getLogger("test"),
    )
    assert runtime.state == "disabled"
    assert runtime.historical_traffic_service is None
