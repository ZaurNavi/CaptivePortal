# CAPTIVPORTAL ADMIN SETTINGS — STAGE 3
## TECH LEAD ARCHITECTURE REVIEW R1

**Reviewed document:** `CAPTIVPORTAL-ADMIN-SETTINGS-OMADA-CONTROLLER-WRITABLE-NONSECRET-ARCHITECTURE-CONTRACT-v0.1`  
**Architect status:** DRAFT FOR TECH LEAD REVIEW  
**Reviewed baseline:** `main@c1167180daec9ca17d13ab44326f143122db8d5e`  
**Tree:** `278df41bfa3134b22963b41006585da35de08074`

## 1. Review disposition

```text
CORE STAGE-3 DIRECTION          = PASS
EXACT ADMISSION                 = PASS
ONE COMMON REGISTRY             = PASS
ONE COMMON SETTINGSSTORE        = PASS
SCHEMA v1 -> v2 REQUIREMENT     = PASS
PRECEDENCE                      = PASS
VALIDATION OWNERSHIP            = PASS
CLEAR-OVERRIDE SEMANTICS        = PASS
CONTROLLER MUTATION BOUNDARY    = PASS
AUTHORIZATION                   = PASS
CONFIGURED/EFFECTIVE MODEL      = PASS
SECRET BOUNDARY                 = PASS
TLS STAGE-3 DECISION            = PASS
FAIL-CLOSED NEW STARTUP         = PASS
STAGE-4 COMPATIBILITY           = PASS

OPEN P0                         = 0
OPEN P1                         = 2

ARCHITECTURE                    = HOLD FOR BOUNDED R1 FIX
CODER                           = HOLD
IMPLEMENTATION TASK             = HOLD
PRODUCTION                      = NO CHANGE
```

The architecture is structurally sound and aligned with the accepted Stage-1/Stage-2 direction. Two bounded P1 architecture gaps must be closed before FINAL / TECH LEAD ACCEPTED.

---

# 2. Source verification performed

The current `main@c116718...` was independently checked.

Confirmed current-state facts used by the contract:

```text
app/settings_control/definitions.py
- registry contains exactly 12 integer definitions;
- settings_dict_key is currently inferred from key.lower();
- environment_variable_name is currently inferred from key.

app/settings_control/repository.py
- SETTINGS_SCHEMA_VERSION = 1;
- settings_overrides is integer-only;
- mutation audit values are integer-specific;
- settings_idempotency result_response_json is physically bounded to <= 65536 bytes;
- current idempotency uniqueness has no mutation_domain.

app/settings_control/bootstrap.py
- Settings-enabled Store failure currently fails open to base settings.

app/settings_control/services.py
- one common mutation service/generation chain exists;
- idempotency replays exact stored successful response;
- successful response is serialized into settings_idempotency;
- Stage-1 change parsing is canonicalized/sorted before hash.

app/controllers/omada_config.py
- one typed injected OmadaControllerRuntimeConfig exists;
- current Controller validation semantics match the Architect inventory;
- public snapshot remains secret-free.

run.py
- Controller config/provider are constructed from the Settings-aware startup mapping;
- several Controller-dependent workers are currently STARTED before
  SettingsActivationService.adopt(...).
```

No discrepancy was found with the contract's source inventory except the two unresolved consequences below.

---

# 3. P1-01 — Controller mutation response is not bounded against durable idempotency storage

## Contract clauses involved

The draft freezes:

```text
Controller mutation request max body = 32768 bytes
OMADA_ID / OMADA_CLIENT_ID = no new semantic length bound
Controller mutation success = full Controller V2 projection
exact successful response = durable for idempotent replay
```

Current accepted SettingsStore physically enforces:

```text
settings_idempotency.result_response_json
<= 65536 bytes
```

The draft does not alter or replace that bound.

## Why this is a blocker

Stage-3 Controller V2 can repeat one admitted string in multiple response fields, for example:

```text
persisted_override_value
configured_value
pending_value
effective_value
```

A syntactically valid request body below 32768 bytes can therefore generate a successful response larger than 65536 bytes.

This is not theoretical only for the new HTTP input. Existing environment-derived Controller values also have no Stage-3 semantic length bound, so the effective side can independently enlarge the mutation response.

Current common mutation semantics persist the exact successful response for idempotent replay. If the response exceeds the store bound, the transaction cannot truthfully satisfy both:

```text
mutation accepted
+
exact successful response durably stored
```

The architecture therefore currently has no deterministic outcome for an otherwise valid Controller mutation whose replay response exceeds the existing storage bound.

## Required Architect fix

Freeze exactly one coherent policy.

Acceptable architectural directions include, but are not limited to:

### Option A — keep full V2 mutation response
Then schema v2 MUST explicitly define a safe new durable idempotency response-size policy sufficient for all Stage-3 accepted Controller values.

The policy must state:
- physical storage bound or absence of the old 65536 bound;
- migration behavior for the existing constraint/table;
- maximum accepted Controller value/request size relationship;
- failure behavior if the durable replay response still cannot be stored.

### Option B — keep bounded idempotency storage
Then Controller mutation success MUST become a bounded mutation result rather than the full value-repeating V2 projection, and the UI re-GETs the Controller read model after success.

The exact response schema must be frozen.

### Option C — introduce explicit transport/storage length bounds
Only if the Architect intentionally chooses a technical Settings-control-plane bound and defines it as such, not as an invented Omada semantic restriction.

Until one policy is frozen:

```text
P1-01 = OPEN
```

---

# 4. P1-02 — Durable adoption boundary vs pre-adoption Controller I/O is not frozen

## Contract clauses involved

The draft freezes:

```text
effective generation does not advance before durable adoption
Controller is a required generation consumer
successful adoption proves exact snapshot G/provider composition
```

and gives the target startup chain ending with:

```text
SettingsActivationService adopts exact generation G
→ effective_generation = G
→ only then serve requests
```

However current `run.py` starts multiple Controller-dependent workers before:

```text
settings_bootstrap.activation_service.adopt(...)
```

Current pre-adoption starts include, among others:

```text
pending_session_cleaner.start()
observation_foundation.start()
current_state_runtime.start()
visitor_snapshot_collector.start()
visitor_registry.start()
visit_lifecycle.start_reconciliation(...)
```

Some of these paths can use the shared Omada provider and can perform external Omada/OAuth activity.

## Why this is a blocker

After Stage 3, generation G may contain a new:

```text
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
```

On restart, the shared provider is constructed from G before durable adoption.

If Controller-dependent workers are allowed to run before `adopt(G)` succeeds, external Controller activity can occur using G while durable Settings state still says:

```text
effective_generation = H
```

and, if adoption later fails, G was never durably effective even though it was already used operationally.

That leaves two competing meanings of "effective":

```text
durably adopted Settings generation
vs
configuration already used by running background consumers
```

This must be resolved at architecture level because Stage 3 explicitly makes Controller a required generation consumer.

## Required Architect fix

Freeze one exact startup rule.

Preferred direction:

```text
compose/validate all required runtime consumers
DO NOT START Controller-dependent external-I/O workers yet
durably adopt generation G
only after successful adoption:
    start Controller-dependent workers
    then serve HTTP
```

If the Architect intentionally permits pre-adoption worker I/O, the contract must explicitly define:
- why this does not violate `effective_generation`;
- what happens if durable adoption fails after Controller I/O has occurred;
- which consumers may start before adoption;
- which may not.

The implementation task cannot infer this.

Until this sequencing is frozen:

```text
P1-02 = OPEN
```

---

# 5. Accepted architecture areas

No return is required for the following decisions:

```text
exact writable keys =
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID

OMADA_CLIENT_SECRET =
OUT OF STAGE 3

VERIFY_SSL =
READ-ONLY

scope =
GLOBAL / installation-level

registry =
one common registry, 15 definitions

store =
one common SettingsStore

schema evolution =
v1 -> v2 required

precedence =
persisted_override > explicit process environment > repository default

validation =
same canonical Controller semantics as runtime

clear_override =
remove persisted ownership, expose/validate lower source

mutation endpoint =
POST /admin/api/v1/settings/controller/generations

mutation engine =
common SettingsMutationService / common generation chain

write capability =
admin.write.settings.controller

read endpoint =
GET /admin/api/v1/settings/controller

read schema =
admin.settings.controller.v2

activation target =
captive-portal.service

hot reconnect =
NO

Admin systemd authority =
NO

save-time connection test =
NO

enabled new-startup Store failure =
FAIL CLOSED

running adopted process + later Store outage =
runtime may continue; effective-only Controller read may remain available

automatic rollback =
NO

Site-scoped mutation =
NO

multi-controller =
NO
```

---

# 6. Binding notes for the Architect return

The revised contract should also make these consequences explicit while closing P1-01/P1-02:

```text
A. Existing Stage-1 idempotency rows migrate with:
   mutation_domain = general

B. Existing Stage-1 audit rows, if schema v2 adds these columns, have deterministic:
   setting_domain = general
   value_type = integer

C. Controller GET and successful Controller mutation responses, when Store is available,
   use the common global ETag:
   "settings-g<configured_generation>"

D. Store-unavailable effective-only read MUST NOT emit cached configured/persisted values
   as if current. Configured/persisted/pending fields are null as already stated.

E. Raw OMADA_CLIENT_SECRET remains absent from every new typed/audit/idempotency path.
```

A/B/C/D/E are not additional scope expansion; they close deterministic migration/API behavior around decisions already made in the draft.

---

# 7. Required return

Architect should return:

```text
CAPTIVPORTAL-ADMIN-SETTINGS-OMADA-CONTROLLER-WRITABLE-NONSECRET-ARCHITECTURE-CONTRACT-v0.1-R1
```

or a clearly revised v0.1 document with:

```text
P1-01 CLOSED
P1-02 CLOSED

OPEN P0 = 0
OPEN P1 = 0

READY FOR TECH LEAD RE-REVIEW = YES
```

No Coder TASK yet.
No implementation.
No database action.
No systemd action.
No production change.

---

# 8. Current gate

```text
STAGE 3 ARCHITECTURE REVIEW R1

SOURCE BASELINE VERIFIED      = PASS
CORE ARCHITECTURE             = PASS

OPEN P0                       = 0
OPEN P1                       = 2

P1-01 IDEMPOTENCY SIZE        = OPEN
P1-02 ADOPTION/I-O SEQUENCING = OPEN

ARCHITECTURE FINAL            = HOLD
TECHNICAL DEVELOPER SETTINGS  = HOLD
CODER                         = HOLD
IMPLEMENTATION                = NO
PRODUCTION                    = NO CHANGE

ARCHITECT                     = GO FOR BOUNDED R1 FIX ONLY
```
