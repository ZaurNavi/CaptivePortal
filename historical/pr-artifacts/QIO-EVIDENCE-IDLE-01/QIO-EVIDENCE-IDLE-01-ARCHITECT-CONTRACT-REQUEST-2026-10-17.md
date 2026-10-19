# Chief Architect — QIO-EVIDENCE-IDLE-01 / SQLite startup validation contract

**Scope:** только Fingerprint Evidence, старая LAB VM `192.168.0.202`. Не Network Metadata и не новый `captiv-prod`.  
**Evidence:** `QIO-EVIDENCE-IDLE-01-TECHLEAD-FORENSIC-2026-10-17.md`.

## Установленные факты

- Старый fingerprint Evidence DB: 3,796,074,496 bytes / 926,776 pages; committed ingest watermark 2,834,788.
- A/B/A показал physical HDD read IOPS `2.64 → 56.20 → 3.31` после запуска одной службы и её выключения; API readiness не наступила в первые 90+ секунд.
- Полная startup `_validate_connection`: `PRAGMA quick_check`, schema signature, storage state, два O(N) ingest-sequence guards, inter-table collision join. Runtime `_validate_runtime_connection`: schema/state only.
- Самостоятельная query-only full quick_check за >2 минуты не завершилась; запрос ingest-sequence тоже не уложился в 4 секунды; bounded runtime path — 0.002s.
- Контрольная in-process подмена deep validation на bounded внутри полной `repository.initialize()` дала **3.500 s**, но это **диагностический небезопасный эксперимент**, без HTTP/ingest и без изменений кода, с `proc.write_bytes delta=356,352` от работы SQLite. После проверки watermark/размер DB прежние. Это не implementation GO.
- Indexed min/max `observed_at` показывают около 30-дневного исторического окна, не свидетельствуют о многомесячном просроченном retention backlog. DB остаётся очень большой даже при корректной ограниченной retention-политике.
- Простая замена deep check на bounded check **не сохраняет текущую способность обнаруживать повреждения**.

## Решения, необходимые до implementation GO

**E1. Startup invariant.** Должна ли каждая рестартующая Evidence проходить полный `quick_check` и глобальную проверку последовательностей прежде чем слушать API/принимать ingest? Или допустима точно описанная многоэтапная проверка при иных доказанных гарантиях?

**E2. Fail closed.** Если deep integrity check не завершён по тайм-ауту/отказу HDD, должен ли процесс оставаться полностью `not-ready`/не принимать событий, или разрешён иной безопасный механизм? Запретить restart storm от systemd `Restart=on-failure`.

**E3. Integrity preservation.** Если предлагается перенести часть аудита оффлайн/в фон, как подтверждается неизменность проверенных страниц и доверие к результату после crash/restart, SQLite WAL/checkpoint, файла/генерации и filesystem errors? Нельзя считать `mtime`, singleton watermark или `quick_check(1)` сами по себе достаточным доказательством.

**E4. Guards.** Какие гарантии должны оставаться для нарушения CHECK/type/range, невалидного `ingest_sequence` и collision между Evidence/Source Health? Можно ли алгоритмически заменить линейные scans эквивалентными подтверждёнными инвариантами или нет?

**E5. Bounded disk I/O.** Какой предельный объём сканирования/IO latency допустим при startup, и какие состояния наблюдаемости показывать? Предпочтителен read-only исследовательский тест до изменения runtime поведения.

**E6. Acceptance.** Утвердить LAB corruption-injection matrix, startup readiness contract, WAL durability gates, A/B/A guest+QEMU+physical HDD measurement and rollback criteria. Отдельно учитывать небольшой quiet idle режим без клиентов.

**Запрашиваемый ответ:** однозначный `APPROVE_CONTRACT / HOLD / REJECT` для Evidence-only. Пока нет решения — никакого эксплуатационного патча и никакого изменения нынешнего production.
