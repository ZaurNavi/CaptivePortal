"""Manual submit-only wrapper; never opens a store or falls back to an audit."""
from __future__ import annotations

import argparse
import json
import uuid

from app.artifact_identity import ArtifactIdentityError, capture_loaded_artifact_identity

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator.protocol import submit_request
from .audit_runner import STORE_ID


def main(argv=None):
    parser = argparse.ArgumentParser(description="Submit Fingerprint Evidence audit to the private coordinator")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--store-id", required=True, choices=[STORE_ID])
    parser.add_argument("--idempotency-key", default=None)
    args = parser.parse_args(argv)
    try:
        key = c.identifier(args.idempotency_key) if args.idempotency_key is not None else str(uuid.uuid4())
        try:
            capture_loaded_artifact_identity("fingerprint-evidence-audit-submit")
        except ArtifactIdentityError:
            print(json.dumps(dict(store_id=STORE_ID, status="coordinator_unavailable", category_code="artifact_identity_unavailable")))
            return 5
        result = submit_request(dict(op="submit", store_id=STORE_ID, idempotency_key=key, origin="manual"))
        print(json.dumps(result))
        return 0
    except c.CoordinatorError as error:
        code = error.code if error.code in {"store_busy", "queue_full", "invalid_request"} else "coordinator_unavailable"
        print(json.dumps(dict(store_id=STORE_ID, status=code, category_code=code)))
        return 2 if code != "coordinator_unavailable" else 5
    except Exception:
        print(json.dumps(dict(store_id=STORE_ID, status="coordinator_unavailable", category_code="coordinator_unavailable")))
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
