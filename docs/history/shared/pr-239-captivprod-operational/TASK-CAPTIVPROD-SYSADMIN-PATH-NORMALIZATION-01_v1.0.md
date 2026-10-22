# CAPTIV-PROD — Техническое задание для SysAdmin

## Нормализация размещения исходников Portal без изменения production-кода и данных

**TASK ID:** `TASK-CAPTIVPROD-SYSADMIN-PATH-NORMALIZATION-01`  
**Редакция:** `v1.0`, 2026-10-18 (Asia/Baku)  
**Заказчик:** Owner · **Архитектурный контракт:** Captiv-Prod Architect  
**Исполнитель:** Captiv-Prod SysAdmin · **Приёмка:** Tech Lead + Owner, независимая QA по необходимости  
**Хост:** `captiv-prod`, `192.168.0.99`  
**Статус:** **ТЗ ГОТОВО; ТОЛЬКО READ-ONLY PREFLIGHT РАЗРЕШЁН ПРИ ПЕРЕДАЧЕ. PREP/ACTIVATE НЕ РАЗРЕШЕНЫ БЕЗ ОТДЕЛЬНЫХ OWNER GO.**

> **Не путать с GitHub Issue #230:** там речь об исправлении Omada webhook classification в **коде** (задача Coder). Настоящее ТЗ — исключительно об аккуратном размещении **уже работающего Portal source checkout** на новом сервере. Оно также не является разрешением на релиз #233 или на включение новых Omada webhooks.

## 1. Результат, который должен получить Owner

Непонятный экспериментальный путь `/opt/captivprod-portal-v2fix`, от которого сегодня запущены Portal и его зависимые процессы, больше не фигурирует в их **effective systemd configuration**. Запускаемый код берётся по понятному постоянному пути:

```text
/opt/captivprod/portal/
├── current -> /opt/captivprod/portal/releases/<APPROVED_SHA>
└── releases/
    └── <APPROVED_SHA>/                  # отдельный Git worktree (detached)
```

**Source-only relocation**: исполняется **тот же самый Git SHA/TREE**, в том же существующем Python venv, с теми же внешними переменными среды и SQLite файлами. Не должна незаметно появиться новая версия приложения, схема БД, настройки Omada, сетевые пути, NPM, дополнительные процессы, изменённые флаги или пересозданные данные.

При неудаче SysAdmin восстанавливает старые systemd paths и возвращает все 7 служб на исходный `/opt/captivprod-portal-v2fix`, не выполняя `git reset`, не удаляя базы и не меняя сетевые настройки.

### Почему именно так

1. `/opt/captivprod-portal-v2fix` — **linked Git worktree**, а не обычная папка, которую можно свободно переименовать: его `.git` — файл-ссылка на `/opt/captivprod-portal/.git/worktrees/captivprod-portal-v2fix`.
2. `/opt/captivprod-portal` уже занят основным Git repository/worktree, со **своим** историческим checkout; переименовать/удалить его, чтобы освободить красивое имя, нельзя без перепривязки Git metadata.
3. Путь `/opt/CaptivePortal` — **отдельное постоянное data/log хранилище**, не переименовывать вместе с source.
4. Раздельные `current` и `releases/<SHA>` обеспечивают воспроизводимость кода, управляемое переключение и откат, не требуя изменения Python-кода.
5. Прямое `mv /opt/captivprod-portal-v2fix ...`, подмена рабочей `.git`, копирование текущих файлов поверх живого source и переименование `/opt/CaptivePortal` **ЗАПРЕЩЕНЫ**.

## 2. Проверенный фактический baseline (READ-ONLY, 18.10.2026)

Проверки выполнены по SSH без изменений сервера. Точность данных ограничена временем проверки — SysAdmin **обязан** сверить их непосредственно перед исполнением. Полученные секреты/гостевые данные не извлекались.

| Объект | Подтверждённое состояние |
|---|---|
| Active Portal code | `/opt/captivprod-portal-v2fix` |
| Code SHA | `b6152459421b48514ddc8af114bcc96e30351cf7` |
| Code TREE | `3dd3588bdae279660fcbf4e9c5310282041c01e9` |
| Status worktree | `git status --porcelain` пуст |
| Linked-worktree metadata | `/opt/captivprod-portal/.git/worktrees/captivprod-portal-v2fix` |
| Git anchor | `/opt/captivprod-portal`, HEAD `191beda1f23f8f466d2431f42e57571815d85778` (оставить на месте) |
| Python runtime | `/opt/captivprod-portal-venv/bin/python` (оставить на месте) |
| Persistent App data/logs | `/opt/CaptivePortal/data`, `/opt/CaptivePortal/logs` (оставить на месте) |
| Evidence receiver data | `/var/lib/captivprod-evidence` (оставить на месте) |
| Sensor source/runtime | `/opt/captivprod-sensor-src`, `/opt/captivprod-sensor-venv` (оставить на месте) |
| Sensor state | `/var/lib/captivprod-sensor`, `/run/captive-portal/fingerprint-sensor` (оставить) |
| Omada | `tpeap.service` и vendor `/opt/tplink/EAPController` (оставить) |
| NPM | `/opt/nginx-proxy-manager/compose.yaml`, контейнер Docker (оставить) |
| Root filesystem | `/dev/mapper/ubuntu--vg-ubuntu--lv`, ext4, ~98 GiB total, ~79 GiB free при проверке |
| Backup volume | `/srv/backups` подтверждён как **отдельный ext4 mount `/dev/sdb1`**, ~888 GiB free (18.10.2026); `captiv-backup.service` в момент проверки inactive между расписаниями |
| Main service statuses | все 7 затронутых units — `active`, `enabled` |
| Adjacent services | `tpeap`, `fingerprint-sensor`, `fingerprint-suricata`, NET01 firewall/watchdog — `active` |

Существующий `captivprod/main` на GitHub **может быть новее** действующего SHA. **Намеренно не совмещать** перенос путей с source upgrade, roaming релизом #233 и импортом Fingerprint PR #222/#229. Отдельный approved release SHA — отдельная задача.

### 2.1 Исчерпывающий подтверждённый список прямых зависимостей от старого source path

| Unit (7) | Existing WorkingDirectory | Existing ExecStart | Доп. зависимость |
|---|---|---|---|
| `captive-portal.service` | `...-v2fix` | `/opt/captivprod-portal-venv/bin/python /opt/captivprod-portal-v2fix/run.py` | `net01.conf`, NET01 start-admit, Docker/firewall guard; изменить **оба** пути |
| `fingerprint-evidence.service` | `...-v2fix` | `/opt/captivprod-portal-venv/bin/python -m app.device_fingerprint.cli run` | `/etc/captive-portal/device-fingerprint/receiver.env`, пользователь `captiv-evidence` |
| `fingerprint-classification.service` | `...-v2fix` | `/opt/captivprod-portal-venv/bin/python -m app.device_fingerprint_integration.cli run` | `portal.env`, пользователь `captivportal`, supplementary `captiv-evidence` |
| `traffic-projection.service` | `...-v2fix` | `/opt/captivprod-portal-venv/bin/python -m app.traffic_projection.cli run` | `portal.env` |
| `network-metadata.service` | `...-v2fix` | `/opt/captivprod-portal-venv/bin/python -m app.network_metadata.cli run` | `network-metadata.env`, `suricata` group |
| `network-metadata-projection.service` | `...-v2fix` | `/opt/captivprod-portal-venv/bin/python -m app.network_metadata_projection.cli run` | `network-metadata-projection.env`, sensor group |
| `network-service-recognition.service` | `...-v2fix` | `/opt/captivprod-portal-venv/bin/python -m app.network_service_recognition.cli run` | `network-service-recognition.env` |

Во всех семи меняется `WorkingDirectory`. **Только** у `captive-portal.service` `ExecStart` содержит абсолютный путь к `run.py`: его необходимо переопределить. В `captive-portal`, `fingerprint-evidence`, `traffic-projection`, `network-metadata`, `network-metadata-projection`, `network-service-recognition` также обнаружен `Environment=GIT_CONFIG_VALUE_0=/opt/captivprod-portal-v2fix`: нужно обновить для Git safe.directory. В `fingerprint-classification.service` такой текущей строки не обнаружено; не вводить новую без причины.

**Не менять:** `User/Group/SupplementaryGroups`, `EnvironmentFile`, existing drop-ins, `ReadWritePaths`, `ProtectSystem`, `ExecStartPre`, `After/Requires/Wants`, venv path, flags, порты, сервисные credentials. Уже существующий `captive-portal.service.d/net01.conf` **оставить как есть**.

### 2.2 Существующие persistent path bindings (намеренно НЕ перемещаются)

- `SETTINGS_DB_PATH=/opt/CaptivePortal/data/settings.sqlite3`;
- Visit/Registry/Traffic/Fingerprint/Network Metadata и Service Intelligence DB — под `/opt/CaptivePortal/data` согласно отдельным конфигурациям;
- Evidence Receiver: `/var/lib/captivprod-evidence/evidence.sqlite3`;
- Network Attribution: `/var/lib/captivprod-sensor/network_attribution.sqlite3`;
- Suricata source: `/run/fingerprint-suricata/dti-ni-v1.eve.json`;
- Configs: `/etc/captive-portal/*.env`, `/etc/captive-portal/device-fingerprint/*.env`, не включать их содержимое в публичные отчёты.

**Отдельная известная проблема**: Fingerprint Device Hints может требовать корректный runtime Evidence read path/ACL; это самостоятельный релиз/Task #233, **не исправлять в данном rename-only Task**.

### 2.3 Смежные компоненты, которые менять НЕ нужно

`fingerprint-sensor`, `fingerprint-suricata`, `tpeap/omada`, `captiv-net01-firewall`, `captiv-net01-watchdog`, `captiv-omada-guard`, Docker/NPM, `network-metadata-rotation.timer`, `captiv-omada-native-mirror.timer`, `captiv-backup.timer`, `captiv-npm-backup-online.timer`, Cisco 3845/2960, AP, SSID, VLAN60, DHCP/CAPPORT, DNS, certificates, старые `.202`/`.222` и старый FQDN.

Все таймеры и смежные службы **проверяются до/после**, но не перенастраиваются. Окно работ не совмещать с ежедневными backup около 03:10/03:30 UTC или иными активными maintenance jobs; 5-минутный NI rotation учитывать при выборе окна.

### 2.4 Проверка других hard-coded references

Read-only поиск точного `/opt/captivprod-portal-v2fix` в `/etc/systemd/system`, `/etc/captive-portal`, `/usr/local/{sbin,bin,libexec}`, cron, `/etc/default`, `/etc/logrotate.d` обнаружил семь units и их `multi-user.target.wants` symlinks. В скриптах NET01 и backup **прямого совпадения с этим строковым путём** при проверенном поиске не обнаружено. Это **не доказательство отсутствия динамически собранных/непроверенных ссылок**.

В preflight повторить grep; если появится дополнительный потребитель — **HOLD**, включить его в согласованный manifest и только потом выполнять migration. **Не редактировать символические ссылки `multi-user.target.wants`**: они указывают на те же базовые unit files, которые остаются в прежнем месте.

## 3. Архитектурное решение: Git + systemd

**Canonical stable entry:** `/opt/captivprod/portal/current` — symlink на неизменяемый source snapshot. 

**Release directories:** `/opt/captivprod/portal/releases/<full-40-char-SHA>` — checkout через `git worktree add --detach` от существующего git-anchor `/opt/captivprod-portal`. Старый source `/opt/captivprod-portal-v2fix` не удалять. Не менять HEAD общего root repo, не делать branch checkout в production.

**Unit modifications — строго drop-ins**, а не переписывание базовых unit files:

```ini
# /etc/systemd/system/<unit>.service.d/90-captivprod-canonical-path.conf
# CAPTIVPROD-PATH-CUTOVER-01
[Service]
WorkingDirectory=/opt/captivprod/portal/current
Environment=GIT_CONFIG_VALUE_0=/opt/captivprod/portal/current
```

Для `fingerprint-classification` — **только** `WorkingDirectory`, без `Environment=GIT_CONFIG_VALUE_0`.

Дополнительные две строки **только для `captive-portal`**:

```ini
ExecStart=
ExecStart=/opt/captivprod-portal-venv/bin/python /opt/captivprod/portal/current/run.py
```

`ExecStart=` без значения — обязательный systemd reset старого запуска перед новым `ExecStart` (не удалить старый `ExecStartPre`). `GIT_CONFIG_VALUE_0` переопределяется поверх исходного `Environment=GIT_CONFIG_COUNT=1 / GIT_CONFIG_KEY_0=safe.directory`. При загрузке нового кода обязательно проверить `git -C /opt/captivprod/portal/current` под обоими service UIDs, если приложение читает Git provenance. Если safe.directory/path resolution не работает, **HOLD** до согласованного узкого исправления; не делать `git config --global --add safe.directory '*'`.

## 4. Пакет исполнения

К ТЗ приложены shell scripts, которые являются **предлагаемыми исполняемыми приложениями** (перед реальным использованием SysAdmin проверяет SHA256 файлов и запускает в контролируемой shell-среде):

| File | Назначение | Изменяет production? |
|---|---|---|
| `01_preflight_readonly.sh` | SHA, tree, чистота Git, текущие units, active guards, дисковая база | **Нет** |
| `02_prepare_release.sh` | Создать отдельный Git worktree с ТОЧНО тем же SHA и initial symlink | **Да**, только подготовка source path/Git metadata, без restart |
| `03_activate_release.sh` | Backup units, остановить 7 services, применить path-only drop-ins, запустить, 60s check | **Да**, требуется отдельный Owner DEPLOY GO |
| `04_rollback.sh` | Удалить только свои path drop-ins, вернуть все 7 units на старый source | **Да**, emergency rollback по утверждённому сценарию |

Scripts зашиты под **проверенный на 18 октября** SHA. **Если к моменту работы source SHA/TREE или unit shape изменились — STOP/HOLD; не подставлять новые SHA автоматически и не продолжать в надежде, что «и так сойдёт».** Выдать Architect/Tech Lead read-only drift report, обновить package v1.1 отдельно.

### G0 — обязательный read-only preflight (можно выполнять раньше окна, никаких мутаций)

```bash
sudo bash 01_preflight_readonly.sh
```

**G0 PASS только если:** hostname, SHA+tree, `git status`, old WorkingDirectory всех семи, root Git metadata, venv, data/log, смежные units, отсутствие ранее созданных target paths/drop-ins, место на диске — подтверждены.

Вручную SysAdmin также обязан: (a) повторить внешний reference-scan из §2.4, (b) удостовериться, что сам Git source по-прежнему связан с доверенным `captivprod/main` baseline, (c) проверить реальные backup snapshots, что `/srv/backups` **отдельно смонтирован**, и что нет активного backup/maintenance, (d) зафиксировать текущие `systemctl show` для 7 units и список их реально работающих PIDs, (e) зафиксировать текущий HTTP/Admin/CAPPORT / Omada / Network Intelligence health **без гостевых персональных данных**, (f) получить maintenance window и уведомить Owner о кратком простое Portal / metadata consumers / Evidence receiver.

**Preflight никогда не является GO для переключения.** Если пропущены проверки — HOLD.

### G1 — preparation (только после отдельного `OWNER_GO_PREP`)

```bash
sudo bash 02_prepare_release.sh --owner-go-prep-recorded
```

Ожидаемый результат:

```text
/opt/captivprod/portal/releases/b6152459421b48514ddc8af114bcc96e30351cf7/
/opt/captivprod/portal/current -> .../releases/b6152459421b48514ddc8af114bcc96e30351cf7
```

Проверить `git rev-parse HEAD`, `HEAD^{tree}`, clean worktree, root-owned read-only code, Python import под `captivportal` и `captiv-evidence`, сохранность исходного old worktree и его общих Git metadata. **Ни одного systemd edit/restart** на G1. Если import path/generation/runtime permissions отличаются — HOLD. Дополнительно проверить safe.directory именно под service UIDs, чтобы прежде чем остановить хоть один сервис не обнаружить проблему.

### G2 — switch (только после `OWNER_GO_DEPLOY` и принятого rollback plan)

```bash
sudo bash 03_activate_release.sh --owner-go-deploy-recorded
```

Скрипт сохраняет копии **семи исходных unit files** в приватный каталог на проверенном отдельном mount `/srv/backups/captivprod-path-cutover/<UTC>` с правами `0700/0600`. Если `/srv/backups` не отдельный mount — **автоматический HOLD**, другой backup destination определять заранее, а не менять команду на ходу.

**Stop order (зависимые → upstream):**

```text
network-service-recognition
network-metadata-projection
network-metadata
traffic-projection
fingerprint-classification
captive-portal
fingerprint-evidence
```

`fingerprint-sensor` и `fingerprint-suricata` **не останавливать**: перед окном проверить способность spool выдержать краткую остановку Evidence Receiver. Если нет доказанного буфера/ограничений — HOLD и определить безопасное окно/смягчение до GO; нельзя обещать, что ни один fingerprint event не пропадёт.

**Start order (upstream → зависимые):**

```text
fingerprint-evidence
captive-portal
fingerprint-classification
traffic-projection
network-metadata
network-metadata-projection
network-service-recognition
```

В рамках G2 скрипт выполняет `systemctl daemon-reload`, проверяет effective WorkingDirectory, запускает сервисы и через 60 сек проверяет active PID + фактический `/proc/<PID>/cwd` (он должен разрешаться в approved release directory). При системном сбое/ошибке G2 скрипт вызывает rollback. Это только **basic 60-sec health**; E2E не подменяется простым `active`.

**Не выполнять здесь:** `systemctl restart tpeap`, перезапуск NPM/Docker, SSH/network rebuild, `git pull`, изменение firewall/NAT, миграции SQLite, обновление Python dependencies, перезапуск всего сервера, изменение AP/webhooks. Нет задачи редактировать `/etc/captive-portal/*.env` или application source.

### G3 — обязательная функциональная приёмка после basic health

Проверить на том же SHA/TREE, что был до переключения:

- **Service state:** 7/7 `active` + все старые units имели `enabled`, те же UIDs / env files / groups / hardening; также `fingerprint-sensor`, `fingerprint-suricata`, `tpeap`, NET01 firewall/watchdog по-прежнему в штатном состоянии; без неожиданного второго экземпляра Python/receiver.
- **Git/Python:** все 7 PID используют новый resolved cwd; Portal cmdline использует `/opt/captivprod/portal/current/run.py`; `import app` под обоими затронутыми пользователями; loaded source SHA/TREE совпадает approved identity.
- **Portal/Web:** `captivprod-navi.duckdns.org` через текущий NPM/NET01 прежним образом; CAPPORT/API и Admin login/read-only на новом FQDN функционируют. Нельзя объявлять E2E PASS по одному HTTP 200 на `/`.
- **Guest/Auth/Visit:** контролируемый телефон Owner, новый SSID `Zefer_Parki`, настоящий authorized CAPPORT flow; Visit open/close **только** если источник offline действительно получен. Не менять AP provisioning/subscriptions ради теста.
- **Network Intelligence:** evidence receiver продолжает прием, sensor/Suricata не теряют штатную работоспособность, network-metadata/projection/traffic-projection/service-recognition сохраняют свои штатные checkpoints и приём без новых необъяснимых ошибок/разрывов.
- **Stability:** повторная проверка через ~10–15 минут: logs/journal errors, 503/5xx, worker lag, SQLite locks, физические HDD I/O, CPU/RAM; сравнить с числовым preflight baseline. Если реальные функции нельзя проверить — записать `NOT_TESTED`, не `PASS`.
- **Backups/restore:** конфиги и old unit snapshots восстановимы; после path cutover проверить, что scheduled backup продолжает включать **постоянные SQLite и секреты**, а не случайно новый checkout как замену данным. Отдельный SQLite Online Backup TASK имеет собственную приёмку; обычный `rsync` работающих SQLite не объявлять полноценно согласованным restore.

**G3 acceptance:** Tech Lead присылает Owner компактный отчёт `BEFORE → AFTER`, exact SHA/tree, 7 units, сеть/Omada/CAPPORT, Admin, fingerprint, NI, backup/rollback и P0/P1. Наличие отдельной ссылки на Coder QA test suite **не обязательно**, поскольку это **не новый код**, но независимая эксплуатационная проверка желательна. До полноценной проверки статус только `PATH_CUTOVER_BASIC_HEALTH=PASS`, а не `PRODUCTION_ACCEPTANCE=PASS`.

### G4 — rollback (разрешён только внутри approved cutover window при stop criteria)

```bash
sudo bash 04_rollback.sh --approved-path-cutover-rollback
```

Rollback удаляет **только** drop-ins, помеченные `# CAPTIVPROD-PATH-CUTOVER-01`, возвращает исходный `WorkingDirectory` и старый `ExecStart` через base units, делает daemon-reload и запускает семь служб. Старый `/opt/captivprod-portal-v2fix` и `/opt/captivprod-portal` **обязательно сохранять**. **Не удалять** `/opt/captivprod/portal/current` или release worktree в рамках emergency rollback: после стабилизации их исследуют отдельно.

**Rollback trigger:** любой unit не запускается/не active через 60 sec, Git SHA/tree mismatch, runtime dir/cwd неверен, auth/CAPPORT отказ, Evidence receiver перестал принимать, NET01 firewall rejects корректный NPM путь, P1 regression на Visit/traffic, существенный неописанный рост ошибок/503/I/O. После rollback — полноценная проверка G3 на **старом** source path и отчёт Owner; никаких молчаливых повторных попыток.

Если rollback тоже не восстановил здоровье — `CRITICAL/HOLD`, сохранить logs и debug evidence, уведомить Owner, не трогать Cisco/Omada/firewall в поисках обходного решения.

## 5. Control gates и change authority

| Gate | Разрешено | Условие перехода |
|---|---|---|
| `G0 READ_ONLY` | Только чтение, подготовка отчёта | PASS по фактическим зависимостям |
| `G1 PREP` | Создать Git worktree + stable symlink | **Отдельный `OWNER_GO_PREP`**, без restarts |
| `G2 DEPLOY` | Изменить 7 systemd drop-ins и controlled restarts | **Отдельный `OWNER_GO_DEPLOY`**, backup+rollback+window |
| `G3 ACCEPT` | Функциональный тест и независимый контроль | Tech Lead PASS, затем Owner acceptance |
| `G4 ROLLBACK` | Вернуть исходные пути в утверждённом окне | stop criteria, сохранённый old source |
| `CLEANUP` | Удаление старых worktrees/references | **НЕ входит** в TASK; отдельная задача и GO |

**Роль SysAdmin — механический исполнитель именно этого плана.** Любой drift SHA/paths, неожиданный unit, проблемы env/Git safe.directory, права, backup, попытка использовать иной release SHA или изменения существующего release tracker #233 — STOP. SysAdmin не придумывает workaround на работающем Portal; эскалирует Architect/Tech Lead с точной технической причиной.

## 6. Итоговый шаблон отчёта исполнителя

```text
TASK=TASK-CAPTIVPROD-SYSADMIN-PATH-NORMALIZATION-01
HOST=captiv-prod
EXECUTION_TIME_UTC=
OWNER_GO_PREP=LINK_OR_NONE
OWNER_GO_DEPLOY=LINK_OR_NONE

PRE_SHA=b6152459421b48514ddc8af114bcc96e30351cf7
PRE_TREE=3dd3588bdae279660fcbf4e9c5310282041c01e9
POST_SHA=
POST_TREE=
SOURCE_CHANGE=NO
GIT_WORKTREE_CLEAN=PASS/HOLD
GIT_ANCHOR_UNCHANGED=PASS/HOLD
CURRENT_SYMLINK_TARGET=
ROLLBACK_SOURCE_AVAILABLE=PASS/HOLD

UNITS_7_WORKDIR=PASS/HOLD
UNIT_PORTAL_EXECSTART=PASS/HOLD
UNIT_GIT_SAFE_DIRECTORY=PASS/HOLD
UNITS_7_ACTIVE=PASS/HOLD
PROTECTED_SERVICES_UNTOUCHED=PASS/HOLD
PID_CWD_SEVEN=PASS/HOLD
ENV_DB_PATHS_UNCHANGED=PASS/HOLD
BACKUP_MOUNT_AND_CONFIG_SNAPSHOT=PASS/HOLD
RESTART_60SEC=PASS/HOLD
NPM_NET01_CAPPORT=PASS/HOLD/NOT_TESTED
ADMIN_UI=PASS/HOLD/NOT_TESTED
OWNER_GUEST_E2E=PASS/HOLD/NOT_TESTED
EVIDENCE_AND_NI=PASS/HOLD/NOT_TESTED
CPU_RAM_IO_10_15MIN=PASS/HOLD/NOT_TESTED
BACKUP_RESTORE_READY=PASS/HOLD/NOT_TESTED
ROLLBACK_TRIAL_OR_READINESS=PASS/HOLD/NOT_TESTED

BLOCKERS=
ACTIONS_TAKEN=
PROD_OR_LEGACY_SIDE_EFFECTS=NONE/DETAILS
SYSADMIN_VERDICT=PASS/HOLD/ROLLBACK/FAIL
TECH_LEAD_VERDICT=PASS/HOLD/PENDING
OWNER_FINAL_ACCEPTANCE=PENDING/APPROVED
```

## 7. Источники и границы доказанности

1. `CAPTIVPROD_ARCHITECTURE_AND_TEAM_RULES_v1.md` — роли, независимость старого/нового PROD, Owner GO, запрет несанкционированных production изменений.
2. `CAPTIVPROD_GITHUB_BRANCH_ZERO_BASELINE_POLICY_2026-10-16_v1.0.md` — исходные Git/source SHA/TREE, linked worktree, ветка `captivprod/main`, запрет прямого deploy из `main`.
3. `CAPTIVPROD_NETWORK_ROUTING_AND_ACCESS_BASELINE_2026-10-16_v1.md` — NPM 172.18.0.2 → 172.18.0.1:18089, NET01 firewall guard, VLAN60, Cisco; **не менять**.
4. `CAPTIVPROD_FULL_BACKEND_AUDIT_2026-10-16_v1.0.md` — status компонентов, data/backup риски.
5. **Live SSH READ-ONLY 18.10.2026 около 12:08–12:11 UTC** — `systemctl show/cat`, активные PID CWD, Git worktree-list/status, 7 direct path users, service units, env file **path keys only**, таймеры, root filesystem. После исходного снимка никаких production edits не выполнялось.
6. Исполняемые приложения проверены `bash -n` в рабочем контейнере при выпуске v1.0. **Ни один из скриптов НЕ запускался на боевом сервере**; успешный script syntax НЕ является проверкой реального cutover/rollback, прав, доступности backup mount или полного E2E.

**ARCHITECT VERDICT:** `READY_FOR_OWNER_REVIEW_AND_FUTURE_SYSADMIN_EXECUTION`, `PRODUCTION_CHANGE=HOLD_OWNER_GO`.
