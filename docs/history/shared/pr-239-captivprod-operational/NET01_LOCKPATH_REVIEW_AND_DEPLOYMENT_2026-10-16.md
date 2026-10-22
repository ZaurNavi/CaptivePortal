# NET01 FINAL BASELINE — offline lock-path review and scoped deployment handoff

**Date:** 2026-10-16. **Scope:** Architect-authorized offline lock-path correction ONLY.
**Status:** NET01_LOCK_FIX=PASS (offline); NET01_OFFLINE_REGRESSION=196/196 PASS; NET01_FINAL_BASELINE=FROZEN AS OFFLINE ARTIFACT; NET01_READY_FOR_OWNER_GO=YES (conditional live preflight); LIVE_DEPLOYMENT=NOT_AUTHORIZED. 
**Source:** NET01_INTEGRATED_P1AB_APPROVED_OFFLINE(1).zip, sha256 `594ec49f486085a130ab741b669c830746129db42691907683db87dfca279808`.

## Exact changes since source ZIP

Active runtime changes (only):

1. `firewall/net01-clear-hold-review-only.sh`
2. `firewall/net01-clear-maintenance-review-only.sh`
3. `firewall/net01-fw-install.sh`
4. `firewall/net01-fw-rollback.sh`
5. `firewall/net01-maintenance-enter.sh`
6. `firewall/net01-start-admit.sh`
7. `systemd/captiv-net01-watchdog.service`

All six scripts replace `/run/lock/captiv-net01-firewall.lock` with persistent `/var/lib/captiv-net01/net01-firewall.lock`, verify root:root `0700` unsymlinked parent; root:root `0600`, regular, nlink=1 file when existing; cold-create `0600` under the existing `umask 077`; acquire `flock -n` on fd 9 and verify fd/path same inode. No lock-file deletion in maintenance/rollback/reinstall. The watchdog `ReadWritePaths` is reduced from two paths to **only** `/var/lib/captiv-net01`. `StateDirectory` is already owned by `captiv-net01-firewall.service` with `StateDirectory=captiv-net01` and `StateDirectoryMode=0700` (UNCHANGED). Root-running participants: firewall.service `User=root`, watchdog `User=root`, failsafe `User=root`, application prestart has `ExecStartPre=+` for root-only admission. Interactive maintenance/rollback require EUID=0. The Flask main process remains unprivileged.

Test/support files changed: `tests/rev4_fixture.py`, `tests/test_rev4_negative_offline.py`, `tests/test_p1ab_original_tuple_and_lock.py`; added `tests/test_lockpath_secure_offline.py` (+16 focused cases). Added `CHANGELOG_LOCKPATH_FINAL.md`, this handoff, and top-level README status header. Historical `.patch`/`.diff` and historical staging records are retained byte-for-byte for provenance and contain obsolete lock path: **never deploy from patches**.

Verified byte-identical to source ZIP: firewall verifier, Python watchdog, sensor/conntrack/TCP policy logic, Docker compose, NPM image evidence, firewall service unit, failsafe unit, captive-portal drop-in, all other original runtime files.

## Independent offline acceptance

- Source regression before edit: `180/180 PASS`.
- Final regression: `196/196 PASS` (`180` preserved + `16` lock cases), command `python -m pytest -q tests --disable-warnings --maxfail=1`.
- `bash -n firewall/*.sh`: PASS.
- `bash tests/test_systemd_verify_offline.sh`: PASS (synthetic/root fixture; not actual production systemd execution).
- Python AST for `.py`: PASS; manifest SHA-256: PASS after package build.
- Negative tests: symlink directory, symlink file, hardlink, non-regular file, wrong mode, missing StateDirectory, wrong dir mode, held lock across six scripts; cold creation 0600 and inode persistence; rollback/reinstall cannot unlink the lock.
- Previous real WSL2 Docker/nft/systemd network staging (`180/180`) is **reported** in original evidence, not rerun with the amended lock path. Byte-identical full-stack live acceptance remains a change-window gate.

## Exact scoped live change set — PROPOSED, NOT AUTHORIZED

**Read-only preflight before any mutation (GO prerequisite):**

1. Confirm target is `captiv-prod` / `192.168.0.99` and capture date, OS, snapshot/backups, free space, running sites, NPM Proxy Host/port status and existing NPM image digest. No Cisco, DNS, Omada or public NPM route edits.
2. Confirm exact approved Docker bridge/IP/MAC (`br-627e7c1ca6d5`, NPM `172.18.0.2`, gateway `172.18.0.1`, MAC `b2:fa:fc:bf:d5:bc`) **with live read-only commands**; compare observed state, Docker NAT/iptables-nft and container membership with strict verifier assumptions. Any mismatch => HOLD; never substitute identities at install time.
3. Confirm `fingerprint-sensor` dedicated numeric nonzero UID exists, actual service ownership, `systemctl show` dependencies/masks/states, no existing TCP 18089 listener, existing INPUT/OUTPUT/ip6tables policy and absence of conflicting rules, whether `/var/lib/captiv-net01` already exists. If exists it must be root:root 0700 real directory, and existing `net01-firewall.lock` must be root:root 0600 regular one-link inode. Unknown ownership => HOLD; never chmod/chown files belonging to other services.
4. Save root-protected before-snapshots of all touched target files, relevant firewall rule snapshots, Docker network identity, systemd unit states, NPM health/backup metadata and timestamp. Sanitise reports; no secrets.

**After an explicitly scoped Owner GO only:**

1. Verify final ZIP SHA-256 and every `MANIFEST.sha256` entry against extracted bytes in a **root-controlled staging directory**. Do not execute archive members from Downloads/ZIP. Before installation ensure target paths are either absent or explicitly owned by this task; any collision => HOLD.
2. Install the six `firewall/*.sh` above to `/usr/local/libexec/captiv-net01/` individually with `install -o root -g root -m 0755` (executable); install the existing Python `firewall/*.py` as root-owned `0644` (invoked via `/usr/bin/python3`); install approved `systemd/*.service` to their explicit unit locations as root-owned `0644`, and only place `captive-portal-net01.drop-in.conf` at the approved new-Portal unit drop-in when authorized to create it. Never use recursive chmod; do not install `commands-review-only.txt` as an executable.
3. Use the existing `captiv-net01-firewall.service` `StateDirectory=captiv-net01`, `StateDirectoryMode=0700`, root-run service to provision the persistent directory on service start. Do not manually create it in an unapproved location, and do not enable the watchdog/Core/Flask until explicit startup admission is approved. Check owner/mode with `stat` before lock use. Existing unknown lock or directory => HOLD, not overwrite/unlink.
4. Run `systemd-analyze verify` on installed units, `bash -n` on installed shell files, strict identity preflight, baseline snapshots. Launch *only* the approved diagnostic backend and NET01 temporary components under the approved preinstall staging plan; verify actual NPM container TCP reachability, host-local Sensor UID path, negative access, conntrack original tuple, watchdog drift/failure, maintenance, exact rollback, reinstall, cold start and persistent lock inode. Test actual NPM HTTPS Proxy Host only under its **separate later GO**; do not change old Proxy Hosts or public ingress as part of this lock fix.
5. After PASS freeze evidence and restore verified staging-clean state (or accepted preinstall-only state), confirm active NPM public sites unchanged. No CaptivePortal install; no AP migration; no Cisco changes.

**STOP/rollback:** If any uncertain identity, wrong rights, lock path, service state or firewall mismatch occurs, HOLD and do not start the new backend. On failure *before firewall mutation*, revert only newly installed NET01 files/units from timestamped prechange copies and run `systemctl daemon-reload` if units changed; preserve root directory/lock file and all unrelated services. Once firewall installed, set MAINTENANCE and verify actual new service/backend quiescence before running **the exact accepted** `net01-fw-rollback.sh`; it must verify exact ownership and remove only its dedicated rules. Never flush iptables, delete lock, rename a held lock, manually replace a partial policy or stop Docker/NPM. If rollback verifier cannot prove ownership, leave fail-closed/HOLD, keep diagnostic backend off, and escalate with protected evidence. Post-rollback assert NPM public HTTPS, existing sites and old production unchanged; then record exact pre/post diff. Owner authorizes all live changes separately.

**Note on installation sequencing:** The approved new CaptivePortal base service is intentionally absent at this preinstall stage; no attempt to install/start it is permitted. A diagnostic backend is not a substitute for Portal authorization acceptance. The package is a verified OFFLINE baseline, not proof of production deployment.
