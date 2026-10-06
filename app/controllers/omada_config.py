"""Canonical startup Omada configuration and its separate public projection."""

from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlsplit

from app.exceptions import ConfigurationError


_REQUIRED = (
    ("OMADA_URL", "omada_url", "controller_url"),
    ("OMADA_ID", "omada_id", "controller_id"),
    ("OMADA_CLIENT_ID", "client_id", "client_id"),
    ("OMADA_CLIENT_SECRET", "client_secret", "client_secret"),
)


def _valid_base_url(value: str) -> bool:
    if any(character.isspace() for character in value) or "?" in value or "#" in value:
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
        and parsed.hostname is not None
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.netloc.endswith(":")
        and port != 0
    )


@dataclass(frozen=True, slots=True)
class OmadaControllerRuntimeConfig:
    controller_url: str
    controller_id: str
    client_id: str
    client_secret: str = field(repr=False)
    verify_ssl: bool

    def __post_init__(self):
        missing = [external for external, _, attribute in _REQUIRED
                   if not isinstance(getattr(self, attribute), str)
                   or not getattr(self, attribute).strip()]
        if missing:
            raise ConfigurationError("Missing required configuration: " + ", ".join(missing))
        for _, _, attribute in _REQUIRED:
            object.__setattr__(self, attribute, getattr(self, attribute).strip())
        if not _valid_base_url(self.controller_url):
            raise ConfigurationError("Invalid configuration: OMADA_URL")
        if self.controller_url.endswith("/"):
            object.__setattr__(self, "controller_url", self.controller_url[:-1])


def build_omada_runtime_config(settings: Mapping[str, Any]) -> OmadaControllerRuntimeConfig:
    """Resolve only from the caller's already-adopted mapping, with no I/O."""
    return OmadaControllerRuntimeConfig(
        **{attribute: settings.get(internal) for _, internal, attribute in _REQUIRED},
        verify_ssl=settings["verify_ssl"],
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


def public_omada_snapshot(
    runtime_config: OmadaControllerRuntimeConfig,
    explicit_environment_names: frozenset[str],
) -> OmadaControllerPublicConfigSnapshot:
    """Project the same config used by the provider; never expose secret material."""
    def source(name):
        return "environment" if name in explicit_environment_names else "repository_default"

    return OmadaControllerPublicConfigSnapshot(
        controller_url=runtime_config.controller_url,
        controller_url_source=source("OMADA_URL"),
        controller_id=runtime_config.controller_id,
        controller_id_source=source("OMADA_ID"),
        client_id=runtime_config.client_id,
        client_id_source=source("OMADA_CLIENT_ID"),
        client_secret_presence="configured" if runtime_config.client_secret else "not_configured",
        client_secret_source=source("OMADA_CLIENT_SECRET"),
        tls_certificate_verification=runtime_config.verify_ssl,
        # VERIFY_SSL is a repository constant, not an environment binding.
        tls_certificate_verification_source="repository_default",
    )
