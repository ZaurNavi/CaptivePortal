"""Read projections and atomic global mutation, with no activation authority."""
import hashlib
import json
from dataclasses import asdict
from .definitions import SettingsDefinitionRegistry
from .models import API_VERSION, SettingsError, SettingReadModelV1, SettingsMutationChange, SettingsMutationResult, utc_now
from .repository import canonical_json
from .resolver import resolve_settings
from .validation import SettingsValidationService
from .value_validation import validate_setting_value
from app.portal_presentation import portal_validation_metadata


def parse_changes(raw, registry=None, domain="general"):
    registry = registry or SettingsDefinitionRegistry()

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate member")
            result[key] = value
        return result

    def invalid_constant(_value):
        raise ValueError("non-JSON constant")

    try:
        document = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
        if type(document) is not dict or set(document) != {"changes"}:
            raise ValueError()
        changes = document["changes"]
        if domain not in ("general", "controller", "portal") or type(changes) is not list or not 1 <= len(changes) <= {"general": 64, "controller": 3, "portal": 14}[domain]:
            raise ValueError()
        seen, result = set(), []
        for change in changes:
            if type(change) is not dict:
                raise ValueError()
            key, operation = change.get("key"), change.get("operation")
            definition = registry.get(key) if type(key) is str else None
            if definition is None or definition.domain != domain or key in seen:
                raise ValueError()
            seen.add(key)
            if operation == "set" and set(change) == {"key", "operation", "value"} and type(change["value"]) is (int if domain == "general" else str):
                value = change["value"]
                if definition.value_type == "string":
                    value = validate_setting_value(definition, value)
                result.append(SettingsMutationChange(key, operation, value))
            elif operation == "clear_override" and set(change) == {"key", "operation"}:
                result.append(SettingsMutationChange(key, operation))
            else:
                raise ValueError()
        return tuple(sorted(result, key=lambda item: item.key))
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise SettingsError("invalid_request", 400) from exc


class SettingsReadService:
    def __init__(self, repository, base_settings, explicit_environment_names, startup_snapshot, registry=None):
        self.repository = repository
        self.base_settings = startup_snapshot.values if startup_snapshot.generation_id is None else base_settings
        self.environment_names = frozenset(explicit_environment_names)
        self.startup_snapshot = startup_snapshot
        self.registry = registry or SettingsDefinitionRegistry()
        self._adopted = False

    def project(self, db, generation=None):
        generation = self.repository.head(db) if generation is None else generation
        snapshot = resolve_settings(self.base_settings, self.environment_names, self.repository.overrides(db, generation), generation, self.registry)
        effective = self.repository.effective(db)
        trustworthy = self._adopted and effective == self.startup_snapshot.generation_id
        latest_result = self.repository.latest_activation_result(db, generation)
        activation = "runtime_unavailable" if not trustworthy else (
            "active" if generation == effective else "activation_failed" if latest_result == "failed" else "pending_main_restart"
        )
        settings = []
        for item in self.registry.for_domain("general"):
            enabled = self.startup_snapshot.values.get(item.consumer_enable_settings_dict_key, "false") in (True, "true")
            consumer = ("active" if enabled else "consumer_disabled") if trustworthy else None
            audit = self.repository.latest_setting_audit(db, item.key, generation)
            value = snapshot.values[item.settings_dict_key]
            settings.append(asdict(SettingReadModelV1(
                item.key, item.display_label, item.description, item.group, item.value_type,
                item.scope_type, None, item.editable, None, item.secret_class,
                item.repository_default_value, snapshot.base_source_by_key[item.key],
                snapshot.base_value_by_key[item.key], snapshot.persisted_override_by_key[item.key],
                value, self.startup_snapshot.values[item.settings_dict_key] if trustworthy and enabled else None,
                value if generation != effective else None, generation, effective, activation,
                item.apply_requirement, item.activation_target, consumer,
                {"type": "integer", "min": item.min_value, "max": item.max_value},
                audit["timestamp_utc"] if audit else None,
                {"principal_type": audit["principal_type"], "principal_name": audit["principal_name"]} if audit else None,
            )))
        return {
            "api_version": API_VERSION, "scope": {"type": "global"}, "store_state": "available",
            "configured_generation": generation, "effective_generation": effective,
            "etag": f'"settings-g{generation}"', "restart_required": generation != effective,
            "pending_setting_count": len(settings) if generation != effective else 0,
            "settings": settings,
        }

    def read(self):
        with self.repository.transaction() as db:
            return self.project(db)

    def read_controller(self):
        """Safe configured-domain boundary; excludes the secret-bearing mapping."""
        with self.repository.transaction() as db:
            generation = self.repository.head(db)
            overrides = self.repository.overrides(db, generation)
            snapshot = resolve_settings(self.base_settings, self.environment_names, overrides, generation, self.registry)
            effective = self.repository.effective(db)
            trustworthy = self._adopted and effective == self.startup_snapshot.generation_id
            latest = self.repository.latest_activation_result(db, generation)
            activation = "runtime_unavailable" if not trustworthy else (
                "active" if generation == effective else "activation_failed" if latest == "failed" else "pending_main_restart")
            fields = {}
            for item in self.registry.for_domain("controller"):
                audit = self.repository.latest_setting_audit(db, item.key, generation)
                fields[item.key] = {
                    "persisted_override_value": overrides.get(item.key),
                    "configured_value": snapshot.values[item.settings_dict_key],
                    "configured_source": "persisted_override" if item.key in overrides else snapshot.base_source_by_key[item.key],
                    "last_changed_at": audit["timestamp_utc"] if audit else None,
                    "last_changed_by": {"principal_type": audit["principal_type"], "principal_name": audit["principal_name"]} if audit else None,
                }
            return {"configured_generation": generation, "activation_state": activation,
                    "restart_required": generation != effective, "fields": fields}

    def read_portal(self):
        with self.repository.transaction() as db:
            generation = self.repository.head(db)
            snapshot = resolve_settings(self.base_settings, self.environment_names,
                self.repository.overrides(db, generation), generation, self.registry)
            effective = self.repository.effective(db)
            trustworthy = self._adopted and effective == self.startup_snapshot.generation_id
            latest = self.repository.latest_activation_result(db, generation)
            activation = "runtime_unavailable" if not trustworthy else (
                "active" if generation == effective else "activation_failed" if latest == "failed" else "pending_main_restart")
            settings = []
            for item in self.registry.for_domain("portal"):
                audit = self.repository.latest_setting_audit(db, item.key, generation)
                configured = snapshot.values[item.settings_dict_key]
                adopted = self.startup_snapshot.values.get(item.settings_dict_key, item.repository_default_value) if trustworthy else None
                settings.append({
                    "key": item.key, "display_label": item.display_label, "description": item.description,
                    "group": item.group, "value_type": item.value_type, "presentation_type": item.presentation_type,
                    "scope_type": item.scope_type, "scope_id": None, "editable": item.editable,
                    "secret_class": item.secret_class, "default_value": item.repository_default_value,
                    "base_source": snapshot.base_source_by_key[item.key], "base_value": snapshot.base_value_by_key[item.key],
                    "persisted_override_value": snapshot.persisted_override_by_key[item.key],
                    "configured_value": configured, "effective_value": adopted,
                    "pending_value": configured if trustworthy and generation != effective and configured != adopted else None,
                    "configured_generation": generation, "effective_generation": effective, "activation_state": activation,
                    "apply_requirement": item.apply_requirement, "activation_target": item.activation_target,
                    "validation": portal_validation_metadata(item.key), "last_changed_at": audit["timestamp_utc"] if audit else None,
                    "last_changed_by": {"principal_type": audit["principal_type"], "principal_name": audit["principal_name"]} if audit else None,
                })
            return {"api_version": "admin.settings.portal.v1", "scope": {"type": "global"}, "store_state": "available",
                    "configured_generation": generation, "effective_generation": effective, "etag": f'"settings-g{generation}"',
                    "restart_required": generation != effective,
                    "pending_setting_count": sum(item["pending_value"] is not None for item in settings), "settings": settings}


class SettingsMutationService:
    def __init__(self, repository, read_service, validation=None):
        self.repository, self.read_service = repository, read_service
        self.validation = validation or SettingsValidationService(read_service.registry)
        self.secret_repository = None

    @staticmethod
    def _replay(existing, payload_hash):
        if existing["request_fingerprint_kind"] != "sha256_canonical_json_v1" or existing["request_fingerprint"] != payload_hash:
            raise SettingsError("idempotency_conflict", 409)
        return SettingsMutationResult(existing["result_http_status"], json.loads(existing["result_response_json"]))

    def mutate(self, raw_body, *, principal, source_ip, request_id, idempotency_key, expected_generation, domain="general"):
        changes = parse_changes(raw_body, self.read_service.registry, domain)
        canonical = {"changes": [
            {"key": change.key, "operation": change.operation, **({"value": change.value} if change.operation == "set" else {})}
            for change in changes
        ]}
        payload_hash = hashlib.sha256(canonical_json(canonical).encode("utf-8")).hexdigest()
        domain_args = (domain,) if domain != "general" else ()
        existing = self.repository.lookup_idempotency(principal, idempotency_key, *domain_args)
        if existing:
            return self._replay(existing, payload_hash)
        with self.repository.transaction(write=True) as db:
            # Mandatory re-check: another writer may have accepted this identity.
            existing = self.repository.idempotency(db, principal, idempotency_key, *domain_args)
            if existing:
                return self._replay(existing, payload_hash)
            parent = self.repository.head(db)
            if expected_generation != parent:
                raise SettingsError("stale_generation", 412)
            previous = self.repository.overrides(db, parent)
            overrides = dict(previous)
            for change in changes:
                if change.operation == "set":
                    overrides[change.key] = change.value
                else:
                    overrides.pop(change.key, None)
            try:
                current = resolve_settings(self.read_service.base_settings, self.read_service.environment_names, previous, parent, self.read_service.registry)
                candidate = resolve_settings(self.read_service.base_settings, self.read_service.environment_names, overrides, parent, self.read_service.registry)
            except SettingsError as error:
                controller_keys = {item.key for item in self.read_service.registry.for_domain("controller")}
                if domain == "portal" and error.code == "validation_failed" and any(
                    detail.get("key") in controller_keys for detail in error.details
                ):
                    raise SettingsError("validation_failed", 422, ({"key": None, "reason": "controller_prerequisite_invalid"},)) from None
                raise
            resolution = None
            if domain != "portal" and self.secret_repository is not None:
                try:
                    resolution = self.secret_repository.resolve(parent, self.read_service.base_settings, self.read_service.environment_names)
                except SettingsError as error:
                    if error.code != "controller_secret_configuration_invalid":
                        raise
                    raise SettingsError("validation_failed", 422, ({"key": None, "reason": "controller_prerequisite_invalid"},)) from None
            if domain == "portal":
                self.validation.validate_portal_candidate(candidate)
            else:
                self.validation.validate(candidate, secret_resolution=resolution)
            changed = previous != overrides
            generation = parent
            if changed:
                now = utc_now()
                generation = self.repository.create_generation(db, parent=parent, principal=principal,
                    request_id=request_id, created_at=now, overrides=overrides)
                for change in changes:
                    if previous.get(change.key) == overrides.get(change.key):
                        continue
                    definition = self.read_service.registry.get(change.key)
                    self.repository.append_mutation_audit(db, generation=generation, parent=parent,
                        principal=principal, source_ip=source_ip, request_id=request_id,
                        idempotency_key=idempotency_key, timestamp=now, key=change.key, operation=change.operation,
                        previous_override=previous.get(change.key), new_override=overrides.get(change.key),
                        previous_value=current.values[definition.settings_dict_key],
                        new_value=candidate.values[definition.settings_dict_key],
                        apply_requirement=definition.apply_requirement, activation_target=definition.activation_target,
                        domain=domain, value_type=definition.value_type)
            if domain in ("controller", "portal"):
                effective = self.repository.effective(db)
                latest = self.repository.latest_activation_result(db, generation)
                activation = "pending_main_restart" if changed else (
                    "runtime_unavailable" if not self.read_service._adopted else "active" if generation == effective
                    else "activation_failed" if latest == "failed" else "pending_main_restart")
                body = {"api_version": f"admin.settings.{domain}.mutation.v1", "request_id": request_id,
                        "scope": {"type": "global"}, "resource": {"type": "guest_portal" if domain == "portal" else "omada_controller", "scope": "installation"},
                        "changed": changed, "changed_keys": [item.key for item in changes if previous.get(item.key) != overrides.get(item.key)],
                        "configured_generation": generation, "effective_generation": effective,
                        "activation_state": activation, "restart_required": generation != effective}
            else:
                projection = self.read_service.project(db, generation)
                body = {key: projection[key] for key in ("api_version", "scope", "configured_generation", "effective_generation", "restart_required", "settings")}
                body.update(request_id=request_id, changed=changed,
                            activation_state="pending_main_restart" if changed else projection["settings"][0]["activation_state"])
            status = 201 if changed else 200
            self.repository.save_idempotency(db, principal, idempotency_key, payload_hash, status, body, *domain_args)
            return SettingsMutationResult(status, body)
