# Omada Open API: evidence levels and current application usage

Status: current curated contract
Updated: 2026-08-25
Repository baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`
Live research target: Omada Software Controller 5.14.31

This document separates:
1. schema presence;
2. live controller behavior;
3. physical/effect verification;
4. current application usage.

A verified capability is not automatically an approved product action.

## Response rule

For Omada OpenAPI:
`HTTP 200 != success`.

Check:
network/timeout → HTTP status → JSON shape → `errorCode`/message → endpoint-specific result → post-action verification where required.

## Live-verified read foundations

Verified on Controller 5.14.31 include OAuth `client_credentials`, Site/client inventory/detail, AP read endpoints used by research, Rate Limit Profile reads and Hotspot authentication records.

Important runtime fact:
Client List is not the universe of all historical known clients; direct Client Detail can return an offline known client even when it is absent from active list search.

## Controlled live mutation findings

Research on the owner's designated test phone established:

| Capability | Evidence |
|---|---|
| Rename client | live verified |
| Custom per-client Rate Limit apply | live + physical shaping verified |
| Rate Limit Profile CRUD/application | live + physical shaping verified |
| Lock-to-AP configuration/rollback | live config verified; roaming-prevention physical effect still unverified |
| Reconnect | live disruptive disconnect verified; OS auto-reconnect not guaranteed |
| Block / Unblock | live connectivity effect verified |
| Hotspot Unauth | live authorization revocation verified |
| Hotspot Auth | live transition of captured pending client to authorized verified; isolated portal-bypass test not obtained |
| Authentication Period | live verified as expiration extension delta in milliseconds |
| Batch | schema surface exists; destructive product use not approved |

## Critical semantics

- Reconnect ≠ guaranteed automatic reconnect.
- Unblock ≠ reconnect.
- Block ≠ Hotspot Unauth.
- Authentication Period: `new_end = old_end + period_ms`.
- Lock-to-AP has Block interaction constraints.
- A valid authentication record does not prove every future join will skip captive flow.
- Profile-mode client detail may not expand effective profile rates; the profile object is authoritative for configured profile values.

## Known limitation: Custom Rate Limit clear

Public `/ratelimit` successfully applies custom limits, but research did not establish a supported public call that reliably restores `rateLimit.enable=false`.

The Omada UI can clear it through a private `/api/v2/.../clients/{MAC}` path.

Private UI API is **not** an approved stable CaptivPortal integration contract without separate architecture/risk approval.

## Current application provider usage

Current application code uses the shared provider for the Portal/Auth/CAPPORT/operational contracts, including client reads, Hotspot auth/unauth and guarded reconnect where implemented.

Observation and Current State reuse the same provider for read collection.

Admin Web and Analytics do not call Omada.

Client-control research capabilities such as rename, block/unblock, rate-limit and lock-to-AP are **not** automatically exposed by Admin Web. The current Admin product boundary remains read-only.

## Unsupported / not approved

- direct `/clients/{mac}/disconnect` was live-tested as unsupported/404 on 5.14.31;
- Delete Client/historical card deletion not established as supported public client-control contract;
- ordinary endpoint reboot not established;
- destructive batch operations not approved;
- private/internal UI API not approved;
- Fixed IP/DHCP semantics must not be assumed in the current Cisco-authoritative guest DHCP topology.

## Safety for future mutations

Any new product mutation requires:
- explicit TASK/policy;
- correct permission scope;
- Site/client identity validation;
- audit-before-action when appropriate;
- bounded retry;
- post-action read-back/effect verification;
- safe rollback semantics;
- no action on unrelated visitors during testing.
