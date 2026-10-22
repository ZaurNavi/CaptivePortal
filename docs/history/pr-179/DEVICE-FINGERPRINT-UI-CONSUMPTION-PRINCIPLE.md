# DEVICE-FINGERPRINT-UI-CONSUMPTION-PRINCIPLE

**Project:** CaptivPortal  
**Area:** Device Fingerprint / Admin Web  
**Type:** Product/UI presentation principle  
**Status:** OWNER INTENT — FIXED FOR FUTURE UI WORK  
**Date:** 2026-09-23  
**Architecture note:** This document does **not** change Device Fingerprint R14 semantics. It defines how already-produced fingerprint data may be consumed and displayed by product UI.

---

## 1. Core principle

Device Fingerprint data is **reusable product data, not UI-specific data**.

The classifier determines the fingerprint result once and produces one structured, authoritative result for the device.

UI modules MUST NOT create their own independent device-identification logic, recalculate fingerprint semantics, or reinterpret the classifier result.

Any internal CaptivPortal screen may consume and display the subset of fingerprint fields appropriate for that screen.

---

## 2. Main fingerprint dimensions

For a device, the fingerprint result may provide these primary identity dimensions:

- `platform_family`
  - examples: Android, iOS, Windows, macOS, Linux, ChromeOS;

- `device_class`
  - examples: smartphone, tablet, laptop;

- `manufacturer_family`
  - examples: Apple, Samsung, Xiaomi, Lenovo;

- `model_family`
  - examples: iPhone, Galaxy S24 family, Redmi family, ThinkPad family.

For each dimension, the result also carries classification metadata such as:

- `status`
  - `resolved`
  - `recognized_out_of_scope`
  - `unknown`
  - `insufficient_evidence`
  - `conflicting_evidence`

- `support_level`
  - `none`
  - `low`
  - `medium`
  - `high`

The detailed result may also include:

- supporting origin groups;
- contradicting origin groups;
- not-evaluable origin groups;
- out-of-scope references;
- explanation codes;
- knowledge references.

The UI must preserve these semantics and must not convert an unknown or insufficient result into a guessed value.

---

## 3. Device Card — Identity

For a concrete device, **Device Card → Identity** is the primary detailed product surface for fingerprint information.

The Identity block should be able to show the full user-facing fingerprint summary:

```text
Identity

Platform          Android               HIGH
Device type       Smartphone            HIGH
Manufacturer      Samsung               MEDIUM
Model family      Galaxy S24            MEDIUM

Fingerprint status: Classified
```

If a dimension cannot be resolved, the card must show that honestly, for example:

```text
Model family      Unknown
Reason            Insufficient evidence
```

It must not fabricate a model, manufacturer, platform, or device type.

A detailed/expandable `Fingerprint details` section may expose diagnostic information such as:

- per-dimension status;
- support level;
- supporting evidence/origin groups;
- contradictory evidence/origin groups;
- explanation codes;
- relevant knowledge references.

This detailed information is intended for Admin/internal use and should not overload the default compact presentation.

---

## 4. Home → Online Devices

`Home → Online Devices` is a compact operational list and should **not** display every fingerprint field.

It may use a concise subset, for example:

```text
Device icon
Device type
Manufacturer / Model family
Platform
```

Example:

```text
📱 Samsung Galaxy S24 · Android
```

The exact compact composition is a UI decision and may evolve without changing Device Fingerprint architecture.

---

## 5. Other product surfaces

Any future CaptivPortal page or component may reuse only the fingerprint fields it needs.

Examples:

```text
Inventory page
→ manufacturer_family + model_family

Operating-system view
→ platform_family

Device-type statistics
→ device_class

Compact table
→ model_family only

Device Card
→ complete fingerprint summary

Engineering/debug view
→ complete per-dimension diagnostic metadata
```

A request such as:

> “Show only `model_family` in this table”

is a presentation/read-model task, **not** a change to Device Fingerprint classification semantics.

---

## 6. Single source of truth

The required data flow is conceptually:

```text
Evidence
    ↓
Device Fingerprint classifier
    ↓
Persisted / authoritative ClassificationResult
    ↓
Internal read/API boundary
    ↓
┌───────────────────────────┐
│ Home → Online Devices     │ → compact subset
│ Device Card → Identity    │ → detailed identity
│ Inventory                 │ → selected fields
│ Future Admin pages        │ → selected fields
└───────────────────────────┘
```

There must NOT be separate classification logic such as:

```text
Home classifier
Device Card classifier
Inventory classifier
```

All product surfaces consume the same authoritative fingerprint result.

---

## 7. No UI reinterpretation

Presentation layers may:

- choose which fields to display;
- choose labels/icons/layout;
- hide technical detail in compact views;
- expose additional detail in Admin-only views.

Presentation layers must NOT:

- recalculate classification;
- silently replace `unknown`;
- upgrade or downgrade `support_level`;
- convert `insufficient_evidence` into a guessed value;
- select a different manufacturer/model than the classifier result;
- create independent “best guess” logic.

The classifier result remains authoritative.

---

## 8. Product intent summary

The intended product model is:

```text
Fingerprint computes once.
Fingerprint stores structured identity.
Any internal UI can reuse it.
Each screen displays only what is useful there.
Device Card → Identity is the full user-facing identity view.
Home → Online Devices remains compact.
```

This separation lets CaptivPortal add new pages and presentations later without rebuilding or duplicating Device Fingerprint logic.

---

## 9. Implementation timing

This note is a future UI/read-model requirement.

It does not authorize implementation by itself.

The Device Fingerprint classification pipeline, persistence/read boundaries, and acceptance gates remain governed by the active Device Fingerprint architecture and roadmap.

UI integration should be implemented only after the authoritative fingerprint result/read path exists and has passed the required acceptance process.
