#!/usr/bin/env python3
"""
Temporary Pending Session Probe/Cleaner for a 2–3 day field experiment.

Purpose
-------
Observe and safely clear stale unauthorised Omada client sessions while the
production PendingClientSessionCleaner is still under development.

Core behaviour
--------------
- fixed-delay scan every 60 seconds;
- exact SSID Zefer_Parki;
- wireless=true, active=true, authStatus=1, uptime>=120 seconds;
- no global reconnect limit: every distinct eligible MAC may be processed;
- fresh exact-client preflight immediately before reconnect;
- recent portal/auth activity read from auth_telemetry.log protects the MAC;
- per-MAC cooldown: 15 minutes;
- verification GET after 1 second and after an additional 4 seconds;
- strict rotating JSONL journal;
- durable JSON state so cooldown and rejoin classification survive restart;
- refuses to run when the production Pending Session Cleaner is enabled.

Important limitation
--------------------
This is a separate process. It cannot read AuthSessionManager memory directly.
Protection therefore uses the existing JSONL authorization telemetry:
capport.portal_opened, auth.worker_started/completed, auth.session_finished,
auth.retry_* and other auth.* activity. If that journal cannot be read, the
probe fails closed and sends no reconnect commands.
"""

from __future__ import annotations

import argparse
import fcntl
import ipaddress
import json
import logging
import math
import os
import re
import signal
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterable

import requests

try:
    import urllib3
except ImportError:  # pragma: no cover
    urllib3 = None


SCHEMA_VERSION = 1
TOKEN_EXPIRED_ERROR = -44112
PAGE_SIZE = 500
MAX_PAGES = 20
UPTIME_TOLERANCE_SECONDS = 5
MAC_HEX_RE = re.compile(r"^[0-9A-F]{12}$")

DEFAULT_SSID = "Zefer_Parki"
DEFAULT_SCAN_INTERVAL_SECONDS = 60.0
DEFAULT_MIN_UPTIME_SECONDS = 120
DEFAULT_COOLDOWN_SECONDS = 900.0
DEFAULT_PORTAL_GRACE_SECONDS = 90.0
DEFAULT_REQUEST_TIMEOUT_SECONDS = 5.0
DEFAULT_VERIFY_DELAYS_SECONDS = (1.0, 4.0)

DEFAULT_AUTH_LOG_PATH = "/opt/CaptivePortal/logs/auth_telemetry.log"
DEFAULT_JOURNAL_PATH = "/opt/CaptivePortal/logs/pending_session_probe.log"
DEFAULT_STATE_PATH = "/opt/CaptivePortal/data/pending_session_probe_state.json"
DEFAULT_LOCK_PATH = "/opt/CaptivePortal/data/pending_session_probe.lock"

DEFAULT_JOURNAL_MAX_BYTES = 52_428_800
DEFAULT_JOURNAL_BACKUP_COUNT = 10
AUTH_LOG_TAIL_BYTES_PER_FILE = 8 * 1024 * 1024
AUTH_LOG_BACKUP_COUNT = 10

AUTH_START_EVENTS = {
    "auth.worker_started",
    "auth.retry_started",
}
AUTH_FINISH_EVENTS = {
    "auth.worker_completed",
    "auth.worker_exception",
    "auth.session_finished",
    "auth.retry_succeeded",
    "auth.retry_failed",
    "auth.retry_rejected",
}
PORTAL_EVENT = "capport.portal_opened"


class ProbeError(RuntimeError):
    """Controlled configuration, journal or API failure."""


class ControllerError(ProbeError):
    def __init__(self, operation: str, error_code: int, message: str):
        super().__init__(
            f"{operation}: Omada errorCode={error_code}: {message}"
        )
        self.operation = operation
        self.error_code = error_code
        self.controller_message = message


@dataclass(frozen=True)
class Config:
    controller_url: str
    omadac_id: str
    site_id: str
    client_id: str
    client_secret: str
    verify_ssl: bool

    ssid: str
    scan_interval_seconds: float
    min_uptime_seconds: int
    cooldown_seconds: float
    portal_grace_seconds: float
    request_timeout_seconds: float
    verify_delays_seconds: tuple[float, float]

    auth_log_path: Path
    journal_path: Path
    state_path: Path
    lock_path: Path
    journal_max_bytes: int
    journal_backup_count: int
    once: bool


@dataclass(frozen=True)
class ClientState:
    mac: str
    wireless: bool
    active: bool
    auth_status: int
    uptime: int
    ssid: str
    blocked: bool
    ip: str | None
    ap_mac: str | None
    radio_id: int | None


@dataclass
class ResetRecord:
    reset_id: str
    reset_at: str
    reset_epoch: float
    cooldown_until_epoch: float
    uptime_before: int
    client_ip_before: str | None
    ap_mac_before: str | None
    command_outcome: str
    verification_result: str | None
    last_classification: str | None = None
    last_classification_at: str | None = None


@dataclass
class PersistentState:
    schema_version: int = SCHEMA_VERSION
    resets: dict[str, ResetRecord] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthProtection:
    available: bool
    protected: bool
    reason: str
    portal_open: bool
    auth_run_active: bool
    recent_auth_activity: bool
    last_portal_at: str | None = None
    last_auth_at: str | None = None


@dataclass
class AuthTelemetrySnapshot:
    available: bool
    error: str | None = None
    last_portal_epoch: dict[str, float] = field(default_factory=dict)
    last_auth_epoch: dict[str, float] = field(default_factory=dict)
    active_sessions_by_mac: dict[str, set[str]] = field(default_factory=dict)

    def protection(
        self,
        *,
        mac: str,
        now_epoch: float,
        grace_seconds: float,
    ) -> AuthProtection:
        if not self.available:
            return AuthProtection(
                available=False,
                protected=True,
                reason="auth_telemetry_unavailable",
                portal_open=False,
                auth_run_active=False,
                recent_auth_activity=False,
            )

        last_portal = self.last_portal_epoch.get(mac)
        last_auth = self.last_auth_epoch.get(mac)
        portal_recent = (
            last_portal is not None
            and now_epoch - last_portal < grace_seconds
        )
        auth_recent = (
            last_auth is not None
            and now_epoch - last_auth < grace_seconds
        )
        active_run = bool(self.active_sessions_by_mac.get(mac))

        if active_run:
            reason = "active_auth_run"
        elif portal_recent:
            reason = "recent_portal_open"
        elif auth_recent:
            reason = "recent_auth_activity"
        else:
            reason = "not_protected"

        return AuthProtection(
            available=True,
            protected=active_run or portal_recent or auth_recent,
            reason=reason,
            portal_open=portal_recent,
            auth_run_active=active_run,
            recent_auth_activity=auth_recent,
            last_portal_at=(
                epoch_to_timestamp(last_portal)
                if last_portal is not None
                else None
            ),
            last_auth_at=(
                epoch_to_timestamp(last_auth)
                if last_auth is not None
                else None
            ),
        )

    def activity_since(
        self,
        *,
        mac: str,
        since_epoch: float,
    ) -> tuple[bool, bool]:
        if not self.available:
            return False, False
        portal_open = self.last_portal_epoch.get(mac, 0.0) > since_epoch
        auth_activity = self.last_auth_epoch.get(mac, 0.0) > since_epoch
        return portal_open, auth_activity


class StrictJsonlJournal:
    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int,
        backup_count: int,
    ):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(self.path.parent, 0o2750)

        self._logger = logging.getLogger(
            f"pending_session_probe.{id(self)}"
        )
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._handler = RotatingFileHandler(
            filename=str(path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            delay=False,
        )
        self._handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(self._handler)
        self._restore_modes()

    def write(self, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("schema_version", SCHEMA_VERSION)
        payload.setdefault("timestamp", utc_timestamp())

        try:
            line = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            line.encode("utf-8", errors="strict")
        except Exception as exc:
            raise ProbeError("Probe event is not strict JSON") from exc

        try:
            self._handler.emit(
                logging.LogRecord(
                    name=self._logger.name,
                    level=logging.INFO,
                    pathname=__file__,
                    lineno=0,
                    msg=line,
                    args=(),
                    exc_info=None,
                )
            )
            self._handler.flush()
            self._restore_modes()
        except Exception as exc:
            raise ProbeError("Probe journal write failed") from exc

    def close(self) -> None:
        try:
            self._logger.removeHandler(self._handler)
        except Exception:
            pass
        self._handler.close()

    def _restore_modes(self) -> None:
        if os.name != "posix":
            return
        for candidate in [self.path, *sorted(self.path.parent.glob(
            f"{self.path.name}.*"
        ))]:
            try:
                if candidate.is_file():
                    os.chmod(candidate, 0o640)
            except OSError:
                continue


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(self.path.parent, 0o2750)

    def load(self) -> PersistentState:
        if not self.path.exists():
            return PersistentState()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ProbeError(
                f"State file cannot be read safely: {self.path}"
            ) from exc
        if not isinstance(payload, dict):
            raise ProbeError("State root must be an object")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ProbeError("Unsupported probe state schema")
        raw_resets = payload.get("resets")
        if not isinstance(raw_resets, dict):
            raise ProbeError("State resets must be an object")

        resets: dict[str, ResetRecord] = {}
        for raw_mac, raw_record in raw_resets.items():
            try:
                mac = normalize_mac(raw_mac)
                if not isinstance(raw_record, dict):
                    raise ValueError("record")
                resets[mac] = ResetRecord(
                    reset_id=required_text(raw_record, "reset_id"),
                    reset_at=required_text(raw_record, "reset_at"),
                    reset_epoch=finite_number(
                        raw_record.get("reset_epoch"), "reset_epoch"
                    ),
                    cooldown_until_epoch=finite_number(
                        raw_record.get("cooldown_until_epoch"),
                        "cooldown_until_epoch",
                    ),
                    uptime_before=strict_int(
                        raw_record.get("uptime_before"),
                        "uptime_before",
                        minimum=0,
                    ),
                    client_ip_before=optional_text(
                        raw_record.get("client_ip_before")
                    ),
                    ap_mac_before=optional_mac(
                        raw_record.get("ap_mac_before")
                    ),
                    command_outcome=required_text(
                        raw_record, "command_outcome"
                    ),
                    verification_result=optional_text(
                        raw_record.get("verification_result")
                    ),
                    last_classification=optional_text(
                        raw_record.get("last_classification")
                    ),
                    last_classification_at=optional_text(
                        raw_record.get("last_classification_at")
                    ),
                )
            except (KeyError, TypeError, ValueError, ProbeError) as exc:
                raise ProbeError(
                    f"Invalid state record for MAC {raw_mac!r}"
                ) from exc
        return PersistentState(resets=resets)

    def save(self, state: PersistentState) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_timestamp(),
            "resets": {
                mac: asdict(record)
                for mac, record in sorted(state.resets.items())
            },
        }
        try:
            serialized = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            serialized.encode("utf-8", errors="strict")
        except Exception as exc:
            raise ProbeError("State cannot be serialized") from exc

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=str(self.path.parent),
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(serialized)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            if os.name == "posix":
                os.chmod(temp_path, 0o640)
            os.replace(temp_path, self.path)
            if os.name == "posix":
                os.chmod(self.path, 0o640)
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise


class SingleInstanceLock:
    def __init__(self, path: Path):
        self.path = path
        self._stream = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(
                self._stream.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError as exc:
            raise ProbeError(
                "Another pending-session probe instance is already running"
            ) from exc
        self._stream.seek(0)
        self._stream.truncate()
        self._stream.write(str(os.getpid()))
        self._stream.flush()
        if os.name == "posix":
            os.chmod(self.path, 0o640)

    def close(self) -> None:
        if self._stream is None:
            return
        try:
            fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        self._stream.close()
        self._stream = None


class OmadaApi:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        if not config.verify_ssl and urllib3 is not None:
            urllib3.disable_warnings(
                urllib3.exceptions.InsecureRequestWarning
            )

    def close(self) -> None:
        self.session.close()

    def get_token(self) -> str:
        url = (
            f"{self.config.controller_url}/openapi/authorize/token"
            "?grant_type=client_credentials"
        )
        payload = self._request_json(
            "POST",
            url,
            json_body={
                "omadacId": self.config.omadac_id,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            },
            headers={"Content-Type": "application/json"},
        )
        self._require_success(payload, "token")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ProbeError("Token result must be an object")
        token = result.get("accessToken")
        if not isinstance(token, str) or not token:
            raise ProbeError("Token response has no accessToken")
        return token

    def list_all_active_clients(self, token: str) -> list[Any]:
        rows: list[Any] = []
        expected_total: int | None = None

        for page in range(1, MAX_PAGES + 1):
            payload = self._request_json(
                "GET",
                (
                    f"{self.config.controller_url}/openapi/v1/"
                    f"{self.config.omadac_id}/sites/"
                    f"{self.config.site_id}/clients"
                ),
                token=token,
                params={"page": page, "pageSize": PAGE_SIZE},
            )
            self._require_success(payload, f"client list page {page}")
            result = payload.get("result")
            if not isinstance(result, dict):
                raise ProbeError("Client list result must be an object")
            page_rows = result.get("data")
            total_rows = result.get("totalRows")
            if not isinstance(page_rows, list):
                raise ProbeError("Client list data must be an array")
            if type(total_rows) is not int or total_rows < 0:
                raise ProbeError("Client list totalRows is invalid")

            if expected_total is None:
                expected_total = total_rows
            elif total_rows != expected_total:
                raise ProbeError(
                    "Client totalRows changed during pagination"
                )

            rows.extend(page_rows)
            if len(rows) == expected_total:
                break
            if len(rows) > expected_total:
                raise ProbeError("Inventory exceeded totalRows")
            if not page_rows or len(page_rows) < PAGE_SIZE:
                break
        else:
            raise ProbeError("Pagination exceeded MAX_PAGES")

        if expected_total is None:
            raise ProbeError("Client list returned no totalRows")
        if len(rows) != expected_total:
            raise ProbeError(
                f"Incomplete inventory: {len(rows)} of {expected_total}"
            )
        return rows

    def get_client(self, token: str, client_mac: str) -> dict[str, Any]:
        payload = self._request_json(
            "GET",
            (
                f"{self.config.controller_url}/openapi/v1/"
                f"{self.config.omadac_id}/sites/{self.config.site_id}/"
                f"clients/{hyphen_mac(client_mac)}"
            ),
            token=token,
        )
        self._require_success(payload, f"exact client {client_mac}")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ProbeError("Exact-client result must be an object")
        return dict(result)

    def reconnect(self, token: str, client_mac: str) -> dict[str, Any]:
        return self._request_json(
            "POST",
            (
                f"{self.config.controller_url}/openapi/v1/"
                f"{self.config.omadac_id}/sites/{self.config.site_id}/"
                f"clients/{hyphen_mac(client_mac)}/reconnect"
            ),
            token=token,
        )

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = dict(headers or {})
        request_headers.setdefault("Accept", "application/json")
        if token is not None:
            request_headers["Authorization"] = f"AccessToken={token}"

        try:
            response = self.session.request(
                method,
                url,
                headers=request_headers,
                params=params,
                json=json_body,
                verify=self.config.verify_ssl,
                timeout=self.config.request_timeout_seconds,
            )
        except requests.Timeout as exc:
            raise ProbeError(f"{method} request timed out") from exc
        except requests.ConnectionError as exc:
            raise ProbeError(f"{method} connection failed") from exc
        except requests.RequestException as exc:
            raise ProbeError(
                f"{method} request failed: {type(exc).__name__}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProbeError(
                f"{method} HTTP {response.status_code}: invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ProbeError("Omada JSON root is not an object")
        if not 200 <= response.status_code <= 299:
            message = payload.get("msg") or payload.get("error") or "HTTP error"
            raise ProbeError(
                f"{method} HTTP {response.status_code}: {message}"
            )
        return payload

    @staticmethod
    def _require_success(payload: dict[str, Any], operation: str) -> None:
        error_code = payload.get("errorCode")
        if type(error_code) is not int:
            raise ProbeError(f"{operation}: no integer errorCode")
        if error_code != 0:
            message = str(payload.get("msg") or "controller error")
            raise ControllerError(operation, error_code, message)


def console(level: str, message: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"{timestamp} [{level.upper():10}] {message}", flush=True)


def utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def epoch_to_timestamp(value: float) -> str:
    return (
        datetime.fromtimestamp(value, timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def parse_timestamp(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.timestamp()


def normalize_mac(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("MAC must be a string")
    compact = re.sub(r"[^0-9A-Fa-f]", "", value).upper()
    if not MAC_HEX_RE.fullmatch(compact):
        raise ValueError(f"Invalid MAC: {value!r}")
    return ":".join(
        compact[index:index + 2] for index in range(0, 12, 2)
    )


def hyphen_mac(value: str) -> str:
    return normalize_mac(value).replace(":", "-")


def optional_mac(value: Any) -> str | None:
    if value is None:
        return None
    return normalize_mac(value)


def strict_int(value: Any, name: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(name)
    return value


def finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(name)
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(name) from exc
    if not math.isfinite(parsed):
        raise ValueError(name)
    return parsed


def required_text(mapping: dict[str, Any], key: str) -> str:
    value = mapping[key]
    if not isinstance(value, str) or not value:
        raise ValueError(key)
    return value


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional text")
    return value


def parse_bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    raise ProbeError(f"{name} must be boolean")


def parse_csv_pair(value: str, name: str) -> tuple[float, float]:
    parts = [item.strip() for item in value.split(",")]
    if len(parts) != 2 or any(not item for item in parts):
        raise ProbeError(f"{name} must contain exactly two values")
    parsed = tuple(finite_number(item, name) for item in parts)
    if any(item < 0 for item in parsed):
        raise ProbeError(f"{name} values must be non-negative")
    return parsed[0], parsed[1]


def env_number(name: str, default: float, *, minimum: float) -> float:
    value = os.getenv(name)
    result = default if value is None else finite_number(value, name)
    if result < minimum:
        raise ProbeError(f"{name} must be >= {minimum}")
    return result


def env_integer(name: str, default: int, *, minimum: int) -> int:
    value = os.getenv(name)
    if value is None:
        result = default
    else:
        if not re.fullmatch(r"[0-9]+", value.strip()):
            raise ProbeError(f"{name} must be an integer")
        result = int(value)
    if result < minimum:
        raise ProbeError(f"{name} must be >= {minimum}")
    return result


def parse_active_client(value: Any) -> ClientState | None:
    if not isinstance(value, dict):
        return None
    try:
        mac = normalize_mac(value["mac"])
        wireless = value["wireless"]
        active = value["active"]
        auth_status = value["authStatus"]
        uptime = value["uptime"]
        ssid = value["ssid"]
        blocked = value.get("blocked", False)
        client_ip = value.get("ip")
        ap_mac = optional_mac(value.get("apMac"))
        radio_id = value.get("radioId")

        if type(wireless) is not bool or type(active) is not bool:
            return None
        if type(auth_status) is not int:
            return None
        if type(uptime) is not int or uptime < 0:
            return None
        if not isinstance(ssid, str) or not ssid:
            return None
        if type(blocked) is not bool:
            return None
        if client_ip is not None:
            if not isinstance(client_ip, str):
                return None
            ipaddress.ip_address(client_ip)
        if radio_id is not None and type(radio_id) is not int:
            return None
    except (KeyError, TypeError, ValueError):
        return None

    return ClientState(
        mac=mac,
        wireless=wireless,
        active=active,
        auth_status=auth_status,
        uptime=uptime,
        ssid=ssid,
        blocked=blocked,
        ip=client_ip,
        ap_mac=ap_mac,
        radio_id=radio_id,
    )


def is_candidate(client: ClientState, config: Config) -> bool:
    return (
        client.wireless is True
        and client.active is True
        and client.auth_status == 1
        and client.blocked is not True
        and client.uptime >= config.min_uptime_seconds
        and client.ssid == config.ssid
    )


def duplicate_macs(rows: Iterable[Any]) -> set[str]:
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            mac = normalize_mac(row.get("mac"))
        except ValueError:
            continue
        counts[mac] = counts.get(mac, 0) + 1
    return {mac for mac, count in counts.items() if count > 1}


def tail_complete_lines(path: Path, max_bytes: int) -> list[str]:
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        start = max(0, size - max_bytes)
        stream.seek(start)
        data = stream.read()
    if start > 0:
        first_newline = data.find(b"\n")
        data = b"" if first_newline < 0 else data[first_newline + 1 :]
    if data and not data.endswith(b"\n"):
        data = data[: data.rfind(b"\n") + 1] if b"\n" in data else b""
    return data.decode("utf-8", errors="replace").splitlines()


def load_auth_telemetry(
    config: Config,
    *,
    now_epoch: float,
    state: PersistentState,
) -> AuthTelemetrySnapshot:
    active = config.auth_log_path
    candidates = [
        Path(f"{active}.{index}")
        for index in range(AUTH_LOG_BACKUP_COUNT, 0, -1)
    ] + [active]
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return AuthTelemetrySnapshot(
            available=False,
            error=f"auth telemetry not found: {active}",
        )

    earliest_reset = min(
        (record.reset_epoch for record in state.resets.values()),
        default=now_epoch - max(config.cooldown_seconds, 3600.0),
    )
    cutoff = min(
        earliest_reset,
        now_epoch - max(config.portal_grace_seconds * 2, 600.0),
    )

    events: list[tuple[float, dict[str, Any]]] = []
    readable_files = 0
    try:
        for path in existing[-2:]:
            lines = tail_complete_lines(
                path, AUTH_LOG_TAIL_BYTES_PER_FILE
            )
            readable_files += 1
            for line in lines:
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(value, dict):
                    continue
                event_epoch = parse_timestamp(value.get("timestamp"))
                if event_epoch is None or event_epoch < cutoff:
                    continue
                events.append((event_epoch, value))
    except OSError as exc:
        return AuthTelemetrySnapshot(
            available=False,
            error=f"auth telemetry read failed: {type(exc).__name__}",
        )

    if readable_files == 0:
        return AuthTelemetrySnapshot(
            available=False,
            error="auth telemetry is unreadable",
        )

    events.sort(key=lambda item: item[0])
    snapshot = AuthTelemetrySnapshot(available=True)
    session_state: dict[str, tuple[str, str, bool]] = {}

    for event_epoch, value in events:
        raw_mac = value.get("client_mac")
        try:
            mac = normalize_mac(raw_mac)
        except ValueError:
            continue
        event = value.get("event")
        if not isinstance(event, str):
            continue

        if event == PORTAL_EVENT:
            snapshot.last_portal_epoch[mac] = max(
                event_epoch,
                snapshot.last_portal_epoch.get(mac, 0.0),
            )

        if event.startswith("auth."):
            snapshot.last_auth_epoch[mac] = max(
                event_epoch,
                snapshot.last_auth_epoch.get(mac, 0.0),
            )

        session_id = value.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            continue

        if event in AUTH_START_EVENTS:
            session_state[session_id] = (mac, event, True)
        elif event in AUTH_FINISH_EVENTS:
            session_state[session_id] = (mac, event, False)

    for session_id, (mac, _event, active_state) in session_state.items():
        if active_state:
            snapshot.active_sessions_by_mac.setdefault(mac, set()).add(
                session_id
            )
    return snapshot


def refresh_preflight(
    api: OmadaApi,
    *,
    token: str,
    listed: ClientState,
    config: Config,
) -> tuple[str, ClientState] | None:
    try:
        raw = api.get_client(token, listed.mac)
    except ControllerError as exc:
        if exc.error_code != TOKEN_EXPIRED_ERROR:
            return None
        token = api.get_token()
        raw = api.get_client(token, listed.mac)
    except ProbeError:
        return None

    current = parse_active_client(raw)
    if current is None or current.mac != listed.mac:
        return None
    if not is_candidate(current, config):
        return None
    if current.uptime + UPTIME_TOLERANCE_SECONDS < listed.uptime:
        return None
    if current.ssid != listed.ssid:
        return None
    if listed.ap_mac and current.ap_mac is None:
        return None
    if listed.ap_mac and current.ap_mac and listed.ap_mac != current.ap_mac:
        return None
    return token, current


def parse_verification(
    raw: dict[str, Any],
    *,
    before: ClientState,
) -> tuple[str | None, ClientState | None]:
    try:
        response_mac = normalize_mac(raw.get("mac"))
    except ValueError:
        return None, None
    if response_mac != before.mac:
        return None, None

    active = raw.get("active")
    if type(active) is not bool:
        return None, None
    if active is False:
        return "confirmed_disconnected", None

    after = parse_active_client(raw)
    if after is None:
        return None, None
    if after.auth_status == 2:
        return "client_now_authorized", after
    if (
        after.auth_status == 1
        and after.uptime + UPTIME_TOLERANCE_SECONDS < before.uptime
    ):
        return "confirmed_new_session", after
    return None, after


def verify(
    api: OmadaApi,
    *,
    token: str,
    before: ClientState,
    delays: tuple[float, float],
) -> tuple[str, ClientState | None, int]:
    last_state: ClientState | None = None
    attempts = 0
    for delay in delays:
        if interruptible_wait(delay):
            break
        attempts += 1
        try:
            raw = api.get_client(token, before.mac)
        except ControllerError as exc:
            if exc.error_code != TOKEN_EXPIRED_ERROR:
                continue
            try:
                token = api.get_token()
                raw = api.get_client(token, before.mac)
            except ProbeError:
                continue
        except ProbeError:
            continue

        result, after = parse_verification(raw, before=before)
        if after is not None:
            last_state = after
        if result is not None:
            return result, after, attempts

    if last_state is not None:
        return "reset_not_confirmed", last_state, attempts
    return "verification_failed", None, attempts


def event_base(
    *,
    event: str,
    config: Config,
) -> dict[str, Any]:
    return {
        "event": event,
        "site_id": config.site_id,
        "ssid": config.ssid,
    }


def observe_rejoins(
    *,
    rows: list[Any],
    duplicates: set[str],
    state: PersistentState,
    auth_snapshot: AuthTelemetrySnapshot,
    journal: StrictJsonlJournal,
    config: Config,
    now_epoch: float,
) -> dict[str, int]:
    current_by_mac: dict[str, ClientState] = {}
    for row in rows:
        parsed = parse_active_client(row)
        if parsed is None or parsed.mac in duplicates:
            continue
        current_by_mac[parsed.mac] = parsed

    counts = {
        "inactive_or_absent": 0,
        "automatic_rejoin_without_portal_activity": 0,
        "rejoin_with_portal_activity": 0,
        "rejoined_and_authorized": 0,
        "old_session_still_active": 0,
    }

    for mac, record in state.resets.items():
        current = current_by_mac.get(mac)
        if current is None:
            classification = "inactive_or_absent"
            counts[classification] += 1
            continue

        portal_open, auth_activity = auth_snapshot.activity_since(
            mac=mac,
            since_epoch=record.reset_epoch,
        )
        is_new_session = (
            current.uptime + UPTIME_TOLERANCE_SECONDS
            < record.uptime_before
        )

        if current.auth_status == 2:
            classification = "rejoined_and_authorized"
        elif current.auth_status == 1 and is_new_session:
            if portal_open or auth_activity:
                classification = "rejoin_with_portal_activity"
            else:
                classification = (
                    "automatic_rejoin_without_portal_activity"
                )
        elif current.auth_status == 1:
            classification = "old_session_still_active"
        else:
            classification = "rejoin_with_portal_activity"

        counts[classification] = counts.get(classification, 0) + 1
        if record.last_classification == classification:
            continue

        record.last_classification = classification
        record.last_classification_at = utc_timestamp()
        journal.write({
            **event_base(event="pending_probe.client_rejoined", config=config),
            "reset_id": record.reset_id,
            "client_mac": mac,
            "client_ip": current.ip,
            "ap_mac": current.ap_mac,
            "seconds_after_reset": max(
                0, round(now_epoch - record.reset_epoch, 3)
            ),
            "uptime_before": record.uptime_before,
            "new_uptime": current.uptime,
            "auth_status": current.auth_status,
            "portal_open": portal_open,
            "auth_run_or_activity": auth_activity,
            "classification": classification,
        })
    return counts


def perform_scan(
    *,
    api: OmadaApi,
    config: Config,
    state: PersistentState,
    store: StateStore,
    journal: StrictJsonlJournal,
) -> None:
    scan_id = str(uuid.uuid4())
    started_epoch = time.time()
    started_monotonic = time.monotonic()
    now_epoch = started_epoch

    counters = {
        "clients_seen": 0,
        "clients_invalid": 0,
        "duplicate_mac_count": 0,
        "unauthorized_active": 0,
        "eligible": 0,
        "protected_by_portal": 0,
        "protection_unavailable": 0,
        "cooldown_skipped": 0,
        "preflight_rejected": 0,
        "reconnect_attempted": 0,
        "reconnect_accepted": 0,
        "reconnect_rejected": 0,
        "reconnect_ambiguous": 0,
        "reconnect_confirmed": 0,
        "confirmed_new_session": 0,
        "client_now_authorized": 0,
        "reconnect_unconfirmed": 0,
    }

    token = api.get_token()
    rows = api.list_all_active_clients(token)
    counters["clients_seen"] = len(rows)
    duplicates = duplicate_macs(rows)
    counters["duplicate_mac_count"] = len(duplicates)

    auth_snapshot = load_auth_telemetry(
        config,
        now_epoch=now_epoch,
        state=state,
    )

    rejoin_counts = observe_rejoins(
        rows=rows,
        duplicates=duplicates,
        state=state,
        auth_snapshot=auth_snapshot,
        journal=journal,
        config=config,
        now_epoch=now_epoch,
    )

    candidates: list[ClientState] = []
    for row in rows:
        client = parse_active_client(row)
        if client is None:
            counters["clients_invalid"] += 1
            continue
        if (
            client.wireless
            and client.active
            and client.auth_status == 1
        ):
            counters["unauthorized_active"] += 1
        if client.mac in duplicates:
            continue
        if is_candidate(client, config):
            counters["eligible"] += 1
            candidates.append(client)

    candidates.sort(key=lambda item: (-item.uptime, item.mac))

    for listed in candidates:
        now_epoch = time.time()
        existing = state.resets.get(listed.mac)
        if (
            existing is not None
            and now_epoch < existing.cooldown_until_epoch
        ):
            counters["cooldown_skipped"] += 1
            continue

        first_protection = auth_snapshot.protection(
            mac=listed.mac,
            now_epoch=now_epoch,
            grace_seconds=config.portal_grace_seconds,
        )
        if not first_protection.available:
            counters["protection_unavailable"] += 1
            continue
        if first_protection.protected:
            counters["protected_by_portal"] += 1
            continue

        preflight = refresh_preflight(
            api,
            token=token,
            listed=listed,
            config=config,
        )
        if preflight is None:
            counters["preflight_rejected"] += 1
            continue
        token, current = preflight

        # Re-read telemetry immediately before the mutating command.
        current_auth_snapshot = load_auth_telemetry(
            config,
            now_epoch=time.time(),
            state=state,
        )
        second_protection = current_auth_snapshot.protection(
            mac=current.mac,
            now_epoch=time.time(),
            grace_seconds=config.portal_grace_seconds,
        )
        if not second_protection.available:
            counters["protection_unavailable"] += 1
            continue
        if second_protection.protected:
            counters["protected_by_portal"] += 1
            continue

        reset_id = str(uuid.uuid4())
        reset_epoch = time.time()
        record = ResetRecord(
            reset_id=reset_id,
            reset_at=epoch_to_timestamp(reset_epoch),
            reset_epoch=reset_epoch,
            cooldown_until_epoch=reset_epoch + config.cooldown_seconds,
            uptime_before=current.uptime,
            client_ip_before=current.ip,
            ap_mac_before=current.ap_mac,
            command_outcome="planned",
            verification_result=None,
        )
        state.resets[current.mac] = record
        store.save(state)

        counters["reconnect_attempted"] += 1
        command_outcome = "ambiguous"
        controller_error_code: int | None = None
        controller_message: str | None = None

        try:
            response = api.reconnect(token, current.mac)
            error_code = response.get("errorCode")
            if type(error_code) is not int:
                command_outcome = "ambiguous"
                counters["reconnect_ambiguous"] += 1
            elif error_code == 0:
                command_outcome = "accepted"
                counters["reconnect_accepted"] += 1
                controller_error_code = 0
                controller_message = optional_text(response.get("msg"))
            else:
                command_outcome = "rejected"
                counters["reconnect_rejected"] += 1
                controller_error_code = error_code
                controller_message = optional_text(response.get("msg"))
        except ControllerError as exc:
            command_outcome = "rejected"
            counters["reconnect_rejected"] += 1
            controller_error_code = exc.error_code
            controller_message = exc.controller_message
        except ProbeError as exc:
            command_outcome = "ambiguous"
            counters["reconnect_ambiguous"] += 1
            controller_message = type(exc).__name__

        record.command_outcome = command_outcome

        verification_result: str | None = None
        after: ClientState | None = None
        verification_attempts = 0

        if command_outcome in {"accepted", "ambiguous"}:
            verification_result, after, verification_attempts = verify(
                api,
                token=token,
                before=current,
                delays=config.verify_delays_seconds,
            )
            record.verification_result = verification_result
            if verification_result == "confirmed_disconnected":
                counters["reconnect_confirmed"] += 1
            elif verification_result == "confirmed_new_session":
                counters["reconnect_confirmed"] += 1
                counters["confirmed_new_session"] += 1
            elif verification_result == "client_now_authorized":
                counters["client_now_authorized"] += 1
            else:
                counters["reconnect_unconfirmed"] += 1

        store.save(state)
        journal.write({
            **event_base(
                event="pending_probe.reset.completed",
                config=config,
            ),
            "reset_id": reset_id,
            "scan_id": scan_id,
            "client_mac": current.mac,
            "client_ip_before": current.ip,
            "client_ip_after": after.ip if after else None,
            "ap_mac_before": current.ap_mac,
            "ap_mac_after": after.ap_mac if after else None,
            "radio_id": current.radio_id,
            "uptime_before": current.uptime,
            "uptime_after": after.uptime if after else None,
            "auth_status_before": current.auth_status,
            "auth_status_after": after.auth_status if after else None,
            "portal_activity_before": second_protection.portal_open,
            "auth_run_before": second_protection.auth_run_active,
            "protection_reason": second_protection.reason,
            "command_outcome": command_outcome,
            "controller_error_code": controller_error_code,
            "controller_message": controller_message,
            "verification_attempts": verification_attempts,
            "result": verification_result or command_outcome,
            "cooldown_until": epoch_to_timestamp(
                record.cooldown_until_epoch
            ),
        })

    store.save(state)
    journal.write({
        **event_base(event="pending_probe.scan.completed", config=config),
        "scan_id": scan_id,
        "started_at": epoch_to_timestamp(started_epoch),
        "finished_at": utc_timestamp(),
        "duration_ms": max(
            0, round((time.monotonic() - started_monotonic) * 1000)
        ),
        "auth_telemetry_available": auth_snapshot.available,
        "auth_telemetry_error": auth_snapshot.error,
        **counters,
        **{
            f"observed_{key}": value
            for key, value in rejoin_counts.items()
        },
    })

    console(
        "scan",
        (
            f"clients={counters['clients_seen']} "
            f"pending={counters['unauthorized_active']} "
            f"eligible={counters['eligible']} "
            f"protected={counters['protected_by_portal']} "
            f"cooldown={counters['cooldown_skipped']} "
            f"attempted={counters['reconnect_attempted']} "
            f"confirmed={counters['reconnect_confirmed']}"
        ),
    )


def load_project_settings() -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

    try:
        from app import get_settings
    except Exception as exc:
        raise ProbeError(
            "Cannot import CaptivePortal settings from /opt/CaptivePortal"
        ) from exc
    try:
        settings = get_settings()
    except Exception as exc:
        raise ProbeError("CaptivePortal settings could not be loaded") from exc
    if not isinstance(settings, dict):
        raise ProbeError("get_settings() returned invalid data")
    return settings


def setting_text(
    settings: dict[str, Any],
    *keys: str,
) -> str:
    for key in keys:
        value = settings.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ProbeError(f"Missing project setting: {' / '.join(keys)}")


def load_config(args: argparse.Namespace) -> Config:
    settings = load_project_settings()
    production_enabled = parse_bool(
        settings.get("pending_session_cleaner_enabled") or False,
        "PENDING_SESSION_CLEANER_ENABLED",
    )
    if production_enabled:
        raise ProbeError(
            "Production Pending Session Cleaner is enabled. "
            "Stop and disable the temporary probe."
        )

    interval = env_number(
        "PENDING_PROBE_SCAN_INTERVAL_SECONDS",
        DEFAULT_SCAN_INTERVAL_SECONDS,
        minimum=1,
    )
    min_uptime = env_integer(
        "PENDING_PROBE_MIN_UPTIME_SECONDS",
        DEFAULT_MIN_UPTIME_SECONDS,
        minimum=1,
    )
    cooldown = env_number(
        "PENDING_PROBE_COOLDOWN_SECONDS",
        DEFAULT_COOLDOWN_SECONDS,
        minimum=0,
    )
    grace = env_number(
        "PENDING_PROBE_PORTAL_GRACE_SECONDS",
        DEFAULT_PORTAL_GRACE_SECONDS,
        minimum=0,
    )
    timeout = env_number(
        "PENDING_PROBE_REQUEST_TIMEOUT_SECONDS",
        DEFAULT_REQUEST_TIMEOUT_SECONDS,
        minimum=0.1,
    )
    delays = parse_csv_pair(
        os.getenv(
            "PENDING_PROBE_VERIFY_DELAYS_SECONDS",
            "1,4",
        ),
        "PENDING_PROBE_VERIFY_DELAYS_SECONDS",
    )

    if args.interval is not None:
        interval = args.interval
    if args.min_uptime is not None:
        min_uptime = args.min_uptime

    ssid = os.getenv("PENDING_PROBE_SSID", DEFAULT_SSID).strip()
    if not ssid:
        raise ProbeError("PENDING_PROBE_SSID must be non-empty")

    auth_log = Path(
        os.getenv(
            "PENDING_PROBE_AUTH_LOG_PATH",
            str(
                settings.get(
                    "auth_telemetry_log_path",
                    settings.get(
                        "auth_telemetry_log_file",
                        DEFAULT_AUTH_LOG_PATH,
                    ),
                )
            ),
        )
    )
    journal = Path(
        os.getenv("PENDING_PROBE_LOG_FILE", DEFAULT_JOURNAL_PATH)
    )
    state = Path(
        os.getenv("PENDING_PROBE_STATE_FILE", DEFAULT_STATE_PATH)
    )
    lock = Path(
        os.getenv("PENDING_PROBE_LOCK_FILE", DEFAULT_LOCK_PATH)
    )

    for name, path in {
        "auth log": auth_log,
        "journal": journal,
        "state": state,
        "lock": lock,
    }.items():
        if not path.is_absolute():
            raise ProbeError(f"{name} path must be absolute")

    return Config(
        controller_url=setting_text(
            settings, "omada_url", "controller_url"
        ).rstrip("/"),
        omadac_id=setting_text(settings, "omada_id", "omadac_id"),
        site_id=setting_text(settings, "capport_site_id"),
        client_id=setting_text(settings, "client_id", "omada_client_id"),
        client_secret=setting_text(
            settings, "client_secret", "omada_client_secret"
        ),
        verify_ssl=parse_bool(
            settings.get("verify_ssl", False),
            "verify_ssl",
        ),
        ssid=ssid,
        scan_interval_seconds=interval,
        min_uptime_seconds=min_uptime,
        cooldown_seconds=cooldown,
        portal_grace_seconds=grace,
        request_timeout_seconds=timeout,
        verify_delays_seconds=delays,
        auth_log_path=auth_log,
        journal_path=journal,
        state_path=state,
        lock_path=lock,
        journal_max_bytes=env_integer(
            "PENDING_PROBE_ROTATION_MAX_BYTES",
            DEFAULT_JOURNAL_MAX_BYTES,
            minimum=1,
        ),
        journal_backup_count=env_integer(
            "PENDING_PROBE_ROTATION_BACKUP_COUNT",
            DEFAULT_JOURNAL_BACKUP_COUNT,
            minimum=1,
        ),
        once=args.once,
    )


_STOP_REQUESTED = False


def request_stop(_signum: int, _frame: Any) -> None:
    global _STOP_REQUESTED
    _STOP_REQUESTED = True


def interruptible_wait(seconds: float) -> bool:
    deadline = time.monotonic() + max(0.0, seconds)
    while not _STOP_REQUESTED:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(remaining, 0.25))
    return True


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Temporary Pending Session Probe/Cleaner"
    )
    value.add_argument(
        "--once",
        action="store_true",
        help="Run one active scan and exit.",
    )
    value.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Override scan interval in seconds.",
    )
    value.add_argument(
        "--min-uptime",
        type=int,
        default=None,
        help="Override minimum pending uptime in seconds.",
    )
    return value


def main() -> int:
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    lock: SingleInstanceLock | None = None
    journal: StrictJsonlJournal | None = None
    api: OmadaApi | None = None

    try:
        args = parser().parse_args()
        config = load_config(args)

        lock = SingleInstanceLock(config.lock_path)
        lock.acquire()

        store = StateStore(config.state_path)
        state = store.load()
        journal = StrictJsonlJournal(
            config.journal_path,
            max_bytes=config.journal_max_bytes,
            backup_count=config.journal_backup_count,
        )
        api = OmadaApi(config)

        journal.write({
            **event_base(event="pending_probe.started", config=config),
            "scan_interval_seconds": config.scan_interval_seconds,
            "min_uptime_seconds": config.min_uptime_seconds,
            "cooldown_seconds": config.cooldown_seconds,
            "portal_grace_seconds": config.portal_grace_seconds,
            "verify_delays_seconds": list(
                config.verify_delays_seconds
            ),
            "auth_log_path": str(config.auth_log_path),
            "state_path": str(config.state_path),
        })

        console(
            "info",
            (
                f"probe started: interval={config.scan_interval_seconds}s "
                f"threshold={config.min_uptime_seconds}s "
                f"cooldown={config.cooldown_seconds}s "
                f"ssid={config.ssid}"
            ),
        )

        while not _STOP_REQUESTED:
            try:
                perform_scan(
                    api=api,
                    config=config,
                    state=state,
                    store=store,
                    journal=journal,
                )
            except Exception as exc:
                console(
                    "error",
                    f"scan failed safely: {type(exc).__name__}: {exc}",
                )
                try:
                    journal.write({
                        **event_base(
                            event="pending_probe.scan.failed",
                            config=config,
                        ),
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:512],
                    })
                except Exception:
                    pass

            if config.once or _STOP_REQUESTED:
                break
            interruptible_wait(config.scan_interval_seconds)

        journal.write({
            **event_base(event="pending_probe.stopped", config=config),
            "reset_records": len(state.resets),
        })
        return 0

    except ProbeError as exc:
        console("error", str(exc))
        return 2
    except Exception as exc:
        console(
            "error",
            f"unexpected fatal error: {type(exc).__name__}: {exc}",
        )
        return 3
    finally:
        if api is not None:
            api.close()
        if journal is not None:
            journal.close()
        if lock is not None:
            lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
