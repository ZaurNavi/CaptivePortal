$ErrorActionPreference = "Stop"

$WORK = "$env:USERPROFILE\Downloads\CaptivPortal-KB-Work"
$REPO = "ZaurNavi/CaptivePortal"
$EXPECTED = "8e36132398398b13d7503f624ef19c26d0057566"
$BRANCH = "docs/centralize-full-test-gate-2026-08-26"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content, $Utf8NoBom)
}

function Replace-Exact([string]$Path, [string]$Old, [string]$New) {
    # Normalize line endings before exact replacement. Git files are LF while
    # PowerShell here-strings on Windows are normally CRLF.
    $Text = [System.IO.File]::ReadAllText($Path)
    $TextNorm = $Text.Replace("`r`n", "`n")
    $OldNorm = $Old.Replace("`r`n", "`n")
    $NewNorm = $New.Replace("`r`n", "`n")
    $Count = ([regex]::Matches($TextNorm, [regex]::Escape($OldNorm))).Count
    if ($Count -ne 1) {
        throw "STOP: expected exactly one replacement target in $Path, found $Count"
    }
    $TextNorm = $TextNorm.Replace($OldNorm, $NewNorm)
    Write-Utf8NoBom $Path $TextNorm
}

function Replace-RegexOne([string]$Path, [string]$Pattern, [string]$Replacement) {
    $Text = [System.IO.File]::ReadAllText($Path)
    $Matches = [regex]::Matches($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if ($Matches.Count -ne 1) {
        throw "STOP: expected exactly one regex replacement target in $Path, found $($Matches.Count)"
    }
    $Text = [regex]::Replace($Text, $Pattern, $Replacement, [System.Text.RegularExpressions.RegexOptions]::Singleline)
    Write-Utf8NoBom $Path $Text
}

Write-Host "`n=== PRECHECK / RECOVER FAILED V1 ATTEMPT ==="
if (-not (Test-Path (Join-Path $WORK ".git"))) {
    throw "STOP: repository not found at $WORK"
}

$ExpectedPaths = @(
    ".github/instructions/tests.instructions.md",
    "AGENTS.md",
    "README.md",
    "README_RU.md",
    "docs/agents/handoff.md",
    "docs/agents/task-contract.md",
    "docs/agents/workflow.md",
    "docs/deployment.md",
    "docs/plans/PLAN-template.md",
    "docs/project-inventory.md",
    "docs/tasks/TASK-template.md",
    "docs/testing.md"
)

git -C "$WORK" fetch origin main
if ($LASTEXITCODE -ne 0) { throw "STOP: fetch failed" }
$RemoteMain = (git -C "$WORK" rev-parse origin/main).Trim()
Write-Host "origin/main: $RemoteMain"
if ($RemoteMain -ne $EXPECTED) {
    throw "STOP: origin/main changed. Expected $EXPECTED, got $RemoteMain"
}

$CurrentBranch = (git -C "$WORK" branch --show-current).Trim()
$DirtyLines = @(git -C "$WORK" status --porcelain)
$DirtyPaths = @()
foreach ($line in $DirtyLines) {
    if ($line.Length -ge 4) {
        $p = $line.Substring(3).Trim()
        if ($p -match ' -> ') { $p = ($p -split ' -> ')[-1] }
        $DirtyPaths += $p
    }
}

if ($CurrentBranch -eq $BRANCH) {
    # V1 stopped before commit/push. Recovery is permitted only when HEAD is
    # still the exact expected base and all dirty paths belong to this docs update.
    $BranchHead = (git -C "$WORK" rev-parse HEAD).Trim()
    if ($BranchHead -ne $EXPECTED) {
        throw "STOP: recovery branch HEAD is not expected base. Expected $EXPECTED, got $BranchHead"
    }
    $RemoteBranch = git -C "$WORK" ls-remote --heads origin $BRANCH
    if ($RemoteBranch) {
        throw "STOP: remote branch already exists; do not auto-recover: $BRANCH"
    }
    foreach ($p in $DirtyPaths) {
        if ($ExpectedPaths -notcontains $p) {
            throw "STOP: unexpected local change on failed branch: $p"
        }
    }
    if ($DirtyPaths.Count -gt 0) {
        Write-Host "Recovering failed V1 attempt; discarding only generated docs changes:"
        $DirtyPaths | ForEach-Object { Write-Host "  $_" }
    }
    git -C "$WORK" reset --hard origin/main
    if ($LASTEXITCODE -ne 0) { throw "STOP: failed-attempt reset failed" }
} else {
    if ($DirtyLines.Count -gt 0) {
        Write-Host "Unexpected working-tree changes:"
        $DirtyLines | ForEach-Object { Write-Host $_ }
        throw "STOP: working tree is not clean outside recoverable failed branch"
    }
    git -C "$WORK" switch main
    if ($LASTEXITCODE -ne 0) { throw "STOP: cannot switch to main" }
    git -C "$WORK" merge --ff-only origin/main
    if ($LASTEXITCODE -ne 0) { throw "STOP: main fast-forward failed" }

    if (git -C "$WORK" branch --list $BRANCH) {
        $ExistingHead = (git -C "$WORK" rev-parse $BRANCH).Trim()
        if ($ExistingHead -ne $EXPECTED) {
            throw "STOP: local branch exists with unexpected HEAD: $ExistingHead"
        }
        git -C "$WORK" branch -D $BRANCH
        if ($LASTEXITCODE -ne 0) { throw "STOP: cannot remove stale local branch" }
    }
    $RemoteBranch = git -C "$WORK" ls-remote --heads origin $BRANCH
    if ($RemoteBranch) {
        throw "STOP: remote branch already exists: $BRANCH"
    }
    git -C "$WORK" switch -c $BRANCH
    if ($LASTEXITCODE -ne 0) { throw "STOP: branch creation failed" }
}

if ((git -C "$WORK" status --porcelain)) {
    throw "STOP: recovery did not produce a clean exact-base tree"
}
Write-Host "PASS: exact base restored on $BRANCH"

Write-Host "`n=== UPDATE CANONICAL TEST WORKFLOW ==="

# 1) docs/testing.md — canonical detailed testing contract
$Testing = @'
# Testing

Status: current
Updated: 2026-08-26
Documentation/workflow baseline: `main@8e36132398398b13d7503f624ef19c26d0057566`
Runtime code checkpoint described by the current KB: `dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`

## Responsibility model

`AGENTS.md` is the universal entry contract. This document is the detailed testing authority.

The current project model is:

```text
Coder / executor
→ TASK/module-scoped testing

Central Lab
→ full regression
→ official baseline
→ final Test Evidence
```

The purpose is to avoid repeating the same heavy regression suite in Coder, Tech Lead and owner workflows while preserving strong local verification of each implementation.

### Coder / executor

The Coder keeps both the right and the responsibility to test the work being implemented.

Expected Coder verification includes:

- targeted tests for modules/components changed by the TASK;
- tests for specific files/classes/scenarios affected by the change;
- regression cases added with the implementation;
- repeated local runs of those targeted tests during development/fixes;
- relevant static/syntax/frontend checks;
- `git diff --check`.

The Coder does **not** run the full CaptivPortal repository regression suite by default after every implementation.

A TASK may explicitly require an exceptional broader run when there is a concrete reason, but that exception must be stated; it is not inherited from old TASK wording.

### Tech Lead / Reviewer

The Tech Lead normally verifies:

- architecture and TASK/ADR conformance;
- implementation boundaries and DIFF;
- contracts, risk and regression surface;
- Coder targeted-test evidence;
- whether new/changed tests cover the intended behavior.

The Tech Lead is **not** required to personally execute the full repository suite for ordinary implementation review.

When official full-baseline evidence is required, the Tech Lead requests/consumes the Central Lab result for the exact artifact.

The Tech Lead may still run a targeted or broader test when it answers a specific unresolved question, platform delta or investigation need.

### Central Lab

The Central Lab is the controlled source for:

- official current full-regression baseline;
- Full Regression Gate;
- final Test Evidence before further promotion when required;
- confirmation that no strict regression appeared;
- reproducible evidence that can be consumed by Tech Lead, Coder and other roles.

A successful full gate on an unchanged exact artifact must not be duplicated by another role merely for formality.

## Official Windows Local Gate

Current approved tool:

```text
C:\CaptivPortal-Lab\lab-test-v4-fixed.cmd
```

Owner-provided confirmed baseline date:

```text
2026-08-26
```

Strict-suite result:

```text
1985 passed
30 skipped
0 strict regressions
```

Five compatibility cases are tracked separately and narrowly:

```text
WARN — SQLite infinity edge case
WARN — Node async harness timing
PASS — Visitor Registry Windows thread-timing case 1
PASS — Visitor Registry Windows thread-timing case 2
PASS — Visitor Registry Windows thread-timing case 3
```

Additional gate checks:

```text
compileall          PASS
git diff --check    PASS
Windows Local Gate  PASS
```

`lab-test-v4-fixed.cmd` is the current official Windows Local Test Gate. It must not be loosened merely to make a new failure green.

### Compatibility-baseline rule

Compatibility handling is exact and case-specific.

Forbidden:

- excluding a whole module/file because one known case is environment-sensitive;
- converting a new failure into WARN without reviewed evidence;
- broadening the compatibility allowlist merely to preserve a green result;
- weakening assertions or deleting tests to satisfy the gate.

Any new failure outside the explicitly recorded compatibility cases is a **strict regression** until investigated and reclassified through an explicit reviewed decision.

The numeric baseline above is evidence from the confirmed 2026-08-26 run. After runtime/test changes, a new official exact-artifact baseline must be generated before the old numbers are presented as current.

## Linux / production-compatible gate

The Windows Local Gate does **not** replace, weaken or waive Linux pre-production acceptance.

When a deploy/release contract requires a Linux or other production-compatible full gate, it is executed separately on the exact artifact in the required environment.

Canonical Linux gate remains:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
git diff --check
```

The deploy/release TASK identifies who executes that environment-specific acceptance. It is not automatically assigned to the Coder or Tech Lead merely because they implemented/reviewed the change.

Windows compatibility WARNs do not automatically transfer to Linux; platform-specific results are classified in their own evidence.

## Evidence contract

Every claimed targeted or full test result must identify, as applicable:

- exact artifact/baseline;
- exact command or approved lab gate version;
- environment;
- passed/skipped/failed or strict-regression result;
- compatibility classification;
- `compileall` / `git diff --check` status where included;
- whether the result is Coder targeted evidence, Central Lab official evidence, or Linux pre-production evidence.

Historical green results remain historical. Never present a prior count as a current exact-artifact result after runtime/test changes.

## Reuse and non-duplication

Do not repeat an identical targeted or full run only to duplicate another role's evidence.

A rerun is justified when it provides new information, for example:

- a new patch/commit changed the tested artifact;
- a new risk or previously uncovered scenario must be checked;
- a different platform/environment is required;
- previous evidence is incomplete, contradictory or suspect;
- a deploy/production contract explicitly requires the independent environment gate.

## Current test map

Repository test root: `tests/`.

Coverage groups include:

- Portal/Auth/retry/session ownership;
- CAPPORT/discovery/frontend;
- telemetry/counters;
- Omada provider and webhook;
- Visitor Snapshot/Registry;
- Pending Session Cleaner;
- Visit Lifecycle including schema/write contention/reader/reconciliation;
- Observation;
- Current State;
- Analytics/API/Current Traffic;
- Admin Web/Home Live/Home Traffic.

## CI

`.github/workflows` is absent at the documented runtime baseline. Automated GitHub release gating is not implemented; this remains process debt, not a runtime defect.

The Central Lab is the official manual full-regression source until a separately approved CI/release-gate architecture changes that responsibility.

## Documentation-only tasks

For a pure documentation change:

- no runtime pytest claim is required from the documentation executor;
- validate paths/links/claims against current sources;
- run Markdown/link tooling only if already available/relevant;
- run `git diff --check`;
- request a fresh Central Lab or Linux gate only when an owner/release contract requires exact-artifact runtime evidence.
'@
Write-Utf8NoBom (Join-Path $WORK "docs/testing.md") ($Testing.TrimStart())

# 2) docs/agents/workflow.md
$Workflow = @'
# Workflow coding agent

Status: current
Updated: 2026-08-26

## 1. Intake

1. Read `AGENTS.md`.
2. Read the current TASK as scope/change-intent.
3. Determine execution mode, TASK-scoped test responsibility and repository actions.
4. Read only linked knowledge contracts.
5. Verify affected current code/tests before planning.

Current-state truth: code → tests → current docs.
Change-intent truth: FINAL TASK → PLAN → ADR.

## 2. Modes

- `planning-only`: read/verify/plan; no changes.
- `implementation`: allowed-file changes only.
- `review`: diff/contracts/tests verdict; fixes only if separately allowed.
- `publish`: only explicitly authorized branch/commit/push/PR.
- `deploy`: separate production task with backup/health/rollback.

## 3. Implementation

- minimal sufficient scope;
- preserve current architectural invariants;
- no unrelated refactor;
- no schema/public contract change unless TASK requires it;
- update the canonical knowledge contract if a current contract changes.

## 4. Verification responsibility

### Coder / executor

Runs task-scoped verification:

- targeted tests for changed modules/components;
- new regression tests assigned by TASK;
- repeated targeted tests needed during implementation/fixes;
- relevant static/syntax/frontend checks;
- `git diff --check`.

The Coder does not run the whole CaptivPortal regression suite by default.

### Tech Lead / Reviewer

Reviews architecture, TASK/ADR conformance, DIFF, contracts, risk and the Coder's targeted-test evidence.

The Tech Lead does not personally rerun the full suite for ordinary review unless a separate concrete reason requires it.

### Central Lab

Owns the controlled full-regression function:

```text
official full baseline
Full Regression Gate
final Test Evidence
strict-regression confirmation
```

Use the Central Lab evidence for the exact artifact rather than duplicating the same full run in multiple roles.

### Linux pre-production

When production acceptance requires Linux/production-compatible execution, that is a separate exact-artifact gate defined by the deploy/release contract. Windows Local Gate does not replace it.

Detailed policy and current Windows V4 baseline: `../testing.md`.

## 5. Promotion flow

Normal flow:

```text
Coder implementation
→ targeted/module test evidence
→ Tech Lead review
→ Central Lab full gate when required
→ owner/release decision
→ separate Linux production-compatible gate when required
→ deploy/activation
```

Do not repeat an identical test run unless the rerun supplies new evidence: changed artifact, new risk, different platform, investigation or explicit release requirement.

## 6. Repository actions

Implementation permission does not imply publish/merge permission.

Branch/commit/push/PR/merge are separate repository actions. Merge, force push and production deploy remain owner-only without direct authorization.

## 7. Conflicts

If TASK, code, tests and current docs disagree:

- identify exact sources;
- stop only affected part;
- continue independent safe work;
- escalate to Architect/Tech Lead.

Never silently choose the convenient source.

## 8. Handoff

Use `agents/handoff.md`.

State exact artifact, files changed, Coder targeted checks, any Central Lab evidence reference, any separate Linux pre-production evidence, actual repository actions, open risks and owner actions. Never claim an operation that was not executed.
'@
Write-Utf8NoBom (Join-Path $WORK "docs/agents/workflow.md") ($Workflow.TrimStart())

# 3) docs/agents/task-contract.md
$TaskContract = @'
# Контракт TASK

Status: current
Updated: 2026-08-26

TASK — высший источник change intent конкретной задачи и её scope contract. Он не является источником фактов о текущей реализации и не может молча отменить security или необратимые owner-only ограничения.

## Две модели истины

Current-state truth:

1. код;
2. тесты;
3. актуальная документация.

Change-intent truth:

1. утверждённый TASK;
2. PLAN;
3. ADR.

TASK определяет требуемое изменение относительно подтверждённого current state. PLAN описывает способ выполнения TASK. ADR фиксирует устойчивое архитектурное решение, но не подменяет фактическую проверку кода и тестов.

## Обязательные поля

- цель и требуемое поведение;
- execution mode;
- исполнитель/platform;
- capability assumptions;
- TASK-scoped test responsibility: agent, owner, shared или not-applicable;
- требуется ли свежий официальный Central Lab full-regression baseline для продвижения exact artifact;
- требуется ли отдельный Linux/production-compatible gate;
- текущее фактическое состояние;
- out of scope;
- 1–3 связанных документа;
- allowed и forbidden files;
- allowed, forbidden и owner-only repository actions;
- входные и выходные contracts;
- fail-open/fail-closed;
- logging, persistence, lifecycle и security;
- targeted tests;
- acceptance и stop conditions;
- handoff и PR requirements.

## Scope rule

Файл не становится разрешённым только потому, что его удобно отрефакторить. Если необходимый файл отсутствует в allowed list, агент останавливает эту часть и объясняет минимальное расширение.

## Conflicts

При противоречии внутри current-state truth, внутри change-intent truth или между ними агент:

1. приводит точные факты;
2. не выбирает молча одну сторону;
3. продолжает независимые безопасные части;
4. передаёт конфликт Architect/Tech Lead.

## TASK-scoped test responsibility

Значения относятся к тестированию конкретного TASK/изменяемого модуля, а не к официальному full regression всего CaptivPortal:

- `agent`: агент создаёт/обновляет и запускает назначенные targeted/module tests;
- `owner`: агент не добавляет назначенные tests, но описывает необходимые cases/actions;
- `shared`: TASK делит конкретные targeted cases/actions;
- `not-applicable`: TASK объясняет, почему TASK-scoped tests не требуются.

По умолчанию full repository regression не назначается Coder/agent и не должен автоматически копироваться из исторических TASK.

## Official full regression

Официальный full regression / current baseline / final Test Evidence является функцией Central Lab согласно `docs/testing.md`.

TASK должен указать только:

```text
fresh Central Lab baseline required: yes/no
exact artifact to validate: <SHA/patch identity when known>
```

Если для конкретной задачи действительно нужен exceptional full run в другой роли, это должно быть отдельным прямым owner requirement с причиной.

## Linux / production-compatible gate

Linux gate — отдельная release/deploy acceptance boundary. TASK указывает необходимость и среду; он не назначается автоматически Coder или Tech Lead.

## Repository permissions

Implementation mode не означает автоматический commit или push. Publish permissions всегда перечисляются явно.
'@
Write-Utf8NoBom (Join-Path $WORK "docs/agents/task-contract.md") ($TaskContract.TrimStart())

# 4) docs/agents/handoff.md
$Handoff = @'
# Handoff contract

Status: current
Updated: 2026-08-26

## Обязательный итог

### Цель и результат

Что требовалось и что фактически сделано.

### Изменённые файлы

Каждый файл и краткая причина. Если изменений нет — сказать явно.

### Контракты

Изменились ли public API, config, events, persistence, lifecycle, security или architecture.

### TASK-scoped проверки исполнителя

Точные targeted/module/static команды и результат: passed, skipped, failed. Не выполненные проверки — с причиной.

Не писать, что Coder выполнил full regression, если он только передаёт Central Lab evidence.

### Central Lab / official Test Evidence

Указать одно из:

```text
not required for this handoff
pending Central Lab gate
Central Lab evidence: <artifact/date/result/reference>
```

Если официальный baseline существует, указать exact artifact и результат, но не приписывать выполнение Coder/Tech Lead.

### Linux / production-compatible evidence

Если применимо: environment, exact artifact, command/gate and result. Иначе явно `not applicable / separate release step`.

### Риски и ограничения

Известные defects, environment limits, incomplete gates и assumptions.

### Repository actions

Фактически выполненные branch, commit, push и PR; идентификаторы только если реально получены. Отдельно forbidden/not executed.

### Owner actions

Минимальные следующие действия с ответственным.

### Agent execution summary

    Agent/platform:
    Model:
    Task type:
    Execution mode:
    Files inspected:
    Files changed:
    Targeted/module tests:
    Central Lab full regression: not-run-by-agent / evidence reference / not-required
    Linux pre-production gate: separate / evidence reference / not-required
    Unexpected rework:
    Reason for additional context:
    Repository actions:

## Запрещено

Не прикладывать полную command history, многотысячные logs, secrets или неподтверждённые claims.
'@
Write-Utf8NoBom (Join-Path $WORK "docs/agents/handoff.md") ($Handoff.TrimStart())

# 5) TASK template
$TaskTemplate = @'
# TASK-XXX — Название

Status: draft

## 1. Цель

## 2. Execution mode

planning-only / implementation / review / publish / deploy

## 3. Исполнитель и agent platform

## 4. Agent capability assumptions

## 5. TASK-scoped test responsibility

agent / owner / shared / not-applicable

> Это поле относится к targeted/module tests текущего TASK. Официальный full regression по умолчанию принадлежит Central Lab.

## 6. Текущее состояние

## 7. Требуемое поведение

## 8. Не входит в задачу

## 9. Связанные документы

Указать 1–3 файла.

## 10. Разрешённые файлы

## 11. Запрещённые файлы и области

## 12. Разрешённые repository actions

## 13. Запрещённые и owner-only repository actions

## 14. Архитектурные ограничения

## 15. Входные контракты

## 16. Выходные контракты

## 17. Error handling

## 18. Fail-open / fail-closed

## 19. Logging и events

## 20. Persistence

## 21. Lifecycle и shutdown

## 22. Security

## 23. Targeted/module tests

## 24. Official full regression / Central Lab

Указать:

```text
fresh Central Lab baseline required: yes/no
exact artifact: <SHA/patch identity when known>
```

Не назначать full repository suite Coder/Tech Lead автоматически.

## 25. Linux / production-compatible gate

required / not-required / separate deploy-release task

## 26. Acceptance criteria

## 27. Stop conditions

## 28. Handoff format

## 29. PR requirements
'@
Write-Utf8NoBom (Join-Path $WORK "docs/tasks/TASK-template.md") ($TaskTemplate.TrimStart())

# 6) PLAN template
$PlanTemplate = @'
# План TASK-XXX

Status: draft

## Связанные документы

## Проверенное текущее состояние

## Agent capabilities

## Затрагиваемые файлы

## Не затрагиваемые файлы

## Шаги реализации

## Изменения контрактов

## Риски

## Targeted/module tests исполнителя

## Central Lab full regression

required / not-required; exact artifact/evidence reference when available

## Linux / production-compatible gate

required / not-required / separate release step

## Repository actions

## Rollback

## Нерешённые вопросы
'@
Write-Utf8NoBom (Join-Path $WORK "docs/plans/PLAN-template.md") ($PlanTemplate.TrimStart())

# 7) Deployment contract
$Deployment = @'
# Deployment

Status: current contract; production details remain host-verified
Updated: 2026-08-26
Runtime repository baseline documented by KB: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`
Test-workflow update baseline: `main@8e36132398398b13d7503f624ef19c26d0057566`

## Repository vs production

Repository establishes code/default contracts. It does not prove:
- feature flags currently enabled in systemd;
- current DB health/size;
- process environment values;
- reverse-proxy/systemd unit details.

Never print production secret values in deployment evidence.

## Core precondition

Required Omada environment:
`OMADA_URL`, `OMADA_ID`, `OMADA_CLIENT_ID`, `OMADA_CLIENT_SECRET`.

Provider construction is fail-closed when core configuration is missing/invalid.

## Deploy model

Implementation and production activation are separate actions.

A deploy TASK must specify:
target, approved commit, backup, exact config change, required test evidence, health checks, rollback and owner authorization.

Repository feature defaults being `false` intentionally support code deployment before separate activation.

## Current runtime startup health

Use current `run.py` ordering documented in `project-inventory.md`.

Health review should distinguish:
- core portal/auth availability;
- independent runtime state: disabled / active / degraded / unavailable;
- no duplicate OmadaProvider;
- expected single application process;
- expected storage/journal permissions.

## Current shutdown

Expected order:
Admin state clear → Cleaner → Observation → Current State → Public Traffic → stop Visit scheduling → drain Auth executor → stop Visit accepting/close → drain Snapshot → Registry final scan.

Do not activate/deploy changes that break bounded shutdown.

## Testing responsibility

Coder targeted/module evidence is reused by Tech Lead and the release process.

The official full-regression baseline / Full Regression Gate / final Test Evidence is supplied by Central Lab according to `docs/testing.md`. Tech Lead does not need to duplicate the same full suite for ordinary review.

Before a production deployment/activation, the release owner decides whether the exact artifact requires a fresh Central Lab gate and whether a separate Linux/production-compatible gate is mandatory.

The Windows Local Gate does **not** replace Linux acceptance when the deploy contract requires Linux. The Linux gate is executed separately by the executor named by the deploy/release TASK; it is not automatically Coder or Tech Lead responsibility.

## Feature activation

Activation of Snapshot, Registry, Visit, Observation, Current State, Analytics/API, Admin Web/Home sections or Cleaner is owner-controlled and requires production configuration verification plus component-specific health evidence.

A repository `*_ENABLED=false` does not imply production disabled.

## Rollback

Prefer:
1. disable affected feature in production environment;
2. restart service where environment change requires it;
3. verify core portal and component state;
4. if necessary restore approved code/config/data backup.

Never delete audit/history merely to make rollback look clean.

## Infrastructure boundary

systemd, reverse proxy, Alloy, Loki and Grafana are outside normal application implementation scope and require their own deploy/infrastructure authorization.
'@
Write-Utf8NoBom (Join-Path $WORK "docs/deployment.md") ($Deployment.TrimStart())

# 8) GitHub path-specific test instructions
$TestsInstructions = @'
---
applyTo: "tests/**/*.py"
---

# Tests

- TASK-scoped test responsibility берётся из TASK: agent, owner, shared или not-applicable.
- Coder/agent запускает минимальную связанную targeted/module группу и новые regression cases текущего TASK; повторные локальные targeted-прогоны во время разработки разрешены.
- Не запускай full CaptivPortal suite по умолчанию только потому, что изменён test-файл; официальный full regression принадлежит Central Lab согласно `AGENTS.md` и `docs/testing.md`.
- Exceptional broader/full run в agent workflow требует отдельной прямой причины/owner requirement.
- Не удаляй тесты, не ослабляй assertions и не исправляй несвязанные failures ради green result.
- Для внешних API используй deterministic fakes/fixtures; production network запрещён без отдельного TASK.
- Handoff содержит точную targeted-команду и числа passed, skipped, failed; Central Lab evidence указывается отдельно и не приписывается agent.
- Environment failure отделяй от product failure.
'@
Write-Utf8NoBom (Join-Path $WORK ".github/instructions/tests.instructions.md") ($TestsInstructions.TrimStart())

# 9) AGENTS.md — targeted replacements to preserve all architecture rules
$AgentsPath = Join-Path $WORK "AGENTS.md"
Replace-Exact $AgentsPath "Updated: 2026-08-24" "Updated: 2026-08-26"

$OldAgentRule = @'
- Исполнитель запускает только targeted tests модулей и компонентов, которые он изменял, добавлял или переписывал. Полный repository suite выполняет Reviewer / Tech Lead / owner непосредственно перед production deployment или feature activation.
- Не исправлять несвязанные падения full suite.
'@
$NewAgentRule = @'
- Coder/исполнитель запускает TASK/module-scoped targeted tests, новые regression cases и релевантные static/syntax checks; он может повторять эти targeted-прогоны в процессе разработки.
- Официальный full repository regression / current baseline / final Test Evidence является централизованной функцией Central Lab и не дублируется Coder или Tech Lead без отдельной причины.
- Tech Lead проверяет архитектуру, TASK/ADR, DIFF и targeted evidence; полный suite не является его обычной ручной обязанностью.
- Windows Local Gate не заменяет отдельный Linux/production-compatible gate, когда такой gate требуется release/deploy contract.
- Не исправлять несвязанные падения full suite.
'@
Replace-Exact $AgentsPath $OldAgentRule $NewAgentRule

$OldChecksPattern = '(?s)## Проверки\r?\n\r?\nTargeted commands.*?Если environment запрещает назначенную стороне проверку, укажи команду, причину и owner action\.\r?\n'
$NewChecks = @'
## Проверки

Targeted commands для Coder/исполнителя определяет TASK. Они проверяют изменённые модули, непосредственные контракты, новые regression-сценарии и необходимые static/syntax checks.

Статические проверки, такие как `compileall`, проверка синтаксиса изменённого frontend-кода и `git diff --check`, не превращают targeted workflow Coder в официальный full regression.

Полный repository suite не является обязанностью Coder и не является обычной ручной обязанностью Tech Lead. Официальный full-regression baseline и final Test Evidence предоставляет Central Lab для exact artifact, когда он требуется для продвижения изменения.

Current approved Windows Local Gate и его compatibility baseline описаны в `docs/testing.md`.

Если перед production требуется Linux/full production-compatible gate, он выполняется отдельно по deploy/release contract. Windows gate его не заменяет.

Если environment запрещает назначенную стороне проверку, укажи команду/требуемый gate, причину и owner action.
'@
Replace-RegexOne $AgentsPath $OldChecksPattern ($NewChecks.TrimStart())

$OldFullReuse = @'
Full repository suite выполняется нашей стороной один раз в составе pre-production gate. Он не перекладывается на исполнителя и не повторяется без новой причины после успешного gate на неизменённом exact artifact.
'@
$NewFullReuse = @'
Full repository suite выполняется централизованно Central Lab и не повторяется другими ролями без новой причины после успешного gate на неизменённом exact artifact. Отдельный Linux production-compatible gate не считается дублированием, когда он требуется как platform-specific release acceptance.
'@
Replace-Exact $AgentsPath $OldFullReuse $NewFullReuse
Replace-Exact $AgentsPath "Верни: цель и результат; изменённые файлы; targeted/full checks с числами passed, skipped и failed; не выполненные проверки; риски; repository actions, выполненные фактически; owner actions; Agent execution summary." "Верни: цель и результат; изменённые файлы; TASK-scoped targeted checks с числами passed, skipped и failed; Central Lab/full evidence reference или pending/not-required; отдельный Linux gate evidence если применимо; не выполненные проверки; риски; repository actions, выполненные фактически; owner actions; Agent execution summary."

# 10) project inventory — process/evidence section only
$InventoryPath = Join-Path $WORK "docs/project-inventory.md"
Replace-Exact $InventoryPath "Updated: 2026-08-25" "Updated: 2026-08-26"
$InventoryPattern = '(?s)## 18\. Tests and CI\r?\n.*?\r?\n## 19\. Current vs historical vs change-intent'
$InventoryReplacement = @'
## 18. Tests and CI

`tests/` is the repository test root. Current groups cover Auth, CAPPORT, Omada/webhook, Visitor Registry, Pending Cleaner, Visit Lifecycle, Observation, Current State, Analytics and Admin Web.

Current workflow separates test responsibilities:

```text
Coder → TASK/module-scoped targeted testing
Central Lab → full regression / official baseline / final Test Evidence
Tech Lead → architecture/DIFF/targeted-evidence review
```

Owner-provided current Windows Local Gate tool:

```text
C:\CaptivPortal-Lab\lab-test-v4-fixed.cmd
```

Confirmed 2026-08-26 Windows evidence:

```text
strict suite: 1985 passed / 30 skipped / 0 strict regressions
compatibility: 2 WARN + 3 PASS (five exact tracked cases)
compileall: PASS
git diff --check: PASS
overall Windows Local Gate: PASS
```

The compatibility baseline is narrow; a new failure outside the recorded cases is a strict regression until reviewed.

These numbers are operational test evidence, not a repository-derived evergreen count. After runtime/test changes a new exact-artifact Central Lab baseline is required before presenting them as current.

`.github/workflows` is absent at the documented runtime baseline. GitHub release CI remains open process debt; the official full-regression source is currently the manual Central Lab.

Windows Local Gate does not replace a separately required Linux/production-compatible pre-production gate.

## 19. Current vs historical vs change-intent
'@
Replace-RegexOne $InventoryPath $InventoryPattern ($InventoryReplacement.TrimStart())

# 11) README_RU testing section
$ReadmeRuPath = Join-Path $WORK "README_RU.md"
$ReadmeRuPattern = '(?s)# Testing и release discipline\r?\n.*?\r?\n---\r?\n\r?\n# Configuration'
$ReadmeRuReplacement = @'
# Testing и release discipline

Текущая модель разделяет повседневное тестирование реализации и официальный full regression.

```text
Coder
→ targeted / module / TASK-scoped tests

Tech Lead
→ architecture / TASK / DIFF / targeted-evidence review

Central Lab
→ Full Regression Gate
→ official current baseline
→ final Test Evidence
```

Кодер может и должен тестировать свою функциональность столько раз, сколько требуется для разработки и исправлений. Но ему не нужно после каждой реализации запускать весь CaptivPortal regression suite.

Tech Lead не обязан дублировать тяжёлый full suite для обычного review. Когда нужен официальный baseline exact artifact, используется evidence Central Lab.

### Official Windows Local Gate

Текущий утверждённый инструмент:

```text
C:\CaptivPortal-Lab\lab-test-v4-fixed.cmd
```

Подтверждённый baseline от **26 августа 2026 года**:

```text
Strict suite: 1985 passed / 30 skipped / 0 strict regressions
Compatibility: 5 точечных cases → 2 WARN / 3 PASS
compileall: PASS
git diff --check: PASS
RESULT: PASS
```

Два compatibility WARN относятся к SQLite infinity edge case и Node async harness timing. Три Visitor Registry Windows thread-timing cases в контрольном прогоне — PASS.

Compatibility allowlist остаётся точечным. Новое падение вне этих явно зафиксированных cases считается strict regression до отдельного reviewed решения.

Windows Local Gate не заменяет Linux/production-compatible pre-production acceptance. Если release/deploy contract требует Linux full gate, он выполняется отдельно на exact artifact.

Нельзя заявлять current full green baseline после runtime/test changes, опираясь только на старый прогон.

Тесты не должны зависеть от реальных production Omada credentials или live production controller.

На documented runtime checkpoint `.github/workflows` отсутствует, поэтому GitHub release CI остаётся отдельным process debt.

---

# Configuration
'@
Replace-RegexOne $ReadmeRuPath $ReadmeRuPattern ($ReadmeRuReplacement.TrimStart())

# 12) README.md testing section
$ReadmeEnPath = Join-Path $WORK "README.md"
$ReadmeEnPattern = '(?s)# Testing and release discipline\r?\n.*?\r?\n---\r?\n\r?\n# Configuration'
$ReadmeEnReplacement = @'
# Testing and release discipline

The current model separates day-to-day implementation testing from the official full regression function.

```text
Coder
→ targeted / module / TASK-scoped tests

Tech Lead
→ architecture / TASK / DIFF / targeted-evidence review

Central Lab
→ Full Regression Gate
→ official current baseline
→ final Test Evidence
```

The Coder can and should rerun tests for the implemented functionality as often as development and fixes require. The Coder does not need to execute the whole CaptivPortal regression suite after every implementation.

The Tech Lead does not need to duplicate the heavy full suite for ordinary review. When an official exact-artifact baseline is required, the team consumes Central Lab evidence.

### Official Windows Local Gate

Current approved tool:

```text
C:\CaptivPortal-Lab\lab-test-v4-fixed.cmd
```

Confirmed baseline from **26 August 2026**:

```text
Strict suite: 1985 passed / 30 skipped / 0 strict regressions
Compatibility: 5 exact cases → 2 WARN / 3 PASS
compileall: PASS
git diff --check: PASS
RESULT: PASS
```

The two compatibility WARNs are the SQLite infinity edge case and Node async harness timing. The three Visitor Registry Windows thread-timing cases passed in the control run.

The compatibility allowlist stays narrow. Any new failure outside the explicitly recorded cases is a strict regression until a separate reviewed decision reclassifies it.

The Windows Local Gate does not replace Linux/production-compatible pre-production acceptance. If a release/deploy contract requires a Linux full gate, it is executed separately on the exact artifact.

Do not present an old run as the current full green baseline after runtime/test changes.

Tests must not depend on real production Omada credentials or a live production controller.

At the documented runtime checkpoint `.github/workflows` is absent, so GitHub release CI remains separate process debt.

---

# Configuration
'@
Replace-RegexOne $ReadmeEnPath $ReadmeEnPattern ($ReadmeEnReplacement.TrimStart())

Write-Host "`n=== SCOPE CHECK ==="
$ChangedPaths = @(git -C "$WORK" diff --name-only)
$ChangedPaths | ForEach-Object { Write-Host $_ }

if ($ChangedPaths.Count -ne $ExpectedPaths.Count) {
    throw "STOP: expected $($ExpectedPaths.Count) changed files, found $($ChangedPaths.Count)"
}
foreach ($p in $ChangedPaths) {
    if ($ExpectedPaths -notcontains $p) {
        throw "STOP: unexpected changed path: $p"
    }
}
foreach ($p in $ExpectedPaths) {
    if ($ChangedPaths -notcontains $p) {
        throw "STOP: expected path not changed: $p"
    }
}

git -C "$WORK" --no-pager diff --check
if ($LASTEXITCODE -ne 0) { throw "STOP: git diff --check failed" }
Write-Host "PASS: docs/instructions-only scope and diff check"

Write-Host "`n=== POLICY CONTRADICTION CHECK ==="
$CurrentPolicyFiles = @(
    "AGENTS.md",
    "README.md",
    "README_RU.md",
    "docs/testing.md",
    "docs/deployment.md",
    "docs/project-inventory.md",
    "docs/agents/workflow.md",
    "docs/agents/task-contract.md",
    "docs/agents/handoff.md",
    "docs/tasks/TASK-template.md",
    "docs/plans/PLAN-template.md",
    ".github/instructions/tests.instructions.md"
)
$ForbiddenPhrases = @(
    "Reviewer / Tech Lead / owner runs the full",
    "Reviewer / Tech Lead / owner pre-production gate",
    "Reviewer / Tech Lead / owner runs the full exact-artifact",
    "Сначала запускай минимальную связанную группу, затем full gate",
    "Полный repository suite выполняет Reviewer / Tech Lead / owner"
)
foreach ($rel in $CurrentPolicyFiles) {
    $text = [System.IO.File]::ReadAllText((Join-Path $WORK $rel))
    foreach ($phrase in $ForbiddenPhrases) {
        if ($text.Contains($phrase)) {
            throw "STOP: stale policy phrase remains in $rel : $phrase"
        }
    }
}
Write-Host "PASS: known stale responsibility phrases removed"

Write-Host "`n=== STAGE / COMMIT ==="
git -C "$WORK" add -- $ExpectedPaths
if ($LASTEXITCODE -ne 0) { throw "STOP: git add failed" }
$Staged = @(git -C "$WORK" diff --cached --name-only)
if ($Staged.Count -ne $ExpectedPaths.Count) { throw "STOP: staged file count mismatch" }
git -C "$WORK" --no-pager diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "STOP: staged diff check failed" }

# Documentation/workflow-only update: no runtime pytest is intentionally executed here.
git -C "$WORK" commit `
    -m "docs: centralize CaptivPortal full test gate" `
    -m "Document Coder targeted testing, Central Lab full regression ownership, Windows V4 baseline, and separate Linux pre-production acceptance. Documentation/instructions only; no runtime code or tests changed."
if ($LASTEXITCODE -ne 0) { throw "STOP: commit failed" }
$Commit = (git -C "$WORK" rev-parse HEAD).Trim()

Write-Host "`n=== PUSH ==="
git -C "$WORK" push -u origin $BRANCH
if ($LASTEXITCODE -ne 0) { throw "STOP: push failed" }

Write-Host "`n=== GITHUB AUTH ==="
gh auth status
if ($LASTEXITCODE -ne 0) { throw "STOP: GitHub CLI is not authenticated" }

$BodyTemplate = @'
## Purpose

Centralize CaptivPortal full-regression responsibility in the project **Central Lab** while preserving the Coder's right and duty to perform TASK/module-scoped testing.

## Current workflow

```text
Coder
→ targeted / module / TASK-scoped testing

Tech Lead
→ architecture / TASK / ADR / DIFF / targeted-evidence review

Central Lab
→ Full Regression Gate
→ official baseline
→ final Test Evidence
```

A Linux/production-compatible gate remains a separate release/deploy acceptance when required. The Windows Local Gate does not replace it.

## Official Windows Local Gate baseline

Approved tool:

`C:\CaptivPortal-Lab\lab-test-v4-fixed.cmd`

Confirmed 2026-08-26 evidence:

- strict suite: **1985 passed / 30 skipped / 0 strict regressions**;
- five exact compatibility cases: **2 WARN / 3 PASS**;
- SQLite infinity edge case: WARN;
- Node async harness timing: WARN;
- three Visitor Registry Windows thread-timing cases: PASS;
- `compileall`: PASS;
- `git diff --check`: PASS;
- overall Windows Local Gate: **PASS**.

Compatibility handling remains exact and narrow. New failures outside the recorded cases are strict regressions until explicitly reviewed.

## Files

Documentation/instructions only:

- `.github/instructions/tests.instructions.md`
- `AGENTS.md`
- `README.md`
- `README_RU.md`
- `docs/testing.md`
- `docs/deployment.md`
- `docs/project-inventory.md`
- `docs/agents/workflow.md`
- `docs/agents/task-contract.md`
- `docs/agents/handoff.md`
- `docs/tasks/TASK-template.md`
- `docs/plans/PLAN-template.md`

## Explicit non-scope

- no runtime code changes;
- no test-code changes;
- no schema/config/feature-flag changes;
- no production changes;
- no weakening of Linux pre-production acceptance.

Base: `__BASE__`

Commit: `__COMMIT__`

Created as **Draft**. Merge remains owner-controlled.
'@
$Body = $BodyTemplate.Replace("__BASE__", $EXPECTED).Replace("__COMMIT__", $Commit)

Write-Host "`n=== CREATE DRAFT PR ==="
gh pr create `
    --repo $REPO `
    --base main `
    --head $BRANCH `
    --title "Docs: centralize CaptivPortal full test gate" `
    --body $Body `
    --draft
if ($LASTEXITCODE -ne 0) { throw "STOP: Draft PR creation failed" }

Write-Host "`n=== PR CHECK ==="
gh pr list `
    --repo $REPO `
    --head $BRANCH `
    --state open `
    --json number,title,state,isDraft,url,baseRefName,headRefName,headRefOid
if ($LASTEXITCODE -ne 0) { throw "STOP: PR verification failed" }

Write-Host "`n=== FINAL ==="
Write-Host "Branch: $BRANCH"
Write-Host "Commit: $Commit"
Write-Host "Changed files: $($ExpectedPaths.Count) documentation/instruction files only"
Write-Host "Runtime code changed: NO"
Write-Host "Test code changed: NO"
Write-Host "Runtime pytest executed for this docs-only update: NO (intentional)"
Write-Host "git diff --check: PASS"
Write-Host "Merge performed: NO"
