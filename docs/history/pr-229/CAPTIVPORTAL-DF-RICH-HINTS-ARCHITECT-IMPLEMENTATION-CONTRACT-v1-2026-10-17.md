# CaptivPortal — DF-RICH-HINTS-01
## Chief Architect → Tech Lead: Architecture & Implementation Contract v1

**Дата:** 2026-10-17 (Asia/Baku)  
**Решение:** **APPROVED — simple observed-hints presentation**  
**Исполнитель следующего шага:** Tech Lead составляет узкий Coder TASK; данный документ **не является Coder GO**.  
**Current GitHub `main` при review:** HEAD `c6db833952d8daabb8fccedb03a774f9277850b6`, TREE `a9ea6dbf7a19a843e34882ba68f70c8ff2b67d92`. Tech Lead перепроверяет baseline перед TASK.  
**Исходные материалы:** `DF-RICH-IDENTITY-ROOT-CAUSE-AND-ARCHITECTURE-HANDOFF-2026-10-17`; `DEVICE-FINGERPRINT-UI-CONSUMPTION-PRINCIPLE`; существующий R14.  
**Важное уточнение Owner:** службы Fingerprint и CaptivPortal намеренно остановлены для разбора полётов. **Это не дефект DF-RICH-HINTS-01, не основание для восстановления служб и не блокер проектирования.**

## 1. Что именно делаем

На странице **Admin → Devices → Device Card** оставить существующую **Fingerprint Information** (каноническую классификацию R14) неизменной и рядом показать небольшой **«Observed Device Hints / Наблюдаемые сведения»** из уже сохранённых нормализованных `portal_headers` evidence.

**Продуктовый смысл:** *«Что браузер устройства сообщил и что система сохранила, то показываем; не требуется доказывать, что Nokia — это Nokia».* Это **наблюдение/сообщение клиента**, а не новая проверенная классификация или device identity claim.

В первую очередь два поля:
- **Reported model / Сообщённая модель:** существующее `model_family`, например `Nokia G21`.
- **Reported OS / Сообщённая ОС:** `platform_family` вместе с `os_major` **из того же нормализованного v1 payload** (например Android + 13 → `Android 13`). Если `platform_family` отсутствует, показывать `OS major: 13`, **не** заимствовать платформу из R14, Omada или другой строки. Для v2, где нет `platform_family`, применяется то же правило.

Под полями компактно показывать **source** и **observed_at** («Получено из User-Agent · 16.10…»). Один ненавязчивый дисклеймер: *«Сведения из браузера устройства; не подтверждены классификатором»*. Без панели уверенности, голосований, таксономии, новых правил и перечня всех исходных заголовков.

## 2. Что уже доказано кодом и read-only исследованием

- `app/device_fingerprint/portal_schemas.py` содержит **строгую** проверку `portal_headers/1` и `portal_headers/2`, в том числе `model_family`, `os_major`, `model_source`, `os_major_source`; v2 schema support **не означает** разрешение на включение нового producer.
- `app/device_fingerprint/schema.py`: retained source `device_fingerprint_evidence` имеет `site_id`, `observed_mac`, `source_kind`, `feature_schema_version`, `observed_at`, `quality_state`, `payload_json`, `payload_sha256`; есть индекс `(site_id, observed_mac, observed_at, evidence_id)`.
- `app/device_fingerprint/payload_integrity.py:verify_persisted_payload()` умеет проверять persisted bytes/digest и поддерживаемую схему до materialization.
- `app/admin_web/query_service.py:device_detail()` уже авторизует `admin.read.device`, получает `device.canonical_mac` в точном Site и отдаёт существующий `result.fingerprint`; `app/admin_web/runtime.py` создаёт его read adapter; `app/admin_web/static/admin.js` рисует Fingerprint Information.
- Переданная bounded production выборка из последних 200 `portal_headers` строк: 119 с `model_family`, 198 с `os_major`, все v1. Это **не** реальное текущее состояние сервиса и **не** гарантия достоверности значений.

## 3. Один утверждённый read path

```
Authenticated GET /admin/api/v1/sites/<site_id>/devices/<device_id>
  → existing admin.read.device + resolved device.canonical_mac
  → optional read-only DeviceFingerprintReadService portal hint read
  → exact Site + exact canonical MAC + retained-time window
  → validate persisted payload integrity + existing portal schema
  → safe additive result.observed_device_hints
  → existing Admin Device Card
```

**Механизм V1 — выбран, альтернативы Coder не оставлять:**

1. Расширить `DeviceFingerprintReadService` **одним** специализированным readonly-методом `latest_portal_hints(...)`. Он использует уже существующий `open_read_only()`, не вызывает `initialize()`, не создаёт DB/WAL и не пишет метаданные. **Один** запрос при открытии Device Card, не при рендеринге списка устройств. SQL: `site_id=? AND observed_mac=? AND source_kind='portal_headers'`, временная граница не шире действующего evidence retention; порядок `observed_at DESC, evidence_id DESC`, **LIMIT 16**. Не использовать безграничное чтение или ascending-пейджинг до самого нового элемента. Следовать existing Admin query deadline; при истечении — только hint `unavailable`.
2. Для этих максимум 16 кандидатов проверить неизменяемые `payload_sha256`, exact `feature_schema_version` и schema registry. Не интерпретировать raw User-Agent, Client Hints или JSON без существующей валидации. Если попалась запись с нарушенной целостностью — **hint unavailable**, без раскрытия payload и без подмены другими источниками.
3. **Выбирать последнее ненулевое значение каждого поля независимо**, чтобы новое OS-наблюдение не стирало более раннюю модель. Для каждого значения сохранить **его собственные** `observed_at`, `source`, `feature_schema_version`, `quality_state`; никакого объединения источников в одну «доказанную идентичность». Если в ограниченной выборке ничего нет — `no_evidence`. Если есть противоречащие значения — более поздняя запись для соответствующего поля, без заключений о конфликтной классификации.
4. Учесть известное `site_first_seen_at` устройства: не использовать evidence до начала известной Device identity в этом Site, даже если MAC позже переиспользован. MAC сам по себе не означает доказанный физически тот же телефон, а randomized MAC не склеивается.
5. Добавить компактную fail-open presentation-проекцию в `app/admin_web/device_fingerprint_presentation.py`, независимую от `FingerprintPresentation` и его R14 результатов. Композиция в существующем `admin_web/runtime.py` использует **configured evidence DB path** (`device_fingerprint_db_path`) и configured retention, а не жёстко прошитое имя файла. Если read adapter создать нельзя, Admin продолжает работать.
6. Расширить **существующий** `device_detail` DTO, не создавать endpoint, фонового worker или нового процесса. При частичном сбое возвращать нормальный Device Card + `observed_device_hints.state='unavailable'`.

## 4. Additive API DTO v1

В `result` существующего Device Detail добавить **только** новый optional объект (старые поля и версии не изменять):

```json
"observed_device_hints": {
  "state": "observed",
  "reported_model": {
    "value": "Nokia G21",
    "source": "user_agent",
    "evidence_schema": "portal_headers/1",
    "observed_at_utc": "2026-10-16T18:46:33.892Z",
    "quality_state": "valid"
  },
  "reported_os": {
    "platform_family": "android",
    "os_major": 13,
    "source": "user_agent",
    "evidence_schema": "portal_headers/1",
    "observed_at_utc": "2026-10-16T18:46:33.892Z",
    "quality_state": "valid"
  },
  "trust": "client_reported_unverified"
}
```

Пример **иллюстративный**, не production запись. Допустимые `state`: `observed`, `no_evidence`, `unavailable`. При отсутствии одного поля его значение `null`; при `no_evidence`/`unavailable` оба `null`. **Не возвращать** raw payload, заголовки, полный URL, IP, путь к БД, evidence rows, exception text, hash, producer credentials или новые MAC.

`reported_os.platform_family` заполняется **только** из того же payload, который дал `os_major`; для `portal_headers/2` он всегда `null`. Источники — существующие валидированные `model_source`/`os_major_source`, без придуманных confidence scores. Значения показывать как неинтерпретированный validated text, не создавать manufacturer из модельной строки.

## 5. Что строго НЕ меняем

- **R14/Fusion, K1–K4, taxonomy, confidence, canonical classification persistence, classification results и UI confidence/Status.** Ни одного upcast hint → `manufacturer_result`, `model_result` или `platform_result`.
- Действующий producer/admission `portal_headers/1`; `portal_headers/2` **не включать** и не менять маршруты его ingestion. Если v2 данные уже валидно существуют, read path их может отображать; в рамках задачи нет rollout v2.
- Fingerprint services, systemd, capture, Omada, CAPPORT/Auth, Sites, durable lineage, schema/SQLite, migrations, retention и checkpoints.
- Никаких таблиц, индексов, cron, фоновых задач, feature flags, карточек в Home, истории или new Settings.
- Устранение смешанных `knowledge_source_expired` explanation — **отдельная** задача `TASK-DF-DIAGNOSTIC-ORIGIN-ATTRIBUTION-01`, не смешивать с этой.

## 6. Scope для Tech Lead TASK

**Разрешённые production-файлы:**

- `app/device_fingerprint/read_service.py` — readonly bounded latest hints.
- `app/admin_web/device_fingerprint_presentation.py` — безопасная DTO-проекция.
- `app/admin_web/runtime.py` — композиция optional read adapter.
- `app/admin_web/query_service.py` — одно новое поле в существующем detail result.
- `app/admin_web/static/admin.js` — компактный блок в Device Card, safe text rendering.

**Разрешены** только соответствующие focused-тесты в `tests/device_fingerprint/`, `tests/admin_web/`, узкая поправка в `docs/modules/admin-web.md`. Не нужны изменения routes, DB schema, importers или добавление новых файлов-сервисов. Если Tech Lead на pre-code inspection обнаружит, что требуется существенно другая production область, `HOLD → Architect` вместо молчаливого расширения.

## 7. Тесты и критерии приёмки

**Coder: только focused tests и diff-check. Tech Lead: независимая full Windows/Linux и PERF/security проверка.**

Минимальные focused cases:

1. `portal_headers/1` validated `Nokia G21` + `android` + `13` → отображение «Nokia G21 / Android 13», provenance/UTC.
2. v2 supported payload `Nokia G21`, `13` без платформы → «Nokia G21 / OS major 13», **не** «Android 13» из R14/Controller.
3. Нет модели / нет версии / нет evidence → правильные `null` и `no_evidence`, отсутствие текстовых догадок.
4. Более поздние независимые поля не перезаписывают друг друга; ограничение `LIMIT 16`, retention, precise Site/MAC, `site_first_seen_at`, deterministic ties; никакой кросс-сайтовой утечки, переиспользованных MAC и чужих `device_id`.
5. Невалидная схема/хеш/JSON, SQLite unavailable/busy/deadline → hint `unavailable`; исходный `fingerprint`, identity, visits и API остаются работоспособны. Нет SQLite writer/open-create.
6. Длинные/опасные строки отображаются **только через text nodes**, не `innerHTML`; raw UA/headers не выдаются; numeric/nullable проверка.
7. Существующие R14 Device Card/Home snapshot, controller-first и status/support-level полностью неизменны.
8. Read-only query plan + bounded time and light I/O under no data / dense history. Никакого широкого запросного пути на странице Devices.

**Rollback:** source rollback к прежнему tree/коммиту по отдельному Owner production GO; DB rollback/migration не требуется (хранилище не изменяется). Если optional hint не работает, прежний Device Card продолжает показываться. Разрешение на Git PR/merge и отдельное разрешение на production — самостоятельные gates.

## 8. Передача полномочий

```text
TASK=DF-RICH-HINTS-01
ARCHITECT_VERDICT=APPROVED
IMPLEMENTATION_SHAPE=EXISTING_EVIDENCE_TO_EXISTING_DEVICE_CARD
R14_CLASSIFIER=FROZEN
NEW_DB=NO
NEW_SERVICE=NO
NEW_ENDPOINT=NO
NEW_PRODUCER=NO
SITE_BOUNDARY=STRICT
OBSERVATIONS=UNVERIFIED_CLIENT_REPORTED
CODER_TASK_PREPARATION=YES
CODER_IMPLEMENTATION_GO=TECH_LEAD_ONLY
FULL_WINDOWS_LINUX_PERF=TECH_LEAD_ONLY
COMMIT_PUSH_PR=HOLD_UNTIL_PUBLICATION_GO
MERGE=OWNER_ONLY
PRODUCTION_ACTIVATION=SEPARATE_OWNER_GO
CURRENT_PORTAL_STOP=OWNER_INTENTIONAL_RESEARCH_STOP
```

**Tech Lead:** сверить current HEAD/TREE, точный runtime path и доступность read-only Evidence DB в Lab, затем выпустить **одно узкое Coder TASK** по разделам 3–7. Не делать из этого новый этап классификации устройств.
