# Issue298 Phase B — Classification provisioning requirement

Status: **LAB implementation / SysAdmin design handoff, NOT provisioning or deployment GO**.
Task: APPHEALTH-B-01 v2, comment 6365226105. Base:
`1b44caca7bf333dfe6891cf2380b6169002b2bd7`.

## Read-only source findings

`deploy/device-fingerprint/fingerprint-classification.service` runs the existing
Integration Worker as **User=admin / Group=admin** with `ProtectSystem=strict`,
`NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectHome=true` and only
`ReadWritePaths=/opt/CaptivePortal/data`. There is no Classification Operations
child in the historical startup-report channel allowlist. Do not repurpose the
Evidence, NI01, NI04 or Sensor directories for this independent process.

Phase B admits exactly `/run/captiveportal-operations/classification/app-health.json`
through the SAME secure `Channel` primitive. The producer never provisions,
chmods, widens privileges or falls back to a data-directory report. Missing or
read-only provisioning makes publication fail open and Admin honestly UNKNOWN;
it does not make the worker fail or fabricate a successful report.

## Separate bounded SysAdmin / Owner prerequisite

After code acceptance and separate Owner GO, review the standard root-managed
tmpfs provisioning mechanism and add only this exact child. Required invariants:

| Object | Owner | Mode / constraint |
|---|---|---|
| `/run` and parent ancestry | root, not group/other writable | Real no-symlink directories, tmpfs |
| `/run/captiveportal-operations` | root:root | 0755; preserve all existing channel boundaries |
| `classification` child | existing admin:admin | 0700, real directory on the same tmpfs |
| `app-health.json` and atomic temporary regular file | admin:admin | 0600, one hard link, at most4096 bytes |

A root-managed tmpfiles rule for this child (rather than application mkdir) is
the narrow proposed provisioning path. Preserve root ownership of the parent;
do NOT recursively chown it, grant world access or use a RuntimeDirectory setup
that hands the parent tree to admin. Ensure the child exists before creating the
unit's sandbox. The separately reviewed unit change must permit writes to
**only** `/run/captiveportal-operations/classification` in addition to its existing
data path, retaining all other restrictions. Do not make all `/run` writable or
bind-mount a single report inode, since reports are atomically replaced.

Portal already uses the same admin UID: this is informational shared-UID trust,
NOT an independently authenticated writer boundary. Confirm effective UID/GID,
umask compatible with0600, parent mount/ACL/no-symlink properties, sandbox views,
and existing `/proc/<MainPID>/stat` plus boot-id readability. No raw Sensor DB
permissions, capabilities, user/group rename, credentials or service registration
are requested. The existing `WEB_ADMIN_DB_SERVICES_ENABLED` startup flag controls
optional publication; no second feature flag is introduced.

**No provisioning commands, unit edits, production reads, restart or activation
were performed by Coder.** Record actual installation evidence and then verify
current boot/PID/start identity, report cadence and negative permissions under
separate deployment approval. Traffic reuses its existing approved channel;
Suricata has no publisher/channel and Core has no persistent report.

## Phase B visibility and rollback notes

Traffic aggregation uses only cached outcomes for the owner's complete current
version/site set, including build targets. Native statuses are refreshed by the
existing5s observer; cache evidence older than its existing55s heartbeat is no
longer positive proof. Native `stale` is a known degraded state; a stale cached
observation is unknown. File reports retain the existing180s TTL. No additional
health observations, SQL or background thread is introduced.

Core reads completed in-process wiring and existing authorization snapshots.
Only recent authorization failures within the existing Operations180s evidence
window contribute a partial degradation, with original observation time retained.
Older failure history is not a permanent outage. The tracker covers configured
tracked sites, so failures do not claim global Omada E2E failure. Critical missing
Web/Auth wiring is unavailable; enabled missing CAPPORT/Admin routes are degraded.
Disabled CAPPORT, optional data workers and idle authorization do not imply outage.

Rollback is source-only reversal of Phase B publisher/projection mappings; four
rows return to UNKNOWN. Phase A / Sensor / NI02, startup checks, DB schemas,
durability and native worker semantics remain untouched. Provisioning/deployment,
publication, merge and activation require separate approvals.
