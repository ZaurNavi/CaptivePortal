import os
import socket
import struct
import sys
import threading
import time
import uuid

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator.protocol import receive,send,peer_scope
from tests.db_audit_coordinator import lab,cleanup


@pytest.mark.parametrize('raw',[b'\0\0\0\0',struct.pack('!I',8193),struct.pack('!I',2)+b'{',
    struct.pack('!I',13)+b'{"x":1,"x":2}'])
def test_bounded_invalid_or_partial_frame_is_rejected_without_source_io(raw):
    left,right=socket.socketpair()
    try:
        left.sendall(raw);left.shutdown(socket.SHUT_WR)
        with pytest.raises(c.CoordinatorError,match='invalid_request'):receive(right)
    finally:left.close();right.close()


def test_portable_frame_roundtrip():
    left,right=socket.socketpair()
    try:
        send(left,dict(op='status',job_id=str(uuid.uuid4())))
        assert receive(right)['op']=='status'
        with pytest.raises(c.CoordinatorError):send(left,{'x':'a'*8192})
    finally:left.close();right.close()


@pytest.mark.skipif(sys.platform!='linux',reason='Linux AF_UNIX SO_PEERCRED and private socket contract')
def test_real_peer_credentials_and_unauthorized_caller(tmp_path):
    left,right=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        assert peer_scope(right,{os.geteuid()})==c.scope(os.geteuid())
        with pytest.raises(c.CoordinatorError,match='unauthorized'):peer_scope(right,{os.geteuid()+1})
    finally:left.close();right.close()


@pytest.mark.skipif(sys.platform!='linux',reason='Linux private event-driven coordinator socket integration')
@pytest.mark.parametrize('authorized',[True,False])
def test_real_private_socket_closed_requests_and_no_source_reads(tmp_path,authorized):
    fixture=lab(tmp_path);subject=fixture.coordinator();ready=threading.Event();errors=[]
    def run():
        try:subject.serve({os.geteuid()} if authorized else {os.geteuid()+1},ready.set)
        except Exception as error:errors.append(error)
    thread=threading.Thread(target=run);thread.start()
    try:
        assert ready.wait(3)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
            client.connect(str(fixture.root/'coordinator.sock'))
            if authorized:send(client,dict(op='submit',store_id='forged_store',origin='manual',idempotency_key=str(uuid.uuid4())))
            reply=receive(client)
        assert reply==dict(error='invalid_request' if authorized else 'unauthorized')
        assert subject.store.read()['jobs']==[]
        assert not tuple(fixture.root.glob('*.source_read'))
    finally:subject.close();thread.join(4);cleanup(subject)
    assert not thread.is_alive() and errors==[]
    assert not (fixture.root/'coordinator.sock').exists()


@pytest.mark.skipif(sys.platform!='linux',reason='Linux socket/peercred/worker/durable queue end-to-end fixture')
def test_F19_socket_submit_duplicate_status_and_quiet_idle_have_no_extra_commits(tmp_path):
    fixture=lab(tmp_path);syncs=[]
    def sync(fd):syncs.append(1);os.fsync(fd)
    subject=fixture.coordinator('hold_preflight',sync=sync,timeout=10)
    ready=threading.Event();errors=[]
    def serve():
        try:subject.serve({os.geteuid()},ready.set)
        except Exception as error:errors.append(error)
    thread=threading.Thread(target=serve);thread.start()
    def exchange(value):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
            client.connect(str(fixture.root/'coordinator.sock'));send(client,value);return receive(client)
    try:
        assert ready.wait(4)
        request=dict(op='submit',store_id='visits',idempotency_key=str(uuid.uuid4()),origin='scheduled')
        reply=exchange(request);job=reply['job']['job_id'];assert reply['status']=='queued'
        from tests.db_audit_coordinator import marker
        marker(fixture,job,'preflight')
        assert exchange(request)['job']['job_id']==job
        os.write(subject.cancel_fd,b'g')
        deadline=time.monotonic()+5
        while True:
            status=exchange(dict(op='status',job_id=job))
            if status['job']['state']=='completed':break
            assert time.monotonic()<deadline;time.sleep(.01)
        assert status['last_verified_success']['fixture_only'] is True
        before=len(syncs)
        for _ in range(100):assert exchange(dict(op='status',job_id=job))['job']['state']=='completed'
        assert len(syncs)==before
        assert exchange(request)['status']=='duplicate' and len(syncs)==before
        encoded=c.encode(status)
        assert str(fixture.root).encode() not in encoded
        assert b'nonce' not in encoded and b'auth_hash' not in encoded and b'scope_hash' not in encoded
    finally:subject.close();thread.join(4);cleanup(subject)
    assert not thread.is_alive() and errors==[]
