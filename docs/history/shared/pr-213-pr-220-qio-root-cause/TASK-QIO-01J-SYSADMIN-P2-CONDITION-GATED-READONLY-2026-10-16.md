# TASK-QIO-01J-SYSADMIN-P2 — Condition-gated full-journal attribution (READ ONLY)

**Заказчик:** Optimization Tech Lead · **Исполнитель:** SysAdmin · **Дата:** 2026-10-16  
**Статус:** `GO_FOR_LOW_PRESSURE_READONLY_ONLY`; `HOLD_ON_HIGH_PRESSURE`; никакого production mutation.

## 1. Зачем

Закрыть нехватку доказательств после P1: root authorized path уже найден, но историческое W1 прочитано частично (195 строк до time limit), W2 не запускалось, при этом у VM высокий PSI. Требуется узнать **полный** список и объём сообщений по producer-ам, не ухудшая гостевую авторизацию/диск. Не искать новые privilege paths; использовать ранее подтверждённое `sudo -n` в текущей авторизованной SSH-сессии. Никакого копирования исходных журналов в чат.

## 2. Допуск по текущему состоянию — строго ПЕРЕД чтением journal

Первым действием только read-only лёгкий preflight: время AZST/UTC, `loadavg`, `/proc/pressure/io`, CPU/memory availability, состояние `captive-portal.service`, `/sys/fs/cgroup/system.slice/systemd-journald.service/io.stat`, `/proc/diskstats` guest `/dev/vda`; по возможности read-only источник host I/O отдельно (только при уже разрешённом host-доступе). Фиксировать 2 коротких снимка минимум с 30-секундным интервалом **без циклов активного ожидания**.

**Консервативные пороги допуска к повторному чтению 4-GiB journald** (это операционный safety gate этого исследования, НЕ SLO приложения): I/O PSI `full avg10` ≤ 5% и `some avg10` ≤ 20% **в обоих** preflight-снимках, без продолжающегося роста нагрузки или тревог Auth/Omada/backlog; при сомнениях — HOLD. Если не достигнуты, не пытаться читать журнал; вернуть только показания и `P2_ADMISSION=HOLD_IO_PRESSURE`. Никаких команд, меняющих приоритет служб или другие процессы.

Если давление остаётся острым / сервисы деградируют — сообщить Owner как о возможном эксплуатационном инциденте; **не** переходить к правкам/рестартам без отдельного Owner GO. Не вызывать повторные тяжёлые сканы за счёт длительного ожидания.

## 3. Однократный ограниченный сбор ПОСЛЕ gate

**Фиксированные окна AZST, полуоткрытые:**
- W1: `[2026-10-16 21:56:00, 21:58:00)`; epoch `[1792173360,1792173480)`.
- W2: `[2026-10-16 21:58:00, 22:00:00)`; следующий contiguous интервал, до 22:00:00 не включительно.

Выполнить агрегирование **на VM**, используя существующий root `journalctl` с фильтрами времени и агрегацию структурированного вывода локальным Python; экспортировать только агрегаты. Использовать `nice -n 19`, `ionice -c3`, ограниченный timeout, без интерактивного pager и без сырого `MESSAGE` в выводе. Сохранить реальное время запуска, предел elapsed, exit/status journalctl и агрегатора **раздельно**, parsed-count и признак true EOF. Не трактовать parsed-count как полный, если хоть один процесс был убит, pipeline завершился неуспешно или EOF не доказан.

**Жёсткий STOP:** любая неуспешная/неполная W1 → W2 не запускать; любая новая высокая PSI, рост гостевой latency, load/pressure spike, проблемы readiness/Omada, I/O timeout → немедленно остановить дальнейшее чтение, сообщить HOLD. Не перезапускать окно повторно в той же сессии и не менять настройки journal для ускорения. Отсутствующее/ротированное историческое окно → `HISTORICAL_WINDOW_UNAVAILABLE`, не заменять тихо другим диапазоном.

Для каждого **полного** окна: сумма записей и UTF-8 байт `MESSAGE`; severity counts; TOP-30 `_SYSTEMD_UNIT`/`SYSLOG_IDENTIFIER` с однократным учётом; top-5 producer шаблоны (category + bounded hash, count, bytes, severity). Дополнительно root/full minus restricted (по сравнению с ранее сохранёнными restricted результатами либо отдельной безопасной статистикой, без лишнего полного чтения); указать метод и ограничения сравнения.

### Минимальные независимые классификации

- Отдельно `captive-portal.service` HTTP-access: **не раскрывать route, IP или идентичности**, не называть auth/CAPPORT no-op без consumer-аудита.
- `fingerprint-evidence.service`: различать `inserted>0`, `inserted=0` + `duplicate_noop>0`, source-health, rejection/error/retention. Отдельно учитывать второе `device_fingerprint_ingest_duplicate`; не считать два события двумя приёмами.
- `snap.microk8s.daemon-kubelite.service`: для повторного hash `b8b298677b2f` и 17 предварительно error-like строк **локально** классифицировать истинность и серьёзность (actual errors, retry loop, информационное сообщение с trigger-word, kube health warning). Возвращать категорию+счёт, без raw body/секретов. Unknown остаётся UNKNOWN.
- `cron`, `rsyslog`, `alloy` и остальные единицы без скрытия системных producer-ов.

## 4. Если полные окна удачно завершены

И только при сохранении низкого I/O давления провести **два** сопоставимых безопасных live 120-секундных наблюдения, с временем начала/конца и одинаковыми счётчиками journald cgroup `252:0`/`253:0` (**не складывать**), guest `/dev/vda`, guest PSI, CPU, число сообщений top producer-ов; при разрешённом host-доступе отдельно QEMU cgroup и physical HDD. Не запускать `strace`, `perf`, `iotop -a`, полное копирование логов или длительное чтение SQLite на production. Если вторая стадия не допущена, не подменять её старыми цифрами.

## 5. Обязательный handoff

Подготовить `QIO-01J-SYSADMIN-P2-ATTRIBUTION-HANDOFF.md` с полями:

```ini
P2_ADMISSION=GO_LOW_PRESSURE | HOLD_IO_PRESSURE
WINDOW_W1_COMPLETE=YES | NO | UNAVAILABLE
WINDOW_W2_COMPLETE=YES | NO | NOT_ATTEMPTED | UNAVAILABLE
JOURNALCTL_EXIT_W1/W2=...
AGGREGATOR_EXIT_W1/W2=...
TRUE_EOF_CONFIRMED_W1/W2=YES | NO
W1/W2_TOTAL_ENTRIES=...
W1/W2_TOP_30_UNITS=...
W1/W2_TOP_5_TEMPLATE_COUNTS_BYTES_SEVERITIES=...
HIDDEN_VS_RESTRICTED=EXACT | LOWER_BOUND | UNKNOWN
MICROK8S_ERROR_LIKE_SEMANTICS=CLASSIFIED | UNKNOWN
MATCHED_GUEST_IO=MEASURED | NOT_MEASURED
MATCHED_HOST_PHYSICAL_IO=MEASURED | NOT_MEASURED
RAW_MESSAGE_EXPORTED=NO
PRODUCTION_MUTATION=NO
ROOT_CAUSE=NOT_CONCLUDED_BY_SYSADMIN
NEXT=TECH_LEAD_REVIEW
```

Приложить обезличенные агрегаты, точную методику (включая исключение правой границы времени), идентификаторы тестового оборудования и status timeout/exit. Не выдавать оценки `IOPS/байты журнала/вклад writer-а` за взаимозаменяемые метрики. SysAdmin отвечает за факты, **не** объявляет suppression безопасным и не даёт Coder GO.

## 6. Запреты

Никакого изменения journald retention/rate limit, `journald.conf`, systemd, `sysctl`, прав пользователей, служб, MicroK8s, SQLite, Grafana/Loki/Alloy; никакого удаления файлов/журналов, рестартов, production-кода, heavy profiling, raw log export, credential/PII leaks. При нарушении safety gate — остановиться и передать HOLD. **Отдельного архитектурного запроса для этого read-only этапа не требуется.**
