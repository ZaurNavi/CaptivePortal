# CaptivPortal — SSR-01B R2 — Tech Lead final Coder directive

**Date:** 2026-10-16 (Asia/Baku)  
**Status:** `CODE_REVIEW=PASS`; `CODER_COMMIT_PUSH_DRAFT_PR=GO_TEST_ONLY`; `RELEASE_ACCEPTANCE=HOLD`; `OWNER_MERGE_ONLY`; `PRODUCTION=OBSERVATION_FREEZE`.

## Authority and scope

Owner explicitly instructed Tech Lead to perform the remaining review directly and authorize Coder to **commit, push and open a PR**, reserving **merge to Owner**. Tech Lead grants a narrow **TEST-ONLY / EXPERIMENTAL publication exception** under `docs/agents/task-contract.md` because ordinary pre-publication release gates are not yet all PASS. The exception does **not** convert the candidate into accepted/deployable release code and does not authorize merge, deployment, systemd installation or activation.

## Exact allowed artifact

- Repo: `ZaurNavi/CaptivePortal`
- Task: `TASK-SSR-01B-1+2` / Coder R2
- Base HEAD: `7e84bc563f1b6dd3d72da66ae25849d9a7d96540`
- Base TREE: `ea664b1d49ace86fc8a0c4ab2fc52945531e574a`
- Candidate TREE: `7d567333cf45f8b901252e892c51f18867c783c1`
- Replacement patch: `TASK-SSR-01B-1+2-R2.patch`
- Patch SHA256: `3d720dbcd8308396211b201ec12e299fb225c720a430f6e34dcf09ebcfcec7f8`
- 5 changed files only: `deploy/device-fingerprint/fingerprint-sensor.service`, `deploy/device-fingerprint/fingerprint-suricata.service`, `docs/deployment.md`, `tests/device_fingerprint_sensor/test_deployment_outputs.py`, `tests/device_fingerprint_sensor/test_ssr01b_systemd_contract.py`.

## Tech Lead review evidence

1. R2 ZIP integrity/CRC and inventory checks PASS. Exact replacement patch checksum PASS. HEAD/TREE independently recomputed on dedicated laptop WSL worktree; candidate TREE matches exact SHA above; `git diff --check` PASS.
2. Coder R2 focused tests: **29 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, including five 30s missing-socket attempts (sixth denied in 300.436 s), five slow-90s attempts (sixth denied in 600.475 s), and cold start + 3 deliberate Sensor restarts + Suricata crash/recovery without `reset-failed`.
3. Tech Lead independently reran **27 selected focused tests: 27 PASS, 0 FAIL**, on WSL Ubuntu 22.04 / systemd 249.11-0ubuntu3.22 in 76.53 s, with fresh isolated evidence at `/home/zaur_navi/captivportal-lab/ssr01b-techlead-r2-recheck-20261016` and JUnit `/home/zaur_navi/captivportal-lab/ssr01b-techlead-r2-recheck.xml`. The two long-duration timeout/saturation cases were **not repeated** by Tech Lead; Coder's full raw records and timings were independently reviewed.
4. Tech Lead's earlier isolated lab independently verified authentic Suricata 8.0.6 offline PCAP → AF_UNIX SOCK_DGRAM EVE events, live-vs-stale socket and receiver-disconnect event losses. **This is not proof of full production Sensor/Evidence/NI source-health pipeline or physical HDD**.
5. R1 P1 (`start-limit-hit` after third successful Sensor restart) reproduced RED; R2 5/750 policy and no-automatic-reset correction reviewed and passed focused tests.

## Coder instructions — publication phase only

1. Use **only** the exact reviewed R2 replacement patch/worktree. Do not use R1. Confirm base HEAD/TREE and candidate TREE before proceeding. If the repository's current target branch/base has changed incompatibly, **STOP and report**; do not silently rebase, modify files, change test expectations, or change approved numeric parameters.
2. Create a dedicated task branch and one scoped commit for the five-file candidate. After commit confirm **the commit TREE equals `7d567333cf45f8b901252e892c51f18867c783c1`** and `git diff --check` is clean. Do not include logs, generated files, credentials or ZIP evidence in the source commit.
3. Push only the dedicated task branch and open a **Draft PR** against the correct project base branch. Title begins `[TEST-ONLY][SSR-01B]`. PR description must explicitly state `RELEASE_ACCEPTANCE=HOLD / NOT MERGEABLE / NO PRODUCTION`, the exact HEAD/TREE, patch SHA256, Tech Lead's 27 PASS, Coder's 29 PASS, test limitations, and links/references to the evidence. This is an **exception for review visibility**, not regular publication acceptance.
4. **Never merge or mark ready for review/merge** on your own. Owner alone decides merge after necessary independent release gates. Do not install or edit production systemd, start/stop production units, change networks, or run load tests on production.
5. Return PR URL, branch, commit SHA, committed TREE, remote push confirmation, and a concise list of remaining gates to Tech Lead. If GitHub policy disallows Draft PR or the branch cannot be published, stop and report the exact blocker; do not bypass permissions.

## Remaining mandatory release/activation gates (not claimed PASS)

- Official Windows **Central Lab V7** full strict regression on the exact candidate.
- Full nonproduction real Sensor + Suricata 8.0.6 EVE/heartbeat/source-health/durable ACK/gap contract (or explicit approved equivalence and separate uncovered activation HOLD).
- Deployed `suricata`/`fingerprint-sensor`/`fingerprint-eve` credentials-free permission/path attestation and safe rollback.
- Adequate actual boot, startup budget, slow-storage/performance and Auth responsiveness in the chosen target environment. Laptop virtual-fsync results are not physical-production HDD proof.
- Separate Owner merge authorization and later *separate* SysAdmin/Owner production deployment GO (not given).

## Machine disposition

```ini
TASK=TASK-SSR-01B-1+2
CANDIDATE=R2
TECH_LEAD_CODE_FOCUSED_REVIEW=PASS
TECH_LEAD_INDEPENDENT_FOCUSED_RECHECK=27_PASS_2_LONG_CASES_EVIDENCE_REVIEWED
R2_CODER_FOCUSED=29_PASS
TEST_ONLY_PUBLICATION_EXCEPTION=OWNER_PLUS_TECHLEAD_AUTHORIZED
CODER_COMMIT=GO_EXACT_TREE_ONLY
CODER_PUSH=GO_TASK_BRANCH_ONLY
CODER_DRAFT_PR=GO_EXPERIMENTAL_NOT_MERGEABLE
OWNER_MERGE=RESERVED_NOT_AUTHORIZED
RELEASE_ACCEPTANCE=HOLD
PRODUCTION=OBSERVATION_FREEZE
DEPLOY=NO
```
