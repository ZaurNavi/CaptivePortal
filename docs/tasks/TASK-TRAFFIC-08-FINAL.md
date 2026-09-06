# TASK-TRAFFIC-08 — Completed Guest Session Traffic

Status: CLOSED / DEPLOYED / ACTIVE / PRODUCTION VERIFIED
Updated: 2026-09-06

## Canonical closure

```text
TASK-TRAFFIC-08=CLOSED
PRODUCTION=DEPLOYED
FEATURE=ACTIVE
PRODUCTION_VERIFICATION=PASS
TRAFFIC_08_NEW_FAILURES=0
TRAFFIC_08_REGRESSIONS=0
```

Development, Owner Acceptance, merge, production deploy, separate activation and
production verification are complete.

## Git / artifact identity

```text
PR=#104
feature branch=feature/traffic-completed-sessions-v1
parent baseline=3761981f4b1ec30b330abe1eec1713f15191c711
accepted implementation commit=8cfe30c2bcb13bf3ca7e001238991abd5943ea08
merge / production commit=df91355a99d2561abc9c4d6d4bb6f5a968d327b3
accepted / production tree=1161739c6b4fe90fa08928556746a5a4ea6af4cd
cumulative R6 patch SHA256=6077ea09f6f1421d43f2602cbea6beeae436faf5dc19a032ed520cf348efbbfa
```

PR #104 used a normal merge commit.

Production checkout at closure:

```text
host=192.168.0.202
application=/opt/CaptivePortal
HEAD(detached)=df91355a99d2561abc9c4d6d4bb6f5a968d327b3
worktree=CLEAN
service=captive-portal.service
```

## Production activation

Deployment was intentionally two-stage:

```text
1. dormant deploy with WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false → PASS
2. separate Owner-authorized activation to true → PASS
```

Final production flag:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
```

The active process environment and `/etc/default/captive-portal` both confirmed
the enabled value.

Startup/readiness after deploy and activation: PASS.

## Product

Admin page:

```text
/admin/sites/<site_id>/traffic
```

API:

```text
GET /admin/api/v1/sites/<site_id>/traffic/completed-sessions
```

Production Site:

```text
site_id=6a64f17630da7c70d232187a
current name=Zefer_Parki
historical name=Home
```

This is the existing renamed Omada Site and is not the newer separate Site
currently named `Home`.

Source boundary:

```text
Visit Lifecycle DB
+
persisted Client Observation evidence
→ CompletedGuestSessionTrafficReadService
→ AdminQueryService
→ Admin API/UI
```

No Omada/provider polling occurs in this read path.
`historical_traffic_projection.v1` is not a source and was not changed.

## Session / cohort semantics

```text
session identity=visit_id
population=status=closed only
cohort=closed_at
attribution=[started_at, closed_at)
ranges=24h|7d
default=24h
pagination=keyset / no OFFSET
limit default=100
limit max=100
sort=closed_at DESC, visit_id DESC
sort contract=closed_at_desc_visit_id_desc.v1
maximum supported attribution window=86400s
```

The selected UI cohort does not clip the Visit attribution window.

For Visit duration > 24 hours:

```text
traffic values=null
evidence status=unavailable
reason=attribution_window_exceeds_supported_max
```

## Traffic evidence semantics

Download and Upload are independent.

Counters:

```text
monotonic delta=accepted
zero delta=valid numeric evidence
missing=counter_missing
regression=counter_reset
negative/wrap/clamp=not used
```

Continuity:

```text
uptime required
C uptime > P uptime=proven
equal=continuity_frozen
lower=connection_reset
missing=continuity_unproven
```

Maximum accepted Observation interval:

```text
180 seconds
```

Larger gap: `gap_too_large`.

SSID:

```text
both endpoints must have SSID
same SSID required
transition=ssid_transition
missing/unproven=ssid_unproven
```

AP equality is not required; roaming is allowed.

Authorization boundary inside candidate interval:
`authorization_boundary`.

## Public evidence contract

Statuses:

```text
complete
partial
insufficient_data
unavailable
```

Numeric `0` is evidence. `null` means unknown/unavailable.

Reason codes:

```text
invalid_elapsed
gap_too_large
authorization_boundary
ssid_transition
ssid_unproven
continuity_frozen
connection_reset
continuity_unproven
counter_missing
counter_reset
start_edge_uncovered
end_edge_uncovered
no_usable_interval
observation_source_unavailable
attribution_window_exceeds_supported_max
```

Root source health:

```text
Visits: healthy | unavailable
Observations: healthy | unavailable | not_required
Root status: ok | partial | insufficient_data | unavailable
```

## Admin UI contract

Panel order:

```text
1. Current Network Throughput
2. Online Guests
3. Completed Sessions
4. Network History
5. Statistics
6. Peak
7. Traffic by AP
8. AP Share
```

Heading:

```text
Completed Guest Session Traffic
```

Columns:

```text
Guest
Session Start
Session End
Duration
SSID
Download
Upload
Total
Evidence
```

Display:

```text
numeric zero → 0 B
unknown/null → —
```

Evidence labels:

```text
Complete sampled evidence
Partial evidence
Insufficient data
Unavailable
```

## Production smoke

```text
GET /admin/login = 200
POST /admin/login = 302
GET /admin/sites/6a64f17630da7c70d232187a/traffic = 200
GET /admin/api/v1/sites/6a64f17630da7c70d232187a/traffic/completed-sessions = 200

COMPLETED_SESSIONS_PANEL=FOUND
COMPLETED_SESSIONS_HEADING=FOUND
```

Final observed API smoke:

```text
ROOT_STATUS=partial
VISIT_SOURCE=healthy
OBSERVATION_SOURCE=healthy
RETURNED_COUNT=100
NEXT_CURSOR=True

EVIDENCE_STATUS_COUNTS:
partial=94
insufficient_data=6

NUMERIC_TOTAL_ROWS=94
API_RESPONSE_BYTES=75316
API_PARSE=PASS
```

`ROOT_STATUS=partial` is not an error. Both sources were healthy. It reflects
per-Visit evidence quality (commonly including `continuity_frozen`) and can
change as live Observation acquisition continues.

An earlier smoke had numeric rows `93` / insufficient `7`; the next smoke had
numeric rows `94` / insufficient `6`. This is expected live-data movement.

## Production dependencies / health

After restart:

```text
captive-portal.service=active
Analytics runtime=active
Public Traffic reconciliation=working
Omada webhook=204
Observation Client cycle complete=True
new TASK-TRAFFIC-08 startup exception/traceback=none
```

Existing `urllib3 InsecureRequestWarning` caused by `VERIFY_SSL=false` remains
pre-existing security debt and is not a TRAFFIC-08 failure.

## Acceptance

Windows:

```text
reconstruction=PASS
focused=50 passed
regression=PASS_WITH_BASELINE_EXCEPTIONS
canonical PERF=PASS
full suite=PASS_WITH_BASELINE_EXCEPTIONS
TASK-TRAFFIC-08 regressions=0
```

Owner Linux Lab:

```text
reconstruction=PASS
focused=50 passed
regression=PASS_WITH_BASELINE_EXCEPTIONS
PERF=PASS
full suite=2892 passed, 1 skipped, 3 baseline failures
TASK-TRAFFIC-08 new failures=0
```

Canonical Linux PERF:

```text
API50 p95=1.3743s <=2.0s
API50 max=1.3743s <=3.0s
API100 p95=2.3960s <=4.0s
API100 max=2.3960s <=6.0s

deadline failures=0
unexpected HTTP statuses=0
provider calls=0
payload <=256KiB=PASS
five source DB fingerprints unchanged=PASS
```

Required existing indexes confirmed:

```text
idx_visits_site_closed
idx_visit_auth_visit_time
idx_client_site_mac_time
```

TRAFFIC-08 added no new indexes.

## Known baseline exceptions — outside TRAFFIC-08

1. `tests/analytics/test_current_traffic.py::test_sql_integrity_aggregates_reject_corrupt_rate_and_null_values[wired_download_mbps-inf-bad_rate_count]`
2. `tests/test_auth_retry_frontend.py::test_lost_retry_response_reconciles_active_run`
3. Linux SQLite EXPLAIN planner:
   `tests/analytics/test_historical_traffic_peak.py::test_peak_projection_reuses_one_materialized_requested_range_validation`
4. Linux SQLite EXPLAIN planner:
   `tests/analytics/test_historical_traffic_statistics.py::test_combined_projection_materializes_one_expensive_validation_path`
5. Visitor Registry `[stopping]` timing race — baseline-flaky.

TRAFFIC-08 did not fix, suppress or newly introduce these conditions.

## Canonical Owner Linux Lab prerequisite

```text
WSL distro=Ubuntu-22.04
OS=Ubuntu 22.04.5 LTS
host=DESKTOP-7C8M3BS
user=zaur_navi
repo=~/captivportal-lab/repo
Python env=~/captivportal-lab/perf-venv
Python=3.10.12
pytest=9.1.1
Node.js=24.20.0
npm=11.19.0
node=/usr/bin/node
npm=/usr/bin/npm
```

Canonical entry:

```text
wsl -d Ubuntu-22.04
```

Before pytest:

```text
export PYTHONPATH="$PWD"
~/captivportal-lab/perf-venv/bin/python -m pytest ...
```

Do not treat generic `wsl` as canonical. Do not execute acceptance in a source
repo containing unfinished work; use a native Linux detached worktree from the
exact artifact.

Owner/production runbooks must not use `set -e` or `set -euo pipefail`.

## Rollback artifacts

```text
code rollback=6fbc3736085be9d0538d893b6e9569ff490ef7f4
pre-dormant env=/etc/default/captive-portal.pre-traffic08-20260906-233314
pre-activation env=/etc/default/captive-portal.pre-traffic08-activation-20260906-233650
```

Rollback is not required.

## Final decision

```text
TASK-TRAFFIC-08=CLOSED
PRODUCTION=DEPLOYED
FEATURE=ACTIVE
PRODUCTION_VERIFICATION=PASS
TRAFFIC_08_NEW_FAILURES=0
TRAFFIC_08_REGRESSIONS=0
```

No next Traffic TASK is currently assigned.
