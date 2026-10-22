# CAPTIV-PROD — GitHub-ветка и нулевой исходный baseline

**Документ ID:** `CAPTIVPROD-GIT-BASELINE-01`  
**Редакция:** `v1.0`  
**Дата:** `2026-10-16` (Asia/Baku)  
**Статус:** `GITHUB BRANCH CREATED / BASELINE REF VERIFIED / PRODUCTION UNCHANGED`  
**Owner:** владелец проекта Captiv-Prod  
**Ответственный за контроль:** Captiv-Prod Tech Lead  
**Репозиторий:** <https://github.com/ZaurNavi/CaptivePortal>

## 1. Принятое решение

Для команды нового физического сервера используется **самостоятельная долгоживущая ветка внутри существующего GitHub-репозитория**, не отдельный fork:

- Общий основной поток старой команды: `main`.
- Долгоживущая интеграционная ветка нового сервера: [`captivprod/main`](https://github.com/ZaurNavi/CaptivePortal/tree/captivprod/main).
- Неизменяемая по командной политике историческая нулевая отметка: `captivprod-baseline-2026-10-16` (lightweight Git tag).
- Новые реализации Captiv-Prod: отдельные краткоживущие ветки от `captivprod/main` с PR **в `captivprod/main`**, а не в старый `main` по умолчанию.
- Выборочный импорт изменений старой команды выполняется отдельными проверяемыми PR; автоматического слияния `main` в `captivprod/main` нет.

**Создание GitHub-ветки и метки не выполняет deploy и не перенастраивает запущенный сервис.**

## 2. Проверенный исходный Git baseline

**Сервер:** `captiv-prod`, management `192.168.0.99`, Ubuntu 22.04.  
**Service:** `captive-portal.service`.  
**MainPID на момент осмотра:** `426358`.  
**ExecStart:** `/opt/captivprod-portal-venv/bin/python /opt/captivprod-portal-v2fix/run.py`.  
**WorkingDirectory:** `/opt/captivprod-portal-v2fix`.  
**Исходная локальная ветка checkout:** `fix/captivprod-omada-v2-readonly`.

| Git identity | Подтверждённое значение |
|---|---|
| Working checkout HEAD | `b6152459421b48514ddc8af114bcc96e30351cf7` |
| HEAD tree | `3dd3588bdae279660fcbf4e9c5310282041c01e9` |
| Tracked working diff | `NONE` (porcelain status empty) |
| Staged changes | `NONE` (porcelain status empty) |
| Untracked files | `0` (Git excludes ignored artifacts) |
| Origin | `https://github.com/ZaurNavi/CaptivePortal.git` |
| Commit subject | `fix(omada): admit exact v2 AP read-only GET endpoints` |
| GitHub commit author | `CaptivProd-SysAdmin` |
| GitHub commit timestamp | `2026-10-16T13:55:29Z` |
| Service start observed | `2026-10-16 13:57:35 UTC` |

Commit presence was independently verified in GitHub: <https://github.com/ZaurNavi/CaptivePortal/commit/b6152459421b48514ddc8af114bcc96e30351cf7>.

Сведения об источниках и текущей service-команде получены read-only по SSH. Совпадение времени commit и старта сервиса согласуется с запуском именно этого checkout; **полный runtime byte-for-byte audit загруженных модулей не проводился**. Чистый Git checkout также не означает, что игнорируемые deployment-файлы, сертификаты, env, базы и systemd overrides входят в Git baseline — они ведутся отдельно.

В этом сеансе не повторялись guest E2E, AP/Omada smoke, физические performance-тесты и application acceptance; прежние результаты Owner/SysAdmin относятся к собственным протоколам испытаний.

## 3. Факт публикации и проверка

**GitHub branch:** `refs/heads/captivprod/main`  
**GitHub tag:** `refs/tags/captivprod-baseline-2026-10-16`  
**Оба ref указывают на один commit:** `b6152459421b48514ddc8af114bcc96e30351cf7`.

И ветка, и метка созданы 16 октября 2026 года через уже авторизованный GitHub CLI аккаунта `ZaurNavi` на рабочей станции Owner; после создания обе ссылки были повторно прочитаны через GitHub API и дали точный ожидаемый SHA. Подключённый GitHub-plugin позволял чтение, но не имел разрешения на создание refs (`403`); дополнительного GitHub-пользователя или второго репозитория не создавали.

**Важно:** локальный checkout на сервере намеренно оставлен на исходной ветке `fix/captivprod-omada-v2-readonly`. Это не препятствует baseline: его HEAD совпадает с новой `captivprod/main`. Никакого `checkout`, `pull`, `reset`, `commit`, `push`, reboot или restart на production не было. Перед будущим обновлением SysAdmin отдельно определяет release SHA и процедуру развёртывания, не делает `git pull main` на живом сервере.

**Нулевая отметка относится прежде всего к исходному Git-дереву.** Это не полная резервная копия работающей инфраструктуры (Omada, NPM, systemd, SQLite, сертификатов, секретов, DNS, Cisco и AP). Их состояние и recovery поддерживаются отдельными operational backups/baselines.

## 4. Правила команды Captiv-Prod

1. **Architect**: определяет границы совместимости, архитектуру, safety и acceptance.
2. **Tech Lead**: выпускает Implementation TASK, указывает base SHA/tree, scope, review и testing gates; независимый технический вердикт.
3. **Coder**: создаёт `task/captivprod-...`/`fix/captivprod-...` от текущей принятой `captivprod/main`, в отдельном clone/worktree; делает изменения, тесты и PR в `captivprod/main`.
4. **Research/QA**: независимая проверка, regression/security/operational evidence и фиксация PASS/HOLD/FAIL.
5. **Owner**: разрешает merge и отдельно deployment/cutover/activation на живой сервер.
6. **SysAdmin**: deploy только утверждённого SHA; проверка настроек, backups, E2E, rollback; production-изменения только после GO.

Не смешивать commit/merge и фактический deployment. Не писать новые исходники поверх рабочего `/opt/captivprod-portal-v2fix` и не менять `captivprod/main` прямым непроверенным push. Требуется отдельная настройка branch protection/rulesets (review, restricted direct pushes, no force-push); **в данной операции защита ветки ещё не настраивалась**.

## 5. Выборочное заимствование исправлений старой команды

Если Owner выбирает изменение старого `main` или PR (например, оптимизацию), Tech Lead определяет **полный SHA конкретного commit/список commit**, их зависимости и совместимость с `captivprod/main`. Номер `#256` обозначает Issue/PR, но не SHA.

В безопасной временной ветке от `captivprod/main` можно применить `git cherry-pick -x <SHA>`; при merge-commit или зависимостях — перенести точный approved patch либо адаптировать вручную, сохраняя provenance. После независимых тестов оформляется PR в `captivprod/main`, Owner разрешает merge, SysAdmin отдельно получает GO на deploy.

**Без автоматического merge `main` в нашу ветку, без force-push и без прямого применения старых изменений на работающем сервере.** Cherry-pick даёт новый commit SHA даже при том же логическом исправлении; он не обязан переносить все предыдущие работы старой команды.

## 6. Security / data boundary

Не публиковать в GitHub: runtime `.env`, реальные OpenAPI credentials/token, TLS private keys/CA private keys, SQLite/JSONL сессии/посетителей, raw logs/pcap/backups, приватные адреса клиентов/MAC и любые operational secrets. Допустимы reviewed код, тесты, безопасные шаблоны и обезличенные документы.

Изменение исходников общего продукта не даёт права менять старую VM Portal `.202`, Omada Windows `.222`, Cisco, NPM, AP, VLAN/DHCP или production-модули. Текущие правила независимости Captiv-Prod сохраняются.

## 7. Контрольные статусы на 16.10.2026

```text
HOST_SSH_IDENTITY=PASS
SSH_AUTHENTICATION=PASS (key-based sysadmin)
RUNNING_SERVICE_EXECSTART_IDENTIFIED=PASS
WORKTREE_HEAD_TREE_IDENTIFIED=PASS
GIT_WORKTREE_CLEAN=YES
GITHUB_COMMIT_VERIFIED=PASS
CAPTIVPROD_BRANCH_CREATED=PASS
CAPTIVPROD_BRANCH_SHA=b6152459421b48514ddc8af114bcc96e30351cf7
BASELINE_TAG_CREATED=PASS
BASELINE_TAG_SHA=b6152459421b48514ddc8af114bcc96e30351cf7
GITHUB_REF_READBACK=PASS
RUNTIME_LOADED_BYTE_PARITY=NOT_TESTED
GUEST_AP_E2E_IN_THIS_SESSION=NOT_TESTED
BRANCH_PROTECTION=NOT_CONFIGURED
PRODUCTION_SERVICE_RESTART=NO
PRODUCTION_GIT_CHECKOUT_MODIFIED=NO
OLD_PRODUCTION_CHANGED=NO
NEW_PRODUCTION_CHANGED=NO
NEXT_DEPLOY_AUTHORIZED=NO
```

**Tech Lead disposition:** Git-source baseline и публикация refs — `PASS`. Это **не** новый production release acceptance и не лицензия на автоматический deploy/merge. Зафиксированная нулевая версия сохраняется постоянной меткой; развитие ведётся через reviewable PR в `captivprod/main`.

---

*Источники фиксации: непосредственный read-only SSH осмотр `captiv-prod`, ответ GitHub API о commit и о создании/повторном чтении двух Git refs, архитектурный документ `CAPTIVPROD_ARCHITECTURE_AND_TEAM_RULES_v1.md`. Секреты и содержимое пользовательских данных не извлекались.*
