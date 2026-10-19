# QIO-EVIDENCE-IDLE-01 — Tech Lead forensic / Evidence-only

**Дата:** 2026-10-17 (Asia/Baku)  
**Объект:** старая лабораторная VM `192.168.0.202`, `fingerprint-evidence.service`; host `omv-hp` / HP ProLiant.  
**Запрет:** новый действующий `captiv-prod` не исследовался и не изменялся. `Network Metadata` в данном этапе не исследуется и не запускается.  
**Результат:** `ROOT_CAUSE_CONFIRMED_FOR_IDLE_STARTUP_READ_PRESSURE`; `SAFE_IMPLEMENTATION=HOLD_PENDING_ARCHITECTURE`.

## 1. Воспроизведённая физическая нагрузка (45-секундные окна)

Состояние сервисов старого CaptivPortal: всё выключено → **запущена только Fingerprint Evidence** → всё снова выключено. Окна гостя и хоста взяты почти одновременно, но начальные секунды не совпадают точно; не следует считать показатели VM и физического диска транзакционно синхронными.

| Метрика | До | Только Evidence | После |
|---|---:|---:|---:|
| Host `/dev/sda` completed **read IOPS** | 2.64 | **56.20** | 3.31 |
| Host `/dev/sda` **write IOPS** | 71.84 | 69.46 | 38.11 |
| Host `/dev/sda` busy | 35.88% | 65.68% | 24.95% |
| Guest `/dev/vda` completed **read IOPS** | 0.04 | **56.17** | 0.07 |
| Guest `/dev/vda` write IOPS | 33.48 | 54.70 | 40.85 |
| Guest `I/O PSI full` (integral over window) | 7.32% | **35.15%** | 8.59% |

Это **диагноз read-pressure**, а не доказательство экономии write IOPS. Результаты HDD включают прочие процессы физического узла; A/B/A причинно связывает скачок чтения с Evidence, но не позволяет присвоить каждую HDD-операцию её PID.

### Сырьё на рабочем компьютере

`C:\CaptivPortal-Lab\handoffs\QIO-EVIDENCE-IDLE-IO-FORENSICS-20261017.zip`

SHA256 архива: `7c7a22f9d5ccfc759df7719d5e33f26c33d61566191bdaa2d65998263e46fe42`.

Внутри — все шесть парных счётчиков `off/evidence/off` host/guest, диагностические сценарии и `SHA256SUMS.txt`. Результаты не являются замерами текущего production.

## 2. Причина стартового чтения

- Старая служба запускается через `/usr/bin/python3 -m app.device_fingerprint.cli run` из source tree `main@810484e69baa371c4696c3b46654199631538fc4` (отдельно от `/opt/CaptivePortal`).
- SQLite-файл `/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3` — **3,796,074,496 bytes**, `page_count=926,776`, `page_size=4096`, durable allocator watermark `2,834,788`.
- `DeviceFingerprintRepository.initialize()` выполняет `DeviceFingerprintRepository._validate_connection()`, содержащую **полную** `PRAGMA quick_check`, проверку подписей схемы/индексов, затем две проверки всех `ingest_sequence` и межтабличное обнаружение совпадающих ingest sequences.
- Последующие две проверки используют сканирование покрывающих индексов (`SCAN ... USING COVERING INDEX uq_df_..._ingest_sequence`); межтабличное сравнение сканирует Evidence и делает поиск по индексу Source Health. Это не bounded/point lookup.
- При запуске **только** `fingerprint-evidence.service` процесс находился в `D` / `wait_on_page_bit_common` и не открыл HTTP-порт `9443` в первые 90+ секунд. Семисекундная `strace` дала **86 `pread64`** к самому `device_fingerprint_evidence.sqlite3` (348,160 bytes возвращённых данных). Всё это без новых клиентов/ингеста.
- Отдельно запущенная на **query-only / mode=ro** базе `PRAGMA quick_check` продолжала ждать диск более 2 минут; ручное завершение диагностического процесса выполнено через `SIGTERM`, полного результата quick_check нет. Поэтому **целостность этой базы не объявляется подтверждённой**.
- Существующая **bounded runtime** проверка `_validate_runtime_connection()` на той же БД завершилась за **0.002 s**, с `proc.read_bytes delta=0`, `proc.write_bytes delta=0`. Она НЕ эквивалентна full startup validation.
- Отдельная `ingest_sequence`-проверка с прерыванием через 4 s завершилась `OperationalError: interrupted` через **4.079 s**, пройдя ориентировочно **433,000 SQLite VM steps**, вызвав `proc.read_bytes delta=753,664`, `proc.write_bytes delta=0`. Значит, обход только quick_check не гарантирует быстрого полного старта.
- **Дополнительный контрольный LAB:** отдельный Python-процесс, без HTTP и без приёма ingest, вызвал настоящую `DeviceFingerprintRepository.initialize()` с *временной in-process подменой* только глубокой стартовой валидации на существующую `_validate_runtime_connection()`. Инициализация прошла за **3.500 s**, `proc.read_bytes delta=16,384`, `proc.write_bytes delta=356,352`. Это **намеренно неполная/небезопасная проверка только для диагностики**, не разрешённая эксплуатационная оптимизация. На SQLite возникли служебные записи при открытии/закрытии; опыт **не считается read-only** в смысле байтов диска. Никакого изменения Python-файлов не было.
- После опыта сверено: служба `inactive`, `MainPID=0`, `disabled`; `git status --porcelain` пустой; Evidence DB **3,796,074,496 bytes**, `last_ingest_sequence=2,834,788`, journal mode WAL.
- **Индексная проверка retention без полного сканирования:** первые/последние `observed_at` у Evidence: `2026-09-17T06:27:16.976Z` / `2026-10-16T18:49:07.216Z`; у Source Health: `2026-09-17T06:20:35.262Z` / `2026-10-17T06:31:12.231Z`. Период хранения примерно один месяц; **нет подтверждения гигантской просроченной очереди**, требующей немедленного полного VACUUM. `freelist_count=6,194` из 926,776 страниц. Ни `DELETE`, ни `VACUUM` не выполнялись.

## 3. Почему нельзя просто заменить quick_check на runtime-check

`PRAGMA quick_check` может выявлять физические/структурные и `CHECK`-нарушения в SQLite, которые не видны через bounded проверку схемы, `user_version` и singleton. На отдельной синтетической SQLite-базе с нарушенным `CHECK` подтверждено `PRAGMA quick_check -> CHECK constraint failed in example`. Это ограничение безопасности, не вопрос производительности.

**Без архитектурного решения запрещено:** заменять `_validate_connection()` на `_validate_runtime_connection()` при записи/приёме событий, автоматически «предоверять» большую базу после незавершённого скана, менять durability, отключать другие защитные проверки или предлагать перенос на SSD как решение архитектурной причины.

## 4. Текущий вердикт и следующий шаг

**Доказано:** один лишь старт Fingerprint Evidence способен поднять физический read IOPS примерно с 3 до 56; дорогое чтение сопровождает стартовую глубокую проверку крупной базы. **Не доказано:** что только `quick_check` ответственна за все длительные чтения; показаны дополнительные линейные guard-сканы. **Не доказано:** полноценная безопасная версия с ускоренным startup. Диагностическая ускоренная инициализация 3.500 s **не сохраняет** полную deep-integrity гарантию и не является candidate для PR.

1. Получить архитектурный контракт об обязательном уровне полной проверки на *каждом* старте, допустимости bounded-time и offline/attested validation, fail-closed semantics, частоте full audit, crash/data-corruption fallback.
2. После этого заказать **Evidence-only** Coder LAB implementation, синтетические corruption/failure тесты, независимые cross-layer A/B/A на старой VM, readiness, WAL и fidelity gates.
3. До архитектурного решения `EVIDENCE_IMPLEMENTATION=HOLD`, `NETWORK_METADATA=HOLD`, `CURRENT_PRODUCTION=NO_TOUCH`.

## 5. Проверка завершения

На 2026-10-17 15:23:36 AZST: `fingerprint-evidence.service: inactive, MainPID=0, disabled`; `git status --porcelain` в deployment tree пустой; разовый диагностический Python завершён; база сохраняет прежний размер. Текущая `I/O PSI full avg10=6.09%` после завершения проверки. Никакой PR, merge, deploy, restart production не выполнялись.
