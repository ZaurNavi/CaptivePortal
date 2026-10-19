# TASK-DTI-NI-01
## SQLITE CAPACITY ARCHITECTURE AMENDMENT R2
### BOUNDED ARCHITECTURE RETURN AFTER CAPACITY GATE FAILURE
### DRAFT FOR TECH LEAD REVIEW

**Проект:** CaptivPortal  
**Программа:** DTI — Network Intelligence  
**Задача:** `TASK-DTI-NI-01`  
**Причина возврата:** `SQLITE_CAPACITY_GATE_FAILED`  
**Роль:** Architect  
**Статус:** `DRAFT FOR TECH LEAD REVIEW`

---

# 0. ВХОДНОЙ VERDICT

Принятые факты:

```text
CODE_STATUS =
IMPLEMENTATION ACCEPTED

PRODUCTION_BOUNDED_INGEST =
PASS

PRODUCTION_PERMANENT_ACTIVATION =
HOLD

OPEN_CODE_P0 =
0

OPEN_CODE_P1 =
0
```

Capacity failure является архитектурным, а не функциональным defect реализации.

Принятый bounded production evidence:

```text
duration ≈ 305 s

observations = 183
dns = 71
tls = 52
quic = 60

ingest_fault_aggregates = 0

generation_state = runnable
blocked_reason = NONE

metadata_output_health = usable
metadata_ingest_health = usable
capture_health = usable

SQLite quick_check = ok

Fingerprint sensor PID unchanged
Fingerprint sensor NRestarts unchanged

rollback = PASS
```

Принятый performance evidence:

```text
30,000 mixed observations

sustained ingest =
~1051.5 events/s

replay =
~2808.2 events/s

replay duplicates =
30,000

replay new commits =
0

concurrent read p95 =
~1.8 ms

concurrent read max =
~25.9 ms

recovery =
~48 ms

30,000-row retention cleanup =
~3.26 s

reader max RSS =
~94 MiB

checkpoint lag after successful batches =
0

64-MiB physical-cap test =
capacity_halted = true
failed batch checkpoint advance = 0
hard cap exceeded = NO

page reuse / repeated-cycle ratio =
1.032
```

Следовательно:

```text
SQLITE FUNCTIONAL / PERFORMANCE FITNESS =
PASS

SQLITE CURRENT CAPACITY BUDGET =
FAIL
```

---

# 1. FROZEN — НЕ ПЕРЕОТКРЫВАЕТСЯ

Этот amendment НЕ меняет:

```text
DB engine = SQLite

sensitive retention = 14 days

core retention = 30 days

DNS admission = unchanged

TLS admission = unchanged

QUIC admission = unchanged

source cardinality = unchanged

NO sampling

NO heuristic dedup

NO event dropping

NO provenance removal

NO identity removal

NO health-data removal

NO source schema weakening

NO Device attribution in NI-01

NO public/Admin API

NO payload/PCAP persistence
```

Implementation semantic model остаётся accepted.

---

# 2. CAPACITY EVIDENCE — ARCHITECTURAL INPUT

Принятый NI-00 event-rate evidence:

```text
DNS  ≈ 3.0733 events/s
QUIC ≈ 1.4600 events/s
TLS  ≈ 1.1800 events/s

TOTAL ≈ 5.7132 events/s
```

Measured storage cost:

```text
DNS:
full-sensitive = 2215.5 B/event
core-only      = 1855.5 B/event

TLS:
full-sensitive = 2307.7 B/event
core-only      = 2181.5 B/event

QUIC:
full-sensitive = 1961.2 B/event
core-only      = 1833.8 B/event
```

Frozen retention:

```text
SensitiveNetworkMetadata =
14 days

normalized non-sensitive core =
30 days
```

Accepted steady-state projection:

```text
DNS  ≈ 15.01 GiB
QUIC ≈  6.67 GiB
TLS  ≈  6.38 GiB

active retained dataset ≈
28.07 GiB

+ WAL operational reserve =
64 MiB

+ transaction headroom =
16 MiB

required capacity ≈
28.14 GiB
```

Old architecture hard cap:

```text
8 GiB
```

Result:

```text
projected utilization ≈ 351.8%

capacity shortfall ≈ 20.14 GiB

SQLITE_CAPACITY_GATE = FAIL
```

---

# 3. ARCHITECTURAL DECISION

Capacity failure is resolved by an **explicit storage-budget revision**, not by changing the accepted data model.

Stage NI-01 R2 freezes:

```text
DB ENGINE =
SQLite unchanged

REPOSITORY DEFAULT MAX DB =
8 GiB unchanged

ARCHITECTURE HARD MAX =
64 GiB

CURRENT PRODUCTION TARGET MAX =
48 GiB
```

Exact bytes:

```text
8 GiB =
8589934592

48 GiB =
51539607552

64 GiB =
68719476736
```

This is an explicit architecture-owned change.

It is NOT a silent configuration increase.

---

# 4. WHY 48 GiB IS THE CURRENT PRODUCTION TARGET

Current projected requirement:

```text
28.14 GiB
```

Against configured production target:

```text
48 GiB
```

Projected utilization:

```text
28.14 / 48
≈ 58.6%
```

Projected headroom inside the configured SQLite footprint cap:

```text
48 - 28.14
≈ 19.86 GiB
```

Therefore current accepted model is no longer close to the configured stop boundary.

48 GiB is the exact current production target.

64 GiB is only the architecture hard ceiling allowing future explicitly reviewed configuration increases without another DB-engine decision.

---

# 5. CAPACITY ADMISSION RULE

Permanent NI-01 activation requires:

```text
projected_steady_state_required_bytes
<=
0.65 × configured NETWORK_METADATA_MAX_DB_BYTES
```

For current evidence:

```text
28.14 GiB
<=
0.65 × 48 GiB

28.14
<=
31.20

PASS
```

If later evidence violates this ratio:

```text
PRODUCTION HOLD
→ capacity re-admission
```

No automatic increase.

No automatic retention reduction.

No sampling.

---

# 6. CONFIGURATION CONTRACT REVISION

Repository-safe default remains:

```text
NETWORK_METADATA_MAX_DB_BYTES =
8589934592
= 8 GiB
```

Reason:

```text
merge / accidental enablement
must not automatically authorize a 48-GiB footprint
```

Permanent current-production activation MUST explicitly configure:

```text
NETWORK_METADATA_MAX_DB_BYTES =
51539607552
= 48 GiB
```

Validator hard maximum changes from:

```text
<= 8589934592
```

to:

```text
<= 68719476736
```

Therefore:

```text
0 <
NETWORK_METADATA_MAX_DB_BYTES
<=
68719476736
```

All other NI-01 technical ceilings remain unchanged.

---

# 7. CURRENT IMPLEMENTATION STATUS AFTER THIS AMENDMENT

Existing NI-01 implementation remains:

```text
IMPLEMENTATION ACCEPTED
```

Architecture requires only a bounded capacity remediation for:

```text
hard-max validation constant

configuration validation tests

capacity documentation / activation preflight
```

No storage schema redesign is authorized.

No observation model change is authorized.

No retention code change is authorized.

No source-normalizer change is authorized.

No replay/idempotency change is authorized.

No DB-engine change is authorized.

---

# 8. PRODUCTION FILESYSTEM GATE

The SQLite footprint cap alone is insufficient.

Permanent production activation requires the filesystem containing:

```text
NETWORK_METADATA_DB_PATH
```

to have, at activation time:

```text
available_bytes
>=
configured NETWORK_METADATA_MAX_DB_BYTES
+
16 GiB host/filesystem safety reserve
```

For the current 48-GiB target:

```text
minimum available filesystem space at activation =
64 GiB
```

Exact:

```text
48 GiB configured footprint
+
16 GiB external filesystem reserve
=
64 GiB available
```

The 16-GiB filesystem reserve is OUTSIDE:

```text
sqlite_footprint_bytes
```

and is not counted as retained NI data.

---

# 9. STORAGE LOCATION REQUIREMENT

Production Network Observation Store MUST reside on:

```text
local filesystem storage
with normal SQLite locking/durability semantics
```

Forbidden for NI-01 V1 permanent activation:

```text
NFS

SMB/CIFS

object-storage mount

remote FUSE filesystem

other network filesystem
without a separately accepted SQLite durability contract
```

A dedicated local filesystem/LV is preferred but not mandatory.

A shared filesystem is allowed only if it satisfies the same free-space gate and has no competing unbounded writer that invalidates the reserve assumption.

---

# 10. CURRENT PRODUCTION ROOT FILESYSTEM DISPOSITION

Existing production baseline measured approximately:

```text
root filesystem =
98G total

54G used

~40G available
```

Therefore current root filesystem does NOT satisfy:

```text
64 GiB available
```

required for permanent NI-01 activation with the 48-GiB configured footprint.

Consequently:

```text
CURRENT ROOT STORAGE =
NOT ELIGIBLE FOR PERMANENT NI-01 ACTIVATION
```

This is not a CaptivPortal code defect.

Before permanent activation, SysAdmin/deployment must do ONE of:

```text
A.
expand the filesystem containing NETWORK_METADATA_DB_PATH

OR

B.
place NETWORK_METADATA_DB_PATH on another suitable local filesystem/volume
```

No storage action is authorized by this architecture document itself.

---

# 11. DB PATH POLICY

Architecture does NOT require a source-code path rewrite.

Existing configurable:

```text
NETWORK_METADATA_DB_PATH
```

remains the storage-location authority.

The repository default may remain:

```text
/opt/CaptivePortal/data/network_metadata.sqlite3
```

But production activation may override it to an approved local filesystem path.

The exact production path must be recorded in activation evidence.

---

# 12. COMBINED SQLITE FOOTPRINT — UNCHANGED

Capacity enforcement continues to use:

```text
sqlite_footprint_bytes =
size(main database)
+
size(-wal if present)
+
size(-shm if present)
+
size(-journal if unexpectedly present)
```

WAL/SHM are not excluded from the configured cap.

The existing successful hard-cap behavior remains mandatory:

```text
no transaction that would exceed configured cap

no checkpoint advance for failed over-cap batch

metadata_ingest_health becomes unavailable on capacity halt
```

---

# 13. NO SILENT CAP ESCALATION

Runtime MUST NOT automatically change:

```text
NETWORK_METADATA_MAX_DB_BYTES
```

based on:

```text
free disk
observed traffic
current DB size
retention pressure
```

If configured cap is reached:

```text
ingest halts safely
checkpoint does not advance
health reports capacity failure
```

Operator must resolve the condition explicitly.

---

# 14. FUTURE LOAD GROWTH

64 GiB architecture hard maximum does NOT mean NI-01 may silently grow to 64 GiB.

Current approved configuration is:

```text
48 GiB
```

A future increase above 48 GiB but not above 64 GiB requires at minimum:

```text
new measured event-rate evidence

new projected steady-state calculation

filesystem free-space preflight

Tech Lead capacity re-admission

explicit deployment configuration change
```

No code architecture redesign is required solely because the value remains within the 64-GiB hard ceiling.

If required configured capacity would exceed:

```text
64 GiB
```

then:

```text
STOP
→ ARCHITECTURE RETURN
```

Possible future decisions may include another storage architecture, but are not pre-authorized.

---

# 15. RETENTION / CARDINALITY REMAIN FROZEN

Capacity remediation MUST NOT be implemented by:

```text
shortening 14-day sensitive retention

shortening 30-day core retention

dropping DNS

dropping TLS

dropping QUIC

sampling

event coalescing that changes source cardinality

heuristic dedup

removing source identity

removing provenance

removing source health
```

The accepted 28.14-GiB projection is therefore the capacity object to provision for, not something to force back under 8 GiB by weakening semantics.

---

# 16. WHY SQLITE REMAINS ACCEPTED

The failed gate was storage budget, not SQLite performance.

Accepted evidence shows:

```text
~1051.5 events/s sustained ingest
vs
~5.7132 events/s accepted production load

~2808.2 events/s replay

read p95 ~1.8 ms

recovery ~48 ms

30k cleanup ~3.26 s

checkpoint lag = 0

page reuse ratio = 1.032

hard-cap halt semantics = PASS
```

Therefore no evidence justifies changing DB engine.

Architecture verdict:

```text
SQLITE ENGINE =
RETAIN

SQLITE 8-GiB BUDGET =
REJECT / SUPERSEDED
```

---

# 17. BOUNDED CODE REMEDIATION AUTHORITY

After Tech Lead accepts this amendment, the implementation owner may prepare a bounded remediation patch containing ONLY what is required to support the revised capacity contract.

Expected code-level scope:

```text
architecture hard-max constant:
8 GiB → 64 GiB

validation:
allow configured values up to 64 GiB

repository default:
remain 8 GiB

tests:
8-GiB default preserved
48-GiB value accepted
64-GiB value accepted
>64-GiB value rejected
small synthetic cap halt behavior still PASS
```

The patch MUST NOT modify:

```text
SQLite schema
retention semantics
normalization
event families
cardinality
replay semantics
checkpoint semantics
privacy model
health model
Fingerprint integration
```

If more code scope appears necessary:

```text
STOP
→ Tech Lead / Architect return
```

---

# 18. SYSADMIN / DEPLOYMENT PRECONDITION

Permanent activation requires separate SysAdmin evidence for the chosen DB filesystem.

Required evidence:

```text
resolved NETWORK_METADATA_DB_PATH

filesystem / mount identity

local-vs-network filesystem proof

total bytes

available bytes

available bytes >= 64 GiB
for current 48-GiB config

write ownership/permissions

SQLite create/write/fsync viability

no conflicting storage quota below configured cap
```

This evidence is activation-time infrastructure evidence.

It is not Coder evidence.

---

# 19. CAPACITY REVALIDATION AFTER BOUNDED PATCH

The full 30,000-event performance campaign does NOT need to be repeated solely because the architecture hard ceiling changed, unless Tech Lead requests it or code changes exceed the bounded constant/validation scope.

Mandatory bounded revalidation:

```text
1. exact config validation:
   48 GiB accepted

2. exact hard-max validation:
   64 GiB accepted
   >64 GiB rejected

3. repository default:
   remains 8 GiB

4. existing small-cap physical stop test:
   PASS

5. mathematical production projection:
   28.14 / 48 ≈ 58.6%
   PASS against <=65% admission threshold

6. target production filesystem:
   >=64 GiB available
   PASS

7. no directly affected regression
```

If any item fails:

```text
PRODUCTION HOLD
```

---

# 20. PERMANENT ACTIVATION GATE

Permanent NI-01 activation is allowed only when ALL are true:

```text
CODE_STATUS =
IMPLEMENTATION ACCEPTED

BOUNDED CAPACITY REMEDIATION =
PASS

CONFIGURED MAX =
48 GiB

PROJECTED STEADY-STATE =
<=65% of configured max

TARGET FILESYSTEM =
local / SQLite-suitable

AVAILABLE SPACE AT ACTIVATION =
>=64 GiB

RETENTION =
14d sensitive / 30d core unchanged

SOURCE CARDINALITY =
unchanged

FINGERPRINT COEXISTENCE =
PASS

ROLLBACK =
PASS

TECH LEAD =
PASS

OWNER =
explicit activation authorization
```

Until then:

```text
PRODUCTION_PERMANENT_ACTIVATION = HOLD
```

---

# 21. BOUNDED PRODUCTION INGEST STATUS

The already completed ~305-second bounded production ingest remains valid evidence.

It does NOT need to be repeated merely because this architecture changes the permitted storage budget.

It proved:

```text
source output usable
ingest usable
capture usable
generation runnable
no ingest fault aggregates
SQLite integrity ok
Fingerprint unaffected
rollback pass
```

Capacity was the only returned architecture blocker.

---

# 22. RUNTIME SAFETY — NO HOST-DISK CLAIM

The 48-GiB configured DB cap is not permission to consume all host disk.

It is an upper bound for:

```text
combined SQLite footprint
```

and must coexist with the external 16-GiB filesystem reserve at activation.

If real filesystem capacity later becomes insufficient because of unrelated host growth:

```text
ordinary SQLite/write failures
must remain fail-safe:
no false successful ingest
no checkpoint advance beyond failed batch
health unavailable
```

A future dedicated runtime free-space guard may be architected separately if operational evidence shows it is required.

It is NOT necessary to reopen accepted NI-01 code solely for this capacity return.

---

# 23. UPDATED NI-01 CAPACITY INVARIANTS

```text
NI01-CAP-I01

SQLite remains the NI-01 V1 DB engine.

NI01-CAP-I02

Frozen retention remains:
14d sensitive / 30d core.

NI01-CAP-I03

DNS/TLS/QUIC cardinality is unchanged.

NI01-CAP-I04

Repository default NETWORK_METADATA_MAX_DB_BYTES remains 8 GiB.

NI01-CAP-I05

Architecture hard maximum becomes 64 GiB.

NI01-CAP-I06

Current production configured maximum is exactly 48 GiB.

NI01-CAP-I07

Permanent activation requires projected steady-state <=65% of configured max.

NI01-CAP-I08

Current 28.14-GiB model against 48 GiB is ~58.6% and satisfies the revised architecture ratio.

NI01-CAP-I09

Current production target filesystem must have >=64 GiB available at activation.

NI01-CAP-I10

Current ~40-GiB-free root filesystem is not eligible for permanent NI-01 activation.

NI01-CAP-I11

WAL/SHM/journal remain part of combined SQLite footprint accounting.

NI01-CAP-I12

No automatic cap increase is permitted.

NI01-CAP-I13

No silent retention reduction is permitted.

NI01-CAP-I14

No sampling/dedup/cardinality change is permitted as capacity remediation.

NI01-CAP-I15

No DB-engine change is authorized.

NI01-CAP-I16

Configured cap >48 GiB requires new capacity evidence and Tech Lead admission.

NI01-CAP-I17

Configured requirement >64 GiB requires architecture return.

NI01-CAP-I18

Permanent activation remains separate Owner-controlled action.
```

---

# 24. SUPERSEDED NI-01 R1 CLAUSES

The following R1 values are superseded:

```text
Hard architecture maximum =
8 GiB
```

becomes:

```text
Hard architecture maximum =
64 GiB
```

Validation:

```text
0 < NETWORK_METADATA_MAX_DB_BYTES <= 8589934592
```

becomes:

```text
0 < NETWORK_METADATA_MAX_DB_BYTES <= 68719476736
```

The repository default statement:

```text
NETWORK_METADATA_MAX_DB_BYTES=8589934592
```

remains unchanged.

For current permanent production activation, deployment MUST explicitly override it to:

```text
NETWORK_METADATA_MAX_DB_BYTES=51539607552
```

All other NI-01 R1 clauses remain normative.

---

# 25. ARCHITECTURE DISPOSITION

```text
TASK =
TASK-DTI-NI-01

RETURN_REASON =
SQLITE_CAPACITY_GATE_FAILED

ARCHITECTURE_RESOLUTION =
EXPLICIT SQLITE STORAGE-BUDGET REVISION
+
PRODUCTION FILESYSTEM CAPACITY GATE

DB_ENGINE =
SQLITE UNCHANGED

RETENTION =
UNCHANGED

CARDINALITY =
UNCHANGED

REPOSITORY_DEFAULT_MAX =
8 GiB

CURRENT_PRODUCTION_CONFIGURED_MAX =
48 GiB

ARCHITECTURE_HARD_MAX =
64 GiB

CURRENT_PROJECTED_REQUIREMENT =
28.14 GiB

CURRENT_PROJECTED_UTILIZATION =
~58.6% OF 48 GiB

PRODUCTION_FILESYSTEM_MIN_AVAILABLE =
64 GiB

CURRENT ROOT FILESYSTEM =
NOT ELIGIBLE FOR PERMANENT ACTIVATION

CODE_STATUS =
IMPLEMENTATION ACCEPTED

BOUNDED_CODE_REMEDIATION =
REQUIRED AFTER TECH LEAD PASS

PRODUCTION_BOUNDED_INGEST =
PASS / EVIDENCE RETAINED

PRODUCTION_PERMANENT_ACTIVATION =
HOLD

OPEN_ARCH_P0 =
0

OPEN_ARCH_P1 =
0

OPEN_CODE_P0 =
0

OPEN_CODE_P1 =
0

ARCHITECTURE_STATUS =
DRAFT FOR TECH LEAD REVIEW
```

Следующий разрешённый шаг:

```text
Tech Lead
→ review this bounded capacity amendment

if PASS:
→ bounded capacity remediation task
→ targeted code/config validation
→ SysAdmin storage preflight
→ capacity revalidation
→ Owner permanent-activation decision

until then:
PERMANENT PRODUCTION ACTIVATION = HOLD
```
