#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

EXPECTED_BRANCH = "docs/device-fingerprint-production-knowledge-sync"
EXPECTED_HEAD = "c2be27f6ee30e060a8e4adac6a51866a214d24bf"
EXPECTED_PARENT = "7c7c0919c3e546f499b5252ea9479d32c8f494d7"

EN_OLD = """`Device Traffic Enrichment / Device Intelligence (DTI)` is a separate future
architecture/roadmap initiative under Owner + Tech Lead review. It is not part
of TASK-DEVICE-FINGERPRINT-06 and this documentation sync does not present DTI
as implemented or production-active.
"""

EN_NEW = """`Device Traffic Enrichment / Device Intelligence (DTI)` is a separate
architecture/roadmap program whose v0.3 architecture is FINAL / TECH LEAD
ACCEPTED and whose roadmap registration is authorized. It is not part of
TASK-DEVICE-FINGERPRINT-06. Implementation remains NOT authorized, Coder remains
HOLD, production remains unchanged, and the next executable program step is
TASK-DTI-00 in RESEARCH / LAB / INVENTORY mode.
"""

RU_OLD = """`Device Traffic Enrichment / Device Intelligence (DTI)` — отдельная будущая
architecture/roadmap initiative, находящаяся на Owner + Tech Lead review. Она не
является частью TASK-DEVICE-FINGERPRINT-06, и этот knowledge sync не выдаёт DTI
за реализованную или production-active функцию.
"""

RU_NEW = """`Device Traffic Enrichment / Device Intelligence (DTI)` — отдельная
architecture/roadmap program; архитектура v0.3 имеет статус FINAL / TECH LEAD
ACCEPTED, а регистрация roadmap авторизована. DTI не является частью
TASK-DEVICE-FINGERPRINT-06. Implementation по-прежнему НЕ авторизован, Coder
остаётся HOLD, production не меняется, а следующий executable program step —
TASK-DTI-00 в режиме RESEARCH / LAB / INVENTORY.
"""

MODULE_OLD = """Device Traffic Enrichment / Device Intelligence is future architecture work. It
must not be described as already implemented Device Fingerprint behavior.
"""

MODULE_NEW = """Device Traffic Enrichment / Device Intelligence is a separate accepted
architecture/roadmap program. Its v0.3 architecture is FINAL / TECH LEAD ACCEPTED
and roadmap registration is authorized, but implementation is not authorized,
Coder remains HOLD, and production is unchanged. TASK-DTI-00 is the next
executable RESEARCH / LAB / INVENTORY step. DTI must not be described as already
implemented Device Fingerprint behavior.
"""

def git(repo: Path, *args: str) -> str:
    cp = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        encoding="utf-8",
        errors="strict",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if cp.returncode:
        details = "\n".join(x.rstrip() for x in (cp.stdout, cp.stderr) if x.strip())
        raise RuntimeError(f"git {' '.join(args)} failed" + (f":\n{details}" if details else ""))
    return cp.stdout.strip()

def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path.name}: expected exactly one replacement anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    print("=== DTI v0.3 PRE-PUSH CORRECTION PRECHECK ===")
    branch = git(repo, "branch", "--show-current")
    head = git(repo, "rev-parse", "HEAD")
    parent = git(repo, "rev-parse", "HEAD^")

    if branch != EXPECTED_BRANCH:
        raise RuntimeError(f"wrong branch: {branch}")
    if head != EXPECTED_HEAD:
        raise RuntimeError(f"wrong HEAD: {head}")
    if parent != EXPECTED_PARENT:
        raise RuntimeError(f"wrong parent: {parent}")
    if git(repo, "status", "--porcelain"):
        raise RuntimeError("worktree must be clean before correction")

    print("PASS: exact local commit state")

    replace_exact(repo / "README.md", EN_OLD, EN_NEW)
    replace_exact(repo / "README_RU.md", RU_OLD, RU_NEW)
    replace_exact(repo / "docs/modules/device-fingerprint.md", MODULE_OLD, MODULE_NEW)

    changed = tuple(sorted(line for line in git(repo, "diff", "--name-only").splitlines() if line))
    expected = tuple(sorted(("README.md", "README_RU.md", "docs/modules/device-fingerprint.md")))
    if changed != expected:
        raise RuntimeError(f"unexpected changed scope: {changed}")

    for path in expected:
        subprocess.run(["git", "add", "--", path], cwd=repo, check=True)

    git(repo, "diff", "--cached", "--check")

    # Content gates.
    en = (repo / "README.md").read_text(encoding="utf-8")
    ru = (repo / "README_RU.md").read_text(encoding="utf-8")
    module = (repo / "docs/modules/device-fingerprint.md").read_text(encoding="utf-8")

    required = (
        "FINAL / TECH LEAD ACCEPTED",
        "roadmap registration is authorized",
        "Implementation remains NOT authorized",
        "Coder remains\nHOLD",
        "TASK-DTI-00 in RESEARCH / LAB / INVENTORY mode",
    )
    for needle in required:
        if needle not in en:
            raise RuntimeError(f"EN README missing: {needle!r}")

    for needle in (
        "FINAL / TECH LEAD\nACCEPTED",
        "регистрация roadmap авторизована",
        "Implementation по-прежнему НЕ авторизован",
        "Coder\nостаётся HOLD",
        "TASK-DTI-00 в режиме RESEARCH / LAB / INVENTORY",
    ):
        if needle not in ru:
            raise RuntimeError(f"RU README missing: {needle!r}")

    for needle in (
        "FINAL / TECH LEAD ACCEPTED",
        "roadmap registration is authorized",
        "implementation is not authorized",
        "Coder remains HOLD",
        "TASK-DTI-00 is the next",
        "RESEARCH / LAB / INVENTORY",
    ):
        if needle not in module:
            raise RuntimeError(f"module missing: {needle!r}")

    if "under Owner + Tech Lead review" in en:
        raise RuntimeError("stale EN DTI review wording remains")
    if "находящаяся на Owner + Tech Lead review" in ru:
        raise RuntimeError("stale RU DTI review wording remains")
    if "is future architecture work" in module:
        raise RuntimeError("stale module DTI architecture wording remains")

    print("PASS: DTI v0.3 content correction")
    print("PASS: exact 3-file correction scope")
    print("PASS: git diff --cached --check")

    # Amend the existing docs commit, preserving its message.
    subprocess.run(["git", "commit", "--amend", "--no-edit"], cwd=repo, check=True)

    new_head = git(repo, "rev-parse", "HEAD")
    new_tree = git(repo, "rev-parse", "HEAD^{tree}")
    new_parent = git(repo, "rev-parse", "HEAD^")
    if new_parent != EXPECTED_PARENT:
        raise RuntimeError(f"unexpected amended parent: {new_parent}")
    if git(repo, "status", "--porcelain"):
        raise RuntimeError("worktree not clean after amend")

    files = tuple(sorted(line for line in git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines() if line))
    if len(files) != 13:
        raise RuntimeError(f"amended commit no longer has 13 files: {len(files)}")

    print("=== DTI v0.3 PRE-PUSH CORRECTION PASS ===")
    print(f"OLD_COMMIT={EXPECTED_HEAD}")
    print(f"NEW_COMMIT={new_head}")
    print(f"NEW_TREE={new_tree}")
    print(f"PARENT={new_parent}")
    print(f"FILES={len(files)}")
    print("PUSH=NO")
    print("PR=NO")
    print("MERGE=NO")
    print("DEPLOY=NO")

if __name__ == "__main__":
    main()
