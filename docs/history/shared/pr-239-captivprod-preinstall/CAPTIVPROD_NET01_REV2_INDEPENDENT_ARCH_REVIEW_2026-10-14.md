# CAPTIV-PROD — NET-01 Implementation-03 / Part A Rev2
## Independent Architect Code Review — 2026-10-14

**Artifact reviewed:** `TASK-CAPTIVPROD-NET01-IMPLEMENTATION-03_PART-A_REV2(1).zip`  
**ZIP SHA-256:** `35a5b499a7df2b68e38e73d6a80abc309631a77855a6df5bfcf42d227e4214d3`  
**Scope:** Offline review of supplied archive, no access to/changes on `captiv-prod`.  
**Verdict:** `PART_A_REV2=REVIEWED_WITH_P1_FINDINGS`; `PART_B=HOLD`; `OWNER_GO=NOT_REQUESTED_FOR_ACTIVATION`.

## Verified offline

- ZIP integrity test successful; paths inspected before extraction; `MANIFEST.sha256` reports OK for all 20 tracked files.
- Executed supplied regression scripts locally: firewall `1 positive / 15 negative` PASS; Docker identity `2 positive / 8 negative` PASS; watchdog decision `1 positive / 4 negative` PASS. These are fixtures/mocks, not live network or systemd acceptance.
- `bash -n` for all `.sh` scripts and Python compilation for scripts/tests PASS.
- Reviewed `compose.current.yaml`, `compose.proposed.yaml`, `compose.diff`, firewall scripts, identity guard, runtime watchdog/stop, systemd units, evidence and rollback plan.
- Existing NPM, Docker, firewall, Omada, old Portal, Cisco and routing **not modified** by this review. Current live runtime not independently verified.

## P1-01: Unprivileged app ExecStartPre cannot execute root-level guard

**Evidence:** `systemd/captive-portal-net01.drop-in.conf:9–13` defines `ExecStartPre=/usr/bin/python3 /usr/local/libexec/captiv-net01/net01-verify.py --all` without root privilege override. The intended main app service runs as `User=captivportal` per Portal installation TASK. `firewall/net01-verify.py:72–145` uses `docker network inspect`, `docker inspect`, `docker image inspect`, `iptables -S`, and `ip6tables -S`; also checks a root-owned 0700 HOLD directory at lines 160–165. On a default host, the app identity will not access Docker socket or traverse `/var/lib/captiv-net01`.

**Impact:** deterministic startup HOLD despite valid configuration; granting service user access to Docker socket is an unacceptable root-equivalent workaround.

**Required:** Architect-reviewed privileged prestart gate (e.g. root-only separate unit, or explicit narrowly scoped systemd privileged prestart command under root-controlled unit). Application process must retain an unprivileged `User`, no Docker-group membership and no app Docker-socket access. Verify permission model and real unit startup in staging.

## P1-02: Reverse watchdog dependency does not guarantee Flask stops when watchdog stops

**Evidence:** `systemd/captive-portal-net01.drop-in.conf:3–7` sets `Wants=captiv-net01-watchdog.service` on Flask; `systemd/captiv-net01-watchdog.service:3–7` sets `BindsTo=captive-portal.service`, `PartOf=captive-portal.service` on watchdog. These dependencies stop watchdog with Flask, not necessarily Flask with watchdog. `OnFailure` triggers on failed watchdog state, not a deliberate `systemctl stop`/service suppression. The package acknowledges manual watchdog suppression at `README.md:51`, but backend may remain serving.

**Impact:** missing runtime drift protection while backend stays bound. With host INPUT policy ACCEPT, this is an operational security gap.

**Required:** A fail-closed supervision/lifecycle contract such that watchdog absence, failure or intentional stop while Flask runs causes Flask stop/HOLD, without unit ordering cycles or unsafe startup windows. Implement and test real systemd stop/failure scenarios in an isolated staging environment. Do not rely on `Wants` alone. Clarify handling of systemd watchdog cancellation while its own code requests Flask stop.

## P1-03: Rollback claims exact-match removal but has no prior guard validation

**Evidence:** `firewall/net01-fw-rollback.sh:14–18` directly runs `iptables -D/-F/-X` and `ip6tables -D`. It only checks that service is inactive and port is not listening (lines 5–13), and does not call strict firewall checker, although `TEST_AND_ROLLBACK_PLAN.md` says non-matching firewall state should cause HOLD/manual security review.

**Impact:** could flush/rewrite unexpected or drifted dedicated chain contents, losing diagnostic state and potentially deleting rules owned by other work, contrary to rollback's claimed fail-closed exact-state semantics.

**Required:** Verify exact installed rule/chain ownership and expected semantics **before deletion**; permit checking with HOLD latch present only in root-controlled rollback path, or use pre-recorded owner-specific state/atomically safe deletion plan. Reject drifted rules without mutation. Add offline tests for modified chain, modified hooks, partial install, and stale rules. Preserve fail-closed behavior and evidence.

## P2-01: Emergency watchdog and service stop are not covered by current tests

**Evidence:** `tests/test_runtime_offline.py` tests only `iteration()` and never `main()` / `net01-hold-and-stop.py` / actual systemd `OnFailure`. `firewall/net01-hold-and-stop.py:31–39` invokes `systemctl stop captive-portal.service` from a watchdog that is coupled with `PartOf=captive-portal.service`, which may cause watchdog termination mid-emergency action.

**Required:** Targeted offline/mock and isolated systemd integration tests for marker creation failure, stop timeout, SIGKILL fallback, watchdog unexpected exit, OnFailure, service restart suppression, real listener shutdown and post-stop port check. No disruption of existing NPM or active guest services.

## Accepted design elements / remaining gates

- Target path remains `NPM 172.18.0.2 → host bridge 172.18.0.1:18089 → Flask` as a **candidate approved architecture**, not a verified live deployment.
- Docker endpoint pinning proposed without network recreation; NPM container recreate is still expected and needs explicit Owner maintenance authorization. IP/MAC are not cryptographic container identities.
- Current dedicated IPv4 INPUT/IPv6 deny concept, exact-match firewall guard, root-owned sticky marker and separate TLS FQDN are directionally sound after corrections and live validation.
- `FLASK HOST/PORT` and `CAPPORT SITE_ID/PUBLIC_BASE_URL` changes must arrive via reviewed Git commit/tree with separate application gates.
- Live tests still required: root-only prestart; firewall enforcement/negative traffic; NPM→Flask connection; HTTP forwarded-header spoofing; watchdog drift/failsafe; Docker recreate/reboot; rollback; no regression to old NPM Portal, Nextcloud, VPN, Omada.
- `PART_B=NOT_AUTHORIZED`; no existing NPM Proxy Host may be modified; no new public Proxy Host yet.

## Requested Rev3 handoff

Provide full revised ZIP with updated manifest and explicit diffs; run offline regression and isolated systemd tests. Report `P1-01..03=PASS/HOLD`, `P2-01=PASS/HOLD`, record tested systemd privilege/ownership semantics. Independent re-review required prior to Owner GO.
