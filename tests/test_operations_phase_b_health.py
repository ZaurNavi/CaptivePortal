"""Phase B file transport inherits Phase A safety; local sources cannot spoof it."""
import os
from pathlib import Path

import pytest

from app import operations_app_health as transport
from app.operations_health import CLASSIFICATION_UNIT, TRAFFIC_UNIT, CORE_UNIT, SURICATA_UNIT, owner_health, validate_local
from tests.test_operations_app_health import TestChannel, NOW, _real_publisher
from app.device_fingerprint_sensor.operations_metadata import stamp


@pytest.mark.skipif(os.name != 'posix', reason='Linux/POSIX owner report openat contract')
@pytest.mark.parametrize('unit', [CLASSIFICATION_UNIT, TRAFFIC_UNIT])
def test_phase_b_owner_roundtrip_identity_and_unit_rejection(tmp_path, unit):
    publisher = _real_publisher(unit, tmp_path)
    health = owner_health(CLASSIFICATION_UNIT, 'ready') if unit == CLASSIFICATION_UNIT else dict(state='healthy', reason='source_ready')
    assert publisher.publish(health)
    value = transport.decode((tmp_path/transport.REPORT).read_bytes(), unit)
    identity = lambda pid, uid: dict(value['producer'], pid=pid)
    reader = transport.HealthReader(unit, channel=lambda unit: TestChannel(tmp_path), identity=identity, boottime=lambda:100_000_000_000)
    service = dict(operational_state='running', main_pid=os.getpid(), started_at_utc=stamp(NOW))
    assert reader.read(service, NOW, deadline=1, monotonic=lambda:0)['health'] == health
    other = TRAFFIC_UNIT if unit == CLASSIFICATION_UNIT else CLASSIFICATION_UNIT
    reader = transport.HealthReader(other, channel=lambda unit: TestChannel(tmp_path), identity=identity)
    assert reader.read(service, NOW, deadline=1, monotonic=lambda:0)['status'] == 'unknown'
    service['main_pid'] += 1
    assert transport.HealthReader(unit, channel=lambda unit: TestChannel(tmp_path), identity=identity).read(
        service, NOW, deadline=1, monotonic=lambda:0)['status'] == 'unknown'


@pytest.mark.parametrize('unit', [CORE_UNIT, SURICATA_UNIT])
def test_local_provenance_cannot_become_a_shared_uid_file_report(unit):
    with pytest.raises(ValueError):transport.HealthPublisher(unit)
    with pytest.raises(ValueError):transport.HealthReader(unit)


@pytest.mark.parametrize('unit,state,reason', [
    (CORE_UNIT,'healthy','source_ready'), (CORE_UNIT,'healthy','projection_rebuilding'),
    (SURICATA_UNIT,'healthy','core_composed'), (SURICATA_UNIT,'degraded','source_degraded'),
])
def test_local_state_reason_pairing_is_closed(unit, state, reason):
    with pytest.raises(ValueError):validate_local(dict(state=state, reason=reason), unit)


def test_ready_marker_is_bound_only_after_adopted_existing_composition():
    root = Path(__file__).resolve().parents[1]
    source = (root/'run.py').read_text(encoding='utf-8')
    assert source.count('bind_core_operations_snapshot(app, settings)') == 1
    assert source.index('app = create_app(**app_kwargs)') < source.index('    _configure_admin_web(app, settings,')
    assert source.index('settings_bootstrap.activation_service.adopt(') < source.index('bind_core_operations_snapshot(app, settings)')
    helper = (root/'app/operations_app_health.py').read_text(encoding='utf-8')
    assert 'os.mkdir(' not in helper and 'os.chmod(' not in helper and 'makedirs(' not in helper
