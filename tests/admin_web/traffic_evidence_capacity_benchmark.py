"""Owner-run authenticated capacity gate for TASK-TRAFFIC-09.

This is deliberately not a pytest test.  The supplied factory must return a
``TrafficEvidenceBenchmarkTarget`` backed by the representative immutable
production-size fixture.  Keeping fixture construction outside this runner
lets Owner/Central Lab control protected snapshot locations while this module
owns the frozen measurement and acceptance contract.

Example:
    python tests/admin_web/traffic_evidence_capacity_benchmark.py \
      --factory central_lab.traffic09_fixture:build_target --runs 10
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


@dataclass(frozen=True, slots=True)
class TrafficEvidenceBenchmarkTarget:
    app: Any
    site_id: str
    login: Callable[[Any], Any]
    source_db_paths: Mapping[str, Path]
    counters: Callable[[], Mapping[str, int]]


def _fingerprint(path: Path) -> dict[str, Any]:
    main = path.read_bytes()
    wal_path = path.with_name(path.name + "-wal")
    wal = wal_path.read_bytes() if wal_path.exists() else b""
    return {
        "main_size": len(main),
        "main_sha256": hashlib.sha256(main).hexdigest(),
        "wal_size": len(wal),
        "wal_sha256": hashlib.sha256(wal).hexdigest(),
    }


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def _load_factory(value: str):
    module_name, separator, function_name = value.partition(":")
    if not separator or not module_name or not function_name:
        raise ValueError("--factory must be module:function")
    factory = getattr(importlib.import_module(module_name), function_name)
    target = factory()
    if not isinstance(target, TrafficEvidenceBenchmarkTarget):
        raise TypeError("factory did not return TrafficEvidenceBenchmarkTarget")
    return target


def _measure(target: TrafficEvidenceBenchmarkTarget, *, runs: int):
    client = target.app.test_client()
    login_response = target.login(client)
    if getattr(login_response, "status_code", None) not in {200, 302}:
        raise RuntimeError("authenticated benchmark login failed")
    page = client.get(
        f"/admin/sites/{target.site_id}/traffic", base_url="https://localhost"
    )
    if page.status_code != 200 or b'data-traffic-evidence-enabled="true"' not in page.data:
        raise RuntimeError("representative fixture does not enable Traffic Evidence")
    before_fingerprints = {
        name: _fingerprint(Path(path))
        for name, path in target.source_db_paths.items()
    }
    before_counts = dict(target.counters())
    required = {
        "current_site_calls", "current_ap_calls", "historical_calls",
        "online_calls", "completed_calls", "provider_calls", "writes",
        "collection_cycles",
    }
    if set(before_counts) != required:
        raise RuntimeError("benchmark counter contract is incomplete")
    measurements = {}
    for range_id in ("24h", "7d"):
        durations: list[float] = []
        statuses: list[int] = []
        deadline_failures = 0
        maximum_bytes = 0
        for _ in range(runs):
            started = time.perf_counter()
            response = client.get(
                f"/admin/api/v1/sites/{target.site_id}/traffic/evidence?range={range_id}",
                base_url="https://localhost",
            )
            durations.append(time.perf_counter() - started)
            statuses.append(response.status_code)
            maximum_bytes = max(maximum_bytes, len(response.data))
            try:
                payload = response.get_json() or {}
            except Exception:
                payload = {}
            if payload.get("error", {}).get("code") == "query_deadline":
                deadline_failures += 1
        measurements[range_id] = {
            "runs": runs,
            "p50_seconds": _percentile(durations, 0.50),
            "p95_seconds": _percentile(durations, 0.95),
            "max_seconds": max(durations),
            "max_response_bytes": maximum_bytes,
            "unexpected_http_statuses": sum(status != 200 for status in statuses),
            "deadline_failures": deadline_failures,
        }
    after_counts = dict(target.counters())
    after_fingerprints = {
        name: _fingerprint(Path(path))
        for name, path in target.source_db_paths.items()
    }
    deltas = {
        name: after_counts[name] - before_counts[name] for name in required
    }
    expected_requests = runs * 2
    result = {
        "measurements": measurements,
        "call_deltas": deltas,
        "source_db_fingerprints_unchanged": before_fingerprints == after_fingerprints,
        "thresholds": {
            "24h": {"p95_seconds": 5.0, "max_seconds": 10.0},
            "7d": {"p95_seconds": 7.0, "max_seconds": 12.0},
            "max_response_bytes": 65_536,
        },
    }
    result["pass"] = (
        measurements["24h"]["p95_seconds"] <= 5.0
        and measurements["24h"]["max_seconds"] <= 10.0
        and measurements["7d"]["p95_seconds"] <= 7.0
        and measurements["7d"]["max_seconds"] <= 12.0
        and all(item["max_response_bytes"] <= 65_536 for item in measurements.values())
        and all(item["unexpected_http_statuses"] == 0 for item in measurements.values())
        and all(item["deadline_failures"] == 0 for item in measurements.values())
        and deltas["current_site_calls"] == expected_requests
        and 0 <= deltas["current_ap_calls"] <= expected_requests
        and deltas["historical_calls"] == expected_requests
        and deltas["online_calls"] == expected_requests
        and deltas["completed_calls"] == expected_requests
        and deltas["provider_calls"] == 0
        and deltas["writes"] == 0
        and deltas["collection_cycles"] == 0
        and result["source_db_fingerprints_unchanged"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory", required=True)
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()
    if args.runs < 10:
        parser.error("--runs must be at least 10")
    result = _measure(_load_factory(args.factory), runs=args.runs)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
