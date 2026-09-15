import queue
import threading

from app.device_fingerprint_portal.coalescer import PortalEvidenceCoalescer
from app.device_fingerprint_portal.models import QueuedPortalEvidence


class Clock:
    value = 0.0
    def __call__(self): return self.value


def item(key):
    return lambda admitted: QueuedPortalEvidence({"observed_at": "2026-09-15T00:00:00.000Z"}, key, admitted)


def test_atomic_admission_coalescing_expiry_and_queue_full_no_poison():
    clock = Clock(); coalescer = PortalEvidenceCoalescer(expiry_seconds=21600, max_entries=2, monotonic=clock)
    output = queue.Queue(maxsize=1); key = ("s", "m", "capport_login", "h")
    assert coalescer.try_admit(key, output, item(key)).status == "admitted"
    assert coalescer.try_admit(key, output, item(key)).status == "coalesced"
    other = ("s", "m2", "capport_login", "h")
    assert coalescer.try_admit(other, output, item(other)).status == "full"
    assert coalescer.expiry(other) is None
    output.get_nowait(); assert coalescer.try_admit(other, output, item(other)).status == "admitted"
    clock.value = 21601; output.get_nowait()
    assert coalescer.try_admit(key, output, item(key)).status == "admitted"


def test_capacity_evicts_only_after_successful_queue_admission_and_shorten_remove_work():
    clock = Clock(); coalescer = PortalEvidenceCoalescer(expiry_seconds=100, max_entries=1, monotonic=clock)
    output = queue.Queue(maxsize=1); one=("s","1","x","h"); two=("s","2","x","h")
    coalescer.try_admit(one, output, item(one)); assert coalescer.try_admit(two, output, item(two)).status == "full"
    assert coalescer.expiry(one) == 100
    output.get(); coalescer.try_admit(two, output, item(two)); assert coalescer.expiry(one) is None
    coalescer.shorten((two,), 10); assert coalescer.expiry(two) == 10
    coalescer.remove((two,)); assert len(coalescer) == 0


def test_six_hour_expiry_and_capacity_remain_bounded():
    clock = Clock()
    coalescer = PortalEvidenceCoalescer(
        expiry_seconds=21600,
        max_entries=2,
        monotonic=clock,
    )
    output = queue.Queue(maxsize=4)
    keys = [("s", str(index), "capport_login", "h") for index in range(3)]
    for key in keys:
        assert coalescer.try_admit(key, output, item(key)).status == "admitted"
    assert len(coalescer) == 2
    assert coalescer.expiry(keys[-1]) == 21600
    output.queue.clear()
    clock.value = 21600
    assert coalescer.try_admit(keys[-1], output, item(keys[-1])).status == "admitted"


def test_request_path_never_waits_for_contended_lock():
    lock = threading.Lock(); lock.acquire()
    coalescer = PortalEvidenceCoalescer(lock=lock)
    key=("s","m","x","h")
    assert coalescer.try_admit(key, queue.Queue(), item(key)).status == "busy"
    lock.release()
