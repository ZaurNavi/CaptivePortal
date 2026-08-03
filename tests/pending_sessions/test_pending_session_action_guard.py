from app.pending_sessions.action_guard import ActionGuard


class Clock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value


def test_guard_enforces_scan_limit_cooldown_and_hourly_limit():
    clock = Clock()
    guard = ActionGuard(
        cooldown_seconds=10,
        max_actions_per_mac_per_hour=2,
        clock=clock,
    )
    base = {
        "client_mac": "AA:BB:CC:DD:EE:FF",
        "actions_this_scan": 0,
        "max_actions_per_scan": 1,
        "stopping": False,
        "inventory_complete": True,
        "budget_exhausted": False,
        "journal_available": True,
    }

    assert guard.check(**base).allowed is True
    guard.record_attempt(base["client_mac"])
    assert guard.check(**base).reason == "cooldown_active"

    clock.value += 11
    assert guard.check(**base).allowed is True
    guard.record_attempt(base["client_mac"])
    clock.value += 11
    assert guard.check(**base).reason == "hourly_action_limit"

    assert guard.check(
        **{**base, "actions_this_scan": 1}
    ).reason == "scan_action_limit"


def test_guard_rejects_unsafe_scan_states():
    guard = ActionGuard(
        cooldown_seconds=0,
        max_actions_per_mac_per_hour=3,
    )
    base = {
        "client_mac": "AA:BB:CC:DD:EE:FF",
        "actions_this_scan": 0,
        "max_actions_per_scan": 1,
        "stopping": False,
        "inventory_complete": True,
        "budget_exhausted": False,
        "journal_available": True,
    }
    assert guard.check(
        **{**base, "stopping": True}
    ).reason == "shutdown_started"
    assert guard.check(
        **{**base, "inventory_complete": False}
    ).reason == "incomplete_inventory"
    assert guard.check(
        **{**base, "budget_exhausted": True}
    ).reason == "scan_time_budget_exceeded"
    assert guard.check(
        **{**base, "journal_available": False}
    ).reason == "audit_unavailable"
