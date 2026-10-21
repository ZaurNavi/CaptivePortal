## Linux PERF Lab / WSL2 — новый лабораторный инструмент CaptivPortal

**Статус:** ACTIVE / LAB ONLY  
**Добавлен:** 2026-08-30  
**Назначение:** production-compatible Linux testing, performance/capacity gates и проверка exact candidate tree до Git publication и production deployment.

### Среда

На рабочем Windows-хосте создана отдельная Linux Lab-среда:

- Distribution: Ubuntu 22.04.5 LTS
- Platform: WSL2
- Kernel: `6.18.33.2-microsoft-standard-WSL2`
- Architecture: x86_64
- glibc: 2.35
- Python: 3.10.12
- SQLite: 3.37.2
- Linux user: `zaur_navi`

Это не production-сервер и не замена production VM `192.168.0.202`.

Технически среда работает под WSL2, поэтому в документации её следует называть **Linux PERF Lab / WSL2 Lab**, а не полноценной отдельной hardware/Hyper-V VM.

### Основной каталог

```text
/home/zaur_navi/captivportal-lab
```

Все benchmark-sensitive файлы расположены внутри Linux filesystem (`/home/...`), а не в `/mnt/c`, чтобы Windows filesystem layer не влиял на I/O PERF.

### Python PERF environment

Отдельное virtual environment:

```text
/home/zaur_navi/captivportal-lab/perf-venv
```

Зафиксированный runtime:

```text
Python 3.10.12
SQLite 3.37.2

Flask 3.1.2
Werkzeug 3.1.3
Jinja2 3.1.6
MarkupSafe 3.0.3
click 8.3.1
itsdangerous 2.2.0
blinker 1.9.0
requests 2.34.2
urllib3 1.26.5
certifi 2026.7.22
idna 3.3
charset-normalizer 3.4.9
```

Для TRAFFIC-04 PERF `tzdata` и `pytest` в PERF venv специально не устанавливались.

### Связь с Windows Central Lab

Windows Central Lab остаётся отдельной канонической лабораторией:

```text
C:\CaptivPortal-Lab
```

Linux PERF Lab используется как дополнительный Linux/production-compatible gate там, где FINAL TASK требует Linux PERF, capacity или другого Linux-specific acceptance.

Типовой процесс:

```text
Coder patch
    ↓
Windows Central Lab
    ↓
exact candidate tree
    ↓
Linux PERF Lab
    ↓
mandatory PERF / Linux gate
    ↓
Controlled Browser Acceptance
    ↓
ALL mandatory gates PASS
    ↓
Git publication
    ↓
merge
    ↓
production deployment FROM GIT
```

Linux Lab не является источником production deployment.

### Exact candidate materialization

Для pre-publication testing допускается локальный `LAB ONLY` Git commit.

Он:

- используется только для immutable candidate identity;
- не push'ится;
- не является publication commit;
- не является production identity;
- может иметь другой commit SHA, если exact Git tree совпадает с candidate tree.

Для TRAFFIC-04 был использован следующий baseline:

```text
commit:
e1a278c3e2c131b0762d7134485dcf3208eac11e

tree:
a529faae4ded9e3f6c5cb72c5a9c6d9cfcc9df3e
```

TRAFFIC-04 patch:

```text
C:\CaptivPortal-Lab\TASK-TRAFFIC-04-Peak.patch

SHA256:
493c0e8b1ff1f48dc718eea15264cf0d08ab17e1d25560747871f1c23edaa002
```

После применения patch поверх exact baseline был независимо получен expected candidate tree:

```text
c1a50ff84b7c5719665fe105ededa0454a1aaf94
```

Linux LAB ONLY commit для этого tree:

```text
5891ce6b1b53fbc9e75f5fc937dd4242ac20420e
```

Commit SHA является локальным Lab metadata. Каноническая candidate content identity для этого gate — Git tree.

### B / C-P worktrees

Для сравнительного PERF созданы независимые clean worktrees:

```text
/home/zaur_navi/captivportal-lab/repo/worktrees/B
/home/zaur_navi/captivportal-lab/repo/worktrees/C
```

Где:

```text
B
= approved baseline

C
= exact candidate, Peak functionality не запрашивается

P
= тот же exact candidate tree, Peak functionality запрашивается
```

C и P не являются разными source trees.

### Production-size Observation snapshot

Для PERF используется отдельный immutable production-size snapshot:

```text
/home/zaur_navi/captivportal-lab/perf/observations-production-20260830.sqlite3
```

Identity:

```text
bytes:
261754880

SHA256:
5da87e99e115f2de311f3a0d026ae00849cd2c399e3097b96d2f384c277f3710

permissions:
444 / read-only

SQLite:
3.37.2

PRAGMA user_version:
1

integrity_check:
ok
```

Snapshot содержит production Observation facts, но используется только как immutable read-only Lab input.

Для всех сравнительных B/C/P измерений используется один и тот же snapshot.

### Snapshot coverage на момент создания

Site:

```text
6a64f17630da7c70d232187a
```

Eligible completed successful `ap_dynamic` cycles:

```text
44246
```

Coverage:

```text
first_started_at:
2026-08-13T17:36:29.420Z

last_finished_at:
2026-08-30T15:47:30.722Z
```

### Fixed TRAFFIC-04 PERF evaluation identity

Для TRAFFIC-04 зафиксировано:

```text
evaluated_at_utc:
2026-08-30T15:47:30.722Z
```

24h:

```text
[from,to):
2026-08-29T15:47:30.722Z
→
2026-08-30T15:47:30.722Z

bucket:
300 s

bucket_count:
288
```

7d:

```text
[from,to):
2026-08-23T15:47:30.722Z
→
2026-08-30T15:47:30.722Z

bucket:
900 s

bucket_count:
672
```

Фиксированные параметры хранятся в:

```text
/home/zaur_navi/captivportal-lab/perf/traffic04-evaluation.env
```

### PERF evidence

TRAFFIC-04 стал первым TASK, для которого новая Linux PERF Lab была использована для полноценного production-size comparative gate.

Методика:

```text
B24 / C24 / P24
B7  / C7  / P7

minimum:
10 measured successful runs per variant
60 measured runs total

ordering:
B → C → P
P → C → B
interleaved
```

До measured runs выполнялся одинаковый unmeasured warm-up каждого варианта.

После PERF повторно проверялись:

- baseline tree;
- candidate tree;
- clean worktree state;
- snapshot SHA256;
- snapshot byte size.

### Первый зафиксированный PERF result

TRAFFIC-04 candidate:

```text
tree:
c1a50ff84b7c5719665fe105ededa0454a1aaf94
```

получил:

```text
Functional gates:
PASS

Semantic base identity:
PASS

C24 vs B24:
PASS

C7 vs B7:
PASS

P24 vs C24:
PASS

P7 vs C7:
FAIL

Post-PERF tree/snapshot identity:
PASS
```

Причина blocking failure — Peak-specific 7d relative overhead превысил допустимые relative PERF thresholds, несмотря на прохождение hard absolute limits.

Поэтому candidate не был принят для Git publication.

Это подтверждает назначение Linux PERF Lab: mandatory Linux/PERF gate реально способен остановить publication до Git и production.

Evidence:

```text
/home/zaur_navi/captivportal-lab/perf/results/traffic04-perf-20260830T163917Z.json

/home/zaur_navi/captivportal-lab/perf/results/traffic04-perf-20260830T163917Z.csv
```

### Governance

Linux PERF Lab должна рассматриваться как часть controlled Central Lab workflow.

Основные правила:

1. Production `192.168.0.202` не используется вместо Linux Lab для mandatory pre-publication PERF.
2. Production-size snapshot переносится в Lab и после переноса становится immutable/read-only.
3. Candidate должен иметь зафиксированный exact Git tree.
4. Tree и snapshot identity проверяются непосредственно до и после PERF.
5. Сравниваемые варианты используют одинаковый snapshot, Site, `[from,to)` и `evaluated_at_utc`.
6. PERF failure не разрешается обходить увеличением timeout/deadline, ослаблением thresholds или скрытым изменением architecture.
7. Candidate после mandatory gate FAIL не публикуется в обычный Git/GitHub workflow.
8. После remediation новый candidate tree считается новым artifact и проходит необходимые affected gates повторно.
9. Git publication выполняется только после полного mandatory acceptance.
10. Production application code по нормальному workflow поступает только FROM GIT.

### Current state

На 2026-08-30 Linux PERF Lab:

```text
environment:
READY

production-size immutable snapshot:
READY

exact B/C candidate worktrees:
READY

production-compatible Python runtime:
READY

comparative PERF runner:
AVAILABLE

first production-size PERF execution:
COMPLETED

TRAFFIC-04 tested candidate:
PERF FAIL / NOT ACCEPTED
```

Linux PERF Lab следует включить в project inventory, testing/governance documentation и будущие TASK FINAL, когда для изменения требуется Linux-specific, production-size, PERF или capacity acceptance.