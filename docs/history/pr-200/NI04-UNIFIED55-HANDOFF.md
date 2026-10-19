# TASK-DTI-NI-04-UNIFIED55 — local implementation handoff

STATUS=HOLD_DIFF_CHECK_SUPPLIED_EVIDENCE_WHITESPACE
Category-cardinality blocker: CLOSED / implemented.
Implementation code and focused tests: complete local candidate for review.
Candidate accepted: NO. All mandatory gates PASS: NO.

## Exact identity / transport

- Worktree: C:\CaptivPortal-Lab\coder-dti-ni-04-unified55
- Branch: feature/dti-ni-04-unified55
- BASE_HEAD: 22cdde5d4168de02d142c840028a4d66167e47f7
- BASE_TREE: a783d1cb3b2f33107ba64878ae5d3d8b80463f38
- HEAD remains BASE_HEAD; candidate uncommitted; worktree DIRTY.
- Candidate tree (external temporary Git index): d110a716c0c2406fc0e00d4e0f862bdeac440524
- Actual repository index: no staged paths.
- Complete replacement patch: C:\CaptivPortal-Lab\handoffs\ni04-unified55-20261012\TASK-DTI-NI-04-UNIFIED55.patch
- PATCH_BYTES: 269658
- PATCH_SHA256: 228f1e2c5ffda1b543450562704919efd186abc54d96387c5cea84054a3d46b2
- Stat: 37 files changed, 4189 insertions, 1 deletion.
- Reverse apply check: PASS, exit 0.
- No commit (including no LAB ONLY commit), push, PR, merge or deployment.

## Blocking disposition requested from TechLead22

Full candidate `git diff --cached --check` using the temporary index FAILS only
for supplied `docs/network-service-recognition/lane-a-evidence-pack-v1.md` lines
4, 5 and 6. Each contains the original two-space Markdown hard line break.
Working file SHA256 is the unchanged supplied identity:
5b57eedbe0dd60194e25d22f18e9701102f7893cf443649de2b406a0b1ef540a.

Ordinary `git diff --check` had PASS but excludes new/untracked files. The full
candidate check is explicitly FAIL, not hidden or reclassified as PASS. No
whitespace normalization was performed. No broader whitespace configuration or
silent exception was applied. Request bounded approval to preserve these three
supplied Markdown lines as an explicit exception, or exact alternative disposition.
STOP implementation pending that answer; current patch/evidence remains available.

## Focused verification actually executed by Coder

Windows, Python 3.10.11, SQLite 3.40.1, Node v24.19.0.
External PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\ni04-unified55-pycache.
Exact final command in candidate worktree:

```powershell
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q tests/network_service_recognition tests/admin_web/test_device_service_intelligence.py tests/admin_web/test_device_service_intelligence_frontend.py --basetemp='C:\CaptivPortal-Lab\tmp\ni04-unified55-final-01'
```

209 PASS / 0 FAIL / 0 ERROR / 0 SKIP, 6.98 seconds.
Production matcher used, no alternate test matcher. Includes all 34 retained Lane
A vectors, TLS/QUIC, same-org YouTube Music negative, DNS-only/ECH/inbound/local/
wrong-device rejection, exact category subsets 1..10, R1 reference digests,
5000/5001 facts, 256/257 batches, 25000/25001 scalar values, 12/13/55 synthetic
Service limits, provenance joins, privacy, fail-closed API, defaults, deadlines,
simultaneous concurrency and Node coordinator timing/strict DTO scenarios.

Compileall PASS (exit 0): new recognition package, both protected readers, changed
Admin/config/settings Python modules, new recognition tests and two Admin Python
test files. Only external pycache used.
Node syntax PASS (exit 0) for app/admin_web/static/admin.js and new CJS self-check.
Existing tracked-change diff-check PASS; complete candidate diff-check FAIL as above.
No existing tests changed. No full/cross-module/official gate executed.

## New files (27)

```text
app/network_metadata/recognition_read_service.py
app/network_metadata_projection/recognition_read_service.py
app/network_service_recognition/__init__.py
app/network_service_recognition/artifacts.py
app/network_service_recognition/canonical.py
app/network_service_recognition/knowledge/recognition-knowledge-manifest-v1.json
app/network_service_recognition/knowledge/recognition-ruleset-v1.json
app/network_service_recognition/knowledge/recognition-taxonomy-v1.json
app/network_service_recognition/matcher.py
app/network_service_recognition/models.py
app/network_service_recognition/read_service.py
app/network_service_recognition/serialization.py
docs/network-service-recognition/NI04-UNIFIED55-RESEARCH-REGISTRY-v1.json
docs/network-service-recognition/README.md
docs/network-service-recognition/lane-a-evidence-pack-v1.md
docs/network-service-recognition/unified55-launch-scope-v1.json
tests/admin_web/device_service_intelligence.cjs
tests/admin_web/test_device_service_intelligence.py
tests/admin_web/test_device_service_intelligence_frontend.py
tests/network_service_recognition/__init__.py
tests/network_service_recognition/fixtures/research-fixtures-v1.json
tests/network_service_recognition/lab_acceptance.py
tests/network_service_recognition/support.py
tests/network_service_recognition/test_artifacts_matcher.py
tests/network_service_recognition/test_limits_vectors.py
tests/network_service_recognition/test_protected_readers.py
tests/network_service_recognition/test_summary.py
```

## Modified files (10), additive integration

```text
app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/runtime.py
app/admin_web/static/admin.css
app/admin_web/static/admin.js
app/admin_web/templates/admin/device.html
app/config.py
app/settings.py
```

Actual permitted composition helpers: runtime.py initializes only optional
readers/local bundle; pages.py adds two flag propagation lines for Device template.
The one removed route line is replaced by a prepended NI-04 API-version branch;
the existing NI-03 conditional and all other error API versions remain intact.
Existing run.py already consumes the Settings pipeline; no entrypoint change.

## Requirement -> implementation

| Requirement | Implementation/evidence |
|---|---|
| Closed immutable canonical tuple, digests, expiry, declared ambiguity | canonical.py, artifacts.py, matcher.py; reference digests and negative tests |
| Ten allowed categories, concrete 1..10 | artifacts.py + category subset/unknown/duplicate/dangling tests; original Lane A unchanged |
| NI-01 bounded protected evidence | new recognition_read_service.py; mode=ro/query_only, 256 refs, provenance/retention, original answer ordinals |
| NI-02B one exact event-time snapshot | new projection recognition_read_service.py; authoritative Site/Device/MAC; no IP reattribution |
| Main read-only bounded orchestration | read_service.py; closes projection transaction before source reads; complete set verified before matching |
| Exact public safe DTO | models.py + serialization.py; no raw source/network identifiers |
| Authenticated same-Site REST / 16 KiB | query_service.py + routes.py; exact codes/Retry-After/no-store; HTTP envelope owns size failure |
| Separate Device Card, bounded coordinator | device.html + scoped CSS + appended admin.js IIFE; production JS exercised by Node tests |
| Default OFF, failure isolation | config.py -> settings.py -> existing composition; no source workers/DB initialization |
| 55 scope, only five admitted | corrected registry + separate launch report; synthetic 55 engine test only |

No SQLite schema/writer/retention/normalizer, NI-03 semantics, Settings control,
Omada, Portal/Auth/CAPPORT, Traffic, Device Fingerprint/Sensor or production units
changed. Existing NI-03 model/read service/frontend and pre-NI04 admin.js bytes
are baseline-identical (Git-normalized line-ending identity tests PASS).

## Exact immutable input / runtime tuple attestation

All runtime artifact IDs/versions and review evidence in feature README.
Semantic tuple (v1 each):

```text
taxonomy 7e122a828c0877d4fb61382646604a2b4a8421a40c4388e513460c84c69c8278
manifest 7ecca6dc42ef73c2dd4b40e4d56d4115078f548cd3693e510f095968be1f0210
ruleset 46d9485b6aea5c6a0b40a4b9a969eed553a4353904a1667fe85cb0620c02a56a
```

Raw JSON SHA256 (unchanged original bytes):

```text
taxonomy 58ff1a1e49cf07229f0247bbeeca6db79acc99b6cd19437aa6245a1ab5c8cfc0
manifest 6f1617441b8ce20aed6d91056a685c9efa444b04cfe79e42f57e7db0091d57a0
ruleset e6493f24b802a21e34fcbc436f2e7b150172d3bab3e04db7cb4c7005466c94c1
research registry 70893ee3ec5ccd283c9bccce7948a5d914d8ad3a8f5ca81785a1654a9cbf79c7
research fixtures 2f4d735737a73000c4035670741ac3d210243f34a49adf20170bcbf3e5c989be
```

Catalog=55; exact rules admitted in candidate=5; production recognitions measured=0
(not executed). No native-app-use claim. X/VK remain HOLD. No extra rule activation.

## Mandatory acceptance matrix / known limitations

| Gate | Environment / ownership | Result |
|---|---|---|
| Coder focused kernel/read/API/frontend | Windows Coder, exact production-source candidate | 209 PASS |
| Complete diff check | Whole 37-file candidate | FAIL: 3 original supplied Markdown lines |
| Native Linux focused / NI-03 and cross-surface compatibility | Owner/TL dedicated clean Linux Lab | PENDING |
| Synthetic max-case RSS <=64 MiB / p50,p95,max <=5s | Owner/TL Linux, lab_acceptance.py prepared not run | PENDING |
| NI-01/NI-02B actual writers + WAL/checkpoint/retention capacity coexistence | Owner/TL Linux | PENDING; resource script is not this proof |
| Non-feature Portal/Auth/CAPPORT latency / regression | Owner/TL differential gate | PENDING |
| Desktop/mobile browser/accessibility acceptance | Owner/TL | PENDING; Node tests are not visual acceptance |
| Official refreshed Central Lab/full acceptance | Owner/TL | PENDING / NOT EXECUTED |

No official FULL PASS, Linux PASS, PERF PASS or accepted-candidate claim.
Owner/TL first reviews source and whitespace disposition, then assigns immutable
Lab candidate and exact refreshed gate commands. No publication until all mandatory
gates pass and Owner separately authorizes it.

## Preservation / repository and production actions

Prior Traffic worktree remains clean at
2097d4b971555bc7f6a747faa6562ef4ac59e02a; no files/history touched.
Current NI04 baseline unchanged. Temporary index creates a review tree/patch only,
not a commit, and leaves actual index unstaged. No production accessed.
Default flag remains OFF. Environment/main-process deployment and rollback notes
are reviewable documentation, not executed service/configuration actions.

## Agent execution summary

Agent/platform: Codex Coder / Windows PowerShell; no subagents.
Mode: authorized local implementation and focused checks; now HOLD for review.
Source/test files: exact inventory above; existing test files modified: NONE.
Unexpected rework: fixture-only local failures corrected during focused development;
final 209 tests green. Full diff surfaced supplied Markdown whitespace, preserved
and reported rather than normalized. Broader/Linux/full gates NOT executed.
Acceptance/publication/deployment/activation: NOT performed.

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
