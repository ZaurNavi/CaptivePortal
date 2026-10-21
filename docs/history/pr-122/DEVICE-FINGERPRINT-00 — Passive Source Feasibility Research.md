# RESEARCH — DEVICE-FINGERPRINT-00  
## Passive Mobile / Personal Device Fingerprinting — Source Feasibility & Architecture Inputs

**Project:** CaptivPortal  
**Type:** Architecture / feasibility research  
**Status:** RESEARCH — NO IMPLEMENTATION  
**Owner goal:** подготовить доказательную базу для последующего `TASK-DEVICE-FINGERPRINT-01-DRAFT`  
**Coder:** NOT INVOLVED  
**Production feature implementation:** FORBIDDEN  

---

## 1. Goal

До проектирования Passive Device Fingerprinting Foundation необходимо доказать:

1. какие passive evidence реально доступны в текущей CaptivPortal / guest-network topology;
2. в какой физической точке их можно наблюдать;
3. сохраняется ли client-side packet information до этой точки;
4. какие существующие CaptivPortal facts уже доступны и не должны собираться повторно;
5. какие готовые parsers/tools способны безопасно извлекать evidence;
6. как связывать network evidence с текущими `device_id` / MAC / IP / Visit;
7. какие sources достаточно надёжны для Phase 1;
8. какие sources должны быть optional/deferred;
9. какие privacy/retention ограничения необходимы до начала реализации.

Research не должен создавать production fingerprint collector.

---

# 2. Architecture assumptions to verify

Исходная архитектурная гипотеза:

```text
Existing CaptivPortal facts
        +
Passive Network / Portal Evidence
        ↓
Normalized Fingerprint Evidence
        ↓
Evidence Repository
        ↓
Mobile/Personal Classification
        ↓
Derived Device Classification
```

Предварительная ownership boundary:

```text
Visitor Registry
→ device identity / device_id

Current State / Observation
→ existing Omada/controller facts

Visit Lifecycle
→ visit/session facts

Passive Fingerprint domain
→ NEW passive evidence

Classifier
→ derived classification

Admin Device Card
→ consumer only
```

Не превращать Visitor Registry или existing Observation Storage в универсальное packet evidence store без отдельного архитектурного решения.

---

# 3. Existing CaptivPortal source inventory

Провести source-level inventory и вернуть таблицу:

```text
FACT
SOURCE DOMAIN
PERSISTED?
HISTORICAL?
CURRENT?
DEVICE_ID AVAILABLE?
MAC AVAILABLE?
IP AVAILABLE?
TIMESTAMP AVAILABLE?
ALREADY SUFFICIENT FOR FINGERPRINT?
```

Минимум проверить:

```text
controller device_type / device_type_key
name
hostname
system_name
connect_device_type
MAC
IP / IPv6 if present
SSID
AP MAC/name
radio
band
channel
RSSI
SNR
active/auth state
uptime / connection duration
traffic counters
Visit duration/state
Visitor Registry snapshots
Current State facts
Observation client history
```

Goal:

```text
DO NOT COLLECT AGAIN
what CaptivPortal already owns.
```

---

# 4. Physical topology / capture-point research — BLOCKING

Определить точную current guest traffic path:

```text
Wi-Fi client
→ EAP
→ switch/trunk
→ guest VLAN
→ gateway/router
→ NAT/WAN
```

Для каждой потенциальной capture point определить:

```text
L2 source MAC visible?
VLAN tag visible?
original client IP visible?
pre-NAT?
DHCP visible?
DNS visible?
client TCP SYN visible?
TLS visible?
QUIC visible?
IPv6 ND/RA visible?
mDNS visible?
LLMNR visible?
both directions visible?
```

Особо проверить варианты:

```text
Catalyst SPAN / mirror

dedicated physical sensor NIC

existing server/hypervisor NIC possibility

Portal VM direct capture feasibility

router-side capture feasibility

other available passive tap
```

Не считать наличие SPAN достаточным доказательством.

Нужно доказать реальным bounded capture.

---

# 5. Capture safety

Исследовательские captures проводить только:

```text
в согласованное Owner окно

на Owner-controlled / lab devices
где требуется labeled ground truth
```

Не выполнять:

```text
port scan
Nmap OS scan
banner grabbing
SNMP probing clients
HTTP probes clients
special TCP probes
active TLS probes
special QUIC probes
```

Raw PCAP:

```text
temporary only

minimum necessary duration

not committed to Git

not uploaded into normal project logs

deleted after extraction/report
unless Owner explicitly requests preservation
```

Отчёт должен содержать sanitized feature excerpts, а не browsing payload.

---

# 6. DHCP feasibility proof

Проверить в реальной guest network:

```text
DHCP Discover
DHCP Request
client MAC
hostname option
client identifier
vendor class identifier
user class if present
parameter request list
ordered DHCP option list
requested IP
maximum message size
FQDN
vendor-specific options
other stable client-originating options
```

Главный вопрос:

```text
видим ли мы ORIGINAL CLIENT DHCP OPTIONS
и их ORDER в выбранной capture point?
```

Проверить минимум на доступных Owner-controlled:

```text
Android
iOS/iPadOS if available
Windows
macOS if available
Linux if available
```

Недоступная платформа:

```text
NOT TESTED
```

а не guessed PASS/FAIL.

---

# 7. Portal HTTP evidence proof

Проверить фактические headers, которые CaptivPortal получает сегодня от:

```text
normal browser

Android captive portal/webview

iOS captive portal assistant if available

Windows captive flow if available
```

Минимум:

```text
User-Agent
Sec-CH-UA
Sec-CH-UA-Mobile
Sec-CH-UA-Platform
Accept
Accept-Language
other already naturally present safe headers
```

Разделить результат:

```text
NATURALLY SENT / PASSIVE

REQUIRES Accept-CH

REQUIRES JS getHighEntropyValues()

NOT AVAILABLE
```

Особенно проверить:

```text
Sec-CH-UA-Model
platform version
architecture
bitness
```

Не изменять production response headers ради исследования без отдельного Owner authorization.

---

# 8. TCP/IP passive stack feasibility

Из естественных client-originating SYN packets проверить доступность:

```text
IP version
observed TTL
DF behavior
IPv4 ID behavior where relevant

TCP window
MSS
window scale
SACK
timestamps
ECN
TCP option set
TCP option order
```

Установить:

```text
capture is pre-NAT / post-NAT

does middlebox alter:
MSS
TTL
TCP options
window characteristics
```

Нельзя создавать OS classifier до этого proof.

Отдельно оценить:

```text
p0f-style signatures
```

только как candidate evidence extractor, не как canonical classifier authority.

---

# 9. TLS feasibility

На естественном client TLS traffic проверить, что реально видно:

```text
TLS version
cipher suite vector
extension set/order
supported groups
signature algorithms
ALPN when visible
GREASE behavior
ClientHello fingerprint
JA3/JA4-like output where supported
ECH presence/absence
```

Обязательный результат:

```text
VISIBLE ALWAYS
VISIBLE SOMETIMES
HIDDEN BY ECH
NOT AVAILABLE
```

Не предполагать, что:

```text
SNI
ALPN
inner ClientHello
```

всегда доступны.

---

# 10. QUIC / HTTP3 feasibility

На естественном QUIC traffic проверить:

```text
QUIC version
Initial packet visibility
ClientHello extraction from Initial
JA4/other supported client fingerprint
ALPN when observable
ECH behavior
transport parameters where safely exposed
```

Проверить готовыми tools прежде, чем предлагать custom parser.

---

# 11. Parser / sensor tool comparison

Сравнить минимум:

```text
Zeek

Suricata

tcpdump/tshark
as validation/reference tools

p0f
for passive TCP-stack evidence only
```

Для каждого вернуть:

```text
Ubuntu deployment feasibility
required privileges/capabilities
live-interface support
VLAN visibility
JSON/machine-readable output
DHCP fields
ordered DHCP options
TCP metadata
TLS fields
JA3/JA4
QUIC support
DNS
mDNS
LLMNR
IPv6 metadata
CPU/RAM observations
integration complexity
custom parsing required?
```

Goal:

```text
avoid writing custom packet parsers
when maintained parser already provides evidence.
```

---

# 12. DNS observability / privacy proof

Сначала определить фактическую network behavior:

```text
what DNS resolver is advertised to guest clients?

how much client DNS is plain UDP/TCP 53?

is DoT observed?

is DoH/HTTP3 likely bypassing observable DNS?

does capture point see client DNS before resolver?
```

На Owner-controlled devices проверить startup/platform traffic.

Do NOT perform general production browsing-history collection.

Research output should answer whether a privacy-safe model is feasible:

```text
raw query
→ in-memory / bounded rule match
→ ecosystem evidence
→ raw query discarded
```

Possible durable examples:

```text
ecosystem=apple
ecosystem=google_android
ecosystem=microsoft
ecosystem=samsung
```

but final rule taxonomy is NOT part of research.

---

# 13. IPv6 feasibility

Determine first:

```text
is IPv6 actually enabled on guest network?
```

If NO:

```text
IPv6 evidence =
DEFERRED / NOT AVAILABLE
```

If YES, verify visibility of:

```text
RA
RS
NS/NA
DAD
SLAAC
temporary/privacy addressing
IPv6 preference
```

Do not design an IPv6 classifier before this proof.

---

# 14. mDNS / LLMNR feasibility

Verify whether guest WLAN / AP isolation / switch behavior allows the sensor to observe:

```text
mDNS
LLMNR
```

For Phase 1 focus only on personal-device relevant evidence.

Examples to inspect:

```text
Apple device-info/workstation presence
selected AirPlay/Bonjour indicators
Windows LLMNR behavior
selected Android/Google discovery
```

Do not expand research into full IoT classification.

---

# 15. MAC / private-MAC evidence

For test devices record only:

```text
globally-administered vs locally-administered bit

OUI usable / not usable

private/randomized MAC observed

stability during same SSID test
```

Important research invariant:

```text
fingerprint evidence MUST NOT
be used to merge two different MAC/device_id identities
during this research.
```

Cross-MAC identity resolution is a separate future architecture.

---

# 16. Existing behavior evidence reuse

Determine which proposed behavioral features already exist from CaptivPortal and therefore require NO packet collector:

```text
session duration

reconnect / visits

traffic totals

current/previous activity

AP association

band

roaming evidence if currently derivable

RSSI/SNR history

uptime
```

Return:

```text
EXISTING FACT
vs
NEW PASSIVE FACT
```

Do not duplicate existing collectors.

---

# 17. Identity correlation feasibility

For every NEW packet evidence event determine which identifiers are available at observation time:

```text
site_id
timestamp
source MAC
source IP
destination IP
VLAN
SSID if independently resolvable
device_id if resolvable
visit_id if resolvable
auth_session_id if resolvable
```

Research candidate correlation chain:

```text
packet source MAC
        ↓
Visitor Registry / current device identity
        ↓
device_id
```

and where MAC is unavailable:

```text
IP + time
        ↓
current/lease evidence
        ↓
MAC
        ↓
device_id
```

Do NOT approve IP-only long-term identity.

Return every ambiguity/race found.

---

# 18. Evidence quality dataset

Use only Owner-controlled devices for ground-truth evaluation.

For each available device record ground truth:

```text
device class
OS family
vendor
model/family if known
```

Then collect per-source evidence independently.

Required result matrix:

```text
SOURCE
AVAILABLE?
CONSISTENT?
DISTINGUISHING VALUE
FALSE/MISLEADING CASES
PRIVACY COST
COLLECTION COST
RECOMMENDED PHASE
```

Do NOT tune classifier rules using random visitor devices whose true device model/OS is unknown.

---

# 19. Evidence source ranking

Research must recommend each source as one of:

```text
PHASE-1 CORE

PHASE-1 OPTIONAL

PHASE-1 WEAK SUPPORTING

DEFER

REJECT
```

Evaluate at minimum:

```text
Existing Omada/CaptivPortal
DHCP
Portal UA/default Client Hints
TCP SYN
TLS
QUIC
Hostname
MAC/OUI/private-MAC
DNS ecosystem
IPv4/IPv6 behavior
mDNS
LLMNR
connection behavior
```

No source becomes “high confidence” solely because conceptually it sounds strong.

---

# 20. Privacy classification

For each candidate evidence classify:

```text
LOW SENSITIVITY

MODERATE

HIGH / REQUIRES SPECIAL RETENTION POLICY
```

Special attention:

```text
DNS names
TLS server identifiers
raw User-Agent/model
raw PCAP
connection behavior
```

Research must recommend:

```text
what is never persisted

what is persisted only as normalized evidence

what may require short raw retention

what can safely have normal evidence retention
```

---

# 21. Raw vs durable evidence decision input

Research must explicitly distinguish:

```text
RAW ACQUISITION DATA
```

from:

```text
NORMALIZED EVIDENCE
```

Example:

```text
raw ClientHello
→ ephemeral

JA4 / normalized feature vector
→ candidate durable evidence
```

```text
raw DNS FQDN
→ ephemeral / potentially not persisted

ecosystem signal + rule/version
→ candidate durable evidence
```

Goal:

```text
classifier can be reweighted/recalculated later
from privacy-minimized normalized evidence.
```

Do not assume future extraction rules can be regenerated after raw data is discarded; document that tradeoff.

---

# 22. Evidence versioning research

Recommend how future evidence should identify:

```text
evidence source kind

extractor version

feature schema version

observed_at

site_id

device/MAC binding

quality/availability state
```

Keep this conceptual.

Do NOT design final DB schema yet.

---

# 23. Capacity / sensor viability

During bounded test window measure:

```text
packet rate

traffic rate

parser CPU

parser RAM

event output rate

DHCP events/day estimate

TLS/QUIC fingerprint event rate

DNS event rate if tested
```

Goal:

determine whether future production collector can run:

```text
on existing CaptivPortal host/VM

on existing physical host with dedicated NIC

or requires a separate sensor
```

Do not make this choice before measurements.

---

# 24. Process topology question

Research must recommend one of:

```text
A. collector inside existing captive-portal process

B. separate process/service on same VM

C. separate sensor process/VM on same host

D. separate physical sensor
```

Architectural preference before evidence:

```text
DO NOT place packet capture
inside current portal request process
unless research provides a compelling reason.
```

Packet capture privileges and failure lifecycle should be isolated from portal authorization.

---

# 25. Failure boundary

Research recommendation must preserve:

```text
Fingerprint acquisition failure
MUST NOT break captive authorization.

Classifier failure
MUST NOT break captive authorization.

Evidence DB failure
MUST NOT break captive authorization.

Device Card enrichment unavailable
!= device unknown source facts disappear.
```

---

# 26. Required final feasibility table

Return one table:

```text
SOURCE | LIVE VISIBILITY | TOOL | IDENTITY BINDING |
PRIVACY | QUALITY | PHASE-1 DECISION | BLOCKERS
```

for every proposed source.

---

# 27. Required reports

Return:

```text
1. TOPOLOGY-AND-CAPTURE-VISIBILITY

2. EXISTING-FACT-INVENTORY

3. PASSIVE-SOURCE-FEASIBILITY-MATRIX

4. PORTAL-UA-CLIENT-HINTS-PROOF

5. PACKET-PARSER-TOOL-COMPARISON

6. LAB-GROUND-TRUTH-EVIDENCE

7. IDENTITY-CORRELATION-FEASIBILITY

8. PRIVACY-RETENTION-RECOMMENDATION

9. CAPACITY-SENSOR-PLACEMENT-RESULT

10. FINAL-RESEARCH-HANDOFF
```

They may be sections of one consolidated Markdown report.

---

# 28. Final research verdict

For every source return:

```text
PASS

CONDITIONAL

FAIL

NOT TESTED
```

Final handoff must explicitly answer:

```text
Can Phase 1 be implemented passively?

Where must packet capture occur?

Which sources are realistically available?

Which sources are privacy-safe enough for V1?

What should be stored as durable normalized evidence?

Which parser/sensor stack is recommended?

Can current hardware host it?

How should evidence bind to device_id?

Which proposed sources should be removed from Phase 1?

Which questions still block Architecture DRAFT?
```

---

# 29. Forbidden during research

No:

```text
production fingerprint feature

new DB schema

new permanent worker/service

Visitor Registry schema changes

Observation schema changes

Device Card changes

classification engine

automatic user/device profiling

cross-MAC identity merging

active scanning

port scanning

client probing

long-term raw PCAP retention

general visitor DNS history retention

GitHub implementation PR
```

---

# 30. Gate

```text
DEVICE-FINGERPRINT-00
=
RESEARCH ONLY

CODER =
HOLD

IMPLEMENTATION =
NOT AUTHORIZED

ARCHITECTURE DRAFT =
HOLD UNTIL RESEARCH HANDOFF
```

After this research the Architect will prepare:

```text
TASK-DEVICE-FINGERPRINT-01-DRAFT
```

with exact:

```text
module boundaries
process topology
evidence contract
persistence ownership
identity binding
retention/privacy contract
source priorities
classification boundary
roadmap
testing/acceptance strategy
```