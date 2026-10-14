# Network Intelligence V1 — Visual Architecture Atlas

Status: current production architecture
Updated: 2026-10-14
Repository / production baseline: main@27087766d3f2e104a44da3f36aa6e72a082b12de
Tree: 3fe941f1962e6df72d102ba36da60bf25f3bd70a

This atlas visualizes the production Network Intelligence V1 implementation. It is a companion to docs/modules/network-intelligence.md.

Network Intelligence and Device Fingerprint share capture infrastructure but have different semantic ownership. Device Fingerprint answers what kind of device this is. Network Intelligence answers which supported protocol families and recognized services have been observed for an authoritatively attributed Device, with explicit coverage and freshness.

## Legend

| Shape / label | Meaning |
|---|---|
| DB cylinder | durable SQLite state |
| background | auxiliary worker / non-request pipeline |
| read | bounded read-only product path |
| unavailable / pending / conflict | explicit uncertainty, never converted to zero |
| dashed red path | forbidden product path |

## NI-VIS-01 — Full End-to-End Architecture

```mermaid
flowchart LR
    C[Guest Device] --> AP[EAP / Wi-Fi]
    AP --> SW[Catalyst RSPAN]
    SW --> NIC[VM enp8s0<br/>no L3 address]

    NIC --> FS[fingerprint-sensor<br/>AF_PACKET]
    NIC --> SU[Suricata<br/>AF_PACKET]

    FS --> DF[Device Fingerprint evidence]
    SU --> EVE[DTI EVE<br/>DNS / TLS / QUIC]

    EVE -->|background write| NI01[network-metadata.service<br/>NI-01]
    NI01 --> NM[(network_metadata.sqlite3)]

    FS -->|trusted DHCP authority| NA[(network_attribution.sqlite3<br/>NI-02A)]

    NM -->|bounded read| P[network-metadata-projection.service<br/>NI-02B]
    NA -->|event-time attribution| P
    REG[(Visitor Registry)] -->|MAC to Device authority| P
    P --> NP[(network_metadata_projection.sqlite3)]

    NP -->|read| NI03[Protocol Intelligence]
    NI03 --> PA[Protocol Admin API]

    NP -->|committed recognition feed| NI04[network-service-recognition.service<br/>NI-04]
    NM -->|exact source evidence| NI04
    NI04 --> NS[(network_service_intelligence.sqlite3)]

    NS -->|materialized read only| SA[Service Intelligence Admin API]
    PA --> CARD[Device Card]
    SA --> CARD
    CARD --> RS[Recent Services]
    CARD --> ORG[Organizations]
    CARD --> CAT[Service Categories]
    CARD --> LAST[Last Service Observation]

    classDef store fill:#eef6ff,stroke:#2563eb,color:#111;
    class NM,NA,REG,NP,NS store;
```

## NI-VIS-02 — Evidence Sources and Capture

```mermaid
flowchart TB
    V20[Guest VLAN / intended network scope] --> CAT[Catalyst]
    V10[Other admitted mirrored scope] --> CAT
    CAT -->|RSPAN source VLANs 10,20<br/>RX-only final production setting| V999[RSPAN VLAN 999]
    V999 --> HOST[omv-hp physical capture NIC]
    HOST --> VM[macvtap to Ubuntu VM enp8s0<br/>pre-Cisco-NAT]

    VM --> RAW[Fingerprint raw AF_PACKET<br/>DHCP + guest outbound TCP SYN]
    VM --> SUR[Suricata AF_PACKET]
    SUR --> DTI[Network Intelligence metadata<br/>DNS / TLS / QUIC]
    SUR --> FPE[Fingerprint TLS / QUIC evidence path]

    RAW --> FP[Device Fingerprint classifier]
    FPE --> FP
    DTI --> NI[Network Intelligence pipeline]

    FP -. distinct semantic owner .-> B[Device identity/classification]
    NI -. distinct semantic owner .-> U[Network usage intelligence]

    SCOPE[Capture source + network scope + Site binding] --> DTI
    SCOPE --> FPE
```

Shared observation infrastructure does not create a shared classifier or shared product meaning. Capture is proven pre-NAT; Network Intelligence must still enforce capture/network scope before Site/Device projection.

## NI-VIS-03 — NI-01 Ingestion Lifecycle

```mermaid
flowchart TD
    EVE[Suricata DTI EVE file] --> GEN[Open source generation]
    GEN --> ANC[Verify physical identity<br/>continuity anchor]
    ANC --> READ[Bounded byte / record batch]
    READ --> NORM{Normalize}
    NORM -->|dns / tls / quic valid| OBS[Normalized observation]
    NORM -->|unsupported / invalid| FAULT[Bounded fault disposition]
    OBS --> TX[SQLite transaction]
    FAULT --> TX
    TX --> DB[(network_metadata.sqlite3)]
    TX --> CP[Durable committed checkpoint]

    CP -->|restart / replay| GEN
    ROT[rotation / truncation / continuity change] --> DECIDE[Generation transition decision]
    DECIDE --> GEN

    CRASH1[Crash before commit] --> REPLAY[Replay same uncommitted source prefix]
    CRASH2[Crash after commit] --> CP

    BAD[Advance checkpoint past unconfirmed processing]:::forbidden
    TX -. forbidden .-> BAD
    classDef forbidden fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
```

The scan position is disposable. The repository checkpoint is the durable authority. A checkpoint cannot safely advance past processing that has not committed.

## NI-VIS-04 — NI-02 / NI-02B Device Attribution

```mermaid
flowchart TD
    O[NI-01 observation<br/>Site + endpoint IP + event_at] --> COV{NI-02A source coverage<br/>usable at event time?}
    DHCP[Trusted DHCP authority facts<br/>from fingerprint-sensor] --> COV
    COV -->|no| UNAV[unavailable]
    COV -->|yes| BIND{Temporal Site + IPv4 binding}
    BIND -->|exact one authority| MAC[Site + client MAC<br/>resolved]
    BIND -->|none| UNA[unattributed]
    BIND -->|multiple| AMB[ambiguous]

    MAC --> EDGE[NI-02B device-relative edge]
    EDGE --> REG{Visitor Registry binding}
    REG -->|exact MAC Device record| AUTH[authoritative<br/>Site + MAC + Device]
    REG -->|not yet present| PEND[not_yet_registry_resolved]
    REG -->|read unavailable| RGU[registry_unavailable]

    PEND --> RETRY[bounded reconcile / late binding]
    RGU --> RETRY
    RETRY --> REG

    IP[IP-only permanent identity]:::forbidden
    O -. forbidden .-> IP
    classDef forbidden fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
```

No heuristic nearest row, IP-only permanent identity, cross-MAC merge, or unproven attribution becomes an authoritative Device fact.

## NI-VIS-05 — Protocol Intelligence

```mermaid
flowchart LR
    NP[(NI-02B projection<br/>device-relative edges)] -->|read only| PR[DeviceProtocolIntelligenceReadService]
    PR --> W24[24-hour bounded evidence window]
    W24 --> R60[Recent Protocols<br/>last 60 min]
    W24 --> LAST[Last Protocol Observation<br/>last 24 h]
    W24 --> COV[Source / Attribution / Projection coverage]
    R60 --> API[GET protocol-intelligence]
    LAST --> API
    COV --> API
    API --> UI[Device Card<br/>Network / Protocol Intelligence]

    FAM[DNS / TLS / QUIC] --> PR
    SR[Service Recognition] -. separate semantic path .-> UI
```

Protocol families are non-exclusive observations. NI-03 does not calculate service identity, traffic percentages, dominant protocol, or byte shares.

## NI-VIS-06 — Service Recognition Pipeline

```mermaid
flowchart TD
    E[Eligible NI-02B edge<br/>src + outbound + external] --> ID{Authoritative Site + MAC + Device?}
    ID -->|no| NOID[No positive Device service fact]
    ID -->|yes| SRC[Exact NI-01 source evidence]
    SRC --> EV{Evidence valid and retained?}
    EV -->|no / expired / unavailable| LIMITED[limited / unavailable coverage]
    EV -->|yes TLS or QUIC with canonical direct SNI| MATCH[ServiceRecognitionEvaluatorV1<br/>match_direct_sni_v1]
    BUNDLE[Admitted taxonomy v2<br/>manifest v2<br/>ruleset v2] --> MATCH
    MATCH -->|exact active admitted rule| POS[directly_supported Service]
    MATCH -->|no admitted positive| NONE[No supported result]
    POS --> ORG[Organization dimension]
    POS --> CAT[Category dimension]

    DNS[DNS evidence] --> COV[Coverage context]
    DNS -. not a positive V1 service source .-> NONE

    IP[Peer IP alone]:::forbidden
    IP -. forbidden .-> POS
    classDef forbidden fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
```

The current admitted runtime bundle is version 2: 55 active taxonomy services, 41 organizations, 10 categories and 53 active exact-SNI service rules. The research catalog is not itself a production-recognition claim.

## NI-VIS-07 — Background Materialization

```mermaid
flowchart TB
    COMMIT[Committed eligible NI-02B edge] -->|same projection transaction| FEED[(Recognition delivery feed<br/>monotonic feed_seq)]
    FEED -->|max 256| WORK[NI-04 background worker]
    SRC[(NI-01 exact source evidence)] --> WORK
    ART[Immutable admitted artifacts<br/>taxonomy + manifest + ruleset] --> WORK
    WORK --> EVAL[Reusable evaluator]
    EVAL -->|confirmed positive| MOBS[Materialized observation]
    EVAL -->|safe evaluated no-positive| STATE[Coverage / device state]
    MOBS --> MDB[(network_service_intelligence.sqlite3)]
    STATE --> MDB

    BIND[(Authoritative binding change index<br/>change_seq)] -->|max 128| JOB[Targeted Site + MAC replay job]
    JOB --> WORK
    BACK[Bounded 24h backfill] --> WORK

    MDB --> GEN[Active artifact generation]
    GEN --> READ[MaterializedDeviceServiceReadService]
    READ --> CARD[Device Card]

    CARD -. forbidden query-time matcher / history scan .-> WORK
```

**Compute when evidence arrives → persist confirmed result → read the materialized result.**

## NI-VIS-08 — Data Stores and Ownership

```mermaid
flowchart LR
    subgraph SourceFacts["Authoritative / source facts"]
      NM[(network_metadata.sqlite3<br/>writer: NI-01)]
      NA[(network_attribution.sqlite3<br/>writer: fingerprint-sensor attribution recorder)]
      VR[(visitor_registry.sqlite3<br/>writer: Visitor Registry)]
    end

    subgraph Derived["Derived / rebuildable or materialized"]
      NP[(network_metadata_projection.sqlite3<br/>writer: NI-02B)]
      NS[(network_service_intelligence.sqlite3<br/>writer: NI-04 worker)]
    end

    NM -->|read| NP
    NA -->|read| NP
    VR -->|read| NP
    NP -->|feed / binding changes| NS
    NM -->|exact evidence read| NS

    NP -->|read only| P[Protocol Intelligence]
    NS -->|read only| S[Service Intelligence]
    P --> ADMIN[Admin]
    S --> ADMIN
```

The projection/materialized stores do not replace NI-01 source provenance or existing Registry identity authority.

## NI-VIS-09 — Recognition Evidence and Confidence Semantics

```mermaid
stateDiagram-v2
    [*] --> Evaluate
    Evaluate --> Positive: authoritative identity + admitted direct evidence + exact active rule
    Evaluate --> NoSupportedResult: safely evaluated, no admitted positive
    Evaluate --> PendingAttribution: Device authority incomplete
    Evaluate --> SourceInsufficient: source coverage incomplete / stale / expired
    Evaluate --> RecognitionLimited: artifact/evidence limitation
    Evaluate --> MaterializationLagging: worker behind / backfilling
    Evaluate --> Unavailable: required read/storage unavailable
    Evaluate --> Conflict: lineage / identity contradiction

    Positive --> ProductSafeSummary
    NoSupportedResult --> QualifiedEmpty
    PendingAttribution --> QualifiedUnknown
    SourceInsufficient --> QualifiedUnknown
    RecognitionLimited --> QualifiedUnknown
    MaterializationLagging --> QualifiedStoredFacts
    Unavailable --> QualifiedUnknown
    Conflict --> FailClosed
```

No supported service result is **not** proof that the Device had no Internet/network activity. Missing, stale, pending, insufficient and unavailable are not zero.

## NI-VIS-10 — Service / Organization / Category

```mermaid
flowchart TB
    S1[Service: YouTube] --> O1[Organization: Google]
    S1 --> C1[Category: Video Streaming]

    S2[Service: Gmail] --> O1
    S2 --> C2[Category: Productivity & Collaboration]

    S3[Service: WhatsApp] --> O2[Organization: Meta]
    S3 --> C3[Category: Messaging]

    S4[Service: Instagram] --> O2
    S4 --> C4[Category: Social]

    IP[Arbitrary remote IP]:::forbidden
    IP -. does not define .-> O1
    IP -. does not define .-> S1
    classDef forbidden fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
```

Service, Organization and Category are distinct taxonomy dimensions. Organization Context groups already recognized recent services; it does not independently infer an organization from a remote IP.

## NI-VIS-11 — Device Card User Experience

```mermaid
flowchart LR
    API[One Service Intelligence response<br/>materialized V3 in serve mode] --> REC[Recent Services<br/>60 min<br/>max 12]
    API --> ORG[Organizations<br/>derived from same Recent Services<br/>no second request]
    API --> CAT[Service Categories<br/>max 10]
    API --> LAST[Last Service Observation<br/>24 h]
    API --> Q[Freshness / Coverage / Materialization]

    REC --> CARD[Device Card]
    ORG --> CARD
    CAT --> CARD
    LAST --> CARD
    Q --> CARD

    PAPI[Separate Protocol Intelligence response] --> PROTO[Recent Protocols 60 min<br/>Last Protocol 24 h]
    PROTO --> CARD

    RAW[Raw DNS / SNI / peer IP history]:::forbidden
    RAW -. not exposed .-> CARD
    classDef forbidden fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
```

NI-05 Organization Context uses only confirmed entries already present in the bounded 60-minute Recent Services result. It does not query another database or create another network request.

## NI-VIS-12 — Read Path and Performance Boundary

```mermaid
flowchart TB
    subgraph Background["Background / heavy work"]
      FEED[NI-02B committed feed] --> W[NI-04 worker]
      NI01[(NI-01 source evidence)] --> W
      MATCH[Recognition evaluator] --> W
      W --> MAT[(Materialized NI-04 SQLite)]
    end

    subgraph Request["Admin request path"]
      OPEN[Open Device Card] --> AUTH[Admin auth + Site/Device gateway]
      AUTH --> READ[Materialized bounded read]
      MAT --> READ
      READ --> DTO[Product-safe DTO]
      DTO --> UI[Render]
    end

    OPEN -. forbidden .-> SCAN[NI-02B 24h bulk scan]
    OPEN -. forbidden .-> RAW[NI-01 batch reread]
    OPEN -. forbidden .-> REMATCH[Recognition / backfill]
    classDef forbidden fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    class SCAN,RAW,REMATCH forbidden;
```

Serve mode opens only the NI-04 materialized SQLite after existing Admin authorization. Raising request-time deadlines is not the architecture.

## NI-VIS-13 — Process / Service Map

```mermaid
flowchart TB
    CP[captive-portal.service<br/>run.py / Admin reads]
    FS[fingerprint-sensor.service<br/>raw sensor + NI-02A DHCP authority]
    SU[fingerprint-suricata.service<br/>Suricata AF_PACKET]
    N1[network-metadata.service<br/>NI-01 ingestion]
    N2[network-metadata-projection.service<br/>NI-02B projection]
    N4[network-service-recognition.service<br/>NI-04 materializer]

    FS -->|ordering only| SU
    SU -->|DTI EVE source| N1
    N1 -->|ordered upstream| N2
    FS -->|attribution DB| N2
    CP -->|Registry / Admin context| N2
    N2 -->|ordered upstream| N4

    N2 -->|read-only NI-03| CP
    N4 -->|materialized DB read| CP

    NOTE[Independent auxiliary processes<br/>not threads inside Flask] --> N1
    NOTE --> N2
    NOTE --> N4
```

The production services are independently supervised. Their absence or lag must not become a hard dependency of guest authorization.

## NI-VIS-14 — Failure Isolation and Recovery

```mermaid
flowchart TD
    FAIL{Failure}
    FAIL --> S[Suricata unavailable]
    FAIL --> L[NI-01 lag / source backlog]
    FAIL --> A[Attribution insufficient]
    FAIL --> M[NI-04 materializer lag]
    FAIL --> R[Recognition artifact unavailable]
    FAIL --> D[Admin read deadline]

    S --> SU[source unavailable / no fabricated absence]
    L --> LU[downstream freshness degrades]
    A --> AU[pending / unattributed / unavailable<br/>no positive Device service]
    M --> MU[retain confirmed facts<br/>qualify materialization coverage]
    R --> RU[recognition unavailable<br/>no new positives]
    D --> DU[request unavailable / fail-soft UI]

    AUTH[Omada guest authorization / CAPPORT] --> OK[continues independently]
    S -. no failure authority .-> AUTH
    L -. no failure authority .-> AUTH
    A -. no failure authority .-> AUTH
    M -. no failure authority .-> AUTH
    R -. no failure authority .-> AUTH
```

## NI-VIS-15 — Privacy / Security / Retention Boundary

```mermaid
flowchart LR
    MIRROR[Mirrored packets<br/>ephemeral capture] --> SUR[Suricata]
    SUR --> META[DNS / SNI / endpoint metadata<br/>privacy-sensitive internal evidence]
    META --> NI01[(NI-01 source store)]
    NI01 --> EVAL[Attribution + recognition]
    EVAL --> POS[Confirmed service ID + org + category + lineage]
    POS --> NI04[(NI-04 materialized store<br/>positive observations up to 14d)]
    NI04 --> SAFE[Product-safe bounded summary]
    SAFE --> POLICY[Admin auth + Site/Device authorization]
    POLICY --> CARD[Device Card]

    PAYLOAD[Full PCAP / body / credentials / cookies]:::forbidden
    RAWUI[Raw DNS/SNI/IP history in Device Card]:::forbidden
    MIRROR -. no durable product history .-> PAYLOAD
    META -. no public exposure .-> RAWUI
    classDef forbidden fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
```

Metadata minimization does not make DNS/SNI/remote endpoint metadata non-sensitive. Product presentation exposes bounded semantic summaries, not raw history.

## NI-VIS-16 — Functional Closure / Roadmap

```mermaid
flowchart LR
    N0[NI-00<br/>Capture Research<br/>Completed] --> N1[NI-01<br/>Metadata Ingestion<br/>Production]
    N1 --> N2[NI-02 / 02B<br/>Attribution + Projection<br/>Production]
    N2 --> N3[NI-03<br/>Protocol Intelligence<br/>Production]
    N3 --> N4[NI-04<br/>Service Recognition + Materialization<br/>Production]
    N4 --> N5[NI-05<br/>Organization Context<br/>Production]
    N5 --> CLOSE[NETWORK INTELLIGENCE V1<br/>FUNCTIONALLY COMPLETE<br/>PRODUCTION DEPLOYED / CLOSED]

    N5 -. owner decision .-> N6[NI-06 Transport Health<br/>CANCELLED]
    CLOSE --> PERF[Separate Performance & Optimization program<br/>I/O / queues / SQLite / NI-01 latency]
```

NI-06 is **Cancelled**, not Pending or HOLD. Performance optimization is a separate workstream and does not reopen Network Intelligence V1 functional scope.

## Production closure snapshot

| Stage | Current disposition |
|---|---|
| NI-00 | Completed |
| NI-01 | Production |
| NI-02 / NI-02B | Production |
| NI-03 | Production |
| NI-04 | Production |
| NI-05 | Production |
| NI-06 | **CANCELLED BY OWNER** |
| Network Intelligence V1 | **FUNCTIONALLY COMPLETE / PRODUCTION DEPLOYED / CLOSED** |

## Known Performance Work / Not a NI V1 Functional Blocker

A dated investigation on 2026-10-14 observed NI-01 ingestion lag of roughly 8–9 minutes while the storage subsystem was under pressure and SQLite physical reads were blocking. That observation is **not** a permanent SLA and is **not** proof of the current instantaneous lag. Read amplification remains a separate optimization hypothesis to verify. Functional closure does not claim that I/O optimization is complete, does not prescribe SSD as an architectural substitute, and does not weaken SQLite durability guarantees.
