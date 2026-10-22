# TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1 — bounded T05 disposition required

STATUS=BLOCKED_T05_PREFLIGHT_VIRTUAL_DEVICE_GUARD
IMPLEMENTATION_ACCEPTED=NO
COMMIT/PUSH/PR/MERGE/DEPLOY=NO
PRODUCTION_ACTION=NO

## Exact blocker / requested TechLeadJR decision

TASK §5 requires `no master/bridge/bond` and preservation of all safety gates, but authorizes capture.py only to remove the exact `enp8s0` denial. Actual `InterfacePreflight._validate()` checks only `<selected>/master` for virtual/master relationship. No check rejects a selected device which itself has `<selected>/bridge` or `<selected>/bonding` and otherwise satisfies every existing guard.

Offline synthetic reproductions for both device kinds **FAIL expected rejection**:

```text
tests/device_fingerprint_sensor/test_deploy_preflight.py::test_T05_selected_bridge_or_bond_must_be_rejected[bridge]
tests/device_fingerprint_sensor/test_deploy_preflight.py::test_T05_selected_bridge_or_bond_must_be_rejected[bonding]
Failed: DID NOT RAISE SensorPreflightError
2 failed in 0.26s
```

Fixture: selected `enp1s0`, operstate UP, `bridge` or `bonding` directory, no master, no L3/default route/forwarding/DHCP/active NM profile. Mocked ip/netplan/systemctl and synthetic sys/proc only; no real interface/socket/network. Alternative interface names are now valid claims, but a fixed name alone is not evidence of physical device type.

Request: authorize a narrowly bounded additional guard **in the already allowlisted capture.py** rejecting existing or symlink `<selected>/bridge` and `<selected>/bonding`, while preserving current master and every other check. This exceeds the directive's literal `remove only the fixed-name denial`, so Coder has NOT implemented it. Alternatively, explicitly clarify whether “bridge/bond” means membership only; do not silently waive the failing safety requirement. No new production file, capture filter or architecture redesign proposed.

## Preserved dirty implementation / chain of custody

- Worktree: `/home/zaur_navi/captivportal-lab/worktrees/captivprod-deploy-config-02`
- Branch: `task/captivprod-deploy-config-02`
- Base HEAD: `84b80376b13002d435be28eec98b91b9cbf71c63`
- Base TREE: `fda2f2dad7c1f9c89d383ef0bef63f8aebfc93b8`
- Clean at start; HEAD remains base, final worktree DIRTY / UNCOMMITTED.
- origin/main re-fetched at blocker handoff: same exact baseline HEAD/TREE.
- Current **partial, NOT accepted** candidate tree: `08cab06eac76764b932c5ce955e30959f9aeaf62`.
- Tree generated through external temporary Git index, no commit or branch rewrite. The two failing tests are deliberately included, not skipped/xfail.
- Full partial patch: `C:\CaptivPortal-Lab\handoffs\captivprod-deploy-config-02-20261015\PARTIAL-BLOCKED-T05.patch`
- Bytes: 67896
- SHA256: `2f5a578a658bf7097207ad834da29bb6024df53e21039fbd1672f9da8ec0dfdd`

Exact 15-file inventory:

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

Only three production files changed. Models/dataclass shapes, runtime, producer, cli, normalizer, spool, filter and receiver remain byte-identical to base. Static AST proves capture.py differs ONLY by removal of its initial fixed-name check; no other preflight or RawCapture code changed. No source/binding/classifier, SQL, Auth/CAPPORT, systemd, Suricata, NPM or production edits.

## Work already implemented (not an acceptance claim)

Strict Sensor deployment claims: bounded safe NIC, private/literal Core destination and canonical port, exact direct-TLS URL, machine IDs/Site, canonical bounded nonoverlapping IPv4 CIDRs, independent canonical unicast DHCP authorities. Legacy full defaults and disabled Wave-2 behavior preserved; Sensor remains independent of main config/Settings.

Portal isolated claims: IDs/Site, IPv4 guest scopes, bounded exact UTF-8 SSIDs, direct-TLS URL and external absolute Linux paths. Existing queue/batch/coalescing/timeouts/cooldowns remain pinned; original BATCH_SIZE=51 rejection preserved. Both URLs reject ambiguous numeric authorities, userinfo, escapes, query/fragment/alternate paths; only a single terminal slash normalizes. No credential/configuration report prints secrets.

Former fixed-authority negative cases for enp1s0 and custom IDs/Site reclassified into explicit positive claim tests, not deleted without replacements. Existing truly invalid vectors remain negative. Docs preserve all legacy defaults and distinguish parsing, real receiver/token/peer/TLS registration, F-B1/clock/emitter admission, clean spool/cutover and independent Suricata/readiness/activation gates.

## Focused evidence T01–T10

| Gate | Local evidence / disposition |
| --- | --- |
| T01 | Entire Sensor/Portal dataclass snapshots vs literal legacy defaults, disabled bad overrides ignored, Wave-2 invalid booleans still reject. PASS in initial scope. |
| T02 | Typed custom Sensor fields, independent public-test-range DHCP source/option54 values, no socket or filesystem I/O in parser. PASS. |
| T03 | Custom Portal config, UTF-8 SSID byte bounds, optional missing SSID and frozen tuning fields. PASS. |
| T04 | Both URL policies, numeric aliases, CIDR hostbits/duplicates/overlaps, wrong types/empty/control, NIC/IDs/Site/Core/ports and external paths. PASS in initial scope. |
| T05 | Alternate clean NIC, existing negative L3/route/forwarding/DHCP/NM/tools/proc guards and selected AF_PACKET target PASS. **Selected bridge/bond rejection FAIL (2 cases)**; scope decision required. |
| T06 | Configured TCP endpoint, bounded retries/timeouts, no HTTP method, no runtime on unreachable Core. PASS. |
| T07 | Mock transport exact producer/Site/source/event/CA/bearer tuple and 401/403 no fallback. PASS locally; actual receiver admission/denial remains independent QA. |
| T08 | Original trusted CA injection, credential file handling, TLS exceptions and no ACK on failure verified with mocks/disposable files. Actual good/bad CA/SAN/expiry direct-TLS receiver proofs remain TechLeadJR-owned. |
| T09 | Configured normalized evidence/source health, original disk spool unchanged by parser/new claims; no relabel. Operational activation over nonempty spool remains HOLD. |
| T10 | External Portal and CAPPORT login, disabled/invalid/delivery-failed optional producer: existing 200/session/run/submission and exact mock controller calls unaffected. PASS in expanded focused scope. |

No cross-module/full/official gate claims; no carryover of DEPLOY-CONFIG-01 exception or its old QA results.

## Commands / results / retained evidence

Environment: WSL Ubuntu 22.04, Python 3.10.12, pytest 9.1.1, SQLite 3.37.2. Interpreter `/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python`, SHA256 `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae`.

All commands from task worktree with external `PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/tmp/captivprod-deploy-config-02-pycache`, same qualified interpreter, `-m pytest -q -p no:cacheprovider`:

1. `tests/device_fingerprint_sensor/test_config.py tests/device_fingerprint_sensor/test_runtime.py tests/device_fingerprint_sensor/test_cli.py tests/device_fingerprint_sensor/test_producer.py tests/device_fingerprint_sensor/test_deploy_config.py tests/device_fingerprint_sensor/test_deploy_preflight.py tests/device_fingerprint_portal/test_config.py tests/device_fingerprint_portal/test_privacy.py tests/device_fingerprint_portal/test_producer.py tests/device_fingerprint_portal/test_deploy_config.py tests/device_fingerprint_portal/test_deploy_isolation.py` → **260 PASS**, 4.58s, initial scope before expanded CAPPORT/TLS and blocker fixtures. `focused.log/xml` retained.
2. `tests/device_fingerprint_portal/test_deploy_isolation.py tests/device_fingerprint_sensor/test_producer.py::test_T08_sensor_tls_failure_never_acknowledges` → **12 PASS**, 0.73s after T10 CAPPORT/TLS expansion. `isolation-expanded.log/xml` retained.
3. `tests/device_fingerprint_sensor/test_deploy_preflight.py::test_T05_selected_bridge_or_bond_must_be_rejected` → **2 FAIL**, 0.26s. Full tracebacks in `preflight-blocker.log/xml`. No failures hidden, skips or xfails added.

These are per-run results on successive focused drafts, not a full PASS claim on the final blocked tree. The platform-independent dangling-master fixture was also refined to mock is_symlink rather than require Windows symlink privileges; no further execution claimed for that fixture after HOLD.

`compileall -q` of all changed Python source/test files with external bytecode output: PASS. `git diff --check`: PASS. No public/private test certificates or real credentials added. No full regression, Central Lab, production test, SSH, deployment, restart or source activation.

Stop pending TechLeadJR bounded amendment/disposition; dirty draft and all evidence preserved. Suggested eventual PR subject remains `Deploy Config 02: configurable Device Fingerprint sensor and portal producers`, but COMMIT/PUSH/PR are HOLD.
