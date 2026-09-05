# TASK-DB-BASELINE-SYNC-01 — привести production DB layer к актуальному baseline

Status: APPROVED / READY FOR EXECUTION / NOT YET ACCEPTED
Updated: 2026-09-06

## 1. Baseline

Canonical Git baseline for this TASK:

```text
main = 6fbc3736085be9d0538d893b6e9569ff490ef7f4
tree = fc3c1ed53df32d0074036a749ee028781ec1f1b5
```

Owner-confirmed production application state at TASK intake:

```text
PROD_HEAD=6fbc3736085be9d0538d893b6e9569ff490ef7f4
WORKTREE=CLEAN
```

`TASK-ADMIN-PROD-BASELINE-01` is complete.

The next planned product stage is **Traffic 0.8**, but it must not begin until
this DB baseline task finishes with:

```text
FINAL_DB_BASELINE=PASS
```

This TASK does not implement Traffic 0.8.

## 2. Goal

Inspect every active CaptivPortal production SQLite persistent store against the
schema/runtime contract of the exact current `main`, apply only migrations or
activation procedures already defined by the project, and establish one
unambiguous healthy production DB baseline.

Do not change data or schema merely to make the databases look newer.

## 3. Primary production databases

Minimum required inventory:

```text
/opt/CaptivePortal/data/observations.sqlite3
/opt/CaptivePortal/data/visits.sqlite3
/opt/CaptivePortal/data/traffic_projection.sqlite3
```

Also inventory any other active persistent SQLite store declared/used by the
exact current `main` and enabled in production, including where applicable:

```text
/opt/CaptivePortal/data/current_state.sqlite3
visitor_registry.sqlite3
public_traffic.sqlite3
portal_counter.db
```

Exact runtime paths for stores other than the three primary DBs must be resolved
from current code/settings and production configuration rather than guessed.

## 4. Source-of-truth boundaries

### Observation

`observations.sqlite3` is authoritative raw/historical evidence for historical
telemetry.

Forbidden merely for compatibility convenience:
- deleting historical Observation rows;
- rewriting historical facts;
- normalizing old evidence into a new semantic meaning;
- purging source evidence to make a migration/rebuild easier.

### Traffic Projection

`traffic_projection.sqlite3` is a derived/materialized read-model over
authoritative Observation evidence.

Current code baseline identifies:

```text
projection version = historical_traffic_projection.v1
source schema version = 1
default DB path = /opt/CaptivePortal/data/traffic_projection.sqlite3
```

Projection data is disposable/rebuildable only from canonical Observation
evidence. It is not a second authoritative source.

Do not rebuild merely for formality when schema/version is current, health is
good and backlog is zero.

### Visits

The existing Visit Lifecycle state and the previously accepted recovery after
the Omada Site rename are current production truth.

Do not re-run Site rename recovery and do not re-open/re-close visits without a
new, explicit reason and Owner/Tech Lead authorization.

## 5. Schema inventory gate

For every active DB record:

```text
path
exists
size
SQLite version if relevant
PRAGMA user_version
tables
indexes
triggers
foreign_keys
```

Compare the production schema to the contract expected by exact baseline:

```text
6fbc3736085be9d0538d893b6e9569ff490ef7f4
```

Current code wins over stale documentation when they disagree.

## 6. Integrity gate

Before changing any DB, run at minimum:

```sql
PRAGMA quick_check;
PRAGMA foreign_key_check;
```

Required healthy result:

```text
quick_check=ok
foreign_key_violations=0
```

Any integrity failure is a STOP before modifying data. Return a separate Tech
Lead report.

## 7. Migration assessment

For each DB establish:

```text
CURRENT_SCHEMA_VERSION=
EXPECTED_SCHEMA_VERSION=
MIGRATION_REQUIRED=yes/no
```

If no migration is required, do not manufacture one.

If migration is required, use only the repository's existing migration,
activation or rebuild contract. Do not write ad-hoc production SQL merely to
force schema parity.

## 8. Backup gate

Before any operation that can modify a DB:

1. create a timestamped backup of that DB;
2. verify backup exists;
3. verify backup size > 0;
4. run SQLite `PRAGMA quick_check` against the backup;
5. stop if the backup is unhealthy.

Read-only inventory/integrity checks do not require a backup by themselves.

## 9. Allowed DB changes

Apply only changes objectively required by current `main`.

Without separate approval, do not:

```text
DROP production tables
mass DELETE
manual historical data rewrite
schema redesign
change semantic meaning of stored fields
purge Observation evidence
re-run Site rename Visit recovery
```

## 10. Traffic Projection gate

Confirm separately:

```text
traffic-projection.service
projection schema/version
projection health
projection backlog
materialized data availability
```

If projection is current, healthy and `backlog=0`, do not rebuild for formality.

If rebuild is objectively required, stop before rebuild long enough to record
the reason and ensure the backup/source/read-model boundaries above are
satisfied.

A rebuild, when justified, must derive only from canonical Observation evidence.

## 11. Post-change verification

After all required changes repeat:

```text
PRAGMA quick_check
PRAGMA foreign_key_check
schema/user_version
service health
projection health/backlog
```

Verify CaptivPortal can continue to read all relevant DBs without new runtime
errors.

## 12. Out of scope

This TASK does not:
- implement Traffic 0.8;
- change Traffic business logic;
- change Admin Web;
- optimize SQL because a query merely looks slow;
- resolve the known synthetic 12AP/14d/30s performance debt;
- create a new DB architecture;
- redesign projection semantics.

## 13. Final Tech Lead report

```text
TASK-DB-BASELINE-SYNC-01

GIT_BASELINE=
DBS_CHECKED=

OBSERVATION_DB:
path=
user_version=
quick_check=
foreign_key_violations=
migration_required=
migration_applied=

VISITS_DB:
path=
user_version=
quick_check=
foreign_key_violations=
migration_required=
migration_applied=

TRAFFIC_PROJECTION_DB:
path=
user_version=
quick_check=
foreign_key_violations=
migration_required=
migration_applied=
projection_health=
projection_backlog=

OTHER_ACTIVE_DBS=

BACKUPS_CREATED=

DATA_REWRITTEN=yes/no
DESTRUCTIVE_ACTIONS=none/<details>

FINAL_DB_BASELINE=PASS/FAIL
BLOCKERS_FOR_TRAFFIC_0_8=none/<details>
```

## 14. Completion criterion

This TASK is complete only when all active production DBs match the exact current
repository contract, integrity checks pass, all genuinely required migrations
are complete, Traffic Projection is healthy with backlog zero or an explicitly
documented accepted exception, and no unjustified historical-data modification
occurred.

Only after:

```text
FINAL_DB_BASELINE=PASS
```

is the DB layer considered ready for the planned **Traffic 0.8** stage.
