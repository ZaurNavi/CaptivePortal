# CaptivPortal — DB-SERVICES-01
## Chief Architect Architecture Contract v1 — Admin Web / Databases & Services

**Date:** 2026-10-17 (Asia/Baku)  
**Request:** Owner + Web Design Tech Lead / `DB-SERVICES-01`  
**Decision:** **`MODIFY → ARCHITECTURE_ACCEPTED; IMPLEMENTATION_ADMISSION_CONDITIONAL`**  
**Nature:** binding architecture/semantics decision, **not** Coder TASK, PR/merge permission, production action or systemd/DB mutation.  
**Scope:** deployment-global, authenticated, read-only operational inventory for CaptivPortal.  
**Exact reviewed repository HEAD:** `c6db833952d8daabb8fccedb03a774f9277850b6`, PR #221 merge.  
**Exact verified commit TREE:** `a9ea6dbf7a19a843e34882ba68f70c8ff2b67d92`. HEAD corroborated with connected GitHub commit listing and pinned source reads; TREE independently corroborated against public GitHub Git Commit API `git/commits/c6db833952d8daabb8fccedb03a774f9277850b6`, which reports this exact `tree.sha`. Tech Lead shall independently re-check tree from its local worktree before Coder admission.
**Boundary:** GitHub source inventory ≠ deployed production state, installed unit manifests, effective env, live process code identity or filesystem existence.

### 0. Executive resolution — decisions A1…A18

| Question | Frozen decision |
|---|---|
| A1: Service identity | Only explicit CaptivPortal-owned **independently supervised** service units; in-process workers appear as DB *component owners*, not duplicate Service rows. |
| A2: DB identity | All catalogued CaptivPortal-owned durable **SQLite logical stores**, plus Sensor spool; no logs, lockfiles, backup copies or arbitrary discovered files. |
| A3: Inventory authority | **One versioned resolved inventory** = immutable source-controlled catalog + explicitly attested operator deployment bindings. No implicit auto-discovery. |
| A4: Service read | **One bounded batched** `systemctl show` read-only subprocess over exact allowlisted unit names; server-side sample/cache. No sudo, mutation or whole-system enumeration. |
| A5: Expected state | Manifest explicit intent `run / disabled / maintenance / unknown`; `systemctl enabled` and file existence are diagnostic, not expectation. |
| A6: DB state | Closed DB state machine below; `stat exists` proves `present_unverified`, never `available/healthy`. |
| A7: SQLite probe | **None in page sampler**: no `sqlite3.connect`, `PRAGMA`, tables, schema, checkpoint, quick_check, writers, DB opens. Startup/maintenance attestations only if separately sourced and fresh. |
| A8: Footprint | `main_file_bytes + wal_bytes + shm_bytes`, existing regular files only, excludes other artifacts; partial sizes explicitly unknown. |
| A9: Ownership | Catalog `writer_owner_component_id`, optionally `writer_service_id`, bounded `reader_service_ids[]`; single writer-owner authority, many readers allowed. |
| A10: Paths | Browser receives stable ID, human label, safe basename/unit, **not absolute paths** or environment. |
| A11: Authorization | New exclusive GLOBAL capability **`admin.read.operations`**, explicitly granted, not reused from Settings/site permissions. |
| A12: API | **One** `GET /admin/api/v1/operations/db-services`, schema `admin.operations.db-services.v1`; one safe bounded snapshot. |
| A13: Refresh | Browser every **15 s** while visible + manual refresh; one server sampler at most every **30 s**; item-level sample age, stale beyond **90 s**. |
| A14: Partial failure | Independent per-item `unknown/stale/unavailable`; trusted sibling objects remain; no false total or old-green. |
| A15: Problems | Only positively supported `degraded/failed/unavailable/incompatible/unexpected_running`; `unknown/stale` separately tallied, not silently healthy. |
| A16: Flag | `WEB_ADMIN_DB_SERVICES_ENABLED` exact `true/false`, default **false**, startup-only; not Admin Settings-editable. |
| A17: Persistent store | **NO** new DB, log history, on-disk cache or migrations; operator startup manifest is *configuration*, not storage of runtime observations. |
| A18: Background service | **NO** new systemd unit/daemon. One bounded in-process on-demand sampling worker; no periodic timer when page unused. |

---

### 1. Source review, confidence and production evidence boundary

At pinned `main@c6db833...`, checked:
- `run.py`, `app/config.py`, `app/settings.py`, `app/admin_web/{config,runtime,routes,policy,capabilities,read_gateway}.py` and `app/admin_web/templates/admin/base.html`.
- `app/{portal_counter,public_traffic,visitor_registry,visit_lifecycle,observations,current_state,traffic_projection}/...` writer/config owners.
- `app/device_fingerprint/{config,cli,classification_persistence,control_plane_store}.py`, `app/device_fingerprint_integration/{config,cli,runtime,repository}.py`.
- `app/{network_metadata,network_attribution,network_metadata_projection,network_service_recognition}/...`, `app/device_fingerprint_sensor/{config,spool}.py`.
- `deploy/device-fingerprint/{fingerprint-sensor,fingerprint-suricata,fingerprint-classification}.service`, `deploy/network-metadata-projection/network-metadata-projection.service`, `deploy/network-service-recognition/network-service-recognition.service`.
- `docs/project-inventory.md` **only as a source index**, not an authoritative live/current snapshot; it retains October 14 context.

Source-verified *logical identities* below are sufficiently supported to freeze the **recognized V1 catalog**. This does NOT prove their installed service/unit name, runtime enablement, effective DB path, expected mode, version, current schema integrity or loaded process SHA on production. These require the finite **G0 Read-only Deployment Binding Attestation**, section 25, **before an implementation TASK is marked pre-code GO**.

No claim is made that `captive-portal-edge-bridge.service` (seen in a separate operational transcript) is repo-owned. It is **outside the recognized nine until SysAdmin supplies evidence of CaptivPortal ownership, independent supervision and approved V1 enrollment**; the catalog is not silently expanded from that historical mention.

### 2. Canonical Service inventory v1 — exactly nine registered identities

| Stable ID | Unit identifier | Label / primary role | Repo authority | Expected value |
|---|---|---|---|---|
| `portal_core` | `captive-portal.service` | CaptivPortal Core, Guest Auth/CAPPORT/Admin and in-process workers | `run.py` / runtime identity / deployment docs | operator-attested |
| `fingerprint_evidence` | `fingerprint-evidence.service` | Direct-TLS Fingerprint Evidence ingress/writer | `app/device_fingerprint/cli.py` | operator-attested |
| `fingerprint_sensor` | `fingerprint-sensor.service` | AF_PACKET sensor, durable spool, NI-02A attribution | `app/device_fingerprint_sensor/{config,cli,spool}.py`, deploy template | operator-attested |
| `fingerprint_suricata` | `fingerprint-suricata.service` | Suricata EVE/TLS/QUIC capture | deploy template, NI EVE producer | operator-attested |
| `fingerprint_classification` | `fingerprint-classification.service` | Post-auth fingerprint integration/classification worker | deploy template → `app/device_fingerprint_integration/cli.py` | operator-attested |
| `network_metadata` | `network-metadata.service` | NI-01 durable EVE ingestion | `app/network_metadata/cli.py` / NI docs | operator-attested |
| `network_metadata_projection` | `network-metadata-projection.service` | NI-02B derived projection/late binding | deploy template / CLI | operator-attested |
| `network_service_recognition` | `network-service-recognition.service` | NI-04 background materialized intelligence | deploy template / CLI | operator-attested |
| `traffic_projection` | `traffic-projection.service` | Derived traffic history projection worker | `app/traffic_projection/cli.py` and deployment docs | operator-attested |

Not additional Service rows: Visit reader/reconciler, Registry writer, Observation, Current State, Public Traffic, Pending Cleaner, Analytics, Portal Counter, Sensor-local network attribution, Admin Web and integration submitter in Core. They appear via their real hosting unit/component owner. No process or systemd wildcard enumeration. No Omada Controller, PRTG, NPM, MicroK8s, Grafana/Loki, host journald, host filesystem or unrelated services.

The current Git repository contains unit **templates** for some identities, not all nine; only the deployment attestation may certify installed definitions, overrides and startup expectations.

### 3. Canonical SQLite/store inventory v1 — exactly seventeen recognized logical stores

`path_key` denotes an operator-resolved effective path, not a browser-visible path.

| Stable ID | Default safe basename | Authoritative writer owner / hosting service | Character / role | Source path authority |
|---|---|---|---|---|
| `portal_counter` | `portal_counter.db` | Portal Counter / `portal_core` | Durable authorization counter | `app/config.py`, `app/portal_counter/repository.py` |
| `public_traffic` | `public_traffic.sqlite3` | Public Traffic / `portal_core` | Completed-session traffic | `app/config.py`, `app/public_traffic` |
| `visitor_registry` | `visitor_registry.sqlite3` | Visitor Registry / `portal_core` | Authoritative device/identity registry | `app/visitor_registry/registry_config.py` |
| `visits` | `visits.sqlite3` | Visit Lifecycle / `portal_core` | Authoritative visit/open-close/offline facts/checkpoint | `app/visit_lifecycle/config.py` |
| `observations` | `observations.sqlite3` | Observation Foundation / `portal_core` | Authoritative historical client/AP observations | `app/observations/config.py` |
| `current_state` | `current_state.sqlite3` | Current State / `portal_core` | Current and recent materialized snapshots | `app/current_state/config.py` |
| `traffic_projection` | `traffic_projection.sqlite3` | Traffic Projection / `traffic_projection` | Derived/replayable traffic projection | `app/traffic_projection/config.py` |
| `fingerprint_evidence` | `device_fingerprint_evidence.sqlite3` | Evidence foundation / `fingerprint_evidence` | Durable normalized evidence/source health | `app/device_fingerprint/config.py` |
| `fingerprint_classification` | `device_fingerprint_classification.sqlite3` | Fingerprint Classification / `fingerprint_classification` | Persisted classification output/history | `app/device_fingerprint/classification_persistence.py`, `app/config.py` |
| `fingerprint_control_plane` | `device_fingerprint_control_plane.sqlite3` | Fingerprint control-plane/configuration owner; **no automatic unit writer attribution** | Admission/activation/lineage; protected state | `app/device_fingerprint/control_plane_store.py`, `app/config.py` |
| `fingerprint_integration` | `device_fingerprint_integration.sqlite3` | Integration submitter in Core + worker in `fingerprint_classification` | Durable post-auth jobs/identity links; **shared authorized write ownership** | `app/device_fingerprint_integration/{runtime,repository}.py` |
| `network_metadata` | `network_metadata.sqlite3` | NI-01 / `network_metadata` | Durable EVE ingestion/checkpoint | `app/network_metadata/config.py` |
| `network_attribution` | `network_attribution.sqlite3` | NI-02A Sensor-local writer / `fingerprint_sensor` | Trusted DHCP attribution and lookup | `app/network_attribution/{models,config}.py` |
| `network_metadata_projection` | `network_metadata_projection.sqlite3` | NI-02B / `network_metadata_projection` | Derived projection/pending late identity | `app/network_metadata_projection/{models,config}.py` |
| `network_service_intelligence` | `network_service_intelligence.sqlite3` | NI-04 / `network_service_recognition` | Materialized recognized services | `app/network_service_recognition/materialization_config.py` |
| `settings` | `settings.sqlite3` | Settings Control bootstrap/runtime / `portal_core` | Durable global configuration generations, protected admin control | `app/settings_control/{bootstrap,repository}.py`, `app/config.py` |
| `sensor_spool` | `spool.sqlite3` | Fingerprint Sensor / `fingerprint_sensor` | **Authoritative durable delivery spool**, not a derived cache | `app/device_fingerprint_sensor/config.py`, `spool.py` |

**Special DB-owner resolutions:**
- `fingerprint_integration` has **two authorized writer contexts**: Portal enqueues and separate worker claims/commits. Catalog must expose `writer_owner_component_ids[]`; do not incorrectly claim exclusive unit ownership.
- `fingerprint_control_plane` must not be represented as auto-written by the classifier just because it reads admission/activation. Source lineage/privileged config owner separately attested.
- `network_attribution` generic code default is under `/opt/CaptivePortal/data`, whereas an earlier verified deployment manifest describes `/var/lib/captive-portal/fingerprint-sensor/network_attribution.sqlite3`. This is **an effective-path discrepancy to resolve in G0**, not a reason to select either as current truth.
- Sensor `spool.sqlite3` default is `/var/lib/captive-portal/fingerprint-sensor/spool.sqlite3`, outside the main data directory.
- `settings.sqlite3` can be enabled/disabled independently of Admin operations page; never open the control-plane DB to compute UI status.
- Existing Writer/Settings integration may use more than one process; no new unique DB writer ownership is created here.

Excluded even if named like a database: `*-wal`, `*-shm` (size components, not logical DB rows); `*-journal`, `.lock`, `.writer.lock`, backup/archive `.sqlite3`, recovery copies, raw/normalized webhook JSONL, `auth_telemetry.log`, Loki storage, PRTG DB, Omada Controller storage, external NAS databases, runtime sockets and temporary files.

### 4. Identity, ownership and versioned registry (one selected model)

Choose **`DB_SERVICES_INVENTORY_V1 = STATIC_CODE_CATALOG ⨝ VERIFIED_DEPLOYMENT_BINDINGS`**; joined records are the *only* canonical V1 inventory. Neither input is an alternate fallback inventory.

**Code catalog:** exact 9 and 17 IDs, order, unit allowlist, safe names, roles, writer-component-to-unit relationships, default path *hints*, allowed feature dependencies, criticality and schema contract hints. Versioned with code, reviewable. Registration is explicit; optional objects remain listed with `disabled/not_provisioned/unknown` as appropriate.

**Deployment bindings:** a small (max **32 KiB**) **privileged operator-managed startup JSON** at fixed trusted location `/etc/captiveportal/admin-db-services-v1.json`, or a location fixed by SysAdmin approved packaging; exact final path is frozen above for V1. No UI editing, no GET of file content, no import from uncontrolled env dumps. Contains only enumerated service IDs with `intent` `run|disabled|maintenance|unknown`, and exact enumerated DB IDs with absolute effective `path`, `intent` `expected|optional_disabled|unknown`, and optional maintenance-attestation references (digest/status/timestamp only). Optional per-item `reason_code` must come from a closed safe enum. Does **not** contain tokens, credentials, arbitrary unit lists, DB SQL, script paths, shell arguments or extra entries. Must match catalog IDs and unique paths; no arbitrary additions. A full inventory entry is required for all IDs. The operator attests effective auxiliary service env paths separately, without showing secret values.

Startup reads/validates once with symlink-safe regular-file check, strict JSON schema/length, file-owner/mode/parent trust verification, canonical absolute path and approved realpath roots; reject `..`, control chars, duplicate JSON keys and unknown fields. Path resolution must not create or open SQLite files. Only operator-attested paths that match the service writer's effective deployment configuration are admitted. Code defaults alone never overwrite operator values. If invalid/missing manifest and feature ON: disable only Operations sampler, surface safe `operations_unavailable`, keep Auth running.

There is **no** auto-discovery via globbing, `systemctl list-units`, `/proc` scan, SQL metadata discovery, service env dump, `systemctl cat` on every request, or directory crawler. When modules are added, a reviewed catalog/schema change and new operator binding are required; never silently inherit unknown stores.

### 5. Scope and authentication

GLOBAL one-deployment surface, independent of selected Omada Site. UI path: `GET /admin/db-services`; title `Databases & Services`; nav text `DB & Services`. Site selectors MUST NOT filter or duplicate this inventory. Future Multi-Site operates on the same host-level resources until a separate cluster/fleet architecture exists.

Add explicit capability `admin.read.operations` to the **global** allowlist and grant parser in `app/admin_web/capabilities.py` and `policy.authorize_global()`. It is **not** granted by default to every Site viewer and **not** inferred from `admin.read.settings.*` or site read capabilities. Operator must opt into `WEB_ADMIN_GLOBAL_CAPABILITIES` through approved startup deployment configuration; keep existing grants unchanged. Exact global grant parser bounds/strictness continue to apply; revise only as necessary to accommodate one token without relaxing checks.

Authenticated Admin session + `platform_operator` + capability + feature enabled are required for both page and JSON; errors before any sample. Existing cookie, HTTPS, CSP, no-store, auth rate/session rules unchanged. Unauthorized = **403**, unauthenticated = existing session boundary, feature OFF = **404**. No Site ID supplied or accepted. Never expose an unauthenticated health endpoint for this feature.

### 6. Service authority and closed states

**Selected mechanism:** one asynchronous, bounded read-only `systemctl show` invocation per sampler cycle with **constant** argv:
`systemctl --no-pager show --property=Id,LoadState,ActiveState,SubState,MainPID,NRestarts,ExecMainStartTimestamp,UnitFileState <nine literal allowlisted unit names>`.
Implementation uses `subprocess.run([...], shell=False, capture_output=True, timeout=0.75, check=False, env=sanitized_minimal)`; max stdout **16 KiB**, max stderr **1 KiB**, bounded parse; if output cannot be bounded *during* acquisition, use bounded `Popen` read/terminate and reap rather than unbounded `capture_output`. No sudo/D-Bus mutation/polkit/command-string construction. `systemctl show` may use systemd read D-Bus internally; no new Python D-Bus dependency. Mock parity test on **target systemd 249** required: multi-unit output delimiting and property availability, no unit-name confusion. Effective `UnitFileState` shown only as secondary diagnostic, never sole source of expected state.

**State fields** `operational_state`, `application_health`, `expected_mode`, `evidence_at_utc`, `state_reason`, `sample_stale` (with separate `ActiveState`/`SubState` safe strings). `operational_state` exactly:
- `running`: required unit loaded+active and usable MainPID/started-at evidence; **process state only**, not proof of functioning application.
- `degraded`: positively observed active process with known application-health degraded/fault OR unexpected active while declared disabled/maintenance.
- `failed`: systemd `ActiveState=failed` for expected `run`.
- `stopped`: expected `run`, loaded but inactive; diagnosed distinct from `failed`.
- `disabled`: explicitly `intent=disabled`/`maintenance`, not running. Maintenance distinguished in `expected_mode`.
- `unknown`: systemd probe or intent/fields unreliable or missing; never green.
- `stale`: last successful state evidence older than 90 seconds or stale sample after failed source refresh; never old-green.
If expected=`run` but LoadState `not-found`: `operational_state=failed` with `reason=unit_unavailable` (verified absent unit, not inferred from missing sample). `main_pid` is null for non-running. Uptime/start timestamp null if not trustworthy; `uptime_seconds` derived only from positive, coherent start instant. `n_restarts` nullable, integer only when systemd reports it; not a historical incident counter. `application_health` enum `healthy|degraded|unavailable|unknown|stale`, **default unknown** unless an existing module-owned fresh state signal explicitly attests it. `systemd active` never makes `application_health=healthy`.

No manipulation of `ActiveState` if stopped on operator-declared maintenance; unknown expectation remains unknown rather than red. All reasons safe coded: `systemd_unavailable`, `unit_unavailable`, `not_running`, `maintenance`, `unexpected_running`, `application_degraded`, `sample_stale`, `source_unattested`.

### 7. Database authority and closed states

**Selected read:** `os.lstat`/equivalent safe metadata on exactly the 17 operator-resolved **main file paths**, plus exact `-wal`/`-shm` siblings; zero SQLite connections or SQL calls. Lstat only regular existing files; symlinks (including dangling), nonregular files, untrusted roots and permission errors are `unavailable` or `unknown` with safe reason; **never follow arbitrary symlinks**. Values may be race-inconsistent because writer changes WAL during stat; report a bounded observed **physical footprint estimate**, not an atomic SQLite snapshot.

DB `operational_state` enum:
- `disabled`: deployment explicitly declares optional store disabled (including old leftover file). Footprint may still be counted if verified present; do not call it current healthy.
- `not_provisioned`: optional declared not provisioned **and** main file proven absent; not an error.
- `present_unverified`: main file proven regular through accessible metadata with known size; no fresh writer/schema/integrity attestation. **Default for file-present DB with no other health authority**; neutral, not green.
- `available`: main file present **and** current, authoritative module-owned positive store/writer health proof, and no contradictory active fault, with a currently valid separately attested compatibility/integrity status if asserted. `lstat` alone cannot emit `available`.
- `degraded`: verified module fault or degraded contract while store still meaningful; attach safe reason.
- `unavailable`: expected store absent, inaccessible, nonregular, or verified writer/store unavailable.
- `incompatible`: explicit **recent** owner-generated schema/incompatibility attestation; never derived from basename/guessed PRAGMA.
- `unknown`: ambiguous/missing configuration, unknown effective path/owner/attestation or failed sampler.
- `stale`: once-trusted health observation older than allowed age; previous green never carried forward as green.

Closed auxiliary fields: `file_presence=present|absent|unknown`, `size_evidence=sampled|partial|unknown`, `health_evidence=runtime_attested|maintenance_attested|none`, `health_checked_at_utc|null`, `reason_code` from closed safe values (e.g. `file_missing`, `nonregular_file`, `stat_unavailable`, `owner_unavailable`, `schema_incompatible`, `not_attested`, `sample_stale`, `configured_disabled`). Do not infer `unavailable` from parent service failure alone when DB survives and read owner still healthy: service state and DB state are separate facts. If required writer is failed, it may establish DB `degraded`/`unavailable` **only where its owning module contract explicitly says so**, otherwise DB remains `present_unverified` with `writer_service_state` reference.

**No `sqlite3.connect(mode=ro)`, immutable SQLite URI, `user_version`, `quick_check`, `integrity_check`, `PRAGMA`, `SELECT sqlite_master`, schema sniff, row count, WAL checkpoint, opening source DB or transient lock** in normal page sampling. Even `mode=ro` can lock/read under HDD pressure; deliberate prohibition chosen for V1. Existing startup/maintenance integrity attestation is displayed only with exact source/time/version and cannot be regenerated by the page. `schema_expected_version` is a code-contract label; `schema_observed_version` must be `null` absent a trusted attestation. Never label expected == observed.

### 8. Storage footprint and counting

Per store:
- `main_file_bytes = st_size(main)` if existing regular file, `0` if **proven absent regardless of expected mode** (state remains `unavailable` if expected); else `null` if unknown.
- `wal_bytes = st_size(main+"-wal")` if existing regular sidecar; `0` when proven absent; `null` when untrustworthy.
- `shm_bytes = st_size(main+"-shm")` likewise.
- `total_footprint_bytes = main+wal+shm` **iff all three components are reliable nonnegative integers**, otherwise `null`.
- `wal_present/shm_present` describe presence, not journal mode. Absence does **not** certify WAL disabled, no pending writes or durability.
- Exclude `-journal`, temporary SQLite files, lock/writer-lock files, backups, archived generations, swap files, journals/logs of other systems, duplicate aliases and memory overhead. Sidecars are **part of** store, not extra store rows.
- File lstat values are apparent bytes (`st_size`), **not allocated disk blocks/`du`**, sparse-file or full-volume consumption. UI label: **"DB storage footprint (file lengths)"**, not disk usage/capacity.
- Main absent but stray sidecars present: do **not** claim a healthy DB; flag `orphan_sidecar_possible` and show measured sidecars where safe, do not delete.
- Explicit duplicate underlying storage paths/inodes between registered logical DBs are catalog/attestation error, **not double-counted**. Treat affected entries `unknown`, storage sum `partial`.
- At most one file-state sample per path per cycle; path resolution/permissions checked at startup; no per-request directory listing.

**Summary DB storage** = sum of known, nonduplicated `total_footprint_bytes` across all registered stores (including historical files for disabled entries), with `storage_coverage=complete|partial|unknown`. If any included total unknown, present known subtotal + `total_complete=false`, never imply it is full total; UI must show "known subtotal" until complete.

### 9. Ownership relationship contract

Catalog shape for each DB:
```json
{
  "store_id": "visits",
  "writer_owner_component_ids": ["visit_lifecycle"],
  "writer_service_ids": ["portal_core"],
  "reader_service_ids": ["portal_core"],
  "store_kind": "authoritative",
  "purpose": "Visits, offline evidence and durable reader checkpoint"
}
```
`store_kind` closed `authoritative|derived|durable_queue|configuration|operational_counter|materialized_snapshot`. No claim of rebuildability unless established by module; Sensor spool is `durable_queue`, Settings `configuration`, Traffic Projection `derived`, NI-04 `materialized_snapshot`. `writer_owner_component_ids[]` can have **multiple approved components** (`fingerprint_integration`), while ownership metadata is still from catalog, not from filenames. Cross-unit readers and writer control-plane ownership shown explicitly. No on-page discovery or enforcement of SQLite writer privilege; this feature only reports the mapped contract.

### 10. API and serialized contract

- UI: `GET /admin/db-services`.
- **Only snapshot endpoint**: `GET /admin/api/v1/operations/db-services`.
- API/schema: `admin.operations.db-services.v1`.
- Request: no query string, no request body, no arbitrary selectors/site/path/unit parameters. Only GET; other methods standard 405.
- Response `200` for full or trustworthy partial snapshot; `503` if sampler/manifest totally unavailable and no trustworthy item evidence; errors sanitized. No response over **48,000 UTF-8 bytes**. `Cache-Control: no-store`, existing Admin security/CSP/session headers.
- DTO exact top-level keys:
```json
{
  "api_version": "admin.operations.db-services.v1",
  "request_id": "<existing safe request uuid>",
  "scope": "global",
  "snapshot_state": "complete",
  "generated_at_utc": "2026-10-17T10:00:00Z",
  "sampling_started_at_utc": "2026-10-17T09:59:59Z",
  "sampling_completed_at_utc": "2026-10-17T10:00:00Z",
  "freshness_seconds": 0,
  "sample_status": "fresh",
  "summary": {
    "services": {"registered": 9, "expected_running": 0, "running": 0, "degraded": 0,
                 "failed": 0, "stopped": 0, "disabled": 0, "unknown_or_stale": 9},
    "databases": {"registered": 17, "available": 0, "present_unverified": 0,
                  "disabled": 0, "not_provisioned": 0, "degraded": 0,
                  "unavailable": 0, "incompatible": 0, "unknown_or_stale": 17},
    "storage": {"known_footprint_bytes": 0, "total_complete": false,
                "unknown_store_count": 17, "coverage": "partial"},
    "problems": {"established": 0, "unknown_or_stale": 26}
  },
  "services": [],
  "databases": [],
  "partial_failures": []
}
```
**Numbers in the example above are purely illustration of schema**, never an actual deployment state or fabricated measurement. In a real non-error response, arrays must contain all **registered** entries in catalog order, with per-item truthful states. Top-level counts derive **only** from current item DTOs using backend rules.

Service row exact required keys: `id,label,unit,role,expected_mode,operational_state,application_health,active_state,sub_state,main_pid,n_restarts,started_at_utc,uptime_seconds,sampled_at_utc,reason_code` (nullable facts explicitly `null`; no raw errors).
DB row exact required keys: `id,label,filename,purpose,writer_owner_component_ids,writer_service_ids,reader_service_ids,store_kind,expected_mode,operational_state,file_presence,main_file_bytes,wal_bytes,shm_bytes,total_footprint_bytes,schema_expected_version,schema_observed_version,health_evidence,health_checked_at_utc,sampled_at_utc,reason_code`.
Error entry `{"source":"service_state|db_stat|inventory","id":"<known-id-or-null>","code":"<closed-safe-code>"}`; maximum **32** entries (no paths/exception text). `generated_at` is HTTP snapshot assembly time, **not underlying collection time**.
`partial_failures` may be nonempty while HTTP=200. `snapshot_state` `complete|partial|unavailable` and `sample_status` `fresh|stale|unavailable`; freshness derived from underlying oldest relevant sample, not just newest HTTP response time. No split per-row endpoints.

### 11. Backend composition, cache and lifecycle

Feature OFF → no sampler, no `/etc` inventory reads, no new subprocess, no file stats, no component startup overhead.

Feature ON + authorized access:
1. Compose `AdminOperationsReadService` within existing `captive-portal.service` Admin runtime. No new daemon/unit or database.
2. At Admin composition read and validate privileged deployment manifest once; do not re-read on every GET or hot-load Settings mutations. Invalid manifest makes **only this feature** unavailable (fail-open to Guest Auth).
3. On first authorized snapshot read, schedule a single on-demand sampling job in a private **one-worker** bounded executor; no periodic thread wakeup when unused, no free-running polling.
4. Reuse one immutable cached snapshot for **30 seconds** minimum even for manual refresh. Concurrent GETs coalesce onto the same job; no queue of pending samples, no overlapping `systemctl` processes, no separate sample per visitor/tab.
5. Sampling: at most one fixed allowlist `systemctl show` read and three `lstat`s per admitted store (max 9 units/17 stores current; cap 32 services/48 stores), strict stdout/stderr bounds and subprocess deadline <=0.75 s; bounded FS metadata stage, target <=1.0 s. Overall sample budget **2.0 s** as a circuit-breaker; blocked OS filesystem syscalls cannot be forcibly interrupted, so **never spawn replacements if an old worker is stuck**.
6. HTTP wait on a pending job at most **250 ms**. If no first trustworthy snapshot, return safe 503 `snapshot_pending|operations_unavailable`, not block Auth. A partial snapshot may be used if it has independently valid items. No spinning retry/recursion.
7. If a sample fails, throttle new attempts to 30 s. Cache ages continue increasing, transition to `stale` at age >**90 s**, then neutral/unavailable; never carry a previous green as freshly healthy.
8. Close private executor on Admin shutdown with bounded nonblocking discipline; never extend Core graceful Visit/Auth shutdown ordering or hold Auth while joining stalled sampler. No supervisor/process-level policy modification.

HTTP browser refresh **15 s while visible**, stopped while tab hidden, one in-flight request only; manual Refresh calls same endpoint and **does not bypass** backend TTL. UI shows `Updated N sec ago` from **sampling_completed_at_utc** and separately labels stale/unavailable. In-process time comparison uses monotonic clock; UTC timestamps are display/attestation. No data persisted between restarts; warm-up state is unknown/snapshot_pending, never an old green.

**Security/performance cap:** 32 registered services, 48 registered stores, one sampling worker, 0 queued jobs, ≤1 subprocess per sample, maximum 3×48 main/sidecar lstat candidates, 48 KB response, 32 partial failures, 30-s minimum resample, 90-s freshness limit, 250-ms HTTP wait, no SQLite connections. Tech Lead may propose **stricter** limits in implementation if load evidence requires, not looser without architectural review.

### 12. Dashboard semantics and colors

- **Services**: `running / expected_running` numerator/denominator; denominator includes `intent=run`, including stopped/failed/stale/unknown, not `disabled|maintenance|unknown`. Report explicitly `expected_running` and count of incomplete states. Running means **unit active**, not Auth semantic ready.
- **Databases**: report `available / registered` *verified* and separately `present_unverified`, disabled/not_provisioned and unknown. Never label file-present as healthy.
- **DB Storage**: known sum and coverage. Disabled DB files count physically if present; optional unprovisioned files contribute proven 0. Duplicate paths and missing values produce `partial` coverage.
- **Problems**: count *established actionable* `degraded/failed/stopped when expected run/unavailable/incompatible/unexpected_running`; **unknown/stale counted separately**, not claimed zero problems. Deduplicate one affected object once even if several reasons.
- Backend calculates summaries; frontend has no implicit state inference or count reclassification. Status **text mandatory** and semantic color: green only positively verified, yellow degraded, red verified failure, gray unknown/stale/disabled/present_unverified. `running` with `application_health=unknown` may use a process-running indicator, **not** a green "system healthy".
- No giant card per DB; dense rows on desktop, stacked secondary data on mobile, no horizontal overflow. No history charts or alerting.

### 13. Errors and isolation

- Manifest invalid/missing, global auth failure, collector unavailable or oversize: safe API error `{"api_version": "...", "request_id": "...", "error":{"code":"operations_unavailable|snapshot_pending|feature_disabled|operations_forbidden|invalid_request","details":[]}}`; codes never contain paths/SQL/errors. Existing Admin authentication error handling remains.
- Single unit show property malformed: that service `unknown`, others trustworthy if parser can isolate; if whole subprocess fails: all service rows unknown/stale, **DB stat data retained independently**.
- One DB inaccessible: that DB unknown/unavailable, other DB stats retained; storage known subtotal, not false total.
- Observed file disappearing/rotating while stat: mark item unknown/partial; no retry loop scanning directory.
- No supplier: do not reclassify old positive attestation as healthy; stale after 90 s.
- Exceptions caught at the Admin Operations boundary. Failure may disable page/read model but **must not fail Guest Auth/Omada/CAPPORT**, existing Admin pages or unrelated workers.

### 14. Security/privacy, no-write invariant

- Browser sees only safe basename (`filename`), unit name, bounded human label, PID/restart and numerical sizes when authenticated with explicit global capability. Never send absolute paths, user/group, UID, raw process arguments, environment variables, service unit file bodies, socket filenames, controller identifiers, secrets, secret names/values, SQLite exception or traceback, timestamps correlated to user identity, arbitrary source path or DB file bytes.
- Strict no directory iteration/glob, no any shell execution from untrusted input, no sudo/polkit, no D-Bus method that changes units, no `systemctl start|stop|restart|reload|enable|disable|kill`, no Python `sqlite3` connection in Operations page.
- The sampler never mutates any DB, sidecar, writer lock, checkpoint, WAL, spool, Settings store, source-health, file permissions, systemd/service state, env or pending queues. No explicit `PRAGMA quick_check` or implicit SQLite open that could cause locks.
- `lstat` failures and symlinks do **not** trigger repair/unlink/chmod. No `stat` over user-supplied paths: target resolved exclusively from privileged catalog+manifest.
- Only minimum bounded operational event telemetry: feature startup ready/unavailable, sample failure/slow/partial and sample age threshold transitions with rate limiting/aggregates; avoid per-refresh INFO spam and names of confidential filesystem paths. No new journald small-I/O source.

### 15. Feature/default-off and deployment

Code-owned startup `WEB_ADMIN_DB_SERVICES_ENABLED` = exact lowercase `true|false`, default `false`. Enabled state gated by `WEB_ADMIN_ENABLED` and Admin authentication plus `admin.read.operations`. It is **not** added to Admin-writable Settings feature list or DB; startup env only, no hot reload, no implicit enabling after merge. Invalid value fail-closed for Operations (not fatal to Auth), logged by safe error category.

When OFF: nav absent, HTML/API both 404, no collector. When ON but missing explicit global grant: nav absent, routes 403 (or existing authenticated-vs-unauthenticated boundary), never leak inventory. When ON but manifest broken: nav available to authorized operator with honest unavailable error; never guess defaults to turn it green. Production activation = separately authorized operator manifest, explicit permission grant and env flag + controlled restart, all Owner/SysAdmin GO; Git merge alone does nothing.

### 16. Multi-Site compatibility

The deployment-level Host inventory remains **GLOBAL**, independent of Site selection and accepts no `site_id`. Multi-Site future may share one DB and service or many logical site partitions, but DB row describes **file/store** and writer service, not a Site-specific health promise. Never multiply storage footprint by Site count or infer Site from filename. Multi-host/fleet monitoring remains outside V1.

### 17. Observability and performance

Baseline and post-change measurements owned by Tech Lead: authenticated UI 15s repeated requests (1, 5, 20 tabs); subprocess spawn rate; `lstat` calls, sampling cache hit %, p50/p95/timeout, snapshot age; `captive-portal.service` cgroup I/O/CPU; journald log volume; hypervisor `/dev/sda` physical completed IOPS/await/busy in comparable quiet windows. Cannot infer host physical IOPS from guest logical reads or sample size. No unfounded percent savings. Test very slow HDD, unavailable systemd bus, missing DB and stalled lstat. Ensure no measurable Auth latency regression or increased durable writes from feature telemetry.

### 18. Exact acceptance matrix — Tech Lead owns independent gates

| Gate | Deterministic PASS criterion |
|---|---|
| `DS-G0` — source/deployment parity | GitHub pinned HEAD/TREE, 9/17 catalog evidence, operator-reviewed actual installed units/drop-ins and effective DB paths/feature intent; collision and cross-root cases resolved without secrets; Tech Lead `git rev-parse` TREE independently attested before code. |
| `DS-G1` — catalog security | Exactly registered IDs, bounds 32/48, reject duplicate/unknown/untrusted manifest values, symlink/relative/traversal/secret cases, no dynamic discovery. |
| `DS-G2` — Global access | Unauthenticated/session expired; feature OFF; grant absent; grant present; allowed Sites/no Site all tested; no read performed before auth. `admin.read.operations` independent of Settings and Site rights. |
| `DS-G3` — systemd parity | One batched fixed unit `systemctl show` on systemd 249, reliable property separation, regular/failed/not-found/disabled/maintenance, no command injection, subprocess timeout/overflow; no mutation. |
| `DS-G4` — DB stat/size | Present/absent WAL/SHM, missing main, nonregular/symlink/dangling, permission failure, rapid WAL change, orphan sidecars, duplicate paths; precise total/partial storage; **0 SQLite opens**. |
| `DS-G5` — state and freshness | Closed enums, expected-vs-actual, every current/source age and null, old green → stale after 90 s, process-active ≠ application healthy, present ≠ database healthy. |
| `DS-G6` — caching and concurrency | 15s UI refresh does not multiply samples; manual refresh respects 30s; 20 tabs at most 1 worker/1 subprocess per sample and 0 queued; 250ms HTTP wait; 2s circuit breaker; missing/hung source doesn't spawn more. |
| `DS-G7` — partial failure | One broken service or DB yields useful sibling rows, no fabricated healthy/size, top-level summary partial and coverage flags, 48k response cap. |
| `DS-G8` — SSR/isolation | Guest Auth/Omada/CAPPORT unchanged, existing Visit/Auth graceful lifecycle and all currently accepted DB/replay/durability invariants unchanged; no new unit or DB. |
| `DS-G9` — Admin UX | New top-level nav only with enable/grant, GLOBAL URL, accessible compact rows and status text, busy/empty/stale/manual refresh, mobile layout; no new JS framework. |
| `DS-G10` — full regressions | Tech Lead independently runs applicable full Windows/Linux, security and performance gates on exact candidate TREE; Coder only focused scope tests; no unauthorized skips/xfail or reuse of unrelated release exceptions. |
| `DS-G11` — production gate | Owner separately signs off manifest, grant, feature flag and restart; read-only pre/post checks, matched HDD/CPU, safe rollback and actual Auth E2E on approved Owner device. Merge alone = no activation. |

**Negative gate:** Coder must not solve missing DB health proof by adding request-time `quick_check`, `PRAGMA`, SQL schema scans or full table checks; must not solve source inventory gaps by directory/systemd enumeration; must not turn old-green data into fresh-green.

### 19. Rollback

Flag OFF + controlled restart (separate Owner GO) restores previous Admin page behavior; new endpoint/nav disabled and sampler not composed. Operator manifest/grant are retained only as operator-protected configuration and can be reverted to their versioned backup. No DB schema, service or capture changes to undo. If collector contributes quiet HDD I/O or Auth latency, stop activation rather than weakening DB durability. A failed readiness/integrity attestation is **not** remedied by deleting a store.

### 20. Coder and responsibility boundaries

**Chief Architect** owns this semantic contract and scope amendments. **Web Design Tech Lead** finalizes visual-only layout against enums/DTO. **Project Tech Lead** verifies G0 and prepares **one exact Coder TASK** with pinned base SHA/TREE, source-specific path allowlist, negative tests, release policy and immutable baseline. **Coder** builds in isolated worktree, performs focused tests only; full Windows/Linux/Security/PERF are **Tech Lead-owned**. SysAdmin/Owner attests runtime config, installed units and controls production rollout.

Implementation may touch only the bounded Admin Web runtime/config/policy/capabilities/routes/template/JS/CSS; new **`app/admin_web/operations_inventory.py` / `operations_service.py`** pure-read modules, startup settings plumbing (`app/config.py`, `app/settings.py` where strictly necessary), focused `tests/admin_web/` and docs. Final exact file allowlist must be frozen by Tech Lead **before** Coder GO. No DB repositories, Omada, Auth, fingerprint capture/NI data plane, migrations, service templates, SSR-01 systemd dependencies, operator `/etc` edits, Git publication or production restart under this contract.

Potential mandatory UI low-level change: `base.html` currently implements a binary `global_settings_page` branch; introduce an explicit **`global_operations_page`** path rather than treating operations as a Site or as Settings. No bypass of per-Site routes.

### 21. Non-goals (binding)

Generic Linux monitor; CPU/RAM/SMART, temperatures, network interfaces, process list, filesystem explorer, uptime history, time series, Grafana/Loki access, ad hoc arbitrary `systemctl` or SQL, service start/stop/restart, DB migration/VACUUM/checkpoint/quick_check/repair, backup/restore, Settings mutation, tenant/site-specific DB health, multi-host aggregation, user alerts/notifications, Omada Controller redesign, data-plane optimizations or new runtime background daemon.

### 22. Explicit research blockers / open P0, P1, P2

**P0 — mandatory before Tech Lead Coder implementation GO:**
1. `DS-P0-01` **Operator source attestation:** produce secret-safe static inventory of all 9 installed service units (+ effective drop-ins, independent-vs-in-process classification) and all 17 effective DB paths/intent. Confirm actual `network_attribution` path and Sensor spool; confirm whether external `captive-portal-edge-bridge` is CaptivPortal-owned and needs a later explicit enrollment. Owner-authorized read-only only; no production modification.
2. `DS-P0-02` **Pre-code re-pin:** GitHub API TREE identity is already verified by Chief Architect. Tech Lead must *additionally* locally verify `git rev-parse HEAD^{tree}` equals the accepted tree for `c6db833...` and re-check current `main` before implementation; if newer main, material-impact diff review.
3. `DS-P0-03` **systemd show compatibility:** systemd 249 compatible batched fixed-argv parser, property semantics and user permissions. If not supported without sudo or requires new privileged helper, return to Architect; do not improvise.
4. `DS-P0-04` **Manifest security feasibility:** SysAdmin confirms trusted path, ownership/perms, allowed DB roots, and that manifest effective path/intent facts can be attested against each independent unit without exposing secrets. No reliance on current documentation or default values as runtime authority.
5. `DS-P0-05` **Compatibility of expected/observed health:** identify which existing module-owned health attestations actually expose trustworthy current health; modules without such proof MUST remain `present_unverified`/`application_health=unknown` and must not be falsely marked green.

**P1 — required by Tech Lead before acceptance/publication:** threat-model manifest poisoning, output parsing overflows, concurrent requests/hung metadata syscalls, mixed stale/cache timeline, oversize response, separate Windows mocked and target Linux/systemd gated tests, external frontend/consumer UX accessibility.

**P2 — explicitly postponed:** supporting additional independently supervised `edge-bridge` if separately source-attested; last attested schema versions in a dedicated nonrequest time-bound artifact; historical DB size charts, true disk block allocation, multi-host, health correlation and service control.

### 23. Final disposition

```text
TASK=DB-SERVICES-01
ARCHITECTURE_CONTRACT=V1_FINAL
ARCHITECT_VERDICT=MODIFY_ACCEPT
SOURCE_HEAD=c6db833952d8daabb8fccedb03a774f9277850b6
SOURCE_TREE_REPORTED=a9ea6dbf7a19a843e34882ba68f70c8ff2b67d92
TREE_INDEPENDENT_VERIFICATION=GITHUB_COMMIT_API_CONFIRMED
SOURCE_RECOGNIZED_SERVICES=9
SOURCE_RECOGNIZED_STORES=17
LIVE_DEPLOYMENT_BINDINGS=UNATTESTED
INVENTORY_MODEL=CODE_CATALOG_JOIN_OPERATOR_BINDINGS
SERVICE_READ=BATCHED_READONLY_SYSTEMCTL_SHOW_CACHED
DB_READ=FIXED_PATH_LSTAT_ONLY_NO_SQLITE_OPEN
GLOBAL_CAPABILITY=admin.read.operations
FEATURE_FLAG=WEB_ADMIN_DB_SERVICES_ENABLED_DEFAULT_FALSE
API=GET_/admin/api/v1/operations/db-services
SCHEMA=admin.operations.db-services.v1
CODER_TASK_PREPARATION=YES_AFTER_G0_REVIEW
CODER_IMPLEMENTATION_GO=HOLD_UNTIL_TECH_LEAD_TASK_AND_P0_PASS
GIT_PUBLICATION=NO
OWNER_MERGE=HOLD
PRODUCTION_CHANGE=NO
```

**End — Chief Architect Contract v1.**
