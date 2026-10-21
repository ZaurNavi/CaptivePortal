# Captiv-Prod — Omada, Evidence, Suricata/EVE and NPM preinstall progress

Date: 2026-10-16, Asia/Baku. New host: `captiv-prod` 192.168.0.99.

## Accepted baseline

NET-01 LIVE ACCEPTED, active firewall/watchdog, reboot PASS; exact verifier PASS at start and after credential preparation. Prior frozen NET-01 artifacts retained. Old 192.168.0.202/.222 and Cisco unchanged.

## Omada

New Omada v5.14.32.3 running; its `/api/info` returns `errorCode=0`, controller ID `68ba0bb73ec9f9f0add0a21382f1b810` (NOT a Site ID). TLS leaf fingerprint `EE:07:E9:1D:2B:A9:62:81:3E:EA:10:23:E2:66:72:BC:76:1E:21:A9:61:CF:5D:E4:6F:14:80:89:D3:BC:28:DB`; DNS SAN `Omada`; prior verified TLS test with pinned cert and SNI `Omada` PASS. Read-only localhost MongoDB `omada.site` has one Site `_id=6acbd7ed0e281b36c6c133f5`, `name=Zefer_Parki`; this is target-DB evidence, NOT authenticated OpenAPI confirmation. DB metadata-only inventory: 4 AP records (`AP-1` EAP613, `AP-2` EAP613, `AP-3` EAP225, `AP-4` EAP110-Outdoor), not proof of online or adopted devices; 2 SSID records (`Zefer_Parki` and `Welcome`). `Zefer_Parki` has `portal_enable=true`, `vlan_enable=false` even though stored `vlan_setting.vlan_id=20`; do not infer active VLAN20 tagging. Portal profile `Zefer` is enabled, HTTPS redirect flagged on. Two inherited OpenAPI applications named `Repeater Scanner` and `Portal` exist with broad admin_id role metadata. Their secrets were NOT read and no authenticated OAuth check was done. Dedicated minimally scoped credential and read-only API confirmation of AP/SSID/Hotspot/permissions remain HOLD. No historical Site ID used or AP adoption.

## Evidence Receiver

Prepared on actual target:
- `captiv-evidence` independent non-login OS account (UID 996).
- `/etc/captive-portal/device-fingerprint` and `/tls` root-owned mode 0700.
- Dedicated ECDSA P-256 root CA, server leaf `SAN IP:127.0.0.1`, EKU serverAuth, CA signature verify PASS. Server leaf valid to 2027-01-14T07:23:17Z, SHA-256 fingerprint `28:0D:A2:90:E3:72:22:0F:42:6C:66:6C:70:79:FA:15:7E:2A:28:67:98:05:EF:35:11:16:57:D3:51:A5:26:D2`.
- Root-only key files 0600, independent bearer tokens for Sensor and Portal 0600, values NEVER disclosed; must later deliver through scoped systemd credentials and bind to actual registered producers.
- Server PKI source CA/leaf verified at `/etc/captive-portal/device-fingerprint/tls`; explicit SAN `IP Address:127.0.0.1` PASS. Omada self-signed TLS leaf separately fingerprint pinned in root-owned `/etc/captive-portal/omada-trust/omada-leaf-pinned.pem`, exact SAN `DNS:Omada` verified. Actual curl `--cacert` + `--resolve Omada:8043:127.0.0.1` `/api/info`: HTTP 200, `ssl_verify_result=0`, `errorCode=0`. The real receiver CLI exists in approved CaptivePortal Git `7e84bc563f1b6dd3d72da66ae25849d9a7d96540`: `app.device_fingerprint.cli`. It requires `DEVICE_FINGERPRINT_PRODUCERS_JSON` nonempty in enabled mode, with actual Site ID and valid source registration. Without Site inventory, production Receiver service/port 9443 and durable event test remain HOLD rather than mocked PASS.

## Suricata/EVE

`enp3s0` is up/promisc without an IP; observed packets from 192.168.8.0/22 through SPAN, no switch change. Reusable workstation `suricata.yaml` points to `enp8s0` (not this host) and Unix dgram socket `/run/captive-portal/fingerprint-sensor/suricata-eve.sock` to be created by genuine Sensor. Debian/Ubuntu Jammy apt candidate only 6.0.4-3; template uses JA4/QUIC fields requiring newer Suricata. OISF official `ppa:oisf/suricata-stable` supports Jammy; 8.0.7 package security release September 2026. Staged root-owned `0644` target YAML `/etc/captivprod-suricata/captivprod-suricata.yaml` SHA256 `d8ee034795c905958ce312faef0aef4ca04b2137afd36e7726c6fb38cdae6ff3`, changing only capture interface `enp8s0` to `enp3s0`; retains socket-only EVE under the Sensor-owned run directory and `192.168.8.0/22` BPF scope. The accepted service unit from approved Git SHA is bound to real Sensor and hard-checks exact `8.0.6 RELEASE`, while OISF current security release (Sept 2026) is 8.0.7; choose and approve exact version policy before installation. Adding the OISF stable PPA changes target apt sources and needs a scoped Owner GO. No outdated 6.0.4 installed; no socket or capture daemon started. Cannot claim socket active while Sensor absent.

## NPM

Existing Docker NPM 2.16.0 and three legacy Proxy Hosts functioning, none changed. New FQDN `captivprod-navi.duckdns.org` resolves to 85.132.110.97. NPM already holds a matching Let's Encrypt certificate with expiry 2027-01-12. Independent Proxy Host not created. Modifying existing NPM state requires scoped GO and authenticated NPM session/API (none supplied). Diagnostic backend port 18089 is protected by NET-01 and Portal is absent; don't create a long-running mock which conflicts with guard semantics.

## Minimal next actions

1. Authorize/provision dedicated *new* Omada OpenAPI credentials locally (not in chat); perform read-only OAuth2 Site/AP/WLAN/Hotspot and privileges inventory with existing trusted `DNS:Omada` leaf pin. No AP adoption.
2. Approve OISF stable PPA and exact pinned Suricata 8.0.7 on new host, passive `enp3s0` only, socket-only EVE to true Sensor; no Cisco or other net changes. Install/test once supported source socket lifecycle is ready.
3. With confirmed Site ID, register Sensor/Portal source credentials and Site binding; deploy only independent Evidence CLI with own systemd service, TLS SAN verification, fresh SQLite, and isolated durable synthetic event tests. No new Portal service.
4. Approve NPM addition of ONLY `captivprod-navi.duckdns.org` proxy host using existing cert, after exact private diagnostic backend and NET-01 gated connectivity are reviewed; preserve existing hosts.

## Final read-only sanity

NET-01 exact verifier `DOCKER_IDENTITY=PASS` and `FIREWALL_FAIL_CLOSED=PASS`; services `tpeap`, `captiv-net01-firewall`, `captiv-net01-watchdog` all active after preparatory changes. Read-only PyMongo client only unpacked into an isolated `/tmp` scratch directory and that scratch was removed; no package installed, no Omada DB writes, no AP adoption, no Cisco changes, no old production mutations.
