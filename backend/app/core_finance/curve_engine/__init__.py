"""
Yield curve engine — unified interpolation, curve construction, bootstrapping,
and parametric fitting.

Public API:
    Interpolation:
        - ``interpolate``: main entry (cubic spline / linear)
        - ``curve_from_tenor_map``: build FittedCurve from tenor→rate dict
        - ``build_cubic_spline``: construct spline from CurvePoints
    Bootstrapping:
        - ``bootstrap_zero_curve``: strip zero-coupon curve from par yields
        - ``direct_spot_result``: wrap vendor spot rates into BootstrapResult
        - ``cross_validate_spot_curve``: compare bootstrapped vs vendor spot
    Parametric fitting:
        - ``fit_nelson_siegel``: 4-parameter NS model
        - ``fit_svensson``: 6-parameter Svensson model
        - ``ns_interpolate``: evaluate fitted NS/Svensson model
    Data types:
        - ``CurvePoint``, ``FittedCurve``, ``InterpolationMethod``
        - ``BootstrapResult``, ``CrossValidationResult``
        - ``NSFitResult``, ``NSParams``, ``SvenssonParams``
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
from backend.app.core_finance.curve_engine.nelson_siegel import (
    NSFitResult,
    NSParams,
    SvenssonParams,
    fit_nelson_siegel,
    fit_svensson,
    ns_interpolate,
)

__all__ = [
    "BootstrapResult",
    "CrossValidationResult",
    "CurvePoint",
    "FittedCurve",
    "InterpolationMethod",
    "NSFitResult",
    "NSParams",
    "SvenssonParams",
    "bootstrap_zero_curve",
    "build_cubic_spline",
    "cross_validate_spot_curve",
    "curve_from_tenor_map",
    "direct_spot_result",
    "fit_nelson_siegel",
    "fit_svensson",
    "interpolate",
    "ns_interpolate",
]
