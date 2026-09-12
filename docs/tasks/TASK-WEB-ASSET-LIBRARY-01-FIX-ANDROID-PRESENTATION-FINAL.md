# TASK-WEB-ASSET-LIBRARY-01-FIX-ANDROID-PRESENTATION — FINAL

Status: CLOSED / PRODUCTION PASS
Updated: 2026-09-12

## Root cause

```text
real production value=android
initial predicate=exact "Android"
"android" !== "Android"
```

The defect was presentation matching only. Backend/API/data contracts were not
defective.

## Accepted FIX

```text
baseline=5d1a590d1d575eeea8148ca868b9de5183c0fff5
patch SHA256=c11bba2544124bc448f1d1a63a295dda479f0ab81cd430e2dbd6cc829509189b
accepted commit=d207e048f0fcdec685d3bae1f8497fdbdcd611d4
branch=fix/web-asset-library-01-android-presentation
PR=#114
merge=043a13bc1e3aa3353e27af1859dc0bb698df4955
changed files=4
diff stat=+68/-23
```

Canonical predicate:

```text
typeof value === "string" && value.trim().toLowerCase() === "android"
```

Source text remains unchanged. No inference from any other field is allowed.

## Acceptance / production

```text
git diff --check=PASS
bounded Admin Web tests=12/12 PASS
case-insensitive matching=PASS
Owner LAB visual acceptance=PASS
production delivery verification=PASS
Owner production visual acceptance=PASS
restart required=NO
HEAD=043a13bc1e3aa3353e27af1859dc0bb698df4955
tree=c2a9a01b2f8507c192fe2ef034ed4b9c850deed4
captive-portal.service=ACTIVE
```
