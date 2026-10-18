# Configuration map

Status: current repository contract
Updated: 2026-10-14

<!-- NETWORK-INTELLIGENCE-V1:BEGIN -->
## Network Intelligence V1

Repository defaults are deployment defaults, not proof of current production feature state.

| Setting | Repository default | Meaning |
|---|---|---|
| NETWORK_METADATA_ENABLED | false | NI-01 auxiliary ingestion gate |
| NETWORK_METADATA_SOURCE_PATH | /run/fingerprint-suricata/dti-ni-v1.eve.json | Suricata NI EVE source |
| NETWORK_METADATA_DB_PATH | /opt/CaptivePortal/data/network_metadata.sqlite3 | NI-01 source store |
| NETWORK_ATTRIBUTION_ENABLED | false | NI-02A attribution writer/read gate |
| NETWORK_ATTRIBUTION_DB_PATH | /opt/CaptivePortal/data/network_attribution.sqlite3 | NI-02A store |
| NETWORK_ATTRIBUTION_MAX_DB_BYTES | 536870912 | default attribution DB budget |
| NETWORK_METADATA_PROJECTION_ENABLED | false | NI-02B worker gate |
| NETWORK_METADATA_PROJECTION_DB_PATH | /opt/CaptivePortal/data/network_metadata_projection.sqlite3 | NI-02B derived store |
| WEB_ADMIN_DEVICE_PROTOCOL_INTELLIGENCE_ENABLED | false | NI-03 Device Card surface |
| WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED | false | Service Intelligence Device Card surface |
| NETWORK_SERVICE_MATERIALIZATION_MODE | off | NI-04 off / shadow / serve |
| NETWORK_SERVICE_MATERIALIZATION_DB_PATH | /opt/CaptivePortal/data/network_service_intelligence.sqlite3 | NI-04 materialized store |
| NETWORK_SERVICE_MATERIALIZATION_MAX_DB_BYTES | 536870912 | NI-04 default budget; admitted range 128 MiB..2 GiB |

Current production state must be host-verified independently of these repository
defaults. Network Intelligence settings are not automatically Admin Settings
writable controls.
<!-- NETWORK-INTELLIGENCE-V1:END -->
Baseline: `main@27087766d3f2e104a44da3f36aa6e72a082b12de`

Authoritative code: `app/config.py`, `app/settings.py`, `.env.example`.

The application does not automatically load `.env.example`. Production values come from process environment/approved secret handling.

## Core/CAPPORT deployment-owned startup configuration

These five optional keys remain outside writable Admin Settings and SettingsStore.
Absent keys preserve the old typed defaults. Explicit empty/invalid values fail
startup with a key-specific generic error, never a fallback, even if CAPPORT is
disabled. Parsing performs no interface, socket, Omada or network I/O.

| Key | Default when absent | Explicit grammar / runtime type |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Exact `127.0.0.1` or canonical dotted RFC1918 IPv4; string. No wildcard, DNS, IPv6, public/link-local or loopback alias. |
| `PORT` | `8088` | Canonical ASCII decimal `1024..65535`, no padding/sign/whitespace; integer. |
| `CAPPORT_SITE_ID` | `6a64f17630da7c70d232187a` | Exactly 24 lowercase hex characters; unchanged string, verified by operator against the selected Omada Site. |
| `CAPPORT_PUBLIC_BASE_URL` | `https://captivportal-navi.duckdns.org` | HTTPS ASCII DNS origin, optional canonical port `1..65535` and one final `/`; hostname lowercased and final slash removed. No IP literal/userinfo/path/query/fragment/escapes/control bytes. |
| `CAPPORT_ALLOWED_CLIENT_NETWORKS` | `("192.168.1.0/24", "192.168.8.0/22")` | CSV of 1..16 unique exact canonical IPv4/IPv6 CIDRs without spaces, host bits or `/0`; tuple of strings. CAPPORT derives strict typed networks for its unchanged source-IP check. |

`https://PORTAL.example:8443/` canonicalizes to `https://portal.example:8443`.
Site IDs and CIDRs are not trimmed, casefolded, repaired or widened. The typed
CAPPORT entrypoint also accepts a single CIDR string (not a CSV string) for
historical direct-call compatibility. Only process environment supplies overrides;
no dotenv loader, hot reload, new flag or Admin mutation is introduced. Activation
requires a separately authorized restart.

Independent Captiv-Prod examples `172.18.0.1:18089` and
`https://captivprod-navi.duckdns.org` are not defaults or deployability proof.
The existing VM/stores are untouched; this task introduces no data migration.
SysAdmin must separately verify D01 interface/port/TLS/guest routing, D02 NPM-only
default-deny isolation and forwarded-header sanitization, D03 actual Omada Site
and OpenAPI permissions. One-hop ProxyFix is unchanged; unit tests cannot prove
firewall/proxy isolation. `/.well-known/captive-portal` is not a new Flask route.

Portal Fingerprint's independently pinned old Site/scope/evidence endpoint remains
a separate compatibility HOLD for a new deployment. Sensor core-readiness defaults
also remain independently configured; this task does not make Fingerprint/NI ready.
See [CAPPORT](modules/capport.md) and [deployment](deployment.md).

## Device Fingerprint Evidence (default disabled)

## Sensor/Portal producer deployment configuration

DEPLOY-CONFIG-02 affects only startup parsers and the Sensor's fixed-name
preflight guard. These values are not main `app.settings`/Admin Settings,
registration, source binding or live identity switching. Existing enable flags
remain default **false**; absent overrides reproduce the entire typed config.
Changing process environment requires a separately authorized restart.

| Sensor suffix (`DEVICE_FINGERPRINT_SENSOR_`) | Exact legacy default |
| --- | --- |
| INTERFACE | `enp8s0` |
| PRODUCER_ID / CAPTURE_SOURCE_ID | `sensor-zefer-01` / `zefer-span-01` |
| SITE_ID / GUEST_CIDRS | `6a64f17630da7c70d232187a` / `192.168.8.0/22` |
| DHCP_SERVER_AUTHORITY / DHCP_OPTION54_AUTHORITY | `192.168.10.1` / `192.168.10.1` |
| EVIDENCE_BASE_URL | `https://192.168.0.202:9443/api/internal/device-fingerprint/v1` |
| CA_CERT_PATH | `/etc/captive-portal/device-fingerprint/sensor-ca.crt` |
| SPOOL_PATH | `/var/lib/captive-portal/fingerprint-sensor/spool.sqlite3` |
| EVE_SOCKET_PATH | `/run/captive-portal/fingerprint-sensor/suricata-eve.sock` |
| CORE_READY_HOST / CORE_READY_PORT | `127.0.0.1` / integer `8088` |

Sensor interface must be a 1..15-byte ASCII Linux name with alphanumeric first
character and only letters/digits/underscore/dot/hyphen, not `lo`/`any`/wildcard/path.
Preflight remains interface-relative: UP, no master/L3/default routes/forwarding,
DHCP disabled and no active DHCP client/NetworkManager profile. All runtime checks
and frozen BPF/selected-interface AF_PACKET binding remain; parser checks no NIC.
Readiness host is canonical private IPv4 or exact `127.0.0.1`, port canonical
ASCII decimal `1024..65535`. DHCP authorities are independently configured
canonical IPv4 unicast, not implicitly forced equal or RFC1918-only; actual DHCP
evidence and directed-broadcast/topology facts require separate operational proof.

| Portal suffix (`DEVICE_FINGERPRINT_PORTAL_`) | Exact legacy default |
| --- | --- |
| PRODUCER_ID / CAPTURE_SOURCE_ID | `portal-zefer-01` / `zefer-portal-http-01` |
| SITE_ID / GUEST_CIDRS / ALLOWED_SSIDS | `6a64f17630da7c70d232187a` / `192.168.8.0/22` / `Zefer_Parki` |
| EVIDENCE_BASE_URL | `https://192.168.0.202:9443/api/internal/device-fingerprint/v1` |
| CA_CERT_PATH / CREDENTIAL_PATH | `/etc/captive-portal/device-fingerprint/portal-ca.crt` / `/etc/captive-portal/device-fingerprint/portal.bearer` |

Both parsers require exact lowercase machine IDs and 24-hex Site, 1..16 canonical
nonoverlapping IPv4 CIDRs with no host bits/duplicates/empty members or `/0`.
Evidence URL: HTTPS valid ASCII DNS or canonical private IPv4/exact loopback,
optional canonical port `1..65535`, exact `/api/internal/device-fingerprint/v1`
path. Reject numeric IP aliases, controls/whitespace, userinfo, escapes, query,
fragment and other paths. Only one final slash may normalize. Portal SSIDs are
1..16 distinct case-sensitive exact strings of 1..32 UTF-8 bytes, no blank/control
or wildcard member. Missing SSID stays optional; no guest authorization change.
Portal queue/batch/age/coalescer/timeouts/cooldowns remain strictly pinned.
Disabled Portal ignores bad overrides; disabled Sensor ignores deployment strings
but retains original Wave-2 boolean validation. Sensor budgets/tuning stay unchanged.

Synthetic examples (not admitted producer identities or operational recommendations):
Sensor `enp1s0`, `172.18.0.1:18089`, `lab-sensor-02` / `lab-span-02`, Site
`aaaaaaaaaaaaaaaaaaaaaaaa`, scope `10.20.0.0/24`; Portal `lab-portal-02` /
`lab-portal-http-02`, same synthetic Site, SSID `Guest WiFi`, endpoint
`https://evidence.example:9443/api/internal/device-fingerprint/v1`.
No bearer is configured inline: Sensor uses only systemd LoadCredential
`CREDENTIALS_DIRECTORY/device-fingerprint-bearer`; Portal uses an absolute
protected external file. CA trust, SAN/expiry, receiver peer policy and the exact
registered producer/token/Site/source/kinds/guest scope are independent gates.

Do not relabel/replay/purge an old Sensor spool under new identity/scope. New
installation needs its own empty spool; changes to a nonempty spool are operational
HOLD pending lineage/cutover. Parser never opens a spool or auto-registers a source.
Receiver acceptance is not F-B1/source-health/clock/classification admission.
Core readiness is raw TCP only, not HTTP health; SysAdmin must prove trusted local
Sensor-to-Core path and negative Guest/WAN reachability. NIC override does not
change Suricata/NI/systemd/NPM. No current production activation is authorized.

### Evidence service configuration (unchanged)

`DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false` is the repository default. The
module uses only `DEVICE_FINGERPRINT_*`: DB/lock paths, bind address/port,
direct-TLS certificate/key paths, API management CIDRs, external producer JSON,
retention and bounded request/storage limits. Defaults are in `.env.example`
and `docs/modules/device-fingerprint.md`.

When enabled, absolute distinct DB/lock and TLS paths, valid direct-peer CIDRs,
and one to 32 strict producer records are mandatory. Bearer secrets and TLS
private keys are provisioned outside Git. Source-health retention is fixed at
30 days and has no environment override.

| Variable | Repository default |
|---|---|
| `DEVICE_FINGERPRINT_DB_PATH` | `/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3` |
| `DEVICE_FINGERPRINT_WRITER_LOCK_PATH` | `/opt/CaptivePortal/data/device_fingerprint_evidence.writer.lock` |
| `DEVICE_FINGERPRINT_BIND_ADDRESS` | `192.168.0.202` |
| `DEVICE_FINGERPRINT_PORT` | `9443` |
| `DEVICE_FINGERPRINT_TLS_CERT_PATH` | `/etc/captive-portal/device-fingerprint/server.crt` |
| `DEVICE_FINGERPRINT_TLS_KEY_PATH` | `/etc/captive-portal/device-fingerprint/server.key` |
| `DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS` | `192.168.0.0/24` |
| `DEVICE_FINGERPRINT_PRODUCERS_JSON` | empty/disabled-only |
| `DEVICE_FINGERPRINT_RETENTION_DAYS` | `30` (range `1..90`) |
| `DEVICE_FINGERPRINT_MAX_FUTURE_SKEW_SECONDS` | `120` (range `0..600`) |
| `DEVICE_FINGERPRINT_MAX_DELAYED_EVENT_AGE_SECONDS` | `86400` (range `60..604800`) |
| `DEVICE_FINGERPRINT_MAX_DB_BYTES` | `1073741824` (range `67108864..8589934592`) |
| `DEVICE_FINGERPRINT_MAX_HTTP_REQUEST_BYTES` | `1048576` (range `65536..4194304`) |
| `DEVICE_FINGERPRINT_MAX_EVENTS_PER_BATCH` | `100` (range `1..500`) |
| `DEVICE_FINGERPRINT_MAX_PAYLOAD_BYTES` | `8192` (range `256..65536`) |
| `DEVICE_FINGERPRINT_MAX_CONCURRENT_INGEST_REQUESTS` | `2` (range `1..8`) |

### Portal fingerprint producer (default disabled)

`DEVICE_FINGERPRINT_PORTAL_ENABLED=false` leaves the main portal without a
Task-03 worker or I/O. When enabled, the isolated configuration is frozen to
producer `portal-zefer-01`, capture source `zefer-portal-http-01`, the production
Site/guest CIDR/SSID scope, a 256-event queue, 50-event batches, 300-second
queue age, six-hour coalescing, `(0.5s, 2.0s)` HTTPS timeouts, and 30/300-second
cooldowns. The full exact variable list is in `.env.example`; the Bearer value
is never stored there. See `docs/modules/device-fingerprint-portal.md`.

## Core / Omada

| Setting | Repository default / requirement | Notes |
|---|---|---|
| `HOST` | `127.0.0.1` | application bind |
| `PORT` | `8088` | application port |
| `DEBUG` | `false` | no reloader in `run.py` |
| `VERIFY_SSL` | `true` | mandatory Omada strict policy; no writable/unsafe toggle |
| `OMADA_URL` | `https://Omada:8043` required externally | only the approved HTTPS origin; case-normalized |
| `OMADA_TLS_TRUST_ANCHOR_PATH` | empty / required externally | absolute root-owned public PEM outside Git; no controller private key |
| `OMADA_TLS_TRUST_ANCHOR_SHA256` | empty / required externally | approved DER SHA256 from independent Owner/SysAdmin export, not network TOFU |
| `OMADA_ID` | required external | controller id |
| `OMADA_CLIENT_ID` | required external | OpenAPI client |
| `OMADA_CLIENT_SECRET` | required secret | never commit/log |
| `OMADA_WEBHOOK_SITE_ID_MAP_JSON` | `{}` in example | Site-name → Site-id normalization context |

Provider construction fails closed when required core Omada configuration is missing/invalid.

### QIO-01B — Option B only (activation remains HOLD)

The accepted startup settings mapping supplies one immutable strict Omada TLS
policy. No request rereads the environment, accepts a certificate from a network
handshake, changes DNS/SNI/Host, or falls back to HTTP/disabled verification.
`OMADA_URL` must have scheme HTTPS, host `Omada`, explicit port 8043, no credentials,
query, fragment or non-root path. A trailing root slash/case is normalized to
`https://Omada:8043`. IP/localhost/other-controller aliases are rejected.

At provider construction the public PEM must be one parseable, valid, self-signed
certificate with DNS SAN Omada and server-auth EKU, with the independently approved
DER fingerprint. It must be a regular single-link non-symlink file, owned by root,
not group/other-writable, readable by the application, and outside the repository.
Linux permission attestation is mandatory; an unsupported non-POSIX deployment
fails closed rather than pretending POSIX mode bits attest a Windows ACL.
Pure Settings semantic validation remains file/network-I/O-free; actual file
admission is the provider's separate preflight before any Omada operation.

The provider-local SSLContext contains only that admitted public leaf; it does
not load certifi/system roots. Chain, reference hostname and validity are checked
on each fresh connection. All twelve token/API request sites, including pending
sessions and observations, use the same transport. Sessions are operation-local
(as with the prior top-level Requests calls), without long-lived pooled trust.
Environment proxies, netrc, REQUESTS_CA_BUNDLE and CURL_CA_BUNDLE are not consulted
for Omada; explicit proxy/verify/Host/redirect overrides are rejected. Other
Requests clients are unchanged. No redirect (even same-origin) is followed.

TLS/policy/redirect failures are sanitized, non-authoritative failures. In
particular, get_sites raises ControllerError on failed authority (including token,
TLS, DNS/timeout, HTTP/API failure or invalid site-list shape) instead of returning
authoritative `[]`; a valid empty API result still returns `[]`. This assigned
legacy boundary is the only success/error parsing change. Existing API paths,
methods, payloads, timeouts, cache concurrency and other response parsing and
non-TLS timeout/network classifications remain.
Other Result-based methods return failure, never a successful empty snapshot.

The first TLS failure and every reason transition/recovery is logged without
URL, token, secret or PEM. Identical failures are aggregated for a monotonic
60-second heartbeat with repeated counts and previous reason; individual failed
operation results are never suppressed. Runtime tls_health describes only the
last connection state, not authorization readiness or all-system health.
Admin's existing read-only TLS field additionally exposes strict verification
mode, approved-leaf policy/source and "verification required on every connection";
it discloses neither PEM/path nor secrets, and adds no mutation control.

Admission of the real leaf/name/IP, independent full/security/staging/performance
acceptance, and production activation are Tech Lead/Owner gates, not implied by
the lab code. Quiet logs are not proof of physical HDD savings. See the QIO-01B
section in deployment.md for the single-path installation/rotation/rollback plan.

## Feature groups

### Public counters / telemetry

Repository code defaults:
- `PORTAL_COUNTER_ENABLED=true`
- `PORTAL_COUNTER_API_ENABLED=true`
- `PUBLIC_TRAFFIC_COUNTER_ENABLED=true`
- `AUTH_TELEMETRY_ENABLED=true`

Storage defaults:
- `/opt/CaptivePortal/data/portal_counter.db`
- `/opt/CaptivePortal/data/public_traffic.sqlite3`
- `/opt/CaptivePortal/logs/auth_telemetry.log`

### Authorized Snapshot

Prefix: `VISITOR_SNAPSHOT_*`

Repository default: `VISITOR_SNAPSHOT_ENABLED=false`.

Important capacity/lifecycle settings:
workers, pending jobs, max job age, request timeout, retry delays, rotation, shutdown timeout.

### Visitor Registry

Prefix: `VISITOR_REGISTRY_*`

Repository default: disabled.

Controls DB path, scan interval, max line size and shutdown timeout.

### Visit Lifecycle

Prefix: `VISIT_LIFECYCLE_*`

Repository default: disabled.

Key groups:
- DB and normalized webhook source;
- reader line/byte/time budgets;
- reconciliation interval/batch;
- pending offline batch/grace;
- writer coordination (`*_WRITER_SLOT_WAIT_MS`);
- SQLite busy timeout;
- bounded Visit Start attempts/total budget;
- shutdown and offline evidence drift/skew bounds.

### Observation Foundation

Prefix: `OBSERVATION_*`

Repository default: `OBSERVATION_FOUNDATION_ENABLED=false`.

Client/AP subcollectors default enabled **inside the disabled foundation**.

Key groups:
- Site/SSID scope;
- DB;
- dynamic/config retention;
- client interval/pagination;
- AP inventory/dynamic/config intervals and request budgets;
- rate gap;
- cleanup;
- shutdown.

### Current State

Prefix: `CURRENT_STATE_*`

Repository default: disabled.

Key groups:
- Site scope;
- exact case-sensitive `CURRENT_STATE_CLIENT_SSIDS_JSON`;
- client/AP polling and pagination;
- separate client/AP fresh/stale thresholds;
- short history retention and hard client-row cap;
- cleanup;
- SQLite busy timeout;
- shutdown.

Repository defaults include 48h history retention.

### Analytics

Prefix: `ANALYTICS_*`

Repository default: foundation disabled; wireless/visit submodules default true if foundation is enabled.

Controls:
query limits/window/deadline, quality gap, wireless sample/window rules, counter gap, AP join lag, optional RSSI/SNR thresholds, visit cohort/window.

### Analytics internal API

Prefix: `ANALYTICS_API_*`

Repository default: disabled.

Requires external bearer token when enabled, plus network/Site allowlists, concurrency and response-size limits.

### Admin Web

`WEB_ADMIN_DB_SERVICES_ENABLED=false` is an independent exact lowercase `true|false`
startup flag, default OFF. It is not writable through Settings or Features. An
operator must explicitly grant `admin.read.operations` in
`WEB_ADMIN_GLOBAL_CAPABILITIES`; default grants are unchanged. The GLOBAL page is
`/admin/db-services`, with one read endpoint `/admin/api/v1/operations/db-services`.
Activation additionally requires the root-owned, non-group/world-writable file
`/etc/captive-portal/admin-db-services-v1.json` and protected ancestors. Its closed
schema is `admin.db-services.bindings.v1` with exactly nine `services` entries
(`id,intent`) and seventeen `databases` entries (`id,path,intent`). Service intents
are `run|disabled|maintenance|unknown`; database intents are
`expected|optional_disabled|unknown`. No extra keys, duplicates, selectors, secrets
or implicit path defaults are accepted. Database paths have a direct parent in
`/opt/CaptivePortal/data`, `/var/lib/captivprod-sensor` or
`/var/lib/captivprod-evidence`, using the exact catalog filename. The attested
special bindings are `fingerprint_evidence` →
`/var/lib/captivprod-evidence/evidence.sqlite3`, `network_attribution` →
`/var/lib/captivprod-sensor/network_attribution.sqlite3`, and `sensor_spool` →
`/var/lib/captivprod-sensor/spool.sqlite3`; legacy or cross-root aliases for
these stores are rejected. The other fourteen deployment bindings and all intents
must be independently verified by the operator; catalog/default paths are not
evidence that a file exists or is active. Unverified intent stays `unknown`.
Denied sensor-directory metadata remains unknown/unavailable, not healthy;
no ACL or service-user privilege change is implied by source integration.
The manifest is read once at composition. Missing/invalid bindings disable only
Operations, not Auth or other Admin pages. This repository change does not create
the operator file, grant the permission, or activate the flag.

The same snapshot includes `admin.operations.topology.v1`: 31 code-owned nodes
and 45 structural relations, with no extra flag, capability or acquisition.
R1 edges are not live-flow evidence (`flow_evidence=not_instrumented`); there is
no active-flow animation. Operational Data Flow appears between the four Summary
tiles and the detailed Services/Databases inventories. It adds no SQLite opens,
systemd commands, filesystem sampling or network calls. Future live-flow R2
telemetry requires a separate architecture decision.

Prefix: `WEB_ADMIN_*`

Repository default: disabled.

When enabled requires external username/password hash/Site configuration.

Security and capacity groups:
- source networks;
- Site allowlist/default Site;
- HTTPS requirement;
- idle/absolute session timeout;
- login rate limits/lock;
- pre-auth CSRF;
- bounded session/login-tracker stores;
- request/query/cursor/filter/response limits;
- bounded concurrent queries and query deadline.

At this baseline `.env.example` includes:
`127.0.0.1/32,::1/128,10.8.0.0/24`
for `WEB_ADMIN_ALLOWED_NETWORKS`, including the owner-approved VPN network.

### Device Current Context

Feature flag:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=false
```

Repository default remains safe/opt-in `false`.

Activation dependency:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=true
requires WEB_ADMIN_ENABLED=true
```

Owner-confirmed production state on 2026-09-09:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=true
```

This flag controls the Current Device Context exposure/read route only. It does
not start Current State, change its collectors, add persistence or modify the
historical Device Card.

Repository default `false` must not be interpreted as production disabled.

### Home Live

Prefix: `WEB_ADMIN_HOME_LIVE_*` and `WEB_ADMIN_CURRENT_STATE_PAGE_SIZE`.

Repository default: disabled.

### Home Traffic

Prefix: `WEB_ADMIN_HOME_TRAFFIC_*`

Repository default: disabled.

Controls refresh/request timeout/page size plus fresh/stale age and maximum AP skew.

### Home Activity

Prefix: `WEB_ADMIN_HOME_ACTIVITY_*`.

Repository default: `WEB_ADMIN_HOME_ACTIVITY_ENABLED=false`.

Current contract:
- requires Admin Web + Home Live + enabled Current State scope when activated;
- guest SSIDs come from canonical `CURRENT_STATE_CLIENT_SSIDS_JSON`; no second Activity SSID list exists;
- `WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON` supplies per-Site `timezone`, `visits_coverage_from_utc`, `traffic_coverage_from_utc`;
- Activity-only invalid configuration fails open relative to the rest of Admin/guest authorization.

Confirmed production Site context on 2026-08-26:
- Site `6a64f17630da7c70d232187a`;
- timezone `Asia/Baku`;
- Visits coverage `2026-08-26T17:46:55.982Z`;
- Traffic coverage `null`.

### Home System Health

Prefix: `WEB_ADMIN_HOME_HEALTH_*`.

Repository defaults:

```text
WEB_ADMIN_HOME_HEALTH_ENABLED=false
WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS=60
WEB_ADMIN_HOME_HEALTH_REQUEST_TIMEOUT_SECONDS=30
WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS=86400
```

The feature is Admin-only/read-only and fails open relative to guest
authorization. Repository default `false` is not evidence of production
disablement.

### Home AP-24H

Repository defaults:

```text
WEB_ADMIN_HOME_AP_24H_ENABLED=false
WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS=120
WEB_ADMIN_HOME_AP_24H_REQUEST_TIMEOUT_SECONDS=30
```

The read model is bounded/read-only over persisted Current State + Observation
facts. It adds no query-time Omada path, DB or collector.

### Home AP-24H telemetry

Prefix: `WEB_ADMIN_HOME_AP_24H_TELEMETRY_*`.

Repository default: `WEB_ADMIN_HOME_AP_24H_TELEMETRY_ENABLED=false`.

The worker also requires active Admin Web, active Home AP-24H, the shared Admin
query controls and available Authorization Telemetry. The initial delay is
bounded to `0..3600` seconds and the fixed-delay interval to `60..3600`
seconds; repository defaults are `15` and `120` seconds respectively. Invalid
enabled telemetry configuration fails closed for this worker only.

### Traffic Section

Prefix: `WEB_ADMIN_TRAFFIC_*`.

Repository defaults:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=false
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=false
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=30
```

Production state 2026-09-08:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=true
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=true
```

Feature dependencies:

```text
History requires Admin + Traffic.
Statistics requires Admin + Traffic + History.
Peak requires Admin + Traffic + History + Statistics.
Traffic by AP requires Admin + Traffic + History.
Independent ranges requires Admin + Traffic + History.
AP Traffic Share requires Admin + Traffic + History + Independent ranges.
Online Guests Traffic requires Admin + Traffic only.
Completed Guest Session Traffic requires Admin + Traffic only; it reads Visit +
Observation persistence and does not require Historical Traffic Projection.
Traffic Evidence requires Admin + Traffic and its endpoint authorizes both
`admin.read.overview` and `admin.read.devices`.

Repository defaults remain opt-in/off for Online Guests, Completed Sessions and
Traffic Evidence. Owner-confirmed production activation is `true` for all three.
```

Independent ranges does **not** require every optional historical product to be
enabled. It changes historical product range/request orchestration for whichever
historical products are enabled.

These are product-exposure/orchestration flags. They do not start/stop Observation,
`CurrentTrafficReadService` or `HistoricalTrafficReadService`.

### Historical Traffic projection

The derived projection has two independent, repository-default-off controls:

```text
TRAFFIC_PROJECTION_ENABLED=false
TRAFFIC_PROJECTION_DB_PATH=/opt/CaptivePortal/data/traffic_projection.sqlite3
TRAFFIC_PROJECTION_WRITER_LOCK_PATH=/opt/CaptivePortal/data/traffic_projection.writer.lock
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=false
```

The worker is a separate process (`python -m app.traffic_projection.cli run`) and
reads the existing Observation database in SQLite read-only/query-only mode. The
Admin read flag switches History, Statistics, Peak, Traffic by AP and AP Share as
one bundle. It never falls back automatically to raw reconstruction. Build,
`mark-ready`, `activate`, `repair-site`, and cleanup are explicit CLI operations;
production execution requires separate Owner authorization.

Current Network Throughput shared policy remains:

```text
fresh max age = 90s
stale boundary = 180s
max AP skew = 60s
```

Historical product ranges:

```text
24h
7d
```

With independent ranges enabled, History, Statistics, Peak, Traffic by AP and AP Traffic Share each own independent page-local selected/applied range state. Current Network Throughput remains range-insensitive.

At acceptance of `TASK-TRAFFIC-RANGE-01`, the historical limits were:

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS=10
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS=10
Traffic browser request timeout=20s
Admin concurrency=unchanged
```

RANGE-01 itself did not increase these limits.

Current production baseline after `TASK-ADMIN-PROD-BASELINE-01` (2026-09-05):

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS=3
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS=25
dependent Admin/Home request timeouts=30s
WEB_ADMIN_MAX_CONCURRENT_QUERIES=4
```

Repository default=false must not be rewritten as production disabled.

### Historical Traffic projection — production lifecycle state

Repository defaults remain safe/off unless separately configured:

```text
TRAFFIC_PROJECTION_ENABLED=false
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=false
```

Repository default values do not describe current production runtime.

Owner-confirmed production recovery on 2026-09-11 ended with:

```text
traffic-projection.service=active + enabled
projection_version=historical_traffic_projection.v1
version_status=active
Site health=healthy
```

Canonical worker runtime environment is supplied by:

```text
/etc/systemd/system/traffic-projection.service
EnvironmentFile=/etc/default/captive-portal
User=admin
Group=admin
WorkingDirectory=/opt/CaptivePortal
ExecStart=/usr/bin/python3 -m app.traffic_projection.cli run
```

Production CLI/repair must use the canonical worker environment rather than an
arbitrary interactive shell environment. Secret values are never recorded in KB.

### TASK-TEST-BASELINE-CLEANUP-01

This production delivery changed no configuration contract:

```text
configuration changes=NO
feature flag changes=NO
systemd unit changes=NO
DB/schema changes=NO
```

### Device Type normalization / presentation tasks

`TASK-DEVICE-TYPE-NORMALIZATION-01` and
`TASK-WEB-DEVICE-TYPE-PRESENTATION-01` introduce no new configuration key,
feature flag, DB migration or systemd setting.

### Pending Session Cleaner

Prefix: `PENDING_SESSION_CLEANER_*`

Repository default: disabled.

Controls SSID scope, scan budget, uptime/grace, request/retry/verification, pagination, per-scan/per-MAC action limits, cooldown, audit rotation and shutdown.

## Production-state rule

Never write:
`repository default=false ⇒ production disabled`.

Never write:
`historical production acceptance ⇒ currently healthy`.

Production EnvironmentFile/systemd values are host facts and must be verified separately without printing secrets.

### Device Fingerprint sensor

All `DEVICE_FINGERPRINT_SENSOR_*` variables are parsed exclusively by
`app/device_fingerprint_sensor/config.py`. The main application settings path
does not parse them. Repository default is
`DEVICE_FINGERPRINT_SENSOR_ENABLED=false`. The Bearer credential is supplied
through systemd `LoadCredential`; it is never stored in `.env.example`.

<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:BEGIN -->
## Device Fingerprint configuration map

Repository configuration exposes separate paths for the four ownership domains:

```text
DEVICE_FINGERPRINT_EVIDENCE_DB_PATH
  /opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3

DEVICE_FINGERPRINT_CLASSIFICATION_DB_PATH
  /opt/CaptivePortal/data/device_fingerprint_classification.sqlite3

DEVICE_FINGERPRINT_CONTROL_PLANE_DB_PATH
  /opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3

DEVICE_FINGERPRINT_INTEGRATION_DB_PATH
  /opt/CaptivePortal/data/device_fingerprint_integration.sqlite3
```

`DEVICE_FINGERPRINT_INTEGRATION_ENABLED` remains repository-default false; a
repository default is not evidence of the live production flag.

The current 1-GiB `SnapshotExecutionPolicy.process_memory_guard_bytes` is a
versioned classifier/foundation policy artifact, not a replacement environment
variable and not a 1-GiB reservation.
<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:END -->

## Settings Foundation V1

`WEB_ADMIN_SETTINGS_ENABLED=false` is the default. Disabled startup performs no
SettingsStore I/O and keeps base settings authoritative. `SETTINGS_DB_PATH`
defaults to `/opt/CaptivePortal/data/settings.sqlite3`; these two bootstrap
controls are not editable Settings. Provision the parent directory externally;
the application does not create it. Exact accepted schema-v1/v2/v3 databases
are migrated transactionally to v4 during Settings-enabled startup; incompatible
or corrupt stores are rejected.

When enabled and available, GLOBAL persisted overrides precede explicit
environment values, which precede the shared typed repository defaults. An
invalid configuration or unavailable SettingsStore aborts enabled startup
before the shared Omada provider or any Controller-dependent worker starts.
There is no automatic base-settings fallback when Settings is enabled.

The unchanged ordered General integer allowlist is exactly:

| Key | Default | Bounds |
| --- | ---: | --- |
| WEB_ADMIN_DEVICE_PAGE_SIZE | 100 | 1–500 |
| WEB_ADMIN_VISIT_PAGE_SIZE | 100 | 1–500 |
| WEB_ADMIN_OBSERVATION_PAGE_SIZE | 100 | 1–500 |
| WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS | 24 | 1–168 |
| WEB_ADMIN_CURRENT_STATE_PAGE_SIZE | 100 | 1–250 |
| WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE | 100 | 1–250 |
| WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS | 60 | 60–300 |
| WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS | 60 | 60–300 |
| WEB_ADMIN_TRAFFIC_REFRESH_SECONDS | 60 | 60–300 |
| WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS | 60 | 60–300 |
| WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS | 60 | 60–300 |
| WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS | 120 | 60–600 |

SQLite schema v4 retains immutable generations, complete typed per-generation
override sets, mutation audit, successful idempotency responses and activation
events, plus the mutable `captive-portal.service` effective-generation target.
Generation 0 is created with `system / settings_bootstrap`, no overrides, no
mutation audit and no idempotency record. Foreign keys are enabled and the
SQLite busy timeout is 1000 ms.

The common definition registry has 29 entries: the twelve General integers
above and exactly three Controller strings (`OMADA_URL`, `OMADA_ID`,
`OMADA_CLIENT_ID`) and fourteen public Portal strings. The same Store, generation head and CAS authority serve
all domains. Idempotency keys are scoped by domain. The transactional v1→v2→v3→v4
migration preserves generation IDs, original audit/activation history and exact
successful General response bytes; migration itself creates no generation,
audit or activation event.

A successful Save persists configuration only. All keys require a main-service
restart; the Settings API cannot restart services or hot-reload configuration.
The main runtime composes one immutable startup snapshot and durably adopts
that exact generation before starting Controller-dependent workers or serving
HTTP. Operational source degradation is not
Settings activation failure. No service or production activation is performed
by this implementation.

## Omada Controller Settings — non-secret settings and write-only Stage 4

`WEB_ADMIN_SETTINGS_ENABLED` also gates the GLOBAL Controller page/read/write API.
The main process builds one immutable `OmadaControllerRuntimeConfig` from the
ordinary resolved settings plus one separate secret resolution, injects it into the shared provider and derives a
separate secret-free public snapshot for Admin. The provider no longer reads
settings independently. `create_app(controller=None)` retains compatibility
by using the same canonical builder on its already-resolved local mapping;
an injected controller is never rebuilt.

`OMADA_URL`, `OMADA_ID`, `OMADA_CLIENT_ID` and `OMADA_CLIENT_SECRET` remain required.
Trim and OAuth/request semantics are retained; QIO-01B now restricts the runtime
origin to `https://Omada:8043` and requires an explicit admitted strict TLS policy.
The selected writable value is normalized by the same canonical Omada owner:
persisted override > explicit startup environment > repository default.
The immutable effective snapshot retains the adopted generation and each
writable value's `persisted_override`, `environment` or `repository_default`
provenance. No environment reread occurs in an Admin request.
`VERIFY_SSL=true` is now a mandatory repository constant; QIO-01B permits no
disabled-verification compatibility fallback.
Client Secret is represented only by presence/source, never its value or any
derived length/hash/mask. `OMADA_CLIENT_SECRET` and `VERIFY_SSL` have no ordinary
writable definition. Only the three non-secret Controller strings enter ordinary overrides/audit paths.
The Client Secret uses the separate Stage-4 encrypted boundary below. General reads
and successful General receipts still contain exactly the twelve integers.

Controller Save persists configuration, not running provider state. The GLOBAL
`admin.write.settings.controller` capability is independent of General write
authorization. A successful Save requires an externally authorized/performed
`captive-portal.service` restart to activate; no Admin restart control, Test
Connection, hot reconnect, live-health claim, deployment or production
activation is supplied here.

After trustworthy startup adoption, Store loss does not invent configured
truth: the Controller V3 read can return effective-only state with configured
fields/pending state null, while writes return `503 settings_store_unavailable`.

### Stage-4 Controller secret boundary

`WEB_ADMIN_GLOBAL_CAPABILITIES` is a strict comma-separated ASCII startup grant.
Its default grants `admin.read.settings.global`, `admin.write.settings.global`,
`admin.read.settings.controller`, `admin.write.settings.controller` only.
An operator must explicitly grant `admin.write.settings.controller.secret` in
addition to Controller read for write-only secret management; ordinary Controller
write does not grant secret write. Grants are captured in each new login session.
Empty/unknown/duplicate/whitespace-bearing tokens fail closed. Restart and a new
login are required for a deployment grant change; this is not a managed setting.

Controller v3 exposes independent infrastructure availability for ordinary and
secret mutations. The secret row exposes configured/effective presence and source,
managed-override presence, pending replacement and secret-store state, never value,
mask, length, internal version ID, hash or ciphertext. A secret-only pending change
counts as one pending Controller setting; unrelated generations do not.

`POST /admin/api/v1/settings/controller/client-secret/generations` accepts exactly
`replace_secret` with a new `secret`, or `clear_secret_override` without it, under
strict JSON, session CSRF, global ETag/CAS and UUIDv4 idempotency. Receipts contain
only safe operation/generation/restart facts; replay returns the original receipt
at HTTP 200. HMAC-SHA256 fingerprints use a separate HKDF key, principal, operation
and idempotency key. The same global generation is shared by all mutation domains.

Schema v3 adds immutable secret bindings and safe audit, encrypted live versions,
and typed domain-scoped idempotency fingerprints. Migration preserves history and
exact old receipts and creates no new generation, secret, binding or audit. Generic
generation creation copies secret ownership. Only configured/effective versions
remain live after replace/clear/adoption; historical bindings may outlive ciphertext.
Logical deletion does not guarantee forensic erasure from SQLite/backups/storage.

The external raw 32-byte master key is code-owned at
`/etc/captiveportal/omada-controller-secret-master.key`; HKDF-SHA256 separates
AES-256-GCM and idempotency keys. Each version has UUIDv4, a random 12-byte nonce,
exact AAD, random-padded 4100-byte plaintext frame and 4116-byte ciphertext/tag.
`cryptography>=3.4.8` is required and the implementation supports 3.4.8.
Managed ownership outranks environment/repository default and fails closed on
security, reference or decryption failure without fallback. Without a managed
binding, a valid deployment secret can run even if the managed secret store/key is
unavailable. There is no live credential test, hot reconnect or restart authority.

## Guest Portal presentation — Settings Stage 5

The ordinary GLOBAL registry now includes exactly fourteen public string settings:
`PORTAL_UI_TITLE_AZ/RU/EN`, `PORTAL_UI_GREETING_AZ/RU/EN`,
`PORTAL_UI_DESCRIPTION_AZ/RU/EN`, `PORTAL_SUPPORT_PHONE`, `PORTAL_SUPPORT_EMAIL`,
`PORTAL_SUPPORT_WHATSAPP_URL`, `PORTAL_SUPPORT_TELEGRAM_URL`, and
`PORTAL_SUPPORT_FACEBOOK_URL`. Each uppercase key is its environment variable;
the runtime mapping uses its lowercase name. `.env.example` lists exact defaults.
Code-owned `PORTAL_SETTING_DEFAULTS` is the single default authority.

Persisted override wins over explicit environment, then the repository default.
Clear Override removes the persisted value; it does not write a default.
Branding is NFC plain text, with no trimming/normalization: title 1–80,
greeting 1–120, description 1–400 Unicode code points. Descriptions allow LF and
at most four lines; edge whitespace, C0/C1 controls and bidi controls are rejected
(LF is the description exception). HTML-like text is valid and escaped literally.

Support values can be exactly empty to hide that contact. Phone uses `+` and
ASCII digits/spaces with 8–15 digits; email is ASCII without display names or
query parameters. Social links require exact HTTPS authorities (`wa.me`, `t.me`,
`facebook.com`/`www.facebook.com`), restricted paths, no userinfo/port/fragment,
and no query except Facebook's single `locale` parameter. Server-derived
`tel:`/`mailto:` links and escaped HTTPS values are the only link projections.

One validated, immutable `PortalTemplatePresentationV1` is built during startup
and shared by normal Portal, CAPPORT, discovery and controlled-error HTML. Only
the nine branding translations are overlaid; other full-catalog translations,
Auth, counters and JSON contracts are unchanged. Requests do not read Settings
or environment. Invalid Portal composition records the safe failed-adoption
category `portal_configuration_adoption_failed` and never advances effective
generation or serves HTTP. An already adopted projection remains usable during
SettingsStore outages.

Portal reads/mutations/rendering do not access the Controller secret repository.
Portal candidate validation checks General/Admin values, canonical non-secret
Controller prerequisites and all fourteen Portal values. A new generation carries
its parent secret binding unchanged without decrypting it. General/Controller
full secret validation and Stage-4 fail-closed startup remain unchanged.
### NI-01 ingestion hot path — PERF-IO-NI01-A

`NETWORK_METADATA_IO_HOTPATH_V1_ENABLED` is an independent process-startup
boolean, **default OFF** (unset or literal `false`). Only lowercase `true`
and `false` are accepted when `NETWORK_METADATA_ENABLED=true`; malformed
values cause controlled NI-01 startup failure. Disabled NI-01 does not parse it.

The single switch enables all three A optimizations together: an exact
generation/start-offset range probe before normalization plus an independent
probe under `BEGIN IMMEDIATE`; a validated connection-owned immutable insert
column allowlist; and one fault UPSERT per actually reached batch-local group.
Any overlap uses the original ordered per-record identity checks.

OFF preserves the legacy SQL path and omits the new flag from canonical
configuration-digest inputs. ON includes `io_hotpath_v1_enabled=true` in that
digest for explicit run lineage. There is no Admin/runtime toggle; changing
the environment requires a separately authorized controlled restart.

SQLite V1 schema/indexes, WAL/FULL durability, source/replay/checkpoint semantics,
health, event-count telemetry and all downstream read contracts are unchanged.
Package B retention optimization is not implemented by A.

This opt-in reduces measured SQL statement amplification only. Physical IOPS
or host-load improvement is not established by statement counts. Publication
does not authorize production activation; independent Tech Lead release and
performance checks plus Owner authorization remain required.
