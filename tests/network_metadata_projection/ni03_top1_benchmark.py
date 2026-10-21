"""Reproducible #293 LAB-only before/after probe. No production configuration.

Run as a module with --root pointing to a NEW disposable external directory.
Optional strace -ttt captures can be paired with each phase's epoch interval.
Reports guest/kernel I/O, not physical HDD requests or production savings.
"""
import argparse
import hashlib
import json
import os
import platform
import resource
import sqlite3
import statistics
import subprocess
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_format_utc
from app.network_metadata.canonical import observation_uuid
from app.network_metadata_projection.models import ProjectionUnavailable
from app.network_metadata_projection.ni03_top1_migration import INDEX, migrate, validate_index_version
from app.network_metadata_projection.read_service import DeviceNetworkMetadataReadService, PROTOCOL_LATEST_SQL
from app.network_metadata_projection.recognition_read_service import DeviceNetworkMetadataRecognitionReadService
from app.network_metadata_projection.repository import ProjectionRepository
from app.network_protocol_intelligence.read_service import DeviceProtocolIntelligenceReadService
from .test_protocol_latest_snapshot import seed, SITE, MAC, DEVICE, AT, FAMILIES
from .support import source_record

BASE = "6abbfe6b4546d7931696061f8703a7b413303a29"


@contextmanager
def core_variant(indexed):
    """Build the reference using ACTUAL baseline schema, not DROP/free pages.

    Test-process-only composition: runtime source and validators are unmodified.
    The remaining writer/retention/extension code is byte-identical to baseline.
    """
    if indexed:
        yield
        return
    import app.network_metadata_projection.schema as schema
    import app.network_metadata_projection.repository as repository
    import app.network_metadata_projection.read_service as reads
    namespace = {"__package__": "app.network_metadata_projection", "__name__": "reference_schema"}
    source = subprocess.check_output(["git", "show", BASE + ":app/network_metadata_projection/schema.py"])
    exec(compile(source, "reference_schema.py", "exec"), namespace)
    with patch.object(schema, "validate_schema", namespace["validate_schema"]), \
            patch.object(repository, "validate_schema", namespace["validate_schema"]), \
            patch.object(repository, "create_schema", namespace["create_schema"]), \
            patch.object(reads, "validate_schema", namespace["validate_schema"]):
        yield


def io():
    return {key: int(value) for key, value in
            (line.split(":") for line in Path("/proc/self/io").read_text().splitlines())}


def footprint(path):
    return {suffix or "db": Path(path + suffix).stat().st_size if Path(path + suffix).exists() else 0
            for suffix in ("", "-wal", "-shm")}


def phase(function):
    before = io()
    epoch = time.time()
    start = time.perf_counter()
    value = function()
    elapsed = time.perf_counter() - start
    end = time.time()
    after = io()
    result = dict(seconds=elapsed, epoch_start=epoch, epoch_end=end,
                  process_io_delta={key: after[key] - before[key] for key in before}, result=value)
    print(json.dumps(result), flush=True)  # preserve raw phases even if a later probe aborts
    return result


def timings(function, runs=20):
    values = []
    outcomes = {}
    for _ in range(runs):
        start = time.perf_counter()
        try:
            function()
            outcome = "ok"
        except ProjectionUnavailable:
            outcome = "ProjectionUnavailable"
        values.append(time.perf_counter() - start)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    return dict(runs=runs, median_seconds=statistics.median(values),
                p95_seconds=sorted(values)[int(.95 * (len(values) - 1))],
                max_seconds=max(values), outcomes=outcomes)


def run_case(root, indexed, count, batches):
    with core_variant(indexed):
        return _run_case(root, indexed, count, batches)


def _run_case(root, indexed, count, batches):
    root.mkdir()
    state = seed(root, count, extension=True,
                 families=("dns",) * 90 + ("quic",) * 9 + ("tls",))
    c = state.repo.connection
    validate_index_version(c, installed=indexed)
    report = dict(indexed=indexed, initial_edges=count, extension=True,
                  footprint_before=footprint(state.config.db_path),
                  initial_page_count=c.execute("PRAGMA page_count").fetchone()[0],
                  initial_freelist_count=c.execute("PRAGMA freelist_count").fetchone()[0])
    first, last = ni_format_utc(AT - timedelta(days=1)), ni_format_utc(AT)
    # Other Device for NI04 bounded-reader latency (same store/mixed workload).
    other_device, other_mac = "20000000-0000-4000-8000-000000000002", "02:00:00:00:00:02"
    c.execute("INSERT INTO projection_registry_identities VALUES(?,?,1,?,?,NULL)",
              (other_device, other_mac, last, last))
    c.execute("INSERT INTO projection_site_mac_bindings SELECT site_id,?,'authoritative',?,first_edge_at,"
              "last_edge_at,last_evaluated_at,authoritative_bound_at,last_safe_reason "
              "FROM projection_site_mac_bindings WHERE site_id=? AND client_mac=?", (other_mac, other_device, SITE, MAC))
    template = dict(c.execute("SELECT * FROM device_network_metadata_edges LIMIT 1").fetchone())
    row = {**template, "edge_id": "f" * 64, "client_mac": other_mac,
           "source_observation_ref": "50000000-0000-5000-8000-000000000001"}
    c.execute("INSERT INTO device_network_metadata_edges (" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")", tuple(row.values()))
    if indexed:
        report["query_plans"] = {family: [r[3] for r in c.execute("EXPLAIN QUERY PLAN " + PROTOCOL_LATEST_SQL,
            (SITE, MAC, family, first, last))] for family in FAMILIES}
        reader = DeviceNetworkMetadataReadService(state.config.db_path)
        report["ni03"] = phase(lambda: timings(lambda: DeviceProtocolIntelligenceReadService(reader).get_device_protocol_summary(
            SITE, DEVICE, MAC, evaluated_at_utc=last, deadline=QueryDeadline.after(5))))
        report["fetched_facts"] = len(reader.read_protocol_latest_snapshot(
            SITE, DEVICE, MAC, first, last, deadline=QueryDeadline.after(5))["facts"])
        ni04 = DeviceNetworkMetadataRecognitionReadService(state.config.db_path)
        report["ni04"] = phase(lambda: timings(lambda: ni04.read_service_recognition_snapshot(
            SITE, other_device, other_mac, first, last, max_rows=5000, deadline=QueryDeadline.after(5))))
    else:
        reader = DeviceNetworkMetadataReadService(state.config.db_path)
        report["ni03_legacy_cap"] = phase(lambda: timings(lambda: reader.read_protocol_evidence_snapshot(
            SITE, DEVICE, MAC, first, last, max_rows=20000, deadline=QueryDeadline.after(5))))
        ni04 = DeviceNetworkMetadataRecognitionReadService(state.config.db_path)
        report["ni04"] = phase(lambda: timings(lambda: ni04.read_service_recognition_snapshot(
            SITE, other_device, other_mac, first, last, max_rows=5000, deadline=QueryDeadline.after(5))))
    # Prepared rows outside the timed writer section, same three-family mix.
    def prepare(number, i):
        record = source_record(number, dst_ip="203.0.113.93",
            event_at=ni_format_utc(AT - timedelta(seconds=31 + i % 20)))
        record = replace(record, source_event_family=FAMILIES[i % 3],
                         observation_id=observation_uuid(FAMILIES[i % 3], record.source_event_identity))
        value = state.service.prepare(record)
        assert len(value.edges) == 1
        return value
    prepared = [[prepare(1000000 + batch * 128 + i, i) for i in range(128)] for batch in range(batches)]
    def write():
        elapsed = []
        for batch in prepared:
            start = time.perf_counter()
            state.repo.commit_dispositions(batch, {}, state.service.run_id)
            elapsed.append(time.perf_counter() - start)
        return dict(edges=batches * 128, batches=batches,
                    edges_per_second=batches * 128 / sum(elapsed),
                    commit_p95_seconds=sorted(elapsed)[int(.95 * (len(elapsed) - 1))])
    report["writer"] = phase(write)
    report["footprint_after_writer"] = footprint(state.config.db_path)
    # Existing unchanged sole-writer bounded retention including extension FK.
    state.clock.advance(days=15)
    report["retention"] = phase(state.service.retain)
    report["footprint_after_retention"] = footprint(state.config.db_path)
    report["pragmas"] = {key: c.execute("PRAGMA " + key).fetchone()[0]
                         for key in ("journal_mode", "synchronous", "foreign_keys", "wal_autocheckpoint")}
    state.repo.close()
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=100001)
    parser.add_argument("--batches", type=int, default=20)
    parser.add_argument("--order", choices=("baseline-first", "index-first"), default="baseline-first")
    args = parser.parse_args()
    args.root.mkdir(exist_ok=False)
    order = (("reference", False), ("candidate", True)) if args.order == "baseline-first" else (("candidate", True), ("reference", False))
    report = dict(methodology="v2_fresh_actual_baseline_schema_no_drop_freelist_advantage",
                  python=platform.python_version(), sqlite=sqlite3.sqlite_version,
                  platform=platform.platform(), physical_hdd_metrics="UNAVAILABLE_WSL_LAB",
                  production_effectiveness="NOT_MEASURED", fixture_edges=args.rows,
                  cold_warm="fresh independent DBs; OS cache not flushed; 20 consecutive warm-capable reads; writer rows prepared outside timed commits",
                  benchmark_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  baseline=BASE, order=[label for label, _ in order])
    report["cases"] = [run_case(args.root / label, indexed, args.rows, args.batches)
                       for label, indexed in order]
    build = args.root / "build"
    build.mkdir()
    with core_variant(False):
        state = seed(build, args.rows, extension=True)
        state.repo.close()
    report["build_initial_footprint"] = footprint(state.config.db_path)
    samples, stages, stop = [], {}, threading.Event()
    def sample():
        while not stop.is_set():
            samples.append(dict(footprint=footprint(state.config.db_path),
                free_bytes=os.statvfs(build).f_bavail * os.statvfs(build).f_frsize))
            stop.wait(.01)
    sampler = threading.Thread(target=sample)
    sampler.start()
    try:
        report["full_fixture_index_build"] = phase(lambda: migrate(state.config, direction="up", maintenance_confirmed=True,
            crash_point=lambda stage: stages.update({stage: time.perf_counter()})))
    finally:
        stop.set()
        sampler.join()
    report["index_ddl_seconds"] = stages["index_changed"] - stages["preflight"]
    report["build_sampling"] = dict(interval_seconds=.01, samples=len(samples),
        minimum_filesystem_free_bytes=min(s["free_bytes"] for s in samples),
        maximum_db_wal_shm_bytes=max(sum(s["footprint"].values()) for s in samples))
    report["build_final_footprint"] = footprint(state.config.db_path)
    with sqlite3.connect(state.config.db_path) as connection:
        report["compile_options"] = [row[0] for row in connection.execute("PRAGMA compile_options")]
        try:
            report["index_bytes_dbstat"] = connection.execute(
                "SELECT sum(pgsize) FROM dbstat WHERE name=?", (INDEX,)).fetchone()[0]
        except sqlite3.Error:
            report["index_bytes_dbstat"] = None
    report["peak_process_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    (args.root / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
