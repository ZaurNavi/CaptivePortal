# Practical Command Execution Lessons Learned

Status: CURRENT / PERMANENT OPERATIONAL GUIDANCE
Updated: 2026-09-06

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

Port `127.0.0.1:8088` may become ready several seconds later.

Use a bounded readiness loop with multiple `curl` attempts and a finite timeout.
Do not classify a single request after a fixed three-second sleep as a product
failure.

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

## 8. `set -euo pipefail` can terminate diagnostics

With:

```text
set -euo pipefail
```

one failing diagnostic command terminates the remaining block.

If a diagnostic absence/error is expected and non-fatal:
- isolate it into a separate bounded stage; or
- deliberately use `|| true` where that behavior is explicitly intended.

Do not accidentally skip later evidence collection because a diagnostic probe
returned non-zero.

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
