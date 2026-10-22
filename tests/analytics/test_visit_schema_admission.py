"""#296 narrow admission parity only; no Analytics metric/SQL changes."""
import sqlite3
from contextlib import contextmanager

import pytest

from app.analytics.source_gateway import compatible_source_schema_version, SOURCE_SCHEMA_VERSIONS
from app.analytics.runtime import _check_source


@pytest.mark.parametrize('version,accepted',[(1,False),(2,True),(3,True),(4,True),(5,False),(99,False)])
def test_visit_exact_version_admission_and_runtime_health_match(version,accepted):
    class Source:
        @contextmanager
        def analytics_read_connection(self):
            with sqlite3.connect(':memory:') as c:
                c.execute('PRAGMA user_version='+str(version));c.execute('PRAGMA query_only=ON')
                yield c
    assert compatible_source_schema_version('visits',version) is accepted
    health=_check_source('visits',Source())
    assert health.available is accepted and health.expected_schema_version==SOURCE_SCHEMA_VERSIONS['visits']
    assert type(health.expected_schema_version) is int and health.actual_schema_version==version


@pytest.mark.parametrize('source',['observations','registry'])
@pytest.mark.parametrize('version',[0,1,2,3,99,True])
def test_other_source_admission_remains_exact(source,version):
    assert compatible_source_schema_version(source,version) is (type(version) is int and version==1)
