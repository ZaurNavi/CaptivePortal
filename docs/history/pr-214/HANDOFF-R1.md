# TASK-TEST-GATE-PLATFORM-COMPAT-01 — local implementation handoff R1

Date: 2026-10-15. Coder implementation/focused evidence only. **Independent acceptance and full gates remain PENDING TECH LEAD.**

## Exact candidate

```ini
TASK=TASK-TEST-GATE-PLATFORM-COMPAT-01
IMPLEMENTATION_BASE_HEAD=7e84bc563f1b6dd3d72da66ae25849d9a7d96540
IMPLEMENTATION_BASE_TREE=ea664b1d49ace86fc8a0c4ab2fc52945531e574a
CANDIDATE_TREE=f77e48f85950ddc8f0b5962829088a6fa2a6fe5e
WORKTREE=/home/zaur_navi/captivportal-lab/worktrees/test-gate-platform-compat-01
BRANCH=task/test-gate-platform-compat-01
HEAD=7e84bc563f1b6dd3d72da66ae25849d9a7d96540
WORKTREE_STATE=DIRTY_UNCOMMITTED
CHANGED_FILES=19
NEW_REPO_FILES=NONE
PRODUCTION_FILES_CHANGED=0
PATCH_BYTES=61265
PATCH_SHA256=28228bfe1afa7fbe759ff60e8a0094f7d0622d302656b47ab4d1edd9f7e77962
```

Full patch: `C:\CaptivPortal-Lab\handoffs\test-gate-platform-compat-01-20261015\TEST-GATE-PLATFORM-COMPAT-01-R1.patch`.

Fresh origin/main at start and final check remained exact base HEAD/tree. QIO-01A is not merged into this baseline. A separate clean worktree/local branch was created; no rebase or synthetic commit used. QIO worktree remains clean at publication commit `65a0029bef762f83eb13677c46f3bd3cb4f94d0c`, tree `301e5fd934e92162a868315775a1646711ba8fab`; PR #213 untouched. Future main advancement/QIO merge requires Tech Lead reconciliation, not silent rebase.

Patch and candidate tree generated using an external temporary Git index; fresh base-index reconstruction and reverse check PASS. Real index remains unstaged. No commit/push/PR created.

## Scope amendment / exact routing

The provided original UTF-16 Windows baseline log contains **238** failure sections. Parsed classification matches the TASK exactly: 168 pread, 63 O_NONBLOCK, 2 fcntl, 3 open-file replacement, 1 Linux CLI lifecycle, 1 native-path fixture. Full identities/categories are in `baseline-windows-failures.json`.

Actual path distribution required and received **Tech Lead SCOPE A1 EXTENSION APPROVED** in this chat:

- `tests/network_metadata_projection/test_projection_source.py`: exactly five approved functions / 21 cases.
- `tests/network_metadata_projection/test_external_peer_v2.py`: exactly six approved I/O functions / 7 cases, separate from A2 native-path fixture.

No extension inferred independently. Exact 28 approved node IDs and original causes: `approved-extension-28.json`. Each of these 28 has actual Linux PASS and exact Windows skip in `windows-posix-linux-paired-237.json`.

The full routed set is **237 exact cases = 209 NI-01 + 28 approved projection cases**. Shared `requires_posix_io` is precisely the built-in:

```python
pytest.mark.skipif(os.name != "posix", reason="Linux/POSIX Network Metadata I/O contract")
```

It is applied explicitly to functions/individual parameters; not to modules, packages, directories or fixtures. The common store has no new conditional behavior. Test arguments, assertions and bodies of every routed case/helper are unchanged (AST proof retained). Mixed parametrizations keep their Windows-capable members active: both zero-record cases and source-open/stat failures. No Windows pread/fcntl emulation, broad conftest hook, deselection or xfail was introduced. No pytest.ini change needed.

The remaining original failure is repaired, not skipped: scope admission fixture uses three distinct native absolute tmp_path DB names. It still asserts canonical fixture identity, disabled behavior and exact `scope_admission_untrusted`; added assertion confirms zero files created.

Read-only collection evidence: **386 identical IDs** in the twelve changed routing files on both platforms, 237 explicit marks with false condition on Linux / true on Windows. The complete Network Metadata collection also remains **446 exact IDs before/after**, with no lost/renamed cases. Collection itself is not treated as execution.

## Linux baseline repairs

### B1 — expensive validation protection, not EXPLAIN-string normalization

Raw native plans, Python/SQLite versions, compile options, root-page map and complete VDBE for both actual unmodified production SQL variants:

- `sqlite-plans-linux.json` — Python 3.10.12 / SQLite 3.37.2.
- `sqlite-plans-windows.json` — Python 3.10.11 / SQLite 3.40.1.

Observed 3.37.2 inlines cheap `validated_cycles` / `ranged` projections into reads of the **one materialized cycle_aggregates**, whereas 3.40.1 exposes separate materialization nodes. Peak also reuses ordered temporary rows in both UNION branches; two scans of a shared temporary result are not two raw AP validations. Both native programs open the actual AP table and its identity index exactly once for the shared requested range. This is empirical plan/code evidence, not a blanket SQLite-version exemption.

The revised tests retain existing result/index assertions and establish:

1. Exactly one materialized candidate producer and expensive cycle-aggregation producer.
2. Exactly two disjoint indexed cycle-range arms, exactly one raw AP identity-index access in the plan.
3. Full VDBE of the **unchanged actual production query**, not rewritten test SQL: exactly one OpenRead for the AP table and its identity index; aggregate opcodes contained in a Once-guarded producer, with no external Gosub bypassing the guard.
4. One producer of ordered statistics, whether coroutine or materialized. Consumers may re-read shared temporary rows, not rebuild expensive source work.
5. Actual compiled separate History + Statistics projections require at least two raw AP-index paths versus one in the combined query. This is structural work sharing, **not** elapsed-time/PERF evidence.
6. Six negative oracle cases reject duplicate aggregate, duplicate raw table/index opens, missing once guard, guard-bypassing entry and missing index. No unconditional `0 or 1`, version skip or tautology.

Focused checks also retain real History-only vs combined equivalence, exact typed Peak rows, corrupt requested-range fail-closed behavior and unchanged source/schema snapshot. No production SQL, schema, SQLite dependency or durability setting changed. Only two authorized Analytics test files are edited. Future SQLite opcode/plan changes require review of this oracle, not automatic skip.

### B2 — fixed delay / non-overlap / stop

Replaced the `sleep(0.13)` two-callback guess with two coordinated real background cycles. Actual provider entry and cycle lock are exercised; concurrent direct run_once is rejected while each cycle owns the lock. Controlled Event.wait observes the exact positive 0.04s delay **after** cycle completion; next entry is withheld until that delay advances. Fake monotonic time accounts for 0.03s provider work and proves a full 0.04s post-completion gap, not fixed-rate overlap.

Stop interrupts the second completed-cycle delay; bounded finally cleanup releases gates and stops the worker. Assertions require exactly two calls, zero overlap, no late duplicate, `_thread is None`, not running, no captured worker error. No runtime/config changes or sleep-padding. Bounded waits/join only coordinate threads; they do not guess callback count from elapsed wall time.

Exactly **10 predetermined subprocess test runs on each platform**, all PASS, with every result retained; not retry-until-green. Independent contended-load/service stability acceptance is still Tech Lead-owned.

### B3 — real AF_UNIX and cleanup

Existing POSIX/AF_UNIX skip condition retained. The test creates and binds a **real** AF_UNIX/SOCK_STREAM socket in `TemporaryDirectory(prefix="vr-", dir="/tmp")`, independent of pytest basetemp. Asserted pathname length <100 bytes, original reader complete/no-reason/empty-state assertions preserved. Socket context closes on failure; private directory context cleans even on exceptions and successful completion explicitly asserts removal. No fake socket or weakened trust checks.

PASS with ordinary short pytest temp root and with explicit >108-byte basetemp:
`/tmp/platform-compat-01-intentionally-long-pytest-root-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.
The socket itself stays short/private. No production path or data used.

## Focused results (not a full gate)

All runs use explicit affected cases/functions only. Counts overlap across runs; unique-case unions are shown separately.

| Execution | Result |
| --- | --- |
| Routing Windows: exact 237 marked IDs + 8 portable controls | **8 PASS / 237 justified SKIP / 0 FAIL / 0 ERROR**, 60.02s |
| Same exact routing set on native Linux | **245 PASS / 0 SKIP / 0 FAIL / 0 ERROR**, 18.74s |
| Windows Analytics oracle/equivalence + native-path fixture + scheduling | **11 PASS**, 5.63s |
| Linux Analytics oracle/equivalence/integrity/readonly/typed output + fixture/scheduling | **14 PASS**, 3.76s |
| Final added shared-vs-separate structural assertion | **1 PASS Windows / 1 PASS Linux**; retested only this changed function |
| Scheduling predetermined repeats | **10/10 PASS Windows; 10/10 PASS Linux** |
| AF_UNIX test short root | **PASS** in initial three-case Linux safe-fix run |
| AF_UNIX intentionally long root | **1 PASS**, 0.29s |
| Unique focused outcomes across all retained runs | **Windows 19 PASS + 237 explicit SKIP; Linux 260 PASS**, no FAIL/ERROR |

Linux routing emits four pre-existing pytest warnings for the existing record_property/xunit2 metadata combination. They are not hidden or converted into skips; test metadata semantics were not altered to silence warnings. See full logs.

No full repository, unrelated cross-module, broad differential, independent PERF or official runner gate was executed by Coder. The exact 245 routing cases are changed functions/parameters plus the required portable controls, not all 446 NI-01 tests or a full projection suite. Six historical strict V7 cases are source/selection-protected but not independently executed by Coder.

### Commands / provenance

Native Linux cwd: the worktree above. Export:

```bash
export PYTHONPATH="$PWD"
export PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/tmp/test-gate-platform-compat-01-pycache
```

Interpreter: `/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python` (Python 3.10.12, pytest 9.1.1, SQLite 3.37.2).

Windows cwd is the same Coder source via UNC:
`\\wsl.localhost\Ubuntu-22.04\home\zaur_navi\captivportal-lab\worktrees\test-gate-platform-compat-01`.
Interpreter `C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe` (Python 3.10.11, pytest 9.1.1, SQLite 3.40.1). External `PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\platform-compat-01-pycache` and separate explicit Windows basetemp paths were used. No package/system changes.

Task artifact directory is `C:\CaptivPortal-Lab\handoffs\test-gate-platform-compat-01-20261015` (Linux `/mnt/c/CaptivPortal-Lab/handoffs/test-gate-platform-compat-01-20261015`).

Reproducible routing commands, using the respective qualified interpreter from that cwd:

```text
<python> <artifact-dir>/routing_evidence.py collect
<python> <artifact-dir>/routing_evidence.py focused
<python> <artifact-dir>/repeat_schedule.py
```

`routing_evidence.py` is an external task-scoped evidence helper, not an admission runner. Its plugin only reads collected item metadata in collection_finish; it never changes/filters/reorders items, ignores paths or adds skips. The only actual platform routing is explicit repository test markers. `focused-linux-args.json` / `focused-windows-args.json` contain every exact pytest argument/node ID for the 245 cases. Collection ledgers and `routing-{platform}.log/xml` retain all outcomes.

Scheduling helper records all ten exact `python -m pytest -q -p no:cacheprovider <test-id> --junitxml=...` commands and exits in `schedule-{platform}-repeats.json`; individual `.log/xml` files retain every run. No failing run was discarded.

Other explicit focused invocations used `python -m pytest -q -p no:cacheprovider` on the two named plan functions, six parametrized negative oracle cases, combined History equivalence, corrupt-range refusal, source-readonly snapshot, typed Peak rows, one scheduling function and one scope fixture. Their exact names/results appear in `stability-and-analytics-linux.xml`, `portable-fixes-windows.xml`, `sharing-{platform}.xml`. AF_UNIX's one exact function is in `socket-long-root-linux.xml`, with the long basetemp above. All raw `.log` siblings retained. These are commands for focused verification, not a replacement full gate.

## Exact changed-file inventory

19 existing files, **353 insertions / 32 deletions**, no new repository files:

```text
docs/testing-environments.md
docs/testing.md
tests/analytics/test_historical_traffic_peak.py
tests/analytics/test_historical_traffic_statistics.py
tests/current_state/test_workers.py
tests/network_metadata/__init__.py
tests/network_metadata/test_capacity.py
tests/network_metadata/test_checkpoint_crash.py
tests/network_metadata/test_cli.py
tests/network_metadata/test_health.py
tests/network_metadata/test_privacy.py
tests/network_metadata/test_read_service.py
tests/network_metadata/test_repository.py
tests/network_metadata/test_retention.py
tests/network_metadata/test_service.py
tests/network_metadata/test_source.py
tests/network_metadata_projection/test_external_peer_v2.py
tests/network_metadata_projection/test_projection_source.py
tests/visitor_registry/test_device_registry.py
```

Docs describe only the resulting explicit routing, paired Linux coverage, test oracles/stability and Owner/Tech Lead runner ownership, without claiming full acceptance. No historical evidence is relabeled current PASS. `verification.json` contains each file byte size/SHA256, exact outcomes, preserved function names and protected-six IDs; `diff-stat.txt`, `changed-files.txt`, `git-status.txt` retain observed state.

## Static / isolation proof

- compileall of all 17 changed Python files: PASS on Linux/Windows. Final changed Analytics function compiled again on Windows after its focused rerun; Linux full changed-file compile repeated. External bytecode output; no source pycache.
- `git diff --check`: PASS, no exception. External candidate index diff-check: PASS. Patch reconstruction and reverse check: PASS.
- Routed test/helper bodies and argument signatures compared to base AST: IDENTICAL (except the expressly authorized A2 fixture). Marking changes only decorators/parameter marks/imports. All original tests retained; six deliberate negative oracle cases added.
- Complete `app` and `deploy` Git subtrees are byte-identical to baseline; no SQL/schema/durability/config/systemd change. No pytest.ini or root conftest created/changed. No credentials, production data or services used.
- Protected-six files byte-identical to base; exact IDs disjoint from the 237 routed IDs. They remain ordinary strict Windows tests. Full execution belongs to Tech Lead.
- Existing V7 runner read-only checksum remains **45d3b37150a2c3b3d3e95460b2a1c6cab8d97aa333c3d3e0cd3507ef1c994f77**. It was not modified or executed. Old external TEST-GATE-PLATFORM-01 scripts/manifest were read only for protected-six identities, not reused as routing/execution policy.
- QIO-01A branch/worktree/accepted tree/PR preserved clean. No main modification, commit, reset, stash, rebase, push, PR, merge or deployment.

## Remaining gates / risks

No unresolved implementation scope blocker remains after the explicit A1 extension. This candidate is **not yet independently accepted**. Tech Lead/Owner must perform the TASK's complete Windows zero-failure gate, complete Linux zero-failure gate, all platform-paired ID/skip coverage and protected-six executions, contended scheduling/socket/FD-leak checks, independent Analytics oracle/mutation review, clean exact-tree/source checks and separately reviewed/versioned official runner path admission. No former baseline failure or QIO exception is automatically waived.

Risk: future SQLite plan/opcode changes may require a new test-oracle review; no runtime/version-specific skip is installed. Source I/O remains genuinely POSIX-specific; explicit routing is not Windows production support. The unique focused result counts are not predictions of full suite counts. If main advances or QIO merges, Tech Lead must reconcile exact parent/tree and select affected reruns; Coder must not silently rebase.

Agent summary: Coder, isolated implementation, no subagents; parsed provided QA logs, obtained exact scope amendment, changed allowed tests/docs, ran only affected focused tests and read-only collection/plan probes, prepared patch/tree/paired evidence. Full/official gates pending; production untouched.

```ini
FOCUSED_WINDOWS=19_UNIQUE_PASS_237_EXPLICIT_PLATFORM_SKIP_0_FAIL_0_ERROR
FOCUSED_LINUX=260_UNIQUE_PASS_0_SKIP_0_FAIL_0_ERROR
WINDOWS_POSIX_SKIP_INVENTORY=windows-posix-linux-paired-237.json
LINUX_CORRESPONDING_TEST_EXECUTION=237_OF_237_PASS
ANALYTICS_PLAN_EVIDENCE=sqlite-plans-linux.json_AND_sqlite-plans-windows.json
CURRENT_STATE_TIMING_PROOF=10_OF_10_PASS_EACH_PLATFORM
AF_UNIX_SHORT_PATH_PROOF=REAL_SOCKET_PASS_SHORT_AND_LONG_PYTEST_ROOT
DIFF_CHECK=PASS
COMPILEALL=PASS
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
INDEPENDENT_GATES=PENDING_TECHLEAD
CODER_HOLD=YES
```
