# TASK-DTI-NI-01
## METADATA-ONLY NETWORK OBSERVATION FOUNDATION
### АРХИТЕКТУРНЫЙ / IMPLEMENTATION CONTRACT v0.1

**Проект:** CaptivPortal  
**Программа:** DTI — Network Intelligence  
**Задача:** `TASK-DTI-NI-01`  
**Роль:** Architect  
**Статус:** `ЧЕРНОВИК ДЛЯ РЕВЬЮ TECH LEAD`

**Базовая версия репозитория:**

```text
main@c1167180daec9ca17d13ab44326f143122db8d5e
```

**Вышестоящая authority:**

```text
TASK-DTI-NI-00
= PASS / CLOSED

OPEN_P0 = 0
OPEN_P1 = 0
```

**Разрешение на реализацию:** НЕТ  
**Coder:** HOLD  
**Изменения production:** НЕТ  
**Systemd actions:** НЕТ  
**Изменения production Suricata:** НЕТ

Принятый roadmap определяет NI-01 как первый metadata-only implementation slice общей Network Observation Foundation. В NI-01 должны появиться нормализованные DNS/TLS/QUIC observation-контракты, source health, bounded ingest, idempotent replay, conflict handling, provenance/versioning, retention и layered health. Traffic buckets и Device Card в этот этап не входят.

---

# 1. ТОЧНЫЙ SCOPE NI-01

NI-01 реализует ровно:

```text
NetworkMetadataEnvelopeV1

DnsObservationV1

TlsObservationV1

QuicObservationV1

NetworkMetadataSourceHealthV1

CaptureScopeBindingV1

SourceGenerationV1

SourceCheckpointV1

SourceRecordIdentityV1

bounded regular-EVE reader

canonical source normalizer

Network Observation Store

idempotent replay

conflict detection

checkpoint recovery

retention / cleanup

internal read boundary

layered source / output / ingest health
```

NI-01 НЕ реализует:

```text
FlowProtocolObservationV1

traffic buckets
periodic traffic meter
traffic byte accounting
current traffic rate
Visit traffic slicing

Device attribution
Site+IP → MAC mapping
DeviceNetworkMetadataEdgeV1

Device Card
Admin UI

Protocol summary product
Service Recognition
Organization Recognition
Transport Health product
Security/anomaly product

DNS latency

HTTP metadata
DHCP metadata
alert ingestion

PCAP storage
packet payload storage
```

`FLOW` остаётся conditional и не может блокировать основной DNS/TLS/QUIC путь NI-01.

---

# 2. ЗАМОРОЖЕННАЯ ТОПОЛОГИЯ ИСТОЧНИКА

Канонический источник NI-01:

```text
existing production Suricata
        ↓
isolated DTI EVE output
        ↓
regular file
newline-delimited EVE JSON
        ↓
network-metadata auxiliary reader
        ↓
normalization / scope gate
        ↓
Network Observation Store
```

Логический ID источника V1:

```text
suricata-dti-ni-v1
```

Канонический путь source file:

```text
/run/fingerprint-suricata/dti-ni-v1.eve.json
```

Изолированный DTI source output содержит:

```text
DNS v3 requests + responses
TLS admitted metadata
QUIC admitted metadata
```

NI-01 НЕ добавляет второй STATS stream.

`STATS` health переиспользуется из уже принятого source-health path.

NI-01 НЕ включает в DTI output:

```text
flow
http
alert
dhcp
```

---

# 3. ГРАНИЦА СОСУЩЕСТВОВАНИЯ С DEVICE FINGERPRINT

Существующее ownership Device Fingerprint остаётся без изменений.

NI-01 НЕ ДОЛЖЕН:

```text
использовать Fingerprint EVE как product store

писать в Device Fingerprint DB

менять Fingerprint evidence semantics

менять Fingerprint classification

заменять Fingerprint source health

расширять Fingerprint normalizer

связывать доступность Network Metadata
с успешностью Fingerprint classification
```

Постоянный архитектурный инвариант:

```text
Suricata EVE != product database
Suricata EVE != Device Card API
```

Между EVE и продуктом обязательно существует нормализованный versioned contract.

---

# 4. PROCESS OWNERSHIP

NI-01 — отдельный auxiliary runtime.

Он НЕ является частью `captive-portal.service`.

Канонический runtime entrypoint:

```text
python3 -m app.network_metadata.cli run
```

Каноническая будущая systemd identity:

```text
network-metadata.service
```

Этот документ определяет target identity, но НЕ разрешает:

```text
создание unit
установку unit
enable
start
restart
```

Failure invariant:

```text
network-metadata unavailable
!=
Portal unavailable

network-metadata unavailable
!=
CAPPORT unavailable

network-metadata unavailable
!=
Authorization unavailable

network-metadata unavailable
!=
Device Fingerprint unavailable
```

Основной процесс CaptivPortal не является writer'ом Network Observation Store.

---

# 5. SOURCE GENERATION — ТОЧНОЕ ОПРЕДЕЛЕНИЕ

Принятый NI-00 primitive:

```text
source_generation
+
record_start_byte_offset
```

`source_generation_id` в NI-01 — это:

```text
opaque UUID,
создаваемый NI reader ровно один раз
для одного непрерывного byte-address namespace
одной жизни admitted source file
```

Он НЕ является:

```text
content hash
DNS/TLS/QUIC identity
Suricata PID
arrival timestamp
inode сам по себе
filename сам по себе
```

После создания `source_generation_id` сохраняется durable и остаётся immutable.

---

# 6. ИДЕНТИЧНОСТЬ ЖИЗНЕННОГО ЦИКЛА SOURCE FILE

Для проверки continuity reader сохраняет:

```text
logical_source_id

source_generation_id

host_boot_id

st_dev

st_ino

committed_byte_offset

continuity_anchor_start_offset
continuity_anchor_length
continuity_anchor_sha256
```

`continuity_anchor_sha256` используется только как:

```text
bounded file-continuity guard
```

Он НЕ является event identity.

Anchor покрывает до последних 4096 уже committed source bytes непосредственно перед durable checkpoint.

Сами source bytes в checkpoint не сохраняются.

---

# 7. УСЛОВИЯ ПРОДОЛЖЕНИЯ ТОЙ ЖЕ GENERATION

После рестарта reader предыдущий `source_generation_id` разрешено продолжить только если одновременно истинны все условия:

```text
тот же logical source

тот же host_boot_id

тот же st_dev

тот же st_ino

current file size >= committed checkpoint

сохранённый continuity anchor совпадает
```

Тогда:

```text
reader продолжает с committed_byte_offset
```

Если хотя бы одно условие не выполняется:

```text
NEW source_generation
```

Без эвристики и без угадывания.

---

# 8. ГРАНИЦЫ НОВОЙ SOURCE GENERATION

Новый `source_generation_id` обязателен, если произошло любое из событий:

```text
изменился host boot_id

изменился st_dev source file

изменился st_ino source file

размер файла стал меньше committed checkpoint

continuity anchor больше не совпадает

source file исчез,
а затем появился после того,
как предыдущая generation была признана lost/closed

обнаружен copytruncate или эквивалентная truncation
```

Один лишь restart Suricata НЕ является автоматической generation boundary.

Следовательно:

```text
Suricata restart
+
same inode
+
append continuity valid
→ same source_generation
```

Но:

```text
Suricata restart
+
replace/truncate file
→ new source_generation
```

---

# 9. HOST REBOOT И ПОТЕРЯ `/run`

Поскольку source находится в `/run`, reboot может уничтожить source file.

Каноническое поведение:

```text
old boot_id = A

host reboot

new boot_id = B
        ↓
предыдущая active source_generation
не может быть продолжена
        ↓
предыдущая generation закрывается:
host_reboot_source_lost
        ↓
ожидание source file
        ↓
новый file появился
        ↓
создать NEW source_generation
offset = 0
```

Исчезнувшие `/run` bytes не восстанавливаются и не реконструируются.

События для образовавшегося gap не фабрикуются.

Source health обязан отразить coverage discontinuity.

---

# 10. ROTATION SEMANTICS

V1 поддерживает как безопасную producer-owned модель:

```text
rename / replace / reopen
```

`copytruncate` НЕ считается continuity-preserving.

Если обнаружен copytruncate:

```text
old generation ended
+
possible coverage gap
+
new source_generation
```

NI reader сам НЕ ДОЛЖЕН:

```text
посылать signal Suricata
restart Suricata
truncate active EVE
rotate Suricata logs
менять Suricata configuration
```

Rotation/retention source transport остаются operational ownership producer'а.

Production activation должна использовать bounded rotation policy, удерживающую активный DTI source ниже:

```text
134217728 bytes
= 128 MiB
```

---

# 11. ROTATION ПРИ РАБОТАЮЩЕМ READER

Если canonical path начинает указывать на новый файл, а reader всё ещё держит открытым старый file descriptor:

```text
1. пометить old generation как closing

2. дочитать уже открытый old descriptor
   до последней complete newline record

3. зафиксировать final checkpoint

4. закрыть old generation

5. открыть current canonical path

6. создать new source_generation

7. начать с offset 0
```

Reader НЕ ДОЛЖЕН объединять старый и новый файл в один byte-offset namespace.

---

# 12. ROTATION ПОКА READER НЕ РАБОТАЛ

V1 не выполняет heuristic directory archaeology.

Если reader стартует и:

```text
stored generation identity
!=
current canonical source-file identity
```

то предыдущая generation закрывается с причиной:

```text
source_replaced_while_reader_down
```

и:

```text
coverage_gap_possible = true
```

Новая generation начинается с текущего canonical source file.

Rotated-away historical EVE files автоматически НЕ импортируются.

Это сознательное решение, потому что NI-R0 raw EVE — transient transport, а не product history.

---

# 13. ТОЧНАЯ SOURCE RECORD IDENTITY

Для каждой complete EVE line:

```text
SourceRecordIdentityV1 {
    source_generation_id
    record_start_byte_offset
}
```

Каноническая serialised identity:

```text
suricata-eve-v1:<source_generation_uuid>:<decimal_start_offset>
```

Именно она используется как `source_event_identity` нормализованного observation.

Запрещены identity constructions:

```text
content hash alone

DNS name + time

endpoint + time

flow_id alone

transaction_id alone

arrival time

event_at alone
```

---

# 14. OBSERVATION IDENTITY

Каждая admitted EVE line создаёт максимум один top-level normalized family observation.

Канонический `observation_id` детерминированно строится из:

```text
source_event_identity
+
normalized family
+
normalized schema version
```

с использованием фиксированного NI-01 UUID namespace.

Повторный replay той же source record обязан давать тот же `observation_id`.

`ingested_at` в semantic identity НЕ входит.

---

# 15. RAW И SEMANTIC DIGESTS

Для каждой complete source record reader вычисляет:

```text
source_record_sha256
```

по точным source bytes без завершающего newline.

Для успешно нормализованной записи дополнительно вычисляется:

```text
semantic_payload_sha256
```

по canonical normalized semantic content.

Semantic digest НЕ включает:

```text
ingested_at
health snapshot identity
runtime counters
mutable operational status
```

Digests используются для conflict/audit evidence.

Они не заменяют принятую source identity.

---

# 16. IDEMPOTENT REPLAY

Каноническое правило:

```text
same source_event_identity
+
same semantic_payload_sha256
→ duplicate_noop
```

Исходное сохранённое observation не изменяется.

Replay НЕ меняет:

```text
observation_id
event_at
ingested_at
provenance
source_health_ref
```

и не создаёт второе observation.

---

# 17. CONFLICT

Канонический conflict:

```text
same source_event_identity
+
different normalized semantic payload
→ SOURCE IDENTITY CONFLICT
```

Результат:

```text
существующее observation никогда не перезаписывается

новое конфликтующее observation не вставляется

conflict fault сохраняется durable

checkpoint НЕ продвигается дальше конфликтующей record

metadata_ingest_health = unavailable

обработка этой source_generation приостанавливается
```

Новая действительно новая source generation позднее может продолжить ingest.

Запрещены:

```text
best effort overwrite
first-writer-wins
last-writer-wins
```

---

# 18. CHECKPOINT TRANSACTION

Один normal batch фиксируется одной SQLite write transaction, которая атомарно commit'ит:

```text
source-record identity/digest state

normalized observation rows

family-specific rows

необходимые source-health/fault изменения

checkpoint advancement
```

Только после успешного commit разрешено продвинуть:

```text
committed_byte_offset
```

Crash до commit:

```text
те же source bytes повторно replay'ятся
→ idempotent
```

Crash после commit:

```text
resume after committed offset
```

Никакой отдельный checkpoint file не является authoritative.

Canonical checkpoint state хранится в SQLite.

---

# 19. PARTIAL FINAL RECORD

Source record считается admissible только после обнаружения newline delimiter.

То есть:

```text
bytes after final newline
+
no terminating newline
→ PARTIAL
```

Пока generation active:

```text
wait
не parse
не checkpoint
```

Если generation достоверно закрывается, а tail так и не получил newline:

```text
сохранить bounded partial_final_record fault

сохранить только:
source_generation_id
offset
byte_length
sha256

НЕ сохранять raw bytes

НЕ normalise

закрыть generation
```

Даже если JSON визуально выглядит синтаксически целым, без newline он не принимается как complete EVE transport record.

---

# 20. COMPLETE MALFORMED RECORD

Для newline-terminated record с ошибкой:

```text
UTF-8 failure
JSON parse failure
non-object JSON
schema failure
```

reader сохраняет bounded ingest fault:

```text
source_event_identity
fault category
record byte length
source_record_sha256
observed_at/ingested_at where safely known
```

Raw record body не сохраняется.

Poison record считается consumed, checkpoint продвигается за неё.

Health становится как минимум:

```text
partial
```

Одна malformed record не должна навсегда заблокировать ingest.

---

# 21. RECORD RESOURCE LIMIT

Максимальный размер одной complete source record:

```text
1 MiB
= 1048576 bytes
```

Newline-terminated record, превышающая лимит:

```text
не parse

не normalise

raw content не сохраняется

записывается bounded resource_limit fault

checkpoint продвигается после terminating newline
```

Unterminated over-limit tail обрабатывается как output/resource fault без unbounded buffering.

Reader может удерживать в памяти не больше configured technical ceiling для одной unfinished line.

Это technical containment limit, а не семантическое утверждение о Suricata.

---

# 22. BATCH BOUNDS

Одна ingest transaction обрабатывает максимум:

```text
256 complete source records
```

и максимум:

```text
1 MiB source bytes
```

— что наступит раньше.

Target poll interval:

```text
1 second
```

Это НЕ задаёт будущий Device Card refresh cadence.

---

# 23. NETWORK SCOPE AUTHORITY

NI-00 зафиксировал:

```text
capture_source_id =
zefer-span-01

V1 intended IPv4 population =
192.168.8.0/22

VLAN identity at VM capture API =
NOT AUTHORITY
```

NI-01 вводит:

```text
CaptureScopeBindingV1
```

с полями:

```text
schema_version

capture_source_id

site_id

network_scope_id

ipv4_cidrs

valid_from_utc

binding_digest
```

Binding является configuration authority.

Он не выводится из отдельного packet/event.

---

# 24. SITE ID НЕЛЬЗЯ HARDCODE'ИТЬ

Repository НЕ ДОЛЖЕН hardcode'ить production Site ID для NI-01.

Active deployment обязан передать exact current Site identity через approved capture-scope binding.

Это защищает от silent reinterpretation при миграции Site.

`Home`, SSID name, interface name или subnet сами по себе не заменяют Site identity.

---

# 25. SCOPE BINDING IDENTITY

`binding_digest`:

```text
SHA-256(
  canonical JSON safe semantic content CaptureScopeBindingV1
)
```

Binding не содержит secret.

Каждая source generation pin'ит ровно один binding digest.

Изменение binding требует новой source generation до продолжения ingest.

Event одной capture-binding epoch не переинтерпретируется под более новым binding.

---

# 26. V1 NETWORK SCOPE GATE

Для IPv4 event:

```text
хотя бы один src/dst endpoint
находится внутри admitted IPv4 network scope
→ event eligible для NI-01 observation persistence
```

Иначе:

```text
outside_intended_scope
→ product observation row не создаётся
```

Out-of-scope records учитываются только в bounded aggregate ingest/health counters.

Их DNS/SNI/IP values не сохраняются.

---

# 27. IPV6

NI-01 не придумывает IPv6 scope authority.

Пока trustworthy IPv6 binding отдельно не admitted:

```text
IPv6-only source event
→ unsupported_address_family_for_scope
→ no normalized product observation
```

IPv6 event не связывается с IPv4 identity.

Он не блокирует IPv4 NI-01.

---

# 28. НИКАКОЙ DEVICE ATTRIBUTION

NI-01 заканчивается на:

```text
Site-scoped normalized network observation
```

NI-01 не выполняет:

```text
IP → MAC

MAC → device_id

Device direction normalization

Device-relative peer projection
```

`Site + IPv4 + event_at → Site + MAC → device_id` принадлежит следующему этапу NI-02.

---

# 29. `NetworkMetadataEnvelopeV1`

Канонические поля:

```text
observation_id

schema_version = 1

source_type = suricata
source_contract_version = suricata-eve-v1
source_event_family

source_event_identity
source_generation_id
record_start_byte_offset
source_record_sha256

capture_source_id
capture_scope_binding_version

network_scope_id
network_scope_state

site_id

event_at
ingested_at

flow_id nullable
transaction_id nullable

source_health_ref

ingest_run_id
normalizer_version
```

`event_at` и `ingested_at` всегда являются разными понятиями.

Late arrival не делает старое evidence current.

---

# 30. SENSITIVE ENDPOINT SIDECAR

Fine-grained endpoint data хранится отдельно от более долго живущего base observation:

```text
NetworkMetadataSensitiveEndpointV1
```

Поля:

```text
observation_id

src_ip nullable
dst_ip nullable

src_port nullable
dst_port nullable

transport_protocol nullable
```

Такое разделение позволяет применить более короткий retention к SensitiveNetworkMetadata без удаления всей структурной observation.

---

# 31. `DnsObservationV1`

Одна DNS EVE source record отображается в один `DnsObservationV1`.

Канонические поля:

```text
observation_id

dns_version = 3

dns_event_kind =
request | response

flow_id

dns_tx_id

dns_wire_id nullable

queries[]

rcode nullable

answers[]

queries_truncated
answers_truncated
```

`dns_tx_id` — correlation identity внутри flow context.

Это НЕ global source-event identity.

---

# 32. DNS QUERIES

Каждый query entry содержит ровно:

```text
query_name
query_type
```

Bounds:

```text
max queries per source record = 8
```

`query_name` сохраняется в том виде, в котором emitted source после успешного UTF-8 parsing.

NI-01 не выполняет:

```text
lowercase transformation
service classification
organization classification
registrable-domain guessing
```

Raw DNS names являются `SensitiveNetworkMetadata`.

---

# 33. DNS ANSWERS

NI-01 сохраняет только bounded answer metadata, необходимые для будущей deterministic correlation:

```text
A
AAAA
CNAME
```

Каждый retained answer содержит:

```text
answer_type
answer_value
```

Maximum:

```text
32 retained answers per DNS source record
```

Если answers больше:

```text
answers_truncated = true
```

DNS payload за пределами admitted fields не сохраняется.

DNS transaction latency НЕ вычисляется.

---

# 34. `TlsObservationV1`

Канонические поля:

```text
observation_id

flow_id nullable

tls_version nullable

sni nullable

client_alpns[]
server_alpns[]
```

Bounds:

```text
max ALPN entries per side = 16
max one ALPN value = 255 bytes UTF-8
```

Не сохраняются:

```text
certificate body
certificate chain
```

NI-01 не создаёт JA4-derived device/classification claim.

Постоянный инвариант:

```text
sni = null
!=
service absent
```

---

# 35. `QuicObservationV1`

Канонические V1 fields:

```text
observation_id

flow_id nullable

quic_version nullable

sni nullable
```

Generic arbitrary field вроде:

```text
handshake_metadata_json
```

не сохраняется.

В normalized V1 schema входят только конкретно замороженные поля:

```text
QUIC version
nullable SNI
flow relation
```

Будущее добавление нового named handshake field требует явного schema-version extension.

Постоянный инвариант:

```text
missing / opaque QUIC metadata
→ UNKNOWN

не
→ negative service evidence
```

---

# 36. STATS

Изолированный NI-01 EVE file не дублирует STATS.

`capture_health` использует уже admitted existing source-health boundary.

NI-01 НЕ ДОЛЖЕН напрямую читать Device Fingerprint SQLite tables.

Reuse разрешён только через существующий source-health/read-service boundary.

Если boundary не способен дать trustworthy current capture health:

```text
capture_health = unknown
или unavailable
```

а не optimistic `usable`.

---

# 37. OWNERSHIP NETWORK OBSERVATION STORE

Логический owner:

```text
Network Metadata Foundation
```

Physical V1 candidate:

```text
SQLite
```

Канонический target path:

```text
/opt/CaptivePortal/data/network_metadata.sqlite3
```

Это отдельный Network Observation Store.

Он НЕ является:

```text
Device Fingerprint DB
Observation DB
Current State DB
Traffic Projection DB
SettingsStore
```

---

# 38. СТАТУС SQLITE

Выбор SQLite:

```text
CANDIDATE ACCEPTED FOR NI-01 IMPLEMENTATION
SUBJECT TO MANDATORY LAB CAPACITY GATE
```

То есть:

```text
Coder может реализовать SQLite V1
```

но:

```text
production acceptance запрещён,
если NI-01 capacity gate FAIL
```

При FAIL выбор storage возвращается Architect / Tech Lead.

Молчаливая замена DB engine запрещена.

---

# 39. DATABASE DURABILITY CONTRACT

V1 database использует:

```text
SQLite WAL

foreign_keys = ON

synchronous = FULL

bounded busy timeout

one logical writer
```

Только `network-metadata.service` владеет write path.

Будущие consumers читают данные через read service.

Прямой consumer SQL против store запрещён.

---

# 40. ЛОГИЧЕСКИЕ TABLES

Schema V1 логически содержит:

```text
network_metadata_schema

network_metadata_ingest_runs

network_metadata_capture_scope_bindings

network_metadata_source_generations

network_metadata_checkpoint

network_metadata_source_records

network_metadata_observations

network_metadata_sensitive_endpoints

network_metadata_dns

network_metadata_dns_queries

network_metadata_dns_answers

network_metadata_tls

network_metadata_tls_alpn

network_metadata_quic

network_metadata_source_health

network_metadata_ingest_faults
```

Точные SQL definitions и indices фиксируются implementation TASK/PLAN, но semantic ownership и separation выше обязательны.

---

# 41. SOURCE-RECORD UNIQUENESS

Hard uniqueness:

```text
(source_generation_id, record_start_byte_offset)
```

Вторая row с той же identity не может молча заменить первую.

Family observation имеет one-to-one ownership от source record.

---

# 42. INGEST RUN PROVENANCE

Каждый service process run создаёт immutable:

```text
IngestRunV1
```

минимум с полями:

```text
ingest_run_id

started_at_utc

repository commit identity
repository tree identity

normalizer_version

configuration digest
```

Configuration digest не включает secrets и включает active capture-scope binding.

Observations ссылаются на:

```text
ingest_run_id
```

Это запрещает будущим версиям кода молча переинтерпретировать старые rows без provenance.

---

# 43. SOURCE HEALTH MODEL

`NetworkMetadataSourceHealthV1` содержит отдельные dimensions:

```text
health_id

evaluated_at

capture_source_id

source_generation_id nullable

capture_health

metadata_output_health

metadata_ingest_health

last_output_event_at nullable

last_ingested_event_at nullable

committed_byte_offset nullable

reason_codes[]
```

Один boolean:

```text
healthy = true/false
```

не может заменять эти dimensions.

---

# 44. HEALTH ENUM

Каждая NI-01 health dimension использует:

```text
usable

partial

stale

unavailable

unknown
```

`unknown` означает недостаток evidence.

`unknown` не считается healthy.

---

# 45. CAPTURE HEALTH

`capture_health` выводится только из admitted capture/Fingerprint source-health evidence.

Примеры:

```text
source-health явно usable
→ usable

известны drops/degradation
в рамках admitted semantics
→ partial

source-health stale
→ stale

source-health unavailable
→ unavailable

нет trustworthy health evidence
→ unknown
```

NI-01 не пересчитывает NIC/Suricata packet health из unrelated application events.

---

# 46. METADATA OUTPUT HEALTH

`metadata_output_health` относится только к изолированной DTI EVE delivery.

Примеры:

```text
valid current source file identity
+
нет lifecycle/resource fault
→ usable

malformed/unsupported records имеются,
но valid ingest продолжается
→ partial

source path absent
→ unavailable

source identity conflict
→ unavailable
```

Silence сама по себе НЕ доказывает failure, потому что qualifying DNS/TLS/QUIC activity могла отсутствовать.

---

# 47. METADATA INGEST HEALTH

`metadata_ingest_health` отражает состояние:

```text
reader
normalizer
database
checkpoint
conflict state
```

Примеры:

```text
normal processing
→ usable

bounded malformed records
→ partial

database unavailable
→ unavailable

source identity conflict
→ unavailable

невозможно установить service state
→ unknown
```

---

# 48. SOURCE ABSENT AT START

Auxiliary service НЕ ДОЛЖЕН попадать в restart loop только потому, что `/run` source file ещё не существует.

Каноническое поведение:

```text
service starts
DB/readiness available

source absent
→ metadata_output_health = unavailable
→ bounded wait/retry

source appears
→ allocate/admit generation
→ begin ingest
```

Portal/Auth/Fingerprint при этом не затрагиваются.

---

# 49. SOURCE ИСЧЕЗАЕТ ВО ВРЕМЯ РАБОТЫ

Каноническое поведение:

```text
не фабриковать EOF success

не переиспользовать old identity для new file

закрыть/loss-classify generation где применимо

metadata_output_health = unavailable

ждать source reappearance

при reappearance:
выполнить полный generation identity decision
```

Запрещено угадывать другой path со «старыми байтами».

---

# 50. DATABASE FAILURE

При SQLite unavailable/corrupt/resource-limit failure:

```text
source checkpoint НЕ продвигается

accepted source identity не теряется

metadata_ingest_health = unavailable

normalization writes останавливаются
```

Нет fallback DB.

Нет записи в Fingerprint DB.

Нет «успешного» in-memory ingest, который не переживёт restart.

---

# 51. DATABASE HARD CAP

V1 hard database ceiling:

```text
8589934592 bytes
= 8 GiB
```

До production activation capacity gate обязан доказать:

```text
expected steady-state
при frozen retention
с существенным запасом ниже hard cap
```

Hard cap — safety containment, а не целевое заполнение.

Если после normal retention cleanup cap достигнут:

```text
ingest stops
checkpoint stops
metadata_ingest_health = unavailable
```

Unexpired observations не удаляются молча только ради удержания DB ниже cap.

---

# 52. RETENTION — FINAL NI-01 POLICY

NI-01 фиксирует:

```text
NI-R0
raw EVE transport
=
NO product retention
transient source transport only

NI-R1
SensitiveNetworkMetadata
=
14 days maximum

NI-R2
non-sensitive normalized observation core
=
30 days maximum

NetworkMetadataSourceHealthV1
=
45 days maximum

ingest faults / quality evidence
=
45 days maximum

source generation / checkpoint / provenance lineage
=
90 days after generation closure
```

Active source generation и её live checkpoint никогда не удаляются retention cleanup.

---

# 53. RETENTION CLOCK

Observation data удаляются, если выполняется хотя бы одно условие:

```text
event_at < now - retention
OR
ingested_at < now - retention
```

Это не позволяет:

```text
очень старому late event
```

или:

```text
недавно ingested,
но семантически древнему event
```

расширить sensitive history сверх policy.

---

# 54. ЧТО ВХОДИТ В NI-R1

NI-R1 включает:

```text
src_ip
dst_ip

src_port
dst_port

DNS query names
DNS answer IPs
DNS CNAME values

TLS SNI
QUIC SNI

другие будущие fine-grained endpoint identifiers
```

Они хранятся только в short-retained sensitive tables.

Они никогда не являются routine log fields.

---

# 55. ЧТО ВХОДИТ В NI-R2

NI-R2 может сохранять без NI-R1:

```text
family
event_at
flow correlation IDs
transaction IDs
DNS request/response type
DNS query type
DNS rcode/result
TLS version
ALPN
QUIC version
scope/binding/provenance
```

После expiry NI-R1 слой NI-R2 не имеет права заявлять Device-level reconstructability.

---

# 56. REBUILDABILITY CONSEQUENCE

NI-02 temporal attribution требует endpoint evidence.

Поэтому:

```text
NI-R1 endpoint data expired
→ historical Device attribution cannot be reconstructed
from that NI-01 observation
```

Позднейший task не имеет права притворяться обратным.

Если NI-02 уже успел materialize provenance-complete attribution result до expiry NI-R1, этот derived result может жить по своему отдельно принятому retention contract.

---

# 57. RETENTION CLEANUP

Writer-owned cleanup запускается:

```text
при startup
+
не чаще одного раза в час во время runtime
```

Deletion выполняется bounded transaction batches.

Cleanup не запускается из read service.

Cleanup не меняет checkpoint/source identity.

---

# 58. RAW PAYLOAD PROHIBITION

Постоянно запрещено:

```text
packet payload

PCAP

HTTP content

TLS application data

full arbitrary EVE record persistence

request/response body

credentials

cookies

authorization headers
```

---

# 59. LOGGING PRIVACY

Routine logs могут содержать:

```text
source_generation_id

byte offset

observation_id

family

reason code

counts

health state

database capacity state
```

Routine logs НЕ ДОЛЖНЫ содержать:

```text
DNS query name

SNI

remote IP

endpoint tuple

raw EVE JSON

source record bytes
```

Exception traceback не должен сериализовать целый event object.

---

# 60. НИКАКОГО HTTP/API SURFACE

NI-01 не создаёт public или Admin route.

В частности нет:

```text
/admin/api/...
/api/network-metadata/...
Device Card endpoint
diagnostic raw-domain endpoint
```

Sensitive metadata не получает browser-visible permission surface на этапе NI-01.

Любой будущий diagnostic API требует отдельного authorization contract.

---

# 61. INTERNAL READ SERVICE

NI-01 предоставляет internal boundary:

```text
NetworkMetadataReadService
```

Будущие NI-02/NI-03 consumers ОБЯЗАНЫ использовать его вместо direct SQLite access.

Read service владеет:

```text
Site validation

event-time windows

family filters

stable ordering

bounded pagination

retention visibility

source-health joins/projections
```

Device attribution logic внутри этого read service запрещён.

---

# 62. READ ORDER

Канонический порядок:

```text
event_at ASC
observation_id ASC
```

для deterministic replay/history consumption.

Future reverse/latest query может появиться только как versioned read method.

Consumers не зависят от SQLite `rowid`.

---

# 63. READ BOUNDS

V1 internal read:

```text
maximum page size = 500
```

Unbounded full-history materialization запрещён.

Максимальный query window не может превышать retained NI-R2 horizon.

Sensitive endpoint material возвращается только явно авторизованным internal foundation consumers, например будущему attribution layer, и не выдаётся обычному reader по умолчанию.

---

# 64. CONFIGURATION BOUNDARY

NI-01 configuration — process/environment controlled.

Она НЕ входит в CaptivPortal Admin Settings в рамках этой задачи.

Canonical settings family:

```text
NETWORK_METADATA_*
```

Минимальный configuration contract:

```text
NETWORK_METADATA_ENABLED=false

NETWORK_METADATA_SOURCE_PATH=
/run/fingerprint-suricata/dti-ni-v1.eve.json

NETWORK_METADATA_DB_PATH=
/opt/CaptivePortal/data/network_metadata.sqlite3

NETWORK_METADATA_MAX_DB_BYTES=
8589934592

NETWORK_METADATA_MAX_RECORD_BYTES=
1048576

NETWORK_METADATA_BATCH_MAX_RECORDS=
256

NETWORK_METADATA_BATCH_MAX_BYTES=
1048576

NETWORK_METADATA_POLL_INTERVAL_SECONDS=
1
```

Capture scope передаётся через один strict V1 binding config, а не через scattered guesses.

---

# 65. ENABLEMENT DEFAULT

Repository default:

```text
NETWORK_METADATA_ENABLED=false
```

Disabled означает:

```text
не открывать source file

не создавать Network Metadata DB

не запускать background loop

не взаимодействовать с Suricata
```

Merge NI-01 сам по себе не является production activation.

---

# 66. CAPTURE SCOPE CONFIG

При enabled требуется ровно один V1 binding.

Концептуально:

```json
{
  "capture_source_id": "zefer-span-01",
  "site_id": "<deployment Site ID>",
  "network_scope_id": "<deployment scope id>",
  "ipv4_cidrs": [
    "192.168.8.0/22"
  ]
}
```

Exact Site ID задаётся deployment и source-verified при activation.

Запрещены:

```text
implicit Site
first configured Site
Home shortcut
```

---

# 67. CONFIG VALIDATION

Перед startup writer обязательно проверяет:

```text
absolute source path required

absolute DB path required

source path != DB path

capture_source_id required

one valid Site ID required

network_scope_id required

exact non-overlapping IPv4 CIDR set required

V1 current scope contains 192.168.8.0/22

positive technical bounds required

DB cap >= implementation minimum

no unsupported IPv6 authority
```

Invalid configuration fail-closed только для auxiliary runtime.

Main Portal продолжает работать.

---

# 68. CONFIG DIGEST

Validated safe runtime config canonicalize'ится и hash'ится.

Digest входит в:

```text
IngestRunV1
```

и в generation provenance.

Secrets в NI-01 config отсутствуют.

---

# 69. SOURCE FAMILY ALLOWLIST

Ровно:

```text
dns
tls
quic
```

normalise'ятся в Network Metadata observations.

`stats` не дублируется в isolated source.

Unexpected families:

```text
flow
http
alert
dhcp
other
```

дают:

```text
no normalized product observation

bounded unexpected_family counter/fault

metadata_output_health at least partial
```

Source field не может быть молча admitted только потому, что Suricata его emitted.

---

# 70. FIELD MINIMIZATION

Unknown JSON members игнорируются versioned parser'ом, если они явно не admitted.

Они не копируются в generic columns:

```text
payload_json
extras_json
raw_event_json
```

Это постоянный NI-01 data-minimization invariant.

---

# 71. `event_at`

`event_at` берётся исключительно из admitted Suricata semantic event timestamp.

Он normalise'ится в UTC.

Он никогда не заменяется на file mtime или read time.

---

# 72. `ingested_at`

`ingested_at` — central reader time первого успешного durable commit source record.

Idempotent replay сохраняет первоначальный value.

Постоянно:

```text
event_at != ingested_at
```

как два разных понятия.

---

# 73. LATE DELIVERY

NI-01 сохраняет evidence о lateness, но НЕ классифицирует product presentation как:

```text
fresh
recent
stale
```

Эти окна принадлежат более позднему NI-03 product contract.

Late arrival никогда не изменяет `event_at`.

Arrival timestamp не делает старое evidence current.

---

# 74. SOURCE HEALTH REFERENCES

Каждое успешно сохранённое observation ссылается на current NI source-health snapshot, доступный в момент первого commit.

Если trustworthy health snapshot невозможно построить:

```text
source_health_ref указывает
на explicit unknown/unavailable health record
```

Health не может быть пропущен и позже по умолчанию считаться healthy.

---

# 75. MISSING METADATA SEMANTICS

Канонически:

```text
TLS SNI null
→ not observed / unavailable in that source event

QUIC SNI null
→ not observed / opaque

no DNS record
→ no claim unless source coverage is sufficient
```

Запрещено:

```text
SNI null → no service

no NI observation → no network activity
```

---

# 76. AUXILIARY SERVICE FAILURE

Network Metadata failure изолирован.

Ни один компонент не имеет права использовать NI-01 failure для:

```text
block guest authorization
unauthorize guest
block CAPPORT
restart Omada
control AP/client state
```

DTI — evidence/intelligence subsystem, а не enforcement owner.

---

# 77. SERVICE RESTART

Reader/service restart:

```text
не создаёт new source generation
```

если source continuity proof PASS.

Reader открывает DB, читает durable checkpoint и продолжает ingest.

Duplicate observation не создаётся.

---

# 78. INGEST CODE RESTART / UPGRADE

Новый code build может продолжить existing source generation, если file continuity PASS.

Но каждое новое inserted observation сохраняет новый:

```text
ingest_run_id
normalizer_version
```

Previously committed observation semantics не переписываются.

Semantic normalization change требует:

```text
new normalized schema version
```

а не reinterpretation старых rows.

---

# 79. SCHEMA VERSIONING

Initial:

```text
NetworkMetadataEnvelopeV1
schema_version = 1

DnsObservationV1
schema_version = 1

TlsObservationV1
schema_version = 1

QuicObservationV1
schema_version = 1

NetworkMetadataSourceHealthV1
schema_version = 1
```

Future incompatible field semantics требуют schema evolution.

Nearest-version parsing запрещён.

---

# 80. DATABASE MIGRATION PRINCIPLE

V1 стартует со schema version 1.

Future schema migration должна быть:

```text
explicit
transactional
version checked
rollback-safe before writer activation
```

Unknown/newer schema:

```text
writer does not start
```

Automatic destructive reinitialize запрещён.

---

# 81. SOURCE CONFLICT — НЕ DEDUPLICATION

Постоянно:

```text
duplicate
=
same identity + same semantic fact

conflict
=
same identity + different semantic fact
```

Conflict запрещено разрешать через:

```text
timestamp preference
larger JSON
newest arrival
hash sort
field merge
```

---

# 82. NO HEURISTIC DEDUP

Явно запрещены эвристики:

```text
same DNS name nearby

same SNI nearby

same flow_id nearby

same IP nearby

same query + second

same semantic hash from a different source offset
```

Два различных source offsets — это два различных source observations, пока более высокий semantic projection явно не агрегирует их по своему отдельному contract.

---

# 83. CAPACITY GATE ДО PRODUCTION

SQLite NI-01 обязан пройти отдельный Lab gate с admitted/sanitized representative metadata.

Gate измеряет:

```text
sustained ingest rate

replay ingest rate

DB bytes per normalized event

projected steady-state DB under 14d/30d retention

transaction latency

checkpoint lag

cleanup latency

reader CPU

reader RSS

SQLite WAL growth

concurrent bounded read latency

crash/restart recovery
```

Acceptance требует:

```text
no unbounded growth

no checkpoint corruption

no duplicate observations

no source identity loss

no privacy-retention failure

DB projection comfortably below 8 GiB

no material regression to unrelated project tests
```

Если FAIL:

```text
PRODUCTION HOLD
STORAGE ARCHITECTURE RETURN
```

---

# 84. НИКАКОЙ НОВОЙ EXTERNAL PYTHON DEPENDENCY

Предпочтительная реализация использует:

```text
Python stdlib
sqlite3
json
hashlib
uuid
ipaddress
pathlib
dataclasses
```

Если Coder считает новую external dependency необходимой:

```text
STOP
вернуть dependency rationale Tech Lead
```

Молчаливое добавление пакета запрещено.

---

# 85. CRASH TESTS

Implementation acceptance обязан проверить минимум следующие transaction cuts:

```text
crash before observation insert

crash after observation insert but before transaction commit

crash before checkpoint update

crash after checkpoint update statement but before commit

crash immediately after commit
```

Каждый случай должен сходиться к:

```text
zero loss from committed source bytes
+
zero duplicate semantic observation
```

пока raw source остаётся доступным.

---

# 86. SOURCE-LIFECYCLE TEST MATRIX

Обязательные deterministic tests:

```text
fresh source file

append

reader restart same file

process restart same file

Suricata restart + append continuity

inode replacement

rename/reopen rotation

truncation

copytruncate detection

file disappears

file reappears

host boot_id change

checkpoint offset beyond file size

continuity anchor mismatch

partial final line

malformed complete line

oversized line

duplicate replay

same-identity semantic conflict
```

Ни один case не может опираться на предположение «probably same file».

---

# 87. FAMILY TEST MATRIX

DNS tests должны доказать:

```text
request
response
tx_id
query name/type
rcode
A answer
AAAA answer
CNAME answer
bounds/truncation
no latency
```

TLS tests:

```text
version
SNI present
SNI null
client ALPN
server ALPN
flow relation
```

QUIC tests:

```text
version
SNI present
SNI null/opaque
flow relation
```

Unexpected families должны доказать rejection/non-admission.

---

# 88. NETWORK-SCOPE TESTS

Обязательно:

```text
one endpoint inside 192.168.8.0/22
→ admitted scope

both endpoints inside
→ admitted scope

neither endpoint inside
→ no product observation

IPv6-only
→ unsupported for V1 scope

invalid IP
→ schema fault

wrong capture_source_id/binding
→ no silent admission
```

VLAN field не используется как authority.

---

# 89. RETENTION TESTS

Time-controlled tests должны доказать:

```text
NI-R1 deleted at policy boundary

NI-R2 survives NI-R1 only to its own boundary

health/fault retention independent

closed generation lineage survives observation cleanup

active generation/checkpoint never deleted

no early sensitive-row leak through orphan join

WAL/checkpoint/cleanup remain consistent
```

---

# 90. PRIVACY TESTS

Sentinel values должны доказать отсутствие sensitive values в:

```text
logs

tracebacks

health events

fault details

checkpoint rows

source-generation rows

configuration diagnostics
```

Sensitive values могут находиться только в точных short-retained normalized tables, разрешённых schema.

Raw complete EVE JSON не должен появляться в product DB.

---

# 91. INTERNAL READ TESTS

Доказать:

```text
Site required

bounded window

bounded page <= 500

stable event_at + observation_id ordering

no cross-Site rows

expired NI-R1 not reconstructed

source-health unavailable preserved

no direct consumer SQL contract
```

---

# 92. FINGERPRINT REGRESSION

NI-01 acceptance должен доказать:

```text
Fingerprint schema unchanged

Fingerprint evidence semantics unchanged

Fingerprint writer unchanged

Fingerprint source-health semantics unchanged

Fingerprint API unchanged

Fingerprint classification unchanged
```

NI reader может consume существующий health read boundary, но не становится его owner'ом.

---

# 93. PORTAL REGRESSION

Обязательно подтвердить:

```text
Visitor Auth unchanged

CAPPORT unchanged

OmadaProvider/token lifecycle unchanged

Pending Session Cleaner unchanged

Observation unchanged

Current State unchanged

Visit Lifecycle unchanged

Traffic products unchanged

Admin Settings unchanged
```

Изменение любого из этих semantic owners требует отдельного scope return.

---

# 94. PRODUCTION SOURCE ACTIVATION — ОТДЕЛЬНЫЙ ЭТАП

Merge NI-01 code НЕ разрешает постоянно включать isolated Suricata DTI EVE output.

Production activation требует отдельного reviewed activation step с проверкой:

```text
exact production commit/tree

exact source config

bounded rotation

file permissions

network-metadata service unit

DB/data path ownership

enabled config

resource preflight

rollback

Fingerprint health verification
```

Это новый NI-01 activation reason, а не продолжение NI-00 testing.

NI-00 дополнительных live tests больше не требует.

---

# 95. ROLLBACK PRINCIPLE

Rollback NI-01 code/runtime не должен требовать изменения:

```text
Device Fingerprint DB

Portal DB

Visit DB

Observation DB

Omada configuration
```

Auxiliary runtime и isolated DTI source output отключаются отдельно.

Existing unrelated products продолжают работать.

Network Observation Store можно оставить offline для forensic/rollback inspection; автоматически уничтожать его запрещено.

---

# 96. ЯВНО ЗАПРЕЩЁННАЯ РЕАЛИЗАЦИЯ

```text
NO direct packet capture by NI-01

NO second Python packet sniffer

NO PCAP writer

NO generic raw EVE database

NO Device Fingerprint DB reuse

NO direct Fingerprint SQLite reads

NO IP→MAC attribution

NO MAC→device_id attribution

NO protocol summary product

NO service recognition

NO traffic accounting

NO current-rate calculation

NO flow-family dependency

NO DNS latency

NO Admin UI

NO public API

NO authorization decisions

NO Omada control

NO systemd control from application

NO Suricata restart from application

NO heuristic dedup

NO source-identity repair by guess
```

---

# 97. IMPLEMENTATION LAYOUT — ЛОГИЧЕСКИЙ

Предпочтительная module boundary:

```text
app/network_metadata/
    models
    config
    source
    scope
    normalizer
    repository
    retention
    health
    read_service
    service
    cli
```

Это logical decomposition requirement, а не разрешение на unrelated refactoring.

Tests:

```text
tests/network_metadata/
```

Изменения вне необходимых DTI/deployment/docs boundaries требуют review Tech Lead.

---

# 98. CODER PRE-CODE PLAN — ОБЯЗАТЕЛЕН

До broad implementation Coder обязан вернуть exact PLAN mapping:

```text
architecture clause
→ file/module
→ schema/table
→ test
```

PLAN обязан явно показать:

```text
source-generation state machine

checkpoint atomicity

rotation/reboot handling

conflict handling

sensitive/core retention split

database capacity guard

capture-scope gate

health reuse boundary

zero direct Fingerprint DB access

zero main Portal dependency
```

Tech Lead должен принять PLAN до broad coding.

---

# 99. ACCEPTANCE EVIDENCE

Coder handoff обязан содержать:

```text
baseline commit/tree

candidate commit/tree

targeted NI-01 tests

full project regression suite

compileall

diff-check

SQLite schema/version proof

crash/replay proof

source-generation lifecycle proof

retention proof

privacy sentinel proof

capacity benchmark report

Fingerprint regression proof

Portal/Auth/CAPPORT regression proof

no production action statement
```

Fabricated production evidence запрещён.

---

# 100. STOP CONDITIONS

Implementation немедленно останавливается и возвращается Architect/Tech Lead, если:

```text
accepted source identity нельзя сделать deterministic

rotation требует heuristic file matching

checkpoint и observation commit нельзя сделать atomic

SQLite capacity gate FAIL

required network-scope authority unavailable

implementation требует Device Fingerprint DB writes

implementation требует direct packet capture

raw EVE persistence становится необходимым

raw payload persistence становится необходимым

материально требуется новая external dependency

production Site scope нельзя передать explicit

existing Fingerprint semantics должны измениться

Flow становится обязательным для DNS/TLS/QUIC core

source conflict нельзя surfaced без silent overwrite
```

---

# 101. NI-02 HANDOFF CONTRACT

Выход NI-01 для NI-02:

```text
retained Site-scoped normalized observation

+
retained SensitiveNetworkMetadata endpoint sidecar

+
event_at

+
source/capture provenance

+
source-health / coverage evidence
```

NI-02 отдельно владеет:

```text
Site + IPv4 + event_at
→ authoritative Site + MAC
→ existing device_id where available
```

Ни одна часть этого mapping не реализуется заранее в NI-01.

---

# 102. FINAL ARCHITECTURE INVARIANTS

```text
NI01-I01
Every product observation has deterministic source lineage.

NI01-I02
Source identity = generation + byte offset.

NI01-I03
No heuristic event dedup exists.

NI01-I04
Observation and checkpoint commit atomically.

NI01-I05
Replay cannot duplicate an observation.

NI01-I06
Identity conflict never overwrites evidence.

NI01-I07
Partial final record is never silently accepted.

NI01-I08
Host reboot cannot reuse a /run generation.

NI01-I09
Suricata restart alone does not force generation change.

NI01-I10
Truncation/replacement always forces new generation.

NI01-I11
Out-of-scope events do not become product observations.

NI01-I12
VLAN at VM capture API is not scope authority.

NI01-I13
No IP-only Device identity is created.

NI01-I14
DNS latency is absent.

NI01-I15
TLS/QUIC missing SNI is unknown, not negative evidence.

NI01-I16
Flow is not a NI-01 core dependency.

NI01-I17
STATS is not duplicated.

NI01-I18
Capture health reuses the existing admitted boundary.

NI01-I19
Network Metadata never writes Fingerprint storage.

NI01-I20
Raw EVE JSON is not product-persisted.

NI01-I21
Sensitive endpoint metadata expires after at most 14 days.

NI01-I22
Normalized non-sensitive core expires after at most 30 days.

NI01-I23
Expired attribution dependencies are not reconstructed by guess.

NI01-I24
No HTTP/Admin API is added.

NI01-I25
Auxiliary failure cannot break Portal/Auth/CAPPORT.

NI01-I26
SQLite production acceptance requires capacity PASS.

NI01-I27
No source checkpoint advances without durable normalized/fault outcome.

NI01-I28
No secret or packet/application payload is persisted.

NI01-I29
Current source silence never means no network activity.

NI01-I30
Future consumers use the internal read boundary, not direct SQL.
```

---

# 103. OPEN ARCHITECTURE QUESTIONS

```text
OPEN_P0 = 0

OPEN_P1 = 0
```

Этот contract закрывает оставшиеся implementation dependencies после NI-00:

```text
source_generation identity
= CLOSED

file lifecycle identity
= CLOSED

rotation semantics
= CLOSED

Suricata restart semantics
= CLOSED

host reboot semantics
= CLOSED

checkpoint persistence
= CLOSED

reader restart semantics
= CLOSED

old-generation replay behavior
= CLOSED

partial-final-record behavior
= CLOSED

duplicate delivery behavior
= CLOSED

conflicting identity behavior
= CLOSED

idempotency key construction
= CLOSED

checkpoint invalidation
= CLOSED

/run disappearance across reboot
= CLOSED

sensitive metadata numeric retention
= CLOSED
```

---

# 104. FINAL DISPOSITION

```text
TASK =
DTI-NI-01
METADATA-ONLY NETWORK OBSERVATION FOUNDATION

ARCHITECTURE =
DRAFT FOR TECH LEAD REVIEW

UPSTREAM NI-00 =
PASS / CLOSED

CORE FAMILIES =
DNS
TLS
QUIC

STATS =
REUSE EXISTING SOURCE-HEALTH PATH

FLOW =
NOT IN NI-01 CORE / CONDITIONAL LATER

SOURCE TRANSPORT =
ISOLATED REGULAR NEWLINE-DELIMITED EVE

SOURCE EVENT IDENTITY =
source_generation_id
+
record_start_byte_offset

NETWORK SCOPE =
EXPLICIT CAPTURE SCOPE BINDING
NO VLAN ASSUMPTION

DEVICE ATTRIBUTION =
NO / NI-02

STORAGE =
SEPARATE NETWORK OBSERVATION STORE

SQLITE =
NI-01 CANDIDATE
MANDATORY CAPACITY GATE

SENSITIVE RETENTION =
14 DAYS MAX

NORMALIZED CORE RETENTION =
30 DAYS MAX

PAYLOAD / PCAP =
FORBIDDEN

PUBLIC / ADMIN API =
NO

PORTAL/AUTH DEPENDENCY =
NO

PRODUCTION CHANGE =
NO

SYSADMIN ACTION =
NO

CODER =
HOLD

OPEN P0 =
0

OPEN P1 =
0

READY FOR TECH LEAD REVIEW =
YES
```

Следующий governance step:

```text
Tech Lead
→ review TASK-DTI-NI-01 contract
→ PASS или bounded architecture return

только после PASS:
→ exact implementation authorization / Coder gate

до этого:
CODER = HOLD
PRODUCTION = NO CHANGE
```

Ключевой design choice NI-01:

```text
raw EVE НЕ является durable product history.

Raw EVE остаётся transient NI-R0 transport.

Durability начинается только после того,
как complete newline record получила
source_generation + byte offset identity
и была атомарно normalise'на вместе с checkpoint.
```

Это сохраняет separation между Suricata transport и Network Observation Store и даёт последующим NI-02/NI-03 deterministic evidence без replay heuristics.
