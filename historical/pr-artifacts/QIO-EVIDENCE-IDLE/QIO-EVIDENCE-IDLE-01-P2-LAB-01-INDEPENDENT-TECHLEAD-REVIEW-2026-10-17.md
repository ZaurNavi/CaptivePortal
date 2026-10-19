# CAPTIVPORTAL — QIO-EVIDENCE-IDLE-01 / P2-LAB-01
## Independent Tech Lead research review and Chief Architect decision return

**Date:** 2026-10-17 (Asia/Baku)  
**Role:** Performance & Optimization Tech Lead  
**Disposition:** RESEARCH EVIDENCE ACCEPTED WITH LIMITATIONS; VALIDATOR REPLACEMENT NOT ADMITTED; N08/N11 ARCHITECT DECISION REQUIRED  
**Authority:** Chief Architect P1 Decision / P2 LAB Coder Boundary v1.2. Research only; no production changes.

## 1. Exact artifact and independent verification

| Item | Independently established result |
|---|---|
| Base commit | `810484e69baa371c4696c3b46654199631538fc4` |
| Base tree | `6816e73148c91c1e2e778613067a41d8c973c03d` |
| Candidate tree | `2021c7df0859e3d94d39de52a68489e367fad809` — **independently reproduced** using alternate temporary Git index on isolated WSL research worktree |
| Patch size | `48090` bytes — independently verified |
| Patch SHA256 | `1f0f7edf12ec92d5710d540cc117db58401c5b6a0343994d1ad61a81b1c1782e` — independently verified |
| Changed paths | Exactly four **added** research/test files; no existing production files edited, no deletions |
| Restored new-file hashes | Independently match all four `candidate-identity.json` expected SHA-256 values |
| Evidence ZIP | 350 declared SHA-256/length entries all verified; 351st entry is the inventory itself; ZIP `replacement.patch` byte-identical to separately uploaded patch |
| Linux Tech Lead rerun | **53 PASS / 0 FAIL / 0 SKIP**, exit 0, ~5.35 s, on Ubuntu-22.04 WSL using a distinct external `--basetemp` |
| Native Windows Tech Lead rerun | **53 PASS / 0 FAIL / 0 SKIP**, exit 0, ~17.36 s, native Windows Python using a distinct external `--basetemp` |
| Existing full Windows/Linux/security/PERF regression gates | **NOT RUN / NOT CLAIMED** — no production source change and no publication GO sought |
| Commit/push/PR/merge/deploy | **NONE** |

`research/qio_evidence_idle_01/{__init__.py,README.md,exact_validator_prototype.py}` and `tests/device_fingerprint/test_qio_evidence_exact_validator.py` are the only candidate additions.

The adapter is visibly research-only: bounded disposable file budget, explicit read-only SQLite URI, `query_only`, one read transaction, pinned source-blob checks, no runtime import/hook/READY admission. It performs baseline, forced covering-index, forced table scan, and intentionally incomplete MIN/MAX negative control. This **does not** establish broad trust equivalence or a physical performance gain.

## 2. Original L0 full quick_check — FINAL OBSERVATION, replaces PENDING

The original remote execution output was retrieved directly through the still-accessible Desktop Commander process output of **remote process 22904** (guest auditor PID **500349**), not inferred from process disappearance.

| Field | Recorded result |
|---|---|
| LAB source | `810484e69baa371c4696c3b46654199631538fc4` |
| Original Evidence DB | `/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3`, 3,796,074,496 bytes |
| Audit start | 2026-10-17T15:54:14+04:00 |
| Evidence sequence guard | PASS, 148.402 seconds, process `read_bytes=41,791,488` |
| Source Health guard | PASS, 0.106 seconds |
| Cross-family collision guard | PASS, 1.252 seconds |
| Full quick_check start | 2026-10-17T15:56:44+04:00 |
| Full quick_check end | **2026-10-17T16:52:36+04:00** |
| Full quick_check wall | **3352.86 seconds (55 min 52.86 s)** |
| Literal result | `result_count=1`, `all_ok=true`, `first_response="ok"`, stage `PASS` |
| quick_check process `read_bytes` delta | **3,961,155,584 bytes** (not equivalent to exclusive HDD physical sector count) |
| quick_check process `write_bytes` delta | `0` |
| Finished audit marker | `L0_ALL_STAGES_COMPLETE`, `ALL_STAGES_PASS` |
| Remote process exit | **0**, complete execution ~3506.22 seconds |

**Correction of stale handoffs:** L0 `FULL_PRAGMA_QUICK_CHECK` is now **PASS** for the audited SQLite snapshot; no longer `PENDING`. This proves completion of the defined historical check, **not** detection of arbitrary corruption, absence of hidden UNIQUE/index-table anomalies, operational fast-readiness, or trustworthy output for other snapshots.

No second L0 scan was launched. At subsequent remote inspection, `fingerprint-evidence.service` remained `inactive`, guest PID 500349 had exited, and the existing `/opt/CaptivePortal` checkout had moved to `cd83c3e04233593126d247b0c96c1135f4233072`; therefore the pinned historical source and current checkout must not be conflated. No service restart or configuration/database changes were performed.

## 3. Independent counterexample review: N08 and N11

### N08 — inconsistent UNIQUE index declaration/data

Fixture method: in an isolated disposable v2 DB, intentionally create duplicate sequence values under a non-unique index, then alter the disposable SQLite catalog declaration to `CREATE UNIQUE INDEX` using `writable_schema`; reopen. Thus schema reports UNIQUE but index content violates it.

Independent, *read-only* examination of the shipped Linux fixture using SQLite **3.46.1** observed:

- `PRAGMA quick_check` → `[('ok',)]`;
- `PRAGMA integrity_check` → `non-unique entry in index uq_df_evidence_ingest_sequence`;
- real table `NOT INDEXED` group-by on `ingest_sequence` → duplicate `(1, 2)`;
- original sequence guard reads do not flag the duplicate; the legacy signature accepts the purported UNIQUE index.

**N08 confirmed as a failure of the stronger all-corrupt-states fail-closed requirement in the tested corrupt scenario.** It is artificial corruption, not evidence the real 3.8-GB DB contains duplicates. Merely stating that the catalog declares UNIQUE is insufficient proof of historical contents.

### N11 — missing index entry conceals malformed table row

Fixture method: on a disposable copy only, insert a REAL `ingest_sequence` via controlled constraint bypass, then replace an index leaf with a syntactically valid empty leaf. The table still contains the invalid row; its covering index does not.

The research runs on Python SQLite **3.37.2** (WSL) and **3.40.1** (Windows) record legacy baseline PASS, forced covering PASS, forced table-scan REJECT, and `integrity_check` diagnostic failure. The independent Tech Lead WSL/Windows focused reruns reproduce the tests (53/53 PASS on both platforms).

**SQLite-version caveat:** independent read-only examination of the shipped N11 fixture with SQLite **3.46.1** returns `wrong # of entries in index ...` from `PRAGMA quick_check`, whereas the historical 3.37.2/3.40.1 test results showed `quick_check=ok`. This is version-sensitive evidence; one must not claim that all SQLite releases necessarily miss this exact case. The underlying index/table mismatch is real, and the covering-index scan can hide the invalid table row.

**N11 demonstrates that a stricter forced table scan is not a historically outcome-equivalent replacement for the legacy guard**, even where it would detect more damage. That difference is an architecture decision, not authority for Coder to replace the query. No inference about actual historical Evidence DB corruption is warranted.

## 4. Final research/performance verdict

```ini
SOURCE_SCOPE_REVIEW=PASS_RESEARCH_ONLY
ARTIFACT_IDENTITY=PASS
ZIP_INVENTORY=PASS
INDEPENDENT_LINUX_FOCUSED=53_PASS_0_FAIL_0_SKIP
INDEPENDENT_WINDOWS_FOCUSED=53_PASS_0_FAIL_0_SKIP
ORIGINAL_L0_FULL_QUICK_CHECK=PASS_2026-10-17T16:52:36+04:00
COVERING_CANDIDATE=UNKNOWN_NO_EQUIVALENCE_PROOF
TABLE_SCAN_CANDIDATE=REJECTED_NON_EQUIVALENT_OUTCOME
MINMAX_CANDIDATE=REJECTED_FALSE_ACCEPTANCE
GUARD_EQUIVALENCE=NOT_PROVEN
DEEP_T1_REPLACEMENT=NOT_ADMITTED
HOST_PHYSICAL_HDD_SAVINGS=NOT_MEASURED
OPERATIONAL_FAST_READY=HOLD
N08_N11=ARCHITECT_DECISION_REQUIRED
FULL_REGRESSIONS=NOT_RUN
CODER_RUNTIME_GO=NO
COMMIT_PUSH_PR_MERGE_DEPLOY=NO
PRODUCTION_ACTION=NO
```

The original full `quick_check` consumed about **55.9 minutes**; even perfect removal of the 148-second Evidence sequence guard could not by itself make full historical startup fast. Original L0 used sequential phases in a different order than production `initialize()` (production runs `quick_check` before schema/sequence guards). Do not equate one-statement timings or warm/cold phases with total trusted startup or physical IOPS savings. Host HDD workload contains other VM/host activity; no matched HDD A/B/A saving has been established for any candidate.

**Source-level outcome:** Accept the narrow bounded research as documented evidence, **not** a production-candidate algorithm. Block any subsequent runtime validator shortcut or readiness change. There is no reason to publish/merge this research-only diff before the Chief Architect decides how to capture the newly established semantic discrepancy, if publication is desired at all.

## 5. Formal Chief Architect decision request

**ARCHITECT RETURN / P1 INTEGRITY SEMANTICS ADJUDICATION — requested, not self-approved.**

**A1 — scope of promised trust:** Does the accepted T1 requirement mean *exact historical checks* (which may miss N08/N11 corrupt states), or *fail-closed against arbitrary on-disk UNIQUE/index-table corruption* (which the legacy checks demonstrably do not fully establish)? Please state the chosen explicit guarantee; do not leave both as simultaneously fulfilled.

**A2 — required correction:** If stronger detection is mandatory, specify the authorized architectural direction for integrity checking (e.g. explore full `integrity_check` or independently trusted historical attestation) and its precise error/READY consequences. This review is **not** authorizing a switch to `integrity_check`: its true cost and corruption/locking behavior on the 3.8-GB HDD database are unmeasured here.

**A3 — order and risk:** Assign P0/P1/P2 to this specification/runtime discrepancy, and state whether any separate mitigation/admission is required for an operational existing single-store Evidence service. No live corruption is evidenced; no accidental service restart or emergency deployment is warranted solely from these artificial fixtures.

**A4 — subsequent roadmap:** Confirm whether P2-LAB-01 closes as a negative result and the next work is (a) safety/integrity contract research or (b) independent small trusted ingress vs historical generation architecture. The latter requires a separate new contract and must not be smuggled into this experiment.

**Until Architect/Owner disposition:** `CODER=HOLD`, no source publication or runtime changes; `captiv-prod` and Network Metadata remain strictly out of scope. Tech Lead holds independent full regression/security/physical HDD gates for any later authorized production-facing candidate.
