#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

EXPECTED_MAIN = "1bfc35b1669ae1ffb7f3f2f36147465328de953b"
BRANCH = "docs/readme-visual-architecture-atlas"
COMMIT_MESSAGE = "docs: expose visual architecture in root readmes"
PR_TITLE = "docs: expose CaptivPortal visual architecture in root READMEs"

ATLAS_BEGIN = "<!-- README-LANDING-VISUAL-ATLAS:BEGIN -->"
ATLAS_END = "<!-- README-LANDING-VISUAL-ATLAS:END -->"
DF_BEGIN = "<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:BEGIN -->"
DF_END = "<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:END -->"

DF_RU_TITLES = {
    "DF-01": "Полный end-to-end путь",
    "DF-02": "Источники evidence / origins",
    "DF-03": "Evidence + source health + time",
    "DF-04": "Сборка snapshot",
    "DF-05": "Pure deterministic classification core",
    "DF-06": "Fusion по отдельным dimensions",
    "DF-07": "Knowledge и policy",
    "DF-08": "Runtime profile / admission lifecycle",
    "DF-09": "Artifact / audit lineage",
    "DF-10": "Post-Auth integration / worker",
    "DF-11": "История классификации устройства",
    "DF-12": "Admin presentation read path",
    "DF-13": "UI state semantics",
    "DF-14": "Failure isolation",
    "DF-15": "Production components and stores",
    "DF-16": "Current Device Fingerprint vs future Traffic Enrichment",
}

DF_RU_PURPOSE = {
    "DF-01": "Весь production-путь от клиента и passive evidence до persisted ClassificationResult и Home / Device Card.",
    "DF-02": "Независимые origin families и правило: повторные строки одного origin не становятся дополнительными votes.",
    "DF-03": "Связь evidence, source health и времени; отсутствие/устаревание источника остаётся явным состоянием.",
    "DF-04": "Bounded snapshot assembly перед классификацией и граница SnapshotContentPolicy / SnapshotExecutionPolicy.",
    "DF-05": "Чистое deterministic classification core без Auth/CAPPORT authority и без product-side inference.",
    "DF-06": "Независимый fusion для device_class, platform_family, manufacturer_family и model_family.",
    "DF-07": "Versioned knowledge/policy boundary, необходимый для воспроизводимости результата.",
    "DF-08": "Runtime profile, candidate/admission lifecycle и граница между accepted production artifact и новым candidate.",
    "DF-09": "Artifact identity, audit lineage и reacceptance boundary при семантическом изменении classifier implementation.",
    "DF-10": "Post-authorization durable job path: подтверждённый AuthRun создаёт bounded classification/integration work.",
    "DF-11": "Append/history модель классификаций и связь с Device/Visit без переписывания исходной evidence-history.",
    "DF-12": "Production-only read path из Classification SQLite в presentation service и далее Home / Device Card.",
    "DF-13": "Разницу между no result, completed Unknown и Unavailable; эти состояния не взаимозаменяемы.",
    "DF-14": "Failure isolation: сбой fingerprint не ломает guest authorization, CAPPORT или core Admin data.",
    "DF-15": "Production components, auxiliary services и owned stores; repository component не доказывает live service state.",
    "DF-16": "Границу: Device Fingerprint отвечает «что это за устройство?», а future DTI — «как оно использует сеть?».",
}


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="strict",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and cp.returncode != 0:
        details = "\n".join(x.rstrip() for x in (cp.stdout, cp.stderr) if x.strip())
        raise RuntimeError(
            f"command failed ({cp.returncode}): {' '.join(cmd)}"
            + (f"\n{details}" if details else "")
        )
    return cp


def git(repo: Path, *args: str) -> str:
    return run(["git", *args], repo).stdout.strip()


def replace_marked(text: str, begin: str, end: str, replacement: str) -> str:
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), flags=re.DOTALL)
    count = len(pattern.findall(text))
    if count != 1:
        raise RuntimeError(f"expected exactly one marked block {begin!r}..{end!r}; found {count}")
    return pattern.sub(replacement.rstrip(), text, count=1)


def insert_or_replace_after_anchor(
    text: str, *, anchor: str, begin: str, end: str, block: str
) -> str:
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), flags=re.DOTALL)
    if pattern.search(text):
        return pattern.sub(block.rstrip(), text, count=1)

    count = text.count(anchor)
    if count != 1:
        raise RuntimeError(f"expected exactly one insertion anchor; found {count}: {anchor!r}")
    return text.replace(anchor, anchor + "\n\n" + block.rstrip(), 1)


def parse_df_sections(source: str) -> list[dict[str, str]]:
    heading_re = re.compile(r"(?m)^##\s+\d+\.\s+(DF-\d{2})\s+[—-]\s+(.+?)\s*$")
    matches = list(heading_re.finditer(source))
    if len(matches) != 16:
        raise RuntimeError(f"expected exactly 16 canonical DF sections, found {len(matches)}")

    result: list[dict[str, str]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
        body = source[start:end]

        mer = re.search(r"```mermaid\s*\n(.*?)\n```", body, flags=re.DOTALL)
        if not mer:
            raise RuntimeError(f"{match.group(1)}: Mermaid block not found")

        def field(name: str) -> str:
            fm = re.search(rf"(?m)^\*\*{re.escape(name)}:\*\*\s*(.+?)\s*$", body)
            if not fm:
                raise RuntimeError(f"{match.group(1)}: field {name!r} not found")
            return fm.group(1).strip()

        result.append({
            "id": match.group(1),
            "title": match.group(2).strip(),
            "purpose": field("Purpose"),
            "inputs": field("Inputs"),
            "outputs": field("Outputs"),
            "persistence": field("Persistence boundary"),
            "failure": field("Failure behavior"),
            "owner": field("Authoritative owner/module"),
            "mermaid": mer.group(1).rstrip(),
        })

    expected_ids = [f"DF-{i:02d}" for i in range(1, 17)]
    actual_ids = [x["id"] for x in result]
    if actual_ids != expected_ids:
        raise RuntimeError(f"DF section order mismatch: {actual_ids}")
    return result


def build_top_atlas_en() -> str:
    return r'''<!-- README-LANDING-VISUAL-ATLAS:BEGIN -->
## Why CaptivPortal exists — visual map

CaptivPortal is no longer only a captive-login page. It is the application layer
between guest access, Omada, durable network evidence and an operator-facing
product surface.

| Problem | CaptivPortal responsibility | Product result |
|---|---|---|
| Guest must obtain controlled Wi-Fi access | One verified authorization engine for External Portal + CAPPORT | Bounded guest authorization |
| Authorization events are not enough for history | Registry + Visit Lifecycle preserve durable identity/session facts | Device and Visit history |
| Operators need trustworthy current state | Current State persists active wireless client/AP evidence | Home / Device Current Context |
| Operators need historical network evidence | Observation + Traffic/Analytics read persisted facts | Traffic and Analytics products |
| Controller `device_type` is not enough for device identity | Passive deterministic Device Fingerprint classifies bounded normalized evidence | Fingerprint Type + Fingerprint Information |
| Product UI must not depend on raw infrastructure | AdminQueryService/read services mediate product data | Native Admin Web |
| Engineering needs deep diagnostics | Telemetry → Loki/Grafana remains a separate observability plane | Engineering diagnostics |

### How the platform works end to end

```mermaid
flowchart TB
    Client[Guest Wi-Fi client]

    subgraph Access["Access / authorization"]
      Entry[External Portal / CAPPORT]
      Auth[AuthSessionManager + AuthWorker]
      Provider[Shared OmadaProvider]
      Omada[(Omada Controller)]
    end

    subgraph Facts["Durable facts"]
      Snap[Authorized Snapshot]
      Registry[(Visitor Registry)]
      Visit[(Visit Lifecycle)]
      Obs[(Observation)]
      Current[(Current State)]
    end

    subgraph Fingerprint["Device Fingerprint"]
      Mirror[SPAN / passive network evidence]
      PortalEvidence[Portal evidence]
      FPEvidence[(Fingerprint Evidence)]
      Classifier[Deterministic classifier]
      FPResult[(PRODUCTION ClassificationResult)]
    end

    subgraph Product["Read / product plane"]
      Reads[Read services / Analytics / Traffic]
      AdminQuery[AdminQueryService]
      Admin[Native Admin Web]
    end

    subgraph Eng["Engineering observability"]
      Telemetry[Telemetry / journals]
      Loki[(Loki)]
      Grafana[Grafana]
    end

    Client --> Entry --> Auth --> Provider --> Omada
    Auth --> Snap --> Registry
    Auth --> Visit
    Omada --> Obs
    Omada --> Current

    Client --> Mirror --> FPEvidence
    Entry --> PortalEvidence --> FPEvidence
    FPEvidence --> Classifier --> FPResult

    Registry --> Reads
    Visit --> Reads
    Obs --> Reads
    Current --> Reads
    FPResult --> AdminQuery
    Reads --> AdminQuery --> Admin

    Auth --> Telemetry
    Reads --> Telemetry
    Telemetry --> Loki --> Grafana
```

### Data-processing rule

```mermaid
flowchart LR
    Source[Controller / Portal / passive sensor] --> Acquire[Bounded acquisition]
    Acquire --> Persist[(Owned persistence)]
    Persist --> Read[Read service]
    Read --> Derive[Analytics / product interpretation]
    Derive --> Present[AdminQueryService / Admin Web]
    Present -. no direct source polling .-> Blocked[No query-time history manufacturing]
```

The permanent direction is **source → normalized fact → owned persistence → read
boundary → interpretation → presentation**. Product reads do not manufacture
missing history by polling Omada on demand.

### Subsystem ownership matrix

| Layer | Why it exists | Canonical owner/source | Durable boundary / output |
|---|---|---|---|
| Guest authorization | Decide whether guest access actually succeeded | AuthSessionManager / AuthWorker / shared OmadaProvider | verified controller state + telemetry |
| Visitor identity/history | Keep durable device/history identity | Visitor Registry | `visitor_registry.sqlite3` |
| Visit Lifecycle | Model real Site-aware visits rather than AuthSessions | Visit Lifecycle | `visits.sqlite3` v2 |
| Historical wireless/AP facts | Preserve measurements over time | Observation Foundation | `observations.sqlite3` v1 |
| Current wireless state | Preserve current active client/AP evidence | Current State | `current_state.sqlite3` v1 |
| Traffic / Analytics | Derive bounded product views from stored facts | Analytics read services | read models; no source writes |
| Device Fingerprint | Answer “what is this device?” from passive bounded evidence | Device Fingerprint | Evidence / Classification / Integration stores |
| Admin Web | Present Site-safe operator views | AdminQueryService + Admin Web | read-only product presentation |
| Engineering observability | Diagnose implementation/runtime behavior | telemetry / Alloy / Loki / Grafana | engineering-only observability |

### Hard boundaries visible from the landing page

| Boundary | Invariant |
|---|---|
| Authorization success | Successful HTTP call is not enough; final controller state is verified |
| Analytics | Reads persisted facts; does not call Omada to manufacture history |
| Admin browser | Does not directly read SQLite, Omada, Loki, Grafana or internal bearer APIs |
| Optional subsystems | May degrade/fail independently of guest authorization |
| Evidence semantics | `missing / unknown / stale / insufficient / unavailable != 0` |
| Omada provider | One process → one shared provider/token lifecycle |
| Device Fingerprint | Advisory only; never authorizes, blocks, disconnects or changes CAPPORT |
| DTI | Separate future program; not silently folded into Device Fingerprint |

The rest of this README contains the detailed processing diagrams for
authorization, persistence, Visit Lifecycle, analytics, Traffic, Admin Web, Home,
observability and the complete sixteen-diagram Device Fingerprint atlas.
<!-- README-LANDING-VISUAL-ATLAS:END -->'''


def build_top_atlas_ru() -> str:
    return r'''<!-- README-LANDING-VISUAL-ATLAS:BEGIN -->
## Зачем существует CaptivPortal — визуальная карта

CaptivPortal уже не просто страница captive-login. Это application layer между
гостевым доступом, Omada, долговременным network evidence и operator-facing
product surface.

| Задача | За что отвечает CaptivPortal | Результат |
|---|---|---|
| Гостю нужен контролируемый Wi-Fi access | Один verified authorization engine для External Portal + CAPPORT | Bounded guest authorization |
| Одних auth events недостаточно для истории | Registry + Visit Lifecycle сохраняют durable identity/session facts | История Devices и Visits |
| Оператору нужен честный current state | Current State хранит active wireless client/AP evidence | Home / Device Current Context |
| Нужна историческая сеть и Traffic | Observation + Traffic/Analytics читают persisted facts | Traffic и Analytics products |
| Controller `device_type` не равен fingerprint identity | Passive deterministic Device Fingerprint классифицирует bounded normalized evidence | Fingerprint Type + Fingerprint Information |
| Product UI не должен зависеть от raw infrastructure | AdminQueryService/read services являются product boundary | Native Admin Web |
| Инженерам нужна глубокая диагностика | Telemetry → Loki/Grafana остаётся отдельным observability plane | Engineering diagnostics |

### Как платформа работает end to end

```mermaid
flowchart TB
    Client[Guest Wi-Fi client]

    subgraph Access["Access / authorization"]
      Entry[External Portal / CAPPORT]
      Auth[AuthSessionManager + AuthWorker]
      Provider[Shared OmadaProvider]
      Omada[(Omada Controller)]
    end

    subgraph Facts["Durable facts"]
      Snap[Authorized Snapshot]
      Registry[(Visitor Registry)]
      Visit[(Visit Lifecycle)]
      Obs[(Observation)]
      Current[(Current State)]
    end

    subgraph Fingerprint["Device Fingerprint"]
      Mirror[SPAN / passive network evidence]
      PortalEvidence[Portal evidence]
      FPEvidence[(Fingerprint Evidence)]
      Classifier[Deterministic classifier]
      FPResult[(PRODUCTION ClassificationResult)]
    end

    subgraph Product["Read / product plane"]
      Reads[Read services / Analytics / Traffic]
      AdminQuery[AdminQueryService]
      Admin[Native Admin Web]
    end

    subgraph Eng["Engineering observability"]
      Telemetry[Telemetry / journals]
      Loki[(Loki)]
      Grafana[Grafana]
    end

    Client --> Entry --> Auth --> Provider --> Omada
    Auth --> Snap --> Registry
    Auth --> Visit
    Omada --> Obs
    Omada --> Current

    Client --> Mirror --> FPEvidence
    Entry --> PortalEvidence --> FPEvidence
    FPEvidence --> Classifier --> FPResult

    Registry --> Reads
    Visit --> Reads
    Obs --> Reads
    Current --> Reads
    FPResult --> AdminQuery
    Reads --> AdminQuery --> Admin

    Auth --> Telemetry
    Reads --> Telemetry
    Telemetry --> Loki --> Grafana
```

### Главное правило обработки данных

```mermaid
flowchart LR
    Source[Controller / Portal / passive sensor] --> Acquire[Bounded acquisition]
    Acquire --> Persist[(Owned persistence)]
    Persist --> Read[Read service]
    Read --> Derive[Analytics / product interpretation]
    Derive --> Present[AdminQueryService / Admin Web]
    Present -. no direct source polling .-> Blocked[No query-time history manufacturing]
```

Постоянное направление: **source → normalized fact → owned persistence → read
boundary → interpretation → presentation**. Product-read не создаёт отсутствующую
историю query-time опросом Omada.

### Кто чем владеет

| Слой | Зачем нужен | Канонический owner/source | Durable boundary / output |
|---|---|---|---|
| Guest authorization | Решить, действительно ли guest access получен | AuthSessionManager / AuthWorker / shared OmadaProvider | verified controller state + telemetry |
| Visitor identity/history | Сохранить durable device/history identity | Visitor Registry | `visitor_registry.sqlite3` |
| Visit Lifecycle | Моделировать Site-aware Visit, а не считать AuthSession визитом | Visit Lifecycle | `visits.sqlite3` v2 |
| Historical wireless/AP facts | Хранить measurements во времени | Observation Foundation | `observations.sqlite3` v1 |
| Current wireless state | Хранить текущие active client/AP facts | Current State | `current_state.sqlite3` v1 |
| Traffic / Analytics | Строить product views из сохранённых фактов | Analytics read services | read models; без source writes |
| Device Fingerprint | Ответить «что это за устройство?» по passive bounded evidence | Device Fingerprint | Evidence / Classification / Integration stores |
| Admin Web | Показать Site-safe operator view | AdminQueryService + Admin Web | read-only product presentation |
| Engineering observability | Диагностировать runtime/implementation | telemetry / Alloy / Loki / Grafana | engineering-only observability |

### Жёсткие границы, которые должны быть видны прямо из README

| Граница | Инвариант |
|---|---|
| Authorization success | Успешного HTTP transport недостаточно; проверяется final controller state |
| Analytics | Читает persisted facts и не опрашивает Omada для создания истории |
| Admin browser | Не читает напрямую SQLite, Omada, Loki, Grafana или internal bearer API |
| Optional subsystems | Могут degraded/fail независимо от guest authorization |
| Evidence semantics | `missing / unknown / stale / insufficient / unavailable != 0` |
| Omada provider | Один process → один shared provider/token lifecycle |
| Device Fingerprint | Advisory only; не авторизует, не блокирует, не disconnect и не меняет CAPPORT |
| DTI | Отдельная future program; не является скрытым расширением Device Fingerprint |

Ниже в этом же README находятся подробные схемы authorization, persistence,
Visit Lifecycle, Analytics, Traffic, Admin Web, Home, observability и полный
16-схемный Device Fingerprint atlas.
<!-- README-LANDING-VISUAL-ATLAS:END -->'''


def df_index_table_en(sections: list[dict[str, str]]) -> str:
    rows = [
        "| ID | Diagram | Why it is on the landing README |",
        "|---|---|---|",
    ]
    for s in sections:
        rows.append(f"| {s['id']} | {s['title']} | {s['purpose']} |")
    return "\n".join(rows)


def df_index_table_ru(sections: list[dict[str, str]]) -> str:
    rows = [
        "| ID | Схема | Что показывает |",
        "|---|---|---|",
    ]
    for s in sections:
        rows.append(f"| {s['id']} | {DF_RU_TITLES[s['id']]} | {DF_RU_PURPOSE[s['id']]} |")
    return "\n".join(rows)


def build_df_en(sections: list[dict[str, str]]) -> str:
    parts = [r'''<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:BEGIN -->
## Device Fingerprint — current production

Device Fingerprint is a production-active passive/advisory classification
subsystem. The landing README intentionally carries the complete visual atlas so
a reader can understand the subsystem without opening a second document.

```text
runtime / production implementation checkpoint = 7c7c0919c3e546f499b5252ea9479d32c8f494d7
runtime / production tree = dbf3e3804931d637ef1ec569128746ebce5c141a
TASK-DEVICE-FINGERPRINT-04 = CLOSED / ACCEPTED
TASK-DEVICE-FINGERPRINT-05 = CLOSED / INTEGRATED
TASK-DEVICE-FINGERPRINT-05-PERF-01 = CLOSED
TASK-DEVICE-FINGERPRINT-06 = PRODUCTION PASS / DEPLOYED / ADMIN VISIBLE
captive-portal.service = active
fingerprint-classification.service = active
```

### What Device Fingerprint answers

| Product dimension | Meaning |
|---|---|
| `device_class` | broad device class shown as Fingerprint **Type** |
| `platform_family` | fingerprint-derived platform family |
| `manufacturer_family` | fingerprint-derived manufacturer family |
| `model_family` | fingerprint-derived model family |

Classification support is `none | low | medium | high`; it is not a probability.

| Dimension/result state | Product meaning |
|---|---|
| `resolved` | supported value exists |
| `recognized_out_of_scope` | evidence is recognized but outside the admitted taxonomy/scope |
| `unknown` | classification completed without a supported value |
| `insufficient_evidence` | available evidence is not sufficient |
| `conflicting_evidence` | admitted evidence conflicts |
| no authoritative production result | UI shows `—` |
| completed unresolved dimension | UI shows `Unknown` |
| read/persistence path unavailable | UI shows `Unavailable` / fail-soft `—` |

Permanent UI rule:

```text
Type     = fingerprint device_class
Platform = controller / Omada device_type

Type != Platform
Controller Platform NEVER backfills Fingerprint Type
```

### Evidence origins

| Origin | Role |
|---|---|
| DHCP | passive normalized network evidence |
| Portal | bounded application/Portal evidence |
| TCP | passive TCP SYN fingerprint evidence |
| TLS | normalized TLS client fingerprint evidence |
| QUIC | normalized QUIC client fingerprint evidence |
| MAC Registry | knowledge-derived origin, not packet evidence |

Canonical origin order:

```text
dhcp, portal, tcp, tls, quic, mac_registry
```

Repeated rows from the same origin are not independent votes.

### Device Fingerprint architecture atlas — all 16 diagrams

''', df_index_table_en(sections), "\n"]

    for s in sections:
        parts.append(f"\n#### {s['id']} — {s['title']}\n\n")
        parts.append(f"- **Purpose:** {s['purpose']}\n")
        parts.append(f"- **Inputs:** {s['inputs']}\n")
        parts.append(f"- **Outputs:** {s['outputs']}\n")
        parts.append(f"- **Persistence boundary:** {s['persistence']}\n")
        parts.append(f"- **Failure behavior:** {s['failure']}\n")
        parts.append(f"- **Authoritative owner/module:** {s['owner']}\n\n")
        parts.append("```mermaid\n" + s["mermaid"] + "\n```\n")

    parts.append(r'''
### Current vs future Device Traffic Intelligence

Device Traffic Enrichment / Device Intelligence is a **separate program**. The
accepted v0.3 architecture does not change Device Fingerprint semantics.

Current program state:

```text
DTI architecture = FINAL / TECH LEAD ACCEPTED
TASK-DTI-00 = APPROVED FOR SYSADMIN RESEARCH
TASK-DTI-00 mode = RESEARCH / LAB / INVENTORY
Implementation = NO
Coder action = HOLD
Production feature activation = NO
Production configuration change = NO
```

DTI-00 proves the real SPAN/capture path before any implementation: topology,
direction, L2 identity, VLAN/Site binding, pre/post-NAT placement, host capture
path, drops/completeness evidence, resource baseline and coexistence with the
accepted Fingerprint sensor. It does not implement DTI.

The exact engineering contract remains in
[`docs/modules/device-fingerprint.md`](docs/modules/device-fingerprint.md); the
README now mirrors its complete visual architecture instead of hiding that
architecture behind the link.
<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:END -->''')
    return "".join(parts)


def build_df_ru(sections: list[dict[str, str]]) -> str:
    parts = [r'''<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:BEGIN -->
## Device Fingerprint — текущее production-состояние

Device Fingerprint — production-active пассивная/advisory подсистема
классификации. Полный visual atlas намеренно находится прямо в landing README,
чтобы архитектуру можно было понять без перехода в другой документ.

```text
runtime / production implementation checkpoint = 7c7c0919c3e546f499b5252ea9479d32c8f494d7
runtime / production tree = dbf3e3804931d637ef1ec569128746ebce5c141a
TASK-DEVICE-FINGERPRINT-04 = CLOSED / ACCEPTED
TASK-DEVICE-FINGERPRINT-05 = CLOSED / INTEGRATED
TASK-DEVICE-FINGERPRINT-05-PERF-01 = CLOSED
TASK-DEVICE-FINGERPRINT-06 = PRODUCTION PASS / DEPLOYED / ADMIN VISIBLE
captive-portal.service = active
fingerprint-classification.service = active
```

### На какие вопросы отвечает Device Fingerprint

| Product dimension | Смысл |
|---|---|
| `device_class` | широкий класс устройства; в Home это Fingerprint **Type** |
| `platform_family` | fingerprint-derived platform family |
| `manufacturer_family` | fingerprint-derived manufacturer family |
| `model_family` | fingerprint-derived model family |

Support: `none | low | medium | high`; это не probability.

| Состояние | Product meaning |
|---|---|
| `resolved` | поддерживаемое значение определено |
| `recognized_out_of_scope` | evidence распознано, но находится вне admitted taxonomy/scope |
| `unknown` | классификация завершена без supported value |
| `insufficient_evidence` | evidence недостаточно |
| `conflicting_evidence` | admitted evidence конфликтует |
| authoritative production result ещё нет | UI показывает `—` |
| classification завершена, dimension не resolved | UI показывает `Unknown` |
| read/persistence path недоступен | UI показывает `Unavailable` / fail-soft `—` |

Постоянный UI contract:

```text
Type     = fingerprint device_class
Platform = controller / Omada device_type

Type != Platform
Controller Platform NEVER backfills Fingerprint Type
```

### Evidence origins

| Origin | Роль |
|---|---|
| DHCP | passive normalized network evidence |
| Portal | bounded application/Portal evidence |
| TCP | passive TCP SYN fingerprint evidence |
| TLS | normalized TLS client fingerprint evidence |
| QUIC | normalized QUIC client fingerprint evidence |
| MAC Registry | knowledge-derived origin, а не packet evidence |

Канонический порядок:

```text
dhcp, portal, tcp, tls, quic, mac_registry
```

Повторные строки одного origin не становятся независимыми votes.

### Device Fingerprint architecture atlas — все 16 схем

''', df_index_table_ru(sections), "\n"]

    for s in sections:
        sid = s["id"]
        parts.append(f"\n#### {sid} — {DF_RU_TITLES[sid]}\n\n")
        parts.append(f"{DF_RU_PURPOSE[sid]}\n\n")
        parts.append("```mermaid\n" + s["mermaid"] + "\n```\n")

    parts.append(r'''
### Current Device Fingerprint и future DTI — разные программы

Device Traffic Enrichment / Device Intelligence — **отдельная программа**.
Принятая архитектура v0.3 не меняет Device Fingerprint semantics.

Текущий статус:

```text
DTI architecture = FINAL / TECH LEAD ACCEPTED
TASK-DTI-00 = APPROVED FOR SYSADMIN RESEARCH
TASK-DTI-00 mode = RESEARCH / LAB / INVENTORY
Implementation = NO
Coder action = HOLD
Production feature activation = NO
Production configuration change = NO
```

DTI-00 должен доказать реальный SPAN/capture path до любой реализации: topology,
direction, L2 identity, VLAN/Site binding, pre/post-NAT placement, полный host
capture path, drops/completeness evidence, resource baseline и безопасное
сосуществование с accepted Fingerprint sensor. DTI-00 ничего не реализует.

Точный engineering contract остаётся в
[`docs/modules/device-fingerprint.md`](docs/modules/device-fingerprint.md), но
его полный visual architecture больше не спрятан за этой ссылкой.
<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:END -->''')
    return "".join(parts)


def update_dti_roadmap_en(text: str) -> str:
    pattern = re.compile(
        r"`Device Traffic Enrichment / Device Intelligence \(DTI\)` is a separate\n"
        r"architecture/roadmap program whose v0\.3 architecture is FINAL / TECH LEAD\n"
        r"ACCEPTED and whose roadmap registration is authorized\. It is not part of\n"
        r"TASK-DEVICE-FINGERPRINT-06\. Implementation remains NOT authorized, Coder remains\n"
        r"HOLD, production remains unchanged, and the next executable program step is\n"
        r"TASK-DTI-00 in RESEARCH / LAB / INVENTORY mode\."
    )
    replacement = (
        "`Device Traffic Enrichment / Device Intelligence (DTI)` is a separate "
        "architecture/roadmap program. Its v0.3 architecture is **FINAL / TECH LEAD "
        "ACCEPTED** and roadmap registration is authorized. `TASK-DTI-00` is now "
        "**APPROVED FOR SYSADMIN RESEARCH** in `RESEARCH / LAB / INVENTORY` mode. "
        "Implementation remains **NO**, Coder remains **HOLD**, and production feature "
        "activation/configuration remain **NO**."
    )
    new, n = pattern.subn(replacement, text, count=1)
    if n != 1:
        raise RuntimeError(f"EN DTI roadmap status anchor mismatch: replacements={n}")
    return new


def update_dti_roadmap_ru(text: str) -> str:
    pattern = re.compile(
        r"`Device Traffic Enrichment / Device Intelligence \(DTI\)` — отдельная\n"
        r"architecture/roadmap program; архитектура v0\.3 имеет статус FINAL / TECH LEAD\n"
        r"ACCEPTED, а регистрация roadmap авторизована\. DTI не является частью\n"
        r"TASK-DEVICE-FINGERPRINT-06\. Implementation по-прежнему НЕ авторизован, Coder\n"
        r"остаётся HOLD, production не меняется, а следующий executable program step —\n"
        r"TASK-DTI-00 в режиме RESEARCH / LAB / INVENTORY\."
    )
    replacement = (
        "`Device Traffic Enrichment / Device Intelligence (DTI)` — отдельная "
        "architecture/roadmap program. Архитектура v0.3 имеет статус **FINAL / TECH "
        "LEAD ACCEPTED**, roadmap registration авторизована. `TASK-DTI-00` теперь "
        "**APPROVED FOR SYSADMIN RESEARCH** в режиме `RESEARCH / LAB / INVENTORY`. "
        "Implementation остаётся **NO**, Coder — **HOLD**, production feature "
        "activation/configuration — **NO**."
    )
    new, n = pattern.subn(replacement, text, count=1)
    if n != 1:
        raise RuntimeError(f"RU DTI roadmap status anchor mismatch: replacements={n}")
    return new


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--repo",
        default=r"C:\Users\Zaur Navi\Downloads\CaptivPortal-KB-DF-Sync-R2-2026-10-04",
    )
    ap.add_argument("--no-pr", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        raise RuntimeError(f"not a git repository: {repo}")

    print("=== 1. PRECHECK / BASELINE ===")
    if git(repo, "status", "--porcelain"):
        raise RuntimeError("worktree is not clean")

    run(["git", "fetch", "origin", "main", "--prune"], repo)
    remote_main = git(repo, "rev-parse", "origin/main")
    if remote_main != EXPECTED_MAIN:
        raise RuntimeError(
            f"origin/main moved; expected {EXPECTED_MAIN}, got {remote_main}. STOP."
        )

    local_branches = git(repo, "branch", "--format=%(refname:short)").splitlines()
    if BRANCH in local_branches:
        raise RuntimeError(f"local branch already exists: {BRANCH}")

    remote_line = run(
        ["git", "ls-remote", "--heads", "origin", f"refs/heads/{BRANCH}"], repo
    ).stdout.strip()
    if remote_line:
        raise RuntimeError(f"remote branch already exists: {BRANCH}")

    print(f"PASS: origin/main={remote_main}")
    print("PASS: clean worktree")
    print("PASS: target branch does not exist")

    print("\n=== 2. CREATE DOCS-ONLY BRANCH ===")
    run(["git", "switch", "-c", BRANCH, "origin/main"], repo)
    if git(repo, "rev-parse", "HEAD") != EXPECTED_MAIN:
        raise RuntimeError("branch did not start from expected main")
    print(f"PASS: {BRANCH}")

    print("\n=== 3. EXTRACT CANONICAL DEVICE FINGERPRINT VISUAL ATLAS ===")
    df_source = (repo / "docs" / "modules" / "device-fingerprint.md").read_text(encoding="utf-8")
    sections = parse_df_sections(df_source)
    print("PASS: extracted DF-01..DF-16 with metadata + Mermaid")

    readme_path = repo / "README.md"
    readme_ru_path = repo / "README_RU.md"
    en = readme_path.read_text(encoding="utf-8")
    ru = readme_ru_path.read_text(encoding="utf-8")

    en_anchor = "> Repository defaults, production enabled-state and dated acceptance evidence are different facts."
    ru_anchor = "> Repository defaults, production enabled-state и dated acceptance evidence — разные факты."

    en = insert_or_replace_after_anchor(
        en, anchor=en_anchor, begin=ATLAS_BEGIN, end=ATLAS_END, block=build_top_atlas_en()
    )
    ru = insert_or_replace_after_anchor(
        ru, anchor=ru_anchor, begin=ATLAS_BEGIN, end=ATLAS_END, block=build_top_atlas_ru()
    )

    en = replace_marked(en, DF_BEGIN, DF_END, build_df_en(sections))
    ru = replace_marked(ru, DF_BEGIN, DF_END, build_df_ru(sections))
    en = update_dti_roadmap_en(en)
    ru = update_dti_roadmap_ru(ru)

    readme_path.write_text(en, encoding="utf-8", newline="\n")
    readme_ru_path.write_text(ru, encoding="utf-8", newline="\n")

    print("PASS: visual map inserted")
    print("PASS: DF-01..DF-16 embedded in both root READMEs")
    print("PASS: DTI-00 status reconciled")

    print("\n=== 4. CONTENT / SCOPE GATES ===")
    changed = sorted(x for x in git(repo, "diff", "--name-only").splitlines() if x.strip())
    expected = ["README.md", "README_RU.md"]
    if changed != expected:
        raise RuntimeError(f"docs-only scope violated: {changed}")

    for path in expected:
        run(["git", "add", "--", path], repo)

    run(["git", "diff", "--cached", "--check"], repo)

    staged = sorted(x for x in git(repo, "diff", "--cached", "--name-only").splitlines() if x.strip())
    if staged != expected:
        raise RuntimeError(f"staged scope mismatch: {staged}")

    en2 = readme_path.read_text(encoding="utf-8")
    ru2 = readme_ru_path.read_text(encoding="utf-8")

    for label, text in (("README.md", en2), ("README_RU.md", ru2)):
        for i in range(1, 17):
            token = f"DF-{i:02d}"
            if token not in text:
                raise RuntimeError(f"{label}: missing {token}")
        if "README-LANDING-VISUAL-ATLAS:BEGIN" not in text:
            raise RuntimeError(f"{label}: landing visual atlas marker missing")
        if "APPROVED FOR SYSADMIN RESEARCH" not in text:
            raise RuntimeError(f"{label}: current DTI-00 research status missing")

    en_mermaid = en2.count("```mermaid")
    ru_mermaid = ru2.count("```mermaid")
    if en_mermaid < 25 or ru_mermaid < 25:
        raise RuntimeError(f"unexpected Mermaid count after atlas: EN={en_mermaid}, RU={ru_mermaid}")

    print("PASS: exact 2-file docs-only scope")
    print("PASS: git diff --cached --check")
    print(f"PASS: Mermaid count EN={en_mermaid}, RU={ru_mermaid}")
    print("PASS: no runtime/test/schema/config files changed")

    print("\n=== 5. COMMIT ===")
    run(["git", "commit", "-m", COMMIT_MESSAGE], repo)
    commit = git(repo, "rev-parse", "HEAD")
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    parent = git(repo, "rev-parse", "HEAD^")
    if parent != EXPECTED_MAIN:
        raise RuntimeError(f"commit parent mismatch: {parent}")
    if git(repo, "status", "--porcelain"):
        raise RuntimeError("worktree not clean after commit")

    print(f"COMMIT={commit}")
    print(f"TREE={tree}")
    print(f"PARENT={parent}")

    print("\n=== 6. PUSH ===")
    run(["git", "push", "-u", "origin", BRANCH], repo)
    remote_line = run(
        ["git", "ls-remote", "--heads", "origin", f"refs/heads/{BRANCH}"], repo
    ).stdout.strip()
    remote_sha = remote_line.split()[0] if remote_line else ""
    if remote_sha != commit:
        raise RuntimeError(f"remote SHA mismatch: {remote_sha} != {commit}")
    print(f"PASS: remote branch={BRANCH}")
    print(f"REMOTE={remote_sha}")

    pr_url = "NO"
    if not args.no_pr:
        print("\n=== 7. DRAFT PR ===")
        gh = run(["gh", "auth", "status"], repo, check=False)
        if gh.returncode != 0:
            raise RuntimeError("gh is not authenticated; branch pushed, Draft PR not created")

        body = f'''## Summary

Makes the root GitHub landing page carry the architecture a human reader needs
to see without opening `docs/`.

- adds a top-level visual explanation of why CaptivPortal exists and how the
  access/data/product planes connect;
- adds subsystem ownership and hard-boundary tables;
- exposes canonical Device Fingerprint DF-01..DF-16 Mermaid diagrams directly
  in both root READMEs;
- keeps Type vs Platform and `— / Unknown / Unavailable` semantics visible;
- records current DTI-00 state as APPROVED FOR SYSADMIN RESEARCH while
  implementation/Coder/production activation remain NO/HOLD/NO.

## Scope

Exactly two files:

- `README.md`
- `README_RU.md`

No runtime code, tests, schema, migrations, configuration or deployment changes.

## Baseline

- base: `main@{EXPECTED_MAIN}`
- head: `{commit}`
- tree: `{tree}`

## Validation

- exact two-file docs-only scope
- `git diff --cached --check` PASS before commit
- DF-01..DF-16 present in both root READMEs
- Mermaid count: EN={en_mermaid}, RU={ru_mermaid}
- clean worktree after commit

## Explicitly excluded

- runtime behavior
- production configuration
- merge
- deploy
'''
        body_file = repo / ".git" / "README_VISUAL_ATLAS_PR_BODY.md"
        body_file.write_text(body, encoding="utf-8", newline="\n")

        cp = run(
            [
                "gh", "pr", "create",
                "--repo", "ZaurNavi/CaptivePortal",
                "--base", "main",
                "--head", BRANCH,
                "--title", PR_TITLE,
                "--body-file", str(body_file),
                "--draft",
            ],
            repo,
        )
        pr_url = cp.stdout.strip().splitlines()[-1].strip()
        print(f"PR={pr_url}")

    print("\n============================================================")
    print("README VISUAL ARCHITECTURE PR PASS")
    print("============================================================")
    print(f"BRANCH={BRANCH}")
    print(f"COMMIT={commit}")
    print(f"TREE={tree}")
    print(f"PARENT={parent}")
    print("FILES=2")
    print(f"MERMAID_EN={en_mermaid}")
    print(f"MERMAID_RU={ru_mermaid}")
    print(f"PR={pr_url}")
    print("MERGE=NO")
    print("DEPLOY=NO")
    print("============================================================")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("\n============================================================", file=sys.stderr)
        print("STOP — README VISUAL ARCHITECTURE PR FAILED", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        print("============================================================", file=sys.stderr)
        raise
