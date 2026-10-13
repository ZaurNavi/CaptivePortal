"""Independent NI-04 deployment lane, default OFF; no product adoption authority."""
import os
from dataclasses import dataclass
from pathlib import Path,PurePosixPath
from .materialization_schema import MaterializationUnavailable


@dataclass(frozen=True,slots=True)
class MaterializationConfigV1:
    mode: str = "off"
    db_path: str = "/opt/CaptivePortal/data/network_service_intelligence.sqlite3"
    projection_db_path: str = "/opt/CaptivePortal/data/network_metadata_projection.sqlite3"
    source_db_path: str = "/opt/CaptivePortal/data/network_metadata.sqlite3"
    max_db_bytes: int = 512*1024*1024
    projection_idle_write_reduction_enabled: bool = False

    def __post_init__(self):
        if self.mode not in {"off","shadow","serve"} or type(self.projection_idle_write_reduction_enabled) is not bool or type(self.max_db_bytes) is not int or not 128*1024*1024<=self.max_db_bytes<=2*1024**3:
            raise MaterializationUnavailable()
        paths=(self.db_path,self.projection_db_path,self.source_db_path)
        if any(type(p) is not str or not (Path(p).is_absolute() or PurePosixPath(p).is_absolute()) for p in paths) or len({Path(p).resolve() for p in paths})!=3:
            raise MaterializationUnavailable()


def materialization_config_from_env(env=None):
    values=os.environ if env is None else env
    try:
        size=values.get("NETWORK_SERVICE_MATERIALIZATION_MAX_DB_BYTES","536870912")
        if not size.isascii() or not size.isdecimal() or str(int(size))!=size:raise ValueError
        from app.network_metadata_projection.config import idle_read_guard_from_env
        idle=idle_read_guard_from_env(values)
        return MaterializationConfigV1(values.get("NETWORK_SERVICE_MATERIALIZATION_MODE","off"),
            values.get("NETWORK_SERVICE_MATERIALIZATION_DB_PATH","/opt/CaptivePortal/data/network_service_intelligence.sqlite3"),
            values.get("NETWORK_METADATA_PROJECTION_DB_PATH","/opt/CaptivePortal/data/network_metadata_projection.sqlite3"),
            values.get("NETWORK_METADATA_DB_PATH","/opt/CaptivePortal/data/network_metadata.sqlite3"),int(size),idle)
    except Exception:
        raise MaterializationUnavailable() from None
