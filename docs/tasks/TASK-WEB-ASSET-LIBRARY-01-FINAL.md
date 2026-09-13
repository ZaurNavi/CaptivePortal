# TASK-WEB-ASSET-LIBRARY-01 — Admin Web Local Asset Library — FINAL

Status: CLOSED / PRODUCTION PASS
Updated: 2026-09-12

## Final status

```text
TASK-WEB-ASSET-LIBRARY-01=CLOSED / PRODUCTION PASS
TASK-WEB-ASSET-LIBRARY-01-FIX-ANDROID-PRESENTATION=CLOSED / PRODUCTION PASS
```

## Purpose

Add a repository-local Admin Web icon asset library. The first production use is
a decorative Android icon displayed before the unchanged `device_type` text.

The icon is presentation only. It does not change source data, API semantics,
device classification or backend behavior.

## Initial implementation — PR #113

```text
branch=feature/web-asset-library-01
accepted commit=0b3a692684d5d87ca7b96cf75c722dda7e2e8cf3
PR=#113
merge=5d1a590d1d575eeea8148ca868b9de5183c0fff5
changed files=6
diff stat=+39/-1
```

Android asset:

```text
app/admin_web/static/icons/platforms/android.svg
SHA256=2f2411f1f05522e90049f8cbb06105fb553057efeadf772cdcc3ae24bbc8a6cc
```

Initial production matching used exact `"Android"`. Real production data supplied
`device_type=android`, so the icon did not render:

```text
"android" !== "Android"
```

Backend/API/data contracts remained correct. The defect was presentation-only.

## Production FIX — PR #114

```text
patch=TASK-WEB-ASSET-LIBRARY-01-FIX-ANDROID-PRESENTATION.patch
patch SHA256=c11bba2544124bc448f1d1a63a295dda479f0ab81cd430e2dbd6cc829509189b
baseline=5d1a590d1d575eeea8148ca868b9de5183c0fff5
branch=fix/web-asset-library-01-android-presentation
accepted commit=d207e048f0fcdec685d3bae1f8497fdbdcd611d4
PR=#114
merge / production=043a13bc1e3aa3353e27af1859dc0bb698df4955
changed files=4
diff stat=+68/-23
```

Final canonical predicate:

```text
typeof value === "string" && value.trim().toLowerCase() === "android"
```

Accepted forms include `android`, `Android`, `ANDROID` and leading/trailing-space
equivalents.

The original `device_type` text is displayed unchanged. `android` remains
visually `android`.

No inference is permitted from hostname, MAC, vendor, SSID, AP, IP, history or
any other field. Non-Android values do not receive the Android icon.

## Current coverage

```text
Devices list
Device Detail / Identity
Device Detail evidence
Observations when device_type is present
```

## Acceptance

```text
patch application=PASS
git diff --check=PASS
bounded Admin Web tests=12/12 PASS
case-insensitive Android matching=PASS
Devices list LAB visual=PASS
Device Detail Identity LAB visual=PASS
Device Detail evidence LAB visual=PASS
Owner visual acceptance=PASS
```

## Production

```text
HEAD=043a13bc1e3aa3353e27af1859dc0bb698df4955
tree=c2a9a01b2f8507c192fe2ef034ed4b9c850deed4
worktree=CLEAN
captive-portal.service=ACTIVE
admin.js=HTTP 200
android.svg=HTTP 200
served android.svg SHA256=2f2411f1f05522e90049f8cbb06105fb553057efeadf772cdcc3ae24bbc8a6cc
asset identity=PASS
service restart required for FIX=NO
Owner production visual acceptance=PASS
```

## Permanent boundary

```text
repository-local presentation asset=YES
external runtime icon dependency=NO
backend/API/data/security/business semantics changed=NO
device_type mutation=NO
platform inference=NO
```

## Later Device Type architecture supersession — 2026-09-13

The raw browser-owned case-insensitive Android predicate documented above remains
valid **historical acceptance evidence for this earlier task**.

It is no longer the current machine-decision contract.

Later accepted work:

```text
TASK-DEVICE-TYPE-NORMALIZATION-01 / PR #119
TASK-WEB-DEVICE-TYPE-PRESENTATION-01 / PR #120
```

established:

```text
device_type     = raw/source/display evidence
device_type_key = server-provided canonical machine key
Android decision = device_type_key === "android"
```

Current Admin Web must not reconstruct the key from raw `device_type`.
