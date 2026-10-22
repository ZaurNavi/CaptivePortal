from pathlib import Path

ROOT = Path(r"C:\CaptivPortal-Lab\coder-work")

changes = {
    ROOT / "tests" / "admin_web" / "test_traffic_peak_frontend.py": [
        (
            '    assert \'"&include=statistics,peak"\' in panel\n',
            '    assert \'"statistics,peak"\' in panel\n'
            '    assert "encodeURIComponent(include)" in panel\n',
        ),
        (
            'assert(url==="/api/traffic/history?range=24h&include=statistics,peak","one combined Peak request")',
            'assert(url==="/api/traffic/history?range=24h&include=statistics%2Cpeak","one combined Peak request")',
        ),
    ],
    ROOT / "tests" / "admin_web" / "test_traffic_statistics_frontend.py": [
        (
            '    assert "&include=statistics" in panel\n',
            '    assert \'"statistics"\' in panel\n'
            '    assert "encodeURIComponent(include)" in panel\n',
        ),
    ],
}

for path, replacements in changes.items():
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"STOP: expected exactly one match in {path}: {old!r}; found {count}")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"UPDATED: {path}")
    print(f"  replacements: {len(replacements)}")
