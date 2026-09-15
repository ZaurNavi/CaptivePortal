"""Operator-invoked CLI for Task-03A lab matrix tooling."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .exporter import export_unsealed_matrix, seal_matrix, validate_staging_directory
from .format import MatrixFormatError, canonical_json_text
from .validator import validate_matrix


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="device-fingerprint-03a")
    commands = parser.add_subparsers(dest="command", required=True)

    staging = commands.add_parser("validate-staging")
    staging.add_argument("--staging-dir", required=True)

    export = commands.add_parser("export")
    export.add_argument("--db-path", required=True)
    export.add_argument("--staging-dir", required=True)
    export.add_argument("--output-dir", required=True)
    export.add_argument("--environment-record", required=True)
    export.add_argument("--matrix-id", required=True)
    export.add_argument("--repository-head", required=True)
    export.add_argument("--repository-tree", required=True)
    export.add_argument("--collection-procedure-version", required=True)
    export.add_argument("--ground-truth-policy-version", required=True)
    export.add_argument("--task01-retention-days", required=True, type=int)
    export.add_argument("--invalid-reason", action="append", default=[])
    export.add_argument("--limitation", action="append", default=[])
    export.add_argument("--supersedes-matrix-id")

    seal = commands.add_parser("seal")
    seal.add_argument("--matrix-dir", required=True)
    seal.add_argument("--sealed-at", required=True)
    seal.add_argument("--owner-verified", action="store_true", required=True)
    seal.add_argument("--calibration", action="store_true")

    validate = commands.add_parser("validate")
    validate.add_argument("--matrix-dir", required=True)
    validate.add_argument("--calibration", action="store_true")

    summary = commands.add_parser("summary")
    summary.add_argument("--matrix-dir", required=True)
    summary.add_argument("--calibration", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "validate-staging":
            result = validate_staging_directory(_absolute(arguments.staging_dir, "staging directory"))
        elif arguments.command == "export":
            result = export_unsealed_matrix(
                db_path=str(_absolute(arguments.db_path, "Task-01 database")),
                staging_dir=_absolute(arguments.staging_dir, "staging directory"),
                output_dir=_absolute(arguments.output_dir, "output directory", must_exist=False),
                authorized_environment_record=_absolute(arguments.environment_record, "environment record"),
                matrix_id=arguments.matrix_id,
                repository_head=arguments.repository_head,
                repository_tree=arguments.repository_tree,
                collection_procedure_version=arguments.collection_procedure_version,
                ground_truth_policy_version=arguments.ground_truth_policy_version,
                task01_retention_days=arguments.task01_retention_days,
                invalid_sample_reason_counts=_reason_counts(arguments.invalid_reason),
                known_coverage_limitations=arguments.limitation,
                supersedes_matrix_id=arguments.supersedes_matrix_id,
            )
            result = {
                "matrix_id": result.matrix_id,
                "device_count": result.device_count,
                "sealed_sample_count": result.sample_count,
                "evidence_count": result.evidence_count,
                "source_health_count": result.source_health_count,
                "status": "unsealed",
            }
        elif arguments.command == "seal":
            result = seal_matrix(
                _absolute(arguments.matrix_dir, "matrix directory"),
                sealed_at=arguments.sealed_at,
                owner_verified=arguments.owner_verified,
                require_v1_coverage=not arguments.calibration,
            )
        else:
            result = validate_matrix(
                _absolute(arguments.matrix_dir, "matrix directory"),
                require_v1_coverage=not arguments.calibration,
            )
        print(canonical_json_text(result))
        return 0
    except (MatrixFormatError, OSError, ValueError) as exc:
        del exc
        print(canonical_json_text({"status": "invalid_matrix"}), file=sys.stderr)
        return 2


def _absolute(value: str, label: str, *, must_exist: bool = True) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise MatrixFormatError(f"{label} must be absolute")
    if must_exist:
        try:
            return path.resolve(strict=True)
        except OSError as exc:
            raise MatrixFormatError(f"{label} is unavailable") from exc
    return path.resolve(strict=False)


def _reason_counts(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key, separator, raw_count = value.partition("=")
        if not separator or key in result:
            raise MatrixFormatError("Invalid-sample reason argument is invalid")
        try:
            count = int(raw_count)
        except ValueError as exc:
            raise MatrixFormatError("Invalid-sample reason argument is invalid") from exc
        result[key] = count
    return result


if __name__ == "__main__":
    raise SystemExit(main())
