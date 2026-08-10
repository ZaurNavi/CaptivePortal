# CaptivPortal Core Platform

[Русская версия](README_RU.md)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-green.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-production%20deployed-blue.svg)]()

CaptivPortal is a Python platform for an external captive portal and related operational services for **TP-Link Omada Controller**.

The project uses one shared authorization flow, a shared `OmadaProvider`, background operational modules, structured telemetry, and persistent visitor data. Independent background components are designed to fail open: their failure must not break the core captive-portal authorization path.

## Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Main modules](#main-modules)
- [Authorization flow](#authorization-flow)
- [Pending Session Cleaner](#pending-session-cleaner)
- [Installation](#installation)
- [Configuration](#configuration)
- [Testing](#testing)
- [Project knowledge base](#project-knowledge-base)
- [Current module status](#current-module-status)
- [Future direction](#future-direction)
- [Security notes](#security-notes)
- [License](#license)

---

## Overview

Current platform capabilities include:

- integration with **Omada Software Controller 5.14.31** through Open API;
- external captive-portal authorization;
- RFC 8908 CAPPORT support;
- bounded client discovery before authorization;
- one shared `AuthSession` / `AuthWorker` authorization flow;
- cleanup of stale unauthorized sessions through **Pending Session Cleaner**;
- authorized-client snapshots;
- persistent **Visitor Registry** storage;
- public authorization counters;
- normalized Omada webhook processing;
- structured JSONL telemetry and journals;
- observability through Alloy, Loki, and Grafana in the production environment.

Omada API handling follows an important rule:

> HTTP 200 is not sufficient to declare success. The application also validates the JSON `errorCode` and endpoint-specific response structure.

---

## Architecture

`run.py` is the composition root: it loads settings, creates the shared `OmadaProvider`, builds the Flask application, wires authorization services and background components, and controls startup/shutdown.

```mermaid
flowchart TD
    Client[Wi-Fi client] --> Entry{Portal entry}

    Entry -->|Omada External Portal| Portal[Portal entry handler]
    Entry -->|RFC 8908 CAPPORT| Capport[CAPPORT discovery / login]
    Capport --> Portal

    Portal --> Context[PortalClientContext]
    Context --> Sessions[AuthSessionManager]
    Sessions --> Worker[AuthWorker]
    Worker --> Provider[Shared OmadaProvider]
    Provider --> Controller[(Omada Controller)]

    Provider --> Cleaner[Pending Session Cleaner]
    Provider --> Snapshots[Authorized Client Snapshot Collector]

    Snapshots --> Registry[Visitor Registry]
    Registry --> SQLite[(SQLite)]

    Worker --> Telemetry[Authorization telemetry]
    Cleaner --> CleanerJournal[Cleaner JSONL journal]
    Snapshots --> SnapshotJournal[Visitor snapshots JSONL]

    Telemetry --> Observability[Alloy / Loki / Grafana]
    SnapshotJournal --> Observability
    CleanerJournal --> Observability
```

### Core architectural rules

- Use the existing shared `OmadaProvider`.
- Do not create a second OAuth/token manager without a separate architectural decision.
- CAPPORT does not implement a second authorization mechanism.
- Background modules must not make a failure of an optional subsystem become a portal failure.
- Runtime configuration follows the existing `app/config.py` → `app/settings.py` → `get_settings()` pipeline.
- The current production design is **single-process**; process-local session/guard state is an accepted limitation until a future scaling/HA design is approved.

---

## Main modules

### Authorization

The core authorization path uses `AuthSessionManager` and `AuthWorker`.

Responsibilities include:

- creating and tracking authorization sessions;
- checking Omada readiness;
- performing authorization through the shared provider;
- bounded retry/verification;
- final session states such as `AUTHORIZED`, `FAILED`, `RESET`, and `EXPIRED`;
- structured authorization telemetry.

### CAPPORT

CAPPORT provides RFC 8908 integration and captive-portal client discovery.

Current behavior includes:

- source-client validation;
- bounded waiting for a client to appear in Omada;
- same-page discovery-to-authorization transition;
- monotonic connection progress;
- reuse of the common authorization flow.

After confirmed `AUTHORIZED`, the frontend attempts to close the captive window and performs at most one same-page revalidation/reload fallback. The exact behavior of captive WebViews is OS-dependent and is validated separately in production field tests.

### Pending Session Cleaner

`app/pending_sessions` handles stale unauthorized Omada sessions.

A client can be considered for cleanup only after safety checks, including:

- wireless and active client state;
- `authStatus == 1`;
- allowed SSID;
- minimum session uptime;
- local authorization protection;
- fresh preflight state;
- action rate limits;
- audit-before-action.

The verified Omada operation is:

```text
POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect
```

The Cleaner uses bounded verification and does not use `block/unblock` as an automatic fallback.

### Authorized Client Snapshot Collector

Captures structured snapshots of authorized clients for operational history and downstream Visitor Registry processing.

### Visitor Registry

`app/visitor_registry` maintains persistent device/visit information in SQLite.

The production activation and observability stage has been accepted. Visitor snapshot events are also forwarded to Loki through a dedicated Alloy source for Grafana analysis.

A future **Visit Lifecycle** feature is a separate project stage and is not part of the already completed Visitor Registry activation.

### Public Authorization Counter

Maintains public authorization statistics without replacing the core authorization flow.

### Omada Webhook Normalizer

Normalizes Omada webhook events into the project's structured event model.

---

## Authorization flow

```mermaid
sequenceDiagram
    participant Client as Wi-Fi Client
    participant Portal as CaptivPortal
    participant Sessions as AuthSessionManager
    participant Worker as AuthWorker
    participant Omada as Omada Controller

    Client->>Portal: Open captive portal
    Portal->>Portal: Resolve PortalClientContext
    Portal->>Sessions: Create/reuse AuthSession
    Sessions->>Worker: Start authorization work
    Worker->>Omada: Read client state
    Omada-->>Worker: active/authStatus/client data
    Worker->>Omada: Authorize client
    Omada-->>Worker: HTTP + JSON errorCode/result
    Worker->>Omada: Final verification
    Omada-->>Worker: Authorized state
    Worker-->>Sessions: AUTHORIZED
    Sessions-->>Portal: Final state / progress 100%
    Portal-->>Client: Close attempt + bounded same-page revalidation fallback
```

---

## Pending Session Cleaner

High-level flow:

```mermaid
flowchart TD
    Start[Start scan] --> List[Read all active clients]
    List --> Complete{Inventory complete?}
    Complete -- No --> Partial[Finish partial scan; no reconnect]
    Complete -- Yes --> Classify[Classify candidates]

    Classify --> Protect1{Local auth protected?}
    Protect1 -- Yes --> Skip[Skip]
    Protect1 -- No --> Preflight[Fresh client GET]

    Preflight --> Eligible{Still eligible?}
    Eligible -- No --> Skip
    Eligible -- Yes --> Protect2{Protected now?}

    Protect2 -- Yes --> Skip
    Protect2 -- No --> Audit[Write and flush action.planned]
    Audit --> Guard{Action guard allows POST?}
    Guard -- No --> Skip
    Guard -- Yes --> Reconnect[POST reconnect]
    Reconnect --> Verify[Bounded verification]
    Verify --> CompleteAction[Write action.completed]
```

---

## Installation

### Requirements

- Python 3.10+
- Linux (Ubuntu 22.04 is the current production family)
- network access to an Omada Controller
- project dependencies from `requirements.txt`

### Clone and install

```bash
git clone https://github.com/ZaurNavi/CaptivePortal.git
cd CaptivePortal
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Run locally

Prepare the required process environment first, then run:

```bash
python3 run.py
```

Production uses the system service `captive-portal.service` and deployment-specific environment configuration.

---

## Configuration

Production Omada credentials are **not stored as literals in the current Git tree**.

The core Omada configuration contract uses these environment variables:

| Variable | Purpose |
|---|---|
| `OMADA_URL` | Omada Controller base URL |
| `OMADA_ID` | Omada Controller ID (`omadacId`) |
| `OMADA_CLIENT_ID` | Open API client ID |
| `OMADA_CLIENT_SECRET` | Open API client secret |
| `CAPPORT_SITE_ID` | Omada site used by CAPPORT/application flows |

Additional module settings are documented in `.env.example` and the module documentation.

> `.env.example` is a reference template. The application does **not** automatically load a local `.env` file; production configuration is supplied by the process environment / approved deployment mechanism.

Examples must use placeholders only. Never commit real controller credentials.

---

## Testing

Run targeted tests for the module being changed first.

The repository-level gate is:

```bash
python -m pytest -q -rs
python -m compileall -q app
git diff --check
```

A historical green Linux baseline exists, but release-quality status must always be tied to the exact commit being tested. Do not claim a current full gate is green unless it was actually executed on that revision.

Tests must not depend on real production Omada credentials or a real controller.

---

## Project knowledge base

The repository contains a permanent knowledge base for developers and coding agents.

Start with:

- [`AGENTS.md`](AGENTS.md) — universal repository rules;
- [`docs/README.md`](docs/README.md) — documentation index;
- [`docs/architecture.md`](docs/architecture.md) — current architecture;
- [`docs/module-index.md`](docs/module-index.md) — module map and status;
- [`docs/testing.md`](docs/testing.md) — test strategy;
- [`docs/deployment.md`](docs/deployment.md) — deployment contract;
- [`docs/security.md`](docs/security.md) — security rules.

The current TASK defines scope. Historical reports and old specifications are evidence/history, not a replacement for current code, tests, and module contracts.

---

## Current module status

| Area | Status | Notes |
|---|---|---|
| Core Flask platform | ✅ Active | Production service is deployed |
| Shared OmadaProvider | ✅ Active | OAuth `client_credentials`, shared token lifecycle |
| Authorization / AuthSession / AuthWorker | ✅ Active | Common authorization path |
| CAPPORT | ✅ Active | Bounded discovery and same-page transition |
| Pending Session Cleaner | ✅ Active | Production cleanup with safety guards and audit |
| Authorized Client Snapshot Collector | ✅ Active | Start-of-history snapshot after successful authorization |
| Visitor Registry | ✅ Active | Production/observability stage accepted |
| Public Authorization Counter | ✅ Active | Operational counter module |
| Omada Webhook Normalizer | ✅ Implemented | Structured webhook normalization |
| Observation Foundation v1 | ⏳ Planned next | Periodic client/AP observations and persistent history |
| Visit Lifecycle v1 | ⏳ Planned | Links devices, snapshots, observations, start and finalization |
| Analytics Foundation | ⏳ Planned | Reads stored history; does not collect from Omada itself |
| Web Foundation / Admin Console | ⏳ Planned | Product-facing application/API layer after data foundations |
| GitHub CI | ⚠️ Not yet implemented | Full gate is currently a manual Linux operation |

Operational debts and accepted limitations are tracked separately from this stable README.

---


## Future direction

CaptivPortal is being developed toward a **data-driven managed captive-portal platform**, not only an authorization page.

The next stages deliberately build the data foundation before a large customer-facing UI:

```mermaid
flowchart TD
    Authorized[Successful authorization] --> Snapshot[Existing Authorized Client Snapshot]
    Snapshot --> Observations[Observation Foundation v1]

    Omada[(Omada Controller)] --> ClientObs[Client Observation Collector]
    Omada --> APObs[AP Observation Collector]
    ClientObs --> Observations
    APObs --> Observations

    Observations --> Store[(Persistent Observation Storage)]
    Store --> Visits[Visit Lifecycle v1]
    Visits --> Analytics[Analytics Foundation]
    Store --> Analytics
    Analytics --> Web[Web Foundation]
    Web --> Console[CaptivPortal Admin Console]

    Console --> MultiSite[Multi-Site]
    MultiSite --> Tenant[Tenant / customer isolation]
    Tenant --> RBAC[Customer accounts / RBAC]
    RBAC --> Entitlements[Plans / entitlements]
    Entitlements --> Managed[Managed Captive Portal Service]
```

### Observation Foundation v1

The next planned functional stage is a persistent observation layer for **Wi-Fi clients and access points**.

The existing **Authorized Client Snapshot Collector is not replaced**. It keeps its current role: capture a detailed start-of-history snapshot immediately after successful authorization.

Observation Foundation then adds periodic, normalized observations while clients and APs remain active.

Research against the current Omada Open API has already confirmed useful data sources for planned collection, including:

- client context such as site, SSID, AP, radio/band, channel and session state;
- client RSSI, SNR, RX/TX rates and traffic counters when available;
- AP model, firmware, uptime, CPU and memory;
- AP radio channel, width, TX power and Wi-Fi mode;
- 2.4/5 GHz traffic counters;
- radio TX/RX/busy/interference utilization;
- packet errors, drops and retries;
- Ethernet/LAN uplink counters and link information;
- selected slowly changing capabilities such as channels and OFDMA state.

The intended rule is:

> **Collect facts now; analyze them later.**

Collectors should store normalized facts and timestamps, not hard-code product conclusions such as "weak signal", "bad AP placement" or "needs a second AP".

Periodic observation data is planned to use its own persistence/repository boundary rather than turning Visitor Registry into a generic time-series database.

### Visit Lifecycle and analytics

After enough observation history is being collected, **Visit Lifecycle v1** will connect:

```text
Device
→ successful authorization
→ initial snapshot
→ open visit
→ client/AP observations
→ offline/finalization
→ closed visit
```

A separate **Analytics Foundation** will then work from stored data. Analytics is expected to query Visitor Registry, Visit Lifecycle and Observation Storage instead of collecting historical data from Omada on demand.

Future analysis can include, for example:

- visitor-device and visit trends;
- new vs. returning devices;
- visit duration and repeat visits;
- RSSI/SNR distributions;
- weak-signal ratios and radio-quality trends;
- client distribution by AP and band;
- AP load, utilization, retries and errors;
- traffic trends;
- correlations between client radio quality and AP load;
- evidence useful for deciding whether an AP should be relocated or an additional AP may be justified.

RSSI is treated as a radio-quality signal, **not as an exact physical distance measurement**.

### Web Foundation and Admin Console

A small **Web Foundation** is planned before a full commercial Admin Console. It will establish stable application/query APIs, site-aware context, administrative security boundaries, and initial read-only views.

The later **CaptivPortal Admin Console** is the product/customer interface. It is intentionally separate from Grafana.

```text
Grafana
= internal engineering observability

CaptivPortal Admin Console
= product/customer interface
```

Grafana remains an internal tool for diagnostics, telemetry, collector validation, investigation and platform-wide engineering visibility.

Customer-facing metrics should be exposed through CaptivPortal application services and APIs, not by making Grafana/Loki the product backend.

### Site-aware commercial evolution

Near-term development follows a **site-aware, single-tenant** model:

- keep `site_id` where data naturally belongs to an Omada Site;
- do not hard-code the platform as permanently single-site;
- do not introduce a premature `tenant_id`;
- do not assume `Tenant == Site`;
- continue using the shared `OmadaProvider` and token lifecycle.

When a real second site or external customer appears, the planned evolution is:

```text
Site-aware platform
→ Multi-Site
→ Tenant model
→ customer accounts / RBAC
→ subscription entitlements
→ commercial managed service
```

One future tenant may own multiple sites.

Commercial plans are expected to use one Admin Console with **server-enforced entitlements**, rather than separate Basic/Standard/Professional forks of the application.

The long-term goal is a managed service in which customers use only their own CaptivPortal interface, see only their permitted sites/data/features, and do not receive direct access to internal Grafana or platform infrastructure.

---

## Security notes

- Never commit `OMADA_CLIENT_SECRET`, access tokens, cookies, or Authorization headers.
- Never log Wi-Fi passwords or complete sensitive Omada `/override` responses.
- Full MAC addresses are intentionally preserved in technical logs and operational data.
- Omada HTTP status and JSON `errorCode` are validated separately.
- The previous Omada Client Secret was removed from the current tree, but secret rotation is a separate owner-controlled security action because historical Git content may still contain old values.
- TLS verification toward Omada remains an operations/security item until a trusted certificate model is deployed.

---

## License

MIT License. See [LICENSE](LICENSE).

---

*README synchronized with the CaptivPortal production state and current project direction documented in August 2026.*
