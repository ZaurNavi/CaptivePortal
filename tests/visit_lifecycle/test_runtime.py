from __future__ import annotations

import logging

from app.visit_lifecycle import create_visit_lifecycle


def test_disabled_runtime_creates_no_database(tmp_path):
    db_path = tmp_path / "visits.sqlite3"
    runtime = create_visit_lifecycle(
        {
            "visit_lifecycle_enabled": False,
            "visit_lifecycle_db_path": str(db_path),
        },
        logger=logging.getLogger("test.runtime"),
    )
    assert runtime.state == "disabled"
    assert runtime.start_submitter.submit_authorized(None).status == "disabled"
    assert not db_path.exists()


def test_invalid_enabled_runtime_is_fail_open_unavailable(tmp_path):
    runtime = create_visit_lifecycle(
        {
            "visit_lifecycle_enabled": True,
            "visit_lifecycle_db_path": "relative.sqlite3",
        },
        logger=logging.getLogger("test.runtime"),
    )
    assert runtime.state == "unavailable"
    assert runtime.start_submitter.submit_authorized(None).status == "unavailable"


def test_enabled_runtime_starts_storage_without_finalization_reader(
    visit_config,
):
    runtime = create_visit_lifecycle(
        {
            "visit_lifecycle_enabled": True,
            "visit_lifecycle_db_path": visit_config.db_path,
            "visit_lifecycle_webhook_source": visit_config.webhook_source,
        },
        logger=logging.getLogger("test.runtime"),
    )
    assert runtime.enabled is True
    assert runtime.state == "starting"
    assert runtime.read_service is not None
    assert not hasattr(runtime, "webhook_reader")
    runtime.stop_accepting()
    assert runtime.close() is True
