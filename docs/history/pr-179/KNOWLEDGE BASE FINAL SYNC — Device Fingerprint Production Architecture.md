# KNOWLEDGE BASE / DOCUMENTATION KEEPER DIRECTIVE

## CaptivPortal — Device Fingerprint Final Production Knowledge Sync

### От Owner + Tech Lead

Device Fingerprint прошёл полный путь:

```text
Evidence Foundation
→ Network / Portal Evidence
→ Source Health / Contracts
→ Knowledge / Policies
→ Runtime Admission
→ Classification Core
→ Persistence
→ Auth / Device Integration
→ Production Worker
→ Admin Presentation
→ Production Acceptance
```

Система уже **реально работает в production**, сохраняет классификации устройств и показывает результаты в Admin Home и Device Card.

Теперь необходимо выполнить полноценную синхронизацию базы знаний и документации проекта.

Это не задача «дописать статус».

Необходимо привести **весь current knowledge layer репозитория** в соответствие с фактическим состоянием проекта.

---

# 1. Главное правило этой работы

НЕ опирайся только на этот handoff.

Этот документ является навигацией и перечнем уже известных Tech Lead фактов.

Перед изменением документации ОБЯЗАТЕЛЬНО самостоятельно исследуй текущий repository state.

Authoritative repository:

```text
ZaurNavi/CaptivePortal
```

Начальная точка для инвентаризации:

```text
main commit =
7c7c0919c3e546f499b5252ea9479d32c8f494d7

tree =
dbf3e3804931d637ef1ec569128746ebce5c141a

merged PR =
#178
```

Production работает на том же exact commit/tree.

Не использовать старый README checkpoint как текущую истину.

---

# 2. Обязательная repository-wide инвентаризация

Перед написанием документации исследовать repository целиком с особым вниманием к:

```text
README.md
README_RU.md
AGENTS.md

docs/
.github/

app/device_fingerprint/
app/device_fingerprint_integration/
app/admin_web/

research/device_fingerprint_*/

tests/device_fingerprint*/
tests/device_fingerprint_integration/
tests/admin_web/

deploy/
configuration/settings related to fingerprint

systemd/runtime documentation
```

Выполнить repository-wide search минимум по понятиям:

```text
device_fingerprint
Device Fingerprint
ClassificationResult
ClassificationRuntimeProfile
FoundationRuntimeProfile
SnapshotExecutionPolicy
SourceEvaluability
OriginAssessment
ClassifierArtifactManifest
Task04AcceptanceManifest
fingerprint-classification
fingerprint_type
Controller Platform
Fingerprint Platform
100663296
536870912
1073741824
TASK-DEVICE-FINGERPRINT
```

Цель поиска:

1. найти current contracts;
2. найти устаревшие current-status утверждения;
3. отделить historical evidence от current documentation;
4. определить все документы, где Device Fingerprint должен быть отражён;
5. выявить противоречия между README/docs/current code.

---

# 3. Source priority

При противоречиях использовать следующий порядок доверия:

```text
1. exact current main source code
2. exact current tests describing current contract
3. production-verified current state
4. FINAL registered architecture decisions
5. accepted task handoffs
6. current docs
7. historical task documents
8. old planning documents / old chat summaries
```

Исторический документ может быть совершенно правильным для своего времени и одновременно неправильным как описание current state.

НЕ переписывать историческую приёмочную документацию так, будто прошлое состояние никогда не существовало.

---

# 4. Критически важное исправление структуры документации

Сейчас `docs/modules/device-fingerprint.md` начинается как описание первоначального TASK-01 Evidence Foundation.

Там исторически корректно говорится, что этот foundation сам:

```text
does not classify devices
does not link identities
does not change Admin behavior
```

Это по-прежнему правда для TASK-01 как отдельного слоя.

Но это БОЛЬШЕ НЕ ЯВЛЯЕТСЯ корректным описанием всей современной системы Device Fingerprint.

Необходимо переработать документ по слоям:

```text
Device Fingerprint
│
├── Evidence Foundation
│
├── Evidence Producers
│   ├── network
│   └── portal
│
├── Foundation Contracts
│
├── Classification Core
│
├── Runtime Profiles / Admission
│
├── Classification Persistence
│
├── Auth / Device Integration
│
├── Production Worker
│
└── Product Presentation
    ├── Home
    └── Device Card
```

TASK-01 semantics не удалять.

Нужно просто ясно показать:

```text
TASK-01 = foundation layer
!=
whole current Device Fingerprint system
```

---

# 5. Текущий production state, который должен быть зафиксирован

На момент этого knowledge sync:

```text
PRODUCTION_HEAD =
7c7c0919c3e546f499b5252ea9479d32c8f494d7

PRODUCTION_TREE =
dbf3e3804931d637ef1ec569128746ebce5c141a

PR #178 =
MERGED

TASK-DEVICE-FINGERPRINT-06 =
PRODUCTION DEPLOYED

captive-portal.service =
active

fingerprint-classification.service =
active
```

Final Task06 deployment:

```text
EXACT_CODE_SWITCH = PASS
TASK06_SMOKE = PASS
TASK06_PRODUCTION_DEPLOY = PASS
```

Owner визуально подтвердил:

```text
Home fingerprint Type visible
Device Card Fingerprint Information visible
```

То есть это уже не theoretical / future UI requirement.

Это current production behavior.

---

# 6. Что сейчас умеет Device Fingerprint

Система должна быть описана как production capability, которая:

```text
1. собирает нормализованные evidence;
2. хранит source health;
3. строит согласованный evidence snapshot;
4. оценивает применимость/доступность источников;
5. использует versioned knowledge;
6. строит OriginAssessments;
7. объединяет claims через deterministic fusion;
8. формирует structured ClassificationResult;
9. сохраняет результат;
10. связывает классификацию с production auth/device lifecycle;
11. хранит историю классификаций;
12. предоставляет authoritative read boundary;
13. показывает результат в Admin UI.
```

---

# 7. Основные итоговые fingerprint dimensions

Current product dimensions:

```text
device_class
platform_family
manufacturer_family
model_family
```

Типичные presentation examples:

```text
device_class
  Smartphone
  Tablet
  Laptop

platform_family
  Android
  iOS
  Windows
  macOS
  Linux
  ChromeOS

manufacturer_family
  Apple
  Samsung
  Xiaomi
  Lenovo
  ...

model_family
  device/model family where resolvable
```

Не обещать, что каждая dimension всегда определяется.

---

# 8. Dimension status semantics

Документация обязательно должна объяснить:

```text
resolved
recognized_out_of_scope
unknown
insufficient_evidence
conflicting_evidence
```

и support:

```text
none
low
medium
high
```

Очень важно:

```text
unknown
!=
no result
!=
unavailable
```

Product presentation:

```text
—          = authoritative completed production result ещё отсутствует

Unknown    = classification завершена,
             но эта dimension не была разрешена

Unavailable = fingerprint persistence/read path
              временно недоступен
```

Не смешивать эти состояния.

---

# 9. Evidence architecture

Необходимо подробно задокументировать все текущие evidence paths по фактическому code/main.

Обязательно описать минимум следующие origin families:

```text
DHCP
Portal
TCP
TLS
QUIC
MAC Registry
```

Но точные:

```text
schema versions
producer names
adapter names
claim rules
runtime admission conditions
```

брать непосредственно из current main и FINAL R14.

Не копировать их из этого handoff без проверки.

---

# 10. Network evidence

Нужно описать фактическую network evidence pipeline.

Показать:

```text
SPAN / mirrored traffic
        ↓
sensor-side processing
        ↓
bounded normalized evidence
        ↓
Device Fingerprint Evidence DB
```

Разобрать реальные текущие paths:

```text
DHCP
TCP SYN
TLS client metadata
QUIC client metadata
```

Указать:

```text
что захватывается
что нормализуется
что сохраняется
что НЕ сохраняется
```

Особенно сохранить privacy/property:

```text
raw frames are not durable evidence
raw EVE is not durable product storage
normalized bounded evidence is persisted
```

Точные текущие sensor implementation details проверить по repository.

---

# 11. Portal evidence

Отдельно показать Portal evidence path:

```text
Portal / CAPPORT request
        ↓
bounded request metadata
        ↓
portal evidence producer
        ↓
normalized portal evidence
        ↓
Device Fingerprint evidence storage
```

Показать, что Portal evidence является ещё одним origin, а не отдельным classifier.

---

# 12. Source Health

Очень важно не потерять всю проделанную работу с source-health.

Описать:

```text
evidence
+
source-health timeline
```

и смысл:

```text
нет evidence
```

НЕ всегда означает:

```text
устройство не имеет признака
```

Причиной может быть:

```text
source unavailable
source unknown
source outside coverage
schema unsupported
runtime origin disabled
```

Объяснить conservative semantics.

---

# 13. Binding / time model

Задокументировать:

```text
source binding timeline
clock policy
capture/source identity
Site binding
time windows
source-health coverage
```

Отдельно объяснить, зачем snapshot использует временное окно и почему evidence нельзя просто брать «последний ряд из таблицы».

---

# 14. Snapshot architecture

Подробно описать:

```text
EvidenceSnapshotContent
EvidenceSnapshotMaterialization
SourceEvaluability
```

и их разные обязанности.

Концептуально:

```text
retained evidence
       +
source health
       +
bindings/time rules
       ↓
consistent snapshot transaction
       ↓
EvidenceSnapshotContent
       +
verified materialization
       +
SourceEvaluability
```

Очень важно показать:

```text
SnapshotContentPolicy
!=
SnapshotExecutionPolicy
```

Semantic content ceilings отделены от operational execution limits.

---

# 15. Current memory policy

Current canonical production-aligned value:

```text
SnapshotExecutionPolicy.process_memory_guard_bytes =
1073741824
= 1024 MiB
= 1 GiB
```

Current artifact identity:

```text
SnapshotExecutionPolicy:v1:sha256:
36074993bb86daca8c43268c19ce0efab7e0e3ef5d644e07b9b6e65f5fff7f77
```

Историю:

```text
96 MiB
512 MiB
```

не представлять как current configuration.

96 MiB оказался операционно недостаточен.

512 MiB был промежуточным состоянием.

Final current policy:

```text
1 GiB
```

Это guard/threshold, а не reservation.

То есть worker не резервирует 1 GiB RAM.

---

# 16. Knowledge architecture

Отдельный большой раздел должен описать versioned knowledge layer.

На уровне архитектуры показать:

```text
ClassificationTaxonomy
AliasMapping
Knowledge sources
Knowledge provenance
Knowledge freshness
KnowledgeBundle
ClassificationPolicy
EvidenceAdapterContractSet
```

И принцип:

```text
classifier cannot silently use arbitrary external/current knowledge
```

Все knowledge dependencies должны быть versioned/pinned/auditable.

Точные K1/K2A/K2B/K3/K4 contracts и их ownership определить из current repository + FINAL R14.

---

# 17. Pure classification core

Это одна из самых важных схем.

Показать:

```text
EvidenceSnapshotContent
+
EvidenceSnapshotMaterialization
+
SourceEvaluability
+
KnowledgeBundle
+
ClassificationPolicy
+
knowledge_evaluation_at_utc
+
ClassifierArtifactManifest
        ↓
OriginAssessments
        ↓
Cross-Origin Fusion
        ↓
DimensionResults
        ↓
ClassificationResult
```

Обязательно подписать границу:

```text
PURE DETERMINISTIC CORE
```

Внутри pure core отсутствуют:

```text
DB access
network access
filesystem discovery
current-clock reads
mutable config reads
vendor schema reads
persistence
```

Это фундаментальный architectural property.

---

# 18. OriginAssessment

Разъяснить человеческим языком:

Каждый origin сначала оценивается отдельно.

Например:

```text
DHCP origin
Portal origin
TCP origin
TLS origin
QUIC origin
MAC Registry origin
```

Каждый origin может:

```text
provide candidate
provide no claim
be ambiguous
contain conflict
be unsupported/not evaluable
```

Только после этого выполняется cross-origin fusion.

Не писать упрощённую ложную схему:

```text
нашли User-Agent → Android
```

или:

```text
нашли DHCP → Smartphone
```

Это не описывает реальную архитектуру.

---

# 19. Cross-origin fusion

Обязательно объяснить, что:

```text
origins remain independent
```

Количество одинаковых строк от одного origin не превращается автоматически в множество независимых источников.

Fusion учитывает:

```text
claim strength
independent origin agreement
contradiction
same-origin ambiguity/conflict
cross-origin conflict
```

Результат dimension не является простым majority vote.

---

# 20. ClassificationResult

Задокументировать `ClassificationResult` как authoritative structured product artifact.

Он содержит:

```text
global classification status

platform_result
device_class_result
manufacturer_result
model_result
```

Для каждой dimension:

```text
canonical value
status
support level
supporting origins
contradicting origins
not-evaluable origins
out-of-scope references
explanation codes
knowledge references
```

Не превращать документацию в raw schema dump — дать отдельно:

```text
human explanation
+
exact engineering contract reference
```

---

# 21. Reproducibility / audit

Объяснить зачем существуют:

```text
ClassificationRequestManifest
ClassifierArtifactManifest
SnapshotRecord
ClassificationResult
RuntimeProfile lineage
```

Ключевая идея:

> Результат должен быть объясним и воспроизводим относительно exact evidence, knowledge, policy и classifier implementation identity.

---

# 22. ClassifierArtifactManifest

Документация должна объяснить, что production classifier привязан не к абстрактному «v1», а к exact executable identity.

В manifest входят exact implementation identities соответствующих adapters/core components.

Поэтому изменение classifier implementation bytes может потребовать новый admission lineage.

Это принципиально отличает:

```text
semantic classifier code change
```

от:

```text
Admin presentation-only change
```

---

# 23. Runtime profile architecture

Обязательно показать два уровня:

```text
FoundationRuntimeProfile
ClassificationRuntimeProfile
```

и их отношение.

Нельзя описывать систему так, будто worker просто читает «текущие настройки».

Production request pin-ит exact accepted ClassificationRuntimeProfile.

Этот профиль определяет exact semantic execution set.

---

# 24. Admission / activation

Отдельная схема должна показывать:

```text
Foundation artifacts
        ↓
Foundation admission
        ↓
FoundationRuntimeProfile

Classifier + policy + knowledge + foundation
        ↓
ClassificationRuntimeProfile candidate
        ↓
Task04 acceptance
        ↓
RuntimeProfileAdmissionManifest
        ↓
activation record
        ↓
active production profile
```

Показать:

```text
candidate
!=
accepted
!=
admitted
!=
active
```

Это важнейшая часть системы.

---

# 25. In-flight stability

Обязательно отразить R14 invariant:

После pin-а production ClassificationRuntimeProfile текущий request не должен повторно читать active profile pointer и собирать смесь старого и нового поколения.

Смысл:

```text
request starts
    ↓
exact profile generation pinned
    ↓
whole request uses same semantic generation
```

Даже если в процессе активирован новый safe profile, текущий request не меняется.

---

# 26. Persistence

Задокументировать отдельную classification SQLite.

Current production file:

```text
/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3
```

Также Device Fingerprint использует отдельные stores для своих областей.

Проверить current main / deployment и отразить фактически существующие:

```text
device_fingerprint_evidence.sqlite3
device_fingerprint_classification.sqlite3
device_fingerprint_control_plane.sqlite3
device_fingerprint_integration.sqlite3
```

Не утверждать путь только по этому handoff — подтвердить repository/runtime documentation.

---

# 27. History

ClassificationResult не «перезаписывает карточку».

Модель:

```text
Device
   ↓
same Site + MAC
   ↓
multiple Visits
   ↓
multiple ClassificationResults over time
```

Старые классификации сохраняются согласно retention/history contract.

Product UI получает current authoritative production classification.

---

# 28. Auth / integration architecture — Task05

Это должна быть отдельная подробная схема.

Показать:

```text
Guest connects
    ↓
Portal authorization
    ↓
Auth/session information persisted
    ↓
fingerprint integration job created
    ↓
job waits until due
    ↓
single durable worker claims job
    ↓
identity/session context resolved
    ↓
exact ClassificationRuntimeProfile pinned
    ↓
snapshot assembled
    ↓
classification executed
    ↓
ClassificationResult committed
    ↓
job becomes CLASSIFIED
    ↓
classification linked to device / visit where identity allows
```

Точные delay/window constants брать из current code/contracts.

Не копировать старые временные значения без проверки.

---

# 29. Device identity relation

Разъяснить:

```text
Device Card
```

и:

```text
ClassificationResult
```

не являются одной записью.

Они связываются через authoritative identity context:

```text
Site
MAC
device_id
visit_id where resolved
integration job
classification_id
```

Для UI Task06 current classification выбирается через:

```text
Site + observed MAC
```

с production-only semantics.

---

# 30. Same device on later visit

Документация должна пояснять:

При том же Site + MAC:

```text
existing Device identity
+
new Visit/session
+
new fingerprint classification opportunity
```

Старый результат не обязан уничтожаться.

Новый authoritative production result становится current presentation result.

Randomized MAC может означать отдельную Device identity, если нет отдельного доказанного linking mechanism.

Не обещать automatic cross-MAC identity linking, если его нет.

---

# 31. Task05 durable worker

Отразить production service:

```text
fingerprint-classification.service
```

Worker:

```text
durable
single-worker / current implementation
claim-based
retry/stateful
historical failures preserved
```

Job states и точные reason codes брать из current implementation.

---

# 32. Task05 performance incident и решение

Это важно сохранить как engineering history, но не перегружать README.

Исходный successful assembly:

```text
wall ≈ 248.5 sec
CPU  ≈ 247.9 sec
```

Профилирование показало CPU-bound repeated validation/rematerialization.

TASK-DEVICE-FINGERPRINT-05-PERF-01 устранил повторную KnowledgeBundle validation/rematerialization внутри одного request.

После изменения реальный production-shaped result:

```text
wall ≈ 32.35 sec
speedup ≈ 7.68x
reduction ≈ 86.98%
```

Семантика классификации не менялась.

Это должно попасть в detailed engineering history / performance section.

Не обязательно выносить цифры в главный README.

---

# 33. Memory-pressure incident

Обязательно зафиксировать историю корректно.

После PERF исправления live worker выявил:

```text
snapshot_memory_pressure
```

Причина:

```text
process_memory_guard_bytes = 96 MiB
```

Guard проверял весь process RSS, а реальная successful classification требовала существенно больше.

Это НЕ был:

```text
host OOM
classifier semantic regression
memory leak proof
```

Final operational policy:

```text
1 GiB
```

После этого свежая Owner phone classification:

```text
CLASSIFIED
attempt_count = 1
last_reason_code = empty
```

Старый failed historical row должен оставаться историческим evidence.

---

# 34. Task06 authoritative read

Task06 НЕ создаёт новый classifier.

Required current path:

```text
persisted PRODUCTION ClassificationResult
        ↓
DeviceFingerprintClassificationReadService
        ↓
typed presentation adapter
        ↓
Admin query/read model
        ↓
Home / Device Card
```

UI не классифицирует.

JavaScript не классифицирует.

Admin query не запускает classifier.

---

# 35. Production-only read semantics

Current product presentation должна брать:

```text
execution_context = PRODUCTION
```

Новый `PRE_ACCEPTANCE_CANDIDATE`, даже если он новее по timestamp, не имеет права shadow-ить production result.

Отразить это явно.

---

# 36. Batch Home read

Current Home implementation не должна делать N SQLite connections на N строк.

Отразить:

```text
bounded batch
maximum = 250 MAC inputs
canonicalize
deduplicate
one readonly SQLite connection/transaction
latest production result per MAC
```

Current implementation выполняет bounded grouped read, а не query-per-row.

---

# 37. Home current UI semantics

После Task06:

```text
Home → Online Devices
```

имеет два разных понятия.

## Type

Source:

```text
Device Fingerprint device_class
```

Examples:

```text
Smartphone
Laptop
Tablet
Unknown
—
```

## Platform

Source:

```text
existing controller / Omada device_type
```

Examples:

```text
Android
iOS
Windows
...
```

КРИТИЧНО:

```text
Type
!=
Platform
```

И:

```text
controller Platform
NEVER backfills fingerprint Type
```

---

# 38. Старый Device Type contract

Не удалить старую документацию о:

```text
device_type
device_type_key
Android icon
```

Но переразметить её.

Теперь это:

```text
Controller Platform
```

в product terminology.

Backend field compatibility может по-прежнему называться:

```text
device_type
device_type_key
```

То есть:

```text
backend historical field name
!=
new user-facing label
```

Не переименовывать документационно backend contract в несуществующее поле.

---

# 39. Device Card current UI

В Device Card теперь существует отдельный блок:

```text
Fingerprint Information
```

Он должен быть отражён в README/docs.

Summary:

```text
Status
Classified at
Type
Fingerprint Platform
Manufacturer
Model Family
support
```

Detailed/expandable diagnostic information может показывать:

```text
dimension status
support level
supporting origins
contradicting origins
not-evaluable origins
out-of-scope references
explanation codes
knowledge references
```

---

# 40. Controller Platform vs Fingerprint Platform

Это два независимых факта.

Device Card должен концептуально выглядеть так:

```text
Controller information
    Controller Platform = Android

Fingerprint Information
    Fingerprint Platform = Android / Unknown / other
```

Если значения расходятся:

```text
НЕ reconciliation
НЕ auto-correction
НЕ hidden override
```

Оба значения должны оставаться честно видимыми.

---

# 41. Fail-soft product behavior

Fingerprint является advisory data.

Failure fingerprint read path НЕ должен ломать:

```text
Home
Device Card core information
Auth
CAPPORT
traffic/current-state
```

Product semantics:

```text
fingerprint unavailable
        ↓
fingerprint fields = Unavailable / —
        ↓
rest of Admin continues
```

---

# 42. Real production smoke example

В current production Task06 smoke успешно прочитал реальный persisted result:

```text
classification_id =
35d644e0-b6ca-4f96-a6c2-c93a907f227c

ClassificationResult =
ClassificationResult:v1:sha256:
b8e905b3d4c1935558285a771a5495a1142fd10f0153a30577ff464be9bf961c

global status =
partial

Type =
Smartphone

Fingerprint Platform =
Unknown

Manufacturer =
Unknown

Model Family =
Unknown
```

Использовать это только как:

```text
production acceptance example
```

Не как hardcoded expected classification всех Android phones.

---

# 43. Waiting / unauthenticated devices

Owner после production deploy визуально увидел, что многие устройства, которые ещё не прошли соответствующий fingerprint lifecycle / authorization, имеют отсутствие fingerprint result.

Это нормальная ситуация.

Документация должна объяснять:

```text
waiting / no completed authoritative fingerprint
→ —
```

Не называть это classifier failure.

---

# 44. Security / privacy

Device Fingerprint должен быть описан как passive/advisory subsystem.

Обязательно зафиксировать:

```text
no auth decision from fingerprint
no CAPPORT authorization decision from fingerprint
no automatic client blocking
no destructive Omada action
```

Classifier результат не является security credential.

Также сохранить no-cloud principle текущего classifier path, если он подтверждается repository/accepted architecture.

Не писать secrets в документацию.

---

# 45. Site boundary

Все relevant Device Fingerprint reads/writes должны описываться как Site-scoped.

Не создавать впечатление глобальной:

```text
MAC → one universal identity
```

Current identity boundary учитывает Site.

Это важно для будущего Multi-Site.

---

# 46. Что обязательно обновить

Проведи inventory и измени все документы, где current truth устарела.

Минимальный ожидаемый scope:

```text
README.md
README_RU.md

docs/README.md
docs/project-inventory.md
docs/architecture.md
docs/module-index.md

docs/modules/device-fingerprint.md
docs/modules/device-fingerprint-portal.md
docs/modules/admin-web.md

docs/testing.md
docs/deployment.md
docs/security.md
```

Проверить дополнительно:

```text
docs/configuration.md
docs/decisions/*
docs/research/*
docs/deferred/*
AGENTS.md
.github/* instructions
roadmap/current-status documents
multi-site future documents
```

Изменять дополнительные файлы только если там действительно есть устаревшая current truth или отсутствует необходимая source-of-truth ссылка.

---

# 47. README.md — English

English README должен стать актуальной человеческой картой проекта.

Обязательно:

1. обновить repository checkpoint;
2. обновить production checkpoint;
3. добавить Device Fingerprint в Project at a glance;
4. отразить:

```text
Device Fingerprint =
production active
```

5. объяснить high-level:

```text
passive evidence
→ deterministic classifier
→ persisted result
→ Admin UI
```

6. обновить Home table:

старое:

```text
Type = controller device_type
```

больше не является current UI truth.

Новое:

```text
Type = Fingerprint device class
Platform = controller source value
```

7. добавить Device Card Fingerprint Information;
8. дать ссылку на подробную architecture/module documentation.

README не превращать в 1000-строчный R14.

---

# 48. README_RU.md — Russian

Русский README обновить синхронно с English README.

Это НЕ машинный перевод ради формальности.

Обе версии должны передавать одинаковый current architectural/product truth.

Обязательно проверить:

```text
commit/tree
task statuses
Home columns
Device Card
production status
next-step wording
```

---

# 49. Старые README checkpoints

В current README сейчас остались старые production checkpoint значения вида:

```text
3dc857...
831265...
```

Нужно repository-wide проверить все подобные current-production references.

Если это исторический пример:

```text
preserve / label historical
```

Если это current status:

```text
update
```

Не делать blind global replacement SHA.

---

# 50. docs/architecture.md

Это главный architecture map.

Device Fingerprint теперь должен быть полноценной частью общей архитектуры CaptivPortal.

Нужно показать его связь с:

```text
Omada
Captive Portal Auth
Visitor / Device Registry
Visit Lifecycle
Current State
Admin Web
SPAN sensor
Fingerprint stores
Fingerprint worker
```

---

# 51. docs/project-inventory.md

Добавить фактический inventory:

```text
modules
services
entrypoints
DBs
worker
read boundaries
Admin consumers
tests
configuration
production state
```

Repository inventory должен соответствовать exact current main.

---

# 52. docs/module-index.md

Device Fingerprint больше не должен выглядеть как obscure optional foundation.

Добавить/обновить индекс на:

```text
Evidence Foundation
Portal Evidence
Classification
Integration Worker
Admin Presentation
```

Если текущая структура документов использует один consolidated module document — индексировать его подразделы.

---

# 53. docs/testing.md

Разделить:

```text
historical acceptance evidence
current regression commands
production smoke
```

Не писать, что full suite был запущен на production.

Этого НЕ было и НЕ должно быть.

Зафиксировать последние relevant acceptance facts:

```text
Task05 PERF candidate full repository:
5198 passed
28 skipped

Task06 focused:
189 passed

Task06 R1:
22 passed
```

Но чётко подписать даты/кандидаты и не выдавать их за автоматически текущий HEAD full-suite gate после любых будущих изменений.

---

# 54. docs/deployment.md

Добавить/проверить operational facts:

```text
fingerprint-classification.service
classification DB
integration DB
control-plane DB
evidence DB
1 GiB current memory guard
exact-code deploy principle
```

Preserve project rule:

```text
no local production source patch
```

И:

```text
no full pytest on production
```

---

# 55. docs/security.md

Добавить Device Fingerprint boundaries:

```text
Admin-only presentation
Site authorization
read-only UI boundary
fingerprint does not authorize users
fingerprint does not block clients
no query-time external cloud classification
secrets not persisted in knowledge docs
```

---

# 56. Roadmap

Current roadmap/status должен быть обновлён так, чтобы:

```text
TASK-DEVICE-FINGERPRINT-04 = CLOSED
TASK-DEVICE-FINGERPRINT-05 = CLOSED
TASK-DEVICE-FINGERPRINT-05-PERF-01 = CLOSED
TASK-DEVICE-FINGERPRINT-06 = PRODUCTION PASS
```

Если roadmap имеет более подробные Foundation/03A/03R2 stages — сверить весь блок с Git/main и accepted evidence.

Не оставлять старое:

```text
Task04 HOLD
```

как current status.

---

# 57. Новый Traffic Enrichment initiative

Owner уже передал Architect отдельную инициативу:

```text
Device Traffic Enrichment / Device Intelligence
```

Она должна использовать уже существующий SPAN traffic для будущего обогащения Device Card:

```text
traffic history
protocols
services
current activity
network quality
behavior
security/anomaly signals
```

Это FUTURE initiative.

Не смешивать её с завершённым Device Fingerprint.

Правильная документационная модель:

```text
Device Fingerprint
= current production capability

Device Traffic Enrichment
= next/future architecture work
```

---

# 58. ОБЯЗАТЕЛЬНАЯ ВИЗУАЛИЗАЦИЯ

Это критически важная Owner requirement.

Документация Device Fingerprint НЕ принимается, если человек должен читать Python-код, чтобы понять, как система работает.

Все основные схемы должны быть:

```text
human-readable
GitHub-renderable
editable as text
```

Предпочтительный формат:

```text
Mermaid
```

Если Mermaid невозможно использовать в конкретном документе — допускается другой repository-native text diagram, но не заменять все схемы PNG-картинками без исходника.

---

# 59. Обязательная схема №1 — Full End-to-End

Нарисовать всю цепочку:

```text
Client device
    ↓
Wi-Fi / Omada
    ↓
SPAN mirror
    ↓
Network Sensor
    ↓
Normalized Evidence
    ↓
Evidence DB
    ↓
Snapshot
    ↓
SourceEvaluability
    ↓
OriginAssessments
    ↓
Fusion
    ↓
ClassificationResult
    ↓
Classification DB
    ↓
Task05 Integration
    ↓
Device identity / Visit
    ↓
Task06 read model
    ↓
Home + Device Card
```

Отдельно на схеме показать Portal evidence path, который входит в Evidence layer не через SPAN.

---

# 60. Обязательная схема №2 — Evidence Sources / Origins

Сделать блок-схему:

```text
DHCP --------\
TCP ----------\
TLS -----------\
QUIC ------------> Snapshot → OriginAssessments
Portal ----------/
MAC Registry ---/
```

Но подробно показать:

```text
physical/network origin
portal/application origin
knowledge-based MAC registry origin
```

и какие пути могут быть:

```text
available
unavailable
unsupported
disabled
unknown
```

---

# 61. Обязательная схема №3 — Evidence + Source Health

Показать:

```text
Evidence rows
       +
Source Health timeline
       +
Binding timeline
       +
Clock policy
       ↓
SourceEvaluability
```

Визуально объяснить почему:

```text
absence of evidence
!=
negative evidence
```

---

# 62. Обязательная схема №4 — Snapshot Build

Нарисовать detailed snapshot flow:

```text
classification window
        ↓
one consistent SQLite read snapshot
        ↓
evidence selection
health selection
bindings
resource policies
        ↓
EvidenceSnapshotContent
        ↓
verified materialization
        ↓
SourceEvaluability
```

Показать отдельно:

```text
SnapshotContentPolicy
SnapshotExecutionPolicy
```

---

# 63. Обязательная схема №5 — Pure Classification Core

Это центральная схема документации.

```text
EvidenceSnapshotContent
Materialization
SourceEvaluability
KnowledgeBundle
ClassificationPolicy
EvidenceAdapterContractSet
ClassifierArtifactManifest
        ↓
6 OriginAssessments
        ↓
per-dimension candidate state
        ↓
Cross-Origin Fusion
        ↓
4 DimensionResults
        ↓
global status
        ↓
ClassificationResult
```

Вокруг pure core сделать визуальную границу и подписать:

```text
NO DB
NO NETWORK
NO CURRENT CLOCK
NO PERSISTENCE
```

---

# 64. Обязательная схема №6 — Per-Dimension Fusion

Для одной dimension показать:

```text
DHCP claim
Portal claim
TCP claim
TLS claim
QUIC claim
MAC Registry claim
        ↓
same-origin assessment
        ↓
cross-origin comparison
        ↓
resolved / unknown /
insufficient / conflicting /
recognized-out-of-scope
        ↓
support level
```

Схема должна объяснить, что это не majority vote.

---

# 65. Обязательная схема №7 — Knowledge and Policy

Показать:

```text
Taxonomy
Aliases
K1 / K2 / K3 / K4 knowledge
Provenance
Freshness
        ↓
KnowledgeBundle
        +
ClassificationPolicy
        +
EvidenceAdapterContractSet
        ↓
Classification Request
```

Точные K ownership и названия взять из current source/R14.

---

# 66. Обязательная схема №8 — Runtime Profile / Admission

Нарисовать lifecycle:

```text
Foundation artifacts
        ↓
FoundationRuntimeProfile
        ↓
Foundation admission
        ↓

Classifier candidate
+
Foundation profile
+
Knowledge
+
Policy
+
Adapters
        ↓
ClassificationRuntimeProfile
        ↓
Acceptance
        ↓
Admission Manifest
        ↓
Activation
        ↓
Pinned Production Profile
```

Обязательно показать:

```text
candidate
accepted
admitted
active
```

как разные состояния.

---

# 67. Обязательная схема №9 — Artifact / Audit Lineage

Human-readable схема:

```text
SnapshotRecord
        ↓
ClassificationRequestManifest
        ↓
ClassificationResult

plus references to:
KnowledgeBundle
ClassificationPolicy
ClassifierArtifactManifest
Runtime Profile
Activation/Audit lineage
```

Цель схемы:

> показать, почему результат можно воспроизвести и объяснить.

Не надо рисовать все 48 artifact types на одном нечитаемом графе.

Полный artifact graph можно дать отдельной engineering diagram.

---

# 68. Обязательная схема №10 — Post-Auth Integration / Task05

```text
Auth success
    ↓
Integration Job
    ↓
PENDING
    ↓
due
    ↓
LEASED
    ↓
worker
    ↓
identity resolution
    ↓
classification
    ↓
persist
    ↓
CLASSIFIED
    ↓
device / visit linkage
```

Добавить error/retry branch.

---

# 69. Обязательная схема №11 — Device History

Показать:

```text
Device
├── Visit #1
│   └── ClassificationResult #1
├── Visit #2
│   └── ClassificationResult #2
└── Visit #3
    └── ClassificationResult #3
```

И current selection:

```text
latest authoritative PRODUCTION result
→ current Device Card presentation
```

---

# 70. Обязательная схема №12 — Task06 UI Read Path

```text
Classification SQLite
        ↓
production-only read
        ↓
typed presentation adapter
        ↓
AdminQueryService
       / \
      /   \
 Home     Device Card
```

Home:

```text
Type = fingerprint
Platform = controller
```

Device Card:

```text
Controller Platform
+
Fingerprint Information
```

---

# 71. Обязательная схема №13 — UI State Semantics

Нарисовать decision flow:

```text
production result exists?
    |
   NO
    ↓
    —

   YES
    ↓
dimension resolved?
    |
   YES → value
    |
   NO  → Unknown

read unavailable?
    ↓
Unavailable
```

Это должно быть видно без чтения prose.

---

# 72. Обязательная схема №14 — Failure Isolation

Показать:

```text
Fingerprint sensor failure
Fingerprint DB failure
Classifier unavailable
Worker retry/failure
        ↓
Fingerprint degraded/unavailable
```

и параллельно:

```text
Auth continues
CAPPORT continues
Admin core continues
Traffic continues
```

где это соответствует current implementation/contracts.

---

# 73. Обязательная схема №15 — Production Components / Stores

Нарисовать runtime:

```text
captive-portal.service
fingerprint-classification.service

Evidence SQLite
Classification SQLite
Control Plane SQLite
Integration SQLite

Admin read consumers
```

Показать ownership каждого store.

---

# 74. Обязательная схема №16 — Current vs Future

Чтобы следующий архитектор не смешал два проекта:

```text
CURRENT
Device Fingerprint
    ↓
identity/classification data

FUTURE
Traffic Enrichment
    ↓
activity/traffic/quality/service history

Both
    ↓
richer Device Card
```

---

# 75. Требование к схемам

Для каждой схемы добавить:

```text
Purpose
Inputs
Outputs
Persistence boundary
Failure behavior
Authoritative owner/module
```

Схема без легенды недостаточна.

---

# 76. Не создавать одну гигантскую нечитаемую схему

Нужны:

```text
1 high-level overview
+
several focused detailed diagrams
```

а не один граф на 200 узлов.

High-level схема должна быть понятна человеку за 30 секунд.

Engineering diagrams могут быть глубже.

---

# 77. README diagrams

В README.md и README_RU.md желательно оставить только одну компактную high-level diagram:

```text
Evidence → Classification → Persistence → Integration → Admin
```

и ссылку:

```text
Full Device Fingerprint architecture →
docs/modules/device-fingerprint.md
```

Все сложные схемы — в docs.

---

# 78. Historical architecture R14

FINAL R14 является важнейшим архитектурным source.

Не копировать его полностью в current module docs.

Вместо этого:

```text
current module docs
= understandable explanation

R14
= exact normative engineering contract / provenance
```

Добавить ссылки между ними.

---

# 79. Historical docs

Не удалять доказательства:

```text
Task04 acceptance
Task05 acceptance
PERF-01
memory-pressure investigation
Task06 handoffs
```

если они хранятся как project evidence.

Но clearly label:

```text
HISTORICAL ACCEPTANCE EVIDENCE
```

если документ больше не является current source-of-truth.

---

# 80. Current docs must not contradict current production

После работы repository-wide search не должен оставлять current statements вроде:

```text
Device Fingerprint does not classify
```

без явного scope:

```text
TASK-01 Evidence Foundation itself does not classify
```

Также не должен оставаться current Home contract:

```text
Type = Omada/controller device_type
```

Нынешний user-facing contract:

```text
Type = Fingerprint device class
Platform = Controller value
```

---

# 81. Documentation language

Engineering identifiers оставлять exact:

```text
ClassificationResult
SourceEvaluability
OriginAssessment
ClassificationRuntimeProfile
```

В русском тексте рядом давать нормальное человеческое объяснение.

Не переводить class/schema names так, чтобы их нельзя было найти в коде.

---

# 82. Documentation for coding agents

После update новый coding agent должен суметь без чата ответить:

```text
Что такое Device Fingerprint?
Откуда приходят evidence?
Где они хранятся?
Как строится snapshot?
Что делает SourceEvaluability?
Какие origins есть?
Где лежит knowledge?
Как работает fusion?
Что хранится в ClassificationResult?
Как result связан с Device?
Когда запускается classification?
Как worker получает job?
Где хранится history?
Что показывает Home?
Что показывает Device Card?
Чем Controller Platform отличается от Fingerprint Platform?
Что означает — / Unknown / Unavailable?
Какой profile считается production-active?
Что требует admission?
Какие изменения требуют reacceptance?
Где граница fingerprint vs Auth/CAPPORT?
```

Если для ответа на эти вопросы агент вынужден читать исходный Python — knowledge update недостаточен.

---

# 83. Source-of-truth map

Добавить explicit table примерно такого типа:

```text
Area                           Current source of truth

High-level project             README / docs/README
Project architecture           docs/architecture.md
Fingerprint module             docs/modules/device-fingerprint.md
Portal evidence                docs/modules/device-fingerprint-portal.md
Admin presentation             docs/modules/admin-web.md
Exact classifier architecture  FINAL R14 / current code
Current executable behavior    main source + tests
Deployment                     docs/deployment.md
Security                       docs/security.md
Testing                        docs/testing.md
```

Адаптировать реальные названия по repository.

---

# 84. Current production proof section

В detailed Device Fingerprint docs добавить небольшой раздел:

```text
Production status
```

без гигантского лога.

Достаточно:

```text
PR #178 merged
production exact merged tree deployed
Task06 smoke PASS
Portal active
Fingerprint worker active
Admin visual acceptance observed
```

И date:

```text
2026-10-04
```

---

# 85. Не вносить production secrets

Не документировать:

```text
OAuth secrets
Bearer tokens
passwords
private keys
session secrets
```

Даже если они встретятся во время inventory.

---

# 86. Не менять runtime code в этом TASK

Это documentation / knowledge synchronization task.

Expected:

```text
runtime behavior changes = NONE
schema changes = NONE
configuration changes = NONE
production changes = NONE
```

Если во время документации обнаруживается реальный code defect:

```text
STOP
report separately
do not silently repair it in documentation PR
```

---

# 87. Не «улучшать» архитектуру задним числом

Твоя задача:

```text
document current accepted system
```

а не:

```text
redesign current accepted system
```

Architectural improvement ideas поместить только в:

```text
Future / Deferred / Follow-up
```

---

# 88. Branch / candidate

Предлагаемый branch:

```text
docs/device-fingerprint-production-knowledge-sync
```

Работа должна быть documentation-only.

Не merge самостоятельно.

Не deploy.

---

# 89. Проверки

Так как это docs-only task:

обязательно:

```text
git diff --check
repository-wide stale-reference search
Markdown/Mermaid syntax sanity
internal relative-link validation where tooling exists
```

Full pytest не нужен автоматически для чистого docs-only change.

Если изменяются agent instructions или executable configuration — это уже другой scope и нужно сообщить Tech Lead.

---

# 90. Финальный handoff

Вернуть Owner + Tech Lead:

```text
BASE_COMMIT
BASE_TREE

BRANCH
COMMIT
TREE

FILES_INSPECTED
FILES_CHANGED

CURRENT_DOCS_UPDATED
HISTORICAL_DOCS_PRESERVED

README_EN_UPDATED
README_RU_UPDATED

DEVICE_FINGERPRINT_MODULE_REWRITTEN
ARCHITECTURE_UPDATED
PROJECT_INVENTORY_UPDATED
MODULE_INDEX_UPDATED
ADMIN_WEB_DOC_UPDATED
TESTING_DOC_UPDATED
DEPLOYMENT_DOC_UPDATED
SECURITY_DOC_UPDATED

DIAGRAMS_CREATED = <count>
DIAGRAM_INDEX = <list>

STALE_CURRENT_REFERENCES_FOUND = <count>
STALE_CURRENT_REFERENCES_FIXED = <count>
REMAINING_STALE_REFERENCES = <list / NONE>

RUNTIME_CODE_CHANGED = NO
SCHEMA_CHANGED = NO
CONFIG_CHANGED = NO

GIT_DIFF_CHECK = PASS/FAIL
LINK_CHECK = PASS/FAIL/NOT_AVAILABLE
MERMAID_SANITY = PASS/FAIL

PUSH = NO unless separately authorized
PR = NO unless separately authorized
MERGE = NO
DEPLOY = NO
```

---

# 91. Отдельный Diagram Index в базе знаний

Создать в Device Fingerprint document section:

```text
Architecture diagrams
```

с оглавлением:

```text
DF-01 End-to-End
DF-02 Evidence Origins
DF-03 Source Health & Time
DF-04 Snapshot Assembly
DF-05 Pure Classification Core
DF-06 Per-Dimension Fusion
DF-07 Knowledge & Policy
DF-08 Runtime Profiles & Admission
DF-09 Artifact / Audit Lineage
DF-10 Post-Auth Integration
DF-11 Device History
DF-12 Admin Presentation
DF-13 UI State Semantics
DF-14 Failure Isolation
DF-15 Production Components & Stores
DF-16 Current vs Future Enrichment
```

Названия можно улучшить.

Покрытие — обязательно.

---

# 92. Definition of Done

Работа считается законченной только если после неё новый инженер или AI-agent может открыть GitHub и визуально понять:

```text
откуда Device Fingerprint получает данные
↓
как проверяется доступность источников
↓
как строится snapshot
↓
как из evidence получаются claims
↓
как claims объединяются
↓
как появляется ClassificationResult
↓
как он сохраняется
↓
как он привязывается к устройству
↓
как попадает в Home / Device Card
↓
как система ведёт себя при ошибках
```

без необходимости сначала читать исходники.

---

# 93. Final current truth

После завершения этой документационной задачи база знаний должна однозначно говорить:

```text
DEVICE FINGERPRINT =
IMPLEMENTED
ACCEPTED
INTEGRATED
PRODUCTION ACTIVE
VISIBLE IN ADMIN UI
```

и одновременно сохранять важнейший invariant:

```text
Fingerprint is advisory.

It does not authorize the guest.
It does not control CAPPORT access.
It does not automatically block the client.
It produces reusable structured device intelligence.
```

Это и есть current production state, который теперь должен стать частью постоянной базы знаний CaptivPortal.