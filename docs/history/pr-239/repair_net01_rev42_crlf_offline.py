#!/usr/bin/env python3
"""Offline-only REV4.2 archive repair/validator. Never runs firewall commands.

Run on Linux/WSL where bash exists; input zip explicitly named on command line.
Creates a NEW archive only. Does not overwrite or delete input or any host file.
"""
import hashlib
import pathlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

if len(sys.argv) != 3:
    raise SystemExit('Usage: python3 repair_net01_rev42_crlf_offline.py INPUT_REV4_2.zip NEW_OUTPUT.zip')
source=pathlib.Path(sys.argv[1]).resolve()
output=pathlib.Path(sys.argv[2]).resolve()
if not source.is_file() or source.suffix.lower() != '.zip' or output.suffix.lower() != '.zip':
    raise SystemExit('HOLD: input must be ZIP and output must be new ZIP')
if output.exists() or output == source:
    raise SystemExit('HOLD: refusing to overwrite an existing archive')
if not shutil.which('bash'):
    raise SystemExit('HOLD: bash required to verify real shell syntax, use WSL Ubuntu')

with tempfile.TemporaryDirectory(prefix='net01-rev42-fix-') as t:
    root=pathlib.Path(t)
    with zipfile.ZipFile(source) as z:
        members=z.infolist()
        if not members:raise SystemExit('HOLD: empty ZIP')
        for member in members:
            p=pathlib.PurePosixPath(member.filename)
            if (p.is_absolute() or not p.parts or p.parts[0]!='NET01_IMPL03_PART_A'
                    or any(s in ('..','') for s in p.parts)):
                raise SystemExit('HOLD: unexpected/path-traversal ZIP member')
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise SystemExit('HOLD: symlink ZIP member not admitted')
        z.extractall(root)
    work=root/'NET01_IMPL03_PART_A'
    expected=work/'firewall/net01-fw-install.sh'
    rollback=work/'firewall/net01-fw-rollback.sh'
    verifier=work/'firewall/net01-verify.py'
    guard_test=work/'tests/test_rev4_1_real_verifier_cli.py'
    if not all(p.is_file() for p in (expected,rollback,verifier,guard_test)):
        raise SystemExit('HOLD: required REV4.1/REV4.2 file missing')
    if b'host-local Sensor readiness allow' not in verifier.read_bytes():
        raise SystemExit('HOLD: missing REV4.2 3-rule verifier extension')
    changed=[]
    for script in sorted(work.rglob('*.sh')):
        before=script.read_bytes()
        after=before.replace(b'\r\n',b'\n')
        if b'\r' in after:
            raise SystemExit('HOLD: stray CR in shell file '+str(script.relative_to(work)))
        if before!=after:
            script.write_bytes(after)
            changed.append(str(script.relative_to(work)))
        r=subprocess.run(['bash','-n',str(script)],capture_output=True,text=True)
        if r.returncode:
            raise SystemExit('HOLD: real bash -n failed: '+str(script.relative_to(work))+': '+r.stderr.strip())
    if 'firewall/net01-fw-install.sh' not in changed and 'firewall/net01-fw-rollback.sh' not in changed:
        print('INFO: installer/rollback did not require newline repair; syntax rechecked')
    test=work/'tests/test_actual_packaged_bash.py'
    if test.exists():raise SystemExit('HOLD: unexpected pre-existing test filename')
    test.write_text('''"""Catch malformed actual package shell files, not just fixture copies."""\nfrom pathlib import Path\nimport subprocess\nimport pytest\nROOT=Path(__file__).resolve().parents[1]\nFILES=sorted(ROOT.rglob("*.sh"))\n@pytest.mark.parametrize("script",FILES,ids=lambda s:s.name)\ndef test_on_disk_bash_syntax_and_lf(script):\n    assert b"\\r" not in script.read_bytes(), script\n    r=subprocess.run(["bash","-n",str(script)],capture_output=True,text=True)\n    assert r.returncode == 0,r.stderr\n''',encoding='utf-8')
    results=work/'TEST_RESULTS_REV4_2_LF_PATCH.txt'
    results.write_text('REV=REV4.2_LF_REVIEW_CANDIDATE\nSCOPE=OFFLINE_ONLY\n'
                       +'NORMALIZED_SHELL_FILES='+','.join(changed)+'\n'
                       +'ALL_PACKAGED_BASH_SYNTAX=PASS\n'
                       +'OLD_ARCHIVE_PRESERVED=YES\n'
                       +'PYTEST=REQUIRES_FRESH_RUN\nREAL_FIREWALL_PID1=NOT_TESTED\n',encoding='utf-8')
    manifest=work/'MANIFEST.sha256'
    lines=[]
    for f in sorted(work.rglob('*')):
        if f.is_file() and f != manifest:
            lines.append(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.relative_to(work).as_posix())
    manifest.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for f in sorted(work.rglob('*')):
            if f.is_file():z.write(f,'NET01_IMPL03_PART_A/'+f.relative_to(work).as_posix())
    with zipfile.ZipFile(output) as z:
        for line in z.read('NET01_IMPL03_PART_A/MANIFEST.sha256').decode().splitlines():
            hexd,rel=line.split('  ',1)
            if hashlib.sha256(z.read('NET01_IMPL03_PART_A/'+rel)).hexdigest()!=hexd:
                raise SystemExit('HOLD: ZIP manifest mismatch: '+rel)
    print('OUTPUT='+str(output))
    print('OUTPUT_SHA256='+hashlib.sha256(output.read_bytes()).hexdigest())
    print('BASH_SYNTAX=PASS')
    print('MANIFEST=PASS')
    print('SHELL_FILES_NORMALIZED='+','.join(changed))
    print('STATUS=OFFLINE_REVIEW_CANDIDATE_NOT_PRODUCTION_GO')
