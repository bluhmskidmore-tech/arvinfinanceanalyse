"""Campisi 决策级正式 PnL 闭合判定的负向/分级测试。

修复前：explained_pnl = fixed_components + selection_proxy + residual_noise ≡ actual_pnl，
service 层 `abs(explained_pnl - formal_actual_pnl) <= 0.01` 代数恒真——假门禁、解释率恒 100%。
修复后：explained_pnl 只累加固定因子，闭合判定必须能真实地判为未闭合（可失败），
同时在固定因子确实解释了全部 PnL 时仍能判为 closed（可通过）。
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.core_finance.campisi_decision_grade import compute_decision_grade_row
from backend.app.services import campisi_attribution_service as campisi_svc
from backend.app.services.campisi_attribution_service import (
    _decision_pnl_closure,
    _decision_quality_flag,
)
from tests.test_campisi_decision_grade import (
    _create_decision_grade_tables,
    _seed_decision_grade_sample,
)


def _flat_row(*, actual_pnl: float, carry: float, realized: float = 0.0, manual: float = 0.0) -> dict:
    """构造无市场效应的行：只有 carry/realized/manual 属于固定因子。"""
    return {
        "actual_pnl": actual_pnl,
        "carry": carry,
        "realized_trading": realized,
        "manual_adjustment": manual,
        "market_value": 0.0,
        "modified_duration": 0.0,
        "convexity": 0.0,
        "spread_dv01": 0.0,
        "years_to_maturity": 5.0,
        "is_credit": False,
    }


def _closure_for_row(row: dict) -> dict:
    computed = compute_decision_grade_row(
        row,
        treasury_start=None,
        treasury_end=None,
        credit_start_by_rating={},
        credit_end_by_rating={},
    )
    closure = _decision_pnl_closure(
        explained_pnl=computed["explained_pnl"],
        formal_actual_pnl=computed["actual_pnl"],
    )
    return {"computed": computed, "closure": closure}


# ---------------------------------------------------------------------------
# 负向：固定因子与 actual_pnl 出现真实缺口 -> explained != actual 且未闭合
# ---------------------------------------------------------------------------
def test_decision_grade_real_gap_is_not_closed() -> None:
    # actual=100，但固定因子只解释 carry=10，缺口 90 进入 selection_proxy（非固定因子）。
    result = _closure_for_row(_flat_row(actual_pnl=100.0, carry=10.0))
    computed = result["computed"]
    closure = result["closure"]

    assert computed["explained_pnl"] == Decimal("10")
    assert computed["actual_pnl"] == Decimal("100")
    # 关键：explained_pnl 不再恒等于 actual_pnl（此前的假门禁）。
    assert computed["explained_pnl"] != computed["actual_pnl"]
    assert computed["components"]["selection_proxy"] == Decimal("90")

    assert closure["status"] != "closed"
    assert closure["status"] == "error"  # |90/100| = 0.9 > 0.10
    assert closure["difference"] == pytest.approx(90.0)  # actual - explained


def test_decision_grade_residual_noise_gap_is_not_closed() -> None:
    # 缺 analytics -> 缺口进入 residual_noise（同样是平衡项，不算解释）。
    row = _flat_row(actual_pnl=100.0, carry=10.0)
    row["missing_analytics"] = True
    result = _closure_for_row(row)
    computed = result["computed"]
    closure = result["closure"]

    assert computed["components"]["residual_noise"] == Decimal("90")
    assert computed["components"]["selection_proxy"] == Decimal("0")
    assert computed["explained_pnl"] == Decimal("10")
    assert closure["status"] != "closed"


# ---------------------------------------------------------------------------
# 正向：固定因子完全解释 actual_pnl -> 门禁仍能判为 closed（证明不是恒失败）
# ---------------------------------------------------------------------------
def test_decision_grade_fully_explained_still_closes() -> None:
    result = _closure_for_row(_flat_row(actual_pnl=100.0, carry=60.0, realized=30.0, manual=10.0))
    computed = result["computed"]
    closure = result["closure"]

    assert computed["explained_pnl"] == Decimal("100")
    assert computed["actual_pnl"] == Decimal("100")
    assert computed["components"]["selection_proxy"] == Decimal("0")
    assert closure["status"] == "closed"
    assert closure["difference"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _decision_pnl_closure 分级阈值（绝对 + 相对）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("explained", "actual", "expected_status", "expected_difference"),
    [
        # 绝对阈值：|difference| <= 0.01 -> closed
        (Decimal("100.005"), Decimal("100"), "closed", -0.005),
        (Decimal("100"), Decimal("100"), "closed", 0.0),
        # 相对阈值：|difference/actual| <= 0.05 -> closed
        (Decimal("970"), Decimal("1000"), "closed", 30.0),
        # 0.05 < ratio <= 0.10 -> warning（含 0.10 边界）
        (Decimal("920"), Decimal("1000"), "warning", 80.0),
        (Decimal("900"), Decimal("1000"), "warning", 100.0),
        # ratio > 0.10 -> error
        (Decimal("800"), Decimal("1000"), "error", 200.0),
        (Decimal("1200"), Decimal("1000"), "error", -200.0),
        # actual = 0：有缺口无法归一化 -> error；无缺口 -> closed
        (Decimal("5"), Decimal("0"), "error", -5.0),
        (Decimal("0"), Decimal("0"), "closed", 0.0),
    ],
)
def test_decision_pnl_closure_grading(
    explained: Decimal,
    actual: Decimal,
    expected_status: str,
    expected_difference: float,
) -> None:
    closure = _decision_pnl_closure(explained_pnl=explained, formal_actual_pnl=actual)
    assert closure["status"] == expected_status
    assert closure["difference"] == pytest.approx(expected_difference)
    assert closure["basis"] == "fact_formal_pnl_fi.total_pnl"


def test_decision_pnl_closure_ratio_none_when_actual_zero_and_gap() -> None:
    closure = _decision_pnl_closure(explained_pnl=Decimal("5"), formal_actual_pnl=Decimal("0"))
    assert closure["difference_ratio"] is None
    assert closure["status"] == "error"


# ---------------------------------------------------------------------------
# closure 分级必须上抛到 quality_flag：closure=error 不得停留在 "ok"
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("closure_status", "warnings", "residual_noise", "expected"),
    [
        ("closed", [], Decimal("0"), "ok"),
        # 缺口只落在 selection_proxy 时 residual_noise 仍为 0，只有 closure 能识别。
        ("warning", [], Decimal("0"), "warning"),
        ("error", [], Decimal("0"), "error"),
        # 既有信号保持不变。
        ("closed", ["缺曲线"], Decimal("0"), "warning"),
        ("closed", [], Decimal("5"), "warning"),
        # closure=error 的严重度不被其他 warning 稀释。
        ("error", ["缺曲线"], Decimal("5"), "error"),
    ],
)
def test_decision_quality_flag_escalates_with_closure_status(
    closure_status: str,
    warnings: list[str],
    residual_noise: Decimal,
    expected: str,
) -> None:
    assert (
        _decision_quality_flag(
            warnings=warnings,
            residual_noise=residual_noise,
            closure_status=closure_status,
        )
        == expected
    )


def test_decision_grade_envelope_escalates_quality_flag_when_closure_is_error(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """端到端负向：仓库自带样本 closure=error（difference_ratio 91.6%）。

    修复前 residual_noise=0 且 warnings 为空，quality_flag 恒为 "ok" —— closure=error
    永不升级的假门禁。修复后必须升级为 error 并追加说明性 warning。
    """
    db_path = tmp_path / "decision_grade_closure_quality.duckdb"
    _create_decision_grade_tables(db_path)
    _seed_decision_grade_sample(db_path)
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(db_path), governance_path=str(tmp_path)),
    )

    envelope = campisi_svc.campisi_decision_grade_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )
    result = envelope["result"]

    assert result["formal_pnl_view"]["closure"]["status"] == "error"
    assert result["summary"]["residual_noise"] == pytest.approx(0.0)
    assert result["summary"]["quality_flag"] == "error"
    assert envelope["result_meta"]["quality_flag"] == "error"
    assert any("未闭合" in warning for warning in result["warnings"])
