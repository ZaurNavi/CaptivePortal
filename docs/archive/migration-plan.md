# Documentation classification and migration map

Status: current routing map
Updated: 2026-08-25
Baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`

No historical/research document is deleted automatically.

## Classes

- `CURRENT` — normative current implementation contract.
- `CHANGE-INTENT` — approved but not yet merged behavior.
- `HISTORICAL` — past baseline/acceptance/report.
- `RESEARCH` — experimental/API evidence.
- `OPERATIONS` — deploy/infra procedure/evidence.
- `SUPERSEDED` — useful old document whose normative role moved elsewhere.

## Current normative entry points

CURRENT:
- `AGENTS.md`
- `docs/README.md`
- `docs/project-inventory.md`
- `docs/architecture.md`
- `docs/module-index.md`
- `docs/configuration.md`
- `docs/testing.md`
- `docs/logging.md`
- `docs/security.md`
- `docs/deployment.md`
- `docs/api/omada-open-api.md`
- `docs/modules/*` listed by module-index

## Existing legacy/specialized docs

Earlier specialized files such as:
`docs/CAPPORT.md`, `docs/auth_retry.md`, `docs/auth_telemetry.md`,
`docs/portal_counter.md`, `docs/public_traffic.md`,
`docs/visitor_snapshot_collector.md`, `docs/visitor_device_registry.md`,
`docs/omada_webhook_receiver.md`, `docs/omada_webhook_normalizer.md`

remain `SUPERSEDED/HISTORICAL SUPPORT` where their normative module contract exists under `docs/modules/`.

Do not delete them without per-file approval.

## Research

Omada endpoint research reports remain `RESEARCH` evidence. The curated current integration/evidence contract is `docs/api/omada-open-api.md`.

Research proving a capability does not change current runtime or Admin product permissions.

## Change intent

Home Activity is not current runtime at this baseline. If its FINAL TASK is maintained outside this repository snapshot, classify it as `CHANGE-INTENT`, not CURRENT.

## Archive rule

A move to `docs/archive/` is a repository action and requires explicit approval. Before moving:
1. verify no unique current fact would be lost;
2. ensure canonical current source exists;
3. add `Superseded by` header/link;
4. preserve evidence/history.
