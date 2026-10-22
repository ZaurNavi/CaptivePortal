# TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1 — D02-02 / T05 FIX

STATUS=READY_FOR_TECHLEADJR_INDEPENDENT_QA

## Identity and delivery

- Worktree: `/home/zaur_navi/captivportal-lab/worktrees/captivprod-deploy-config-02`
- Branch: `task/captivprod-deploy-config-02`
- HEAD remains `84b80376b13002d435be28eec98b91b9cbf71c63`.
- Base tree: `fda2f2dad7c1f9c89d383ef0bef63f8aebfc93b8`.
- Previous partial tree: `08cab06eac76764b932c5ce955e30959f9aeaf62`.
- New candidate tree: `a787a5ad842aa72189423e0d0940567b31b1b953`.
- Working tree: DIRTY / UNCOMMITTED, preserved; no branch/history rewrite.
- Full replacement patch: `C:\CaptivPortal-Lab\handoffs\captivprod-deploy-config-02-t05fix-20261015\TASK-CAPTIVPROD-DEPLOY-CONFIG-02-T05FIX.patch`.
- Patch bytes: **69323**.
- Patch SHA256: **4762fe3e30a326cdd658f1da467dfb6c9232dd1fee39c0f3c9f17b79b4fe7600**.
- Serialization: `git diff --binary --full-index --output=<patch>` against unchanged HEAD, including all four intent-to-add test files.
- Reverse apply check: PASS.
- Reconstruction: patch applied to a fresh external index initialized from exact base HEAD; `git write-tree` reproduced `a787a5ad842aa72189423e0d0940567b31b1b953`. No commit was created; real index was not used for staging the candidate.

The original partial patch, old failing logs and QA evidence remain preserved in their existing directories. This is a new replacement artifact, not a rewrite of historical evidence.

## Exact bounded repair

Only two files differ from the reviewed partial candidate (18 added lines, zero removals):

1. `app/device_fingerprint_sensor/capture.py`: four-line `bridge` / `bonding` loop in `InterfacePreflight._validate()`. Each marker rejects when `exists()` OR `is_symlink()`, including dangling symlinks, through existing `_fail()` with `capture_interface_unavailable`.
2. `tests/device_fingerprint_sensor/test_deploy_preflight.py`: four additional parametrized symlink/dangling-link regression cases, exact safe error assertion. Portable filesystem-property fixtures do not require Windows symlink privileges. The two existing directory-rejection tests remain unchanged.

The existing `master` check is unchanged. Removing only the newly added four-line loop yields capture.py byte-for-byte identical to the preceding partial tree. All other preflight checks, failure handling, AF_PACKET, selected-interface binding and frozen filter remain unchanged. All other 13 partial-candidate files are byte-identical to that partial tree.

## Complete BASE-to-candidate inventory

15 files, 888 insertions(+), 51 deletions(-). Exactly three production files, as originally authorized:

```text
.env.example
app/device_fingerprint_portal/config.py
app/device_fingerprint_sensor/capture.py
app/device_fingerprint_sensor/config.py
docs/configuration.md
docs/modules/device-fingerprint-portal.md
docs/modules/device-fingerprint.md
tests/device_fingerprint_portal/test_deploy_config.py
tests/device_fingerprint_portal/test_deploy_isolation.py
tests/device_fingerprint_sensor/test_cli.py
tests/device_fingerprint_sensor/test_config.py
tests/device_fingerprint_sensor/test_deploy_config.py
tests/device_fingerprint_sensor/test_deploy_preflight.py
tests/device_fingerprint_sensor/test_producer.py
tests/device_fingerprint_sensor/test_runtime.py
```

New test files relative to base: both Portal `test_deploy_*` files and Sensor `test_deploy_config.py`, `test_deploy_preflight.py`. All other listed test files are modified existing tests. No other tracked/untracked repository paths changed. Full per-file byte sizes and SHA256 values are in `verification.json`.

## Focused Linux QA

Environment: WSL Ubuntu 22.04; Python 3.10.12; pytest 9.1.1; SQLite 3.37.2. Interpreter:
`/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python`

Interpreter SHA256: `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae`.

Exact focused command (native Linux shell, from task worktree):

```bash
export PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/tmp/captivprod-deploy-config-02-pycache
/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/device_fingerprint_sensor/test_config.py \
  tests/device_fingerprint_sensor/test_runtime.py \
  tests/device_fingerprint_sensor/test_cli.py \
  tests/device_fingerprint_sensor/test_producer.py \
  tests/device_fingerprint_sensor/test_deploy_config.py \
  tests/device_fingerprint_sensor/test_deploy_preflight.py \
  tests/device_fingerprint_portal/test_config.py \
  tests/device_fingerprint_portal/test_privacy.py \
  tests/device_fingerprint_portal/test_producer.py \
  tests/device_fingerprint_portal/test_deploy_config.py \
  tests/device_fingerprint_portal/test_deploy_isolation.py \
  --junitxml=/mnt/c/CaptivPortal-Lab/handoffs/captivprod-deploy-config-02-t05fix-20261015/focused.xml
```

**Result: 271 passed in 1.89s; 0 failures, 0 errors, 0 skips.** Full output in `focused.log`; per-case results in `focused.xml`. The complete current 11-file suite was executed, not just the repaired cases. The previous 265 passing cases remain passing; both previous T05 failures now pass; four new link-state cases pass.

### Separate T05 proof

The focused suite contains **33 T05 cases**, all PASS:

- Safe alternate `enp1s0`: ACCEPT only after the complete existing no-L3 preflight.
- Existing 26 unsafe conditions: REJECT (missing/down device, master directory/dangling-master property, IPv4/IPv6 addresses/routes/forwarding, DHCP configuration/client processes, active NetworkManager and tool/proc errors).
- Existing `[bridge]`, `[bonding]` directory cases: REJECT.
- Four new cases: bridge/bonding symlink and dangling symlink: REJECT with exact generic error.

Additionally, `verify_t05_handoff.py` executed **seven native Linux synthetic filesystem checks** outside Git, with actual directories and actual symlinks (not simulated symlink properties):

| Synthetic selected NIC state | Outcome |
| --- | --- |
| bridge directory | REJECT |
| bonding directory | REJECT |
| bridge symlink to existing directory | REJECT |
| bonding symlink to existing directory | REJECT |
| dangling bridge symlink | REJECT |
| dangling bonding symlink | REJECT |
| ordinary alternate NIC, UP, no L3 | ACCEPT |

All six unsafe states fail through the existing guard before any mocked external command, with exact `SensorPreflightError("capture_interface_unavailable")` and no wrapped unexpected exception. Actual marker `exists()` / `is_symlink()` properties were asserted. Real network interfaces, raw sockets, live network configuration and production were not accessed. Test-created disposable synthetic roots were automatically cleaned up.

Native proof + static verification command:

```bash
PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/tmp/captivprod-deploy-config-02-pycache \
/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python \
/mnt/c/CaptivPortal-Lab/handoffs/captivprod-deploy-config-02-t05fix-20261015/verify_t05_handoff.py
```

Result: exit 0; `verification.log` and `verification.json` retain all 33 exact pytest names, all seven native outcomes, environment, unchanged-file checks and source hashes. These seven checks are separate supplemental proof, not added to the 271 pytest count.

## Static and security-boundary verification

- `compileall -q` on all **11 changed Python files**, using the same interpreter and external bytecode prefix: PASS (exit 0). `compileall.log` is empty because there are no diagnostics. Scope: the three changed production files and eight changed/new test files listed above.
- `git diff --check`: PASS, no exceptions.
- Exact 15-file allowlist: PASS.
- Exactly three changed production paths: PASS. Current repair touches only capture.py among them.
- 13 other partial-candidate file byte comparisons: PASS.
- Other preflight/capture source byte comparison after removing the exact new loop: PASS.
- Sensor/Portal models/runtime/producer, Sensor cli/normalizer/spool/frozen capture filter, main config/settings/run.py and Evidence receiver api/config/service/repository/models/schema compared byte-for-byte to base: PASS. Full list retained in `verification.json`.
- No schema, SQL, systemd, AF_PACKET implementation, BPF or receiver identity/security change.
- Bounded added-line secret-pattern inspection: no private-key blocks or known AWS/GitHub/GitLab credential token shapes found. New repair contains only marker names, error assertion and synthetic test paths; no credential material. No real secrets/certificates/private keys added. This is a bounded inspection, not a claim that an arbitrary-secret scanner proves absence of every possible secret.
- Existing configured-tuple, TLS/CA/bearer, 401/403 no-fallback, no-ACK-on-TLS-error, provenance/spool and Auth/CAPPORT isolation tests are included and PASS. Actual receiver admission and real-certificate release/security proofs remain independent QA responsibilities.

## T01–T10 local disposition

| Gate | Current focused evidence |
| --- | --- |
| T01 | Defaults/disabled snapshots and Wave-2 boolean validation: PASS. |
| T02 | Strict typed custom Sensor claims: PASS. |
| T03 | Strict custom Portal claims, optional SSID and frozen tuning: PASS. |
| T04 | Malformed values/URLs/identities/CIDRs/ports/paths: REJECT as expected. |
| T05 | Previous blocker corrected; all 33 focused cases + seven native supplemental checks: PASS. |
| T06 | Configured bounded TCP readiness, no HTTP reinterpretation: PASS. |
| T07 | Configured identity tuple and denial/no-fallback mocks: PASS; independent receiver admission pending. |
| T08 | CA/credential/TLS-error/no-ACK focused cases: PASS; real direct-TLS certificate matrix pending. |
| T09 | Configured provenance and unchanged old spool behavior: PASS locally; operational lineage/activation remains HOLD. |
| T10 | Optional Producer disabled/invalid/delivery-failed guest Auth/CAPPORT isolation: PASS in authorized focused scope. |

## Remaining ownership and actions

Local T05 blocker is repaired; this is NOT a release/production acceptance claim. Independent TechLeadJR QA, mandatory release/security gates and official Windows/Linux full gates are pending and were not run by Coder. DEPLOY-CONFIG-01 acceptance exception is not carried over. No full/Central regression was run. No live NIC attachment, receiver registration, source admission or feature activation performed.

Agent execution summary: applied only approved guard and four regressions; ran exact focused suite; verified native synthetic link handling, static scope and preserved contracts; exported full replacement patch and reconstructed exact candidate tree through external indexes. External proof scripts/logs/index files remain outside the repository.

```ini
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
SERVICE_RESTART=NO
PRODUCTION_ACTION=NO
CODER_HOLD=YES
NEXT_ACTION=TECHLEADJR_INDEPENDENT_QA
```
