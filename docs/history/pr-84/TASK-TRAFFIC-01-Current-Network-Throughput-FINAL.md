# TASK-TRAFFIC-01 — Current Network Throughput — FINAL

**Проект:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Parent:** `CaptivPortal — Генеральная дорожная карта раздела Admin Console → Traffic — FINAL v1`  
**Dependency:** `TASK-TRAFFIC-00 — Traffic Section Foundation — MERGED / ACCEPTED`  
**Тип:** coder-ready Admin API / Traffic panel implementation specification  
**Статус:** `FINAL — READY FOR EXPLICIT OWNER IMPLEMENTATION AUTHORIZATION`  
**Implementation authorization:** `NOT GRANTED BY THIS FINAL; REQUIRES SEPARATE OWNER AUTHORIZATION`  
**Branch / code / commit / push / PR / merge:** `NOT AUTHORIZED BY THIS FINAL`  
**Production activation:** `NOT GRANTED; SEPARATE OWNER-CONTROLLED ACTION`  
**Дата финализации:** 2026-08-29

---

# 1. Exact post-TRAFFIC-00 rebind

Перед выпуском FINAL фактически проверен current repository.

Canonical implementation baseline:

```text
origin/main =
70b0801db0e115af96cd88faee3f667fa4369aa0

tree =
df3c565ae7e955f2bcc9ad54290473c72a43e657
```

Current main:

```text
Merge pull request #83
TASK-TRAFFIC-00 — Traffic Section Foundation
```

PR #83 implementation commit:

```text
8648fcec1ee795ecca8387a2265a960a0637060a
```

Previous baseline:

```text
c719525a1a2a324a0959597c993b99a82bf465b0
```

is historical for `TRAFFIC-01` and MUST NOT be used as the implementation baseline.

If `origin/main` changes after this FINAL and before implementation authorization:

```text
git fetch origin
git rev-parse origin/main
```

must be repeated.

If newer main touches any of:

```text
app/admin_web/routes.py
app/admin_web/query_service.py
app/admin_web/current_traffic_serialization.py
app/admin_web/static/admin.js
app/admin_web/templates/admin/traffic.html
app/analytics/current_traffic.py
app/analytics/runtime.py
```

then implementation MUST stop for Architect / Tech Lead impact review before coding.

---

# 2. Verified TRAFFIC-00 dependency

Merged Foundation now already provides:

```text
AdminPage("traffic", "Traffic", "admin/traffic.html")
GET /admin/sites/<site_id>/traffic
Traffic navigation entry
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
shared Traffic page dataset
window.CaptivPortalTrafficCoordinator
```

Public coordinator API:

```text
registerPanel(...)
refreshPanel(...)
refreshAll(...)
```

Coordinator already owns:

```text
one initial execution per registered panel
periodic scheduling for autoRefresh=true
manual refresh
per-panel generation
per-panel AbortController
request timeout
visibilitychange
pagehide
Retry-After/backoff
panel-local failure isolation
global 401/403 boundary
same-origin Site Traffic API request helper
```

Therefore `TRAFFIC-01` MUST consume this Foundation contract.

It MUST NOT create another Traffic page lifecycle owner.

---

# 3. TRAFFIC-00 acceptance state

PR #83 recorded:

```text
Coder focused tests:
23 passed

Central Lab exact worktree gate:
PASS

strict regressions:
0

compileall:
PASS

git diff --check:
PASS

production activation:
NO
```

Thus `TRAFFIC-00` is an accepted dependency.

Production may still have:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
```

and `TRAFFIC-01` does not change that operational fact.

---

# 4. Goal

Add the first real product panel to the existing Traffic page:

```text
Current Network Throughput
```

The panel answers:

```text
Какой принятый Site Network Throughput
виден по persisted AP/network evidence сейчас?
```

Visible primary metrics:

```text
Download Now
Upload Now
Total Now
```

Unit:

```text
Mbps
```

Also surface:

```text
selected source family
freshness
coverage
product-safe evidence/provenance state
```

No historical range or AP history is implemented here.

---

# 5. Product meaning

`Current Network Throughput` means:

```text
current Site AP physical/network throughput evidence
```

It MUST NOT be presented as:

```text
Internet Traffic
WAN Traffic
Internet Usage
Billing Traffic
Guest Session Traffic
Completed Guest Traffic
Zefer_Parki Traffic
SSID Traffic
```

Required persistent helper meaning:

```text
Derived from persisted AP traffic counters.
May include local/service traffic and is not an Internet-only measurement.
```

Final Web Designer wording may later improve presentation but MUST preserve this meaning.

---

# 6. Semantic domain

This TASK belongs only to:

```text
A. NETWORK TRAFFIC
```

It does not implement:

```text
B. GUEST SESSION TRAFFIC
```

Guest Session Traffic remains a later product domain based on Visit Lifecycle / completed-session evidence.

Never combine their values.

---

# 7. Canonical data owner

The existing semantic/read owner remains:

```text
CurrentTrafficReadService
```

Canonical path:

```text
Omada current AP primitives
        ↓
Observation acquisition
        ↓
persisted Observation AP facts
        ↓
CurrentTrafficReadService
        ↓
AdminQueryService.current_traffic_summary()
        ↓
existing safe serializer
        ↓
Traffic Site API
        ↓
Traffic coordinator
        ↓
Current Network Throughput panel
```

Permanent boundary:

```text
acquisition != product read
```

---

# 8. Explicit zero-duplicate-calculation rule

`TRAFFIC-01` MUST NOT calculate current throughput independently from Home.

Both product surfaces consume the same semantic owner:

```text
CurrentTrafficReadService
```

Forbidden:

```text
Home calculation A
Traffic calculation B

Traffic route reads raw Observation rows
and computes its own Site total

Traffic browser computes Site throughput
from AP rows
```

Presentation formatting may differ where explicitly defined.

Numeric meaning MUST NOT diverge by product surface.

---

# 9. Existing application/read contract — exact reuse

Current repository already contains:

```python
AdminQueryService.current_traffic_summary(
    principal,
    site_id,
)
```

This method already:

```text
authorizes Site overview access
uses the shared Admin query concurrency/deadline gate
calls CurrentTrafficReadService.get_current_site_traffic(...)
uses the existing Current Traffic policy
serializes through serialize_current_traffic_summary(...)
maps read/serialization failures safely
```

`TRAFFIC-01` MUST reuse this exact method.

Do NOT add:

```text
traffic_current_summary()
traffic_section_current_summary()
another current Traffic query service
```

unless current repository facts change and Architect explicitly reopens the decision.

---

# 10. Existing serializer — exact reuse

Current backend serializer:

```python
serialize_current_traffic_summary(...)
```

in:

```text
app/admin_web/current_traffic_serialization.py
```

is the canonical Admin Current Traffic summary serializer.

Its result shape is already domain-suitable:

```text
result
├── snapshot
├── freshness_policy
├── traffic
├── source_selection
└── coverage
```

`TRAFFIC-01` MUST reuse it.

Do NOT create a second backend serializer with independent semantics.

A frontend validator/render adapter is allowed because browser safety/presentation is not a second backend semantic serializer.

---

# 11. Existing shared Current Traffic policy

Current `AdminQueryService.current_traffic_summary()` obtains the accepted policy from existing config fields:

```text
home_traffic_fresh_max_age_seconds
home_traffic_stale_max_age_seconds
home_traffic_max_ap_skew_seconds
```

Current accepted defaults:

```text
fresh max age = 90s
stale/unavailable boundary = 180s
max AP skew = 60s
```

For `TRAFFIC-01 v1`, these remain the single shared Current Traffic semantic policy.

Do NOT add a second Traffic-specific fresh/stale/skew policy.

Legacy Home-prefixed naming is accepted implementation debt.

Renaming this shared policy is outside this TASK.

---

# 12. Foundation refresh policy is different

Existing Foundation values:

```text
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
```

are page/orchestration policy only.

They MUST NOT redefine:

```text
Current Traffic fresh/stale thresholds
AP source skew
Observation cadence
source-selection policy
```

Permanent distinction:

```text
browser refresh interval
!=
source freshness policy
```

---

# 13. CurrentTrafficReadService semantics remain unchanged

Machine source values remain:

```text
primary_source = "wired"

selected_source =
"wired"
|
"lan"
|
null
```

Radio is excluded from Site Current Traffic total.

No browser/API parameter may select source family.

---

# 14. Source-family selection remains owned by read service

Existing canonical behavior remains authoritative.

Conceptually:

```text
wired full pair coverage → wired
else lan full pair coverage → lan
else family with higher valid pair coverage
tie / wired higher → wired
```

One Site result uses one selected source family.

Forbidden:

```text
AP-1 wired
+
AP-2 lan
→ Site total
```

No source mixing.

---

# 15. Direction semantics

Accepted mappings remain:

```text
wired Download = wired_download_mbps
wired Upload   = wired_upload_mbps

lan Download = lan_rx_mbps
lan Upload   = lan_tx_mbps
```

Research independently supports:

```text
LAN RX ≈ RADIO TX ≈ CLIENT DOWN
CLIENT UP ≈ RADIO RX ≈ LAN TX
```

Small cross-layer differences are not defects because collection is asynchronous and accounting layers differ.

`wired_activity_raw` remains diagnostic/cross-check evidence only.

It MUST NOT replace directional Download/Upload.

---

# 16. No new acquisition / schema

`TRAFFIC-01` MUST NOT introduce:

```text
new Observation acquisition
new Omada polling
new collector
new DB
schema migration
new AP telemetry writer
new Current State calculation pipeline
new persisted Traffic current table
```

If persisted evidence is stale, degraded, partial or unavailable:

```text
surface existing quality semantics
```

Do not repair data in Admin UI.

---

# 17. Explicit no-Omada product path

Forbidden:

```text
Browser → Omada
Admin route → Omada
Traffic panel → Omada
Admin request → force Observation cycle
Admin request → increase Omada polling
```

Also forbidden as product source:

```text
Loki
Grafana
Alloy
raw logs
```

---

# 18. Omada Traffic research binding

`TRAFFIC-SOURCE-RESEARCH-01` found no superior native Site-wide current throughput source.

Useful native historical endpoints remain:

```text
dashboard/traffic-activities
dashboard/traffic-distribution
```

but those are:

```text
VALIDATION / REFERENCE
```

for later historical tasks, not `TRAFFIC-01` product dependencies.

Therefore `TRAFFIC-01` uses no new Omada API surface.

---

# 19. Exact new Traffic API endpoint

Canonical endpoint for this TASK:

```text
GET /admin/api/v1/sites/<site_id>/traffic/current
```

Query parameters:

```text
NONE
```

Any supplied query parameter:

```text
400 invalid_request
```

This endpoint lives inside the namespace reserved by `TRAFFIC-00`.

---

# 20. API security ordering

The new Traffic data endpoint MUST preserve the existing Admin security boundary.

Conceptual order:

```text
authenticated Admin session
        ↓
resolve canonical Site
        ↓
authorize admin.read.context
        ↓
check WEB_ADMIN_TRAFFIC_ENABLED
        ↓
execute Current Traffic application query
```

The reused:

```python
AdminQueryService.current_traffic_summary(...)
```

also performs its existing internal:

```text
admin.read.overview
```

authorization before reading data.

Current v1 platform-operator policy authorizes both capabilities, but both layers remain explicit and permissions-ready.

Do not create a Traffic-specific Site resolver or policy implementation.

---

# 21. Feature gate

The new endpoint is controlled by the already merged master flag:

```text
WEB_ADMIN_TRAFFIC_ENABLED
```

When false:

```text
authorized Site request
→ 404 not_found
```

The feature gate is checked only after existing authentication/Site authorization boundary.

Do not add a second panel flag for `TRAFFIC-01`.

---

# 22. Home Traffic feature independence

Existing Home Current Traffic endpoint remains controlled by:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED
```

New Traffic endpoint is controlled by:

```text
WEB_ADMIN_TRAFFIC_ENABLED
```

Required behavior:

```text
Home Traffic=false / Traffic=true
→ Traffic current endpoint may work

Home Traffic=true / Traffic=false
→ existing Home Current Traffic continues to work

both=true
→ both surfaces use same semantic owner/serializer

both=false
→ no product surface, shared backend service remains unaffected
```

Do not tie `CurrentTrafficReadService` lifecycle to either presentation flag.

---

# 23. Narrow route-helper refactor

Current `_current_traffic_query(...)` already owns the accepted Site/query/error path for Home Current Traffic but currently gates through:

```text
config.home_traffic_enabled
```

Preferred exact implementation change:

```text
parameterize the helper with an explicit feature_enabled argument
```

Conceptually:

```python
_current_traffic_query(
    site_id,
    *,
    route_name,
    capability,
    feature_enabled,
    allowed_parameters,
    required_parameters,
    operation,
)
```

Existing Home routes pass:

```text
feature_enabled=config.home_traffic_enabled
```

New Traffic route passes:

```text
feature_enabled=config.traffic_enabled
```

The rest of helper behavior remains unchanged.

Do not copy/paste a second full Current Traffic route error stack.

---

# 24. New endpoint execution

Preferred route call:

```python
_current_traffic_query(
    site_id,
    route_name="traffic_current",
    capability="admin.read.context",
    feature_enabled=config.traffic_enabled,
    allowed_parameters=frozenset(),
    required_parameters=frozenset(),
    operation=lambda service, selected:
        service.current_traffic_summary(
            g.admin_principal,
            selected,
        ),
)
```

Exact local variable spelling may differ.

Semantic requirements may not.

---

# 25. Existing Home endpoint must remain unchanged

Existing:

```text
GET /admin/api/v1/sites/<site_id>/current-traffic/summary
```

continues to:

- use the existing Home feature gate;
- use the same `AdminQueryService.current_traffic_summary()`;
- return the same existing contract;
- preserve current error behavior.

No Home URL migration.

No Home browser change.

No Home template change.

---

# 26. API result contract

`result` is exactly the existing:

```python
serialize_current_traffic_summary(...)
```

result.

No Traffic-specific backend transformation.

Top-level result:

```text
snapshot
freshness_policy
traffic
source_selection
coverage
```

---

# 27. `traffic` contract

Canonical:

```json
{
  "download_mbps": "<float|null>",
  "upload_mbps": "<float|null>",
  "total_mbps": "<float|null>",
  "unit": "Mbps"
}
```

Rules are already enforced by backend serializer.

Required product behavior:

```text
numeric 0.0 → valid zero
null → missing/unavailable → display —
```

Browser MUST NOT calculate `total_mbps` from Download + Upload.

It displays backend `total_mbps`.

---

# 28. `snapshot` product evidence

Existing safe fields include:

```text
source_kind
cycle_id
complete
evaluated_at
observed_at
newest_observed_at
age_seconds
source_skew_seconds
freshness_status
freshness_reason
latest_attempt_state
latest_attempt_result
latest_attempt_at
using_previous_complete_snapshot
selected_source
selection_reason
empty_population
```

No raw DB path.

No provider payload.

No Omada token.

No internal exception.

---

# 29. `source_selection` product evidence

Existing safe fields:

```text
primary_source
selected_source
selection_reason
source_mixing_allowed
wired_pair_valid_ap_count
lan_pair_valid_ap_count
```

Permanent:

```text
source_mixing_allowed = false
```

Browser cannot override source choice.

---

# 30. `coverage` product evidence

Existing safe fields include:

```text
coverage_status
coverage_reasons
empty_population
total_ap_count
valid_rate_ap_count
valid_download_ap_count
valid_upload_ap_count
missing_rate_ap_count
stale_ap_count
unavailable_ap_count
reset_ap_count
gap_rejected_ap_count
no_baseline_ap_count
source_unavailable_ap_count
invalid_elapsed_ap_count
```

`TRAFFIC-01` UI does not need to expose every counter.

The API preserves the existing safe semantic contract.

---

# 31. No-snapshot state

If there is no canonical complete-success AP dynamic snapshot, existing service returns a product quality result rather than a source exception.

Expected conceptual result:

```text
cycle_id = null
selected_source = null
freshness_status = unavailable
coverage_status = none
traffic values = null
selection_reason = no_complete_snapshot
```

HTTP:

```text
200
```

Panel:

```text
Unavailable
—
```

Do not display `0 Mbps`.

---

# 32. Valid empty population

Existing accepted special case:

```text
empty_population = true
coverage_status = complete
selected_source = wired

download_mbps = 0.0
upload_mbps = 0.0
total_mbps = 0.0
```

This is a real accepted zero.

UI MUST display it as zero, not unavailable.

---

# 33. Integrity/source failure

Contradictory persisted source, schema/storage failure or source-read failure:

```text
AdminQueryUnavailable
→ HTTP 503 source_unavailable
```

Do not:

```text
fallback to Omada
repair source
show cached fabricated zero
```

Panel failure remains panel-local.

---

# 34. HTTP error contract

Reuse existing safe Admin Current Traffic semantics.

Expected:

```text
401 authentication_required
→ Foundation coordinator global auth state

403 site_forbidden
→ Foundation coordinator global Site/auth state

404 not_found
→ Traffic master feature disabled

400 invalid_request
→ invalid Site/query contract

429 concurrency_limit
→ Retry-After
→ coordinator backoff

503 query_deadline
→ coordinator timeout classification

503 source_unavailable
→ panel-local unavailable failure

503 response_too_large
→ safe unavailable failure

500 internal_error
→ sanitized unexpected failure
```

No raw traceback/provider/SQLite details.

---

# 35. Traffic Foundation integration — mandatory

The new panel MUST register through:

```text
window.CaptivPortalTrafficCoordinator
```

Canonical panel key:

```text
current-network-throughput
```

Recommended registration:

```javascript
coordinator.registerPanel({
  key: "current-network-throughput",
  autoRefresh: true,
  load,
  render,
  renderLoading,
  renderFailure,
});
```

No second coordinator.

No direct `fetch()` from panel code.

---

# 36. Initial execution semantics

Merged Foundation guarantees:

```text
every successful registerPanel(...)
→ one initial execution
```

Therefore `TRAFFIC-01` MUST NOT manually invoke an initial fetch after registration.

Required:

```text
register panel
→ exactly one initial execution
```

Not:

```text
register panel
+
panel immediately calls refreshPanel()
→ two initial requests
```

---

# 37. Periodic refresh semantics

`TRAFFIC-01` uses:

```text
autoRefresh=true
```

Therefore:

```text
initial execution
→ successful execution
→ coordinator schedules next execution
  according to WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
```

No private `setInterval`, `setTimeout`, or poll loop inside the panel.

---

# 38. Global Refresh semantics

Existing Traffic page `Refresh` button is owned by Foundation.

It calls:

```text
refreshAll({manual:true})
```

`TRAFFIC-01` must not attach another listener to the global Refresh button.

Current panel participates because it is registered.

---

# 39. Panel-specific refresh

`TRAFFIC-01 v1` requires no dedicated panel-specific Refresh control.

Therefore no new button is added solely to call `refreshPanel(...)`.

If implementation later introduces a justified current-panel-specific trigger, it MUST use:

```text
refreshPanel("current-network-throughput", {manual:true})
```

and MUST NOT call `load()`, `fetch()`, or `requestJson()` directly.

---

# 40. Coordinator request helper

Panel loader uses only coordinator-provided:

```text
requestJson
```

Expected:

```text
load(context)
→ context.requestJson(
    `${context.apiBase}/traffic/current`
  )
```

Foundation enforces same-origin and current Site Traffic API namespace.

No arbitrary external URL construction.

---

# 41. No panel-owned lifecycle

Panel MUST NOT own:

```text
AbortController
request timeout
generation counter
visibilitychange
pagehide
Retry-After
backoff
periodic timer
global auth state
```

These remain Foundation coordinator responsibilities.

---

# 42. Panel markup

Modify existing:

```text
app/admin_web/templates/admin/traffic.html
```

to add one functional panel inside:

```text
#traffic-panels
```

Recommended semantic structure:

```text
Current Network Throughput
helper meaning

Download Now
Upload Now
Total Now

Traffic evidence:
Source
Freshness
Coverage
Last evaluated / observed
```

Reuse existing Admin CSS classes where practical.

No final Web Designer redesign.

---

# 43. Recommended stable panel hooks

Required stable hooks:

```text
traffic-current-panel
traffic-current-state
traffic-current-state-title
traffic-current-state-message
traffic-current-download
traffic-current-upload
traffic-current-total
traffic-current-source
traffic-current-freshness
traffic-current-coverage
traffic-current-updated
```

These become frontend functional contracts and must be tested.

No AP table in this TASK.

---

# 44. Existing Foundation empty state

Current Foundation owns:

```text
traffic-empty-state
```

When TRAFFIC-01 template/JS is present and registration succeeds:

```text
Foundation coordinator hides empty state
```

No manual duplicate empty-state logic.

If the `TRAFFIC-01` panel is absent/not registered:

```text
existing zero-panel Foundation behavior remains valid:
empty state visible
Refresh disabled
zero product requests
```

This is a mandatory regression invariant.

---

# 45. Panel loading state

Before accepted result:

```text
state = loading
```

Visible concept:

```text
Loading current network throughput…
```

Metrics:

```text
—
```

During later refresh, implementation may preserve the last accepted values while indicating refresh state only if stale data is not presented as newly accepted. A simpler v1 implementation may keep the current accepted result until replacement succeeds.

---

# 46. Panel ready/degraded/unavailable mapping

The browser does not calculate source semantics.

It maps accepted backend fields to presentation.

Recommended UI mapping:

```text
fresh + complete
→ Ready
→ <Source> · Fresh · Complete

fresh + partial
→ Degraded
→ <Source> · Fresh · Partial

stale + usable evidence
→ Degraded
→ <Source> · Stale · <Coverage>

freshness unavailable OR coverage none
→ Unavailable
→ —
```

Transport/source failure becomes a safe panel-local failure.

Do not convert source partial into page-global failure.

---

# 47. Source label mapping

Presentation-only mapping:

```text
selected_source = "wired"
→ Wired

selected_source = "lan"
→ LAN fallback

selected_source = null
→ Source unavailable
```

Do not expose a source-selection control.

---

# 48. Freshness label mapping

Use backend:

```text
snapshot.freshness_status
```

Allowed:

```text
fresh
stale
unavailable
```

Presentation:

```text
Fresh
Stale
Unavailable
```

`TRAFFIC-01` MUST NOT implement a second source freshness algorithm from browser wall-clock time.

The next periodic read obtains a new backend evaluation.

---

# 49. Coverage label mapping

Use backend:

```text
coverage.coverage_status
```

Allowed:

```text
complete
partial
none
```

Presentation:

```text
Complete
Partial
Unavailable
```

Coverage reasons may be shown as safe secondary detail but are not required for first visual implementation.

---

# 50. Numeric formatting

Presentation formatting:

```text
number
→ fixed two decimal places + " Mbps"

null
→ "—"
```

Examples:

```text
0.0 → 0.00 Mbps
12.437 → 12.44 Mbps
null → —
```

Formatting does not change metric meaning.

Browser does not recompute Total.

---

# 51. Frontend DTO validation

Panel loader/render adapter MUST validate enough of the safe result to fail closed on malformed data.

At minimum verify:

```text
payload is object
payload.result is object
result.traffic.unit == "Mbps"

download/upload/total:
finite non-negative number or null

snapshot.freshness_status:
fresh | stale | unavailable

snapshot.selected_source:
wired | lan | null

source_selection.selected_source:
matches snapshot.selected_source

coverage.coverage_status:
complete | partial | none
```

A malformed successful HTTP payload becomes:

```text
panel-local safe unexpected failure
```

Do not render unchecked strings as product state.

No `innerHTML`.

---

# 52. Panel failure isolation

Ordinary panel failures:

```text
429
503
request timeout
source_unavailable
malformed DTO
```

remain local to Current Network Throughput.

They MUST NOT:

```text
replace whole Traffic page
stop unrelated future panels
convert to global Traffic failure
```

Foundation coordinator owns retry eligibility.

---

# 53. Global auth failure ownership

Existing Foundation contract remains:

```text
401
403
```

may promote:

```text
traffic-global-state
```

and pause page refresh.

`TRAFFIC-01` renderFailure MUST NOT duplicate global auth handling.

---

# 54. Cross-surface semantic equality — corrected FINAL rule

Permanent invariant:

```text
Home Current Traffic
and
Traffic Current Network Throughput

use:
same semantic owner
same source-family contract
same Current Traffic policy
same serializer meaning
```

Exact numeric equality is required only under:

```text
SAME FIXED SOURCE / EVALUATION CONTEXT
```

Valid automated proof may use:

```text
same injected fake CurrentTrafficReadService result
or
same frozen source snapshot + same evaluated_at
or
another harness forcing identical read result
```

Then:

```text
same source context
→ same semantic result
```

---

# 55. Separate live evaluations may legitimately differ

Forbidden acceptance assumption:

```text
GET Home at t1
GET Traffic at t2
→ exact numeric equality required
```

Between `t1` and `t2`:

```text
Observation may advance
canonical cycle may change
evaluated_at may change
freshness may age
```

Therefore:

```text
SEPARATE LIVE EVALUATIONS
MAY LEGITIMATELY DIFFER
```

This is not semantic drift by itself.

---

# 56. Fixed-context equality fields

Under one fixed source/evaluation context, compare:

```text
snapshot.cycle_id
snapshot.selected_source
snapshot.selection_reason
snapshot.freshness_status
snapshot.freshness_reason

traffic.download_mbps
traffic.upload_mbps
traffic.total_mbps
traffic.unit

source_selection
coverage
```

`evaluated_at` is compared exactly only when the test explicitly freezes/forces the same evaluation timestamp/result.

---

# 57. Home boundary

`TRAFFIC-01` does not redesign or expand Home.

Do NOT change:

```text
app/admin_web/templates/admin/home.html
```

No new Home card.

No Home label/layout change.

No Home coordinator redesign.

The only shared behavior change allowed is the narrow `routes.py` helper parameterization required to let Home and Traffic use the same Current Traffic route machinery with independent product flags.

---

# 58. No Home frontend refactor required

Current Traffic panel on Traffic page does not need to reuse Home DOM/hooks.

Shared ownership is guaranteed at:

```text
CurrentTrafficReadService
+
AdminQueryService.current_traffic_summary()
+
serialize_current_traffic_summary()
```

not by forcing two pages to share one DOM component.

---

# 59. Exact expected implementation scope after rebind

Based on `main@70b0801d...`, expected changed files:

```text
app/admin_web/routes.py
app/admin_web/static/admin.js
app/admin_web/templates/admin/traffic.html
```

Expected new focused tests:

```text
tests/admin_web/test_traffic_current.py
tests/admin_web/test_traffic_current_frontend.py
```

No other production file is currently required.

---

# 60. Expected unchanged files

These should remain unchanged:

```text
app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/current_traffic_serialization.py
app/admin_web/templates/admin/base.html
app/admin_web/templates/admin/home.html
app/admin_web/static/admin.css

app/analytics/current_traffic.py
app/analytics/source_gateway.py
app/analytics/models.py
app/analytics/runtime.py

app/config.py
app/settings.py
.env.example
```

If implementation requires changing an expected-unchanged file:

```text
STOP
→ report exact factual reason
→ Architect / Tech Lead impact review
```

Do not silently expand scope.

---

# 61. Forbidden scope

Do NOT change:

```text
Observation acquisition/writers/schema
Current State acquisition/schema
Visit Lifecycle
Visitor Registry
Auth/CAPPORT
Pending Session Cleaner
OmadaProvider/controllers
Loki/Grafana/Alloy
systemd
reverse proxy
requirements/dependencies
production env
```

No new DB.

No migration.

---

# 62. No Traffic telemetry dependency

`TRAFFIC-01` does not require a new Loki/Grafana telemetry stream.

Existing Admin/request logging is sufficient for the feature increment.

Product correctness comes from the application/read contract.

---

# 63. API output size / query bounds

The reused query service already executes through shared Admin controls:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
WEB_ADMIN_MAX_RESPONSE_BYTES
```

Current Site summary returns one bounded result.

No pagination.

No AP item list.

No historical window.

---

# 64. Feature-disabled behavior

With:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
```

Foundation remains authoritative:

```text
Traffic navigation absent
Traffic page authorized request → 404
Traffic product API authorized request → 404
```

No production activation is implied by implementation.

---

# 65. Traffic enabled / source unavailable

With Traffic enabled but Current Traffic source unavailable:

```text
Traffic page still renders
Current Network Throughput panel fails safely/local
other future Traffic panels remain independent
```

Do not make the Traffic HTML page unavailable because one read service is unavailable.

---

# 66. Coder testing ownership — FINAL corrected rule

Coder may:

```text
add/change TRAFFIC-01 focused tests
run minimal TASK/module tests
verify new Traffic route/panel/coordinator integration
run relevant syntax/compile checks
run git diff --check
```

Coder MUST NOT independently execute:

```text
existing Home broader regression
cross-module broader regression
full tests/admin_web
full repository pytest
Central Lab gate
baseline/candidate differential
official release gate
```

Those belong to:

```text
Owner + Tech Lead / Central Lab
```

---

# 67. Focused Coder backend tests

New:

```text
tests/admin_web/test_traffic_current.py
```

At minimum:

```text
Traffic enabled + authorized Site
→ /traffic/current 200

no query parameters allowed

Traffic disabled
→ authorized request 404

invalid Site → 400
forbidden Site → 403
missing session → 401

fixed valid Current Traffic result
→ exact existing serializer result

no complete snapshot
→ 200 unavailable/null product state

empty population
→ 200 valid 0.0 Mbps

source unavailable
→ 503 source_unavailable

query busy
→ 429 + Retry-After

query deadline
→ 503 query_deadline
```

Do not duplicate broad Home tests.

---

# 68. Focused Coder frontend tests

New:

```text
tests/admin_web/test_traffic_current_frontend.py
```

At minimum prove:

```text
panel registers only on Traffic page when DOM hooks exist
key = current-network-throughput
autoRefresh=true
registration causes exactly one initial execution
panel uses coordinator-provided requestJson
URL = <apiBase>/traffic/current
no direct global fetch call from panel
ready result renders Download/Upload/Total
valid 0.0 renders 0.00 Mbps
null renders —
wired label renders Wired
lan label renders LAN fallback
fresh/complete renders ready
fresh/partial renders degraded
stale renders degraded
unavailable renders unavailable
renderFailure remains panel-local
panel adds no visibility/pagehide listener
panel adds no private timer
panel adds no global Refresh listener
```

Foundation coordinator lifecycle itself is not reimplemented in these tests.

---

# 69. Coder focused/minimal command

Expected:

```bash
python -m pytest -q   tests/admin_web/test_traffic_current.py   tests/admin_web/test_traffic_current_frontend.py
```

Static checks:

```bash
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app/admin_web

git diff --check
```

No broader suite by Coder.

---

# 70. Cross-surface equality test ownership

The FINAL requires fixed-context Home↔Traffic semantic proof.

Coder may:

```text
prepare fixture/helper/test evidence
needed for this comparison
```

but official execution of the cross-surface regression belongs to:

```text
Owner + Tech Lead / Central Lab
```

It MUST NOT be added to the Coder focused command if it exercises existing Home behavior as regression evidence.

---

# 71. Preferred Central Lab fixed-context proof

Central Lab should force both routes to consume the same deterministic Current Traffic source result.

Example:

```text
inject/fake CurrentTrafficReadService
return one fixed immutable CurrentSiteTraffic
```

Then call:

```text
GET /admin/api/v1/sites/<site_id>/current-traffic/summary

GET /admin/api/v1/sites/<site_id>/traffic/current
```

with both feature flags enabled.

Compare:

```text
home_response["result"]
==
traffic_response["result"]
```

when the fake/evaluation result is intentionally identical.

---

# 72. Central Lab must NOT use sequential live equality as a gate

Do NOT fail candidate merely because live Home and later live Traffic requests show slightly different current values/cycles.

Live comparison may be used diagnostically but not as an exact equality assertion unless source/evaluation context is pinned.

---

# 73. Central Lab feature independence proof

Official acceptance must verify:

```text
Home flag=false / Traffic=true
→ Traffic endpoint works if source available

Home=true / Traffic=false
→ Home Current Traffic unchanged

both=true
→ both routes available

both=false
→ neither surface exposed; shared semantic owner not shut down
```

---

# 74. Central Lab Home regression

Because `routes.py` Current Traffic helper is shared, Central Lab must run existing relevant Home Current Traffic regression on the exact candidate.

Coder does not own this execution.

Verify:

```text
existing Home current-traffic URL unchanged
existing Home feature gate unchanged
existing Home result contract unchanged
existing Home frontend behavior unchanged
```

No Home template change is expected.

---

# 75. Central Lab Traffic Foundation regression

Central Lab should verify accepted TRAFFIC-00 contract remains intact:

```text
one coordinator owner
one initial execution
autoRefresh contract
refreshAll ownership
refreshPanel contract
Retry-After/backoff
same-origin request enforcement
panel failure isolation
global 401/403 behavior
zero-panel behavior when panel absent/not registered
```

The new panel is a consumer of Foundation, not a replacement.

---

# 76. Current Central Lab runner evidence and anti-drift rule

As of the rebind request, the currently verified Windows runner is reported as:

```text
C:\CaptivPortal-Lab\lab-test-v6-fixed.cmd
```

Canonical current invocation was reported as:

```text
call C:\CaptivPortal-Lab\lab-test-v6-fixed.cmd C:\CaptivPortal-UI-Preview
```

This is current evidence, NOT a timeless TASK constant.

Permanent anti-drift rule:

```text
documented runner version
!=
automatically current runner version
```

Before official full gate, Owner / Tech Lead MUST verify:

```text
exact candidate
exact baseline
current approved Central Lab runner
current compatibility baseline
```

Official acceptance uses the CURRENT VERIFIED runner at execution time.

---

# 77. Central Lab official acceptance

Owner + Tech Lead / Central Lab own:

```text
exact-candidate focused rerun as appropriate
shared Home regression
Traffic Foundation regression
fixed-context cross-surface semantic equality
broader/full regression according to current release policy
baseline/candidate differential
official PASS/FAIL
```

Coder results are input evidence, not official release acceptance.

---

# 78. Browser acceptance

Controlled authenticated browser acceptance with Traffic enabled:

```text
Traffic nav visible
Traffic page opens
Current Network Throughput panel visible
one initial request occurs
values render in Mbps
source label visible
freshness visible
coverage visible
manual global Refresh triggers coordinator refresh
periodic refresh follows Foundation cadence
no duplicate request loop
no console exception
```

---

# 79. Browser network acceptance

Expected product request:

```text
/admin/api/v1/sites/<site_id>/traffic/current
```

Forbidden browser requests:

```text
Omada Controller
Analytics bearer API
Loki
Grafana
external origin
```

---

# 80. Panel failure browser acceptance

Controlled:

```text
/traffic/current → 503 source_unavailable
```

must produce panel-local unavailable state while Traffic page and unrelated panels remain independent.

---

# 81. Auth failure browser acceptance

Controlled:

```text
401
or
403
```

continues to use Foundation global behavior.

`TRAFFIC-01` must not install a second auth/session redirect mechanism.

---

# 82. No production activation in implementation

Implementation/merge MUST NOT automatically change production:

```text
WEB_ADMIN_TRAFFIC_ENABLED
```

No production env change.

No production restart instruction is implied by this FINAL.

---

# 83. Governance separation

Permanent:

```text
implementation authorization
!=
merge authorization
!=
deployment
!=
production activation
```

Expected:

```text
FINAL
→ explicit Owner implementation authorization
→ Coder implementation
→ Coder focused/minimal tests
→ Owner + Tech Lead Central Lab acceptance
→ Owner merge authorization
→ merge
→ optional dormant deploy
→ separate Owner production activation decision
```

---

# 84. Recommended dormant deployment

Safe default:

```text
deploy code
with
WEB_ADMIN_TRAFFIC_ENABLED=false
```

until Owner explicitly activates Traffic.

---

# 85. Production activation — later separate action

If later authorized:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
```

Activation verification should confirm:

```text
Traffic nav visible
Traffic page 200
/traffic/current behaves safely
Home unchanged
Observation unchanged
no browser → Omada
```

This activation is NOT granted by this FINAL.

---

# 86. Rollback

Operational rollback after future activation:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
```

Expected:

```text
Traffic nav disappears
Traffic page → 404
Traffic product endpoint → 404
Home unchanged
CurrentTrafficReadService still available to other consumers
Observation unchanged
```

No DB/schema/Omada rollback.

---

# 87. Exact file-scope conclusion

Against:

```text
main@70b0801db0e115af96cd88faee3f667fa4369aa0
tree df3c565ae7e955f2bcc9ad54290473c72a43e657
```

clean implementation path:

```text
MODIFY:
app/admin_web/routes.py
app/admin_web/static/admin.js
app/admin_web/templates/admin/traffic.html

ADD:
tests/admin_web/test_traffic_current.py
tests/admin_web/test_traffic_current_frontend.py
```

Expected production delta:

```text
3 modified files
0 new runtime modules
0 schema files
0 config files
0 Home templates
```

Broader production-file delta requires STOP + factual review.

---

# 88. Explicit out of scope

Not in `TRAFFIC-01`:

```text
Historical Network Traffic
24h / 7d selector
TRAFFIC-02-READ
Period Statistics
Peak Load Period
Traffic by AP history
AP Traffic Share
Online Guests
Current per-client Mbps
Completed Guest Session Traffic
Consolidated Traffic Evidence
30-day range
Heatmap
Period Comparison
Home Top Consumers
Home redesign
AP list on Traffic page
```

---

# 89. Acceptance criteria

`TRAFFIC-01` is accepted only if:

1. Exact accepted baseline is used or explicitly rebound if main changes.
2. TRAFFIC-00 remains the page/lifecycle owner.
3. Current Network Throughput panel exists.
4. Panel shows Download / Upload / Total in Mbps.
5. Product wording does not claim WAN/Internet/billing/guest-session semantics.
6. Endpoint is `GET /admin/api/v1/sites/<site_id>/traffic/current`.
7. Endpoint is same-origin, Site-scoped and authenticated.
8. Existing Site/security boundary is reused.
9. Traffic feature gate is checked after Site authorization.
10. No query parameters are accepted.
11. Endpoint reuses `AdminQueryService.current_traffic_summary()`.
12. Endpoint reuses `serialize_current_traffic_summary()`.
13. `CurrentTrafficReadService` remains sole current throughput semantic owner.
14. No second source-selection policy exists.
15. No second freshness policy exists.
16. No new collector/acquisition exists.
17. No Omada product call exists.
18. No new DB/schema exists.
19. No browser throughput calculation exists.
20. Browser does not recompute total.
21. Valid zero remains zero.
22. Missing/unavailable remains `—`, not zero.
23. Panel registers through `CaptivPortalTrafficCoordinator`.
24. Exactly one initial execution comes from registration.
25. `autoRefresh=true` uses Foundation scheduling.
26. Global Refresh uses existing `refreshAll`.
27. No private timer exists.
28. No private AbortController/lifecycle owner exists.
29. Panel-specific trigger, if added, uses `refreshPanel`.
30. Ordinary panel failure remains panel-local.
31. 401/403 retain Foundation global behavior.
32. Existing zero-panel Foundation behavior remains valid when panel absent.
33. Home UI structure is unchanged.
34. Existing Home Current Traffic URL/contract remains unchanged.
35. Under same fixed source/evaluation result, Home and Traffic semantics/results match.
36. Two independent live requests are not required to be exactly equal.
37. Coder runs only focused/minimal TRAFFIC-01 tests.
38. Official Home/cross-surface/broader regression is Central Lab-owned.
39. Official Central Lab gate uses current verified runner at execution time.
40. Production activation remains separate Owner action.

---

# 90. Coder handoff requirements after authorization

Coder handoff MUST record:

```text
implementation baseline SHA/tree
changed files
new files
exact focused test commands
passed/skipped/failed counts
compileall result
git diff --check result
any deviation from expected file scope
any factual contradiction discovered
```

Coder MUST NOT attribute Central Lab evidence to itself.

If no broader regression was run by Coder:

```text
Broader / cross-surface / full regression:
NOT RUN BY CODER — Central Lab owned
```

---

# 91. Stop conditions

Coder MUST STOP and return evidence if implementation requires:

```text
changing CurrentTrafficReadService semantics
changing Observation acquisition/rate formulas
changing source family contract
changing backend serializer semantics
changing Home template/UI
adding config/schema/DB
adding direct Omada call
adding new dependency
creating second Traffic coordinator
bypassing Foundation request helper
```

Also STOP if current `origin/main` changes materially before work starts.

---

# 92. Final architecture statement

`TRAFFIC-01` is intentionally a thin new product consumer over an already accepted semantic owner.

```text
Observation persisted AP facts
        ↓
CurrentTrafficReadService
        ↓
AdminQueryService.current_traffic_summary()
        ↓
serialize_current_traffic_summary()
        ├── existing Home surface
        └── new Traffic /traffic/current API
                         ↓
            CaptivPortalTrafficCoordinator
                         ↓
            Current Network Throughput panel
```

The project gains a new product surface, not a second Traffic implementation.

---

# 93. Final status

```text
TASK:
TRAFFIC-01 — Current Network Throughput

STATUS:
FINAL — READY FOR EXPLICIT OWNER IMPLEMENTATION AUTHORIZATION

BOUND TO:
main@70b0801db0e115af96cd88faee3f667fa4369aa0

TREE:
df3c565ae7e955f2bcc9ad54290473c72a43e657

DEPENDENCY:
TRAFFIC-00 MERGED / ACCEPTED

ARCHITECTURE:
READY

CODER AUTHORIZATION:
NOT GRANTED BY THIS FINAL

MERGE AUTHORIZATION:
NOT GRANTED BY THIS FINAL

PRODUCTION ACTIVATION:
NOT GRANTED BY THIS FINAL
```

Next action:

```text
Owner explicitly authorizes Coder implementation of TRAFFIC-01
```

Only after that authorization may implementation begin.
