"""executive 排除面标记纪律守卫（纯静态 AST 扫描，不 import、不执行被扫描的测试）。

tests/AGENTS.md（Required markers / Three enforcement tiers）要求：排除面上的
executive 测试模块必须携带模块级 ``pytestmark``，同时给出层级标记
（``excluded_surface_regression`` 或 ``excluded_surface_acceptance``）与主表面标记
``surface_executive``。本守卫扫描 tests/ 与 backend/tests/ 下全部
``test_executive*.py``，任何未登记豁免且缺标记的文件都会导致守卫失败。

豁免清单（EXEMPT_FILES）只收录已审阅的落地 E1 稳定面文件：

- pytest.ini 对 ``surface_executive`` 的定义是 "executive surfaces beyond the
  landed E1 stable set"，落地 E1 golden/release 契约不在该表面语义内；
- 这些文件是 scripts/backend_release_suite.py 固定门禁成员，与同为 E1 golden
  的 tests/test_golden_samples_capture_ready.py 同样保持无标记进入默认门禁。

新增 executive 测试文件时：按 tests/AGENTS.md 判定层级并补模块级 pytestmark；
只有经审阅确认属落地 E1 稳定面 golden/release 契约时才允许在此登记豁免。
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()

SCAN_ROOTS = ("tests", "backend/tests")
TIER_MARKERS = {"excluded_surface_regression", "excluded_surface_acceptance"}
SURFACE_MARKER = "surface_executive"

# 已审阅豁免：落地 E1 稳定面 golden/release 契约（理由见模块 docstring）。
EXEMPT_FILES = {
    "tests/test_executive_release_contract.py",
}


def _executive_test_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        files.extend(
            path for path in base.rglob("test_executive*.py") if path.resolve() != SELF_PATH
        )
    return sorted(files)


def _module_pytestmark_markers(source: str) -> set[str]:
    """Collect marker attribute names referenced by module-level ``pytestmark``.

    静态 AST 解析（含 utf-8-sig 兼容 BOM 文件），仅识别模块级赋值；类级/用例级
    标记不满足 tests/AGENTS.md 的“模块级 pytestmark 优先”纪律，不计入。
    """

    tree = ast.parse(source)
    markers: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in targets):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute):
                markers.add(child.attr)
    return markers


def test_exempt_entries_point_at_existing_executive_files() -> None:
    scanned = {path.relative_to(REPO_ROOT).as_posix() for path in _executive_test_files()}
    stale = sorted(rel for rel in EXEMPT_FILES if rel not in scanned)
    assert not stale, "豁免清单指向不存在（或已改名）的文件，请同步清理：\n" + "\n".join(stale)


def test_executive_test_modules_declare_boundary_markers() -> None:
    violations: list[str] = []
    for path in _executive_test_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in EXEMPT_FILES:
            continue
        markers = _module_pytestmark_markers(path.read_text(encoding="utf-8-sig"))
        missing: list[str] = []
        if not markers & TIER_MARKERS:
            missing.append("excluded_surface_regression 或 excluded_surface_acceptance")
        if SURFACE_MARKER not in markers:
            missing.append(SURFACE_MARKER)
        if missing:
            violations.append(f"{rel}: 缺少模块级 pytestmark 标记（{ '，'.join(missing) }）")

    assert not violations, (
        "executive 测试模块必须按 tests/AGENTS.md 携带层级标记 + surface_executive，"
        "或经审阅后在本守卫的 EXEMPT_FILES 登记 E1 稳定面豁免：\n" + "\n".join(violations)
    )


def test_marker_collector_matches_expected_semantics() -> None:
    sample = "\n".join(
        [
            "import pytest",
            "pytestmark = [",
            "    pytest.mark.excluded_surface_regression,",
            "    pytest.mark.surface_executive,",
            "]",
        ]
    )
    assert _module_pytestmark_markers(sample) >= {
        "excluded_surface_regression",
        SURFACE_MARKER,
    }

    # 类级/用例级标记不计入模块级纪律。
    class_level_only = "\n".join(
        [
            "import pytest",
            "class TestX:",
            "    pytestmark = [pytest.mark.surface_executive]",
        ]
    )
    assert _module_pytestmark_markers(class_level_only) == set()
