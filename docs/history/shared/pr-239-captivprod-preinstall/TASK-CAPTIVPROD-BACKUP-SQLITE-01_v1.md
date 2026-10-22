# TASK-CAPTIVPROD-BACKUP-SQLITE-01 — Application-consistent Backup & Restore

**Версия:** v1.0 (предложение Tech Lead; готово для архитектурного review, не разрешение на production changes)  
**Дата:** 2026-10-17  
**Основание:** QA Finding `CP-QA-BACKUP-001`, P1 Data Integrity / Disaster Recovery  
**Контур:** только `captiv-prod` (`192.168.0.99`)  
**Owner GO:** REQUIRED для production deployment/activation  
**Текущий QA:** `BACKUP_RECOVERY=HOLD`  
**Исполнители:** Architect — контракт межбазовой согласованности; Tech Lead — delivery; Coder/SysAdmin — реализация; независимый QA — acceptance.

## 1. Краткое решение

Действующий ежедневный системный backup **сохранить**, но перестать считать прямой `rsync` открытых SQLite доказуемым восстановимым snapshot. Подготовить согласованные **онлайн-копии SQLite Backup API**, интегрировать их в неизменяемый системный snapshot и добавить обязательный изолированный restore test и проверки межбазовых инвариантов.

**Принцип:** один файл SQLite можно корректно скопировать без остановки работающего приложения; несколько отдельных SQLite-файлов при этом **не обязаны соответствовать одному моменту времени**. Нужен отдельный, явно принятый контракт multi-DB recovery, см. §5.

**Не делать:** `cp/rsync` живых `*.sqlite3`/`*.db`/WAL как единственное резервирование; форсированный checkpoint; отключение WAL или изменение SQLite durability; отключение `captiv-backup` до появления замены; импорт тестовых данных в production; внешние вызовы Omada при restore smoke.

## 2. Доказанный baseline (read-only, 17 октября 2026)

- `captiv-backup.timer`: ежедневный запуск **03:30 UTC** (07:30 Asia/Baku), `Persistent=true`.
- `/usr/local/sbin/captiv-backup-run`: последовательно `captiv-backup-system`, `captiv-backup-retention`, затем обновляет маркеры последнего успеха в `/var/lib/captiv-backup/`.
- `/usr/local/sbin/captiv-backup-system`: проверяет UUID выделенного ext4 `/srv/backups` (`/dev/sdb1`), `flock`, затем `rsync -aHAXx --numeric-ids` живой `/` в `.incomplete-*`, `--link-dest` на предыдущий snapshot, собирает OS manifest, атомарно переводит каталог и ссылку `latest`. Базы не исключает; SQLite Backup API не вызывает.
- `/usr/local/sbin/captiv-backup-retention`: **30** последних системных snapshot-каталогов.
- Последний проверенный snapshot: `/srv/backups/snapshots/20261017T033019Z`, статус `BACKUP_STATUS=PASS`. Все 17 найденных SQLite в его файловых копиях имеют `PRAGMA quick_check(1)=ok`. **Это не свидетельство транзакционной или межбазовой согласованности**, и полного restore не было.
- Подтверждены WAL-файлы, в том числе у `network_metadata`, `network_metadata_projection`, `network_service_intelligence`, `evidence` и `network_attribution`; базы используют не одинаковые journal modes.
- На сервере существуют самостоятельные механизмы `captiv-npm-backup-online` и `captiv-omada-native-mirror` (последние исполнения PASS); не смешивать их с гарантиями Portal SQLite.
- Backup ext4 — **второй диск на том же физическом хосте**, а не off-site копия. Требуется отдельная задача для защиты от общей потери/компрометации хоста.
- В корневом snapshot входят `/etc/captive-portal`, unit-файлы, TLS/CA materials и файлы приложений. Нужны проверка восстановления секретов, прав/ownership и отдельная оценка защиты backup at rest; пароли и ключи в evidence не выводить.
- Production Git baseline при аудите: `ZaurNavi/CaptivePortal@b6152459421b48514ddc8af114bcc96e30351cf7`; рабочий checkout чистый.

### 2.1 Полный реестр SQLite (17 реальных баз)

| № | Файл (полный путь или относительно указанной директории) | Роль / writer | Restore-класс, предварительно |
|---|---|---|---|
| 1 | `/opt/CaptivePortal/data/visits.sqlite3` | Portal / Visit Lifecycle: визиты и source offsets | A — authoritative |
| 2 | `/opt/CaptivePortal/data/visitor_registry.sqlite3` | Portal: устройства и снимки | A — authoritative |
| 3 | `/opt/CaptivePortal/data/settings.sqlite3` | Portal: generations/overrides | A — authoritative; связан с ключами |
| 4 | `/opt/CaptivePortal/data/portal_counter.db` | Portal: счётчик | A/B — подтвердить источник и replay |
| 5 | `/opt/CaptivePortal/data/public_traffic.sqlite3` | Portal: агрегат трафика / dedup | A/B — проверить replay и offsets |
| 6 | `/opt/CaptivePortal/data/observations.sqlite3` | Portal: AP/client observations | A/B — source history, проверить rebuild |
| 7 | `/opt/CaptivePortal/data/current_state.sqlite3` | Portal: текущие снимки | B — derived при доказанном rebuild |
| 8 | `/opt/CaptivePortal/data/traffic_projection.sqlite3` | `traffic-projection.service` | B — derived, checkpoint-bound |
| 9 | `/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3` | `fingerprint-classification.service` / Portal: job & identity state | A — authoritative job lifecycle |
| 10 | `/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3` | `fingerprint-classification.service`: результаты/артефакты | A — authoritative until replay contract proved |
| 11 | `/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3` | Control Plane: активные профили/допуски | A — critical authoritative |
| 12 | `/opt/CaptivePortal/data/network_metadata.sqlite3` | `network-metadata.service`: исходные нормализованные события и offsets | A — source-of-truth for NI downstream; ограниченное replay |
| 13 | `/opt/CaptivePortal/data/network_metadata_projection.sqlite3` | `network-metadata-projection.service` | B — derived, но содержит reset epochs/checkpoints/feed |
| 14 | `/opt/CaptivePortal/data/network_service_intelligence.sqlite3` | `network-service-recognition.service` | B — derived с feed cursor |
| 15 | `/var/lib/captivprod-evidence/evidence.sqlite3` | `fingerprint-evidence.service`: received evidence | A — raw authoritative |
| 16 | `/var/lib/captivprod-sensor/network_attribution.sqlite3` | `fingerprint-sensor.service`: DHCP/authority | A/B — временные первичные привязки, восстановление уточнить |
| 17 | `/var/lib/captivprod-sensor/spool.sqlite3` | `fingerprint-sensor.service`: unacknowledged delivery | A — in-flight queue, dedup/replay critical |

A/B означает, что исполнитель **не имеет права** удалять или регенерировать базу по предположению. Architect/maintainer должен подтвердить источник истины, допустимые потери и метод безопасного replay. На старте **копировать все 17**, включая derived: это минимизирует опасность до доказательства rebuild-пути.

**Регистр не должен быть жёстко «навсегда 17»:** перед каждым запуском перечислять реальные SQLite в утверждённых production data roots и сверять с манифестом. Новая/неизвестная БД, изменённый path или обнаруженный произвольный WAL-компаньон вызывают отказ backup acceptance до обновления allowlist/контракта; не оставлять базу незамеченной.

## 3. Задача для Coder/SysAdmin (ограниченная)

### A. Версионированная утилита online SQLite backup

1. Реализовать переносимый, тестируемый Python CLI на стандартном `sqlite3.Connection.backup()` с исходным SQLite в read-only connection; сохранять данные в отдельный staging-каталог на выделенном backup volume. Не выполнять SQL, модифицирующий source.
2. Поддержать 17 целевых путей, схемные версии, `journal_mode`, `page_size`, source file metadata, time window каждой копии, исходный host, app Git SHA и dependency manifest. Для каждого результата: schema/content fingerprint, размер, SHA-256, `PRAGMA integrity_check`, `PRAGMA foreign_key_check` (где применимо), счётчики/границы или схематические метаданные без персональных данных.
3. Destination записывать в уникальный **новый файл** (`open exclusive`) с временным именем; fsync файла и каталога, `os.replace` в окончательное место. Права 0600, минимальные права доступа и сохранение проверенных UID/GID при restore. Не вносить изменения в предыдущие backup snapshots, включая hardlinked `--link-dest` файлы.
4. Не делать source-side WAL checkpoint, `VACUUM`, `PRAGMA journal_mode` modification или durability downgrade. Учитывать busy/locked, timeouts, bounded retries, disk-full, IO throttling и частичные операции. **Одна недокопированная БД = весь application SQLite pack FAILED.**
5. Утилита никогда не передаёт настоящие secret values в CLI-аргументах, logs, QA evidence или Git; производственный инвентарь конфигурации читать по доверенным путям.

### B. Интеграция с существующим backup

1. Сохранить ежедневный `captiv-backup` и предыдущие snapshots. В существующем `captiv-backup-system` под текущим flock и mount UUID gate сформировать набор SQLite online backups **как обязательный этап до публикации `latest`**.
2. Убрать прямое копирование живых DB, `-wal`, `-shm`, `-journal` **только для зарегистрированных app SQLite paths** из root `rsync`, или гарантированно заместить эти файлы валидированными app copies. В готовом snapshot должно быть **по одному каноническому восстановимому DB-файлу на каждый путь**, без сырых WAL/SHM, собранных в другой момент. Не исключать весь `/opt/CaptivePortal/data` и его необработанные файлы.
3. Даже при `--link-dest` файлы новых SQLite snapshots записывать только через create-new+atomic rename; никогда не выполнять SQLite Backup API поверх hardlinked copy из старого snapshot.
4. Только после 17/17 PASS, validation + manifest checksum и согласованных dependency gates — атомарно публиковать snapshot и last-success marker. При FAIL оставить предыдущий `latest`, остановить публикацию новой копии, записать явный failure и сохранить пригодный evidence (без секретов).
5. Формат `snapshot/meta/portal-sqlite-manifest.json` версионировать; фиксировать UTC start/end для каждой БД, journal mode и backup byte count. Отметить многобазовую модель/ограничения; никогда не писать в manifest «одновременный снимок» без proof.

### C. Межбазовая согласованность — **ARCHITECT DECISION REQUIRED**

Просто 17 × Backup API означает **17 разных моментов**, и этого недостаточно для безусловного `MULTI_DB_CONSISTENCY=PASS`.

**Предпочтительная первая архитектура, если подтверждена проверками:** independently consistent DB + **dependency-aware restore gate** + безопасный selective rebuild derived states. Для не-переигрываемых authoritative данных — ограниченная причинная согласованность (пары должны иметь существующие referenced records). Никакая связь/offset не может указывать на данные «из будущего», отсутствующие в скопированном source. Это **документированная ограниченная модель**, а не атомарная гарантия одного timestamp. QA должен принять именно её и заявленный RPO.

Обязательные проверяемые зависимости:

- `visits ↔ visitor_registry`: non-null `visits.device_id` должен существовать в Registry; visit authorization → visit; `offline_event_id` → source event. Учитывать неконтролируемые внешние webhook-source offsets и replay.
- `device_fingerprint_integration ↔ device_fingerprint_classification ↔ device_fingerprint_control_plane`: `CLASSIFIED` job → существующий `classification_id`; каждая сохранённая классификация должна разрешать `classification_runtime_profile_id + digest` и `foundation` в Control Plane; активные pointers/activation graph valid. **Если проверка не проходит — NO AUTO-START CLASSIFICATION.**
- `network_metadata → network_metadata_projection → network_service_intelligence`: cursor/checkpoint/feed_seq в восстанавливаемом downstream не может превышать подтверждённый upstream head; при несоответствии только явно разрешённая очистка/перестройка **derived**, с исходными immutable observations и epoch/reset доказательствами. Не пропускать watermark, не изображать покрытие полным.
- `observations/current_state → traffic_projection`: bounds projection не превышают подтверждённые source cycles; при mismatch расчёт блокируется до документированного rebootstrap/reconciliation.
- `settings.sqlite3` и секреты/ключи (включая controller TLS/credential trust) — одна версия конфигурации и ключевого материала; нельзя восстановить encrypted settings без соответствующего ключа и затем запускать Portal как будто всё OK.
- `evidence ↔ sensor spool`: защищённая семантика ack/dedup при replay; после восстановления не дублировать или терять подтверждённые authoritative events молча.

**HOLD для Architect:** подтвердить (a) границы допустимого RPO для визитов, авторизаций, evidence, control plane и replay очередей; (b) является ли dependency-checked «разновременный снимок» допустимым. Если нет — спроектировать краткий **write fence / bounded quiesce** для группы authoritative writers, с сохранением гостевой доступности, и только затем implementation. Нельзя автоматически останавливать Portal, webhook consumer или Omada ради backup. Не объявлять multi-DB PASS по одному успешному `integrity_check`.

### D. Restore smoke — изолированно и воспроизводимо

1. На отдельной staging filesystem/namespace распаковать **только published immutable snapshot**, проверить manifest/signatures/hashes/DB content, DB file permissions. Нельзя читать незаконченный `.incomplete-*` или подменять production DB.
2. Выполнить `integrity_check`, `foreign_key_check`, необходимые cross-DB SQL invariants (§C), pinned profiles/data schema compatibility и read-only projection/analytics queries.
3. В **network-disabled** изолированной среде (container `--network none` либо netns + строгие no-egress правила) запустить выбранный smoke без подключения к Omada, NPM, webhook, Cisco или живой Portal. Отдельные temp DB, env/key material, без systemd production actions, email/notification, reconnect/cleanup и внешних side effects.
4. Проверить, что могут быть прочитаны настройки, секреты (без вывода значений), valid controller trust materials и нужный Git commit / Python dependencies / service unit definitions. Не выдавать локальную успешную дешифрацию за успешную связь с Omada.
5. Испытать **контролируемые негативные сценарии** только в тестовой среде: ошибка WAL/исходного DB, отсутствующий DB, расхождение classification-profile, неверный service cursor, отсутствие secret key, недостаточно места и падение во время копирования. Fail closed, предыдущий snapshot остаётся `latest`.
6. Документировать точные RPO/RTO, версию скрипта и код restore, лог runtime. QA самостоятельно повторяет процедуры.

### E. Эксплуатация

- Расписание: **сохранить 03:30 UTC ежедневно** на первом этапе. 30 immutable snapshots по текущей политике — только после расчёта размера при росте `network_metadata`/Projection/Evidence; лимит по свободному пространству, пороги warning/fail и запрет заполнения диска.
- I/O: `nice`/`ionice`, ограниченные batch pages/bytes, измерения до/во время/после с HDD `iostat` и `PSI`; утверждённое влияние на гостевой Portal. Не фиксировать «0 нагрузка» без measurements.
- Мониторинг: machine-readable `PORTAL_SQLITE_BACKUP_CONSISTENCY=PASS/FAIL`, `PORTAL_SQLITE_RESTORE_SMOKE=PASS/FAIL`, timestamp/age, DB count, bytes, last gate, disk free; OnFailure alert + отсутствие обновления last-success на FAIL; регулярный изолированный restore smoke (предпочтительно по расписанию не реже еженедельно).
- Backups содержат секреты и ключи: root-only, audit permissions/restore, оценить backup-at-rest encryption и внехостовую копию в **отдельном security/DR follow-up**, не вводить сторонний сервис без утверждения.

## 4. План внедрения / rollback

**Stage 0 — read-only:** подтвердить 17 DB inventory, owners, optional stores и contract A/B; оформить решение Architect о multi-DB model; baseline `lsblk`, свободное место, I/O. `Owner GO` для production изменений обязателен.

**Stage 1 — offline:** утилита и тесты в новой Git-ветке/worktree (не править production source). Восстановление из текущего файлового snapshot — reference baseline, но **не** proof нового алгоритма. Проверить SQLite Backup API на тестовых WAL databases с конкурентным writer, crash injection и multi-DB mismatches.

**Stage 2 — shadow на .99:** выполнить online backup в изолированный **новый staging**, не трогая текущий `captiv-backup/latest`; сравнить DB list, counts, integrity, cross-DB references, overhead; применить restore smoke без сети.

**Stage 3 — production activation с Owner GO:** versioned Git release; добавить backup pack в `captiv-backup-system` с gate before publish; одну ежедневную копию проверить независимым QA. Не отключать старый system backup и NPM/Omada backups.

**Rollback:** если новый этап ломает backup, вернуть предыдущий versioned script/config, продолжить прежний `rsync` как **временный аварийный, но НЕ принятый** recovery mechanism, поставить явный `BACKUP_RECOVERY=HOLD`, сохранить последний валидированный new-format snapshot. Никаких автоматических restaurations в живую SQLite; любой production restore — отдельное разрешение и runbook.

## 5. Acceptance и независимый QA

- `PORTAL_SQLITE_BACKUP_CONSISTENCY=PASS`: **17/17** DB есть, проверены по отдельности через SQLite API; SHA-256 + manifest + schema/mode, ни одного скопированного live WAL/SHM. Unknown DB → hard fail.
- `PORTAL_SQLITE_RESTORE_SMOKE=PASS`: изолированная проверка published immutable snapshot, без network egress/production side effects.
- `MULTI_DB_CONSISTENCY=PASS` **либо** `MODEL_DOCUMENTED_AND_ACCEPTED=PASS`: Architect и QA приняли причинные инварианты, допустимые RPO и реакции на mismatch.
- `SETTINGS_AND_SECRETS_RECOVERY=PASS`: безопасное чтение Config/Settings/keys/certs, key provenance/permissions и явная проверка несовместимых ключей.
- `BACKUP_FAILURE_DETECTION=PASS`: inject failures в тесте не публикуют incomplete snapshot и не обновляют last-success; alert сигнализирует о провале/просрочке.
- `PRODUCTION_SERVICE_REGRESSION=NONE`: Portal/Omada/Guest/Auth/Fingerprint/NI продолжают нормально работать, no extra producers / side effects.
- `BACKUP_IO_OVERHEAD=ACCEPTED`: измерено и утверждено по HDD/PSI, не предположено.
- `OLD_SNAPSHOT_RECOVERABILITY=NOT_PROMISED`: файловые copies до нового алгоритма не получают задним числом PASS; 30-day retention и cleanup не удаляют единственный новый validated restore point.

**Вердикт Tech Lead:** `IMPLEMENTATION_TASK=READY_FOR_ARCHITECT_MULTI_DB_DECISION`; `CODER_PRODUCTION=HOLD`; `BACKUP_RECOVERY=HOLD` до evidence и Owner GO.
