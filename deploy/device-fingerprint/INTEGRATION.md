# Task-05 deployment artifact (not activated)

Integration defaults to disabled. Portal composition creates only the short-write
submitter; the separate `fingerprint-classification.service` owns classification.
The unit follows the existing admin user, `/opt/CaptivePortal` source directory and
`/etc/default/captive-portal` environment convention. It opens no listener and uses
no controller/provider. Installing/enabling/restarting it requires a separate Owner
deployment authorization.

The dedicated integration database is schema v1, FULL synchronous, rollback-journal
SQLite with a 100 ms contention budget. Its parent must already exist; only this
database is initialized by Task-05. Other domain databases are never initialized or
migrated. Evidence/Registry/Visit reads use their existing read-only boundaries.
The integration database and consumer lock must be owned by the same runtime user
as the Portal submitter and worker. Do not alias any domain database path.

One successful AuthRun queues one durable job. The fixed window is Auth-300s to
Auth+120s, due at Auth+150s; Foundation valid-from clamps only the start. Classification
uses the dynamically pinned admitted profile and normal Task-04 production path.
Five attempts and the 30/120/300/600s retry schedule are bounded. A kernel consumer
lock prevents overlapping consumers even after lease expiry; DB token CAS protects
completion. A committed planned classification ID is recovered before new assembly.
Shutdown stops new work and permits the current synchronous request to finish; a
forced exit leaves the lease and planned ID recoverable.

Identity uses only exact Registry session/Site/MAC snapshots and exact Visit start
session/run matches. A historical Visit read is one page of at most 100 visits in
the fixed Auth +/-1h range; absent proof remains unresolved. Identity retries end
at Auth+1h. No MAC/identity guessing or raw/result payload replication is permitted.

The Linux snapshot memory guard measures current RSS from `/proc/self/statm` and
`SC_PAGE_SIZE`; missing measurements fail closed for the classification job. No
profile, timing, memory ceiling or classifier policy is tuned by this subsystem.
