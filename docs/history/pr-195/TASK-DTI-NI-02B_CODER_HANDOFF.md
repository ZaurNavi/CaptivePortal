# TASK-DTI-NI-02B — Coder implementation handoff / T1 included

Status: candidate prepared; HOLD FOR TECH LEAD SOURCE REVIEW. This is not production acceptance or capacity admission.

## IMPLEMENTED

Independent default-OFF NI-02B worker, NI-01-owned read-only projection source boundary, NI-02A read-only horizon extension and exact T1 timestamp bridge. Materialization produces 0/1/2 immutable Site+MAC edges, normalized late Registry device_id binding, atomic generation/byte-offset checkpoints, R1 partial retry snapshots, bounded retention and capacity maintenance, projection-only keyset reads, safe telemetry and auxiliary deployment examples.

## NOT IMPLEMENTED

No UI/Device Card integration, new Device creation, Registry/Visit writes, cross-MAC merge, query-time attribution, IPv6 attribution, raw EVE parsing, external polling, production installation/enablement or live-network test. NI-01 writer/schema/normalizer/retention, NI-02A writer/schema/fact and binding identity, and Visitor Registry source/schema are unchanged. No full repository or Central Lab gate was run.

## BASELINE VERIFIED

```text
BASE_HEAD=e32c695e53ffb2b173178189581751728c2ee0c2
BASE_TREE=6348fe5fddb22f597ba8a6e40cf5f96a4d9d73ac
CANDIDATE_TREE=aff1464ef26caca4c8a2c5543f840850b9a50f2d
BRANCH=feature/dti-ni-02b-device-network-projection
WORKTREE=C:\CaptivePortal-NI02B
WORKTREE_CLEAN=NO
INDEX_STAGED_FILES=0
```

The implementation worktree remains intentionally dirty because COMMIT is not authorized. Its HEAD/tree remain the accepted baseline. Candidate tree was computed using an external temporary Git index, without staging the actual worktree index. The Linux mirror independently produced the same candidate Git tree, with canonical text/file-mode handling for Windows-to-Linux transport.

Linux isolated mirror: `/home/zaur_navi/captivportal-lab/coder-ni02b` in `Ubuntu-22.04`; Python `/home/zaur_navi/captivportal-lab/perf-venv/bin/python` (3.10.12). Existing NI02A/DTI worktrees were not edited/reset/cleaned/rebased.

## FILES INSPECTED

- Architecture contract v1-RU, v1-R1, original implementation directive and Timestamp Interoperability Addendum T1.
- Repository instructions: `AGENTS.md`, `docs/agents/workflow.md`, `docs/agents/handoff.md`, `docs/testing-environments.md`, `docs/operations-command-lessons-learned.md`.
- `app/network_metadata/`: models.py, schema.py, repository.py, read_service.py, config.py, service.py, cli.py, retention.py, validation.py, canonical.py; related source/health and test fixture boundaries.
- `app/network_attribution/`: models.py, read_service.py, config.py, schema.py, repository.py, validation.py; existing temporal/coverage/writer tests.
- `app/visitor_registry/`: registry_read_service.py, registry_repository.py, registry_models.py, registry_service.py; exact read/status/schema and disposable fixture methods/tests.
- `app/artifact_identity.py`, `.env.example`, `deploy/device-fingerprint/fingerprint-sensor.service`.
- Related test inventories under tests/network_metadata, tests/network_attribution and tests/visitor_registry; directly relevant fixture/read/schema cases were inspected. File inspection does not imply a full Visitor Registry test run.

## FILES CHANGED

27 files, 2750 insertions, 24 deletions against the accepted baseline:

```text
M .env.example
M app/network_attribution/models.py
M app/network_attribution/read_service.py
M app/network_attribution/validation.py
A app/network_metadata/projection_source.py
A app/network_metadata_projection/__init__.py
A app/network_metadata_projection/cli.py
A app/network_metadata_projection/config.py
A app/network_metadata_projection/models.py
A app/network_metadata_projection/read_service.py
A app/network_metadata_projection/registry_adapter.py
A app/network_metadata_projection/repository.py
A app/network_metadata_projection/retention.py
A app/network_metadata_projection/schema.py
A app/network_metadata_projection/service.py
A app/network_metadata_projection/telemetry.py
A app/network_metadata_projection/validation.py
A deploy/network-metadata-projection/README.md
A deploy/network-metadata-projection/network-metadata-projection.env.example
A deploy/network-metadata-projection/network-metadata-projection.service
A tests/network_attribution/test_read_timestamp_interoperability.py
A tests/network_metadata_projection/__init__.py
A tests/network_metadata_projection/support.py
A tests/network_metadata_projection/test_capacity_config.py
A tests/network_metadata_projection/test_integration.py
A tests/network_metadata_projection/test_projection.py
A tests/network_metadata_projection/test_projection_source.py
```

## ARCHITECTURE v1 COMPLIANCE

- NI-01 source: exact source record, generation/binding/observation identity and endpoint-state validation from one ro/query-only SQLite snapshot; no family payload/raw EVE read or expired endpoint reconstruction.
- Authority: exact Site+IPv4+original event time through NI-02A; horizon bounds backfill; unsupported/absent endpoints do not call authority; invalid or out-of-scope resolved endpoints conflict.
- Edges: deterministic observation+role SHA-256 IDs, immutable semantic digest, UPDATE/unauthorized DELETE triggers; replay does not refresh edge/binding timestamps.
- Registry: existing get_device_by_mac read boundary only; exact existing UUID, global MAC/UUID uniqueness, Site-local binding rows, monotonic authoritative binding; IP/Site fields never infer identity.
- Store: exactly nine frozen logical tables; user_version 1, exact schema signature, WAL/FULL/FK/busy_timeout 500, startup quick_check/FK check, single writer lock, fail-closed future/partial schema.
- Commit: one prepared batch up to 256 observations commits edges, binding/events, pending, checkpoint and runtime together. First checkpoint is absent until successful disposition; offset zero is not a sentinel.
- Reads: projection-local joins only, exact Site, half-open bounded window <=14d, limit <=500, event/edge keyset order; missing internal binding fails closed.
- Retention: strict event OR source-ingestion 14-day boundary, pending expiry, event 30d and unreferenced historical run 90d GC, visible-generation checkpoint protection, bounded 5000-row/20-batch cleanup. The current live writer still references its run; it is not treated as an unreferenced historical run.
- Default OFF: no DB/lock/upstream configuration/open/Registry/identity capture; independent CLI/service with no main composition or upstream stop/restart dependency.
- Privacy: projection has no DNS/SNI/raw Registry/DHCP data; safe structured logs exclude raw endpoints, MAC and device_id.

## ARCHITECTURE v1-R1 COMPLIANCE

- Pending persists src/dst state and exact counterpart binding snapshots, with pending flags iff unavailable; no endpoint copy.
- Cases A/B/C and simultaneous resolution preserve old edges byte-for-byte. Only pending roles are queried; old edge digest is not recomputed during retry.
- Retry selection <=500, partitioned into bounded <=256-disposition transactions. Terminal/expired dependencies remove pending without inventing edges.
- Registry reconciliation preselects once, deterministic unresolved 400 / authoritative 100 quotas, exact priority and spillover, with no identity repeated during one pass.
- Fixed transaction headroom = 16777216; footprint includes main+WAL+SHM+journal, not writer lock. Every write (including diagnostics/retention) uses the headroom gate.
- PASSIVE follows each successful write commit. Pressure-only TRUNCATE has zero waiting timeout; pinned readers yield capacity_waiting_reader, other pressure capacity_halted. Recovery revalidates trust/headroom; committed checkpoints are never rewound.
- Shutdown stops new/prepared work and closes DB/lock without signalling upstream services. A running SQLite transaction retains its normal atomic commit/rollback boundary.

## TESTS EXECUTED

Final Linux targeted run from the exact mirrored candidate:

```bash
PYTHONPATH=. /home/zaur_navi/captivportal-lab/perf-venv/bin/python -B -m pytest -q -s \
  -o junit_family=legacy \
  tests/network_metadata_projection tests/network_metadata tests/network_attribution \
  --basetemp=/home/zaur_navi/captivportal-lab/ni02b-final-evidence-20261009 \
  --junitxml=/mnt/c/CaptivPortal-Lab/artifacts/TASK-DTI-NI-02B_linux-targeted-results.xml \
  --tb=short
```

Smallest existing Registry compatibility subset used:

```text
tests/visitor_registry/test_device_registry.py::test_registry_read_service_derives_device_type_keys_without_mutating_raw_source
tests/visitor_registry/test_device_registry.py::test_schema_and_singleton_are_created
tests/visitor_registry/test_device_registry.py::test_startup_rejects_singleton_with_invalid_runtime_state
tests/visitor_registry/test_device_registry.py::test_future_and_partial_schemas_are_preserved_and_rejected
tests/visitor_registry/test_device_registry.py::test_read_only_cli_lists_cards_and_never_exposes_raw_json
```

Executed with the same Linux Python, `-B -m pytest -q`, separate external basetemp and JUnit output. Earlier incremental targeted runs assisted implementation; their results are superseded by the final run. An initial Windows source-fixture attempt encountered the POSIX-only `os.pread` boundary; source/storage verification was moved to native Linux, without bypassing the fixture or changing existing tests.

Compileall (Windows canonical repo venv, PYTHONPYCACHEPREFIX external to repo): app/network_metadata_projection, app/network_metadata/projection_source.py, app/network_attribution, tests/network_metadata_projection, tests/network_attribution/test_read_timestamp_interoperability.py.

Also executed: git diff --check; external-index full-candidate diff check; reverse `git apply --cached --reverse --check`; Linux `systemd-analyze verify` on the deployment unit. No service install/start/enable operation.

## TEST RESULTS

```text
NI02B_FOCUSED=74 passed
NI01_REGRESSION=368 passed
NI02A_REGRESSION_INCLUDING_T1=106 passed
LINUX_TARGETED_TOTAL=548 passed / 0 failed / 0 errors / 0 skipped
REGISTRY_DIRECT_COMPATIBILITY=5 passed / 0 failed / 0 skipped
T1_DEDICATED_TESTS=34 passed
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
SYSTEMD_UNIT_VALIDATION=PASS (exit 0; Lab environment warnings, not runtime activation)
```

Remaining systemd-analyze warnings refer to the Lab's unrelated netplan private runtime path and snapd RestartMode compatibility. Windows-to-Linux copied unit mode was aligned to 0644 before final validation; no source bytes were changed.

Retained JUnit artifacts:

- `C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-02B_linux-targeted-results.xml`, 116604 bytes; SHA256 `f6bf5af818417a6be6b7a40c998ffbe69e30149100e6fec4eed3e48a389f6493`.
- `C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-02B_registry-compatibility-results.xml`, 984 bytes; SHA256 `01c0d2fc0072a67a23279d7f98caf2b51f92d6566a8aa222f9c347570b07cf5d`.

## 16 MiB TRANSACTION HEADROOM PROOF

Linux, final exact schema/index set, 256 observations; maximum-length machine IDs, IPv4 endpoint strings and ports, near-int64-max offsets, checkpoint/runtime work and real SQLite/WAL/index effects. Physical footprint sampled before COMMIT, after COMMIT and after maintenance against the pretransaction footprint.

| Shape | Edge/binding/event rows | Pending rows | Maximum measured growth |
| --- | ---: | ---: | ---: |
| Both roles resolved | 512 / 512 / 512 | 0 | 2707064 bytes |
| One role resolved, other unavailable | 256 / 256 / 256 | 256 | 1593832 bytes |

```text
FIXED_HEADROOM_BYTES=16777216
MAX_MEASURED_TRANSACTION_GROWTH_BYTES=2707064
HEADROOM_PROOF=PASS
HEADROOM_INCREASED=NO
FROZEN_BATCH_REDUCED=NO
```

This bounds the exercised maximum materialization transaction shapes, not an entire production steady-state capacity/throughput admission.

## FAILURE-INJECTION RESULTS

PASS: untrusted source schema/identity/binding/timestamp/endpoint loss; authority invalid/scope conflict/unavailability; Registry absence/outage and MAC/UUID conflict; projection ro write refusal, foreign/future/partial schema, second writer refusal; precommit/postcommit crash and reopen/replay; retry crash atomicity; source checkpoint conflict; held-reader capacity deferral/recovery; overflow diagnostic no-write; postcommit pressure with durable checkpoint; no raw sensitive exception/log disclosure. Existing committed edges remain readable and no upstream writer APIs are used by projection. Production/upstream service execution was not performed.

## TIMESTAMP_INTEROPERABILITY_RESULT

```text
TIMESTAMP_INTEROPERABILITY_RESULT=PASS
FILES_CHANGED_FOR_TIMESTAMP_REPAIR=app/network_attribution/validation.py; app/network_attribution/read_service.py; tests/network_attribution/test_read_timestamp_interoperability.py; tests/network_metadata_projection/test_integration.py
TIMESTAMP_TESTS=34 passed + real-authority projection integration/reassignment cases
MILLIS_MICROS_EQUIVALENCE=PASS
HALF_OPEN_BOUNDARY_RESULT=PASS
COVERAGE_WATERMARK_RESULT=PASS
COVERAGE_OUTAGE_RECOVERY_BOUNDARIES=PASS
HORIZON_BOUNDARIES=PASS
EXACT_EVENT_TIME_PRESERVED=YES
NI01_TIMESTAMP_CHANGED=NO
NI02A_WRITER_CONTRACT_CHANGED=NO
NI02A_SCHEMA_CHANGED=NO
```

Read-query accepts exactly canonical millisecond or microsecond Z timestamps; source/fact validation stays millisecond-only. Indexed membership/confirmation predicates use an internal floored millisecond key. Strict watermark, horizon and continuity comparisons use exact parsed instants. Valid read results retain caller event_at. Real NI-02A integration proves `2026-10-09T12:00:00.123456Z` reaches resolve unchanged and is persisted unchanged in the edge with the exact millisecond-boundary authority binding ID. No global parse_utc/format_utc change, migration or historical rewrite.

## UNVERIFIED AREAS

No production database, live-network acquisition, production permissions/ACL or service runtime verification; no steady-state production cardinality/throughput/reader-duration admission; no full repository or official Central Lab gate. No official NI02B acceptance claimed by Coder.

## KNOWN RISKS

- Production capacity admission remains mandatory before enablement. This Lab proof is not a claim that a production deployment fits its configured capacity indefinitely.
- Long-held readers legitimately pause writes; consumer reader lifetimes need operational bounds.
- Source FK checking per snapshot and existing Registry health validation per lookup have costs that were not benchmarked against production-sized upstream stores.
- Schema mismatch/conflict is fail-closed and intentionally requires an explicit disposition rather than destructive recovery.
- No currently failing authorized targeted test or implementation blocker remains in the reported candidate. Tech Lead still owns review and acceptance.

## REPOSITORY ACTIONS

Complete binary-capable BASE-to-CANDIDATE replacement patch:

```text
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-DTI-NI-02B_BASE-to-CANDIDATE.patch
PATCH_BYTES=165868
PATCH_SHA256=ba46e5667d1a7b716b155c2ef4edb5b60bfeaee8d2ec0a5b8ac3bf7773080ef3
PATCH_BASE=e32c695e53ffb2b173178189581751728c2ee0c2
PATCH_REVERSE_APPLY_CHECK=PASS
```

External review indexes/object trees and isolated Lab disposable databases/test evidence were created only for candidate verification. Actual implementation index is unstaged. No implementation commit was made; candidate worktree changes are preserved.

```text
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOYMENT=NO
PRODUCTION_ACTION=NO
FULL_PROJECT_GATE=NO
CENTRAL_LAB_RUN=NO
HOLD_FOR_TECH_LEAD_REVIEW=YES
```

## NEXT OWNER ACTION

Send this handoff, complete replacement patch and retained JUnit evidence to Tech Lead for independent source review. Do not enable the service or publish/commit without a new authorization. Coder is HOLD.
