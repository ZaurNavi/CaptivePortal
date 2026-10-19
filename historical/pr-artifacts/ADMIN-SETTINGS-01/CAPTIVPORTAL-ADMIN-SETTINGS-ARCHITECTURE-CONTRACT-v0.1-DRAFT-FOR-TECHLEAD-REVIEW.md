# CAPTIVPORTAL ADMIN SETTINGS — ARCHITECTURE CONTRACT v0.1
## Writable Configuration Control Plane / Settings UI V1

**Project:** CaptivPortal  
**Area:** Admin UI → Settings  
**Role:** Architect  
**Status:** DRAFT FOR TECH LEAD REVIEW  
**Baseline:** `main@be3fe14f929b45e4a1ca3991bc6a2a3011792641`  
**Implementation authorization:** NO  
**Coder task:** NO  
**Production change:** NO  

---

# 0. ARCHITECTURE DISPOSITION

CaptivPortal may add a writable Admin Settings control plane, but V1 MUST be intentionally narrow.

The architectural objective of Settings V1 is:

```text
build a trustworthy configuration mutation foundation
+
expose a small non-secret / non-self-lockout allowlist
+
make configured vs effective state explicit
+
make every mutation atomic, authorized, auditable and stale-write safe
```

Settings V1 is NOT:

```text
a generic editor for every environment variable
a systemd control panel
a secret manager
an Omada credential editor
a CAPPORT control panel
an auxiliary-service orchestrator
a raw .env editor
```

Permanent principle:

```text
SETTING EXISTS IN app/config.py
!=
SETTING IS SAFE FOR ADMIN UI MUTATION
```

Only keys registered as:

```text
ui_editable = true
```

in the canonical Settings Definition Registry may be mutated.

Everything else is deny-by-default.

---

# 1. SCOPE SETTINGS V1

## Decision

Settings V1 is GLOBAL-only and contains exactly two editable groups.

No other current configuration key is writable through Admin UI in V1.

---

## 1.1 Group A — Admin UI pagination / bounded query presentation

Exact allowlist:

```text
WEB_ADMIN_DEVICE_PAGE_SIZE
WEB_ADMIN_VISIT_PAGE_SIZE
WEB_ADMIN_OBSERVATION_PAGE_SIZE
WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS
WEB_ADMIN_CURRENT_STATE_PAGE_SIZE
WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE
```

Canonical V1 bounds:

```text
WEB_ADMIN_DEVICE_PAGE_SIZE
type = integer
min = 1
max = 500

WEB_ADMIN_VISIT_PAGE_SIZE
type = integer
min = 1
max = 500

WEB_ADMIN_OBSERVATION_PAGE_SIZE
type = integer
min = 1
max = 500

WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS
type = integer
min = 1
max = 168

WEB_ADMIN_CURRENT_STATE_PAGE_SIZE
type = integer
min = 1
max = 250

WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE
type = integer
min = 1
max = 250
```

---

## 1.2 Group B — Admin UI refresh cadence

Exact allowlist:

```text
WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS
WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS
WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS
WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS
```

Canonical V1 bounds:

```text
WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS
type = integer
min = 60
max = 300

WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS
type = integer
min = 60
max = 300

WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
type = integer
min = 60
max = 300

WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS
type = integer
min = 60
max = 300

WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS
type = integer
min = 60
max = 300

WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS
type = integer
min = 60
max = 600
```

---

## 1.3 Explicitly outside Settings V1

The following domains are NOT writable through Settings V1:

```text
Omada URL / IDs / OAuth credentials / client secrets

Admin username/password/password hash

Admin enabled state

Admin source-network allowlist

Admin Site allowlist/default Site

Admin HTTPS requirement

Admin session/login/CSRF/security limits

CAPPORT settings

Auth behavior

Authorization policy

Pending Session Cleaner

Visit Lifecycle operational configuration

Visitor Registry operational configuration

Observation collector configuration

Current State collector configuration

Analytics semantic thresholds

Traffic Projection

Device Fingerprint

Network Intelligence / DTI

Webhook secrets / auth configuration

bearer tokens

TLS certificate/private-key paths

database paths

log paths

system bind addresses / ports

NIC / SPAN / RSPAN

systemd/service configuration

auxiliary-process direct-env settings

all *_ENABLED feature switches

all destructive/action-rate settings

all retention/storage-limit settings

all timeout/concurrency settings not explicitly allowlisted above
```

Future expansion requires a new bounded architecture/Tech Lead decision.

Coder MUST NOT infer editability from type, name, environment origin, or presence in `.env.example`.

---

# 2. CONFIGURATION SOURCE OF TRUTH

## Decision

Create one durable writable owner:

```text
SettingsStore
```

Physical persistence:

```text
SQLite
```

Canonical V1 database:

```text
/opt/CaptivePortal/data/settings.sqlite3
```

This path is bootstrap/deployment-controlled and is NOT editable through Settings UI.

Logical ownership:

```text
SettingsStore
→ immutable configuration generations
→ persisted overrides
→ activation records
→ durable audit
→ idempotency records
```

Admin Web routes MUST NOT read/write SQLite directly.

Required logical service boundary:

```text
Admin HTTP
    ↓
SettingsReadService / SettingsMutationService
    ↓
SettingsDefinitionRegistry
SettingsValidationService
SettingsRepository
```

---

## 2.1 Storage format

Values are persisted as canonical typed values, not raw environment strings.

V1 value types:

```text
integer
```

Future registry types may include:

```text
boolean
string
enum
list
object
```

only after corresponding contracts exist.

SettingsStore MUST NOT become a generic arbitrary JSON key/value store.

Unknown keys are rejected.

---

## 2.2 Bootstrap safety

SettingsStore location and feature activation remain deployment controlled.

Introduce deployment/bootstrap controls conceptually equivalent to:

```text
WEB_ADMIN_SETTINGS_ENABLED
SETTINGS_DB_PATH
```

Rules:

```text
WEB_ADMIN_SETTINGS_ENABLED default = false

SETTINGS_DB_PATH default =
/opt/CaptivePortal/data/settings.sqlite3
```

Neither is writable through Settings UI.

---

# 3. CONFIGURATION PRECEDENCE

For a registered setting, resolution order is exactly:

```text
1. repository/code default
        ↓
2. process environment
        ↓
3. persisted GLOBAL Settings override
        ↓
4. persisted SITE Settings override
   only for a future setting explicitly registered as Site-scoped
```

Highest applicable layer wins.

Therefore:

```text
site persisted override
>
global persisted override
>
environment
>
repository default
```

For Settings V1:

```text
Site-scoped writable values = NONE
```

so effective configured resolution is:

```text
persisted global override
>
environment
>
repository default
```

---

## 3.1 Reset-to-deployment semantics

The UI MUST support:

```text
clear persisted override
```

which means:

```text
fall back to environment if present
otherwise repository default
```

The UI MUST NOT copy the current environment value into persistence merely to “reset”.

---

## 3.2 One resolver

Runtime and Settings API MUST use the same canonical resolver.

Forbidden:

```text
UI computes one precedence
runtime computes another precedence
```

Target logical flow:

```text
repository defaults / app config
        +
process environment
        ↓
base settings snapshot
        +
SettingsStore persisted override generation
        ↓
ResolvedSettingsSnapshot
        ↓
runtime composition
```

The existing `app/config.py → app/settings.py:get_settings()` pipeline is evolved by adding the persisted override layer after the deployment/base layer.

No wholesale rewrite of unrelated configuration is authorized.

---

# 4. CONFIGURED VALUE VS EFFECTIVE VALUE

## Decision

YES — they are distinct first-class concepts.

For every registered setting the read model MUST expose:

```text
configured_value
effective_value
persisted_override_value
pending_value
configured_generation
effective_generation
activation_state
```

Definitions:

### configured_value

```text
value that WOULD be used by a fresh runtime
after applying the full precedence chain
```

### persisted_override_value

```text
explicit value stored in SettingsStore
or null when no persisted override exists
```

### effective_value

```text
value actually adopted by the currently running runtime
```

### pending_value

```text
configured_value when it differs from the running effective generation
otherwise null
```

---

## 4.1 Activation states

V1 canonical states:

```text
active

pending_main_restart

activation_failed

runtime_unavailable

consumer_disabled
```

### active

```text
configured_generation == effective_generation
and the owning runtime successfully adopted it
```

### pending_main_restart

```text
persistence committed
but current captive-portal process still uses an older generation
```

### activation_failed

```text
an activation attempt for the configured generation failed
```

### runtime_unavailable

```text
no trustworthy current effective runtime snapshot is available
```

### consumer_disabled

```text
setting is configured but its owning optional feature/component
is currently disabled and therefore has no active consumed value
```

A configured value MUST NOT be displayed as “currently active” merely because Save succeeded.

---

# 5. GLOBAL VS SITE-SCOPED SETTINGS

## Settings V1

All writable Settings V1 keys are:

```text
GLOBAL
```

No Site-scoped mutation is authorized in V1.

Reason:

```text
current environment/configuration semantics are not uniformly Site-scoped
and Site-specific persistence precedence has not yet been admitted.
```

---

## 5.1 Canonical UI route

```text
GET /admin/settings
```

This is a GLOBAL Admin page.

It MUST NOT fake global authorization by selecting the default Site.

---

## 5.2 Canonical API scope

```text
GET  /admin/api/v1/settings
POST /admin/api/v1/settings/generations
```

No `site_id` is accepted by these V1 endpoints.

Reserved future conceptual scope:

```text
/admin/sites/<site_id>/settings
/admin/api/v1/sites/<site_id>/settings
```

is NOT implemented by Settings V1.

---

# 6. APPLY SEMANTICS

## Decision

Settings V1 supports exactly one activation class:

```text
MAIN_SERVICE_RESTART_REQUIRED
```

Every V1 editable key has:

```text
apply_requirement =
restart captive-portal.service
```

No Settings V1 key is hot-reloaded.

No component recreation/reload is implemented for V1.

No auxiliary service restart is implemented for V1.

This is deliberate.

Coder MUST NOT independently decide that a particular integer can be “safely hot-reloaded”.

---

## 6.1 Why

The current application obtains settings during startup/composition and multiple Admin sub-components build validated configuration objects from that snapshot.

V1 preserves one simple invariant:

```text
one running process
→ one effective settings generation
```

---

# 7. RESTART / SERVICE-CONTROL AUTHORITY

## Decision

CaptivPortal Admin Web has:

```text
NO systemd restart/reload authority
```

Settings V1 MUST NOT execute:

```text
systemctl restart
systemctl reload
systemctl try-restart
systemd D-Bus service control
sudo service control
```

No restart button is present in Settings V1.

---

## 7.1 Save result

After successful Save:

```text
Persisted successfully.
Pending captive-portal.service restart.
```

API state:

```text
activation_state = pending_main_restart
```

An external authorized operator performs the restart through the existing deployment/operations channel.

---

# 8. MULTI-PROCESS CONSISTENCY / ATOMIC ACTIVATION

## V1 decision

No editable Settings V1 key may have more than one runtime activation target.

Canonical V1 activation target:

```text
captive-portal.service
```

Therefore:

```text
cross-process writable setting
= OUT OF V1
```

Auxiliary processes continue using their existing deployment-controlled configuration.

---

## 8.1 Future permanent rule

If a future setting is consumed by multiple processes:

```text
one persisted configuration generation
→ explicit activation target set
→ each target reports adopted generation
```

The generation MUST NOT be called fully active until every required target reports the same generation.

Required future states include:

```text
pending_multi_target_activation
partial_activation
active
activation_failed
```

Forbidden:

```text
one process generation N
another process generation N-1
+
UI says "Active"
```

No silent partial activation.

---

# 9. FAILURE SEMANTICS

## 9.1 Validation failure

```text
persistence = NO CHANGE
generation = NOT CREATED
HTTP = 422
```

---

## 9.2 Persistence failure

```text
persistence = NO CHANGE
generation = NOT CREATED
HTTP = 503
```

No in-memory-only “successful” mutation is permitted.

---

## 9.3 Save successful, no restart performed

This is NOT an error.

State:

```text
configured generation = new
effective generation = old
activation_state = pending_main_restart
```

---

## 9.4 Activation/restart attempted and failed

Canonical result:

```text
configured generation remains persisted
activation record = activation_failed
last known effective generation remains recorded
runtime effective state may be unavailable
```

There is:

```text
NO automatic rollback
```

in Settings V1.

Reason:

```text
automatic rollback creates hidden state transitions
and future multi-component side effects are not yet modeled.
```

The failed configured generation remains auditable.

Recovery is an out-of-band operator action.

Admin UI rollback is outside V1.

---

## 9.5 Activation success

A configured generation is marked active only after:

```text
settings load
+
full V1 validation
+
owning runtime composition
+
Admin Web owning components reach accepted ready/active state
```

Reading the DB is NOT enough to mark a generation active.

---

## 9.6 SettingsStore unavailable at application startup

Because V1 manages only non-security Admin presentation settings:

```text
Portal/Auth/CAPPORT/main product runtime
MUST NOT fail because SettingsStore is unavailable.
```

Behavior:

```text
fall back to repository/environment base settings
Settings mutation surface = unavailable
Settings store health = unavailable
other Admin/read surfaces may continue if independently healthy
```

The condition MUST be visible/logged.

No fabricated persisted values.

---

# 10. VALIDATION CONTRACT

## Decision

Create one code-owned:

```text
SettingsDefinitionRegistry
```

This registry is authoritative for:

```text
whether a key is UI-manageable
type
scope
secret class
display metadata
primitive validation
apply requirement
owning subsystem validator
```

The registry is NOT the source of persisted values.

---

## 10.1 Existing validators remain semantic authorities

Existing subsystem validators remain authoritative for their existing configuration contracts.

Settings V1 MUST NOT duplicate their cross-setting semantic rules in JavaScript or in a second unrelated parser.

For affected Admin settings, candidate configuration is validated through the existing Admin configuration boundaries, including where applicable:

```text
AdminWebConfig validator
HomeActivityConfig validator
HomeHealthConfig validator
HomeAp24Config validator
```

---

## 10.2 Primitive validation

Registry primitive bounds MUST run even when an optional consumer is currently disabled.

Reason:

```text
a disabled feature must not allow an invalid hidden persisted value
that later becomes active after deployment enables the feature.
```

---

## 10.3 Atomic group validation

For one mutation request:

```text
current base
+
current persisted overrides
+
all proposed changes
        ↓
candidate full settings snapshot
        ↓
primitive registry validation
        ↓
all affected subsystem validators
        ↓
cross-setting validation
        ↓
ONE atomic persistence transaction
```

If any setting fails:

```text
NONE of the proposed changes are persisted.
```

Partial field success is forbidden.

Frontend validation is UX only.

Backend validation is authoritative.

---

# 11. SECRETS / SENSITIVE CONFIGURATION

V1 introduces an explicit classification.

## Class A — NORMAL

```text
safe non-secret registered setting
```

May be readable/editable only if allowlisted.

All Settings V1 writable keys are Class A.

---

## Class B — SENSITIVE_READONLY

Potential examples:

```text
certificate path
private-key path
credential-file path
integration endpoint identity
```

If a future product needs to show these, only a masked/non-sensitive representation may be returned.

Not editable in V1.

V1 does not require these fields to appear.

---

## Class C — SECRET_WRITE_ONLY

Concept reserved for future use.

Semantics:

```text
existing value never returned
replacement may be accepted only through a separate secret mutation contract
audit records presence/change only
```

Settings V1 implements NO Class C mutation.

---

## Class D — SECRET_FORBIDDEN

Not exposed by Settings API/UI at all.

Includes at minimum:

```text
OMADA CLIENT_SECRET
OAuth/access/bearer tokens
OMADA_WEBHOOK_SHARED_SECRET
OMADA_WEBHOOK_HEADER_TOKEN
WEB_ADMIN_PASSWORD_HASH
WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET
private credential material
private keys
authorization headers/tokens
```

---

## 11.1 Omada non-secret identifiers

Even non-secret Omada integration values such as URL/client identifiers are:

```text
deployment/integration controlled
NOT editable in Settings V1
```

No inference that “not secret” means “UI-editable”.

---

## 11.2 Secret storage

SettingsStore V1 MUST NOT store plaintext secrets.

Future secret mutation requires a separate Secret Storage architecture decision.

---

# 12. ADMIN AUTHORIZATION FOR MUTATION

Current read-only Admin policy is extended conceptually with two separate GLOBAL capabilities:

```text
admin.read.settings.global
admin.write.settings.global
```

They are intentionally distinct.

Current V1 principal type:

```text
platform_operator
```

may be granted both by policy.

But the capability boundary remains separate for future role separation.

---

## 12.1 Global authorization is not Site authorization

Global Settings authorization MUST NOT be implemented as:

```text
authorize(principal, capability, default_site_id)
```

or by choosing an arbitrary allowed Site.

Settings global authorization is a distinct policy decision.

Conceptually:

```text
authorize_global(principal, capability)
```

or an equivalent typed global scope.

---

## 12.2 Future Site capabilities

Reserved architecture names:

```text
admin.read.settings.site
admin.write.settings.site
```

Not implemented in V1.

---

# 13. MUTATION HTTP / SECURITY CONTRACT

## 13.1 Read

```text
GET /admin/api/v1/settings
```

Authentication:

```text
existing Admin authenticated session
+
admin.read.settings.global
```

Response:

```text
Content-Type: application/json
Cache-Control: no-store
ETag: "settings-g<configured_generation>"
```

---

## 13.2 Mutation

Canonical mutation endpoint:

```text
POST /admin/api/v1/settings/generations
```

Meaning:

```text
create one new immutable configured generation
from an atomic batch of override changes
```

Authentication:

```text
existing Admin authenticated session
+
admin.write.settings.global
```

---

## 13.3 Content type

Exactly:

```text
application/json
```

No form-urlencoded Settings mutation.

Login/logout form POST contract is NOT reused.

---

## 13.4 Body limit

Dedicated Settings mutation body limit:

```text
32768 bytes
```

Maximum changes in one mutation:

```text
64
```

Both are server enforced.

These limits are deployment-controlled, not editable through Settings V1.

---

## 13.5 CSRF

Mutation requires:

```text
X-CSRF-Token
```

matching the authenticated Admin session CSRF token using the existing canonical token/constant-time comparison boundary.

Session cookie remains:

```text
Secure
HttpOnly
SameSite=Strict
```

Settings JSON mutation MUST NOT accept a CSRF token from query string.

---

## 13.6 Request shape

Canonical:

```json
{
  "changes": [
    {
      "key": "WEB_ADMIN_DEVICE_PAGE_SIZE",
      "operation": "set",
      "value": 100
    },
    {
      "key": "WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS",
      "operation": "clear_override"
    }
  ]
}
```

Allowed operations:

```text
set
clear_override
```

Unknown fields/operations/keys are rejected.

Duplicate keys in one request are rejected.

---

## 13.7 Optimistic concurrency

Mutation requires:

```text
If-Match: "settings-g<configured_generation>"
```

Missing:

```text
428 Precondition Required
```

Stale/mismatched:

```text
412 Precondition Failed
```

The generation compare-and-swap occurs inside the same SQLite transaction as persistence.

---

## 13.8 Idempotency

Mutation requires:

```text
Idempotency-Key
```

Canonical value:

```text
UUID
```

The key is persisted with:

```text
principal
scope
request payload hash
result generation
```

Replay:

```text
same principal + same idempotency key + same payload
→ return original accepted result
```

Conflict:

```text
same idempotency key + different payload
→ 409 idempotency_conflict
```

---

## 13.9 Success response

Changed:

```text
201 Created
```

Canonical fields:

```text
api_version
request_id
scope
changed = true
configured_generation
effective_generation
activation_state
restart_required
settings
```

No semantic persisted change:

```text
200 OK
changed = false
no new generation
```

“No change” compares persisted override state, not merely the visible effective scalar.

---

## 13.10 Error contract

Canonical error envelope:

```json
{
  "api_version": "admin.settings.v1",
  "request_id": "<uuid>",
  "error": {
    "code": "validation_failed",
    "details": [
      {
        "key": "WEB_ADMIN_DEVICE_PAGE_SIZE",
        "reason": "out_of_range"
      }
    ]
  }
}
```

Canonical classes:

```text
400 invalid_request
400 invalid_csrf

401 authentication_required

403 settings_forbidden

404 not_found / feature_disabled

409 idempotency_conflict

412 stale_generation

413 request_too_large

415 unsupported_media_type

422 validation_failed

428 precondition_required

503 settings_store_unavailable

500 internal_error
```

Do not return stack traces, raw DB errors, secret values, or environment dumps.

---

# 14. DURABLE AUDIT

YES — durable configuration audit is mandatory.

Audit and generation commit MUST be transactionally linked.

For every accepted generation record:

```text
generation_id
parent_generation_id

principal_type
principal_name

source_ip
request_id
idempotency_key

timestamp_utc

scope_type
scope_id

setting_key
operation

previous_persisted_override
new_persisted_override

previous_configured_value
new_configured_value

apply_requirement
activation_target
```

Activation produces a separate durable event:

```text
generation_id
target
attempted_at
activation_result
effective_generation_after_attempt
safe error_code if failed
```

---

## 14.1 Secret audit rule

For any future secret:

```text
NO raw previous secret
NO raw new secret
NO reversible representation
```

Audit stores only:

```text
secret_changed = true
previous_presence = present/absent
new_presence = present/absent
```

V1 has no writable secret settings.

---

# 15. CONCURRENT EDITING / STALE FORM PROTECTION

YES — mandatory.

Canonical mechanism:

```text
generation ETag + If-Match
```

A Settings page opened at generation 10 MUST NOT silently overwrite generation 11.

Client behavior on:

```text
412 stale_generation
```

must be:

```text
do not retry automatically
reload current Settings read model
show conflict/stale-page message
require operator to review and resubmit
```

No last-writer-wins mutation.

---

# 16. ROLLBACK / HISTORY

SettingsStore MUST retain immutable prior generations and audit history.

Settings V1 UI does NOT provide:

```text
history browser
rollback button
activate old generation
```

Therefore:

```text
UI rollback = OUT OF V1
```

Previous generations exist for:

```text
audit
forensics
future recovery tooling
future explicit rollback feature
```

No automatic pruning is required in V1 because V1 values are tiny, non-secret and configuration changes are low-volume.

Any future UI rollback is itself a NEW mutation that must create a NEW generation.

It must never mutate history in place.

---

# 17. SELF-LOCKOUT SETTINGS

Settings V1 MUST NOT allow mutation of any setting that can remove or materially weaken the operator's own access path.

Explicitly forbidden:

```text
WEB_ADMIN_ENABLED

WEB_ADMIN_ALLOWED_NETWORKS

WEB_ADMIN_ALLOWED_SITE_IDS

WEB_ADMIN_DEFAULT_SITE_ID

WEB_ADMIN_REQUIRE_HTTPS

WEB_ADMIN_USERNAME

WEB_ADMIN_PASSWORD_HASH

session/login/CSRF security bounds

Admin bind/listen security boundary

Settings feature bootstrap enable/path
```

These values are not normal editable controls.

No “Are you sure?” safeguard is considered sufficient for V1.

The architectural safeguard is:

```text
NOT EDITABLE
```

Future self-lockout-capable mutation requires a separate contract with external recovery proof.

---

# 18. CURRENT HARDCODED CAPPORT SETTINGS

## Exact decision

CAPPORT remains:

```text
CODE / DEPLOYMENT CONTROLLED
AND OUTSIDE SETTINGS UI V1
```

Do NOT opportunistically migrate current CAPPORT constants into the writable SettingsStore as part of Settings V1.

Do NOT create a separate CAPPORT Settings owner.

Current CAPPORT configuration ownership remains unchanged until a separate dedicated architecture/task explicitly moves it.

Reason:

```text
CAPPORT affects client network behavior / external contract
and is not equivalent to harmless Admin presentation configuration.
```

Future CAPPORT settings integration may reuse the Settings control-plane architecture, but is not authorized now.

---

# 19. AUXILIARY DIRECT-ENV CONFIGURATION

## V1 decision

Auxiliary-process direct-env configuration is:

```text
OUT OF SETTINGS V1
```

SettingsStore does NOT become authoritative for auxiliary services merely because those variables appear related.

No V1 Settings mutation may require:

```text
auxiliary service restart
multi-process generation adoption
generated EnvironmentFile
systemd daemon-reload
```

Those processes retain their existing deployment/startup boundaries.

---

## 19.1 Future admission requirement

To bring an auxiliary process into Settings later, a separate contract MUST freeze:

```text
process identity
settings ownership
read mechanism
generation adoption
activation target
restart/reload semantics
failure behavior
partial activation behavior
rollback
```

Only then can it consume SettingsStore values.

---

# 20. SETTINGS UI READ MODEL

Canonical per-setting frontend contract:

```text
SettingReadModelV1
```

Required fields:

```text
key
display_label
description
group

value_type

scope_type
scope_id

editable
read_only_reason

secret_class

default_value
base_source
base_value

persisted_override_value
configured_value
effective_value
pending_value

configured_generation
effective_generation

activation_state
apply_requirement
activation_target

consumer_state

validation

last_changed_at
last_changed_by
```

---

## 20.1 `validation`

For integer V1 settings:

```json
{
  "type": "integer",
  "min": 1,
  "max": 500
}
```

Frontend MUST render from server metadata.

Frontend MUST NOT maintain an independent hidden table of validation bounds.

---

## 20.2 `base_source`

Canonical:

```text
environment
repository_default
```

It identifies the layer below persisted override.

---

## 20.3 `apply_requirement`

V1 exact value:

```text
main_service_restart
```

---

## 20.4 `activation_target`

V1:

```text
captive-portal.service
```

---

## 20.5 Page-level metadata

`GET /admin/api/v1/settings` also returns:

```text
api_version = admin.settings.v1

scope =
  type = global

store_state

configured_generation
effective_generation

etag

restart_required

pending_setting_count

settings[]
```

---

# 21. SETTINGS DEFINITION REGISTRY — CANONICAL V1 MATRIX

| Key | Group | Type | Scope | Bounds | Editable | Secret | Apply |
|---|---|---|---|---|---|---|---|
| `WEB_ADMIN_DEVICE_PAGE_SIZE` | pagination | int | global | 1..500 | yes | normal | main restart |
| `WEB_ADMIN_VISIT_PAGE_SIZE` | pagination | int | global | 1..500 | yes | normal | main restart |
| `WEB_ADMIN_OBSERVATION_PAGE_SIZE` | pagination | int | global | 1..500 | yes | normal | main restart |
| `WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS` | pagination | int | global | 1..168 | yes | normal | main restart |
| `WEB_ADMIN_CURRENT_STATE_PAGE_SIZE` | pagination | int | global | 1..250 | yes | normal | main restart |
| `WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE` | pagination | int | global | 1..250 | yes | normal | main restart |
| `WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS` | refresh | int | global | 60..300 | yes | normal | main restart |
| `WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS` | refresh | int | global | 60..300 | yes | normal | main restart |
| `WEB_ADMIN_TRAFFIC_REFRESH_SECONDS` | refresh | int | global | 60..300 | yes | normal | main restart |
| `WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS` | refresh | int | global | 60..300 | yes | normal | main restart |
| `WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS` | refresh | int | global | 60..300 | yes | normal | main restart |
| `WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS` | refresh | int | global | 60..600 | yes | normal | main restart |

Any key absent from this table is:

```text
NOT WRITABLE IN SETTINGS V1
```

regardless of whether it is environment-driven.

---

# 22. TARGET CONFIGURATION FLOW

```text
Repository defaults
        ↓
Process environment
        ↓
Base settings
        ↓
SettingsStore global override generation
        ↓
ResolvedSettingsSnapshot
        ↓
Existing subsystem validators
        ↓
Runtime composition
        ↓
Effective generation
```

Admin mutation path:

```text
Settings page
        ↓
authenticated JSON mutation
        ↓
CSRF + capability + ETag + idempotency
        ↓
SettingsDefinitionRegistry
        ↓
candidate full snapshot
        ↓
primitive + subsystem + cross-setting validation
        ↓
ONE SQLite transaction
        ↓
new configured generation
        ↓
pending_main_restart
        ↓
external operator restart
        ↓
runtime composition succeeds
        ↓
effective generation = configured generation
```

---

# 23. SECURITY INVARIANTS

Permanent for Settings V1:

```text
deny-by-default editability

no raw .env editing

no arbitrary setting names

no secret mutation

no systemd authority

no Site authorization spoofing for global mutation

no client-side-only validation

no partial batch persistence

no last-writer-wins

no silent activation

no silent fallback from configured to active wording

no direct DB mutation from route/UI layer

no stack traces or raw config dumps

no self-lockout settings
```

---

# 24. IMPLEMENTATION BOUNDARY FOR TECHNICAL DEVELOPER SETTINGS

After this architecture is Tech Lead accepted, Technical Developer Settings must prepare ONE exact implementation TASK.

That task must include:

```text
exact baseline commit/tree

exact new/modified files

Settings domain module boundaries

SQLite schema/migration/bootstrap

SettingsDefinitionRegistry exact implementation matrix

resolved-settings integration point

Admin page/navigation integration

global authorization-policy extension

GET/POST API contracts

JSON parser/body limits

CSRF implementation

ETag/If-Match implementation

Idempotency-Key implementation

atomic validation/persistence behavior

activation-generation reporting

audit persistence

UI read model

pending-restart UX

targeted tests

failure-path tests

forbidden-change list

production activation gate
```

Coder MUST NOT make architecture decisions that differ from this contract.

---

# 25. EXPLICIT NON-GOALS FOR IMPLEMENTATION TASK V1

The implementation TASK MUST forbid:

```text
CAPPORT migration

Omada credential mutation

Admin credential mutation

Admin network/Site allowlist mutation

systemd restart/reload

hot reload

auxiliary process integration

Site-scoped settings

secret store implementation

generic environment editor

feature-enable toggles

destructive worker settings

configuration rollback UI

history browser UI

arbitrary configuration search/edit

unrelated refactors
```

---

# 26. REVIEW QUESTIONS FOR TECH LEAD

Tech Lead review should explicitly disposition:

```text
S1  V1 exact allowlist = PASS / REVISE

S2  SQLite SettingsStore owner/path = PASS / REVISE

S3  precedence:
    persisted global > env > repository default
    = PASS / REVISE

S4  configured/effective/pending model = PASS / REVISE

S5  GLOBAL-only V1 scope = PASS / REVISE

S6  all V1 changes require main service restart = PASS / REVISE

S7  Admin Web has NO systemd authority = PASS / REVISE

S8  no multi-process V1 settings = PASS / REVISE

S9  no automatic rollback = PASS / REVISE

S10 registry + existing validators + atomic batch validation = PASS / REVISE

S11 no writable secrets V1 = PASS / REVISE

S12 capabilities:
    admin.read.settings.global
    admin.write.settings.global
    = PASS / REVISE

S13 HTTP mutation contract = PASS / REVISE

S14 durable audit = PASS / REVISE

S15 ETag stale-write protection = PASS / REVISE

S16 history retained, UI rollback out of V1 = PASS / REVISE

S17 self-lockout settings forbidden = PASS / REVISE

S18 CAPPORT remains outside V1 = PASS / REVISE

S19 auxiliary env settings outside V1 = PASS / REVISE

S20 SettingReadModelV1 = PASS / REVISE
```

---

# 27. CURRENT AUTHORIZATION STATE

```text
ADMIN SETTINGS ARCHITECTURE =
DRAFT FOR TECH LEAD REVIEW

TECHNICAL DEVELOPER SETTINGS =
AUTHORIZED TO REVIEW / PREPARE COMMENTS ONLY

IMPLEMENTATION TASK =
NOT YET AUTHORIZED FOR CODER

CODER =
HOLD

PRODUCTION =
NO CHANGE

SYSTEMD CONTROL =
NO

CAPPORT SETTINGS =
OUT OF V1

SECRETS =
OUT OF V1

SITE-SCOPED MUTATION =
OUT OF V1

NEXT =
TECH LEAD ARCHITECTURE REVIEW
→ bounded revisions if required
→ FINAL architecture
→ Technical Developer Settings writes exact implementation TASK
→ Tech Lead implementation-contract review
→ only then Coder
```
