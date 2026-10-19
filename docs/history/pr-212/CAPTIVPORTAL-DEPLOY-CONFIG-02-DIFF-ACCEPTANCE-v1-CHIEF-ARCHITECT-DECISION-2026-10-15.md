# CAPTIVPORTAL — DEPLOY-CONFIG-02
## Chief Architect Release-Gate Disposition — `DEPLOY-CONFIG-02-DIFF-ACCEPTANCE-v1`

**Date:** 2026-10-15 · Asia/Baku  
**Request / TASK:** `CAPTIVPROD-DEPLOY-CONFIG-02` / `TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1`  
**Decision:** **APPROVE CONDITIONAL TASK-SCOPED DIFFERENTIAL ACCEPTANCE ROUTE**  
**Implementation:** Device Fingerprint Sensor / Portal Producer *deployment configurability*, R3 candidate after T05 amendment  
**Applicability:** **one TASK, one exact candidate TREE, one baseline, one explicit Owner exception**  
**Baseline HEAD:** `84b80376b13002d435be28eec98b91b9cbf71c63`  
**Baseline TREE:** *to be pinned from the exact baseline Git commit in the QA evidence; not supplied in request*  
**Candidate R3 TREE:** `ea664b1d49ace86fc8a0c4ab2fc52945531e574a`  
**Patch SHA256 (reported):** `51c39c08c15663c0d4f9a8964c378257dae34be90edcbc7f6415805e11da7d55`  
**Code status:** `IMPLEMENTATION_QA_PASS` as reported by TechLeadJR; source patch/full raw QA logs have **not** been independently supplied to this Chief Architect  
**Release status:** `EXCEPTION_METHOD_APPROVED / FINAL_DIFFERENTIAL_ACCEPTANCE_PENDING_EVIDENCE_ATTESTATION_AND_OWNER_SIGNOFF`  
**Publication / PR / merge:** **HOLD now**; may proceed only through §5  
**Production / source admission / sensor activation:** **SEPARATE HOLD**

**Normative lineage:** `CAPTIVPORTAL-DEPLOY-CONFIG-02-CHIEF-ARCHITECT-CONTRACT-v1-FINAL-2026-10-15.md`; `CAPTIVPORTAL-DEPLOY-CONFIG-02-T05-ARCHITECT-AMENDMENT-v1-2026-10-15.md`; repository `docs/testing.md`, `docs/testing-environments.md`, `docs/deployment.md`. This decision **does not** inherit or automatically reuse the separate `DEPLOY-CONFIG-01-DIFF-ACCEPTANCE-v1` exception. No project-wide gate policy or Windows runner is changed.

---

## 1. Decision and exact limits

**Chief Architect approves a task-scoped, baseline-equivalence alternative acceptance method.** The normal official Windows Central Lab **V7 strict gate remains NOT PASSED** for this R3 candidate: the original V7 runner was **not executed** on this candidate (the QA worktrees were isolated clones not accepted by its worktree allowlist). Consequently **do not report `V7=PASS`**. The equivalent four-stage execution is evidence only for the newly authorized **task-specific differential gate**.

TechLeadJR **does not need to rerun the entire Windows suite under the original V7 command merely to recreate an inaccessible worktree topology**, provided that all *conjunctive* requirements G0–G4 below are independently attested. In particular, the full direct Windows pytest invocation must be shown to have reproduced the substantive strict V7 test selection and safety behavior. If equivalence cannot be proven, **the original V7 runner on an eligible clean immutable Lab artifact becomes mandatory**; do not edit the allowlist or runner to force PASS, and do not widen this implementation task to repair unrelated Windows/NI failures.

The method accepts **demonstrably pre-existing failures** for this candidate only. It does not turn baseline failures into warnings, add permanent test exclusions, create `xfail` allowances, excuse new regressions or establish a general Windows/Linux platform exception.

**No new code corrections are requested.** Application code, runner, tests, CI scripts, SQLite and production are not authorized to change under this decision. New candidate TREE / changed patch bytes after acceptance invalidate the acceptance and require change analysis and requalification.

## 2. QA findings reported to Architect — claims versus acceptance

| Dimension | TechLeadJR report | Architectural disposition |
|---|---|---|
| Exact baseline | `84b80376b13002d435be28eec98b91b9cbf71c63` | Confirm exact baseline **TREE** and raw materialization before G0 PASS |
| R3 candidate | TREE `ea664b1d49ace86fc8a0c4ab2fc52945531e574a`; patch SHA256 as above | Unique exception target; commit SHA does not yet exist |
| Windows focused | **271 PASS** | Positive; test list must be attributed to candidate TREE |
| Linux focused | **271 PASS** | Positive |
| Linux T05 | **33 PASS** | Security preflight correction evidence |
| Linux cross-module | **276 PASS** | Positive independent regression coverage |
| Disposable direct-TLS matrix | **14 PASS** | Positive TLS identity/transport coverage |
| Actual Evidence receiver over disposable TLS | **10 PASS** | Positive producer/receiver admission-negative/positive evidence; confirm exact cases |
| Windows full direct differential: baseline | **7730 PASS / 250 FAIL / 34 SKIP** | Baseline context; *not* V7 runner success |
| Windows full direct differential: R3 | **7944 PASS / 250 FAIL / 34 SKIP** | Candidate context; *not* V7 runner success |
| Differential failure sets | **all 250 failed pytest node IDs identical**; **278 normalized error lines identical**; **candidate-only FAIL = 0** | Strong baseline-equivalence evidence; require raw trace inventory and no masking |
| Windows collected-count delta | **+214 PASS** (total baseline 8014, candidate 8228); FAIL and SKIP counts unchanged | Map **all 214 added node IDs** to authorized R3 tests; ensure no lost original tests or collection truncation |
| Linux full R3 | **8224 PASS / 3 FAIL / 1 SKIP** | Remains full-suite FAIL; exact targeted baseline and environment explanations required |
| Linux 2× SQLite `MATERIALIZE validated_cycles` FAIL | Identical on clean baseline and candidate in targeted replay, per report | Acceptable only after G2 proves same node IDs, signatures and conditions |
| Linux 1× Unix-socket FAIL | Long QA `basetemp` path; same test passes on baseline and R3 with short `basetemp` | Acceptable as proven harness/path-limit artifact only under G2; no test change/skip |
| Official Windows V7 | **original runner not run on R3** | `OFFICIAL_V7=NOT_RUN_ON_R3 / NOT_PASSED`; retain historic failures; no PASS label |
| Source/security & scope | Only approved production files, diff-check and Git TREE PASS, per report | G3 verification still required in signed evidence report |

**Evidence status:** These are **reported independent TechLeadJR test outcomes**. The Chief Architect has not physically rerun the suites or been given the complete original JUnit/runner logs, so the evidence is sufficient to approve the **conditional route**, **not** sufficient to pronounce final independent acceptance on behalf of Tech Lead / Owner.

## 3. Mandatory alternate differential acceptance: G0–G4

All gates are conjunctive. No gate may be silently removed because other tests are green.

### G0 — Exact artifact and test-selection chain of custody

1. Pin baseline **commit HEAD and TREE** and candidate **TREE** from real Git artifacts. Verify candidate tree equals `ea664b1d49ace86fc8a0c4ab2fc52945531e574a` and patch bytes hash to `51c39c08c15663c0d4f9a8964c378257dae34be90edcbc7f6415805e11da7d55`. Original test runs must link unambiguously to those artifacts.
2. Preserve raw Windows/Linux baseline+R3 JUnit, stdout/stderr, pytest collection data, test environment snapshots, command lines, runner revision/hash, dependency versions, `git diff --check`, compilation logs and verified clean/immutable materializations. Lab-only detached commits may attest immutable trees but are not publication commits.
3. Confirm only three approved production source files were changed: `app/device_fingerprint_sensor/config.py`, `app/device_fingerprint_sensor/capture.py`, `app/device_fingerprint_portal/config.py`. All other changes must be within authorized focused tests and documentation of the architecture contract / T05 amendment. Show exact changed-file list.
4. No changes to failing test expectations, test deletion, `xfail`, conditional deselection, pytest monkeypatches designed to suppress known failure, altered dependencies or manipulated data to manufacture baseline equivalence.
5. Verify that the **+214 Windows successes** correspond to exactly identified new/modified permitted test node IDs and that **every baseline test ID** remains collected in the candidate (subject only to an explicit proven approved rename, not silent omission). Baseline/candidate skip sets must be compared by node ID, not only number.

### G1 — Windows V7-substantive equivalence and 250-case baseline differential

1. TechLeadJR must inspect the actually current, approved Windows V7 runner and produce a **V7↔direct-execution parity table** covering: interpreter and dependencies, working directory/checkout byte identity, pytest command/selection and plugins, `-k`/markers, test collection, handling of expected failures/skips, test temp roots, environment and setup, **compileall**, branch diff, and exact immutable-tree check. The *verified current runner*, not a filename remembered from documentation, is authoritative.
2. The direct R3 and baseline full pytest must have been executed with materially equivalent, strict test-selection behavior and no accidental deselection/exclusion. Include the ordinary **six formerly excluded strict compatibility cases** from `docs/testing.md`; they must retain strict test treatment and **PASS on R3** for this exception. Neither a baseline-equivalent failure of one of those protected six nor a WARN/xfail route is automatically allowed under this exception.
3. Produce a machine-readable mapping of **all 250 exact failing node IDs**: baseline and candidate failure outcomes, raw exception/traceback signatures and normalized-line identity. Preserve the **278 normalized error lines** and the normalization rules. A normalization that erases materially different error causes is not acceptable. Show **zero new candidate-only failures**, zero changed signatures left unexplained, zero truncation, and no newly skipped/deselected baseline cases.
4. Independently attest the other **three substantive V7 stages** (compileall, diff-check, immutable-tree verification) on the exact R3 tree, with commands and results. A direct 4-stage parity reproduction **is not** an official V7 PASS; it supports only `DEPLOY-CONFIG-02-DIFF-ACCEPTANCE-v1`.
5. **Original V7 runner rerun is not mandatory** if items G1.1–G1.4 PASS. **Mandatory fallback:** if the runner has additional meaningful security/test logic not executed by the direct method, parity cannot be shown, protected six fail, or test inventory differs without approved explanation, stop with `RELEASE_HOLD`. Use the official V7 runner on an allowed immutable Lab worktree without modifying its policy, or seek a separately approved platform-gate remediation. Merely reusing a summary count is insufficient.

### G2 — Linux full failures: targeted sufficient, provided exact attribution

1. Preserve Linux full R3 `8224 PASS / 3 FAIL / 1 SKIP` as **full-suite FAIL**. Enumerate all three node IDs and raw signatures.
2. For the two SQLite planner/`MATERIALIZE validated_cycles` assertions, show targeted comparison on clean baseline and R3 with matching node IDs, SQL/`EXPLAIN` assumptions, observed signatures, Python/SQLite versions and selection context. No production patch to the SQLite planner or NI subsystem is allowed to fix unrelated inherited failures.
3. For the Unix-socket case, retain evidence that the long `basetemp` path creates a Unix-domain-socket path-length failure, and that **both** baseline and R3 pass the identical test with the **same sufficiently short `basetemp`**. No changed test body, mock, skipped assertion, system-service dependency or runtime workaround allowed. A path-length constraint is a QA harness issue, not proof of a candidate runtime defect.
4. Require no candidate-only Linux fail/skip. A new full Linux baseline run is **not mandatory** under this *specific* exception if all three failures have matching, controlled targeted evidence, full R3 collection is intact, and the isolated focused/cross-module suites are green. Incomplete/mismatched evidence restores `HOLD` and requires appropriate additional same-environment baseline/candidate runs.

### G3 — D02 / T05 / security gates remain mandatory

1. Attribute reported **271 Windows focused, 271 Linux focused, 33 Linux T05, 276 Linux cross-module, 14 direct-TLS, 10 actual disposable receiver** passing cases to exact R3 TREE; explain overlap so counts are not misleadingly summed as independent unique tests.
2. Confirm old Sensor/Portal Producer defaults and disabled behavior unchanged; valid new deployment settings accepted; invalid identities/networks/URLs/ports/secret path inputs fail-closed as specified; Sensor process remains independent of writable main settings; Portal Producer errors remain fail-soft to guest authorization.
3. Confirm T05 explicitly rejects `master`, `bridge`, `bonding` for **directory, live symlink and dangling symlink**, maintains full non-L3/SPAN preflight and permits an independently named eligible physical NIC. No raw capture starts after a failed preflight. AF_PACKET/frozen BPF, timestamp semantics, source-health and attribution contracts unchanged.
4. Confirm existing receiver enforcement: Producer ID, Capture Source ID, Site, source kind, guest scope, distinct credentials, authenticated direct peer and full certificate/SAN/CA verification. Producer configuration alone never auto-registers identities or grants F-B1/source-binding/classification admission. No bypass of TLS, bearer admission or direct network restrictions.
5. Independent final Tech Lead security/source review must explicitly record **open P0=0, open P1=0** for R3 and verify no unauthorized changes to auth, Omada, CAPPORT, Fingerprint classification, NI, SQLite, systemd or deployment infrastructure. Do not infer this solely from focused PASS counts.

### G4 — Release authority, evidence and immutable Git publication

1. TechLeadJR issues one signed/attributed **`DEPLOY-CONFIG-02-DIFF-ACCEPTANCE-v1` Evidence Report**, binding all G0–G3 claims to exact baseline HEAD/TREE, R3 TREE, original raw logs, test IDs, signatures, environment/runner parity and patch hash. Explicitly report `OFFICIAL_WINDOWS_V7=NOT_RUN_ON_R3 / NOT_PASSED`, `LINUX_FULL=FAIL_BASELINE_ATTRIBUTED`, and distinguish that from `TASK_DIFF_ACCEPTANCE=PASS` if the conditions are met.
2. Owner must explicitly authorize **this one-time DEPLOY-CONFIG-02 task-specific exception** with knowledge of the official Windows V7 non-PASS and Linux full inherited failures. No automatic reuse of the prior DEPLOY-CONFIG-01 exception; a generic approval to merge is not equivalent to informed signoff of this particular exception.
3. **Only after G0–G3 PASS and Owner exception signoff**, TechLeadJR may issue a separate **Coder GO for a publication commit, push and PR** corresponding to **exact R3 TREE**. No code/test/docs changes during publication; verify candidate TREE = publication TREE = PR HEAD TREE. If any tree difference, stop and re-evaluate gates.
4. PR review and merge are distinct: **merge remains Owner-only** after release review. This decision does not authorize deployment to `captiv-prod` or old VM, restarting Sensor, SPAN configuration, source registration, Evidence receiver live authorization, F-B1 admission, credentials provisioning, or any production data migration. Each stays under its separate Owner/SysAdmin/Source Governance gates.

## 4. Explicit allowed deviations and stop conditions

**Permitted for this one artifact only:** pre-existing Windows failures proven identical for all 250 raw node IDs/signatures; Linux two baseline-identical SQLite planner assertions; Linux Unix socket path-length harness error proven by identical short-path reproduction. These are **attribution findings**, not globally accepted test regressions.

**Never permitted:** official Windows V7 PASS claim without an actual passing V7 run; hidden strict test exclusions; suppression or reinterpretation of the six protected compatibility cases; baseline/candidate failure-count equality without full node-ID evidence; unexplained +214 test delta; unsafe new source admission; candidate-only errors; altered test inputs/patch/runner to manufacture equivalence; release with open P0/P1; Coder publication before G4 Owner approval; any production activation under this decision.

**Fallback:** If evidence parity/inventory cannot be proven or any G0–G3 condition fails, the R3 candidate remains `RELEASE_HOLD`. The next permitted steps are a specific additional independent evidence run, the original V7 runner in an approved clean location, or a **separate** platform-gate remediation task. None broadens `TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1` or changes its production source scope.

## 5. Status / machine-readable verdict

```text
REQUEST=CAPTIVPROD-DEPLOY-CONFIG-02
TASK=TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1
EXCEPTION_ID=DEPLOY-CONFIG-02-DIFF-ACCEPTANCE-v1
ARCHITECT_VERDICT=CONDITIONAL_APPROVAL
ACCEPTANCE_METHOD=TASK_SCOPED_BASELINE_EQUIVALENCE
BASE_HEAD=84b80376b13002d435be28eec98b91b9cbf71c63
BASE_TREE=TO_BE_PINNED_IN_EVIDENCE
R3_TREE=ea664b1d49ace86fc8a0c4ab2fc52945531e574a
PATCH_SHA256=51c39c08c15663c0d4f9a8964c378257dae34be90edcbc7f6415805e11da7d55
WINDOWS_DIRECT_BASELINE=7730_PASS_250_FAIL_34_SKIP
WINDOWS_DIRECT_R3=7944_PASS_250_FAIL_34_SKIP
WINDOWS_FAILURE_NODE_IDS=250_MATCH_REPORTED
WINDOWS_NORMALIZED_ERRORS=278_MATCH_REPORTED
WINDOWS_CANDIDATE_ONLY_FAILURES=0_REPORTED
WINDOWS_NEW_PASS_DELTA=214_REQUIRE_NODE_ID_MAPPING
WINDOWS_OFFICIAL_V7=NOT_RUN_ON_R3_NOT_PASSED
WINDOWS_V7_RERUN=NOT_MANDATORY_IF_STRICT_PARITY_ATTESTED
LINUX_FULL_R3=8224_PASS_3_FAIL_1_SKIP
LINUX_BASELINE_ATTRIBUTION=REPORTED_THREE_REQUIRE_FINAL_ATTESTATION
FOCUSED_WINDOWS=271_PASS_REPORTED
FOCUSED_LINUX=271_PASS_REPORTED
LINUX_T05=33_PASS_REPORTED
LINUX_CROSS_MODULE=276_PASS_REPORTED
DIRECT_TLS=14_PASS_REPORTED
RECEIVER_TLS=10_PASS_REPORTED
G0_G1_G2_G3=FINAL_QA_ATTESTATION_PENDING
TASK_DIFF_ACCEPTANCE=HOLD_PENDING_EVIDENCE_REPORT
OWNER_EXCEPTION_APPROVAL=PENDING
CODER_COMMIT_PUSH_PR=HOLD
OWNER_MERGE=HOLD
PRODUCTION_CHANGE=NO
SENSOR_ACTIVATION=HOLD
SOURCE_ADMISSION=HOLD
```

**Chief Architect directive to TechLeadJR:** Do not modify R3 code to address inherited Windows/Linux issues. Freeze exact R3 TREE, assemble G0–G3 evidence report with V7↔direct parity and all 250 failure mappings, obtain explicit Owner exception signoff, then issue **a separate publication GO**. The conditional architectural decision itself is **not** publication or merge permission.
