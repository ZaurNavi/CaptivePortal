# Observation Foundation

Status: current module contract
Updated: 2026-09-13
Baseline: `main@3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`
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

## Device Type read enrichment

Observation storage continues to preserve raw `device_type` and the independent
`connect_device_type` fact.

Client Observation read DTO data adds:

```text
device_type_key
```

derived from raw `device_type` by the central lexical normalizer.

The key is read-time enrichment only. It does not rewrite persisted historical
evidence and it must never be inferred from `system_name`,
`connect_device_type`, MAC/vendor or other fields.

## Maintenance

- dynamic and config retention differ;
- cleanup is bounded;
- integrity worker runs independently;
- client/AP/cleanup/integrity health contributes to active/degraded state.

## Dependencies

Uses the process-wide shared `OmadaProvider`.

Exposes persisted read boundary for Analytics/Admin.

Failure is fail-open relative to guest authorization.
