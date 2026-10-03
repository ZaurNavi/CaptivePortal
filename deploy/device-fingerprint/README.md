# Fingerprint Suricata production output boundary

The deployable `suricata.yaml` contains exactly one enabled EVE output:

```text
filetype: unix_dgram
filename: /run/captive-portal/fingerprint-sensor/suricata-eve.sock
```

There is no admitted production diagnostic regular EVE dependency. In a separately
authorized deployment, replace the installed configuration with this complete
template; do not merge or append the old diagnostic `eve-log` entry. In particular,
`/run/fingerprint-suricata/diag-eve.json` must not be an enabled output.

Suricata 8.0.6 requires a writable `default-log-dir` during startup even with
socket-only EVE. Keep that directory separate from the sensor-owned socket directory:

```text
default-log-dir: /run/fingerprint-suricata
RuntimeDirectory=fingerprint-suricata
RuntimeDirectoryMode=0750
```

The unit creates this directory for its `suricata` user. Do not restore
`ReadOnlyPaths=/run` or add a `ReadWritePaths=/run` workaround. The diagnostic-output
boundary is the complete socket-only configuration, not a blanket read-only tmpfs.
Do not add a regular EVE output or a daemon/PID-file mode to this foreground service.
Capture interface, BPF, sensor socket path and TLS/QUIC output remain unchanged.

No deployment, service restart, production file deletion or profile activation is
performed by this source repair. Existing diagnostic bytes require separate Owner
cleanup authorization; applying this configuration does not delete them. The FIX1
task reports production-proven recovery with this directory arrangement, `-T` and
service startup PASS, no diagnostic EVE file, and sensor ready with an empty spool.
That is supplied Owner deployment evidence, not a Linux execution by this Coder.
Any further deployment/startup verification remains a separate Owner operation.

## Task-01 integrity lifecycle

Repository startup still performs full `PRAGMA quick_check`, exact schema/state
validation and evidence/health sequence consistency checks before admitting writes.
Offline migration/recovery retains the same full validation. Periodic runtime
maintenance checks only schema/version and singleton generation/allocator metadata;
it does not scan evidence data or run full integrity PRAGMAs on the ingest lock.
Retention remains chunked, the single writer/lock and HTTP semaphore are unchanged,
and corruption reported by SQLite operations still latches runtime unavailable.
Periodic metadata health is not a claim that every evidence page has been scanned;
full verification occurs at the explicit startup/offline lifecycle boundary.
