# PHASE1-R1-REPAIR-HANDOFF

TASK=TEST-GATE-PLATFORM-01
STATUS=READY_FOR_TECH_LEAD_REPAIR_REVIEW
P1_01=REPAIRED
P1_02=REPAIRED_AT_DEPENDENCY_PREPARATION_BOUNDARY
MANIFEST=DRAFT / NOT ADMITTED
ENVIRONMENT_LOCK=DRAFT / NOT ADMITTED
GATE_IDENTITY=TEST-GATE-PLATFORM-01/P1-R1-v2

This is preparation and source review only, not an official acceptance result and not historical V7 strict PASS.

## Frozen boundaries

BASE_HEAD=51deead342bd821b5c46fb75a7ceef37bef63e7c
BASE_TREE=7b6cfa20c23c097e87059ca12a593f697f0a36a2
NI03_ACCEPTED_TREE=8ed141f0184d65e6fd8d4d3a06adadc5940497e3
LAB_ONLY_COMMIT=57b35ee7d45d2e780230fae7de48071b9645b061
V7_RUNNER_SHA256=45d3b37150a2c3b3d3e95460b2a1c6cab8d97aa333c3d3e0cd3507ef1c994f77

C:/CaptivPortal-Lab/coder-work remains clean at the exact Lab commit/tree.
C:/CaptivPortal-Lab/coder-dti-ni-03 remains the original dirty draft. Read-only comparison checked all 24 accepted-delta paths against the accepted blobs: zero mismatches and zero unexpected tracked/untracked source paths.
C:/CaptivPortal-Lab/coder-test-gate-platform-01 remains at BASE_HEAD/BASE_TREE, dirty ONLY with the four accepted test fixes. All four blobs match the accepted infrastructure composition mapping; no R1 edit to any of them.
Native baseline /home/zaur_navi/captivportal-lab/test-gate-platform-01-baseline remains clean at BASE_HEAD/BASE_TREE.
No real index, repository source, SQL, planner assertions, run.py, V7 runner, production or existing perf-venv was changed.

## Complete replacement source files and exact inventory

All eight external infrastructure files changed relative to the archived R0 source. Complete files are linked below; no snippets or omitted helpers.

| Complete file | Bytes | SHA256 |
|---|---:|---|
| [compare-gate-evidence-v1.py](C:/CaptivPortal-Lab/test-gate-platform-01/compare-gate-evidence-v1.py) | 8658 | 01f779a1b21158d550df211d8162a79caf36e1e6161f637681f3c99824b46ba3 |
| [gate-environment-lock-v1.json](C:/CaptivPortal-Lab/test-gate-platform-01/gate-environment-lock-v1.json) | 9803 | 61ecef6851915b12cb256d5ed09b3956a3ddfb926e4eefe4ad710e0debcab3b1 |
| [gate-preflight-v1.py](C:/CaptivPortal-Lab/test-gate-platform-01/gate-preflight-v1.py) | 13660 | baeeab562ec56f40c06e8a8a8c6042757692f9c4c3c725379cad48e2dfc0fc1f |
| [platform-manifest-v1.json](C:/CaptivPortal-Lab/test-gate-platform-01/platform-manifest-v1.json) | 255126 | ccca746f45ad1e22ee82add7b4b02598b6a0e7f6f5954a8930a873b37ca31b07 |
| [pytest_platform_contract.py](C:/CaptivPortal-Lab/test-gate-platform-01/pytest_platform_contract.py) | 21538 | 3cab7cc7550190a44b14456ed2c32af266d1aaa6df71715b433d410d5c63dd0f |
| [run-linux-platform-gates-v1.sh](C:/CaptivPortal-Lab/test-gate-platform-01/run-linux-platform-gates-v1.sh) | 600 | 3885905b6b5333ca3c1284d2f1901922705bad787af68695476e229c8b037438 |
| [run-platform-gates-v1.cmd](C:/CaptivPortal-Lab/test-gate-platform-01/run-platform-gates-v1.cmd) | 561 | 3265bf9d6c081e152c81ea0edeb38d678e6e810d90abd27ef9094dfd7f83f736 |
| [test_gate_platform_contract.py](C:/CaptivPortal-Lab/test-gate-platform-01/test_gate_platform_contract.py) | 28960 | 17c800dc90f25316b479f8f4558b6b2c69a4242f2dc93c13cfdc3b6a0e801234 |

Machine-readable current/archived identities:
[FILE-INVENTORY](C:/CaptivPortal-Lab/artifacts/TEST-GATE-PLATFORM-01-PHASE1-R1-FILE-INVENTORY.json).

Before editing, all eight original source files were copied byte-for-byte into C:/CaptivPortal-Lab/artifacts/TEST-GATE-PLATFORM-01-PHASE1-R0-SOURCE/.
All eight archived hashes still match the prior inventory. Eight previously retained evidence/patch/V7 items also remain hash-identical.
Old environment/evidence versions were not overwritten. New R1 evidence has separate filenames.

## P1-01: exact native skip precedence

The closed manifest is schema v2 under the independent P1-R1-v2 gate identity. It retains the same 219 node IDs, ordering, Linux counterparts, causal justifications, source digests and retained evidence mappings.

Exact classes:
- 186 PLUGIN_ASSIGNED transfers: original skip/skipif/xfail marker inventory must be empty; plugin creates the approved_linux_transfer skip.
- 33 EXISTING_NATIVE transfers: exact per-ID source SHA, mechanism, source line, condition expression and original reason are pinned.
- Inspection shows these 33 are 31 skipif decorators plus 2 early runtime pytest.skip OS guards, not 33 decorators. Existing source semantics are preserved, not rewritten.

For the 31 skipif cases the plugin deliberately adds its own skip without removing the original skipif. Classification accepts the actual original skipif reason only when source, exact node ID, AST guard, original marker snapshot and phase outcomes match the contract.
For the two early runtime guards, the plugin does not substitute a generic setup skip; the original guard runs and the exact call-phase skip must match its pinned reason.

The ledger retains transfer_binding containing node ID, source SHA, typed skip contract and original skip-marker snapshot. Both reported reason and exact setup/call/teardown phase shape are checked. A failed phase, XFAIL/XPASS, unexpected marker/skip/reason, source drift, unknown ID, missing counterpart or protected ID cannot become an admitted platform transfer.
The composite validator still requires an actual Linux PASS for every exact transferred ID. Historical Linux evidence is retained; no new real Linux admission PASS is claimed here.

The exact protected-six list remains:
- tests/analytics/test_current_traffic.py::test_sql_integrity_aggregates_reject_corrupt_rate_and_null_values[wired_download_mbps-inf-bad_rate_count]
- tests/test_auth_retry_frontend.py::test_lost_retry_response_reconciles_active_run
- tests/visitor_registry/test_device_registry_worker.py::test_long_full_audit_runs_in_worker_and_does_not_block_start
- tests/visitor_registry/test_device_registry_worker.py::test_start_exposes_initializing_until_full_audit_finishes[ready]
- tests/visitor_registry/test_device_registry_worker.py::test_start_exposes_initializing_until_full_audit_finishes[stopping]
- tests/admin_web/test_home_health.py::test_unavailable_analytics_is_one_component_not_health_503

The actual manifest remains DRAFT with approval=null. No wildcard/module-level transfer was added and no real Windows transfer was enabled.

## Focused infrastructure verification

Final command:
C:/CaptivPortal-UI-Preview/.venv/Scripts/python.exe -m pytest -q C:/CaptivPortal-Lab/test-gate-platform-01/test_gate_platform_contract.py --basetemp=C:/CaptivPortal-Lab/tmp/tgp01-r1-selftests-03 -o cache_dir=C:/CaptivPortal-Lab/tmp/tgp01-r1-cache-03 --junitxml=C:/CaptivPortal-Lab/artifacts/TEST-GATE-PLATFORM-01-R1-selftests-03.xml

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1; pycache and temporary fixtures are external.
RESULT=107 passed / 0 failed / 0 skipped (28.34 seconds).
[Final JUnit](C:/CaptivPortal-Lab/artifacts/TEST-GATE-PLATFORM-01-R1-selftests-03.xml)
SHA256=c4d9e5ecc333c59bb3b6d6bf176aa65be311ec7c057399c1d439fc7e44761dfa

Real subprocess pytest scenarios use ONLY disposable synthetic source, explicitly load -p pytest_platform_contract and separately labelled synthetic approval; they never load the repository test suite.
The positive skipif scenario verifies both original skipif and plugin-added skip are present and retains the original actual reason.
Positive early-runtime-guard scenario also passes.
Negative scenarios verify wrong approved reason, wrong actual outcome reason, wrong marker, unauthorized node, protected node, protected transfer in manifest, failed teardown, unexpected xfail marker and missing Linux counterpart. Assertions check the intended error, not merely any nonzero exit.
Additional synthetic origin negatives cover virtualenv prefix/base_prefix drift despite an identical underlying interpreter binary.
The 219 IDs, protected-six, all original source/evidence hashes and 33 native AST guards are checked in a focused self-test.

Preserved R1 attempt history:
- selftests-01.xml: 102 PASS / 3 FAIL due to missing tests package in the NEW synthetic integration fixture. Production/source origin rejection worked correctly. The synthetic fixture only was corrected.
- selftests-02.xml: 105 PASS.
- selftests-03.xml: 107 PASS after adding precise failure assertions and virtualenv origin negatives.

[Verification evidence, synthetic ledgers and hash identities](C:/CaptivPortal-Lab/artifacts/TEST-GATE-PLATFORM-01-R1-VERIFICATION-EVIDENCE.json)
SHA256=19ef163978de722b3c7378e7e84b31d05b45ba7286582bb5504df5da17167ea9

Static checks:
- external infrastructure compileall: PASS; pycache external.
- Linux launcher bash -n: PASS; LF bytes verified.
- manifest closed schema / all 219 IDs / protected-six: PASS.
- all seven environment-lock infrastructure SHA bindings: PASS.
- accepted test-only worktree git diff --check: PASS.
No repository/full/cross-module test, V7 or official gate was run.

## P1-02: approved isolated Linux dependency preparation

Owner / Tech Lead explicitly approved this target and requirements-dev installation, including transitives:
 /home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv

Preconditions verified before creation: target ABSENT; baseline requirements-dev.txt and included requirements.txt PRESENT.
Only /usr/bin/python3.10 -m venv with the full target path was used.
Installation used the TARGET/bin/python, not a global/system Python package install.
No apt/system configuration action was needed or performed.

Commands:
1. /usr/bin/python3.10 -m venv /home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv
2. env -i HOME=/home/zaur_navi PATH=/usr/bin:/bin LANG=C.UTF-8 PIP_CONFIG_FILE=/dev/null PIP_CACHE_DIR=/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/pip-cache PYTHONNOUSERSITE=1 /home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python -m pip install -r /home/zaur_navi/captivportal-lab/test-gate-platform-01-baseline/requirements-dev.txt
3. /home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python -m pip check

INSTALL=EXIT 0
PIP_CHECK=EXIT 0 / No broken requirements found.
All five mandatory requirements in the recursive dev closure satisfy their version specifiers: flask, requests, tzdata, cryptography and pytest.
cryptography=50.0.2
tzdata=2026.5

Python=3.10.12
SQLite=3.37.2
INTERPRETER=/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python
INTERPRETER_SHA256=a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae
PREFIX=/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv
BASE_PREFIX=/usr

Windows comparison remains Python 3.10.11 / SQLite 3.40.1.
The full package/version inventory, SQLite compile options, sys.path, interpreter identity and requirements-file hashes for both platforms are in:
[Dependency evidence](C:/CaptivPortal-Lab/artifacts/TEST-GATE-PLATFORM-01-R1-DEPENDENCY-EVIDENCE.json)
SHA256=9e7fb44d4405065beae54771ac28048b51255d943be21ea181e8aa0ab3a0f368
[Installation output](C:/CaptivPortal-Lab/artifacts/TEST-GATE-PLATFORM-01-R1-DEPENDENCY-INSTALL.log)

The new environment lock pins the selected virtualenv executable path and sys.prefix/base_prefix in addition to the binary digest, Python, SQLite/options and full package set. This prevents confusing the new qualified venv with old perf-venv merely because both symlink the same /usr/bin/python3.10.
The preflight inspects the complete requirements-dev include closure and rejects incomplete/different requirements bindings before approved execution.
This is dependency qualification/preparation, NOT Linux full-gate/admission qualification. Any runtime/profile approval still belongs to Tech Lead.
Existing perf-venv package inventory and interpreter SHA were rechecked against the archived lock and are unchanged. Global packages, existing repositories and production were not modified.

## Accepted test-only patch — unchanged, complete replacement delivery

[Complete four-file replacement patch](C:/CaptivPortal-Lab/artifacts/TEST-GATE-PLATFORM-01-TEST-ONLY.patch)
BYTES=5850
SHA256=4a3ab3ff24bf4027d31b283652e23c9ce3a3c0f378e44937d1a15002f0be9c16
4 files changed / 11 additions / 11 deletions:
- tests/admin_web/test_home_traffic.py
- tests/device_fingerprint_portal/test_client_hints_probe.py
- tests/test_capport_routes.py
- tests/test_proxy_headers.py

No R1 change to this patch or these files. Previous focused fixture result=6 PASS is historical Phase-1 evidence, not an R1 rerun.

## SQLite disposition — unresolved HOLD, unchanged

[Exact retained SQLite diagnostic](C:/CaptivPortal-Lab/artifacts/TEST-GATE-PLATFORM-01-SQLITE-DIAGNOSTIC.json)
Previous diagnostic only: Windows SQLite 3.40.1 materializes validated_cycles once in both queries; native Linux SQLite 3.37.2 materializes it zero times, with inlined/repeated scans.
The new isolated venv uses the same native SQLite 3.37.2. No new EXPLAIN/test diagnostic was executed during R1.
Planner test assertions, SQL and production dependencies remain unchanged.
Linux reference SQLite 3.40.1 was not installed or qualified. A reference pin is not native Linux acceptance.
Required separate Tech Lead disposition remains: native physical-planner contract and any isolated reference-build qualification.

## Proposed lineage — unchanged, not new acceptance

| Layer | Tree |
|---|---|
| Original baseline | 7b6cfa20c23c097e87059ca12a593f697f0a36a2 |
| Original accepted NI-03 | 8ed141f0184d65e6fd8d4d3a06adadc5940497e3 |
| Baseline + accepted four-test delta | d015f4387ad85e35175828aa7308baf3ff2ba94a |
| NI-03 + identical four-test delta | ce527d665ab842fb6e7dd2dc4b78a3b0901a1c21 |

[Composition lineage / exact production blob mapping](C:/CaptivPortal-Lab/artifacts/TEST-GATE-PLATFORM-01-COMPOSITION-LINEAGE.json)
No new composition or commit was created during R1. Original production delta and proposed lineage are unchanged. Combined trees are not relabelled as the original NI03 accepted tree.

## Remaining admission blockers

1. Separate exact 219-ID manifest approval, now including exact native skip contracts.
2. Review/approval of independent P1-R1-v2 runtime/profile and updated environment lock.
3. Freeze exact baseline/candidate collections, including NI-03 added tests, and approve the proposed composed-tree lineage.
4. Owner/Tech Lead full Windows/Linux collection/outcome and admission execution is still pending. Synthetic self-tests do not substitute for mandatory Linux coverage or protected-six real PASS.
5. SQLite native planner disposition remains HOLD.
6. Historical full-order Linux startup/artifact-identity failures still need clean native Git full-order evidence from Owner/Tech Lead; no run.py/artifact checks were disabled.

COMMIT=HOLD
PUSH=HOLD
PR=HOLD
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
NI03_SOURCE_MODIFICATION=NO
V7_RUNNER_MODIFICATION=NO
OFFICIAL_GATE_RUN=NO
FULL_REPOSITORY_TESTS_RUN=NO
NEXT_ACTION=TECH_LEAD_REPAIR_REVIEW
