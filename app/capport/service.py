"""CAPPORT identity snapshots, authoritative state and short caches."""

import ipaddress
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.auth_telemetry import get_auth_telemetry
from app.auth_telemetry import events
from app.logger import logger

from .models import CapportClient, CapportConfig, CapportState


LOGIN_LOOKUP_ATTEMPTS = 5
LOGIN_LOOKUP_INTERVAL_SECONDS = 1.0
LOGIN_LOOKUP_MAX_WAIT_SECONDS = 5.0
IDENTITY_CHANGE_ATTEMPTS = 2


@dataclass(frozen=True)
class _IdentitySnapshot:
    expires_at: float
    generation: int
    mac_by_ip: dict[str, str]
    ambiguous_ips: frozenset[str]


@dataclass(frozen=True)
class _CachedClientState:
    expires_at: float
    identity_generation: int
    client: CapportClient


@dataclass(frozen=True)
class _ResolvedClient:
    client: CapportClient | None
    reason: str
    cache_hit: bool


@dataclass(frozen=True)
class _FailureCooldown:
    expires_at: float
    reason: str


class _LookupFailure(RuntimeError):
    def __init__(self, reason: str, *, cache_hit: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.cache_hit = cache_hit


class _IdentityChanged(RuntimeError):
    pass


class CapportService:
    def __init__(
        self,
        controller: Any,
        config: CapportConfig,
        telemetry=None,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.controller = controller
        self.config = config
        self._telemetry = telemetry or get_auth_telemetry()
        self._monotonic = monotonic
        self._sleep = sleep

        self._identity_cache: dict[str, _IdentitySnapshot] = {}
        self._state_cache: dict[
            str,
            dict[str, _CachedClientState],
        ] = {}
        self._failure_cache: dict[str, _FailureCooldown] = {}

        self._cache_lock = threading.RLock()
        self._identity_refresh_locks: dict[
            str,
            threading.Lock,
        ] = {}
        self._state_refresh_locks: dict[
            tuple[str, str],
            threading.Lock,
        ] = {}

    def is_client_allowed(self, client_ip: str | None) -> bool:
        try:
            address = ipaddress.ip_address(client_ip)
        except (TypeError, ValueError):
            return False
        return any(
            address.version == network.version
            and address in network
            for network in self.config.allowed_networks
        )

    def resolve(
        self,
        client_ip: str | None,
        *,
        force_refresh: bool = False,
    ) -> CapportState:
        started = self._monotonic()
        try:
            normalized_ip = str(ipaddress.ip_address(client_ip))
        except (TypeError, ValueError):
            return self._state(
                started=started,
                allowed=False,
                client_ip=str(client_ip or ""),
                reason="INVALID_CLIENT_IP",
            )

        if not self.is_client_allowed(normalized_ip):
            return self._state(
                started=started,
                allowed=False,
                client_ip=normalized_ip,
                reason="CLIENT_NOT_ALLOWED",
            )

        try:
            resolved = self._resolve_allowed_client(
                normalized_ip,
                force_identity_refresh=force_refresh,
            )
            if resolved.client is None:
                self._emit(
                    events.CAPPORT_CLIENT_NOT_FOUND,
                    client_ip=normalized_ip,
                    site_id=self.config.site_id,
                    cache_hit=resolved.cache_hit,
                )
                state = self._state(
                    started=started,
                    client_ip=normalized_ip,
                    reason=resolved.reason,
                    cache_hit=resolved.cache_hit,
                )
            else:
                client = resolved.client
                self._emit(
                    events.CAPPORT_CLIENT_RESOLVED,
                    client_ip=client.client_ip,
                    client_mac=client.client_mac,
                    site_id=client.site_id,
                    auth_status=client.auth_status,
                    active=client.active,
                    cache_hit=resolved.cache_hit,
                )
                state = self._state(
                    started=started,
                    client_ip=normalized_ip,
                    client=client,
                    reason=resolved.reason,
                    cache_hit=resolved.cache_hit,
                )
            self._emit_state(state)
            return state
        except _LookupFailure as exc:
            self._emit(
                events.CAPPORT_LOOKUP_FAILED,
                "error",
                client_ip=normalized_ip,
                reason=exc.reason,
                fallback_captive=True,
                cache_hit=exc.cache_hit,
            )
            state = self._state(
                started=started,
                client_ip=normalized_ip,
                reason=exc.reason,
                cache_hit=exc.cache_hit,
                lookup_failed=True,
            )
            self._emit_state(state)
            return state
        except Exception as exc:
            logger.exception(
                "capport.lookup_failed client_ip=%s",
                normalized_ip,
            )
            reason = type(exc).__name__.upper()
            self._store_failure(reason)
            self._emit(
                events.CAPPORT_LOOKUP_FAILED,
                "error",
                client_ip=normalized_ip,
                reason=reason,
                fallback_captive=True,
            )
            state = self._state(
                started=started,
                client_ip=normalized_ip,
                reason=reason,
                lookup_failed=True,
            )
            self._emit_state(state)
            return state

    def resolve_for_login(
        self,
        client_ip: str | None,
    ) -> CapportState:
        """
        Resolve login clients without reusing a cached not-found result.

        A newly joined device may be absent from the first site identity
        snapshot. Login retries force a new identity refresh, while
        retaining the bounded attempt count and failure cooldown.
        """
        started = self._monotonic()
        state = self.resolve(client_ip)
        if (
            not state.allowed
            or state.client_found
            or state.lookup_failed
            or state.reason != "CLIENT_NOT_FOUND"
        ):
            return state

        deadline = started + LOGIN_LOOKUP_MAX_WAIT_SECONDS
        for _attempt in range(1, LOGIN_LOOKUP_ATTEMPTS):
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                break
            self._sleep(
                min(LOGIN_LOOKUP_INTERVAL_SECONDS, remaining)
            )
            if self._monotonic() >= deadline:
                break

            state = self.resolve(
                client_ip,
                force_refresh=True,
            )
            if (
                state.client_found
                or state.lookup_failed
                or not state.allowed
                or state.reason != "CLIENT_NOT_FOUND"
            ):
                return state
        return state

    def _resolve_allowed_client(
        self,
        client_ip: str,
        *,
        force_identity_refresh: bool,
    ) -> _ResolvedClient:
        refresh_identity = force_identity_refresh
        for _attempt in range(IDENTITY_CHANGE_ATTEMPTS):
            identity, identity_cache_hit = (
                self._get_identity_snapshot(
                    force_refresh=refresh_identity,
                )
            )
            refresh_identity = False
            if client_ip in identity.ambiguous_ips:
                raise _LookupFailure("DUPLICATE_CLIENT_IP")

            client_mac = identity.mac_by_ip.get(client_ip)
            if client_mac is None:
                return _ResolvedClient(
                    client=None,
                    reason="CLIENT_NOT_FOUND",
                    cache_hit=identity_cache_hit,
                )

            try:
                return self._get_authoritative_state(
                    client_ip=client_ip,
                    client_mac=client_mac,
                    identity_generation=identity.generation,
                )
            except _IdentityChanged:
                continue

        raise _LookupFailure("IDENTITY_CHANGED")

    def _get_identity_snapshot(
        self,
        *,
        force_refresh: bool,
    ) -> tuple[_IdentitySnapshot, bool]:
        site_id = self.config.site_id
        requested_at = self._monotonic()
        with self._cache_lock:
            cached = self._get_cached_identity(
                site_id,
                requested_at,
            )
            requested_generation = (
                cached.generation if cached is not None else -1
            )
            if cached is not None and not force_refresh:
                return cached, True
            failure = self._get_failure(site_id, requested_at)
            if failure is not None:
                raise _LookupFailure(
                    failure.reason,
                    cache_hit=True,
                )
            refresh_lock = self._identity_refresh_locks.setdefault(
                site_id,
                threading.Lock(),
            )

        # The site lock protects only the paginated get_clients refresh.
        with refresh_lock:
            now = self._monotonic()
            with self._cache_lock:
                cached = self._get_cached_identity(site_id, now)
                if cached is not None and (
                    not force_refresh
                    or cached.generation > requested_generation
                ):
                    return cached, True
                failure = self._get_failure(site_id, now)
                if failure is not None:
                    raise _LookupFailure(
                        failure.reason,
                        cache_hit=True,
                    )

            result = self._call_controller(
                "CLIENT_LIST_EXCEPTION",
                self.controller.get_clients,
                site_id,
            )
            if not result.success:
                reason = str(
                    result.error or "LOOKUP_FAILED"
                ).upper()
                self._store_failure(reason)
                raise _LookupFailure(reason)

            raw_clients = result.data.get("clients")
            if not isinstance(raw_clients, list):
                self._store_failure("MALFORMED_RESPONSE")
                raise _LookupFailure("MALFORMED_RESPONSE")

            with self._cache_lock:
                previous = self._identity_cache.get(site_id)
                generation = (
                    previous.generation + 1
                    if previous is not None
                    else 0
                )
            snapshot = self._build_identity_snapshot(
                raw_clients,
                generation=generation,
            )
            with self._cache_lock:
                self._identity_cache[site_id] = snapshot
                self._prune_site_state(site_id, snapshot)
            return snapshot, False

    def _build_identity_snapshot(
        self,
        raw_clients: list[Any],
        *,
        generation: int,
    ) -> _IdentitySnapshot:
        grouped: dict[str, list[tuple[str, bool | None]]] = {}
        for raw in raw_clients:
            if not isinstance(raw, dict):
                continue
            try:
                client_ip = str(
                    ipaddress.ip_address(raw.get("client_ip"))
                )
            except (TypeError, ValueError):
                continue
            client_mac = raw.get("client_mac")
            if not isinstance(client_mac, str) or not client_mac:
                continue
            grouped.setdefault(client_ip, []).append(
                (
                    client_mac,
                    self._optional_bool(raw.get("active")),
                )
            )

        mac_by_ip: dict[str, str] = {}
        ambiguous: set[str] = set()
        for client_ip, identities in grouped.items():
            selected = self._select_identity(identities)
            if selected is None:
                ambiguous.add(client_ip)
                logger.warning(
                    "capport.duplicate_client_ip "
                    "site_id=%s client_ip=%s",
                    self.config.site_id,
                    client_ip,
                )
            else:
                mac_by_ip[client_ip] = selected

        refreshed_at = self._monotonic()
        return _IdentitySnapshot(
            expires_at=(
                refreshed_at + self.config.cache_ttl_seconds
            ),
            generation=generation,
            mac_by_ip=mac_by_ip,
            ambiguous_ips=frozenset(ambiguous),
        )

    def _get_authoritative_state(
        self,
        *,
        client_ip: str,
        client_mac: str,
        identity_generation: int,
    ) -> _ResolvedClient:
        site_id = self.config.site_id
        lock_key = (site_id, client_ip)
        now = self._monotonic()
        with self._cache_lock:
            cached = self._get_cached_state(site_id, client_ip, now)
            cached = self._validate_cached_state(
                site_id,
                client_ip,
                cached,
                client_mac=client_mac,
                identity_generation=identity_generation,
            )
            if cached is not None:
                return _ResolvedClient(
                    client=cached.client,
                    reason=self._state_reason(cached.client),
                    cache_hit=True,
                )
            failure = self._get_failure(site_id, now)
            if failure is not None:
                raise _LookupFailure(
                    failure.reason,
                    cache_hit=True,
                )
            refresh_lock = self._state_refresh_locks.setdefault(
                lock_key,
                threading.Lock(),
            )

        # Different client IPs have different locks and can run in parallel.
        with refresh_lock:
            now = self._monotonic()
            with self._cache_lock:
                cached = self._get_cached_state(
                    site_id,
                    client_ip,
                    now,
                )
                cached = self._validate_cached_state(
                    site_id,
                    client_ip,
                    cached,
                    client_mac=client_mac,
                    identity_generation=identity_generation,
                )
                if cached is not None:
                    return _ResolvedClient(
                        client=cached.client,
                        reason=self._state_reason(cached.client),
                        cache_hit=True,
                    )
                failure = self._get_failure(site_id, now)
                if failure is not None:
                    raise _LookupFailure(
                        failure.reason,
                        cache_hit=True,
                    )

            try:
                result = self.controller.get_client(
                    site_id,
                    client_mac,
                )
            except Exception:
                logger.exception(
                    "capport.controller_exception "
                    "operation=get_client"
                )
                with self._cache_lock:
                    if not self._identity_matches(
                        site_id,
                        client_ip,
                        client_mac,
                        identity_generation,
                    ):
                        raise _IdentityChanged
                    self._store_failure(
                        "GET_CLIENT_EXCEPTION"
                    )
                raise _LookupFailure("GET_CLIENT_EXCEPTION")

            with self._cache_lock:
                if not self._identity_matches(
                    site_id,
                    client_ip,
                    client_mac,
                    identity_generation,
                ):
                    raise _IdentityChanged
                if not result.success:
                    reason = str(
                        result.error or "CLIENT_STATE_FAILED"
                    ).upper()
                    self._store_failure(reason)
                    raise _LookupFailure(reason)

            auth_status = self._optional_int(
                result.data.get("authStatus")
            )
            if auth_status is None:
                with self._cache_lock:
                    if not self._identity_matches(
                        site_id,
                        client_ip,
                        client_mac,
                        identity_generation,
                    ):
                        raise _IdentityChanged
                    self._store_failure(
                        "MALFORMED_CLIENT_STATE"
                    )
                raise _LookupFailure("MALFORMED_CLIENT_STATE")

            client = CapportClient(
                site_id=site_id,
                client_ip=client_ip,
                client_mac=client_mac,
                auth_status=auth_status,
                active=self._optional_bool(
                    result.data.get("active")
                ),
            )
            cached = _CachedClientState(
                expires_at=(
                    self._monotonic()
                    + self.config.cache_ttl_seconds
                ),
                identity_generation=identity_generation,
                client=client,
            )
            with self._cache_lock:
                if not self._identity_matches(
                    site_id,
                    client_ip,
                    client_mac,
                    identity_generation,
                ):
                    raise _IdentityChanged
                self._state_cache.setdefault(
                    site_id,
                    {},
                )[client_ip] = cached
            return _ResolvedClient(
                client=client,
                reason=self._state_reason(client),
                cache_hit=False,
            )

    def _call_controller(
        self,
        error_reason: str,
        operation,
        *args,
    ):
        try:
            return operation(*args)
        except Exception:
            logger.exception(
                "capport.controller_exception operation=%s",
                getattr(operation, "__name__", "unknown"),
            )
            self._store_failure(error_reason)
            raise _LookupFailure(error_reason)

    def _get_cached_identity(
        self,
        site_id: str,
        now: float,
    ) -> _IdentitySnapshot | None:
        cached = self._identity_cache.get(site_id)
        if cached is None:
            return None
        if cached.expires_at > now:
            return cached
        return None

    def _get_cached_state(
        self,
        site_id: str,
        client_ip: str,
        now: float,
    ) -> _CachedClientState | None:
        cached = self._state_cache.get(site_id, {}).get(client_ip)
        if cached is None:
            return None
        if cached.expires_at > now:
            return cached
        self._state_cache.get(site_id, {}).pop(client_ip, None)
        return None

    def _validate_cached_state(
        self,
        site_id: str,
        client_ip: str,
        cached: _CachedClientState | None,
        *,
        client_mac: str,
        identity_generation: int,
    ) -> _CachedClientState | None:
        if cached is None:
            return None
        if (
            cached.client.client_mac == client_mac
            and cached.identity_generation == identity_generation
        ):
            return cached
        self._state_cache.get(site_id, {}).pop(client_ip, None)
        return None

    def _identity_matches(
        self,
        site_id: str,
        client_ip: str,
        client_mac: str,
        identity_generation: int,
    ) -> bool:
        identity = self._identity_cache.get(site_id)
        return (
            identity is not None
            and identity.generation == identity_generation
            and identity.mac_by_ip.get(client_ip) == client_mac
        )

    def _get_failure(
        self,
        site_id: str,
        now: float,
    ) -> _FailureCooldown | None:
        failure = self._failure_cache.get(site_id)
        if failure is None:
            return None
        if failure.expires_at > now:
            return failure
        self._failure_cache.pop(site_id, None)
        return None

    def _store_failure(self, reason: str) -> None:
        with self._cache_lock:
            self._failure_cache[self.config.site_id] = (
                _FailureCooldown(
                    expires_at=(
                        self._monotonic()
                        + self.config.failure_cache_ttl_seconds
                    ),
                    reason=reason,
                )
            )

    def _prune_site_state(
        self,
        site_id: str,
        identity: _IdentitySnapshot,
    ) -> None:
        now = self._monotonic()
        valid_ips = set(identity.mac_by_ip)
        site_states = self._state_cache.get(site_id, {})
        for client_ip, cached in list(site_states.items()):
            if (
                cached.expires_at <= now
                or client_ip not in valid_ips
                or cached.client.client_mac
                != identity.mac_by_ip.get(client_ip)
                or cached.identity_generation != identity.generation
            ):
                site_states.pop(client_ip, None)
        if not site_states:
            self._state_cache.pop(site_id, None)

        for lock_key, state_lock in list(
            self._state_refresh_locks.items()
        ):
            lock_site_id, client_ip = lock_key
            if (
                lock_site_id == site_id
                and client_ip not in valid_ips
                and not state_lock.locked()
            ):
                self._state_refresh_locks.pop(lock_key, None)

    @staticmethod
    def _select_identity(
        identities: list[tuple[str, bool | None]],
    ) -> str | None:
        if len(identities) == 1:
            return identities[0][0]
        active = [
            client_mac
            for client_mac, is_active in identities
            if is_active is True
        ]
        if len(active) == 1:
            return active[0]
        return None

    @staticmethod
    def _state_reason(client: CapportClient) -> str:
        return (
            "AUTHORIZED"
            if client.auth_status == 2
            else "CAPTIVE"
        )

    def _state(
        self,
        *,
        started: float,
        client_ip: str,
        allowed: bool = True,
        client: CapportClient | None = None,
        reason: str,
        cache_hit: bool = False,
        lookup_failed: bool = False,
    ) -> CapportState:
        return CapportState(
            allowed=allowed,
            captive=(client is None or client.auth_status != 2),
            client_found=client is not None,
            client_ip=client_ip,
            client=client,
            reason=reason,
            cache_hit=cache_hit,
            lookup_failed=lookup_failed,
            response_time_ms=round(
                (self._monotonic() - started) * 1000,
                2,
            ),
        )

    def _emit_state(self, state: CapportState) -> None:
        self._emit(
            events.CAPPORT_STATE_RESPONSE,
            client_ip=state.client_ip,
            client_mac=(
                state.client.client_mac
                if state.client is not None
                else None
            ),
            site_id=self.config.site_id,
            client_found=state.client_found,
            auth_status=(
                state.client.auth_status
                if state.client is not None
                else None
            ),
            active=(
                state.client.active
                if state.client is not None
                else None
            ),
            captive=state.captive,
            cache_hit=state.cache_hit,
            response_time_ms=state.response_time_ms,
            reason=state.reason,
        )

    def _emit(
        self,
        event: str,
        level: str = "info",
        **fields: Any,
    ) -> None:
        try:
            self._telemetry.safe_emit_system(
                event,
                level,
                **fields,
            )
        except Exception:
            logger.exception("capport.telemetry_failed event=%s", event)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_bool(value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        return None
