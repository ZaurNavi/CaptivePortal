# TASK-ANALYTICS-01B — Wireless Analytics

**Project:** CaptivPortal  
**Parent:** `TASK-ANALYTICS-FOUNDATION-01 — REV1`  
**Status:** BLOCKED BY 01A  
**Architecture baseline:** `main@fe797593fb12b9cb9f81bdb22e1c14f2d08b037e`  
**Implementation baseline:** MUST be replaced/pinned to exact accepted 01A merge SHA before owner approval  
**Recommended branch:** `feature/wireless-analytics-v1`  
**Next:** 01C blocked until merge + acceptance 01B

---

## 1. Goal

Implement evidence-based Site-aware wireless/AP analytics over persisted Observation facts.

```text
Observation Foundation
→ 01A Read/Data Quality Foundation
→ Wireless Analytics
```

No new collector. No Omada calls.

---

## 2. Prerequisites

Before approval:

```text
01A merged + accepted
QUERY_ON_READ_ACCEPTED
exact merged 01A SHA pinned
```

Then execute pre-change Linux full gate.

If 01A quality/source contract differs from REV1, return for architecture rebind.

---

## 3. Allowed files

```text
app/analytics/wireless.py
app/analytics/formulas.py
app/analytics/models.py
app/analytics/config.py
app/analytics/read_service.py
app/analytics/source_gateway.py
app/analytics/telemetry.py

tests/analytics/test_wireless*.py
tests/analytics/** shared fixtures
```

Narrow read-only source additions only if 01A handoff explicitly identifies an approved gap.

---

## 4. Forbidden

Do not change:

```text
OmadaProvider
Observation schema
Observation collectors/cadence/writes
Visit schema/finalization
Registry schema
Snapshot
Auth/CAPPORT
Cleaner
run.py production wiring
requirements
Grafana/Alloy/Loki
production
```

No customer API/UI.

No AP-placement recommendation flag.

---

## 5. Configuration

```text
ANALYTICS_WIRELESS_ENABLED=true
ANALYTICS_WIRELESS_MIN_SAMPLES=20
ANALYTICS_WIRELESS_MAX_WINDOW_DAYS=7
ANALYTICS_COUNTER_MAX_GAP_SECONDS=180
ANALYTICS_AP_JOIN_MAX_LAG_SECONDS=120

ANALYTICS_RSSI_THRESHOLD_DBM=
ANALYTICS_SNR_THRESHOLD_DB=
```

Master flag remains false.

Validation:

- min samples >=2;
- wireless max window positive and <= master max;
- gap >0;
- join lag >0;
- thresholds optional finite numeric values.

No default semantic labels such as good/bad/poor/excellent.

---

## 6. Source acceptance

Default:

```text
quality_mode=strict_complete
```

Uses 01A accepted facts only.

Diagnostic partial source mode must be explicitly requested and returns `partial` quality/provenance.

---

## 7. Percentile contract

Use R-7 deterministic interpolation.

For sorted x[0..n-1], p∈[0,1]:

```text
h=(n-1)*p
j=floor(h)
g=h-j

if j == n-1:
    Q=x[j]
else:
    Q=x[j] + g*(x[j+1]-x[j])
```

Required:

```text
p10
p50
p90
p95
```

No external numerical dependency.

---

## 8. Signal distributions

Independent metrics:

```text
RSSI in dBm
SNR in dB
```

Output:

```text
sample_count
missing_count
minimum
maximum
mean
p10
p50
p90
p95
```

If sample count below configured minimum:

```text
status=insufficient_data
distribution values=NULL
```

Counts/provenance may remain available.

---

## 9. Configured threshold ratios

Only if caller/config supplies threshold.

RSSI:

```text
below_threshold_count =
count(rssi < threshold_dbm)

ratio =
below_threshold_count / count(non-null rssi)
```

SNR equivalent.

Output label:

```text
below_configured_threshold_ratio
```

Never automatically call it “bad-signal ratio”.

Threshold returned in provenance.

---

## 10. Client distributions by context

For Site/window return both:

```text
observation_count
distinct_client_count
```

Group dimensions:

```text
ap_mac
ssid
band
channel
```

Do not label observation count as clients.

Group with NULL context is either:

```text
explicit null bucket
```

or excluded with missing_count, but behavior must be explicit per method.

---

## 11. Concurrent observed authorized clients

One accepted complete Client Observation cycle is one collector inventory sample.

Per cycle:

```text
concurrent_observed_clients =
count(client rows)
```

Optional grouping:

```text
AP
band
SSID
```

Across cycles:

```text
cycle_sample_count
minimum
mean
p50
p95
maximum
```

Meaning:

```text
clients visible to the authorized-client collector at sample time
```

Not guaranteed human headcount.

---

## 12. AP CPU/RAM

Fields:

```text
cpu_util
mem_util
```

Return:

```text
sample_count
missing_count
mean
p50
p90
p95
max
```

Only accepted AP overview section.

---

## 13. Radio utilization

Fields:

```text
tx_util
rx_util
interference_util
busy_util
```

Per AP+band by default.

Do not sum utilization fields unless source semantics explicitly require.

Site-level aggregate keeps:

```text
distinct_ap_count
band
sample_count
```

---

## 14. Stored AP/radio throughput

Use persisted derived rates where corresponding reason:

```text
ok
```

Fields:

```text
wired_download_mbps
wired_upload_mbps
lan_rx_mbps
lan_tx_mbps
radio_rx_mbps
radio_tx_mbps
```

Return:

```text
valid_rate_sample_count
excluded_rate_sample_count
reason_counts
mean
p50
p90
p95
max
```

Do not reinterpret radio aggregate rates as per-client rates.

---

## 15. Client counter-derived throughput

Inputs:

```text
traffic_down
traffic_up
```

Same:

```text
site_id + client_mac
```

ordered consecutive accepted observations.

Formula:

```text
delta_bytes = current_bytes - previous_bytes
elapsed = current_time - previous_time

mbps =
delta_bytes * 8 / elapsed_seconds / 1_000_000
```

Valid when:

```text
delta_bytes >=0
elapsed_seconds >0
elapsed_seconds <= ANALYTICS_COUNTER_MAX_GAP_SECONDS
```

Reasons:

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_missing
```

Counter decrease never creates negative rate.

Directions:

```text
traffic_down → client_download_mbps
traffic_up   → client_upload_mbps
```

---

## 16. Retry/error/drop counter diagnostics

Radio fields are cumulative.

Never:

```text
SUM(raw cumulative snapshot values)
```

Use consecutive same:

```text
site_id + ap_mac + band
```

Valid delta interval has non-decreasing counter and acceptable gap.

Return independently:

```text
rx_retry_delta
tx_retry_delta
rx_error_delta
tx_error_delta
rx_drop_delta
tx_drop_delta
rx_packet_delta
tx_packet_delta
```

Quality:

```text
valid_interval_count
reset_interval_count
gap_interval_count
missing_interval_count
```

Optional diagnostic ratio:

```text
events_per_1000_packets =
1000 * sum(valid event deltas) / sum(valid packet deltas)
```

only if denominator >0.

Name must state controller-counter semantics.

---

## 17. Client ↔ AP temporal join

For each accepted client observation:

1. same `site_id`;
2. same `ap_mac`;
3. same `band` where both have one;
4. choose latest AP/radio sample with timestamp `<= client observed_at`;
5. require lag `<= ANALYTICS_AP_JOIN_MAX_LAG_SECONDS`.

Forbidden:

```text
future AP sample matched to earlier client sample
```

Return join quality:

```text
client_sample_count
matched_count
unmatched_count
match_ratio
lag_p50
lag_p95
lag_max
```

If band unavailable on client, AP-level CPU may still be matched by AP; radio metric match remains unavailable unless identity is safe.

---

## 18. Correlation

Candidates:

```text
RSSI ↔ busy_util
SNR  ↔ busy_util
RSSI ↔ cpu_util
SNR  ↔ cpu_util
```

Pearson:

```text
r =
Σ((x-x̄)(y-ȳ))
/
sqrt(Σ(x-x̄)^2 * Σ(y-ȳ)^2)
```

Requirements:

```text
matched n >= min samples
variance x >0
variance y >0
```

Else:

```text
insufficient_data
r=NULL
```

Always return match coverage.

No causal interpretation.

---

## 19. Wireless evidence bundle

Allowed composite output:

```text
signal distribution
configured threshold ratios
client distributions
concurrent observed clients
AP CPU/RAM
radio utilization
throughput
counter quality
correlations
coverage/provenance
```

Forbidden:

```text
needs_second_ap=true
move_ap=true
bad_ap=true
```

The bundle is evidence only.

---

## 20. Query API

Conceptual:

```text
get_signal_distribution(
    site_id, from_utc, to_utc,
    metric,
    client_mac=None,
    ap_mac=None,
    ssid=None,
    band=None,
    channel=None,
)

get_client_distribution(...)
get_concurrent_client_distribution(...)
get_ap_resource_distribution(...)
get_radio_utilization(...)
get_throughput_distribution(...)
get_counter_quality(...)
get_signal_ap_correlation(...)
get_wireless_evidence_bundle(...)
```

All require Site/range.

Entity-specific client query is internal-only.

---

## 21. Bounds/performance

Wireless hard window:

```text
7 days
```

No hidden override.

Longer trend need:

- separate aggregate query design; OR
- later rollup architecture.

No full history load.

Prefer:

```text
set-based SQL aggregate
streaming
bounded keyset pagination
```

Not:

```text
fetch all rows → Python
```

If 01A performance budget cannot be met:

```text
query rejected/insufficient with explicit reason
```

Do not bypass bounds.

---

## 22. NULL/partial/stale/reset/gap

Rules:

```text
NULL stays NULL
partial excluded default
stale join > lag excluded
counter reset invalidates interval
gap > max invalidates interval
missing AP ≠ zero AP load
offline/missing AP ≠ 0 utilization
```

Every exclusion count appears in quality/provenance.

---

## 23. Privacy/security

Aggregate outputs do not contain:

```text
client MAC list
device ID list
client IP
hostname
raw JSON
```

AP MAC may appear because it is managed infrastructure identity.

Entity-specific internal client debug result may echo requested MAC, but aggregate telemetry omits it.

No secrets.

---

## 24. Multi-Site

Every query requires `site_id`.

No cross-site aggregation.

Same AP MAC/client MAC in another Site cannot match.

Tenant not introduced.

---

## 25. Product/observability

Potential future Web metrics:

```text
aggregate signal distributions
AP/band distributions
concurrent observed clients
radio utilization
throughput distributions
```

Initially internal:

```text
counter reset diagnostics
join coverage
correlation
field/source quality
```

No routes/UI now.

---

## 26. Telemetry

Summary only:

```text
analytics.wireless_query_completed
analytics.wireless_insufficient_data
analytics.wireless_join_coverage_low
analytics.wireless_query_unavailable
```

Safe fields:

```text
site_id
metric
duration_ms
sample_size
status
reason
quality_mode
```

No sample arrays.

---

## 27. Tests — formulas

Minimum:

- R-7 exact vectors;
- one sample;
- min sample boundary;
- mean;
- threshold unset;
- threshold set;
- strict `< threshold`;
- NULL exclusion;
- no denominator.

---

## 28. Tests — grouping/concurrency

- Site isolation;
- AP grouping;
- SSID grouping;
- band grouping;
- channel grouping;
- observation_count != distinct_client_count case;
- concurrent clients per cycle;
- partial client cycle excluded;
- empty cycle semantics;
- half-open time boundary.

---

## 29. Tests — rates/counters

- client positive delta;
- counter reset;
- exact max-gap accepted;
- > max-gap excluded;
- invalid elapsed;
- no baseline;
- AP persisted rate reason filtering;
- radio bands independent;
- retry/error/drop positive deltas;
- reset of one counter does not invalidate unrelated direction;
- zero packet denominator;
- per-1000 formula.

---

## 30. Tests — temporal join/correlation

- exact timestamp match;
- predecessor chosen;
- future sample rejected;
- lag exactly max accepted;
- lag greater max rejected;
- Site mismatch rejected;
- AP mismatch rejected;
- band mismatch rejected for radio;
- AP CPU match without radio where safe;
- known Pearson example;
- zero variance;
- min sample boundary;
- matched coverage.

---

## 31. Tests — safety/performance

- no Omada calls;
- source read-only;
- no source schema change;
- 7-day max;
- query deadline;
- partial source exclusion;
- unavailable source;
- privacy markers;
- no secrets;
- performance fixture from 01A.

---

## 32. Regression/full gate

Run:

```text
tests/analytics/**
tests/observations/**
```

plus 01A-required source regressions.

Then:

```bash
python -m pytest -q -rs

PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc   python -m compileall -q app

git diff --check
```

Exact results required.

---

## 33. Acceptance

PASS if:

- formulas deterministic;
- percentile exact;
- min sample enforced;
- partial cycles excluded default;
- reset/gap safe;
- no negative rate;
- AP/radio semantics preserved;
- bands separate;
- temporal join never future-matches;
- correlation includes match coverage;
- thresholds neutral/configurable;
- no product recommendation;
- no Omada call;
- bounded 7d;
- read-only;
- privacy clean;
- regressions/full gate accepted;
- production unchanged.

---

## 34. Stop conditions

Stop if:

- 01A not accepted;
- exact merged baseline not pinned;
- query-on-read rejected;
- source field/unit semantics insufficient;
- proposed metric requires unknown unit conversion;
- source schema migration required;
- new dependency required;
- performance requires derived storage;
- product label cannot be defined without unverified assumptions.

---

## 35. Repository actions

Before explicit owner approval:

```text
NO implementation
```

After baseline pin and approval:

```text
TASK Analytics 01B утверждено, начинать PR B
```

Branch:

```text
feature/wireless-analytics-v1
```

Commit/push/PR/merge/deploy controlled separately.

---

## 36. Handoff

Return:

```text
BASELINE
IMPLEMENTED METRICS
NOT IMPLEMENTED
FILES
FORMULAS
SOURCE FIELDS
QUALITY POLICY
COUNTER/RATE POLICY
JOIN POLICY
PERFORMANCE
PRIVACY
TARGETED TESTS
REGRESSIONS
FULL GATE
RISKS
REPOSITORY ACTIONS
01C READINESS
```
