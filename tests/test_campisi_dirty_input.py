"""Campisi 脏输入语义测试（A3-2：decimal 落零点位治理）。

约定（两级语义必须可区分）：
- 真缺失（None / NaN / 空白 / "nan|none|null" 占位符）→ 维持既有 0 聚合语义；
- 脏输入（非数字字符串、不可解析对象、无穷）→ DirtyNumericInputError，禁止静默落零；
- 决策评级 envelope 对脏行逐行降级：跳过 + warning 披露，不产出假 0 行。
"""
from __future__ import annotations

import logging
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.core_finance.campisi_decision_grade import (
    ZERO,
    DirtyNumericInputError,
    compute_decision_grade_row,
    decimal_value,
)
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.services import campisi_attribution_service as campisi_svc
from tests.test_campisi_decision_grade import (
    _create_decision_grade_tables,
    _seed_decision_grade_sample,
)

pytestmark = pytest.mark.unit

MISSING_INPUTS = [
    None,
    "",
    "   ",
    "nan",
    "None",
    "NULL",
    float("nan"),
    Decimal("NaN"),
]

DIRTY_INPUTS = [
    "abc",
    "12,5",
    "N/A",
    "inf",
    float("inf"),
    float("-inf"),
    Decimal("Infinity"),
    # Stable id: repr(object()) embeds a memory address, which breaks
    # pytest-xdist collection consistency across workers.
    pytest.param(object(), id="object-instance"),
    [1],
    {"raw": 1},
]

VALID_INPUTS = [
    ("1.5", Decimal("1.5")),
    (2, Decimal("2")),
    (-1.25, Decimal("-1.25")),
    (Decimal("-3.25"), Decimal("-3.25")),
    (0, ZERO),
]


# ---------------------------------------------------------------------------
# core_finance.campisi_decision_grade.decimal_value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", MISSING_INPUTS, ids=repr)
def test_decision_decimal_true_missing_maps_to_zero(value) -> None:
    assert decimal_value(value) == ZERO


@pytest.mark.parametrize("value", DIRTY_INPUTS, ids=repr)
def test_decision_decimal_dirty_raises_instead_of_zero(value) -> None:
    with pytest.raises(DirtyNumericInputError):
        decimal_value(value)


@pytest.mark.parametrize(("value", "expected"), VALID_INPUTS, ids=repr)
def test_decision_decimal_valid_inputs_parse(value, expected) -> None:
    assert decimal_value(value) == expected


# ---------------------------------------------------------------------------
# services.campisi_attribution_service._decimal_value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", MISSING_INPUTS, ids=repr)
def test_service_decimal_true_missing_maps_to_zero(value) -> None:
    assert campisi_svc._decimal_value(value) == Decimal("0")


@pytest.mark.parametrize("value", DIRTY_INPUTS, ids=repr)
def test_service_decimal_dirty_raises_instead_of_zero(value) -> None:
    with pytest.raises(DirtyNumericInputError):
        campisi_svc._decimal_value(value)


@pytest.mark.parametrize(("value", "expected"), VALID_INPUTS, ids=repr)
def test_service_decimal_valid_inputs_parse(value, expected) -> None:
    assert campisi_svc._decimal_value(value) == expected


def test_service_numeric_raw_dirty_payload_raises() -> None:
    with pytest.raises(DirtyNumericInputError):
        campisi_svc._numeric_raw({"raw": "not-a-number"})


def test_missing_and_dirty_semantics_are_distinguishable() -> None:
    """真 None 走 0（不抛异常）；脏输入抛异常（不产出 0）——两种语义不可混同。"""
    assert decimal_value(None) == ZERO
    assert campisi_svc._decimal_value(None) == Decimal("0")
    with pytest.raises(DirtyNumericInputError):
        decimal_value("dirty-value")
    with pytest.raises(DirtyNumericInputError):
        campisi_svc._decimal_value("dirty-value")


# ---------------------------------------------------------------------------
# compute_decision_grade_row：脏字段向上抛，真缺失照旧
# ---------------------------------------------------------------------------


def _decision_row(actual_pnl) -> dict:
    return {
        "actual_pnl": actual_pnl,
        "carry": 1.0,
        "realized_trading": 0.0,
        "manual_adjustment": 0.0,
        "market_value": 100.0,
        "modified_duration": 0.0,
        "convexity": 0.0,
        "spread_dv01": 0.0,
        "years_to_maturity": 5.0,
        "is_credit": False,
    }


def test_compute_decision_grade_row_dirty_field_raises() -> None:
    with pytest.raises(DirtyNumericInputError):
        compute_decision_grade_row(
            _decision_row("N/A"),
            treasury_start=None,
            treasury_end=None,
            credit_start_by_rating={},
            credit_end_by_rating={},
        )


def test_compute_decision_grade_row_true_none_keeps_missing_semantics() -> None:
    result = compute_decision_grade_row(
        _decision_row(None),
        treasury_start=None,
        treasury_end=None,
        credit_start_by_rating={},
        credit_end_by_rating={},
    )
    assert result["actual_pnl"] == ZERO


# ---------------------------------------------------------------------------
# 决策评级 envelope：脏行跳过 + 披露，不产出假 0 行
# ---------------------------------------------------------------------------


def test_decision_grade_envelope_skips_dirty_row_and_discloses(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "decision_grade_dirty.duckdb"
    _create_decision_grade_tables(db_path)
    _seed_decision_grade_sample(db_path)
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(db_path), governance_path=str(tmp_path)),
    )

    original_fetch = PnlRepository.fetch_campisi_decision_pnl_rows

    def fetch_with_dirty_row(self, report_date, *, conn=None):
        rows = original_fetch(self, report_date, conn=conn)
        dirty = dict(rows[0])
        dirty["total_pnl"] = "N/A"  # 脏输入：数值列出现非数字字符串
        return rows + [dirty]

    monkeypatch.setattr(PnlRepository, "fetch_campisi_decision_pnl_rows", fetch_with_dirty_row)

    envelope = campisi_svc.campisi_decision_grade_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )
    result = envelope["result"]

    # 干净行照常闭合（100 + 7），脏行不得以 0 计入总额或行数。
    assert result["summary"]["formal_actual_pnl"] == pytest.approx(107.0)
    assert result["summary"]["bond_scope_row_count"] == 2
    assert result["residual_diagnostics"]["dirty_input_row_count"] == 1
    assert any("脏数值输入" in warning for warning in result["warnings"])
    # 样本自身 closure=error（缺口 98/107 落在 selection_proxy），质量信号取更严重的一档。
    assert result["formal_pnl_view"]["closure"]["status"] == "error"
    assert result["summary"]["quality_flag"] == "error"
    # 会计矩阵不被脏行污染（脏行既不加 0 也不加错值）。
    assert result["accounting_matrix"]["FVTPL"]["formal_pnl"] == pytest.approx(100.0)
    assert result["accounting_matrix"]["FVOCI"]["formal_pnl"] == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# _try_fetch_formal_bridge：宽捕获窄化 + warning 日志
# ---------------------------------------------------------------------------


def test_try_fetch_formal_bridge_degrades_on_data_unavailable_with_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def raise_unavailable(**kwargs):
        raise ValueError("No pnl bridge data found for report_date=2026-01-31")

    monkeypatch.setattr(campisi_svc, "_fetch_formal_bridge", raise_unavailable)
    with caplog.at_level(logging.WARNING, logger=campisi_svc.__name__):
        assert (
            campisi_svc._try_fetch_formal_bridge(
                settings=SimpleNamespace(),
                report_date="2026-01-31",
            )
            is None
        )
    assert any("正式 PnL 桥接不可用" in record.getMessage() for record in caplog.records)


def test_try_fetch_formal_bridge_no_longer_swallows_programming_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_bug(**kwargs):
        raise KeyError("total_actual_pnl")

    monkeypatch.setattr(campisi_svc, "_fetch_formal_bridge", raise_bug)
    with pytest.raises(KeyError):
        campisi_svc._try_fetch_formal_bridge(
            settings=SimpleNamespace(),
            report_date="2026-01-31",
        )
