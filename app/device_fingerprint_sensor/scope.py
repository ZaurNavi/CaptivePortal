"""Bounded DHCP guest-scope correlation and lease authority."""

from __future__ import annotations

import ipaddress
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable

DHCP_TRANSACTION_TTL_SECONDS = 120.0
DHCP_TRANSACTION_MAX_ENTRIES = 4096
DHCP_TRANSACTION_MAX_PENDING_CLIENT_EVENTS = 8
DHCP_LEASE_CACHE_MAX_ENTRIES = 4096


@dataclass(slots=True)
class _Transaction:
    first_seen: float
    sequence: int
    pending: list[dict[str, Any]] = field(default_factory=list)
    confirmed: tuple[str, str, str] | None = None


@dataclass(slots=True)
class _Lease:
    expires: float
    sequence: int


class DhcpScopeResolver:
    def __init__(self, guest_cidrs: tuple[Any, ...], server: str, option54: str, *, monotonic: Callable[[], float]) -> None:
        self._guest = guest_cidrs
        self._server = server
        self._option54 = option54
        self._clock = monotonic
        self._transactions: OrderedDict[tuple[str, int], _Transaction] = OrderedDict()
        self._leases: dict[tuple[str, str, str], _Lease] = {}
        self._sequence = 0

    def client(self, mac: str, xid: int, event: dict[str, Any], *, directly_scoped: bool) -> list[dict[str, Any]]:
        now = self._clock()
        self._purge(now)
        if directly_scoped:
            return [event]
        key = (mac, xid)
        tx = self._transactions.get(key)
        if tx is None:
            tx = self._new_transaction(key, now)
        if tx.confirmed is not None:
            return [event]
        if len(tx.pending) >= DHCP_TRANSACTION_MAX_PENDING_CLIENT_EVENTS:
            del self._transactions[key]
            return []
        tx.pending.append(dict(event))
        return []

    def server_reply(self, mac: str, xid: int, *, yiaddr: str, server_source: str,
                     option54: str, lease_seconds: int | None = None,
                     is_ack: bool = False) -> list[dict[str, Any]]:
        now = self._clock()
        self._purge(now)
        key = (mac, xid)
        tx = self._transactions.get(key)
        if tx is None:
            tx = self._new_transaction(key, now)
        fact = (yiaddr, server_source, option54)
        valid = (
            self._inside(yiaddr)
            and server_source == self._server
            and option54 == self._option54
        )
        if not valid:
            if tx.confirmed is not None:
                del self._transactions[key]
            return []
        if tx.confirmed is not None and tx.confirmed != fact:
            del self._transactions[key]
            return []
        released = list(tx.pending) if tx.confirmed is None else []
        tx.pending.clear()
        tx.confirmed = fact
        if is_ack:
            self._record_lease(mac, yiaddr, server_source, lease_seconds, now)
        return released

    def lease_proves(self, mac: str, ip: str) -> bool:
        now = self._clock()
        self._purge(now)
        return (mac, ip, self._server) in self._leases

    def transaction_proves(self, mac: str, xid: int, ip: str) -> bool:
        now = self._clock()
        self._purge(now)
        tx = self._transactions.get((mac, xid))
        return bool(
            tx is not None
            and tx.confirmed == (ip, self._server, self._option54)
        )

    def _new_transaction(self, key: tuple[str, int], now: float) -> _Transaction:
        if len(self._transactions) >= DHCP_TRANSACTION_MAX_ENTRIES:
            self._transactions.popitem(last=False)
        self._sequence += 1
        tx = _Transaction(now, self._sequence)
        self._transactions[key] = tx
        return tx

    def _record_lease(self, mac: str, ip: str, server: str, lease_seconds: int | None, now: float) -> None:
        for key in tuple(self._leases):
            if key[0] == mac and key[2] == server and key[1] != ip:
                del self._leases[key]
        seconds = 3600 if lease_seconds is None else min(max(0, lease_seconds), 86400)
        key = (mac, ip, server)
        self._sequence += 1
        self._leases[key] = _Lease(now + seconds, self._sequence)
        if len(self._leases) > DHCP_LEASE_CACHE_MAX_ENTRIES:
            victim = min(self._leases, key=lambda item: (self._leases[item].expires, self._leases[item].sequence))
            del self._leases[victim]

    def _purge(self, now: float) -> None:
        for key, tx in tuple(self._transactions.items()):
            if now - tx.first_seen >= DHCP_TRANSACTION_TTL_SECONDS:
                del self._transactions[key]
        for key, lease in tuple(self._leases.items()):
            if now >= lease.expires:
                del self._leases[key]

    def _inside(self, value: str) -> bool:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            return False
        return any(address in network for network in self._guest)

    @property
    def transaction_count(self) -> int:
        return len(self._transactions)

    @property
    def lease_count(self) -> int:
        return len(self._leases)
