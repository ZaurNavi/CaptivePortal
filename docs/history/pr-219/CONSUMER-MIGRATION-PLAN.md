# QIO-01D consumer migration — DRAFT / NOT ACTIVATION APPROVAL

External review artifact only. No Grafana/Loki/Alloy/Promtail configuration was
read from or written to a live service by Coder. No query execution against Loki
is claimed. Tech Lead owns actual installed-version query validation and
consumer admission. Production compact flag remains absent/OFF.

## Current consumer evidence and inventory prerequisite

The Tech Lead TASK identifies deployed dashboard UID
`captive-portal-auth-v3-fixed`, version 65, panel 138, with a completed-event
`count_over_time` series. This is supplied evidence, not a Coder observation
of the deployed dashboard. Owner/Tech Lead must read-only verify actual
dashboard version/query, labels, JSON envelope, data source/version, alert
rules, recording rules, exports/API consumers and non-Grafana parsers.
Repository searches cannot prove that all external consumers were found.

## Required series / semantics

1. **Completed reports emitted/observed**: count completion event log records.
2. **Completed scans represented (best effort)**: legacy event weight 1;
   schema-v2 weight `scans_represented`. Includes represented quiet scans plus
   the current successful or incomplete scan. Never add failed/deferred scans.
3. **Current activity**: processed line count/current nonempty reports, not
   `scans_represented` times current activity; aggregate counts do not multiply
   current `duration_ms` or processed lines.
4. **Incomplete/failure/deferral**: separate series with original semantics;
   incomplete completed report is NOT healthy success.
5. **Freshness**: last observed healthy complete report age and independent
   process/delivery health. Missing data is unknown, never a fabricated zero or
   healthy status. >120s stale/investigate, >180s unavailable/escalate at standard
   5s cadence/20s budget. For other budgets, require reviewed thresholds.
6. **Schema/data quality**: unknown schema, invalid/missing weight or parser
   errors must be visible and must block consumer acceptance. Never silently
   reinterpret malformed v2 as legacy weight 1.

## Review-only LogQL templates

Replace `<APP_SELECTOR>` with the *observed approved* selector (including braces).
No label names/values are invented here. Use separate queries/series; adapt the
actual JSON extraction to the observed envelope. `[5m]` is an example window,
not a change to existing dashboard resolution or alert policy.

Legacy completed scans:

```logql
sum(count_over_time(
  <APP_SELECTOR> | json | __error__=""
  | event="visit.reader_scan_completed"
  | reader_report_schema_version=""
  [5m]
))
```

V2 represented completed scans:

```logql
sum(sum_over_time(
  <APP_SELECTOR> | json | __error__=""
  | event="visit.reader_scan_completed"
  | reader_report_schema_version="2"
  | unwrap scans_represented | __error__=""
  [5m]
))
```

Reported events (both modes):

```logql
sum(count_over_time(
  <APP_SELECTOR> | json | __error__=""
  | event="visit.reader_scan_completed"
  [5m]
))
```

The two represented-scan series should be summed only after proving label
alignment and explicit missing-series behavior on the installed Loki/Grafana.
Do not blindly use vector `legacy + v2`: a missing operand can erase a series.
Do not coalesce absent logs into a healthy-zero scan assertion. Keep emitted
reports visible under a distinct legend rather than silently changing the old
legend. Complete/incomplete split must filter `scan_complete` independently;
all suppressed counts represent previous healthy complete scans, even if the
current reporting scan is incomplete. For a health-split metric, allocate
`suppressed_empty_scans` to healthy completed scans and the current unit weight
according to `scan_complete` instead of labelling the whole report incomplete.

`unwrap` and `sum_over_time` syntax follows the official
[Loki metric query reference](https://grafana.com/docs/loki/latest/query/metric_queries/)
and [query examples](https://grafana.com/docs/loki/latest/query/query_examples/).
These references do not prove compatibility with the deployed Loki version.
Error filtering in a numeric series is not permission to hide invalid input:
independent raw/quality views must expose JSON/unwrap failures and malformed or
missing v2 fields, negative/fractional weights, and violated
`scans_represented = suppressed_empty_scans + 1`. Tech Lead must verify integer
validation/invariant enforcement outside a mere float `unwrap` conversion.

## Disposable query-Lab acceptance (Tech Lead, NOT executed by Coder)

- Legacy-only events with no schema version: one per record.
- V2-only: weights 1, 2, 12; exact sum 15 and report count 3.
- Mixed OFF -> ON -> restart -> OFF, two processes, repeated timestamps and
  ordinary activity, incomplete, error and deferred records. Check weighting
  across process boundaries without treating process-local counters as durable.
- A v2 report with 11 suppressed healthy scans plus a current incomplete scan:
  represented total 12, healthy units 11, incomplete units 1.
- Broken JSON, unknown schema, absent/NaN/non-numeric/negative/fractional
  `scans_represented`, inconsistent suppressed count. Quality error visible;
  no incorrect fallback weight, no silent metric query error/series loss.
- Empty windows, one mode absent, stream labels differing, rollbacks/restarts,
  telemetry emission failure/crash-loss. No success inferred from silence;
  no invented durable delivery or exact durable scan count.
- Heartbeat at next successful completion >=60s; up to ~85s+jitter at standard
  cadence/budget. Verify 120s/180s observability boundaries, recovery display,
  and unchanged warning/error/deferral alerts on actual timestamps.

## Rollout / rollback / ownership

1. Tech Lead read-only inventories actual consumers and prepares exact versioned
   query changes; Owner approves any dashboard/alert mutation separately.
2. Validate mixed-history queries and quality/freshness checks in disposable Lab.
3. Admit code with default OFF through independent correctness/full/performance
   gates. Coder focused tests do not satisfy consumer or release admission.
4. Roll out admitted consumers first. Only then separate Owner GO for startup
   flag opt-in and a controlled service restart.
5. Matched performance evidence must measure producer messages/bytes, log writes
   and host physical HDD IOPS independently; no HDD benefit inferred from fewer
   INFO records. Coder performs no profiling or production measurements here.
6. Rollback by approved flag `false` and controlled restart; mixed queries remain
   valid. Never rewind offsets, mutate Visit rows, reset replay or change DB
   schema to undo an operational telemetry setting.

LIVE_GRAFANA_EDIT=NO
LOKI_QUERY_LAB_EXECUTION=NOT_RUN
CONSUMER_ADMISSION=PENDING_TECH_LEAD
PRODUCTION_COMPACT_ACTIVATION=HOLD
