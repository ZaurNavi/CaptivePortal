# CAPTIVPORTAL — SSR-01B-1 / Tech Lead Target-Systemd Research Verdict R3

**Date:** 2026-10-15 (Asia/Baku)  
**Owner:** CaptivPortal Tech Lead  
**Governing decision:** `SSR-01B Chief Architect Amendment v1 FINAL` + `SSR-01 Chief Architect ADR v1 FINAL`  
**Status:** `RESEARCH ADVANCED; CANDIDATE IDENTIFIED; CODER GO=HOLD; PRODUCTION FREEZE`  
**Execution scope:** repository read-only and temporary systemd test services in the **dedicated Ubuntu-22.04 WSL laboratory**. Production provided information only through Owner-executed read-only `systemctl`/Git commands. **No production changes, restarts, faults or workload tests.**

## 1. Source and target baseline (confirmed)

| Authority | Verified fact | Qualification |
|---|---|---|
| Owner's production read-only systemctl report | systemd `249 (249.11-0ubuntu3.22)` | Target OS-level systemd version |
| Owner's production Git report | checkout HEAD `7e84bc563f1b6dd3d72da66ae25849d9a7d96540`, TREE `ea664b1d49ace86fc8a0c4ab2fc52945531e574a` | Checkout, **not proof of process-loaded Python artifact** |
| GitHub repository blob comparison at `84b80376...` versus `7e84bc56...` | `fingerprint-sensor.service`, `fingerprint-suricata.service`, `app/device_fingerprint_sensor/cli.py`, `docs/deployment.md` blob SHAs unchanged | Repository templates only; installed unit definitions may differ |
| Owner's live systemctl show | Sensor: `Type=simple`, `Restart=on-failure`, `RestartSec=30s`, `TimeoutStart=90s`, `TimeoutStop=20s`, `StartLimitBurst=5/10s`, `After=Core`, **no `Wants=Suricata`** | Installed Sensor ExecStart is venv Python, unlike repo template `/usr/bin/python3` |
| Owner's live systemctl show | Suricata: `Type=simple`, `BindsTo=Sensor`, `PartOf=Sensor`, `After=Sensor`, `Restart=on-failure`, `RestartSec=30s`, `TimeoutStart=90s`, socket wait `timeout 1830`, `StartLimitBurst=5/10s` | Installed Suricata effective entrypoints supplied in full via `systemctl show` |
| Owner's live systemctl show | NI-01 `Wants=Suricata` + `After=Suricata`; `StartLimitBurst=3/5min` | Starts of NI-01 can enqueue Suricata and indirectly Sensor |
| Dedicated laptop WSL Lab | Ubuntu 22.04 with **exact systemd 249.11-0ubuntu3.22** | Version parity demonstrated; functional EVE/application parity is **not** demonstrated |

## 2. Causal systemd tests on exact target release (WSL Lab only)

Used unique temporary test units under `/run/systemd/system`, e.g. `ssr01b249-sensor.service`, `ssr01b249-suricata.service`, `ssr01b249-ni.service`, launched as mock `sleep` processes. Unit cleanup and daemon-reload executed at test end. These are unit job-graph tests, **not** actual Sensor/Suricata packet capture.

Candidate under test:

- Sensor gains *soft* `Wants=Suricata` start pull-in, without `Requires`/`BindsTo` back onto Sensor.
- Suricata retains current `After+BindsTo+PartOf=Sensor`.
- Unit-native **volatile** `ConditionPathExists=!...` inhibits distinguish (a) full Sensor–Suricata pair maintenance and (b) Suricata-only maintenance. The pair condition appears on both units; Suricata-only condition appears only on Suricata.
- Marker paths were temporary WSL-only fixtures. Exact production marker paths, ownership and privileged operator procedure are **NOT approved**. Neither marker is to be introduced until an implementation/runbook task is admitted.

| Test on systemd 249 | Observed | Disposition |
|---|---|---|
| Cold start of mock Sensor + NI | `Sensor=active, Suricata=active, NI=active` | `PASS` **for mock process job graph** |
| Explicit restart Sensor | both active, Suricata PID changed `28399 → 28409` | `PASS` **for mock restart propagation** |
| Stop Sensor | `Sensor=inactive, Suricata=inactive` | `PASS` |
| Start Sensor after stop | `Sensor=active, Suricata=active` | `PASS` **for mock local reattach** |
| Kill Sensor main PID (`SIGKILL`), local auto-restart | `Sensor=active, Suricata=active` after bounded observation | `PASS` **for mock auto recovery** |
| Inhibit **entire pair** and start NI (which Wants Suricata) | `NI=active; Sensor=inactive; Suricata=inactive` | `PASS` for indirect-start prevention, mock only |
| Inhibit **Suricata only**, start NI | `NI=active; Sensor=active; Suricata=inactive` | `PASS`, mock only |
| Restart Sensor while Suricata-only inhibit active | `Sensor=active; Suricata=inactive` | `PASS`, mock only |
| Remove inhibit and controlled resume | both active | `PASS`, mock only |

**Critical rejected candidate:** one `ConditionPathExists` guard on Suricata alone fails pair-maintenance isolation: NI start left `Sensor=active, Suricata=inactive` despite an intended pair stop. This was observed in WSL Lab. Do not suggest that a Suricata-only guard protects the whole pair.

## 3. Readiness / timeout negative proof on exact release

- A test-created Unix datagram socket was bound and then closed **without unlinking** its pathname. `test -S <path>` remained `true` while the socket was absent from `/proc/net/unix`. **Socket-path existence is not proof of a live receiver or ownership.** This matches the Architect prohibition on treating `test -S` as functional readiness. This negative proof used a temporary independent lab socket, not the production EVE socket.
- A separate mocked `ExecStartPre=/usr/bin/timeout 1830 <wait-for-socket-script>` test had `TimeoutStartSec=4s` for rapid demonstration. With socket absent, `systemctl start` failed after **4 seconds** with `Result=timeout`. Therefore inner `timeout 1830` does not supersede the systemd service start budget. This was **scaled**: it does not claim a production 90-second failure was observed.
- The effective production budget remains `TimeoutStart=90s` versus inner socket wait `1830s`. The first start attempt **can be interrupted** if the socket is late. Do not change either number within SSR-01B-1 without the Architect's SSR-01B-2 decision and separate proof. Existing retry may recover; exact convergence, backoff and capture gap remain untested.
- The current Sensor is `Type=simple` and can become `active` before its EVE socket. No test above proves a live-Sensor-owned socket, actual Suricata EVE handshake, heartbeat or restored source health.

## 4. Admission gate ledger (mandatory Architect conditions)

| Gate | State | Why |
|---|---|---|
| G0 — installed version/graph parity | `PARTIAL` | exact version 249 proved, effective show/dependencies reported, repository file SHAs match; sanitized full `systemctl cat`, reverse-dependency manifests and exact loaded artifact identity not fully captured |
| G1 — positive reattach + causal EVE readiness | `PARTIAL / HOLD` | systemd job semantics PASS on version 249, but actual socket lifecycle, stale ownership, heartbeat and slow-socket full end-to-end unproven |
| G2 — negative maintenance/fault intent | `PARTIAL` | two volatile inhibit scenarios and NI Wants indirect start PASS in mock lab; crash loops, unit limits, unwanted auto-restart under prolonged faults, reboot semantics and privileged operator runbook unproven |
| G3 — Auth/data correctness/performance | `NOT RUN` | real Core/Suricata/Sensor/Evidence/NI integration, durable spool, source-health separation, CPU/HDD-equivalent metrics not run |
| G4 — release/rollback | `NOT RUN` | no candidate diff, no exact-tree independent QA, no accepted release gate or production rollout |

**Decision:** `SSR-01B-1 IMPLEMENTATION_ADMISSION=HOLD`, `CODER_IMPLEMENTATION_GO=NO`, `PRODUCTION_CHANGE=NO`.

## 5. Concrete next steps for Tech Lead (no action requested from Owner yet)

1. Prepare **isolated Lab fixture** with real Unix datagram EVE socket owner identity and staged creation; verify both fast and >systemd-start-budget cases without importing production credentials or initiating capture.
2. Prove live readiness of the *current Sensor-owned* socket and reject stale socket path. If solution requires new helpers/oneshot, application lifecycle change, privileged activator or new state beyond the approved volatile operational inhibit, **RETURN TO ARCHITECT** before Coder GO.
3. Prove bounded convergence or explicit failure with socket late, with `RestartSec`, `StartLimit`, no false ready; keep 90s/1830s `SSR-01B-2` separate.
4. Define exact safe pair-maintenance and Suricata-only maintenance procedure, its reboot expiration policy, fail-closed path permissions and cleanup/rollback. Current WSL `ConditionPathExists` mock result alone is not a production operational permit.
5. Request only any remaining sanitized **read-only installed manifest**, if needed, after reconciling to known effective state; do not expose secret env values. Do not request production stop/restart/fault injection during freeze.
6. Once all applicable G0–G3 pass, prepare scope-limited Coder TASK for repo-owned Sensor/Suricata templates plus test fixtures/runbook; Owner controls Central Lab official gate, Git publication/merge and future installation/activation separately.

## 6. Owner-facing takeaway

The specific `Wants` + local volatile pair/Suricata inhibit **works in mocked job-graph tests on the exact production systemd version**. It is not yet an accepted full solution: socket correctness, 90s/1830s mismatch convergence and end-to-end availability remain real admission blockers. No change to running CaptivPortal has been made.
