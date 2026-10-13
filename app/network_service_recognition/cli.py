"""Independent opt-in NI-04 process. Never imported by Portal startup."""
import argparse
import signal
from .materialization_config import materialization_config_from_env


def main(argv=None):
    parser=argparse.ArgumentParser(description='NI-04 background Service Intelligence')
    parser.add_argument('command',choices=('run',))
    parser.parse_args(argv)
    repo=None
    try:
        config=materialization_config_from_env()
        if config.mode=='off':return 0
        from .source_adapter import WorkerSourceReadService
        from app.network_metadata_projection.service_delivery_read_service import ServiceRecognitionDeliveryReadService
        from .artifacts import load_local_bundle
        from .materialization_repository import ServiceMaterializationRepository
        from .worker import ServiceMaterializationWorker
        repo=ServiceMaterializationRepository(config.db_path,max_db_bytes=config.max_db_bytes)
        service=ServiceMaterializationWorker(repo,
            ServiceRecognitionDeliveryReadService(config.projection_db_path,idle_write_reduction_enabled=config.projection_idle_write_reduction_enabled),
            WorkerSourceReadService(config.source_db_path),load_local_bundle())
        for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:service.stop())
        service.run()
        return 0
    except Exception:
        print('network_service_materialization_unavailable')
        return 1
    finally:
        if repo is not None:repo.close()


if __name__=='__main__':raise SystemExit(main())
