# Issue #298 — existing owner startup results

Status: repository implementation / independent acceptance pending. This is NOT
a production provisioning, restart or deployment instruction. Authority: Issue
#298 Architect6323729806, Tech Lead6323948610. Baseline main6ba82f6.

## No verification work added

The initializer bodies and their SQL remain unchanged. A small in-memory wrapper
records a normal result, known validation failure, or unknown startup refusal.
Existing NI02/NI04/Attribution validators are invoked through an observational
call wrapper so their sanitized exceptions still produce a truthful FAILED.
No additional SQLite connect/query, transaction, PRAGMA, checkpoint, fsync or
application DB write is performed for reporting. Existing enabled components
still perform their normal existing initialization/migration as before.

Reporting failure cannot change the owner's initialize result or original
exception. On failure the completed scope is conservatively empty; no partial
subcheck success is invented. A process restart/fork cannot inherit another
process's check. The bounded context holds at most the17 registered store IDs.

## Exact source mapping

| Store | Owner / existing initialize | Reported successful scope |
|---|---|---|
| portal_counter | Portal / PortalCounterRepository.migrate | NOT_ATTESTED: upper-bound/bootstrap is not an exact verification gate |
| public_traffic | Portal / PublicTrafficRepository.migrate | NOT_ATTESTED: bootstrap/column handling only |
| visitor_registry | Portal / VisitorRegistryRepository.initialize | schema_version, schema_signature, quick_check; no startup FK/full audit claim |
| visits | Portal / VisitRepository.initialize | schema_version, schema_signature, quick_check, foreign_key_check after startup/migration branch |
| observations | Portal / ObservationRepository.initialize | schema_version, schema_signature only; runtime health quick/FK is separate |
| current_state | Portal / CurrentStateRepository.initialize | existing file: schema_version, schema_signature, quick_check; fresh creation: not_run, NOT_ATTESTED |
| traffic_projection | traffic-projection / TrafficProjectionRepository.initialize | schema_version, schema_signature, quick_check, foreign_key_check |
| fingerprint_evidence | fingerprint-evidence / DeviceFingerprintRepository.initialize | schema_version, schema_signature only, no startup quick_check |
| fingerprint_classification | classification / DeviceFingerprintClassificationStore.initialize | NOT_ATTESTED: bootstrap only |
| fingerprint_control_plane | classification dependency / DeviceFingerprintControlPlaneStore.initialize | NOT_ATTESTED: no corresponding verified startup result |
| fingerprint_integration | Portal / IntegrationRepository.initialize | schema_version, integration_jobs column signature only; Portal is the single report authority |
| network_metadata | NI01 / NetworkMetadataRepository.initialize | schema_version, schema_signature only; foreign_keys=ON is NOT a FK check |
| network_attribution | Sensor / NetworkAttributionRepository.initialize | schema_version, schema_signature, quick_check, foreign_key_check |
| network_metadata_projection | NI02B / ProjectionRepository.initialize | schema_version, schema_signature, quick_check, foreign_key_check |
| network_service_intelligence | NI04 / ServiceMaterializationRepository.initialize | schema_version, schema_signature, quick_check, foreign_key_check |
| settings | Portal / SettingsRepository.initialize, enabled bootstrap only | schema_version, schema_signature, quick_check, foreign_key_check; optional_disabled intent -> N/A |
| sensor_spool | Sensor / SensorSpool.initialize | schema_version, quick_check only; no exact signature/full integrity claim |

This matrix is eligible executed scope, not a declaration that thirteen or all
seventeen production DBs currently have fresh reports. No `integrity_check` is
attested: separate offline/full-audit methods are not run by this feature.
The integration repository can be initialized by classification too, but that
process is not an authoritative exporter of the Portal-owned integration check.

## Channels and versioning

- Portal-owned checks stay in the same process; no report file or new writer.
- Sensor: SAME `/run/captiveportal-operations/sensor/metadata.json`, new explicit
  `captivprod.ops.sensor-metadata.v3`, retaining exact v1/v2 admission. V3 adds
  only `store_checks`; existing metadata probes supply current opaque identities,
  not additional raw DB access. Existing60-second publisher/180-second TTL,
  4096-byte cap, Sensor-only writer UID and reader-only group are unchanged.
- NI02B: SAME `/run/captiveportal-operations/ni02b/health.json`, explicit
  `captivprod.ops.ni02b-health.v2`, retaining exact v1 admission. Its existing
  publisher adds cached checks and one bounded owner main-file lstat for identity
  at its existing cadence. NO extra pending/attribution/source SQL. Trust remains
  **source_self_reported_shared_uid**, informational only, not independently
  authenticated.
- Other admitted processes use `captivprod.ops.owner-startup-check.v1`, one
  startup-only `startup-checks.json` in the corresponding child below. No new
  run loop, timer, service, socket or persistent history is created. Sequence and
  original check time change only if initialization actually runs again.

| Unit | Future fixed child under /run/captiveportal-operations |
|---|---|
| fingerprint-evidence.service | evidence |
| network-metadata.service | ni01 |
| network-service-recognition.service | ni04 |
| traffic-projection.service | traffic-projection |

Each new child must be separately Owner/SysAdmin-approved root-provisioned tmpfs,
with root-owned non-writable/no-symlink parent ancestry, existing admin owner0700
child, and owner0600 single-link regular report/temporary file <=4096 bytes.
The current code admits only that shared-admin channel; if the real unit uses a
different UID or sandbox, it remains unavailable pending a separately reviewed
disposition, never an implicit User/Group change. Confirm actual UID/sandbox/proc
access before enabling. The implementation does NOT create directories/groups,
grant rights, edit units, change permissions or install configuration.

The SAME existing `WEB_ADMIN_DB_SERVICES_ENABLED=true` gates optional reports;
there is no new feature flag. Existing Sensor provisioning and raw-storage
isolation rules in operations-sensor-metadata-295.md continue to apply. Do not
grant Portal raw Sensor group membership/traversal to improve display coverage.

Every transport validates closed version/fields/IDs, original UTC check time,
boot/PID/start ticks, process epoch, sequence, dual clock ages, stable atomic file
read and owner/mode/tmpfs. The check's file identity is an opaque hash of regular
main-file device/inode, not a hash/read of database contents. The Admin reuses its
existing lstat sample to compare non-Sensor files. For Sensor it uses only the
owner-exported identity; absence/unreadable/identity collision cannot yield PASS.
Metadata identity is NOT proof against in-place data mutation or a compromised
trusted/shared-UID process; historical scope/time is always displayed explicitly.

## UI/API semantics and rollout boundary

Only the existing authenticated global v2 DB & Services view gains check fields;
v1 is unchanged. Same9 services/17 DBs/31 nodes/45 edges/four tiles,48,000-byte
budget,30-second shared sampler and15-second visible-only browser refresh.
Source check records/opaque IDs/private paths never cross the public API. File
presence/size, application health, and historical check are separate axes.

A current report of historical PASS does not imply a new check, continuous
integrity or currently healthy application. Report TTL and sampler age are
independently enforced in cached responses. Stopped/restarted/unbound producer,
changed file, malformed report or rollback/replay never retains a current PASS.
Previously checked time/scope can remain labelled STALE. One-shot reports become
STALE after180seconds if no new existing initialization occurred; there is no
heartbeat added to make them fresh. Disabled Settings uses authoritative
optional_disabled inventory intent; missing/unknown intent is not guessed.

Future authorized deployment must upgrade consumers/UI before producers, because
old strict readers reject new report keys/versions by design. Rollback needs no
application DB/schema/data change; old binaries may show unknown for new report
versions until the owner regenerates an old-compatible report or an independently
approved operational procedure handles tmpfs. No cleanup, restart, provisioning,
production mutation or release action is authorized by this document.

Independent Tech Lead/RQA owns real systemd/sandbox parity, release/full gates and
deployment admission. Coder tests are isolated synthetic/focused only.
