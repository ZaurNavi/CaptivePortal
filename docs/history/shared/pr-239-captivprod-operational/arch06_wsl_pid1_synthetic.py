#!/usr/bin/env python3
"""Isolated WSL systemd PID1 synthetic lifecycle test; NO production access."""
import os, subprocess, pathlib, socket, time, shutil, textwrap
ROOT=pathlib.Path('/tmp/captivprod-arch06-systemd-staging')
WATCH_UNIT='captivprod-arch06-watchdog.service'
BACK_UNIT='captivprod-arch06-backend.service'
UNIT_DIR=pathlib.Path('/run/systemd/system')
PORT=48089

def run(*cmd,check=True):
    r=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=12)
    if check and r.returncode:
        raise RuntimeError('command failed '+repr(cmd)+': '+r.stdout[-900:])
    return r

def port_open():
    try:
        with socket.create_connection(('127.0.0.1',PORT),timeout=.3):return True
    except OSError:return False

def wait(predicate,timeout=5):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if predicate():return True
        time.sleep(.15)
    return False

if os.geteuid()!=0:raise SystemExit('root required inside isolated WSL distro')
if pathlib.Path('/proc/1/comm').read_text().strip()!='systemd':
    raise SystemExit('HOLD: no real systemd PID1')
if ROOT.exists():raise SystemExit('HOLD: staging dir already exists')
if port_open():raise SystemExit('HOLD: diagnostic port 48089 occupied')
for n in (WATCH_UNIT,BACK_UNIT):
    if (UNIT_DIR/n).exists():raise SystemExit('HOLD: staging unit already exists')
ROOT.mkdir(mode=0o755);ROOT.chmod(0o755)  # fixture contains no credentials; allow nobody to read backend
watch=ROOT/'watchdog.py';back=ROOT/'backend.py'
watch.write_text(textwrap.dedent("""
import os,sys,socket,time,pathlib
root=pathlib.Path('/tmp/captivprod-arch06-systemd-staging')
if (root/'fail_guard').exists():sys.exit(75)
addr=os.environ['NOTIFY_SOCKET']
if addr.startswith('@'):addr='\\0'+addr[1:]
with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sock:
    sock.sendto(b'READY=1\\nSTATUS=synthetic guard admitted',addr)
while True:
    if (root/'fail_guard').exists():sys.exit(75)
    time.sleep(.2)
"""))
back.write_text(textwrap.dedent("""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(204);self.end_headers()
    def log_message(self,*a):pass
ThreadingHTTPServer(('127.0.0.1',48089),H).serve_forever()
"""))
(UNIT_DIR/WATCH_UNIT).write_text(textwrap.dedent(f"""
[Unit]
Description=Captiv ARCH06 disposable Type notify guard
[Service]
Type=notify
NotifyAccess=main
ExecStart=/usr/bin/python3 {watch}
Restart=no
TimeoutStartSec=4
TimeoutStopSec=3
"""))
(UNIT_DIR/BACK_UNIT).write_text(textwrap.dedent(f"""
[Unit]
Description=Captiv ARCH06 disposable synthetic backend
BindsTo={WATCH_UNIT}
After={WATCH_UNIT}
[Service]
Type=simple
User=nobody
ExecStart=/usr/bin/python3 {back}
Restart=no
TimeoutStartSec=4
TimeoutStopSec=3
"""))
try:
    run('systemctl','daemon-reload')
    run('systemctl','reset-failed',WATCH_UNIT,BACK_UNIT,check=False)
    print('PID1_PRESENT=PASS')
    print('UNIT_SYNTAX='+ ('PASS' if run('systemd-analyze','verify',str(UNIT_DIR/WATCH_UNIT),str(UNIT_DIR/BACK_UNIT),check=False).returncode==0 else 'FAIL'))
    run('systemctl','start',BACK_UNIT)
    assert wait(lambda:port_open())
    assert run('systemctl','is-active',WATCH_UNIT).stdout.strip()=='active'
    print('NOTIFY_READY_ORDERING=PASS')
    print('DIAGNOSTIC_LISTENER_BEFORE_STOP=PASS')
    run('systemctl','stop',WATCH_UNIT)
    assert wait(lambda:not port_open(),5), 'BindsTo failed to stop backend socket'
    assert run('systemctl','is-active',BACK_UNIT,check=False).stdout.strip()!='active'
    print('BINDSTO_STOP_PROPAGATION=PASS')
    print('LISTENER_DISAPPEARANCE_ON_GUARD_STOP=PASS')
    (ROOT/'fail_guard').touch()
    run('systemctl','reset-failed',WATCH_UNIT,BACK_UNIT,check=False)
    attempt=run('systemctl','start',BACK_UNIT,check=False)
    assert attempt.returncode!=0, 'Backend incorrectly started with failed guard'
    assert not port_open()
    print('GUARD_NOT_READY_PREVENTS_BACKEND=PASS')
    print('FAIL_CLOSED_DIAGNOSTIC=PASS')
finally:
    run('systemctl','stop',BACK_UNIT,WATCH_UNIT,check=False)
    run('systemctl','reset-failed',BACK_UNIT,WATCH_UNIT,check=False)
    for n in (BACK_UNIT,WATCH_UNIT):
        with __import__('contextlib').suppress(FileNotFoundError):(UNIT_DIR/n).unlink()
    run('systemctl','daemon-reload',check=False)
    shutil.rmtree(ROOT,ignore_errors=True)
    print('WSL_STAGING_CLEANUP=COMPLETED')
