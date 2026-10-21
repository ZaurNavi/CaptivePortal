# TECHLEAD22 — NI-04 Unified55: source evidence and bounded admission verdict R7

Date: 2026-10-12. Owner's total target: 55 real detections. This review is **TechLead-owned**; Coder gets no investigation, source-comparison, semantic decision, packet capture or proof tasks.

## Findings and exact disposition

| Group | Count | Decision |
|---|---:|---|
| Original Lane A | 5 | Existing verified v1 exact-SNI rules; old artifacts unchanged. |
| Additional exact first-party web/service-host **proposals** | 48 | Specific hosts and first-party locators frozen in `TECHLEAD-55-HOST-DECISIONS.json`. Suitable for deterministic implementation subject to normal new-version code acceptance; no native-app/transactions/playback assertions. |
| Messenger | 1 | **NOT ADMITTED**. Standalone `messenger.com` web messaging was retired in April 2026. Active replacement `facebook.com/messages` uses shared Facebook SNI, while HTTP path is encrypted. First-party unique direct-SNI proof absent. |
| Viber | 1 | **NOT ADMITTED**. The official domain `www.viber.com` is a product/download website, not evidence of private Viber messages; `chatapi.viber.com` documents bots, not consumer clients. Official Viber developer documentation describes proprietary TCP transport for client communication; no qualifying uniquely attributable TLS/QUIC SNI is evidenced. |
| Total | **55** | **55 identities in taxonomy, 53 supported exact-SNI rule candidates; 55/55 RELEASE ADMISSION = HOLD.** |

## Provenance and priority of facts

- Existing 41/50 first-party web identity findings are taken **as research** from the attached October 12 TOP50 Research R2 and Architect semantic decision R2. That decision accepted 40 service web-host/taxonomy semantics (including the original five), 1 ChatGPT category repair, and held 9; it **did not** admit all as runtime rules.
- The remaining five user-added names are exact first-party web hosts: Gmail `mail.google.com`, Maps `maps.google.com`, Translate `translate.google.com`, Outlook.com `outlook.live.com`, Booking.com `www.booking.com`. Only direct web-host connections are claimed.
- New firsthand checks on October 12: OpenAI identifies `chatgpt.com` as web ChatGPT; Microsoft identifies `outlook.live.com` as consumer Outlook.com and `onedrive.live.com` as OneDrive; Signal-owned Desktop `production.json` identifies `chat.signal.org` as production server; Alibaba Group identifies AliExpress `www.aliexpress.com`; Wolt legal ToS treats `wolt.com` as Wolt Service website; Bolt operates `mm-web.bolt.eu` for its micromobility web experience. These do **not** prove mobile usage generally.
- Messenger's April 2026 web shutdown (Meta announcement reported by multiple contemporary outlets) specifically invalidates the old research lead. Source: https://www.facebook.com/help/messenger-app/804132271957789 (first-party Meta Help, login-gated); corroboration: https://techcrunch.com/2026/02/19/meta-is-shutting-down-messengers-standalone-website/ and https://www.elevenforum.com/t/facebook-messenger-com-is-no-longer-available-for-messaging-starting-april-2026.44645/.
- Viber client transport and bot API official source: https://developers.viber.com/docs/all/ ; Viber official download site: https://help.viber.com/hc/en-us/articles/9084593040285-Set-up-Viber-on-your-desktop .
- Signal official client source: https://github.com/signalapp/Signal-Desktop/blob/main/config/production.json and Android app https://github.com/signalapp/Signal-Android/blob/main/app/build.gradle.kts .
- First-party platform/legal updates: https://explore.wolt.com/en/aze/terms ; https://mm-web.bolt.eu/ ; https://home.alibabagroup.com/en-US/ile-1643422862263975936 ; https://support.microsoft.com/en-us/outlook/getstarted/what-version-of-outlook-do-i-have?so=1 ; https://help.openai.com/en/articles/12677804-what-is-chatgpt-faq .

## What Tech Lead checked (and did not check)

**Performed:** mechanically reconciled all 55 exact Registry55 IDs, selected distinct first-party web-host candidates, fixed ChatGPT category, checked same-org SNI collisions, retained v1 semantic rules, built 55-row frozen source matrix and version-2 canonical source/ruleset/taxonomy, recalculated raw and semantic SHA-256, checked 330 preassigned synthetic TLS/QUIC/DNS/near-host/CDN/sibling expectations through an independent local oracle. The **safe candidate** has 53 active rules. No live visitor traffic, production load, production service, GitHub branch or production DB were touched.

**Not performed / NOT equivalent to PASS:** 55 independent real mobile-client traces; authenticated or decrypting HTTPS path for Messenger; extraction of proprietary Viber TCP protocol client identity; application-source code integration tests; real production observations. Offline vectors prove deterministic matching, **not** that client traffic exposes the SNI. First-party direct domain does not prove messages sent, videos played, paid orders or rides.

## Only Tech Lead owns next proof decision

To support genuine Messenger recognition, identify and verify a **unique visible service-specific endpoint** used by the Messenger client without colliding with Facebook OR issue an explicitly approved safe new evidence source contract. Current V1 SNI alone does not show `/messages` path. To support genuine consumer Viber messaging, verify a distinct exposed first-party endpoint via a TechLead-controlled, consented lab capture OR issue an architecture-contract extension for another trustworthy signal. Neither task belongs to Coder. Do not authorize `service.messenger` or `service.viber` merely because a generic Meta/Viber website is reachable.

## Scope authority

Original architecture/R1 and original five v1 immutable artifacts remain binding. TechLead's frozen 53-rule v2 candidate is **implementation input, not 55-rule release admission**. Independent Lab/production gates are separate. No right to mislabel research as proven runtime classification, no Coder research and no bypass of Owner's single combined-deploy requirement.
