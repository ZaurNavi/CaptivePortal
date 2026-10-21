# TASK-DTI-NI-G5
## TEMPORAL ATTRIBUTION AUTHORITY ADMISSION
### ТОЧНЫЙ BOUNDED RESEARCH / SYSADMIN / QA CONTRACT
### FINAL CANDIDATE FOR TECH LEAD REVIEW

**Проект:** CaptivPortal  
**Программа:** DTI — Network Intelligence  
**Gate:** `NI-G5 — Temporal Attribution Authority`  
**Следующий implementation stage после PASS:** `TASK-DTI-NI-02`  
**Роль:** Architect  
**Статус:** `FINAL CANDIDATE FOR TECH LEAD REVIEW`

---

# 0. AUTHORITATIVE BASELINE

Текущий repository / production baseline:

```text
HEAD =
dfd3178b2cd2a3c52387402ea18600d23b052bc4

TREE =
c418bab3d5e1a270d8b6f12b60b5f1d7d5de8e80
```

Upstream production state:

```text
TASK-DTI-NI-01 =
CLOSED / PRODUCTION ACCEPTED

network-metadata.service =
active + enabled

isolated Suricata DTI EVE =
permanent

DNS/TLS/QUIC live ingest =
PASS

source generation/checkpoint/replay =
PASS

rename/reopen rotation =
PASS

configured SQLite target =
48 GiB

architecture hard max =
64 GiB

source health = usable
ingest health = usable
capture health = usable
faults = 0

Fingerprint regression = NO
CaptivPortal regression = NO
```

---

# 1. ARCHITECT DECISION

Текущих принятых evidence НЕДОСТАТОЧНО, чтобы честно заморозить:

```text
Site + IPv4 + event_at
→ Site + MAC
```

как production-authoritative temporal attribution.

Следовательно выбран expected output:

```text
OPTION B
```

То есть сейчас выпускается:

```text
TASK-DTI-NI-G5
TEMPORAL ATTRIBUTION AUTHORITY ADMISSION
```

а НЕ `TASK-DTI-NI-02 implementation contract`.

Текущий gate:

```text
IPV4 TEMPORAL ATTRIBUTION AUTHORITY =
NOT YET ADMITTED

TASK-DTI-NI-02 = HOLD
CODER = HOLD
PRODUCTION NI-02 CHANGE = NO
```

---

# 2. ПОЧЕМУ CURRENT EVIDENCE НЕДОСТАТОЧНО

Source review current baseline подтверждает пять разных evidence domains, но ни один сейчас не даёт уже замороженный полный event-time lease interval.

## 2.1 Current State

`current_client_state` хранит point-in-time facts:

```text
site_id
observed_at
client_mac
ip
```

Current State может доказать:

```text
в конкретном accepted snapshot/cycle
этот MAC был виден с этим IP
```

Но не определяет:

```text
valid_from
valid_until
lease expiry
authoritative reassignment boundary
```

Итог:

```text
Current State =
POINT-IN-TIME SUPPORTING EVIDENCE
```

## 2.2 Historical Observation

`client_observations` хранит:

```text
site_id
observed_at
client_mac
ip
source_inventory_complete
```

Это historical point evidence, но не lease authority.

Нельзя считать весь промежуток между двумя rows одним IP ownership interval без отдельного доказанного правила.

## 2.3 Visitor Registry

Registry имеет:

```text
visitor_devices.device_id
visitor_devices.mac UNIQUE
```

и snapshots с:

```text
device_id
site_id
requested_mac
authorized_at
captured_at
portal_client_ip
ip
```

Отсюда уже фиксируется вторая часть будущей цепочки:

```text
Site + MAC
→ existing device_id where authoritative
```

Canonical device identity owner:

```text
Visitor Registry
```

Но Registry `last_ip` и snapshot IP не являются temporal lease authority.

## 2.4 Visit Lifecycle

Visit хранит:

```text
site_id
client_mac
device_id nullable
started_at
closed_at
start_ip
final_ip
```

а authorization/offline evidence содержит дополнительные point IP facts.

Нельзя предполагать:

```text
visit.started_at .. visit.closed_at
=
IP ownership interval
```

Visit Lifecycle остаётся owner Visit semantics, не DHCP lease semantics.

## 2.5 Device Fingerprint / DHCP

Existing Fingerprint capture path реально видит DHCP traffic.

Текущий DHCP parser получает в runtime минимум:

```text
client MAC
transaction ID
yiaddr
requested IP
server identifier
lease_seconds
ACK / OFFER / NAK
```

`DhcpScopeResolver` поддерживает bounded in-memory lease proof.

Но current persisted Fingerprint evidence не хранит полный durable DHCP lease lifecycle с lease-expiry/reassignment interval semantics.

Итог:

```text
Fingerprint DHCP =
IMPORTANT ADMISSION CANDIDATE

CURRENT DURABLE FINGERPRINT STORE =
NOT YET ADMITTED TEMPORAL AUTHORITY
```

---

# 3. CONTROLLED CLIENT TRACE REOPENED

Ранее controlled owner-client trace был отложен, потому что предыдущим этапам было достаточно доказать:

```text
MAC visibility
IPv4 visibility
pre-NAT placement
both directions
```

Теперь NI-G5 требует более сильное доказательство:

```text
identity-correlated temporal IP reassignment semantics
```

Поэтому controlled-client trace теперь:

```text
REQUIRED
```

---

# 4. ЧТО УЖЕ ЗАМОРОЖЕНО ДО RESEARCH

Нормативно остаётся:

```text
NO IP-only permanent identity
NO cross-MAC merge
NO alternate Registry
NO alternate Visit system
ambiguous remains ambiguous
missing attribution does not invent Device
no device_id yet does not drop observation
late authoritative device_id binding must remain possible
IPv6 does not block IPv4
```

Для `Site + MAC → existing device_id` уже заморожено:

```text
canonical identity owner = Visitor Registry
lookup key = canonical MAC
```

Forbidden:

```text
nearest MAC
fingerprint similarity merge
hostname merge
device-name merge
IP-based device_id lookup
synthetic alternate device_id
```

---

# 5. TEMPORARY POLICY UNTIL NI-G5 PASS

До отдельного Architect acceptance:

```text
Current State IP/MAC
MUST NOT be extrapolated into open-ended temporal bindings.

Observation IP/MAC
MUST NOT be extrapolated into open-ended temporal bindings.

Registry last_ip
MUST NOT be used as historical attribution authority.

Visit start_ip/final_ip
MUST NOT be treated as Visit-wide IP ownership.

Fingerprint point evidence
MUST NOT be converted into arbitrary validity windows.

No source may silently fill a gap from another source.
```

Если exact temporal authority отсутствует:

```text
ATTRIBUTION =
UNAVAILABLE / UNATTRIBUTED
```

а не guess.

---

# 6. NI-G5 RESEARCH OBJECTIVE

Исследование отвечает ровно на один вопрос:

```text
Какой минимальный production evidence source
или exact combination of sources
может детерминированно построить:

Site + IPv4 + event_at
→ Site + MAC
```

с доказанными:

```text
start boundary
end boundary
reassignment semantics
conflict semantics
coverage semantics
source health
historical availability
```

После исследования Architect, а не Coder, выбирает final authority.

---

# 7. PRIMARY ADMISSION HYPOTHESIS

Первый и предпочтительный candidate:

```text
trusted production DHCPv4 lease lifecycle
observed on the existing pre-NAT capture path
```

Research должен доказать или опровергнуть, что production capture может получить trustworthy facts минимум для:

```text
ACK / renewal ACK
assigned IPv4
client MAC
trusted DHCP server identity
lease duration / expiry basis
Release where actually emitted
Decline where actually emitted
NAK semantics where observed
subsequent reassignment
```

Ни один из этих пунктов не считается admitted заранее.

---

# 8. SUPPORTING SOURCES

Исследуются как supporting/cross-check:

```text
Current State
Historical Observation
Visitor Registry snapshots
Visit Lifecycle
Device Fingerprint packet evidence
bounded direct capture observation
```

Для каждого final report обязан выбрать ровно одну роль:

```text
PRIMARY AUTHORITY CANDIDATE
BOUNDARY TERMINATION SOURCE
SUPPORTING / CROSS-CHECK
DEVICE-ID AUTHORITY ONLY
UNSUITABLE FOR TEMPORAL ATTRIBUTION
```

Запрещён итог вида:

```text
"использовать всё и выбирать самое свежее"
```

---

# 9. ROLES

## SysAdmin / Production Research

```text
read-only production inventory
bounded packet-header / DHCP evidence capture
clock/source verification
exact runtime config capture
controlled owner-device trace execution
safe rollback of any explicitly authorized temporary action
```

## Research & QA

```text
independent evidence correlation
timeline construction
false-positive / ambiguity analysis
source-completeness analysis
reassignment proof
final PASS / PARTIAL / FAIL recommendation
```

## Architect

```text
chooses authority
freezes precedence
freezes interval semantics
freezes NI-02 architecture
```

## Coder

```text
HOLD
```

---

# 10. SAFETY BOUNDARY

Разрешено по умолчанию:

```text
read-only source inspection
read-only SQLite queries
read-only service/config inspection
bounded stdout packet inspection
owner-controlled client connect/disconnect
owner-controlled DNS/TLS/QUIC generation
owner-controlled Portal authorization
temporary research files under /tmp
```

Запрещено без отдельного Owner approval:

```text
production code change
Git commit
service restart
Suricata config change
Fingerprint config change
DHCP pool config change
DHCP lease-duration change
ACL change
RSPAN change
VLAN change
random visitor manipulation
full persistent PCAP
```

---

# 11. CONTROLLED DEVICES

Использовать только:

```text
OWNER-CONTROLLED DEVICE A
```

и, если нужен conflict/local test:

```text
OWNER-CONTROLLED DEVICE B
```

Заранее фиксируется:

```text
canonical MAC
stable/randomized MAC mode
device label
test start UTC
test end UTC
```

Случайные visitor MAC не являются active test targets.

---

# 12. PRIVACY BOUNDARY

Не сохранять:

```text
full packet payload
full PCAP
visitor DNS history
visitor SNI history
visitor application content
credentials
cookies
tokens
```

Для owner-controlled trace допустимы только необходимые fields:

```text
timestamp
MAC
IPv4
DHCP message type
DHCP transaction ID where needed
lease duration where visible
server identity
NI-01 observation_id
source_event_identity
source family
```

DNS/SNI content не нужен для NI-G5.

---

# 13. PHASE A — STATIC SOURCE CONTRACT AUDIT

На exact baseline составить `SourceAuthorityMatrix` для:

```text
Current State
Observation
Visitor Registry
Visit Lifecycle
Device Fingerprint
NI-01 Network Metadata
```

Для каждого зафиксировать:

```text
physical DB/path owner
supported read boundary
retention
site field
MAC field
IPv4 field
event timestamp
capture/ingest timestamp
explicit validity start? YES/NO
explicit validity end? YES/NO
lease duration? YES/NO
reassignment event? YES/NO
negative/removal event? YES/NO
source completeness/health? YES/NO
historical coverage horizon
missing evidence vs negative evidence semantics
current semantic owner
candidate NI-G5 role
```

---

# 14. PHASE A — CURRENT PRODUCTION VALUES

Повторно доказать current production values, не путать их с repository defaults:

```text
Current State client cadence
Current State history retention
Observation client cadence
Observation dynamic retention
Device Fingerprint retention
Visitor Registry status
Visit Lifecycle status
NI-01 retention state
capture_source_id
Site binding
Guest IPv4 CIDR
current DHCP authority/server identity
```

Каждый факт пометить:

```text
repository default
production configured
live observed
```

---

# 15. PHASE B — DHCP AUTHORITY INVENTORY

Определить exact production DHCPv4 authority:

```text
DHCP server device
server interface/address
guest pool/network
lease duration
default gateway option
server identifier / option54 behavior
reservation/static-binding behavior
current binding-table visibility
lease expiration visibility
renew/rebind behavior
historical lease log availability
authoritative start/end event visibility
```

Topology alone не считается proof.

---

# 16. PHASE B — CAPTURE SEMANTICS

На existing RSPAN path доказать для owner-controlled Device A:

```text
DHCP request visible
server reply visible
Ethernet client MAC visible
assigned IPv4 visible
trusted server identity visible
ACK visible
lease duration visible or explicitly unavailable
capture timestamp basis
```

Preferred evidence:

```text
bounded textual/header decode
```

No persistent full PCAP.

---

# 17. PHASE C1 — CURRENT BINDING TRACE

Device A sequence:

```text
1. record canonical MAC
2. record current IPv4 from client
3. record current DHCP binding where available
4. generate bounded DNS/TLS/QUIC activity
5. correlate timeline across:
   NI-01
   Current State
   Observation
   Registry
   Visit
   Fingerprint
   DHCP/capture evidence
```

Required proof:

```text
known Device A
→ one Site
→ one MAC
→ one IPv4 at event time

NI-01 endpoint
correlates to same controlled identity
```

---

# 18. PHASE C2 — RENEWAL

Observe at least one DHCP renewal/rebind if safely obtainable.

Record:

```text
pre-renew MAC/IP
request time
ACK time
assigned IP
lease duration
post-renew traffic
supporting source timestamps
```

Research reports evidence only; final renewal interval semantics are Architect-owned.

---

# 19. PHASE C3 — REAL IP REASSIGNMENT

`NI_G5_VERDICT = PASS` requires at least one real controlled reassignment boundary.

Accepted forms:

```text
CASE A:
same controlled MAC
IP1 → IP2

OR

CASE B:
same IPv4 X
MAC-A → MAC-B
where both MACs are owner-controlled
```

Record exact order:

```text
last authoritative fact supporting old binding
first authoritative end/invalidation fact if source provides one
first authoritative fact supporting new binding
NI-01 observation immediately before boundary where available
NI-01 observation immediately after boundary where available
Current State/Observation/Registry/Visit/Fingerprint comparison
```

---

# 20. REASSIGNMENT MAY NOT BE FABRICATED

Если reconnect/renew не производит reassignment:

```text
DO NOT infer or synthesize production proof.
```

Optional active DHCP action is NOT pre-authorized.

Research/SysAdmin must return:

```text
ACTIVE_REASSIGNMENT_TEST_REQUIRED
```

с exact owner-device-only proposal.

Owner approval required before execution.

Если safe real reassignment не получен:

```text
NI_G5_VERDICT = PARTIAL
TASK-DTI-NI-02 = HOLD
```

---

# 21. EXACT BOUNDARY QUESTIONS

Evidence must allow Architect later to answer:

```text
event_at == binding start
→ which MAC?

event_at immediately before ownership change
→ which MAC?

event_at == authoritative change boundary
→ which MAC?

event_at immediately after change
→ which MAC?

event_at == lease expiry
→ valid or invalid?

after expiry without renewal
→ what state?
```

Если source не может ответить без heuristic:

```text
SOURCE CANNOT BE PRIMARY TEMPORAL AUTHORITY
```

---

# 22. PHASE C4 — AMBIGUITY

Search retained source evidence for:

```text
same Site
same IPv4
different MACs
overlapping candidate validity
```

Non-owner MAC values в final report должны быть redacted/hashed if aggregate research uses them.

Если natural overlap отсутствует, допускается только non-production synthetic timeline using exact source record shape для проверки representability:

```text
MAC-A / IP-X
MAC-B / IP-X
overlapping evidence
```

Final classification:

```text
conflict detectable
partial
not detectable
```

---

# 23. PHASE C5 — MISSING BINDING

Найти или создать owner-controlled NI-01 observation, для которого candidate authority не даёт binding.

Expected semantic:

```text
NO mapping
→ UNATTRIBUTED / AUTHORITY_GAP
```

Нельзя подставлять Registry last_ip / nearest Current State / nearest Observation.

---

# 24. PHASE D — PRE-REGISTRY / LATE DEVICE_ID

Использовать owner-controlled MAC без current Registry record.

Preferred:

```text
fresh randomized MAC on Device A
```

Sequence:

```text
1. Registry exact-MAC lookup = no device_id
2. establish candidate Site+IPv4→MAC evidence
3. generate eligible network observation before Registry creation where policy permits
4. complete normal Portal authorization
5. prove Registry resolves one exact device_id for same MAC
6. prove no MAC merge/rewrite occurred
```

Research не реализует late binding; он доказывает prerequisites.

---

# 25. PRE-REGISTRY IDENTITY

Единственный допустимый pre-Registry identity candidate:

```text
Site + canonical MAC
```

Forbidden:

```text
Site + IP
IP alone
hostname
device name
fingerprint similarity
synthetic device_id
```

---

# 26. PHASE E — LOCAL DEVICE↔DEVICE

Использовать Device A + Device B, если network policy permits.

Goal:

```text
one admitted NI-01 event
with both IPv4 endpoints inside same Site scope
```

Preferred family:

```text
TLS or QUIC
```

Need independently prove:

```text
endpoint A → MAC-A
endpoint B → MAC-B
```

Если guest isolation запрещает local traffic:

```text
LOCAL_DEVICE_TO_DEVICE =
NOT_APPLICABLE_BY_PROVEN_NETWORK_POLICY
```

Нельзя отключать isolation без separate Owner approval.

---

# 27. SOURCE STRENGTH MATRIX

Для каждого source fact final report использует exact enums:

```text
authority_class =
authoritative_candidate
termination_candidate
supporting
cross_check
device_identity_only
unsuitable

temporal_precision =
explicit_interval
lease_derived_interval_candidate
point_only
current_only
unknown

conflict_visibility =
yes
partial
no

coverage_health =
explicit
partial
absent
```

---

# 28. PRIMARY AUTHORITY PASS CONDITIONS

Source / exact source combination может быть recommended for Architect admission только если ALL true:

```text
1. Site scope exact.
2. IPv4 exact.
3. MAC exact.
4. event timestamp trustworthy.
5. valid start derived without guess.
6. valid end derived without guess OR exact conservative finite end is factually supportable.
7. reassignment boundary observable.
8. conflict/overlap detectable.
9. source outage distinguishable from no binding.
10. source health/coverage representable.
11. replay gives same binding facts.
12. weaker source cannot silently override stronger contradiction.
13. historical availability known.
14. retention/backfill horizon explicitly known.
15. controlled current binding PASS.
16. controlled real reassignment PASS.
```

Failure of a mandatory item:

```text
NI_G5_VERDICT != PASS
```

---

# 29. DEVICE_ID AUTHORITY CHECK

For:

```text
Site + MAC
→ existing device_id
```

verify:

```text
exact canonical MAC lookup
one MAC does not resolve to two Registry device_ids
Site context preserved by NI observation
missing Registry record returns no device_id
later Registry appearance for same MAC observable
no cross-MAC aliasing
```

Visitor Registry remains only device_id owner.

---

# 30. FALLBACK ADMISSION TESTS

Explicitly answer:

```text
Can Current State or Historical Observation
fill a DHCP-authority gap?
```

Default before proof:

```text
NO
```

Any proposed fallback must prove:

```text
equivalent binding semantics
bounded validity
exact precedence
conflict behavior
staleness behavior
source-health behavior
```

Also explicitly answer:

```text
Can Visit start/final IP,
Registry snapshot IP,
or Registry last_ip
fill temporal IP→MAC gaps?
```

Default:

```text
NO
```

---

# 31. HISTORICAL COVERAGE / BACKFILL INPUT

Report exact earliest trustworthy timestamp for every candidate authority source:

```text
earliest retained authority fact
retention duration
whether retained NI-01 observations have matching authority
largest proven historical overlap window
```

Required classification:

```text
HISTORICAL_AUTHORITY =
SUFFICIENT_FOR_FULL_NI_R1_BACKFILL

or

SUFFICIENT_FROM <UTC>

or

CURRENT/FORWARD_ONLY

or

INSUFFICIENT
```

No backfill implementation is authorized here.

---

# 32. NI-R1 / NI-R2 RELATION

Current NI-01:

```text
Sensitive endpoint metadata = 14 days
non-sensitive core = 30 days
```

Research must determine whether temporal authority is reconstructable across the retained endpoint horizon:

```text
0..14 days
```

If authority history is shorter:

```text
BACKFILL COVERAGE = PARTIAL
```

---

# 33. CLOCK / TIME QUALITY

Use same Ubuntu capture-host timestamp basis wherever possible.

Record:

```text
host UTC time
NTP synchronization state
Suricata event timestamp basis
Fingerprint observed_at basis
Current State timestamp basis
Observation timestamp basis
controller timestamp basis if used
measured cross-source skew
```

No source can be admitted as exact boundary source if unexplained skew can reverse event ordering.

---

# 34. FORBIDDEN HEURISTICS

Forbidden conclusions:

```text
nearest timestamp wins
newest source wins
Current State overrides DHCP because newer
Registry last_ip wins
Visit-wide start_ip wins
first observed MAC owns IP until another appears
last observed MAC owns IP indefinitely
```

A point observation:

```text
T, IP-X, MAC-A
```

does NOT automatically imply any open-ended interval.

---

# 35. IPV6

NI-G5 V1 scope:

```text
IPv4 ONLY
```

IPv6:

```text
SEPARATE ADMISSION
NON-BLOCKING
```

Observed IPv6 may be recorded as capability note only.

No IPv4 identity borrowing.

---

# 36. FAILURE ISOLATION

Before/after controlled tests record:

```text
network-metadata.service state
fingerprint-sensor state/PID/NRestarts
fingerprint-suricata state/PID/NRestarts
CaptivPortal service state
NI-01 health
NI-01 fault count
```

Any unexplained regression:

```text
STOP
ROLLBACK
REPORT
```

Research must not degrade:

```text
CaptivPortal
CAPPORT
Authorization
Omada integration
Device Fingerprint
Current State
Observation
Visit Lifecycle
NI-01 ingest
```

---

# 37. NO PRODUCTION IMPLEMENTATION CHANGE

TASK-DTI-NI-G5 authorizes:

```text
NO production DB schema change
NO new service
NO permanent collector
NO new durable table
NO NI-02 code
NO Registry mutation
NO Visit mutation
```

Temporary research files:

```text
/tmp only
not committed
not service-managed
```

---

# 38. DETERMINISTIC CASE MATRIX

Final evidence matrix must include:

```text
G5-C01 current IPv4 binding
G5-C02 stable binding across multiple NI-01 events
G5-C03 DHCP renewal/rebind
G5-C04 real IP reassignment boundary
G5-C05 event before reassignment
G5-C06 event after reassignment
G5-C07 exact boundary semantics or proof boundary cannot be represented
G5-C08 ambiguous/overlapping binding representation
G5-C09 missing binding
G5-C10 pre-Registry Site+MAC
G5-C11 later exact Registry device_id
G5-C12 no cross-MAC device merge
G5-C13 one endpoint resolvable, peer external/unresolved
G5-C14 both local endpoints resolvable OR proven N/A policy
G5-C15 source authority unavailable
G5-C16 source scope unavailable/invalid
G5-C17 replay of same authority evidence
G5-C18 historical retained overlap
G5-C19 IPv6 not admitted
G5-C20 protected production services unchanged
```

---

# 39. REQUIRED CORRELATION MATRIX

Для каждого controlled milestone, где available:

```text
NI-01 observation_id
NI-01 event_at
NI-01 endpoint IPv4
NI-01 source_generation_id
DHCP/capture evidence ref
Fingerprint evidence ref
Current State cycle_id / observed_at
Observation row ref / observed_at
Registry snapshot_id / device_id
Visit visit_id / timestamps
```

Если source fact отсутствует:

```text
NONE / NOT OBSERVED
```

не молчаливый пропуск.

---

# 40. EVIDENCE CLASSIFICATION

Каждый material conclusion маркируется:

```text
SOURCE-CODE-PROVEN
CONFIGURATION-PROVEN
PRODUCTION-OBSERVED
CONTROLLED-TRACE-PROVEN
MODELED
UNKNOWN
```

`MODELED` не становится authority автоматически.

---

# 41. REQUIRED FINAL AUTHORITY TABLE

Для каждого source:

```text
Source:
<name>

Role:
PRIMARY / TERMINATION / SUPPORTING / DEVICE-ID-ONLY / REJECTED

Site authority:
YES / NO / PARTIAL

IPv4 authority:
YES / NO / PARTIAL

MAC authority:
YES / NO / PARTIAL

Start boundary:
<exact fact or NONE>

End boundary:
<exact fact or NONE>

Reassignment:
PROVEN / PARTIAL / NO

Conflict detection:
PROVEN / PARTIAL / NO

Health/coverage:
PROVEN / PARTIAL / NO

Historical horizon:
<duration / timestamp / NONE>

Fallback eligibility:
YES / NO / CONDITIONAL

Evidence class:
<highest class>
```

---

# 42. REQUIRED INTERVAL-SEMANTICS INPUT

Для recommended primary source report must state:

```text
what exact fact begins ownership
what exact fact renews ownership
what exact fact ends ownership
what exact fact supersedes ownership
what happens if explicit end is never observed
what happens at nominal lease expiry
what happens when same IP appears for new MAC
what happens when same MAC appears with new IP
whether [valid_from, valid_until) is factually supportable
timestamp precision
clock authority
known source gaps
```

Research reports facts; Architect freezes final interval law later.

---

# 43. REQUIRED PRE-REGISTRY OUTPUT

```text
PRE_REGISTRY_LATE_BINDING =
PROVEN / PARTIAL / FAIL
```

Must prove/disprove:

```text
Site+MAC exists before device_id
same exact MAC later resolves via Registry
no cross-MAC merge is needed
```

---

# 44. REQUIRED LOCAL-DEVICE OUTPUT

```text
LOCAL_DEVICE_TO_DEVICE =
PROVEN

or

NOT_APPLICABLE_BY_PROVEN_NETWORK_POLICY

or

UNPROVEN
```

If proven, include two endpoint bindings.

---

# 45. SOURCE HEALTH INPUT

For proposed authority source, identify evidence sufficient to classify later:

```text
usable
partial
stale
unavailable
unknown
```

No-binding result is invalid when authority source itself is unavailable.

---

# 46. PASS CONDITIONS

`NI_G5_VERDICT = PASS` only when ALL are true:

```text
CONTROLLED_CURRENT_BINDING = PASS
REAL_REASSIGNMENT = PASS
AUTHORITY_SOURCE_IDENTIFIED = YES
START_BOUNDARY = PROVEN
END/SUPERSESSION_BOUNDARY = PROVEN OR FACTUALLY SUPPORTABLE FINITE RULE
CONFLICT_DETECTABLE = YES
MISSING_BINDING_DISTINGUISHABLE = YES
SOURCE_OUTAGE_DISTINGUISHABLE = YES
SITE_SCOPE = PROVEN
MAC_IDENTITY = PROVEN
REGISTRY_LATE_DEVICE_ID = PROVEN
NO_CROSS_MAC_MERGE = PROVEN
HISTORICAL_HORIZON = KNOWN
IPV6 = SEPARATE / NON-BLOCKING
PROTECTED_SERVICE_REGRESSION = NO
```

---

# 47. PARTIAL / FAIL CONDITIONS

`PARTIAL` when:

```text
current binding proven but reassignment not proven
candidate viable but expiry/end semantics unresolved
historical horizon unknown
source outage not distinguishable from no binding
```

`FAIL` when:

```text
no deterministic source can bind Site+IPv4+event_at→MAC
only heuristic nearest-snapshot inference is possible
conflict cannot be detected
safe controlled reassignment cannot be supported by any candidate source
```

Both keep Coder HOLD.

---

# 48. REQUIRED FINAL VERDICT FORMAT

```text
TASK =
TASK-DTI-NI-G5

BASELINE_HEAD =
dfd3178b2cd2a3c52387402ea18600d23b052bc4

BASELINE_TREE =
c418bab3d5e1a270d8b6f12b60b5f1d7d5de8e80

MODE =
RESEARCH / ADMISSION

CONTROLLED_CLIENT_TRACE =
PASS / PARTIAL / BLOCKED

CURRENT_BINDING =
PASS / PARTIAL / FAIL

REAL_REASSIGNMENT =
PASS / PARTIAL / BLOCKED

PRIMARY_AUTHORITY_CANDIDATE =
<exact source or NONE>

TERMINATION_SOURCE =
<exact source or NONE>

ALLOWED_FALLBACK_CANDIDATE =
<exact source or NONE>

FORBIDDEN_FALLBACKS =
<exact list>

CONFLICT_DETECTION =
PASS / PARTIAL / FAIL

SOURCE_HEALTH_AUTHORITY =
<exact source / NONE>

HISTORICAL_AUTHORITY =
<FULL_NI_R1 / FROM_UTC / FORWARD_ONLY / INSUFFICIENT>

PRE_REGISTRY_LATE_BINDING =
PASS / PARTIAL / FAIL

LOCAL_DEVICE_TO_DEVICE =
PASS / NOT_APPLICABLE / PARTIAL / FAIL

IPV6_ATTRIBUTION =
NOT_ADMITTED

PROTECTED_SERVICE_REGRESSION =
NO / YES

CHANGES_MADE =
NONE
or exact Owner-authorized bounded action

ROLLBACK =
NOT_REQUIRED / PASS / FAIL

OPEN_P0 =
<number>

OPEN_P1 =
<number>

NI_G5_VERDICT =
PASS / PARTIAL / FAIL

NI_02_CODER =
HOLD
```

---

# 49. AFTER NI-G5 PASS

Даже `NI_G5_VERDICT = PASS` не авторизует Coder.

Порядок:

```text
Research / SysAdmin / QA handoff
        ↓
Architect review
        ↓
Architect freezes NI-02:
    temporal authority
    precedence
    fallback
    interval boundaries
    attribution result contract
    pre-Registry/late binding
    backfill
    edge semantics
    local Device↔Device
    storage/schema
    runtime ownership
    replay/re-attribution
    retention/privacy
    health/coverage
        ↓
TASK-DTI-NI-02
FINAL ARCHITECTURE / IMPLEMENTATION CONTRACT
        ↓
Tech Lead review
        ↓
only then Coder authorization
```

---

# 50. FINAL ARCHITECT DISPOSITION

```text
TASK-DTI-NI-01 =
CLOSED / PRODUCTION ACCEPTED

NEXT GATE =
TASK-DTI-NI-G5
TEMPORAL ATTRIBUTION AUTHORITY ADMISSION

WHY RESEARCH IS REQUIRED =
CURRENT SOURCES PROVE MULTIPLE IP/MAC POINT FACTS
BUT DO NOT YET PROVE ONE DETERMINISTIC
EVENT-TIME OWNERSHIP INTERVAL AUTHORITY

CURRENT BEST AUTHORITY HYPOTHESIS =
TRUSTED PRODUCTION DHCPv4 LEASE LIFECYCLE
OBSERVED ON EXISTING PRE-NAT CAPTURE PATH

FINAL AUTHORITY =
NOT YET ADMITTED

VISITOR REGISTRY ROLE =
MAC → EXISTING device_id AUTHORITY

CURRENT STATE =
SUPPORTING POINT EVIDENCE ONLY

HISTORICAL OBSERVATION =
SUPPORTING HISTORICAL POINT EVIDENCE ONLY

VISIT LIFECYCLE =
LIFECYCLE / CONTEXT ONLY
NOT IP LEASE AUTHORITY

CURRENT DURABLE FINGERPRINT EVIDENCE =
SUPPORTING / ADMISSION CANDIDATE
NOT YET TEMPORAL LEASE AUTHORITY

CONTROLLED OWNER TRACE =
REQUIRED NOW

REAL IP REASSIGNMENT =
MANDATORY FOR NI-G5 PASS

IPV6 =
SEPARATE ADMISSION / NON-BLOCKING

TASK-DTI-NI-02 =
HOLD

CODER =
HOLD

PRODUCTION CHANGE =
NO

OPEN_ARCHITECTURE_P0 =
0

OPEN_ARCHITECTURE_P1 =
1

OPEN_P1 =
NI-G5 TEMPORAL ATTRIBUTION AUTHORITY NOT YET ADMITTED

READY_FOR_TECH_LEAD_REVIEW =
YES
```

Следующий разрешённый шаг:

```text
Tech Lead
→ review TASK-DTI-NI-G5

if PASS:
→ Research / SysAdmin / QA execute only this bounded admission task

Coder remains HOLD.
```
