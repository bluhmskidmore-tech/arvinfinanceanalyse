"""契约测试：ZQTZ 资产侧「其中」细分类在前后端之间保持同步。

前端 `frontend/src/features/pnl/zqtzAdbAvgRollup.ts` 中的
`ADB_AVG_ROLLUP_CHILDREN_BY_PARENT` 是对
`backend/app/core_finance/zqtz_asset_bond_category.py` 里
`ZQTZ_ASSET_BOND_ROWS`（sort_order 83-88 附近的「其中」细分行）
父子关系的手工复刻，并通过
`frontend/src/features/pnl/__fixtures__/zqtzAdbAvgRollupChildren.fixture.json`
与既有 vitest 测试对齐。但那份 vitest 测试只校验
「TS 常量 == fixture JSON」两份人工维护的字符串是否互相一致，
从不读取后端 Python 源，无法发现后端侧的分类漂移。

`ZQTZ_ASSET_BOND_ROWS` 本身没有显式的父子关系字段；「这一行是某个
父类的其中细分」这一事实，唯一稳定编码在 `source_note` 字段里——
sort_order 83-88 这 6 行的 `source_note` 均包含字面量「其中项」
（例如 "ZQTZSHOW 其中项：instrument_code prefix=G0"），而父级行
（如 sort_order 80/82/90）与其余单行分类的 `source_note` 都不含
该字样。据此可从数据里稳定地筛出「细分行」集合，而不必硬编码
sort_order 数字区间（这样即使未来细分行的 sort_order 发生偏移，
只要 source_note 仍标注「其中项」，本测试依然能正确定位）。

本测试据此从后端源出发，与前端 fixture 中 `parents` 下所有子类
标签的并集做双向存在性校验：
- fixture 有、后端没有 -> 后端已删除/改名该分类，fixture 引用了失效标签。
- 后端有、fixture 没有 -> 后端新增了细分类，前端 rollup 未同步。
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.core_finance.zqtz_asset_bond_category import ZQTZ_ASSET_BOND_ROWS

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_PATH = (
    _REPO_ROOT
    / "frontend"
    / "src"
    / "features"
    / "pnl"
    / "__fixtures__"
    / "zqtzAdbAvgRollupChildren.fixture.json"
)
_BACKEND_SOURCE_PATH = _REPO_ROOT / "backend" / "app" / "core_finance" / "zqtz_asset_bond_category.py"

# 唯一稳定的「细分行」判定信号：source_note 中的「其中项」字样（见模块 docstring）。
_DETAIL_ROW_MARKER = "其中项"


def _load_fixture_children_by_parent() -> dict[str, list[str]]:
    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    return fixture["parents"]


def _fixture_child_labels() -> set[str]:
    labels: set[str] = set()
    for children in _load_fixture_children_by_parent().values():
        labels.update(children)
    return labels


def _backend_detail_row_labels() -> set[str]:
    return {
        str(row["row_label"])
        for row in ZQTZ_ASSET_BOND_ROWS
        if _DETAIL_ROW_MARKER in str(row.get("source_note", ""))
    }


def test_fixture_has_at_least_one_detail_label() -> None:
    """先决条件：fixture 必须非空，否则下面两个双向断言会失去意义。"""
    assert _fixture_child_labels(), f"fixture 未声明任何子类标签，请检查 {_FIXTURE_PATH}"


def test_backend_has_at_least_one_detail_row() -> None:
    """先决条件：后端必须存在「其中」细分行，否则说明判定信号已失效。"""
    assert _backend_detail_row_labels(), (
        f"未能在 {_BACKEND_SOURCE_PATH} 的 ZQTZ_ASSET_BOND_ROWS 中找到任何 "
        f"source_note 含「{_DETAIL_ROW_MARKER}」的细分行，判定信号可能已失效，需人工复核"
    )


def test_fixture_child_labels_all_exist_in_backend_rows() -> None:
    """fixture 中列出的每个子类标签，必须能在后端 ZQTZ_ASSET_BOND_ROWS 中找到对应 row_label。"""
    fixture_labels = _fixture_child_labels()
    backend_labels = _backend_detail_row_labels()

    missing_in_backend = sorted(fixture_labels - backend_labels)
    assert not missing_in_backend, (
        f"以下标签仅存在于前端 fixture（{_FIXTURE_PATH}）中，"
        f"但在后端 {_BACKEND_SOURCE_PATH} 的 ZQTZ_ASSET_BOND_ROWS 里已找不到匹配的 "
        f"row_label（source_note 含「{_DETAIL_ROW_MARKER}」的细分行）："
        f"{missing_in_backend}。说明后端已删除/改名该分类，"
        "需要人工确认后同步更新前端 "
        "frontend/src/features/pnl/zqtzAdbAvgRollup.ts 中的 "
        "ADB_AVG_ROLLUP_CHILDREN_BY_PARENT 以及对应 fixture。"
    )


def test_backend_detail_rows_all_covered_by_fixture() -> None:
    """后端「其中」细分行的 row_label，必须全部被前端 fixture 覆盖到。"""
    fixture_labels = _fixture_child_labels()
    backend_labels = _backend_detail_row_labels()

    missing_in_fixture = sorted(backend_labels - fixture_labels)
    assert not missing_in_fixture, (
        f"以下 row_label 存在于后端 {_BACKEND_SOURCE_PATH} 的 ZQTZ_ASSET_BOND_ROWS 中"
        f"（source_note 含「{_DETAIL_ROW_MARKER}」的细分行），"
        f"但未被前端 fixture（{_FIXTURE_PATH}）的 parents 覆盖："
        f"{missing_in_fixture}。说明后端新增了细分类，"
        "需要人工确认后同步更新前端 "
        "frontend/src/features/pnl/zqtzAdbAvgRollup.ts 中的 "
        "ADB_AVG_ROLLUP_CHILDREN_BY_PARENT 以及对应 fixture。"
    )
