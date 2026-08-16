# 2026-07-19 审计 共享 M-5：safe_decimal / to_decimal 系列对 Decimal("NaN") /
# Decimal("Infinity")（以及 "nan"/"inf" 字符串构造产物）必须按各自缺省语义设防，
# 不得让 NaN 静默传播进下游算术。各实现缺省语义不同（0 / None / raise），不强行统一。
from __future__ import annotations

from decimal import Decimal

import pytest

from tests.helpers import load_module

NAN = Decimal("NaN")
INF = Decimal("Infinity")
NEG_INF = Decimal("-Infinity")


def test_core_safe_decimal_returns_default_for_non_finite():
    mod = load_module(
        "backend.app.core_finance.safe_decimal",
        "backend/app/core_finance/safe_decimal.py",
    )

    assert mod.safe_decimal(NAN) == Decimal("0")
    assert mod.safe_decimal(INF) == Decimal("0")
    assert mod.safe_decimal(NEG_INF) == Decimal("0")
    assert mod.safe_decimal(NAN, default=Decimal("1.5")) == Decimal("1.5")
    # 正常值与既有语义不受影响。
    assert mod.safe_decimal(Decimal("2.5")) == Decimal("2.5")
    assert mod.safe_decimal(None, default=Decimal("7")) == Decimal("7")


def test_bond_analytics_safe_decimal_returns_zero_for_non_finite():
    from backend.app.core_finance.bond_analytics.common import safe_decimal

    assert safe_decimal(NAN) == Decimal("0")
    assert safe_decimal(INF) == Decimal("0")
    # "nan" 字符串能被 Decimal 构造成功，同样不得放行。
    assert safe_decimal("nan") == Decimal("0")
    assert safe_decimal("inf") == Decimal("0")
    assert safe_decimal(Decimal("3.14")) == Decimal("3.14")
    assert safe_decimal("1.25") == Decimal("1.25")


def test_decimal_utils_to_decimal_coerces_non_finite_to_zero():
    from backend.app.core_finance.decimal_utils import to_decimal

    assert to_decimal(NAN) == Decimal("0")
    assert to_decimal(INF) == Decimal("0")
    assert to_decimal("nan") == Decimal("0")
    assert to_decimal(Decimal("9.99")) == Decimal("9.99")


def test_decimal_utils_to_decimal_strict_raises_for_non_finite():
    from backend.app.core_finance.decimal_utils import to_decimal_strict

    with pytest.raises(ValueError):
        to_decimal_strict(NAN)
    with pytest.raises(ValueError):
        to_decimal_strict(INF)
    with pytest.raises(ValueError):
        to_decimal_strict("nan")
    assert to_decimal_strict(Decimal("1.23")) == Decimal("1.23")
    assert to_decimal_strict("4.56") == Decimal("4.56")


def test_risk_tensor_safe_decimal_returns_zero_for_non_finite():
    from backend.app.core_finance.risk_tensor import _safe_decimal

    assert _safe_decimal(NAN) == Decimal("0")
    assert _safe_decimal(INF) == Decimal("0")
    assert _safe_decimal("nan") == Decimal("0")
    assert _safe_decimal(Decimal("100.5")) == Decimal("100.5")


def test_qdb_gl_to_decimal_treats_non_finite_as_missing():
    # qdb_gl 的缺省语义是 None（缺失），与其他实现的 0 缺省不同，保持不变。
    from backend.app.core_finance.qdb_gl_monthly_analysis import _as_decimal, _to_decimal

    assert _to_decimal(float("nan")) is None
    assert _to_decimal("nan") is None
    assert _to_decimal(NAN) is None
    assert _as_decimal(NAN) is None
    assert _to_decimal("1.5") == Decimal("1.5")
    assert _as_decimal(Decimal("2.5")) == Decimal("2.5")
