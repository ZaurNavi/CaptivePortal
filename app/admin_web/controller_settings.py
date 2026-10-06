"""Read-only, secret-free Controller projection. No provider/store/network access."""

from dataclasses import dataclass

from app.controllers.omada_config import OmadaControllerPublicConfigSnapshot


@dataclass(frozen=True, slots=True)
class ControllerConfigurationReadService:
    snapshot: OmadaControllerPublicConfigSnapshot

    def __post_init__(self):
        if type(self.snapshot) is not OmadaControllerPublicConfigSnapshot:
            raise ValueError("public Controller snapshot required")
        snapshot = self.snapshot
        for name in ("controller_url", "controller_id", "client_id"):
            if not isinstance(getattr(snapshot, name), str) or not getattr(snapshot, name):
                raise ValueError("public Controller snapshot unavailable")
        for name in ("controller_url_source", "controller_id_source", "client_id_source",
                     "client_secret_source", "tls_certificate_verification_source"):
            if getattr(snapshot, name) not in ("environment", "repository_default"):
                raise ValueError("public Controller snapshot unavailable")
        if snapshot.client_secret_presence not in ("configured", "not_configured"):
            raise ValueError("public Controller snapshot unavailable")
        if type(snapshot.tls_certificate_verification) is not bool:
            raise ValueError("public Controller snapshot unavailable")

    def read(self, request_id: str) -> dict:
        snapshot = self.snapshot

        def value(label, kind, effective_value, source):
            return {"display_label": label, "value_type": kind,
                    "effective_value": effective_value, "effective_source": source}

        return {
            "api_version": "admin.settings.controller.v1",
            "request_id": request_id,
            "scope": {"type": "global"},
            "resource": {"type": "omada_controller", "scope": "installation"},
            "management_mode": "deployment_controlled",
            "configuration_state": "configured",
            "fields": {
                "controller_url": value("Controller URL", "url", snapshot.controller_url,
                                        snapshot.controller_url_source),
                "controller_id": value("Controller ID", "string", snapshot.controller_id,
                                       snapshot.controller_id_source),
                "client_id": value("Client / Application ID", "string", snapshot.client_id,
                                   snapshot.client_id_source),
                "client_secret": {"display_label": "Client Secret", "value_type": "secret_presence",
                                  "effective_presence": snapshot.client_secret_presence,
                                  "effective_source": snapshot.client_secret_source},
                "tls_certificate_verification": value("TLS certificate verification", "boolean",
                    snapshot.tls_certificate_verification, snapshot.tls_certificate_verification_source),
            },
        }
