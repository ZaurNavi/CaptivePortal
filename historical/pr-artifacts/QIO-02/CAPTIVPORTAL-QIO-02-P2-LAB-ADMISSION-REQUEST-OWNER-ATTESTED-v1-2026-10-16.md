# CAPTIVPORTAL — QIO-02 / H1
## Tech Lead → Chief Architect: P2 Disposable Lab Admission Request v1 (Owner-attested)

**Date:** 2026-10-16, Asia/Baku  
**Issuer:** Optimization Tech Lead  
**Normative:** Chief Architect QIO-02 architecture v1, P0/P1 clarification v1.1, H1 field disposition v1.2, laptop Lab direction v1.3  
**Request:** `P2_LAB_GO / HOLD / REJECT` for **one narrow variant**, with no production mutation.  
**Current state:** `P1_L0=EVIDENCE_COLLECTED`; `P2=AWAITING_CHIEF_ARCHITECT_DISPOSITION`; `CODER=HOLD`; `PRODUCTION=NO_CHANGES`.

## 1. Owner's consumer attestation, 2026-10-16

Owner explicitly confirmed in this conversation:

> «Да-да, я точно помню, что ничего не прописывали. Мы хотели создать, если я не ошибаюсь, там еще дополнительные панели, что ли, что-то с трафиком. Но это так и осталось, мы это не сделали. Поэтому можешь это смело рубить. В крайнем случае, если где-то что-то пропадет, мы посмотрим и починим.»

**Faithful operational interpretation:** Owner confirms he did **not** configure an obligatory external monitoring rule consuming every refresh of exactly `public_traffic.sqlite3:reader_state.updated_at`; contemplated extra traffic panels were not implemented. Owner accepts **bounded residual unknown-consumer risk** and corrective action should a previously unknown dependent consumer later be discovered. Owner approval is **not an inventory of all historical external scripts**, not independent SysAdmin attestation if a separate operator exists, and **not a production deployment authorization**.

Independent bounded first-party evidence:

- At pinned source revision, `app/public_traffic/repository.py:get_reader_states()` returns the seven recovery/state fields and **does not select** `reader_state.updated_at`.
- `app/portal_counter/routes.py` → `PublicTrafficService.get_snapshot()` uses **`traffic_daily.updated_at`**, not the operational reader-state timestamp.
- Scoped tracked Git search found no literal `reader_state.updated_at`; SQLite queries to similarly named `reader_state` in Visitor Registry belong to a **different database/domain**.
- Supplied Grafana dashboard `CaptivePortal_Grafana_AP24_Evidence_Health_v60(1).json` has **168 panels**, with zero occurrences of `reader_state`, `public_traffic`, or `traffic_daily`; a text search in this one snapshot does not attest other dashboards or other operator queries.
- Prior P1/R3 read-only operational scan: selected systemd/cron/scripts/observability locations returned no known required field consumer. Coverage is limited and was documented previously.

**Consumer result:** `OWNER_ATTESTATION=RECEIVED`; `KNOWN_MANDATORY_READER_STATE_UPDATED_AT_CONSUMER=NONE_FOUND_WITHIN_CHECKED_SCOPE`; `UNKNOWN_EXTERNAL_READERS=RESIDUAL_RISK_ACCEPTED_BY_OWNER_FOR_DISPOSABLE_LAB`; `SEPARATE_SYSADMIN_ATTESTATION=NOT_ESTABLISHED` (obtain if separate responsible operator exists before deployment).

If Chief Architect considers this insufficient for **Lab-only** P2, specify a finite verification step. Do not silently call the graph mathematically complete.

## 2. P1-L0 experimental proof; physical-evidence limits

Exact unmodified source and synthetic fixtures on Owner laptop (WSL2 Ubuntu 22.04.5 on Windows 10, SSD SK hynix 512 GB):

- Frozen source `191beda1f23f8f466d2431f42e57571815d85778`, tree `3f6d0a05c5d893d3139db44a1692c81e67fd6c6e`.
- Five completed retired log files (`.log.1`–`.log.5`) plus one unchanged active file yield, **per repeated complete scan**, six `BEGIN IMMEDIATE`, six `INSERT INTO reader_state ... ON CONFLICT DO UPDATE`, six `COMMIT`; six rows change **only** `updated_at` while the seven-field recovery tuple stays identical. Repeated five times: **30 redundant UPSERT transactions**.
- Under Linux `strace -yy` in an unchanged six-source scan: WAL `pwrite64`: **18 writes/24,912 bytes**; SQLite DB main-file `pwrite64`: **6 writes/24,576 bytes**; WAL successful sync: **12**; main-file sync: **6**. Repeated five scans: WAL writes 90, main-file writes 30, total recorded sync calls 90. This represents **lab file syscalls** associated with the full original scan; not proven savings from a variant and not the physical production HDD IOPS.
- No source data/DB from production copied. No live server/QEMU/hypervisor profiling since Owner STOP direction.
- Synthetic baseline exercises new event incl traffic=0 and duplicate, partial + completed line, same-size checkpoint-changing rewrite, rotation/retirement, retired and active missing/reappearance, and pre/post COMMIT process-crash replay. Baseline PASS at the asserted level; **not** variant correctness.

Full predecessor evidence: `CAPTIVPORTAL-QIO-02-P1-L0-LAPTOP-CAUSAL-BASELINE-AND-P2-ADMISSION-REQUEST-2026-10-16.md` and P1 R3 report.

**Revision check:** As of this request, GitHub main `516abc7f56cb9c60a0e450af109334f4949b3da9` merged PR **#215** (SSR-01B), parent `191beda...`, changed five device-fingerprint deployment/test/doc files and **no Public Traffic path**. For reproducible P2 comparative work, keep `191beda...` as the candidate base; separately assess rebase to current main before publication. Do not silently mix PR #215 with H1.

## 3. Proposed precise H1 variant — request for architectural GO, not code

**Scope narrowed further for lowest risk:** only the *already-retired and unchanged* file's final genuine EOF (`retired_completed=1 → 1`). Keep active-source final EOF as-is in initial P2 variant. The archive's `0 → 1` or `1 → 0` retirement transitions are **mandatory durable updates**.

Suggested flow to freeze in P2 contract:

1. `PublicTrafficReader._process_source()` retains existing discover/open/fstat/source identity, checkpoint validation, line processing, incomplete-tail and offset/size guards. Only after **successful complete final EOF** for a **retired** source may it request an *optional* conditional unchanged write-skip from the repository. Early in-memory `scan() → get_reader_states()` is **not** sufficient to skip.
2. Add an opt-in-only discriminator to **`PublicTrafficRepository.observe_source()`** (default preserves exact legacy behavior). `reset_source_after_truncate()` and incomplete-tail callers get the default legacy path. Do **not** modify process-event, advance, reset, backfill, missing warning, deletion or aggregates.
3. Enter the existing `BEGIN IMMEDIATE` serialized writer boundary, inspect the **actual current persisted** row, and allow no-op only when its **complete** tuple equals the request: `source_identity`, `source_path`, `source_offset`, **full** `source_checkpoint`, `last_observed_size`, `retired_completed=1`, `missing_warning_emitted=0` — and source's final-complete-EOF/identity/inode/generation evidence is valid. The operational `updated_at` alone may differ. Missing row, unverified hash, mismatch, late concurrent DB mutation or unknown condition: execute **legacy UPSERT**. No independent writer or stale snapshot guard.
4. On the admitted true no-op, skip row UPDATE while safely ending transaction; avoid adding any `last_scan` heartbeat. Compare no-op writer-lock cost in L1 rather than assuming SQL transactions/sync disappear automatically. Preserve source integrity/replay under concurrent FS changes: DB lock does not lock an OS source file; if uncertain, retain durable behavior. Do not reinterpret time of last full scan.
5. Preserve all PRAGMAs, transaction boundaries for authoritative effects, data schemas, WAL mode, `synchronous`, fsync and API semantics. No global polling/batching changes or new dependencies.

**Architecture-specific issue to resolve explicitly at GO:** proof that the path still points to the expected source generation at the no-op point, and fall-through semantics if append/replace occurs around the final fstat/checkpoint/DB lock. Do not claim an impossible filesystem/SQLite cross-resource atomicity; prove replay and next-scan reconciliation. The no-op is purely optional and must fail closed to existing durable UPSERT.

## 4. Proposed P2 Coder file allowlist and stop conditions

**Allowed once Architect issues explicit P2 GO AND Tech Lead issues Coder TASK:**

- `app/public_traffic/reader.py`
- `app/public_traffic/repository.py`
- `tests/test_public_traffic.py`

Any doc update only as a separately listed allowed path when final task is issued; no broader file changes. **Prohibited:** env/config values, services/systemd, deployments, unrelated writer domains, migrations, SQLite PRAGMA change, QIO-01D, SSR-01B / PR #215, any live production operation.

**STOP, revert to HOLD:** newly found mandatory consumer; inability to serialize current-row comparison; undefined source generation/inode/replay; new failure on late append, duplicate/zero event, partial tail, rotation/reappearance, truncate, missing flag, archive transitions, concurrent writer/reset, crash before/within/after transaction; user-facing freshness impact; performance no-win or regression.

Coder may execute **focused** unit/integration tests only, with exact test IDs, patch SHA256, tree, test logs, diff and zero authorization for commit/push/PR/merge/deploy. Tech Lead independently owns full clean Windows/Linux regression, security, crash/replay and matched performance acceptance.

## 5. Required L1 evidence and falsification

- Matched control/variant A/B on same local WSL2/SSD, repeated interleaved ABBA or BAAB cycles; separate cold/warm SQLite connection/file-system cache states and idle/burst/eventful conditions. **Do not** treat `strace`-inflated wall time as an uninstrumented latency benchmark.
- Compare exact per-scan `BEGIN/COMMIT/UPSERT`, WAL/main `pwrite64` byte count and `fdatasync/fsync`, SQLite checkpoint on close, error/collision incidence, wall latency, recovery tuple and front-end/API aggregates. Trace both cases using identical instrumentation; monitor host physical writes only where attribution is defensible.
- On unchanged six-source fixture with **five retired + one active**, the target for an effective variant is **five fewer retired UPSERT updates per complete scan**, with active legacy update unchanged. This is a **predicted logical result**, not a measured physical saving. Compare actual syscall impact to baseline and do not assume full elimination of WAL/fsync caused by connection setup/teardown.
- Negative controls: active append, duplicate event, zero-traffic session, malformed/completed partial tail, source inode re-use, changed hash at same size, 0→1 / 1→0 retirement, missing warning and return, new file, late append, concurrent reset/write/delete, crash pre/post conditional check and event-before-checkpoint replay, multiple-source partial/global incomplete.
- If no independently attributable WAL/sync/local device benefit, **reject H1 as a physical I/O optimization** even if timestamps stop changing.
- `LAB_HDD_FIDELITY=LIMITED`: Owner laptop uses SSD, not an isolated spinning HDD. Production `/dev/sda` savings/busy/await **remain UNPROVEN**. Per Architect v1.3 the original three quiet production windows are no longer a precondition for *Lab-only* P2 review.

## 6. Single requested Chief Architect disposition

Please issue an unambiguous ruling:

> **`QIO-02 H1 / P2 DISPOSABLE LAPTOP LAB: GO / MODIFY / HOLD / REJECT`** for the *already-retired same-tuple final EOF only*, on pinned `191beda...`, with writer-boundary atomic guard and narrow Coder allowlist above. A GO authorizes **isolated laptop code and tests only after separate Tech Lead TASK**. It does not authorize GitHub PR/merge, production changes, or claiming production HDD improvement.

If `MODIFY/HOLD`, specify only necessary finite blockers (e.g. independent SysAdmin confirmation or explicit inode/fstat guard). No Owner question remains concerning whether the Owner deliberately created a freshness consumer; he explicitly confirmed he did not.

```ini
TASK=QIO-02
REQUEST=P2_DISPOSABLE_LAPTOP_LAB_ADMISSION
OWNER_EXPLICIT_NO_CONFIGURED_MANDATORY_CONSUMER=YES
OWNER_LAB_RESIDUAL_UNKNOWN_CONSUMER_RISK_ACCEPTED=YES
OTHER_EXTERNAL_CONSUMER_COMPLETENESS=BOUNDED_NOT_ABSOLUTE
SYSADMIN_INDEPENDENT_ATTESTATION=NOT_ESTABLISHED_IF_SEPARATE_OWNER
BASE_SHA=191beda1f23f8f466d2431f42e57571815d85778
BASE_TREE=3f6d0a05c5d893d3139db44a1692c81e67fd6c6e
CURRENT_MAIN_OBSERVED=516abc7f56cb9c60a0e450af109334f4949b3da9
P1_L0_BASELINE=COMPLETE
H1_PROPOSED_SCOPE=STABLE_RETIRED_FINAL_EOF_ONLY
H1_ATOMIC_WRITER_GUARD=MANDATORY
H1_SQL_SYSCALL_COST=CAUSALLY_OBSERVED_ON_LAPTOP
H1_VARIANT_SAVINGS=NOT_YET_MEASURED
H1_PROD_HDD_EFFECT=UNPROVEN
P2_CHIEF_ARCHITECT_GO=NOT_YET_ISSUED
CODER=HOLD
OWNER_MERGE_GO=NO
OWNER_PRODUCTION_GO=NO
```
