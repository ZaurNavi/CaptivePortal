# CAPPORT API

Status: superseded as normative contract
Current contract: [modules/capport.md](modules/capport.md)
Historical implementation details below are retained for reference.

This module adds RFC 8908 captive-state discovery while preserving the
existing Omada External Portal authorization flow.

## Public endpoints

- API: `https://captivportal-navi.duckdns.org/capport/api`
- Portal entry: `https://captivportal-navi.duckdns.org/capport/login`
- Existing Omada entry: `https://captivportal-navi.duckdns.org/`

`GET /capport/api` is read-only. It looks up the requesting device by
source IP and returns `application/captive+json`. It never creates an
AuthSession, starts an AuthWorker, changes Omada state, sets a cookie, or
redirects.

For a known authorized client the API returns:

```json
{
  "captive": false,
  "user-portal-url": "https://captivportal-navi.duckdns.org/capport/login"
}
```

For an unauthorized, unknown, or temporarily unresolved guest client it
fails safely with `captive: true`.

`GET /capport/login` resolves the same client by IP and passes a typed
client context into the shared portal-entry handler. From that point it
uses the existing AuthSession, AuthWorker, progress page, and Omada
`/auth` implementation.

The client list is used only for identity resolution (`IP → MAC`).
CAPPORT does not trust optional state fields from that list: after a MAC
is found it calls the existing `get_client(site_id, client_mac)` method
and uses that authoritative `authStatus` and `active` response.

Identity and state use separate two-second caches:

```text
site_id → identity snapshot (client_ip → client_mac)
site_id + client_ip → authoritative authStatus / active
```

The site-level single-flight lock covers only the paginated
`get_clients()` refresh. Authoritative `get_client()` calls use per-IP
locks, so different phones share one identity snapshot while their
detail lookups run concurrently.

If the early API poll caches `CLIENT_NOT_FOUND`, `/capport/login`
bypasses that negative cache and performs a bounded retry (up to five
total lookups and no more than five seconds of scheduled wait). A
controller failure is cached separately for two seconds so concurrent
requests fail safely without forming a queue of repeated timeouts.

## Project settings

The existing `app/config.py` and `app/settings.py` layer contains:

```python
CAPPORT_ENABLED = True
CAPPORT_SITE_ID = "6a64f17630da7c70d232187a"
CAPPORT_PUBLIC_BASE_URL = "https://captivportal-navi.duckdns.org"
CAPPORT_API_PATH = "/capport/api"
CAPPORT_LOGIN_PATH = "/capport/login"
CAPPORT_ALLOWED_CLIENT_NETWORKS = (
    "192.168.1.0/24",
    "192.168.8.0/22",
)
CAPPORT_CLIENT_CACHE_TTL_SECONDS = 2
CAPPORT_FAILURE_CACHE_TTL_SECONDS = 2
```

The two networks above are a temporary VLAN20 migration and rollback
contract. The old guest network remains `192.168.1.0/24`. The new guest
network is `192.168.8.0/22` with gateway `192.168.10.1`; its usable client
range remains bounded by that exact `/22`. Do not remove the old `/24`
without separate owner approval after the migration has stabilized.

This allowlist change takes effect only after the production repository is
synchronized and `captive-portal.service` is restarted. It prepares the
portal only; it does not authorize any Cisco, DHCP, NAT, Omada, Nginx, or
systemd change.

Startup validation rejects an empty site ID, non-HTTPS public URL,
relative paths, invalid networks, non-positive cache TTL, or a Flask bind
address other than `127.0.0.1`.

## Nginx and trusted proxy

Flask must listen only on `127.0.0.1:8088`. Nginx is the sole trusted
proxy hop and must overwrite the forwarded headers:

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto https;
proxy_set_header X-Forwarded-Host  $host;
proxy_set_header X-Forwarded-Port  443;
```

The application deliberately configures `ProxyFix` with exactly one hop
for `x_for`, `x_proto`, `x_host`, and `x_port`. Do not expose port 8088
on a LAN interface and do not increase the trusted-hop count without a
separate security review.

## Omada pre-auth access

Before a guest is authorized, Omada must permit TCP 443 access to:

```text
captivportal-navi.duckdns.org
```

The public certificate must remain valid for this hostname. The network
must not intercept or disable TLS verification for the API.

Omada Open API access must include permission to list clients in the
configured site. The provider uses:

```text
GET /openapi/v1/{omadac_id}/sites/{site_id}/clients?page=...&pageSize=...
```

Deployment should confirm the anonymized field names and pagination
metadata against the actual Omada Controller 5.14.31 response before
enabling DHCP option 114.

## Tests

From the repository root:

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q app
python -m unittest discover -s tests -v
```

The test suite covers CAPPORT media and cache headers, fail-safe states,
allowed networks, read-only behavior, shared login entry, client-list
pagination, exact IP matching, duplicate IP handling, MAC normalization,
authoritative state lookup, early-login negative-cache refresh, Omada
failure cooldown, multi-IP site snapshot sharing, concurrent detail
lookups, system telemetry without a session ID, cache single-flight, and
the one-hop ProxyFix contract.

## Enabling DHCP option 114

Only after code review, deployment, HTTPS/pre-auth validation, and field
testing, the network administrator can configure the guest DHCP pool:

```cisco
option 114 ascii https://captivportal-navi.duckdns.org/capport/api
```

This is an infrastructure operation and is not executed by the
application or by this code change.

## Rollback

1. Remove or disable DHCP option 114 in the guest DHCP pool.
2. Set `CAPPORT_ENABLED = False` and restart
   `captive-portal.service`, or deploy the previous application version.
3. Keep the existing Omada External Portal URL pointing to `/`; the
   legacy query-parameter flow remains independent and operational.
4. Verify the service still binds only to `127.0.0.1:8088` and that
   Nginx continues to serve the existing HTTPS portal.

Disabling option 114 causes capable clients to fall back to their legacy
connectivity-probe behavior; it does not require changes to AuthWorker or
the existing Omada authorization endpoint.
