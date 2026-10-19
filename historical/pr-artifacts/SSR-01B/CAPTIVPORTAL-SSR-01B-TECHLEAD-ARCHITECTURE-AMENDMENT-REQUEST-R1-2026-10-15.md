# CaptivPortal — SSR-01B / Tech Lead → Chief Architect
## Узкий запрос на архитектурное дополнение: восстановление Suricata после локального восстановления Sensor

**Дата:** 2026-10-15 (Asia/Baku)  
**Автор и владелец реализации:** CaptivPortal Tech Lead  
**Основание:** `SSR-01 Chief Architect ADR v1 FINAL`, особенно SSR-A02, A05, A09, A11, A12 и gates SSR-R01/R05.  
**Режим:** DESIGN / RESEARCH; **никакого Coder GO на изменение поведения, systemd GO, production GO, restart GO**.  
**Решение Owner:** продолжать исследование и лабораторную подготовку; выпускать прямое ТЗ Coder для обычных исправлений в пределах утверждённого контракта; если меняется архитектурный lifecycle-контракт — получить решение Chief Architect.

## 1. Точный предмет решения

Нужно обеспечить **локальное восстановление Suricata после непредвиденного падения и автоматического восстановления Fingerprint Sensor**, когда Sensor действительно создал корректный EVE-сокет и прошёл свои preflight. **Не менять** Auth/Omada/CAPPORT, Evidence, NI-01/02B/04, SQLite, схему данных и глобальную последовательность systemd. Не превращать planned stop в незапрошенное восстановление захвата.

Это **архитектурное дополнение**, а не уже разрешённый обычный bugfix: меняется семантика автоматического запуска/взаимного надзора между процессами; ADR §A12 прямо требует отдельного Architect scope amendment для локального auto-reattachment и любых новых systemd edge/startup logic/drop-in. Поэтому Tech Lead **не выдаёт implementation GO по SSR-01B до решения ниже**.

## 2. Подтверждённые факты (и границы вывода)

### 2.1. Установленный production-граф, Owner read-only `systemctl show`, 15.10.2026

- `fingerprint-sensor.service`: `active`, `enabled`, `Restart=on-failure`, `After=captive-portal.service`, `TimeoutStopUSec=20s`. Жёсткой зависимости от Core нет.
- `fingerprint-suricata.service`: `active`, `enabled`, `Restart=on-failure`, `After=fingerprint-sensor.service`, `BindsTo=fingerprint-sensor.service`, `PartOf=fingerprint-sensor.service`, `TimeoutStartUSec=90s`.
- Suricata `ExecStartPre`: до `1830s` ожидает Unix-сокет Sensor. Реальный systemd upper-bound `90s` потенциально прерывает такое ожидание; это **отдельная гипотеза**, не доказанный production incident.
- `network-metadata.service`: `Wants=fingerprint-suricata.service`, `After=fingerprint-suricata.service`; такой soft-trigger может инициировать старт при собственном запуске NI-01, но **не заменяет** обещание восстанавливать Suricata при падении Sensor.
- Main Auth не имеет `Requires/BindsTo/PartOf` на optional stack; не создавать обратную зависимость.
- Последний наблюдавшийся Suricata start `15:36:04 +04`, `Result=success`, `NRestarts=0`. Причина запуска не доказана; **не** утверждать, что реальная авария/неудачный reattach происходили на production.

### 2.2. Отдельная WSL/Linux Lab — воспроизведённая systemd-семантика

**Lab:** Ubuntu WSL 2, systemd `259`, отдельные `ssr01a-*` units, `/usr/bin/sleep`, без capture/Omada/доступа к production. Не является доказательством точного поведения целевой версии systemd на Ubuntu VM.

| Сценарий | Mock Sensor | Mock Suricata | Вывод |
|---|---|---|---|
| Explicit `restart Sensor` | PID 424 → 435 | PID 425 → 436 | Restart propagation подтверждена |
| Explicit `stop Sensor` | stopped | inactive | Stop coupling подтверждена |
| Later `start Sensor` only | active | inactive | Reattach не произошёл |
| Unexpected Sensor main SIGKILL + `Restart=on-failure` | PID 431 → 440, active | PID 0, inactive после 3 s | Автоматический reattach не произошёл в окне проверки |

**Не выполнены:** проверка именно целевого systemd, Suricata-only crash, настоящий EVE-socket/readiness, startup budget в соответствующей версии, sustained observations и полный R05 acceptance. `SSR-R05=PARTIAL`, `SSR-01B=ARCHITECTURE_AMENDMENT_REQUESTED`, не PRODUCTION DEFECT CONFIRMED.

## 3. Минимальные ограничения уже принятой архитектуры

1. `AUTH_INDEPENDENT`: Core/Auth не останавливается и не перезапускается из-за Sensor/Suricata.
2. `LOCAL_ONLY`: разрешено только локальное сопряжение Sensor↔Suricata; никаких каскадов NI/Evidence/Traffic/Classification.
3. `NO_FALSE_COVERAGE`: любое фактическое отсутствие захвата означает достоверный coverage gap; TLS/QUIC не объявлять usable до source/heartbeat.
4. `PLANNED_STOP_RESPECTED`: ручная остановка Sensor не должна тайно снова включать Sensor или Suricata.
5. `SURICATA_ONLY_STOP_POLICY`: нужно однозначно определить, допускается ли auto-recovery после запланированной остановки *только* Suricata, когда Sensor работает. Нельзя самовольно нарушить maintenance stop.
6. `NO_RESTART_STORM`: retries/backoff/StartLimit и readiness должны оставаться ограниченными, без петли от двух сервисов.
7. `EVIDENCE_SAFETY`: spool ACK-after-200, replay, source-health и NI durable cursor сохраняются.
8. `NO_GLOBAL_ORCHESTRATOR`: не вводить global controller, fixed sleeps и новый общий process manager.
9. `VERSION_COMPATIBILITY`: доказать работоспособность на версии systemd, реально установленной на production, до выбора directives.
10. `SEPARATE_RELEASE`: template/code PR → Lab gates → merge Owner → отдельное разрешение SysAdmin на installed unit → отдельная activation/rollback после freeze.

## 4. Вопросы, на которые требуется одно архитектурное решение Chief Architect

**SSR-B01 — Точная целевая семантика.** Подтвердить матрицу ниже или исправить её:

| Событие | Предлагаемая целевая политика |
|---|---|
| Full boot / оба enabled | Sensor получает socket/readiness; Suricata стартует при валидной локальной зависимости |
| Intentional `restart Sensor` | Сохранять совместный restart; без каскада на Core/NI |
| Intentional `stop Sensor` | Остановить Suricata; не возвращать до операционного старта/явного resume |
| Subsequent intentional `start Sensor` | **Вопрос:** автозапуск Suricata после socket-ready или отдельная команда оператора? Предпочтительнее auto-reattach, если операция означает возобновление Sensor; maintenance-протокол должен быть однозначен |
| Sensor process crash → local auto restart | Suricata reattach после валидного socket/readiness и только в допустимом bounded recovery |
| Suricata-only process crash | Её собственный local `Restart=on-failure`, без restart Sensor/Core |
| Intentional `stop Suricata` при active Sensor | **Вопрос:** оставлять остановленной (maintenance-aware) либо разрешать авто-возврат? Предпочтительнее уважать planned stop |
| Evidence 429/503/offline | Sensor spool/retry, без stop/restart capture pair |
| Socket permanently unavailable / bad config | bounded failure, no restart storm, marked degraded/unavailable; no silent source continuity |

**SSR-B02 — Назначение владельца восстановления.** Зафиксировать, кто инициирует reattach при Sensor auto-restart: systemd-only relation, локальный отдельный readiness/reattach actuator или Sensor application lifecycle. **Tech Lead рекомендует минимальный systemd-owned локальный механизм**, если он может доказать все negative scenarios; не выбирать directive по удобству без Lab.

**SSR-B03 — Дискриминация planned/unplanned.** Является ли обязательным разделить `systemctl stop Sensor`, explicit restart и auto-restart после crash? При положительном ответе какой семантический источник намерения разрешён (операционная процедура/units/job-type), без глобального coordination state?

**SSR-B04 — Нужен ли отдельный scope для timeout mismatch?** Можно ли рассматривать `TimeoutStartUSec=90s` vs inner socket wait `1830s` как самостоятельный `SSR-01B-2` лишь после воспроизведения на Lab target version, не смешивая его с reattach? Рекомендация Tech Lead: **да**; никаких заранее выбранных чисел.

**SSR-B05 — Approval boundary.** После принятия B01–B04 допускается ли Tech Lead выпустить **узкий implementation TASK** на repo-owned service template (и соответствующие Lab fixture/tests) без повторной архитектурной итерации, а installed systemd deployment оформить отдельным SysAdmin TASK с Owner GO? Рекомендация: **да**, при сохранении SSR-I01..I12 и всех R05/C1..C7 gates.

## 5. Выходной контракт Architect (коротко, достаточно решения)

Вернуть ответ `SSR-01B Chief Architect Amendment v1` с:

- `SSR-B01..B05`: однозначные принятые политики и ограничения; статус `ACCEPTED / MODIFY / HOLD`.
- Разрешённый тип механизма auto-reattach (`systemd local / local sensor-owned / none`), без обязательного выбора неиспытанной конкретной systemd директивы.
- Определение planned stop, restart and auto-recovery для Sensor и Suricata.
- Mandatory compatibility/negative test list; acceptance and rollback criteria.
- Явный `CODER_TASK_PREPARATION=YES/NO`; `CODER_IMPLEMENTATION_GO` остается за Tech Lead после доказательства Candidate и gate review. Production GO остаётся отдельным.

## 6. Дальнейшая ответственность Tech Lead (без дополнительного круга по неизменным деталям)

После Architect amendment:

1. Уточнить целевую версию systemd и перепроверить effective installed unit graph (read-only).
2. На изолированной Lab-модели соответствующей версии сравнить минимальные кандидаты, включая cold boot, restart, planned stop→start, Sensor crash, Suricata crash, socket absent/late, NI-01 Wants interaction, StartLimit/storm и source-health gap reporting.
3. **Если candidate не доказан — не выдавать GO Coder**. Если доказан — самому выпустить `TASK-SSR-01B-*` с exact allowed files, fixture/test assertions, rollback, acceptance и deadline behavior, без изменения DB/Auth.
4. Проверить Coder diff + focused tests; направить Owner официальный Central Lab gate только по установленной процедуре; дать ACCEPT/REJECT.
5. Внедрение systemd на production — отдельный later Owner/SysAdmin rollout после freeze и проверок, без автоматического deploy из PR.

### Статус

```
REQUEST=SSR-01B_LOCAL_SENSOR_SURICATA_REATTACH
ARCHITECTURE_AMENDMENT=REQUIRED
REPOSITORY_REVIEW=84b80376b13002d435be28eec98b91b9cbf71c63
PROD_INSTALLED_RELATION=AFTER+BINDS_TO+PART_OF
LAB_WSL_SYSTEMD_VERSION=259
LAB_CRASH_SENSOR_RECOVERS=YES
LAB_CRASH_SURICATA_REATTACH=ABSENT_IN_3S
TARGET_SYSTEMD_VERSION=UNVERIFIED
SSR_R05=PARTIAL
CODER_GO=NO
PRODUCTION_MUTATION=NO
RESTART=NO
```

**End — SSR-01B Chief Architect Amendment Request R1.**
