# CAPTIVPORTAL — SSR-01: Startup / Shutdown / Recovery Orchestration
## Tech Lead → Chief Architect: архитектурный запрос / решение требуется

**Дата:** 2026-10-15 (Asia/Baku)  
**Автор и ответственный за дальнейшее исполнение:** **Tech Lead CaptivPortal**  
**Адресат:** Chief Architect CaptivPortal  
**Решение Owner:** подготовить регламент и архитектуру сейчас; **production остаётся в observation freeze**. Не менять systemd, код, runtime, БД, сеть, службы или режимы ресурсов до отдельного решения Owner после наблюдения.  
**Статус документа:** `ARCHITECTURE_RFI / TECHLEAD_RESEARCH_R1 / NOT_IMPLEMENTATION_TASK`  
**Исходный проект правил:** `CAPTIVPORTAL-STARTUP-SHUTDOWN-RECOVERY-PRELIMINARY-RULES-v0.1-2026-10-15.md` — предварительный материал, не утверждённый контракт. Настоящий документ — **единственный handoff для архитектурного решения по SSR-01**.

---

## 0. Запрос решения

Нужен **единый контракт жизненного цикла CaptivPortal** для **обоих** сценариев:

1. boot / shutdown всей Ubuntu VM, восстановление после crash/power-loss;
2. плановый/аварийный restart или недоступность **любой отдельной службы** при продолжающейся работе остальных.

Требование Owner: приоритет гостевой авторизации; исключить необязательную конкуренцию за HDD в момент старта/recovery; не создавать ненужные каскадные restart; очереди, replay, source health и metadata остаются корректными. **Не превращать это в принудительную цепочку задержек `sleep N` или обязательную последовательную загрузку всего приложения.**

**Chief Architect должен вернуть Architecture Contract/ADR с однозначным выбором политики и границ ответственности.** После архитектурного ответа **тот же Tech Lead, который направил этот документ**, проводит implementation review и формирует Coder TASK/инфраструктурный TASK, определяет QA/Lab gates и организует acceptance. Промежуточной передачи «ещё одному Tech Lead» нет.

## 1. Установленные факты и границы доказательств

**Контроль исходников:** изучен pinned repository `ZaurNavi/CaptivePortal@84b80376b13002d435be28eec98b91b9cbf71c63` (checkout, наблюдавшийся 2026-10-15). Шаблоны `deploy/...` и `docs/...` характеризуют **репозиторий**, а не доказывают байтовое совпадение каждого реально установленного production unit/drop-in или загруженного процесса. Актуальный current-state before implementation подлежит отдельной read-only сверке **после observation freeze**, при согласованном допуске. На текущем этапе **production не опрашивался и не менялся в рамках SSR-01**.

### 1.1. Подтверждённая модель процессов/источников

| Компонент | Функция и boundary | Факт / источник |
|---|---|---|
| `captive-portal.service` / `run.py` | Main composition root: Guest Auth, Omada provider, CAPPORT, Visit Lifecycle, Current State, Observation, Registry, Public Traffic, Admin | `run.py`, `docs/project-inventory.md` |
| `fingerprint-evidence.service` | Отдельный direct-TLS Evidence ingress + SQLite writer + maintenance, readiness после инициализации/валидации | `app/device_fingerprint/cli.py`; unit в просмотренных repo templates **не установлен** |
| `fingerprint-sensor.service` | Raw AF_PACKET, trusted DHCP/NI-02A attribution writer, bounded durable normalized evidence spool, delivery to Evidence | `app/device_fingerprint_sensor/{runtime,producer}.py`, `deploy/device-fingerprint/fingerprint-sensor.service` |
| `fingerprint-suricata.service` | Отдельный AF_PACKET consumer; TLS/QUIC и NI EVE | `deploy/device-fingerprint/fingerprint-suricata.service` |
| `network-metadata.service` (NI-01) | Читает Suricata EVE file, durable SQLite checkpoint/replay, source health | `app/network_metadata/cli.py`, `docs/modules/network-intelligence.md` |
| `network-metadata-projection.service` (NI-02B) | Читает NI-01 source, trusted DHCP attribution и authoritative Registry, хранит derived projection с pending/late binding | `deploy/network-metadata-projection/network-metadata-projection.service`, `docs/project-inventory.md` |
| `network-service-recognition.service` (NI-04) | Background materialization; читает admitted evidence и projection, хранит materialized Service Intelligence | `deploy/network-service-recognition/network-service-recognition.service` |
| Другие workers | Fingerprint Classification/Integration, Traffic Projection, Visit/Cleaner/Snapshot и прочие — могут вносить startup I/O и иметь свои invariants | `docs/project-inventory.md`, PERF-IO-QUIET roadmap; **полная systemd-карта пока не установлена** |

Это не единый монолитный процесс. Не допускать ошибочного предположения, что `systemctl restart captive-portal` автоматически и правильно перезапускает всю аналитическую цепочку.

### 1.2. Уже существующее явное управление зависимостями

| Из репозиторного template | Текущая семантика и важное следствие |
|---|---|
| Sensor: `After=captive-portal.service` | Порядок начала стартовых job, **не доказательство готовности** Evidence/Guest Auth и не автоматический hard dependency |
| Suricata: `After=`, `BindsTo=`, `PartOf=fingerprint-sensor.service` | **Уже существует частичная каскадная связь**: потеря/остановка и некоторые операции с Sensor затрагивают Suricata. Не объявлять blanket «никаких каскадов»; нужна осознанная оценка этой пары |
| Suricata `ExecStartPre`: ожидание Unix EVE socket Sensor до **1830 с**, затем Suricata config validation | Реальное ожидание готовности *конкретного сокета*, но не общий proof ingress/consumer readiness; возможен затяжной start и длительный coverage gap |
| NI-02B: `After=network-metadata.service fingerprint-sensor.service captive-portal.service` | Soft ordering; не значит «все downstream ready» и не подразумевает stop/restart on upstream failure |
| NI-04: `After=network-metadata-projection.service` | Soft ordering без health coupling |
| Шаблоны Sensor/Suricata/NI-02B/NI-04: `Restart=on-failure`, `RestartSec=30` | Уже есть локальная политика restart; следует проверить, соответствует ли она eventual readiness / sustained retry и не создаёт ли штормов |

**Важно:** exact live units + drop-ins (`After/Wants/Requires/BindsTo/PartOf`, `Restart=`, `Timeout*`, resource limits, environment) **пока не собраны**. Отдельные unit-файлы могут быть deployed вне репозитория. Никаких изменений по этим шаблонам без live reconciled manifest.

### 1.3. Важный контракт в `run.py` уже есть

Основной Core имеет **идемпотентный graceful shutdown**, а не простое убийство всех workers: остановка background scheduling, **остановка Visit scheduling ДО drain Auth executor**, закрытие Visit accepting ПОСЛЕ Auth drain, далее Snapshot drain/Registry final scan. Этот порядок — архитектурный инвариант; SSR-01 должен **наследовать**, а не заменить его «красивой» внешней очередностью systemd. Документация `docs/project-inventory.md` называет его нормативным, но часть её заголовочных SHA относится к более ранним версиям: применять именно к выбранной source baseline и перепроверять source-once-before-task.

### 1.4. Что доказал реальный инцидент 2026-10-14/15 — и чего не доказал

- Sensor spool ранее вырос до десятков тысяч событий; при доставке встречался HTTP **429 `concurrency_limit`** (в Evidence ingress — неблокирующая семафорная граница + `Retry-After: 1`); Sensor считает 429/500/503 transient и умеет retry/backoff. Это **не** доказательство, что первопричина — systemd boot order.
- Доставка восстановилась без очистки SQLite/рестарта: очередь от ~34 тыс. снизилась практически до нуля; NI capture health перешёл `stale → usable`, сохранив честную source-health семантику.
- Evidence имеет отдельно зафиксированный **read-heavy cold start / SQLite validation risk**; он требует readiness-admission и измерений, а не безусловного обхода в systemd.
- При низкой гостевой активности физический HDD продолжает иметь ~50–60% `busy` и повышенный `await`; это **steady-state small-I/O**. Отдельно существующий roadmap QIO-01..08 занимается producer-level write amplification. **Startup burst, backlog catch-up и steady-state не смешивать.**
- Для NI `capture_health` определяется по свежести TLS/QUIC source-health events (600 с). `service active`, TCP accept, «вчера был usable» и `queue=0` не эквивалентны полноценной source freshness.
- Shared HDD конкурирует не только с Portal VM: другие VM, journald, host-local writers и MicroK8s могут создавать I/O. Оркестрация только application-сервисов не решит всё disk contention; не обещать фиксированного эффекта.

### 1.5. Замороженные границы

- **Guest Auth/Omada/CAPPORT — первичный serving path.** Необязательные Fingerprint/NI не должны блокировать авторизацию; исключения — только доказанные авторизационные/safety dependencies.
- Единственные authoritative owners данных остаются прежними; для derived workers нужно **durable/replay** без продвижения курсора вперёд необратимо.
- Не стирать/очищать SQLite, spool, source-health, provenance, audit, pending NI-02B ради устранения очереди. `synchronous=FULL`, FS durability, checkpoint/replay остаются прежними.
- Не допускать ложного `ready/available`, если source stale/missing; `0 users` и `0 messages` сами по себе не доказывают ready.
- Остановка Sensor/Suricata реально прекращает passive capture — **coverage gap**, который нужно отмечать, даже если вся остальная система зелёная.
- Отдельные permissions для systemd/infrastructure TASK, repository application TASK и production operational action. Owner не разрешал реализацию/деплой/рестарт.

---

## 2. Техническая схема, представленная на решение архитектору (proposal, НЕ финальное решение)

```text
                         ┌──── Guest authorization / CAPPORT ────┐
Omada + Core readiness ──►│ serving readiness independent of NI   │
                         └───────────────────────────────────────┘

Mirror enp8s0 ──► fingerprint-sensor ──► durable bounded spool ──► Evidence API/SQLite
       │                  │                                  ▲
       └────────► Suricata (socket from Sensor)             │
                           │  └─ TLS/QUIC → Sensor ──────────┘
                           └─ DTI EVE file ──► NI-01 SQLite/checkpoint
Sensor trusted DHCP attribution DB ─┐           │
Core Registry authoritative read ───┼────► NI-02B projection/pending
NI-01 source ───────────────────────┘           │
                                                └──► NI-04 materialization
```

**Soft ordering** означает лишь порядок попыток старта. **Hard dependency** должна быть обоснована failure semantics и отдельно проверена на full boot и targeted restart. **Ready gate** — конкретное состояние потребителя, а не просто `ActiveState=active`. Допустимый partial/degraded запуск зависит от domain, capacity и честности источника.

### 2.1. Предварительные решения, которые Tech Lead рекомендует архитектору

1. **Не вводить новый orchestration daemon** на первом этапе. Сначала использовать systemd ordering/restart policy + уже существующий app readiness и bounded retry. Добавлять coordinator только при доказанном нетривиальном сценарии, который невозможно реализовать безопасно локально.
2. **Не делать глобальный hard dependency Sensor/NI → Auth.** Core-first — логическое приоритетное serving, не требование отложить всю acquisition до завершения backfill.
3. **Сохранить deliberate Sensor↔Suricata coupling**, пока не доказана необходимость изменения; проверить, что `BindsTo/PartOf` не приводит к непредусмотренным gap при targeted maintenance.
4. **Ставить ограничения именно на recovery/catch-up** по доказанным bottlenecks; не снижать throughput steady-state без нужды и не обещать сохранения всей raw capture при полной остановке Sensor.
5. **Разделить milestones:** Core serving ready; Evidence ingest ready; Sensor capture active; NI source continuous; derived materialized current; catch-up complete. Они не наступают одновременно.
6. **Изменения проводить пакетами по минимальной границе отказа**, чтобы в тесте было видно: поправили unit-order, consumer readiness или backoff — и какой именно эффект получили на физическом HDD.

---

## 3. Вопросы архитектору — решения обязательны (P0 до реализации)

Для каждого пункта просьба вернуть `DECISION`, `RATIONALE`, `INVARIANT`, `FAILURE/RESTART BEHAVIOR`, `ADMISSION/TEST`. Если данных недостаточно — **точный Research Gate + владелец evidence + критерий PASS**, а не отложить выбор на Coder.

**SSR-A01. Authority и границы orchestration.** Подтвердить, что единицей управления являются systemd units (и существующий lifecycle внутри Core), без нового coordinator. Где проходит граница между app-owned readiness и infrastructure-owned ordering? Кто имеет право инициировать graceful stop и restart: operator-only или возможны заранее ограниченные автоматические реакции? Как избежать неконтролируемой цепной остановки? Нужен точный change-scope.

**SSR-A02. Классификация dependency edges.** Для каждой пары `Core↔Evidence`, `Sensor↔Evidence`, `Sensor↔Suricata`, `Suricata↔NI-01`, `NI-01+Sensor+Registry↔NI-02B`, `NI-02B↔NI-04`, `Fingerprint Evidence↔Classifier`, `Core↔Traffic Projection`: `start-order-only | consumer-readiness gate | hard-runtime coupling | independent-fail-degraded`. Указать *что делать на stop/crash/restart* каждой вершины и какая потеря данных/coverage ожидаема. Особое внимание — существующие `BindsTo/PartOf` Suricata.

**SSR-A03. Core и authorization readiness.** Какие точные критерии «Guest Auth доступен», учитывая Omada недоступность, обязательную конфигурацию, Visit scheduling / Auth executor и внешнюю сеть? Как отличить HTTP response 400 без captive параметров и реальный auth-ready от «процесс слушает порт»? Никакой обязательной зависимости от NI/Fingerprint без явного доказательства.

**SSR-A04. Evidence readiness/cold start.** Какая минимальная доказанная стадия Evidence означает: «принимает valid normalized batches и может durable-ack»? Достаточен ли готовый HTTP endpoint / initialized writer, требуется ли завершение тяжёлой full-DB verification? Что делать Sensor, пока Evidence поднимается долго, и что считается startup timeout (не превращая в бессрочную остановку capture)? Не разрешать фиктивный ready.

**SSR-A05. Sensor↔Suricata lifecycle.** Подтвердить либо изменить **существующую** модель `BindsTo+PartOf+After`, долгий `ExecStartPre` wait socket (1830 s), роли EVE Unix socket и shutdown order. При каких остановках Sensor Suricata должна выключаться обязательно? Что должен показывать capture health при Suricata-only outage, при сохранённом raw DHCP/SYN и наоборот? Как оформляется coverage gap?

**SSR-A06. Sensor↔Evidence outage & spool policy.** Допустимо ли Sensor сохранять capture в durable spool при Evidence 429/503/offline? Если да — какие допустимые `max queued events/bytes/age`, state/alert thresholds и поведение при capacity exhaustion; кто источник этих порогов? 429 `Retry-After` сохранять семантически; отдельный предел concurrent ingestion и recovery-delivery. Что сделать при долгой недоступности так, чтобы не нарушить authority/replay и не захлебнуться на HDD?

**SSR-A07. NI-01 source/replay.** Требования к EVE file availability/rotation/partial-write, immutable generation, checkpoint и replay при Suricata restart и NI-01 restart. Продолжает ли NI-01 жить с `stale/unavailable` без Suricata? Когда readiness должны запрещать downstream читать/делать выводы, когда достаточно `pending/stale`? Не менять accepted NI-01-A/B статус.

**SSR-A08. NI-02B, NI-04, Classification, Registry.** При недоступности любого authoritative reader или partial DB readiness определить матрицу: продолжать с `pending`, остановить конкретный derived writer, держать last-good с TTL, либо fail-closed. Нужны границы late-binding/attribution replay и невозможность «unknown → positive» при missing source. Реальные healthy `backfill complete` не путать с near-zero CPU.

**SSR-A09. Ordered graceful shutdown vs fail-fast.** Зафиксировать сохраняемый порядок **внутри Core** из `run.py`; для auxiliary stacks определить порядок stop/acquisition→flush/spool→consumer writer без бесконечного ожидания. Что при `TimeoutStopSec` и SIGKILL? Как отражать незавершённые операции, а не falsely successful checkpoint? Гарантировать, что stop отдельных workers не ломает доступность Auth без необходимости.

**SSR-A10. Recovery scheduling и HDD budget.** Назвать **политику**, как допускается concurrent catch-up: fixed global concurrency? per-source bounded batches? priority classes? resource cgroup weights? Применяется ли throttle к replay только или ко всем workers? Принцип: именно Omada/Auth/CAPPORT первичны. Значения IOPS/CPU/latency — **измеряемые параметры Lab**, никаких придуманных production порогов. Указать fairness и отсутствие starvation/TTLs, недопустимость permanent backlog.

**SSR-A11. Distinct scenarios и observability.** Freeze domain state transitions для: `cold boot`, `ordered reboot`, `targeted restart`, `unexpected worker crash`, `consumer outage 429/503`, `slow HDD`, `unresponsive Evidence validation`, `queue near/full`, `EVE rotation`, `power loss`. Определить публичные и внутренние состояния: `starting / ready / recovering / degraded / stale / unavailable / gap / catch-up`. Кто является authority каждой метрики; `systemctl active` не заменяет её.

**SSR-A12. Release/rollback boundary.** Какая минимальная первая implementation slice? Возможен ли Phase 1 только unit-templates/readiness instrumentation без изменения data-plane и с feature/default-off? Какие части требует отдельного infrastructure task, а какие Coder application patch? Какой порядок reverse activation и rollback, что делать при ухудшении Auth latency или увеличении drops? Без миграций и очисток authoritative DB ради deploy.

### 3.1. Не блокирующие архитектурный ответ вопросы (P1 / Research Gate)

- **SSR-R01:** Полный unit/drop-in graph на установленном production после observation window: `systemctl cat/show` + active state + reverse dependencies; secrets/env values не выводить. Сверить deployed templates, не опираться на docs alone.
- **SSR-R02:** `Fingerprint Evidence cold-start` фактическая wall-time/CPU/physical read latency на **Lab**, включая large DB, empty DB, corrupted/partial DB, ресурсную конкуренцию. Не проводить провоцирующий restart на production.
- **SSR-R03:** Профиль boot-burst/catch-up/quiet/peak host `/dev/sda` и VM `/dev/vda` в сопоставимых окнах, отдельно journal/other VMs. Не складывать nested cgroup и host счетчики.
- **SSR-R04:** Реальные источники/единицы backlog: Sensor durable spool, NI-01 input generation, NI-02B pending attribution, NI-04 replay и Traffic Projection — независимые queues, не объединять в один численный «backlog».
- **SSR-R05:** Проверить возможность managed/readiness gating средствами текущих services/unit без нового приложения и без непредусмотренных stop propagation.
- **SSR-R06:** Уточнить какие части `docs/project-inventory.md`, `docs/modules/network-intelligence.md` являются историческим snapshot: например, документация по mirror VLAN10+20 **устарела** после Owner-authorized изменения на VLAN20-only; history нельзя выдавать за current truth.

---

## 4. Предлагаемая таблица ответов архитектора (обязательна в итоговом Contract)

| Edge | Start gate | On dependency stop | On restart | Buffer/data gap | Ready/unavailable authority |
|---|---|---|---|---|---|
| Core → Evidence (if actual edge) | choose | choose | choose | choose | choose |
| Sensor → Evidence | choose | choose | choose | bounded spool or stop | choose |
| Suricata ↔ Sensor | choose | choose | choose | capture gap | choose |
| NI-01 → Suricata EVE | choose | choose | choose | file/replay generation | choose |
| NI-02B → NI-01+attribution+Registry | choose | choose | choose | pending/late binding | choose |
| NI-04 → NI-02B+source | choose | choose | choose | materialized freshness | choose |
| Classifier/Integration → Evidence/Auth | choose | choose | choose | durable jobs | choose |

**В таблице недопустимы неопределённые значения вроде `restart dependent if needed` без определённого условия.** Если архитектурно остаётся выбор A/B, Architect выбирает одну политику либо вводит точный gate на недостающий факт.

## 5. Acceptance matrix, которую Tech Lead применит после Contract

| Gate | Обязательный результат |
|---|---|
| Correctness | Auth/CAPPORT/Omada contract неизменён; Visit/Auth shutdown invariant; source-health/stale/coverage честны; никакой потери confirmed evidence, неверного cursor или позитивной атрибуции без authority |
| Fault isolation | Targeted restart каждого изменённого unit без непредусмотренных каскадов и deadlock; Suricata↔Sensor deliberate coupling проверено отдельно |
| Restart/recovery | cold boot, full shutdown, failed Evidence ready, 429/503, spool limit, failed/partial EVE, NI lag, process crash, power-loss/replay — воспроизводимо на Lab |
| Performance | Равные сценарии/дистрибуции на HDD-like Lab: host completed IOPS, busy, await, guest cgroup, IO PSI, CPU, startup duration, Auth readiness latency, queue drain throughput, drops |
| Security & privacy | Не публиковать creds и полные payload; сохранение audit, source/site scope, TLS, spool permissions и fail-closed поведения |
| Operational | rollback tested; изменение манифеста/юнитов отдельно от приложения; не допускать persistent restart storm и «вечного запуска» |
| Owner gate | Отдельное решение для code merge, deployment, feature activation, systemd updates, production restart; green Lab ≠ разрешение менять production |

**Особый отрицательный gate:** улучшение одной метрики «время старта» или «меньше Disk Busy» не является PASS, если degraded скрывает отсутствие capture, queue не сходится, Auth медленнее или нарушен durable/replay contract.

## 6. План выполнения после ответа Chief Architect — ответственность Tech Lead

1. Получить `SSR-01 Architecture Contract / ADR` с explicit decisions SSR-A01…A12 либо точными Research Gates. Review against frozen contracts; при конфликте — architecture return.
2. Подготовить **Tech Lead Implementation Contract** с exact affected files, units and drop-ins, observability, feature/default-off if applicable, rollback, тестами. Разделить на минимальные пакеты, например `SSR-01A` manifest/readiness, `SSR-01B` targeted restart rules, `SSR-01C` bounded recovery scheduling **только если это реально требуется архитектурой**. Никакой автоматической реализации трёх пакетов без решения.
3. Передать Coder **точное TASK** на repo application/templates/test changes; инфраструктурные изменения с privileged systemd/VM доступны только SysAdmin/Operator по отдельному Owner authorization. Coder не получает полномочий менять production.
4. Провести code review, PRE-CODE PLAN gate, unit/integration fault-injection Lab и regression по точному Git SHA/TREE, включая already accepted Test Gate. Owner physically operates official Central Lab по проектным правилам.
5. После завершения observation window и отдельного Owner GO согласовать staged production; read-only baseline, один controlled change at a time, post-change matched evidence, explicit rollback.

**Сейчас:** никаких TASK для Coder на изменение поведения; никакого `systemctl`, live networking, data cleanup, migration или production restart. **Документ именно на решение Chief Architect**.

## 7. Source index / evidence provenance

Repository sources на pinned SHA `84b80376b13002d435be28eec98b91b9cbf71c63`:

- [`run.py` (graceful shutdown)](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/run.py#L93-L220)
- [`docs/project-inventory.md` (composition inventory)](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/docs/project-inventory.md)
- [`docs/architecture.md` (boundary / startup rules)](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/docs/architecture.md#L772-L797)
- [`docs/deployment.md` (NI process boundary)](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/docs/deployment.md#L12-L72)
- [`deploy/device-fingerprint/fingerprint-sensor.service`](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/deploy/device-fingerprint/fingerprint-sensor.service)
- [`deploy/device-fingerprint/fingerprint-suricata.service`](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/deploy/device-fingerprint/fingerprint-suricata.service)
- [`deploy/network-metadata-projection/network-metadata-projection.service`](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/deploy/network-metadata-projection/network-metadata-projection.service)
- [`deploy/network-service-recognition/network-service-recognition.service`](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/deploy/network-service-recognition/network-service-recognition.service)
- [`app/device_fingerprint/cli.py`](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/app/device_fingerprint/cli.py)
- [`app/device_fingerprint/api.py` (429)](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/app/device_fingerprint/api.py#L166-L179)
- [`app/device_fingerprint_sensor/producer.py` (retry)](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/app/device_fingerprint_sensor/producer.py)
- [`app/device_fingerprint_sensor/runtime.py` (Sensor lifecycle)](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/app/device_fingerprint_sensor/runtime.py)
- [`app/network_metadata/health.py`](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/app/network_metadata/health.py#L19-L51)
- [`docs/modules/network-intelligence.md`](https://github.com/ZaurNavi/CaptivePortal/blob/84b80376b13002d435be28eec98b91b9cbf71c63/docs/modules/network-intelligence.md)

Project materials: `CAPTIVPORTAL-PERF-IO-QUIET-LOAD-OPTIMIZATION-ROADMAP-v1.0-2026-10-15.md` (quiet/catch-up/cold start; immutable data safety), `ПАМЯТКА-АРХИТЕКТОРА-CAPTIVPORTAL.md` (lifecycle authority and contract format), `CAPTIVPORTAL-STARTUP-SHUTDOWN-RECOVERY-PRELIMINARY-RULES-v0.1-2026-10-15.md` (discussion basis).

---

```text
TASK=SSR-01
FROM=TECH_LEAD
TO=CHIEF_ARCHITECT
ARTIFACT=ARCHITECTURE_RFI_R1
OWNER_APPROVED=DESIGN_ONLY
PRODUCTION=OBSERVATION_FREEZE
REPO_INSPECTION=PINNED_84b80376b13002d435be28eec98b91b9cbf71c63
LIVE_SYSTEMD_UNIT_GRAPH=UNVERIFIED
ARCHITECT_DECISION_REQUIRED=SSR-A01..SSR-A12
CODER_GO=NO
PRODUCTION_CHANGE=NO
NEXT=CHIEF_ARCHITECT_ARCHITECTURE_CONTRACT_OR_EXACT_RESEARCH_GATES
TECH_LEAD_AFTER_RETURN=IMPLEMENTATION_CONTRACT_AND_CODER_TASK_WHEN_ADMITTED
```
