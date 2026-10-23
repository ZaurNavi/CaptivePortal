"""#296 canonical port: retain configured Sensor and truthful #315 hooks."""
from pathlib import Path
import sqlite3
import subprocess

import pytest

from app import operations_verification as checks
from app.network_service_recognition.materialization_repository import ServiceMaterializationRepository
from app.network_service_recognition.materialization_schema import MaterializationUnavailable
from app.visit_lifecycle.models import VisitSchemaError
from .conftest import visit_config
from app.visit_lifecycle.repository import VisitRepository

ROOT = Path(__file__).resolve().parents[2]
BASE = '2594c8753ed09a36fb8ded9b70e5966b23a4810d'


def test_configured_sensor_and_operations_sources_are_exact_canonical_bytes():
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE,
        'app/device_fingerprint_sensor/'], cwd=ROOT).decode().splitlines()
    assert paths and 'app/device_fingerprint_sensor/capture_filter.py' in paths
    paths += ['app/operations_verification.py', 'app/admin_web/operations_service.py',
        'app/admin_web/static/db_services.js', 'app/network_metadata_projection/schema.py',
        'app/network_metadata_projection/repository.py']
    for name in paths:
        expected = subprocess.check_output(['git', 'show', BASE + ':' + name], cwd=ROOT)
        assert ROOT.joinpath(name).read_bytes() == expected, name
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.joinpath('app/device_fingerprint_sensor').glob('*.py')}
    assert actual == {p for p in paths if p.startswith('app/device_fingerprint_sensor/') and p.endswith('.py')}


@pytest.mark.parametrize('store', ['visits', 'network_service_intelligence'])
def test_real_migrated_owners_report_current_checks_and_revoke_stale_pass(tmp_path, monkeypatch, visit_config, store):
    monkeypatch.setattr(checks, '_rows', {})
    monkeypatch.setattr(checks, '_paths', {})
    if store == 'visits':
        repo = VisitRepository(visit_config)
        expected_version, error = 6, VisitSchemaError
    else:
        repo = ServiceMaterializationRepository(str(tmp_path / 'ni04.sqlite3'))
        expected_version, error = 2, MaterializationUnavailable
    try:
        repo.initialize()
        with sqlite3.connect(repo.db_path) as c:
            assert c.execute('PRAGMA user_version').fetchone()[0] == expected_version
        row = checks.snapshot(checks.OWNERS[store])['checks'][store]
        assert row['status'] == 'passed' and row['scope'] == list(checks.ALLOWED[store])
        assert row['checked_store_id'] == checks.file_identity(repo.db_path)
        # A successful migration must not freeze a green Operations verdict.
        if hasattr(repo, 'close'):
            repo.close()  # Release the real NI04 sole-writer lease before restart.
        with sqlite3.connect(repo.db_path) as c:
            c.execute('CREATE TABLE unexpected_schema_canary(value)')
        with pytest.raises(error):
            repo.initialize()
        failed = checks.snapshot(checks.OWNERS[store])['checks'][store]
        assert failed['status'] == 'failed' and failed['scope'] == []
    finally:
        if hasattr(repo, 'close'):
            repo.close()
