"""回归测试：core_finance 不得反向 import repositories（CFFEX 会员持仓排名下沉）。

背景：`backend/app/core_finance/macro/toolkit/scripts/crowding_cn.py` 与
`backend/app/core_finance/macro/toolkit/WindPy.py` 曾直接
`from backend.app.repositories.cffex_member_rank_repo import ...`，违反
core_finance 纯计算层红线。表名/视图名常量与相关只读函数已下沉到
`backend.app.core_finance.macro.toolkit.cffex_member_rank_shared`，
`backend.app.repositories.cffex_member_rank_repo` 从该模块 re-export
以保持向后兼容。

本文件验证：
1. 冷导入两个曾违规的文件不会加载任何 ``backend.app.repositories`` 模块。
2. repositories 侧的 re-export 与 core_finance 侧的下沉定义是同一对象
   （非重复定义），杜绝未来出现双份定义漂移。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _assert_cold_import_has_no_repositories(import_statement: str) -> None:
    code = (
        "import sys; "
        f"{import_statement}; "
        "loaded = sorted("
        "m for m in sys.modules "
        "if m.startswith('backend.app.repositories')"
        "); "
        "assert not loaded, loaded"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr


def test_windpy_cold_import_stays_pure_of_repositories() -> None:
    _assert_cold_import_has_no_repositories("import backend.app.core_finance.macro.toolkit.WindPy")


def test_crowding_cn_cold_import_stays_pure_of_repositories() -> None:
    _assert_cold_import_has_no_repositories(
        "import backend.app.core_finance.macro.toolkit.scripts.crowding_cn"
    )


def test_repo_reexports_are_identical_objects_to_shared_module() -> None:
    """repositories 侧只做 re-export，不得出现第二份独立定义（防止漂移）。"""
    from backend.app.core_finance.macro.toolkit import cffex_member_rank_shared as shared
    from backend.app.repositories import cffex_member_rank_repo as repo

    assert repo.TABLE_NAME is shared.TABLE_NAME
    assert repo.VIEW_NAME is shared.VIEW_NAME
    assert repo.normalize_cffex_contract is shared.normalize_cffex_contract
    assert repo.normalize_trade_date is shared.normalize_trade_date
    assert repo.load_member_rank_frame is shared.load_member_rank_frame


def test_shared_constants_match_documented_table_and_view_names() -> None:
    from backend.app.core_finance.macro.toolkit import cffex_member_rank_shared as shared

    assert shared.TABLE_NAME == "fact_cffex_member_rank_daily"
    assert shared.VIEW_NAME == "vw_cffex_member_rank_daily"
