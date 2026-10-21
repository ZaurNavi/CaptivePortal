# QIO02_P2_H1_CODER_R2 — narrow Windows test compatibility repair

Status: IMPLEMENTED_IN_ISOLATED_LAB / FOCUSED_TESTS_ONLY / AWAITING_TECHLEAD_INDEPENDENT_REVIEW.

## Exact identities

```ini
BASE_HEAD=191beda1f23f8f466d2431f42e57571815d85778
BASE_TREE=3f6d0a05c5d893d3139db44a1692c81e67fd6c6e
INCOMING_TREE=7fc908e1e6e5b2ae96f00a50adc7bce321620c62
INCOMING_PATCH_SHA256=63ce6d7020ffa9e68e93711d9017e0d2cfbc5aa49dbfe097820ce584be09a742
R2_CANDIDATE_TREE=23302d2048ce9fb55cb17c2557fdc8ee635cc6aa
BRANCH=task/qio-02-p2-h1-stable-retired-eof
WORKTREE=/home/zaur_navi/captivportal-lab/worktrees/qio-02-p2-h1-candidate
HEAD=UNCHANGED_BASE_HEAD
WORKTREE_STATE=DIRTY
ORDINARY_GIT_INDEX=EMPTY_UNCHANGED
```

Candidate tree calculated using a new external index, not a commit. Original incoming patch/hash and both runtime file hashes were verified before editing. No baseline reconciliation, fetch, merge or history modification was needed/performed.

## Exact R2 scope

Only `tests/test_public_traffic.py` changed relative to the incoming candidate: 30 insertions / 3 deletions, within the existing parameterized `test_H1_C11_C13_C16_invalid_file_proof_uses_legacy_write`. No tests added/removed/renamed; all C01–C20 coverage and original assertions preserved, additional proof/durable-state assertions added.

- POSIX: the existing actual unlink / rename / replacement of the open archive remains unchanged. The real validator must reject it and legacy UPSERT must occur.
- Windows: the archive remains open and is NOT physically unlinked/renamed. At the same proof callback seam, missing raises `FileNotFoundError` from `Path.stat`; replace returns a stat signature with another inode; rename returns a changed ctime_ns signature. The actual `_verify_stable_retired_eof()` is invoked in all cases, not mocked to return false. The stat mock is scoped to that invocation only.
- On both platforms the validator result must be exactly `[False]`, scan succeeds, exactly one legacy reader-state UPSERT is observed, all seven recovery fields are preserved and the durable timestamp equals the current service clock. The original proof-error case also remains covered.
- No sleep, skip, xfail, deselect, relaxed assertion or product behavior change.

Runtime files remain byte-identical to the incoming tree:

| File | Bytes | SHA256 |
|---|---:|---|
| app/public_traffic/reader.py | 16384 | 812f5c92ec69a496f853d23dcd343a12cb52ddde07b233a2caf22aea7c14c536 |
| app/public_traffic/repository.py | 28746 | 934a3a5f373080255aad1de1fb1ca97cc062d4f92141f3ef0024343dac5e9417 |
| tests/test_public_traffic.py (R2) | 72938 | 078135dfb4f9fb90ca33bbf67c6856100fdc69bf5efcf3e4bb6dfd72a45de421 |

No runtime config, SQLite schema/mode, library or other file changed. The full replacement patch still contains the THREE original authorized files, because it is measured from the frozen baseline, not from the incoming candidate.

## Patches

| Artifact | Baseline | Bytes | SHA256 |
|---|---|---:|---|
| qio02-p2-h1-r2-replacement.patch | 191beda… | 25229 | 8eac6bb360881083150995ff9da0381059e8daae8c3449aa2bb6480751c41755 |
| qio02-p2-h1-r2-only.patch | incoming 7fc908… tree | 2688 | 5a7f9979f56d20301b8c09cee37c5c5e7c534b0b95ef7cad50bf16aee08d5b9d |

Full replacement stat: 3 files, 539 insertions / 1 deletion. R2-only stat: 1 test file, 30 insertions / 3 deletions. Both patches pass reverse-apply check against the current candidate without changing it. `identity.json` and `static-identity.log` contain exact file inventory/status/hashes.

## Focused evidence

| Platform | Result | Log / JUnit |
|---|---|---|
| WSL2 Ubuntu 22.04, Python 3.10.12 | 126 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 0 DESELECTED | focused-linux.log / focused-linux.xml |
| Native Windows, Python 3.10.11 | 126 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 0 DESELECTED | focused-windows.log / focused-windows.xml |

All three formerly failing IDs now PASS on each platform:

```text
tests/test_public_traffic.py::test_H1_C11_C13_C16_invalid_file_proof_uses_legacy_write[missing]
tests/test_public_traffic.py::test_H1_C11_C13_C16_invalid_file_proof_uses_legacy_write[replace]
tests/test_public_traffic.py::test_H1_C11_C13_C16_invalid_file_proof_uses_legacy_write[rename]
```

The fourth `[proof_error]` case also PASS/PASS. `test-inventory.json` contains all exact IDs/outcomes/timings on both platforms; the same 126 IDs are preserved and paired with the incoming candidate inventory.

Linux command from the candidate worktree:

```sh
PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/qio02-p2-h1-pycache \
/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python \
  -m pytest -q -p no:cacheprovider tests/test_public_traffic.py \
  --basetemp=/tmp/qio02-h1-r2-correction-linux \
  --junitxml=/mnt/c/CaptivPortal-Lab/handoffs/qio02-p2-h1-r2-coder-20261016/focused-linux.xml
```

Windows command from `\\wsl.localhost\Ubuntu-22.04\home\zaur_navi\captivportal-lab\worktrees\qio-02-p2-h1-candidate`:

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\qio02-h1-r2-pycache'
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider tests/test_public_traffic.py --basetemp=C:\CaptivPortal-Lab\tmp\qio02-h1-r2-correction-windows --junitxml=C:\CaptivPortal-Lab\handoffs\qio02-p2-h1-r2-coder-20261016\focused-windows.xml
```

Static checks: `python -m compileall -q tests/test_public_traffic.py` PASS on Linux AND Windows, with the external bytecode prefixes above; `git diff --check` PASS both frozen-base and incoming-tree comparisons; external-index cached diff-check PASS. Versions in `environment-linux.json`, `environment-windows.json`. `capture_r2.py` records the static/identity checks and creates the external-index tree.

## Limits / rollback / ownership

This R2 proves Windows-compatible negative validation, NOT successful physical unlink/rename of an in-use Windows file. Actual POSIX mutations remain independently executed on Linux. No filesystem/SQLite atomicity or other new product claim is made. Original Architecture v1.4 residuals remain unchanged.

Full Central/Windows/Linux suites, independent PERF and acceptance remain Tech Lead-owned and were NOT run by Coder. Prior R1 measurements are historical, not newly executed R2 performance evidence. No new implementation blocker found.

Rollback R2 only: preserve the R2 patches/evidence, then restore only the test file's incoming blob from tree `7fc908e1e6e5b2ae96f00a50adc7bce321620c62` (or reverse the R2-only patch under explicit authorization). Do NOT restore from HEAD: that would discard the original H1 tests as well. Runtime files need no rollback. No rollback/deletion/reset was executed. Original R1 handoff and ZIP remain untouched.

```ini
SOURCE_RUNTIME_CHANGE=NO
FULL_GATES=NOT_RUN_TECHLEAD_OWNED
PERF_RERUN=NO
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACCESS=NO
PRODUCTION_ACTION=NO
NEXT_ACTION=TECH_LEAD_R2_REVIEW
```
