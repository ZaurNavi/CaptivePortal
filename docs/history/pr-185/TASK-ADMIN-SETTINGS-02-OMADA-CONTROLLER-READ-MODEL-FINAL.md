# TASK-ADMIN-SETTINGS-02 — OMADA CONTROLLER READ MODEL

**Project:** CaptivPortal  
**Area:** Admin UI → Settings → Controller  
**Owner:** Technical Developer Settings / Tech Lead  
**Status:** FINAL IMPLEMENTATION TASK — CODER AUTHORIZED  
**Baseline:** `main@9ca25fd3dc9d552d446be4669f2e67247dcb7a1b`  
**TREE:** `0ef5c4555fa254a8904f35e19c0570a5bbe8abe7`  
**Architecture:** `CAPTIVPORTAL-ADMIN-SETTINGS-OMADA-CONTROLLER-READ-MODEL-ARCHITECTURE-CONTRACT-v0.1` — TECH LEAD ACCEPTED

---

## 0. Governance

This TASK authorizes **Stage 2 only**: read-only GLOBAL Omada Controller configuration under Admin Settings.

Before coding:

```text
git rev-parse HEAD
= 9ca25fd3dc9d552d446be4669f2e67247dcb7a1b

git rev-parse HEAD^{tree}
= 0ef5c4555fa254a8904f35e19c0570a5bbe8abe7

git status --porcelain
= empty
```

If `main` advances: STOP → Tech Lead baseline reconciliation.

```text
CODER = GO
PRODUCTION = NO CHANGE
SYSTEMD = NO ACTION
OMADA MUTATION = FORBIDDEN
SECRET STORAGE = FORBIDDEN
LIVE CONTROLLER PROBE = FORBIDDEN
```

---

## 1. Objective

Implement:

```text
Admin
→ Settings
→ Controller
```

The page/API must describe the exact Controller configuration adopted by the running `captive-portal.service`.

Permanent invariant:

```text
WHAT SHARED OMADA RUNTIME ADOPTED
=
WHAT CONTROLLER READ MODEL DESCRIBES
```

No environment/file reread from Admin request path. No provider-private-field inspection. No raw secret disclosure. No Omada HTTP/OAuth request.

---

## 2. Required composition correction

Current production path contains a second configuration composition:

```text
run.py
→ Settings-aware runtime settings

but separately:

create_controller()
→ OmadaProvider()
→ get_settings()
```

Replace it with:

```text
run.py
→ get_settings()
→ Stage-1 Settings bootstrap
→ settings_bootstrap.runtime_settings
→ ONE OmadaControllerRuntimeConfig
       ├──→ shared OmadaProvider
       └──→ OmadaControllerPublicConfigSnapshot
              → ControllerConfigurationReadService
              → Admin API/UI
```

`OmadaProvider` MUST consume the same typed runtime config from which the public snapshot is derived.

Production `OmadaProvider` MUST NOT independently call `get_settings()` after this TASK.

---

## 3. Canonical Controller config boundary

Create:

```text
app/controllers/omada_config.py
```

### `OmadaControllerRuntimeConfig`

Immutable secret-bearing runtime object:

```text
controller_url: str
controller_id: str
client_id: str
client_secret: str
verify_ssl: bool
```

It is:

- constructed once during main-service startup;
- validated before provider construction;
- never exposed to Admin HTTP;
- never stored in SettingsStore;
- never logged;
- not attached to browser-visible Flask state.

**Binding secret rule:** `repr()` / `str()` must not expose `client_secret`. No generic `asdict()` serialization of this object is allowed in production paths.

### `OmadaControllerPublicConfigSnapshot`

Separate immutable secret-free object containing:

```text
controller_url
controller_url_source
controller_id
controller_id_source
client_id
client_id_source
client_secret_presence
client_secret_source
tls_certificate_verification
tls_certificate_verification_source
```

Admin code receives only this public snapshot.

---

## 4. Validation / normalization

Preserve existing Omada semantics.

Required core values:

```text
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
OMADA_CLIENT_SECRET
```

All four remain required and non-empty after trim.

`OMADA_URL` keeps existing rules:

```text
http|https only
hostname required
userinfo forbidden
query forbidden
fragment forbidden
path empty or "/"
invalid port rejected
port 0 rejected
whitespace rejected
trailing root "/" removed
```

No new case folding, truncation, Unicode normalization or guessed aliases.

`verify_ssl` remains part of effective runtime config and is read-only in Stage 2.

Use one semantic validator. Do not duplicate a separate read-model URL validator.

---

## 5. Provenance

Capture once in `run.py`:

```text
explicit_environment_names = frozenset(os.environ)
```

Reuse the same set for Stage-1 bootstrap and Stage-2 provenance.

Canonical field:

```text
effective_source
```

Allowed values:

```text
environment
repository_default
```

Never infer source from scalar equality.

Do not expose as source:

```text
systemd
.env
environment_file
deployment_controlled
unknown_file
```

For current `VERIFY_SSL=false`, source is `repository_default`.

---

## 6. Provider/factory contract

Target:

```text
create_controller(runtime_config: OmadaControllerRuntimeConfig)
→ OmadaProvider(runtime_config)
```

`OmadaProvider(runtime_config)` is mandatory in production.

Do not preserve a production-reachable fallback:

```text
OmadaProvider()
→ get_settings()
```

A test-only helper is allowed only if it cannot be reached by production composition.

Do not create a second provider for Admin.

---

## 7. Public read service

Create:

```text
app/admin_web/controller_settings.py
```

with:

```text
ControllerConfigurationReadService
```

It consumes only `OmadaControllerPublicConfigSnapshot`.

It MUST NOT receive/read:

```text
raw settings mapping
OmadaControllerRuntimeConfig
OmadaProvider
os.environ
systemd env
.env
SettingsStore repository
```

Read execution performs zero network I/O.

---

## 8. Admin runtime integration

Extend `AdminWebRuntime` conceptually with:

```text
controller_settings_state
controller_settings_read_service
```

States:

```text
active
unavailable
disabled
```

Rules:

```text
WEB_ADMIN_SETTINGS_ENABLED=false
→ disabled

feature enabled + public snapshot available
→ active

feature enabled + safe read projection unavailable
→ unavailable
```

**Failure isolation is binding:** valid provider/runtime config must continue operating even if Controller Admin public projection/read service fails. Such failure affects only Controller Settings page/API.

Invalid core Omada runtime config keeps existing startup fail-closed behavior.

---

## 9. Authorization

Add exactly:

```text
admin.read.settings.controller
```

Do NOT add:

```text
admin.write.settings.controller
```

Authorization is GLOBAL and independent of Site selection.

Do not use:

```text
AdminSiteContextResolver
default Site
site_id
fake Site authorization
```

Current `platform_operator` may receive the capability.

---

## 10. Settings navigation — binding clarification

Compute independently:

```text
settings_general_allowed
settings_controller_allowed
```

Top-level Settings nav is visible when:

```text
WEB_ADMIN_SETTINGS_ENABLED
AND
(settings_general_allowed OR settings_controller_allowed)
```

Preferred top-level target:

```text
general allowed    → /admin/settings
else controller allowed → /admin/settings/controller
```

Inside Settings show capability-aware secondary nav:

```text
General     → /admin/settings
Controller  → /admin/settings/controller
```

---

## 11. Global page/template boundary — binding clarification

Use:

```text
page.key = "settings"              # General
page.key = "settings_controller"   # Controller
```

Treat both as Settings-domain GLOBAL pages.

`base.html` must not use only `page.key == "settings"` as the definition of a global Settings page.

Script selection:

```text
settings            → settings.js
settings_controller → controller_settings.js
other pages         → admin.js
```

Controller MUST NOT load mutation `settings.js` or Site-oriented `admin.js`.

---

## 12. Controller page

Canonical route:

```text
GET /admin/settings/controller
```

Template:

```text
app/admin_web/templates/admin/settings_controller.html
```

Display:

```text
Controller URL
Controller ID
Client / Application ID
Client Secret
TLS certificate verification
```

Client Secret shows only:

```text
Configured
Not configured
```

No textbox, masked real value, reveal/copy control, secret length, prefix/suffix, hash or fingerprint.

Do not claim:

```text
Connected
Healthy
Online
Authenticated
Token valid
```

---

## 13. Controller JS

Create:

```text
app/admin_web/static/controller_settings.js
```

Requirements:

- GET only;
- same-origin;
- calls only `/admin/api/v1/settings/controller`;
- safe text rendering;
- no mutation logic;
- no polling requirement;
- no raw HTML interpolation of API values;
- no Omada request.

---

## 14. Canonical API

Exactly:

```text
GET /admin/api/v1/settings/controller
```

No alias. No Site variant. No mutation methods.

Unexpected query parameters:

```text
400 invalid_request
```

Headers:

```text
Content-Type: application/json
Cache-Control: no-store
Pragma: no-cache
```

Canonical model:

```json
{
  "api_version": "admin.settings.controller.v1",
  "request_id": "<uuid>",
  "scope": {"type": "global"},
  "resource": {
    "type": "omada_controller",
    "scope": "installation"
  },
  "management_mode": "deployment_controlled",
  "configuration_state": "configured",
  "fields": {
    "controller_url": {
      "display_label": "Controller URL",
      "value_type": "url",
      "effective_value": "<normalized URL>",
      "effective_source": "environment"
    },
    "controller_id": {
      "display_label": "Controller ID",
      "value_type": "string",
      "effective_value": "<trimmed ID>",
      "effective_source": "environment"
    },
    "client_id": {
      "display_label": "Client / Application ID",
      "value_type": "string",
      "effective_value": "<trimmed client ID>",
      "effective_source": "environment"
    },
    "client_secret": {
      "display_label": "Client Secret",
      "value_type": "secret_presence",
      "effective_presence": "configured",
      "effective_source": "environment"
    },
    "tls_certificate_verification": {
      "display_label": "TLS certificate verification",
      "value_type": "boolean",
      "effective_value": false,
      "effective_source": "repository_default"
    }
  }
}
```

No Controller Settings generations in Stage 2.

---

## 15. API errors

Canonical codes:

```text
400 invalid_request
401 authentication_required
403 controller_settings_forbidden
404 feature_disabled
503 controller_settings_read_unavailable
500 internal_error
```

No raw exception, traceback, environment dump, settings mapping, provider repr, path, DB/systemd detail or secret in responses.

---

## 16. Absolute secret non-disclosure

Raw `OMADA_CLIENT_SECRET` must be absent from:

```text
API
HTML
HTML attributes
JS bootstrap
browser console
logs
telemetry
audit
exceptions
public repr/str
request metadata
```

Also forbidden:

```text
masked real substring
prefix
suffix
length
hash
digest
fingerprint
first/last characters
reversible encoding
```

Only presence + source are public.

---

## 17. Zero Omada I/O

Mandatory:

```text
GET /admin/settings/controller
GET /admin/api/v1/settings/controller
→ ZERO Omada HTTP/OAuth calls
```

No token request/refresh, `/sites`, `/clients`, status probe, reconnect or reauthentication.

Connection/health is OUT OF SCOPE.

---

## 18. SettingsStore relationship

No SettingsStore schema change.

Do NOT:

```text
add Controller override tables
add Controller generations
persist current env values into SQLite
add Omada keys to current 12-key writable registry
```

Controller read health is independent of SettingsStore health.

A trustworthy runtime public snapshot may remain readable even if SettingsStore is unavailable.

---

## 19. Feature gate

Reuse only:

```text
WEB_ADMIN_SETTINGS_ENABLED
```

Do not add a second Controller-specific feature flag.

Disabled:

```text
HTML /admin/settings/controller
→ 404 not_found

API /admin/api/v1/settings/controller
→ 404 feature_disabled
```

---

## 20. Exact OUT OF SCOPE

No:

```text
OMADA_URL mutation
OMADA_ID mutation
OMADA_CLIENT_ID mutation
OMADA_CLIENT_SECRET replacement
Secret Storage
Controller overrides/generations/DB
Controller health/probe
token controls
reconnect/reauthenticate
OpenAPI client management
Omada-side configuration mutation
Site-scoped Controller settings
multi-controller implementation
generic env editor
systemd/restart controls
hot reload/rebind
```

---

## 21. Authorized files

Existing files allowed as needed:

```text
run.py
app/controllers/__init__.py
app/controllers/factory.py
app/controllers/omada.py
app/admin_web/policy.py
app/admin_web/runtime.py
app/admin_web/routes.py
app/admin_web/templates/admin/base.html
app/admin_web/static/admin.css
docs/configuration.md
docs/modules/admin-web.md
```

New production files authorized:

```text
app/controllers/omada_config.py
app/admin_web/controller_settings.py
app/admin_web/templates/admin/settings_controller.html
app/admin_web/static/controller_settings.js
```

Tests may update existing Omada/Admin suites and add:

```text
tests/test_admin_controller_settings.py
```

Not authorized without Tech Lead re-open:

```text
SettingsStore schema/repository changes
Omada request-operation behavior changes beyond config injection
CAPPORT behavior
systemd units
production host configuration
```

---

## 22. Required focused tests

Must prove at minimum:

```text
T1  one normalized immutable OmadaControllerRuntimeConfig
T2  all four core Omada values remain required
T3  existing URL validation/normalization preserved
T4  provider consumes injected config
T5  production provider no longer calls get_settings()
T6  public snapshot contains no raw secret
T7  repr/str do not reveal sentinel secret
T8  provenance is environment/repository_default from startup membership
T9  authorized API GET = 200
T10 unauthenticated = 401
T11 unauthorized = 403
T12 feature disabled API = 404 feature_disabled
T13 feature disabled HTML = 404 not_found
T14 unexpected query = 400 invalid_request
T15 no-store/no-cache headers
T16 GLOBAL / no site_id
T17 no mutation route/method
T18 Controller page uses controller_settings.js only
T19 Settings navigation is capability-aware
T20 Controller HTML/API causes zero Omada/OAuth requests
T21 public projection failure yields Controller unavailable/503 only
T22 projection failure does not break Portal/Auth/shared provider
T23 SettingsStore unavailable alone does not kill Controller read model
T24 existing Stage-1 12-key writable allowlist unchanged
T25 no systemd authority
```

Use a distinctive sentinel client secret and assert it never appears in HTTP, HTML, logs, errors, repr or public serialization.

---

## 23. Regression / quality gates

Run:

```text
focused Stage-2 tests
existing Omada configuration tests
existing Admin Settings tests
existing Admin auth/policy tests
existing Admin route/template tests
affected portal/auth/controller-construction tests
```

Also:

```bash
python -m compileall app run.py tests
git diff --check
```

Run JS syntax validation for:

```text
app/admin_web/static/controller_settings.js
```

No existing Stage-1 test may be weakened/deleted to make Stage 2 pass.

---

## 24. Coder STOP conditions

STOP → Tech Lead if implementation appears to require:

- SettingsStore schema change;
- writable Controller setting;
- secret storage;
- auth protocol change;
- live Controller probe;
- Site-scoped config;
- multi-controller;
- systemd authority;
- production change;
- raw secret disclosure;
- production fallback `OmadaProvider() → get_settings()`;
- coding from a baseline different from the frozen HEAD/TREE.

---

## 25. Delivery contract

One focused feature branch / PR.

PR title:

```text
ADMIN-SETTINGS-02: add read-only Omada Controller settings
```

PR evidence must include:

```text
baseline HEAD/TREE
changed files
composition-normalization summary
focused test results
regression results
secret non-disclosure evidence
zero-Omada-I/O evidence
compileall
JS syntax check
git diff --check
known issues
```

No production deploy in this TASK.

---

## 26. Final disposition

```text
TASK ID =
TASK-ADMIN-SETTINGS-02

TASK NAME =
OMADA CONTROLLER READ MODEL

ARCHITECTURE =
FINAL / TECH LEAD ACCEPTED

IMPLEMENTATION CONTRACT =
FINAL / BINDING

BASELINE =
main@9ca25fd3dc9d552d446be4669f2e67247dcb7a1b
TREE=0ef5c4555fa254a8904f35e19c0570a5bbe8abe7

SCOPE =
READ-ONLY GLOBAL INSTALLATION-LEVEL OMADA CONTROLLER CONFIGURATION

MUTATION =
NO

SECRET RAW DISCLOSURE =
FORBIDDEN

CONNECTION HEALTH =
OUT OF SCOPE

SETTINGSSTORE SCHEMA CHANGE =
NO

SYSTEMD ACTION =
NO

PRODUCTION CHANGE =
NO

CODER =
GO

OPEN IMPLEMENTATION P0 =
0

OPEN IMPLEMENTATION P1 =
0
```
