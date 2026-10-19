# CaptivPortal — QIO-01D night production deployment runbook

**Status 2026-10-16:** `PLAN_READY / EXECUTION_NOT_STARTED / OWNER_NIGHT_WINDOW_GO_PENDING`. This is a procedure, not a record of a completed deployment.

## Frozen release identity

- GitHub PR #219: merged into `main`.
- Accepted merge HEAD: `191beda1f23f8f466d2431f42e57571815d85778`.
- Accepted exact Git tree: `3f6d0a05c5d893d3139db44a1692c81e67fd6c6e` (identical to Tech Lead-accepted Coder tree).
- Production at 2026-10-16 15:54 Asia/Baku: `/opt/CaptivePortal` still `e2cbd96916d8a81f07f0d79a1a745f593ccb5114`; `captive-portal.service` active, PID `1887236`, `NRestarts=0`.
- QIO-01D startup toggle: `VISIT_LIFECYCLE_READER_SCAN_TELEMETRY_COMPACT_ENABLED=false` by default; existing production setting absent. **Deploy with default OFF.** Do not enable compact, edit Grafana, or mutate data as part of this rollout.
- PR #215 remains out of scope, including any pending draft changes.

## Gate A — Owner-selected low-load time, not now

1. Obtain **separate explicit Owner GO** for the selected nighttime deployment window; do not automatically deploy because the PR merged. Re-check live guest and hypervisor CPU/PSI/HDD pressure and application traffic. If physical disk remains saturated, delay.
2. GitHub and host HEAD/tree must still match frozen expected SHA/tree. If `main` advances or another deployment changes production, **STOP / revalidate**, not ad-hoc merge, cherry-pick or silent baseline drift.
3. Check systemd status, current process PID/restarts, portal HTTPS and guest auth baseline. Check exact runtime settings, mounted paths and absence of `VISIT_LIFECYCLE_READER_SCAN_TELEMETRY_COMPACT_ENABLED=true` in every relevant environment/settings source. Check Omada strict TLS trust file/name still resolves correctly. No new secret extraction.
4. Read-only Git cleanliness, file permissions, available disk and backup/rollback path verified. Record start timestamps and old code commit. Do not copy live SQLite files with naive filesystem copy while writers run; QIO-01D does **not** require a schema migration.
5. Preserve root-only env backup with owner/mode, change only if needed to enforce `compact=false`; keep previous QIO-01B Omada TLS configuration intact. Do not turn on compact. Preserve approved Lab test evidence; full gates already ran on exact tree.

## Gate B — controlled code-only cutover

1. Stop `fingerprint-evidence.service` first, then `captive-portal.service` per project deployment procedure; verify inactive before checkout. No unrelated service restarts.
2. `git fetch` to obtain the exact merged SHA and verify tree; switch production worktree only to `191beda1f23f8f466d2431f42e57571815d85778`, not merely whatever `origin/main` happens to be at that moment; verify clean checkout and exact `HEAD^{tree}`.
3. Start `captive-portal.service`; restore `fingerprint-evidence.service` and verify both active. Note initial PID, timestamp, restart count. Do not run heavy SQLite checkpoint/VACUUM/reindex, nor eager large tests on production.
4. **Allow a full 20-minute portal warm-up/observation window** because QIO-01B took ~11 minutes for cold SQLite reads before web 200. An early reverse-proxy 502 while the app is still initializing is not by itself deployment FAIL. A fatal traceback, restart loop, unexpected TLS trust failure or auth safety issue is an immediate STOP.

## Gate C — admission and 20-minute observation

- `captive-portal.service` active with stable PID and `NRestarts=0`; `fingerprint-evidence.service` active; no unexpected service restarts.
- HTTPS `/admin/login` and portal public endpoints return expected status once startup completes. Check repeated stable responses **after** the 20-minute window.
- `Omada` DNS mapping and strict TLS verified; Omada OpenAPI read-only cycles HTTP 200, no `InsecureRequestWarning` and no persistent `origin_not_admitted` regression.
- The Visit reader's completed event remains legacy **OFF schema** (event name, only legacy `processed_line_count`, `scan_complete`, `duration_ms`; no `reader_report_schema_version=2`, `scans_represented`, `report_reason`). Do **not** infer from mere absence of v2 that reader is healthy: check completed-scan/progress/error/freshness independently.
- Auth/Visit lifecycle, background readers, Admin/portal health and an Owner-controlled guest phone authentication should be checked before release acceptance. Do not test destructive Omada actions on visitors.
- Compare logs and service health with pre-cutover baseline; collect timestamps/SHA/HTTP results. Physical HDD optimization is neither expected nor claimed from the disabled feature.

## Gate D — rollback / escalation

Immediate stop conditions: strong evidence of auth failure, durable Visit/source progress discrepancy, bad code/tree/config, strict Omada TLS failure, unexpected persistent errors, restart loop. If no web readiness by 20 minutes, assess I/O progress and choose rollback or explicitly extended observation with Owner awareness; do **not** call a slow D-state read a silent PASS.

Rollback sequence is a controlled restart: stop companion + portal, restore previous exact `e2cbd96916d8a81f07f0d79a1a745f593ccb5114` checkout and any needed original protected env backup, start portal and companion, allow another sufficiently long startup, repeat tests. No SQLite schema change or data rewind is expected. Never remove or overwrite DB/WAL files to roll back this code-only feature.

## Separate, future compact activation

`COMPACT_ACTIVATION=HOLD`. First complete real consumer inventory and accepted mixed legacy/v2 LogQL in disposable Lab; migrate Grafana dashboard UID `captive-portal-auth-v3-fixed`, panel 138, ahead of activation under Owner approval. Prove numeric weights, schema-quality violations, absent-vector handling, stale/no-data distinctions, alert compatibility and rollback. Only then a **separate Owner GO** for changing startup flag to `true` and another controlled restart. Do not overlap with QIO-02 quiet baselines or infer host HDD savings from fewer INFO logs.

```ini
PR_219=MERGED
QIO01D_SOURCE=ACCEPTED
DEPLOY_NOW=NO
NIGHT_DEPLOY=AWAIT_SELECTED_TIME_AND_SEPARATE_OWNER_GO
TARGET_MAIN=191beda1f23f8f466d2431f42e57571815d85778
TARGET_TREE=3f6d0a05c5d893d3139db44a1692c81e67fd6c6e
COMPACT=DEFAULT_OFF
GRAFANA_MUTATION=NO
PRODUCTION_ACTION_PERFORMED=NONE
ROLLBACK_HEAD=e2cbd96916d8a81f07f0d79a1a745f593ccb5114
OBSERVATION_WINDOW=20_MINUTES
```
