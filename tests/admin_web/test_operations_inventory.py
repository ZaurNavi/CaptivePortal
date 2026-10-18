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
             else inventory.APPROVED_ROOTS[2] if item.id == "fingerprint_evidence"
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
    assert inventory.MANIFEST_PATH == "/etc/captive-portal/admin-db-services-v1.json"


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
    assert calls[0][1] & fake_os.O_NOFOLLOW
    assert calls[0][1] & fake_os.O_NONBLOCK
    if case not in {"missing", "symlink"}: assert calls[-1] == ("close", 91)


def test_duplicate_nested_key_is_rejected():
    raw = json.dumps(manifest()).replace('"intent": "run"', '"intent": "run", "intent": "disabled"', 1)
    with pytest.raises(inventory.InventoryUnavailable): inventory.parse_inventory(raw.encode())


def test_captivprod_three_root_manifest_is_complete_and_pure(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("pure parsing must not probe the filesystem")
    monkeypatch.setattr(inventory.os, "open", forbidden)
    bound = resolved()
    assert len(bound.paths) == 17
    assert bound.paths["fingerprint_evidence"] == "/var/lib/captivprod-evidence/evidence.sqlite3"
    assert bound.paths["network_attribution"] == "/var/lib/captivprod-sensor/network_attribution.sqlite3"
    assert bound.paths["sensor_spool"] == "/var/lib/captivprod-sensor/spool.sqlite3"
    assert {str(inventory.PurePosixPath(path).parent) for path in bound.paths.values()} == set(inventory.APPROVED_ROOTS)
    assert next(s for s in inventory.STORES if s.id == "fingerprint_evidence").filename == "evidence.sqlite3"


@pytest.mark.parametrize("identity,path", [
    ("sensor_spool", "/var/lib/captive-portal/fingerprint-sensor/spool.sqlite3"),
    ("network_attribution", "/var/lib/captive-portal/fingerprint-sensor/network_attribution.sqlite3"),
    ("fingerprint_evidence", "/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"),
    ("fingerprint_evidence", "/opt/CaptivePortal/data/evidence.sqlite3"),
    ("sensor_spool", "/var/lib/captivprod-evidence/spool.sqlite3"),
    ("network_attribution", "/opt/CaptivePortal/data/network_attribution.sqlite3"),
    ("settings", "/opt/CaptivePortal/data/arbitrary.sqlite3"),
    ("settings", "/opt/CaptivePortal/data/settings.sqlite3-wal"),
    ("sensor_spool", "/var/lib/captivprod-sensor/nested/spool.sqlite3"),
    ("sensor_spool", "/var/lib/captivprod-sensor/./spool.sqlite3"),
    ("sensor_spool", "/var/lib/captivprod-sensor//spool.sqlite3"),
])
def test_captivprod_only_attested_special_roots_and_catalog_names(identity, path):
    value = manifest()
    next(item for item in value["databases"] if item["id"] == identity)["path"] = path
    with pytest.raises(inventory.InventoryUnavailable, match="^inventory_unavailable$"):
        resolved(**value)


@pytest.mark.parametrize("mode,uid", [(stat.S_IFLNK | 0o755, 0),
    (stat.S_IFDIR | 0o777, 0), (stat.S_IFDIR | 0o755, 1000)])
def test_manifest_rejects_unsafe_ancestor_even_when_direct_parent_is_trusted(mode, uid):
    class Ancestor:
        def lstat(self): return SimpleNamespace(st_mode=mode, st_uid=uid)
    class Directory:
        parents = (Ancestor(),)
        def lstat(self): return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
    with pytest.raises(inventory.InventoryUnavailable):
        inventory._trusted_directory(Directory())
