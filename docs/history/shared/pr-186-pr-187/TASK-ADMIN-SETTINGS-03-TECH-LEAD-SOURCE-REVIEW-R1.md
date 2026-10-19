# TASK-ADMIN-SETTINGS-03 — TECH LEAD SOURCE REVIEW R1

**Task:** `TASK-ADMIN-SETTINGS-03`  
**Candidate commit:** `913b500076d9b831fb0cdc0e3fae142b7742a1a3`  
**Candidate tree:** `7a2782876f1060fb7297014ce1c6c95dec8df9c3`  
**Parent / baseline:** `c1167180daec9ca17d13ab44326f143122db8d5e`  
**Baseline tree:** `278df41bfa3134b22963b41006585da35de08074`  
**Disposition:** **HOLD — bounded FIX1 required**

---

## 1. Artifact identity — independently verified

```text
COMMIT = 913b500076d9b831fb0cdc0e3fae142b7742a1a3
PARENT = c1167180daec9ca17d13ab44326f143122db8d5e
TREE   = 7a2782876f1060fb7297014ce1c6c95dec8df9c3
SUBJECT= ADMIN-SETTINGS-03: add writable non-secret Omada Controller settings

WORKTREE = CLEAN
CHANGED_FILES = 33
DIFFSTAT = +1180 / -205
```

The supplied full-index patch was independently regenerated from exact BASE→CANDIDATE and matched byte-for-byte:

```text
PATCH_BYTES  = 134355
PATCH_SHA256 = 5ecdaaef0132dfe71eee267814a85b5de53437d3750983ab137f343189397ae3
```

No baseline drift was observed during review.

---

## 2. Independent verification

### Focused

```text
186 passed
```

### Affected runtime / integration

Independent Tech Lead run:

```text
2404 passed
27 skipped
1 failed
```

The only failure was:

```text
tests/admin_web/test_home_traffic.py::
test_home_template_delivers_traffic_only_when_enabled
```

The exact same failure was independently rerun on the untouched accepted baseline:

```text
HEAD=c1167180daec9ca17d13ab44326f143122db8d5e
same assertion
same actual [6850, 10547, 10471]
same expected [6850, 10471, 10547]
```

Therefore this failure is **baseline-known / non-Stage-3** and is not an AS03 implementation blocker.

### Static

```text
python -m compileall -q app run.py = PASS
node --check app/admin_web/static/controller_settings.js = PASS
git diff --check BASE CANDIDATE = PASS
```

---

## 3. Architecture areas that PASS

The following implementation areas were source-reviewed and are accepted for R1:

```text
EXACT THREE WRITABLE KEYS
= PASS

OMADA_CLIENT_SECRET EXCLUSION
= PASS

VERIFY_SSL READ-ONLY
= PASS

ONE COMMON REGISTRY / 15 DEFINITIONS
= PASS

GENERAL DOMAIN REMAINS 12
= PASS

ONE SETTINGSSTORE
= PASS

SCHEMA v1 → v2
= PASS

TYPED INTEGER + STRING OVERRIDES
= PASS

TRANSACTIONAL v1→v2 MIGRATION
= PASS

MIGRATED GENERAL IDEMPOTENCY DOMAIN
= PASS

MIGRATED GENERAL AUDIT DOMAIN/TYPE
= PASS

GLOBAL GENERATION / CAS
= PASS

COMMON MUTATION ENGINE
= PASS

CONTROLLER MUTATION DOMAIN ISOLATION
= PASS

BOUNDED MUTATION RECEIPT
= PASS

DURABLE IDEMPOTENT REPLAY
= PASS

CANONICAL CONTROLLER NORMALIZATION
= PASS

CLEAR-OVERRIDE VALIDATION
= PASS

CONFIGURED/EFFECTIVE/PENDING SPLIT
= PASS

EFFECTIVE STARTUP GENERATION PROVENANCE
= PASS

ZERO OMADA/OAUTH READ-PATH I/O
= PASS

WRITE CAPABILITY SEPARATION
= PASS

ADMIN JSON CARVEOUT
= PASS

SETTINGS-ENABLED STARTUP FAIL-CLOSED
= PASS

DURABLE ADOPTION BEFORE CONTROLLER WORKERS
= PASS

HTTP SERVING AFTER ADOPTION
= PASS

ADMIN PROJECTION FAILURE NON-CORE
= PASS

NO LIVE CONNECTION TEST
= PASS

NO HOT RECONNECT / NO SYSTEMD AUTHORITY
= PASS

SECRET NON-DISCLOSURE
= PASS
```

---

# 4. OPEN P1-01 — arbitrary configured-read failures are silently misclassified as SettingsStore outage

## Candidate behavior

In:

```text
app/admin_web/controller_settings.py
ControllerConfigurationReadService.read()
```

the candidate currently does logically:

```python
try:
    configured = configured_read_service.read_controller()
except Exception:
    configured = None
```

and then returns:

```text
HTTP 200
store_state = unavailable
effective-only model
```

for **every exception class**.

This is too broad.

The architecture authorizes effective-only `200` specifically when the already-adopted process loses trustworthy access to the SettingsStore.

It separately defines Controller read-side projection failure as:

```text
503 controller_settings_read_unavailable
```

## Independent proof

A Tech Lead probe injected:

```text
configured_read_service.read_controller()
→ RuntimeError("synthetic projection bug")
```

Current candidate result:

```text
RETURNED unavailable None 7
```

That is, an arbitrary programming/projection failure is converted into a fake Store outage and a successful 200-style effective-only model.

This masks internal projection defects and gives a false `store_state`.

## Required FIX1

Bound the degrade path.

Required semantics:

```text
actual configured-side SettingsStore unavailability
→ effective-only Controller V2 model
→ store_state = unavailable
→ HTTP 200

unexpected/non-store configured projection failure
→ propagate out of ControllerConfigurationReadService.read()
→ route returns
   503 controller_settings_read_unavailable
```

Recommended implementation shape:

```python
try:
    configured = configured_read_service.read_controller()
except SettingsError as error:
    if error.code != "settings_store_unavailable":
        raise
    configured = None
```

Equivalent safe implementation is allowed.

Also:

```text
configured_read_service missing / malformed while Stage-3 Controller Settings is active
```

must not silently become an effective-only Store outage. Treat it as Controller read-surface unavailable.

Required tests:

```text
FIX1-R01 SettingsError(settings_store_unavailable)
         → 200 effective-only / store_state=unavailable

FIX1-R02 unexpected RuntimeError from configured read boundary
         → 503 controller_settings_read_unavailable

FIX1-R03 non-store SettingsError from configured boundary
         → 503 controller_settings_read_unavailable

FIX1-R04 missing configured read boundary in active Stage-3 composition
         → unavailable / not fake Store outage
```

---

# 5. OPEN P1-02 — canonical Store-outage Controller V2 field `mutation_available=false` is missing

The accepted architecture explicitly freezes the running-process Store-loss response with:

```text
store_state = unavailable
configured_generation = null
activation_state = null
restart_required = null
mutation_available = false
...
effective_generation / effective values remain
```

The candidate currently emits no `mutation_available` property at all.

Behaviorally, the browser derives editability from:

```text
store_state == available
```

so mutation is disabled, but the API contract is incomplete.

This is an API/read-model contract issue, not merely a UI wording issue.

## Required FIX1

Add canonical mutation availability to Controller V2.

Freeze for implementation:

```text
store available + configured control-plane read available
→ mutation_available = true

Store unavailable effective-only response
→ mutation_available = false
```

This field describes control-plane availability, **not principal authorization**. Browser write affordance remains additionally gated by:

```text
admin.write.settings.controller
```

Controller UI should use the server field rather than independently reconstructing Store mutation availability where practical.

Required tests:

```text
FIX1-M01 normal V2 read
         → mutation_available=true

FIX1-M02 post-adoption Store outage
         → mutation_available=false

FIX1-M03 read-only principal
         → API availability may remain true
         → edit controls still absent due write capability

FIX1-M04 Store unavailable
         → edit controls disabled/absent
```

---

# 6. Non-blocking notes

These do not currently hold publication:

```text
N1. UI renders persisted_override_value=null as "Unavailable".
    For Store-available/no-override state, wording such as "No override" would be clearer.
    This is UX polish, not a P1 architecture violation.

N2. The common SettingsReadService is passed as the configured boundary object.
    Current Admin code only calls its safe read_controller() projection and does not inspect
    the full settings mapping. Keep that restriction; do not widen Admin access in FIX1.
```

No scope expansion is requested for these notes.

---

# 7. FIX1 allowed scope

Coder is authorized for **bounded FIX1 only**.

Expected production files:

```text
app/admin_web/controller_settings.py
app/admin_web/static/controller_settings.js        [only if consuming mutation_available]
app/admin_web/runtime.py                           [only if boundary validation/composition needs it]
```

Expected tests:

```text
tests/admin_web/test_controller_settings_stage3.py
tests/admin_web/test_controller_settings_stage3_frontend.py
tests/admin_web/controller_settings_stage3_ui.cjs
tests/settings_control/test_controller_stage3.py   [only if useful for direct service proof]
tests/test_admin_controller_settings.py            [only if compatibility assertion needed]
```

If another production file is required:

```text
STOP
return exact file + reason
```

Do not modify schema/migration/mutation/startup ordering for FIX1 unless a failing regression proves it is necessary.

---

# 8. FIX1 verification required

Run at minimum:

```text
focused Stage-3 suite
affected Admin Controller suite
tests/settings_control
tests/settings_control/test_run_integration.py

python -m compileall -q app run.py
node --check app/admin_web/static/controller_settings.js
git diff --check
```

A new full repository run is not required solely for these two bounded Controller read/UI corrections unless FIX1 unexpectedly widens beyond the files above.

Return:

```text
FIX1_COMMIT=
FIX1_PARENT=913b500076d9b831fb0cdc0e3fae142b7742a1a3
FIX1_TREE=

FIX1_CHANGED_FILES=
FULL_BASE_TO_FIX1_PATCH_PATH=
FULL_PATCH_BYTES=
FULL_PATCH_SHA256=

FOCUSED_TESTS=
CONTROLLER_TESTS=
COMPILEALL=
NODE_CHECK=
GIT_DIFF_CHECK=

P1-01=CLOSED evidence
P1-02=CLOSED evidence

PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```

The review artifact must still be the complete:

```text
BASE c116718... → FIX1 candidate
```

patch.

---

# 9. Current gate

```text
TASK-ADMIN-SETTINGS-03 SOURCE REVIEW R1

ARTIFACT IDENTITY                 = PASS
PATCH IDENTITY                    = PASS
BASELINE                          = PASS

SCHEMA / MIGRATION                = PASS
REGISTRY / TYPING                 = PASS
GENERAL BACKWARD COMPATIBILITY    = PASS
CONTROLLER MUTATION               = PASS
IDEMPOTENCY                       = PASS
VALIDATION                        = PASS
SECRET BOUNDARY                   = PASS
STARTUP FAIL-CLOSED               = PASS
ADOPTION / I-O ORDERING           = PASS
UI WRITE FLOW                     = PASS WITH FIX1 READ-MODEL ITEMS

KNOWN FULL-SUITE FAILURE           = BASELINE / NON-BLOCKING

OPEN P0                           = 0
OPEN P1                           = 2

P1-01 CONFIGURED READ FAILURE     = OPEN
P1-02 mutation_available FIELD    = OPEN

CANDIDATE                         = HOLD
PUBLICATION COMMIT                = HOLD
PUSH                              = HOLD
PR                                = HOLD
MERGE                             = HOLD
DEPLOY                            = HOLD
PRODUCTION                        = HOLD

CODER                             = GO FOR BOUNDED FIX1 ONLY
```
