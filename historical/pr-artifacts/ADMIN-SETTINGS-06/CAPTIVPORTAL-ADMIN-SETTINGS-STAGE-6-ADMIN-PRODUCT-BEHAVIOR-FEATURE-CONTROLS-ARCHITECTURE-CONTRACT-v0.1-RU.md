# CAPTIVPORTAL ADMIN SETTINGS
## STAGE 6 — ADMIN PRODUCT BEHAVIOR / FEATURE CONTROLS
### ARCHITECTURE CONTRACT v0.1
### DRAFT FOR TECH LEAD REVIEW

**Проект:** CaptivPortal  
**Роль:** Architect  
**Baseline:** `main@701ce630b595a87e9350b826a06ee02eaebc7f9e`  
**TREE:** `59425257b1b9ddd557113da158c88d58bfe06bfc`  
**Current Settings schema:** `v4`  
**Production Settings state:** `configured_generation=0`, `effective_generation=0`  
**Stage 0–5:** `CLOSED / PRODUCTION ACCEPTED`  
**Stage-5 UI remediation:** `CLOSED / PRODUCTION ACCEPTED`  
**Статус:** `DRAFT FOR TECH LEAD REVIEW`  
**Implementation TASK:** `HOLD`  
**Coder:** `HOLD`  
**Schema change:** `NO — until Tech Lead architecture PASS`  
**Production change:** `NO`

---

# 0. ЦЕЛЬ

Stage 6 вводит отдельный writable Settings domain:

```text
features
```

для управления:

```text
ADMIN PRODUCT BEHAVIOR / FEATURE CONTROLS
```

Feature Control означает:

```text
показывает / использует ли CaptivPortal Admin
конкретную product/read capability
```

Feature Control НЕ означает:

```text
start/stop collector
start/stop worker
start/stop producer
start/stop external integration
изменение security boundary
изменение independent process lifecycle
```

Нормативная граница:

```text
Stage 6
→ Admin product/read exposure,
  product composition,
  read-only orchestration,
  read-source selection

Stage 8
→ operational module lifecycle / tuning

Stage 10
→ auxiliary / independent process settings
```

Stage 6 расширяет существующий Settings control plane и не создаёт параллельный.

---

# 1. CURRENT-STATE SOURCE REVIEW

Проверенный baseline содержит:

```text
Settings schema = v4

ordinary definitions:
General = 12
Controller = 3
Portal = 14
TOTAL = 29
```

Current source уже содержит candidate flags как deployment/environment configuration.

Current Traffic flags являются product exposure / orchestration controls и не запускают:

```text
Observation
Current Traffic
Historical Traffic producer
Visit producer
```

`WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED` в current main process выбирает historical read source:

```text
false
→ existing non-projection historical gateway

true
→ TrafficProjectionReadService
```

Отдельный writer остаётся владельцем:

```text
TRAFFIC_PROJECTION_ENABLED
traffic-projection.service
build/mark-ready/activate/repair/cleanup lifecycle
```

Critical current-state exception:

```text
WEB_ADMIN_HOME_AP_24H_ENABLED
```

сейчас является prerequisite для создания:

```text
HomeAp24TelemetryWorker
```

когда:

```text
WEB_ADMIN_HOME_AP_24H_TELEMETRY_ENABLED=true
```

Следовательно текущий `WEB_ADMIN_HOME_AP_24H_ENABLED` не является чистым read/product flag.

---

# 2. STAGE-6 ADMISSION RULE

Key может быть Stage-6 Feature Control только если одновременно:

```text
1. управляет Admin read/product exposure,
   read-only orchestration,
   overlay
   или main-process read-source selection;

2. не запускает/останавливает collector,
   writer, producer или independent process;

3. имеет ровно один activation target:
   captive-portal.service;

4. другой process не использует тот же persisted override
   как lifecycle authority;

5. runtime source outage может быть представлен
   как product/read degradation,
   не как Settings activation failure;

6. feature disablement не требует мутации
   operational-module flag.
```

Если условие не выполнено:

```text
NOT STAGE 6
```

---

# 3. CANDIDATE DISPOSITION — HOME

## 3.1 WEB_ADMIN_HOME_LIVE_ENABLED

```text
DISPOSITION = ADMIT
FEATURE_ID = home.live
```

Причина:

```text
Admin read/product exposure only.
Не запускает CURRENT_STATE_ENABLED.
```

## 3.2 WEB_ADMIN_HOME_TRAFFIC_ENABLED

```text
DISPOSITION = ADMIT
FEATURE_ID = home.traffic
```

Причина:

```text
Home current-traffic product/read exposure.
Не запускает producer.
```

## 3.3 WEB_ADMIN_HOME_ACTIVITY_ENABLED

```text
DISPOSITION = ADMIT
FEATURE_ID = home.activity
```

Причина:

```text
Main-process read/product composition.
Фоновый producer этим flag не запускается.
```

## 3.4 WEB_ADMIN_HOME_HEALTH_ENABLED

```text
DISPOSITION = ADMIT
FEATURE_ID = home.health
```

Причина:

```text
Read-only Admin product.
Не запускает collector/repair/health writer.
```

## 3.5 WEB_ADMIN_HOME_AP_24H_ENABLED

```text
DISPOSITION = DEFER
```

Причина:

```text
Current baseline связывает этот read flag
с composition prerequisite фонового
Home AP-24H telemetry worker.

Это нарушает Stage-6 pure product/read boundary.
```

Future owner:

```text
Stage 8
или dedicated Home AP-24H operational architecture
```

До будущего admission необходимо архитектурно выбрать:

```text
A. decouple AP-24H read exposure
   from telemetry-worker lifecycle

OR

B. explicitly co-own read + telemetry lifecycle
   in an operational stage
```

Stage 6 этот key не мутирует.

---

# 4. CANDIDATE DISPOSITION — TRAFFIC

Следующие 10 keys:

```text
DISPOSITION = ADMIT
```

```text
WEB_ADMIN_TRAFFIC_ENABLED
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED
WEB_ADMIN_TRAFFIC_PEAK_ENABLED
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED
```

Причина:

```text
Current ownership =
Admin product exposure / orchestration.

Эти flags не стартуют/останавливают
Observation, Current Traffic, Visit,
Analytics или Traffic Projection writer.
```

---

# 5. CANDIDATE DISPOSITION — DEVICES

## 5.1 WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED

```text
DISPOSITION = ADMIT
FEATURE_ID = devices.list_context
```

Причина:

```text
Read-only Devices-list Current State overlay.
Не владеет Current State lifecycle.
```

## 5.2 WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED

```text
DISPOSITION = ADMIT
FEATURE_ID = devices.current_context
```

Причина:

```text
Read-only Device Card current-context exposure.
Не активирует Current State producer.
```

---

# 6. SPECIAL CANDIDATE — TRAFFIC PROJECTION READ

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED
```

Final disposition:

```text
ADMIT
FEATURE_ID = traffic.projection_read
```

Этот key управляет только:

```text
main captive-portal.service
historical read-source selection
```

Он НЕ владеет:

```text
TRAFFIC_PROJECTION_ENABLED
traffic-projection.service
writer lock lifecycle
projection build
mark-ready
activate
repair-site
cleanup
```

Permanent split:

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED
→ main-process read consumer

TRAFFIC_PROJECTION_ENABLED
→ independent writer/process owner
```

Stage 6 не создаёт multi-process activation target.

---

# 7. EXACT STAGE-6 ALLOWLIST

Stage 6 admits exactly **17** Feature Controls.

## Home — 4

```text
WEB_ADMIN_HOME_LIVE_ENABLED
WEB_ADMIN_HOME_TRAFFIC_ENABLED
WEB_ADMIN_HOME_ACTIVITY_ENABLED
WEB_ADMIN_HOME_HEALTH_ENABLED
```

## Traffic — 11

```text
WEB_ADMIN_TRAFFIC_ENABLED
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED
WEB_ADMIN_TRAFFIC_PEAK_ENABLED
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED
```

## Devices — 2

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED
```

Итого:

```text
17
```

После Stage 6 ordinary registry:

```text
General = 12
Controller = 3
Portal = 14
Features = 17

TOTAL = 46
```

---

# 8. DEFINITION CONTRACT

Все 17 definitions:

```text
domain =
features

scope_type =
global

scope_id =
null

secret_class =
normal

editable =
true

repository_default =
false

durable value_type =
string

canonical durable values =
"true"
"false"

public_value_type =
boolean

presentation_type =
boolean_toggle

apply_requirement =
main_service_restart

activation_target =
captive-portal.service
```

Не допускается generic `_ENABLED` discovery.

Только exact registry allowlist writable.

---

# 9. FEATURE METADATA — HOME

```text
KEY =
WEB_ADMIN_HOME_LIVE_ENABLED

feature_id =
home.live

display_label =
Live network state

description =
Show the Home live network state product.

group =
home

control_kind =
surface
```

```text
KEY =
WEB_ADMIN_HOME_TRAFFIC_ENABLED

feature_id =
home.traffic

display_label =
Traffic summary

description =
Show the Home current traffic summary product.

group =
home

control_kind =
surface
```

```text
KEY =
WEB_ADMIN_HOME_ACTIVITY_ENABLED

feature_id =
home.activity

display_label =
Activity

description =
Show the Home activity product.

group =
home

control_kind =
surface
```

```text
KEY =
WEB_ADMIN_HOME_HEALTH_ENABLED

feature_id =
home.health

display_label =
System health

description =
Show the Home system health product.

group =
home

control_kind =
surface
```

---

# 10. FEATURE METADATA — TRAFFIC

```text
WEB_ADMIN_TRAFFIC_ENABLED
feature_id = traffic.root
label = Traffic page
description = Expose the Admin Traffic product.
group = traffic
control_kind = surface
```

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED
feature_id = traffic.history
label = Historical traffic
description = Expose historical traffic on the Traffic page.
group = traffic
control_kind = surface
```

```text
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED
feature_id = traffic.statistics
label = Statistics
description = Expose Traffic statistics.
group = traffic
control_kind = surface
```

```text
WEB_ADMIN_TRAFFIC_PEAK_ENABLED
feature_id = traffic.peak
label = Peak periods
description = Expose Traffic peak-period analysis.
group = traffic
control_kind = surface
```

```text
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED
feature_id = traffic.by_ap
label = Traffic by AP
description = Expose historical Traffic grouped by access point.
group = traffic
control_kind = surface
```

```text
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED
feature_id = traffic.independent_ranges
label = Independent ranges
description = Use independent page-local historical ranges for supported Traffic products.
group = traffic
control_kind = behavior
```

```text
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED
feature_id = traffic.ap_share
label = AP share
description = Expose AP Traffic Share.
group = traffic
control_kind = surface
```

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED
feature_id = traffic.online_guests
label = Online guests
description = Expose current online guest traffic.
group = traffic
control_kind = surface
```

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED
feature_id = traffic.completed_sessions
label = Completed sessions
description = Expose completed guest session traffic.
group = traffic
control_kind = surface
```

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED
feature_id = traffic.evidence
label = Evidence / data quality
description = Expose Traffic evidence and data-quality information.
group = traffic
control_kind = surface
```

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED
feature_id = traffic.projection_read
label = Historical projection read source
description = Use the Traffic Projection read boundary for supported historical Traffic products.
group = traffic
control_kind = source_selector
```

---

# 11. FEATURE METADATA — DEVICES

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED
feature_id = devices.list_context
label = Device list context
description = Enrich the Devices list with the existing Current State context overlay.
group = devices
control_kind = overlay
```

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED
feature_id = devices.current_context
label = Device current context
description = Expose current network context on the Device Card.
group = devices
control_kind = surface
```

`SettingsDefinitionRegistry` является единственным code-owned source для:

```text
feature_id
display_label
description
group
control_kind
parent_feature_keys
```

Frontend не владеет второй Feature-definition table.

---

# 12. REJECT — SECURITY / BOOTSTRAP / SELF-LOCKOUT

Stage 6 НЕ допускает:

```text
WEB_ADMIN_ENABLED
WEB_ADMIN_SETTINGS_ENABLED

Admin username/password/hash
Admin allowed networks
Admin allowed Sites/default Site
HTTPS requirement
session/login limits
WEB_ADMIN_GLOBAL_CAPABILITIES
capability grants
```

Disposition:

```text
REJECT FROM STAGE 6
```

Причина:

```text
bootstrap
security boundary
self-lockout risk
authorization ownership
```

---

# 13. REJECT — CAPPORT / GUEST ACCESS CONTRACT

Stage 6 НЕ допускает:

```text
CAPPORT_ENABLED
CAPPORT_SITE_ID
CAPPORT_PUBLIC_BASE_URL
CAPPORT_API_PATH
CAPPORT_LOGIN_PATH
CAPPORT_ALLOWED_CLIENT_NETWORKS
CAPPORT cache controls
DHCP option 114
CAPPORT external/network contract
```

Disposition:

```text
REJECT FROM STAGE 6
```

Future owner:

```text
dedicated CAPPORT architecture
```

---

# 14. DEFER — OPERATIONAL MODULES

Stage 6 НЕ допускает:

```text
CURRENT_STATE_ENABLED

OBSERVATION_FOUNDATION_ENABLED
OBSERVATION_CLIENT_ENABLED
OBSERVATION_AP_ENABLED

VISIT_LIFECYCLE_ENABLED
VISITOR_REGISTRY_ENABLED
VISITOR_SNAPSHOT_ENABLED

PENDING_SESSION_CLEANER_ENABLED

ANALYTICS_FOUNDATION_ENABLED
ANALYTICS_WIRELESS_ENABLED
ANALYTICS_VISIT_ENABLED

OMADA_WEBHOOK_ENABLED

WEB_ADMIN_HOME_AP_24H_ENABLED
WEB_ADMIN_HOME_AP_24H_TELEMETRY_ENABLED
```

Disposition:

```text
DEFER TO STAGE 8
OR DEDICATED OPERATIONAL ARCHITECTURE
```

---

# 15. DEFER — AUXILIARY / MULTI-PROCESS

```text
TRAFFIC_PROJECTION_ENABLED

DEVICE_FINGERPRINT_EVIDENCE_ENABLED
DEVICE_FINGERPRINT_INTEGRATION_ENABLED
```

Disposition:

```text
DEFER TO STAGE 10
OR DEDICATED PROCESS ARCHITECTURE
```

Only:

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED
```

is admitted because it is the main-process read consumer selector.

---

# 16. PARENT / CHILD GRAPH

There is one code-owned Feature graph.

No frontend-owned graph.

No route-local duplicate graph.

## Home

```text
home.live
→ no parent

home.traffic
→ home.live

home.activity
→ home.live

home.health
→ no parent
```

## Traffic

```text
traffic.root
→ no parent

traffic.history
→ traffic.root

traffic.statistics
→ traffic.history

traffic.peak
→ traffic.statistics

traffic.by_ap
→ traffic.history

traffic.independent_ranges
→ traffic.history

traffic.ap_share
→ traffic.independent_ranges

traffic.online_guests
→ traffic.root

traffic.completed_sessions
→ traffic.root

traffic.evidence
→ traffic.root

traffic.projection_read
→ traffic.history
```

## Devices

```text
devices.list_context
→ no parent

devices.current_context
→ no parent
```

Dependencies are transitive.

---

# 17. WEB_ADMIN_ENABLED IS NOT A FEATURE PARENT

`WEB_ADMIN_ENABLED` remains deployment/bootstrap configuration.

It is not:

```text
Stage-6 definition
parent_feature_key
writable Feature Control
```

Feature preferences MAY remain true while Admin Web is deployment-disabled.

Admin disablement MUST NOT rewrite Feature preferences.

---

# 18. ALL PARENT/CHILD BOOLEAN COMBINATIONS ARE VALID

Permanent invariant:

```text
child=true
parent=false
=
VALID CONFIGURATION
```

Example:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
```

is valid.

No mutation rejection.

No automatic cascade.

No hidden rewrite.

---

# 19. NO AUTO-CASCADE MUTATION

Changing one Feature may persist only Feature keys explicitly present in the operator request.

Forbidden:

```text
parent=false
→ write every child=false
```

Forbidden:

```text
parent=true
→ write every child=true
```

Forbidden:

```text
dependency evaluation
→ audit keys absent from request
```

Dependencies alter derived Feature state only.

---

# 20. DORMANT CHILD

Example:

```text
configured Traffic = false
configured History = true
```

After adoption:

```text
effective Traffic = false
effective History = true

History effective_feature_state =
dormant_parent_disabled
```

When Traffic is later enabled and that generation adopted:

```text
History preference remains true
History becomes usable automatically
```

No child mutation required.

---

# 21. CONFIGURED / EFFECTIVE SEMANTICS

Existing Settings semantics remain unchanged.

```text
configured_value
=
value in current configured generation

effective_value
=
value in trustworthy adopted startup snapshot
```

Example before restart:

```text
configured Home Health = false
effective Home Health = true
activation_state = pending_main_restart
```

Running product behavior continues using the effective snapshot until adoption.

---

# 22. PUBLIC BOOLEAN VS DURABLE STRING

To reuse current v4 ordinary storage type:

```text
durable value_type =
string

durable values =
"true"
"false"
```

Public Feature API projects:

```text
public_value_type =
boolean
```

Therefore the following read fields are JSON boolean or null:

```text
default_value
base_value
persisted_override_value
configured_value
effective_value
pending_value
```

Raw durable strings are not a public API concern.

---

# 23. FEATURE MUTATION VALUE

For domain `features`, `set` accepts JSON boolean only.

Valid:

```json
{
  "key": "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED",
  "operation": "set",
  "value": true
}
```

Invalid:

```json
{"value": "true"}
```

Invalid:

```json
{"value": 1}
```

Server conversion is exact:

```text
true  → "true"
false → "false"
```

before persistence.

`clear_override` contains no value.

---

# 24. FEATURE STATE MODEL

Stage 6 introduces two derived states.

```text
configured_feature_state
effective_feature_state
```

`configured_feature_state` enum:

```text
enabled
disabled
dormant_parent_disabled
```

`effective_feature_state` enum:

```text
enabled
disabled
dormant_parent_disabled
runtime_unavailable
```

Definitions:

```text
disabled
=
own value false
```

```text
enabled
=
own value true
AND
all transitive parent values true
```

```text
dormant_parent_disabled
=
own value true
AND
at least one transitive parent value false
```

```text
runtime_unavailable
=
trustworthy effective Feature snapshot cannot be projected
```

`enabled` does NOT mean source healthy.

---

# 25. BLOCKED-BY MODEL

Per Feature read model:

```text
parent_feature_keys
configured_blocked_by_feature_keys
effective_blocked_by_feature_keys
```

`parent_feature_keys` contains direct parents.

Blocked lists contain all false ancestors in deterministic order:

```text
root
→
nearest parent
```

No frontend dependency computation.

---

# 26. CONFIGURED/EFFECTIVE IS NOT OPERATIONAL HEALTH

Settings Features API MUST NOT query:

```text
Current State
Observation
Visit DB
Analytics source
Traffic Projection DB
Omada
Loki
systemd
```

Therefore Feature state is only:

```text
configuration/product graph state
```

No live:

```text
healthy
connected
fresh
source_healthy
```

field exists in Features Settings V1.

---

# 27. THREE DEPENDENCY CLASSES

Every dependency belongs to exactly one class.

## 27.1 PARENT_PRODUCT_DEPENDENCY

Another admitted Stage-6 Feature.

Behavior:

```text
may make child dormant
never invalidates boolean combination
never cascades persistence
```

## 27.2 CONFIGURATION_PREREQUISITE

Static configuration required for safe composition.

Behavior:

```text
checked only when configured Feature graph state = enabled
```

Failure:

```text
422 validation_failed
reason = configuration_prerequisite_invalid
```

## 27.3 RUNTIME_SOURCE_DEPENDENCY

Runtime DB/read service/evidence needed to answer product query.

Temporary failure:

```text
does NOT invalidate generation
does NOT become activation_failed
```

---

# 28. HOME ACTIVITY STATIC PREREQUISITES

When:

```text
configured_feature_state(home.activity)=enabled
```

must validate:

```text
Activity supporting numeric/timing configuration

WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON

CURRENT_STATE_ENABLED=true

Current State Site scope non-empty and valid

Current State guest SSID scope non-empty and valid

Activity Site context lies within:
Admin allowed Site scope
AND
Current State Site scope
```

Important:

```text
home.live=false
home.activity=true
```

is valid because Activity is dormant.

While dormant, stale/broken Activity-only optional config does not reject the preference.

When the parent becomes enabled, full candidate validation occurs in the same atomic mutation.

---

# 29. DEVICE LIST CONTEXT STATIC PREREQUISITE

When:

```text
configured_feature_state(devices.list_context)=enabled
```

existing deployment-owned:

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET
```

must be structurally valid.

The secret itself is NOT Stage-6 writable.

Failure:

```text
422 validation_failed
key = WEB_ADMIN_DEVICE_LIST_CONTEXT_ENABLED
reason = configuration_prerequisite_invalid
```

No secret value in error/log/audit.

---

# 30. TRAFFIC PROJECTION READ STATIC CONFIG

Introduce exact main-process read config boundary:

```text
TrafficProjectionReadConfigV1
```

It owns only:

```text
read_enabled
projection_db_path
observation_db_path
site_ids
```

When `traffic.projection_read` graph state is enabled, validate:

```text
TRAFFIC_PROJECTION_DB_PATH absolute

OBSERVATION_DB_PATH absolute

paths distinct

OBSERVATION_SITE_IDS non-empty and valid
```

It MUST NOT require:

```text
TRAFFIC_PROJECTION_ENABLED=true
traffic-projection.service active
TRAFFIC_PROJECTION_WRITER_LOCK_PATH
writer lock availability
```

Projection store existence/health/readiness is runtime source state, not static configuration validity.

---

# 31. OTHER STATIC PREREQUISITES

When `home.health` graph state is enabled:

```text
existing Home Health bounded tuning values
must be structurally valid
```

For other admitted Feature Controls there are no new Feature-specific static prerequisites beyond existing safe base Admin configuration.

Parent values are never CONFIGURATION_PREREQUISITE.

---

# 32. RUNTIME SOURCE DEPENDENCY MATRIX

```text
home.live
→ Current State read boundary
```

```text
home.traffic
→ existing Current Traffic read service
```

```text
home.activity
→ existing Home Activity read service
  and its current read-source dependencies
```

```text
home.health
→ existing Authorization health evidence
  Current State runtime
  Observation runtime
  Visit runtime
  Analytics runtime
```

```text
traffic.root
→ existing current-traffic read service
```

```text
traffic.history
traffic.statistics
traffic.peak
traffic.by_ap
traffic.independent_ranges
traffic.ap_share
→ existing historical Traffic read/composition boundary
```

```text
traffic.online_guests
→ existing Current Guest Traffic read service
```

```text
traffic.completed_sessions
→ existing Completed Guest Session Traffic read service
```

```text
traffic.evidence
→ existing Traffic Evidence aggregator
```

```text
traffic.projection_read
→ Traffic Projection read store / projection evidence
```

```text
devices.list_context
→ Current State list-context read boundary
```

```text
devices.current_context
→ Current State current-device-context read boundary
```

---

# 33. SOURCE OUTAGE SEMANTICS

If:

```text
effective_feature_state=enabled
```

and source becomes temporarily unavailable:

```text
effective Feature value remains true
Settings generation remains valid
Settings activation remains adopted
```

The product uses its existing bounded read failure semantics.

Typical:

```text
503 source_unavailable
```

where that is current contract.

Forbidden:

```text
source outage
→ activation_failed
```

Forbidden:

```text
source outage
→ auto-set Feature false
```

For projection read:

```text
source unavailable
→ no automatic raw historical fallback
```

---

# 34. STATIC CONFIG FAILURE VS RUNTIME FAILURE

Configuration failures include:

```text
invalid Activity Site context
invalid required list-context cursor secret
invalid projection read path/scope config
invalid enabled Feature-owned bounded config
```

They may reject mutation/adoption.

Runtime source failures include:

```text
DB temporarily unavailable
source service absent/degraded after safe composition
source stale
query timeout
projection runtime/data unavailable
```

They do not invalidate Settings generation.

---

# 35. VALIDATION OF DORMANT / DISABLED FEATURE CONFIG

Feature-specific optional configuration is validated only when:

```text
WEB_ADMIN_ENABLED=true
AND
configured_feature_state(feature)=enabled
```

If Feature is:

```text
disabled
or
dormant_parent_disabled
```

stale/broken optional supporting config does not block storing the Feature preference.

When a later mutation makes the graph state:

```text
enabled
```

its supporting config becomes mandatory in that same atomic candidate validation.

---

# 36. CURRENT CROSS-FEATURE FAIL-CLOSED RULES ARE RECLASSIFIED

Current source checks such as:

```text
Home Traffic requires Home Live
History requires Traffic
Statistics requires History
Peak requires Statistics
By AP requires History
Independent Ranges requires History
AP Share requires Independent Ranges
Online Guests requires Traffic
Completed Sessions requires Traffic
Evidence requires Traffic
```

are no longer configuration-invalid combinations under Stage 6.

They become:

```text
PARENT_PRODUCT_DEPENDENCY
→ dormant_parent_disabled
```

The same preference-preservation principle applies when deployment root:

```text
WEB_ADMIN_ENABLED=false
```

No child preferences are destroyed.

---

# 37. SINGLE STARTUP FEATURE PLAN

Introduce immutable:

```text
AdminFeaturePlanV1
```

It is built from the exact startup `ResolvedSettingsSnapshot(G)` and owns:

```text
normalized effective Feature booleans
Feature graph
effective_feature_state
effective blocked-by relationships
control kinds
```

Canonical runtime chain:

```text
ResolvedSettingsSnapshot(G)
        ↓
Feature candidate validation
        ↓
AdminFeaturePlanV1
        ↓
Admin runtime
routes
templates
```

No route reparses environment.

No template computes dependencies.

No JS owns Feature graph.

---

# 38. PRODUCT ROUTES USE EFFECTIVE PLAN

Runtime product behavior uses:

```text
AdminFeaturePlanV1
```

not current configured head.

Therefore:

```text
Save OFF while runtime ON
→ runtime remains ON until restart/adoption
```

```text
Save ON while runtime OFF
→ runtime remains OFF until restart/adoption
```

---

# 39. INTENTIONAL DISABLEMENT IS NOT FAILURE

Permanent invariant:

```text
disabled
!=
failure
```

and:

```text
dormant_parent_disabled
!=
failure
```

Disabled/dormant optional product services do not produce false degradation merely because they are not composed/used.

---

# 40. HOME HEALTH INTERACTION

Stage 6 does NOT redesign Home Health component schema.

No 17 Feature-health components are added.

Exact rule:

```text
Home Traffic read service is expected by Home Health
only if effective_feature_state(home.traffic)=enabled.

Home Activity read service is expected by Home Health
only if effective_feature_state(home.activity)=enabled.
```

If either is:

```text
disabled
or
dormant_parent_disabled
```

its absence must not produce:

```text
current_traffic_service_unavailable
home_activity_service_unavailable
```

solely because the product was intentionally disabled.

Other underlying operational health remains independently evaluated.

Disabling Home Live product does not falsify Current State operational health.

---

# 41. HOME HEALTH PRODUCT VS ADMIN RUNTIME HEALTH

If:

```text
WEB_ADMIN_HOME_HEALTH_ENABLED effective=false
```

the Home System Health product is unavailable/hidden.

But:

```text
GET /admin/api/v1/health
```

remains unchanged because it is Admin runtime health, not Home System Health product.

---

# 42. ACTIVATION MODEL

All 17 admitted Feature Controls:

```text
apply_requirement =
main_service_restart

activation_target =
captive-portal.service
```

No exceptions.

No:

```text
hot enable
hot disable
automatic restart
systemctl
systemd D-Bus
sudo
provider recreation from HTTP
```

Any Feature requiring another activation target is excluded from Stage 6.

---

# 43. FEATURE ACTIVATION FAILURE CATEGORY

Add one bounded safe category:

```text
features_configuration_adoption_failed
```

It may be recorded only when the new main process positively determines:

```text
configured generation G
contains structurally invalid Feature configuration
that prevents AdminFeaturePlanV1
or a required graph-enabled Feature composition
```

It MUST NOT be used for:

```text
temporary source outage
query timeout
stale data
projection worker stopped
source DB temporarily unavailable
```

---

# 44. SETTINGS DOMAIN

Canonical durable domain:

```text
features
```

No aliases:

```text
feature
admin_features
product
behavior
```

---

# 45. REGISTRY OWNERSHIP

Reuse:

```text
SettingsDefinitionRegistry
```

Do NOT create:

```text
FeatureDefinitionRegistry
FeatureSettingsRegistry
second writable registry
```

Feature definition metadata additionally owns:

```text
feature_id
control_kind
parent_feature_keys
public_value_type
```

There is exactly one Feature graph source.

---

# 46. RESOLVER

Reuse canonical resolver.

Inputs remain:

```text
base settings
explicit environment-name presence snapshot
persisted overrides
registry
generation
```

Precedence remains:

```text
persisted override
>
explicit environment
>
repository default
```

No Feature-specific precedence.

No Site precedence.

No request-time environment lookup.

---

# 47. RESET

UI action:

```text
Reset to deployment/default
```

maps exactly to:

```text
clear_override
```

Then ownership falls to:

```text
explicit environment
or
repository default
```

Reset does not persist false merely because repository default is false.

---

# 48. FEATURE MUTATION VALIDATION PIPELINE

Exact sequence:

```text
1. strict JSON request parse;

2. Feature set values accept JSON boolean only;

3. boolean canonicalized internally to "true"/"false";

4. apply only explicitly requested override changes;

5. resolve complete candidate snapshot;

6. validate all ordinary durable values;

7. derive configured Feature graph;

8. validate Feature-specific static prerequisites
   only for graph-enabled Features;

9. validate ordinary Admin startup composition
   with parent relationships represented by graph,
   not fail-closed cross-feature boolean checks;

10. DO NOT resolve/decrypt managed Client Secret;

11. if valid:
    create one global generation atomically.
```

On failure:

```text
NO generation
NO Feature audit
NO successful idempotency receipt
```

---

# 49. SECRET ISOLATION

Feature read/mutation MUST NOT call:

```text
ControllerSecretRepository.resolve
SecretFilesystem.load_master_key
decrypt_secret
secret read-back
```

A Feature generation carries the parent secret binding unchanged.

Feature mutation remains usable if:

```text
SettingsStore available
managed-secret key/store unavailable
```

This does NOT weaken existing General/Controller/main-startup Stage-4 secret semantics.

Managed-secret production activation remains unrelated to Stage 6.

---

# 50. TRAFFIC PROJECTION READ/WRITER OWNERSHIP SPLIT

Main-process read boundary:

```text
TrafficProjectionReadConfigV1
```

owns:

```text
read_enabled
projection DB path
Observation DB path
Site read scope
```

Independent writer owner continues to own:

```text
TRAFFIC_PROJECTION_ENABLED
writer lock path
worker lifecycle
build/repair/activate lifecycle
```

No Feature mutation changes writer configuration.

---

# 51. FEATURE-DISABLED PRODUCT ROUTE RULE

Product route gating always uses:

```text
effective_feature_state
```

For `surface` controls:

```text
disabled
or
dormant_parent_disabled
→ panel/surface absent from HTML
→ direct product API returns current canonical 404 not_found
→ no source query
```

No new external product API error:

```text
parent_feature_disabled
```

is introduced.

Parent-disabled detail is visible only on Settings → Features.

---

# 52. HOME LIVE EFFECT

If `home.live` is not effectively enabled:

Home Live panels are absent.

Gated before source read:

```text
/admin/api/v1/sites/<site_id>/current-state/clients/summary
/admin/api/v1/sites/<site_id>/current-state/clients
/admin/api/v1/sites/<site_id>/current-state/aps/summary
/admin/api/v1/sites/<site_id>/current-state/aps
```

Response:

```text
404 not_found
```

---

# 53. HOME TRAFFIC EFFECT

If `home.traffic` is disabled/dormant:

Home Traffic panel absent.

Gated APIs:

```text
/admin/api/v1/sites/<site_id>/current-traffic/summary
/admin/api/v1/sites/<site_id>/current-traffic/aps
```

Response:

```text
404 not_found
```

No source query.

---

# 54. HOME ACTIVITY EFFECT

If `home.activity` is disabled/dormant:

Home Activity panel absent.

Existing API family including:

```text
/admin/api/v1/sites/<site_id>/home-activity/today
/admin/api/v1/sites/<site_id>/home-activity/selected
/admin/api/v1/sites/<site_id>/home-activity/range-preview
```

returns:

```text
404 not_found
```

before source query.

---

# 55. HOME HEALTH EFFECT

If `home.health=false` effective:

Home System Health panel absent.

```text
/admin/api/v1/sites/<site_id>/home/health
→ 404 not_found
```

No source evaluation.

Unrelated:

```text
/admin/api/v1/health
```

remains available under its existing contract.

---

# 56. TRAFFIC ROOT EFFECT

If `traffic.root=false` effective:

```text
Traffic navigation absent
/admin/sites/<site_id>/traffic → 404 not_found
```

All child Traffic product APIs are gated before source query.

Child value true remains stored but derived state is:

```text
dormant_parent_disabled
```

---

# 57. TRAFFIC HISTORY EFFECT

If `traffic.history` disabled/dormant:

Historical Traffic product absent.

```text
/admin/api/v1/sites/<site_id>/traffic/history
→ 404 not_found
```

before historical source query.

Descendants are dormant.

---

# 58. TRAFFIC STATISTICS / PEAK / BY AP / AP SHARE

They share existing historical request boundary.

If request explicitly asks for a child product whose effective state is not enabled:

```text
404 not_found
```

before child computation.

Sibling controls remain independent.

Examples:

```text
Statistics OFF
does not disable History.

Peak OFF
does not disable Statistics.

By AP OFF
does not disable History.

AP Share OFF
does not disable By AP.
```

---

# 59. INDEPENDENT RANGES

`traffic.independent_ranges`:

```text
control_kind = behavior
```

No standalone route.

If disabled/dormant:

```text
existing shared-range orchestration
```

If enabled:

```text
supported historical products use
independent page-local selected/applied ranges
```

No producer lifecycle change.

---

# 60. AP SHARE PARENT

Direct parent:

```text
traffic.independent_ranges
```

Thus:

```text
AP Share=true
Independent Ranges=false
```

is valid but AP Share is dormant.

No auto-rewrite.

---

# 61. ONLINE GUESTS EFFECT

If disabled/dormant:

```text
/admin/api/v1/sites/<site_id>/traffic/online-guests/current
→ 404 not_found
```

No source query.

---

# 62. COMPLETED SESSIONS EFFECT

If disabled/dormant:

```text
/admin/api/v1/sites/<site_id>/traffic/completed-sessions
→ 404 not_found
```

No source query.

---

# 63. TRAFFIC EVIDENCE EFFECT

If disabled/dormant:

```text
/admin/api/v1/sites/<site_id>/traffic/evidence
→ 404 not_found
```

No aggregator/source query.

---

# 64. TRAFFIC PROJECTION READ EFFECT

`traffic.projection_read` owns no panel and no standalone route.

If disabled/dormant:

```text
historical Traffic uses existing non-projection read path
```

If enabled:

```text
History
Statistics
Peak
Traffic by AP
AP Share
```

use `TrafficProjectionReadService`.

If projection source unavailable:

```text
existing historical source-unavailable/503 behavior
```

No automatic raw reconstruction fallback.

---

# 65. DEVICE LIST CONTEXT EFFECT

`devices.list_context`:

```text
control_kind = overlay
```

Effective false:

```text
Devices page remains available
base Devices list remains available
Current State overlay is not requested
```

Enabled + Current State temporarily unavailable:

```text
base Devices product remains usable under
existing unknown/unavailable overlay semantics
```

No Settings failure.

---

# 66. DEVICE CURRENT CONTEXT EFFECT

Effective false:

```text
Device Card remains available
current-context section hidden
```

Endpoint:

```text
/admin/api/v1/sites/<site_id>/devices/<device_id>/current
→ 404 not_found
```

before source query.

---

# 67. SETTINGS UI HIERARCHY

Canonical order:

```text
Settings
├─ General
├─ Features
├─ Controller
└─ Portal
```

Features page:

```text
GET /admin/settings/features
```

Page key:

```text
settings_features
```

Title:

```text
Features
```

Groups exact order:

```text
Home
Traffic
Devices
```

No AP-24H row.

No empty groups.

---

# 68. FEATURES UI EDITING

Each Feature row shows:

```text
product label
technical key as secondary metadata

Configured
Effective
Source
Pending

Configured feature state
Effective feature state

Blocked by parent(s) when applicable

Reset action if persisted override exists
```

Editor:

```text
boolean switch
```

Switch changes only local configured candidate.

No immediate write.

Explicit:

```text
Save changes
```

sends one atomic batch.

---

# 69. DORMANT CHILD UX

Dormant child stays visible.

Example:

```text
History switch = ON

state =
Dormant — Traffic page is disabled
```

Switch remains ON.

Operator may edit dormant child.

No UI cascade.

Blocked-parent metadata comes from server.

---

# 70. PENDING UX

When configured differs from effective:

```text
Persisted successfully.
Pending captive-portal.service restart.
```

Do not say:

```text
Applied
Enabled now
Disabled now
```

before adoption.

No restart/apply button.

---

# 71. AUTHORIZATION

Introduce exact capabilities:

```text
admin.read.settings.features
admin.write.settings.features
```

Add to recognized global capability universe.

Do NOT add to:

```text
DEFAULT_GLOBAL_CAPABILITIES
```

No silent privilege expansion.

---

# 72. AUTHORIZATION SEMANTICS

Page + read API require:

```text
admin.read.settings.features
```

Mutation requires BOTH:

```text
admin.read.settings.features
admin.write.settings.features
```

Write does not imply read.

GLOBAL only.

No Site authorization.

---

# 73. CAPABILITY ACTIVATION BOUNDARY

Grants remain deployment-owned through existing:

```text
WEB_ADMIN_GLOBAL_CAPABILITIES
```

Stage 6 does not mutate grants.

Grant change follows existing:

```text
deployment config change
→ captive-portal.service restart
→ new Admin login/session
```

Production grant activation is separate from code deployment.

---

# 74. SETTINGS NAV

Features tab visible only when:

```text
WEB_ADMIN_SETTINGS_ENABLED=true
AND
principal has admin.read.settings.features
```

Store unavailable:

```text
tab remains visible to authorized principal
page renders bounded unavailable state
```

---

# 75. READ API

Canonical:

```text
GET /admin/api/v1/settings/features
```

API version:

```text
admin.settings.features.v1
```

Resource:

```json
{
  "type": "admin_product_features",
  "scope": "installation"
}
```

No query parameters.

No body.

Headers:

```text
Cache-Control: no-store
Pragma: no-cache
ETag: "settings-gN"
```

---

# 76. READ API TOP LEVEL

Success body contains exactly:

```text
api_version
request_id
scope
resource
store_state
configured_generation
effective_generation
etag
restart_required
pending_setting_count
features
```

---

# 77. PER-FEATURE READ MODEL

Each Feature object contains exactly:

```text
key
feature_id
display_label
description
group
control_kind
public_value_type
presentation_type

scope_type
scope_id
editable
secret_class

default_value

base_source
base_value

persisted_override_value

configured_value
configured_source

effective_value
effective_source

pending_value

configured_generation
effective_generation
activation_state

apply_requirement
activation_target

parent_feature_keys

configured_feature_state
configured_blocked_by_feature_keys

effective_feature_state
effective_blocked_by_feature_keys

validation

last_changed_at
last_changed_by
```

---

# 78. SOURCE ENUMS

`base_source`:

```text
environment
repository_default
```

`configured_source`:

```text
persisted_override
environment
repository_default
```

`effective_source`:

```text
persisted_override
environment
repository_default
null
```

`null` only when trustworthy effective projection unavailable.

Do not infer:

```text
systemd
.env
manual
deployment
```

---

# 79. VALIDATION METADATA

Every Feature exposes exactly:

```json
{
  "type": "boolean"
}
```

No frontend-owned validation enum table.

---

# 80. PENDING VALUE / COUNT

`pending_value` equals configured boolean only when:

```text
trustworthy effective runtime exists
AND
configured_value != effective_value
```

Else:

```text
null
```

`pending_setting_count` counts Feature rows with non-null `pending_value`.

Global `restart_required` may be true while:

```text
pending_setting_count = 0
```

if only another Settings domain differs. This is valid.

---

# 81. MUTATION API

Canonical:

```text
POST /admin/api/v1/settings/features/generations
```

API version:

```text
admin.settings.features.mutation.v1
```

No:

```text
PUT
PATCH
DELETE
per-feature POST
Site route
```

---

# 82. MUTATION BODY

Exact shape:

```json
{
  "changes": [
    {
      "key": "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED",
      "operation": "set",
      "value": true
    },
    {
      "key": "WEB_ADMIN_TRAFFIC_PEAK_ENABLED",
      "operation": "clear_override"
    }
  ]
}
```

Allowed:

```text
set
clear_override
```

Minimum changes:

```text
1
```

Maximum:

```text
17
```

Unknown key, duplicate key or wrong type:

```text
400 invalid_request
```

---

# 83. MUTATION HEADERS

Required:

```text
Content-Type: application/json
X-CSRF-Token
If-Match: "settings-gN"
Idempotency-Key: canonical UUID
```

UUID semantics reuse current ordinary Settings rule:

```text
str(uuid.UUID(value)) == value
```

Maximum body:

```text
32768 bytes
```

---

# 84. MUTATION SUCCESS RECEIPT

Changed:

```text
HTTP 201
```

No-op:

```text
HTTP 200
```

Exact response fields:

```text
api_version
request_id
scope
resource
changed
changed_keys
configured_generation
effective_generation
activation_state
restart_required
```

Example:

```json
{
  "api_version": "admin.settings.features.mutation.v1",
  "request_id": "<uuid>",
  "scope": {"type": "global"},
  "resource": {
    "type": "admin_product_features",
    "scope": "installation"
  },
  "changed": true,
  "changed_keys": [
    "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED"
  ],
  "configured_generation": 5,
  "effective_generation": 4,
  "activation_state": "pending_main_restart",
  "restart_required": true
}
```

No full Feature values in receipt.

Client performs fresh GET.

---

# 85. CHANGED KEYS

Only keys whose persisted override state changed.

Ordering:

```text
ascending canonical key order
```

No-op:

```text
changed=false
changed_keys=[]
```

No new generation.

No ordinary mutation audit.

Successful idempotency receipt is persisted.

---

# 86. COMMON ETAG / CAS

Features use the same global generation.

ETag:

```text
"settings-g<configured_generation>"
```

Example:

```text
Portal creates G5
Feature UI holds settings-g4

Feature Save
→ 412 stale_generation
```

No Features-only generation.

No Features-only ETag.

---

# 87. IDEMPOTENCY

Identity:

```text
principal_type
principal_name
scope_type=global
mutation_domain=features
Idempotency-Key
```

Same key + same canonical request:

```text
return original stored HTTP status
+
original stored body
```

even after head advance.

Replay MUST NOT become 412.

Same key + different payload:

```text
409 idempotency_conflict
```

Replay ETag corresponds to stored configured generation.

---

# 88. ERROR CONTRACT

Feature Settings read/mutation errors:

```text
400 invalid_request
400 invalid_csrf

401 authentication_required

403 settings_forbidden

404 feature_disabled
for Settings product/API disabled

409 idempotency_conflict

411 length_required

412 stale_generation

413 request_too_large

415 unsupported_media_type

422 validation_failed

428 precondition_required

503 settings_store_unavailable

500 internal_error
```

Static prerequisite detail:

```json
{
  "key": "WEB_ADMIN_HOME_ACTIVITY_ENABLED",
  "reason": "configuration_prerequisite_invalid"
}
```

Safe errors only.

No raw path/exception/secret/config dump.

---

# 89. NO INVALID PARENT COMBINATION ERROR

There is no parent/child boolean combination that is invalid.

Therefore parent relationships never produce:

```text
invalid_dependency_combination
```

They produce dormant state.

---

# 90. SETTINGS SCHEMA v5

Stage 6 requires:

```text
SettingsStore schema v5
```

Reason:

```text
durable audit/idempotency domain enums
must admit "features"
```

No new physical DB.

No Feature-specific table.

No new generation table.

No new override value type.

---

# 91. EXACT v5 DELTA

`settings_mutation_audit.setting_domain`:

```text
general
controller
portal
features
```

Feature audit:

```text
value_type=string
```

canonical values:

```text
"true"
"false"
```

`settings_idempotency.mutation_domain`:

```text
general
controller
controller_secret
portal
features
```

`settings_overrides` already supports string values and needs no new column.

---

# 92. v4 → v5 MIGRATION

Migration owner:

```text
SettingsRepository startup/schema boundary
```

Must preserve exactly:

```text
all generation IDs
all parent generation IDs
effective target generation

all General overrides
all Controller overrides
all Portal overrides

all secret versions
all secret bindings

all activation events
all ordinary audit
all secret audit
all idempotency records

history identity
```

Migration creates:

```text
NO generation
NO Feature override
NO audit
NO activation event
NO idempotency result
```

No Feature defaults materialized.

---

# 93. MIGRATION MUST NOT CHANGE PRODUCT STATE

Because no Feature overrides are materialized:

```text
current production explicit environment
remains base authority
```

Schema migration alone must not alter current product exposure.

Repository default false is not evidence that production feature is false.

---

# 94. STAGE-4 BREAK-GLASS ON v5

Recovery remains:

```text
current-schema-aware
existing-only
non-creating
non-migrating
secret-safe
no decrypt/read-back
CAS protected
```

After Stage 6:

```text
SETTINGS_SCHEMA_VERSION=5
```

and current:

```text
SettingsRepository.open_existing_for_recovery(...)
```

must validate/accept exact v5.

No hard-coded v4 recovery contract.

---

# 95. BREAK-GLASS MUST PRESERVE FEATURES

On v5 recovery secret-clear generation, copy unchanged:

```text
General overrides
Controller ordinary overrides
Portal overrides
Feature overrides
```

Only managed secret ownership changes.

No Feature audit/idempotency/history change.

Mandatory gate:

```text
v5 + Stage-4 break-glass recovery = PASS
```

with populated Feature generations.

---

# 96. ROLLBACK / DOWNGRADE

Before production v4→v5 migration:

```text
verified v4 Settings DB backup required
```

Rollback to pre-Stage6 code requires:

```text
restore compatible v4 DB backup
```

Old binary + v5 DB:

```text
NOT SUPPORTED
must fail closed
```

No down-migration.

---

# 97. STORE UNAVAILABLE

Settings enabled + store unavailable:

```text
/admin/settings/features
→ bounded unavailable page

GET /admin/api/v1/settings/features
→ 503 settings_store_unavailable

POST /admin/api/v1/settings/features/generations
→ 503 settings_store_unavailable
```

Already-running product behavior continues from:

```text
adopted in-memory AdminFeaturePlanV1
```

No request-time SettingsStore dependency.

---

# 98. FAILURE ISOLATION

Request-time Feature Settings failure must not break:

```text
Guest Portal
CAPPORT
Authorization
Omada authorization
already-composed Admin read surfaces
```

At startup, structurally invalid configured Feature config may prevent adoption of that generation under existing Settings fail-closed semantics.

---

# 99. AUDIT

Changed Feature generation writes ordinary immutable audit only for explicitly changed persisted override keys.

Audit includes existing ordinary fields and:

```text
setting_domain=features
value_type=string
```

Stored old/new values are canonical:

```text
"true"
"false"
```

Do NOT audit derived:

```text
feature_state
blocked_by
source health
```

No cascade audit rows.

---

# 100. MANAGED SECRET INDEPENDENCE

Feature Settings does not depend on:

```text
Stage-4 managed-secret production activation
master key availability
Controller secret store availability
```

Feature read/mutation does not require:

```text
admin.write.settings.controller.secret
```

Existing secret binding is only carried to child generation unchanged.

---

# 101. PROJECTION SOURCE FAILURE

`traffic.projection_read=true` does NOT claim:

```text
traffic-projection.service running
projection healthy
projection fresh
projection active
```

Features Settings does not probe projection health.

If projection query fails:

```text
historical product reports runtime source failure
```

Feature remains enabled.

No auto-mutation.

No auto-fallback.

---

# 102. UI MUST NOT CLAIM HEALTH

Settings → Features may show only:

```text
Enabled
Disabled
Dormant — parent disabled
Pending restart
```

It MUST NOT infer:

```text
Healthy
Connected
Fresh
Projection healthy
Current State healthy
```

---

# 103. NO PRODUCER CONTROLS ON FEATURES PAGE

No controls for:

```text
Current State collector
Observation collector
Visit Lifecycle
Visitor Registry
Pending Cleaner
Analytics module lifecycle
Traffic Projection writer
Device Fingerprint
AP-24H telemetry
Webhook
```

---

# 104. NO SYSTEMD AUTHORITY

No:

```text
Restart
Apply now
Start
Stop
Enable service
Disable service
systemctl
systemd D-Bus
sudo
```

Save persists only.

---

# 105. NO HOT RECONFIGURATION

No hot swap after Save.

No request-time replacement of:

```text
AdminFeaturePlanV1
historical gateway
Current State overlay configuration
```

Only a new `captive-portal.service` process may adopt a saved generation.

---

# 106. IMPLEMENTATION FORBIDDEN LIST

Coder MUST NOT implement/change:

```text
WEB_ADMIN_ENABLED mutation
WEB_ADMIN_SETTINGS_ENABLED mutation

Admin credentials/security mutation
Admin capability grant mutation

CAPPORT mutation

Site-scoped Feature settings

collector lifecycle
worker lifecycle
producer lifecycle

CURRENT_STATE_ENABLED mutation

Observation enable flags

Visit/Registry enable flags

Pending Cleaner enable flag

Analytics enable flags

OMADA_WEBHOOK_ENABLED mutation

TRAFFIC_PROJECTION_ENABLED mutation
traffic-projection.service control

Device Fingerprint process control

WEB_ADMIN_HOME_AP_24H_ENABLED mutation
WEB_ADMIN_HOME_AP_24H_TELEMETRY_ENABLED mutation

automatic parent/child cascade

generic environment editor

Feature-specific Settings DB
Feature-specific generation chain
Feature-specific ETag

multi-target activation

restart/apply button
hot reload
systemd authority

live source-health polling from Features Settings

raw secret/master-key access

unrelated UI redesign
```

---

# 107. ACCEPTANCE — REGISTRY

Mandatory:

```text
exactly 17 Feature definitions

total ordinary definitions = 46

exact keys
exact runtime mapping keys
all defaults false

domain=features
GLOBAL-only
normal/non-secret

main_service_restart
captive-portal.service

exact feature_id
exact group
exact control_kind
exact direct parents

WEB_ADMIN_HOME_AP_24H_ENABLED absent

no operational/process flag accidentally admitted
```

---

# 108. ACCEPTANCE — RESOLUTION

For every Feature prove:

```text
repository default
explicit environment
persisted override
clear_override fallback

base_source
configured_source
effective_source
```

No scalar-equality source inference.

No request-time environment reread.

---

# 109. ACCEPTANCE — PARENT GRAPH

Required cases:

```text
Traffic=false
History=true
→ valid / History dormant

Traffic=true
History=true
→ History enabled

Traffic=true
History=false
Statistics=true
→ Statistics dormant

Statistics=false
Peak=true
→ Peak dormant

History=false
ByAP=true
→ ByAP dormant

IndependentRanges=false
APShare=true
→ APShare dormant

HomeLive=false
HomeTraffic=true
→ HomeTraffic dormant

HomeLive=false
HomeActivity=true
→ HomeActivity dormant

parent re-enabled
→ child preference becomes usable after adoption
without child rewrite
```

---

# 110. ACCEPTANCE — NO CASCADE

Parent-only mutation must prove:

```text
only parent persisted value changes

only parent audit row exists

child overrides unchanged

changed_keys excludes untouched children
```

---

# 111. ACCEPTANCE — CONFIGURATION PREREQUISITES

Required:

```text
Home Activity enabled + valid config → PASS

Home Activity enabled + invalid Site/scope config
→ 422 configuration_prerequisite_invalid

Home Activity dormant + same optional config invalid
→ dormant preference remains valid

Device List Context enabled + valid cursor secret
→ PASS

Device List Context enabled + invalid cursor secret
→ safe 422 / no secret leak

Projection Read enabled + valid read config
→ PASS

Projection Read enabled + invalid read config
→ safe 422

Projection Read dormant + invalid read-only config
→ dormant preference remains valid until parent enable attempts composition
```

---

# 112. ACCEPTANCE — SOURCE OUTAGE

For enabled Feature, simulate:

```text
Current State unavailable
Analytics unavailable
Visit unavailable
Observation unavailable
Traffic Projection unavailable
```

Must NOT:

```text
change effective Feature value
create generation
create activation_failed
```

Product surfaces retain existing bounded runtime failure semantics.

---

# 113. ACCEPTANCE — ROUTE GATING

Mandatory:

```text
Home Live false
→ current-state APIs 404 before source query

Home Traffic dormant
→ current-traffic Home APIs 404 before source query

Home Activity false/dormant
→ Home Activity APIs 404 before source query

Home Health false
→ /home/health 404
→ /admin/api/v1/health unchanged

Traffic root false
→ nav absent
→ page 404
→ child APIs unavailable

History false
→ history 404

disabled Statistics/Peak/ByAP/APShare requested
→ 404 before child computation

Online Guests false
→ endpoint 404

Completed Sessions false
→ endpoint 404

Evidence false
→ endpoint 404

Device Current Context false
→ current endpoint 404
→ Device Card still available

Device List Context false
→ base Devices list available
→ overlay not requested
```

---

# 114. ACCEPTANCE — PROJECTION READ

Mandatory:

```text
projection-read false
→ existing non-projection historical source

projection-read true + parent enabled
→ TrafficProjectionReadService

projection unavailable
→ no automatic raw fallback

Feature mutation
→ no TRAFFIC_PROJECTION_ENABLED mutation

Feature mutation
→ no traffic-projection.service start/stop

writer lock configuration
→ not required by main read config
```

---

# 115. ACCEPTANCE — HEALTH

Mandatory:

```text
Home Traffic disabled/dormant
+
current traffic service absent
→ no degradation solely for optional missing service

Home Activity disabled/dormant
+
activity service absent
→ no degradation solely for optional missing service

Feature disablement
→ no new health-component failure

Home Health disabled
→ no Home Health evaluation
```

No 17-component health redesign.

---

# 116. ACCEPTANCE — ACTIVATION

Mandatory:

```text
Save Feature
→ configured generation changes

before restart
→ runtime product behavior unchanged

successful restart/adoption
→ exact configured generation effective

structural Feature composition failure
→ features_configuration_adoption_failed
→ effective generation not advanced
→ unadopted runtime not served as adopted

temporary source outage
→ adoption still succeeds if structural config valid
```

---

# 117. ACCEPTANCE — API

Read:

```text
GET /admin/api/v1/settings/features
api_version=admin.settings.features.v1

exact 17 ordered rows
exact metadata/state fields

no source query
no secret access
```

Mutation:

```text
POST /admin/api/v1/settings/features/generations
api_version=admin.settings.features.mutation.v1

JSON boolean only

changed → 201
no-op → 200

max 17 changes

common ETag/CAS
idempotency replay/conflict
```

---

# 118. ACCEPTANCE — AUTHORIZATION

Required matrix:

```text
no read
→ page/API forbidden

read only
→ GET allowed
→ mutation forbidden

write only
→ mutation forbidden

read + write
→ mutation allowed

new capabilities not default-granted
→ no silent existing-operator privilege increase
```

---

# 119. ACCEPTANCE — v5 MIGRATION

Required:

```text
empty v4 → v5
populated v4 → v5

generation IDs preserved
parents preserved
effective generation preserved

General overrides preserved
Controller overrides preserved
Portal overrides preserved

secret versions/bindings preserved
ordinary audit preserved
secret audit preserved
idempotency bytes preserved
activation events preserved

migration creates no generation
migration creates no Feature override

environment-owned production Feature state remains unchanged
```

---

# 120. ACCEPTANCE — STAGE-4 RECOVERY

Required:

```text
v5 + managed secret + Feature overrides
→ open_existing_for_recovery PASS

expected-generation CAS preserved

clear managed ownership only

Feature overrides copied unchanged

General/Controller/Portal overrides copied unchanged

no decrypt/read-back

no master-key requirement for break-glass clear

effective generation unchanged

immutable history preserved
```

Gate:

```text
v5 + Stage-4 break-glass recovery = PASS
```

---

# 121. ACCEPTANCE — SECRET ISOLATION

Feature read/mutation must work when:

```text
SettingsStore available
managed secret key/store unavailable
```

Tests must prove zero calls to:

```text
ControllerSecretRepository.resolve
load_master_key
decrypt_secret
```

from Feature read/mutation.

---

# 122. PRODUCTION ACTIVATION BOUNDARY

Stage-6 implementation does NOT itself:

```text
grant Feature Settings capabilities
create production Feature overrides
change production Feature values
restart production
perform production schema migration without separate deployment authorization
```

Production requires separate approved deploy/activation plan for:

```text
v4→v5 production migration
capability grant if desired
Feature override changes if desired
external captive-portal.service restart
post-adoption smoke
rollback readiness
```

---

# 123. OPEN QUESTIONS

```text
OPEN P0 = 0
OPEN P1 = 0
```

No implementation-relevant architecture choice remains open.

The current ownership conflict is explicitly resolved:

```text
WEB_ADMIN_HOME_AP_24H_ENABLED
→ DEFER
```

while:

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED
→ ADMIT
```

under the exact main-read vs writer-process split.

---

# 124. FINAL ARCHITECTURE DISPOSITION

```text
DOCUMENT =
CAPTIVPORTAL ADMIN SETTINGS
STAGE 6 — ADMIN PRODUCT BEHAVIOR / FEATURE CONTROLS
ARCHITECTURE CONTRACT v0.1

BASELINE =
main@701ce630b595a87e9350b826a06ee02eaebc7f9e

TREE =
59425257b1b9ddd557113da158c88d58bfe06bfc

CURRENT_SETTINGS_SCHEMA =
v4

TARGET_SETTINGS_SCHEMA =
v5

DOMAIN =
features

ADMITTED_FEATURE_CONTROLS =
17

HOME_ADMITTED =
4

TRAFFIC_ADMITTED =
11

DEVICES_ADMITTED =
2

WEB_ADMIN_HOME_AP_24H_ENABLED =
DEFER / NOT STAGE 6

WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED =
ADMIT

SCOPE =
GLOBAL ONLY

PARENT_FALSE_CHILD_TRUE =
VALID

AUTO_CASCADE_MUTATION =
FORBIDDEN

DORMANT_CHILD_STATE =
dormant_parent_disabled

CONFIGURED_EFFECTIVE_SEMANTICS =
UNCHANGED SETTINGS GENERATION SEMANTICS

LIVE_SOURCE_HEALTH_IN_FEATURE_SETTINGS =
NO

RUNTIME_SOURCE_OUTAGE =
DOES NOT INVALIDATE SETTINGS GENERATION

ACTIVATION =
main_service_restart

ACTIVATION_TARGET =
captive-portal.service

MULTI_PROCESS_ACTIVATION =
NO

ADMIN_SYSTEMD_AUTHORITY =
NO

FEATURE READ API =
GET /admin/api/v1/settings/features

FEATURE READ API VERSION =
admin.settings.features.v1

FEATURE MUTATION API =
POST /admin/api/v1/settings/features/generations

FEATURE MUTATION API VERSION =
admin.settings.features.mutation.v1

FEATURE RESOURCE =
admin_product_features / installation

MAX CHANGES =
17

COMMON GLOBAL ETAG =
YES

COMMON GLOBAL GENERATION =
YES

IDEMPOTENCY DOMAIN =
features

CAPABILITIES =
admin.read.settings.features
admin.write.settings.features

CAPABILITIES DEFAULT GRANTED =
NO

SECRET RESOLUTION DEPENDENCY =
NO

STAGE-4 BREAK-GLASS v5 =
REQUIRED / PRESERVED

OPEN_ARCH_P0 =
0

OPEN_ARCH_P1 =
0

ARCHITECTURE =
DRAFT FOR TECH LEAD REVIEW

IMPLEMENTATION TASK =
HOLD

CODER =
HOLD

SCHEMA CHANGE =
NO — PENDING ARCHITECTURE PASS

PRODUCTION CHANGE =
NO
```

---

# 125. NEXT GOVERNANCE STEP

```text
Tech Lead
→ review Stage-6 Architecture Contract v0.1

if PASS:
→ Technical Developer Settings prepares one exact implementation TASK
→ Tech Lead reviews implementation contract
→ only then Coder may be authorized

until then:

IMPLEMENTATION TASK = HOLD
CODER = HOLD
SCHEMA CHANGE = NO
PRODUCTION CHANGE = NO
```
