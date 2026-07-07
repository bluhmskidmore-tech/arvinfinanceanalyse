"""Plan E 字征测试：跨页 FTP 利率口径分歧（决策落地前钉住现状）。

`/pnl-by-business` 使用硬编码常量 `FTP_RATE_PCT = Decimal("1.600000")`；
`/product-category-pnl` 按报表年份查表 `FTP_RATE_PCT_BY_REPORT_YEAR`。

2026 年两页数值巧合一致（均为 1.60），2025 年存在口径分歧（1.75 vs 1.60）。
若「2025 口径分歧」相关断言开始失败，说明分歧已被修复，应同步更新本测试与
Plan E 决策文档 `docs/pnl/plan-e-ftp-rate-unification-decision.md`。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.config.product_category_mapping import resolve_product_category_ftp_rate_pct
from backend.app.services import pnl_service
from backend.app.tasks import pnl_by_business_precompute

PNL_BY_BUSINESS_FTP_RATE_PCT = Decimal("1.600000")


def test_pnl_by_business_ftp_rate_constants_match_and_are_one_point_six() -> None:
    """pnl-by-business 两条链路共用同一硬编码 FTP 利率，防止两份字面量漂移。"""
    assert pnl_service.FTP_RATE_PCT == pnl_by_business_precompute.FTP_RATE_PCT
    assert pnl_service.FTP_RATE_PCT == PNL_BY_BUSINESS_FTP_RATE_PCT


def test_product_category_2026_ftp_rate_matches_pnl_by_business() -> None:
    """2026 年 product-category 年表利率与 pnl-by-business 常量数值相等（巧合一致）。"""
    product_category_rate = resolve_product_category_ftp_rate_pct(
        date(2026, 6, 15), Decimal("9.99")
    )
    assert product_category_rate == Decimal("1.60")
    assert product_category_rate == pnl_service.FTP_RATE_PCT


def test_product_category_2025_ftp_rate_diverges_from_pnl_by_business() -> None:
    """2025 年 product-category 年表利率 1.75，与 pnl-by-business 常量 1.60 口径分歧。"""
    product_category_rate = resolve_product_category_ftp_rate_pct(
        date(2025, 3, 31), Decimal("9.99")
    )
    assert product_category_rate == Decimal("1.75")
    assert product_category_rate != pnl_service.FTP_RATE_PCT
