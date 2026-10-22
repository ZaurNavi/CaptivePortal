# DEPLOY-CONFIG-02 — final publication evidence report

Date: 2026-10-15. Prepared by Coder following the TechLeadJR FINAL PUBLICATION DIRECTIVE. This is the publication identity/evidence summary; independent QA results below are attributed to that directive, not newly executed or independently attested by Coder. It does not substitute for TechLeadJR's raw G0–G3 QA records.

## Final result

```ini
TASK=TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1
PUBLICATION=COMPLETE
PUBLICATION_COMMIT=b64ac972dc74b77ca685d9b610c67ad05c7261db
PARENT=84b80376b13002d435be28eec98b91b9cbf71c63
BASE_TREE=fda2f2dad7c1f9c89d383ef0bef63f8aebfc93b8
PUBLICATION_TREE=ea664b1d49ace86fc8a0c4ab2fc52945531e574a
ACCEPTED_R3_TREE_MATCH=YES
BRANCH=task/captivprod-deploy-config-02
PUSH=PASS
REMOTE_HEAD=b64ac972dc74b77ca685d9b610c67ad05c7261db
REMOTE_HEAD_TREE=ea664b1d49ace86fc8a0c4ab2fc52945531e574a
PR_NUMBER=212
PR_URL=https://github.com/ZaurNavi/CaptivePortal/pull/212
PR_STATE=OPEN
PR_BASE_BRANCH=main
PR_BASE_SHA=84b80376b13002d435be28eec98b91b9cbf71c63
PR_HEAD_BRANCH=task/captivprod-deploy-config-02
PR_HEAD_SHA=b64ac972dc74b77ca685d9b610c67ad05c7261db
PR_HEAD_TREE=ea664b1d49ace86fc8a0c4ab2fc52945531e574a
COMMITS=1
CHANGED_FILES=15
PRODUCTION_PYTHON_FILES=3
ADDITIONS=888
DELETIONS=51
WORKTREE=CLEAN
GIT_STATUS_PORCELAIN=EMPTY
GITHUB_MERGEABLE=YES
GITHUB_MERGEABLE_STATE=clean
MERGED=false
AUTO_MERGE=null
```

PR title: **TASK-CAPTIVPROD-DEPLOY-CONFIG-02 — Configurable Fingerprint Sensor and Portal Producer**.

Publication commit subject: `DEPLOY-CONFIG-02: configure Fingerprint Sensor and Portal Producer`.

## Directly verified publication checks

1. Before staging, local HEAD, base tree and branch matched the accepted baseline and task branch. `git diff --exit-code ea664b1d49ace86fc8a0c4ab2fc52945531e574a` returned 0: working candidate matched R3 exactly.
2. Fresh uncommitted patch export used `git diff --binary --full-index --output=precommit-R3.patch`. Size **69329 bytes**, SHA256 **51c39c08c15663c0d4f9a8964c378257dae34be90edcbc7f6415805e11da7d55**, exact accepted artifact.
3. `git diff --check` and staged `git diff --cached --check`: PASS. No unauthorized/untracked files; actual staging included only the 15 named files below.
4. `git write-tree` before commit matched **ea664b1d49ace86fc8a0c4ab2fc52945531e574a**. One ordinary publication commit was created directly on exact base, without synthetic QA commits or history rewrite.
5. Immediately after commit, `HEAD^{tree}` matched accepted R3, `HEAD^` matched base, and `git status --porcelain` was empty.
6. `git fetch origin` and the GitHub main branch API both confirmed **main remained 84b80376b13002d435be28eec98b91b9cbf71c63**. Main was checked again before push and PR creation. No rebase/merge-main/amend was required or performed.
7. Normal non-force `git push -u origin task/captivprod-deploy-config-02`: PASS. `git ls-remote` confirmed exact remote branch head and unchanged main.
8. Exactly one PR was created to main, then attached to this Codex task. GitHub REST PR metadata, commit tree/parent and all PR filenames were read back and matched the accepted identities and exact allowlist. PR has one commit, is OPEN, merged=false and auto_merge=null. GitHub reports mergeable=true / clean; this does not authorize or perform merge.
9. Final local HEAD/tree and clean worktree rechecked. No tests, source fixes, formatting, dependency changes, production commands or service actions were performed during publication.

CI snapshot: combined commit status **pending**, zero individual statuses; PR `statusCheckRollup` null. No CI PASS claimed. CI status is independent from the approved task-scoped QA acceptance.

## Accepted QA — attributed, not rerun for publication

Authority: TechLeadJR FINAL PUBLICATION DIRECTIVE, reporting Chief Architect approval of **DEPLOY-CONFIG-02-DIFF-ACCEPTANCE-v1**, explicit informed Owner exception approval, **G0–G3 PASS**, implementation QA PASS and task differential acceptance PASS for this exact R3 artifact.

| Gate / evidence | Exact reported result |
| --- | --- |
| Windows direct full candidate | 7944 PASS / 250 FAIL / 34 SKIP |
| Windows differential | All 250 failures identical to baseline; candidate-only FAIL=0 |
| Linux full candidate | 8224 PASS / 3 FAIL / 1 SKIP |
| Linux failure attribution | Two inherited SQLite planner cases; one QA Unix-socket path-length case |
| Windows focused Sensor/Portal | 271 PASS |
| Linux focused Sensor/Portal | 271 PASS |
| Linux T05 | 33 PASS |
| Direct TLS | 14 PASS |
| Real disposable Evidence receiver TLS | 10 PASS |

**OFFICIAL_WINDOWS_V7=NOT_RUN_ON_R3 / NOT_PASSED. LINUX_FULL=FAIL_BASELINE_QA_PATH_ATTRIBUTED. TASK_DIFF_ACCEPTANCE=PASS under the separately approved task-scoped route.** Neither official Windows V7 nor Linux full is labeled PASS. No DEPLOY-CONFIG-01 exception is automatically carried over. Overlapping focused/T05 counts are not added into a misleading unique-case total.

Prior Coder R3 evidence independently retained: Windows original W01 three cases 3 PASS; Windows focused 271 PASS; Linux focused 271 PASS; Linux T05 33 PASS; no skips/errors/failures; both-platform compileall PASS and diff-check PASS. No such tests were rerun during publication.

## Evidence references

- PR and durable acceptance summary: https://github.com/ZaurNavi/CaptivePortal/pull/212
- Exact commit: https://github.com/ZaurNavi/CaptivePortal/commit/b64ac972dc74b77ca685d9b610c67ad05c7261db
- Precommit exact patch: `C:\CaptivPortal-Lab\handoffs\captivprod-deploy-config-02-publication-20261015\precommit-R3.patch`.
- R3 full handoff: `C:\CaptivPortal-Lab\handoffs\captivprod-deploy-config-02-r3-20261015\R3-HANDOFF.md`.
- R3 source hashes / unchanged-file proof: sibling `verification.json`.
- R3 focused logs/JUnit: sibling `windows-three.log/xml`, `windows-focused.log/xml`, `linux-focused.log/xml`, `linux-t05.log/xml`; these retain the exact Coder test commands and outcomes.
- Architect method: `C:\Users\Zaur Navi\Downloads\CAPTIVPORTAL-DEPLOY-CONFIG-02-DIFF-ACCEPTANCE-v1-CHIEF-ARCHITECT-DECISION-2026-10-15.md`.
- Independent final QA/Owner signoff source: user's **TECHLEADJR FINAL PUBLICATION DIRECTIVE**, 2026-10-15. No separately hosted final signed TechLeadJR QA report URL was provided to Coder; the independent figures here and in the PR are explicitly sourced to that directive.
- Raw GitHub read-back snapshots in this publication evidence directory: `pr-212.json`, `remote-commit.json`, `pr-files.json`, `ci-status.json`.
- `PR-BODY.md` contains the submitted PR description. Lab evidence/raw logs/secrets were not added to the repository.

## Exact committed files

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

Scope is unchanged from accepted R3. This publication does not modify runtime, producers, Evidence receiver authority, models, schema, AF_PACKET/BPF, Auth/CAPPORT, NI or systemd. Config parsing never implies receiver registration or source/classification admission.

```ini
NEW_SOURCE_CHANGES=NO
ADDITIONAL_IMPLEMENTATION_COMMITS=NO
QA_SYNTHETIC_COMMITS_PUBLISHED=NO
REBASE=NO
HISTORY_REWRITTEN=NO
FORCE_PUSH=NO
TESTS_RERUN_DURING_PUBLICATION=NO
MERGE=NO
DEPLOY=NO
SERVICE_RESTART=NO
SENSOR_PORTAL_ACTIVATION=NO
EVIDENCE_SOURCE_REGISTRATION=NO
PRODUCTION_ACTION=NO
NEXT_ACTION=OWNER_TECHLEADJR_PR_REVIEW
CODER_HOLD=YES
```
