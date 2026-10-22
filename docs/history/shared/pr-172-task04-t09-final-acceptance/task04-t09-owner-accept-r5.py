"""Create the Owner ACCEPT DecisionRecord for frozen T-09 R5 evidence.

This is an external audit helper, not a product/classification action.
It consumes only exact pinned Phase-A/Phase-B locks and writes one immutable
DecisionRecord after the Owner has explicitly reviewed and accepted R5.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
EXPECTED_PHASE_A_SHA = "1142010057ddaa8564fe076160f35595e84ae51c5dae6d798d5e8bbb839c6ac1"
EXPECTED_PHASE_B_SHA = "93256ffa5224693a1823b0ece4bba5f7a2eb919eb022a08d59e6837a89603a05"
EXPECTED_R5_RUNNER_SHA = "a80456c02b875eb5b9ef7205683473f79be0a039a18434898ad2a46d8ad0063f"
EXPECTED_TASK01_SHA = "a8ea541ca7fe5cd8498efaba028d8768a39e06cd1cdc688551a9f883e16040cd"
GATE_ID = "T-09"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalized(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("Artifact object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in result:
                raise ValueError("Artifact NFC key collision")
            result[normalized_key] = _normalized(child)
        return result
    if isinstance(value, (list, tuple)):
        return [_normalized(child) for child in value]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or type(value) in (bool, int):
        return value
    raise ValueError("Unsupported ArtifactCanonicalJsonV1 value")


def canonical_artifact_json(value: Any) -> bytes:
    normalized = _normalized(value)
    return json.dumps(
        normalized,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"NOT_JSON_OBJECT:{path}")
    return value


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", value):
        raise RuntimeError("INVALID_CANONICAL_UTC")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def canonical_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-a-lock", type=Path, required=True)
    parser.add_argument("--phase-b-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if sha256(args.phase_a_lock) != EXPECTED_PHASE_A_SHA:
        raise RuntimeError("PHASE_A_LOCK_SHA256_MISMATCH")
    if sha256(args.phase_b_lock) != EXPECTED_PHASE_B_SHA:
        raise RuntimeError("PHASE_B_LOCK_SHA256_MISMATCH")

    a = read_json(args.phase_a_lock)
    b = read_json(args.phase_b_lock)

    if a.get("phase") != "A":
        raise RuntimeError("PHASE_A_LOCK_PHASE_MISMATCH")
    if b.get("phase") != "B":
        raise RuntimeError("PHASE_B_LOCK_PHASE_MISMATCH")
    if b.get("candidate_commit") != EXPECTED_COMMIT or b.get("candidate_tree") != EXPECTED_TREE:
        raise RuntimeError("PHASE_B_CANDIDATE_MISMATCH")
    if b.get("runner_sha256") != EXPECTED_R5_RUNNER_SHA or b.get("phase_b_runner_sha256") != EXPECTED_R5_RUNNER_SHA:
        raise RuntimeError("PHASE_B_RUNNER_MISMATCH")
    if b.get("phase_a_lock_sha256") != EXPECTED_PHASE_A_SHA:
        raise RuntimeError("PHASE_CHAIN_MISMATCH")
    if b.get("validation_run_id") != a.get("validation_run_id"):
        raise RuntimeError("VALIDATION_RUN_MISMATCH")
    if b.get("state") != "OWNER_REVIEW_REQUIRED":
        raise RuntimeError("PHASE_B_NOT_OWNER_REVIEW_REQUIRED")
    if b.get("policy_outcome") != "PASS":
        raise RuntimeError("PHASE_B_POLICY_NOT_PASS")
    if b.get("task01_input_sha256") != EXPECTED_TASK01_SHA:
        raise RuntimeError("PHASE_B_TASK01_INPUT_MISMATCH")

    entries = b.get("entries")
    if not isinstance(entries, list) or len(entries) != 2:
        raise RuntimeError("PHASE_B_ENTRY_COUNT_MISMATCH")

    artifact_ids = set()
    expected_labels = {"OWNER_ANDROID", "OWNER_WINDOWS_LAPTOP"}
    labels = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("PHASE_B_ENTRY_SHAPE")
        labels.add(entry.get("controlled_device_lab_label"))
        for key in ("ground_truth", "request", "result", "comparison"):
            ref = entry.get(key)
            if not isinstance(ref, dict) or set(ref) != {"artifact_id", "content_sha256"}:
                raise RuntimeError(f"PHASE_B_REF_SHAPE:{key}")
            artifact_id = ref["artifact_id"]
            digest = ref["content_sha256"]
            if not isinstance(artifact_id, str) or not isinstance(digest, str) or not artifact_id.endswith(digest):
                raise RuntimeError(f"PHASE_B_REF_IDENTITY:{key}")
            artifact_ids.add(artifact_id)

    if labels != expected_labels:
        raise RuntimeError("CONTROLLED_DEVICE_LABEL_SET_MISMATCH")
    if len(artifact_ids) != 8:
        raise RuntimeError("OWNER_DECISION_ARTIFACT_COUNT_NOT_8")

    decided_at = canonical_now()
    if parse_utc(decided_at) <= parse_utc(b["completed_at_utc"]):
        raise RuntimeError("OWNER_DECISION_NOT_AFTER_RESULTS")

    unsigned = {
        "decision_record_id": str(uuid.uuid4()),
        "decision_subject_type": "TASK04_PRODUCT_VALIDATION",
        "decision_subject_id": a["validation_run_id"],
        "decision": "ACCEPT",
        "decided_at_utc": decided_at,
        "actor_role": "OWNER",
        "referenced_artifact_ids": sorted(artifact_ids),
        "referenced_gate_ids": [GATE_ID],
        "reason_reference_text": (
            "Owner reviewed and accepts the frozen T-09 R5 controlled ground truth "
            "and ProductValidationComparison results. Phase B policy_outcome=PASS; "
            "automatic_learning=NO; production_activation=NO."
        ),
    }
    record = {
        **unsigned,
        "record_sha256": hashlib.sha256(canonical_artifact_json(unsigned)).hexdigest(),
    }

    if args.output.exists():
        raise RuntimeError("OWNER_DECISION_OUTPUT_ALREADY_EXISTS")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(canonical_artifact_json(record) + b"\n")

    # Self-check exact bytes and digest.
    written = read_json(args.output)
    unsigned_written = {k: v for k, v in written.items() if k != "record_sha256"}
    if hashlib.sha256(canonical_artifact_json(unsigned_written)).hexdigest() != written["record_sha256"]:
        raise RuntimeError("OWNER_DECISION_SELF_CHECK_FAILED")

    print("OWNER_DECISION_STATUS=PASS")
    print(f"OWNER_DECISION_PATH={args.output}")
    print(f"OWNER_DECISION_RECORD_ID={record['decision_record_id']}")
    print(f"OWNER_DECISION_RECORD_SHA256={record['record_sha256']}")
    print(f"OWNER_DECISION_FILE_SHA256={sha256(args.output)}")
    print(f"OWNER_DECISION_DECIDED_AT_UTC={record['decided_at_utc']}")
    print("OWNER_DECISION=ACCEPT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
