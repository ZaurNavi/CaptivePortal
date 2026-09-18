"""Offline F-B1-A candidate proof entry point; never activates runtime authority."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.device_fingerprint.artifact_content import decode_artifact_json

from .proof import run_candidate_proof, write_report_file


def main() -> int:
    parser = argparse.ArgumentParser(description="F-B1-A candidate proof only; no final binding admission")
    parser.add_argument("--input", required=True, help="strict retained proof input JSON")
    parser.add_argument("--output", required=True, help="sanitized exclusive-create report JSON")
    args = parser.parse_args()
    source, target = Path(args.input), Path(args.output)
    if source.resolve() == target.resolve():
        parser.error("Proof output cannot overwrite input")
    value = decode_artifact_json(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        parser.error("Proof input must be an object")
    report = run_candidate_proof(value)
    write_report_file(report, str(target))
    return 0 if report["result"] == "PROOF_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
