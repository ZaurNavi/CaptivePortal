import os
import hashlib
from dataclasses import replace
import pytest
from app.network_metadata.source import BinarySourceReader, continuity_anchor, decide_startup_generation
from . import store, record, configuration, BOOT


def test_reader_append_partial_and_crlf(tmp_path):
    path = tmp_path / "reader"
    path.write_bytes(b'{}\r\n{"partial":')
    fd = os.open(path, os.O_RDONLY)
    try:
        reader = BinarySourceReader(fd, max_record_bytes=4096)
        first = reader.read_batch(256, 1048576)
        assert [(item.data, item.start, item.end, item.byte_length) for item in first] == [(b"{}\r", 0, 4, 3)]
        assert first[0].source_record_sha256 == hashlib.sha256(b"{}\r").hexdigest()
        assert reader.tail_length == 11 and reader.retained_unfinished_bytes == 11
        with path.open("ab") as stream:
            stream.write(b"1}\n")
        second = reader.read_batch(256, 1048576)
        assert second[0].start == 4 and second[0].data == b'{"partial":1}'
        assert second[0].source_record_sha256 == hashlib.sha256(second[0].data).hexdigest()
    finally:
        os.close(fd)


def test_oversize_discard_and_final_tail_bounded(tmp_path):
    path = tmp_path / "reader"
    path.write_bytes(b"x" * 12000 + b"\n" + b"x" * 13000)
    fd = os.open(path, os.O_RDONLY)
    try:
        reader = BinarySourceReader(fd, max_record_bytes=4096)
        records = reader.read_batch(256, 1048576)
        assert len(records) == 1 and records[0].data is None and records[0].byte_length == 12000
        assert records[0].source_record_sha256 == hashlib.sha256(b"x" * 12000).hexdigest()
        assert reader.read_batch(256, 1048576) == []
        assert reader.tail_length == 13000 and reader.retained_unfinished_bytes == 0
        assert reader.scan_offset == 25001
        reader.reset(0)
        assert reader.read_batch(1, 1048576)[0].source_record_sha256 == records[0].source_record_sha256
    finally:
        os.close(fd)


def test_prefix_before_oversize_dedicated_batch(tmp_path):
    path = tmp_path / "reader"
    path.write_bytes(b"{}\n" + b"x" * 5000 + b"\n")
    fd = os.open(path, os.O_RDONLY)
    try:
        reader = BinarySourceReader(fd, max_record_bytes=4096)
        assert len(reader.read_batch(256, 1048576)) == 1
        assert reader.scan_offset == 3
        assert reader.read_batch(256, 1048576)[0].data is None
    finally:
        os.close(fd)


def test_exact_decision_order(tmp_path):
    with store(tmp_path) as state:
        generation, checkpoint = state.repo.load_active()
        info = os.fstat(state.fd)
        binding = state.config.capture_scope_binding
        assert decide_startup_generation(generation, checkpoint, BOOT, info, binding).action == "resume"
        assert decide_startup_generation(generation, checkpoint, "26716a71-d675-4c17-bbe2-9c66661fc0b7", None, binding).close_reason == "host_reboot_source_lost"
        assert decide_startup_generation(generation, checkpoint, BOOT, None, binding).action == "wait"
        assert decide_startup_generation(generation, checkpoint, BOOT, info, binding, continuity=False).close_reason == "continuity_anchor_mismatch"
        assert decide_startup_generation(generation, checkpoint, BOOT, info, replace(binding, binding_digest="f" * 64)).action == "cutover"
        assert continuity_anchor(state.fd, 0) == (0, 0, None)


def test_reader_restart_checkpoint_and_anchor(tmp_path):
    with store(tmp_path) as state:
        reader = BinarySourceReader(state.fd, max_record_bytes=4096)
        items = reader.read_batch(1, 1048576)
        anchor = continuity_anchor(state.fd, items[0].end)
        assert anchor[:2] == (0, items[0].end)
        restarted = BinarySourceReader(state.fd, max_record_bytes=4096, offset=items[0].end)
        assert restarted.read_batch(256, 1048576) == []


def test_discard_hash_streams_across_bounded_polls_without_retaining_tail(tmp_path):
    path = tmp_path / "stream-hash"
    data = b"x" * 2000000 + b"\r"
    path.write_bytes(data)
    fd = os.open(path, os.O_RDONLY)
    try:
        reader = BinarySourceReader(fd, max_record_bytes=4096)
        while not reader.at_eof:
            assert reader.read_batch(1, 65536) == []
            assert reader.retained_unfinished_bytes <= 4096
        assert reader.retained_unfinished_bytes == 0
        with path.open("ab") as stream:
            stream.write(b"\nnext\n")
        item = reader.read_batch(1, 65536)[0]
        assert item.data is None and item.source_record_sha256 == hashlib.sha256(data).hexdigest()
        next_item = reader.read_batch(1, 65536)[0]
        assert next_item.source_record_sha256 == hashlib.sha256(b"next").hexdigest()
    finally:
        os.close(fd)
