# TASK-ADMIN-SETTINGS-03 — OMADA CONTROLLER WRITABLE NON-SECRET CONFIGURATION

**Project:** CaptivPortal  
**Area:** Admin UI → Settings → Controller  
**Stage:** Settings Stage 3  
**Document type:** FINAL IMPLEMENTATION TASK / BINDING CODER CONTRACT  
**Task ID:** `TASK-ADMIN-SETTINGS-03`  
**Task name:** `OMADA CONTROLLER WRITABLE NON-SECRET CONFIGURATION`  
**Status:** **FINAL — CODER AUTHORIZED**  

---

# 0. AUTHORITY / BASELINE / GATE

## 0.1 Authoritative code baseline

Implementation MUST start from exactly:

```text
main@c1167180daec9ca17d13ab44326f143122db8d5e
TREE=278df41bfa3134b22963b41006585da35de08074
```

At task issue time, GitHub `main` was independently rechecked and the latest commit remained:

```text
c1167180daec9ca17d13ab44326f143122db8d5e
Merge pull request #185
ADMIN-SETTINGS-02: add read-only Omada Controller settings
```

If Coder's implementation worktree does not have this exact parent/tree before modification:

```text
STOP
DO NOT silently rebase
DO NOT transplant onto a different main
RETURN BASELINE DRIFT TO TECH LEAD
```

## 0.2 Binding architecture

This TASK implements, without reinterpretation:

```text
CAPTIVPORTAL-ADMIN-SETTINGS-OMADA-CONTROLLER-WRITABLE-NONSECRET-
ARCHITECTURE-CONTRACT-v0.1

+

CAPTIVPORTAL-ADMIN-SETTINGS-OMADA-CONTROLLER-WRITABLE-NONSECRET-
ARCHITECTURE-CONTRACT-v0.1-R1

+

CAPTIVPORTAL-ADMIN-SETTINGS-STAGE3-TECH-LEAD-ARCHITECTURE-REVIEW-R2-ACCEPTED
```

Architecture disposition:

```text
FINAL / TECH LEAD ACCEPTED
OPEN P0 = 0
OPEN P1 = 0
```

Where R1 conflicts with the original v0.1 text, **R1 wins**.

In particular, original v0.1 section 60's full Controller V2 mutation response is superseded by the R1 **bounded mutation receipt + mandatory re-GET** contract.

## 0.3 Current authorization

```text
CODER IMPLEMENTATION          = GO
LOCAL TESTING                 = GO
LOCAL LAB-ONLY COMMIT         = ALLOWED

PUSH                          = HOLD
PR                            = HOLD
MERGE                         = NO
DEPLOY                        = NO
PRODUCTION ACTION             = NO
SYSTEMD ACTION                = NO
MANUAL PRODUCTION DB ACTION   = NO
```

Coder stops after implementation + evidence handoff.

---

# 1. OBJECTIVE

Turn the existing Stage-2 Controller Settings page from a safe read-only projection into a safe Settings-controlled write surface for exactly:

```text
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
```

while preserving one common CaptivPortal Settings control plane:

```text
SettingsDefinitionRegistry
        ↓
SettingsStore
        ↓
global immutable generation chain
        ↓
canonical validation
        ↓
pending main-service restart
        ↓
exact startup snapshot G
        ↓
OmadaControllerRuntimeConfig(G)
        ↓
shared OmadaProvider
        ↓
durable Settings adoption
        ↓
effective Controller snapshot(G)
```

The implementation is complete only when persistence, migration, read/write API, UI, authorization, startup/adoption sequencing, secret isolation, and regression evidence all satisfy this contract.

---

# 2. EXACT STAGE-3 SCOPE

## 2.1 Writable Controller definitions

Add exactly three writable Controller definitions:

```text
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
```

Canonical mapping:

| Settings key | settings mapping key | domain | type | presentation | required | scope | apply |
|---|---|---|---|---|---|---|---|
| `OMADA_URL` | `omada_url` | `controller` | `string` | `url` | yes | `global` | `main_service_restart` |
| `OMADA_ID` | `omada_id` | `controller` | `string` | `string` | yes | `global` | `main_service_restart` |
| `OMADA_CLIENT_ID` | `client_id` | `controller` | `string` | `string` | yes | `global` | `main_service_restart` |

For all three:

```text
secret_class = normal
editable = true
activation_target = captive-portal.service
consumer = required shared OmadaProvider
```

## 2.2 Explicitly NOT writable

```text
OMADA_CLIENT_SECRET
VERIFY_SSL / tls_certificate_verification
```

No fourth Controller setting may be admitted.

## 2.3 Permanent boundaries

Do NOT implement:

```text
Secret Storage
OMADA_CLIENT_SECRET mutation
secret encryption / rotation / recovery
VERIFY_SSL mutation
TLS trust-store management

Test Connection
live Controller health
OAuth health
token refresh/reset
reconnect
reauthenticate
hot provider recreation
hot reload

OpenAPI client CRUD
Omada-side Controller configuration mutation

Site-scoped Controller settings
multi-controller

generic environment editor
.env editor

systemd control
sudo
restart button

Controller-specific database
Controller-specific generation chain
Controller-specific CAS engine

automatic rollback
history browser
rollback UI
auxiliary-process activation
```

---

# 3. SOURCE-VERIFIED BASELINE FACTS CODER MUST PRESERVE

At the baseline:

```text
app/settings_control/definitions.py
- one 12-definition integer-only registry
- settings_dict_key currently inferred via key.lower()
- environment_variable_name currently inferred from key

app/settings_control/repository.py
- SETTINGS_SCHEMA_VERSION = 1
- settings_overrides is integer-only
- mutation audit value columns are integer-only
- idempotency uniqueness has no mutation domain
- idempotency response JSON is physically bounded to <= 65536 bytes

app/settings_control/resolver.py
- one resolver
- integer-oriented coercion
- explicit environment membership is already used for provenance

app/settings_control/validation.py
- current common validation is integer/general oriented

app/settings_control/bootstrap.py
- Settings-enabled Store startup failure currently falls back to base settings

app/settings_control/services.py
- one common SettingsMutationService
- one common generation chain
- idempotent replay precedes normal stale-CAS rejection
- successful response is stored durably for replay

app/settings_control/activation.py
- durable main-service adoption exists
- effective generation is advanced by SettingsActivationService

app/controllers/omada_config.py
- canonical OmadaControllerRuntimeConfig exists
- Omada validation/normalization already has one owner
- provider construction from typed config is network-free
- public snapshot is secret-free

app/admin_web/controller_settings.py
- Stage-2 effective-only Controller read service exists

app/admin_web/routes.py
- Controller GET exists
- General Settings GET/POST exist
- current Admin POST boundary special-cases only General Settings JSON mutation

app/admin_web/policy.py
- admin.read.settings.controller exists
- admin.write.settings.controller does not yet exist

run.py
- shared typed Controller config/provider already exist
- several Controller-dependent workers currently start before Settings adoption
```

Do not regress the Stage-1 or Stage-2 guarantees while generalizing these boundaries.

---

# 4. ONE DOMAIN-AWARE SETTINGS DEFINITION REGISTRY

There remains exactly one:

```text
SettingsDefinitionRegistry
```

After Stage 3:

```text
TOTAL      = 15
GENERAL    = 12
CONTROLLER = 3
```

The original twelve definitions MUST retain their exact external semantics:

```text
keys
integer type
defaults
bounds
groups
consumer enabled/disabled semantics
General API membership
General mutation route
General authorization
General UI behavior
configured/effective behavior
```

The registry must become domain-aware:

```text
domain = general | controller
```

and must explicitly own mapping metadata; Controller mapping MUST NOT depend on naming inference.

At minimum a definition must logically own:

```text
key
settings_dict_key
environment_variable_name
repository_default_value
domain
value_type
presentation_type
scope_type
secret_class
editable
required
validation / normalization profile
apply_requirement
activation_target
consumer semantics
display_label
description
```

For General definitions, implementation may preserve existing integer-specific metadata such as `min_value`, `max_value`, `group`, and consumer-enable key.

Do not create a second Controller registry.

---

# 5. GENERAL API MUST REMAIN A 12-SETTING DOMAIN

The common registry has 15 definitions, but:

```text
GET /admin/api/v1/settings
POST /admin/api/v1/settings/generations
```

remain **General-domain APIs**.

They must expose/mutate only the original twelve `domain=general` definitions.

Required:

```text
GET /admin/api/v1/settings
→ api_version remains admin.settings.v1
→ settings count remains exactly 12
→ existing Stage-1 representation remains compatible

POST /admin/api/v1/settings/generations
→ admin.write.settings.global
→ rejects Controller-domain keys
```

Do not make `settings.js` understand Controller fields.

---

# 6. SETTINGSSTORE SCHEMA v2

## 6.1 One existing database

There remains one configured Settings DB:

```text
SETTINGS_DB_PATH
default /opt/CaptivePortal/data/settings.sqlite3
```

No new DB.

## 6.2 Version

Advance:

```text
SETTINGS_SCHEMA_VERSION
1 → 2
```

A new empty database is created directly as schema v2.

Existing schema-v1 databases migrate automatically **in place** during normal SettingsStore initialization.

No external/manual migration command is part of Stage 3.

## 6.3 Typed override rows

`settings_overrides` must support exactly:

```text
integer
string
```

Conceptual invariant:

```text
value_type = integer
→ integer storage populated
→ string storage null

value_type = string
→ string storage populated
→ integer storage null
```

No:

```text
secret
binary
arbitrary JSON setting value
```

type is admitted.

The repository API must return typed Python scalars and preserve a complete generation override snapshot containing both General integer and Controller string overrides.

## 6.4 Immutable generation history

Schema v2 must preserve the existing immutable-generation model.

Generation 0 remains:

```text
generation_id = 0
parent = null
scope = global
persisted overrides = empty
```

Schema migration itself creates:

```text
NO new configured generation
NO mutation audit event
NO activation transition
```

---

# 7. REQUIRED v1 → v2 TRANSACTIONAL MIGRATION

Migration must be:

```text
in-place
single-transaction
non-destructive
history-preserving
fail-closed on any integrity/migration failure
```

It MUST preserve exactly:

```text
all generation IDs
all parent_generation_id relationships
generation 0
current configured head
effective_generation target state
activation events
safe_error_code history
mutation audit chronology
existing General overrides
successful idempotency records
created timestamps / principals / request IDs
```

Existing v1 override rows become v2:

```text
value_type = integer
integer value preserved exactly
string value = null
```

Existing idempotency rows become:

```text
mutation_domain = general
```

New Controller idempotency rows use:

```text
mutation_domain = controller
```

Idempotency uniqueness becomes logically:

```text
principal_type
+
principal_name
+
scope_type
+
mutation_domain
+
idempotency_key
```

Existing successful Stage-1 replay response bodies MUST NOT be semantically rewritten.

If audit schema materializes domain/type metadata, existing audit rows migrate deterministically as:

```text
setting_domain = general
value_type = integer
```

New Controller audit rows:

```text
setting_domain = controller
value_type = string
```

All immutable-history protections must still apply after migration.

The physical v2 DDL is implementation-owned, but it must enforce the typed-value invariants above and pass explicit migration/integrity tests.

---

# 8. IDEMPOTENCY RESPONSE STORAGE REMAINS BOUNDED

Keep the existing durable result bound:

```text
settings_idempotency.result_response_json <= 65536 bytes
```

Do not increase or remove it for Stage 3.

A successful Settings mutation is atomic with its durable idempotency success record.

Forbidden state:

```text
generation committed
but replay receipt not durably committed
```

If the exact Controller mutation receipt cannot be persisted within the limit:

```text
rollback whole transaction
HTTP 500 internal_error
NO generation
NO override mutation
NO audit
NO success replay row
```

---

# 9. RESOLUTION / PRECEDENCE / PROVENANCE

For each Controller definition:

```text
persisted GLOBAL override
>
explicit process-startup environment
>
repository default
```

Canonical source vocabulary:

```text
persisted_override
environment
repository_default
```

`environment` means only:

```text
the explicit process environment captured at process startup
```

No request-time:

```text
os.environ reread
systemctl show
EnvironmentFile parse
/etc/default parse
```

is permitted.

The single resolver must support typed General and Controller definitions without changing General behavior.

A shadowed invalid Controller lower-precedence value does NOT invalidate a valid selected persisted override.

Validation targets the resolved selected configured Controller values.

---

# 10. STRING CANONICALIZATION AND PERSISTENCE

Persist Controller string overrides only after canonical normalization.

Examples:

```text
input:
"  https://controller.example:8043/  "

persisted:
"https://controller.example:8043"
```

```text
input:
"  controller-id  "

persisted:
"controller-id"
```

No raw browser string is stored when a canonical string differs.

For no-op determination:

```text
parse
→ canonicalize
→ validate
→ compare resulting persisted override state
```

If existing override is already canonical X and the newly submitted raw string canonicalizes to X:

```text
changed = false
NO generation
```

But:

```text
no persisted override
+
environment effective scalar = X
+
operator explicitly sets persisted override = X
```

IS a persisted-ownership change:

```text
changed = true
new generation
```

Scalar equality alone does not erase ownership semantics.

---

# 11. CLEAR OVERRIDE

`clear_override` means:

```text
delete persisted override for that key
→ expose next lower-precedence source
→ canonicalize
→ validate the COMPLETE resulting Controller configuration
→ commit only if valid
```

It does NOT copy the environment/default scalar into SettingsStore.

If clear would expose an invalid/missing required value:

```text
422 validation_failed
NO generation
NO audit
NO successful idempotency record
NO configured-state change
```

This rule applies to all three admitted Controller keys.

---

# 12. ONE CANONICAL CONTROLLER VALIDATION OWNER

Do not create Settings-only Omada validation semantics.

The semantic owner remains:

```text
app/controllers/omada_config.py
```

Refactoring into reusable local validation/normalization primitives is allowed and expected if needed, but:

```text
Settings candidate validation
and
runtime OmadaControllerRuntimeConfig construction
```

must use the same rules.

Required `OMADA_URL` semantics remain exactly:

```text
must be string
strip surrounding whitespace
required / non-empty
scheme http or https
hostname required
valid port when present
port != 0
no userinfo
no query
no fragment
path only empty or "/"
no whitespace
canonical trailing root "/" removal
```

Required `OMADA_ID` / `OMADA_CLIENT_ID` semantics:

```text
must be string
strip surrounding whitespace
required / non-empty
```

Do NOT invent:

```text
charset whitelist
case normalization
Omada semantic max length
```

No validation may perform:

```text
DNS
TCP
TLS
OAuth
token
/sites
Controller HTTP
```

I/O.

---

# 13. FULL CANDIDATE VALIDATION

Every successful mutation — General or Controller — must leave one valid full Settings generation.

Conceptually:

```text
startup base snapshot
+
complete persisted override snapshot at head
+
requested domain changes
        ↓
typed resolve
        ↓
General primitive/semantic validation
        ↓
canonical complete Controller validation
        ↓
atomic generation commit or no commit
```

Controller validation includes the existing non-writable runtime prerequisite:

```text
OMADA_CLIENT_SECRET
```

but any error attributable to that prerequisite must remain bounded/safe and MUST NOT reveal:

```text
secret value
length
prefix
suffix
hash
fingerprint
```

A safe category equivalent to:

```text
controller_prerequisite_invalid
```

is acceptable where needed.

---

# 14. CONTROLLER MUTATION HTTP ENDPOINT

Add exactly:

```text
POST /admin/api/v1/settings/controller/generations
```

It is a separate HTTP authorization façade only.

It MUST delegate to the same common Settings mutation engine / repository / global generation chain.

No second:

```text
ControllerMutationStore
ControllerGenerationStore
Controller CAS
```

is allowed.

The common mutation boundary must take an explicit mutation domain:

```text
general
controller
```

and reject keys not belonging to the selected domain.

No mixed General+Controller HTTP batch.

---

# 15. CONTROLLER MUTATION REQUEST CONTRACT

Content:

```text
Content-Type: application/json
maximum raw request body: 32768 bytes
maximum changes: 3
```

Canonical shape:

```json
{
  "changes": [
    {
      "key": "OMADA_URL",
      "operation": "set",
      "value": "https://controller.example:8043"
    },
    {
      "key": "OMADA_CLIENT_ID",
      "operation": "clear_override"
    }
  ]
}
```

Allowed:

```text
operation = set
operation = clear_override
```

For Controller:

```text
set
→ requires JSON string value

clear_override
→ value member forbidden
```

Strictly reject:

```text
unknown top-level members
unknown change members
duplicate JSON members
duplicate setting keys
empty changes
>3 changes
Site fields
scope fields
General keys
OMADA_CLIENT_SECRET
VERIFY_SSL
non-string set value
non-JSON constants
malformed JSON
query parameters
```

The accepted Controller mutation API error family is defined in section 22 below.

---

# 16. MUTATION SECURITY / CONCURRENCY

Controller POST requires all of:

```text
authenticated Admin session
admin.write.settings.controller
valid X-CSRF-Token
valid If-Match
valid UUID Idempotency-Key
application/json
bounded body
```

CAS uses the **common global Settings configured generation**:

```text
If-Match: "settings-gN"
```

There is no Controller-local generation.

Required:

```text
missing If-Match
→ 428 precondition_required

malformed If-Match
→ 400 invalid_request

stale generation
→ 412 stale_generation

same idempotency identity + different canonical payload
→ 409 idempotency_conflict
```

Successful replay of the same identity/payload occurs before ordinary current-head stale rejection and performs:

```text
NO current-head CAS
NO new validation
NO new generation
NO new audit
NO Settings mutation
```

It returns the exact original stored mutation receipt.

A General mutation may stale an open Controller page because both domains share one global generation chain. This is required.

---

# 17. IDEMPOTENCY DOMAIN

The common mutation engine/repository must carry:

```text
mutation_domain = general | controller
```

General endpoint:

```text
mutation_domain = general
```

Controller endpoint:

```text
mutation_domain = controller
```

The same UUID may therefore exist independently in General and Controller domains for the same principal/scope without cross-surface replay.

No successful General replay body may ever be returned by Controller POST.

---

# 18. BOUNDED CONTROLLER MUTATION RECEIPT — R1 OVERRIDE

**This section supersedes original architecture v0.1 section 60.**

Successful Controller POST MUST NOT return or persist the full Controller V2 projection.

Canonical API version:

```text
admin.settings.controller.mutation.v1
```

Changed response:

```json
{
  "api_version": "admin.settings.controller.mutation.v1",
  "request_id": "<uuid>",
  "scope": {"type": "global"},
  "resource": {
    "type": "omada_controller",
    "scope": "installation"
  },
  "changed": true,
  "changed_keys": ["OMADA_URL"],
  "configured_generation": 12,
  "effective_generation": 11,
  "activation_state": "pending_main_restart",
  "restart_required": true
}
```

Status:

```text
201 Created
```

No-op response:

```json
{
  "api_version": "admin.settings.controller.mutation.v1",
  "request_id": "<uuid>",
  "scope": {"type": "global"},
  "resource": {
    "type": "omada_controller",
    "scope": "installation"
  },
  "changed": false,
  "changed_keys": [],
  "configured_generation": 11,
  "effective_generation": 11,
  "activation_state": "active",
  "restart_required": false
}
```

Status:

```text
200 OK
```

Receipt MUST contain no Controller scalar values, including no:

```text
Controller URL
Controller ID
Client/Application ID
persisted_override_value
configured_value
configured_source
effective_value
effective_source
pending_value
pending_source
client secret data
```

`changed_keys` is bounded to the exact three-key allowlist.

Successful response header:

```text
ETag: "settings-g<configured_generation>"
```

---

# 19. UI MUST RE-GET AFTER EVERY SUCCESSFUL CONTROLLER POST

After every Controller mutation success:

```text
200 or 201
```

including an idempotent replay, browser MUST immediately perform:

```text
GET /admin/api/v1/settings/controller
```

and use that GET as the authoritative field presentation.

Reason:

```text
mutation receipt = durable commit acknowledgement
Controller GET = current configured/effective truth
```

Do not render field state directly from the receipt.

---

# 20. AUTHORIZATION

Add exactly:

```text
admin.write.settings.controller
```

Keep:

```text
admin.read.settings.controller
```

distinct.

Current `platform_operator` policy:

```text
read Controller  = allowed
write Controller = allowed
```

No Site inputs or authorization dependency.

Do not use:

```text
default_site_id
allowed Site IDs
AdminSiteContextResolver
site_id
```

for Controller Settings.

General capability:

```text
admin.write.settings.global
```

MUST NOT authorize Controller mutation.

Controller write capability MUST NOT authorize General mutation.

Controller write 403 code:

```text
controller_settings_forbidden
```

Page/navigation still depend on Controller **read** capability.

Edit controls additionally depend on Controller **write** capability.

Direct POST checks write authorization independently from rendered UI.

---

# 21. ADMIN JSON BOUNDARY

The existing global Admin `before_app_request` currently treats POSTs as form-urlencoded except for the existing General Settings mutation route.

Stage 3 MUST carve out the new Controller JSON mutation route as well, without weakening login/logout or unrelated Admin POST handling.

Required invariant:

```text
/admin/api/v1/settings/generations
/admin/api/v1/settings/controller/generations
→ their own strict JSON mutation contract

all other existing Admin POSTs
→ existing form/media-type boundary unchanged
```

Do not globally relax Admin POST content-type handling.

---

# 22. CONTROLLER MUTATION ERROR TAXONOMY

Required exposed Controller mutation errors:

```text
400 invalid_request
400 invalid_csrf

401 authentication_required

403 controller_settings_forbidden

404 feature_disabled

409 idempotency_conflict

412 stale_generation

413 request_too_large

415 unsupported_media_type

422 validation_failed

428 precondition_required

503 settings_store_unavailable

500 internal_error
```

Use bounded Controller-specific mutation response/error serialization.

Do not return raw exception text.

Safe field details may identify only key + bounded reason, e.g.:

```json
{"key":"OMADA_URL","reason":"required"}
{"key":"OMADA_URL","reason":"invalid_url"}
{"key":"OMADA_CLIENT_ID","reason":"required"}
```

Never echo the rejected scalar.

Do not expose secret-adjacent data.

General Settings error/API behavior remains backward compatible.

---

# 23. CONTROLLER READ API V2

Preserve path:

```text
GET /admin/api/v1/settings/controller
```

Bump successful model:

```text
admin.settings.controller.v1
→ admin.settings.controller.v2
```

Preserve Stage-2 meanings:

```text
effective_value
effective_source
effective_presence
```

They continue to mean actual currently adopted runtime state.

Top-level V2 must contain:

```text
api_version
request_id

scope.type = global

resource.type = omada_controller
resource.scope = installation

management_mode = hybrid

store_state

configured_generation
effective_generation

activation_state
restart_required

pending_controller_setting_count

fields
```

When configured Store state is available:

```text
ETag: "settings-g<configured_generation>"
```

No Controller-local ETag.

No Controller-local generation.

Controller GET remains:

```text
ZERO Omada/OAuth network I/O
```

and accepts no query/body as in Stage 2.

---

# 24. CONTROLLER V2 NON-SECRET FIELD MODEL

For:

```text
controller_url
controller_id
client_id
```

expose safe metadata equivalent to:

```text
setting_key
display_label
value_type

editable = true
read_only_reason = null

persisted_override_value

configured_value
configured_source

effective_value
effective_source

pending_value
pending_source

apply_requirement
activation_target

consumer_state

validation

last_changed_at
last_changed_by
```

Sources:

```text
persisted_override
environment
repository_default
```

`configured_value` is the canonical value resolved from the process-startup base snapshot + current configured head.

`effective_value` is the exact canonical value adopted by the currently running shared Controller runtime.

For a trustworthy effective Controller snapshot:

```text
consumer_state = active
```

If trustworthy effective runtime is unavailable:

```text
consumer_state = null
```

There is no `consumer_disabled` state for these three required Controller definitions.

---

# 25. FIELD-SEMANTIC PENDING STATE

Do not mark a Controller field pending merely because a newer global generation changed only General Settings.

For each Controller field:

```text
pending_value / pending_source are populated only when:

configured_generation != effective_generation
AND
(configured_value, configured_source)
!=
(effective_value, effective_source)
```

Otherwise:

```text
pending_value = null
pending_source = null
```

Top-level generation state may still be:

```text
configured_generation = 10
effective_generation = 9
activation_state = pending_main_restart
restart_required = true
pending_controller_setting_count = 0
```

when only General settings differ.

The UI MUST distinguish:

```text
global Settings restart pending
```

from:

```text
Controller fields actually pending
```

---

# 26. SAFE CONFIGURED-SIDE READ BOUNDARY

Controller Admin code MUST NOT:

```text
open SQLite directly
read raw complete application settings mapping
inspect provider private fields
```

The common Settings control plane must expose a safe Controller-domain configured projection containing only the three admitted non-secret definitions and safe generation/source/override/audit metadata.

Effective side comes only from the immutable safe Controller runtime snapshot.

Logical composition:

```text
configured side
← common Settings read/control-plane boundary

effective side
← OmadaControllerPublicConfigSnapshot
```

No raw `client_secret` may cross into the configured domain projection.

---

# 27. PUBLIC EFFECTIVE CONTROLLER SNAPSHOT EVOLUTION

Evolve the safe Stage-2 `OmadaControllerPublicConfigSnapshot` enough to prove the exact adopted runtime truth.

It must safely carry:

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

startup/effective Settings generation identity when Settings control is active
```

For the three writable fields, effective source MUST come from the exact startup Settings resolution.

It may now be:

```text
persisted_override
environment
repository_default
```

Do NOT infer writable-field source merely from environment membership after Stage 3.

For Settings-disabled deployment-controlled startup, generation may be absent/null and current Stage-2 source semantics remain.

The snapshot remains secret-free and provider-private-field-free.

---

# 28. CLIENT SECRET — PERMANENT STAGE-3 BOUNDARY

`OMADA_CLIENT_SECRET` remains presence-only.

Controller read representation preserves only:

```text
effective_presence = configured | not_configured
effective_source = environment | repository_default
```

No:

```text
raw value
configured raw value
persisted override
pending value
edit control
Replace
Reveal
Copy
Clear
Reset
mask
prefix
suffix
length
hash
fingerprint
```

No new Stage-3 persistence/API/audit/idempotency path may contain raw secret material.

---

# 29. TLS VERIFICATION

`VERIFY_SSL / tls_certificate_verification` remains:

```text
VISIBLE
READ-ONLY
NOT PERSISTED
NOT MUTABLE
```

No TLS override row.

No Stage-3 edit control.

---

# 30. SETTINGSSTORE AVAILABLE READ STATE

With Store available, Controller V2 reports:

```text
store_state = available
configured_generation = G
effective_generation = H
activation_state =
    active
    | pending_main_restart
    | activation_failed
    | runtime_unavailable
restart_required = (G != H)
```

Configured and effective data are both available where trustworthy.

---

# 31. STORE LOST AFTER SUCCESSFUL RUNNING ADOPTION

This is a request-time outage after a process has already successfully adopted a runtime.

The immutable safe effective Controller snapshot remains trustworthy.

Controller GET may return:

```text
HTTP 200
store_state = unavailable

configured_generation = null
configured_value = null
configured_source = null
persisted_override_value = null
pending_value = null
pending_source = null

activation_state = null
restart_required = null

effective_generation = adopted startup generation
effective_value = adopted runtime value
effective_source = adopted runtime source
client_secret effective_presence = allowed
```

It MUST NOT emit cached configured/persisted state as though current.

Controller mutation during Store outage:

```text
503 settings_store_unavailable
```

General Settings behavior remains its existing bounded unavailable behavior.

---

# 32. SETTINGS-ENABLED NEW STARTUP MUST FAIL CLOSED ON STORE FAILURE

This is a deliberate Stage-3 change.

When:

```text
WEB_ADMIN_SETTINGS_ENABLED=true
```

and the SettingsStore cannot be safely:

```text
opened
migrated
read
integrity-validated
```

a new process startup MUST:

```text
FAIL CLOSED
before shared OmadaProvider construction
```

Forbidden:

```text
silent fallback to base/environment Controller values
fabricated generation
automatic DB recreation over an existing broken store
automatic rollback
hidden Controller identity reversion
```

This is mandatory because the unavailable DB may contain authoritative higher-precedence Controller overrides.

When:

```text
WEB_ADMIN_SETTINGS_ENABLED=false
```

preserve explicit deployment-controlled behavior:

```text
NO SettingsStore dependency
base settings
→ OmadaControllerRuntimeConfig
→ shared provider
```

No Settings UI/API mutation in disabled mode.

---

# 33. ACTIVATION / FAILURE SEMANTICS

The shared Controller runtime becomes a required Settings consumer.

A configured generation cannot become effective if its required Controller runtime cannot be validly composed.

If full configured generation validation fails:

```text
do not construct provider
do not serve
do not advance effective generation
```

When positively attributable and Store is writable, durable bounded failure attestation is required using the existing safe validation failure family.

If validation succeeds but required Controller/provider composition fails before adoption:

```text
startup aborts
effective generation does not advance
```

A safe category equivalent to:

```text
controller_configuration_adoption_failed
```

is authorized.

If this new failure category is implemented, the activation service allowlist must be deliberately extended and tested.

No failure record may contain Controller values or secret material.

`activation_failed` remains a positive durable in-process attestation only.

Do NOT infer it from:

```text
service disappearance
timeout
host failure
silence
lack of heartbeat
early process death
```

No external activation reporter.

No automatic rollback.

---

# 34. ADMIN CONTROLLER PROJECTION FAILURE REMAINS NON-CORE

If:

```text
canonical Controller config valid
shared provider constructed successfully
```

but safe Admin Controller projection composition fails:

```text
Portal/Auth/provider may continue
Settings generation may still be adopted
Controller Settings read surface = unavailable
```

Do NOT convert an Admin read-projection defect into required Controller runtime failure.

---

# 35. NO LIVE CONNECTION TEST DURING SAVE OR ADOPTION

Neither mutation nor adoption may perform:

```text
DNS reachability
TLS handshake
OAuth request
token request
/sites request
health probe
credential verification
```

A syntactically valid but operationally wrong Controller URL/client ID may be:

```text
persisted successfully
adopted successfully as runtime configuration
```

and later fail normal operational Omada I/O.

That later external failure is not retroactive Settings `activation_failed`.

---

# 36. R1 STARTUP SEQUENCING — DURABLE ADOPTION BEFORE CONTROLLER I/O

This section is binding and supersedes the current baseline ordering.

Three normative phases:

```text
PHASE A
RESOLVE / VALIDATE / COMPOSE

PHASE B
DURABLE SETTINGS ADOPTION

PHASE C
START RUNTIME I/O / SERVE
```

Order is mandatory.

## Phase A

Allowed:

```text
artifact identity capture
get_settings()
capture explicit environment provenance

open/migrate/validate SettingsStore
read configured generation G
resolve exact immutable snapshot G
validate complete snapshot G

build OmadaControllerRuntimeConfig(G)
construct shared OmadaProvider — MUST remain network-free
build safe Controller public snapshot(G)

construct Flask app
construct runtime/service objects
construct repositories/read services
register routes/blueprints
compose Admin runtime

bounded LOCAL readiness/configuration checks
```

Forbidden before durable adoption of G:

```text
Controller OAuth
token acquisition
Omada HTTP
Controller DNS/TLS probe
background provider call
Controller-dependent periodic loop start
guest authorization reaching Omada
HTTP server accepting product/Admin/guest requests
```

## Phase B

After required local composition/readiness succeeds:

```text
SettingsActivationService.adopt(exact G)
```

must durably commit:

```text
activation_result = adopted
settings_target_state.effective_generation = G
```

Only after that commit is G an effective Controller generation.

## Phase C

Only after successful durable adoption may Controller-dependent workers start and HTTP serving begin.

---

# 37. EXACT CURRENT CONTROLLER-DEPENDENT STARTS TO MOVE POST-ADOPTION

At minimum, current baseline calls:

```text
_pending_session_cleaner.start()
_observation_foundation.start()
_current_state_runtime.start()
_visitor_snapshot_collector.start()
```

MUST execute only after successful durable adoption.

Permanent capability rule:

```text
ANY start/scheduling path capable of:
- invoking shared OmadaProvider
- requesting/refreshing Omada token
- otherwise performing Controller external I/O

MUST be post-adoption.
```

Coder MUST classify every current pre-adoption `.start()` / reconciliation / scheduler call in `run.py`.

A pre-adoption start may remain before adoption only when source/test evidence proves all:

```text
no OmadaProvider access
no Omada/OAuth I/O
does not expose HTTP traffic
does not externally use candidate Controller generation G
```

No unclassified pre-adoption runtime start is permitted.

At minimum explicitly classify:

```text
Visitor Registry start / local processing
Visit Lifecycle reconciliation/scheduling
Analytics/Admin composition
Home AP 24H telemetry start path
Public Traffic worker start path
any other run.py start/scheduler reached before app.run()
```

If a currently pre-adoption component can reach Controller I/O, move it after adoption.

Do not change its internal product semantics beyond ordering required by this gate.

---

# 38. POST-ADOPTION WORKER FAILURE

If a Controller-dependent worker fails to start after G was durably adopted:

```text
G remains effective
no effective-generation rollback
no automatic activation_failed rewrite
no automatic Settings generation rollback
```

The worker keeps its existing operational degraded/fail-open/unavailable semantics.

Settings adoption proves local configuration/runtime acceptance, not permanent worker health.

---

# 39. HTTP SERVING

`app.run(...)` / product request serving MUST occur only after successful durable adoption when Settings control is enabled and available.

If `adopt(G)` fails:

```text
NO Controller-dependent worker start
NO HTTP serving
NO Controller/OAuth external I/O using candidate G
startup aborts
```

For Settings disabled, preserve current deployment-controlled startup behavior; no Settings adoption service exists.

---

# 40. CONTROLLER PAGE UX

Existing information architecture stays:

```text
Settings
├── General
└── Controller
```

Route remains:

```text
GET /admin/settings/controller
```

Editable controls:

```text
Controller URL
Controller ID
Client / Application ID
```

Read-only:

```text
Client Secret
TLS certificate verification
```

For each editable field, present:

```text
Configured value
Configured source

Effective value
Effective source

Persisted override state/value

Pending value/source when field-semantic pending exists
```

Technical key may be secondary text.

Source labels must be server-derived.

Do not infer source in JS.

---

# 41. CLEAR OVERRIDE UX

Provide explicit per-field action equivalent to:

```text
Clear override / use deployment value
```

Do not ambiguously present "Reset" as "restore hardcoded default".

The operator must understand that clear means:

```text
remove SettingsStore ownership
→ fall through to lower-precedence environment/default
```

If lower source would be invalid, server rejects and UI keeps authoritative current state.

---

# 42. SAVE UX / EXPLICIT CONFIRMATION

Controller Save is one atomic batch containing any subset of the three admitted keys.

Before POST, after the proposed diff is assembled, require explicit operator confirmation.

Confirmation must identify changed keys and communicate:

```text
configuration will be persisted
no connection test will be performed
current running Controller configuration remains unchanged until restart/adoption
```

No secret appears in the confirmation.

Changed success wording must communicate equivalently:

```text
Persisted successfully.
Pending captive-portal.service restart.
Current runtime still uses the effective configuration shown.
```

Do NOT claim:

```text
Connected
Verified
Working
Authenticated
Online
Healthy
```

No restart button.

No systemd action.

---

# 43. STALE UI BEHAVIOR

On:

```text
412 stale_generation
```

Controller UI MUST:

```text
re-GET current Controller model
show stale/conflict state
require operator review
use a NEW Idempotency-Key for any resubmission
```

No automatic resubmit.

---

# 44. CLIENT-SIDE SECURITY / IMPLEMENTATION RULES

Keep Controller JS dedicated:

```text
app/admin_web/static/controller_settings.js
```

Do not move mutation logic into `admin.js` or General `settings.js`.

Required:

```text
same-origin credentials
no-store GET
DOM construction with textContent / safe properties
no innerHTML for server-provided values
no localStorage
no sessionStorage
no console logging of Controller values
no secret bootstrap
```

Do not serialize raw Controller configuration into HTML attributes.

CSRF token may continue to be provided through the existing safe page mechanism for mutation.

Write controls must not render/activate without `admin.write.settings.controller`.

---

# 45. CONTROLLER PAGE STATE WHEN STORE IS UNAVAILABLE

If effective snapshot exists but Store is unavailable at request time:

```text
show effective Controller configuration
show configured/persisted state unavailable
disable/hide mutation affordances
do not display stale cached configured values as current
```

Mutation is unavailable.

If safe effective snapshot itself is unavailable:

```text
Controller configuration is unavailable.
```

preserve sanitized read failure behavior.

---

# 46. LOGGING / AUDIT

For every changed Controller override, protected durable Settings audit must preserve equivalent data:

```text
generation_id
parent_generation_id

setting_domain = controller
setting_key
value_type = string

principal_type
principal_name
source_ip
request_id
idempotency_key
timestamp_utc

operation
previous persisted override
new persisted override

previous configured value
new configured value

apply_requirement = main_service_restart
activation_target = captive-portal.service
```

The three admitted Controller values are non-secret and may exist in protected Settings audit.

Routine application logs SHOULD contain:

```text
request_id
generation
changed key names
result category
```

Routine logs SHOULD NOT dump Controller scalar values.

Never log:

```text
OMADA_CLIENT_SECRET
Authorization header
access token
whole settings mapping
whole mutation body
secret-bearing config repr
```

---

# 47. SECRET-SAFETY NEGATIVE REQUIREMENT

The raw production/test sentinel for `OMADA_CLIENT_SECRET` must be absent from every newly introduced:

```text
API success body
API error body
HTML
JavaScript
Settings override row
mutation audit
idempotency payload identity
idempotency response receipt
activation event
routine log
exception serialization
Controller V2 configured projection
```

Presence-only semantics are the only permitted Admin representation.

Tests MUST use a unique sentinel and assert non-disclosure across these boundaries.

---

# 48. EXPECTED PRODUCTION CODE SURFACE

Coder is authorized to modify the following production areas as required by this TASK:

```text
run.py

app/settings_control/definitions.py
app/settings_control/models.py
app/settings_control/resolver.py
app/settings_control/repository.py
app/settings_control/validation.py
app/settings_control/services.py
app/settings_control/bootstrap.py
app/settings_control/activation.py
app/settings_control/__init__.py                 [only if exports require it]

app/controllers/omada_config.py

app/admin_web/controller_settings.py
app/admin_web/policy.py
app/admin_web/runtime.py
app/admin_web/routes.py
app/admin_web/__init__.py                       [only if composition/export requires it]

app/admin_web/templates/admin/base.html         [bounded capability/page data only]
app/admin_web/templates/admin/settings_controller.html
app/admin_web/static/controller_settings.js
app/admin_web/static/admin.css                  [Controller Settings UX only]

docs/configuration.md
docs/modules/admin-web.md
```

Tests/fixtures may be added/modified under:

```text
tests/settings_control/
tests/admin_web/
tests/test_admin_controller_settings.py
tests/test_omada_configuration.py
tests/test_proxy_headers.py
tests/test_auth_retry.py
tests/test_portal_counter.py
tests/test_auth_telemetry.py
tests/test_public_traffic.py
tests/integrations/omada/
tests/visitor_registry/
tests/observations/
tests/current_state/
tests/pending_sessions/
```

Other test-only files may be touched if needed to exercise the authorized behavior.

## Scope blocker rule

If implementation truly requires a **production** file outside the authorized production surface:

```text
STOP before editing that file
return exact file + reason + minimal required change to Tech Lead
```

Do not silently widen scope.

---

# 49. PRODUCTION AREAS FROZEN AGAINST SEMANTIC CHANGE

Except for the explicit startup ordering needed by R1, do NOT change behavior of:

```text
guest portal flow
CAPPORT contract
authentication policy
Omada operational API methods
pending-session cleaner business rules
observation business logic
current-state business logic
visitor lifecycle semantics
traffic semantics
analytics semantics
device fingerprint semantics
webhook semantics
site mapping
proxy/security headers
login/logout semantics
```

Do not use Stage 3 as cleanup/refactor scope.

---

# 50. REQUIRED DATABASE TEST MATRIX

Add tests proving at minimum:

```text
DB-01 new DB is created as schema v2
DB-02 generation 0 remains canonical and empty
DB-03 integer override persists/reads unchanged
DB-04 string override persists/reads canonical value
DB-05 integer + string overrides coexist in one generation
DB-06 unknown value_type rejected
DB-07 malformed typed row fails Store integrity/open
DB-08 secret key cannot be persisted as Stage-3 override

DB-09 exact schema-v1 fixture migrates to v2 transactionally
DB-10 generation IDs preserved
DB-11 parent relationships preserved
DB-12 configured head preserved
DB-13 effective_generation preserved
DB-14 activation events preserved
DB-15 General override values preserved
DB-16 General mutation audit chronology/values preserved
DB-17 General successful idempotency rows preserved
DB-18 migrated idempotency domain = general
DB-19 migrated audit domain/type = general/integer if materialized
DB-20 migration creates no generation
DB-21 migration creates no mutation audit
DB-22 migration creates no activation event
DB-23 v1 migration failure rolls back / fails Store closed
DB-24 v2 DDL/integrity checks reject unexpected schema
```

The v1 fixture must be built from the actual accepted Stage-1 schema contract, not a hand-waved approximate table.

---

# 51. REQUIRED REGISTRY / RESOLVER TEST MATRIX

```text
REG-01 total registry definitions = 15
REG-02 General definitions = exactly original 12
REG-03 Controller definitions = exactly 3
REG-04 no editable OMADA_CLIENT_SECRET
REG-05 no editable VERIFY_SSL
REG-06 OMADA_CLIENT_ID maps explicitly to client_id
REG-07 all Controller definitions GLOBAL
REG-08 all require captive-portal.service restart
REG-09 existing General metadata/bounds remain unchanged

RES-01 persisted Controller override beats environment
RES-02 environment beats repository default
RES-03 explicit environment source comes from membership, not scalar inference
RES-04 persisted_override source is explicit
RES-05 selected valid override can mask invalid lower Controller base
RES-06 clearing override exposes valid lower source
RES-07 clearing override exposing invalid lower source fails
RES-08 canonical Controller URL is persisted
RES-09 canonical trimmed IDs are persisted
RES-10 General integer resolution behavior remains unchanged
```

---

# 52. REQUIRED VALIDATION TEST MATRIX

```text
VAL-01 OMADA_URL trims and removes one root trailing slash
VAL-02 http accepted
VAL-03 https accepted
VAL-04 hostname required
VAL-05 valid explicit port accepted
VAL-06 port 0 rejected
VAL-07 malformed port rejected
VAL-08 userinfo rejected
VAL-09 query rejected
VAL-10 fragment rejected
VAL-11 non-root path rejected
VAL-12 whitespace rejected
VAL-13 empty URL rejected

VAL-14 OMADA_ID trims
VAL-15 empty OMADA_ID rejected
VAL-16 OMADA_CLIENT_ID trims
VAL-17 empty OMADA_CLIENT_ID rejected
VAL-18 no new charset/case/semantic length policy

VAL-19 full Controller candidate is validated for one-field mutation
VAL-20 multi-field candidate is all-or-nothing
VAL-21 Controller mutation validation causes zero network I/O
VAL-22 General mutation still validates complete generation
VAL-23 Settings/runtime validation share the same Omada semantic boundary
VAL-24 prerequisite-secret failure is safe and non-disclosing
```

---

# 53. REQUIRED MUTATION SERVICE / ROUTE TEST MATRIX

```text
MUT-01 Controller POST exact route exists
MUT-02 read and write capabilities are distinct
MUT-03 admin.write.settings.global cannot mutate Controller
MUT-04 admin.write.settings.controller cannot mutate General
MUT-05 no Site resolver used

MUT-06 strict JSON body
MUT-07 max body 32768
MUT-08 max changes 3
MUT-09 set requires string
MUT-10 clear_override forbids value
MUT-11 duplicate JSON members rejected
MUT-12 duplicate setting keys rejected
MUT-13 unknown member rejected
MUT-14 query rejected
MUT-15 scope/site fields rejected
MUT-16 secret/TLS keys rejected
MUT-17 General key rejected by Controller route
MUT-18 Controller key rejected by General route

MUT-19 missing CSRF / invalid CSRF rejected
MUT-20 missing If-Match => 428
MUT-21 malformed If-Match => 400
MUT-22 stale If-Match => 412
MUT-23 malformed Idempotency-Key rejected
MUT-24 same idempotency/payload replays exact receipt
MUT-25 replay does not allocate generation/audit
MUT-26 same idempotency/different payload => 409
MUT-27 General and Controller idempotency domains are isolated

MUT-28 canonical-equal existing override => changed=false / no generation
MUT-29 no override + same scalar explicit set => changed=true / generation
MUT-30 clear valid fallback => changed=true
MUT-31 clear invalid fallback => 422 / atomic no-change
MUT-32 multi-field partial invalidity => no partial commit

MUT-33 changed receipt api_version = admin.settings.controller.mutation.v1
MUT-34 changed receipt = 201
MUT-35 no-op receipt = 200
MUT-36 receipt contains no Controller scalar values
MUT-37 changed_keys only contains exact Controller allowlist keys
MUT-38 success ETag = common configured generation
MUT-39 serialized receipt remains <= 65536
MUT-40 replay-receipt persistence failure rolls back entire transaction
MUT-41 successful mutation always has durable replay row
```

---

# 54. REQUIRED CONTROLLER READ V2 TEST MATRIX

```text
READ-01 path remains /admin/api/v1/settings/controller
READ-02 api_version = admin.settings.controller.v2
READ-03 scope global
READ-04 resource = omada_controller / installation
READ-05 management_mode = hybrid

READ-06 Controller GET has zero Omada/OAuth I/O
READ-07 provider private fields are not read-model source
READ-08 configured projection does not receive full secret-bearing settings mapping

READ-09 configured source/value from common Settings boundary
READ-10 effective source/value from exact safe startup snapshot
READ-11 effective source can be persisted_override
READ-12 effective snapshot has startup generation identity

READ-13 pending field populated only for actual Controller field diff
READ-14 unrelated General pending generation does not fabricate Controller field pending
READ-15 top-level global pending state may exist with pending_controller_setting_count=0

READ-16 Client Secret presence-only
READ-17 Client Secret has no configured/pending/raw value
READ-18 TLS remains read-only
READ-19 no secret length/prefix/suffix/hash/fingerprint

READ-20 Store available returns common ETag
READ-21 Store lost after adoption still returns effective-only 200 when safe snapshot exists
READ-22 Store-outage response nulls configured/persisted/pending fields
READ-23 Store-outage response does not reuse cached configured state
READ-24 mutation unavailable during Store outage
READ-25 no safe effective snapshot => sanitized read unavailable
```

---

# 55. REQUIRED UI TEST MATRIX

```text
UI-01 Controller page remains separate Settings sub-page
UI-02 read capability controls visibility/page access
UI-03 write capability controls edit controls
UI-04 direct POST auth independent of UI

UI-05 exactly Controller URL, Controller ID, Client/Application ID editable
UI-06 Client Secret read-only presence only
UI-07 TLS read-only
UI-08 configured/effective/source/override/pending state rendered safely
UI-09 source not inferred by JS
UI-10 no Site context

UI-11 Clear override semantics are explicit
UI-12 Save batches selected changes atomically
UI-13 confirmation required before POST
UI-14 confirmation lists changed keys only / no secret
UI-15 confirmation says no connection test and restart needed
UI-16 changed success says persisted + pending restart, not connected
UI-17 no restart/systemd/Test Connection controls

UI-18 every successful 200/201 POST triggers authoritative GET
UI-19 idempotent replay also triggers GET
UI-20 412 triggers reload + conflict state + no auto-resubmit
UI-21 next resubmit uses new Idempotency-Key

UI-22 Store unavailable shows effective state but disables mutation
UI-23 unavailable configured state is not shown from stale cache

UI-24 no innerHTML for server values
UI-25 no localStorage/sessionStorage
UI-26 no console Controller-value logging
UI-27 dedicated controller_settings.js remains
```

Static JS assertions are acceptable only as supplements; behavior must also be exercised where practical.

---

# 56. REQUIRED STARTUP / ADOPTION TEST MATRIX

Tests must explicitly instrument event order and fail if candidate generation performs Controller I/O before adoption.

```text
START-01 Settings disabled opens no SettingsStore
START-02 Settings disabled keeps deployment-controlled Controller startup

START-03 Settings enabled + valid Store resolves exact head G
START-04 Settings enabled + Store open failure fails closed
START-05 Settings enabled + migration failure fails closed
START-06 Settings enabled + integrity failure fails closed
START-07 fail-closed occurs before create_controller/provider construction

START-08 exact snapshot G builds OmadaControllerRuntimeConfig(G)
START-09 exact same typed config feeds shared provider
START-10 provider construction itself performs zero network I/O
START-11 public effective snapshot corresponds to exact G

START-12 pending_session_cleaner.start occurs after durable adoption
START-13 observation_foundation.start occurs after durable adoption
START-14 current_state_runtime.start occurs after durable adoption
START-15 visitor_snapshot_collector.start occurs after durable adoption

START-16 every other pre-adoption start/scheduler is explicitly classified
START-17 no classified Controller-capable start occurs pre-adoption
START-18 no Omada/OAuth I/O occurs pre-adoption
START-19 app.run / HTTP serving occurs after durable adoption

START-20 adoption durable-write failure starts no Controller-dependent worker
START-21 adoption failure performs zero candidate-G Controller external I/O
START-22 adoption failure does not advance effective generation

START-23 post-adoption Controller-worker start failure does not roll back effective generation
START-24 no automatic activation_failed rewrite for post-adoption operational worker failure
START-25 no Test Connection/OAuth health probe added to adoption

START-26 Admin Controller public projection failure remains non-core
START-27 valid provider + projection failure may still durably adopt
```

The existing `tests/settings_control/test_run_integration.py` must be strengthened accordingly; do not rely only on unit tests of isolated services.

---

# 57. REQUIRED SECRET NON-DISCLOSURE TEST MATRIX

Use a unique sentinel string and assert it is absent from:

```text
SEC-01 Controller GET response
SEC-02 Controller POST receipt
SEC-03 validation error response
SEC-04 generic/internal error response
SEC-05 HTML
SEC-06 JavaScript/bootstrap data
SEC-07 Settings overrides table
SEC-08 mutation audit
SEC-09 idempotency request/result persistence
SEC-10 activation events
SEC-11 ordinary logs/caplog
SEC-12 repr/str of public objects
```

Existing `OmadaControllerRuntimeConfig.client_secret` repr safety must remain.

---

# 58. REQUIRED GENERAL / STAGE-1 REGRESSION

Explicitly prove:

```text
GEN-01 General GET returns exactly 12
GEN-02 General API version remains admin.settings.v1
GEN-03 General groups/order/validation remain expected
GEN-04 existing General mutation semantics remain
GEN-05 existing General CSRF/CAS/idempotency semantics remain
GEN-06 General integer history survives migration
GEN-07 General UI does not render Controller settings
GEN-08 existing General write capability remains unchanged
GEN-09 existing Settings-disabled behavior remains
GEN-10 existing Settings feature gate remains one product-area gate
```

---

# 59. REQUIRED STAGE-2 REGRESSION

Prove:

```text
S2-01 one injected OmadaControllerRuntimeConfig remains
S2-02 no zero-argument production create_controller call returns
S2-03 provider does not independently call get_settings
S2-04 Controller GET performs zero external I/O
S2-05 effective field meanings remain Stage-2 compatible
S2-06 secret remains presence-only
S2-07 TLS remains visible
S2-08 Controller page remains GLOBAL
S2-09 no Site resolver dependency
S2-10 Admin projection failure remains isolated
```

---

# 60. REQUIRED BROADER REGRESSION AREAS

Because this TASK changes the common Settings schema/bootstrap and `run.py` sequencing, rerun impacted product integration coverage for at least:

```text
Portal/Auth
proxy/security headers
auth retry
auth telemetry
portal counter
public traffic

Omada webhook/site mapping
visitor registry/snapshot runtime
visit lifecycle
observations
current state
pending session cleaner

Admin Web
Settings General
Controller Settings
```

No test may require a live Omada Controller.

---

# 61. REQUIRED DOCUMENTATION UPDATE

Update operator/developer docs to reflect:

```text
Controller Settings Stage 3 is writable only for:
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID

OMADA_CLIENT_SECRET remains read-presence-only
VERIFY_SSL remains read-only

precedence =
persisted override > startup environment > repository default

save persists configuration but does not activate running Controller config
activation requires externally performed captive-portal.service restart

no Admin restart control
no Test Connection
no live health claim

schema v2 migration occurs automatically on Settings-enabled startup
Settings-enabled new startup fails closed if SettingsStore cannot be safely used
```

Do not document future Secret Storage as implemented.

---

# 62. STATIC / QUALITY GATES

Must pass:

```text
python -m compileall -q app run.py
node --check app/admin_web/static/controller_settings.js
git diff --check
```

No new lint/type tool requirement is introduced if repository does not already use one.

---

# 63. REQUIRED TEST EXECUTION

Coder must run and report exact counts for:

## 63.1 Stage-3 focused suite

All newly added/modified Settings Stage-3 tests, including:

```text
tests/settings_control/
tests/test_admin_controller_settings.py
tests/admin_web/test_settings_routes.py
```

plus any new Controller Stage-3 test module(s).

## 63.2 Affected runtime regression

Run relevant tests under:

```text
tests/visitor_registry/
tests/observations/
tests/current_state/
tests/pending_sessions/
```

and the existing Omada/Admin/Portal regression files affected by Stage 2.

## 63.3 Full repository suite

Run:

```text
python -m pytest -q
```

If there is any unrelated pre-existing failure, return:

```text
exact test
exact failure
proof it exists on untouched baseline
```

Do not silently waive it.

---

# 64. MANUAL SOURCE REVIEW CHECKS BEFORE HANDOFF

Coder must inspect the final diff and explicitly confirm:

```text
no raw secret added to any API/model/UI/audit path

no OMADA_CLIENT_SECRET SettingsDefinition

no VERIFY_SSL writable definition

no Controller-specific DB/store/generation/CAS engine

no systemd/subprocess/sudo implementation

no restart button

no live Controller probe

no request-time env/systemd reread

General GET remains domain-filtered to 12

Controller write route uses admin.write.settings.controller

new Controller JSON POST is narrowly carved out of Admin form-only boundary

R1 bounded mutation receipt is used, not old full-V2 mutation response

Controller-dependent workers are post-adoption

HTTP serve is post-adoption

projection failure remains non-core
```

Search for accidental secret references and unsafe logging before handoff.

---

# 65. EXPECTED BRANCH / LOCAL COMMIT

Use branch:

```text
feature/admin-settings-03-controller-writable-nonsecret
```

Implementation may end in one local review commit with subject:

```text
ADMIN-SETTINGS-03: add writable non-secret Omada Controller settings
```

Do NOT push it.

If multiple local implementation commits are used during development, squash locally to one review candidate before handoff unless preserving multiple commits is necessary for evidence. Do not rewrite accepted baseline.

---

# 66. REQUIRED CODER HANDOFF

Return exactly enough identity/evidence for independent Tech Lead reconstruction/review:

```text
TASK=TASK-ADMIN-SETTINGS-03

BASE_HEAD=
BASE_TREE=

BRANCH=
CANDIDATE_COMMIT=
CANDIDATE_PARENT=
CANDIDATE_TREE=

GIT_STATUS_PORCELAIN=
WORKTREE_STATE=

CHANGED_FILES_COUNT=
CHANGED_FILES_LIST=

FULL_BASE_TO_CANDIDATE_PATCH_PATH=
FULL_PATCH_BYTES=
FULL_PATCH_SHA256=

SCHEMA_VERSION=
SCHEMA_MIGRATION_TEST_COUNT/PASS=

FOCUSED_TESTS=
AFFECTED_RUNTIME_TESTS=
FULL_PYTEST=
COMPILEALL=
NODE_CHECK=
GIT_DIFF_CHECK=

OPEN_P0=
OPEN_P1=

PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```

The patch MUST be the complete:

```text
BASE c116718... → candidate tree
```

patch, not only the final local commit delta if those differ.

Also return a concise source note covering:

```text
1. exact v1→v2 migration strategy
2. exact Controller domain mutation path
3. exact safe configured read boundary
4. exact effective snapshot provenance/generation change
5. exact run.py pre/post-adoption start classification
6. proof that Client Secret remains outside all new Stage-3 persistence paths
```

---

# 67. STOP / RETURN CONDITIONS

Coder MUST stop and return a blocker rather than invent architecture if any of these occur:

```text
baseline differs from c116718...

schema v1 production shape differs from source-verified baseline

migration cannot preserve immutable history transactionally

implementation appears to require a second persistence owner

Controller mutation requires secret persistence

canonical Omada validator cannot be reused without semantic change

a pre-adoption runtime start cannot be classified as Controller-I/O safe/unsafe

a required production file outside authorized scope is necessary

architecture contains an implementation-significant contradiction not resolved by R1 precedence
```

No architectural improvisation.

---

# 68. TECH LEAD ACCEPTANCE CRITERIA

Tech Lead source review will independently verify:

```text
artifact identity
complete diff identity
schema migration correctness
typed Store integrity
General backward compatibility
Controller write authorization
mutation atomicity/CAS/idempotency
bounded R1 receipt
Controller V2 read truth
secret boundary
zero request-time Omada I/O
startup fail-closed behavior
durable adoption ordering
post-adoption worker start ordering
Portal/Auth regressions
UI semantics
docs
test evidence
```

Any P0/P1 keeps publication on HOLD.

No push/PR authorization is implied by implementation completion.

---

# 69. FINAL IMPLEMENTATION GATE

```text
TASK ID =
TASK-ADMIN-SETTINGS-03

TASK NAME =
OMADA CONTROLLER WRITABLE NON-SECRET CONFIGURATION

ARCHITECTURE =
FINAL / TECH LEAD ACCEPTED

IMPLEMENTATION CONTRACT =
FINAL / BINDING

BASELINE =
main@c1167180daec9ca17d13ab44326f143122db8d5e

TREE =
278df41bfa3134b22963b41006585da35de08074

ADMITTED WRITABLE KEYS =
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID

OMADA_CLIENT_SECRET =
OUT OF SCOPE / NOT WRITABLE

VERIFY_SSL =
READ-ONLY

SETTINGSSTORE =
ONE COMMON STORE

SCHEMA =
v1 → v2

MUTATION =
POST /admin/api/v1/settings/controller/generations

MUTATION RECEIPT =
admin.settings.controller.mutation.v1
BOUNDED
NO CONTROLLER SCALAR VALUES

READ =
GET /admin/api/v1/settings/controller
admin.settings.controller.v2

WRITE CAPABILITY =
admin.write.settings.controller

ACTIVATION TARGET =
captive-portal.service

PRE-ADOPTION CONTROLLER/OAUTH I/O =
FORBIDDEN

HOT RECONNECT =
NO

ADMIN SYSTEMD AUTHORITY =
NO

CONNECTION TEST =
NO

RAW SECRET DISCLOSURE =
FORBIDDEN

CODER =
GO

PUSH =
HOLD

PR =
HOLD

MERGE =
NO

DEPLOY =
NO

PRODUCTION CHANGE =
NO
```
