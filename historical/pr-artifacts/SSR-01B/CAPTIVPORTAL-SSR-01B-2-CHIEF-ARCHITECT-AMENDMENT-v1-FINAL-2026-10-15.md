# CAPTIVPORTAL — SSR-01B-2
## Chief Architect Architecture Amendment v1 FINAL — bounded Suricata recovery and live EVE socket readiness

**Дата:** 2026-10-15, Asia/Baku  
**Источник решения:** `CAPTIVPORTAL-SSR-01B-2-TECHLEAD-TO-CHIEF-ARCHITECT-GATE-BLOCKER-R1-2026-10-15(1).md`  
**Родительские контракты:** `SSR-01 Chief Architect ADR v1 FINAL` + `SSR-01B Chief Architect Amendment v1 FINAL`; их инварианты `SSR-I01..I12`, `SSR-B01..B05`, `G0..G4`, `SSR-R01/R05` и `C1..C7` остаются обязательными.  
**Reference code baseline:** repo review `84b80376b13002d435be28eec98b91b9cbf71c63`; наблюдавшийся на VM checkout `7e84bc563f1b6dd3d72da66ae25849d9a7d96540`, TREE `ea664b1d49ace86fc8a0c4ab2fc52945531e574a`. Это **не** подтверждение loaded-artifact каждого процесса.  
**Решение:** `SSR-01B-2 = MODIFY → ACCEPT_ARCHITECTURE`; `SSR-01B-1 IMPLEMENTATION ADMISSION = HOLD` до completion research/negative gates.  
**Owner scope:** DESIGN + LAB RESEARCH ONLY; production observation freeze сохраняется. Никакой команды запуска/остановки/редактирования служб этим документом не разрешено.

---

## 0. Итог для Tech Lead

Представленные данные достаточны, чтобы **утвердить узкое изменение архитектурного scope**: `SSR-01B-1` допускает локальное повторное подключение Suricata к Sensor, а `SSR-01B-2` дополняет его конечным recovery budget и проверкой **живого EVE Unix datagram receiver**. Дополнения можно оформить **единым ограниченным Coder TASK** только после закрытия pre-code Lab gates, не создавая глобальный orchestration-проект.

**Не доказано:** инцидент на production; end-to-end реальная Suricata 8.0.6/EVE/health; полное соответствие installed unit graph; достаточность любого конкретного timeout. Ни один из этих пробелов нельзя выдавать за PASS.

Принятая целевая цепочка:

```text
Sensor start/auto-restart → existing preflight → live EVE socket readiness
           │                                  │
           ├── local systemd soft start ──────┘
           │                         └─ Suricata ExecStartPre: live, non-sending AF_UNIX check
           │                              → real Suricata startup/EVE → heartbeat/health
           └── failure/timeout → bounded recovery episode → degraded/explicit operator recovery
```

При этом `service active`, `test -S`, successful Unix `connect`, Suricata PID, actual EVE heartbeat и NI `capture_health=usable` — **неэквивалентные** состояния.

## 1. Доказательная база и границы

1. Из Owner-provided read-only unit manifest: target Ubuntu `systemd 249.11-0ubuntu3.22`; Suricata `TimeoutStartUSec=90s`, `RestartUSec=30s`, `StartLimitBurst=5 / StartLimitInterval=10s`; внутренний socket wait `timeout 1830`; Sensor `Type=simple` и локальный `Restart=on-failure`.
2. Из эквивалентной по build WSL Lab: `Sensor Wants=Suricata` вместе с имеющимся у Suricata `After+BindsTo+PartOf=Sensor` в mock-сценариях восстанавливает пару после cold start, explicit start/restart и Sensor SIGKILL→auto-restart; отдельный Suricata SIGKILL не рестартует Sensor.
3. Два локальных operator-controlled `/run` hold-state под `ConditionPathExists=!…` в mock блокируют попытки NI-01 Wants и Sensor-generated start; production runbook и effective unit diff ещё не закрыты.
4. `test -S` пропускает pathname оставшегося сокета после остановки receiver; AF_UNIX datagram `connect()` в этом случае не прошёл. Наличие pathname **не доказывает bound live endpoint**.
5. При фиктивно уменьшенных Lab таймаутах startup deadline вызывает timeout и `Restart=on-failure` инициирует повторные попытки. Это доказательство **механизма**, а не скорости или количества рестартов на production.
6. При `RestartSec=30s` / `StartLimitIntervalSec=10s` ограничение `5 starts / 10s` **не является конечной квотой на весь эпизод восстановления**: редкие повторные старты могут не накопить 5 запусков за 10 секунд. Start limiting — window-based механизм, не универсальный lifetime counter. Условные start jobs также могут не засчитываться в лимит. Значит нельзя считать существующий `5/10s` достаточной защитой.

## 2. B2-Q01 — Restart/timeout: **APPROVE WITH EXPLICIT FINITE EPISODE**

**DECISION.** Повторные `TimeoutStartSec` + `Restart=on-failure`, которые при постоянной недоступности socket могут продолжаться без определённого предела, **нарушают** SSR-B02/B04 и `NO_RESTART_STORM`. Допускается ограниченное изменение retry/start-rate policy **только для Suricata**, под измеренную, документированную модель одного recovery episode.

**Обязательный контракт:**

- `Recovery episode` — серия попыток после конкретного cold start/explicit resume/restart/автоматического восстановления Sensor. Tech Lead обязан определить наблюдаемое начало/конец, кто сбрасывает бюджет, как отличить её от Suricata-only crash и не допустить обход квоты через новое автоматическое start job.
- При постоянно недоступном socket **число попыток и суммарное активное ожидание на один эпизод конечны**; длительность конкретного wait и порядок повторов измеряются. При исчерпании бюджета Suricata остаётся `unavailable/failed` либо явно `not started` с доступной диагностикой; Sensor и Core продолжают жить по собственным условиям.
- После исчерпания лимита не обещать позднее автоматическое восстановление только от того, что socket внезапно появился: без нового admissible trigger это не гарантируется. Допустимые способы возобновления: **операторский explicit resume/reset-failed/start** после проверки причин или новое **доказанное** событие старта/restart Sensor, если Lab подтверждает переинициализацию квоты без bypass maintenance inhibit. Если systemd этого не обеспечивает, честно документировать operator intervention, не добавлять тайный periodic poller.
- Не проектировать новый таймер/oneshot daemon/сервис только для сброса start limit. Не использовать `Restart=always`, слепое `StartLimitIntervalSec=0`, `TimeoutStartSec=infinity` или неограниченное ожидание.
- `StartLimitBurst`, `StartLimitIntervalSec`, `RestartSec` — единая проверяемая тройка. Лимит должен реально срабатывать для **медленных** timeout failure циклов, а не только для быстрых crash. Window должен охватывать нужное число реальных длительных попыток либо иной **подтверждённый на systemd 249** unit-only механизм создаёт эквивалентный конечный эпизод. Не полагаться на возможности более новых systemd (`RestartSteps`, `RestartMaxDelaySec` и т. п.).
- Не включать reboot/poweroff/failure actions при исчерпании лимита: `StartLimitAction=none` или функционально эквивалентная безопасная политика. Гостевой Auth не страдает.
- Два локальных planned-maintenance inhibit сохраняются; skipped `ConditionPathExists` и failure от socket readiness различать по статусам/журналу. Condition **не** заменяет физическую stop operation.

**Порогов в секундах и N attempts сейчас не утверждаю.** Выбирать их обязан Tech Lead из независимых измерений реального cold-start и медленного HDD, документируя границы и худший end-to-end recovery, а не «оптимальную» цифру из краткого mock-теста.

## 3. B2-Q02 — Несогласованность startup budgets: **APPROVE IN SSR-01B-2**

**DECISION.** Разрешить **именно в SSR-01B-2** research-driven корректировку Suricata `ExecStartPre` live socket wait, systemd `TimeoutStartSec`, `RestartSec`, `StartLimitIntervalSec`, `StartLimitBurst`, при необходимости явную запись безопасного `StartLimitAction` — в уже существующем `deploy/device-fingerprint/fingerprint-suricata.service`. Приобретённые параметры и их источник должны быть объяснены как согласованный budget. `fingerprint-sensor.service` можно менять только для **ранее утверждённого** soft `Wants=Suricata` и двух локальных condition/maintenance boundaries; **не** менять startup timeout, restart или StartLimit самого Sensor без нового Architect GO.

**Budget contract:**

1. Один start attempt не должен ждать дольше своего утверждённого конечного systemd start-budget; внутренний wait сокета должен заканчиваться **до** общего `TimeoutStartSec`, оставляя замеренный резерв для `suricata -T`, start/exec, preflight и scheduling на медленном диске. Должен быть согласованный верхний bound, а не `1830s` внутри `90s`.
2. Включить в бюджет **все** последовательные `ExecStartPre` операции, а не только EVE check. Если тайминг инициализации неизвестен, провести bounded Lab measurements.
3. Ограничить **число** failure/retry попыток и общий шум HDD/CPU. Изменение не должно вешать полный boot или откладывать Guest Auth из-за `After=` optional stack; проверить NI-01 `After=Suricata` на задержку её **собственного** старта без изменения NI-01.
4. Проверить корректное поведение при валидном позднем socket внутри бюджета, постоянно отсутствующем, stale inode, receiver crash после успешного `connect`, bad Suricata config, immediate crash, StartLimit saturation, manual resume, unit restart interleaving.
5. Предпочесть краткий bounded wait + доказанное ограничение новых попыток; не превращать readiness в бесконечное циклическое сканирование. Не использовать `systemctl` из подчинённых приложений.

Вычислимые значения `T_socket`, `T_other_preflight`, `T_start_total`, `T_restart`, `N_attempts` и испытанные cold/warm/P95/P99 latency — **evidence table Tech Lead**. Архитектурное требование: `T_socket + T_other_preflight + measured safety headroom < T_start_total` с конечными границами. Пересмотр чисел в рамках этих правил не требует нового архитектурного круга, но утверждается Tech Lead до implementation GO.

## 4. B2-Q03 — Live socket proof: **APPROVE, NARROW THREAT MODEL**

**DECISION.** В уже защищённом локальном runtime path разрешён **non-sending `AF_UNIX` `SOCK_DGRAM` `connect()`** из процесса `ExecStartPre` Suricata, под его существующим `User=suricata` и разрешённым `SupplementaryGroups`, в сочетании с systemd `After+BindsTo` и актуальным start/stop Sensor. Для указанной угрозы **stale/unbound socket inode** это достаточный startup barrier, если non-sending connect, permissions, negative tests и отсутствие фальшивого EVE признаны Lab PASS.

- `connect()` — проверка, что *сейчас* по pathname есть принимающий kernel socket, но **не** криптографическая identity attest, не надёжная гарантия PID/owner и не доказательство downstream EVE consumption. Не называть её полной `Sensor READY`.
- **Не требовать** кросс-пользовательское чтение `/proc/<PID>/fd`, D-Bus/polkit/root escalation, новую privileged API или send fake EVE frames. Если protected path допускает другого неавторизованного bind-ера либо kernel endpoint нельзя надёжно связать с управляемым Sensor через доступный unit/lifecycle, это **G0/G2 HOLD** и возврат с альтернативным минимальным доказательством.
- Разрешён **минимальный unit-local `ExecStartPre` inline probe** на имеющемся в deployment Python standard library `socket` (или эквивалентная установленная проверенная утилита), без нового helper-file/daemon/app module и без write/send по сокету. Команда, timeout, escaping, вызовы внешних бинарников и permission handling подлежат code review; не допускать бесконтрольного shell quoting или логирования приватных данных.
- Любая ошибка (not found, `ECONNREFUSED`, timeout, access denied, неверный socket type, Sensor stopped) → fail-closed, не запускать Suricata как будто EVE healthy. Poll с разумным bounded интервалом/таймаутом допускается в пределах B2-Q02.
- Между `connect`-проверкой и реальным запуском Suricata существует TOCTOU: при последующей гибели receiver Suricata/health обязаны деградировать естественным образом. **Никакой `usable` до реального EVE stats/heartbeat + source-health contract.** Отсутствие покета capture во время перехода — coverage gap.
- Исключён общий `Type=notify` рефакторинг Sensor и его application code: это иной lifecycle scope.

## 5. B2-Q04 — Research/QA admission: **APPROVE WITH NON-PROD END-TO-END GATE**

**DECISION.** Target-version `systemd 249.11-0ubuntu3.22` mock с живым `SOCK_DGRAM` доказывает **unit/job/budget primitives** и порядок socket binding, но не полноту реального EVE pipeline. Для Coder implementation GO и особенно до PR release acceptance Tech Lead должен закрыть две отдельные evidence categories.

### 5.1. Pre-code `G0 + R05` (допуск Tech Lead к точному Coder TASK)

- Получить Owner-allowed sanitized effective installed `systemctl cat/show` для Sensor, Suricata и NI-01, reverse dependency edges, drop-ins, unit startup timeouts, StartLimit, credentials paths **без secret contents**; сверить с repo template, зафиксировать `systemd 249`.
- В независимой Lab на **целевой версии** проверить положительный matrix: cold boot, sensor `restart`, `stop → explicit start`, sensor SIGKILL → local recovery, suricata-only SIGKILL; no Core/NI/Evidence restarts, process identity/stop propagation.
- Отрицательный matrix: stale and dangling socket, live-but-delayed socket, no socket beyond budget, EVE receiver exits after probe, wrong perms/owner, malformed socket path, bad config, saturating slow timeouts, skipped hold, pair-wide and Suricata-only hold through NI-01 `Wants`, manual resume, no unauthorized reattach.
- **Must prove numerically:** finite attempts/time budget on *permanently missing* socket and separate normal/slow disk-like startup; no claim `5/10s` is bound. Document exact unit fixture and observed start/restart count, status transitions and failure classification.
- Если конечный unit-only механизм не доказан или status/maintenance contract конфликтует, `SSR-01B-1=HOLD`, не передавать неиспытанный выбор в Coder.

### 5.2. Integration/equivalence `G1/G3/G4` (до release acceptance)

- В изолированной non-production Linux Lab проверить **реальный** Sensor + Suricata 8.0.6 + EVE socket/producer/heartbeat/source-health under restart and outage, **или** в случае отсутствия безопасного capture NIC получить заранее подписанный независимым QA `faithful EVE fixture equivalence protocol`. Fixture обязан эмулировать именно bind/unbind, datagram delivery/receiver failure, heartbeat/staleness, kernel/runtime delays; синтетический socket-only mock не покрывает всю цепочку и не считается достаточным.
- Если real NIC/capture невозможно, не создавать искусственных production faults. Допускается bounded, non-production EVE fixture **только для проверяемых контрактов**; непокрытые реальные kernel/Suricata semantics явно оставить как `UNPROVEN`, а соответствующий production activation gate — `HOLD` до отдельной разрешённой проверки.
- Отдельно измерить cold/slow start, HDD-like I/O contention, recovery latency, start attempts, EVE loss/coverage gap, source-health stale/unavailable→usable после heartbeat, durable spool ACK-after-200 (без изменения); preserve NI-01 source-generation/checkpoint and replay.
- QA на exact candidate TREE; действующий официальный Central Lab и прочие обязательные release gates не обходить. Прежние differential exceptions `DEPLOY-CONFIG-01/02` не распространять на SSR-01B.
- До PR/merge/deploy: Tech Lead signed acceptance report; Owner approval — отдельно. **Production observation freeze**; никакой установки live units/drop-ins до отдельного SysAdmin TASK/Owner GO.

## 6. Границы реализации и запреты

**Разрешённые production repo-файлы:** только

1. `deploy/device-fingerprint/fingerprint-sensor.service` — soft Sensor `Wants=Suricata` и рассмотренные maintenance condition(s), без нового strong dependency или изменённого Sensor runtime/restart policy;
2. `deploy/device-fingerprint/fingerprint-suricata.service` — existing `After+BindsTo+PartOf`, conditions, live datagram socket guard и measured finite wait/start/retry/start-limit policy.

**Прочее в разрешённом scope:** непосредственно связанные tests/fixtures и deployment/rollback runbook. Не вводить новые systemd service/target/path/timer units, helper files, приложения или библиотеки. Не менять `run.py`, Core/Auth, Omada, CAPPORT, Evidence API/SQLite, Sensor application runtime, `network-metadata`/NI-01/02B/04, Suricata config/AF_PACKET/BPF, `fingerprint-*` algorithm/health semantics, production spools/DB, certificate/token stores, network/VLAN, cgroup/resource quotas.

**Inhibit policy из SSR-01B v1 остаётся:** pair-wide и Suricata-only hold под `/run`, создать hold *до* stop, затем stop target; `ConditionPathExists` предотвращает только будущий start job. Volatile hold теряется после reboot. Эта семантика должна быть изложена без обещания долгой блокировки через power-loss; если нужен persistent inhibit, отдельный Architect/Owner scope.

**Граница systemd:** unit source diff → target-version Lab → Coder QA → official release gate → Owner merge; installed unit diff/drop-in deployment → отдельный SysAdmin/Owner authorization → postdeploy verification и rollback. Смешивать нельзя.

## 7. Handoff, критерии возвращения и machine disposition

Tech Lead вправе выполнить исследование, создать **один** уточнённый TASK `TASK-SSR-01B-1+2` после **G0/R05 PASS**, с точными файловыми границами, измеренными числовыми параметрами, фикстурами и negative tests. Coder может получить implementation GO **только** от Tech Lead после pre-code review; архитектурное решение само GO не даёт.

**Возврат Chief Architect (не выбирать самостоятельно):** требуется новый Python/application модуль, отдельный helper/file/oneshot unit, системный timer/poller, изменение Sensor startup/restart policy, root escalation, изменение NI-01 `Wants`, dynamic readiness API или другой lifecycle graph; либо доказать finite start budget в systemd 249 в рамках двух existing unit templates не удалось.

```text
TASK=SSR-01B-2
FROM=CHIEF_ARCHITECT
TO=CAPTIVPORTAL_TECH_LEAD
REQUEST=B2-Q01..B2-Q04
ARCHITECT_VERDICT=MODIFY_ACCEPT
PARENT_ADR=SSR-01_v1_FINAL
PARENT_AMENDMENT=SSR-01B_v1_FINAL
ALLOWED_MECHANISM=SYSTEMD_LOCAL_BOUNDED
B2_Q01=APPROVE_FINITE_RECOVERY_EPISODE
B2_Q02=APPROVE_RESEARCH_DRIVEN_SURICATA_TIMEOUT_RETRY_STARTLIMIT
B2_Q03=APPROVE_NON_SENDING_AF_UNIX_SOCK_DGRAM_CONNECT
B2_Q04=APPROVE_TARGET_VERSION_MOCK_PLUS_FAITHFUL_EVE_GATE
TARGET_SYSTEMD=249.11-0ubuntu3.22_REPORTED
REPO_PRODUCTION_FILES=2_EXISTING_SERVICE_TEMPLATES_ONLY
RESEARCH_G0_R05=PENDING
CODER_TASK_PREPARATION=YES_CONDITIONAL
CODER_IMPLEMENTATION_GO=NO
RELEASE_GATE=NOT_YET_PASSED
PR_PUBLICATION=HOLD
OWNER_MERGE=HOLD
PRODUCTION=OBSERVATION_FREEZE
SYSTEMD_INSTALL=NO
PRODUCTION_RESTART=NO
```

**Документ подготовлен как узкое дополнение к SSR-01B; прежние контракты остаются действительными вне явно изменённых условий.**

## References (not evidence of current deployed state)

- SSR-01B-2 Tech Lead request R1, 2026-10-15, §1–5 (reported exact Lab/systemd observations).
- SSR-01B Chief Architect Amendment v1 FINAL; SSR-01 ADR v1 FINAL.
- Ubuntu 22.04, systemd 249 manual: `systemd.unit(5)`, `systemd.service(5)`; source-level man references: https://manpages.ubuntu.com/manpages/jammy/man5/systemd.unit.5.html and https://manpages.ubuntu.com/manpages/jammy/man5/systemd.service.5.html.
