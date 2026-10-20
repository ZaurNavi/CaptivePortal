# TASK-ANALYTICS-01A — Read and Data Quality Foundation

**Project:** CaptivPortal  
**Parent:** `TASK-ANALYTICS-FOUNDATION-01 — REV1`  
**Status:** DRAFT — BLOCKED UNTIL OWNER APPROVAL  
**Architecture baseline:** `origin/main@fe797593fb12b9cb9f81bdb22e1c14f2d08b037e`  
**Implementation baseline:** MUST equal accepted current `origin/main` at approval; re-review if source contracts changed  
**Recommended branch:** `feature/analytics-read-quality-v1`  
**Next task:** 01B blocked until merge + acceptance 01A

---

## 1. Result

Create the read-only foundation that safely composes:

```text
Visitor Registry / Snapshot
        ↓
Visit
        ↓
Client Observation
        ↓
AP / Radio Observation
```

PR A delivers:

- `app/analytics/` foundation;
- immutable Analytics DTO/result/provenance contracts;
- Site-aware validation;
- source adapters/read orchestration;
- strict accepted-row policy;
- data-quality metrics;
- bounded cross-source query composition;
- capacity/performance report;
- no wireless quality verdicts;
- no source writes/migrations;
- no production activation.

---

## 2. Baseline gate

Before first change:

```bash
git fetch origin
git rev-parse origin/main
git status --short

python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc   python -m compileall -q app
git diff --check
```

Record:

```text
exact SHA
Python version
passed
skipped
failed
compileall
diff-check
working tree
```

If Observation/Visit/Registry/read-service code changed after `fe797593fb12b9cb9f81bdb22e1c14f2d08b037e`, stop and return impact before implementation.

---

## 3. Allowed new files

```text
app/analytics/__init__.py
app/analytics/config.py
app/analytics/models.py
app/analytics/validation.py
app/analytics/source_gateway.py
app/analytics/read_service.py
app/analytics/quality.py
app/analytics/formulas.py
app/analytics/telemetry.py

tests/analytics/**
```

Names may be minimally consolidated.

---

## 4. Narrow existing-file changes allowed

Only if current public read services cannot satisfy a required bounded read:

```text
app/observations/read_service.py
app/observations/repository.py        # read-only methods only

app/visit_lifecycle/read_service.py
app/visit_lifecycle/repository.py     # read-only methods only

app/visitor_registry/registry_read_service.py
app/visitor_registry/registry_repository.py  # read-only methods only

app/config.py
app/settings.py
.env.example
```

Rules:

```text
NO schema
NO migration
NO INSERT/UPDATE/DELETE
NO collector/finalizer behavior change
NO lifecycle change
```

Any source repository method added by 01A must use a read-only connection.

---

## 5. Forbidden

Do not change:

```text
app/controllers/omada*.py
app/auth/**
app/capport/**
app/pending_sessions/**
Observation workers/normalizers/writers
Visit start/finalization/reader runtime
Snapshot Collector
Registry worker
source SQLite schemas
run.py
requirements*
Grafana/Alloy/Loki
systemd/Nginx
production env
KB/docs
```

No Omada call path may exist in `app/analytics`.

---

## 6. Configuration

Safe defaults:

```text
ANALYTICS_FOUNDATION_ENABLED=false
ANALYTICS_DEFAULT_LIMIT=500
ANALYTICS_MAX_LIMIT=2000
ANALYTICS_MAX_QUERY_WINDOW_DAYS=31
ANALYTICS_MAX_QUERY_DURATION_SECONDS=10
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS=180
```

PR A is not wired in `run.py`; therefore these keys have no production runtime effect.

Validation:

- exact boolean;
- positive integer limits;
- default <= max;
- max <= 2000;
- window positive and bounded;
- query duration >0;
- gap threshold >0.

---

## 7. Source access contract

Conceptual dependency injection:

```text
AnalyticsSourceGateway(
    observation_read_service,
    visit_read_service,
    registry_read_service,
)
```

No globals.

No duplicate SQLite persistence owner.

No arbitrary source DB path opening inside metric modules.

If set-based aggregation requires source repository read-only SQL, that access is encapsulated behind the source read boundary.

---

## 8. Read-only enforcement

Tests must prove:

- source readonly connections are used;
- Analytics has no source write dependency;
- source writes through Analytics are impossible/rejected;
- row counts and source data do not change after Analytics queries;
- no source migrations/user_version changes.

Observation current readonly path already uses `mode=ro` and `PRAGMA query_only=ON`; do not weaken it.

---

## 9. Time semantics

All Analytics ranges:

```text
[from_utc, to_utc)
```

Strict fixed-width UTC.

Current Observation read methods are inclusive at `to_utc`. 01A must normalize this safely by:

- adding a narrow half-open source read method; OR
- filtering exact `to_utc` rows without losing cursor correctness.

Do not hide an undocumented “minus one millisecond” adjustment.

---

## 10. Immutable contracts

Minimum conceptual models:

```text
AnalyticsProvenance
AnalyticsQuality
AnalyticsResult[T]

CoverageMetric
CycleQualitySummary
SourceFreshness
FieldCompleteness
VisitObservationCoverage
AnalyticsVisitContext
AnalyticsPage[T]
```

No mutable source dictionaries or `sqlite3.Row` escape from Analytics API.

Nested mappings exposed in result must be immutable/defensively copied.

---

## 11. Status semantics

Allowed:

```text
ok
partial
insufficient_data
unavailable
```

Exact rules:

### `ok`

Required sources available and metric requirements satisfied.

### `partial`

Computation completed but caller explicitly allowed diagnostic partial source rows, deadline cut work short, or optional source component was unavailable while safe partial result remains.

### `insufficient_data`

Sources are available but denominator/sample/required data is insufficient.

### `unavailable`

Required source cannot be read or validated.

Never convert these to zero.

---

## 12. Strict Observation acceptance

Default:

```text
quality_mode = strict_complete
```

Client row:

```text
parent state = completed
parent complete = true
parent result = success
source_inventory_complete = true
```

AP:

```text
parent state = completed
parent complete = true
parent result = success
ap.partial = false
required section flag = true
```

Radio:

```text
accepted parent AP
same Site/AP
```

Diagnostic mode may include partial source data but provenance/status must show it.

---

## 13. Required narrow source capabilities

### 13.1 Observation quality aggregate

Need bounded read-only access for:

```text
cycle counts by kind/state/result/complete
latest accepted timestamp
source row count
approved-field missing counts
```

If added to Observation read service, existing methods/semantics must remain backward compatible.

### 13.2 Visit authorization evidence

Need bounded read-only:

```text
authorization count by visit_id
authorization count for bounded visit-id batch
```

No source write.

### 13.3 Visit source event quality

Need Site-scoped aggregate counts:

```text
processing_result
reason
```

Null-site events cannot be attributed to requested Site.

### 13.4 Snapshot safe summary

Need exact safe lookup:

```text
site_id + snapshot_id
```

Allowed output fields:

```text
snapshot_id
device_id
auth_session_id
site_id
requested_mac
authorized_at
captured_at
device_type
ssid
ap_mac
radio_id
channel
rssi
snr
traffic_down
traffic_up
```

Never expose:

```text
raw_controller_snapshot_json
client_json
auth_context_json
```

---

## 14. Registry Site protection

Current device identity is global-by-MAC.

Analytics may use `device_id` for stable identity.

But if current Registry card has:

```text
last_site_id != requested site_id
```

then these current `last_*` values MUST NOT be returned as Site-specific context:

```text
last_ip
last_ssid
last_ap_name
last_ap_mac
last_rssi
last_snr
```

Use Site-scoped snapshot/Visit/Observation facts.

Explicit test required.

---

## 15. Device link coverage

Population is the selected Visit population.

```text
numerator =
count(visits where device_id IS NOT NULL)

denominator =
count(eligible visits)

ratio =
numerator / denominator
```

If denominator 0:

```text
status=insufficient_data
ratio=NULL
```

Return numerator and denominator.

---

## 16. Initial Snapshot coverage

```text
numerator =
count(visits where initial_snapshot_id IS NOT NULL)

denominator =
eligible visits
```

Link presence and safe snapshot existence should be distinguishable:

```text
linked_id_count
resolved_snapshot_count
missing_snapshot_row_count
```

No nearest snapshot guessing.

---

## 17. Authorization attachment coverage

For each Visit:

```text
authorization_count =
COUNT(visit_authorizations)
```

Coverage:

```text
visits_with_authorization_count>=1 / visits
```

Every Visit should have start evidence. Analytics reports mismatch; it does not repair it.

---

## 18. Visit close coverage

Return:

```text
total_visit_count
open_visit_count
closed_visit_count
closed_ratio
```

`open` is a lifecycle state, not an error.

Do not use this ratio as finalization-success KPI without an age/window policy.

---

## 19. Observation coverage in Visit window

Closed Visit:

```text
[started_at, closed_at)
```

Open Visit:

```text
[started_at, evaluation_to_utc)
provisional=true
```

Return:

```text
sample_count
first_observed_at
last_observed_at
edge_gap_start_seconds
edge_gap_end_seconds
max_inter_sample_gap_seconds
gap_count_over_threshold
```

If closed Visit duration >0 and at least two samples:

```text
observed_span_seconds =
last_observed_at - first_observed_at

observed_span_ratio =
min(1, observed_span_seconds / visit.duration_seconds)
```

If sample count <2, ratio is NULL with `insufficient_data` for span calculation.

---

## 20. Cycle quality

For each:

```text
client
ap_dynamic
ap_config
```

return:

```text
running
completed
abandoned

completed_complete
completed_incomplete

success
partial
failed
shutdown

complete_ratio =
completed_complete / completed
```

Zero denominator => ratio NULL.

Do not combine `abandoned` with failed silently.

---

## 21. Source freshness

Each source returns latest accepted timestamp and:

```text
freshness_seconds =
evaluation_at - latest_timestamp
```

If no accepted source row:

```text
insufficient_data
```

01A reports seconds only; no “fresh/stale” label.

---

## 22. Gap metrics

For ordered samples:

```text
gap_i = timestamp_i - timestamp_(i-1)
```

Return:

```text
sample_count
interval_count
max_gap_seconds
gap_count_over_threshold
threshold_seconds
```

No inferred missing samples count unless cadence history becomes authoritative.

---

## 23. Missing-field quality allowlist

Only count:

### Client

```text
ap_mac
radio_id
band
channel
rssi
snr
traffic_down
traffic_up
```

### AP/radio

```text
cpu_util
mem_util
busy_util
tx_util
rx_util
interference_util
rx_retry_packets
tx_retry_packets
rx_error_packets
tx_error_packets
rx_drop_packets
tx_drop_packets
radio_rx_mbps
radio_tx_mbps
```

For each:

```text
row_count
non_null_count
missing_count
coverage_ratio
```

Unknown columns are not accepted dynamically.

---

## 24. Query contracts

### Overall source quality

```text
get_source_quality(
    site_id,
    from_utc,
    to_utc,
    evaluation_at_utc,
)
```

### Visit quality page

```text
list_visit_quality(
    site_id,
    from_utc,
    to_utc,
    status=None,
    limit=500,
    cursor=None,
)
```

Ordering:

```text
started_at DESC, visit_id DESC
```

### Single Visit context

```text
get_visit_context(
    site_id,
    visit_id,
    evaluation_to_utc=None,
    gap_threshold_seconds=None,
)
```

### Cycle quality

```text
get_observation_cycle_quality(
    site_id,
    kind,
    from_utc,
    to_utc,
)
```

### Approved field completeness

```text
get_field_completeness(
    site_id,
    source,
    from_utc,
    to_utc,
    fields,
)
```

Fields must be subset of fixed allowlist.

---

## 25. Pagination/bounds

- default 500;
- hard max 2000;
- opaque canonical cursors;
- malformed cursor => `AnalyticsQueryValidationError`;
- `from < to`;
- hard max window;
- deadline checked between source operations/pages;
- no unbounded page loop.

If deadline prevents completion:

```text
status=partial
reason=query_deadline
```

Never pretend complete.

---

## 26. No N+1

Forbidden for a page:

```text
for each Visit:
    query Visit auth
    query Registry
    query Observation
```

Required:

```text
bounded Visit batch
→ set-based/batch source lookups
→ compose in memory with bounded maps
```

Single-Visit context may use a small fixed number of source queries.

---

## 27. Capacity/performance gate

Required representative datasets:

```text
A: 30 clients, 2 AP, 1 day
B: 100 clients, 10 AP, 7 days
C: 300 clients, 30 AP, 7 days
```

Approx client rows:

```text
43,200
1,008,000
3,024,000
```

Record:

```text
rows/table
DB size
query elapsed
source SQL call count
rows transferred to Python
peak collection size
query plan/index use where practical
```

Benchmark at least:

1. cycle quality 24h;
2. cycle quality 7d;
3. single Visit coverage;
4. Site field completeness;
5. Visit link coverage;
6. source freshness.

Hard stop before 01B if 24h/100-client normal quality query needs:

```text
unbounded full-table scan
OR >250,000 Python row objects materialized at once
```

If query-on-read fails, return rollup-storage recommendation.

---

## 28. Query-on-read acceptance recommendation

01A handoff MUST say one:

```text
QUERY_ON_READ_ACCEPTED
```

or:

```text
QUERY_ON_READ_REJECTED
ROLLUP_ARCHITECTURE_REQUIRED
```

01B remains blocked until explicit acceptance.

---

## 29. Security/privacy

Entity-specific internal response may include:

```text
visit_id
device_id
requested client_mac
AP MAC
```

Aggregate results must not include lists of:

```text
client MAC
device IDs
IP
hostname
```

Never expose source raw JSON columns.

No secrets/tokens/passwords/cookies.

---

## 30. Telemetry

Summary only:

```text
analytics.query_completed
analytics.query_insufficient_data
analytics.query_unavailable
analytics.performance_budget_exceeded
```

Safe fields:

```text
metric
site_id
duration_ms
sample_size
accepted_rows
rejected_rows
status
reason
quality_mode
```

No sample arrays.

---

## 31. Source failure behavior

If one required source fails:

- single-source metric may still succeed if that source is not needed;
- composed result uses `partial` only if safe partial meaning is explicit;
- otherwise `unavailable`.

Never convert source failure to zero.

Analytics failure remains fail-open to production runtime.

---

## 32. Tests

Minimum:

- config validation;
- immutable result;
- status semantics;
- half-open boundaries;
- exact-to Observation exclusion;
- Site isolation;
- Registry cross-Site protection;
- source read-only;
- no Omada dependency;
- complete/partial cycle policy;
- running/abandoned cycle counts;
- NULL != 0;
- zero denominator;
- device link coverage;
- snapshot link/resolution coverage;
- authorization coverage;
- Visit observation coverage;
- open Visit provisional window;
- closed zero-duration handling;
- gaps;
- missing-field allowlist;
- freshness;
- cursor/limit validation;
- deadline partial;
- bounded >1 page;
- no-N+1 batch spy;
- representative performance datasets;
- secret markers.

---

## 33. Regression gate

At minimum current:

```text
tests/observations/**
tests/visit_lifecycle/**
tests/visitor_registry/**
current Auth/CAPPORT tests
```

Then full:

```bash
python -m pytest -q -rs

PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc   python -m compileall -q app

git diff --check
```

Exact numbers required.

---

## 34. Acceptance

PASS only if:

- analytics foundation is read-only;
- no Omada path;
- no source schema/write changes;
- Site isolation preserved;
- Registry cross-Site last-context leakage prevented;
- half-open semantics consistent;
- quality outputs deterministic;
- no wireless good/bad verdict;
- bounded pagination/deadline;
- no N+1;
- performance report delivered;
- query-on-read verdict explicit;
- regressions/full gate reviewable;
- production untouched.

---

## 35. Stop conditions

Stop if:

- baseline/source contracts materially changed;
- required Site isolation cannot be guaranteed;
- read method requires write connection;
- source migration required;
- raw JSON would need exposure;
- query cannot be bounded;
- materialized analytics storage becomes necessary;
- new dependency required;
- full regression failure cannot be classified.

---

## 36. Repository actions

Until explicit owner approval:

```text
NO branch
NO code
NO commit
NO push
NO PR
```

After approval, branch:

```text
feature/analytics-read-quality-v1
```

Commit/push/PR/merge/deploy follow separate owner permissions.

---

## 37. Handoff

Return:

```text
BASELINE
IMPLEMENTED
NOT IMPLEMENTED
FILES
SOURCE READ EXTENSIONS
READ-ONLY PROOF
QUERY CONTRACTS
QUALITY FORMULAS
PERFORMANCE TABLE
QUERY_ON_READ VERDICT
SECURITY/PRIVACY
TARGETED TESTS
REGRESSIONS
FULL GATE
RISKS
REPOSITORY ACTIONS
NEXT OWNER ACTION
```

---

## 38. Review gate

Implementation command only after approval:

```text
TASK Analytics 01A утверждено, начинать PR A
```
