# CaptivPortal — TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1
## TechLeadJR independent review: T05 architecture HOLD
**Date:** 2026-10-15 (Asia/Baku)  
**Authority:** Chief Architect contract v1 FINAL / independent TechLeadJR QA  
**Final result:** **NOT ACCEPTED; COMMIT/PUSH/PR/MERGE/DEPLOY HOLD**

### Immutable chain of custody
- Baseline `main` HEAD: `84b80376b13002d435be28eec98b91b9cbf71c63`
- Baseline TREE: `fda2f2dad7c1f9c89d383ef0bef63f8aebfc93b8`
- Coder dirty, uncommitted candidate TREE independently reconstructed using a temporary Git index: `08cab06eac76764b932c5ce955e30959f9aeaf62`. Matches Coder handoff.
- 15 changed files; only three production Python paths: `app/device_fingerprint_sensor/config.py`, `app/device_fingerprint_sensor/capture.py`, `app/device_fingerprint_portal/config.py`; `git diff --check`: PASS.
- Uploaded handoff patch: 67,896 bytes, SHA256 `2f5a578a658bf7097207ad834da29bb6024df53e21039fbd1672f9da8ec0dfdd` (verified). A fresh `git diff HEAD --binary` serialization of the dirty worktree produced 66,906 bytes, SHA256 `dc8b2183ec31a83e6c3acf0993095709dfdfcc7b0664c629d4244364e981d76c`. The Git TREE agrees; textual patch streams differ. A fresh unambiguous final patch/hash must be supplied after remediation.

### Independent focused test results
On the preserved **same dirty candidate**, WSL Ubuntu 22.04 / Python 3.10.12, an independent 11-file focused suite of both producer modules, configuration, Sensor preflight and guest-auth isolation returned **265 PASS / 2 FAIL** (2.42s):

- `tests/device_fingerprint_sensor/test_deploy_preflight.py::test_T05_selected_bridge_or_bond_must_be_rejected[bridge]`
- `tests/device_fingerprint_sensor/test_deploy_preflight.py::test_T05_selected_bridge_or_bond_must_be_rejected[bonding]`

Both fail because no `SensorPreflightError` is raised. Additional reproducibility run of those exact two node IDs: **2 FAIL** (0.66s).

**Test-harness caveat:** An initial independent invocation had a Windows→WSL line-ending contamination of the `--basetemp` path (`CR` character), yielding 10 artificial failures in path-validation tests. After correcting the invocation *without editing any Coder code or tests*, those 10 failures vanished. Only the two T05 failures above are substantive.

### What the blocker means
`InterfacePreflight._validate` previously denied any selected interface other than `enp8s0`. The authorized patch deletes only that fixed-name check. This permits a configured alternate interface whose Linux `/sys/class/net/<selected>/bridge` or `/bonding` directory exists (including virtual master itself), provided its other synthetic checks pass. The existing `<selected>/master` defense catches interfaces **enslaved** to a master but does not catch a selected bridge or bonding **master**.

Chief Architect v1 formally authorizes **only removing the hardcoded interface-name denial**, not adding a new preflight guard; TechLeadJR §5 also states `no master/bridge/bond`. There is a contract tension. TechLeadJR cannot authorize an additional production-code guard without narrow Architect approval. Do not remove or xfail the two negative tests to obtain a green gate.

### Requested Architect amendment (one-file-only, fail-closed)
Permit `app/device_fingerprint_sensor/capture.py::InterfacePreflight._validate()` to reject a selected interface where either `<sys_root>/class/net/<selected>/bridge` or `.../bonding` exists **or is a symlink** (including dangling symlink). Keep existing selected `<selected>/master` check, interface `up`, zero L3, route, forwarding, DHCP, NetworkManager, AF_PACKET, frozen BPF and all existing behavior. No other production-file scope expansion, model, config, systemd, Suricata, NI, SQLite, source admission, producer or production actions.

Only after written Architect acceptance: return Coder to perform the minimum defensive change and add/retain alternate-NIC valid/invalid and sysfs-directory/symlink tests, run focused suite with clean temp paths, supply a fresh exact TREE and patch SHA. Independent TechLeadJR must then run the relevant Linux and official Windows/other release gates and review TLS/receiver-source security before any publication GO. The task-specific DEPLOY-CONFIG-01 exception is NOT inherited.

### Decision
**TECHLEADJR = HOLD / ARCHITECT AMENDMENT REQUIRED**  
**CODER = CORRECTION PLAN ONLY UNTIL AMENDMENT APPROVED**  
**COMMIT / PUSH / PR / MERGE / PRODUCTION / SOURCE ACTIVATION = NO**
