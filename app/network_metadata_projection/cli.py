"""Authorized independent composition root; never loaded by the Portal."""
import argparse
import os
import signal
from pathlib import Path
from app.artifact_identity import capture_loaded_artifact_identity
from app.network_metadata.projection_source import NetworkMetadataProjectionSourceReadService
from app.network_attribution.config import network_attribution_config_from_env
from app.network_attribution.read_service import NetworkAttributionReadService
from .config import projection_config_from_env
from .repository import ProjectionRepository
from .registry_adapter import RegistryAdapter
from .service import NetworkMetadataProjectionService
from .telemetry import ProjectionTelemetry


def main(argv=None):
    parser = argparse.ArgumentParser(description="Independent NI-02B projection worker")
    parser.add_argument("command", choices=("run",))
    parser.parse_args(argv)
    repo = None
    try:
        config = projection_config_from_env()
        if not config.enabled:
            return 0  # No DB, lock, upstream configuration/open, identity capture.
        attribution_config = network_attribution_config_from_env()
        if Path(config.db_path).resolve() == Path(attribution_config.db_path).resolve():
            raise ValueError
        identity = capture_loaded_artifact_identity("network-metadata-projection.service")
        repo = ProjectionRepository(config)
        service = NetworkMetadataProjectionService(config, repo,
            NetworkMetadataProjectionSourceReadService(config.source_db_path), NetworkAttributionReadService(attribution_config),
            RegistryAdapter(config.registry_db_path), identity, telemetry=ProjectionTelemetry())
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: service.stop())
        service.run()
        return 0
    except Exception:
        # No raw endpoints, Registry row, config dump, traceback or secrets.
        print("network_metadata_projection_unavailable")
        return 1
    finally:
        if repo is not None:
            repo.close()


if __name__ == "__main__":
    raise SystemExit(main())
