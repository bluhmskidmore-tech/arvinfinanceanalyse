# 回归（B10-4，2026-08 审计）：compute_liabilities_monthly 不得依赖调用方 SQL 预过滤。
# 历史唯一调用方 fetch_zqtz_liability_rows_for_year 在 SQL 侧
# coalesce(is_issuance_like, false) 预过滤且结果集不带 is_issuance_like 列；
# 新调用方直接传全量 ZQTZ 行时，资产债券行曾被静默计入发行负债。
# 修复后：携带 is_issuance_like 键且 falsy/None 的行在函数内剔除（与
# compute_liability_risk_buckets 的发行类过滤、SQL coalesce 语义一致），
# 剔除发生在月度天数分母记账之前；不带该键的行按预过滤契约信任（幂等）。
from __future__ import annotations

import pytest

from backend.app.core_finance.liability_analytics_compat import compute_liabilities_monthly

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_liability_analytics,
]


def _issuance_row(*, report_date: str, amount: str, flag: object = True) -> dict:
    row = {
        "report_date": report_date,
        "amortized_cost_native": amount,
        "coupon_rate": "2",
        "bond_type": "同业存单",
        "maturity_date": "2026-12-31",
    }
    if flag is not ...:
        row["is_issuance_like"] = flag
    return row


def test_full_rows_input_excludes_asset_side_rows_and_their_dates() -> None:
    rows = [
        _issuance_row(report_date="2026-01-15", amount="100", flag=True),
        # 资产侧行（显式 False）：金额不得计入发行负债。
        _issuance_row(report_date="2026-01-15", amount="999", flag=False),
        # 快照 NULL 标志（None）：与 SQL coalesce(is_issuance_like, false) 同语义，
        # 剔除且其快照日期（01-20）不得进入月度平均天数分母。
        _issuance_row(report_date="2026-01-20", amount="888", flag=None),
    ]

    payload = compute_liabilities_monthly(2026, rows, [])

    assert len(payload["months"]) == 1
    month = payload["months"][0]
    assert month["month"] == "2026-01"
    # 若资产行日期被记入天数分母，avg 会被错误摊薄为 50；若资产金额被计入，
    # avg 会虚增为 1099/1987。
    assert month["num_days"] == 1
    assert month["avg_total_liabilities"] == 100.0
    assert month["avg_issued_liabilities"] == 100.0


def test_prefiltered_rows_without_flag_key_are_trusted_unchanged() -> None:
    # 复刻 fetch_zqtz_liability_rows_for_year 的真实输出形状：SQL 预过滤后
    # 不携带 is_issuance_like 列，行为必须与修复前完全一致（幂等）。
    rows = [
        _issuance_row(report_date="2026-02-10", amount="50", flag=...),
        _issuance_row(report_date="2026-02-20", amount="150", flag=...),
    ]

    payload = compute_liabilities_monthly(2026, rows, [])

    assert len(payload["months"]) == 1
    month = payload["months"][0]
    assert month["month"] == "2026-02"
    assert month["num_days"] == 2
    assert month["avg_total_liabilities"] == 100.0
    assert payload["ytd_avg_total_liabilities"] == 100.0
