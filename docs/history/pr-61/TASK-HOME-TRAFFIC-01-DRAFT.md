# TASK-HOME-TRAFFIC-01 — Admin Console Home Current Traffic — DRAFT

**Project:** CaptivPortal  
**Parent product concept:** `TASK-HOME-01 — Admin Console Home v1`  
**Depends on:** `TASK-HOME-LIVE-01` code at `main@dafbc40b6f5c5b3dde6b52fcc2c7689e95d05081`  
**Type:** master architecture / implementation specification  
**Status:** `DRAFT FOR TECH LEAD REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Branch authorization:** `NOT GRANTED`  
**Code / commit / push / PR / merge authorization:** `NOT GRANTED`  
**Production change authorization:** `NOT GRANTED`  
**Architecture baseline:** `origin/main@dafbc40b6f5c5b3dde6b52fcc2c7689e95d05081`  
**Baseline verified against GitHub:** 2026-08-24  
**Prepared:** 2026-08-24  
**Next action:** Tech Lead architecture review only.

---

# 1. Purpose

Implement the next operational Home increment:

```text
HOME-TRAFFIC-01
```

The feature adds a current traffic view to the already deployed Home Live without creating a second data-acquisition path.

Target product view:

```text
Download Now
Upload Now
Total Traffic Now

Traffic observed time
Traffic freshness
Traffic coverage

Traffic by AP
```

The traffic metric represents the most recent valid **AP physical traffic evidence persisted by Observation**.

It does **not** automatically mean:

```text
Internet/WAN-only traffic
Zefer_Parki-only traffic
human-user-only traffic
RF channel utilization
configured uplink capacity
```

The UI and API must preserve that distinction.

---

# 2. Current HOME-LIVE status and gating

At DRAFT preparation:

```text
HOME-LIVE-01:
PRODUCTION / ACTIVATED / OWNER VISUAL SMOKE PASS

Final acceptance:
PENDING SOAK AND PERFORMANCE GATE

Production/main:
dafbc40b6f5c5b3dde6b52fcc2c7689e95d05081
```

Current production Home Live settings:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=true
WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS=60
WEB_ADMIN_HOME_LIVE_REQUEST_TIMEOUT_SECONDS=20
WEB_ADMIN_CURRENT_STATE_PAGE_SIZE=100
```

`HOME-TRAFFIC-01` may be designed and reviewed while the Home Live soak is running.

However:

```text
HOME-TRAFFIC production activation
REQUIRES
HOME-LIVE-01 final production acceptance = PASS
```

A later Owner may separately authorize implementation before that final Home Live production acceptance, but production activation of Traffic must not stack on an unaccepted Home baseline.

---

# 3. Exact baseline findings

This DRAFT is based on current source code, not the historical roadmap.

Verified at:

```text
origin/main =
dafbc40b6f5c5b3dde6b52fcc2c7689e95d05081
```

The merge is:

```text
TASK-HOME-LIVE-01: add Current State data to Admin Home
```

The following current contracts matter to this task.

---

# 4. Existing Observation acquisition already provides traffic facts

No new Omada acquisition is required.

Current AP Observation dynamically reads:

```text
AP overview
wired uplink
LAN traffic
radios
```

The existing normalizer stores cumulative controller counters.

Current persisted AP rate fields include:

```text
wired_download_mbps
wired_upload_mbps
wired_download_rate_reason
wired_upload_rate_reason

lan_rx_mbps
lan_tx_mbps
lan_rx_rate_reason
lan_tx_rate_reason
```

Current persisted radio rate fields include:

```text
radio_rx_mbps
radio_tx_mbps
radio_rx_rate_reason
radio_tx_rate_reason
```

The current Observation worker already calculates rates.

`HOME-TRAFFIC-01` MUST NOT recalculate rates from raw counters in Admin/UI code.

---

# 5. Existing rate algorithm to preserve

The current AP worker uses:

```text
rate_mbps =
(current_counter - previous_counter)
× 8
÷ elapsed_seconds
÷ 1,000,000
```

Current rate outcomes are:

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

Current behavior:

```text
missing timestamp/counter
→ source_unavailable

no previous sample
→ no_baseline

elapsed <= 0
→ invalid_elapsed

elapsed > configured maximum gap
→ gap_too_large

current counter < previous counter
→ counter_reset

otherwise
→ numeric Mbps + reason=ok
```

A negative delta is never passed through `abs()`.

After a reset, the new counter becomes a future baseline by normal acquisition behavior.

HOME-TRAFFIC reads the persisted output of this algorithm.

---

# 6. Current acquisition cadence / rate bounds

Current repository defaults for AP Observation are:

```text
OBSERVATION_AP_INTERVAL_SECONDS=30
OBSERVATION_AP_CYCLE_MAX_DURATION_SECONDS=120
OBSERVATION_RATE_MAX_GAP_SECONDS=180
```

The Observation config enforces:

```text
AP cycle max duration
+
AP interval
<=
rate max gap
```

Production values must be checked during activation rather than assumed from repository defaults.

Traffic frontend polling does not change these values.

---

# 7. Verified direction semantics

Current normalized wired source:

```text
downBytes
→ wired_down_bytes
→ wired_download_mbps

upBytes
→ wired_up_bytes
→ wired_upload_mbps
```

Current LAN source:

```text
LAN rx
→ lan_rx_mbps

LAN tx
→ lan_tx_mbps
```

Current radio source:

```text
radio rx
→ radio_rx_mbps

radio tx
→ radio_tx_mbps
```

Product direction semantics:

```text
wired download
LAN RX
radio TX
→ network/AP toward Wi-Fi clients
→ Download

wired upload
LAN TX
radio RX
→ Wi-Fi clients toward AP/network
→ Upload
```

These are AP/network-flow directions.

---

# 8. Values that are NOT current throughput

Forbidden as Current Traffic rate source:

```text
wired uplink "rate"
maxTxRate
txUtil
rxUtil
busyUtil
interferenceUtil
activity
CPU
memory
Current State controller_traffic_* counters
```

`wired uplink rate` is link capability/state, not observed throughput.

Utilization fields are RF/controller facts, not Mbps.

Current State client traffic fields remain neutral controller counters in this task.

---

# 9. Permanent Data Acquisition / Analytics Boundary

Permanent architecture:

```text
Omada
  ↓
existing Observation AP worker
  ↓
observations.sqlite3
  ↓
Analytics read boundary
  ↓
CurrentTrafficReadService
  ↓
AdminQueryService
  ↓
Admin API
  ↓
Home Traffic UI
```

Forbidden:

```text
Browser → Omada

Admin route → Omada

AdminQueryService → Omada

CurrentTrafficReadService → Omada

Home opening → new Observation cycle

Home opening → second collector

Home opening → higher Omada polling

Home → Loki/Grafana

Home → raw log parsing
```

Traffic is query-on-read over already persisted Observation facts.

---

# 10. Product / Observability Boundary

Product-safe:

```text
Download Mbps
Upload Mbps
Total Mbps
traffic source family
traffic observed time
freshness
coverage
per-AP traffic
bounded quality/reason summaries
```

Engineering-only:

```text
raw SQL
SQLite path
stack trace
raw source exception
raw Omada response
credentials/token
unbounded reason text
raw controller configuration
WLAN override payload
```

Grafana/Loki remain engineering observability and are not the Home product backend.

---

# 11. Future Multi-Site Compatibility

Current model remains:

```text
Site-aware
single-tenant
```

Mandatory:

```text
site_id on every traffic query
no cross-Site aggregate
no cross-Site cursor
no hardcoded production Site
no tenant_id
Tenant != Site
```

Traffic scope is the selected Site AP Observation population.

Do not infer a Site by MAC.

---

# 12. Important product scope limitation

The AP traffic sources describe AP physical/network traffic.

Therefore `HOME-TRAFFIC-01` must not label the total:

```text
Internet Load
WAN Load
Guest Internet Traffic
Zefer_Parki Traffic
```

unless a later architecture proves that semantic.

Allowed product wording:

```text
Traffic Now
Site AP Traffic
Download Now
Upload Now
Total Traffic Now
```

Helper copy must state that traffic is derived from AP counters and may include non-Internet/local/service traffic.

`Channel Load` remains explicitly out of scope.

---

# 13. Current read-contract gap

Current code does not yet expose one product-safe current Site traffic snapshot.

Existing interfaces provide:

```text
ObservationReadService:
  get latest AP observation for one AP
  get AP observations for one AP/range
  get latest radio observations for one AP

WirelessAnalyticsService:
  historical throughput distributions over a time window

AdminReadGateway:
  per-AP Observation rows for explicit AP/range
```

They do NOT currently provide:

```text
latest complete-success AP dynamic cycle
+
all AP rows from exactly that cycle
+
one deterministic Site-wide source family
+
current aggregate
+
coverage/freshness contract
```

Using existing per-AP latest reads independently would allow:

```text
AP A from cycle X
+
AP B from cycle Y
```

and is therefore rejected.

Using Wireless Analytics throughput distribution would produce a historical distribution, not current Site traffic.

---

# 14. Required explicit prerequisite

Because the current read contract is insufficient, this master DRAFT defines an explicit prerequisite:

```text
TASK-HOME-TRAFFIC-READ-01
Current Traffic Read Foundation
```

Status inside this master:

```text
PREREQUISITE DRAFT
IMPLEMENTATION NOT AUTHORIZED
```

It must be implemented/reviewed/accepted before the Admin/API/UI increment.

This prerequisite:

```text
adds read/query contracts only
does not collect
does not mutate
does not migrate source DB
does not change rate calculation
does not change Observation cadence
does not call Omada
```

Execution decomposition after Owner authorization:

```text
PR A:
TASK-HOME-TRAFFIC-READ-01
  persisted Observation → CurrentTrafficReadService

then merge + acceptance

PR B:
TASK-HOME-TRAFFIC-01
  CurrentTrafficReadService → Admin API → Home UI
```

Tech Lead may approve this decomposition or request a separate physical TASK file, but Coder must not collapse the prerequisite into UI work without review.

---

# 15. Preferred prerequisite package placement

Preferred implementation:

```text
app/analytics/current_traffic.py
```

with immutable result DTOs in:

```text
app/analytics/models.py
```

and bounded Observation access through:

```text
AnalyticsSourceGateway
→ ObservationReadService.analytics_read_connection()
```

Preferred runtime exposure:

```text
AnalyticsRuntime.current_traffic_service
```

Rationale:

```text
Analytics reads persisted facts.
Analytics does not collect.
```

No new business DB is created.

No source repository ownership is duplicated.

No loopback HTTP to Analytics 02A is used.

---

# 16. Prerequisite source query — canonical cycle

Current Traffic v1 MUST select one exact AP dynamic snapshot:

```text
observation_cycles.site_id = requested Site
kind = 'ap_dynamic'
state = 'completed'
complete = 1
result = 'success'
```

Select newest by deterministic completed-cycle ordering.

All traffic rows used by one response come from:

```text
one exact cycle_id
```

Forbidden:

```text
latest row independently per AP
cross-cycle fill
previous-cycle fill for one missing AP
future-cycle fill
```

---

# 17. Cycle integrity validation

For the selected complete-success cycle, the read service validates at minimum:

```text
AP row Site = requested Site
AP row cycle_id = selected cycle
AP MAC unique in selected cycle

cycle.items_seen == cycle.items_stored
stored AP row count == cycle.items_stored
```

For a non-empty cycle used for traffic:

```text
AP partial=false
wired_uplink_ok=true
lan_traffic_ok=true
```

must hold for every selected AP row.

A persisted contradiction to a complete-success cycle is a source-integrity failure.

Result:

```text
source_unavailable
```

not a fabricated partial total.

A valid complete-success cycle with zero APs is allowed as an empty exact population.

---

# 18. Canonical traffic source decision — FINAL IN DRAFT

The v1 source hierarchy is:

```text
Primary:
wired

Fallback:
LAN
```

Mappings:

```text
wired:
  Download = wired_download_mbps
  Upload   = wired_upload_mbps

LAN:
  Download = lan_rx_mbps
  Upload   = lan_tx_mbps
```

Radio is not a Site-total source in v1.

---

# 19. No double counting

Never:

```text
wired + LAN
wired + radio
LAN + radio
wired + LAN + radio
```

These are alternate/related representations of traffic, not independent traffic classes.

Site total uses exactly one source family.

---

# 20. No per-AP source mixing

Forbidden:

```text
AP-1 wired
+
AP-2 LAN fallback
```

inside one Site total.

One response selects:

```text
wired for every AP
```

OR:

```text
LAN for every AP
```

This prevents a semantically mixed total.

---

# 21. Deterministic source-selection algorithm

For the selected cycle calculate:

```text
wired_pair_valid_ap_count

LAN_pair_valid_ap_count
```

Pair valid means:

```text
Download reason = ok
AND
Upload reason = ok
AND
both numeric finite non-negative
```

Select:

```text
if wired_pair_valid == total_ap_count:
    selected_source = wired
    selection_reason = primary_full_coverage

elif lan_pair_valid == total_ap_count:
    selected_source = lan
    selection_reason = fallback_full_coverage

elif lan_pair_valid > wired_pair_valid:
    selected_source = lan
    selection_reason = fallback_higher_coverage

else:
    selected_source = wired
    selection_reason = primary_preferred_tie_or_higher
```

This also defines the zero-valid tie:

```text
wired=0
LAN=0
→ selected_source=wired
```

so source reasons/freshness remain inspectable.

Coder must not invent a per-AP blended fallback.

---

# 22. Source disagreement

If both wired and LAN are valid for the same AP they may differ.

v1 rule:

```text
difference does not change source selection
difference is not automatically a defect
difference is not averaged
difference is not added
```

The prerequisite MAY internally compute bounded comparison diagnostics for tests/telemetry, but Home v1 does not need to expose raw discrepancy values.

Selected source remains governed by section 21.

---

# 23. Exact zero semantics

A persisted rate is a valid exact zero when:

```text
reason = ok
value = 0.0
```

That is traffic zero.

Do not convert it to:

```text
null
—
unavailable
no traffic evidence
```

A complete cycle with:

```text
total_ap_count=0
```

returns:

```text
Download=0.0
Upload=0.0
Total=0.0
coverage_status=complete
empty_population=true
```

This is distinct from a non-empty AP population with no valid delta.

---

# 24. Invalid/missing rate semantics

For selected source, only:

```text
reason=ok
AND finite non-negative numeric value
```

contributes to aggregation.

Reasons:

```text
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

do not contribute a numeric rate.

No invalid rate becomes zero.

No negative rate is exposed.

---

# 25. Direction-specific aggregation

For selected source:

```text
Site Download Now
=
SUM(valid Download rate across APs)

Site Upload Now
=
SUM(valid Upload rate across APs)
```

`Total Traffic Now`:

```text
Download subtotal + Upload subtotal
```

only over the same selected source family.

Return direction coverage separately.

If coverage is partial, the numeric value is explicitly an observed subtotal.

---

# 26. Coverage counters

Minimum result coverage:

```text
total_ap_count

valid_rate_ap_count
valid_download_ap_count
valid_upload_ap_count

missing_rate_ap_count

stale_ap_count

reset_ap_count
gap_rejected_ap_count
no_baseline_ap_count
source_unavailable_ap_count
invalid_elapsed_ap_count
```

Definitions:

```text
valid_rate_ap_count:
  both selected-source directions valid

missing_rate_ap_count:
  total_ap_count - valid_rate_ap_count
```

Reason AP counts are non-exclusive:

```text
one AP can contribute to reset_ap_count
and gap_rejected_ap_count
if its two directions differ
```

Count an AP at most once per reason category.

---

# 27. Alternative-source metadata

For transparency return bounded source-selection metadata:

```text
primary_source = wired
selected_source = wired|lan
selection_reason

wired_pair_valid_ap_count
lan_pair_valid_ap_count

source_mixing_allowed = false
```

Do not return raw counter values.

---

# 28. Coverage status

Allowed:

```text
complete
partial
none
```

## complete

```text
total_ap_count = 0
```

OR:

```text
valid_rate_ap_count = total_ap_count
AND
source_skew_seconds <= configured maximum skew
```

## partial

At least one selected-source numeric direction is valid, but:

```text
not every AP has both directions valid
OR
source skew exceeds maximum
```

## none

Non-empty AP population with no valid selected-source numeric Download or Upload rate.

---

# 29. Partial display semantics

If:

```text
coverage_status=partial
```

numeric subtotals MAY be displayed.

They must be visibly marked:

```text
Partial
X / Y APs
```

Helper wording:

```text
Observed subtotal from the APs with valid current rates.
```

Never visually present a partial subtotal as an exact Site total.

---

# 30. No-valid-rate semantics

If:

```text
coverage_status=none
```

then:

```text
download_mbps=null
upload_mbps=null
total_mbps=null
```

even if some raw controller counters exist.

UI shows:

```text
—
No valid current rate
```

and quality/reason summary.

---

# 31. Traffic temporal identity

Traffic has an independent source watermark.

It must not reuse:

```text
Client Current State observed_at
AP Current State observed_at
browser refresh time
```

Traffic is sourced from Observation AP dynamic facts.

---

# 32. Section timestamp used by source family

For wired:

```text
source timestamp per AP =
wired_observed_at
```

For LAN:

```text
source timestamp per AP =
lan_observed_at
```

`ap_observations.observed_at` is not substituted when the section-specific timestamp exists.

---

# 33. Aggregate traffic watermark

For selected source and selected cycle:

```text
oldest_source_observed_at
=
MIN(selected section timestamp across AP population)

newest_source_observed_at
=
MAX(selected section timestamp across AP population)
```

Product:

```text
observed_at = oldest_source_observed_at
```

This is intentionally conservative.

Also return:

```text
newest_observed_at
source_skew_seconds =
newest - oldest
```

For zero AP population:

```text
observed_at = cycle.finished_at
newest_observed_at = cycle.finished_at
source_skew_seconds = 0
```

---

# 34. Source-skew policy

Repository/product default:

```text
WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS=60
```

Bounds proposed for review:

```text
10..180
```

If:

```text
source_skew_seconds > max_ap_skew_seconds
```

then:

```text
coverage_status cannot be complete
```

If there are usable values it becomes:

```text
partial
coverage_reason includes temporal_skew
```

No cross-cycle replacement is allowed to repair skew.

---

# 35. Freshness policy

Repository/product defaults:

```text
WEB_ADMIN_HOME_TRAFFIC_FRESH_MAX_AGE_SECONDS=90

WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS=180
```

Bounds proposed:

```text
fresh: 30..300
stale: fresh..600
```

Freshness uses:

```text
evaluated_at - observed_at
```

Clock regression / invalid future timestamp:

```text
freshness=unavailable
```

not negative age.

---

# 36. Fresh/stale/unavailable

```text
fresh:
  age <= 90s

stale:
  90s < age <= 180s

unavailable:
  age > 180s
  OR timestamp invalid/future beyond accepted clock tolerance
  OR no valid selected-cycle timestamp
```

These defaults are independent product policy.

They do not change Observation `rate_max_gap_seconds`.

---

# 37. Stale numeric values

If traffic snapshot is:

```text
stale
```

but still within stale maximum:

```text
last selected-cycle values remain visible
```

with a prominent:

```text
STALE
```

label and age.

Coverage remains independently visible.

---

# 38. Unavailable numeric values

If freshness becomes:

```text
unavailable
```

API returns source metadata/quality, but product traffic numbers are:

```text
null
```

UI shows:

```text
—
Unavailable
```

Old values must not remain current-looking.

---

# 39. Freshness vs coverage are independent

Examples:

```text
fresh + complete
fresh + partial
fresh + none

stale + complete
stale + partial
stale + none

unavailable
```

Do not collapse all quality dimensions into one generic status.

---

# 40. Collector downtime

No new cycle is triggered.

Last complete-success traffic snapshot ages naturally:

```text
fresh → stale → unavailable
```

No reconstruction from:

```text
Current State
client counters
Visit
Registry
Grafana
```

---

# 41. Partial/failed latest Observation cycle

The canonical selection uses the latest:

```text
complete=1
result=success
```

A newer:

```text
partial
failed
shutdown
```

cycle does not replace it.

The read result should expose only a generic bounded latest-attempt warning if cheaply available:

```text
Latest AP collection did not complete successfully;
showing the latest complete traffic snapshot.
```

Do not expose raw failure category to product UI.

---

# 42. AP add/remove behavior

AP population comes from the selected complete-success `ap_dynamic` cycle.

New AP:

```text
appears in next complete-success cycle
```

Its first stored rate may be:

```text
no_baseline
```

and coverage becomes partial/none until a valid delta exists.

Removed AP:

```text
disappears from the next complete-success cycle
```

No historical AP is carried forward into a new current total.

---

# 43. Current State AP inventory is not canonical traffic population

Do NOT build Site traffic as:

```text
CurrentState AP list
×
independent latest Observation per AP
```

That mixes source timelines.

`CurrentStateReadService` is not required to compute the Traffic total.

The Home may visually place AP Traffic beside AP Current State, but their watermarks are independent.

---

# 44. Radio-band decision — OUT OF v1

`HOME-TRAFFIC-01` v1 does NOT expose per-band traffic.

Reserve:

```text
HOME-TRAFFIC-RADIO-01
```

Future semantics, if implemented:

```text
band Download = radio_tx_mbps
band Upload   = radio_rx_mbps
```

Radio totals remain an alternate view.

They are never added to wired/LAN Site total.

Current normalizer support must be re-reviewed before future 6 GHz UI; present normalizer explicitly handles current 2g/5g source keys.

---

# 45. Channel Load decision

`Channel Load` is NOT part of `HOME-TRAFFIC-01`.

Do not derive it from:

```text
Total Traffic Mbps
wired link rate
busyUtil
txUtil/rxUtil
```

without a separate product contract.

Reserved follow-up remains separate.

---

# 46. CurrentTrafficReadService conceptual contract

Prerequisite exposes:

```python
get_current_site_traffic(
    site_id,
    *,
    evaluated_at_utc=None,
    deadline=None,
) -> CurrentSiteTraffic

list_current_ap_traffic(
    site_id,
    *,
    cycle_id=None,
    limit=100,
    cursor=None,
    evaluated_at_utc=None,
    deadline=None,
) -> CurrentApTrafficPage
```

The service is:

```text
read-only
Site-scoped
bounded
immutable
deadline-aware
Omada-free
```

---

# 47. Current traffic immutable models

Conceptual models:

```text
CurrentTrafficSnapshotMeta
CurrentTrafficSourceSelection
CurrentTrafficCoverage
CurrentSiteTraffic
CurrentApTrafficItem
CurrentApTrafficPage
```

No `sqlite3.Row` escapes.

No mutable raw source dictionaries escape.

---

# 48. Summary source transaction

Summary selection and aggregate computation must occur through one read-only Observation connection/transaction.

The query must:

```text
select canonical cycle
compute source-family coverage
select source deterministically
aggregate selected family
compute timestamps/skew
compute reason counts
```

without N+1 AP reads.

Preferred:

```text
set-based SQL
```

No:

```text
for AP in inventory:
    get_latest_ap_observation(AP)
```

---

# 49. AP page source transaction

AP page is pinned to one exact:

```text
Site
cycle_id
selected_source
```

Keyset ordering v1:

```text
ap_mac ASC
```

No user-selectable traffic sort in v1.

Reason:

```text
stable simple pagination
no nullable-rate sort ambiguity
```

Traffic sort can be a later UX increment if needed.

---

# 50. AP page cursor contract

Cursor binds:

```text
endpoint kind
Site
cycle_id
selected source family
last AP MAC
version
```

Cursor is opaque to browser.

Cross-Site use:

```text
400 invalid_request
```

Changed cycle/source:

```text
400 invalid_request
```

Malformed/overlong cursor:

```text
400 invalid_request
```

No fallback to newest page for an explicit stale cursor.

---

# 51. Explicit cycle semantics

No explicit `cycle_id`:

```text
select current canonical cycle
```

No canonical complete-success cycle:

```text
HTTP 200
freshness=unavailable
coverage=none
values=null
items=[]
```

Explicit `cycle_id` supplied but no longer valid/selectable:

```text
400 invalid_request
```

The UI then performs exactly one clean Traffic refresh.

No infinite 400 retry.

---

# 52. Prerequisite error mapping

Caller validation:

```text
invalid Site syntax
invalid limit
invalid cycle syntax
malformed cursor
cross-Site cursor
changed cursor context
→ validation error
```

Source storage/integrity:

```text
SQLite read/open failure
schema mismatch
cycle invariant mismatch
non-finite persisted rate
negative persisted rate with reason=ok
unexpected reason code
→ source unavailable
```

Programming error:

```text
sanitized internal error at Admin boundary
```

Raw SQLite/SQL/path text is not returned.

---

# 53. Prerequisite deadline

Unlike Current State, this read path can use the existing Analytics deadline-aware SQLite boundary.

Use existing:

```text
QueryDeadline
SQLite progress handler / deadline checks
read-only URI mode
PRAGMA query_only=ON
```

Do not create a new deadline abstraction.

---

# 54. No source schema changes

Prerequisite must not change:

```text
observations.sqlite3 schema
Observation user_version
Observation indexes
Observation worker
Observation retention
Observation cadence
rate reasons
rate formula
Omada provider
```

Current indexes around:

```text
cycle_id + AP
Site + AP + time
Site + time
```

must be benchmarked before any index request.

If query plan is not acceptable:

```text
STOP
return EXPLAIN QUERY PLAN + timings
prepare explicit storage/index amendment
```

No silent source index addition.

---

# 55. Prerequisite performance gate

Before PR A acceptance, benchmark on representative production-scale copy/read-only data.

Minimum queries:

```text
current Site summary
AP page 100
AP page 250
```

Record:

```text
EXPLAIN QUERY PLAN
row population
p50
p95
max
deadline result
```

No production activation in PR A.

---

# 56. Main HOME-TRAFFIC feature flag

Add:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
```

Repository-safe default:

```text
false
```

Invariant:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=true
requires
WEB_ADMIN_ENABLED=true
AND
WEB_ADMIN_HOME_LIVE_ENABLED=true
```

Traffic is an increment of Live Home.

It is not enabled on legacy Home.

---

# 57. Home Traffic configuration

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

Validation:

```text
refresh:
60..300

request timeout:
5..60

page size:
1..250

fresh max age:
30..300

stale max age:
fresh..600

max AP skew:
10..180
```

Cross-field:

```text
Traffic request timeout
>
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

---

# 58. Settings path

Exact configuration path:

```text
app/config.py
→ app/settings.py:get_settings()
→ AdminWebConfig
→ render_admin_page()
→ admin Home template data-* attributes
→ Home Traffic controller
```

Safe values exposed to browser:

```text
home_traffic_enabled
home_traffic_refresh_seconds
home_traffic_request_timeout_seconds
home_traffic_page_size
```

Freshness/skew policy is returned by API and need not be duplicated as browser configuration.

No secret in HTML.

JS does not probe an endpoint to discover whether the feature is enabled.

---

# 59. Feature disabled behavior

When:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
```

then:

```text
existing Home Live remains unchanged

Traffic DOM is not rendered
Traffic timers/listeners are not started
Traffic fetches are not sent

Observation collection is unchanged
Omada polling is unchanged

Devices unchanged
Device Card unchanged
Visits unchanged
Observations unchanged
```

---

# 60. Admin runtime dependency

Add Current Traffic as an optional Admin read dependency.

Preferred:

```text
analytics_runtime.current_traffic_service
→ AdminQueryService
```

It must NOT participate in existing mandatory Admin runtime readiness.

Therefore:

```text
Traffic source absent/unavailable
does not make legacy Admin unavailable
does not make Home Live unavailable
```

When feature enabled but current traffic service absent:

```text
Traffic endpoints → 503 source_unavailable
```

Current State Home remains operational.

---

# 61. AdminQueryService methods

Conceptual:

```python
current_traffic_summary(
    principal,
    site_id,
)

list_current_ap_traffic(
    principal,
    site_id,
    *,
    cycle_id=None,
    limit=None,
    cursor=None,
)
```

No direct SQL in routes.

No Omada.

No Loki/Grafana.

---

# 62. Capability mapping

FINAL choice in this DRAFT:

```text
Traffic summary:
admin.read.overview

Traffic by AP:
admin.read.observations
```

Reason:

```text
summary is high-level operational overview

AP page exposes managed AP identity
plus Observation-derived rate/quality detail
```

Coder does not select a weaker capability.

---

# 63. Admin API routes

Register exactly:

```text
GET /admin/api/v1/sites/{site_id}/current-traffic/summary

GET /admin/api/v1/sites/{site_id}/current-traffic/aps
```

Use existing:

```text
api_version=admin.read.v1
```

No new public API version.

---

# 64. Feature-disabled route security order

Both routes are registered even when Traffic is disabled.

Required order:

```text
HTTPS/network/query-size boundary
→ Admin session
→ Site syntax/allowlist
→ capability
→ Traffic feature flag
→ canonical 404 not_found
```

Only when enabled:

```text
→ endpoint-specific query validation
→ CurrentTrafficReadService
```

This mirrors the accepted Home Live rollout/rollback model.

---

# 65. Pre-auth duplicate-query handling

Current Admin `before_app_request` has a special path exception for Current State so endpoint-specific query schema is not exposed before its intended gate.

HOME-TRAFFIC must receive equivalent reviewed handling.

Do not allow:

```text
malformed/duplicate Traffic query
→ distinguish feature route/schema before session/Site/capability/feature gate
```

Add a narrow Traffic-path predicate rather than weakening the global Admin boundary.

---

# 66. Traffic summary endpoint

```text
GET /admin/api/v1/sites/{site_id}/current-traffic/summary
```

Query parameters:

```text
none
```

Capability:

```text
admin.read.overview
```

---

# 67. Traffic summary API DTO

Conceptual:

```json
{
  "snapshot": {
    "source_kind": "observation_ap_dynamic",
    "cycle_id": "<opaque-id-or-null>",
    "evaluated_at": "2026-08-24T10:00:00.000Z",
    "observed_at": "2026-08-24T09:59:42.000Z",
    "newest_observed_at": "2026-08-24T09:59:55.000Z",
    "age_seconds": 18.0,
    "source_skew_seconds": 13.0,
    "freshness_status": "fresh",
    "freshness_reason": "within_freshness_window",
    "complete": true
  },
  "freshness_policy": {
    "fresh_max_age_seconds": 90,
    "unavailable_after_seconds": 180,
    "max_ap_skew_seconds": 60
  },
  "traffic": {
    "download_mbps": 42.125,
    "upload_mbps": 6.250,
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

No raw SQL.

---

# 68. Summary unavailable-source-quality response

If source storage is readable but no canonical complete-success cycle exists:

```text
HTTP 200
```

with:

```text
freshness_status=unavailable
coverage_status=none
download_mbps=null
upload_mbps=null
total_mbps=null
cycle_id=null
```

This is source-quality unavailability, not an HTTP source read failure.

SQLite/schema/integrity failure remains:

```text
503 source_unavailable
```

---

# 69. AP traffic endpoint

```text
GET /admin/api/v1/sites/{site_id}/current-traffic/aps
```

Allowed query parameters:

```text
cycle_id
limit
cursor
```

No sort/filter v1.

Capability:

```text
admin.read.observations
```

Default limit:

```text
100
```

Hard max:

```text
250
```

---

# 70. AP Traffic item DTO

Expose only:

```text
ap_mac
name

download_mbps
upload_mbps
total_mbps

download_reason
upload_reason

rate_status

observed_at
age_seconds

selected_source
```

Do not expose:

```text
IP
firmware
raw counters
raw link rate
CPU/RAM
raw controller payload
SSID/WLAN override
```

---

# 71. AP item rate status

Allowed:

```text
valid
partial
unavailable
```

## valid

Both selected-source directions:

```text
reason=ok
finite non-negative
```

## partial

Exactly one direction valid.

## unavailable

Neither direction valid.

A numeric zero with `reason=ok` remains valid.

---

# 72. AP page pinning

Home load:

```text
Traffic Summary
→ selected cycle_id
→ AP Traffic page(cycle_id=same)
```

Summary and AP rows never mix cycles.

Load More remains pinned to that cycle.

---

# 73. AP page pagination

Independent Traffic AP cursor.

Do not reuse:

```text
Home Live Client cursor
Home Live AP cursor
```

Traffic AP pagination state:

```text
traffic_cycle_id
traffic_source
traffic_cursor
traffic_generation
```

---

# 74. API error envelope

Use existing Admin envelope.

No raw source error.

Status mapping:

```text
200:
valid/stale/unavailable source-quality response

400:
caller invalid request
malformed/expired explicit traffic cursor/cycle

401:
Admin session required

403:
Site/capability forbidden

404:
Traffic feature disabled after security/Site/capability gate

429:
Admin concurrency busy

503:
Traffic read service absent
source DB/schema/integrity unavailable
query deadline
response too large

500:
sanitized unexpected programming error
```

---

# 75. Deadline / concurrency

Both endpoints use existing:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES
QueryDeadline
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
response-size cap
```

No new server queue.

No new long-running worker.

---

# 76. Route telemetry

Add:

```text
admin.current_traffic_query_completed
```

Allowed fields:

```text
request_id
route_name
site_id AFTER successful authorization
status_code
outcome
reason
duration_ms
coverage_status
freshness_status
item_count
```

All enum/text fields are allowlisted.

Forbidden:

```text
client MAC
client IP
SSID
AP MAC
AP filter values
cursor
cycle_id
source hash
raw query string
raw URL
raw source exception
SQLite path
credentials
Omada payload
WLAN override data
```

Telemetry failure cannot alter route result.

---

# 77. Traffic UI placement

Traffic is added as an independent Home Live section.

Recommended layout:

```text
Home Live top current-state cards
↓
Traffic Now
  Download Now
  Upload Now
  Total Traffic Now
  Freshness
  Coverage
↓
Traffic by AP
↓
existing Devices by AP / Online Devices / Access Points
```

Exact CSS placement may be refined during implementation without changing semantics.

---

# 78. Traffic UI wording

Cards:

```text
Download Now
Upload Now
Total Traffic Now
```

Unit:

```text
Mbps
```

Helper text:

```text
Derived from persisted AP traffic counters.
May include local/service traffic and is not an Internet-only measurement.
```

Do not label:

```text
Internet Load
WAN
Channel Load
Guest-only
```

---

# 79. Coverage UI

## complete

Show:

```text
Coverage: Complete · X/X APs
```

## partial

Show:

```text
Coverage: Partial · X/Y APs
```

and:

```text
Observed subtotal
```

near numeric totals.

## none

Show:

```text
Coverage: No valid current rate
```

Numbers:

```text
—
```

---

# 80. Freshness UI

Traffic has its own:

```text
Observed
Age
Fresh / Stale / Unavailable
```

Do not merge Traffic timestamp with:

```text
Clients
AP Current State
```


---

# 81. Traffic controller architecture

Traffic must not use the destructive generic legacy Home `showFailure()` path.

Preferred current-code integration:

```text
existing Home Live controller
+
isolated Traffic sub-controller/state
```

Traffic owns independent:

```text
traffic_generation
AbortController
in_flight
failure_count
next_eligible_at
cycle/cursor
last accepted snapshot
timer
```

Current State Client/AP generation and Traffic generation remain logically independent.

---

# 82. Failure isolation

Traffic request failure:

```text
does not clear Online
does not clear Authorized/Pending
does not clear Devices by AP
does not clear Online Devices
does not clear Access Points Now
```

Current State failure:

```text
does not clear a still-valid Traffic section
```

Global:

```text
401
403
feature rollback
```

may stop the whole appropriate Home flow.

---

# 83. Traffic normal refresh cadence

Repository default:

```text
60 seconds
```

This is not faster than the current 30-second AP Observation repository cadence.

Frontend Traffic polling never causes Omada traffic.

No missed timer queue.

If a refresh is still running:

```text
skip/replace according to generation rule
```

not overlap.

---

# 84. Manual Refresh

Existing Home Live Refresh action must also trigger one Traffic refresh when Traffic is enabled.

Rules:

```text
new Traffic generation
abort superseded Traffic request
start exactly one fresh summary request
then pinned AP first page if summary accepted
```

Manual Traffic refresh does not reset/clear healthy Current State sections.

---

# 85. Traffic request timeout

Use:

```text
AbortController
```

with:

```text
WEB_ADMIN_HOME_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
```

Always clear timeout/controller/in-flight state in `finally`.

Late response from aborted or older generation is ignored.

---

# 86. Hidden-tab behavior

When:

```text
document.hidden=true
```

Traffic automatic polling stops.

Outstanding Traffic refresh is aborted as:

```text
neutral cancellation
```

Neutral hidden cancellation:

```text
does not increment failure_count
does not show source error
```

On visible:

```text
if refresh due
→ one controlled Traffic refresh
```

---

# 87. Traffic retry/backoff

Traffic owns one source-group retry state:

```text
traffic_failure_count
traffic_next_eligible_at
```

Automatic retry:

```text
1st retryable failure → 60s
2nd → 120s
3rd+ → 300s max
```

Actual delay:

```text
max(configured refresh, backoff)
```

Success resets Traffic counter only.

Current State Client/AP retry counters are untouched.

---

# 88. Retryable errors

Traffic retryable:

```text
network error
request timeout
429
503
sanitized 500
```

429 respects:

```text
Retry-After
```

but never retries faster than configured cadence.

---

# 89. Non-retry/global states

```text
401:
stop Home polling
show sign-in state

403 Site forbidden:
stop current Site Home polling

404 Traffic feature disabled during rollout/rollback:
stop Traffic polling only
hide/disable Traffic section
do not break Home Live
recommend/rely on page reload
```

A Traffic 404 must not revert Home Live to legacy Home.

---

# 90. Traffic UI-generated 400

A 400 caused by stale pinned Traffic state:

```text
clear Traffic cursor/cycle
perform exactly one clean Traffic refresh
```

If the clean refresh also produces 400:

```text
stop clean retry loop
show sanitized unexpected Traffic state
```

No infinite retry.

---

# 91. Generation guard

Every Traffic async operation captures:

```text
generation
site_id
cycle_id if page
cursor if page
```

Before accepting response:

```text
generation still current
Site still current
cycle still current
cursor context still current
```

Else discard.

Old AP traffic rows never append after a new Traffic summary.

---

# 92. New summary + failed AP page

Forbidden:

```text
new Traffic cards
+
old AP Traffic rows
```

When a newer Traffic summary is accepted:

```text
old AP Traffic rows are cleared/hidden
```

If pinned page then fails:

```text
new summary remains
AP Traffic table shows independent error
```

---

# 93. Browser-side freshness progression

API returns:

```text
age_seconds
freshness_policy
```

Browser uses monotonic elapsed time:

```text
performance.now()
```

Displayed age advances between requests.

Local transitions:

```text
fresh → stale → unavailable
```

At unavailable threshold:

```text
numeric cards hidden
```

A network outage cannot leave Traffic permanently marked Fresh.

---

# 94. Strict frontend response validation

Before rendering Traffic 200:

```text
api_version == admin.read.v1
root Site == current Site

snapshot source_kind == observation_ap_dynamic

freshness_status in:
fresh|stale|unavailable

coverage_status in:
complete|partial|none

selected_source in:
wired|lan

selection_reason allowlisted

unit == Mbps

numeric traffic:
null OR finite non-negative number
boolean rejected

counts:
non-negative integers
boolean rejected

source_mixing_allowed == false

page items:
Array

next_cursor:
null OR bounded non-empty string
```

---

# 95. Strict traffic arithmetic validation

When all three numeric values are present:

```text
abs(
  total_mbps
  - (download_mbps + upload_mbps)
)
<= deterministic serialization tolerance
```

Recommended tolerance:

```text
1e-6
```

Counts must satisfy:

```text
0 <= valid_rate_ap_count <= total_ap_count

missing_rate_ap_count
=
total_ap_count - valid_rate_ap_count

valid_download_ap_count <= total_ap_count
valid_upload_ap_count <= total_ap_count
```

Malformed 200:

```text
do not partially render
Traffic section → unexpected response
```

---

# 96. UI exact zero validation

Frontend must preserve:

```text
0
0.0
```

as:

```text
0.00 Mbps
```

or equivalent deterministic formatting.

Do not use truthiness:

```javascript
value || "—"
```

for traffic numbers.

---

# 97. AP Traffic table

Columns:

```text
AP
Download
Upload
Total
Rate state
Observed
```

Secondary reason details may be shown in compact text/expandable detail:

```text
Download reason
Upload reason
Source
```

No raw counter values.

---

# 98. AP identity display

AP label priority:

```text
name
else MAC
```

MAC may remain visible because this is owner/operator managed infrastructure.

AP MAC must not enter route telemetry.

---

# 99. AP Traffic pagination UI

Separate:

```text
Traffic Load More
```

or a clearly Traffic-scoped control.

Do not reuse:

```text
Online Devices Load More
Access Points Now Load More
```

New Traffic refresh discards loaded extra Traffic AP pages.

---

# 100. No browser persistence

Do not store Traffic:

```text
cycle_id
cursor
AP rows
traffic values
source selection
```

in:

```text
localStorage
sessionStorage
IndexedDB
Cache API
service worker cache
```

Only in-memory page state.

All Admin API responses remain:

```text
Cache-Control: no-store
```

---

# 101. Frontend technology

Keep:

```text
Flask
Jinja
plain CSS
vanilla JS
```

No new frontend framework/library.

No external CDN.

Use `textContent` for dynamic source text.

---

# 102. API data minimization

Do not expose future-use fields.

Summary DTO only needs the sections defined above.

AP item only needs section 70.

No generic:

```text
asdict(source_row)
dict(sqlite_row)
```

public serializer.

Use explicit allowlist serializers.

---

# 103. Security

Existing Admin:

```text
authentication
HTTPS
source network allowlist
session
Site resolver
capability policy
response-size limit
query concurrency
security headers
```

remain authoritative.

No separate Traffic authentication.

No browser Analytics 02A bearer.

No loopback HTTP to Analytics API.

---

# 104. WLAN override prohibition

HOME-TRAFFIC does not need:

```text
AP WLAN overrides
SSID passwords
AP config endpoints
```

Do not call/read them for Traffic.

No password-bearing Omada configuration can enter Traffic DTO/log/telemetry.

---

# 105. Targeted prerequisite tests — canonical cycle

PR A tests at minimum:

```text
newest complete-success ap_dynamic selected

newer partial ignored
newer failed ignored
newer shutdown ignored

cross-Site cycle ignored/rejected

zero-AP complete-success cycle

persisted cycle count mismatch → source unavailable

duplicate/identity contradiction → source unavailable
```

---

# 106. Targeted prerequisite tests — source selection

Fixtures:

```text
wired full, LAN full
→ wired

wired full, LAN partial
→ wired

wired partial, LAN full
→ LAN

wired 1, LAN 2
→ LAN

wired 1, LAN 1
→ wired

wired 0, LAN 0
→ wired + coverage none
```

Prove no per-AP mixing.

---

# 107. Targeted prerequisite tests — rate reasons

For selected source:

```text
ok numeric
ok exact zero

no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

Prove:

```text
invalid rate does not contribute zero
negative/non-finite persisted rate with reason=ok rejected as integrity error
```

Existing worker formula regression remains green.

---

# 108. Targeted prerequisite tests — coverage

Mandatory:

```text
complete
partial one AP missing
partial one direction missing
none

stale AP count
reset AP count
gap-rejected AP count
no-baseline count

reason category counts non-exclusive
```

---

# 109. Targeted prerequisite tests — temporal

Mandatory:

```text
same-cycle AP timestamps

skew <=60 → may be complete
skew >60 → partial

fresh <=90
stale >90 <=180
unavailable >180

clock regression/future timestamp
→ unavailable

traffic watermark independent of Current State
```

---

# 110. Targeted prerequisite tests — AP lifecycle

Mandatory:

```text
AP added with no_baseline
AP next cycle valid

AP removed
next complete cycle excludes it

collector downtime
old cycle ages stale/unavailable

no previous-cycle AP fill
```

---

# 111. Prerequisite no-N+1 test

Query spy proves current summary does not execute:

```text
one query per AP
```

Use bounded set-based source reads.

AP page query count remains constant per page, not per row.

---

# 112. Prerequisite read-only tests

Prove:

```text
Observation DB row counts unchanged
user_version unchanged
no INSERT
no UPDATE
no DELETE
no migration
query_only/read-only connection
```

---

# 113. Admin config tests

PR B:

```text
Traffic default disabled

feature exact bool

Traffic enabled requires:
WEB_ADMIN_ENABLED=true
WEB_ADMIN_HOME_LIVE_ENABLED=true

refresh 60..300

timeout 5..60
timeout > Admin query deadline

page size 1..250

fresh max 30..300

stale >= fresh
stale <=600

skew 10..180

repr secret-safe
```

---

# 114. Runtime optional-source tests

Prove:

```text
Traffic service absent
does not make Admin runtime unavailable

Traffic service absent
does not break Home Live

feature false
Traffic service not touched

feature true + service absent
Traffic endpoints 503
Home Live endpoints remain operational
```

---

# 115. Admin route/security tests

For both Traffic endpoints:

```text
unauthenticated → 401

invalid Site → canonical existing validation

forbidden Site → 403

missing capability → 403

feature disabled authorized caller → canonical JSON 404

feature enabled valid caller → source result
```

Feature-disabled test proves source not called.

---

# 116. Duplicate/unknown parameter tests

When enabled:

Summary:

```text
any query parameter → 400
```

AP page:

```text
only cycle_id, limit, cursor
```

Unknown/duplicate:

```text
400
```

Also prove feature-disabled gate prevents endpoint schema probing per section 64/65.

---

# 117. Limit tests

Traffic AP page:

```text
omitted → 100
1 accepted
100 accepted
101 accepted
250 accepted
251 → 400
0 → 400
non-canonical integer → 400
```

Use the same independent default/max validation convention accepted for Home Live.

---

# 118. Cursor/cycle tests

Mandatory:

```text
valid page 1/page 2

cross-Site cursor rejected

changed cycle rejected

changed source context rejected

malformed cursor rejected

overlong cursor rejected

explicit removed/expired cycle → 400

no explicit cycle + no canonical current snapshot
→ 200 unavailable
```

---

# 119. API serializer tests

Assert exact public keys.

A future unexpected source field does not appear.

No:

```text
raw counters
IP
SSID
firmware
CPU
WLAN data
raw reason text
```

---

# 120. API quality tests

Mandatory:

```text
exact zero
partial numeric subtotal
none/null
stale numeric
unavailable/null

complete empty AP population

selected_source wired
selected_source LAN fallback
```

---

# 121. Frontend controller tests

Mandatory:

```text
Traffic failure leaves Home Live Current State intact

Current State failure does not clear Traffic

late old-generation Traffic response ignored

new Traffic summary + failed AP page
does not retain old AP rows

manual Refresh no overlap

timeout abort

hidden-tab neutral abort

visible return controlled refresh

Traffic 404 stops Traffic only

401 global session behavior preserved
```

---

# 122. Frontend strict-response tests

Reject:

```text
wrong api_version
wrong Site
wrong source_kind

unknown freshness
unknown coverage
unknown source
source_mixing_allowed=true

negative/non-finite rate
boolean rate

invalid counts
count invariant mismatch

total arithmetic mismatch

invalid page item
cycle mismatch
invalid cursor type
```

No partial render of malformed response.

---

# 123. Exact zero frontend test

Must explicitly test:

```text
download=0.0
upload=0.0
total=0.0

coverage=complete
freshness=fresh
```

UI shows numeric zero Mbps, not dash.

---

# 124. Privacy tests

Traffic code and telemetry must not emit:

```text
client MAC
client IP
SSID
AP MAC in telemetry
cursor
cycle_id
scope/source hash
raw query
raw SQL
raw exception
credentials
Omada payload
WLAN password data
```

AP MAC remains allowed only in authenticated API/UI DTO.

---

# 125. No direct Omada dependency test

New Traffic code must not import/use:

```text
OmadaProvider
requests
controller factory
get_observation_ap_*
list_observation_*
```

outside the already-existing Observation acquisition code.

Browser request cannot cause provider calls.

Use spy/mocking proof.

---

# 126. Regression boundary

Must remain green:

```text
Home Live Online
Authorized
Waiting
Other/Unknown
AP Online/Total
Client/AP freshness
Devices by AP
Online Devices
Access Points Now

Devices
Device Card
Visits
Observations

Portal
CAPPORT

Observation acquisition
Current State
Registry
Visit Lifecycle
Analytics
```

---

# 127. Targeted test gate

PR A minimum:

```bash
python -m pytest -q \
  tests/analytics \
  tests/observations \
  --tb=short
```

PR B minimum:

```bash
python -m pytest -q \
  tests/admin_web \
  tests/analytics \
  --tb=short
```

If focused Current Traffic modules are introduced, run them first and include exact commands in handoff.

---

# 128. Full Linux gate

For each implementation PR after targeted PASS:

```bash
python -m pytest -q -rs

PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app

git diff --check
git status --short
```

Record exact counts and SHA.

---

# 129. Pre-change gate

Before each separately authorized PR:

```bash
git fetch origin
git rev-parse origin/main
git status --short

python -m pytest -q -rs

PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app

git diff --check
```

Expected DRAFT baseline:

```text
dafbc40b6f5c5b3dde6b52fcc2c7689e95d05081
```

If newer, impact review mandatory if changes touch:

```text
app/observations/**
app/analytics/**
app/admin_web/**
app/config.py
app/settings.py
run.py

tests/observations/**
tests/analytics/**
tests/admin_web/**
```

---

# 130. Expected PR A files

Preferred:

```text
app/analytics/current_traffic.py
app/analytics/models.py
app/analytics/source_gateway.py
app/analytics/runtime.py
app/analytics/__init__.py

tests/analytics/test_current_traffic*.py
```

Only if proven required:

```text
app/analytics/config.py
```

No Observation source schema/worker file should need modification.

If `app/observations/**` modification becomes necessary:

```text
STOP
return exact gap
Tech Lead/Architect review required
```

---

# 131. Expected PR B files

Likely:

```text
app/admin_web/config.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/pages.py
app/admin_web/templates/admin/home.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/current_traffic_serialization.py

app/config.py
app/settings.py
.env.example

tests/admin_web/**
```

`run.py` only if actual composition requires narrow wiring not already available via AnalyticsRuntime.

No broad refactor.

---

# 132. Forbidden implementation areas

Do not change:

```text
Omada provider/token lifecycle
Auth/CAPPORT
Pending Session Cleaner
Visitor Registry schema/write
Visit schema/start/finalization
Current State schema/collector
Observation schema/worker/rate formula
Grafana/Loki/Alloy
Cisco
Omada Controller
production systemd
Nginx
```

No Knowledge Base files in this runtime task:

```text
AGENTS.md
docs/**
```

---

# 133. Coder PLAN contract after future authorization

Coder must return PLAN before edits with:

```text
exact baseline

PR A:
canonical cycle query
source selection SQL
coverage logic
freshness/skew logic
cursor/page design
query plans/tests

PR B:
feature config path
optional runtime wiring
two routes
capabilities
serializer allowlists
Traffic controller state
AbortController/generation/backoff
strict validation
telemetry
tests

proof:
no Omada
no Observation schema/worker change
no source mixing
```

No architecture options in this DRAFT are delegated to Coder.

---

# 134. Stop conditions

STOP affected work and return facts if:

- latest complete-success AP dynamic cycle cannot be selected through bounded read-only SQL;
- source cycle invariants differ from current code;
- correct Site aggregate requires cross-cycle mixing;
- source family must be mixed per AP to produce a value;
- required query needs Observation schema/index change;
- read service needs Omada;
- API needs Current State client counters as Mbps;
- Traffic cannot fail independently from Home Live;
- Traffic feature cannot be independently disabled;
- browser polling would alter Omada acquisition cadence;
- source semantics suggest traffic is WAN-only and require a different authority;
- full tests produce new product regression.

Do not silently broaden scope.

---

# 135. Production deployment boundary

Merge does not activate Traffic.

Repository default:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
```

Deployment:

```text
code first
feature disabled
```

Activation:

```text
separate Owner-controlled action
```

---

# 136. Production validation runtime context

All deployment/config validation must run with:

```text
the same Python interpreter
the same module/import context
the same relevant environment
```

as:

```text
captive-portal.service
```

Do not validate with an unrelated venv/runtime and assume service equivalence.

---

# 137. Code deployment runbook requirements

Future exact runbook includes:

```text
1 exact expected merged SHA
2 clean working tree gate
3 production branch/HEAD evidence

4 backup environment file preserving metadata

5 deploy code with Traffic flag false

6 validate config using service-equivalent Python/runtime

7 restart service

8 bounded wait for:
  systemd active/running
  actual HTTP listener readiness

9 Portal smoke
10 CAPPORT smoke
11 Admin login smoke
12 Home Live smoke
13 Devices/Visits/Observations smoke

14 verify Traffic is not rendered/requested
15 verify Observation cadence unchanged
16 inspect activation-window logs
```

`active/running` alone is not HTTP readiness.

---

# 138. Production code rollback

If feature-disabled code deployment fails mandatory gate:

```text
rollback code to previous accepted SHA/tag
restore environment if changed
restart
bounded HTTP readiness wait
verify Portal/CAPPORT/Admin/Home Live
```

Code rollback is distinct from Traffic feature rollback.

---

# 139. Traffic activation runbook requirements

After code deployment PASS and required prerequisite/Home gates:

```text
1 exact merged SHA still present
2 clean working tree
3 env backup

4 set:
WEB_ADMIN_HOME_TRAFFIC_ENABLED=true
and reviewed Traffic config

5 service-equivalent config validation BEFORE restart

6 verify env owner/group/mode contract

7 restart service

8 bounded systemd + HTTP readiness wait

9 Portal
10 CAPPORT
11 Admin login
12 Home Live current-state panels

13 authenticated Traffic summary
14 authenticated Traffic AP page

15 verify selected source metadata
16 verify coverage
17 verify exact zero behavior if naturally observable/test-fixture only
18 compare API result to CurrentTrafficReadService result

19 verify Observation cycle continues
20 verify Current State continues
21 verify Registry/Visit/Analytics continue

22 inspect activation-window logs
```

---

# 140. Traffic feature rollback

Fast product rollback:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
```

or restore pre-activation environment backup.

Then:

```text
restart
bounded HTTP readiness wait

verify Home Live remains enabled
verify Online/Auth/AP panels
verify Devices/Visits/Observations
verify Portal/CAPPORT
verify Observation continues
```

Do NOT:

```text
disable Observation
disable Current State
delete observations.sqlite3
delete current_state.sqlite3
```

---

# 141. Open-browser rollback behavior

If Traffic is disabled while an already-open Home page exists:

Traffic request receives:

```text
404 not_found
```

Traffic controller:

```text
stops Traffic polling
clears/hides Traffic-specific current data
shows small disabled/reload state if needed
leaves Home Live Current State operational
```

After reload:

```text
Home Live without Traffic
```

not legacy Home.

---

# 142. Production functional soak

After activation minimum:

```text
5 consecutive automatic Traffic refreshes
at production cadence

1 manual Refresh

1 hidden-tab pause/resume

2 simultaneous visible Home tabs
```

During soak:

```text
no overlapping Traffic requests
no old-generation append
no unexpected 400/401/403/404/429/500/503
unless deliberately injected

Traffic freshness advances
Home Live continues
Observation continues
Portal/CAPPORT remain healthy
```

---

# 143. Production performance gate

Synthetic tests do not replace production measurement.

Collect at least:

```text
20 route-completion measurements
for Traffic summary

20 route-completion measurements
for Traffic AP page
```

Minimum:

```text
40 measurements
```

Record per endpoint:

```text
count
p50
p95
max
HTTP 429 count
HTTP 503 count
HTTP 500 count
coverage distribution
freshness distribution
```

Proposed targets for Tech Lead review:

```text
Traffic summary p95 <= 100 ms

Traffic AP page p95 <= 250 ms
```

If targets fail:

```text
do not weaken correctness
return query plan/timing evidence
```

---

# 144. Production source reconciliation

At acceptance select at least one real Traffic snapshot and compare:

```text
Admin Traffic summary
=
CurrentTrafficReadService summary
```

For AP page:

```text
Admin AP rows
=
same pinned cycle/source rows
```

Do not compare only against Grafana.

Do not compare only against Omada UI instantaneous values because the product source is persisted Observation.

---

# 145. Production no-double-count proof

Acceptance record must show:

```text
selected source = wired OR LAN

Site total =
sum selected-source AP values

wired + LAN never summed

radio never added
```

If fallback selected:

```text
why LAN won coverage
```

must be visible in safe source metadata.

---

# 146. Production partial-coverage proof

If natural partial coverage occurs during acceptance, verify UI.

If not naturally occurring:

```text
backend/frontend automated tests are acceptance evidence
```

Production must not be intentionally disrupted merely to force counter reset/gap.

Production performance, however, must still use real production reads.

---

# 147. Production privacy gate

Inspect Traffic route telemetry/access logs.

Must not contain:

```text
client MAC
client IP
SSID
AP MAC
cursor
cycle_id
source hash
raw query
raw source exception
credentials
Omada payload
```

Safe aggregate fields only.

---

# 148. Production coexistence gate

After activation verify:

```text
Current State Client cycles continue
Current State AP cycles continue

Observation Client cycles continue
Observation AP cycles continue

Registry continues
Visit Lifecycle continues
Analytics remains available

Home Live Online/Auth/AP continues

Devices works
Device Card works
Visits works
Observations works

Portal works
CAPPORT works
```

No new service restart loop/errors.

---

# 149. Acceptance — architecture

Architecture PASS requires:

- one persisted Observation source path;
- no Omada read from Home;
- no new collector;
- no rate recomputation in Home;
- one complete-success AP cycle per current aggregate;
- one source family per Site snapshot;
- wired primary / LAN fallback;
- no wired/LAN/radio double count;
- no per-AP source blending;
- independent Traffic watermark;
- explicit freshness/coverage;
- radio-band excluded v1;
- channel load excluded;
- Site-aware;
- product/observability boundary preserved.

---

# 150. Acceptance — backend

Backend PASS requires:

- prerequisite read service accepted before UI;
- bounded set-based summary;
- bounded AP page;
- exact cycle pinning;
- stable keyset cursor;
- source integrity checks;
- exact zero preserved;
- invalid rate not zero;
- partial subtotal marked partial;
- stale/unavailable honest;
- AP add/remove safe;
- query deadline/cancellation;
- existing Admin auth/capability;
- source failure sanitized;
- DTO allowlist;
- route telemetry sanitized.

---

# 151. Acceptance — frontend

Frontend PASS requires:

- Download/Upload/Total;
- Mbps;
- observed time;
- Traffic freshness;
- coverage;
- AP table;
- exact zero;
- partial label;
- no-valid-rate state;
- stale;
- unavailable;
- error isolation;
- no overlap;
- AbortController;
- generation guard;
- hidden tab behavior;
- bounded backoff;
- manual Refresh integration;
- strict 200 validation;
- no browser persistence;
- Home Live remains functional on Traffic failure.

---

# 152. Accepted limitations for v1

`HOME-TRAFFIC-01` intentionally accepts:

```text
near-real-time, not realtime socket streaming

Traffic freshness based on persisted Observation,
not browser instant

AP physical traffic,
not guaranteed WAN-only

AP physical traffic,
not guaranteed selected SSID-only

wired preferred over LAN

LAN is Site-wide fallback,
not per-AP fallback

no radio-band UI v1

no RF channel-load metric

no per-client speed

no Today traffic

no long-term Traffic chart
```

These are not defects.

---

# 153. Follow-up boundaries

Separate future tasks:

```text
HOME-TRAFFIC-RADIO-01
  optional per-band view after source-support review

HOME-CHANNEL-LOAD-01
  only after precise RF/uplink product semantics

HOME-TODAY-01
  calendar-day counters/traffic

HOME-HEALTH-01
  product-safe health

HOME-AP-24H-01
  AP distribution history
```

No follow-up is silently included in this implementation.

---

# 154. Tech Lead review questions

Please review these already-selected DRAFT decisions:

1. Is explicit two-PR decomposition accepted:
   `HOME-TRAFFIC-READ-01` then `HOME-TRAFFIC-01`?

2. Is the canonical current snapshot correctly defined as:
   newest `ap_dynamic` cycle with
   `completed + complete=1 + result=success`?

3. Is strict one-cycle aggregation accepted instead of independent latest per AP?

4. Is source policy accepted:
   wired primary, LAN Site-wide fallback, radio excluded?

5. Is coverage-based Site-wide source selection accepted?

6. Is per-AP source mixing correctly prohibited?

7. Is `0 Mbps + reason=ok` correctly treated as exact zero?

8. Are freshness defaults `90/180s` acceptable?

9. Is max cross-AP source skew `60s` acceptable?

10. Is conservative Traffic watermark = oldest selected section timestamp accepted?

11. Is `coverage_status = complete|partial|none` sufficient?

12. Is partial numeric subtotal allowed only with visible Partial coverage?

13. Is AP Traffic v1 pagination by canonical AP MAC sufficient without sort/filter?

14. Are capability choices accepted:
    summary=`admin.read.overview`,
    AP page=`admin.read.observations`?

15. Are API routes accepted:
    `/current-traffic/summary`
    `/current-traffic/aps`?

16. Is separate default-off `WEB_ADMIN_HOME_TRAFFIC_ENABLED` accepted?

17. Is Traffic enabled only when Home Live is enabled accepted?

18. Are production p95 targets `100ms summary / 250ms page` accepted?

19. Is Home Live final production acceptance required before Traffic production activation?

20. Is radio-band traffic correctly deferred to a separate task?

Any required correction should be returned as targeted revision items; rewriting the architecture from scratch should not be necessary unless a source contract assumption is disproven.

---

# 155. Current authorization status

```text
TASK-HOME-TRAFFIC-01-DRAFT

Status:
DRAFT FOR TECH LEAD REVIEW

IMPLEMENTATION NOT AUTHORIZED
BRANCH NOT AUTHORIZED
CODE NOT AUTHORIZED
COMMIT NOT AUTHORIZED
PUSH NOT AUTHORIZED
PR NOT AUTHORIZED
MERGE NOT AUTHORIZED
PRODUCTION CHANGE NOT AUTHORIZED
```

The only allowed next action is:

```text
Tech Lead review
```

Then:

```text
targeted DRAFT revision if needed
→ FINAL
→ separate Owner implementation authorization
→ Coder PLAN
→ PR A read prerequisite
→ review/Linux gate/merge
→ PR B Admin/UI
→ review/Linux gate/merge
→ code deployment feature disabled
→ separate production activation
→ soak/performance/privacy/coexistence acceptance
```

---

# 156. Final architecture statement

The Home Traffic v1 chain is:

```text
existing Omada AP polling
→ existing cumulative counters
→ existing Observation rate derivation
→ observations.sqlite3
→ one complete-success AP dynamic cycle
→ one Site-wide selected source family
→ CurrentTrafficReadService
→ AdminQueryService
→ Site-scoped Admin API
→ isolated Home Traffic controller
```

It introduces:

```text
no new source of truth
no new collector
no new Omada request
no source DB mutation
no hidden fallback across cycles
no double counting
```

The feature is a read-only product projection over already persisted traffic evidence.
