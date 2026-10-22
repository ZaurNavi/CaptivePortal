import copy
import json
import stat
from types import SimpleNamespace

import pytest

from app.admin_web import operations_inventory as inventory


def manifest():
    return {
        "schema_version": "admin.db-services.bindings.v1",
        "services": [{"id": item.id, "intent": "run"} for item in inventory.SERVICES],
        "databases": [{"id": item.id, "intent": "expected", "path":
            (inventory.APPROVED_ROOTS[1] if item.id in {"sensor_spool", "network_attribution"}
             else inventory.APPROVED_ROOTS[0]) + "/" + item.filename} for item in inventory.STORES],
    }


def resolved(**changes):
    value = manifest()
    value.update(changes)
    return inventory.parse_inventory(json.dumps(value).encode())


def test_exact_catalog_order_ownership_immutable_and_no_bridge():
    assert tuple(s.id for s in inventory.SERVICES) == (
        "portal_core", "fingerprint_evidence", "fingerprint_sensor", "fingerprint_suricata",
        "fingerprint_classification", "network_metadata", "network_metadata_projection",
        "network_service_recognition", "traffic_projection")
    assert tuple(s.id for s in inventory.STORES) == (
        "portal_counter", "public_traffic", "visitor_registry", "visits", "observations", "current_state",
        "traffic_projection", "fingerprint_evidence", "fingerprint_classification", "fingerprint_control_plane",
        "fingerprint_integration", "network_metadata", "network_attribution", "network_metadata_projection",
        "network_service_intelligence", "settings", "sensor_spool")
    assert len({s.id for s in inventory.SERVICES}) == 9
    assert len({s.id for s in inventory.STORES}) == 17
    assert all("bridge" not in s.unit for s in inventory.SERVICES)
    control, integration = inventory.STORES[9:11]
    assert control.services == () and integration.services == ("portal_core", "fingerprint_classification")
    assert integration.writers == ("fingerprint_integration_submitter", "fingerprint_integration_worker")
    bound = resolved()
    with pytest.raises(TypeError):
        bound.paths["settings"] = "/bad"
    assert inventory.MANIFEST_PATH == "/etc/captiveportal/admin-db-services-v1.json"


@pytest.mark.parametrize("which", ["services", "databases"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown", "bad-intent", "extra-field", "not-list"])
def test_manifest_closed_ids_fields_and_intents(which, mutation):
    value = manifest()
    if mutation == "missing": value[which].pop()
    elif mutation == "duplicate": value[which][-1] = copy.deepcopy(value[which][0])
    elif mutation == "unknown": value[which][0]["id"] = "arbitrary"
    elif mutation == "bad-intent": value[which][0]["intent"] = "active"
    elif mutation == "extra-field": value[which][0]["token"] = "SYNTHETIC_CANARY"
    else: value[which] = {}
    with pytest.raises(inventory.InventoryUnavailable, match="^inventory_unavailable$"):
        resolved(**value)


@pytest.mark.parametrize("raw", [b"[]", b"null", b"{}", b"\xff", b"{bad", b"{}" + b" " * 32768,
    b'{"schema_version":"x","schema_version":"y"}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}'],
    ids=["array", "null", "object", "invalid-utf8", "bad-json", "oversize", "duplicate-key",
         "nan", "infinity", "negative-infinity"])
def test_invalid_json_length_duplicate_members_and_constants(raw):
    with pytest.raises(inventory.InventoryUnavailable):
        inventory.parse_inventory(raw)


@pytest.mark.parametrize("path", ["relative.sqlite3", "/etc/private.sqlite3", "/opt/CaptivePortal/data/sub/a.db",
    "/opt/CaptivePortal/data/../a.db", "/opt/CaptivePortal/data/./a.db", "/opt/CaptivePortal/data//a.db",
    "//opt/CaptivePortal/data/a.db", "/opt/CaptivePortal/data/a\n.db", "/opt/CaptivePortal/data/a\x00.db",
    "/opt/CaptivePortal/data/", "/opt/CaptivePortal/data/.hidden", "/opt/CaptivePortal/data/a" + "x" * 520])
def test_path_rejections(path):
    value = manifest()
    value["databases"][0]["path"] = path
    with pytest.raises(inventory.InventoryUnavailable): resolved(**value)


def test_duplicate_path_extra_top_level_and_wrong_version():
    value = manifest()
    value["databases"][1]["path"] = value["databases"][0]["path"]
    with pytest.raises(inventory.InventoryUnavailable): resolved(**value)
    with pytest.raises(inventory.InventoryUnavailable): resolved(token="SYNTHETIC_CANARY")
    with pytest.raises(inventory.InventoryUnavailable): resolved(schema_version="v2")


@pytest.mark.parametrize("mode,uid", [(stat.S_IFLNK | 0o755, 0), (stat.S_IFREG | 0o644, 0),
    (stat.S_IFDIR | 0o777, 0), (stat.S_IFDIR | 0o775, 0), (stat.S_IFDIR | 0o755, 1000)])
def test_trusted_manifest_parent_rejects_symlink_kind_owner_and_write_permissions(mode, uid):
    class Directory:
        parents = ()
        def lstat(self): return SimpleNamespace(st_mode=mode, st_uid=uid)
    with pytest.raises(inventory.InventoryUnavailable): inventory._trusted_directory(Directory())


def test_trusted_parent_positive():
    class Directory:
        parents = ()
        def lstat(self): return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
    inventory._trusted_directory(Directory())


@pytest.mark.parametrize("case", ["valid", "missing", "symlink", "nonregular", "unsafe-owner", "unsafe-mode", "oversize"])
def test_loader_bounded_nofollow_regular_root_owned_file_once(monkeypatch, case):
    raw = json.dumps(manifest()).encode()
    calls = []
    def opened(path, flags):
        calls.append((path, flags))
        if case == "missing": raise FileNotFoundError()
        if case == "symlink": raise OSError("no-follow synthetic")
        return 91
    fake_os = SimpleNamespace(name="posix", O_NOFOLLOW=0x20000, O_RDONLY=0, O_NONBLOCK=0x800,
        open=opened, fstat=lambda fd: SimpleNamespace(st_mode=(stat.S_IFIFO if case == "nonregular" else stat.S_IFREG) | (0o666 if case == "unsafe-mode" else 0o640),
            st_uid=1000 if case == "unsafe-owner" else 0, st_size=32769 if case == "oversize" else len(raw)),
        close=lambda fd: calls.append(("close", fd)))
    chunks = iter([raw, b""])
    fake_os.read = lambda fd, amount: next(chunks)
    monkeypatch.setattr(inventory, "os", fake_os)
    monkeypatch.setattr(inventory, "_trusted_directory", lambda p: None)
    class FakePath:
        def __init__(self, value): self.parent = self; self.parents = ()
        def lstat(self): return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755)
    monkeypatch.setattr(inventory, "Path", FakePath)
    if case == "valid":
        assert len(inventory.load_inventory().paths) == 17
    else:
        with pytest.raises(inventory.InventoryUnavailable): inventory.load_inventory()
    assert len([c for c in calls if c[0] != "close"]) == 1
    if case not in {"missing", "symlink"}: assert calls[-1] == ("close", 91)


def test_duplicate_nested_key_is_rejected():
    raw = json.dumps(manifest()).replace('"intent": "run"', '"intent": "run", "intent": "disabled"', 1)
    with pytest.raises(inventory.InventoryUnavailable): inventory.parse_inventory(raw.encode())


def nested_manifest():
    value = manifest()
    next(row for row in value['databases'] if row['id'] == 'fingerprint_evidence')['path'] = '/opt/CaptivePortal/data/evidence/evidence.sqlite3'
    return value


def test_evidence_only_parent_exception_and_legacy_catalog_unchanged():
    assert inventory.APPROVED_ROOTS == ('/opt/CaptivePortal/data', '/var/lib/captive-portal/fingerprint-sensor')
    store = next(item for item in inventory.STORES if item.id == 'fingerprint_evidence')
    assert store.filename == 'device_fingerprint_evidence.sqlite3'
    assert resolved().paths[store.id] == '/opt/CaptivePortal/data/' + store.filename
    bound = resolved(**nested_manifest())
    assert bound.paths[store.id] == '/opt/CaptivePortal/data/evidence/evidence.sqlite3'
    assert len(bound.paths) == 17 and len(bound.service_intents) == 9


@pytest.mark.parametrize('identity', [item.id for item in inventory.STORES if item.id != 'fingerprint_evidence'])
def test_all_other_sixteen_store_ids_denied_in_evidence_parent(identity):
    value = manifest()
    next(row for row in value['databases'] if row['id'] == identity)['path'] = '/opt/CaptivePortal/data/evidence/other.sqlite3'
    with pytest.raises(inventory.InventoryUnavailable): resolved(**value)


@pytest.mark.parametrize('path', [
    '/opt/CaptivePortal/data/evidence/sub/evidence.sqlite3',
    '/opt/CaptivePortal/data/evidence-other/evidence.sqlite3',
    '/opt/CaptivePortal/data/other/evidence.sqlite3',
    '/var/lib/captive-portal/fingerprint-sensor/evidence/evidence.sqlite3',
    'data/evidence/evidence.sqlite3', '/opt/CaptivePortal/data/evidence/../evidence.sqlite3',
    '/opt/CaptivePortal/data/evidence/./evidence.sqlite3', '/opt/CaptivePortal/data//evidence/evidence.sqlite3',
    '//opt/CaptivePortal/data/evidence/evidence.sqlite3', '/opt/CaptivePortal/data/evidence/a\n.sqlite3',
    '/opt/CaptivePortal/data/evidence/a\0.sqlite3', '/opt/CaptivePortal/data/evidence/.hidden',
    '/opt/CaptivePortal/data/evidence/*.sqlite3', '/opt/CaptivePortal/data/evidence/evidence.sqlite3;injected',
])
def test_evidence_exception_remains_exact_canonical_direct_parent(path):
    value = nested_manifest()
    next(row for row in value['databases'] if row['id'] == 'fingerprint_evidence')['path'] = path
    with pytest.raises(inventory.InventoryUnavailable): resolved(**value)


@pytest.mark.parametrize('mutation', ['duplicate-path', 'unknown-id', 'extra-entry'])
def test_nested_exception_does_not_relax_closed_manifest_or_collision(mutation):
    value = nested_manifest()
    if mutation == 'duplicate-path':
        value['databases'][1]['path'] = value['databases'][0]['path']
    elif mutation == 'unknown-id':
        next(row for row in value['databases'] if row['id'] == 'fingerprint_evidence')['id'] = 'other_evidence'
    else: value['databases'].append(copy.deepcopy(value['databases'][0]))
    with pytest.raises(inventory.InventoryUnavailable): resolved(**value)


@pytest.mark.parametrize('kind', ['regular', 'symlink', 'directory', 'fifo'])
def test_downstream_snapshot_uses_manifest_selected_path_and_keeps_partial_evidence(kind):
    from datetime import datetime, timezone
    from app.admin_web.operations_service import AdminOperationsReadService
    bound = resolved(**nested_manifest())
    selected = bound.paths['fingerprint_evidence']
    calls = []
    def sample(path):
        calls.append(path)
        if path != selected: raise FileNotFoundError()
        modes = dict(regular=stat.S_IFREG, symlink=stat.S_IFLNK, directory=stat.S_IFDIR, fifo=stat.S_IFIFO)
        return SimpleNamespace(st_mode=modes[kind] | 0o640, st_size=8192, st_ino=123, st_dev=1)
    reader = AdminOperationsReadService(bound, acquire=lambda _: '', lstat=sample,
        monotonic=lambda: 0.0, now=lambda: datetime(2026, 10, 19, tzinfo=timezone.utc))
    try: snapshot = reader._collect(0.0)
    finally: reader.close()
    row = next(item for item in snapshot['databases'] if item['id'] == 'fingerprint_evidence')
    assert row['filename'] == 'evidence.sqlite3' and selected in calls
    assert '/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3' not in calls
    assert row['operational_state'] == ('present_unverified' if kind == 'regular' else 'unavailable')
    assert row['health_evidence'] == 'none'
    if kind != 'regular':
        assert row['reason_code'] == ('symlink_file' if kind == 'symlink' else 'nonregular_file')
        assert snapshot['snapshot_state'] == 'partial'


@pytest.mark.parametrize('fault', ['valid', 'symlink', 'nonregular', 'owner', 'mode', 'parent-mode', 'oversize'])
def test_native_disposable_root_manifest_nofollow_and_trust_unchanged(monkeypatch, fault):
    import os
    import shutil
    import sys
    import tempfile
    from pathlib import Path
    if sys.platform != 'linux' or os.geteuid() != 0:
        pytest.skip('Linux root-only disposable manifest no-follow/trust check; independent root rerun')
    folder = Path(tempfile.mkdtemp(prefix='issue245-partb-', dir='/run'))
    path = folder / 'bindings.json'
    try:
        path.write_bytes(json.dumps(nested_manifest()).encode()); path.chmod(0o640)
        if fault == 'symlink':
            path.rename(folder / 'real'); path.symlink_to(folder / 'real')
        elif fault == 'nonregular': path.unlink(); os.mkfifo(path)
        elif fault == 'owner': os.chown(path, 65002, -1)
        elif fault == 'mode': path.chmod(0o666)
        elif fault == 'parent-mode': folder.chmod(0o722)
        elif fault == 'oversize': path.write_bytes(b' ' * (inventory.MANIFEST_MAX_BYTES + 1))
        monkeypatch.setattr(inventory, 'MANIFEST_PATH', str(path))
        # Only final legacy-root existence probes are substituted; never access installed paths.
        monkeypatch.setattr(inventory, 'Path', lambda value: folder if str(value) in inventory.APPROVED_ROOTS else Path(value))
        if fault == 'valid': assert inventory.load_inventory().paths['fingerprint_evidence'].endswith('/evidence/evidence.sqlite3')
        else:
            with pytest.raises(inventory.InventoryUnavailable): inventory.load_inventory()
    finally: shutil.rmtree(folder)
