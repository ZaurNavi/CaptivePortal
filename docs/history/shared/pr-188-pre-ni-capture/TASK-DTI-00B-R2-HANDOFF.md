# TASK-DTI-00B-R2 — LIVE LINUX CAPTURE ADAPTER

Implementation only: READY_FOR_TECH_LEAD_SOURCE_REVIEW. This report does not
claim actual Linux/production capture, coexistence admission, packet-stealing
absence or DTI-00 program acceptance. Sysadmin live admission remains HOLD until
R2 review. DTI-01 remains HOLD.

```text
LIVE_ADAPTER_IMPLEMENTED=YES
LIVE_ADAPTER_VERSION=r2.0
ACCOUNTING_CORE_VERSION=0.1.0 (unchanged)
AF_PACKET_MODE=Linux / AF_PACKET / SOCK_RAW / explicitly bound independent socket
PACKET_FANOUT_USED=NO
FINITE_DURATION_REQUIRED=YES (1..300 integer seconds)
IDLE_TIMER_SLICE=PASS (controlled clock/fake socket)
SOURCE_FAILURE_QUALITY=PASS (controlled clock/fake socket)
BOUNDED_BUFFERING=PASS (implementation bounds + focused tests)
CONTROLLED_SHUTDOWN=PASS (controlled stop/signal-handler tests)
NEW_DEPENDENCIES=NONE

TEST_RESULTS=92 passed / 0 skipped / 0 failed / 0 errors
EXISTING_R1_TESTS=57 passed
NEW_R2_TEST_CASES=35 passed
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
PATCH_REVERSE_APPLY_CHECK=PASS (check only)

REAL_AF_PACKET_SOCKET_OPENED_BY_CODER=NO
PRODUCTION_ACCESS=NO
PRODUCTION_ATTACHMENT=NO
PACKET_STEALING=NOT_PROVEN_BY_CODER
FULL_PROJECT_GATE=NO
OFFICIAL_CENTRAL_LAB=NO
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_CHANGE=NO
DTI01=HOLD
```

## Exact candidate/patch

```text
BASE_COMMIT=c8d8d620dfed06caee92a498b891bf2faa37a6a9
BASE_TREE=be3470c378180aa215d527c6de6b686583ae0d79
LOCAL_HEAD=c8d8d620dfed06caee92a498b891bf2faa37a6a9
LOCAL_HEAD_TREE=be3470c378180aa215d527c6de6b686583ae0d79
IMPLEMENTATION_COMMIT=NOT_CREATED
WORKTREE=DIRTY_WITH_UNCOMMITTED_R1_PLUS_R2_CANDIDATE
STAGED_CONTENT=EMPTY (intent-to-add only for patch export)

BASE_TO_R2_PATCH=C:\CaptivPortal-Lab\artifacts\TASK-DTI-00B_BASE-to-R2.patch
PATCH_BYTES=118891
PATCH_SHA256=c9db8968e134334728e5f418a282655c84806455fce5f1df1ce36c3bc32182a4
PROTOTYPE_PACKAGE_SHA256=90bedeadeafb91e7d8d6aeb9fa84ec58a4fdf213a23bf23b92172097706c41be
R1_ACCEPTED_PATCH_SHA256=4ec2898f5767f09652ece24c7a0581bef8a514b4f710775136f42c1a8acb091e
```

This is the **complete** patch against the original repository baseline, not
merely the adapter delta. R1 was uncommitted, so its accepted content is included.
Historical R1 patch/reconciliation/measurement files were not overwritten.

## R2 changed files relative to accepted R1

1. `research/dti_00b/live_capture.py` — NEW Linux-only independent packet source.
2. `research/dti_00b/live.py` — NEW timer-driven orchestration / stop / bounded output.
3. `tests/dti_00b/test_live.py` — NEW 35 fake/injected targeted cases.
4. `research/dti_00b/__main__.py` — explicit finite `live` CLI only.
5. `research/dti_00b/admission.py` — source identity inventory includes the two new files;
   no change to offline reconciliation or admission semantics.
6. `research/dti_00b/README.md` — research CLI, safety/quality/resource/stop runbook.

The accepted R1 `__init__.py`, model.py, pcap.py, meter.py, fixtures.py, replay.py
and benchmark.py were hash-compared with the retained R1 identity map: all seven
**byte-identical**. Existing R1 test modules/__init__.py were not edited.
No accounting-core redesign, new generic dedup, app import/composition,
Fingerprint/Suricata/BPF/NIC/RSPAN/configuration changes or production actions.

## Implementation summary

- AF_PACKET/SOCK_RAW is created with protocol zero, preventing receipt from an
  arbitrary interface before explicit bind. Bind selects the supplied interface
  and ETH_P_ALL. Only socket-local receive-buffer/timestamp settings are made;
  no fanout, group membership, ring, transmit path or promiscuous-mode change.
- Linux-only source accepts an existing Ethernet interface; reads admin-UP/carrier
  from sysfs. It never writes interface flags, rings, offloads, sysctls or services.
  There is no hard-coded production interface.
- recvmsg_into uses one 82-byte prefix buffer + bounded ancillary space and MSG_TRUNC
  original wire length; accepted parse_header produces only bounded L2/IP metadata.
  The raw prefix buffer is zeroed after each receive. No application parsing/archive.
- Same R1 account/make_slice code handles native L3 bytes, source-relative direction,
  epoch-aligned half-open identities and separate run UUID/sequence. Optional offline
  synthetic duplicate provenance is never enabled in live mode.
- Architect policy: NO_HEURISTIC_DEDUP, COUNT_AMBIGUOUS_OBSERVATIONS. Output has an
  explicit raw-observation qualification; equal headers/timestamps and retransmission
  are not suppressed or represented as proved unique transmissions.
- Monotonic deadlines close 5s UTC-aligned slices even with no next packet. Startup/
  final open buckets are partial. A healthy full idle interval emits zero; source
  failure emits unavailable, malformed headers degrade, and unknown drop evidence
  never becomes a normal healthy zero.
- Source evidence includes socket open/bind/close, received/rejected/unassigned
  counts, cumulative resetting PACKET_STATISTICS, actual SO_RCVBUF, link checks,
  queue readability at seal, timestamp mode, UTC/monotonic drift, receive backlog,
  slice emission/output-write delay and actual stop vs covered interval end.
- No user packet/slice/output queue or live dedup cache. Received packets are counted
  incrementally. Requested kernel receive buffer <=4MiB, actual <=8MiB; accepted
  record/output limits remain enforced. Output is exclusive-create and bounded.
- Drops/queue-backlog/timestamp uncertainty degrade the run. Late/future events are
  not assigned to a nearest bucket; unassigned frames/native bytes are exposed.
  Since emitted rows are immutable, **whole-run summary must be reviewed** rather
  than accepting an earlier healthy row in isolation.
- Controlled stop/finite completion reads final socket evidence and detaches before
  final output. Open bucket is partial or more severe known quality. SIGINT/SIGTERM
  only request stop and original handlers are restored; exceptions close the socket.

## Focused test evidence

Environment: Windows 10 10.0.19045, Python 3.10.11 x64.
Existing interpreter: `C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe`.
Workdir: `C:\CaptivPortal-Lab\coder-task05-identity-session`.

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\dti-00b-r2-pyc'
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest tests/dti_00b -q --basetemp='C:\CaptivPortal-Lab\tmp\dti-00b-r2-target-final'
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m compileall -q research/dti_00b tests/dti_00b
git diff --check
```

Final focused result: **92 passed in 3.24s**, 0 skipped/failed/errors, exit 0.
compileall exit 0, diff-check exit 0. No broad project suite was run.
R1's small paced smoke cases are included only because the authorized targeted
suite requires existing R1 tests; no new official/Linux/production PERF run occurred.

R2 tests use FakeSocket, FakeClock, synthetic frames and filesystem fixtures only:

| Required proof | Evidence |
|---|---|
| Existing frame/byte accounting | upload IPv4 100 bytes + download IPv6 1280 bytes |
| Upload/download | exact subject-relative counts, native lengths and rate |
| No next packet required | empty source emits at monotonic 5s and 10s |
| Healthy idle | healthy absence true, rate zero |
| Failed source != zero | open/bind/receive/link failure -> source_unavailable |
| Parser errors | malformed header -> degraded, rejection exposed |
| Bounds | 1000 frames streamed; record/output caps; fixed 82-byte buffer |
| Stop | controlled event; restored signals; source closes before final partial output |
| Identity | distinct run UUIDs replay identically; existing make_slice identity equals live |
| No fanout | factory/option-call assertions and source AST option whitelist |
| No production interface | injected socket/probes, interface lab0 only; Windows guard never calls factory |
| R1 compatibility | all 57 retained tests passed unchanged |
| Timing/drop uncertainty | clock step, missing timestamps/stats, resetting drop counters, queue at seal |
| Backpressure | slow output latency/emission delay measured; no buffered slice list |
| Event boundaries | exact 5s event in next bucket; exact duration-end observation excluded |
| No nearest assignment | old kernel timestamp -> explicit unassigned accounting + degraded run |
| Linux link probe | synthetic sysfs admin-UP/carrier/type; no volatile IFF_RUNNING dependency |
| Output preflight | historical output untouched, no capture attempted before exclusive-create succeeds |

## Full BASE-to-R2 file inventory

`git diff --name-status`:

```text
A research/dti_00b/README.md
A research/dti_00b/__init__.py
A research/dti_00b/__main__.py
A research/dti_00b/admission.py
A research/dti_00b/benchmark.py
A research/dti_00b/fixtures.py
A research/dti_00b/live.py
A research/dti_00b/live_capture.py
A research/dti_00b/meter.py
A research/dti_00b/model.py
A research/dti_00b/pcap.py
A research/dti_00b/replay.py
A tests/dti_00b/__init__.py
A tests/dti_00b/test_live.py
A tests/dti_00b/test_meter.py
A tests/dti_00b/test_replay.py
```

`git diff --stat`:

```text
research/dti_00b/README.md       | 264 +
research/dti_00b/__init__.py     |   3 +
research/dti_00b/__main__.py     |  86 +
research/dti_00b/admission.py    |  53 +
research/dti_00b/benchmark.py    | 100 +
research/dti_00b/fixtures.py     | 109 +
research/dti_00b/live.py         | 261 +
research/dti_00b/live_capture.py | 205 +
research/dti_00b/meter.py        | 104 +
research/dti_00b/model.py        | 168 +
research/dti_00b/pcap.py         | 117 +
research/dti_00b/replay.py       |  67 +
tests/dti_00b/__init__.py        |   1 +
tests/dti_00b/test_live.py       | 411 +
tests/dti_00b/test_meter.py      | 246 +
tests/dti_00b/test_replay.py     | 110 +
16 files changed, 2305 insertions(+), 0 deletions(-)
```

`git status --short`: these exact 16 paths are ` A` (intent-to-add, uncommitted).
No unrelated path changed, no staged content. HEAD/tree remain exact baseline.
New source/test/package files are supplied completely in the BASE-to-R2 patch.

## Explicit remaining authority/limitations

No Linux host/root/AF_PACKET/production capture was executed by Coder. Mock proof
does not establish actual kernel visibility, driver timing/queue behavior,
packet-stealing absence, Fingerprint/source-health coexistence or production
capacity. Existing consumer/NIC configuration determines visibility because this
adapter deliberately does not enable promiscuous mode or change any capture setup.

Finite duration bounds the requested capture; filesystem writes can block. Actual
stop and output latency are observable, and final flushing occurs after detach.
No CPU/RAM enforcement, production systemd limits or new resource admission is
claimed. R1 resource characterization is historical unchanged evidence, not a
live-R2 benchmark. Kernel drop counters are this socket's evidence, not a complete
NIC/driver/Fingerprint drop proof. Those independent checks belong to reviewed,
separately authorized Sysadmin admission.

No new implementation blocker found. Production/live acceptance remains pending,
not self-declared PASS. No service/daemon installed; rollback is not applicable.
Coder stops for TechLead R2 source review. No commit, publication or DTI-01 work.
