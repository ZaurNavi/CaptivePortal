## TASK-FOUNDATION-PROD-STABILITY-01-FIX1

Bounded deployment follow-up to #173, implementing the exact Linux recovery arrangement supplied by Owner/TechLead.

### Defect and repair

Suricata 8.0.6 validates `default-log-dir` writability at startup. The previous sensor-owned directory and blanket `ReadOnlyPaths=/run` caused the supplied production startup failure.

- `default-log-dir: /run/fingerprint-suricata`
- `RuntimeDirectory=fingerprint-suricata`
- `RuntimeDirectoryMode=0750`
- Removes `ReadOnlyPaths=/run`; no `ReadWritePaths=/run` workaround.
- Preserves exactly one EVE output and its entire admitted UNIX-datagram block.
- No regular EVE output or `diag-eve.json` in deployable configuration.
- Preserves `enp8s0`, `net 192.168.8.0/22`, sensor socket path, `CAP_NET_RAW`, foreground execution and TLS/QUIC extraction.
- Documentation and static deployment tests reflect the corrected arrangement.

No application source, SQLite/evidence schema, Device Fingerprint/classification, TTL, producer identity or Task-04/05/06 semantics changed. PR #173's bounded repository health repair remains unchanged.

### Exact identity / scope

Baseline: `810484e69baa371c4696c3b46654199631538fc4` (main after #173 merge).
Commit: `b53fedb0a56f7be45b31e0ee9d4f1d034a684ef1`.
Tree: `85d7d41e1ad19c079cad0ae819a3fe38a068e242`.

Exactly four modified files; 31 additions / 17 deletions:

```text
deploy/device-fingerprint/README.md
deploy/device-fingerprint/fingerprint-suricata.service
deploy/device-fingerprint/suricata.yaml
tests/device_fingerprint_sensor/test_deployment_outputs.py
```

### Coder focused verification

Windows / Python 3.10.11. Interpreter: `C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe`.
Worktree: `C:\CaptivPortal-Lab\coder-foundation-prod-stability-01-fix1`.
`PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\foundation-stability-fix1-pyc`.

```text
python -m pytest -q --basetemp=C:\CaptivPortal-Lab\tmp\foundation-stability-fix1-focused-20261003-01 tests/device_fingerprint/test_repository.py tests/device_fingerprint/test_service.py tests/device_fingerprint_sensor/test_deployment_outputs.py
62 passed / 0 skipped / 0 failed

python -m pytest -q --basetemp=C:\CaptivPortal-Lab\tmp\foundation-stability-fix1-regression-20261003-01 tests/device_fingerprint/test_storage_v2.py tests/device_fingerprint/test_api.py tests/device_fingerprint/test_cli.py tests/device_fingerprint/test_config.py tests/device_fingerprint_sensor/test_runtime.py
158 passed / 0 skipped / 0 failed

python -m compileall -q tests/device_fingerprint_sensor/test_deployment_outputs.py
PASS

git diff --check
PASS
git diff --cached --check
PASS
git diff --check HEAD^ HEAD
PASS
```

Total: 220 passed / 0 skipped / 0 failed. No full suite, Central Lab or formal acceptance gates were run.

### Linux / production evidence boundary

The TASK supplies production-proven `suricata -T` and startup PASS, no regular EVE output/diagnostic file, sensor ready, spool 0 and Suricata active with this arrangement. Those are Owner/TechLead-supplied observations, not Linux tests or production operations performed by Coder. Windows/static tests do not independently execute the Linux unit.

No deployment, production access/action, activation or cleanup was performed. No production state/log/database files are committed.

MERGE: NO; Owner-only.
DEPLOY: NO.
