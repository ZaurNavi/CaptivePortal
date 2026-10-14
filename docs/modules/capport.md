# CAPPORT

Status: current
Updated: 2026-08-26
Baseline: `main@53f617b3ac0155d0d647e58e98309927f9a4d318`

## Purpose

RFC 8908/8910 captive-portal discovery/identity layer and login bridge into the common authorization engine.

CAPPORT is **not** a second authorization system.

## Flow

`source IP → allowed-network validation → Site-bound client discovery → PortalClientContext → PortalEntryHandler → AuthSessionManager → AuthWorker`.

When the client is not yet discoverable, CAPPORT returns a bounded discovery mode and the existing page performs sequential same-page polling. No AuthSession/AuthWorker is created until client identity is resolved.

SSID evidence is preserved from the existing Omada client lookup:

`Omada /clients ssid → CapportClient.ssid → PortalClientContext.ssid → AuthSession.ssid → VisitStartRequest.portal_ssid → Visit Lifecycle`.

Missing/malformed SSID remains unproven; CAPPORT does not infer it from Site or configuration and does not add an extra Omada request.

## Identity/discovery safeguards

Current implementation includes:
- source-IP allowed networks;
- Site binding;
- bounded identity/state caches;
- failure cooldown;
- duplicate-IP protection;
- forced refresh for recently appearing clients;
- bounded discovery retry;
- `resolve_for_login` before entering Auth;
- strict controlled responses and no-store behavior.

## Same-page completion

Progress remains monotonic across discovery/auth phases.

After confirmed `AUTHORIZED`, frontend completion is guarded so a fallback same-page revalidation cannot become a reload loop. Exact captive-WebView behavior remains an operational acceptance fact, not a repository health claim.

## Dependencies

Allowed:
shared `OmadaProvider`, PortalEntryHandler, auth telemetry, Flask blueprint.

Forbidden:
separate AuthWorker, separate provider/token cache, bypass of common AuthSession flow.

## Persistence/lifecycle

CAPPORT uses bounded process-local caches only. Service/blueprint are composed inside `create_app()` using the shared controller.

A CAPPORT failure must not break the ordinary Omada External Portal path.

## Deployment-owned inputs

`CAPPORT_SITE_ID`, `CAPPORT_PUBLIC_BASE_URL` and
`CAPPORT_ALLOWED_CLIENT_NETWORKS` may be provided in the process environment at
startup; absent inputs retain the existing Site, public origin and both guest
networks. See the exact defaults and grammar in [configuration](../configuration.md).
Invalid explicit inputs fail startup without fallback. Site is canonical lowercase
24-hex; origin is HTTPS ASCII DNS only, optionally port and one final slash;
guest scope is 1..16 canonical strict CIDRs in a no-whitespace CSV. Hostnames are
lowercased and a permitted single final slash removed; Site/CIDRs are never repaired.

The typed CAPPORT config uses the same validators, converts valid CIDR strings to
strict IPv4/IPv6 network objects, and preserves actual source-IP membership before
the shared Site-bound Omada lookup. Private RFC1918 Flask binds are permitted by
Core config; CAPPORT no longer imposes a loopback-only DTO constraint.
`user-portal-url` remains configured origin + existing `/capport/login`; public API,
discovery, retries, media type, no-store and shared authorization flow are unchanged.
No `/.well-known/captive-portal` route is introduced or claimed operational.

All five Core/CAPPORT deployment keys are startup-owned, outside writable Admin
Settings, with restart-only adoption. Code acceptance does not prove NPM reachability,
header sanitization or firewall safety. Target SysAdmin D01–D03 and Owner deployment
approval are separate. No old VM change or migration; Portal Fingerprint pins and
sensor readiness remain separate HOLD items for independently configured hosts.
