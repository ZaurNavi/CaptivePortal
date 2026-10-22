#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_MAIN = "ce948017cde0b82a778bd07cc9dffe72189aa0bb"
EXPECTED_TREE = "5464f749fa119132071fa25d6dc50ea57a3aa840"
EXPECTED_TAXONOMY_ID = (
    "ClassificationTaxonomy:v1:sha256:"
    "399e2a337e7ebecb1bd7a9b21dff5e744c13be36313bc39f16832bc7a57a4d10"
)


def die(message: str) -> None:
    print("K3 FINAL TAXONOMY BINDING = FAIL")
    print(message)
    raise SystemExit(1)


def run(cmd: list[str], *, cwd: Path | None = None) -> str:
    try:
        cp = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", "") or ""
        die(f"Command failed: {' '.join(cmd)}\n{stderr.strip()}")
    return cp.stdout.strip()


def git(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args])


def discover_repo(root: Path) -> Path:
    candidates: set[Path] = set()
    probes = [root]
    try:
        first = [p for p in root.iterdir() if p.is_dir()]
    except OSError as exc:
        die(f"Cannot list root {root}: {exc!r}")
    probes += first
    for base in first:
        try:
            probes += [p for p in base.iterdir() if p.is_dir()]
        except OSError:
            pass

    for probe in probes:
        try:
            top = subprocess.run(
                ["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        if top:
            candidates.add(Path(top).resolve())

    matches: list[Path] = []
    for repo in sorted(candidates):
        try:
            head = git(repo, "rev-parse", "HEAD")
            tree = git(repo, "rev-parse", "HEAD^{tree}")
        except SystemExit:
            continue
        if head == EXPECTED_MAIN and tree == EXPECTED_TREE:
            matches.append(repo)

    if len(matches) != 1:
        die(
            "Could not resolve exactly one local checkout at merged main "
            f"{EXPECTED_MAIN}. Matches: {[str(p) for p in matches]}"
        )
    return matches[0]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def envelope(content: Any) -> dict[str, Any]:
    return {
        "artifact_type": content.artifact_type,
        "artifact_schema_version": content.artifact_schema_version,
        "semantic_payload": content.semantic_payload,
        "content_sha256": content.content_sha256,
        "artifact_id": content.artifact_id,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"C:\CaptivPortal-Lab")
    ap.add_argument("--repo", default=None)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        die(f"Root not found: {root}")

    if args.repo:
        repo = Path(args.repo).resolve()
        if not repo.is_dir():
            die(f"Repo not found: {repo}")
        head = git(repo, "rev-parse", "HEAD")
        tree = git(repo, "rev-parse", "HEAD^{tree}")
        if head != EXPECTED_MAIN or tree != EXPECTED_TREE:
            die(
                f"Repo identity mismatch: HEAD={head}, TREE={tree}; "
                f"expected {EXPECTED_MAIN}/{EXPECTED_TREE}"
            )
    else:
        repo = discover_repo(root)
        head = git(repo, "rev-parse", "HEAD")
        tree = git(repo, "rev-parse", "HEAD^{tree}")

    sys.path.insert(0, str(repo))
    try:
        from app.device_fingerprint.artifact_content import ArtifactRef
        from app.device_fingerprint.k3_portal_rules import (
            build_k3_internal_provenance,
            build_k3_portal_rule_set_v1,
            evaluate_k3_rules,
        )
        from app.device_fingerprint.taxonomy_artifacts import (
            build_classification_taxonomy_v1,
        )
    except Exception as exc:
        die(f"Cannot import merged-main implementation: {exc!r}")

    taxonomy = build_classification_taxonomy_v1()
    if taxonomy.artifact_id != EXPECTED_TAXONOMY_ID:
        die(f"Accepted taxonomy identity mismatch: {taxonomy.artifact_id}")

    rule_set = build_k3_portal_rule_set_v1()
    payload = rule_set.semantic_payload

    # Re-run every retained K3 test vector against the exact rule-set artifact.
    vector_count = 0
    for vector in payload["test_vectors"]:
        actual = evaluate_k3_rules(
            rule_set,
            vector["feature_schema_version"],
            vector["normalized_input"],
        )
        if actual["matched_rule_ids"] != vector["expected_rule_ids"]:
            die(f"K3 vector rule mismatch: {vector['test_vector_id']}")
        if actual["dimension_outcomes"] != vector["expected_dimension_outcomes"]:
            die(f"K3 vector outcome mismatch: {vector['test_vector_id']}")
        vector_count += 1

    # Explicit accepted-taxonomy compatibility over every canonical K3 target.
    tax = taxonomy.semantic_payload
    platform_values = set(tax["platform_family_values"])
    device_values = set(tax["device_class_values"])
    for rule in payload["rules"]:
        if rule["outcome_kind"] != "CANONICAL_VALUE":
            continue
        dim = rule["dimension_name"]
        target = rule["outcome_id_or_ref"]
        if dim == "platform_family" and target not in platform_values:
            die(f"K3 platform target not admitted: {target}")
        if dim == "device_class" and target not in device_values:
            die(f"K3 device-class target not admitted: {target}")
        if dim in {"manufacturer_family", "model_family"}:
            die(f"Unexpected K3 canonical manufacturer/model target: {target}")

    taxonomy_ref = ArtifactRef(
        taxonomy.artifact_id, taxonomy.content_sha256
    ).as_dict()

    provenance = build_k3_internal_provenance(
        rule_set,
        repository_commit_sha=EXPECTED_MAIN,
        repository_tree_sha=EXPECTED_TREE,
        taxonomy_compatibility=taxonomy_ref,
    )

    prov = provenance.semantic_payload
    if prov["provenance_kind"] != "internal":
        die("K3 provenance kind is not internal")
    if prov["taxonomy_compatibility"] != taxonomy_ref:
        die("K3 provenance taxonomy reference mismatch")
    if prov["repository_commit_sha"] != EXPECTED_MAIN:
        die("K3 provenance repository commit mismatch")
    if prov["repository_tree_sha"] != EXPECTED_TREE:
        die("K3 provenance repository tree mismatch")
    if prov["source_artifact_identity"] is not None:
        die("K3 internal provenance unexpectedly contains source artifact identity")

    schema_compat = {
        (row["source_kind"], row["feature_schema_version"])
        for row in prov["input_schema_compatibility"]
    }
    if schema_compat != {("portal_headers", 1), ("portal_headers", 2)}:
        die(f"K3 schema compatibility mismatch: {sorted(schema_compat)}")

    out_dir = root / "artifacts" / "fe3-k3-final-taxonomy-binding"
    rule_path = out_dir / "k3-portal-rule-set.json"
    provenance_path = out_dir / "k3-knowledge-provenance-manifest.json"

    write_json(rule_path, envelope(rule_set))
    write_json(provenance_path, envelope(provenance))

    report = {
        "execution_contract": "captivportal.fe3.k3.final_taxonomy_binding.v1",
        "repository": str(repo),
        "repository_commit_sha": head,
        "repository_tree_sha": tree,
        "classification_taxonomy": taxonomy_ref,
        "k3_portal_rule_set": {
            "artifact_id": rule_set.artifact_id,
            "content_sha256": rule_set.content_sha256,
            "rule_count": len(payload["rules"]),
            "test_vector_count": vector_count,
        },
        "k3_internal_provenance": {
            "artifact_id": provenance.artifact_id,
            "content_sha256": provenance.content_sha256,
            "taxonomy_compatibility": prov["taxonomy_compatibility"],
            "repository_commit_sha": prov["repository_commit_sha"],
            "repository_tree_sha": prov["repository_tree_sha"],
            "input_schema_compatibility": prov["input_schema_compatibility"],
        },
        "checks": {
            "all_retained_vectors_pass": True,
            "all_canonical_targets_admitted": True,
            "no_manufacturer_model_canonical_target": True,
            "taxonomy_binding_exact": True,
            "repository_binding_exact": True,
            "schema_compatibility_exact": True,
        },
    }
    report_path = out_dir / "fe3-k3-final-taxonomy-binding-report.json"
    write_json(report_path, report)

    print(f"MAIN_HEAD={head}")
    print(f"MAIN_TREE={tree}")
    print(f"REPO={repo}")
    print(f"TAXONOMY_ARTIFACT_ID={taxonomy.artifact_id}")
    print(f"K3_RULE_SET_ARTIFACT_ID={rule_set.artifact_id}")
    print(f"K3_RULE_SET_CONTENT_SHA256={rule_set.content_sha256}")
    print(f"K3_RULE_COUNT={len(payload['rules'])}")
    print(f"K3_TEST_VECTOR_COUNT={vector_count}")
    print(f"K3_PROVENANCE_ARTIFACT_ID={provenance.artifact_id}")
    print(f"K3_PROVENANCE_CONTENT_SHA256={provenance.content_sha256}")
    print("K3_TAXONOMY_COMPATIBILITY=PASS")
    print("K3_SCHEMA_COMPATIBILITY=portal_headers/1,portal_headers/2")
    print(f"RULE_SET_REPORT={rule_path}")
    print(f"PROVENANCE_REPORT={provenance_path}")
    print(f"BINDING_REPORT={report_path}")
    print("K3 FINAL TAXONOMY BINDING = PASS")


if __name__ == "__main__":
    main()
