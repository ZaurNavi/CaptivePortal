# CAPTIVPORTAL — QIO-02 / P1 R2
## Chief Architect → Tech Lead: Public Traffic `reader_state.updated_at` Semantic Disposition v1.2

**Date:** 2026-10-16 (Asia/Baku)  
**Owner of decision:** Chief Architect — CaptivPortal Performance / Small-I/O  
**Request:** Tech Lead QIO-02 P1 R2 semantic consumer & writer audit (summary presented by Tech Lead)  
**Normative parents:** `CAPTIVPORTAL-QIO-02-SQLITE-SMALL-IO-ARCHITECTURE-ADMISSION-CONTRACT-v1-2026-10-16.md`; `CAPTIVPORTAL-QIO-02-CHIEF-ARCHITECT-RESPONSE-TO-TECHLEAD-P0-P1-v1.1-2026-10-16.md`  
**Source review:** `ZaurNavi/CaptivePortal` at `e2cbd96916d8a81f07f0d79a1a745f593ccb5114` (selected repository functions; live loaded SHA not newly verified).  
**Evidence limitations:** Full named P1 R2 report was not accessible in this handoff; this disposition uses the Tech Lead's submitted findings and independent source review. It does not independently verify the 5/6 runtime sample or the 91.27% host busy.  
**Class:** Architecture clarification only; no Coder TASK, no production change, no Lab implementation GO.

---

## 1. Executive disposition — explicit answer

**QUESTION:** Is `public_traffic.sqlite3:reader_state.updated_at` an obligatory **durable proof of a successfully completed full source scan**, even when no direct application consumer of the field is found?

**DECISION: NO — not under the currently evidenced Public Traffic domain contract.**

- The field is an **operational row-update timestamp** (a record of when this row was last written), not an independently sufficient `successful_full_scan_at` with declared completeness, scan scope, result, and freshness SLA.
- Its presence and renewal do **not**, by themselves, make repeated no-change EOF an authority-bearing event requiring a new durable commit.
- This does **not** declare the field freely discardable: it remains persisted schema data; external consumers, forensic conventions and backwards compatibility are not yet fully audited. The existing producer continues to write it until a separately admitted implementation proves compatibility.
- A source-level EOF is not the same as successful completion of the **entire** rotated-source scan. Partial/incomplete source paths may still write `updated_at` elsewhere. Accordingly, this field cannot be elevated retroactively into a reliable global successful-scan proof.
- For Registry, Current State, Visits and Observations, the independently specified freshness/attempt/authority requirements in v1 are **unchanged**. The decision is scoped **only to Public Traffic reader_state.updated_at**.

**H1 disposition:** `H1=CONDITIONAL_CONTINUE_P1` (not REJECT, not PASS_TO_LAB). Continue semantic and physical attribution. No P2/implementation authority is granted.

## 2. Evidence-to-semantics reasoning

Code paths reviewed on the stated source revision:

1. `app/public_traffic/reader.py:scan()` discovers multiple source files and returns a composite `complete` status; it has no persisted global `successful_full_scan_at` in `reader_state`.
2. `_process_source()` calls `repository.observe_source()` when handling an **incomplete trailing line** (then returns false), and separately at the **final EOF** (then returns true). Thus a refreshed `updated_at` by itself cannot distinguish a complete scan from a partial-line visit.
3. `app/public_traffic/repository.py:observe_source()` currently does `BEGIN IMMEDIATE → _upsert_reader_state() → COMMIT`.
4. `_upsert_reader_state()` unconditionally updates `updated_at` on conflict, including when `source_identity`, path, offset, checkpoint, observed_size and retirement status have not changed.
5. `get_reader_states()` projects source identity/path/offset/checkpoint/observed_size/retired/missing, **not** `updated_at`. This is positive evidence for current first-party reader semantics, **not** proof that external readers do not exist.
6. The official counter presentation uses `traffic_daily.updated_at`, which is **not** `reader_state.updated_at`. Likewise `visit_reader_state.updated_at` is another domain and must not be conflated.

**Tech Lead R2 findings accepted as reported, pending artifact review:** 5/6 tracked rows changed only `updated_at` within 32 seconds; no direct Python consumer found; external consumer graph incomplete; risk of TOCTOU from stale in-memory reader state; synchronized guest/QEMU/HDD sampling under ~91.27% busy does not establish quiet causality or the physical cost of this one method.

## 3. Reconciliation with v1 N1–N7

- **N1 (effective tuple):** The semantic comparison must cover `source_identity`, `source_path`, `source_offset`, `source_checkpoint`, `last_observed_size`, `retired_completed`, `missing_warning_emitted` plus source identity/generation, rotation/reappearance/truncation state and owner/consumer contracts. `updated_at` is not excluded from the **consumer audit** merely because this architect classifies it as operational.
- **N2 (new source fact):** A confirmed *same-inode, same-checkpoint, no-new-line* EOF with no changed durable processing/recovery state is **not automatically** a new authority fact. This clarification is limited to Public Traffic; it does not change the mandatory per-cycle proofs in Current State/Observations.
- **N3 (freshness):** The generic v1 phrase about `last_*_at` timestamps still protects every timestamp carrying an **established** freshness/health/absence promise. The unqualified `reader_state.updated_at` is not currently established as such a promise. If consumer inventory finds it is required, H1 must be rejected or a new compatibility/freshness contract approved; no silent reinterpretation.
- **N4:** Crash/restart/replay must not lose processed events, cursor progress, checkpoint verification or transitions.
- **N5 / TOCTOU:** **A check against `get_reader_states()` preloaded before scan is insufficient for a skip.** Any future skip/no-update decision belongs inside the same serialized persistence boundary as the current authoritative writer, using a single atomic conditional predicate or an equivalent owner-locked and verified CAS. Avoid introducing a second writer/authority. File-system changes during a scan require separate identity/offset/checkpoint safeguards; DB atomicity alone does not freeze the source file.
- **N6:** Preserve audit, diagnostics, source missing/reappearance/truncation, idempotency and real failure semantics. No misleading indicator such as `last_scan_success_at` may be inferred from `reader_state.updated_at`.
- **N7-pre/N7-post:** Before Lab approval demonstrate a plausible isolated cost and consumer safety. Only after Lab implementation may Tech Lead claim actual matched host physical I/O improvement. When host busy is ~91%, a brief synchronous window is **not** the required quiet proof.

## 4. Exactly what may be investigated under H1

**H1 scope (research only):** The **final** `observe_source()` issued by `PublicTrafficReader._process_source()` after verified, genuine unchanged EOF **for the same source identity/generation**, with equal persisted recovery tuple and no new processing, quality-state or freshness obligation.

**Do not apply H1 to:**

- a newly discovered source, newly appended line (including zero-byte-traffic or duplicate event), changed checkpoint/hash, offset, observed size, path or inode;
- incomplete tail/partial line, unsuccessful file open, rotated/replaced/truncated source, source missing/reappearing, reset, `missing_warning_emitted` transition, source retirement or change from retired back to active;
- `process_offline_event()`, `advance_source()`, `reset_source_*()`, `mark_missing_warning_emitted()`, `delete_reader_state()`, initial backfill, aggregate/processed-event commits and existing idempotency/replay boundaries;
- unverified consumer semantics or a stale preloaded object.

**Prohibited algorithm:** `if old_state == new_state: return` based solely on `scan()`'s earlier `get_reader_states()` result. The correctness boundary is the **final actual persistence decision**, with conflict-safe validation of the full tuple, not earlier assumption. A specific SQL algorithm is intentionally **not approved at P1**.

**No global parameter changes:** no `synchronous`/journal-mode/checkpoint/`fsync` changes, global batching, guessed freshness interval, new durable heartbeat, vacuum, deletion or migration of source facts.

## 5. Tech Lead's remaining P1 deliverables

1. **Complete relevant consumer graph**: static first-party reader, API/UI, health/readiness/alert, cleanup/retention, analytics, Grafana/Loki/Alloy, operational queries, external SQLite readers and forensic procedures. Explicitly state which external consumers were checked and which cannot be excluded.
2. **Attribute the exact observed changes**: distinguish final same-source EOF updates from event processing, partial-line handling, source reset, retention and writer concurrency. The 5/6 row sample by itself is insufficient; explain the sixth and source generation/missing/retired status.
3. **Establish N7-pre**: a matched and repeatable baseline by actual guest/host device map; rank per-DB writers; estimate whether final EOF update has significant avoidable physical cost. Avoid pretending guest `wios` or SQL calls are physical `/dev/sda` writes 1:1. If high busy prevents per-operation isolation, document the blocker and propose controlled disposable Lab attribution, without claiming production causality.
4. **Submit a falsifiable Lab experiment design**: one narrow change, source and target trees, no source-schema change if possible, exact equality/atomicity boundary, rollback, representative workload, negative cases, and acceptance metrics. Return to Architect for **separate P2 LAB GO**.
5. **Consumer safety outcome**: If a true required freshness/last-scan consumer depends on periodic `updated_at`, report `H1 REJECT_CURRENT_DESIGN` and request a separate compatibility design. No silent throttling. If unavailable to rule out, report `H1_CONSUMER_HOLD`, not a fabricated PASS.

## 6. Required Lab correctness test cases (not authorization to execute)

- Repeated complete no-change EOF, same inode/generation, same source tuple: replay/reader-state equality as before except for explicitly admitted operational-only timestamp.
- New line, duplicate, zero-traffic event, changed size without complete line, partial tail and completed tail; checkpoint/offset never advance prematurely.
- Inode rotation, replacement/truncation/rewrite, old backup retirement, source disappears/reappears, missing warning transition, same offset with altered checkpoint.
- One source succeeds while another source in the scan is incomplete/fails; no fabricated global full scan, no incorrectly skipped source state.
- Concurrent thread/writer or late append between preloaded read and final decision: no lost state and no skipped required transition; stable DB owner/lock/CAS semantics.
- Kill/crash just before conditional decision, during transaction, just after commit, after event durable effect but before source checkpoint: retry/replay and idempotency remain identical.
- External consumer regression for any observed reader_state access and all critical freshness/health/forensic tools; no false healthy/readiness.
- Performance: multiple workload-matched control/variant windows under representative small-I/O HDD; host `/dev/sda` completed writes/sec and await/busy plus guest cgroup, wall latencies, correctness. No win => reject hypothesis as an optimization.

## 7. Scope and owner responsibilities

- **Chief Architect:** P1 field semantics disposition, conditional H1 boundaries, separate explicit P2 Lab admission after evidence. No production actions.
- **Tech Lead:** completes P1 read-only consumer/per-DB physical attribution and proposal; owns full independent Windows/Linux, failure/replay/security and performance acceptance after future Coder candidate.
- **Coder:** HOLD until P2 Architect Lab GO + Tech Lead narrow implementation TASK. Focused tests only after that GO.
- **Owner:** separate decisions on publication/merge and any production deployment/mutation.
- **QIO-01D, PR #215, cold-start read latency:** distinct tracks, unmodified by this disposition.

## 8. Machine-readable status

```ini
TASK=QIO-02
STAGE=P1_R2_ARCHITECTURE_DISPOSITION
QUESTION=PUBLIC_TRAFFIC_READER_STATE_UPDATED_AT_MANDATORY_SUCCESSFUL_FULL_SCAN_PROOF
DECISION=NO_NOT_CURRENTLY_AUTHORITATIVE_PROOF
FIELD_CLASSIFICATION=OPERATIONAL_ROW_UPDATE_TIMESTAMP
H1=CONDITIONAL_CONTINUE_P1
H1_CONSUMER_GRAPH=INCOMPLETE
H1_TOCTOU=GUARD_REQUIRED
H1_N7_PRE=UNPROVEN
ARCHITECTURE_P0=PASS_WITH_CLARIFICATION
P1=EVIDENCE_REQUIRED
P2_LAB_ADMISSION=HOLD
CODER=HOLD
PRODUCTION_CHANGES=NO
OWNER_GO=NO
DURABILITY_WEAKENING=FORBIDDEN
```

**Bottom line:** The source-code evidence does not make `reader_state.updated_at` a mandatory durable **full-scan** proof. That narrow decision keeps H1 eligible for investigation, but does **not** prove that its removal is compatible with all consumers or saves host HDD IOPS. Return P1 evidence before requesting P2.
