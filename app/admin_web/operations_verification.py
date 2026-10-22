"""Owner-check inputs consumed ONLY by the existing Operations sampler."""
import os
from app.operations_verification import PORTAL,SENSOR,NI02,snapshot,validate_checks
from app.operations_verification_report import Reader,UNITS


class OwnerChecks:
    def __init__(self,readers=None):
        self.readers={unit:Reader(unit) for unit in UNITS} if readers is None else dict(readers)

    def collect(self,services,sensor,ni02,now,*,deadline,monotonic,cancel):
        by_unit={row['unit']:row for row in services};sources={SENSOR:sensor,NI02:ni02}
        sources[PORTAL]=dict(status='fresh',checks=snapshot(PORTAL),producer={'pid':os.getpid()})
        for unit,reader in self.readers.items():
            try:sources[unit]=reader.read(by_unit[unit],now,deadline=deadline,monotonic=monotonic,cancel=cancel)
            except Exception:sources[unit]=dict(status='unknown')
        records={}
        for unit,source in sources.items():
            service=by_unit[unit]
            try:
                checks=validate_checks(source['checks'],unit,now)['checks']
                producer=source['producer']
                if producer['pid']!=service['main_pid'] or service['operational_state']!='running':continue
                start=service['started_at_utc']
                for db_id,row in checks.items():
                    if row['checked_at_utc'] is not None and (start is None or row['checked_at_utc']<start):continue
                    records[db_id]=dict(row=row,source_current=source.get('status')=='fresh',
                        expires=source.get('expires_boottime_ns'))
            except Exception:continue
        return records
