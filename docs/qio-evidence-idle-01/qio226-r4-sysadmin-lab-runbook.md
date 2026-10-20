# QIO226 / 04C R4 — SysAdmin mixed-source-GID handoff and attended LAB runbook

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
