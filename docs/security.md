# Security

Status: current
Updated: 2026-08-25
Baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`

## Secrets

- Production secrets come only from process environment/approved secret handling.
- No secrets in Git, fixtures, TASK, PLAN, ADR, PR, examples or handoff.
- Never log Access Token, Client Secret, Authorization header, Admin password/hash, session token/cookie, CSRF token or Wi-Fi password.
- A leaked historical secret must be rotated/revoked even if Git history is not rewritten.

## Current repository findings

- Required Omada credentials have no production literal fallback.
- `VERIFY_SSL=false` remains repository default and an open security/operations debt.
- `.github/workflows` is absent; release CI is manual.
- `.env.example` allows the owner-approved VPN client network `10.8.0.0/24` for Admin Web repository defaults.

Repository facts do not prove current production secret/flag values.

## Reverse proxy and request-line privacy

Current Flask app uses `ProxyFix` for exactly one trusted local reverse-proxy hop.

`SecretSafeRequestHandler` strips the entire query string from access-log request lines for Admin and internal Analytics namespaces.

Do not broaden proxy trust without a deployment/security TASK.

## Admin Web security boundary

Guest Portal authentication is unrelated to Admin authentication.

When Admin Web is enabled:
- HTTPS is required by policy;
- source network must be allowlisted;
- Site is allowlisted/defaulted separately;
- password is verified against external stored hash;
- login uses pre-auth CSRF;
- login attempts are rate limited;
- sessions are bounded and process-local;
- idle and absolute expiration apply;
- cookies are Secure + HttpOnly + SameSite=Strict;
- logout requires CSRF;
- responses apply no-store, nosniff, no-referrer, frame deny and CSP.

Admin business/data API remains read-only.

## Analytics internal API

Separate protected service boundary:
- Bearer token;
- source-network allowlist;
- Site allowlist;
- bounded concurrency;
- response-size cap;
- no query-string credentials.

Admin browser must not consume this bearer API directly.

## Persistence

- writer owns schema/migration;
- read-only Analytics connections require `PRAGMA query_only`;
- backups are required before schema migration in deployment tasks;
- raw sensitive Omada responses are not persisted.

## Omada mutations

Research proving a mutation works does not authorize product exposure.

New write/control behavior requires explicit policy/audit/change-intent. Private Omada UI `/api/v2` behavior is research evidence, not an approved integration contract.
