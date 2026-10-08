"""Secret-free Controller V3 composition through the common Settings boundary."""

from dataclasses import dataclass

from app.controllers.omada_config import OmadaControllerPublicConfigSnapshot
from app.settings_control.models import SettingsError
from app.settings_control.controller_secret import CONTROLLER_SECRET_DEFINITION


@dataclass(frozen=True, slots=True)
class ControllerConfigurationReadService:
    snapshot: OmadaControllerPublicConfigSnapshot
    configured_read_service: object = None
    secret_metadata_service: object = None

    def __post_init__(self):
        if type(self.snapshot) is not OmadaControllerPublicConfigSnapshot:
            raise ValueError("public Controller snapshot required")
        snapshot = self.snapshot
        for name in ("controller_url", "controller_id", "client_id"):
            if not isinstance(getattr(snapshot, name), str) or not getattr(snapshot, name):
                raise ValueError("public Controller snapshot unavailable")
        for name in ("controller_url_source", "controller_id_source", "client_id_source",
                     "client_secret_source", "tls_certificate_verification_source"):
            allowed = ("environment", "repository_default", "persisted_override") if name in ("controller_url_source", "controller_id_source", "client_id_source") else ("environment", "repository_default", "managed_secret_override") if name == "client_secret_source" else ("environment", "repository_default")
            if getattr(snapshot, name) not in allowed:
                raise ValueError("public Controller snapshot unavailable")
        if snapshot.client_secret_presence not in ("configured", "not_configured"):
            raise ValueError("public Controller snapshot unavailable")
        if type(snapshot.tls_certificate_verification) is not bool:
            raise ValueError("public Controller snapshot unavailable")
        if not callable(getattr(self.configured_read_service, "read_controller", None)):
            raise ValueError("configured Controller read boundary required")

    def read(self, request_id: str) -> dict:
        snapshot = self.snapshot
        try:
            configured = self.configured_read_service.read_controller()
        except SettingsError as error:
            if error.code != "settings_store_unavailable":
                raise
            # An adopted immutable effective snapshot survives request-time Store loss.
            configured = None
        else:
            if not isinstance(configured, dict) or not configured:
                raise ValueError("configured Controller projection unavailable")
        generation = configured["configured_generation"] if configured else None

        def value(label, kind, effective_value, source):
            return {"display_label": label, "value_type": kind,
                    "effective_value": effective_value, "effective_source": source}

        fields = {}
        for name, key, label, kind in (
            ("controller_url", "OMADA_URL", "Controller URL", "url"),
            ("controller_id", "OMADA_ID", "Controller ID", "string"),
            ("client_id", "OMADA_CLIENT_ID", "Client / Application ID", "string"),
        ):
            item = value(label, kind, getattr(snapshot, name), getattr(snapshot, name + "_source"))
            current = configured["fields"][key] if configured else {}
            pending = (configured is not None and generation != snapshot.effective_generation
                       and (current["configured_value"], current["configured_source"]) != (item["effective_value"], item["effective_source"]))
            item.update(setting_key=key, editable=True, read_only_reason=None,
                persisted_override_value=current.get("persisted_override_value"),
                configured_value=current.get("configured_value"), configured_source=current.get("configured_source"),
                pending_value=current.get("configured_value") if pending else None,
                pending_source=current.get("configured_source") if pending else None,
                apply_requirement="main_service_restart", activation_target="captive-portal.service",
                consumer_state="active", validation={"type": "string", "required": True},
                last_changed_at=current.get("last_changed_at"), last_changed_by=current.get("last_changed_by"))
            fields[name] = item
        secret_metadata = {"configured_presence": None, "configured_source": None,
                           "persisted_secret_override_present": None, "pending_replacement": None,
                           "secret_store_state": "unavailable"}
        if configured and self.secret_metadata_service is not None:
            source = "environment" if CONTROLLER_SECRET_DEFINITION.key in self.configured_read_service.environment_names else "repository_default"
            try:
                secret_metadata = self.secret_metadata_service.metadata(generation, snapshot.effective_generation, source)
            except SettingsError as error:
                if error.code != "settings_store_unavailable":
                    raise
                return self._effective_only(request_id)
        fields["client_secret"] = {"display_label": "Client Secret", "value_type": "secret_write_only",
            "management_mode": "write_only", "effective_presence": snapshot.client_secret_presence,
            "effective_source": snapshot.client_secret_source, **secret_metadata,
            "apply_requirement": CONTROLLER_SECRET_DEFINITION.apply_requirement,
            "activation_target": CONTROLLER_SECRET_DEFINITION.activation_target}
        fields["tls_certificate_verification"] = value("TLS certificate verification", "boolean",
            snapshot.tls_certificate_verification, snapshot.tls_certificate_verification_source)
        fields["tls_certificate_verification"].update(editable=False, read_only_reason="deployment_controlled")
        return {
            "api_version": "admin.settings.controller.v3",
            "request_id": request_id,
            "scope": {"type": "global"},
            "resource": {"type": "omada_controller", "scope": "installation"},
            "management_mode": "hybrid",
            "configuration_state": "configured",
            "store_state": "available" if configured else "unavailable",
            "mutation_available": configured is not None,
            "secret_mutation_available": configured is not None and secret_metadata["secret_store_state"] == "available",
            "configured_generation": generation,
            "effective_generation": snapshot.effective_generation,
            "activation_state": configured["activation_state"] if configured else None,
            "restart_required": configured["restart_required"] if configured else None,
            "pending_controller_setting_count": sum(item.get("pending_value") is not None for item in fields.values()) + int(secret_metadata["pending_replacement"] is True) if configured else None,
            "fields": fields,
        }

    def _effective_only(self, request_id):
        class Unavailable:
            def read_controller(self):
                raise SettingsError("settings_store_unavailable")
        return ControllerConfigurationReadService(self.snapshot, Unavailable()).read(request_id)
