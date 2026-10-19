"""Offline commands share parser/renderer, print LF even on Windows, no capture."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.device_fingerprint_sensor import bpf_cli
from app.device_fingerprint_sensor.config import parse_guest_cidrs
from app.device_fingerprint_sensor.capture_filter import render_raw_capture_filter


@pytest.mark.parametrize('scope',['192.168.8.0/22','10.50.0.0/19','192.168.8.0/22,10.50.0.0/19'])
def test_render_subprocess_exact_ascii_lf_ignores_sensor_env(scope):
    env=dict(os.environ,DEVICE_FINGERPRINT_SENSOR_ENABLED='invalid',DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS='0.0.0.0/0')
    run=subprocess.run([sys.executable,'-B','-m','app.device_fingerprint_sensor.bpf_cli','render','--guest-cidrs',scope],
        cwd=Path(__file__).parents[2],env=env,capture_output=True,timeout=15)
    assert run.returncode==0 and not run.stderr
    assert run.stdout==render_raw_capture_filter(parse_guest_cidrs(scope)).encode()+b'\n'


@pytest.mark.parametrize('raw',[b'wrong',b'\r\n',b'\xef\xbb\xbf',None])
def test_verify_bad_or_missing_file_sanitized_and_does_not_write(tmp_path,capsys,raw):
    file=tmp_path/'artifact.bpf'
    if raw is not None:file.write_bytes(raw)
    before=tuple(tmp_path.iterdir())
    assert bpf_cli.main(['verify','--guest-cidrs','10.50.0.0/19','--artifact',str(file)])==2
    output=capsys.readouterr();assert output.out=='' and output.err=='offline raw capture BPF operation failed\n'
    assert tuple(tmp_path.iterdir())==before
    if raw is not None:assert file.read_bytes()==raw


@pytest.mark.parametrize('suffix',[b'',b'\n',b'\r\n',b'\n\n'])
def test_verify_exact_encoding_without_text_newline_translation(tmp_path,capsys,suffix):
    file=tmp_path/'artifact.bpf';content=render_raw_capture_filter(parse_guest_cidrs('10.50.0.0/19')).encode()+suffix
    file.write_bytes(content)
    assert bpf_cli.main(['verify','--guest-cidrs','10.50.0.0/19','--artifact',str(file)])==(0 if suffix in (b'',b'\n') else 2)
    assert file.read_bytes()==content
    assert capsys.readouterr().out==''


@pytest.mark.parametrize('args',[[],['render'],['render','--guest-cidrs','0.0.0.0/0'],
    ['render','--guest-cidrs','10.50.0.0/19;SENSITIVE_CANARY'],['render','--expression','SENSITIVE_CANARY'],
    ['verify','--guest-cidrs','10.50.0.0/19','--artifact','relative.bpf']])
def test_invalid_cli_input_is_sanitized(args,capsys):
    assert bpf_cli.main(args)==2
    out=capsys.readouterr();assert out.out=='' and out.err=='offline raw capture BPF operation failed\n'
    assert 'SENSITIVE_CANARY' not in out.err
