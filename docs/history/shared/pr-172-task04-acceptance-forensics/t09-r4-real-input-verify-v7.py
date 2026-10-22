"""T-09 R4 V7: verify the pre-existing real-device T-09 Task-01 input.

Read-only proof that:
- the historical T-09 capture exists at its pinned path and exact SHA256;
- it is distinct from the empty T-07 fixture used accidentally by R4;
- it contains the frozen controlled Android/Windows windows and expected binding scopes;
- source-health rows/anchors exist where available.

No classification, no writes, no payload_json output.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

REAL_DB = Path(r"C:\CaptivPortal-Lab\official-runs\task04\t09\inputs\task01-t09-20260930.sqlite3")
REAL_DB_SHA = "a8ea541ca7fe5cd8498efaba028d8768a39e06cd1cdc688551a9f883e16040cd"

EMPTY_T07_DB = Path(r"C:\CaptivPortal-Lab\gates\task04\t07\inputs\task01-source-r2.sqlite3")
EMPTY_T07_SHA = "79cfcfb8c463c235af1d7dfe4f49a8e9ef491a25749ccbeeded85b88f2ee90f9"

SITE_ID = "6a64f17630da7c70d232187a"

DEVICES = (
    ("OWNER_ANDROID", "be:00:7d:9b:04:2e",
     "2026-09-30T09:04:08.388Z", "2026-09-30T09:08:09.000Z"),
    ("OWNER_WINDOWS_LAPTOP", "cc:f9:e4:d6:ab:1e",
     "2026-09-30T09:23:00.176Z", "2026-09-30T09:30:15.000Z"),
)

BINDINGS = (
    ("dhcp", "sensor-zefer-01", "zefer-span-01"),
    ("portal_headers", "portal-zefer-01", "zefer-portal-http-01"),
    ("quic_client", "sensor-zefer-01", "zefer-span-01"),
    ("tcp_syn", "sensor-zefer-01", "zefer-span-01"),
    ("tls_client", "sensor-zefer-01", "zefer-span-01"),
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def open_ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def check_identity(path: Path, expected: str, label: str) -> str:
    if not path.is_file():
        print(f"{label}_EXISTS=NO")
        raise RuntimeError(f"{label}_MISSING")
    actual = sha256(path)
    print(f"{label}_PATH={path}")
    print(f"{label}_EXISTS=YES")
    print(f"{label}_SHA256={actual}")
    if actual != expected:
        raise RuntimeError(f"{label}_SHA256_MISMATCH")
    return actual


def inspect_db(path: Path, prefix: str):
    conn = open_ro(path)
    try:
        quick = [r[0] for r in conn.execute("PRAGMA quick_check").fetchall()]
        print(f"{prefix}_QUICK_CHECK={'PASS' if quick == ['ok'] else 'FAIL'}")
        print(f"{prefix}_USER_VERSION={scalar(conn, 'PRAGMA user_version')}")
        state = conn.execute(
            "SELECT database_generation_id,last_ingest_sequence "
            "FROM device_fingerprint_storage_state WHERE singleton_id=1"
        ).fetchone()
        if state is None:
            raise RuntimeError(f"{prefix}_STORAGE_STATE_MISSING")
        watermark = int(state["last_ingest_sequence"])
        print(f"{prefix}_DATABASE_GENERATION_ID={state['database_generation_id']}")
        print(f"{prefix}_MAX_COMMITTED_INGEST_SEQUENCE={watermark}")
        print(f"{prefix}_EVIDENCE_TOTAL={scalar(conn, 'SELECT COUNT(*) FROM device_fingerprint_evidence')}")
        print(f"{prefix}_HEALTH_TOTAL={scalar(conn, 'SELECT COUNT(*) FROM device_fingerprint_source_health_events')}")
        return conn, watermark
    except Exception:
        conn.close()
        raise


def main() -> int:
    try:
        real_before = check_identity(REAL_DB, REAL_DB_SHA, "REAL_T09_DB")
        empty_before = check_identity(EMPTY_T07_DB, EMPTY_T07_SHA, "EMPTY_T07_DB")

        empty, empty_wm = inspect_db(EMPTY_T07_DB, "EMPTY_T07")
        try:
            empty_e = scalar(empty, "SELECT COUNT(*) FROM device_fingerprint_evidence")
            empty_h = scalar(empty, "SELECT COUNT(*) FROM device_fingerprint_source_health_events")
            if empty_wm != 0 or empty_e != 0 or empty_h != 0:
                raise RuntimeError("T07_FIXTURE_NOT_EMPTY_AS_EXPECTED")
        finally:
            empty.close()
        print("T07_FIXTURE_EMPTY_CONFIRMED=YES")

        real, watermark = inspect_db(REAL_DB, "REAL_T09")
        try:
            site_e = scalar(
                real,
                "SELECT COUNT(*) FROM device_fingerprint_evidence "
                "WHERE site_id=? AND ingest_sequence<=?",
                (SITE_ID, watermark),
            )
            site_h = scalar(
                real,
                "SELECT COUNT(*) FROM device_fingerprint_source_health_events "
                "WHERE site_id=? AND ingest_sequence<=?",
                (SITE_ID, watermark),
            )
            print(f"REAL_T09_SITE_ID={SITE_ID}")
            print(f"REAL_T09_SITE_EVIDENCE_TOTAL={site_e}")
            print(f"REAL_T09_SITE_HEALTH_TOTAL={site_h}")

            overall_device_pass = True

            for idx, (label, mac, start, end) in enumerate(DEVICES, 1):
                print(f"DEVICE_{idx}_LABEL={label}")
                print(f"DEVICE_{idx}_MAC={mac}")
                print(f"DEVICE_{idx}_WINDOW_START={start}")
                print(f"DEVICE_{idx}_WINDOW_END={end}")

                raw = scalar(
                    real,
                    "SELECT COUNT(*) FROM device_fingerprint_evidence "
                    "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? "
                    "AND ingest_sequence<=?",
                    (SITE_ID, mac, start, end, watermark),
                )
                print(f"DEVICE_{idx}_RAW_EXACT_EVIDENCE_COUNT={raw}")

                groups = real.execute(
                    "SELECT source_kind,producer_id,capture_source_id,quality_state,"
                    "feature_schema_version,COUNT(*) AS n "
                    "FROM device_fingerprint_evidence "
                    "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? "
                    "AND ingest_sequence<=? "
                    "GROUP BY source_kind,producer_id,capture_source_id,quality_state,feature_schema_version "
                    "ORDER BY source_kind,producer_id,capture_source_id,quality_state,feature_schema_version",
                    (SITE_ID, mac, start, end, watermark),
                ).fetchall()
                print(
                    f"DEVICE_{idx}_EVIDENCE_GROUPS=["
                    + ";".join(
                        f"{r['source_kind']}|{r['producer_id']}|{r['capture_source_id']}|"
                        f"{r['quality_state']}|schema={r['feature_schema_version']}|count={r['n']}"
                        for r in groups
                    )
                    + "]"
                )

                binding_total = 0
                health_window_total = 0
                health_anchor_count = 0
                for kind, producer, capture in BINDINGS:
                    ec = scalar(
                        real,
                        "SELECT COUNT(*) FROM device_fingerprint_evidence "
                        "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? "
                        "AND source_kind=? AND producer_id=? AND capture_source_id=? "
                        "AND ingest_sequence<=?",
                        (SITE_ID, mac, start, end, kind, producer, capture, watermark),
                    )
                    binding_total += int(ec)
                    print(f"DEVICE_{idx}_BINDING_{kind.upper()}_EVIDENCE_COUNT={ec}")

                    hc = scalar(
                        real,
                        "SELECT COUNT(*) FROM device_fingerprint_source_health_events "
                        "WHERE site_id=? AND producer_id=? AND capture_source_id=? AND source_kind=? "
                        "AND observed_at>=? AND observed_at<? AND ingest_sequence<=?",
                        (SITE_ID, producer, capture, kind, start, end, watermark),
                    )
                    health_window_total += int(hc)

                    anchor = real.execute(
                        "SELECT observed_at,status,reason_code "
                        "FROM device_fingerprint_source_health_events "
                        "WHERE site_id=? AND producer_id=? AND capture_source_id=? AND source_kind=? "
                        "AND observed_at<=? AND ingest_sequence<=? "
                        "ORDER BY observed_at DESC,source_health_id DESC LIMIT 1",
                        (SITE_ID, producer, capture, kind, start, watermark),
                    ).fetchone()
                    if anchor is not None:
                        health_anchor_count += 1
                        anchor_text = (
                            f"{anchor['observed_at']}|{anchor['status']}|"
                            f"{'' if anchor['reason_code'] is None else anchor['reason_code']}"
                        )
                    else:
                        anchor_text = "NONE"
                    print(
                        f"DEVICE_{idx}_HEALTH_{kind.upper()}="
                        f"window_count={hc}|anchor={anchor_text}"
                    )

                print(f"DEVICE_{idx}_EXPECTED_BINDING_EVIDENCE_TOTAL={binding_total}")
                print(f"DEVICE_{idx}_HEALTH_WINDOW_TOTAL={health_window_total}")
                print(f"DEVICE_{idx}_HEALTH_ANCHOR_SCOPE_COUNT={health_anchor_count}")

                before = real.execute(
                    "SELECT observed_at,source_kind,producer_id,capture_source_id "
                    "FROM device_fingerprint_evidence "
                    "WHERE site_id=? AND observed_mac=? AND observed_at<? AND ingest_sequence<=? "
                    "ORDER BY observed_at DESC,evidence_id DESC LIMIT 1",
                    (SITE_ID, mac, start, watermark),
                ).fetchone()
                after = real.execute(
                    "SELECT observed_at,source_kind,producer_id,capture_source_id "
                    "FROM device_fingerprint_evidence "
                    "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND ingest_sequence<=? "
                    "ORDER BY observed_at,evidence_id LIMIT 1",
                    (SITE_ID, mac, end, watermark),
                ).fetchone()
                print(
                    f"DEVICE_{idx}_NEAREST_BEFORE="
                    + ("NONE" if before is None else "|".join(str(v) for v in before))
                )
                print(
                    f"DEVICE_{idx}_NEAREST_AFTER="
                    + ("NONE" if after is None else "|".join(str(v) for v in after))
                )

                device_pass = raw > 0 and binding_total > 0
                print(f"DEVICE_{idx}_CONTROLLED_WINDOW_DATA_PRESENT={'YES' if device_pass else 'NO'}")
                overall_device_pass = overall_device_pass and device_pass

            print(f"REAL_T09_CONTROLLED_WINDOWS_DATA_PRESENT={'YES' if overall_device_pass else 'NO'}")
            if not overall_device_pass:
                raise RuntimeError("REAL_T09_CONTROLLED_WINDOW_DATA_MISSING")
        finally:
            real.close()

        real_after = sha256(REAL_DB)
        empty_after = sha256(EMPTY_T07_DB)
        print(f"REAL_T09_DB_SHA256_AFTER={real_after}")
        print(f"EMPTY_T07_DB_SHA256_AFTER={empty_after}")
        print(f"REAL_T09_DB_UNCHANGED={'YES' if real_after == real_before == REAL_DB_SHA else 'NO'}")
        print(f"EMPTY_T07_DB_UNCHANGED={'YES' if empty_after == empty_before == EMPTY_T07_SHA else 'NO'}")
        print("CLASSIFICATION_EXECUTION=NO")
        print("CLASSIFICATION_RESULT_PERSISTED=NO")
        print("T09_FORMAL_RERUN=NO")
        print("PRODUCTION_ACTION=NO")
        print("DIAGNOSTIC_STATUS=PASS")
        return 0
    except Exception as exc:
        print("CLASSIFICATION_EXECUTION=NO")
        print("CLASSIFICATION_RESULT_PERSISTED=NO")
        print("T09_FORMAL_RERUN=NO")
        print("PRODUCTION_ACTION=NO")
        print("DIAGNOSTIC_STATUS=BLOCKED")
        print(f"BLOCKER={type(exc).__name__}:{exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
