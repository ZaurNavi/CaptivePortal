# CaptivPortal KB Reconciliation Report — 2026-08-26

## Baseline

- Repository main: `53f617b3ac0155d0d647e58e98309927f9a4d318`
- Production deployed HEAD: `53f617b3ac0155d0d647e58e98309927f9a4d318`
- Production branch: `main`
- Production working tree: clean
- TASK: `TASK-HOME-ACTIVITY-01`
- Runtime/code changes in this deliverable: **none**

## Drift found

1. Root README EN/RU still described Home Activity as the next change-intent and used old repository/runtime checkpoints.
2. `docs/README.md` and `docs/module-index.md` explicitly said Home Activity was not current code.
3. `docs/project-inventory.md` still used PR #62 / `dfc62b...`, omitted Home Activity, and retained the stale 1985-test Central Lab evidence.
4. `docs/testing.md` still published the earlier `1985 passed / 30 skipped` baseline instead of the exact-artifact final run for `53f617b...`.
5. `docs/modules/admin-web.md` explicitly said Home Activity was not current.
6. `docs/modules/analytics.md` omitted `HomeActivityReadService`.
7. `docs/modules/portal-entry.md` documented only legacy `ssid`, not canonical `ssidName` + conflict semantics.
8. `docs/modules/capport.md` omitted the final CAPPORT SSID propagation chain.
9. `docs/modules/visit-lifecycle.md` did not document ingress SSID as Visit-opening evidence.
10. `docs/modules/current-state.md` omitted PR #71/#72 startup-integrity and Python 3.10 SQLite compatibility behavior.
11. `docs/configuration.md` had no Home Activity configuration group / Site coverage context.
12. `docs/architecture.md` still modeled Admin/Analytics without Home Activity and lacked the final ingress SSID no-guess contract.
13. `docs/deployment.md` did not record the first-restart acceptance rule or the accepted first restart.
14. `docs/logging.md` did not distinguish the missing `current_state.runtime_started` event as an observability gap.
15. There was no current `docs/modules/home-activity.md`.
16. There was no Home Activity finalization postmortem.

## Documents changed by the patch

- `README.md`
- `README_RU.md`
- `docs/README.md`
- `docs/module-index.md`
- `docs/project-inventory.md`
- `docs/architecture.md`
- `docs/configuration.md`
- `docs/testing.md`
- `docs/deployment.md`
- `docs/logging.md`
- `docs/modules/portal-entry.md`
- `docs/modules/capport.md`
- `docs/modules/visit-lifecycle.md`
- `docs/modules/current-state.md`
- `docs/modules/analytics.md`
- `docs/modules/admin-web.md`
- NEW `docs/modules/home-activity.md`
- NEW `docs/postmortems/TASK-HOME-ACTIVITY-01-2026-08-26.md`

## Current state after reconciliation

- Home Activity: Implemented / Merged / Central Lab PASS / Production deployed / Core production acceptance PASS.
- Authorized Visits: Visit-opening cohort from persisted Visit Lifecycle facts; AuthSession count is not used.
- Guest scope: canonical `CURRENT_STATE_CLIENT_SSIDS_JSON`.
- Unknown/unproven guest scope: unavailable, never false zero.
- Traffic: estimated completed-session offline evidence; `completed_session_end`; not WAN/billing/Current State traffic.
- Visits and Traffic: independent status/coverage.
- Artificial Home Activity 31/90-day ceiling: none.
- CAPPORT SSID propagation: proven through Visit opening.
- External Portal: `ssidName` canonical, `ssid` fallback, conflict => unproven.
- Visits production coverage from: `2026-08-26T17:46:55.982Z`.
- Traffic coverage start: **null / not proven**.
- Production Visit aggregate after boundary: 14/14 verified guest, 0 integrity anomalies, 0 unproven scope.
- Current State first-restart acceptance: PASS.
- Central Lab final exact-artifact result: `2100 passed / 30 skipped / 5 deselected`, strict regressions 0, compatibility 2 WARN / 3 PASS, RESULT PASS.
- Production Python: `3.10.12`.

## History moved out of current behavior

Historical/postmortem only:
- false zero on unproven scope;
- missing CAPPORT SSID propagation;
- External Portal `ssidName` mismatch;
- Current State self-timeout misclassification;
- Python 3.10 SQLite constant compatibility omission;
- stale Central Lab PASS that did not validate the final artifact.

## Remaining gaps

1. `traffic_coverage_from_utc = null`: Traffic coverage is not yet a proven complete-history boundary.
2. Time-based Visits coverage:
   - Today starts fully after Visits boundary from `2026-08-27 00:00 Asia/Baku`;
   - Last 24h is fully inside proven Visits coverage after `2026-08-27 21:46:55 Asia/Baku`;
   - Last 7d / 30d require natural accumulation.
3. Observability gap: expected `current_state.runtime_started` event was not found despite persisted Current State success evidence. This is not an active runtime defect.

## Validation / application

This is a docs-only patch prepared against exact main `53f617b3ac0155d0d647e58e98309927f9a4d318`.

Before applying locally:

```powershell
git fetch origin
git switch main
git pull --ff-only
git rev-parse HEAD
git status --short
git apply --check .\CaptivPortal_KB_Reconciliation_2026-08-26.patch
```

Expected HEAD must equal:

```text
53f617b3ac0155d0d647e58e98309927f9a4d318
```

Then, only after review:

```powershell
git apply .\CaptivPortal_KB_Reconciliation_2026-08-26.patch
git diff --check
git status --short
```

No commit, push, PR, merge or production operation is part of this handoff.
