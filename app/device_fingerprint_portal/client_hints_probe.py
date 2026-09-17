"""Default-off, one-shot Client Hints research probe for guarded portal entries.

No raw high-entropy header enters state, telemetry, recorder, or Task-03 V1.
The probe cannot influence authorization, navigation, or response status/body.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.common.mac import format_mac_hyphen

from .telemetry import safe_emit


ACCEPT_CH = "Sec-CH-UA-Model, Sec-CH-UA-Platform-Version, Sec-CH-UA-Form-Factors"
CLEAR_CLIENT_HINTS = '"clientHints"'
_HEADERS = ("Sec-CH-UA-Model", "Sec-CH-UA-Platform-Version", "Sec-CH-UA-Form-Factors")
_SUBTYPES = frozenset({"omada_external_portal", "capport_login"})
_MODEL = re.compile(r'"([0-9A-Za-z][0-9A-Za-z ._()+\-]{0,63})"')
_VERSION = re.compile(r'"(0|[1-9][0-9]{0,2})(?:\.[0-9]{1,3}){1,3}"')
_FACTOR = re.compile(r'[ \t]*"([A-Za-z]{1,16})"[ \t]*')
_MAC_LIKE = re.compile(r'(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}')
_UUID_LIKE = re.compile(r'[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}')
_MODEL_FAMILIES = (
    (re.compile(r'Pixel(?: [0-9]+(?: Pro|a| XL| Fold)?)?', re.I), "pixel"),
    (re.compile(r'(?:Samsung )?Galaxy(?: [A-Za-z0-9 +\-]+)?', re.I), "samsung_galaxy"),
    (re.compile(r'SM-[A-Za-z0-9]+', re.I), "samsung_galaxy"),
    (re.compile(r'(?:Redmi|Xiaomi)(?: [A-Za-z0-9 +\-]+)?', re.I), "xiaomi"),
    (re.compile(r'OnePlus(?: [A-Za-z0-9 +\-]+)?', re.I), "oneplus"),
    (re.compile(r'(?:Moto|Motorola)(?: [A-Za-z0-9 +\-]+)?', re.I), "motorola"),
)


@dataclass(frozen=True, slots=True)
class ProbeConfig:
    enabled: bool
    ttl_seconds: int | None = None
    max_entries: int | None = None
    output_path: str | None = None


def probe_config_from_env(env: Mapping[str, str] | None = None) -> ProbeConfig:
    values = os.environ if env is None else env
    enabled = values.get("DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_ENABLED", "false")
    if not isinstance(enabled, str) or enabled.strip().lower() not in {"true", "false"}:
        raise ValueError("Invalid Client Hints probe enablement")
    if enabled.strip().lower() == "false":
        return ProbeConfig(False)

    def positive(name: str, maximum: int) -> int:
        raw = values.get(name)
        if not isinstance(raw, str) or re.fullmatch(r"[1-9][0-9]*", raw) is None:
            raise ValueError(f"Invalid required Client Hints probe setting: {name}")
        number = int(raw)
        if number > maximum:
            raise ValueError(f"Client Hints probe setting out of range: {name}")
        return number

    ttl = positive("DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_TTL_SECONDS", 3600)
    maximum = positive("DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_MAX_ENTRIES", 100000)
    path = values.get("DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_OUTPUT_PATH")
    if (not isinstance(path, str) or not path or "\x00" in path
            or not Path(path).is_absolute() or Path(path).is_dir()):
        raise ValueError("Invalid required Client Hints probe output path")
    return ProbeConfig(True, ttl, maximum, path)


@dataclass(frozen=True, slots=True)
class PortalClientHintsProbeObservation:
    source_subtype: str
    model_header_present: bool
    model_normalization_state: str
    normalized_model_family_candidate: str | None
    platform_version_header_present: bool
    platform_version_normalization_state: str
    normalized_platform_version_major_candidate: int | None
    form_factors_header_present: bool
    form_factors_normalization_state: str
    normalized_form_factors_candidate: tuple[str, ...] | None
    lifecycle_result: str


def _model(value: str | None) -> tuple[str, str | None]:
    if value is None:
        return "ABSENT", None
    if len(value) > 128 or _MODEL.fullmatch(value) is None:
        return "UNUSABLE", None
    candidate = re.sub(r"[ \t]+", " ", _MODEL.fullmatch(value).group(1)).strip()
    if (not candidate or len(candidate) > 64 or _MAC_LIKE.search(candidate)
            or _UUID_LIKE.search(candidate) or re.search(r"\bBuild[/ _-]", candidate, re.I)):
        return "UNUSABLE", None
    # Only bounded coarse families leave request memory; never an arbitrary
    # device name or an uncontrolled raw model fragment.
    for pattern, family in _MODEL_FAMILIES:
        if pattern.fullmatch(candidate):
            return "NORMALIZED", family
    return "UNUSABLE", None


def _platform_version(value: str | None) -> tuple[str, int | None]:
    if value is None:
        return "ABSENT", None
    if len(value) > 64:
        return "UNUSABLE", None
    match = _VERSION.fullmatch(value)
    return ("NORMALIZED", int(match.group(1))) if match else ("UNUSABLE", None)


def _form_factors(value: str | None) -> tuple[str, tuple[str, ...] | None]:
    if value is None:
        return "ABSENT", None
    if not value or len(value) > 128:
        return "UNUSABLE", None
    factors: set[str] = set()
    parts = value.split(",")
    if not 1 <= len(parts) <= 8:
        return "UNUSABLE", None
    for part in parts:
        match = _FACTOR.fullmatch(part)
        if match is None or match.group(1).lower() not in {"mobile", "tablet", "desktop"}:
            return "UNUSABLE", None
        factors.add(match.group(1).lower())
    return "NORMALIZED", tuple(sorted(factors))


def normalize_candidate_headers(
    headers: Mapping[str, Any], *, source_subtype: str,
) -> PortalClientHintsProbeObservation:
    if source_subtype not in _SUBTYPES:
        raise ValueError("Unsupported portal entry subtype")
    # No raw value survives this function, including in exceptions.
    values = [headers.get(name) for name in _HEADERS]
    values = [item if isinstance(item, str) else "" if item is not None else None for item in values]
    model_state, model = _model(values[0])
    version_state, version = _platform_version(values[1])
    factors_state, factors = _form_factors(values[2])
    return PortalClientHintsProbeObservation(
        source_subtype, values[0] is not None, model_state, model,
        values[1] is not None, version_state, version,
        values[2] is not None, factors_state, factors, "OBSERVED",
    )


class SanitizedProbeRecorder:
    """Append only bounded, schema-controlled semantic records to an explicit path."""

    def __init__(self, output_path: str) -> None:
        self.output_path = output_path
        self._lock = threading.Lock()

    def record(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=True, allow_nan=False,
                          sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
        if len(line) > 2048:
            raise ValueError("Sanitized probe record exceeded bound")
        with self._lock:
            fd = os.open(self.output_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                if os.write(fd, line) != len(line):
                    raise OSError("Short sanitized probe write")
            finally:
                os.close(fd)


class PortalClientHintsProbe:
    def __init__(
        self, config: ProbeConfig, *, recorder: Any = None, telemetry: Any = None,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if (not config.enabled or type(config.ttl_seconds) is not int
                or not 1 <= config.ttl_seconds <= 3600
                or type(config.max_entries) is not int
                or not 1 <= config.max_entries <= 100000
                or not isinstance(config.output_path, str)
                or not Path(config.output_path).is_absolute()):
            raise ValueError("Explicit enabled probe configuration required")
        self._config = config
        self._recorder = recorder if recorder is not None else SanitizedProbeRecorder(config.output_path)
        self._telemetry = telemetry
        self._monotonic = monotonic
        self._now = now
        self._lock = threading.Lock()
        self._pending: dict[tuple[str, str, str], float] = {}
        # Terminal tombstones prevent an absent-hints result from immediately
        # starting a new negotiation on the next natural portal visit.
        self._terminal: dict[tuple[str, str, str], float] = {}

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    @property
    def lifecycle_entry_count(self) -> int:
        with self._lock:
            return len(self._pending) + len(self._terminal)

    def _record(self, event_type: str, source_subtype: str,
                observation: PortalClientHintsProbeObservation | None,
                v1_candidate: Any = None) -> None:
        try:
            digest = None
            if v1_candidate is not None:
                # The V1 extractor already produced this bounded canonical semantic
                # payload. Raw UA / Client Hints never enter the hash input.
                encoded = json.dumps(v1_candidate.payload, ensure_ascii=True, allow_nan=False,
                                     sort_keys=True, separators=(",", ":")).encode("ascii")
                digest = hashlib.sha256(encoded).hexdigest()
            event = {
                "event_type": event_type,
                "observed_at": self._now().astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "source_subtype": source_subtype,
                "observation": asdict(observation) if observation is not None else None,
                "v1_semantic_digest": digest,
            }
            self._recorder.record(event)
        except Exception:
            # Experiment output is never a portal or Authorization dependency.
            return

    def apply(
        self, *, response: Any, headers: Mapping[str, Any], site_id: str,
        client_mac: str, source_subtype: str, secure: bool,
        v1_candidate: Any = None,
    ) -> None:
        if not secure or source_subtype not in _SUBTYPES:
            return
        if not isinstance(site_id, str) or re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._:-]{0,127}", site_id) is None:
            return
        try:
            key = (site_id, format_mac_hyphen(client_mac), source_subtype)
        except (TypeError, ValueError):
            return
        instant = self._monotonic()
        observed: PortalClientHintsProbeObservation | None = None
        action = None
        with self._lock:
            expired = [item for item, deadline in self._pending.items() if instant >= deadline]
            for item in expired:
                del self._pending[item]
            for item, deadline in tuple(self._terminal.items()):
                if instant >= deadline:
                    del self._terminal[item]
            if key in expired:
                action = "EXPIRED"
            elif key in self._pending:
                del self._pending[key]
                self._terminal[key] = instant + self._config.ttl_seconds
                action = "CONSUMED"
            elif any(name in headers for name in _HEADERS):
                if key in self._terminal or len(self._pending) + len(self._terminal) < self._config.max_entries:
                    self._terminal[key] = instant + self._config.ttl_seconds
                action = "UNSOLICITED"
            elif key in self._terminal:
                action = "TERMINAL"
            elif len(self._pending) + len(self._terminal) < self._config.max_entries:
                self._pending[key] = instant + self._config.ttl_seconds
                action = "REQUESTED"
            else:
                action = "CAPACITY_REJECTED"
        if action == "REQUESTED":
            response.headers["Accept-CH"] = ACCEPT_CH
            safe_emit(self._telemetry, "probe_requested")
            return
        if action == "CAPACITY_REJECTED":
            safe_emit(self._telemetry, "probe_capacity_rejected")
            return
        if action == "EXPIRED":
            safe_emit(self._telemetry, "probe_expired")
            self._record("probe_expired", source_subtype, None)
        if action == "CONSUMED":
            if any(name in headers for name in _HEADERS):
                observed = normalize_candidate_headers(headers, source_subtype=source_subtype)
                safe_emit(self._telemetry, "probe_observed")
                if any(getattr(observed, name) == "UNUSABLE" for name in (
                    "model_normalization_state", "platform_version_normalization_state",
                    "form_factors_normalization_state",
                )):
                    safe_emit(self._telemetry, "probe_normalization_unusable")
                self._record("probe_observed", source_subtype, observed, v1_candidate)
            else:
                safe_emit(self._telemetry, "probe_missing")
                missing = PortalClientHintsProbeObservation(
                    source_subtype, False, "ABSENT", None, False, "ABSENT", None,
                    False, "ABSENT", None, "MISSING",
                )
                self._record("probe_missing", source_subtype, missing, v1_candidate)
        if action in {"EXPIRED", "CONSUMED", "UNSOLICITED"}:
            response.headers["Clear-Site-Data"] = CLEAR_CLIENT_HINTS
            safe_emit(self._telemetry, "probe_teardown_emitted")
