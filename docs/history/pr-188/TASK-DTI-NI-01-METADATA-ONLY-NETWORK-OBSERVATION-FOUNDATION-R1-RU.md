# TASK-DTI-NI-01
## METADATA-ONLY NETWORK OBSERVATION FOUNDATION
### АРХИТЕКТУРНЫЙ / IMPLEMENTATION CONTRACT
### R1 FINAL CANDIDATE FOR TECH LEAD REVIEW

**Проект:** CaptivPortal  
**Программа:** DTI — Network Intelligence  
**Задача:** `TASK-DTI-NI-01`  
**Роль:** Architect  
**Статус:** `R1 FINAL CANDIDATE FOR TECH LEAD REVIEW`

---

# 0. AUTHORITY / BASELINE / ТЕКУЩИЙ GATE

Точный repository baseline:

```text
HEAD =
c1167180daec9ca17d13ab44326f143122db8d5e

TREE =
278df41bfa3134b22963b41006585da35de08074
```

Upstream authority:

```text
TASK-DTI-NI-00
= PASS / CLOSED

OPEN_P0 = 0
OPEN_P1 = 0
```

Tech Lead review v0.1:

```text
ARCHITECTURE DIRECTION = PASS
UPSTREAM NI-00 ALIGNMENT = PASS
ROADMAP ALIGNMENT = PASS
SOURCE / NORMALIZATION DIRECTION = PASS
DEVICE-FINGERPRINT ISOLATION = PASS
PRIVACY DIRECTION = PASS

REDESIGN = NO
```

R1 является bounded revision и закрывает:

```text
TL-NI01-R1
...
TL-NI01-R19
```

Ни одно принятое архитектурное направление NI-01 не переоткрывается.

Если `main` изменится до начала Coder PRE-CODE PLAN:

```text
STOP
→ Tech Lead baseline reconciliation
```

Запрещено молча реализовывать этот contract против другого HEAD/TREE.

Текущий gate:

```text
CODER = HOLD
SYSADMIN = NO ACTION
PRODUCTION = NO CHANGE
SYSTEMD = NO ACTION
SURICATA = NO CHANGE
```

---

# 1. ТОЧНЫЙ SCOPE NI-01

NI-01 реализует ровно metadata-only foundation:

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
IngestRunV1

bounded regular-EVE reader
canonical source normalizer
Network Observation Store
idempotent replay
conflict handling
checkpoint recovery
retention / cleanup
layered health
non-sensitive internal read boundary
```

NI-01 НЕ реализует:

```text
FlowProtocolObservationV1 как core dependency
traffic buckets
periodic traffic meter
traffic byte accounting
current traffic rate
Visit traffic slicing

Device attribution
Site+IP → MAC mapping
MAC → device_id
DeviceNetworkMetadataEdgeV1

Device Card
Admin UI
public API

Protocol Summary
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

`FLOW` остаётся conditional / later admission и не блокирует DNS/TLS/QUIC core.

`STATS` переиспользуется через существующий admitted source-health boundary и не дублируется отдельным NI EVE stream.

---

# 2. SOURCE TOPOLOGY

Канонический NI-01 path:

```text
existing production Suricata
        ↓
isolated DTI EVE output
        ↓
regular newline-delimited EVE JSON file
        ↓
network-metadata auxiliary reader
        ↓
normalization / scope gate
        ↓
Network Observation Store
```

Логический source ID:

```text
suricata-dti-ni-v1
```

Канонический V1 source path:

```text
/run/fingerprint-suricata/dti-ni-v1.eve.json
```

Изолированный DTI output допускает только:

```text
dns

tls

quic
```

Не допускаются в NI-01 source family allowlist:

```text
flow
http
alert
dhcp
other
```

Unexpected family не становится product observation только потому, что Suricata её emitted.

---

# 3. DEVICE FINGERPRINT ISOLATION

Existing Device Fingerprint ownership остаётся неизменным.

NI-01 НЕ ДОЛЖЕН:

```text
писать в Device Fingerprint DB
читать Fingerprint DB прямым SQL
знать Fingerprint table names
изменять Fingerprint schema
изменять Fingerprint evidence semantics
изменять Fingerprint classification
изменять Fingerprint writer
заменять Fingerprint source-health owner
парсить Fingerprint telemetry logs как health authority
```

Постоянно:

```text
Suricata EVE != product database
Suricata EVE != Device Card API
```

Network Metadata Foundation имеет отдельное storage ownership.

---

# 4. PROCESS OWNERSHIP

NI-01 — отдельный auxiliary runtime.

Канонический runtime entrypoint:

```text
python3 -m app.network_metadata.cli run
```

Каноническая target service identity:

```text
network-metadata.service
```

Это target identity, а не разрешение на systemd action.

Failure isolation:

```text
network-metadata unavailable
!= Portal unavailable

network-metadata unavailable
!= CAPPORT unavailable

network-metadata unavailable
!= Authorization unavailable

network-metadata unavailable
!= Device Fingerprint unavailable
```

`captive-portal.service` не является writer'ом Network Observation Store.

---

# 5. SOURCE RECORD IDENTITY

Принятый V1 primitive:

```text
source_generation_id
+
record_start_byte_offset
```

Канонический object:

```text
SourceRecordIdentityV1 {
    source_generation_id
    record_start_byte_offset
}
```

Каноническая строка:

```text
suricata-eve-v1:<source_generation_uuid>:<decimal_start_offset>
```

Она является `source_event_identity`.

Запрещено использовать вместо неё:

```text
content hash alone
flow_id alone
transaction_id alone
event_at alone
arrival time
DNS name + time
endpoint + time
```

---

# 6. SOURCE GENERATION — EXACT CONTRACT

`source_generation_id`:

```text
UUIDv4
```

Он создаётся reader'ом для одного непрерывного byte-address namespace admitted source file/binding epoch.

`SourceGenerationV1` содержит минимум:

```text
source_generation_id
logical_source_id
host_boot_id
st_dev
st_ino

generation_start_offset
committed_byte_offset
end_offset nullable

capture_scope_binding_schema_version
capture_scope_binding_digest
binding_valid_from_utc

opened_at_utc
closed_at_utc nullable
close_reason nullable
coverage_gap_possible
```

`source_generation_id` НЕ является:

```text
content hash
Suricata PID
arrival timestamp
inode
filename
binding digest
```

---

# 7. FILE CONTINUITY PROOF

Для restart/resume reader хранит:

```text
host_boot_id
st_dev
st_ino
committed_byte_offset

continuity_anchor_start_offset
continuity_anchor_length
continuity_anchor_sha256
```

Anchor покрывает максимум последние 4096 committed source bytes непосредственно перед durable checkpoint.

Anchor используется только как bounded continuity guard.

Raw anchor bytes не сохраняются.

Предыдущая generation может быть продолжена только когда одновременно:

```text
logical source тот же
host_boot_id тот же
st_dev тот же
st_ino тот же
current file size >= committed_byte_offset
continuity anchor совпадает
```

Тогда reader продолжает с:

```text
committed_byte_offset
```

Иначе требуется новая source generation.

---

# 8. BINDING-EPOCH CHANGE НА ТОМ ЖЕ PHYSICAL FILE

Если `CaptureScopeBindingV1` намеренно меняется, а тот же physical source file продолжает существовать:

## OLD GENERATION

```text
end_offset = current durable committed_byte_offset
close_reason = capture_scope_binding_changed
```

## NEW GENERATION

Тот же physical file разрешено продолжить только после continuity proof PASS.

```text
generation_start_offset =
old_generation.end_offset

first readable offset =
generation_start_offset
```

Запрещено:

```text
rewind to offset 0
reinterpret already-consumed bytes under new binding
```

Для genuinely new / replaced / truncated file:

```text
generation_start_offset = 0
```

Постоянный invariant:

```text
один source byte range
никогда не интерпретируется
под двумя разными binding epochs
```

---

# 9. `CaptureScopeBindingV1.valid_from_utc`

`valid_from_utc` имеет обязательную semantic meaning.

Если:

```text
event_at < binding.valid_from_utc
```

результат:

```text
PRE_BINDING_EVENT
```

Такой record:

```text
НЕ создаёт normalized product observation
НЕ сохраняет sensitive DNS/SNI/IP values
МОЖЕТ увеличивать bounded source/coverage counters
МОЖЕТ быть checkpoint-consumed после durable outcome
```

Исторические source bytes не переинтерпретируются как принадлежащие binding, который ещё не был valid.

Каждый `SourceGenerationV1` pin'ит:

```text
capture_scope_binding_digest
binding_valid_from_utc
generation_start_offset
```

---

# 10. BINDING PROVENANCE — ТОЧНЫЕ FIELD NAMES

Ambiguous field:

```text
capture_scope_binding_version
```

в V1 запрещён.

`NetworkMetadataEnvelopeV1` использует два отдельных поля:

```text
capture_scope_binding_schema_version = 1
capture_scope_binding_digest = <64-char lowercase SHA-256 hex>
```

Первое — schema identity.

Второе — immutable content identity конкретного binding instance.

Каждое persisted observation обязано указывать точный binding content, использованный для scope decision.

---

# 11. HOST REBOOT / `/run` LOSS

Поскольку source расположен под `/run`, смена `host_boot_id` всегда завершает старую generation.

```text
old boot_id = A
host reboot
new boot_id = B
        ↓
old generation cannot continue
        ↓
close_reason = host_reboot_source_lost
coverage_gap_possible = true
        ↓
wait for source
        ↓
new source file
        ↓
new source_generation_id
```

Исчезнувшие bytes не реконструируются.

Gap не заполняется fabricated observations.

---

# 12. ROTATION POLICY

Production V1 допускает только:

```text
rename / replace / reopen
```

Production V1 НЕ допускает:

```text
copytruncate
```

как accepted rotation strategy.

Если running reader наблюдает shrink/copytruncate:

```text
close old generation
close_reason = observed_truncation
coverage_gap_possible = true
new generation
```

Reader может detect:

```text
observed shrink
anchor mismatch
inode replacement
```

но НЕ заявляет невозможную гарантию perfect offline copytruncate detection, если reader не работал.

Production activation обязана отдельно доказать producer rotation model:

```text
rename / replace / reopen
```

NI reader сам НЕ имеет authority на:

```text
signal Suricata
restart Suricata
truncate EVE
rotate EVE
rewrite Suricata config
```

---

# 13. LIVE ROTATION

Если canonical path уже указывает на новый file, но old descriptor всё ещё открыт:

```text
1. old generation → closing
2. дочитать old descriptor до final complete newline record
3. durable final checkpoint
4. close old generation
5. открыть current canonical path
6. new generation
7. generation_start_offset = 0
```

Два physical files никогда не объединяются в один byte-offset namespace.

---

# 14. ROTATION WHILE READER DOWN

V1 не выполняет heuristic directory archaeology.

Если при restart:

```text
stored file identity
!=
current canonical file identity
```

то:

```text
old generation close_reason = source_replaced_while_reader_down
coverage_gap_possible = true
new generation starts at offset 0
```

Rotated-away historical EVE автоматически не импортируются.

Raw EVE остаётся NI-R0 transient transport, а не product history.

---

# 15. CANONICAL JSON V1

Для `binding_digest`, `configuration_digest`, `semantic_payload_sha256` и UUIDv5 name используется единый `Ni01CanonicalJsonV1`.

Exact semantics:

```text
JSON-compatible normalized values only
object keys = strings only
UTF-8
sort_keys = true
separators = (",", ":")
ensure_ascii = false
allow_nan = false
floats = forbidden in NI-01 semantic canonical objects
no locale-dependent formatting
no unordered-set serialization
no implicit Unicode normalization
```

Equivalent Python serialization semantics:

```text
json.dumps(
    value,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
)
.encode("utf-8")
```

Semantically ordered lists сохраняют contract-defined order.

Semantically unordered collections сначала canonicalize'ятся, затем сортируются детерминированно до hashing.

Для CIDRs:

```text
parse strict IPv4 network
canonical network string
sort by (integer network address, prefix length)
```

Duplicate CIDRs rejected до hashing.

SHA-256 representation:

```text
lowercase hexadecimal
exactly 64 ASCII characters
```

---

# 16. UUID CONTRACT

```text
source_generation_id = UUIDv4

ingest_run_id = UUIDv4
```

Фиксированный namespace для `observation_id`:

```text
NI01_OBSERVATION_NAMESPACE_UUID =
ce2387da-5bc4-5c4e-9e6a-6de970889764
```

`observation_id`:

```text
UUIDv5(
    ce2387da-5bc4-5c4e-9e6a-6de970889764,
    Ni01CanonicalJsonV1({
        "family": <dns|tls|quic>,
        "schema_version": 1,
        "source_event_identity": <canonical source identity>
    }).decode("utf-8")
)
```

Coder НЕ генерирует namespace UUID сам.

---

# 17. RAW / SEMANTIC DIGESTS

Для successfully parsed complete source record:

```text
source_record_sha256 =
SHA-256(exact source bytes excluding terminating newline)
```

Для successfully normalized observation:

```text
semantic_payload_sha256 =
SHA-256(Ni01CanonicalJsonV1(normalized semantic payload))
```

Semantic payload digest включает semantic facts observation и sensitive values, пока они присутствуют.

Он НЕ включает:

```text
observation_id
ingested_at
health_id
ingest_run_id
source_record_sha256
semantic_payload_sha256
runtime counters
mutable operational status
```

---

# 18. DUPLICATE / CONFLICT MATRIX

## CASE A — exact duplicate

```text
same source_event_identity
+
same source_record_sha256
+
same semantic_payload_sha256
→ DUPLICATE_NOOP
```

Existing evidence immutable.

No second observation.

Original `ingested_at` сохраняется.

## CASE B — raw identity conflict

```text
same source_event_identity
+
DIFFERENT source_record_sha256
→ SOURCE_RECORD_IDENTITY_CONFLICT
```

Это conflict даже если normalized semantic payload случайно одинаков.

## CASE C — normalizer determinism conflict

```text
same source_event_identity
+
same source_record_sha256
+
DIFFERENT semantic_payload_sha256
→ NORMALIZER_DETERMINISM_CONFLICT
```

## CASE D — replay после expiry digest evidence

Если source identity уже существует, но required retained digest был удалён по privacy retention:

```text
→ REPLAY_IDENTITY_EVIDENCE_EXPIRED
→ fail closed for that generation
```

V1 НЕ имеет права угадать duplicate/conflict после утраты требуемого digest evidence.

Для CASE B/C/D:

```text
existing evidence immutable
conflicting/replayed replacement not inserted
bounded durable fault recorded
checkpoint does not advance past the record
metadata_ingest_health = unavailable
generation processing pauses
```

Запрещены:

```text
first-writer-wins
last-writer-wins
semantic-equivalence excuse for changed raw bytes
heuristic repair
```

---

# 19. CHECKPOINT ATOMICITY

Одна ingest SQLite write transaction атомарно commit'ит:

```text
accepted source-record state where required
normalized observation
family-specific rows
sensitive rows
required health/fault transition or aggregate update
checkpoint advancement
```

Только после commit существует новый:

```text
committed_byte_offset
```

Crash before commit:

```text
same source bytes replay
→ deterministic duplicate/new processing
```

Crash after commit:

```text
resume after committed offset
```

Canonical checkpoint хранится только в Network Observation Store.

Отдельный checkpoint file не является authoritative.

---

# 20. PARTIAL FINAL RECORD

Complete source record существует только после terminating newline.

```text
bytes after last newline
+
no terminating newline
→ PARTIAL
```

Пока generation active:

```text
wait
no parse
no checkpoint
```

Если generation окончательно закрывается и newline так и не появился:

```text
partial_final_record fault aggregate/update
```

Разрешено хранить только:

```text
source_generation_id
offset
byte_length
non-sensitive fault metadata
```

Raw bytes не сохраняются.

Digest такой partial raw tail не получает long-lived persistence.

---

# 21. MALFORMED COMPLETE RECORD

Newline-terminated record с:

```text
invalid UTF-8
invalid JSON
non-object JSON
schema failure
resource/field bound failure
```

даёт bounded fault outcome.

Raw record body не сохраняется.

Record считается consumed, и checkpoint может продвинуться после durable fault aggregate update.

Один malformed record не wedge'ит ingest навсегда.

`metadata_ingest_health` становится минимум `partial`.

---

# 22. SOURCE RECORD HARD LIMIT

Architecture hard ceiling:

```text
1048576 bytes
= 1 MiB
```

Newline-terminated record выше effective configured limit:

```text
no parse
no normalize
no raw persistence
resource_limit fault
checkpoint may advance after durable bounded fault outcome
```

Unterminated over-limit tail не вызывает unbounded memory buffering.

---

# 23. BATCH BOUNDS

Architecture hard ceilings:

```text
records per transaction <= 256
source bytes per transaction <= 1048576
```

Default poll interval:

```text
1 second
```

Это ingest cadence, а не Device Card polling contract.

---

# 24. CAPTURE SCOPE BINDING — GENERIC FOUNDATION

`CaptureScopeBindingV1` содержит ровно:

```text
schema_version = 1
capture_source_id
site_id
network_scope_id
ipv4_cidrs[]
valid_from_utc
binding_digest
```

Repository НЕ hardcode'ит:

```text
zefer-span-01
192.168.8.0/22
конкретный production Site ID
Home
SSID
```

Generic validator требует:

```text
explicit capture_source_id
explicit canonical site_id
explicit network_scope_id
1..16 IPv4 CIDRs
strict canonical IPv4 network syntax
no duplicates
no overlaps
IPv6 authority absent in V1
valid_from_utc required
```

Deployment activation отдельно доказывает текущий Zefer binding.

---

# 25. EXACT CAPTURE-SCOPE CONFIG TRANSPORT

Ровно один process/environment input:

```text
NETWORK_METADATA_CAPTURE_SCOPE_BINDING_JSON
```

Он содержит один strict JSON object.

Exact object fields:

```json
{
  "schema_version": 1,
  "capture_source_id": "<explicit id>",
  "site_id": "<explicit canonical Site ID>",
  "network_scope_id": "<explicit id>",
  "ipv4_cidrs": ["<canonical IPv4 CIDR>", "..."],
  "valid_from_utc": "<RFC3339 timezone-aware timestamp>"
}
```

Parser requirements:

```text
top-level object only
unknown fields rejected
missing fields rejected
duplicate object members rejected
NaN / Infinity / -Infinity rejected
site_id validated by existing canonical Site validator
capture_source_id validated by existing canonical machine-id validator
network_scope_id length 1..64 UTF-8 bytes and ASCII syntax [A-Za-z0-9][A-Za-z0-9._:-]*
CIDRs strict-canonicalized deterministically
CIDR count <= 16
no CIDR duplicates
no CIDR overlaps
no implicit Site/default Site
no Home inference
no SSID inference
```

`binding_digest` в input не передаётся — он вычисляется локально по canonical semantic content без самого digest field.

---

# 26. NETWORK SCOPE GATE

Для IPv4 event:

```text
at least one src/dst endpoint
belongs to admitted binding.ipv4_cidrs
→ eligible for product observation normalization
```

Если ни один endpoint не входит в intended scope:

```text
OUTSIDE_INTENDED_SCOPE
→ no product observation
→ no sensitive DNS/SNI/IP persistence
→ bounded counters only
```

VLAN field на VM capture API не является authority.

---

# 27. IPV6

V1 не имеет admitted IPv6 binding authority.

IPv6-only source event:

```text
UNSUPPORTED_ADDRESS_FAMILY_FOR_SCOPE
→ no normalized product observation
```

Никакого IPv4 identity borrowing.

IPv6 не блокирует IPv4 NI-01.

---

# 28. NO DEVICE ATTRIBUTION

NI-01 заканчивается на:

```text
Site-scoped normalized network observation
```

Не выполняются:

```text
IP → MAC
MAC → device_id
Device direction normalization
Device-relative peer projection
```

Это ownership NI-02.

---

# 29. `NetworkMetadataEnvelopeV1`

Canonical fields:

```text
observation_id
schema_version = 1

source_type = suricata
source_contract_version = suricata-eve-v1
source_event_family
source_event_identity
source_generation_id
record_start_byte_offset

capture_source_id
capture_scope_binding_schema_version = 1
capture_scope_binding_digest
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

sensitive_endpoint_presence_state
```

`source_record_sha256` и `semantic_payload_sha256` не являются 30/90-day provenance fields; их privacy lifetime отдельно ограничен ниже.

---

# 30. `ingested_at` — IMPLEMENTABLE SEMANTICS

`ingested_at` означает:

```text
UTC timestamp,
назначенный внутри первой accepted ingest transaction
и durable committed атомарно вместе с source record/observation
```

Replay сохраняет original `ingested_at`.

Это НЕ post-commit completion timestamp.

Post-commit timing, если нужен telemetry, является отдельной operational metric и не частью observation identity.

---

# 31. SENSITIVE ENDPOINT SIDECAR

`NetworkMetadataSensitiveEndpointV1` хранит short-retained values:

```text
observation_id
src_ip nullable
dst_ip nullable
src_port nullable
dst_port nullable
transport_protocol nullable
```

Longer-lived core хранит:

```text
sensitive_endpoint_presence_state
```

Exact enum:

```text
observed_retained
not_observed
expired
```

---

# 32. RETENTION-PRESENCE SEMANTICS

Для sensitive values V1 обязательно различает:

```text
observed_retained
not_observed
expired
```

Meaning:

```text
observed_retained
= source value был observed и его admitted sensitive value ещё retained

not_observed
= source event изначально не дал admitted value

expired
= value был observed/persisted, но удалён retention policy
```

Это обязательно минимум для:

```text
TLS SNI
QUIC SNI
DNS query names
DNS retained answer values / CNAME values
sensitive endpoint tuple
```

Retention cleanup атомарно:

```text
delete sensitive value rows
+
change longer-lived presence state:
observed_retained → expired
```

Запрещено:

```text
expired SNI → ordinary null
expired DNS names → ordinary empty list
expired endpoints → not_observed
```

---

# 33. `DnsObservationV1`

One admitted DNS EVE record → one `DnsObservationV1`.

Core fields:

```text
observation_id
dns_version = 3
dns_event_kind = request | response
flow_id
dns_tx_id
dns_wire_id nullable
rcode nullable

query_names_presence_state
answer_values_presence_state

query_count_observed
answer_count_observed
queries_truncated
answers_truncated
```

Sensitive child rows хранят retained values:

```text
DNS query_name + query_type
DNS answer value + answer_type
```

`dns_tx_id` — transaction correlation внутри flow context, не global source identity.

DNS latency в NI-01 отсутствует.

---

# 34. DNS ARRAY BOUNDS

```text
max retained queries per source record = 8
max retained answers per source record = 32
```

Если source array больше:

```text
retain deterministic first N in source order
set *_truncated = true
```

Это единственная разрешённая array truncation для DNS V1.

Individual semantic string никогда не truncates silently.

Retained answer types V1:

```text
A
AAAA
CNAME
```

Другие answer types не persisted как sensitive values в NI-01.

---

# 35. `TlsObservationV1`

Core fields:

```text
observation_id
flow_id nullable
tls_version nullable
sni_presence_state
client_alpns[]
server_alpns[]
client_alpns_truncated
server_alpns_truncated
```

Sensitive sidecar:

```text
SNI value
```

ALPN V1:

```text
max 16 values per side
source order preserved
individual value max 255 UTF-8 bytes
```

Certificate body/chain не сохраняются.

JA4 не превращается в Device/classification claim в NI-01.

`SNI not_observed` не означает `service absent`.

---

# 36. `QuicObservationV1`

Core fields:

```text
observation_id
flow_id nullable
quic_version nullable
sni_presence_state
```

Sensitive sidecar:

```text
SNI value
```

Generic arbitrary:

```text
handshake_metadata_json
```

запрещён.

Missing/opaque QUIC metadata:

```text
UNKNOWN
```

а не negative service evidence.

---

# 37. FIELD TYPE / LENGTH CONTRACT

Ниже hard schema expectations для admitted V1 fields.

## Common timestamp

```text
source JSON type = string
UTF-8 bytes <= 64
timezone required
RFC3339 / ISO-8601 offset form required
fractional seconds = 0..6 digits
normalize to UTC
canonical output = YYYY-MM-DDTHH:MM:SS.ffffffZ
```

Fractional precision > 6 digits:

```text
schema fault
```

Без silent truncation.

## `flow_id`

```text
JSON integer
boolean forbidden
0 <= value <= 18446744073709551615
```

## DNS `dns_tx_id`

```text
JSON integer
boolean forbidden
0 <= value <= 18446744073709551615
```

## DNS wire ID

```text
JSON integer or null
0 <= value <= 65535
```

## IP address

```text
JSON string
UTF-8/ASCII bytes <= 45
must parse via canonical IP parser
canonical textual representation persisted
```

V1 product scope remains IPv4-only.

## Port

```text
JSON integer or null
0 <= value <= 65535
```

## Transport protocol

```text
JSON string
1..16 ASCII bytes
V1 admitted canonical values = TCP | UDP
```

## DNS `query_type`

```text
JSON string
1..32 ASCII bytes
syntax = [A-Za-z0-9_-]+
no silent case rewrite
```

## DNS `rcode`

```text
JSON string or null
1..32 ASCII bytes when non-null
syntax = [A-Za-z0-9_-]+
```

## DNS query name / CNAME / SNI

```text
JSON string
1..253 UTF-8 bytes
NUL forbidden
ASCII control characters U+0000..U+001F and U+007F forbidden
no silent truncation
```

Source spelling/case is retained; NI-01 does not service-normalize names.

## A/AAAA answer

```text
JSON string
must parse as matching IP family
persist canonical IP textual representation
```

## TLS version

```text
JSON string or null
1..32 UTF-8 bytes when non-null
NUL/control characters forbidden
```

## QUIC version

```text
JSON string or null
1..64 ASCII bytes when non-null
syntax = [A-Za-z0-9._:-]+
```

## ALPN

```text
JSON string
1..255 UTF-8 bytes
NUL forbidden
no silent truncation
```

Invalid/over-limit admitted field:

```text
→ schema/resource fault
→ no fabricated normalized value
→ no silent string truncation
```

Array truncation разрешена только там, где contract явно имеет `*_truncated` state.

---

# 38. NETWORK OBSERVATION STORE

Logical owner:

```text
Network Metadata Foundation
```

Physical V1 candidate:

```text
SQLite
```

Canonical target path:

```text
/opt/CaptivePortal/data/network_metadata.sqlite3
```

Это НЕ:

```text
Device Fingerprint DB
Observation DB
Current State DB
Traffic Projection DB
SettingsStore
```

---

# 39. SQLITE DURABILITY

V1 требует:

```text
SQLite WAL
foreign_keys = ON
synchronous = FULL
one logical writer
bounded busy timeout
```

Только Network Metadata writer владеет mutation path.

Ни один generic consumer не выполняет direct SQL.

Exact physical schema/version mechanism, WAL checkpoint policy, busy timeout value, page-growth containment и transaction headroom formula должны быть заморожены в обязательном PRE-CODE PLAN и доказаны capacity tests до broad implementation acceptance.

Это implementation-detail gate, а не открытый architecture question.

---

# 40. SQLITE FOOTPRINT — EXACT DEFINITION

Configured/hard storage ceiling применяется к:

```text
sqlite_footprint_bytes =
size(main database file)
+
size(-wal if present)
+
size(-shm if present)
+
size(-journal if unexpectedly present)
```

То есть WAL не может быть исключён из capacity accounting.

`-shm` считается частью measured/enforced operational footprint, даже если обычно мал.

Hard architecture maximum:

```text
8589934592 bytes
= 8 GiB
```

Если safe transaction headroom не может быть гарантирован:

```text
no new ingest transaction
no checkpoint advance
metadata_ingest_health = unavailable
```

Запрещено:

```text
report only main DB while WAL grows
silent VACUUM/full rewrite in ingest hot path
silent deletion of unexpired evidence to fit cap
```

PRE-CODE PLAN обязан зафиксировать:

```text
schema-version mechanism
WAL checkpoint policy
busy timeout
page/file growth containment
freelist reuse behavior
retention-cleanup/WAL interaction
transaction-over-cap behavior
```

---

# 41. LOGICAL TABLE OWNERSHIP

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
network_metadata_ingest_fault_aggregates
```

Exact SQL/indexes — PRE-CODE PLAN.

Semantic ownership выше — mandatory.

---

# 42. SOURCE-RECORD UNIQUENESS

Hard uniqueness:

```text
(source_generation_id, record_start_byte_offset)
```

No silent replacement.

Successful family observation имеет deterministic one-source-record ownership.

---

# 43. INGEST RUN PROVENANCE

`IngestRunV1`:

```text
ingest_run_id = UUIDv4
started_at_utc
repository_head
repository_tree
normalizer_version
configuration_digest
```

`configuration_digest` = SHA-256 `Ni01CanonicalJsonV1` validated safe NI config.

Он включает exact binding semantic content/digest.

Secrets в NI-01 config отсутствуют.

Observations reference `ingest_run_id`.

Смена code build не переписывает старые rows.

---

# 44. DIGEST PRIVACY CLASS

`source_record_sha256` и `semantic_payload_sha256` являются:

```text
SensitiveDerivedNetworkMetadata
NI-R1
```

Потому что они derived из raw records / semantic content, содержащих DNS names, SNI и endpoint data.

Maximum persistence:

```text
14 days
```

Они НЕ наследуют 90-day generation/provenance retention.

После NI-R1 expiry:

```text
digest values removed/nullified
source_record digest_state = expired
```

Длиннее могут жить только non-sensitive identity/provenance fields.

---

# 45. SOURCE-RECORD STATE RETENTION

`network_metadata_source_records` имеет две semantic части.

## Identity spine

Может содержать:

```text
source_generation_id
record_start_byte_offset
record_end_byte_offset
record_byte_length
source_event_family
outcome_code
observation_id nullable
ingested_at
digest_state
```

Для successfully normalized observation identity spine живёт не дольше associated NI-R2 observation:

```text
30 days max
```

Для fault-only records НЕ создаётся unbounded one-row-per-fault history; repeated faults живут только как bounded aggregates.

## Sensitive digests

```text
source_record_sha256
semantic_payload_sha256
```

живут максимум:

```text
14 days
```

После 14 дней digest fields удалены/nullified, `digest_state=expired`.

После 30 дней observation + associated source-record identity spine удаляются согласно FK-safe cleanup.

`SourceGenerationV1` non-sensitive lineage может жить 90 дней после generation closure независимо от source-record deletion.

Active checkpoint никогда не зависит от retention of old per-record digest rows.

Если replay требует уже expired digest evidence:

```text
REPLAY_IDENTITY_EVIDENCE_EXPIRED
→ fail closed
```

---

# 46. RETENTION POLICY

```text
NI-R0 raw EVE transport
= no product retention

NI-R1 sensitive values + sensitive digests
= 14 days max

NI-R2 non-sensitive normalized core
= 30 days max

NetworkMetadataSourceHealthV1
= 45 days max

fault aggregates / quality evidence
= 45 days max

closed source generation / ingest provenance lineage
= 90 days max after generation closure
```

Active generation и active checkpoint retention cleanup не удаляет.

---

# 47. RETENTION CLOCK

Для observation-linked retained data expiry наступает, если выполняется хотя бы одно:

```text
event_at < now - retention
OR
ingested_at < now - retention
```

Это не позволяет late old event расширить privacy lifetime.

Для generation/provenance retention clock начинается от:

```text
closed_at_utc
```

Для active generation retention clock не применяется.

---

# 48. RETENTION FK / CASCADE INVARIANTS

Cleanup НЕ ДОЛЖЕН:

```text
ломать active checkpoint
удалять active generation
уничтожать evidence, необходимое для deterministic current recovery
оставлять orphan family rows
оставлять orphan sensitive rows
оставлять FK-invalid source_health_ref
```

Поскольку health retention 45d > core observation 30d, referenced health не должен истекать раньше observation по normal policy.

Exact physical delete/cascade ordering фиксируется PRE-CODE PLAN.

---

# 49. SOURCE HEALTH MODEL

`NetworkMetadataSourceHealthV1` содержит:

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

Health enum:

```text
usable
partial
stale
unavailable
unknown
```

`unknown` не является healthy.

---

# 50. HEALTH SNAPSHOT CARDINALITY

Health snapshots immutable.

Новый durable health row создаётся только при:

```text
health state/reason transition
source generation transition
periodic heartbeat
```

Exact heartbeat interval:

```text
NETWORK_METADATA_HEALTH_HEARTBEAT_SECONDS = 60
```

При отсутствии transition:

```text
не более одной heartbeat row на 60 секунд
```

При transition row создаётся немедленно, даже если предыдущий heartbeat был меньше 60 секунд назад.

Normal observations ссылаются на latest immutable `health_id`.

Запрещено:

```text
one health row per observation
```

---

# 51. FAULT AGGREGATION CARDINALITY

Repeated ingest faults не создают unbounded row-per-event storage.

Aggregation window:

```text
NETWORK_METADATA_FAULT_AGGREGATION_WINDOW_SECONDS = 300
```

Durable aggregate identity:

```text
logical_source_id
source_generation_id nullable
fault_category
aggregation_epoch_start_utc
```

Где epoch = UTC five-minute bucket.

Aggregate содержит минимум:

```text
count
first_seen_utc
last_seen_utc
first_relevant_offset nullable
last_relevant_offset nullable
```

Без raw sensitive value.

Conflict faults могут немедленно transition'ить health to `unavailable`, но durable fault storage всё равно bounded aggregate.

---

# 52. CAPTURE HEALTH REUSE BOUNDARY

NI-01 использует существующий Python read-service boundary:

```text
app.device_fingerprint.read_service.DeviceFingerprintReadService.latest_source_health(...)
```

через отдельный NI adapter/projection boundary:

```text
FingerprintCaptureHealthAdapterV1
```

Архитектурный path:

```text
DeviceFingerprintReadService.latest_source_health(...)
        ↓
FingerprintCaptureHealthAdapterV1
        ↓
NI capture_health
```

Запрещено:

```text
Fingerprint telemetry log parsing
Fingerprint direct SQLite SQL
Fingerprint writer access
Fingerprint table-name dependency in NI core
second capture-health owner
```

Exact existing source_kind→capture_health mapping должен быть указан Coder в PRE-CODE PLAN только на основании current admitted Device Fingerprint source-health semantics.

Если trustworthy projection невозможна:

```text
capture_health = unknown / unavailable
```

а не optimistic `usable`.

---

# 53. METADATA OUTPUT HEALTH

`metadata_output_health` описывает только isolated DTI EVE delivery.

Примеры:

```text
current valid source file + no lifecycle fault
→ usable

bounded malformed/unexpected records while ingest continues
→ partial

source path absent
→ unavailable

identity conflict
→ unavailable
```

Silence сама по себе НЕ доказывает failure и НЕ доказывает отсутствие network activity.

---

# 54. METADATA INGEST HEALTH

`metadata_ingest_health` описывает:

```text
reader
normalizer
SQLite
checkpoint
conflict state
capacity state
```

Примеры:

```text
normal processing → usable
bounded malformed records → partial
database unavailable → unavailable
capacity hard stop → unavailable
source identity conflict → unavailable
state cannot be established → unknown
```

---

# 55. SOURCE ABSENT AT START

Auxiliary runtime не restart-loop'ится только из-за отсутствия `/run` source file.

```text
service starts
DB/readiness available
source absent
→ metadata_output_health = unavailable
→ bounded wait/retry
```

Когда source появляется:

```text
full generation identity decision
→ ingest
```

Portal/Auth/Fingerprint unaffected.

---

# 56. SOURCE DISAPPEARS WHILE RUNNING

```text
no fabricated EOF success
no identity reuse by guess
classify/close generation where applicable
metadata_output_health = unavailable
wait for source
on reappearance → full identity decision
```

---

# 57. DATABASE FAILURE / CAPACITY FAILURE

При DB unavailable/corrupt/capacity stop:

```text
checkpoint does not advance
no successful in-memory ingest claim
metadata_ingest_health = unavailable
normalization writes stop
```

Нет fallback DB.

Нет Fingerprint DB fallback.

Нет silent deletion of unexpired data.

---

# 58. CONFIGURATION BOUNDARY

NI-01 config остаётся process/environment controlled.

Не входит в Admin Settings этого task.

Canonical inputs:

```text
NETWORK_METADATA_ENABLED=false

NETWORK_METADATA_SOURCE_PATH=
/run/fingerprint-suricata/dti-ni-v1.eve.json

NETWORK_METADATA_DB_PATH=
/opt/CaptivePortal/data/network_metadata.sqlite3

NETWORK_METADATA_CAPTURE_SCOPE_BINDING_JSON=<strict JSON>

NETWORK_METADATA_MAX_DB_BYTES=8589934592
NETWORK_METADATA_MAX_RECORD_BYTES=1048576
NETWORK_METADATA_BATCH_MAX_RECORDS=256
NETWORK_METADATA_BATCH_MAX_BYTES=1048576
NETWORK_METADATA_POLL_INTERVAL_SECONDS=1
```

Disabled means:

```text
no source-file open
no Network Metadata DB creation
no background loop
no Suricata interaction
```

Merge code != production activation.

---

# 59. CONFIGURABLE LIMITS МОГУТ ТОЛЬКО УЖЕСТОЧАТЬ HARD CEILINGS

Validation обязательно обеспечивает:

```text
0 < NETWORK_METADATA_MAX_DB_BYTES <= 8589934592

0 < NETWORK_METADATA_MAX_RECORD_BYTES <= 1048576

1 <= NETWORK_METADATA_BATCH_MAX_RECORDS <= 256

0 < NETWORK_METADATA_BATCH_MAX_BYTES <= 1048576

NETWORK_METADATA_BATCH_MAX_BYTES >= NETWORK_METADATA_MAX_RECORD_BYTES

NETWORK_METADATA_POLL_INTERVAL_SECONDS >= 1
```

Environment может уменьшить resource ceilings.

Environment не может расширить architecture hard ceilings.

Exact lower implementation minima, кроме указанных positive/relational constraints, Coder фиксирует в PRE-CODE PLAN и доказывает tests; они не могут менять hard maxima.

---

# 60. CONFIG VALIDATION

При `NETWORK_METADATA_ENABLED=true` обязательно:

```text
absolute source path
absolute DB path
source path != DB path
strict capture-scope JSON
explicit Site
explicit capture source
explicit network scope
1..16 non-overlapping canonical IPv4 CIDRs
IPv6 authority absent
valid_from_utc valid
positive bounded technical limits
```

Invalid auxiliary config:

```text
network-metadata runtime fails closed
```

Но:

```text
main Portal/Auth/CAPPORT remain isolated
```

---

# 61. GENERIC FOUNDATION — NO CURRENT GUEST CIDR CONSTANT

Repository validator НЕ требует universal:

```text
192.168.8.0/22
```

Current production deployment gate отдельно подтверждает exact intended deployment binding, включая current Zefer CIDR.

Это deployment evidence, не repository invariant.

---

# 62. RAW PAYLOAD / PRIVACY PROHIBITIONS

Постоянно запрещено durable persist:

```text
packet payload
PCAP
HTTP content
TLS application content
full arbitrary EVE JSON
request/response body
credentials
cookies
authorization headers
```

Routine logs НЕ содержат:

```text
DNS query names
SNI
remote IP
endpoint tuple
raw EVE JSON
source record bytes
```

Разрешены routine identifiers/counters:

```text
source_generation_id
offset
observation_id
family
reason code
counts
health state
capacity state
```

---

# 63. INTERNAL READ BOUNDARY — OPTION A

NI-01 выбирает минимальный вариант:

```text
OPTION A
```

Обычный:

```text
NetworkMetadataReadService
```

экспонирует только non-sensitive normalized observations и health/provenance-safe data.

В NI-01 НЕТ:

```text
include_sensitive=true
sensitive=true
raw=true
```

или аналогичного generic escape hatch.

Dedicated attribution-only sensitive read boundary НЕ создаётся в NI-01.

Он может быть добавлен только в NI-02 exact contract, где будут заморожены:

```text
explicit site_id
bounded event-time window
exact attribution-required fields
page bounds
no raw EVE
no generic reader use
```

---

# 64. NON-SENSITIVE READ SERVICE

`NetworkMetadataReadService` owns:

```text
Site validation
event-time windows
family filters
stable ordering
bounded pagination
retention visibility
source-health projection
```

Canonical ordering:

```text
event_at ASC
observation_id ASC
```

Maximum page size:

```text
500
```

No unbounded history read.

No direct consumer SQL.

No Device attribution logic.

---

# 65. LATE DELIVERY

NI-01 сохраняет `event_at` отдельно от `ingested_at`.

Late arrival не изменяет semantic event time.

NI-01 НЕ присваивает product states:

```text
fresh
recent
stale
```

Это later NI-03 product contract.

---

# 66. SOURCE HEALTH REFERENCE

Каждое successful normalized observation references latest immutable NI health snapshot valid for its first ingest transaction.

Если trustworthy health unavailable:

```text
reference explicit unknown/unavailable health snapshot
```

Не разрешено отсутствие health ref трактовать как healthy.

---

# 67. MISSING METADATA SEMANTICS

```text
TLS SNI not_observed
!= no service

QUIC SNI not_observed
!= no service

SNI expired
!= SNI was never observed

no DNS observation
!= no DNS/network activity

source unavailable
!= no protocol activity
```

---

# 68. SCHEMA VERSIONING

Initial semantic schemas:

```text
NetworkMetadataEnvelopeV1 = 1
DnsObservationV1 = 1
TlsObservationV1 = 1
QuicObservationV1 = 1
NetworkMetadataSourceHealthV1 = 1
CaptureScopeBindingV1 = 1
```

Incompatible semantics require explicit new schema version.

Nearest-version parsing запрещён.

Unknown newer DB schema:

```text
writer does not start
```

No automatic destructive reinitialize.

---

# 69. RETENTION CLEANUP

Writer-owned cleanup выполняется:

```text
at startup
+
no more frequently than once per hour during normal runtime
```

Delete batches bounded.

Cleanup:

```text
does not run from read service
does not change source identity
does not move checkpoint backward
does not delete active generation/checkpoint
```

No `VACUUM` in hot ingest path.

---

# 70. PRODUCTION SOURCE OUTPUT SIZE

Producer-owned rotation policy должна удерживать active DTI source transport ниже accepted safety ceiling:

```text
128 MiB
= 134217728 bytes
```

Reader не является rotation owner.

Production activation доказывает exact rotation config отдельно.

---

# 71. SQLITE CAPACITY GATE

До production eligibility SQLite V1 обязан пройти Lab capacity gate.

Измерить минимум:

```text
sustained ingest rate
replay ingest rate
DB bytes per normalized event
combined sqlite footprint main+WAL+SHM
projected steady-state under 14d/30d retention
transaction latency
checkpoint lag
cleanup latency
reader CPU
reader RSS
WAL growth/checkpoint behavior
bounded concurrent read latency
crash/restart recovery
```

PASS требует:

```text
no unbounded growth
no checkpoint corruption
no duplicate observations
no source identity loss
no privacy retention failure
combined footprint comfortably below configured/hard cap
no material directly affected regression
```

FAIL:

```text
PRODUCTION HOLD
STORAGE ARCHITECTURE RETURN
```

No silent DB-engine substitution.

---

# 72. NO NEW EXTERNAL PYTHON DEPENDENCY BY DEFAULT

Preferred:

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

Если новая external dependency materially required:

```text
STOP
→ return rationale to Tech Lead
```

---

# 73. SOURCE-LIFECYCLE TEST MATRIX

Mandatory deterministic tests:

```text
fresh source file
append
reader restart same file
process restart same file
Suricata restart + valid append continuity
binding change on same physical file at non-zero offset
binding valid_from pre-event filtering
inode replacement
rename/reopen rotation
observed truncation
copytruncate rejected as production model
file disappears
file reappears
host boot_id change
checkpoint offset beyond file size
continuity anchor mismatch
partial final line
malformed complete line
oversized line
exact duplicate replay
raw source identity conflict
normalizer determinism conflict
replay with expired digest evidence
```

---

# 74. CRASH TEST MATRIX

Минимальные transaction cuts:

```text
crash before observation insert
crash after observation insert before commit
crash before checkpoint update
crash after checkpoint update statement before commit
crash immediately after commit
```

Expected convergence:

```text
zero duplicate durable semantic observation
+
no checkpoint beyond uncommitted outcome
```

в пределах availability raw source bytes.

---

# 75. FAMILY TEST MATRIX

DNS:

```text
request
response
flow_id
tx_id
wire id
query name/type
rcode
A
AAAA
CNAME
query bound/truncation
answer bound/truncation
presence states
no latency
```

TLS:

```text
version
SNI retained
SNI not_observed
SNI expired
client ALPN
server ALPN
ALPN bounds/truncation state
flow relation
```

QUIC:

```text
version
SNI retained
SNI not_observed/opaque
SNI expired
flow relation
```

Unexpected family:

```text
no observation
bounded fault/counter
```

---

# 76. NETWORK-SCOPE TESTS

Generic tests используют synthetic/configured CIDRs, а не hardcoded production subnet.

Обязательно:

```text
one endpoint inside configured IPv4 scope → admitted
both endpoints inside → admitted
neither endpoint inside → no product observation
PRE_BINDING_EVENT → no product observation
IPv6-only → unsupported V1 scope
invalid IP → schema fault
duplicate CIDR → config reject
overlapping CIDRs → config reject
17 CIDRs → config reject
wrong binding digest/generation relationship → fail closed
```

Separate deployment activation test проверяет current Zefer binding.

---

# 77. RETENTION TESTS

Time-controlled proof:

```text
sensitive value observed_retained before expiry
sensitive value → expired at NI-R1 boundary
not_observed remains distinguishable from expired
sensitive digests expire by 14d
core observation survives only to 30d
health/fault retention independent
closed generation lineage survives to its own boundary
active generation/checkpoint never deleted
no orphan family/sensitive rows
no FK-invalid source_health_ref
replay after digest expiry fails closed
```

---

# 78. PRIVACY TESTS

Sentinel DNS/SNI/IP values должны быть absent из:

```text
routine logs
tracebacks
health rows
fault aggregate details
checkpoint rows
generation rows
config diagnostics
90-day lineage
```

Они могут появляться только в exact admitted NI-R1 sensitive rows до retention expiry.

Raw EVE JSON не появляется в product DB.

---

# 79. FINGERPRINT / PORTAL REGRESSION BOUNDARY

NI-01 acceptance должен доказать отсутствие semantic changes в:

```text
Device Fingerprint schema/writer/API/classification
Visitor Auth
CAPPORT
OmadaProvider/token lifecycle
Pending Session Cleaner
Observation
Current State
Visit Lifecycle
existing traffic products
Admin Settings
```

Любая необходимость менять эти owners:

```text
STOP
→ scope return
```

---

# 80. PRODUCTION ACTIVATION — ОТДЕЛЬНО

Merge NI-01 code НЕ включает feature в production.

Production activation требует отдельного Owner-controlled action после merge + accepted Lab evidence.

Activation gate проверяет минимум:

```text
exact production HEAD/TREE
exact source config
rename/reopen rotation
source path permissions
network-metadata service unit
DB/data path ownership
NETWORK_METADATA_ENABLED
exact CaptureScopeBinding for current deployment
resource preflight
capacity evidence
rollback
Fingerprint health regression check
```

NI-00 заново не открывается.

---

# 81. ROLLBACK

NI-01 rollback не требует mutation:

```text
Device Fingerprint DB
Portal DB
Visit DB
Observation DB
Omada configuration
```

Auxiliary runtime / isolated source output отключаются отдельно под Owner-approved activation/rollback plan.

Network Observation Store не уничтожается автоматически.

---

# 82. CODER WORKFLOW — STAGE A

После Tech Lead PASS R1 Coder получает exact accepted HEAD/TREE и сначала возвращает ТОЛЬКО PRE-CODE PLAN.

PLAN mapping:

```text
architecture clause
→ module/file
→ DB table/index
→ test
```

PLAN обязан отдельно показать:

```text
source-generation state machine
binding-change non-zero generation_start_offset
valid_from gate
canonical JSON/hash/UUID implementation
conflict matrix
checkpoint atomicity
rotation/reboot handling
copytruncate prohibition
sensitive presence-state lifecycle
digest privacy/retention
source-record retention
health heartbeat
fault aggregation
Capture Health adapter boundary
SQLite footprint/cap handling
WAL checkpoint policy
schema-version mechanism
busy timeout
freelist/cleanup behavior
transaction capacity headroom
field parsers/bounds
non-sensitive read boundary
zero direct Fingerprint DB access
zero main Portal dependency
```

До Tech Lead PLAN PASS broad implementation запрещён.

---

# 83. CODER WORKFLOW — STAGE B IMPLEMENTATION

Implementation только в isolated worktree от exact accepted HEAD/TREE.

Первый implementation handoff:

```text
COMMIT = NO
PUSH = NO
PR = NO
MERGE = NO
DEPLOY = NO
```

Coder возвращает:

```text
BASE_HEAD
BASE_TREE
worktree status
exact changed/new files
source/diff
targeted tests
compileall
git diff --check
schema proof
crash/replay proof
lifecycle proof
retention/privacy proof
capacity benchmark
directly affected regression tests
```

Coder НЕ запускает broad/full project regression suite без explicit Tech Lead request.

---

# 84. CODER WORKFLOW — STAGE C / LAB / PRODUCTION

```text
Stage C:
Tech Lead source/diff review
```

Только после source review Tech Lead может отдельно разрешить:

```text
commit
push
PR
```

Broad/full regression suite:

```text
LAB GATE
```

а не first Coder implementation gate.

Production:

```text
separate Owner-controlled activation
после merge и accepted Lab evidence
```

---

# 85. STOP CONDITIONS

Coder немедленно останавливается и возвращает вопрос Tech Lead/Architect, если:

```text
accepted source identity нельзя реализовать deterministic
binding change требует reinterpret consumed bytes
checkpoint + durable outcome нельзя commit atomic
rotation требует heuristic file archaeology
SQLite capacity gate fails
combined DB+WAL(+SHM) containment нельзя обеспечить
capture-scope authority unavailable
implementation требует direct Fingerprint SQL/write
implementation требует direct packet capture
raw EVE persistence становится необходимым
raw payload persistence становится необходимым
external dependency materially required
production Site/capture binding невозможно передать explicit
existing Fingerprint semantics должны измениться
FLOW становится обязательным для DNS/TLS/QUIC core
source conflict нельзя surface без overwrite
sensitive expiry нельзя отличить от never-observed
```

---

# 86. EXPLICITLY FORBIDDEN IMPLEMENTATION

```text
NO direct packet capture
NO second Python packet sniffer
NO PCAP writer
NO generic raw EVE database
NO Device Fingerprint DB reuse
NO direct Fingerprint SQL
NO IP→MAC attribution
NO MAC→device_id attribution
NO Device Card
NO Protocol Summary
NO Service Recognition
NO traffic accounting
NO current-rate calculation
NO FLOW dependency
NO DNS latency
NO Admin UI
NO public API
NO authorization decisions
NO Omada control
NO systemd control from application
NO Suricata restart from application
NO copytruncate production rotation
NO heuristic dedup
NO source-identity repair by guess
NO generic sensitive read flag
```

---

# 87. NI-02 HANDOFF

NI-01 durable foundation оставляет для NI-02:

```text
Site-scoped normalized observation
+
event_at
+
retained NI-R1 endpoint/name evidence while still within retention
+
source/capture provenance
+
source-health/coverage evidence
```

NI-02 отдельно определит narrow sensitive attribution read boundary и owns:

```text
Site + IPv4 + event_at
→ authoritative Site + MAC
→ existing device_id where available
```

Если NI-R1 sensitive evidence уже expired:

```text
historical attribution is not reconstructable from NI-01
```

и это не исправляется guess'ом.

---

# 88. FINAL ARCHITECTURE INVARIANTS

```text
NI01-R1-I01
Exact baseline HEAD/TREE pinned.

NI01-R1-I02
Main drift before PRE-CODE PLAN → STOP/reconcile.

NI01-R1-I03
Source identity = source_generation_id + byte offset.

NI01-R1-I04
Generation may start at non-zero physical offset after binding change.

NI01-R1-I05
One byte range is never interpreted under two binding epochs.

NI01-R1-I06
event_at before binding.valid_from_utc never becomes product observation.

NI01-R1-I07
Binding schema version and binding digest are separate provenance fields.

NI01-R1-I08
Canonical JSON/hash algorithms are single and frozen.

NI01-R1-I09
Observation UUID namespace is fixed literal.

NI01-R1-I10
Exact raw+semantic duplicate/conflict matrix is enforced.

NI01-R1-I11
Changed raw bytes at same source identity are always conflict.

NI01-R1-I12
Same raw bytes with changed semantic digest are normalizer conflict.

NI01-R1-I13
Checkpoint never advances beyond unresolved conflict.

NI01-R1-I14
Observation + checkpoint outcome commit atomically.

NI01-R1-I15
Copytruncate is not admitted production rotation.

NI01-R1-I16
Host reboot cannot reuse /run generation.

NI01-R1-I17
Suricata restart alone does not force generation change if continuity passes.

NI01-R1-I18
Sensitive presence distinguishes retained/not_observed/expired.

NI01-R1-I19
Sensitive digests expire by 14 days.

NI01-R1-I20
Generic foundation contains no hardcoded production Guest CIDR.

NI01-R1-I21
Capture scope arrives as one strict JSON setting.

NI01-R1-I22
Configured safety limits may tighten but never loosen hard ceilings.

NI01-R1-I23
No health row per observation.

NI01-R1-I24
Health heartbeat interval is 60 seconds absent transitions.

NI01-R1-I25
Repeated faults are five-minute bounded aggregates.

NI01-R1-I26
Capture health reuse is via DeviceFingerprintReadService + adapter only.

NI01-R1-I27
NI core knows no Fingerprint table names.

NI01-R1-I28
8 GiB cap measures main + WAL + SHM (+journal if present).

NI01-R1-I29
No hot-path VACUUM/full rewrite.

NI01-R1-I30
Source-record digests and identity spine have explicit separate lifetimes.

NI01-R1-I31
ingested_at is assigned inside first accepted transaction and committed atomically.

NI01-R1-I32
Ordinary NI-01 read service is non-sensitive only.

NI01-R1-I33
No generic include_sensitive escape hatch exists.

NI01-R1-I34
Field primitive types and individual bounds are explicit.

NI01-R1-I35
No silent semantic string truncation.

NI01-R1-I36
Array truncation exists only where explicit truncation state exists.

NI01-R1-I37
FLOW is not NI-01 core.

NI01-R1-I38
STATS is reused, not duplicated.

NI01-R1-I39
No Device attribution exists in NI-01.

NI01-R1-I40
No public/Admin API exists in NI-01.

NI01-R1-I41
Auxiliary failure cannot break Portal/Auth/CAPPORT.

NI01-R1-I42
SQLite production eligibility requires capacity PASS.

NI01-R1-I43
No raw EVE product storage.

NI01-R1-I44
No packet/application payload persistence.

NI01-R1-I45
Coder first gate is PRE-CODE PLAN only.

NI01-R1-I46
First implementation handoff has no commit/push/PR/merge/deploy.

NI01-R1-I47
Broad/full regression belongs to later LAB gate unless Tech Lead explicitly requests it.
```

---

# 89. TL-NI01-R1..R19 DISPOSITION

```text
TL-NI01-R1  BINDING-EPOCH / GENERATION OFFSET
= CLOSED

generation_start_offset exact
same-file binding cutover exact
no rewind/reinterpretation

TL-NI01-R2  valid_from_utc semantics
= CLOSED

PRE_BINDING_EVENT exact

TL-NI01-R3  binding provenance naming
= CLOSED

schema_version + digest split

TL-NI01-R4  raw/semantic conflict matrix
= CLOSED

CASE A/B/C + expired-digest fail-closed

TL-NI01-R5  canonical serialization / UUID
= CLOSED

CanonicalJsonV1 + literal namespace UUID

TL-NI01-R6  sensitive retention meaning
= CLOSED

observed_retained / not_observed / expired

TL-NI01-R7  digest privacy
= CLOSED

NI-R1 / 14 days max

TL-NI01-R8  no hardcoded Guest CIDR
= CLOSED

generic validator + deployment-only Zefer proof

TL-NI01-R9  capture-scope config transport
= CLOSED

NETWORK_METADATA_CAPTURE_SCOPE_BINDING_JSON

TL-NI01-R10 configurable safety ceilings
= CLOSED

config may tighten only

TL-NI01-R11 health/fault cardinality
= CLOSED

60s heartbeat + 300s fault aggregation

TL-NI01-R12 capture-health boundary
= CLOSED

DeviceFingerprintReadService.latest_source_health → adapter

TL-NI01-R13 SQLite real footprint
= CLOSED AT ARCHITECTURE LEVEL

main+WAL+SHM(+journal) counted
physical checkpoint/headroom details mandatory PRE-CODE PLAN

TL-NI01-R14 source-record retention
= CLOSED

14d digest / 30d identity spine / 90d generation lineage

TL-NI01-R15 ingested_at
= CLOSED

assigned inside first accepted transaction

TL-NI01-R16 copytruncate
= CLOSED

not admitted production strategy

TL-NI01-R17 sensitive read boundary
= CLOSED

Option A selected

TL-NI01-R18 field type/length contract
= CLOSED

exact primitive/range/string bounds frozen

TL-NI01-R19 Coder workflow
= CLOSED

PLAN → review → isolated implementation → source review → later Lab/production
```

---

# 90. OPEN QUESTIONS / FINAL R1 DISPOSITION

```text
OPEN_P0 = 0
OPEN_P1 = 0
```

Эти значения означают:

```text
Architect считает bounded return TL-NI01-R1..R19 закрытым в R1 candidate.
```

Они НЕ означают Tech Lead final acceptance до повторного review.

Final status:

```text
TASK =
TASK-DTI-NI-01
METADATA-ONLY NETWORK OBSERVATION FOUNDATION

DOCUMENT =
ARCHITECTURAL / IMPLEMENTATION CONTRACT
R1 FINAL CANDIDATE FOR TECH LEAD REVIEW

ARCHITECTURE CORE =
UNCHANGED / PREVIOUSLY PASS

REDESIGN =
NO

UPSTREAM NI-00 =
NOT REOPENED

CODER =
HOLD

SYSADMIN =
NO ACTION

PRODUCTION =
NO CHANGE

SYSTEMD =
NO ACTION

SURICATA =
NO CHANGE

READY_FOR_TECH_LEAD_FINAL_REVIEW =
YES
```

Следующий разрешённый шаг:

```text
Tech Lead final R1 review
        ↓
if PASS:
Coder PRE-CODE PLAN ONLY
        ↓
Tech Lead PLAN review
        ↓
only then implementation authorization
```
