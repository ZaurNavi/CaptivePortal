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
Suricata capture interface, BPF, sensor socket path and TLS/QUIC output remain unchanged.

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

## Issue #244: raw Sensor site filter (repository implementation only)

The tracked `raw-capture.bpf` is deliberately byte-frozen as a legacy
`192.168.8.0/22` sample. For any other explicitly approved scope, use the offline
renderer with the exact `DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS` startup value;
do not edit Python or introduce a second environment variable:

```sh
python -m app.device_fingerprint_sensor.bpf_cli render --guest-cidrs 10.50.0.0/19
python -m app.device_fingerprint_sensor.bpf_cli verify --guest-cidrs 10.50.0.0/19 --artifact /absolute/staged/raw-capture.bpf
```

These commands print or verify only; they do not install files, enable capture,
open sockets, access credentials, or change services. The approved operator's
separate installation procedure must provision the rendered bytes at the fixed
`/etc/captive-portal/device-fingerprint/raw-capture.bpf` path: root-owned regular
single-link file, no group/world write, and root-owned nonwritable-by-group/other
directory chain with no symlinks. Read permission must permit the Sensor process
to read it. Only exact ASCII expression or expression plus one LF is accepted;
do not use a Windows CRLF text writer. A wrong or missing artifact fails closed.
The runtime performs bounded descriptor-based validation and never installs it.

DHCP's global UDP 67/68 branch remains unchanged; TCP SYN without ACK uses only
the parsed source networks. Protocol-zero socket creation avoids an unfiltered
receive window before verified BPF attachment and selected-interface activation.
No systemd or Suricata template is changed here. Suricata HOME_NET/BPF/interface
alignment remains separate Issue #243 work; raw-capture success alone is not a
complete cross-site deployment gate. Preserve nonempty-spool scope/identity rules.
No .202/.99 service, source copy, restart or activation is authorized by this task.
