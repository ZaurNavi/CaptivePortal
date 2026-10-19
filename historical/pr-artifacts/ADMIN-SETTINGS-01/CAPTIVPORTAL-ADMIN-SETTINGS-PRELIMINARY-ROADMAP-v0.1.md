# CAPTIVPORTAL ADMIN SETTINGS — PRELIMINARY ROADMAP v0.1

**Project:** CaptivPortal  
**Area:** Admin UI → Settings  
**Document type:** Shared planning roadmap  
**Status:** PRELIMINARY / NON-AUTHORIZING  
**Baseline reference:** `main@be3fe14f929b45e4a1ca3991bc6a2a3011792641`  
**Architecture source:** `CAPTIVPORTAL ADMIN SETTINGS — ARCHITECTURE CONTRACT v0.1`  
**Current architecture status at roadmap creation:** DRAFT FOR TECH LEAD REVIEW  
**Implementation authorization:** NO  
**Coder authorization:** NO  

---

## 0. PURPOSE

This document defines the preliminary staged development direction for CaptivPortal Admin UI → Settings.

It exists as a shared reference for Owner, Architect, Technical Developer Settings, Tech Lead, Coder, and QA / production acceptance.

This roadmap is intentionally separate from the architecture contract and from implementation TASKs.

It answers:

> In what order should CaptivPortal progressively admit configuration domains into Admin Settings?

It does NOT answer:

> How exactly should a particular stage be implemented?

---

## 1. AUTHORITY AND GOVERNANCE

The architecture contract is authoritative over this roadmap.

If this roadmap conflicts with an accepted architecture contract:

```text
ACCEPTED ARCHITECTURE
>
IMPLEMENTATION CONTRACT / TASK
>
THIS ROADMAP
```

This roadmap MUST NOT be used by Coder as implementation authorization.

For every implementation stage:

```text
architecture accepted
    ↓
exact implementation TASK prepared
    ↓
Tech Lead implementation-contract review
    ↓
Coder authorization
    ↓
implementation
    ↓
independent acceptance / regression / production gate
```

Future roadmap stages are planning intent only until their own architecture boundaries are accepted.

Permanent planning principle:

```text
SETTING EXISTS IN CURRENT CONFIGURATION
!=
SETTING SHOULD BE ADMIN-EDITABLE
```

Settings must grow by explicitly admitted product domains, not by bulk-importing environment variables.

---

# 2. DEVELOPMENT STRATEGY

CaptivPortal Settings should be developed as a configuration control plane, not as a raw configuration editor.

The long-term conceptual layers are:

```text
Settings Definition
        ↓
Configuration resolution
        ↓
Durable configured state
        ↓
Validation
        ↓
Activation state
        ↓
Runtime effective state
        ↓
Admin UI representation
```

The Admin Settings page is the user-facing control surface over this system.

The first stages intentionally use low-risk configuration so that the control plane can be validated before operational, integration, security-sensitive, or secret configuration is admitted.

---

# 3. STAGE 0 — SETTINGS V1 ARCHITECTURE FINALIZATION

## Goal

Finalize the architecture contract for the first writable Settings control plane.

## Current state

Architecture draft already defines:

- `SettingsStore`;
- SQLite persistence;
- immutable configuration generations;
- persisted overrides;
- configuration precedence;
- configured vs effective state;
- activation state;
- `SettingsDefinitionRegistry`;
- atomic validation;
- durable audit;
- optimistic concurrency;
- idempotency;
- global authorization capabilities;
- Settings read/mutation API;
- no systemd authority;
- no writable secrets;
- GLOBAL-only V1;
- exact first 12 writable settings.

## Remaining bounded clarification before FINAL

The final architecture should explicitly freeze:

1. which runtime owner records `effective_generation`, and at what exact successful-startup/readiness boundary;
2. how `activation_failed` can be durably established when restart/service startup is performed externally and the new process never reaches its own successful runtime reporting boundary;
3. initial/bootstrap generation and ETag semantics for a brand-new empty `SettingsStore`;
4. exact `effective_value` semantics for a setting whose `consumer_state = disabled`.

## Exit gate

```text
ADMIN SETTINGS ARCHITECTURE = FINAL / ACCEPTED
```

Only after this gate may the Technical Developer Settings prepare the Stage 1 implementation TASK.

---

# 4. STAGE 1 — SETTINGS FOUNDATION + SAFE ADMIN SETTINGS V1

## Purpose

Build and prove the complete Settings control plane using a deliberately low-risk writable allowlist.

The primary value of Stage 1 is not the importance of the 12 values themselves.

The primary value is proving:

```text
Registry
→ Resolver
→ SettingsStore
→ Generation
→ Validation
→ Audit
→ Mutation
→ Pending activation
→ Restart boundary
→ Effective generation
```

## 4.1 Editable group A — Pagination / bounded query presentation

Exact planned V1 allowlist:

```text
WEB_ADMIN_DEVICE_PAGE_SIZE
WEB_ADMIN_VISIT_PAGE_SIZE
WEB_ADMIN_OBSERVATION_PAGE_SIZE
WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS
WEB_ADMIN_CURRENT_STATE_PAGE_SIZE
WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE
```

Canonical bounds are owned by the accepted Settings V1 architecture.

## 4.2 Editable group B — Refresh cadence

Exact planned V1 allowlist:

```text
WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS
WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS
WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS
WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS
```

Canonical bounds are owned by the accepted Settings V1 architecture.

## 4.3 Intended Stage 1 user-facing outcome

Admin UI obtains a real `Settings` surface which can:

- show registered editable settings;
- show configured and effective values distinctly;
- show deployment/base source;
- show persisted override state;
- set an override;
- clear an override;
- validate atomically;
- protect against stale writes;
- record durable generations/audit;
- show pending restart state;
- never claim a saved value is active before runtime adoption.

## 4.4 Stage 1 non-goals

Stage 1 does NOT expand into:

- Omada controller mutation;
- Omada secrets;
- CAPPORT;
- Site-scoped settings;
- feature-enable switches;
- systemd control;
- hot reload;
- auxiliary processes;
- operational worker tuning;
- rollback UI;
- generic environment editing.

## Exit gate

Before proceeding to Controller settings:

```text
Settings V1 implementation accepted
+
targeted behavior accepted
+
integration/regression accepted
+
production activation accepted
+
no unresolved Settings control-plane defect that would make expansion unsafe
```

---

# 5. STAGE 2 — OMADA CONTROLLER SETTINGS: READ MODEL

## Status

ROADMAP PROPOSAL ONLY.

Requires a dedicated architecture extension before implementation.

## Goal

Make Omada Controller configuration visible as a coherent product configuration domain in:

```text
Admin UI
→ Settings
→ Controller
```

without yet allowing controller configuration mutation.

## Candidate read-only information

Subject to a dedicated architecture decision, the Controller Settings read model may expose safe representations of:

- controller URL;
- controller identity / Omada ID;
- client/application identity;
- whether required secret material is configured;
- configuration source;
- configured/effective state where meaningful;
- connection/health state only if a separate trustworthy health contract is defined.

Raw secret material MUST NOT be returned.

## Why this stage precedes Controller mutation

It allows CaptivPortal to establish a stable product-facing Controller configuration model before introducing mutation of integration-critical values.

It also separates:

```text
represent configuration correctly
```

from:

```text
change configuration safely
```

---

# 6. STAGE 3 — OMADA CONTROLLER SETTINGS: WRITABLE NON-SECRET CONFIGURATION

## Status

ROADMAP PROPOSAL ONLY.

Requires a dedicated architecture extension.

## Candidate domain

Potential non-secret controller settings include conceptually:

```text
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
```

The final admitted key set must be explicitly approved by architecture.

## Intended direction

Where approved, Controller non-secret settings should reuse the common Settings control plane:

```text
SettingsDefinitionRegistry
→ SettingsStore
→ configured generation
→ validation
→ activation requirement
→ runtime effective generation
```

No separate ad-hoc Controller settings database or parallel mutation mechanism should be introduced without an explicit architecture decision.

## Default roadmap preference

Prefer restart-based activation first.

Do not introduce hot reconnect / live Omada provider replacement merely because a particular field appears technically reloadable.

---

# 7. STAGE 4 — OMADA CONTROLLER SECRET MANAGEMENT

## Status

ROADMAP PROPOSAL ONLY.

Requires a dedicated Secret Storage architecture contract.

## Goal

Allow safe replacement of required controller secret material without ever exposing the current raw secret to the browser.

Conceptual UI:

```text
Client Secret
Status: Configured

[Replace secret]
```

Not:

```text
Client Secret: <current secret value>
```

## Required architecture before implementation

A future secret stage must define at minimum:

- secret storage owner;
- encryption / protected storage model;
- write-only API semantics;
- secret replacement validation;
- runtime consumption boundary;
- audit redaction;
- recovery behavior;
- deployment interaction;
- activation semantics.

Ordinary SettingsStore persistence MUST NOT silently become plaintext secret storage.

---

# 8. STAGE 5 — PORTAL / GUEST EXPERIENCE SETTINGS

## Status

FUTURE ROADMAP DIRECTION ONLY.

## Goal

Begin exposing settings that an operator naturally understands as guest-portal product behavior.

Admission must be by explicit allowlist.

CAPPORT network/external-contract configuration is NOT automatically included.

Before any CAPPORT-related value becomes writable, architecture must explicitly decide which values are safe product settings and which remain deployment/network configuration.

---

# 9. STAGE 6 — ADMIN PRODUCT BEHAVIOR / FEATURE CONTROLS

## Status

FUTURE ROADMAP DIRECTION ONLY.

Potential future scope may include selected non-security Admin product behavior or feature controls.

Feature-enable switches are NOT part of Settings V1 and must not be admitted automatically.

Any enable/disable control requires its own dependency, activation, failure, and access-impact analysis.

---

# 10. STAGE 7 — ANALYTICS / PRODUCT THRESHOLDS

## Status

FUTURE ROADMAP DIRECTION ONLY.

## Goal

Expose only operator-meaningful analytical configuration.

The Settings UI should not become a dump of internal tuning constants.

Candidate values should be admitted only when:

- their semantics are understandable to the operator;
- bounds and dependencies are explicit;
- runtime ownership is clear;
- changing them does not create hidden destructive effects.

---

# 11. STAGE 8 — OPERATIONAL MODULE SETTINGS

## Status

FUTURE / HIGHER-RISK.

Potential domains:

- Current State;
- Observation;
- Visit Lifecycle;
- Visitor Registry;
- Pending Session Cleaner;
- Traffic-related operational behavior.

These settings may affect external requests, load, polling, data retention, runtime actions, or visitor/client behavior.

They therefore require stricter architecture admission than presentation settings.

They MUST NOT be pulled into Admin Settings simply because environment variables already exist.

---

# 12. STAGE 9 — SITE-SCOPED SETTINGS

## Status

FUTURE ARCHITECTURE EXPANSION.

Settings V1 remains GLOBAL-only.

Site-scoped Settings should be admitted only after the project has a stable contract for:

- which definitions are Global;
- which definitions are Site-scoped;
- precedence;
- authorization scope;
- Site identity;
- inheritance/fallback;
- generation semantics;
- multi-Site read/write UX.

No default Site should be used to fake Global Settings authorization.

---

# 13. STAGE 10 — AUXILIARY / MULTI-PROCESS SETTINGS

## Status

FUTURE / HIGH-RISK.

Before admission, architecture must freeze:

```text
process identity
settings ownership
read mechanism
generation adoption
activation target set
restart/reload semantics
failure behavior
partial activation semantics
rollback/recovery semantics
```

No multi-process setting may be called active while required consumers have adopted different generations.

---

# 14. SETTINGS INFORMATION ARCHITECTURE — LONG-TERM DIRECTION

The Admin Settings UI should grow by product domain, not by configuration source.

Possible long-term navigation direction:

```text
Settings

General

Controller
  Omada Controller

Portal
  Guest Portal
  CAPPORT              [only if separately admitted]

Administration
  Admin UI
  Security             [future, restricted]

Data & Analytics
  Traffic
  Analytics

Operations
  Current State
  Observations
  Visits

Integrations
  Webhooks
  Device Fingerprint   [future, if admitted]
  ...
```

Do NOT create empty navigation sections merely to match this roadmap.

A section should appear only when a real read or mutation contract exists.

---

# 15. PRODUCT UX PRINCIPLES

As Settings grows, user-facing UI should prefer product meaning over raw environment-variable presentation.

Example:

```text
Devices per page
100
```

is the primary UI representation.

The canonical technical key may be shown secondarily:

```text
WEB_ADMIN_DEVICE_PAGE_SIZE
```

where useful for diagnostics or advanced context.

The UI should distinguish deployment/base value, persisted override, configured value, effective value, and pending value where the applicable architecture exposes them.

A successful Save MUST NOT be represented as successful activation when restart or another activation step remains pending.

Reset semantics should mean:

```text
clear persisted override
→ return control to lower-precedence deployment/default configuration
```

not:

```text
copy the current deployment value into SettingsStore
```

---

# 16. ROADMAP DECISION SUMMARY

Current intended sequence:

```text
Stage 0
Finalize Settings V1 architecture
        ↓
Stage 1
Settings Foundation + 12 safe Admin values
        ↓
Stage 2
Controller read model
        ↓
Stage 3
Controller writable non-secret settings
        ↓
Stage 4
Controller secret replacement / Secret Storage
        ↓
Stage 5+
Progressive product-domain expansion
        ↓
Later
Site scope / operational / auxiliary / multi-process settings
```

The core expansion rule is:

```text
first prove the Settings control plane on low-risk values
then reuse that control plane for increasingly important configuration domains
```

---

# 17. CURRENT PROJECT POSITION

At creation of this roadmap:

```text
ARCHITECTURE CONTRACT
= DRAFT FOR TECH LEAD REVIEW

ROADMAP
= PRELIMINARY / NON-AUTHORIZING

STAGE 1 IMPLEMENTATION TASK
= NOT YET ISSUED

CODER
= HOLD

NEXT
= bounded architecture clarification
→ FINAL / accepted Settings V1 architecture
→ exact Stage 1 implementation TASK
→ Tech Lead implementation-contract review
→ Coder only after authorization
```

---

# 18. CHANGE CONTROL FOR THIS ROADMAP

This roadmap is expected to evolve.

A roadmap revision may reorder future stages, split or merge a future stage, add a newly discovered product configuration domain, or remove a future direction.

A roadmap revision MUST NOT silently override an accepted architecture contract or active implementation TASK.

When a stage becomes architecturally accepted, its authoritative behavior should live in the corresponding architecture contract and implementation TASK, while this roadmap remains the high-level sequencing reference.
