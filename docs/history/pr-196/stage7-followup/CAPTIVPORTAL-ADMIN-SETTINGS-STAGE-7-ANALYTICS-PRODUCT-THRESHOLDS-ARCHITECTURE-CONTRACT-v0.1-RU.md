# CAPTIVPORTAL ADMIN SETTINGS
## STAGE 7 — ANALYTICS / PRODUCT THRESHOLDS
### ARCHITECTURE CONTRACT v0.1
### DRAFT FOR TECH LEAD REVIEW

**Проект:** CaptivPortal  
**Роль:** Architect  
**Baseline:** `main@51deead342bd821b5c46fb75a7ceef37bef63e7c`  
**TREE:** `7b6cfa20c23c097e87059ca12a593f697f0a36a2`  
**Production baseline:** тот же exact HEAD/TREE — подтверждено Owner  
**Settings schema:** `v5`  
**Stage 6:** `CLOSED / PRODUCTION ACCEPTED`  
**Тип документа:** Architecture Contract; НЕ implementation TASK  
**Source changes:** `NO`  
**Production changes:** `NO`  
**Coder:** `HOLD`

---

# 0. BASELINE RE-PIN / CURRENT-STATE DISPOSITION

Перед подготовкой Stage 7 текущий `origin/main` был re-pinned.

Получено:

```text
origin/main HEAD =
51deead342bd821b5c46fb75a7ceef37bef63e7c
```

Это совпадает с baseline из Owner request.

Следовательно:

```text
BASELINE_MOVED = NO
```

Owner также подтвердил production на том же exact HEAD/TREE.

Stage 7 не переоткрывает Stage 6.

---

# 1. НАЗНАЧЕНИЕ STAGE 7

Stage 7 вводит только те Analytics параметры, которые являются понятной операторской политикой интерпретации результата.

Stage 7 НЕ является:

```text
.env editor

экраном всех полей AnalyticsConfig

экраном performance tuning

экраном operational module lifecycle

экраном Analytics API security

экраном background-worker tuning
```

Критерий admission:

```text
Operator должен понимать, КАКОЙ продуктовый смысл он меняет,
без знания внутреннего алгоритма или SQL.
```

Наличие поля в `AnalyticsConfig` само по себе admission не создаёт.

---

# 2. SOURCE-VERIFIED CURRENT ANALYTICS CONFIGURATION

Current source содержит один основной `AnalyticsConfig` со следующими полями:

```text
ANALYTICS_FOUNDATION_ENABLED

ANALYTICS_DEFAULT_LIMIT
ANALYTICS_MAX_LIMIT
ANALYTICS_MAX_QUERY_WINDOW_DAYS
ANALYTICS_MAX_QUERY_DURATION_SECONDS

ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS

ANALYTICS_WIRELESS_ENABLED
ANALYTICS_WIRELESS_MIN_SAMPLES
ANALYTICS_WIRELESS_MAX_WINDOW_DAYS

ANALYTICS_COUNTER_MAX_GAP_SECONDS
ANALYTICS_AP_JOIN_MAX_LAG_SECONDS

ANALYTICS_RSSI_THRESHOLD_DBM
ANALYTICS_SNR_THRESHOLD_DB

ANALYTICS_VISIT_ENABLED
ANALYTICS_VISIT_MIN_COHORT_SIZE
ANALYTICS_VISIT_MAX_WINDOW_DAYS
```

Current repository defaults:

```text
ANALYTICS_FOUNDATION_ENABLED=false

ANALYTICS_DEFAULT_LIMIT=500
ANALYTICS_MAX_LIMIT=2000
ANALYTICS_MAX_QUERY_WINDOW_DAYS=31
ANALYTICS_MAX_QUERY_DURATION_SECONDS=10

ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS=180

ANALYTICS_WIRELESS_ENABLED=true
ANALYTICS_WIRELESS_MIN_SAMPLES=20
ANALYTICS_WIRELESS_MAX_WINDOW_DAYS=7

ANALYTICS_COUNTER_MAX_GAP_SECONDS=180
ANALYTICS_AP_JOIN_MAX_LAG_SECONDS=120

ANALYTICS_RSSI_THRESHOLD_DBM=<empty / None>
ANALYTICS_SNR_THRESHOLD_DB=<empty / None>

ANALYTICS_VISIT_ENABLED=true
ANALYTICS_VISIT_MIN_COHORT_SIZE=20
ANALYTICS_VISIT_MAX_WINDOW_DAYS=90
```

Current canonical parser:

```text
app/analytics/config.py
→ analytics_config_from_settings()
```

Current source already validates:

```text
default_limit <= max_limit
max_limit <= 2000

max_query_window_days <= 31

wireless_max_window_days <= max_query_window_days

wireless_min_samples >= 2

visit_min_cohort_size >= 2

visit_max_window_days <= 90
```

RSSI/SNR are currently optional finite numbers.

---

# 3. CURRENT CONSUMER MAP — SOURCE VERIFIED

No listed field was found completely unused.

However several names are much broader than their real current consumer scope.

## 3.1. `ANALYTICS_FOUNDATION_ENABLED`

Consumed by:

```text
AnalyticsReadService
WirelessAnalyticsService
VisitAnalyticsService
Analytics runtime composition
```

Effect:

```text
operational enable/disable of Analytics runtime family
```

This is lifecycle/exposure behavior, not a product threshold.

## 3.2. `ANALYTICS_DEFAULT_LIMIT`

Current direct semantic consumer:

```text
AnalyticsReadService.list_visit_quality()
→ query_limit()
```

Effect:

```text
default page size when Analytics quality query omits limit
```

This is API/resource behavior.

It is NOT a general Analytics product threshold.

## 3.3. `ANALYTICS_MAX_LIMIT`

Current direct consumer:

```text
query_limit()
```

Effect:

```text
hard upper request/page bound
```

Existing code hard-caps it at:

```text
<= 2000
```

This is a resource-safety invariant.

## 3.4. `ANALYTICS_MAX_QUERY_WINDOW_DAYS`

Consumers:

```text
AnalyticsReadService query_range()

cross-validation ceiling for:
ANALYTICS_WIRELESS_MAX_WINDOW_DAYS
```

Existing hard ceiling:

```text
<= 31 days
```

This is a query-safety invariant.

## 3.5. `ANALYTICS_MAX_QUERY_DURATION_SECONDS`

Consumers include:

```text
AnalyticsReadService
WirelessAnalyticsService
VisitAnalyticsService
HistoricalTrafficReadService
```

Effect:

```text
QueryDeadline / bounded read execution
```

This is resource/DoS containment.

## 3.6. `ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS`

Verified consumers:

```text
AnalyticsReadService
→ Visit observation coverage

VisitAnalyticsService
→ observation coverage

VisitAnalyticsService
→ Visit wireless coverage

HistoricalTrafficReadService
→ gap classification
→ bucket completeness/partial semantics
→ historical traffic interval acceptance semantics

HomeAp24ReadService
→ observation quality
→ observation lookback/gap interpretation
```

Current gap comparison semantics:

```text
gap > threshold
→ gap is over threshold

gap == threshold
→ NOT over threshold
```

This value directly changes product interpretation of evidence quality.

## 3.7. `ANALYTICS_WIRELESS_ENABLED`

Consumed by:

```text
WirelessAnalyticsService
VisitAnalyticsService wireless paths
```

Effect:

```text
operational module availability
```

Not a threshold.

## 3.8. `ANALYTICS_WIRELESS_MIN_SAMPLES`

Consumers:

```text
Wireless distributions
Wireless correlation

Visit wireless signal distribution
Visit wireless correlation
```

Effect:

```text
minimum statistical sample requirement
before result is considered sufficient
```

It also affects whether Pearson correlation is emitted.

This is algorithm/statistical-quality tuning.

## 3.9. `ANALYTICS_WIRELESS_MAX_WINDOW_DAYS`

Consumers:

```text
WirelessAnalyticsService query range
VisitAnalyticsService per-Visit wireless window
```

Effect:

```text
resource/performance bound
```

Not an operator policy threshold.

## 3.10. `ANALYTICS_COUNTER_MAX_GAP_SECONDS`

Consumers:

```text
Wireless counter/rate analysis
Visit observed-traffic summary
```

Effect:

```text
which counter intervals are considered sufficiently continuous
for traffic/rate derivation
```

This changes the data-model acceptance of counter deltas.

## 3.11. `ANALYTICS_AP_JOIN_MAX_LAG_SECONDS`

Consumers:

```text
Wireless signal ↔ AP resource correlation

Visit wireless correlation
```

Effect:

```text
temporal matching tolerance between two evidence streams
```

This is analytical join semantics.

## 3.12. `ANALYTICS_RSSI_THRESHOLD_DBM`

Consumers:

```text
WirelessAnalyticsService.get_signal_distribution()

VisitAnalyticsService per-Visit wireless signal distribution
```

Current Wireless Analytics API also permits an explicit per-request:

```text
threshold=
```

Therefore this configuration value is:

```text
DEFAULT THRESHOLD
```

not an absolute policy that callers can never override.

Current comparison:

```text
sample_value < threshold
→ below threshold

sample_value == threshold
→ NOT below threshold
```

When threshold is `None`:

```text
threshold value = null
below_threshold_count = null
below_configured_threshold_ratio = null
```

The base RSSI distribution itself remains available.

## 3.13. `ANALYTICS_SNR_THRESHOLD_DB`

Same semantics as RSSI:

```text
default per-query threshold
sample < threshold → below threshold
None → no configured-threshold ratio
```

RSSI and SNR remain independent.

No combined Wi-Fi score is created by Stage 7.

## 3.14. `ANALYTICS_VISIT_ENABLED`

Consumed by:

```text
VisitAnalyticsService
```

Effect:

```text
operational Visit Analytics availability
```

Not a threshold.

## 3.15. `ANALYTICS_VISIT_MIN_COHORT_SIZE`

Current source scope is narrower than the name suggests.

Verified current direct use:

```text
VisitAnalyticsService.get_return_intervals()
```

It controls:

```text
minimum sample count
for return-interval distribution sufficiency
```

It is NOT currently a general privacy suppression floor across Visit Analytics.

It is NOT currently a guarantee that all Visit metrics hide small cohorts.

Therefore Stage 7 MUST NOT present it as a "privacy cohort size".

## 3.16. `ANALYTICS_VISIT_MAX_WINDOW_DAYS`

Consumer:

```text
VisitAnalyticsService._query()
```

Effect:

```text
hard maximum Visit Analytics query window
```

Existing ceiling:

```text
<= 90 days
```

This is resource/query safety.

---

# 4. NEIGHBORING ANALYTICS API CONFIGURATION — EXPLICITLY REVIEWED

Current source also contains separate internal Analytics API configuration:

```text
ANALYTICS_API_ENABLED
ANALYTICS_API_BEARER_TOKEN
ANALYTICS_API_ALLOWED_NETWORKS
ANALYTICS_API_ALLOWED_SITE_IDS
ANALYTICS_API_MAX_CONCURRENT_REQUESTS
ANALYTICS_API_MAX_RESPONSE_BYTES
```

These are NOT Stage-7 product thresholds.

Disposition:

```text
ANALYTICS_API_ENABLED
→ D / operational-security domain
→ NOT Stage 7

ANALYTICS_API_BEARER_TOKEN
→ D / secret-security boundary
→ NOT ordinary Settings
→ NOT Stage 7

ANALYTICS_API_ALLOWED_NETWORKS
→ D / security/access boundary
→ NOT Stage 7

ANALYTICS_API_ALLOWED_SITE_IDS
→ D / authorization/Site access boundary
→ NOT Stage 7

ANALYTICS_API_MAX_CONCURRENT_REQUESTS
→ C / INTERNAL-ONLY safety control

ANALYTICS_API_MAX_RESPONSE_BYTES
→ C / INTERNAL-ONLY safety control
```

Stage 7 does not enlarge the internal Analytics API security surface.

---

# 5. ADMISSION RESULT — EXACT

Stage 7 admits exactly THREE existing configuration keys:

```text
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS

ANALYTICS_RSSI_THRESHOLD_DBM

ANALYTICS_SNR_THRESHOLD_DB
```

No other Analytics parameter is Admin-editable in Stage 7.

Therefore:

```text
STAGE_7_ADMITTED_KEY_COUNT = 3
```

---

# 6. COMPLETE CLASSIFICATION MATRIX

| Existing key | Decision | Reason |
|---|---|---|
| `ANALYTICS_FOUNDATION_ENABLED` | **D — Stage 8 / Operational Module Settings** | Operational Analytics lifecycle/availability; Stage 6 controls Admin product surfaces, not underlying Analytics module lifecycle. |
| `ANALYTICS_DEFAULT_LIMIT` | **C — INTERNAL-ONLY** | Internal API/page-size default; current scope is narrow and not a product analytical meaning. |
| `ANALYTICS_MAX_LIMIT` | **C — INTERNAL-ONLY** | Request/resource safety ceiling; operator must not loosen hard containment. |
| `ANALYTICS_MAX_QUERY_WINDOW_DAYS` | **C — INTERNAL-ONLY** | Query safety ceiling and parent bound for wireless window. |
| `ANALYTICS_MAX_QUERY_DURATION_SECONDS` | **C — INTERNAL-ONLY** | Query deadline / DoS/resource containment. |
| `ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS` | **A — ADMIT** | Direct operator-meaningful evidence-quality interpretation: how long a gap may be before it is classified as a quality gap. |
| `ANALYTICS_WIRELESS_ENABLED` | **D — Stage 8 / Operational Module Settings** | Operational module availability, not threshold. |
| `ANALYTICS_WIRELESS_MIN_SAMPLES` | **C — INTERNAL-ONLY** | Statistical algorithm sufficiency and correlation stability; lowering it changes validity guarantees. |
| `ANALYTICS_WIRELESS_MAX_WINDOW_DAYS` | **C — INTERNAL-ONLY** | Resource/query safety bound. |
| `ANALYTICS_COUNTER_MAX_GAP_SECONDS` | **C — INTERNAL-ONLY** | Technical counter-delta acceptance/data-model semantics. |
| `ANALYTICS_AP_JOIN_MAX_LAG_SECONDS` | **C — INTERNAL-ONLY** | Technical temporal join semantics. |
| `ANALYTICS_RSSI_THRESHOLD_DBM` | **A — ADMIT** | Operator-meaningful default threshold for below-threshold RSSI ratio. |
| `ANALYTICS_SNR_THRESHOLD_DB` | **A — ADMIT** | Operator-meaningful default threshold for below-threshold SNR ratio. |
| `ANALYTICS_VISIT_ENABLED` | **D — Stage 8 / Operational Module Settings** | Operational module availability. |
| `ANALYTICS_VISIT_MIN_COHORT_SIZE` | **C — INTERNAL-ONLY** | Current source uses it only for return-interval statistical sufficiency; it is not a general privacy control. |
| `ANALYTICS_VISIT_MAX_WINDOW_DAYS` | **C — INTERNAL-ONLY** | Query/resource safety ceiling. |

There are no unresolved B-class parameters in the current Stage-7 admission.

Future re-admission of a C/D item requires a new explicit architecture decision.

---

# 7. ENABLE FLAGS — STAGE 6 / STAGE 7 / STAGE 8 BOUNDARY

The following MUST NOT be absorbed into the Stage-6 feature graph:

```text
ANALYTICS_FOUNDATION_ENABLED
ANALYTICS_WIRELESS_ENABLED
ANALYTICS_VISIT_ENABLED
```

Reason:

Stage 6 owns:

```text
Admin product/read feature exposure
```

These three flags own:

```text
underlying Analytics module composition / availability
```

Mapping them into Stage 6 would create semantic conflation:

```text
Admin page visible
!=
Analytics module operationally enabled
```

Therefore:

```text
Stage 6 feature controls remain unchanged.

Stage 7 exposes no enable switches.

Analytics enable flags remain deployment-owned
until Stage 8 / Operational Module Settings architecture.
```

No second panel controls the same availability.

---

# 8. QUERY / RESOURCE SAFETY CONTROLS — PERMANENT STAGE-7 DISPOSITION

The following remain INTERNAL-ONLY:

```text
ANALYTICS_DEFAULT_LIMIT
ANALYTICS_MAX_LIMIT
ANALYTICS_MAX_QUERY_WINDOW_DAYS
ANALYTICS_MAX_QUERY_DURATION_SECONDS
ANALYTICS_WIRELESS_MAX_WINDOW_DAYS
ANALYTICS_VISIT_MAX_WINDOW_DAYS
```

Stage 7 MUST NOT allow Admin operator to relax hard query/resource containment.

Existing architecture/code-owned constraints remain authoritative, including:

```text
ANALYTICS_MAX_LIMIT <= 2000

ANALYTICS_MAX_QUERY_WINDOW_DAYS <= 31

ANALYTICS_WIRELESS_MAX_WINDOW_DAYS
<=
ANALYTICS_MAX_QUERY_WINDOW_DAYS

ANALYTICS_VISIT_MAX_WINDOW_DAYS <= 90
```

`ANALYTICS_MAX_QUERY_DURATION_SECONDS` currently has positive-finite validation rather than a separately frozen architecture hard upper ceiling.

Stage 7 does NOT invent an Admin-editable deadline or a new hard ceiling.

Any future operator exposure of query deadlines requires a separate resource-safety architecture.

---

# 9. DATA-MODEL / ALGORITHM TUNING — INTERNAL-ONLY

The following stay outside Stage 7:

```text
ANALYTICS_COUNTER_MAX_GAP_SECONDS
ANALYTICS_AP_JOIN_MAX_LAG_SECONDS
ANALYTICS_WIRELESS_MIN_SAMPLES
ANALYTICS_VISIT_MIN_COHORT_SIZE
```

Reason:

They alter:

```text
counter interval acceptance
temporal stream joining
correlation statistical validity
distribution sufficiency
```

These are not currently simple operator policies.

Especially:

```text
ANALYTICS_VISIT_MIN_COHORT_SIZE
```

MUST NOT be described as privacy protection.

Current source does not support that claim.

---

# 10. STAGE-7 SETTINGS DOMAIN

Introduce one new ordinary Settings domain:

```text
domain = analytics
```

Do NOT create:

```text
separate Analytics Settings DB
separate generation chain
separate ETag
separate SettingsStore
separate audit system
```

Reuse:

```text
SettingsDefinitionRegistry
Settings resolver
SettingsStore
global Settings generations
CAS / If-Match
idempotency
ordinary mutation audit
main-service adoption
effective generation
```

Stage-7 definitions increase the common registry by exactly:

```text
+3
```

From current:

```text
12 General
3 Controller
14 Portal
17 Features
=
46
```

to:

```text
49 total ordinary definitions
```

---

# 11. EXACT DEFINITION — QUALITY GAP

Canonical key:

```text
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
```

Runtime mapping key:

```text
analytics_quality_gap_threshold_seconds
```

Display label:

```text
Observation gap threshold
```

Group:

```text
data_quality
```

Operator description:

```text
Maximum gap that is still treated as continuous analytical coverage.
A gap greater than this value is classified as a data-quality gap
by consumers using the common Analytics gap policy.
```

Public type:

```text
integer
```

Internal Settings value type:

```text
string
```

Unit:

```text
seconds
```

Repository default:

```text
180
```

Allowed Stage-7 managed range:

```text
1 .. 3600 seconds inclusive
```

Nullable:

```text
NO
```

Comparison semantics:

```text
gap > threshold
→ over-threshold quality gap

gap <= threshold
→ not over threshold
```

Scope:

```text
GLOBAL
```

Secret class:

```text
normal
```

Editable:

```text
true
```

Apply requirement:

```text
main_service_restart
```

Activation target:

```text
captive-portal.service
```

Presentation type:

```text
duration_seconds
```

---

# 12. EXACT DEFINITION — RSSI

Canonical key:

```text
ANALYTICS_RSSI_THRESHOLD_DBM
```

Runtime mapping key:

```text
analytics_rssi_threshold_dbm
```

Display label:

```text
Default RSSI threshold
```

Group:

```text
wireless_signal
```

Operator description:

```text
Default RSSI threshold used to calculate the share of accepted RSSI
samples below the configured threshold when a query does not provide
its own explicit threshold.
```

Public type:

```text
nullable_integer
```

Internal Settings value type:

```text
string
```

Unit:

```text
dBm
```

Repository default:

```text
null
```

Internal repository-default representation:

```text
""
```

Allowed non-null Stage-7 managed range:

```text
-120 .. -1 dBm inclusive
```

Nullable:

```text
YES
```

`null` semantics:

```text
no default RSSI threshold

threshold-related:
threshold
below_threshold_count
below_configured_threshold_ratio

remain null unless an explicit query threshold is supplied.
```

Comparison:

```text
sample RSSI < applied threshold
→ below threshold

sample RSSI == threshold
→ NOT below threshold
```

Scope:

```text
GLOBAL
```

Secret class:

```text
normal
```

Editable:

```text
true
```

Apply:

```text
main_service_restart
```

Activation target:

```text
captive-portal.service
```

Presentation type:

```text
rssi_dbm
```

---

# 13. EXACT DEFINITION — SNR

Canonical key:

```text
ANALYTICS_SNR_THRESHOLD_DB
```

Runtime mapping key:

```text
analytics_snr_threshold_db
```

Display label:

```text
Default SNR threshold
```

Group:

```text
wireless_signal
```

Operator description:

```text
Default SNR threshold used to calculate the share of accepted SNR
samples below the configured threshold when a query does not provide
its own explicit threshold.
```

Public type:

```text
nullable_integer
```

Internal Settings value type:

```text
string
```

Unit:

```text
dB
```

Repository default:

```text
null
```

Internal repository-default representation:

```text
""
```

Allowed non-null Stage-7 managed range:

```text
-100 .. 100 dB inclusive
```

Nullable:

```text
YES
```

`null` semantics:

```text
no default SNR threshold
```

Comparison:

```text
sample SNR < applied threshold
→ below threshold

sample SNR == threshold
→ NOT below threshold
```

Scope / secret / activation:

```text
GLOBAL
normal
editable=true
main_service_restart
captive-portal.service
```

Presentation type:

```text
snr_db
```

---

# 14. RANGE SEMANTICS

Stage-7 RSSI/SNR ranges are product-management guardrails.

They are NOT claims that all physical devices can only emit values inside those ranges.

Raw Observation source validation remains unchanged.

An out-of-range source observation is not reclassified by Stage 7.

Only the operator-managed threshold itself is bounded.

---

# 15. MUTATION PUBLIC TYPES VS DURABLE TYPES

The existing SettingsStore supports:

```text
integer
string
```

Stage 7 MUST NOT add SQLite REAL/FLOAT Settings storage.

All three Analytics overrides are durably stored as:

```text
value_type = string
```

Canonical durable representation:

```text
QUALITY GAP:
"180"

RSSI:
"-70"
or
""

SNR:
"10"
or
""
```

Public API does NOT expose the storage encoding as product value.

Public projections are:

```text
QUALITY GAP:
integer

RSSI:
integer | null

SNR:
integer | null
```

---

# 16. MUTATION NORMALIZATION

For Stage-7 mutation:

## Quality gap

Accepted JSON `value`:

```text
integer
```

Rejected:

```text
boolean
float
string
null
```

## RSSI/SNR

Accepted JSON `value`:

```text
integer
or
null
```

Rejected:

```text
boolean
float
string
```

Canonical persistence:

```text
integer
→ canonical base-10 ASCII text

null
→ ""
```

No whitespace.

No leading `+`.

No decimal/exponent representation.

Idempotency request fingerprint is computed AFTER canonical Stage-7 value normalization.

Therefore semantically identical accepted values have one canonical request representation.

---

# 17. LOWER-PRECEDENCE ENVIRONMENT NORMALIZATION

For these three admitted keys, selected environment values must resolve under the same semantic type contract.

Accepted environment forms:

```text
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
→ ASCII integer text only

ANALYTICS_RSSI_THRESHOLD_DBM
→ ASCII signed integer text or exact empty string

ANALYTICS_SNR_THRESHOLD_DB
→ ASCII signed integer text or exact empty string
```

Whitespace is rejected.

Floating/exponent environment values become invalid Stage-7 product configuration.

No rounding or truncation is permitted.

This deliberately aligns all active consumers on one exact Stage-7 product representation.

---

# 18. RESOLUTION PRECEDENCE

For all three:

```text
persisted Settings override
>
explicit process environment
>
repository default
```

Reset means:

```text
clear_override
```

and therefore:

```text
relinquish Settings ownership
→ expose selected environment/default source
```

Reset MUST NOT write the default value into SettingsStore.

---

# 19. NULL OVERRIDE VS RESET — IMPORTANT

For RSSI/SNR:

```text
Set "Not set"
!=
Reset
```

Exact semantics:

```text
set value=null
→ create/retain a persisted override
→ override lower-precedence environment value
→ effective default threshold is disabled/null
```

while:

```text
clear_override
→ remove persisted override
→ environment/default regains authority
```

The read model MUST include:

```text
persisted_override_present
```

because:

```text
persisted_override_value=null
```

alone cannot distinguish:

```text
explicit managed null
```

from:

```text
no override exists
```

---

# 20. CROSS-SETTING VALIDATION

No cross-field relationship is introduced between the three admitted values.

Specifically:

```text
RSSI and SNR are independent.

QUALITY GAP does not depend on RSSI/SNR.

QUALITY GAP does not gain a cross-validation rule against
Current State interval or Observation cadence in Stage 7.
```

Reason:

Those operational cadences belong to Stage 8.

Stage 7 MUST NOT create a hidden Stage-7 → Stage-8 ownership dependency.

---

# 21. VALIDATION OWNERSHIP

Analytics semantic validation remains owned by:

```text
app/analytics/config.py
```

Stage 7 introduces one canonical semantic projection:

```text
AnalyticsProductThresholdsV1
```

and one canonical parser/normalizer owned by the Analytics domain.

Conceptually:

```text
analytics_product_thresholds_from_settings(...)
```

Settings control plane MUST delegate to this canonical Analytics-owned validation/normalization.

Bounds MUST NOT be independently reimplemented in:

```text
JavaScript
route
Settings mutation service
Analytics runtime consumer
```

The Settings read API supplies validation metadata to the UI.

---

# 22. `AnalyticsProductThresholdsV1`

Exact immutable runtime projection:

```text
AnalyticsProductThresholdsV1

schema_version = 1

settings_generation:
    integer | null

quality_gap_threshold_seconds:
    integer

rssi_threshold_dbm:
    integer | null

snr_threshold_db:
    integer | null
```

`settings_generation=null` is allowed only when the Settings control plane is deployment-disabled and runtime values therefore come from the legacy environment/default path.

No Site ID exists in V1.

---

# 23. SINGLE STARTUP COMPOSITION

When Settings is enabled:

```text
base settings
→ SettingsStore resolution
→ ResolvedSettingsSnapshot(G)
→ AdminFeaturePlanV1(G)
→ AnalyticsProductThresholdsV1(G)
→ runtime composition
```

Exactly one Stage-7 runtime policy object is built for generation `G`.

The SAME object/value set is injected into every Stage-7 consumer.

No admitted consumer may independently re-resolve:

```text
os.getenv()
get_settings()
SettingsStore
```

after bootstrap.

---

# 24. EXACT CONSUMER INJECTION

The adopted policy feeds:

```text
AnalyticsConfig
→ quality_gap_threshold_seconds
→ rssi_threshold_dbm
→ snr_threshold_db

HistoricalTrafficReadService
→ quality gap

AnalyticsReadService
→ quality gap

WirelessAnalyticsService
→ RSSI/SNR defaults

VisitAnalyticsService
→ quality gap
→ RSSI/SNR defaults

HomeAp24ReadService
→ quality gap
```

Current direct Admin Home AP-24H composition MUST stop independently reading:

```text
settings.get("analytics_quality_gap_threshold_seconds", ...)
```

when Settings-managed Stage-7 composition is active.

It receives the same adopted `AnalyticsProductThresholdsV1`.

---

# 25. SETTINGS-DISABLED COMPATIBILITY

If:

```text
WEB_ADMIN_SETTINGS_ENABLED=false
```

then:

```text
no Stage-7 managed SettingsStore semantics exist
no Stage-7 Settings UI/API exists
no Stage-7 generation adoption exists
```

Existing deployment/environment Analytics configuration behavior is preserved.

Stage 7 MUST NOT make a historically dormant Analytics deployment fail the whole Portal solely because Settings itself is disabled.

---

# 26. ACTIVATION

All admitted Stage-7 changes require:

```text
captive-portal.service restart
```

No hot reload.

No in-request mutation of existing service objects.

No systemd authority in Admin.

No Restart button.

No Apply button.

Save means:

```text
configured generation persisted
```

not:

```text
running Analytics immediately changed
```

---

# 27. GENERATION / ETag

Stage 7 uses the SAME global Settings generation chain.

Therefore:

```text
Portal mutation
Features mutation
General mutation
Controller mutation
Analytics mutation
```

all participate in one configured generation head.

ETag remains:

```text
"settings-g<N>"
```

Concurrent mutation in another domain can make an Analytics write stale.

This is intentional.

---

# 28. ADOPTION

On restart, main runtime adopts one exact configured generation.

Stage-7 policy belongs to that same adoption.

`SettingsActivationService` must attest:

```text
AnalyticsProductThresholdsV1.settings_generation
==
ResolvedSettingsSnapshot.generation_id
```

and that active Stage-7 consumers use the same adopted policy.

No second "Analytics effective generation" is created.

---

# 29. ACTIVATION FAILURE CATEGORY

Introduce safe Stage-7 adoption failure category:

```text
analytics_configuration_adoption_failed
```

It applies only when:

```text
an admitted Stage-7 value cannot be composed
under the accepted Stage-7 contract

or

a consumer that must receive the adopted Stage-7 policy
receives a different/mismatched policy
```

In that case:

```text
configured generation remains configured
effective generation does not advance
activation event = failed
```

No partial adoption.

---

# 30. WHAT IS NOT STAGE-7 ACTIVATION FAILURE

The following are NOT, by themselves:

```text
analytics_configuration_adoption_failed
```

```text
Observation source unavailable

Visit DB unavailable

Registry unavailable

Traffic source unavailable

Analytics query timeout

Analytics API disabled

Analytics Foundation disabled

Wireless Analytics disabled

Visit Analytics disabled

Stage-6 Admin product surface disabled

normal runtime source degradation
```

Those remain operational/product availability states.

Settings activation is configuration adoption, not source-health attestation.

---

# 31. DORMANT VALUES

Stage 7 adopts the Stage-6 preservation principle:

```text
disabled parent/dependency
does NOT erase child preference.
```

If an Analytics consumer is disabled:

```text
persisted threshold override remains
configured value remains
generation history remains
audit remains
```

No automatic mutation to default/null occurs.

When the owning module is later enabled under its own accepted lifecycle and the main service restarts:

```text
the existing configured Stage-7 preference becomes eligible for use.
```

---

# 32. CONSUMER STATE

Stage-7 read model uses:

```text
active
dormant_dependency_disabled
runtime_unavailable
```

## `active`

At least one owning runtime consumer is intentionally enabled and has adopted the Stage-7 policy.

## `dormant_dependency_disabled`

All known consumers of that setting are intentionally disabled by their non-Stage-7 parent/lifecycle controls.

## `runtime_unavailable`

A consumer is configured to exist but startup composition/adoption does not provide a trustworthy runtime consumer for the adopted policy.

Transient source/query degradation after successful composition does NOT change `consumer_state` to `runtime_unavailable`; it remains the owning product runtime's operational degraded/unavailable state.

`runtime_unavailable` is not the same as Settings activation failure.

---

# 33. QUALITY-GAP CONSUMER DEPENDENCIES

`ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS` is potentially consumed by:

```text
Analytics Foundation family
when:
ANALYTICS_FOUNDATION_ENABLED=true
AND ANALYTICS_API_ENABLED=true

and/or

Home AP-24H
when:
WEB_ADMIN_ENABLED=true
AND WEB_ADMIN_HOME_AP_24H_ENABLED=true
```

These are current source composition prerequisites; Stage 7 does not take ownership of those flags.

It is therefore considered `active` if at least one known consumer has adopted the policy.

A disabled Stage-6 Traffic surface does not erase or rewrite the value.

---

# 34. RSSI/SNR CONSUMER DEPENDENCIES

RSSI/SNR defaults require the existing Wireless Analytics path.

Exact current source prerequisites for an active default-threshold consumer are:

```text
ANALYTICS_FOUNDATION_ENABLED=true
AND ANALYTICS_API_ENABLED=true
AND ANALYTICS_WIRELESS_ENABLED=true
```

`ANALYTICS_VISIT_ENABLED` is not required for this consumer state because the standalone `WirelessAnalyticsService` is itself a threshold consumer.

Stage 7 does not take ownership of any of these enable flags.

If that path is intentionally disabled:

```text
consumer_state=dormant_dependency_disabled
```

The configured default remains stored.

Stage 7 does NOT take ownership of those operational enable flags.

---

# 35. EFFECTIVE VALUE WHILE DORMANT

To preserve existing Settings semantics:

```text
configured_value
→ retained and visible

effective_value
→ null while no trustworthy active consumer exists

consumer_state
→ dormant_dependency_disabled
```

After the consumer becomes active and the adopted generation is trustworthy:

```text
effective_value
→ adopted public value
```

`pending_value` is calculated against the adopted startup configuration, not against the public null used to represent a dormant consumer.

Therefore dormant state MUST NOT create false perpetual pending state.

---

# 36. STAGE-6 DEPENDENCY SEMANTICS

Stage 7 does NOT add these thresholds as children to `AdminFeaturePlanV1`.

Feature-plan state affects whether a product surface consumes/displays Analytics, not whether the threshold preference exists.

Therefore:

```text
Feature OFF
→ threshold retained

Feature ON later
→ no threshold rewrite required
```

No Stage-6 feature mutation cascades into Analytics domain.

No Analytics mutation cascades into Stage-6 Features domain.

---

# 37. HISTORICAL DATA SEMANTICS — QUALITY GAP

`ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS` changes interpretation at READ TIME.

It does NOT rewrite:

```text
Observation rows
Visit rows
Current State rows
Traffic Projection source facts
```

After successful restart/adoption, a query for the SAME historical interval may produce different:

```text
gap counts
partial/complete quality state
accepted interval interpretation
historical traffic quality
Home AP-24H quality state
```

because current product policy changed.

This is intentional.

The system MUST NOT claim that stored historical source facts themselves changed.

---

# 38. HISTORICAL DATA SEMANTICS — RSSI/SNR

Changing RSSI/SNR threshold does NOT alter:

```text
stored RSSI
stored SNR
distribution min/max/percentiles
sample count
source rows
```

It may alter only threshold-derived fields such as:

```text
below_threshold_count
below_configured_threshold_ratio
```

for future reads that use the configured default.

---

# 39. RESULT PROVENANCE REQUIREMENT

No new durable Analytics-result store is introduced.

Therefore Stage 7 does NOT require a separate persisted `settings_generation` marker on every historical source fact.

Instead every threshold-sensitive product result MUST expose the actual applied threshold value.

Existing source already does this for:

```text
VisitObservationCoverage.gap_threshold_seconds

ConfiguredThresholdRatio.threshold
```

Stage 7 additionally requires exact applied quality-gap value on the currently non-self-describing affected products:

```text
Historical Traffic result

Home AP-24H result
```

Exact public field:

```text
quality_gap_threshold_seconds
```

It must equal the actual adopted threshold used for that result.

No configuration generation number is required in those result DTOs because:

```text
results are read-time derived
not durably materialized
and the exact applied semantic value is carried by the result.
```

If a future stage persists/caches threshold-derived Analytics results across generations, that future stage MUST introduce explicit configuration provenance before admission.

---

# 40. REQUEST-SPECIFIC RSSI/SNR OVERRIDE

Current internal Analytics API supports:

```text
/wireless/signal?...&threshold=<value>
```

Stage 7 does NOT remove this behavior.

Therefore the Settings values are named and documented as:

```text
DEFAULT RSSI threshold
DEFAULT SNR threshold
```

Exact precedence for one wireless signal query:

```text
explicit query threshold
>
adopted Stage-7 default threshold
```

The result must continue exposing the actual applied threshold.

Stage 7 MUST NOT describe the global setting as an unavoidable classification boundary.

The Stage-7 managed bounds apply only to the managed default values. They do NOT silently tighten or redefine the existing explicit per-request `threshold` contract of the internal Analytics API; that API remains outside Stage-7 Settings ownership.

---

# 41. NO WI-FI QUALITY CLASSIFIER

Stage 7 does NOT create:

```text
Good
Fair
Poor
Weak
Excellent
```

Wi-Fi classes.

It does not create a combined RSSI/SNR score.

It only controls a numeric below-threshold comparison already present in Analytics.

Any future categorical Wi-Fi quality policy requires a separate architecture.

---

# 42. SETTINGS VALIDATION — REGISTERED VALUES

When Settings is enabled, every registered Stage-7 scalar is always primitive/product validated, even when its consumers are dormant.

Therefore these are always invalid:

```text
quality gap outside 1..3600

RSSI non-null outside -120..-1

SNR non-null outside -100..100

wrong type

float

NaN/Infinity

whitespace-bearing lower-precedence representation

non-integer text representation
```

Dormancy does not permit storing malformed Stage-7 configuration.

---

# 43. NON-REGISTERED ANALYTICS TUNING VALIDATION

Non-admitted Analytics configuration remains outside Settings registry.

Stage-7 mutation MUST NOT fail merely because a dormant, non-registered operational/tuning Analytics parameter would be invalid if its module were activated.

This preserves the Stage-6 principle:

```text
registered managed scalar
→ always primitive validated

supporting/non-registered runtime config
→ validated according to the owning module activation boundary
```

Stage 7 MUST NOT reintroduce raw fail-closed checks for dormant operational Analytics modules through another Settings mutation domain.

---

# 44. CROSS-DOMAIN MUTATION VALIDATION

After Stage 7 is active, valid dormant Analytics-threshold combinations remain valid during:

```text
Analytics mutation
General mutation
Controller mutation
Portal mutation
Features mutation
main startup validation
```

All three registered Analytics values remain primitive-validated.

But another Settings domain MUST NOT need:

```text
Analytics API bearer token
Analytics source availability
live Analytics query
Observation DB read
Visit DB read
```

to create a generation.

---

# 45. SECRET ISOLATION

Analytics Settings are non-secret.

Analytics read/mutation/rendering MUST NOT:

```text
open ControllerSecretRepository

read master key

decrypt OMADA_CLIENT_SECRET

require secret-store availability

read back secret material
```

An Analytics mutation carries the parent generation's existing secret binding forward unchanged using the common generation mechanism.

General/Controller existing secret prerequisites remain unchanged.

---

# 46. FAILURE OF SETTINGSSTORE

If SettingsStore becomes unavailable AFTER successful startup/adoption:

```text
already adopted Analytics runtime continues
with its immutable startup policy.
```

Analytics Settings read/write API returns:

```text
503 settings_store_unavailable
```

No fallback to a newly reread environment occurs inside HTTP request handling.

---

# 47. SETTINGS SCHEMA VERSION

Stage 7 requires:

```text
Settings schema v6
```

Reason:

Current schema v5 constrains:

```text
settings_mutation_audit.setting_domain

settings_idempotency.mutation_domain
```

to the existing domains.

Stage 7 adds:

```text
analytics
```

No new Settings database is created.

---

# 48. EXACT v6 DOMAIN TYPE CONTRACT

Semantic audit type contract:

```text
general
→ value_type=integer

controller
portal
features
analytics
→ value_type=string
```

For `analytics`:

```text
previous_configured_value
new_configured_value

and non-null persisted override values

must be SQLite TEXT.
```

Nullable product semantics for RSSI/SNR are represented as:

```text
text ""
```

not SQL NULL when a persisted explicit-null override exists.

SQL NULL continues to mean:

```text
no persisted override
```

where applicable.

---

# 49. EXACT v6 TABLE DELTA

v5 → v6 rebuilds only the tables whose CHECK constraints need the new domain:

```text
settings_mutation_audit

settings_idempotency
```

Required changes:

```text
settings_mutation_audit.setting_domain
adds:
analytics

settings mutation audit value-type CHECK
adds:
analytics → string/text

settings_idempotency.mutation_domain
adds:
analytics
```

Unchanged storage capability:

```text
settings_overrides already supports string values
```

No Analytics-specific table is added.

---

# 50. v6 MIGRATION PRESERVATION

Migration MUST preserve exactly:

```text
all generation IDs
all parent_generation_id values
configured head
effective target generation
General overrides
Controller overrides
Portal overrides
Feature overrides
secret versions
secret bindings
activation events
ordinary mutation audit
secret mutation audit
idempotency records
original timestamps
principal identity
request identity
history identity
```

Migration creates:

```text
NO new Settings generation
NO default Analytics override
NO mutation audit event
NO activation event
NO secret version
```

---

# 51. v6 ENTRY PATHS

Supported initialization paths remain:

```text
v1 → v2 → v3 → v4 → v5 → v6

v2 → v3 → v4 → v5 → v6

v3 → v4 → v5 → v6

v4 → v5 → v6

v5 → v6
```

Current production expected entry:

```text
v5 → v6
```

---

# 52. v6 POST-MIGRATION VALIDATION

Before commit of migration transaction / as part of accepted migration gate:

```text
exact schema validation
immutable trigger restoration
PRAGMA foreign_keys=ON
foreign_key_check
quick_check
history validation
secret-history validation
```

must pass.

Any failure:

```text
settings_store_unavailable
```

and no partial v6 state is accepted.

---

# 53. STAGE-4 BREAK-GLASS COMPATIBILITY

Stage-4 Controller secret break-glass recovery MUST remain operational on v6.

The recovery opener remains:

```text
current-schema-aware
existing-only
non-creating
non-migrating
```

It must:

```text
require the accepted service-stopped boundary

preserve CAS / expected-generation semantics

clear only managed secret ownership

preserve General overrides
preserve Controller overrides
preserve Portal overrides
preserve Feature overrides
preserve Analytics overrides

preserve immutable audit/history/idempotency

preserve secure filesystem/key validation

never unnecessarily decrypt/print secret
```

Mandatory acceptance:

```text
schema v6
+
populated Analytics override generation
+
Stage-4 break-glass recovery
=
PASS
```

---

# 54. DOWNGRADE / ROLLBACK OF SCHEMA

Old v5 code operating directly against a v6 SettingsStore is:

```text
UNSUPPORTED
```

Before first production v6 migration:

```text
verified Settings DB backup required.
```

If source rollback to pre-Stage7 code is required after migration:

```text
stop owning service under approved rollback

restore exact pre-v6 Settings DB backup

restore accepted pre-Stage7 code/config

restart owning service

verify configured/effective state
```

No automatic v6 → v5 down-migration.

---

# 55. ANALYTICS DATA MIGRATION

```text
ANALYTICS DATA DB MIGRATION = NONE
```

Stage 7 MUST NOT alter schemas of:

```text
Observation DB
Visit DB
Visitor Registry DB
Traffic projection DB
Current State DB
```

No rebuild/backfill of historical Analytics source data.

---

# 56. API — PAGE

New Admin page:

```text
GET /admin/settings/analytics
```

No Site parameter.

No query parameters.

Page title:

```text
Analytics
```

It is GLOBAL installation-level Settings.

---

# 57. API — READ

Exact endpoint:

```text
GET /admin/api/v1/settings/analytics
```

API version:

```text
admin.settings.analytics.v1
```

Requires:

```text
admin.read.settings.analytics
```

No request body.

No query parameters.

Success includes ETag:

```text
"settings-g<N>"
```

Cache:

```text
no-store
```

via existing Admin boundary.

---

# 58. READ RESPONSE — TOP LEVEL

Exact shape:

```text
api_version:
    admin.settings.analytics.v1

request_id:
    UUID/request identity

scope:
    type = global

resource:
    type = analytics_product_thresholds
    scope = installation

store_state:
    available

configured_generation:
    integer

effective_generation:
    integer | null

etag:
    "settings-g<N>"

restart_required:
    boolean

pending_setting_count:
    integer 0..3

settings:
    exactly 3 ordered rows
```

Order:

```text
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
ANALYTICS_RSSI_THRESHOLD_DBM
ANALYTICS_SNR_THRESHOLD_DB
```

---

# 59. READ RESPONSE — SETTING ROW

Each row contains exactly the Stage-7 Settings metadata:

```text
key
display_label
description
group

value_type
public_value_type
presentation_type
unit

scope_type
scope_id

editable
secret_class

default_value

base_source
base_value

persisted_override_present
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

consumer_state

validation

last_changed_at
last_changed_by
```

`scope_id`:

```text
null
```

for all Stage-7 V1 settings.

---

# 60. VALIDATION JSON — QUALITY GAP

Exact read metadata:

```json
{
  "type": "integer",
  "nullable": false,
  "min": 1,
  "max": 3600,
  "unit": "seconds"
}
```

---

# 61. VALIDATION JSON — RSSI

Exact:

```json
{
  "type": "integer",
  "nullable": true,
  "min": -120,
  "max": -1,
  "unit": "dBm"
}
```

---

# 62. VALIDATION JSON — SNR

Exact:

```json
{
  "type": "integer",
  "nullable": true,
  "min": -100,
  "max": 100,
  "unit": "dB"
}
```

UI MUST consume server-provided validation metadata.

No independent JS bounds table.

---

# 63. API — MUTATION

Exact endpoint:

```text
POST /admin/api/v1/settings/analytics/generations
```

API version:

```text
admin.settings.analytics.mutation.v1
```

Maximum changes:

```text
3
```

Reuse existing ordinary Settings controls:

```text
authenticated Admin session
CSRF
If-Match
global generation CAS
UUIDv4 Idempotency-Key
strict JSON
atomic batch mutation
```

---

# 64. MUTATION BODY

Exact logical form:

```json
{
  "changes": [
    {
      "key": "ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS",
      "operation": "set",
      "value": 180
    },
    {
      "key": "ANALYTICS_RSSI_THRESHOLD_DBM",
      "operation": "set",
      "value": -70
    },
    {
      "key": "ANALYTICS_SNR_THRESHOLD_DB",
      "operation": "set",
      "value": null
    }
  ]
}
```

Reset:

```json
{
  "changes": [
    {
      "key": "ANALYTICS_RSSI_THRESHOLD_DBM",
      "operation": "clear_override"
    }
  ]
}
```

Unknown member/key/duplicate key/duplicate JSON member is rejected.

---

# 65. MUTATION SUCCESS RESPONSE

Exact fields:

```text
api_version =
admin.settings.analytics.mutation.v1

request_id

scope:
    type=global

resource:
    type=analytics_product_thresholds
    scope=installation

changed:
    boolean

changed_keys:
    ordered list

configured_generation

effective_generation

activation_state

restart_required
```

No full Settings projection is embedded in the mutation receipt.

The client performs a normal GET refresh when it needs refreshed projection.

---

# 66. MUTATION HTTP STATUS

```text
changed=true
→ 201

changed=false
→ 200
```

Idempotency replay returns:

```text
the exact stored successful response object
and its original successful HTTP status
```

Reuse of same idempotency identity with a different canonical mutation:

```text
409 idempotency_conflict
```

---

# 67. CAS

Required header:

```text
If-Match: "settings-g<N>"
```

Mismatch:

```text
412 stale_generation
```

Cross-domain write can make Analytics mutation stale.

No Analytics-specific generation counter.

---

# 68. ERROR MODEL

Reuse existing ordinary Settings error taxonomy.

At minimum:

```text
400 invalid_request

401 authentication_required

403 settings_forbidden

404 feature_disabled
    when Settings control plane itself is disabled

409 idempotency_conflict

412 stale_generation

422 validation_failed

503 settings_store_unavailable
```

No Analytics source probe is performed to decide mutation success.

---

# 69. AUTHORIZATION

Introduce recognized global capabilities:

```text
admin.read.settings.analytics
admin.write.settings.analytics
```

They are:

```text
recognized
but NOT default-granted
```

The existing default global grants remain unchanged.

Read page/API requires:

```text
admin.read.settings.analytics
```

Mutation requires BOTH:

```text
admin.read.settings.analytics
admin.write.settings.analytics
```

Write does not imply read.

---

# 70. CAPABILITY ACTIVATION

Capability grants remain deployment/startup configuration.

Stage 7 does not make capability grants managed Settings.

Changing production capability grant requires existing accepted lifecycle:

```text
deployment config change
→ captive-portal.service restart
→ new Admin login/session
```

No silent grant on schema/code upgrade.

---

# 71. SETTINGS NAVIGATION

Preserve existing accepted order and append Stage 7 without reordering existing tabs:

```text
General
→ Features
→ Controller
→ Portal
→ Analytics
```

`settings_nav_enabled` remains:

```text
principal has read capability for at least one visible Settings domain
```

`settings_nav_target` remains first authorized page in canonical order above.

Therefore an Analytics-only read principal gets:

```text
/admin/settings/analytics
```

No inaccessible General landing page.

---

# 72. UI INFORMATION ARCHITECTURE

Page:

```text
Settings
→ Analytics
```

Sections:

```text
Data quality

Wireless signal thresholds
```

Data quality contains:

```text
Observation gap threshold
```

Wireless contains:

```text
Default RSSI threshold
Default SNR threshold
```

Technical environment keys are secondary metadata, not primary labels.

---

# 73. UI EDITING MODEL

UI uses explicit local edit + Save.

No immediate network mutation on input change.

For every setting show as applicable:

```text
Configured value
Effective value
Configured source
Effective source
Pending restart
Consumer state
Reset
```

RSSI/SNR additionally expose:

```text
Not set
```

as a real managed value.

UI MUST distinguish:

```text
Not set
from
Reset to deployment/default
```

---

# 74. UI WARNINGS

Quality gap help text must state:

```text
Changing this setting can change the quality interpretation
of the same retained historical evidence after restart.
Stored source observations are not rewritten.
```

RSSI/SNR help must state:

```text
This is a default threshold.
An internal Analytics query that explicitly supplies a threshold
uses that query threshold instead.
```

No wording may imply:

```text
RSSI threshold = Wi-Fi quality classifier
SNR threshold = authorization policy
```

---

# 75. AUDIT

Stage-7 values are non-secret.

Ordinary immutable audit records:

```text
principal
source IP
request ID
idempotency identity
timestamp
key
operation
previous override
new override
previous configured value
new configured value
generation
```

Full admitted numeric value may appear in Settings mutation audit.

No raw Analytics observations are added to Settings audit.

---

# 76. LOGGING / PRIVACY

Stage-7 Settings logs may contain:

```text
setting key
generation
safe operation/result
```

They SHOULD NOT duplicate numeric policy values into general application logs unless required for a bounded diagnostic event.

No:

```text
MAC
device_id
raw RSSI history
raw SNR history
Visit data
Observation payload
```

is required by Stage-7 mutation telemetry.

---

# 77. RESET / RECOVERY

Normal operator recovery:

```text
clear_override
→ restart
→ lower-precedence source becomes active
```

or:

```text
set previous desired value
→ new generation
→ restart
```

Immutable Settings history is retained.

No "undo by deleting history".

---

# 78. FEATURE DISABLED / DORMANT UX

When `consumer_state=dormant_dependency_disabled`:

```text
configured value remains editable
effective value = null
pending status follows generation/adopted configuration truth
```

UI message:

```text
Saved configuration is retained, but no active Analytics consumer
currently uses this setting.
```

No automatic enabling of Analytics.

---

# 79. RUNTIME UNAVAILABLE UX

When:

```text
consumer_state=runtime_unavailable
```

UI MUST NOT claim that the configured threshold itself is invalid unless the Settings activation event actually failed for Stage-7 configuration.

Product-safe wording:

```text
The configuration is saved, but its runtime consumer is currently unavailable.
```

Operational source recovery is not a Settings mutation.

---

# 80. NO CACHE / MATERIALIZATION CHANGE

Stage 7 introduces:

```text
NO new cache
NO new result materialization
NO background recomputation
NO backfill
NO Analytics history rewrite
```

Existing read-time derived results simply use the adopted threshold for future requests.

---

# 81. STAGE-8 BOUNDARY — EXPLICIT OUT

Stage 7 does NOT admit:

```text
Current State polling/tuning

Observation collection/cadence

Visit Lifecycle worker behavior

Visitor Registry operational behavior

Pending Session Cleaner

retention policies

cleanup cadence

background-worker cadence

external request scheduling

Traffic ingestion operational behavior

Analytics operational enable flags

Analytics API security/exposure
```

These require Stage 8 or a dedicated architecture.

---

# 82. SITE SCOPE

Stage-7 V1 scope:

```text
GLOBAL only
```

No:

```text
Site selector
Site override
Site inheritance
Site-specific generation
```

Stage 7 does not pretend these policies are inherently Site-independent forever.

Future Site-specific override belongs to Stage 9 architecture.

A future Stage-9 implementation may add a higher-precedence Site layer without changing the meaning of these three canonical settings.

---

# 83. MULTI-SITE SAFETY

Current GLOBAL value applies consistently to all Sites that consume it.

No Site-specific value is inferred from:

```text
Home
default Site
SSID
AP
network
```

No hardcoded production Site.

---

# 84. NO LIVE ANALYTICS PROBE FROM SETTINGS

Settings GET/POST MUST NOT:

```text
query Observation DB

query Visit DB

run Wireless Analytics

run Historical Traffic

call Analytics API

test RSSI/SNR samples

probe Omada
```

Mutation success means:

```text
configuration accepted and durably saved
```

not:

```text
live Analytics result verified
```

---

# 85. COMPATIBILITY — EXISTING ANALYTICS API

Stage 7 keeps current internal Analytics API query semantics.

In particular:

```text
/wireless/signal threshold=<explicit value>
```

continues to override configured default for that single request.

Stage 7 does not change authentication/network/Site controls of that API.

---

# 86. COMPATIBILITY — EXISTING PRODUCT RESULTS

Existing source facts and historical ranges remain readable.

Stage 7 may add:

```text
quality_gap_threshold_seconds
```

as semantic provenance to Historical Traffic and Home AP-24H response models.

This is an additive semantic field.

No existing value is redefined except the intended future-query effect of using the newly adopted threshold.

---

# 87. COMPATIBILITY — CURRENT DEPLOYMENT VALUES

Before Stage-7 production migration/activation, deployment preflight MUST verify the selected current lower-precedence values for the three admitted keys satisfy the Stage-7 contract.

Expected repository defaults already satisfy:

```text
QUALITY GAP = 180

RSSI = null

SNR = null
```

If production has an explicit incompatible lower-precedence representation:

```text
ACTIVATION = HOLD
```

It must be reconciled explicitly.

No silent rounding/coercion.

---

# 88. IMMUTABLE SAFETY INVARIANTS

Stage 7 MUST NOT make operator-editable:

```text
max 2000 Analytics page/request limit

31-day base Analytics query ceiling

90-day Visit Analytics query ceiling

wireless query window safety

query deadline

Analytics API concurrency

Analytics API response size

wireless minimum statistical samples

Visit return-interval minimum statistical samples

counter gap acceptance

AP correlation join lag
```

These remain implementation/deployment safety/algorithm contracts.

---

# 89. ACCEPTANCE — ADMISSION

Mandatory:

```text
exact admitted count = 3

only:
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
ANALYTICS_RSSI_THRESHOLD_DBM
ANALYTICS_SNR_THRESHOLD_DB
```

No fourth Analytics config key may appear on Stage-7 page/API.

---

# 90. ACCEPTANCE — CLASSIFICATION

Tests/static review must prove:

```text
enable flags absent from Analytics Settings domain

query/resource controls absent

wireless min samples absent

counter gap absent

AP join lag absent

Visit cohort min absent

Visit max window absent

Analytics API security absent
```

---

# 91. ACCEPTANCE — RESOLUTION

For each admitted key:

```text
persisted override > explicit env > repository default
```

Required cases:

```text
no override + no env
→ repository default

env only
→ env

override + env
→ override

clear override
→ env/default

RSSI/SNR explicit null override + non-null env
→ effective configured value null
→ persisted_override_present=true
```

---

# 92. ACCEPTANCE — NUMERIC VALIDATION

Quality gap:

```text
1 → PASS
3600 → PASS
0 → FAIL
3601 → FAIL
float → FAIL
null → FAIL
bool → FAIL
```

RSSI:

```text
null → PASS
-120 → PASS
-1 → PASS
-121 → FAIL
0 → FAIL
float → FAIL
```

SNR:

```text
null → PASS
-100 → PASS
100 → PASS
-101 → FAIL
101 → FAIL
float → FAIL
```

---

# 93. ACCEPTANCE — THRESHOLD BOUNDARIES

Quality gap:

```text
gap == threshold
→ not over threshold

gap > threshold
→ over threshold
```

RSSI/SNR:

```text
sample == threshold
→ not below threshold

sample < threshold
→ below threshold
```

---

# 94. ACCEPTANCE — NULL SIGNAL POLICY

With configured RSSI/SNR:

```text
null
```

and no request override:

```text
distribution remains available

configured threshold = null
below-threshold count = null
below-threshold ratio = null
```

No Wireless Analytics disablement.

---

# 95. ACCEPTANCE — QUERY OVERRIDE

Configured RSSI:

```text
-70
```

query explicitly requests:

```text
threshold=-65
```

Result MUST use:

```text
-65
```

and expose `-65` as actual applied threshold.

Settings value remains:

```text
-70
```

No Settings mutation.

---

# 96. ACCEPTANCE — HISTORICAL REINTERPRETATION

Using identical retained source facts:

```text
generation G effective gap threshold = 180

then

generation G+1 effective gap threshold = 300
```

after required restart:

```text
future historical query may produce different gap/quality state
```

while proving:

```text
source DB bytes/rows not rewritten by Stage-7 mutation/adoption
```

Result must expose:

```text
quality_gap_threshold_seconds = 300
```

---

# 97. ACCEPTANCE — SINGLE RUNTIME POLICY

When Settings enabled:

```text
one ResolvedSettingsSnapshot(G)

→ one AnalyticsProductThresholdsV1(G)
```

The same policy must feed:

```text
AnalyticsConfig
HistoricalTrafficReadService
AnalyticsReadService
WirelessAnalyticsService
VisitAnalyticsService
HomeAp24ReadService
```

No independent request-time env/SettingsStore read for the three admitted keys.

---

# 98. ACCEPTANCE — DORMANT PREFERENCE

Example:

```text
RSSI override = -70
Wireless Analytics disabled
```

Must be valid.

Expected:

```text
configured_value=-70
consumer_state=dormant_dependency_disabled
effective_value=null
override retained
generation may adopt successfully
```

After future authorized Wireless Analytics enable + restart:

```text
same retained configured preference becomes active
without automatic rewrite.
```

---

# 99. ACCEPTANCE — STAGE-6 INDEPENDENCE

Turning a Stage-6 product feature OFF MUST NOT mutate:

```text
Analytics threshold overrides
```

Turning it ON MUST NOT create an Analytics Settings generation.

No cascade writes in either direction.

---

# 100. ACCEPTANCE — ACTIVATION FAILURE

Inject mismatch between:

```text
resolved generation policy
and
consumer-composed policy
```

Expected:

```text
analytics_configuration_adoption_failed

effective generation does not advance

no partial Stage-7 activation
```

---

# 101. ACCEPTANCE — OPERATIONAL FAILURE ISOLATION

Inject after valid adoption:

```text
Observation DB unavailable

Visit DB unavailable

Analytics source unavailable

query deadline
```

Expected:

```text
no new Settings activation failure

effective generation remains adopted

runtime/product returns its existing unavailable/degraded semantics
```

Guest Portal/Auth unaffected.

---

# 102. ACCEPTANCE — API

Required:

```text
GET /admin/settings/analytics
→ authorized page

GET /admin/api/v1/settings/analytics
→ admin.settings.analytics.v1

POST /admin/api/v1/settings/analytics/generations
→ admin.settings.analytics.mutation.v1

read-only principal
→ GET allowed
→ POST forbidden

write without read
→ no usable mutation path

If-Match stale
→ 412

idempotency conflict
→ 409

changed
→ 201

no-op
→ 200
```

---

# 103. ACCEPTANCE — NAVIGATION

Canonical tab order:

```text
General
Features
Controller
Portal
Analytics
```

Analytics-only read principal:

```text
Settings nav exists

target =
/admin/settings/analytics
```

No empty/inaccessible landing page.

---

# 104. ACCEPTANCE — SCHEMA v6

Mandatory fixtures:

```text
v1 → v6
v2 → v6
v3 → v6
v4 → v6
v5 → v6
```

Verify:

```text
generation identity preserved
effective target preserved
all existing domain overrides preserved
feature overrides preserved
secret state preserved
audit preserved
idempotency preserved
triggers restored
foreign_key_check PASS
quick_check PASS
```

No migration-created Analytics override.

---

# 105. ACCEPTANCE — BREAK-GLASS

Populate v6 DB with:

```text
Analytics overrides
Portal overrides
Feature overrides
Controller secret managed binding
ordinary history
```

Run accepted Stage-4 recovery semantics.

Must prove:

```text
only managed secret ownership cleared

Analytics overrides preserved exactly

CAS preserved

history immutable

no secret read-back

recovery remains existing-only/non-migrating
```

---

# 106. ACCEPTANCE — RESET

RSSI example:

```text
env=-75
persisted override=-70
```

Reset:

```text
clear_override
```

After restart:

```text
configured/effective=-75
source=environment
```

Setting `null` instead:

```text
configured/effective=null
source=persisted_override
```

These MUST NOT be conflated.

---

# 107. ACCEPTANCE — SECRET ISOLATION

Analytics Settings GET/POST must work without:

```text
master key read
secret decrypt
secret repository availability
```

provided common SettingsStore itself is available.

No secret appears in request/response/audit/log.

---

# 108. ACCEPTANCE — NO OPERATIONAL MODULE MUTATION

Stage-7 code path MUST NOT mutate:

```text
ANALYTICS_FOUNDATION_ENABLED

ANALYTICS_WIRELESS_ENABLED

ANALYTICS_VISIT_ENABLED

Current State flags

Observation flags

Visit Lifecycle flags

Traffic ingestion flags
```

No worker/service start/stop.

---

# 109. ACCEPTANCE — NO NEW ANALYTICS DATA STORE

Prove:

```text
new Analytics Settings DB = NO

new threshold-history DB = NO

new derived-result cache = NO

historical data rewrite = NO

background threshold recompute = NO
```

---

# 110. ACCEPTANCE — UI

Required:

```text
exact 3 controls

two groups only

numeric input semantics

RSSI/SNR explicit "Not set"

Reset distinct from Not set

configured/effective/source shown

pending restart shown

consumer state shown

explicit Save

no restart button

no feature enable switch

no internal safety-control fields
```

---

# 111. NON-GOALS

Stage 7 does NOT implement:

```text
Site-scoped Analytics settings

Analytics operational lifecycle management

Analytics API security Settings

query deadline editing

page limit editing

max query window editing

wireless min-sample editing

Visit cohort editing

counter-gap editing

AP join-lag editing

retention controls

background-worker cadence

Traffic ingestion controls

new Wi-Fi quality classifier

new analytics cache

historical result materialization

live Test Analytics button

systemd controls
```

---

# 112. ARCHITECTURE QUESTIONS / RESEARCH

Current source evidence is sufficient for Stage-7 V1 admission.

No live-network or production-data research is required to decide the three admitted settings.

Therefore:

```text
OPEN_ARCHITECTURE_RESEARCH = NONE
```

Production preflight remains required later to verify exact lower-precedence deployment values before v6 activation.

That is deployment verification, not an Architecture Research blocker.

---

# 113. CODER OWNERSHIP BOUNDARY — FUTURE IMPLEMENTATION ONLY

After Architecture PASS and a separate Implementation Contract, implementation may touch the bounded conceptual areas:

```text
app/analytics/config.py
→ canonical Stage-7 threshold semantics/runtime projection

app/settings_control/*
→ 3 definitions
→ analytics domain
→ validation/read/mutation
→ schema v6
→ recovery compatibility
→ adoption attestation

run.py / runtime composition
→ single adopted threshold policy injection

app/analytics/*
→ consume one adopted policy
→ expose actual quality threshold provenance where required

app/admin_web/*
→ Settings Analytics page/API/navigation/UI
```

No implementation authorization is granted by this Architecture Contract.

---

# 114. FORBIDDEN SCOPE EXPANSION

Future Coder MUST STOP and return if implementation appears to require:

```text
new Analytics DB

new worker/service

new Site override system

new permission model outside two Analytics Settings capabilities

changing Analytics API authentication

changing Analytics API allowed networks

changing Observation collection

changing Visit Lifecycle

changing Current State cadence

changing Traffic Projection lifecycle

changing query hard ceilings

changing min-sample statistical contracts

changing counter/join semantics

new Wi-Fi quality classifier
```

---

# 115. ARCHITECTURE INVARIANTS

```text
S7-I01
Stage 7 admits exactly 3 Analytics settings.

S7-I02
Settings is not an AnalyticsConfig dump.

S7-I03
Resource/query safety controls remain internal.

S7-I04
Operational Analytics enable flags remain Stage 8 / deployment-owned.

S7-I05
RSSI/SNR settings are defaults, not mandatory per-query overrides.

S7-I06
RSSI and SNR remain independent.

S7-I07
Stage 7 creates no Wi-Fi quality classifier.

S7-I08
Quality gap is a read-time evidence-quality policy.

S7-I09
Quality gap equality is not a gap violation.

S7-I10
Signal equality is not below threshold.

S7-I11
RSSI/SNR null disables only configured-default threshold ratio semantics.

S7-I12
Reset is clear_override.

S7-I13
Explicit nullable override is distinct from Reset.

S7-I14
Scope is GLOBAL only.

S7-I15
Stage 7 uses the common global Settings generation/ETag.

S7-I16
Activation requires captive-portal.service restart.

S7-I17
No hot reload or Admin systemd authority exists.

S7-I18
Dormant preferences are retained.

S7-I19
Stage-6 feature disablement does not rewrite Stage-7 settings.

S7-I20
Stage-7 mutation does not enable/disable Analytics modules.

S7-I21
No threshold-sensitive historical source row is rewritten.

S7-I22
Future reads use the currently adopted threshold policy.

S7-I23
Threshold-sensitive result exposes the actual applied threshold.

S7-I24
No separate config-generation marker is required while results remain read-time only.

S7-I25
If threshold-derived results become durable later, provenance must be redesigned first.

S7-I26
Stage 7 introduces schema v6 only for Settings domain admission.

S7-I27
No Analytics source DB migration occurs.

S7-I28
Stage-4 break-glass remains compatible with v6.

S7-I29
Analytics Settings are secret-isolated.

S7-I30
Operational source outage is not Settings activation failure.

S7-I31
One startup Stage-7 policy feeds every admitted consumer.

S7-I32
No request-time SettingsStore/env reread for admitted values.

S7-I33
New Analytics capabilities are recognized but not default-granted.

S7-I34
Analytics-only reader has a valid Settings navigation target.

S7-I35
Coder receives no authority to reclassify excluded Analytics parameters.
```

---

# 116. FINAL ADMISSION VERDICT

```text
STAGE =
7

TITLE =
ANALYTICS / PRODUCT THRESHOLDS

BASELINE =
main@51deead342bd821b5c46fb75a7ceef37bef63e7c

TREE =
7b6cfa20c23c097e87059ca12a593f697f0a36a2

BASELINE_MOVED =
NO

CURRENT_SETTINGS_SCHEMA =
v5

TARGET_SETTINGS_SCHEMA =
v6

ADMITTED_DOMAIN =
analytics

ADMITTED_KEY_COUNT =
3

ADMITTED =
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
ANALYTICS_RSSI_THRESHOLD_DBM
ANALYTICS_SNR_THRESHOLD_DB

ANALYTICS_ENABLE_FLAGS =
NOT STAGE 7
→ STAGE 8 / OPERATIONAL MODULE SETTINGS

QUERY_SAFETY_CONTROLS =
INTERNAL-ONLY

STATISTICAL MIN-SAMPLE CONTROLS =
INTERNAL-ONLY

COUNTER/JOIN TUNING =
INTERNAL-ONLY

SCOPE =
GLOBAL

SETTINGS STORE =
REUSE EXISTING

GENERATION MODEL =
COMMON GLOBAL

ETAG =
COMMON settings-gN

PRECEDENCE =
persisted override
>
explicit environment
>
repository default

ACTIVATION =
captive-portal.service restart

HOT RELOAD =
NO

ANALYTICS DATA MIGRATION =
NONE

HISTORICAL SOURCE REWRITE =
NO

RESULT POLICY =
READ-TIME CURRENT ADOPTED THRESHOLD

NEW CAPABILITIES =
admin.read.settings.analytics
admin.write.settings.analytics

DEFAULT GRANT =
NO

STAGE-4 SECRET DEPENDENCY =
NO

OPEN_P0 =
0

OPEN_P1 =
0

OPEN_P2 =
0
```

---

# 117. GOVERNANCE DISPOSITION

```text
ARCHITECTURE_ADMISSION =
COMPLETE

ARCHITECTURE_STATUS =
DRAFT FOR TECH LEAD REVIEW

READY_FOR_TECH_LEAD_ARCHITECTURE_REVIEW =
YES

READY_FOR_IMPLEMENTATION_TASK =
NO — UNTIL TECH LEAD ARCHITECTURE PASS

IMPLEMENTATION_AUTHORIZATION =
NO

CODER =
HOLD

SOURCE_CHANGES =
NO

PRODUCTION_CHANGES =
NO
```

Next exact governance step:

```text
Architect
→ Stage-7 Architecture Contract v0.1

Tech Lead
→ architecture source review

if PASS:

Technical Developer Settings
→ exact Stage-7 implementation TASK

Tech Lead
→ implementation-contract review

then and only then:
Coder workflow may be authorized.
```
