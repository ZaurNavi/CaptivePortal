# TASK-HOME-ACTIVITY-01 — Admin Console Home Visits and Traffic Summary — FINAL

**Project:** CaptivPortal  
**Parent product concept:** `TASK-HOME-01 — Admin Console Home v1`  
**Supersedes / absorbs:** `HOME-TODAY-01`  
**Type:** final architecture / coder-ready implementation specification  
**Status:** `FINAL SPECIFICATION`  
**Implementation authorization:** `NOT GRANTED BY THIS DOCUMENT`  
**Branch / code / commit / push / PR / merge:** `NOT GRANTED BY THIS DOCUMENT`  
**Deployment / production activation:** `SEPARATE OWNER AUTHORIZATION REQUIRED`  
**Verified baseline:** `origin/main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`  
**Baseline verified:** `2026-08-25`  
**Prepared after:** Owner + Tech Lead review  
**Execution mode until explicit Owner authorization:** `planning-only`

---

# 1. Final purpose

Implement one compact Home panel:

```text
Visits and Traffic
```

The panel compares:

```text
Today
vs
Selected period
```

with the same two product metrics:

```text
Authorized visits
Traffic
```

The panel is operational context for Home.

It is NOT:

```text
a full Analytics page
a Traffic drill-down page
a Visit report
a billing report
an Internet/WAN meter
a Grafana replacement
```

---

# 2. Decisions already closed

The following decisions are FINAL and MUST NOT be reopened during implementation unless current repository facts directly contradict them:

```text
1. One successful Visit-opening authorization = one Authorized visit.

2. Authorized visits are based on Visit Lifecycle persisted facts,
   not AuthSession count.

3. Historical Traffic authority is Visit Lifecycle
   visit_source_events persisted offline traffic evidence.

4. Traffic remains an estimated completed-session metric.

5. There is no artificial Home Activity limit of 31 or 90 days.

6. HOME-TODAY-01 is absorbed into HOME-ACTIVITY-01.
```

If implementation discovers a factual source conflict, STOP and return evidence rather than silently redesigning.

---

# 3. Current source facts verified on baseline

Current Visit Lifecycle schema v2 contains:

```text
visits
visit_authorizations
visit_source_events
visit_reader_state
```

Current `visits.started_at` is created from the successful `authorized_at` that opens the Visit.

Current Visit start evidence fields are immutable.

Current `visit_source_events.processing_result` schema permits exactly:

```text
pending_match
closed
unmatched
invalid
```

Current normalized offline persistence can contain:

```text
site_id
client_mac
controller_event_at
received_at
ssid
reported_connected_seconds
reported_traffic_total_bytes
processing_result
reason
event_id
```

Current normalized event ID is derived from:

```text
webhook_id:text_index
```

Current `event_id` is the `visit_source_events` primary key.

Current Current State configuration already owns the canonical configured guest SSID list:

```text
CURRENT_STATE_CLIENT_SSIDS_JSON
```

Activity MUST reuse that scope and MUST NOT introduce a competing guest-SSID list.

---

# 4. Current Home architecture to preserve

Home already contains:

```text
Current State
Current Traffic
shared Refresh
bounded coordinator
AbortController ownership
generation protection
hidden-tab pause
retry/backoff
Site-aware Admin API
```

Activity is added into the existing Home orchestration.

Do NOT create:

```text
a new independent polling subsystem
a separate browser scheduler unrelated to Home coordinator
a direct Omada browser path
```

---

# 5. User-facing panel

Desktop concept:

```text
┌──────────────────────── Visits and Traffic ───────────────────────┐
│                                                                   │
│ TODAY                          SELECTED PERIOD                     │
│ 25 Aug 00:00 → 11:20 +04      Last 24 hours                      │
│                                24 Aug 11:20 → 25 Aug 11:20 +04   │
│                                                                   │
│ Authorized visits      32      Authorized visits           71    │
│ Traffic        4.8 GB Estimated Traffic         9.7 GB Estimated │
│                                                                   │
│ Complete                       Partial · coverage through …       │
│ Estimated completed sessions   Estimated completed sessions       │
│                                                                   │
│                    [ Change period ]                              │
└───────────────────────────────────────────────────────────────────┘
```

Exact numbers are illustrative.

---

# 6. Narrow/mobile layout

At narrow width:

```text
Visits and Traffic

TODAY
boundaries
Authorized visits
Traffic · Estimated
quality

SELECTED PERIOD
period selector
boundaries
Authorized visits
Traffic · Estimated
quality
```

Requirements:

```text
no horizontal page scroll
Today first
Selected second
keyboard-operable picker
quality remains visible
Estimated remains visible
```

---

# 7. Metric A — Authorized visits

API machine field:

```text
authorized_visits
```

Visible label:

```text
Authorized visits
```

One unit:

```text
one Visit opened by one successful portal authorization
```

Never use visible wording:

```text
people
persons
unique people
AuthSession
auth run
```

---

# 8. Authorized Visit cohort

A Visit belongs to requested interval:

```text
[from_utc,to_utc)
```

when:

```text
v.site_id = requested Site

v.started_at >= from_utc
v.started_at <  to_utc

v.start_ssid belongs to canonical guest SSID scope
```

Count:

```text
one qualifying Visit row = one unit
```

Not:

```text
one authorization row
one AuthSession
one current Omada client
```

---

# 9. Opening authorization integrity

The qualifying Visit must have opening authorization evidence consistent with:

```text
visit_id
start_auth_session_id
start_auth_run_number
authorized_at == visits.started_at
```

If exact opening evidence is missing or contradictory:

```text
do not invent a timestamp
do not count a later authorization as replacement
do not rewrite Visit persistence
```

Return:

```text
verified subtotal
status=partial
quality reason
integrity anomaly count
```

---

# 10. Authorized Visit edge cases

Required semantics:

```text
association before range + successful Visit-opening auth in range
→ included

Visit opened before range but stays online in range
→ excluded from that range

Visit started exactly at from
→ included

Visit started exactly at to
→ excluded

open Visit
→ counts

Visit closes later
→ previous cohort does not move

duplicate authorization run
→ no extra Visit unit

multiple successful authorizations in one still-open Visit
→ one Visit unit

new Visit after previous Visit closed
→ new unit

out-of-order later auth evidence
→ does not rewrite started_at
→ quality anomaly only
```

---

# 11. Canonical guest SSID scope — one source of truth

Activity MUST NOT add:

```text
WEB_ADMIN_HOME_ACTIVITY_GUEST_SSIDS
guest_ssids inside Activity Site JSON
another static Activity SSID list
```

Canonical Activity guest scope is derived from the same current configured source used by Home Current State:

```text
CURRENT_STATE_CLIENT_SSIDS_JSON
```

Current baseline configuration parser already validates this as:

```text
non-empty JSON string array
exact strings
duplicates forbidden
UTF-8 bounded
```

Activity consumes this canonical scope.

---

# 12. Site/scope consistency gate

When Activity is enabled for a Site:

```text
Site MUST exist in Current State Site configuration
canonical guest SSID scope MUST be available
Activity MUST consume exactly that scope
```

If Activity cannot obtain the same canonical guest scope:

```text
Activity for that Site = unavailable
```

Do NOT silently fall back to another SSID list.

---

# 13. Home Traffic scope distinction

Current `Traffic Now` is AP physical/network traffic and is intentionally not an SSID-only metric.

Therefore:

```text
Home Live client scope
→ canonical configured guest SSIDs

Home Activity historical Traffic
→ same canonical configured guest SSIDs

Home Traffic Now
→ AP physical traffic scope
```

This difference MUST remain explicit in UI/help text.

Do not falsely claim Home Traffic Now is guest-only.

No configuration mismatch may masquerade as the same metric.

---

# 14. Metric B — Traffic

API field:

```text
traffic
```

Visible label:

```text
Traffic
```

Primary value:

```text
combined estimated bytes from eligible completed guest-session offline reports
```

API unit:

```text
bytes
```

UI adaptive unit:

```text
B / KB / MB / GB / TB
```

No Download/Upload split in v1.

---

# 15. Traffic authority

Authoritative persistence:

```text
visits.sqlite3
```

Authoritative table:

```text
visit_source_events
```

Authoritative event family:

```text
omada.client_offline
```

Traffic value:

```text
reported_traffic_total_bytes
```

No Home Activity request calls Omada.

---

# 16. Traffic estimate meaning

The normalizer converts Omada reported:

```text
B
KB
MB
GB
TB
```

to integer byte estimate using:

```text
binary 1024 multipliers
ROUND_HALF_UP
```

Therefore the Traffic metric is permanently:

```text
Estimated
```

even when quality/coverage status is complete.

---

# 17. Estimated is always visible

The visible Traffic value MUST always include:

```text
Estimated
```

Examples:

```text
4.8 GB · Estimated

0 B · Estimated

4.8 GB · Partial · Estimated

— · Unavailable · Estimated
```

Do not hide `Estimated` only inside tooltip/details.

---

# 18. Mandatory visible Traffic explanation

A compact persistent helper MUST communicate all four facts:

```text
completed guest sessions only

active session appears after offline evidence is recorded

whole reported volume is attributed to session end time

not WAN / Internet / billing traffic
```

Recommended compact text:

```text
Estimated from completed guest sessions.
Active sessions appear after offline reporting.
Volume is attributed to session end.
Not WAN/Internet or billing traffic.
```

Localization may change wording, not meaning.

---

# 19. Traffic interval attribution

Preferred event timestamp:

```text
controller_event_at
```

Traffic contribution belongs to interval when:

```text
controller_event_at >= from_utc
controller_event_at <  to_utc
```

No interval clipping of bytes.

Example:

```text
session crosses midnight
controller reports 3 GB at 00:30

→ entire 3 GB belongs to interval containing 00:30
```

---

# 20. Received-time-only evidence

For FINAL v1 numeric Traffic inclusion:

```text
controller_event_at is REQUIRED
```

If an otherwise relevant offline event has no controller timestamp but has only:

```text
received_at
```

then:

```text
do NOT include its bytes in exact subtotal
count as excluded time-fallback/anomalous evidence
status becomes partial when attributable to requested Site/SSID population
```

Reason:

```text
event-time attribution is less certain
semantic replay dedupe is weaker without stable controller time
```

This is stricter than the earlier DRAFT.

---

# 21. Traffic processing_result contract

Current schema values are handled exactly as follows.

| `processing_result` | Include bytes? | Excluded count? | Makes partial? | Meaning for Activity |
|---|---:|---:|---:|---|
| `closed` | YES, if all Traffic eligibility fields are valid | no | no by itself | terminal valid event matched to Visit |
| `unmatched` | YES, if all Traffic eligibility fields are valid | no | no by itself | terminal structurally valid offline event; Visit match is not required for general guest Traffic |
| `pending_match` | NO | `pending_event_count += 1` | YES when attributable to requested Site/SSID/time | not terminal yet; value may change |
| `invalid` | NO | `invalid_event_count += 1` | YES when attributable to requested Site/SSID/time | insufficient event validity |
| unknown future value | NO | n/a | source becomes unavailable | fail closed; unsupported processing contract/schema |

---

# 22. Why `unmatched` is allowed

Traffic is intentionally:

```text
general guest-session traffic
```

not:

```text
only successfully authorized Visit traffic
```

Therefore a structurally valid terminal offline event does not need a Visit match.

`unmatched` itself is a Visit-correlation outcome.

It is not automatically a Traffic-invalid outcome.

---

# 23. Traffic eligibility fields

A terminal `closed` or `unmatched` row contributes only when all are true:

```text
event_type == omada.client_offline

site_id == requested Site

ssid exactly belongs to canonical guest scope

client_mac is valid/present

controller_event_at is valid/present

reported_traffic_total_bytes is non-null non-negative integer

processing_result in {closed, unmatched}
```

No row contributes merely because it contains a traffic number.

---

# 24. Traffic exclusions

Within attributable requested Site/SSID/range evidence, count separately:

```text
pending_event_count
invalid_event_count
missing_traffic_count
missing_controller_time_count
semantic_duplicate_count
other_excluded_event_count
```

The public DTO exposes counts only, never event identities.

---

# 25. Traffic partial rules

Traffic becomes `partial` if the requested range has one or more attributable events that are:

```text
pending_match

invalid with enough Site/SSID/time context to belong to range

missing reported traffic

missing controller time

excluded because semantic confidence is insufficient
```

`unmatched` alone does NOT make Traffic partial.

A semantic duplicate that is confidently identified and suppressed does NOT make Traffic partial by itself; it is diagnostic evidence.

---

# 26. Unknown processing_result fail-closed

Current schema v2 CHECK only permits four known values.

If runtime somehow observes an unsupported value while claiming supported schema:

```text
Traffic metric = unavailable
quality_reason = unsupported_processing_result
```

Do not:

```text
ignore it
include it
treat as unmatched
```

A future schema version must be explicitly reviewed before Activity accepts it.

---

# 27. Duplicate event_id

Because `event_id` is primary key:

```text
one persisted event_id
→ one row
→ one possible contribution
```

Replay of the same normalized event ID cannot double Traffic.

Required test:

```text
same event_id replay
→ same Traffic total
```

---

# 28. Semantic duplicate across different event_id

A controller/source replay may theoretically produce the same offline session with another `event_id`.

Activity adds conservative read-side semantic replay suppression.

For eligible terminal rows, define replay fingerprint:

```text
site_id
client_mac
ssid
controller_event_at
reported_connected_seconds
reported_traffic_total_bytes
```

Rows with an identical full fingerprint:

```text
contribute bytes once
semantic_duplicate_count += duplicates suppressed
```

This is read-only aggregation.

No source row is deleted or modified.

---

# 29. Semantic dedupe limits

Semantic replay suppression only applies when the full fingerprint is stable enough.

If required fingerprint confidence is missing:

```text
do not invent heuristic clustering by “close enough” timestamps
do not collapse rapid reconnects by MAC alone
```

Such evidence is excluded/partial according to eligibility rules.

No fuzzy time-window dedupe.

---

# 30. Traffic SQL dedupe requirement

Semantic dedupe must be set-based.

Allowed shape:

```text
GROUP BY full semantic replay fingerprint
```

or equivalent deterministic SQL.

Forbidden:

```text
load all events into Python
loop and dedupe in application memory
```

---

# 31. Traffic active sessions

Active sessions have no final offline Traffic report yet.

Therefore:

```text
active session bytes are not included
```

This is expected.

UI helper must make this visible so delayed jumps are not mistaken for bugs.

---

# 32. Traffic zero

A valid terminal event with:

```text
reported_traffic_total_bytes = 0
```

contributes valid zero.

A successful fully covered query with no eligible traffic:

```text
0 B · Estimated
```

Missing evidence is NOT zero.

---

# 33. No AP-counter conversion

Activity Traffic does NOT:

```text
integrate Current Traffic Mbps
derive bytes from AP rate samples
sum radio Mbps
sum WAN-like counters
```

Therefore AP counter:

```text
reset
wrap
baseline
gap
```

is not part of this metric formula.

---

# 34. Arbitrary period — final user contract

The picker must behave like a familiar Grafana-style period selector.

It supports:

```text
quick ranges

custom From date

custom To date

optional From time

optional To time
```

Date-only custom input is VALID.

This supersedes the earlier DRAFT prohibition.

---

# 35. Quick ranges

Required:

```text
Last 24 hours
Yesterday
Last 48 hours
Last 7 days
Current month
Last 30 days
Custom
```

No arbitrary:

```text
31 days
```

quick range.

---

# 36. Date-only From

If user selects:

```text
From date = 2026-08-01
From time = empty
```

resolve:

```text
2026-08-01 00:00:00
in Site timezone
```

This is inclusive technical `from`.

---

# 37. Date-only To — inclusive user date

If user selects:

```text
To date = 2026-08-05
To time = empty
```

user-visible meaning:

```text
through the whole day 5 August
```

technical exclusive boundary:

```text
00:00 of next local calendar day
```

Therefore:

```text
[2026-08-01 00:00 local,
 2026-08-06 00:00 local)
```

No `23:59:59.999` hack.

---

# 38. Same date, date-only

User may select:

```text
From date = 2026-08-25
To date   = 2026-08-25
no times
```

This means one full local calendar day:

```text
[25 Aug 00:00,
 26 Aug 00:00)
```

It is VALID if the resolved exclusive end is not in the future relative to request policy.

---

# 39. Optional From time

If provided:

```text
From date + From time
```

resolve exactly to that Site-local wall-clock timestamp.

Technical boundary remains inclusive.

---

# 40. Optional To time

If provided:

```text
To date + To time
```

resolve exactly to that Site-local wall-clock timestamp.

Technical boundary is exclusive.

The special “inclusive end date → next midnight” rule applies ONLY when To time is empty.

---

# 41. Mixed custom examples

Allowed:

```text
From date only
To date only

From date + time
To date only

From date only
To date + time

From date + time
To date + time
```

Every accepted range becomes one canonical half-open UTC interval.

---

# 42. Server-owned timezone resolution

Browser timezone is NEVER the source of truth.

Forbidden:

```javascript
new Date(localInput).toISOString()
```

for authoritative Activity range conversion.

The server resolves all custom wall-clock values using the configured Site timezone.

---

# 43. Site timezone source

Activity requires one Site-specific timezone mapping.

Activity configuration MUST NOT contain guest SSIDs.

Preferred config:

```text
WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON
```

Conceptual:

```json
{
  "<site-id>": {
    "timezone": "Asia/Baku",
    "visits_coverage_from_utc": "2026-08-19T00:00:00.000Z",
    "traffic_coverage_from_utc": "2026-08-19T00:00:00.000Z"
  }
}
```

Coverage values may be null when a proven start is not yet known.

---

# 44. Site context fields

Per Site:

```text
timezone
visits_coverage_from_utc
traffic_coverage_from_utc
```

There is NO:

```text
guest_ssids
```

in Activity Site context.

Canonical SSID scope comes from Current State.

---

# 45. Site context validation

`timezone`:

```text
valid IANA timezone
```

Coverage starts:

```text
null
or canonical UTC timestamp
not future at configuration validation time where safely checkable
```

Site key:

```text
canonical allowed Site ID
```

Invalid Activity Site context:

```text
Activity unavailable for affected Site
Admin remains active
Home Live remains active
Current Traffic remains active
Portal remains active
```

---

# 46. Custom range preview before Apply

Before custom Apply, UI MUST show:

```text
Site timezone
resolved local From
resolved local To
resolved UTC From
resolved UTC To
```

Therefore add lightweight authenticated resolver endpoint:

```text
GET /admin/api/v1/sites/{site_id}/home-activity/range-preview
```

It performs:

```text
Site/capability/feature checks
timezone resolution
custom range validation
```

It does NOT:

```text
read Visits
read Traffic
call Omada
consume heavy historical query
```

---

# 47. Range preview input

Exact custom fields:

```text
from_date=YYYY-MM-DD
to_date=YYYY-MM-DD

optional:
from_time=HH:MM[:SS]
to_time=HH:MM[:SS]
```

Unknown parameters:

```text
400
```

Duplicates:

```text
400
```

Missing required date:

```text
400
```

---

# 48. Preview output

Conceptual:

```json
{
  "timezone": "Asia/Baku",
  "requested": {
    "from_date": "2026-08-01",
    "from_time": null,
    "to_date": "2026-08-05",
    "to_time": null,
    "to_date_inclusive": true
  },
  "resolved": {
    "from_local": "2026-08-01T00:00:00+04:00",
    "to_local_exclusive": "2026-08-06T00:00:00+04:00",
    "from_utc": "2026-07-31T20:00:00.000Z",
    "to_utc": "2026-08-05T20:00:00.000Z"
  }
}
```

No data source access.

---

# 49. Apply behavior

Apply sends the same requested custom fields to the Selected data endpoint.

Server resolves again.

The returned data response includes its final resolved boundaries.

If they differ from preview for any reason:

```text
render returned boundaries
do not hide the difference
```

No browser-side assumption overrides server result.

---

# 50. DST nonexistent local time

If an explicitly chosen local date/time does not exist due to DST transition:

```text
400 invalid_request
```

Visible message:

```text
This local time does not exist in the Site timezone.
Choose another time.
```

No automatic shift.

---

# 51. DST ambiguous local time

Do NOT silently choose:

```text
fold=0
fold=1
```

v1 policy:

```text
ambiguous explicitly chosen local time
→ reject
```

Visible message:

```text
This local time occurs twice in the Site timezone.
Choose an unambiguous time.
```

No offset picker is required in v1.

---

# 52. Date-only midnight and DST

Date-only midnight is resolved through the same strict timezone resolver.

If that local midnight is:

```text
nonexistent
or ambiguous
```

the range is rejected.

Do not silently choose an offset.

---

# 53. Future custom range

Final resolved:

```text
from_utc < to_utc
```

required.

Selected data endpoint rejects:

```text
to_utc > evaluated_at
```

No silent clipping to now.

Preview may show a future resolved end with validation state if desired, but Apply/data request must reject it.

Preferred UI:

```text
show preview
show “End is in the future”
disable Apply
```

---

# 54. Rolling presets

Server resolution:

```text
Last 24h = evaluated_at - 24 hours → evaluated_at

Last 48h = evaluated_at - 48 hours → evaluated_at

Last 7d  = evaluated_at - 7*24 hours → evaluated_at

Last 30d = evaluated_at - 30*24 hours → evaluated_at
```

These are elapsed rolling windows.

---

# 55. Yesterday

Yesterday is previous completed Site-local calendar day:

```text
previous local midnight
→ current local midnight
```

It may be:

```text
23h
24h
25h
```

depending on timezone rules.

---

# 56. Current month

Current month:

```text
Site-local first day of current month 00:00
→ evaluated_at
```

It changes over time.

---

# 57. Today

Today:

```text
Site-local current date 00:00
→ evaluated_at
```

Today is NOT:

```text
Last 24 hours
```

---

# 58. Exact period display

Both halves display:

```text
resolved local boundaries
timezone
```

For custom date-only end, UI should visibly communicate:

```text
user selected through 5 Aug
technical end = 6 Aug 00:00 local
```

No hidden inclusive/exclusive conversion.

---

# 59. No artificial duration ceiling

The final server rule:

```text
range is NOT rejected solely because it is long
```

Allowed if source history exists:

```text
32 days
90 days
365 days
multiple years
```

There is no hidden:

```text
31-day cap
90-day cap
```

---

# 60. No silent clipping

If requested range extends outside proven source coverage:

```text
query the requested interval
return observed subtotal
mark partial
return coverage boundaries
```

Do NOT silently change:

```text
requested from
requested to
```

to fit available evidence.

---

# 61. Stored rows are not coverage proof

The following do NOT prove collection started continuously at that time:

```text
MIN(visits.started_at)

MIN(visit_source_events.controller_event_at)

earliest persisted row

DB file creation timestamp
```

They are evidence timestamps only.

They are not authoritative `coverage_from_utc`.

---

# 62. Per-metric coverage

Coverage is independent for:

```text
Authorized visits
Traffic
```

Each metric returns:

```text
coverage_from_utc
coverage_through_utc
fully_covered
coverage_status
quality_reasons
```

Visits and Traffic may have different coverage boundaries.

---

# 63. Visits coverage_from

Primary source:

```text
Activity Site context
visits_coverage_from_utc
```

Meaning:

```text
operator-verified start of continuous Visit collection semantics
for this Site under the accepted current source contract
```

If null:

```text
coverage start unknown
```

Do not infer it from first Visit.

---

# 64. Traffic coverage_from

Primary source:

```text
Activity Site context
traffic_coverage_from_utc
```

Meaning:

```text
operator-verified start of continuous normalized offline Traffic collection
for this Site under the accepted current source contract
```

If null:

```text
coverage start unknown
```

Do not infer it from first traffic row.

---

# 65. Visits coverage_through

For a readable Activity query:

```text
coverage_through_utc = evaluated_at
```

only when the Visit Lifecycle start/source path required for Visit opening is currently available under the accepted runtime contract.

Reason:

```text
a successful portal Visit-opening authorization is generated by this application path itself
```

If Visit source is unavailable:

```text
Authorized visits metric unavailable
coverage_through_utc = null
```

---

# 66. Traffic coverage_through

Traffic uses persisted Visit reader heartbeat/progress.

Primary evidence:

```text
visit_reader_state.updated_at
```

representing the latest successful reader progress/EOF processing heartbeat.

Traffic:

```text
coverage_through_utc = latest safe reader coverage heartbeat
```

Do not substitute:

```text
latest traffic event timestamp
```

because absence of an event does not prove source inactivity.

---

# 67. Traffic reader freshness

Expose:

```text
reader_watermark_at
ingestion_freshness
```

Freshness policy uses Activity-specific configured age bounds.

Example machine enum:

```text
fresh
stale
unavailable
```

This is separate from historical range coverage status.

---

# 68. Coverage intersection

For a metric requested interval:

```text
R = [requested_from, requested_to)
```

proven source interval:

```text
C = [coverage_from, coverage_through)
```

when both bounds are known.

Return:

```text
covered_range = intersection(R,C)
```

But query value remains over requested R.

No clipping.

---

# 69. Coverage status

## `complete`

Only when:

```text
coverage_from known
coverage_through known
requested_from >= coverage_from
requested_to <= coverage_through
no metric-specific quality anomaly affecting completeness
```

## `partial`

When source is readable and a numeric observed subtotal can be returned, but:

```text
coverage_from unknown
requested range begins before coverage_from
requested range ends after coverage_through
or metric-specific eligible evidence is excluded
```

## `unavailable`

When no trustworthy numeric result can be produced because:

```text
source unreadable
schema unsupported
unsupported processing result
query deadline
integrity failure
```

---

# 70. Zero and coverage

A numeric:

```text
0
0 B
```

may be `complete` only when the full requested range is proven covered.

If range reaches before known collection start:

```text
0 · Partial
0 B · Partial · Estimated
```

Never:

```text
0 complete
```

for unproven historical time.

---

# 71. Earlier persisted evidence outside proven coverage

Rows may exist before configured `coverage_from_utc`.

They may still contribute to observed requested subtotal.

But:

```text
their existence does not upgrade coverage
```

Example:

```text
requested range starts before proven start
old rows exist

→ subtotal includes them
→ status partial
```

---

# 72. DTO — requested vs resolved vs coverage

Every data response contains:

```text
requested range
resolved range
metric-specific coverage
```

These are distinct.

No overloaded field.

---

# 73. Range DTO

Conceptual:

```json
{
  "requested": {
    "kind": "custom",
    "from_date": "2026-08-01",
    "from_time": null,
    "to_date": "2026-08-05",
    "to_time": null,
    "to_date_inclusive": true
  },
  "resolved": {
    "from_utc": "2026-07-31T20:00:00.000Z",
    "to_utc": "2026-08-05T20:00:00.000Z",
    "from_local": "2026-08-01T00:00:00+04:00",
    "to_local_exclusive": "2026-08-06T00:00:00+04:00",
    "timezone": "Asia/Baku"
  }
}
```

For presets, `requested` uses stable preset enum instead of custom raw fields.

---

# 74. Metric coverage DTO

Conceptual:

```json
{
  "coverage": {
    "coverage_from_utc": "2026-08-19T00:00:00.000Z",
    "coverage_through_utc": "2026-08-25T07:19:55.000Z",
    "covered_from_utc": "2026-08-19T00:00:00.000Z",
    "covered_through_utc": "2026-08-25T07:19:55.000Z",
    "fully_covered": false,
    "status": "partial",
    "quality_reasons": ["requested_before_coverage_start"]
  }
}
```

If no overlap:

```text
covered_from_utc=null
covered_through_utc=null
fully_covered=false
status=partial
```

when source is readable and subtotal semantics remain available.

---

# 75. Stable coverage quality enums

Minimum allowlist:

```text
coverage_start_unknown
requested_before_coverage_start
requested_after_coverage_through
source_unavailable
query_deadline
opening_authorization_evidence_missing
authorization_chronology_anomaly
pending_offline_events
invalid_offline_events
missing_reported_traffic
missing_controller_time
semantic_replay_suppressed
unsupported_processing_result
reader_stale
reader_unavailable
```

Do not expose arbitrary exception strings.

---

# 76. Authorized Visits DTO

Conceptual:

```json
{
  "value": 32,
  "status": "complete",
  "cohort": "visit_opening_authorization",
  "source_kind": "visit_lifecycle",
  "verified_visit_count": 32,
  "integrity_anomaly_count": 0,
  "coverage": {
    "coverage_from_utc": "...",
    "coverage_through_utc": "...",
    "covered_from_utc": "...",
    "covered_through_utc": "...",
    "fully_covered": true,
    "status": "complete",
    "quality_reasons": []
  },
  "earliest_persisted_evidence_at": "...",
  "latest_persisted_evidence_at": "..."
}
```

`earliest_persisted_evidence_at` is diagnostic only.

---

# 77. Traffic DTO

Conceptual:

```json
{
  "bytes": 5153960755,
  "status": "partial",
  "estimated": true,
  "attribution": "completed_session_end",
  "source_kind": "omada_offline_reported_traffic",
  "eligible_terminal_event_count": 48,
  "included_fingerprint_count": 46,
  "unmatched_included_event_count": 8,
  "pending_event_count": 1,
  "invalid_event_count": 0,
  "missing_traffic_count": 1,
  "missing_controller_time_count": 0,
  "semantic_duplicate_count": 2,
  "other_excluded_event_count": 0,
  "reader_watermark_at": "...",
  "ingestion_freshness": "fresh",
  "coverage": {
    "coverage_from_utc": "...",
    "coverage_through_utc": "...",
    "covered_from_utc": "...",
    "covered_through_utc": "...",
    "fully_covered": false,
    "status": "partial",
    "quality_reasons": ["pending_offline_events","missing_reported_traffic"]
  },
  "earliest_persisted_evidence_at": "...",
  "latest_persisted_evidence_at": "..."
}
```

No event/client identities.

---

# 78. Final endpoint architecture — separate Today and Selected

The earlier combined endpoint proposal is REMOVED.

Final endpoints:

```text
GET /admin/api/v1/sites/{site_id}/home-activity/today

GET /admin/api/v1/sites/{site_id}/home-activity/selected

GET /admin/api/v1/sites/{site_id}/home-activity/range-preview
```

Reason:

```text
Today must survive heavy Selected failure
Selected refresh policy differs from Today
long static custom range should not be recomputed every minute
independent Admin deadlines are simpler and safer
```

---

# 79. Today endpoint

No query parameters.

Returns:

```text
server evaluated_at
Today requested/resolved range
Authorized visits
Traffic
next_site_midnight_utc
canonical Site timezone
canonical guest scope
```

One Admin query slot.

One Admin deadline.

---

# 80. Selected endpoint

For preset:

```text
period=<enum>
```

For custom:

```text
period=custom
from_date=YYYY-MM-DD
to_date=YYYY-MM-DD
optional from_time
optional to_time
```

Returns:

```text
its own evaluated_at
requested/resolved range
Authorized visits
Traffic
canonical Site timezone
canonical guest scope
```

One independent Admin query slot.

One independent Admin deadline.

---

# 81. Today / Selected temporal independence

The two endpoints do NOT claim one atomic cross-endpoint snapshot.

Each returns:

```text
evaluated_at
```

The UI displays accepted boundaries.

For rolling selected periods, requests are issued immediately after Today in the same Home coordinator cycle, so evaluation instants are close but explicitly distinct.

No false atomicity claim.

---

# 82. Selected failure isolation

Mandatory behavior:

```text
Today request succeeds
→ Today rendered and accepted

Selected long request then receives:
429 / 503 query_deadline / 503 source_unavailable / network error

→ Today remains visible and valid
→ Selected shows its own failure/stale state
```

Selected failure MUST NOT clear:

```text
Today
Current State
Current Traffic
```

---

# 83. Today failure isolation

If Today fails:

```text
Selected previous accepted state may remain with visible age/failure state
```

One side does not blank the other merely because they share one panel.

---

# 84. Admin capability

All Activity endpoints require:

```text
admin.read.overview
```

No broader capability.

Range preview also requires the same Home overview capability.

---

# 85. Route gate order

Required:

```text
HTTPS/source network/query-size boundary
→ Admin session
→ Site syntax
→ Site allowlist
→ admin.read.overview
→ Activity feature flag
→ Activity Site context / canonical scope availability
→ exact query parameter schema
→ timezone/range resolution
→ data query if data endpoint
```

Do not leak feature/range schema before intended auth/Site gates.

---

# 86. Duplicate query-parameter handling

Add a narrow Activity path exception analogous to existing hardened current-state/current-traffic routing if required so duplicate validation occurs after intended security gates.

Do NOT weaken global Admin query handling.

After gate:

```text
duplicate parameter
→ 400 invalid_request
```

---

# 87. Canonical HTTP behavior

```text
200
valid metric result, including complete/partial

400
invalid request/range/time

401
authentication required

403
Site/capability forbidden

404
Activity feature disabled after security gates

429
Admin concurrency unavailable
Retry-After: 1

503 query_deadline
data endpoint exceeded hard query budget

503 source_unavailable
Activity source/config unavailable

500
sanitized internal error
```

A Selected 503 does not affect already accepted Today.

---

# 88. Read service architecture

Preferred:

```text
Visit Lifecycle persisted DB
        ↓
existing read-only analytics connection boundary
        ↓
HomeActivityReadService
        ↓
AdminQueryService
        ↓
Today / Selected Admin API
```

Recommended module:

```text
app/analytics/home_activity.py
```

No source ownership change.

---

# 89. Read-only contract

Activity uses:

```text
URI read-only SQLite
PRAGMA query_only=ON
schema/version validation
deadline-aware query execution
small aggregate result
```

No writes.

No migration.

No source mutation.

---

# 90. Today and Selected use independent read budgets

Today endpoint:

```text
its own AdminQueryService._run()
its own QueryDeadline
```

Selected endpoint:

```text
its own AdminQueryService._run()
its own QueryDeadline
```

No nested sharing of the same deadline.

This is the FINAL mechanism chosen to satisfy Today isolation.

---

# 91. No generic Analytics history cap reuse

Do NOT call generic Visit Analytics in a way that inherits:

```text
31-day generic max
90-day Visit max
```

Activity uses its own narrow aggregate read contract.

Do not globally widen existing Analytics configuration.

---

# 92. Authorized Visit SQL

Use existing Site/start-SSID/start-time indexes.

Set-based only.

Preferred query computes:

```text
COUNT verified qualifying Visits
integrity anomaly count
MIN/MAX persisted evidence diagnostics
```

Do not fetch every Visit into Python.

---

# 93. Traffic SQL

Use set-based terminal event selection:

```text
site_id
exact SSID scope
controller_event_at range
processing_result terminal allowlist
valid required fields
```

Then semantic fingerprint grouping.

Compute:

```text
SUM bytes once per fingerprint
counts by processing/exclusion category
MIN/MAX diagnostic evidence
```

No Python row materialization.

---

# 94. Traffic pending/invalid diagnostics

Pending/invalid events that can be attributed to requested Site/SSID/controller-time range must be counted by bounded aggregate SQL.

Do not expose rows.

If an invalid row lacks enough Site/time/SSID evidence to belong to the requested metric population:

```text
do not arbitrarily assign it to this Site/range
```

It may remain covered by broader engineering telemetry, not the per-Site product metric.

---

# 95. No N+1

Forbidden:

```text
per Visit query authorization
per event query extra state
per client query
```

Query count remains a small constant independent of row population.

---

# 96. No full-history Python materialization

Long range must still use:

```text
COUNT
SUM
MIN
MAX
GROUP BY
EXISTS / JOIN
```

inside SQLite.

Never:

```text
SELECT all history
→ loop in Python
```

---

# 97. Performance contract — no artificial range cap

The hard safety mechanism remains:

```text
bounded SQL
Admin QueryDeadline
Admin semaphore
response-size limit
```

Not:

```text
duration cap
hidden clipping
31/90-day rejection
```

---

# 98. Early query-plan gate

Before frontend polish, implementation must capture:

```text
EXPLAIN QUERY PLAN
```

for:

```text
Visit Today
Visit long Selected
Traffic terminal included query
Traffic semantic dedupe query
Traffic pending/invalid diagnostic query
coverage metadata query
```

If query plan is unexpectedly unbounded:

```text
STOP
```

---

# 99. Current-history benchmark

Measure against representative production-sized read-only copy/source for:

```text
Today
24h
7d
30d
current month
32+ days
90+ days when available
all retained history
```

Record:

```text
row counts
cold timing
warm timing
p50
p95
max
deadline failures
```

---

# 100. Long-term regression gate

One-time benchmark is NOT sufficient.

Add a repeatable performance/capacity gate for long history.

Required artifacts:

```text
deterministic synthetic long-history fixture/generator
query-plan regression assertions
capacity benchmark script
```

Benchmark must exercise at least:

```text
365 days
```

and a scalable larger-history case where practical.

Do not put flaky wall-clock microbenchmarks into ordinary correctness pytest if environment variance makes them unreliable.

---

# 101. Long-term operational performance monitoring

After production activation, Activity telemetry must make visible:

```text
Today query durations
Selected query durations
Selected range category
429 count
query_deadline count
source_unavailable count
500 count
```

Long-range deadline failures must remain observable over time as the DB grows.

---

# 102. Performance review trigger

If production shows increasing:

```text
query_deadline
or material p95 degradation for long Selected ranges
```

then:

```text
investigate query plan / DB growth
```

Do NOT automatically introduce a time-range cap.

---

# 103. Performance prerequisite rule

If full retained history cannot stay within the existing hard deadline:

```text
STOP
```

Prepare smallest separate prerequisite:

```text
index
or
bounded rollup
```

with explicit schema/retention/rebuild semantics.

Do not hide that change inside UI work.

Do not silently reduce selectable history.

---

# 104. Activity refresh policy — source-aware

The panel does NOT blindly refresh every Selected range every 60 seconds.

Today and Selected have separate refresh eligibility.

---

# 105. Today refresh

Today:

```text
auto-refreshes at Activity refresh cadence
manual Refresh
visibility return when due
Site reload/change
midnight rollover
```

Default cadence:

```text
60 seconds
```

within existing allowed bounds.

---

# 106. Rolling Selected refresh

These change continuously and may auto-refresh:

```text
Last 24 hours
Last 48 hours
Last 7 days
Last 30 days
Current month
```

Use Activity refresh policy.

Do not overlap requests.

---

# 107. Yesterday refresh

Yesterday is a completed calendar interval during the current day.

Therefore after its initial Apply/load:

```text
do NOT reread every minute
```

Refresh only on:

```text
manual Refresh
period re-Apply
Site change/reload
local midnight rollover
```

At midnight the meaning of Yesterday changes, so exactly one new Selected query is required.

---

# 108. Completed custom refresh

An absolute custom range with resolved end in the past:

```text
do NOT auto-query every 60 seconds
```

Refresh only on:

```text
Apply
manual Refresh
Site change/reload
```

Midnight rollover does NOT change its boundaries.

---

# 109. Custom range and late Traffic events

A completed custom Traffic result may change later if delayed offline evidence arrives.

v1 deliberately chooses:

```text
no automatic repeated historical polling
```

The UI shows:

```text
last updated
coverage/watermark
```

Manual Refresh rechecks it.

This prevents years-long custom ranges from being recalculated every minute.

---

# 110. Current month midnight behavior

At local midnight:

```text
Today resets
Current month remains same month unless month rollover
its end advances
```

Refresh Current month as a dynamic calendar interval.

At first day of a new month:

```text
Current month start changes
```

---

# 111. Midnight scheduler

Today endpoint returns:

```text
next_site_midnight_utc
```

Browser schedules one bounded wake-up.

Hidden tab:

```text
no background burst
```

On visibility return after rollover:

```text
one controlled Today refresh
one Selected refresh only if its calendar meaning changed
```

---

# 112. Frontend coordinator — final phases

When all sources enabled:

```text
PHASE A
  Current Client
  Current AP
  concurrent, max 2

PHASE B
  Current Traffic
  if enabled

PHASE C
  Activity Today
  if due

PHASE D
  Activity Selected
  only if due
```

Traffic and Activity data requests are not started as a new parallel burst.

---

# 113. Selected static optimization

For:

```text
Yesterday
completed custom
```

Phase D is skipped during ordinary auto-refresh.

Today still updates.

---

# 114. Picker Apply

Picker Apply is Selected-specific.

It MUST NOT trigger:

```text
Current Client refresh
Current AP refresh
Current Traffic refresh
Today refresh
```

Required:

```text
commit selection
increment selected selection_revision
abort obsolete Selected request only
queue one Selected request
```

---

# 115. Preview request behavior

Range preview:

```text
may run while picker is open
does not read historical sources
does not alter accepted Selected data
```

Debounce UI calls.

Do not issue preview on every keystroke without bound.

Recommended:

```text
after both dates syntactically valid
and input settles
```

---

# 116. Apply requires valid preview state

Recommended UI rule:

```text
custom Apply enabled only when latest preview matches current draft fields
```

This ensures user sees exact accepted timezone boundaries before applying.

If preview is unavailable:

```text
do not guess using browser timezone
```

---

# 117. Abort ownership

Activity Today and Activity Selected each own their own current AbortController state.

Rules:

```text
late finally cannot clear newer controller
superseded Selected abort is neutral
hidden/pagehide abort is neutral
```

No cross-abort of unrelated Current State/Traffic.

---

# 118. Selection revision

Selected source captures:

```text
Site
period
custom draft identity
selection_revision
request generation
```

Old response:

```text
cannot overwrite newer selection
```

---

# 119. Apply during active Home cycle

If another Home phase is active:

```text
store one pending Selected refresh
```

When coordinator becomes idle:

```text
run newest selection only
```

Do not cancel unrelated Current State/Traffic merely because picker changed.

---

# 120. Manual Refresh

Single existing Home Refresh remains.

Manual Refresh requests:

```text
Current State
Current Traffic if enabled
Today
Selected regardless of static/dynamic classification
```

still through bounded coordinator.

---

# 121. Retry/backoff

Today and Selected have independent failure state.

Use existing Home bounded pattern.

Recommended:

```text
60s
120s
300s
```

with:

```text
max(refresh interval, backoff, Retry-After)
```

429 jitter remains bounded.

---

# 122. Static Selected failure retry

For completed custom/Yesterday:

```text
do not create an automatic every-minute error loop
```

After request failure:

```text
show failure
retry only manual Refresh / re-Apply / Site change / midnight if Yesterday identity changes
```

This is stricter than rolling auto-retry.

---

# 123. Rolling Selected failure retry

Rolling/current-month ranges may use bounded automatic retry/backoff.

No overlap.

---

# 124. Hidden tab

When hidden:

```text
no Today polling
no Selected polling
outstanding Activity fetches abort neutral
```

On visible:

```text
refresh only sources actually due
```

No catch-up burst.

---

# 125. Pagehide

Activity:

```text
abort owned requests
clear timers
clear pending operations
```

No persistent browser state.

---

# 126. Browser persistence

Do not use:

```text
localStorage
sessionStorage
IndexedDB
service worker cache
```

v1 fresh page default:

```text
Last 24 hours
```

---

# 127. Activity UI state isolation

Maintain independent UI state:

```text
today
selected
```

Each contains independent:

```text
loading
accepted result
last updated
failure
```

Selected failure does not clear Today.

Today failure does not erase a still-valid completed Selected result.

---

# 128. Metric state isolation inside each side

Within Today/Selected:

```text
Authorized visits
Traffic
```

remain independently representable.

Example:

```text
Authorized visits complete
Traffic partial
```

Do not collapse whole side into one generic error when one metric is partial.

---

# 129. Loading

First load:

```text
Today Loading…
Selected Loading…
```

Custom Apply:

```text
Today remains
Selected Loading…
```

No unrelated Home blanking.

---

# 130. Partial

Visible subtotal remains.

Examples:

```text
Authorized visits 12 · Partial

Traffic 4.7 GB · Partial · Estimated
```

Coverage/helper explains why.

---

# 131. Unavailable

Visible:

```text
Authorized visits —
Unavailable

Traffic —
Unavailable · Estimated
```

Estimated helper remains visible even when Traffic is unavailable.

---

# 132. Zero

Required exact rendering:

```text
0
0 B
```

No truthiness bug converting zero to dash.

Coverage status still displayed.

---

# 133. Range coverage UI

For partial coverage, show concise message:

```text
Coverage: from 19 Aug 2026
```

or:

```text
Coverage through 11:19:55
```

or:

```text
Coverage start unknown
```

No raw UTC required in primary label, but exact details may show both local and UTC.

---

# 134. Frontend strict validation

A data response is accepted only if:

```text
api_version correct
Site correct
evaluated_at canonical
timezone present
range requested/resolved valid
from < to
metric statuses allowlisted
quality reasons allowlisted
all counts non-negative integers
booleans are not accepted as integers
Traffic estimated === true
coverage fields internally consistent
```

Malformed 200:

```text
Activity source unexpected
do not partially trust malformed payload
```

Unrelated Home sources remain intact.

---

# 135. Safe DOM

Dynamic API values use:

```text
textContent
createElement
safe attributes
```

No unsafe HTML injection.

No new frontend library.

---

# 136. Traffic formatting

Binary units:

```text
1024
```

Recommended:

```text
B integer
larger units max one decimal
```

Examples:

```text
0 B
842 B
12.4 KB
836 MB
4.8 GB
1.2 TB
```

Do not imply false precision.

---

# 137. Admin feature flag

Add:

```text
WEB_ADMIN_HOME_ACTIVITY_ENABLED=false
```

Repository-safe default:

```text
false
```

Dependency:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_HOME_LIVE_ENABLED=true
Current State canonical scope available
```

It does NOT require Home Traffic enabled.

---

# 138. Activity-specific config

Recommended:

```text
WEB_ADMIN_HOME_ACTIVITY_ENABLED

WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS

WEB_ADMIN_HOME_ACTIVITY_REQUEST_TIMEOUT_SECONDS

WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON

WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_FRESH_MAX_AGE_SECONDS

WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_STALE_MAX_AGE_SECONDS
```

No history-duration max.

No guest-SSID field.

---

# 139. Config isolation

Prefer separate Activity config parser/module so malformed Activity-only settings do not take down core Admin.

Example:

```text
app/admin_web/home_activity_config.py
```

Failure:

```text
Activity unavailable
Admin active
```

---

# 140. Canonical scope startup check

At Activity construction/startup verify:

```text
each Activity Site exists in Admin allowlist
each Activity Site exists in Current State Site config
canonical Current State guest SSID scope is available
Activity does not provide another SSID scope
```

Mismatch:

```text
Activity unavailable for Site
telemetry reason=scope_mismatch
```

Required acceptance test.

---

# 141. Current Traffic consistency rule

Because Current Traffic is AP-wide, startup validation does NOT try to force its source into the guest SSID scope.

Instead ensure visible semantics remain distinct:

```text
Traffic Now
→ AP traffic, may include local/non-guest

Activity Traffic
→ canonical guest SSID completed-session estimate
```

No silent equivalence.

---

# 142. Public serializer

Use explicit allowlist.

Never generic serialize source rows.

No public fields:

```text
client_mac
visit_id
event_id
auth_session_id
IP
AP MAC
raw SSID event text
DB path
source file path
raw processing reason
```

---

# 143. Route telemetry

Add safe bounded events such as:

```text
admin.home_activity_today_query_completed

admin.home_activity_selected_query_completed

admin.home_activity_range_preview_completed
```

Safe fields:

```text
request_id
Site
status_code
outcome
reason enum
duration_ms
period enum
visit status
traffic status
coverage status
range duration category
```

Do not log raw custom dates/times if unnecessary.

Never log query string/full URL.

---

# 144. Selected duration category telemetry

Allowed coarse categories:

```text
<=1d
>1d<=7d
>7d<=31d
>31d<=90d
>90d<=365d
>365d
```

This is telemetry categorization only.

It is NOT an input limit.

---

# 145. No Loki/Grafana product dependency

Activity product backend does not read:

```text
Grafana
Loki
auth telemetry logs
```

They may be used manually for engineering reconciliation only.

---

# 146. No Omada path

Activity implementation must not import/use:

```text
OmadaProvider
OpenAPI request client
Omada token lifecycle
controller HTTP
```

Required test/spies prove zero Omada calls.

---

# 147. No source schema change by default

Expected implementation needs:

```text
read service
Admin routes/query service
config
frontend
tests
```

No Visit schema migration is currently authorized.

If performance proves an index/rollup is required:

```text
STOP
separate prerequisite
```

---

# 148. Expected implementation files

Likely:

```text
app/analytics/home_activity.py
app/analytics/models.py
app/analytics/source_gateway.py
app/analytics/runtime.py
app/analytics/__init__.py

app/admin_web/home_activity_config.py
app/admin_web/home_activity_serialization.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/runtime.py
app/admin_web/pages.py
app/admin_web/templates/admin/home.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css

app/config.py
app/settings.py
.env.example

tests/analytics/test_home_activity*.py
tests/admin_web/test_home_activity*.py
tests/admin_web/test_home_activity_frontend.py
```

Exact file split may vary narrowly.

---

# 149. Forbidden broad changes

Do not modify semantics of:

```text
Visit writer/finalizer
Visit schema
Observation workers
Current State workers
Current Traffic formula
Public Traffic writer
Omada provider
Auth/CAPPORT
Pending Cleaner
Registry writes
Grafana/Loki
Nginx
systemd
network devices
```

No new dependency unless separately approved.

---

# 150. Backend tests — calendar ranges

Mandatory:

```text
date-only From/To accepted

date-only To is user-inclusive

technical To becomes next local midnight

same From/To date with no time = full calendar day

From date+time / To date only

From date only / To date+time

both explicit times

from inclusive
to exclusive

future rejected

reverse rejected

nonexistent DST time rejected

ambiguous DST time rejected

browser timezone never defines resolved UTC

preview boundaries equal applied server semantics
```

---

# 151. Backend tests — presets

Mandatory:

```text
Today local midnight

Today != Last 24h

Last 24h rolling

Yesterday completed local calendar day

Last 48h rolling

Last 7d rolling

Current month

Last 30d rolling

timezone offset transitions
```

---

# 152. Backend tests — coverage

Mandatory:

```text
request before proven Visit coverage start
→ partial, not 0 complete

request before proven Traffic coverage start
→ partial, not 0 complete

Visits and Traffic have different coverage_from

Traffic coverage_through from reader heartbeat

requested end beyond Traffic coverage_through
→ partial

unknown coverage_from
→ partial/unknown

full proven range with zero
→ 0 complete

partial range with zero
→ 0 partial

no silent clipping

earliest persisted row does not become automatic coverage_from
```

---

# 153. Backend tests — long range

Mandatory:

```text
32-day custom accepted

90-day custom accepted

365+ day custom accepted when represented by fixture/source

no generic Analytics max-window rejection

long Selected remains deadline-aware

long query uses aggregate SQL

no full Python materialization
```

---

# 154. Backend tests — Authorized visits

Mandatory:

```text
new Visit-opening success = one

duplicate auth run = one

multiple auth rows same Visit = one

pending/failed/no Visit excluded

from boundary included

to boundary excluded

cross-midnight by started_at

open Visit counts

later closure does not move count

new Visit after closure counts

Site isolation

canonical SSID scope

case-sensitive SSID scope

opening evidence anomaly partial

out-of-order evidence no cohort rewrite
```

---

# 155. Backend tests — Traffic processing_result

Mandatory test every branch:

```text
closed valid → included

unmatched valid → included

pending_match → excluded + pending count + partial

invalid attributable → excluded + invalid count + partial

unknown future → unavailable/fail closed
```

No untested branch.

---

# 156. Backend tests — Traffic confidence

Mandatory:

```text
valid bytes conversion matches persisted byte contract

null traffic excluded + partial

zero traffic included as 0

missing controller time excluded + partial

received_at-only number not included

event not included merely because traffic number exists
```

---

# 157. Backend tests — Traffic replay

Mandatory:

```text
same event_id replay
→ no double count

different event_id with identical full semantic fingerprint
→ one contribution

semantic duplicate count increments

different legitimate session fingerprint
→ separate contribution

no fuzzy MAC/time-window collapse
```

---

# 158. Backend tests — scope mismatch

Mandatory:

```text
Activity enabled
Current State canonical scope unavailable
→ Activity unavailable

Activity Site absent from Current State Site set
→ Activity unavailable

no alternate Activity SSID config accepted
```

---

# 159. API tests — Today isolation

Mandatory scenario:

```text
Today endpoint succeeds

Selected long endpoint hits query deadline

UI/state keeps correct Today value

Selected becomes unavailable/error state
```

This is a release-blocking test.

---

# 160. API/security tests

Mandatory:

```text
401 unauthenticated
400 invalid Site syntax
403 forbidden Site
403 capability denied
404 feature disabled after security gates
503 Activity Site context/source unavailable
429 shared query slot busy + Retry-After
503 query_deadline
503 source_unavailable
response-size cap
unknown params 400
duplicate params 400
DTO allowlist
no identities
GET read-only
no Omada
```

---

# 161. Preview API tests

Mandatory:

```text
auth/Site/capability gates

no DB/source data read

date-only inclusive To preview

timezone shown

UTC shown

DST ambiguous rejected

DST nonexistent rejected

invalid format rejected

duplicate params rejected
```

---

# 162. Frontend real-Node gate

Node remains mandatory for Home frontend contract.

Do not skip because Node is absent.

Environment without Node:

```text
frontend gate fails
```

consistent with current Home Traffic testing convention.

---

# 163. Node tests — picker

Mandatory:

```text
default Last 24h

quick ranges

custom date-only

optional times

preview before Apply

Apply disabled while preview stale/invalid

Cancel keeps old Selected

Escape closes without applying

focus enters picker

focus returns to opener

ambiguous/nonexistent server error visible

no browser-timezone authoritative conversion
```

---

# 164. Node tests — refresh eligibility

Mandatory:

```text
Today auto refreshes

Last 24h auto refreshes

Last 48h auto refreshes

Last 7d auto refreshes

Last 30d auto refreshes

Current month auto refreshes

Yesterday does NOT poll every minute

completed custom does NOT poll every minute

Yesterday refreshes once at local midnight

completed custom remains unchanged at midnight

manual Refresh rereads static Selected

Site change/reload rereads
```

---

# 165. Node tests — endpoint isolation

Mandatory:

```text
Today response accepted before Selected request

Selected 503 leaves Today

Selected 429 leaves Today

Selected network failure leaves Today

Today failure leaves previous valid Selected

Activity failure leaves Current State

Activity failure leaves Current Traffic
```

---

# 166. Node tests — coordinator

Mandatory:

```text
Phase A max concurrency remains 2

Current Traffic remains sequential phase

Today separate phase

Selected only when due

static Selected skipped on ordinary refresh

picker Apply only requests Selected

Apply during busy cycle queues one newest Selected request

no overlap

old selection response discarded

neutral abort behavior

hidden-tab behavior

pagehide cleanup
```

---

# 167. Node tests — Traffic presentation

Mandatory:

```text
4.8 GB shows Estimated

0 B shows Estimated

partial shows Estimated

unavailable shows Estimated

persistent helper text remains visible

helper states active sessions delayed until offline

helper states end-time attribution

helper states not WAN/Internet/billing
```

---

# 168. Existing Home regression scope

Because coordinator/template/JS changes, targeted regression includes:

```text
Current Client summary/page
Current AP summary/page
Traffic Now summary
Traffic by AP
Traffic AP-page 403 preservation
manual Refresh
hidden tab
pagehide
```

Feature combinations:

```text
Live only

Live + Current Traffic

Live + Activity

Live + Current Traffic + Activity
```

---

# 169. Performance regression artifacts

Implementation must add/retain:

```text
EXPLAIN plan evidence
long-history capacity fixture/script
documented production benchmark results in handoff
```

Future Reviewer/Tech Lead can rerun after meaningful DB growth.

---

# 170. Production deadline monitoring acceptance

After activation observe Activity route telemetry.

Record:

```text
Today 200 count
Today p50/p95/max

Selected 200 count
Selected p50/p95/max by duration category

429 count
query_deadline count
source_unavailable count
500 count
```

A rising long-range deadline rate is a performance issue, not a reason to silently cap period length.

---

# 171. Coder testing responsibility

Coder runs:

```text
targeted tests for changed modules
related Home regression tests
real Node frontend gate
compile/static checks
git diff --check
```

Coder is NOT assigned the full repository suite by default.

---

# 172. Full repository suite

Per current project policy:

```text
Reviewer / Tech Lead / Owner
```

runs full repository gate:

```text
on exact accepted artifact
immediately before deployment / activation
```

This responsibility remains unchanged.

---

# 173. Coder PLAN before edits

After explicit implementation authorization, Coder must first return PLAN with:

```text
exact main SHA

canonical Current State SSID scope integration

Activity Site timezone/coverage config

range-preview resolver

date-only inclusive-end semantics

DST reject semantics

Today endpoint

Selected endpoint

independent deadlines

Visit aggregate SQL

Traffic processing_result table implementation

semantic replay SQL

coverage SQL/metadata

EXPLAIN plan

long-history benchmark

coordinator refresh eligibility

static Selected no-poll rule

targeted tests

Node gate

no Omada proof
```

No code before PLAN acceptance if Owner workflow requires it.

---

# 174. Early implementation STOP gate

Before final frontend styling:

```text
prove range resolver
prove canonical scope
prove Visit query plan
prove Traffic query plan
prove semantic dedupe query plan
prove long-range bounded behavior
```

If any requires new schema/index:

```text
STOP
return prerequisite
```

---

# 175. Source coverage activation requirement

Production Activity activation must explicitly record for each Site:

```text
timezone

visits_coverage_from_utc
or null with known limitation

traffic_coverage_from_utc
or null with known limitation
```

Do not invent coverage start from first row.

---

# 176. Production reconciliation — Visits

Compare for:

```text
Today
Last 24h
one long range
```

against direct safe aggregate from same persisted Visit source.

Do NOT validate only against AuthSession/Grafana counters.

---

# 177. Production reconciliation — Traffic

Compare:

```text
HomeActivityReadService
Admin Selected/Today API
```

same Site/scope/range.

Additionally use Public Traffic only as compatible calendar-day sanity check where semantics/history overlap.

Do not force equality across different source contracts.

---

# 178. Production calendar acceptance

Required browser/API acceptance:

```text
date-only From/To

inclusive To day

same-day full-day custom

custom with From time

custom with To time

Last 24h

Yesterday

Last 7d

Current month

32+ day custom

90+ day custom if history exists

365+ day custom if history exists
```

---

# 179. Production coverage acceptance

Demonstrate at least:

```text
range fully after proven coverage start
→ complete when through covered

range beginning before proven coverage
→ partial

Visits/Traffic different coverage starts
→ different metric coverage output

Traffic through reader watermark
→ correct partial/current behavior
```

---

# 180. Production Selected deadline acceptance

Use a safe test/fixture/range capable of exercising Selected failure without harming service.

Verify:

```text
Today remains correct
Current State remains correct
Current Traffic remains correct
Selected shows bounded failure
no request storm
```

---

# 181. Production static-range polling acceptance

With Yesterday selected:

```text
observe no minute-by-minute Selected requests
```

With completed custom selected:

```text
observe no minute-by-minute Selected requests
```

Today continues refreshing.

---

# 182. Two-tab gate

Two visible Home tabs:

```text
no uncontrolled burst
no overlapping Activity loop
query slot contention bounded
429 recoverable
static ranges do not create excess reads
```

---

# 183. Fast rollback

Rollback only Activity:

```text
WEB_ADMIN_HOME_ACTIVITY_ENABLED=false
restart under Owner-controlled procedure
```

Do NOT disable:

```text
Admin
Home Live
Current Traffic
Visit Lifecycle
Observation
Analytics
Public Traffic
```

No DB deletion.

---

# 184. Open-browser rollback

After Activity disabled, an already-open browser may receive Activity 404.

Behavior:

```text
stop Activity polling
clear/hide Activity current state
leave Current State running
leave Current Traffic running
```

Reload:

```text
Activity panel absent
```

---

# 185. Product / observability boundary

Home product displays:

```text
period
timezone
Authorized visits
Traffic · Estimated
coverage status
data through/start note
last updated
```

Engineering telemetry may contain:

```text
query duration
deadline category
row counts
reader freshness
```

Do not surface raw SQL/internal paths in UI.

---

# 186. Future Multi-Site contract

Mandatory:

```text
every request Site-scoped

timezone per Site

canonical guest scope provided by Site-aware/current-state scope provider

no MAC-based Site inference

no cross-Site aggregate

Tenant != Site
```

When Current State evolves to per-Site SSID scope, Activity must consume that provider rather than freeze the current global implementation shape.

---

# 187. Accepted v1 limitations

Intentional:

```text
Traffic estimated

completed sessions only

controller-event end-time attribution

active sessions absent until offline

combined Traffic only

not WAN/Internet/billing

no interval byte splitting

no Traffic chart

no per-AP Traffic history

no per-client Traffic history

no automatic polling of completed long custom periods
```

---

# 188. Future Traffic page boundary

A later dedicated Traffic page may add:

```text
time series
AP/client breakdown
SSID breakdown
source reconciliation
late-event revision indicators
different traffic authorities
interval-clipped model if a new source supports it
```

Not part of this Home task.

---

# 189. Final resolved Tech Lead review items

All requested review corrections are incorporated:

```text
1. Date-only custom range + optional time
   → RESOLVED

2. Inclusive user To date converted to next local midnight
   → RESOLVED

3. Exact pre-Apply timezone/boundary preview
   → RESOLVED

4. Ambiguous DST not silently folded
   → RESOLVED by rejection

5. Stored rows separated from proven coverage
   → RESOLVED

6. Separate Visits and Traffic coverage boundaries
   → RESOLVED

7. No artificial 31/90-day cap
   → PRESERVED

8. Long-term performance regression/monitoring
   → ADDED

9. Combined endpoint vs Today isolation contradiction
   → RESOLVED by separate Today and Selected endpoints

10. SSID competing source of truth
    → REMOVED; Activity reuses Current State canonical scope

11. Traffic processing_result behavior
    → EXPLICIT TABLE

12. Replay / semantic duplicate behavior
    → EXPLICIT

13. Static historical polling
    → DISABLED except Apply/manual/Site/calendar rollover as applicable

14. Estimated visibility
    → ALWAYS VISIBLE

15. Requested/resolved/coverage DTO separation
    → ADDED

16. Acceptance tests
    → ADDED
```

---

# 190. Blocking Owner decisions

```text
NONE
```

No unresolved Owner product decision remains for this panel.

Implementation may proceed only after separate explicit Owner authorization.

---

# 191. Final architecture

```text
Current State canonical guest scope
            +
Activity Site timezone / proven coverage metadata
            ↓
Visit Lifecycle persisted facts
   ├─ Visit-opening authorization facts
   └─ terminal offline traffic evidence
            ↓
HomeActivityReadService
            ↓
AdminQueryService
            ↓
Today endpoint
Selected endpoint
Range Preview endpoint
            ↓
existing bounded Home coordinator
            ↓
Visits and Traffic panel
```

---

# 192. Final invariants

The implementation MUST add:

```text
no Omada request
no second guest-SSID truth
no AuthSession counting
no source DB
no source schema by default
no 31/90-day range cap
no hidden clipping
no browser-timezone authority
no silent DST fold
no minute polling of completed long ranges
no false complete zero before proven collection
no Selected failure that clears Today
no Traffic value without Estimated
```

---

# 193. Final status

```text
TASK:
TASK-HOME-ACTIVITY-01

SPECIFICATION:
FINAL

TECH LEAD REVIEW COMMENTS:
INCORPORATED

BLOCKING OWNER DECISIONS:
NONE

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED BY THIS DOCUMENT

NEXT STEP:
Owner explicitly authorizes implementation / Coder PLAN
```
