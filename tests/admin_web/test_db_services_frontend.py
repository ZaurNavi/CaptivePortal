import json
from pathlib import Path
import shutil
import subprocess

from app.admin_web.operations_service import AdminOperationsReadService
from tests.admin_web.test_operations_inventory import resolved
from tests.admin_web.test_operations_service import NOW, regular, systemd_text


def ui_fixture():
    subject = AdminOperationsReadService(resolved(), acquire=lambda c: systemd_text(), lstat=regular, now=lambda: NOW)
    result = subject.read("synthetic-browser")
    subject.close()
    return result


def test_dedicated_javascript_behaviour_with_exact_backend_snapshot(tmp_path):
    root = Path(__file__).parents[2]
    node = shutil.which("node")
    assert node is not None, "Node required for this focused frontend contract"
    source = root / "app/admin_web/static/db_services.js"
    subprocess.run([node, "--check", str(source)], check=True, capture_output=True)
    model = ui_fixture()
    model["summary"]["services"]["running"] = 111  # Deliberate canary: frontend must not recompute.
    model["databases"][0]["label"] = "<script>SYNTHETIC</script>"
    for row, size in zip(model["databases"], (0, None, 1024, 1024**2, 1024**3, 1024**4)):
        row["total_footprint_bytes"] = size
    model["databases"][0]["private_path"] = "/private/PATH_CANARY"
    fixture = tmp_path / "synthetic.json"
    fixture.write_text(json.dumps(model), encoding="utf-8")
    result = subprocess.run([node, str(Path(__file__).with_name("db_services_ui.cjs")), str(source), str(fixture)],
                            check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_css_is_page_scoped_and_precedes_old_ni03_suffix():
    root = Path(__file__).parents[2]
    css = (root / "app/admin_web/static/admin.css").read_text(encoding="utf-8")
    assert css.index("/* DB-SERVICES-01: global Operations page only. */") < css.index("#device-service-intelligence") < css.index("/* NI-03 presentation only;")
    section = css.split("/* DB-SERVICES-01: global Operations page only. */", 1)[1].split("#device-service-intelligence", 1)[0]
    for line in section.splitlines():
        if "{" in line and not line.startswith("@media"):
            assert line.lstrip().startswith("#db-services-page"), line
    assert "min-width: 0" in section and "grid-template-columns: minmax(0, 1fr)" in section
    assert '[data-state="present_unverified"]' not in section  # neutral default, no false green override
    assert '[data-family="service"][data-state="running"]' in section


def test_static_page_has_accessible_sections_and_dedicated_controller():
    root = Path(__file__).parents[2]
    template = (root / "app/admin_web/templates/admin/db_services.html").read_text(encoding="utf-8")
    assert template.index(">Summary<") < template.index(">Operational Data Flow<") < template.index(">Services<") < template.index(">Databases<")
    assert "Structural only" in template and "not current data movement" in template
    assert "Flow activity is not instrumented in R1." in template
    assert 'role="status"' in template and 'aria-live="polite"' in template
    js = (root / "app/admin_web/static/db_services.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js and "textContent" in js
    assert "site_id" not in js and "setInterval" not in js


def test_topology_relations_are_neutral_static_and_geometry_has_no_polling():
    root = Path(__file__).parents[2]
    css = (root / "app/admin_web/static/admin.css").read_text(encoding="utf-8")
    section = css.split("/* Operational Data Flow:",1)[1].split("#device-service-intelligence",1)[0]
    assert "ops-relation-writes_to" in section and "stroke-width: 1.7" in section
    assert "ops-relation-read_by" in section and "stroke-dasharray: 4 3" in section
    assert "@keyframes" not in section and "animation:" not in section
    assert 'data-state=' not in section and "active-flow" not in section
    js = (root / "app/admin_web/static/db_services.js").read_text(encoding="utf-8")
    assert js.count("await fetch(") == 1
    assert "requestAnimationFrame(geometry)" in js and 'addEventListener("resize", scheduleGeometry)' in js
    assert "ResizeObserver" not in js and "setInterval" not in js
    assert '"aria-hidden":"true", focusable:"false"' in js
