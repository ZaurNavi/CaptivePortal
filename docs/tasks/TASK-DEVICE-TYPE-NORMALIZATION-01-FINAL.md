# TASK-DEVICE-TYPE-NORMALIZATION-01 — Canonical Device Type Foundation — FINAL

Status: CLOSED / MERGED / DEPLOYED / PRODUCTION ACTIVE
Updated: 2026-09-13

## Identity

```text
PR=#119
title=TASK-DEVICE-TYPE-NORMALIZATION-01: canonical Device Type foundation
baseline=2d87fd6d56f969492318e21c809086576b2b1ab1
publication commit=6597d6615af14a1dc7988cefc5a769ad51591b39
merge commit=144c8a922b4431293fdc1d4bb57bed29a8402f6b
accepted / merge tree=2349838d7e524efd3fb2e0433a7111553f195e71
changed files=19
diff stat=+425/-21
```

## Canonical owner

```text
app/common/device_type.py

DEVICE_TYPE_KEY_MAX_UTF8_BYTES = 128

normalize_device_type_key(source_value: object) -> str | None
```

## Canonical lexical normalization

The canonical machine key is derived from one raw source value only:

```text
1. None -> None
2. non-string -> None
3. strip
4. empty -> None
5. NUL -> None
6. strict UTF-8 encode
7. raw trimmed value > 128 UTF-8 bytes -> None
8. casefold
9. empty -> None
10. NUL -> None
11. strict UTF-8 encode
12. canonical value > 128 UTF-8 bytes -> None
13. return canonical key
```

Permanent exclusions:

```text
Unicode normalization form=NO
semantic alias mapping=NO
cross-field inference=NO
separator collapsing=NO
truncation=NO
```

Examples:

```text
" Android " -> "android"
"phone"     -> "phone"
"É"         -> "é"
```

A decomposed `E + combining acute` is not automatically converted to composed
`é`; there is no NFC/NFD/NFKC/NFKD normalization.

## Raw vs canonical roles

```text
device_type     = raw/source/display evidence
device_type_key = canonical machine/presentation key
```

The raw value remains backward-compatible evidence and is not replaced by the
canonical key.

## Read-surface enrichment

The task adds read-time canonical keys while preserving source persistence.

Relevant surfaces include:

- Home Current State client items: `device_type`, `device_type_key`;
- historical Device list / identity;
- Device Current Context current client;
- Observation client DTO data;
- Analytics `SafeSnapshotSummary`;
- Visitor Registry snapshots: `device_type_key`;
- Visitor Registry device summary: `last_known_device_type_key`.

No DB migration or backfill stores the canonical key as a new source fact.

## Frontend boundary

The browser is not the normalization authority.

```text
frontend trim/lower/casefold=FORBIDDEN
frontend Unicode normalization=FORBIDDEN
frontend Device Type inference=FORBIDDEN
```

Consumers use the server-provided canonical key for machine decisions and raw
`device_type` for truthful display/source text.

## Acceptance

```text
Coder focused tests=38 passed
compileall=PASS
git diff --check=PASS
Windows Central Lab V7 strict=PASS
accepted tree=2349838d7e524efd3fb2e0433a7111553f195e71
```

The current production project later advanced through PR #120 without changing
this canonical normalization contract.
