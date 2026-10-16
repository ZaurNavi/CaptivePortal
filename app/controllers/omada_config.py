"""Canonical startup Omada configuration and its separate public projection."""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from app.exceptions import ConfigurationError


_REQUIRED = (
    ("OMADA_URL", "omada_url", "controller_url"),
    ("OMADA_ID", "omada_id", "controller_id"),
    ("OMADA_CLIENT_ID", "client_id", "client_id"),
    ("OMADA_CLIENT_SECRET", "client_secret", "client_secret"),
)

CANONICAL_HTTPS_ORIGIN = "https://Omada:8043"


@dataclass(frozen=True, slots=True)
class OmadaTlsPolicy:
    """Pure startup policy from adopted settings; certificate I/O belongs to transport."""
    canonical_https_origin: str
    trust_anchor_path: str = field(repr=False)
    trust_anchor_sha256: str = field(repr=False)
    verification_mode: str = "strict"

    def __post_init__(self):
        if not _valid_base_url(self.canonical_https_origin) or self.verification_mode != "strict":
            raise ConfigurationError("Invalid Omada strict TLS origin/policy")
        if not isinstance(self.trust_anchor_path, str) or not Path(self.trust_anchor_path).is_absolute():
            raise ConfigurationError("Invalid configuration: OMADA_TLS_TRUST_ANCHOR_PATH")
        if not isinstance(self.trust_anchor_sha256, str) or not re.fullmatch(
                r"[0-9a-fA-F]{64}", self.trust_anchor_sha256):
            raise ConfigurationError("Invalid configuration: OMADA_TLS_TRUST_ANCHOR_SHA256")
        object.__setattr__(self, "canonical_https_origin", CANONICAL_HTTPS_ORIGIN)
        object.__setattr__(self, "trust_anchor_sha256", self.trust_anchor_sha256.lower())


def _valid_base_url(value: str) -> bool:
    if not isinstance(value, str):
        return False
    if any(character.isspace() for character in value) or "?" in value or "#" in value:
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.hostname is not None and parsed.hostname.lower() == "omada"
        and parsed.netloc.lower() == "omada:8043"
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.netloc.endswith(":")
        and port == 8043
    )


def normalize_controller_setting(key: str, value: Any) -> str:
    """The same local semantic boundary for Settings and runtime composition."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError("Missing required configuration: " + key)
    value = value.strip()
    if key == "OMADA_URL":
        if not _valid_base_url(value):
            raise ConfigurationError("Invalid configuration: OMADA_URL")
        return CANONICAL_HTTPS_ORIGIN
    return value


@dataclass(frozen=True, slots=True)
class OmadaControllerRuntimeConfig:
    controller_url: str
    controller_id: str
    client_id: str
    client_secret: str = field(repr=False)
    verify_ssl: bool
    tls_policy: OmadaTlsPolicy | None = field(default=None, repr=False)

    def __post_init__(self):
        missing = [external for external, _, attribute in _REQUIRED
                   if not isinstance(getattr(self, attribute), str)
                   or not getattr(self, attribute).strip()]
        if missing:
            raise ConfigurationError("Missing required configuration: " + ", ".join(missing))
        for _, _, attribute in _REQUIRED:
            key = next(key for key, _, name in _REQUIRED if name == attribute)
            object.__setattr__(self, attribute, normalize_controller_setting(key, getattr(self, attribute)))
        if self.verify_ssl is not True or not isinstance(self.tls_policy, OmadaTlsPolicy):
            raise ConfigurationError("Missing or invalid Omada strict TLS policy")
        if self.controller_url != self.tls_policy.canonical_https_origin:
            raise ConfigurationError("Invalid Omada strict TLS origin/policy")


def build_omada_runtime_config(settings: Mapping[str, Any], secret_resolution=None) -> OmadaControllerRuntimeConfig:
    """Resolve only from the caller's already-adopted mapping, with no I/O."""
    required = {attribute: secret_resolution.value if attribute == "client_secret" and secret_resolution is not None
                else settings.get(internal) for _, internal, attribute in _REQUIRED}
    missing = [external for external, _, attribute in _REQUIRED
               if not isinstance(required[attribute], str) or not required[attribute].strip()]
    if missing:
        raise ConfigurationError("Missing required configuration: " + ", ".join(missing))
    origin = normalize_controller_setting("OMADA_URL", required["controller_url"])
    return OmadaControllerRuntimeConfig(
        **required,
        verify_ssl=settings["verify_ssl"],
        tls_policy=OmadaTlsPolicy(
            canonical_https_origin=origin,
            trust_anchor_path=settings.get("omada_tls_trust_anchor_path", ""),
            trust_anchor_sha256=settings.get("omada_tls_trust_anchor_sha256", ""),
        ),
    )


@dataclass(frozen=True, slots=True)
class OmadaControllerPublicConfigSnapshot:
    controller_url: str
    controller_url_source: str
    controller_id: str
    controller_id_source: str
    client_id: str
    client_id_source: str
    client_secret_presence: str
    client_secret_source: str
    tls_certificate_verification: bool
    tls_certificate_verification_source: str
    effective_generation: int | None = None
    tls_verification_mode: str = "unavailable"
    tls_trust_policy: str = "unavailable"
    tls_trust_anchor_source: str = "repository_default"
    tls_certificate_status: str = "unavailable"


def public_omada_snapshot(
    runtime_config: OmadaControllerRuntimeConfig,
    explicit_environment_names: frozenset[str],
    settings_snapshot=None,
    secret_resolution=None,
) -> OmadaControllerPublicConfigSnapshot:
    """Project the same config used by the provider; never expose secret material."""
    def source(name):
        if settings_snapshot is not None and settings_snapshot.generation_id is not None and name in settings_snapshot.base_source_by_key:
            return ("persisted_override" if settings_snapshot.persisted_override_by_key[name] is not None
                    else settings_snapshot.base_source_by_key[name])
        return "environment" if name in explicit_environment_names else "repository_default"

    return OmadaControllerPublicConfigSnapshot(
        controller_url=runtime_config.controller_url,
        controller_url_source=source("OMADA_URL"),
        controller_id=runtime_config.controller_id,
        controller_id_source=source("OMADA_ID"),
        client_id=runtime_config.client_id,
        client_id_source=source("OMADA_CLIENT_ID"),
        client_secret_presence="configured" if runtime_config.client_secret else "not_configured",
        client_secret_source=secret_resolution.source if secret_resolution is not None else source("OMADA_CLIENT_SECRET"),
        tls_certificate_verification=runtime_config.verify_ssl,
        # VERIFY_SSL is a repository constant, not an environment binding.
        tls_certificate_verification_source="repository_default",
        effective_generation=settings_snapshot.generation_id if settings_snapshot is not None else None,
        tls_verification_mode=runtime_config.tls_policy.verification_mode,
        tls_trust_policy="independently_approved_self_signed_leaf",
        tls_trust_anchor_source=("environment" if {
            "OMADA_TLS_TRUST_ANCHOR_PATH", "OMADA_TLS_TRUST_ANCHOR_SHA256"
        }.issubset(explicit_environment_names) else "repository_default"),
        # A configuration projection is not a current peer/health attestation.
        tls_certificate_status="verification_required_on_every_connection",
    )
