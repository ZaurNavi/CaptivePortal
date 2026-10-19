# TASK-ADMIN-SETTINGS-01 — SETTINGS FOUNDATION + SAFE ADMIN SETTINGS V1
## R1 FINAL CANDIDATE FOR TECH LEAD REVIEW

**Project:** CaptivPortal  
**Area:** Admin UI → Settings  
**Role owner:** Technical Developer Settings  
**Task type:** Exact implementation contract for Coder  
**Status:** R1 FINAL CANDIDATE FOR TECH LEAD REVIEW  
**Coder:** HOLD  
**Implementation:** NOT AUTHORIZED  
**Production:** NO CHANGE  
**Systemd:** NO ACTION  

**Authoritative implementation baseline:**

```text
main@9af1cb158bfcfcb31d441caf71061c9aa2888b85
TREE=4850e322a4286880a32dbd995121a85bc85c9e99
```

If `main` advances before Coder starts:

```text
STOP
→ Tech Lead baseline reconciliation
```

Coder MUST NOT silently implement from an older base.

---

# 0. AUTHORITATIVE INPUTS

This TASK implements without architectural reinterpretation:

1. `CAPTIVPORTAL ADMIN SETTINGS — ARCHITECTURE CONTRACT v0.1`
2. `CAPTIVPORTAL ADMIN SETTINGS — ARCHITECTURE DISPOSITION A1–A4`
3. `CAPTIVPORTAL ADMIN SETTINGS — PRELIMINARY ROADMAP v0.2`
4. Tech Lead implementation-contract review `TL-AS-R1..TL-AS-R17`

Architecture status:

```text
FINAL / ACCEPTED
```

Roadmap status:

```text
PASS / NO SEMANTIC REVISION REQUIRED
```

Open architecture P0:

```text
0
```

Architect return:

```text
NOT REQUIRED
```

This R1 incorporates TL-AS-R1..TL-AS-R17. It does NOT authorize Coder until Tech Lead gives final implementation-contract PASS.

---

# 1. OBJECTIVE

Implement the first writable CaptivPortal Admin Settings control plane and expose exactly the approved 12 GLOBAL, non-secret, non-self-lockout Admin presentation/refresh settings.

Required configuration chain:

```text
repository defaults
+
process environment
        ↓
base settings snapshot
+
durable SettingsStore configured generation
        ↓
one immutable ResolvedSettingsSnapshot(G)
        ↓
primitive + existing semantic validation
        ↓
runtime composition from that exact snapshot
        ↓
durable runtime adoption of exact generation G
        ↓
effective_generation = G
```

Required mutation chain:

```text
Admin Settings UI
        ↓
authenticated GLOBAL JSON mutation
        ↓
CSRF + strict JSON + idempotency + If-Match
        ↓
atomic full-candidate validation
        ↓
single SQLite write transaction
        ↓
immutable configured generation
+
audit
+
idempotency success result
        ↓
pending_main_restart
```

Admin Web MUST NOT restart/reload `captive-portal.service`.

---

# 2. BASELINE / WORKFLOW GATE

Before any source modification Coder must verify:

```bash
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

Required:

```text
HEAD=9af1cb158bfcfcb31d441caf71061c9aa2888b85
TREE=4850e322a4286880a32dbd995121a85bc85c9e99
```

If either differs:

```text
STOP
no implementation
return exact observed HEAD/TREE
```

Coder implementation round MUST use an isolated worktree from this exact accepted baseline.

First handoff rules:

```text
COMMIT = NO
PUSH = NO
PR = NO
MERGE = NO
DEPLOY = NO
SERVICE RESTART = NO
PRODUCTION TEST = NO
```

Repository history may be created only after Tech Lead source/diff review.

---

# 3. EXACT WRITABLE ALLOWLIST

Only these 12 keys are UI-editable in Stage 1.

Any key absent from this matrix is denied by default.

| Canonical key | settings dict key | Environment variable | Repository default | Bounds | Semantic validator | Consumer-enable source |
|---|---|---|---:|---:|---|---|
| `WEB_ADMIN_DEVICE_PAGE_SIZE` | `web_admin_device_page_size` | `WEB_ADMIN_DEVICE_PAGE_SIZE` | 100 | 1..500 | `admin_web_config_from_settings` | `WEB_ADMIN_ENABLED` |
| `WEB_ADMIN_VISIT_PAGE_SIZE` | `web_admin_visit_page_size` | `WEB_ADMIN_VISIT_PAGE_SIZE` | 100 | 1..500 | `admin_web_config_from_settings` | `WEB_ADMIN_ENABLED` |
| `WEB_ADMIN_OBSERVATION_PAGE_SIZE` | `web_admin_observation_page_size` | `WEB_ADMIN_OBSERVATION_PAGE_SIZE` | 100 | 1..500 | `admin_web_config_from_settings` | `WEB_ADMIN_ENABLED` |
| `WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS` | `web_admin_observation_max_window_hours` | `WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS` | 24 | 1..168 | `admin_web_config_from_settings` | `WEB_ADMIN_ENABLED` |
| `WEB_ADMIN_CURRENT_STATE_PAGE_SIZE` | `web_admin_current_state_page_size` | `WEB_ADMIN_CURRENT_STATE_PAGE_SIZE` | 100 | 1..250 | `admin_web_config_from_settings` | `WEB_ADMIN_HOME_LIVE_ENABLED` |
| `WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE` | `web_admin_home_traffic_page_size` | `WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE` | 100 | 1..250 | `admin_web_config_from_settings` | `WEB_ADMIN_HOME_TRAFFIC_ENABLED` |
| `WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS` | `web_admin_home_live_refresh_seconds` | `WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS` | 60 | 60..300 | `admin_web_config_from_settings` | `WEB_ADMIN_HOME_LIVE_ENABLED` |
| `WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS` | `web_admin_home_traffic_refresh_seconds` | `WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS` | 60 | 60..300 | `admin_web_config_from_settings` | `WEB_ADMIN_HOME_TRAFFIC_ENABLED` |
| `WEB_ADMIN_TRAFFIC_REFRESH_SECONDS` | `web_admin_traffic_refresh_seconds` | `WEB_ADMIN_TRAFFIC_REFRESH_SECONDS` | 60 | 60..300 | `admin_web_config_from_settings` | `WEB_ADMIN_TRAFFIC_ENABLED` |
| `WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS` | `web_admin_home_activity_refresh_seconds` | `WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS` | 60 | 60..300 | `home_activity_config_from_settings` | `WEB_ADMIN_HOME_ACTIVITY_ENABLED` |
| `WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS` | `web_admin_home_health_refresh_seconds` | `WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS` | 60 | 60..300 | `home_health_config_from_settings` | `WEB_ADMIN_HOME_HEALTH_ENABLED` |
| `WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS` | `web_admin_home_ap_24h_refresh_seconds` | `WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS` | 120 | 60..600 | `home_ap_24h_config_from_settings` | `WEB_ADMIN_HOME_AP_24H_ENABLED` |

For every Stage-1 definition:

```text
value_type = integer
scope_type = global
scope_id = null
secret_class = normal
editable = true
apply_requirement = main_service_restart
activation_target = captive-portal.service
```

No other current configuration key becomes writable.

---

# 4. ONE SOURCE OF TRUTH FOR DEFAULT METADATA

The SettingsDefinitionRegistry MUST own, for each definition:

```text
key
settings_dict_key
environment_variable_name
repository_default_value
display_label
description
group
value_type
scope_type
secret_class
editable
min_value
max_value
apply_requirement
activation_target
semantic_validator
consumer_enable_settings_dict_key
```

The registry MUST NOT infer environment origin from an already-resolved scalar.

Prevent drift between repository defaults and registry metadata as follows:

1. In `app/config.py`, introduce typed canonical Stage-1 repository-default constants for the 12 values.
2. Existing `os.getenv()` defaults for these 12 settings MUST derive from those canonical constants rather than repeat independent literals.
3. `SettingsDefinitionRegistry` MUST use those same canonical constants as `repository_default_value`.
4. Do NOT create a second frontend/default table.
5. Focused tests must assert all 12 registry defaults equal canonical repository defaults.

This is the only Stage-1 default-deduplication authorized.

---

# 5. DEPLOYMENT-CONTROLLED BOOTSTRAP SETTINGS

Add:

```text
WEB_ADMIN_SETTINGS_ENABLED
SETTINGS_DB_PATH
```

Canonical defaults:

```text
WEB_ADMIN_SETTINGS_ENABLED = false
SETTINGS_DB_PATH = /opt/CaptivePortal/data/settings.sqlite3
```

Expose them in the normal base settings dictionary as:

```text
web_admin_settings_enabled
settings_db_path
```

They are deployment/bootstrap controls only.

They are NOT:

- persisted Settings overrides;
- entries in the 12-key registry;
- writable through Admin Settings;
- Site-scoped;
- secret settings.

`WEB_ADMIN_SETTINGS_ENABLED=false` must have zero SettingsStore side effects:

```text
SettingsStore not opened
settings.sqlite3 not created
persisted generations not read
normal repository/environment base settings remain authoritative
legacy non-Settings runtime behavior unchanged
Settings nav absent
Settings page/API surface disabled
```

---

# 6. SETTINGS DOMAIN PACKAGE

Create exactly:

```text
app/settings_control/
```

New files:

```text
app/settings_control/__init__.py
app/settings_control/definitions.py
app/settings_control/models.py
app/settings_control/repository.py
app/settings_control/resolver.py
app/settings_control/validation.py
app/settings_control/services.py
app/settings_control/activation.py
app/settings_control/bootstrap.py
```

`app/settings_control/__init__.py` MUST remain lightweight and MUST NOT create an import cycle with `app/config.py` / `app/settings.py`.

## 6.1 `definitions.py`

Own:

```text
SettingsDefinition
SettingsDefinitionRegistry
```

and exactly the 12-key matrix from Section 3.

Unknown key:

```text
not registered
→ not writable
```

## 6.2 `models.py`

Own immutable typed models/enums/constants required by Stage 1, at minimum:

```text
ResolvedSettingsSnapshot
SettingReadModelV1
SettingsReadModelV1
SettingsMutationChange
SettingsMutationResult
SettingsActivationEvent
SettingsAdminContext
SettingsBootstrapResult
ActivationState
ConsumerState
StoreState
```

`ResolvedSettingsSnapshot` must contain at minimum:

```text
generation_id: int | None
values: immutable Mapping[str, Any]
base_source_by_key: immutable Mapping[str, str]
base_value_by_key: immutable Mapping[str, int]
persisted_override_by_key: immutable Mapping[str, int | None]
```

For Settings-disabled or store-unavailable fallback runtime:

```text
generation_id = null
values = immutable base settings
```

but this MUST NOT be represented as an adopted Settings generation.

## 6.3 `repository.py`

Own all SQLite access:

- schema bootstrap/validation;
- configured head;
- override generations;
- target effective generation;
- activation events;
- audit;
- idempotency;
- atomic mutation transaction.

No Admin route/template/JS directly accesses SQLite.

## 6.4 `resolver.py`

Own one canonical resolver for registered Stage-1 values.

Inputs:

```text
base settings
explicit environment-variable presence snapshot
registry
persisted override state
generation_id
```

Output:

```text
ResolvedSettingsSnapshot
```

Resolution:

```text
persisted GLOBAL override
>
explicit process environment
>
repository default
```

## 6.5 `validation.py`

Own:

```text
SettingsValidationService
```

It must:

- primitive-validate all registered candidate values;
- construct the complete candidate settings mapping;
- invoke existing semantic validators;
- preserve cross-setting validation;
- return one all-or-nothing validation result.

## 6.6 `services.py`

Own:

```text
SettingsReadService
SettingsMutationService
```

Admin HTTP calls services only.

## 6.7 `activation.py`

Own:

```text
SettingsActivationService
```

Only the main runtime lifecycle may use it to advance target effective generation or record attributable Settings activation failure.

Admin HTTP, browser JS, individual components and `SettingsMutationService` MUST NOT advance `effective_generation`.

## 6.8 `bootstrap.py`

Own exact startup bootstrap:

```text
bootstrap_settings_control(...)
```

Return one `SettingsBootstrapResult` containing:

```text
feature_enabled
store_state
runtime_settings
resolved_snapshot
admin_context
activation_service
```

`admin_context` exposes only:

```text
feature_enabled
store_state
read_service
mutation_service
```

It MUST NOT expose activation authority to Admin HTTP.

---

# 7. EXACT STARTUP / RESOLUTION COMPOSITION

Current production issue intentionally corrected by Stage 1:

```text
run.py obtains settings
AND
app/web/web.py:create_app() currently calls get_settings() again
```

Production startup MUST use one Settings-aware snapshot.

## 7.1 Exact `run.py` flow

Conceptually exactly:

```text
capture_loaded_artifact_identity()
        ↓
base_settings = get_settings()
        ↓
settings_bootstrap = bootstrap_settings_control(
    base_settings=base_settings,
    explicit_environment_names=<snapshot of process env names>,
    logger=logger,
)
        ↓
settings = settings_bootstrap.runtime_settings
        ↓
compose all existing runtime components using `settings`
        ↓
create_app(..., settings=settings, ...)
        ↓
compose Admin Web using the SAME `settings`
and settings_bootstrap.admin_context
        ↓
verify V1 consumer configuration composition
        ↓
if Settings enabled + store available:
    SettingsActivationService records adoption/failure
        ↓
only after successful adoption commit:
    app.run(...)
```

No Stage-1 runtime consumer may re-read SettingsStore during startup.

Adoption MUST refer to the exact configured generation and immutable snapshot used for composition.

Forbidden:

```text
read head G
→ compose from G
→ re-read G+1
→ claim G+1 adopted
```

## 7.2 Settings disabled

When:

```text
WEB_ADMIN_SETTINGS_ENABLED=false
```

`bootstrap_settings_control()` must:

- not construct/open `SettingsRepository`;
- not create DB;
- not read generations;
- return `runtime_settings = base_settings`;
- return `store_state = disabled`;
- return no read/mutation/activation services.

The rest of startup follows legacy behavior.

## 7.3 Enabled + store available

Must:

1. open/validate schema;
2. identify configured generation `G`;
3. resolve exactly one immutable `ResolvedSettingsSnapshot(G)`;
4. fully validate Stage-1 candidate settings;
5. use that exact snapshot mapping for runtime composition;
6. make read/mutation services available;
7. later record adoption for exactly `G`.

## 7.4 Enabled + store unavailable

Must:

- log bounded safe SettingsStore unavailability;
- use repository/environment base settings for main product runtime;
- expose Settings feature as enabled but store unavailable;
- make Settings read/mutation API return `503 settings_store_unavailable`;
- leave unrelated independently healthy Admin/read surfaces operational;
- not fabricate configured/effective/persisted values;
- not record Settings adoption.

---

# 8. `create_app()` SETTINGS INJECTION

Modify:

```text
app/web/web.py
```

This file is explicitly authorized because current `create_app()` independently calls `get_settings()`.

Add keyword-only parameter:

```text
settings=None
```

Exact behavior:

```text
if settings is None:
    settings = get_settings()
else:
    use supplied Mapping unchanged as application configuration source
```

Production `run.py` MUST always pass the Settings-aware `settings` mapping.

Fallback `get_settings()` remains only for backwards-compatible direct factory/test use.

No SettingsStore access is added to `app/web/web.py`.

A focused test must prove:

```text
supplied settings
→ get_settings() is NOT called
→ supplied mapping is used
```

---

# 9. ALLOWED PRODUCTION FILES

## New

```text
app/settings_control/__init__.py
app/settings_control/definitions.py
app/settings_control/models.py
app/settings_control/repository.py
app/settings_control/resolver.py
app/settings_control/validation.py
app/settings_control/services.py
app/settings_control/activation.py
app/settings_control/bootstrap.py

app/admin_web/templates/admin/settings.html
app/admin_web/static/settings.js
```

## Existing files allowed to change

```text
app/config.py
app/settings.py
run.py
app/web/web.py

app/admin_web/policy.py
app/admin_web/runtime.py
app/admin_web/routes.py
app/admin_web/templates/admin/base.html
app/admin_web/static/admin.css
```

Do NOT change:

```text
app/admin_web/static/admin.js
```

Canonical Admin static root:

```text
app/admin_web/static/
```

Canonical Settings JS:

```text
app/admin_web/static/settings.js
```

No second `app/admin_web/static/admin/` hierarchy.

No inline JS/style.

No other production file is authorized.

If another production file appears unavoidable:

```text
STOP
return exact reason
```

---

# 10. SQLITE SCHEMA IDENTITY / INTEGRITY

Freeze:

```text
SETTINGS_SCHEMA_VERSION = 1
PRAGMA user_version = 1
PRAGMA foreign_keys = ON
SETTINGS_SQLITE_BUSY_TIMEOUT_MS = 1000
```

Busy timeout is internal Stage-1 implementation constant, not UI-editable.

## 10.1 New database

A path is a new Settings DB only when SQLite opens new/empty DB with:

```text
user_version = 0
and
no existing Settings user tables
```

Initialize schema v1 transactionally.

Do not create parent directory automatically.

Missing/unusable parent path:

```text
SettingsStore unavailable
```

## 10.2 Existing schema v1

```text
user_version = 1
+ required schema shape valid
→ open normally
```

Startup schema/integrity validation must detect corrupt/incompatible DB.

A SQLite `DatabaseError`, failed `PRAGMA quick_check`, missing required v1 structure, or unknown persisted setting key makes SettingsStore unavailable.

## 10.3 Unknown/incompatible schema

Examples:

```text
user_version > 1
user_version < 1 with existing Settings tables
schema v1 shape incompatible
corrupt DB
unknown setting key in persisted override state
```

Required:

```text
NO DROP
NO destructive recreation
NO silent migration
NO runtime use of unknown key
SettingsStore unavailable
main product falls back to base settings
```

---

# 11. PHYSICAL SQLITE TABLES

Create exactly:

```text
settings_generations
settings_overrides
settings_target_state
settings_activation_events
settings_mutation_audit
settings_idempotency
```

## 11.1 `settings_generations`

```text
generation_id INTEGER PRIMARY KEY
parent_generation_id INTEGER NULL
scope_type TEXT NOT NULL
created_at_utc TEXT NOT NULL
created_by_principal_type TEXT NOT NULL
created_by_principal_name TEXT NOT NULL
request_id TEXT NULL

parent_generation_id
    FK → settings_generations(generation_id)
```

Rows immutable.

## 11.2 `settings_overrides`

```text
generation_id INTEGER NOT NULL
setting_key TEXT NOT NULL
value_type TEXT NOT NULL
integer_value INTEGER NOT NULL

PRIMARY KEY (generation_id, setting_key)
generation_id FK → settings_generations(generation_id)
```

Stage 1 permits only:

```text
value_type = integer
```

Rows present for one generation represent the complete persisted override set of that generation.

## 11.3 `settings_target_state`

```text
target TEXT PRIMARY KEY
effective_generation INTEGER NULL
updated_at_utc TEXT NULL

effective_generation FK → settings_generations(generation_id)
```

Canonical target:

```text
captive-portal.service
```

## 11.4 `settings_activation_events`

```text
event_id INTEGER PRIMARY KEY
generation_id INTEGER NOT NULL
target TEXT NOT NULL
attempted_at_utc TEXT NOT NULL
activation_result TEXT NOT NULL
effective_generation_after_attempt INTEGER NULL
safe_error_code TEXT NULL

generation_id FK → settings_generations(generation_id)
effective_generation_after_attempt FK → settings_generations(generation_id)
```

Allowed:

```text
adopted
failed
```

## 11.5 `settings_mutation_audit`

```text
audit_id INTEGER PRIMARY KEY
generation_id INTEGER NOT NULL
parent_generation_id INTEGER NULL

principal_type TEXT NOT NULL
principal_name TEXT NOT NULL

source_ip TEXT NOT NULL
request_id TEXT NOT NULL
idempotency_key TEXT NOT NULL
timestamp_utc TEXT NOT NULL

scope_type TEXT NOT NULL
scope_id TEXT NULL

setting_key TEXT NOT NULL
operation TEXT NOT NULL

previous_persisted_override INTEGER NULL
new_persisted_override INTEGER NULL

previous_configured_value INTEGER NOT NULL
new_configured_value INTEGER NOT NULL

apply_requirement TEXT NOT NULL
activation_target TEXT NOT NULL

generation_id FK → settings_generations(generation_id)
parent_generation_id FK → settings_generations(generation_id)

UNIQUE (generation_id, setting_key)
```

One audit row per setting whose persisted override state actually changed.

## 11.6 `settings_idempotency`

```text
idempotency_id INTEGER PRIMARY KEY

principal_type TEXT NOT NULL
principal_name TEXT NOT NULL
scope_type TEXT NOT NULL
idempotency_key TEXT NOT NULL

request_payload_hash TEXT NOT NULL

result_http_status INTEGER NOT NULL
result_response_json TEXT NOT NULL
result_generation INTEGER NOT NULL
result_changed INTEGER NOT NULL

created_at_utc TEXT NOT NULL

result_generation FK → settings_generations(generation_id)

UNIQUE (
    principal_type,
    principal_name,
    scope_type,
    idempotency_key
)
```

`result_response_json`:

- canonical;
- non-secret;
- successful Settings mutation response only;
- not arbitrary Settings storage;
- maximum 65536 UTF-8 bytes.

If successful response cannot fit the bound, do not commit mutation.

---

# 12. BOOTSTRAP GENERATION `0`

First schema initialization transaction creates:

```text
generation_id = 0
parent_generation_id = null
scope_type = global
persisted override set = empty
```

and target state:

```text
target = captive-portal.service
effective_generation = null
```

Generation 0 is:

- physical;
- reserved;
- immutable;
- system bootstrap root;
- not operator mutation.

Initial:

```text
configured_generation = 0
ETag = "settings-g0"
effective_generation = null
```

After first successful Settings-aware adoption:

```text
configured_generation = 0
effective_generation = 0
activation_state = active
```

First changed mutation:

```text
new generation = 1
parent_generation_id = 0
```

Generation allocation MUST use SQLite `INTEGER PRIMARY KEY` allocation inside the write transaction.

Forbidden:

```text
unlocked SELECT MAX(generation_id) + 1
```

---

# 13. CANONICAL RESOLVER

For each registered key:

```text
persisted GLOBAL override
>
explicit environment value
>
repository default
```

At main startup capture the set of explicitly present process environment variable names.

Resolver uses:

```text
definition.environment_variable_name in explicit_environment_names
```

for `base_source`.

Do NOT infer source from scalar imported through `app/config.py`.

For each registered key:

```text
base_source = environment | repository_default
base_value = typed integer before persisted override
```

Invalid explicit environment/base scalar must fail validation safely; do not silently replace with default.

`clear_override` means no override row for that key in the new generation.

Never persist a copied lower-precedence value to simulate reset.

---

# 14. VALIDATION CONTRACT

One candidate:

```text
current base settings
+
current persisted override set
+
all proposed changes
        ↓
candidate complete settings mapping
        ↓
registry primitive validation
        ↓
existing semantic validators
        ↓
cross-setting validation
        ↓
only then persistence commit
```

If any field fails:

```text
NONE persisted
no generation
no audit
no success-idempotency record
422 validation_failed
```

Frontend validation is UX only.

Primitive validation:

- exact integer;
- boolean is NOT accepted as integer;
- canonical bounds;
- runs even if consumer disabled.

Use existing semantic authorities:

```text
admin_web_config_from_settings
home_activity_config_from_settings
home_health_config_from_settings
home_ap_24h_config_from_settings
```

Do not duplicate their cross-setting rules in JS.

---

# 15. SINGLE-WRITER MUTATION TRANSACTION

Every new idempotency identity reaches SQLite single-writer boundary:

```text
BEGIN IMMEDIATE
```

Inside the SAME transaction:

1. re-check idempotency identity;
2. read/re-check configured head;
3. compare `If-Match`;
4. load complete current override state;
5. construct resulting override state;
6. determine persisted change/no-op;
7. validate full candidate;
8. if changed, allocate/insert one generation;
9. if changed, persist complete override rows for new generation;
10. if changed, persist audit rows for actually changed keys;
11. persist successful idempotency result for changed OR no-op success;
12. commit.

SQLite busy/lock/commit failure:

```text
rollback
no in-memory-only success
503 settings_store_unavailable
```

Two concurrent requests using same current `If-Match` must not both create successful child generations.

---

# 16. MUTATION ENDPOINT

```text
POST /admin/api/v1/settings/generations
```

Content type:

```text
application/json
```

Dedicated body limit:

```text
32768 bytes
```

Maximum changes:

```text
64
```

Operations:

```text
set
clear_override
```

Canonical request:

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

Reject:

- malformed JSON;
- top-level non-object;
- unknown top-level field;
- missing/invalid/empty `changes`;
- >64 changes;
- unknown change field;
- duplicate key;
- unknown/non-editable key;
- unsupported operation;
- missing value on `set`;
- value on `clear_override`;
- wrong value type;
- Site/scope field;
- arbitrary setting name.

---

# 17. EXACT JSON POST CARVE-OUT

Add exactly one JSON exception:

```text
POST /admin/api/v1/settings/generations
```

For this endpoint only:

```text
Content-Type = application/json
body limit = 32768 bytes
```

Do NOT apply `WEB_ADMIN_MAX_POST_BYTES` here.

Do NOT increase `WEB_ADMIN_MAX_POST_BYTES`.

Do NOT parse `request.form`.

Preserve unchanged:

```text
POST /admin/login
POST /admin/logout
```

including current form-urlencoded/body-limit/duplicate-field/CSRF/session behavior.

No other Admin POST gets JSON behavior.

Settings mutation body:

1. require `Content-Length` under current Admin POST security rule;
2. reject >32768 before parse;
3. read raw body once;
4. parse JSON from bounded body;
5. reject malformed/non-object/unknown fields.

---

# 18. GLOBAL AUTHORIZATION

Add:

```text
GLOBAL_SETTINGS_CAPABILITIES = frozenset({
    "admin.read.settings.global",
    "admin.write.settings.global",
})
```

Add exact policy boundary:

```python
AdminAccessPolicy.authorize_global(
    principal,
    capability,
) -> bool
```

V1 true only when:

```text
principal is AdminPrincipal
principal.principal_type == "platform_operator"
capability in GLOBAL_SETTINGS_CAPABILITIES
```

Preserve existing Site `authorize(...)` behavior unchanged.

Global Settings MUST NOT depend on:

```text
default_site_id
allowed Site selection
arbitrary Site ID
AdminSiteContextResolver
```

Settings page/API call `authorize_global`.

---

# 19. CSRF

Mutation requires:

```text
authenticated Admin session
+
admin.write.settings.global
+
X-CSRF-Token
```

Header token matches:

```text
g.admin_session.csrf_token
```

using existing canonical token/constant-time comparison boundary.

Do not accept Settings CSRF from query/body/form.

Existing session cookie remains:

```text
Secure
HttpOnly
SameSite=Strict
```

---

# 20. `If-Match` / STALE WRITE

GET returns:

```text
ETag: "settings-g<configured_generation>"
```

New mutation identity requires canonical:

```text
If-Match: "settings-g<configured_generation>"
```

Missing:

```text
428 precondition_required
```

Malformed:

```text
400 invalid_request
```

Stale:

```text
412 stale_generation
```

CAS occurs inside same `BEGIN IMMEDIATE` transaction.

No last-writer-wins.

No auto-retry after 412.

Client on 412:

- re-read current model;
- show conflict/stale message;
- require operator review;
- resubmit only explicitly with NEW idempotency key.

---

# 21. IDEMPOTENCY

Require:

```text
Idempotency-Key: <canonical UUID>
```

Exact request order:

```text
A authenticate
B authorize GLOBAL write
C validate CSRF + required header syntax + content type + body bounds
D parse/validate structural JSON
E canonicalize payload
F compute payload SHA-256
G check existing idempotency BEFORE ordinary stale-generation rejection
```

Existing identity + same hash:

```text
return stored ORIGINAL successful status + JSON
no current-head CAS
no generation
no audit
```

Existing identity + different hash:

```text
409 idempotency_conflict
```

New identity:

```text
BEGIN IMMEDIATE
→ re-check idempotency
→ current-head If-Match CAS
→ mutation/no-op
```

## 21.1 Canonical payload

Canonicalize after strict structure validation:

```text
{
  "changes": [canonical change objects sorted by setting key]
}
```

`set` canonical object:

```text
key
operation="set"
value=<canonical integer>
```

`clear_override`:

```text
key
operation="clear_override"
```

Serialize deterministic UTF-8 compact JSON with sorted object keys.

Equivalent whitespace/object-member ordering/change ordering must hash identically.

Hash:

```text
SHA-256 lowercase hex
```

## 21.2 Successful no-op

```text
200
changed=false
```

is accepted success and MUST persist idempotency result.

Later replay after head advance returns original stored 200.

## 21.3 Failures

No successful idempotency record for authentication/authorization/CSRF/request/validation/stale/media/body/idempotency/persistence failure.

---

# 22. MUTATION RESULT

Changed persisted override state:

```text
201 Created
changed=true
new generation
restart_required=true
activation_state=pending_main_restart
```

No semantic persisted override change:

```text
200 OK
changed=false
no generation
configured_generation unchanged
ETag generation unchanged
```

“No change” compares resulting persisted override state, not visible effective scalar.

Success body fields:

```text
api_version
request_id
scope
changed
configured_generation
effective_generation
activation_state
restart_required
settings
```

Exact successful body/status is stored transactionally for idempotent replay.

Normal non-replayed success is followed by fresh GET in UI.

---

# 23. READ API

```text
GET /admin/api/v1/settings
```

Requires authenticated session +:

```text
admin.read.settings.global
```

Headers:

```text
Content-Type: application/json
Cache-Control: no-store
ETag: "settings-g<configured_generation>"
```

Page-level:

```text
api_version = admin.settings.v1
scope.type = global
store_state
configured_generation
effective_generation
etag
restart_required
pending_setting_count
settings[]
```

Per-setting `SettingReadModelV1` exactly:

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

Frontend validation metadata comes from server registry.

---

# 24. READ MODEL SEMANTICS

`configured_value`:

```text
value fresh runtime would use now under current base + configured-head override
```

`persisted_override_value`:

```text
explicit configured-generation override or null
```

Read service receives immutable in-memory startup snapshot actually adopted by current runtime.

Enabled consumer:

```text
effective_value = canonical scalar from adopted runtime snapshot
```

Disabled consumer:

```text
effective_value = null
consumer_state = consumer_disabled
```

If:

```text
configured_generation != effective_generation
```

then:

```text
pending_value = configured_value
```

otherwise:

```text
pending_value = null
```

Consumer states:

```text
active
consumer_disabled
null
```

Activation states:

```text
active
pending_main_restart
activation_failed
runtime_unavailable
```

Resolution:

1. no trustworthy runtime effective snapshot → `runtime_unavailable`;
2. configured == effective → `active`;
3. current configured generation has later positive durable failed event not superseded by adoption → `activation_failed`;
4. otherwise → `pending_main_restart`.

`last_changed_at` / `last_changed_by` refer to latest successful audit row that actually changed that setting override; otherwise null.

---

# 25. PENDING / RESTART UX

Changed Save wording must mean:

```text
Persisted successfully.
Pending captive-portal.service restart.
```

There is:

```text
NO restart button
NO systemctl
NO systemd D-Bus
NO sudo service control
NO reload
NO hot reload
```

---

# 26. RUNTIME ADOPTION

Only:

```text
captive-portal.service main runtime
via run.py composition/lifecycle boundary
```

declares adoption.

Call path:

```text
run.py
→ SettingsActivationService
→ SettingsRepository / SettingsStore
```

For startup generation `G`:

1. head `G` read during bootstrap;
2. one immutable snapshot `G` created;
3. full Stage-1 validation succeeds;
4. same snapshot used for composition;
5. every enabled Stage-1 config consumer accepts it OR is explicitly disabled;
6. Admin Settings/Admin configuration composition registers successfully;
7. durable adoption written;
8. only then effective generation = `G`;
9. only after durable commit may `app.run(...)` serve requests.

Canonical event:

```text
generation_id = G
target = captive-portal.service
attempted_at = <UTC>
activation_result = adopted
effective_generation_after_attempt = G
safe_error_code = null
```

Atomic activation transaction:

```text
append activation event
+
update target effective_generation = G
```

Every Settings-aware main-service startup reports adoption, even if `G` equals previously recorded effective generation.

Startup adoption never creates configured generation.

---

# 27. ADOPTION IS NOT SOURCE HEALTH

Do NOT require healthy:

- Omada reachability;
- Analytics data;
- Current State freshness;
- Traffic source;
- Observation source;
- indefinite future liveness.

Operational source degradation unrelated to Settings configuration is not activation failure.

Settings availability must not depend on `AdminQueryService` availability.

---

# 28. ACTIVATION FAILURE

No external activation reporter.

`activation_failed` requires positive in-process durable attestation by the new `captive-portal.service` process after it:

```text
identifies configured G
attempts Stage-1 adoption
positively determines Settings/Admin configuration adoption failure
can durably write failure event
```

Failure event:

```text
generation_id = G
target = captive-portal.service
attempted_at = <UTC>
activation_result = failed
effective_generation_after_attempt = <last adopted generation or null>
safe_error_code = <bounded non-secret category>
```

Do not advance effective generation.

No automatic rollback.

Do not infer failure from restart request/process disappearance/timeout/missing heartbeat/absent success/systemd pre-Python failure/import/host/resource failure/early crash.

If available-store Settings/Admin configuration is positively invalid/uncomposable, new process must NOT serve requests from an unadopted generation.

After best-effort durable attributable failure recording, startup aborts rather than silently serving hidden fallback configuration.

Store-unavailable fallback is the only automatic base-settings fallback in Stage 1.

---

# 29. INDEPENDENT SETTINGS AVAILABILITY

Admin healthy + Settings enabled + store healthy + Analytics/read source unhealthy:

```text
Settings page/API remain usable
```

Admin healthy + Settings enabled + store unavailable:

```text
Settings nav remains present for authorized operator
GET /admin/settings renders bounded unavailable state
Settings API → 503 settings_store_unavailable
unrelated healthy Admin/read surfaces continue
```

Settings disabled:

```text
no Settings DB access
no Settings nav
GET /admin/settings → 404 not_found
GET/POST Settings API → 404 feature_disabled
rest of Admin unchanged
```

Never leak raw SQLite error/path in UI/API failure response.

---

# 30. ADMIN RUNTIME INTEGRATION

Extend `AdminWebRuntime` with Settings-specific fields equivalent to:

```text
settings_feature_enabled: bool
settings_store_state: str
settings_read_service: SettingsReadService | None
settings_mutation_service: SettingsMutationService | None
```

`create_admin_web_runtime(...)` receives:

```text
settings_control: SettingsAdminContext
```

Settings context attaches independently of Analytics/Observation/Visit/Current-State query source availability.

Settings routes MUST NOT depend on `runtime.query_service`.

---

# 31. GLOBAL SETTINGS PAGE

```text
GET /admin/settings
```

GLOBAL only.

MUST NOT call:

```text
AdminSiteContextResolver
resolver.default()
default Site selection
site-scoped page rendering semantics
```

Requires authenticated session + `admin.read.settings.global`.

Enabled + store available:

- render Settings shell;
- expose current session CSRF token to dedicated same-origin JS using safe HTML metadata/attribute;
- JS loads GET API.

Enabled + store unavailable:

- render bounded unavailable state;
- no raw DB error/path;
- page reachable.

Disabled:

```text
404 not_found
```

---

# 32. NAVIGATION

```text
WEB_ADMIN_SETTINGS_ENABLED=false
→ Settings nav absent
```

```text
WEB_ADMIN_SETTINGS_ENABLED=true
+ authenticated principal passes authorize_global(read)
→ Settings nav present
```

Nav remains present if store unavailable.

Use Blueprint template context processor or equivalent Admin template context derived from feature-enabled flag + current principal + `authorize_global`.

Do not authorize via Site.

---

# 33. SETTINGS UI

Template:

```text
app/admin_web/templates/admin/settings.html
```

JS:

```text
app/admin_web/static/settings.js
```

CSS additions:

```text
app/admin_web/static/admin.css
```

Exactly two groups:

```text
Pagination / Presentation
Refresh Cadence
```

Primary UI uses human labels/descriptions; technical key secondary.

Show per setting:

- configured value;
- effective value;
- persisted override;
- base source/value;
- pending value;
- consumer state;
- apply requirement;
- validation bounds.

Actions:

```text
set override
clear override / use deployment value
save one atomic batch
```

No inline JS/style.

---

# 34. SETTINGS JS REQUEST CONTRACT

Dedicated JS must:

1. GET Settings API;
2. retain ETag;
3. render from server metadata;
4. on Save generate fresh UUID idempotency key using browser crypto UUID support;
5. POST JSON with `X-CSRF-Token`, `If-Match`, `Idempotency-Key`, `Content-Type`;
6. on 200/201 show correct save/pending state and perform fresh GET;
7. on 412 do not auto-retry, reload current model, show stale/conflict message, require review;
8. on 503 show bounded unavailable state.

No browser precedence logic.

No independent client validation-bound table.

---

# 35. ERROR CONTRACT

Canonical:

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

Classes:

```text
400 invalid_request
400 invalid_csrf
401 authentication_required
403 settings_forbidden
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

Disabled page uses standard/HTML:

```text
404 not_found
```

Never return stack trace/raw SQLite exception/raw DB path/environment dump/secret/token/header.

---

# 36. AUDIT

Changed generation and mutation audit are transactionally linked.

Audit only settings whose persisted override state changed.

Entire batch no-op:

```text
no generation
no mutation audit
successful idempotency result persisted
```

Activation events are separate durable records.

No history browser/rollback UI/automatic rollback/pruning.

---

# 37. AUTHORIZED TEST FILES

Create:

```text
tests/settings_control/__init__.py
tests/settings_control/test_definitions.py
tests/settings_control/test_repository.py
tests/settings_control/test_resolver.py
tests/settings_control/test_validation.py
tests/settings_control/test_services.py
tests/settings_control/test_activation.py
tests/settings_control/test_bootstrap.py
tests/settings_control/test_run_integration.py
tests/settings_control/test_web_settings_injection.py

tests/admin_web/test_settings_routes.py
tests/admin_web/test_settings_ui.py
```

No existing test file modification authorized.

Existing directly affected tests may be RUN but not rewritten.

If an existing test genuinely requires modification:

```text
STOP
return exact file/test/reason
```

---

# 38. REQUIRED FOCUSED TEST COVERAGE

Required tests include:

1. exactly 12 definitions + exact env names/settings keys/defaults/bounds/validator-consumer mapping;
2. config defaults and registry defaults do not drift;
3. disabled default causes zero DB side effect;
4. new DB schema v1 + generation 0 + target row;
5. repeated initialization idempotent;
6. unknown/newer/corrupt schema no drop/recreate and main fallback;
7. unknown persisted setting key fails safely;
8. FK/uniqueness/immutability contracts;
9. resolver override > env > repository default;
10. clear override fallback;
11. correct `base_source`;
12. invalid explicit env not silently replaced;
13. primitive bounds/wrong type/bool rejection;
14. disabled consumer still validates;
15. existing semantic validators invoked;
16. invalid field rejects whole batch;
17. concurrent same-If-Match CAS yields exactly one successful head transition;
18. changed request → 201/new generation/audit/idempotency/pending restart;
19. no-op → 200/no generation/no audit/idempotency stored;
20. replay after head advance returns original success, not 412;
21. no-op replay after head advance returns original 200;
22. idempotency conflict → 409 even if old If-Match is now stale;
23. Settings JSON POST isolated from login/logout form POST;
24. Settings 32768-byte bound independent from `WEB_ADMIN_MAX_POST_BYTES`;
25. GLOBAL policy independent of Site/default Site;
26. existing Site authorization remains unchanged;
27. store unavailable nav/page/API bounded behavior;
28. startup snapshot identity: compose G → adopt G only;
29. injected `create_app(settings=...)` never calls `get_settings()`;
30. adoption commit before `app.run`;
31. adoption durable-write failure → not active and no serving;
32. positive Settings adoption failure → durable failed event/no effective advance/no serving;
33. silence/process loss not synthesized as activation_failed;
34. disabled consumer semantics exactly match A4;
35. unrelated operational source degradation does not invalidate adoption;
36. Settings remains independent of Admin query-source health.

---

# 39. FOCUSED VERIFICATION COMMANDS

Minimum:

```bash
pytest -q \
  tests/settings_control \
  tests/admin_web/test_settings_routes.py \
  tests/admin_web/test_settings_ui.py
```

Also run exact directly affected existing Admin/config/policy/web-factory/startup tests required by actual diff and list each in handoff.

Mandatory:

```bash
python -m compileall \
  app/settings_control \
  tests/settings_control
```

and:

```bash
git diff --check
```

No broad/full repository gate by Coder.

No production test.

No service restart.

---

# 40. DOCUMENTATION FILES AUTHORIZED

Only:

```text
.env.example
docs/configuration.md
docs/modules/admin-web.md
```

Document implemented Stage-1 behavior only:

- `WEB_ADMIN_SETTINGS_ENABLED`;
- `SETTINGS_DB_PATH`;
- exact 12-key allowlist;
- disabled-by-default state;
- configured/effective/pending distinction;
- restart-required semantics;
- no restart/systemd UI;
- no secret mutation;
- no Site mutation;
- reset = clear persisted override.

No architecture/roadmap rewrite by Coder.

---

# 41. FORBIDDEN CHANGES

Do NOT implement/change:

```text
CAPPORT settings ownership/mutation
Omada URL/ID/client credential mutation
Omada secret storage
Admin username/password/password-hash mutation
Admin source-network allowlist mutation
Admin Site allowlist/default Site mutation
Admin HTTPS/security boundary mutation
session/login/CSRF security-bound mutation
Site-scoped Settings
feature-enable toggles as editable values
Pending Session Cleaner settings
Visit Lifecycle operational settings
Visitor Registry operational settings
Observation collector settings
Current State collector settings
Analytics semantic thresholds
Traffic Projection settings
Device Fingerprint settings
Network Intelligence / DTI settings
webhook secret/auth mutation
bearer token mutation
TLS/private-key path mutation
database/log path mutation
bind address/port mutation
NIC/SPAN/RSPAN mutation
auxiliary direct-env integration
generated EnvironmentFile
systemctl/systemd D-Bus/sudo service control
restart/reload button
hot reload
automatic rollback
history browser
rollback UI
generic environment editor
arbitrary setting search/edit
new auxiliary/background service
unrelated refactor
unrelated visual redesign
```

Do not change:

```text
app/admin_web/static/admin.js
```

---

# 42. PRODUCTION ACTIVATION GATE

Coder does not enable production Settings.

Default:

```text
WEB_ADMIN_SETTINGS_ENABLED=false
```

No production DB creation/env change/restart/mutation/test is authorized by this R1.

Production activation requires separate explicit operator/Tech Lead gate later.

---

# 43. CODER FIRST-HANDOFF CONTRACT

Return:

```text
BASE_HEAD
BASE_TREE
WORKTREE_STATE

exact new files
exact modified files

focused test commands/results
exact directly affected existing test commands/results

compileall result
git diff --check result

architecture requirement → implementation mapping
SQLite schema summary
generation-0 behavior confirmation
resolver precedence confirmation
12-and-only-12 writable key confirmation
global authorization confirmation
JSON route isolation confirmation
idempotency changed/no-op/replay confirmation
startup snapshot/adoption confirmation
no-systemd/no-restart-authority confirmation
known limitations

architecture ambiguity = NONE / <exact>
```

If patch artifact created, also return:

```text
exact BASE-to-implementation patch path
patch size
patch SHA256
```

First handoff MUST state:

```text
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
```

If ambiguity appears:

```text
STOP
do not invent behavior
return exact ambiguity
```

---

# 44. ACCEPTANCE CRITERIA

R1 implementation is source-review eligible only if all are true:

1. exact accepted HEAD/TREE used;
2. Settings disabled by default;
3. disabled state opens/creates no Settings DB;
4. schema v1 identity/integrity implemented;
5. immutable physical generation 0 exists;
6. exactly 12 keys writable;
7. canonical defaults/env identities do not drift;
8. GLOBAL-only mutation;
9. one canonical resolver;
10. override > env > repository default;
11. one immutable startup snapshot used by V1 runtime consumers;
12. production `create_app` does not independently call `get_settings`;
13. backend validation atomic;
14. existing semantic validators authoritative;
15. `BEGIN IMMEDIATE` CAS/single-writer behavior correct;
16. no concurrent sibling successful heads;
17. ETag/If-Match stale protection works;
18. idempotency lookup precedes stale rejection for replay;
19. changed and no-op success are idempotent;
20. stored idempotency response reproduces original success;
21. JSON Settings POST isolated from login/logout;
22. dedicated body limit does not alter existing POST bound;
23. read/write GLOBAL capabilities distinct;
24. Site authorization unchanged;
25. CSRF protects JSON mutation;
26. Settings availability independent of query-source health;
27. store-unavailable UI/API safe and bounded;
28. enabled/store-unavailable nav remains reachable;
29. main runtime alone advances effective generation;
30. adoption is exact startup generation/snapshot;
31. adoption commits before request serving;
32. durable adoption failure never claims active;
33. `activation_failed` requires positive in-process attestation;
34. unrelated operational source degradation is not activation failure;
35. disabled consumer has `effective_value=null`;
36. consumer state separate from activation state;
37. durable mutation audit exists;
38. durable activation events exist;
39. Save never claims immediate activation;
40. no restart/systemd authority exists;
41. no forbidden domain expansion;
42. focused tests pass;
43. compileall passes;
44. `git diff --check` passes;
45. first handoff has no commit/push/PR/merge/deploy.

---

# 45. CURRENT AUTHORIZATION STATE

```text
ARCHITECTURE
= FINAL / ACCEPTED

ROADMAP v0.2
= PASS

TASK-ADMIN-SETTINGS-01 R1
= FINAL CANDIDATE FOR TECH LEAD REVIEW

ARCHITECT
= NO ACTION REQUIRED

TECHNICAL DEVELOPER SETTINGS
= R1 ISSUED FOR TECH LEAD REVIEW

CODER
= HOLD

IMPLEMENTATION
= NOT YET AUTHORIZED

PRODUCTION
= NO CHANGE

SYSTEMD
= NO ACTION
```

Next:

```text
Tech Lead final implementation-contract review
→ if PASS:
   Coder implementation authorization
→ isolated worktree implementation
→ first source/diff handoff with COMMIT=NO
```
