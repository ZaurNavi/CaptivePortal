import subprocess
from pathlib import Path
import pytest

from app.device_fingerprint_sensor.capture import InterfacePreflight
from app.device_fingerprint_sensor.models import SensorPreflightError
from .test_runtime import make_tree, runner


def test_T05_alternate_interface_passes_only_complete_no_l3_preflight(tmp_path):
    roots = make_tree(tmp_path, interface="enp1s0")
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return runner(command, **kwargs)
    InterfacePreflight("enp1s0", sys_root=roots[0], proc_root=roots[1], runner=run).validate()
    assert ["ip", "-j", "address", "show", "dev", "enp1s0"] in calls
    assert ["ip", "-6", "-j", "route", "show", "default", "dev", "enp1s0"] in calls
    assert ["netplan", "get", "ethernets.enp1s0.dhcp4"] in calls
    assert ["netplan", "get", "ethernets.enp1s0.dhcp6"] in calls
    assert all("enp8s0" not in " ".join(command) for command in calls)


@pytest.mark.parametrize("fault", ["missing", "missing_operstate", "down", "master", "master_symlink",
    "inet", "inet6", "route4", "route6", "forward4", "forward6", "dhcp4", "dhcp6",
    "dhclient", "dhcpcd", "udhcpc", "networkmanager", "ip_failed", "ip_invalid_json", "ip_missing",
    "netplan_failed", "netplan_missing", "nmcli_failed", "nmcli_missing", "proc_unreadable", "forward_missing"])
def test_T05_alternate_interface_preserves_every_existing_guard(tmp_path, monkeypatch, fault):
    sys_root, proc_root = make_tree(tmp_path, interface="enp1s0")
    net = sys_root / "class/net/enp1s0"
    if fault in {"missing", "missing_operstate"}:
        (net / "operstate").unlink()
        if fault == "missing":
            net.rmdir()
    elif fault == "down":
        (net / "operstate").write_text("down")
    elif fault == "master":
        (net / "master").mkdir()
    elif fault == "master_symlink":
        # A dangling master link must also fail, not just a resolvable master.
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == net / "master" or original(path))
    elif fault in {"forward4", "forward6", "forward_missing"}:
        family = "ipv6" if fault == "forward6" else "ipv4"
        path = proc_root / f"sys/net/{family}/conf/enp1s0/forwarding"
        if fault == "forward_missing":
            path.unlink()
        else:
            path.write_text("1")
    elif fault in {"dhclient", "dhcpcd", "udhcpc"}:
        (proc_root / "100/cmdline").write_bytes(f"/sbin/{fault}\0--interface=enp1s0\0".encode())
    elif fault == "proc_unreadable":
        original = Path.iterdir
        def unreadable(path):
            if path == proc_root:
                raise PermissionError()
            return original(path)
        monkeypatch.setattr(Path, "iterdir", unreadable)
    def run(command, **kwargs):
        if command[0] == "ip":
            if fault == "ip_missing":
                raise FileNotFoundError()
            if fault == "ip_failed":
                return subprocess.CompletedProcess(command, 1, "", "synthetic")
            if fault == "ip_invalid_json":
                return subprocess.CompletedProcess(command, 0, "invalid", "")
            if fault in {"inet", "inet6"} and "address" in command:
                return subprocess.CompletedProcess(command, 0, '[{"addr_info":[{"family":"' + fault + '"}]}]', "")
            if (fault == "route4" and "route" in command and "-6" not in command
                    or fault == "route6" and "route" in command and "-6" in command):
                return subprocess.CompletedProcess(command, 0, '[{"dst":"default"}]', "")
        if command[0] == "netplan":
            if fault == "netplan_missing":
                raise FileNotFoundError()
            if fault == "netplan_failed":
                return subprocess.CompletedProcess(command, 1, "", "synthetic")
            if fault in {"dhcp4", "dhcp6"} and command[-1].endswith(fault):
                return subprocess.CompletedProcess(command, 0, "true", "")
        if command[0] == "systemctl" and fault in {"networkmanager", "nmcli_failed", "nmcli_missing"}:
            return subprocess.CompletedProcess(command, 0, "active", "")
        if command[0] == "nmcli":
            if fault == "nmcli_missing":
                raise FileNotFoundError()
            return subprocess.CompletedProcess(command, 1 if fault == "nmcli_failed" else 0, "wired:enp1s0", "")
        return runner(command, **kwargs)
    with pytest.raises(SensorPreflightError):
        InterfacePreflight("enp1s0", sys_root=sys_root, proc_root=proc_root, runner=run).validate()


@pytest.mark.parametrize("kind", ["bridge", "bonding"])
def test_T05_selected_bridge_or_bond_must_be_rejected(tmp_path, kind):
    sys_root, proc_root = make_tree(tmp_path, interface="enp1s0")
    (sys_root / "class/net/enp1s0" / kind).mkdir()
    with pytest.raises(SensorPreflightError):
        InterfacePreflight("enp1s0", sys_root=sys_root, proc_root=proc_root, runner=runner).validate()


@pytest.mark.parametrize("kind", ["bridge", "bonding"])
@pytest.mark.parametrize("dangling", [False, True], ids=["symlink", "dangling_symlink"])
def test_T05_selected_bridge_or_bond_symlink_must_be_rejected(tmp_path, monkeypatch, kind, dangling):
    sys_root, proc_root = make_tree(tmp_path, interface="enp1s0")
    link = sys_root / "class/net/enp1s0" / kind
    original_exists = Path.exists
    original_is_symlink = Path.is_symlink
    # Model both link states without requiring Windows symlink privileges.
    monkeypatch.setattr(Path, "exists", lambda path: not dangling if path == link else original_exists(path))
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == link or original_is_symlink(path))
    with pytest.raises(SensorPreflightError, match="^capture_interface_unavailable$"):
        InterfacePreflight("enp1s0", sys_root=sys_root, proc_root=proc_root, runner=runner).validate()
