"""Independent opt-in NI-04 process. Never imported by Portal startup."""
import argparse
import signal
from .materialization_config import materialization_config_from_env


def main(argv=None):
    parser=argparse.ArgumentParser(description='NI-04 background Service Intelligence')
    parser.add_argument('command',choices=('run',))
    parser.add_argument('--visit-history-db',default=None,help='Explicit Owner-approved Visit consumer DB; default disabled')
    parser.add_argument('--visit-history-ttl-days',type=int,default=None,help='Owner-approved policy, 1..365; no implicit 30-day default')
    args=parser.parse_args(argv)
    repo=None
    try:
        config=materialization_config_from_env()
        if config.mode=='off':return 0
        if (args.visit_history_db is None)!=(args.visit_history_ttl_days is None) or args.visit_history_ttl_days is not None and not 1<=args.visit_history_ttl_days<=365:
            raise ValueError('Incomplete Visit history activation policy')
        from .source_adapter import WorkerSourceReadService
        from app.network_metadata_projection.service_delivery_read_service import ServiceRecognitionDeliveryReadService
        from .artifacts import load_local_bundle
        from .materialization_repository import ServiceMaterializationRepository
        from .worker import ServiceMaterializationWorker
        repo=ServiceMaterializationRepository(config.db_path,max_db_bytes=config.max_db_bytes,
            visit_delivery_db_path=args.visit_history_db,visit_delivery_ttl_days=args.visit_history_ttl_days)
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
