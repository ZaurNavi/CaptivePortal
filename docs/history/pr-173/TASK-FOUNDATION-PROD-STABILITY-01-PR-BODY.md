## TASK-FOUNDATION-PROD-STABILITY-01

Bounded repair of the two production-preflight defects. No Task-04 classification, evidence schema, capture/BPF, TTL, producer identity, concurrency-limit or activation change.

### Exact publication candidate

- Baseline: `fa27c8dedba93b72924b4bf88c7e1aa551ad06ac`
- Baseline tree: `e2521f27c9f91978e381bce202ab3e3c83aa6dad`
- Commit: `0dd481f22f83b0ae6c8c96f7778d2fd544a25038`
- Tree: `6816e73148c91c1e2e778613067a41d8c973c03d`
- Diff: 7 files, 240 additions, 11 deletions.
- Binary/full-index review patch: `C:\CaptivPortal-Lab\artifacts\TASK-FOUNDATION-PROD-STABILITY-01.patch`; 17046 bytes; SHA256 `1b872e29375a5799dbd39e64eaa987783d456ca367baba9df559949604045a99`.

### DEFECT-01: bounded periodic repository health

Periodic maintenance now checks schema/version and singleton generation/allocator metadata, without `quick_check`, integrity PRAGMAs, evidence/health sequence scans or cross-table joins while holding the ingest serialization lock.

Full startup integrity and sequence validation remain before writes are admitted. Explicit offline migration/recovery retains full validation. SQLite corruption errors and invalid runtime metadata still fail closed. Runtime metadata health is deliberately not a full-page integrity claim. Retention chunks, single-writer locking and bounded HTTP ingest slots are unchanged.

Deterministic tests prohibit full integrity operations/evidence reads in runtime health, cover maintenance recovery branches, prove subsequent ingest remains usable, preserve startup corruption rejection and prove metadata corruption disables ingest.

### DEFECT-02: no unbounded diagnostic EVE file in /run

The tracked deployable configuration already contains only the admitted UNIX datagram EVE output. Its exact output block remains unchanged. Deployment instructions explicitly require replacing the installed configuration with the complete socket-only template, rather than retaining a local diagnostic output.

The Suricata unit adds `ReadOnlyPaths=/run` as a fail-closed regular-file-write boundary, including configuration drift. The existing sensor-owned UNIX socket, foreground service, interface, BPF, TLS/QUIC output and network sensor service remain unchanged. Static tests pin the exact output block and service boundary. See the [systemd filesystem namespace contract](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml) for the distinction between regular-file writes and AF_UNIX communication.

Existing production diagnostic bytes have NOT been removed. Installed configuration replacement, cleanup and Linux service/socket verification require a separately authorized Owner operation; no deployment or production access was performed here.

### Coder task-scoped test evidence

Environment: Windows, Python 3.10.11, interpreter `C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe`; isolated publication worktree `C:\CaptivPortal-Lab\coder-foundation-prod-stability-01`. `PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\foundation-stability-pyc`.

Focused repair tests:

```text
python -m pytest -q --basetemp=C:\CaptivPortal-Lab\tmp\foundation-stability-focused-20261003-01 tests/device_fingerprint/test_repository.py tests/device_fingerprint/test_service.py tests/device_fingerprint_sensor/test_deployment_outputs.py
62 passed / 0 skipped / 0 failed
```

Direct Task-01/sensor regression (storage/WAL/migration, API bounded ingest, startup/CLI/config and capture runtime):

```text
python -m pytest -q --basetemp=C:\CaptivPortal-Lab\tmp\foundation-stability-regression-20261003-01 tests/device_fingerprint/test_storage_v2.py tests/device_fingerprint/test_api.py tests/device_fingerprint/test_cli.py tests/device_fingerprint/test_config.py tests/device_fingerprint_sensor/test_runtime.py
158 passed / 0 skipped / 0 failed
```

Syntax and diff checks:

```text
python -m compileall -q app/device_fingerprint/repository.py tests/device_fingerprint/test_repository.py tests/device_fingerprint/test_service.py tests/device_fingerprint_sensor/test_deployment_outputs.py
PASS
git diff --check
PASS
git diff --cached --check
PASS
```

Total: 220 passed, 0 skipped, 0 failed. No full repository suite, Central Lab, performance run, formal Task-04 gate or production test was run. Linux service execution was not tested by these Windows/static tests.

### Publication / Owner boundary

No local databases, generated corpora, run directories, pycache, secrets or acceptance artifacts are committed. This PR is the source repair and Coder focused-evidence handoff for TechLead/Owner review; it does not claim independent Central Lab acceptance or production verification.

MERGE: Owner-only; not performed.
DEPLOY: NO.
PRODUCTION ACCESS / CHANGE / ACTIVATION: NO.
