import copy
import json
import uuid

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator.admission import Admission,CompletionFence,FilesystemAdmission


def test_closed_initial_queue_and_registered_store_inventory():
    value=c.empty_state()
    assert c.state(value)==value and len(c.STORES)==17
    assert value['next_sequence']==1 and value['jobs']==[]
    assert c.MAX_OUTSTANDING==32 and c.MAX_HISTORY==128 and c.MAX_BYTES==262144
    assert c.DOMAIN=='lab-ubunt-local-sqlite-v1'


@pytest.mark.parametrize('value',[True,False,-1,1.0,'1',None,2**63])
def test_nonnegative_canonical_integer_rejects_bool_and_overflow(value):
    with pytest.raises(c.CoordinatorError):c.integer(value)


@pytest.mark.parametrize('value',[None,[],{},'NOT-A-UUID','00000000-0000-0000-0000-00000000000X','123456781234123412341234567890ab'])
def test_uuid_rejects_noncanonical_identity(value):
    with pytest.raises(c.CoordinatorError):c.identifier(value)


def test_uuid_has_no_version_restriction():
    assert c.identifier('12345678-1234-1234-1234-1234567890ab')


@pytest.mark.parametrize('changes',[{'store_id':'not_registered'},{'origin':'cron'},{'origin':[]},
    {'store_id':'/opt/CaptivePortal/data/visits.sqlite3'},{'source_path':'/secret'}, {'op':'cancel'},
    {'op':'status'},{'idempotency_key':'bad'}])
def test_request_closed_fields_no_paths_no_unknown_origins(changes):
    value=dict(op='submit',store_id='visits',idempotency_key=str(uuid.uuid4()),origin='manual')|changes
    with pytest.raises(c.CoordinatorError):c.request(value)


@pytest.mark.parametrize('raw',[b'{"a":1,"a":2}',b'{"x":NaN}',b'{"x":Infinity}',b'\xff',b'{' ,b'x'*262145],
    ids=['duplicate','nan','infinity','non-utf8','broken-json','oversize'])
def test_wire_duplicate_nonfinite_unicode_and_size_rejected(raw):
    with pytest.raises(c.CoordinatorError):c.decode(raw)


@pytest.mark.parametrize('change',[{'schema_version':'future'},{'controller_epoch':'x'},{'next_sequence':True},
    {'next_sequence':-1},{'jobs':{}},{'extra':'private'},{'last_attempt_by_store':{'unknown':{}}}])
def test_queue_schema_rejects_malformed_state(change):
    with pytest.raises(c.CoordinatorError):c.state(c.empty_state()|change)


@pytest.mark.parametrize('facts',[None,{}, {'cgroup':None},{'memory_max':'max'},{'memory_max':0},
    {'memory_max':'bad'},{'containment':True}])
def test_F12_unqualified_production_resource_and_completion_interfaces_deny(facts):
    with pytest.raises(c.CoordinatorError,match='not_admitted'):Admission().envelope(facts)
    assert CompletionFence().released(facts) is False


def test_status_key_scope_is_hashed_and_deterministic():
    key=str(uuid.uuid4())
    assert c.scope(1)!=c.scope(2)
    assert c.idempotency(c.scope(1),key)==c.idempotency(c.scope(1),key)
    assert key not in c.idempotency(c.scope(1),key)


def test_filesystem_and_completion_production_defaults_never_invent_qualification():
    with pytest.raises(c.CoordinatorError,match='not_admitted'):FilesystemAdmission().validate('/not-opened',0)
    assert CompletionFence().exitcode(None) is None


@pytest.mark.parametrize('value',['/PRIVATE/secret-path','RAW_IP_PAYLOAD','unknown',None])
def test_typed_errors_do_not_echo_arbitrary_exception_text(value):
    assert str(c.CoordinatorError(value))=='coordinator_unavailable'
