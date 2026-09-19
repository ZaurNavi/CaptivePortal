"""Lab-only CLI: python -m research.device_fingerprint_fa4 ..."""

from __future__ import annotations

import argparse
from pathlib import Path

from .measurement import InspectionCase, failed_report, inspect_read_only, write_report_file
from .semantic_accounting import load_semantic_accounting_dependencies
from .workload import StressCase, run_disposable_stress


def main() -> int:
    parser = argparse.ArgumentParser(description="Task-01 F-A4-A measurement only; no final policy")
    parser.add_argument("--output", required=True, help="one JSON report path")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--tree-sha", required=True)
    parser.add_argument("--page-size", type=int, required=True)
    parser.add_argument("--binding-timeline-payload")
    parser.add_argument("--binding-clock-policy-payload")
    modes = parser.add_subparsers(dest="mode", required=True)
    inspect = modes.add_parser("inspect", help="read-only inspection of an existing DB")
    inspect.add_argument("--db", required=True)
    inspect.add_argument("--site", required=True)
    inspect.add_argument("--mac", required=True)
    inspect.add_argument("--from-utc", required=True)
    inspect.add_argument("--to-utc", required=True)
    inspect.add_argument("--health-scope", action="append", nargs=3, required=True,
                         metavar=("PRODUCER", "CAPTURE", "SOURCE_KIND"))
    stress = modes.add_parser("stress", help="internally created disposable DB only")
    stress.add_argument("--evidence-rows", type=int, required=True)
    stress.add_argument("--health-rows", type=int, required=True)
    stress.add_argument("--writer-batches", type=int, required=True)
    stress.add_argument("--rows-per-writer-batch", type=int, required=True)
    stress.add_argument("--temporary-parent")
    args = parser.parse_args()
    if bool(args.binding_timeline_payload) != bool(args.binding_clock_policy_payload):
        parser.error("Both final F-B1 semantic payload files are required together")
    if args.mode == "inspect" and Path(args.db).resolve() == Path(args.output).resolve():
        parser.error("Report output cannot overwrite the inspected database")
    try:
        semantic_dependencies = None
        if args.binding_timeline_payload:
            semantic_dependencies = load_semantic_accounting_dependencies(
                args.binding_timeline_payload,
                args.binding_clock_policy_payload,
            )
        if args.mode == "inspect":
            report = inspect_read_only(InspectionCase(
                args.case_id, args.db, args.site, args.mac, args.from_utc,
                args.to_utc, tuple(tuple(scope) for scope in args.health_scope),
                args.page_size, args.commit_sha, args.tree_sha,
            ), semantic_dependencies=semantic_dependencies)
        else:
            report = run_disposable_stress(StressCase(
                args.case_id, args.evidence_rows, args.health_rows,
                args.page_size, args.writer_batches, args.rows_per_writer_batch,
                args.commit_sha, args.tree_sha,
            ), temporary_parent=args.temporary_parent,
                semantic_dependencies=semantic_dependencies)
    except Exception as exc:
        write_report_file(failed_report(args.commit_sha, args.tree_sha, args.case_id,
                                        args.mode.upper(), type(exc).__name__), args.output)
        return 1
    write_report_file(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
