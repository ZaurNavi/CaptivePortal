# Issue #295 WP2 — Sensor metadata export provisioning design

Status: code/Lab design for Tech Lead review; **NOT production provisioning GO**.
Baseline: `080af74c8388a25f691f4de43781402613fae9d8`, accepted WP1 tree
`5e72133e994720dba00054751534fe8f6a446c2f`. Accepted WP2 candidate:
`d8526407a16063b142488b67e801d37111b8b981`. The WP3 additions below are
isolated implementation only, pending independent acceptance. No database attestation.

## Trust boundary (SysAdmin + Owner only)

The fixed artifact is
`/run/captiveportal-operations/sensor/metadata.json`.

| Resource | Owner/group | Required mode | Purpose |
| --- | --- | --- | --- |
| `/run` and fixed parent ancestry | root, no group/other write | existing secure directories | No path-component symlink or replaceable parent |
| `/run/captiveportal-operations` | root:root | 0755 | Dedicated root-controlled tmpfs parent |
| `sensor` child | fingerprint-sensor:captiveportal-ops-reader | 02750 | Only Sensor writes; dedicated group can traverse/read sanitized export |
| `metadata.json` and new temporary regular file | fingerprint-sensor:captiveportal-ops-reader | 0640, one hard link | Portal group read only, no group/other write |

The setgid child makes new temporary files inherit only the dedicated export
group; use an effective umask compatible with 0640 (e.g. 0027). A restrictive
umask that prevents the required group read fails closed, not auto-chmod.
No named/default ACL may grant additional write access. Do not reuse the Sensor
raw DB group as the export group; code explicitly rejects aliasing Sensor's
primary GID. SysAdmin must also ensure the group is not an alias of any other
sensitive group. Do not add Portal to fingerprint-sensor/fingerprint-eve or
grant traversal/ACL/world-readable permissions on the raw DB directory.

Only the provisioned dedicated child is writable by Sensor. Parent ownership
prevents Sensor replacing the child directory with a symlink. A mode/owner/group
change, wrong filesystem, mount/file-device mismatch, symlink, nonregular file,
oversize or hard link causes UNKNOWN rather than a bypass. The code walks
directory FDs with O_DIRECTORY/O_NOFOLLOW and verifies native Linux fstatfs
TMPFS_MAGIC. It does not create directories, groups, ACLs or systemd settings.

## Required independent deployment review (no commands executed by Coder)

Before any provisioning or activation, SysAdmin must collect safe effective
UID/GID, supplementary groups, mount/sandbox and configured source-path evidence.
The reporter's exact fixed store IDs must match the already trusted deployment
manifest bindings to Sensor's configured `spool_path` and enabled NI02A `db_path`.
No paths are exported, so that binding is a deployment responsibility, not an
inference from JSON. Disabled NI02A is explicitly UNKNOWN/source_disabled, with
no guessed/default DB read. Existing Sensor directory permissions stay intact.

The checked repository Sensor template uses ProtectSystem=strict and existing
ReadWritePaths for its raw/spool paths; it does NOT authorize this new child.
After code acceptance, **separate Owner approval** is required for any provisioning,
dedicated Portal supplementary group and narrowly additive sandbox changes:

- Sensor: permit write only to the exact dedicated tmpfs child (not its parent),
  retaining existing Eve access, raw DB paths and all other sandbox/capability
  limits. No new capability is required.
- Portal: read/traverse only the sanitized export child via the dedicated group;
  no write access, no raw DB rights. Review any effective ReadOnlyPaths,
  InaccessiblePaths, PrivateMounts, RootDirectory or hidepid/proc restrictions.
  Bind-mount the directory only if separately approved; never pin the report file
  inode, since publication uses atomic rename.
- Existing startup flag `WEB_ADMIN_DB_SERVICES_ENABLED=true` must be explicitly
  provided to Sensor as well as Portal for the optional publisher. It is the SAME
  Operations flag, not a second feature switch. Missing/noncanonical values keep
  the publisher OFF. No per-tick environment reread. Current production env and
  units are not changed by this patch.
- Kernel boot ID and bounded `/proc/<systemd Sensor MainPID>/stat` start identity
  must be readable under the actual Portal sandbox. If not, keep UNKNOWN and
  request a bounded decision; do not widen proc/raw DB privileges opportunistically.
- Confirm actual on-host account/group names and /run tmpfs. Missing group/path,
  wrong UID/GID or unapproved sandbox means **WP2 production activation HOLD**.

The metadata read is not an app-health proof: process RUNNING plus successful
export is never HEALTHY. WP3 adds the two explicit native producers described
below; the remaining seven services have UNKNOWN app health. V1 and V2 share
ONE30-second sampler/cache. Source TTL is independently enforced on cached
responses, without another sample or filesystem read.

## Protocol and I/O

Schema `captivprod.ops.sensor-metadata.v1`, fixed Sensor unit, kernel boot/PID/start
identity, random per-process exporter epoch, monotonic sequence, UTC and Linux
boottime sample clocks, complete/partial and exactly two stores. Up to seven
bounded owner-side lstat calls: main/WAL/SHM for attribution, main/WAL/SHM/journal
for spool. Final symlink/nonregular/foreign-owner/hard-link, collision, EACCES or
expired budget => unknown, never zero. Only verified ENOENT => absent/0.
No source contents or SQLite access; no IP/MAC/device IDs, SQL, paths or raw errors.

Publication occurs only after an existing 60-second telemetry tick, after refresh
and metrics. Nonblocking single-publisher lock and a 60-second last-attempt gate
also throttle failures. A cooperative 50-ms local-operation budget refuses late
publication. As with existing lstat collection, Python cannot preempt a wedged
kernel filesystem syscall; this is a dedicated local tmpfs channel, not a remote
filesystem or a hard-real-time guarantee. Nothing new runs on capture/delivery
threads, and optional exporter exceptions never change Sensor state/spool health.

One exclusive temporary file and one atomic replace, at most 4096 bytes; no
fsync/fdatasync, SQLite transaction or durable retry history. Failed publication
leaves the old file untouched and removes only its own unpublished temporary file.
Old valid metadata naturally expires. Reader checks size/schema/duplicate keys,
file identity/owner/mode, PID/start/boot, epoch/sequence and both clock ages. Age
over 180 seconds is STALE; future or inconsistent clocks/restart/replay are UNKNOWN.

The DELETE-journal component is separate, never WAL. **V1 footprint intentionally
remains main + WAL + SHM** for compatibility; journal is retained only inside the
typed exporter result and separately exposed by the WP3 v2 DTO. A missing journal is zero
only on ENOENT, and unknown journal metadata is not silently verified.

## Acceptance and rollback ownership

Coder uses synthetic fixtures and disposable tmpfs with distinct numeric
Sensor/Portal/outsider principals, no installed account/group changes. Native
tests prove Portal export access AND raw-store denial, outsider denial, invalid
permissions/schema/races, TTL/restart and atomic replace. Exact module bytes are
copied into a root-owned disposable test code directory so those test principals
do not need access to the developer home. Test source canaries are not SQLite DBs.

Independent systemd/sandbox, full regression, real browser, physical-device I/O
and security admission remain Tech Lead/RQA work. Lab `/proc/self/io` accounting
on verified tmpfs is not a production HDD measurement or performance acceptance.

Rollback is optional-exporter/Operations flag OFF with separately authorized
process restart and provisioning cleanup. No application DB/schema/data rollback,
checkpoint or raw Sensor path permission change is needed. Coder does not execute
this procedure. Missing export remains UNKNOWN; there is no direct DB fallback.

## WP3 — native health, versioned DTO and disclosed NI02B trust

Authority: TechLead WP3 GO #6319783437 and Architect shared-admin disposition
https://github.com/ZaurNavi/CaptivePortal/issues/295#issuecomment-6321505786 .
No service User/Group change, no case change to `Admin`, no new credential,
daemon, socket, signature, capture or authorization authority.

Sensor uses the SAME WP2 directory, process identity, seven metadata probes,
atomic report,4096-byte cap,60-second telemetry tick and180-second TTL. Explicit
`captivprod.ops.sensor-metadata.v2` adds closed `application_health`; unchanged
v1 shape cannot contain that key. The upgraded consumer accepts each exact
version explicitly; it projects metadata into the unchanged Operations v1 DTO.
V1-only exporters remain valid (health UNKNOWN). Upgrade Portal reader before
Sensor publisher in an eventual authorized rollout; an old binary reader rejects
new v2 rather than accepting unknown fields. No implicit schema relaxation.

Sensor `ready` is eligible for HEALTHY only with explicit preflight, available
DHCP/TCP and TLS/QUIC source statuses, recent Suricata heartbeat, delivery without
permanent fault, unblocked spool and no stop request. These are existing runtime
fields, not another metrics/SQLite/Controller probe. `degraded`/`unavailable`
remain native limitations/failure; initializing/stopping or incomplete ready
dependencies stay UNKNOWN. A regular metadata artifact is NOT this proof.

NI02B retains the existing **shared admin UID** with Portal. The fixed disposable
artifact is `/run/captiveportal-operations/ni02b/health.json`:

| Resource | Future owner/mode | Contract |
| --- | --- | --- |
| Existing Operations parent | root:root0755, tmpfs | Same secure ancestry/no symlink policy |
| `ni02b` child | existing admin,0700 | Writable/readable within the approved shared identity |
| `health.json`/exclusive temporary | admin,0600, one regular link,<=4096bytes | Atomic, no fsync or persistent history |

**Provenance=`source_self_reported_shared_uid`. NOT independently_authenticated.**
The file cannot prove NI02B-exclusive authorship against another admin-UID
process. PID/start/boot/epoch correlation and schema/age checks do not change
that fact. This explicitly accepted trust is for informational display ONLY;
it is forbidden as an authorization, mutation, security-attestation or automatic
recovery input. No group/DB ownership migration or Portal privilege widening.

NI02B uses its existing run-loop update boundary, rate-limited to at most one
attempt60seconds, including failures. Source/commit confirmation is observed
after already successful poll/commit; pending count is captured from the existing
retry-counter calculation. The report never adds a queue/SQL/source read.
`usable` requires recent source success<=30seconds, confirmed current-run writer
commit<=180seconds, Registry/attribution dependencies and a known recent zero
pending count. Unknown count is NOT zero. Native attribution_unavailable plus
confirmed positive pending count is DEGRADED/pending_attribution even while the
process is RUNNING. Existing failure events invalidate ready evidence until a
later source success. Other native degraded/unavailable states remain explicit;
missing/stale prerequisites never manufacture HEALTHY.

Both protocols validate exact fields, enum/type/range, canonical UTC, process
start/boot, epoch/sequence and clock ages. Source evidence and snapshot/cache age
are independent. Invalid newer data cannot erase a confirmed degradation in the
same still-running producer generation: the last valid failure ages to STALE at
its ORIGINAL expiry. Green is never retained on an invalid replacement. Restart,
missing identity or unreadable proc evidence is UNKNOWN. No freshness extension
from the30-second cache or15-second browser refresh.

`GET/HEAD /admin/api/v2/operations/db-services` is the closed versioned
`admin.operations.db-services.v2` projection. V1 remains compatible. Same global
capability and startup flag,401/403/404 before sampling, no mutation endpoint,
48KiB cap and one sampler. V2 includes health source/observed/received time,
age/TTL/reason; all stores remain `not_attested`, no new SQLite checks. Journal
is separately typed and never added to the V1 main+WAL+SHM sum. The frontend
selects V2 and falls back once to V1 only on unsupported404, not401/403/503.
It keeps the four tiles,9/17 rows,31/45 structural graph, safe DOM fields and
15-second visible-only schedule. No extra browser polling loop.

Future SysAdmin/Owner admission must provision only these exact tmpfs children,
allow narrowly additive write access under the EXISTING Sensor/NI02B sandbox,
and explicitly supply the same startup flag to each enabled optional publisher.
No production command was executed by Coder. NI02B unit identities and Sensor
raw-group restrictions remain unchanged. Real systemd/proc/sandbox parity,
broader security/regression/browser/performance and deployment remain HOLD for
independent acceptance. WP4 SQLite attestation is DEFERRED.
