# Admin Web icon assets

Local presentation assets for CaptivPortal Admin Web.

## Structure

- `platforms/` — operating-system / platform icons.
- `devices/` — device-class icons reserved for future approved UI tasks.
- `ui/` — general presentation icons reserved for future approved UI tasks.

Assets are repository-local. Do not add runtime CDN or third-party image dependencies.

## Android robot

- Asset: `platforms/android.svg`
- Purpose: repository-local Android presentation cue. Home Online Devices uses the icon without constant adjacent `Android` text; Device/observation surfaces may pair the cue with unchanged raw `device_type` display text.
- Presentation matching uses only the canonical `device_type_key == "android"`; raw `device_type` text remains unchanged, and Admin Web does not normalize or infer the key.
- Source authority: Google LLC / Android Developers.
- Source asset URL: https://developer.android.com/static/images/brand/android-head_flat.svg
- Brand guidelines: https://developer.android.com/distribute/marketing-tools/brand-guidelines
- License: Creative Commons Attribution 3.0 (CC BY 3.0), as stated by the Android brand guidelines for the Android robot.
- Required attribution: "The Android robot is reproduced or modified from work created and shared by Google and used according to terms described in the Creative Commons 3.0 Attribution License."
- Modified: YES. The local copy adds an explicit `viewBox="0 0 152 89"` for bounded responsive rendering; artwork paths, fills and intrinsic width/height are otherwise unchanged.

The accepted Android asset is production-active under `TASK-WEB-ASSET-LIBRARY-01`; preserve this provenance/attribution record for future modification or replacement.
# NI-05 Organization Context assets (2026-10-14)

The organization dimension and service names are admitted NI-04 data, not a
claim of affiliation, endorsement, app use or complete activity. All images are
decorative, repository-local and loaded only through the existing
`/admin/static/icons/` route. Unknown IDs and failed images use the original
generic glyphs below; neither API names nor IDs become paths.

## Original generic glyphs

- `organizations/generic.svg`: original neutral building glyph, authored for
  CaptivPortal NI-05 (v1). Not a Google G, Meta infinity symbol or imitation.
- `services/generic.svg`: original neutral application glyph, authored for
  CaptivPortal NI-05 (v1). Not a YouTube play-logo imitation.
- These contain only passive SVG geometry; no third-party brand artwork or
  attribution requirement is asserted.

## Approved asset-specific exceptions

- **org.meta — Owner Exception 01:** generic organization glyph + the validated
  text name Meta. No Meta infinity artwork is bundled. The official
  [Meta brand guidelines](https://www.meta.com/brand/resources/meta/company-brand/)
  require brand approval for logo use; such approval was not supplied.
- **org.google — Owner Exception 02:** the same generic organization glyph +
  Google text, without Google G artwork or imitation. The
  [Google brand terms](https://about.google/intl/en/brand-resource-center/brand-terms/)
  do not establish a logo license for this application without approval.
- **service.youtube — Exception 02, clause 6:** generic service glyph + YouTube
  text. The current official [YouTube icon guidelines](https://brand.youtube/youtube-icon/)
  specify a 100px minimum digital height, incompatible with the approved
  compact 20–28px service tiles. No YouTube artwork is bundled or altered.
- The exceptions affect presentation assets only; Google/Meta service grouping
  and NI-04 data semantics are unchanged. They do not grant trademark licenses.

## Instagram

- Owner: Meta / Instagram. Source:
  [official Instagram Brand Resource Center](https://www.meta.com/brand/resources/instagram/instagram-brand/).
- Official download: `IG_brand_asset_pack_2023.zip`, entry
  `01 Static Glyph/03 Black Glyph/Instagram_Glyph_Black.svg`.
- Local file: `services/instagram.svg`; official black glyph geometry and
  viewBox preserved. Only a terminal newline is added; no design/color change.
- Official member SHA256: `a036f8197b3856b02d1e236e08dd1b50a4ed68cb148686beb274eabf29794d51`
  (1759 bytes). Local SHA256:
  `4d00888a7127830117f4538a9704f9fab9314cd6d2fce79444b293bed775503a`
  (1760 bytes).
- Basis: the website-use brand guidelines permit the official assets subject
  to their conditions, distinguish broadcast/large print approval, and prohibit
  implied endorsement, prominent branding and altered names. This is a small
  decorative icon beside the plain-text admitted service name, not a partner
  badge or app logo. No open-source license or unrelated Android license is
  claimed. All applicable trademark rights remain with the owner.
- No additional attribution obligation is stated in those website guidelines.
  This provenance record identifies the owner; it does not broaden permission.

## WhatsApp

- Owner: Meta / WhatsApp. Source:
  [official WhatsApp Brand Resource Center](https://www.meta.com/brand/resources/whatsapp/whatsapp-brand/).
- Official download: `WhatsApp-Brand-Resource-Center.zip`, entry
  `Brand Resource Center Page Downloads/01_Glyph/01_Digital RGB/03_SVG/Digital_Glyph_Green_RGB_2026.svg`.
- Local file: `services/whatsapp.svg`; official 2026 digital green SVG preserved
  without artwork, color or geometry edits; only a terminal newline is added.
- Official member SHA256: `f7b1311db718533e671645f57cd94b92f0e006e61d7e6581a80675fc5a478fc4`
  (1181 bytes). Local SHA256:
  `46d8d8acf2cf2bee7618db0924c6b53329cd70c919e763e7c77f0c12d03b53be`
  (1182 bytes).
- Basis: use of the official website resources subject to the published
  guidelines; scaling is allowed, alteration and implied endorsement are not.
  This small decorative icon accompanies the name WhatsApp and is not the
  dominant page element. No open-source license or sublicensing right is
  claimed. All applicable trademark rights remain with the owner.
- No additional attribution obligation is stated for this website use in those
  guidelines. Production activation remains a separate Owner decision.
