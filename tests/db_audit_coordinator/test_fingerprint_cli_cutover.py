"""Public CLI is submit-only. Test sockets are disposable, never operational."""
import json
import os
import socket
import sys
import threading
import uuid

import pytest

from app.db_audit_coordinator import contracts as c, protocol
from app.device_fingerprint import audit_cli, audit_runner


@pytest.mark.parametrize("status,exit_code", [("store_busy",2),("queue_full",2),("invalid_request",2),
    ("coordinator_unavailable",5),("queue_unknown",5),("unsafe_path",5)])
def test_typed_unavailable_never_falls_back_to_source_or_auditor(monkeypatch,capsys,status,exit_code):
    monkeypatch.setattr(audit_cli,"capture_loaded_artifact_identity",lambda *a:object())
    monkeypatch.setattr(audit_runner,"EvidenceAuditor",lambda *a,**k:pytest.fail("no local auditor fallback"))
    def fail(_request):raise c.CoordinatorError(status)
    monkeypatch.setattr(audit_cli,"submit_request",fail)
    assert audit_cli.main(["run","--store-id","fingerprint_evidence"])==exit_code
    result=json.loads(capsys.readouterr().out)
    assert set(result)=={"store_id","status","category_code"}
    assert result["status"]==(status if status in {"store_busy","queue_full","invalid_request"} else "coordinator_unavailable")


@pytest.mark.parametrize("args", [["--store-id","visits"],["--store-id","fingerprint_evidence","--db-path","/private/source"],
    ["--store-id","fingerprint_evidence","--socket","/fake"],["--store-id","fingerprint_evidence","--sql","SELECT 1"]])
def test_no_public_target_path_sql_or_socket_selector(monkeypatch,args):
    monkeypatch.setattr(audit_cli,"capture_loaded_artifact_identity",lambda *a:pytest.fail("reject parser first"))
    with pytest.raises(SystemExit) as error:audit_cli.main(["run",*args])
    assert error.value.code==2


def test_canonical_non_v4_key_is_preserved_without_source_settings(monkeypatch,capsys):
    key="11111111-1111-1111-8111-111111111111";job=str(uuid.uuid4());requests=[]
    monkeypatch.setattr(audit_cli,"capture_loaded_artifact_identity",lambda *a:object())
    def send(value):
        requests.append(value)
        return dict(store_id="fingerprint_evidence",status="queued",job_id=job)
    monkeypatch.setattr(audit_cli,"submit_request",send)
    assert audit_cli.main(["run","--store-id","fingerprint_evidence","--idempotency-key",key])==0
    assert requests==[dict(op="submit",store_id="fingerprint_evidence",origin="manual",idempotency_key=key)]
    assert json.loads(capsys.readouterr().out)==dict(store_id="fingerprint_evidence",status="queued",job_id=job)


@pytest.mark.skipif(sys.platform!="linux",reason="Real Linux private Unix socket and SO_PEERCRED client")
@pytest.mark.parametrize("reply", ["valid","wrong-store","oversize","raw-path","unknown-status"])
def test_actual_cli_socket_submission_is_bounded_and_private(tmp_path,monkeypatch,capsys,reply):
    tmp_path.chmod(0o700);path=tmp_path/"fake.sock";requests=[];errors=[]
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(str(path));path.chmod(0o600);server.listen(1)
    job=str(uuid.uuid4())
    def serve():
        try:
            connection,_=server.accept()
            with connection:
                protocol.peer_scope(connection,{os.geteuid()})
                request=protocol.receive(connection);requests.append(request);c.request(request)
                value=dict(status="queued",job=dict(job_id=job,store_id="fingerprint_evidence",private="/private/NO_ECHO"))
                if reply=="wrong-store":value["job"]["store_id"]="visits"
                if reply=="unknown-status":value["status"]="passed"
                if reply=="raw-path":value=dict(error="/private/NO_ECHO")
                if reply=="oversize":connection.sendall((8193).to_bytes(4,"big"))
                else:protocol.send(connection,value)
        except Exception as error:errors.append(error)
        finally:server.close()
    thread=threading.Thread(target=serve);thread.start()
    monkeypatch.setattr(audit_cli,"capture_loaded_artifact_identity",lambda *a:object())
    monkeypatch.setattr(audit_cli,"submit_request",lambda value:protocol.submit_request(value,_socket_path=str(path)))
    monkeypatch.setattr(audit_runner,"EvidenceAuditor",lambda *a,**k:pytest.fail("client must not construct audit"))
    try:
        result=audit_cli.main(["run","--store-id","fingerprint_evidence"])
        output=capsys.readouterr().out
        assert result==(0 if reply=="valid" else 5)
        assert "NO_ECHO" not in output and str(tmp_path) not in output
        assert len(requests)==1 and requests[0]["op"]=="submit"
        assert set(requests[0])=={"op","store_id","idempotency_key","origin"}
    finally:thread.join(3);server.close()
    assert not thread.is_alive() and errors==[]


@pytest.mark.skipif(sys.platform!="linux",reason="Linux missing private socket refusal")
def test_missing_socket_no_files_created_and_no_direct_fallback(tmp_path):
    with pytest.raises(c.CoordinatorError):
        protocol.submit_request(dict(op="submit",store_id="fingerprint_evidence",origin="manual",idempotency_key=str(uuid.uuid4())),
            _socket_path=str(tmp_path/"absent.sock"))
    assert list(tmp_path.iterdir())==[]
