# CAPTIVPORTAL ADMIN SETTINGS
## STAGE 6 — ADMIN PRODUCT BEHAVIOR / FEATURE CONTROLS
### TECH LEAD R1.1 CLARIFICATION ADDENDUM
### TL-S6-P1-07 — `WEB_ADMIN_ENABLED` / FEATURE-SUPPORTING-CONFIG VALIDATION GATE

**Project:** CaptivPortal  
**Role:** Architect  
**Parent documents:**  
- `STAGE 6 — ARCHITECTURE CONTRACT v0.1`  
- `STAGE 6 — ARCHITECTURE R1 ADDENDUM`  

**Status:** `ARCHITECTURE CLARIFICATION — NORMATIVE`  
**Precedence:** this clarification has precedence over any R1 wording that omitted the outer `WEB_ADMIN_ENABLED` gate.  
**Implementation TASK:** `HOLD until Tech Lead records PASS`  
**Coder:** `HOLD until implementation TASK authorization`  
**Schema change:** `NO`  
**Production change:** `NO`

---

# 1. EXACT DECISION

Stage 6 freezes:

```text
OPTION A
```

The exact condition for all Stage-6 graph-conditional supporting/prerequisite validation is:

```text
feature_support_validation_required(feature)
=
WEB_ADMIN_ENABLED == true
AND
configured_feature_state(feature) == enabled
```

This is the only admitted rule.

Therefore:

```text
WEB_ADMIN_ENABLED=false
```

means:

```text
admitted Feature preferences remain preservable;

registered SettingsDefinition scalars remain
primitive-validated unconditionally;

Stage-6 Feature-specific non-registered supporting configuration
is NOT evaluated;

Stage-6 Feature-specific semantic prerequisites
are NOT evaluated;

no Feature-supporting configuration object is required
solely for Stage-6 validation;

no features_configuration_adoption_failed may be produced
solely from dormant/inactive Admin product configuration.
```

---

# 2. `WEB_ADMIN_ENABLED` REMAINS OUTSIDE THE FEATURE GRAPH

`WEB_ADMIN_ENABLED` remains:

```text
deployment/bootstrap configuration
```

It is NOT:

```text
a Stage-6 Feature definition
a writable Settings Feature
a parent_feature_key
a persisted Feature override
```

Therefore the Feature preference graph continues to preserve:

```text
own configured Feature values
parent/child Feature relationships
dormant child preferences
```

independently of whether Admin Web is deployment-enabled.

The outer Admin bootstrap gate is applied only when deciding whether
Feature-specific supporting/prerequisite configuration must be evaluated.

---

# 3. REGISTERED SETTINGS SCALARS — UNCONDITIONAL

R1 §2.1 remains unchanged.

All registered SettingsDefinition scalars are primitive-validated
regardless of:

```text
WEB_ADMIN_ENABLED
Feature enabled/disabled/dormant state
consumer availability
runtime source health
```

This includes all existing General integer definitions and all 17
registered Stage-6 Feature boolean definitions.

Examples:

```text
WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS
→ always integer 60..300

WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS
→ always integer 60..300

WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
→ always integer 60..300

WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS
→ always integer 60..300

WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS
→ always integer 60..300

all 17 Stage-6 Feature definitions
→ always exact canonical "true" / "false"
```

`WEB_ADMIN_ENABLED=false` never suppresses primitive validation of
registered Settings values.

---

# 4. HOME LIVE SUPPORTING TUNING — EXACT GATE

Supporting configuration:

```text
WEB_ADMIN_HOME_LIVE_REQUEST_TIMEOUT_SECONDS
```

Validation condition:

```text
WEB_ADMIN_ENABLED=true
AND
configured_feature_state(home.live)=enabled
```

Only then require:

```text
integer 5..60
AND
> WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

If:

```text
WEB_ADMIN_ENABLED=false
home.live preference=true
supporting value invalid
```

result:

```text
Feature preference remains valid/preservable;
supporting value is not evaluated by Stage 6;
no Stage-6 validation failure;
no features_configuration_adoption_failed.
```

---

# 5. HOME TRAFFIC SUPPORTING TUNING — EXACT GATE

Supporting configuration:

```text
WEB_ADMIN_HOME_TRAFFIC_REQUEST_TIMEOUT_SECONDS
WEB_ADMIN_HOME_TRAFFIC_FRESH_MAX_AGE_SECONDS
WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS
WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS
```

Validation condition:

```text
WEB_ADMIN_ENABLED=true
AND
configured_feature_state(home.traffic)=enabled
```

Only then apply the accepted Home Traffic structural/range/relationship
validation.

If Admin Web is disabled, these Stage-6 supporting values are not
evaluated solely because the Feature preference is true.

Registered General values such as:

```text
WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS
WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE
```

remain primitive-validated unconditionally.

---

# 6. HOME ACTIVITY SUPPORTING TUNING — EXACT GATE

Supporting configuration:

```text
WEB_ADMIN_HOME_ACTIVITY_REQUEST_TIMEOUT_SECONDS
WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_FRESH_MAX_AGE_SECONDS
WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_STALE_MAX_AGE_SECONDS
```

Validation condition:

```text
WEB_ADMIN_ENABLED=true
AND
configured_feature_state(home.activity)=enabled
```

Only then apply the accepted Activity tuning validation.

Registered:

```text
WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS
```

remains unconditionally primitive-validated.

---

# 7. HOME ACTIVITY SITE CONTEXT — EXACT GATE

Supporting/prerequisite configuration:

```text
WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON
```

Validation condition:

```text
WEB_ADMIN_ENABLED=true
AND
configured_feature_state(home.activity)=enabled
```

Only then require the accepted:

```text
valid JSON object
no duplicate members
valid Site IDs
valid timezone
coverage timestamps
scope relationships
```

When:

```text
WEB_ADMIN_ENABLED=false
home.activity preference=true
WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON invalid
```

Stage-6 result is:

```text
preference preserved
Site-context prerequisite not evaluated
no Stage-6 mutation/startup rejection from this field
```

---

# 8. HOME ACTIVITY CURRENT STATE PREREQUISITES — EXACT GATE

The following are semantic prerequisites of Home Activity:

```text
CURRENT_STATE_ENABLED=true
valid/non-empty Current State Site scope
valid/non-empty Current State guest SSID scope
Activity Site context within admitted Admin/Current-State scope
```

They are evaluated only when:

```text
WEB_ADMIN_ENABLED=true
AND
configured_feature_state(home.activity)=enabled
```

Therefore:

```text
WEB_ADMIN_ENABLED=false
home.activity preference=true
CURRENT_STATE_ENABLED=false
```

is a valid preserved Stage-6 preference state.

It does not authorize Home Activity runtime composition because Admin Web
itself is deployment-disabled.

---

# 9. HOME HEALTH SUPPORTING TUNING — EXACT GATE

Supporting configuration:

```text
WEB_ADMIN_HOME_HEALTH_REQUEST_TIMEOUT_SECONDS
WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS
```

Validation condition:

```text
WEB_ADMIN_ENABLED=true
AND
configured_feature_state(home.health)=enabled
```

Only then apply the accepted range/relationship checks.

Registered:

```text
WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS
```

remains unconditionally primitive-validated.

---

# 10. DEVICE LIST CURSOR SECRET — EXACT GATE

Supporting prerequisite:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET
```

Validation condition:

```text
WEB_ADMIN_ENABLED=true
AND
configured_feature_state(devices.list_context)=enabled
```

Only then require the accepted structural secret format.

Therefore:

```text
WEB_ADMIN_ENABLED=false
devices.list_context preference=true
cursor secret invalid/absent
```

does NOT reject the Stage-6 preference and does NOT cause
`features_configuration_adoption_failed`.

The secret remains deployment-owned and non-writable.

---

# 11. TRAFFIC ROOT SUPPORTING TUNING — EXACT GATE

Supporting configuration:

```text
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS
```

Validation condition:

```text
WEB_ADMIN_ENABLED=true
AND
configured_feature_state(traffic.root)=enabled
```

Only then apply:

```text
integer 5..60
AND
> WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

Registered:

```text
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
```

remains unconditionally primitive-validated.

---

# 12. TRAFFIC PROJECTION READ CONFIGURATION — EXACT GATE

Supporting/prerequisite configuration:

```text
TRAFFIC_PROJECTION_DB_PATH
OBSERVATION_DB_PATH
OBSERVATION_SITE_IDS
```

Validation condition:

```text
WEB_ADMIN_ENABLED=true
AND
configured_feature_state(traffic.projection_read)=enabled
```

Only then require the accepted Stage-6 read-side structural checks:

```text
absolute/non-empty paths
projection path != Observation path
valid/non-empty Observation Site scope
```

The following remain explicitly NOT required by the Stage-6 read consumer:

```text
TRAFFIC_PROJECTION_ENABLED=true
traffic-projection.service active
writer lock availability
projection DB current health/readiness
```

If:

```text
WEB_ADMIN_ENABLED=false
traffic.projection_read preference=true
projection read supporting config invalid
```

then:

```text
preference remains preservable;
projection configuration is not validated/probed/opened;
no projection read runtime is composed from Stage 6;
no features_configuration_adoption_failed solely from this configuration.
```

---

# 13. COMPLETE STAGE-6 CONDITIONAL VALIDATION MATRIX

```text
HOME LIVE
supporting tuning
→ WEB_ADMIN_ENABLED
  AND configured_feature_state(home.live)=enabled

HOME TRAFFIC
supporting tuning
→ WEB_ADMIN_ENABLED
  AND configured_feature_state(home.traffic)=enabled

HOME ACTIVITY
supporting tuning
→ WEB_ADMIN_ENABLED
  AND configured_feature_state(home.activity)=enabled

HOME ACTIVITY
Site context
→ WEB_ADMIN_ENABLED
  AND configured_feature_state(home.activity)=enabled

HOME ACTIVITY
Current State prerequisites
→ WEB_ADMIN_ENABLED
  AND configured_feature_state(home.activity)=enabled

HOME HEALTH
supporting tuning
→ WEB_ADMIN_ENABLED
  AND configured_feature_state(home.health)=enabled

DEVICE LIST CONTEXT
cursor secret
→ WEB_ADMIN_ENABLED
  AND configured_feature_state(devices.list_context)=enabled

TRAFFIC ROOT
supporting tuning
→ WEB_ADMIN_ENABLED
  AND configured_feature_state(traffic.root)=enabled

TRAFFIC PROJECTION READ
paths / Site scope
→ WEB_ADMIN_ENABLED
  AND configured_feature_state(traffic.projection_read)=enabled
```

There are no Stage-6 exceptions to this matrix.

---

# 14. REQUIRED EXAMPLE — FROZEN

Given:

```text
WEB_ADMIN_ENABLED=false

WEB_ADMIN_HOME_ACTIVITY_ENABLED=true

WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON=<invalid>

CURRENT_STATE_ENABLED=false

WEB_ADMIN_HOME_ACTIVITY_REQUEST_TIMEOUT_SECONDS=<invalid>
```

and assuming all registered SettingsDefinition scalars themselves are
primitive-valid:

```text
Stage-6 Feature preference =
PRESERVED

Feature-specific supporting/prerequisite validation =
SKIPPED

Stage-6 validation result from those supporting values =
PASS

features_configuration_adoption_failed =
NO
```

This does NOT claim those values would be acceptable if Admin Web were
later enabled.

---

# 15. LATER ENABLEMENT OF ADMIN WEB — FROZEN

If deployment later changes:

```text
WEB_ADMIN_ENABLED=false
→ true
```

then on the next main-process startup the same preserved Feature
preferences are re-evaluated.

For every Feature whose:

```text
configured_feature_state(feature)=enabled
```

Stage-6 supporting/prerequisite validation becomes mandatory.

Therefore an invalid previously dormant supporting configuration may
then:

```text
fail startup candidate validation
or
produce the accepted positive structural adoption failure
where composition reaches the activation-attestation boundary
```

according to the existing Stage-6 startup/adoption contract.

Stage 6 does not silently auto-disable the Feature.

Stage 6 does not rewrite the Feature preference.

---

# 16. STARTUP VALIDATION — FROZEN

Main startup uses exactly:

```text
WEB_ADMIN_ENABLED
AND configured_feature_state(feature)=enabled
```

for every Stage-6 supporting/prerequisite validation decision.

Therefore:

```text
WEB_ADMIN_ENABLED=false
```

means:

```text
build/preserve the Feature preference graph
but do not require Stage-6 Admin-product supporting composition.
```

Registered Settings scalars remain primitive-validated.

No raw child boolean may bypass the outer Admin bootstrap gate.

---

# 17. GENERAL MUTATION — FROZEN

General mutation candidate validation uses the same rule:

```text
WEB_ADMIN_ENABLED
AND configured_feature_state(feature)=enabled
```

No alternate General-domain path may invoke Stage-6 feature-specific
supporting/prerequisite validation while Admin Web is disabled.

Existing General-domain Controller-secret semantics remain unchanged.

Registered scalars remain primitive-validated.

---

# 18. CONTROLLER MUTATION — FROZEN

Controller ordinary mutation candidate validation uses the same rule:

```text
WEB_ADMIN_ENABLED
AND configured_feature_state(feature)=enabled
```

No alternate Controller-domain validation path may reject preserved
Feature preferences solely because Admin Web is disabled and optional
Stage-6 supporting configuration is invalid.

Existing Controller secret semantics remain unchanged.

---

# 19. PORTAL MUTATION — FROZEN

Portal mutation candidate validation uses the same rule:

```text
WEB_ADMIN_ENABLED
AND configured_feature_state(feature)=enabled
```

Portal remains secret-isolated exactly as already accepted.

No Stage-6 supporting/prerequisite configuration is evaluated when
Admin Web is disabled.

Registered Settings scalars remain primitive-validated.

---

# 20. FEATURES MUTATION — FROZEN

Features mutation candidate validation uses:

```text
1. unconditionally validate registered General primitive scalars;

2. unconditionally validate all registered Feature primitive scalars;

3. derive the candidate Feature graph;

4. if WEB_ADMIN_ENABLED=false:
   skip all Stage-6 Feature-specific supporting/prerequisite checks;

5. if WEB_ADMIN_ENABLED=true:
   evaluate supporting/prerequisite checks only for
   configured_feature_state(feature)=enabled.
```

Therefore Feature preferences can be prepared/preserved while Admin Web
is deployment-disabled.

---

# 21. `features_configuration_adoption_failed` — EXACT GATE

`features_configuration_adoption_failed` may only be emitted from
positive in-process evidence when:

```text
WEB_ADMIN_ENABLED=true

AND

effective_feature_state(feature)=enabled

AND

the required Stage-6 runtime composition for that Feature
is structurally inconsistent/missing after successful configuration
validation.
```

It MUST NOT be emitted solely because:

```text
WEB_ADMIN_ENABLED=false

Feature own preference=true

supporting/prerequisite configuration is invalid/incomplete

Admin runtime is intentionally absent
```

---

# 22. RELATION TO `AdminFeaturePlanV1`

The one startup `AdminFeaturePlanV1` remains constructed even when:

```text
WEB_ADMIN_ENABLED=false
```

so that Feature preferences and graph relationships remain deterministic
and preservable.

However:

```text
WEB_ADMIN_ENABLED=false
```

means there is no active Stage-6 Admin product consumer.

The plan MUST NOT cause:

```text
Feature-supporting config parsing
projection-read configuration validation
Admin product source composition
Home Health optional-product expectations
Stage-6 activation failure
```

solely from a true Feature preference while Admin is deployment-disabled.

This does not make `WEB_ADMIN_ENABLED` a Feature parent.

It is an outer deployment/bootstrap gate.

---

# 23. GENERAL `consumer_state` RELATION

R1 §4 remains effective-state based.

When Admin Web is deployment-disabled, admitted Stage-6 General consumers
are not running product consumers.

Therefore General read projection MUST NOT claim such a consumer is
active merely because the stored/adopted Feature preference is true.

The exact General read implementation must use the effective runtime
Feature-consumer eligibility that includes the Admin bootstrap gate.

Thus:

```text
WEB_ADMIN_ENABLED=false
+ Feature preference=true
→ admitted Feature consumer is not active
```

and affected General consumer rows must not report `active`.

Deferred AP-24H remains governed by its previously frozen separate
consumer semantics.

---

# 24. NO CASCADE / NO PREFLIGHT REWRITE

When Admin Web is disabled, Stage 6 MUST NOT automatically:

```text
set Feature preferences false

clear Feature persisted overrides

repair optional supporting config

materialize deployment defaults

write audit rows for derived disablement
```

The desired Feature preferences remain exactly as configured.

---

# 25. TEST / ACCEPTANCE MATRIX ADDITION

Mandatory cases:

```text
CASE A
WEB_ADMIN_ENABLED=false
Feature=true
supporting config valid
→ PASS / preference preserved

CASE B
WEB_ADMIN_ENABLED=false
Feature=true
supporting config invalid
→ PASS / preference preserved
→ no supporting-config evaluation

CASE C
WEB_ADMIN_ENABLED=false
Feature=false
supporting config invalid
→ PASS

CASE D
WEB_ADMIN_ENABLED=true
Feature=false
supporting config invalid
→ PASS

CASE E
WEB_ADMIN_ENABLED=true
Feature=dormant_parent_disabled
supporting config invalid
→ PASS

CASE F
WEB_ADMIN_ENABLED=true
Feature=enabled
supporting config valid
→ PASS

CASE G
WEB_ADMIN_ENABLED=true
Feature=enabled
supporting config invalid
→ validation failure

CASE H
Admin changes false→true outside writable Settings domain;
preserved Feature=true;
supporting config invalid
→ next startup MUST evaluate and fail closed
→ Feature preference not rewritten
```

Run the same semantic cases through:

```text
main startup
General mutation
Controller mutation
Portal mutation
Features mutation
```

---

# 26. NORMATIVE FORMULA

The final Stage-6 validation rule is:

```text
registered_scalar_validation_required(setting)
=
true
```

and:

```text
stage6_supporting_validation_required(feature)
=
WEB_ADMIN_ENABLED
AND
configured_feature_state(feature) == enabled
```

and runtime structural adoption rule is:

```text
stage6_runtime_composition_required(feature)
=
WEB_ADMIN_ENABLED
AND
effective_feature_state(feature) == enabled
```

These formulas supersede any R1 wording that stated only:

```text
configured_feature_state(feature)=enabled
```

without the outer Admin bootstrap gate.

---

# 27. FINAL DISPOSITION

```text
TL-S6-P1-07 =
CLOSED

SELECTED OPTION =
A

FEATURE SUPPORT VALIDATION GATE =
WEB_ADMIN_ENABLED=true
AND
configured_feature_state(feature)=enabled

RUNTIME COMPOSITION GATE =
WEB_ADMIN_ENABLED=true
AND
effective_feature_state(feature)=enabled

REGISTERED SETTINGS SCALAR VALIDATION =
UNCONDITIONAL

WEB_ADMIN_ENABLED=false
+
FEATURE=true
+
INVALID SUPPORTING CONFIG =
VALID PRESERVED FEATURE PREFERENCE;
SUPPORTING CONFIG NOT EVALUATED;
NO STAGE-6 ADOPTION FAILURE SOLELY FROM IT

STARTUP =
SAME RULE

GENERAL MUTATION =
SAME RULE

CONTROLLER MUTATION =
SAME RULE

PORTAL MUTATION =
SAME RULE

FEATURES MUTATION =
SAME RULE

OPEN P0 =
0

OPEN P1 =
0

ARCHITECTURE =
PASS

IMPLEMENTATION TASK PREPARATION =
GO

CODER =
HOLD UNTIL ACCEPTED IMPLEMENTATION TASK

SCHEMA CHANGE =
NO — UNTIL IMPLEMENTATION AUTHORIZATION

PRODUCTION CHANGE =
NO
```
