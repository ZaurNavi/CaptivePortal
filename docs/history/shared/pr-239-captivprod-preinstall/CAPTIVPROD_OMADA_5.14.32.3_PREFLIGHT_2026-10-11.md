# TASK-CAPTIVPROD-OMADA-INSTALL-01 — Package / Dependency Preflight

**Date:** 2026-10-11 (Asia/Baku)  
**Scope:** offline inspection, read-only inspection of target and source; **no installation, no migration, no AP adoption.**  
**Overall task status:** `PART_A=HOLD`, `PART_B=NOT_STARTED`, `PRODUCTION_AP_MIGRATION=NO`.

## 1. Source and target

- Original Omada (read-only `/api/info`): Windows Server 2016, `192.168.0.222:8043`; full version **5.14.32.3**; API v3; configured.
- Target: `captiv-prod`, `192.168.0.99`, Ubuntu **22.04.5 LTS (jammy)**, `amd64`/x86_64, 4 logical CPUs, 15 GiB RAM (approx. 14 GiB available), root filesystem approx. 84 GiB available; backup filesystem approx. 900 GiB available.
- NPM production ingress: TCP `80/81/443` bound on `192.168.0.99`, Docker container `npm`, image `jc21/nginx-proxy-manager:2.16.0`; no target Omada listeners observed.
- Target before changes: Java absent, JSVC absent, `mongod` absent, Omada absent; `curl` installed.
- Network: default route `192.168.0.1`, target interface `enp2s0`; UFW inactive and INPUT policy ACCEPT. Thus management and device paths require deliberate access controls before starting a restored controller per task A4.
- Existing NPM and OS backup timers active; latest NPM backup observed `/srv/backups/app-data/npm/20261011T160955Z` (separate from future Omada backup).

## 2. Exact official package, acquired OFF the production server

- TP-Link official download listing, dated 2024-11-01:
  https://www.tp-link.com/uk-ua/support/download/ds-p7001-04/?app=kasa
- Direct official vendor URL:
  https://static.tp-link.com/upload/software/2024/202411/20241101/Omada_SDN_Controller_v5.14.32.3_linux_x64.deb
- Artifact filename: `Omada_SDN_Controller_v5.14.32.3_linux_x64.deb`
- Size: **234,289,220 bytes**.
- Locally computed SHA-256: `934b34dac9469307dee37e10edd9707595171d65bc2db114002a18f38bf48899`.
- Downloaded to an authorized Windows workstation at `%USERPROFILE%\Downloads\Omada_SDN_Controller_v5.14.32.3_linux_x64.deb`; **not** copied to `/opt`, `/tmp`, or other paths on the target.
- The SHA-256 above proves reproducibility of this file, **not independent vendor signature verification**; a vendor-published digest was not confirmed.

## 3. Offline .deb metadata, directly extracted from control.tar.xz

```
Package: omadac
Version: 5.14.32.3
Architecture: all
Depends: adduser, jsvc (>=1.0.8), curl,
 mongodb-server (>= 3.0.0) | mongodb-10gen (>= 3.0.0) | mongodb-org-server (>= 3.0.0),
 mongodb-server (<< 1:7.1.0) | mongodb-10gen (<< 7.1.0) | mongodb-org-server (<< 7.1.0),
 java8-runtime-headless
Pre-Depends: debconf (>= 0.5) | debconf-2.0
Conflicts: omada, eap-controller, omadac-pro
```

**Definitive finding:** MongoDB Server is a HARD PACKAGE DEPENDENCY. A compliant `apt`/`dpkg` installation *without any installed MongoDB server provider* cannot succeed. Do not bypass dependencies with `--force-depends` or equivalent. Omada does **not** ship an executable `mongod` in this `.deb`; `mongodb-driver-*.jar` files are Java drivers, not a database server.

### Installer behavior found in maintainer scripts

- `postinst` defines `OMADA_USER=omada`, creates OS service account and data/log/work/property directories under `/opt/tplink/EAPController`.
- `postinst` explicitly runs `ln -sf $(which mongod) ${INSTALL_DIR}/bin/mongod`.
- `postinst` registers `tpeap` with `update-rc.d tpeap defaults` and executes `tpeap start` **during package installation**.
- `control.sh` checks presence of `jsvc` and `curl`, then starts the Java controller via `jsvc ... OmadaLinuxMain start`. Database process startup/lifecycle needs to be verified at runtime in an approved test; it must not be inferred simply from the number of system services.
- The `.deb` carries an init script, Java libraries and drivers, but does not contain MongoDB's executable server.

### Package-compatible apt candidates visible on Ubuntu 22.04 target (read-only `apt-cache`)

| Dependency | Candidate or installed | Assessment |
|---|---|---|
| `openjdk-11-jre-headless` | `11.0.32.1+1-1ubuntu1~22.04` candidate | Provides `java8-runtime-headless`; viable candidate, not yet installed |
| `jsvc` | `1.0.15-8` candidate | Satisfies `.deb` `jsvc >= 1.0.8`; not yet installed; runtime compatibility untested |
| `curl` | `7.81.0-1ubuntu1.29` installed | Available |
| `mongodb-org-server` | No configured candidate at preflight | An approved vendor repository and pinned compatible `7.0.x` build required if installation proceeds |

TP-Link documentation permits MongoDB up to v7 for Omada releases after v5.14.20. This `.deb` specifically constrains `mongodb-org-server` to versions **below 7.1.0**. Choose an exact patched 7.0.x build, rather than unpinned `latest`, after verifying repository availability and version; do not choose MongoDB v8.

## 4. Safe MongoDB strategy for later authorized installation

1. Keep Omada version **5.14.32.3** locked to match current Windows source.
2. Before package mutation, close Part A gates (source configuration inventory, backup and checksum, documented management access / isolation), and obtain separate Owner authorization for Part B.
3. Install approved Java, JSVC and curl; obtain an approved MongoDB **server binary/package** of a compatible pinned build.
4. Verify and prevent automatic operation of a separate **system `mongod.service`**; installing a server binary must not leave an additional system MongoDB daemon running alongside the Omada-controlled instance. Systemd/service handling should be verified for this specific MongoDB package at install time.
5. Be aware: the vendor Omada `.deb` **auto-starts** the controller in `postinst`. Pre-install safety checks must therefore happen before `dpkg -i` / `apt install ./...`, not after.
6. After explicit Part B authorization, validate `mongod` process count, startup command, port (often Omada-internal `27217`, to be confirmed on the installed version), listening bind address, ownership, process restart, logs, and correct service stop behavior.
7. Never expose the Omada admin interface through NPM public 80/443 or alter Cisco, source Omada, AP, or portal in this task.
8. After approved isolated restore, verify source AP ownership unchanged and create protected target Omada backup plus offline restore evidence.

## 5. Open gates

- `A1_SOURCE_INVENTORY=HOLD` — version confirmed, but site/WLAN/AP/Webhook and permission inventory not complete.
- `A2_TARGET_INVENTORY=PARTIAL_PASS` — resources/listeners/firewall/dependencies checked; complete access-control and port matrix not yet certified.
- `A3_PACKAGE_VERSION=PASS` — exact official artifact downloaded and SHA-256 computed; dependency compatibility narrowed, MongoDB exact build and backup restore acceptance still need sign-off.
- `A4_ISOLATION_PLAN=HOLD` — Owner reports prior non-interference testing, but a version-specific safety plan/evidence is not documented in this run.
- `A5_SOURCE_BACKUP=HOLD` — original controller config export and SHA-256 not performed.
- `PART_B_INSTALL=NOT_AUTHORIZED_BY_PREP_TASK`; no package installed on target, no service started.

### Sources

- User-assigned TASK `TASK-CAPTIVPROD-OMADA-INSTALL-01 v1`, Parts A–E.
- TP-Link official 5.14.32.3 download listing: https://www.tp-link.com/uk-ua/support/download/ds-p7001-04/?app=kasa
- TP-Link official Linux FAQ: https://www.tp-link.com/uk/support/faq/3272/
- TP-Link migration/compatibility FAQ: https://www.tp-link.com/baltic/support/faq/3589/
- Direct inspection of unexecuted `.deb` control metadata, maintainer scripts and archive file list, and target read-only commands.
