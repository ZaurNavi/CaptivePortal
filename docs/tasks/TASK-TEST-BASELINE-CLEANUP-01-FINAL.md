# TASK-TEST-BASELINE-CLEANUP-01 — Windows Compatibility Debt Removal — FINAL

Status: FINAL ACCEPTED / MERGED / DEPLOYED / PRODUCTION PASS
Updated: 2026-09-12

## Final identity

```text
TASK=TASK-TEST-BASELINE-CLEANUP-01
PR=#116
PR title=TASK-TEST-BASELINE-CLEANUP-01: remove Windows compatibility debt
publication branch=feature/test-baseline-cleanup-01
publication commit=ef3e8ca20e2303c29437c6c087919a6715afac96
publication parent / accepted baseline=75df5af1500ebcaf7d4950abccbaabc0a03610e1
merge / current production HEAD=c1dc3344bc778a32cdc6b0edce278ee40b287c29
accepted / merged / production tree=0563f58cf2a5c961e1dedb52cfa2b4b298dd2c1c
```

Critical identity invariant:

```text
accepted candidate tree
=
publication commit tree
=
merge commit tree
=
production tree
=
0563f58cf2a5c961e1dedb52cfa2b4b298dd2c1c
```

## Implementation scope

Exactly four implementation/test files changed:

```text
app/analytics/source_gateway.py
tests/analytics/test_historical_traffic.py
tests/test_auth_retry_frontend.py
tests/visitor_registry/test_device_registry_worker.py
```

Final diff:

```text
4 files changed
30 insertions
16 deletions
NO EXTRAS
```

Only `app/analytics/source_gateway.py` is production runtime code.

## SQLite finite/nonnegative portability

The platform-sensitive max-double comparison was removed.

Canonical fail-closed SQL shape:

```text
typeof(value) IN ('integer','real')
AND value >= 0
AND COALESCE((value - value) = 0, 0)
```

Finite numeric values satisfy `value - value = 0`.

Infinity produces non-finite/NULL semantics through self-subtraction and fails
the predicate closed.

This applies to current and historical Analytics read paths.

Historical regression evidence now includes `float("inf")`.

## Node retry tests

Production JavaScript was not changed.

The test harness no longer assumes the production click handler returns a
Promise. Tests invoke the listener and separately drain asynchronous work using
`setImmediate`.

```text
production JavaScript change=NO
test synchronization change=YES
```

## Visitor Registry timing tests

Production Visitor Registry runtime was not changed.

The test helper now accepts a parametrized `scan_interval_seconds`. The three
timing/background cases use a test-only 5.0 second interval so a second scan
cannot begin before stop.

```text
production Visitor Registry change=NO
test timing synchronization change=YES
```

## Home Health

Production Home Health implementation was not changed.

The previously known Windows compatibility case is now an ordinary strict
regression test.

## Windows compatibility debt closure

Before this TASK, Windows Central Lab V6 had six special compatibility cases:

```text
1. SQLite infinity edge
2. Node retry async timing
3. Visitor Registry long audit
4. Visitor Registry previous-ready
5. Visitor Registry previous-stopping
6. Home Health unavailable analytics baseline
```

That is historical V6 evidence only.

Current contract:

```text
former six compatibility cases=ordinary strict regression tests
compatibility allowlist for former six=EMPTY
six-case --deselect path=REMOVED
separate six-case compatibility stage=REMOVED
six-case compatibility WARN escape=REMOVED
```

A failure in any of these cases is a normal strict regression failure.

## Windows Central Lab V7

Current canonical Windows full-regression runner:

```text
C:\CaptivPortal-Lab\lab-test-v7-strict.cmd
SHA256=45d3b37150a2c3b3d3e95460b2a1c6cab8d97aa333c3d3e0cd3507ef1c994f77
```

V7 stages:

```text
[1/4] ordinary full strict pytest
[2/4] compileall
[3/4] branch diff check
[4/4] exact-artifact immutability
```

Accepted run evidence:

```text
3129 passed
30 skipped
0 failed
0 deselected
strict regressions=0
compileall=PASS
branch diff=PASS
exact-artifact immutability=PASS
```

`3129 passed / 30 skipped` is evidence from this accepted run, not a permanent
hardcoded test-count invariant.

Permanent invariant:

```text
former six compatibility cases execute as ordinary strict tests
and cannot degrade to WARN
```

V6 runner:

```text
C:\CaptivPortal-Lab\lab-test-v6-fixed.cmd
status=HISTORICAL / AUDIT ONLY
```

V6 was not deleted or rewritten.

## Production deployment

Previous production:

```text
HEAD=043a13bc1e3aa3353e27af1859dc0bb698df4955
```

Merged target:

```text
HEAD=c1dc3344bc778a32cdc6b0edce278ee40b287c29
tree=0563f58cf2a5c961e1dedb52cfa2b4b298dd2c1c
```

Production `/opt/CaptivePortal` was updated FROM GIT using exact detached
artifact identity.

Post-deploy:

```text
HEAD=c1dc3344bc778a32cdc6b0edce278ee40b287c29
tree=0563f58cf2a5c961e1dedb52cfa2b4b298dd2c1c
worktree=CLEAN
```

Because `app/analytics/source_gateway.py` is runtime code and is also imported by
the Traffic Projection source path, production activation restarted:

```text
traffic-projection.service
captive-portal.service
```

Not required for this delivery:

```text
DB migration=NO
schema change=NO
configuration change=NO
feature flag change=NO
systemd unit change=NO
daemon-reload=NO
```

## Production acceptance

Traffic Projection:

```text
traffic-projection.service=active
artifact_sha=c1dc3344bc778a32cdc6b0edce278ee40b287c29
artifact_tree=0563f58cf2a5c961e1dedb52cfa2b4b298dd2c1c
projection_version=historical_traffic_projection.v1
status=healthy
backlog_cycle_count=0
```

Captive Portal:

```text
captive-portal.service=active
artifact_sha=c1dc3344bc778a32cdc6b0edce278ee40b287c29
artifact_tree=0563f58cf2a5c961e1dedb52cfa2b4b298dd2c1c
analytics startup=analytics.api_runtime_active
server=127.0.0.1:8088 / debug=False
listener=127.0.0.1:8088 LISTEN
HTTP readiness=400
```

HTTP `400` on `/` without required Omada request parameters is the expected
production readiness contract.

Observation continued successful cycles after restart. Admin Current State reads
executed after startup. No startup traceback or critical failure attributable to
this delivery was observed.

## Startup observation

The first readiness probe was early:

```text
systemd state=active
listener=absent
HTTP=000
```

The same PID then continued normal startup composition and reached:

```text
analytics.api_runtime_active
Starting server on 127.0.0.1:8088
LISTEN
HTTP=400
```

This is not a TASK regression.

Permanent operational rule:

```text
systemd active != HTTP readiness
```

After restart, wait for actual listener/readiness evidence. Do not issue a second
restart solely because systemd is already active while the HTTP listener has not
yet appeared if the same process is still making normal startup progress.

## Existing warning

Production logs contain `urllib3 InsecureRequestWarning` for HTTPS access to the
Omada Controller at `192.168.0.222`.

This warning pre-dates TASK-TEST-BASELINE-CLEANUP-01 and is not a regression of
this delivery.

## Final verdict

```text
TASK-TEST-BASELINE-CLEANUP-01=FINAL ACCEPTED
PR #116=MERGED
PRODUCTION DEPLOY=PASS
PRODUCTION ACCEPTANCE=PASS
CURRENT WINDOWS FULL RUNNER=V7 STRICT
V6=HISTORICAL / AUDIT ONLY
FORMER SIX COMPATIBILITY EXCLUSIONS=ORDINARY STRICT
COMPATIBILITY WARN ESCAPE FOR FORMER SIX=REMOVED
```
