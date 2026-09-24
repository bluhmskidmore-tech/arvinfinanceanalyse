"""Plan E 落地测试：`/pnl-by-business` 与 `/product-category-pnl` 跨页 FTP 利率口径一致性。

Plan E（方案A）已于 2026-07-07 落地：`/pnl-by-business` 不再使用硬编码常量
`FTP_RATE_PCT = Decimal("1.600000")`，改为与 `/product-category-pnl` 相同的
按报表年份查表口径 `FTP_RATE_PCT_BY_REPORT_YEAR`（经 `resolve_product_category_ftp_rate_pct`
解析）。本测试钉住两页在 2024/2025/2026 三个报表年份下的利率完全一致，
防止未来再次出现口径分歧回归。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.config.product_category_mapping import (
    FTP_RATE_PCT_BY_REPORT_YEAR,
    resolve_product_category_ftp_rate_pct,
)
from tests.helpers import load_module

precompute_module = load_module(
    "backend.app.tasks.pnl_by_business_precompute",
    "backend/app/tasks/pnl_by_business_precompute.py",
)


@pytest.mark.parametrize(
    ("report_year", "expected_rate_pct"),
    [
        (2024, Decimal("2.00")),
        (2025, Decimal("1.75")),
        (2026, Decimal("1.60")),
    ],
)
def test_pnl_by_business_ftp_rate_matches_product_category_year_table(
    report_year: int, expected_rate_pct: Decimal
) -> None:
    """两页对同一报表年份解析出的 FTP 利率必须相等，杜绝重新出现口面分歧。"""
    product_category_rate = resolve_product_category_ftp_rate_pct(
        date(report_year, 6, 15), Decimal("9.99")
    )
    pnl_by_business_rate = resolve_product_category_ftp_rate_pct(
        date(report_year, 12, 31), Decimal("9.99")
    )

    assert product_category_rate == expected_rate_pct
    assert pnl_by_business_rate == expected_rate_pct
    assert product_category_rate == pnl_by_business_rate


def test_pnl_by_business_precompute_task_resolves_same_rate_as_year_table() -> None:
    """precompute 任务实际调用的解析函数与年表直接查询结果一致（防止任务层写死或漂移）。"""
    for report_year, expected_rate_pct in FTP_RATE_PCT_BY_REPORT_YEAR.items():
        resolved = precompute_module.resolve_product_category_ftp_rate_pct(
            date(report_year, 12, 31), Decimal("9.99")
        )
        assert resolved == expected_rate_pct


def test_year_table_has_no_hardcoded_pnl_by_business_constant() -> None:
    """确认 pnl-by-business 两个模块已删除硬编码 FTP_RATE_PCT 常量。"""
    from backend.app.services import pnl_service

    assert not hasattr(pnl_service, "FTP_RATE_PCT")
    assert not hasattr(precompute_module, "FTP_RATE_PCT")
