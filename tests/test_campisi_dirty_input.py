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

@pytest.mark.parametrize("surface", ["four-effects", "enhanced", "maturity-buckets"])
@pytest.mark.parametrize("business_code", [None, "PNL_BRIDGE_WINDOW_MISMATCH", "DUPLICATE_BALANCE_KEY"])
def test_campisi_api_bridge_failure_preserves_code_without_private_payload(
    monkeypatch, tmp_path, caplog, surface, business_code,
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.api.routes import campisi_attribution as route
    from tests.test_campisi_attribution_service import (
        _bond_row, _flat_treasury, _install_full_service_fakes,
    )

    original_closure = campisi_svc._fetch_formal_closure
    row = _bond_row(code="SYNTHETIC", asset_class="rate", market_value=Decimal("1000"), face_value=Decimal("1000"))
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-08-31", "2026-07-31"],
        rows_by_date={"2026-07-31": [row], "2026-08-31": [row]},
        curves={(day, "treasury"): _flat_treasury(Decimal("3")) for day in ("2026-07-31", "2026-08-31")},
        duckdb_path=str(tmp_path / "unused.duckdb"),
    )
    monkeypatch.setattr(campisi_svc, "_fetch_formal_closure", original_closure)
    marker = "synthetic-campisi-private-source-payload"

    def fail_bridge(**_kwargs):
        raise ValueError(f"{business_code or 'arbitrary data failure'}: {marker}")

    monkeypatch.setattr(campisi_svc, "_fetch_formal_bridge", fail_bridge)
    # Actual route serialization, with authorization and all business data sources isolated.
    monkeypatch.setattr(route, "_ensure_pnl_attribution_read_allowed", lambda _auth: None)
    monkeypatch.setattr(route, "_svc", lambda: campisi_svc)
    app = FastAPI()
    app.dependency_overrides[route.get_auth_context] = lambda: SimpleNamespace(user_id="synthetic-user")
    app.include_router(route.router)
    campisi_svc.clear_campisi_four_effects_runtime_cache()
    try:
        response = TestClient(app).get(
            f"/api/pnl-attribution/campisi/{surface}",
            params={"start_date": "2026-07-31", "end_date": "2026-08-31"},
        )
    finally:
        campisi_svc.clear_campisi_four_effects_runtime_cache()
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["quality_flag"] != "ok"
    if surface == "four-effects":
        closure = payload["result"]["formal_closure"]
        assert closure["status"] == "unavailable"
        assert closure["formal_actual_pnl"] is None
        assert closure["residual_to_formal_pnl"] is None
        assert closure["residual_ratio"] is None
    if business_code:
        assert business_code in response.text
    assert marker not in response.text
    assert marker not in caplog.text
    assert "ValueError" in response.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("entry", ["uncached", "cached", "closure"])
@pytest.mark.parametrize("error_kind", ["type", "attribute", "key", "read_selection"])
def test_campisi_bridge_preserves_programming_and_read_selection_errors(
    monkeypatch, tmp_path, caplog, entry, error_kind,
):
    from backend.app.repositories.duckdb_read_context import DuckDBReadSelectionError

    error_type = {
        "type": TypeError, "attribute": AttributeError,
        "key": KeyError, "read_selection": DuckDBReadSelectionError,
    }[error_kind]
    marker = "synthetic-campisi-error-must-propagate"
    error = error_type(marker)

    def fail(**_kwargs):
        raise error

    monkeypatch.setattr(campisi_svc, "_fetch_formal_bridge", fail)
    settings = SimpleNamespace(duckdb_path=str(tmp_path / "unused.duckdb"), governance_path=str(tmp_path / "gov"))
    kwargs = {"settings": settings, "report_date": "2026-08-31", "start_date": "2026-07-31"}
    warnings = []
    if entry == "closure":
        operation = campisi_svc._fetch_formal_closure
        kwargs["campisi_total_return"] = Decimal("7")
    elif entry == "cached":
        operation = campisi_svc._try_fetch_cached_formal_bridge
        kwargs.update(duckdb_fingerprint=None, warnings=warnings)
    else:
        operation = campisi_svc._try_fetch_formal_bridge
        kwargs["warnings"] = warnings
    campisi_svc.clear_campisi_four_effects_runtime_cache()
    try:
        with pytest.raises(error_type) as caught:
            operation(**kwargs)
    finally:
        campisi_svc.clear_campisi_four_effects_runtime_cache()
    assert caught.value is error
    assert warnings == []
    assert marker not in caplog.text


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


@pytest.mark.parametrize("ambiguous,reverse_order", [(True, False), (True, True), (False, False)])
def test_balance_ambiguity_cannot_become_formal_campisi_closure(
    monkeypatch: pytest.MonkeyPatch, ambiguous: bool, reverse_order: bool,
) -> None:
    from backend.app.core_finance.pnl_bridge import build_pnl_bridge_rows
    from backend.app.services import pnl_bridge_service

    identity = {
        "instrument_code": "SYNTH", "portfolio_name": "P", "cost_center": "C",
        "currency_basis": "CNY", "accounting_basis": "FVTPL",
    }
    balance = {
        **identity, "report_date": "2026-08-31", "market_value_amount": Decimal("100"),
        "face_value_amount": Decimal("100"), "accrued_interest_amount": Decimal("0"),
        "maturity_date": "2030-08-31", "modified_duration": Decimal("2"),
        "bond_type": "企业债", "asset_class": "信用债",
    }
    current = [balance]
    if ambiguous:
        current.append({**balance, "market_value_amount": Decimal("400"),
                        "modified_duration": Decimal("4")})
    if reverse_order:
        current.reverse()
    prior = [{**balance, "report_date": "2026-07-31"}]
    pnl = [{**identity, "report_date": "2026-08-31", "interest_income_514": Decimal("0"),
            "fair_value_change_516": Decimal("-2"), "capital_gain_517": Decimal("0"),
            "manual_adjustment": Decimal("0"), "total_pnl": Decimal("-2")}]

    def bridge_from_synthetic_inputs(**_kwargs):
        rows = build_pnl_bridge_rows(
            pnl, current, prior,
            treasury_curve_current={"3Y": Decimal("4"), "5Y": Decimal("4")},
            treasury_curve_prior={"3Y": Decimal("3"), "5Y": Decimal("3")},
            aaa_credit_curve_current={"3Y": Decimal("4"), "5Y": Decimal("4")},
            aaa_credit_curve_prior={"3Y": Decimal("3"), "5Y": Decimal("3")},
        )
        return {
            "result": {"summary": pnl_bridge_service._build_summary(rows).model_dump(mode="json")},
            "result_meta": {"filters_applied": {
                "window_aligned": True,
                "balance_window": {"start": "2026-07-31", "end": "2026-08-31"},
            }},
        }

    monkeypatch.setattr(pnl_bridge_service, "pnl_bridge_envelope", bridge_from_synthetic_inputs)
    closure = campisi_svc._fetch_formal_closure(
        settings=SimpleNamespace(duckdb_path="unused", governance_path="unused"),
        report_date="2026-08-31", start_date="2026-07-31",
        campisi_total_return=Decimal("-2"),
    )
    if ambiguous:
        assert closure["status"] == "unavailable"
        assert closure["formal_actual_pnl"] is None
        assert closure["residual_to_formal_pnl"] is None
        assert "DUPLICATE_BALANCE_KEY" in closure["message"]
    else:
        assert closure["status"] == "closed"
        assert closure["formal_actual_pnl"] == -2.0
        assert closure["residual_to_formal_pnl"] == 0.0
