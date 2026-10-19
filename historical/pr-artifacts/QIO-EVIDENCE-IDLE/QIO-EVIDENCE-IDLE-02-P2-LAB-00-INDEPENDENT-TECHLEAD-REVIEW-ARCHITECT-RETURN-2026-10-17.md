# CAPTIVPORTAL — QIO-EVIDENCE-IDLE-02 / P2-LAB-00
## Independent Tech Lead Research Acceptance & Chief Architect Decision Return

**Date:** 2026-10-17 (Asia/Baku)  
**Scope:** Fingerprint Evidence only, disposable HOT/ARCHIVE research prototype; source pinned to old LAB baseline. New `captiv-prod`, original 3.8-GB Evidence DB, Network Metadata, live services and runtime settings are out of scope.  
**Architecture basis:** Chief Architect HOT/ARCHIVE decision v1.3; Tech Lead Coder TASK v1.0.  
**Verdict:** `RESEARCH_ARTIFACT=ACCEPTED_WITH_LIMITATIONS; HOT_ARCHIVE_SAFETY=UNKNOWN; ARCHITECT_DECISION_REQUIRED; RUNTIME_CODER=HOLD; FAST_READY=HOLD; PUBLICATION=NO; PRODUCTION=UNCHANGED`.

## 1. Exact artifact identity and independent reconstruction

| Field | Result |
|---|---|
| BASE HEAD | `810484e69baa371c4696c3b46654199631538fc4` |
| BASE tree | `6816e73148c91c1e2e778613067a41d8c973c03d` |
| Candidate tree (independently reconstructed using temporary Git index) | `1d34e5bb1982ed3b99c382ca728b886799f0c10e` — MATCH |
| Patch SHA256 (independent byte hash) | `c3e92eb8e5f20fde77bbe3d6f6e88107bcfdea07f40b4447b3565310e5faf0c5` — MATCH |
| Patch length | `90702` bytes — MATCH |
| ZIP SHA256 (independent byte hash) | `cf8fbc56bae2209e799286ee9736027fa2a621147f26f84db9a316333f740a0c` |
| ZIP payload / inventory | 2407 archive members; all 2406 entries of `SHA256-inventory.json` match member length and SHA256 |
| Patch in ZIP vs separately supplied patch | Exact byte match |
| New file SHA256 identities | All five match `candidate-identity.json` after reconstructing files from patch |
| Diff | Exactly five **added** allowlisted files, 1563 insertions; no existing file replaced; isolated staged `git diff --check` PASS |

Allowlist-only:

1. `research/qio_evidence_idle_02/__init__.py`
2. `research/qio_evidence_idle_02/hot_archive_trust_proof.py`
3. `research/qio_evidence_idle_02/CONTRACT.md`
4. `research/qio_evidence_idle_02/README.md`
5. `tests/device_fingerprint/test_qio_evidence_hot_archive_research.py`

No git commit, push, PR, merge or deployment was authorized or performed by Tech Lead. On the authorized operator workstation, the research worktree was observed at exact base HEAD with only the two expected untracked research/test path groups. A distinct temporary Git index was used solely to calculate the candidate tree; the original staging index was not modified.

## 2. Tech Lead independent focused verification

| Gate | Independent result | Environment |
|---|---|---|
| Focused Linux | **54 PASS / 0 FAIL / 0 SKIP**, exit code `0`, `18.51 s` pytest report | WSL Ubuntu-22.04, sqlite3 `3.37.2`; research worktree; separate Tech Lead `--basetemp` and JUnit path |
| Focused Windows | **54 PASS / 0 FAIL / 0 SKIP**, exit code `0`, `68.79 s` pytest report | Native Windows interpreter, same exact research worktree, separate Tech Lead `--basetemp` and JUnit path |
| Local reconstructed patch content | Five new-file SHA256 matches | Independent container verification |
| Static / repository diff | Exact source tree match, allowlist and staged whitespace check PASS | Isolated temporary Git index |
| Full-project Linux/Windows/security/physical host tests | **NOT RUN / NOT CLAIMED** | Reserved for separately admitted runtime-facing candidate per TASK §5 |

The 54 finite focused cases test the declared *process-crash/cooperative-writer model*. They do not certify full cutover recovery, host power-loss durability, external trust anchor or deployment. Linux and Windows counts were reproduced by Tech Lead, not copied from Coder's JUnit reports. Coder's compilation and static checks are also reported; independent focused pytest runs import and execute the candidate source.

## 3. Acceptance of bounded findings, not runtime safety

**Accepted positive evidence:**

- H02–H04: two synthetic generations, one global sequence order, idempotent duplicates across archives/HOT and rollback on immutable conflict work on finite tested fixtures.
- H05–H08: missing or untrusted history, overlapping sequence, absent receipt and stale cooperative epoch produce HOLD rather than false ACK under model assumptions.
- H09–H12, H15: child-process abrupt exits and interrupted SQLite Backup API give the documented outcomes under preserved OS storage; no proof of hardware power-loss safety.
- H16/H17 (old N08/N11): disposable index corruption is rejected by **full `PRAGMA integrity_check` plus domain T3 checks**. SQLite `3.37.2` (Linux) and `3.40.1` (Windows) are observed; VM engine/version-specific repetition remains separate. These cases do **not** assert that the real LAB Evidence DB is corrupt.
- H24/H26/H27: finite cross-generation pagination, late event-time ordering, Source Health unknown/stale distinction and a pinned pre-cutover reader behave consistently in the model; production integration and multi-process reader lifetime are unproven.

**Explicit caveat:** The original 3.8-GB LAB database passed the completed legacy L0 `quick_check` (`3352.86 s`, `3,961,155,584` process-read bytes) and sequence scan (`148.402 s`), but has **not** passed target T3 and was not touched in this research. These are historic L0 observations, not matched physical host HDD savings or end-to-end startup time.

## 4. Significant blocking gaps and independent code-review observations

### B1 — No independently protected, anti-rollback authority

`ProtectedAuthority` is a separate ordinary LAB SQLite database, not a proven non-rollbackable trust root. A cooperating writer epoch and fencing token are useful, but takeover uses an assumed `certified_dead` input; no independent certification/fencing hardware, ACL policy, protected write-ahead receipt channel or replay-proof monotonic counter has been established. Co-rollback of authority + HOT + archive and privileged replacement remain outside the tested model. Changing a local manifest together with archived bytes cannot be trusted. **Runtime GO prohibited.**

### B2 — Cross-store ACK durability versus `WAL/NORMAL`

The model deliberately commits sequence reservations to authority before HOT writes, then commits HOT rows + HOT allocator, then authority receipts, then logical ACK. It does **not** use atomic multi-DB commit. The process-exit model is consistent, but the requirement “after a *durable* ACK no accepted event is lost” has not been validated under power loss, filesystem/cache controller behavior or partial WAL/checkpoint/fsync. Both stores use existing `synchronous=NORMAL`; altering production durability pragmas was not authorized. RPO under host power loss remains UNKNOWN.

### B3 — RECOVER is safe-stop, not recoverable cutover

`ProofStore.recover()` on a non-`NEW_ACTIVE` phase sets state to `RECOVER` and returns `HOLD`. It does not prove deterministic idempotent forward recovery or rollback after interrupted PREPARE/VERIFY/CREATE_HOT/ACTIVATE, nor any bounded recovery time. There is a risk that collapsing the phase to the generic `RECOVER` state will require richer retained step provenance to choose the correct transition. A safe HOLD is preferable to data loss, but it is not accepted operational availability. **RTO UNKNOWN**.

### B4 — Current model actively reads history during ingest and gate

`ProofStore.ingest()` calls `_verify_universe()`, which verifies archived identities, opens ALL retained generations and traverses ALL rows, validates the HOT store and compares receipt/reservation metadata. `_publication()` rehashes archived file bytes, and `gate()` repeats global universe verification. Therefore this model is **not** a fast-active-only startup/ingest design: it currently retains significant historical read cost by construction. This is an intentional research defense absent real immutable external attestation, not a permitted future runtime implementation. No physical HDD savings or reasonable hot-ingest latency can be inferred.

### B5 — Archive unavailable versus truly independent HOT readiness

In H05 the model correctly withholds **new ingest ACK** whenever the archive is offline, unverified or quarantined, because idempotency across generations cannot be proved. That is safe fail-closed behavior, but demonstrates a design tradeoff: **small HOT does not automatically imply independent new-ingest availability** unless a separate independently durable global dedup/identity registry is established or the Owner explicitly chooses a fail-closed availability policy. Architect must specify which property is normative before a runtime design.

### B6 — Retention and snapshot consumers incomplete

`retention_plan()` reports `deleted=0` and `physical_expiry=UNKNOWN/HOLD`: the demonstration has no archival segment expiry, rebuild/reseal, garbage collection or cross-process pinned-reader protection. Legacy Evidence retention by `observed_at` and Source Health +600 s must remain true as *physical* policy, including late observed_at events, gaps and predecessor anchors. `ReadView` is intentionally not API-compatible with existing one-file `DeviceFingerprintReadService`/`snapshot_service`/Source Health policy and cannot be used as a drop-in. Catalog/global-generation identity, typed unavailable history and all semantic artifacts require separate consumer migration and tests.

### B7 — No causally valid HDD improvement or operational threshold

No matched host `/dev/sda`, QEMU cgroup and guest `/dev/vda` A/B/A; no isolated hot-only startup, one-time T3 sealing expense, physical write amplification, P95 HTTP latency, rollover frequency or cutoff benchmark. The prototype's 16 MiB, 4096 rows and 32 event budget are fixture caps, **not** operational constants. Do not advertise faster READY, lower HDD IOPS or no change in durability.

## 5. Chief Architect / Owner decision request (addressed questions)

**A1. Security authority and attacker/rollback model.** Select concrete independently enforceable epoch/fencing owner, non-rollbackable reservation/receipt authority, archive immutability and attestation publication mechanism. Specify who can write and restore each object, reboot/power-failure and privileged-co-rollback assumptions. A second writable LAB directory is insufficient.

**A2. Authoritative ACK durability policy.** Define exact required guarantee for logical/HTTP ACK under process failure vs host power loss with WAL/NORMAL; identify acceptable RPO (prefer no acknowledged loss), fsync/file/directory policy per platform and publication ordering. If durability policy changes, require explicit separate architecture and Owner risk approval; never silently change SQLite pragmas.

**A3. Exact crash cutover algorithm.** Issue a machine-checkable per-step publication/recovery algorithm with authoritative pending record, old-writer fencing, global reservation high-water, WAL/backup provenance, idempotent forward/rollback through each crash point and safe handling of ACKs after cutover. State what must persist and how ambiguous states are resolved. Define acceptable recovery time; repeated perpetual HOLD is not an operational recovery plan.

**A4. Hot availability versus archive outage.** Decide whether archive failure blocks all ingest (safe but dependent) or a separately durable global dedup registry permits new ingest without reading historical archive. Prove duplicate/conflict semantics, Source Health and sequence authority for whichever route is chosen; never interpret unavailable history as empty.

**A5. Trust, sealing and scrub lifecycle.** Define final T3 (`full integrity_check` + exact domain checks) for cutover, independent attestation authority, immutable filesystem/storage controls, TOCTOU/rehash strategy, quarantine/reseal/scrub policy and latency. Specify whether at-rest archival corruption after seal changes new-ingest availability or only history availability.

**A6. Physical retention and multi-generation snapshot API.** Define segment segmentation/resizing/expiry without over-retention, reader leases/refcounts, late observed_at insertion, Source Health predecessor margin and typed unavailable behavior. Define stable catalog/combined-generation snapshot identity and compatibility migration for `read_service`, `snapshot_service`, Source Health policy, classification/Fusion and external consumers.

**A7. Next validation stage and HDD performance.** Decide whether to authorize a **design-closure-only** R2 / P2-LAB-01 scope for state machine and trusted-anchor research *before* any runtime code, and specify controlled LAB HDD performance plan: separate one-time original-size T3-on-safe-clone cost from repeated tiny HOT gate, account for actual added control-plane writes, matched physical HDD reads/await/busy and health/HTTP P95; no original DB corruption or production effects.

**Requested Architect disposition:** maintain `RUNTIME_IMPLEMENTATION=HOLD`, accept LAB-00 as evidence with explicit UNKNOWN, approve precise design closure contract or return MODIFY on unresolved A1–A7. A simple “Coder GO” for production implementation would contradict v1.3 gates.

## 6. Machine-readable handoff

```ini
TASK=QIO-EVIDENCE-IDLE-02-P2-LAB-00-HOT-ARCHIVE-TRUST-PROOF
REVIEW_DATE=2026-10-17
BASE_HEAD=810484e69baa371c4696c3b46654199631538fc4
BASE_TREE=6816e73148c91c1e2e778613067a41d8c973c03d
CANDIDATE_TREE=1d34e5bb1982ed3b99c382ca728b886799f0c10e
PATCH_BYTES=90702
PATCH_SHA256=c3e92eb8e5f20fde77bbe3d6f6e88107bcfdea07f40b4447b3565310e5faf0c5
ZIP_HASH_INVENTORY=2406_OF_2406_PASS
ALLOWLIST=5_NEW_FILES_ONLY
RECONSTRUCTED_TREE=PASS
INDEPENDENT_FOCUSED_LINUX=54_PASS_0_FAIL_0_SKIP_EXIT_0
INDEPENDENT_FOCUSED_WINDOWS=54_PASS_0_FAIL_0_SKIP_EXIT_0
RESEARCH_DELIVERABLE=ACCEPTED_WITH_LIMITATIONS
PROTOTYPE_BEHAVIOR=CONSISTENT_IN_TESTED_COOPERATIVE_PROCESS_CRASH_MODEL
N08_N11_T3_DISPOSABLE_FIXTURES=REJECTED_BY_FULL_INTEGRITY_CHECK
HOT_ARCHIVE_DURABILITY=UNKNOWN
EXTERNAL_PROTECTED_AUTHORITY=UNPROVEN
RECOVERY_AUTOMATION=NOT_IMPLEMENTED
PHYSICAL_RETENTION=NOT_IMPLEMENTED
FULL_WINDOWS_LINUX_SECURITY_GATES=NOT_RUN_RESEARCH_ONLY
PHYSICAL_HDD_SAVING=NOT_MEASURED
PRODUCTION_FACING_FAST_READY=HOLD
RUNTIME_CODER=HOLD
ARCHITECT_REVIEW=REQUIRED
ORIGINAL_EVIDENCE_DB_MUTATION=NO
CAPTIV_PROD=DO_NOT_TOUCH
COMMIT_PUSH_PR_MERGE_DEPLOY=NO
```

**Owner-readable conclusion:** five-file candidate and all 54 focused tests on both operating systems reproduce exactly. Research can close; runtime fast-ready cannot. The main technical barrier is not missing Python functionality, but a defensible independent trust/anti-rollback authority, crash-durable ACK and cutover, cross-generation dedup/readers, and compliant history retention. One candidate's immediate scanning of historical data also prevents any demonstrated HDD win. Return A1–A7 to Chief Architect before issuing any production-facing task.
