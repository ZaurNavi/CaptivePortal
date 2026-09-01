from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime
from pathlib import Path
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

from .conftest import SITE_ID, enabled_settings, login
from .test_traffic_ap import OneApCurrentSource, _product
from .test_traffic_history import _resolved, _result
from .test_traffic_peak import _peak_result


PRODUCTS = ("history", "statistics", "peak", "aps")


class ProductSource:
    def __init__(self):
        self.calls = []

    def get_site_history(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        start = datetime.fromisoformat(kwargs["from_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(kwargs["to_utc"].replace("Z", "+00:00"))
        evaluated = datetime.fromisoformat(
            kwargs["evaluated_at_utc"].replace("Z", "+00:00")
        )
        base = _result(
            "7d" if (end - start).days == 7 else "24h",
            evaluated=evaluated,
        )
        value = _peak_result(base)
        if not kwargs.get("include_peak_load"):
            value = replace(value, peak_load=None)
        if not kwargs.get("include_period_statistics"):
            value = replace(value, period_statistics=None)
        if kwargs.get("include_ap_traffic"):
            value = replace(value, ap_traffic=_product(base=base))
        return value

    def compose_current_ap_traffic(self, value, **kwargs):
        self.calls.append(("compose", kwargs))
        return value


def _app(tmp_path, source, *, independent=True):
    settings = enabled_settings(
        web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="true",
        web_admin_traffic_statistics_enabled="true",
        web_admin_traffic_peak_enabled="true",
        web_admin_traffic_by_ap_enabled="true",
        web_admin_traffic_independent_ranges_enabled=str(independent).lower(),
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
        SimpleNamespace(repository=SimpleNamespace(
            config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3")
        )),
        SimpleNamespace(repository=SimpleNamespace(
            db_path=tmp_path / "visits.sqlite3"
        )),
        SimpleNamespace(_repository=SimpleNamespace(
            db_path=tmp_path / "observations.sqlite3"
        )),
        logging.getLogger("traffic-independent-ranges-test"),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1
    )
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def _url(query, site=SITE_ID):
    return f"/admin/api/v1/sites/{site}/traffic/history?{query}"


def _project(value, products):
    return serialize_historical_traffic(
        value,
        SITE_ID,
        resolved_range=_resolved(),
        include_history="history" in products,
        include_period_statistics="statistics" in products,
        include_peak_load="peak" in products,
        include_ap_traffic="aps" in products,
        requested_products=products,
    )


def test_independent_ranges_flag_defaults_false_and_requires_history():
    assert admin_web_config_from_settings({}).traffic_independent_ranges_enabled is False
    example = (Path(__file__).parents[2] / ".env.example").read_text(
        encoding="utf-8"
    )
    assert "WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=false\n" in example
    with pytest.raises(AdminWebConfigError, match="INDEPENDENT_RANGES_ENABLED requires"):
        admin_web_config_from_settings(enabled_settings(
            web_admin_traffic_enabled="true",
            web_admin_traffic_history_enabled="false",
            web_admin_traffic_independent_ranges_enabled="true",
        ))


@pytest.mark.parametrize(
    "query",
    (
        "range=24h&products=",
        "range=24h&products=statistics,history",
        "range=24h&products=history,history",
        "range=24h&products=history,unknown",
        "range=24h&products=history,%20statistics",
        "range=24h&products=history&products=statistics",
        "range=24h&products=history&include=statistics",
    ),
)
def test_products_query_is_exact_canonical_and_rejected_before_source(
    tmp_path, query,
):
    source = ProductSource()
    client = _app(tmp_path, source).test_client()
    assert login(client).status_code == 302
    response = client.get(_url(query), base_url="https://localhost")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_request"
    assert source.calls == []


def test_products_security_and_feature_gate_precede_query_validation(tmp_path):
    source = ProductSource()
    anonymous = _app(tmp_path, source).test_client()
    assert anonymous.get(
        _url("range=24h&products=history&products=statistics"),
        base_url="https://localhost",
    ).status_code == 401

    disabled = _app(tmp_path, source, independent=False).test_client()
    assert login(disabled).status_code == 302
    response = disabled.get(
        _url("range=24h&products=history"),
        base_url="https://localhost",
    )
    assert response.status_code == 404
    forbidden = disabled.get(
        _url("range=24h&products=history", site="f" * 24),
        base_url="https://localhost",
    )
    assert forbidden.status_code == 403
    assert source.calls == []


def test_page_switches_between_independent_and_legacy_range_controls(tmp_path):
    source = ProductSource()
    enabled = _app(tmp_path, source, independent=True).test_client()
    assert login(enabled).status_code == 302
    body = enabled.get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    ).get_data(as_text=True)
    assert 'data-traffic-independent-ranges-enabled="true"' in body
    assert 'id="traffic-history-range-24h"' in body
    assert 'id="traffic-statistics-range-24h"' in body
    assert 'id="traffic-peak-range-24h"' in body
    assert 'id="traffic-ap-range-24h"' in body
    assert 'id="traffic-network-range-24h"' not in body

    legacy = _app(tmp_path, ProductSource(), independent=False).test_client()
    assert login(legacy).status_code == 302
    body = legacy.get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    ).get_data(as_text=True)
    assert 'data-traffic-independent-ranges-enabled="false"' in body
    assert 'id="traffic-network-range-24h"' in body
    assert 'id="traffic-history-range-24h"' not in body


@pytest.mark.parametrize(
    "products,fields",
    (
        (("history",), {"buckets"}),
        (("statistics",), {"period_statistics"}),
        (("peak",), {"peak_load"}),
        (("aps",), {"ap_traffic", "ap_bucket_axis"}),
        (PRODUCTS, {
            "buckets", "period_statistics", "peak_load", "ap_traffic",
            "ap_bucket_axis",
        }),
    ),
)
def test_products_route_returns_exact_projection_in_one_historical_call(
    tmp_path, products, fields,
):
    source = ProductSource()
    client = _app(tmp_path, source).test_client()
    assert login(client).status_code == 302
    response = client.get(
        _url(f"range=24h&products={','.join(products)}"),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    result = response.get_json()["result"]
    assert result["requested_products"] == list(products)
    optional = {
        "buckets", "period_statistics", "peak_load", "ap_traffic",
        "ap_bucket_axis",
    }
    assert set(result) & optional == fields
    history_calls = [call for call in source.calls if call[0] == SITE_ID]
    assert len(history_calls) == 1
    flags = history_calls[0][1]
    assert flags["include_period_statistics"] is ("statistics" in products)
    assert flags["include_peak_load"] is ("peak" in products)
    assert flags["include_ap_traffic"] is ("aps" in products)


def test_single_product_projection_matches_same_product_in_combined_response():
    base = _result()
    value = _peak_result(base)
    value = replace(value, ap_traffic=_product(base=base))
    combined = _project(value, PRODUCTS)
    for product, field in (
        ("history", "buckets"),
        ("statistics", "period_statistics"),
        ("peak", "peak_load"),
        ("aps", "ap_traffic"),
    ):
        projected_value = value
        if product != "statistics":
            projected_value = replace(projected_value, period_statistics=None)
        if product != "peak":
            projected_value = replace(projected_value, peak_load=None)
        if product != "aps":
            projected_value = replace(projected_value, ap_traffic=None)
        single = _project(projected_value, (product,))
        assert single[field] == combined[field]
    ap_only = _project(
        replace(value, period_statistics=None, peak_load=None), ("aps",)
    )
    assert ap_only["ap_bucket_axis"] == {
        "bucket_count": 288,
        "bucket_seconds": 300,
        "bucket_start_utc": [bucket.bucket_start_utc for bucket in base.buckets],
    }


def test_serializer_fails_closed_on_requested_projection_mismatch():
    with pytest.raises(
        HistoricalTrafficSerializationError,
        match="requested product projection",
    ):
        serialize_historical_traffic(
            _result(),
            SITE_ID,
            resolved_range=_resolved(),
            include_history=True,
            requested_products=("statistics",),
        )
