# TASK-DTI-NI-02A — REPAIR R1 handoff

REPAIR_STATUS=REPAIRED / READY_FOR_TECH_LEAD_SOURCE_REVIEW
P1-01_RESULT=LOCAL_PASS
P1-02_RESULT=LOCAL_PASS

## Identities

- Worktree: `C:\CaptivePortal-NI02A`
- Branch: `feature/dti-ni-02a-ipv4-temporal-authority`
- BASE_HEAD / unchanged HEAD: `701ce630b595a87e9350b826a06ee02eaebc7f9e`
- BASE_TREE: `59425257b1b9ddd557113da158c88d58bfe06bfc`
- Previous reviewed candidate tree: `92eafeee47077aa7a16dba199efbaf9c4fe3cef3`
- NEW_REVIEW_CANDIDATE_TREE: `6348fe5fddb22f597ba8a6e40cf5f96a4d9d73ac`
- Worktree state: DIRTY, intentional uncommitted implementation candidate.
- Actual staged diff: empty. Candidate tree calculated with an external temporary Git index; no commit created.

## FILES_CHANGED_FROM_PREVIOUS_CANDIDATE

```text
app/network_attribution/dhcp_authority.py
app/network_attribution/read_service.py
app/network_attribution/repository.py
app/network_attribution/schema.py
tests/network_attribution/test_authority.py
tests/network_attribution/test_sensor_adapter.py

6 files changed, 240 insertions(+), 9 deletions(-)
```

No additional Sensor edits in R1. All other paths are byte-identical to the previous reviewed candidate. No forbidden production paths changed.

## Repair behavior

P1-01: ordinary transactions no longer checkpoint/truncate. Writer explicitly configures `wal_autocheckpoint=1000`. Combined main/WAL/SHM capacity checks remain before mutation and before commit, with an additional post-commit check for newly appended WAL frames. One maintenance attempt runs after the existing bounded retention operation (at most once per 60 seconds). PASSIVE checkpoint is attempted outside write transactions; incomplete/busy checkpoint is deferred. TRUNCATE is attempted only after PASSIVE reports every frame checkpointed; it uses zero busy timeout and restores the prior timeout. Busy/locked results, including a racing reader, do not fault the recorder. Actual I/O errors and actual capacity exhaustion remain unavailable/fail-closed.

P1-02: schema-contract checks are separated from full storage-integrity scans. Writer startup, including its existing-store read-only probe, retains exact schema/user_version/singleton/foreign_keys/WAL checks and both full integrity PRAGMAs. Each read snapshot still validates the exact schema contract, but performs neither quick_check nor foreign_key_check. No schema caching that would admit a changed/foreign store was introduced.

DHCP authority, coverage, resolution precedence, temporal intervals, retention, default-OFF and Fingerprint isolation semantics unchanged.

## NEW_TESTS

No new test files. Added 10 parameterized test cases to the two existing NI test files:

- R1-A: held independent read snapshot reproduces old TRUNCATE busy; writes succeed and reader snapshot remains valid.
- R1-B: real recorder poll/frame/maintenance with held reader; no permanent fault or unavailable telemetry; persisted ACK resolves.
- R1-C: repeated writes and deferred maintenance under a reader; reclaim after reader release, subsequent writer remains usable.
- R1-C capacity: actual combined-footprint exhaustion rejects further writes and returns read unavailable.
- R1-D: instrument full integrity and SQL traces; five resolves run static checks only; initial/reopened writer retains full scans.
- R1-E: wrong user_version, extra foreign table and missing singleton each fail closed after an earlier successful lookup (3 cases).
- Maintenance error boundary: SQLite busy defers; SQLite I/O error becomes unavailable (2 cases).

## TESTS_EXECUTED / TEST_RESULTS

Windows PowerShell, Python 3.10.11, working directory `C:\CaptivePortal-NI02A`:

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\ni02a-r1-pycache'
python -m pytest -q tests/network_attribution --basetemp C:\CaptivPortal-Lab\tmp\ni02a-r1-focused-02
```

Final exact candidate: **72 passed, 0 failed, 0 skipped**. Earlier intermediate R1 check: 70 passed before adding the two maintenance-error cases.

```powershell
python -m pytest -q tests/device_fingerprint_sensor/test_runtime.py tests/device_fingerprint_sensor/test_dhcp.py tests/device_fingerprint_sensor/test_spool.py tests/device_fingerprint_sensor/test_producer.py tests/device_fingerprint_sensor/test_cli.py --basetemp C:\CaptivPortal-Lab\tmp\ni02a-r1-sensor-01
```

Same minimal Sensor set as previous handoff: **47 passed, 0 failed, 0 skipped**.

Dedicated WSL Ubuntu-22.04 Linux Lab, same focused NI scope (not an official acceptance gate):

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/c/CaptivePortal-NI02A --exec env PYTHONPATH=/mnt/c/CaptivePortal-NI02A PYTHONPYCACHEPREFIX=/tmp/ni02a-r1-pycache /home/zaur_navi/captivportal-lab/perf-venv/bin/python -m pytest -q tests/network_attribution --basetemp /tmp/ni02a-r1-focused-01
```

**72 passed, 0 failed, 0 skipped**.

```powershell
python -m compileall -q app/network_attribution app/device_fingerprint_sensor/cli.py app/device_fingerprint_sensor/runtime.py tests/network_attribution
git diff --check
```

COMPILEALL=PASS
DIFF_CHECK=PASS

No full repository suite, Central Lab, benchmark or production access.

## Complete replacement patch

NEW_PATCH_PATH=`C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-02A-R1_BASE-to-CANDIDATE.patch`

NEW_PATCH_BYTES=92108

NEW_PATCH_SHA256=`af068676761e55caad74286b182130e1c5db87886fb09103c8ac35d87ff685a5`

Binary-capable/full-index patch against original baseline `701ce630b595a87e9350b826a06ee02eaebc7f9e`, not only the R1 delta. Forward application to an external baseline index and reverse application check against the working candidate both PASS.

Full baseline-to-candidate scope: **13 files, 1696 insertions(+), 3 deletions(-)**:

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

## KNOWN_REMAINING_RISKS

- No known remaining blocker in the requested focused scope; Tech Lead acceptance is pending.
- A sufficiently long-held reader can still prevent reclaim until actual configured storage exhaustion; fail-closed on that real exhaustion is intentional, not a checkpoint-contention fault.
- The post-commit capacity guard detects WAL bytes appended by COMMIT. If that append crosses the configured cap, the operation may already be committed when unavailable is raised; subsequent writes are refused. This is detection/fencing of actual exhaustion, not a hard filesystem quota or rollback of a completed commit.
- Reads intentionally do not conduct full storage scans; writer initialization retains those scans. Production-scale capacity/performance and full repository acceptance were not run.

## REPOSITORY_ACTIONS

Commit created: NO
Push completed: NO
PR opened: NO
Merge completed: NO
Deployment completed: NO
Production actions: NO

External patch, handoff and temporary review index created under `C:\CaptivPortal-Lab\artifacts`; candidate edits only in the authorized worktree. No other worktrees modified.

HOLD FOR TECH LEAD SOURCE REVIEW.
