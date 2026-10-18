"""Frozen Issue #227 structural topology; no live flow evidence is implied."""
from collections import Counter
from dataclasses import FrozenInstanceError
import builtins
import json
import socket
import sqlite3

import pytest

from app.admin_web import operations_inventory as inventory, operations_service as ops
from tests.admin_web.test_operations_inventory import resolved
from tests.admin_web.test_operations_service import NOW, regular, systemd_text

TRIPLES = """
src:guest_http feeds svc:portal_core
src:omada_controller feeds svc:portal_core
src:visit_webhook_journal feeds svc:portal_core
src:passive_capture feeds svc:fingerprint_sensor
src:passive_capture feeds svc:fingerprint_suricata
svc:fingerprint_suricata feeds svc:fingerprint_sensor
svc:fingerprint_suricata feeds svc:network_metadata
svc:fingerprint_sensor feeds svc:fingerprint_evidence
svc:portal_core writes_to db:portal_counter
svc:portal_core writes_to db:public_traffic
svc:portal_core writes_to db:visitor_registry
svc:portal_core writes_to db:visits
svc:portal_core writes_to db:observations
svc:portal_core writes_to db:current_state
svc:portal_core writes_to db:settings
svc:portal_core writes_to db:fingerprint_integration
svc:traffic_projection writes_to db:traffic_projection
svc:fingerprint_evidence writes_to db:fingerprint_evidence
svc:fingerprint_classification writes_to db:fingerprint_classification
svc:fingerprint_classification writes_to db:fingerprint_integration
svc:fingerprint_sensor writes_to db:network_attribution
svc:fingerprint_sensor writes_to db:sensor_spool
svc:network_metadata writes_to db:network_metadata
svc:network_metadata_projection writes_to db:network_metadata_projection
svc:network_service_recognition writes_to db:network_service_intelligence
db:observations read_by svc:traffic_projection
db:network_metadata read_by svc:network_metadata_projection
db:network_attribution read_by svc:network_metadata_projection
db:visitor_registry read_by svc:network_metadata_projection
db:network_metadata_projection read_by svc:network_service_recognition
db:network_metadata read_by svc:network_service_recognition
db:fingerprint_integration read_by svc:fingerprint_classification
db:fingerprint_evidence read_by svc:fingerprint_classification
db:fingerprint_control_plane read_by svc:fingerprint_classification
db:visitor_registry read_by svc:fingerprint_classification
db:visits read_by svc:fingerprint_classification
db:visits read_by consumer:admin_read_models
db:observations read_by consumer:admin_read_models
db:visitor_registry read_by consumer:admin_read_models
db:current_state read_by consumer:admin_read_models
db:fingerprint_classification read_by consumer:admin_read_models
db:fingerprint_evidence read_by consumer:admin_read_models
db:network_metadata_projection read_by consumer:admin_read_models
db:network_service_intelligence read_by consumer:admin_read_models
db:traffic_projection read_by consumer:admin_read_models
""".strip().splitlines()

GROUPS = {
    'portal_guest': ('src:guest_http','src:omada_controller','src:visit_webhook_journal','svc:portal_core',
        'db:portal_counter','db:public_traffic','db:visitor_registry','db:visits','db:observations',
        'db:current_state','db:settings','consumer:admin_read_models'),
    'fingerprint': ('src:passive_capture','svc:fingerprint_evidence','svc:fingerprint_sensor',
        'svc:fingerprint_suricata','svc:fingerprint_classification','db:fingerprint_evidence',
        'db:fingerprint_classification','db:fingerprint_control_plane','db:fingerprint_integration',
        'db:network_attribution','db:sensor_spool'),
    'network_intelligence': ('svc:network_metadata','svc:network_metadata_projection',
        'svc:network_service_recognition','db:network_metadata','db:network_metadata_projection',
        'db:network_service_intelligence'),
    'traffic_analytics': ('svc:traffic_projection','db:traffic_projection'),
}


def test_exact_31_node_order_types_groups_labels_and_catalog_references():
    topology = inventory.topology_snapshot()
    assert set(topology) == {'contract_version','scope','mode','nodes','edges'}
    assert topology['contract_version'] == 'admin.operations.topology.v1'
    assert topology['scope'] == 'global' and topology['mode'] == 'structural_only'
    nodes = topology['nodes']
    expected = ['src:guest_http','src:omada_controller','src:visit_webhook_journal','src:passive_capture']
    expected += ['svc:'+item.id for item in inventory.SERVICES]
    expected += ['db:'+item.id for item in inventory.STORES] + ['consumer:admin_read_models']
    assert [node['id'] for node in nodes] == expected
    assert len(nodes) == len(set(expected)) == 31
    assert Counter(node['node_type'] for node in nodes) == dict(source=4,service=9,database=17,consumer=1)
    for node in nodes:
        assert set(node) == {'id','node_type','label','catalog_ref','group'}
        assert node['id'] in GROUPS[node['group']]
        if node['node_type'] in {'source','consumer'}: assert node['catalog_ref'] is None
        else:
            catalog = inventory.SERVICES if node['node_type'] == 'service' else inventory.STORES
            item = next(item for item in catalog if item.id == node['catalog_ref'])
            assert node['label'] == item.label


@pytest.mark.parametrize('index,triple', list(enumerate(TRIPLES)), ids=[str(i+1) for i in range(45)])
def test_exact_45_ordered_edge_triples_without_runtime_fields(index,triple):
    topology = inventory.topology_snapshot()
    source, relation, target = triple.split()
    edge = topology['edges'][index]
    assert edge == dict(id=f'e:{source}:{relation}:{target}',from_node_id=source,to_node_id=target,
        relation=relation,flow_evidence='not_instrumented')
    assert source in {node['id'] for node in topology['nodes']}
    assert target in {node['id'] for node in topology['nodes']}


def test_catalog_closed_bounds_pure_projection_and_immutable_records(monkeypatch):
    def forbidden(*args,**kwargs): raise AssertionError('unexpected acquisition')
    with monkeypatch.context() as scoped:
        scoped.setattr(sqlite3,'connect',forbidden)
        scoped.setattr(socket,'socket',forbidden)
        scoped.setattr(ops.os,'lstat',forbidden)
        scoped.setattr(ops.subprocess,'Popen',forbidden)
        scoped.setattr(ops.threading,'Thread',forbidden)
        scoped.setattr(builtins,'open',forbidden)
        graph = inventory.topology_snapshot()
    edges = graph['edges']
    assert len(edges) == len({edge['id'] for edge in edges}) == 45
    assert Counter(edge['relation'] for edge in edges) == dict(feeds=8,writes_to=17,read_by=20)
    assert sum(edge['to_node_id'].startswith('consumer:') for edge in edges) == 9
    assert not any(edge['relation']=='writes_to' and edge['to_node_id']=='db:fingerprint_control_plane' for edge in edges)
    with pytest.raises(FrozenInstanceError): inventory.TOPOLOGY_EDGES[0].relation = 'active'
    with pytest.raises(FrozenInstanceError): inventory.TOPOLOGY_SOURCES[0].group = 'unknown'
    graph['edges'].clear(); graph['nodes'][0]['label'] = 'mutated response'
    assert len(inventory.topology_snapshot()['edges']) == 45
    assert inventory.topology_snapshot()['nodes'][0]['label'] == 'Guest Portal / Auth'


def test_reader_metadata_exact_source_backed_eleven_and_no_consumer():
    expected = {
        'observations':('traffic_projection',),
        'network_metadata':('network_metadata_projection','network_service_recognition'),
        'network_attribution':('network_metadata_projection',),
        'visitor_registry':('network_metadata_projection','fingerprint_classification'),
        'network_metadata_projection':('network_service_recognition',),
        'fingerprint_integration':('fingerprint_classification',),
        'fingerprint_evidence':('fingerprint_classification',),
        'fingerprint_control_plane':('fingerprint_classification',),
        'visits':('fingerprint_classification',),
    }
    assert sum(len(item.readers) for item in inventory.STORES) == 11
    assert {item.id:item.readers for item in inventory.STORES} == {item.id:expected.get(item.id,()) for item in inventory.STORES}


@pytest.mark.parametrize('partial',[False,True])
def test_full_topology_same_snapshot_48k_bound_and_zero_extra_acquisition(partial):
    calls = dict(systemd=0,lstat=0)
    def acquire(cancel):
        calls['systemd'] += 1
        if partial: raise OSError('PRIVATE_CANARY')
        return systemd_text()
    def lstat(path): calls['lstat'] += 1; return regular(path)
    subject = ops.AdminOperationsReadService(resolved(),acquire=acquire,lstat=lstat,now=lambda:NOW)
    try:
        first = subject.read('topology-1')
        counts = calls.copy()
        second = subject.read('topology-2')
        assert calls == counts == dict(systemd=1,lstat=51)
        assert first['topology'] == second['topology'] == inventory.topology_snapshot()
        assert len(first['services']) == 9 and len(first['databases']) == 17
        assert first['snapshot_state'] == ('partial' if partial else 'complete')
        raw = json.dumps(first,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
        assert len(raw) <= ops.RESPONSE_LIMIT == 48000
        assert b'PRIVATE_CANARY' not in raw and b'/opt/' not in raw
        assert first['summary'] == ops.summarize(first['services'],first['databases'])
    finally: subject.close()
