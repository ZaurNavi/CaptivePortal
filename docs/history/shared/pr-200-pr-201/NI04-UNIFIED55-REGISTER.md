# NI-04 Unified 55 — исследовательский реестр (НЕ runtime ruleset)

**TOP-50 + исходная пятёрка:** исходные пять уже находятся в TOP-50. Для 55 уникальных сервисов добавлены новые №51–55. Это scope/delivery реестр, а не доказательство 55 успешных распознаваний.

| № | Service | Exact SNI candidate | Category | Architect / admission |
|---:|---|---|---|---|
| 1 | YouTube | `www.youtube.com` | `category.video_streaming` | LANE A VERIFIED (OWNER DIRECTED) |
| 2 | TikTok | `www.tiktok.com` | `category.social` | ARCH ACCEPT HOST TAXONOMY |
| 3 | WhatsApp | `web.whatsapp.com` | `category.messaging` | LANE A VERIFIED (OWNER DIRECTED) |
| 4 | Instagram | — | `category.social` | ARCH HOLD |
| 5 | Telegram | `web.telegram.org` | `category.messaging` | LANE A VERIFIED (OWNER DIRECTED) |
| 6 | Facebook | `www.facebook.com` | `category.social` | ARCH ACCEPT HOST TAXONOMY |
| 7 | ChatGPT | `chatgpt.com` | `category.other_supported` | ARCH REPAIR CATEGORY |
| 8 | Spotify | `open.spotify.com` | `category.audio_streaming` | LANE A VERIFIED (OWNER DIRECTED) |
| 9 | Netflix | `www.netflix.com` | `category.video_streaming` | LANE A VERIFIED (OWNER DIRECTED) |
| 10 | Pinterest | `pinterest.com` | `category.social` | ARCH ACCEPT HOST TAXONOMY |
| 11 | Roblox | `www.roblox.com` | `category.gaming` | ARCH ACCEPT HOST TAXONOMY |
| 12 | Snapchat | `web.snapchat.com` | `category.social` | ARCH ACCEPT HOST TAXONOMY |
| 13 | Facebook Messenger | `messenger.com` | `category.messaging` | ARCH ACCEPT HOST TAXONOMY |
| 14 | Discord | `discord.com` | `category.messaging` | ARCH ACCEPT HOST TAXONOMY |
| 15 | Twitch | `www.twitch.tv` | `category.video_streaming` | ARCH ACCEPT HOST TAXONOMY |
| 16 | X | — | `category.social` | ARCH HOLD |
| 17 | Google Drive | `drive.google.com` | `category.cloud_storage` | ARCH ACCEPT HOST TAXONOMY |
| 18 | Microsoft Teams | `teams.microsoft.com` | `category.productivity_collaboration` | ARCH ACCEPT HOST TAXONOMY |
| 19 | Zoom | `join.zoom.us` | `category.productivity_collaboration` | ARCH ACCEPT HOST TAXONOMY |
| 20 | LinkedIn | `www.linkedin.com` | `category.social` | ARCH ACCEPT HOST TAXONOMY |
| 21 | Threads | `threads.com` | `category.social` | ARCH ACCEPT HOST TAXONOMY |
| 22 | Reddit | `www.reddit.com` | `category.social` | ARCH ACCEPT HOST TAXONOMY |
| 23 | VK | — | `category.social` | ARCH HOLD |
| 24 | Signal | — | `category.messaging` | ARCH HOLD |
| 25 | Viber | — | `category.messaging` | ARCH HOLD |
| 26 | Microsoft OneDrive | — | `category.cloud_storage` | ARCH HOLD |
| 27 | Dropbox | `www.dropbox.com` | `category.cloud_storage` | ARCH ACCEPT HOST TAXONOMY |
| 28 | Google Meet | `meet.google.com` | `category.productivity_collaboration` | ARCH ACCEPT HOST TAXONOMY |
| 29 | Google Docs | `docs.google.com` | `category.productivity_collaboration` | ARCH ACCEPT HOST TAXONOMY |
| 30 | Google Gemini | `gemini.google.com` | `category.other_supported` | ARCH ACCEPT HOST TAXONOMY |
| 31 | Claude | `claude.ai` | `category.other_supported` | ARCH ACCEPT HOST TAXONOMY |
| 32 | DeepSeek | `chat.deepseek.com` | `category.other_supported` | ARCH ACCEPT HOST TAXONOMY |
| 33 | Apple Music | `music.apple.com` | `category.audio_streaming` | ARCH ACCEPT HOST TAXONOMY |
| 34 | SoundCloud | `soundcloud.com` | `category.audio_streaming` | ARCH ACCEPT HOST TAXONOMY |
| 35 | YouTube Music | `music.youtube.com` | `category.audio_streaming` | ARCH ACCEPT HOST TAXONOMY |
| 36 | Prime Video | `www.primevideo.com` | `category.video_streaming` | ARCH ACCEPT HOST TAXONOMY |
| 37 | Disney+ | `www.disneyplus.com` | `category.video_streaming` | ARCH ACCEPT HOST TAXONOMY |
| 38 | Steam | `store.steampowered.com` | `category.software_distribution` | ARCH ACCEPT HOST TAXONOMY |
| 39 | Epic Games Store | `store.epicgames.com` | `category.software_distribution` | ARCH ACCEPT HOST TAXONOMY |
| 40 | Birmarket | `birmarket.az` | `category.other_supported` | ARCH ACCEPT HOST TAXONOMY |
| 41 | Tap.az | `tap.az` | `category.other_supported` | ARCH ACCEPT HOST TAXONOMY |
| 42 | Turbo.az | `turbo.az` | `category.other_supported` | ARCH ACCEPT HOST TAXONOMY |
| 43 | Lalafo.az | `lalafo.az` | `category.other_supported` | ARCH ACCEPT HOST TAXONOMY |
| 44 | Oxu.az | `oxu.az` | `category.other_supported` | ARCH ACCEPT HOST TAXONOMY |
| 45 | Yandex Search | `yandex.com` | `category.web_search` | ARCH ACCEPT HOST TAXONOMY |
| 46 | Temu | `www.temu.com` | `category.other_supported` | ARCH ACCEPT HOST TAXONOMY |
| 47 | Trendyol | `www.trendyol.com` | `category.other_supported` | ARCH ACCEPT HOST TAXONOMY |
| 48 | AliExpress | — | `category.other_supported` | ARCH HOLD |
| 49 | Bolt | — | `category.other_supported` | ARCH HOLD |
| 50 | Wolt | — | `category.other_supported` | ARCH HOLD |
| 51 | Gmail | `mail.google.com` | `category.productivity_collaboration` | NEW RESEARCH CANDIDATE |
| 52 | Google Maps | `maps.google.com` | `category.other_supported` | NEW RESEARCH CANDIDATE |
| 53 | Google Translate | `translate.google.com` | `category.other_supported` | NEW RESEARCH CANDIDATE |
| 54 | Outlook.com (consumer web) | `outlook.live.com` | `category.productivity_collaboration` | NEW RESEARCH CANDIDATE |
| 55 | Booking.com | `www.booking.com` | `category.other_supported` | NEW RESEARCH CANDIDATE |

## Надёжность

- Источник для 50 позиций — существующая исследовательская матрица R2 и формальный Architect R2 decision; некоторые источники — только фирменные сайты, не полноценное per-rule доказательство.
- `ARCH_ACCEPT_HOST_TAXONOMY` ≠ knowledge bundle PASS; без доказательств §2.4 Coder не включает runtime rule.
- Девять `ARCH_HOLD` не получают активных host-rule даже если известен бренд или есть маркетинговый сайт.
- Новый TOP-55 — не рейтинг статистики реального трафика Zefer_Parki и не список подтверждённых мобильных приложений.
- Не использовать этот JSON как runtime файл; в production нужны три проверенных immutable artifacts с digest.

## Официальные источники для дополнительных пяти

- **Gmail**: `mail.google.com` — https://support.google.com/mail/answer/9259768?hl=en-GB; negative suggestion `docs.google.com`; *research-only*.
- **Google Maps**: `maps.google.com` — https://support.google.com/maps/answer/17114780?hl=en-GB; negative suggestion `drive.google.com`; *research-only*.
- **Google Translate**: `translate.google.com` — https://support.google.com/translate/answer/15139004?hl=en-GB; negative suggestion `maps.google.com`; *research-only*.
- **Outlook.com (consumer web)**: `outlook.live.com` — https://support.microsoft.com/en-us/outlook/getstarted/what-version-of-outlook-do-i-have?so=1; negative suggestion `teams.microsoft.com`; *research-only*.
- **Booking.com**: `www.booking.com` — https://www.booking.com/content/terms.html; negative suggestion `notwww.booking.com`; *research-only*.
