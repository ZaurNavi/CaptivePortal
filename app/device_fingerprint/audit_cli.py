"""Explicit manual RAM audit; no timer, HTTP entrypoint or startup import."""
from __future__ import annotations

import argparse
import json
import signal
import threading

from app.artifact_identity import ArtifactIdentityError, capture_loaded_artifact_identity

from .audit_runner import EvidenceAuditor, STORE_ID
from .config import device_fingerprint_config_from_settings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manual Fingerprint Evidence RAM snapshot audit")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--store-id", required=True, choices=[STORE_ID])
    parser.parse_args(argv)
    canceled = threading.Event()
    previous = {}
    try:
        try:
            identity = capture_loaded_artifact_identity("fingerprint-evidence-manual-audit")
        except ArtifactIdentityError:
            print(json.dumps({"store_id":STORE_ID, "status":"incomplete", "category_code":"artifact_identity_unavailable"}))
            return 5
        from app.settings import get_settings
        config = device_fingerprint_config_from_settings(get_settings())
        for kind in (signal.SIGINT, signal.SIGTERM):
            previous[kind] = signal.signal(kind, lambda _kind, _frame: canceled.set())
        record, code = EvidenceAuditor(config.db_path, canceled=canceled.is_set, source_commit=identity.artifact_sha).run()
        # Full operator record is protected on disk, never print source data.
        print(json.dumps({"store_id":STORE_ID, "status":record["status"], "category_code":record["category_code"]}))
        return code
    except Exception:
        print(json.dumps({"store_id":STORE_ID, "status":"incomplete", "category_code":"configuration_unavailable"}))
        return 5
    finally:
        for kind, handler in previous.items(): signal.signal(kind, handler)


if __name__ == "__main__":
    raise SystemExit(main())
