import json

from app.models import Result
from app.pending_sessions.action_guard import ActionGuard
from app.pending_sessions.cleaner import PendingClientSessionCleaner
from app.pending_sessions.config import PendingSessionCleanerConfig
from app.pending_sessions.journal import JournalWriter
from app.pending_sessions.models import ProtectionDecision
from app.pending_sessions.telemetry import CleanerTelemetryAdapter


def make_config(path, **changes):
    values = {
        "enabled": True,
        "site_id": "site-1",
        "ssids": ("Guest",),
        "initial_delay_seconds": 0.0,
        "scan_interval_seconds": 60.0,
        "max_scan_duration_seconds": 50.0,
        "min_uptime_seconds": 120,
        "portal_grace_seconds": 45.0,
        "uptime_regression_tolerance_seconds": 5.0,
        "request_timeout_seconds": 5.0,
        "get_retry_delays_seconds": (0.0, 0.0),
        "verify_delays_seconds": (0.0, 0.0),
        "page_size": 500,
        "max_pages": 20,
        "max_clients": 10000,
        "max_actions_per_scan": 1,
        "action_cooldown_seconds": 180.0,
        "max_actions_per_mac_per_hour": 3,
        "log_file": str(path),
        "rotation_max_bytes": 1024 * 1024,
        "rotation_backup_count": 2,
        "shutdown_timeout_seconds": 20.0,
    }
    values.update(changes)
    return PendingSessionCleanerConfig(**values)


def client(*, active=True, auth_status=1, uptime=180):
    return {
        "mac": "AA-BB-CC-DD-EE-FF",
        "wireless": True,
        "active": active,
        "authStatus": auth_status,
        "uptime": uptime,
        "ssid": "Guest",
        "blocked": False,
        "ip": "192.168.1.10",
        "apMac": "11-22-33-44-55-66",
        "radioId": 0,
        "channel": 11,
        "rssi": -60,
        "snr": 30,
    }


class Provider:
    def __init__(self, *, pages, states, reconnect=None):
        self.pages = list(pages)
        self.states = list(states)
        self.reconnect_result = reconnect or Result.ok(
            message="Success.",
            data={
                "http_status": 200,
                "error_code": 0,
                "command_accepted": True,
            },
        )
        self.post_calls = 0

    def list_active_clients(self, **kwargs):
        return self.pages.pop(0)

    def get_pending_client_state(self, **kwargs):
        return self.states.pop(0)

    def reconnect_client(self, **kwargs):
        self.post_calls += 1
        return self.reconnect_result


class Protection:
    def __init__(self, decisions=None):
        self.decisions = list(decisions or [])

    def check(self, **kwargs):
        if self.decisions:
            return self.decisions.pop(0)
        return ProtectionDecision(False)


class Telemetry:
    def safe_emit_system(self, *args, **kwargs):
        return True


def page(rows, total=None):
    return Result.ok(
        data={
            "clients": rows,
            "total_rows": len(rows) if total is None else total,
        }
    )


def state(row):
    return Result.ok(
        data={
            "client": row,
            "http_status": 200,
            "error_code": 0,
        }
    )


def read_events(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def build(tmp_path, provider, protection=None, **changes):
    path = tmp_path / "pending.log"
    cfg = make_config(path, **changes)
    cleaner = PendingClientSessionCleaner(
        config=cfg,
        provider=provider,
        protection=protection or Protection(),
        journal=JournalWriter(
            str(path),
            max_bytes=1024 * 1024,
            backup_count=2,
        ),
        telemetry=CleanerTelemetryAdapter(Telemetry()),
        action_guard=ActionGuard(
            cooldown_seconds=cfg.action_cooldown_seconds,
            max_actions_per_mac_per_hour=3,
        ),
    )
    return cleaner, path


def test_complete_pipeline_reconnects_and_verifies(tmp_path):
    provider = Provider(
        pages=[page([client()])],
        states=[
            state(client(uptime=181)),
            state({"active": False}),
        ],
    )
    cleaner, path = build(tmp_path, provider)

    summary = cleaner.run_once()
    cleaner.close()

    assert provider.post_calls == 1
    assert summary.reconnect_attempted_count == 1
    assert summary.reconnect_confirmed_count == 1
    assert summary.scan_result == "success"
    events = read_events(path)
    assert [item["event"] for item in events] == [
        "pending_session.action.planned",
        "pending_session.action.completed",
        "pending_session.scan.completed",
    ]
    assert events[1]["result"] == "confirmed_disconnected"


def test_partial_inventory_never_sends_post(tmp_path):
    provider = Provider(
        pages=[page([client()], total=2)],
        states=[],
    )
    cleaner, path = build(tmp_path, provider, max_pages=1)

    summary = cleaner.run_once()
    cleaner.close()

    assert summary.inventory_complete is False
    assert summary.scan_result == "partial"
    assert provider.post_calls == 0


def test_local_protection_blocks_preflight_and_post(tmp_path):
    provider = Provider(
        pages=[page([client()])],
        states=[],
    )
    cleaner, path = build(
        tmp_path,
        provider,
        Protection(
            [ProtectionDecision(True, "active_auth_run")]
        ),
    )

    summary = cleaner.run_once()
    cleaner.close()

    assert summary.local_protected_count == 1
    assert provider.post_calls == 0
    completed = [
        event
        for event in read_events(path)
        if event["event"] == "pending_session.action.completed"
    ]
    assert completed[0]["result"] == "skipped_local_auth_active"


def test_authorized_preflight_is_never_disconnected(tmp_path):
    provider = Provider(
        pages=[page([client()])],
        states=[state(client(auth_status=2, uptime=181))],
    )
    cleaner, path = build(tmp_path, provider)

    summary = cleaner.run_once()
    cleaner.close()

    assert summary.preflight_rejected_count == 1
    assert provider.post_calls == 0
    completed = [
        event
        for event in read_events(path)
        if event["event"] == "pending_session.action.completed"
    ]
    assert completed[0]["result"] == "skipped_authorized"


def test_new_session_after_reconnect_is_confirmed(tmp_path):
    provider = Provider(
        pages=[page([client(uptime=300)])],
        states=[
            state(client(uptime=301)),
            state(client(uptime=2)),
        ],
    )
    cleaner, path = build(tmp_path, provider)

    summary = cleaner.run_once()
    cleaner.close()

    assert summary.reconnect_confirmed_count == 1
    completed = [
        event
        for event in read_events(path)
        if event["event"] == "pending_session.action.completed"
    ]
    assert completed[0]["result"] == "confirmed_new_session"
