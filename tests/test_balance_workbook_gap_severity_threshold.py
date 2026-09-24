# 回归（BAL-P1-08，owner 2026-08-12 裁决）：期限缺口 severity 阈值为绝对亿元口径，
# 以万元表达：high ≥ 100 亿元（=1,000,000 万元），medium ≥ 10 亿元（=100,000 万元）。
# 原 20/5 万元阈值在银行体量（生产校准 2026-07-29..31：资产约 3600-3800 亿元，
# 桶级 |全口径缺口| p25≈90 亿 / p50≈206 亿 / max≈614 亿）下恒为 high，失去区分度。
#
# 单体权威实现 balance_analysis_workbook.py 与休眠拆分副本 balance_workbook/_utils.py
# 必须双侧同步（双实现等价性，防止副本漂移；参照 test_balance_workbook_campisi_rate.py）。
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.balance_analysis_workbook import (
    _severity_from_gap as _severity_from_gap_monolith,
)
from backend.app.core_finance.balance_workbook._utils import (
    _severity_from_gap as _severity_from_gap_package,
)

_BOTH_SIDES = (_severity_from_gap_monolith, _severity_from_gap_package)

# (gap 万元, 期望标签)；边界含等于（>=）
_BOUNDARY_CASES = [
    (Decimal("1000000"), "high"),  # 恰为 100 亿 → high（边界含等于）
    (Decimal("999999.99"), "medium"),  # 100 亿以下一分钱 → medium
    (Decimal("100000"), "medium"),  # 恰为 10 亿 → medium（边界含等于）
    (Decimal("99999.99"), "low"),  # 10 亿以下一分钱 → low
    (Decimal("0"), "low"),
    (Decimal("20"), "low"),  # 旧 high 阈值（20 万元）在新口径下为 low
    (Decimal("5"), "low"),  # 旧 medium 阈值（5 万元）在新口径下为 low
    (Decimal("-1000000"), "high"),  # 负缺口按绝对值判级
    (Decimal("-100000"), "medium"),
    (Decimal("-99999.99"), "low"),
    (Decimal("6137559"), "high"),  # 校准观测最大桶缺口 ≈ 613.76 亿
]


@pytest.mark.parametrize("gap_wan, expected", _BOUNDARY_CASES)
def test_monolith_severity_thresholds_use_absolute_yi_bands(gap_wan: Decimal, expected: str) -> None:
    assert _severity_from_gap_monolith(gap_wan) == expected


@pytest.mark.parametrize("gap_wan, expected", _BOUNDARY_CASES)
def test_package_severity_thresholds_use_absolute_yi_bands(gap_wan: Decimal, expected: str) -> None:
    assert _severity_from_gap_package(gap_wan) == expected


def test_monolith_and_package_severity_are_identical_across_sweep() -> None:
    # 0 元到 1000 亿元的粗扫 + 边界点，双实现输出必须逐点一致
    sweep = [case[0] for case in _BOUNDARY_CASES]
    sweep += [Decimal(step) * Decimal("50000") for step in range(0, 201)]  # 0..10,000,000 万元
    for gap_wan in sweep:
        assert _severity_from_gap_monolith(gap_wan) == _severity_from_gap_package(gap_wan), gap_wan
