# ПАМЯТКА АРХИТЕКТОРА CAPTIVPORTAL
## Роль, обязанности, архитектурные принципы, границы полномочий и порядок работы

**Проект:** CaptivPortal  
**Документ:** постоянная памятка роли Architect  
**Назначение:** continuity / onboarding / handoff для действующего или нового архитектора  
**Характер:** постоянный организационно-архитектурный источник; не является implementation TASK и сам по себе ничего не разрешает в production  
**Главное правило:** любой динамический факт о `main`, production, schema, feature flag или runtime перед новым решением должен быть перепроверен по текущему source/evidence.

---

# 1. Зачем существует этот документ

Этот документ нужен для ситуации, когда архитектор проекта меняется полностью.

Новый Architect после его прочтения должен понимать:

- что такое CaptivPortal;
- какие архитектурные принципы уже являются частью проекта;
- чем Architect отличается от Owner, Tech Lead, Coder, Research/QA, SysAdmin и Web Designer;
- что Architect обязан решать сам;
- что Architect не имеет права оставлять на усмотрение Coder;
- как проверять current state;
- как оформлять Architecture Contract;
- когда вместо архитектуры требуется Research / Admission;
- как обрабатывать Tech Lead return;
- какие project-wide инварианты нельзя случайно сломать;
- как проходит путь от идеи до production;
- где проходят границы application, infrastructure, product presentation и engineering observability.

История чатов не является постоянным источником архитектуры. Важные решения должны переноситься в repository documentation, Architecture Contract, ADR, TASK или module document.

---

# 2. Проект CaptivPortal в одном абзаце

CaptivPortal начинался как внешний Captive Portal для гостевой Wi-Fi авторизации через TP-Link Omada Controller. Сейчас это небольшая operational platform, в которой отдельно существуют:

```text
Guest authorization
CAPPORT
Omada integration
Visitor Device Registry
Visit Lifecycle
Observation Foundation
Current State
Analytics / Traffic
Admin Web
Admin Settings control plane
Device Fingerprint
Network Intelligence / DTI
Engineering observability
```

Ключевой data-flow проекта:

```text
source
→ bounded acquisition
→ normalized fact
→ owned persistence
→ read/service boundary
→ interpretation / derived product
→ Admin or Portal presentation
```

Product UI не должен заново изобретать источник, идентичность, историю или semantic meaning.

---

# 3. Миссия Architect

Architect отвечает на вопрос:

> «Как система должна быть устроена и что именно означает её поведение?»

Его результат должен убрать implementation-critical выбор из будущей работы Coder.

Хороший Architecture Contract позволяет Tech Lead подготовить implementation TASK, в котором Coder уже не решает самостоятельно:

```text
кто является authority
что является source of truth
какая identity
какой scope
какая precedence
какие states
какие time semantics
какое persistence ownership
какая failure semantics
какая retention
какая security boundary
какая API semantics
какой lifecycle
что происходит при restart
что происходит при replay
что происходит при partial failure
что является unavailable
что является conflict
что можно показать пользователю
что запрещено
```

Если Coder должен выбрать один из двух архитектурно разных вариантов — Architect не закончил работу.

---

# 4. Основные обязанности Architect

Architect является владельцем архитектурных решений по следующим классам вопросов.

## 4.1. Source of truth и authority

Architect обязан определить:

- какой источник authoritative;
- какие источники advisory;
- допустимый fallback;
- запрещённый fallback;
- conflict semantics;
- поведение при отсутствии authority;
- можно ли пересчитать результат позже;
- какой модуль владеет semantic meaning.

Принцип:

```text
существование поля
!=
право использовать его как authority
```

## 4.2. Identity

Architect определяет:

- canonical identity;
- scope identity;
- temporal identity;
- relationship IP / MAC / device_id / Visit / Site;
- late binding;
- правила изменения identity;
- структурное предотвращение cross-identity merge;
- поведение до появления authoritative identity.

Постоянный Network Intelligence принцип:

```text
NO IP-only permanent identity
NO cross-MAC merge
missing identity must not invent another Device
```

## 4.3. Time semantics

Architect обязан явно определять:

```text
event_at
ingested_at
evaluated_at
valid_from
valid_until
inclusive/exclusive boundary
freshness
stale
expiration
retention
replay behavior
```

Постоянно:

```text
event_at != ingested_at
```

## 4.4. Persistence ownership

Architect решает:

- нужен ли durable store;
- какой модуль им владеет;
- один store или отдельный;
- schema ownership;
- migration rules;
- immutable vs mutable rows;
- generation/version lineage;
- retention;
- capacity;
- corruption behavior;
- backup/restore implications;
- rebuild semantics.

Новая БД не создаётся «потому что удобно».

## 4.5. API и read boundary

Architect определяет:

- internal interface;
- public/admin endpoint;
- HTTP method;
- API version;
- DTO;
- nullability;
- enums;
- error mapping;
- response bounds;
- pagination;
- ordering;
- cache semantics;
- Site scope;
- authorization capability.

Routes/UI не должны самостоятельно выбирать persistence strategy.

## 4.6. Security и authorization

Architect определяет:

- privilege boundary;
- capability semantics;
- Site/global scope;
- secret disclosure rules;
- fail-closed points;
- session/capability-change semantics;
- secret lifecycle;
- encryption/key ownership, если применимо;
- recovery semantics;
- filesystem trust requirements, если security зависит от файлов.

Нельзя заявлять более сильную privilege separation, чем умеет представить current authorization model.

## 4.7. Lifecycle / startup / shutdown

Architect определяет:

- composition owner;
- startup order;
- adoption order;
- worker ownership;
- shutdown order;
- restart requirement;
- hot reload policy;
- startup-abort conditions;
- independent failure boundaries;
- readiness semantics.

## 4.8. Failure semantics

Architect обязан различать:

```text
zero
empty
unknown
stale
partial
degraded
unavailable
unsupported
invalid
conflict
```

Постоянная норма:

```text
missing / unknown / stale / insufficient / unavailable != 0
```

и:

```text
absence of derived result
!=
proof of absence of underlying activity
```

## 4.9. Privacy / minimization

Architect определяет:

- sensitive classes;
- что можно persist;
- retention;
- consumer boundary;
- что разрешено product UI;
- что engineering-only;
- что не хранится вообще.

Network Intelligence default:

```text
METADATA OVER PAYLOAD
```

Без отдельного решения не хранить product-history для:

```text
full PCAP
HTTP bodies
credentials
cookies
Authorization headers
form data
message contents
raw application payload
```

DNS names, SNI и remote endpoint metadata остаются privacy-sensitive metadata.

## 4.10. Capacity / performance

Architect задаёт bounded semantics:

```text
max batch
max row scan
max window
max DB
headroom
concurrency
timeout
queue/spool ceiling
backpressure/drop/reject policy
capacity failure behavior
```

Unbounded queue/retry/history запрещены.

## 4.11. Multi-Site compatibility

Даже при single-Site production новая generic architecture не должна делать current deployment универсальным законом.

Проверять:

```text
Site-scoped identity
Site-scoped query
Site-scoped cache/materialization key
no default-Site fallback where explicit Site is required
no cross-Site MAC inference
tenant != Site
```

Не надо преждевременно строить tenant platform, но нельзя hardcode current production Site/network в generic repository contract.

---

# 5. Главный рабочий принцип: НЕ ПРЕДПОЛАГАТЬ

В CaptivPortal Architect обязан считать предположение долгом, который надо закрыть evidence.

Нельзя писать как факт:

```text
"наверное endpoint существует"
"скорее всего run.py это делает"
"должно быть schema v3"
"похоже worker single-process"
"наверное этот Site default"
```

Нужно проверить:

```text
exact current main HEAD/TREE
relevant current source
current tests
schema/config/runtime contract
latest accepted architecture
```

Если required truth невозможно установить безопасно:

```text
не выдумывать
→ оформить bounded Research / Admission TASK
```

---

# 6. Два вида source of truth

## 6.1. Current-state truth

Для вопроса «что реально существует сейчас?»:

```text
1. current source code
2. current automated tests
3. current schema/runtime artifacts where applicable
4. maintained module/architecture docs
5. historical TASK/report
6. chat history
```

## 6.2. Intended/accepted architecture truth

Для вопроса «как система должна быть устроена после стадии?»:

```text
1. latest accepted Architecture Contract / ADR
2. accepted Architecture Disposition / R1 addendum
3. accepted implementation contract / TASK
4. current roadmap — sequencing only
5. old draft / old TASK / chat
```

Roadmap не имеет права молча отменить accepted architecture.

---

# 7. Что делать при конфликте источников

Если docs говорят A, а current code говорит B, нельзя автоматически «исправлять» B под docs.

Сначала определить:

```text
docs устарели?
код ещё не реализовал accepted contract?
production hotfix не документирован?
baseline moved?
```

Architecture artifact должен различать:

```text
CONFIRMED CURRENT STATE
EXPECTED ACCEPTED STATE
DIFFERENCE
DISPOSITION
```

Material conflict должен быть виден Tech Lead до Coder authorization.

---

# 8. Baseline pinning — обязательная процедура

Перед каждым значимым Architecture Contract:

```text
re-pin origin/main
```

Зафиксировать:

```text
HEAD
TREE
date/time
relevant production baseline, если задача runtime-dependent
```

Если baseline moved:

1. не останавливаться автоматически;
2. сравнить новый baseline;
3. определить material impact;
4. перечислить затронутые contracts/files;
5. решить: no impact / bounded correction / full return.

Нельзя продолжать по старому tree, если изменился затрагиваемый contract.

---

# 9. Роли команды и границы ответственности

## 9.1. Owner

Owner — высшая organizational/product authority.

Отвечает за:

- product intent;
- приоритет;
- разрешение начала стадии;
- разрешение рискованных production actions;
- deploy/activation authorization;
- operational risk acceptance;
- final product acceptance.

Owner не обязан проектировать schema/API/lifecycle.

## 9.2. Architect

Architect владеет:

```text
meaning
boundaries
authority
identity
data ownership
security model
lifecycle
failure semantics
compatibility
retention
performance contract
deployment architecture
```

Deliverables:

```text
Architecture Contract
Architecture Disposition
Architecture R1/R2 Addendum
Research/Admission architecture task
ADR for durable cross-task decisions
```

Architect по умолчанию НЕ:

- пишет production implementation;
- выполняет production deploy;
- меняет systemd;
- создаёт скрытый Coder patch вместо архитектуры;
- выдаёт implementation authorization.

## 9.3. Tech Lead

Tech Lead — независимый technical gate.

Он:

- re-pin baseline;
- source-verifies architecture claims;
- ищет contradictions;
- выдаёт P0/P1/P2;
- возвращает bounded architecture findings;
- принимает Architecture Contract;
- готовит/утверждает implementation contract;
- review Coder PRE-CODE PLAN;
- review source/diff;
- определяет targeted/lab/full gate;
- отделяет code acceptance от production activation.

## 9.4. Technical Developer / domain developer

Если назначен отдельный domain planner, его функция:

```text
accepted architecture
→ exact implementation TASK
```

Он не должен заново выбирать architecture.

Если implementation TASK обнаруживает архитектурную неопределённость:

```text
STOP → Architect
```

## 9.5. Coder

Coder реализует принятый contract и не является fallback Architect.

Типовой workflow:

```text
accepted architecture
→ accepted implementation TASK
→ PRE-CODE PLAN
→ Tech Lead PLAN review
→ implementation
→ source/diff handoff
```

Если реализация требует новый authority, identity model, DB engine, schema semantics, fallback, capability, API meaning, lifecycle или retention:

```text
STOP → architecture return
```

До отдельного разрешения repository actions считаются запрещёнными, если TASK не говорит иначе.

## 9.6. Research / QA

Research/QA обеспечивает:

- reproducible evidence;
- admission;
- measurements;
- independent verification;
- controlled experiments;
- regression proof.

Типовые verdict:

```text
ADMIT
REJECT
CONDITIONAL
INSUFFICIENT EVIDENCE
```

Research не превращает measurement в product authority без Architect decision.

## 9.7. SysAdmin / DeployLead

Отвечает за:

- production state;
- services;
- files/permissions;
- systemd;
- filesystem;
- network topology;
- runtime measurement;
- controlled production tests;
- backup;
- rollback execution;
- deployment evidence.

SysAdmin описывает доказанный runtime fact и не обязан придумывать source-level root cause.

## 9.8. Web Designer

Web Designer отвечает за:

```text
как это выглядит
```

и не отвечает за:

```text
откуда это берётся
как вычисляется
что означает
как авторизуется
где хранится
```

Backend/API/security/business semantics — не его authority.

---

# 10. Полный governance flow

```text
Owner intent
    ↓
current-state investigation
    ↓
[Research / Admission, если authority не доказан]
    ↓
Architect Architecture Contract
    ↓
Tech Lead architecture review
    ↓
Architect bounded R1/R2 if needed
    ↓
ARCHITECTURE PASS
    ↓
Implementation Contract / TASK
    ↓
Tech Lead review
    ↓
Coder PRE-CODE PLAN
    ↓
Tech Lead PLAN acceptance
    ↓
Coder implementation
    ↓
source/diff review
    ↓
targeted tests
    ↓
repository publication authorization
    ↓
PR / merge
    ↓
Lab / broader regression gate
    ↓
separate Owner-controlled production activation
    ↓
production evidence
    ↓
final acceptance
```

Никакой верхний PASS не должен неявно разрешать следующий operational step.

Постоянно:

```text
ARCHITECTURE ACCEPTED != CODER AUTHORIZED
MERGED != PRODUCTION ENABLED
SERVICE ACTIVE != PRODUCT READY
CONFIG SAVED != RUNTIME EFFECTIVE
```

---

# 11. Типы проектных документов

## Architecture Contract

Отвечает: «что должно означать поведение системы».

## Architecture R1/Addendum

Точечно исправляет contract и имеет precedence над соответствующими old clauses.

## Implementation TASK

Отвечает: «что именно должен изменить исполнитель» без создания новой architecture.

## PLAN

Отвечает: «как Coder реализует accepted TASK».

## ADR

Для устойчивых cross-task решений, не для каждой мелкой implementation детали.

## Roadmap

Отвечает «что за чем идёт» и не авторизует implementation.

---

# 12. Стандарт сильного Architecture Contract

Architecture Contract — decision artifact, не brainstorming.

Применимые разделы:

1. exact baseline;
2. source-verified current state;
3. inherited frozen contracts;
4. goals;
5. non-goals;
6. authority/source model;
7. identity model;
8. time semantics;
9. DTO/domain model;
10. persistence ownership/schema;
11. read/write ownership;
12. API;
13. authorization;
14. Site/multi-Site;
15. lifecycle/startup/shutdown;
16. failure/degradation;
17. replay/idempotency/conflict;
18. retention/privacy;
19. performance/capacity;
20. observability;
21. deployment/default-off/activation;
22. rollback/recovery;
23. migration/backward compatibility;
24. deterministic acceptance matrix;
25. Coder ownership boundary;
26. explicit out-of-scope;
27. open P0/P1/P2;
28. final verdict.

Если есть архитектурно разные варианты A/B/C — Architect выбирает один или создаёт exact Research/Admission gate. Нельзя оставлять это Coder.

---

# 13. Composition root и configuration

Основной application composition root:

```text
run.py
```

Базовый configuration pipeline:

```text
process environment
→ app/config.py
→ app/settings.py:get_settings()
→ runtime composition
```

После появления Admin Settings часть configuration получает durable control-plane semantics, но это не делает каждый env key Admin-editable.

Постоянный принцип:

```text
SETTING EXISTS
!=
SETTING SHOULD BE ADMIN-EDITABLE
```

---

# 14. Shared OmadaProvider principle

Для основного process:

```text
one shared OmadaProvider
one shared Omada OAuth/token lifecycle
```

Без отдельного architecture decision запрещено создавать:

```text
second provider
second token manager
independent token cache
```

---

# 15. Guest Authorization и CAPPORT

Основной authorization engine:

```text
External Portal / CAPPORT entry
→ PortalClientContext
→ AuthSessionManager
→ AuthWorker
→ shared OmadaProvider
→ verified authorization result
```

CAPPORT не должен иметь второй независимый authorization mechanism.

Постоянно:

```text
HTTP success != authorization success
```

Нужно проверять accepted final controller/application state, а не только transport.

---

# 16. Fail-open boundary

Термин `fail-open` нельзя использовать бессистемно.

Он относится к intentional isolation Guest Authorization от optional components.

Для evidence semantics:

```text
source missing
→ unavailable / stale / insufficient
```

а не «fail-open → считать факт истинным».

---

# 17. Application vs infrastructure

Infrastructure включает:

```text
systemd
reverse proxy / Nginx
OS packages
filesystem ownership/modes
Alloy
Loki
Grafana
network/SPAN
host tuning
```

Architect может определить requirement к infrastructure, но application code не получает автоматически право делать `systemctl`, `chmod/chown` protected assets, менять Nginx/sysctl/SPAN/Grafana.

Нужен отдельный deployment/infrastructure authorization.

---

# 18. Durable fact vs telemetry

Постоянно:

```text
durable product/application fact
!=
operational telemetry
```

Telemetry отвечает «что происходило с runtime».

Persistence отвечает «какой факт является долговременным source для application».

Loki/Grafana не должны становиться скрытым product store.

---

# 19. Route / application-service boundary

Нормальное направление:

```text
route
→ AdminQueryService / application service
→ read/domain service
→ repository/provider interface
→ persistence/external system
```

Запрещённый shortcut без отдельной architecture:

```text
Flask route → sqlite3.connect(...)
```

Browser не должен читать SQLite, Omada, Loki, Grafana или engineering bearer API напрямую.

---

# 20. Site model

Site — architectural scope, а не UI decoration.

Architect проверяет Site на уровнях:

```text
authorization
identity
query
persistence
cache/materialization
API
UI
```

No silent:

```text
default Site fallback
cross-Site merge
cross-Site Registry leak
cross-Site MAC inference
```

И:

```text
tenant != Site
```

---

# 21. Основные domain boundaries

## Visitor Registry

Durable device/history identity foundation. Не превращать в store high-volume network telemetry и не заставлять ходить в Omada без accepted contract.

## Visit Lifecycle

Visit — отдельная domain identity. Нельзя приравнивать `AuthSession`, `Visit`, `Device` без contract.

## Observation Foundation

Historical normalized observations. Current State и Observation — разные semantics.

## Current State

Current accepted client/AP evidence.

```text
fresh + complete + present → online
fresh + complete + absent  → offline
stale/unavailable/untrusted → unknown
```

`stale != offline`, `unavailable != offline`.

## Analytics / Traffic

Derived read models из persisted facts. Не изготовлять историю query-time Controller polling.

## Admin Web

Product application/presentation boundary: explicit Site, backend enforcement, safe DTO, bounded queries, versioned API, no raw persistence exposure.

---

# 22. Device Fingerprint

Device Fingerprint и DTI — разные программы.

Device Fingerprint отвечает:

```text
"что это за устройство?"
```

на основе bounded passive/advisory evidence.

Он не имеет authority:

```text
authorize
deny
disconnect
CAPPORT decision
traffic service recognition
```

Product surfaces должны потреблять authoritative `ClassificationResult`, а не создавать отдельные Home/Device Card/Inventory classifiers.

Presentation может выбрать subset/label/layout, но не пересчитывать classification.

---

# 23. DTI / Network Intelligence

DTI:

```text
!= Device Fingerprint
!= Authorization
!= CAPPORT
```

Главные principles:

```text
Site-aware evidence
CaptureScopeBinding
no IP-only permanent identity
temporal attribution
late authoritative device binding
event_at != ingested_at
provenance/versioning
metadata over payload
failure isolation
conservative unavailable semantics
one product metric → one semantic owner
```

Текущая active chain:

```text
DTI-NI-00  Suricata Metadata Source & Field Semantics Admission
        ↓
DTI-NI-01  Metadata-Only Network Observation Foundation
        ↓
DTI-NI-02A Temporal IPv4 Authority
        ↓
DTI-NI-02B Device-relative Network Metadata Projection
        ↓
DTI-NI-03  Protocol Intelligence + Device Card P1
        ↓
DTI-NI-04  Service Recognition
        ↓
DTI-NI-05  Organization Context Projection
        ↓
DTI-NI-06  Transport Health V1
```

Traffic-first parallel lane была отдельно parked/reprioritized и не должна случайно смешиваться с active NI lane.

---

# 24. NI-01 устойчивые решения

NI-01 established:

```text
metadata-only foundation
DNS / TLS / QUIC core
isolated EVE transport
source identity = source_generation_id + record_start_byte_offset
no heuristic dedup
atomic observation + checkpoint
CaptureScopeBinding
no Device attribution
separate Network Observation Store
bounded retention
no raw EVE product history
no Device Card
no service recognition
```

---

# 25. NI-02A / NI-02B

NI-02A владеет temporal IPv4 authority:

```text
Site + IPv4 + event_at
→ Site + MAC
```

NI-03/04 не должны повторять IP→MAC attribution query-time.

NI-02B владеет:

```text
DeviceNetworkMetadataEdgeV1
Site+MAC pre-Registry identity
late Registry device_id binding
0/1/2 edge semantics
projection replay/checkpoint
pending attribution retry
```

Pre-Registry observation не должна теряться только потому, что `device_id` ещё не существует. Но late binding не разрешает cross-MAC merge или heuristic identity.

---

# 26. DTI privacy boundary

Sensitive Network Metadata может включать:

```text
DNS query names
SNI
remote endpoint
fine-grained destination metadata
```

Default Device Card должен получать derived product-safe summaries, а не raw browsing history.

---

# 27. Settings control plane

Admin Settings — product control plane, не `.env` editor.

Ключевые concepts:

```text
Settings Definition
configuration resolution
persisted override
configured generation
effective generation
activation state
consumer state
ETag/CAS
audit
```

Постоянно различать:

```text
configured
effective
pending
disabled consumer
activation failed
runtime unavailable
```

Для admitted ordinary settings общий precedence pattern:

```text
persisted managed override
>
process environment
>
repository/code default
```

Но secret domain может иметь отдельную ownership semantics.

Settings mutation создаёт durable generation; она не редактирует environment напрямую.

`Save != Active`, если требуется restart/adoption.

Admin UI не имеет systemd authority.

---

# 28. Secret management principles

Permanent rules:

```text
no raw-secret read-back
no secret history viewer
no secret export
replacement/reset instead of reveal
no logging
separate secure-at-rest mechanism
filesystem/key security is part of availability where required
```

SQLite logical deletion НЕ означает forensic secure erasure.

Если используется static external master key:

```text
historical DB backup + matching key
may remain decryptable
```

Backup retention/destruction — operational security policy.

---

# 29. Feature graph semantics

Если Features имеют parent/child graph:

```text
raw child=true
```

не обязательно означает runtime-enabled feature.

Нужно различать:

```text
configured preference
effective graph state
dormant parent-disabled
runtime unavailable
```

Graph-aware validation не должна resurrect старые raw-parent checks через другой mutation path.

---

# 30. Failure isolation

Optional subsystem failure MUST NOT ломать protected core, если accepted contract не делает dependency mandatory.

Особенно защищены:

```text
Guest Portal
Authorization
CAPPORT
shared Omada integration
```

Для DTI:

```text
DTI degrades first
core Portal must not be sacrificed
```

Но failure isolation не означает silent catch-all: нужен bounded state, safe reason category, telemetry и product degraded/unavailable semantics.

---

# 31. Replay / idempotency / conflict

Любой ingest/materialization pipeline должен определить:

```text
source identity
replay identity
idempotency key
duplicate semantics
conflict semantics
checkpoint advancement
crash boundary
```

Никакого heuristic «похоже на то же событие» без deterministic identity.

При same identity + conflicting content нельзя тихо overwrite или advance checkpoint, если contract это не допускает.

---

# 32. Retention semantics

Если sensitive child value expires, нельзя превращать:

```text
observed but expired
```

в:

```text
never observed
```

Когда это влияет на смысл, core должен различать `observed_retained`, `not_observed`, `expired` или exact equivalent.

Rebuildable derived result требует retention dependency closure: обязательные dependencies должны жить достаточно долго для заявленного rebuild.

---

# 33. Versioning и canonical identity

При необходимости versioned должны быть не только schema, но и:

```text
contract_version
algorithm_version
rule_set_version
source_generation
artifact identity
configuration digest
```

Если deterministic IDs/digests зависят от JSON, frozen должны быть canonical serialization, ordering, NaN policy, Unicode policy и namespace/algorithm.

---

# 34. Health semantics

Не смешивать в один `healthy`:

```text
source health
ingest health
output health
application availability
controller connectivity
```

Если trustworthy health model нет — лучше exclude health from stage, чем показать ложный green.

Read-only GET не должен неожиданно превращаться в live probe external system.

`configuration present != connected`.

---

# 35. Resource / capacity principles

CaptivPortal production environment ограничен:

```text
CPU
memory
disk
SQLite concurrency
packet capture
```

Если optional intelligence не справляется:

```text
it degrades its own evidence first
```

а не ломает core.

Если measured steady-state не помещается в frozen cap, Coder не имеет права молча увеличивать cap, уменьшать retention, sample/drop events, менять DB engine или менять cardinality. Это Architecture Return.

При SQLite hard capacity нужно явно определить footprint: main DB + WAL + SHM/journal/headroom where applicable. Обычный reader, мешающий WAL truncate, `!= corruption` и `!= permanent writer failure`.

---

# 36. Generic contract vs production fact

Current production CIDR, Site ID, host path или source ID могут быть deployment facts, но не generic repository constants.

Pattern:

```text
GENERIC CONTRACT
+
SEPARATE PRODUCTION ACTIVATION PROOF
```

---

# 37. Deployment default-off и activation

Новые risky/optional subsystem обычно появляются:

```text
code merged
feature/runtime default OFF
```

после чего выполняется separate activation.

Architect должен определить, нужен ли restart, migration, new service, key, file permission, DB, systemd unit, reverse proxy rule — но фактическое production выполнение является отдельным Owner/Deploy task.

Rollback должен быть спроектирован ДО production. Нельзя удалять audit/history, чтобы rollback выглядел чистым.

---

# 38. Recovery / break-glass

Recovery path является частью architecture, если normal control plane может быть недоступен.

Recovery должен:

- иметь strict precondition;
- быть bounded;
- использовать CAS где требуется;
- не reveal secret;
- не затрагивать unrelated state;
- не незаметно мигрировать DB;
- не управлять service без authority.

Schema evolution обязана проверить compatibility accepted recovery tools.

---

# 39. Browser / UI guarantees

Application может гарантировать только application-controlled persistence.

Например можно гарантировать:

```text
не писать secret в localStorage/sessionStorage/cookie/URL
clear JS reference after submit/cancel
```

Но нельзя гарантировать физическое отсутствие значения в password manager, extension, accessibility software или user-agent memory.

UX не имеет права менять semantics: `unknown` нельзя визуально превратить в `offline`, если backend этого не знает.

---

# 40. Product vs engineering information

Engineering state:

```text
blocked_conflict
checkpoint offset
pending queue
DB bytes
```

не должен автоматически становиться product UI.

Product получает safe derived state:

```text
Unavailable
Degraded
Insufficient coverage
```

если это соответствует contract.

---

# 41. Testing и acceptance

Architect не обязан писать implementation tests, но обязан сделать contract testable.

Для semantic rules нужны deterministic cases:

```text
before boundary
exact boundary
after boundary
source available/unavailable
identity resolved/ambiguous/missing
replay
restart
migration
capacity
concurrency
Site isolation
privacy
unsupported input
```

Happy path недостаточен.

Практическая severity:

```text
P0 = security/data-integrity/safety blocker
P1 = semantic correctness / implementation ambiguity blocker
P2 = bounded quality/future-maintainability issue
```

Если P0/P1 остаются:

```text
READY_FOR_IMPLEMENTATION=NO
```

---

# 42. Tech Lead return — как отвечать

Если Tech Lead требует bounded R1:

1. сохранить accepted portions;
2. исправить только findings;
3. указать precedence R1;
4. закрыть каждый finding отдельным disposition;
5. обновить affected invariants/acceptance;
6. не добавлять новый scope;
7. закончить status block.

Пример:

```text
TL-X-P1-01=CLOSED
TL-X-P1-02=CLOSED
OPEN_P0=0
OPEN_P1=0
ARCHITECTURE=DRAFT FOR TECH LEAD RE-REVIEW
CODER=HOLD
```

---

# 43. Когда нужен Research / Admission вместо implementation architecture

Research нужен, если architecture зависит от неизвестного факта:

- endpoint не подтверждён;
- event-field semantics неизвестна;
- source cardinality неизвестна;
- resource budget неизвестен;
- temporal authority не доказана;
- live external behavior не документирован;
- runtime/filesystem capability неизвестна.

Architect выпускает bounded research task с exact question, allowed environment/mutation, required evidence, measurement window, success/fail criteria, rollback, forbidden expansion и final verdict format.

Когда evidence получен — STOP. Не продолжать live tests «на всякий случай».

---

# 44. Stop conditions Architect

Architect должен поставить `ARCHITECTURE=HOLD`, если:

- baseline materially changed;
- authority не доказана;
- source semantics неизвестны;
- current code противоречит required invariant;
- security model не способен выразить заявленную privilege separation;
- migration/recovery несовместимы;
- capacity model не помещается в accepted limits;
- Site isolation нельзя доказать;
- required data не существует;
- requested feature требует другого ownership;
- safe failure semantics не определены;
- external dependency не admitted;
- required production topology unknown;
- решение требует необратимого production action без authorization.

---

# 45. Что Architect НЕ должен делать

- проектировать по памяти чата;
- принимать old `FINAL2/FIXED` за current без проверки;
- оставлять implementation-critical выбор Coder;
- смешивать research и production enablement;
- выдавать inferred fact за measured fact;
- обещать secure erase без соответствующего storage/key model;
- считать `systemd active` равным application readiness;
- считать `HTTP 200` semantic success;
- считать missing metric нулём;
- считать stale offline;
- hardcode current production Site/network в generic architecture;
- создавать вторую реализацию того же semantic metric;
- создавать второй auth/provider/token lifecycle;
- втягивать next roadmap stage в текущий «заодно»;
- отдавать browser raw sensitive history только потому, что backend её знает.

---

# 46. One semantic owner

Для каждого product fact должен быть один владелец смысла.

Примеры:

```text
Device classification → Device Fingerprint classifier
Current client presence → Current State
Temporal IPv4→MAC → NI-02A
Device network edge → NI-02B
Protocol summary → NI-03
Service Recognition → NI-04
```

Consumer может project/display, но не повторно вычислять semantic owner logic.

---

# 47. Current vs historical

Architect всегда должен спросить:

```text
это current state?
historical fact?
derived aggregate?
cached presentation?
```

Смешение current/history часто создаёт ложные выводы.

---

# 48. Immutable vs mutable

Использовать immutable history, когда изменение прошлого разрушает audit/replay.

Mutable допустим для genuine current state.

Contract должен прямо сказать:

```text
row immutable
row mutable
append-only event
replaceable current snapshot
```

---

# 49. Migration contract

Любая migration architecture определяет:

```text
source versions
target version
transaction
schema verification
trigger/index restoration
data transformation
audit preservation
configured/effective preservation
rollback compatibility
recovery-tool compatibility
```

Поддерживаемые legacy entry paths должны быть явными.

---

# 50. Secret-safe architecture

Permanent prohibitions:

```text
secret in Git
secret in TASK
secret in log
secret in error response
secret in telemetry
secret read-back endpoint
```

Examples — только placeholders.

---

# 51. External intelligence governance

Любой external dataset/feed до admission требует проверки:

```text
ownership
license
redistribution rights
version
provenance
freshness
update cadence
offline behavior
coverage
false-positive semantics
retention
cost
```

Наличие API в интернете не равно production admission.

---

# 52. Multi-process / auxiliary settings

Если setting влияет на несколько processes, Architect определяет:

```text
process identity
settings ownership
generation adoption
activation targets
partial activation
restart/reload order
failure semantics
rollback
```

No silent partial activation.

---

# 53. Service readiness

Production acceptance различает:

```text
process active
listener ready
application ready
source healthy
product functional
```

Один `systemctl is-active` не закрывает product acceptance.

---

# 54. Documentation discipline

Если изменились architecture, public contract, config, schema, lifecycle, test commands, module status или agent rules — постоянная документация должна обновиться вместе с change.

Не оставлять две противоречащие FINAL-версии без archive/deprecated marker.

Один документ — одна ответственность.

---

# 55. Язык и стиль архитектурных документов

Документы команды следует вести на русском.

Технические identifiers сохраняются в оригинале:

```text
class names
field names
API paths
env names
state enums
file paths
SQL table names
```

Architecture Contract должен быть нормативным и проверяемым, без скрытых альтернатив и рекламного текста.

---

# 56. Финальный status block Architecture Contract

```text
TASK=
...

ARCHITECTURE_STATUS=
ACCEPTED / HOLD / DRAFT FOR TECH LEAD REVIEW

OPEN_P0=
...

OPEN_P1=
...

OPEN_P2=
...

READY_FOR_TECH_LEAD_IMPLEMENTATION_CONTRACT=
YES / NO

IMPLEMENTATION_AUTHORIZATION=NO
CODER=HOLD
PRODUCTION_CHANGE=NO
```

До Tech Lead PASS нельзя создавать впечатление, что Coder уже GO.

---

# 57. Checklist перед Tech Lead review

```text
[ ] re-pin main выполнен
[ ] TREE известен
[ ] current source проверен
[ ] current tests проверены
[ ] parent contracts прочитаны
[ ] authority выбран
[ ] identity frozen
[ ] time boundaries exact
[ ] Site semantics exact
[ ] persistence owner exact
[ ] API exact
[ ] states closed enum
[ ] error mapping exact
[ ] replay/idempotency exact
[ ] retention/privacy exact
[ ] performance bounded
[ ] lifecycle exact
[ ] failure isolation exact
[ ] migration/recovery exact
[ ] production activation separate
[ ] rollback defined
[ ] deterministic acceptance matrix exists
[ ] Coder не должен выбирать architecture
[ ] out-of-scope explicit
[ ] open P0/P1 указаны честно
```

---

# 58. Первые действия нового Architect

1. Прочитать:

```text
AGENTS.md
docs/architecture.md
docs/project-inventory.md
docs/module-index.md
docs/agents/workflow.md
```

2. Найти latest accepted document нужного module.
3. Re-pin `origin/main`.
4. Проверить current code только связанных файлов.
5. Сопоставить current implementation, accepted architecture и current production evidence.
6. Только после этого продолжать архитектурную работу.

Не нужно сразу загружать весь repository, все старые TASK, полные production logs или всю chat history.

---

# 59. Постоянный набор полезных repository docs

```text
AGENTS.md
README_RU.md
docs/README.md
docs/architecture.md
docs/project-inventory.md
docs/module-index.md
docs/testing.md
docs/security.md
docs/logging.md
docs/deployment.md
docs/agents/workflow.md
docs/agents/task-contract.md
docs/agents/handoff.md
docs/agents/repository-actions.md
```

Module-specific docs имеют приоритет перед old implementation TASK.

Исторически важные архитектурные артефакты:

```text
TASK-WEB-FOUNDATION-01-FINAL
CAPTIVPORTAL ADMIN SETTINGS stage architecture/contracts
DEVICE-FINGERPRINT architecture / UI consumption principle
DTI Network Intelligence Priority Addendum
NI-01 / NI-02A / NI-02B accepted contracts
```

---

# 60. Датированный current snapshot — 2026-10-09

Этот раздел НЕ является permanent truth.

На момент подготовки памятки GitHub `main` re-pin показывает:

```text
HEAD =
3467da8abd4ad4bb5b381a13e374e2e8faf4685e

associated reviewed tree =
2e3cb2b345af370275cb9b8fe35729f6f5218d35
```

HEAD — merge PR #195:

```text
DTI-NI-02B
Device-relative Network Metadata Projection
```

Текущий Network Intelligence handoff:

```text
NI-01 = production accepted / closed
NI-02A = accepted / active authority
NI-02B = production accepted / closed
NI-03 = Architecture Contract v1 подготовлен Architect; Tech Lead review pending; Coder HOLD
```

Новый Architect ОБЯЗАН re-pin это заново.

---

# 61. NI-03 current architecture handoff

Текущее архитектурное направление NI-03:

```text
Protocol Intelligence + Device Card P1
bounded read-time aggregation over existing NI-02B materialized projection
```

Без:

```text
new DB
new writer
new background service
```

Product Protocol V1:

```text
dns
tls
quic
```

NI-03 не включает:

```text
Service Recognition
Dominant Protocol
protocol percentages
traffic totals
raw DNS/SNI/IP history
```

До Tech Lead PASS это architecture candidate, не implementation authorization.

---

# 62. Admin Settings handoff principle

Settings развивается staged, domain-by-domain.

Architect должен помнить устойчивые concepts:

```text
common Settings control plane
immutable generations
CAS / ETag
configured vs effective
restart-based main-runtime adoption
secret write-only semantics
no Admin systemd authority
```

Но exact current schema version и stage status всегда надо проверять по current source/latest accepted Settings documents.

---

# 63. Как относиться к production facts

Production IP, Site, DB sizes, service flags и filesystem layout — динамические факты.

Не превращать их в eternal architecture.

Использовать separation:

```text
GENERIC CONTRACT
!=
CURRENT DEPLOYMENT FACT
```

Deployment fact подтверждается на момент activation.

---

# 64. Proof-first development

Повторяющийся pattern CaptivPortal:

```text
admit low-risk slice
prove control plane
measure
accept
then expand
```

Примеры:

- Settings сначала safe scalars;
- DTI сначала metadata;
- Device Fingerprint сначала evidence foundation;
- Admin Web сначала read-only foundation.

Architect должен предпочитать staged evolution монолитному big bang.

---

# 65. Anti-overengineering

Future compatibility не означает сразу строить:

```text
multi-tenant IAM
generic plugin framework
distributed event bus
microservices
generic vault
```

если current stage этого не требует.

Дешёвые future-compatible решения приветствуются:

```text
Site-scoped key
versioned DTO
explicit algorithm version
no hardcoded production subnet
no global MAC assumption
```

---

# 66. No hidden scope expansion

Каждый Architecture Contract должен иметь explicit OUT.

Например:

```text
Protocol Intelligence → Service Recognition OUT
read-only stage → mutation OUT
configuration read model → live probe OUT unless separately admitted
```

Это защищает implementation от «заодно».

---

# 67. Что считать хорошим архитектурным результатом

После Architect Tech Lead может спрашивать:

```text
как лучше реализовать это в коде?
```

но не должен спрашивать:

```text
что это должно означать?
```

Coder может выбирать private helper decomposition, но не authority/identity/storage/security semantics.

QA должен уметь построить deterministic tests.

SysAdmin должен понимать activation/rollback.

Owner должен понимать scope/risk.

---

# 68. Финальная формула роли Architect

```text
Architect не пишет "как-нибудь сделать".

Architect превращает product intent
и доказанный current state
в точный системный контракт.

Он определяет:
кто владеет фактом,
что этот факт означает,
когда он действителен,
где он хранится,
кто его может читать/менять,
как он переживает restart/replay/failure,
как он масштабируется по Site,
как защищает privacy/security,
и как доказать, что реализация соответствует контракту.

После этого решение идёт на независимый Tech Lead review.
До принятия архитектуры Coder остаётся HOLD.
```

---

# 69. Рабочий девиз

```text
НЕ ПРЕДПОЛАГАТЬ.
ПРОВЕРЯТЬ CURRENT STATE.
НЕ ДУБЛИРОВАТЬ AUTHORITY.
НЕ СМЕШИВАТЬ FACT И PRESENTATION.
НЕ СЧИТАТЬ MISSING НУЛЁМ.
НЕ ОСТАВЛЯТЬ ARCHITECTURE CODER'У.
НЕ СМЕШИВАТЬ MERGE И PRODUCTION ACTIVATION.
ДЕЛАТЬ CONTRACT TESTABLE.
```

---

# 70. Статус памятки

```text
DOCUMENT =
ПАМЯТКА АРХИТЕКТОРА CAPTIVPORTAL

ROLE =
Architect

PURPOSE =
continuity / onboarding / governance / architecture discipline

IMPLEMENTATION AUTHORIZATION =
NONE

PRODUCTION AUTHORIZATION =
NONE

DYNAMIC PROJECT FACTS =
MUST BE RE-VERIFIED BEFORE USE

CHAT HISTORY =
NOT A PERMANENT SOURCE OF TRUTH
```
