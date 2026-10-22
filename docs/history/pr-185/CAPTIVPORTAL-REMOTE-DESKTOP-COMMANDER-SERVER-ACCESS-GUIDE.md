# CaptivPortal — Remote Desktop Commander / production server access guide

## Purpose

This guide explains the approved operational path used by project agents to reach the CaptivPortal production host through the authorized Windows workstation.

It contains no password, private-key material, token, Client Secret, or other credential.

## Connection topology

```text
ChatGPT agent
    ↓
Remote Desktop Commander
    ↓
authorized Windows workstation: DESKTOP-7C8M3BS
    ↓
PuTTY / plink saved session: Ubunt
    ↓
SSH as admin
    ↓
CaptivPortal production host: 192.168.0.202
```

Important:

```text
PRODUCTION HOST = 192.168.0.202
DO NOT USE       = 192.168.0.99
```

The PuTTY saved session `Ubunt` already contains the SSH connection configuration. Do not inspect, print, copy, or expose private-key material.

## 1. Confirm that the authorized desktop is online

Use Remote Desktop Commander device discovery/listing first.

Select:

```text
DESKTOP-7C8M3BS
```

Do not assume a stale device identifier is still valid if device discovery returns a different current identifier.

## 2. Basic read-only server command

Run PowerShell on the authorized Windows workstation and let `plink.exe` execute the Linux command through the saved PuTTY session.

Canonical pattern:

```powershell
& 'C:\Program Files\PuTTY\plink.exe' -batch -load Ubunt 'hostname; id -un; uptime'
```

For the CaptivPortal repository:

```powershell
& 'C:\Program Files\PuTTY\plink.exe' -batch -load Ubunt 'cd /opt/CaptivePortal; git rev-parse HEAD; git rev-parse HEAD^{tree}; git status --porcelain'
```

`-batch` is required for non-interactive automation. If PuTTY needs an unexpected interactive credential or host-key confirmation, stop rather than trying to extract or transmit a secret.

## 3. Prefer read-only prechecks before any production mutation

Before a deploy/change, verify at least:

```text
exact production HEAD
exact production TREE
git worktree clean
service active
MainPID
NRestarts
required feature-gate/drop-in state
database existence/integrity where applicable
exact target commit/tree/parents
rollback artifact availability
```

Example:

```powershell
& 'C:\Program Files\PuTTY\plink.exe' -batch -load Ubunt 'cd /opt/CaptivePortal; git rev-parse HEAD; git rev-parse HEAD^{tree}; git status --porcelain; systemctl is-active captive-portal.service; systemctl show captive-portal.service -p MainPID -p NRestarts --no-pager'
```

Never broadly dump the process environment. Query only explicitly approved, non-secret configuration keys.

## 4. Multiline remote work

For non-trivial commands, do not fight nested quoting in one huge PowerShell line.

Preferred pattern:

1. Use Remote Desktop Commander to create a temporary `.ps1` file under:

```text
C:\CaptivPortal-Lab\tmp\
```

2. Inside that PowerShell file use a here-string for the Linux command:

```powershell
$remote = @'
cd /opt/CaptivePortal
git rev-parse HEAD
git status --porcelain
systemctl is-active captive-portal.service
'@

& 'C:\Program Files\PuTTY\plink.exe' -batch -load Ubunt $remote
```

3. Execute the `.ps1` through Remote Desktop Commander.
4. Read/poll process output until the command has actually completed.

This is much safer than deeply nested shell quoting.

## 5. Transferring a reviewed script to the server

Use PuTTY `pscp.exe` from the authorized Windows workstation.

Example:

```powershell
& 'C:\Program Files\PuTTY\pscp.exe' -batch -load Ubunt `
  'C:\CaptivPortal-Lab\tmp\reviewed-script.sh' `
  'admin@192.168.0.202:/home/admin/reviewed-script.sh'
```

Then verify remotely before execution:

```powershell
& 'C:\Program Files\PuTTY\plink.exe' -batch -load Ubunt `
  'chmod 700 /home/admin/reviewed-script.sh; bash -n /home/admin/reviewed-script.sh; sha256sum /home/admin/reviewed-script.sh; wc -c /home/admin/reviewed-script.sh'
```

A production script should be exact-target, fail-fast, identity-checking, and have an explicit rollback path.

## 6. `sudo`

Current non-interactive checks showed:

```text
sudo -n true = unavailable
```

Therefore:

- do not request or paste a sudo password into ChatGPT;
- do not scrape credentials from the workstation;
- do not infer that `sudo` is passwordless;
- if a task truly requires sudo, use an explicitly approved local/operator interaction or stop for a task-specific plan.

Never treat lack of passwordless sudo as permission to improvise a privilege bypass.

## 7. Service restart behavior

Always inspect the actual unit before relying on behavior:

```powershell
& 'C:\Program Files\PuTTY\plink.exe' -batch -load Ubunt `
  'systemctl show captive-portal.service -p User -p Restart -p RestartUSec -p MainPID -p NRestarts --no-pager'
```

At the time this guide was written, `captive-portal.service` ran as `admin` with `Restart=always`.

That fact is **not a generic restart recipe**. Signal-based restart/rollback is task-specific and must only be used when the current Tech Lead deployment plan explicitly authorizes it and verifies owner/restart semantics first.

Preferred normal operator restart remains the project's authorized service-management path when available.

## 8. Correct external HTTPS smoke path

The correct CaptivPortal Admin HTTPS virtual host is:

```text
captivportal-navi.duckdns.org
```

For a forced local SNI test from the authorized Windows workstation:

```powershell
curl.exe -k --resolve captivportal-navi.duckdns.org:443:192.168.0.202 `
  -D - -o NUL `
  https://captivportal-navi.duckdns.org/admin/login
```

Typical unauthenticated boundary checks:

```text
/admin/login
→ 200

/admin/settings/controller
→ 302 to /admin/login

/admin/api/v1/settings/controller
→ 401 JSON
```

The default IP HTTPS vhost is not the authoritative Admin smoke target.

## 9. Production acceptance must test application readiness, not only systemd state

A Linux service can be:

```text
systemctl is-active = active
MainPID stable
NRestarts unchanged
```

while the Flask application is not yet listening.

Therefore every future CaptivPortal deploy gate must include an explicit readiness check such as:

```text
127.0.0.1:8088 is LISTENING
AND
local /admin/login responds
AND
external Admin HTTPS smoke succeeds
```

Do not accept production merely from `active` + stable PID.

This rule was reinforced by the Stage-3 deployment attempt on 2026-10-07.

## 10. Security / evidence rules

Never print or copy:

```text
private SSH keys
passwords
OMADA_CLIENT_SECRET
access tokens
Authorization headers
entire environment dumps
secret-bearing config objects
```

Prefer:

```text
exact commit/tree IDs
bounded status output
counts
safe error categories
database schema/integrity metadata
HTTP status/headers
sanitized journal events
```

For any mutation, preserve before/after evidence and a rollback identity.

## 11. Current production note at time of this guide

After the Stage-3 deployment attempt was rejected and rolled back:

```text
PRODUCTION HEAD =
c1167180daec9ca17d13ab44326f143122db8d5e

PRODUCTION TREE =
278df41bfa3134b22963b41006585da35de08074

Stage-2 production state = restored / green
```

Remote GitHub `main` is newer than production. Never assume `production == main`; verify both explicitly before every operation.
