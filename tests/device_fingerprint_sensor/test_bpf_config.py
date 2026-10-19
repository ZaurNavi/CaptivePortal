"""Issue 244: one strict scope parser, immutable wiring, byte-exact grammar."""
import ipaddress
import itertools
from pathlib import Path

import pytest

from app.device_fingerprint_sensor.config import parse_guest_cidrs, sensor_config_from_env
from app.device_fingerprint_sensor.capture_filter import RAW_CAPTURE_FILTER, render_raw_capture_filter, verify_filter_bytes
from app.device_fingerprint_sensor.models import SensorError

OLD = '192.168.8.0/22'
NEW = '10.50.0.0/19'


@pytest.mark.parametrize('scope',[OLD,NEW,'203.0.113.0/24','10.0.0.0/8','0.0.0.0/1'])
def test_single_scope_exact_fixed_grammar_and_no_private_substitution(scope):
    value=render_raw_capture_filter(parse_guest_cidrs(scope))
    assert value == '(udp and (port 67 or port 68)) or (src net '+scope+' and tcp[tcpflags] & (tcp-syn|tcp-ack) == tcp-syn)'
    assert value.isascii() and '\n' not in value


def test_legacy_default_and_tracked_sample_bytes_unchanged():
    config=sensor_config_from_env({'DEVICE_FINGERPRINT_SENSOR_ENABLED':'true'})
    assert render_raw_capture_filter(config.guest_cidrs)==RAW_CAPTURE_FILTER
    assert (Path(__file__).parents[2]/'deploy/device-fingerprint/raw-capture.bpf').read_bytes()==RAW_CAPTURE_FILTER.encode()+b'\n'


@pytest.mark.parametrize('raw',['', ' ', '0.0.0.0/0', '::/64','192.168.8.1/22','10.50.0.0/255.255.224.0',
    '10.50.0.0/19 ', ' 10.50.0.0/19', OLD+', '+NEW, OLD+','+OLD, '10.0.0.0/8,10.50.0.0/19',
    NEW+',', NEW+' or ip', NEW+'\n', '010.50.0.0/19', '10.50.0.0', '1'*1025, None, 123])
def test_bad_csv_is_rejected_by_both_startup_and_offline_parser(raw):
    with pytest.raises(SensorError):parse_guest_cidrs(raw)
    with pytest.raises(SensorError):sensor_config_from_env({'DEVICE_FINGERPRINT_SENSOR_ENABLED':'true',
        'DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS':raw})


@pytest.mark.parametrize('scope',[None, [], (), (NEW,), (True,), (ipaddress.IPv6Network('::/64'),),
    (ipaddress.IPv4Network('0.0.0.0/0'),), parse_guest_cidrs(NEW)*2])
def test_renderer_does_not_trust_typed_tuple_callers(scope):
    with pytest.raises(SensorError):render_raw_capture_filter(scope)


def test_mutated_ipv4_object_and_subclass_are_not_typed_authority():
    class Network(ipaddress.IPv4Network):pass
    with pytest.raises(SensorError):render_raw_capture_filter((Network(NEW),))
    changed=ipaddress.IPv4Network(NEW);changed.network_address=ipaddress.IPv4Address('10.50.0.1')
    with pytest.raises(SensorError):render_raw_capture_filter((changed,))


def test_multi_scope_sort_is_stable_but_does_not_reorder_input_configuration():
    values=(OLD,NEW,'203.0.113.0/24')
    expressions=set()
    for order in itertools.permutations(values):
        networks=parse_guest_cidrs(','.join(order));original=tuple(map(str,networks))
        expressions.add(render_raw_capture_filter(networks))
        assert tuple(map(str,networks))==original
    assert expressions=={'(udp and (port 67 or port 68)) or ((src net 10.50.0.0/19 or src net 192.168.8.0/22 or src net 203.0.113.0/24) and tcp[tcpflags] & (tcp-syn|tcp-ack) == tcp-syn)'}


def test_sixteen_disjoint_networks_are_exact_and_seventeen_denied():
    values=[f'10.{value}.0.0/16' for value in range(17)]
    first=parse_guest_cidrs(','.join(values[:16]));rendered=render_raw_capture_filter(tuple(reversed(first)))
    assert rendered.count('src net ')==16 and '10.16.0.0/16' not in rendered
    assert rendered==render_raw_capture_filter(first)
    with pytest.raises(SensorError):parse_guest_cidrs(','.join(values))
    with pytest.raises(SensorError):render_raw_capture_filter(tuple(ipaddress.IPv4Network(v) for v in values))


@pytest.mark.parametrize('suffix',[b'',b'\n'])
def test_exact_optional_single_lf_only(suffix):
    networks=parse_guest_cidrs(NEW);expected=render_raw_capture_filter(networks)
    assert verify_filter_bytes(expected.encode()+suffix,networks)==expected


@pytest.mark.parametrize('mutate',[lambda x:b' '+x,lambda x:x+b' ',lambda x:x+b'\r\n',lambda x:x+b'\n\n',
    lambda x:b'\xef\xbb\xbf'+x,lambda x:x+b'\xff',lambda x:x.replace(b'src net',b'dst net'),
    lambda x:x.replace(b'10.50.0.0/19',b'0.0.0.0/0'),lambda x:RAW_CAPTURE_FILTER.encode()])
def test_artifact_not_normalized_or_broadened(mutate):
    networks=parse_guest_cidrs(NEW)
    with pytest.raises(SensorError):verify_filter_bytes(mutate(render_raw_capture_filter(networks).encode()),networks)


def test_runtime_passes_same_tuple_and_respects_even_falsey_injected_capture(monkeypatch):
    from app.device_fingerprint_sensor import runtime as module
    from tests.device_fingerprint_sensor.test_runtime import Log,Spool,Eve,Producer
    from app.device_fingerprint_sensor.telemetry import SensorTelemetry
    config=sensor_config_from_env({'DEVICE_FINGERPRINT_SENSOR_ENABLED':'true','DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS':NEW})
    calls=[]
    monkeypatch.setattr(module,'RawCapture',lambda nic,nets:calls.append((nic,nets)) or object())
    module.SensorRuntime(config,telemetry=SensorTelemetry(Log()),spool=Spool(),eve=Eve(),producer=Producer())
    assert calls[0][1] is config.guest_cidrs
    class FalseCapture:
        def __bool__(self):return False
    capture=FalseCapture()
    assert module.SensorRuntime(config,telemetry=SensorTelemetry(Log()),capture=capture,spool=Spool(),eve=Eve(),producer=Producer()).capture is capture
    assert len(calls)==1


def test_socket_retries_never_reread_env_or_change_resolved_scope(monkeypatch):
    from app.device_fingerprint_sensor import capture as module
    config=sensor_config_from_env({'DEVICE_FINGERPRINT_SENSOR_ENABLED':'true','DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS':NEW})
    monkeypatch.setenv('DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS',OLD)
    seen=[]
    monkeypatch.setattr(module,'load_deployed_filter',lambda nets:seen.append(nets) or render_raw_capture_filter(nets))
    monkeypatch.setattr(module,'attach_frozen_filter',lambda sock,nets:seen.append(nets))
    monkeypatch.setattr(module.socket,'AF_PACKET',17,raising=False)
    class Socket:
        def settimeout(self,*a):pass
        def setsockopt(self,*a):pass
        def bind(self,*a):pass
        def close(self):pass
    capture=module.RawCapture(config.interface,config.guest_cidrs,socket_factory=lambda *a:Socket())
    for _ in range(2):capture.open();capture.close()
    assert seen and all(nets is config.guest_cidrs for nets in seen)


def test_enabled_parser_reads_scope_once_and_disabled_path_ignores_bad_scope():
    class Environment(dict):
        reads = 0
        def get(self, key, *default):
            if key == 'DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS': self.reads += 1
            return super().get(key, *default)
    enabled = Environment(DEVICE_FINGERPRINT_SENSOR_ENABLED='true', DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS=NEW)
    assert str(sensor_config_from_env(enabled).guest_cidrs[0]) == NEW
    assert enabled.reads == 1
    disabled = Environment(DEVICE_FINGERPRINT_SENSOR_ENABLED='false', DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS='bad or ip')
    config = sensor_config_from_env(disabled)
    assert not config.enabled and str(config.guest_cidrs[0]) == OLD and disabled.reads == 0
