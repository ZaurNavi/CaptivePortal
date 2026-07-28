# CaptivePortal

**English** | [Русский](README_RU.md)

A standards-based, controller-integrated captive portal platform for managed guest Wi-Fi networks.


CaptivePortal provides a complete guest access flow: network discovery, portal presentation, client authorization, session tracking, structured telemetry, and operational monitoring.

The platform is currently developed and tested with **TP-Link Omada Software Controller**, while the internal architecture is designed to support additional network controllers and authorization backends in the future.

> **Project status:** Active development and field testing.

---

## Overview

CaptivePortal started as a custom portal for a guest Wi-Fi network and has evolved into a modular platform that can be adapted for organizations providing managed public or corporate wireless access.

The project is intended for environments such as:

* parks and public spaces;
* hotels and hospitality;
* offices and business centers;
* educational institutions;
* clinics and service locations;
* retail spaces;
* event venues;
* municipal guest networks.

The platform separates the user-facing portal from controller-specific authorization logic. This allows the portal, session model, telemetry, and monitoring components to remain reusable when integrating with another Wi-Fi controller or network access platform.

---

## Current Integration

The first supported controller integration is:

**TP-Link Omada Software Controller**

The current test environment validates:

* client discovery through Omada Open API;
* guest authorization through Omada Open API;
* controller-based access enforcement;
* CAPPORT-compatible portal discovery;
* structured authorization telemetry;
* integration with Grafana Loki through Grafana Alloy.

The current implementation is tested against an Omada Software Controller from the **5.14.x** release line.

Omada is the first controller adapter, not a permanent architectural limitation of the platform.

---

## Main Goals

CaptivePortal is designed around the following principles:

* standards-based captive portal discovery;
* clean separation between portal logic and controller integration;
* observable authorization flows;
* predictable error handling;
* reusable session management;
* vendor-neutral extension points;
* gradual development without temporary throwaway components;
* deployment suitable for real guest networks.

---

## How It Works

The current authorization flow is:

```text
Guest device connects to Wi-Fi
        ↓
DHCP provides CAPPORT information through Option 114
        ↓
Client requests the CAPPORT API
        ↓
Operating system opens the captive portal
        ↓
CaptivePortal creates or restores a session
        ↓
Backend locates the client in Omada
        ↓
CaptivePortal requests client authorization
        ↓
Omada grants network access
        ↓
Authorization result is written to structured telemetry
```

CAPPORT is responsible for portal discovery and captive-state communication.

Actual network authorization is performed by the configured controller integration.

---

## Implemented Features

The project currently includes:

* CAPPORT discovery through DHCP Option 114;
* CAPPORT API support;
* responsive captive portal page;
* guest authorization through Omada Open API;
* client lookup using controller data;
* portal session management;
* authorization status tracking;
* structured JSON telemetry;
* complete MAC address logging for technical diagnostics;
* isolated error handling;
* Grafana Alloy log collection;
* Loki log storage;
* Grafana-based operational analysis;
* deployment and testing in a dedicated guest VLAN.

---

## Observability

CaptivePortal treats observability as a core platform feature.

Authorization events are written as structured JSON records and can include:

* session identifier;
* client IP address;
* client MAC address;
* authorization attempt number;
* controller lookup result;
* authorization result;
* execution duration;
* failure reason;
* module and event names;
* schema version;
* server timestamp.

Example:

```json
{
  "timestamp": "2026-07-28T08:30:15Z",
  "level": "info",
  "service": "captive_portal",
  "module": "auth_telemetry",
  "event": "authorization_succeeded",
  "schema_version": 1,
  "session_id": "example-session-id",
  "client_ip": "192.168.50.24",
  "client_mac": "AA:BB:CC:DD:EE:FF",
  "attempt_number": 1
}
```

The current telemetry pipeline is:

```text
CaptivePortal
        ↓
Structured JSON log files
        ↓
Grafana Alloy
        ↓
Grafana Loki
        ↓
Grafana
```

Grafana configuration and dashboard development are maintained separately from the application code.

---

## Architecture

The project is divided into several logical layers.

### Portal Layer

Responsible for:

* rendering the captive portal;
* presenting connection progress;
* displaying authorization results;
* communicating with backend API endpoints;
* handling retry actions.

### Session Layer

Responsible for:

* creating portal sessions;
* restoring active sessions;
* tracking authorization attempts;
* maintaining session state;
* preventing conflicting operations.

### Controller Integration Layer

Responsible for:

* controller authentication;
* client discovery;
* client authorization;
* controller-specific API communication;
* normalization of controller responses.

The first adapter targets TP-Link Omada.

Future adapters may support other controllers or access-control systems without replacing the portal and session layers.

### Telemetry Layer

Responsible for:

* structured application events;
* authorization diagnostics;
* performance measurements;
* failure classification;
* integration with the existing logging pipeline.

### Integration Layer

Reserved for incoming events and external systems, including:

* Omada webhooks;
* controller lifecycle events;
* client disconnect events;
* traffic statistics;
* additional infrastructure integrations.

---

## Repository Structure

The exact structure may evolve as the project grows.

```text
CaptivePortal/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── exceptions.py
│   ├── logger.py
│   ├── settings.py
│   └── integrations/
│       └── omada/
├── logs/
├── tests/
├── run.py
├── requirements.txt
├── .gitignore
└── README.md
```

Controller-specific functionality should remain inside the corresponding integration module rather than being mixed with the core portal logic.

---

## Development Setup

### Requirements

* Linux server or development environment;
* Python 3;
* access to the target network controller;
* network connectivity between CaptivePortal and the controller;
* DHCP server capable of providing Option 114 for CAPPORT discovery.

### Installation

Clone the repository:

```bash
git clone <repository-url>
cd CaptivePortal
```

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure the application using the existing settings system in:

```text
app/settings.py
app/config.py
```

Run the application:

```bash
python run.py
```

Deployment-specific controller credentials, secrets, addresses, and tokens must not be committed to the repository.

---

## Current Development Roadmap

### Portal Reliability

* manual retry without reloading the page;
* reuse of the existing session during retry;
* prevention of parallel authorization workers;
* improved handling of delayed DHCP and unstable Wi-Fi connectivity.

### Client-Side Telemetry

Planned events include:

* portal request received;
* frontend script started;
* page fully loaded;
* page visible;
* authorization UI started;
* retry requested.

This will make it possible to distinguish:

* portal loading failures;
* frontend failures;
* DHCP delays;
* controller discovery delays;
* authorization failures.

### Omada Webhook Integration

A permanent Omada webhook receiver is planned as a dedicated integration module.

Initial responsibilities:

* accept webhook requests;
* verify the source;
* preserve the original payload;
* write structured webhook logs;
* provide real controller data for further development.

Later stages may include:

* client connection events;
* client disconnect events;
* traffic counter collection;
* session completion events;
* correlation with CaptivePortal sessions.

### Guest Traffic Accounting

The intended model is to obtain traffic statistics from the network controller rather than estimate them from portal HTTP traffic.

Potential session metrics:

* downloaded bytes;
* uploaded bytes;
* total traffic;
* session duration;
* connection and disconnect time;
* access point;
* SSID;
* controller-reported termination reason.

Implementation will be based on verified Omada webhook and Open API data collected during live testing.

### Additional Controller Support

The long-term architecture may support:

* other wireless controllers;
* router-based authorization;
* RADIUS or CoA integrations;
* firewall or ACL-based access control;
* custom authorization adapters.

---

## Development Principles

The project follows several practical engineering rules:

1. Real controller behavior is verified through live testing before architecture is finalized.
2. Permanent modules are developed incrementally instead of being replaced by temporary prototypes.
3. Controller-specific logic must not leak into the universal portal core.
4. Telemetry failure must never become an authorization failure.
5. Secrets and credentials must never be written to logs.
6. Every development stage must leave the system in a working state.
7. Operational decisions should be based on collected telemetry rather than assumptions.

---

## Security Considerations

The project should be deployed only after reviewing environment-specific security requirements.

Expected security controls include:

* secrets stored outside source code;
* controller credentials excluded from Git;
* validation of incoming webhook sources;
* token or signature validation where supported;
* request body size limits;
* rate limiting;
* structured security logging;
* protection against duplicate and parallel operations;
* strict separation of frontend data and trusted backend state.

Frontend-provided values must not be treated as authoritative for:

* client authorization state;
* MAC address ownership;
* controller results;
* traffic totals;
* final session status.

---

## Testing Strategy

Development is validated in a dedicated guest VLAN to keep experiments isolated from the primary network.

Testing includes:

* normal client authorization;
* delayed client appearance in Omada;
* unstable wireless connectivity;
* DHCP delays;
* portal page reloads;
* repeated authorization attempts;
* controller API errors;
* logging and telemetry delivery;
* application restart behavior.

Live tests are used to define controller behavior before implementing dependent features.

---

## Product Direction

CaptivePortal is being developed as more than a single-purpose login page.

The long-term direction is a reusable captive access platform providing:

* configurable portal experiences;
* controller-independent authorization workflows;
* session lifecycle management;
* real-time operational telemetry;
* guest traffic analytics;
* failure diagnostics;
* external integration support;
* deployment across different organizations and network environments.

The current Omada deployment serves as the first production-style reference implementation.

---

## Project Status

The platform is currently operational in a controlled test environment.

Working components include:

* CAPPORT-based discovery;
* portal delivery;
* Omada client authorization;
* structured telemetry;
* centralized log collection;
* Grafana-based monitoring.

The project remains under active development and should not yet be considered a finished general-availability release.

---

## License

No public license has been assigned to the project yet.

Until a license is explicitly added, the source code should be treated as proprietary and not redistributed or reused outside the project without permission.
