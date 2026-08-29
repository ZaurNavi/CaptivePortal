# Deployment

Status: current contract; production details remain host-verified
Updated: 2026-08-29
Current repository baseline: `main@8f3ad59771f72c49834b1012963de6d94b9e0d18`
Confirmed production deployed HEAD: `8f3ad59771f72c49834b1012963de6d94b9e0d18`
Confirmed production tree: `2ef8bf264a008259242cde0778d0ebd20fa94b9e`

## Repository vs production

Repository establishes code/default contracts. It does not prove:
- feature flags currently enabled in systemd;
- current DB health/size;
- process environment values;
- reverse-proxy/systemd unit details.

Never print production secret values in deployment evidence.

## Core precondition

Required Omada environment:
`OMADA_URL`, `OMADA_ID`, `OMADA_CLIENT_ID`, `OMADA_CLIENT_SECRET`.

Provider construction is fail-closed when core configuration is missing/invalid.

## Deploy model

Implementation and production activation are separate actions.

A deploy TASK must specify:
target, approved commit, backup, exact config change, required test evidence, health checks, rollback and owner authorization.

Repository feature defaults being `false` intentionally support code deployment before separate activation.

## Current runtime startup health

Use current `run.py` ordering documented in `project-inventory.md`.

Health review should distinguish:
- core portal/auth availability;
- independent runtime state: disabled / active / degraded / unavailable;
- no duplicate OmadaProvider;
- expected single application process;
- expected storage/journal permissions.

## Current shutdown

Expected order:
Admin state clear → Cleaner → Observation → Current State → Public Traffic → stop Visit scheduling → drain Auth executor → stop Visit accepting/close → drain Snapshot → Registry final scan.

Do not activate/deploy changes that break bounded shutdown.

## First-restart acceptance

A production startup/retry change is not accepted merely because a later restart succeeds. Capture the **first restart** after deployment: service state plus component-specific persisted/telemetry evidence. Do not use a second restart to mask a startup defect.

For the 2026-08-26 rollout at `main@53f617b3`, only one restart was performed (`22:55:39 +04`). Service, CAPPORT, webhook and Observation were active; Current State persisted 4/4 successful client cycles and 4/4 successful AP cycles with no non-success result. First-restart startup acceptance: **PASS**.

## Testing responsibility

Coder focused/minimal TASK/module evidence is reused by Tech Lead and the release process. Coder does not execute cross-module/broader/full regression as part of implementation handoff.

The official cross-module/broader/full-regression baseline / Full Regression Gate / final Test Evidence follows `docs/testing.md`: Tech Lead defines the exact artifact, commands and acceptance criteria; Owner physically operates `C:\CaptivPortal-Lab` and launches the official regression; Owner + Tech Lead issue PASS/FAIL.

Before production deployment/activation, the release owner decides whether the exact artifact requires a fresh Central Lab gate and whether a separate Linux/production-compatible gate is mandatory. Official gate execution is not delegated to Coder.

The Windows Local Gate does **not** replace Linux acceptance when the deploy contract requires Linux. The Linux gate is executed separately by the executor named by the deploy/release TASK; it is not automatically Coder or Tech Lead responsibility.

## Traffic production checkpoint — 2026-08-29

Owner-reported state:

```text
TRAFFIC-00: DONE / MERGED / PRODUCTION / ACTIVE
TRAFFIC-01: DONE / MERGED / PRODUCTION / ACTIVE
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_HOME_TRAFFIC_ENABLED=true
```

Acceptance health:
- service active;
- CAPPORT 200;
- Omada webhook 204;
- Observation `complete=True`, `error_count=0`;
- Admin Console PASS;
- Traffic UI PASS.

The two Traffic flags are separate feature boundaries.

Pre-Traffic rollback checkpoint is retained:

```text
previous production HEAD: f5887758898b512747d2ea8bd51763389230dc2d
```

Owner also retained the previous production tree, `/etc/default/captive-portal`
and the systemd service definition. Do not delete this checkpoint merely because
Traffic acceptance passed.

## Feature activation

Activation of Snapshot, Registry, Visit, Observation, Current State, Analytics/API, Admin Web/Home sections, Traffic Section or Cleaner is owner-controlled and requires production configuration verification plus component-specific health evidence.

A repository `*_ENABLED=false` does not imply production disabled.

## Rollback

Prefer:
1. disable affected feature in production environment;
2. restart service where environment change requires it;
3. verify core portal and component state;
4. if necessary restore approved code/config/data backup.

Never delete audit/history merely to make rollback look clean.

## Infrastructure boundary

systemd, reverse proxy, Alloy, Loki and Grafana are outside normal application implementation scope and require their own deploy/infrastructure authorization.