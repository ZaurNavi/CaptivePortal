# CAPTIV-PROD — отдельная GitHub-ветка и нулевой baseline работающего Portal

**Документ:** `CAPTIVPROD-GIT-BASELINE-01`  
**Редакция:** `v0.1 / PREPARATION — BRANCH NOT CREATED`  
**Дата:** `2026-10-16` (Asia/Baku)  
**Владелец решения:** Owner  
**Роль ответственного:** Captiv-Prod Tech Lead  
**Общий репозиторий:** `https://github.com/ZaurNavi/CaptivePortal`  
**Новый контур:** `captiv-prod` (`192.168.0.99`)  
**Старый контур:** Portal `192.168.0.202` / Omada Windows `192.168.0.222`

## 1. Решение Owner

Создать **отдельную долгоживущую ветку внутри существующего репозитория**, отражающую именно подтверждённый рабочий исходный код нового физического сервера, а не автоматически последний GitHub `main`. Считать эту версию **нулевой точкой Captiv-Prod**, продолжать собственную разработку в ветках от неё и **выборочно** переносить одобренные изменения старой команды. Старый production и развитие старой команды сохраняются отдельно.

**Предлагаемое постоянное имя:** `captivprod/main`.  
**Предлагаемая метка первоначального принятого состояния:** `captivprod-baseline-2026-10-16` (создаётся после фактической верификации и acceptance; дата при сдвиге принятия может быть изменена в версионированном решении).

Это одна репозитория с разными ветками, а не второй fork. Старый `main` остаётся веткой старой команды; `captivprod/main` становится источником **исходников** для новой команды после принятия baseline. Операционные конфигурации, секреты и состояние сервисов хранятся и управляются отдельно от Git.

## 2. Фактическое состояние на момент составления

- На GitHub уже существуют и объединены PR [#211](https://github.com/ZaurNavi/CaptivePortal/pull/211) (настраиваемые Flask bind/CAPPORT) и [#212](https://github.com/ZaurNavi/CaptivePortal/pull/212) (конфигурация Sensor/Portal Producer). Их наличие в `main` **не подтверждает**, что установленный на `.99` код совпадает с `main`.
- Предшествующий отчёт установки 16 октября фиксировал чистый checkout `/opt/captivprod-portal` на SHA `191beda1f23f8f466d2431f42e57571815d85778`, но это историческая точка, **не current running code proof**.
- Более поздний read-only network baseline 16 октября, около 20:30–20:37 Asia/Baku, указывает работающий `captive-portal.service` с установленным checkout `/opt/captivprod-portal-v2fix`, backend `172.18.0.1:18089` и NPM → Portal. В документе не зафиксирован точный актуальный SHA/tree/working tree этого checkout.
- Проверка SSH с доверенной рабочей станции выявила **REMOTE HOST IDENTIFICATION HAS CHANGED** для `192.168.0.99` (локально сохранённый ECDSA конфликтует с предъявленным ED25519). Предъявленный удалённым узлом ED25519 fingerprint: `SHA256:eey4JJdPpDnpWusfFjLslhmFejJij59Y7Zr3poxtVNE` — **НЕ ВЕРИФИЦИРОВАН** по независимому каналу. Обход проверки отключён.
- **Итог:** `DEPLOYED_SHA=UNVERIFIED`, `DEPLOYED_TREE=UNVERIFIED`, `LOCAL_CODE_DELTA=UNVERIFIED`, `BASELINE_ACCEPTED=NO`, `GITHUB_CAPTIVPROD_MAIN_CREATED=NO`.

Никаких service restart, AP/Omada, Cisco, DNS, NPM и старых production changes для этой подготовки не выполнялось. Никакая ветка или commit от имени Captiv-Prod этой операцией пока не опубликованы.

## 3. Обязательная процедура перед созданием ветки — только read-only

1. **Подтвердить SSH-host identity** вне SSH-соединения через консоль нового `captiv-prod` или другой уже доверенный управляющий путь. Пример локальной команды на самом `.99`: `sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. Сравнить fingerprint с указанным выше; при несовпадении STOP. Только после независимого подтверждения обновить сохранённый `known_hosts` точечно, с контролем того, какой хост/ключ заменяется.
2. **Определить действительно исполняемый checkout**, а не выбирать по названию каталога: текущий `MainPID`, `ExecStart`, `WorkingDirectory`, путь скрипта/интерпретатора `captive-portal.service`, его symlink resolution и действующий systemd unit/drop-ins. Не распечатывать EnvironmentFiles или credential values.
3. Для подтверждённого checkout собрать `git remote -v` (без токенов в URL), `git rev-parse HEAD`, `git rev-parse 'HEAD^{tree}'`, `git branch --show-current`, `git status --porcelain=v1`, локальные ahead/behind refs, `git diff --name-status` и `git diff --cached --name-status`; найти untracked файлы **без публикации их содержимого**. Проверить, что runtime process относится именно к этому дереву; стартовавший до редактирования файлов процесс нельзя автоматически приравнивать к текущему состоянию on-disk файлов.
4. Сравнить текущие tracked-файлы с Git `HEAD`, выявить deployment-only patches, symlinks, отдельно хранимые шаблоны и любые изменения, внесённые SysAdmin на физическом сервере. До фиксации проверить назначение/безопасность каждого отличия; не нормализовать всё под GitHub `main` и не терять локальные исправления.
5. Проверить исходный репозиторий GitHub, ancestry полного SHA, дерево и наличие ветки `captivprod/main`. Провести независимый Tech Lead/QA review локального delta и проверить выбранное дерево тестами вне production.

**Никогда не копировать в GitHub:** `.env` и service credentials, TLS/private keys, CA private material, Omada secrets/API tokens, production SQLite/JSONL, сессии, MAC/IP посетителей, pcap, raw access logs, backup archives, systemd override с секретами, runtime/generated files. Разрешены только reviewed исходники, безопасные шаблоны и обезличенная nonsecret конфигурационная документация.

## 4. Создание и принятие baseline — после закрытия gates

- Если действующий код точно соответствует одному clean Git commit: создать `captivprod/main` **от полного подтверждённого SHA**, записать SHA + tree и необязательную immutable baseline tag. Искусственный «snapshot-commit» без изменений не нужен.
- Если код имеет необходимые изменения вне Git: в **изолированном worktree/clone, не на работающем сервере** создать ветку от подтверждённого исходного commit, перенести только отобранные безопасные исходные изменения, оформить отдельный reviewable commit/PR, проверить diff и tests. После независимой проверки baseline tree сравнить с фактическими deployed исходниками, исключая согласованные operational artifacts. Если различие неразрешено, `BASELINE=HOLD`.
- Если исполняемый process не соответствует файловому checkout, образ/compiled файлы изменены или исходное дерево невозможно доказать: `BASELINE=HOLD`; вместо догадки документировать фактические runtime artifacts и провести отдельное исследование.
- Настроить защиту `captivprod/main` (без прямого push, обязательный PR/review и запрет force-push) по возможностям репозитория, без изменения защит `main`. Owner разрешает публикацию ветки только после финальной проверки точного источника.
- Итоговый handoff: `DEPLOYED_SERVICE_PATH`, `GIT_BASE_SHA`, `GIT_BASE_TREE`, `REVIEWED_LOCAL_DELTA`, `CAPTIVPROD_BRANCH_HEAD_SHA`, `CAPTIVPROD_BRANCH_TREE`, `RUNTIME_CODE_PARITY=PASS`, `CREDENTIAL_LEAK_SCAN=PASS`, `OWNER_BASELINE_GO`, `OLD_PRODUCTION_UNCHANGED=YES`.

Ветка `captivprod/main` — **источник кода**, не команда автоматического деплоя. Любой переход нового сервера на другой SHA требует самостоятельных SysAdmin release/backup/smoke/rollback gates и Owner GO. Нельзя в ходе baseline делать pull на живом checkout, перезапускать Portal/Omada/NPM, менять Cisco/AP, включать auto-deploy.

## 5. Работа команды после принятия

- Architect: архитектурный контракт и compatibility/safety boundary.
- Tech Lead: implementation TASK, allowed scope, baseline pin, требования тестов, независимая приёмка.
- Coder: ветка `task/captivprod-...` от принятого `captivprod/main`, изолированный worktree, reviewable commits, PR **в `captivprod/main`**.
- Independent QA: source/test/regression/security parity, доказательства и вердикт.
- Owner: merge и отдельный production-deploy GO.
- SysAdmin: релиз только принятого полного SHA, backup, контролируемое применение, health/E2E, rollback. Старый контур остаётся неизменным без своего GO.

## 6. Как перенести понравившееся изменение старой команды

Это возможно — Git поддерживает выборочный перенос между ветками одного репозитория. Процесс: найти конкретный PR и **его точный commit SHA (или полный список commits)** в `main`; выяснить зависимости, миграции, feature flags, конфликты и актуальность; создать отдельную временную ветку от `captivprod/main`; применить проверенный commit с сохранением provenance через `git cherry-pick -x <FULL_SHA>` (только в изолированном worktree), либо вручную адаптировать/перенести патч, если это merge commit, несколько зависимых commit или ветки разошлись; запустить тесты; оформить PR в `captivprod/main`; после Owner GO — merge; затем отдельный deploy GO.

Номер `#256` — номер GitHub Issue/PR, **не идентификатор Git-коммита**. Нельзя автоматически cherry-pick «весь PR #256» по его номеру без инспекции commit history и последующих исправлений. Уже включённые изменения не дублируются. Перенос может вызвать конфликт или потребовать иных зависимых изменений; не считать любой commit автономным. Никогда не переносить напрямую в production `git pull` старого `main` и не переписывать ветку `captivprod/main` принудительно.

## 7. Обязательные статусы

```text
HOST_SSH_IDENTITY=HOLD (fingerprint unverified)
RUNNING_SOURCE_PATH=HOLD (last observed /opt/captivprod-portal-v2fix, verify live)
DEPLOYED_SHA=HOLD
DEPLOYED_TREE=HOLD
LOCAL_CODE_DELTA=HOLD
BASELINE_SOURCE_REVIEW=HOLD
CAPTIVPROD_MAIN_BRANCH=NOT_CREATED
BASELINE_TAG=NOT_CREATED
OLD_PRODUCTION_CHANGES=NONE
NEW_PRODUCTION_CHANGES=NONE
OWNER_INTENT=AUTHORIZED_TO_PREPARE_AND_CREATE_AFTER_EVIDENCE
```

**Документ готов для размещения в источниках как протокол намерения/правила; он НЕ является свидетельством, что baseline уже создан или синхронизирован.** После фактического создания ветки выпустить `v1.0`, проставить фактический SHA/tree, дату/время, GitHub URL ветки, accepted parity evidence и final Tech Lead/Owner verdict.
