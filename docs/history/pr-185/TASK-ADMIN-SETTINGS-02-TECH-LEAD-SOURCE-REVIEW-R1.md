# TASK-ADMIN-SETTINGS-02 — TECH LEAD SOURCE REVIEW R1

**Task:** TASK-ADMIN-SETTINGS-02 — OMADA CONTROLLER READ MODEL  
**Architecture:** FINAL / TECH LEAD ACCEPTED  
**Binding addendum:** TL-AS02-F1  
**Candidate patch SHA256:** `3d7fa0ef132ca0c5530b3ca0e14e730366764bb7c3094bea97420dab1bb950a6`  
**Candidate tree:** `ab0c754dde834a415faac0a089771a5c7ab737ca`  
**Review disposition:** HOLD — FIX1 REQUIRED

---

## 1. Independent verification completed

Tech Lead independently verified:

```text
PATCH_BYTES = 67595
PATCH_SHA256 = 3d7fa0ef132ca0c5530b3ca0e14e730366764bb7c3094bea97420dab1bb950a6

LAB_ONLY_HEAD = 83e6069b803030d2309d1a356eb9d5d7a3b1a1c6
LAB_ONLY_TREE = ab0c754dde834a415faac0a089771a5c7ab737ca
LAB_ONLY_WORKTREE = CLEAN
```

Independent test reruns:

```text
focused Settings/Controller = 107 PASS
direct Admin/Omada/Portal compatibility = 268 PASS
affected application wiring = 30 PASS
startup compatibility = 13 PASS

compileall = PASS
controller_settings.js node syntax = PASS
git diff --check = PASS
```

No publication commit, push, PR, merge or production action is authorized yet.

---

# 2. SOURCE REVIEW RESULT

Core Stage-2 architecture is implemented correctly:

```text
one OmadaControllerRuntimeConfig
shared provider injection
no provider-side get_settings fallback
safe public snapshot
secret-presence only
GLOBAL controller read capability
SettingsStore independence
zero Omada/OAuth read-path I/O
bounded app/web/web.py fallback
dedicated read-only Controller JS
no systemd / production authority
```

However two contract mismatches remain open.

```text
OPEN P0 = 0
OPEN P1 = 2
```

---

# 3. P1-01 — API GET incorrectly accepts a non-empty request body

## Contract

Stage-2 API request contract is:

```text
GET /admin/api/v1/settings/controller

no query parameters
no request body
```

Unexpected request content must not silently participate in a successful read.

## Current candidate

`controller_settings_read()` checks `request.args`, but does not reject a non-empty request body.

Independent Tech Lead reproduction against the clean candidate:

```text
GET /admin/api/v1/settings/controller
Content-Type: application/octet-stream
body = "body"

CURRENT RESULT = 200
```

This violates the frozen request contract.

## Required FIX1

For the Controller API route only:

```text
non-empty request body
→ 400 invalid_request
```

Requirements:

- do not parse arbitrary request-body schema;
- do not introduce a body contract;
- preserve GET-only semantics;
- no secret/config logging;
- preserve no-store/no-cache headers.

Add focused regression proving at minimum:

```text
GET with non-empty body → 400 invalid_request
GET without body → existing 200 behavior
```

---

# 4. P1-02 — Controller UI does not conform to the accepted UI contract

## Frozen architecture

Required UI semantics:

```text
Page heading:
Controller

Provider identity:
Omada Controller

Success status:
Read-only effective startup configuration.

Unavailable status:
Controller configuration is unavailable.
```

## Current candidate

Current route uses:

```text
title = "Controller Settings"
```

Current template subtitle is:

```text
Installation-level configuration adopted at startup.
Deployment-controlled and read-only;
this page does not check Controller connectivity.
```

Current JS success state is:

```text
Startup configuration — deployment-controlled.
No connection test performed.
```

Current unavailable wording is:

```text
Controller configuration read unavailable.
```

The safe semantics are generally correct, but the accepted UI contract was explicit and the provider identity is missing entirely.

## Required FIX1

Make the Controller page conform:

```text
<h1>Controller</h1>

visible provider identity:
Omada Controller

success state:
Read-only effective startup configuration.

unavailable state:
Controller configuration is unavailable.
```

`Loading Controller configuration…` is already correct and may remain.

Additional explanatory text such as `Deployment-controlled` / `No connection test performed` may remain separately, provided it does not replace the required canonical status/provider identity and does not imply health/connectivity.

Add focused UI tests for:

```text
heading = Controller
provider identity = Omada Controller
canonical success status present
canonical unavailable status present
```

---

# 5. No other source-review blockers found in R1

The following reviewed areas are accepted as implemented:

```text
Omada URL validation semantics
runtime config immutability
client_secret repr suppression
safe public projection
source provenance vocabulary
mandatory injected provider config
create_app bounded fallback
read-service isolation
GLOBAL authorization
capability-aware Settings navigation
Settings-domain page shell
separate controller_settings.js
canonical API success schema
canonical error envelope/version
SettingsStore independence
Stage-1 12-key allowlist preservation
zero live Controller probe
projection failure isolation
Portal/Auth/CAPPORT compatibility
```

---

# 6. FIX1 delivery requirements

Coder should make only the bounded FIX1 changes above.

Do not create publication commit yet unless Tech Lead explicitly authorizes after re-review.

Return:

```text
new candidate tree
new complete patch
new patch SHA256
exact changed files since R1
focused test results
compatibility results if touched shared routes/templates
compileall
node --check
git diff --check
```

At minimum rerun:

```text
tests/test_admin_controller_settings.py
tests/admin_web/test_settings_routes.py
tests/admin_web/test_settings_ui.py
```

and the existing Stage-2 focused gate.

---

# 7. Final R1 disposition

```text
SOURCE REVIEW = HOLD

P0 = 0
P1 = 2

P1-01 = reject non-empty Controller API request body
P1-02 = conform Controller UI heading/provider/status wording

CORE ARCHITECTURE = PASS
SECRET BOUNDARY = PASS
ZERO OMADA I/O = PASS
COMPATIBILITY = PASS

PUBLICATION COMMIT = HOLD
PUSH = HOLD
PR = HOLD
MERGE = HOLD
PRODUCTION = HOLD

CODER = GO FOR FIX1 ONLY
```
