# TASK-DTI-NI-03 — CODER HANDOFF

STATUS=REVIEW CANDIDATE / HOLD FOR TECH LEAD SOURCE REVIEW

Implementation authority: TASK-DTI-NI-03-IMPLEMENTATION-CONTRACT-v3-RU.md,
supplied by Owner; architecture v1 + v1-R1 unchanged.

## BASELINE VERIFIED

```ini
BASE_HEAD=51deead342bd821b5c46fb75a7ceef37bef63e7c
BASE_TREE=7b6cfa20c23c097e87059ca12a593f697f0a36a2
HEAD_REMAINS=51deead342bd821b5c46fb75a7ceef37bef63e7c
BRANCH=feature/dti-ni-03-protocol-intelligence
WORKTREE=C:\CaptivPortal-Lab\coder-dti-ni-03
WORKTREE_STATUS=DIRTY / UNCOMMITTED
INDEX_STAGED_FILES=NONE
REMOTE_MAIN_AT_FINAL_EXPORT=51deead342bd821b5c46fb75a7ceef37bef63e7c
```

A separate clean worktree was created from the exact baseline before source edits.
Existing Settings/DTI worktrees were not edited/reset/rebased/cleaned.

## IMPLEMENTED

- DeviceProtocolIntelligenceReadService owns DNS/TLS/QUIC vocabulary, exact
  half-open 24h/60m windows, protocol aggregation, ordering, coverage/freshness,
  and closed public DeviceProtocolSummaryV1 construction.
- One process-local non-blocking two-slot semaphore plus the existing shared
  Admin query budget. Projection reads receive the smaller of the remaining
  shared deadline and five seconds; SQLite progress interruption is installed
  before schema/snapshot reads, and connections close on cancellation/failure.
- Narrow NI-02B read extension reads runtime, binding and facts in one read-only
  SQLite transaction. It uses the existing Site+MAC+time index, fetches at most
  20,001 candidate facts, and rejects overflow without a partial summary.
- Future/evaluation-time facts are separately detected by an indexed existence
  probe and fail closed. Non-authoritative identities never scan edge facts.
- Optional, default-OFF composition through canonical ProjectionConfig only.
  No projection DB is opened when disabled. Invalid optional configuration does
  not change core Admin runtime readiness.
- Site/capability-safe Device lookup and strict public serializer, route-specific
  v1 success/error envelope, 16 KiB response ceiling, no-store/no-cache.
- Conditional Device Card section and standalone safe-DOM coordinator: one
  request in flight, one coalesced manual follow-up, 60s polling, hidden/pagehide
  controls, 10s AbortController timeout, 60/120/300s failure backoff, 15m last-good
  display bound and terminal 401/403/404 stop.
- Repository-only main-service EnvironmentFile drop-in plus activation collision
  gate documentation. No installation/restart was performed.

## NOT IMPLEMENTED

No service/provider recognition, percentages, dominant protocol, endpoint data,
raw DNS/SNI/IP/port history, summary persistence/cache, upstream query-time
attribution, new writer/DB/service, Settings mutation or production activation.

## FILES INSPECTED

- Supplied v3 implementation contract; repository AGENTS.md.
- docs/testing-environments.md, docs/operations-command-lessons-learned.md,
  docs/agents/handoff.md.
- Modified source files listed below and existing NI-02B schema/config/models/
  validation/repository contracts, NI-01 timestamp validation, NI-02A MAC
  validation, Admin models/policy/Device gateway, QueryDeadline and existing
  Current Device serializer/frontend patterns.
- Existing Settings feature plan/definition/snapshot interfaces, read-only.
- Focused Admin fixtures/tests and NI-02B disposable support helpers.

Inspection served implementation mapping only; no alternative architecture or
production research was performed.

## FILES CHANGED

```text
M .env.example
M app/config.py
M app/settings.py
M app/network_metadata_projection/read_service.py
A app/network_protocol_intelligence/__init__.py
A app/network_protocol_intelligence/models.py
A app/network_protocol_intelligence/read_service.py
M app/admin_web/config.py
M app/admin_web/runtime.py
M app/admin_web/query_service.py
A app/admin_web/device_protocol_intelligence_serialization.py
M app/admin_web/routes.py
M app/admin_web/pages.py
M app/admin_web/templates/admin/base.html
M app/admin_web/templates/admin/device.html
A app/admin_web/static/device_protocol_intelligence.js
M deploy/network-metadata-projection/README.md
A deploy/network-metadata-projection/captive-portal-network-metadata-projection-read.conf
A tests/network_protocol_intelligence/__init__.py
A tests/network_protocol_intelligence/test_read_service.py
A tests/network_metadata_projection/test_protocol_evidence_snapshot.py
A tests/admin_web/test_device_protocol_intelligence.py
A tests/admin_web/test_device_protocol_intelligence_frontend.py
A tests/admin_web/device_protocol_intelligence.cjs
```

24 files changed, 1402 insertions(+), 4 deletions(-).
Existing test files modified: NONE. admin.css did not require changes.

## ARCHITECTURE INVARIANTS / REQUIREMENT MAPPING

| Requirement | Implementation / focused evidence |
| --- | --- |
| §§4–8 vocabulary, DTO, freshness, identity | network_protocol_intelligence models/read_service; deterministic boundary and coverage cases |
| §§10–12 concurrency, deadline, bounded same snapshot | projection read extension + process-local semaphore; 20,000/20,001, progress cancellation, unknown family, pending no-scan tests |
| §§13–15 default-OFF canonical config / startup plan | config/settings/Admin config/runtime; optional config disabled/invalid/valid and outer-gate tests |
| §§16–19 exact Site/capability/API/privacy | query_service, closed serializer and route; authorization, lookup ordering, 16 KiB, safe error mapping/header tests |
| §§20–22 Device Card coordinator | conditional templates + dedicated JS; real Node DOM/fetch/timer/visibility/timeout/terminal tests |
| §25 deployment configuration ownership | exact two-line read drop-in and collision-gate README; static artifact verification |
| §30 same snapshot / writer coexistence | two real NI-03 reads hold WAL snapshots while normal NI-02B poll/transaction commits; before/after observations remain consistent |

```ini
DATABASE_MIGRATION=NONE
SCHEMA_CHANGE=NO
NEW_DATABASE=NO
NEW_WRITER=NO
NI03_SUMMARY_PERSISTENCE=NO
NI02B_WRITER_CHECKPOINT_RETENTION_CHANGED=NO
NI01_NI02A_REGISTRY_PRODUCTION_SOURCE_CHANGED=NO
ADMIN_FEATURE_PLAN_REGISTRY_CHANGED=NO
SETTINGS_WRITABLE_SCOPE_CHANGED=NO
ADMIN_JS_CHANGED=NO
```

## CONFIG HANDOFF RESULT

PASS in focused tests. New flag defaults false and survives the existing feature
plan's composition as an unrelated deployment preference. Outer Admin=false +
NI-03=true remains inert, not an error. Existing 17 managed feature definitions
remain unchanged. Canonical projection disabled opens no old DB; invalid config
isolates NI-03; valid config hands the exact path/enabled/capacity to the reader.
The exact existing startup feature_plan object is preserved.

## SAME-SNAPSHOT / SQLITE WRITER-COEXISTENCE RESULT

PASS on Windows and Ubuntu-22.04 with disposable databases. Runtime, binding and
facts are observed from one snapshot. Two concurrent NI-03 readers coexist with
normal NI-02B polling/transactions; subsequent reads see the newer committed
state and facts. No permanent writer failure, blocked_conflict or false
capacity_halted was observed in this focused scenario.

Linux database/temp paths are native Linux under
/home/zaur_navi/captivportal-lab/ni03-disposable-native-02.
The Linux focused runner read the same candidate source bytes through
/mnt/c/CaptivPortal-Lab/coder-dti-ni-03; no Linux candidate commit was fabricated.

## PROTOCOL / COVERAGE / FRESHNESS RESULT

PASS: exact protocol ordering, deduplication, microsecond ordering, 60m/24h
boundaries, future/integrity rejection, base freshness and all runtime coverage
caps. Committed evidence under attribution_unavailable/source_unavailable/
capacity_halted returns HTTP 200 with degraded availability and the exact cap.
Zero eligible facts stays empty, never a claim of no network activity.

## API / FRONTEND / PRIVACY RESULT

PASS within focused scope. Exact envelope, Site/capability denial, canonical
identity validation, query/body rejection, feature-off 404, missing Device 404,
busy 429 + Retry-After:1, deadline/store 503, sanitized unexpected 500 and size
ceiling covered. The panel/script are absent when disabled or capability denied.
Node exercises real dedicated frontend source and rejects extra/invalid fields.
No browser persistence or unsafe HTML interpolation is introduced. New
application failure logs use constant sanitized event names without traceback,
device_id or raw source values. No Nginx changes.

## TESTS EXECUTED / EXACT FINAL COMMANDS

Windows interpreter: C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe.
Node: C:\Program Files\nodejs\node.exe.
External Python cache: C:\CaptivPortal-Lab\tmp\ni03-pycache.

```powershell
python -m pytest -q `
  tests/network_protocol_intelligence `
  tests/network_metadata_projection/test_protocol_evidence_snapshot.py `
  tests/admin_web/test_device_protocol_intelligence.py `
  tests/admin_web/test_device_protocol_intelligence_frontend.py `
  tests/admin_web/test_config.py `
  tests/admin_web/test_runtime.py `
  tests/admin_web/test_routes.py `
  tests/admin_web/test_query_service.py `
  tests/admin_web/test_device_current_context.py `
  tests/admin_web/test_device_current_context_frontend.py `
  tests/settings_control/test_features_stage6.py `
  --basetemp C:\CaptivPortal-Lab\tmp\ni03-final-02 `
  --junitxml C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-03-focused.xml
```

Final Windows result: 340 passed / 0 failed / 0 errors / 0 skipped.
Breakdown: new NI-03 tests 89 passed; authorized existing direct tests 251 passed.

Linux: existing Ubuntu-22.04 WSL, Python 3.10.12, existing perf-venv.

```bash
cd /mnt/c/CaptivPortal-Lab/coder-dti-ni-03
export PYTHONPATH="$PWD"
export PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/ni03-pycache
/home/zaur_navi/captivportal-lab/perf-venv/bin/python -m pytest -q \
  tests/network_protocol_intelligence \
  tests/network_metadata_projection/test_protocol_evidence_snapshot.py \
  --basetemp /home/zaur_navi/captivportal-lab/ni03-disposable-native-02 \
  --junitxml /mnt/c/CaptivPortal-Lab/artifacts/TASK-DTI-NI-03-linux-focused.xml
```

Final Linux result: 58 passed / 0 failed / 0 errors / 0 skipped.

```text
python -m compileall -q app/config.py app/settings.py
  app/network_metadata_projection/read_service.py app/network_protocol_intelligence
  app/admin_web/config.py app/admin_web/runtime.py app/admin_web/query_service.py
  app/admin_web/device_protocol_intelligence_serialization.py
  app/admin_web/routes.py app/admin_web/pages.py
  tests/network_protocol_intelligence
  tests/network_metadata_projection/test_protocol_evidence_snapshot.py
  tests/admin_web/test_device_protocol_intelligence.py
  tests/admin_web/test_device_protocol_intelligence_frontend.py

node --check app/admin_web/static/device_protocol_intelligence.js
git diff --check
```

COMPILEALL=PASS; NODE_CHECK=PASS; DIFF_CHECK=PASS.
An intermediate newly added test used an instance monkeypatch on a frozen policy;
that test-only fixture error was corrected, and the same full authorized focused
set then passed. No unrelated test expectations were changed. An initially
guessed bundled Node path was absent; the installed Node path above was used.

## UNVERIFIED AREAS / KNOWN RISKS

Official broader acceptance/Central Lab and production activation/collision/smoke
remain Tech Lead/Owner responsibilities. These were not executed or claimed.
Real production DBs, live capture, Omada or systemd were not accessed.
Linux proof is focused disposable WAL/deadline evidence, not production capacity
acceptance. No known blocker remains within the executed focused scope.

## CANDIDATE IDENTITY / PATCH

```ini
CANDIDATE_TREE=ece007c668c22471f802251ac8369369ad7e278d
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-03-CANDIDATE.patch
PATCH_BYTES=95925
PATCH_SHA256=ee9be3a5ac74ccd921ea7bfdb960b86f53e9a16c67d9127f5fd793dcef83373e
PATCH_FORMAT=git diff --binary --full-index BASE CANDIDATE_TREE
PATCH_RECONSTRUCTION=PASS
RECONSTRUCTED_TREE=ece007c668c22471f802251ac8369369ad7e278d
PATCH_REVERSE_APPLY_CHECK=PASS
INDEX_STAGED_FILES=NONE
HEAD=UNCOMMITTED CANDIDATE; repository HEAD remains BASE_HEAD
```

Candidate tree/export and reconstruction used separate external Git indices;
the actual worktree index remains unstaged. The full binary-capable patch includes
all new files, including the empty test package marker.

## REPOSITORY ACTIONS

```ini
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOYMENT=NO
PRODUCTION_ACTION=NO
FULL_REPOSITORY_TESTS=NO
CENTRAL_LAB=NO
NEXT_ACTION=TECH LEAD SOURCE REVIEW
```

Agent execution summary: Coder, implementation mode; one isolated worktree,
24 authorized changed files; new focused tests only, no existing tests modified;
Windows authorized focused set and Linux relevant subset executed; candidate
not declared accepted; no publication or production action.
