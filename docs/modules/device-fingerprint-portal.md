# Device Fingerprint Portal Evidence

Status: **current production-foundation producer; repository default remains disabled**.

TASK-DEVICE-FINGERPRINT-03 adds passive normalized evidence from the existing
Omada External Portal and resolved CAPPORT login requests. It reads only the
bounded `User-Agent`, `sec-ch-ua`, `sec-ch-ua-platform`, and
`sec-ch-ua-mobile` values. Raw headers, their hashes, cookies, authorization,
URLs, high-entropy Client Hints, and JavaScript fingerprint signals are never
queued, logged, or persisted.

Eligible requests are normalized in the request thread and handed off with
`put_nowait()` through a bounded 256-item FIFO. A non-blocking, 8192-entry,
six-hour coalescer prevents portal refresh floods. The daemon worker named
`device-fingerprint-portal` sends batches of at most 50 normalized P1 events to
the existing direct-TLS Task-01 API. Delivery, credential, CA, queue, parser,
and telemetry failures are contained and never change authorization results.

The legacy defaults are producer `portal-zefer-01`, capture source
`zefer-portal-http-01`, Site `6a64f17630da7c70d232187a`, guest CIDR
`192.168.8.0/22`, and optional corroborating SSID `Zefer_Parki`. These claims
may be configured at process startup under DEPLOY-CONFIG-02; they are not
self-authorizing receiver/source registrations. The production
schema registry adds only `portal_headers/1`; no classifier, DB, API, collector,
or identity-linking model is introduced.

Configuration is isolated under `DEVICE_FINGERPRINT_PORTAL_*`; the default is
`DEVICE_FINGERPRINT_PORTAL_ENABLED=false`. The Bearer credential and CA trust
file remain external to Git. Production activation is a separate Owner action.

## Independent deployment configuration

Only Producer ID, Capture Source ID, Site, guest CIDRs, exact SSIDs, direct-TLS
Evidence base URL and absolute Linux CA/bearer file paths are configurable here.
Machine IDs use `[a-z0-9][a-z0-9._-]{0,63}` and Site exactly 24 lowercase hex.
Guest scope is CSV of 1..16 canonical nonoverlapping strict IPv4 networks, no `/0`,
host bits, duplicate or empty item. SSIDs are 1..16 distinct exact case-sensitive
UTF-8 strings, 1..32 bytes each, with no control/blank/wildcard members. Unicode
and spaces in an actual SSID are not casefolded/trimmed into another identity.
Missing session SSID remains optional corroboration, not an Auth requirement.

Evidence URL is direct HTTPS DNS or canonical private IPv4/exact loopback,
optional canonical port, and exactly `/api/internal/device-fingerprint/v1`.
Only one terminal slash may normalize; no userinfo, query, fragment, percent
escape, numeric IP alias or alternate path. CA/SAN/expiry are separate real TLS
proofs; production retains `verify=<CA file>`, never `verify=False` or a Core/NPM relay.

All queue/batch/age/coalescer/timeouts/cooldowns remain pinned (256 / 50 / 300 /
21600 / 8192 / 0.5 / 2.0 / 30 / 300). Disabled ignores deployment overrides and
composition creates no producer worker; invalid enabled config/delivery remains
contained independently of guest Auth, Omada and CAPPORT.

New deployment requires its own bearer and receiver registration admitting exact
producer/Site/source/kinds/guest scope, peer policy and CA/SAN. HTTP 200 does not
admit F-B1 timelines, clocks, emitters or classification profile. Source admission,
activation and restart require separate authorization. See [configuration](../configuration.md#sensorportal-producer-deployment-configuration).

<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:BEGIN -->
## Current relationship to the production classifier

Portal evidence is one origin in the current Device Fingerprint system; it is not
a separate classifier. The normalized Portal evidence joins DHCP/TCP/TLS/QUIC
evidence in snapshot/origin assessment, while MAC Registry is a knowledge-based
sixth origin.

Current source-health liveness uses the admitted PERIODIC Portal emitter:

```text
nominal same-state heartbeat = 60 seconds
freshness timeout = 180 seconds
timeout disposition = unknown
```

The older EVENT_DRIVEN emitter remains historical lineage and has a frozen
freshness value of 0 seconds.

Raw request headers remain non-durable. The classifier consumes normalized
persisted evidence only.
<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:END -->
