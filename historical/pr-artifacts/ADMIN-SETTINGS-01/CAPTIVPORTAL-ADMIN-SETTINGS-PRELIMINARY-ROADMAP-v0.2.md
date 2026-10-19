# CAPTIVPORTAL ADMIN SETTINGS — PRELIMINARY ROADMAP v0.2

**Project:** CaptivPortal  
**Area:** Admin UI → Settings  
**Document type:** Shared planning roadmap  
**Status:** ACTIVE PLANNING REFERENCE / NON-AUTHORIZING  
**Baseline reference:** `main@be3fe14f929b45e4a1ca3991bc6a2a3011792641`  
**Architecture source:** `CAPTIVPORTAL ADMIN SETTINGS — ARCHITECTURE CONTRACT v0.1`  
**Architecture clarification:** `CAPTIVPORTAL ADMIN SETTINGS — ARCHITECTURE DISPOSITION A1–A4`  
**Architecture status:** FINAL / ACCEPTED FOR STAGE 1 TASK PREPARATION  
**Implementation authorization:** NO  
**Coder authorization:** NO  

---

## 0. PURPOSE

This document defines the staged development direction for CaptivPortal Admin UI → Settings.

It is a shared sequencing reference for Owner, Architect, Technical Developer Settings, Tech Lead, Coder, and QA / production acceptance.

It is intentionally separate from architecture contracts and implementation TASKs.

It answers:

> In what order should CaptivPortal progressively admit configuration domains into Admin Settings?

It does NOT authorize implementation.

---

## 1. AUTHORITY AND GOVERNANCE

Authority order:

```text
ACCEPTED ARCHITECTURE
>
ACCEPTED IMPLEMENTATION CONTRACT / TASK
>
THIS ROADMAP
```

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

Permanent planning principle:

```text
SETTING EXISTS IN CURRENT CONFIGURATION
!=
SETTING SHOULD BE ADMIN-EDITABLE
```

Settings grows by explicitly admitted product domains, not by bulk-importing environment variables.

---

# 2. DEVELOPMENT STRATEGY

CaptivPortal Settings is a configuration control plane, not a raw environment/configuration editor.

Conceptual layers:

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

The first implementation stage intentionally uses low-risk values to prove the control plane before admitting integration-critical, security-sensitive, secret, Site-scoped, operational, or multi-process configuration.

---

# 3. STAGE 0 — SETTINGS V1 ARCHITECTURE FINALIZATION

## Status

```text
CLOSED
```

Architecture v0.1 plus A1–A4 disposition is:

```text
FINAL / ACCEPTED FOR STAGE 1 TASK PREPARATION
```

The final clarifications freeze:

- `captive-portal.service` main runtime / `run.py` composition boundary owns generation adoption;
- `SettingsActivationService` owns durable adoption/failure recording;
- adoption is reported on every Settings-aware main-service startup;
- `activation_failed` requires positive in-process durable attestation;
- silence/service disappearance does not become `activation_failed`;
- physical immutable bootstrap generation is `0`;
- initial `configured_generation = 0`;
- pre-adoption `effective_generation = null`;
- initial ETag is `"settings-g0"`;
- first real generation has parent `0`;
- disabled consumer means `effective_value = null`;
- `consumer_disabled` belongs to `consumer_state`, not `activation_state`;
- generation may be fully adopted while an optional consumer is disabled.

No change was made to S1–S20 or the V1 allowlist.

---

# 4. STAGE 1 — SETTINGS FOUNDATION + SAFE ADMIN SETTINGS V1

## Status

```text
IMPLEMENTATION TASK PREPARATION AUTHORIZED
CODER HOLD
IMPLEMENTATION NOT YET AUTHORIZED
```

## Purpose

Build and prove the complete Settings control plane using a deliberately low-risk writable allowlist.

Primary proof chain:

```text
Registry
→ Resolver
→ SettingsStore
→ Generation
→ Validation
→ Audit
→ Mutation
→ Pending activation
→ Main-service restart boundary
→ Runtime adoption
→ Effective generation
```

## 4.1 Editable group A — Pagination / bounded query presentation

```text
WEB_ADMIN_DEVICE_PAGE_SIZE
WEB_ADMIN_VISIT_PAGE_SIZE
WEB_ADMIN_OBSERVATION_PAGE_SIZE
WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS
WEB_ADMIN_CURRENT_STATE_PAGE_SIZE
WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE
```

## 4.2 Editable group B — Refresh cadence

```text
WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS
WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS
WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS
WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS
```

Canonical types, bounds, scope, apply requirements, API behavior, authorization, audit, concurrency, activation and failure semantics are owned by the accepted architecture contract.

## 4.3 Intended user-facing outcome

Admin UI obtains a real `Settings` surface which can:

- show registered editable settings;
- distinguish configured, effective, pending and persisted override state;
- show deployment/base source;
- set an override;
- clear an override;
- validate atomically;
- protect against stale writes;
- record durable generations/audit;
- show pending restart state;
- never claim a saved value is active before runtime adoption.

## 4.4 Stage 1 non-goals

No:

- Omada controller mutation;
- Omada secret mutation;
- CAPPORT mutation;
- Site-scoped settings;
- feature-enable switches;
- systemd authority;
- restart button;
- hot reload;
- auxiliary-process integration;
- operational worker tuning;
- rollback UI;
- history browser UI;
- generic environment editor.

## Exit gate

Proceed to Controller work only after:

```text
Stage 1 implementation accepted
+
targeted behavior accepted
+
integration/regression accepted
+
production activation accepted
+
no unresolved Settings control-plane defect that makes expansion unsafe
```

---

# 5. STAGE 2 — OMADA CONTROLLER SETTINGS: READ MODEL

## Status

```text
ROADMAP PROPOSAL ONLY
DEDICATED ARCHITECTURE EXTENSION REQUIRED
```

## Goal

Create:

```text
Admin UI
→ Settings
→ Controller
```

with a coherent safe read model before allowing integration mutation.

Candidate information, subject to architecture:

- Controller URL;
- Omada/controller identity;
- client/application identity;
- secret configured/not-configured status;
- configuration source;
- configured/effective state where meaningful;
- trustworthy connection/health state only if separately contracted.

Raw secret material must never be returned.

---

# 6. STAGE 3 — OMADA CONTROLLER: WRITABLE NON-SECRET CONFIGURATION

## Status

```text
ROADMAP PROPOSAL ONLY
DEDICATED ARCHITECTURE EXTENSION REQUIRED
```

Candidate keys:

```text
OMADA_URL
OMADA_ID
OMADA_CLIENT_ID
```

Final key names/ownership must be confirmed against current code and accepted by architecture.

Preferred direction:

```text
Controller Settings
→ reuse common SettingsDefinitionRegistry
→ reuse SettingsStore
→ configured generation
→ validation
→ restart-based activation
→ runtime effective generation
```

No parallel ad-hoc Controller settings database or independent mutation system.

No hot reconnect by default.

---

# 7. STAGE 4 — OMADA CONTROLLER SECRET MANAGEMENT

## Status

```text
ROADMAP PROPOSAL ONLY
SEPARATE SECRET STORAGE ARCHITECTURE REQUIRED
```

Goal: write-only secret replacement without browser disclosure of current raw secret.

Conceptual UX:

```text
Client Secret
Status: Configured

[Replace secret]
```

Required future contract includes:

- protected secret storage owner;
- write-only API;
- replacement validation;
- runtime consumption;
- audit redaction;
- recovery;
- deployment interaction;
- activation semantics.

Ordinary SettingsStore must not silently become plaintext secret storage.

---

# 8. STAGE 5 — PORTAL / GUEST EXPERIENCE SETTINGS

Future roadmap direction only.

Expose operator-meaningful guest-portal behavior by explicit allowlist.

CAPPORT network/external-contract configuration is not automatically included and requires a separate admission decision.

---

# 9. STAGE 6 — ADMIN PRODUCT BEHAVIOR / FEATURE CONTROLS

Future roadmap direction only.

Selected product controls may be admitted later.

Feature-enable switches remain outside Stage 1 and require dependency, activation, failure, and access-impact analysis.

---

# 10. STAGE 7 — ANALYTICS / PRODUCT THRESHOLDS

Future roadmap direction only.

Expose only operator-meaningful analytical configuration with explicit semantics, bounds, ownership, and safe effects.

Do not turn Settings into a dump of internal tuning constants.

---

# 11. STAGE 8 — OPERATIONAL MODULE SETTINGS

Future / higher risk.

Potential domains:

- Current State;
- Observation;
- Visit Lifecycle;
- Visitor Registry;
- Pending Session Cleaner;
- Traffic-related operational behavior.

These require stricter admission because they may affect polling, external requests, retention, load, runtime actions or guest/client behavior.

---

# 12. STAGE 9 — SITE-SCOPED SETTINGS

Future architecture expansion.

Requires contracts for:

- Global vs Site definitions;
- precedence;
- authorization;
- Site identity;
- inheritance/fallback;
- generations;
- multi-Site UI/UX.

V1 remains GLOBAL-only.

---

# 13. STAGE 10 — AUXILIARY / MULTI-PROCESS SETTINGS

Future / high risk.

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

No silent partial activation.

---

# 14. LONG-TERM SETTINGS INFORMATION ARCHITECTURE

Possible future navigation direction:

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

Do not create empty sections simply to match this roadmap.

A section appears only when a real read or mutation contract exists.

---

# 15. PRODUCT UX PRINCIPLES

Prefer operator meaning over raw environment-variable presentation.

Primary:

```text
Devices per page
100
```

Technical key may be secondary:

```text
WEB_ADMIN_DEVICE_PAGE_SIZE
```

UI must preserve the distinction between:

```text
deployment/base value
persisted override
configured value
effective value
pending value
consumer state
activation state
```

A successful Save is not successful activation when restart/adoption is still pending.

Reset means:

```text
clear persisted override
→ return control to lower-precedence environment/default configuration
```

not copying the current lower-precedence scalar into SettingsStore.

---

# 16. CURRENT SEQUENCE

```text
Stage 0
Architecture FINAL
        ↓
Stage 1
Foundation + 12 safe Admin values
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
Site / operational / auxiliary / multi-process settings
```

Core rule:

```text
prove the Settings control plane on low-risk values
then reuse it for increasingly important configuration domains
```

---

# 17. CURRENT PROJECT POSITION

```text
ARCHITECTURE
= FINAL / ACCEPTED FOR STAGE 1 TASK PREPARATION

ROADMAP
= ACTIVE PLANNING REFERENCE / NON-AUTHORIZING

STAGE 1 IMPLEMENTATION TASK
= PREPARATION AUTHORIZED

CODER
= HOLD

IMPLEMENTATION
= NOT AUTHORIZED

PRODUCTION CHANGE
= NO

SYSTEMD ACTION
= NO

NEXT
= exact Stage 1 implementation TASK
→ Tech Lead implementation-contract review
→ only then Coder authorization
```

---

# 18. CHANGE CONTROL

This roadmap may be revised as future stages are accepted, split, merged, reordered or removed.

It must never silently override an accepted architecture contract or active implementation TASK.

When a stage becomes architecturally accepted, authoritative behavior belongs in that stage's architecture contract and implementation TASK; this roadmap remains the high-level sequencing reference.
