# Repository instruction pilots

Status: passed for one repository-aware agent; cross-agent validation pending
Updated: 2026-08-04
Runtime baseline: main `227ebe93831447d16b78f277ee3052ddd06e15a3`
Knowledge-base branch: `agent/knowledge-base-integration`

## Ограничение

Оба pilot выполнены одним repository-aware Codex agent после размещения `AGENTS.md`, `.github/copilot-instructions.md` и path-specific instructions внутри рабочей ветки. Второй независимый coding agent и GitHub Copilot не запускались. Автоматическая path activation платформой не наблюдаема изнутри этой сессии, поэтому проверены presence/applyTo, ручная маршрутизация и фактическое соблюдение правил.

Эта граница не выдаётся за cross-agent universality.

## Pilot A — simple documentation implementation

Input:

- task: актуализировать базу знаний после merge Cleaner;
- mode: implementation/publish;
- allowed scope: documentation, instructions, templates, README и pytest discovery config;
- runtime, API implementation, events, databases и infrastructure запрещены;
- test responsibility: agent where environment permits.

Прочитано:

- `AGENTS.md`;
- `.github/instructions/documentation.instructions.md`;
- `docs/project-inventory.md`;
- `docs/module-index.md`;
- `docs/modules/pending-session-cleaner.md`;
- связанные architecture/API/testing/logging/deployment contracts.

Observed result:

- scope остался documentation-only;
- runtime commit сначала обновлён и инвентаризирован;
- unmerged TASK intent не выдан за current state;
- token-cache противоречие разрешено только после проверки merged code/tests;
- Cleaner status разделяет repository default и owner-confirmed production activation;
- невозможный pytest gate отмечен как environment limitation, а не passed;
- handoff требует точных repository actions.

Verdict: `passed for current agent`.

## Pilot B — complex planning-only mutation conflict

Input:

- hypothetical task: рассмотреть `block/unblock` как fallback после неуспешного Cleaner reconnect;
- mode: planning-only;
- repository writes, network mutation, Grafana/Alloy/Loki/systemd запрещены.

Прочитано:

- `AGENTS.md`;
- `.github/instructions/pending-sessions.instructions.md`;
- `.github/instructions/omada-api.instructions.md`;
- `docs/modules/pending-session-cleaner.md`;
- `docs/api/omada-open-api.md`;
- `docs/architecture.md`.

Observed result:

- current Cleaner action path определён как reconnect-only;
- `block/unblock` распознаны как schema-confirmed, но rejected для Cleaner v1;
- fallback меняет mutation/action policy и требует отдельного TASK, PLAN, ADR, guards, audit, verification и tests;
- план останавливается до изменения кода;
- Visitor Registry DB и infrastructure остаются вне scope.

Verdict: `passed stop-condition pilot`.

## Path-specific instruction audit

- восемь `.github/instructions/*.instructions.md` содержат `applyTo`;
- Cleaner paths покрыты отдельным adapter;
- Omada adapter включает `app/controllers/omada_pending_sessions.py`;
- documentation, tests, logging, background-worker и Python rules покрывают связанные файлы без дублирования полного `AGENTS.md`.

## Rerun condition

Повторить pilots при изменении universal rules, platform adapter, `applyTo` routing или TASK/handoff contract. Для cross-agent claim нужен отдельный запуск вторым coding agent с фиксацией model/version, прочитанных files, deviations и verdict.
