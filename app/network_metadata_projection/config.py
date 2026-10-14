"""Default-OFF independent configuration; upstream paths are read-only."""
import hashlib
import ipaddress
import os
import re
from dataclasses import asdict, fields
from pathlib import Path
from app.network_metadata.canonical import ni01_canonical_json
from app.network_metadata.config import make_capture_scope_binding
from app.network_metadata.validation import strict_json, ni_timestamp
from .models import ProjectionConflict
from .models import ProjectionConfig, ProjectionValidationError

PREFIX = "NETWORK_METADATA_PROJECTION_"


class ScopeAdmission:
    """Closed operator admission. Physical placement is attested, not discovered."""
    def __init__(self, encoded):
        try:
            if type(encoded) is not str or len(encoded.encode("utf-8")) > 65536:
                raise ValueError
            value = strict_json(encoded)
            if (type(value) is not dict or set(value) != {"schema_version", "placement_kind", "scopes"}
                    or type(value["schema_version"]) is not int or value["schema_version"] != 1
                    or value["placement_kind"] != "verified_pre_nat_guest_ipv4"
                    or type(value["scopes"]) is not list or not 1 <= len(value["scopes"]) <= 64):
                raise ValueError
            bindings = []
            for entry in value["scopes"]:
                if type(entry) is not dict or set(entry) != {"site_id", "capture_source_id", "network_scope_id",
                        "capture_scope_binding_digest", "ipv4_cidrs", "binding_valid_from_utc"}:
                    raise ValueError
                ni_timestamp(entry["binding_valid_from_utc"], canonical=True)
                binding = make_capture_scope_binding(dict(schema_version=1, site_id=entry["site_id"],
                    capture_source_id=entry["capture_source_id"], network_scope_id=entry["network_scope_id"],
                    ipv4_cidrs=entry["ipv4_cidrs"], valid_from_utc=entry["binding_valid_from_utc"]))
                if (binding.binding_digest != entry["capture_scope_binding_digest"]
                        or list(binding.ipv4_cidrs) != entry["ipv4_cidrs"]
                        or any(ipaddress.IPv4Network(cidr).prefixlen == 0 for cidr in binding.ipv4_cidrs)
                        or any(old.binding_digest == binding.binding_digest
                            or (old.site_id == binding.site_id and old.capture_source_id == binding.capture_source_id
                                and old.network_scope_id == binding.network_scope_id) for old in bindings)):
                    raise ValueError
                bindings.append(binding)
            # One event binding per Site/source/scope, no contradictory overlapping
            # attribution domains in one Site. Different Sites may reuse RFC1918.
            for index, binding in enumerate(bindings):
                for other in bindings[:index]:
                    if binding.site_id == other.site_id and any(ipaddress.IPv4Network(a).overlaps(ipaddress.IPv4Network(b))
                            for a in binding.ipv4_cidrs for b in other.ipv4_cidrs):
                        raise ValueError
            value["scopes"] = sorted(value["scopes"], key=lambda entry: (
                entry["site_id"], entry["capture_source_id"], entry["network_scope_id"]))
            self.canonical = ni01_canonical_json(value).decode("utf-8")
            self.digest = hashlib.sha256(self.canonical.encode("utf-8")).hexdigest()
            self.bindings = tuple(bindings)
        except Exception:
            raise ProjectionConflict("scope_admission_untrusted") from None

    def binding_for(self, source):
        try:
            return self._binding_for(source)
        except Exception:
            raise ProjectionConflict("scope_admission_untrusted") from None

    def _binding_for(self, source):
        matches = [binding for binding in self.bindings if all(getattr(source, name) == getattr(binding, name)
            for name in ("site_id", "capture_source_id", "network_scope_id"))]
        if (len(matches) != 1 or source.network_scope_state != "within_intended_scope"
                or matches[0].binding_digest != source.capture_scope_binding_digest
                or matches[0].ipv4_cidrs != tuple(source.capture_scope_ipv4_cidrs)
                or getattr(source, "binding_valid_from_utc", None) != matches[0].valid_from_utc
                or ni_timestamp(source.event_at, canonical=True) < ni_timestamp(matches[0].valid_from_utc, canonical=True)):
            raise ProjectionConflict("scope_admission_untrusted")
        return matches[0]


def configuration_digest(config):
    values = asdict(config)
    # New OFF fields are absent from the original canonical configuration.
    for name in ("idle_write_reduction_enabled", "checkpoint_opt_enabled", "telemetry_aggregation_enabled"):
        if not values[name]:
            values.pop(name)
    return hashlib.sha256(ni01_canonical_json(values)).hexdigest()


def idle_read_guard_from_env(environ=None):
    """Reader process opt-in; must be enabled together with the writer flag."""
    env = os.environ if environ is None else environ
    value = env.get(PREFIX + "IDLE_WRITE_REDUCTION_ENABLED", "false")
    if type(value) is not str or value not in {"true", "false"}:
        raise ProjectionValidationError()
    return value == "true"


def projection_config_from_env(environ=None):
    env = os.environ if environ is None else environ
    enabled = env.get(PREFIX + "ENABLED", "false")
    if enabled not in {"true", "false"}:
        raise ProjectionValidationError()
    if enabled == "false":
        return ProjectionConfig()
    defaults, values = ProjectionConfig(), {"enabled": True}
    for field in fields(defaults):
        name = field.name
        if name == "enabled":
            continue
        key = {"source_db_path": "NETWORK_METADATA_DB_PATH", "registry_db_path": "VISITOR_REGISTRY_DB_PATH"}.get(name, PREFIX + name.upper())
        default = getattr(defaults, name)
        value = env.get(key, str(default))
        if name == "scope_admission_json":
            value = ScopeAdmission(env.get(key)).canonical
        elif type(default) is bool:
            value = env.get(key, "true" if default else "false")
            if type(value) is not str or value not in {"true", "false"}:
                raise ProjectionValidationError()
            value = value == "true"
        elif name.endswith("db_path"):
            if not isinstance(value, str) or not value or "\0" in value or not Path(value).is_absolute():
                raise ProjectionValidationError()
        else:
            if not isinstance(value, str) or re.fullmatch(r"[0-9]{1,11}", value) is None:
                raise ProjectionValidationError()
            value = int(value)
            if name == "max_db_bytes":
                if not 67108864 <= value <= 68719476736:
                    raise ProjectionValidationError()
            elif value != default:
                # V1 processing values are frozen, not operator-tunable limits.
                raise ProjectionValidationError()
        values[name] = value
    paths = [Path(values[name]).resolve() for name in ("db_path", "source_db_path", "registry_db_path")]
    if len(set(paths)) != len(paths):
        raise ProjectionValidationError()
    return ProjectionConfig(**values)
