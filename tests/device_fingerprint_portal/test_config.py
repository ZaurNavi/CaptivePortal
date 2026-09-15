import pytest

from app.device_fingerprint_portal.config import (
    CAPTURE_SOURCE_ID, PRODUCER_ID, SITE_ID, portal_config_from_env,
)
from app.device_fingerprint_portal.models import PortalEvidenceConfigError


def test_disabled_is_fail_open_and_uses_frozen_defaults():
    config = portal_config_from_env({"DEVICE_FINGERPRINT_PORTAL_ENABLED": "false", "DEVICE_FINGERPRINT_PORTAL_SITE_ID": "bad"})
    assert not config.enabled
    assert (config.producer_id, config.capture_source_id, config.site_id) == (PRODUCER_ID, CAPTURE_SOURCE_ID, SITE_ID)


def test_enabled_exact_config_and_fixed_override_rejection():
    assert portal_config_from_env({"DEVICE_FINGERPRINT_PORTAL_ENABLED": "true"}).enabled
    with pytest.raises(PortalEvidenceConfigError):
        portal_config_from_env({"DEVICE_FINGERPRINT_PORTAL_ENABLED": "true", "DEVICE_FINGERPRINT_PORTAL_BATCH_SIZE": "51"})
