# TASK-HOME-TRAFFIC-READ-01 — Current Traffic Read Foundation — FINAL

**Project:** CaptivPortal  
**Parent:** `TASK-HOME-TRAFFIC-MASTER — FINAL`  
**Type:** executable backend/read-foundation specification  
**Status:** `FINAL — TECH LEAD REVIEW INCORPORATED`  
**Implementation authorization:** `NOT GRANTED — requires separate Owner authorization`  
**Branch / code / commit / push / PR:** `NOT AUTHORIZED`  
**Production activation:** `NOT APPLICABLE — read foundation is merged/deployed only as dependency; product flag remains off`  
**Exact implementation baseline:** `origin/main@dafbc40b6f5c5b3dde6b52fcc2c7689e95d05081`  
**Prepared:** 2026-08-24

---

## 1. Goal

Create a Site-aware, bounded, read-only `CurrentTrafficReadService` over already persisted Observation AP facts.

```text
observations.sqlite3
→ CurrentTrafficReadService
→ later AdminQueryService
```

No UI/API Home Traffic is implemented in this task.

---

## 2. Permanent boundaries

Forbidden:

```text
new Omada request
new collector
Observation worker change
rate formula change
Observation schema migration
new business DB
Loki/Grafana query
Current State reconstruction
Visit/Registry reconstruction
```

The service reads persisted Observation facts only.

---

## 3. Preferred package

```text
app/analytics/current_traffic.py
app/analytics/models.py
app/analytics/source_gateway.py
app/analytics/runtime.py
app/analytics/__init__.py
```

Preferred runtime exposure:

```text
AnalyticsRuntime.current_traffic_service
```

Use existing Observation read-only connection boundary and existing `QueryDeadline`.

No loopback HTTP to Analytics API.

---

## 4. Canonical cycle selection

Filter:

```sql
WHERE site_id = ?
  AND kind = 'ap_dynamic'
  AND state = 'completed'
  AND complete = 1
  AND result = 'success'
ORDER BY started_at DESC, cycle_id DESC
LIMIT 1
```

This exact ordering is the v1 contract.

Do not use independent latest-per-AP rows.

---

## 5. Read transaction

For one summary request, perform in one read-only SQLite snapshot transaction:

```text
canonical cycle selection
latest-attempt selection
cycle integrity validation
AP row integrity validation
strict rate/reason/timestamp validation
source-family coverage computation
source selection
Site aggregation
freshness/skew computation
reason counters
```

Read-only requirements:

```text
URI mode=ro
PRAGMA query_only=ON
existing schema version check
existing QueryDeadline/progress interruption
```

No mutation.

---

## 6. Canonical cycle integrity

Required:

```text
finished_at != null
finished_at >= started_at

items_seen = items_stored
items_skipped = 0
error_count = 0
data_quality_warning_count = 0

stored AP row count = items_stored
source_rows_reported = items_seen
```

Every selected AP row:

```text
site_id = requested Site
cycle_id = selected cycle
AP MAC canonical
AP MAC unique
partial = 0
overview_ok = 1
wired_uplink_ok = 1
lan_traffic_ok = 1
radios_ok = 1
```

Contradiction:

```text
CurrentTrafficSourceUnavailable
→ later Admin maps to 503 source_unavailable
```

Not product partial coverage.

---

## 7. Accepted source families

```text
wired
LAN
```

Mappings:

```text
wired Download = wired_download_mbps
wired Upload   = wired_upload_mbps
wired timestamp = wired_observed_at

LAN Download = lan_rx_mbps
LAN Upload   = lan_tx_mbps
LAN timestamp = lan_observed_at
```

Radio excluded.

---

## 8. Strict rate matrix

Allowed reasons exactly:

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

For each wired/LAN direction:

```text
reason=ok
→ rate is finite numeric
→ rate >= 0
→ section timestamp valid

reason!=ok
→ rate is null
```

Integrity failure:

```text
reason=ok + null rate
reason=ok + negative rate
reason=ok + NaN/Inf
reason!=ok + numeric rate
null/unknown reason
reason=ok + missing/invalid section timestamp
```

Boolean is not numeric.

---

## 9. Temporal integrity

For every required section timestamp:

```text
cycle.started_at
<= section timestamp
<= cycle.finished_at
<= evaluated_at
```

Any violation/negative age:

```text
snapshot freshness=unavailable
freshness_reason=clock_anomaly
```

If the persisted row otherwise contradicts the complete-success rate matrix, treat it as integrity failure rather than silently dropping it.

No hidden clock tolerance.

---

## 10. Empty population

First source-selection branch:

```text
if total_ap_count == 0:
    selected_source = wired
    selection_reason = empty_population
```

Return:

```text
empty_population=true
coverage=complete
download=0.0
upload=0.0
total=0.0
observed_at=cycle.finished_at
newest_observed_at=cycle.finished_at
source_skew_seconds=0
```

---

## 11. No canonical cycle

Return a source-quality result, not an exception:

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

This later serializes as HTTP 200.

DB/schema/integrity failure is different and raises source unavailable.

---

## 12. Pair validity

For non-empty population a source-family AP pair is valid only if:

```text
Download reason=ok
Upload reason=ok
both values finite non-negative numeric
section timestamp valid under temporal contract
```

Calculate:

```text
wired_pair_valid_ap_count
lan_pair_valid_ap_count
```

---

## 13. Source selection

Non-empty algorithm:

```text
if wired_pair_valid == total_ap_count:
    wired / primary_full_coverage

elif lan_pair_valid == total_ap_count:
    LAN / fallback_full_coverage

elif lan_pair_valid > wired_pair_valid:
    LAN / fallback_higher_coverage

else:
    wired / primary_preferred_tie_or_higher
```

One selected source for all APs.

No blending.

---

## 14. Direction aggregation

For selected source:

```text
download_mbps = SUM(valid Download values)
                if valid_download_ap_count > 0
                else null

upload_mbps = SUM(valid Upload values)
              if valid_upload_ap_count > 0
              else null

total_mbps = download + upload
             only if both non-null
             else null
```

Missing direction never becomes zero.

Exact `0.0 + reason=ok` remains a valid zero.

---

## 15. Coverage counters

Return:

```text
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

`valid_rate_ap_count` means both directions valid.

```text
missing_rate_ap_count = total_ap_count - valid_rate_ap_count
```

Reason counters are non-exclusive by AP, but one AP is counted at most once in each category.

---

## 16. Coverage status

```text
complete
partial
none
```

`complete`:

```text
empty population
OR
valid_rate_ap_count == total_ap_count
AND source skew within policy
```

`partial`:

```text
at least one direction subtotal numeric
AND not complete
```

`none`:

```text
non-empty population
AND download subtotal null
AND upload subtotal null
```

Coverage reasons allowlist:

```text
missing_direction
missing_pair
temporal_skew
no_valid_rate
empty_population
```

---

## 17. Freshness and skew inputs

The read service accepts policy values from the caller/configured service:

```text
fresh_max_age_seconds
stale_max_age_seconds
max_ap_skew_seconds
```

For selected source/non-empty population:

```text
observed_at = oldest selected-section AP timestamp
newest_observed_at = newest selected-section AP timestamp
source_skew_seconds = newest - oldest
```

Per AP classify:

```text
fresh
stale
unavailable
```

and count stale/unavailable APs.

Aggregate:

```text
age < 0 → unavailable / clock_anomaly
age <= fresh max → fresh / within_freshness_window
age <= stale max → stale / within_stale_window
age > stale max → unavailable / age_exceeded
```

If aggregate unavailable:

```text
download/upload/total = null
```

Coverage data remains inspectable.

---

## 18. Latest attempt metadata

Select the latest AP dynamic attempt for the same Site using:

```sql
WHERE site_id = ?
  AND kind = 'ap_dynamic'
ORDER BY started_at DESC, cycle_id DESC
LIMIT 1
```

Return:

```text
latest_attempt_state
latest_attempt_result
latest_attempt_at
using_previous_complete_snapshot
```

State allowlist:

```text
none
running
completed
abandoned
```

Result allowlist:

```text
null
success
partial
failed
shutdown
```

`latest_attempt_at`:

```text
finished_at when non-null
else started_at
```

`using_previous_complete_snapshot=true` when a newer attempt than the selected canonical cycle exists and is not the same canonical successful cycle.

Do not expose raw failure category.

---

## 19. Immutable service contract

Conceptual:

```python
get_current_site_traffic(
    site_id,
    *,
    evaluated_at_utc=None,
    fresh_max_age_seconds,
    stale_max_age_seconds,
    max_ap_skew_seconds,
    deadline=None,
) -> CurrentSiteTraffic

list_current_ap_traffic(
    site_id,
    *,
    cycle_id,
    selected_source,
    evaluated_at_utc=None,
    fresh_max_age_seconds,
    stale_max_age_seconds,
    limit=100,
    cursor=None,
    deadline=None,
) -> CurrentApTrafficPage
```

Page requires explicit `cycle_id` and `selected_source`; it does not silently select a new cycle when called as a pinned detail page.

---

## 20. AP page pinned-cycle validity

Explicit cycle is allowed when it is still retained and satisfies the same canonical complete-success integrity contract for that Site, even if it is no longer the newest canonical cycle.

Deleted/expired/not-valid cycle:

```text
CurrentTrafficValidationError
```

Cross-Site use is rejected.

---

## 21. AP page ordering

Stable v1 keyset ordering:

```text
canonical AP MAC ASC
```

No traffic sort/filter in v1.

---

## 22. Cursor contract

Cursor binds:

```text
version
kind=current_traffic_aps
site_id
cycle_id
selected_source
last_ap_mac
```

Requirements:

```text
opaque base64url payload
bounded length
strict type/key set
canonical AP MAC
canonical decode
canonical re-encode equals submitted token
```

Reject:

```text
cursor without cycle
cross-Site
cycle mismatch
source mismatch
malformed
non-canonical encoding
overlong
```

---

## 23. AP item model

Immutable item fields:

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

`rate_status`:

```text
valid      both directions valid
partial    exactly one direction valid
unavailable neither direction valid
```

If item age exceeds stale maximum or is negative:

```text
rate numeric values become null
rate_status=unavailable
```

---

## 24. Full AP page model

Return an immutable page object containing:

```text
snapshot
freshness_policy
source_selection
items
page.limit
page.next_cursor
page.cycle_id
page.selected_source
```

Snapshot identity must match the requested pinned cycle and selected source.

---

## 25. No N+1

Summary query count is constant with AP count.

Forbidden:

```text
for each AP → get_latest_ap_observation()
```

Use set-based SQL in one snapshot transaction.

AP page query count is constant per page, not per AP row.

---

## 26. Query plan / performance gate

Before acceptance record for representative read-only production-scale data:

```text
EXPLAIN QUERY PLAN
row counts
p50
p95
max
```

Queries:

```text
summary
AP page 100
AP page 250
```

If current indexes are insufficient:

```text
STOP
return plan + timings
separate index/storage amendment required
```

No index is silently added in this task.

---

## 27. Error classes

Caller/input errors:

```text
CurrentTrafficValidationError
```

Source/storage/schema/integrity errors:

```text
CurrentTrafficSourceUnavailable
```

Deadline:

```text
existing AnalyticsQueryDeadlineExceeded
```

No raw SQL/SQLite/path in public error messages.

---

## 28. Tests — canonical cycle

Mandatory:

```text
exact started_at DESC, cycle_id DESC ordering
newer partial ignored
newer failed ignored
newer shutdown ignored
newer running does not replace canonical
cross-Site excluded
```

---

## 29. Tests — integrity

Mandatory contradictions:

```text
finished_at null
finished before started
items_seen != items_stored
items_skipped != 0
error_count != 0
quality warning != 0
stored row count mismatch
source_rows_reported mismatch
row Site mismatch
row cycle mismatch
noncanonical/duplicate AP MAC
partial=1
any *_ok != 1
```

All source unavailable.

---

## 30. Tests — rate matrix

Mandatory:

```text
ok + finite zero
ok + positive
ok + null
ok + negative
ok + NaN/Inf
non-ok + null
non-ok + numeric
unknown/null reason
ok + missing timestamp
```

Only valid combinations accepted.

---

## 31. Tests — no-cycle / empty-cycle

Mandatory exact model assertions for both states, including:

```text
selected_source null vs wired
selection_reason no_complete_snapshot vs empty_population
traffic null vs 0.0
coverage none vs complete
empty_population false vs true
```

---

## 32. Tests — source selection

Mandatory:

```text
wired full/LAN full → wired
wired full/LAN partial → wired
wired partial/LAN full → LAN
wired lower pair coverage → LAN
coverage tie → wired
zero-valid non-empty tie → wired + none
```

No per-AP blending.

---

## 33. Tests — direction partials

Mandatory:

```text
Download X/Y, Upload Y/Y, Both X/Y
Download none, Upload some → total null
Upload none, Download some → total null
partial numeric subtotal
none
```

Missing direction is never zero.

---

## 34. Tests — temporal

Mandatory:

```text
section before cycle start
section after finish
finish after evaluated_at
negative age
fresh boundary
stale boundary
unavailable boundary
source skew boundary
NULL timestamp cannot be hidden by MIN/MAX
```

---

## 35. Tests — latest attempt

Mandatory:

```text
no attempt
same successful canonical attempt
newer running attempt
newer partial completed attempt
newer failed attempt
newer abandoned attempt
using_previous_complete_snapshot exact semantics
```

---

## 36. Tests — cursor/page

Mandatory:

```text
first/next page
cursor without cycle
cross-Site
cycle mismatch
source mismatch
noncanonical base64url encoding
malformed
overlong
retained old complete-success cycle allowed
expired/deleted cycle rejected
```

---

## 37. Read-only gate

Prove before/after:

```text
Observation row counts unchanged
PRAGMA user_version unchanged
no INSERT/UPDATE/DELETE
no migration
```

No new Omada/provider calls.

---

## 38. Targeted tests

Minimum:

```bash
python -m pytest -q \
  tests/analytics/test_current_traffic*.py \
  tests/analytics \
  tests/observations \
  --tb=short
```

Then full Linux gate:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
git diff --check
git status --short
```

Record exact counts.

---

## 39. Pre-change gate

Before authorized work:

```bash
git fetch origin
git rev-parse origin/main
git status --short
```

Required exact baseline:

```text
dafbc40b6f5c5b3dde6b52fcc2c7689e95d05081
```

If it differs:

```text
STOP
return new main SHA
Architect rebind required
```

Do not implement against a floating baseline.

---

## 40. Expected files

Preferred:

```text
app/analytics/current_traffic.py
app/analytics/models.py
app/analytics/source_gateway.py
app/analytics/runtime.py
app/analytics/__init__.py

tests/analytics/test_current_traffic*.py
```

If an `app/observations/**` change is believed necessary:

```text
STOP
return exact gap
```

No broad refactor.

---

## 41. Handoff after PR A implementation

Coder/Tech Lead handoff must include:

```text
branch
commit SHA
full diff summary
targeted tests
full tests
compileall
diff --check
query-plan evidence
performance evidence
read-only proof
no-Omada proof
```

After merge, record the **actual merge SHA**. That exact SHA becomes the only allowed baseline for `TASK-HOME-TRAFFIC-01-FINAL`.

---

## 42. Authorization state

```text
SPECIFICATION: FINAL
IMPLEMENTATION: NOT AUTHORIZED
BRANCH: NOT AUTHORIZED
CODE: NOT AUTHORIZED
COMMIT: NOT AUTHORIZED
PUSH: NOT AUTHORIZED
PR: NOT AUTHORIZED
PRODUCTION CHANGE: NOT AUTHORIZED
```
