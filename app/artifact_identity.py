"""Immutable startup identity for code loaded from the repository checkout."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


_SHA = re.compile(r"[0-9a-f]{40}")
UTC = timezone.utc


class ArtifactIdentityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LoadedArtifactIdentity:
    artifact_sha: str
    artifact_tree: str
    service_name: str
    process_started_at: str

    def __post_init__(self) -> None:
        if (
            _SHA.fullmatch(self.artifact_sha) is None
            or _SHA.fullmatch(self.artifact_tree) is None
            or not isinstance(self.service_name, str)
            or not self.service_name
            or len(self.service_name) > 128
            or _canonical_utc(self.process_started_at) != self.process_started_at
        ):
            raise ArtifactIdentityError("loaded artifact identity is unavailable")

    def safe_fields(self) -> dict[str, str]:
        return {
            "artifact_sha": self.artifact_sha,
            "artifact_tree": self.artifact_tree,
            "service_name": self.service_name,
            "process_started_at": self.process_started_at,
        }

    def json_line(
        self,
        *,
        event: str = "captivportal_loaded_artifact_identity",
    ) -> str:
        payload = {"event": event, **self.safe_fields()}
        return json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )


def capture_loaded_artifact_identity(service_name: str) -> LoadedArtifactIdentity:
    started = datetime.now(UTC).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
    root = Path(__file__).resolve().parents[1]
    try:
        sha = _git(root, "rev-parse", "--verify", "HEAD")
        tree = _git(root, "rev-parse", "--verify", "HEAD^{tree}")
        status = _git(
            root, "status", "--porcelain=v1", "--untracked-files=normal"
        )
        if status.strip():
            raise ValueError
        return LoadedArtifactIdentity(
            artifact_sha=sha.strip(),
            artifact_tree=tree.strip(),
            service_name=service_name,
            process_started_at=started,
        )
    except Exception as exc:
        raise ArtifactIdentityError(
            "loaded artifact identity is unavailable"
        ) from exc


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=2.0,
    )
    return completed.stdout


def _canonical_utc(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return None
    canonical = parsed.replace(tzinfo=UTC).isoformat(timespec="milliseconds")
    return canonical.replace("+00:00", "Z")
