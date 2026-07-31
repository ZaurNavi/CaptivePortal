#!/usr/bin/env python3
"""
Temporary standalone proof-of-concept for clearing stale unauthorised
Omada client sessions.

The script is intentionally independent from PendingClientSessionCleaner:
- no systemd service;
- no background integration with CaptivePortal;
- no database;
- no project source changes.

Default behaviour:
- scan every 120 seconds;
- target only SSID Zefer_Parki;
- candidate age >= 60 seconds;
- require wireless=true, active=true, authStatus=1, blocked!=true;
- perform a fresh exact-client GET before reconnect;
- send POST /reconnect once;
- verify the resulting client state.

Run from /opt/CaptivePortal with the project virtual environment active.
Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

import requests

try:
    import urllib3
except ImportError:  # pragma: no cover
    urllib3 = None


MAC_HEX_RE = re.compile(r"^[0-9A-F]{12}$")
TOKEN_EXPIRED_ERROR = -44112
DEFAULT_PAGE_SIZE = 500
DEFAULT_MAX_PAGES = 20
UPTIME_REGRESSION_TOLERANCE_SECONDS = 5


class ScriptError(RuntimeError):
    """A controlled scan/API failure."""


@dataclass(frozen=True)
class Config:
    controller_url: str
    omadac_id: str
    site_id: str
    client_id: str
    client_secret: str
    verify_ssl: bool
    ssid: str
    min_uptime_seconds: int
    interval_seconds: float
    request_timeout_seconds: float
    max_actions_per_scan: int
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


def log(level: str, message: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"{timestamp} [{level.upper():7}] {message}", flush=True)


def normalize_mac(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("MAC must be a string")
    compact = re.sub(r"[^0-9A-Fa-f]", "", value).upper()
    if not MAC_HEX_RE.fullmatch(compact):
        raise ValueError(f"Invalid MAC: {value!r}")
    return ":".join(compact[index:index + 2] for index in range(0, 12, 2))


def hyphen_mac(value: str) -> str:
    return normalize_mac(value).replace(":", "-")


def parse_bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ScriptError(f"{name} must be boolean")


def parse_active_client(value: Any) -> ClientState | None:
    """Strict parser for an active client session."""
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
        ap_mac_raw = value.get("apMac")

        if type(wireless) is not bool:
            return None
        if type(active) is not bool:
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
        ap_mac = normalize_mac(ap_mac_raw) if ap_mac_raw is not None else None
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


def load_project_settings() -> dict[str, Any]:
    try:
        from app import get_settings
    except Exception as exc:
        raise ScriptError(
            "Cannot import CaptivePortal settings. Run the script from "
            "/opt/CaptivePortal with the project virtual environment active."
        ) from exc

    try:
        settings = get_settings()
    except Exception as exc:
        raise ScriptError("CaptivePortal settings could not be loaded") from exc

    if not isinstance(settings, dict):
        raise ScriptError("CaptivePortal get_settings() returned invalid data")
    return settings


def required_string(settings: dict[str, Any], key: str) -> str:
    value = settings.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ScriptError(f"Required setting {key!r} is missing")
    return value.strip()


def build_config(args: argparse.Namespace) -> Config:
    settings = load_project_settings()

    controller_url = required_string(settings, "omada_url").rstrip("/")
    omadac_id = required_string(settings, "omada_id")
    site_id = required_string(settings, "capport_site_id")
    client_id = required_string(settings, "client_id")
    client_secret = required_string(settings, "client_secret")
    verify_ssl = parse_bool(settings.get("verify_ssl", False), "verify_ssl")

    if args.interval <= 0:
        raise ScriptError("--interval must be greater than zero")
    if args.min_uptime <= 0:
        raise ScriptError("--min-uptime must be greater than zero")
    if args.request_timeout <= 0:
        raise ScriptError("--request-timeout must be greater than zero")
    if args.max_actions <= 0:
        raise ScriptError("--max-actions must be greater than zero")
    if not isinstance(args.ssid, str) or not args.ssid:
        raise ScriptError("--ssid must be non-empty")

    return Config(
        controller_url=controller_url,
        omadac_id=omadac_id,
        site_id=site_id,
        client_id=client_id,
        client_secret=client_secret,
        verify_ssl=verify_ssl,
        ssid=args.ssid,
        min_uptime_seconds=args.min_uptime,
        interval_seconds=args.interval,
        request_timeout_seconds=args.request_timeout,
        max_actions_per_scan=args.max_actions,
        once=args.once,
    )


class OmadaApi:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        if not config.verify_ssl and urllib3 is not None:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def close(self) -> None:
        self.session.close()

    def get_token(self) -> str:
        url = (
            f"{self.config.controller_url}/openapi/authorize/token"
            "?grant_type=client_credentials"
        )
        payload = {
            "omadacId": self.config.omadac_id,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        data = self._request_json(
            "POST",
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        self._require_success(data, "token")
        result = data.get("result")
        if not isinstance(result, dict):
            raise ScriptError("Token response result is not an object")
        token = result.get("accessToken")
        if not isinstance(token, str) or not token:
            raise ScriptError("Token response has no accessToken")
        return token

    def list_all_active_clients(self, token: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        expected_total: int | None = None

        for page in range(1, DEFAULT_MAX_PAGES + 1):
            url = (
                f"{self.config.controller_url}/openapi/v1/"
                f"{self.config.omadac_id}/sites/{self.config.site_id}/clients"
            )
            data = self._request_json(
                "GET",
                url,
                token=token,
                params={"page": page, "pageSize": DEFAULT_PAGE_SIZE},
            )
            self._require_success(data, f"client list page {page}")
            result = data.get("result")
            if not isinstance(result, dict):
                raise ScriptError("Client list result is not an object")
            page_rows = result.get("data")
            total_rows = result.get("totalRows")
            if not isinstance(page_rows, list):
                raise ScriptError("Client list data is not an array")
            if type(total_rows) is not int or total_rows < 0:
                raise ScriptError("Client list totalRows is invalid")

            if expected_total is None:
                expected_total = total_rows
            elif total_rows != expected_total:
                raise ScriptError(
                    "Client inventory changed during pagination; "
                    "no reconnects will be performed in this scan"
                )

            for item in page_rows:
                if isinstance(item, dict):
                    rows.append(dict(item))
                else:
                    rows.append(item)

            if len(rows) >= expected_total:
                break
            if not page_rows or len(page_rows) < DEFAULT_PAGE_SIZE:
                break
        else:
            raise ScriptError("Client pagination exceeded the page limit")

        if expected_total is None:
            raise ScriptError("Client list returned no pagination metadata")
        if len(rows) != expected_total:
            raise ScriptError(
                f"Incomplete client inventory: received {len(rows)} "
                f"of {expected_total}"
            )
        return rows

    def get_client(self, token: str, client_mac: str) -> dict[str, Any]:
        url = (
            f"{self.config.controller_url}/openapi/v1/"
            f"{self.config.omadac_id}/sites/{self.config.site_id}/clients/"
            f"{hyphen_mac(client_mac)}"
        )
        data = self._request_json("GET", url, token=token)
        self._require_success(data, f"exact client {client_mac}")
        result = data.get("result")
        if not isinstance(result, dict):
            raise ScriptError("Exact-client result is not an object")
        return dict(result)

    def reconnect(self, token: str, client_mac: str) -> dict[str, Any]:
        url = (
            f"{self.config.controller_url}/openapi/v1/"
            f"{self.config.omadac_id}/sites/{self.config.site_id}/clients/"
            f"{hyphen_mac(client_mac)}/reconnect"
        )
        return self._request_json("POST", url, token=token)

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
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
                json=json,
                verify=self.config.verify_ssl,
                timeout=self.config.request_timeout_seconds,
            )
        except requests.Timeout as exc:
            raise ScriptError(f"{method} request timed out") from exc
        except requests.ConnectionError as exc:
            raise ScriptError(f"{method} connection failed") from exc
        except requests.RequestException as exc:
            raise ScriptError(f"{method} request failed: {type(exc).__name__}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ScriptError(
                f"{method} returned HTTP {response.status_code} with invalid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise ScriptError(
                f"{method} returned HTTP {response.status_code} "
                "with a non-object JSON root"
            )
        if not 200 <= response.status_code <= 299:
            message = payload.get("msg") or payload.get("error") or "HTTP error"
            raise ScriptError(
                f"{method} returned HTTP {response.status_code}: {message}"
            )
        return payload

    @staticmethod
    def _require_success(data: dict[str, Any], operation: str) -> None:
        error_code = data.get("errorCode")
        if type(error_code) is not int:
            raise ScriptError(f"{operation}: response has no integer errorCode")
        if error_code != 0:
            message = data.get("msg") or "controller error"
            raise ScriptError(
                f"{operation}: Omada errorCode={error_code}: {message}"
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


def refresh_and_preflight(
    api: OmadaApi,
    token: str,
    listed: ClientState,
    config: Config,
) -> tuple[str, ClientState] | None:
    """Return a fresh token/client only when the same session is still eligible."""
    try:
        raw = api.get_client(token, listed.mac)
    except ScriptError as exc:
        if f"errorCode={TOKEN_EXPIRED_ERROR}" not in str(exc):
            log("warning", f"{listed.mac}: preflight failed: {exc}")
            return None
        token = api.get_token()
        raw = api.get_client(token, listed.mac)

    current = parse_active_client(raw)
    if current is None:
        log("skip", f"{listed.mac}: exact client card is incomplete or invalid")
        return None
    if current.mac != listed.mac:
        log("skip", f"{listed.mac}: MAC changed in exact-client response")
        return None
    if not is_candidate(current, config):
        log(
            "skip",
            f"{listed.mac}: no longer eligible "
            f"(active={current.active}, authStatus={current.auth_status}, "
            f"uptime={current.uptime}, ssid={current.ssid!r})",
        )
        return None
    if current.uptime + UPTIME_REGRESSION_TOLERANCE_SECONDS < listed.uptime:
        log(
            "skip",
            f"{listed.mac}: session was replaced "
            f"(list uptime={listed.uptime}, current uptime={current.uptime})",
        )
        return None
    if current.ssid != listed.ssid:
        log("skip", f"{listed.mac}: SSID changed")
        return None
    if listed.ap_mac and current.ap_mac and listed.ap_mac != current.ap_mac:
        log("skip", f"{listed.mac}: AP changed")
        return None
    if listed.ap_mac and current.ap_mac is None:
        log("skip", f"{listed.mac}: AP disappeared from exact-client card")
        return None
    return token, current


def verify_result(
    api: OmadaApi,
    token: str,
    before: ClientState,
) -> str:
    """Verify once after reconnect using the real inactive-card semantics."""
    time.sleep(2.0)
    try:
        raw = api.get_client(token, before.mac)
    except ScriptError as exc:
        if f"errorCode={TOKEN_EXPIRED_ERROR}" in str(exc):
            try:
                token = api.get_token()
                raw = api.get_client(token, before.mac)
            except ScriptError as refresh_exc:
                return f"verification unavailable: {refresh_exc}"
        else:
            return f"verification unavailable: {exc}"

    try:
        response_mac = normalize_mac(raw.get("mac"))
    except ValueError:
        return "verification card has invalid MAC"
    if response_mac != before.mac:
        return "verification returned another MAC"

    active = raw.get("active")
    if type(active) is not bool:
        return "verification card has no boolean active"
    if active is False:
        return "confirmed disconnected (active=false)"

    # For active=true, require a complete active-session card.
    after = parse_active_client(raw)
    if after is None:
        return "active client card is incomplete"
    if after.auth_status == 2:
        return "client is now authorized"
    if (
        after.auth_status == 1
        and after.uptime + UPTIME_REGRESSION_TOLERANCE_SECONDS < before.uptime
    ):
        return (
            "confirmed new session "
            f"(uptime {before.uptime} -> {after.uptime})"
        )
    return (
        "reset not confirmed "
        f"(active={after.active}, authStatus={after.auth_status}, "
        f"uptime={after.uptime})"
    )


def run_scan(api: OmadaApi, config: Config) -> None:
    started = time.monotonic()
    log(
        "scan",
        f"starting: ssid={config.ssid!r}, "
        f"min_uptime={config.min_uptime_seconds}s",
    )

    token = api.get_token()
    rows = api.list_all_active_clients(token)
    duplicates = duplicate_macs(rows)

    candidates: list[ClientState] = []
    invalid_rows = 0
    for row in rows:
        parsed = parse_active_client(row)
        if parsed is None:
            invalid_rows += 1
            continue
        if parsed.mac in duplicates:
            log("skip", f"{parsed.mac}: duplicate MAC in active inventory")
            continue
        if is_candidate(parsed, config):
            candidates.append(parsed)

    candidates.sort(key=lambda item: (-item.uptime, item.mac))

    log(
        "scan",
        f"active rows={len(rows)}, invalid={invalid_rows}, "
        f"duplicates={len(duplicates)}, candidates={len(candidates)}",
    )

    actions = 0
    for listed in candidates:
        if actions >= config.max_actions_per_scan:
            log(
                "scan",
                f"action limit reached ({config.max_actions_per_scan}); "
                "remaining candidates deferred",
            )
            break

        preflight = refresh_and_preflight(api, token, listed, config)
        if preflight is None:
            continue
        token, current = preflight

        log(
            "action",
            f"{current.mac} ip={current.ip or '-'} "
            f"uptime={current.uptime}s authStatus={current.auth_status} "
            f"ssid={current.ssid}: sending reconnect",
        )

        try:
            response = api.reconnect(token, current.mac)
        except ScriptError as exc:
            # The controller may have accepted the command even if the HTTP
            # response was lost or malformed. Never send a blind second POST.
            actions += 1
            log(
                "warning",
                f"{current.mac}: reconnect outcome is ambiguous: {exc}; "
                "verifying without retry",
            )
            verification = verify_result(api, token, current)
            log("result", f"{current.mac}: ambiguous; {verification}")
            continue

        error_code = response.get("errorCode")
        if type(error_code) is not int:
            actions += 1
            log(
                "warning",
                f"{current.mac}: reconnect response has no integer errorCode; "
                "verifying without retry",
            )
            verification = verify_result(api, token, current)
            log("result", f"{current.mac}: ambiguous; {verification}")
            continue

        # One controlled token-expiry recovery. No retry for timeout/network errors.
        if error_code == TOKEN_EXPIRED_ERROR:
            log("warning", f"{current.mac}: token expired; refreshing and rechecking")
            token = api.get_token()
            second_preflight = refresh_and_preflight(
                api, token, current, config
            )
            if second_preflight is None:
                continue
            token, current = second_preflight
            try:
                response = api.reconnect(token, current.mac)
            except ScriptError as exc:
                actions += 1
                log(
                    "warning",
                    f"{current.mac}: recovery reconnect is ambiguous: {exc}; "
                    "verifying without another POST",
                )
                verification = verify_result(api, token, current)
                log("result", f"{current.mac}: ambiguous; {verification}")
                continue
            error_code = response.get("errorCode")

        if error_code != 0:
            message = response.get("msg") or "controller rejected reconnect"
            log(
                "error",
                f"{current.mac}: reconnect rejected "
                f"errorCode={error_code}: {message}",
            )
            continue

        actions += 1
        message = response.get("msg") or "Success."
        log("action", f"{current.mac}: reconnect accepted: {message}")
        verification = verify_result(api, token, current)
        log("result", f"{current.mac}: {verification}")

    elapsed = time.monotonic() - started
    log("scan", f"completed in {elapsed:.2f}s; reconnects sent={actions}")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Temporary standalone Omada pending-session cleanup test."
        )
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one scan and exit.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=120.0,
        help="Seconds between completed scans (default: 120).",
    )
    parser.add_argument(
        "--min-uptime",
        type=int,
        default=60,
        help="Minimum unauthorised session uptime in seconds (default: 60).",
    )
    parser.add_argument(
        "--ssid",
        default="Zefer_Parki",
        help="Exact SSID to process (default: Zefer_Parki).",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=5.0,
        help="HTTP request timeout in seconds (default: 5).",
    )
    parser.add_argument(
        "--max-actions",
        type=int,
        default=20,
        help="Maximum reconnects per scan (default: 20).",
    )
    return parser


_STOP_REQUESTED = False


def request_stop(signum: int, frame: Any) -> None:
    del signum, frame
    global _STOP_REQUESTED
    _STOP_REQUESTED = True
    log("info", "stop requested; finishing current operation")


def main() -> int:
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    try:
        args = build_argument_parser().parse_args()
        config = build_config(args)
    except ScriptError as exc:
        log("error", str(exc))
        return 2

    log(
        "info",
        "temporary cleaner started "
        f"(controller={config.controller_url}, site={config.site_id}, "
        f"verify_ssl={config.verify_ssl})",
    )
    log(
        "warning",
        "standalone prototype cannot inspect the live AuthSessionManager; "
        "it relies on Omada authStatus and the fresh preflight check",
    )

    api = OmadaApi(config)
    try:
        while not _STOP_REQUESTED:
            try:
                run_scan(api, config)
            except ScriptError as exc:
                log("error", f"scan failed safely: {exc}")
            except Exception as exc:
                log(
                    "error",
                    f"unexpected scan failure: {type(exc).__name__}: {exc}",
                )

            if config.once or _STOP_REQUESTED:
                break

            log("info", f"next scan in {config.interval_seconds:g} seconds")
            deadline = time.monotonic() + config.interval_seconds
            while not _STOP_REQUESTED:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(remaining, 0.5))
    finally:
        api.close()

    log("info", "temporary cleaner stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
