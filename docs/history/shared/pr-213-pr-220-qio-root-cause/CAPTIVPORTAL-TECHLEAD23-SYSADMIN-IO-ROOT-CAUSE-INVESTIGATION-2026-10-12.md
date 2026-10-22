# CaptivPortal — Incident Report + SysAdmin Investigation Directive

**Предлагаемый Task ID:** `TASK-INFRA-IO-01`  
**Инициатор:** Owner / CaptivPortal Tech Lead  
**Дата:** 2026-10-12  
**Тип:** Root-cause investigation / корреляционная диагностика хранилища  
**Режим:** READ-ONLY / NO MUTATIONS  
**Исполнитель:** SysAdmin  
**Приоритет:** высокий для качества Network Intelligence; авария пользовательского портала НЕ подтверждена  
**Coder:** HOLD; **deploy / restart / migrations / tuning:** NO

## 1. Назначение

Установить, **какие именно источники и процессы** создают дисковую нагрузку, приводящую к высокой задержке I/O в виртуальной машине CaptivPortal, и на каком уровне находится узкое место: **(а)** приложение/SQLite внутри guest, **(б)** гипервизор/конкурирующие ВМ, **(в)** физическое хранилище/RAID/контроллер, **(г)** комбинация причин. Не объявлять виновника заранее. В частности, VM-диск `vda` не тождествен автоматически конкретному физическому диску HP ProLiant.

Требуется не общая рекомендация «добавить SSD», а доказанный список **TOP N фактических источников I/O** с количественным вкладом, путём до физического диска и оценкой степени уверенности.

## 2. Строгий scope / топология

**Исследуемый production:** VM `192.168.0.202` (`/opt/CaptivePortal`), текущий Git HEAD `88541da8d6952cb91fc945b7f77efcf7e5c46420`, tree `d879f5113319c334faf2bf9ae7b8bea7cfdc977e`; guest Linux, виртуальный блочный диск `vda`, guest root `/dev/mapper/ubuntu--vg-ubuntu--lv`. На физическом уровне — основной сервер семейства **HP ProLiant DL180 Gen6** согласно инвентарю проекта (верифицировать фактический host, гипервизор и диски).

**Очень важно:** `captiv-prod` `192.168.0.99` — **отдельный будущий физический узел** и **НЕ** рассматриваемая production VM. Не спутать два хоста.

SysAdmin должен установить реальное отображение:

`guest /dev/vda → virtual disk/volume → VM datastore/storage pool → host device/RAID logical volume → physical drive(s)`.

Отдельно установить другие ВМ, гостевые сервисы и фоновые задачи, которые используют **тот же самый физический I/O path** (включая host OS, если размещена там же). Гипервизор, RAID и устройство не предполагать по памяти — подтвердить командами/инвентарём.

## 3. Непосредственные факты Tech Lead (production, 2026-10-12)

| Контроль | Наблюдение |
|---|---|
| Функциональность портала | `captive-portal.service`, Nginx, Edge Bridge, Fingerprint Suricata, `network-metadata.service`, `network-metadata-projection.service` — `active`. Публичная страница и Admin Login HTTP 200. |
| NI-03 / Device Card | Реальный bounded read-service на одном авторитетно привязанном устройстве — PASS; данные `stale`, недавних протоколов 0. |
| NI-04 | Включён в production; 55 taxonomy Service IDs, **53 active exact-SNI rules** (Messenger/Viber исключены). На одном существующем устройстве периодически `ServiceDeadline`. |
| Локализация NI-04 | В проблемном измерении NI-02B snapshot = **0,024 с**, NI-01 evidence read = **5,075 с**, итог `ServiceDeadline` (бюджет 5 с). Позднее при нулевом наборе фактов NI-04 PASS за **0,009 с**, recent services = 0. Это указывает на интермиттирующую медленную исходную операцию, но ещё не доказывает root cause. |
| Задержка ingest | `event_at=2026-10-12T14:35:35.940240Z`, `ingested_at=2026-10-12T15:07:08.750542Z` — **около 31 мин 33 с**. NI-01 получает/пишет события, но значительно позднее их возникновения. |
| Диск guest | **Один** `iostat -dx 1 2` interval: `vda %util≈98,8%`; примерно 73 read/s, 77 write/s, `r_await≈28,2 ms`, `w_await≈31,4 ms`, `aqu-sz≈4,6`. Это **не среднее** и **не измерение физического HDD**. |
| Guest system | `load average` около **9–10** во время диагностики; `vmstat` показывал заметный `wa` в отдельных интервалах. RAM: ~7,9 GB всего, ~5,4 GB available в одном замере. Файловая система guest ~41% заполнена, свободно ~92 GB — переполнения не наблюдалось. |
| Базы | `network_metadata.sqlite3` ~**2,85 GB**, `network_metadata_projection.sqlite3` ~**0,99 GB**, WAL существуют и обновляются. Размер сам по себе не означает ошибки или избыточной нагрузки. |
| Health | NI-01 `capture_health` менялся `usable`↔`unavailable` при `metadata_output_health=usable`, `metadata_ingest_health=usable`; NI-02B наблюдался `registry_degraded` и `usable`, source polling продолжался, `pending_attribution_count=0`. Не утверждать, что эти состояния вызваны диском, без отдельного доказательства. |
| Приложение | Git worktree CLEAN. Изменений production в ходе диагностики не производилось. |

**Границы доказанного:** нет измерений дисков физического HP ProLiant, нет разбиения I/O по другим ВМ, нет ranking процессов по read/write IOPS и bandwidth. Поэтому **виновник НЕ установлен**. Не считать доказанным баг портала, отсутствие бага, поломку HDD, вину RAID или конкурирующую ВМ.

## 4. SysAdmin investigation plan (только пассивная диагностика)

### A. Привязка VM → физическое хранилище

1. Подтвердить реальную модель/ОС физического HP ProLiant, вид гипервизора и имя исследуемой VM; зафиксировать виртуальный диск `vda`, controller, datastore/storage pool, guest volume и host block device, RAID/controller/HDD slots.
2. Установить, используют ли **guest OS `192.168.0.202`, host OS и другие ВМ** тот же физический диск/RAID-group. Составить таблицу «VM/host workload → vDisk → storage pool → physical spindle/group».
3. Проверить в read-only режиме состояние storage/RAID/SMART, ошибки SATA/SAS/HBA, media/timeout/retry, деградацию массива, read/write cache, cache battery/BBU, thin provisioning и свободное место, **если применимо**. Если какой-то слой недоступен — `UNKNOWN` и требуемый доступ, не фантазировать.

### B. Внутри CaptivPortal VM `192.168.0.202`

1. В согласованных по UTC интервалах собрать `iostat` с устройством `vda` и LVM, `%util`, r/s, w/s, rkB/s, wkB/s, `r_await`, `w_await`, avgqu-sz/aqu-sz, `vmstat` (`wa`, `st`, swap/reclaim), load, CPU, память.
2. Собрать **TOP процессов и потоков** по фактическому block I/O: PID, process/command/service, read/write IOPS либо операции, read/write kB/s, cumulative bytes/delta и duration; различать logical syscall write и действительно совершённый disk write. Инструменты по доступности: `pidstat -d`, `iotop`, `/proc/PID/io`, systemd/cgroup, `iostat`, `sar` (если уже доступен). Не устанавливать пакеты и не включать новые агенты без одобрения.
3. Сопоставить I/O с `network-metadata.service` (NI-01), `network-metadata-projection.service` (NI-02B), `captive-portal.service` (включая NI-03/NI-04 query), Suricata/Fingerprint, journald, прочими process/service. Учесть SQLite WAL, checkpoint, journaling, retention/cleanup и конкурирующие задачи. **Не выполнять** `VACUUM`, `REINDEX`, ручной WAL checkpoint, изменение PRAGMA, удаление/перенос DB.
4. Определить, какие типы обращений создают нагрузку: частые мелкие sync/random writes, read amplification, fsync, heavy scans, checkpoint stalls, swap, filesystem errors, CPU steal / scheduling. Если замеры не позволяют причинно связать операцию с задержкой — явно отметить.

### C. На гипервизоре и физическом HP ProLiant

1. Снять **неагрегированный** host block I/O по реальному RAID logical disk / device (latency, IOPS, KB/s, queue depth, busy / saturation) и на уровне hypervisor VM vDisk I/O за те же UTC интервалы. Проверить наличие host I/O throttling, ballooning/swap/CPU contention/steal, если гипервизор это поддерживает.
2. Построить рейтинг **всех ВМ и host processes/services** по их реальным чтениям/записям на разделяемом storage path. Для QEMU/KVM указать VM identity за гипервизорным `qemu` process, а не оставить только процесс `qemu-system-*`; для VMware/других использовать штатные host/hypervisor counters. Возможные соседи (например Omada/PRTG/другие VM) — проверить фактически, не назначать виновными по перечню.
3. Проверить scheduled jobs/backup/snapshot/scrub/RAID rebuild/media scans, host logs и конкурентный I/O других VM. Сравнить guest-visible latency vs host datastore latency vs physical device latency. Ищем не только **кто пишет**, но и **почему накопитель не успевает**.

### D. Корреляция и доказательная база

- Минимум **два режима**: обычная естественная нагрузка и эпизод реально высокой задержки; если возможно, тихий базовый интервал для сравнения. Никакого искусственного стресс-теста. Каждый интервал: UTC начало/конец, длительность, узел, физический device, активные VM, выборки 1–5 s в течение 3–5 min либо более безопасный пассивный режим.
- Не делать вывод по **одному** `top`, `iostat`, `%util` или одному PID snapshot; проверить повторяемость.
- Для всех измерений обеспечить одни и те же UTC временные окна гостевой ВМ, hypervisor и host. Фиксировать разные единицы (`IOPS`, `KiB/s`, bytes, `ms`, `%util`) и учитывать page cache, scheduler и sampling limitations.
- Сопоставить пики дисковой задержки с задержкой `event_at → ingested_at` NI-01, `last_projection_commit_at` NI-02B, `capture_health`, `registry_degraded` и ошибками/временем чтения NI-04. Причина подтверждена только если временная связь, топология и источники нагрузки согласуются между собой.
- Логи/скриншоты из host management не должны содержать пароли, секреты, токены, MAC, IP посетителей, сырые SNI или содержимое пакетов. `sudo` используется SysAdmin только в разрешённом read-only режиме.

## 5. Обязательный итог — один FINAL ROOT CAUSE REPORT

Вернуть **не предположение, а факты и количественные результаты**:

```
TASK = TASK-INFRA-IO-01
INVESTIGATION = READ_ONLY
UTC_WINDOWS = ...
PRODUCTION_VM = 192.168.0.202
HYPERVISOR_TYPE_AND_HOST = ... / UNKNOWN
VM_VDA_TO_PHYSICAL_DISK_MAPPING = ... / UNKNOWN
PHYSICAL_DISK_RAID_HEALTH = ... / UNKNOWN
GUEST_IO_PEAK_AND_BASELINE = ...
HOST_IO_PEAK_AND_BASELINE = ...
GUEST_CPU_IOWAIT_STEAL_AND_MEMORY = ...
SOURCE_NI01_LAG = ...
PROJECTION_NI02B_LAG = ...
NI04_READ_LATENCY = ...
TOP_GUEST_IO_PROCESSES = ranked table + read/write IOPS, KiB/s, duration
TOP_HOST_IO_PROCESSES_OR_VMS = ranked table + real storage path, read/write IOPS, KiB/s, duration
OTHER_COLOCATED_VM_IO_CONTRIBUTION = measured % / UNKNOWN
CAPTIVPORTAL_VM_IO_CONTRIBUTION = measured % / UNKNOWN
SOURCE_OF_CONTENDED_IO = APP / OTHER_VMS / HOST / SHARED / STORAGE_LIMIT / MIXED / UNKNOWN
CORRELATED_LATENCY_EVIDENCE = timestamps + counters
STORAGE_DEVICE_OR_RAID_FAULTS = ... / NONE_OBSERVED / UNKNOWN
ROOT_CAUSE_STATUS = PROVEN / PARTIALLY_PROVEN / UNKNOWN
ROOT_CAUSE_DETAILS = ...
OPEN_GAPS = ...
PRODUCTION_CHANGES = NONE
RECOMMENDATIONS_ONLY = ordered options, expected effect, risk, separate approval required
```

**Особое требование:** вернуть **ТОП-1/ТОП-3/ТОП-10** по фактически измеренным потребителям, насколько это позволяют средства учёта; с разделением **гостевых процессов** и **физических потребителей всего host**. Не выдавать процессы, которые нельзя связать с storage path, за виновников. Если точное процентное распределение технически недоступно — `UNKNOWN`, объяснить причину и предложить контролируемый способ получить доказательство.

**Критерий завершения:** понятно, какое устройство/очередь тормозит, какие ВМ и процессы на него дают нагрузку, каковы их количественные вклады, а какие причинные связи остались неподтверждёнными. Отдельно — 2–3 варианта дальнейшего решения (например перераспределить хранилище, вынести VM/БД, корректировать cadence/query после отдельного code review, устранить аппаратный дефект при наличии доказательств), **не применяя** ни один из них.

## 6. Safety / authority boundary

**Запрещено без нового Owner approval:** перезапуски сервисов/ВМ/host; изменения конфигурации VMware/KVM/Hyper-V/storage/RAID/BIOS, sysctl, I/O scheduler, cpuset, limits; установка пакетов/агентов; создание VM snapshots; live migration; любые SQL-writing operations, SQLite cleanup/checkpoint/VACUUM; остановка NI-01/NI-02B; изменение retention или feature flags; нагрузочные тесты. Не предпринимать «оптимизацию по ходу».

В случае аппаратных ошибок, угрозы данным или отказа гостевого портала немедленно отметить severity и вернуть Owner/Tech Lead диагностический результат и запрос отдельного плана, а не выполнять рискованную мутацию.

**Owner decision gate:** после FINAL REPORT Tech Lead готовит из доказанной причины отдельное решение на remediation, отдельный план безопасного исполнения с backup/rollback и только затем Owner санкционирует action.
