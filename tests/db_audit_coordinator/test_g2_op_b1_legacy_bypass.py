import ast
import json
from pathlib import Path

import pytest

from app.db_audit_coordinator import contracts as c
from app.device_fingerprint import audit_cli, audit_runner


@pytest.mark.parametrize('failure', ['unavailable', 'unknown', 'queue_full', 'unexpected'])
@pytest.mark.parametrize('force', [False, True])
def test_public_cli_never_direct_audits_even_with_environment_force(monkeypatch, capsys, failure, force):
    monkeypatch.setattr(audit_cli, 'capture_loaded_artifact_identity', lambda *a: object())
    monkeypatch.setattr(audit_runner.EvidenceAuditor, 'run', lambda *a, **k: pytest.fail('NO_DIRECT_FALLBACK'))
    monkeypatch.setenv('DB_AUDIT_REAL_ENABLED', str(force))
    monkeypatch.setenv('DB_AUDIT_FORCE', str(force))
    requests = []
    def unavailable(value):
        requests.append(value)
        if failure == 'unexpected': raise RuntimeError('PRIVATE_CANARY')
        raise c.CoordinatorError({'unavailable': 'coordinator_unavailable', 'unknown': 'queue_unknown', 'queue_full': 'queue_full'}[failure])
    monkeypatch.setattr(audit_cli, 'submit_request', unavailable)
    code = audit_cli.main(['run', '--store-id', 'fingerprint_evidence'])
    output = capsys.readouterr().out; value = json.loads(output)
    assert code == (2 if failure == 'queue_full' else 5)
    assert value['status'] == ('queue_full' if failure == 'queue_full' else 'coordinator_unavailable')
    assert 'PRIVATE_CANARY' not in output and len(requests) == 1
    assert requests[0]['op'] == 'submit' and 'db_path' not in requests[0]


def test_source_cli_and_worker_contain_no_operational_audit_fallback():
    root = Path(__file__).resolve().parents[2]
    cli = (root/'app/device_fingerprint/audit_cli.py').read_text(encoding='utf-8')
    worker = (root/'app/db_audit_coordinator/worker.py').read_text(encoding='utf-8')
    tree = ast.parse(cli)
    assert 'EvidenceAuditor' not in cli and 'submit_request' in cli
    assert not any(isinstance(node, ast.Attribute) and node.attr == 'run' for node in ast.walk(tree))
    assert 'EvidenceAuditor' not in worker and 'SQLite' not in worker
    tree = ast.parse(worker)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'execute')
    guard = next(node for node in ast.walk(function) if isinstance(node, ast.If)
        and ast.unparse(node.test) == "authority['plan'] is None")
    assert isinstance(guard.body[-1], ast.Raise)
    assert 'not_admitted' in ast.unparse(guard.body[-1])
