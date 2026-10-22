# TASK-DTI-NI-04-UNIFIED55 — PATCH REVIEW R1 bounded repair handoff

STATUS=READY_FOR_TECHLEAD22_SOURCE_RE_REVIEW
P1_01_LOCAL_REPAIR=PASS
P1_02_LOCAL_REPAIR=PASS
WHITESPACE_BLOCKER=CLOSED_BY_EXACT_APPROVED_EXCEPTION
Candidate accepted=NO; mandatory Linux/full/PERF/browser gates remain PENDING.

This handoff replaces the status/test/identity sections of the prior local handoff.
Historical patch/report are retained unchanged; no additional production scope.

## Identity and complete replacement patch

```text
WORKTREE=C:\CaptivPortal-Lab\coder-dti-ni-04-unified55
BRANCH=feature/dti-ni-04-unified55
BASE_HEAD=22cdde5d4168de02d142c840028a4d66167e47f7
BASE_TREE=a783d1cb3b2f33107ba64878ae5d3d8b80463f38
HEAD=22cdde5d4168de02d142c840028a4d66167e47f7
WORKTREE_STATE=DIRTY / UNCOMMITTED
PREVIOUS_REVIEW_TREE=d110a716c0c2406fc0e00d4e0f862bdeac440524
CANDIDATE_TREE=a91f9ed93a3602a91473a15b98f1a85c634c7b66
PATCH_PATH=C:\CaptivPortal-Lab\handoffs\ni04-unified55-r1-20261012\TASK-DTI-NI-04-UNIFIED55-R1.patch
PATCH_BYTES=276260
PATCH_SHA256=aa6d6dd6039da6c5dcca3c6d8881cd12355939fdf55582bfe114bfa0d8047385
COMPLETE_BASE_TO_CANDIDATE_STAT=37 files / 4287 additions / 1 deletion
REVERSE_APPLY_CHECK=PASS / exit 0
ACTUAL_REPOSITORY_INDEX=UNSTAGED
```

Candidate tree was computed with an external temporary index, not a commit.
All repair-vs-prior-tree changed paths match exactly the six-file whitelist below.

## Exact repair files / changes (six only)

1. `app/network_metadata_projection/recognition_read_service.py`: add internal
   device_ip/device_port from existing NI-02B columns to the protected fact DTO;
   validate canonical IP and bounded nullable port. No schema/writer alteration.
2. `app/network_service_recognition/read_service.py`: compare retained NI-01
   `(src_ip, src_port, dst_ip, dst_port, transport_protocol)` with authoritative
   NI-02B `(device_ip, device_port, peer_ip, peer_port, transport_protocol)`.
   Entire fact set is verified before matching; any mismatch is source_unavailable.
   Legitimately expired endpoints retain existing limited-coverage behavior.
3. `app/admin_web/static/admin.js`: retain an absolute next-automatic deadline.
   First visible request and manual Refresh remain immediate with the existing
   one-in-flight/manual-coalescing gate. Automatic visibility/observer events
   schedule only the remaining delay. Success waits 120 seconds; failures retain
   120/300/600 backoff. Neutral cancellation retains its dispatch cadence anchor.
4. `tests/network_service_recognition/test_summary.py`: extend synthetic exact
   fact shape, add 15 endpoint assertions/cases (TLS/QUIC positives, independent
   source IP/port and peer/protocol negatives, multi-fact all-or-nothing before
   matcher invocation, and preserved legitimate endpoint expiry).
5. `tests/network_service_recognition/test_protected_readers.py`: prove real
   protected snapshot returns the existing authoritative device IP/port exactly.
6. `tests/admin_web/device_service_intelligence.cjs`: fake timers now advance to
   their deterministic due time; test 5-second hide/show, >=120-second visibility
   return, repeated intersection/visibility callbacks, remaining-delay timer,
   300/600 backoff preservation, cancellation anchor and immediate manual Refresh.

No artifact/taxonomy/registry/evidence bytes, other source, API schema, source
writers, retention, NI-03, feature flag, deployment or architecture was changed.

## Exact complete candidate file inventory (unchanged 37 paths)

Modified existing paths (10):

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

New paths (27):

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

## Focused verification actually run

Windows; Python 3.10.11; SQLite 3.40.1; Node v24.19.0.
External pycache: C:\CaptivPortal-Lab\tmp\ni04-unified55-pycache.

```powershell
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q tests/network_service_recognition tests/admin_web/test_device_service_intelligence.py tests/admin_web/test_device_service_intelligence_frontend.py --basetemp='C:\CaptivPortal-Lab\tmp\ni04-unified55-r1-01'
```

224 PASS / 0 FAIL / 0 ERROR / 0 SKIP, 8.08 seconds. All prior 209 tests remain
present/green; 15 new Python cases added. The same focused command also executes
the production NI-04 JavaScript coordinator with the expanded Node scenarios.
Existing protected NI-03 assets and pre-NI04 JS prefix identity checks remain green.

Compileall: PASS / exit 0, same focused changed/new Python scope as prior handoff.
Node --check: PASS / exit 0 for production admin.js and the CJS harness.
Full repository, cross-module, official Central Lab, Linux/PERF and browser visual
acceptance: NOT RUN. Prepared lab resource helper was not executed.

## Native full diff check and separate exact whitelist proof

`git diff --cached --check` on the complete external-index candidate:
FAIL / exit 2 WITH APPROVED BOUNDED EXCEPTION, not unqualified PASS.

Complete failure set:

```text
docs/network-service-recognition/lane-a-evidence-pack-v1.md:4
docs/network-service-recognition/lane-a-evidence-pack-v1.md:5
docs/network-service-recognition/lane-a-evidence-pack-v1.md:6
```

Separate audit=PASS. Each original line ends in exactly two ASCII spaces (preceded
by a non-whitespace character). The complete native output was compared case-
sensitively to exactly those three diagnostics plus those three original added
lines; no other native finding or output is permitted. No global whitespace
configuration change, suppressed check or artifact normalization was used.
Machine-readable proof: `whitespace-whitelist-audit-r1.json` alongside this handoff.

## Immutable input attestation — recalculated after repairs

```text
taxonomy raw=58ff1a1e49cf07229f0247bbeeca6db79acc99b6cd19437aa6245a1ab5c8cfc0
manifest raw=6f1617441b8ce20aed6d91056a685c9efa444b04cfe79e42f57e7db0091d57a0
ruleset raw=e6493f24b802a21e34fcbc436f2e7b150172d3bab3e04db7cb4c7005466c94c1
registry raw=70893ee3ec5ccd283c9bccce7948a5d914d8ad3a8f5ca81785a1654a9cbf79c7
evidence pack raw=5b57eedbe0dd60194e25d22f18e9701102f7893cf443649de2b406a0b1ef540a
```

All three semantic digests and v1 versions remain unchanged and focused-tested.
Catalog 55 / exact admitted Lane A rules 5 / no new rule or production activation.
All non-repair candidate blobs equal the previously reviewed candidate tree.

## Acceptance boundaries and next action

Local repair evidence is not Tech Lead acceptance. Next: TechLead22 source re-review.
Native Linux, full official gates, actual writer/reader coexistence, RSS/performance,
differential Portal/Auth/CAPPORT, NI-03 compatibility and browser/accessibility
remain PENDING under separate Owner/TL gate ownership. No full PASS is claimed.
Current worktree remains dirty and baseline/branch unchanged; actual index unstaged.
No other worktree or production/service/configuration was accessed or changed.

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
FEATURE_ACTIVATION=NO
PRODUCTION_ACTION=NO
