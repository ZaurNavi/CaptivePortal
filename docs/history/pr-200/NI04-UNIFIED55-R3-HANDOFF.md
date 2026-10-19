# TASK-DTI-NI-04-UNIFIED55 — R3 bounded repair handoff

STATUS=READY_FOR_TECHLEAD22_SOURCE_REVIEW
P1_03_LOCAL_REPAIR=PASS
P1_04_LOCAL_REPAIR=PASS
FULL_ACCEPTANCE=HOLD

## Exact identity / complete replacement patch

```text
BASE_HEAD=22cdde5d4168de02d142c840028a4d66167e47f7
BASE_TREE=a783d1cb3b2f33107ba64878ae5d3d8b80463f38
PRIOR_CANDIDATE_TREE=a91f9ed93a3602a91473a15b98f1a85c634c7b66
CANDIDATE_TREE=078ed0b107cbd4ca2fe2200add9973f35a683319
PATCH_PATH=C:\CaptivPortal-Lab\handoffs\ni04-unified55-r3-20261012\TASK-DTI-NI-04-UNIFIED55-R3.patch
PATCH_BYTES=278767
PATCH_SHA256=dd8293718ffc35015f94bd13995995b61676d84692629b136431f44ac8ce133b
BASE_TO_CANDIDATE_STAT=37 files / 4324 additions / 1 deletion
BRANCH=feature/dti-ni-04-unified55
WORKTREE=C:\CaptivPortal-Lab\coder-dti-ni-04-unified55
HEAD=22cdde5d4168de02d142c840028a4d66167e47f7
WORKTREE_STATE=DIRTY / UNCOMMITTED
ACTUAL_REPOSITORY_INDEX=UNSTAGED
REVERSE_PATCH_APPLY_CHECK=PASS / exit 0
```

The patch is the full BASE-to-candidate replacement, not a small repair delta.
Previous patch/reports are preserved. Candidate tree was calculated with an
external temporary index; there is no implementation or LAB ONLY commit.

## Exact R3 changed-file whitelist (three paths)

Compared with the previously reviewed a91f9ed... tree, only these paths differ:

1. `app/admin_web/static/admin.js`: one early `typeof document === "undefined"`
   return before the NI-04 initializer's first DOM access. Earlier Admin JS bytes,
   NI-04 actual browser path, cadence, backoff and manual-refresh behavior unchanged.
2. `app/admin_web/static/admin.css`: relocate the unchanged scoped NI-04 block
   before the existing NI-03 sentinel. NI-03 suffix exactly equals the baseline
   Git content, including its terminal newline; no selector/rule semantic changes.
3. `tests/admin_web/test_device_service_intelligence_frontend.py`: two new narrow
   tests. Full Admin bundle loads with window but no document; NI-04 alone performs
   no browser work without DOM. NI-03 CSS suffix is byte-identical and NI-04 remains
   exclusively #device-service-intelligence scoped before that suffix.

All other candidate blobs equal the prior reviewed tree. The complete 37-path
inventory (27 new, 10 modified) is unchanged from R1 and is carried by the complete
replacement patch. No legacy test or old Node harness was modified.

## Actual final-candidate verification

| Selection | Windows | Native Ubuntu 22.04 |
|---|---|---|
| NI-04 focused (all prior cases + two new regressions) | 226 PASS / 0 FAIL / 0 SKIP, 11.58s | 226 PASS / 0 FAIL / 0 SKIP, 9.20s |
| Entire tests/admin_web + tests/network_protocol_intelligence | 1256 PASS / 0 FAIL / 0 SKIP, 101.43s | 1256 PASS / 0 FAIL / 0 SKIP, 86.98s |
| compileall | PASS / exit 0, focused changed/new Python scope | PASS / exit 0, app |
| Node syntax admin.js | PASS / exit 0 | PASS / exit 0 |
| Native full candidate diff-check | FAIL / exit 2, only approved three lines | FAIL / exit 2, only approved three lines |
| Exact separate whitespace whitelist audit | PASS | PASS |
| Candidate Git tree / no source drift | exact / PASS | exact / PASS |

Selections overlap and must not be summed as a unique full-repository count.
Collection inventory confirms the 1256-case selection splits into 1206 Admin Web
cases and 50 NI-03 cases; both groups passed completely in both environments.
The 1256-test selection contains the complete Admin Web set and unchanged NI-03
test suite, including all formerly failing legacy Node contracts. No failing
assertion was weakened, skipped, xfailed or deselected.

An initial Windows run also returned 1256 PASS before the final terminal-newline
preservation and stricter byte assertion. It was repeated on the final artifact;
the table uses only the final-candidate run.

### Exact Windows commands / environment

Python: C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe (3.10.11).
SQLite 3.40.1; Node v24.19.0.
PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\ni04-unified55-pycache.

```powershell
python -m pytest -q tests/network_service_recognition tests/admin_web/test_device_service_intelligence.py tests/admin_web/test_device_service_intelligence_frontend.py --basetemp=C:\CaptivPortal-Lab\tmp\ni04-unified55-r3-final-focused-01
python -m pytest -q tests/admin_web tests/network_protocol_intelligence --basetemp=C:\CaptivPortal-Lab\tmp\ni04-unified55-r3-final-admin-01
node --check app/admin_web/static/admin.js
```

The actual Python commands used the explicit interpreter path above, not PATH.
Compileall used the same previously authorized changed/new Python module/test list.

### Native Linux materialization / commands

Fresh Coder validation clone:
`/home/zaur_navi/captivportal-lab/ni04-unified55-coder-r3-20261012`.
Source baseline clone was read only; previous Owner acceptance checkout was not
modified. No packages were installed. Existing qualified interpreter:
`/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python`.
Python 3.10.12, SQLite 3.37.2, Node v24.20.0; pytest/Flask/cryptography/tzdata present.

Local `git clone --no-hardlinks --no-checkout` from the existing native baseline,
detached checkout of exact BASE_HEAD, then `git apply --index` of this exact patch.
Native `git write-tree` returned 078ed0b107cbd4ca2fe2200add9973f35a683319.
No commit was created: baseline HEAD unchanged; candidate staged and source files
match the staged tree. This is isolated Coder validation, not a clean committed
official release artifact or an official Central Lab acceptance result.

```bash
PYTHONPYCACHEPREFIX=/tmp/ni04-unified55-r3-pycache <qualified-python> -m pytest -q tests/network_service_recognition tests/admin_web/test_device_service_intelligence.py tests/admin_web/test_device_service_intelligence_frontend.py --basetemp=/tmp/ni04-unified55-r3-linux-focused-01
PYTHONPYCACHEPREFIX=/tmp/ni04-unified55-r3-pycache <qualified-python> -m pytest -q tests/admin_web tests/network_protocol_intelligence --basetemp=/tmp/ni04-unified55-r3-linux-admin-01
PYTHONPYCACHEPREFIX=/tmp/ni04-unified55-r3-pycache <qualified-python> -m compileall -q app
node --check app/admin_web/static/admin.js
```

Native SQLite 3.37.2 is disclosed, not relabeled as reference SQLite 3.40.1. No SQL
planner assertion/dependency was altered. Whole-repository acceptance remains a
separate Tech Lead/Owner gate after source review.

## Exact whitespace disposition

Full native diff-check is honestly FAIL_WITH_APPROVED_EXACT_EXCEPTION, exit 2.
Both complete native outputs were compared case-sensitively to exactly these
diagnostics and their original added lines:

```text
docs/network-service-recognition/lane-a-evidence-pack-v1.md:4
docs/network-service-recognition/lane-a-evidence-pack-v1.md:5
docs/network-service-recognition/lane-a-evidence-pack-v1.md:6
```

Each line retains exactly two trailing ASCII spaces. No other whitespace finding;
no global whitespace waiver or normalized evidence. Machine-readable proof:
`whitespace-whitelist-audit-r3.json` in this handoff directory.

## Frozen raw identities (confirmed in native Linux candidate)

```text
taxonomy=58ff1a1e49cf07229f0247bbeeca6db79acc99b6cd19437aa6245a1ab5c8cfc0
manifest=6f1617441b8ce20aed6d91056a685c9efa444b04cfe79e42f57e7db0091d57a0
ruleset=e6493f24b802a21e34fcbc436f2e7b150172d3bab3e04db7cb4c7005466c94c1
Registry55=70893ee3ec5ccd283c9bccce7948a5d914d8ad3a8f5ca81785a1654a9cbf79c7
EvidencePack=5b57eedbe0dd60194e25d22f18e9701102f7893cf443649de2b406a0b1ef540a
```

Semantic digests, v1 versions, default-OFF feature flag and protected modules remain
unchanged. Five runtime Lane A rules; 55 research IDs; no new recognition admission.
No schema/writer/retention, Portal/Auth/CAPPORT, NI-03 behavior, Traffic, Settings,
Omada, runtime services or production change.

## Review / full acceptance boundary

Next: TechLead22 source review of the new complete patch/tree. After that, Owner/TL
rematerializes and reruns the required whole-repository Linux acceptance,
writer-reader coexistence, performance/RSS, isolation under load and real-browser/
accessibility gates. Those gates were not executed in this Coder repair round.
No full repository PASS or production eligibility is claimed.

This remains one Unified55 task. Current dirty implementation is preserved and
Coder stops after this handoff.

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
FEATURE_ACTIVATION=NO
PRODUCTION_ACTION=NO
