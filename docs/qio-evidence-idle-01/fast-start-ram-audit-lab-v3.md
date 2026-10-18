# Evidence fast startup and independent RAM audit — LAB v3

Implementation intent: Issue #226 TASK v2.1, Architect FINAL v2.0 with Owner's
RAM-only experiment override, and Tech Lead D1/F04 existing-store-only ruling.
Base: `810484e69baa371c4696c3b46654199631538fc4`.

This document does not authorize publication, merge, installation, a service
start, a VM/RAM change, original-DB audit or any production operation.

## Ordinary startup: operational readiness, not history integrity

`DeviceFingerprintRepository.initialize()` requires an existing regular v2
database, existing safe parent chain and no symlink. It uses SQLite `mode=rw`,
never create-capable `rwc`, then metadata-only startup validation. Missing,
vanished and unsafe targets are StorageUnavailable. Empty/version-zero,
partial/wrong schema, invalid generation/singleton/allocator are StorageCorrupt.
Version 1 retains MigrationRequired. An unpublished connection is closed on
failure; runtime must not mark READY or ACK an ingest after failed initialize.

There is intentionally **no ordinary first-install provisioning** in this LAB
variant. It needs a future separately authorized operator contract. A missing
file, writer-lock or user_version=0 is not installation authority. Test setup
explicitly provisions disposable v2 schemas and singleton state.

The fast gate checks user_version, exact schema columns/indexes/CHECK fragments,
one canonical v4 database generation and bounded integer allocator, cap and
existing WAL/NORMAL configuration. It performs no historical table inspection,
full sequence scan/JOIN, COUNT/MIN/MAX, quick_check or integrity_check. Legacy
deep validation remains callable for explicit recovery; it is not removed.

This is an intentional reduction in pre-READY corruption detection. N08/N11
latent index/table defects may pass metadata readiness. Live observed SQLite
errors retain fail-closed handling. Operationally ready is NOT
FULL_HISTORY_INTEGRITY_PASSED. WAL recovery, I/O and lock latency remain real;
there is no unconditional startup latency SLA.

Path lstat identity before/after opening detects ordinary disappearance and
replacement races, but SQLite's pathname API is not an anti-rollback authority.
Protected deployment ancestry remains mandatory. A privileged replacement with
a different valid-looking v2 DB, rollback to an old valid generation, or a
replacement race completed entirely between pathname checks cannot be fully
excluded without an external trusted expected generation/handle-based binding.
No such marker or authority is invented here.

## Explicit manual auditor

Only this command is admitted, after independent acceptance and operator GO:

```text
python3 -m app.device_fingerprint.audit_cli run --store-id fingerprint_evidence
```

It is not imported/composed into `cli.py`, `service.py`, `run.py` or the API.
There is no daemon, automatic startup work, UI endpoint, scheduler activation,
arbitrary path/SQL flag, second writer, database migration or disk snapshot.

The trusted source comes from existing `get_settings()` and Fingerprint config,
including when the service is disabled/stopped. The source must pass existing
file/symlink checks, protected ancestry, owner/write-permission and hardlink
checks. Sidecars are checked before read-only opening. Metadata v2 validation
before backup rejects an accidentally configured different store without
copying it. Source opens via URI `mode=ro`, query_only=ON, with existing 500 ms
busy boundary. No source BEGIN, write, checkpoint, PRAGMA durability change or
source data repair is performed.

Readonly SQLite can natively create/maintain `-wal`/`-shm` locking sidecars.
That is not a new authoritative DB or application transaction. This auditor
does not manually create/delete/clean source sidecars. Fixture evidence checks
main and WAL bytes and records sidecar lengths; concurrency changes by the
legitimate writer are not falsely attributed to the auditor.

### M0–M8 algorithm

1. Claim audit-only nonblocking cross-process lock. It is distinct from and
   does not acquire Evidence's writer lock. A second run returns already_running.
2. Read protected status; reconcile orphan running to incomplete only after
   obtaining the singleton. Retain recovery identity in the new attempt.
3. Validate registered source and open read-only. Read metadata/page geometry.
4. Qualify memory before constructing a destination. Unknown facts defer.
5. Open a fresh `:memory:` SQLite connection, set source page_size before copy,
   verify it, then call source Connection.backup(destination, pages=256,
   sleep=0.05). These are versioned internal constants, not CLI parameters.
6. Callback bounds work by cancellation, two-hour monotonic ceiling and live
   resource checks. Record bounded progress counters, including resets; do not
   log or publish per page. A partial callback or BUSY/LOCKED cannot PASS.
7. After completed Backup API, make destination query_only and temp_store=MEMORY.
   Verify page geometry/schema/state again. Read generation and watermark from
   the destination only, not a later live connection. Full integrity_check must
   complete with exactly one `ok`. Check FKs if declared (baseline v2 has none).
   Stream full Evidence/Health rows for sequence range, canonical identities,
   timestamps, payload/content digest and immutable consistency; check global
   cross-family sequence collisions. Retention gaps are legal. Existing current
   producer policy is not retroactively applied to historic accepted rows.
8. Close both connections and clear progress handlers. Publish final bounded
   operator status only; destroy the RAM image, never copy it back.

Snapshot time means backup-completion observation, not an exact MVCC instant at
backup start. Concurrent source commits can restart/prolong copy. A completed
SQLite backup is consistent; unconverged/interrupted work is never PASSED.
Audit success attests only the copied generation/watermark, not subsequent live
writes. The RAM image is not a durable recovery backup.

## Resource admission and containment

Fixed LAB R1 profile, checked 64-bit integer arithmetic:

```text
image = max(page_count * page_size, main_file_bytes)
reserve = max(2 GiB, ceil(0.15 * MemTotal))
required = ceil(2.25 * image) + reserve
headroom = min(MemAvailable, each finite cgroup ancestor max-current,
               finite RLIMIT_AS - current VmSize when applicable)
admit only if headroom >= required and a finite containment limit exists
```

Windows focused tests inject explicit resource facts; native Windows is not a
qualified real-runtime resource probe. Real probes are Linux `/proc` plus
hierarchical cgroup v2 and existing RLIMIT_AS, never a global/package/VM edit.
Unsupported/missing/ambiguous facts, unknown containment, active swap/direct-reclaim counter
increase or insufficient headroom yield incomplete/resource_deferred before
destination allocation. Two observations are made before copy; observations
continue no less often than callback/VM-progress opportunities, throttled to
250 ms during ordinary work. Growth in backup page total forces re-admission.
The same conservative required headroom is retained during validation, without
lowering the 2.25 factor after allocation. RSS high-water and bounded memory/I/O
PSI observations are retained. I/O PSI alone is not an HDD performance claim.

This is conservative admission, not a guarantee against all OS allocations.
Python cannot interrupt every kernel/VFS/driver stall. A finite operator-owned
cgroup MemoryMax or RLIMIT_AS sandbox and external supervised timeout are real
deployment prerequisites, not inferred from a large MemAvailable alone. Coder
does not install limits. Tech Lead/SysAdmin must qualify reclaim/swap behavior,
containment and RAM capacity on the actual expanded VM before a full-size run.
No deliberate OOM/swap storm is a fixture requirement. Process kill may leave
a running marker, not a false success; the next owner reconciles it.

The RAM backup still reads the entire ~3.54-GiB original at least once. It may
read more under concurrent writes. `:memory:` does not prove zero OS swapping
or physical HDD savings. Real full-size resource acceptance remains separate.

## Operator status and failure policy

Code-fixed private location:
`/opt/CaptivePortal/data/audit-status/fingerprint_evidence.json`.
Audit lock: same directory, `fingerprint_evidence.audit.lock`. Operator prepares
the protected directory separately (recommended owner-only 0700); the auditor
does not create deployment directories or infer bootstrap from them. Run as
the admitted source/status owner (or explicitly authorized root), never sudo
from an HTTP request. Windows ACL/fsync semantics are not production-qualified.

Status file is 0600 and <=32768 bytes. Publication uses a unique O_EXCL/no-follow
same-directory temporary file, flush/fsync, replace and POSIX directory fsync.
Only that run's own temporary file can be cleaned up. Unsafe ownership/path,
Native Windows sharing/access refusal during os.replace gets at most eight
attempts with seven 10 ms sleeps; permanent refusal is report failure. This
does not retry SQLite operations or change database durability.
malformed/duplicate/nonfinite/oversize status or report failure is nonzero;
there is no silent success. Windows directory-fsync guarantee is explicitly
false in records. Deployment permissions and the fixed binding need operator
verification before invoking the CLI.

`db_audit_status.v1` holds `last_attempt` separately from
`last_verified_success`. Only full completed success updates the latter.
Failure/cancellation does not erase or refresh an earlier successful snapshot.
No credible status means never_run. There is no automatic time-based stale
promotion because no schedule freshness policy is activated. Queued/schedule
are future controls; this CLI only executes manual attempts synchronously.

Each attempt contains run/store/lock PID, stages, source commit, audit method,
UTC timestamps, monotonic duration, private source path/device/inode, copied
generation/allocator, geometry, bounded progress/resource summaries, check
summary, clock confidence and category. No packet payload, MAC/IP/DNS/SNI,
producer tokens, raw SQLite result or exception is reported. CLI stdout has
only store ID, status and closed category. Report is operator-private, not an
Admin API projection. Audit failed/integrity_suspect is manual alert evidence,
not authority to stop/restart/repair the live service automatically.

| Exit | Meaning |
| --- | --- |
| 0 | Completed RAM snapshot T3 passed and status publication succeeded |
| 2 | Already running (or argparse rejects unsupported command/arguments) |
| 3 | Resource deferral / prevented allocation |
| 4 | Confirmed integrity failure, canceled/deadline/busy/partial/other incomplete audit |
| 5 | Unsafe/unavailable status/config/artifact identity or status publication failure |

`resource_deferred` is a category with status=incomplete, not an extra success
enum or evidence of corruption. I/O/unavailable errors do not masquerade as
integrity failures. Actual CORRUPT/NOTADB or completed failed checks do.

## Deployment and rollback — future separately authorized steps

1. Tech Lead independently reviews exact patch/tree and wider Linux/Windows,
   crash, permissions, resource and security gates. Coder runs only focused tests.
2. After explicit publication GO only: normal approved commit to a dedicated
   LAB feature branch, no force push/PR/main merge. Verify remote exact tree.
3. Owner/SysAdmin approves window, cold-stops VM and expands RAM separately.
   Verify actual guest/cgroup/host resources and code/config rollback plan.
4. Integrate exact approved commit into isolated old-LAB release. Deployed
   source last observed cd83c3... differs from pinned source 810484...; no
   blind overwrite of /opt/CaptivePortal or another task's changes.
5. After separate LAB deploy/start GO, start Evidence normally and observe
   READY plus approved narrow ingest/replay through existing monitoring/PRTG.
   Do not repeat the 56-minute historical baseline or A/B/A, and do not invoke
   RAM audit as part of this first startup trial.
6. Full-size manual RAM audit is a later separate Owner-approved test after
   containment/resource admission, not implied by successful READY.
7. On faults stop/isolate under approved supervision and roll back code/config
   only. Never restore an old DB over acknowledged new events; preserve WAL,
   generation/allocator and original data. No automatic repair/delete/checkpoint.

## Future timer blueprint — NOT INSTALLED

Future oneshot runs only the admitted manual CLI, one audit lock, no restart.
Desired calendar is daily **03:00 Asia/Baku**, `Persistent=false`, no catch-up
storm. Tech Lead/SysAdmin must validate the supported calendar timezone spelling
with systemd-analyze calendar on actual LAB systemd/timezone before installing.
Do not guess a portable Timezone= directive or use 03:00 UTC. This task changes
no unit, timer, environment, VM, Grafana, UI or production file. Future UI audit
control and scheduler-owner handoff require a separate security contract.

## Evidence classification

F01–F30 map to the new focused module and individually named affected repository
tests. Real disposable corruption/SQLite/process termination are distinct from
synthetic error/resource/signal injections. Small fixture timing is
SMALL_FIXTURE_NON_CAUSAL, not hardware power-loss proof or HDD performance.
The existing-store-only change intentionally invalidates implicit-create test
setups elsewhere; they are not silently mass-edited. Tech Lead owns wider
regression reconciliation and any additional fixture-scope authorization.

PRODUCTION=UNTOUCHED; ORIGINAL_DB=NOT_ACCESSED; SCHEDULER=NOT_INSTALLED;
FULL_GATES=TECH_LEAD_ONLY; PHYSICAL_HDD_SAVINGS=NOT_MEASURED.
