# TASK-DTI-NI-04-UNIFIED55-R7 — Dev Handoff

STATUS=BOUNDED_CODE_HANDOFF_READY_FOR_TECHLEAD_SOURCE_REVIEW
SOURCE_CHANGED=YES
RESEARCH_PERFORMED=NO
55_OF_55_RELEASE_ADMISSION=HOLD (TechLead-owned Messenger/Viber decisions)

This is software delivery, not a research, architecture or admission report.
It implements only the supplied frozen 53-rule candidate. It does not redefine
53 software-supported rule candidates as 55 real detections or complete release.

## Exact base / candidate / complete replacement patch

```text
BASE_HEAD=54ce5569b4799b097807399560badc2149c2502c
BASE_TREE=078ed0b107cbd4ca2fe2200add9973f35a683319
BRANCH=feature/dti-ni-04-unified55-r7
WORKTREE=C:\CaptivPortal-Lab\coder-dti-ni-04-unified55-r7
HEAD=54ce5569b4799b097807399560badc2149c2502c
WORKTREE_STATE=DIRTY / UNCOMMITTED
ACTUAL_GIT_INDEX=UNSTAGED
CANDIDATE_TREE=d879f5113319c334faf2bf9ae7b8bea7cfdc977e
PATCH_PATH=C:\CaptivPortal-Lab\handoffs\ni04-unified55-r7-20261012\TASK-DTI-NI-04-UNIFIED55-R7.patch
PATCH_BYTES=166114
PATCH_SHA256=912abbc2a61c4fdb5d289a995dc3be95c5c466a65ccc31b8093f1a191075fa9b
STAT=8 files changed / 210 insertions / 3 deletions
REVERSE_APPLY_CHECK=PASS / exit 0
FULL_DIFF_CHECK_WINDOWS=PASS / exit 0
FULL_DIFF_CHECK_LINUX=PASS / exit 0
```

The tree was calculated with an external temporary index and independently
reconstructed in a fresh native Linux clone. No commit was created. The patch is
complete against the exact merged-PR-200 baseline, not a delta requiring another
uncommitted candidate. Original publication worktree remains clean at 8f313458...

## Exact changed files

Only modified existing production file:

```text
app/network_service_recognition/artifacts.py
```

Only new paths:

```text
app/network_service_recognition/knowledge/recognition-taxonomy-v2.json
app/network_service_recognition/knowledge/recognition-knowledge-manifest-v2.json
app/network_service_recognition/knowledge/recognition-ruleset-v2.json
tests/network_service_recognition/fixtures/r7-techlead/TECHLEAD-55-HOST-DECISIONS.json
tests/network_service_recognition/fixtures/r7-techlead/TECHLEAD-55-SYNTHETIC-TEST-VECTORS.json
tests/network_service_recognition/fixtures/r7-techlead/TECHLEAD-RELEASE-BLOCKERS.json
tests/network_service_recognition/test_r7_supplied_bundle.py
```

Source change is confined to load_local_bundle(): atomically select the exact
SHA-pinned v2 tuple, then use unchanged load_bundle() validation. No filename
discovery, environment-selected directory, rule override, network fallback,
runtime auto-refresh or subset activation. Explicit version=1 selects the original
SHA-pinned tuple for software rollback; invalid/missing v2 never falls back to v1.
Unknown/non-integer version selectors and non-pinned contents are rejected safely.

No matcher, NI-01/NI-02B protected reader, API, UI, cadence/backoff, feature flag,
schema, DB, writer, worker, retention, auth, Site scoping or protected module change.
Old tests/contracts/README/evidence and original artifacts are preserved. Existing
Admin composition handles the closed-loader failure; a new actual-runtime
composition test confirms only NI-04 becomes unavailable with safe logs.

## Supplied immutable inputs — copied, not authored

| v2 file | Raw SHA256 | Semantic SHA256 |
|---|---|---|
| recognition-taxonomy-v2.json | 9dfc0a2ed699f09a4f70e32f30e2d259d96f0f70eb2e8eb06366e5198486c7ee | 0d6a9898d41e8a40863eab1582781e394752a0529b51dc4e92075c592abccfc2 |
| recognition-knowledge-manifest-v2.json | 8f09b6cc685a103a9b4515367980ccefbaa9755a28134b9c6b184cad3e1834f3 | 148bf04201080ebbb10245bfbcd7d05aef521eff3e633bb6b1f734912200b203 |
| recognition-ruleset-v2.json | 595c6982ddf2625de1dbf0262a8da68e5e0cfcb12894a9883cf21bc63a226db8 | 9c6a89c5dcf4f69396fef0645d19f52ae57312944a0308f1fd541f4c92a7ffe6 |

All version 2; schema_version 1. Data counts verified mechanically by existing app
validator: 55 stable taxonomy Service IDs, ten categories, 57 sources, 53 active
exact-SNI candidate rules. Messenger/Viber have no active rule. Facebook host
resolves only Facebook under the supplied expectations. No native-app/action claim.

Fixture raw identities:

```text
HOST_DECISIONS_JSON=60022efb11ca4f00dc9c79ed2256b4b072c9dae408d2f083b693cbc979744151
SYNTHETIC_VECTORS_JSON=2c79d7b99d115cdef99296be26ba6663e14b319dc48f5fbe1ab5367d45535092
RELEASE_BLOCKERS_JSON=ced3c7b1eae65049f19b2ce1936d9c02024cf8bca658275a930521efa1146b66
HOST_DECISIONS_CSV=fc659fd5d5da493995b1bb0578b6a60eca424f1d3b5d50f31b64a2944a4308ff
```

The supplementary CSV is TechLead evidence, not a runtime/test dependency. Its
19554 original bytes (56 CRLF lines) are preserved alongside this Dev Handoff as
TECHLEAD-55-HOST-DECISIONS.csv, outside Git. No CSV normalization/hash change and
no broader whitespace exception. Tests use the supplied equivalent authoritative
JSON and all supplied vectors. This keeps non-code CSV evidence out of the patch.
The originally supplied ZIP remains unchanged in Downloads.

Existing v1/registry/evidence raw identities remain unchanged:

```text
taxonomy_v1=58ff1a1e49cf07229f0247bbeeca6db79acc99b6cd19437aa6245a1ab5c8cfc0
manifest_v1=6f1617441b8ce20aed6d91056a685c9efa444b04cfe79e42f57e7db0091d57a0
ruleset_v1=e6493f24b802a21e34fcbc436f2e7b150172d3bab3e04db7cb4c7005466c94c1
Registry55=70893ee3ec5ccd283c9bccce7948a5d914d8ad3a8f5ca81785a1654a9cbf79c7
EvidencePack=5b57eedbe0dd60194e25d22f18e9701102f7893cf443649de2b406a0b1ef540a
```

All legacy rule/taxonomy semantics remain tested; original source/rule review dates
in v1 bytes unchanged. The supplied v2 dates are used verbatim. No research-only
prototype is copied or selectable. The supplied independent oracle was read as
reference, not executed: it refers to an external /mnt/data legacy ZIP absent
from this handoff. Real production app loader/matcher tests were used instead.

## Local developer verification

| Selection | Windows result | Native Ubuntu 22.04 result |
|---|---|---|
| Focused NI-04/R7 + API/frontend | 583 PASS / 0 FAIL / 0 SKIP, 9.70s | 583 PASS / 0 FAIL / 0 SKIP, 11.36s |
| All 330 supplied vectors (within focused selection) | 330/330 expected outcomes | 330/330 expected outcomes |
| Complete Admin Web + NI-03 | 1256 PASS / 0 FAIL / 0 SKIP, 99.73s | included in 2063 PASS below |
| NI-01/NI-02B/Portal/Auth/CAPPORT protected regression | 617 PASS / 186 FAIL / 4 SKIP, 39.75s | included in 2063 PASS below |
| Admin + NI-03 + protected regression combined | selections above | 2063 PASS / 0 FAIL / 0 SKIP, 112.48s |
| Same protected selection on exact Windows baseline | 617 PASS / 186 FAIL / 4 SKIP, 41.81s | not rerun |
| Compileall / Node syntax | PASS / exit 0 | PASS / exit 0 |

All old tests remain unchanged. New file has 357 cases, including the 330 supplied
vectors. Every vector exercises production matcher (DNS-only rejection at matcher
boundary) and the normal read/serializer path; it is not a test-owned matcher.
Additional cases cover full taxonomy IDs, source refs/expiry, source/peer context,
wrong Site/Device/inbound/local/ECH, safe public DTO, missing/mixed/stale/unpinned
files, strict selection, explicit v1 rollback and isolated actual Admin composition.

Selections overlap; do not sum them into a full-repository total. No skip/deselect/
xfail/assertion weakening was introduced. An initial new-test import typo was
fixed locally; final focused selection is green on both platforms.

### Exact commands

FOCUSED:

```text
python -m pytest -q tests/network_service_recognition tests/admin_web/test_device_service_intelligence.py tests/admin_web/test_device_service_intelligence_frontend.py
```

ADMIN_NI03:

```text
python -m pytest -q tests/admin_web tests/network_protocol_intelligence
```

PROTECTED:

```text
python -m pytest -q tests/network_metadata tests/network_metadata_projection tests/device_fingerprint_portal tests/test_auth_retry.py tests/test_auth_health.py tests/test_auth_telemetry.py tests/test_capport_routes.py tests/test_capport_service.py tests/test_capport_telemetry.py tests/test_portal_entry.py
```

Linux regression command concatenated ADMIN_NI03 and PROTECTED selections in one
pytest execution. All runs used exact explicit interpreters and external basetemp:

- Windows: C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe, Python 3.10.11,
  SQLite 3.40.1, Node v24.19.0. External pycache ni04-unified55-r7-pycache. Basetemps:
  ni04-unified55-r7-final-focused-02, ni04-unified55-r7-final-admin-01,
  ni04-unified55-r7-protected-01 under C:\CaptivPortal-Lab\tmp.
- Windows exact baseline: C:\CaptivPortal-Lab\ni04-unified55-r7-baseline-verification-20261012;
  basetemp ni04-unified55-r7-baseline-protected-01; explicit same interpreter.
- Linux: /home/zaur_navi/captivportal-lab/ni04-unified55-coder-r7-20261012;
  existing /home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python,
  Python 3.10.12, SQLite 3.37.2, Node v24.20.0. /tmp/ni04-unified55-r7-pycache;
  /tmp/ni04-unified55-r7-focused-01 and /tmp/ni04-unified55-r7-regression-01.

Windows compileall covered app/network_service_recognition and its tests; Linux
compileall covered app. Node --check used unchanged app/admin_web/static/admin.js.
Fresh native clone reconstructed the patch/index exact tree without a commit;
no package installation or environment/global/perf-venv changes were made.

## Baseline exceptions / limits

Windows protected failures are preserved as FAIL, not relabeled PASS. The exact
186 failing node-ID set matches exact BASE_HEAD with zero additions/removals;
representative traceback is the pre-existing POSIX os.pread call unavailable on
Windows. Machine-readable comparison: windows-protected-baseline-comparison.json.
Baseline JUnit output is outside Git. No unrelated production/test fix attempted.

The two historical full-suite native SQLite 3.37.2 planner failures are still
known baseline exceptions. This R7 scoped run does not execute those whole-suite
gates or relabel them PASS. No full repository/official Central Lab, live visitor
capture, source-admission assessment, performance/RSS/load analysis, browser
release acceptance or production gate was performed in this code-only task.

TechLead must review this candidate and owns all remaining release/evidence
decisions, especially the two not-admitted slots. No correcting PR or joint
deployment is authorized by the bounded 53-rule software handoff.

SOURCE_CHANGED=YES (load_local_bundle only)
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
FEATURE_ACTIVATION=NO
PRODUCTION_ACTION=NO

Coder stops for TechLead source review. Unified55 remains one release task.
