"""Exact artifact authority and no unfiltered packet activation (Issue 244)."""
import inspect
import os
from pathlib import Path
import shutil
import socket
import tempfile

import pytest

from app.device_fingerprint_sensor import capture, capture_filter as bpf
from app.device_fingerprint_sensor.config import parse_guest_cidrs
from app.device_fingerprint_sensor.models import SensorError

NETWORKS = parse_guest_cidrs('10.50.0.0/19')


@pytest.fixture
def trusted_artifact(monkeypatch):
    if os.name != 'posix' or os.geteuid() != 0:
        pytest.skip('Linux root-owned artifact filesystem contract; executed by root LAB suite')
    # /tmp is deliberately not a trusted runtime ancestor. Only disposable /run state.
    directory = Path(tempfile.mkdtemp(prefix='issue244-artifact-', dir='/run'))
    path = directory / 'raw-capture.bpf'
    path.write_bytes(bpf.render_raw_capture_filter(NETWORKS).encode('ascii') + b'\n')
    path.chmod(0o600)
    monkeypatch.setattr(bpf, 'DEPLOYED_FILTER_PATH', path)
    try:
        yield path
    finally:
        shutil.rmtree(directory)


def test_runtime_helpers_expose_no_path_expression_or_library_bypass():
    assert tuple(inspect.signature(bpf.load_deployed_filter).parameters) == ('guest_cidrs',)
    assert tuple(inspect.signature(bpf.attach_frozen_filter).parameters) == ('raw_socket', 'guest_cidrs')
    for kwargs in ({'expression': 'ip'}, {'path': '/tmp/filter'}, {'library': object()}):
        with pytest.raises(TypeError):
            bpf.attach_frozen_filter(object(), **kwargs)


def test_offline_boolean_result_cannot_authorize_attach(monkeypatch):
    monkeypatch.setattr(bpf, 'load_deployed_filter', lambda _nets: True)
    with pytest.raises(SensorError):
        bpf.attach_frozen_filter(object(), NETWORKS)


@pytest.mark.parametrize('suffix', [b'', b'\n'])
def test_trusted_exact_artifact_is_read_without_mutation(trusted_artifact, suffix):
    expected = bpf.render_raw_capture_filter(NETWORKS)
    trusted_artifact.write_bytes(expected.encode() + suffix)
    before = trusted_artifact.stat()
    assert bpf.load_deployed_filter(NETWORKS) == expected
    after = trusted_artifact.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns)


@pytest.mark.parametrize('fault', ['missing', 'directory', 'symlink', 'dangling', 'hardlink',
    'file_group_write', 'file_world_write', 'owner', 'ancestor_group_write', 'ancestor_world_write',
    'ancestor_owner', 'ancestor_symlink', 'escape', 'crlf', 'bom', 'extra_lf', 'stale', 'huge', 'race'])
def test_runtime_artifact_fail_closed(trusted_artifact, monkeypatch, fault):
    path = trusted_artifact
    if fault == 'missing': path.unlink()
    elif fault == 'directory': path.unlink(); path.mkdir()
    elif fault in ('symlink', 'dangling'):
        target = path.parent / 'target'
        if fault == 'symlink': path.rename(target)
        else: path.unlink()
        path.symlink_to(target)
    elif fault == 'hardlink': os.link(path, path.parent / 'alias')
    elif fault == 'file_group_write': path.chmod(0o620)
    elif fault == 'file_world_write': path.chmod(0o602)
    elif fault == 'owner': os.chown(path, 65534, -1)
    elif fault == 'ancestor_group_write': path.parent.chmod(0o720)
    elif fault == 'ancestor_world_write': path.parent.chmod(0o702)
    elif fault == 'ancestor_owner': os.chown(path.parent, 65534, -1)
    elif fault == 'ancestor_symlink':
        alias = path.parent / 'alias'; alias.symlink_to(path.parent, target_is_directory=True)
        monkeypatch.setattr(bpf, 'DEPLOYED_FILTER_PATH', alias / path.name)
    elif fault == 'escape': monkeypatch.setattr(bpf, 'DEPLOYED_FILTER_PATH', path.parent / '..' / path.parent.name / path.name)
    elif fault == 'crlf': path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
    elif fault == 'bom': path.write_bytes(b'\xef\xbb\xbf' + path.read_bytes())
    elif fault == 'extra_lf': path.write_bytes(path.read_bytes() + b'\n')
    elif fault == 'stale': path.write_bytes(bpf.RAW_CAPTURE_FILTER.encode())
    elif fault == 'huge': path.write_bytes(b'x' * 8192)
    elif fault == 'race':
        original = os.read
        def changed(fd, maximum):
            value = original(fd, maximum)
            path.chmod(0o640)
            return value
        monkeypatch.setattr(bpf.os, 'read', changed)
    before = len(os.listdir('/proc/self/fd'))
    with pytest.raises(SensorError): bpf.load_deployed_filter(NETWORKS)
    assert len(os.listdir('/proc/self/fd')) == before


@pytest.mark.parametrize('phase', ['timeout', 'timestamp', 'second_verify', 'compile', 'attach', 'bind'])
def test_activation_fault_closes_socket_without_publication_or_read(monkeypatch, phase):
    events = []
    expected = bpf.render_raw_capture_filter(NETWORKS)
    monkeypatch.setattr(capture, 'load_deployed_filter', lambda nets: expected)
    class Raw:
        def settimeout(self, value):
            events.append('timeout')
            if phase == 'timeout': raise OSError('timeout')
        def setsockopt(self, *args):
            events.append('timestamp')
            if phase == 'timestamp': raise OSError('timestamp')
        def bind(self, value):
            assert value == ('safe-nic', 3) and owner.socket is None
            events.append('bind')
            if phase == 'bind': raise OSError('bind')
        def close(self): events.append('close')
        def recvmsg(self, *args): pytest.fail('receive before successful activation')
    raw = Raw()
    def factory(*args):
        assert args == (socket.AF_PACKET if hasattr(socket, 'AF_PACKET') else 17, socket.SOCK_RAW, 0)
        events.append('socket'); return raw
    # AF_PACKET does not exist on Windows; the lifecycle seam remains portable.
    monkeypatch.setattr(capture.socket, 'AF_PACKET', 17, raising=False)
    def attach(value, nets):
        assert value is raw and nets is NETWORKS and owner.socket is None
        events.append('attach')
        if phase in ('second_verify', 'compile', 'attach'): raise SensorError(phase)
        return 12
    monkeypatch.setattr(capture, 'attach_frozen_filter', attach)
    owner = capture.RawCapture('safe-nic', NETWORKS, socket_factory=factory)
    with pytest.raises((SensorError, OSError)): owner.open()
    assert events[-1] == 'close' and events.count('close') == 1 and owner.socket is None
    assert ('bind' in events) == (phase == 'bind')


def test_invalid_artifact_prevents_socket_creation(monkeypatch):
    def fail(_): raise SensorError('untrusted')
    monkeypatch.setattr(capture, 'load_deployed_filter', fail)
    owner = capture.RawCapture('safe-nic', NETWORKS, socket_factory=lambda *a: pytest.fail('socket created'))
    with pytest.raises(SensorError): owner.open()
    assert owner.socket is None


def test_artifact_is_independently_rechecked_at_attach(monkeypatch):
    expected = bpf.render_raw_capture_filter(NETWORKS)
    monkeypatch.setattr(capture, 'load_deployed_filter', lambda nets: expected)
    def stale_at_attach(_): raise SensorError('artifact changed')
    monkeypatch.setattr(bpf, 'load_deployed_filter', stale_at_attach)
    events = []
    monkeypatch.setattr(capture.socket, 'AF_PACKET', 17, raising=False)
    class Raw:
        def settimeout(self, value): pass
        def setsockopt(self, *args): pass
        def close(self): events.append('closed')
        def bind(self, *args): pytest.fail('activated after artifact changed')
    owner = capture.RawCapture('safe-nic', NETWORKS, socket_factory=lambda *a: Raw())
    with pytest.raises(SensorError): owner.open()
    assert events == ['closed'] and owner.socket is None


@pytest.mark.parametrize('fault', ['compile', 'zero', 'overlong', 'null', 'attach'])
def test_native_compiler_limits_and_cleanup(monkeypatch, fault):
    import ctypes
    events = []
    instructions = (bpf._BpfInsn * 1)(bpf._BpfInsn(6, 0, 0, 65535))
    class Function:
        def __init__(self, call): self.call = call
        def __call__(self, *args): return self.call(*args)
    def compile_program(handle, pointer, expression, optimize, mask):
        events.append('compile')
        program = ctypes.cast(pointer, ctypes.POINTER(bpf._BpfProgram)).contents
        program.bf_len = {'zero': 0, 'overlong': 4097}.get(fault, 1)
        if fault != 'null': program.bf_insns = instructions
        return -1 if fault == 'compile' else 0
    class Pcap:
        pcap_open_dead = Function(lambda *a: 1)
        pcap_compile = Function(compile_program)
        pcap_freecode = Function(lambda *a: events.append('free'))
        pcap_close = Function(lambda *a: events.append('close'))
    class Libc:
        setsockopt = Function(lambda *a: -1)
    monkeypatch.setattr(bpf.ctypes.util, 'find_library', lambda name: 'test-pcap')
    monkeypatch.setattr(bpf.ctypes, 'CDLL', lambda name, **kw: Libc() if name is None else Pcap())
    monkeypatch.setattr(bpf, 'load_deployed_filter', lambda nets: bpf.render_raw_capture_filter(nets))
    class Raw:
        def fileno(self): return 123
    with pytest.raises((SensorError, OSError)): bpf.attach_frozen_filter(Raw(), NETWORKS)
    assert events == ['compile', 'free', 'close']
