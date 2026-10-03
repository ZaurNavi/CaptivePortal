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

The service's `ReadOnlyPaths=/run` is a second, fail-closed boundary: a configuration
that attempts a regular file write there cannot exhaust host tmpfs. Sending to the
existing sensor-owned AF_UNIX datagram socket remains allowed. This distinction is
documented by [systemd](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml).
Do not add a writable `/run` exception or a daemon/PID-file mode to this foreground
service. Capture interface, BPF, socket path and TLS/QUIC output remain unchanged.

No deployment, service restart, production file deletion or profile activation is
performed by this source repair. Existing diagnostic bytes require separate Owner
cleanup authorization; applying the boundary does not delete them. Linux service
startup/socket delivery must be verified by Owner during the separately authorized
deployment, not on production as a Coder test.

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
