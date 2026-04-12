"""Contract tests for `backend.app.repositories.currency_codes.normalize_currency_code`."""

from __future__ import annotations

import pytest

from backend.app.repositories.currency_codes import normalize_currency_code


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        (None, ""),
        ("人民币", "CNY"),
        ("CNY", "CNY"),
        ("美元", "USD"),
        ("USD", "USD"),
        ("综本", "CNX"),
        ("CNX", "CNX"),
        ("usd", "USD"),
        ("EUR", "EUR"),
        ("欧元", "欧元"),
    ],
)
def test_normalize_currency_code_mapped_and_passthrough(value: object, expected: str) -> None:
    assert normalize_currency_code(value) == expected
