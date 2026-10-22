"""Read-only public-traffic schema2 T3 bridge; never calls migrate/reset."""
import ast
from datetime import date
from functools import lru_cache
import hashlib
import inspect
import sqlite3
import textwrap

from . import contracts as c
from .live_policy import require


def signature(db):
    return tuple(tuple(row) for row in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"))


@lru_cache(maxsize=1)
def expected_signature():
    # Consume the ONE canonical owner DDL literal, not a second schema/migration.
    from app.public_traffic.repository import PublicTrafficRepository
    tree = ast.parse(textwrap.dedent(inspect.getsource(PublicTrafficRepository.migrate)))
    values = [node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == 'executescript'
        and len(node.args) == 1 and isinstance(node.args[0], ast.Constant) and type(node.args[0].value) is str]
    require(len(values)==1)
    db=sqlite3.connect(':memory:')
    try:
        db.executescript(values[0]); return signature(db)
    finally: db.close()


def validate(db, guard, *, check=lambda _:None):
    from app.public_traffic.repository import SCHEMA_VERSION, _strict_db_integer, _safe_add
    check('sqlite_user_version')
    require(db.execute('PRAGMA user_version').fetchone()[0]==SCHEMA_VERSION)
    check('pt_schema_signature')
    require(signature(db)==expected_signature())
    check('pt_counter_singleton')
    rows=list(db.execute('SELECT * FROM counter_state'))
    require(len(rows)==1 and rows[0]['singleton_id']==1 and type(rows[0]['initial_backfill_completed']) is int
        and rows[0]['initial_backfill_completed'] in {0,1})
    totals={}; count=0; watermark=hashlib.sha256()
    for row in db.execute('SELECT * FROM traffic_daily ORDER BY ssid,local_date'):
        guard();check('pt_traffic_daily_date')
        require(date.fromisoformat(row['local_date']).isoformat()==row['local_date'])
        check('pt_traffic_daily_numeric')
        require(type(row['ssid']) is str)
        pair=totals.get(row['ssid'],(0,0))
        totals[row['ssid']]=(_safe_add(pair[0],_strict_db_integer(row['traffic_bytes'])),
            _safe_add(pair[1],_strict_db_integer(row['completed_sessions'])))
        check('pt_watermark_encode');watermark.update(c.encode(tuple(row))); count+=1
    for row in db.execute('SELECT * FROM processed_events ORDER BY normalized_event_id'):
        guard();check('pt_event_type')
        require(type(row['counted']) is int and row['counted'] in {0,1})
        require(row['event_type']=='omada.client_offline')
        check('pt_event_offset_order')
        start=_strict_db_integer(row['source_offset_start']); end=_strict_db_integer(row['source_offset_end'])
        require(start<=end)
        if row['counted']:
            check('pt_event_counted_fields')
            require(row['ssid'] is not None and row['event_local_date'] is not None and row['skip_reason'] is None)
            check('pt_event_event_date')
            require(date.fromisoformat(row['event_local_date']).isoformat()==row['event_local_date'])
            _strict_db_integer(row['event_traffic_bytes'])
        check('pt_watermark_encode');watermark.update(c.encode(tuple(row))); count+=1
    for row in db.execute('SELECT * FROM reader_state ORDER BY source_identity'):
        guard();check('pt_reader_offset');_strict_db_integer(row['source_offset'])
        if row['last_observed_size'] is not None: _strict_db_integer(row['last_observed_size'])
        for field in ('retired_completed','missing_warning_emitted'):
            check('pt_reader_flags')
            require(type(row[field]) is int and row[field] in {0,1})
        check('pt_watermark_encode');watermark.update(c.encode(tuple(row))); count+=1
    for row in db.execute('SELECT * FROM counter_resets ORDER BY reset_id'):
        guard();check('pt_reset_scope');c.identifier(row['reset_id']);require(row['reset_scope'] in {'ssid','all'})
        for field in ('previous_today_bytes','previous_total_bytes','previous_sessions_today','previous_sessions_total','affected_ssids'):
            check('pt_reset_numeric')
            if row[field] is not None: _strict_db_integer(row[field])
        check('pt_watermark_encode');watermark.update(c.encode(tuple(row))); count+=1
    # Reset semantics mean historical processed events must NOT be re-summed
    # into current totals; that would reject legitimate owner-authorized resets.
    check('pt_watermark_encode')
    return 'pinned_file_instance', hashlib.sha256(c.encode(('public_traffic',SCHEMA_VERSION,signature(db)))).hexdigest(), watermark.hexdigest()
