# TASK-DTI-NI-04K — TOP-50 Service Recognition Research Dossier R2

**Project:** CaptivPortal  
**Date:** 2026-10-12 (Asia/Baku)  
**Audience:** Architect — independent semantic admission / bounded decision  
**Research baseline:** Priority TOP-50 v1, Architect review R1 of five-service candidate v1, NI-04 Architecture v1 + R1  
**Repository:** observed `main@22cdde5d4168de02d142c840028a4d66167e47f7` (no new live repo check performed for this dossier)  
**Authority:** research only; NO Coder / production / network / Git changes

## 1. Executive result

All **50/50** priorities have been assessed at **public, first-party web-identity evidence** level. **D=23** explicit first-party documentary hostname mentions, **S=18** first-party inspected web-site identities, **H=9** insufficient evidence for a positive exact-SNI rule in this review. These are *evidence classes*, not semantic admission decisions. 41 domain propositions are ready for Architect review only, 9 remain Research HOLD.

**CRITICAL:** 50 evaluated service entries ≠ 50 admitted rules ≠ 50 proven mobile apps ≠ 50 measured traffic classes. There is no operational NI-04 matcher and no authenticated production SNI evidence test here. Never auto-import this dossier as a runtime ruleset.

Priority numbers came from a guest-Wi-Fi research queue tailored to AZ and are not actual top-50 traffic measurements. All 50 positions are preserved verbatim from the existing priority catalog.

## 2. Evidence grade rubric

- **D:** Publisher directly names the exact hostname in support, official newsroom, or related primary instruction. This is a stronger web-host specificity lead; still needs Architect individual approval of category, identity, ambiguity, per-rule negative fixtures.
- **S:** First-party branded web service retrieved (or inspected directly) with the proposed hostname. This establishes a first-party site identity, **not** independent evidence of full native-app coverage, and is weaker than D.
- **H:** Marketing site only, multi-service collision, inaccessible first-party host or insufficient precise hostname evidence. **No active rule from H.**

**Every hostname is an exact-match *proposal*.** Unverified wildcard/suffix patterns, DNS→IP correlation, ASN/CDN/IP-only rules and classifier guesses forbidden. `other_supported` entries are category *proposals* only, requiring Architect decision under the closed V1 taxonomy.

## 3. Full 50-service evidence/decision matrix

| # | Service | Primary Organization (candidate) | V1 Category (candidate) | Exact web SNI proposal | Evidence | Decision | First-party source |
|---:|---|---|---|---|:---:|---|---|
| 1 | YouTube | Google | `category.video_streaming` | `www.youtube.com` | D | Review | [publisher](https://support.google.com/youtube/answer/171780) |
| 2 | TikTok | TikTok | `category.social` | `www.tiktok.com` | D | Review | [publisher](https://newsroom.tiktok.com/tiktok-tutorial-series-expanding-web-experience?lang=en) |
| 3 | WhatsApp | Meta | `category.messaging` | `web.whatsapp.com` | D | Review | [publisher](https://faq.whatsapp.com/668538004658079/?cms_platform=windows-desktop&locale=ja_JP) |
| 4 | Instagram | Meta | `category.social` | `www.instagram.com` | H | **HOLD** | [publisher](https://about.fb.com/news/2025/12/ai-breakthroughs-advanced-ai-glasses-meta-2025-highlights/) |
| 5 | Telegram | Telegram | `category.messaging` | `web.telegram.org` | D | Review | [publisher](https://bugs.telegram.org/c/4002) |
| 6 | Facebook | Meta | `category.social` | `www.facebook.com` | S | Review | [publisher](https://www.facebook.com/) |
| 7 | ChatGPT | OpenAI | `category.productivity_collaboration` | `chatgpt.com` | D | Review | [publisher](https://help.openai.com/en/articles/12677804-what-is-chatgpt-faq) |
| 8 | Spotify | Spotify | `category.audio_streaming` | `open.spotify.com` | D | Review | [publisher](https://support.spotify.com/gd/article/web-player-help/) |
| 9 | Netflix | Netflix | `category.video_streaming` | `www.netflix.com` | D | Review | [publisher](https://help.netflix.com/en/node/133134) |
| 10 | Pinterest | Pinterest | `category.social` | `pinterest.com` | D | Review | [publisher](https://help.pinterest.com/ru/article/log-in-and-out-of-pinterest) |
| 11 | Roblox | Roblox | `category.gaming` | `www.roblox.com` | S | Review | [publisher](https://www.roblox.com/) |
| 12 | Snapchat | Snap | `category.social` | `web.snapchat.com` | D | Review | [publisher](https://help.snapchat.com/hc/en-us/articles/8133227022484-How-do-I-get-Snapchat-for-Web) |
| 13 | Facebook Messenger | Meta | `category.messaging` | `messenger.com` | D | Review | [publisher](https://www.facebook.com/help/messenger-app/1256202571735558/) |
| 14 | Discord | Discord | `category.messaging` | `discord.com` | D | Review | [publisher](https://support.discord.com/hc/en-us/articles/360057027354-How-to-Log-In-to-your-Discord-Account) |
| 15 | Twitch | Twitch | `category.video_streaming` | `www.twitch.tv` | S | Review | [publisher](https://www.twitch.tv/) |
| 16 | X | X | `category.social` | `x.com` | H | **HOLD** | [publisher](https://help.x.com/en/managing-your-account/log-in-issues) |
| 17 | Google Drive | Google | `category.cloud_storage` | `drive.google.com` | D | Review | [publisher](https://support.google.com/drive/answer/2424384?hl=en) |
| 18 | Microsoft Teams | Microsoft | `category.productivity_collaboration` | `teams.microsoft.com` | D | Review | [publisher](https://support.microsoft.com/en-us/teams/meetings/use-microsoft-teams-on-the-web) |
| 19 | Zoom | Zoom | `category.productivity_collaboration` | `join.zoom.us` | D | Review | [publisher](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060732) |
| 20 | LinkedIn | LinkedIn | `category.social` | `www.linkedin.com` | D | Review | [publisher](https://www.linkedin.com/help/linkedin/answer/a522734) |
| 21 | Threads | Meta | `category.social` | `threads.com` | D | Review | [publisher](https://about.fb.com/news/2025/04/new-features-threads-web-experience/) |
| 22 | Reddit | Reddit | `category.social` | `www.reddit.com` | S | Review | [publisher](https://www.reddit.com/) |
| 23 | VK | VK | `category.social` | `vk.com` | H | **HOLD** | [publisher](https://vk.com/) |
| 24 | Signal | Signal | `category.messaging` | **NONE** | H | **HOLD** | [publisher](https://signal.org/download/) |
| 25 | Viber | Rakuten Viber | `category.messaging` | **NONE** | H | **HOLD** | [publisher](https://help.viber.com/hc/en-us/articles/9210039148189-Supported-platforms) |
| 26 | Microsoft OneDrive | Microsoft | `category.cloud_storage` | **NONE** | H | **HOLD** | [publisher](https://support.microsoft.com/en-us/excel/using-office-for-the-web-in-onedrive) |
| 27 | Dropbox | Dropbox | `category.cloud_storage` | `www.dropbox.com` | D | Review | [publisher](https://help.dropbox.com/security/official-domains) |
| 28 | Google Meet | Google | `category.productivity_collaboration` | `meet.google.com` | D | Review | [publisher](https://support.google.com/meet/answer/9303069?hl=en) |
| 29 | Google Docs | Google | `category.productivity_collaboration` | `docs.google.com` | D | Review | [publisher](https://support.google.com/docs/answer/7068618?hl=en) |
| 30 | Google Gemini | Google | `category.other_supported` | `gemini.google.com` | D | Review | [publisher](https://support.google.com/gemini/answer/13278668?hl=ru) |
| 31 | Claude | Anthropic | `category.other_supported` | `claude.ai` | S | Review | [publisher](https://claude.ai/) |
| 32 | DeepSeek | DeepSeek | `category.other_supported` | `chat.deepseek.com` | D | Review | [publisher](https://deepseek.com/en/news/v4-preview/) |
| 33 | Apple Music | Apple | `category.audio_streaming` | `music.apple.com` | S | Review | [publisher](https://music.apple.com/) |
| 34 | SoundCloud | SoundCloud | `category.audio_streaming` | `soundcloud.com` | S | Review | [publisher](https://soundcloud.com/) |
| 35 | YouTube Music | Google | `category.audio_streaming` | `music.youtube.com` | D | Review | [publisher](https://support.google.com/youtubemusic/answer/9231765?hl=en-gb) |
| 36 | Prime Video | Amazon | `category.video_streaming` | `www.primevideo.com` | S | Review | [publisher](https://www.primevideo.com/) |
| 37 | Disney+ | Disney | `category.video_streaming` | `www.disneyplus.com` | S | Review | [publisher](https://www.disneyplus.com/) |
| 38 | Steam | Valve | `category.software_distribution` | `store.steampowered.com` | S | Review | [publisher](https://store.steampowered.com/) |
| 39 | Epic Games Store | Epic Games | `category.software_distribution` | `store.epicgames.com` | S | Review | [publisher](https://store.epicgames.com/) |
| 40 | Birmarket | Birmarket | `category.other_supported` | `birmarket.az` | S | Review | [publisher](https://birmarket.az/) |
| 41 | Tap.az | Tap.az | `category.other_supported` | `tap.az` | S | Review | [publisher](https://tap.az/) |
| 42 | Turbo.az | Turbo.az | `category.other_supported` | `turbo.az` | S | Review | [publisher](https://turbo.az/) |
| 43 | Lalafo.az | Lalafo | `category.other_supported` | `lalafo.az` | S | Review | [publisher](https://lalafo.az/) |
| 44 | Oxu.az | Oxu.az | `category.other_supported` | `oxu.az` | S | Review | [publisher](https://oxu.az/) |
| 45 | Yandex Search | Yandex | `category.web_search` | `yandex.com` | D | Review | [publisher](https://yandex.com/support/common/ru/browsers-settings/yandex-searches) |
| 46 | Temu | Temu | `category.other_supported` | `www.temu.com` | S | Review | [publisher](https://www.temu.com/) |
| 47 | Trendyol | Trendyol | `category.other_supported` | `www.trendyol.com` | S | Review | [publisher](https://www.trendyol.com/) |
| 48 | AliExpress | AliExpress | `category.other_supported` | **NONE** | H | **HOLD** | [publisher](https://www.aliexpress.com/) |
| 49 | Bolt | Bolt | `category.other_supported` | **NONE** | H | **HOLD** | [publisher](https://bolt.eu/en-az/legal/rides/tnc-platform-ride-hailing/) |
| 50 | Wolt | Wolt | `category.other_supported` | **NONE** | H | **HOLD** | [publisher](https://wolt.com/) |

## 4. Individual evidence and negative reasoning — 50 dossiers

### 01. YouTube
- **Proposition:** `service.youtube`; primary Organization **Google**; proposed `category.video_streaming`.
- **Exact SNI:** `www.youtube.com`.
- **First-party evidence:** [https://support.google.com/youtube/answer/171780](https://support.google.com/youtube/answer/171780); grade **D**; claim: YouTube Help directly documents this player host.
- **Mandatory false-positive caution / next negative:** Same-org negative music.youtube.com; web host not playback volume.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 02. TikTok
- **Proposition:** `service.tiktok`; primary Organization **TikTok**; proposed `category.social`.
- **Exact SNI:** `www.tiktok.com`.
- **First-party evidence:** [https://newsroom.tiktok.com/tiktok-tutorial-series-expanding-web-experience?lang=en](https://newsroom.tiktok.com/tiktok-tutorial-series-expanding-web-experience?lang=en); grade **D**; claim: TikTok newsroom explicitly directs web users to www.tiktok.com.
- **Mandatory false-positive caution / next negative:** Category social vs video_streaming Architect choice; not native media CDN.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 03. WhatsApp
- **Proposition:** `service.whatsapp`; primary Organization **Meta**; proposed `category.messaging`.
- **Exact SNI:** `web.whatsapp.com`.
- **First-party evidence:** [https://faq.whatsapp.com/668538004658079/?cms_platform=windows-desktop&locale=ja_JP](https://faq.whatsapp.com/668538004658079/?cms_platform=windows-desktop&locale=ja_JP); grade **D**; claim: WhatsApp Help instructs browser users to web.whatsapp.com.
- **Mandatory false-positive caution / next negative:** WhatsApp mobile traffic / calls not inferred.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 04. Instagram
- **Proposition:** `service.instagram`; primary Organization **Meta**; proposed `category.social`.
- **Exact SNI:** `www.instagram.com`.
- **First-party evidence:** [https://about.fb.com/news/2025/12/ai-breakthroughs-advanced-ai-glasses-meta-2025-highlights/](https://about.fb.com/news/2025/12/ai-breakthroughs-advanced-ai-glasses-meta-2025-highlights/); grade **H**; claim: Meta acknowledges Instagram as distinct service; hostname-specific source not independently obtained.
- **Mandatory false-positive caution / next negative:** URL access 429; require first-party hostname-specific proof.
- **Decision for Architect:** **RESEARCH_HOLD**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 05. Telegram
- **Proposition:** `service.telegram`; primary Organization **Telegram**; proposed `category.messaging`.
- **Exact SNI:** `web.telegram.org`.
- **First-party evidence:** [https://bugs.telegram.org/c/4002](https://bugs.telegram.org/c/4002); grade **D**; claim: Telegram's official WebA/WebK paths share web.telegram.org.
- **Mandatory false-positive caution / next negative:** Native MTProto traffic not inferable from web.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 06. Facebook
- **Proposition:** `service.facebook`; primary Organization **Meta**; proposed `category.social`.
- **Exact SNI:** `www.facebook.com`.
- **First-party evidence:** [https://www.facebook.com/](https://www.facebook.com/); grade **S**; claim: Official service login site inspected.
- **Mandatory false-positive caution / next negative:** Messenger and Instagram negative; login does not prove social activity.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 07. ChatGPT
- **Proposition:** `service.chatgpt`; primary Organization **OpenAI**; proposed `category.productivity_collaboration`.
- **Exact SNI:** `chatgpt.com`.
- **First-party evidence:** [https://help.openai.com/en/articles/12677804-what-is-chatgpt-faq](https://help.openai.com/en/articles/12677804-what-is-chatgpt-faq); grade **D**; claim: OpenAI FAQ explicitly names chatgpt.com as ChatGPT web app.
- **Mandatory false-positive caution / next negative:** API platform and unrelated OpenAI domains excluded.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 08. Spotify
- **Proposition:** `service.spotify`; primary Organization **Spotify**; proposed `category.audio_streaming`.
- **Exact SNI:** `open.spotify.com`.
- **First-party evidence:** [https://support.spotify.com/gd/article/web-player-help/](https://support.spotify.com/gd/article/web-player-help/); grade **D**; claim: Spotify support explicitly names open.spotify.com web player.
- **Mandatory false-positive caution / next negative:** No assertion that audio bytes used this host.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 09. Netflix
- **Proposition:** `service.netflix`; primary Organization **Netflix**; proposed `category.video_streaming`.
- **Exact SNI:** `www.netflix.com`.
- **First-party evidence:** [https://help.netflix.com/en/node/133134](https://help.netflix.com/en/node/133134); grade **D**; claim: Netflix directs browser users to www.netflix.com.
- **Mandatory false-positive caution / next negative:** CDN/media hostnames distinct.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 10. Pinterest
- **Proposition:** `service.pinterest`; primary Organization **Pinterest**; proposed `category.social`.
- **Exact SNI:** `pinterest.com`.
- **First-party evidence:** [https://help.pinterest.com/ru/article/log-in-and-out-of-pinterest](https://help.pinterest.com/ru/article/log-in-and-out-of-pinterest); grade **D**; claim: Pinterest Help names pinterest.com/login web access.
- **Mandatory false-positive caution / next negative:** Marketing and pin-CDNs excluded.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 11. Roblox
- **Proposition:** `service.roblox`; primary Organization **Roblox**; proposed `category.gaming`.
- **Exact SNI:** `www.roblox.com`.
- **First-party evidence:** [https://www.roblox.com/](https://www.roblox.com/); grade **S**; claim: Roblox first-party web login/game portal inspected.
- **Mandatory false-positive caution / next negative:** Game servers, games and platform sessions are not proven.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 12. Snapchat
- **Proposition:** `service.snapchat`; primary Organization **Snap**; proposed `category.social`.
- **Exact SNI:** `web.snapchat.com`.
- **First-party evidence:** [https://help.snapchat.com/hc/en-us/articles/8133227022484-How-do-I-get-Snapchat-for-Web](https://help.snapchat.com/hc/en-us/articles/8133227022484-How-do-I-get-Snapchat-for-Web); grade **D**; claim: Snapchat Help explicitly names web.snapchat.com.
- **Mandatory false-positive caution / next negative:** Currently redirects to www.snapchat.com/web; runtime SNI only if actually observed.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 13. Facebook Messenger
- **Proposition:** `service.messenger`; primary Organization **Meta**; proposed `category.messaging`.
- **Exact SNI:** `messenger.com`.
- **First-party evidence:** [https://www.facebook.com/help/messenger-app/1256202571735558/](https://www.facebook.com/help/messenger-app/1256202571735558/); grade **D**; claim: Messenger Help explicitly instructs opening messenger.com.
- **Mandatory false-positive caution / next negative:** Facebook messages also exist on facebook.com; no all-Messenger-traffic claim.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 14. Discord
- **Proposition:** `service.discord`; primary Organization **Discord**; proposed `category.messaging`.
- **Exact SNI:** `discord.com`.
- **First-party evidence:** [https://support.discord.com/hc/en-us/articles/360057027354-How-to-Log-In-to-your-Discord-Account](https://support.discord.com/hc/en-us/articles/360057027354-How-to-Log-In-to-your-Discord-Account); grade **D**; claim: Discord official help names discord.com/login.
- **Mandatory false-positive caution / next negative:** Does not prove calls/voice app network flow.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 15. Twitch
- **Proposition:** `service.twitch`; primary Organization **Twitch**; proposed `category.video_streaming`.
- **Exact SNI:** `www.twitch.tv`.
- **First-party evidence:** [https://www.twitch.tv/](https://www.twitch.tv/); grade **S**; claim: Twitch first-party web portal inspected; Help also documents twitch.tv.
- **Mandatory false-positive caution / next negative:** Exact www host not explicitly required by browser-help; CDN video separate.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 16. X
- **Proposition:** `service.x`; primary Organization **X**; proposed `category.social`.
- **Exact SNI:** `x.com`.
- **First-party evidence:** [https://help.x.com/en/managing-your-account/log-in-issues](https://help.x.com/en/managing-your-account/log-in-issues); grade **H**; claim: X help confirms X product; homepage fetch blocked.
- **Mandatory false-positive caution / next negative:** Requires first-party exact x.com web hostname proof for active admission.
- **Decision for Architect:** **RESEARCH_HOLD**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 17. Google Drive
- **Proposition:** `service.google_drive`; primary Organization **Google**; proposed `category.cloud_storage`.
- **Exact SNI:** `drive.google.com`.
- **First-party evidence:** [https://support.google.com/drive/answer/2424384?hl=en](https://support.google.com/drive/answer/2424384?hl=en); grade **D**; claim: Google Drive Help directs users to drive.google.com.
- **Mandatory false-positive caution / next negative:** Drive vs Google Docs/Meet/Google auth sibling negatives.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 18. Microsoft Teams
- **Proposition:** `service.teams`; primary Organization **Microsoft**; proposed `category.productivity_collaboration`.
- **Exact SNI:** `teams.microsoft.com`.
- **First-party evidence:** [https://support.microsoft.com/en-us/teams/meetings/use-microsoft-teams-on-the-web](https://support.microsoft.com/en-us/teams/meetings/use-microsoft-teams-on-the-web); grade **D**; claim: Microsoft instructs users to teams.microsoft.com.
- **Mandatory false-positive caution / next negative:** Meeting media/microsoft telemetry excluded.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 19. Zoom
- **Proposition:** `service.zoom`; primary Organization **Zoom**; proposed `category.productivity_collaboration`.
- **Exact SNI:** `join.zoom.us`.
- **First-party evidence:** [https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060732](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060732); grade **D**; claim: Zoom support explicitly names join.zoom.us for meeting join.
- **Mandatory false-positive caution / next negative:** Only join portal, not media transfer or full Zoom app.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 20. LinkedIn
- **Proposition:** `service.linkedin`; primary Organization **LinkedIn**; proposed `category.social`.
- **Exact SNI:** `www.linkedin.com`.
- **First-party evidence:** [https://www.linkedin.com/help/linkedin/answer/a522734](https://www.linkedin.com/help/linkedin/answer/a522734); grade **D**; claim: LinkedIn Help names www.linkedin.com web login.
- **Mandatory false-positive caution / next negative:** LinkedIn authentication and ads separate.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 21. Threads
- **Proposition:** `service.threads`; primary Organization **Meta**; proposed `category.social`.
- **Exact SNI:** `threads.com`.
- **First-party evidence:** [https://about.fb.com/news/2025/04/new-features-threads-web-experience/](https://about.fb.com/news/2025/04/new-features-threads-web-experience/); grade **D**; claim: Meta explicitly announces Threads.net to Threads.com migration.
- **Mandatory false-positive caution / next negative:** Do not silently admit old threads.net.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 22. Reddit
- **Proposition:** `service.reddit`; primary Organization **Reddit**; proposed `category.social`.
- **Exact SNI:** `www.reddit.com`.
- **First-party evidence:** [https://www.reddit.com/](https://www.reddit.com/); grade **S**; claim: Official Reddit web homepage inspected.
- **Mandatory false-positive caution / next negative:** Media/CDN and third-party embeds not inferred.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 23. VK
- **Proposition:** `service.vk`; primary Organization **VK**; proposed `category.social`.
- **Exact SNI:** `vk.com`.
- **First-party evidence:** [https://vk.com/](https://vk.com/); grade **H**; claim: Proposed domain but official page could not be independently fetched.
- **Mandatory false-positive caution / next negative:** Need service-specific first-party source and legal operator validation.
- **Decision for Architect:** **RESEARCH_HOLD**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 24. Signal
- **Proposition:** `service.signal`; primary Organization **Signal**; proposed `category.messaging`.
- **Exact SNI:** NONE — no safely admitted proposed hostname in this research round.
- **First-party evidence:** [https://signal.org/download/](https://signal.org/download/); grade **H**; claim: Official site documents apps, not a service-specific SNI for messaging.
- **Mandatory false-positive caution / next negative:** signal.org homepage/download is NOT messaging evidence; native opaque service.
- **Decision for Architect:** **RESEARCH_HOLD**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 25. Viber
- **Proposition:** `service.viber`; primary Organization **Rakuten Viber**; proposed `category.messaging`.
- **Exact SNI:** NONE — no safely admitted proposed hostname in this research round.
- **First-party evidence:** [https://help.viber.com/hc/en-us/articles/9210039148189-Supported-platforms](https://help.viber.com/hc/en-us/articles/9210039148189-Supported-platforms); grade **H**; claim: Viber supports mobile/desktop apps; no admitted web messenger SNI.
- **Mandatory false-positive caution / next negative:** www.viber.com is marketing; do not classify app messaging.
- **Decision for Architect:** **RESEARCH_HOLD**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 26. Microsoft OneDrive
- **Proposition:** `service.onedrive`; primary Organization **Microsoft**; proposed `category.cloud_storage`.
- **Exact SNI:** NONE — no safely admitted proposed hostname in this research round.
- **First-party evidence:** [https://support.microsoft.com/en-us/excel/using-office-for-the-web-in-onedrive](https://support.microsoft.com/en-us/excel/using-office-for-the-web-in-onedrive); grade **H**; claim: Microsoft says OneDrive.com web, but direct onedrive.live.com redirects to Microsoft marketing.
- **Mandatory false-positive caution / next negative:** Web hostname and account ecosystem need exact validation.
- **Decision for Architect:** **RESEARCH_HOLD**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 27. Dropbox
- **Proposition:** `service.dropbox`; primary Organization **Dropbox**; proposed `category.cloud_storage`.
- **Exact SNI:** `www.dropbox.com`.
- **First-party evidence:** [https://help.dropbox.com/security/official-domains](https://help.dropbox.com/security/official-domains); grade **D**; claim: Dropbox says most online use happens on www.dropbox.com.
- **Mandatory false-positive caution / next negative:** Dropbox has multiple documented domains; only this exact host proposed.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 28. Google Meet
- **Proposition:** `service.google_meet`; primary Organization **Google**; proposed `category.productivity_collaboration`.
- **Exact SNI:** `meet.google.com`.
- **First-party evidence:** [https://support.google.com/meet/answer/9303069?hl=en](https://support.google.com/meet/answer/9303069?hl=en); grade **D**; claim: Google Meet Help instructs meet.google.com.
- **Mandatory false-positive caution / next negative:** Video/voice transport domains excluded.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 29. Google Docs
- **Proposition:** `service.google_docs`; primary Organization **Google**; proposed `category.productivity_collaboration`.
- **Exact SNI:** `docs.google.com`.
- **First-party evidence:** [https://support.google.com/docs/answer/7068618?hl=en](https://support.google.com/docs/answer/7068618?hl=en); grade **D**; claim: Google Docs Help instructs docs.google.com.
- **Mandatory false-positive caution / next negative:** Docs and Drive remain distinct services despite shared storage.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 30. Google Gemini
- **Proposition:** `service.gemini`; primary Organization **Google**; proposed `category.other_supported`.
- **Exact SNI:** `gemini.google.com`.
- **First-party evidence:** [https://support.google.com/gemini/answer/13278668?hl=ru](https://support.google.com/gemini/answer/13278668?hl=ru); grade **D**; claim: Google Gemini Help identifies gemini.google.com web app.
- **Mandatory false-positive caution / next negative:** Provisional other_supported category needs Architect admission.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 31. Claude
- **Proposition:** `service.claude`; primary Organization **Anthropic**; proposed `category.other_supported`.
- **Exact SNI:** `claude.ai`.
- **First-party evidence:** [https://claude.ai/](https://claude.ai/); grade **S**; claim: Anthropic-branded Claude web app inspected.
- **Mandatory false-positive caution / next negative:** Other_supported category requires Architect admission; API excluded.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 32. DeepSeek
- **Proposition:** `service.deepseek`; primary Organization **DeepSeek**; proposed `category.other_supported`.
- **Exact SNI:** `chat.deepseek.com`.
- **First-party evidence:** [https://deepseek.com/en/news/v4-preview/](https://deepseek.com/en/news/v4-preview/); grade **D**; claim: DeepSeek first-party news explicitly names chat.deepseek.com.
- **Mandatory false-positive caution / next negative:** AI product taxonomy decision; API excluded.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 33. Apple Music
- **Proposition:** `service.apple_music`; primary Organization **Apple**; proposed `category.audio_streaming`.
- **Exact SNI:** `music.apple.com`.
- **First-party evidence:** [https://music.apple.com/](https://music.apple.com/); grade **S**; claim: First-party Apple Music Web Player inspected.
- **Mandatory false-positive caution / next negative:** Do not extrapolate native Apple Music/CDN media.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 34. SoundCloud
- **Proposition:** `service.soundcloud`; primary Organization **SoundCloud**; proposed `category.audio_streaming`.
- **Exact SNI:** `soundcloud.com`.
- **First-party evidence:** [https://soundcloud.com/](https://soundcloud.com/); grade **S**; claim: SoundCloud site self-identifies as music streaming.
- **Mandatory false-positive caution / next negative:** Domain choice bare vs www redirect confirmed only for landing.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 35. YouTube Music
- **Proposition:** `service.youtube_music`; primary Organization **Google**; proposed `category.audio_streaming`.
- **Exact SNI:** `music.youtube.com`.
- **First-party evidence:** [https://support.google.com/youtubemusic/answer/9231765?hl=en-gb](https://support.google.com/youtubemusic/answer/9231765?hl=en-gb); grade **D**; claim: YouTube Music Help directly names music.youtube.com.
- **Mandatory false-positive caution / next negative:** Mandatory negative for normal YouTube; sibling Google service.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 36. Prime Video
- **Proposition:** `service.prime_video`; primary Organization **Amazon**; proposed `category.video_streaming`.
- **Exact SNI:** `www.primevideo.com`.
- **First-party evidence:** [https://www.primevideo.com/](https://www.primevideo.com/); grade **S**; claim: Prime Video official streaming portal inspected.
- **Mandatory false-positive caution / next negative:** Amazon/AWS/CDN not inferred; region-dependent domains.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 37. Disney+
- **Proposition:** `service.disney_plus`; primary Organization **Disney**; proposed `category.video_streaming`.
- **Exact SNI:** `www.disneyplus.com`.
- **First-party evidence:** [https://www.disneyplus.com/](https://www.disneyplus.com/); grade **S**; claim: Disney+ first-party streaming website inspected.
- **Mandatory false-positive caution / next negative:** Streaming content may be elsewhere; web host only.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 38. Steam
- **Proposition:** `service.steam`; primary Organization **Valve**; proposed `category.software_distribution`.
- **Exact SNI:** `store.steampowered.com`.
- **First-party evidence:** [https://store.steampowered.com/](https://store.steampowered.com/); grade **S**; claim: Steam Store first-party storefront inspected.
- **Mandatory false-positive caution / next negative:** Steam client/games traffic not inferred; category vs gaming Architect choice.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 39. Epic Games Store
- **Proposition:** `service.epic_games_store`; primary Organization **Epic Games**; proposed `category.software_distribution`.
- **Exact SNI:** `store.epicgames.com`.
- **First-party evidence:** [https://store.epicgames.com/](https://store.epicgames.com/); grade **S**; claim: Epic Games Store first-party store portal inspected.
- **Mandatory false-positive caution / next negative:** Fortnite/Unreal/Epic login distinct services.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 40. Birmarket
- **Proposition:** `service.birmarket`; primary Organization **Birmarket**; proposed `category.other_supported`.
- **Exact SNI:** `birmarket.az`.
- **First-party evidence:** [https://birmarket.az/](https://birmarket.az/); grade **S**; claim: Birmarket AZ marketplace official webpage inspected.
- **Mandatory false-positive caution / next negative:** Marketplace taxonomy vs other_supported Architect decision.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 41. Tap.az
- **Proposition:** `service.tap_az`; primary Organization **Tap.az**; proposed `category.other_supported`.
- **Exact SNI:** `tap.az`.
- **First-party evidence:** [https://tap.az/](https://tap.az/); grade **S**; claim: Tap.az classified-listing web service directly inspected.
- **Mandatory false-positive caution / next negative:** Same link family Turbo.az should not be conflated.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 42. Turbo.az
- **Proposition:** `service.turbo_az`; primary Organization **Turbo.az**; proposed `category.other_supported`.
- **Exact SNI:** `turbo.az`.
- **First-party evidence:** [https://turbo.az/](https://turbo.az/); grade **S**; claim: Turbo.az dedicated vehicle marketplace inspected.
- **Mandatory false-positive caution / next negative:** Related Tap.az links do not prove same Service.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 43. Lalafo.az
- **Proposition:** `service.lalafo_az`; primary Organization **Lalafo**; proposed `category.other_supported`.
- **Exact SNI:** `lalafo.az`.
- **First-party evidence:** [https://lalafo.az/](https://lalafo.az/); grade **S**; claim: Lalafo official Azerbaijan marketplace inspected.
- **Mandatory false-positive caution / next negative:** Other_supported category requires Architect decision.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 44. Oxu.az
- **Proposition:** `service.oxu_az`; primary Organization **Oxu.az**; proposed `category.other_supported`.
- **Exact SNI:** `oxu.az`.
- **First-party evidence:** [https://oxu.az/](https://oxu.az/); grade **S**; claim: Oxu.az official Azerbaijan news portal inspected.
- **Mandatory false-positive caution / next negative:** Other_supported category decision and editorial content not inferred.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 45. Yandex Search
- **Proposition:** `service.yandex_search`; primary Organization **Yandex**; proposed `category.web_search`.
- **Exact SNI:** `yandex.com`.
- **First-party evidence:** [https://yandex.com/support/common/ru/browsers-settings/yandex-searches](https://yandex.com/support/common/ru/browsers-settings/yandex-searches); grade **D**; claim: Yandex support documents yandex.com/search/?text=....
- **Mandatory false-positive caution / next negative:** Other Yandex services and region hosts not inferred.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 46. Temu
- **Proposition:** `service.temu`; primary Organization **Temu**; proposed `category.other_supported`.
- **Exact SNI:** `www.temu.com`.
- **First-party evidence:** [https://www.temu.com/](https://www.temu.com/); grade **S**; claim: Official Temu storefront page retrieved.
- **Mandatory false-positive caution / next negative:** Other_supported commerce category decision; payment/CDN separate.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 47. Trendyol
- **Proposition:** `service.trendyol`; primary Organization **Trendyol**; proposed `category.other_supported`.
- **Exact SNI:** `www.trendyol.com`.
- **First-party evidence:** [https://www.trendyol.com/](https://www.trendyol.com/); grade **S**; claim: First-party Trendyol online storefront inspected.
- **Mandatory false-positive caution / next negative:** Marketplace taxonomy decision and region/redirect handling.
- **Decision for Architect:** **ARCHITECT_REVIEW_CANDIDATE**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 48. AliExpress
- **Proposition:** `service.aliexpress`; primary Organization **AliExpress**; proposed `category.other_supported`.
- **Exact SNI:** NONE — no safely admitted proposed hostname in this research round.
- **First-party evidence:** [https://www.aliexpress.com/](https://www.aliexpress.com/); grade **H**; claim: Expected AliExpress portal inaccessible during research.
- **Mandatory false-positive caution / next negative:** No promoted exact hostname without first-party evidence.
- **Decision for Architect:** **RESEARCH_HOLD**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 49. Bolt
- **Proposition:** `service.bolt`; primary Organization **Bolt**; proposed `category.other_supported`.
- **Exact SNI:** NONE — no safely admitted proposed hostname in this research round.
- **First-party evidence:** [https://bolt.eu/en-az/legal/rides/tnc-platform-ride-hailing/](https://bolt.eu/en-az/legal/rides/tnc-platform-ride-hailing/); grade **H**; claim: Bolt official evidence covers multi-service mobility platform including rides/delivery.
- **Mandatory false-positive caution / next negative:** bolt.eu is group brand host; does not identify rides from other Bolt products.
- **Decision for Architect:** **RESEARCH_HOLD**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

### 50. Wolt
- **Proposition:** `service.wolt`; primary Organization **Wolt**; proposed `category.other_supported`.
- **Exact SNI:** NONE — no safely admitted proposed hostname in this research round.
- **First-party evidence:** [https://wolt.com/](https://wolt.com/); grade **H**; claim: Wolt multi-function delivery public portal inspected.
- **Mandatory false-positive caution / next negative:** Single host may combine retail/delivery/merchant; exact Service scope needs admission.
- **Decision for Architect:** **RESEARCH_HOLD**, NOT ADMITTED. Additional Architect taxonomy/provenance/negative-fixture review required.

## 5. Special conflicts requiring explicit Architect action

1. **Meta family:** Facebook, Instagram, WhatsApp, Messenger, Threads are different Services; Meta-owned hostnames never inherit Service identity from corporate owner. `messenger.com` vs `facebook.com` contextual cross-service access requires conservative handling.
2. **Google family:** YouTube vs YouTube Music vs Docs vs Drive vs Meet vs Gemini vs shared Google identity. The previously missing `music.youtube.com` negative fixture is mandatory for original v1.
3. **Microsoft:** Teams / OneDrive / LinkedIn must not be inferred from login.microsoftonline.com or other common identity/CDN hosts.
4. **Bolt** has rides, delivery and micromobility under one brand; no exact rides-from-bolt.eu rule. **Wolt** and delivery-commerce sites need product scope definition.
5. **AI assistants:** ChatGPT / Gemini / Claude / DeepSeek do not map cleanly into `productivity_collaboration`; proposed `other_supported` or `productivity_collaboration` requires one explicit architect-wide policy; **no new category is silently invented**.
6. **Commerce and news:** local/global marketplaces, news, mobility services tentatively `category.other_supported`. This is only allowed for explicitly admitted known Service—not unrecognized traffic.
7. **Native applications:** Signal/Viber/Telegram/WhatsApp/etc. website evidence does not prove their mobile app payload. TLS ECH, VPN, SNI absence, IP/DNS/cache and QUIC with invisible hostname return coverage-limited/unknown.
8. **Host naming:** `threads.net` vs `threads.com`, `www` versus apex, and redirect hops are different exact SNI identities. A 30x navigation may result in a connection to a different host. Neither is silently auto-added.

## 6. Proposed fixtures / validation boundaries

`PROPOSED-NEGATIVE-FIXTURES-RESEARCH-v1.json` contains **189** draft vectors generated from exact-host equality. These are design vectors, **not an accepted NI-04K fixture suite**, not a production matcher test, and not actual network measurements. A negative fixture must be validated against the **whole candidate ruleset**: one sibling may itself be correctly recognized as a different Service, while it must *never resolve the wrong Service*. No accidental rule-ID winner, no inferred shared-IP service.

## 7. Architect prior R1 disposition (NORMATIVE; do not erase)

- The `TASK-DTI-NI-04K-ARCHITECT-SEMANTIC-REVIEW-R1` reviewed **candidate v1 (5 services)**, not candidate v2 or this TOP-50 research. It returned **REPAIR**, not PASS: missing same-Organization/different-Service negative `music.youtube.com`.
- The bounded corrected v1-R1 evidence-only package retains all three exact pre-existing artifact semantic digests and adds that one fixture; it must go through Architect bounded re-review.
- Existing candidate v2 (6 services with TikTok) is a **different, unadmitted** artifact set. No previous PASS or accepted hashes transfer to v2 or TOP-50 automatically.
- Extension to 50 should not be treated as 50 runtime rules in V1. Architect should decide whether to freeze a minimal vetted bundle first, then expand through version increments, or admit a larger explicitly evidenced bundle.

## 8. Required Architect disposition / decisions

1. Independently re-review repaired five-service v1-R1 fixture and confirm invariant semantic bytes; return PASS/REPAIR/REJECT.
2. Review each 50 entry: choose `ACCEPTED_HOST_AND_TAXONOMY` / `RESEARCH_REPAIR` / `HOLD`; explicit category for TikTok/AI/Steam/commerce/news/mobility, primary Organization, same-org siblings, site-specificity.
3. Decide whether the scope should initially contain **only verified web-hosts**; mobile-app-wide recognition is explicitly out of scope without independently admitted signal evidence.
4. Choose a new immutable **versioned** runtime bundle only for items receiving full per-rule admission; every active rule requires source references, positive/near-match/shared-cloud/same-org negatives, review due dates and complete manifest canonical integrity.
5. Only after Architect PASS, independent Tech Lead reviews provenance/integrity, then Owner accepts **exact digest tuple** for implementation. Until then NI-04A-CODE and MAIN NI-04 remain HOLD.

## 9. Governance footer

```text
TOP50_SOURCE_RESEARCH = COMPLETE_AS_PUBLIC_WEB_IDENTITY_AUDIT
TOP50_RUNTIME_RULESET = NOT_CREATED
TOP50_ARCHITECT_SEMANTIC_ADMISSION = PENDING
PRIOR_5_SERVICE_BOUNDED_EVIDENCE_REPAIR = PREPARED_SEPARATELY
INDEPENDENT_TECHLEAD_ADMISSION = PENDING
OWNER_BUNDLE_AUTHORIZATION = PENDING
NI04A_CODER = HOLD
MAIN_NI04_CODER = HOLD
PRODUCTION_MUTATIONS = NONE
```
