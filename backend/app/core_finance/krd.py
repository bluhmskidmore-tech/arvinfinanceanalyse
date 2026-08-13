"""
DORMANT: 无生产调用方（2026-08 复核：除 tests/ 外，仓库内仅同样休眠的
credit_spread.py 引用 classify_asset_class / map_accounting_class）。接线前必须：

1. 短端桶归并（``KRD_SHORT_END_BUCKET_MERGE``）已补，但**正式 KRD 口径以
   risk_tensor.py 为准**；本文件是迁移期备用实现，不得与 risk_tensor 并行出账。
2. 先消歧"KRD"三义再暴露给页面：本文件 ``krd`` = Σ weight × 修正久期（无量纲）；
   ``risk_tensor`` 的 krd_1y..krd_30y = 桶内 ΣDV01（元/bp）；
   ``bond_analytics/read_models`` 的 krd_buckets.avg_modified_duration
   = 桶内市值加权平均修正久期（年）。见 docs/calc_rules.md
   "Curve-risk bucket field naming"。
3. 补齐黄金测试：tests/test_krd_golden.py 三只券均 ≥2Y，短端另见
   tests/test_krd_short_end_buckets.py；接线新口径需同步扩这两个文件。

已知口径限制：
- 久期来自 bond_duration.py 的整期闭式近似，对碎期券与街市惯例（引擎口径）
  存在约 8% 量级差异，见 docs/calc_rules.md "Fractional-period duration
  dual caliber"。
- steepening / flattening 幅度与 bond_analytics/common.py 同名情景不同
  （本文件 1Y∓25bp / 30Y±25bp 驼峰形，该处为 30Y±50bp 线性），2026-07 经确认并存。

关键利率久期（KRD）与曲线情景（纯函数）。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.app.core_finance.config.classification_rules import infer_invest_type
from backend.app.core_finance.field_normalization import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    derive_accounting_basis_value,
)

from .attribution_core import get_tenor_bucket
from .bond_duration import (
    estimate_convexity_bond,
    estimate_duration,
    modified_duration_from_macaulay,
)
from .safe_decimal import safe_decimal

logger = logging.getLogger(__name__)

KRD_TENORS = ("1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y")

# 短端桶归并。``attribution_core.get_tenor_bucket`` 会产出 ON/7D/1M/3M/6M，而
# ``KRD_TENORS`` 自 1Y 起：不归并则短融/超短融/存单被静默丢弃，但权重分母仍含
# 全部持仓，导致 Σ KRD < 组合修正久期且无披露。
# 口径对齐 ``risk_tensor.KRD_BUCKET_FALLBACK``（生产路径）的"就近映射到受支持桶"
# 规则——其中 6M -> krd_1y 已是既有生产口径；其余 <1Y 桶按同一规则同归 1Y。
KRD_SHORT_END_BUCKET_MERGE: dict[str, str] = {
    "ON": "1Y",
    "7D": "1Y",
    "1M": "1Y",
    "3M": "1Y",
    "6M": "1Y",
}

STANDARD_KRD_SCENARIOS = (
    # 平行情景用 ``"all"`` 键（与 bond_analytics/common.py 的 STANDARD_SCENARIOS
    # 一致）：逐桶枚举 KRD_TENORS 会让 ON~6M 短端持仓冲击恒为 0，"平行"情景损益
    # 被系统性低估。
    {
        "name": "parallel_up_25bp",
        "description": "Parallel +25bp",
        "shocks": {"all": 25},
    },
    {
        "name": "parallel_up_50bp",
        "description": "Parallel +50bp",
        "shocks": {"all": 50},
    },
    {
        "name": "parallel_up_100bp",
        "description": "Parallel +100bp",
        "shocks": {"all": 100},
    },
    {
        "name": "parallel_down_25bp",
        "description": "Parallel -25bp",
        "shocks": {"all": -25},
    },
    # 口径说明（2026-07 经确认并存，勿擅自统一）：本文件 KRD 情景的陡峭化/平坦化
    # 幅度为 1Y∓25bp / 30Y±25bp（10Y 后回落的驼峰形），而 bond_analytics/common.py
    # 的 STANDARD_SCENARIOS 同名情景为 1Y∓25bp / 30Y±50bp 线性插值。两套服务于
    # 不同展示场景，数值差异属已知口径差异。
    {
        "name": "steepening_50bp",
        "description": "Curve steepening",
        "shocks": {
            "1Y": -25,
            "2Y": -15,
            "3Y": -5,
            "5Y": 5,
            "7Y": 15,
            "10Y": 25,
            "15Y": 20,
            "20Y": 23,
            "30Y": 25,
        },
    },
    {
        "name": "flattening_50bp",
        "description": "Curve flattening",
        "shocks": {
            "1Y": 25,
            "2Y": 15,
            "3Y": 5,
            "5Y": -5,
            "7Y": -15,
            "10Y": -25,
            "15Y": -20,
            "20Y": -23,
            "30Y": -25,
        },
    },
)

RATE_BOND_TYPES = {
    "国债",
    "国开债",
    "政金债",
    "地方债",
    "央票",
    "政府债",
    "政策性金融债",
    "地方政府债券",
    "地方政府债",
    "国家开发银行",
    "进出口银行",
    "农业发展银行",
}

CREDIT_BOND_TYPES = {
    "企业债",
    "公司债",
    "中票",
    "短融",
    "PPN",
    "ABS",
    "金融债",
    "同业存单",
    "NCD",
    "超短融",
    "短期融资券",
    "中期票据",
    "私募债",
    "定向工具",
}


def _get_value(record: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if isinstance(record, Mapping) and key in record:
            value = record[key]
        else:
            value = getattr(record, key, None)
        if value is not None:
            return value
    return default


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime().date()
        except (ValueError, TypeError, AttributeError):
            logger.exception("_coerce_date: to_pydatetime() failed for %r", type(value).__name__)
            return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except (ValueError, TypeError, AttributeError):
            logger.exception("_coerce_date: .date() failed for %r", type(value).__name__)
            return None
    return None


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        logger.exception("_optional_decimal: failed to convert %r", type(value).__name__)
        return None


def classify_asset_class(bond_type: str | None) -> str:
    if not bond_type:
        return "other"
    for rate_type in RATE_BOND_TYPES:
        if rate_type in bond_type:
            return "rate"
    for credit_type in CREDIT_BOND_TYPES:
        if credit_type in bond_type:
            return "credit"
    return "other"


def map_accounting_class(asset_class: str | None) -> str:
    """Map raw accounting label to KRD bucket (TPL / OCI / AC / other).

    W-krd-2026-04-21: H/A/T classification delegates to canonical
    ``classification_rules.infer_invest_type`` (caliber ``hat_mapping``),
    then maps ``derive_accounting_basis_value`` outputs to legacy KRD
    strings (``OCI`` for FVOCI, ``TPL`` for FVTPL).

    When the canonical matcher returns ``None``, the historical fallbacks
    for ``债权投资``, substring ``摊余``, and exact ``AC`` remain — these
    are not expressible solely via ``_match_invest_type_by_substring``.
    """
    if not asset_class:
        return "other"
    invest = infer_invest_type(None, None, asset_class)
    if invest is not None:
        basis = derive_accounting_basis_value(invest)  # type: ignore[arg-type]
        if basis == ACCOUNTING_BASIS_AC:
            return "AC"
        if basis == ACCOUNTING_BASIS_FVOCI:
            return "OCI"
        return "TPL"
    if (
        "债权投资" in asset_class
        or "摊余" in asset_class
        or str(asset_class).strip() == ACCOUNTING_BASIS_AC
    ):
        return "AC"
    return "other"


def _get_market_value(position: Any) -> Decimal:
    return safe_decimal(
        _get_value(
            position,
            "market_value",
            "market_value_end",
            "market_value_start",
            default=Decimal("0"),
        )
    )


def _get_face_value(position: Any, *, fallback_market_value: Decimal) -> Decimal:
    face_value = safe_decimal(
        _get_value(
            position,
            "face_value_cny",
            "face_value",
            "face_value_amount",
            "face_value_end",
            "face_value_start",
            "face_value_native",
            default=Decimal("0"),
        )
    )
    return face_value if face_value > Decimal("0") else fallback_market_value


def _get_coupon_frequency(position: Any) -> int:
    explicit = _get_value(position, "coupon_frequency")
    if explicit is not None:
        try:
            return max(int(explicit), 1)
        except (TypeError, ValueError):
            pass

    bond_code = str(_get_value(position, "bond_code", default="")).upper()
    asset_hint = " ".join(
        str(_get_value(position, key, default=""))
        for key in ("asset_class", "sub_type", "bond_type")
    )
    if "超短融" in asset_hint or bond_code.startswith("SCP") or bond_code.startswith("SA"):
        return 1
    return 2


def _get_tenor_from_position(
    position: Any,
    *,
    report_date: date | None = None,
    duration: Decimal | None = None,
) -> str:
    maturity_date = _coerce_date(_get_value(position, "maturity_date", "maturity_date_end"))
    effective_report_date = _coerce_date(
        _get_value(position, "report_date", "biz_date", "report_date_end", default=report_date)
    )
    if maturity_date is not None and effective_report_date is not None:
        years = max((maturity_date - effective_report_date).days / 365.0, 0.0)
        return get_tenor_bucket(years)
    # ``duration`` 为 Decimal("0") 时必须按真实的 0 处理：缺到期日的持仓经
    # ``common.resolve_missing_maturity_duration`` 返回 DURATION_UNAVAILABLE(0)，
    # 而 ``or`` 会把它当成"没有值"回退到 5 年，把这批持仓错分进 5Y 桶。
    # 只有"根本没传久期"（None）才走 5 年占位。
    return get_tenor_bucket(float(duration if duration is not None else Decimal("5")))


def build_krd_position_metrics(
    positions: Iterable[Any],
    *,
    report_date: date | None = None,
    wind_metrics: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    position_list = list(positions)
    total_market_value = sum(
        (_get_market_value(position) for position in position_list),
        Decimal("0"),
    )
    metrics: list[dict[str, Any]] = []

    for position in position_list:
        market_value = _get_market_value(position)
        if market_value <= Decimal("0"):
            continue
        face_value = _get_face_value(position, fallback_market_value=market_value)

        bond_code = str(_get_value(position, "bond_code", default=""))
        coupon_rate = safe_decimal(_get_value(position, "coupon_rate"))
        ytm = safe_decimal(_get_value(position, "yield_to_maturity"))
        coupon_frequency = _get_coupon_frequency(position)
        report_for_position = _coerce_date(
            _get_value(position, "report_date", "biz_date", "report_date_end", default=report_date)
        )
        maturity_date = _coerce_date(_get_value(position, "maturity_date", "maturity_date_end"))
        wind_bond = dict((wind_metrics or {}).get(bond_code, {}))
        duration = estimate_duration(
            maturity_date=maturity_date,
            report_date=report_for_position or report_date or date.today(),
            coupon_rate=coupon_rate,
            bond_code=bond_code,
            ytm=ytm,
            wind_metrics={bond_code: wind_bond} if wind_bond else None,
            coupon_frequency=coupon_frequency,
        )
        wind_mod_duration = _optional_decimal(wind_bond.get("mod_duration"))
        modified_duration = (
            wind_mod_duration
            if wind_mod_duration is not None
            else modified_duration_from_macaulay(
                duration=duration,
                ytm=ytm,
                coupon_frequency=max(coupon_frequency, 1),
                wind_mod_dur=None,
            )
        )
        wind_convexity = _optional_decimal(wind_bond.get("convexity"))
        convexity = (
            wind_convexity
            if wind_convexity is not None
            else estimate_convexity_bond(
                duration=duration,
                ytm=ytm,
                wind_convexity=None,
                coupon_frequency=max(coupon_frequency, 1),
            )
        )
        weight = market_value / total_market_value if total_market_value > 0 else Decimal("0")
        metrics.append(
            {
                "bond_code": bond_code,
                "market_value": market_value,
                "face_value": face_value,
                "duration": duration,
                "modified_duration": modified_duration,
                "convexity": convexity,
                "dv01": face_value * modified_duration / Decimal("10000"),
                "weight": weight,
                "tenor_bucket": _get_tenor_from_position(
                    position,
                    report_date=report_date,
                    duration=duration,
                ),
                "asset_class": classify_asset_class(
                    str(_get_value(position, "sub_type", "bond_type", default=""))
                ),
                "accounting_class": map_accounting_class(
                    str(_get_value(position, "asset_class", default=""))
                ),
            }
        )
    return metrics


def _aggregate_krd_buckets(
    metrics: Iterable[Mapping[str, Any]],
    tenors: Iterable[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """按桶聚合 KRD，并返回归并/丢弃披露。

    短端桶按 ``KRD_SHORT_END_BUCKET_MERGE`` 归并；仍无法归并的桶才丢弃，
    丢弃必须 warning 并在披露中给出市值、行数与占组合市值的比重（该比重即
    Σ KRD 相对组合修正久期的缺口上界）。
    """
    metric_list = list(metrics)
    tenor_map = {
        tenor: {
            "tenor": tenor,
            "krd": Decimal("0"),
            "dv01": Decimal("0"),
            "market_value_weight": Decimal("0"),
        }
        for tenor in tenors
    }
    total_market_value = sum(
        (safe_decimal(metric["market_value"]) for metric in metric_list),
        Decimal("0"),
    )

    merged_buckets: dict[str, str] = {}
    merged_market_value = Decimal("0")
    merged_position_count = 0
    dropped_buckets: set[str] = set()
    dropped_market_value = Decimal("0")
    dropped_position_count = 0

    for metric in metric_list:
        tenor_bucket = str(metric["tenor_bucket"])
        market_value = safe_decimal(metric["market_value"])
        if tenor_bucket in tenor_map:
            target = tenor_bucket
        else:
            target = KRD_SHORT_END_BUCKET_MERGE.get(tenor_bucket, "")
            if target not in tenor_map:
                dropped_buckets.add(tenor_bucket)
                dropped_market_value += market_value
                dropped_position_count += 1
                continue
            merged_buckets[tenor_bucket] = target
            merged_market_value += market_value
            merged_position_count += 1

        bucket = tenor_map[target]
        bucket["krd"] += metric["weight"] * safe_decimal(metric["modified_duration"])
        bucket["dv01"] += safe_decimal(metric["dv01"])
        bucket["market_value_weight"] += (
            market_value / total_market_value if total_market_value > 0 else Decimal("0")
        )

    warnings: list[str] = []
    if merged_buckets:
        detail = ", ".join(f"{src}->{dst}" for src, dst in sorted(merged_buckets.items()))
        warnings.append(f"Short-end tenor buckets merged into nearest KRD bucket: {detail}")
        logger.warning(
            "compute_krd_by_tenor: merged short-end buckets %s (market_value=%s, rows=%s)",
            detail,
            merged_market_value,
            merged_position_count,
        )
    if dropped_buckets:
        detail = ", ".join(sorted(dropped_buckets))
        warnings.append(f"Tenor buckets excluded from KRD: {detail}")
        logger.warning(
            "compute_krd_by_tenor: dropped buckets %s (market_value=%s, rows=%s); "
            "sum(KRD) understates portfolio modified duration",
            detail,
            dropped_market_value,
            dropped_position_count,
        )

    disclosure = {
        "total_market_value": total_market_value,
        "merged_buckets": dict(sorted(merged_buckets.items())),
        "merged_market_value": merged_market_value,
        "merged_position_count": merged_position_count,
        "dropped_buckets": sorted(dropped_buckets),
        "dropped_market_value": dropped_market_value,
        "dropped_position_count": dropped_position_count,
        "dropped_market_value_weight": (
            dropped_market_value / total_market_value
            if total_market_value > 0
            else Decimal("0")
        ),
        "warnings": warnings,
    }
    return list(tenor_map.values()), disclosure


def compute_krd_by_tenor(
    positions: Iterable[Any],
    *,
    report_date: date | None = None,
    wind_metrics: Mapping[str, Mapping[str, Any]] | None = None,
    tenors: Iterable[str] = KRD_TENORS,
) -> list[dict[str, Any]]:
    """按期限桶汇总 KRD。归并/丢弃披露见 ``compute_krd_curve_risk`` 的
    ``krd_bucket_disclosure``（本函数只保留桶行，另经 logger 告警）。"""
    metrics = build_krd_position_metrics(
        positions,
        report_date=report_date,
        wind_metrics=wind_metrics,
    )
    buckets, _disclosure = _aggregate_krd_buckets(metrics, tenors)
    return buckets


def _resolve_scenario_shock(shocks: Mapping[str, Any], tenor_bucket: str) -> Decimal:
    """解析某个期限桶的冲击（bp）。

    - ``"all"`` 键表示平行情景，对所有桶（含 ON~6M 短端）生效并优先于逐桶键，
      与 ``bond_analytics/common.py`` 的 STANDARD_SCENARIOS 语义一致。
    - 逐桶情景（陡峭化/平坦化）对短端按 ``KRD_SHORT_END_BUCKET_MERGE`` 回落到
      归并桶，避免短端持仓冲击被静默置零。
    """
    if "all" in shocks:
        return safe_decimal(shocks["all"])
    if tenor_bucket in shocks:
        return safe_decimal(shocks[tenor_bucket])
    merged = KRD_SHORT_END_BUCKET_MERGE.get(tenor_bucket)
    if merged is not None and merged in shocks:
        return safe_decimal(shocks[merged])
    return Decimal("0")


def compute_curve_scenario(
    position_metrics: Iterable[Mapping[str, Any]],
    scenario: Mapping[str, Any],
) -> dict[str, Any]:
    shocks = dict(scenario.get("shocks") or {})
    pnl_economic = Decimal("0")
    pnl_oci = Decimal("0")
    pnl_tpl = Decimal("0")
    rate_contribution = Decimal("0")
    convexity_contribution = Decimal("0")
    by_asset_class = {"rate": Decimal("0"), "credit": Decimal("0"), "other": Decimal("0")}

    for metric in position_metrics:
        shock_bp = _resolve_scenario_shock(shocks, str(metric["tenor_bucket"]))
        shock_decimal = shock_bp / Decimal("10000")
        market_value = safe_decimal(metric["market_value"])
        modified_duration = safe_decimal(metric["modified_duration"])
        convexity = safe_decimal(metric["convexity"])
        rate_effect = -modified_duration * market_value * shock_decimal
        convexity_effect = (
            Decimal("0.5") * convexity * market_value * shock_decimal * shock_decimal
        )
        delta_pnl = rate_effect + convexity_effect

        pnl_economic += delta_pnl
        rate_contribution += rate_effect
        convexity_contribution += convexity_effect

        accounting_class = str(metric["accounting_class"])
        if accounting_class == "OCI":
            pnl_oci += delta_pnl
        elif accounting_class == "TPL":
            pnl_tpl += delta_pnl

        asset_class = str(metric["asset_class"])
        by_asset_class[asset_class if asset_class in by_asset_class else "other"] += delta_pnl

    return {
        "scenario_name": str(scenario.get("name") or "custom"),
        "scenario_description": str(scenario.get("description") or ""),
        "shocks": {key: int(safe_decimal(value)) for key, value in shocks.items()},
        "pnl_economic": pnl_economic,
        "pnl_oci": pnl_oci,
        "pnl_tpl": pnl_tpl,
        "rate_contribution": rate_contribution,
        "convexity_contribution": convexity_contribution,
        "by_asset_class": by_asset_class,
    }


def aggregate_krd_by_asset_class(
    position_metrics: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    metrics = list(position_metrics)
    total_market_value = sum(
        (safe_decimal(metric["market_value"]) for metric in metrics),
        Decimal("0"),
    )
    groups: dict[str, dict[str, Any]] = {}

    for metric in metrics:
        asset_class = str(metric["asset_class"])
        group = groups.setdefault(
            asset_class,
            {
                "asset_class": asset_class,
                "market_value": Decimal("0"),
                "weighted_duration": Decimal("0"),
                "dv01": Decimal("0"),
            },
        )
        market_value = safe_decimal(metric["market_value"])
        group["market_value"] += market_value
        group["weighted_duration"] += market_value * safe_decimal(metric["duration"])
        group["dv01"] += safe_decimal(metric["dv01"])

    results: list[dict[str, Any]] = []
    for asset_class, payload in groups.items():
        market_value = payload["market_value"]
        results.append(
            {
                "asset_class": asset_class,
                "market_value": market_value,
                "duration": (
                    payload["weighted_duration"] / market_value
                    if market_value > 0
                    else Decimal("0")
                ),
                "dv01": payload["dv01"],
                "weight": (
                    market_value / total_market_value if total_market_value > 0 else Decimal("0")
                ),
            }
        )
    return results


def compute_krd_curve_risk(
    positions: Iterable[Any],
    *,
    report_date: date | None = None,
    scenarios: Iterable[Mapping[str, Any]] | None = None,
    wind_metrics: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    metrics = build_krd_position_metrics(
        positions,
        report_date=report_date,
        wind_metrics=wind_metrics,
    )
    total_market_value = sum(
        (metric["market_value"] for metric in metrics),
        Decimal("0"),
    )

    portfolio_duration = Decimal("0")
    portfolio_modified_duration = Decimal("0")
    portfolio_dv01 = Decimal("0")
    portfolio_convexity = Decimal("0")

    for metric in metrics:
        weight = safe_decimal(metric["weight"])
        portfolio_duration += weight * safe_decimal(metric["duration"])
        portfolio_modified_duration += weight * safe_decimal(metric["modified_duration"])
        portfolio_dv01 += safe_decimal(metric["dv01"])
        portfolio_convexity += weight * safe_decimal(metric["convexity"])

    scenario_inputs = list(scenarios) if scenarios is not None else list(STANDARD_KRD_SCENARIOS)
    krd_buckets, krd_bucket_disclosure = _aggregate_krd_buckets(metrics, KRD_TENORS)
    return {
        "position_metrics": metrics,
        "total_market_value": total_market_value,
        "portfolio_duration": portfolio_duration,
        "portfolio_modified_duration": portfolio_modified_duration,
        "portfolio_dv01": portfolio_dv01,
        "portfolio_convexity": portfolio_convexity,
        "krd_buckets": krd_buckets,
        "krd_bucket_disclosure": krd_bucket_disclosure,
        "scenarios": [compute_curve_scenario(metrics, scenario) for scenario in scenario_inputs],
        "by_asset_class": aggregate_krd_by_asset_class(metrics),
    }
