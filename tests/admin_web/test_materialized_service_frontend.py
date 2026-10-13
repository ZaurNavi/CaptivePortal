from pathlib import Path
import shutil
import subprocess


def test_strict_v3_and_explicit_legacy_modes():
    root=Path(__file__).parents[2]
    node=shutil.which('node')
    assert node is not None
    result=subprocess.run([node,str(root/'tests/admin_web/materialized_service_intelligence.cjs'),str(root/'app/admin_web/static/admin.js')],cwd=root,text=True,capture_output=True,timeout=25)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'NI04_MATERIALIZED_FRONTEND_PASS' in result.stdout
