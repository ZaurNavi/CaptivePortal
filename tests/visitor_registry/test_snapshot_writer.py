from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.visitor_registry.snapshot_writer import (
    VisitorSnapshotWriteError,
    VisitorSnapshotWriter,
)


def make_writer(path: Path, max_bytes: int = 1_000_000):
    return VisitorSnapshotWriter(
        str(path),
        rotation_max_bytes=max_bytes,
        rotation_backup_count=2,
    )


def test_writer_creates_compact_utf8_jsonl(tmp_path):
    path = tmp_path / "visitor.log"
    writer = make_writer(path)
    assert writer.initialize()
    writer.write({"event": "captured", "name": "Azərbaycan"})
    writer.close()
    raw = path.read_text(encoding="utf-8")
    assert raw == '{"event":"captured","name":"Azərbaycan"}\n'
    assert json.loads(raw)["name"] == "Azərbaycan"


def test_writer_initialization_is_idempotent(tmp_path):
    writer = make_writer(tmp_path / "visitor.log")
    assert writer.initialize()
    first = writer._handler
    assert writer.initialize()
    assert writer._handler is first
    writer.close()


def test_writer_rejects_nan_and_surrogate(tmp_path):
    writer = make_writer(tmp_path / "visitor.log")
    assert writer.initialize()
    with pytest.raises(VisitorSnapshotWriteError):
        writer.write({"value": float("nan")})
    with pytest.raises(VisitorSnapshotWriteError):
        writer.write({"value": "\ud800"})
    writer.close()


def test_rotation_keeps_valid_json_lines(tmp_path):
    path = tmp_path / "visitor.log"
    writer = make_writer(path, max_bytes=90)
    assert writer.initialize()
    for index in range(10):
        writer.write({"event": "captured", "index": index})
    writer.close()
    rotated = list(tmp_path.glob("visitor.log.*"))
    assert rotated
    for candidate in [path, *rotated]:
        for line in candidate.read_text(encoding="utf-8").splitlines():
            assert isinstance(json.loads(line), dict)


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode only")
def test_writer_uses_0640_on_posix(tmp_path):
    path = tmp_path / "visitor.log"
    writer = make_writer(path)
    assert writer.initialize()
    assert path.stat().st_mode & 0o777 == 0o640
    writer.close()


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode only")
def test_writer_restores_0640_after_rotation(tmp_path):
    path = tmp_path / "visitor.log"
    writer = make_writer(path, max_bytes=60)
    assert writer.initialize()
    for index in range(10):
        writer.write({"event": "captured", "index": index})
    assert path.stat().st_mode & 0o777 == 0o640
    writer.close()
