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
