from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

import run
from app.artifact_identity import (
    ArtifactIdentityError,
    LoadedArtifactIdentity,
    capture_loaded_artifact_identity,
)


SHA = "a" * 40
TREE = "b" * 40


def _mock_git(monkeypatch, *, sha=SHA, tree=TREE, status=""):
    calls = []
    answers = iter((sha + "\n", tree + "\n", status))

    def execute(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return SimpleNamespace(stdout=next(answers))

    monkeypatch.setattr(subprocess, "run", execute)
    return calls


def test_artifact_identity_clean_mocked_git_contract(monkeypatch):
    # Artifact identity Git behavior is unit-tested through mocked subprocess
    # results; the Coder candidate worktree cleanliness is not part of this test.
    calls = _mock_git(monkeypatch)
    identity = capture_loaded_artifact_identity("service")
    assert identity.artifact_sha == SHA
    assert identity.artifact_tree == TREE
    assert identity.service_name == "service"
    assert identity.process_started_at.endswith("Z")
    assert identity.safe_fields() == {
        "artifact_sha": SHA,
        "artifact_tree": TREE,
        "service_name": "service",
        "process_started_at": identity.process_started_at,
    }
    payload = json.loads(identity.json_line())
    assert set(payload) == {
        "event", "artifact_sha", "artifact_tree", "service_name",
        "process_started_at",
    }
    assert "\n" not in identity.json_line()
    assert [call[0][3:] for call in calls] == [
        ["rev-parse", "--verify", "HEAD"],
        ["rev-parse", "--verify", "HEAD^{tree}"],
        ["status", "--porcelain=v1", "--untracked-files=normal"],
    ]
    for _arguments, kwargs in calls:
        assert kwargs == {
            "check": True,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.DEVNULL,
            "text": True,
            "timeout": 2.0,
        }


@pytest.mark.parametrize(
    "status",
    [" M tracked.py\n", "M  staged.py\n", " D deleted.py\n", "?? new.py\n"],
)
def test_artifact_identity_rejects_dirty_mocked_status_without_path_leak(
    monkeypatch, status
):
    _mock_git(monkeypatch, status=status)
    with pytest.raises(ArtifactIdentityError) as raised:
        capture_loaded_artifact_identity("service")
    assert str(raised.value) == "loaded artifact identity is unavailable"
    assert status.strip() not in str(raised.value)


@pytest.mark.parametrize(
    "sha,tree",
    [
        ("A" * 40, TREE),
        ("a" * 39, TREE),
        ("z" * 40, TREE),
        (SHA, "B" * 40),
        (SHA, "b" * 39),
    ],
)
def test_artifact_identity_rejects_invalid_hashes(monkeypatch, sha, tree):
    _mock_git(monkeypatch, sha=sha, tree=tree)
    with pytest.raises(ArtifactIdentityError, match="^loaded artifact identity is unavailable$"):
        capture_loaded_artifact_identity("service")


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.CalledProcessError(1, ["git"]),
        subprocess.TimeoutExpired(["git"], 2.0),
    ],
)
def test_artifact_identity_sanitizes_git_failures(monkeypatch, failure):
    def execute(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(subprocess, "run", execute)
    with pytest.raises(ArtifactIdentityError, match="^loaded artifact identity is unavailable$"):
        capture_loaded_artifact_identity("service")


def test_loaded_artifact_identity_is_immutable():
    identity = LoadedArtifactIdentity(
        SHA, TREE, "service", "2026-09-11T12:00:00.000Z"
    )
    with pytest.raises((AttributeError, TypeError)):
        identity.artifact_sha = "c" * 40
    assert identity.artifact_sha == SHA


def test_run_main_identity_failure_precedes_all_startup(monkeypatch):
    events = []
    monkeypatch.setattr(
        run,
        "capture_loaded_artifact_identity",
        lambda _name: (_ for _ in ()).throw(ArtifactIdentityError("secret")),
    )
    monkeypatch.setattr(run.logger, "critical", lambda message: events.append(message))
    monkeypatch.setattr(run.atexit, "register", lambda *_args: pytest.fail("atexit reached"))
    monkeypatch.setattr(run.signal, "signal", lambda *_args: pytest.fail("signal reached"))
    monkeypatch.setattr(run, "get_settings", lambda: pytest.fail("settings reached"))
    monkeypatch.setattr(run, "create_controller", lambda: pytest.fail("controller reached"))

    with pytest.raises(SystemExit) as raised:
        run.main()
    assert raised.value.code == 1
    assert events == ["captivportal_artifact_identity_startup_failed"]


def test_run_main_logs_identity_before_normal_startup(monkeypatch):
    events = []
    identity = LoadedArtifactIdentity(
        SHA, TREE, "captive-portal.service", "2026-09-11T12:00:00.000Z"
    )
    monkeypatch.setattr(
        run,
        "capture_loaded_artifact_identity",
        lambda name: events.append(("capture", name)) or identity,
    )
    monkeypatch.setattr(run.logger, "info", lambda message, *_args: events.append(("log", message)))
    monkeypatch.setattr(
        run,
        "get_settings",
        lambda: (_ for _ in ()).throw(RuntimeError("startup sentinel")),
    )
    monkeypatch.setattr(run.atexit, "register", lambda *_args: None)
    monkeypatch.setattr(run.signal, "signal", lambda *_args: None)

    with pytest.raises(RuntimeError, match="startup sentinel"):
        run.main()
    assert events[:3] == [
        ("capture", "captive-portal.service"),
        ("log", identity.json_line()),
        ("log", "Starting Captive Portal"),
    ]
