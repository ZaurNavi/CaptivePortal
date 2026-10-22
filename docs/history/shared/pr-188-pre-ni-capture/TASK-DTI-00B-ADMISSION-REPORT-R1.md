# TASK-DTI-00B-LIGHTWEIGHT-PERIODIC-TRAFFIC-METER-PROTOTYPE-ADMISSION-REPORT

Implementation/self-check handoff for TechLead source review. NOT a formal
DTI-00B acceptance or DTI-00 program closure. Overall result is PARTIAL, with
explicit evidence gaps below. DTI-01 remains HOLD.

## Required result block

```text
TASK=TASK-DTI-00B
PROTOTYPE_IMPLEMENTED=YES
PROTOTYPE_VERSION=0.1.0
EXECUTION_MODE=OFFLINE_LAB
CONTROLLED_CLIENT_USED=NO
CONTROLLED_FIXTURES=SYNTHETIC_ONLY
METER_NATIVE_BYTE_BASIS=L3 IP packet length
PRIMARY_TEST_SLICE=5 seconds / UTC epoch-aligned / half-open
PROTOTYPE_ACCOUNTING_SCOPE=subject-MAC unicast IPv4/IPv6 only

PERIODIC_PACKET_SLICES=PASS
PERIODIC_BYTE_SLICES=PASS
CURRENT_RATE_PRIMITIVE=PASS
CURRENT_ACTIVITY_PRIMITIVE=PASS
LONG_LIVED_FLOW_SLICING=PASS
VISIT_BOUNDARY_SLICING=PASS
UPLOAD_DOWNLOAD=PASS
RESTART_SEMANTICS=PASS
DETERMINISTIC_SLICE_ID=PASS
RUN_SESSION_IDENTITY=PASS
REPLAY_IDEMPOTENCY_SUPPORT=PASS
COVERAGE_ZERO_SEMANTICS=PASS
MIRROR_DUPLICATE_HANDLING=PARTIAL
RETRANSMISSION_DISTINCTION=PASS
CAPTURE_QUALITY_PROVENANCE=PASS

RESOURCE_IMPACT=BOUNDED
RESOURCE_SUSTAINABILITY_19000_PPS=PASS_FOR_10_SECOND_WINDOWS_FIXTURE_ONLY
RESOURCE_SUSTAINABILITY_38000_PPS=NOT_SUSTAINED
FINGERPRINT_REGRESSION=NOT_APPLICABLE
PACKET_STEALING=NOT_APPLICABLE
OFFLINE_FUNCTIONAL_ACCOUNTING_ADMISSION=PARTIAL
PRODUCTION_TOPOLOGY_ADMISSION_REQUIRED=YES
DTI01_RESOURCE_BUDGET_CANDIDATE=PARTIAL
OPEN_P0=0
OPEN_P1=2
IMPLEMENTATION_DEPENDENCIES=NONE
CHANGES_MADE=13 new files exclusively in research/dti_00b and tests/dti_00b
ROLLBACK_STATUS=NOT_APPLICABLE
TASK_DTI_00B_VERDICT=PARTIAL

FULL_PROJECT_GATE=NOT_RUN
OFFICIAL_CENTRAL_LAB=NOT_RUN
OFFICIAL_LINUX_PERF_GATE=NOT_RUN
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACCESS=NO
PRODUCTION_ENP8S0_ATTACHMENT=NO
DTI01=HOLD
```

Capability PASS values above describe focused synthetic proof only, not independent
formal acceptance. Production topology admission is required **if** final parser
allocation is a direct production packet consumer; that allocation is not frozen
by this prototype. No packet-stealing/Fingerprint live proof is claimed.

## Exact artifact identity

```text
WORKTREE=C:\CaptivPortal-Lab\coder-task05-identity-session
BASE_COMMIT=c8d8d620dfed06caee92a498b891bf2faa37a6a9
BASE_TREE=be3470c378180aa215d527c6de6b686583ae0d79
LOCAL_HEAD=c8d8d620dfed06caee92a498b891bf2faa37a6a9
LOCAL_HEAD_TREE=be3470c378180aa215d527c6de6b686583ae0d79
IMPLEMENTATION_COMMIT=NOT_CREATED
WORKTREE_STATE=DIRTY_WITH_EXACT_UNCOMMITTED_PROTOTYPE
STAGED_CONTENT=EMPTY

PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-DTI-00B_BASE-to-PROTOTYPE-R1.patch
PATCH_BYTES=69999
PATCH_SHA256=4ec2898f5767f09652ece24c7a0581bef8a514b4f710775136f42c1a8acb091e
PATCH_FORMAT=git diff --binary --full-index BASE
PATCH_REVERSE_APPLY_CHECK=PASS (check only; not applied)
PROTOTYPE_PACKAGE_SHA256=632b1ae5299f3ca57c810c2523e25b1c48d2a335ce126c2a786b3b0c3ae1f6df
```

Package SHA hashes the canonical filename->SHA256 map of the ten research package
files, including README; patch SHA binds the complete candidate including tests.
Git intent-to-add was used to include new files in the exact BASE-to-candidate
patch. No content is staged, no commit or branch publication occurred.

## Focused verification

Environment: Windows 10 10.0.19045, Python 3.10.11 x64;
`C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe`.
External pycache: `C:\CaptivPortal-Lab\tmp\dti-00b-pyc`.

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\dti-00b-pyc'
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest tests/dti_00b -q --basetemp='C:\CaptivPortal-Lab\tmp\dti-00b-target-final'
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m compileall -q research/dti_00b tests/dti_00b
git diff --check
git apply --reverse --check 'C:\CaptivPortal-Lab\artifacts\TASK-DTI-00B_BASE-to-PROTOTYPE-R1.patch'
```

Results: **57 passed / 0 skipped / 0 failed / 0 errors**, 3.63 seconds;
pytest exit 0; compileall exit 0; diff-check exit 0; reverse patch check exit 0.
The CLI replay/import path is exercised by the focused suite. No other project
test suite was run. New test modules: test_meter.py and test_replay.py;
new test package __init__.py; existing tests modified: NONE.

## Independent reconciliation matrix

Reference truth is declared logical sender transmissions, timestamps, IP lengths,
direction and original-transmission identities **before** encoding. Reference
arithmetic never calls the PCAP parser or meter. Tests additionally assert literal
byte/rate/boundary expectations. Every fixture has closed coverage metadata.

| Scenario | Reference packets | Meter packets | Reference bytes | Meter bytes | Timing/quality |
|---|---:|---:|---:|---:|---|
| A short completed | 2 | 2 | 240 | 240 | PASS / healthy |
| B long-lived | 20 | 20 | 24000 | 24000 | PASS / healthy |
| C idle | 0 | 0 | 0 | 0 | PASS / healthy proven zero |
| D burst | 100 | 100 | 90000 | 90000 | PASS / healthy |
| E active before start | 20 | 20 | 24000 | 24000 | PASS / outside-window records excluded |
| F ends after end | 20 | 20 | 24000 | 24000 | PASS / outside-window records excluded |
| G Visit T at 7s | 20 | 20 | 24000 | 24000 | PASS / exact half-open conservation |
| H restart at 7s | 7 | 7 | 8400 | 8400 | PASS / healthy, partial, then unavailable |
| I deterministic replay | 20 | 20 | 24000 | 24000 | PASS / UUID excluded from semantic comparison |
| J declared mirror duplicate | 1 | 1 | 100 | 100 | Synthetic PASS only / general admission PARTIAL |
| K retransmission | 2 | 2 | 200 | 200 | PASS / both transmissions counted |
| L degraded capture | 1 | 1 | 100 | 100 | PASS / later missing intervals never assert healthy zero |
| M IPv4 | 1 | 1 | 60 | 60 | PASS / total_length |
| N IPv6 | 1 | 1 | 1280 | 1280 | PASS / 40+payload_length |
| O upload | 1 | 1 | 500 | 500 | PASS / subject source MAC + synthetic IP |
| P download | 1 | 1 | 750 | 750 | PASS / subject destination MAC + synthetic IP |

Complete per-slice independent truth, semantic output, coverage and counters:
`TASK-DTI-00B-reconciliation-R1-final.json`, 74448 bytes,
SHA256 `ead72b573e877d6668b3c0e7ddd12bbde7cbcfca0dd76078af3992ba63746e37`.
Generated via `python -m research.dti_00b reconcile --report <external path>`.

## Accounting capability matrix

| Capability | Meter proof | Independent reference / verdict |
|---|---|---|
| Periodic packet/byte slices | A..P, integer counters | logical event counts/declared IP lengths, PASS |
| Current rate | completed slice before flow end | literal 480/720 B/s; burst 18000 B/s then 0, PASS |
| Current activity | packet timestamps and healthy absence | known burst/idle/missing timeline, PASS |
| Long-lived slicing | no flow-terminal dependency | B/E/F bounded windows, PASS |
| Visit boundary | optional split at T=7s | exact before+after=whole, PASS |
| Upload/download | controlled MAC endpoints | synthetic IPv4/IPv6 known endpoints, PASS |
| Restart | open interval partial, later unavailable | new run UUID/sequence reset; conflicting partial/full slice detected, PASS |
| slice_id | hash source/scope/subject/window/schema | independent replay equality, PASS |
| Run/session | separate UUID | new run distinct, same semantic ID, PASS |
| Idempotency | REPLAY vs CONFLICT | changed counts/quality with same ID conflicts, PASS |
| Healthy zero | exact coverage partition | C, PASS |
| Degraded/missing | incomplete flags, null rates | L and partial edges, PASS |
| Mirror duplicates | explicit synthetic original-record assertion | one transmission -> one count; general provenance unresolved, PARTIAL |
| Retransmission | no similarity heuristic | both equivalent-header transmissions retained; indistinguishable records without provenance retained, PASS |
| Capture quality | manifest + observed rejects/restart | unavailable != zero; malformed header degrades, PASS |
| Bounded resources | hard record/output/cache/manifest ceilings | smoke + paced observations; throughput/budget review pending, PARTIAL admission |

## Mirror/retransmission admission boundary (open P1-1)

Native before dedup in J: 2 raw in-scope records / 200 bytes. After corroborated
synthetic provenance: 1 packet / 100 bytes. Configured dedup horizon 1 second,
4096 original header entries maximum, observable eviction/unresolved counters.
Identity: explicit synthetic repeat ordinal -> original ordinal, corroborated by
bounded header/native-length equality. Not a TCP-data similarity heuristic.

False-positive risk: wrong provenance can label a legitimate same-header
transmission as a repeat. No full-frame equality claim is made from header-only
data. False-negative risk: no provenance or expired/evicted original means repeat
remains counted; unresolved declared provenance degrades quality rather than
silently dropping a packet. Real retransmission has a separate transmission and
is always counted. No Fingerprint dedup dependency.

This proves the controlled synthetic case, not a safe generic mirror dedup rule
for arbitrary production input. **G26 remains PARTIAL; total admission cannot be
declared PASS.** No request to attach to production has been made.

## Paced resource characterization (open P1-2)

These are local Windows header-only synthetic replay measurements, NOT official
Linux/PERF or production admission. CPU includes generation + parse + meter +
output serialization; CPU is process CPU / elapsed time on one-core basis. RSS is
sampled, not cgroup enforced. Native Mbit/s represents declared IP packet lengths,
not a real NIC/driver/copy-throughput measurement.

| Measurement | 19000 pps | 38000 pps |
|---|---:|---:|
| Offered native Mbit/s | 156.56 | 313.12 |
| Offered duration seconds | 10 | 10 |
| Actual elapsed seconds | 10.0042724 | 31.4526530 |
| Accounted packets | 190000 | 380000 |
| Accounted bytes | 195700000 | 391400000 |
| Rejected/missing accounting packets | 0 / 0 | 0 / 0 |
| CPU seconds | 6.140625 | 31.078125 |
| One-core CPU percent | 61.3800 | 98.8092 |
| Sampled RSS peak bytes | 16744448 | 16416768 |
| Incremental sampled RSS bytes | 311296 | 299008 |
| Queue / bounded generator chunk | 1 / <=190 records | 1 / <=190 records |
| Parser header buffer peak bytes | 34 | 34 |
| Slice count / output bytes | 2 / 1608 | 2 / 1612 |
| Output bytes/second observed | 160.7313 | 51.2516 |
| Maximum pacing drift seconds | 0.0212727 | 21.4409037 |
| Slice emission drifts seconds | 0.0107650 / 0.0042252 | 7.0832090 / 21.4524834 |
| Offered pace sustained for fixture | YES | NO |

At 2x load the bounded synchronous reader backpressures offline input and delivers
all counts late; it does not meet real-time cadence. This is characterized, not
hidden as PASS or capture-drop-free production behavior. Offline capture/kernel
drops are NOT_APPLICABLE, not asserted as zero. Real consumer queue/drop behavior
remains untested and cannot be inferred from this pull reader.

Final measured artifacts (same final source, no overwrite of earlier attempts):

- `TASK-DTI-00B-paced-19000-R1-final.json`, 1212 bytes,
  SHA256 `d284adf7afd56d25e3e1d2c9fa2dd6e8382fc8ea35f9edd9fb0909fd7f976e68`.
- `TASK-DTI-00B-paced-38000-R1-final.json`, 1204 bytes,
  SHA256 `179c9a1e2d60313f855458ceb65431c60d33cc7555cef260ea3b64cff8e49139`.

Earlier R1 resource attempts are historical diagnostic files, not final-candidate
resource evidence. They preceded correction of per-sample ctypes type creation
inside the Windows memory observer; the final observer uses one static type.
The added focused regression proves repeated memory sampling does not grow that
ctypes pointer-type cache. No production component was changed for this correction.

## DTI01 resource-budget candidate

Observed Windows 19k envelope: approximately 61% one CPU core for this 10s fixture,
approximately 16 MiB process RSS, approximately 0.30 MiB incremental sampled RSS.
Not a production capacity or long-duration guarantee. At 38k this implementation
is CPU-bound and cannot keep pace. Production headroom, subject cardinality,
Linux host measurement and actual capture/drop behavior remain unresolved.

One subject emits approximately 0.2 slices/s. Normalized output around 804 bytes/
slice gives approximately 160.8 bytes/s, 13.9 MB/day per active observed subject
at this representation; this is modeled JSONL volume, **not** a durable database
storage contract and not a multi-subject capacity extrapolation.

Candidate hard data bounds: record <=65535, replay <=2000000 records, coverage
<=24h, manifest <=1MiB, <=4096 quality intervals/duplicate declarations,
<=4096 dedup entries, one pending packet, one bucket, output <=16MiB.
Any rejected header degrades the bucket; structural framing/order/limit failures
block COMPLETE. Output short write/disk-full/ceiling failure blocks and leaves an
incomplete attempt for diagnosis; no retry/fallback/silent discard. Synchronous
output backpressure is bounded but can delay accounting. CPU/RAM enforcement and
drop policy for a live capture queue are deliberately not frozen here.

Thus candidate budget is **PARTIAL**, not a production resource admission.

## Gate disposition for TechLead

G1..G10, G12..G14, G17, G21..G25, G27: focused synthetic proof present.
G11: explicit method/counters/limitations documented.
G15/G16: bounded local measurement and output-error proof present; not live capacity.
G18: no Fingerprint source/config changes; live regression NOT_APPLICABLE offline.
G19: NOT_APPLICABLE offline; later conditional production coexistence required.
G20: PARTIAL resource budget.
G26: PARTIAL general mirror provenance.
G28: 19k paced local fixture sustained; 2x measured and not sustained.
G29: offline/production admission explicitly separated.

No final ownership decision, parser allocation freeze, TASK-DTI-00 acceptance,
DTI-01 implementation or production attachment is made by Coder.

## Exact changed files and git evidence

`git diff --name-status`:

```text
A research/dti_00b/README.md
A research/dti_00b/__init__.py
A research/dti_00b/__main__.py
A research/dti_00b/admission.py
A research/dti_00b/benchmark.py
A research/dti_00b/fixtures.py
A research/dti_00b/meter.py
A research/dti_00b/model.py
A research/dti_00b/pcap.py
A research/dti_00b/replay.py
A tests/dti_00b/__init__.py
A tests/dti_00b/test_meter.py
A tests/dti_00b/test_replay.py
```

`git diff --stat`:

```text
research/dti_00b/README.md    | 169 +
research/dti_00b/__init__.py  |   3 +
research/dti_00b/__main__.py  |  68 +
research/dti_00b/admission.py |  53 +
research/dti_00b/benchmark.py | 100 +
research/dti_00b/fixtures.py  | 109 +
research/dti_00b/meter.py     | 104 +
research/dti_00b/model.py     | 168 +
research/dti_00b/pcap.py      | 117 +
research/dti_00b/replay.py    |  67 +
tests/dti_00b/__init__.py     |   1 +
tests/dti_00b/test_meter.py   | 246 +
tests/dti_00b/test_replay.py  | 110 +
13 files changed, 1315 insertions(+), 0 deletions(-)
```

`git status --short` shows the same 13 added working-tree files (` A`,
intent-to-add only). No other tracked paths changed; no staged content.
Baseline HEAD/tree unchanged. No commit/amend/rebase/push/PR/merge performed.
Only disposable local fixture/test/report/pycache files outside Git were produced.
No local databases, secrets, visitor captures, generated production corpus or
production configuration were added. Rollback is NOT_APPLICABLE; cleanup only
after TechLead/Owner retention decision, per research README.

## Next authority boundary

TechLead reviews this exact patch and determines disposition of the two open
issues. Official gates, final admission/ownership and any later controlled
production consumer test require the corresponding TechLead/Owner authorization.
Coder stops here. No publication or DTI-01 work is authorized.
