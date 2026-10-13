"""Read-only operator evidence check; never authorizes or performs migration."""
import argparse
import json
import re
from pathlib import Path


def validate_preflight(value):
    keys = {"schema_version", "accepted_compatibility_bridge_sha", "declared_consumers",
            "consumer_commit_shas", "backup_verified", "backfill_running", "timeout_start_seconds"}
    if type(value) is not dict or set(value) != keys or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("invalid_preflight")
    bridge = value["accepted_compatibility_bridge_sha"]
    if type(bridge) is not str or re.fullmatch("[0-9a-f]{40}", bridge) is None:
        raise ValueError("invalid_preflight")
    if bridge == "b1442efc434716d35e21b9e3124c3b9cd2222fbe":
        raise ValueError("old_binary_not_rollback_compatible")
    consumers, reports = value["declared_consumers"], value["consumer_commit_shas"]
    if (type(consumers) is not list or not consumers or len(consumers) > 128
            or any(type(item) is not str or re.fullmatch("[a-z][a-z0-9_]{0,63}", item) is None for item in consumers)
            or len(set(consumers)) != len(consumers)
            or not {"captive_portal_admin", "network_metadata_projection"} <= set(consumers)
            or type(reports) is not dict or set(reports) != set(consumers)
            or any(type(sha) is not str or sha != bridge for sha in reports.values())):
        raise ValueError("consumer_bridge_rollout_incomplete")
    if (value["backup_verified"] is not True or value["backfill_running"] is not False
            or type(value["timeout_start_seconds"]) is not int or not 180 <= value["timeout_start_seconds"] <= 86400):
        raise ValueError("migration_operational_preconditions_incomplete")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check operator-supplied NI-04 migration preconditions; no DB access")
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        validate_preflight(json.loads(args.evidence.read_text(encoding="utf-8")))
    except Exception:
        print("NI04_MIGRATION_PREFLIGHT=HOLD")
        return 1
    print("NI04_MIGRATION_PREFLIGHT=INPUTS_VALIDATED / OWNER_AUTHORIZATION_STILL_REQUIRED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
