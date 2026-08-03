import json
import os
import stat

import pytest

from app.pending_sessions import CleanerTelemetryAdapter, JournalWriteError, JournalWriter


class CaptureTelemetry:
    def __init__(self, *, raises=False, returns=True):
        self.raises = raises
        self.returns = returns
        self.calls = []

    def safe_emit_system(self, event, *, level, **fields):
        self.calls.append((event, level, fields))
        if self.raises:
            raise RuntimeError("telemetry unavailable")
        return self.returns


def test_journal_writes_compact_json_flushes_and_sets_private_mode(tmp_path):
    path = tmp_path / "pending.log"
    writer = JournalWriter(str(path), max_bytes=1024, backup_count=1)

    writer.write_and_flush(
        {"event": "scan_completed", "message": "Привет", "count": 1},
        fsync=True,
    )
    writer.close()

    line = path.read_text(encoding="utf-8").strip()
    assert json.loads(line) == {
        "event": "scan_completed",
        "message": "Привет",
        "count": 1,
    }
    assert ": " not in line
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_journal_rejects_nan_and_write_after_close(tmp_path):
    path = tmp_path / "pending.log"
    writer = JournalWriter(str(path), max_bytes=1024, backup_count=1)

    with pytest.raises(JournalWriteError, match="serialize failed"):
        writer.write_and_flush({"value": float("nan")})

    writer.close()
    with pytest.raises(JournalWriteError, match="writer closed"):
        writer.write_and_flush({"event": "late"})


def test_journal_close_is_idempotent(tmp_path):
    writer = JournalWriter(str(tmp_path / "pending.log"), max_bytes=1024, backup_count=1)
    writer.close()
    writer.close()


def test_telemetry_adds_component_and_preserves_fields():
    capture = CaptureTelemetry()
    adapter = CleanerTelemetryAdapter(capture)

    emitted = adapter.safe_emit_system(
        "scan_started",
        level="warning",
        scan_id="scan-1",
    )

    assert emitted is True
    assert capture.calls == [
        (
            "scan_started",
            "warning",
            {"component": "pending_session_cleaner", "scan_id": "scan-1"},
        )
    ]


def test_telemetry_is_fail_open():
    adapter = CleanerTelemetryAdapter(CaptureTelemetry(raises=True))
    assert adapter.safe_emit_system("scan_failed") is False
