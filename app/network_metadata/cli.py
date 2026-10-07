"""Authorized auxiliary entrypoint only: python3 -m app.network_metadata.cli run."""
import argparse
import signal
import sys
from app.artifact_identity import capture_loaded_artifact_identity
from .config import network_metadata_config_from_env
from .health import FingerprintCaptureHealthAdapterV1
from .models import NetworkMetadataConfigError
from .repository import NetworkMetadataRepository, WriterLock
from .service import NetworkMetadataService
from .telemetry import configure_logger


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run",))
    parser.parse_args(argv)
    try:
        config = network_metadata_config_from_env()
    except NetworkMetadataConfigError:
        print("Invalid network metadata configuration", file=sys.stderr)
        return 2
    if not config.enabled:
        return 0
    repository = None
    handlers = {}
    try:
        telemetry = configure_logger()
        identity = capture_loaded_artifact_identity("network-metadata.service")
        with WriterLock(config.writer_lock_path):
            repository = NetworkMetadataRepository(config, telemetry=telemetry)
            service = NetworkMetadataService(config, repository, identity, FingerprintCaptureHealthAdapterV1())
            for signum in (signal.SIGINT, signal.SIGTERM):
                handlers[signum] = signal.signal(signum, lambda *_: service.stop())
            service.run_forever()
        return 0
    except Exception:
        print("Network metadata service unavailable", file=sys.stderr)
        return 1
    finally:
        if repository is not None:
            repository.close()
        for signum, handler in handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
