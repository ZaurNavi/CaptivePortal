"""External preparation-only platform contract; DRAFT cannot transfer tests.

Independent gate identity. Never rewrites failures into PASS or historical V7.
No application monkeypatches, imports, fixtures, SQL, or environment rereads.
"""
import hashlib
import json
import os
from pathlib import Path

import pytest

GATE = "TEST-GATE-PLATFORM-01/P1-v1"
PROTECTED = (
    "tests/analytics/test_current_traffic.py::test_sql_integrity_aggregates_reject_corrupt_rate_and_null_values[wired_download_mbps-inf-bad_rate_count]",
    "tests/test_auth_retry_frontend.py::test_lost_retry_response_reconciles_active_run",
    "tests/visitor_registry/test_device_registry_worker.py::test_long_full_audit_runs_in_worker_and_does_not_block_start",
    "tests/visitor_registry/test_device_registry_worker.py::test_start_exposes_initializing_until_full_audit_finishes[ready]",
    "tests/visitor_registry/test_device_registry_worker.py::test_start_exposes_initializing_until_full_audit_finishes[stopping]",
    "tests/admin_web/test_home_health.py::test_unavailable_analytics_is_one_component_not_health_503",
)


class ContractError(ValueError):
    pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exact(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ContractError("closed_schema")


def strict_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError("duplicate_json_member")
            result[key] = value
        return result
    def constant(_):
        raise ContractError("non_finite_json")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def node_id(value):
    if not isinstance(value, str) or not value.startswith("tests/") or "::test_" not in value:
        raise ContractError("node_id")
    path = value.split("::", 1)[0]
    if "\\" in value or any(p in {"", ".", ".."} for p in path.split("/")) or not path.endswith(".py"):
        raise ContractError("node_id")
    return value


def manifest_digest(manifest):
    # Approval binds the semantic body, excluding the approval itself.
    body = {key: value for key, value in manifest.items() if key != "approval"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_manifest(value, *, require_approved=False):
    exact(value, {"schema_version", "gate_identity", "status", "approval", "protected_windows_ids", "transfers", "permitted_skips"})
    if type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["gate_identity"] != GATE:
        raise ContractError("manifest_version")
    if value["protected_windows_ids"] != list(PROTECTED) or value["status"] not in {"DRAFT", "APPROVED"}:
        raise ContractError("protected_or_status")
    if not isinstance(value["transfers"], list) or not isinstance(value["permitted_skips"], list):
        raise ContractError("manifest_lists")
    seen = set()
    for row in value["transfers"]:
        exact(row, {"node_id", "linux_node_id", "cause", "source", "evidence"})
        identifier = node_id(row["node_id"])
        if identifier in seen or identifier in PROTECTED or row["linux_node_id"] != identifier:
            raise ContractError("duplicate_or_protected_transfer")
        seen.add(identifier)
        if not isinstance(row["cause"], str) or not row["cause"].strip():
            raise ContractError("causal_justification")
        for key in ("source", "evidence"):
            exact(row[key], {"path", "sha256", "reference"})
            ref = row[key]
            if not all(isinstance(ref[k], str) and ref[k] for k in ref):
                raise ContractError("provenance")
            if len(ref["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in ref["sha256"]):
                raise ContractError("provenance_digest")
    for row in value["permitted_skips"]:
        exact(row, {"node_id", "platforms", "reason", "authority"})
        identifier = node_id(row["node_id"])
        if identifier in seen or identifier in PROTECTED or not row["reason"] or not row["authority"]:
            raise ContractError("skip_contract")
        if row["platforms"] not in (["windows"], ["linux"], ["windows", "linux"]):
            raise ContractError("skip_platform")
        seen.add(identifier)
    if value["status"] == "DRAFT":
        if value["approval"] is not None or require_approved:
            raise ContractError("draft_manifest_not_admitted")
    else:
        exact(value["approval"], {"authority", "reference", "body_sha256"})
        approval = value["approval"]
        if approval["authority"] != "TECH_LEAD_21" or not approval["reference"] or approval["body_sha256"] != manifest_digest(value):
            raise ContractError("manifest_approval_binding")
    return value


def validate_outcomes(manifest, platform, collected, outcomes, deselected=(), collection_errors=()):
    """No baseline waiver. Windows transfer is debt until Linux counterpart PASS."""
    validate_manifest(manifest)
    if platform not in {"windows", "linux"} or len(collected) != len(set(collected)):
        raise ContractError("platform_or_collection")
    reasons = []
    identifiers = set(collected)
    if deselected:
        reasons.append("deselection_forbidden")
    if collection_errors:
        reasons.append("collection_errors")
    if identifiers != set(outcomes):
        reasons.append("missing_or_extra_outcomes")
    missing = set(PROTECTED) - identifiers
    if missing:
        reasons.append("protected_missing")
    transfer_ids = {r["node_id"] for r in manifest["transfers"]}
    if transfer_ids - identifiers:
        reasons.append("mandatory_transfer_missing")
    allowed = {r["node_id"]: r for r in manifest["permitted_skips"] if platform in r["platforms"]}
    for identifier, row in outcomes.items():
        exact(row, {"status", "phases", "reason"})
        status = row["status"]
        phases = row["phases"]
        if (not isinstance(phases, dict) or not set(phases) <= {"setup", "call", "teardown"}
                or any(v not in {"passed", "failed", "skipped"} for v in phases.values())):
            raise ContractError("outcome_phases")
        if "failed" in phases.values() and status not in {"FAIL", "ERROR"}:
            reasons.append("failed_phase_hidden:" + identifier)
        if status in {"SKIP", "PLATFORM_TRANSFER"} and "skipped" not in phases.values():
            reasons.append("skip_without_skipped_phase:" + identifier)
        if identifier in PROTECTED and status != "PASS":
            reasons.append("protected_not_pass:" + identifier)
        if status in {"FAIL", "ERROR", "XFAIL", "XPASS", "INCOMPLETE"}:
            reasons.append("strict_failure:" + identifier)
        elif status == "PLATFORM_TRANSFER":
            if platform != "windows" or manifest["status"] != "APPROVED" or identifier not in transfer_ids or row["reason"] != "approved_linux_transfer":
                reasons.append("unapproved_transfer:" + identifier)
        elif status == "SKIP":
            if identifier not in allowed or row["reason"] != allowed[identifier]["reason"]:
                reasons.append("unexpected_skip:" + identifier)
        elif status != "PASS":
            reasons.append("unknown_outcome:" + identifier)
        if platform == "linux" and identifier in transfer_ids and status != "PASS":
            reasons.append("linux_mandatory_not_pass:" + identifier)
        if status == "PASS" and row["phases"] != {"setup": "passed", "call": "passed", "teardown": "passed"}:
            reasons.append("incomplete_pass:" + identifier)
    return sorted(set(reasons))


def pytest_addoption(parser):
    group = parser.getgroup("platform-contract")
    group.addoption("--platform-contract-context")
    group.addoption("--platform-contract-manifest")
    group.addoption("--platform-contract-ledger")
    group.addoption("--platform-contract-transfer", action="store_true", default=False)


def source_origins(repo):
    from importlib.util import find_spec
    repo = Path(repo).resolve()
    result = {}
    for name in ("app", "tests"):
        spec = find_spec(name)
        if spec is None:
            raise ContractError("application_source_origin:" + name)
        if spec.origin is not None:
            origin = Path(spec.origin).resolve()
            if origin != repo / name / "__init__.py":
                raise ContractError("application_source_origin:" + name)
            result[name] = str(origin)
        else:
            locations = [Path(p).resolve() for p in (spec.submodule_search_locations or ())]
            if name != "tests" or locations != [repo / "tests"]:
                raise ContractError("application_source_origin:" + name)
            result[name] = {"namespace_locations": [str(p) for p in locations]}
    return result


def verify_runtime_context(context, manifest_path):
    import sys
    import platform
    import sqlite3
    import importlib.metadata
    if digest(__file__) != context["plugin_sha256"] or digest(manifest_path) != context["manifest_sha256"]:
        raise ContractError("plugin_or_manifest_origin")
    source_origins(context["repo"])
    expected = context["environment"]
    if (str(Path(sys.executable).resolve()) != expected["interpreter"]
            or digest(sys.executable) != expected["interpreter_sha256"]):
        raise ContractError("interpreter_origin")
    with sqlite3.connect(":memory:") as connection:
        options = sorted(row[0] for row in connection.execute("PRAGMA compile_options"))
    packages = dict(sorted((d.metadata["Name"].lower(), d.version) for d in importlib.metadata.distributions() if d.metadata.get("Name")))
    if (platform.python_version() != expected["python"] or sqlite3.sqlite_version != expected["sqlite"]
            or options != expected["sqlite_compile_options"] or packages != expected["packages"]):
        raise ContractError("interpreter_environment_drift")
    if (os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") != "1"
            or "PYTEST_ADDOPTS" in os.environ or "PYTEST_PLUGINS" in os.environ):
        raise ContractError("pytest_environment_origin")


def pytest_configure(config):
    context_path = config.getoption("platform_contract_context")
    manifest_path = config.getoption("platform_contract_manifest")
    ledger_path = config.getoption("platform_contract_ledger")
    if not all((context_path, manifest_path, ledger_path)):
        raise pytest.UsageError("Explicit reviewed launcher context/manifest/ledger required")
    try:
        context = strict_json(context_path)
        exact(context, {"schema_version", "gate_identity", "platform", "repo", "head", "tree", "manifest_sha256", "plugin_sha256", "environment", "source_inventory", "expected_collection", "launcher_sha256"})
        if context["gate_identity"] != GATE or context["schema_version"] != 1:
            raise ContractError("context_identity")
        if context["platform"] != ("windows" if os.name == "nt" else "linux"):
            raise ContractError("platform_origin")
        verify_runtime_context(context, manifest_path)
        manifest = validate_manifest(strict_json(manifest_path), require_approved=config.getoption("platform_contract_transfer"))
    except Exception as error:
        raise pytest.UsageError("Platform contract rejected: " + str(error)) from None
    config._platform_contract = Contract(config, context, manifest, ledger_path)
    config.pluginmanager.register(config._platform_contract, "closed_platform_ledger")


class Contract:
    def __init__(self, config, context, manifest, ledger_path):
        self.config, self.context, self.manifest = config, context, manifest
        self.ledger_path = Path(ledger_path)
        if self.ledger_path.exists():
            raise pytest.UsageError("Immutable ledger output already exists")
        self.collected, self.deselected, self.errors, self.reports = [], [], [], {}

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, session, config, items):
        self.collected = [node_id(item.nodeid.replace("\\", "/")) for item in items]
        if self.collected != self.context["expected_collection"]:
            raise pytest.UsageError("Frozen collection inventory drift")
        for item in items:
            path = Path(item.path).resolve()
            try:
                relative = path.relative_to(Path(self.context["repo"]).resolve()).as_posix()
            except ValueError:
                raise pytest.UsageError("Test source outside candidate") from None
            if self.context["source_inventory"].get(relative) != digest(path):
                raise pytest.UsageError("Test source identity drift")
        transfers = {r["node_id"] for r in self.manifest["transfers"]}
        if config.getoption("platform_contract_transfer") and self.context["platform"] == "windows":
            validate_manifest(self.manifest, require_approved=True)
            for item in items:
                if item.nodeid.replace("\\", "/") in transfers:
                    item.add_marker(pytest.mark.skip(reason="approved_linux_transfer"))

    def pytest_deselected(self, items):
        self.deselected.extend(item.nodeid for item in items)

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append(report.nodeid)

    def pytest_runtest_logreport(self, report):
        self.reports.setdefault(report.nodeid.replace("\\", "/"), []).append(report)

    def pytest_sessionfinish(self, session, exitstatus):
        outcomes = {}
        for identifier, reports in self.reports.items():
            phases = {r.when: r.outcome for r in reports}
            reason = ""
            if len(phases) != len(reports):
                status = "ERROR"  # retries/duplicate outcomes cannot replace a failed attempt
            elif any(getattr(r, "wasxfail", False) for r in reports):
                status = "XFAIL" if any(r.skipped for r in reports) else "XPASS"
            elif any(r.failed for r in reports):
                status = "FAIL"
            elif any(r.skipped for r in reports):
                skipped = next(r for r in reports if r.skipped)
                detail = skipped.longrepr[2] if isinstance(skipped.longrepr, tuple) else str(skipped.longrepr)
                reason = detail.removeprefix("Skipped: ")
                status = "PLATFORM_TRANSFER" if reason == "approved_linux_transfer" else "SKIP"
            else:
                status = "PASS" if phases == {"setup": "passed", "call": "passed", "teardown": "passed"} else "INCOMPLETE"
            outcomes[identifier] = {"status": status, "phases": phases, "reason": reason}
        failures = validate_outcomes(self.manifest, self.context["platform"], self.collected, outcomes, self.deselected, self.errors)
        if exitstatus:
            failures.append("pytest_exit_nonzero:" + str(exitstatus))
        ledger = {"schema_version": 1, "gate_identity": GATE, "context": self.context,
                  "collected": self.collected, "outcomes": outcomes, "deselected": self.deselected,
                  "collection_errors": self.errors, "pytest_exit_code": int(exitstatus),
                  "contract_failures": sorted(set(failures)), "status": "FAIL" if failures else "PASS"}
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("x", encoding="utf-8") as output:
            json.dump(ledger, output, sort_keys=True, indent=2)
        if failures:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
