"""WP3 source-native health: no DB/Controller/host probes."""
import copy
import threading
from types import SimpleNamespace

import pytest

from app.operations_health import SENSOR_UNIT, NI02_UNIT, DEPENDENCIES, sensor_health, ni02_health, validate
from app.device_fingerprint_sensor import operations_metadata as metadata
from tests.device_fingerprint_sensor.test_operations_metadata import report, encoded


def dependencies(unit=SENSOR_UNIT, **changes):
    return dict.fromkeys(DEPENDENCIES[unit], True) | changes


@pytest.mark.parametrize("native,expected", [("ready","healthy"),("degraded","degraded"),
    ("unavailable","unavailable"),("initializing","unknown"),("stopping","unknown"),("PRIVATE","unknown")])
def test_native_sensor_state_not_process_or_file_presence(native,expected):
    value = sensor_health(native, dependencies())
    assert value['state'] == expected and 'PRIVATE' not in str(value)


@pytest.mark.parametrize("missing", sorted(DEPENDENCIES[SENSOR_UNIT]))
def test_ready_without_each_required_dependency_is_not_healthy(missing):
    assert sensor_health('ready',dependencies(**{missing:False}))['state'] == 'unknown'


@pytest.mark.parametrize("fault", ['extra','missing','bool_type','unknown_reason','green_missing_dependency','state','private_payload'])
def test_health_closed_allowlist_rejects_invalid_claims(fault):
    value = sensor_health('ready',dependencies())
    if fault=='extra':value['extra']=1
    elif fault=='missing':del value['dependencies']['spool']
    elif fault=='bool_type':value['dependencies']['spool']=1
    elif fault=='unknown_reason':value['reason']='/private/IP_TOKEN_CANARY'
    elif fault=='green_missing_dependency':value['dependencies']['delivery']=False
    elif fault=='state':value['state']='RUNNING'
    else:value['dependencies']['client_mac']='02:00:00:00:00:01'
    with pytest.raises((ValueError,TypeError)):validate(value,SENSOR_UNIT)


def test_sensor_v2_explicit_version_evolution_preserves_strict_v1():
    v1=report();health=sensor_health('degraded',dependencies(delivery=False))
    assert metadata.decode(encoded(v1)) == v1
    illegal=copy.deepcopy(v1);illegal['application_health']=health
    with pytest.raises(ValueError):metadata.decode(encoded(illegal))
    v2=copy.deepcopy(illegal);v2['schema_version']=metadata.SCHEMA_V2
    assert metadata.decode(encoded(v2)) == v2
    assert len(encoded(v2))<=4096
    v2['application_health']['state']='healthy'
    with pytest.raises(ValueError):metadata.decode(encoded(v2))


@pytest.mark.parametrize('native,pending,native_reason,attribution,expected,reason',[
    ('usable',0,None,True,'healthy','source_ready'),
    ('usable',None,None,True,'unknown','dependencies_unconfirmed'),
    # Accepted #324 / PR326: queued work alone is not degradation. Explicit
    # pending-only reason and all independent dependencies are still required.
    ('attribution_unavailable',2143,'pending_attribution',True,'healthy','source_ready'),
    ('attribution_unavailable',None,'pending_attribution',True,'unknown','dependencies_unconfirmed'),
    ('attribution_unavailable',2143,None,True,'unknown','dependencies_unconfirmed'),
    ('attribution_unavailable',None,'attribution_authority_unavailable',False,'degraded','source_degraded'),
    ('attribution_unavailable',2143,'attribution_authority_unavailable',False,'degraded','source_degraded'),
    ('source_unavailable',2143,None,True,'unavailable','source_unavailable'),
    ('blocked_conflict',0,None,True,'unavailable','blocked_conflict'),
    ('registry_degraded',0,None,True,'degraded','registry_degraded'),
    ('capacity_halted',0,None,True,'degraded','capacity_limited'),
    ('stopping',0,None,True,'unknown','source_stopping')])
def test_ni02_mapping_uses_precomputed_state_and_confirmed_pending(native,pending,native_reason,attribution,expected,reason):
    deps=dependencies(NI02_UNIT,pending=pending is not None,attribution=attribution)
    value=ni02_health(native,deps,pending,native_reason=native_reason)
    assert value['state']==expected and value['reason']==reason


@pytest.mark.parametrize('pending',[-1,True,1.5,2**53])
def test_ni02_pending_never_accepts_bool_invalid_or_out_of_bounds(pending):
    with pytest.raises(ValueError):ni02_health('attribution_unavailable',dependencies(NI02_UNIT),pending)


@pytest.mark.parametrize('fault',['none','preflight','raw','heartbeat','delivery','capacity','stop'])
def test_runtime_health_is_precomputed_no_extra_SQL_or_source_probe(fault):
    from app.device_fingerprint_sensor.runtime import SensorRuntime
    value=object.__new__(SensorRuntime)
    value.state='ready';value.reason=None;value.monotonic=lambda:100
    value._capture_preflight_passed=fault!='preflight'
    value._local_health={k:('available',None) for k in ('dhcp','tcp_syn','tls_client','quic_client')}
    if fault=='raw':value._local_health['dhcp']=('unavailable','raw_parser_unavailable')
    value._suricata_ready=True;value._suricata_last_heartbeat=1 if fault=='heartbeat' else 99
    value._delivery_available=fault!='delivery';value._delivery_permanent_fault=False
    value.producer=SimpleNamespace(permanent_fault=False)
    value.spool=SimpleNamespace(capacity_blocked=fault=='capacity')
    value.stop_event=threading.Event()
    if fault=='stop':value.stop_event.set()
    actual=value._operations_health()
    assert actual['state']==('healthy' if fault=='none' else 'unknown')
