# TASK-STARTUP-AVAILABILITY-01-DRAFT

## CaptivPortal Core HTTP / Authorization Readiness Isolation

**Project:** CaptivPortal  
**Owner trigger:** production cold-start incident during INFRA CHANGE-B  
**Prepared:** 2026-09-14  
**Status:** `DRAFT — FOR TECH LEAD REVIEW`  
**Execution:** `PLANNING / ARCHITECTURE ONLY`  
**Implementation-ready:** `NO`  
**Coder:** `HOLD`  
**Production change:** `NOT AUTHORIZED`

---

# 0. Architect Verdict

```text
INCIDENT =
SELF-RECOVERED

CURRENT PRODUCTION =
HEALTHY

EMERGENCY CHANGE =
NOT REQUIRED

ARCHITECTURAL SIGNIFICANCE =
HIGH

CLASSIFICATION =
STARTUP AVAILABILITY DEFECT / ARCHITECTURAL DEBT

EXPECTED BY CURRENT STARTUP SEQUENCING =
YES

ACCEPTABLE BEHAVIOR =
NO
```

The incident is not treated as proof that SQLite itself is defective.

The demonstrated defect is broader:

```text
optional / read-side startup work
can execute synchronously
before the production HTTP listener exists
```

Therefore:

```text
systemd process ACTIVE
!=
HTTP listener READY
!=
Authorization READY
```

This weakens the existing fail-open/failure-isolation architecture specifically during cold start.

---

# 1. Production Incident Evidence

Owner/Infrastructure evidence:

```text
captive-portal.service active:
~16:05

Web application created:
16:13:19

HTTP server bind:
16:24:33

Running on 127.0.0.1:8088:
16:24:34
```

Observed outage:

```text
Public Captive Portal =
502

Admin Web =
502

NGINX/Hestia =
healthy

configured upstream =
127.0.0.1:8088
```

After bind:

```text
Portal =
normal

Admin =
normal

/capport/api =
HTTP 200

real client authorization =
resumed immediately
```

No manual restart/recovery was required.

---

# 2. Storage / Kernel Evidence

During the unavailable interval:

```text
captive-portal process =
D-state / uninterruptible I/O wait

kernel wait =
wait_on_page_bit_common

blocking file =
/opt/CaptivePortal/data/observations.sqlite3

DB approximate size =
~448 MiB
```

Observed synchronous path:

```text
pread64
→ ext4_file_read_iter
→ filemap_read
→ wait_on_page_bit_common
```

A separate process:

```text
python3 -m app.traffic_projection.cli run
```

was concurrently reading the same:

```text
observations.sqlite3
```

and was also observed waiting in the same read path.

Negative evidence:

```text
filesystem full =
NO

inode exhaustion =
NO

explicit ext4 / I/O error =
NOT OBSERVED

primary VM network defect =
NO

new passive sensor NIC changed default route =
NO
```

---

# 3. Fresh Repository Baseline

Repository:

```text
ZaurNavi/CaptivePortal
```

Fresh `main` at architecture review:

```text
HEAD =
414de85c311e72405dc25446461dcd458b5ae597

TREE =
9f267dc0944a91f7a4b81dccee8a77e0ec05fbe0
```

This DRAFT must be rebound again by Tech Lead before any implementation-ready FINAL.

---

# 4. Current Startup Critical Path — SOURCE CONFIRMED

Current `run.py` performs, in order:

```text
artifact identity
settings
controller
Visitor Snapshot composition
Visit Lifecycle composition
create_app()
"Web application created"

Observation Foundation construction
Current State construction
Pending Cleaner construction/start

Observation Foundation.start()
Current State.start()
Visitor Snapshot.start()

Visitor Registry construction/start
Visit reconciliation start

Analytics runtime configuration
Admin Web runtime configuration
Home AP telemetry
Public Traffic worker

ONLY THEN:

app.run(
    host,
    port,
    ...
)
```

Therefore the listener is structurally downstream of optional/read-side startup work.

This matches the production timeline:

```text
Web application created
~11 minutes before
HTTP listener bind
```

---

# 5. Observation Startup Is Synchronous Before Bind

Current Observation startup is:

```text
run.py
→ _observation_foundation.start()
→ ObservationFoundationRuntime.start()
→ repository.initialize()
```

`repository.initialize()` executes synchronously before `start()` returns.

It includes:

```text
open SQLite

PRAGMA user_version

schema/table/index validation

startup schema check

BEGIN IMMEDIATE

UPDATE running observation cycles
→ abandoned

COMMIT
```

Only after that does Observation start its workers and return to `run.py`.

Consequently:

```text
slow Observation DB initialization
=
slow main HTTP bind
```

today.

---

# 6. Traffic Projection Cold-Start Contention — SOURCE CONFIRMED

`traffic-projection.service` is a separate auxiliary process.

Its authoritative source is:

```text
observations.sqlite3
```

through read-only SQLite connections.

Worker startup immediately enters source maintenance, including:

```text
source head reads

metadata reads

cycle/AP reads

reconciliation / maintenance
```

Production evidence that both processes were simultaneously blocked reading the Observation DB is therefore consistent with current architecture.

The architectural issue is resource/startup contention:

```text
independent processes
can compete for the same cold Observation storage
during the critical Portal startup window
```

not a logical dependency on Traffic Projection.

---

# 7. Existing Failure-Isolation Principle

Current architecture requires:

```text
failure of independent components
must not break guest authorization
where core auth dependencies remain healthy
```

This incident demonstrates incomplete temporal isolation:

```text
runtime failure isolation exists

BUT

startup latency isolation is incomplete
```

A component can be logically fail-open yet still block core availability by occupying the synchronous pre-bind startup path.

---

# 8. Architectural Goal

Freeze the target principle:

```text
CORE CAPTIVE AUTHORIZATION AVAILABILITY
MUST NOT WAIT FOR
OPTIONAL READ-SIDE INITIALIZATION
```

Core listener availability must not require successful/fast startup of:

```text
Observation

Current State read foundation

Visitor Registry read initialization

Visit reconciliation

Analytics

Admin read composition

Traffic Projection
```

unless fresh source review proves a component is actually mandatory to Authorization.

---

# 9. Required Readiness Model

Introduce explicit lifecycle dimensions:

```text
PROCESS_ACTIVE

CORE_HTTP_READY

AUTHORIZATION_READY

OPTIONAL_READ_SURFACES =
INITIALIZING
READY
DEGRADED
UNAVAILABLE
```

Semantics:

```text
PROCESS_ACTIVE
=
process exists

CORE_HTTP_READY
=
local listener accepts requests
and core routing is installed

AUTHORIZATION_READY
=
mandatory Authorization dependencies
are usable

OPTIONAL_READ_SURFACES
=
module-specific readiness
```

Permanent:

```text
PROCESS_ACTIVE
does NOT imply
CORE_HTTP_READY
```

and:

```text
OPTIONAL_READ_SURFACE UNAVAILABLE
must NOT force
AUTHORIZATION_UNAVAILABLE
```

---

# 10. Core HTTP Surface

Candidate core-ready surface includes:

```text
public Captive Portal

Authorization flow

CAPPORT

core Portal assets/routes

Omada webhook HTTP ingress route
where route composition itself is bounded
```

Exact route inventory must be source-bound by Tech Lead.

Admin/Analytics are not declared core-ready dependencies.

---

# 11. Admin / Analytics Startup Semantics

Admin/Analytics routes may be registered during bounded app composition, but expensive source initialization must not be required before core listener readiness.

Preferred semantics:

```text
route surface exists

source runtime initializing/unavailable
→ explicit bounded initializing/degraded/unavailable response

core Portal continues normally
```

Important Flask constraint:

```text
route/blueprint registration
must be completed before normal request serving
```

Therefore implementation must distinguish:

```text
cheap route composition
from
expensive source/runtime initialization
```

No unsafe post-first-request blueprint mutation.

---

# 12. Listener-First Ordering Requirement

Target ordering:

```text
PROCESS START
        ↓
bounded core configuration/composition
        ↓
bind HTTP listener
        ↓
CORE_HTTP_READY
        ↓
start optional/read-side initialization
        ↓
module-specific readiness transitions
```

Important:

```text
starting an optional worker immediately before app.run()
does NOT prove listener-first ordering
```

because `app.run()` performs bind internally.

Implementation-ready design must provide an explicit server lifecycle primitive that proves:

```text
socket/listener bound
BEFORE
heavy optional startup launches
```

Possible family:

```text
explicit Werkzeug server lifecycle
or equivalent project-compatible mechanism
```

Exact primitive is not frozen in this DRAFT.

---

# 13. Authorization Readiness

`CORE_HTTP_READY` and `AUTHORIZATION_READY` are distinct.

Tech Lead must identify the minimum mandatory Authorization startup set.

Candidate mandatory set:

```text
settings

loaded artifact identity

Omada/controller provider construction

core Flask application composition

Auth manager/executor

Authorization health tracker
```

Candidate fail-open/non-blocking integrations:

```text
Visitor Snapshot submission

Visit start submission

telemetry

Observation

Current State

Analytics

Admin
```

Exact boundary must be source-bound before FINAL.

---

# 14. Optional Runtime Bootstrap

Required properties:

```text
starts only AFTER listener-bound proof

does not execute at import

does not block Authorization request handling

bounded per-component startup policy

module states:
initializing / ready / degraded / unavailable

safe telemetry

safe shutdown/cancellation
```

Exact orchestration pattern remains Tech Lead/Architect review material.

---

# 15. Observation Startup Policy

Observation remains independent of Authorization.

Required behavior:

```text
Observation DB startup fast
→ Observation ready normally

Observation DB startup slow
→ Portal remains available

Observation DB unavailable/corrupt
→ Observation unavailable/degraded
→ Analytics/Admin evidence may degrade
→ Authorization remains available

Observation startup exceeds bounded policy
→ core startup remains unblocked
```

No unsafe thread cancellation.

---

# 16. Bounded Startup Semantics

Each optional component must declare:

```text
startup deadline / budget

bounded work

interruptible work

non-interruptible work

state after budget exhaustion

telemetry

retry policy

shutdown interaction
```

Permanent:

```text
bounded waiting by core
!=
force-killing arbitrary SQLite work
```

An optional background initializer may finish later while core remains available.

---

# 17. Startup Telemetry

Minimum lifecycle evidence:

```text
process_started_at

core_composition_started

core_composition_completed

http_listener_bound_at

core_http_ready_at

authorization_ready_at

optional_bootstrap_started_at

component_start_started

component_start_ready

component_start_degraded

component_start_unavailable

component_start_duration_ms
```

Observation-specific:

```text
observation_initialize_started

observation_initialize_completed

observation_initialize_duration_ms

observation_initialize_failure_category
```

No raw DB content logging.

---

# 18. Readiness Probe Contract

A readiness surface is required, separate from process existence.

At minimum expose:

```text
core_http_ready

authorization_ready

optional component states
```

Candidate:

```text
local/internal readiness endpoint
or equivalent machine-readable local probe
```

Security/exposure and exact URL remain Tech Lead source-review items.

---

# 19. systemd Semantics

Do NOT redefine Linux:

```text
active (running)
```

as app readiness.

Instead:

```text
systemd ACTIVE =
process liveness

application readiness =
explicit application contract
```

Tech Lead should evaluate:

```text
Type=notify / sd_notify

or

explicit readiness probe

or

another bounded project-compatible mechanism
```

No systemd change is authorized by this DRAFT.

---

# 20. NGINX / Upstream Semantics

The production 502 was consistent with:

```text
NGINX healthy
+
127.0.0.1:8088 not listening
```

Target:

```text
core listener becomes available quickly
```

Optional read surfaces may then return application-level:

```text
200
503
degraded response
```

A long 502 window caused only by optional read-side startup is unacceptable.

---

# 21. Traffic Projection Cold-Start Coordination

Traffic Projection remains logically independent.

Permanent:

```text
CaptivPortal core
MUST NOT wait for
traffic-projection.service
```

But startup resource coordination SHOULD prevent simultaneous expensive cold Observation reads during the core-ready critical window.

Direction:

```text
CaptivPortal core readiness
        ↓
Traffic Projection may begin heavy source maintenance
```

Never the reverse.

Candidate mechanisms:

```text
systemd ordering + readiness signal

bounded startup delay

projection initial-idle window

explicit local readiness dependency
```

Exact mechanism is not frozen.

---

# 22. Cold-Cache / Storage Acceptance

Future implementation must prove:

```text
Observation initialize blocked/slow

BUT

core HTTP listener becomes ready
within bounded core target

Portal/CAPPORT reachable

Authorization usable
if mandatory dependencies healthy

Observation =
initializing/degraded/unavailable

Admin/Analytics evidence =
degraded/unavailable as designed
```

Use:

```text
controlled injected delay
+
Linux integration/cold-cache evidence
```

as appropriate.

A 448 MiB production DB is not required for every unit test.

---

# 23. Simultaneous Reader Acceptance

Linux/integration gate should include:

```text
Observation startup/read

AND

Traffic Projection source read
```

against a representative Observation DB.

Acceptance is not zero contention.

Acceptance is:

```text
contention cannot hold core HTTP/Auth availability hostage
```

while source-integrity rules remain intact.

---

# 24. Core Startup Time Target

A numeric SLO is required before implementation-ready FINAL.

Direction:

```text
CORE_HTTP_READY:
seconds, not minutes
```

Do NOT invent the exact number in this DRAFT.

Tech Lead should return evidence and a recommended target.

Potential separate SLOs:

```text
process → listener bound

listener bound → authorization ready

optional component startup → ready/degraded
```

---

# 25. Failure Semantics

Permanent:

```text
Observation startup failure
!=
Authorization failure

Analytics startup failure
!=
Authorization failure

Admin source failure
!=
Authorization failure

Traffic Projection failure
!=
Authorization failure
```

If a truly mandatory auth dependency fails:

```text
AUTHORIZATION_READY =
false
```

while:

```text
CORE_HTTP_READY
```

may still be true to allow controlled application-level unavailability rather than connection refusal.

---

# 26. No Weakening of Source Integrity

Do NOT solve startup by:

```text
skipping schema validation permanently

disabling DB integrity protections

allowing unsafe concurrent writes

ignoring corruption

removing writer locks

loosening Site/source identity

serving stale as fresh
```

This task changes:

```text
availability / isolation / lifecycle
```

not data-integrity semantics.

---

# 27. No Emergency DB Surgery

This DRAFT authorizes NO:

```text
VACUUM

REINDEX

DB copy/replace

SQLite PRAGMA changes

Observation retention change

manual row deletion

filesystem tuning

cache dropping

service priority tuning
```

Separate evidence and authorization would be required.

---

# 28. Tech Lead Source Review Scope

Inspect at minimum:

```text
run.py

app/web/web.py

app/auth/**

app/capport/**

app/observations/runtime.py

app/observations/repository.py

app/current_state/**

app/visitor_registry/**

app/visit_lifecycle/**

app/analytics/**

app/admin_web/**

app/traffic_projection/cli.py

app/traffic_projection/service.py

app/traffic_projection/source.py

systemd/deployment docs

health/readiness docs
```

Classify each pre-bind operation as:

```text
CORE MANDATORY

CHEAP COMPOSITION

OPTIONAL ASYNC STARTUP

MUST MOVE POST-BIND

SEPARATE SERVICE
```

---

# 29. Proposed Task Decomposition

Architecture work may decompose implementation into:

```text
A. startup critical-path inventory

B. core/listener readiness contract

C. listener-first server lifecycle

D. optional bootstrap state machine

E. Observation startup isolation

F. Admin/Analytics degraded startup behavior

G. readiness telemetry/probe

H. Traffic Projection cold-start coordination

I. systemd/deployment semantics

J. cold-cache / failure-isolation acceptance
```

If implementation is too broad for one safe patch, split implementation while preserving this architecture contract.

---

# 30. Acceptance Invariants

Future implementation must prove:

```text
1.
Core listener does not wait for Observation DB initialize.

2.
Authorization does not depend on Observation/Analytics/Admin readiness.

3.
Slow Observation startup produces module degradation,
not upstream connection refusal.

4.
Traffic Projection cannot become a prerequisite
for CaptivPortal startup.

5.
No optional bootstrap starts before listener-bound proof.

6.
No post-start Flask blueprint mutation.

7.
Core readiness is machine-visible.

8.
systemd process active is not presented
as equivalent to app ready.

9.
Existing DB integrity checks remain.

10.
Clean shutdown remains bounded and safe.
```

---

# 31. Incident Classification

Architect classification:

```text
TYPE =
architectural startup availability defect / debt

SEVERITY =
high availability significance

CURRENT EMERGENCY =
no

CURRENT PRODUCTION =
healthy

EXACT SINGLE SQLITE QUERY ROOT CAUSE =
NOT PROVEN

ARCHITECTURAL CAUSAL PATH =
CONFIRMED:
optional synchronous pre-bind work exists

OBSERVATION DB AS INCIDENT BLOCKING FILE =
production evidence

TRAFFIC PROJECTION SIMULTANEOUS SOURCE READ =
production evidence + source-consistent
```

Do not close this as only:

```text
large DB / one-time slow boot
```

even if the exact kernel wait does not reproduce every restart.

---

# 32. Answers to Owner Questions

## Q1 — Core listener before heavy Observation / Analytics / Admin?

```text
YES.
```

## Q2 — Optional/read-side runtimes async after core bind?

```text
YES.
```

Exact orchestration requires source review.

## Q3 — Slow/unavailable Observation degrades only evidence surfaces?

```text
YES.
```

It must not delay Authorization.

## Q4 — Bounded execution / fail-degraded / telemetry / cancellation?

```text
YES.
```

Cancellation must be safe.

## Q5 — Avoid simultaneous cold heavy reads with Traffic Projection?

```text
YES.
```

Use one-way coordination; Portal never waits for Projection.

## Q6 — Explicit readiness contract?

```text
YES.
```

At least:

```text
PROCESS_ACTIVE
CORE_HTTP_READY
AUTHORIZATION_READY
OPTIONAL_READ_SURFACES
```

## Q7 — systemd semantics?

```text
YES.
```

`active` remains liveness; application readiness becomes explicit.

---

# 33. Explicit Non-Goals

Not in this task:

```text
Observation DB performance optimization alone

Traffic Projection semantic redesign

Analytics semantic redesign

Admin UI redesign

Authorization semantic redesign

Omada integration redesign

SQLite migration

database pruning

INFRA CHANGE-B sensor implementation

Device Fingerprint Sensor implementation
```

Current INFRA CHANGE-B / sensor work may continue independently unless it later touches the same restart/deployment window.

---

# 34. Tech Lead Questions

Return:

```text
1. PASS / FIX on architectural significance.

2. Exact current pre-bind call graph.

3. Pre-bind disk/network/blocking operations.

4. Exact mandatory Authorization dependency boundary.

5. Recommended listener-first server primitive.

6. Safe optional bootstrap composition pattern.

7. Readiness endpoint/notify recommendation.

8. Traffic Projection one-way startup coordination recommendation.

9. Numeric core-readiness SLO recommendation.

10. One task vs staged implementation split.

11. Required focused / Linux / Central Lab gates.

12. Exact file boundary for implementation-ready FINAL.
```

---

# 35. Control Status

```text
TASK =
TASK-STARTUP-AVAILABILITY-01-DRAFT

ARCHITECTURAL SIGNIFICANCE =
CONFIRMED

INCIDENT =
SELF-RECOVERED

PRODUCTION =
CURRENTLY HEALTHY

NEW RESEARCH =
NO BROAD RESEARCH REQUIRED

SOURCE REBIND =
TECH LEAD REQUIRED

IMPLEMENTATION-READY =
NO

CODER =
HOLD

IMPLEMENTATION =
NOT AUTHORIZED

BRANCH =
NOT AUTHORIZED

COMMIT =
NOT AUTHORIZED

PUSH =
NOT AUTHORIZED

PR =
NOT AUTHORIZED

DEPLOY =
NOT AUTHORIZED
```

---

# 36. Next Workflow

```text
TASK-STARTUP-AVAILABILITY-01-DRAFT
        ↓
Tech Lead source / critical-path review
        ↓
PASS or narrow FIX
        ↓
Architect + Tech Lead
implementation-ready FINAL
        ↓
Owner explicit implementation authorization
        ↓
Coder
```

No emergency production action is requested by this DRAFT.

**End of TASK-STARTUP-AVAILABILITY-01-DRAFT.**
