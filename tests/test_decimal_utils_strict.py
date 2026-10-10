# 回归：decimal_utils.to_decimal_strict 严格性；to_decimal(None) 仍为宽松 0。
from __future__ import annotations

import logging
import re
from decimal import Decimal

import pytest

from backend.app.core_finance.decimal_utils import to_decimal, to_decimal_strict

LOGGER_NAME = "backend.app.core_finance.decimal_utils"


def _call_to_decimal(value: object) -> Decimal:
    return to_decimal(value)


def test_to_decimal_strict_rejects_none() -> None:
    with pytest.raises(TypeError):
        to_decimal_strict(None)


def test_to_decimal_strict_rejects_nan_inf() -> None:
    with pytest.raises(ValueError):
        to_decimal_strict(float("nan"))
    with pytest.raises(ValueError):
        to_decimal_strict(float("inf"))


def test_to_decimal_strict_accepts_values() -> None:
    assert to_decimal_strict(Decimal("123.45")) == Decimal("123.45")
    assert to_decimal_strict(0) == Decimal("0")
    assert to_decimal_strict("123.45") == Decimal("123.45")


def test_to_decimal_lenient_none_still_zero() -> None:
    assert to_decimal(None) == Decimal("0")


@pytest.mark.parametrize(
    ("value", "reason", "bucket", "type_name"),
    [
        (None, "missing", "missing", "NoneType"),
        (float("nan"), "non_finite", "nan", "float"),
        (float("inf"), "non_finite", "inf", "float"),
        ("not-a-number", "invalid", "invalid", "str"),
    ],
)
def test_to_decimal_lenient_zero_fallback_logs_warning(
    caplog: pytest.LogCaptureFixture,
    value: object,
    reason: str,
    bucket: str,
    type_name: str,
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        assert _call_to_decimal(value) == Decimal("0")

    messages = [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME]
    assert len(messages) == 1
    message = messages[0]
    assert "to_decimal coerced" in message
    assert type_name in message
    assert f"reason={reason}" in message
    assert f"bucket={bucket}" in message
    assert "caller=unknown" not in message
    assert re.search(r"caller=.*\.py:\d+:", message)
    assert "first_occurrence=true" in message
    assert "not-a-number" not in message


def test_to_decimal_lenient_zero_fallback_warns_once_per_caller(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        for _ in range(2):
            assert to_decimal(None) == Decimal("0")

    messages = [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME]
    assert len(messages) == 1
    assert "reason=missing" in messages[0]


def test_to_decimal_lenient_valid_values_do_not_log_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        assert to_decimal("123.45") == Decimal("123.45")

    assert [record for record in caplog.records if record.name == LOGGER_NAME] == []
