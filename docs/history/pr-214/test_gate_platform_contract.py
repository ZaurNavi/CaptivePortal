"""Focused synthetic infrastructure proofs only; no real application/gate runs."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pytest_platform_contract as contract


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


comparison = load("compare-gate-evidence-v1")
preflight = load("gate-preflight-v1")
TRANSFER = "tests/test_synthetic_posix.py::test_native_descriptor"


def manifest(approved=False):
    result = {"schema_version": 1, "gate_identity": contract.GATE, "status": "DRAFT", "approval": None,
              "protected_windows_ids": list(contract.PROTECTED), "transfers": [
                  {"node_id": TRANSFER, "linux_node_id": TRANSFER, "cause": "Synthetic native fcntl/pread test input, not a real transfer approval",
                   "source": {"path": "tests/test_synthetic_posix.py", "sha256": "a" * 64, "reference": "synthetic"},
                   "evidence": {"path": "synthetic", "sha256": "b" * 64, "reference": "synthetic"}}], "permitted_skips": []}
    if approved:
        result["status"] = "APPROVED"
        result["approval"] = {"authority": "TECH_LEAD_21", "reference": "SYNTHETIC_SELF_TEST_ONLY_NOT_REAL_APPROVAL", "body_sha256": contract.manifest_digest(result)}
    return result


def outcomes():
    return {key: {"status": "PASS", "phases": {"setup": "passed", "call": "passed", "teardown": "passed"}, "reason": ""}
            for key in (*contract.PROTECTED, TRANSFER)}


def ledger(platform="linux", approved=True):
    data = outcomes()
    context = {"schema_version": 1, "gate_identity": contract.GATE, "platform": platform,
               "repo": "/synthetic", "head": "a" * 40, "tree": "b" * 40,
               "manifest_sha256": "c" * 64, "plugin_sha256": "d" * 64, "launcher_sha256": "e" * 64,
               "environment": {"python": "synthetic", "sqlite": "synthetic", "sqlite_compile_options": [], "interpreter_sha256": "f" * 64, "packages": {}},
               "source_inventory": {}, "expected_collection": list(data)}
    return {"schema_version": 1, "gate_identity": contract.GATE, "context": context,
            "collected": list(data), "outcomes": data, "deselected": [], "collection_errors": [],
            "pytest_exit_code": 0, "contract_failures": [], "status": "PASS"}


def recalculate(value, rules):
    reasons = contract.validate_outcomes(rules, value["context"]["platform"], value["collected"], value["outcomes"], value["deselected"], value["collection_errors"])
    if value["pytest_exit_code"]:
        reasons.append("pytest_exit_nonzero:" + str(value["pytest_exit_code"]))
    value["contract_failures"] = sorted(set(reasons))
    value["status"] = "FAIL" if reasons else "PASS"
    return value


def test_actual_manifest_draft_closed_and_no_approval():
    value = contract.validate_manifest(contract.strict_json(HERE / "platform-manifest-v1.json"))
    assert value["status"] == "DRAFT" and value["approval"] is None
    assert len(value["transfers"]) == 219
    assert not set(contract.PROTECTED) & {r["node_id"] for r in value["transfers"]}
    with pytest.raises(contract.ContractError, match="draft_manifest_not_admitted"):
        contract.validate_manifest(value, require_approved=True)


@pytest.mark.parametrize("change", ["extra", "duplicate", "protected", "counterpart", "digest", "empty_cause", "approval"])
def test_manifest_bad_shapes_rejected(change):
    value = manifest()
    if change == "extra": value["unexpected"] = True
    if change == "duplicate": value["transfers"].append(copy.deepcopy(value["transfers"][0]))
    if change == "protected": value["transfers"][0]["node_id"] = contract.PROTECTED[0]
    if change == "counterpart": value["transfers"][0]["linux_node_id"] += "_different"
    if change == "digest": value["transfers"][0]["source"]["sha256"] = "A" * 64
    if change == "empty_cause": value["transfers"][0]["cause"] = ""
    if change == "approval": value["approval"] = {"fake": True}
    with pytest.raises(contract.ContractError): contract.validate_manifest(value)


def test_approval_binds_exact_manifest_semantics():
    value = manifest(True)
    contract.validate_manifest(value, require_approved=True)
    value["transfers"][0]["cause"] = "changed"
    with pytest.raises(contract.ContractError, match="approval_binding"):
        contract.validate_manifest(value, require_approved=True)


@pytest.mark.parametrize("status", ["FAIL", "ERROR", "XFAIL", "XPASS", "SKIP", "INCOMPLETE", "UNKNOWN"])
def test_any_nonpass_is_not_hidden(status):
    data = outcomes(); data[TRANSFER]["status"] = status
    assert contract.validate_outcomes(manifest(), "linux", list(data), data)


@pytest.mark.parametrize("identifier", contract.PROTECTED)
@pytest.mark.parametrize("mode", ["missing", "skip", "deselect", "fail"])
def test_every_protected_windows_case_fail_closed(identifier, mode):
    data = outcomes(); collected = list(data); deselected = []
    if mode == "missing": collected.remove(identifier); del data[identifier]
    if mode == "skip": data[identifier]["status"] = "SKIP"
    if mode == "fail": data[identifier]["status"] = "FAIL"
    if mode == "deselect": deselected.append(identifier)
    assert contract.validate_outcomes(manifest(), "windows", collected, data, deselected)


def test_missing_linux_counterpart_never_passes():
    data = outcomes(); del data[TRANSFER]
    assert contract.validate_outcomes(manifest(True), "linux", list(data), data)


def test_draft_cannot_transfer_even_if_status_claims_transfer():
    data = outcomes(); data[TRANSFER].update(status="PLATFORM_TRANSFER", reason="approved_linux_transfer")
    data[TRANSFER]["phases"] = {"setup": "skipped", "teardown": "passed"}
    assert contract.validate_outcomes(manifest(), "windows", list(data), data)
    assert not contract.validate_outcomes(manifest(True), "windows", list(data), data)
    assert contract.validate_outcomes(manifest(True), "linux", list(data), data)


def test_pass_requires_all_three_real_phases():
    data = outcomes(); del data[TRANSFER]["phases"]["call"]
    assert contract.validate_outcomes(manifest(), "linux", list(data), data)


def test_collection_errors_duplicates_and_missing_outcomes():
    data = outcomes()
    assert contract.validate_outcomes(manifest(), "linux", list(data), data, collection_errors=["bad import"])
    with pytest.raises(contract.ContractError):
        contract.validate_outcomes(manifest(), "linux", list(data) + [TRANSFER], data)
    collected = list(data); del data[TRANSFER]
    assert contract.validate_outcomes(manifest(), "linux", collected, data)


def test_false_reported_pass_cannot_hide_real_failure():
    value = ledger(); value["outcomes"][TRANSFER]["status"] = "FAIL"
    with pytest.raises(contract.ContractError, match="claimed_status"):
        comparison.validate_ledger(value, manifest(True))


def test_baseline_failure_is_not_absolute_pass():
    rules = manifest(True); a = ledger(); a["outcomes"][TRANSFER]["status"] = "FAIL"; recalculate(a, rules)
    result = comparison.compare_pair(a, copy.deepcopy(a), rules)
    assert result["differential_no_new_failures"]
    assert result["baseline_strict"] == result["candidate_strict"] == "FAIL"


def test_composite_requires_exact_linux_pass():
    rules = manifest(True); windows, linux = ledger("windows"), ledger()
    windows["outcomes"][TRANSFER].update(status="PLATFORM_TRANSFER", reason="approved_linux_transfer")
    windows["outcomes"][TRANSFER]["phases"] = {"setup": "skipped", "teardown": "passed"}
    recalculate(windows, rules)
    assert comparison.composite(windows, linux, rules)["status"] == "PASS"
    linux["outcomes"][TRANSFER]["status"] = "SKIP"; recalculate(linux, rules)
    assert comparison.composite(windows, linux, rules)["status"] == "FAIL"


@pytest.mark.parametrize("kind", ["tree", "collection", "environment", "plugin"])
def test_pair_drift_rejected(kind):
    a, b = ledger(), ledger()
    if kind == "tree":
        b["context"]["tree"] = "c" * 40
        with pytest.raises(contract.ContractError): comparison.composite(ledger("windows"), b, manifest(True))
        return
    if kind == "collection": b["context"]["expected_collection"] = []
    if kind == "environment": b["context"]["environment"]["sqlite"] = "different"
    if kind == "plugin": b["context"]["plugin_sha256"] = "f" * 64
    with pytest.raises(contract.ContractError): comparison.compare_pair(a, b, manifest(True))


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}'])
def test_json_duplicate_and_nonfinite_rejected(tmp_path, text):
    path = tmp_path / "invalid.json"; path.write_text(text)
    with pytest.raises(contract.ContractError): contract.strict_json(path)


def test_safe_environment_drops_all_feature_secret_pytest_inputs(tmp_path):
    value = preflight.safe_environment(tmp_path, Path("/synthetic"))
    assert not any(k.startswith(("WEB_ADMIN", "CAPPORT", "OMADA", "DEVICE_FINGERPRINT", "NETWORK_METADATA")) for k in value)
    assert "PYTEST_ADDOPTS" not in value and "PYTEST_PLUGINS" not in value
    assert value["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"


def test_environment_draft_refuses_gate(tmp_path):
    lock = contract.strict_json(HERE / "gate-environment-lock-v1.json")
    with pytest.raises(contract.ContractError, match="draft_environment"):
        preflight.approved_lock(lock, tmp_path, HERE / "run-platform-gates-v1.cmd",
            contract.digest(HERE / "gate-environment-lock-v1.json"), "windows")


def test_plugin_duplicate_report_cannot_overwrite_fail(tmp_path):
    config = SimpleNamespace()
    ctx = {"platform": "linux"}
    plugin = contract.Contract(config, ctx, manifest(), tmp_path / "ledger.json")
    plugin.collected = list(outcomes())
    for identifier in plugin.collected:
        for phase in ("setup", "call", "teardown"):
            plugin.pytest_runtest_logreport(SimpleNamespace(nodeid=identifier, when=phase, outcome="passed", passed=True, failed=False, skipped=False))
    plugin.pytest_runtest_logreport(SimpleNamespace(nodeid=TRANSFER, when="call", outcome="failed", failed=True, skipped=False))
    session = SimpleNamespace(exitstatus=0)
    plugin.pytest_sessionfinish(session, 0)
    assert session.exitstatus != 0
    value = contract.strict_json(tmp_path / "ledger.json")
    assert value["outcomes"][TRANSFER]["status"] == "ERROR"


def test_real_pytest_plugin_refuses_missing_explicit_launcher_context(tmp_path):
    path = tmp_path / "test_synthetic.py"
    path.write_text("def test_synthetic():\n    assert True\n")
    env = preflight.safe_environment(tmp_path, tmp_path)
    run = subprocess.run([sys.executable, "-m", "pytest", "-p", "pytest_platform_contract", str(path)],
        env=env, cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode != 0
    assert "Explicit reviewed launcher context" in run.stderr


@pytest.mark.parametrize("status", ["PASS", "PLATFORM_TRANSFER", "SKIP"])
def test_failed_phase_cannot_hide_behind_claimed_status(status):
    data = outcomes()
    data[TRANSFER].update(status=status, reason="approved_linux_transfer")
    data[TRANSFER]["phases"]["call"] = "failed"
    assert any("failed_phase_hidden" in reason for reason in contract.validate_outcomes(manifest(True), "windows", list(data), data))


@pytest.mark.parametrize("drift", ["plugin", "manifest", "interpreter", "packages", "app", "tests", "pytest_env"])
def test_runtime_origin_checks_reject_drift(tmp_path, monkeypatch, drift):
    # Synthetic metadata only: no application imports, tests or gates are executed.
    import importlib.util
    repo = tmp_path / "candidate"
    metadata = preflight.environment_metadata()
    value = {"repo": str(repo), "environment": metadata,
             "plugin_sha256": contract.digest(contract.__file__),
             "manifest_sha256": contract.digest(HERE / "platform-manifest-v1.json")}
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: SimpleNamespace(origin=str(repo / name / "__init__.py")))
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("PYTEST_PLUGINS", raising=False)
    if drift == "plugin": value["plugin_sha256"] = "0" * 64
    if drift == "manifest": value["manifest_sha256"] = "0" * 64
    if drift == "interpreter": metadata["interpreter_sha256"] = "0" * 64
    if drift == "packages": metadata["packages"] = {}
    if drift in {"app", "tests"}:
        monkeypatch.setattr(importlib.util, "find_spec", lambda name: SimpleNamespace(origin=str(tmp_path / "outside.py" if name == drift else repo / name / "__init__.py")))
    if drift == "pytest_env": monkeypatch.setenv("PYTEST_ADDOPTS", "-k hide_failure")
    with pytest.raises(contract.ContractError):
        contract.verify_runtime_context(value, HERE / "platform-manifest-v1.json")


@pytest.mark.parametrize("drift", ["collection", "source", "outside"])
def test_collection_hook_rejects_exact_inventory_and_source_drift(tmp_path, drift):
    repo = tmp_path / "repo"
    repo.mkdir()
    path = repo / "test_synthetic.py"
    path.write_text("# synthetic source only\n")
    ctx = {"repo": str(repo), "platform": "linux", "expected_collection": [TRANSFER],
           "source_inventory": {"test_synthetic.py": contract.digest(path)}}
    config = SimpleNamespace(getoption=lambda _: False)
    plugin = contract.Contract(config, ctx, manifest(), tmp_path / "ledger.json")
    item = SimpleNamespace(nodeid=TRANSFER, path=path)
    if drift == "collection": ctx["expected_collection"] = []
    if drift == "source": ctx["source_inventory"]["test_synthetic.py"] = "0" * 64
    if drift == "outside": item.path = tmp_path / "outside.py"
    with pytest.raises(pytest.UsageError):
        plugin.pytest_collection_modifyitems(None, config, [item])


@pytest.mark.parametrize("drift", [False, True])
def test_exact_tests_namespace_origin(tmp_path, monkeypatch, drift):
    import importlib.util
    repo = tmp_path / "candidate"
    def spec(name):
        if name == "app": return SimpleNamespace(origin=str(repo / "app" / "__init__.py"))
        locations = [str(repo / "tests")]
        if drift: locations.append(str(tmp_path / "foreign-tests"))
        return SimpleNamespace(origin=None, submodule_search_locations=locations)
    monkeypatch.setattr(importlib.util, "find_spec", spec)
    if drift:
        with pytest.raises(contract.ContractError): contract.source_origins(repo)
    else:
        assert contract.source_origins(repo)["tests"] == {"namespace_locations": [str((repo / "tests").resolve())]}


def test_added_candidate_case_needs_explicit_inventory_approval():
    a, b = ledger(), ledger()
    new_id = "tests/test_synthetic_new.py::test_added"
    b["collected"].append(new_id)
    b["context"]["expected_collection"] = list(b["collected"])
    b["outcomes"][new_id] = copy.deepcopy(b["outcomes"][TRANSFER])
    with pytest.raises(contract.ContractError, match="delta_requires_disposition"):
        comparison.compare_pair(a, b, manifest(True))
    result = comparison.compare_pair(a, b, manifest(True), approved_added_ids=[new_id])
    assert result["differential_no_new_failures"]
    b["outcomes"][new_id]["status"] = "FAIL"
    recalculate(b, manifest(True))
    assert comparison.compare_pair(a, b, manifest(True), approved_added_ids=[new_id])["new_failures"] == [new_id]


@pytest.mark.parametrize("drift", ["draft", "tree", "collection", "plugin", "environment"])
def test_comparison_requires_closed_external_environment_approval(drift):
    value = ledger()
    ctx = value["context"]
    lock = {"schema_version": 1, "gate_identity": contract.GATE, "status": "APPROVED", "approval": None,
            "profiles": {"linux": copy.deepcopy(ctx["environment"])},
            "approved_artifacts": [{"head": ctx["head"], "tree": ctx["tree"]}],
            "collection_inventories": {ctx["tree"]: list(ctx["expected_collection"])},
            "infrastructure_sha256": {"platform-manifest-v1.json": ctx["manifest_sha256"],
                "pytest_platform_contract.py": ctx["plugin_sha256"], "run-linux-platform-gates-v1.sh": ctx["launcher_sha256"]}}
    lock["approval"] = {"authority": "TECH_LEAD_21", "reference": "SYNTHETIC_SELF_TEST_ONLY_NOT_REAL_APPROVAL", "body_sha256": contract.manifest_digest(lock)}
    comparison.validate_context_lock(value, lock, ctx["manifest_sha256"])
    if drift == "draft": lock["status"] = "DRAFT"
    if drift == "tree": ctx["tree"] = "0" * 40
    if drift == "collection": ctx["expected_collection"] = []
    if drift == "plugin": ctx["plugin_sha256"] = "0" * 64
    if drift == "environment": ctx["environment"]["sqlite"] = "foreign"
    with pytest.raises(contract.ContractError): comparison.validate_context_lock(value, lock, ctx["manifest_sha256"])
