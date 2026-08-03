from __future__ import annotations

from typing import Sequence, List, Dict, Tuple
from .models import (
    PendingClientObservation,
    PendingClientCandidate,
    ClassificationResult,
)
from app.common.mac import format_mac_colon
import types


def _is_int_but_not_bool(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


class PendingSessionClassifier:
    """
    Classifier that parses raw controller rows and builds an initial candidate list.
    """

    def __init__(self, *, min_uptime_seconds: int, ssid_allowlist: Sequence[str]):
        self.min_uptime_seconds = int(min_uptime_seconds)
        self.ssid_allowlist = tuple(ssid_allowlist)

    def _parse_row(self, row) -> PendingClientObservation:
        # Raises ValueError / TypeError / KeyError on invalid row (caller will catch)
        if not isinstance(row, dict):
            raise TypeError("row must be dict")

        # required
        raw_mac = row["mac"]
        mac = format_mac_colon(raw_mac)  # may raise ValueError
        wireless = row["wireless"]
        active = row["active"]
        if type(wireless) is not bool or type(active) is not bool:
            raise TypeError("wireless/active must be bool")
        auth_status = row["authStatus"]
        if not _is_int_but_not_bool(auth_status):
            raise TypeError("authStatus must be int and not bool")
        auth_status = int(auth_status)
        uptime = row["uptime"]
        if not _is_int_but_not_bool(uptime):
            raise TypeError("uptime must be int and not bool")
        uptime = int(uptime)
        if uptime < 0:
            raise ValueError("uptime must be >= 0")
        ssid = row["ssid"]
        if not isinstance(ssid, str) or not ssid:
            raise TypeError("ssid must be non-empty string")

        # blocked optional
        if "blocked" in row:
            blocked_raw = row["blocked"]
            if type(blocked_raw) is not bool:
                raise TypeError("blocked must be bool if present")
            blocked = bool(blocked_raw)
        else:
            blocked = False

        # optional fields
        client_ip = row.get("ip")
        if client_ip is not None and not isinstance(client_ip, str):
            raise TypeError("ip must be string or absent")
        ap_mac_raw = row.get("apMac")
        ap_mac = None
        if ap_mac_raw is not None:
            ap_mac = format_mac_colon(ap_mac_raw)

        def _optional_int(key):
            v = row.get(key)
            if v is None:
                return None
            if not _is_int_but_not_bool(v):
                raise TypeError(f"{key} must be int or absent")
            return int(v)

        radio_id = _optional_int("radioId")
        channel = _optional_int("channel")
        rssi = _optional_int("rssi")
        snr = _optional_int("snr")

        return PendingClientObservation(
            mac=mac,
            wireless=wireless,
            active=active,
            auth_status=auth_status,
            uptime=uptime,
            ssid=ssid,
            blocked=blocked,
            client_ip=client_ip,
            ap_mac=ap_mac,
            radio_id=radio_id,
            channel=channel,
            rssi=rssi,
            snr=snr,
        )

    def classify_inventory(self, clients: Sequence[object], *, site_id: str) -> ClassificationResult:
        clients_rows_received = 0
        clients_valid = 0
        clients_invalid = 0
        duplicate_mac_count = 0
        wireless_active_count = 0
        wired_or_non_wireless_count = 0
        authorized_active_count = 0
        unauthorized_active_count = 0
        unknown_auth_status_count = 0
        below_threshold_count = 0
        ssid_not_allowed_count = 0
        blocked_count = 0
        initial_candidate_count = 0
        auth_status_counts: Dict[str, int] = {}

        parsed: List[PendingClientObservation] = []

        # 1. parse rows strictly -> valid/invalid counters
        for row in clients:
            clients_rows_received += 1
            try:
                obs = self._parse_row(row)
            except (KeyError, TypeError, ValueError):
                clients_invalid += 1
                continue
            clients_valid += 1
            parsed.append(obs)

        # 2. duplicate detection
        counts: Dict[str, int] = {}
        for p in parsed:
            counts[p.mac] = counts.get(p.mac, 0) + 1
        duplicates = {m for m, c in counts.items() if c > 1}
        duplicate_mac_count = len(duplicates)

        # 3. active/wired split and authStatus split for valid active wireless
        for obs in parsed:
            if obs.wireless and obs.active:
                wireless_active_count += 1
                if obs.auth_status == 2:
                    authorized_active_count += 1
                elif obs.auth_status == 1:
                    unauthorized_active_count += 1
                else:
                    unknown_auth_status_count += 1
                # auth_status_counts only for valid active wireless
                key = str(obs.auth_status)
                auth_status_counts[key] = auth_status_counts.get(key, 0) + 1
            else:
                wired_or_non_wireless_count += 1

        # 4. collect candidates from valid active wireless with authStatus == 1
        candidates: List[PendingClientCandidate] = []
        for obs in parsed:
            if not (obs.wireless and obs.active and obs.auth_status == 1):
                continue
            if obs.blocked:
                blocked_count += 1
                continue
            if obs.uptime < self.min_uptime_seconds:
                below_threshold_count += 1
                continue
            if obs.ssid not in self.ssid_allowlist:
                ssid_not_allowed_count += 1
                continue
            if obs.mac in duplicates:
                # excluded; duplicates already counted
                continue
            candidates.append(PendingClientCandidate(observation=obs, list_uptime=obs.uptime))

        # Sort
        candidates.sort(key=lambda c: (-c.list_uptime, c.observation.mac))
        initial_candidate_count = len(candidates)

        # make auth_status_counts read-only
        auth_status_counts_ro = types.MappingProxyType(dict(auth_status_counts))

        return ClassificationResult(
            clients_rows_received=clients_rows_received,
            clients_valid=clients_valid,
            clients_invalid=clients_invalid,
            duplicate_mac_count=duplicate_mac_count,
            wireless_active_count=wireless_active_count,
            wired_or_non_wireless_count=wired_or_non_wireless_count,
            authorized_active_count=authorized_active_count,
            unauthorized_active_count=unauthorized_active_count,
            unknown_auth_status_count=unknown_auth_status_count,
            below_threshold_count=below_threshold_count,
            ssid_not_allowed_count=ssid_not_allowed_count,
            blocked_count=blocked_count,
            initial_candidate_count=initial_candidate_count,
            auth_status_counts=auth_status_counts_ro,
            candidates=tuple(candidates),
        )
