# TASK-ADMIN-SETTINGS-03 — PRODUCTION DEPLOY ATTEMPT / ROLLBACK EVIDENCE

**Date:** 2026-10-07  
**Target merge:** `b6927cf70207810cec9d6a8186e92f131ca1392f`  
**Target tree:** `06611fff6650fa0eb3be2e5ff301010146413fe7`  
**Previous production:** `c1167180daec9ca17d13ab44326f143122db8d5e`

## Outcome

```text
SOURCE MERGE            = PASS
DEPLOY INSTALL          = PERFORMED
SETTINGS DB v1→v2       = PASS
45s SYSTEMD PID STABLE  = PASS

APPLICATION READINESS   = FAIL
ADMIN HTTPS             = 502
127.0.0.1:8088          = NOT LISTENING at smoke time

PRODUCTION ACCEPTANCE   = REJECTED
ROLLBACK REQUIRED       = YES
ROLLBACK COMPLETED      = YES
PRODUCTION RESTORED     = STAGE 2
```

## Pre-deploy

```text
HEAD=c1167180daec9ca17d13ab44326f143122db8d5e
TREE=278df41bfa3134b22963b41006585da35de08074
WORKTREE=CLEAN

SERVICE=active
PID=1456310
NRESTARTS=0

SETTINGS_DB schema=1
configured_generation=0
effective_generation=0
persisted_overrides=0
```

An exact pre-deploy Settings DB backup was created before migration:

```text
/home/admin/captivportal-deploy-backups/as03-20261007T083810Z/settings.sqlite3.v1

SHA256=
1f5b3f9c70fe129c13b1cfbb39b6a5a62977eb0310169b2eeb53644fcb994663
```

## Target install evidence

```text
HEAD=b6927cf70207810cec9d6a8186e92f131ca1392f
TREE=06611fff6650fa0eb3be2e5ff301010146413fe7
WORKTREE=CLEAN

PID=2327090
NRESTARTS=1

45s stable PID/systemd state = PASS

SETTINGS_DB schema=2
integrity=ok
configured_generation=0
effective_generation=0
persisted_overrides=0

tracebacks observed by deploy script=0
controller projection unavailable events=0
```

## Failed readiness smoke

External forced-SNI Admin smoke returned:

```text
GET /admin/login
→ 502 Bad Gateway

GET /admin/settings/controller
→ 502 Bad Gateway

GET /admin/api/v1/settings/controller
→ 502 Bad Gateway
```

At the same time:

```text
127.0.0.1:8088
→ not listening

local curl /admin/login
→ connection refused
```

The systemd service being `active` was therefore insufficient evidence of product readiness.

## Startup timing evidence

Stage-3 target PID `2327090`:

```text
12:38:40 Starting Captive Portal
12:38:41 Configuration loaded
12:38:41 Creating controller provider...
12:40:45 portal_counter.migration_completed
12:40:45 Web application created
```

The target therefore spent approximately 124 seconds between Controller-provider creation logging and completion of `create_app()`.

By comparison, after rollback Stage-2 PID `2331193`:

```text
12:41:19 Starting Captive Portal
12:41:19 Configuration loaded
12:41:19 Creating controller provider...
12:41:20 Web application created
12:41:55 analytics.api_runtime_active
12:41:56 Starting server on 127.0.0.1:8088
```

This is a production-only startup/readiness regression requiring investigation before another Stage-3 deploy.

## Rollback

Rollback restored:

```text
CODE:
c1167180daec9ca17d13ab44326f143122db8d5e

TREE:
278df41bfa3134b22963b41006585da35de08074

SETTINGS DB:
pre-deploy schema-v1 backup
```

After Stage-2 restarted, its normal startup wrote its own activation metadata, so the live DB byte hash is expected to differ from the frozen backup; logical schema/state is restored.

Final rollback verification:

```text
HEAD=c1167180daec9ca17d13ab44326f143122db8d5e
TREE=278df41bfa3134b22963b41006585da35de08074
WORKTREE=CLEAN

SERVICE=active
PID=2331193
NRESTARTS=2

DB_USER_VERSION=1
DB_INTEGRITY=ok
GEN_HEAD=0
PERSISTED_OVERRIDES=0
```

External smoke after rollback:

```text
/admin/login
→ 200

/admin/settings/controller
→ 302 to login

/admin/api/v1/settings/controller
→ 401 JSON

HTTP root
→ 200
```

Post-rollback Omada observation cycle also completed successfully with:

```text
complete=True
error_count=0
http_status=200
```

## Tech Lead disposition

```text
TASK-ADMIN-SETTINGS-03
SOURCE / MERGE               = ACCEPTED

PRODUCTION DEPLOYMENT        = REJECTED
PRODUCTION STATE             = ROLLED BACK / GREEN ON STAGE 2

OPEN P0                      = 0
OPEN P1                      = 1

P1-PROD-01 =
Stage-3 startup/readiness regression:
create_app completion delayed ~124s in production;
Admin upstream unavailable during smoke.

STAGE-3 REDEPLOY             = HOLD
PRODUCTION MUTATION          = HOLD
```

Before the next deploy attempt:

```text
1. reproduce or instrument the Stage-3 startup delay;
2. close P1-PROD-01;
3. preserve the accepted Stage-3 architecture/security contracts;
4. add an explicit application-listener/local-HTTP readiness gate to deployment validation;
5. repeat source review for any source fix;
6. deploy only after a new Tech Lead GO.
```
