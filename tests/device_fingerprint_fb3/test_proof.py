"""Real Task-01 cleanup boundary proof at two configured retention lengths."""

from datetime import timedelta

import pytest

from app.device_fingerprint.validation import parse_utc
from research.device_fingerprint_fb3.proof import run_f_b3_proof


@pytest.mark.parametrize("days", [30, 90])
def test_repository_retains_exact_predecessor_and_deletes_older_rows(tmp_path, days):
    report = run_f_b3_proof(tmp_path, evidence_retention_days=days)
    assert report["derived_health_anchor_margin_seconds"] == 600
    assert report["max_family_freshness_seconds"] == 600
    assert report["clock_uncertainty_seconds"] == 0
    assert report["evidence_retention_days"] == days
    assert report["evidence_retention_seconds"] == days * 86_400
    assert report["source_health_retention_seconds"] == days * 86_400 + 600
    assert parse_utc(report["evidence_cutoff"]) - parse_utc(report["health_cutoff"]) == (
        timedelta(seconds=600))
    assert report["oldest_evidence_retained"] is True
    assert report["required_predecessor_retained"] is True
    assert report["older_health_row_deleted"] is True
    assert report["older_evidence_row_deleted"] is True
    assert report["cleanup_parses_binding_timeline"] is False
    assert report["activation_600_with_600"] is True
    assert report["activation_601_with_600"] is False
