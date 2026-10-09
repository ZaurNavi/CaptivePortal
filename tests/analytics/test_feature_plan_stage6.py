"""Plan-owned historical source selection, with independent read-only config."""
import logging
import pytest
from app.analytics.runtime import create_analytics_runtime
from app.settings_control.features import AdminFeaturePlanV1
from app.settings_control.models import ResolvedSettingsSnapshot
from app.traffic_projection.config import traffic_projection_read_config_from_settings
from app.traffic_projection.models import TrafficProjectionConfigError
from .test_runtime import _sources, _settings, SITE


def plan(settings):
    return AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(7, settings, {}, {}, {}))


def runtime(settings, stack, selected):
    return create_analytics_runtime(settings, *_sources(stack), logging.getLogger("stage6"), feature_plan=selected)


@pytest.mark.parametrize("admin,root,history", [("false", "true", "true"), ("true", "false", "true"), ("true", "true", "false")])
def test_off_or_dormant_does_not_parse_or_open_projection(analytics_stack, monkeypatch, admin, root, history):
    settings = _settings(web_admin_enabled=admin, web_admin_traffic_enabled=root,
        web_admin_traffic_history_enabled=history, web_admin_traffic_projection_read_enabled="true",
        traffic_projection_db_path="invalid", traffic_projection_writer_lock_path=None)
    import app.traffic_projection.config as config
    monkeypatch.setattr(config, "traffic_projection_read_config_from_settings",
        lambda *_: pytest.fail("dormant projection config accessed"))
    result = runtime(settings, analytics_stack, plan(settings))
    assert result.state == "active" and result.historical_source_mode == "base"
    assert result.historical_traffic_service is not None


def test_source_selection_uses_supplied_plan_not_raw_flag(analytics_stack, monkeypatch, tmp_path):
    settings = _settings(web_admin_enabled="true", web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="true", web_admin_traffic_projection_read_enabled="true",
        traffic_projection_enabled="invalid writer flag",
        traffic_projection_writer_lock_path=None,
        traffic_projection_db_path=str(tmp_path / "projection.sqlite3"),
        observation_db_path=str(tmp_path / "observation.sqlite3"), observation_site_ids=SITE)
    selected = plan(settings)
    supplied = {**settings, "web_admin_traffic_projection_read_enabled": "false"}
    from app.traffic_projection.repository import TrafficProjectionRepository
    monkeypatch.setattr(TrafficProjectionRepository, "initialize", lambda *_: pytest.fail("writer initialization"))
    result = runtime(supplied, analytics_stack, selected)
    assert result.feature_plan is selected and result.historical_source_mode == "projection"
    assert result.historical_traffic_service is not None
    assert not (tmp_path / "projection.sqlite3").exists()


def test_selected_projection_failure_never_falls_back(analytics_stack):
    settings = _settings(web_admin_enabled="true", web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="true", web_admin_traffic_projection_read_enabled="true",
        traffic_projection_db_path="relative")
    result = runtime(settings, analytics_stack, plan(settings))
    assert result.historical_source_mode == "projection"
    assert result.historical_traffic_service is None


@pytest.mark.parametrize("damage", ["relative", "same", "empty_scope", "bad_scope"])
def test_read_config_prerequisites_exclude_writer(tmp_path, damage):
    settings = {"traffic_projection_db_path": str(tmp_path / "projection.sqlite3"),
        "observation_db_path": str(tmp_path / "observation.sqlite3"), "observation_site_ids": SITE,
        "traffic_projection_enabled": "not a boolean", "traffic_projection_writer_lock_path": None}
    if damage == "relative":
        settings["traffic_projection_db_path"] = "relative"
    elif damage == "same":
        settings["traffic_projection_db_path"] = settings["observation_db_path"]
    else:
        settings["observation_site_ids"] = "" if damage == "empty_scope" else "invalid"
    with pytest.raises(TrafficProjectionConfigError):
        traffic_projection_read_config_from_settings(settings)


def test_read_config_does_not_require_writer(tmp_path):
    settings = {"traffic_projection_db_path": str(tmp_path / "projection.sqlite3"),
        "observation_db_path": str(tmp_path / "observation.sqlite3"), "observation_site_ids": SITE,
        "traffic_projection_enabled": "not a boolean", "traffic_projection_writer_lock_path": None}
    config = traffic_projection_read_config_from_settings(settings)
    assert config.read_enabled and config.site_ids == (SITE,)
    assert not hasattr(config, "writer_lock_path") and not hasattr(config, "enabled")
