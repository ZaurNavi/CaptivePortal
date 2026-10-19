# TASK-HOME-TRAFFIC-01 — Admin Console Home Current Traffic — LOCKED POST-READ SPEC

**Project:** CaptivPortal  
**Parent:** `TASK-HOME-TRAFFIC-MASTER — FINAL`  
**Dependency:** `TASK-HOME-TRAFFIC-READ-01-FINAL`  
**Type:** locked post-dependency implementation contract  
**Status:** `ARCHITECTURE LOCKED — NOT EXECUTABLE UNTIL EXACT PR A MERGE SHA IS PINNED`  
**Executable FINAL filename after rebind:** `TASK-HOME-TRAFFIC-01-FINAL.md`  
**Baseline:** `MUST BE the actual merge SHA of TASK-HOME-TRAFFIC-READ-01; placeholder execution forbidden`  
**Implementation authorization:** `NOT GRANTED`

---

## 1. Why this is not yet named FINAL

Tech Lead requires Task B to start from one exact already-merged Task A baseline. That SHA does not exist before PR A merge.

Therefore this document locks every Task B architecture choice now, but intentionally refuses execution. After PR A merge the Architect must:

```text
1. fetch actual origin/main
2. verify it is the accepted PR A merge
3. inspect PR A handoff against this contract
4. insert exact merge SHA
5. confirm no source contract changed
6. emit TASK-HOME-TRAFFIC-01-FINAL.md
```

No Coder may begin from this locked spec.

---

## 2. Goal

Add Home Traffic UI/API on top of the accepted `CurrentTrafficReadService`.

```text
CurrentTrafficReadService
→ AdminQueryService
→ /admin/api/v1
→ Home Live Traffic section
```

No collection and no Omada.

---

## 3. Feature flag

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
```

Invariant:

```text
HOME_TRAFFIC=true
requires WEB_ADMIN_ENABLED=true
AND WEB_ADMIN_HOME_LIVE_ENABLED=true
```

Merge/deploy != activation.

---

## 4. Configuration

Repository-safe defaults:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_HOME_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE=100
WEB_ADMIN_HOME_TRAFFIC_FRESH_MAX_AGE_SECONDS=90
WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS=180
WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS=60
```

Bounds:

```text
refresh 60..300
request timeout 5..60
page size 1..250
fresh max 30..300
stale max >= fresh and <=600
max AP skew 10..180
```

Cross-field:

```text
Traffic request timeout > WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

---

## 5. Optional runtime dependency

`CurrentTrafficReadService` is optional to Admin runtime readiness.

```text
Traffic service unavailable
≠ Admin unavailable
≠ Home Live unavailable
```

Feature true + source absent:

```text
Traffic endpoint 503
other Home Live continues
```

Preferred dependency:

```text
analytics_runtime.current_traffic_service
→ AdminQueryService
```

---

## 6. Capabilities

```text
summary → admin.read.overview
AP page → admin.read.observations
```

Do not weaken.

---

## 7. Routes

```text
GET /admin/api/v1/sites/{site_id}/current-traffic/summary
GET /admin/api/v1/sites/{site_id}/current-traffic/aps
```

Use existing `admin.read.v1` envelope.

---

## 8. Route gate order

```text
HTTPS/network/query-size
→ session
→ Site syntax/allowlist
→ capability
→ Traffic feature flag
→ disabled 404
→ endpoint query validation
→ service
```

Add a narrow Traffic-path duplicate-query handling exception analogous to Current State so pre-auth/query parsing does not leak endpoint schema before intended gates.

---

## 9. Summary query

No query parameters.

Response `result` exact shape:

```json
{
  "snapshot": {
    "source_kind": "observation_ap_dynamic",
    "cycle_id": "<id-or-null>",
    "complete": true,
    "evaluated_at": "2026-08-24T13:00:00.000Z",
    "observed_at": "2026-08-24T12:59:42.000Z",
    "newest_observed_at": "2026-08-24T12:59:55.000Z",
    "age_seconds": 18.0,
    "source_skew_seconds": 13.0,
    "freshness_status": "fresh",
    "freshness_reason": "within_freshness_window",
    "latest_attempt_state": "completed",
    "latest_attempt_result": "success",
    "latest_attempt_at": "2026-08-24T12:59:57.000Z",
    "using_previous_complete_snapshot": false
  },
  "freshness_policy": {
    "fresh_max_age_seconds": 90,
    "unavailable_after_seconds": 180,
    "max_ap_skew_seconds": 60
  },
  "traffic": {
    "download_mbps": 42.125,
    "upload_mbps": 6.25,
    "total_mbps": 48.375,
    "unit": "Mbps"
  },
  "source_selection": {
    "primary_source": "wired",
    "selected_source": "wired",
    "selection_reason": "primary_full_coverage",
    "wired_pair_valid_ap_count": 2,
    "lan_pair_valid_ap_count": 2,
    "source_mixing_allowed": false
  },
  "coverage": {
    "coverage_status": "complete",
    "empty_population": false,
    "total_ap_count": 2,
    "valid_rate_ap_count": 2,
    "valid_download_ap_count": 2,
    "valid_upload_ap_count": 2,
    "missing_rate_ap_count": 0,
    "stale_ap_count": 0,
    "unavailable_ap_count": 0,
    "reset_ap_count": 0,
    "gap_rejected_ap_count": 0,
    "no_baseline_ap_count": 0,
    "source_unavailable_ap_count": 0,
    "invalid_elapsed_ap_count": 0,
    "coverage_reasons": []
  }
}
```

No raw counters.

---

## 10. Summary no-cycle shape

HTTP 200:

```text
cycle_id=null
complete=false
selected_source=null
selection_reason=no_complete_snapshot
freshness=unavailable
freshness_reason=no_complete_snapshot
coverage=none
traffic values=null
empty_population=false
```

Latest-attempt fields may still describe a failed/running attempt if available.

---

## 11. Empty-cycle shape

HTTP 200:

```text
real cycle_id
complete=true
selected_source=wired
selection_reason=empty_population
coverage=complete
empty_population=true
download=0.0
upload=0.0
total=0.0
freshness from cycle.finished_at
```

---

## 12. AP endpoint query contract

Allowed:

```text
cycle_id
limit
cursor
```

Rules:

```text
cycle_id required for AP page
cursor without cycle_id → 400
first page cursor omitted
next page same cycle_id + cursor
limit default 100
limit max 250
```

The server derives/validates selected source for the pinned cycle; the browser does not choose an arbitrary source parameter.

Cursor source binding must match the source selected by the service for that pinned cycle.

---

## 13. Full AP page wire contract

Admin envelope:

```json
{
  "api_version": "admin.read.v1",
  "site_id": "<site>",
  "result": {
    "snapshot": {
      "source_kind": "observation_ap_dynamic",
      "cycle_id": "<same-summary-cycle>",
      "evaluated_at": "2026-08-24T13:00:00.000Z",
      "observed_at": "2026-08-24T12:59:42.000Z",
      "newest_observed_at": "2026-08-24T12:59:55.000Z",
      "age_seconds": 18.0,
      "freshness_status": "fresh",
      "freshness_reason": "within_freshness_window"
    },
    "freshness_policy": {
      "fresh_max_age_seconds": 90,
      "unavailable_after_seconds": 180
    },
    "source_selection": {
      "selected_source": "wired",
      "selection_reason": "primary_full_coverage",
      "source_mixing_allowed": false
    },
    "items": [
      {
        "ap_mac": "AA:BB:CC:DD:EE:FF",
        "name": "AP-1",
        "download_mbps": 20.0,
        "upload_mbps": 3.0,
        "total_mbps": 23.0,
        "download_reason": "ok",
        "upload_reason": "ok",
        "rate_status": "valid",
        "observed_at": "2026-08-24T12:59:42.000Z",
        "age_seconds": 18.0,
        "selected_source": "wired"
      }
    ]
  },
  "page": {
    "limit": 100,
    "next_cursor": null,
    "cycle_id": "<same-summary-cycle>",
    "selected_source": "wired"
  }
}
```

No IP, firmware, counters, CPU/RAM or raw controller data.

---

## 14. AP page pinned-cycle behavior

```text
retained valid old complete-success cycle explicitly pinned → allowed
expired/deleted cycle → 400
cycle Site mismatch → 400
cursor cycle/source mismatch → 400
noncanonical cursor → 400
```

---

## 15. Summary unavailable behavior

If summary freshness is unavailable:

```text
Traffic numeric cards show —
AP Traffic request is not sent
AP Traffic rows cleared/hidden
Load More hidden
pagination disabled
```

Local age progression to unavailable performs the same clearing/hiding without waiting for server response.

Next accepted available summary reloads AP first page.

---

## 16. Partial UI behavior

When coverage partial:

```text
numeric direction subtotals are shown only where non-null
all shown partial numeric values labeled Observed subtotal
```

Coverage block MUST show:

```text
Download X/Y APs
Upload   X/Y APs
Both     X/Y APs
```

If one direction is null, that card shows `—`, not zero.

Total is `—` unless both direction subtotals are non-null.

---

## 17. Exact zero UI

```text
0.0 + reason=ok
```

renders as a numeric zero such as:

```text
0.00 Mbps
```

Never use JS truthiness fallback for rate values.

---

## 18. Permission-specific 403 behavior

```text
Traffic summary 403
→ global Site-forbidden state / stop Site Home polling

Traffic AP page 403 after accepted summary
→ keep summary cards
→ stop AP table only
→ show AP detail access denied
```

---

## 19. Top-level Home coordinator

One coordinator owns all Home refresh scheduling.

Phases:

```text
A: Current State Client + AP in parallel (max 2)
B: after both settle, Traffic Summary
C: after accepted non-unavailable summary, Traffic AP first page
```

The shared Refresh button is enabled/disabled only by the coordinator, not independently by Client/AP/Traffic subcontrollers.

Per-request timeouts bound each phase, so Traffic cannot wait indefinitely.

Load More cannot overlap a new refresh.

---

## 20. Source-state isolation

Scheduling is shared; rendering/error state is not.

Traffic error cannot clear:

```text
Online
Authorized/Pending
Devices by AP
Online Devices
Access Points Now
```

Current State error cannot clear still-valid Traffic.

---

## 21. Cross-tab 429 policy

No cross-tab leader election.

429 is retryable and non-destructive.

After 429:

```text
respect Retry-After
minimum retry eligibility 60s
bounded backoff
add per-tab random jitter 0..10s after 429 to desynchronize tabs
```

No immediate retry.

Two-tab production acceptance:

```text
2 tabs
5 automatic cycles each
1 manual refresh in one tab
429 total <=12
no source >3 consecutive eligible 429s in one tab
both tabs recover without reload
```

---

## 22. AbortController ownership

Each subrequest stores:

```text
generation
controller identity
```

Release in finally only if both still match the stored owner.

Old finally cannot clear a newer request.

Pinned-400 clean refresh:

```text
exactly one
new generation
starts only after old lifecycle completed
no overlap
```

---

## 23. Retry policy

Retryable:

```text
network
Abort timeout
429
503
sanitized 500
```

Per Traffic group backoff:

```text
1st failure 60s
2nd 120s
3rd+ 300s max
```

Actual delay:

```text
max(refresh interval, backoff, Retry-After where present)
+ 0..10s jitter after 429 only
```

Success resets Traffic failure count.

Hidden-tab abort is neutral and does not increment failure count.

---

## 24. Visibility behavior

When hidden:

```text
automatic Home refresh stops
outstanding Home requests may be neutrally aborted by coordinator
```

When visible:

```text
one coordinated phased refresh if due
```

No request storm.

---

## 25. Strict enum allowlists

### freshness_status

```text
fresh
stale
unavailable
```

### freshness_reason

```text
within_freshness_window
within_stale_window
age_exceeded
clock_anomaly
no_complete_snapshot
source_unavailable
```

### coverage_status

```text
complete
partial
none
```

### coverage_reasons

```text
missing_direction
missing_pair
temporal_skew
no_valid_rate
empty_population
```

### selection_reason

```text
no_complete_snapshot
empty_population
primary_full_coverage
fallback_full_coverage
fallback_higher_coverage
primary_preferred_tie_or_higher
```

### rate reasons

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

### rate_status

```text
valid
partial
unavailable
```

### latest attempt state

```text
none
running
completed
abandoned
```

### latest attempt result

```text
null
success
partial
failed
shutdown
```

Unknown value → malformed response, no partial DOM update.

---

## 26. Frontend mutual invariants

Validate before DOM mutation:

```text
api_version == admin.read.v1
site_id == current Site
source_kind == observation_ap_dynamic

cycle_id=null ↔ complete=false/no complete snapshot
complete=true ↔ cycle_id non-null

coverage=none → traffic values null
freshness=unavailable → traffic values null

empty_population=true
→ cycle_id non-null
→ selected_source=wired
→ selection_reason=empty_population
→ coverage=complete
→ all traffic values exactly numeric 0.0

selected_source=null
allowed only for no_complete_snapshot state

observed_at <= newest_observed_at <= evaluated_at
age_seconds finite non-negative where timestamps exist

page.cycle_id == accepted summary cycle
page.selected_source == accepted summary source
item.selected_source == page source
```

All UTC timestamps must match canonical project UTC format before use.

Boolean is rejected where numeric expected.

---

## 27. Arithmetic validation

When all three totals numeric:

```text
abs(total - (download + upload)) <= 1e-6
```

Counts:

```text
0 <= valid_rate <= total AP
0 <= valid_download <= total AP
0 <= valid_upload <= total AP
missing_rate = total AP - valid_rate
```

Malformed 200 does not partially render.

---

## 28. Browser freshness progression

Use monotonic browser elapsed time from accepted server age:

```text
performance.now()
```

Local progression:

```text
fresh → stale → unavailable
```

At unavailable:

```text
clear/hide all Traffic/AP numeric data and pagination
```

A network outage cannot leave Fresh forever.

---

## 29. UI placement

Recommended:

```text
Home Live top cards
Traffic Now cards
Traffic freshness + coverage
Traffic by AP
existing Devices by AP
Online Devices
Access Points Now
```

Keep Flask/Jinja/plain CSS/vanilla JS.

No external frontend framework/CDN.

---

## 30. Telemetry

Event:

```text
admin.current_traffic_query_completed
```

Allowed:

```text
request_id
route_name
site_id after authorization
status_code
outcome
allowlisted reason
duration_ms
coverage_status
freshness_status
item_count
```

Forbidden:

```text
AP MAC
client MAC/IP
SSID
cursor
cycle_id
raw URL/query
raw exception
DB path
credentials
Omada payload
```

---

## 31. Mandatory Node gate

Record:

```text
node --version
```

Run:

```bash
node --check app/admin_web/static/admin.js
```

New Traffic frontend behavioral test suite:

```text
PASS
0 skipped because Node unavailable
```

A Node-unavailable skip is a failed Task B gate.

---

## 32. Mandatory frontend behavior tests

At minimum:

```text
phase coordinator max 2 in-tab parallel reads
shared Refresh button ownership
Traffic waits for Phase A settle, not forever
Traffic failure isolation
AP-page 403 summary preservation
summary 403 global state
429 non-destructive/backoff/jitter
late generation ignored
identity-safe finally
pinned-400 exactly-one clean refresh
hidden-tab neutral abort
visibility resume one coordinated refresh
new summary clears old AP rows before page result
summary unavailable skips AP request
local unavailable clears AP rows/pagination
exact zero
partial direction coverage
strict enum/state/timestamp/cycle/source validation
```

---

## 33. Backend/Admin tests

At minimum:

```text
feature default false
feature requires Admin + Home Live
bounds/cross-fields
optional runtime dependency
summary capability
AP capability
disabled 404 after security gates
unknown/duplicate params
AP cursor requires cycle
limit 1..250
retained pinned cycle
expired cycle 400
response allowlist
503 isolation
```

---

## 34. No direct Omada test

New Task B code must not import/call Omada provider/acquisition methods.

Browser HTTP must not trigger Omada.

---

## 35. Full gates

Targeted:

```bash
python -m pytest -q tests/admin_web tests/analytics --tb=short
```

Node gate as section 31.

Full Linux:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
git diff --check
git status --short
```

Record exact counts and Node version.

---

## 36. Production deployment

Code deploy first with:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
```

Validate using same Python/module/environment context as `captive-portal.service`.

Bounded readiness requires both:

```text
systemd active/running
HTTP listener ready
```

Then smoke:

```text
Portal
CAPPORT
Admin login
Home Live
Devices
Visits
Observations
```

Traffic must not render/request while disabled.

---

## 37. Production activation prerequisites

Before Traffic activation:

```text
HOME-LIVE-01 final acceptance PASS
Task A merged/accepted
Task B merged/deployed feature false
clean production tree
exact expected SHA
```

Record actual production source settings:

```text
OBSERVATION_AP_INTERVAL_SECONDS
OBSERVATION_AP_CYCLE_MAX_DURATION_SECONDS
OBSERVATION_RATE_MAX_GAP_SECONDS
```

Require:

```text
Traffic stale max age
>= AP interval + AP cycle max duration
```

unless explicitly reviewed otherwise based on measured production duration.

---

## 38. Production activation

Enable reviewed values in environment, validate in service-equivalent runtime, restart, wait for HTTP readiness.

Then verify:

```text
Home Live existing panels
Traffic summary
Traffic AP page
selected source metadata
coverage/freshness/latest-attempt
Observation cycles continue
Current State cycles continue
Registry/Visit/Analytics continue
Portal/CAPPORT healthy
```

---

## 39. Production two-tab functional soak

Minimum:

```text
5 automatic cycles
1 manual Refresh
1 hidden/visible transition
2 simultaneous visible tabs
```

Verify coordinator, isolation, 429 policy, no overlap, no stale generation append.

Two-tab 429 acceptance exactly as section 21.

---

## 40. Performance gate

Per endpoint:

```text
>=20 successful HTTP 200 latency samples
```

Separate counts:

```text
429
500
503
```

Nearest-rank p95:

```text
rank = ceil(0.95 × N)
```

Targets:

```text
summary p95 <=100ms
AP page p95 <=250ms
```

Only successful 200 durations enter percentile.

---

## 41. Privacy/coexistence gate

No sensitive identity in Traffic telemetry/access-query logging beyond ordinary sanitized access path.

Verify no regression in:

```text
Portal/CAPPORT
Home Live Current State
Devices/Device Card
Visits
Observations
Current State
Observation
Registry
Visit Lifecycle
Analytics
```

---

## 42. Rollback

Fast product rollback:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
restart
HTTP readiness
```

Open-page Traffic 404:

```text
stop Traffic polling only
clear/hide Traffic-specific current data
leave Home Live operational
```

Do not disable/delete Observation or Current State.

---

## 43. Rebind requirement

This locked specification becomes executable FINAL only after:

```text
actual accepted PR A merge SHA is known
```

At that point:

```text
Architecture baseline = exact PR A merge SHA
```

If PR A implementation matches `TASK-HOME-TRAFFIC-READ-01-FINAL`, no other architecture choice is reopened.

If it differs materially, STOP and return for architecture impact review.
