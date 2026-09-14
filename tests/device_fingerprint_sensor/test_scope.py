from ipaddress import ip_network

from app.device_fingerprint_sensor.scope import (
    DHCP_LEASE_CACHE_MAX_ENTRIES, DHCP_TRANSACTION_MAX_ENTRIES,
    DhcpScopeResolver,
)


class Clock:
    value = 0.0
    def __call__(self):
        return self.value


def resolver(clock):
    return DhcpScopeResolver((ip_network("192.168.8.0/22"),), "192.168.10.1", "192.168.10.1", monotonic=clock)


def test_transaction_confirmation_releases_once_and_does_not_extend_ttl():
    clock = Clock(); scope = resolver(clock)
    event = {"kind": "discover"}
    assert scope.client("00:11:22:33:44:55", 1, event, directly_scoped=False) == []
    clock.value = 119
    assert scope.server_reply("00:11:22:33:44:55", 1, yiaddr="192.168.8.2", server_source="192.168.10.1", option54="192.168.10.1") == [event]
    assert scope.server_reply("00:11:22:33:44:55", 1, yiaddr="192.168.8.2", server_source="192.168.10.1", option54="192.168.10.1") == []
    clock.value = 120
    assert scope.client("00:11:22:33:44:55", 1, event, directly_scoped=False) == []


def test_pending_limit_ninth_event_invalidates_transaction():
    clock = Clock(); scope = resolver(clock)
    for index in range(8):
        assert scope.client("00:11:22:33:44:55", 2, {"index": index}, directly_scoped=False) == []
    scope.client("00:11:22:33:44:55", 2, {"index": 8}, directly_scoped=False)
    assert scope.transaction_count == 0


def test_oldest_transaction_is_evicted_at_4096():
    clock = Clock(); scope = resolver(clock)
    for xid in range(DHCP_TRANSACTION_MAX_ENTRIES + 1):
        scope.client("00:11:22:33:44:55", xid, {"xid": xid}, directly_scoped=False)
    assert scope.transaction_count == DHCP_TRANSACTION_MAX_ENTRIES
    assert ("00:11:22:33:44:55", 0) not in scope._transactions


def test_conflicting_confirmed_fact_fails_closed():
    clock = Clock(); scope = resolver(clock)
    scope.client("00:11:22:33:44:55", 3, {"x": 1}, directly_scoped=False)
    assert scope.server_reply("00:11:22:33:44:55", 3, yiaddr="192.168.8.2", server_source="192.168.10.1", option54="192.168.10.1")
    assert scope.server_reply("00:11:22:33:44:55", 3, yiaddr="192.168.8.3", server_source="192.168.10.1", option54="192.168.10.1") == []
    assert scope.transaction_count == 0


def test_confirmed_transaction_binding_is_exact_mac_xid_and_ip():
    clock = Clock(); scope = resolver(clock)
    scope.server_reply("00:11:22:33:44:55", 30, yiaddr="192.168.8.2", server_source="192.168.10.1", option54="192.168.10.1")
    assert scope.transaction_proves("00:11:22:33:44:55", 30, "192.168.8.2")
    assert not scope.transaction_proves("00:11:22:33:44:55", 31, "192.168.8.2")
    assert not scope.transaction_proves("00:11:22:33:44:56", 30, "192.168.8.2")
    assert not scope.transaction_proves("00:11:22:33:44:55", 30, "192.168.8.3")


def test_lease_refresh_replace_expire_and_cache_miss():
    clock = Clock(); scope = resolver(clock)
    scope.server_reply("00:11:22:33:44:55", 4, yiaddr="192.168.8.2", server_source="192.168.10.1", option54="192.168.10.1", lease_seconds=10, is_ack=True)
    assert scope.lease_proves("00:11:22:33:44:55", "192.168.8.2")
    clock.value = 5
    scope.server_reply("00:11:22:33:44:55", 5, yiaddr="192.168.8.3", server_source="192.168.10.1", option54="192.168.10.1", lease_seconds=10, is_ack=True)
    assert not scope.lease_proves("00:11:22:33:44:55", "192.168.8.2")
    assert scope.lease_proves("00:11:22:33:44:55", "192.168.8.3")
    clock.value = 15
    assert not scope.lease_proves("00:11:22:33:44:55", "192.168.8.3")


def test_lease_cache_is_bounded_by_earliest_expiry():
    clock = Clock(); scope = resolver(clock)
    for xid in range(DHCP_LEASE_CACHE_MAX_ENTRIES + 1):
        mac = f"02:00:{(xid >> 24) & 255:02x}:{(xid >> 16) & 255:02x}:{(xid >> 8) & 255:02x}:{xid & 255:02x}"
        ip = f"192.168.{8 + ((xid // 254) % 4)}.{1 + xid % 254}"
        scope.server_reply(mac, xid, yiaddr=ip, server_source="192.168.10.1", option54="192.168.10.1", lease_seconds=100 + xid, is_ack=True)
    assert scope.lease_count == DHCP_LEASE_CACHE_MAX_ENTRIES
