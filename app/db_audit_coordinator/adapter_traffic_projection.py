"""Historical Traffic read-only T3: reuse canonical schema and domain enums."""
import hashlib
import math
import sqlite3
from functools import lru_cache

from . import contracts as c
from .live_policy import require


def signature(db):
    return tuple(tuple(row) for row in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"))


@lru_cache(maxsize=1)
def expected_signature():
    from app.traffic_projection.repository import schema_sql
    db=sqlite3.connect(':memory:')
    try:db.executescript(schema_sql());return signature(db)
    finally:db.close()


def validate(db, guard):
    from app.traffic_projection.repository import TrafficProjectionRepository
    from app.traffic_projection.models import (PROJECTION_VERSION, SUPPORTED_SEMANTIC_CONTRACTS,
        VERSION_STATUSES, HEALTH_STATUSES, validate_projection_version)
    TrafficProjectionRepository._validate(db,deep=True)
    require(signature(db)==expected_signature())
    lineage=hashlib.sha256(); watermark=hashlib.sha256(); active=0
    for row in db.execute('SELECT * FROM traffic_projection_versions ORDER BY projection_version'):
        guard(); validate_projection_version(row['projection_version'])
        require(row['status'] in VERSION_STATUSES and row['projection_schema_version']==1
            and row['source']=='observations' and row['source_schema_version']==1
            and row['semantic_contract_sha256'] in SUPPORTED_SEMANTIC_CONTRACTS)
        active+=row['status']=='active'; lineage.update(c.encode(tuple(row)))
    require(active<=1)
    for table, order in (('traffic_projection_site_state','projection_version,site_id'),
            ('traffic_projection_cycles','projection_version,site_id,cycle_id'),
            ('traffic_projection_ap_cycles','projection_version,site_id,cycle_id,ap_mac')):
        for row in db.execute(f'SELECT * FROM {table} ORDER BY {order}'):
            guard()
            if table=='traffic_projection_site_state': require(row['status'] in HEALTH_STATUSES)
            for key in row.keys():
                if row[key] is None:continue
                if key.endswith('_mbps'):
                    require(type(row[key]) in {int,float} and math.isfinite(row[key]) and row[key]>=0)
                elif key.endswith('_count') or key in {'projection_revision','stored_row_count'}:
                    require(type(row[key]) is int and row[key]>=0)
            # SQLite integrity/FK checks enforce the original CHECK, lifecycle,
            # rates/counter constraints. No recomputation from live Observation.
            watermark.update(c.encode(tuple(row)))
    return 'native_lineage',lineage.hexdigest(),watermark.hexdigest()
