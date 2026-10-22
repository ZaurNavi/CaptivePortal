# To: CaptivPortal Architect
## TASK-DTI-NI-04K — Independent Semantic Admission Review Request

**Status:** RESEARCH CANDIDATE / NOT ADMITTED

Review the exact three immutable candidate artifacts and `EVIDENCE-PACK-v1.md` against original `TASK-DTI-NI-04-ARCHITECTURE-CONTRACT-v1.md` and normative `v1-R1` SHA-256 `788879cec606f88b13bcf3a759dc19dd68eebe426e5584a727a4e6aa66d1a17e`.

**Requested decision (one per rule, then whole bundle):** `PASS`, `REPAIR`, or `REJECT`, with explicit grounding in published first-party claim/source and V1 taxonomy/hostname semantics. This is not a request to write code.

### Exact candidate identity

| Artifact | Version | Semantic SHA256 (digest field excluded) |
|---|---:|---|
| Taxonomy `captivportal.network-intelligence.recognition-taxonomy` | 1 | `7e122a828c0877d4fb61382646604a2b4a8421a40c4388e513460c84c69c8278` |
| Manifest `captivportal.network-intelligence.recognition-knowledge` | 1 | `7ecca6dc42ef73c2dd4b40e4d56d4115078f548cd3693e510f095968be1f0210` |
| Ruleset `captivportal.network-intelligence.service-recognition` | 1 | `46d9485b6aea5c6a0b40a4b9a969eed553a4353904a1667fe85cb0620c02a56a` |

### Specific review questions

1. Is exact `www.youtube.com` independently Service-specific enough for `service.youtube` under SNI, distinct from other Google brands? Are `org.google` and `category.video_streaming` appropriate?
2. Is exact `web.whatsapp.com` independently Service-specific for WhatsApp, with `org.meta` as primary Organization (NOT Instagram/Facebook)? Is the Meta source/current source provenance sufficient?
3. Is exact `web.telegram.org` still clearly attributable to the Telegram Service based on official current Telegram Web + apps sources?
4. Is exact `open.spotify.com` uniquely the Spotify Service, not merely generic hosting? Does `category.audio_streaming` match the intended primary taxonomy?
5. Is exact `www.netflix.com` uniquely the Netflix Service; is `category.video_streaming` justified?
6. Are the deliberately omitted domains/suffixes a correct narrow V1 decision rather than unjustified false-negative repair?
7. Are the positive/negative synthetic fixtures adequate for knowledge admission (not NI-04A integration), and are any missing near-match, shared-host, same-organization or ambiguity fixtures mandatory?
8. Does source provenance require immutable webpage snapshots or an Owner-controlled trace before independent factual admission? If yes, return a precise repair—not an implied Coder decision.
9. Are the 90-day expiry metadata and exact organization naming adequate?
10. Does the candidate preserve all original v1 + R1 inherited constraints, including zero active DNS-connected rules and absence of any numeric IP-only rule?

### Governance outcomes

- `PASS` means **Architect semantic review only**. Tech Lead independent factual/integrity verification and explicit Owner acceptance of these exact IDs/versions/digests are still separate.
- `REPAIR`/`REJECT` means Coder stays HOLD and a new candidate bundle identity must be generated, with updated versions/digests when any admitted artifact semantics change.
- No implementation, Git, systemd, network, production or client-data actions are authorized by this request.
