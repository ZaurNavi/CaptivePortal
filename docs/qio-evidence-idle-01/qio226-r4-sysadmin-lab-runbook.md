# QIO226 / 04D R4 — pinned T3 directory capability and first-HOLD attribution

## 04K-R1 — active R4 duration fixes; pre-admission bootstrap HOLD

Authority: [04K-R1 final correction](https://github.com/ZaurNavi/CaptivePortal/issues/226#issuecomment-6362904919).
R4 sends, including cancel, explicitly use seconds=None; owner cancel receive
also uses None after readiness. After authenticated released + exact child reap,
root closes IPC endpoints and joins existing reader/reaper threads to actual
termination, never a timed join false-HOLD. Shared IPC defaults stay unchanged.

R4_BOOTSTRAP_300S=UNRESOLVED_PRE_ADMISSION. Before authorize() reads its FIFO,
both methods use the same root command with only auth_fd. The R4 discriminator,
sealed profile/claim FD numbers and parent binding are inside the unread message;
an unverified r4_fd must not select an unlimited path. Controlled fake-clock/
real-pipe proof resumes at301s and rejects before decoding for either possible
method. A trusted pre-auth discriminator requires changing the bootstrap
interface (LiveCoordinator.command / Session.start / authorize); no such change
is made without scope approval. Do not claim ALL LAB LIMITS REMOVED or release
original A/B/C. TechLead disposition required; keep legacy bootstrap finite.

## 04K — active R4 execution has NO elapsed-job-time cutoff

Authority: [Owner/TechLead TASK-COORD-04K](https://github.com/ZaurNavi/CaptivePortal/issues/226#issuecomment-6362416420).
Direct parent: accepted04J `e691c1e8ded3106cfa14d0302f58208796017c1a`,
tree `d452ed7a5b3e0f01085a6b25693a3a3b2c40ae14`. This section supersedes all
historical R4 finite-deadline/1200s and engineering900s instructions below;
their old receipts/queues remain historical facts, not current execution caps.

Only the existing enabled R4 LAB path is changed. Root Session has
`deadline=None`; its sealed, fixed-schema owner capability encodes JSON
`deadline_ns:null`, accepted only as null (not bool, numeric, huge or omitted).
Backup source/progress/BUSY callbacks, T3 guards and worker/owner packet receives
never expire due to elapsed age. Authenticated Unix `receive(seconds=None)` and
the existing root selector wait for actual peer/event/reaper completion. There
is no replacement time cap, timeout toggle or polling scheduler. Elapsed
durations are observations. Legacy `attempt_seconds` and durable
`resource_envelope.timeout_seconds` stay byte/schema compatible but are NOT
effective R4 experiment limits. The bounded diagnostic reap observation (.25s)
remains; it does not measure total job age. R4 per-send timeouts and timed
positive joins are removed by04K-R1 above; pre-auth bootstrap is unresolved.

All gate/source/FD/PID/membership and cgroup memory/swap/ancestor checks remain,
including the once-per-guard fresh full hierarchy. Operator-scoped cancel,
real IPC EOF/helper/worker death, resource violations and source/security
failures remain fail-closed. Root R4 `expire()` never sends `cgroup.kill` due
to age. Uncertain reap/cleanup remains HOLD, not fabricated terminal success.
The non-R4 finite deadline/cancel grace/leaf-kill path is unchanged. SQLite RO,
pinned owner read transaction, callback100000 limit, full integrity/FK/schema/
canonical rows, all strong hashes and positive helper/worker cleanup remain.

Focused QA advances actual process clocks by1201/5401 seconds without sleeping
for those durations: root guard/expire, helper ready/begin/Backup callbacks,
worker T3 and IPC waits must complete with genuine authenticated positive
release. Actual scoped cancellation, child exit/EOF, swap/OOM and finite
non-R4 expiration remain separate negative/regression controls. Existing
uninstalled QA provenance exceptions do NOT qualify installed F2/native5.15.
No additional dense benchmark or performance target is required by04K.

Coder delivers one clean direct-parent LOCAL LAB commit only. No push, PR,
installation, original-source run or production action. After brief TechLead
source/focused PASS, SysAdmin (not Coder) may conduct the separately authorized
ONE full original-backed OLD LAB A→B→C via authenticated submit-batch, fresh
isolated immutable release/epoch/queue/keys, source OS RO main/WAL/SHM,
unchanged UID/root/two-FD/cgroup and positive cleanup. Never use old04J binary
for this trial. A's known `pt_schema_signature` must remain truthful; no
comparator auto-fix. B/C natural results and source safety are the evidence.

## 04H — fast pinned guards, strong boundary SHA and closed T3 attribution

Authority: [TASK-COORD-04H](https://github.com/ZaurNavi/CaptivePortal/issues/226#issuecomment-6324005276).
Exact source parent: `46e66c36bbb61b2bd80e0ca9025c21e554a55eaa`, tree
`ea3bc9c7ce9ec7b1cb9f6d758239f3467fc37d60`. Coder may prepare one direct-parent
LOCAL LAB-only commit after focused disposable tests. Push, PR, installation,
real original A/B/C, queue operations, main and production remain forbidden.

Real04G facts are preserved: owner backup DONE on all three; B real T3 PASS;
A failed/audit_failed with unknown predicate; C hit the original1200s deadline
and was held, then SysAdmin separately retired its exact kernel resources.
That forced retirement is NOT positive R4 release and does not rewrite C.
No original database is inspected here to guess or relax A's domain rule.

Worker now uses two private guard strengths. Fast guard calls the original
resource/deadline/cancel/flock guard EVERY time and rechecks fresh private
proc/self/NSpid/PPid, unchanged CWD, final directory FD/alias, root0440/GID/
regular-file/nlink1 image, inode/device/size, tmpfs receipt, child set and denied
write access. Image and directory stat stamps include fixed nanosecond
mtime/ctime captured at initial ownership handoff; same-size/same-inode
rewrites and restored mtime still fail. No timed content-hash cache is trusted.

Strong guard adds full authenticated image SHA with stable pre/post fast
metadata checks: before SQLite opens, after it opens, and after SQLite CLOSES
before success. Root's independent post-T3 full SHA before cleanup is unchanged.
SQLite VM progress every1000 and canonical per-row callbacks use fast checks,
not full-image reads. Full integrity_check, foreign_key_check, exact schema,
canonical deep=True and all row/lineage/watermark assertions remain. No timeout,
image allowance, owner read transaction, backup callback100000 cap, SQLite
PRAGMA/durability, authorization, import provenance or release fence changed.

The image is writable by no untrusted validator/source owner after helper reap
and promotion. Root remains the trusted supervisor. The new stat pins plus
strong boundary hashes do not claim protection against a malicious privileged
root that can alter the code or falsify the kernel's metadata/clock. No such
authority is granted to UID995 or the original source owner.

One OPTIONAL `t3_diagnostic` object travels only inside authenticated private
`t3_done`, with existing SO_PASSCRED/PID/claim-binding and no new FD/channel.
Root validates exact field names, enums, integer types/ranges (bool rejected)
and emits at most one protected `qio226_r4_t3_outcome` summary. It is stripped
before adopting the original result/reason/snapshot fields: no public audit_result,
queue or release-proof schema change. Missing/none is `unreported`; malformed
private payload is rejected without echoing values. A broken logging sink
cannot change the result. A valid diagnostic never authorizes PASS or release.

Summary: last ACTUALLY entered check/stage, sanitized exception class, category
(domain/resource_guard/snapshot_tamper/unexpected/none), fast-guard and VM counts
(clamped100000), full-digest count (<=3), successfully verified digest bytes,
elapsed_ms and fixed integrity/FK/adapter/final-digest timings. No per-row/tick
logging, raw exception, SQL, source path, SSID, IP/MAC, row/job/event ID or payload.
Milliseconds/counts are bounded diagnostics, not a wider resource allowance.
The last check is set before its real query/assertion; it is not proof a later
check ran. Native CHECK/FK failures can correctly stop at sqlite_integrity/FK
before the more specific adapter stage. Do not relabel those as a later check.

Python guard exceptions captured in SQLite progress are re-raised as the
original private guard failure, not mislabeled as logical corruption merely
because SQLite wraps them as interrupted. Semantic T3 failures preserve
failed/audit_failed. Structural refusals use existing incomplete/preflight_denied;
cancellation stays incomplete/canceled. An expired/resource-invalid guard may
prevent any final packet/release, leaving the existing fail-closed orphan HOLD.
Missing diagnostic then remains unreported, never a fabricated exact cause.

Focused fixtures include a canonical117MiB+ C with16000 actual site-state rows,
native SQLite VM progress, nonowner995/993 and real private PIDNS/proc/tmpfs
two-FD transport. An exact04G bounded12-guard prefix is compared with the same
candidate prefix; the full candidate separately must finish full T3 and final
SHA. A canceled prefix is not a baseline PASS or a full-baseline runtime.
Synthetic timings/bytes are RAM/Lab measurements, not original HDD/production
savings or proof that full hashing was the ONLY real1200s C cause. Preserve
the actual per-stage receipt for a next independently approved native run.

UID995 cannot traverse the laptop owner's HOME: new native pipeline fixtures
copy the existing test interpreter/dependencies and exact source bytes into a
disposable traversable root; no package install, global chmod, user-site stub
or installed F2 exception is introduced. These are QA-only provenance seams,
not qualification of the immutable installed interpreter/release.

NEXT=TECHLEAD_EXACT_SOURCE_REVIEW; then a separately approved SysAdmin original
A/B/C only after old orphan kernel-clearance evidence and exact publication.
Do not rerun old recovery, change an epoch/lock/history, restart services or
grant source/helper access based on this source-only handoff.

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

## 04G — one read transaction across the native backup

Authority: [04F original A/B/C 128-page plateau](https://github.com/ZaurNavi/CaptivePortal/issues/226#issuecomment-6317327603).
Source parent: accepted04F `dcc2a130342c7192ab2bbac5a8aff92d6ae923ed`.
Those three real attempts remain deferred, snapshot=null, zero real T3 PASS.
Their positive cleanup is not successful backup; the forced service stop is
not graceful shutdown. Do not replay, reset or rewrite any historical result.

Native CPython3.10 / SQLite3.37.2 disposable reproduction, using the unchanged
R4 read-only file bindings, owner chroot, actual UID drop and private tmpfs:
a valid228-page WAL-mode image, no active writer, native empty WAL and retained
SHM yields repeated `(0,100,228)` with autocommit backup128-page steps. This
reproduces the exact128-page plateau WITHOUT concurrent source changes, BUSY,
LOCKED, corruption or a fake progress callback. All main/WAL/SHM SHA256 values
remain identical. The fixture writer constructs/checkpoints its OWN disposable
database before exiting; no implementation/operator checkpoint is added.
Nonempty idle WAL and stable active-writer controls reach DONE. A second,
event-coordinated synthetic writer that commits between steps independently
reproduces the same plateau. The real04F numeric report alone does not establish
which restart trigger occurred on the originals; no new original-source access
is claimed by Coder.

In SQLite3.37.2 [wal.c](https://github.com/sqlite/sqlite/blob/version-3.37.2/src/wal.c#L2439-L2448),
read-only unreliable SHM with WAL shorter than its header causes `pChanged=1`
even without writes. [pager.c](https://github.com/sqlite/sqlite/blob/version-3.37.2/src/pager.c)
resets the pager on that new read transaction; `pager_reset` restarts attached
backups. [backup.c](https://github.com/sqlite/sqlite/blob/version-3.37.2/src/backup.c#L325-L332)
opens/closes a read transaction per step only when no caller-owned read view
already exists. Thus this is native backup restart, not callback misaccounting
or evidence that a required source write/SHM permission should be granted.

04G adds one deferred `BEGIN` on the existing `mode=ro`, `query_only=ON`,
busy_timeout0 source connection BEFORE the existing schema/page metadata reads.
Those existing reads establish the one WAL read view. It remains open through
all128-page steps, actual DONE, normal backup return and original post-guard;
connection close releases it on success and every exception. No source COMMIT,
DML, checkpoint, journal/durability PRAGMA, writable binding, new VFS, immutable
source bypass, generic sleep or retry loop. Check that the source connection
still owns its transaction before admitting owner_done. No destination
transaction policy changes. Original callback status/count/image validation,
100000 ceiling, finite deadline/cancel, closed diagnostics, UID/GID, memory and
no-swap limits, promotion, two-FD immutable T3 and positive release stay intact.
A pinned reader can delay WAL checkpoint/recycling until its finite attempt
ends; this is bounded by the existing deadline, not a new lifetime allowance.

Focused native tests compare autocommit/pinned callbacks in four controlled
source states, and run actual owner backup plus canonical A/B/C T3 on large
empty-WAL disposable images. All three must reach genuine101/DONE and exact
ceil(page_count/128) callbacks, immutable snapshot transport, helper/worker
positive reap, cleanup, zero shmem/swap and two empty observations. Portable
tests cover RO write denial, external writer isolation, cancellation/deadline
and post-DONE guard rejection/connection close; existing04F fault guards remain.
These are Coder WSL mechanics, NOT installed/native5.15 F2/F3 qualification or
the next original LAB A/B/C proof. TechLead owns independent exact source review;
only then SysAdmin performs its separately authorized preserved-history run.

COMMIT=HOLD; PUSH=NO; PR=NO; MERGE=NO; INSTALL=NO; PRODUCTION=NO.

## 04I — one full SQLite audit, unchanged structural/domain T3

Authority: [TASK-COORD-04I](https://github.com/ZaurNavi/CaptivePortal/issues/226#issuecomment-6346500575).
Source parent: accepted04H `b394bac09060c21965a7b8a2d4b2acaba5af6ab3`.
Only the TrafficProjection T3 adapter requests canonical `_validate(deep=False)`.
Its caller still performs full `integrity_check`, then `foreign_key_check`, on
the SAME immutable connection before adapter entry. The canonical repository's
normal deep callers, schema/columns/index/expression checks, exact schema
signature, row guards, lineage and watermark encoding are unchanged. The closed
diagnostic name `tp_canonical_deep` is retained for compatibility; it now marks
the structural canonical call, not a second physical scan. No public protocol,
source read-view, deadline, release, queue or owner-helper change is made.

[SQLite documents](https://www.sqlite.org/pragma.html#pragma_quick_check) that
quick_check omits index/table consistency and UNIQUE checks present in full
integrity_check; FK is a separate check. Disposable physical-index, UNIQUE and
orphan-FK canaries verify earlier rejection. A native SQLite3.37.2 caveat is
recorded honestly: after mode=ro reopening, the selected CHECK-negative fixture
can return `ok` from BOTH integrity_check and quick_check; the unchanged adapter
numeric check rejects it. Tests compare both native results on that exact RO
connection, rather than falsely claiming earlier rejection. No new guarantee
that every CHECK violation is diagnosed by native SQLite is asserted. The
earlier-gate-only CHECK requirement needs TechLead disposition of this evidence.

The allowed native test module provides a deterministic dense C workload:
65,536 cycles, two APs per cycle, one site/version, 196,610 total canonical rows,
no padding table or oversized error strings. Fixture size and physical hash are
measured, not inferred from original LAB C. Compare exact clean04H app and the
direct-parent LOCAL04I commit, with the SAME qualified interpreter, copied QA
harness, private PIDNS/procfs, two descriptors, tmpfs, actual UID995/GID993/no
supplementary groups, source UID1003/GID996/mode0600 and original1200s budget.
The copied QA harness is NOT an installed-release/F2 qualification or a Git
identity claim for the copy; record original commit/tree and source blob hashes.

QA cost instrumentation wraps, never bypasses, the real guard on EVERY call.
It retains the1000-opcode VM interval and three full image hashes. At most six
aggregate checkpoints plus one final record per T3 go to a root-private0600
child log; no row/SQL payload. Record actual wall/process/user/system CPU,
per-stage guard CPU, encode CPU, canonical and SQLite execute timing, existing
T3 phases/counts and image hashes. SQLite/canonical timings INCLUDE callbacks
and therefore overlap guard timings; do not sum them as disjoint costs.
`/proc/self/io` is recorded only when permitted after the real UID drop; an
unavailable field remains unavailable, without changing process dumpability or
permissions. Logical rchar is not guest block or physical host HDD I/O.
Standalone raw quick/FK timing is a separate same-image control with no security
guard, not the cost of guarded scans or a measurement of the original C.

If the original1200s limit is reached, preserve the observed stage/aggregate
CPU evidence and HOLD. Do not cache security checks, raise progress intervals,
skip rows/hashes or extend deadlines to obtain PASS. Positive release requires
actual reaps, cleanup, zero shmem/swap and two empty observations; test-finally
disposal after a failed fixture is not a production positive-release receipt.

A remains separate. Test-only lexical comparison proposes stripping ASCII
whitespace BETWEEN tokens while preserving quoted literal/identifier bytes,
comments, operators, numeric spelling and unknown-syntax rejection. It reports
closed classes and hashes, not DDL payload. Real A's seven raw-signature
differences plus simple whitespace-collapse equality do NOT prove lexical or
semantic equivalence. `adapter_public_traffic` exact predicate remains unchanged
and the disposable whitespace-only variant still fails current acceptance.
No original A read, migration or invented PASS is authorized by this proposal.

Native source/history and retained04F/04G/04H negative tests stay in scope.
Coder runs only affected Linux root/nonroot and portable Windows tests; full
independent acceptance belongs to TechLead. Existing OLD LAB results and scoped
SysAdmin retirement are not rewritten by LOCAL fixture success or cleanup.

LOCAL_COMMIT=REQUIRED_FOR_HANDOFF; PUSH=NO; PR=NO; INSTALL=NO; PRODUCTION=NO.

## 04J — one fresh full hierarchy observation per mandatory R4 guard

Authority: [TechLead7 TASK 04J](https://github.com/ZaurNavi/CaptivePortal/issues/226#issuecomment-6352952961).
Exact parent: accepted04I `87306d076a07b458e021ca51eefffffb98098f46`,
tree `85c6f82fb67a7a218f85880a7b80bed7108753ca`.
Only `execute_r4.guard` changes: bind the result of `leaf.samples()` to a local
variable, use its last node for the existing policy checks, and pass that SAME
complete tuple to `guest_sample(...).check()`. Every next invocation obtains a
new kernel observation. There is no cross-call cache, interval sampling,
shortened ancestry, reduced VM/row callbacks, new resource limit or timeout.
The original leading deadline/gate/leaf checks, cancel pipe and exact process
membership precede that observation. All existing exception classes and result
mapping remain unchanged. In particular the closed `CoordinatorError` already
normalizes the internal `canceled` token to `coordinator_unavailable`; the
coordinator's separate canceled-result mapping must still be tested, not fixed
by broadening the public error vocabulary in this task.

QA wraps the original `Leaf.samples`, secure directory/read_at operations and
actual `os.open`/`os.read` calls, without substituting values or skipping any
check. Aggregate per-ancestor/per-field attempts, successful opens, kernel read
calls and bytes distinguish absent optional root controls from real reads.
One bounded final aggregate per T3 records exactly one complete traversal per
successful VM/row guard. Existing04I CPU/stage/hash observer remains the same;
these observers add measurement overhead and do not establish physical HDD I/O.
No per-row/cgroup disk log is emitted during the large measurement.

Native UID995/GID993 tests execute the exact guard body compiled before the UID
drop, with genuine cgroup2, `/proc`, real gate and pipe FDs. Two independent
calls prove fresh observations and live membership/deadline/cancel/gate and
directory-mount rejection. Explicit private bind-mounted counter fixtures
exercise otherwise unsafe or infeasible states (nonzero swap.current, invalid
ancestor current/subtree/pressure, OOM counter) via real native file reads.
They are adversarial filesystem views, NOT a claim of actual swapped memory.
A separate real, test-owned leaf OOM kills only the disposable validator and
must not be described as positive R4 release. Full authenticated A/B/C pipeline
tests independently prove the genuine owner/worker/root handoff, immutable
two-FD image, three worker digests plus independent root hash, original online
backup read-view/BUSY controls, actual reaps, zero shmem/swap and double empty.
Test-finally disposal of a negative is never counted as successful R4 release.

Keep the exact04I dense C fixture and old baseline receipts unchanged. Before
the single candidate measurement, prove interpreter/kernel/SQLite/compile
options, source and deterministic image hashes, UID/GID, memory/deadline and
I/O profile comparability. Measure all196610 rows in an image at least147800064
bytes at the existing1200s cap. Record elapsed/CPU, each stage, guard/traversal
counts, actual cgroup reads, proc I/O, OOM/swap and real release. The engineering
admission target is T3<=900s (25% Lab margin), NOT a runtime timeout change.
If it is missed, HOLD and report; no extra optimization, original trial or
deadline change follows automatically. Existing04I1041s baseline need not be
rerun when comparability is proven. Actual results belong in the immutable
external handoff, not an invented runbook PASS.

04I's CHECK-negative disposition is end-to-end unchanged-domain rejection,
not a claim that that fixture must fail at the earlier integrity stage. The
real A schema remains independently `failed/audit_failed,pt_schema_signature`;
this guard change does not accept whitespace-collapsed signatures or authorize
original data access. Original A/B/C remain HOLD pending TechLead decision
after independent review. Preserve all04H queue/inode/retirement history.

LOCAL_LAB_COMMIT=REQUIRED; PUSH=NO; PR=NO; INSTALL=NO; ORIGINALS=NO;
MERGE=NO; PRODUCTION=NO. Full independent acceptance belongs to TechLead.
