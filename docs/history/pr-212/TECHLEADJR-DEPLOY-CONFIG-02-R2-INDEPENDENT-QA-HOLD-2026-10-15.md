# CaptivPortal — DEPLOY-CONFIG-02 / R2 Independent QA

**2026-10-15 • TechLeadJR • Status: QA HOLD / NO COMMIT, PUSH, PR, MERGE OR DEPLOY**

## 1. Chain of custody

- Base HEAD: `84b80376b13002d435be28eec98b91b9cbf71c63`
- Base TREE: `fda2f2dad7c1f9c89d383ef0bef63f8aebfc93b8`
- Accepted for QA candidate TREE: `a787a5ad842aa72189423e0d0940567b31b1b953` (reproduced from WSL external Git index and Windows isolated Git synthetic QA commit)
- Supplied replacement patch: 69,323 bytes, SHA256 `4762fe3e30a326cdd658f1da467dfb6c9232dd1fee39c0f3c9f17b79b4fe7600` (verified in both sandbox and Lab)
- 15 changed files; exactly 3 production Python files within Architect allowlist; `git diff --check` PASS; no task commit/push/PR.
- Windows isolated QA checkout synthetic commit: `3c2c676d16138a894fdf257900652f11fd0a6883`, TREE exact candidate, clean. This is a **Lab-only synthetic commit**, not publication or Coder history.

## 2. Independently executed tests

| Gate | Result | Notes |
|---|---|---|
| Linux focused Sensor + Portal | **271 PASS / 0 FAIL** | Same 11-file suite, Python 3.10.12 |
| Linux T05 full selected file | **33 PASS / 0 FAIL** | Bridge, bonding, links, preflight guards |
| Windows focused Sensor + Portal | **268 PASS / 3 FAIL** | 3 new test portability failures, Windows Central Lab Python interpreter |
| Linux full candidate | **Interrupted at 52%** | 4,340 PASS, 2 FAIL, 1 SKIP before interrupt; **not** full gate PASS |
| Official Windows strict V7 | **NOT RUN** | Candidate already has 3 new focused FAIL; formal V7 remains required |
| Live disposable TLS receiver matrix / receiver admission | **NOT YET VERIFIED** | Mandatory independent security proof not yet established |

Linux full run was stopped with SIGINT after a new Windows-focused blocker was established. Its two observed failures were the previously reported SQLite query-plan assertions concerning `MATERIALIZE validated_cycles` in `tests/analytics/test_historical_traffic_peak.py` and `tests/analytics/test_historical_traffic_statistics.py`; baseline-equivalence of this **new** candidate has not been independently re-established in this attempt. **Do not infer overall regression PASS** from the interrupted run.

## 3. Blocking issue: Windows path representation in T07/T08/T09 test

Three parametrized cases in `tests/device_fingerprint_portal/test_deploy_isolation.py` fail for `[200]`, `[401]`, `[403]` in `test_T07_T08_T09_portal_exact_transport_tuple_and_verified_ca_injection`.

At `read_credential(path, **_kwargs)`, the assertion `str(path) == config.credential_path` compares the Windows-rendered `\\lab\\portal.bearer` with the expected literal `/lab/portal.bearer`. This is a **test assertion portability error** in a newly introduced test. The production credential-reading implementation has not been shown defective by these failures. A safe minimal correction is `assert path.as_posix() == config.credential_path` (or equivalent cross-platform lexical POSIX comparison). Preserve path/credential identity checks and all 200/401/403 assertions; do not relax expected transport behavior.

## 4. Coder directive and follow-up gates

1. Change **only** `tests/device_fingerprint_portal/test_deploy_isolation.py` at the credential path mock assertion to use a cross-platform path representation. Production files, T05 fix and all other tests must remain byte-identical to this candidate. No skipped/xfail tests.
2. Rerun the exact 11-file Linux and Windows focused suites, including 33 T05 cases; require **0 FAIL** on both operating systems.
3. Supply new patch, SHA256, candidate TREE, file hashes, Linux/Windows focused logs; keep worktree dirty/uncommitted.
4. TechLeadJR then reruns independent gates including strict Windows V7, full Linux, real TLS and receiver/provenance checks. A historic Windows baseline failure is not automatically excused: any release-gate exception needs an Architect decision and conscious Owner approval specific to DEPLOY-CONFIG-02.
5. No production VM changes. Owner alone controls merge, publication still on HOLD.

**VERDICT: R2 NOT ACCEPTED FOR PUBLICATION; BOUNDED TEST-ONLY CORRECTION REQUIRED.**
