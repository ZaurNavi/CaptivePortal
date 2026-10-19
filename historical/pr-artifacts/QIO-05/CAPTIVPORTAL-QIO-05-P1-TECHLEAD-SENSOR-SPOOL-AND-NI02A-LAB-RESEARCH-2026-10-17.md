# CaptivPortal — QIO-05 P1 / Tech Lead independent source + LAB research

**Дата:** 2026-10-17, Asia/Baku  
**Роль:** Performance & Optimization Tech Lead  
**Статус:** `RESEARCH_PASS / IMPLEMENTATION_HOLD / PRODUCTION_HOLD`  
**Граница:** No application code edits; no production mutations; no permission or SQLite durability changes.

## 1. Цель и последовательность

После принятого QIO-05 P0 (128 PASS Linux + 128 PASS Windows; 112 успешных лабораторных запусков; duplicate-only Evidence не создаёт измеренных request DB/WAL write bytes) исследовать уже существующие источники write-amplification внутри `fingerprint-sensor.service`, не приписывая guest writes физическому HDD без совпадающих измерений.

Источник производственных цифр — `QIO-01J-SYSADMIN-FINAL-FULL-ATTRIBUTION-2026-10-16`: в двух отдельных 120-секундных LIVE окнах Evidence wios 6750/1254, Sensor wios 2691/650, guest `/dev/vda` 111.50/72.26 write IOPS, host `/dev/sda` 127.39/88.74 write IOPS. Этот документ **не** содержит file-attributed per-DB write bytes или частот/размеров ingest-транзакций в тех же окнах. `PRODUCTION_PHYSICAL_HDD_SAVINGS_BOUND=NOT_QUANTIFIABLE`.

## 2. Production safety preflight / STOP

Remote Desktop Commander → existing approved SSH profile `Ubunt` → Ubuntu VM. Пассивно проверены только `date -Is`, `uptime`, `/proc/pressure/io`, `systemctl is-active`. 

| AZST | load 1m | IO some avg10 | IO full avg10 | Essential units |
|---|---:|---:|---:|---|
| 2026-10-17 01:05:09 | 2.74 | 15.78% | **11.66%** | fingerprint-evidence, fingerprint-sensor, captive-portal = active |
| 2026-10-17 01:05:21 | 2.94 | 13.91% | **11.39%** | unchanged during short check |

Contract pressure gate `full avg10 <=5%` in **both** samples was not met; `PRESSURE_GATE=HOLD`, `OWNER_OVERRIDE_FOR_THIS_TASK=NO`. NO extended production journal scans, proc FD inventory, DB connection/query, profiler, service restart, runtime config read or host metrics were performed. No claims about current production Wave-2 flag values.

## 3. Independent source review (same blobs pinned QIO05 base and main@cd83c3e)

Source Git blob SHA preserved across `516abc7...` → `cd83c3e...`:

| Source | Git blob SHA |
|---|---|
| `app/device_fingerprint_sensor/spool.py` | `a9a4c8146a228c6c285412b1feb1c0bd53f0d8ad` |
| `app/device_fingerprint_sensor/ingress_coalescer.py` | `3cb8f99cac426664c103196566668523251c7248` |
| `app/device_fingerprint_sensor/config.py` | `3c6fbcc23314386483dfee92475c4d9b4834e0c3` |
| `app/network_attribution/dhcp_authority.py` | `9fba287cbddb0f45516086ae9330b23d5372a133` |
| `app/network_attribution/repository.py` | `7f5795d86c5b368f74fb09d04f69d63a46f3da0e` |

**Finding S1 (spool):** `SensorSpool` is SQLite DELETE-journal + `synchronous=FULL`. The legacy `spool.enqueue([event])` path can produce one durable SQLite transaction per submission. `IngressCoalescer` already exists; its flag `DEVICE_FINGERPRINT_SENSOR_IO_INGRESS_COALESCE_ENABLED` is parsed from env with default **false**. It accumulates evidence in a pre-durable memory window of max 32 events / max 100ms / max 262144 serialized bytes; source-health is an immediate barrier; the actual spool stays the sole writer. A successful `submit()` can precede the actual durable spool insert. Activation is a substantive crash/ordering/reliability decision, **NOT an innocent logging toggle**. Current production flag is UNKNOWN.

**Finding S2 (NI-02A):** `DhcpAuthorityRecorder.poll()` advances source coverage `verified_through` at roughly 1-second intervals when enabled; `record_frame()` can independently call `confirm_capture()` for each actual DHCP authority frame before `record(fact)`. Repository uses WAL + `synchronous=FULL`; `confirm_capture()` checks current coverage and updates `verified_through` in a real separate transaction. `NetworkAttributionReadService` checks exact event-time against durable `verified_through` and returns unavailable when coverage is insufficient. Lowering cadence or combining authoritativeness transitions can change attribution/unknown/freshness guarantees; no code change is approved. `retain()` plus bounded WAL maintenance is scheduled roughly every 60 s, with its own correctness constraints.

**Finding S3:** Empty spool on earlier quiet baseline does not prove an absent active write workload at other times. Production spike Evidence/Sensor may be legitimate new events, spool enqueue+ack, NI-02A heartbeat/facts, checkpoint, retention or backlog. No causal file-to-wios mapping is yet proven.

## 4. Independent reproducible laptop LAB S1: NI-02A watermark

Isolated script on authorized notebook (outside source repository):

`C:\CaptivPortal-Lab\tmp\qio05-ni02a-confirm-probe-20261017.py`

Uses exact current `NetworkAttributionRepository`, synthetic Site/source, temp SQLite DB, fixed UTC clock, no prod data; repository initialize and coverage seed before measured phases. `journal_mode=wal`, `synchronous=2 (FULL)`, `wal_autocheckpoint=1000`.

| Phase | BEGIN/SELECT/UPDATE/COMMIT | SQLite total_changes delta | WAL size delta |
|---|---|---:|---:|
| 60 timestamps advancing one second | 60 of each | +60 | **+247,200 bytes** |
| 60 updates with exact same timestamp | 60 of each | +60 | **0 bytes** |

This falsifies a naive claim that exactly-equal watermark updates necessarily write WAL: SQLite itself avoided WAL growth under this fixture. It does not prove zero CPU/locking/SHM activity, nor physical disk IOPS of a deployed Sensor. **Advancing** authoritative coverage produces real WAL growth, but changing frequency requires architectural admission.

## 5. Independent reproducible laptop LAB S2: SensorSpool single vs bounded group

Script, source-unmodified:

`C:\CaptivPortal-Lab\tmp\qio05-spool-synthetic-syscalls-20261017.py`

WSL2 Ubuntu22.04 laptop NVMe SSD; temporary synthetic spool; 100 event IDs, known in-range UTC observation timestamps, same event document class. Both arms use `io_stale_purge_gate_enabled=True` and SQLite DELETE journal + FULL; only transaction grouping differs. Groups respect existing `MAX_COALESCED_ROWS=32`. Direct `SensorSpool.enqueue` is measured, **not** the asynchronous `IngressCoalescer` scheduling/barrier/crash semantics. No natural traffic/physical HDD observation.

| Measurement | 100 one-event enqueue calls | 4 bounded calls (32+32+32+4) |
|---|---:|---:|
| Persisted rows and distinct IDs | 100 / 100 | 100 / 100 |
| `strace`-instrumented elapsed for enqueue arm | 1.293 sec | 0.060 sec |
| Independent `strace -c` repeat elapsed | 1.115 sec | 0.061 sec |
| Total `pwrite64` calls including **startup+close** | **2614** | **126** |
| Total `fdatasync` including startup+close | **404** | **20** |
| Total `unlink` including startup+close | **102** | **6** |

The count comparison is end-to-end **whole synthetic process** (including equal init/close), not a per-transaction syscall profile; no exact file-attributed physical write bytes are claimed. ~95% fewer counted write/sync syscalls in this bounded synthetic scenario is a meaningful **LAB candidate** only, not a promise of host-HDD IOPS savings, nor evidence that coalescer ON is safe.

## 6. Ranked hypotheses, safety decision, and next dependency

1. **Highest actionable LAB candidate**: already-coded, default-OFF **Sensor evidence pre-durable coalescer**; quantified request-level transaction cost under direct spool fixture. Critical unresolved **architecture gate**: are any pre-durable evidence losses on abrupt termination acceptable, and what exact accepted/queued/durable contract holds? Do not change startup flags until Chief Architect/Owner decision and real runtime config attestation.
2. **Authoritative steady write floor**: NI-02A `verified_through` roughly 1Hz, FULL WAL. Lab confirms WAL growth, but attribution freshness is safety-critical and this write floor alone cannot explain the observed Evidence 6750 guest writes. Defer any rate change to a **separate** architecture question after better production attribution.
3. **Evidence direct new data**: QIO05-P0 demonstrates 100 positive rows and WAL cost; duplicate-only request has zero measured DB/WAL write bytes. No rerun of duplicate DB write optimization.

`ARCHITECT_REQUIRED_FOR_COALESCER_ACTIVATION=YES` because it changes pre-durable acceptance boundary. One bounded Chief Architect request prepared separately. `CODER_IMPLEMENTATION_GO=NO`, `PRODUCTION_GO=NO`. If architecture refuses lossy pre-durable evidence buffering, archive candidate and investigate safer transaction batching only where inputs are already durably staged.

## 7. Explicit nonclaims / follow-up gates

No reader claims about production loaded SHA, `IO_INGRESS_COALESCE_ENABLED` runtime value, disk file attribution, spool queue at 01:05, guest write savings from enablement or physical HDD savings. Relevant future checks, only after pressure gate: safe nonsecret runtime flag attestation; matched guest/host cgroup and per-file attribution **if available without invasive tracing**; spool in/out throughput and `acknowledge`/source-health rates; held reader and crash/replay non-loss tests in Lab; rollback to OFF under explicit Owner GO. The existing 2026-10-16 Owner high-I/O override did not carry forward.
