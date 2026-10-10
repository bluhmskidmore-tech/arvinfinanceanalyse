"""Unit tests for backend.app.schemas.common_numeric.Numeric."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.app.schemas.common_numeric import (
    Numeric,
    NumericUnit,
    null_numeric,
    numeric_from_raw,
)


class TestNumericBasicConstruction:
    @pytest.mark.parametrize(
        ("raw", "expected_raw_text"),
        [
            (Decimal("0E-8"), "0.00000000"),
            (Decimal("-0E-8"), "-0.00000000"),
            (Decimal("1E+3"), "1000"),
            (Decimal("1E-8"), "0.00000001"),
            (Decimal("1.2300"), "1.2300"),
        ],
    )
    def test_decimal_raw_text_uses_plain_decimal_notation(
        self,
        raw: Decimal,
        expected_raw_text: str,
    ) -> None:
        numeric = Numeric(
            raw=raw,
            unit="yuan",
            display="unchanged display",
            precision=4,
            sign_aware=False,
        )

        assert numeric.raw == float(raw)
        assert numeric.raw_text == expected_raw_text
        assert numeric.display == "unchanged display"
        assert numeric.unit == "yuan"
        assert numeric.precision == 4
        assert numeric.sign_aware is False

    def test_decimal_raw_text_is_preserved_without_float_roundtrip(self) -> None:
        raw = Decimal("12345678901234567890.12345678")

        numeric = Numeric(
            raw=raw,
            unit="yuan",
            display="12345678901234567890.12345678",
            precision=8,
            sign_aware=False,
        )

        assert numeric.raw_text == str(raw)
        assert numeric.model_dump(mode="json")["raw_text"] == str(raw)

    def test_explicit_raw_text_is_not_overwritten(self) -> None:
        numeric = Numeric(
            raw=Decimal("1E+3"),
            raw_text="1000.000",
            unit="yuan",
            display="1,000.000",
            precision=3,
            sign_aware=False,
        )

        assert numeric.raw_text == "1000.000"

    @pytest.mark.parametrize(
        "raw", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")]
    )
    def test_non_finite_decimal_constructor_is_rejected(self, raw: Decimal) -> None:
        with pytest.raises(ValidationError):
            Numeric(
                raw=raw,
                unit="yuan",
                display="invalid",
                precision=2,
                sign_aware=False,
            )

    def test_positive_yuan_value(self) -> None:
        n = Numeric(
            raw=12_345_678_900.0,
            unit="yuan",
            display="+123.46 亿",
            precision=2,
            sign_aware=True,
        )
        assert n.raw == 12_345_678_900.0
        assert n.raw_text is None
        assert "raw_text" not in n.model_dump(mode="json")
        assert n.unit == "yuan"
        assert n.display == "+123.46 亿"
        assert n.precision == 2
        assert n.sign_aware is True

    def test_negative_yuan_value_preserves_sign(self) -> None:
        n = Numeric(
            raw=-5_000_000_000.0,
            unit="yuan",
            display="-50.00 亿",
            precision=2,
            sign_aware=True,
        )
        assert n.raw < 0
        assert n.display.startswith("-")

    def test_null_raw_allowed(self) -> None:
        n = Numeric(
            raw=None,
            unit="yuan",
            display="—",
            precision=2,
            sign_aware=True,
        )
        assert n.raw is None
        assert n.display == "—"

    def test_pct_unit(self) -> None:
        n = Numeric(
            raw=0.0255,
            unit="pct",
            display="+2.55%",
            precision=2,
            sign_aware=True,
        )
        assert n.unit == "pct"

    def test_bp_unit(self) -> None:
        n = Numeric(
            raw=-12.5,
            unit="bp",
            display="-12.5 bp",
            precision=1,
            sign_aware=True,
        )
        assert n.unit == "bp"

    def test_ratio_unit(self) -> None:
        n = Numeric(
            raw=0.42,
            unit="ratio",
            display="0.42",
            precision=2,
            sign_aware=False,
        )
        assert n.sign_aware is False

    def test_count_unit(self) -> None:
        n = Numeric(
            raw=1234.0,
            unit="count",
            display="1,234",
            precision=0,
            sign_aware=False,
        )
        assert n.unit == "count"

    def test_dv01_unit(self) -> None:
        n = Numeric(
            raw=1500000.0,
            unit="dv01",
            display="1,500,000",
            precision=0,
            sign_aware=False,
        )
        assert n.unit == "dv01"

    def test_yi_unit(self) -> None:
        n = Numeric(
            raw=123.45,
            unit="yi",
            display="+123.45 亿",
            precision=2,
            sign_aware=True,
        )
        assert n.unit == "yi"


class TestNumericValidation:
    def test_reject_unknown_unit(self) -> None:
        with pytest.raises(ValidationError):
            Numeric(
                raw=1.0,
                unit="bogus_unit",  # type: ignore[arg-type]
                display="1",
                precision=0,
                sign_aware=False,
            )

    def test_reject_negative_precision(self) -> None:
        with pytest.raises(ValidationError):
            Numeric(
                raw=1.0,
                unit="yuan",
                display="1",
                precision=-1,
                sign_aware=False,
            )

    def test_reject_missing_display(self) -> None:
        with pytest.raises(ValidationError):
            Numeric(  # type: ignore[call-arg]
                raw=1.0,
                unit="yuan",
                precision=0,
                sign_aware=False,
            )


class TestNullNumericFactory:
    def test_null_numeric_default_display_dash(self) -> None:
        n = null_numeric(unit="yuan")
        assert n.raw is None
        assert n.display == "—"
        assert n.unit == "yuan"
        assert n.precision == 2
        assert n.sign_aware is True

    def test_null_numeric_custom_display(self) -> None:
        n = null_numeric(unit="pct", display="N/A", precision=1, sign_aware=False)
        assert n.raw is None
        assert n.display == "N/A"
        assert n.precision == 1
        assert n.sign_aware is False


class TestNumericFromRawFactory:
    @pytest.mark.parametrize(
        ("raw", "expected_raw", "expected_raw_text", "expected_display"),
        [
            (Decimal("0E-8"), 0.0, "0.00000000", "0.0000"),
            (Decimal("-0E-8"), -0.0, "-0.00000000", "-0.0000"),
            (Decimal("1E+3"), 1000.0, "1000", "1,000.0000"),
            (Decimal("1E-8"), 0.00000001, "0.00000001", "0.0000"),
            (Decimal("1.2300"), 1.23, "1.2300", "1.2300"),
        ],
    )
    def test_numeric_from_decimal_uses_plain_decimal_raw_text(
        self,
        raw: Decimal,
        expected_raw: float,
        expected_raw_text: str,
        expected_display: str,
    ) -> None:
        numeric = numeric_from_raw(raw=raw, unit="ratio", precision=4, sign_aware=False)

        assert numeric.raw == expected_raw
        assert numeric.raw_text == expected_raw_text
        assert numeric.display == expected_display
        assert numeric.unit == "ratio"
        assert numeric.precision == 4
        assert numeric.sign_aware is False

    def test_numeric_from_decimal_preserves_raw_text(self) -> None:
        raw = Decimal("12345678901234567890.12345678")

        numeric = numeric_from_raw(raw=raw, unit="yuan", precision=8, sign_aware=False)

        assert numeric.raw_text == str(raw)
        assert numeric.model_dump(mode="json")["raw_text"] == str(raw)

    def test_numeric_from_raw_yuan_positive(self) -> None:
        n = numeric_from_raw(raw=12_345_678_900.0, unit="yuan")
        assert n.raw == 12_345_678_900.0
        assert n.unit == "yuan"
        assert n.sign_aware is True
        assert n.display != "—"

    def test_numeric_from_raw_none_returns_null_display(self) -> None:
        n = numeric_from_raw(raw=None, unit="yuan")
        assert n.raw is None
        assert n.display == "—"

    def test_numeric_from_raw_respects_sign_aware_false(self) -> None:
        n = numeric_from_raw(raw=-1.5, unit="ratio", sign_aware=False)
        assert n.sign_aware is False


class TestNumericJsonRoundtrip:
    def test_dump_and_load(self) -> None:
        original = Numeric(
            raw=42.0,
            unit="pct",
            display="+4.20%",
            precision=2,
            sign_aware=True,
        )
        dumped = original.model_dump(mode="json")
        restored = Numeric.model_validate(dumped)
        assert restored == original

    def test_null_roundtrip(self) -> None:
        original = null_numeric(unit="bp")
        dumped = original.model_dump(mode="json")
        restored = Numeric.model_validate(dumped)
        assert restored.raw is None
        assert restored.display == "—"


class TestNumericUnitTypeAlias:
    def test_numeric_unit_covers_all_expected_values(self) -> None:
        expected = {"yuan", "pct", "bp", "ratio", "years", "count", "dv01", "yi"}
        # NumericUnit is a Literal; use typing.get_args to enumerate
        from typing import get_args

        assert set(get_args(NumericUnit)) == expected
