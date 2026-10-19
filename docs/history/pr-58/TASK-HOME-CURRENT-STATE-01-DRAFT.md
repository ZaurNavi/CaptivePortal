# TASK-HOME-CURRENT-STATE-01 — Current Network State Foundation — DRAFT

**Project:** CaptivPortal  
**Parent product concept:** `TASK-HOME-01 — Admin Console Home v1`  
**Type:** architecture / preparatory implementation specification  
**Status:** `DRAFT FOR TECH LEAD REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Production activation:** separate owner-controlled step  
**Architecture baseline:** `main@e43bead3028e45981012c4f540200bf3d9754cac`  
**Prepared:** 2026-08-23

---

## 1. Purpose

Create a separate Site-aware **Current Network State Foundation** that prepares authoritative near-real-time client/AP state for the future Admin Console Home.

The layer is required because the current historical Client Observation contract intentionally stores only:

```text
wireless = true
active = true
authStatus = 2
SSID in configured Observation allowlist
```

Therefore current Observation Storage cannot truthfully answer:

```text
Online Now
Authorized Now
Waiting Authorization
Other / Unknown auth state
Online Devices
Devices by AP — Now
```

Current Network State must collect and persist a bounded current-state snapshot for **all active wireless clients in the configured Home SSID scope**, including non-authorized states.

The layer also keeps a short bounded history of these snapshots so the later `HOME-AP-24H-01` increment can calculate Avg / Peak / Unique without introducing another acquisition path.

This TASK is backend/acquisition/read-foundation only. It does **not** implement the new Home UI.

---

## 2. Product outcomes enabled

After this foundation is implemented and separately activated, later Home tasks must be able to build:

```text
Online Now
Authorized Now
Waiting Authorization
Other / Unknown
Devices by AP — Now
Online Devices table
Access Points Now
Devices by AP — 24h
```

without:

```text
browser → Omada
Admin route → Omada
Home → Loki/Grafana
Home → raw log parsing
Home → growing Observation history scan
```

Traffic, Today and product-health remain separate follow-on increments.

---

## 3. Verified baseline

At baseline:

```text
main = e43bead3028e45981012c4f540200bf3d9754cac
```

### 3.1 Existing full client inventory primitive

The shared `OmadaProvider` already exposes:

```text
list_observation_clients(site_id, page, page_size, timeout_seconds)
```

It reads:

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/clients
```

and already provides shared token-cache use, token-expiry recovery, HTTP + Omada `errorCode` validation, page bounds, `totalRows` validation and safe copied response data.

The provider returns the full controller client page. Filtering to `authStatus=2` occurs later in the existing Observation worker.

**Decision:** reuse this validated provider primitive. Do not create a second Omada client HTTP implementation.

### 3.2 Existing Client Observation semantics

Current `classify_client()` accepts only:

```text
wireless is True
active is True
authStatus == 2
SSID is allowed
```

`authStatus=1` is intentionally excluded from historical Client Observation.

**Decision:** keep this contract unchanged.

### 3.3 Existing AP inventory primitive

The shared provider already exposes:

```text
list_observation_access_points(site_id, page, page_size, timeout_seconds)
```

using:

```text
GET /openapi/v1/{omadacId}/sites/{siteId}/devices
```

Current AP Observation uses the inventory mainly to resolve AP identities and does not persist inventory `status` as authoritative AP online/offline state.

### 3.4 Existing AP rates

Historical AP Observation already persists counter-delta rates such as:

```text
wired_download_mbps
wired_upload_mbps
wired_download_rate_reason
wired_upload_rate_reason
```

**Decision:** Current State does not duplicate AP rate calculations. `HOME-TRAFFIC-01` later composes AP identity/status from Current State with rates from Observation.

---

## 4. Architecture decision

Create independent package and persistence owner:

```text
app/current_state/
```

with dedicated DB:

```text
/opt/CaptivePortal/data/current_state.sqlite3
```

Canonical flow:

```text
                         shared OmadaProvider
                         shared OAuth/token cache
                                 │
                  ┌──────────────┴──────────────┐
                  │                             │
         Current Client Collector      Current AP Collector
                  │                             │
                  └──────────────┬──────────────┘
                                 │
                        current_state.sqlite3
                                 │
                       CurrentStateReadService
                                 │
                  future AdminQueryService bridge
                                 │
                      future Home Admin API
```

Existing historical flow remains separate:

```text
Omada → authorized-only Observation → observations.sqlite3 → Analytics
```

---

## 5. Permanent invariants

### 5.1 Home does not collect

```text
Home/Admin API = reader
Current State workers = collectors
```

No HTTP request may call Omada to fill current-state gaps.

### 5.2 Observation meaning does not change

Do not silently redefine Client Observation from authorized history to all-client current state.

### 5.3 One logical client snapshot

All related live client facts exposed together must share one exact:

```text
client_cycle_id
```

Forbidden:

```text
Online from cycle A
Authorized from cycle B
Pending from cycle C
Devices by AP from cycle D
```

### 5.4 Count invariants

For one complete normalized snapshot:

```text
online_count
=
authorized_count
+ pending_count
+ other_count
+ unknown_count
```

and:

```text
online_count
=
sum(non-null AP buckets)
+ ap_unknown_count
```

### 5.5 Missing is not zero

```text
stale != 0
unavailable != 0
unknown auth != pending
missing AP != offline
missing RSSI/SNR != 0
```

### 5.6 No reconstructed state

Do not reconstruct current clients from Visit/Registry/Observation history. Do not infer AP offline from missing detailed AP observation.

---

## 6. Data Acquisition / Analytics Boundary

Permanent boundary:

```text
Current State collectors
→ obtain/persist near-real-time facts

CurrentStateReadService
→ reads persisted facts

Analytics
→ may consume short history only through reviewed read contracts

Admin/Home
→ reads application/read services
```

Current State must not calculate Visit Analytics, customer cohorts, repair Observation, mutate Registry/Visit/Observation, or call Omada on behalf of HTTP requests.

Short history exists only for bounded operational windows such as future AP 24h distribution. It is not the long-term Wireless Analytics authority.

---

## 7. Home network scope

`Online` must not silently mean the whole Omada Site.

v1 scope:

```text
Site ID
+
configured portal-managed SSID allowlist
```

Expected production scope is the production Home Site and `Zefer_Parki`, but production identifiers/SSID values are not hardcoded in runtime code.

Every client snapshot persists its exact source scope.

---

## 8. Future Multi-Site Compatibility

Current model remains:

```text
Site-aware
single-tenant
```

Mandatory:

- canonical `site_id` on every cycle/row;
- no cross-Site snapshot;
- no cross-Site MAC matching;
- no hidden default Site in repository/read methods;
- no tenant_id;
- Tenant != Site;
- reuse one shared OmadaProvider/token lifecycle.

Snapshot scope is persisted so future per-Site SSID mapping can be introduced without changing historical meaning.

---

## 9. Product / Observability Boundary

Product-safe future facts:

```text
current online/auth counts
client current context
AP current inventory state
freshness/completeness
short AP/client distribution history
```

Operational-only telemetry:

```text
request/page count
poll duration
failure category
storage errors
duplicate/malformed counts
cleanup/retention pressure
```

Home never uses Loki/Grafana/log files as a product data source.

---

## 10. New package

Preferred:

```text
app/current_state/
├── __init__.py
├── config.py
├── models.py
├── normalizer.py
├── repository.py
├── read_service.py
├── client_worker.py
├── ap_worker.py
├── cleanup.py
├── runtime.py
└── telemetry.py
```

Minimal consolidation is allowed if responsibilities remain clear.

---

## 11. Configuration

Through existing pipeline only:

```text
app/config.py → app/settings.py:get_settings() → CurrentStateConfig
```

Proposed repository-safe defaults:

```text
CURRENT_STATE_ENABLED=false
CURRENT_STATE_DB_PATH=/opt/CaptivePortal/data/current_state.sqlite3

CURRENT_STATE_SITE_IDS=
CURRENT_STATE_CLIENT_SSIDS=

CURRENT_STATE_CLIENT_INITIAL_DELAY_SECONDS=10
CURRENT_STATE_CLIENT_INTERVAL_SECONDS=30

CURRENT_STATE_AP_INITIAL_DELAY_SECONDS=15
CURRENT_STATE_AP_INTERVAL_SECONDS=30

CURRENT_STATE_REQUEST_TIMEOUT_SECONDS=5

CURRENT_STATE_CLIENT_PAGE_SIZE=500
CURRENT_STATE_CLIENT_MAX_PAGES=20
CURRENT_STATE_CLIENT_MAX_ROWS=10000

CURRENT_STATE_AP_PAGE_SIZE=100
CURRENT_STATE_AP_MAX_PAGES=10
CURRENT_STATE_AP_MAX_ROWS=500

CURRENT_STATE_CLIENT_FRESH_MAX_AGE_SECONDS=60
CURRENT_STATE_CLIENT_STALE_MAX_AGE_SECONDS=180
CURRENT_STATE_AP_FRESH_MAX_AGE_SECONDS=90
CURRENT_STATE_AP_STALE_MAX_AGE_SECONDS=300

CURRENT_STATE_HISTORY_RETENTION_HOURS=48
CURRENT_STATE_HISTORY_MAX_CLIENT_ROWS=5000000

CURRENT_STATE_CLEANUP_INITIAL_DELAY_SECONDS=300
CURRENT_STATE_CLEANUP_INTERVAL_SECONDS=3600
CURRENT_STATE_CLEANUP_BATCH_SIZE=5000

CURRENT_STATE_SQLITE_BUSY_TIMEOUT_MS=500
CURRENT_STATE_SHUTDOWN_TIMEOUT_SECONDS=20
```

These are DRAFT defaults for Tech Lead review, not approved production values.

---

## 12. Configuration validation

When enabled:

- non-empty Site IDs;
- exact lowercase `[0-9a-f]{24}` Site IDs;
- non-empty unique SSID allowlist;
- non-empty DB path.

Bounds:

```text
client interval:         10..300s
AP interval:             10..600s
request timeout:          1..30s
client page size:         1..500
client max pages:         1..100
client max rows:          1..50000
AP page size:             1..100
AP max pages:             1..100
AP max rows:              1..5000
fresh age > 0
stale age > fresh age
history retention:       24..168h
history max client rows: 100000..20000000
cleanup interval > 0
busy timeout:             0..5000ms
shutdown timeout:         1..120s
```

---

# PART A — CURRENT CLIENT STATE

## 13. Client acquisition source

Use existing:

```text
OmadaProvider.list_observation_clients(...)
```

Do not copy its HTTP/token logic.

No second provider. No second token cache.

A semantic alias may be added only if Tech Lead requires it; it must delegate to the existing implementation and not duplicate network logic.

---

## 14. Client cycle

Each Site poll creates one logical snapshot:

```text
client_cycle_id
site_id
SSID scope
started_at
finished_at
duration_ms
```

All pages from the poll belong to the same cycle.

Omada pagination is sequential, so the controller is not assumed to provide an atomic multi-page snapshot. The capture interval remains explicit in metadata.

---

## 15. Pagination completeness

Inventory is complete only when:

```text
all expected pages retrieved
AND totalRows stable across pages
AND len(all_rows) == totalRows
AND no page/row bound exceeded
```

No silent truncation.

Failure categories include:

```text
timeout
network_error
http_error
controller_error
token_error
malformed_response
inconsistent_total
row_limit
page_limit
shutdown
storage_error
```

---

## 16. Client eligibility

A Current State row is eligible when:

```text
wireless is True
active is True
ssid in CURRENT_STATE_CLIENT_SSIDS
```

Unlike historical Client Observation:

```text
authStatus does NOT decide eligibility
```

Therefore Current State stores safely identifiable active wireless in-scope clients for:

```text
PENDING
AUTHORIZED
other confirmed auth codes
unknown/missing auth code
```

Exclude wired, inactive and non-scoped SSID clients.

---

## 17. Identity safety

Canonical identity:

```text
site_id + canonical client MAC
```

Duplicate canonical MAC inside one cycle:

```text
exclude ambiguous identity
record duplicate count
complete=false
quality warning
```

A scope-relevant active wireless row with invalid/missing MAC:

```text
unidentified_client_count += 1
complete=false
```

Do not create synthetic device IDs.

---

## 18. Client allowlist fields

Minimum v1 persisted row:

```text
client_cycle_id
site_id
observed_at

client_mac
controller_client_id
name
hostname
device_type

ip
ssid

ap_name
ap_mac
radio_id
band
channel

rssi
snr
uptime_seconds

auth_status_code
auth_classification

traffic_down_bytes
traffic_up_bytes
traffic_total_bytes

active
wireless
```

NULL is allowed where source data is absent.

No raw controller JSON column.

---

## 19. Auth status contract

Persist a strict integer raw status when available.

Known project research:

```text
0 = CONNECTED
1 = PENDING
2 = AUTHORIZED
3 = AUTH-FREE
```

Product-safe classification:

```text
2 → authorized
1 → pending
0 → other
3 → other
other integer → other
missing/non-integer → unknown
```

Future Home collapses:

```text
other + unknown → Other / Unknown
```

Do not relabel `AUTH-FREE` as Captive Portal `AUTHORIZED`.

Unknown future integer codes remain raw evidence and are not given invented meanings.

---

## 20. Online count contract

For a complete snapshot:

```text
online_count = number of normalized in-scope rows
```

Derived from the same rows:

```text
authorized_count
pending_count
other_count
unknown_count
other_unknown_count
```

Required:

```text
online = authorized + pending + other + unknown
```

No second count source may be mixed into the same current picture.

---

## 21. Devices by AP — Now readiness

Group exact selected snapshot by:

```text
ap_mac
```

NULL AP becomes:

```text
AP unknown
```

Required on complete snapshot:

```text
online_count
=
sum(AP buckets)
+ ap_unknown_count
```

Never infer current AP from historical Registry/Visit/Observation.

---

## 22. Uptime semantics

Persist controller field as:

```text
uptime_seconds
```

Do not equate it with Visit duration.

Intended Home meaning:

```text
controller-reported current client association/session uptime
```

Before FINAL Home consumption, controlled live acceptance must confirm:

1. designated owner device connects;
2. uptime increases across snapshots;
3. approved reconnect/new association is performed;
4. reset/disappearance/restart behavior is observed;
5. result is documented.

Until confirmed, field remains neutrally documented as controller-reported client uptime.

---

## 23. Client traffic counters

Persist cumulative controller counters:

```text
traffic_down_bytes
traffic_up_bytes
```

They are not Mbps.

If both are valid non-negative INT64 values:

```text
traffic_total_bytes = down + up
```

If either is NULL or sum would overflow:

```text
traffic_total_bytes = NULL
```

and overflow adds a quality warning.

Intended later Home table meaning:

```text
Download / Upload / Total
= controller-reported cumulative bytes for current active client state/session
```

Controlled live acceptance must confirm reset/continuity behavior across reconnect/new association before FINAL Home labels this as session-consumed traffic.

Current State does not calculate per-client Mbps in this TASK.

---

## 24. RSSI/SNR/radio context

RSSI/SNR remain nullable facts.

```text
NULL RSSI != 0
NULL SNR != 0
```

Band is derived only from safely confirmed radio identity. Do not guess a missing radio solely from historical context.

---

# PART B — CURRENT AP STATE

## 25. AP acquisition source

Use existing:

```text
OmadaProvider.list_observation_access_points(...)
```

Filter only inventory rows with:

```text
type == "ap"
```

and strict canonical AP MAC.

No new detailed per-AP request is added merely to determine online state unless the inventory contract proves insufficient and architecture is amended.

---

## 26. AP snapshot

Each Site poll creates one independent logical AP snapshot:

```text
ap_cycle_id
site_id
started_at
finished_at
complete
```

AP and Client watermarks remain independent.

Future Home must not hide them behind one artificial `Updated` timestamp.

---

## 27. AP allowlist fields

Minimum:

```text
ap_cycle_id
site_id
observed_at

ap_mac
name
ip
model
firmware_version

status_code
status_classification

last_seen_ms
uptime_seconds
uptime_raw
```

Only safely validated allowlisted fields are persisted.

No raw inventory JSON.

---

## 28. AP status contract

Persist raw controller status when safely typed.

Product classification may use only meanings confirmed by:

```text
actual Controller Swagger/documentation
OR controlled verified project evidence
```

Enum:

```text
online
offline
other
unknown
```

If only `status=1 → online` is confirmed, all other unverified codes remain other/unknown rather than being called offline.

This is mandatory before trustworthy `AP Online X/Y` product output.

---

## 29. AP Online semantics

Future:

```text
AP total
= valid AP rows in selected AP snapshot
```

```text
AP Online
= count(status_classification == online)
```

Unknown/other remain separately representable.

Missing detailed historical AP Observation is never itself `OFFLINE`.

---

# PART C — CONSISTENCY / QUALITY

## 30. Common cycle metadata

Minimum:

```text
cycle_id
kind                  # client | ap
site_id
started_at
finished_at
complete
result
source_scope_json
source_rows_reported
items_seen
items_stored
items_skipped
unidentified_count
duplicate_identity_count
unknown_status_count
error_count
data_quality_warning_count
failure_category
duration_ms
created_at
```

Client source scope canonical JSON contains Site + SSID allowlist.

AP source scope contains Site.

---

## 31. Cycle results

```text
success
partial
failed
shutdown
```

`success` = complete acquisition + trustworthy normalized row set.

`partial` = some data exists but exact completeness cannot be guaranteed.

`failed` = no trustworthy snapshot produced.

`shutdown` = interrupted by application shutdown.

---

## 32. Atomic publication

Readers must never see half a snapshot.

Required pattern:

```text
bounded poll into memory
→ bounded normalization
→ one short SQLite transaction:
     insert cycle
     insert all normalized rows
→ commit
```

A failed attempt with no usable rows stores bounded failure metadata only; it must not publish an empty success snapshot.

---

## 33. Latest attempt vs latest usable snapshot

Read boundary distinguishes:

```text
latest attempt
latest usable snapshot
```

If newest attempt failed, previous usable snapshot may remain as last-known evidence but cannot be relabeled fresh simply because it exists.

A complete zero-client cycle is a valid usable snapshot with `online_count=0`.

---

## 34. Freshness contract

Every current read returns:

```text
evaluated_at
observed_at
age_seconds
freshness_status
complete
cycle_id
source_scope
latest_attempt_result
latest_attempt_at
```

Proposed Client thresholds:

```text
<=60s       fresh
>60..180s   stale
>180s       unavailable
```

Proposed AP thresholds:

```text
<=90s       fresh
>90..300s   stale
>300s       unavailable
```

Completeness is independent from freshness.

Examples:

```text
fresh + complete=false  = recent but partial
stale + complete=true   = last full snapshot is old
```

After unavailable threshold, last-known metadata may remain, but old rows must not be exposed as current values.

---

# PART D — PERSISTENCE

## 35. Database

```text
/opt/CaptivePortal/data/current_state.sqlite3
PRAGMA user_version = 1
```

Recommended:

```text
journal_mode=WAL
synchronous=NORMAL
foreign_keys=ON
busy_timeout=CURRENT_STATE_SQLITE_BUSY_TIMEOUT_MS
```

No cross-DB foreign keys.

---

## 36. Tables

Minimum:

```text
current_state_cycles
current_client_state
current_ap_state
```

No Analytics table. No Home presentation table. No business KPI table.

---

## 37. `current_state_cycles`

Conceptual schema:

```text
cycle_id TEXT PRIMARY KEY
kind TEXT NOT NULL
site_id TEXT NOT NULL
started_at TEXT NOT NULL
finished_at TEXT NOT NULL
complete INTEGER NOT NULL
result TEXT NOT NULL
source_scope_json TEXT NOT NULL
source_rows_reported INTEGER
items_seen INTEGER NOT NULL
items_stored INTEGER NOT NULL
items_skipped INTEGER NOT NULL
unidentified_count INTEGER NOT NULL
duplicate_identity_count INTEGER NOT NULL
unknown_status_count INTEGER NOT NULL
error_count INTEGER NOT NULL
data_quality_warning_count INTEGER NOT NULL
failure_category TEXT
duration_ms INTEGER NOT NULL
created_at TEXT NOT NULL
```

Use CHECK constraints for enums/bools/non-negative counts.

---

## 38. `current_client_state`

Conceptual schema:

```text
cycle_id TEXT NOT NULL
site_id TEXT NOT NULL
observed_at TEXT NOT NULL
client_mac TEXT NOT NULL
controller_client_id TEXT
name TEXT
hostname TEXT
device_type TEXT
ip TEXT
ssid TEXT
ap_name TEXT
ap_mac TEXT
radio_id INTEGER
band TEXT
channel INTEGER
rssi INTEGER
snr INTEGER
uptime_seconds INTEGER
auth_status_code INTEGER
auth_classification TEXT NOT NULL
traffic_down_bytes INTEGER
traffic_up_bytes INTEGER
traffic_total_bytes INTEGER
active INTEGER NOT NULL
wireless INTEGER NOT NULL
PRIMARY KEY(cycle_id, client_mac)
FOREIGN KEY(cycle_id) REFERENCES current_state_cycles(cycle_id) ON DELETE CASCADE
```

---

## 39. `current_ap_state`

Conceptual schema:

```text
cycle_id TEXT NOT NULL
site_id TEXT NOT NULL
observed_at TEXT NOT NULL
ap_mac TEXT NOT NULL
name TEXT
ip TEXT
model TEXT
firmware_version TEXT
status_code INTEGER
status_classification TEXT NOT NULL
last_seen_ms INTEGER
uptime_seconds INTEGER
uptime_raw TEXT
PRIMARY KEY(cycle_id, ap_mac)
FOREIGN KEY(cycle_id) REFERENCES current_state_cycles(cycle_id) ON DELETE CASCADE
```

Do not force AP inventory uptime into seconds if source format cannot be safely normalized.

---

## 40. Required indexes

At minimum:

```text
cycles: (kind, site_id, finished_at DESC)
client: (cycle_id, client_mac)
client: (cycle_id, auth_classification, client_mac)
client: (cycle_id, ap_mac, client_mac)
client: (cycle_id, uptime_seconds DESC, client_mac)
client: (cycle_id, traffic_total_bytes DESC, client_mac)
AP:     (cycle_id, ap_mac)
AP:     (cycle_id, status_classification, ap_mac)
```

Additional 24h index requires query-plan/benchmark evidence; do not add speculatively.

---

## 41. Short history retention

Purpose:

```text
future Devices by AP — 24h
recent capacity/trend verification
short current-state diagnostics
```

Default:

```text
48h
```

This is not long-term client history.

Cleanup is bounded/batched/fail-open and preserves at least the latest usable cycle for each `(kind, site_id)` even if older than retention.

No unbounded delete. No `VACUUM` in request path.

---

## 42. Hard storage cap

Default:

```text
CURRENT_STATE_HISTORY_MAX_CLIENT_ROWS=5,000,000
```

Cleanup removes whole oldest removable client cycles until under cap.

Never partially delete a retained cycle.

If pressure requires loss inside a future 24h analysis window:

```text
record retention_pressure
future 24h metric must report partial coverage
```

Latest usable current snapshot is preserved.

---

# PART E — READ SERVICE

## 43. Read-only boundary

Create:

```text
CurrentStateReadService
```

It is the only supported application read boundary for future Home integration.

It:

```text
does not call Omada
does not mutate storage
does not run migrations
```

Readonly connections:

```text
mode=ro
PRAGMA query_only=ON
```

---

## 44. Immutable read models

Conceptual:

```text
CurrentSnapshotMeta
CurrentClientSummary
CurrentClientRow
CurrentClientPage
CurrentApSummary
CurrentApRow
CurrentApPage
CurrentStateAvailability
```

No mutable `sqlite3.Row` or raw dict escapes.

---

## 45. Current client summary

Conceptual:

```python
get_current_client_summary(
    site_id,
    *,
    evaluated_at_utc=None,
)
```

Returns one exact cycle:

```text
snapshot metadata
online_count
authorized_count
pending_count
other_count
unknown_count
other_unknown_count
ap_unknown_count
devices_by_ap
```

If `complete=false`, counts may be returned as observed counts but must not be represented as exact complete inventory.

If unavailable, current values are unavailable; last-known metadata may remain.

---

## 46. Current client page

Conceptual:

```python
list_current_clients(
    site_id,
    *,
    cycle_id=None,
    limit=100,
    cursor=None,
    sort="traffic_total_desc",
    auth_classification=None,
    ap_mac=None,
)
```

If cycle omitted, resolve current usable snapshot and pin that cycle for the complete page sequence.

Cursor binding includes:

```text
site_id
cycle_id
sort
filters
```

Page 2 must not silently switch to a newer snapshot.

---

## 47. Pagination

No OFFSET.

Stable keyset pagination with `client_mac` tie-breaker.

Examples:

```text
traffic_total_bytes DESC, client_mac ASC
uptime_seconds DESC, client_mac ASC
client_mac ASC
```

NULL ordering must be explicit and deterministic.

---

## 48. Sort/filter allowlist

Prepare only Home-required sorts:

```text
client_mac
uptime
traffic_total
traffic_down
traffic_up
auth_status
ap
rssi
snr
```

Filters:

```text
auth classification
AP
SSID when multiple are configured
```

No arbitrary SQL column names or free-form ORDER BY.

A low-frequency sort may use a bounded single-snapshot scan if benchmarked safely, but it must never scan all 48h history to sort the current table.

---

## 49. Current AP summary

Conceptual:

```python
get_current_ap_summary(site_id, *, evaluated_at_utc=None)
```

Returns:

```text
snapshot metadata
ap_total
online_count
offline_count
other_count
unknown_count
```

Only confirmed classification semantics are used.

---

## 50. Current AP page

Conceptual:

```python
list_current_aps(site_id, *, cycle_id=None, limit=100, cursor=None)
```

Stable order:

```text
ap_mac ASC
```

No growing-history scan.

---

# PART F — FUTURE AP-24H READINESS

## 51. Required evidence

This TASK does not implement final `Devices by AP — 24h` product output.

It must retain enough complete-cycle evidence for later calculation of:

```text
Avg concurrent observed clients by AP
Peak concurrent observed clients by AP
Distinct client MAC identities seen by AP
```

Later `HOME-AP-24H-01` defines exact average/time weighting and UI semantics.

---

## 52. 24h quality readiness

Storage must allow later output of:

```text
from_utc
to_utc
complete_cycle_count
partial_cycle_count
failed_cycle_count
coverage
first_snapshot_at
last_snapshot_at
max_gap_seconds
retention_pressure
```

No silent `24h` label when only a shorter history is available.

---

# PART G — RUNTIME

## 53. Runtime composition

Current State receives the already-created shared provider.

Conceptually:

```text
create app
→ create shared OmadaProvider
→ existing source runtimes
→ Current State runtime
→ Admin Web runtime / server
```

Exact order may follow current `run.py` composition, but no second provider/token lifecycle is allowed.

---

## 54. Runtime state

```text
disabled
starting
active
degraded
unavailable
stopping
```

Client and AP collector states remain independently inspectable.

Example:

```text
client=active
ap=degraded
```

must be representable.

---

## 55. Scheduling

Client/AP workers use fixed-delay, non-overlapping cycles.

If a previous cycle is still running:

```text
do not queue/start another overlapping cycle
```

No unbounded missed-poll queue.

---

## 56. Failure isolation

Current State is fail-open relative to:

```text
Captive Portal
CAPPORT
AuthWorker
Snapshot/Registry/Visit
Observation
Analytics 02A
Admin login
```

Provider/storage errors only degrade Current State.

Invalid enabled Current State configuration must not break visitor authorization.

---

## 57. Shutdown

Use stop events and bounded joins.

No Flask `current_app` inside worker threads.

No worker continues DB writes after successful shutdown return.

---

# PART H — TELEMETRY

## 58. Events

Minimum:

```text
current_state.client_cycle_completed
current_state.client_cycle_partial
current_state.client_cycle_failed
current_state.ap_cycle_completed
current_state.ap_cycle_partial
current_state.ap_cycle_failed
current_state.storage_error
current_state.cleanup_completed
current_state.cleanup_failed
current_state.retention_pressure
current_state.runtime_started
current_state.runtime_stopped
```

---

## 59. Safe fields

Allowed summary fields:

```text
site_id
cycle_id
kind
duration_ms
complete
items_seen/stored/skipped
page_count
error/warning count
duplicate count
unknown status count
failure category
cleanup rows/cycles
```

Do not emit one log per client per cycle.

No secrets/tokens/passwords/cookies.

---

# PART I — SECURITY / PRIVACY

## 60. Internal only

Full MAC is permitted in authenticated internal Admin/current-state storage as project device identity.

This TASK adds no public endpoint.

Do not expose Current State through `/`, CAPPORT or public counter APIs.

---

## 61. Raw-data prohibition

Never persist:

```text
raw client JSON
raw AP inventory JSON
OAuth token
Client Secret
Authorization header
cookies
SSID password
portal password
```

Allowlist-only normalized storage.

---

# PART J — PERFORMANCE / CAPACITY

## 62. Polling budget

Proposed candidate cadence:

```text
client inventory every 30s
AP inventory every 30s
```

This is not automatically production-approved.

Before activation Tech Lead verifies:

```text
controller load
request count
cycle duration
shared token behavior
no interference with Observation/AP workers
```

If 30s is excessive, increase interval rather than weaken bounded safety.

---

## 63. No request amplification

Client cycle:

```text
one bounded paginated /clients inventory
```

Forbidden:

```text
one /clients/{MAC} call per client
```

AP cycle:

```text
one bounded paginated /devices inventory
```

No detailed AP N+1 for status.

---

## 64. Required read benchmarks

Implementation handoff later records at minimum:

```text
10,000-row synthetic current client snapshot summary
first Online Devices page
next cursor page
sort by traffic_total
sort by uptime
filter by AP
filter by auth class
AP summary
24h-support aggregate/query-plan prototype over representative history
```

---

## 65. Storage capacity benchmark

Representative upper current-use case:

```text
250 clients
2 snapshots/min
60 min/hour
48h
=
1,440,000 client rows
```

This is within proposed five-million-row cap.

If actual SQLite size/query behavior is unacceptable:

```text
STOP
return evidence
propose revised cadence/retention/index design
```

Do not silently remove required 24h readiness.

---

# PART K — TESTS

## 66. Configuration tests

Minimum:

- disabled default;
- enabled missing Site IDs rejected;
- missing SSID scope rejected;
- exact canonical Site validation;
- duplicate Site/SSID rejection;
- interval/page/row bounds;
- freshness bounds;
- stale > fresh;
- retention/hard-cap bounds;
- safe repr/errors.

---

## 67. Client normalization tests

Minimum:

- auth 2 → authorized;
- auth 1 → pending;
- auth 0 → other;
- auth 3 → other;
- unknown integer → raw + other;
- missing/non-integer auth → unknown;
- inactive excluded;
- wired excluded;
- other SSID excluded;
- IP/AP MAC normalization;
- nullable RSSI/SNR;
- nullable traffic counters;
- safe traffic total;
- overflow handling;
- invalid MAC quality;
- duplicate MAC makes snapshot incomplete.

---

## 68. Client inventory tests

Minimum:

- one-page complete;
- multi-page complete;
- changing `totalRows` → partial;
- returned page mismatch;
- short page before expected total;
- page limit;
- row limit;
- provider failure;
- shutdown;
- zero-client complete inventory = success.

---

## 69. Count invariant tests

For a complete snapshot prove:

```text
online = authorized + pending + other + unknown
online = AP buckets + AP unknown
```

No cross-cycle mixing.

---

## 70. AP tests

Minimum:

- only `type=ap`;
- canonical AP MAC;
- safe metadata;
- raw status retained;
- confirmed code classification;
- unconfirmed code remains other/unknown;
- missing status unknown;
- duplicate AP identity makes snapshot incomplete;
- complete zero-AP inventory valid.

---

## 71. Storage tests

Minimum:

- schema v1;
- constraints/FK;
- atomic publication;
- failed cycle != empty success;
- complete empty client cycle supported;
- readers do not see half-cycle;
- WAL read/write concurrency;
- cleanup whole cycles only;
- latest usable cycle preserved;
- hard cap removes oldest removable cycles;
- retention pressure recorded.

---

## 72. Read-service tests

Minimum:

- Site isolation;
- latest attempt vs latest usable;
- fresh/stale/unavailable;
- completeness preserved;
- source scope returned;
- summary uses one exact cycle;
- stable keyset cursor;
- cursor cannot change Site/cycle/sort/filter;
- no OFFSET;
- allowlist-only sort/filter;
- deterministic NULL ordering;
- bounded page size;
- immutable DTOs;
- readonly DB; no write through service.

---

## 73. Worker/runtime tests

Minimum:

- shared provider injected;
- no new provider created;
- no overlapping client/AP cycles;
- fixed-delay behavior;
- fail-open provider/storage error;
- independent Client/AP degradation;
- bounded shutdown;
- disabled runtime starts no worker;
- no Portal/CAPPORT/Auth behavior change.

---

## 74. Regression suites

Mandatory targeted existing coverage:

```text
tests/observations/**
tests/test_omada_observations.py
tests/pending_sessions/**
tests/analytics/**
tests/admin_web/**
```

plus:

```text
tests/current_state/**
```

Existing historical Observation regression must continue proving that non-`authStatus=2` clients are not stored as authorized Client Observations.

---

## 75. Full gate

```bash
python -m pytest -q -rs

PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app

git diff --check
git status --short
```

Handoff records exact baseline/implementation SHA, Python version and exact passed/skipped/failed counts.

---

# PART L — SCOPE

## 76. Allowed new files

```text
app/current_state/**
tests/current_state/**
```

---

## 77. Narrow existing-file changes allowed

For config/composition only:

```text
app/config.py
app/settings.py
.env.example
run.py
```

Provider changes are not expected because existing validated primitives are reusable.

If Tech Lead requires a semantic alias, narrow allowed paths may be added in FINAL:

```text
app/controllers/omada_observations.py
app/controllers/__init__.py
tests/test_omada_observations.py
```

Alias/delegation only; no duplicate HTTP/token logic.

---

## 78. Forbidden

Do not change business behavior in:

```text
app/auth/**
app/capport/**
app/visitor_registry/**
app/visit_lifecycle/**
app/pending_sessions/**
app/observations/** historical semantics
app/analytics/** formulas/metrics
app/admin_web/** routes/UI in this TASK
app/public_traffic/**
app/portal_counter/**
```

Do not change source schemas for Observation/Visit/Registry/Public Traffic/Portal Counter.

No Home UI.

No Current State Admin route in this TASK unless Tech Lead explicitly asks to combine the bridge with the foundation.

Preferred boundary:

```text
TASK ends at CurrentStateReadService
HOME-LIVE-01 adds Admin API + widgets
```

---

# PART M — STOP CONDITIONS

## 79. STOP / return architecture impact if

- `/clients` does not provide all active wireless in-scope clients required;
- provider filters data before Current State can access it;
- auth status semantics materially differ from confirmed research;
- AP inventory status cannot be safely classified enough for product use;
- client uptime semantics cannot be verified;
- client traffic counter semantics materially differ from expected current-session interpretation;
- reliable pagination completeness cannot be established;
- implementation needs historical Observation semantic/schema change;
- safe behavior requires N+1 client detail requests;
- proposed cadence materially impacts Omada/Portal/Observation;
- short history cannot remain bounded;
- implementation requires direct Home/Admin → Omada calls.

Continue independent safe parts where possible and report exact evidence.

---

# PART N — ACCEPTANCE

## 80. Code acceptance

Implementation accepted only if:

- separate Current State package and schema-v1 DB exist;
- repository default disabled;
- shared provider/token lifecycle reused;
- no duplicate Omada HTTP client;
- Observation authorized-only meaning unchanged;
- all active wireless allowed-SSID auth states represented safely;
- one client snapshot drives Online/Auth/AP distribution facts;
- count invariants pass;
- AP inventory status persisted with raw/safe classification;
- read service Site-scoped/read-only;
- freshness/completeness/scope explicit;
- current table queries bounded to one snapshot;
- stable keyset pagination;
- short history bounded by time + hard cap;
- future AP-24h evidence retained;
- targeted/full tests green;
- compileall/diff-check green;
- no Portal/CAPPORT/Auth regression.

---

## 81. Production-readiness acceptance

Implementation merge does **not** authorize activation.

Separate owner-controlled activation verifies:

### Client

- collector active at configured cadence;
- complete snapshot exists;
- controller client count reconciles with configured SSID scope;
- designated owner device observed through `PENDING → AUTHORIZED`;
- Online invariant confirmed;
- Devices-by-AP matches controller state;
- uptime semantics confirmed;
- traffic counter behavior confirmed.

### AP

- AP inventory snapshot complete;
- all production APs present;
- online status mapping verified;
- unknown status never becomes false offline.

### Coexistence

- historical authorized Observation still accumulates normally;
- Registry/Visit/Analytics remain healthy;
- Captive Portal unchanged;
- no material controller-load regression.

Future production Home must not consume Current State until this acceptance passes.

---

# PART O — FOLLOW-ON

## 82. Follow-on sequence

After this TASK is merged, Linux-gated and production-accepted:

```text
HOME-LIVE-01
  Online / Authorized / Pending / Other
  Devices by AP — Now
  Online Devices

HOME-TRAFFIC-01
  Current Traffic
  traffic by AP
  Channel Load

HOME-TODAY-01
  existing opened_today bridge
  existing Public Traffic today_bytes bridge

HOME-HEALTH-01
  product-safe component health

HOME-AP-24H-01
  Avg / Peak / Unique by AP
  coverage/capacity benchmark

final Home composition
```

This decomposition does not reduce the Owner/Architect-approved Home product scope.

---

## 83. Required Coder handoff later

When FINAL is separately authorized, implementation handoff must include:

```text
exact baseline
files changed
schema version
config keys/defaults
provider primitives reused
cycle semantics
auth classification table
AP status classification evidence
uptime semantic evidence status
traffic-counter semantic evidence status
targeted/full tests
performance benchmark
storage estimate
query plans
known limitations
production activation NOT performed
```

---

## 84. Tech Lead review questions

Please explicitly review:

1. Is separate `current_state.sqlite3` preferred over extending Observation schema?
2. Is direct reuse of existing `list_observation_clients()` and `list_observation_access_points()` accepted?
3. Is proposed 30s Client/AP cadence acceptable as a production candidate?
4. Are `60/180s` Client and `90/300s` AP freshness thresholds reasonable?
5. Is `48h + 5,000,000 client rows` an acceptable bounded history contract?
6. Are proposed current-client fields sufficient for Home without overcollection?
7. Is strict auth classification (`2=authorized`, `1=pending`, all others Other/Unknown) accepted?
8. Does AP status mapping need extra controller-schema evidence before code, or can raw status be implemented first and product classification activated after verification?
9. Are current-snapshot keyset pagination/sort contracts sufficient for future Online Devices?
10. Should any additional index for future AP-24h be added now, or only after `HOME-AP-24H-01` query-plan benchmark?

---

## 85. Current authorization status

```text
TASK-HOME-CURRENT-STATE-01
DRAFT FOR TECH LEAD REVIEW

IMPLEMENTATION NOT AUTHORIZED
BRANCH NOT AUTHORIZED
COMMIT NOT AUTHORIZED
PUSH NOT AUTHORIZED
PR NOT AUTHORIZED
PRODUCTION ACTIVATION NOT AUTHORIZED
```

Next allowed action:

```text
Tech Lead architecture review
```

Then:

```text
DRAFT corrections
→ FINAL
→ separate Owner implementation authorization
→ Coder execution
```
