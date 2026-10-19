# TASK-HOME-CURRENT-STATE-01 — Current Network State Foundation — FINAL

**Project:** CaptivPortal  
**Parent product concept:** `TASK-HOME-01 — Admin Console Home v1`  
**Type:** architecture / preparatory implementation specification  
**Status:** `FINAL — TECH LEAD REVIEW INCORPORATED`  
**Implementation authorization:** `NOT GRANTED — requires separate Owner authorization`  
**Production activation:** separate owner-controlled step  
**Architecture baseline:** `main@e43bead3028e45981012c4f540200bf3d9754cac`  
**Prepared:** 2026-08-23  
**Tech Lead review:** `PASS — required clarifications incorporated`

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

### 3.5 Acquisition request-cost decision

Reusing the shared `OmadaProvider` and token cache does **not** reuse an inventory already fetched by another worker. Current State therefore adds its own bounded reads of `/clients` and `/devices`.

**FINAL decision: Option A is selected.**

```text
A. Independent repeated polling is deliberately allowed
   after measured load/cycle-duration acceptance.

B. A shared acquisition/coalescing layer is NOT part of this TASK.
```

At the 30-second production-candidate cadence, for one Site and one page per inventory, expected incremental request pressure is approximately:

```text
/clients:
Current State     2 requests/min
Observation       1 request/min
Total             3 requests/min

/devices:
Current State     2 requests/min
Observation       ~0.2 requests/min
Total             ~2.2 requests/min
```

With multiple pages, inventory request count scales with actual page count. Detailed AP Observation endpoint requests remain separate and are not included in the `/devices` line above.

Current State must record actual per-cycle request/page count and duration. Production activation must prove that the chosen cadence does not materially affect Observation, authorization, Portal/CAPPORT, or Omada Controller health.

If the load gate fails, the allowed response is to increase Current State polling intervals. Introducing shared acquisition/coalescing requires a separate architecture amendment/TASK because it changes ownership and scheduling boundaries across existing collectors.

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

Client v1 scope is:

```text
Site ID
+
configured portal-managed SSID allowlist
```

AP v1 scope is different and is defined later as **all AP inventory rows of the selected Site**.

Expected production client scope is the production Home Site and `Zefer_Parki`, but production identifiers/SSID values are never hardcoded in runtime code.

### 7.1 Lossless SSID configuration

SSID matching is exact and case-sensitive. There is no hidden trimming, case folding, Unicode normalization, comma splitting, or whitespace normalization.

To support spaces and commas safely, v1 configuration uses a JSON array rather than CSV semantics:

```text
CURRENT_STATE_CLIENT_SSIDS_JSON=["Zefer_Parki"]
```

Examples that must remain representable exactly:

```json
["Lobby WiFi", "VIP,Guests", "  LeadingSpace"]
```

Individual SSID strings are preserved exactly as configured. Empty SSIDs are rejected. Duplicate exact strings are rejected.

### 7.2 Canonical source scope

Every cycle stores:

```text
source_scope_version
source_scope_json
source_scope_hash
```

For client cycles, canonical scope v1 is logically:

```json
{
  "scope_type": "client_ssid_allowlist",
  "site_id": "<canonical-site-id>",
  "ssids": ["<exact-ssid>"]
}
```

For AP cycles:

```json
{
  "scope_type": "site_ap_inventory",
  "site_id": "<canonical-site-id>"
}
```

Canonicalization rules:

- `source_scope_version = 1`;
- object keys serialized in stable sorted order;
- no insignificant whitespace;
- UTF-8 encoding;
- client SSID list deduplicated then sorted only for hash stability; individual string bytes are not otherwise normalized;
- `source_scope_hash = lowercase SHA-256 hex` of canonical `source_scope_json`.

Changing Site or SSID allowlist creates a different scope hash. Old and new scope hashes must never be silently combined as if they described one unchanged population.

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

Repository-safe defaults:

```text
CURRENT_STATE_ENABLED=false
CURRENT_STATE_DB_PATH=/opt/CaptivePortal/data/current_state.sqlite3

CURRENT_STATE_SITE_IDS=
CURRENT_STATE_CLIENT_SSIDS_JSON=[]

CURRENT_STATE_CLIENT_INITIAL_DELAY_SECONDS=10
CURRENT_STATE_CLIENT_INTERVAL_SECONDS=60

CURRENT_STATE_AP_INITIAL_DELAY_SECONDS=15
CURRENT_STATE_AP_INTERVAL_SECONDS=60

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
CURRENT_STATE_CLEANUP_MAX_CYCLES_PER_RUN=100
CURRENT_STATE_CLEANUP_MAX_ROWS_PER_TRANSACTION=100000
CURRENT_STATE_CLEANUP_MAX_DURATION_SECONDS=30

CURRENT_STATE_SQLITE_BUSY_TIMEOUT_MS=500
CURRENT_STATE_SHUTDOWN_TIMEOUT_SECONDS=20
```

The disabled repository default cadence is 60 seconds. A 30-second Client/AP cadence is an explicit **production candidate**, not an automatic production default. It may be activated only after the load gate in this FINAL passes.

## 12. Configuration validation

When enabled:

- non-empty Site IDs;
- exact lowercase `[0-9a-f]{24}` Site IDs;
- `CURRENT_STATE_CLIENT_SSIDS_JSON` must parse as a JSON array of strings;
- at least one exact non-empty SSID;
- duplicate exact SSIDs rejected;
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
cleanup max cycles/run:   1..10000
cleanup rows/transaction: 1..1000000
cleanup max duration:     1..300s
busy timeout:             0..5000ms
shutdown timeout:         1..120s
```

DB path safety validation is additionally governed by Part D; numeric config validity alone is not sufficient.

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
source scope
capture_started_at
capture_finished_at
duration_ms
```

All pages from the poll belong to the same cycle.

Omada pagination is sequential. `complete=true` therefore does **not** assert that every row existed at one atomic controller instant. It means the bounded pagination contract was retrieved successfully and consistently for the capture interval.

The capture interval remains explicit:

```text
[capture_started_at, capture_finished_at]
```

`duration_ms` is measured with a monotonic clock. Wall-clock timestamps are not used to calculate cycle duration.

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
ssid is an exact member of the parsed CURRENT_STATE_CLIENT_SSIDS_JSON allowlist
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
cycle_kind = client
site_id
observed_at

client_mac
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
controller_uptime

auth_status_code
auth_classification

controller_traffic_down
controller_traffic_up
controller_traffic_total

active
wireless
```

`controller_client_id` is deliberately **not persisted in v1** because the agreed Home contract does not require it and no separate current-state use case justifies the extra identity field.

### 18.1 Controller string bounds

Persisted controller text is bounded in UTF-8 bytes:

```text
name                 <= 256 bytes
hostname             <= 253 bytes
device_type          <= 128 bytes
ssid                  <= 32 bytes
ap_name              <= 256 bytes
band                  <= 32 bytes
```

IP is accepted only after canonical IP-address parsing; no arbitrary IP text is stored.

Text is not silently truncated. If an optional controller field exceeds its bound, has an unsafe embedded NUL, or fails field-specific validation:

```text
field = NULL
data_quality_warning_count += 1
```

The rest of an otherwise safe client row may still be stored.

SSID is special: exact bytes/string semantics are preserved for matching. Do not trim or normalize the SSID before scope comparison.

## 19. Auth status contract

Persist a strict integer raw status when available.

Current project/controller research provides the candidate mapping:

```text
0 = CONNECTED
1 = PENDING
2 = AUTHORIZED
3 = AUTH-FREE
```

Storage classification v1:

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

Do not relabel `AUTH-FREE` as Captive Portal `AUTHORIZED`. Unknown future integer codes remain raw evidence and are not assigned invented meanings.

**Production evidence gate:** before product use, the implementation/activation handoff must record the exact Controller build/version, relevant Swagger/API version and controlled evidence confirming the status mapping on that production controller family. If evidence materially disagrees, STOP and return architecture impact; do not silently keep labels.

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

Persist the controller field neutrally as:

```text
controller_uptime
```

Do not call it Visit duration and do not expose it to product UI as seconds until verified.

Before `HOME-LIVE-01` may label it `Online time`, controlled evidence must confirm:

1. exact Controller build/version and API source;
2. unit;
3. value increases across repeated snapshots;
4. behavior on approved reconnect/new association;
5. behavior on client disappearance/reappearance;
6. reset/continuity behavior after relevant AP/controller restart when safe to test.

After evidence confirms seconds/current association semantics, the read/UI layer may present a derived `uptime_seconds`/duration without changing stored raw evidence.

Until then the value is a neutral controller counter.

## 23. Client traffic counters

Persist strict non-negative controller integers neutrally as:

```text
controller_traffic_down
controller_traffic_up
controller_traffic_total
```

They are counters, not Mbps. The storage field names deliberately do not assert unit or product direction semantics beyond the controller field names.

If both direction counters are valid INT64 values and their sum is safe:

```text
controller_traffic_total = down + up
```

If either value is unavailable or sum overflows:

```text
controller_traffic_total = NULL
```

Overflow adds a quality warning.

Before `HOME-LIVE-01` may display these values as `Download / Upload / Total Traffic`, controlled production-family evidence must confirm:

```text
trafficDown direction = Download
trafficUp direction   = Upload
unit                  = bytes
reset behavior
continuity behavior across normal samples
behavior across reconnect/new association
```

Evidence records Controller build/version and API/Swagger version.

Until that gate is passed, Admin/product UI may show only neutral controller counters, not `MB/GB Download` labels.

Current State does not calculate per-client Mbps in this TASK.

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

Each Site poll creates one independent logical AP inventory snapshot:

```text
ap_cycle_id
site_id
source scope = all AP inventory rows of selected Site
capture_started_at
capture_finished_at
complete
```

AP scope is **not** restricted by the client SSID allowlist.

Client and AP snapshots are independently captured and have independent cycle IDs/watermarks. Future Home must not hide them behind one artificial common `Updated` timestamp.

## 27. AP allowlist fields

Minimum:

```text
ap_cycle_id
cycle_kind = ap
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
controller_uptime
uptime_raw
```

Controller text bounds:

```text
name             <= 256 UTF-8 bytes
model            <= 128 UTF-8 bytes
firmware_version <= 256 UTF-8 bytes
uptime_raw       <= 128 UTF-8 bytes
```

IP requires canonical address parsing. Optional overlong/unsafe text becomes NULL + quality warning; it is never silently truncated.

Only safely validated allowlisted fields are persisted. No raw inventory JSON.

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

Unknown/other remain separately representable. Missing detailed historical AP Observation is never itself `OFFLINE`. Unknown inventory status never becomes `offline`.

### 29.1 Client/AP merge contract

The two current-state scopes differ:

```text
Client snapshot = Site + exact SSID allowlist
AP snapshot     = all APs in selected Site inventory
```

Future composition joins only by canonical AP MAC, never by AP name.

Required behavior:

- client references AP MAC absent from selected AP snapshot → keep the client AP bucket; AP health/status for that bucket is `unknown`;
- AP exists in inventory but has zero scoped clients → keep the AP in `Access Points Now` and attach scoped client count `0`;
- client `ap_mac=NULL` → `AP unknown` client bucket;
- client and AP watermarks remain independent;
- no future join may rewrite a client AP bucket based on AP display name.

# PART C — CONSISTENCY / QUALITY

## 30. Common cycle metadata

Minimum:

```text
cycle_id
kind                  # client | ap
site_id

capture_started_at
capture_finished_at
complete
result

source_scope_version
source_scope_json
source_scope_hash

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

For row-level storage:

```text
observed_at = capture_started_at
```

All rows in one logical cycle therefore share the same `observed_at`. The finish time remains separately available to show capture skew.

## 31. Cycle results

Allowed results:

```text
success
partial
failed
shutdown
```

Hard invariant enforced by model/repository/DB constraints:

```text
success  → complete=true
partial  → complete=false
failed   → complete=false
shutdown → complete=false
```

`complete=true` means:

> bounded pagination was retrieved completely and consistently according to the API contract and the normalized persisted row set has no completeness-breaking identity/scope error.

It does **not** mean that a multi-page Controller inventory was atomically frozen at one millisecond. A multi-page snapshot represents the explicit capture interval.

Mathematical count invariants are exact for the persisted normalized row set of that cycle.

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

## 33. Snapshot selection contract

The repository/read boundary exposes three distinct identities:

```text
latest_attempt
latest_complete_snapshot
latest_partial_snapshot
```

Definitions:

```text
latest_attempt
= newest cycle of the requested kind/site regardless of result

latest_complete_snapshot
= newest cycle where result=success AND complete=true

latest_partial_snapshot
= newest cycle where result=partial AND complete=false AND rows were persisted
```

The ambiguous term `latest usable snapshot` is forbidden in the FINAL contract.

### Exact Home-current rule

Future exact counters and default Online Devices page resolve **only** `latest_complete_snapshot`.

A fresh partial snapshot may be exposed through explicit diagnostic/observed APIs later, but it never silently replaces exact counters.

A failed attempt does not erase older complete/partial snapshots. Its failure remains visible through `latest_attempt`.

If the latest complete snapshot exceeds the unavailable threshold:

```text
exact current values = unavailable
```

even when a fresher partial snapshot exists. The partial snapshot may be reported separately as incomplete observed evidence, never as the exact current picture.

A complete zero-client cycle is a valid complete snapshot with `online_count=0`. A failed/partial zero-row attempt is not.

## 34. Freshness and wall-clock contract

Every current read returns/derives at minimum:

```text
evaluated_at
observed_at              # capture_started_at
capture_finished_at
age_seconds
freshness_status
freshness_reason
complete
cycle_id
source_scope_version
source_scope_hash
source_scope
latest_attempt_result
latest_attempt_at
```

Normal age rule:

```text
observed_at = capture_started_at
age_seconds = max(0, evaluated_at - observed_at)
```

Using capture start prevents a long poll from looking artificially fresh immediately after completion. `duration_ms` is always measured from a monotonic clock.

Client thresholds:

```text
<=60s       fresh
>60..180s   stale
>180s       unavailable
```

AP thresholds:

```text
<=90s       fresh
>90..300s   stale
>300s       unavailable
```

Completeness and freshness are independent.

### 34.1 Clock anomalies

If persisted timestamp parsing fails, evaluated wall clock is earlier than `observed_at`, or a future timestamp is otherwise detected:

```text
data-quality warning
freshness_status = unavailable
freshness_reason = clock_anomaly | invalid_timestamp
```

No negative age is emitted. For a detected future/wall-clock-regression case `age_seconds` may be clamped to `0`, but the snapshot remains unavailable. Invalid/unparseable timestamps return `age_seconds=NULL`.

Clock anomalies never promote old/invalid data to fresh.

# PART D — PERSISTENCE

## 35. Database and filesystem contract

Canonical production target:

```text
/opt/CaptivePortal/data/current_state.sqlite3
PRAGMA user_version = 1
```

SQLite settings:

```text
journal_mode=WAL
synchronous=NORMAL
foreign_keys=ON
busy_timeout=CURRENT_STATE_SQLITE_BUSY_TIMEOUT_MS
```

### 35.1 Path safety

Before creating/opening the DB:

- the target path itself must not be a symlink;
- if target exists, it must be a regular file;
- parent directory must exist, be a real directory and not be a symlink;
- production target must not live under application/Admin static/template roots or the active web-server public document tree;
- resolved DB path must not equal any other configured SQLite DB path in CaptivPortal, including Observation, Visit, Registry, Portal Counter and Public Traffic storage;
- path collision is a configuration error, never an instruction to share a DB.

Tests may use isolated temporary directories but must preserve the same symlink/non-regular/collision checks.

### 35.2 Permissions

New DB file mode:

```text
0640
```

Whenever SQLite WAL/SHM sidecars exist, repository/runtime must ensure they are not world-readable; expected maximum mode is:

```text
0640
```

Parent-directory permissions must prevent public web access. Production activation records actual owner/group/modes for DB, WAL and SHM.

### 35.3 Schema/version/integrity safety

Only an absent target may be initialized as schema v1.

For an existing DB:

```text
wrong user_version
missing/incompatible required schema
failed integrity/quick-check
SQLite corruption/open failure
```

→ Current State becomes unavailable/degraded, Portal remains fail-open, and data is **not** deleted, recreated, reset or migrated implicitly.

Any future schema migration requires a separately reviewed contract.

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
cycle_id TEXT NOT NULL
kind TEXT NOT NULL
site_id TEXT NOT NULL

capture_started_at TEXT NOT NULL
capture_finished_at TEXT NOT NULL
complete INTEGER NOT NULL
result TEXT NOT NULL

source_scope_version INTEGER NOT NULL
source_scope_json TEXT NOT NULL
source_scope_hash TEXT NOT NULL

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

PRIMARY KEY(cycle_id)
UNIQUE(cycle_id, site_id, kind)
```

CHECK constraints enforce:

- `kind IN ('client','ap')`;
- non-negative counts/duration;
- complete boolean;
- result enum;
- `success ↔ complete=1` and every non-success result requires `complete=0`;
- scope version positive;
- scope hash exactly lowercase 64-hex.

## 38. `current_client_state`

Conceptual schema:

```text
cycle_id TEXT NOT NULL
cycle_kind TEXT NOT NULL DEFAULT 'client' CHECK(cycle_kind='client')
site_id TEXT NOT NULL
observed_at TEXT NOT NULL
client_mac TEXT NOT NULL
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
controller_uptime INTEGER
auth_status_code INTEGER
auth_classification TEXT NOT NULL
controller_traffic_down INTEGER
controller_traffic_up INTEGER
controller_traffic_total INTEGER
active INTEGER NOT NULL
wireless INTEGER NOT NULL

PRIMARY KEY(cycle_id, client_mac)
FOREIGN KEY(cycle_id, site_id, cycle_kind)
  REFERENCES current_state_cycles(cycle_id, site_id, kind)
  ON DELETE CASCADE
```

This composite FK + constant `cycle_kind='client'` rejects both cross-Site and cross-kind attachment at the DB layer. Repository methods must independently enforce the same invariant before executing SQL.

## 39. `current_ap_state`

Conceptual schema:

```text
cycle_id TEXT NOT NULL
cycle_kind TEXT NOT NULL DEFAULT 'ap' CHECK(cycle_kind='ap')
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
controller_uptime INTEGER
uptime_raw TEXT

PRIMARY KEY(cycle_id, ap_mac)
FOREIGN KEY(cycle_id, site_id, cycle_kind)
  REFERENCES current_state_cycles(cycle_id, site_id, kind)
  ON DELETE CASCADE
```

This rejects AP row → client cycle and cross-Site attachment at both DB and repository boundaries.

## 40. Required indexes

Minimum indexes needed for current-state reads:

```text
cycles: (kind, site_id, capture_started_at DESC)
client: (cycle_id, client_mac)
client: (cycle_id, auth_classification, client_mac)
client: (cycle_id, ap_mac, client_mac)
client: (cycle_id, controller_uptime DESC, client_mac)
client: (cycle_id, controller_traffic_total DESC, client_mac)
AP:     (cycle_id, ap_mac)
AP:     (cycle_id, status_classification, ap_mac)
```

No extra AP-24H index is pre-authorized. `HOME-AP-24H-01` may add one only after representative `EXPLAIN QUERY PLAN` + measured benchmark demonstrates need.

## 41. Short history retention and cleanup unit

Purpose:

```text
future Devices by AP — 24h
recent capacity/trend verification
short current-state diagnostics
```

Retention candidate:

```text
48h
```

This is not long-term client history.

Cleanup unit is **whole cycles**, never individual state rows. `CURRENT_STATE_CLEANUP_MAX_CYCLES_PER_RUN` is therefore counted in cycles, not rows.

Each cleanup transaction also obeys:

```text
CURRENT_STATE_CLEANUP_MAX_ROWS_PER_TRANSACTION
```

If one removable cycle alone contains more rows than that row budget, that one whole cycle may be deleted in its own transaction. It must never be partially deleted.

Each cleanup run additionally obeys `CURRENT_STATE_CLEANUP_MAX_DURATION_SECONDS`.

Preserve at minimum for each `(kind, site_id)`:

```text
newest latest_attempt metadata cycle
latest_complete_snapshot cycle
latest_partial_snapshot cycle when it exists and is distinct
```

No unbounded delete. No `VACUUM` in request path.

## 42. Hard storage cap and retention pressure

Production-candidate cap:

```text
CURRENT_STATE_HISTORY_MAX_CLIENT_ROWS=5,000,000
```

It is not production-approved merely because the integer is configured. Byte/disk acceptance in Part J must pass first.

Cleanup removes oldest removable **whole client cycles** until under cap or until the cleanup run budget expires.

If the cap cannot be restored within the bounded run, or preserving required snapshots prevents deletion:

```text
retention_pressure = true
telemetry emitted
Current State remains fail-open
next cleanup may continue bounded work
```

Never partially delete a retained cycle.

If pressure causes missing coverage inside a future 24h window, later AP-24H output must report partial coverage. It must not label the remaining samples as a complete 24h history.

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

Conceptual exact method:

```python
get_current_client_summary(
    site_id,
    *,
    evaluated_at_utc=None,
)
```

Default exact result resolves `latest_complete_snapshot` only and returns:

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

If latest complete snapshot is stale, result is explicitly stale. If it exceeds unavailable threshold, current values are unavailable.

A fresh partial snapshot never replaces this exact summary. Read service may expose separate diagnostics identifying `latest_partial_snapshot` and its observed counts, clearly marked incomplete.

## 46. Current client page

Conceptual exact method:

```python
list_current_clients(
    site_id,
    *,
    cycle_id=None,
    limit=100,
    cursor=None,
    sort="controller_traffic_total_desc",
    auth_classification=None,
    ap_mac=None,
)
```

If `cycle_id` is omitted, resolve `latest_complete_snapshot`. The selected complete cycle is pinned for the entire page sequence.

A partial cycle may only be requested through an explicitly diagnostic API/read method in a later task; it is never the implicit default.

Cursor binding includes:

```text
site_id
cycle_id
source_scope_hash
sort
filters
```

Page 2 must not silently switch to a newer snapshot or different scope.

## 47. Pagination

No OFFSET.

Stable keyset pagination with `client_mac` tie-breaker.

Examples:

```text
controller_traffic_total DESC, client_mac ASC
controller_uptime DESC, client_mac ASC
client_mac ASC
```

NULL ordering is explicit and deterministic.

Cursor validation rejects changed Site, cycle, scope hash, sort or filters.

## 48. Sort/filter allowlist

Prepare only Home-required sorts:

```text
client_mac
controller_uptime
controller_traffic_total
controller_traffic_down
controller_traffic_up
auth_status
ap
rssi
snr
```

Filters:

```text
auth classification
AP
exact SSID when multiple are configured
```

No arbitrary SQL column names or free-form ORDER BY.

A low-frequency sort may use a bounded single-snapshot scan if benchmarked safely, but it must never scan all 48h history to sort the current table.

Later UI labels such as `Online`, `Download`, `Upload` are allowed only after the evidence gates for uptime/traffic semantics pass.

## 49. Current AP summary

Conceptual exact method:

```python
get_current_ap_summary(site_id, *, evaluated_at_utc=None)
```

Default exact result resolves AP `latest_complete_snapshot` only and returns:

```text
snapshot metadata
ap_total
online_count
offline_count
other_count
unknown_count
```

Only controller status classifications supported by recorded evidence are used. A fresh partial AP snapshot never silently replaces exact AP counts.

## 50. Current AP page

Conceptual:

```python
list_current_aps(site_id, *, cycle_id=None, limit=100, cursor=None)
```

If cycle is omitted, resolve AP `latest_complete_snapshot`. Stable order:

```text
ap_mac ASC
```

No growing-history scan. The page exposes the AP snapshot watermark independently from any client snapshot watermark.

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

Only complete Client cycles with a single compatible `source_scope_hash` are eligible for one exact population series.

---

## 52. 24h quality and source-scope readiness

Storage must allow later output of:

```text
from_utc
to_utc
source_scope_version
source_scope_hash
complete_cycle_count
partial_cycle_count
failed_cycle_count
coverage
first_snapshot_at
last_snapshot_at
max_gap_seconds
retention_pressure
scope_changed
```

Future `HOME-AP-24H-01` must never merge client cycles with different `source_scope_hash` values into one Avg/Peak/Unique result.

Canonical future rule:

1. determine the current client scope hash at the evaluation end;
2. select only cycles with that exact hash;
3. if a different hash occurs inside the requested 24h interval, set `scope_changed=true`;
4. if the current hash does not provide full requested-window coverage, return partial coverage / `incompatible_scope` reason;
5. never silently fill the missing portion with cycles from the previous scope.

No silent `24h` label when retained/current-scope evidence covers less than 24h.

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

## 62. Polling budget and duplicate-request acceptance

Repository-safe disabled defaults use 60s Client/AP intervals.

Production candidate after load gate:

```text
client inventory every 30s
AP inventory every 30s
```

FINAL deliberately allows independent repeated polling rather than introducing coalescing.

For every load-gate run record separately for `/clients` and `/devices`:

```text
configured interval
actual cycles observed
actual pages/request count
requests per minute
cycle duration min/avg/p95/max
timeouts
HTTP/controller errors
token refresh/expiry events
partial/failed cycles
```

Also record contemporaneous Observation/Auth/Portal health.

30s activation is rejected if it creates material latency/error/degradation in Omada, Observation, authorization or Portal/CAPPORT. On failure increase interval; do not invent a shared acquisition layer inside this TASK.

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

## 65. Storage capacity and disk acceptance

Representative production-load model:

```text
250 clients
2 snapshots/min
60 min/hour
48h
= 1,440,000 client rows
```

Before the 5,000,000-row cap is considered a production-approved value, implementation handoff must provide numerical measurements from the actual schema/indexes or a representative filesystem benchmark:

```text
DB bytes at ~1,440,000 client rows
projected/measured DB bytes at 5,000,000 client rows
index bytes included in the above
peak WAL bytes during representative writes/cleanup
SHM bytes
cleanup duration for representative expired-cycle workload
summary query duration
first-page query duration
cursor-page query duration
traffic-sort query duration
uptime-sort query duration
host filesystem total/free bytes
minimum remaining disk headroom after projected cap
```

Production disk gate:

```text
remaining free space after projected 5M-row DB + measured peak WAL
must be >= 2 GiB
AND >= 30% of the containing filesystem capacity.
```

If either condition fails, 5M is not an accepted production cap. Return evidence and propose a lower cap/cadence/retention plan.

Cleanup benchmark must include a cycle whose row count is larger than `CURRENT_STATE_CLEANUP_MAX_ROWS_PER_TRANSACTION` and prove it is deleted whole in a bounded single-cycle transaction, not partially.

If actual SQLite size/query/cleanup behavior is unacceptable:

```text
STOP
return evidence
propose revised cadence/retention/index design
```

Do not silently remove required 24h readiness.

# PART K — TESTS

## 66. Configuration / filesystem tests

Minimum:

- disabled default;
- enabled missing Site IDs rejected;
- missing/invalid SSID JSON scope rejected;
- exact canonical Site validation;
- duplicate Site/SSID rejection;
- SSID with spaces preserved exactly;
- SSID containing comma preserved as one JSON element;
- case-sensitive SSID matching;
- interval/page/row bounds;
- freshness bounds;
- stale > fresh;
- retention/hard-cap bounds;
- safe repr/errors;
- DB target symlink rejected;
- existing non-regular target rejected;
- symlink parent rejected;
- public-tree DB target rejected where determinable by runtime validation;
- DB-path collision with every other configured CaptivPortal SQLite path rejected;
- created DB mode 0640;
- WAL/SHM not world-readable;
- wrong existing `user_version` unavailable without recreation;
- corrupt/integrity-failing DB unavailable without deletion.

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
- exact case-sensitive SSID match;
- IP/AP MAC normalization;
- nullable RSSI/SNR;
- nullable controller traffic counters;
- safe controller traffic total;
- overflow handling;
- invalid MAC quality;
- duplicate MAC makes snapshot incomplete;
- overlong name/hostname/device_type/AP-name becomes NULL + quality warning without row loss;
- embedded-NUL unsafe optional text handling;
- `controller_client_id` is not persisted.

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

## 69. Count/snapshot-selection tests

For a complete snapshot prove:

```text
online = authorized + pending + other + unknown
online = AP buckets + AP unknown
```

Also test:

- no cross-cycle mixing;
- newest partial + older fresh complete → exact summary uses complete;
- fresh partial never replaces exact counters;
- newest failed + older complete → latest_attempt reports failure while exact summary uses complete according to its age;
- older complete beyond unavailable threshold + fresh partial → exact values unavailable;
- complete zero-client snapshot = exact zero;
- partial/failed zero-row attempt != exact zero;
- multi-page complete semantics preserve capture interval.

## 70. AP / merge tests

Minimum:

- only `type=ap`;
- canonical AP MAC;
- safe metadata;
- raw status retained;
- confirmed code classification;
- unconfirmed code remains other/unknown;
- missing status unknown;
- unknown never becomes offline;
- duplicate AP identity makes snapshot incomplete;
- complete zero-AP inventory valid;
- overlong AP controller text becomes NULL + warning;
- client AP MAC absent from AP inventory keeps client bucket and yields AP health unknown;
- AP inventory row with zero scoped clients remains in AP summary with client count zero;
- AP/client join is MAC-based, never name-based.

## 71. Storage / cleanup tests

Minimum:

- schema v1;
- success/complete constraint;
- composite `(cycle_id, site_id, kind)` FK behavior;
- cross-Site client/AP row rejection;
- client row → AP cycle rejected;
- AP row → client cycle rejected;
- atomic publication;
- failed cycle != empty success;
- complete empty client cycle supported;
- readers do not see half-cycle;
- WAL read/write concurrency;
- cleanup whole cycles only;
- newest attempt/latest complete/latest partial preservation;
- hard cap removes oldest removable cycles;
- retention pressure recorded;
- cleanup cycle larger than configured row transaction budget is removed whole in its own bounded transaction;
- scope version/hash persisted and validated;
- scope-hash change represented without rewriting old cycles.

## 72. Read-service/time/scope tests

Minimum:

- Site isolation;
- latest attempt/latest complete/latest partial separated;
- fresh/stale/unavailable;
- fresh partial cannot replace exact complete;
- source scope/version/hash returned;
- summary uses one exact complete cycle;
- stable keyset cursor;
- cursor cannot change Site/cycle/scope hash/sort/filter;
- no OFFSET;
- allowlist-only sort/filter;
- deterministic NULL ordering;
- bounded page size;
- immutable DTOs;
- readonly DB; no write through service;
- clock regression/future timestamp → unavailable + warning/reason;
- invalid persisted timestamp → unavailable;
- scope hash change inside a 24h prototype window produces partial/incompatible scope and never merges populations.

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
- auth status semantics materially differ from recorded Controller/API evidence;
- AP inventory status cannot be safely classified enough for requested product use;
- controller uptime unit/reset semantics cannot be verified for Home `Online time`;
- `trafficDown/trafficUp` unit or direction differs materially from expected Home labels;
- reliable pagination completeness cannot be established;
- implementation needs historical Observation semantic/schema change;
- safe behavior requires N+1 client detail requests;
- proposed cadence materially impacts Omada/Portal/Observation/Auth;
- byte/disk benchmark rejects the proposed 5M cap;
- short history cannot remain bounded;
- DB target safety/permissions cannot be enforced;
- implementation requires direct Home/Admin → Omada calls.

Continue independent safe parts where possible and report exact evidence. Do not silently weaken semantics.

# PART N — ACCEPTANCE

## 80. Code acceptance

Implementation is accepted only if:

- separate Current State package and schema-v1 DB exist;
- repository default disabled;
- shared provider/token lifecycle reused;
- FINAL Option A independent polling implemented with explicit request telemetry;
- no duplicate Omada HTTP implementation;
- Observation authorized-only meaning unchanged;
- client scope uses exact case-sensitive lossless SSID JSON allowlist;
- scope version/hash implemented;
- all active wireless in-scope auth states represented safely;
- one complete client snapshot drives exact Online/Auth/AP-distribution facts;
- latest attempt/latest complete/latest partial are distinct;
- partial never silently replaces exact current;
- count invariants pass;
- AP inventory status persisted with raw/safe classification;
- AP/client scopes and MAC-based merge behavior are explicit;
- read service Site-scoped/read-only;
- capture-start freshness semantics implemented;
- clock anomaly handling implemented;
- DB path/filesystem/schema/integrity safeguards implemented;
- cross-Site/cross-kind DB constraints pass;
- current table queries bounded to one pinned complete snapshot;
- stable keyset pagination;
- short history bounded by time + measured production-candidate cap;
- cleanup deletes whole cycles only;
- future AP-24h evidence retained without cross-scope mixing;
- required Controller evidence hooks/handoff fields exist;
- targeted/full tests green;
- compileall/diff-check green;
- no Portal/CAPPORT/Auth/Observation regression.

## 81. Production-readiness acceptance and activation/rollback runbook

Implementation merge does **not** authorize activation.

### 81.1 Evidence header

Production acceptance records:

```text
Controller product/build/version
Swagger/OpenAPI version used
OmadaProvider baseline/implementation SHA
Current State config
actual Client/AP request rate
cycle duration statistics
error/partial counts
DB/WAL/SHM paths, modes, owner/group
DB byte size
filesystem free/total bytes
```

### 81.2 Client semantic evidence

Using only designated/approved test devices, record:

```text
authStatus raw values + confirmed meaning
controller_uptime unit
uptime increase behavior
uptime reset/continuity behavior
trafficDown unit
trafficUp unit
trafficDown direction
trafficUp direction
traffic reset behavior
traffic continuity behavior
```

Until traffic direction/unit evidence passes, product UI may only expose neutral controller counters.

### 81.3 AP evidence

Record:

```text
raw AP inventory status code(s)
confirmed online code evidence
confirmed offline code only if actually proven
unknown/other behavior
all expected production AP identities
```

Unknown status never becomes false offline.

### 81.4 Current-state reconciliation

Verify:

- complete Client snapshot exists;
- Controller client inventory reconciles with exact configured SSID scope;
- designated owner device observed through `PENDING → AUTHORIZED`;
- Online invariant;
- Devices-by-AP current distribution;
- AP inventory snapshot complete;
- AP with zero scoped clients remains visible;
- client AP missing from AP inventory yields unknown AP health, not lost client.

### 81.5 Load/coexistence gate

For candidate cadence, record actual request rates and cycle durations and verify:

- existing authorized-only Observation continues accumulating normally;
- Registry/Visit/Analytics remain healthy;
- Auth/Captive Portal/CAPPORT behavior unchanged;
- no material Omada Controller latency/error increase;
- no token lifecycle regression.

30s is accepted only after this evidence passes. Otherwise keep/increase the safer interval.

### 81.6 Storage gate

Record the Part J measurements including:

```text
1.44M-row DB bytes
5M-row projection/measurement
peak WAL
cleanup duration
query durations
filesystem headroom
```

The 5M cap becomes a production value only if the explicit disk-headroom gate passes.

### 81.7 Activation runbook

Required sequence:

```text
1. deploy code with CURRENT_STATE_ENABLED=false
2. validate repository/schema/config/path/permissions while disabled
3. confirm Portal/CAPPORT/Auth baseline
4. enable Current State in production env
5. restart captive-portal.service
6. verify service active and Portal/CAPPORT/Auth baseline again
7. verify Client/AP collectors
8. verify CurrentStateReadService exact/partial/freshness behavior
9. verify Observation coexistence
10. execute semantic/load/storage acceptance gates
```

No future Home production consumption until Current State acceptance passes.

### 81.8 Rollback

Minimum activation rollback:

```text
CURRENT_STATE_ENABLED=false
restart captive-portal.service
verify Portal/CAPPORT/Auth and existing Observation
```

Do **not** delete or recreate `current_state.sqlite3` during rollback. Preserve it for diagnosis.

If code itself causes regression while disabled, use the normal reviewed deployment rollback to the previous application commit; this is separate from the Current State feature-toggle rollback.

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

## 83. Required Coder handoff

When this FINAL is separately authorized for implementation, Coder handoff must include:

```text
exact baseline SHA
implementation SHA
files changed
schema version
config keys/defaults
provider primitives reused
actual request-rate model
cycle/capture timestamp semantics
latest attempt/complete/partial behavior
source-scope version/hash contract
auth classification evidence status
AP status classification evidence status
Controller build/version + Swagger/API version
uptime unit/reset/continuity evidence status
traffic unit/direction/reset/continuity evidence status
targeted/full tests
performance benchmark
DB/WAL size benchmark
cleanup benchmark
query plans
filesystem permission checks
known limitations
production activation NOT performed
```

## 84. Tech Lead review resolution

The DRAFT review is incorporated as follows:

1. separate `current_state.sqlite3` — accepted;
2. reuse existing provider primitives — accepted;
3. acquisition design — **Option A independent repeat polling selected**; no coalescing in this TASK;
4. 30s — production candidate only after load gate; repository-safe disabled default 60s;
5. freshness thresholds `60/180` Client and `90/300` AP — accepted as v1 candidates;
6. 48h retention — accepted; 5M rows gated by byte/disk benchmark;
7. client field set — reduced by removing `controller_client_id`; controller text bounded;
8. auth classification — retained with Controller/API evidence gate;
9. AP raw status — implemented; product offline labels require evidence;
10. current pagination — keyset + cycle/scope pinned; partial/complete selection clarified;
11. AP-24H extra indexes — not pre-authorized; benchmark first;
12. DB/filesystem/composite-FK/cleanup/scope-hash/clock tests and activation rollback — added.

No remaining architecture question is delegated to the Coder by this review.

## 85. Current authorization status

```text
TASK-HOME-CURRENT-STATE-01
FINAL — TECH LEAD REVIEW INCORPORATED

IMPLEMENTATION NOT AUTHORIZED
BRANCH NOT AUTHORIZED
COMMIT NOT AUTHORIZED
PUSH NOT AUTHORIZED
PR NOT AUTHORIZED
PRODUCTION ACTIVATION NOT AUTHORIZED
```

The specification is coder-ready **after a separate explicit Owner implementation authorization**.

Expected next workflow:

```text
Owner implementation authorization
→ Coder implementation/tests
→ Architect static review
→ Tech Lead Linux gate
→ merge/deploy authorization
→ separate production activation/acceptance
→ HOME-LIVE-01
```
