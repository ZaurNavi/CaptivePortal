# TASK-CAPTIVPROD-PORTAL-FRESH-INSTALL-01 v1
## CaptivePortal: независимая чистая установка на `captiv-prod` — руководство SysAdmin

**Дата:** 2026-10-14  
**Architect:** Captiv-Prod  
**Исполнитель:** Captiv-Prod SysAdmin / Deployment Lead  
**Тип:** install/preparation/verification; production cutover — отдельный Owner GO  
**Основа:** `CaptivPortal_Fresh_Install_Guide_2026-10-14.docx`, актуальный GitHub `ZaurNavi/CaptivePortal` и реальная инфраструктура Captiv-Prod.  
**GitHub HEAD, увиденный при ревизии:** `3b5f70cec467939995fecc7667169239000b7308` (2026-10-14, PR #206). **Это не автоматическое разрешение развёртывать HEAD.** Owner/Tech Lead утверждают точный SHA/tree.

> **ОБЯЗАТЕЛЬНО:** Проводить работу по частям. Ни один FAIL/HOLD нельзя обходить подбором случайных значений, отключением безопасности или локальным patch production source. До отдельного GO — не менять работающие Omada/AP/Guest/Portal и публичный NPM routing.

## 0. Итог архитектурной проверки исходного руководства

Исходный документ принят как **источник по поведению приложения**, но **не как готовый runbook для существующего `captiv-prod`**.

| В исходном руководстве | Решение для Captiv-Prod |
|---|---|
| Установить `nginx`, создать Nginx vhost на 443, выпустить Let's Encrypt | **НЕ ВЫПОЛНЯТЬ.** Публичный ingress/TLS уже принадлежит NPM 2.16.0, Docker bridge, `192.168.0.99:80/443`; админ NPM :81 |
| `Nginx → 127.0.0.1:8088` | **Нельзя копировать в NPM как есть:** `127.0.0.1` внутри NPM Docker — loopback контейнера, не хоста. Требуется утверждённый Docker→host backend path (Gate NET-01) |
| `HOST=127.0.0.1`, `PORT=8088`, `VERIFY_SSL=False` | По GitHub `app/config.py` это **кодовые константы**, а не свободно меняемые значения env; `ProxyFix` доверяет 1 hop |
| Omada «уже работающий контроллер» | Новый подготовленный Linux Omada на **этом** `captiv-prod`, а не по умолчанию старый Windows `.222`. Факт завершения Omada TASK установить до действий с Portal |
| Реальный телефон сразу в acceptance | **Только после отдельного пилотного AP GO**. До передачи тестовой AP новой Omada нет фактического гостевого E2E |
| Включение/выключение десятков функций через `.env` | У каждого feature флаг и auxiliary service должны сверяться с **exact SHA и systemd**, env не отключает независимо запущенные units |
| Fresh SQLite/логи | **Принято**, но settings/credentials/Site/domain/trust/profiles — эксплуатационная конфигурация, не «неважная история» |
| OpenAPI `HTTP 200` | Недостаточно: фактический `errorCode=0`, корректный Site, read-only tests и proof authorized с pilot AP |
| Подготовка в одном процессе | **Принято:** `run.py` как основной lifecycle root, без параллельных Flask/WSGI workers |

### Два важнейших HOLD до инсталляции/подключения

1. **CTRL-01:** New Omada на `.99` действительно установлен, восстановлен и изолирован; `TASK-CAPTIVPROD-OMADA-INSTALL-01` принят. По имеющемуся **историческому** preflight от 11 октября: source Windows Controller `5.14.32.3`, target Ubuntu 22.04.5, NPM работает; Omada install тогда **не был выполнен**. Его нынешний статус повторно проверить, не угадывать.
2. **NET-01:** выбрать и проверить реальный путь **NPM (Docker bridge) → Flask (host loopback)**. Варианты требуют отдельного design approval: (а) ограниченный host-side relay на Docker bridge с transport→`127.0.0.1:8088`; (б) reviewed Git change конфигурации bind + строгое сетевое ограничение NPM→backend. **Не** устанавливать второй публичный nginx, **не** публиковать `8088` в WAN/Guest, **не** переводить NPM в host networking, **не** встраивать Docker socket. Если нет подтверждённого способа — остановиться после локального app acceptance, не менять Proxy Host.

## 1. Архитектурные границы и целевое состояние

```text
CURRENT PRODUCTION (unchanged during preparation)
Internet → Cisco NAT 80/443 → NPM on captiv-prod .99
                            → HTTPS → Hestia on .202 → old Portal .202:8088
Production APs → old Omada Windows .222 → old Portal

NEW PARALLEL INSTALL (no AP migration yet)
new Omada Linux on captiv-prod .99 [isolated, no production AP]
new Flask Portal, run.py → 127.0.0.1:8088 (local only)
new isolated SQLite/JSONL/settings/secrets

AFTER SEPARATE CUTOVER GO
Internet → same Cisco/NPM public FQDN/certificate
         → approved NPM→host backend → new Portal
pilot AP → new Omada → new Portal → verified authorization
```

**In scope:** preflight, approved Git checkout, Python/runtime/systemd, clean stores, core configuration, safe local smoke, read-only OpenAPI, later authorized NPM test path, backups and evidence.  
**Out of scope:** moving old SQLite/JSONL/history, old VM shutdown, Cisco/DNS/NAT edits, public TLS reissue, installing another public nginx, migration/adoption of AP, reconfiguring production SSIDs, enabling DHCP option 114, mass webhook redirection, unreviewed CAPPORT or TLS code edits, broad firewall redesign, Fingerprint/Suricata/NI production activation.

## 2. PART A — READ-ONLY PREFLIGHT (no changes)

**A1. Target identity.** On `captiv-prod`, read and record:

```bash
hostnamectl
cat /etc/os-release
uname -m
python3 --version
ip -br addr
ip route
resolvectl status
df -hT
free -h
uptime
timedatectl status
sudo ss -lntup
sudo systemctl --type=service --state=running --no-pager
sudo docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
sudo docker network ls
```

Never change firewall/NPM ports while investigating. Confirm Docker NPM `192.168.0.99:80/443/81`, management isolation, disk headroom, clock sync, existing backups. Do not confuse loopback host with container loopback.

**A2. Source observation (read-only).** On old `.202`, capture `git HEAD/tree`, effective systemd unit/drop-ins and **names/sources only** of EnvironmentFiles, listening ports, activated module/service names, CAPPORT Site/CIDR/domain, webhook route and NPM upstream, with secrets redacted. The old Portal must remain untouched. Compare repo config with live runtime; record discrepancies.

**A3. Controller gate.** Inspect new Omada UI/API safely; capture effective controller URL/port, `omadac_id`, Site names/IDs, SSID and External Portal profile, OpenAPI client permission presence (no secret), isolation state, AP adoption count 0. Old `.222` must retain production AP ownership. Do not run hotspot authorize/unblock/cleaner/actions at this stage. If new Controller is absent/not accepted: `PART_A=HOLD`, no Portal activation.

**A4. Public edge.** Read NPM Proxy Host/cert list, current direct backend path to Hestia, `X-Forwarded-*`/Host/SNI handling, sensitive-query logs, current backup consistency/restore smoke. **Do not edit** production Proxy Host. Test LAN/guest management isolation; no production request replay involving MAC/token.

**A5. Exact release identity.** Owner+Tech Lead select approved full SHA/tree; check PR status, acceptance, Linux compatibility and feature inventory. `main` is only a candidate, not an approved release. `requirements.txt` has lower bounds, not a dependency lock: obtain reviewed resolved-dependencies record and reproducibility evidence.

**PART A PASS:** Target/source/controller/edge inventories, approved SHA+tree, compatibility, bind/network design and isolation all documented. Otherwise STOP/HOLD.

## 3. PART B — CLEAN CORE INSTALL (target mutations require Owner GO)

**B1. Package preparation (NO nginx install):** verify that `git`, Python 3.10+ (`venv`, `pip`), CA certificates and curl are available. On Ubuntu install **only missing approved packages**; do not do unattended distribution upgrades or install host nginx. Record package versions and effect on existing Omada/NPM. Example after gate:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends git python3-venv python3-pip ca-certificates curl
```

**B2. Dedicated identity and permissions.** Use one unprivileged system user. Before creation check if user/path/unit already exist to prevent overwrite. Template (only if absent):

```bash
getent passwd captivportal || sudo useradd --system --home /var/lib/captive-portal --create-home --shell /usr/sbin/nologin captivportal
sudo install -d -o root -g root -m 0700 /etc/captive-portal
sudo install -d -o captivportal -g captivportal -m 0750 /opt/CaptivePortal/data /opt/CaptivePortal/logs
```

Code should ultimately be root-owned and not writable by the running service, while `data` and `logs` remain service-owned. New schemas created by their writer only. **Existing files must never be recursively chowned without inspecting ownership/mounts.**

**B3. Git-only checkout.** Confirm `/opt/CaptivePortal` absent or inventory it and stop for separate handling. Do not overwrite an existing checkout. Once exact SHA has been approved:

```bash
sudo git clone https://github.com/ZaurNavi/CaptivePortal.git /opt/CaptivePortal
cd /opt/CaptivePortal
sudo git fetch origin
sudo git checkout --detach <OWNER_APPROVED_FULL_SHA>
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git status --porcelain
```

If repository is private, use approved Git credentials, never secrets in command/URL/log. Confirm tree matches approved evidence. No direct source file patches or uncontrolled checkout upgrades.

**B4. Python dependencies.** Prepare `.venv` from approved dependency resolution; install `requirements.txt` only under tested/pinned policy (bare lower bounds cannot ensure repeatability). Capture `pip freeze` and hashes/internal manifest **without secrets**. The app is launched through the venv Python with `run.py` directly. Do not run full repository test suite on production.

**B5. Operational config (NO copy of old database).** Place approved root-owned env configuration outside Git, e.g. `/etc/captive-portal/portal.env` mode 0600 (systemd `EnvironmentFile`; `.env.example` does not auto-load). Values must be obtained from **new** Omada; do not assume same `omadac_id`/Site ID/ClientSecret after restore:

```ini
# SCHEMA ONLY — NEVER EXECUTE WITH PLACEHOLDERS
OMADA_URL=https://<VERIFIED_NEW_CONTROLLER_ENDPOINT>
OMADA_ID=<VERIFIED_NEW_CONTROLLER_ID>
OMADA_CLIENT_ID=<VERIFIED_CLIENT_ID>
OMADA_CLIENT_SECRET=<INSERT_VIA_APPROVED_SECRET_HANDLING>
OMADA_WEBHOOK_ENABLED=false
PENDING_SESSION_CLEANER_ENABLED=false
VISITOR_SNAPSHOT_ENABLED=false
VISITOR_REGISTRY_ENABLED=false
VISIT_LIFECYCLE_ENABLED=false
OBSERVATION_FOUNDATION_ENABLED=false
CURRENT_STATE_ENABLED=false
ANALYTICS_FOUNDATION_ENABLED=false
ANALYTICS_API_ENABLED=false
WEB_ADMIN_ENABLED=false
WEB_ADMIN_SETTINGS_ENABLED=false
PUBLIC_TRAFFIC_COUNTER_ENABLED=false
```

**Do not assume this list disables every auxiliary feature.** Validate exact names and behavior against approved Git SHA, `.env.example`, `app/config.py`, `app/settings.py`, `run.py` and effective systemd units. Ensure independently started `traffic-projection`, Fingerprint, sensor, Suricata, NI processes remain stopped/absent unless separately approved. For `WEB_ADMIN_SETTINGS_ENABLED=true` in future, settings DB plus externally provisioned master key are an independent security gate. If required credentials are missing, Omada bootstrap intentionally fails closed.

**B6. Code-bound configuration review.** Confirm constants in selected SHA: `HOST=127.0.0.1`, `PORT=8088`, `DEBUG=False`, `VERIFY_SSL=False`, `CAPPORT_ENABLED=True`, fixed `CAPPORT_SITE_ID`, `CAPPORT_PUBLIC_BASE_URL`, `CAPPORT_ALLOWED_CLIENT_NETWORKS`. The last three **must match actual new Site/domain/client networks**. If they do not, **STOP** and request narrow Git reviewed change/test/merge; do not pretend env overrides work. `VERIFY_SSL=False` is existing technical debt; record and security-gate any change, never imply Omada TLS peer verification is active. Review `ProxyFix(x_for=1,x_proto=1,x_host=1,x_port=1)`.

**B7. Single systemd service.** Only after B1–B6 PASS: implement exactly one main application process and root-controlled unit. Example adapted from source guide (do not overwrite an existing unit):

```ini
# /etc/systemd/system/captive-portal.service
[Unit]
Description=CaptivPortal guest authorization (captiv-prod)
Wants=network-online.target
After=network-online.target
[Service]
Type=simple
User=captivportal
Group=captivportal
WorkingDirectory=/opt/CaptivePortal
EnvironmentFile=/etc/captive-portal/portal.env
ExecStart=/opt/CaptivePortal/.venv/bin/python /opt/CaptivePortal/run.py
Restart=on-failure
RestartSec=5
TimeoutStopSec=120
UMask=0027
Environment=PYTHONDONTWRITEBYTECODE=1
StandardOutput=journal
StandardError=journal
[Install]
WantedBy=multi-user.target
```

Review actual service credentials/`LoadCredential` needs with selected Settings release. Avoid logging environment and credentials. After install, `daemon-reload`; controlled one-time `start` only when the new Controller is reachable and process flags validated. `enable` only after acceptance; no auto-start before gate.

**B8. Startup evidence:**

```bash
sudo systemctl daemon-reload
sudo systemctl start captive-portal.service
systemctl is-active captive-portal.service
systemctl show captive-portal.service -p MainPID -p NRestarts --no-pager
sudo ss -lntp | grep ':8088' || true
curl -sS -i --max-time 5 http://127.0.0.1:8088/ | head -25
sudo journalctl -u captive-portal.service -n 120 --no-pager
```

Before pasting journal into report **redact query identifiers/tokens/secrets**. `/` without Omada parameters may return controlled 4xx; that's not a failure by itself. Confirm one process, no restart loop, correct listener, no unexpected Omada side effects. Preserve first startup evidence. If fail: stop this new service; leave old running.

## 4. PART C — SAFE ISOLATED FUNCTIONAL ACCEPTANCE

**C1 — Loopback/local.** Verify Flask responds, Portal assets, bounded error handling, CAPPORT routes with non-sensitive synthetic requests, correct charset/content types, Admin disabled, no extra public listeners.

**C2 — Controller read-only.** From target OS verify HTTPS reachability, OAuth token exchange and authorized read-only Site/client request with fresh new Controller credentials; Omada's `errorCode=0` and expected Site are necessary. Do not dump token or secret. No production AP in new Controller: zero client inventory is **expected**, not failure.

**C3 — CAPPORT.** `CAPPORT_SITE_ID` matches new Omada's actual Site; public base URL is owner-approved; allowed CIDRs match the actual guest networks. Do not activate DHCP option 114 yet. A CAPPORT discovery/login response may require live Site/client evidence; distinguish `NOT_TESTED` from `PASS`.

**C4 — Optional components.** Record feature matrix `OFF / COMPOSED / RUNNING / VERIFIED`; no extra analytics/NI/projection worker silently started. Verify new SQLite schemas only after associated writer is intentionally enabled; history is intentionally empty.

**C5 — Disk/backup/security.** New `data`/`logs` protected; no secrets in access logs, containers or evidence; log rotation/retention agreed; observe baseline physical HDD IO, CPU, memory. No SQLite durability weakening. Take consistent configuration + new databases + secrets dependency manifest backup with restore smoke in isolated path. Ensure backing up live SQLite is application-consistent, not raw cp of active DB.

**PART C expected accepted result:** `NEW_PORTAL_LOCAL_PREPARED=PASS`, `REAL_GUEST_E2E=NOT_TESTED_BY_DESIGN`, `NPM_PUBLIC_CUTOVER=NO`.

## 5. PART D — NPM INTEGRATION (separate NET-01 decision + Owner GO)

**D0 — BLOCKER:** NPM uses Docker bridge. Flask binds host `127.0.0.1:8088`, unreachable through container `127.0.0.1`. SysAdmin must submit tested proposed reachability/port exposure design to Architect BEFORE modifying NPM; document (1) NPM container actual network, (2) host destination/address and listener, (3) isolation from Guest/WAN/other VLAN, (4) return-path and firewall including Docker NAT, (5) trusted single-hop header semantics. If no safe path exists, `PART_D=HOLD`. A tested narrowly-scoped relay or reviewed bind configurability may be proposed; neither is pre-authorized.

**D1 — No extra TLS stack.** Use existing NPM, public hostname `captivportal-navi.duckdns.org` only if that is still confirmed authoritative. **Do not install host nginx, issue another public cert, or modify Cisco NAT/DNS.** Create isolated NPM route only if it doesn't change the existing production Proxy Host; use temporary hostname/route only after confirming its security and certificate behavior. Do not create ambiguous duplicate Proxy Host for same FQDN.

**D2 — Reverse proxy header and privacy tests.** Confirm `Host`, URI, query, original frontend scheme, client IP and `ProxyFix` trust count. Reject spoofed `X-Forwarded-For/Host/Proto/Port`, verify no sensitive query is retained in NPM persistent or container logs (synthetic canary), record backend route without making it public by accident. Because the older NPM→Hestia real-IP mitigation involved two hops, **do not automatically reuse that Hestia configuration** for new one-hop direct path.

**D3 — Health/preserved production.** Current public NPM route must still reach old Hestia/old Portal; old controller still owns all APs; new controller zero production APs. Real guest flow via new Portal **not claimed**. Accept `NPM_TEST_PATH=PASS` only when routing truly exercises Docker→host target and TLS/headers are verified.

## 6. PART E — PILOT AP + CUTOVER (NOT AUTHORIZED BY THIS TASK)

Separate `TASK-CAPTIVPROD-OMADA-AP-PILOT-01` is required to transfer **one explicitly chosen** test AP to the new controller. Old production APs and the old public Portal stay live. Pilot traffic requires explicitly approved test hostname/SSID/External Portal mapping; same public FQDN cannot arbitrarily split old/new Controller client identity. Owner-controlled phone only. Required real E2E: redirect, no TLS warning, correct Site/SSID/MAC/IP, one AuthSession/worker, authorize + read-back `authStatus==2`, actual Internet, no log privacy regression. Gate failure → return pilot AP and mapping to approved old arrangement.

Only after pilot PASS and separate Owner GO may `TASK-CAPTIVPROD-PRODUCTION-CUTOVER-01` switch the existing NPM Portal Proxy Host from Hestia to approved local backend and migrate remaining APs. Maintain Hestia/old Portal/old Omada rollback path; changes in backend routing and AP ownership must be coordinated, not assumed atomic. Authorize/schedule webhook/analytics/Settings/Fingerprint/NI activations as subsequent gates, not as side effects of base installation.

## 7. STOP / ROLLBACK

- **Any failure during A:** do not mutate anything; report HOLD.
- **Failure B/C:** stop only new `captive-portal.service`; preserve first logs, new DBs/config for diagnostics; old Portal/Omada/NPM remain untouched. No arbitrary `rm -rf`, `VACUUM`, source patch, or reinstallation to disguise first-start failures.
- **Failure D:** restore existing NPM Proxy Host/config from documented backup only if it was explicitly changed with approval; confirm public TLS → Hestia → old Portal + real phone. Never change Cisco/DNS as a shortcut.
- **No AP migration within this TASK.** Pilot/cutover rollback belongs to separate tasks.

## 8. Final mandatory SysAdmin handoff

```text
TASK=TASK-CAPTIVPROD-PORTAL-FRESH-INSTALL-01
DATE_TIME=
TARGET_HOST_IP_OS=
OLD_PORTAL_SOURCE_HEALTH=
NEW_OMADA_VERSION_SITE_AP_COUNT=
NEW_OMADA_PREPARED=PASS/HOLD
APPROVED_GIT_SHA=
APPROVED_GIT_TREE=
DEPLOYED_GIT_SHA_TREE=
GIT_WORKTREE_CLEAN=YES/NO
PYTHON_VERSION=
DEPENDENCY_MANIFEST=
APPLICATION_USER=
CONFIG_FILE_SOURCE_AND_PERMISSIONS=
DATA_LOG_PATH_PERMISSIONS=
CAPPORT_SITE_DOMAIN_CIDR_REVIEW=PASS/HOLD
OMADA_VERIFY_SSL_SECURITY_DEBT=DOCUMENTED/RESOLVED
FEATURES_AND_AUX_UNITS_MATRIX=
SYSTEMD_MAINPID_RESTARTS=
LOCAL_8088_LISTENER=
LOCAL_HTTP_SMOKE=
OMADA_READONLY_OAUTH_API=PASS/HOLD
SETTINGS_STORE=DISABLED/APPROVED
NEW_DB_BOOTSTRAP=PASS/HOLD
NPM_DOCKER_HOST_NET01=PASS/HOLD/NOT_STARTED
NPM_TEST_PATH=PASS/HOLD/NOT_STARTED
NPM_PRODUCTION_ROUTE_UNCHANGED=YES/NO
PUBLIC_TLS_OWNER=NPM_UNCHANGED
NEW_PORTAL_BACKUP_RESTORE_SMOKE=
SENSITIVE_LOG_CANARY=PASS/HOLD/NOT_STARTED
OLD_PRODUCTION_AP_OWNERSHIP_UNCHANGED=YES/NO
REAL_GUEST_E2E=NOT_TESTED_BY_DESIGN
AP_MIGRATION=NO
CUTOVER=NO
PART_A=PASS/HOLD
PART_B=PASS/HOLD/NOT_STARTED
PART_C=PASS/HOLD/NOT_STARTED
PART_D=PASS/HOLD/NOT_STARTED
NEW_PORTAL_LOCAL_PREPARED=PASS/HOLD
OPEN_P0_P1_AND_DECISIONS=
SECRETS_IN_REPORT=NO
```

## 9. Sources / verification boundaries

- Original: `CaptivPortal_Fresh_Install_Guide_2026-10-14.docx` (11 pages), especially install, configuration, one-process lifetime, E2E and optional feature stages.
- Current public repository inspected: https://github.com/ZaurNavi/CaptivePortal (main SHA `3b5f70cec467939995fecc7667169239000b7308` at inspection). Read code contracts: `run.py`, `app/config.py`, `app/settings.py`, `app/web/web.py`, `app/controllers/omada_config.py`; docs `deployment.md`, `configuration.md`, `project-inventory.md`.
- Local infrastructure material: `TASK-CAPTIVPROD-EDGE-NPM-01_v2.md`, Architecture Amendment v3, `TASK-CAPTIVPROD-OMADA-INSTALL-01_v1.md`, `CAPTIVPROD_OMADA_5.14.32.3_PREFLIGHT_2026-10-11.md`.
- **Not independently checked live in this run:** new Omada installation current completion, effective systemd/NPM target configuration, network ACLs, actual AP state and production Git SHA. SysAdmin A1–A5 evidence is authoritative for those current-state claims.

**Architect verdict:** runbook approved for **read-only Part A**; target mutations after Owner GO, release approval and closed relevant gates. `NPM_PUBLIC_CUTOVER=HOLD`, `PRODUCTION_AP_MIGRATION=HOLD`.
