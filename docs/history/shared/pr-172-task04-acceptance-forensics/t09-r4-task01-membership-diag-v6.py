"""T-09 R4 V6: read-only Task-01 membership/binding diagnostic.

Purpose:
- Explain why the frozen R4 T-09 snapshots contained zero evidence descriptors
  and zero source-health descriptors for both controlled devices.
- Distinguish raw-data absence from window mismatch, MAC mismatch, binding-scope
  mismatch, and source-health data gaps.

This tool:
- opens the exact frozen Task-01 DB read-only;
- never runs classification or RequestAssembly;
- never reads/prints payload_json;
- never modifies formal T-09 evidence;
- verifies the Task-01 DB SHA256 before and after.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

TASK01_DB = Path(r"C:\CaptivPortal-Lab\gates\task04\t07\inputs\task01-source-r2.sqlite3")
EXPECTED_TASK01_SHA = "79cfcfb8c463c235af1d7dfe4f49a8e9ef491a25749ccbeeded85b88f2ee90f9"
SITE_ID = "6a64f17630da7c70d232187a"

DEVICES = (
    {
        "label": "OWNER_ANDROID",
        "mac": "be:00:7d:9b:04:2e",
        "start": "2026-09-30T09:04:08.388Z",
        "end": "2026-09-30T09:08:09.000Z",
    },
    {
        "label": "OWNER_WINDOWS_LAPTOP",
        "mac": "cc:f9:e4:d6:ab:1e",
        "start": "2026-09-30T09:23:00.176Z",
        "end": "2026-09-30T09:30:15.000Z",
    },
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


def one(conn: sqlite3.Connection, sql: str, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def rows(conn: sqlite3.Connection, sql: str, params=()):
    return conn.execute(sql, params).fetchall()


def print_group(prefix: str, data):
    if not data:
        print(f"{prefix}=[]")
        return
    packed = []
    for row in data:
        packed.append("|".join("" if value is None else str(value) for value in row))
    print(f"{prefix}=[" + ";".join(packed) + "]")


def main() -> int:
    before = sha256(TASK01_DB)
    print(f"TASK01_DB={TASK01_DB}")
    print(f"TASK01_SHA256_BEFORE={before}")
    if before != EXPECTED_TASK01_SHA:
        print("DIAGNOSTIC_STATUS=BLOCKED")
        print("BLOCKER=TASK01_SHA256_MISMATCH")
        return 2

    uri = TASK01_DB.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        quick = [r[0] for r in conn.execute("PRAGMA quick_check").fetchall()]
        print(f"SQLITE_QUICK_CHECK={'PASS' if quick == ['ok'] else 'FAIL'}")
        print(f"SQLITE_USER_VERSION={one(conn, 'PRAGMA user_version')}")

        state = conn.execute(
            "SELECT database_generation_id,last_ingest_sequence "
            "FROM device_fingerprint_storage_state WHERE singleton_id=1"
        ).fetchone()
        if state is None:
            print("DIAGNOSTIC_STATUS=BLOCKED")
            print("BLOCKER=TASK01_STORAGE_STATE_MISSING")
            return 2
        watermark = int(state["last_ingest_sequence"])
        print(f"DATABASE_GENERATION_ID={state['database_generation_id']}")
        print(f"MAX_COMMITTED_INGEST_SEQUENCE={watermark}")

        evidence_total = one(conn, "SELECT COUNT(*) FROM device_fingerprint_evidence")
        health_total = one(conn, "SELECT COUNT(*) FROM device_fingerprint_source_health_events")
        print(f"TASK01_EVIDENCE_TOTAL={evidence_total}")
        print(f"TASK01_HEALTH_TOTAL={health_total}")

        site_evidence_total = one(
            conn,
            "SELECT COUNT(*) FROM device_fingerprint_evidence "
            "WHERE site_id=? AND ingest_sequence<=?",
            (SITE_ID, watermark),
        )
        site_health_total = one(
            conn,
            "SELECT COUNT(*) FROM device_fingerprint_source_health_events "
            "WHERE site_id=? AND ingest_sequence<=?",
            (SITE_ID, watermark),
        )
        print(f"SITE_ID={SITE_ID}")
        print(f"SITE_EVIDENCE_TOTAL={site_evidence_total}")
        print(f"SITE_HEALTH_TOTAL={site_health_total}")

        site_evidence_range = conn.execute(
            "SELECT MIN(observed_at),MAX(observed_at) "
            "FROM device_fingerprint_evidence WHERE site_id=? AND ingest_sequence<=?",
            (SITE_ID, watermark),
        ).fetchone()
        site_health_range = conn.execute(
            "SELECT MIN(observed_at),MAX(observed_at) "
            "FROM device_fingerprint_source_health_events WHERE site_id=? AND ingest_sequence<=?",
            (SITE_ID, watermark),
        ).fetchone()
        print(f"SITE_EVIDENCE_MIN_OBSERVED_AT={site_evidence_range[0]}")
        print(f"SITE_EVIDENCE_MAX_OBSERVED_AT={site_evidence_range[1]}")
        print(f"SITE_HEALTH_MIN_OBSERVED_AT={site_health_range[0]}")
        print(f"SITE_HEALTH_MAX_OBSERVED_AT={site_health_range[1]}")

        for idx, dev in enumerate(DEVICES, 1):
            label, mac, start, end = dev["label"], dev["mac"], dev["start"], dev["end"]
            print(f"DEVICE_{idx}_LABEL={label}")
            print(f"DEVICE_{idx}_MAC={mac}")
            print(f"DEVICE_{idx}_WINDOW_START={start}")
            print(f"DEVICE_{idx}_WINDOW_END={end}")

            exact_raw = one(
                conn,
                "SELECT COUNT(*) FROM device_fingerprint_evidence "
                "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? "
                "AND ingest_sequence<=?",
                (SITE_ID, mac, start, end, watermark),
            )
            exact_casefold = one(
                conn,
                "SELECT COUNT(*) FROM device_fingerprint_evidence "
                "WHERE site_id=? AND lower(observed_mac)=lower(?) AND observed_at>=? AND observed_at<? "
                "AND ingest_sequence<=?",
                (SITE_ID, mac, start, end, watermark),
            )
            target_all = one(
                conn,
                "SELECT COUNT(*) FROM device_fingerprint_evidence "
                "WHERE site_id=? AND observed_mac=? AND ingest_sequence<=?",
                (SITE_ID, mac, watermark),
            )
            target_range = conn.execute(
                "SELECT MIN(observed_at),MAX(observed_at) FROM device_fingerprint_evidence "
                "WHERE site_id=? AND observed_mac=? AND ingest_sequence<=?",
                (SITE_ID, mac, watermark),
            ).fetchone()
            site_window_any = one(
                conn,
                "SELECT COUNT(*) FROM device_fingerprint_evidence "
                "WHERE site_id=? AND observed_at>=? AND observed_at<? AND ingest_sequence<=?",
                (SITE_ID, start, end, watermark),
            )
            site_window_macs = one(
                conn,
                "SELECT COUNT(DISTINCT observed_mac) FROM device_fingerprint_evidence "
                "WHERE site_id=? AND observed_at>=? AND observed_at<? AND ingest_sequence<=?",
                (SITE_ID, start, end, watermark),
            )

            print(f"DEVICE_{idx}_RAW_EXACT_EVIDENCE_COUNT={exact_raw}")
            print(f"DEVICE_{idx}_RAW_EXACT_CASEFOLD_EVIDENCE_COUNT={exact_casefold}")
            print(f"DEVICE_{idx}_TARGET_MAC_SITE_TOTAL={target_all}")
            print(f"DEVICE_{idx}_TARGET_MAC_MIN_OBSERVED_AT={target_range[0]}")
            print(f"DEVICE_{idx}_TARGET_MAC_MAX_OBSERVED_AT={target_range[1]}")
            print(f"DEVICE_{idx}_SITE_WINDOW_ANY_MAC_EVIDENCE_COUNT={site_window_any}")
            print(f"DEVICE_{idx}_SITE_WINDOW_DISTINCT_MAC_COUNT={site_window_macs}")

            exact_groups = rows(
                conn,
                "SELECT source_kind,producer_id,capture_source_id,quality_state,"
                "feature_schema_version,COUNT(*) "
                "FROM device_fingerprint_evidence "
                "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? "
                "AND ingest_sequence<=? "
                "GROUP BY source_kind,producer_id,capture_source_id,quality_state,feature_schema_version "
                "ORDER BY source_kind,producer_id,capture_source_id,quality_state,feature_schema_version",
                (SITE_ID, mac, start, end, watermark),
            )
            print_group(f"DEVICE_{idx}_RAW_EXACT_EVIDENCE_GROUPS", exact_groups)

            authorized_tuple_total = 0
            for kind, producer, capture in BINDINGS:
                count = one(
                    conn,
                    "SELECT COUNT(*) FROM device_fingerprint_evidence "
                    "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? "
                    "AND source_kind=? AND producer_id=? AND capture_source_id=? "
                    "AND ingest_sequence<=?",
                    (SITE_ID, mac, start, end, kind, producer, capture, watermark),
                )
                authorized_tuple_total += int(count)
                print(
                    f"DEVICE_{idx}_BINDING_MATCH_{kind.upper()}="
                    f"{count}|producer={producer}|capture={capture}"
                )
            print(f"DEVICE_{idx}_BINDING_TUPLE_MATCH_TOTAL={authorized_tuple_total}")

            before_row = conn.execute(
                "SELECT observed_at,source_kind,producer_id,capture_source_id,quality_state "
                "FROM device_fingerprint_evidence "
                "WHERE site_id=? AND observed_mac=? AND observed_at<? AND ingest_sequence<=? "
                "ORDER BY observed_at DESC,evidence_id DESC LIMIT 1",
                (SITE_ID, mac, start, watermark),
            ).fetchone()
            after_row = conn.execute(
                "SELECT observed_at,source_kind,producer_id,capture_source_id,quality_state "
                "FROM device_fingerprint_evidence "
                "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND ingest_sequence<=? "
                "ORDER BY observed_at,evidence_id LIMIT 1",
                (SITE_ID, mac, end, watermark),
            ).fetchone()
            print(
                f"DEVICE_{idx}_NEAREST_EVIDENCE_BEFORE="
                + ("NONE" if before_row is None else "|".join(str(x) for x in before_row))
            )
            print(
                f"DEVICE_{idx}_NEAREST_EVIDENCE_AFTER="
                + ("NONE" if after_row is None else "|".join(str(x) for x in after_row))
            )

            health_exact_total = 0
            health_anchor_total = 0
            for kind, producer, capture in BINDINGS:
                hc = one(
                    conn,
                    "SELECT COUNT(*) FROM device_fingerprint_source_health_events "
                    "WHERE site_id=? AND producer_id=? AND capture_source_id=? AND source_kind=? "
                    "AND observed_at>=? AND observed_at<? AND ingest_sequence<=?",
                    (SITE_ID, producer, capture, kind, start, end, watermark),
                )
                health_exact_total += int(hc)
                anchor = conn.execute(
                    "SELECT observed_at,status,reason_code FROM device_fingerprint_source_health_events "
                    "WHERE site_id=? AND producer_id=? AND capture_source_id=? AND source_kind=? "
                    "AND observed_at<=? AND ingest_sequence<=? "
                    "ORDER BY observed_at DESC,source_health_id DESC LIMIT 1",
                    (SITE_ID, producer, capture, kind, start, watermark),
                ).fetchone()
                if anchor is not None:
                    health_anchor_total += 1
                print(
                    f"DEVICE_{idx}_HEALTH_{kind.upper()}="
                    f"window_count={hc}|anchor="
                    + ("NONE" if anchor is None else "|".join("" if x is None else str(x) for x in anchor))
                )
            print(f"DEVICE_{idx}_HEALTH_EXACT_WINDOW_TOTAL={health_exact_total}")
            print(f"DEVICE_{idx}_HEALTH_ANCHOR_SCOPE_COUNT={health_anchor_total}")

            if exact_raw > 0 and authorized_tuple_total == 0:
                diagnosis = "RAW_EVIDENCE_PRESENT_BUT_BINDING_TUPLE_MISMATCH"
            elif exact_raw > 0:
                diagnosis = "RAW_EVIDENCE_PRESENT_FOR_EXACT_WINDOW"
            elif target_all > 0:
                diagnosis = "TARGET_MAC_PRESENT_BUT_EXACT_WINDOW_MISSES_EVIDENCE"
            elif site_window_any > 0:
                diagnosis = "SITE_ACTIVE_BUT_TARGET_MAC_ABSENT_OR_DIFFERENT_MAC"
            elif site_evidence_total > 0:
                diagnosis = "SITE_HAS_EVIDENCE_BUT_CONTROLLED_WINDOW_IS_DATA_GAP"
            else:
                diagnosis = "SITE_HAS_NO_EVIDENCE_IN_FROZEN_TASK01_DB"
            print(f"DEVICE_{idx}_EVIDENCE_DIAGNOSIS={diagnosis}")

            if health_exact_total > 0 or health_anchor_total > 0:
                health_diag = "HEALTH_ROWS_EXIST_FOR_EXPECTED_SCOPES"
            elif site_health_total > 0:
                health_diag = "SITE_HEALTH_EXISTS_BUT_NOT_FOR_EXPECTED_SCOPES_OR_TIME"
            else:
                health_diag = "SITE_HAS_NO_HEALTH_ROWS_IN_FROZEN_TASK01_DB"
            print(f"DEVICE_{idx}_HEALTH_DIAGNOSIS={health_diag}")

        after = sha256(TASK01_DB)
        print(f"TASK01_SHA256_AFTER={after}")
        print(f"FORMAL_INPUT_UNCHANGED={'YES' if after == before == EXPECTED_TASK01_SHA else 'NO'}")
        print("CLASSIFICATION_EXECUTION=NO")
        print("CLASSIFICATION_RESULT_PERSISTED=NO")
        print("T09_FORMAL_RERUN=NO")
        print("PRODUCTION_ACTION=NO")
        print("DIAGNOSTIC_STATUS=PASS")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
