from __future__ import annotations

import logging

import pytest

from app.visit_lifecycle import (
    VisitStartOutcome,
    VisitStorageCategory,
    VisitStorageError,
    VisitTelemetry,
)
from app.visit_lifecycle.start_sink import LocalVisitStartSubmitter

from .conftest import make_request


class ServiceStub:
    def __init__(self, error=None):
        self.error = error

    def submit_authorized(self, request):
        if self.error is not None:
            raise self.error
        return VisitStartOutcome(status="opened", visit_id="visit")


@pytest.mark.parametrize(
    "category",
    [
        VisitStorageCategory.BUSY,
        VisitStorageCategory.FULL,
        VisitStorageCategory.CORRUPT,
        VisitStorageCategory.IO_ERROR,
    ],
)
def test_storage_failure_is_safe_outcome(category):
    sink = LocalVisitStartSubmitter(
        ServiceStub(VisitStorageError(category)),
        VisitTelemetry(logging.getLogger("test.start_sink")),
    )
    outcome = sink.submit_authorized(make_request())
    assert outcome.status == "unavailable"
    assert outcome.storage_category == category.value


def test_stop_accepting_rejects_new_calls_without_queueing():
    sink = LocalVisitStartSubmitter(
        ServiceStub(),
        VisitTelemetry(logging.getLogger("test.start_sink")),
    )
    sink.stop_accepting()
    assert sink.submit_authorized(make_request()).status == "shutting_down"
    assert sink.wait_for_idle(0) is True
