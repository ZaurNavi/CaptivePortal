# Admin Console Traffic

Status: current production module contract
Updated: 2026-08-29
Repository baseline: `main@8f3ad59771f72c49834b1012963de6d94b9e0d18`
Repository tree: `2ef8bf264a008259242cde0778d0ebd20fa94b9e`
Production deployed HEAD: `8f3ad59771f72c49834b1012963de6d94b9e0d18`
Production deployment: 2026-08-29

## Current status

```text
TRAFFIC-00 — Traffic Section Foundation
DONE / MERGED / PRODUCTION / ACTIVE

TRAFFIC-01 — Current Network Throughput
DONE / MERGED / PRODUCTION / ACTIVE

TRAFFIC-02-READ — Historical Network Traffic Read
NEXT / DRAFT available for architectural review
IMPLEMENTATION NOT STARTED

TRAFFIC-02 — NOT STARTED
TRAFFIC-03+ — NOT STARTED
```

The existence of a `TRAFFIC-02-READ` DRAFT does not grant implementation authorization.

## Product boundary

Traffic is an independent Admin Console product surface.

Production feature state reported by Owner on 2026-08-29:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_HOME_TRAFFIC_ENABLED=true
```

These flags are separate feature boundaries:

```text
WEB_ADMIN_TRAFFIC_ENABLED
!=
WEB_ADMIN_HOME_TRAFFIC_ENABLED
```

Traffic product exposure must not become a lifecycle switch for Observation,
Analytics, CurrentTrafficReadService, Current State, Visit Lifecycle, Home or
OmadaProvider.

## Traffic Section Foundation

Current foundation provides:

- `AdminPage("traffic", "Traffic", "admin/traffic.html")`;
- `GET /admin/sites/<site_id>/traffic`;
- Site-aware Traffic navigation;
- one shared Traffic frontend coordinator;
- one page-level refresh/request lifecycle owner;
- panel-local failure isolation;
- no Traffic-specific collector, database or Omada path.

There must not be a second Traffic frontend coordinator.

## Current Network Throughput

Canonical product path:

```text
Omada current AP primitives
→ Observation acquisition
→ persisted AP traffic facts
→ CurrentTrafficReadService
→ AdminQueryService
→ Admin Traffic API
→ Traffic frontend coordinator
→ Current Network Throughput panel
```

Forbidden:

```text
Admin → Omada direct
browser → Omada
second current traffic collector
second current traffic calculation owner
second Traffic frontend coordinator
```

## Current Traffic API

Canonical endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/current
```

Query parameters: none.

Semantic path:

```text
AdminQueryService.current_traffic_summary(...)
→ CurrentTrafficReadService.get_current_site_traffic(...)
→ serialize_current_traffic_summary(...)
```

Current shared policy:

```text
fresh max age: 90 seconds
stale boundary: 180 seconds
max AP skew: 60 seconds
```

Traffic Section and Home Traffic reuse the same semantic owner. They do not
implement independent current-throughput calculations.

## Network Traffic semantics

Domain:

```text
NETWORK TRAFFIC
AP/network throughput evidence
unit = Mbps
```

Primary source: `wired`.

Fallback: `lan`.

Radio is excluded from the Site Current Network Throughput calculation.

Direction mapping:

```text
wired:
Download = wired_download_mbps
Upload   = wired_upload_mbps

lan fallback:
Download = lan_rx_mbps
Upload   = lan_tx_mbps
```

Backend `total_mbps` is canonical. Browser does not recompute Total.

Network Traffic must not be relabelled as:

- WAN traffic;
- Internet-only traffic;
- billing traffic;
- guest traffic;
- SSID traffic;
- Guest Session Traffic.

Canonical helper meaning:

> Derived from persisted AP traffic counters. May include local/service traffic and is not an Internet-only measurement.

## Cross-surface invariant

For the same fixed source/evaluation context:

```text
Home Traffic Current result
=
Traffic Section Current Network Throughput result
```

This is a semantic equality invariant, not a requirement that two sequential
live HTTP calls return byte-for-byte identical values while the source advances.

## Production acceptance — 2026-08-29

Owner-provided acceptance evidence:

```text
Central Lab targeted: 66 passed
Central Lab current runner: V6-fixed
Central Lab result: PASS
strict regressions: 0
fixed-context Home ↔ Traffic equality: PASS

service: active
CAPPORT: 200
Omada webhook: 204
Observation: complete=True
Observation error_count: 0
Admin Console: PASS
Traffic UI: PASS
```

Acceptance UI sample:

```text
Download Now: 1.52 Mbps
Upload Now:   0.08 Mbps
Total Now:    1.60 Mbps
Source:       Wired
Freshness:    Fresh
Coverage:     Complete
Evaluated:    2026-08-29 16:58:44 +04
Observed:     2026-08-29 16:58:10 +04
```

These Mbps/timestamps are sample acceptance evidence only. They are not system
constants and must not be copied into configuration or permanent assertions.

## Rollback checkpoint

Pre-Traffic production checkpoint is retained.

Previous production HEAD:

```text
f5887758898b512747d2ea8bd51763389230dc2d
```

Owner also retained the previous production tree, `/etc/default/captive-portal`
and the systemd service definition.

Rollback checkpoint status: **RETAINED**.

## Next roadmap item

`TRAFFIC-02-READ — Historical Network Traffic Read` is next.

A DRAFT exists and is awaiting architectural review/finalization. Implementation
has not started and must not be represented as active work.

Current sequence:

```text
TRAFFIC-00      DONE
TRAFFIC-01      DONE
TRAFFIC-02-READ NEXT / DRAFT REVIEW
TRAFFIC-02      NOT STARTED
TRAFFIC-03+     NOT STARTED
```
