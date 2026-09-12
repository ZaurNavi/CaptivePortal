# Admin Web icon assets

Local presentation assets for CaptivPortal Admin Web.

## Structure

- `platforms/` — operating-system / platform icons.
- `devices/` — device-class icons reserved for future approved UI tasks.
- `ui/` — general presentation icons reserved for future approved UI tasks.

Assets are repository-local. Do not add runtime CDN or third-party image dependencies.

## Android robot

- Asset: `platforms/android.svg`
- Purpose: decorative cue before unchanged Android `device_type` text anywhere Admin Web renders that field, including Devices list, Device detail identity/evidence, and observations.
- Presentation matching is case-insensitive (`android`, `Android`, `ANDROID`, etc.); the source text itself is displayed unchanged.
- Source authority: Google LLC / Android Developers.
- Source asset URL: https://developer.android.com/static/images/brand/android-head_flat.svg
- Brand guidelines: https://developer.android.com/distribute/marketing-tools/brand-guidelines
- License: Creative Commons Attribution 3.0 (CC BY 3.0), as stated by the Android brand guidelines for the Android robot.
- Required attribution: "The Android robot is reproduced or modified from work created and shared by Google and used according to terms described in the Creative Commons 3.0 Attribution License."
- Modified: YES. The local copy adds an explicit `viewBox="0 0 152 89"` for bounded responsive rendering; artwork paths, fills and intrinsic width/height are otherwise unchanged.

The accepted Android asset is production-active under `TASK-WEB-ASSET-LIBRARY-01`; preserve this provenance/attribution record for future modification or replacement.
