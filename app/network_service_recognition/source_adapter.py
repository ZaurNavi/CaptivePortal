"""Worker-only NI-01 adapter. Bounded availability verification, no source writes."""
import sqlite3
from pathlib import Path
from app.network_metadata.recognition_read_service import NetworkMetadataRecognitionReadService
from app.network_metadata.schema import validate_schema
from .models import ServiceUnavailable


class WorkerSourceReadService(NetworkMetadataRecognitionReadService):
    def verify_available(self, *, deadline):
        connection=None
        try:
            if not self.enabled:raise ServiceUnavailable()
            deadline.require_remaining()
            connection=sqlite3.connect(Path(self.db_path).resolve().as_uri()+'?mode=ro',uri=True,timeout=.5,isolation_level=None)
            connection.set_progress_handler(lambda:int(deadline.expired()),100)
            for pragma in ('query_only=ON','foreign_keys=ON','busy_timeout=500'):connection.execute('PRAGMA '+pragma)
            connection.execute('BEGIN')
            validate_schema(connection,writer=False)
            deadline.require_remaining()
            return True
        except Exception:raise ServiceUnavailable() from None
        finally:
            if connection is not None:connection.close()
