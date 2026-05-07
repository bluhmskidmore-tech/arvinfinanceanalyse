"""
Yield curve engine — unified interpolation, curve construction, and bootstrapping.

Public API:
    - ``interpolate``: main interpolation entry (cubic spline / linear)
    - ``curve_from_tenor_map``: build a FittedCurve from tenor→rate dict
    - ``build_cubic_spline``: construct spline from CurvePoints
    - ``bootstrap_zero_curve``: strip zero-coupon curve from par yields
    - ``direct_spot_result``: wrap vendor spot rates into BootstrapResult
    - ``cross_validate_spot_curve``: compare bootstrapped vs vendor spot
    - ``CurvePoint``, ``FittedCurve``, ``InterpolationMethod``: data types
    - ``BootstrapResult``, ``CrossValidationResult``: bootstrap results
"""

from backend.app.core_finance.curve_engine.curve_types import (
    CurvePoint,
    FittedCurve,
    InterpolationMethod,
)
from backend.app.core_finance.curve_engine.interpolation import (
    build_cubic_spline,
    curve_from_tenor_map,
    interpolate,
)
from backend.app.core_finance.curve_engine.bootstrapper import (
    BootstrapResult,
    CrossValidationResult,
    bootstrap_zero_curve,
    cross_validate_spot_curve,
    direct_spot_result,
)

__all__ = [
    "BootstrapResult",
    "CrossValidationResult",
    "CurvePoint",
    "FittedCurve",
    "InterpolationMethod",
    "bootstrap_zero_curve",
    "build_cubic_spline",
    "cross_validate_spot_curve",
    "curve_from_tenor_map",
    "direct_spot_result",
    "interpolate",
]
