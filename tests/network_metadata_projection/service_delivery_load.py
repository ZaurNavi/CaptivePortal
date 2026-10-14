"""Scoped synthetic G2 load driver; never opens deployment paths or providers."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--extension", action="store_true")
    parser.add_argument("--batches", type=int, default=60)
    parser.add_argument("--lab-temp", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.repository.resolve()
    if not (root / ".git").exists() or not 20 <= args.batches <= 200 or not args.lab_temp.is_dir():
        raise ValueError("invalid_lab_configuration")
    sys.path.insert(0, str(root))
    from tests.network_metadata_projection.support import (
        source_record, Clock, Source, Attribution, Registry, IDENTITY, MAC, OTHER_MAC, GENERATION, scope_admission)
    from app.network_metadata_projection.repository import ProjectionRepository
    from app.network_metadata_projection.models import ProjectionConfig, RegistryEvaluation
    from app.network_metadata_projection.service import NetworkMetadataProjectionService
    from app.network_metadata.canonical import observation_uuid, source_event_identity
    if Path(sys.modules[ProjectionRepository.__module__].__file__).resolve().parent.parent.parent != root:
        raise ValueError("repository_import_origin_mismatch")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
    commits, elapsed, projected = [], 0.0, 0
    with tempfile.TemporaryDirectory(prefix="ni04mat-g2-load-", dir=args.lab_temp) as disposable:
        config = ProjectionConfig(True, str(Path(disposable) / "projection.sqlite3"), max_db_bytes=536870912,
                                  scope_admission_json=scope_admission())
        clock = Clock()
        repo = ProjectionRepository(config, clock=clock).initialize()
        try:
            if args.extension:
                from app.network_metadata_projection.service_extension import install_service_recognition_extension
                install_service_recognition_extension(repo)
            source, attribution, registry = Source(), Attribution(), Registry()
            attribution.states["203.0.113.93"] = "endpoint_absent"
            registry.values = {
                MAC: RegistryEvaluation("authoritative", "10000000-0000-4000-8000-000000000001"),
                OTHER_MAC: RegistryEvaluation("authoritative", "10000000-0000-4000-8000-000000000002"),
            }
            service = NetworkMetadataProjectionService(config, repo, source, attribution, registry, IDENTITY)
            service.run_id = repo.create_run(IDENTITY)
            original = repo.commit_dispositions
            measured = [False]
            def timed(*values, **kwargs):
                start = time.perf_counter()
                result = original(*values, **kwargs)
                if measured[0]:
                    commits.append(time.perf_counter() - start)
                return result
            repo.commit_dispositions = timed
            total_expected = total_eligible = 0
            for batch in range(args.batches + 3):
                rows = []
                for ordinal in range(256):
                    offset = batch * 256 + ordinal
                    category = offset % 100
                    family = "dns" if category < 65 else "tls" if category < 85 else "quic"
                    external = family != "dns"
                    rows.append(source_record(offset, source_event_family=family,
                        observation_id=observation_uuid(family, source_event_identity(GENERATION, offset)),
                        dst_ip="203.0.113.93" if external else "10.73.0.8",
                        dst_port=443 if external else 53, transport_protocol="TCP" if family == "tls" else "UDP"))
                    total_expected += 1 if external else 2
                    total_eligible += int(external)
                source.records = rows
                measured[0] = batch >= 3
                before = repo.connection.execute("SELECT count(*) FROM device_network_metadata_edges").fetchone()[0]
                start = time.perf_counter()
                outcomes = service.poll()
                duration = time.perf_counter() - start
                after = repo.connection.execute("SELECT count(*) FROM device_network_metadata_edges").fetchone()[0]
                if not outcomes or repo.live_state != "usable" or after - before != sum(item.emitted_edge_count for item in outcomes):
                    raise RuntimeError("lab_projection_disposition_failed")
                if measured[0]:
                    elapsed += duration
                    projected += after - before
                clock.advance(seconds=1)
            actual = repo.connection.execute("SELECT count(*) FROM device_network_metadata_edges").fetchone()[0]
            if actual != total_expected:
                raise RuntimeError("lab_edge_count_mismatch")
            if args.extension:
                actual_feed = repo.connection.execute("SELECT count(*) FROM projection_service_recognition_feed").fetchone()[0]
                if actual_feed != total_eligible:
                    raise RuntimeError("lab_feed_count_mismatch")
            else:
                actual_feed = None
            checkpoint = repo.checkpoint(GENERATION)
            if checkpoint["last_record_start_byte_offset"] != (args.batches + 3) * 256 - 1:
                raise RuntimeError("lab_checkpoint_mismatch")
            result = dict(
                profile="synthetic_mixed_approximately_65pct_local_dns_20pct_outbound_tls_15pct_outbound_quic",
                batch_observations=256, warmup_batches=3, measured_batches=args.batches,
                extension_present=args.extension, repository_head=head, repository_tree=tree,
                worktree_clean=not subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip(),
                python=platform.python_version(), sqlite=sqlite3.sqlite_version,
                platform=platform.platform(), projected_edges=projected,
                measured_poll_seconds=elapsed, projected_edges_per_second=projected / elapsed,
                batch_commit_p95_ms=percentile(commits, .95) * 1000,
                batch_commit_p99_ms=percentile(commits, .99) * 1000,
                batch_commit_median_ms=statistics.median(commits) * 1000,
                committed_feed_rows=actual_feed,
                repository_source_sha256=hashlib.sha256(Path(sys.modules[ProjectionRepository.__module__].__file__).read_bytes()).hexdigest(),
            )
        finally:
            repo.close()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
