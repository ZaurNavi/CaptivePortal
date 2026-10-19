# TASK-QIO-05-SYSADMIN-P0 — Fingerprint Evidence + Sensor matched I/O attribution

**Owner:** Optimization Tech Lead  
**Executor:** SysAdmin  
**Phase:** P0 read-only causality research, NO optimization and NO production mutation.  
**Priority:** high due measured I/O spikes (FP Evidence 6,750 writes, Sensor 2,691 over LIVE1 120s). **NOT** an incident diagnosis or authorization to disrupt a service.

## Goal

Prove which exact **files / durable operations / workload classes** account for unusual `fingerprint-evidence.service` and `fingerprint-sensor.service` guest block writes, and which correlate with host physical write pressure. Separate legitimate positive evidence inserts from duplicate retries, NI-02A authoritative DHCP/network attribution, spool transport, health/telemetry, checkpoint/retention and other writers. Compare same-mode runs only.

## Admission and STOP

1. Before work, confirm the current date/time, guest/host load, guest I/O PSI (`some`, `full`), host disk await/busy, service active state and restart counters. **Default P2 safe pressure gate:** two 10–15s apart samples each `full avg10 <=5%`, `some avg10 <=20%`; otherwise **STOP/HOLD**, return counters only. The earlier Owner high-pressure override applied to the finished QIO-01J study and does **not** extend to this TASK.
2. If CPU/PSI/latency sharply worsens, a command stalls, or source-health/ingest/storage reports faults: **STOP**. No aggressive retries or high-load longer profiling. Read-only metadata and short passive windows first. No process freeze, `strace`, `perf`, `iotop` installation, Python imports of production DBs, full DB scans, SQL pragmas on a live RW connection, `lsof` across the host, `VACUUM`, WAL checkpoint, or permission changes.
3. Preserve per-service permission and secrets; commands must neither print raw payloads nor IP/MAC/site/client/producer tokens, payload JSON, headers, TLS identity, paths outside their expected known service roots. No raw journal export.

## Required evidence if gate PASS

**A — Exact authority and file ownership:** read-only `/proc/<service MainPID>/fd` symbolic link targets, `systemctl show` identity (MainPID, NRestarts, ExecMainStartTimestamp, unit name), loaded artifact SHA/tree if already exposed in authorized sanitized telemetry, and existing deployment **nonsecret** config. Confirm actual FP Evidence DB/WAL/shm and Sensor spool/NI-02A paths, directories and which PID holds handles. Do not interpret `.sqlite3` file size or large freelist as evidence of write rate. Report unknowns, don't assume defaults equal deployed settings.

**B — Two matched 120-second sample windows**, only if safe and low-impact. Sample monotonically counters at same clock boundaries guest `/proc/diskstats` (`/dev/vda`) + guest cgroup `io.stat` for evidence, sensor, journald, capture/related workers; host `/dev/sda` diskstats + QEMU parent `/sys/fs/cgroup/machine.slice/*Ubuntu*.scope/io.stat` and host-local journald. Capture per-window `wios`,`wbytes`, guest/host await,busy and PSI. Do not add nested `252:0` + `253:0`; don't sum cgroup counts into claimed physical disk IOPS. Record uncertainty/time offsets and whether windows represent quiet, normal, retry/catch-up or busy processing.

**C — Full but narrow journal event-count matching** for each exact sample window: privileged `journalctl` with bounded time (`nice/ionice/timeout`) and half-open event timestamps; on-host aggregation ONLY. For Evidence aggregate `device_fingerprint_ingest_completed` by `inserted>0`/`inserted=0`, `received`, `inserted`, `duplicate_noop` *summed as counts* (exclude producer ID and event/request identity); source-health-completed similarly, retention, rejection, storage errors; Sensor aggregate delivery/retry, source health transitions, NI-02A faults/coverage and packet counts only if available as sanctioned telemetry. Mark whether instrumentation counts represent every successful request or partial. On INFO-only entries, preserve error-like semantics. Export only aggregates, not any raw MESSAGE/payload/identifiers.

**D — Outcome and risk:** for each window provide `A` vs `B` real positive evidence rows, number of duplicate-only batches, Sensor attribution/source transitions, `wios/wbytes` service counters, relative changes and matched physical disk stats. Explain whether Evidence high I/O aligns with positive ingest *without assuming causality*. Review existing health/readiness and backlog indicators through bounded read-only supported interfaces **only if already admitted**; never invoke unbounded SQL or a slow deep check. If signals fail, mark UNKNOWN, do not repair.

## Handoff schema

`RUN_MODE`, `DATE_AZST`, `SOURCE_LOADED_SHA/TREE|UNKNOWN`, `PRESSURE_GATE=PASS|HOLD`, `OWNER_OVERRIDE_FOR_THIS_TASK=NO`, `FILES_TO_WRITERS`, `METRICS_W1/W2`, `NEW_ROWS`, `DUPLICATE_ONLY`, `SENSOR_NI02A`, `HOST_QEMU_PHYSICAL`, `EOF/JSON_ERRORS`, `HEALTH`, `NO_PRODUCTION_MUTATION=YES`, `LIMITATIONS`, `RECOMMENDED_NEXT_PROBE`. Clean aggregate markdown and optionally machine-readable aggregate JSON. If pressure gate HOLD, send short report **without** additional full journal scans.

**No commit / PR / merge / deploy.** Production service modifications forbidden, including mode/retention/synchronous/capacity changes. If access cannot meet the gate, return HOLD for Tech Lead decision.
