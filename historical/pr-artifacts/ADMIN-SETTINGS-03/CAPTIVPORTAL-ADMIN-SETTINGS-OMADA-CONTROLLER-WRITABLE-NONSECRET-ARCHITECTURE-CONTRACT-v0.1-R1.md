# CAPTIVPORTAL-ADMIN-SETTINGS-OMADA-CONTROLLER-WRITABLE-NONSECRET-ARCHITECTURE-CONTRACT-v0.1-R1

**Project:** CaptivPortal  
**Stage:** Stage 3 — Omada Controller: Writable Non-Secret Configuration  
**Baseline:** `main@c1167180daec9ca17d13ab44326f143122db8d5e`  
**TREE:** `278df41bfa3134b22963b41006585da35de08074`  
**Status:** **DRAFT FOR TECH LEAD RE-REVIEW**

This R1 is a bounded normative revision of v0.1.

All Stage-3 decisions previously marked PASS by Tech Lead remain unchanged.

R1 changes only:

```text
P1-01 — durable idempotency response-size contract
P1-02 — durable adoption / Controller-I/O sequencing
```

and incorporates Tech Lead binding notes A–E.

---

# R1-01 — P1-01 CLOSED
## Bounded Controller mutation receipt

## Decision

Stage 3 chooses:

```text
OPTION B
```

Controller mutation success MUST NOT persist or return the complete value-repeating Controller V2 read projection.

Instead:

```text
POST /admin/api/v1/settings/controller/generations
        ↓
bounded mutation receipt
        ↓
UI performs GET /admin/api/v1/settings/controller
        ↓
full Controller V2 read model
```

This preserves the existing bounded durable idempotency storage contract.

---

# R1-02 — Idempotency storage bound

The existing physical bound remains:

```text
settings_idempotency.result_response_json
<= 65536 bytes
```

Stage 3 does not enlarge or remove it.

Schema v2 migration may rebuild/extend the idempotency table to introduce:

```text
mutation_domain
```

but the durable response-size limit remains:

```text
65536 bytes
```

Existing successful Stage-1 idempotency responses remain valid and are migrated without semantic rewriting.

---

# R1-03 — Controller request-size contract remains unchanged

Controller mutation request body remains bounded by:

```text
32768 bytes
```

Maximum Controller changes per request remains:

```text
3
```

No new Omada semantic maximum length is imposed on:

```text
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
```

merely to satisfy idempotency storage.

The mutation response is instead designed so its size is independent of Controller scalar length.

---

# R1-04 — Exact Controller mutation success schema

Canonical successful response API version:

```text
admin.settings.controller.mutation.v1
```

Changed mutation:

```json
{
  "api_version": "admin.settings.controller.mutation.v1",
  "request_id": "<uuid>",
  "scope": {
    "type": "global"
  },
  "resource": {
    "type": "omada_controller",
    "scope": "installation"
  },
  "changed": true,
  "changed_keys": [
    "OMADA_URL"
  ],
  "configured_generation": 12,
  "effective_generation": 11,
  "activation_state": "pending_main_restart",
  "restart_required": true
}
```

Canonical HTTP status:

```text
201 Created
```

No-op mutation:

```json
{
  "api_version": "admin.settings.controller.mutation.v1",
  "request_id": "<uuid>",
  "scope": {
    "type": "global"
  },
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

Canonical HTTP status:

```text
200 OK
```

---

# R1-05 — Mutation receipt contains no Controller scalar values

The Controller mutation receipt MUST NOT contain:

```text
persisted_override_value

configured_value

configured_source

effective_value

effective_source

pending_value

pending_source

Controller URL

Controller ID value

Client/Application ID value

Client Secret data
```

Therefore its maximum size is structurally bounded independently of admitted string lengths.

`changed_keys` may contain only members of the fixed three-key allowlist:

```text
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
```

and therefore cannot create an unbounded receipt.

---

# R1-06 — Successful mutation requires durable replay persistence

The following remain one atomic SQLite transaction:

```text
generation creation
+
complete override snapshot
+
mutation audit
+
idempotency response record
```

A Controller mutation is not successful until the bounded mutation receipt has been durably stored for replay.

Therefore:

```text
generation committed
but
idempotency receipt not committed
```

is forbidden.

---

# R1-07 — Defensive oversized-result failure

Although the Stage-3 receipt is structurally far below 65536 bytes, the persistence boundary MUST still enforce the durable limit.

If due to implementation defect or unexpected serialization behavior the exact replay receipt cannot be durably stored within the repository limit:

```text
entire mutation transaction rolls back
```

Result:

```text
HTTP 500 internal_error
```

and:

```text
NO new generation
NO override change
NO mutation audit
NO idempotency success record
```

It MUST NOT downgrade to:

```text
mutation committed but replay unavailable
```

---

# R1-08 — Idempotent replay

Existing Stage-1 ordering remains:

```text
lookup existing idempotency identity
        ↓
same payload hash
        ↓
return exact original mutation receipt
```

Successful replay performs:

```text
NO current-head CAS
NO new validation
NO new generation
NO new audit
NO Settings mutation
```

Same identity with different canonical payload remains:

```text
409 idempotency_conflict
```

---

# R1-09 — UI MUST re-GET after every successful Controller mutation

After any successful:

```text
200
or
201
```

from:

```text
POST /admin/api/v1/settings/controller/generations
```

the browser MUST perform:

```text
GET /admin/api/v1/settings/controller
```

before presenting the authoritative configured/effective field state.

The mutation receipt is:

```text
commit acknowledgement
```

not:

```text
Controller read model
```

This is also required after an idempotent replay because the exact replay receipt intentionally reflects the original successful mutation result, while current runtime activation state may since have changed.

---

# R1-10 — Common global ETag

When SettingsStore is available:

```text
GET /admin/api/v1/settings/controller
```

returns:

```text
ETag: "settings-g<configured_generation>"
```

Successful Controller mutation returns the same global configured-head ETag corresponding to its result generation:

```text
ETag: "settings-g<configured_generation>"
```

There is no Controller-local ETag.

There is no Controller-local generation counter.

---

# R1-11 — Existing idempotency migration

During schema v1 → v2 migration, all existing Stage-1 idempotency records receive deterministically:

```text
mutation_domain = general
```

New Controller mutation records receive:

```text
mutation_domain = controller
```

Canonical uniqueness becomes logically:

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

No existing successful response body is semantically rewritten.

---

# R1-12 — Existing mutation audit migration

If schema v2 materializes:

```text
setting_domain
value_type
```

in mutation-audit rows, all pre-Stage-3 rows deterministically migrate as:

```text
setting_domain = general
value_type = integer
```

New Controller rows use:

```text
setting_domain = controller
value_type = string
```

No historical generation/audit meaning changes.

---

# R1-13 — P1-01 final disposition

```text
P1-01 IDEMPOTENCY SIZE = CLOSED

POLICY =
bounded mutation receipt

FULL CONTROLLER V2 MODEL IN MUTATION RESPONSE =
NO

UI RE-GET AFTER SUCCESS =
MANDATORY

DURABLE RESPONSE LIMIT =
65536 bytes

NEW OMADA SEMANTIC STRING LENGTH LIMIT =
NO

MUTATION WITHOUT DURABLE IDEMPOTENCY RECEIPT =
FORBIDDEN
```

---

# R1-14 — P1-02 CLOSED
## Durable adoption precedes Controller external I/O

## Decision

After Stage 3:

```text
NO Controller/OAuth external I/O
using configured generation G
is permitted before G is durably adopted.
```

This is the canonical meaning of:

```text
effective_generation = G
```

for Controller configuration.

---

# R1-15 — Three startup phases

The main startup lifecycle is divided into three normative phases.

```text
PHASE A
RESOLVE / VALIDATE / COMPOSE

PHASE B
DURABLE SETTINGS ADOPTION

PHASE C
START RUNTIME I/O / SERVE
```

They MUST occur in that order.

---

# R1-16 — PHASE A
## Resolve / validate / compose

Allowed before durable adoption:

```text
capture artifact identity

get_settings()

capture explicit process-environment provenance

open/migrate/validate SettingsStore

read configured generation G

resolve exact immutable Settings snapshot G

validate full Settings snapshot

validate canonical Controller configuration

construct OmadaControllerRuntimeConfig(G)

construct shared OmadaProvider from G

construct safe OmadaControllerPublicConfigSnapshot(G)

construct Flask application

construct runtime/service objects

construct repositories/read services

perform bounded local configuration validation

register blueprints/routes

compose Admin runtime

perform Settings activation readiness checks
```

---

# R1-17 — What Phase A MUST NOT do

Before durable adoption of G:

```text
NO Controller OAuth request

NO Omada token acquisition

NO Omada HTTP request

NO background worker call through shared OmadaProvider

NO Controller-dependent periodic loop start

NO authorization request can reach Omada

NO HTTP server accepts product requests
```

Provider construction itself remains network-free.

---

# R1-18 — Exact Controller-dependent workers gated by adoption

At the current Stage-3 baseline, the following runtime starts MUST occur only after successful durable adoption:

```text
pending_session_cleaner.start()

observation_foundation.start()

current_state_runtime.start()

visitor_snapshot_collector.start()
```

Reason:

their runtime paths own or can own work using the shared Omada provider and therefore can produce Controller/OAuth external activity.

This list is an explicit minimum for the accepted baseline.

---

# R1-19 — Future Controller-dependent consumers

Permanent rule:

```text
any future runtime whose start/scheduling path
can invoke the shared OmadaProvider,
request/refresh an Omada token,
or otherwise perform Controller external I/O
MUST be post-adoption
```

The architecture is therefore capability-based, not dependent only on the four current class names.

---

# R1-20 — Non-Controller local workers

A component MAY start before Settings adoption only when all of the following are proven:

```text
it has no OmadaProvider access

it cannot trigger Omada/OAuth I/O

it cannot expose HTTP product traffic

its start does not cause external use
of the candidate Controller configuration G
```

Current examples that are not Controller consumers may retain their existing ordering if the implementation contract proves those conditions.

Examples include local persistence/journal reconciliation paths such as:

```text
Visitor Registry local journal processing

Visit Lifecycle local reconciliation
```

provided their concrete Stage-3 start path has no shared-provider dependency.

The implementation TASK must classify every pre-adoption `.start()`/scheduler call against this rule.

No unclassified pre-adoption runtime start is permitted.

---

# R1-21 — Admin projection may be composed before adoption

The safe Controller Admin projection may be composed before adoption because it performs:

```text
NO Omada network I/O
NO OAuth I/O
NO provider operation
```

However:

```text
HTTP serving has not begun
```

so no browser can consume it before adoption.

Projection failure remains:

```text
Admin Controller read-surface failure
```

and not a required Controller consumer failure.

The existing rule remains:

```text
valid provider/config
+
Controller Admin projection failure
→ core runtime may still adopt
```

---

# R1-22 — PHASE B
## Durable Settings adoption

Only after all required configuration/runtime composition checks have succeeded:

```text
SettingsActivationService.adopt(G)
```

is executed.

Successful durable transaction:

```text
append activation_result = adopted
+
settings_target_state.effective_generation = G
```

Only after that transaction commits is:

```text
G = effective generation
```

for Controller runtime configuration.

---

# R1-23 — Meaning of successful adoption

For Stage 3 Controller configuration, successful adoption proves:

```text
exact Settings snapshot G was resolved

canonical Controller configuration from G was valid

OmadaControllerRuntimeConfig(G) was constructed

shared OmadaProvider accepted that exact config

required runtime composition reached accepted pre-start readiness

durable Settings adoption of G committed
```

It does NOT prove:

```text
Controller reachable

OAuth valid

credentials accepted remotely

token acquisition successful

network operational

background workers successfully remain alive forever
```

---

# R1-24 — No pre-adoption external use

The following state is architecturally forbidden:

```text
effective_generation = H
while
a background Controller consumer has already performed Omada/OAuth I/O
using candidate generation G
```

where:

```text
G != H
```

This closes the competing meanings of "effective."

---

# R1-25 — Adoption failure before Controller I/O

If `adopt(G)` fails:

```text
NO Controller-dependent worker has been started

NO HTTP server is serving

NO Omada/OAuth external I/O has occurred using G
```

Startup aborts.

`effective_generation` remains the last durably adopted generation:

```text
H
```

or null if none existed.

No automatic rollback generation is created.

---

# R1-26 — Positive adoption failure attestation

Existing semantics remain.

When the new process positively determines a Settings/Controller adoption failure and can durably report it:

```text
activation_result = failed
configured generation remains G
effective generation remains H
```

No external reporter is added.

Silence or process death is still not automatically:

```text
activation_failed
```

---

# R1-27 — PHASE C
## Start external-I/O runtime

Only after successful durable adoption of G may the process start Controller-dependent workers:

```text
pending_session_cleaner.start()

observation_foundation.start()

current_state_runtime.start()

visitor_snapshot_collector.start()
```

and any future Controller-dependent worker.

After post-adoption worker-start attempts complete according to their existing operational semantics:

```text
HTTP serving may begin
```

---

# R1-28 — Worker failure after adoption

A Controller-dependent worker may fail to start after G has already been durably adopted.

That does NOT retroactively make G non-effective.

Canonical meaning:

```text
Settings adoption succeeded
+
operational component startup failed
```

The worker/component follows its existing fail-open/degraded/unavailable semantics.

No:

```text
effective_generation rollback

automatic activation_failed rewrite

automatic Settings generation rollback
```

occurs.

Reason:

Settings adoption proves that the runtime accepted the configured snapshot.

It does not promise every optional/background operational subsystem starts successfully.

---

# R1-29 — HTTP requests cannot race adoption

The Flask/WSGI server MUST NOT begin accepting product/Admin/guest HTTP traffic before:

```text
SettingsActivationService.adopt(G)
```

has committed successfully.

Therefore guest Auth cannot be the first consumer to perform Omada I/O using G before durable adoption.

---

# R1-30 — Startup sequence after R1

Canonical Stage-3 ordering:

```text
1. capture artifact identity

2. get_settings()

3. capture explicit environment provenance

4. bootstrap/migrate/read SettingsStore

5. resolve immutable configured generation G

6. validate complete Settings snapshot G

7. build canonical OmadaControllerRuntimeConfig(G)

8. construct shared OmadaProvider — NO NETWORK

9. build safe effective Controller public snapshot(G)

10. compose Flask and all runtime components — NO Controller worker start

11. compose Admin runtime/read surfaces

12. establish required pre-start readiness

13. durably adopt Settings generation G

14. start Controller-dependent workers

15. start remaining post-adoption runtime workers as required

16. begin HTTP serving
```

This ordering supersedes the current baseline ordering where several workers are started before `SettingsActivationService.adopt(...)`.

---

# R1-31 — No connection check added

Moving worker starts after adoption MUST NOT be interpreted as permission to add a Controller verification step.

Still forbidden before/during Settings adoption:

```text
Test Connection

OAuth credential check

token request

/sites probe

health request

DNS probe

TLS handshake for validation
```

Activation remains configuration/runtime adoption.

Not remote Controller validation.

---

# R1-32 — P1-02 final disposition

```text
P1-02 ADOPTION / I-O SEQUENCING = CLOSED

PRE-ADOPTION CONTROLLER/OAUTH I/O =
FORBIDDEN

PROVIDER CONSTRUCTION BEFORE ADOPTION =
ALLOWED, NETWORK-FREE

CONTROLLER-DEPENDENT WORKER START =
AFTER DURABLE ADOPTION ONLY

HTTP SERVING =
AFTER DURABLE ADOPTION ONLY

POST-ADOPTION WORKER START FAILURE =
OPERATIONAL FAILURE;
DOES NOT ROLLBACK EFFECTIVE GENERATION
```

---

# R1-33 — Store-unavailable effective-only read clarification

The previously accepted Store-outage behavior remains.

If the process has already successfully adopted its runtime and the SettingsStore later becomes unavailable:

```text
effective Controller snapshot remains trustworthy
```

Controller GET may return effective-only state.

It MUST NOT emit cached or previously retrieved configured/persisted state as though it were current.

Canonical unavailable fields:

```text
configured_generation = null

configured_value = null

configured_source = null

persisted_override_value = null

pending_value = null

pending_source = null

activation_state = null

restart_required = null
```

The immutable currently adopted fields may remain:

```text
effective_generation

effective_value

effective_source

client_secret effective_presence
```

Mutation is unavailable.

---

# R1-34 — Secret boundary through new Stage-3 paths

Raw:

```text
OMADA_CLIENT_SECRET
```

remains prohibited from every Stage-3 addition, including:

```text
typed Settings override rows

typed mutation audit

idempotency request identity

idempotency response receipt

mutation response

Controller V2 configured projection

Controller effective projection

HTML

JavaScript

logs

activation events

error details
```

No prefix/suffix/length/hash/fingerprint representation is introduced.

Presence-only Stage-2 semantics remain unchanged.

---

# R1-35 — Accepted v0.1 decisions remain binding

This R1 does NOT reopen the Tech Lead PASS decisions.

They remain:

```text
writable keys =
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
one common registry
15 definitions

store =
one common SettingsStore

schema =
v1 → v2

precedence =
persisted_override
> explicit process environment
> repository default

validation =
one canonical Controller semantic owner

clear_override =
remove persisted ownership
then resolve + validate lower source

Controller mutation endpoint =
POST /admin/api/v1/settings/controller/generations

mutation engine =
common Settings mutation engine
common global generation chain

read capability =
admin.read.settings.controller

write capability =
admin.write.settings.controller

read endpoint =
GET /admin/api/v1/settings/controller

read model =
admin.settings.controller.v2

activation target =
captive-portal.service

hot reconnect =
NO

hot provider recreation =
NO

Admin systemd authority =
NO

restart button =
NO

save-time connection test =
NO

new-startup Store failure with Settings enabled =
FAIL CLOSED

running adopted runtime + later Store outage =
runtime may continue;
effective-only Controller read may remain available

automatic rollback =
NO

Site-scoped mutation =
NO

multi-controller =
NO
```

---

# R1-36 — Additional testable invariants

The Stage-3 implementation TASK must include evidence for:

```text
R1-I01 Controller mutation receipt contains no Controller scalar values.

R1-I02 mutation receipt serialization is durably <= 65536 bytes.

R1-I03 inability to persist replay receipt rolls back the entire mutation.

R1-I04 successful Controller mutation always has a durable idempotency record.

R1-I05 UI re-GETs Controller V2 after every successful Controller mutation.

R1-I06 General idempotency history migrates with mutation_domain=general.

R1-I07 Controller idempotency uses mutation_domain=controller.

R1-I08 pre-Stage-3 audit rows deterministically remain
       domain=general / value_type=integer.

R1-I09 Controller GET and successful mutation expose common global generation ETag.

R1-I10 Store-unavailable effective-only read exposes no cached configured/persisted values.

R1-I11 raw OMADA_CLIENT_SECRET appears in none of the new persistence/API/audit paths.

R1-I12 no Controller-dependent worker performs Omada/OAuth I/O before adopt(G).

R1-I13 shared OmadaProvider may be constructed before adoption
       but performs zero network I/O during construction.

R1-I14 pending_session_cleaner is not started before adoption.

R1-I15 observation_foundation is not started before adoption.

R1-I16 current_state_runtime is not started before adoption.

R1-I17 visitor_snapshot_collector is not started before adoption.

R1-I18 HTTP serving cannot begin before adoption.

R1-I19 adoption failure causes zero Controller external use of candidate G.

R1-I20 post-adoption worker-start failure does not roll back effective generation.

R1-I21 no live Controller/Test Connection probe is introduced by the sequencing change.
```

---

# R1-37 — OPEN ARCHITECTURE QUESTIONS

```text
OPEN P0 = 0
OPEN P1 = 0
```

Specifically:

```text
P1-01 IDEMPOTENCY SIZE
= CLOSED

P1-02 ADOPTION / I-O SEQUENCING
= CLOSED
```

---

# R1-38 — FINAL R1 DISPOSITION

```text
CAPTIVPORTAL ADMIN SETTINGS — STAGE 3
ARCHITECTURE CONTRACT v0.1-R1

CORE ARCHITECTURE =
UNCHANGED / PASS AREAS PRESERVED

P1-01 =
CLOSED

P1-02 =
CLOSED

OPEN P0 =
0

OPEN P1 =
0

ARCHITECTURE STATUS =
DRAFT FOR TECH LEAD RE-REVIEW

READY FOR TECH LEAD RE-REVIEW =
YES
```

Current gate:

```text
TECHNICAL DEVELOPER SETTINGS =
HOLD

CODER =
HOLD

IMPLEMENTATION TASK =
HOLD

IMPLEMENTATION =
NO

DATABASE ACTION =
NO

SYSTEMD ACTION =
NO

PRODUCTION CHANGE =
NO
```

Next permitted action:

```text
Tech Lead
→ bounded R1 re-review

if PASS:
→ Architecture FINAL / TECH LEAD ACCEPTED
→ Technical Developer Settings prepares exact Stage-3 implementation TASK

until then:
→ Coder remains HOLD
```