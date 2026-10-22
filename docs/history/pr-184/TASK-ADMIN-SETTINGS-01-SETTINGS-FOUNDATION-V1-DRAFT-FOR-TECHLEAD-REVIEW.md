# TASK-ADMIN-SETTINGS-01 — SETTINGS FOUNDATION + SAFE ADMIN SETTINGS V1

**Project:** CaptivPortal  
**Area:** Admin UI → Settings  
**Role owner:** Technical Developer Settings  
**Task type:** Exact implementation contract for Coder  
**Status:** DRAFT FOR TECH LEAD IMPLEMENTATION-CONTRACT REVIEW  
**Coder:** HOLD until Tech Lead acceptance  
**Production:** NO CHANGE  
**Systemd action:** NO  
**Baseline:** `main@be3fe14f929b45e4a1ca3991bc6a2a3011792641`

## Authoritative architecture

This TASK implements, without reinterpretation:

1. `CAPTIVPORTAL ADMIN SETTINGS — ARCHITECTURE CONTRACT v0.1`
2. `CAPTIVPORTAL ADMIN SETTINGS — ARCHITECTURE DISPOSITION A1–A4`

Architecture status:

```text
FINAL / ACCEPTED FOR STAGE 1 TASK PREPARATION
```

Roadmap reference:

`CAPTIVPORTAL ADMIN SETTINGS — PRELIMINARY ROADMAP v0.2`

The roadmap is sequencing context only. Architecture and this accepted implementation contract are authoritative.

---

# 0. TASK OBJECTIVE

Implement the first writable CaptivPortal Admin Settings control plane and expose exactly the approved 12 GLOBAL, non-secret, non-self-lockout Admin presentation/refresh settings.

The implementation must provide:

```text
deployment/base settings
+
durable persisted GLOBAL overrides
        ↓
one canonical resolved settings snapshot
        ↓
existing subsystem validation
        ↓
runtime composition
        ↓
durable effective-generation adoption
```

and:

```text
Admin Settings UI
        ↓
authorized JSON mutation
        ↓
atomic validation
        ↓
immutable configured generation
        ↓
durable audit + idempotency
        ↓
pending_main_restart
```

The Admin application must not restart or reload `captive-portal.service`.

---

# 1. HARD SCOPE

## 1.1 Only writable settings

Exactly these 12 keys may be writable.

### Pagination / bounded query presentation

```text
WEB_ADMIN_DEVICE_PAGE_SIZE                  integer  1..500
WEB_ADMIN_VISIT_PAGE_SIZE                   integer  1..500
WEB_ADMIN_OBSERVATION_PAGE_SIZE             integer  1..500
WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS      integer  1..168
WEB_ADMIN_CURRENT_STATE_PAGE_SIZE           integer  1..250
WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE            integer  1..250
```

### Refresh cadence

```text
WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS         integer  60..300
WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS      integer  60..300
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS           integer  60..300
WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS     integer  60..300
WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS       integer  60..300
WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS       integer  60..600
```

Any other key is deny-by-default and must be rejected by mutation.

## 1.2 Scope

All Stage 1 settings are:

```text
scope_type = global
scope_id = null
secret_class = normal
apply_requirement = main_service_restart
activation_target = captive-portal.service
```

No Site ID is accepted by Stage 1 Settings endpoints.

---

# 2. BOOTSTRAP CONTROLS

Add deployment-controlled bootstrap configuration equivalent to:

```text
WEB_ADMIN_SETTINGS_ENABLED
SETTINGS_DB_PATH
```

Canonical defaults:

```text
WEB_ADMIN_SETTINGS_ENABLED = false
SETTINGS_DB_PATH = /opt/CaptivePortal/data/settings.sqlite3
```

These controls:

- remain deployment/environment controlled;
- are not stored as editable Settings values;
- are not returned as mutable settings;
- are not writable through Admin UI.

If Settings is disabled, the Settings mutation/read surface follows the architecture `feature_disabled` behavior and the rest of CaptivPortal must remain unaffected.

If SettingsStore is unavailable at startup:

- Portal/Auth/CAPPORT/main product runtime must continue from repository/environment base settings;
- Settings mutation surface becomes unavailable;
- Settings store health is unavailable;
- other independently healthy Admin/read surfaces may continue;
- no persisted value may be fabricated.

---

# 3. REQUIRED DOMAIN MODULE BOUNDARIES

Create a dedicated common Settings domain outside `app/admin_web` because both startup/runtime composition and Admin HTTP consume it.

Exact new package:

```text
app/settings_control/
```

Exact new files:

```text
app/settings_control/__init__.py
app/settings_control/definitions.py
app/settings_control/models.py
app/settings_control/repository.py
app/settings_control/resolver.py
app/settings_control/validation.py
app/settings_control/services.py
app/settings_control/activation.py
```

Responsibilities:

## `definitions.py`

Own `SettingsDefinitionRegistry` and the exact 12-key matrix.

Registry metadata for each setting must include:

```text
key
settings_dict_key
display_label
description
group
value_type
scope_type
secret_class
editable
primitive bounds
apply_requirement
activation_target
owning semantic validator / consumer mapping
```

Unknown keys are never accepted.

## `models.py`

Own typed immutable domain/read objects required by the architecture, including:

- setting definition;
- resolved/configured setting state;
- page-level Settings read state;
- mutation change;
- mutation result;
- activation event;
- consumer state / activation state enums or equivalent typed constants.

Do not create a generic arbitrary JSON settings model.

## `repository.py`

Own all SQLite access for SettingsStore.

No Admin route/template/browser code may access SQLite directly.

## `resolver.py`

Own canonical resolution of:

```text
repository/code default
→ process environment
→ persisted GLOBAL override
```

for registered Stage 1 settings.

The Settings API and startup/runtime must consume the same resolver behavior.

## `validation.py`

Own:

- registry primitive validation;
- construction of candidate full settings snapshot;
- invocation of existing subsystem validators;
- atomic all-or-nothing validation result.

Frontend validation is UX only.

## `services.py`

Own:

```text
SettingsReadService
SettingsMutationService
```

Routes call these services, not repository internals.

## `activation.py`

Own:

```text
SettingsActivationService
```

Only the main runtime composition boundary may use it to record runtime adoption/failure.

Admin HTTP mutation must not advance `effective_generation`.

---

# 4. EXISTING FILES ALLOWED TO CHANGE

The Coder may modify only the following existing production files unless Tech Lead explicitly revises this list before authorization:

```text
app/config.py
app/settings.py
run.py

app/admin_web/__init__.py
app/admin_web/config.py
app/admin_web/policy.py
app/admin_web/runtime.py
app/admin_web/pages.py
app/admin_web/routes.py

app/admin_web/templates/admin/base.html
```

New UI files authorized:

```text
app/admin_web/templates/admin/settings.html
```

Use the existing Admin static structure. If a dedicated Settings JS file is needed, exactly one new file is authorized under the existing Admin static directory:

```text
app/admin_web/static/admin/settings.js
```

If the repository's actual static root at the baseline uses a different existing Admin static path, preserve that existing path rather than creating a second static hierarchy; record the exact path in handoff.

No unrelated production file may be changed.

---

# 5. TEST FILES AUTHORIZED

Create dedicated narrow tests:

```text
tests/settings_control/__init__.py
tests/settings_control/test_definitions.py
tests/settings_control/test_repository.py
tests/settings_control/test_resolver.py
tests/settings_control/test_validation.py
tests/settings_control/test_services.py
tests/settings_control/test_activation.py

tests/admin_web/test_settings_routes.py
tests/admin_web/test_settings_ui.py
```

Existing Admin test fixtures may be minimally modified only if required to inject the new Settings services/config:

```text
tests/admin_web/conftest.py
```

Existing tests may not be broadly rewritten.

---

# 6. SETTINGSSTORE SQLITE CONTRACT

Canonical database path default:

```text
/opt/CaptivePortal/data/settings.sqlite3
```

The implementation must initialize the SettingsStore transactionally and idempotently.

Required logical persisted data:

1. immutable configured generations;
2. generation-specific persisted override state;
3. activation target effective-generation state;
4. activation events;
5. mutation audit;
6. idempotency records.

Exact physical table/column names are implementation details fixed by this TASK as follows:

```text
settings_generations
settings_overrides
settings_target_state
settings_activation_events
settings_mutation_audit
settings_idempotency
```

## 6.1 `settings_generations`

Must contain at minimum:

```text
generation_id INTEGER PRIMARY KEY
parent_generation_id INTEGER NULL
scope_type TEXT NOT NULL
created_at_utc TEXT NOT NULL
created_by_principal_type TEXT NOT NULL
created_by_principal_name TEXT NOT NULL
request_id TEXT NULL
```

Generation rows are immutable after creation.

## 6.2 `settings_overrides`

Must identify the value belonging to a configured generation:

```text
generation_id
setting_key
value_type
integer_value
```

Stage 1 stores only canonical integer values.

No arbitrary JSON payload column is permitted for Stage 1 setting values.

The persisted override set for a generation represents the complete GLOBAL override state for that generation.

## 6.3 `settings_target_state`

One row per activation target:

```text
target
effective_generation NULLABLE
updated_at_utc NULLABLE
```

Canonical target:

```text
captive-portal.service
```

## 6.4 `settings_activation_events`

At minimum:

```text
event_id
generation_id
target
attempted_at_utc
activation_result
effective_generation_after_attempt
safe_error_code NULLABLE
```

Allowed Stage 1 `activation_result`:

```text
adopted
failed
```

## 6.5 `settings_mutation_audit`

For every accepted changed generation, persist one audit row per changed key containing at minimum the architecture-required fields:

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

Stage 1 contains no secrets.

## 6.6 `settings_idempotency`

Persist at minimum:

```text
principal_type
principal_name
scope_type
idempotency_key
request_payload_hash
result_generation
result_changed
created_at_utc
```

Enforce uniqueness for the canonical idempotency identity required by the architecture.

---

# 7. BOOTSTRAP GENERATION

On first successful SettingsStore initialization, in one bootstrap transaction create physical immutable generation:

```text
generation_id = 0
parent_generation_id = null
scope_type = global
override set = empty
```

Generation `0`:

- is reserved;
- is immutable;
- is not an operator mutation;
- requires no per-setting mutation audit merely for bootstrap.

Initial state:

```text
configured_generation = 0
ETag = "settings-g0"
effective_generation = null
```

After first successful Settings-aware runtime adoption:

```text
configured_generation = 0
effective_generation = 0
activation_state = active
```

First real changed mutation must create:

```text
generation 1
parent_generation_id = 0
```

---

# 8. CONFIGURATION RESOLUTION INTEGRATION

Current baseline pipeline:

```text
process environment
→ app/config.py
→ app/settings.py:get_settings()
→ runtime composition
```

Evolve it only for the registered Stage 1 values:

```text
repository defaults / app config
+
process environment
        ↓
base settings snapshot
+
SettingsStore configured generation
        ↓
ResolvedSettingsSnapshot
        ↓
existing subsystem validators
        ↓
runtime composition
```

Do not rewrite unrelated configuration.

## Required rule

For each registered Stage 1 setting:

```text
persisted GLOBAL override
>
environment
>
repository/code default
```

`clear_override` removes the override from the newly created generation so resolution falls back to environment or repository default.

Do not copy a lower-precedence value into persistence to represent reset.

## Base-source reporting

For Stage 1 read model:

```text
base_source = environment | repository_default
base_value = lower-precedence scalar before persisted override
```

The implementation must know whether the environment explicitly supplied the corresponding value; do not infer `environment` merely because `app/config.py` currently contains the resolved scalar.

---

# 9. FULL CANDIDATE VALIDATION

One mutation request is processed as:

```text
base settings
+
current persisted override head
+
all proposed changes
        ↓
candidate full settings snapshot
        ↓
registry primitive validation
        ↓
existing affected subsystem validators
        ↓
cross-setting validation
        ↓
one SQLite transaction
```

If any proposed change fails:

```text
no new generation
no override change
no mutation audit
no idempotency success record for an accepted generation
HTTP 422 validation_failed
```

Partial field success is forbidden.

The existing validators remain semantic authorities.

The Coder must reuse the current Admin configuration validation boundaries, including where applicable the existing Admin/Home configuration validators; do not duplicate semantic validation in JavaScript or invent a second unrelated parser.

Primitive bounds run even if the owning optional consumer is disabled.

---

# 10. GENERATION MUTATION SEMANTICS

Canonical endpoint:

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

Allowed operations:

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

- unknown top-level fields;
- unknown change fields;
- unknown keys;
- non-editable keys;
- unsupported operations;
- duplicate keys;
- wrong value type;
- value on `clear_override`;
- missing value on `set`;
- Site fields/scope;
- malformed JSON.

No semantic persisted change:

```text
HTTP 200
changed = false
no new generation
configured_generation unchanged
ETag unchanged
```

Changed mutation:

```text
HTTP 201
changed = true
new immutable generation
activation_state = pending_main_restart
restart_required = true
```

“No semantic persisted change” compares resulting persisted override state, not visible effective scalar alone.

---

# 11. OPTIMISTIC CONCURRENCY

GET returns:

```text
ETag: "settings-g<configured_generation>"
```

Mutation requires:

```text
If-Match: "settings-g<configured_generation>"
```

Missing:

```text
428 precondition_required
```

Mismatch/stale:

```text
412 stale_generation
```

Compare-and-swap must happen inside the same SQLite transaction that creates the new generation/audit/idempotency state.

No last-writer-wins.

No automatic retry after stale generation.

---

# 12. IDEMPOTENCY

Mutation requires:

```text
Idempotency-Key: <UUID>
```

Persist identity + canonical request hash + result.

Required behavior:

```text
same principal
+ same idempotency key
+ same canonical payload
→ return original accepted result
```

```text
same idempotency key
+ conflicting payload
→ HTTP 409 idempotency_conflict
```

Request hashing must be deterministic and independent of irrelevant JSON whitespace/member ordering.

Idempotent replay must not create another generation or duplicate audit rows.

---

# 13. AUTHORIZATION

Extend current Admin policy with distinct GLOBAL capabilities:

```text
admin.read.settings.global
admin.write.settings.global
```

Current V1 platform operator may be granted both under existing policy composition, but code must preserve separate read/write capability boundaries.

Do not authorize these operations by selecting `WEB_ADMIN_DEFAULT_SITE_ID` or any arbitrary allowed Site.

Global Settings authorization is a distinct global-scope policy decision.

---

# 14. CSRF / SESSION SECURITY

Mutation requires authenticated Admin session plus write capability plus:

```text
X-CSRF-Token
```

Use the existing canonical Admin session CSRF token and constant-time comparison boundary.

Do not accept Settings CSRF token from query string.

Existing session cookie security remains unchanged:

```text
Secure
HttpOnly
SameSite=Strict
```

Do not reuse login/logout form-urlencoded POST parsing for Settings JSON mutation.

---

# 15. READ API

Canonical endpoint:

```text
GET /admin/api/v1/settings
```

Requires:

```text
authenticated Admin session
+
admin.read.settings.global
```

Response:

```text
Content-Type: application/json
Cache-Control: no-store
ETag: "settings-g<configured_generation>"
```

Page-level fields:

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

Per-setting `SettingReadModelV1` must contain:

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

Frontend must use server-provided validation metadata rather than maintain its own hidden bound table.

---

# 16. ACTIVATION / EFFECTIVE GENERATION

Only:

```text
captive-portal.service main runtime
via run.py composition/lifecycle boundary
```

may declare a generation adopted.

Required call path:

```text
run.py / main composition owner
        ↓
SettingsActivationService
        ↓
SettingsRepository / SettingsStore
```

Admin routes, browser code, `SettingsMutationService`, and individual Admin components must not advance `effective_generation`.

## Successful startup adoption

For configured generation `G`:

```text
1. read SettingsStore head G
2. produce one immutable ResolvedSettingsSnapshot(G)
3. complete Settings V1 validation
4. use the same snapshot for V1 runtime composition
5. every enabled V1 consumer accepts configuration
   OR is explicitly disabled
6. Admin Settings/Admin consumer composition registers successfully
7. durably record adoption of G
8. only then effective_generation = G
9. only after adoption commit may the new process begin serving Admin requests
```

Successful durable event:

```text
generation_id = G
target = captive-portal.service
activation_result = adopted
effective_generation_after_attempt = G
safe_error_code = null
```

Appending the event and updating target effective generation must be atomic.

Every Settings-aware main-service startup reports adoption, even if `G` equals the previously effective generation.

---

# 17. ACTIVATION FAILURE

Stage 1 has no external activation reporter.

`activation_failed` means positive in-process durable failure attestation only.

The new process may record failure only after it:

```text
identified configured generation G
+
attempted Settings V1 adoption
+
positively determined validation/composition of G failed
+
can durably write a failure event
```

Failure event:

```text
generation_id = G
target = captive-portal.service
activation_result = failed
effective_generation_after_attempt = last adopted generation or null
safe_error_code = bounded non-secret category
```

Do not advance effective generation.

Do not rollback configured generation.

Do not infer `activation_failed` from:

- restart request;
- process disappearance;
- timeout;
- absent success event;
- missing heartbeat;
- systemd failure before Python starts;
- interpreter/import/host/resource failure before attributable reporting.

If no trustworthy runtime snapshot exists:

```text
activation_state = runtime_unavailable
```

If older runtime generation `H` is trustworthy while configured head is `G != H`:

```text
activation_state = pending_main_restart
```

---

# 18. CONSUMER STATE

Final V1 activation state values:

```text
active
pending_main_restart
activation_failed
runtime_unavailable
```

Separate per-setting consumer state:

```text
active
consumer_disabled
null
```

For disabled optional consumer after generation adoption:

```text
configured_value = X
effective_value = null
pending_value = null
activation_state = active
consumer_state = consumer_disabled
```

If generation mismatch exists:

```text
pending_value = configured_value
activation_state = pending_main_restart
```

This remains generation-mismatch semantics regardless of current consumer enablement.

Page-level:

```text
effective_generation == configured_generation
```

is valid while individual disabled settings have:

```text
effective_value = null
consumer_state = consumer_disabled
```

---

# 19. ADMIN PAGE / UX

Add:

```text
GET /admin/settings
```

This is a GLOBAL page.

Add `Settings` to the existing Admin navigation only when `WEB_ADMIN_SETTINGS_ENABLED` makes the Settings feature available under current configuration.

Stage 1 UI has exactly two setting groups:

```text
Pagination / Presentation
Refresh Cadence
```

Primary labels are human-readable.

Technical keys may be displayed secondarily for diagnostics/advanced context.

For each setting display enough state to distinguish:

```text
configured value
effective value
persisted override
deployment/base source/value
pending value
consumer state
apply requirement
```

Required operator actions:

```text
set override
clear override / use deployment value
save atomic batch
```

UX wording must not claim activation after Save.

After successful changed Save show meaning equivalent to:

```text
Persisted successfully.
Pending captive-portal.service restart.
```

There is no restart button.

There is no systemd control.

## Stale form

On `412 stale_generation`:

- do not auto-retry;
- reload current Settings read model;
- show stale/conflict notice;
- require operator review and explicit resubmission.

## Store unavailable

Show a bounded Settings-unavailable state without leaking DB errors/paths beyond safe configured UI metadata.

---

# 20. ERROR CONTRACT

Canonical envelope:

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

Required classes:

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

Never return:

- stack traces;
- raw SQLite errors;
- environment dumps;
- secret values;
- authorization headers/tokens.

---

# 21. AUDIT

Every accepted changed generation must have durable mutation audit transactionally linked to generation creation.

Activation events are separate durable records.

No audit/history browser UI is implemented.

No rollback UI is implemented.

No automatic pruning is required for Stage 1.

Existing immutable generations must never be edited in place.

---

# 22. REQUIRED TEST COVERAGE — CODER NARROW TESTS ONLY

Coder is authorized only for focused tests covering this TASK.

Required tests include:

## Registry

- exactly 12 editable keys;
- correct integer bounds;
- unknown key denied;
- no secret / Site / feature-enable key admitted.

## Repository/bootstrap

- new DB creates generation 0 once;
- repeated initialization is idempotent;
- generation 0 immutable/root;
- initial effective generation null;
- first mutation parent 0;
- generations immutable;
- transaction rollback on persistence error.

## Resolver

- override > explicit environment > repository default;
- clear override falls back correctly;
- base_source accurately reports env vs repository default.

## Validation

- primitive min/max;
- wrong type;
- disabled consumer still validates;
- affected existing Admin validators invoked;
- one invalid field rejects entire batch.

## Mutation

- changed request → 201/new generation;
- semantic no-op → 200/no generation;
- duplicate key rejected;
- unknown key rejected;
- stale If-Match → 412;
- missing If-Match → 428;
- idempotent replay returns original result;
- idempotency conflict → 409;
- malformed/wrong content type/body too large handled;
- max changes enforced;
- CSRF/auth/write capability enforced.

## Read API

- ETag correct;
- configured/effective/pending separation;
- base metadata;
- validation metadata;
- no-store;
- global scope only.

## Activation

- successful adoption advances effective generation only after durable event;
- same generation can be adopted again by new process startup without new configured generation;
- durable adoption write failure does not claim active;
- positive config-adoption failure records `failed`;
- silence is not turned into activation_failed;
- disabled consumer semantics exactly match A4.

## UI

- Settings nav/page appears only when feature available;
- two groups and 12 controls;
- server metadata drives validation presentation;
- Save uses JSON endpoint with CSRF/If-Match/Idempotency-Key;
- changed Save shows pending restart;
- no restart/systemd control exists;
- stale generation requires reload/review, no automatic replay;
- clear override UX is distinguishable from setting a scalar.

---

# 23. CODER TEST COMMAND BOUNDARY

Coder may run only the focused Stage 1 tests it adds/modifies plus directly affected existing Admin/config tests necessary to prove compatibility.

Minimum expected focused command:

```bash
pytest -q tests/settings_control tests/admin_web/test_settings_routes.py tests/admin_web/test_settings_ui.py
```

If `tests/admin_web/conftest.py`, current Admin config, policy, route, or UI integration causes directly affected existing tests to require execution, Coder may additionally run only those exact directly affected files and list them in handoff.

Coder MUST NOT run broad/full repository suites merely to satisfy this TASK.

Full regression/integration/runtime/production validation belongs to Owner / Technical Developer / Tech Lead / independent QA gate.

---

# 24. DOCUMENTATION CHANGES

Coder may update only the current Settings/Admin configuration documentation necessary to describe the implemented Stage 1 contract.

Before implementation authorization, Tech Lead must name the exact documentation files if documentation is to be modified.

Coder must not create competing architecture documents or rewrite the roadmap.

---

# 25. EXPLICIT FORBIDDEN CHANGES

Do NOT implement or modify:

```text
CAPPORT settings ownership
Omada URL/ID/client credentials mutation
Omada secret storage
Admin username/password/password hash mutation
Admin source-network allowlist mutation
Admin Site allowlist/default Site mutation
Admin HTTPS/security-boundary mutation
session/login/CSRF security-limit mutation
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
webhook secrets/auth configuration
bearer tokens
TLS/private-key paths
database/log paths as editable values
bind addresses/ports as editable values
NIC/SPAN/RSPAN
auxiliary direct-env integration
generated EnvironmentFile
systemctl/systemd D-Bus/sudo service control
restart/reload button
hot reload
automatic rollback
Settings history browser
rollback UI
generic environment editor
arbitrary setting search/edit
unrelated refactors
```

No new background/auxiliary service may be introduced.

---

# 26. PRODUCTION ACTIVATION GATE

Coder does not perform production activation.

After implementation is accepted through code review/testing, production enablement remains an explicit separate operator/Tech Lead gate.

Because:

```text
WEB_ADMIN_SETTINGS_ENABLED default = false
```

merge/deploy must not silently expose mutation unless deployment explicitly enables it.

No production DB creation, config change or service restart is authorized by this TASK draft.

---

# 27. CODER HANDOFF REQUIREMENTS

Coder handoff must contain:

1. implementation commit SHA;
2. exact baseline SHA;
3. exact new files;
4. exact modified files;
5. concise mapping from architecture requirement to implementation;
6. SQLite schema summary;
7. confirmation generation 0 behavior;
8. confirmation resolver precedence;
9. confirmation all 12 and only 12 keys are writable;
10. confirmation no systemd/restart authority exists;
11. focused test commands executed;
12. exact test results;
13. any directly affected existing tests executed;
14. known limitations;
15. explicit statement of whether any architecture ambiguity was encountered.

If an architecture ambiguity is encountered:

```text
STOP
do not invent behavior
return the ambiguity to Technical Developer Settings / Tech Lead
```

---

# 28. ACCEPTANCE CRITERIA

Stage 1 implementation is acceptable only if all are true:

- baseline is correct;
- Settings disabled by default;
- store bootstraps immutable generation 0;
- resolver precedence is exactly override > env > repository default;
- exactly 12 keys are editable;
- mutation is GLOBAL-only;
- mutation is atomic;
- existing semantic validators remain authoritative;
- configured/effective/pending are distinct;
- runtime/main process alone advances effective generation;
- activation commit occurs before Admin requests are served by the new runtime;
- activation_failed requires positive in-process attestation;
- disabled consumer has `effective_value = null` and separate `consumer_state`;
- ETag/If-Match prevents stale overwrite;
- idempotency prevents duplicate generation creation;
- durable mutation audit exists;
- durable activation events exist;
- Admin read/write capabilities are distinct;
- CSRF applies to JSON mutation;
- Settings page/API do not leak secrets/raw environment/DB errors;
- Save never claims immediate activation;
- no restart/systemd control exists;
- no scope outside Stage 1 was modified;
- focused tests pass;
- Coder handoff is complete.

---

# 29. CURRENT AUTHORIZATION STATE

```text
ARCHITECTURE
= FINAL / ACCEPTED

THIS IMPLEMENTATION TASK
= DRAFT FOR TECH LEAD IMPLEMENTATION-CONTRACT REVIEW

CODER
= HOLD

IMPLEMENTATION
= NOT AUTHORIZED

PRODUCTION
= NO CHANGE

SYSTEMD
= NO ACTION
```

Next:

```text
Tech Lead reviews this exact implementation contract
→ PASS or bounded revision
→ only then Coder receives implementation authorization
```
