# Долги CaptivePortal

Последнее обновление: 10 августа 2026 года

## Назначение

Этот файл — единый оперативный реестр технических долгов, незавершённых проверок и принятых ограничений проекта CaptivePortal.

Правила ведения:

- новый пункт добавляется после явного решения пользователя, архитектора или техлида;
- фактически закрытый пункт не удаляется, а переносится в раздел «Закрытые» с коммитом или Pull Request;
- production-проверка и кодовая готовность разделяются;
- предположение не объявляется дефектом без подтверждения наблюдением или тестом;
- задачи базы знаний фиксируются здесь только как долг/owner action; сами файлы базы знаний этим реестром не изменяются.

## Текущая контрольная точка

- Дата: 10.08.2026
- Production: `/opt/CaptivePortal`
- Service: `captive-portal.service`
- Текущий production/main: `ab776af` — merge PR #37
- Последний deploy: PASS по fast-forward/restart/systemd health
- Функциональная приёмка PR #37 на телефоне: ещё не завершена
- Полный Linux regression gate именно для `ab776af`: ещё не зафиксирован как green

---

# Открытые

## DEBT-P0-001 — Полевой тест закрытия captive-окна после AUTHORIZED

- Приоритет: P0.
- Статус: OPEN / deployed, live validation pending.
- Происхождение: прежний `UX-001 — Поведение страницы после успешной авторизации`.
- Реализация:
  - PR #37;
  - commit `a175919`;
  - merge `ab776af`.
- Текущее поведение кода:
  - после подтверждённого `AUTHORIZED` выполняется `window.close()`;
  - затем допускается один reload текущей страницы;
  - `sessionStorage` защищает от reload-loop.
- Что уже подтверждено:
  - код находится в production;
  - frontend/Node-сценарии проверены;
  - service после deploy работает.
- Что не подтверждено:
  - фактическая реакция Android captive WebView на реальном телефоне.

### Критерий закрытия

На реальном телефоне:

1. получить `AUTHORIZED / 100%`;
2. не делать ручной refresh;
3. подтвердить попытку закрытия;
4. подтвердить максимум один reload текущего `/capport/login`;
5. подтвердить отсутствие цикла;
6. подтвердить автоматическое закрытие окна;
7. повторить минимум 5 раз.

---

## DEBT-P0-002 — Полный Linux regression gate для `main@ab776af`

- Приоритет: P0.
- Статус: OPEN.
- Причина:
  - последний полностью зелёный Linux baseline относится к более раннему состоянию;
  - после PR #34–#37 полного `pytest` с `0 failed` на exact `ab776af` не зафиксировано.
- Ранее:
  - baseline: `894 passed, 10 skipped, 0 failed`;
  - TASK-DEBT-01 full suite: `924 passed, 2 failed`;
  - два падения были связаны с frontend reconciliation и AF_UNIX sandbox limitation;
  - frontend после этого менялся.

### Критерий закрытия

В нормальной Linux/project environment выполнить:

```bash
python -m pytest -q -rs
python -m compileall -q app
git diff --check
```

Зафиксировать точные:

```text
passed
skipped
failed
commit SHA
```

Environment-only failure допускается отделить от product defect, но он должен быть явно документирован.

---

## DEBT-P1-001 — Post-restart health Cleaner / Snapshot / Registry

- Приоритет: P1.
- Статус: UNVERIFIED после deploy 10.08.
- Systemd при restart загрузил drop-in:
  - `pending-session-cleaner.conf`;
  - `visitor-snapshot.conf`;
  - `visitor-registry.conf`.
- Общий сервис после restart — PASS.
- Но в представленном окне журнала отдельно не подтверждены lifecycle/feature state всех трёх компонентов.

### Критерий закрытия

Без вывода secrets подтвердить:

- один application process;
- фактический enabled/disabled state;
- Cleaner scan events;
- Snapshot writer;
- Visitor Registry `ready`;
- Visitor Registry `partial=false`;
- текущие DB/journal counters относительно предыдущей контрольной точки.

---

## DEBT-P1-002 — Rotation старого Omada Client Secret

- Приоритет: P1.
- Статус: OPEN.
- Связанный закрытый этап: TASK-DEBT-01 / PR #34 / `96f7794`.
- Текущее состояние:
  - production credentials удалены из current repository tree;
  - Omada configuration поступает через process environment;
  - старое значение Client Secret остаётся в Git history.
- Переписывание Git history не является обязательной частью этого долга.

### Критерий закрытия

Owner-controlled процедура:

1. выпустить новый Client Secret;
2. обновить production environment;
3. restart + health checks;
4. подтвердить работу Omada API;
5. отозвать старый secret.

Никакие значения secret в этот реестр не записывать.

---

## DEBT-P1-003 — TLS verification к Omada Controller

- Приоритет: P1.
- Статус: OPEN.
- Текущее состояние:
  - `VERIFY_SSL=false`;
  - runtime показывает `InsecureRequestWarning`.
- Это не регрессия deploy 10.08, а существующий security/operations debt.

### Критерий закрытия

- выбрать доверенную модель сертификата контроллера;
- установить/доверить CA или сертификат с корректной цепочкой;
- включить TLS verification;
- выполнить focused tests;
- обновить deployment/security contract через отдельную задачу.

---

## DEBT-P1-004 — Дрейф базы знаний относительно current main

- Приоритет: P1.
- Статус: OPEN.
- Owner: начальник базы знаний / техлид.
- Этот файл только фиксирует долг и не изменяет knowledge-base документы.

### Подтверждённое расхождение

Часть knowledge-base документов всё ещё привязана к старому baseline и может перечислять уже закрытые пункты как активные, включая:

- tracked `pyc/__pycache__`;
- backup-файлы;
- Cleaner token race;
- старый `location.replace()` flow;
- прежнее состояние Visitor Registry.

### Критерий закрытия

Начальник базы знаний должен отдельной documentation-задачей:

- привести актуальные документы к `main@ab776af` или более новому фактическому main;
- убрать закрытые долги из active-state;
- сохранить историю изменений отдельно;
- разделить repository defaults и фактическое production state.

---

## DEBT-P2-001 — Отсутствие GitHub CI

- Приоритет: P2.
- Статус: OPEN.
- В repository отсутствует `.github/workflows` с воспроизводимым release/test gate.
- Текущая проверка зависит от ручного Linux запуска.

### Критерий закрытия

Отдельным infrastructure TASK добавить минимальный CI:

- supported Python;
- install development requirements;
- targeted/full pytest;
- compileall;
- diff/static repository checks.

Не смешивать с feature fixes.

---

## DEBT-P2-002 — Низкоприоритетная repository cleanup

- Приоритет: P2.
- Статус: OPEN.
- В main остаются:
  - legacy route/template `/success`, который согласованный CAPPORT flow больше не использует;
  - `outputs/omada-webhook-normalized.alloy` с незафиксированным ownership.

### Критерий закрытия

Архитектору определить:

- сохранить `/success` как документированный compatibility route или удалить отдельным cleanup TASK;
- назначить owner Alloy artifact либо перенести его в утверждённый infrastructure scope.

---

# Принятые ограничения

## LIMIT-001 — Single-process и process-local bounded state

- Приоритет: P2.
- Статус: ACCEPTED LIMITATION.
- Текущий production рассчитан на один application process.
- Process-local:
  - AuthSession;
  - retry guards;
  - Cleaner action limits;
  - workers;
  - часть bounded in-memory state.
- После restart часть состояния начинается заново.

### Условие возврата

До:

- multi-worker deployment;
- horizontal scaling;
- HA.

Перед масштабированием нужен отдельный ADR по:

- shared session storage;
- inter-process locking / leader election;
- persistent action guard.

При `workers=1` срочным дефектом не считается.

---

# Закрытые

## CLOSED-001 — Бесшовный переход discovery → authorization

- Бывший пункт: `DEBT-001 — Бесшовный переход из ожидания к авторизации`.
- Статус: CLOSED по кодовой части.
- Предварительная защита появления клиента:
  - PR #31;
  - commit `b1b81ee`.
- Финальное бесшовное переключение без `location.replace()`:
  - PR #35;
  - commit `f476cf4`.
- Результат:
  - `portal.html` остаётся той же страницей;
  - discovery выполняется через последовательный `fetch`;
  - после обнаружения клиента используется существующий единый `AuthSession/AuthWorker` flow.

Дополнительная UX-стабилизация прогресса:
- PR #36;
- commit `1538090`;
- устранены обратные скачки progress при discovery → auth и быстрых ответах backend.

---

## CLOSED-002 — Cleaner token recovery race

- Статус: CLOSED.
- PR #30.
- Commit: `a9d2f6a`.
- Результат:
  - Cleaner не очищает свежий token, опубликованный другим thread;
  - добавлен focused concurrency regression test.

---

## CLOSED-003 — TASK-DEBT-01: Omada credentials и repository hygiene

- Статус: CLOSED по code/repository scope.
- PR #34.
- Commit: `96f7794`.
- Результат:
  - четыре Omada OpenAPI-настройки вынесены в process environment;
  - добавлена fail-closed validation;
  - tracked `pyc/__pycache__` удалены;
  - два backup-файла удалены.
- Остаточный security action вынесен отдельно:
  - `DEBT-P1-002 — Rotation старого Omada Client Secret`.

---

## CLOSED-004 — Visitor Registry production readiness

- Статус: CLOSED / PASS.
- PR #32.
- Commit: `6b69d6e`.
- Подтверждено ранее:
  - Registry `ready`;
  - initial backfill 100%;
  - `partial=false`;
  - SQLite integrity PASS;
  - production/observability PASS;
  - Visitor Registry → Alloy → Loki → Grafana работает.
- Следующий `Visit Lifecycle` является отдельным функциональным этапом, а не долгом Visitor Registry.

---

## CLOSED-005 — Production deploy `main@ab776af` от 10.08.2026

- Статус: CLOSED / deploy health PASS.
- До deploy: `59a54a3`.
- Точка отката:
  - tag `server-backup-before-b5-20260810`.
- После deploy:
  - `main@ab776af`;
  - fast-forward выполнен;
  - `captive-portal.service` active (running);
  - startup exception в предоставленном журнале не обнаружен;
  - рабочий `logs/` сохранён.

Важно:
- этот CLOSED относится только к факту успешного deploy/restart;
- `DEBT-P0-001` и `DEBT-P0-002` остаются отдельными release-validation gate.

---

# Ближайший порядок

1. `DEBT-P0-001` — live test captive-window на телефоне.
2. `DEBT-P0-002` — full Linux regression gate exact `ab776af`.
3. `DEBT-P1-001` — post-restart health Cleaner / Snapshot / Registry.
4. `DEBT-P1-002` — rotation старого Client Secret.
5. `DEBT-P1-003` — TLS verification.
6. `DEBT-P1-004` — передать начальнику базы знаний как отдельную documentation-задачу.
7. `DEBT-P2-001` — GitHub CI.
8. `DEBT-P2-002` — repository cleanup.
9. `LIMIT-001` — оставить как accepted limitation до масштабирования.
