from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_backend_dependency_contract_keeps_runtime_and_dev_dependencies_separated() -> (
    None
):
    pyproject = tomllib.loads(
        (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    )

    dependencies = pyproject["project"]["dependencies"]
    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]

    assert "anyio>=4.0,<5" in dependencies
    assert "pandas>=2.2,<3" in dependencies
    assert "numpy>=1.26,<3" in dependencies
    assert "scipy>=1.13,<2" in dependencies

    assert "pytest-xdist>=3.6,<4" in dev_dependencies
    assert "pandas>=2.2,<3" not in dev_dependencies
