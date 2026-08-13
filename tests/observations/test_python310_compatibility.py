from __future__ import annotations

import ast
from datetime import timezone
from pathlib import Path

from app.observations.models import UTC


PROJECT_ROOT = Path(__file__).parents[2]
PYTHON_310_TARGETS = (
    PROJECT_ROOT / "app" / "observations" / "models.py",
    PROJECT_ROOT / "tests" / "observations" / "capacity_benchmark.py",
)


def test_observation_utc_alias_is_python310_compatible():
    assert UTC is timezone.utc


def test_observation_files_do_not_import_datetime_utc():
    for path in PYTHON_310_TARGETS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "datetime"
            for alias in node.names
        }
        assert "UTC" not in imported_names, path
