# CAPTIVPORTAL — SSR-01B-2
## Tech Lead → Chief Architect: Narrow admission decision / recovery budget and live-socket readiness

**Date:** 2026-10-15 (Asia/Baku)  
**Author/implementation owner:** CaptivPortal Tech Lead  
**Disposition:** `SSR-01B-1=HOLD; REQUEST SSR-01B-2 ARCHITECTURE AMENDMENT`  
**Architectural basis:** `SSR-01 ADR v1 FINAL` + `SSR-01B Chief Architect Amendment v1 FINAL`; SSR-B01…B05 and gates G0…G4 remain binding.  
**Operational boundary:** production observation freeze. No production edits, restarts, capture faults, systemd changes or Git publication performed.  
**Action requested:** Chief Architect resolve **B2-Q01–B2-Q04**. The Tech Lead will thereafter finalize a single scope-limited Coder TASK without another architecture round if within the accepted amendment.

## 1. Direct answer: why Tech Lead cannot yet issue Coder implementation GO

The candidate `fingerprint-sensor.service Wants=fingerprint-suricata.service`, retaining Suricata's `After+BindsTo+PartOf`, **does** reattach Suricata in the Lab after a Sensor `start`, `restart`, and SIGKILL→local auto-restart. Two local `ConditionPathExists=!<runtime-hold>` guards also protect pair-wide and Suricata-only maintenance from start jobs through NI-01 `Wants=Suricata` in the Lab.

**Blocking negative case:** Sensor `Type=simple` becomes `active` *before* EVE Unix datagram receiver binding. Existing Suricata `ExecStartPre` checks only `test -S`; a stale unbound socket inode passes that test. A live Unix datagram `connect()` correctly refuses stale socket, but if live socket remains unavailable longer than the unit start deadline, `ExecStartPre` fails on the systemd deadline and `Restart=on-failure` requeues more attempts. Production effective `TimeoutStartUSec=90s`, internal `timeout 1830`, and `RestartSec=30s` are incongruous. This is the exact case SSR-B04 separates into `SSR-01B-2`, forbidding Tech Lead from changing timeouts or numerical budgets under SSR-01B-1. Prior amendment also disallows unbounded reattach or restart storms.

This is **a reproduced negative lab mechanism**, not a claim that the real production Sensor/Suricata has already failed. Therefore `SSR-01B-1 G2/B04 != PASS`; Coder implementation GO would violate the architect's explicit admission condition.

## 2. Verified evidence (separate source facts, live effective units, Lab measurements)

### 2.1 Production read-only Owner-provided manifest

- Target Ubuntu `systemd 249 (249.11-0ubuntu3.22)`.
- Checkout HEAD `7e84bc563f1b6dd3d72da66ae25849d9a7d96540`, TREE `ea664b1d49ace86fc8a0c4ab2fc52945531e574a`. **Checkout does not prove all running process artifact IDs**.
- Fingerprint Sensor: `Type=simple`; `Restart=on-failure`, `RestartUSec=30s`, `TimeoutStart=90s`, `TimeoutStop=20s`, `StartLimitBurst=5` / `StartLimitInterval=10s`; installed `Wants=tmp.mount`, `After=captive-portal.service`. `network-attribution.conf` and `zz-spool-recovery.conf` drop-ins present. The sensor unit does not currently `Wants=Suricata`.
- Fingerprint Suricata: `Type=simple`, `BindsTo=Sensor`, `PartOf=Sensor`, `After=Sensor`; `Restart=on-failure`, `RestartUSec=30s`, `TimeoutStart=90s`, `StartLimitBurst=5` / `StartLimitInterval=10s`; `ExecStartPre` has `/usr/bin/timeout 1830 /bin/sh -c 'until test -S ...; do sleep 1; done'`.
- NI-01: `Wants=Suricata` and `After=Suricata`. Existing upstream NI start transaction therefore matters for planned stop semantics.
- GitHub blobs for `deploy/device-fingerprint/fingerprint-sensor.service`, `deploy/device-fingerprint/fingerprint-suricata.service` and `app/device_fingerprint_sensor/cli.py` were verified identical between Architect review commit `84b80376...` and checkout commit `7e84bc56...`. **Actual complete `systemctl cat` / secret-safe installed-unit diff, runtime loaded-artifact ID, and all reverse dependencies are still outstanding G0 evidence**.

### 2.2 Isolated Ubuntu 22.04 WSL Lab, **exact same systemd build 249.11-0ubuntu3.22**

Temporary mock units under `/run/systemd/system`, unrelated to CaptivPortal production, were stopped and removed after each test; no Omada, live SPAN or production databases involved.

| Test | Observation | Verdict / limit |
|---|---|---|
| Sensor→Suricata `Wants`, with original reverse `After+BindsTo+PartOf` | Cold start `active/active`; Sensor `restart` restarted Suricata (PID changed); stop both, then start Sensor reactivated Suricata; Sensor SIGKILL→autorestart returned both | **PASS** for mocked unit/job semantics on systemd 249 |
| Suricata SIGKILL when Sensor stays running | Sensor PID unchanged `29235→29235`; Suricata PID `29236→29242`, both active | **PASS** for isolated restart |
| Pair-wide hold and simulated NI-01 `Wants=Suricata` | NI mock remained active; guarded Sensor and Suricata both `inactive` | **PASS** for local `ConditionPathExists` test fixture |
| Suricata-only hold during NI start and Sensor restart | Sensor active; Suricata remained inactive; controlled resume returned both | **PASS** for local condition guard fixture |
| Real AF_UNIX SOCK_DGRAM socket appears 3s after `Type=simple` active | After ~1s Sensor active/Suricata `activating`; after ~5s both active and bound socket present; same sequence after Sensor restart; last Suricata result success | **PASS** for equivalently modeled EVE socket start, not real Suricata EVE health |
| Stale socket inode | `test -S` returned true for bound-and-closed pathname, while AF_UNIX datagram `connect()` failed | **FAIL** of present pathname-only readiness |
| Socket remains unavailable, shortened Lab start budget | `ExecStartPre` waiting beyond systemd start deadline resulted in timeout; for 3s deadline and 1s restart cadence after 9s `NRestarts=2`, Suricata `activating` | **FAIL / unresolved** for bounded repeated recovery; compressed values demonstrate mechanism, not production incidence or production restart rate |
| Existing production 90s vs shell 1830s | Unit values read-only verified. Actual full-duration 90s failure/slow-disk/performance path **not executed** | `SSR-01B-2` decision needed; numerical remedy not inferred |

**G1/G3 gap:** no actual Suricata 8.0.6, kernel capture, EVE throughput/heartbeat, production-like device health transition or source-gap/physical HDD profile was exercised in this mock. Never claim end-to-end production readiness, no data loss, or full R05 PASS.

## 3. Minimal bounded implementation design candidate — **not yet authorized to implement**

- Scope only `deploy/device-fingerprint/fingerprint-sensor.service` and `fingerprint-suricata.service`, local tests/fixtures and deployment runbook; no Core, NI-01, Evidence, Fingerprint app runtime, DB, new service, daemon or global orchestrator.
- Sensor may softly pull in Suricata with `Wants=`. Preserve reverse Suricata `After+BindsTo+PartOf`; no Suricata-to-Sensor failure propagation beyond existing arrangement.
- Two **explicit operator-controlled volatile** `/run` hold states (one pair-wide, one Suricata-only), evaluated by systemd `ConditionPathExists=!…`, prevent newly enqueued start jobs under maintenance, including NI `Wants`. Hold file must be created **before** stop; remove only at explicit resume. `ConditionPathExists` is not a guarantee against already-running units; separate stop action mandatory. Volatile hold is cleared at reboot; this must be explicitly documented, not silently promised persistent.
- Replace pathname-only evidence with an independently live AF_UNIX datagram connect probe (or Architect-approved stricter non-mutating ownership proof) before Suricata start. Do not send bogus EVE datagrams or infer functional TLS/QUIC source-health from successful connect. Sensor's preflight and source-health remain authoritative; external probe alone cannot prove full capture health.
- Recovery wait/retry budget, evidence of stop/restart storms, and possible adjustments to `TimeoutStartSec`, `RestartSec`, `StartLimit*` remain **outside SSR-01B-1** until the decision below.

## 4. Chief Architect — only decisions required

**B2-Q01 — Retry/timeout contract.** Does a unit with bounded individual `ExecStartPre` waits but indefinitely repeating `Restart=on-failure` after each `TimeoutStartSec` violate SSR-B02/B04? If yes, approve `SSR-01B-2` as a *narrow* extension to permit a measured and finite local retry/start-limit policy, including target-version behavior and reset/resume rules. If no, define a specific admissible operational bound/monitoring criterion for unavailable socket without changing values speculatively.

**B2-Q02 — Budget alignment.** Authorize research-driven changes to Suricata's effective 90s unit startup budget versus `timeout 1830` socket wait **only in SSR-01B-2**, with measured worst-case and HDD/boot trade-offs. No hardcoded budget is proposed for approval without data. Clarify whether necessary changes to both wait and unit timeout are allowed in existing two service templates, or require a standalone amendment.

**B2-Q03 — Live socket proof without new helper.** Confirm whether a **non-sending AF_UNIX SOCK_DGRAM `connect()` probe**, combined with Sensor unit state and existing runtime-owned protected socket path, is sufficient to block *stale inode* reattach within the systemd-local model, while actual EVE heartbeat/source-health still independently gates usable status. If actual receiver PID ownership must be established by the unit's pre-start guard, specify allowed unit-only proof (under `User=suricata` cross-user `/proc` permissions) or grant a narrow implementation scope exception. No new privileged app API or D-Bus/polkit escalation.

**B2-Q04 — Boundaries of research-only Lab admission.** Confirm that mock target-version process/socket tests establish **systemd behavior only**, with a subsequent required non-production actual Sensor+Suricata (or independently QA-approved faithful EVE fixture) integration and latency/source-health/performance gate before normal publication. If the Lab lacks capture interface/safe NIC, define explicit approved substitution; no production crash injection.

Requested decision format: `SSR-01B-2: ACCEPT (limits and scope) / MODIFY / HOLD`, response to B2-Q01…Q04, any allowed scope for numerical timeouts and readiness proof, condition for later `SSR-01B-1` Coder GO. **Do not ask Coder to decide architecture.**

## 5. Tech Lead next sequence

1. Owner forwards **this document only** to Chief Architect for the narrow B2 amendment. Existing architectural decision for bounded local reattach stays accepted; no new broad design round.
2. Tech Lead records exact approved amendment; runs remaining measured mock/faithful EVE/readiness and retry-bound tests, obtains sanitized installed manifests if still necessary.
3. Tech Lead issues the ready **conditional Coder TASK** (separate draft prepared in parallel) only after the approved G0/R05 pre-code gates are PASS; Coder changes allowed repo templates/tests/runbook only.
4. Official Central Lab + independent QA, exact candidate TREE, Owner controlled publication; installation/restarts remain separately Owner/SysAdmin authorized after observation freeze.

**Machine disposition:** `ARCHITECT_REVIEW_REQUIRED=YES; CODER_IMPLEMENTATION_GO=NO; PRODUCTION_CHANGE=NO; LAB_MOCK_MECHANICS=PASS; LIVE_SOCKET_NEGATIVE=FAIL; SSR-01B-2_DECISION=PENDING`.
