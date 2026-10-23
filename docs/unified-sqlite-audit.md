# Optional unified SQLite audit (QIO226-USQA-01)

Status: disabled candidate; native operational admission requires separate review.
Architecture: Issue #226 v1/v1.1; existing 17-store Operations inventory is the
only path/ownership catalog. Existing owner initialization, first-write,
migration, recovery and deep-check gates are UNCHANGED. No universal fast-start
or physical HDD improvement is claimed.

## Configuration and preflight

`SQLITE_UNIFIED_AUDIT_ENABLED=false` is the default. The value follows
`app/config.py` → `app/settings.py:get_settings()`. Only exact `true` enables
the optional observer. Invalid/missing values disable it without changing Auth
or CAPPORT. OFF does not probe, load bindings, open sources or write a journal.

ON loads the existing protected `/etc/captiveportal/admin-db-services-v1.json`.
Absent/unsafe bindings produce `BLOCKED_NO_TRUSTED_BINDINGS`, 17 catalog-only
entries, bound=0, evaluated=0 and UNKNOWN eligible denominators. The portal
continues subject to its unchanged normal startup gates. Admin Operations keeps
its independent existing unavailable semantics. No manifest is generated.

Startup preflight observes existing owner evidence without refresh and only
owner-qualified file metadata. It adds no SQL/quick_check, history scan, backup
or source creation. Normal portal startup has no qualified deep jobs by default.

## Readiness and one-shot admission

The enabled Flask route `GET /__internal/audit-ready` is passive. It rejects
non-loopback peers, nonlocal Host and proxy/forwarding headers, including the
original address before ProxyFix. The runner requires an actual 204, current
run UUID, boot ID, PID/start and a local listening socket held by that process.
App construction and systemd `active` are not readiness. Public reverse-proxy
denial MUST be independently verified before any enablement.

`python -m app.unified_sqlite_audit.cli run-once` is a single invocation, not a
polling daemon. It never enables itself. The candidate oneshot has
`WantedBy=captive-portal.service`, `After=`, `Requisite=` and `PartOf=` for that
portal unit, with `RemainAfterExit=yes` (no resident process). Only a separately
approved SysAdmin enable would create the protected
`/etc/systemd/system/captive-portal.service.wants/captivportal-unified-sqlite-audit.service`
binding. No enable/install/start or portal-unit edit is performed by this task.
`After=` alone is NOT activation or HTTP readiness. The automatic command uses
`--wait-until-ready-or-cancelled`: no elapsed budget or fixed attempt ceiling,
even if startup lasts hours. Only transient local transport unavailability is
retried, with a cheap cancellation-aware pause; invalid proof/proxy/security
responses terminate closed. SIGTERM/SIGINT/service stop cancels the wait. After
authenticated 204 it invokes exactly one existing run_once. Default manual CLI
is still a single fail-fast probe; optional finite `--wait-ready-seconds` is
mutually exclusive with automatic waiting. Real systemd lifecycle/proxy protection remains
an operational gate. The journal directory must be explicitly provisioned.
Duplicate same-run triggers return the existing cycle. Unfinished executor/PID
reuse or unknown release results in ORPHAN_HOLD, including across portal boots.
There is no automatic stale-lock deletion, orphan cleanup assertion or replay.

## Explicit owner/SysAdmin qualification

Bindings alone never authorize reads. The CLI optionally accepts
`--qualifications <root-owned-file>`: protected root-owned ancestors, regular
non-symlink single-link file, not group/other writable, maximum 32768 bytes.
This is a CURRENT-run admission attestation for a subset of the existing
catalog, **not a second path catalog**. No source paths or validator imports are
accepted. Pure schema:

```json
{
  "version": "audit.owner-qualification.v1",
  "portal_run_id": "<actual current readiness UUID>",
  "stores": [{
    "store_id": "<existing canonical ID>",
    "source_id": "<existing opaque dev/inode SHA256>",
    "uid": 1000,
    "gid": 1000,
    "max_snapshot_bytes": 16777216,
    "host_memory_budget_bytes": 268435456,
    "no_competing_audit": true,
    "cgroup": "/<qualified oneshot cgroup>"
  }]
}
```

Values above illustrate the schema, NOT qualified identities or limits. No
attestation file is shipped/created. Owner and SysAdmin must attest effective
source identity, same-UID read authority, host reserve, enablement and absence
of competing separate full audits. External owners without same-UID RO access
are NOT_ADMITTED; no privilege broker, setuid, ACL change or cross-UID fallback.

The shipped invocation explicitly passes
`--qualifications=${SQLITE_UNIFIED_AUDIT_QUALIFICATIONS}`; SysAdmin supplies the
actual protected file path, never a guessed source path. Empty/unset means no
admission and zero source opens. CLI reads its flag AND default port through
`get_settings()` (not a hard-coded 8080); `--port` is an explicit qualified
override only. Candidate `EnvironmentFile=/etc/default/captive-portal` matches
the reviewed portal unit's base environment path; equivalent effective drop-ins,
flag, port and process environment still require SysAdmin verification. No actual
target unit/drop-ins were read or altered by Coder.

**Operational integration HOLD:** the root-owned qualification is CURRENT-run
bound. An old run's policy is rejected. SysAdmin/owner must supply the exact
current policy before this admitted invocation, and resolve its ordering with
the `.wants` activation. No root policy producer or per-boot authorization writer
is present/authorized in this code task. If automatic renewal requires another
protected unit/drop-in/file producer, STOP that operational portion and obtain
the exact owner contract; do not add a broker, accept a wildcard run ID, relax
file protections or silently generate authorization. Thus the code-only unit
does NOT yet establish automatic **qualified** audits on an actual target.

The native guard independently checks existing OS read-only mounts for source,
family and directory; zero effective capabilities, NoNewPrivs; protected cgroup
controls; exact non-root cgroup identity; visible ancestor limits; finite
effective memory.max; effective memory.swap.max=0 and zero swap.current; guest
reserve and admitted host memory budget. Unknown/unsafe => no SQLite connection.
It does not create cgroups, mounts, directories or permissions. Shared-UID or
hidden-ancestor deployment limitations require owner review, not fallback.

## Deep result and release

Exactly one worker/image: WAL-aware SQLite `mode=ro`, standard online backup to
fresh `:memory:`, RAM-only temp storage, complete integrity_check and complete
foreign_key_check enumeration. No immutable, checkpoint, durability change,
repair or source DML. Main dev/inode/path replacement or an unsafe family path
is rejected. Ordinary live WAL appends do NOT invalidate the already frozen
RAM image: complete checks retain their snapshot verdict and positive release
receipt. All deep assurance is explicitly `SNAPSHOT_ONLY`; aggregate
`live_integrity_verified=false`. Opaque file metadata observations are named
`source_observation_before/snapshot/after`, NOT a committed SQLite/application
generation; `source_generation` remains unknown. If live data advances during
copy/check/release, `live_freshness=ADVANCED` and row freshness is `STALE`, while
the exact frozen snapshot may still PASS. No last-verified success axis (including
legacy full-domain success) is promoted from that stale-live result; the parent
publishes only its independent `deep.snapshot_receipt` for the released image.
A reviewed `(store_id, validator_id)` callable may be
injected by owner code on the same read-only RAM connection. No production T3
validators are invented/shipped by this task; CLI qualification is physical-only.

Systemd dependency semantics: [systemd.unit](https://www.freedesktop.org/software/systemd/man/249/systemd.unit.html).
Snapshot semantics: [SQLite Online Backup API](https://www.sqlite.org/backup.html).

The worker result is provisional. Only positive process exit/reap, disappearance
of its /proc identity, no remaining process group and cgroup membership reduced
to the runner permit publishing receipts and admitting another store. Unknown
release stops the FIFO at ORPHAN_HOLD. Cancellation escalates TERM/KILL with
bounded cleanup waits; a healthy backup/T3 has NO elapsed-time PASS/FAIL cutoff.

Physical and domain coverage have separate eligible denominators. Missing T3
permits physical PASS but domain NOT_ADMITTED, never legacy full success.
Domain FAIL does not relabel physical corruption. Historical receipts remain
historical across boots/source changes. No current PASS is inherited.

## Status, evidence and rollback

`UnifiedSqliteAuditReadService.snapshot()` is the sole sanitized public read
contract (`audit.unified.v1`). No Admin UI changes or extra per-DB endpoints.
One bounded atomic journal contains sanitized outcomes plus private executor
PID/start/boot provenance; public projection excludes that envelope. Writes and
fsync occur only on transitions, never per page or periodic polling. A separate
stable flock file protects the atomic-replace journal. Invalid/partial/unsafe
journal fails closed; no source access is performed by status reads.

Portable algorithm tests explicitly mock qualified OS admission. Mocked cgroup
decision tests and real child reaping tests are NOT native containment proof.
The ordinary WSL shell at cgroup `/` is not admitted: no qualified finite leaf,
NoNewPrivs is off, source mounts are writable. No system/runtime provisioning is
authorized here. Actual qualified RO/no-swap, peer proxy protection and owner
host-reserve evidence remain separate Owner/SysAdmin operational gates.

Rollback: leave feature OFF; stop/cancel/reap an admitted worker and positively
reconcile releases before disabling the integration. Never erase journals to
assert cleanup, change source DB/WAL/schema or bypass owner startup checks.
Production, service install/restart and main merge are not authorized.
