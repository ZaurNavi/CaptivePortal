# Practical Command Execution Lessons Learned

Status: CURRENT / PERMANENT OPERATIONAL GUIDANCE
Updated: 2026-09-12

Purpose: prevent known command/harness mistakes from being repeated in future
deploy, production-validation and acceptance instructions.

These are execution lessons, not product defects.

## 1. Python user/site environment

Do not automatically run production Python CLI checks as:

```text
sudo python3 ...
```

when required dependencies are installed in the `admin` user's Python user-site.

Observed project failure mode:

```text
sudo python3 → ModuleNotFoundError: flask
/usr/bin/python3 as admin → dependencies available
```

Before giving a Python CLI command, determine the actual service user,
interpreter and dependency environment.

Privilege escalation must not silently change the Python environment.

## 2. `/etc/default/captive-portal` permissions

Production file:

```text
/etc/default/captive-portal
```

is root-owned with:

```text
600 root:root
```

Commands that read or modify it must use the required `sudo` path from the
start. Do not first issue an unprivileged Python/file-read command that will
predictably fail with `PermissionError`.

Never print secrets while inspecting this file.

## 3. Service readiness after restart

After:

```text
systemctl restart captive-portal.service
```

`active/running` proves process state, not immediate HTTP readiness.

Permanent invariant:

```text
systemd active != HTTP readiness
```

Port `127.0.0.1:8088` may become ready after systemd already reports the service
active.

During the 2026-09-12 production acceptance, the first probe saw:

```text
systemd=active
listener=absent
HTTP=000
```

The same PID then continued normal startup composition and reached:

```text
analytics.api_runtime_active
127.0.0.1:8088 LISTEN
HTTP=400
```

No second restart was required.

Use a bounded readiness loop with listener/startup-progress evidence and multiple
HTTP attempts. Do not classify one early `HTTP 000` as a product failure, and do
not restart again solely because the listener is not yet present while the same
process is still progressing normally.

HTTP `400` on `/` without required Omada request parameters is expected
CaptivPortal readiness behavior.

## 4. Git status and identity checks

Always write the command explicitly as:

```text
git status --short
```

The project has seen copied commands lose the beginning and become forms such as
`t status...`, meaning the clean-worktree check did not actually execute.

Critical identity/status gates should combine the check with an assertion/test
where practical so a typo cannot silently pass.

## 5. Avoid unnecessary `git worktree move`

Do not physically `git worktree move` unless the move is required.

Windows may return `Permission denied`.

For an immutable test candidate, prefer creating a new detached worktree
directly in the required allowlisted path.

## 6. Check an allowlisted path before reuse

Before creating a Central Lab worktree:

```text
git worktree list
```

and inspect the target directory.

If the path is occupied:
- preserve the existing worktree;
- do not overwrite/delete it;
- use another allowed path when possible.

## 7. Paste/shell corruption is a harness error first

Long shell blocks can be corrupted during terminal paste.

A syntax error, truncated block or malformed pasted command is not automatically
a candidate FAIL.

Classification flow:

```text
command/paste error
→ classify as harness error
→ correct the command
→ rerun the same gate on the unchanged candidate
→ only then classify product behavior
```

## 8. Do not use shell-wide fail-fast in Owner / production runbooks

Do not wrap CaptivPortal Owner acceptance or production runbooks in:

```text
set -e
set -euo pipefail
```

A single diagnostic/non-critical probe can otherwise terminate the remaining
evidence collection and make a harness failure look like a candidate/product
failure.

Use explicit bounded stages and explicit checks for each critical action.
Expected/non-fatal diagnostic absence should be classified deliberately rather
than hidden behind a shell-wide fail-fast mode.

## 8A. Use the canonical systemd environment for Projection repair CLI

Production Projection worker configuration is supplied by systemd
`EnvironmentFile=/etc/default/captive-portal`.

During the 2026-09-11 Projection P0 recovery, running `repair-site` from an
ordinary interactive shell correctly failed closed with:

```text
TRAFFIC_PROJECTION_ENABLED must be true
```

No DB mutation began.

The controlled repair was then run with the same effective runtime context as
`traffic-projection.service`:

```text
User=admin
Group=admin
WorkingDirectory=/opt/CaptivePortal
EnvironmentFile=/etc/default/captive-portal
```

Permanent operational rule:

```text
Do not assume an interactive shell has the production service environment.
For production CLI/repair that depends on service configuration, reproduce the
canonical systemd EnvironmentFile/User/Group/WorkingDirectory context.
```

Never print secret EnvironmentFile values while proving the context.

## 9. Permanent pre-action sequence

Before an operation that can modify state:

```text
verify user
→ verify Python/runtime
→ verify file permissions
→ verify working directory
→ verify Git identity/worktree state
→ verify service readiness assumptions
→ perform the modifying action
```

Command/harness/infrastructure errors must be classified separately from:
- candidate/code regressions;
- production-component failures;
- data-integrity failures.

Correct the harness first, then rerun the unchanged evidence scope.
