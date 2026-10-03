"""Task-05 relation/orchestration boundary; import creates no runtime."""

from .submitter import (
    DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER, FingerprintIntegrationSubmitter,
)

__all__ = ["DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER", "FingerprintIntegrationSubmitter"]
