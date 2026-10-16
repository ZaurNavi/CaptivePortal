"""SSR-01B focused tests. No capture, network packets, DB or production units.

Ordinary tests need Linux AF_UNIX only. Explicit lab matrix:
  SSR01B_LAB_SYSTEMD=1 SSR01B_EVIDENCE_DIR=<new-dir> python -m pytest ...
requires root in the dedicated WSL Lab with exactly systemd 249.11-0ubuntu3.22.
It creates uniquely named temporary *mock* units and removes only those units.
SSR01B_REAL_BUDGET=1 additionally exercises the actual 30/90/30/5/750 policy.
No production service is started, stopped, installed, or queried.
"""

import ast
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import time
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy/device-fingerprint"
SENSOR = (DEPLOY / "fingerprint-sensor.service").read_text(encoding="ascii")
SURICATA = (DEPLOY / "fingerprint-suricata.service").read_text(encoding="ascii")
PAIR = "/run/ssr01b-fingerprint-pair-maintenance.hold"
SUR_HOLD = "/run/ssr01b-fingerprint-suricata-maintenance.hold"
EVE = "/run/captive-portal/fingerprint-sensor/suricata-eve.sock"
PROBE_LINE = next(line for line in SURICATA.splitlines()
                  if line.startswith("ExecStartPre=/usr/bin/python3 -c "))
# The inline code deliberately uses only systemd's documented \n C escape.
PROBE = shlex.split(PROBE_LINE.split("=", 1)[1])[2].replace("\\n", "\n")
POSIX = pytest.mark.skipif(os.name != "posix", reason="Linux AF_UNIX contract")
LAB = pytest.mark.skipif(os.environ.get("SSR01B_LAB_SYSTEMD") != "1",
                         reason="explicit isolated systemd Lab opt-in required")
REAL = pytest.mark.skipif(os.environ.get("SSR01B_REAL_BUDGET") != "1",
                          reason="explicit actual-duration budget opt-in required")


def values(text, key):
    return [line.split("=", 1)[1] for line in text.splitlines()
            if line.startswith(key + "=")]


def test_exact_unit_delta_preserves_all_other_settings():
    baseline_sensor = subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT}", "show", "7e84bc563f1b6dd3d72da66ae25849d9a7d96540:"
         "deploy/device-fingerprint/fingerprint-sensor.service"], cwd=ROOT, text=True)
    baseline_sur = subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT}", "show", "7e84bc563f1b6dd3d72da66ae25849d9a7d96540:"
         "deploy/device-fingerprint/fingerprint-suricata.service"], cwd=ROOT, text=True)
    assert SENSOR.replace("Wants=fingerprint-suricata.service\n", "").replace(
        f"ConditionPathExists=!{PAIR}\n", "") == baseline_sensor
    restored = SURICATA
    for line in [f"ConditionPathExists=!{PAIR}", f"ConditionPathExists=!{SUR_HOLD}",
                 "StartLimitIntervalSec=750", "StartLimitBurst=5", "StartLimitAction=none",
                 "TimeoutStartSec=90"]:
        assert restored.count(line + "\n") == 1
        restored = restored.replace(line + "\n", "")
    old_probe = next(line for line in baseline_sur.splitlines() if "timeout 1830" in line)
    assert restored.replace(PROBE_LINE, old_probe) == baseline_sur
    assert values(SENSOR, "Wants") == ["fingerprint-suricata.service"]
    assert values(SENSOR, "ConditionPathExists") == ["!" + PAIR]
    assert values(SURICATA, "ConditionPathExists") == ["!" + PAIR, "!" + SUR_HOLD]
    assert values(SURICATA, "After") == ["fingerprint-sensor.service"]
    assert values(SURICATA, "BindsTo") == ["fingerprint-sensor.service"]
    assert values(SURICATA, "PartOf") == ["fingerprint-sensor.service"]


def test_budget_and_no_hidden_actuator_or_socket_sends():
    assert values(SURICATA, "RestartSec") == ["30"]
    assert values(SURICATA, "TimeoutStartSec") == ["90"]
    assert values(SURICATA, "StartLimitBurst") == ["5"]
    assert values(SURICATA, "StartLimitIntervalSec") == ["750"]
    assert values(SURICATA, "StartLimitAction") == ["none"]
    assert 30 + 20 + 30 < 90
    assert 5 * 90 + 5 * 30 == 600 < 750
    assert 5 * 90 + 4 * 30 == 570
    tree = ast.parse(PROBE)
    calls = [n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert "connect" in calls and "settimeout" in calls
    assert not {"send", "sendall", "sendto", "sendmsg", "bind"}.intersection(calls)
    assert "with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)" in PROBE
    assert "time.monotonic() + 30.0" in PROBE
    assert "min(0.25, remaining)" in PROBE
    assert "systemctl" not in SENSOR + SURICATA
    assert "Upholds=" not in SENSOR + SURICATA
    assert values(SENSOR, "Restart") == values(SURICATA, "Restart") == ["on-failure"]


@POSIX
@LAB
def test_target_249_analyze_verify_emitted_templates(tmp_path):
    version = subprocess.check_output(["/usr/bin/systemd-analyze", "--version"], text=True)
    assert version.splitlines()[0] == "systemd 249 (249.11-0ubuntu3.22)"
    (tmp_path / "fingerprint-sensor.service").write_text(SENSOR)
    # The offline Lab has no Suricata executable. This is syntax verification,
    # not a Suricata/config/AF_PACKET test; only executable existence is stubbed.
    (tmp_path / "fingerprint-suricata.service").write_text(
        SURICATA.replace("/usr/bin/suricata", "/usr/bin/true"))
    for name in ("sysinit.target", "basic.target", "shutdown.target"):
        (tmp_path / name).write_text("[Unit]\nDefaultDependencies=no\n")
    env = dict(os.environ, SYSTEMD_UNIT_PATH=str(tmp_path))
    result = subprocess.run(["/usr/bin/systemd-analyze", "verify",
                             str(tmp_path / "fingerprint-sensor.service"),
                             str(tmp_path / "fingerprint-suricata.service")],
                            capture_output=True, text=True, timeout=15, env=env)
    assert result.returncode == 0, result.stderr
    assert not any(word in result.stderr.lower() for word in (
        "unknown", "unbalanced", "invalid", "failed to parse", "unknown escape")), result.stderr


def probe_command(path, budget=0.35):
    code = PROBE.replace(repr(EVE).replace("'", '"'), json.dumps(str(path)))
    code = code.replace("+ 30.0", f"+ {budget!r}")
    return ["/usr/bin/python3", "-c", code]


@POSIX
def test_live_connect_is_non_sending_and_receiver_death_is_not_health(tmp_path):
    endpoint = tmp_path / "eve.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as receiver:
        receiver.bind(str(endpoint))
        result = subprocess.run(probe_command(endpoint), capture_output=True, timeout=3)
        assert result.returncode == 0
        receiver.settimeout(0.05)
        with pytest.raises(socket.timeout):
            receiver.recv(65536)
    assert endpoint.is_socket()  # stale inode is deliberately retained
    result = subprocess.run(probe_command(endpoint), capture_output=True, timeout=3)
    assert result.returncode != 0
    assert b"live EVE socket unavailable" in result.stderr
    assert b"usable" not in result.stdout + result.stderr


@POSIX
@pytest.mark.parametrize("kind", ["absent", "stale", "stream", "file", "dangling", "nul", "long"])
def test_bad_endpoints_fail_closed_with_finite_wait(tmp_path, kind):
    path = tmp_path / "bad.sock"
    receiver = None
    if kind == "stale":
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as stale:
            stale.bind(str(path))
    elif kind == "stream":
        receiver = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        receiver.bind(str(path))
        receiver.listen()
    elif kind == "file":
        path.write_text("not a socket")
    elif kind == "dangling":
        path.symlink_to(tmp_path / "missing")
    elif kind == "nul":
        path = str(path) + "\0private-canary"
    elif kind == "long":
        path = str(path) + "x" * 110
    started = time.monotonic()
    try:
        result = subprocess.run(probe_command(path), capture_output=True, timeout=3)
    finally:
        if receiver is not None:
            receiver.close()
    assert result.returncode != 0
    assert 0.30 <= time.monotonic() - started < 2.0
    assert b"live EVE socket unavailable" in result.stderr
    assert b"private-canary" not in result.stderr


@POSIX
def test_delayed_live_socket_succeeds_not_pathname_only(tmp_path):
    path = tmp_path / "eve.sock"
    child = subprocess.Popen(probe_command(path, 2), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        time.sleep(0.3)
        assert child.poll() is None
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as receiver:
            receiver.bind(str(path))
            assert child.wait(timeout=3) == 0
            receiver.settimeout(0.05)
            with pytest.raises(socket.timeout):
                receiver.recv(1)
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=3)


MOCK_SENSOR = """import os, pathlib, signal, socket, sys, time
root = pathlib.Path(sys.argv[1])
mode = (root / 'mode').read_text().strip()
path = root / 'protected' / 'eve.sock'
path.unlink(missing_ok=True)
if mode.startswith('delay:'):
    time.sleep(float(mode.split(':')[1]))
receiver = None
if mode != 'absent':
    receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    receiver.bind(str(path))
    os.chown(path, 0, 65534)
    os.chmod(path, 0o660)
    print('BOUND', time.monotonic(), flush=True)
while True:
    time.sleep(0.05)
"""


class Lab:
    """Only disposable, uniquely named mock units on the *local WSL Lab* manager."""

    def __init__(self, evidence, real=False):
        assert os.geteuid() == 0, "systemd Lab fixture requires root"
        assert "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()
        version = subprocess.check_output(["/usr/bin/systemd", "--version"], text=True)
        assert version.splitlines()[0] == "systemd 249 (249.11-0ubuntu3.22)"
        self.prefix = "ssr01b-lab-" + uuid.uuid4().hex[:12]
        self.root = Path("/run") / self.prefix
        self.root.mkdir(mode=0o755)
        self.evidence = evidence / self.prefix
        self.evidence.mkdir(parents=True)
        self.names = {role: self.prefix + "-" + role + ".service"
                      for role in ("core", "evidence", "ni", "sensor", "suricata")}
        self.names["boot"] = self.prefix + "-boot.target"
        self.real = real
        self.restart = 30 if real else 0.3
        self.socket_wait = 30 if real else 0.6
        self.start = 90 if real else 2
        self.window = int(values(SURICATA, "StartLimitIntervalSec")[0]) if real else 20
        self.burst = int(values(SURICATA, "StartLimitBurst")[0])
        self.trace = []
        self.links = []
        self.root.joinpath("protected").mkdir(mode=0o750)
        os.chown(self.root / "protected", 0, 65534)
        self.root.joinpath("sensor.py").write_text(MOCK_SENSOR)
        self.root.joinpath("mode").write_text("normal")
        self.pair_hold = self.root / "pair.hold"
        self.sur_hold = self.root / "suricata.hold"
        self.endpoint = self.root / "protected/eve.sock"
        self.version = version

    def ctl(self, *args, check=True):
        # Never address production names, wildcard units, or a global reset-failed.
        assert all(not (arg.startswith("fingerprint-") or arg == "captive-portal.service"
                        or arg == "network-metadata.service") for arg in args)
        proc = subprocess.run(["/usr/bin/systemctl", *args], text=True,
                              capture_output=True, timeout=15)
        self.trace.append({"at_monotonic": time.monotonic(), "args": args,
                           "rc": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
        if check:
            assert proc.returncode == 0, self.trace[-1]
        return proc

    def show(self, role):
        data = self.ctl("show", self.names[role], "--property=ActiveState,SubState,Result,"
                        "MainPID,NRestarts,ConditionResult,ExecMainStartTimestampMonotonic,"
                        "TimeoutStartUSec,RestartUSec,StartLimitBurst,StartLimitIntervalUSec").stdout
        return dict(line.split("=", 1) for line in data.splitlines() if "=" in line)

    def wait(self, role, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.show(role)
            if predicate(state):
                return state
            time.sleep(0.05)
        pytest.fail(f"{role} did not converge: {state}")

    def active(self, role, timeout=10):
        return int(self.wait(role, lambda s: s["ActiveState"] == "active", timeout)["MainPID"])

    def saturated(self, timeout=10):
        # systemd 249 retains the preceding exit-code/timeout Result after denying
        # an automatic restart. Prove rate-limit denial from its own journal too.
        state = self.wait("suricata", lambda s: s["ActiveState"] == "failed"
                          and int(s["NRestarts"]) == self.burst, timeout=timeout)
        journal = subprocess.check_output(["journalctl", "--no-pager", "-o", "cat",
                                           "-u", self.names["suricata"]], text=True)
        assert "Start request repeated too quickly" in journal
        assert len(self.attempts()) == self.burst
        return state

    def start_unit(self, role):
        self.ctl("start", "--no-block", self.names[role])

    def install_mocks(self):
        for role in ("core", "evidence", "ni"):
            deps = ""
            if role == "ni":
                deps = f"Wants={self.names['suricata']}\nAfter={self.names['suricata']}\n"
            self.emit(role, "[Unit]\nDefaultDependencies=no\n" + deps
                      + "[Service]\nType=simple\nExecStart=/usr/bin/sleep infinity\n")
        sensor = SENSOR.replace("captive-portal.service", self.names["core"]).replace(
            "fingerprint-suricata.service", self.names["suricata"]).replace(PAIR, str(self.pair_hold))
        # Fixture-only substitutions; production template is never installed or executed.
        unit = sensor.split("[Service]", 1)[0] + (
            "DefaultDependencies=no\n[Service]\nType=simple\n"
            f"ExecStart=/usr/bin/python3 {self.root}/sensor.py {self.root}\n"
            f"Restart=on-failure\nRestartSec={self.restart}\nTimeoutStopSec=2\n"
            f"StandardOutput=append:{self.root}/sensor.log\nStandardError=inherit\n")
        self.emit("sensor", unit)
        sur = SURICATA.split("[Service]", 1)[0].replace(
            "fingerprint-sensor.service", self.names["sensor"]).replace(
            PAIR, str(self.pair_hold)).replace(SUR_HOLD, str(self.sur_hold)).replace(
            f"StartLimitIntervalSec={values(SURICATA, 'StartLimitIntervalSec')[0]}",
            f"StartLimitIntervalSec={self.window}")
        probe = PROBE_LINE.replace(EVE, str(self.endpoint)).replace(
            "+ 30.0", f"+ {float(self.socket_wait)}")
        self.emit("suricata", sur + "DefaultDependencies=no\n[Service]\nType=simple\n"
                  "User=nobody\nGroup=nogroup\nNoNewPrivileges=true\n"
                  f"ExecStartPre=/usr/bin/python3 -c 'import time; print(\"ATTEMPT\", time.monotonic(), flush=True)'\n"
                  + probe + "\n"
                  f"ExecStartPre=/usr/bin/test ! -e {self.root}/bad-config\n"
                  f"ExecStartPre=/usr/bin/python3 -c 'import pathlib, time; p=pathlib.Path(\"{self.root}/slow\"); time.sleep(float(p.read_text()) if p.exists() else 0)'\n"
                  "ExecStart=/usr/bin/sleep infinity\nRestart=on-failure\n"
                  f"RestartSec={self.restart}\nTimeoutStartSec={self.start}\nTimeoutStopSec=2\n"
                  f"StandardOutput=append:{self.root}/suricata.log\nStandardError=inherit\n")
        self.emit("boot", "[Unit]\nDefaultDependencies=no\nWants="
                  + " ".join(self.names[r] for r in ("core", "evidence", "sensor", "suricata", "ni")) + "\n")
        self.ctl("daemon-reload")

    def emit(self, role, content):
        path = self.root / self.names[role]
        path.write_text(content)
        link = Path("/run/systemd/system") / self.names[role]
        assert not link.exists() and not link.is_symlink()
        link.symlink_to(path)
        self.links.append(link)
        self.evidence.joinpath(path.name).write_text(content)

    def attempts(self):
        path = self.root / "suricata.log"
        if not path.exists():
            return []
        return [float(line.split()[1]) for line in path.read_text().splitlines()
                if line.startswith("ATTEMPT ")]

    def close(self):
        try:
            self.ctl("stop", *self.names.values(), check=False)
            for role in self.names:
                self.show(role)
            for name in ("sensor.log", "suricata.log"):
                if (self.root / name).exists():
                    shutil.copyfile(self.root / name, self.evidence / name)
            self.evidence.joinpath("trace.json").write_text(json.dumps(self.trace, indent=2))
            self.evidence.joinpath("version.txt").write_text(self.version)
            journal = subprocess.run(["journalctl", "--no-pager", "-o", "json",
                                      *[arg for name in self.names.values() for arg in ("-u", name)]],
                                     capture_output=True, text=True, timeout=15)
            self.evidence.joinpath("journal.jsonl").write_text(journal.stdout)
        finally:
            self.ctl("reset-failed", *self.names.values(), check=False)
            for link in self.links:
                assert link.parent == Path("/run/systemd/system")
                assert link.name.startswith(self.prefix)
                link.unlink()
            self.ctl("daemon-reload")
            assert self.root.parent == Path("/run") and self.root.name == self.prefix
            shutil.rmtree(self.root)


@pytest.fixture
def lab(tmp_path):
    evidence = Path(os.environ.get("SSR01B_EVIDENCE_DIR", str(tmp_path)))
    instance = Lab(evidence)
    try:
        instance.install_mocks()
        yield instance
    finally:
        instance.close()


@LAB
@REAL
def test_systemd_actual_three_successful_sensor_restarts_then_suricata_crash(tmp_path):
    instance = Lab(Path(os.environ["SSR01B_EVIDENCE_DIR"]), real=True)
    sequence = []
    try:
        instance.install_mocks()
        instance.start_unit("boot")
        pids = {role: instance.active(role) for role in instance.names if role != "boot"}
        sequence.append({"action": "cold", "at": time.monotonic(), "pids": pids})
        for number in range(1, 4):
            old = {role: instance.active(role) for role in ("sensor", "suricata")}
            instance.ctl("restart", "--no-block", instance.names["sensor"])
            for role in ("sensor", "suricata"):
                instance.wait(role, lambda s, role=role: s["ActiveState"] == "active"
                              and int(s["MainPID"]) != old[role], timeout=10)
            current = {r: instance.active(r) for r in pids}
            assert {r: current[r] for r in ("core", "evidence", "ni")} == {
                r: pids[r] for r in ("core", "evidence", "ni")}
            sequence.append({"action": f"restart-{number}", "at": time.monotonic(), "pids": current})
        sensor = instance.active("sensor")
        old_sur = instance.active("suricata")
        instance.ctl("kill", "--signal=SIGKILL", "--kill-who=main", instance.names["suricata"])
        instance.wait("suricata", lambda s: s["ActiveState"] == "active"
                      and int(s["MainPID"]) != old_sur, timeout=45)
        assert instance.active("sensor") == sensor
        assert {r: instance.active(r) for r in ("core", "evidence", "ni")} == {
            r: pids[r] for r in ("core", "evidence", "ni")}
        sequence.append({"action": "suricata-only-recovery", "at": time.monotonic(),
                         "pids": {r: instance.active(r) for r in pids}})
        assert sequence[-1]["at"] - sequence[0]["at"] < instance.window
        assert len(instance.attempts()) == 5
        assert not any("reset-failed" in row["args"] for row in instance.trace)
    finally:
        instance.evidence.joinpath("successful-sequence.json").write_text(json.dumps(sequence, indent=2))
        instance.close()


@LAB
def test_systemd_249_positive_pid_matrix_and_no_unrelated_cascade(lab):
    lab.start_unit("boot")  # enabled-boot-equivalent start transaction
    pids = {role: lab.active(role) for role in lab.names if role != "boot"}
    for action in ("restart", "stop-start", "kill"):
        old = {r: lab.active(r) for r in ("sensor", "suricata")}
        if action == "stop-start":
            lab.ctl("stop", lab.names["sensor"])
            assert lab.show("suricata")["ActiveState"] == "inactive"
            time.sleep(0.4)
            assert lab.show("sensor")["ActiveState"] == "inactive"
            lab.start_unit("sensor")
        elif action == "kill":
            lab.ctl("kill", "--signal=SIGKILL", "--kill-who=main", lab.names["sensor"])
        else:
            lab.ctl("restart", "--no-block", lab.names["sensor"])
        for role in ("sensor", "suricata"):
            lab.wait(role, lambda s, role=role: s["ActiveState"] == "active"
                     and int(s["MainPID"]) != old[role])
        assert {r: lab.active(r) for r in ("core", "evidence", "ni")} == {
            r: pids[r] for r in ("core", "evidence", "ni")}
    sensor_pid = lab.active("sensor")
    old_sur = lab.active("suricata")
    lab.ctl("kill", "--signal=SIGKILL", "--kill-who=main", lab.names["suricata"])
    lab.wait("suricata", lambda s: s["ActiveState"] == "active" and int(s["MainPID"]) != old_sur)
    assert lab.active("sensor") == sensor_pid
    assert len(lab.attempts()) == 5
    assert not any("reset-failed" in row["args"] for row in lab.trace)


@LAB
def test_systemd_active_sensor_waits_for_delayed_live_endpoint(lab):
    lab.root.joinpath("mode").write_text("delay:0.4")
    lab.start_unit("sensor")
    lab.active("sensor")
    assert not lab.endpoint.exists()
    assert lab.show("suricata")["ActiveState"] != "active"
    lab.active("suricata")
    assert lab.endpoint.is_socket()


@LAB
def test_systemd_bare_suricata_stop_has_no_continuous_upholder(lab):
    lab.start_unit("boot")
    pids = {role: lab.active(role) for role in ("sensor", "suricata", "core", "ni", "evidence")}
    lab.ctl("stop", lab.names["suricata"])
    time.sleep(0.8)  # exceeds scaled restart delay, but no new pull-in transaction
    assert lab.show("suricata")["ActiveState"] == "inactive"
    assert {r: lab.active(r) for r in ("sensor", "core", "ni", "evidence")} == {
        r: pids[r] for r in ("sensor", "core", "ni", "evidence")}
    # A fresh NI start is an admissible trigger without a hold, not a sustained stop.
    lab.ctl("restart", "--no-block", lab.names["ni"])
    lab.active("suricata")


@LAB
@pytest.mark.parametrize("kind", ["absent", "stale", "permission"])
def test_systemd_negative_socket_barrier_remains_failed_not_condition_skipped(lab, kind):
    lab.sur_hold.touch()
    lab.root.joinpath("mode").write_text("absent")
    lab.start_unit("sensor")
    sensor_pid = lab.active("sensor")
    if kind == "stale":
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as stale:
            stale.bind(str(lab.endpoint))
    receiver = None
    if kind == "permission":
        receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        receiver.bind(str(lab.endpoint))
        os.chmod(lab.endpoint, 0o600)
    try:
        lab.sur_hold.unlink()
        lab.start_unit("suricata")
        state = lab.saturated()
        assert state["ConditionResult"] == "yes"
        assert state["Result"] == "exit-code"
        assert lab.active("sensor") == sensor_pid
        log = (lab.root / "suricata.log").read_text()
        assert log.count("live EVE socket unavailable") == lab.burst
        assert "usable" not in log
        if receiver is not None:
            receiver.settimeout(0.05)
            with pytest.raises(socket.timeout):
                receiver.recv(1)
    finally:
        if receiver is not None:
            receiver.close()


@LAB
@pytest.mark.parametrize("hold", ["pair", "suricata"])
def test_systemd_holds_block_ni_pullin_and_interleaved_sensor_restart(lab, hold):
    lab.start_unit("boot")
    pids = {r: lab.active(r) for r in ("sensor", "suricata", "core", "evidence", "ni")}
    path = lab.pair_hold if hold == "pair" else lab.sur_hold
    path.touch()  # hold FIRST; ConditionPathExists does not stop an active unit
    assert lab.active("suricata") == pids["suricata"]
    lab.ctl("stop", lab.names["sensor" if hold == "pair" else "suricata"])
    lab.ctl("restart", "--no-block", lab.names["ni"])
    lab.start_unit("sensor")
    time.sleep(0.4)
    assert lab.show("suricata")["ActiveState"] == "inactive"
    assert lab.show("suricata")["ConditionResult"] == "no"
    assert lab.show("suricata")["Result"] == "success"
    if hold == "pair":
        assert lab.show("sensor")["ActiveState"] == "inactive"
        assert lab.show("sensor")["ConditionResult"] == "no"
    else:
        sensor = lab.active("sensor")
        lab.ctl("kill", "--signal=SIGKILL", "--kill-who=main", lab.names["sensor"])
        lab.wait("sensor", lambda s: s["ActiveState"] == "active" and int(s["MainPID"]) != sensor)
        time.sleep(0.4)
        assert lab.show("suricata")["ActiveState"] == "inactive"
    assert {r: lab.active(r) for r in ("core", "evidence")} == {r: pids[r] for r in ("core", "evidence")}
    path.unlink()  # explicit operator resume, not an automatic clear
    lab.start_unit("sensor" if hold == "pair" else "suricata")
    lab.active("suricata")
    # Simulated reboot loss of /run hold: no persistent maintenance promise.
    path.touch()
    lab.ctl("stop", lab.names["sensor"])
    path.unlink()
    lab.start_unit("sensor")
    lab.active("suricata")


@LAB
def test_systemd_bad_config_rate_limit_and_controlled_resume(lab):
    lab.root.joinpath("bad-config").touch()
    lab.start_unit("sensor")
    sensor = lab.active("sensor")
    failed = lab.saturated()
    assert failed["ActiveState"] == "failed"
    assert len(lab.attempts()) == lab.burst
    assert lab.active("sensor") == sensor
    lab.root.joinpath("bad-config").unlink()
    lab.ctl("reset-failed", lab.names["suricata"])
    lab.start_unit("suricata")
    lab.active("suricata")


@LAB
def test_systemd_near_timeout_failures_cannot_escape_rate_window(lab):
    lab.root.joinpath("slow").write_text("5")  # each preflight killed by 2s timeout
    lab.start_unit("sensor")
    lab.active("sensor")
    start = time.monotonic()
    lab.saturated(timeout=18)
    attempts = lab.attempts()
    assert len(attempts) == lab.burst
    assert all(2.0 <= b - a < 3.5 for a, b in zip(attempts, attempts[1:]))
    assert time.monotonic() - start < 18 < lab.window


@LAB
def test_systemd_nonprivileged_probe_and_unauthorized_binder(lab):
    lab.start_unit("sensor")
    lab.active("suricata")
    # Same surrogate uid/group as the Lab producer; parent permits traverse, not bind.
    def unprivileged():
        os.setgroups([65534])
        os.setgid(65534)
        os.setuid(65534)
    run = subprocess.run(probe_command(lab.endpoint), capture_output=True, timeout=3,
                         preexec_fn=unprivileged)
    assert run.returncode == 0
    bind = subprocess.run(["/usr/bin/python3", "-c",
                           "import socket; s=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM); "
                           f"s.bind({str(lab.endpoint.parent / 'spoof.sock')!r})"],
                          capture_output=True, timeout=3, preexec_fn=unprivileged)
    assert bind.returncode != 0 and b"PermissionError" in bind.stderr
    os.chmod(lab.endpoint, 0o600)
    denied = subprocess.run(probe_command(lab.endpoint), capture_output=True, timeout=3,
                            preexec_fn=unprivileged)
    assert denied.returncode != 0
    assert b"live EVE socket unavailable" in denied.stderr
    assert lab.active("sensor") > 0  # producer process state is not source-health evidence


@LAB
@REAL
@pytest.mark.parametrize("failure", ["missing-socket", "slow-preflight"])
def test_systemd_actual_failure_budget_and_saturation_survives_sensor_restart(tmp_path, failure):
    instance = Lab(Path(os.environ["SSR01B_EVIDENCE_DIR"]), real=True)
    try:
        instance.install_mocks()
        instance.root.joinpath("mode").write_text("absent" if failure == "missing-socket" else "normal")
        if failure == "slow-preflight":
            instance.root.joinpath("slow").write_text("120")
        instance.start_unit("sensor")
        instance.active("sensor")
        start = time.monotonic()
        instance.saturated(timeout=640 if failure == "slow-preflight" else 330)
        attempts = instance.attempts()
        assert len(attempts) == instance.burst == 5
        expected_spacing = 120 if failure == "slow-preflight" else 60
        assert all(expected_spacing - 1 <= b - a < expected_spacing + 5
                   for a, b in zip(attempts, attempts[1:]))
        elapsed = time.monotonic() - start
        expected_elapsed = 600 if failure == "slow-preflight" else 300
        assert expected_elapsed - 5 <= elapsed < expected_elapsed + 20 < 750
        instance.ctl("restart", "--no-block", instance.names["sensor"])
        instance.active("sensor")
        time.sleep(0.5)
        assert instance.show("suricata")["ActiveState"] == "failed"
        assert len(instance.attempts()) == 5  # Sensor cannot reset consumed budget
        instance.root.joinpath("mode").write_text("normal")
        instance.root.joinpath("slow").unlink(missing_ok=True)
        instance.ctl("restart", "--no-block", instance.names["sensor"])
        instance.active("sensor")
        instance.ctl("reset-failed", instance.names["suricata"])
        instance.start_unit("suricata")
        instance.active("suricata")
        instance.evidence.joinpath("budget.json").write_text(json.dumps({
            "failure": failure, "attempts_monotonic": attempts, "denied_sixth_elapsed": elapsed,
            "socket_wait": 30, "restart": 30, "timeout_start": 90,
            "burst": 5, "window": 750, "conservative_570_fifth_600_sixth": True,
            "source_health": "UNPROVEN: socket-only fixture, no EVE heartbeat"}, indent=2))
    finally:
        instance.close()
