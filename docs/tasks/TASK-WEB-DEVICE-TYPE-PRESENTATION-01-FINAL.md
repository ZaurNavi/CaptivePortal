# TASK-WEB-DEVICE-TYPE-PRESENTATION-01 — Device Type and SNR Presentation — FINAL

Status: CLOSED / MERGED / DEPLOYED / PRODUCTION ACCEPTANCE PASS
Updated: 2026-09-13

## Identity

```text
PR=#120
baseline=144c8a922b4431293fdc1d4bb57bed29a8402f6b
publication commit=bf40a275d64fdde44125594048eae2a67616323d
merge / current production HEAD=3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5
accepted / merge / production tree=8312658be3ba272998f46212d9bad76950e3867e
changed files=4
diff stat=+154/-31
```

Changed files:

```text
app/admin_web/static/admin.css
app/admin_web/static/admin.js
app/admin_web/static/icons/README.md
tests/admin_web/test_admin_ui_frontend.py
```

Backend/API/DB/security contracts were not changed by this presentation task.

## Canonical Device Type presentation

Machine decisions use only the canonical server-provided key:

```javascript
device_type_key === "android"
```

The browser no longer normalizes raw `device_type`.

```text
frontend trim=NO
frontend lowercase=NO
frontend casefold=NO
frontend Unicode normalize=NO
frontend inference=NO
```

Raw `device_type` remains source/display text.

## Home → Online Devices

A `Type` column exists immediately after `Device / MAC`.

Android:

```text
decision=device_type_key === "android"
visual=repository-local Android SVG
constant adjacent "Android" text=NO
```

When both values are absent:

```text
device_type_key=null
device_type=null
→ NULL
```

Other valid types display the raw source text, for example `phone`.

No classification is inferred from hostname, system name, MAC, vendor, SSID,
AP, IP or history.

## Device Card

Device Card uses `device_type_key` for presentation decisions and raw
`device_type` for display/source text.

If a detail object owns its own `device_type_key`, that key has priority.

For `Latest Site snapshot`, `identity.device_type_key` may be used as the
presentation key when the snapshot raw type and identity raw type refer to the
same Device record.

The canonical machine key is not exposed as a separate user-facing field.

## Home SNR presentation

Source remains `item.snr`.

```text
SNR >= 25      -> good    / #10b956
15 <= SNR < 25 -> warning / #f2c20d
SNR < 15       -> danger  / #ed3038
null           -> neutral / existing "—"
```

No `Good / Warning / Poor` labels are added. RSSI and SNR remain independent;
there is no combined score and no backend classification.

## CSS scope

Home Online Devices geometry/presentation rules are scoped under:

```css
.live-section[aria-labelledby="devices-now-title"]
```

They must not modify unrelated `.live-table` surfaces such as Traffic tables.

An earlier over-broad FIX-3 candidate was rejected and never applied. It is not
part of the implementation history represented by this FINAL.

The accepted final visual state includes the later FIX-3A/FIX-3B corrections.
A small future cosmetic header-centering refinement remains deliberately
non-blocking.

## Acceptance

```text
Owner Visual Acceptance=PASS
Windows Central Lab V7 strict=PASS
Strict regressions=0
LAB commit=b6bf602873fcf4a41e21ced6c0fe1be18ce0f483
accepted LAB tree=8312658be3ba272998f46212d9bad76950e3867e
merge tree identity=PASS
```

Evidence log:

```text
C:\CaptivPortal-Lab\logs\lab-test-v7-strict-20260913-114135-DETACHED.log
```

## Production acceptance

```text
HEAD=3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5
TREE=8312658be3ba272998f46212d9bad76950e3867e
worktree=CLEAN
captive-portal.service=active
traffic-projection.service=active
root readiness=HTTP 400 expected without Omada parameters
PRODUCTION VISUAL ACCEPTANCE=PASS
```

Static artifact proof:

```text
admin.js worktree/head blob=564e2a3d59d99dd02570ec6a0239720e51e460f1
admin.css worktree/head blob=6552ae9221eb390cef54a4fcd13207dd3bc29fc6
```

No application restart was required because this task changed static JS/CSS
delivery only; the controlled checkout immediately exposed the new static files.
