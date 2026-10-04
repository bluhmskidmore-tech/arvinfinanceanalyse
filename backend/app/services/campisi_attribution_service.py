"""
Campisi 完整归因桥接层 — 将 V3 的 DuckDB 数据转换为 campisi.py 纯函数所需的输入格式。

提供两个入口：
- campisi_four_effects_envelope: 四效应（income/treasury/spread/selection）
- campisi_enhanced_envelope: 六效应（+ convexity/cross/reinvestment）
- campisi_maturity_bucket_envelope: 按到期桶分解

数据来源：
- bond_rows: BondAnalyticsRepository.fetch_bond_analytics_rows（期初+期末）
- market: YieldCurveRepository.resolve_curve_snapshot（国债曲线）+ fetch_curve（信用利差）
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections import defaultdict
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Lock
from typing import Any

import duckdb

from backend.app.core_finance.accounting_basis_constants import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    ACCOUNTING_BASIS_FVTPL,
)
from backend.app.core_finance.bond_analytics.common import map_accounting_basis_to_risk_class, map_accounting_class
from backend.app.core_finance.bond_analytics.engine import (
    DURATION_QUALITY_OBSERVED,
    RATE_INPUT_STATUS_OBSERVED,
    _coerce_bool,
)
from backend.app.core_finance.campisi import (
    ACCRUED_INTEREST_MISSING_REASON,
    CampisiResult,
    accrued_interest_basis,
    aggregate_maturity_buckets,
    availability_diagnostics,
    campisi_attribution,
    campisi_enhanced,
    coverage_status,
    effect_availability_entry,
    infer_credit_rating_from_asset_class,
    treasury_tenor_coverage,
    usable_spread_bp,
)
from backend.app.core_finance.campisi import (
    maturity_bucket_attribution as maturity_bucket_attribution,
)
from backend.app.core_finance.campisi_decision_grade import (
    DirtyNumericInputError,
    compute_decision_grade_row,
    compute_decision_scope_disclosure,
    normalize_accounting_basis,
    primary_driver,
)
from backend.app.core_finance.campisi_decision_grade import (
    decimal_value as campisi_decision_decimal,
)
from backend.app.core_finance.pnl_bridge import (
    CREDIT_SPREAD_CURVE_SAME_SOURCE_PREFIX,
    CREDIT_SPREAD_CURVE_UNAVAILABLE_PREFIX,
    DUPLICATE_BALANCE_KEY_PREFIX,
    MARKET_VALUE_BASE_MISSING_PREFIX,
    ROLL_DOWN_TENOR_OUTSIDE_CURVE_PREFIX,
    ROLL_DOWN_WINDOW_MISSING_PREFIX,
    TREASURY_CURVE_SAME_SOURCE_PREFIX,
    TREASURY_CURVE_UNAVAILABLE_PREFIX,
)
from backend.app.core_finance.rate_units import (
    NEGATIVE_YIELD_DIRTY_FLOOR,
    normalize_annual_rate_to_decimal,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.choice_macro_series_repo import ChoiceMacroSeriesRepository
from backend.app.repositories.duckdb_repo import read_only_connection
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.risk_tensor_repo import RiskTensorRepository
from backend.app.repositories.system_read_publication_repo import raise_if_system_read_failure
from backend.app.repositories.yield_curve_repo import YieldCurveRepository
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_formal_result_envelope,
    build_formal_result_meta,
)
from backend.app.services.runtime_cache import InMemoryTTLCache, get_runtime_cache

logger = logging.getLogger(__name__)

RULE_VERSION = "rv_campisi_full_v11"
CACHE_VERSION = "cv_campisi_full_v11"
SOURCE_VERSION = "sv_campisi_formal_fi_v1"
DECISION_RULE_VERSION = "rv_campisi_decision_scope_fields_v2"
DECISION_CACHE_VERSION = "cv_campisi_decision_scope_fields_v2"
SOURCE_EMPTY = "sv_campisi_empty_v1"
TABLES_CAMPISI = [
    "fact_formal_pnl_fi",
    "fact_formal_zqtz_balance_daily",
    "fact_formal_bond_analytics_daily",
    "yield_curve_daily",
    "fact_formal_yield_curve_daily",
    "fact_choice_macro_daily",
    "choice_market_snapshot",
]
TABLES_CAMPISI_DECISION_GRADE = [
    "fact_formal_pnl_fi",
    "fact_formal_zqtz_balance_daily",
    "fact_formal_bond_analytics_daily",
    "fact_formal_yield_curve_daily",
    "fact_formal_risk_tensor_daily",
]
FORMAL_REPORT_BASIS = "formal_report_pnl_bridge"
FORMAL_BRIDGE_DECOMPOSITION_BASIS = (
    "bridge_path: selection_effect is residual after carry, treasury, spread, "
    "realized_trading, manual_adjustment, and fx_translation; "
    "convexity_effect / cross_effect / reinvestment_effect are not decomposed on this "
    "path and are published as an exact 0 with their contribution folded into "
    "selection_effect — not an observation that second-order terms were nil; "
    "model_path: selection_effect is per-bond curve decomposition residual"
)
_FORMAL_BRIDGE_DETAIL_KEYS = ("realized_trading", "manual_adjustment", "fx_translation")
# bridge 的一阶分解框架里根本没有二阶项这一步：convexity / cross / reinvestment
# 在该路径上是"没有被拆出来"，不是"拆出来等于零"。金额侧维持精确 0（贡献留在
# selection_effect 里，见 FORMAL_BRIDGE_DECOMPOSITION_BASIS），但必须带状态下发，
# 否则页面拿到的 0 与真实观测到的 0 无法区分——那正是静默降级。
EFFECT_STATUS_NOT_DECOMPOSED = "not_decomposed"
BRIDGE_SECOND_ORDER_NOT_DECOMPOSED_REASON = "bridge_second_order_not_decomposed"
_BRIDGE_SECOND_ORDER_EFFECT_KEYS = ("convexity_effect", "cross_effect", "reinvestment_effect")
BRIDGE_SECOND_ORDER_NOT_DECOMPOSED_DIAGNOSTIC = (
    "bridge_second_order_not_decomposed: convexity_effect / cross_effect / "
    "reinvestment_effect are not decomposed by the formal-bridge first-order "
    "framework; they are published as an exact 0 and their contribution stays "
    "folded into selection_effect — not an observation that second-order terms "
    "were nil."
)
_FORMAL_BRIDGE_ROW_CLOSURE_ABS_TOLERANCE = Decimal("0.000001")
_FORMAL_BRIDGE_ROW_CLOSURE_REL_TOLERANCE = Decimal("0.000000000001")
# 显式请求的 curve_window 超过该跨度时，仍按"远超月度期间"的口径错配升级为 warning。
_DECISION_WINDOW_MISMATCH_THRESHOLD_DAYS = 45
# 曲线陈旧守卫（owner 拍板值 7 天）：月末曲线观测常比自然月末提前 1-2 个交易日
# （如 08-29 代 08-31），7 天足以放过这类正常提前；而"跳月"错位至少偏离约一个月
# （≥28 天），必然被拦下。解析日偏离窗口端点超过阈值的曲线按缺失处理（相关效应
# 进入 residual_noise 并显式披露），不得静默采用。
_DECISION_CURVE_STALENESS_THRESHOLD_DAYS = 7
_MATURITY_BUCKET_LABELS = ("0-1Y", "1-3Y", "3-5Y", "5-7Y", "7-10Y", "10Y+")

_TREASURY_TENOR_MAP = {
    "1Y": "treasury_1y",
    "3Y": "treasury_3y",
    "5Y": "treasury_5y",
    "7Y": "treasury_7y",
    "10Y": "treasury_10y",
    "30Y": "treasury_30y",
}

_SPREAD_TENOR_MAP = {
    "credit_spread_aaa_3y": ("AAA", "3Y"),
    "credit_spread_aa_plus_3y": ("AA+", "3Y"),
    "credit_spread_aa_3y": ("AA", "3Y"),
}

_SPREAD_FIELD_BY_RATING = {
    "AAA": "credit_spread_aaa_3y",
    "AA+": "credit_spread_aa_plus_3y",
    "AA": "credit_spread_aa_3y",
}

_FORMAL_CREDIT_CURVE_TYPES = {
    "AAA": "aaa_credit",
    "AA+": "aa_plus_credit",
    "AA": "aa_credit",
}

_POSITION_KEY_FIELDS = (
    "instrument_code",
    "portfolio_name",
    "cost_center",
    "accounting_class",
    "currency_code",
)

_QUALITY_MISSING_FIELDS = (
    "ytm",
    # 缺票息在计算端按 0 代入，而 estimate_duration 对 coupon<=0 直接按零息债
    # 返回剩余年限；不在这里列出就等于该退化既不改数也不报数。
    "coupon_rate",
    "maturity_date",
    "rating",
    "portfolio_name",
    "cost_center",
)

_CAMPISI_FOUR_EFFECTS_CACHE_TTL_SECONDS = 300.0
_CAMPISI_FOUR_EFFECTS_CACHE_MAX_ENTRIES = 32
_CAMPISI_FOUR_EFFECTS_CACHE_LOCK = Lock()
_CAMPISI_FOUR_EFFECTS_CACHE: dict[tuple[object, ...], tuple[float, dict[str, Any]]] = {}
_CAMPISI_BRIDGE_CACHE_TTL_SECONDS = 300.0
_CAMPISI_BRIDGE_CACHE_MAX_ENTRIES = 16
_CAMPISI_BRIDGE_CACHE_LOCK = Lock()
_CAMPISI_BRIDGE_CACHE: dict[tuple[object, ...], tuple[float, dict[str, Any]]] = {}
_GOVERNANCE_BRIDGE_DEPENDENCY_FILES = (
    "cache_manifest.jsonl",
    "cache_build_run.jsonl",
)
_GOVERNANCE_FINGERPRINT_TAIL_BYTES = 8192

# WP-A2 top-level envelope cache: sits in front of the existing state / bridge
# caches so a hot request skips repository scans, position merging, market curve
# fetches and envelope rebuilding entirely. Only serves a cached envelope when
# both the DuckDB storage fingerprint and the governance bridge fingerprint are
# available; on hit we shallow-copy the envelope and refresh trace_id in place
# instead of deep-copying the large per-bond payload.
_CAMPISI_FOUR_EFFECTS_ENVELOPE_CACHE_TTL_SECONDS = 900.0
_CAMPISI_FOUR_EFFECTS_ENVELOPE_CACHE: InMemoryTTLCache[tuple[object, ...], dict[str, object]] = get_runtime_cache(
    "campisi.four_effects_envelope",
    ttl_seconds=_CAMPISI_FOUR_EFFECTS_ENVELOPE_CACHE_TTL_SECONDS,
)


def _trace_id() -> str:
    return f"tr_campisi_{uuid.uuid4().hex[:12]}"


def _duckdb_storage_fingerprint(duckdb_path: object) -> tuple[tuple[str, int, int], ...] | None:
    path = Path(str(duckdb_path))
    try:
        path.stat()
    except OSError:
        return None
    fingerprint: list[tuple[str, int, int]] = []
    for candidate in sorted(path.parent.glob(f"{path.name}*")):
        try:
            stat = candidate.stat()
        except OSError:
            continue
        if not candidate.is_file():
            continue
        fingerprint.append((candidate.name, stat.st_size, stat.st_mtime_ns))
    return tuple(fingerprint) or None


def _selected_files_fingerprint(
    base_dir: object,
    filenames: tuple[str, ...],
) -> tuple[tuple[str, int, int, str], ...] | None:
    base_path = Path(str(base_dir))
    fingerprint: list[tuple[str, int, int, str]] = []
    for filename in filenames:
        path = base_path / filename
        try:
            stat = path.stat()
        except OSError:
            return None
        if not path.is_file():
            return None
        try:
            with path.open("rb") as handle:
                if stat.st_size > _GOVERNANCE_FINGERPRINT_TAIL_BYTES:
                    handle.seek(-_GOVERNANCE_FINGERPRINT_TAIL_BYTES, 2)
                content = handle.read()
        except OSError:
            return None
        fingerprint.append((filename, stat.st_size, stat.st_mtime_ns, hashlib.sha256(content).hexdigest()))
    return tuple(fingerprint)


def _campisi_four_effects_cache_key(
    *,
    duckdb_path: object,
    duckdb_fingerprint: tuple[tuple[str, int, int], ...] | None,
    requested_start_date: str | None,
    requested_end_date: str | None,
    resolved_start_date: str,
    resolved_end_date: str,
    lookback_days: int,
) -> tuple[object, ...] | None:
    if duckdb_fingerprint is None:
        return None
    return (
        "campisi.four_effects",
        CACHE_VERSION,
        SOURCE_VERSION,
        RULE_VERSION,
        str(duckdb_path),
        duckdb_fingerprint,
        requested_start_date,
        requested_end_date,
        resolved_start_date,
        resolved_end_date,
        lookback_days,
    )


def _campisi_bridge_cache_key(
    *,
    duckdb_path: object,
    governance_path: object,
    duckdb_fingerprint: tuple[tuple[str, int, int], ...] | None,
    governance_fingerprint: tuple[tuple[str, int, int, str], ...] | None,
    report_date: str,
    start_date: str | None = None,
) -> tuple[object, ...] | None:
    if duckdb_fingerprint is None or governance_fingerprint is None:
        return None
    return (
        "campisi.formal_bridge",
        CACHE_VERSION,
        SOURCE_VERSION,
        RULE_VERSION,
        str(duckdb_path),
        duckdb_fingerprint,
        str(governance_path),
        governance_fingerprint,
        report_date,
        start_date,
    )


def _get_cached_campisi_four_effects_state(key: tuple[object, ...] | None) -> dict[str, Any] | None:
    if key is None:
        return None
    now = time.monotonic()
    with _CAMPISI_FOUR_EFFECTS_CACHE_LOCK:
        entry = _CAMPISI_FOUR_EFFECTS_CACHE.get(key)
        if entry is None:
            return None
        cached_at, state = entry
        if now - cached_at >= _CAMPISI_FOUR_EFFECTS_CACHE_TTL_SECONDS:
            _CAMPISI_FOUR_EFFECTS_CACHE.pop(key, None)
            return None
        return deepcopy(state)


def _get_cached_campisi_bridge(key: tuple[object, ...] | None) -> dict[str, Any] | None:
    if key is None:
        return None
    now = time.monotonic()
    with _CAMPISI_BRIDGE_CACHE_LOCK:
        entry = _CAMPISI_BRIDGE_CACHE.get(key)
        if entry is None:
            return None
        cached_at, bridge = entry
        if now - cached_at >= _CAMPISI_BRIDGE_CACHE_TTL_SECONDS:
            _CAMPISI_BRIDGE_CACHE.pop(key, None)
            return None
        return deepcopy(bridge)


def _set_cached_campisi_four_effects_state(
    key: tuple[object, ...] | None,
    state: dict[str, Any],
) -> None:
    if key is None:
        return
    with _CAMPISI_FOUR_EFFECTS_CACHE_LOCK:
        if len(_CAMPISI_FOUR_EFFECTS_CACHE) >= _CAMPISI_FOUR_EFFECTS_CACHE_MAX_ENTRIES:
            oldest_key = min(_CAMPISI_FOUR_EFFECTS_CACHE, key=lambda item: _CAMPISI_FOUR_EFFECTS_CACHE[item][0])
            _CAMPISI_FOUR_EFFECTS_CACHE.pop(oldest_key, None)
        _CAMPISI_FOUR_EFFECTS_CACHE[key] = (time.monotonic(), deepcopy(state))


def _set_cached_campisi_bridge(
    key: tuple[object, ...] | None,
    bridge: dict[str, Any],
) -> dict[str, Any]:
    if key is None:
        return bridge
    with _CAMPISI_BRIDGE_CACHE_LOCK:
        if len(_CAMPISI_BRIDGE_CACHE) >= _CAMPISI_BRIDGE_CACHE_MAX_ENTRIES:
            oldest_key = min(_CAMPISI_BRIDGE_CACHE, key=lambda item: _CAMPISI_BRIDGE_CACHE[item][0])
            _CAMPISI_BRIDGE_CACHE.pop(oldest_key, None)
        _CAMPISI_BRIDGE_CACHE[key] = (time.monotonic(), deepcopy(bridge))
    return deepcopy(bridge)


def clear_campisi_four_effects_runtime_cache() -> None:
    with _CAMPISI_FOUR_EFFECTS_CACHE_LOCK:
        _CAMPISI_FOUR_EFFECTS_CACHE.clear()
    with _CAMPISI_BRIDGE_CACHE_LOCK:
        _CAMPISI_BRIDGE_CACHE.clear()


def clear_campisi_four_effects_envelope_runtime_cache() -> None:
    _CAMPISI_FOUR_EFFECTS_ENVELOPE_CACHE.clear()


def _campisi_four_effects_envelope_cache_key(
    *,
    detail: str,
    duckdb_path: object,
    governance_path: object,
    duckdb_fingerprint: tuple[tuple[str, int, int], ...] | None,
    governance_fingerprint: tuple[tuple[str, int, int, str], ...] | None,
    requested_start_date: str | None,
    requested_end_date: str | None,
    lookback_days: int,
) -> tuple[object, ...] | None:
    if duckdb_fingerprint is None or governance_fingerprint is None:
        return None
    return (
        "campisi.four_effects_envelope",
        detail,
        CACHE_VERSION,
        SOURCE_VERSION,
        RULE_VERSION,
        str(duckdb_path),
        duckdb_fingerprint,
        str(governance_path),
        governance_fingerprint,
        requested_start_date,
        requested_end_date,
        int(lookback_days),
    )


def _campisi_envelope_with_fresh_trace(envelope: dict[str, object]) -> dict[str, object]:
    """Shallow-copy the envelope and refresh trace_id without deep-copying the payload.

    The cached envelope's `result` may carry hundreds of `by_bond` rows; deep-copying
    on every cache hit reintroduces the same GIL-bound cost this cache is meant to
    eliminate. Callers must not mutate the returned envelope's nested structures.
    """
    response = dict(envelope)
    meta = envelope.get("result_meta")
    if isinstance(meta, dict):
        response["result_meta"] = {**meta, "trace_id": _trace_id()}
    return response


def _meta_ok(
    result_kind: str,
    *,
    filters_applied: dict[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    as_of_date: str | None = None,
):
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=CACHE_VERSION,
        source_version=SOURCE_VERSION,
        rule_version=RULE_VERSION,
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        source_surface="formal_attribution",
        as_of_date=as_of_date,
    )


def _meta_warn(
    result_kind: str,
    *,
    source_version: str = SOURCE_EMPTY,
    filters_applied: dict[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    as_of_date: str | None = None,
):
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        source_version=source_version,
        rule_version=RULE_VERSION,
        cache_version=CACHE_VERSION,
        quality_flag="warning",
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        source_surface="formal_attribution",
        as_of_date=as_of_date,
    )


def curve_to_market_dict(curve: dict[str, Any]) -> dict[str, Any]:
    """将正式曲线的 {tenor: rate_pct} 转为 campisi.py 需要的百分数 market dict。"""
    market: dict[str, Any] = {}
    for tenor, field in _TREASURY_TENOR_MAP.items():
        val = curve.get(tenor) or curve.get(tenor.lower()) or curve.get(tenor.replace("Y", "y"))
        if val is not None:
            market[field] = float(val)
    return market


def _attach_native_principal_evidence(
    positions: list[dict[str, Any]],
    bond_repo: BondAnalyticsRepository,
    start_date: str,
    end_date: str,
    input_quality: dict[str, Any],
) -> None:
    """Use source quantities only for the model's holding-change guard.

    Analytics face and market values remain CNY amounts. Snapshot inputs are
    explanatory evidence and never replace the formal bridge's result.
    """
    foreign = [p for p in positions if _text_value(p.get("currency_code")).upper() not in {"", "CNY", "RMB", "156"}]
    if not foreign:
        return
    input_quality["principal_evidence"] = {
        "source": "zqtz_bond_daily_snapshot",
        "basis": "native_face_value",
        "period_start": start_date,
        "period_end": end_date,
        "model_only": True,
    }
    for endpoint, report_date in (("start", start_date), ("end", end_date)):
        native_by_key: dict[tuple[str, ...], list[object]] = defaultdict(list)
        for row in bond_repo.load_snapshot_rows(report_date):
            if _coerce_bool(row.get("is_issuance_like")):
                continue
            accounting = map_accounting_basis_to_risk_class(_text_value(row.get("accounting_basis")))
            if accounting is None:
                accounting = map_accounting_class(_text_value(row.get("account_category")) or _text_value(row.get("asset_class")))
            key = _position_key({**row, "accounting_class": accounting})
            if key is not None:
                native_by_key[key].append(row.get("face_value_native"))
        for position in foreign:
            key = (
                _text_value(position.get("bond_code")),
                _text_value(position.get("portfolio_name")),
                _text_value(position.get("cost_center")),
                map_accounting_basis_to_risk_class(_text_value(position.get("accounting_class")))
                or _text_value(position.get("accounting_class")),
                _text_value(position.get("currency_code")),
            )
            values = native_by_key.get(key, [])
            native = None
            try:
                parsed = [Decimal(str(value)) for value in values]
                if parsed and all(value.is_finite() for value in parsed):
                    native = sum(parsed, Decimal("0"))
            except (InvalidOperation, ValueError, TypeError):
                pass
            position[f"face_value_native_{endpoint}"] = native


# Private alias kept for backward compatibility with existing internal callers.
_curve_to_market_dict = curve_to_market_dict

# 国债曲线不可用的三种成因，必须被调用方与页面分开处理：
# - curve_absent：目标日没有可采用的正式曲线行；超期旧行另附解析日和弃用告警
# - curve_unusable：有行但 6 个关键期限没有一个可用（单位/符号/解析问题）
# - insufficient_shared_tenors：两端各自可用，但共同正期限 < 2，
#   于是 campisi._build_benchmark_change_evaluator 退化为恒 0 求值器
TREASURY_CURVE_ABSENT_REASON = "curve_absent"
TREASURY_CURVE_UNUSABLE_REASON = "curve_unusable"
TREASURY_CURVE_INSUFFICIENT_SHARED_TENORS_REASON = "insufficient_shared_tenors"
# formal-bridge 路径的效应来自 pnl_bridge 行，成因已由桥的行级诊断给出，
# 这里只标注"桥说这行的曲线效应不可用"。
BRIDGE_CURVE_UNAVAILABLE_REASON = "bridge_curve_unavailable"


def fetch_treasury_market_dict(
    curve_repo: YieldCurveRepository,
    trade_date: str,
) -> tuple[dict[str, Any], bool, str | None, bool]:
    """解析不晚于持仓日的正式快照；超出既有七天守卫的点位不得参与归因。

    返回 market、目标日是否有原始曲线行、实际曲线日、是否采用。保留超期曲线的
    实际日期供质量披露，但 market 为空，不能把该旧点位标成已使用的 fallback。
    """
    snapshot, _warning = curve_repo.resolve_curve_snapshot(trade_date, "treasury")
    resolved = str(snapshot.get("trade_date") or "") if snapshot else ""
    if not resolved:
        logger.warning(
            "No treasury yield curve rows on or before trade_date=%s; Campisi treasury_effect is "
            "unavailable for this period, not an observed zero.",
            trade_date,
        )
        return {}, False, None, False
    deviation_days = (date.fromisoformat(trade_date) - date.fromisoformat(resolved)).days
    if not 0 <= deviation_days <= _DECISION_CURVE_STALENESS_THRESHOLD_DAYS:
        logger.warning(
            "Treasury curve resolved to %s for trade_date=%s, deviation=%s days; "
            "discarded by the %s-day staleness guard.",
            resolved, trade_date, deviation_days, _DECISION_CURVE_STALENESS_THRESHOLD_DAYS,
        )
        return {}, False, resolved, False
    curve = snapshot.get("curve") if snapshot else None
    if not isinstance(curve, dict):
        raise RuntimeError(f"Invalid formal treasury curve snapshot for trade_date={resolved}.")
    return _curve_to_market_dict(curve), resolved == trade_date, resolved, True


_fetch_treasury_market_dict = fetch_treasury_market_dict


def fetch_credit_spread_market(curve_repo: YieldCurveRepository, trade_date: str) -> dict[str, Any]:
    """Fetch AAA/AA+/AA 3Y credit spreads in bp for Campisi.

    Returns a dict with keys like ``credit_spread_aaa_3y``, ``credit_spread_aa_plus_3y``,
    ``credit_spread_aa_3y`` (values in BP). Safe to merge with a treasury curve dict.
    """
    spread = _fetch_legacy_spread_curve_data(curve_repo, trade_date)
    spread.update(_derive_spreads_from_yield_sources(curve_repo, trade_date))
    return spread


# Keep the private alias so internal callers don't break.
_fetch_spread_data = fetch_credit_spread_market


def _fetch_legacy_spread_curve_data(curve_repo: YieldCurveRepository, trade_date: str) -> dict[str, Any]:
    spread: dict[str, Any] = {}
    for curve_type in ("credit_spread_aaa", "credit_spread_aa_plus", "credit_spread_aa"):
        data = curve_repo.fetch_curve(trade_date, curve_type)
        if data:
            for tenor, rate in data.items():
                key = f"{curve_type}_{tenor.lower()}"
                spread[key] = float(rate)
    return spread


def _derive_spreads_from_yield_sources(curve_repo: YieldCurveRepository, trade_date: str) -> dict[str, Any]:
    treasury_3y = _curve_3y_on_or_before(curve_repo, trade_date, "treasury")
    if treasury_3y is None:
        return {}
    spread: dict[str, Any] = {}
    for rating, curve_type in _FORMAL_CREDIT_CURVE_TYPES.items():
        credit_3y = _curve_3y_on_or_before(curve_repo, trade_date, curve_type)
        if credit_3y is not None:
            spread[_SPREAD_FIELD_BY_RATING[rating]] = float((credit_3y - treasury_3y) * Decimal("100"))
    for rating, credit_3y in _choice_macro_repo(curve_repo.path).credit_3y_yields_on_or_before(trade_date).items():
        spread[_SPREAD_FIELD_BY_RATING[rating]] = float((credit_3y - treasury_3y) * Decimal("100"))
    return spread


def _curve_3y_on_or_before(
    curve_repo: YieldCurveRepository,
    trade_date: str,
    curve_type: str,
) -> Decimal | None:
    exact = curve_repo.fetch_curve(trade_date, curve_type)
    if exact.get("3Y") is not None:
        return Decimal(str(exact["3Y"]))
    latest = curve_repo.fetch_latest_trade_date_on_or_before(curve_type, trade_date)
    if latest is None or latest == trade_date:
        return None
    fallback = curve_repo.fetch_curve(latest, curve_type)
    value = fallback.get("3Y")
    return None if value is None else Decimal(str(value))


def _choice_macro_repo(duckdb_path: str) -> ChoiceMacroSeriesRepository:
    return ChoiceMacroSeriesRepository(duckdb_path)


def _position_key(row: dict[str, Any]) -> tuple[str, ...] | None:
    key = tuple(_text_value(row.get(field)) for field in _POSITION_KEY_FIELDS)
    if not key[0]:
        return None
    return key


def _aggregate_position_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, ...], dict[str, Any]]:
    grouped_rows: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _position_key(row)
        if key is not None:
            grouped_rows[key].append(row)
    return {key: _aggregate_position_bucket(bucket_rows) for key, bucket_rows in grouped_rows.items()}


def _aggregate_position_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = rows[0]
    return {
        "instrument_code": _text_value(first.get("instrument_code")),
        "portfolio_name": _text_value(first.get("portfolio_name")),
        "cost_center": _text_value(first.get("cost_center")),
        "accounting_class": _text_value(first.get("accounting_class")),
        "currency_code": _text_value(first.get("currency_code")),
        "market_value": _sum_decimal(rows, "market_value"),
        "face_value": (None if any(_is_missing(row.get("face_value")) for row in rows)
                       else _sum_decimal(rows, "face_value")),
        "accrued_interest": _sum_optional_decimal(rows, "accrued_interest"),
        "coupon_rate": _weighted_row_value(rows, "coupon_rate", "face_value"),
        # 合法负收益率（≥ −20%）必须在聚合时保留，否则下游 merge_positions 只会看到
        # None → 0 → par 回退，与 bond_analytics 事实表按负收益率贴现的口径分叉。
        "ytm": _weighted_row_value(
            rows, "ytm", "market_value", negative_floor=NEGATIVE_YIELD_DIRTY_FLOOR
        ),
        "asset_class_std": _dominant_value(rows, "asset_class_std"),
        "rating": _dominant_value(rows, "rating"),
        "interest_mode": _dominant_value(rows, "interest_mode"),
        "maturity_date": _dominant_value(rows, "maturity_date"),
        # 引擎在 fact_bond_analytics 上已经逐行判过「票息/收益率是观测值还是回退值」，
        # 这里原样带出，免得同一个退化在归因链路上又变成一个没有来历的数。
        "coupon_rate_input_status": _degraded_quality_flag(
            rows, "coupon_rate_input_status", RATE_INPUT_STATUS_OBSERVED
        ),
        "ytm_input_status": _degraded_quality_flag(
            rows, "ytm_input_status", RATE_INPUT_STATUS_OBSERVED
        ),
        "duration_quality_flag": _degraded_quality_flag(
            rows, "duration_quality_flag", DURATION_QUALITY_OBSERVED
        ),
    }


def _degraded_quality_flag(rows: list[dict[str, Any]], field: str, observed: str) -> str | None:
    """聚合桶内的行级质量标记：任一行降级即整桶按降级报（fail-closed）。"""
    present = [value for value in (_text_value(row.get(field)) for row in rows) if value]
    if not present:
        return None
    degraded = [value for value in present if value != observed]
    return degraded[0] if degraded else observed


def _weighted_row_value(
    rows: list[dict[str, Any]],
    value_field: str,
    weight_field: str,
    *,
    negative_floor: float | None = None,
) -> float | None:
    numerator = Decimal("0")
    denominator = Decimal("0")
    equal_weight_sum = Decimal("0")
    equal_weight_count = 0
    for row in rows:
        value = normalize_annual_rate_to_decimal(row.get(value_field), negative_floor=negative_floor)
        if value is None:
            continue
        value_dec = Decimal(str(value))
        weight = abs(_decimal_value(row.get(weight_field)))
        if weight == 0 and weight_field != "market_value":
            weight = abs(_decimal_value(row.get("market_value")))
        if weight > 0:
            numerator += value_dec * weight
            denominator += weight
        equal_weight_sum += value_dec
        equal_weight_count += 1
    if denominator > 0:
        return float(numerator / denominator)
    if equal_weight_count:
        return float(equal_weight_sum / Decimal(equal_weight_count))
    return None


def _campisi_asset_class(s: dict[str, Any], e: dict[str, Any]) -> str:
    s_asset = _text_value(s.get("asset_class_std"))
    e_asset = _text_value(e.get("asset_class_std"))
    asset_class = e_asset if _is_generic_asset_class(s_asset) and e_asset else s_asset or e_asset
    rating = _text_value(s.get("rating") or e.get("rating")).upper().replace(" ", "")
    if rating and rating not in asset_class.upper().replace(" ", ""):
        return f"{asset_class} {rating}".strip()
    return asset_class


def _sum_decimal(rows: list[dict[str, Any]], field: str) -> Decimal:
    return sum((_decimal_value(row.get(field)) for row in rows), Decimal("0"))


def _sum_optional_decimal(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [_decimal_value(row.get(field)) for row in rows if not _is_missing(row.get(field))]
    if not values:
        return None
    return float(sum(values, Decimal("0")))


def _dominant_value(rows: list[dict[str, Any]], field: str) -> Any:
    best_value: Any = None
    best_weight = Decimal("-1")
    for row in rows:
        value = row.get(field)
        if _is_missing(value):
            continue
        weight = abs(_decimal_value(row.get("market_value")))
        if best_value is None or weight > best_weight:
            best_value = value
            best_weight = weight
    return best_value


def _is_generic_asset_class(value: str) -> bool:
    return value.strip().lower() in {"", "other", "unknown"}


# 序列化后的缺失占位符：按真缺失处理，与脏输入语义区分。
_MISSING_NUMERIC_TEXT = {"nan", "none", "null"}


def _decimal_value(value: Any) -> Decimal:
    """真缺失（None/空白/NaN/缺失占位符）→ 0；脏输入 → DirtyNumericInputError，不静默落零。"""
    if _is_missing(value):
        return Decimal("0")
    if isinstance(value, str) and value.strip().lower() in _MISSING_NUMERIC_TEXT:
        return Decimal("0")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DirtyNumericInputError(
            f"无法解析为 Decimal 的脏数值输入：{value!r}（{type(value).__name__}）"
        ) from exc
    if not parsed.is_finite():
        raise DirtyNumericInputError(f"非有限数值不得进入 Campisi 计算：{value!r}")
    return parsed


def _numeric_raw(value: Any) -> Decimal:
    if isinstance(value, dict):
        return _decimal_value(value.get("raw"))
    return _decimal_value(value)


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        # NaN != NaN；pandas NA 布尔化抛 TypeError，numpy 数组抛 ValueError，均按"非缺失"处理。
        return bool(value != value)
    except (TypeError, ValueError):
        return False


def merge_positions(
    rows_start: list[dict[str, Any]],
    rows_end: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    将期初和期末的 bond_analytics_rows 合并为 campisi_attribution 需要的 positions_merged 格式。

    campisi.py 需要每行包含：
    - market_value_start/end, face_value_start, coupon_rate_start,
    - yield_to_maturity_start, asset_class_start, maturity_date_start, bond_code

    键取两期并集，因此会出现只在一侧存在的持仓。这类行保留 ``start_present`` /
    ``end_present`` 标记，缺失一侧的市值/面值留空而不是折成 0；把「不存在」写成 0
    会让下游把整笔市值读成价格涨跌，差额 100% 落进 selection_effect。
    """
    start_by_key = _aggregate_position_rows(rows_start)
    end_by_key = _aggregate_position_rows(rows_end)
    all_codes = set(start_by_key.keys()) | set(end_by_key.keys())
    merged: list[dict[str, Any]] = []

    for key in sorted(all_codes):
        s = start_by_key.get(key, {})
        e = end_by_key.get(key, {})
        start_present = key in start_by_key
        end_present = key in end_by_key
        code = str(s.get("instrument_code") or e.get("instrument_code") or "")

        coupon_source = e if _is_missing(s.get("coupon_rate")) else s
        coupon_raw = coupon_source.get("coupon_rate")
        coupon_dec = normalize_annual_rate_to_decimal(coupon_raw) if coupon_raw is not None else None

        ytm_source = e if _is_missing(s.get("ytm")) else s
        ytm_raw = ytm_source.get("ytm")
        # 与 bond_analytics 引擎同口径：合法负收益率（≥ −20%）保留为观测值，
        # 否则 Campisi 会把同一只券按 par 回退而事实表按负收益率贴现。
        ytm_dec = (
            normalize_annual_rate_to_decimal(ytm_raw, negative_floor=NEGATIVE_YIELD_DIRTY_FLOOR)
            if ytm_raw is not None
            else None
        )

        merged.append({
            "bond_code": code,
            "instrument_id": code,
            "position_key": "|".join(key),
            "portfolio_name": key[1],
            "cost_center": key[2],
            "accounting_class": key[3],
            "currency_code": key[4],
            "start_present": start_present,
            "end_present": end_present,
            "market_value_start": float(s.get("market_value") or 0) if start_present else None,
            "market_value_end": float(e.get("market_value") or 0) if end_present else None,
            "face_value_start": s.get("face_value") if start_present else None,
            "face_value_end": e.get("face_value") if end_present else None,
            "accrued_interest_start": s.get("accrued_interest"),
            "accrued_interest_end": e.get("accrued_interest"),
            # 缺票息/缺 YTM 留 None；真实观测 0 保留为有效收益率，
            # 缺失 YTM 由下游按票息执行 par 回退。
            "coupon_rate_start": coupon_dec,
            "yield_to_maturity_start": ytm_dec,
            "interest_mode_start": _merged_quality_flag(s, e, "interest_mode"),
            "asset_class_start": _campisi_asset_class(s, e),
            "rating_start": s.get("rating") or e.get("rating") or "",
            "maturity_date_start": s.get("maturity_date") or e.get("maturity_date"),
            "coupon_rate_input_status": _text_value(coupon_source.get("coupon_rate_input_status")) or None,
            "ytm_input_status": _text_value(ytm_source.get("ytm_input_status")) or None,
            "duration_quality_flag": _merged_quality_flag(s, e, "duration_quality_flag"),
        })

    return merged


def _merged_quality_flag(s: dict[str, Any], e: dict[str, Any], field: str) -> str | None:
    """与 coupon/ytm 的取值顺序一致：先期初，缺则回退期末。"""
    return _text_value(s.get(field)) or _text_value(e.get(field)) or None


# Private alias kept for backward compatibility with existing internal callers.
_merge_positions = merge_positions


def _build_input_quality(
    *,
    rows_start: list[dict[str, Any]],
    rows_end: list[dict[str, Any]],
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    start_quality = _side_input_quality(rows_start)
    end_quality = _side_input_quality(rows_end)
    single_sided = _single_sided_position_summary(positions)
    degraded_start = start_quality["duration_quality_degraded"]
    degraded_end = end_quality["duration_quality_degraded"]
    warnings: list[str] = []
    if _has_missing_fields(start_quality) or _has_missing_fields(end_quality):
        warnings.append("Campisi input has missing pricing or classification fields.")
    if single_sided["single_sided_positions"]:
        warnings.append(
            "Campisi merged positions include "
            f"{single_sided['start_only_positions']} start-only and "
            f"{single_sided['end_only_positions']} end-only rows (market_value "
            f"{single_sided['start_only_market_value']:.2f} start-only, "
            f"{single_sided['end_only_market_value']:.2f} end-only); all four effects and "
            "total_return are 0 on those rows because a holding that exists on one period end "
            "only is a position change, not a price move. Trade-level attribution for them is "
            "undefined and their amounts are excluded from every effect."
        )
    if degraded_start["rows"] or degraded_end["rows"]:
        warnings.append(
            "Campisi input carries bond-analytics rows whose duration_quality_flag is not "
            f"\"{DURATION_QUALITY_OBSERVED}\" ({degraded_start['rows']} start rows / "
            f"market_value {degraded_start['market_value']:.2f}, {degraded_end['rows']} end rows / "
            f"market_value {degraded_end['market_value']:.2f}); modified duration on those rows "
            "is a fallback, so treasury and spread effects there are model output rather than "
            "observed rate sensitivity."
        )
    if start_quality["duplicate_instrument_codes"]["instrument_codes"] or end_quality["duplicate_instrument_codes"]["instrument_codes"]:
        warnings.append(
            "Campisi input has duplicate instrument_code rows; aggregation uses the business position key."
        )
    if start_quality["duplicate_position_keys"]["position_keys"] or end_quality["duplicate_position_keys"]["position_keys"]:
        warnings.append("Campisi input has duplicate position keys; rows were aggregated before attribution.")
    return {
        "position_key_fields": list(_POSITION_KEY_FIELDS),
        "start_rows": len(rows_start),
        "end_rows": len(rows_end),
        "merged_positions": len(positions),
        **single_sided,
        "duration_quality_degraded": {"start": degraded_start, "end": degraded_end},
        "missing_fields": {
            "start": start_quality["missing_fields"],
            "end": end_quality["missing_fields"],
        },
        "duplicate_instrument_codes": {
            "start": start_quality["duplicate_instrument_codes"],
            "end": end_quality["duplicate_instrument_codes"],
        },
        "duplicate_position_keys": {
            "start": start_quality["duplicate_position_keys"],
            "end": end_quality["duplicate_position_keys"],
        },
        "warnings": warnings,
    }


def _treasury_effect_availability(
    tenors: dict[str, Any],
    *,
    start_curve_rows_present: bool | None,
    end_curve_rows_present: bool | None,
    start_requested_date: str | None = None,
    start_resolved_date: str | None = None,
    end_requested_date: str | None = None,
    end_resolved_date: str | None = None,
    start_curve_used: bool | None = None,
    end_curve_used: bool | None = None,
) -> dict[str, Any]:
    """把国债曲线覆盖度折叠成一个页面可直接分支的显式状态块。

    ``status="unavailable"`` 时 ``treasury_effect`` 的 0 是输入缺失的产物；
    ``reason`` 进一步区分"没有曲线事实 / 曲线不可用 / 共同期限不足"，三者的
    处置完全不同（补数、修单位、放宽期限口径），塌成一个 0 就全看不见了。
    """
    required = len(tenors["required_keys"])
    start_usable = required - len(tenors["start_missing"])
    end_usable = required - len(tenors["end_missing"])
    shared = tenors["shared_positive_tenors"]

    start_available = start_curve_used if start_curve_used is not None else start_curve_rows_present
    end_available = end_curve_used if end_curve_used is not None else end_curve_rows_present
    if start_available is False or end_available is False:
        reason: str | None = TREASURY_CURVE_ABSENT_REASON
    elif start_usable == 0 or end_usable == 0:
        reason = TREASURY_CURVE_UNUSABLE_REASON
    elif shared < 2:
        reason = TREASURY_CURVE_INSUFFICIENT_SHARED_TENORS_REASON
    else:
        reason = None

    return {
        "status": "ok" if reason is None else "unavailable",
        "reason": reason,
        "start_curve_rows_present": start_curve_rows_present,
        "end_curve_rows_present": end_curve_rows_present,
        "start_usable_tenors": start_usable,
        "end_usable_tenors": end_usable,
        "shared_positive_tenors": shared,
        "start_requested_date": start_requested_date,
        "start_resolved_date": start_resolved_date,
        "end_requested_date": end_requested_date,
        "end_resolved_date": end_resolved_date,
        "start_curve_used": start_curve_used,
        "end_curve_used": end_curve_used,
    }


def _treasury_effect_warning(availability: dict[str, Any]) -> str | None:
    """每个 reason 一句自己的话；文本里保留 "degrade to 0" 便于既有匹配器。"""
    reason = availability["reason"]
    if reason is None:
        return None
    if reason == TREASURY_CURVE_ABSENT_REASON:
        sides = ", ".join(
            side
            for side, present, used in (
                ("start", availability["start_curve_rows_present"], availability["start_curve_used"]),
                ("end", availability["end_curve_rows_present"], availability["end_curve_used"]),
            )
            if used is False or (used is None and present is False)
        )
        return (
            f"Campisi treasury curve is absent or stale for the period {sides} date(s): "
            "there is no admissible formal curve on a required side (no prior row, or the latest "
            "prior row was discarded by the staleness guard). Treasury effect and roll-down "
            "degrade to 0 for this period; the 0 means \"no usable curve data\", "
            "not \"rates did not move\"."
        )
    if reason == TREASURY_CURVE_UNUSABLE_REASON:
        return (
            "Campisi treasury curve rows exist but no key tenor is usable on at least one period "
            f"end (start_usable_tenors={availability['start_usable_tenors']}, "
            f"end_usable_tenors={availability['end_usable_tenors']}); treasury effect and "
            "roll-down degrade to 0 for this period rather than measuring a zero rate move."
        )
    return (
        "Campisi treasury curve has fewer than 2 shared positive tenors between period "
        "start and end; treasury effect and roll-down degrade to 0 for this period."
    )


def _add_market_curve_quality(
    input_quality: dict[str, Any],
    *,
    positions: list[dict[str, Any]],
    market_start: dict[str, Any],
    market_end: dict[str, Any],
    start_curve_rows_present: bool | None = None,
    end_curve_rows_present: bool | None = None,
    start_requested_date: str | None = None,
    start_resolved_date: str | None = None,
    end_requested_date: str | None = None,
    end_resolved_date: str | None = None,
    start_curve_used: bool | None = None,
    end_curve_used: bool | None = None,
) -> dict[str, Any]:
    coverage = _market_curve_coverage(positions=positions, market_start=market_start, market_end=market_end)
    input_quality["market_curve_coverage"] = coverage
    missing = coverage["missing_credit_spread_3y"]
    if missing:
        ratings = ", ".join(item["rating"] for item in missing)
        input_quality["warnings"].append(
            "Campisi credit spread curve coverage is incomplete for ratings "
            f"{ratings}; spread effect may be understated because missing spread inputs are unavailable."
        )
    tenors = coverage["treasury_tenors"]
    treasury_effect = _treasury_effect_availability(
        tenors,
        start_curve_rows_present=start_curve_rows_present,
        end_curve_rows_present=end_curve_rows_present,
        start_requested_date=start_requested_date,
        start_resolved_date=start_resolved_date,
        end_requested_date=end_requested_date,
        end_resolved_date=end_resolved_date,
        start_curve_used=start_curve_used,
        end_curve_used=end_curve_used,
    )
    coverage["treasury_effect"] = treasury_effect
    for side, requested, resolved, used in (
        ("start", start_requested_date, start_resolved_date, start_curve_used),
        ("end", end_requested_date, end_resolved_date, end_curve_used),
    ):
        if not requested or not resolved or requested == resolved:
            continue
        if used:
            input_quality["warnings"].append(
                f"Campisi {side} treasury curve uses formal snapshot from {resolved} "
                f"for position date {requested}; latest_snapshot fallback was applied."
            )
        else:
            input_quality["warnings"].append(
                f"Campisi {side} treasury curve resolved to {resolved} for position date {requested}, "
                f"but exceeded the {_DECISION_CURVE_STALENESS_THRESHOLD_DAYS}-day staleness guard "
                "and was discarded. Treasury effect remains unavailable."
            )
    treasury_warning = _treasury_effect_warning(treasury_effect)
    if treasury_warning is not None:
        input_quality["warnings"].append(treasury_warning)
    elif tenors["start_missing"] or tenors["end_missing"]:
        missing_desc = "; ".join(
            f"{side} missing {', '.join(keys)}"
            for side, keys in (("start", tenors["start_missing"]), ("end", tenors["end_missing"]))
            if keys
        )
        input_quality["warnings"].append(
            f"Campisi treasury curve tenor coverage is incomplete ({missing_desc}); "
            "interpolation degrades to the shared-tenor subset and long-end effects may be understated."
        )
    return input_quality


def _market_curve_coverage(
    *,
    positions: list[dict[str, Any]],
    market_start: dict[str, Any],
    market_end: dict[str, Any],
) -> dict[str, Any]:
    required: dict[str, dict[str, Any]] = {}
    for position in positions:
        rating = infer_credit_rating_from_asset_class(position.get("asset_class_start"))
        field = _SPREAD_FIELD_BY_RATING.get(rating)
        if field is None:
            continue
        bucket = required.setdefault(
            rating,
            {
                "rating": rating,
                "field": field,
                "positions": 0,
                "market_value_start": Decimal("0"),
            },
        )
        bucket["positions"] += 1
        bucket["market_value_start"] += _decimal_value(position.get("market_value_start"))

    required_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    for rating in ("AAA", "AA+", "AA"):
        row = required.get(rating)
        if row is None:
            continue
        field = row["field"]
        start_available = usable_spread_bp(market_start, rating) is not None
        end_available = usable_spread_bp(market_end, rating) is not None
        out = {
            "rating": rating,
            "field": field,
            "positions": row["positions"],
            "market_value_start": float(row["market_value_start"]),
            "start_available": start_available,
            "end_available": end_available,
        }
        required_rows.append(out)
        missing_sides = [
            side
            for side, available in (("start", start_available), ("end", end_available))
            if not available
        ]
        if missing_sides:
            missing_rows.append({**out, "missing_sides": missing_sides})

    return {
        "required_credit_spread_3y": required_rows,
        "missing_credit_spread_3y": missing_rows,
        "treasury_tenors": treasury_tenor_coverage(market_start, market_end),
    }


def _side_input_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing: dict[str, dict[str, int | float]] = {}
    for field in _QUALITY_MISSING_FIELDS:
        missing_rows = [row for row in rows if _is_missing(row.get(field))]
        count = len(missing_rows)
        if count:
            missing[field] = {"rows": count, "market_value": float(_sum_decimal(missing_rows, "market_value"))}
    degraded_rows = [
        row
        for row in rows
        if (_text_value(row.get("duration_quality_flag")) or DURATION_QUALITY_OBSERVED)
        != DURATION_QUALITY_OBSERVED
    ]
    return {
        "missing_fields": missing,
        "duration_quality_degraded": {
            "rows": len(degraded_rows),
            "market_value": float(_sum_decimal(degraded_rows, "market_value")),
        },
        "duplicate_instrument_codes": _duplicate_value_summary(rows, "instrument_code", "instrument_codes"),
        "duplicate_position_keys": _duplicate_position_key_summary(rows),
    }


def _single_sided_position_summary(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """只在期初或只在期末存在的持仓：行数与两侧市值都要披露。

    这些行的四效应与 total_return 都是 0，页面必须能区分「没有贡献」与
    「持仓变动，归因口径未裁决」。
    """
    start_only = [row for row in positions if row.get("end_present") is False]
    end_only = [row for row in positions if row.get("start_present") is False]
    return {
        "single_sided_positions": len(start_only) + len(end_only),
        "start_only_positions": len(start_only),
        "end_only_positions": len(end_only),
        "start_only_market_value": float(_sum_decimal(start_only, "market_value_start")),
        "end_only_market_value": float(_sum_decimal(end_only, "market_value_end")),
    }


def _duplicate_value_summary(rows: list[dict[str, Any]], field_name: str, label: str) -> dict[str, int | float]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = _text_value(row.get(field_name))
        if not value:
            continue
        grouped[value].append(row)
    duplicate_rows = [row for bucket in grouped.values() if len(bucket) > 1 for row in bucket]
    return {
        label: sum(1 for bucket in grouped.values() if len(bucket) > 1),
        "rows": len(duplicate_rows),
        "market_value": float(_sum_decimal(duplicate_rows, "market_value")),
    }


def _duplicate_position_key_summary(rows: list[dict[str, Any]]) -> dict[str, int | float]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _position_key(row)
        if key is not None:
            grouped[key].append(row)
    duplicate_rows = [row for bucket in grouped.values() if len(bucket) > 1 for row in bucket]
    return {
        "position_keys": sum(1 for bucket in grouped.values() if len(bucket) > 1),
        "rows": len(duplicate_rows),
        "market_value": float(_sum_decimal(duplicate_rows, "market_value")),
    }


def _has_missing_fields(side_quality: dict[str, Any]) -> bool:
    return any(summary["rows"] for summary in side_quality["missing_fields"].values())


def _anchor_on_or_before(dates: list[str], day: str) -> str | None:
    eligible = [d for d in dates if d <= day]
    return max(eligible) if eligible else None


def _empty_campisi_payload(start: str, end: str) -> dict[str, Any]:
    return {
        "report_date": end,
        "period_start": start,
        "period_end": end,
        "num_days": 0,
        "totals": {
            "income_return": 0.0,
            "treasury_effect": 0.0,
            "spread_effect": 0.0,
            "selection_effect": 0.0,
            "total_return": 0.0,
            "market_value_start": 0.0,
        },
        "by_asset_class": [],
        "by_bond": [],
        "warnings": ["缺债券持仓事实，Campisi 分解为空。"],
    }


def _fetch_formal_bridge(
    *, settings: Any, report_date: str, start_date: str | None = None,
) -> dict[str, Any]:
    from backend.app.services.pnl_bridge_service import pnl_bridge_envelope

    expected_start = _prior_month_end(report_date)
    if start_date is not None and start_date != expected_start:
        raise ValueError(
            "PNL_BRIDGE_WINDOW_MISMATCH: "
            f"Requested exposure window {start_date} through {report_date}; "
            f"formal monthly PnL requires baseline {expected_start}. "
            "Monthly PnL cannot be relabelled as a daily or multi-month return."
        )
    envelope = pnl_bridge_envelope(
        duckdb_path=str(settings.duckdb_path),
        governance_dir=str(settings.governance_path),
        report_date=report_date,
    )
    result_meta = envelope.get("result_meta") or {}
    assert isinstance(result_meta, dict)
    window = result_meta.get("filters_applied") or {}
    if start_date is not None and (
        window.get("window_aligned") is not True
        or (window.get("balance_window") or {}).get("start") != start_date
        or (window.get("balance_window") or {}).get("end") != report_date
    ):
        raise ValueError(
            "PNL_BRIDGE_WINDOW_MISMATCH: Exact monthly balance endpoints are unavailable; "
            "the formal bridge cannot establish same-period Campisi closure."
        )
    return envelope


# 正式桥接的"可用性降级"只覆盖数据/环境类失败（无数据 ValueError、血缘损坏 RuntimeError、
# DuckDB/文件访问错误）；编程错误（KeyError/TypeError/AttributeError 等）不再被静默吞掉。
_BRIDGE_UNAVAILABLE_ERRORS = (duckdb.Error, OSError, ValueError, RuntimeError)


def _formal_bridge_failure_reason(exc: BaseException) -> str:
    """Expose only known bridge failure codes, never source-bearing exception text."""
    code = str(exc).partition(":")[0]
    if code == "PNL_BRIDGE_WINDOW_MISMATCH":
        reason = "PNL_BRIDGE_WINDOW_MISMATCH: Monthly PnL and balance endpoints are not aligned."
    elif code == DUPLICATE_BALANCE_KEY_PREFIX:
        reason = "DUPLICATE_BALANCE_KEY: The formal bridge requires a unique balance match."
    else:
        reason = "Formal bridge data or runtime is unavailable."
    return f"{reason} (error_type={type(exc).__name__})"


def _try_fetch_formal_bridge(
    *, settings: Any, report_date: str, start_date: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any] | None:
    try:
        return _fetch_formal_bridge(settings=settings, report_date=report_date, start_date=start_date)
    except _BRIDGE_UNAVAILABLE_ERRORS as exc:
        raise_if_system_read_failure(exc)
        reason = _formal_bridge_failure_reason(exc)
        logger.warning("正式 PnL 桥接不可用（report_date=%s）：%s", report_date, reason)
        if warnings is not None:
            warnings.append(f"Formal PnL bridge unavailable: {reason}")
        return None


def _try_fetch_cached_formal_bridge(
    *,
    settings: Any,
    report_date: str,
    duckdb_fingerprint: tuple[tuple[str, int, int], ...] | None,
    start_date: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any] | None:
    cache_key = _campisi_bridge_cache_key(
        duckdb_path=settings.duckdb_path,
        governance_path=settings.governance_path,
        duckdb_fingerprint=duckdb_fingerprint,
        governance_fingerprint=_selected_files_fingerprint(
            settings.governance_path,
            _GOVERNANCE_BRIDGE_DEPENDENCY_FILES,
        ),
        report_date=report_date,
        start_date=start_date,
    )
    cached = _get_cached_campisi_bridge(cache_key)
    if cached is not None:
        return cached
    try:
        bridge = _fetch_formal_bridge(settings=settings, report_date=report_date, start_date=start_date)
    except _BRIDGE_UNAVAILABLE_ERRORS as exc:
        raise_if_system_read_failure(exc)
        reason = _formal_bridge_failure_reason(exc)
        logger.warning("正式 PnL 桥接不可用（report_date=%s，缓存路径）：%s", report_date, reason)
        if warnings is not None:
            warnings.append(f"Formal PnL bridge unavailable: {reason}")
        return None
    return _set_cached_campisi_bridge(cache_key, bridge)


def _formal_bridge_rows(bridge_envelope: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not bridge_envelope:
        return []
    rows = ((bridge_envelope.get("result") or {}).get("rows") or [])
    return [row for row in rows if isinstance(row, dict)]


def _bridge_position_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _text_value(row.get("instrument_code") or row.get("bond_code") or row.get("instrument_id")),
        _text_value(row.get("portfolio_name")),
        _text_value(row.get("cost_center")),
    )


def _position_lookup(positions: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for position in positions:
        key = _bridge_position_key(position)
        if not key[0]:
            continue
        existing = out.get(key)
        if existing is None or abs(_decimal_value(position.get("market_value_start"))) > abs(
            _decimal_value(existing.get("market_value_start"))
        ):
            out[key] = position
    return out


def _formal_bridge_has_position_overlap(
    bridge_envelope: dict[str, Any] | None,
    positions: list[dict[str, Any]],
) -> bool:
    position_keys = set(_position_lookup(positions))
    if not position_keys:
        return False
    return any(_bridge_position_key(row) in position_keys for row in _formal_bridge_rows(bridge_envelope))


def _add_formal_bridge_coverage(
    input_quality: dict[str, Any],
    *,
    bridge_envelope: dict[str, Any],
    attributed_rows: int,
) -> None:
    """Disclose inclusion of the bridge population without inventing model exclusions."""
    summary = (bridge_envelope.get("result") or {}).get("summary") or {}
    count = summary.get("row_count")
    bridge_rows = count if type(count) is int and count >= 0 else None
    coverage: dict[str, Any] = {
        "source": "pnl.bridge.rows",
        "basis": FORMAL_REPORT_BASIS,
        "status": "unavailable",
        "bridge_rows": bridge_rows,
        "attributed_rows": attributed_rows,
    }
    if bridge_rows is None:
        coverage["reason"] = "bridge_row_count_unavailable"
    elif bridge_rows == 0:
        coverage["reason"] = "bridge_rows_empty"
    elif attributed_rows == bridge_rows:
        coverage["status"] = "ok"
    else:
        coverage["status"] = "partial" if 0 < attributed_rows < bridge_rows else "unavailable"
        coverage["reason"] = "bridge_row_count_mismatch"
    input_quality["formal_bridge_coverage"] = coverage
    if coverage["status"] != "ok":
        input_quality["warnings"].append(
            f"Campisi formal bridge row inclusion is {coverage['status']} "
            f"({coverage['reason']}; attributed_rows={attributed_rows}, bridge_rows={bridge_rows}); "
            "amount closure does not establish complete bridge population coverage."
        )


def _formal_asset_class(row: dict[str, Any], position: dict[str, Any] | None) -> str:
    asset_class = _text_value((position or {}).get("asset_class_start"))
    accounting_basis = _text_value(row.get("accounting_basis"))
    if asset_class and accounting_basis and accounting_basis.upper() not in asset_class.upper():
        return f"{asset_class} {accounting_basis}"
    return asset_class or accounting_basis or "unclassified"


def _coerce_date(value: Any) -> date | None:
    if hasattr(value, "date"):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text_value(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _formal_maturity_bucket(position: dict[str, Any] | None, start_date: date) -> str:
    maturity = _coerce_date((position or {}).get("maturity_date_start"))
    if maturity is None:
        return "UNKNOWN"
    years = max((maturity - start_date).days / 365.0, 0.01)
    if years <= 1:
        return _MATURITY_BUCKET_LABELS[0]
    if years <= 3:
        return _MATURITY_BUCKET_LABELS[1]
    if years <= 5:
        return _MATURITY_BUCKET_LABELS[2]
    if years <= 7:
        return _MATURITY_BUCKET_LABELS[3]
    if years <= 10:
        return _MATURITY_BUCKET_LABELS[4]
    return _MATURITY_BUCKET_LABELS[5]


def _assert_formal_bridge_row_closure(
    *,
    bridge_row: dict[str, Any],
    selection: Decimal,
) -> None:
    """bridge 路径的 selection 必须等于 pnl_bridge 独立给出的 residual。

    pnl_bridge.build_pnl_bridge_rows 的互斥分解里
    explained_pnl = carry + roll_down + treasury_curve + credit_spread +
    fx_translation + realized_trading + manual_adjustment（不含 516/unrealized_fv），
    residual = actual_pnl − explained_pnl，与本服务重算的 selection 是同一个量。
    因此用桥行自带的 residual 字段做独立对照；若沿用与 selection 完全相同的减法
    重算，断言恒为 0，桥接口径漂移无法被发现。
    """
    residual_raw = bridge_row.get("residual")
    if residual_raw is None:
        raise ValueError(
            "Formal bridge Campisi row closure failed: 桥行缺少 residual 字段，无独立对照可校验 "
            f"selection={selection}"
        )
    residual = _numeric_raw(residual_raw)
    difference = selection - residual
    # 桥行数值经 Numeric.raw（float）出参，分量求和的 float 往返噪音随金额量级增长，
    # 因此在既有 1e-6 绝对容差上叠加一个远大于 float64 相对误差的量级项。
    tolerance = _FORMAL_BRIDGE_ROW_CLOSURE_ABS_TOLERANCE + _FORMAL_BRIDGE_ROW_CLOSURE_REL_TOLERANCE * (
        abs(selection) + abs(residual)
    )
    if abs(difference) > tolerance:
        raise ValueError(
            "Formal bridge Campisi row closure failed: "
            f"selection={selection} 与 pnl_bridge residual={residual} 不一致（difference={difference}）"
        )


def _decision_window_declarations(
    *,
    anchor_start: str,
    anchor_end: str,
) -> tuple[dict[str, str], dict[str, str], int]:
    num_days = max((date.fromisoformat(anchor_end) - date.fromisoformat(anchor_start)).days, 0)
    # fact_formal_pnl_fi 的一行是 anchor_end 报告月的月度期间流量（report_date 均为
    # 月末），窗口声明必须按月度期间给出；此前的 single_day 声明与取数语义不符。
    pnl_window = {
        "start": date.fromisoformat(anchor_end).replace(day=1).isoformat(),
        "end": anchor_end,
        "kind": "monthly_period",
    }
    curve_window = {"start": anchor_start, "end": anchor_end, "kind": "curve_displacement"}
    return pnl_window, curve_window, num_days


def _decision_window_base_clause(
    *,
    pnl_window: dict[str, str],
    curve_window: dict[str, str],
    num_days: int,
) -> str:
    return (
        f"formal PnL 为 pnl_window（{pnl_window['start']}→{pnl_window['end']}）月度期间流量，"
        f"市场效应按 curve_window（{curve_window['start']}→{curve_window['end']}，{num_days} 天）"
        "整段曲线位移解释"
    )


def _decision_window_disclosure(
    *,
    pnl_window: dict[str, str],
    curve_window: dict[str, str],
    num_days: int,
    curve_alignment: dict[str, Any],
) -> dict[str, str] | None:
    """披露分级由曲线解析偏差与窗口口径共同驱动。

    warning 触发条件（任一）：
    - 曲线陈旧守卫触发：解析日偏离窗口端点超过阈值，已按缺失处理；
    - 国债曲线整侧缺失：市场效应整体不可解释；
    - curve_window 跨度超过 45 天：显式长窗口请求相对月度期间属口径错配。
    其余情况为 info：月度对齐是常态口径，但 selection_proxy 仍含残余错配影响，必须披露。
    此前分级仅键在 num_days 上——默认路径 num_days 恒为 30，2026-02 这类曲线跳月的
    危险月份与健康月份拿到同样的 info 级披露，warning 分支形同虚设。
    """
    threshold = int(curve_alignment.get("threshold_days") or _DECISION_CURVE_STALENESS_THRESHOLD_DAYS)
    discarded = list(curve_alignment.get("discarded") or [])
    missing_treasury = list(curve_alignment.get("missing_treasury") or [])
    issues: list[str] = []
    if discarded:
        detail = "；".join(
            f"{item['label']}解析 {item['resolved']} 偏离窗口端点 {item['target']} 达 {item['deviation_days']} 天"
            for item in discarded
        )
        issues.append(f"曲线陈旧守卫（>{threshold} 天）触发：{detail}，已按缺失处理并计入 residual_noise")
    if missing_treasury:
        issues.append("、".join(missing_treasury) + "缺失，相关市场效应计入 residual_noise")
    if num_days > _DECISION_WINDOW_MISMATCH_THRESHOLD_DAYS:
        issues.append(
            f"口径错配：curve_window 跨度 {num_days} 天，"
            f"远超 formal PnL 月度期间（{pnl_window['start']}→{pnl_window['end']}）"
        )
    base = _decision_window_base_clause(pnl_window=pnl_window, curve_window=curve_window, num_days=num_days)
    if issues:
        return {
            "level": "warning",
            "message": (
                f"口径警示：{base}；" + "；".join(issues) + "；"
                "selection_proxy 与 residual_noise 含上述影响，不得解读为主动管理能力。"
            ),
        }
    if num_days < 1:
        return None
    return {
        "level": "info",
        "message": (
            f"口径说明：{base}，曲线解析偏差未超过陈旧守卫阈值 {threshold} 天；"
            "selection_proxy 含残余窗口错配影响，解读主动管理能力时需扣除。"
        ),
    }


def _bridge_row_has_diagnostic(bridge_row: dict[str, Any], prefixes: tuple[str, ...]) -> bool:
    raw = bridge_row.get("balance_diagnostics") or ()
    return any(str(message).startswith(prefixes) for message in raw)


def _formal_bridge_effect_availability(
    by_bond: list[dict[str, Any]],
    *,
    enhanced: bool = False,
    bridge_envelope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """formal-bridge 路径的可用性块，形状与 Campisi 直算路径完全一致。

    没有这一块时 ``CampisiResult.effect_availability`` 会退化成空 dict —— 页面看到
    "没有 unavailable 标记"就会当成一切正常，而这正是本次整改要消灭的那种沉默。

    ``enhanced=True`` 时额外产出 convexity / cross / reinvestment 三条
    ``not_decomposed`` 条目：这三项只出现在 enhanced 形状里，four-effects 形状
    根本没有对应金额，给它加条目反而是凭空多出一个不存在的效应。
    """
    bonds = len(by_bond)

    def _fold(predicate, reason: str) -> tuple[str, int, Decimal]:
        degraded = [row for row in by_bond if predicate(row)]
        market_value = sum(
            (_decimal_value(row.get("market_value_start")) for row in degraded), Decimal("0")
        )
        return coverage_status(len(degraded), bonds), len(degraded), market_value

    treasury_status, treasury_bonds, treasury_mv = _fold(
        lambda row: not row.get("treasury_effect_available", True),
        BRIDGE_CURVE_UNAVAILABLE_REASON,
    )
    spread_status, spread_bonds, spread_mv = _fold(
        lambda row: not row.get("spread_effect_available", True),
        BRIDGE_CURVE_UNAVAILABLE_REASON,
    )
    accrued_status, accrued_bonds, accrued_mv = _fold(
        lambda row: not row.get("has_accrued_interest", False),
        ACCRUED_INTEREST_MISSING_REASON,
    )
    availability: dict[str, Any] = {
        "bonds": bonds,
        "treasury_effect": effect_availability_entry(
            status=treasury_status,
            reason=None if treasury_status == "ok" else BRIDGE_CURVE_UNAVAILABLE_REASON,
            unavailable_bonds=treasury_bonds,
            unavailable_market_value_start=treasury_mv,
        ),
        "spread_effect": effect_availability_entry(
            status=spread_status,
            reason=None if spread_status == "ok" else BRIDGE_CURVE_UNAVAILABLE_REASON,
            unavailable_bonds=spread_bonds,
            unavailable_market_value_start=spread_mv,
        ),
        "accrued_interest": effect_availability_entry(
            status=accrued_status,
            reason=None if accrued_status == "ok" else ACCRUED_INTEREST_MISSING_REASON,
            unavailable_bonds=accrued_bonds,
            unavailable_market_value_start=accrued_mv,
            basis=accrued_interest_basis(accrued_status),
        ),
    }
    if enhanced:
        # 未拆分是整期、全人口的框架事实，不是逐券输入缺失，所以覆盖全部债券与市值。
        total_mv = sum(
            (_decimal_value(row.get("market_value_start")) for row in by_bond), Decimal("0")
        )
        for key in _BRIDGE_SECOND_ORDER_EFFECT_KEYS:
            availability[key] = effect_availability_entry(
                status=EFFECT_STATUS_NOT_DECOMPOSED,
                reason=BRIDGE_SECOND_ORDER_NOT_DECOMPOSED_REASON,
                unavailable_bonds=bonds,
                unavailable_market_value_start=total_mv,
            )
    summary = ((bridge_envelope or {}).get("result") or {}).get("summary") or {}
    for key in ("roll_down_availability", "treasury_curve_availability", "credit_spread_availability"):
        if isinstance(summary.get(key), dict):
            # Relay rather than rebuild: applicable_rows is effect-specific,
            # and not_applicable rows must not dilute the missing-input ratio.
            availability[key] = deepcopy(summary[key])
    return availability


def _formal_bridge_bond_rows(
    *,
    bridge_envelope: dict[str, Any],
    positions: list[dict[str, Any]],
    start_date: date,
    enhanced: bool = False,
) -> list[dict[str, Any]]:
    position_by_key = _position_lookup(positions)
    rows: list[dict[str, Any]] = []
    for bridge_row in _formal_bridge_rows(bridge_envelope):
        position = position_by_key.get(_bridge_position_key(bridge_row))
        income = _numeric_raw(bridge_row.get("carry"))
        treasury = _numeric_raw(bridge_row.get("roll_down")) + _numeric_raw(bridge_row.get("treasury_curve"))
        spread = _numeric_raw(bridge_row.get("credit_spread"))
        realized_trading = _numeric_raw(bridge_row.get("realized_trading"))
        manual_adjustment = _numeric_raw(bridge_row.get("manual_adjustment"))
        fx_translation = _numeric_raw(bridge_row.get("fx_translation"))
        convexity = Decimal("0")
        cross = Decimal("0")
        reinvestment = Decimal("0")
        total = _numeric_raw(bridge_row.get("actual_pnl"))
        selection = (
            total
            - income
            - treasury
            - spread
            - realized_trading
            - manual_adjustment
            - fx_translation
            - convexity
            - cross
            - reinvestment
        )
        _assert_formal_bridge_row_closure(bridge_row=bridge_row, selection=selection)
        record = {
            "bond_code": _text_value(bridge_row.get("instrument_code")),
            "asset_class": _formal_asset_class(bridge_row, position),
            "maturity_bucket": _formal_maturity_bucket(position, start_date),
            "market_value_start": float(
                _numeric_raw(bridge_row.get("beginning_dirty_mv"))
                or _decimal_value((position or {}).get("market_value_start"))
            ),
            "income_return": float(income),
            "treasury_effect": float(treasury),
            "spread_effect": float(spread),
            "realized_trading": float(realized_trading),
            "manual_adjustment": float(manual_adjustment),
            "fx_translation": float(fx_translation),
            "selection_effect": float(selection),
            "total_return": float(total),
            "mod_duration": float(_decimal_value((position or {}).get("mod_duration"))),
            "has_accrued_interest": position is not None
            and not _is_missing(position.get("accrued_interest_start"))
            and not _is_missing(position.get("accrued_interest_end")),
            # 桥已经在行级把"缺曲线 / 两端同源 / 缺市值基数 / 缺滚动窗口"标出来了；
            # 这里原样中继，免得同一个事实在 formal 路径上又退回成一个没有来历的 0。
            # 本路径的 treasury_effect 是 roll_down + treasury_curve 之和，所以把
            # 任一分量顶成 0 的诊断都会让这个和失去观测意义——只认曲线那两条前缀，
            # 就会漏掉"骑乘缺滚动窗口"这一半。
            "treasury_effect_available": not any(
                bridge_row.get(key) == "unavailable"
                for key in ("roll_down_availability", "treasury_curve_availability")
            ) and not _bridge_row_has_diagnostic(
                bridge_row,
                (
                    TREASURY_CURVE_UNAVAILABLE_PREFIX,
                    TREASURY_CURVE_SAME_SOURCE_PREFIX,
                    ROLL_DOWN_WINDOW_MISSING_PREFIX,
                    ROLL_DOWN_TENOR_OUTSIDE_CURVE_PREFIX,
                    MARKET_VALUE_BASE_MISSING_PREFIX,
                ),
            ),
            "spread_effect_available": bridge_row.get("credit_spread_availability") != "unavailable"
            and not _bridge_row_has_diagnostic(
                bridge_row,
                (
                    CREDIT_SPREAD_CURVE_UNAVAILABLE_PREFIX,
                    CREDIT_SPREAD_CURVE_SAME_SOURCE_PREFIX,
                    MARKET_VALUE_BASE_MISSING_PREFIX,
                ),
            ),
        }
        if enhanced:
            record.update(
                {
                    "convexity_effect": float(convexity),
                    "cross_effect": float(cross),
                    "reinvestment_effect": float(reinvestment),
                }
            )
        rows.append(record)
    return rows


def _formal_amount_keys(*, enhanced: bool = False) -> list[str]:
    keys = ["income_return", "treasury_effect", "spread_effect", *_FORMAL_BRIDGE_DETAIL_KEYS]
    if enhanced:
        keys.extend(["convexity_effect", "cross_effect", "reinvestment_effect"])
    keys.extend(["selection_effect", "total_return"])
    return keys


def _aggregate_formal_rows(rows: list[dict[str, Any]], *, enhanced: bool = False) -> list[dict[str, Any]]:
    amount_keys = _formal_amount_keys(enhanced=enhanced)
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        asset_class = _text_value(row.get("asset_class")) or "unclassified"
        bucket = buckets.setdefault(
            asset_class,
            {
                "asset_class": asset_class,
                "market_value_start": Decimal("0"),
                **{key: Decimal("0") for key in amount_keys},
            },
        )
        bucket["market_value_start"] += _decimal_value(row.get("market_value_start"))
        for key in amount_keys:
            bucket[key] += _decimal_value(row.get(key))
    total_mv = sum((_decimal_value(row["market_value_start"]) for row in buckets.values()), Decimal("0"))
    out: list[dict[str, Any]] = []
    for bucket in buckets.values():
        market_value = _decimal_value(bucket["market_value_start"])
        row = {key: float(value) if isinstance(value, Decimal) else value for key, value in bucket.items()}
        row["weight_pct"] = float(market_value / total_mv * Decimal("100")) if total_mv else 0.0
        out.append(row)
    return sorted(out, key=lambda row: -abs(float(row.get("total_return") or 0)))


def _formal_totals(rows: list[dict[str, Any]], *, enhanced: bool = False) -> dict[str, float]:
    keys = [*_formal_amount_keys(enhanced=enhanced), "market_value_start"]
    return {
        key: float(sum((_decimal_value(row.get(key)) for row in rows), Decimal("0")))
        for key in keys
    }


def _formal_bridge_to_campisi_result(
    *,
    bridge_envelope: dict[str, Any],
    positions: list[dict[str, Any]],
    start_date: date,
    end_date: date,
) -> CampisiResult:
    by_bond = _formal_bridge_bond_rows(
        bridge_envelope=bridge_envelope,
        positions=positions,
        start_date=start_date,
    )
    availability = _formal_bridge_effect_availability(by_bond, bridge_envelope=bridge_envelope)
    return CampisiResult(
        num_days=max((end_date - start_date).days, 1),
        totals=_formal_totals(by_bond),
        by_asset_class=_aggregate_formal_rows(by_bond),
        by_bond=by_bond,
        diagnostics=availability_diagnostics(availability),
        effect_availability=availability,
    )


def _formal_bridge_to_enhanced_result(
    *,
    bridge_envelope: dict[str, Any],
    positions: list[dict[str, Any]],
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    by_bond = _formal_bridge_bond_rows(
        bridge_envelope=bridge_envelope,
        positions=positions,
        start_date=start_date,
        enhanced=True,
    )
    availability = _formal_bridge_effect_availability(by_bond, enhanced=True, bridge_envelope=bridge_envelope)
    return {
        "num_days": max((end_date - start_date).days, 1),
        "totals": _formal_totals(by_bond, enhanced=True),
        "by_asset_class": _aggregate_formal_rows(by_bond, enhanced=True),
        "by_bond": by_bond,
        "diagnostics": [
            *availability_diagnostics(availability),
            BRIDGE_SECOND_ORDER_NOT_DECOMPOSED_DIAGNOSTIC,
        ],
        "effect_availability": availability,
        "basis": FORMAL_REPORT_BASIS,
        "decomposition_basis": FORMAL_BRIDGE_DECOMPOSITION_BASIS,
    }


def _formal_bridge_to_maturity_buckets(
    *,
    bridge_envelope: dict[str, Any],
    positions: list[dict[str, Any]],
    start_date: date,
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {
        label: {
            "market_value_start": 0.0,
            "income_return": 0.0,
            "treasury_effect": 0.0,
            "spread_effect": 0.0,
            "selection_effect": 0.0,
            "total_return": 0.0,
        }
        for label in _MATURITY_BUCKET_LABELS
    }
    for row in _formal_bridge_bond_rows(
        bridge_envelope=bridge_envelope,
        positions=positions,
        start_date=start_date,
    ):
        bucket_name = _text_value(row.get("maturity_bucket")) or "UNKNOWN"
        bucket = out.setdefault(
            bucket_name,
            {
                "market_value_start": 0.0,
                "income_return": 0.0,
                "treasury_effect": 0.0,
                "spread_effect": 0.0,
                "selection_effect": 0.0,
                "total_return": 0.0,
            },
        )
        for key in bucket:
            bucket[key] += float(row.get(key) or 0.0)
    return out


def _build_formal_closure(
    *,
    report_date: str,
    campisi_total_return: Decimal,
    bridge_envelope: dict[str, Any],
) -> dict[str, Any]:
    summary = (bridge_envelope.get("result") or {}).get("summary") or {}
    meta = bridge_envelope.get("result_meta") or {}
    formal_actual_pnl = _decimal_value((summary.get("total_actual_pnl") or {}).get("raw"))
    residual = formal_actual_pnl - campisi_total_return
    residual_ratio = (
        abs(residual) / abs(formal_actual_pnl)
        if formal_actual_pnl != 0
        else (Decimal("0") if residual == 0 else None)
    )
    status = "closed" if abs(residual) <= Decimal("1.00") else "warning"
    message = (
        "Campisi total return does not close to formal PnL; "
        "residual_to_formal_pnl is required."
        if status == "warning"
        else "Campisi total return closes to formal PnL."
    )
    return {
        "basis": "pnl.bridge.total_actual_pnl",
        "report_date": report_date,
        "status": status,
        "campisi_total_return": float(campisi_total_return),
        "formal_actual_pnl": float(formal_actual_pnl),
        "residual_to_formal_pnl": float(residual),
        "residual_ratio": float(residual_ratio) if residual_ratio is not None else None,
        "bridge_quality_flag": meta.get("quality_flag"),
        "bridge_vendor_status": meta.get("vendor_status"),
        "bridge_fallback_mode": meta.get("fallback_mode"),
        "bridge_fallback_date": meta.get("fallback_date"),
        "message": message,
    }


def _formal_closure_unavailable(
    *,
    report_date: str,
    campisi_total_return: Decimal,
    reason: str,
) -> dict[str, Any]:
    return {
        "basis": "pnl.bridge.total_actual_pnl",
        "report_date": report_date,
        "status": "unavailable",
        "campisi_total_return": float(campisi_total_return),
        "formal_actual_pnl": None,
        "residual_to_formal_pnl": None,
        "residual_ratio": None,
        "bridge_quality_flag": None,
        "bridge_vendor_status": None,
        "bridge_fallback_mode": None,
        "bridge_fallback_date": None,
        "message": f"Formal PnL bridge unavailable for Campisi closure: {reason}",
    }


def _fetch_formal_closure(
    *,
    settings: Any,
    report_date: str,
    campisi_total_return: Decimal,
    start_date: str | None = None,
) -> dict[str, Any]:
    try:
        bridge = _fetch_formal_bridge(settings=settings, report_date=report_date, start_date=start_date)
    except _BRIDGE_UNAVAILABLE_ERRORS as exc:
        raise_if_system_read_failure(exc)
        return _formal_closure_unavailable(
            report_date=report_date,
            campisi_total_return=campisi_total_return,
            reason=_formal_bridge_failure_reason(exc),
        )
    return _build_formal_closure(
        report_date=report_date,
        campisi_total_return=campisi_total_return,
        bridge_envelope=bridge,
    )


def _resolve_formal_closure(
    *,
    settings: Any,
    report_date: str,
    campisi_total_return: Decimal,
    bridge_envelope: dict[str, Any] | None,
    start_date: str | None = None,
) -> dict[str, Any]:
    if bridge_envelope is not None:
        return _build_formal_closure(
            report_date=report_date,
            campisi_total_return=campisi_total_return,
            bridge_envelope=bridge_envelope,
        )
    return _fetch_formal_closure(
        settings=settings,
        report_date=report_date,
        campisi_total_return=campisi_total_return,
        start_date=start_date,
    )


def _campisi_four_effects_envelope_from_state(
    *,
    state: dict[str, Any],
    settings: Any,
    formal_bridge: dict[str, Any] | None = None,
) -> dict[str, object]:
    result = deepcopy(state["result"])
    input_quality = deepcopy(state["input_quality"])
    filters = deepcopy(state["filters"])
    anchor_start = str(state["anchor_start"])
    anchor_end = str(state["anchor_end"])
    formal_closure = _resolve_formal_closure(
        settings=settings,
        report_date=anchor_end,
        start_date=anchor_start,
        campisi_total_return=Decimal(str(result.totals.get("total_return") or 0)),
        bridge_envelope=formal_bridge,
    )
    payload = _result_to_payload(result, anchor_start, anchor_end, input_quality, formal_closure)
    return build_formal_result_envelope(
        result_meta=_meta_with_quality(
            "campisi.four_effects",
            input_quality,
            formal_closure,
            filters_applied=filters,
            tables_used=TABLES_CAMPISI,
            evidence_rows=int(state["evidence_rows"]),
            as_of_date=anchor_end,
        ),
        result_payload=payload,
    )


def _result_to_payload(
    result: CampisiResult,
    start: str,
    end: str,
    input_quality: dict[str, Any] | None = None,
    formal_closure: dict[str, Any] | None = None,
    basis: str | None = None,
) -> dict[str, Any]:
    payload = {
        "report_date": end,
        "period_start": start,
        "period_end": end,
        "num_days": result.num_days,
        "totals": result.totals,
        "by_asset_class": result.by_asset_class,
        "by_bond": result.by_bond,
    }
    if basis is not None:
        payload["basis"] = basis
    if basis == FORMAL_REPORT_BASIS:
        payload["decomposition_basis"] = FORMAL_BRIDGE_DECOMPOSITION_BASIS
    if input_quality is not None:
        payload["input_quality"] = input_quality
        warnings = list(input_quality["warnings"])
        if formal_closure is not None and formal_closure.get("status") != "closed":
            warnings.append(str(formal_closure.get("message") or "Campisi formal closure warning."))
        payload["warnings"] = warnings
    if formal_closure is not None:
        payload["formal_closure"] = formal_closure
    payload["diagnostics"] = list(result.diagnostics)
    # 逐效应可用性随 payload 一起下发：totals 里的 0 单独看无法区分"观测为零"和
    # "输入缺失"，页面必须能拿到状态才能把后者渲染成"不可用"而不是一个数字。
    payload["effect_availability"] = dict(result.effect_availability)
    return payload


def _meta_with_quality(
    result_kind: str,
    input_quality: dict[str, Any],
    formal_closure: dict[str, Any] | None = None,
    *,
    upstream_meta: dict[str, Any] | None = None,
    filters_applied: dict[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    as_of_date: str | None = None,
):
    has_closure_warning = formal_closure is not None and formal_closure.get("status") != "closed"
    requested_report_date = (
        str(filters_applied["requested_end_date"])
        if filters_applied and filters_applied.get("requested_end_date")
        else None
    )
    resolved_report_date = (
        str(filters_applied["resolved_end_date"])
        if filters_applied and filters_applied.get("resolved_end_date")
        else None
    )
    report_date_fallback = bool(
        requested_report_date
        and resolved_report_date
        and requested_report_date != resolved_report_date
    )
    # 金额闭合只证明加总关系，不能清除正式桥自身的数据质量与降级状态。
    # 四效应的缓存/模型路径只保留闭合对照；使用同一份桥来源字段合并质量。
    bridge_meta = upstream_meta
    if bridge_meta is None and formal_closure is not None:
        bridge_meta = {
            key: formal_closure.get(f"bridge_{key}")
            for key in ("quality_flag", "vendor_status", "fallback_mode", "fallback_date")
        }
    quality_flags = {"warning" if input_quality["warnings"] or has_closure_warning else "ok"}
    vendor_status: VendorStatus = "ok"
    fallback_mode: FallbackMode = "latest_snapshot" if report_date_fallback else "none"
    fallback_date = resolved_report_date if report_date_fallback else None
    treasury_coverage = (input_quality.get("market_curve_coverage") or {}).get("treasury_effect") or {}
    adopted_curve_fallback_dates = [
        str(treasury_coverage[f"{side}_resolved_date"])
        for side in ("start", "end")
        if treasury_coverage.get(f"{side}_curve_used") is True
        and treasury_coverage.get(f"{side}_requested_date")
        and treasury_coverage.get(f"{side}_resolved_date")
        and treasury_coverage[f"{side}_requested_date"] != treasury_coverage[f"{side}_resolved_date"]
    ]
    if adopted_curve_fallback_dates:
        quality_flags.add("stale")
        vendor_status = "vendor_stale"
        fallback_mode = "latest_snapshot"
        # A report-date fallback has its own established meaning and takes
        # precedence. Two different curve dates cannot be compressed into one.
        if not report_date_fallback and len(set(adopted_curve_fallback_dates)) == 1:
            fallback_date = adopted_curve_fallback_dates[0]
    if bridge_meta is not None:
        bridge_quality = bridge_meta.get("quality_flag")
        bridge_vendor = bridge_meta.get("vendor_status")
        bridge_fallback = bridge_meta.get("fallback_mode")
        if bridge_quality in {"ok", "warning", "error", "stale"}:
            quality_flags.add(bridge_quality)
        else:
            quality_flags.add("warning")
        if bridge_vendor in {"vendor_stale", "vendor_unavailable"}:
            vendor_status = bridge_vendor
        elif bridge_vendor != "ok":
            quality_flags.add("warning")
        if bridge_fallback == "latest_snapshot":
            fallback_mode = "latest_snapshot"
            # 上游未给真实降级日期时保持空值；不能把业务报告日当作来源日期。
            fallback_date = bridge_meta.get("fallback_date")
        elif bridge_fallback != "none":
            quality_flags.add("warning")
        if bridge_vendor == "vendor_stale" or bridge_fallback == "latest_snapshot":
            quality_flags.add("stale")
    # 与正式 PnL 桥相同的严重程度顺序；vendor_unavailable 不被推断成 error。
    quality_flag: QualityFlag = (
        "error" if "error" in quality_flags else
        "stale" if "stale" in quality_flags else
        "warning" if "warning" in quality_flags else "ok"
    )
    if upstream_meta is not None:
        filters_applied = {
            **dict(upstream_meta.get("filters_applied") or {}),
            **dict(filters_applied or {}),
        }
    meta = build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=CACHE_VERSION,
        source_version=SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag=quality_flag,
        vendor_status=vendor_status,
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        source_surface="formal_attribution",
        requested_report_date=requested_report_date,
        resolved_report_date=resolved_report_date,
        as_of_date=as_of_date,
        fallback_mode=fallback_mode,
        fallback_date=fallback_date,
    )
    position_change = input_quality.get("position_change") or {}
    if position_change.get("status") in {"partial", "unavailable"} or input_quality.get("principal_evidence", {}).get("model_only"):
        return meta.model_copy(update={"formal_use_allowed": False})
    return meta


def _add_position_change_quality(
    input_quality: dict[str, Any], effect_availability: dict[str, Any]
) -> None:
    """Propagate model exclusions without changing the matched formal-bridge path."""
    coverage = effect_availability.get("position_change")
    if not coverage:
        return
    input_quality["position_change"] = dict(coverage)
    if coverage["status"] == "ok":
        return
    input_quality["warnings"].append(
        f"持仓变动或本金端点缺失导致 {coverage['unavailable_bonds']} 项无法进行模型归因，"
        f"已排除期初绝对市值 {coverage['unavailable_market_value_start']:.2f} 元、"
        f"期末绝对市值 {coverage['unavailable_market_value_end']:.2f} 元。"
        "收益仅覆盖可归因持仓；排除后的零值不代表完整组合零收益。"
    )


def _add_included_maturity_unavailable_quality(
    input_quality: dict[str, Any], result: CampisiResult
) -> None:
    """Disclose model-included rows whose maturity date was unusable to Campisi."""
    # The model emits UNKNOWN only when its parsed maturity is None, and it
    # appends by_bond after excluding one-sided / principal-change positions.
    included = [row for row in result.by_bond if row.get("maturity_bucket") == "UNKNOWN"]
    if not included:
        return
    market_value_start_abs = sum(
        (abs(_decimal_value(row.get("market_value_start"))) for row in included), Decimal("0")
    )
    model_residual = sum(
        (_decimal_value(row.get("selection_effect")) for row in included), Decimal("0")
    )
    input_quality["included_maturity_unavailable"] = {
        "positions": len(included),
        "market_value_start_abs": float(market_value_start_abs),
        "model_residual": float(model_residual),
    }
    input_quality["warnings"].append(
        f"模型已纳入 {len(included)} 项无法取得可用到期日的持仓，"
        f"期初绝对市值 {market_value_start_abs:.2f} 元；"
        f"其 selection_effect 合计 {model_residual:.2f} 元仅为模型剩余项，不代表选券能力。"
    )


_DECISION_EFFECT_LABELS = {
    "carry": ("票息/Carry", "自然持有收益，不直接算主动能力"),
    "rate_level_effect": ("利率水平", "市场利率 beta / 久期仓位贡献"),
    "curve_shape_effect": ("曲线形态", "期限结构策略能力代理"),
    "credit_spread_effect": ("信用利差", "信用 beta，需结合同类比较"),
    "convexity_effect": ("凸性", "二阶市场敏感性贡献"),
    "realized_trading": ("已实现交易", "交易实现贡献，不等同实名交易员评价"),
    "manual_adjustment": ("手工调整", "治理调整，不算能力"),
    "selection_proxy": ("剩余/选券代理", "组合/成本中心主动管理代理，不是交易员能力"),
    "residual_noise": ("残差/噪音", "缺曲线、估值噪音或数据质量问题，不算能力"),
}


def _empty_decision_grade_payload(start: str, end: str, warnings: list[str] | None = None) -> dict[str, Any]:
    zero_components = {key: 0.0 for key in _DECISION_EFFECT_LABELS}
    return {
        "basis": "campisi_decision_grade_v1",
        "report_date": end,
        "period_start": start,
        "period_end": end,
        "num_days": 0,
        "summary": {
            "formal_actual_pnl": 0.0,
            "explained_pnl": 0.0,
            "residual_noise": 0.0,
            "residual_ratio": None,
            "valuation_change_516": 0.0,
            "fvoci_valuation_change_516": 0.0,
            "fvtpl_valuation_change_516": 0.0,
            "main_driver": "none",
            "quality_flag": "warning",
            "bond_scope_row_count": 0,
            "out_of_scope_pnl_row_count": 0,
        },
        "formal_pnl_view": {
            "total_actual_pnl": 0.0,
            "explained_pnl": 0.0,
            "residual_noise": 0.0,
            "components": zero_components,
            # 前端契约把 closure 声明为必填并直接解引用 difference；空载分支
            # 无数据可判闭合，按"未取到正式 PnL"给 warning 而不是伪装 closed。
            "closure": {
                "status": "warning",
                "difference": 0.0,
                "difference_ratio": None,
                "basis": "fact_formal_pnl_fi.total_pnl",
                "scope": "matched_beginning_positions",
                "message": "未取到完整输入，当前不能核对已匹配期初持仓或全月债券覆盖。",
            },
        },
        "valuation_oci_view": {
            "total_valuation_change_516": 0.0,
            "fvoci_valuation_change_516": 0.0,
            "fvtpl_valuation_change_516": 0.0,
            "rows_by_accounting_basis": [],
        },
        "effects": [],
        "accounting_matrix": {},
        "ability_matrix": [],
            "residual_diagnostics": {
                "missing_curve_count": 0,
                "missing_spread_count": 0,
                "duplicate_position_keys": 0,
                "aggregated_position_groups": 0,
                "unmatched_pnl_rows": 0,
                "stale_curve_fallback_count": 0,
                "stale_curve_discarded_count": 0,
                "warnings": list(warnings or []),
        },
        "warnings": list(warnings or []),
    }


def _prior_month_end(day: str) -> str:
    return (date.fromisoformat(day).replace(day=1) - timedelta(days=1)).isoformat()


def _nearest_position_anchor(position_dates: list[str], boundary: str) -> str | None:
    """默认路径的期初持仓锚：取距上月末边界最近的持仓观测日（同距优先边界前）。

    持仓为日频时命中边界当日；但序列起点等极端情况下 on-or-before 会跳到整年前的
    孤立观测日（如 live 库 2024-01-01），把匹配范围拖到过期账本。距边界最近的观测日
    （哪怕在边界后 1 天）才是诚实的期初快照。
    """
    if not position_dates:
        return None
    boundary_day = date.fromisoformat(boundary)

    def _distance(day: str) -> tuple[int, int]:
        delta = (date.fromisoformat(day) - boundary_day).days
        return (abs(delta), 0 if delta <= 0 else 1)

    return min(position_dates, key=_distance)


def _resolve_decision_dates(
    *,
    pnl_repo: PnlRepository,
    bond_repo: BondAnalyticsRepository,
    balance_repo: BalanceAnalysisRepository,
    conn: duckdb.DuckDBPyConnection,
    start_date: str | None,
    end_date: str | None,
    lookback_days: int,
) -> tuple[str | None, str | None, str, str]:
    """解析决策评级窗口锚点。

    fact_formal_pnl_fi 的一行是 anchor_end 报告月的「月度期间 PnL」（全表 report_date
    均为月末），因此默认路径的期初必须锚定该报告月的上月末（曲线对齐到 PnL 报告月），
    而不是继承四效应路径的 lookback_days 滚动窗口——30 天滚动窗口接到月度事实表上
    会造成曲线窗口与 PnL 报告月错位（2026-02 跳月虚增 rate_level 143% 的根因）。
    显式传入 start_date 时行为与历史完全一致，lookback_days 仅在该默认推导中被忽略。
    """
    del lookback_days  # 默认窗口对齐到 PnL 报告月上月末后不再使用；保留参数以稳定 API。
    pnl_dates = pnl_repo.list_campisi_decision_pnl_report_dates(conn=conn)
    position_dates = sorted(
        set(
            bond_repo.list_campisi_decision_analytics_report_dates(conn=conn)
            + balance_repo.list_campisi_decision_zqtz_report_dates(conn=conn)
        ),
        reverse=True,
    )
    all_dates = sorted(set(pnl_dates + position_dates), reverse=True)
    rd_end = end_date or (pnl_dates[0] if pnl_dates else (all_dates[0] if all_dates else ""))
    anchor_end = (rd_end if rd_end in pnl_dates else _anchor_on_or_before(pnl_dates, rd_end)) or _anchor_on_or_before(
        all_dates,
        rd_end,
    )
    if start_date:
        rd_start = start_date
        anchor_start = _anchor_on_or_before(position_dates, rd_start)
    else:
        reference_end = anchor_end or rd_end
        rd_start = _prior_month_end(reference_end) if reference_end else ""
        eligible_dates = [d for d in position_dates if not anchor_end or d <= anchor_end]
        anchor_start = _nearest_position_anchor(eligible_dates, rd_start) if rd_start else None
    anchor_start = anchor_start or _anchor_on_or_before(position_dates, anchor_end or "")
    return anchor_start, anchor_end, rd_start, rd_end


def _decision_key(row: dict[str, Any], *, accounting_field: str, currency_field: str) -> tuple[str, str, str, str, str]:
    return (
        _text_value(row.get("instrument_code")),
        _text_value(row.get("portfolio_name")),
        _text_value(row.get("cost_center")),
        normalize_accounting_basis(row.get(accounting_field)),
        _text_value(row.get(currency_field) or row.get("currency_basis") or row.get("currency_code") or "CNY"),
    )


def _decision_loose_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _text_value(row.get("instrument_code")),
        _text_value(row.get("portfolio_name")),
        _text_value(row.get("cost_center")),
    )


def _lookup_unique(loose: dict[tuple[str, str, str], list[dict[str, Any]]], row: dict[str, Any]) -> dict[str, Any] | None:
    matches = loose.get(_decision_loose_key(row), [])
    return matches[0] if len(matches) == 1 else None


def _index_decision_rows(
    rows: list[dict[str, Any]],
    *,
    accounting_field: str,
    currency_field: str,
) -> tuple[dict[tuple[str, str, str, str, str], dict[str, Any]], dict[tuple[str, str, str], list[dict[str, Any]]]]:
    strict: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    loose: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        strict[_decision_key(row, accounting_field=accounting_field, currency_field=currency_field)] = row
        loose[_decision_loose_key(row)].append(row)
    return strict, loose


def _fetch_decision_curve(
    curve_repo: YieldCurveRepository,
    *,
    conn: duckdb.DuckDBPyConnection,
    requested_date: str,
    curve_type: str,
) -> tuple[dict[str, Decimal], str | None]:
    records, resolved = curve_repo.fetch_campisi_decision_curve_points(
        requested_date=requested_date,
        curve_type=curve_type,
        conn=conn,
    )
    curve: dict[str, Decimal] = {}
    for record in records:
        tenor = str(record["tenor"]).upper()
        try:
            curve[tenor] = _decimal_value(record.get("rate_pct"))
        except DirtyNumericInputError as exc:
            # 脏点位按缺失点位处理（不伪造 0 利率），后续缺曲线机制会计入残差并披露。
            logger.warning(
                "正式收益率曲线含脏点位，已跳过：curve_type=%s trade_date=%s tenor=%s：%s",
                curve_type,
                resolved,
                tenor,
                exc,
            )
    return curve, resolved


def _fetch_decision_curves(
    curve_repo: YieldCurveRepository,
    *,
    conn: duckdb.DuckDBPyConnection,
    anchor_start: str,
    anchor_end: str,
    start_target: str | None = None,
    end_target: str | None = None,
) -> tuple[dict[str, Any], list[str], int, dict[str, Any]]:
    """取期初/期末国债与信用曲线，并施加曲线陈旧守卫。

    start_target/end_target 是窗口目标端点（默认路径为 PnL 报告月上月末/月末，
    显式路径为解析后的锚定日期）。解析出的曲线日期偏离目标端点超过
    _DECISION_CURVE_STALENESS_THRESHOLD_DAYS 时，该侧曲线按缺失处理（走既有
    missing_treasury_curve / missing_credit_curve → residual_noise 路径）而不是静默采用。
    """
    start_target = start_target or anchor_start
    end_target = end_target or anchor_end
    warnings: list[str] = []
    fallback_count = 0
    discarded: list[dict[str, Any]] = []
    missing_treasury: list[str] = []
    max_in_use_deviation_days = 0

    def _apply_staleness_guard(
        label: str,
        curve: dict[str, Decimal],
        resolved: str | None,
        *,
        requested: str,
        target: str,
    ) -> tuple[dict[str, Decimal], str | None]:
        nonlocal fallback_count, max_in_use_deviation_days
        if not resolved:
            return {}, None
        deviation_days = abs((date.fromisoformat(resolved) - date.fromisoformat(target)).days)
        if deviation_days > _DECISION_CURVE_STALENESS_THRESHOLD_DAYS:
            discarded.append(
                {
                    "label": label,
                    "requested": requested,
                    "target": target,
                    "resolved": resolved,
                    "deviation_days": deviation_days,
                }
            )
            warnings.append(
                f"{label}解析日期 {resolved} 偏离窗口端点 {target} 达 {deviation_days} 天，"
                f"超过陈旧守卫阈值 {_DECISION_CURVE_STALENESS_THRESHOLD_DAYS} 天，"
                "按缺失处理，相关影响进入残差噪音。"
            )
            return {}, None
        max_in_use_deviation_days = max(max_in_use_deviation_days, deviation_days)
        if resolved != requested:
            fallback_count += 1
            warnings.append(f"{label}使用 {resolved} 只读 fallback，目标日期为 {requested}。")
        return curve, resolved

    treasury_start, treasury_start_date = _fetch_decision_curve(
        curve_repo,
        conn=conn,
        requested_date=anchor_start,
        curve_type="treasury",
    )
    treasury_start, treasury_start_date = _apply_staleness_guard(
        "期初国债曲线",
        treasury_start,
        treasury_start_date,
        requested=anchor_start,
        target=start_target,
    )
    treasury_end, treasury_end_date = _fetch_decision_curve(
        curve_repo,
        conn=conn,
        requested_date=anchor_end,
        curve_type="treasury",
    )
    treasury_end, treasury_end_date = _apply_staleness_guard(
        "期末国债曲线",
        treasury_end,
        treasury_end_date,
        requested=anchor_end,
        target=end_target,
    )
    for label, resolved in (
        ("期初国债曲线", treasury_start_date),
        ("期末国债曲线", treasury_end_date),
    ):
        # 守卫弃用的一侧已带"按缺失处理"披露，不再重复"缺失"文案。
        if not resolved and not any(item["label"] == label for item in discarded):
            missing_treasury.append(label)
            warnings.append(f"{label}缺失，相关利率影响进入残差噪音。")

    credit_start_by_rating: dict[str, dict[str, Decimal]] = {}
    credit_end_by_rating: dict[str, dict[str, Decimal]] = {}
    for rating, curve_type in _FORMAL_CREDIT_CURVE_TYPES.items():
        start_curve, start_resolved = _fetch_decision_curve(
            curve_repo,
            conn=conn,
            requested_date=anchor_start,
            curve_type=curve_type,
        )
        start_curve, start_resolved = _apply_staleness_guard(
            f"期初{rating}信用曲线",
            start_curve,
            start_resolved,
            requested=anchor_start,
            target=start_target,
        )
        end_curve, end_resolved = _fetch_decision_curve(
            curve_repo,
            conn=conn,
            requested_date=anchor_end,
            curve_type=curve_type,
        )
        end_curve, end_resolved = _apply_staleness_guard(
            f"期末{rating}信用曲线",
            end_curve,
            end_resolved,
            requested=anchor_end,
            target=end_target,
        )
        if start_curve:
            credit_start_by_rating[rating] = start_curve
        if end_curve:
            credit_end_by_rating[rating] = end_curve

    curve_alignment = {
        "threshold_days": _DECISION_CURVE_STALENESS_THRESHOLD_DAYS,
        "max_in_use_deviation_days": max_in_use_deviation_days,
        "discarded": discarded,
        "missing_treasury": missing_treasury,
    }
    return (
        {
            "treasury_start": treasury_start,
            "treasury_end": treasury_end,
            "credit_start_by_rating": credit_start_by_rating,
            "credit_end_by_rating": credit_end_by_rating,
        },
        warnings,
        fallback_count,
        curve_alignment,
    )


def _fetch_decision_risk_tensor_check(
    risk_repo: RiskTensorRepository,
    *,
    conn: duckdb.DuckDBPyConnection,
    report_date: str,
    component_dv01: Decimal,
    component_cs01: Decimal,
) -> dict[str, Any]:
    table_available, rows = risk_repo.fetch_campisi_decision_risk_tensor_aggregate(
        report_date,
        conn=conn,
    )
    if not table_available:
        return {
            "available": False,
            "message": "fact_formal_risk_tensor_daily 不可用，无法做组合级 DV01/CS01 校验。",
        }
    row = rows[0] if rows else {}
    portfolio_dv01 = _decimal_value(row.get("portfolio_dv01"))
    cs01 = _decimal_value(row.get("cs01"))
    return {
        "available": bool(rows),
        "portfolio_dv01": float(portfolio_dv01),
        "component_dv01": float(component_dv01),
        "dv01_difference": float(component_dv01 - portfolio_dv01),
        "portfolio_cs01": float(cs01),
        "component_cs01": float(component_cs01),
        "cs01_difference": float(component_cs01 - cs01),
        "quality_flag": row.get("quality_flag") or "unknown",
        "total_market_value": float(_decimal_value(row.get("total_market_value"))),
        "bond_count": int(_decimal_value(row.get("bond_count"))),
    }


def _decision_float_components(components: dict[str, Decimal]) -> dict[str, float]:
    return {key: float(components.get(key, Decimal("0"))) for key in _DECISION_EFFECT_LABELS}


def _decision_residual_ratio(
    *,
    formal_actual_pnl: Decimal,
    residual_noise: Decimal,
) -> float | None:
    # Human: caliber-formal_scenario_gate-justified -- numeric zero-guard on a PnL
    # amount (avoids division by zero / misleading 0 ratio); not a basis/view gate.
    if formal_actual_pnl == Decimal("0"):
        return 0.0 if residual_noise == Decimal("0") else None
    return float(abs(residual_noise) / abs(formal_actual_pnl))


def _decision_pnl_closure(
    *,
    explained_pnl: Decimal,
    formal_actual_pnl: Decimal,
) -> dict[str, Any]:
    """正式 PnL 真实闭合判定。

    explained_pnl 已排除 selection_proxy/residual_noise 两个平衡项，因此
    difference = actual - explained 就是未被固定因子解释的缺口，可真实判为未闭合。
    分级采用绝对阈值 + 相对阈值组合，与项目 quality_flag(ok/warning/error) 的分级理念一致。
    """
    difference = formal_actual_pnl - explained_pnl
    abs_difference = abs(difference)
    # Human: caliber-formal_scenario_gate-justified -- numeric zero-guard on a PnL
    # amount (avoids division by zero / misleading 0 ratio); not a basis/view gate.
    if formal_actual_pnl == Decimal("0"):
        difference_ratio: float | None = 0.0 if abs_difference == Decimal("0") else None
    else:
        difference_ratio = float(abs_difference / abs(formal_actual_pnl))

    if abs_difference <= Decimal("0.01"):
        status = "closed"
    elif difference_ratio is not None and difference_ratio <= 0.05:
        status = "closed"
    elif difference_ratio is not None and difference_ratio <= 0.10:
        status = "warning"
    else:
        status = "error"

    return {
        "status": status,
        "difference": float(difference),
        "difference_ratio": difference_ratio,
        "basis": "fact_formal_pnl_fi.total_pnl",
        "scope": "matched_beginning_positions",
        "message": "仅核对已匹配期初持仓内部的固定因子解释闭合；闭合状态不代表全月全部债券已核对。",
    }


def _decision_closure_warning(closure: dict[str, Any]) -> str:
    ratio = closure.get("difference_ratio")
    ratio_text = f"{float(ratio) * 100:.2f}%" if isinstance(ratio, (int, float)) else "无法归一化"
    return (
        f"正式 PnL 未闭合（closure={closure.get('status')}）：固定因子未解释缺口 "
        f"{float(closure.get('difference') or 0.0):.2f} 元，占正式 PnL {ratio_text}；"
        "缺口已落入 selection_proxy/residual_noise，不得解读为主动管理能力。"
    )


def _decision_quality_flag(
    *,
    warnings: list[str],
    residual_noise: Decimal,
    closure_status: str,
) -> QualityFlag:
    """closure 分级必须上抛：缺口只落在 selection_proxy 时 residual_noise 仍为 0。

    与 `_result_to_payload`/`_meta_with_quality` 对四效应 formal_closure 的处理同调：
    closure 未闭合即降级质量信号，error 级不被其他 warning 稀释。
    """
    if closure_status == "error":
        return "error"
    if warnings or abs(residual_noise) > Decimal("0.01") or closure_status == "warning":
        return "warning"
    return "ok"


def _decision_effect_rows(components: dict[str, Decimal]) -> list[dict[str, Any]]:
    rows = []
    for key, amount in components.items():
        label, ability_treatment = _DECISION_EFFECT_LABELS[key]
        rows.append(
            {
                "key": key,
                "label": label,
                "amount": float(amount),
                "ability_treatment": ability_treatment,
            }
        )
    return rows


def _accounting_interpretation(accounting_basis: str) -> str:
    if accounting_basis == ACCOUNTING_BASIS_AC:
        return "主要看票息/摊余成本收益；公允价值变动不作为本视图核心解释项。"
    if accounting_basis == ACCOUNTING_BASIS_FVOCI:
        return "516 不进入正式 PnL，但进入估值/OCI 解释视图。"
    if accounting_basis == ACCOUNTING_BASIS_FVTPL:
        return "516 进入正式 PnL，也进入估值解释视图。"
    return "会计分类未标准化，需结合源数据确认。"


def _decision_ability_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (_text_value(row.get("portfolio_name")) or "未分组合", _text_value(row.get("cost_center")) or "未分成本中心")
        bucket = grouped.setdefault(
            key,
            {
                "portfolio_name": key[0],
                "cost_center": key[1],
                "carry": Decimal("0"),
                "market_beta": Decimal("0"),
                "strategy_proxy": Decimal("0"),
                "credit_proxy": Decimal("0"),
                "selection_proxy": Decimal("0"),
                "residual_noise": Decimal("0"),
                "total_actual_pnl": Decimal("0"),
                "warnings": [],
            },
        )
        components = row["components"]
        bucket["carry"] += components["carry"]
        bucket["market_beta"] += (
            components["rate_level_effect"]
            + components["credit_spread_effect"]
            + components["convexity_effect"]
        )
        bucket["strategy_proxy"] += components["curve_shape_effect"]
        bucket["credit_proxy"] += components["credit_spread_effect"]
        bucket["selection_proxy"] += components["selection_proxy"]
        bucket["residual_noise"] += components["residual_noise"]
        bucket["total_actual_pnl"] += row["actual_pnl"]
        bucket["warnings"].extend(row.get("diagnostics") or [])

    out: list[dict[str, Any]] = []
    for bucket in grouped.values():
        residual = bucket["residual_noise"]
        confidence = "low" if abs(residual) > Decimal("0.01") or bucket["warnings"] else "medium"
        out.append(
            {
                "portfolio_name": bucket["portfolio_name"],
                "cost_center": bucket["cost_center"],
                "carry": float(bucket["carry"]),
                "market_beta": float(bucket["market_beta"]),
                "strategy_proxy": float(bucket["strategy_proxy"]),
                "credit_proxy": float(bucket["credit_proxy"]),
                "selection_proxy": float(bucket["selection_proxy"]),
                "residual_noise": float(bucket["residual_noise"]),
                "total_actual_pnl": float(bucket["total_actual_pnl"]),
                "confidence": confidence,
                "notes": "组合/成本中心代理，不是实名交易员评价；票息和残差不算主动能力。",
            }
        )
    return sorted(out, key=lambda item: abs(float(item["total_actual_pnl"])), reverse=True)


def campisi_decision_grade_envelope(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    lookback_days: int = 30,
) -> dict[str, object]:
    settings = get_settings()
    filters: dict[str, object] = {
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "lookback_days": lookback_days,
        "scope": "matched_beginning_positions",
        "scope_decision_status": "PENDING",
    }
    duckdb_path = str(settings.duckdb_path)
    pnl_repo = PnlRepository(duckdb_path)
    bond_repo = BondAnalyticsRepository(duckdb_path)
    balance_repo = BalanceAnalysisRepository(duckdb_path)
    curve_repo = YieldCurveRepository(duckdb_path)
    risk_repo = RiskTensorRepository(duckdb_path)

    try:
        with read_only_connection(duckdb_path) as conn:
            anchor_start, anchor_end, rd_start, rd_end = _resolve_decision_dates(
                pnl_repo=pnl_repo,
                bond_repo=bond_repo,
                balance_repo=balance_repo,
                conn=conn,
                start_date=start_date,
                end_date=end_date,
                lookback_days=lookback_days,
            )
            filters.update(
                {
                    "resolved_start_date": anchor_start,
                    "resolved_end_date": anchor_end,
                }
            )
            if not anchor_start or not anchor_end:
                payload = _empty_decision_grade_payload(rd_start, rd_end, ["缺少正式 PnL 或债券持仓/analytics 日期。"])
                return build_formal_result_envelope(
                    result_meta=_meta_warn(
                        "campisi.decision_grade",
                        filters_applied=filters,
                        tables_used=TABLES_CAMPISI_DECISION_GRADE,
                        evidence_rows=0,
                        as_of_date=anchor_end,
                    ),
                    result_payload=payload,
                )

            # 窗口声明必须在空值守卫之后：anchor_* 为空时 date.fromisoformat 会抛
            # ValueError，绕过下方的优雅空载分支并冒泡成 HTTP 500。
            pnl_window, curve_window, window_span_days = _decision_window_declarations(
                anchor_start=anchor_start,
                anchor_end=anchor_end,
            )
            filters.update({"pnl_window": pnl_window, "curve_window": curve_window})

            pnl_rows = pnl_repo.fetch_campisi_decision_pnl_rows(anchor_end, conn=conn)
            analytics_rows = bond_repo.fetch_campisi_decision_analytics_rows(anchor_start, conn=conn)
            balance_rows = balance_repo.fetch_campisi_decision_balance_rows(anchor_start, conn=conn)
            analytics_by_key, analytics_loose = _index_decision_rows(
                analytics_rows,
                accounting_field="accounting_class",
                currency_field="currency_code",
            )
            balance_by_key, balance_loose = _index_decision_rows(
                balance_rows,
                accounting_field="accounting_basis",
                currency_field="currency_code",
            )
            # 陈旧守卫的窗口目标端点：默认路径为 PnL 报告月上月末（rd_start 由
            # _resolve_decision_dates 推导），显式路径尊重调用方声明的窗口（锚定日期）。
            curve_start_target = rd_start if start_date is None else anchor_start
            curves, curve_warnings, stale_curve_fallback_count, curve_alignment = _fetch_decision_curves(
                curve_repo,
                conn=conn,
                anchor_start=anchor_start,
                anchor_end=anchor_end,
                start_target=curve_start_target,
                end_target=anchor_end,
            )

            computed_rows: list[dict[str, Any]] = []
            warnings: list[str] = list(curve_warnings)
            window_disclosure = _decision_window_disclosure(
                pnl_window=pnl_window,
                curve_window=curve_window,
                num_days=window_span_days,
                curve_alignment=curve_alignment,
            )
            if window_disclosure is not None and window_disclosure["level"] == "warning":
                warnings.append(window_disclosure["message"])
            out_of_scope_rows = 0
            matched_pnl_rows: list[dict[str, Any]] = []
            unmatched_pnl_rows: list[dict[str, Any]] = []
            dirty_input_rows = 0
            duplicate_position_keys = 0
            aggregated_position_groups = 0
            accounting_matrix: dict[str, dict[str, Any]] = {}

            for pnl_row in pnl_rows:
                strict_key = _decision_key(
                    pnl_row,
                    accounting_field="accounting_basis",
                    currency_field="currency_basis",
                )
                analytics = analytics_by_key.get(strict_key) or _lookup_unique(analytics_loose, pnl_row)
                balance = balance_by_key.get(strict_key) or _lookup_unique(balance_loose, pnl_row)
                if analytics is None and balance is None:
                    out_of_scope_rows += 1
                    unmatched_pnl_rows.append(pnl_row)
                    continue
                matched_pnl_rows.append(pnl_row)

                accounting_basis = normalize_accounting_basis(pnl_row.get("accounting_basis"))
                try:
                    row_formal_pnl = _decimal_value(pnl_row.get("total_pnl"))
                    row_valuation_516 = _decimal_value(pnl_row.get("fair_value_change_516"))
                    duplicate_key = (
                        _decimal_value((analytics or {}).get("source_row_count")) > 1
                        or _decimal_value((balance or {}).get("source_row_count")) > 1
                    )
                    market_value = (analytics or {}).get("market_value")
                    market_value_source = "bond_analytics"
                    market_value_coverage = (analytics or {}).get("market_value_coverage_ratio")
                    if _is_missing(market_value):
                        market_value = (balance or {}).get("market_value_amount")
                        market_value_coverage = (balance or {}).get("market_value_coverage_ratio")
                        market_value_source = "missing" if _is_missing(market_value) else "formal_balance"
                    row_input = {
                        "actual_pnl": pnl_row.get("total_pnl"),
                        "carry": pnl_row.get("interest_income_514"),
                        "realized_trading": pnl_row.get("capital_gain_517"),
                        "manual_adjustment": pnl_row.get("manual_adjustment"),
                        "market_value": market_value,
                        "market_value_coverage_ratio": market_value_coverage,
                        "modified_duration": (analytics or {}).get("modified_duration"),
                        **{f"{field}_coverage_ratio": (analytics or {}).get(f"{field}_coverage_ratio") for field in ("modified_duration", "convexity", "years_to_maturity", "spread_dv01")},
                        "convexity": (analytics or {}).get("convexity"),
                        "spread_dv01": (analytics or {}).get("spread_dv01"),
                        "years_to_maturity": (analytics or balance or {}).get("years_to_maturity"),
                        "rating": (analytics or balance or {}).get("rating"),
                        "is_credit": bool((analytics or {}).get("is_credit"))
                        or "credit" in _text_value((analytics or balance or {}).get("asset_class_std") or (balance or {}).get("asset_class")).lower(),
                        "duplicate_position_key": duplicate_key,
                        "duplicate_position_key_is_ambiguous": False,
                        "missing_analytics": analytics is None,
                        "include_market_effects_in_formal_pnl": accounting_basis == ACCOUNTING_BASIS_FVTPL,
                    }
                    computed = compute_decision_grade_row(
                        row_input,
                        treasury_start=curves["treasury_start"],
                        treasury_end=curves["treasury_end"],
                        credit_start_by_rating=curves["credit_start_by_rating"],
                        credit_end_by_rating=curves["credit_end_by_rating"],
                    )
                    row_market_value = campisi_decision_decimal(market_value)
                except DirtyNumericInputError as exc:
                    # 脏输入行不得静默变 0 计入总额：整行跳过并显式披露。
                    dirty_input_rows += 1
                    logger.warning(
                        "Campisi 决策评级行含脏数值输入，已跳过：instrument=%s portfolio=%s cost_center=%s：%s",
                        pnl_row.get("instrument_code"),
                        pnl_row.get("portfolio_name"),
                        pnl_row.get("cost_center"),
                        exc,
                    )
                    warnings.append(
                        f"PnL 明细行含脏数值输入，已跳过且不计入决策评级总额"
                        f"（{_text_value(pnl_row.get('instrument_code')) or 'unknown'}）：{exc}"
                    )
                    continue

                if duplicate_key:
                    aggregated_position_groups += 1
                matrix_row = accounting_matrix.setdefault(
                    accounting_basis,
                    {
                        "accounting_basis": accounting_basis,
                        "formal_pnl": Decimal("0"),
                        "valuation_or_oci_516": Decimal("0"),
                        "interpretation": _accounting_interpretation(accounting_basis),
                    },
                )
                matrix_row["formal_pnl"] += row_formal_pnl
                matrix_row["valuation_or_oci_516"] += row_valuation_516
                computed.update(
                    {
                        "instrument_code": pnl_row.get("instrument_code"),
                        "portfolio_name": pnl_row.get("portfolio_name"),
                        "cost_center": pnl_row.get("cost_center"),
                        "accounting_basis": accounting_basis,
                        "fair_value_change_516": row_valuation_516,
                        "market_value": row_market_value,
                        "market_value_source": market_value_source,
                    }
                )
                warnings.extend(computed.get("diagnostics") or [])
                computed_rows.append(computed)

            totals = {key: Decimal("0") for key in _DECISION_EFFECT_LABELS}
            formal_actual_pnl = Decimal("0")
            explained_pnl = Decimal("0")
            valuation_total = Decimal("0")
            fvoci_valuation = Decimal("0")
            fvtpl_valuation = Decimal("0")
            component_dv01 = Decimal("0")
            component_cs01 = Decimal("0")
            missing_curve_count = 0
            missing_spread_count = 0
            for row in computed_rows:
                formal_actual_pnl += row["actual_pnl"]
                explained_pnl += row["explained_pnl"]
                valuation = row["fair_value_change_516"]
                valuation_total += valuation
                if row["accounting_basis"] == ACCOUNTING_BASIS_FVOCI:
                    fvoci_valuation += valuation
                if row["accounting_basis"] == ACCOUNTING_BASIS_FVTPL:
                    fvtpl_valuation += valuation
                for key in totals:
                    totals[key] += row["components"][key]
                reasons = set(row.get("residual_reasons") or [])
                if {"missing_treasury_curve", "missing_convexity_curve"} & reasons:
                    missing_curve_count += 1
                if "missing_credit_curve" in reasons:
                    missing_spread_count += 1

            for row in analytics_rows:
                try:
                    row_dv01 = _decimal_value(row.get("dv01"))
                    row_cs01 = _decimal_value(row.get("spread_dv01"))
                except DirtyNumericInputError as exc:
                    logger.warning(
                        "Campisi 决策评级 analytics 行 DV01/CS01 含脏数值输入，已跳过：instrument=%s：%s",
                        row.get("instrument_code"),
                        exc,
                    )
                    warnings.append(
                        f"analytics 行 DV01/CS01 含脏数值输入，已跳过该行贡献"
                        f"（{_text_value(row.get('instrument_code')) or 'unknown'}）：{exc}"
                    )
                    continue
                component_dv01 += row_dv01
                component_cs01 += row_cs01

            scope_disclosure = compute_decision_scope_disclosure(pnl_rows, matched_pnl_rows, unmatched_pnl_rows, computed_rows)
            if unmatched_pnl_rows:
                warnings.append(scope_disclosure["message"])
            residual_noise = totals["residual_noise"]
            residual_ratio = _decision_residual_ratio(
                formal_actual_pnl=formal_actual_pnl,
                residual_noise=residual_noise,
            )
            pnl_closure = _decision_pnl_closure(
                explained_pnl=explained_pnl,
                formal_actual_pnl=formal_actual_pnl,
            )
            closure_status = str(pnl_closure["status"])
            if closure_status != "closed":
                warnings.append(_decision_closure_warning(pnl_closure))
            quality_flag = _decision_quality_flag(
                warnings=warnings,
                residual_noise=residual_noise,
                closure_status=closure_status,
            )
            risk_tensor_check = _fetch_decision_risk_tensor_check(
                risk_repo,
                conn=conn,
                report_date=anchor_end,
                component_dv01=component_dv01,
                component_cs01=component_cs01,
            )

            rows_by_accounting = []
            accounting_matrix_json: dict[str, dict[str, Any]] = {}
            for accounting_basis, row in sorted(accounting_matrix.items()):
                formatted = {
                    "accounting_basis": accounting_basis,
                    "formal_pnl": float(row["formal_pnl"]),
                    "valuation_or_oci_516": float(row["valuation_or_oci_516"]),
                    "interpretation": row["interpretation"],
                }
                rows_by_accounting.append(formatted)
                accounting_matrix_json[accounting_basis] = formatted

            payload = {
                "basis": "campisi_decision_grade_v1",
                "scope_disclosure": scope_disclosure,
                "report_date": anchor_end,
                "period_start": anchor_start,
                "period_end": anchor_end,
                "num_days": window_span_days,
                "pnl_window": pnl_window,
                "curve_window": curve_window,
                "window_disclosure": window_disclosure,
                "summary": {
                    "formal_actual_pnl": float(formal_actual_pnl),
                    "explained_pnl": float(explained_pnl),
                    "residual_noise": float(residual_noise),
                    "residual_ratio": residual_ratio,
                    "valuation_change_516": float(valuation_total),
                    "fvoci_valuation_change_516": float(fvoci_valuation),
                    "fvtpl_valuation_change_516": float(fvtpl_valuation),
                    "main_driver": primary_driver(totals),
                    "quality_flag": quality_flag,
                    "bond_scope_row_count": len(computed_rows),
                    "out_of_scope_pnl_row_count": out_of_scope_rows,
                },
                "formal_pnl_view": {
                    "total_actual_pnl": float(formal_actual_pnl),
                    "explained_pnl": float(explained_pnl),
                    "residual_noise": float(residual_noise),
                    "components": _decision_float_components(totals),
                    "closure": pnl_closure,
                },
                "valuation_oci_view": {
                    "total_valuation_change_516": float(valuation_total),
                    "fvoci_valuation_change_516": float(fvoci_valuation),
                    "fvtpl_valuation_change_516": float(fvtpl_valuation),
                    "rows_by_accounting_basis": rows_by_accounting,
                    "reinvestment": {
                        "implemented": False,
                        "message": "数据源不足：缺少稳定短端再投资数据，v1 不伪造为 0 贡献。",
                    },
                },
                "effects": _decision_effect_rows(totals),
                "accounting_matrix": accounting_matrix_json,
                "ability_matrix": _decision_ability_matrix(computed_rows),
                "risk_tensor_check": risk_tensor_check,
                "residual_diagnostics": {
                    "market_value_source_counts": {
                        source: sum(row.get("market_value_source") == source for row in computed_rows)
                        for source in ("bond_analytics", "formal_balance", "missing")
                    },
                    "missing_curve_count": missing_curve_count,
                    "missing_spread_count": missing_spread_count,
                    "duplicate_position_keys": duplicate_position_keys,
                    "aggregated_position_groups": aggregated_position_groups,
                    "unmatched_pnl_rows": out_of_scope_rows,
                    "dirty_input_row_count": dirty_input_rows,
                    "stale_curve_fallback_count": stale_curve_fallback_count,
                    "stale_curve_discarded_count": len(curve_alignment["discarded"]),
                    "warnings": sorted(set(warnings)),
                },
                "warnings": sorted(set(warnings)),
                "method_notes": [
                    "carry = interest_income_514。",
                    "FVOCI 的 516 不进入正式 PnL，但进入估值/OCI 解释视图。",
                    "selection_proxy 是组合/成本中心代理指标，不是实名交易员能力。",
                    "residual_noise 专门承接缺曲线、重复 key、估值噪音和数据质量问题。",
                ],
            }
            report_date_fallback = bool(end_date and anchor_end != end_date)
            return build_formal_result_envelope(
                result_meta=build_formal_result_meta(
                    trace_id=_trace_id(),
                    result_kind="campisi.decision_grade",
                    cache_version=DECISION_CACHE_VERSION,
                    source_version=SOURCE_VERSION,
                    rule_version=DECISION_RULE_VERSION,
                    quality_flag=quality_flag,
                    # 守卫弃用（discarded）的曲线虽未被采用，但反映供应商数据同样陈旧。
                    vendor_status=(
                        "vendor_stale"
                        if stale_curve_fallback_count or curve_alignment["discarded"]
                        else "ok"
                    ),
                    fallback_mode=(
                        "latest_snapshot"
                        if stale_curve_fallback_count or report_date_fallback
                        else "none"
                    ),
                    filters_applied=filters,
                    tables_used=TABLES_CAMPISI_DECISION_GRADE,
                    evidence_rows=len(pnl_rows) + len(analytics_rows) + len(balance_rows),
                    source_surface="formal_attribution",
                    requested_report_date=end_date,
                    resolved_report_date=anchor_end,
                    as_of_date=anchor_end,
                    fallback_date=anchor_end if report_date_fallback else None,
                ),
                result_payload=payload,
            )
    except (OSError, duckdb.Error) as exc:
        payload = _empty_decision_grade_payload("", "", [f"DuckDB 只读连接失败：{exc}"])
        return build_formal_result_envelope(
            result_meta=_meta_warn(
                "campisi.decision_grade",
                filters_applied=filters,
                tables_used=TABLES_CAMPISI_DECISION_GRADE,
                evidence_rows=0,
            ),
            result_payload=payload,
        )


def campisi_four_effects_envelope(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    lookback_days: int = 30,
) -> dict[str, object]:
    """Campisi 四效应归因（income/treasury/spread/selection）。

    WP-A2: 在原有 state/bridge 缓存前面加一层进程内 envelope 缓存；命中路径不再
    触发 repo 扫描、市场曲线拉取、campisi.py 计算或 envelope 重建，也不做大结构
    deepcopy。key 覆盖归一化的请求参数 + DuckDB 存储指纹 + 治理桥依赖指纹，任一
    输入变化都会失效；缺少指纹时自动降级为原计算路径。
    """
    settings = get_settings()
    duckdb_fingerprint = _duckdb_storage_fingerprint(settings.duckdb_path)
    governance_fingerprint = _selected_files_fingerprint(
        settings.governance_path, _GOVERNANCE_BRIDGE_DEPENDENCY_FILES,
    )
    envelope_cache_key = _campisi_four_effects_envelope_cache_key(
        detail="full",
        duckdb_path=settings.duckdb_path,
        governance_path=settings.governance_path,
        duckdb_fingerprint=duckdb_fingerprint,
        governance_fingerprint=governance_fingerprint,
        requested_start_date=start_date,
        requested_end_date=end_date,
        lookback_days=lookback_days,
    )
    if envelope_cache_key is None:
        return _campisi_four_effects_envelope_compute(
            start_date=start_date,
            end_date=end_date,
            lookback_days=lookback_days,
        )
    cached = _CAMPISI_FOUR_EFFECTS_ENVELOPE_CACHE.get_or_set(
        envelope_cache_key,
        lambda: _campisi_four_effects_envelope_compute(
            start_date=start_date,
            end_date=end_date,
            lookback_days=lookback_days,
        ),
    )
    return _campisi_envelope_with_fresh_trace(cached)


def _campisi_four_effects_envelope_compute(
    *,
    start_date: str | None,
    end_date: str | None,
    lookback_days: int,
) -> dict[str, object]:
    settings = get_settings()
    bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
    curve_repo = YieldCurveRepository(str(settings.duckdb_path))
    dates = bond_repo.list_report_dates()

    if not dates:
        payload = _empty_campisi_payload("", "")
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.four_effects"),
            result_payload=payload,
        )

    rd_end = end_date or dates[0]
    if start_date:
        rd_start = start_date
    else:
        rd_start = (date.fromisoformat(rd_end) - timedelta(days=max(1, lookback_days))).isoformat()

    anchor_start = _anchor_on_or_before(dates, rd_start)
    anchor_end = rd_end if rd_end in dates else _anchor_on_or_before(dates, rd_end)

    if not anchor_start or not anchor_end:
        payload = _empty_campisi_payload(rd_start, rd_end)
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.four_effects"),
            result_payload=payload,
        )

    duckdb_fingerprint = _duckdb_storage_fingerprint(settings.duckdb_path)
    cache_key = _campisi_four_effects_cache_key(
        duckdb_path=settings.duckdb_path,
        duckdb_fingerprint=duckdb_fingerprint,
        requested_start_date=start_date,
        requested_end_date=end_date,
        resolved_start_date=anchor_start,
        resolved_end_date=anchor_end,
        lookback_days=lookback_days,
    )

    rows_start = bond_repo.fetch_bond_analytics_rows(report_date=anchor_start)
    rows_end = bond_repo.fetch_bond_analytics_rows(report_date=anchor_end)
    positions = _merge_positions(rows_start, rows_end)
    input_quality = _build_input_quality(rows_start=rows_start, rows_end=rows_end, positions=positions)
    filters: dict[str, object] = {
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "resolved_start_date": anchor_start,
        "resolved_end_date": anchor_end,
        "lookback_days": lookback_days,
    }
    evidence_rows = len(rows_start) + len(rows_end)

    if not positions:
        payload = _empty_campisi_payload(anchor_start, anchor_end)
        envelope = build_formal_result_envelope(
            result_meta=_meta_warn(
                "campisi.four_effects",
                source_version=SOURCE_VERSION if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload=payload,
        )
        return envelope

    formal_bridge = _try_fetch_cached_formal_bridge(
        settings=settings,
        report_date=anchor_end,
        duckdb_fingerprint=duckdb_fingerprint,
        start_date=anchor_start,
        warnings=input_quality["warnings"],
    )
    if formal_bridge is not None and _formal_bridge_has_position_overlap(formal_bridge, positions):
        result = _formal_bridge_to_campisi_result(
            bridge_envelope=formal_bridge,
            positions=positions,
            start_date=date.fromisoformat(anchor_start),
            end_date=date.fromisoformat(anchor_end),
        )
        _add_formal_bridge_coverage(
            input_quality, bridge_envelope=formal_bridge, attributed_rows=len(result.by_bond),
        )
        formal_closure = _build_formal_closure(
            report_date=anchor_end,
            campisi_total_return=Decimal(str(result.totals.get("total_return") or 0)),
            bridge_envelope=formal_bridge,
        )
        payload = _result_to_payload(
            result,
            anchor_start,
            anchor_end,
            input_quality,
            formal_closure,
            basis=FORMAL_REPORT_BASIS,
        )
        envelope = build_formal_result_envelope(
            result_meta=_meta_with_quality(
                "campisi.four_effects",
                input_quality,
                formal_closure,
                upstream_meta=formal_bridge.get("result_meta") or {},
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload=payload,
        )
        return envelope

    cached_state = _get_cached_campisi_four_effects_state(cache_key)
    if cached_state is not None:
        return _campisi_four_effects_envelope_from_state(
            state=cached_state,
            settings=settings,
            formal_bridge=formal_bridge,
        )

    _attach_native_principal_evidence(positions, bond_repo, anchor_start, anchor_end, input_quality)

    treasury_start, treasury_start_present, treasury_start_resolved, treasury_start_used = (
        _fetch_treasury_market_dict(curve_repo, anchor_start)
    )
    treasury_end, treasury_end_present, treasury_end_resolved, treasury_end_used = (
        _fetch_treasury_market_dict(curve_repo, anchor_end)
    )
    spread_start = fetch_credit_spread_market(curve_repo, anchor_start)
    spread_end = fetch_credit_spread_market(curve_repo, anchor_end)
    market_start = {**treasury_start, **spread_start}
    market_end = {**treasury_end, **spread_end}
    _add_market_curve_quality(
        input_quality,
        positions=positions,
        market_start=market_start,
        market_end=market_end,
        start_curve_rows_present=treasury_start_present,
        end_curve_rows_present=treasury_end_present,
        start_requested_date=anchor_start,
        start_resolved_date=treasury_start_resolved,
        end_requested_date=anchor_end,
        end_resolved_date=treasury_end_resolved,
        start_curve_used=treasury_start_used,
        end_curve_used=treasury_end_used,
    )

    result = campisi_attribution(
        positions_merged=positions,
        market_start=market_start,
        market_end=market_end,
        start_date=date.fromisoformat(anchor_start),
        end_date=date.fromisoformat(anchor_end),
    )
    _add_position_change_quality(input_quality, result.effect_availability)
    _add_included_maturity_unavailable_quality(input_quality, result)
    if result.diagnostics:
        input_quality["warnings"] = [*input_quality["warnings"], *result.diagnostics]

    _set_cached_campisi_four_effects_state(
        cache_key,
        {
            "result": result,
            "input_quality": input_quality,
            "filters": filters,
            "anchor_start": anchor_start,
            "anchor_end": anchor_end,
            "evidence_rows": evidence_rows,
        },
    )
    return _campisi_four_effects_envelope_from_state(
        state={
            "result": result,
            "input_quality": input_quality,
            "filters": filters,
            "anchor_start": anchor_start,
            "anchor_end": anchor_end,
            "evidence_rows": evidence_rows,
        },
        settings=settings,
        formal_bridge=formal_bridge,
    )


def _project_campisi_four_effects_summary(envelope: dict[str, object]) -> dict[str, object]:
    result = envelope.get("result")
    if not isinstance(result, dict):
        return envelope
    return {
        **envelope,
        "result": {
            **result,
            "by_bond": [],
        },
    }


def campisi_four_effects_summary_envelope(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    lookback_days: int = 30,
) -> dict[str, object]:
    """四效应 summary 投影：在完整（可能命中缓存的）envelope 之后置空 by_bond。

    不改动计算逻辑、缓存键或 meta；除 by_bond 外与 full 结果逐字段一致。
    WP-A2: summary 使用独立的 envelope cache key（detail=summary），与 full 互
    不串用；缓存的投影结构本身很轻，命中路径同样只做浅拷贝并刷新 trace_id。
    """
    settings = get_settings()
    duckdb_fingerprint = _duckdb_storage_fingerprint(settings.duckdb_path)
    governance_fingerprint = _selected_files_fingerprint(
        settings.governance_path, _GOVERNANCE_BRIDGE_DEPENDENCY_FILES,
    )
    envelope_cache_key = _campisi_four_effects_envelope_cache_key(
        detail="summary",
        duckdb_path=settings.duckdb_path,
        governance_path=settings.governance_path,
        duckdb_fingerprint=duckdb_fingerprint,
        governance_fingerprint=governance_fingerprint,
        requested_start_date=start_date,
        requested_end_date=end_date,
        lookback_days=lookback_days,
    )
    if envelope_cache_key is None:
        return _project_campisi_four_effects_summary(
            campisi_four_effects_envelope(
                start_date=start_date,
                end_date=end_date,
                lookback_days=lookback_days,
            )
        )
    cached = _CAMPISI_FOUR_EFFECTS_ENVELOPE_CACHE.get_or_set(
        envelope_cache_key,
        lambda: _project_campisi_four_effects_summary(
            campisi_four_effects_envelope(
                start_date=start_date,
                end_date=end_date,
                lookback_days=lookback_days,
            )
        ),
    )
    return _campisi_envelope_with_fresh_trace(cached)


def campisi_enhanced_envelope(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    lookback_days: int = 30,
) -> dict[str, object]:
    """Campisi 六效应归因（+ convexity/cross/reinvestment）。"""
    settings = get_settings()
    bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
    curve_repo = YieldCurveRepository(str(settings.duckdb_path))
    dates = bond_repo.list_report_dates()

    if not dates:
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.enhanced"),
            result_payload=_empty_campisi_payload("", ""),
        )

    rd_end = end_date or dates[0]
    rd_start = start_date or (date.fromisoformat(rd_end) - timedelta(days=max(1, lookback_days))).isoformat()
    anchor_start = _anchor_on_or_before(dates, rd_start)
    anchor_end = rd_end if rd_end in dates else _anchor_on_or_before(dates, rd_end)

    if not anchor_start or not anchor_end:
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.enhanced"),
            result_payload=_empty_campisi_payload(rd_start, rd_end),
        )

    rows_start = bond_repo.fetch_bond_analytics_rows(report_date=anchor_start)
    rows_end = bond_repo.fetch_bond_analytics_rows(report_date=anchor_end)
    positions = _merge_positions(rows_start, rows_end)
    input_quality = _build_input_quality(rows_start=rows_start, rows_end=rows_end, positions=positions)
    filters: dict[str, object] = {
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "resolved_start_date": anchor_start,
        "resolved_end_date": anchor_end,
        "lookback_days": lookback_days,
    }
    evidence_rows = len(rows_start) + len(rows_end)

    if not positions:
        return build_formal_result_envelope(
            result_meta=_meta_warn(
                "campisi.enhanced",
                source_version=SOURCE_VERSION if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload=_empty_campisi_payload(anchor_start, anchor_end),
        )

    formal_bridge = _try_fetch_formal_bridge(
        settings=settings, report_date=anchor_end, start_date=anchor_start,
        warnings=input_quality["warnings"],
    )
    if formal_bridge is not None and _formal_bridge_has_position_overlap(formal_bridge, positions):
        result = _formal_bridge_to_enhanced_result(
            bridge_envelope=formal_bridge,
            positions=positions,
            start_date=date.fromisoformat(anchor_start),
            end_date=date.fromisoformat(anchor_end),
        )
        result["report_date"] = anchor_end
        result["period_start"] = anchor_start
        result["period_end"] = anchor_end
        result["input_quality"] = input_quality
        result["warnings"] = list(input_quality["warnings"])
        return build_formal_result_envelope(
            result_meta=_meta_with_quality(
                "campisi.enhanced",
                input_quality,
                upstream_meta=formal_bridge.get("result_meta") or {},
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload=result,
        )

    _attach_native_principal_evidence(positions, bond_repo, anchor_start, anchor_end, input_quality)

    treasury_start, treasury_start_present, treasury_start_resolved, treasury_start_used = (
        _fetch_treasury_market_dict(curve_repo, anchor_start)
    )
    treasury_end, treasury_end_present, treasury_end_resolved, treasury_end_used = (
        _fetch_treasury_market_dict(curve_repo, anchor_end)
    )
    spread_start = fetch_credit_spread_market(curve_repo, anchor_start)
    spread_end = fetch_credit_spread_market(curve_repo, anchor_end)
    market_start = {**treasury_start, **spread_start}
    market_end = {**treasury_end, **spread_end}
    _add_market_curve_quality(
        input_quality,
        positions=positions,
        market_start=market_start,
        market_end=market_end,
        start_curve_rows_present=treasury_start_present,
        end_curve_rows_present=treasury_end_present,
        start_requested_date=anchor_start,
        start_resolved_date=treasury_start_resolved,
        end_requested_date=anchor_end,
        end_resolved_date=treasury_end_resolved,
        start_curve_used=treasury_start_used,
        end_curve_used=treasury_end_used,
    )

    result = campisi_enhanced(
        positions_merged=positions,
        market_start=market_start,
        market_end=market_end,
        start_date=date.fromisoformat(anchor_start),
        end_date=date.fromisoformat(anchor_end),
    )
    _add_position_change_quality(input_quality, result.get("effect_availability") or {})
    if result.get("diagnostics"):
        input_quality["warnings"] = [*input_quality["warnings"], *result["diagnostics"]]

    result["report_date"] = anchor_end
    result["period_start"] = anchor_start
    result["period_end"] = anchor_end
    result["input_quality"] = input_quality
    result["warnings"] = list(input_quality["warnings"])
    return build_formal_result_envelope(
        result_meta=_meta_with_quality(
            "campisi.enhanced",
            input_quality,
            filters_applied=filters,
            tables_used=TABLES_CAMPISI,
            evidence_rows=evidence_rows,
            as_of_date=anchor_end,
        ),
        result_payload=result,
    )


def campisi_maturity_bucket_envelope(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    lookback_days: int = 30,
) -> dict[str, object]:
    """Campisi 按到期桶分解。"""
    settings = get_settings()
    bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
    curve_repo = YieldCurveRepository(str(settings.duckdb_path))
    dates = bond_repo.list_report_dates()

    if not dates:
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.maturity_buckets"),
            result_payload={"buckets": {}, "period_start": "", "period_end": ""},
        )

    rd_end = end_date or dates[0]
    rd_start = start_date or (date.fromisoformat(rd_end) - timedelta(days=max(1, lookback_days))).isoformat()
    anchor_start = _anchor_on_or_before(dates, rd_start)
    anchor_end = rd_end if rd_end in dates else _anchor_on_or_before(dates, rd_end)

    if not anchor_start or not anchor_end:
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.maturity_buckets"),
            result_payload={"buckets": {}, "period_start": rd_start, "period_end": rd_end},
        )

    rows_start = bond_repo.fetch_bond_analytics_rows(report_date=anchor_start)
    rows_end = bond_repo.fetch_bond_analytics_rows(report_date=anchor_end)
    positions = _merge_positions(rows_start, rows_end)
    input_quality = _build_input_quality(rows_start=rows_start, rows_end=rows_end, positions=positions)
    filters: dict[str, object] = {
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "resolved_start_date": anchor_start,
        "resolved_end_date": anchor_end,
        "lookback_days": lookback_days,
    }
    evidence_rows = len(rows_start) + len(rows_end)

    if not positions:
        return build_formal_result_envelope(
            result_meta=_meta_warn(
                "campisi.maturity_buckets",
                source_version=SOURCE_VERSION if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload={"buckets": {}, "period_start": anchor_start, "period_end": anchor_end},
        )

    formal_bridge = _try_fetch_formal_bridge(
        settings=settings, report_date=anchor_end, start_date=anchor_start,
        warnings=input_quality["warnings"],
    )
    if formal_bridge is not None and _formal_bridge_has_position_overlap(formal_bridge, positions):
        buckets = _formal_bridge_to_maturity_buckets(
            bridge_envelope=formal_bridge,
            positions=positions,
            start_date=date.fromisoformat(anchor_start),
        )
        return build_formal_result_envelope(
            result_meta=_meta_with_quality(
                "campisi.maturity_buckets",
                input_quality,
                upstream_meta=formal_bridge.get("result_meta") or {},
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload={
                "period_start": anchor_start,
                "period_end": anchor_end,
                "basis": FORMAL_REPORT_BASIS,
                "buckets": buckets,
                "input_quality": input_quality,
                "warnings": input_quality["warnings"],
            },
        )

    _attach_native_principal_evidence(positions, bond_repo, anchor_start, anchor_end, input_quality)

    treasury_start, treasury_start_present, treasury_start_resolved, treasury_start_used = (
        _fetch_treasury_market_dict(curve_repo, anchor_start)
    )
    treasury_end, treasury_end_present, treasury_end_resolved, treasury_end_used = (
        _fetch_treasury_market_dict(curve_repo, anchor_end)
    )
    spread_start = fetch_credit_spread_market(curve_repo, anchor_start)
    spread_end = fetch_credit_spread_market(curve_repo, anchor_end)
    market_start = {**treasury_start, **spread_start}
    market_end = {**treasury_end, **spread_end}
    _add_market_curve_quality(
        input_quality,
        positions=positions,
        market_start=market_start,
        market_end=market_end,
        start_curve_rows_present=treasury_start_present,
        end_curve_rows_present=treasury_end_present,
        start_requested_date=anchor_start,
        start_resolved_date=treasury_start_resolved,
        end_requested_date=anchor_end,
        end_resolved_date=treasury_end_resolved,
        start_curve_used=treasury_start_used,
        end_curve_used=treasury_end_used,
    )

    # 复用四效应 envelope 已缓存的逐券结果做桶聚合，避免重跑完整 Campisi。
    # 缓存 key 覆盖 duckdb 指纹 + 请求/解析日期，命中即输入完全一致；
    # 未命中时走原完整计算路径（等价 fallback）。
    cached_state = _get_cached_campisi_four_effects_state(
        _campisi_four_effects_cache_key(
            duckdb_path=settings.duckdb_path,
            duckdb_fingerprint=_duckdb_storage_fingerprint(settings.duckdb_path),
            requested_start_date=start_date,
            requested_end_date=end_date,
            resolved_start_date=anchor_start,
            resolved_end_date=anchor_end,
            lookback_days=lookback_days,
        )
    )
    if cached_state is not None:
        model_result = cached_state["result"]
    else:
        model_result = campisi_attribution(
            positions_merged=positions,
            market_start=market_start,
            market_end=market_end,
            start_date=date.fromisoformat(anchor_start),
            end_date=date.fromisoformat(anchor_end),
        )
    buckets = aggregate_maturity_buckets(model_result.by_bond)
    _add_position_change_quality(input_quality, model_result.effect_availability)
    input_quality["warnings"].extend(model_result.diagnostics)

    return build_formal_result_envelope(
        result_meta=_meta_with_quality(
            "campisi.maturity_buckets",
            input_quality,
            filters_applied=filters,
            tables_used=TABLES_CAMPISI,
            evidence_rows=evidence_rows,
            as_of_date=anchor_end,
        ),
        result_payload={
            "period_start": anchor_start,
            "period_end": anchor_end,
            "buckets": buckets,
            "effect_availability": model_result.effect_availability,
            "input_quality": input_quality,
            "warnings": input_quality["warnings"],
        },
    )
