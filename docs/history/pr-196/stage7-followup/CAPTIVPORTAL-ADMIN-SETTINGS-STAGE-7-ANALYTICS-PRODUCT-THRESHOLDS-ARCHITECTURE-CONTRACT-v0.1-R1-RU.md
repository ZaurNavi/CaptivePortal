# CAPTIVPORTAL ADMIN SETTINGS
## STAGE 7 — ANALYTICS / PRODUCT THRESHOLDS
### ARCHITECTURE CONTRACT v0.1-R1
### BOUNDED ARCHITECTURE REPAIR ADDENDUM
### P1-S7-01 — HOME AP-24H DUAL GAP SEMANTICS / PROVENANCE
### FOR TECH LEAD RE-REVIEW

**Проект:** CaptivPortal  
**Роль:** Architect  
**Baseline:** `main@51deead342bd821b5c46fb75a7ceef37bef63e7c`  
**TREE:** `7b6cfa20c23c097e87059ca12a593f697f0a36a2`  
**Production:** тот же exact HEAD/TREE — подтверждено Owner / Tech Lead  
**Parent artifact:** `CAPTIVPORTAL ADMIN SETTINGS — STAGE 7 — ANALYTICS / PRODUCT THRESHOLDS — ARCHITECTURE CONTRACT v0.1`  
**R1 scope:** `P1-S7-01 only`  
**Coder:** `HOLD`  
**Implementation TASK:** `HOLD`  
**Source changes:** `NO`  
**Production changes:** `NO`

---

# 0. PRECEDENCE / NON-REOPEN RULE

Этот документ является нормативным bounded addendum к `ARCHITECTURE CONTRACT v0.1`.

При конфликте:

```text
v0.1-R1
>
v0.1
```

Все положения v0.1, не изменённые ниже, остаются в силе.

R1 НЕ переоткрывает:

```text
Stage-7 admitted key count = 3
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS = ADMITTED
ANALYTICS_RSSI_THRESHOLD_DBM = ADMITTED
ANALYTICS_SNR_THRESHOLD_DB = ADMITTED
Settings schema v6
common global Settings generation
common ETag / CAS / idempotency
RSSI/SNR null-vs-reset semantics
restart-based activation
Analytics Settings capabilities
secret isolation
Stage-8 operational boundary
GLOBAL scope
RSSI/SNR explicit request override semantics
```

---

# 1. SOURCE-VERIFIED CURRENT HOME AP-24H SEMANTICS

Current source на reviewed baseline подтверждает:

```text
HomeAp24ReadService(
    current_state_ap_interval_seconds,
    quality_gap_seconds,
    ...
)
```

и exact composition:

```text
observation_gap_threshold_seconds
=
quality_gap_seconds
```

```text
current_state_gap_threshold_seconds
=
max(
    3 * current_state_ap_interval_seconds,
    quality_gap_seconds
)
```

Следовательно:

```text
managed Analytics quality-gap value
!=
necessarily the exact effective gap threshold
for every Home AP-24H branch
```

Parent v0.1 wording, которое трактовало один `quality_gap_threshold_seconds` как один универсальный actual Home AP-24H threshold, заменяется этим R1.

---

# 2. ARCHITECTURE DECISION — OPTION A

Stage 7 выбирает:

```text
OPTION A
```

`ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS` является:

```text
MANAGED BASE ANALYTICAL GAP POLICY INPUT
```

а НЕ гарантированно точным финальным gap threshold каждого consumer.

Exact rule:

```text
a consumer MAY apply an explicitly frozen consumer-specific operational floor
before obtaining its effective gap threshold.
```

Home AP-24H current cadence-derived floor является таким accepted consumer-specific rule.

---

# 3. STAGE-7 MANAGED QUALITY-GAP SEMANTICS

Canonical setting остаётся:

```text
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
```

Его Stage-7 product meaning заменяется на:

```text
Base gap-tolerance policy used by Analytics consumers when deciding whether
retained analytical evidence remains sufficiently continuous.

A consumer with an accepted operational cadence dependency may apply a larger
consumer-specific effective gap threshold derived from that cadence.

The managed value therefore defines the base policy input, not a universal
promise that every consumer uses exactly the same numeric threshold.
```

Не меняются:

```text
range = 1..3600 seconds inclusive
scope = GLOBAL
secret = normal
activation = captive-portal.service restart
common Settings generation = YES
```

---

# 4. HOME AP-24H — EXACT DUAL-BRANCH FORMULA

Для adopted Stage-7 policy:

```text
M = AnalyticsProductThresholdsV1.quality_gap_threshold_seconds
```

Для Home AP-24H startup composition:

```text
I = current_state_ap_interval_seconds
```

Exact effective thresholds:

```text
observation_gap_threshold_seconds = M
```

```text
current_state_cadence_floor_seconds = 3 * I
```

```text
current_state_gap_threshold_seconds = max(M, current_state_cadence_floor_seconds)
```

No rounding.

Exact multiplier:

```text
3
```

No Site-specific adjustment.

No UI-selected multiplier.

---

# 5. SEMANTIC CONSEQUENCE

Managed value всегда является exact Home AP-24H Observation gap threshold.

Для Current State branch он является только одним входом.

```text
M < 3*I
→ Observation uses M
→ Current State uses 3*I

M = 3*I
→ both branches use M

M > 3*I
→ both branches use M
```

Это intentional behavior.

---

# 6. CURRENT STATE CADENCE OWNERSHIP

Stage 7 НЕ получает ownership над:

```text
CURRENT_STATE_AP_INTERVAL_SECONDS
runtime key: current_state_ap_interval_seconds
```

Этот параметр остаётся:

```text
Operational Module Settings / Stage 8 boundary
```

Stage 7 MUST NOT:

```text
register it as Analytics Settings
show it as editable under Settings → Analytics
mutate it
reset it
create a Stage-7 override for it
change Current State polling cadence
```

Но Home AP-24H является cross-domain consumer, поэтому его effective gap semantics legitimately depends on both:

```text
Stage-7 managed policy M
+
existing operational Current State cadence I
```

Эта зависимость должна быть explicit в runtime composition и result provenance.

---

# 7. SINGLE-STARTUP COMPOSITION — CLARIFICATION

Parent Stage-7 invariant остаётся:

```text
one ResolvedSettingsSnapshot(G)
→ one AnalyticsProductThresholdsV1(G)
```

Home AP-24H получает тот же adopted policy для `M`.

Отдельно Home AP-24H получает существующее startup-resolved operational value `I`.

Derived values вычисляются один раз при composition:

```text
obs_gap = M
cs_floor = 3 * I
cs_gap = max(M, cs_floor)
```

No request-time SettingsStore read.

No request-time env read.

Для lifetime одной composed Home AP-24H service instance:

```text
M
I
obs_gap
cs_floor
cs_gap
```

immutable.

---

# 8. STAGE-7 ADOPTION OWNERSHIP

Stage-7 adoption attests:

```text
M
+
correct injection of M into Home AP-24H composition
```

Stage 7 не берёт ownership над lifecycle/validity `I` beyond существующей Home AP-24H composition requirement.

Если managed Stage-7 policy invalid/mismatched:

```text
analytics_configuration_adoption_failed
```

Если managed `M` valid, но operational `I` invalid и поэтому Home AP-24H не композируется:

```text
Home AP-24H / operational composition failure
```

и это MUST NOT быть автоматически переименовано в:

```text
analytics_configuration_adoption_failed
```

только потому, что `M` участвует в формуле.

---

# 9. HOME AP-24H PROVENANCE — EXACT RESPONSE CONTRACT

Parent requirement одного Home AP-24H поля:

```text
quality_gap_threshold_seconds
```

как универсального actual threshold заменяется.

Home AP-24H MUST expose один top-level provenance object:

```text
quality_gap_policy
```

Exact fields:

```text
quality_gap_policy:
    managed_threshold_seconds
    observation_effective_threshold_seconds
    current_state_ap_interval_seconds
    current_state_cadence_floor_seconds
    current_state_effective_threshold_seconds
```

Все значения:

```text
integer
non-null
seconds
```

Exact mapping:

```text
managed_threshold_seconds = M

observation_effective_threshold_seconds = M

current_state_ap_interval_seconds = I

current_state_cadence_floor_seconds = 3 * I

current_state_effective_threshold_seconds = max(M, 3 * I)
```

Это минимальный authoritative Home AP-24H Stage-7 gap provenance contract.

---

# 10. WHY ALL FIVE FIELDS ARE REQUIRED

Они различают:

```text
managed product policy
operational cadence input
derived cadence floor
actual Observation effective threshold
actual Current State effective threshold
```

Тем самым response не создаёт ложное впечатление:

```text
one Stage-7 value = all Home AP-24H gap thresholds
```

---

# 11. HOME AP-24H CONTRACT VERSION

Поскольку response получает explicit semantic provenance и прежняя single-threshold interpretation больше недостаточна, Home AP-24H contract version MUST advance:

```text
admin.home_ap_24h.v1
→
admin.home_ap_24h.v2
```

Endpoint path остаётся прежним.

`v2` сохраняет existing Home AP-24H data semantics и добавляет только `quality_gap_policy` плюс semantics этого R1.

No unrelated Home AP-24H redesign is admitted.

---

# 12. HISTORICAL / READ-TIME SEMANTICS — REPAIR

При stable operational cadence `I`:

```text
Observation branch
→ always follows M exactly
```

```text
Current State branch
→ follows max(M, 3*I)
```

Поэтому изменение `M` может:

```text
change both branches
```

или:

```text
change only Observation branch,
while Current State remains cadence-floor bound
```

Stored source facts remain unchanged.

No historical source row rewrite.

Effects apply to future read-time interpretation after restart/adoption.

---

# 13. HISTORICAL RESULT PROVENANCE — REPAIR

## Historical Traffic

Если consumer использует managed gap напрямую:

```text
quality_gap_threshold_seconds
=
actual applied threshold
```

No change.

## Existing Analytics / Visit coverage DTOs

Existing exact applied-threshold provenance remains authoritative.

No change.

## Home AP-24H

MUST NOT expose one ambiguous threshold as universal.

Authoritative Stage-7 provenance is exactly:

```text
quality_gap_policy
```

as defined in this R1.

---

# 14. OPERATOR-FACING LABEL — REPLACEMENT

For:

```text
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
```

Stage-7 Settings display label becomes:

```text
Base analytics gap threshold
```

Parent label `Observation gap threshold` is superseded.

---

# 15. OPERATOR-FACING DESCRIPTION — REPLACEMENT

Exact description:

```text
Base gap tolerance used by Analytics when deciding whether retained evidence
is continuous enough for analytical interpretation.

Most consumers use this value directly.

Home AP-24H uses it directly for Observation evidence, while its Current State
branch may use a larger effective gap threshold based on the Current State AP
polling interval.

The Current State polling interval is operational configuration and is not
editable on this page.
```

---

# 16. SETTINGS UI HELP TEXT — REPLACEMENT

Settings → Analytics MUST show:

```text
This value is the managed base Analytics gap policy.

Changing it can change the interpretation of the same retained historical
evidence after restart.

Some consumers may apply an additional operational cadence floor.
Home AP-24H Current State uses the larger of this value and three times the
Current State AP polling interval.

Stored source observations are not rewritten.
```

Settings page MUST NOT show Current State interval as an editable Stage-7 setting.

Settings read MUST NOT perform a live Home AP-24H query merely to show derived effective thresholds.

---

# 17. NO STAGE-7 CROSS-VALIDATION AGAINST CURRENT STATE CADENCE

Parent Stage-7 rule remains:

```text
no Stage-7 cross-setting validation against Current State cadence
```

Specifically, valid:

```text
M < 3 * I
```

MUST NOT be rejected.

No requirement:

```text
M >= 3*I
```

or:

```text
M <= 3*I
```

is introduced.

---

# 18. DORMANT / DISABLED CONSUMER SEMANTICS

If Home AP-24H is disabled:

```text
managed M remains stored
no Home AP-24H derived thresholds are required to exist
Settings GET/POST performs no Current State cadence probe
no cross-domain mutation occurs
```

When later enabled + restarted:

```text
M + startup I
→ exact Home AP-24H derived thresholds
```

No Settings rewrite required.

---

# 19. STAGE-6 FEATURE CONTROLS

No change to Stage-6 ownership.

No Stage-6 feature mutation rewrites `M`.

No Stage-7 mutation enables/disables Home AP-24H.

---

# 20. HOME AP-24H CURRENT-STATE FRESHNESS — EXPLICIT NON-GOAL

Home AP-24H also has separate Current State freshness behavior based on Current State cadence.

This R1 freezes only:

```text
gap / continuity threshold semantics
```

It does NOT transfer all Current State freshness rules into Stage 7.

Operational cadence/freshness remains outside Stage 7.

---

# 21. MANDATORY ACCEPTANCE — CASE 1

Input:

```text
current_state_ap_interval_seconds = 60
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS = 60
```

Expected:

```text
M = 60
I = 60
observation_gap_threshold_seconds = 60
current_state_cadence_floor_seconds = 180
current_state_gap_threshold_seconds = 180
```

Expected Home AP-24H v2 provenance:

```json
{
  "quality_gap_policy": {
    "managed_threshold_seconds": 60,
    "observation_effective_threshold_seconds": 60,
    "current_state_ap_interval_seconds": 60,
    "current_state_cadence_floor_seconds": 180,
    "current_state_effective_threshold_seconds": 180
  }
}
```

Required proof:

```text
Observation branch uses 60
Current State branch uses 180
response does not claim 60 is universal effective threshold
```

---

# 22. MANDATORY ACCEPTANCE — CASE 2

Input:

```text
current_state_ap_interval_seconds = 60
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS = 300
```

Expected:

```text
M = 300
I = 60
observation_gap_threshold_seconds = 300
current_state_cadence_floor_seconds = 180
current_state_gap_threshold_seconds = 300
```

Expected Home AP-24H v2 provenance:

```json
{
  "quality_gap_policy": {
    "managed_threshold_seconds": 300,
    "observation_effective_threshold_seconds": 300,
    "current_state_ap_interval_seconds": 60,
    "current_state_cadence_floor_seconds": 180,
    "current_state_effective_threshold_seconds": 300
  }
}
```

Required proof:

```text
Observation branch uses 300
Current State branch uses 300
managed policy dominates cadence floor
```

---

# 23. MANDATORY ACCEPTANCE — FLOOR INDEPENDENCE

With:

```text
I = 60
M1 = 60
M2 = 120
```

Expected:

```text
Observation effective threshold:
60 → 120

Current State effective threshold:
180 → 180
```

This proves a Stage-7 policy change may alter one Home AP-24H branch without altering the other.

No source-data rewrite.

---

# 24. MANDATORY ACCEPTANCE — NO OWNERSHIP LEAK

Prove:

```text
Settings → Analytics
does NOT register CURRENT_STATE_AP_INTERVAL_SECONDS
```

```text
Analytics mutation
DOES NOT write Current State configuration
```

```text
Home AP-24H derives Current State gap only from existing startup-resolved Current State interval
```

---

# 25. MANDATORY ACCEPTANCE — SINGLE STARTUP VALUES

For one running `captive-portal.service` instance:

```text
M
I
obs_gap
cs_floor
cs_gap
```

remain stable.

Stage-7 Settings mutation without restart:

```text
configured generation may change
running M does not change
running obs_gap does not change
running cs_gap does not change
```

After accepted restart/adoption all are recomposed.

---

# 26. MANDATORY ACCEPTANCE — ADOPTION FAILURE BOUNDARY

Case:

```text
managed Stage-7 M invalid/mismatched during adoption
```

Expected:

```text
analytics_configuration_adoption_failed
```

Case:

```text
managed M valid
but operational Current State interval I invalid
and Home AP-24H composition fails
```

Expected:

```text
Home AP-24H / operational composition failure
```

NOT automatically:

```text
analytics_configuration_adoption_failed
```

---

# 27. R1 REPLACEMENT SUMMARY

Normatively amended parent-v0.1 areas:

```text
QUALITY GAP operator-facing meaning
QUALITY GAP label/help text
Home AP-24H quality-gap semantics
Home AP-24H result provenance
Home AP-24H contract version
historical/read-time interpretation wording
threshold-sensitive result provenance wording
```

All other Stage-7 decisions remain unchanged.

---

# 28. R1 INVARIANTS

```text
S7-R1-I01
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS is a managed base policy input.

S7-R1-I02
It is not guaranteed to be the exact final threshold of every consumer.

S7-R1-I03
Home AP-24H Observation uses the managed value exactly.

S7-R1-I04
Home AP-24H Current State uses max(managed value, 3 × Current State AP interval).

S7-R1-I05
Current State AP interval remains Stage-8 operational configuration.

S7-R1-I06
Stage 7 does not cross-validate managed gap against Current State cadence.

S7-R1-I07
A managed value below the Current State cadence floor is valid.

S7-R1-I08
Home AP-24H exposes managed, operational-input, derived-floor and effective per-branch provenance.

S7-R1-I09
One ambiguous Home AP-24H quality_gap_threshold_seconds field is insufficient.

S7-R1-I10
Home AP-24H response contract advances to admin.home_ap_24h.v2.

S7-R1-I11
No Home AP-24H source facts are rewritten when M changes.

S7-R1-I12
No Current State cadence ownership moves into Stage 7.

S7-R1-I13
No Stage-7 mutation changes Current State polling.

S7-R1-I14
Operational Current State configuration failure is not misclassified as a Stage-7 managed-policy adoption failure.

S7-R1-I15
The Stage-7 admitted key count remains exactly 3.
```

---

# 29. P1-S7-01 DISPOSITION

```text
P1-S7-01 = RESOLVED
```

---

# 30. FINAL R1 STATUS

```text
TASK =
CAPTIVPORTAL ADMIN SETTINGS
STAGE 7 — ANALYTICS / PRODUCT THRESHOLDS

ARCHITECTURE CONTRACT =
v0.1-R1

BASELINE =
main@51deead342bd821b5c46fb75a7ceef37bef63e7c

TREE =
7b6cfa20c23c097e87059ca12a593f697f0a36a2

P1-S7-01 =
RESOLVED

OPEN_P0 =
0

OPEN_P1 =
0

OPEN_P2 =
0

READY_FOR_TECH_LEAD_ARCHITECTURE_REVIEW =
YES

READY_FOR_IMPLEMENTATION_TASK =
NO — UNTIL TECH LEAD ARCHITECTURE PASS

IMPLEMENTATION_AUTHORIZATION =
NO

CODER =
HOLD

IMPLEMENTATION TASK =
HOLD

SOURCE CHANGES =
NO

PRODUCTION CHANGES =
NO
```

---

# 31. NEXT GOVERNANCE STEP

```text
Architect
→ Stage-7 Architecture Contract v0.1-R1

Tech Lead
→ bounded architecture re-review

if PASS:

Technical Developer Settings
→ exact Stage-7 implementation TASK

Tech Lead
→ implementation-contract review

then and only then:

Coder workflow may be authorized.
```
