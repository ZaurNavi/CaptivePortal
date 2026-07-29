"""Public HTTP API for portal counter totals."""

from flask import Blueprint, jsonify

from .service import PortalCounterService


def create_portal_counter_blueprint(
    service: PortalCounterService,
    public_traffic_service=None,
) -> Blueprint:
    blueprint = Blueprint(
        "portal_counter",
        __name__,
    )

    @blueprint.get("/api/public/portal-counter")
    def get_portal_counter():
        service.logger.debug("portal_counter.api_requested")

        try:
            snapshot = service.get_snapshot()
        except Exception:
            service.logger.exception(
                "portal_counter.read_failed"
            )
            response = jsonify(
                {"error": "counter_unavailable"}
            )
            response.status_code = 503
            response.headers["Cache-Control"] = "no-store"
            return response

        traffic_payload = {
            "available": False,
            "ssid": getattr(
                public_traffic_service,
                "ssid",
                "",
            ),
        }
        if public_traffic_service is not None:
            try:
                traffic_payload = (
                    public_traffic_service.snapshot_payload()
                )
            except Exception:
                service.logger.exception(
                    "public_traffic_database_error"
                )

        response = jsonify({
            "opened_today": snapshot.opened_today,
            "opened_total": snapshot.opened_total,
            "day": snapshot.day,
            "timezone": snapshot.timezone,
            "traffic": traffic_payload,
        })
        response.headers["Cache-Control"] = "no-store"
        return response

    return blueprint
