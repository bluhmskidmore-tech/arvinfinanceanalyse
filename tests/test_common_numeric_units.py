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


def test_numeric_from_raw_pct_full_ratio_stays_full_percent() -> None:
    numeric = numeric_from_raw(raw=1.0, unit="pct", sign_aware=False)
    assert numeric.raw == pytest.approx(1.0)
    assert numeric.display == "100.00%"


def test_numeric_from_raw_pct_percent_scale_declared_above_one() -> None:
    numeric = numeric_from_raw(raw=2.55, unit="pct", raw_scale="percent")
    assert numeric.raw == pytest.approx(0.0255)
    assert numeric.display == "+2.55%"


def test_numeric_from_raw_pct_percent_scale_declared_sub_one_percent() -> None:
    # 0.85 declared as percent-points means 0.85%, not 85%.
    numeric = numeric_from_raw(raw=0.85, unit="pct", raw_scale="percent")
    assert numeric.raw == pytest.approx(0.0085)
    assert numeric.display == "+0.85%"


def test_numeric_from_raw_pct_percent_scale_zero_and_none() -> None:
    zero = numeric_from_raw(raw=0.0, unit="pct", raw_scale="percent")
    assert zero.raw == pytest.approx(0.0)
    assert zero.display == "+0.00%"
    missing = numeric_from_raw(raw=None, unit="pct", raw_scale="percent")
    assert missing.raw is None
    assert missing.display == "—"


def test_numeric_from_raw_pct_ratio_scale_never_rescales() -> None:
    numeric = numeric_from_raw(raw=1.5, unit="pct", raw_scale="ratio", sign_aware=False)
    assert numeric.raw == pytest.approx(1.5)
    assert numeric.display == "150.00%"


def test_numeric_from_raw_pct_auto_default_keeps_legacy_heuristic() -> None:
    above = numeric_from_raw(raw=30.0, unit="pct", sign_aware=False)
    assert above.raw == pytest.approx(0.30)
    below = numeric_from_raw(raw=0.85, unit="pct", sign_aware=False)
    assert below.raw == pytest.approx(0.85)


def test_numeric_from_raw_bp_appends_suffix() -> None:
    numeric = numeric_from_raw(raw=-12.5, unit="bp", precision=1)
    assert numeric.raw == pytest.approx(-12.5)
    assert numeric.display == "-12.5 bp"


def test_numeric_from_raw_dv01_respects_precision() -> None:
    numeric = numeric_from_raw(raw=0.20904876, unit="dv01", precision=2, sign_aware=False)
    assert numeric.raw == pytest.approx(0.20904876)
    assert numeric.display == "0.21"
