# TASK-DTI-NI-02A — Coder implementation handoff

Status: REVIEW CANDIDATE / awaiting Tech Lead code review, NOT production acceptance.

## IMPLEMENTED

Separate `app/network_attribution/` IPv4 temporal authority. Immutable DHCP lifecycle facts, finite half-open binding intervals, renewal, reassignment, IP reuse, validated client termination, deterministic lease expiry, exact Site isolation, explicit source coverage and historical horizon, bounded 30-day retention, read-only resolution and fail-open Sensor adapter.

The frozen resolution-precedence clarification is incorporated: invalid → outside_historical_horizon → unavailable → ambiguous → resolved → unattributed. Coverage outages do not rewrite lease intervals. Recovery alone cannot restore a prior lease's authority. A new trusted ACK re-establishes the confirmation boundary. Historical reads select the latest immutable confirmation at/before the requested time, not a future renewal's mutable `last_confirmed_at`.

Candidate identity:

```text
WORKTREE=C:\CaptivePortal-NI02A
BRANCH=feature/dti-ni-02a-ipv4-temporal-authority
BASE_HEAD=701ce630b595a87e9350b826a06ee02eaebc7f9e
BASE_TREE=59425257b1b9ddd557113da158c88d58bfe06bfc
HEAD_REMAINS=701ce630b595a87e9350b826a06ee02eaebc7f9e
REVIEW_CANDIDATE_TREE=92eafeee47077aa7a16dba199efbaf9c4fe3cef3
WORKTREE=DIRTY / exact implementation changes only
COMMIT_CREATED=NO
```

The candidate tree was reconstructed from the full patch using a separate external temporary Git index; it is not a commit and did not replace HEAD or stage candidate contents in the worktree index. New paths were marked intent-to-add solely to export the complete Git diff.

Transport artifact:

```text
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-02A_BASE-to-CANDIDATE.patch
PATCH_BYTES=81471
PATCH_SHA256=a0070a3b94569ac6e3ad657b653f23bf363af4d12a02dd622d143340ecde93bb
PATCH_FORMAT=git diff --binary --full-index BASE
PATCH_RECONSTRUCTION=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
```

Implementation details:

- Config is independent of frozen SensorConfig, default OFF, path `/opt/CaptivePortal/data/network_attribution.sqlite3`, default budget 536870912, hard maximum 2147483648.
- SQLite V1: `user_version=1`, `foreign_keys=ON`, WAL, FULL synchronous, busy_timeout 500. Separate authority facts, binding intervals, confirmation links, source coverage, Site horizon, and schema metadata. No migration framework. Existing foreign/corrupt schema is rejected before changing its journal mode.
- Fact IDs derive from canonical scalar fact semantics excluding ingestion time. Re-observation is idempotent; facts cannot be updated. No packet payload, PCAP, DNS/SNI/HTTP content or credentials are stored.
- Interval renewal retains binding_id/valid_from; expired intervals are not revived across their expiry. No open-ended ownership interval, no timer expiry mutation, no newest/nearest/longest selection.
- Conflicting authority does not overwrite prior facts/intervals. It rejects the new fact and fences the NI source unavailable. Exact equivalent same-pair ACKs at the same millisecond are not falsely rejected merely for a different xid.
- RELEASE uses client ciaddr; DECLINE uses requested-address option 50. Both require exact live Site/MAC/IP repository proof and sufficient coverage continuity. No DHCP ScopeResolver change or alternate authority.
- Coverage includes a durable `verified_through` operational watermark. Open coverage never proves beyond its last persisted capture confirmation; unclosed previous-process coverage cannot bridge a restart gap. Lease rows remain unchanged. Idle-poll watermark updates are bounded, actual authority frames also confirm capture before recording, and shutdown fences NI coverage before capture teardown/worker joins.
- Frames queued before the first persisted usable coverage are ignored as authority, not backfilled and not treated as a permanent recorder fault.
- Retention performs at most 100 removals per interval/fact/link/coverage batch per call; retained start/last facts and the required pre-horizon confirmation/coverage dependencies survive. Recorder invokes retention at most once per minute.
- The sensor spools existing normalized output before calling NI on the already received/deduplicated frame. NI failure does not enter Fingerprint health state, raw normalization, spool or delivery error handling. No second capture socket, thread or process is introduced.

## NOT IMPLEMENTED

NI-02B / device_id lookup / Device-relative edges; Admin or Device Card UI; IPv6; Cisco or Omada polling; alternate Registry/Visit/Observation authority; protocol/service/organization recognition; Suricata DHCP enablement; NI-01 migrations; systemd/deployment configuration; live capture attachment; production activation; production acceptance.

## FILES INSPECTED

Inputs: the original NI-02A task, baseline reconciliation instruction, and frozen resolution-precedence clarification.

Repository instructions:

```text
C:\CaptivePortal-NI02A\AGENTS.md
C:\CaptivePortal-NI02A\docs\agents\workflow.md
C:\CaptivePortal-NI02A\docs\agents\handoff.md
C:\CaptivePortal-NI02A\docs\testing-environments.md
C:\CaptivePortal-NI02A\docs\operations-command-lessons-learned.md
```

Affected/reference source and tests inspected:

```text
app/device_fingerprint_sensor/cli.py
app/device_fingerprint_sensor/runtime.py
app/device_fingerprint_sensor/config.py
app/device_fingerprint_sensor/models.py
app/device_fingerprint_sensor/dhcp.py
app/device_fingerprint_sensor/normalizer.py
app/device_fingerprint_sensor/capture.py
app/device_fingerprint_sensor/telemetry.py
app/device_fingerprint/validation.py
app/device_fingerprint/models.py
app/device_fingerprint/config.py
app/common/mac.py
app/network_metadata/config.py
app/network_metadata/schema.py
app/network_metadata/models.py
app/network_metadata/repository.py (relevant single-writer/transaction section)
tests/device_fingerprint_sensor/test_runtime.py
tests/device_fingerprint_sensor/test_dhcp.py
tests/device_fingerprint_sensor/test_cli.py
```

Paths in the last block are relative to `C:\CaptivePortal-NI02A`. All newly written NI-02A source/tests were also inspected. No nested AGENTS files were found under app/tests. The presumed sensor conftest path does not exist; no such file was created or modified.

## FILES CHANGED

Exactly 13 files: 1465 insertions, 3 deletions.

```text
M app/device_fingerprint_sensor/cli.py
M app/device_fingerprint_sensor/runtime.py
A app/network_attribution/__init__.py
A app/network_attribution/config.py
A app/network_attribution/dhcp_authority.py
A app/network_attribution/models.py
A app/network_attribution/read_service.py
A app/network_attribution/repository.py
A app/network_attribution/schema.py
A app/network_attribution/validation.py
A tests/network_attribution/__init__.py
A tests/network_attribution/test_authority.py
A tests/network_attribution/test_sensor_adapter.py
```

No existing test file modified. No change in `app/network_metadata/**`, `app/device_fingerprint/**`, Sensor scope/normalizer/dhcp/config/models/telemetry, or deploy artifacts. NI-01 byte/schema contract and existing Fingerprint output semantics are not changed.

## TESTS EXECUTED

Windows: Python 3.10.11, pytest 9.1.1. Workdir `C:\CaptivePortal-NI02A`.

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\ni02a-pycache'
python -m pytest -q tests/network_attribution --basetemp C:\CaptivPortal-Lab\tmp\ni02a-focused-final-v2
python -m pytest -q tests/device_fingerprint_sensor/test_runtime.py tests/device_fingerprint_sensor/test_dhcp.py tests/device_fingerprint_sensor/test_spool.py tests/device_fingerprint_sensor/test_producer.py tests/device_fingerprint_sensor/test_cli.py --basetemp C:\CaptivPortal-Lab\tmp\ni02a-sensor-final
python -m compileall -q app/network_attribution app/device_fingerprint_sensor/cli.py app/device_fingerprint_sensor/runtime.py tests/network_attribution
git diff --check
git apply --reverse --check C:/CaptivPortal-Lab/artifacts/TASK-DTI-NI-02A_BASE-to-CANDIDATE.patch
```

The 47-test direct sensor subset was run after the final sensor lifecycle changes. Subsequent changes were confined to NI modules and their focused tests; NI focused verification was rerun on those exact changes.

Linux: dedicated laptop WSL Ubuntu-22.04, Python 3.10.12, existing perf-venv; focused component checks only, not an official acceptance/PERF gate.

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivePortal-NI02A --exec env PYTHONPATH=/mnt/c/CaptivePortal-NI02A PYTHONPYCACHEPREFIX=/tmp/ni02a-pycache /home/zaur_navi/captivportal-lab/perf-venv/bin/python -m pytest -q tests/network_attribution --basetemp /tmp/ni02a-focused-linux-final-v2
```

## TEST RESULTS

```text
NI02A_WINDOWS=62 passed / 0 failed / 0 skipped
NI02A_LINUX=62 passed / 0 failed / 0 skipped
MINIMAL_SENSOR_REGRESSION=47 passed / 0 failed / 0 skipped
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
PATCH_REVERSE_APPLY=PASS
FULL_REPOSITORY_RUN=NO
CENTRAL_LAB_RUN=NO
LIVE_CAPTURE_RUN=NO
PRODUCTION_TEST=NO
```

Required case coverage:

| Task cases | Focused proof |
|---|---|
| 1, 2–5 | exact finite trusted ACK; wrong source/option54/scope/lease; malformed and duplicate authority options |
| 6–8 | one-interval renewal; exact same-MAC reassignment and same-IP reuse boundaries |
| 9, 13 | exact half-open start/end; deterministic expiry with no timer mutation |
| 10–12 | matching RELEASE/DECLINE; unmatched/wrong-MAC/wrong-IP termination ignored; no release after an unproven gap |
| 14 | same-event-time primary conflicts, no overwrite; ambiguity never selects one candidate |
| 15–18 | usable/no binding, unavailable coverage, pre-horizon query, independent Sites |
| 19–20 | recorder/repository failure does not suppress normalized output; dedup precedes both consumers; default-OFF equivalence and no recorder construction |
| Clarification A–E | outage during live lease; before-outage resolution; recovery without ACK remains unavailable; new ACK restores authority; unavailable precedes ambiguity |
| Additional direct boundaries | historical confirmation before a future renewal; restart-gap proof; no queued pre-activation backfill; immutable facts/idempotency; exact schema and pragmas; missing/foreign/tiny store; single-writer exclusion; bounded retention and retained dependencies |

## UNVERIFIED AREAS

Tech Lead owns broader integration/regression, production-like replay, real capture validation, capacity/WAL-reader-pressure acceptance and failure-injection gates. No such formal gate was executed by Coder. Production service filesystem permissions/sandbox access for the new DB path and activation configuration were not tested or modified. No claim of production acceptance.

## KNOWN RISKS

- Related authority arriving earlier than an already materialized related fact is rejected/fenced rather than reordered or used to backfill history. This conservative live-order behavior is visible in source for Tech Lead review; no late-event replay subsystem was introduced.
- WAL/shm space is reserved within the configured total footprint. A blocked truncating checkpoint or storage error permanently degrades the sidecar for that process; pressure/recovery behavior still needs the Tech Lead capacity/failure-injection gate. Default configuration remains OFF.
- Reads beyond the last persisted open-coverage watermark return unavailable until capture confirmation advances. This avoids treating a dead writer's open coverage row as present authority.
- Every syntactically valid query validates the exact schema and SQLite integrity in a read-only transaction. Query performance/production cardinality acceptance is not claimed.
- A conflict leaves previous facts/intervals intact and records unavailable coverage; it is not silently mapped to the first MAC. Restore requires the normal capture/authority re-establishment lifecycle, not heuristic fallback.

## REPOSITORY ACTIONS

```text
Branch created: YES
Dedicated clean baseline worktree created: YES
Commit created: NO
Push completed: NO
PR opened: NO
Merge completed: NO
Deployment completed: NO
Production action: NO
Existing UI/DTI worktrees modified: NO
```

Only local candidate files, intent-to-add entries for patch export, and an external reconstruction index/tree were prepared. No immutable implementation commit was fabricated.

## NEXT OWNER ACTION

Tech Lead: source/diff review the exact patch and frozen continuity contract, then define the relevant broader integration/capacity/failure-injection acceptance set. Coder is HOLD; commit/push/PR require separate explicit authorization. Production deployment/activation remain unauthorized.

Agent execution summary: Codex Coder, implementation mode, offline component tests only, no sub-agents, 13 changed files, no modified existing test files, exact candidate tree/patch above, NOT accepted for production, no publication or production actions.
