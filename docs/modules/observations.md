# Observation Foundation

Status: current module contract
Updated: 2026-08-25
Baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`
Schema: v1

## Purpose

Historical measurement layer for Analytics. It is not the current active-client inventory.

## Client population

A client is eligible only when:
- wireless;
- active;
- `authStatus == 2`;
- SSID is in configured allowlist.

`authStatus == 1` is not part of the historical authorized population.

## AP collection

Observation persists AP inventory/dynamic/radio/config facts at different cadences plus cycle/quality metadata.

Current Traffic later derives live-oriented AP rates from these persisted facts.

## Cycle metadata

Persist:
cycle id/kind/Site, complete/partial/failure state, source totals, stored/skipped/error counts and data-quality warnings.

Consumers must not silently use a partial/failed cycle as complete data.

## Maintenance

- dynamic and config retention differ;
- cleanup is bounded;
- integrity worker runs independently;
- client/AP/cleanup/integrity health contributes to active/degraded state.

## Dependencies

Uses the process-wide shared `OmadaProvider`.

Exposes persisted read boundary for Analytics/Admin.

Failure is fail-open relative to guest authorization.
