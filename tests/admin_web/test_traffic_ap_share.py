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
from app.analytics import (
    CurrentTrafficIntegrityUnavailable,
    CurrentTrafficSourceUnavailable,
    CurrentTrafficValidationError,
    HistoricalTrafficApShare,
    HistoricalTrafficApShareDenominators,
    HistoricalTrafficApShareItem,
    HistoricalTrafficApSharePopulation,
    HistoricalTrafficSourceUnavailable,
)

from .conftest import SITE_ID, enabled_settings, login
from .test_traffic_ap import OneApCurrentSource, _product
from .test_traffic_history import _resolved, _result
from .test_traffic_peak import _peak_result


MAC = "AA:BB:CC:DD:EE:FF"
PRODUCTS = ("history", "statistics", "peak", "aps", "apshare")


def _share(*, base=None, current_status="available", zero=False):
    base = _peak_result(base or _result())
    evidence = base.period_statistics.interval_evidence
    weight = 0.0 if zero else 90.0
    share = None if zero else 1.0
    denominator = "zero_traffic" if zero else "positive"
    item = HistoricalTrafficApShareItem(
        ap_mac=MAC,
        display_name="Main AP",
        display_name_source="current" if current_status == "available" else "historical",
        range_presence_proven=True,
        evidence_status="accepted",
        accepted_presence_interval_count=evidence.accepted_interval_count,
        accepted_presence_seconds=evidence.accepted_interval_seconds,
        download_share_fraction=share,
        upload_share_fraction=share,
        total_share_fraction=share,
        download_weight=weight,
        upload_weight=weight,
    )
    return HistoricalTrafficApShare(
        status="ok" if current_status == "available" else "partial",
        population=HistoricalTrafficApSharePopulation(
            population_count=1,
            historical_population_count=1,
            current_population_status=current_status,
            current_population_count=1 if current_status == "available" else None,
            supported_max_ap_count=12,
            returned_ap_count=1,
            population_complete=current_status == "available",
        ),
        interval_evidence=evidence,
        denominators=HistoricalTrafficApShareDenominators(
            denominator, denominator, denominator
        ),
        items=(item,),
        site_download_weight=weight,
        site_upload_weight=weight,
    )


class ShareSource:
    def __init__(self):
        self.calls = []

    def get_site_history(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        start = datetime.fromisoformat(kwargs["from_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(kwargs["to_utc"].replace("Z", "+00:00"))
        base = _peak_result(_result(
            "7d" if (end - start).days == 7 else "24h",
            evaluated=datetime.fromisoformat(
                kwargs["evaluated_at_utc"].replace("Z", "+00:00")
            ),
        ))
        return replace(
            base,
            period_statistics=(
                base.period_statistics
                if kwargs.get("include_period_statistics") else None
            ),
            peak_load=base.peak_load if kwargs.get("include_peak_load") else None,
            ap_traffic=(
                _product(base=base) if kwargs.get("include_ap_traffic") else None
            ),
            ap_traffic_share=(
                _share(
                    base=base,
                    current_status=kwargs.get(
                        "current_population_status", "available"
                    ),
                )
                if kwargs.get("include_ap_share") else None
            ),
        )

    def compose_current_ap_traffic(self, value, **kwargs):
        return value


class _UnavailableHistoricalSource(ShareSource):
    def get_site_history(self, site_id, **kwargs):
        raise HistoricalTrafficSourceUnavailable("source unavailable")


def _app(
    tmp_path, source, *, share=True, by_ap=False, current_source=None,
    logger=None,
):
    settings = enabled_settings(
        web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="true",
        web_admin_traffic_statistics_enabled="true",
        web_admin_traffic_peak_enabled="true",
        web_admin_traffic_by_ap_enabled=str(by_ap).lower(),
        web_admin_traffic_independent_ranges_enabled="true",
        web_admin_traffic_ap_share_enabled=str(share).lower(),
        web_admin_home_live_enabled="false",
        web_admin_home_traffic_enabled="false",
    )
    runtime = create_admin_web_runtime(
        settings,
        SimpleNamespace(
            state="active",
            visit_service=object(),
            current_traffic_service=current_source or OneApCurrentSource(),
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
        logger or logging.getLogger("traffic-ap-share-test"),
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


def test_share_flag_defaults_false_and_requires_exact_parents():
    assert admin_web_config_from_settings({}).traffic_ap_share_enabled is False
    example = (Path(__file__).parents[2] / ".env.example").read_text(
        encoding="utf-8"
    )
    assert "WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false\n" in example
    with pytest.raises(AdminWebConfigError, match="TRAFFIC_AP_SHARE_ENABLED requires"):
        admin_web_config_from_settings(enabled_settings(
            web_admin_traffic_enabled="true",
            web_admin_traffic_history_enabled="true",
            web_admin_traffic_independent_ranges_enabled="false",
            web_admin_traffic_ap_share_enabled="true",
        ))
    config = admin_web_config_from_settings(enabled_settings(
        web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="true",
        web_admin_traffic_independent_ranges_enabled="true",
        web_admin_traffic_statistics_enabled="false",
        web_admin_traffic_peak_enabled="false",
        web_admin_traffic_by_ap_enabled="false",
        web_admin_traffic_ap_share_enabled="true",
    ))
    assert config.traffic_ap_share_enabled is True


def test_share_panel_is_feature_gated_and_independent(tmp_path):
    disabled = _app(tmp_path, ShareSource(), share=False).test_client()
    assert login(disabled).status_code == 302
    body = disabled.get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    ).get_data(as_text=True)
    assert 'id="traffic-apshare-panel"' not in body

    enabled = _app(tmp_path, ShareSource()).test_client()
    assert login(enabled).status_code == 302
    body = enabled.get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    ).get_data(as_text=True)
    assert 'id="traffic-apshare-panel"' in body
    assert 'id="traffic-apshare-range-24h"' in body
    assert 'id="traffic-apshare-range-7d"' in body


def test_apshare_api_is_atomic_canonical_and_product_scoped(tmp_path):
    source = ShareSource()
    anonymous = _app(tmp_path, source).test_client()
    assert anonymous.get(
        _url("range=24h&products=apshare"), base_url="https://localhost"
    ).status_code == 401

    disabled = _app(tmp_path, ShareSource(), share=False).test_client()
    assert login(disabled).status_code == 302
    assert disabled.get(
        _url("range=24h&products=apshare"), base_url="https://localhost"
    ).status_code == 404
    assert disabled.get(
        _url("range=24h&products=history,apshare"), base_url="https://localhost"
    ).status_code == 404

    client = _app(tmp_path, source).test_client()
    assert login(client).status_code == 302
    assert client.get(
        _url("range=24h&products=apshare", site="f" * 24),
        base_url="https://localhost",
    ).status_code == 403
    for products in (
        "apshare,aps", "apshare,apshare", "apshare,%20aps", "unknown",
    ):
        assert client.get(
            _url(f"range=24h&products={products}"),
            base_url="https://localhost",
        ).status_code == 400
    response = client.get(
        _url("range=24h&products=apshare"), base_url="https://localhost"
    )
    assert response.status_code == 200
    result = response.get_json()["result"]
    assert result["requested_products"] == ["apshare"]
    assert "ap_traffic_share" in result
    assert not ({"buckets", "period_statistics", "peak_load", "ap_traffic", "ap_bucket_axis"} & set(result))
    assert source.calls[-1][1]["include_ap_share"] is True
    assert source.calls[-1][1]["include_ap_traffic"] is False


def test_all_five_products_use_exact_canonical_order(tmp_path):
    source = ShareSource()
    client = _app(tmp_path, source, by_ap=True).test_client()
    assert login(client).status_code == 302
    response = client.get(
        _url(f"range=24h&products={','.join(PRODUCTS)}"),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert response.get_json()["result"]["requested_products"] == list(PRODUCTS)
    assert client.get(
        _url("range=24h&products=history,statistics,peak,apshare,aps"),
        base_url="https://localhost",
    ).status_code == 400


def test_ap_and_share_are_one_atomic_source_execution(tmp_path):
    source = ShareSource()
    client = _app(tmp_path, source, by_ap=True).test_client()
    assert login(client).status_code == 302
    response = client.get(
        _url("range=24h&products=aps,apshare"),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert len(source.calls) == 1
    kwargs = source.calls[0][1]
    assert kwargs["include_ap_traffic"] is True
    assert kwargs["include_ap_share"] is True
    assert response.get_json()["result"]["requested_products"] == [
        "aps", "apshare",
    ]


def test_share_feature_off_preserves_legacy_products_and_include(tmp_path):
    source = ShareSource()
    client = _app(tmp_path, source, share=False, by_ap=True).test_client()
    assert login(client).status_code == 302
    for query in (
        "range=24h&products=history",
        "range=24h&products=statistics",
        "range=24h&products=peak",
        "range=24h&products=aps",
        "range=24h&products=history,statistics,peak,aps",
        "range=24h&include=statistics,peak,aps",
    ):
        response = client.get(_url(query), base_url="https://localhost")
        assert response.status_code == 200, query
        assert source.calls[-1][1]["include_ap_share"] is False
    before = len(source.calls)
    for query in (
        "range=24h&products=apshare",
        "range=24h&products=aps,apshare",
    ):
        assert client.get(
            _url(query), base_url="https://localhost"
        ).status_code == 404
    assert len(source.calls) == before


def test_include_and_products_or_duplicate_products_fail_before_source(tmp_path):
    source = ShareSource()
    client = _app(tmp_path, source).test_client()
    assert login(client).status_code == 302
    for query in (
        "range=24h&include=statistics&products=apshare",
        "range=24h&products=apshare&products=apshare",
        "range=24h&products=",
    ):
        assert client.get(
            _url(query), base_url="https://localhost"
        ).status_code == 400
    assert source.calls == []


class _UnavailableCurrentSource(OneApCurrentSource):
    def get_current_site_traffic(self, site_id, **kwargs):
        raise CurrentTrafficSourceUnavailable("unavailable")


class _IntegrityCurrentSource(OneApCurrentSource):
    def get_current_site_traffic(self, site_id, **kwargs):
        raise CurrentTrafficIntegrityUnavailable("contradictory")


class _ValidationCurrentSource(OneApCurrentSource):
    def get_current_site_traffic(self, site_id, **kwargs):
        raise CurrentTrafficValidationError("internal projection mismatch")


class _UnavailableCurrentPageSource(OneApCurrentSource):
    def list_current_ap_traffic(self, site_id, **kwargs):
        raise CurrentTrafficSourceUnavailable("unavailable")


class _IntegrityCurrentPageSource(OneApCurrentSource):
    def list_current_ap_traffic(self, site_id, **kwargs):
        raise CurrentTrafficIntegrityUnavailable("contradictory")


class _ValidationCurrentPageSource(OneApCurrentSource):
    def list_current_ap_traffic(self, site_id, **kwargs):
        raise CurrentTrafficValidationError("internal projection mismatch")


class _MalformedCurrentPageSource(OneApCurrentSource):
    def list_current_ap_traffic(self, site_id, **kwargs):
        return replace(
            self.page,
            page=replace(self.page.page, next_cursor="unexpected"),
        )


def test_current_source_unavailable_retains_historical_share(tmp_path):
    source = ShareSource()
    client = _app(
        tmp_path, source, current_source=_UnavailableCurrentSource()
    ).test_client()
    assert login(client).status_code == 302
    response = client.get(
        _url("range=24h&products=apshare"), base_url="https://localhost"
    )
    assert response.status_code == 200
    population = response.get_json()["result"]["ap_traffic_share"]["population"]
    assert population["current_population_status"] == "unavailable"
    assert population["current_population_count"] is None
    assert population["population_complete"] is False


@pytest.mark.parametrize(
    "current_source",
    [_UnavailableCurrentSource(), _UnavailableCurrentPageSource()],
)
def test_safe_current_outage_at_summary_or_page_is_partial_not_integrity(
    tmp_path, caplog, current_source,
):
    logger = logging.getLogger(
        f"traffic-ap-share-safe-{type(current_source).__name__}"
    )
    caplog.set_level(logging.INFO, logger=logger.name)
    source = ShareSource()
    client = _app(
        tmp_path, source, current_source=current_source, logger=logger
    ).test_client()
    assert login(client).status_code == 302
    response = client.get(
        _url("range=24h&products=apshare"), base_url="https://localhost"
    )
    assert response.status_code == 200
    share = response.get_json()["result"]["ap_traffic_share"]
    assert share["status"] == "partial"
    assert share["population"]["current_population_status"] == "unavailable"
    assert share["population"]["current_population_count"] is None
    records = [
        record for record in caplog.records
        if record.getMessage() == "admin.traffic_history_query_completed"
        and record.name == logger.name
    ]
    assert records[-1].share_integrity_failure is False


def test_generic_historical_source_outage_is_not_integrity_telemetry(
    tmp_path, caplog,
):
    logger = logging.getLogger("traffic-ap-share-historical-outage")
    caplog.set_level(logging.INFO, logger=logger.name)
    client = _app(
        tmp_path, _UnavailableHistoricalSource(), logger=logger
    ).test_client()
    assert login(client).status_code == 302
    response = client.get(
        _url("range=24h&products=apshare"), base_url="https://localhost"
    )
    assert response.status_code == 503
    records = [
        record for record in caplog.records
        if record.getMessage() == "admin.traffic_history_query_completed"
        and record.name == logger.name
    ]
    assert records[-1].share_integrity_failure is False


def test_safe_current_page_outage_preserves_combined_ap_and_share_response(tmp_path):
    source = ShareSource()
    client = _app(
        tmp_path, source, by_ap=True,
        current_source=_UnavailableCurrentPageSource(),
    ).test_client()
    assert login(client).status_code == 302
    response = client.get(
        _url("range=24h&products=aps,apshare"),
        base_url="https://localhost",
    )
    assert response.status_code == 200
    result = response.get_json()["result"]
    assert result["ap_traffic_share"]["status"] == "partial"
    assert result["ap_traffic_share"]["population"][
        "current_population_status"
    ] == "unavailable"
    assert "ap_traffic" in result


@pytest.mark.parametrize(
    "current_source",
    [
        _IntegrityCurrentSource(), _ValidationCurrentSource(),
        _IntegrityCurrentPageSource(), _ValidationCurrentPageSource(),
        _MalformedCurrentPageSource(),
    ],
)
def test_current_integrity_or_internal_validation_fails_share_closed(
    tmp_path, caplog, current_source,
):
    logger = logging.getLogger(
        f"traffic-ap-share-integrity-{type(current_source).__name__}"
    )
    caplog.set_level(logging.INFO, logger=logger.name)
    source = ShareSource()
    client = _app(
        tmp_path, source, current_source=current_source, logger=logger
    ).test_client()
    assert login(client).status_code == 302
    response = client.get(
        _url("range=24h&products=apshare"), base_url="https://localhost"
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "source_unavailable"
    assert source.calls == []
    records = [
        record for record in caplog.records
        if record.getMessage() == "admin.traffic_history_query_completed"
        and record.name == logger.name
    ]
    assert records[-1].share_integrity_failure is True


def test_malformed_current_population_fails_closed(tmp_path):
    source = ShareSource()
    client = _app(
        tmp_path, source, current_source=_MalformedCurrentPageSource()
    ).test_client()
    assert login(client).status_code == 302
    response = client.get(
        _url("range=24h&products=apshare"), base_url="https://localhost"
    )
    assert response.status_code == 503
    assert source.calls == []


def test_share_serializer_preserves_null_vs_true_zero_and_fails_closed():
    base = _result()
    resolved = _resolved()
    numeric_zero = _share(base=base, zero=True)
    serialized = serialize_historical_traffic(
        replace(base, ap_traffic_share=numeric_zero),
        SITE_ID,
        resolved_range=resolved,
        include_history=False,
        include_ap_share=True,
        requested_products=("apshare",),
    )["ap_traffic_share"]
    item = serialized["items"][0]
    assert item["range_presence_proven"] is True
    assert item["download_share_fraction"] is None
    assert item["total_share_fraction"] is None
    assert serialized["denominators"]["total_status"] == "zero_traffic"

    structural_zero = replace(
        numeric_zero.items[0],
        accepted_presence_interval_count=0,
        accepted_presence_seconds=0.0,
    )
    structural_zero_json = serialize_historical_traffic(
        replace(
            base,
            ap_traffic_share=replace(numeric_zero, items=(structural_zero,)),
        ),
        SITE_ID,
        resolved_range=resolved,
        include_history=False,
        include_ap_share=True,
        requested_products=("apshare",),
    )["ap_traffic_share"]["items"][0]
    assert structural_zero_json["range_presence_proven"] is True
    assert structural_zero_json["accepted_presence_interval_count"] == 0
    assert structural_zero_json["accepted_presence_seconds"] == 0

    unproven = replace(
        numeric_zero.items[0],
        range_presence_proven=False,
        evidence_status="insufficient_data",
        accepted_presence_interval_count=0,
        accepted_presence_seconds=0,
        download_share_fraction=None,
        upload_share_fraction=None,
        total_share_fraction=None,
        download_weight=0.0,
        upload_weight=None,
    )
    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(
            replace(base, ap_traffic_share=replace(
                numeric_zero, items=(unproven,)
            )),
            SITE_ID,
            resolved_range=resolved,
            include_history=False,
            include_ap_share=True,
            requested_products=("apshare",),
        )

    unavailable = _share(base=base, current_status="unavailable")
    unavailable_json = serialize_historical_traffic(
        replace(base, ap_traffic_share=unavailable),
        SITE_ID,
        resolved_range=resolved,
        include_history=False,
        include_ap_share=True,
        requested_products=("apshare",),
    )["ap_traffic_share"]
    assert unavailable_json["status"] == "partial"
    assert unavailable_json["population"]["current_population_status"] == "unavailable"
    assert unavailable_json["population"]["current_population_count"] is None
    assert unavailable_json["items"][0]["total_share_fraction"] == 1
    assert "accepted_endpoint_sample_count" in unavailable_json["coverage"]
    assert "accepted_peak_sample_count" not in unavailable_json["coverage"]

    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(
            replace(base, ap_traffic_share=replace(
                unavailable,
                population=replace(
                    unavailable.population,
                    current_population_count=0,
                ),
            )),
            SITE_ID,
            resolved_range=resolved,
            include_history=False,
            include_ap_share=True,
            requested_products=("apshare",),
        )

    for invalid_fraction in (1.1, float("nan"), float("inf")):
        invalid_item = replace(
            unavailable.items[0],
            total_share_fraction=invalid_fraction,
        )
        with pytest.raises(HistoricalTrafficSerializationError):
            serialize_historical_traffic(
                replace(
                    base,
                    ap_traffic_share=replace(
                        unavailable,
                        items=(invalid_item,),
                    ),
                ),
                SITE_ID,
                resolved_range=resolved,
                include_history=False,
                include_ap_share=True,
                requested_products=("apshare",),
            )


@pytest.mark.parametrize(
    ("count", "seconds"),
    [
        (999, 90.0),
        (1, 999999.0),
        (0, 1.0),
        (1, 0.0),
    ],
)
def test_share_serializer_rejects_impossible_presence_evidence(count, seconds):
    base = _result()
    share = _share(base=base, zero=True)
    item = replace(
        share.items[0],
        accepted_presence_interval_count=count,
        accepted_presence_seconds=seconds,
    )
    with pytest.raises(HistoricalTrafficSerializationError):
        serialize_historical_traffic(
            replace(base, ap_traffic_share=replace(share, items=(item,))),
            SITE_ID,
            resolved_range=_resolved(),
            include_history=False,
            include_ap_share=True,
            requested_products=("apshare",),
        )


def test_share_serializer_accepts_unsupported_without_materializing_subset():
    base = _result()
    source = _share(base=base)
    unsupported = replace(
        source,
        status="unsupported_population",
        population=replace(
            source.population,
            population_count=13,
            historical_population_count=13,
            current_population_count=13,
            returned_ap_count=0,
            population_complete=False,
        ),
        denominators=HistoricalTrafficApShareDenominators(
            "insufficient_data", "insufficient_data", "insufficient_data"
        ),
        items=(),
        site_download_weight=None,
        site_upload_weight=None,
    )
    result = serialize_historical_traffic(
        replace(base, ap_traffic_share=unsupported),
        SITE_ID,
        resolved_range=_resolved(),
        include_history=False,
        include_ap_share=True,
        requested_products=("apshare",),
    )["ap_traffic_share"]
    assert result["status"] == "unsupported_population"
    assert result["population"]["population_count"] == 13
    assert result["population"]["returned_ap_count"] == 0
    assert result["items"] == []
