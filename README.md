# CaptivePortal

**English** | [Русский](README_RU.md)

A standards-based, controller-integrated captive portal platform for managed guest Wi‑Fi networks.

CaptivePortal provides a complete guest access flow: network discovery, portal presentation, client authorization, session tracking, structured telemetry, and operational monitoring.

> **Project status:** Active development and field testing.

---

## Table of contents

- [Overview](#overview)
- [Current Integration](#current-integration)
- [How it works](#how-it-works)
- [Implemented features](#implemented-features)
- [Architecture](#architecture)
  - [High-level diagram](#high-level-diagram)
  - [Cleaner sequence](#cleaner-sequence)
  - [Token expiry race (problem & fix)](#token-expiry-race-problem--fix)
- [Observability](#observability)
- [Development setup](#development-setup)
- [Roadmap & Direction](#roadmap--direction)
- [Development principles & Security](#development-principles--security)
- [Testing strategy](#testing-strategy)
- [License](#license)

---

## Overview

CaptivePortal started as a custom portal for a guest Wi‑Fi network and has evolved into a modular platform adaptable to organizations that provide managed public or corporate wireless access.

Targeted deployments include:

- parks and public spaces
- hotels and hospitality
- offices and business centers
- educational institutions
- clinics and service locations
- retail spaces and event venues
- municipal guest networks

The architecture separates the user-facing portal from controller-specific authorization logic, keeping portal, session model, telemetry, and monitoring reusable across controller adapters.

See also:
- Architecture and module status: `docs/README.md`
- Developer instructions: `AGENTS.md`
- Project inventory and feature map: `docs/project-inventory.md`

---

## Current Integration

First supported adapter: **TP‑Link Omada Software Controller** (tested on 5.14.x release line).

Validated in test environment:
- client discovery via Omada Open API
- guest authorization via Omada Open API
- controller-enforced access
- CAPPORT-compatible portal discovery
- structured authorization telemetry
- integration with Grafana Alloy → Loki → Grafana dashboards

Omada is an adapter — the core supports adding other controllers later.

---

## How it works (high level)

```
Guest device connects to Wi‑Fi
        ↓
DHCP provides CAPPORT info (Option 114)
        ↓
Client queries CAPPORT API
        ↓
OS opens captive portal
        ↓
CaptivePortal creates/restores session
        ↓
Backend locates client via controller adapter
        ↓
CaptivePortal requests controller to authorize client
        ↓
Controller grants network access
        ↓
Authorization is logged to structured telemetry
```

Actual network enforcement is performed by the configured controller adapter (Omada for reference).

---

## Implemented features

- CAPPORT discovery (DHCP Option 114)
- CAPPORT API endpoint
- Responsive portal UI (single‑page portal.html)
- Omada Open API adapter for authorization & lookup
- Portal session management and retry flows
- ActionGuard, retry limits and auditing
- Structured JSON telemetry and journaled events
- Grafana Alloy / Loki integration for logs and dashboards
- Tests and CI targets (unit tests in `tests/`)

---

## Architecture

The system is logically layered:

- Portal layer — renders portal.html, handles client-side retry and discovery
- Session layer — creates/restores session state, avoids conflicting workers
- Controller integration layer — controller authentication, client discovery, authorization
- Telemetry layer — structured events, diagnostics, failure classification
- Integration layer — webhooks, controller events, traffic statistics

### High-level diagram

```mermaid
flowchart LR
  subgraph Network
    Client["Visitor device / browser"]
  end

  subgraph App ["CaptivePortal service"]
    A[Routes: /capport/api, /capport/login]
    B[portal.html (UI)]
    C[PortalEntryHandler -> PortalClientContext]
    D[AuthSessionManager / AuthWorker]
    E[Pending Session Cleaner (background)]
    F[OmadaProvider (shared token cache)]
    G[Journal & Telemetry]
    H[ActionGuard]
  end

  Client -->|GET /capport/login| A
  A -->|resolve_for_login(ip)| F
  F -->|state (client_found?)| A

  A -->|client found → open_portal()| C
  C -->|creates AuthSession| D
  D -->|calls Omada| F
  D -->|audit| G

  A -->|client not found → DISCOVERING_CLIENT (200)| B
  B -->|auto-retry (server-bounded)| A

  E -->|scans inventory| F
  E -->|classify -> decide reconnect| H
  E -->|reconnect_client| F
  E -->|log actions| G
```

### Cleaner sequence (single candidate)

```mermaid
sequenceDiagram
  participant Cleaner
  participant Provider
  participant Omada
  participant Protection
  participant Journal
  participant ActionGuard

  Cleaner->>Provider: list_active_clients(page=1)
  Provider->>Omada: GET /sites/{site}/clients?page=1
  Omada-->>Provider: 200 + clients
  Provider-->>Cleaner: Result {clients, total_rows}
  Cleaner->>Cleaner: classify candidates
  Cleaner->>Protection: check(local protection)
  alt allowed
    Cleaner->>Provider: get_pending_client_state(client_mac)
    Provider->>Omada: GET /sites/{site}/clients/{mac}
    Omada-->>Provider: client record
    Provider-->>Cleaner: client
    Cleaner->>ActionGuard: check(rate limits)
    Cleaner->>Journal: write planned event
    Cleaner->>Provider: reconnect_client(client_mac)
    alt TOKEN_EXPIRED (-44112)
      Provider->>Provider: invalidate_cached_token(old_token)  /* compare-and-invalidate */
      Cleaner->>Provider: get_pending_client_state (fresh GET via _retry_get)
      Cleaner->>Protection: re-check
      Cleaner->>Provider: reconnect_client (retry once)
    end
    Cleaner->>Provider: get_pending_client_state (verify)
    Cleaner->>Journal: write completed event
  else protected
    Cleaner->>Journal: write completed without post
  end
```

### Token expiry race — problem & fix

```mermaid
sequenceDiagram
  participant Cleaner
  participant Provider (token cache)
  participant AuthWorker
  participant Omada

  Cleaner->>Provider: reconnect_client(token=A) -> POST
  Provider->>Omada: POST ... Authorization: AccessToken=A
  Omada-->>Provider: 401 / errorCode=-44112 (TOKEN_EXPIRED)
  Provider->>Provider: invalidate_cached_token(A)   <-- compare-and-invalidate (OK)
  par concurrent
    AuthWorker->>Provider: _get_token() -> refresh -> publish token=B
  and
    Cleaner->>Provider: _recover_expired_token() -> (bad impl) invalidate()  --X deletes token B
  end

  Note right of Provider: Bad: unconditional invalidate() can remove B
  Note right of Provider: Fix: remove unconditional invalidate() from Cleaner; rely on compare-and-invalidate(old_token)
```

---

## Observability

All important events are recorded as structured JSON records in a journal and emitted to the telemetry pipeline:

- session id, client IP, client MAC
- attempt number, controller lookup result, auth result
- duration, error classification, module/event names, schema version, timestamp

Pipeline:

```
App -> JSONL journal -> Grafana Alloy -> Grafana Loki -> Grafana dashboards
```

Keep credentials out of logs — telemetry does not include secrets.

---

## Development setup

Requirements:

- Linux (or WSL/macOS), Python 3.10+
- Access to controller for integration testing
- DHCP server with CAPPORT Option 114 for discovery tests

Quick start:

```bash
git clone <repo>
cd CaptivePortal
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# configure app/settings.py and environment
python run.py
```

Configuration is environment-driven — see `app/config.py` and `app/settings.py`.

---

## Testing

Unit tests are in `tests/`. To run specific groups:

```bash
# run all tests
python -m pytest -q

# run pending_sessions tests
python -m pytest -q tests/pending_sessions
```

(If CI environment is not available, tests cannot be executed locally here — run on your developer machine or CI.)

---

## Roadmap & direction

Priorities:

- portal reliability: non-blocking retry UX, reuse session during retry, avoid parallel workers
- client-side telemetry (page load, retry, visible)
- webhook receiver to enrich controller data
- traffic accounting via controller APIs
- adapter framework for other controllers (RADIUS, CoA, ACLs)

---

## Development principles & security

- Verify controller behavior with live testing before encoding assumptions
- Develop permanent modules incrementally (avoid throwaway prototypes)
- Controller logic must not leak into portal core
- Telemetry failures must not break authorization
- No secrets in source or logs
- Defensive programming around controller responses and timeouts

---

## Testing strategy (notes)

- Validate delayed client appearances (discovery mode)
- Simulate controller errors and token expiry cases
- Replay JSONL telemetry in Grafana
- Keep live tests isolated in dedicated test VLAN

---

## License

No public license yet. Treat repository as private until a license is added.

---

## Diagrams to SVG/PNG

If you want PNG/SVG assets for the diagrams inside `docs/diagrams/`:

- Install mermaid-cli (or use the online editor):

```bash
npm install -g @mermaid-js/mermaid-cli
# save mermaid block to file.mmd and render:
mmdc -i file.mmd -o file.svg
mmdc -i file.mmd -o file.png
```

Alternatively, use the Mermaid Live Editor (https://mermaid.live/) for quick export.

---

## What I changed (summary)

- Reflowed README sections and added TOC
- Added clear Quick Start and Development Setup
- Inserted three Mermaid diagrams to explain architecture and key flows
- Emphasized observability & security guidance
- Kept links to docs and Russian README

---

If you want SVG exports for the three diagrams, tell me which format you prefer (SVG or PNG) and I will provide the SVG text for each diagram so you can save them as files (e.g. `docs/diagrams/arch.svg`) and include them in the repo.
