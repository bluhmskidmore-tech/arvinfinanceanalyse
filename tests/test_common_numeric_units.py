from __future__ import annotations

import pytest

from backend.app.schemas.common_numeric import numeric_from_raw


def test_numeric_from_raw_pct_ratio_formats_as_percent() -> None:
    numeric = numeric_from_raw(raw=0.0255, unit="pct")
    assert numeric.raw == pytest.approx(0.0255)
    assert numeric.display == "+2.55%"


def test_numeric_from_raw_pct_percent_scale_normalizes_raw() -> None:
    numeric = numeric_from_raw(raw=30.0, unit="pct", sign_aware=False)
    assert numeric.raw == pytest.approx(0.30)
    assert numeric.display == "30.00%"


def test_numeric_from_raw_bp_appends_suffix() -> None:
    numeric = numeric_from_raw(raw=-12.5, unit="bp", precision=1)
    assert numeric.raw == pytest.approx(-12.5)
    assert numeric.display == "-12.5 bp"


def test_numeric_from_raw_dv01_respects_precision() -> None:
    numeric = numeric_from_raw(raw=0.20904876, unit="dv01", precision=2, sign_aware=False)
    assert numeric.raw == pytest.approx(0.20904876)
    assert numeric.display == "0.21"
