from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict:
    return tomllib.loads(
        (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    )


def test_backend_dependency_contract_keeps_runtime_and_dev_dependencies_separated() -> (
    None
):
    pyproject = _pyproject()

    dependencies = pyproject["project"]["dependencies"]
    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]

    assert "anyio>=4.0,<5" in dependencies
    assert "pandas>=2.2,<3" in dependencies
    assert "numpy>=1.26,<3" in dependencies
    assert "scipy>=1.13,<2" in dependencies

    assert "pytest-xdist>=3.6,<4" in dev_dependencies
    assert "pandas>=2.2,<3" not in dev_dependencies


def test_starlette_is_explicitly_constrained_instead_of_a_free_transitive() -> None:
    """starlette 直接出现在中间件/TestClient 链路上，却曾只由 fastapi 间接决定版本，
    因此在没有任何回归门禁的情况下从 0.x 跨到了 1.x。它必须自带 major 上界。"""

    dependencies = _pyproject()["project"]["dependencies"]
    starlette = [spec for spec in dependencies if spec.startswith("starlette")]

    assert starlette, "starlette 必须显式声明，不能只作为 fastapi 的传递依赖"
    assert "<2" in starlette[0], f"starlette 必须钉住 major 上界: {starlette[0]}"


def test_lazily_imported_runtime_packages_are_declared_in_an_extra() -> None:
    """代码里以惰性 import 使用的 PyPI 包必须落到某个 extra。

    未声明 = 不进 uv.lock = 对 OSV 门禁永久不可见（scripts/osv_reconciliation_gate.py
    扫的是 backend/uv.lock）。akshare 一条就会带进 lxml / pillow / curl-cffi /
    mini-racer 这类解析外部不可信输入的库。
    """

    extras = _pyproject()["project"]["optional-dependencies"]
    declared = {
        re.split(r"[<>=!~\[]", spec, maxsplit=1)[0].strip().lower()
        for specs in extras.values()
        for spec in specs
    }

    # WindPy / EmQuantAPI 由 Wind / Choice 终端捆绑分发，PyPI 无对应包，无法进 lock。
    for package in ("akshare", "tushare", "matplotlib", "python-docx"):
        assert package in declared, f"{package} 被运行时惰性 import，但没有进任何 extra"


def test_ci_installs_the_backend_from_the_lockfile_instead_of_resolving_afresh() -> None:
    """CI 装的东西必须就是 OSV 扫的东西。

    `pip install -e "./backend[dev]"` 会按 pyproject 的版本范围当日重新解析，
    装出的集合与 backend/uv.lock 无关，`uv lock --check` 就退化成摆设校验。
    """

    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert 'pip install -e "./backend' not in workflow
    assert "pip install -e ./backend" not in workflow
    assert "uv sync --frozen --project backend" in workflow
