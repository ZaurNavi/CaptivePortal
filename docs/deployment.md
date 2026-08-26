# Deployment

Status: current contract; production details remain host-verified
Updated: 2026-08-26
Runtime repository baseline documented by KB: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`
Test-workflow update baseline: `main@8e36132398398b13d7503f624ef19c26d0057566`

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

## Testing responsibility

Coder targeted/module evidence is reused by Tech Lead and the release process.

The official full-regression baseline / Full Regression Gate / final Test Evidence is supplied by Central Lab according to `docs/testing.md`. Tech Lead does not need to duplicate the same full suite for ordinary review.

Before a production deployment/activation, the release owner decides whether the exact artifact requires a fresh Central Lab gate and whether a separate Linux/production-compatible gate is mandatory.

The Windows Local Gate does **not** replace Linux acceptance when the deploy contract requires Linux. The Linux gate is executed separately by the executor named by the deploy/release TASK; it is not automatically Coder or Tech Lead responsibility.

## Feature activation

Activation of Snapshot, Registry, Visit, Observation, Current State, Analytics/API, Admin Web/Home sections or Cleaner is owner-controlled and requires production configuration verification plus component-specific health evidence.

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