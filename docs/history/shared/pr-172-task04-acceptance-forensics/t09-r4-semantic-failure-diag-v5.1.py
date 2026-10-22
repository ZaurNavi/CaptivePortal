from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

FORMAL_GATE = Path(r"C:\CaptivPortal-Lab\tools\task04-t09-phase-b-a1-r4-20261002.py")
FORMAL_GATE_SHA256 = "547a882ca9737ac4c8c8ea9e12553bca16a2ee1f89d802449496033769edbffc"
PHASE_B_RUN = Path(r"C:\CaptivPortal-Lab\official-runs\task04\t09\phase-b-20261002T101524Z-T09-A1-R4-01")
PHASE_B_LOCK_SHA256 = "5109dd8ef3809ffcbfdfca2878a17bc88e4542f32ca1bf964ab7715211b74764"
PHASE_A_LOCK = Path(r"C:\CaptivPortal-Lab\official-runs\task04\t09\phase-a-r2-upgrade-20261002T071712Z-T09-A1-01\phase-a-lock.json")
PHASE_A_LOCK_SHA256 = "1142010057ddaa8564fe076160f35595e84ae51c5dae6d798d5e8bbb839c6ac1"
REPO = Path(r"C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1")
FOUNDATION_DB = Path(r"C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3")
TASK01_DB = Path(r"C:\CaptivPortal-Lab\gates\task04\t07\inputs\task01-source-r2.sqlite3")
DIAG_ROOT = Path(r"C:\CaptivPortal-Lab\diagnostics\t09")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_gate(path: Path):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("t09_r4_formal_gate_diag", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("FORMAL_GATE_IMPORT_SPEC_FAILED")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def list_descriptor_groups(snapshot: dict):
    groups = []
    for key, value in snapshot.items():
        if isinstance(value, list) and ("descriptor" in key.lower() or key.lower().endswith("entries")):
            groups.append((key, value))
    return groups


def descriptor_signature(row):
    if not isinstance(row, dict):
        return ("<non-dict>",)
    fields = (
        "source_kind", "source_subtype", "feature_schema_version", "quality_state",
        "status", "reason_code", "producer_id", "capture_source_id",
    )
    return tuple((k, row.get(k)) for k in fields if k in row)


def print_result_dimension(prefix: str, result: dict, key: str):
    d = result[key]
    print(f"{prefix}_{key.upper()}_STATUS={d.get('status')}")
    print(f"{prefix}_{key.upper()}_VALUE={d.get('canonical_value_id')}")
    print(f"{prefix}_{key.upper()}_SUPPORT={d.get('support_level')}")
    print(f"{prefix}_{key.upper()}_SUPPORTING_ORIGINS={compact(d.get('supporting_origin_groups', []))}")
    print(f"{prefix}_{key.upper()}_CONTRADICTING_ORIGINS={compact(d.get('contradicting_origin_groups', []))}")
    print(f"{prefix}_{key.upper()}_NOT_EVALUABLE_ORIGINS={compact(d.get('not_evaluable_origin_groups', []))}")
    print(f"{prefix}_{key.upper()}_EXPLANATIONS={compact(d.get('explanation_codes', []))}")
    print(f"{prefix}_{key.upper()}_KNOWLEDGE_REF_COUNT={len(d.get('knowledge_references', []))}")


def origin_dimension_rows(payload: dict):
    rows = payload.get("dimension_assessments")
    if rows is None:
        rows = payload.get("origin_dimension_assessments")
    return rows if isinstance(rows, list) else []


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only semantic diagnosis of formal T-09 R4 policy FAIL")
    parser.add_argument("--output", type=Path, default=None)
    args_cli = parser.parse_args()

    for p in (FORMAL_GATE, PHASE_B_RUN / "phase-b-lock.json", PHASE_A_LOCK, REPO, FOUNDATION_DB, TASK01_DB):
        if not p.exists():
            raise RuntimeError(f"REQUIRED_PATH_MISSING:{p}")

    actual_gate_sha = sha(FORMAL_GATE)
    actual_lock_sha = sha(PHASE_B_RUN / "phase-b-lock.json")
    if actual_gate_sha != FORMAL_GATE_SHA256:
        raise RuntimeError("FORMAL_GATE_SHA256_MISMATCH")
    if actual_lock_sha != PHASE_B_LOCK_SHA256:
        raise RuntimeError("PHASE_B_LOCK_SHA256_MISMATCH")
    if sha(PHASE_A_LOCK) != PHASE_A_LOCK_SHA256:
        raise RuntimeError("PHASE_A_LOCK_SHA256_MISMATCH")

    out = args_cli.output or (DIAG_ROOT / f"r4-semantic-failure-{now_tag()}")
    out = out.resolve()
    if out.exists():
        raise RuntimeError("DIAGNOSTIC_OUTPUT_ALREADY_EXISTS")
    out.mkdir(parents=True)
    ctx_dir = out / "context"
    ctx_dir.mkdir()

    gate = load_gate(FORMAL_GATE)
    gate_args = SimpleNamespace(
        repo=REPO,
        foundation_db=FOUNDATION_DB,
        task01_db=TASK01_DB,
        phase_a_lock=PHASE_A_LOCK,
        phase_a_lock_sha256=PHASE_A_LOCK_SHA256,
    )

    print(f"FORMAL_GATE_SHA256={actual_gate_sha}")
    print(f"PHASE_B_LOCK_SHA256={actual_lock_sha}")
    print(f"CANDIDATE_COMMIT={gate.COMMIT}")
    print(f"CANDIDATE_TREE={gate.TREE}")
    print("DIAGNOSTIC_MODE=READ_ONLY_POST_RESULT")
    print("CLASSIFICATION_EXECUTION=NO")
    print("CLASSIFICATION_RESULT_PERSISTED=NO")
    print("T09_FORMAL_RERUN=NO")
    print("PRODUCTION_ACTION=NO")

    with gate.no_network():
        ctx = gate.context(gate_args, ctx_dir, full=True)
        api = ctx.api
        lock = gate.verify_lock(api, PHASE_B_RUN / "phase-b-lock.json", PHASE_B_LOCK_SHA256, "B")
        if lock.get("policy_outcome") != "FAIL":
            raise RuntimeError("EXPECTED_POLICY_FAIL_NOT_PRESENT")
        if gate.db_identity(TASK01_DB) != lock["task01_source_identity"]:
            raise RuntimeError("TASK01_SOURCE_IDENTITY_CHANGED_AFTER_FORMAL_RUN")
        if gate.db_identity(FOUNDATION_DB) != lock["foundation_source_identity"]:
            raise RuntimeError("FOUNDATION_SOURCE_IDENTITY_CHANGED_AFTER_FORMAL_RUN")

        phase_a_lock, truths = gate.checked_phase_a(ctx, gate_args)
        print(f"VALIDATION_RUN_ID={phase_a_lock['validation_run_id']}")
        print("FORMAL_PHASE_B_LOCK_INTEGRITY=PASS")
        print("FORMAL_PHASE_B_POLICY_OUTCOME=FAIL")

        for index, (truth, worker_ref) in enumerate(zip(truths, lock["worker_executions"]), 1):
            worker_dir = PHASE_B_RUN / f"worker-{index}"
            worker_lock_path = worker_dir / "worker-completion.json"
            worker = gate.verify_lock(api, worker_lock_path, worker_ref["file_sha256"], "WORKER")
            req = gate.load_content(api, worker_dir / f"request-{index}.json")
            result = gate.load_content(api, worker_dir / f"result-{index}.json")
            cmp = gate.load_content(api, worker_dir / f"comparison-{index}.json")

            label = worker["device_label"]
            prefix = f"DEVICE_{index}"
            print(f"{prefix}_LABEL={label}")
            print(f"{prefix}_GROUND_TRUTH_PLATFORM={truth.semantic_payload['platform_family_ground_truth']}")
            print(f"{prefix}_GROUND_TRUTH_DEVICE_CLASS={truth.semantic_payload['device_class_ground_truth']}")
            print(f"{prefix}_REQUEST_ID={req.artifact_id}")
            print(f"{prefix}_RESULT_ID={result.artifact_id}")
            print(f"{prefix}_COMPARISON_ID={cmp.artifact_id}")
            print(f"{prefix}_COMPARISON_OVERALL={cmp.semantic_payload['overall_validation_outcome']}")
            print(f"{prefix}_GLOBAL_STATUS={result.semantic_payload['global_classification_status']}")
            print_result_dimension(prefix, result.semantic_payload, "platform_result")
            print_result_dimension(prefix, result.semantic_payload, "device_class_result")
            print_result_dimension(prefix, result.semantic_payload, "manufacturer_result")
            print_result_dimension(prefix, result.semantic_payload, "model_result")

            db = worker_dir / "classification.sqlite3"
            with closing(sqlite3.connect(db.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA query_only=ON")
                named = {
                    key: ctx.t01._resolve_artifact(conn, api, value)
                    for key, value in req.semantic_payload.items()
                    if key != "knowledge_evaluation_at_utc"
                }
                snapshot = named["evidence_snapshot_content"].semantic_payload
                source_eval = named["source_evaluability"].semantic_payload
                origins = [ctx.t01._resolve_artifact(conn, api, ref) for ref in result.semantic_payload["origin_assessments"]]

                print(f"{prefix}_KNOWLEDGE_EVALUATION_AT_UTC={req.semantic_payload.get('knowledge_evaluation_at_utc')}")
                print(f"{prefix}_SNAPSHOT_WINDOW_START={snapshot.get('window_start_utc')}")
                print(f"{prefix}_SNAPSHOT_WINDOW_END={snapshot.get('window_end_utc')}")
                print(f"{prefix}_SNAPSHOT_KEYS={compact(sorted(snapshot.keys()))}")

                descriptor_groups = list_descriptor_groups(snapshot)
                print(f"{prefix}_SNAPSHOT_DESCRIPTOR_GROUP_COUNT={len(descriptor_groups)}")
                for group_name, rows in descriptor_groups:
                    print(f"{prefix}_SNAPSHOT_{group_name.upper()}_COUNT={len(rows)}")
                    counter = Counter(descriptor_signature(row) for row in rows)
                    rendered = [
                        {"count": count, "signature": list(sig)}
                        for sig, count in sorted(counter.items(), key=lambda item: repr(item[0]))
                    ]
                    print(f"{prefix}_SNAPSHOT_{group_name.upper()}_SUMMARY={compact(rendered)}")

                print(f"{prefix}_SOURCE_EVALUABILITY_ID={named['source_evaluability'].artifact_id}")
                print(f"{prefix}_SOURCE_EVALUABILITY_KEYS={compact(sorted(source_eval.keys()))}")
                source_entries = None
                for key, value in source_eval.items():
                    if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                        if any("aggregate_evaluability_state" in x or "coverage_intervals" in x for x in value):
                            source_entries = value
                            print(f"{prefix}_SOURCE_EVALUABILITY_ENTRY_FIELD={key}")
                            break
                if source_entries is None:
                    source_entries = []
                print(f"{prefix}_SOURCE_EVALUABILITY_ENTRY_COUNT={len(source_entries)}")
                for sidx, entry in enumerate(source_entries, 1):
                    print(f"{prefix}_SOURCE_ENTRY_{sidx}={compact(entry)}")

                origin_by_group = {o.semantic_payload.get("origin_group"): o for o in origins}
                print(f"{prefix}_ORIGIN_GROUPS={compact(sorted(origin_by_group))}")
                for group in sorted(origin_by_group):
                    payload = origin_by_group[group].semantic_payload
                    print(f"{prefix}_ORIGIN_{group.upper()}_TOP_EXPLANATIONS={compact(payload.get('explanation_codes', []))}")
                    print(f"{prefix}_ORIGIN_{group.upper()}_TOP_EVIDENCE_REF_COUNT={len(payload.get('evidence_refs', []))}")
                    print(f"{prefix}_ORIGIN_{group.upper()}_TOP_KNOWLEDGE_REF_COUNT={len(payload.get('knowledge_refs', []))}")
                    rows = origin_dimension_rows(payload)
                    if not rows:
                        print(f"{prefix}_ORIGIN_{group.upper()}_DIMENSION_ROWS=UNAVAILABLE")
                    for row in rows:
                        dim = row.get("dimension_name")
                        if dim not in {"platform_family", "device_class", "manufacturer_family", "model_family"}:
                            continue
                        summary = {
                            "dimension_name": dim,
                            "internal_state": row.get("internal_state"),
                            "selected_canonical_value_id": row.get("selected_canonical_value_id"),
                            "selected_out_of_scope_taxon_ref": row.get("selected_out_of_scope_taxon_ref"),
                            "effective_claim_strength": row.get("effective_claim_strength"),
                            "claim_derivations": row.get("claim_derivations", []),
                            "candidate_set": row.get("candidate_set", []),
                            "broad_unresolved_taxon_refs": row.get("broad_unresolved_taxon_refs", []),
                            "evidence_ref_count": len(row.get("evidence_refs", [])),
                            "knowledge_ref_count": len(row.get("knowledge_refs", [])),
                            "explanation_codes": row.get("explanation_codes", []),
                        }
                        print(f"{prefix}_ORIGIN_{group.upper()}_{dim.upper()}={compact(summary)}")

        gate.finish_integrity(ctx, gate_args)

    print("FORMAL_INPUTS_UNCHANGED=YES")
    print("DIAGNOSTIC_STATUS=PASS")
    print(f"DIAGNOSTIC_OUTPUT={out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("DIAGNOSTIC_STATUS=BLOCKED")
        print(f"BLOCKER_TYPE={type(exc).__name__}")
        print(f"BLOCKER={getattr(exc, 'reason_code', str(exc))}")
        raise
