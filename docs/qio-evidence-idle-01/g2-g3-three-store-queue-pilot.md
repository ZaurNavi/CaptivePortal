# Issue 226 — B2 + G3 three-store attended LAB pilot

Implementation candidate, **not installed or admitted for live execution**.
Normative task: Issue 226 comment 6267651916; Owner sequence 6267783868;
host-budget disposition 6267958295. No production, timers, main startup or UI.
Three-store coverage is not the final 17/17 integration milestone.

## Frozen lineage and scope

- Ancestor HEAD: `4e9da8da11e6f8ae709d897cfca6c41344be18d1`.
- Ancestor tree: `76ad848db3f3b9e0a85d9d7357b90c4caecc3d86`.
- Accepted G1/G2/OP-A/B1 composed tree: `d97d8cd380c5429948942d9ff84d96885cee0d75`.
- B2 adds only coordinator code/tests and this document. Existing owner modules,
  SQLite schemas/durability/startup paths and accepted tests are unchanged.
- The old fixture worker still denies absent fixture authority; it does not
  acquire an operational fallback. A separate private blocked child executes
  the explicitly selected real read-only adapters.

## What is and is not measured

The child enforces **guest VM only** `/proc/meminfo`, vmstat, memory PSI,
RSS/RLIMIT and the complete visible native cgroup2 ancestor chain. It never
claims these are hypervisor observations. Native root absence of memory files
is represented as `ROOT_CONTROL_NOT_EXPOSED`, with no invented numeric cap.
Missing non-root controls, finite leaf cap, swap zero, stable identity,
freshness, pressure/event/reclaim growth or sufficient headroom denies work.

`ResourcePolicy.host_reserve_bytes` in unchanged OP-A is a historical misnomer:
it is a conservative **guest-local available-memory margin**. Its old behavior
and tests are preserved. New policies call it `guest_reserve_bytes` and cannot
set that margin to zero. There is no host token, approval file, host environment
variable, SSH/API/collector or automatic hypervisor-pressure abort.

Immediately before ONE attended A/B/C batch, TechLead/SysAdmin records outside
the application: exact host/VM, code SHA/tree/interpreter, current host and
guest reserve/swap/pressure, competing work, approved store identities, three
idempotency keys, returned job/attempt/epoch IDs and short experiment window.
Historical host SwapFree=136 kB is not a current admission receipt. Insufficient
or uncertain host budget, or inability to supervise, means do not submit.
Host degradation during the batch requires operator scoped cancel/STOP.
Approval never survives restart, a fourth request or another time window.

## Local installation policy (SysAdmin later, no Coder installation)

The only daemon command is `python -B -E -s -m
app.db_audit_coordinator.daemon_cli run`. No install/enable/reset command or
source/socket/profile-path override exists. Missing policy or `enabled=false`
fails closed. Nothing is wired into `run.py` or systemd by this patch.

The fixed root-only policy `/etc/captive-portal/db-audit/pilot.json` is ordinary
installation configuration, **not host approval**. It has a closed schema:

- `schema=db_audit_coordinator.pilot.v1`, explicit boolean `enabled`;
- fixed `root=/var/lib/captive-portal/db-audit` and
  `socket=/run/captive-portal/db-audit/coordinator.sock`;
- immutable root-owned `release_root`, exact Git `commit`/`tree`, canonical
  root-owned `python` binary and `python_sha256`;
- sorted complete `blobs`: pairs of every `app/**/*.py` relative name/SHA256;
- `delegated`, `delegated_device`, `delegated_inode` for the qualified native
  cgroup2 delegation; **not** an arbitrary mount or system.slice fallback;
- distinct non-root `worker_uid`/`worker_gid`, bounded `worker_groups`, exact
  `operator_uids` and `operator_gid`;
- exactly three `stores`, each with explicit `StorePolicy` fields (see code).

There are deliberately no ready-to-run example cap numbers. Each store pins
effective absolute path, regular main-file dev/inode/owner/group, schema,
main/WAL/image bounds, backup/validator overhead, positive safety and guest
reserve, finite leaf cap and attempt duration. Qualify those values against
actual small-store geometry and worst-case allocation. Admission conservatively
rechecks the full estimated allocation against current headroom even during
backup; it may defer rather than spend an uncertain reserve.

The release must be a clean root-owned immutable Git release matching the
listed app blobs, without app bytecode caches. The qualified interpreter and
all worker import roots must be root-owned and not writable by worker/operator.
The daemon and child run from that exact release with no user site/PYTHONPATH.
No package install, global Python configuration or dependency change is made.

Queue directory: root:worker-group `0710`; root-only queue JSON and owner lock
`0600`; permanent `heavy.lock` root:worker-group `0640`. Group traversal lets
the child independently open the flock, not read/replace the queue. Root alone
owns every atomic publish; child gets sealed memfd copies, never a writable
queue FD. State store requires qualified local ext4 and file+directory fsync.

Socket directory: root:operator-group `0750`; socket `0660`, root peer verified
by client and exact allowed UID verified by daemon. Status/cancel are UID scoped.
Durable state uses `db_audit_coordinator.queue.operational.v1`; fixture state is
not silently promoted. Provision only a separately approved new domain; never
overwrite unknown old history, orphan claims, locks, or accepted idempotency.
No automatic reset, pruning, rollover or orphan temp recovery exists.

The delegation parent must have no internal processes, memory delegated through
every ancestor, supervisor in its separate subgroup, readable controls and
`cgroup.kill`. Each job gets a new job/attempt UUID leaf, finite `memory.max`,
`memory.swap.max=0`, `pids.max=1`. The parent places/attests a blocked child before
one-time release. Worker then independently acquires the permanent global flock
BEFORE geometry, source connection, page/WAL checks or snapshot allocation.
No real delegation, cgroup creation or hardcap was exercised by Coder tests.

## Source-specific bridges and safety

Shortlist and order: A `public_traffic`; B `network_service_intelligence`;
C `traffic_projection`. All three are distinct, disposable/derived small-store
candidates, subject to later real path/size/admission review.

- Public Traffic schema 2: exact owner DDL, singleton/backfill flags, strict
  counters and aggregate INT64 bounds, event/offset/reader/reset semantics.
  Historical processed events are NOT resummed across legitimate resets.
- NI-04 schema 1: exact owner DDL/constants, generation/runtime consistency,
  immutable SHA256 fact IDs, canonical identities/timestamps, FK and rollup
  provenance. The owner's persistent-WAL check is done on the actual source,
  not spoofed on a memory connection. No matching/re-recognition is performed.
- Historical Traffic schema 1: exact owner DDL/validator/enums, versions,
  semantic-contract digest, lifecycle/FK/CHECK and finite rate/count fields.
- Existing Fingerprint full T3 remains available as the fourth adapter bridge
  in code; the actual three-store policy does not enroll it. No 3.8GB rerun.

Job `source_generation` is explicitly a UUIDv5 **physical file-instance anchor**
over store/dev/inode, NOT a fabricated native database UUID. Completed results
separately hash native generation/version lineage and snapshot watermark. Public
Traffic has no native generation singleton: its metadata says
`pinned_file_instance`. No in-place rollback-detection claim is made.

All sources use trusted pre-existing files, `mode=ro`, `query_only`, no source
DDL/DML/checkpoint/journal/durability changes. WAL sources require already
existing native WAL/SHM; worker permissions must prohibit source/parent writes.
No sidecars are manually created/deleted. Concurrent writer changes are allowed
within pinned identity and bounded geometry. Backup is SQLite Online Backup to
one `:memory:` destination with bounded callbacks/restarts and deadline/cancel
checks. Destination gets full `integrity_check`, FK and exact domain checks;
no unavailable validator can return PASS. Source and RAM connections close on
every exit. No file/disk snapshot fallback or `immutable=1` is permitted.

Preflight receipts are at most 300 seconds old. Whole attempt is independently
bounded at at most 5400 seconds, including claim/placement/backup/T3. Active
timeout sends cooperative cancellation, then whole exact-leaf `cgroup.kill`
after a two-second grace. This never substitutes for positive wait/reap.

## One attended batch and failure exercise

Use `operator_cli submit-batch` with three explicit `--a-store/--a-key`,
`--b-store/--b-key`, `--c-store/--c-key` arguments, in the order above. Each
canonical UUID key has scoped durable idempotency. All three acceptance records
are fsynced before the batch reply and before first dispatch. Individual submit
is supported on the socket, but no dispatch occurs until three new distinct
store requests from the same UID are durably accepted. A fourth new job needs a
new separately reviewed attended run; duplicates remain readable first.

Worker holds its global flock through process exit. After actual child `wait`,
the parent requires the exact opened-while-alive pidfd and TWO ordered empty
reads of the same leaf: `populated=0`, no PIDs and no descendants. Only then
adopt result and fsync terminal state; only after that may the next job start.
Cached charged pages alone are not live snapshot/process memory. Missing wait,
replaced leaf, descendants, unknown release or supervisor death means HOLD,
never success inferred from PID absence, low memory.current, TTL or status file.

For the later real experiment TechLead specifies the nondestructive B fault
point. A bounded termination of the exact B worker/leaf can produce
`worker_crashed`, or scoped B cancel can produce `canceled`; neither is an
integrity verdict. Positive cleanup must still release C. Coder's disposable
test instead corrupts ONLY the private RAM destination and proves the genuine
domain `audit_failed` path, then C PASS, without adding a public fault selector.
Do not damage B's source to manufacture an error. Separate supervisor-death
exercise MUST leave C unclaimed. No real-run PASS is asserted by fixture tests.

`operator_cli status JOB_ID` returns scoped truth and last verified success;
`cancel JOB_ID --controller-epoch E [--attempt-id A]` rejects stale/foreign
authority. Queued cancel has no attempt; running cancel requires its exact
attempt. `stop --controller-epoch E` cancels only the caller's attended batch
and prevents its subsequent claims. No public arbitrary PID/path/SQL/force op.

Preserved saturation contract: at most 32 outstanding, one/store and 128
accepted-ever history. #129 rejects without mutation; duplicates resolve before
capacity checks. No eviction/replay, no scheduler, idle polling or heartbeat
writes. The event loop blocks indefinitely when idle; only active deadline and
child/request events wake it. A partial fsync/unknown publication halts authority.

## P0 cutover, later acceptance and rollback

Before any live admission SysAdmin must positively deny BOTH installed direct
Fingerprint bypass paths to every admitted non-root operator, preserving assets:

- `/home/admin/CaptivePortal-Deploy/qio-evidence-fast-start-3fda7af`
- `/home/admin/CaptivePortal-Deploy/qio-ram-audit-58db905`

The runtime checks root-owned `0700` quarantine of these two known roots. This
is NOT proof of a complete launcher/sudo/alias/service inventory; SysAdmin must
review that inventory and prove both denials externally before enablement. No
second child or live audit while this P0 remains. Do not repeat old T3 as proof.

After source review: Owner-approved immutable Git release, qualified interpreter,
filesystem/delegation/UIDs and caps, P0 cutover, fresh external attended host gate,
then ONE A/B/C and separate orphan-negative experiment. Wider release/crash/
security checks belong to TechLead; future 17-store production integration is
a NEW TASK after real LAB acceptance, not part of this patch.

Rollback: stop new submissions; scoped cancel/STOP; positively reap and prove
empty leaves before retiring the coordinator. Preserve queue/idempotency and
both permanent lock inodes; do not truncate/delete/reprovision to clear HOLD.
Unknown orphan requires explicit reconciliation, not bypass. Re-enabling old
direct tools requires separate Owner/TechLead decision and no surviving audit.
No Coder deploy, service restart, real cgroup mutation or production action.

## Root-control correction and one-shot administrative abandonment (#226)

Repair base: `a31a52875f49a336ddf556e54ffb6559eadd3342` (not `main`).
Authority: TechLead4 comment 6272056294 and TechLead5 comment 6276728081.
This code is an offline review candidate. **Real recovery/install remains HOLD**
until independent source acceptance, explicit Owner/TechLead execution GO and
fresh SysAdmin containment. No automatic startup repair or socket operation exists.

Native cgroup2 `/` may omit all five memory controls/counters while exporting
`memory.pressure`. The parser validates any such PSI, retains it for pressure/
stability checks, and keeps absent cap/current/swap/events as `None` plus
`ROOT_CONTROL_NOT_EXPOSED`. It does not invent a cap or counters. A partial
five-control bundle, malformed PSI, missing non-root control, unbounded leaf,
nonzero swap or identity drift still denies admission. This reproduces the
separate confirmed root-layout defect; it **does not prove the exact original
19:40 exit-3 cause**. The daemon now emits only one closed `stage/reason_code`
line on exit 3, without exception payload, traceback, paths or identities.

### Operator runbook — preparation only, NOT execution authorization

Only the fixed old epoch `475efdfc-1ee0-44b7-9829-98552752a3e4`, A job
`8f5a1f66-3b5b-464e-801f-17de2ce72a39`, attempt
`dc1bc15e-a8b1-44f8-a44a-836bb727491c` is eligible. Old A must still be
`public_traffic`, seq1, claimed, PID null; B/C seq2/3 must still be queued,
unclaimed NI-04/Traffic Projection. Exactly three ACKs, next_sequence=4 and
empty last-attempt/last-success maps are required. Any difference is HOLD.

1. SysAdmin first obtains separate exact-queue execution approval. Stop and
   fence all coordinator/worker/legacy launch paths for the entire exclusive
   operator window. Preserve existing queue, locks, profile, release and
   journald. Do not start the daemon to inspect or repair the queue.
2. Perform TWO distinct, stable current kernel observations on the same boot:
   original `qio226-abc-coordinator-lab.service` stopped, MainPID=0; original
   cgroup/descendants absent; all coordinator/worker processes and relevant FD
   owners absent; old child launch paths contained; unexpected legacy auditors
   absent; socket absent. A missing inventory or uncertain release is HOLD.
   Retain the complete bounded read-only evidence for both observations.
   These establish **current nonexistence**, never recovered historical wait,
   pidfd, audit success or positive old child release.
3. Prepare (separately approved installation step) root-owned directory
   `/var/lib/captive-portal/db-audit-recovery`, mode 0700, outside active queue.
   No tool code provisions it. Put the two root-only regular single-link
   evidence files `observation-1.txt` and `observation-2.txt` there. In the same
   directory place root-only `containment.v1.json`. No symlinks or writable
   untrusted ancestors. Its closed schema is defined by `recover_once.attestation`:
   - schema `db_audit_coordinator.abandon.old_epoch.v1`;
   - exact `epoch`, `job_id`, `attempt_id` above, exact original `service`;
   - `queue_identity`, `owner_identity`, `heavy_identity`: [device, inode]
     of current queue, permanent coordinator.lock and independent heavy.lock;
   - exact original queue `queue_sha256`, `queue_bytes`, same kernel `boot_id`;
   - `observations`: exactly two records with distinct `captured_ns` from the
     same machine's monotonic clock, `evidence_sha256`, integer `main_pid=0`,
     and closed `checks` with every value literal true:
     `original_unit_stopped`, `original_cgroup_and_descendants_absent`,
     `coordinator_and_worker_absent`, `process_fd_owners_absent`,
     `old_child_launch_paths_contained`, `unexpected_legacy_auditors_absent`,
     `launches_fenced_for_operator_window`, `socket_absent`.
   Both observations must be younger than 60 seconds at validation and again
   immediately before queue publication. Their evidence files must match both
   hashes. **This is explicit root operator attestation, not automated proof
   that every process is absent.** Do not fill true without the named checks.
4. From the exact accepted immutable repaired release, approved interpreter,
   with no parallel launch activity, root may later invoke exactly:
   `python -B -E -s -m app.db_audit_coordinator.recover_once abandon-old-epoch`.
   There are no path, epoch, force, reset or environment overrides. It checks
   both permanent locks non-blocking, exact inode/dev and modes (0600 owner,
   0640 heavy, empty single-link root-owned files); never replaces a lock.
5. Before the one atomic transition it exclusively creates a 0400 exact-byte
   queue backup `old-epoch-<epoch>.queue-before.json` and a copy of the root
   attestation alongside it, fsyncing both files and directory. Receipt holds
   the original queue SHA256. Files are immutable **by protected policy** (not
   a claim of filesystem immutable flags). Existing/partial evidence blocks
   retry; never overwrite or delete it to resume. Recheck source bytes/inode,
   directory identities, receipt freshness and both locks before publication.
6. A becomes `deferred`, with `incomplete/restarted_after_claim`, no snapshot
   or verified success. B/C become `canceled` with null attempt/worker/result:
   **canceled before execution**, not failed worker results. All three ACKs,
   job IDs, scoped idempotency hashes, seq, old claim/attempt/epoch and the
   unchanged 128-history semantics survive. next_sequence stays 4. The single
   existing queue atomic replacement uses file+directory fsync; the new JSON
   is independently parsed and compared. There is no reset, pruning or new
   queue. Repeating the command makes no queue/evidence write and returns HOLD.
7. Exit 3 or unknown directory-fsync outcome means STOP and independent review
   of queue plus protected evidence, not retry or manual JSON surgery. A
   pre-publication evidence failure can leave a protected partial backup and
   unchanged queue. A post-rename fsync failure may leave terminal bytes with
   unknown durability; do not treat it as completed recovery or start work.
8. Only after independently verified committed abandonment, accepted repaired
   install and all original P0/resource/source/host gates may a NEW supervised
   coordinator epoch accept a fresh A/B/C batch. Recovery itself never rotates
   epoch, starts services, submits work or claims old B/C. Real pilot remains
   **A PASS → B contained failure → C PASS**, not a historical PASS retrofit.

Coder verification uses only disposable queues/locks and synthetic observation
documents; no real LAB state or native cgroup tree is mutated. Linux root
fixtures exercise actual flock, nofollow, root modes, evidence fsync, atomic
publication, repeat refusal and injected faults. Portable contract/diagnostic
cases also run on Windows. Wider security/crash/release acceptance is TechLead5's
responsibility; these tests do not grant operational recovery authority.
