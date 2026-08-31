from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.admin_web.config import AdminWebConfigError, admin_web_config_from_settings
from app.admin_web.historical_traffic_serialization import (
    HistoricalTrafficSerializationError,
    serialize_historical_traffic,
)
from app.admin_web.traffic_network_ranges import resolve_traffic_network_range
from app.analytics import (
    CurrentTrafficPageMetadata,
    HistoricalTrafficApCoverage,
    HistoricalTrafficApItem,
    HistoricalTrafficApNow,
    HistoricalTrafficApPopulation,
    HistoricalTrafficApSeries,
    HistoricalTrafficByAp,
    HistoricalTrafficPeriodValues,
)

from .conftest import SITE_ID, enabled_settings, login
from .test_home_traffic import TrafficSource, traffic_page, traffic_summary
from .test_traffic_history import EVALUATED, _result


MAC = "AA:BB:CC:DD:EE:FF"


def _product(*, unsupported=False, base=None):
    base = base or _result()
    if unsupported:
        return HistoricalTrafficByAp(
            status="unsupported_population",
            population=HistoricalTrafficApPopulation(13, 1, 13, 12, 0, False),
            current_snapshot=None,
            items=(),
        )
    count = len(base.buckets)
    seconds = (count - 1) * base.range.bucket_seconds
    item = HistoricalTrafficApItem(
        ap_mac=MAC,
        display_name="Main AP",
        display_name_source="current",
        status="complete",
        series=HistoricalTrafficApSeries(
            count,
            ("complete",) * count,
            (1.25,) * count,
            (.25,) * count,
        ),
        average=HistoricalTrafficPeriodValues(1.25, .25, 1.5),
        peak=HistoricalTrafficPeriodValues(1.25, .25, 1.5),
        coverage=HistoricalTrafficApCoverage(
            "complete", count, count, 0, 0, count, count,
            seconds, seconds, 1.0, 0, 0, 0, 0, 0, 0, 0,
        ),
        now=HistoricalTrafficApNow(
            "valid", 20.0, 3.0, 23.0, "ok", "ok",
            base.range.to_utc, 0.0, "wired",
        ),
    )
    return HistoricalTrafficByAp(
        status="ok",
        population=HistoricalTrafficApPopulation(1, 1, 1, 12, 1, True),
        current_snapshot=replace(
            traffic_summary().snapshot,
            evaluated_at=base.range.to_utc,
            observed_at=base.range.to_utc,
            newest_observed_at=base.range.to_utc,
            age_seconds=0.0,
            source_skew_seconds=0.0,
        ),
        items=(item,),
    )


class ApHistorySource:
    def __init__(self, *, unsupported=False):
        self.calls = []
        self.unsupported = unsupported

    def get_site_history(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        start = datetime.fromisoformat(kwargs["from_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(kwargs["to_utc"].replace("Z", "+00:00"))
        range_id = "24h" if (end - start).total_seconds() == 86400 else "7d"
        evaluated = datetime.fromisoformat(
            kwargs["evaluated_at_utc"].replace("Z", "+00:00")
        )
        base = _result(range_id, evaluated=evaluated)
        product = _product(unsupported=self.unsupported, base=base)
        return replace(
            base,
            ap_traffic=(product if kwargs.get("include_ap_traffic") else None),
        )

    def compose_current_ap_traffic(self, value, **kwargs):
        self.calls.append(("compose", kwargs))
        return value


class OneApCurrentSource(TrafficSource):
    def __init__(self):
        super().__init__()
        self.summary = replace(
            self.summary,
            coverage=replace(
                self.summary.coverage,
                total_ap_count=1,
                valid_rate_ap_count=1,
                valid_download_ap_count=1,
                valid_upload_ap_count=1,
                missing_rate_ap_count=0,
            ),
            source_selection=replace(
                self.summary.source_selection,
                wired_pair_valid_ap_count=1,
                lan_pair_valid_ap_count=1,
            ),
        )
        page = traffic_page()
        self.page = replace(
            page,
            page=CurrentTrafficPageMetadata(
                12, None, page.page.cycle_id, page.page.selected_source
            ),
        )


def _app(tmp_path, source, *, enabled=True):
    settings = enabled_settings(
        web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="true",
        web_admin_traffic_by_ap_enabled=str(enabled).lower(),
        web_admin_home_live_enabled="false",
        web_admin_home_traffic_enabled="false",
    )
    runtime = create_admin_web_runtime(
        settings,
        SimpleNamespace(
            state="active",
            visit_service=object(),
            current_traffic_service=OneApCurrentSource(),
            historical_traffic_service=source,
        ),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logging.getLogger("traffic-ap-test"),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def _url(query, site=SITE_ID):
    return f"/admin/api/v1/sites/{site}/traffic/history?{query}"


def test_ap_flag_defaults_false_and_requires_only_traffic_history_parents():
    assert admin_web_config_from_settings({}).traffic_by_ap_enabled is False
    with pytest.raises(AdminWebConfigError, match="TRAFFIC_BY_AP_ENABLED requires"):
        admin_web_config_from_settings(enabled_settings(
            web_admin_traffic_enabled="true",
            web_admin_traffic_history_enabled="false",
            web_admin_traffic_by_ap_enabled="true",
        ))
    config = admin_web_config_from_settings(enabled_settings(
        web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="true",
        web_admin_traffic_statistics_enabled="false",
        web_admin_traffic_peak_enabled="false",
        web_admin_traffic_by_ap_enabled="true",
    ))
    assert config.traffic_by_ap_enabled is True


def test_ap_markup_is_absent_when_disabled_and_present_when_enabled(tmp_path):
    disabled = _app(tmp_path, ApHistorySource(), enabled=False).test_client()
    assert login(disabled).status_code == 302
    response = disabled.get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    )
    assert response.status_code == 200
    assert b'id="traffic-ap-panel"' not in response.data

    enabled = _app(tmp_path, ApHistorySource(), enabled=True).test_client()
    assert login(enabled).status_code == 302
    response = enabled.get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    )
    assert response.status_code == 200
    assert b'id="traffic-ap-panel"' in response.data
    assert b'id="traffic-ap-selector"' not in response.data
    assert b'id="traffic-ap-next"' not in response.data


def test_ap_include_security_feature_gate_exact_grammar_and_no_pagination(tmp_path):
    source = ApHistorySource()
    anonymous = _app(tmp_path, source).test_client()
    assert anonymous.get(_url("range=24h&include=aps"), base_url="https://localhost").status_code == 401

    disabled = _app(tmp_path, ApHistorySource(), enabled=False).test_client()
    assert login(disabled).status_code == 302
    assert disabled.get(_url("range=24h&include=aps"), base_url="https://localhost").status_code == 404
    assert disabled.get(_url("range=24h"), base_url="https://localhost").status_code == 200

    client = _app(tmp_path, source).test_client()
    assert login(client).status_code == 302
    assert client.get(_url("range=24h&include=aps", "f" * 24), base_url="https://localhost").status_code == 403
    for include in ("ap", "aps,statistics", "statistics,aps,peak", "aps,aps"):
        assert client.get(_url(f"range=24h&include={include}"), base_url="https://localhost").status_code == 400
    assert client.get(_url("range=24h&include=aps&ap_limit=4"), base_url="https://localhost").status_code == 400
    response = client.get(_url("range=24h&include=aps"), base_url="https://localhost")
    assert response.status_code == 200
    result = response.get_json()["result"]
    payload = result["ap_traffic"]
    assert payload["population"]["population_count"] == 1
    assert len(payload["items"]) == 1
    assert source.calls[0][1]["include_ap_traffic"] is True
    assert payload["items"][0]["now"] == {
        "status": "valid",
        "download_mbps": 20.0,
        "upload_mbps": 3.0,
        "total_mbps": 23.0,
        "download_reason": "ok",
        "upload_reason": "ok",
        "observed_at": result["range"]["to_utc"],
        "age_seconds": 0.0,
        "selected_source": "wired",
    }


def test_unsupported_population_is_valid_http_product_state(tmp_path):
    client = _app(tmp_path, ApHistorySource(unsupported=True)).test_client()
    assert login(client).status_code == 302
    response = client.get(_url("range=24h&include=aps"), base_url="https://localhost")
    assert response.status_code == 200
    product = response.get_json()["result"]["ap_traffic"]
    assert product["status"] == "unsupported_population"
    assert product["population"]["population_count"] == 13
    assert product["population"]["returned_ap_count"] == 0
    assert product["items"] == []


def test_ap_serializer_fails_closed_on_silent_truncation():
    resolved = resolve_traffic_network_range("24h", EVALUATED)
    base = _result()
    invalid = replace(
        _product(),
        population=HistoricalTrafficApPopulation(2, 1, 1, 12, 1, True),
    )
    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(
            replace(base, ap_traffic=invalid),
            SITE_ID,
            resolved_range=resolved,
            include_ap_traffic=True,
        )
