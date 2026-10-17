"""Retained-origin diagnostics do not change the authoritative R14 result."""
from dataclasses import replace
import hashlib
import json
import shutil
import sqlite3
import time

import pytest

from app.admin_web.device_fingerprint_presentation import DeviceFingerprintPresentationService, present_classification
from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService
from app.device_fingerprint.classification_persistence import ClassificationPersistenceError
from app.device_fingerprint.fusion import fuse_classification
from tests.device_fingerprint import SITE
from tests.device_fingerprint_task04_t01.test_snapshot_service import MAC
from tests.device_fingerprint_task04_t03.test_origin_assessment import _dhcp_row, _inputs
from tests.device_fingerprint_task04_t04.test_fusion import _base_from_source
from tests.device_fingerprint_task04_04e_read.test_classification_read import _persisted


def ref(content):
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def put(connection, content):
    connection.execute('INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?)',
                       (content.artifact_id, content.artifact_type, content.content_sha256,
                        content.semantic_payload_json))


@pytest.fixture(scope='module')
def assets(tmp_path_factory):
    store, _, _, reader = _persisted(tmp_path_factory.mktemp('diagnostic-base'))
    record = reader.get_current(SITE, MAC)
    cases = {}
    for label, when in [('fresh', '2026-10-16T12:00:00.000Z'), ('expired', '2030-01-01T00:00:00.000Z')]:
        fusion = _base_from_source(_inputs(evidence_rows=[_dhcp_row()], knowledge_time=when))
        result = fuse_classification(fusion)
        with sqlite3.connect(store.database_path) as connection:
            raw = connection.execute('SELECT semantic_payload_json FROM artifacts WHERE artifact_id=?',
                                     (record.core.snapshot_record_id,)).fetchone()[0]
        snapshot_payload = json.loads(raw)
        snapshot_payload['evidence_snapshot_content'] = ref(fusion.evidence_snapshot_content)
        snapshot = make_artifact_content('SnapshotRecord', snapshot_payload)
        core = replace(record.core, execution_context='PRODUCTION',
                       runtime_profile_activation_record_id='11111111-1111-4111-8111-111111111111',
                       classification_result_id=result.artifact_id, classification_result_digest=result.content_sha256,
                       classification_request_manifest_digest=result.semantic_payload['classification_request_digest'],
                       classification_request_manifest_id='ClassificationRequestManifest:v1:sha256:' + result.semantic_payload['classification_request_digest'],
                       snapshot_record_id=snapshot.artifact_id, snapshot_record_digest=snapshot.content_sha256)
        cases[label] = (core, result, snapshot, fusion)
    return store.database_path, cases


@pytest.fixture
def retained_case(assets, tmp_path):
    original, cases = assets
    path = tmp_path / 'classification.sqlite'
    shutil.copyfile(original, path)

    def prepare(label='fresh'):
        core, result, snapshot, fusion = cases[label]
        with sqlite3.connect(path) as connection:
            for artifact in (result, snapshot, fusion.evidence_snapshot_content, *fusion.origin_assessments):
                put(connection, artifact)
            fields = core.__dataclass_fields__
            connection.execute('UPDATE classifications SET ' + ','.join(name + '=?' for name in fields),
                               tuple(getattr(core, name) for name in fields))
        reader = DeviceFingerprintClassificationReadService(path)
        return path, core, result, fusion, reader, DeviceFingerprintPresentationService(reader)
    return prepare


def test_A_fresh_k1_claim_and_expired_k4_are_separate_retained_origins(retained_case):
    path, _, result, _, reader, adapter = retained_case()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    old = present_classification(reader.get_current_production(SITE, MAC)).as_dict()
    shown = adapter.get_detail(SITE, MAC).as_dict()
    assert {k: v for k, v in shown.items() if k != 'origin_diagnostics'} == old
    assert shown['device_class_result']['canonical_value_id'] == 'smartphone'
    assert shown['platform_result']['canonical_value_id'] == 'android'
    assert shown['device_class_result']['supporting_origin_groups'] == ['dhcp']
    assert 'knowledge_source_expired' in shown['device_class_result']['explanation_codes']
    origins = {row['origin_group']: row for row in shown['origin_diagnostics']['origins']}
    assert shown['origin_diagnostics']['state'] == 'available'
    assert 'knowledge_source_expired' in origins['mac_registry']['explanation_codes']
    assert 'knowledge_source_expired' not in origins['dhcp']['explanation_codes']
    assert len(origins) == 6
    assert reader.get_current_production(SITE, MAC).result.semantic_payload_json == result.semantic_payload_json
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_B_expired_k1_is_not_masked(retained_case):
    _, _, _, _, _, adapter = retained_case('expired')
    shown = adapter.get_detail(SITE, MAC).as_dict()
    origin = next(row for row in shown['origin_diagnostics']['origins'] if row['origin_group'] == 'dhcp')
    assert 'knowledge_source_expired' in origin['explanation_codes']
    assert all(row['internal_state'] not in {'resolved', 'recognized_out_of_scope'} for row in origin['dimensions'])
    assert shown['device_class_result']['canonical_value_id'] is None
    assert shown['device_class_result']['status'] != 'resolved'


@pytest.mark.parametrize('failure', ['missing', 'corrupt', 'wrong_type', 'duplicate_origin', 'malformed',
                                    'snapshot_site', 'snapshot_mac', 'snapshot_reference', 'origin_reference'])
def test_D_untrusted_diagnostics_do_not_break_authoritative_result(retained_case, failure):
    path, _, result, fusion, _, adapter = retained_case()
    origin = fusion.origin_assessments[0]
    with sqlite3.connect(path) as connection:
        if failure == 'missing':
            connection.execute('DELETE FROM artifacts WHERE artifact_id=?', (origin.artifact_id,))
        elif failure in {'corrupt', 'wrong_type'}:
            field = 'semantic_payload_json' if failure == 'corrupt' else 'artifact_type'
            value = b'{}' if failure == 'corrupt' else 'ClassificationResult'
            connection.execute('UPDATE artifacts SET ' + field + '=? WHERE artifact_id=?', (value, origin.artifact_id))
        elif failure.startswith('snapshot_'):
            payload = fusion.evidence_snapshot_content.semantic_payload
            if failure == 'snapshot_site':
                payload['site_id'] = 'f' * 24
            elif failure == 'snapshot_mac':
                payload['observed_mac'] = '00:11:22:33:44:55'
            else:
                payload = {'site_id': SITE, 'observed_mac': MAC}
            changed = make_artifact_content('EvidenceSnapshotContent', payload)
            connection.execute('UPDATE artifacts SET semantic_payload_json=?,content_sha256=? WHERE artifact_id=?',
                               (changed.semantic_payload_json, changed.content_sha256, fusion.evidence_snapshot_content.artifact_id))
        else:
            payload = origin.semantic_payload
            if failure == 'duplicate_origin':
                payload['origin_group'] = fusion.origin_assessments[1].semantic_payload['origin_group']
            elif failure == 'origin_reference':
                payload['source_evaluability'] = ref(fusion.evidence_snapshot_content)
            else:
                payload['dimension_assessments'] = []
            changed = make_artifact_content('OriginAssessment', payload)
            put(connection, changed)
            result_payload = result.semantic_payload
            result_payload['origin_assessments'] = [ref(changed) if r['artifact_id'] == origin.artifact_id else r
                                                    for r in result_payload['origin_assessments']]
            altered = make_artifact_content('ClassificationResult', result_payload)
            put(connection, altered)
            connection.execute('UPDATE classifications SET classification_result_id=?,classification_result_digest=?',
                               (altered.artifact_id, altered.content_sha256))
    shown = adapter.get_detail(SITE, MAC).as_dict()
    assert shown['state'] == 'classified'
    assert shown['device_class_result']['canonical_value_id'] == 'smartphone'
    assert shown['origin_diagnostics'] == {'state': 'unavailable'}


def test_D_scoped_exact_identity_and_unknown_classification(retained_case):
    _, core, result, _, reader, adapter = retained_case()
    expected = ArtifactRef(result.artifact_id, result.content_sha256)
    for site, mac, identity in [('f' * 24, MAC, core.classification_id),
                                (SITE, '00:11:22:33:44:55', core.classification_id),
                                (SITE, MAC, '22222222-2222-4222-8222-222222222222')]:
        with pytest.raises(ClassificationPersistenceError):
            reader.get_origin_assessments(site, mac, identity, expected_result=expected)
    assert adapter.get_detail('f' * 24, MAC).state == 'no_result'
    wrong = make_artifact_content('ClassificationResult', {'synthetic': 'other'})
    with pytest.raises(ClassificationPersistenceError):
        reader.get_origin_assessments(SITE, MAC, core.classification_id,
                                     expected_result=ArtifactRef(wrong.artifact_id, wrong.content_sha256))


@pytest.mark.parametrize('field,value', [('site_id', 'f' * 24), ('observed_mac', '00:11:22:33:44:55')])
def test_D_consistently_rehashed_cross_scope_closure_is_rejected(retained_case, field, value):
    path, core, result, fusion, _, adapter = retained_case()
    snapshot_payload = fusion.evidence_snapshot_content.semantic_payload
    snapshot_payload[field] = value
    snapshot = make_artifact_content('EvidenceSnapshotContent', snapshot_payload)
    assessments = []
    for original in fusion.origin_assessments:
        payload = original.semantic_payload
        payload['evidence_snapshot_content'] = ref(snapshot)
        assessments.append(make_artifact_content('OriginAssessment', payload))
    result_payload = result.semantic_payload
    result_payload['evidence_snapshot_content'] = ref(snapshot)
    result_payload['origin_assessments'] = [ref(item) for item in assessments]
    altered = make_artifact_content('ClassificationResult', result_payload)
    with sqlite3.connect(path) as connection:
        raw = connection.execute('SELECT semantic_payload_json FROM artifacts WHERE artifact_id=?', (core.snapshot_record_id,)).fetchone()[0]
        payload = json.loads(raw)
        payload['evidence_snapshot_content'] = ref(snapshot)
        snapshot_record = make_artifact_content('SnapshotRecord', payload)
        for artifact in (snapshot, snapshot_record, altered, *assessments):
            put(connection, artifact)
        connection.execute('UPDATE classifications SET classification_result_id=?,classification_result_digest=?,snapshot_record_id=?,snapshot_record_digest=?',
                           (altered.artifact_id, altered.content_sha256, snapshot_record.artifact_id, snapshot_record.content_sha256))
    shown = adapter.get_detail(SITE, MAC).as_dict()
    assert shown['state'] == 'classified'
    assert shown['origin_diagnostics'] == {'state': 'unavailable'}
    assert value not in json.dumps(shown['origin_diagnostics'])


@pytest.mark.parametrize('mode', ['oversized', 'unsupported_version'])
def test_D_bounded_or_unsupported_artifact_fails_soft(retained_case, mode):
    path, _, result, fusion, _, adapter = retained_case()
    original = fusion.origin_assessments[0]
    payload = original.semantic_payload
    if mode == 'oversized':
        payload['explanation_codes'] = ['x' * (1024 * 1024)]
    else:
        payload['origin_assessment_contract_version'] = 2
    changed = make_artifact_content('OriginAssessment', payload)
    result_payload = result.semantic_payload
    result_payload['origin_assessments'] = [ref(changed) if r['artifact_id'] == original.artifact_id else r
                                            for r in result_payload['origin_assessments']]
    altered = make_artifact_content('ClassificationResult', result_payload)
    with sqlite3.connect(path) as connection:
        put(connection, changed); put(connection, altered)
        connection.execute('UPDATE classifications SET classification_result_id=?,classification_result_digest=?',
                           (altered.artifact_id, altered.content_sha256))
    shown = adapter.get_detail(SITE, MAC).as_dict()
    assert shown['state'] == 'classified'
    assert shown['origin_diagnostics'] == {'state': 'unavailable'}


def test_E_detail_bounded_read_only_no_reclassification_and_batch_unchanged(retained_case, monkeypatch, tmp_path):
    path, _, _, _, reader, adapter = retained_case()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    def forbidden(*args, **kwargs):
        pytest.fail('Diagnostic render must not classify, evaluate freshness or read raw evidence')
    monkeypatch.setattr('app.device_fingerprint.fusion.DeviceFingerprintFusionCore.fuse', forbidden)
    monkeypatch.setattr('app.device_fingerprint.origin_assessment.DeviceFingerprintOriginAssessmentBuilder.build', forbidden)
    monkeypatch.setattr('app.device_fingerprint.origin_assessment._reduce_claims', forbidden)
    monkeypatch.setattr('app.device_fingerprint.fe5_external_knowledge.evaluate_external_knowledge_freshness', forbidden)
    connects, statements = [], []
    original = sqlite3.connect
    def counted(*args, **kwargs):
        connects.append(args[0])
        connection = original(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection
    monkeypatch.setattr(sqlite3, 'connect', counted)
    started = time.monotonic()
    assert adapter.get_detail(SITE, MAC).as_dict()['origin_diagnostics']['state'] == 'available'
    detail_seconds = time.monotonic() - started
    assert len(connects) == 2 and all('mode=ro' in uri for uri in connects)
    assert sum(s.startswith('SELECT') for s in statements) == 5
    assert not any(s.startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE')) for s in statements)
    assert not any(' from evidence' in s.lower() for s in statements)
    connects.clear(); statements.clear()
    shown = adapter.get_many(SITE, (MAC,))
    assert 'origin_diagnostics' not in shown[MAC].as_dict()
    assert len(connects) == 1
    assert sum(s.startswith('SELECT') for s in statements) == 2
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    (tmp_path / 'read-count.json').write_text(json.dumps({'detail_selects': 5, 'detail_connections': 2,
        'list_selects': 2, 'list_connections': 1, 'detail_seconds': detail_seconds}), encoding='utf-8')
