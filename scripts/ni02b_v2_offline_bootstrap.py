"""Inert NI-02B V2 / NI-04 offline staging; never switches or deletes live DBs.

Only inspect, prepare and verify are implemented. The separately authorized
operator owns quiescence, the non-atomic pair replacement and service controls.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.network_metadata.canonical import ni01_canonical_json
from app.network_metadata.validation import strict_json, canonical_uuid, ni_format_utc, digest, integer
from app.network_metadata.projection_source import NetworkMetadataProjectionSourceReadService
from app.network_metadata_projection.config import ScopeAdmission
from app.network_metadata_projection.models import ProjectionConfig
from app.network_metadata_projection.repository import ProjectionRepository
from app.network_metadata_projection.schema import validate_schema as validate_projection
from app.network_metadata_projection.validation import validate_reset_floors
from app.network_service_recognition.materialization_repository import ServiceMaterializationRepository
from app.network_service_recognition.materialization_schema import validate_schema as validate_materialization

SUFFIXES = ("", "-wal", "-shm", "-journal")
STATES = frozenset({"PREPARED", "REPLACED_NOT_STARTED", "VERIFIED"})


class BootstrapHold(RuntimeError):
    def __init__(self, code="hold_staging"):
        super().__init__(code)


def exact_path(value):
    path = Path(value)
    if type(value) is not str or not path.is_absolute() or "\0" in value:
        raise BootstrapHold("hold_path_alias")
    # Reject symlinks at any ancestor, not just the database leaf.
    if any(parent.is_symlink() for parent in (path, *path.parents)) or path.resolve() != path:
        raise BootstrapHold("hold_path_alias")
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise BootstrapHold("hold_path_alias")
    return path


def inspect_paths(*, projection_target, materialization_target, keep_paths):
    if type(keep_paths) not in {tuple, list} or not keep_paths:
        raise BootstrapHold("hold_keep_inventory")
    targets = [exact_path(value) for value in (projection_target, materialization_target)]
    keep = [exact_path(value) for value in keep_paths]
    groups = [[exact_path(str(target) + suffix) for suffix in SUFFIXES] for target in targets]
    protected = [exact_path(str(path) + suffix) for path in keep for suffix in SUFFIXES]
    selected = [path for group in groups for path in group]
    if len(set(selected + protected)) != len(selected + protected):
        raise BootstrapHold("hold_protected_path")
    existing = [path for path in selected + protected if path.exists()]
    inodes = [(path.stat().st_dev, path.stat().st_ino) for path in existing]
    if len(set(inodes)) != len(inodes):
        raise BootstrapHold("hold_protected_path")
    return {"selected_groups": [[str(path) for path in group] for group in groups],
            "keep_paths": [str(path) for path in keep], "destructive_action": False,
            "required_barrier": "stop_NI04_then_NI02B_and_drain_ALL_SQLite_readers"}


def file_identity(path):
    path = exact_path(str(path))
    with path.open("rb") as stream:
        hashed = hashlib.file_digest(stream, "sha256") if hasattr(hashlib, "file_digest") else None
        if hashed is None:
            hashed = hashlib.sha256()
            for chunk in iter(lambda: stream.read(65536), b""):
                hashed.update(chunk)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": hashed.hexdigest()}


def inspect_versions(inventory):
    """No SQLite connection/sidecar creation: unqualified on-disk header only.

    A live WAL may contain a newer version. This is never schema admission;
    qualified signature/integrity checks occur only in offline verify.
    """
    versions = []
    for group in inventory["selected_groups"]:
        path = Path(group[0])
        header = b""
        if path.exists():
            with path.open("rb") as stream:
                header = stream.read(100)
        version = int.from_bytes(header[60:64], "big") if len(header) == 100 and header[:16] == b"SQLite format 3\0" else None
        versions.append({"path": str(path), "header_user_version": version, "schema_admitted": False,
                         "wal_may_contain_newer_state": Path(str(path)+"-wal").exists()})
    return versions


@contextmanager
def read_only(path):
    connection = sqlite3.connect(exact_path(str(path)).as_uri() + "?mode=ro", uri=True, timeout=.5, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        for pragma in ("query_only=ON", "foreign_keys=ON", "busy_timeout=500"):
            connection.execute("PRAGMA " + pragma)
        connection.execute("BEGIN")
        yield connection
    finally:
        connection.close()


def prepare(*, staging_dir, source_path, projection_target, materialization_target,
            keep_paths, admission_json, writers_stopped, readers_drained):
    if writers_stopped is not True or readers_drained is not True:
        raise BootstrapHold("hold_reader_drain")
    admission = ScopeAdmission(admission_json)
    source = exact_path(source_path)
    if str(source) not in keep_paths:
        raise BootstrapHold("hold_keep_inventory")
    inventory = inspect_paths(projection_target=projection_target,
        materialization_target=materialization_target, keep_paths=keep_paths)
    stage = Path(staging_dir)
    if not stage.is_absolute() or stage.exists() or stage.resolve() != stage or any(p.is_symlink() for p in stage.parents):
        raise BootstrapHold("hold_staging_path")
    if any(stage == Path(path).parent or stage in Path(path).parents for group in inventory["selected_groups"] for path in group):
        raise BootstrapHold("hold_staging_path")
    floors = NetworkMetadataProjectionSourceReadService(str(source)).read_reset_snapshot(admission=admission)
    epoch, at = str(uuid.uuid4()), ni_format_utc(datetime.now(timezone.utc))
    # Only new staging paths are writable. No existing target is ever opened RW.
    stage.mkdir(mode=0o700)
    projection = stage / "network_metadata_projection.sqlite3"
    materialization = stage / "network_service_intelligence.sqlite3"
    repo = ProjectionRepository(ProjectionConfig(enabled=True, db_path=str(projection),
        source_db_path=str(source), scope_admission_json=admission.canonical),
        install_service_recognition_extension=True,
        reset_bootstrap=dict(floors=floors, reset_epoch_id=epoch, reset_at_utc=at))
    store = ServiceMaterializationRepository(str(materialization))
    try:
        repo.initialize()
        if validate_projection(repo.connection, integrity=True) != "CORE_PLUS_EXTENSION_V1":
            raise BootstrapHold()
        store.initialize()
        validate_materialization(store.connection, integrity=True)
    finally:
        repo.close()
        store.close()
    manifest = {"schema_version": 1, "state": "PREPARED", "reset_epoch_id": epoch,
        "reset_at_utc": at, "admission_digest": admission.digest,
        "source_path": str(source), "source_snapshot_digest": hashlib.sha256(ni01_canonical_json(sorted(floors,
            key=lambda item: item["source_generation_id"]))).hexdigest(),
        "projection_target": projection_target, "materialization_target": materialization_target,
        "keep_paths": list(keep_paths), "projection": file_identity(projection),
        "materialization": file_identity(materialization)}
    manifest_path = stage / "prepared-pair.json"
    encoded = ni01_canonical_json(manifest)
    with manifest_path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    # A successful prepare is not an execution/activation token.
    verify(manifest_path=str(manifest_path), admission_json=admission.canonical)
    return manifest


def verify(*, manifest_path, admission_json, expected_manifest_sha256=None, expected_inventory=None):
    admission = ScopeAdmission(admission_json)
    path = exact_path(manifest_path)
    if path.stat().st_size > 65536:
        raise BootstrapHold("hold_pair_manifest")
    if expected_manifest_sha256 is not None:
        digest(expected_manifest_sha256)
        if file_identity(path)["sha256"] != expected_manifest_sha256:
            raise BootstrapHold("hold_pair_manifest")
    manifest = strict_json(path.read_text(encoding="utf-8"))
    required = {"schema_version", "state", "reset_epoch_id", "reset_at_utc", "admission_digest", "source_path",
        "source_snapshot_digest", "projection_target", "materialization_target", "keep_paths", "projection", "materialization"}
    if (type(manifest) is not dict or set(manifest) != required or type(manifest["schema_version"]) is not int
            or manifest["schema_version"] != 1 or manifest["state"] not in STATES
            or manifest["admission_digest"] != admission.digest):
        raise BootstrapHold("hold_pair_manifest")
    canonical_uuid(manifest["reset_epoch_id"], 4)
    digest(manifest["source_snapshot_digest"])
    if expected_inventory is not None and (expected_inventory["selected_groups"] != [
            [manifest[name] + suffix for suffix in SUFFIXES] for name in ("projection_target", "materialization_target")]
            or expected_inventory["keep_paths"] != manifest["keep_paths"]):
        raise BootstrapHold("hold_pair_manifest")
    inspect_paths(projection_target=manifest["projection_target"], materialization_target=manifest["materialization_target"],
                  keep_paths=manifest["keep_paths"])
    if manifest["source_path"] not in manifest["keep_paths"]:
        raise BootstrapHold("hold_keep_inventory")
    staged = []
    for name in ("projection", "materialization"):
        entry = manifest[name]
        if type(entry) is not dict or set(entry) != {"path", "bytes", "sha256"}:
            raise BootstrapHold("hold_pair_manifest")
        integer(entry["bytes"], 1)
        digest(entry["sha256"])
        wal = Path(entry["path"] + "-wal")
        journal = Path(entry["path"] + "-journal")
        # A query-only WAL connection may create an empty WAL/shared-index. They
        # are not database contents; any actual outstanding journal is a HOLD.
        if (file_identity(entry["path"]) != entry or (wal.exists() and wal.stat().st_size != 0)
                or journal.exists()):
            raise BootstrapHold("hold_pair_identity")
        staged.append(entry["path"])
    inspect_paths(projection_target=staged[0], materialization_target=staged[1], keep_paths=manifest["keep_paths"])
    if len(set(staged + manifest["keep_paths"])) != len(staged + manifest["keep_paths"]):
        raise BootstrapHold("hold_protected_path")
    if manifest["state"] != "PREPARED" and staged != [manifest["projection_target"], manifest["materialization_target"]]:
        raise BootstrapHold("hold_pair_identity")
    with read_only(staged[0]) as connection:
        if validate_projection(connection, integrity=True) != "CORE_PLUS_EXTENSION_V1":
            raise BootstrapHold()
        floors = validate_reset_floors(connection, admission)
        epoch = connection.execute("SELECT * FROM projection_source_reset_epoch").fetchone()
        if (epoch["reset_epoch_id"] != manifest["reset_epoch_id"] or epoch["reset_at_utc"] != manifest["reset_at_utc"]
                or epoch["source_snapshot_digest"] != manifest["source_snapshot_digest"]):
            raise BootstrapHold("hold_pair_identity")
        for table in ("projection_runs", "device_network_metadata_edges", "projection_source_checkpoints",
                      "projection_pending_attribution", "projection_registry_identities", "projection_site_mac_bindings",
                      "projection_registry_binding_events", "projection_service_recognition_feed", "projection_registry_binding_change_index"):
            if connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                raise BootstrapHold("hold_nonempty_store")
    with read_only(staged[1]) as connection:
        validate_materialization(connection, integrity=True)
        for table in ("service_materialization_generations", "service_recognition_observations", "device_service_rollups",
                      "device_materialization_state", "service_materialization_checkpoints", "service_binding_replay_jobs"):
            if connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                raise BootstrapHold("hold_nonempty_store")
    reader = NetworkMetadataProjectionSourceReadService(manifest["source_path"])
    # Retention may have removed the old tail. Monotonic progress and immutable
    # canonical lineage, not a nearest row or raw file length, prove the floor.
    for floor in floors:
        generation = reader.get_source_progress(floor["source_generation_id"])
        if (generation.generation_start_offset != floor["generation_start_offset"]
                or generation.committed_byte_offset < floor["committed_byte_offset"]
                or generation.capture_scope_binding_digest != floor["capture_scope_binding_digest"]
                or generation.binding_valid_from_utc != floor["binding_valid_from_utc"]):
            raise BootstrapHold("hold_source_floor")
    return {"schema_version": 1, "state": "VERIFIED" if manifest["state"] != "PREPARED" else "PREPARED",
            "reset_epoch_id": manifest["reset_epoch_id"], "floor_count": len(floors),
            "destructive_action": False, "activation_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "dry-run", "prepare", "verify"), nargs="?", default="inspect")
    parser.add_argument("--projection-target", required=True)
    parser.add_argument("--materialization-target", required=True)
    parser.add_argument("--keep-path", action="append", required=True)
    parser.add_argument("--source-path")
    parser.add_argument("--admission-file")
    parser.add_argument("--staging-dir")
    parser.add_argument("--manifest")
    parser.add_argument("--manifest-sha256", help="externally retained SHA256 of the reviewed immutable pair manifest")
    parser.add_argument("--writers-stopped", action="store_true")
    parser.add_argument("--readers-drained", action="store_true")
    args = parser.parse_args(argv)
    try:
        inventory = inspect_paths(projection_target=args.projection_target,
            materialization_target=args.materialization_target, keep_paths=args.keep_path)
        if args.command in {"inspect", "dry-run"}:
            result = dict(inventory, current_header_versions=inspect_versions(inventory),
                reset_boundary="single_NI01_normalized_tail_snapshot_not_yet_taken",
                scope_admission="not_supplied", schema_admitted=False)
            if args.admission_file is not None:
                admission_path = exact_path(args.admission_file)
                if admission_path.stat().st_size > 65536:
                    raise BootstrapHold("hold_scope_admission")
                admitted = ScopeAdmission(admission_path.read_text(encoding="utf-8"))
                result.update(scope_admission="typed_operator_statement_only", admission_digest=admitted.digest,
                              scope_count=len(admitted.bindings))
        else:
            admission_path = exact_path(args.admission_file)
            if admission_path.stat().st_size > 65536:
                raise BootstrapHold("hold_scope_admission")
            admission_json = admission_path.read_text(encoding="utf-8")
            if args.command == "prepare":
                result = prepare(staging_dir=args.staging_dir, source_path=args.source_path,
                    projection_target=args.projection_target, materialization_target=args.materialization_target,
                    keep_paths=args.keep_path, admission_json=admission_json,
                    writers_stopped=args.writers_stopped, readers_drained=args.readers_drained)
            else:
                if args.manifest_sha256 is None:
                    raise BootstrapHold("hold_pair_manifest")
                result = verify(manifest_path=args.manifest, admission_json=admission_json,
                                expected_manifest_sha256=args.manifest_sha256, expected_inventory=inventory)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        print("ni02b_v2_bootstrap_hold")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
