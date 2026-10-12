"""Owner/TL-only native Linux synthetic acceptance preparation. NOT a gate PASS.

Run explicitly as a module in a clean exact-tree Lab worktree. It is not pytest
discovery and is never called by Coder focused tests. All DBs are disposable.
"""
from dataclasses import replace
from datetime import timedelta
import json
import os
from pathlib import Path
import platform
import sqlite3
import statistics
import subprocess
import tempfile
import threading
import time

from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.recognition_read_service import NetworkMetadataRecognitionReadService
from app.network_metadata.projection_source import NetworkMetadataProjectionSourceReadService
from app.network_metadata.validation import ni_timestamp
from app.network_metadata_projection.recognition_read_service import DeviceNetworkMetadataRecognitionReadService
from app.network_metadata_projection.models import RegistryEvaluation
from app.network_service_recognition.read_service import DeviceServiceRecognitionReadService
from tests.network_metadata import source_event, record, outcome
from tests.network_metadata_projection.support import stack, MAC
from .support import AT, bundle
from .test_protected_readers import store, DEVICE


def rss_bytes():
    return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")


def run_case(root, family, count=5000):
    event_at = "2026-10-11T23:59:00.123456Z"
    records = []
    for index in range(count):
        event = source_event(family, timestamp=event_at, dest_ip="203.0.113.93", proto="TCP", flow_id=index)
        if family == "dns":
            event["dns"]["queries"] = [dict(rrname=f"unadmitted{number}.example.invalid", rrtype="A") for number in range(5)]
            event["dns"]["answers"] = []
        else:
            event[family]["sni"] = "www.youtube.com"
        records.append(record(event))
    data = b"\n".join(records) + b"\n"
    with store(root, source=data) as source:
        source.clock.value = ni_timestamp(AT, canonical=True)
        offset, batch = 0, []
        for value in records:
            batch.append(outcome(source.config.capture_scope_binding, value, start=offset,
                generation=source.generation.source_generation_id))
            offset += len(value) + 1
            if len(batch) == 100:
                source.repo.ingest_batch(batch, source.run, source.health, source.anchor); batch = []
        if batch: source.repo.ingest_batch(batch, source.run, source.health, source.anchor)
        ni01 = NetworkMetadataProjectionSourceReadService(source.config.db_path)
        refs = tuple(row[0] for row in source.repo.connection.execute("SELECT observation_id FROM network_metadata_observations"))
        assert len(refs) == count
        # Fixture construction is outside the measured read; normal production
        # protected readers below still fetch every real record from SQLite.
        projected = stack(root, [ni01.get_projection_source_record(ref) for ref in refs])
        projected.clock.value = ni_timestamp(AT, canonical=True)
        projected.attribution.states["203.0.113.93"] = "endpoint_absent"
        resolver = projected.attribution.resolve_ipv4
        def resolve(*args):
            value = resolver(*args)
            return replace(value, valid_from="2026-10-11T00:00:00.000Z", valid_until="2026-10-13T00:00:00.000Z") if value.state == "resolved" else value
        projected.attribution.resolve_ipv4 = resolve
        projected.registry.values[MAC] = RegistryEvaluation("authoritative", DEVICE)
        for _ in range(100):
            projected.service.poll()
            if projected.repo.connection.execute("SELECT count(*) FROM device_network_metadata_edges").fetchone()[0] == count: break
        try:
            assert projected.repo.connection.execute("SELECT count(*) FROM device_network_metadata_edges").fetchone()[0] == count
            service = DeviceServiceRecognitionReadService(DeviceNetworkMetadataRecognitionReadService(projected.config.db_path),
                NetworkMetadataRecognitionReadService(source.config.db_path), bundle())
            before = (tuple(source.repo.connection.iterdump()), tuple(projected.repo.connection.iterdump()))
            baseline, peak, stop = rss_bytes(), [rss_bytes()], threading.Event()
            def sample():
                while not stop.wait(.005): peak[0] = max(peak[0], rss_bytes())
            sampler = threading.Thread(target=sample); sampler.start()
            timings = []
            try:
                for _ in range(10):
                    started = time.perf_counter()
                    summary = service.get_device_service_summary(source.config.capture_scope_binding.site_id, DEVICE, MAC,
                        evaluated_at_utc=AT, deadline=QueryDeadline.after(5))
                    timings.append(time.perf_counter() - started)
                    assert bool(summary.recent_services) == (family != "dns")
                    peak[0] = max(peak[0], rss_bytes())
            finally: stop.set(); sampler.join()
            assert before == (tuple(source.repo.connection.iterdump()), tuple(projected.repo.connection.iterdump()))
            delta = max(0, peak[0] - baseline)
            assert delta <= 64 * 1024 * 1024
            assert max(timings) <= 5
            return dict(family=family, facts=count, examined_scalars=count * (5 if family == "dns" else 1),
                p50_seconds=statistics.median(timings), p95_seconds=sorted(timings)[-1], max_seconds=max(timings),
                incremental_rss_bytes=delta, databases_unchanged=True)
        finally: projected.repo.close()


def main():
    assert platform.system() == "Linux", "Owner native Linux Lab only"
    assert not subprocess.check_output(["git", "status", "--porcelain"]).strip(), "Exact clean Lab tree required"
    identity = dict(head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        tree=subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip())
    with tempfile.TemporaryDirectory(prefix="ni04-owner-lab-") as directory:
        cases = []
        for family in ("tls", "dns"):
            target = Path(directory) / family; target.mkdir()
            cases.append(run_case(target, family))
    print(json.dumps(dict(preparation_only_identity="NI04_SYNTHETIC_RESOURCE_CHECK_V1", **identity,
        python=platform.python_version(), sqlite=sqlite3.sqlite_version, cases=cases), sort_keys=True))


if __name__ == "__main__": main()
