from app.device_fingerprint_sensor.dedup import ExactFrameDeduplicator


def test_exact_frame_inside_250_microseconds_is_suppressed():
    dedup = ExactFrameDeduplicator("zefer-span-01")
    assert not dedup.is_duplicate(b"frame", 1_000_000)
    assert dedup.is_duplicate(b"frame", 1_250_000)
    assert (dedup.raw_packet_count, dedup.duplicate_packet_count, dedup.deduplicated_packet_count) == (2, 1, 1)


def test_long_interval_and_different_frames_are_not_suppressed():
    dedup = ExactFrameDeduplicator("zefer-span-01", max_entries=2)
    assert not dedup.is_duplicate(b"same", 0)
    assert not dedup.is_duplicate(b"same", 250_001)
    assert not dedup.is_duplicate(b"other", 250_002)
    assert dedup.raw_packet_count == dedup.duplicate_packet_count + dedup.deduplicated_packet_count


def test_negative_time_delta_is_not_duplicate():
    dedup = ExactFrameDeduplicator("zefer-span-01")
    assert not dedup.is_duplicate(b"same", 10)
    assert not dedup.is_duplicate(b"same", 9)
