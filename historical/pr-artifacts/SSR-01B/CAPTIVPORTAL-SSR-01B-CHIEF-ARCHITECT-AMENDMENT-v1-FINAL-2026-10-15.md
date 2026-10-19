# CAPTIVPORTAL — SSR-01B
## Chief Architect Amendment v1 — Local Sensor → Suricata Reattachment

**Дата:** 2026-10-15 (Asia/Baku)  
**Инициатор:** CaptivPortal Tech Lead  
**Основание:** SSR-01 Chief Architect ADR v1 FINAL; `CAPTIVPORTAL-SSR-01B-TECHLEAD-ARCHITECTURE-AMENDMENT-REQUEST-R1-2026-10-15`  
**Репозиторный baseline для review:** `84b80376b13002d435be28eec98b91b9cbf71c63`  
**Статус:** `MODIFY → ARCHITECTURE_ACCEPTED / CONDITIONAL_IMPLEMENTATION_ADMISSION`  
**Owner:** DESIGN/RESEARCH ONLY. Production observation freeze остаётся в силе.  
**Важно:** Это архитектурное разрешение на локальную модель recovery, **не** Coder GO, не systemd/production GO, не гарантия дефекта на действующей VM.

---

## 1. Короткое решение

Разрешить минимальное **локальное systemd-owned auto-reattachment** `fingerprint-suricata.service` после подтверждённого запуска или автоматического восстановления `fingerprint-sensor.service`, включая cold boot и явный `start Sensor`, при выполнении всех условий:

1. Sensor действительно запущен, прошёл существующие preflight, и его **текущий EVE Unix socket** готов принимать Suricata; `ActiveState=active` для `Type=simple` и существование socket pathname сами по себе не дают доказательства готовности.
2. Нет действующего **явного локального maintenance inhibit** для Suricata.
3. Reattach не запускает/не перезапускает Sensor, Core/Auth, Evidence, NI, Classification или другие workers.
4. Нет бесконечной попытки или restart storm; все отказы и реальные интервалы недоступности захвата наблюдаемы.
5. Порядок действий и поддержка механизма доказаны на версии systemd, применяемой целевой Ubuntu VM, в изолированном Lab.

**Не** утверждать, что `After+BindsTo+PartOf` уже обеспечивают reattach при Sensor auto-restart. `PartOf` транслирует stop/restart-операции, но не является гарантией обратного старта; `BindsTo` не является механизмом самостоятельного включения Suricata после восстановления Sensor.

Постоянные инварианты `SSR-I01..I12`, gates `SSR-R01/R05` и `C1..C7` из SSR-01 ADR v1 сохраняются без изменения.

## 2. Подтверждённое и недоказанное

- По приложенному Tech Lead read-only current-state: Sensor и Suricata `active/enabled`, собственные `Restart=on-failure`; у Suricata `After+BindsTo+PartOf=Sensor`, а NI-01 имеет `Wants=Suricata` и `After=Suricata`.
- WSL/Linux Lab с systemd 259 подтвердил: явный restart Sensor приводит к перезапуску Suricata; явный stop Sensor останавливает Suricata; последующий start Sensor и auto-restart после SIGKILL **не** восстановили Suricata в проверенном окне.
- Это **подтверждённая Lab-проблема целевой семантики**, а не доказанный сбой production VM: точная версия systemd production и реальный end-to-end socket recovery пока не проверены.
- В repo-template Suricata pre-start ждёт socket до 1830 s; Tech Lead сообщает effective `TimeoutStartUSec=90s`. Возможное прерывание ожидания — отдельный незакрытый риск; не объявлять фактическим production-incident без воспроизведения.
- `Type=simple` Sensor может считаться активным раньше создания EVE socket. `After=Sensor` не эквивалентен `SensorEVEReady`.

## 3. Решения SSR-B01…B05

### SSR-B01 — Нормативная матрица событий

| Сценарий | Обязательное целевое поведение |
|---|---|
| Cold boot, обе службы enabled, нет inhibit | Старт Sensor; только после действительного socket/preflight допускается Suricata start/attach. Auth не ждёт эту пару. |
| Явный `restart Sensor` | Deliberate stop/restart Suricata сохраняется. После готовности нового Sensor Suricata возвращается без Core/NI cascade; старый EVE socket не считается новым. |
| Явный `stop Sensor` | Sensor останавливается, Suricata останавливается. Локальный reattach не инициирует возврат; для длительного удержания пары при независимых start jobs обязателен явный maintenance inhibit (B03). |
| Явный `start Sensor` после stop | Нормальное возобновление capture pair: Suricata запускается автоматически, **если** нет Suricata maintenance inhibit и readiness пройден. |
| Sensor неожиданно погиб, затем локальный auto-restart | Suricata не остаётся навсегда inactive; bounded reattach после корректного восстановления Sensor + socket. Отсутствие capture за время падения — реальный gap. |
| Suricata process crash при живом Sensor | Только собственный bounded `Restart=on-failure` Suricata; Sensor/Core не перезапускаются. |
| Явный `stop Suricata` при живом Sensor | Новый reattach-механизм **не** запускает её только потому, что Sensor уже active или socket существует. Для длительного maintenance stop требуется подтверждённый локальный inhibit (см. B03). |
| Evidence offline/429/503 | Не перезапускать capture pair; Sensor сохраняет spool/retry/ACK-after-200 в уже принятом контракте. |
| Socket отсутствует/битый/stale, плохая конфигурация или preflight failure | Нет ложной readiness; bounded unsuccessful start, понятные состояния; нет restart storm и невидимого silent recovery. |
| Suricata stop, NI-01 получает restart/start | `Wants=Suricata` не может обходить явно включённый maintenance inhibit; поведение без inhibit исследуется отдельно и документируется. |

**Auth/Core:** никогда не становятся зависимыми от этих переходов. **Source-health:** raw DHCP/SYN и Suricata TLS/QUIC различаются; отсутствие TLS/QUIC heartbeat не превращается в usable после возвращения одного PID.

### SSR-B02 — Владелец reattach и разрешённый тип механизма

**ВЫБОР: `SYSTEMD_LOCAL`, не app-owned, не global coordinator.**

Допустим минимальный локальный unit relationship/стартовая транзакция, инициируемая переходом Sensor в успешно восстановленное состояние. Tech Lead вправе проверить declarative start pull-in и/или узкий systemd-managed readiness trigger **только** в пределах Sensor–Suricata.

- Предпочтение: уже имеющиеся unit templates и systemd dependencies; ни сервисная mesh, ни новый демон надзора не нужны.
- **Не** переносить полномочие `systemctl start` внутрь непривилегированного процесса Sensor, не добавлять D-Bus/polkit escalation, cron-polling или таймер, который всегда перезапускает Suricata.
- `Wants=`, `PartOf=`, `BindsTo=`, `Upholds=`, `ExecStartPost=` **не утверждены как конкретная реализация**. Tech Lead обязан доказать выбранную комбинацию на целевой версии systemd и с реальным/эквивалентным socket lifecycle.
- Безусловное continuous upholding (`Upholds=` или эквивалент), которое поднимает Suricata после её явного maintenance stop, **не соответствует** B03.
- Никакого нового hard dependency в направлении Sensor → Suricata, который делает сбой Suricata отказом Sensor; не изменять Core/NI/Evidence units.
- Нельзя считать `test -S` единственным доказательством готовности: требуется отсутствие stale socket и проверка, что live Sensor действительно является его владельцем/consumer ready, в безопасной и воспроизводимой форме.
- `Sensor READY` и `Suricata healthy TLS/QUIC source` — **разные** состояния. Требования к actual heartbeat и durable source-health остаются прежними.

Если никакой ограниченный `SYSTEMD_LOCAL` кандидат не удовлетворяет матрице, Tech Lead возвращает `IMPLEMENTATION_HOLD` и точный отрицательный результат; не переключается самовольно на новый actuator/daemon/app-runtime код.

### SSR-B03 — Planned stop против automatic recovery

**Источник намерения — явная операционная процедура/локальное состояние systemd, а не догадка по PID или причине последнего exit.**

1. `systemctl stop Sensor` — намеренная остановка всей пары; сервисный `Restart=on-failure` не должен отрабатывать как реакция на эту stop job. **Новый локальный reattach** до явного resume запрещён. Однако `stop` сам по себе не гарантирует запрета **других start jobs**: NI-01 может затребовать Suricata через `Wants`, а Suricata `BindsTo=Sensor` имеет семантику, близкую к `Requires`, и способна вновь потребовать Sensor. Для долгого planned maintenance Sensor-пары нужен проверенный локальный inhibit, закрывающий эту цепочку; не считать голый `stop` вечным hold.
2. `systemctl restart Sensor` — намеренный restart обеих по локальному контракту; после preflight/socket обе могут вернуться.
3. Непредвиденная гибель Sensor — локальный automatic recovery; после успешного старта Sensor reattach разрешён.
4. `systemctl stop Suricata` — не должен немедленно отменяться механизмом reattach при неизменном работающем Sensor. **Для удержания Suricata выключенной через последующие Sensor/NI start-триггеры оператор обязан заранее оформить явный и проверенный maintenance inhibit**, затем stop, затем отдельный resume (снятие inhibit и контролируемый start).
5. Простой `stop Suricata` **без** такого inhibit не гарантирует длительную остановку при последующих чужих start jobs: уже существующее `Wants=Suricata` у NI-01 может повторно затребовать запуск. Нельзя скрывать этот факт под названием `planned stop respected`.
6. Конкретный локальный inhibit (например, поддерживаемый выбранной установкой systemd способ временно запретить start job) выбирает Tech Lead/SysAdmin **после** Lab-доказательства его эффективности, взаимодействия с установленными `/etc`/`/run` unit paths, собственного rollback и длительности на reboot. Не вводить новый глобальный coordination store. Не объявлять `mask --runtime` рабочим без проверки реального search-path precedence.
7. Если maintenance inhibit не может быть обеспечен без отдельной конфигурационной/инфраструктурной работы, **эту гарантию нельзя пометить PASS**: SSR-01B остаётся HOLD до узкого нового решения, либо до доказанной операционной процедуры. Coder не переопределяет planned stop сам.

### SSR-B04 — Timeout mismatch

**ACCEPT Separate `SSR-01B-2` / RESEARCH HOLD.**

`TimeoutStartUSec=90s` effective vs `ExecStartPre timeout 1830s` — самостоятельная гипотеза. Не менять `TimeoutStartSec`, socket-wait budget и числовые параметры в `SSR-01B-1` по предположению. Проверить действующую версию systemd, effective TimeoutStart/Stop, фазы start job и slow/missing socket в Lab на target-version.

**Если несогласованность реально срывает сценарий B01 или создаёт бесконечный reattach**, основной gate `SSR-01B-1=HOLD`; нельзя обходить обязательный negative test или выдавать PASS с caveat. Для исправления потребуется отдельный узкий `SSR-01B-2` contract/scope, сохраняющий safety и без придуманных timeout-значений.

### SSR-B05 — Делегирование подготовки задачи и release boundary

**`CODER_TASK_PREPARATION=YES_CONDITIONAL`.** Тому же Tech Lead разрешено завершить R01/R05 Lab, выбрать один доказанный minimal systemd-local механизм и **подготовить** Coder TASK, без дополнительного архитектурного круга при неизменном B01–B04.

**`CODER_IMPLEMENTATION_GO=NO` сейчас.** После R05 PASS, source/target parity и Tech Lead pre-code review он вправе выдать отдельный scope-limited GO для repo-owned unit templates, точечных Lab fixtures/tests и документации. Допустимы только файлы Sensor–Suricata service templates, соответствующие тесты/fixtures и deployment runbook; список конкретных путей определяет Tech Lead до GO. Новые helpers/oneshot units, изменение app lifecycle, NI-01 `Wants`, Core, Evidence, TLS, capture engine, DB, identity/lineage или введение нового persistent state — **RETURN TO ARCHITECT**.

Публикация PR, QA, merge Owner и установка live unit/drop-in — разные gates; SysAdmin-only изменения installed systemd требуют нового Owner GO после observation freeze.

## 4. Допуск реализации — обязательные Research/QA gates

### G0 — Installed version/graph parity (Owner-permitted read-only)

- Зафиксировать версию target systemd, actual `systemctl cat/show` обоих units, NI-01 `Wants`, reverse-dependencies, effective timeouts, RestartSec, StartLimit, active sockets, `ExecStart*`, drop-ins и deployed-vs-repo manifest; секреты/env содержимое не раскрывать.
- Зафиксировать exact candidate repository HEAD/TREE. WSL systemd 259 — полезное Lab evidence, но не target-version PASS.
- До разрешённого Owner read-only окна production не опрашивать.

### G1 — Positive matrix / causal readiness

- Full boot двух enabled units; `restart Sensor`, `stop Sensor → start Sensor`, Sensor SIGKILL + auto-restart; отдельно Suricata crash + собственное восстановление.
- Зафиксировать PID transitions, unit jobs, socket lifecycle, preflight, StartLimit, Suricata startup, actual EVE stats/heartbeat, TLS/QUIC source-health (сначала unavailable/gap, затем подтверждённо usable).
- **Контрпример:** Sensor `active` раньше EVE socket. До actual socket-ready Suricata не объявляется восстановленной; никакого stale pathname как proof.

### G2 — Negative matrix / operational intent

- Intentional `stop Sensor` не запускает Suricata через local reattach; подтверждённый длительный Sensor-pair maintenance inhibit блокирует также попытку NI-01 `Wants=Suricata` → Suricata `BindsTo=Sensor` поднять остановленную пару. No Core/NI/Evidence restart.
- Intentional `stop Suricata` при активном Sensor: отсутствие немедленного resurrection; sustained maintenance inhibit переживает Sensor auto-restart и новый NI-01 `Wants` start job до explicit resume.
- Socket absent/late/stale, failed Sensor preflight, Suricata bad config, stopped/failed units, start-limit saturation, repeated fast crash, manual restart interleaving не приводят к restart storm/false ready.
- Operator-controlled resume восстанавливает ровно нужную пару и снимает hold без оставления masked/failed units; сценарий reboot явно описан.

### G3 — Correctness, isolation, durability, observability

- Guest Auth/Omada/CAPPORT, Visit/Auth shutdown order, Evidence producer ACK-after-200, bounded spool, NI-01 durable generation/checkpoint/replay, NI-02B pending и NI-04 materialization без изменения.
- Реальные capture gaps не замаскированы. Raw DHCP/SYN и TLS/QUIC source health проверены раздельно; source stale не превращается в usable по `systemctl active`.
- Нет секретов в service stdout/journal/report; no new privilege escalation and no unsolicited network listen.
- Отдельно зафиксированы latency Auth, startup/recovery time, source gap, drops и HDD-like resource budgets в сопоставимых Lab сценариях. Меньший startup time сам по себе не равен PASS.

### G4 — Release / rollback

- Независимый QA на exact TREE; обязательный официальный Central Lab/release acceptance по актуальной политике проекта — отдельный gate; прежние `DEPLOY-CONFIG-01/02` exceptions не переносятся.
- Минимальный Git diff и тесты; owner-controlled PR merge; нет unreviewed installed drop-in drift.
- Перед будущим production: снимок/checksum effective installed units, план безопасного обратного применения **без очистки spool/SQLite**, операционная процедура on/off inhibit, acceptance/rollback с учетом source gap.
- Любой unexpected Core outage, повторные перезапуски, ложное health, backlog/data loss, неконтролируемый start Suricata при maintenance — gate FAIL / rollback.

## 5. Разрешённая граница и следующий handoff

**SSR-01B-1 scope:** только локальное systemd-owned reattach Sensor → Suricata и его testing/docs; сохранить текущие `After+BindsTo+PartOf` до проверенного изменения, отсутствие глобального side effect, ни одного production edit.

**SSR-01B-2 scope:** отдельно исследовать и при необходимости адресовать `90s / 1830s` start-budget mismatch — не включать автоматически в TASK SSR-01B-1.

**Tech Lead handoff:** представить target-version manifest, один Lab-verified вариант и таблицу G0..G4; если механика не доказана, дать `HOLD` вместо неиспытанной директивы. Затем оформить exact implementation TASK для Coder; production unit rollout — отдельный Owner/SysAdmin action после freeze.

### Exact machine-readable disposition

```text
TASK=SSR-01B
ARCHITECT_VERDICT=MODIFY_ACCEPT
AMENDMENT=SSR-01B_CHIEF_ARCHITECT_v1
BASE_ADR=SSR-01_v1_FINAL
PRODUCTION_DEFECT_CONFIRMED=NO
ALLOWED_MECHANISM=SYSTEMD_LOCAL_BOUNDED_REATTACH
OWNER_AUTHORIZATION=DESIGN_RESEARCH_ONLY
MAINTENANCE_INHIBIT=MANDATORY_FOR_SUSTAINED_SURICATA_ONLY_STOP
TARGET_SYSTEMD_PARITY=PENDING
SSR_R05=PARTIAL
SSR_01B_1=IMPLEMENTATION_ADMISSION_HOLD_PENDING_GATES
SSR_01B_2=TIMEOUT_RESEARCH_HOLD
CODER_TASK_PREPARATION=YES_CONDITIONAL
CODER_IMPLEMENTATION_GO=NO
PR_MERGE=OWNER_ONLY
PRODUCTION=OBSERVATION_FREEZE
SYSTEMD_INSTALL=NO
PRODUCTION_RESTART=NO
```

## 6. Evidence / source index

- Submitted Tech Lead SSR-01B Amendment Request R1, 2026-10-15, sections 1–6.
- Previously ratified `CAPTIVPORTAL-SSR-01-CHIEF-ARCHITECT-ADR-v1-FINAL-2026-10-15.md`, particularly I01..I12, A02/A05/A12, R01/R05, C1..C7.
- Repository at pinned `84b80376b13002d435be28eec98b91b9cbf71c63`: `deploy/device-fingerprint/fingerprint-sensor.service`, `deploy/device-fingerprint/fingerprint-suricata.service` and `app/device_fingerprint_sensor/{cli.py,runtime.py}`.
- Current systemd man pages: `systemd.unit(5)` (`BindsTo`, `PartOf`, `Wants`, `Upholds`, `After`); `systemd.service(5)` (`Type=simple`, `ExecStartPost`, `TimeoutStartSec`, `Restart`).
- Current target production systemd release/effective installed unit budget **not directly verified** by Chief Architect in this work; only Tech Lead's Owner read-only report is available.

**End of SSR-01B Architecture Amendment v1.**
