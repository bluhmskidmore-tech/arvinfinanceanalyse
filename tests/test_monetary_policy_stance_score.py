"""M7 货币政策立场 `_score_term_structure` 分段边界单测。

业务口径（owner 已确认）：[50,80) 段斜率改为 100/30，使该段在 80bp 处
精确衔接满分 100，保留"80bp 及以上满分"语义；旧系数 1.67 在 80⁻ 处仅得
≈49.9，与 ≥80 段存在约 50 分跳变。0 与 20 处的台阶为既有分层设计，保持原样。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.macro.monetary_policy_stance import _score_term_structure


@pytest.mark.parametrize(
    ("slope_bp", "expected"),
    [
        # slope < 0：倒挂 → -100。
        (Decimal("-0.01"), Decimal("-100")),
        # [0,20)：平段 → -60（既有台阶，保持原样）。
        (Decimal("0"), Decimal("-60")),
        (Decimal("19.99"), Decimal("-60")),
        # [20,50)：-20 + (slope-20)*0.67（保持原样）；49.99 → 0.0933。
        (Decimal("20"), Decimal("-20")),
        (Decimal("49.99"), Decimal("0.0933")),
        # [50,80)：(slope-50)*100/30；50 处 =0 与上一段末端 ≈0.09 保持原有近似衔接。
        (Decimal("50"), Decimal("0")),
        (Decimal("65"), Decimal("50")),
        # ≥80：满分语义不变。
        (Decimal("80"), Decimal("100")),
        (Decimal("100"), Decimal("100")),
    ],
)
def test_score_term_structure_boundary_points(slope_bp: Decimal, expected: Decimal) -> None:
    score = _score_term_structure(slope_bp)

    assert isinstance(score, Decimal)
    assert score == expected


def test_score_term_structure_just_below_80_is_near_full_score() -> None:
    # 79.99 → 29.99 * 100/30 ≈ 99.9667（旧口径为 49.93）。
    score = _score_term_structure(Decimal("79.99"))

    assert isinstance(score, Decimal)
    assert float(score) == pytest.approx(99.9667, abs=0.001)


def test_score_term_structure_continuous_at_80_boundary() -> None:
    # 修复目标：80bp 边界不再跳变（旧口径落差约 50 分）。
    below = _score_term_structure(Decimal("79.99"))
    at_boundary = _score_term_structure(Decimal("80"))

    assert below is not None
    assert at_boundary is not None
    assert Decimal("0") <= at_boundary - below < Decimal("0.05")


def test_score_term_structure_none_returns_none() -> None:
    assert _score_term_structure(None) is None
