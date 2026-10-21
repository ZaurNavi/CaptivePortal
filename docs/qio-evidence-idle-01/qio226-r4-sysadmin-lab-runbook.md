# QIO226 / 04D R4 — pinned T3 directory capability and first-HOLD attribution

## 04E owner-helper diagnostic amendment — source review, not a retry GO

Authority: Issue226 SysAdmin handoff6305336464 plus Owner Coder directive.
Exact source parent is accepted04D86976fa0b55a6f4faf490a66743d52da6397d1f9.
The reported R2 actual experiment ended with three deferred/worker_crashed,
snapshot=null and positive root release, NOT three T3 PASS. Earlier original
queues were separately archived by SysAdmin; Coder does not independently
inspect or reconcile those captured facts. No blind repeat, installation or
new queue is authorized by this source-only amendment.

04E adds a separate root-created anonymous nonblocking diagnostic FIFO, passed
only to the exact owner-helper through its sealed private job document. It is
not a source/host/root-directory FD or public endpoint. No uid/pid credential
acceptance is widened on the existing authenticated R4 socket. The write end
is close-on-exec inside helper; no parent writer or worker writer survives.

Closed marker stages cover sealed document/profile, before/after parent and
namespace verification, artifact/import provenance, chroot, UID/GID drop and
receipt checks, owner_ready, BEGIN, RO source open/metadata, destination,
backup start/first progress/completion, close and owner_done/cleanup. Only the
first progress writes a marker, never one per page/batch. The entire fixed
trace plus one typed first-failure record fits4096 bytes; writes never wait,
retry or log raw exception text. A broken diagnostic sink cannot repair or
change the helper result. Missing/truncated/extra/unknown diagnostic content
is explicitly unavailable/invalid, not proof of any particular SQLite error.

Root reads/closes that FIFO only after positive existing pidfd/wait reap.
Exactly one `qio226_r4_owner_outcome` event/version1 per helper contains job and
attempt UUID/seq, observed child exit code, root-received ready/done booleans,
closed outcome and last stage, whitelisted exception class/closed code/numeric
errno and optional canceled/deadline stop_reason. No source paths, data, SQL,
keys, nonce, payload, traceback or subprocess stderr. Root resource HOLD also
may observe an already-exited helper through at most250ms reaper-event wait;
it never cleans/adopts an uncertain process. Existing root-only protected
journal/evidence routing remains required. No public/durable JSON schema change.

`outcome=complete` means ONLY helper exit0 + authenticated owner_done, never T3
PASS. Pre-ready nonzero exit is separate from ready backup abort. A signal has
its positively observed negative exit code and last received stage, without
invented exception. `unreported` means import/sealed-auth/diagnostic setup was
not observed, NOT a guessed root cause. Existing canceled CoordinatorError
normalizes to coordinator_unavailable; the separate closed stop_reason now
identifies observed cancellation without changing that legacy error contract.

Admission, RO bindings/source checks, Backup API, scopes, source UID/GIDs,
nonowner T3/two-FD proc bridge, memory/no-swap, reaps and release/FIFO remain.
The actual umask077→022 launcher correction is SysAdmin-owned, not a source
chmod, group widening or cgroup-policy patch in04E. On runtime errors preserve
the original deferred/non-success or orphan HOLD, never fabricate success.
Native injections at READY can still hit the unchanged live-membership HOLD
gate if the helper dies before the root checks it; diagnostic does not bypass it.

PUSH/PR/INSTALL/REAL_ORIGINALS_RETRY/PRODUCTION=HOLD pending independent review
and separate exact SysAdmin/Owner authority. No old-LAB action by Coder.

## 04D superseding disposition — code review only, real queue remains held

Authority: Issue226 comments6303245042 and6304411705. Parent is accepted04C
`7f4bc354492668834ee97e5825b935110167647b`, tree
`c6067823ea60262c2d680a4ba88e38cd3fcfb47e`. The historical04C procedure below
does not authorize a fresh installation or a repeat original-source batch.

Confirmed code bug: worker UID995/GID993 cannot traverse socket parent exactly
0750 root:GID992. Do not chmod that parent, grant supplementary GID992, loosen
source ownership or change the accepted private PIDNS/procfs arrangement.

Root promotes only after positive owner-helper reap. The private authenticated
snapshot packet carries exactly TWO ordered SCM_RIGHTS capabilities: image
O_RDONLY and final-directory O_RDONLY|O_DIRECTORY (never O_PATH). The root
derives final from the current job, seals dev/inode/GID receipt, and verifies
root0750:worker_gid tmpfs, same device as the finalized root0440:worker_gid
regular one-link image. All other private packet kinds carry zero FDs. Reject
wrong credentials, PID/binding, swapped/duplicate/extra/anonymous/writable FDs.

The worker independently checks both receipts and fixed `snapshot.sqlite3`
through stat(dir_fd=final_fd, follow_symlinks=False), around native SQLite open,
through guarded full integrity/FK/domain T3 and afterward. It rejects extra
entries/sidecars, symlink, stage/foreign final, changes to owner/mode/inode,
size/hash, private proc self mapping or CWD identity. SQLite is native RO,
immutable FINALIZED IMAGE only, query_only/FK ON and temp_store MEMORY.

The approved URI is derived solely from the received bounded decimal final FD:
`file:/proc/self/fd/<final_directory_fd>/snapshot.sqlite3?mode=ro&immutable=1`.
This is an intermediate DIRECTORY-FD magic link in the already-qualified
private PIDNS-bound procfs, NOT the image-FD URI and NOT an arbitrary alias.
No textual readlink-target trust, getcwd/resolve/fchdir, host procfs, new mount,
VFS, dependency, alternate DB or memory/disk copy is introduced. Missing or
mismatched proc self/FD identity fails closed with no alternate opening path.
SQLite closes before both received FDs on success, rejection or cancellation;
the worker never changes its CWD. An ordinary relative SQLite URI was proved
to expand to a denied absolute path and is expressly not a fallback.

Root emits one bounded closed JSON `qio226_r4_first_hold` event/version1 for the
first HOLD only, on its protected stderr/journal route. Required fields:
job_id, attempt_id, seq; closed phase/gate_id/subphase; whitelisted exception
CLASS, closed CoordinatorError code or numeric OS errno; child_role/exit_code
only with positive sole-reaper pidfd/wait evidence; source_gate_verified and
source_open_started booleans. Worker channel EOF before READY is observed by
the root's sole reaper with a finite event wait, not PID absence. An uncertain
reap remains null, never success. No raw exception, traceback, path, payload,
key, nonce, source data or child stderr is logged. SysAdmin must retain the
existing root-only protected journal/evidence route; no public logging API.
Diagnostic facts are NOT release proof, recovery permission or queue schema.

The first real A exception remains UNPROVEN. Original epoch
`a7ae3553-a7f9-4abd-9e98-9d03036a55aa`: A seq25
`6a280e6e-cb1d-45d3-b33c-97a037e37bd2`, attempt
`6772793c-a6ec-4aea-8fa7-64855b1cedbe` is running/orphan_hold; B seq26
`5891c5f3-7bbe-4469-a430-4a60e9d385af` and C seq27
`96fd3463-2269-4b7b-99bf-d4d6d9f66628` remain queued per the protected capture.
No positive A terminal/release exists. Installing04D cannot recover old A.
Do not restart/kill/reset, unmount uncertain resources, rewrite history, repeat
recover_once, change locks/epoch, or resubmit old/new keys. Independent
evidence-backed one-shot reconciliation requires separate Owner/TechLead GO.

UID994 operator inside daemon private PID+mount namespace behind root-owned
attended launcher is the accepted old-LAB arrangement. No PID0, namespace/auth
relaxation, extra endpoint or capabilities are authorized. Existing native5.15
F2/F3/K01/K02/K03 stay frozen PASS, not repeated generic qualification.

04D disposable laptop tests prove only this code contract and canonical
synthetic A/B/C; they are NOT original old-LAB DB PASS. Coder local commit is
allowed only after required tests. PUSH/PR/INSTALL/REAL_RETRY/PRODUCTION=HOLD.

## Historical 04C mixed-source-GID handoff and attended LAB runbook

Status: 04C CODE REVIEW / ORIGINAL SOURCE HOLD. Authority: Issue226 comment6301692092;
04B architecture remains as in comment6296204519.
This is a proposed, separate SysAdmin-owned procedure, NOT Coder permission to
install, access192.168.0.202, open original DBs/queue, start services or run jobs.
No production, main, timers, Admin,17-store audit or3.8GB Fingerprint re-audit.

## 04C disposition — accepted native gates are frozen, not reopened

SysAdmin receipts6301412656/6301508196 accept actual Linux5.15 F3 private
PIDNS/procfs, K01(3/3), K02, K03, and qualified F2/root+UID995 canonical T3.
Protected Python `/opt/captivportal-audit/runtime-r4-20261020/py310/bin/python3.10`
SHA256 `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae`,
Python3.10.12/SQLite3.37.2/Flask3.1.3, is accepted for that immutable release.
Do NOT repeat these generic campaigns, install dependencies, revisit procfs
architecture, rerun recovery or start a new HDD/baseline research loop for04C.
The historical sections below describe preserved contracts, not new repeat gates.

04C changes one incorrect profile invariant: global source owner UID1003 is
shared, but main/WAL/SHM retain each store's exact original group:

| Store | Source UID | Pinned source GID |
|---|---:|---:|
| public_traffic |1003|1004|
| network_service_intelligence |1003|1004|
| traffic_projection |1003|996|

Never chmod/chgrp/reconstruct originals to fit policy. StorePolicy.gid is the
authoritative per-store group, not a derived/guessed value. Helper uses only
the authenticated job's selected policy: `drop_owner(policy.uid,policy.gid)`,
all real/effective/saved IDs exact, supplementary groups EMPTY. Stage ownership
already follows that same per-job UID/GID. The worker's own GID (native accepted
UID995/GID993) is unrelated to source GIDs1004/996; do not grant it broad groups.

The exact R4Installation object now has NINE closed keys (NO owner_gid):

```json
{
  "method": "sqlite_online_backup_private_tmpfs_physical_v1",
  "enabled": true,
  "owner_uid": 1003,
  "ram_root": "/run/captive-portal/db-audit/ram-jobs",
  "ram_device": 1,
  "ram_inode": 2,
  "task_limit": 16,
  "nr_inodes": 64
}
```

All nine keys are required. Device1/inode2
are documentation placeholders, NOT an installable approval: SysAdmin pins the
actual preprovisioned root0711 inode. An obsolete owner_gid or any extra/missing
key is rejected, never ignored. Existing installed pilot has r4=null and is
NOT rewritten/migrated by Coder. Historical queue/method/result schemas stay.

After independent04C review/publication, SysAdmin stages the exact immutable
new commit, retains accepted Python/private PIDNS topology, and pins fresh R4
profile with source groups above. Provision only the separately permitted fixed
RAM root and delegated leaf (previously absent), preserving original queue/locks.
Run remaining in-run preconditions and A/B/C; no repeat generic qualification.
If safe B failure injection is unavailable, report that formal subcase unproven
and continue ordinary successful three-store Backup+full T3; do not damage
originals or block that ordinary proof just to manufacture a controlled failure.

## 1. Immutable source and dependency qualification (F2)

1. TechLead independently reviews the exact04C diff/tree atop accepted04B and all retained failed
   diagnostics. Publication requires a separate GO to a LAB branch only. Record
   accepted04A bridge parent/tree and04B commit/tree; never substitute main or a
   TechLead synthetic worktree. Do not touch the original dirty04A worktree.
2. After a separate installation GO, SysAdmin prepares a STANDALONE root-owned
   Git release with exact HEAD/tree and all app `.py` SHA256 blobs. Its Git dir
   AND common object dir must be root-protected, not a user-owned linked worktree.
   Every import parent/root is root-owned and non-group/world-writable; no app
   pyc/cache/shadow package, PYTHONPATH, user site, `.pth` injection or fake Flask.
   `PilotProfile.artifact()` checks actual Git, blob inventory, file modes and
   canonical regular-file interpreter SHA. It cannot be bypassed operationally.
3. The unqualified `/usr/bin/python3.10` is known to miss Flask. DO NOT choose it
   just because NI-04 DDL imported once. SysAdmin must separately approve an
   immutable dependency-complete interpreter/profile. If a new environment is
   required, obtain installation approval first; use a root-protected copied
   interpreter (not a user-controlled symlink/venv dispatcher), pinned existing
   requirements and recorded package inventory. No Coder package installation.
4. For the intended exact Python, capture `sys.executable`, resolved path/SHA256,
   `sys.version`, SQLite version/compile options, `sys.path`, all import root
   owners/modes and `importlib.metadata` package versions. Repeat clean-process
   `-B -E -s` imports as ROOT and the intended nonowner UID995, with sanitized
   `PATH=/usr/bin:/bin`, `HOME=/nonexistent`, `LANG=C.UTF-8`. No site/import stubs.
5. In a protected disposable test root with complete dependencies, run canonical
   A/B/C T3 through `live_sqlite.validate_snapshot`, using the accepted fixture
   `test_clean_dependency_complete_worker_exact_domain_t3_and_negative_schema`
   and04B K06. Require positive schema+domain, negative wrong schema/domain/
   lineage/index/FK tests. Physical/integrity-only is not domain qualification.
6. Match exact release/tree/blobs/interpreter/profile in BOTH bootstraps. If any
   dependency/root cannot be qualified: `HOLD_QUALIFIED_WORKER_DEPENDENCY`.
   QA interpreter PASS is NOT installed interpreter admission.

## 2. One coherent launcher topology (F3)

Retain the accepted job-private PIDNS/private procfs launcher: one root
supervisor, one nonowner gatekeeper/validator and one backup-only owner helper
in that SAME coherent namespace. Once inside, root creates a fresh MOUNT
namespace only. Do not reuse outer procfs inside it or substitute host PIDs.
The supervisor PID/start ticks in sealed authority must match real child PPid;
`readlink('/proc/self') == str(getpid())` and NSpid contains exactly that one PID.
04A parent-death/wrong-start/NSpid/incorrect-proc tests must remain closed.

Proposed single invocation after all gates and separate GO: root uses the exact
qualified interpreter, exact release cwd, `-B -E -s -m
app.db_audit_coordinator.daemon_cli run`, no path/DB/env selector. PID namespace
composition and delegated control leaf are SysAdmin launcher responsibilities;
no systemd edits are part of this code handoff. Closed failure diagnostics only,
no raw tracebacks/source data/nonces. Wrong proc topology ⇒ HOLD, not fallback.

## 3. Preserved native Linux5.15 criteria — already PASS, no04C repeat

Preserve accepted native5.15 receipts; do NOT rerun these generic tests for04C.
They used ONLY disposable SQLite/WAL fixtures, never originals. Retain their
mountinfo/proc/cgroup and exact IDs/JUnit. Local Coder WSL6.18 tests are separate
regression evidence, not a replacement or reopening of the native5.15 verdict.

- Verify cgroup-v2 unified mount, trusted ancestors, finite local/ancestor caps,
  empty delegated interior, memory controller enabled, root control child and
  unique per-job leaf. Read back memory.max, pids.max, swap.max0/current0 and
  current PSI/events/reserves. External attended host reserve is separate; no
  host-budget token/collector is added. Missing/malformed evidence fails closed.
- All three processes AND tmpfs pages must share the exact same leaf. The root
  enters before allocation. Run K02/K03 with actual LAB UID1003/995, real RO
  remount/chroot, negative source writes, WAL-consistent Backup and bounded
  memory.stat:shmem allocation. Require no capabilities, no_new_privs and no
  escaping inherited FD/host proc/writable source alias. Do not chmod originals.
- On5.15 do NOT require `tmpfs noswap` or memory.peak. Prove cgroup swap.max0 and
  current0 throughout. Read back finite tmpfs size AND nr_inodes, nodev/nosuid/
  noexec. Unknown charge ⇒ `HOLD_R4_SWAP_CHARGE`; failed RO WAL opening ⇒
  `HOLD_R4_SOURCE_VIEW`. No disk/shared-dev-shm/serialize fallback.
- A profile enables R4 explicitly: method exact
  `sqlite_online_backup_private_tmpfs_physical_v1`, common owner UID1003 with
  per-store source GIDs1004/1004/996; worker UID995/its own GID993, RAM root fixed
  `/run/captive-portal/db-audit/ram-jobs`, its preprovisioned root0711 dev/ino,
  finite task_limit8..32 and nr_inodes32..256. Each per-store page-aligned
  image_max is justified with WAL/transient/helper/validator/margin/reserve, not
  copied from old3.8GB evidence sizing. No implicit grant in old profiles.
- Preserve original coordinator.lock/heavy.lock inodes and old JSON/epoch/history.
  Quarantine old direct launches/P0 paths and require independently confirmed
  no overlap. Old recover_once was ALREADY performed: NEVER execute it again.

## 4. Review the failure/release matrix before real source authority

K01 own-FD flock and denied competitor BEFORE source; K02 OS RO source/writes;
K03 shared charge/no swap/cap-pressure negatives; K04 partial/sidecar/symlink/
hardlink/source replacement; K05 positive helper reap and final FD/path/hash;
K06 canonical domain; K07 exact helper/worker/supervisor death, deadline/cancel/
OOM/leftovers; K08 controlled B failure versus orphan; K09 old history and
duplicate/saturation/ACK; K10 credentials/nonce/namespace/store/path/release.

Preserve all initial FAIL outputs. A fixture/path qualification failure is not a
passed native gate. Coder kernel tests use disposable object cleanup only; they
do not qualify the real installed release or complete wider security acceptance.
TechLead owns wider coordinator/cross-surface/security/crash review.

## 5. ONE attended source-backed A→B→C pilot — separate Owner GO only

After all independent gates, installed F2/F3, native5.15, host+guest reserves,
P0 launch-denial, stable protected historical queue/locks and observability PASS:
record all initial queue bytes/hash, exact lock inodes/epoch and fresh keys.
Submit exactly one three-store batch using existing operator protocol. Unknown
ACK: status-by-key with the SAME store+key+UID; do not resubmit/reset/recover.

A Public Traffic full domain PASS; B NI-04 deliberately controlled,
NONDESTRUCTIVE validator failure; C Traffic Projection full domain PASS only
after B positive release. A worker/source corruption injection is NOT authorized
on originals; a real pilot controlled-failure method must be independently
approved and bounded before this step. This implementation adds no general
fault-injection CLI/profile knob. Orphan/supervisor death is NOT controlled B:
HOLD, no C, preserve evidence. Under04C disposition an unavailable safe B
injection leaves that formal subcase unproven, NOT a blocker to ordinary
successful A/B/C proof; never damage a source to manufacture B.

Preserve the single bounded protected root `r4_release_proof` receipt per job and
its durable SHA256 commitment. Verify source pre/post inode/sidecars, snapshot
generation/watermark, root/owner/validator leaf, shmem/current/max/zero-swap,
positive reaps, strict unmount, two empty observations, terminal fsync and next
claim ordering.0440 is not a seal and source pre/post is not exact live MVCC.

## 6. Rollback / unknown outcome

No automatic restart/requeue, epoch rollover, JSON edit, lock recreation, lazy
unmount or PID-absence receipt. STOP further submissions using existing scoped
operator STOP, then wait for positive cleanup if available. On uncertainty keep
durable running/orphan HOLD and require independent reconciliation. Do not mark
old success/failure or claim C. Preserve original state/keys/lock identity and
protected logs. Revert only the separately installed LAB code/profile under
Owner/SysAdmin change control after exact resource ownership is resolved; no
rollback source SQLite writes or schema migration is needed or permitted.

MERGE=NO; PRODUCTION=NO; REAL_LAB_SOURCE_PILOT=HOLD; OLD_RECOVERY=DO_NOT_REPEAT.

## 04F — bounded backup callback correction and closed differentiator

Authority: [04E real A/B/C diagnostic handoff](https://github.com/ZaurNavi/CaptivePortal/issues/226#issuecomment-6313032207).
Source parent: accepted04E `6443e00d87f4465f11a43f7be862dcbee09350dc`.
No new original-source experiment, queue recovery or installation is granted by
this source change. TechLead reviews exact LAB-only source first; SysAdmin needs
the next explicit GO for one new attended queue. Preserve every previous archive
and the original lock inodes. The04E three `deferred/worker_crashed` results are
still **zero real T3 PASS**. The subsequent service stop timeout is not success.

The accepted04E callback rejected all codes except0/101 and required a positive
page total on every callback. A disposable CPython3.10.12 / SQLite3.37.2 probe
reproduces native `(SQLITE_BUSY=5, remaining=0, total=0)` before the first copy
when the disposable destination is locked; after releasing that lock the same
native backup reaches `(SQLITE_DONE=101, 0, 2)`. Old04E rejects the first callback.
This confirms a specific callback-contract defect, **not** the numeric cause of
the real04E failures (their old diagnostic did not capture it).

References: [SQLite backup status/locking](https://www.sqlite.org/c3ref/backup_finish.html),
[CPython3.10.12 original callback/retry loop](https://github.com/python/cpython/blob/v3.10.12/Modules/_sqlite/connection.c#L1640-L1675).
BUSY/LOCKED are transient; CPython itself retries those steps.04F does not add
another backup/retry loop. It accepts only native0/101/5/6 with exact integer
arguments (not bool); 0/0 is allowed only for5/6. Each callback still counts
toward the original100000 ceiling, rechecks the existing deadline/cancel/source
guard, and enforces the existing image budget whenever total is known. For5/6,
a maximum5ms select on the existing control channel is clamped to the remaining
attempt budget; the original guard runs again after wake. No spin, background
retry, timeout extension or larger image allowance. Other SQLite statuses,
bad counters/types, oversized totals and missing DONE fail closed. Completion
requires native101 + remaining0 + positive bounded total, normal backup return
and the original post-backup guard. `pages=128`, `sleep=0`, RO source, chroot,
credentials, mounts, memory limits, SQLite durability and IPC are unchanged.

Protected root `qio226_r4_owner_outcome` may now include one closed `backup`
object: `check`, numeric `status`, `remaining`, `total`, `steps`, `page_size`,
`complete` and bounded `ok/done/busy/locked/other` counters. These are the latest
callback plus bounded aggregate counts, **not a per-call log stream**. Null means
no callback value or a value rejected as out of the closed diagnostic range.
`check` distinguishes backup invocation, guard, step/type/status/count/page-budget
checks, transient wait, required completion and post-backup guard. Failure emits
the current differentiator once; successful backup emits one summary before the
existing completion markers. The nonblocking FIFO stays4096 bytes; a single row
is capped at768 bytes, with at most one summary plus the existing failure row.
Root strictly validates the enum, exact fields/types/ranges/counter sum and
ordering; malformed/overflowed diagnostics are invalid, never echoed or adopted
as proof. No source paths, SQL, error messages, payload, identifiers or nonce are
added. Existing first-HOLD, positive reap, queue results and release proof remain
unchanged. `backup.complete=true` is a SQLite callback fact only, **not T3**;
cancel/post-guard failure can still prevent owner_done and all promotion.

Focused tests use only disposable/native-ABI fixtures. Native source-owner UID1003
and per-store GIDs1004/1004/996, RO/chroot/capability constraints and the existing
physical A/B/C release harness stay real. Destination BUSY is induced only inside
disposable private staging, never by writing original sources. Deadline is a
test-only shortened helper budget; status/page-budget negatives are explicitly
injected callback canaries, not alleged original database corruption. Tests also
cover actual root cancellation, required DONE, original step cap, bad/unknown
reports and all three positive reaps/cleanup/shmem-zero/double-empty releases.
WSL fixture provenance seams are still **NOT installed F2/F3 qualification**;
do not rerun or reopen the previously accepted generic5.15 gates.

NEXT=TECHLEAD_EXACT_SOURCE_REVIEW_THEN_SYSADMIN_NEW_ATTENDED_LAB_GO.
PUSH=NO; PR=NO; MERGE=NO; INSTALL=NO; PRODUCTION=NO; OLD_QUEUE_REPLAY=NO.
