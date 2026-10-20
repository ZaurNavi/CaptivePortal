# CaptivPortal Admin Settings — Stage 2 Architecture Request

## Для Архитектора

Переходим к следующему этапу дорожной карты CaptivPortal Admin Settings:

**Stage 2 — Omada Controller Settings: Read Model**

Нужен **архитектурный контракт**, а не реализация и не Coder TASK.

После твоего документа Tech Lead должен иметь достаточно однозначных решений, чтобы Technical Developer Settings смог подготовить implementation TASK без самостоятельного изобретения архитектуры.

---

## 1. Подтверждённый baseline

Текущий repository / production baseline:

`main@9ca25fd3dc9d552d446be4669f2e67247dcb7a1b`

TREE:

`0ef5c4555fa254a8904f35e19c0570a5bbe8abe7`

**Settings Stage 1 уже принят и активирован в production.**

Имеется:

- GLOBAL Settings page;
- Settings Definition Registry;
- SQLite SettingsStore;
- immutable generations;
- configured/effective generation model;
- activation через `captive-portal.service` restart;
- GLOBAL policy capabilities;
- read/mutation Settings API;
- Settings UI.

Stage 1 остаётся архитектурным фундаментом и не должен дублироваться отдельной системой Controller Settings.

Roadmap следующий:

`Stage 1 → Stage 2 Controller Read Model → Stage 3 writable non-secret Controller settings → Stage 4 secret management`.

Текущая Omada-конфигурация включает как минимум:

- `OMADA_URL`
- `OMADA_ID`
- `OMADA_CLIENT_ID`
- `OMADA_CLIENT_SECRET`

Stage 2 — **READ ONLY**.

Никакой mutation Omada configuration на этом этапе.

---

## 2. Цель Stage 2

Требуется определить архитектуру:

**Admin UI → Settings → Controller**

которая безопасно показывает оператору текущее состояние конфигурации Omada Controller до того, как мы разрешим её изменение в Stage 3/4.

Это должен быть именно **coherent Controller configuration read model**, а не прямое отображение environment variables.

---

## 3. Сначала провести current-state source investigation

До принятия архитектурных решений проверь актуальный source на указанном baseline и документируй:

1. Где определены и откуда читаются:
   - `OMADA_URL`
   - `OMADA_ID`
   - `OMADA_CLIENT_ID`
   - `OMADA_CLIENT_SECRET`

2. Полный current configuration path:

   `process environment → app/config.py → app/settings.py:get_settings() → controller/provider composition`

   Проверь, соответствует ли фактический код именно этому пути и нет ли дополнительных независимых повторных чтений configuration.

3. Кто является текущим runtime consumer этих значений.

4. Когда эти значения snapshot'ятся:
   - process startup;
   - controller construction;
   - request/token operation;
   - либо другим способом.

5. Какие существующие validation rules уже применяются:
   - required/non-empty;
   - URL validation;
   - normalization;
   - SSL-related behavior;
   - иные Omada configuration constraints.

6. Какие текущие runtime objects уже содержат безопасную информацию, пригодную для read model, и где пришлось бы создавать новый read boundary.

Архитектура должна исходить из **фактического current source**, а не из предположения, что все Omada settings уже проходят через SettingsStore.

---

## 4. Зафиксировать authoritative source of truth для Stage 2

Нужен однозначный ответ:

**Откуда Controller Read Model получает свои данные?**

Рассмотри и выбери архитектурный вариант.

Например:

- из startup `settings` snapshot;
- через отдельный typed `ControllerConfigurationReadService`;
- через существующий Settings resolver/read model;
- через runtime controller/provider snapshot;
- иной вариант.

Запрет:

UI/API не должны самостоятельно читать:

- `os.environ`;
- `/etc/default/...`;
- systemd environment;
- `.env`;
- private fields provider'а;
- arbitrary configuration files.

Должен быть один явно определённый application/domain boundary.

---

## 5. Определить точный Stage-2 read model

Для каждого поля зафиксируй:

- canonical API field name;
- human UI label;
- тип;
- normalization;
- можно ли возвращать фактическое значение;
- source semantics;
- configured/effective semantics;
- unavailable/error semantics.

Минимально рассмотреть:

### Controller URL — `OMADA_URL`

Нужно решить:

- показывается полный URL или нормализованный representation;
- допустимо ли показывать scheme/host/port;
- считаем ли это NORMAL non-secret information;
- нужно ли скрывать какие-либо URL components;
- что показывать при invalid/missing configuration.

### Controller / Omada ID — `OMADA_ID`

Определить безопасное representation и semantics.

### Client/Application ID — `OMADA_CLIENT_ID`

Определить безопасное representation и semantics.

### Client Secret — `OMADA_CLIENT_SECRET`

**Raw secret категорически запрещено возвращать в API или HTML/JS.**

Нужно зафиксировать, что именно допускается, например:

`configured: true/false`

либо другой bounded status.

Не должно быть:

- masked substring реального secret;
- длины secret;
- prefix/suffix;
- hash;
- fingerprint, если он позволяет корреляцию без отдельной причины.

---

## 6. Configuration source semantics

Stage 2 должен подготовить модель к будущему Stage 3.

Определи, что означает поле вроде:

`source`

Возможные будущие источники:

- environment;
- SettingsStore persisted override;
- repository default;
- deployment-controlled source.

Но не вводи фиктивную детализацию, если current runtime сейчас не способен достоверно определить источник.

Нужно решить:

**показываем ли source уже в Stage 2, и если да — откуда он достоверно определяется.**

---

## 7. Configured vs effective semantics

Это критический вопрос.

Stage 1 уже различает:

`configured_generation`

и

`effective_generation`.

Но Omada Controller keys в Stage 2 ещё не являются writable Settings.

Поэтому зафиксируй:

1. Имеет ли смысл для Controller read model уже сейчас показывать:
   - configured value;
   - effective value;
   - либо только effective startup configuration.

2. Если configured/effective distinction пока неприменимо — так и зафиксировать, а не симулировать его.

3. Как модель должна эволюционировать в Stage 3, когда `OMADA_URL`, `OMADA_ID`, `OMADA_CLIENT_ID` станут SettingsStore-controlled.

Нельзя сделать Stage-2 API, который потом придётся семантически ломать ради Stage 3.

---

## 8. Controller connection / health status

Roadmap допускает connection/health только при наличии trustworthy semantics.

Нужно принять явное решение:

**входит ли connection/health в Stage 2 или нет.**

Если входит — определить:

- что конкретно означает `healthy/connected`;
- источник evidence;
- freshness;
- timeout/staleness;
- отличие configuration validity от runtime connectivity;
- отличие token/auth failure от network failure;
- поведение при Omada downtime;
- запрещён ли live probe непосредственно из GET UI request;
- возникает ли дополнительная нагрузка на controller.

Нельзя использовать:

`Controller object exists → Connected`

или

`configuration present → Healthy`.

Если достоверного bounded health model сейчас нет, предпочтительно Stage 2 оставить configuration-only и явно вынести Controller Health в отдельный следующий contract.

---

## 9. API contract

Определи canonical read API.

Нужно принять решение между, например:

`GET /admin/api/v1/settings/controller`

либо другим явно мотивированным вариантом.

Зафиксировать:

- authentication;
- authorization capability;
- response schema;
- API version;
- cache semantics;
- error model;
- request_id;
- no-store requirements;
- допускается ли endpoint при SettingsStore unavailable.

Stage 2 не должен использовать mutation endpoint.

Никаких `POST`, `PUT`, `PATCH`, `DELETE`.

---

## 10. Authorization model

Решить, какая capability требуется.

Не оставлять это Coder'у.

Рассмотреть:

- reuse `admin.read.settings.global`;
- либо отдельную capability вроде `admin.read.settings.controller`.

Нужно выбрать один вариант и объяснить, почему.

Controller Settings остаётся **GLOBAL**, не Site-scoped.

Не использовать default Site или `AdminSiteContextResolver` для имитации global authorization.

---

## 11. UI architecture

Зафиксировать canonical UX:

**Admin → Settings → Controller**

Определить:

- это отдельная sub-page или section существующей `/admin/settings`;
- canonical route;
- navigation;
- loading/error/unavailable state;
- representation секретного статуса;
- read-only visual semantics;
- нужны ли badges вроде Environment / Configured;
- что показывается при partial/missing configuration.

Stage 2 UI не должен содержать:

- Save;
- Edit;
- Replace Secret;
- Test & Save;
- Restart;
- Reconnect;
- Reauthenticate;
- systemd control.

Не создавать интерфейс, визуально обещающий mutation, которой архитектурно ещё нет.

---

## 12. Failure states

Нужна закрытая типизированная модель состояний.

Минимально рассмотреть:

- available / configured;
- partially_configured;
- missing_required_configuration;
- invalid_configuration;
- read_model_unavailable;
- secret configured/not-configured.

Если connection health входит — состояния connectivity должны быть **отдельны** от configuration state.

Не использовать одно размытое:

`status = error`.

Определи, что является:

- page-level failure;
- field-level unavailable;
- API 4xx;
- API 5xx;
- нормальным representable configuration state.

---

## 13. Security / secret boundary

Нужен отдельный раздел архитектурного контракта.

Зафиксировать минимум:

- raw `OMADA_CLIENT_SECRET` никогда не пересекает Controller Read API boundary;
- secret не попадает в browser HTML;
- secret не попадает в JS bootstrap data;
- secret не попадает в logs;
- secret не попадает в exception message;
- secret не попадает в telemetry/audit;
- API schema вообще не содержит поля для raw secret.

Stage 2 не должен вводить Secret Storage.

Это Stage 4.

---

## 14. Relationship with SettingsStore

Нужно явно решить:

Stage 2 read model **не должен создавать второй Controller settings database**.

Также не надо насильно записывать существующую Omada environment configuration в SettingsStore только ради отображения.

Определи, как Stage 2 использует уже существующий Settings infrastructure и что остаётся deployment-controlled до Stage 3.

Нужна совместимость с будущим переходом:

`environment → lower-precedence source`

`SettingsStore override → higher-precedence configured source`

без смены внешней семантики read model.

---

## 15. Runtime ownership / restart semantics

Определи ownership Omada configuration:

- какой process является activation target;
- когда Controller configuration становится effective;
- требует ли будущая mutation `captive-portal.service` restart;
- существует ли какой-либо legitimate hot reconnect path.

Для Stage 2 mutation нет, но архитектура read model не должна противоречить Stage 3.

По умолчанию roadmap предполагает restart-based activation и **не предполагает hot reconnect** без отдельного решения.

---

## 16. Stage-2 exclusions

Явно зафиксировать OUT OF SCOPE:

- изменение `OMADA_URL`;
- изменение `OMADA_ID`;
- изменение `OMADA_CLIENT_ID`;
- replacement `OMADA_CLIENT_SECRET`;
- Secret Storage;
- Controller reconnect;
- token reset;
- OpenAPI client creation/deletion;
- Omada controller configuration changes;
- Site-scoped Controller config;
- multi-controller support;
- generic environment editor;
- systemd/service controls.

Если считаешь, что какой-то пункт должен войти сейчас — требуется отдельное архитектурное обоснование, не silent scope expansion.

---

## 17. Multi-Site / future compatibility

Current Stage 2 — GLOBAL.

Но проверь, не закладываем ли мы API/model, который сделает будущий multi-site/multi-controller переход невозможным.

Нужен ответ:

- является ли текущий controller installation-level resource;
- должен ли read model иметь explicit scope/type;
- нужно ли уже сейчас избегать названий, предполагающих навсегда один controller.

Не надо реализовывать multi-controller сейчас.

Нужна только архитектурная совместимость.

---

## 18. Exact deliverable

Верни документ:

**`CAPTIVPORTAL-ADMIN-SETTINGS-OMADA-CONTROLLER-READ-MODEL-ARCHITECTURE-CONTRACT-v0.1`**

Статус:

**DRAFT FOR TECH LEAD REVIEW**

В документе должны быть:

1. source-verified current state;
2. architecture decisions;
3. exact scope / exclusions;
4. canonical read model;
5. exact API contract;
6. authorization contract;
7. UI/navigation contract;
8. secret/redaction contract;
9. failure-state model;
10. configured/effective/source semantics;
11. optional connection-health decision;
12. relationship to existing SettingsStore;
13. Stage-3 forward-compatibility constraints;
14. testable architecture invariants;
15. explicit unresolved questions, если после source investigation что-то действительно невозможно решить.

---

## 19. Required final disposition

В конце дай однозначно:

```text
ARCHITECTURE STATUS =

STAGE 2 SCOPE =

SOURCE OF TRUTH =

SECRET RAW DISCLOSURE =

CONNECTION HEALTH INCLUDED =

GLOBAL/SITE SCOPE =

SETTINGSSTORE RELATIONSHIP =

RESTART/ACTIVATION ASSUMPTION =

OPEN ARCHITECTURE P0 =

OPEN ARCHITECTURE P1 =

READY FOR TECH LEAD REVIEW =
```

Не пиши production-код.

Не составляй Coder implementation TASK.

Не расширяй Stage 2 до writable Controller configuration.

Если source investigation выявит противоречие между roadmap и фактическим current code — остановись на этом месте, зафиксируй evidence и предложи архитектурное решение, а не маскируй расхождение.
