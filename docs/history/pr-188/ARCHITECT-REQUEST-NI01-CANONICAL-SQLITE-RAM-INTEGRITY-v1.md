# ARCHITECT REQUEST — CAPTIVPORTAL
# TASK-DTI-NI-01-DB-VALIDATION-OPT-01
## Canonical SQLite Online Backup → `:memory:` Deep Integrity Validation
### Request for Architecture Contract / Implementation-Ready Decision

**Project:** CaptivPortal  
**Target subsystem:** DTI-NI-01 / Metadata-Only Network Observation Foundation  
**Target service:** `network-metadata.service`  
**Target database:** `/opt/CaptivePortal/data/network_metadata.sqlite3`  
**Current observed DB size:** approximately **4.3 GiB** on production VM `192.168.0.202` at the latest read-only inspection  
**Request owner:** Owner  
**Requested recipient:** CaptivPortal Chief Architect  
**Requested output:** Architecture Contract / Implementation-Ready Decision for Tech Lead  
**Coder:** HOLD  
**Production mutation:** NO  
**Initial execution scope:** Lab / controlled experiment only  
**Production deployment:** separate Tech Lead review + separate Owner GO

---

# 0. Executive request

We have a concrete operational problem: deep SQLite integrity validation of the large NI-01 database creates a very long startup/readiness path and severe HDD read pressure.

Owner does **not** want a custom or experimental database-copy mechanism invented inside CaptivPortal.

The requested design direction is deliberately restricted to an already documented, canonical SQLite mechanism:

```text
LIVE SQLite DB
    ↓
SQLite Online Backup API
    ↓
SQLite in-memory destination (`:memory:`)
    ↓
PRAGMA integrity_check
    +
PRAGMA foreign_key_check where applicable
    ↓
health result
```

The purpose of this request is for Architect to define **how CaptivPortal safely integrates this canonical mechanism into NI-01 lifecycle**, especially:

```text
startup admission
deep-check scheduling
RAM/resource admission
failure semantics
writer coexistence
health state
rollback
QA/PERF gates
```

Architect should NOT invent a new database-copy format, raw-file copier, custom page walker, or alternative integrity algorithm unless official SQLite behavior is proven insufficient and Owner explicitly reopens the design.

---

# 1. Current project facts

## 1.1 NI-01 store ownership

The NI-01 architecture defines:

```text
logical owner:
Network Metadata Foundation

physical store:
SQLite

canonical path:
/opt/CaptivePortal/data/network_metadata.sqlite3
```

NI-01 is a distinct Network Observation Store.

The existing architecture also freezes:

```text
journal_mode = WAL
foreign_keys = ON
synchronous = FULL
bounded busy timeout
one logical writer
```

and:

```text
network-metadata.service
```

owns the NI-01 write path.

These durability/ownership rules are protected by this request.

---

## 1.2 Current production observation

Latest read-only inspection on the CaptivPortal production VM:

```text
host/IP:
192.168.0.202

database:
/opt/CaptivePortal/data/network_metadata.sqlite3

current observed size:
~4.3 GiB
```

The size is dynamic and MUST NOT become a hardcoded implementation constant.

The same VM currently had approximately:

```text
RAM total:      ~7.7 GiB
RAM available:  ~5.6 GiB
Swap total:     ~4.0 GiB
Swap used:      ~110 MiB
Python:         3.10.12
```

Owner states the HP ProLiant hypervisor has substantial unused RAM and is willing to increase VM RAM for the controlled experiment, likely by roughly 10–12 GiB, subject to SysAdmin verification.

RAM expansion is an **operational Lab prerequisite**, not a permanent semantic requirement of NI-01.

---

# 2. Problem statement

Current failure mode conceptually:

```text
network-metadata.service start
        ↓
deep/full SQLite validation
        ↓
large multi-GiB DB traversal
        ↓
many physical reads on mechanical HDD
        ↓
high seek / await / I/O pressure
        ↓
very long startup/readiness
```

Owner reports startup/integrity validation can become unacceptably long under the current disk conditions.

The desired architecture must preserve integrity assurance while avoiding:

```text
every ordinary service start
        =
whole multi-GiB deep validation directly on HDD
```

The problem is specifically a **cold-start / readiness / physical-I/O problem**.

It must not be "solved" by:

```text
disabling integrity verification permanently
weakening SQLite durability
disabling fsync
changing synchronous=FULL
changing WAL
ignoring corruption
moving to SSD merely to hide the architecture issue
```

---

# 3. Canonical external mechanism — authoritative technical basis

This section is intentionally included so Architect and Tech Lead do not have to invent the mechanism.

The following are external technical sources from SQLite and Python documentation.

## 3.1 SQLite Online Backup API — official SQLite documentation

**Primary source:**

https://www.sqlite.org/backup.html

Relevant sections:

```text
1. Using the SQLite Online Backup API
2. Example 1: Loading and Saving In-Memory Databases
2.1 Error handling
2.2 Possible Enhancements
3. Example 2: Online Backup of a Running Database
3.1 File and Database Connection Locking
3.2 backup_remaining() and backup_pagecount()
```

What this official SQLite document establishes:

1. The Online Backup API is specifically designed to copy the contents of a live SQLite database into another SQLite database.
2. It supports copying **to or from an in-memory database**.
3. The copy can be performed incrementally.
4. When incremental backup is used, the source does not have to remain locked for the full duration; the source is read/locked during backup steps.
5. Other users may continue using the source database between steps.
6. On successful completion, the destination is a consistent SQLite snapshot/copy of the source.
7. SQLite documents busy/locking behavior and recommends normal SQLite busy handling/timeout where needed.
8. SQLite explicitly documents a page-size caveat for an **in-memory destination**.
9. SQLite documents that writes by other connections/processes during incremental backup can cause the backup to restart work; sufficiently frequent writes can theoretically prevent completion.

This is the canonical copy mechanism requested for this task.

---

## 3.2 Python `sqlite3.Connection.backup()` — official Python documentation

**Primary source:**

https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup

The Python standard-library API exposes SQLite Online Backup directly:

```text
Connection.backup(
    target,
    *,
    pages=-1,
    progress=None,
    name="main",
    sleep=0.250
)
```

Official Python documentation states that the backup works even when the source database is accessed by other clients.

It also contains an explicit example of copying a file-backed SQLite database into an in-memory SQLite database.

Canonical reference pattern:

```python
import sqlite3

src = sqlite3.connect("example.db")
dst = sqlite3.connect(":memory:")

src.backup(dst)

dst.close()
src.close()
```

This is NOT a CaptivPortal invention.

For CaptivPortal, the final code must be adapted to project safety, error handling, monitoring and resource limits by Tech Lead/Coder after architecture freeze.

---

## 3.3 SQLite `PRAGMA integrity_check` — official SQLite documentation

**Primary source:**

https://www.sqlite.org/pragma.html#pragma_integrity_check

SQLite documents `PRAGMA integrity_check` as a low-level database formatting and consistency check.

It checks classes of problems including:

```text
table/index ordering problems
misformatted records
missing pages
missing/surplus index entries
constraint errors handled by integrity_check
freelist integrity
pages used more than once or not at all
```

Success semantics:

```text
one row:
ok
```

Important:

```text
PRAGMA integrity_check
DOES NOT check foreign-key violations.
```

Therefore, if NI-01 architecture requires FK consistency validation, it is a separate check.

---

## 3.4 SQLite `PRAGMA foreign_key_check`

**Primary source:**

https://www.sqlite.org/pragma.html#pragma_foreign_key_check

This PRAGMA checks foreign-key violations and returns rows for violations.

Therefore a full NI-01 deep-validation policy may require:

```text
PRAGMA integrity_check
AND
PRAGMA foreign_key_check
```

Architect must freeze whether both are mandatory for NI-01 deep validation.

---

## 3.5 SQLite `PRAGMA quick_check`

**Primary source:**

https://www.sqlite.org/pragma.html#pragma_quick_check

SQLite documents `quick_check` as a faster integrity check that skips some work done by `integrity_check`, notably UNIQUE checking and full index-content/table-content consistency checking.

SQLite documentation explicitly describes:

```text
quick_check       O(N)
integrity_check   O(N log N)
```

This source is important for Architect because:

```text
quick_check is faster
```

does NOT automatically mean:

```text
quick_check is constant-time / size-independent / cheap enough for every startup
```

For a multi-GiB database, Architect must not call a whole-database `quick_check` "bounded startup validation" without measured and accepted evidence.

---

## 3.6 Direct SQLite project confirmation: integrity_check on Backup API output

Supporting source from the official SQLite forum:

https://sqlite.org/forum/info/3dd8dad9f82e457501176c1a2ac158640a0c90a090a8db320a425dbba9515f5d?t=c

In that discussion Richard Hipp, SQLite's principal author, confirms that:

```text
PRAGMA integrity_check
```

is valid on a database produced by the SQLite Backup API and should behave as it does on the source database.

This is supporting confirmation of the intended:

```text
Backup API
    ↓
destination SQLite DB
    ↓
integrity_check
```

sequence.

The normative mechanism remains the SQLite Backup API + PRAGMA documentation above.

---

# 4. Requested architecture direction

Architect is asked to design around this exact direction:

```text
                 NI-01 START
                     │
                     ↓
          FAST / BOUNDED STARTUP GATE
                     │
               ┌─────┴─────┐
               │           │
             PASS        FAIL
               │           │
               ↓           ↓
       normal NI-01      fail/degrade
       operation         per contract
               │
               ↓
      scheduled / triggered
          DEEP VALIDATION
               │
               ↓
      SQLite Online Backup API
               │
               ↓
       SQLite `:memory:` DB
               │
               ↓
      PRAGMA integrity_check
               │
               ├───────────────┐
               ↓               ↓
   PRAGMA foreign_key_check   execution/resource failure
     if architect requires
               │
               ↓
        health PASS/FAIL
               │
               ↓
       close memory DB
```

The deep validator MUST NOT use:

```text
cp live.sqlite3
cp live.sqlite3-wal
filesystem copy pretending to be a SQLite snapshot
custom binary copier
custom B-tree/page validator
```

unless Architect produces a separate explicit reason why the SQLite Online Backup API cannot satisfy the accepted contract.

---

# 5. Canonical reference sequence for Tech Lead

The following is an **external-reference implementation shape**, not final production code.

It is included so Architect can freeze semantics against a real supported API rather than an abstract idea.

Conceptual Python sequence:

```python
import sqlite3

src = sqlite3.connect(
    "file:/opt/CaptivePortal/data/network_metadata.sqlite3?mode=ro",
    uri=True,
    timeout=...
)

dst = sqlite3.connect(":memory:")

source_page_size = src.execute("PRAGMA page_size").fetchone()[0]

# SQLite backup documentation warns that page-size mismatch
# matters for an in-memory destination.
# Architect/Tech Lead must freeze the exact handling.
dst.execute(f"PRAGMA page_size={source_page_size}")

src.backup(
    dst,
    pages=...,
    progress=...,
    sleep=...
)

integrity_rows = dst.execute(
    "PRAGMA integrity_check"
).fetchall()

fk_rows = dst.execute(
    "PRAGMA foreign_key_check"
).fetchall()

dst.close()
src.close()
```

The final implementation must NOT blindly copy this snippet.

Tech Lead must freeze:

```text
connection URI/mode
timeouts
page-size handling
pages per backup step
progress callback semantics
sleep/pacing
deadline
cancellation
exception handling
telemetry
memory admission
shutdown/restart behavior
```

---

# 6. Critical SQLite page-size caveat

SQLite's official Backup API documentation specifically warns:

> for an in-memory destination, a source/destination page-size mismatch can cause backup failure.

The SQLite documentation explains that a newly opened empty in-memory database may have its page size set before backup.

Therefore Architect MUST explicitly freeze one of:

```text
A.
read source PRAGMA page_size
set destination PRAGMA page_size to the same value
before backup

OR

B.
prove with the exact deployed SQLite/Python runtime that the chosen
fresh in-memory destination path safely obtains the required page size
without manual setup
```

This must be deterministic.

Coder must not discover this by accident in production.

---

# 7. Incremental backup vs one-step backup

SQLite and Python support both patterns.

## 7.1 Whole backup in one call/step

Conceptually:

```text
pages <= 0
→ copy entire database
```

Advantages:

```text
simple
canonical
easy to reason about
```

Potential risk for our environment:

```text
longer continuous source read/lock pressure
large burst against already constrained HDD
```

---

## 7.2 Incremental / paged backup

SQLite's official running-database example copies a bounded number of pages, releases the source, sleeps/yields, then continues.

Python exposes:

```text
pages=
progress=
sleep=
```

This may reduce interference with the live writer.

However SQLite documentation warns that writes by other connections/processes can cause backup work to restart, and under sufficiently continuous change a backup may fail to converge in a reasonable time.

Architect must therefore freeze:

```text
whether NI-01 uses one-step or incremental backup

if incremental:
  pages per step
  sleep/yield policy
  overall deadline
  restart/non-convergence handling
  writer-latency ceiling
```

Coder must not invent adaptive pacing independently.

---

# 8. RAM/resource admission is mandatory

The source database is currently approximately:

```text
4.3 GiB
```

The production VM currently has only approximately:

```text
7.7 GiB total RAM
```

Therefore the experiment MUST NOT begin with the present RAM allocation unless Tech Lead proves sufficient memory headroom.

Owner is willing to enlarge the VM for the experiment.

Architect must define resource admission based on measured state, not merely:

```text
DB file size < MemAvailable
```

At minimum account for:

```text
in-memory destination database
source page cache
Python/SQLite validator process RSS
network-metadata.service
other CaptivPortal processes
kernel/filesystem memory
operational safety reserve
```

Architect should define a rule such as:

```text
if safe RAM admission cannot be proven
→ do not start in-memory deep validation
→ report resource_deferred / unavailable
```

It MUST NOT:

```text
trigger OOM
create swap storm
force severe reclaim pressure
label DB as corrupt
```

---

# 9. Startup lane: exact bounded checks required

The central architecture question is:

> What minimum checks are required before NI-01 may safely enter its normal writer loop, without performing a full multi-GiB deep traversal?

Architect must freeze an exact closed set.

Candidate classes:

```text
database can be opened
expected application/schema version
exact schema signature/object set
required singleton metadata
required checkpoint metadata
critical source-generation state
required PRAGMA configuration
writer ownership/lock
small bounded invariant queries
```

Architect must explicitly decide the startup status of:

```text
PRAGMA quick_check
PRAGMA integrity_check
PRAGMA foreign_key_check
```

A whole-database check whose work scales with database size is not to be called "bounded" merely because it is faster than another check.

If Architect retains `quick_check` on every startup, it must explain why that check is still operationally acceptable for this ~4.3 GiB DB and define an acceptance budget.

If Architect removes it from every startup, deep validation must preserve the required coverage elsewhere.

---

# 10. Deep validation lane

The requested deep-validation semantic is:

```text
1. pass resource admission
2. open source through admitted read-only/read path
3. create fresh SQLite `:memory:` destination
4. satisfy required page-size compatibility
5. run SQLite Online Backup API
6. require backup completion
7. run PRAGMA integrity_check on destination
8. run PRAGMA foreign_key_check if required
9. record bounded health result
10. close in-memory DB
```

No deep PASS may be recorded unless:

```text
backup completed successfully
AND
integrity_check completed successfully
AND
required FK check completed successfully
```

---

# 11. PASS semantics

A deep-check PASS means:

```text
a transactionally consistent SQLite snapshot,
successfully produced by SQLite Online Backup,
passed the admitted validation set
at a known validation run/time
```

It does NOT mean:

```text
the live database is guaranteed healthy forever
```

The live writer continues after/during the snapshot process.

Architect must define freshness semantics for last-known-good validation.

---

# 12. Failure classes

Architect must distinguish at least:

## 12.1 Resource admission failure

Examples:

```text
insufficient safe RAM
swap/reclaim threshold exceeded
memory budget unavailable
```

Meaning:

```text
deep check not run
NOT corruption
```

---

## 12.2 Backup/snapshot execution failure

Examples:

```text
SQLITE_BUSY beyond accepted retry/deadline
I/O failure
backup interruption
backup does not converge
service shutdown
```

Meaning:

```text
no valid deep-check result
NOT automatically corruption
```

---

## 12.3 Validation execution failure

Examples:

```text
validator exception
deadline exceeded after valid snapshot
unexpected runtime failure
```

Meaning:

```text
validation unavailable/incomplete
```

---

## 12.4 Confirmed integrity failure

Meaning:

```text
consistent backup completed
AND
integrity_check returned not-ok
or admitted foreign_key_check returned violations
```

This is a real integrity incident.

Architect must freeze fail-closed behavior for NI-01.

---

# 13. Failure isolation

Existing CaptivPortal principle must remain:

```text
DTI / intelligence subsystem failure
must not automatically sacrifice:

Guest Portal
Authorization
CAPPORT
shared core functionality
```

But NI-01 itself may need to stop or refuse unsafe operation if its own authoritative store is not trusted.

Architect must define:

```text
whether NI-01 writer may continue after:
  resource-deferred
  backup failure
  stale last-known-good
  confirmed corruption

whether downstream NI-02B/NI-03/NI-04 reads remain allowed

whether checkpoints may advance

what health/degraded/unavailable state is exposed
```

No silent success.

---

# 14. Scheduling

Initial Owner direction:

```text
do not perform expensive whole-DB validation on every ordinary startup
```

Candidate deep-check cadence:

```text
approximately once per 24h
```

Architect must either freeze the exact cadence or freeze a bounded configuration range for Tech Lead.

Architect must also define event-triggered validation conditions such as:

```text
SQLite malformed/corruption signal
unexpected low-level I/O error
schema/invariant contradiction
unclean/recovery event if relevant
operator-requested validation
other admitted integrity suspicion
```

---

# 15. Health record

Architect must define an auditable health record with fields sufficient to distinguish:

```text
never checked
last PASS
currently checking
resource deferred
backup failed
validation incomplete
confirmed FAIL
stale last-known-good
```

Candidate metadata:

```text
validation_run_id
policy/version
source DB identity/path
source page size
source schema/application version
started_at
snapshot_completed_at
validation_completed_at
result
failure category
last_known_good_at
backup page count / remaining telemetry
duration
```

Do not store raw network metadata in health telemetry.

---

# 16. Telemetry / observability

The mechanism should expose bounded operational evidence:

```text
run started/completed
backup progress summary
backup duration
validation duration
source page count
destination page count where useful
result
resource admission outcome
busy/retry counts
deadline/cancel reason
peak RSS / memory safety measurements where available
```

Do NOT log:

```text
raw DNS names
raw SNI
remote IP histories
individual evidence rows
payloads
```

---

# 17. Protected NI-01 invariants

This task MUST NOT change:

```text
NI-01 observation semantics
source-record identity
source-generation semantics
checkpoint ownership
replay/idempotency
WAL
foreign_keys=ON
synchronous=FULL
one logical writer
retention contract
capture scope
privacy semantics
```

The in-memory DB is:

```text
ephemeral
read-validation target
not authoritative
not a second writer store
not a fallback production store
not a recovery backup
```

---

# 18. Explicitly rejected implementation shortcuts

Do NOT implement:

```text
raw `cp` of live .sqlite3
manual copy of .sqlite3 + -wal + -shm
custom page-copy algorithm
custom B-tree validator
custom corruption scanner
VACUUM/VACUUM INTO as the first selected mechanism
synchronous downgrade
fsync suppression
journal_mode change
hot-path VACUUM
automatic delete/recreate on corruption
automatic "repair" of source DB
SSD migration as the answer
```

`VACUUM INTO` is an SQLite-supported technique but is NOT the selected first mechanism for this task because Owner wants to test the canonical Online Backup → RAM validation path with minimum semantic change.

---

# 19. Required Lab correctness matrix

Architect must freeze deterministic tests for at least:

```text
healthy source DB
wrong schema/application version
missing required object
truncated DB
malformed DB
corrupt page/B-tree
index inconsistency detectable by integrity_check
FK violation where applicable

live WAL with committed data
concurrent NI-01 writer while backup runs
source updates during incremental backup
backup restart due to source changes
backup non-convergence/deadline

source/destination page-size compatibility
wrong destination page size

insufficient RAM
swap/reclaim admission failure
SQLite busy
I/O error
backup interrupted
validator interrupted
service shutdown during validation

deep PASS
deep confirmed FAIL
old last-known-good + new live writes
```

For every case Architect must define:

```text
startup allowed?
writer allowed?
checkpoint advancement allowed?
downstream reads allowed?
retry?
health state?
operator action?
```

---

# 20. Required performance experiment

Compare at least:

```text
BASELINE:
current deep check against disk-backed NI-01 DB

CANDIDATE:
Online Backup API
→ SQLite `:memory:`
→ integrity_check
→ optional foreign_key_check
```

Measure:

```text
startup/readiness time
backup time
integrity-check time
total deep-validation time

host physical HDD read IOPS
host read await
host busy
read bytes

guest block reads
NI-01 CPU
validator CPU

RAM peak
MemAvailable
swap in/out
memory PSI
I/O PSI

NI-01 ingest latency
writer latency
WAL size/growth
checkpoint continuity

Portal/Auth health
NI-02B/NI-03/NI-04 continuity
```

No improvement percentage is pre-declared.

PASS requires measurable end-to-end benefit without violating correctness/resource gates.

---

# 21. Exact Architect questions

Architect must answer explicitly:

1. Is canonical `SQLite Online Backup → :memory: → integrity_check` admitted for NI-01?
2. What exact startup validation remains mandatory?
3. Does `quick_check` remain startup-critical or move to deep validation?
4. Is `foreign_key_check` required in the deep-validation set?
5. What exact source connection semantics are required?
6. What exact page-size setup is required before backup to `:memory:`?
7. One-step backup or incremental backup?
8. If incremental, what `pages`, sleep/yield, retry and deadline semantics are frozen?
9. What is the RAM/resource admission formula?
10. What minimum RAM reserve is required?
11. What swap/reclaim condition causes deferral?
12. What happens if backup repeatedly restarts under live writes?
13. What is the deep-check cadence?
14. What event triggers an immediate deep check?
15. Where and how is validation health persisted?
16. How fresh must last-known-good be?
17. What happens after resource deferral?
18. What happens after backup failure?
19. What happens after confirmed corruption?
20. What downstream functionality remains available?
21. What rollback restores the previous startup validation path?
22. What exact QA/PERF gates must Tech Lead pass before recommending production activation?

---

# 22. Requested Architect deliverable

Architect should return an implementation-ready document such as:

```text
TASK-DTI-NI-01-DB-VALIDATION-OPT-01
ARCHITECTURE CONTRACT v1
```

The contract must freeze:

```text
startup validation algorithm
deep validation algorithm
SQLite Backup API usage contract
page-size handling
memory/resource admission
backup pacing
deadline/retry
state machine
health semantics
failure isolation
scheduling
telemetry
privacy
rollback
QA matrix
performance gates
```

The Architect deliverable should be sufficient for Tech Lead to write a narrow implementation TASK without inventing missing semantics.

---

# 23. Governance chain

Required sequence:

```text
Owner request
    ↓
Architect Contract
    ↓
Tech Lead source/current-runtime review
    ↓
Tech Lead freezes exact baseline + file allowlist
    ↓
Tech Lead issues Coder TASK
    ↓
Coder implements in Lab + focused tests
    ↓
Tech Lead independently runs correctness/PERF gates
    ↓
Owner decides whether to permit production experiment
```

Until the Architect Contract is accepted:

```text
CODER = HOLD
PRODUCTION = UNCHANGED
```

---

# 24. External reference index

## SQLite official

**SQLite Online Backup API**  
https://www.sqlite.org/backup.html

Read specifically:

```text
§1  Using the SQLite Online Backup API
§2  Loading and Saving In-Memory Databases
§2.1 Error handling
§2.2 Possible Enhancements
§3  Online Backup of a Running Database
§3.1 File and Database Connection Locking
§3.2 backup_remaining() / backup_pagecount()
```

**PRAGMA integrity_check**  
https://www.sqlite.org/pragma.html#pragma_integrity_check

**PRAGMA quick_check**  
https://www.sqlite.org/pragma.html#pragma_quick_check

**PRAGMA foreign_key_check**  
https://www.sqlite.org/pragma.html#pragma_foreign_key_check

**SQLite forum — integrity_check on Backup API result; Richard Hipp confirmation**  
https://sqlite.org/forum/info/3dd8dad9f82e457501176c1a2ac158640a0c90a090a8db320a425dbba9515f5d?t=c

---

## Python standard library

**Python `sqlite3.Connection.backup()`**  
https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup

Important documented parameters:

```text
target
pages
progress
name
sleep
```

The official Python documentation includes the direct pattern:

```text
file-backed SQLite
→ sqlite3.connect(":memory:")
→ source_connection.backup(memory_connection)
```

This is the selected implementation family for Architect review.

---

# 25. Final design intent

The intended design is not:

```text
"make our own RAM database trick"
```

It is:

```text
use SQLite's own Online Backup API exactly for what it supports:
a consistent SQLite copy into an in-memory SQLite database,
then run SQLite's own integrity PRAGMAs on that copy.
```

CaptivPortal-specific architecture is limited to:

```text
when to run it
what remains in startup
how much RAM is required
how backup coexists with the writer
how failures are represented
what becomes unavailable on confirmed corruption
how Tech Lead proves performance/correctness
```

No custom database-copy or integrity mechanism is requested.
