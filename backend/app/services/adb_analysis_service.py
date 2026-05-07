"""
日均资产负债（ADB）分析 — DuckDB 读模型。

ADB 优先读 `fact_formal_zqtz_balance_daily` / `fact_formal_tyw_balance_daily` 的 `currency_basis = 'CNY'` 行。
当 formal 表缺少某些日期时，自动从 `zqtz_bond_daily_snapshot` / `tyw_interbank_daily_snapshot` 补充（原币，
不做 FX 转换——国内业务绝大多数 CNY 原币即 CNY，偏差可接受）。

期末时点与区间日均对比：若某分类在 ``end_date`` 当天无任何快照行，但区间内曾有余额，则该分类期末时点取
区间内**不晚于** ``end_date`` 的**最近观测日**的同类合计（LOCF），避免「时点=0、日均>0」的伪偏离。

- 债券：`position_scope = liability` 或 `is_issuance_like` → 负债，其余 → 资产。
- 同业：`position_scope` / `position_side` 推断 `ASSET` / `LIABILITY`。
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

from backend.app.core_finance.adb_analytics import (
    aggregate_daily_totals,
    build_comparison_rows,
    build_rate_map,
    compute_adb_trend,
    compute_mom_changes,
    compute_nim,
    compute_weighted_rate,
    enrich_breakdown,
    month_date_range,
)
from backend.app.core_finance.balance_calibration import (
    balance_calibration_meta_to_dict,
    build_adb_daily_balance_calibration_meta,
)
from backend.app.core_finance.adb_interbank_labels import map_ib_category
from backend.app.core_finance.adb_rate_normalize import normalize_rate_values
from backend.app.core_finance.zqtz_asset_bond_category import classify_zqtz_asset_bond_label
from backend.app.governance.settings import get_settings
from backend.app.services.formal_result_runtime import build_result_envelope

IB_ASSET_PRED = (
    "(instr(lower(coalesce(position_side, '')), 'asset') > 0 "
    "OR instr(coalesce(position_side, ''), '资产') > 0)"
)
ADB_CACHE_VERSION = "cv_adb_analysis_v1"
ADB_EMPTY_SOURCE_VERSION = "sv_adb_empty"
ADB_RULE_VERSION = "rv_adb_analysis_v9_formal_only_no_snapshot_adb"


def _conn_ro(path: str) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(path, read_only=True)


def _table_exists(conn: duckdb.DuckDBPyConnection, name: str) -> bool:
    """Detect physical tables reliably (DuckDB ``information_schema`` casing/catalog quirks)."""
    try:
        row = conn.execute(
            """
            select 1 from duckdb_tables()
            where lower(table_name) = lower(?)
            limit 1
            """,
            [name],
        ).fetchone()
        if row is not None:
            return True
    except duckdb.Error:
        pass
    row = conn.execute(
        """
        select 1 from information_schema.tables
        where lower(table_name) = lower(?) limit 1
        """,
        [name],
    ).fetchone()
    return row is not None


def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _stable_factor(key: str, low: Decimal = Decimal("0.85"), high: Decimal = Decimal("1.15")) -> Decimal:
    raw = (key or "").encode("utf-8", errors="ignore")
    h = hashlib.md5(raw).hexdigest()
    n = int(h[:8], 16)
    u = Decimal(n) / Decimal(0xFFFFFFFF)
    return low + (high - low) * u


def _clean_cat(v: object) -> str:
    if v is None:
        return "其它"
    s = str(v).strip()
    return s if s else "其它"


def _merge_versions(values: list[str], default: str) -> str:
    merged = sorted({str(value or "").strip() for value in values if str(value or "").strip()})
    return "__".join(merged) or default


def _issued_mask(bonds_df: pd.DataFrame) -> pd.Series:
    if bonds_df.empty:
        return pd.Series(dtype=bool)
    issued_mask = (
        bonds_df["is_issuance_like"].fillna(False).astype(bool)
        if "is_issuance_like" in bonds_df.columns
        else pd.Series(False, index=bonds_df.index)
    )
    if "asset_class" in bonds_df.columns:
        issued_mask = issued_mask | bonds_df["asset_class"].astype(str).str.contains("发行", na=False)
    return issued_mask


OPTIONAL_ZQTZ_CLASSIFIER_COLUMNS = (
    "instrument_code",
    "instrument_name",
    "business_type_primary",
    "business_type_final",
    "sub_type",
    "currency_code",
    "accounting_basis",
)
ZQTZ_ASSET_CLASSIFIER_KEY_COLUMNS = (
    "sub_type",
    "business_type_final",
    "business_type_primary",
    "bond_type",
    "instrument_name",
    "asset_class",
    "instrument_code",
    "accounting_basis",
    "currency_code",
)


def _column_exists(conn: duckdb.DuckDBPyConnection, table: str, column: str) -> bool:
    try:
        row = conn.execute(
            """
            select 1 from information_schema.columns
            where lower(table_name) = lower(?) and lower(column_name) = lower(?)
            limit 1
            """,
            [table, column],
        ).fetchone()
        return row is not None
    except duckdb.Error:
        return False


def _select_list_zqtz_formal(conn: duckdb.DuckDBPyConnection) -> str:
    table = "fact_formal_zqtz_balance_daily"
    base = [
        "report_date",
        "position_scope",
        "market_value_amount",
        "ytm_value",
        "coupon_rate",
        "asset_class",
        "bond_type",
        "is_issuance_like",
        "source_version",
        "rule_version",
    ]
    parts = list(base)
    for col in OPTIONAL_ZQTZ_CLASSIFIER_COLUMNS:
        if _column_exists(conn, table, col):
            parts.append(col)
        else:
            parts.append(f"cast(null as varchar) as {col}")
    return ",\n                  ".join(parts)


def _select_list_zqtz_snapshot(conn: duckdb.DuckDBPyConnection) -> str:
    table = "zqtz_bond_daily_snapshot"
    header = [
        "report_date",
        "case when is_issuance_like then 'liability' else 'asset' end as position_scope",
        "market_value_native as market_value_amount",
        "ytm_value",
        "coupon_rate",
        "asset_class",
        "bond_type",
        "is_issuance_like",
        "source_version",
        "rule_version",
    ]
    parts = list(header)
    for col in OPTIONAL_ZQTZ_CLASSIFIER_COLUMNS:
        if _column_exists(conn, table, col):
            parts.append(col)
        else:
            parts.append(f"cast(null as varchar) as {col}")
    return ",\n                      ".join(parts)


def _liability_bond_display_category(row: pd.Series) -> str:
    """负债/发行分类：优先会计 sub_type；为空则依次业务种类、债券类型，避免尽落入「其它」。"""
    for col in ("sub_type", "business_type_primary", "bond_type"):
        if col not in row.index:
            continue
        raw = row[col]
        try:
            if pd.isna(raw):
                continue
        except TypeError:
            pass
        if raw is None:
            continue
        label = _clean_cat(raw)
        if label != "其它":
            return label
    return "其它"


def _classify_zqtz_asset_categories(assets: pd.DataFrame) -> pd.Series:
    if assets.empty:
        return pd.Series(index=assets.index, dtype=object)

    key_frame = pd.DataFrame(index=assets.index)
    for column in ZQTZ_ASSET_CLASSIFIER_KEY_COLUMNS:
        if column in assets.columns:
            key_frame[column] = assets[column].fillna("").astype(str)
        else:
            key_frame[column] = ""

    keys = pd.Series(
        list(map(tuple, key_frame.to_numpy(dtype=object))),
        index=assets.index,
        dtype=object,
    )
    category_by_key = {
        key: classify_zqtz_asset_bond_label(
            dict(zip(ZQTZ_ASSET_CLASSIFIER_KEY_COLUMNS, key, strict=True))
        )
        for key in keys.drop_duplicates()
    }
    return keys.map(category_by_key)


def _assign_zqtz_bond_categories(bonds_df: pd.DataFrame) -> pd.DataFrame:
    """资产侧：与资产负债表迁徙同源 ZQTZ 规则；负债/发行侧：sub_type 优先，空则回退业务种类/债券类型。"""
    if bonds_df.empty:
        return bonds_df
    issued = _issued_mask(bonds_df)
    bd = bonds_df.copy()
    assets = bd[~issued]
    liabilities = bd[issued]
    if not assets.empty:
        bd.loc[assets.index, "bond_category"] = _classify_zqtz_asset_categories(assets)
    if not liabilities.empty:
        bd.loc[liabilities.index, "bond_category"] = liabilities.apply(_liability_bond_display_category, axis=1)
    return bd


def _build_analytical_envelope(
    *,
    result_kind: str,
    result_payload: dict[str, Any],
    source_versions: list[str],
    rule_versions: list[str],
    filters_applied: dict[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
) -> dict[str, Any]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_{result_kind.replace('.', '_')}",
        result_kind=result_kind,
        cache_version=ADB_CACHE_VERSION,
        source_version=_merge_versions(source_versions, ADB_EMPTY_SOURCE_VERSION),
        rule_version=_merge_versions(rule_versions, ADB_RULE_VERSION),
        quality_flag="ok",
        vendor_version="vv_none",
        result_payload=result_payload,
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
    )


def _empty_adb_response() -> dict[str, Any]:
    return {
        "summary": {
            "total_avg_assets": 0.0,
            "total_avg_liabilities": 0.0,
            "end_spot_assets": 0.0,
            "end_spot_liabilities": 0.0,
        },
        "trend": [],
        "breakdown": [],
    }


def _classify_zqtz_rows(
    rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Split raw ZQTZ rows into (asset_rows, liability_rows) using position_scope + is_issuance_like."""
    concrete = [r for r in rows if str(r.get("position_scope") or "") in {"asset", "liability"}]
    scoped = concrete if concrete else rows
    assets, liabilities = [], []
    for row in scoped:
        if str(row.get("position_scope") or "") == "liability" or bool(row.get("is_issuance_like")):
            liabilities.append(row)
        else:
            assets.append(row)
    return assets, liabilities


def _classify_tyw_rows(
    rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Split raw TYW rows into (asset_rows, liability_rows) using position_scope + position_side."""
    concrete = [r for r in rows if str(r.get("position_scope") or "") in {"asset", "liability"}]
    scoped = concrete if concrete else rows
    assets, liabilities = [], []
    for row in scoped:
        scope = str(row.get("position_scope") or "").lower()
        side = str(row.get("position_side") or "").lower()
        is_asset = scope == "asset" or (scope not in {"asset", "liability"} and "asset" in side)
        (assets if is_asset else liabilities).append(row)
    return assets, liabilities


def _build_bonds_df(
    asset_rows: list[dict[str, object]],
    liability_rows: list[dict[str, object]],
) -> pd.DataFrame:
    """Construct normalised bonds DataFrame from classified ZQTZ row dicts."""
    def _bond_record(row: dict[str, object], is_issuance: bool) -> dict[str, object]:
        return {
            "report_date": row["report_date"],
            "market_value": row["market_value_amount"],
            "yield_to_maturity": row["ytm_value"],
            "coupon_rate": row["coupon_rate"],
            "interest_rate": 0.0,
            "asset_class": row.get("asset_class") or "",
            "sub_type": row.get("bond_type") or "",
            "is_issuance_like": is_issuance,
        }

    records = [_bond_record(r, False) for r in asset_rows] + [_bond_record(r, True) for r in liability_rows]
    df = pd.DataFrame(records)
    return _normalize_adb_frame(
        df,
        date_columns=("report_date",),
        numeric_columns=("market_value", "yield_to_maturity", "coupon_rate", "interest_rate"),
    )


def _build_ib_df(
    asset_rows: list[dict[str, object]],
    liability_rows: list[dict[str, object]],
) -> pd.DataFrame:
    """Construct normalised interbank DataFrame from classified TYW row dicts."""
    def _ib_record(row: dict[str, object], direction: str) -> dict[str, object]:
        return {
            "report_date": row["report_date"],
            "amount": row["principal_amount"],
            "interest_rate": row["funding_cost_rate"],
            "product_type": row["product_type"],
            "direction": direction,
        }

    records = [_ib_record(r, "ASSET") for r in asset_rows] + [_ib_record(r, "LIABILITY") for r in liability_rows]
    df = pd.DataFrame(records)
    return _normalize_adb_frame(
        df,
        date_columns=("report_date",),
        numeric_columns=("amount", "interest_rate"),
    )


def _collect_version_strings(
    *row_lists: list[dict[str, object]],
    field: str,
) -> list[str]:
    return [str(row.get(field) or "") for rows in row_lists for row in rows]


def _adb_lineage_sources(zqtz_src: str, tyw_src: str) -> tuple[str, list[str]]:
    """comparison 分母标签与 result_meta.tables_used。支持 formal / snapshot / formal+snapshot 混合。"""
    has_formal = "formal" in zqtz_src or "formal" in tyw_src
    has_snapshot = "snapshot" in zqtz_src or "snapshot" in tyw_src
    if has_formal and has_snapshot:
        basis = "formal+snapshot_calendar"
    elif has_formal:
        basis = "formal_calendar"
    else:
        basis = "snapshot_calendar"
    tables: list[str] = []
    if "formal" in zqtz_src:
        tables.append("fact_formal_zqtz_balance_daily")
    if "formal" in tyw_src:
        tables.append("fact_formal_tyw_balance_daily")
    if "snapshot" in zqtz_src:
        tables.append("zqtz_bond_daily_snapshot")
    if "snapshot" in tyw_src:
        tables.append("tyw_interbank_daily_snapshot")
    return basis, tables


def _load_adb_raw_data(
    duckdb_path: str,
    start_date: date,
    end_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str], str, list[str]]:
    if not Path(duckdb_path).exists():
        return pd.DataFrame(), pd.DataFrame(), [], [], "snapshot_calendar", []

    zqtz_df = pd.DataFrame()
    tyw_df = pd.DataFrame()
    zqtz_src = "none"
    tyw_src = "none"

    conn = _conn_ro(duckdb_path)
    try:
        # --- 1. Load from formal tables (primary source) ---
        if _table_exists(conn, "fact_formal_zqtz_balance_daily"):
            zqtz_src = "formal"
            zqtz_df = conn.execute(
                f"""
                select
                  {_select_list_zqtz_formal(conn)}
                from fact_formal_zqtz_balance_daily
                where cast(report_date as date) between ? and ?
                  and currency_basis = 'CNY'
                """,
                [start_date, end_date],
            ).fetchdf()

        if _table_exists(conn, "fact_formal_tyw_balance_daily"):
            tyw_src = "formal"
            tyw_df = conn.execute(
                """
                select
                  report_date,
                  position_scope,
                  position_side,
                  principal_amount,
                  funding_cost_rate,
                  product_type,
                  source_version,
                  rule_version
                from fact_formal_tyw_balance_daily
                where cast(report_date as date) between ? and ?
                  and currency_basis = 'CNY'
                """,
                [start_date, end_date],
            ).fetchdf()

        # --- 2. Snapshot fallback for dates missing from formal tables ---
        formal_dates: set[str] = set()
        for df in (zqtz_df, tyw_df):
            if not df.empty and "report_date" in df.columns:
                formal_dates.update(
                    pd.to_datetime(df["report_date"], errors="coerce")
                    .dropna()
                    .dt.strftime("%Y-%m-%d")
                    .unique()
                    .tolist()
                )

        snapshot_dates: set[str] = set()
        has_zqtz_snap = _table_exists(conn, "zqtz_bond_daily_snapshot")
        has_tyw_snap = _table_exists(conn, "tyw_interbank_daily_snapshot")
        if has_zqtz_snap or has_tyw_snap:
            for snap_tbl in ("zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot"):
                if _table_exists(conn, snap_tbl):
                    snap_date_rows = conn.execute(
                        f"""
                        select distinct cast(report_date as varchar)
                        from {snap_tbl}
                        where cast(report_date as date) between ? and ?
                        """,
                        [start_date, end_date],
                    ).fetchall()
                    snapshot_dates.update(r[0] for r in snap_date_rows if r[0])

        missing_dates = sorted(snapshot_dates - formal_dates)
        has_zqtz_formal = _table_exists(conn, "fact_formal_zqtz_balance_daily")
        has_tyw_formal = _table_exists(conn, "fact_formal_tyw_balance_daily")
        # 仅当对应 formal 表存在时才从快照补缺失日：无 formal 表则不读快照（须先物化 formal）
        if missing_dates and (has_zqtz_formal or has_tyw_formal):
            logger.info(
                "ADB snapshot fallback: %d dates missing from formal tables, supplementing from snapshots",
                len(missing_dates),
            )
            snapshot_date_in_list = ",".join(f"'{d}'" for d in missing_dates)

            # Supplement ZQTZ from snapshot
            if has_zqtz_snap and has_zqtz_formal:
                zqtz_snap_sql = (
                    f"""
                    select
                      {_select_list_zqtz_snapshot(conn)}
                    from zqtz_bond_daily_snapshot
                    where cast(report_date as date) between ? and ?
                      and cast(report_date as varchar) in ({snapshot_date_in_list})
                    """
                )
                zqtz_snap = conn.execute(
                    zqtz_snap_sql,
                    [start_date, end_date],
                ).fetchdf()
                if not zqtz_snap.empty:
                    zqtz_df = pd.concat([zqtz_df, zqtz_snap], ignore_index=True) if not zqtz_df.empty else zqtz_snap
                    if zqtz_src == "none":
                        zqtz_src = "snapshot"
                    else:
                        zqtz_src = "formal+snapshot"

            # Supplement TYW from snapshot
            if has_tyw_snap and has_tyw_formal:
                tyw_snap_sql = f"""
                    select
                      report_date,
                      coalesce(position_side, 'all') as position_scope,
                      position_side,
                      principal_native as principal_amount,
                      funding_cost_rate,
                      product_type,
                      source_version,
                      rule_version
                    from tyw_interbank_daily_snapshot
                    where cast(report_date as date) between ? and ?
                      and cast(report_date as varchar) in ({snapshot_date_in_list})
                    """
                tyw_snap = conn.execute(
                    tyw_snap_sql,
                    [start_date, end_date],
                ).fetchdf()
                if not tyw_snap.empty:
                    tyw_df = pd.concat([tyw_df, tyw_snap], ignore_index=True) if not tyw_df.empty else tyw_snap
                    if tyw_src == "none":
                        tyw_src = "snapshot"
                    else:
                        tyw_src = "formal+snapshot"
    finally:
        conn.close()

    adb_denominator_basis, adb_tables_used = _adb_lineage_sources(zqtz_src, tyw_src)

    source_versions: list[str] = []
    rule_versions: list[str] = []
    for frame in (zqtz_df, tyw_df):
        if frame.empty:
            continue
        if "source_version" in frame.columns:
            source_versions.extend(frame["source_version"].dropna().astype(str).unique().tolist())
        if "rule_version" in frame.columns:
            rule_versions.extend(frame["rule_version"].dropna().astype(str).unique().tolist())

    if zqtz_df.empty:
        bonds_df = pd.DataFrame()
    else:
        scope = zqtz_df["position_scope"].fillna("").astype(str)
        concrete = scope.isin({"asset", "liability"})
        scoped = zqtz_df.loc[concrete].copy() if concrete.any() else zqtz_df.copy()
        scoped_scope = scoped["position_scope"].fillna("").astype(str)
        issuance = scoped["is_issuance_like"].fillna(False).astype(bool)
        liability_mask = scoped_scope.eq("liability") | issuance

        def _ofill_str(column: str) -> pd.Series:
            if column not in scoped.columns:
                return pd.Series("", index=scoped.index, dtype=object)
            return scoped[column].fillna("").astype(str)

        bond_type_series = (
            scoped["bond_type"].fillna("").astype(str) if "bond_type" in scoped.columns else pd.Series("", index=scoped.index)
        )
        if "sub_type" in scoped.columns:
            sub_type_series = scoped["sub_type"].fillna("").astype(str)
        else:
            sub_type_series = pd.Series("", index=scoped.index, dtype=object)

        bonds_df = pd.DataFrame(
            {
                "report_date": scoped["report_date"],
                "market_value": scoped["market_value_amount"],
                "yield_to_maturity": scoped["ytm_value"],
                "coupon_rate": scoped["coupon_rate"],
                "interest_rate": 0.0,
                "asset_class": scoped["asset_class"].fillna("").astype(str),
                "bond_type": bond_type_series,
                "sub_type": sub_type_series,
                "business_type_primary": _ofill_str("business_type_primary"),
                "business_type_final": _ofill_str("business_type_final"),
                "instrument_code": _ofill_str("instrument_code"),
                "instrument_name": _ofill_str("instrument_name"),
                "currency_code": _ofill_str("currency_code"),
                "accounting_basis": _ofill_str("accounting_basis"),
                "is_issuance_like": liability_mask.to_numpy(),
            }
        )
        bonds_df = _normalize_adb_frame(
            bonds_df,
            date_columns=("report_date",),
            numeric_columns=("market_value", "yield_to_maturity", "coupon_rate", "interest_rate"),
        )
        bonds_df = _assign_zqtz_bond_categories(bonds_df)

    if tyw_df.empty:
        ib_df = pd.DataFrame()
    else:
        scope = tyw_df["position_scope"].fillna("").astype(str).str.lower()
        concrete = scope.isin({"asset", "liability"})
        scoped = tyw_df.loc[concrete].copy() if concrete.any() else tyw_df.copy()
        scoped_scope = scoped["position_scope"].fillna("").astype(str).str.lower()
        raw_side = scoped["position_side"].fillna("").astype(str).str.strip()
        side = raw_side.str.lower()
        is_asset = scoped_scope.eq("asset") | (
            ~scoped_scope.isin({"asset", "liability"})
            & (
                raw_side.eq("资产")
                | side.eq("asset")
                | (side.str.contains("asset", na=False) & ~raw_side.eq("负债"))
            )
        )
        ib_df = pd.DataFrame(
            {
                "report_date": scoped["report_date"],
                "amount": scoped["principal_amount"],
                "interest_rate": scoped["funding_cost_rate"],
                "product_type": scoped["product_type"],
                "direction": is_asset.map({True: "ASSET", False: "LIABILITY"}).to_numpy(),
            }
        )
        ib_df = _normalize_adb_frame(
            ib_df,
            date_columns=("report_date",),
            numeric_columns=("amount", "interest_rate"),
        )

    return bonds_df, ib_df, source_versions, rule_versions, adb_denominator_basis, adb_tables_used


def _decimal_or_zero(value: object) -> Decimal:
    return Decimal(str(value or 0))


def _frame_unique_dates(frame: pd.DataFrame) -> set[date]:
    if frame.empty or "report_date" not in frame.columns:
        return set()
    report_dates = pd.to_datetime(frame["report_date"], errors="coerce").dropna()
    return {value.date() for value in report_dates.unique()}


def _adb_distinct_snapshot_days(bonds_df: pd.DataFrame, interbank_df: pd.DataFrame) -> int:
    """ZQTZ ∪ TYW 在区间内的不重复 report_date 数；与月度 `_process_single_month` 口径一致。"""
    return len(_frame_unique_dates(bonds_df) | _frame_unique_dates(interbank_df))


def _frame_sum_by_date(frame: pd.DataFrame, amount_attr: str) -> dict[date, Decimal]:
    totals: dict[date, Decimal] = {}
    if frame.empty:
        return totals
    for row in frame.itertuples(index=False):
        report_date = getattr(row, "report_date", None)
        if report_date is None:
            continue
        day = report_date.date()
        totals[day] = totals.get(day, Decimal("0")) + _decimal_or_zero(getattr(row, amount_attr))
    return totals


def _frame_total_amounts(frame: pd.DataFrame, amount_attr: str) -> tuple[float, float]:
    if frame.empty:
        return 0.0, 0.0
    total_amount = pd.to_numeric(frame[amount_attr], errors="coerce").fillna(0).sum()
    total_weighted = pd.to_numeric(frame["weighted"], errors="coerce").fillna(0).sum() if "weighted" in frame else 0.0
    return float(total_amount), float(total_weighted)


def _frame_spot_total_for_date(frame: pd.DataFrame, amount_attr: str, target_date: date) -> float:
    if frame.empty or "report_date" not in frame.columns:
        return 0.0
    report_dates = pd.to_datetime(frame["report_date"], errors="coerce").dt.normalize()
    mask = report_dates.eq(pd.Timestamp(target_date))
    if not mask.any():
        return 0.0
    total = pd.to_numeric(frame.loc[mask, amount_attr], errors="coerce").fillna(0).sum()
    return float(total)


def _frame_breakdown_rows(
    frame: pd.DataFrame,
    *,
    category_attr: str,
    amount_attr: str,
    num_days: int,
    prefix: str = "",
) -> list[dict[str, Any]]:
    if frame.empty or num_days <= 0:
        return []
    categories = frame[category_attr].map(_clean_cat)
    if prefix:
        categories = prefix + categories
    grouped_source = pd.DataFrame(
        {
            "category": categories,
            "amount": pd.to_numeric(frame[amount_attr], errors="coerce").fillna(0),
            "weighted": (
                pd.to_numeric(frame["weighted"], errors="coerce").fillna(0)
                if "weighted" in frame
                else 0.0
            ),
        }
    )
    grouped = grouped_source.groupby("category", sort=False, as_index=False).sum(numeric_only=True)
    rows: list[dict[str, Any]] = []
    for row in grouped.itertuples(index=False):
        total_amount = float(row.amount or 0)
        total_weighted = float(row.weighted or 0)
        rows.append(
            {
                "category": row.category,
                "avg_balance": total_amount / num_days if num_days > 0 else 0.0,
                "weighted_rate": (total_weighted / total_amount * 100) if total_amount > 0 else None,
            }
        )
    return rows


def _tyw_interval_avg_balances(interbank_df: pd.DataFrame, num_days: int) -> tuple[float, float]:
    """同业（TYW）区间日均资产 / 负债：区间内含金额求和 ÷ ADB 分母天数（与 total_avg_* 分母一致）。"""
    if interbank_df.empty or num_days <= 0:
        return 0.0, 0.0
    if "amount" not in interbank_df.columns or "direction" not in interbank_df.columns:
        return 0.0, 0.0
    amounts = pd.to_numeric(interbank_df["amount"], errors="coerce").fillna(0.0)
    direction = interbank_df["direction"].astype(str).str.upper()
    sum_assets = float(amounts[direction == "ASSET"].sum())
    sum_liabilities = float(amounts[direction == "LIABILITY"].sum())
    nd = float(max(num_days, 1))
    return sum_assets / nd, sum_liabilities / nd


def _accumulate_spot_and_sum_maps(
    frame: pd.DataFrame,
    *,
    amount_attr: str,
    end_date: date,
    category_resolver,
    spot_map: dict[str, Decimal],
    sum_map: dict[str, Decimal],
) -> None:
    if frame.empty:
        return
    for row in frame.itertuples(index=False):
        category = _clean_cat(category_resolver(row))
        amount = _decimal_or_zero(getattr(row, amount_attr))
        sum_map[category] = sum_map.get(category, Decimal("0")) + amount
        report_date = getattr(row, "report_date", None)
        row_day = _adb_row_report_day(report_date)
        if row_day is not None and row_day == end_date:
            spot_map[category] = spot_map.get(category, Decimal("0")) + amount


def _adb_row_report_day(report_date: object) -> date | None:
    if report_date is None:
        return None
    try:
        ts = pd.Timestamp(report_date)
    except (TypeError, ValueError, OverflowError):
        return None
    if pd.isna(ts):
        return None
    return ts.date()


def _finalize_spot_map_locf_for_frame(
    frame: pd.DataFrame,
    *,
    amount_attr: str,
    end_date: date,
    category_resolver,
    spot_map: dict[str, Decimal],
    sum_map: dict[str, Decimal],
) -> None:
    """仅针对当前 frame 内出现的分类：若在 end_date 无行则做 LOCF（见模块说明）。"""
    if frame.empty:
        return
    frame_categories: set[str] = set()
    end_date_seen: set[str] = set()
    pairs_by_cat: dict[str, list[tuple[date, Decimal]]] = {}
    for row in frame.itertuples(index=False):
        cat = _clean_cat(category_resolver(row))
        frame_categories.add(cat)
        day = _adb_row_report_day(getattr(row, "report_date", None))
        if day is None or day > end_date:
            continue
        amount = _decimal_or_zero(getattr(row, amount_attr))
        pairs_by_cat.setdefault(cat, []).append((day, amount))
        if day == end_date:
            end_date_seen.add(cat)

    for cat in frame_categories:
        if sum_map.get(cat, Decimal("0")) == Decimal("0"):
            continue
        if cat in end_date_seen:
            continue
        if spot_map.get(cat, Decimal("0")) != Decimal("0"):
            continue
        pairs = pairs_by_cat.get(cat) or []
        if not pairs:
            continue
        latest = max(d for d, _ in pairs)
        locf_total = sum(amt for d, amt in pairs if d == latest)
        if locf_total != Decimal("0"):
            spot_map[cat] = locf_total


def _normalize_adb_frame(
    frame: pd.DataFrame,
    *,
    date_columns: tuple[str, ...],
    numeric_columns: tuple[str, ...],
) -> pd.DataFrame:
    if frame.empty:
        return frame
    normalized = frame.copy()
    for column in date_columns:
        if column in normalized.columns:
            normalized[column] = pd.to_datetime(normalized[column], errors="coerce")
    for column in numeric_columns:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0)
    return normalized


def _filter_frame_between_dates(frame: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows = [
        row._asdict()
        for row in frame.itertuples(index=False)
        if getattr(row, "report_date", None) is not None
        and start_date <= row.report_date.date() <= end_date
    ]
    return pd.DataFrame(rows, columns=frame.columns)


def _group_frame_by_year_month(frame: pd.DataFrame) -> dict[tuple[int, int], pd.DataFrame]:
    """Split one frame by calendar (year, month) in a single vectorized groupby (avoids N× full-table Python scans)."""
    if frame.empty or "report_date" not in frame.columns:
        return {}
    s = frame["report_date"]
    if s.isna().all():
        return {}
    sub = frame.loc[s.notna()]
    if sub.empty:
        return {}
    gy = sub["report_date"].dt.year
    gm = sub["report_date"].dt.month
    return {(int(y), int(m)): grp for (y, m), grp in sub.groupby([gy, gm], sort=True)}


def _fetch_formal_zqtz_rows(
    conn: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
) -> list[tuple[list[tuple], tuple]]:
    cursor = conn.execute(
        """
        select
          report_date,
          position_scope,
          currency_basis,
          market_value_amount,
          ytm_value,
          coupon_rate,
          asset_class,
          bond_type,
          is_issuance_like,
          source_version,
          rule_version
        from fact_formal_zqtz_balance_daily
        where cast(report_date as date) between ? and ?
          and currency_basis = 'CNY'
        """,
        [start_date, end_date],
    )
    description = list(cursor.description or [])
    return [(description, row) for row in cursor.fetchall()]


def _fetch_formal_tyw_rows(
    conn: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
) -> list[tuple[list[tuple], tuple]]:
    cursor = conn.execute(
        """
        select
          report_date,
          position_scope,
          position_side,
          currency_basis,
          principal_amount,
          funding_cost_rate,
          product_type,
          source_version,
          rule_version
        from fact_formal_tyw_balance_daily
        where cast(report_date as date) between ? and ?
          and currency_basis = 'CNY'
        """,
        [start_date, end_date],
    )
    description = list(cursor.description or [])
    return [(description, row) for row in cursor.fetchall()]


def _split_rate_frames(
    bonds_df: pd.DataFrame,
    interbank_df: pd.DataFrame,
) -> tuple[list[pd.DataFrame], list[pd.DataFrame], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    asset_frames: list[pd.DataFrame] = []
    liability_frames: list[pd.DataFrame] = []

    bonds_assets_df = pd.DataFrame()
    bonds_liab_df = pd.DataFrame()
    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        bonds_assets_df = bonds_df[~issued_mask].copy()
        if not bonds_assets_df.empty:
            bonds_assets_df["category"] = bonds_assets_df["bond_category"].map(_clean_cat)
            bonds_assets_df["balance"] = pd.to_numeric(bonds_assets_df["market_value"], errors="coerce").fillna(0.0)
            bonds_assets_df["rate_decimal"] = normalize_rate_values(
                bonds_assets_df["yield_to_maturity"].tolist(),
                "yield_to_maturity",
            )
            bonds_assets_df["weighted"] = bonds_assets_df["balance"] * bonds_assets_df["rate_decimal"]
            asset_frames.append(bonds_assets_df[["category", "balance", "weighted"]])

        bonds_liab_df = bonds_df[issued_mask].copy()
        if not bonds_liab_df.empty:
            bonds_liab_df["category"] = bonds_liab_df["bond_category"].map(_clean_cat)
            bonds_liab_df["balance"] = pd.to_numeric(bonds_liab_df["market_value"], errors="coerce").fillna(0.0)
            bonds_liab_df["rate_decimal"] = [
                rate if coupon not in (None, 0, 0.0) else 0.0
                for coupon, rate in zip(
                    bonds_liab_df["coupon_rate"].tolist(),
                    normalize_rate_values(bonds_liab_df["coupon_rate"].tolist(), "coupon_rate"),
                    strict=True,
                )
            ]
            bonds_liab_df["weighted"] = bonds_liab_df["balance"] * bonds_liab_df["rate_decimal"]
            liability_frames.append(bonds_liab_df[["category", "balance", "weighted"]])

    ib_assets_df = pd.DataFrame()
    ib_liab_df = pd.DataFrame()
    if not interbank_df.empty:
        ib_assets_df = interbank_df[interbank_df["direction"] == "ASSET"].copy()
        if not ib_assets_df.empty:
            ib_assets_df["category"] = ib_assets_df["product_type"].apply(_clean_cat)
            ib_assets_df["balance"] = pd.to_numeric(ib_assets_df["amount"], errors="coerce").fillna(0.0)
            ib_assets_df["rate_decimal"] = normalize_rate_values(
                ib_assets_df["interest_rate"].tolist(),
                "interbank_interest_rate",
            )
            ib_assets_df["weighted"] = ib_assets_df["balance"] * ib_assets_df["rate_decimal"]
            asset_frames.append(ib_assets_df[["category", "balance", "weighted"]])

        ib_liab_df = interbank_df[interbank_df["direction"] == "LIABILITY"].copy()
        if not ib_liab_df.empty:
            ib_liab_df["category"] = ib_liab_df["product_type"].apply(_clean_cat)
            ib_liab_df["balance"] = pd.to_numeric(ib_liab_df["amount"], errors="coerce").fillna(0.0)
            ib_liab_df["rate_decimal"] = normalize_rate_values(
                ib_liab_df["interest_rate"].tolist(),
                "interbank_interest_rate",
            )
            ib_liab_df["weighted"] = ib_liab_df["balance"] * ib_liab_df["rate_decimal"]
            liability_frames.append(ib_liab_df[["category", "balance", "weighted"]])

    return asset_frames, liability_frames, bonds_assets_df, bonds_liab_df, ib_assets_df, ib_liab_df


def _build_rate_map(frames: list[pd.DataFrame]) -> tuple[dict[str, float | None], float | None]:
    if not frames:
        return {}, None
    rate_map: dict[str, float | None] = {}
    totals: dict[str, tuple[float, float]] = {}
    total_balance = 0.0
    total_weighted = 0.0
    for frame in frames:
        if frame.empty:
            continue
        for row in frame.itertuples(index=False):
            category = _clean_cat(getattr(row, "category", None))
            balance = float(getattr(row, "balance", 0) or 0)
            weighted = float(getattr(row, "weighted", 0) or 0)
            current_balance, current_weighted = totals.get(category, (0.0, 0.0))
            totals[category] = (current_balance + balance, current_weighted + weighted)
            total_balance += balance
            total_weighted += weighted
    for category, (balance, weighted) in totals.items():
        rate_map[category] = round(weighted / balance * 100, 4) if balance > 0 else None
    total_rate = round(total_weighted / total_balance * 100, 4) if total_balance > 0 else None
    return rate_map, total_rate


def _adb_breakdown_from_frames(
    bonds_df: pd.DataFrame,
    interbank_df: pd.DataFrame,
    num_days: int,
) -> list[dict[str, Any]]:
    if num_days <= 0:
        return []

    breakdown_sum: dict[tuple[str, str], Decimal] = {}
    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        bonds_assets_df = bonds_df[~issued_mask].copy()
        bonds_liab_df = bonds_df[issued_mask].copy()
        for row in bonds_assets_df.itertuples(index=False):
            key = (_clean_cat(getattr(row, "bond_category", None)), "Asset")
            breakdown_sum[key] = breakdown_sum.get(key, Decimal("0")) + _decimal_or_zero(getattr(row, "market_value"))
        for row in bonds_liab_df.itertuples(index=False):
            key = (f"Issuance-{_clean_cat(getattr(row, 'bond_category', None))}", "Liability")
            breakdown_sum[key] = breakdown_sum.get(key, Decimal("0")) + _decimal_or_zero(getattr(row, "market_value"))

    if not interbank_df.empty:
        for row in interbank_df.itertuples(index=False):
            side = "Asset" if str(getattr(row, "direction", "") or "").upper() == "ASSET" else "Liability"
            category = map_ib_category(
                str(getattr(row, "product_type")) if getattr(row, "product_type", None) is not None else None,
                side,
            )
            key = (category, side)
            breakdown_sum[key] = breakdown_sum.get(key, Decimal("0")) + _decimal_or_zero(getattr(row, "amount"))

    nd = Decimal(str(num_days))
    out: list[dict[str, Any]] = []
    for (cat, side), total in sorted(breakdown_sum.items(), key=lambda item: float(item[1] or 0), reverse=True):
        avg_val = (total / nd) if nd else Decimal("0")
        out.append({"category": cat, "side": side, "avg_balance": float(avg_val)})
    return out


def _split_bonds_ib_by_side(
    bonds_df: pd.DataFrame,
    interbank_df: pd.DataFrame,
) -> tuple[dict[date, Decimal], dict[date, Decimal], dict[date, Decimal], dict[date, Decimal]]:
    """Return (bonds_assets, bonds_liabilities, ib_assets, ib_liabilities) as date→Decimal maps."""
    bonds_assets: dict[date, Decimal] = {}
    bonds_liabilities: dict[date, Decimal] = {}
    ib_assets: dict[date, Decimal] = {}
    ib_liabilities: dict[date, Decimal] = {}

    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        bonds_assets = _frame_sum_by_date(bonds_df[~issued_mask], "market_value")
        bonds_liabilities = _frame_sum_by_date(bonds_df[issued_mask], "market_value")

    if not interbank_df.empty:
        ib_assets = _frame_sum_by_date(interbank_df[interbank_df["direction"] == "ASSET"], "amount")
        ib_liabilities = _frame_sum_by_date(interbank_df[interbank_df["direction"] == "LIABILITY"], "amount")

    return bonds_assets, bonds_liabilities, ib_assets, ib_liabilities


def calculate_adb(
    duckdb_path: str,
    start_date: date,
    end_date: date,
) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    if not Path(duckdb_path).exists():
        return _empty_adb_response(), [], [], []

    calendar_days = (end_date - start_date).days + 1
    all_days = [start_date + timedelta(days=i) for i in range(calendar_days)]
    bonds_df, interbank_df, source_versions, rule_versions, _adb_basis, adb_tables_used = _load_adb_raw_data(
        duckdb_path, start_date, end_date
    )
    if bonds_df.empty and interbank_df.empty:
        return _empty_adb_response(), source_versions, rule_versions, adb_tables_used

    bonds_assets, bonds_liabilities, ib_assets, ib_liabilities = _split_bonds_ib_by_side(bonds_df, interbank_df)
    daily_assets, daily_liabilities, total_assets_sum, total_liabilities_sum = aggregate_daily_totals(
        all_days, bonds_assets, bonds_liabilities, ib_assets, ib_liabilities
    )

    adb_days = max(_adb_distinct_snapshot_days(bonds_df, interbank_df), 1)
    nd = Decimal(str(adb_days))
    avg_assets = (total_assets_sum / nd) if nd else Decimal("0")
    avg_liabilities = (total_liabilities_sum / nd) if nd else Decimal("0")

    payload = {
        "summary": {
            "total_avg_assets": float(avg_assets),
            "total_avg_liabilities": float(avg_liabilities),
            "end_spot_assets": float(daily_assets.get(end_date, Decimal("0"))),
            "end_spot_liabilities": float(daily_liabilities.get(end_date, Decimal("0"))),
        },
        "trend": compute_adb_trend(all_days, daily_assets),
        "breakdown": _adb_breakdown_from_frames(bonds_df, interbank_df, adb_days),
    }
    return payload, source_versions, rule_versions, adb_tables_used


def _build_comparison_spot_sum_maps(
    bonds_df: pd.DataFrame,
    interbank_df: pd.DataFrame,
    end_date: date,
) -> tuple[dict[str, Decimal], dict[str, Decimal], dict[str, Decimal], dict[str, Decimal]]:
    """Accumulate spot (end_date) and period-sum maps for assets and liabilities."""
    spot_assets: dict[str, Decimal] = {}
    spot_liabilities: dict[str, Decimal] = {}
    sum_assets: dict[str, Decimal] = {}
    sum_liabilities: dict[str, Decimal] = {}

    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        bonds_asset_frame = bonds_df[~issued_mask]
        bonds_liab_frame = bonds_df[issued_mask]
        _accumulate_spot_and_sum_maps(
            bonds_asset_frame,
            amount_attr="market_value",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "bond_category", None),
            spot_map=spot_assets,
            sum_map=sum_assets,
        )
        _finalize_spot_map_locf_for_frame(
            bonds_asset_frame,
            amount_attr="market_value",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "bond_category", None),
            spot_map=spot_assets,
            sum_map=sum_assets,
        )
        _accumulate_spot_and_sum_maps(
            bonds_liab_frame,
            amount_attr="market_value",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "bond_category", None),
            spot_map=spot_liabilities,
            sum_map=sum_liabilities,
        )
        _finalize_spot_map_locf_for_frame(
            bonds_liab_frame,
            amount_attr="market_value",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "bond_category", None),
            spot_map=spot_liabilities,
            sum_map=sum_liabilities,
        )

    if not interbank_df.empty:
        ib_asset_frame = interbank_df[interbank_df["direction"] == "ASSET"]
        ib_liab_frame = interbank_df[interbank_df["direction"] == "LIABILITY"]
        _accumulate_spot_and_sum_maps(
            ib_asset_frame,
            amount_attr="amount",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "product_type", None),
            spot_map=spot_assets,
            sum_map=sum_assets,
        )
        _finalize_spot_map_locf_for_frame(
            ib_asset_frame,
            amount_attr="amount",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "product_type", None),
            spot_map=spot_assets,
            sum_map=sum_assets,
        )
        _accumulate_spot_and_sum_maps(
            ib_liab_frame,
            amount_attr="amount",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "product_type", None),
            spot_map=spot_liabilities,
            sum_map=sum_liabilities,
        )
        _finalize_spot_map_locf_for_frame(
            ib_liab_frame,
            amount_attr="amount",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "product_type", None),
            spot_map=spot_liabilities,
            sum_map=sum_liabilities,
        )

    return spot_assets, spot_liabilities, sum_assets, sum_liabilities


def _scale_decimal_map(values: dict[str, Decimal], factor: Decimal) -> dict[str, Decimal]:
    if factor == Decimal("1"):
        return dict(values)
    return {key: amount * factor for key, amount in values.items()}


def _empty_comparison_response(
    start_date: date,
    end_date: date,
    calendar_days_inclusive: int,
    detail: str | None = None,
    *,
    adb_denominator_basis: str = "snapshot_calendar",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "report_date": end_date.strftime("%Y-%m-%d"),
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "calendar_days_inclusive": calendar_days_inclusive,
        "adb_denominator_basis": adb_denominator_basis,
        "num_days": 0,
        "coverage_days": 0,
        "sample_filled": False,
        "sample_fill_method": "none",
        "simulated": False,
        "total_spot_assets": 0.0,
        "total_avg_assets": 0.0,
        "total_spot_liabilities": 0.0,
        "total_avg_liabilities": 0.0,
        "total_avg_interbank_assets": 0.0,
        "total_avg_interbank_liabilities": 0.0,
        "asset_yield": None,
        "liability_cost": None,
        "net_interest_margin": None,
        "assets_breakdown": [],
        "liabilities_breakdown": [],
    }
    if detail:
        payload["detail"] = detail
    return payload


def _append_other_row(
    breakdown: list[dict[str, Any]],
    total_spot: float,
    total_avg: float,
) -> list[dict[str, Any]]:
    """Append an '其他（未列示）' catch-all row when breakdown doesn't sum to total."""
    if not breakdown or total_avg <= 0:
        return breakdown
    breakdown_spot_sum = sum(row.get("spot_balance", 0) or 0 for row in breakdown)
    breakdown_avg_sum = sum(row.get("avg_balance", 0) or 0 for row in breakdown)
    residual_avg = total_avg - breakdown_avg_sum
    if abs(residual_avg) < 1.0:
        return breakdown
    residual_spot = total_spot - breakdown_spot_sum
    return [
        *breakdown,
        {
            "category": "其他（未列示）",
            "spot_balance": residual_spot,
            "avg_balance": residual_avg,
            "proportion": round(residual_avg / total_avg * 100, 2),
            "weighted_rate": None,
        },
    ]


def get_adb_comparison(
    duckdb_path: str,
    start_date: date,
    end_date: date,
    top_n: int = 20,
    simulate_if_single_snapshot: bool = True,
) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    calendar_days_inclusive = int((end_date - start_date).days) + 1
    calendar_days_dec = Decimal(str(max(calendar_days_inclusive, 1)))

    bonds_df, interbank_df, source_versions, rule_versions, adb_basis, adb_tables_used = _load_adb_raw_data(
        duckdb_path, start_date, end_date
    )
    if bonds_df.empty and interbank_df.empty:
        return (
            _empty_comparison_response(
                start_date,
                end_date,
                calendar_days_inclusive,
                adb_denominator_basis=adb_basis,
            ),
            source_versions,
            rule_versions,
            adb_tables_used,
        )

    spot_assets, spot_liabilities, sum_assets, sum_liabilities = _build_comparison_spot_sum_maps(
        bonds_df, interbank_df, end_date
    )

    snapshot_distinct_days = _adb_distinct_snapshot_days(bonds_df, interbank_df)
    calendar_denom = max(calendar_days_inclusive, 1)
    coverage_days = max(snapshot_distinct_days, 0)
    sample_filled = False
    sample_fill_method = "none"
    sum_assets_effective = dict(sum_assets)
    sum_liabilities_effective = dict(sum_liabilities)
    if coverage_days > 0 and coverage_days < calendar_denom:
        # Sparse snapshots: expand observed balance sum to full window as sample completion.
        fill_factor = Decimal(str(calendar_denom)) / Decimal(str(coverage_days))
        sum_assets_effective = _scale_decimal_map(sum_assets, fill_factor)
        sum_liabilities_effective = _scale_decimal_map(sum_liabilities, fill_factor)
        sample_filled = True
        sample_fill_method = "observed_days_scaled_to_calendar"

    simulated = bool(simulate_if_single_snapshot and calendar_days_inclusive <= 1)
    denom_dec = calendar_days_dec
    assets_all = build_comparison_rows(
        "Asset", spot_assets, sum_assets_effective, denom_dec, None, simulated, end_date, _stable_factor
    )
    liabilities_all = build_comparison_rows(
        "Liability", spot_liabilities, sum_liabilities_effective, denom_dec, None, simulated, end_date, _stable_factor
    )
    assets = assets_all[: max(int(top_n), 0)]
    liabilities = liabilities_all[: max(int(top_n), 0)]

    if simulated:
        total_spot_assets = float(sum(item["spot"] for item in assets_all))
        total_avg_assets = float(sum(item["avg"] for item in assets_all))
        total_spot_liabilities = float(sum(item["spot"] for item in liabilities_all))
        total_avg_liabilities = float(sum(item["avg"] for item in liabilities_all))
    else:
        total_spot_assets = float(sum(spot_assets.values(), start=Decimal("0")))
        total_avg_assets = float(sum(sum_assets_effective.values(), start=Decimal("0")) / calendar_days_dec)
        total_spot_liabilities = float(sum(spot_liabilities.values(), start=Decimal("0")))
        total_avg_liabilities = float(sum(sum_liabilities_effective.values(), start=Decimal("0")) / calendar_days_dec)

    asset_frames, liability_frames, *_ = _split_rate_frames(bonds_df, interbank_df)
    asset_rate_map, asset_yield = build_rate_map(asset_frames)
    liability_rate_map, liability_cost = build_rate_map(liability_frames)

    tyw_avg_days = coverage_days if coverage_days > 0 else calendar_denom
    tyw_avg_assets, tyw_avg_liabilities = _tyw_interval_avg_balances(interbank_df, tyw_avg_days)

    payload = {
        "report_date": end_date.strftime("%Y-%m-%d"),
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "calendar_days_inclusive": calendar_days_inclusive,
        "adb_denominator_basis": adb_basis,
        "num_days": calendar_days_inclusive,
        "coverage_days": coverage_days,
        "sample_filled": sample_filled,
        "sample_fill_method": sample_fill_method,
        "simulated": simulated,
        "total_spot_assets": total_spot_assets,
        "total_avg_assets": total_avg_assets,
        "total_spot_liabilities": total_spot_liabilities,
        "total_avg_liabilities": total_avg_liabilities,
        "total_avg_interbank_assets": tyw_avg_assets,
        "total_avg_interbank_liabilities": tyw_avg_liabilities,
        "asset_yield": asset_yield,
        "liability_cost": liability_cost,
        "net_interest_margin": compute_nim(asset_yield, liability_cost),
        "assets_breakdown": _append_other_row(enrich_breakdown(assets, total_avg_assets, asset_rate_map), total_spot_assets, total_avg_assets),
        "liabilities_breakdown": _append_other_row(enrich_breakdown(liabilities, total_avg_liabilities, liability_rate_map), total_spot_liabilities, total_avg_liabilities),
    }

    return payload, source_versions, rule_versions, adb_tables_used


def _build_month_breakdowns(
    month_bonds_assets: pd.DataFrame,
    month_bonds_liab: pd.DataFrame,
    month_ib_assets: pd.DataFrame,
    month_ib_liab: pd.DataFrame,
    num_days: int,
    avg_assets: float,
    avg_liabilities: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build and annotate asset/liability breakdown rows for a single month."""
    breakdown_assets = _frame_breakdown_rows(
        month_bonds_assets, category_attr="bond_category", amount_attr="market_value", num_days=num_days
    )
    breakdown_assets.extend(
        _frame_breakdown_rows(
            month_ib_assets, category_attr="product_type", amount_attr="amount", num_days=num_days, prefix="同业-"
        )
    )
    breakdown_liabilities = _frame_breakdown_rows(
        month_ib_liab, category_attr="product_type", amount_attr="amount", num_days=num_days, prefix="同业-"
    )
    breakdown_liabilities.extend(
        _frame_breakdown_rows(
            month_bonds_liab, category_attr="bond_category", amount_attr="market_value", num_days=num_days, prefix="发行债券-"
        )
    )
    for item in breakdown_assets:
        item["proportion"] = round(item["avg_balance"] / avg_assets * 100, 2) if avg_assets > 0 else 0
        item["side"] = "Asset"
    for item in breakdown_liabilities:
        item["proportion"] = round(item["avg_balance"] / avg_liabilities * 100, 2) if avg_liabilities > 0 else 0
        item["side"] = "Liability"
    breakdown_assets.sort(key=lambda row: row["avg_balance"], reverse=True)
    breakdown_liabilities.sort(key=lambda row: row["avg_balance"], reverse=True)
    return breakdown_assets, breakdown_liabilities


def _process_single_month(
    month_year: int,
    month_number: int,
    month_bonds_assets: pd.DataFrame,
    month_bonds_liab: pd.DataFrame,
    month_ib_assets: pd.DataFrame,
    month_ib_liab: pd.DataFrame,
    prev_avg_assets: float | None,
    prev_avg_liabilities: float | None,
) -> dict[str, Any] | None:
    """Process a single month's ADB data; return None if no data for that month.

    All four DataFrames are already restricted to the same calendar month (no full-year re-scan).
    """
    month_start, _ = month_date_range(month_year, month_number)
    if month_start > date.today():
        return None

    all_month_dates: set[date] = set()
    for frame in (month_bonds_assets, month_bonds_liab, month_ib_assets, month_ib_liab):
        all_month_dates.update(_frame_unique_dates(frame))
    if not all_month_dates:
        return None

    num_days = len(all_month_dates)
    total_assets, total_assets_weighted = 0.0, 0.0
    for frame, col in ((month_bonds_assets, "market_value"), (month_ib_assets, "amount")):
        ft, fw = _frame_total_amounts(frame, col)
        total_assets += ft
        total_assets_weighted += fw

    total_liabilities, total_liabilities_weighted = 0.0, 0.0
    for frame, col in ((month_bonds_liab, "market_value"), (month_ib_liab, "amount")):
        ft, fw = _frame_total_amounts(frame, col)
        total_liabilities += ft
        total_liabilities_weighted += fw

    if total_assets == 0 and total_liabilities == 0:
        return None

    avg_assets = total_assets / num_days if num_days > 0 else 0.0
    avg_liabilities = total_liabilities / num_days if num_days > 0 else 0.0

    breakdown_assets, breakdown_liabilities = _build_month_breakdowns(
        month_bonds_assets, month_bonds_liab, month_ib_assets, month_ib_liab,
        num_days, avg_assets, avg_liabilities,
    )

    last_data_date = max(all_month_dates)
    end_spot_assets = (
        _frame_spot_total_for_date(month_bonds_assets, "market_value", last_data_date)
        + _frame_spot_total_for_date(month_ib_assets, "amount", last_data_date)
    )
    end_spot_liabilities = (
        _frame_spot_total_for_date(month_bonds_liab, "market_value", last_data_date)
        + _frame_spot_total_for_date(month_ib_liab, "amount", last_data_date)
    )

    assets_mom, assets_mom_pct, liabilities_mom, liabilities_mom_pct = compute_mom_changes(
        avg_assets, avg_liabilities, prev_avg_assets, prev_avg_liabilities
    )
    asset_yield = compute_weighted_rate(total_assets_weighted, total_assets)
    liability_cost = compute_weighted_rate(total_liabilities_weighted, total_liabilities)

    return {
        "month": f"{month_year}-{month_number:02d}",
        "month_label": f"{month_year}年{month_number}月",
        "avg_assets": avg_assets,
        "avg_liabilities": avg_liabilities,
        "end_spot_assets": end_spot_assets,
        "end_spot_liabilities": end_spot_liabilities,
        "mom_change_assets": assets_mom,
        "mom_change_pct_assets": assets_mom_pct,
        "mom_change_liabilities": liabilities_mom,
        "mom_change_pct_liabilities": liabilities_mom_pct,
        "asset_yield": asset_yield,
        "liability_cost": liability_cost,
        "net_interest_margin": compute_nim(asset_yield, liability_cost),
        "breakdown_assets": breakdown_assets,
        "breakdown_liabilities": breakdown_liabilities,
        "num_days": num_days,
        # YTD accumulators — stripped by caller before appending to months_data
        "total_assets": total_assets,
        "total_assets_weighted": total_assets_weighted,
        "total_liabilities": total_liabilities,
        "total_liabilities_weighted": total_liabilities_weighted,
    }


def calculate_monthly_adb(duckdb_path: str, year: int) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    start_date = date(year, 1, 1)
    end_date = min(date(year, 12, 31), date.today())
    empty = {
        "year": year,
        "months": [],
        "ytd_avg_assets": 0.0,
        "ytd_avg_liabilities": 0.0,
        "ytd_asset_yield": None,
        "ytd_liability_cost": None,
        "ytd_nim": None,
        "unit": "percent",
    }

    bonds_df, interbank_df, source_versions, rule_versions, _adb_basis, adb_tables_used = _load_adb_raw_data(
        duckdb_path, start_date, end_date
    )
    if bonds_df.empty and interbank_df.empty:
        return empty, source_versions, rule_versions, adb_tables_used

    asset_frames, liability_frames, bonds_assets_df, bonds_liab_df, ib_assets_df, ib_liab_df = _split_rate_frames(
        bonds_df, interbank_df
    )
    all_dates: set[date] = set()
    all_dates.update(_frame_unique_dates(bonds_df))
    all_dates.update(_frame_unique_dates(interbank_df))
    if not all_dates:
        return empty, source_versions, rule_versions, adb_tables_used

    available_months = sorted({(current_day.year, current_day.month) for current_day in all_dates})

    ba_by_m = _group_frame_by_year_month(bonds_assets_df)
    bl_by_m = _group_frame_by_year_month(bonds_liab_df)
    iba_by_m = _group_frame_by_year_month(ib_assets_df)
    ibl_by_m = _group_frame_by_year_month(ib_liab_df)
    empty_ba = bonds_assets_df.head(0).copy() if not bonds_assets_df.empty else pd.DataFrame()
    empty_bl = bonds_liab_df.head(0).copy() if not bonds_liab_df.empty else pd.DataFrame()
    empty_iba = ib_assets_df.head(0).copy() if not ib_assets_df.empty else pd.DataFrame()
    empty_ibl = ib_liab_df.head(0).copy() if not ib_liab_df.empty else pd.DataFrame()

    months_data: list[dict[str, Any]] = []
    prev_avg_assets: float | None = None
    prev_avg_liabilities: float | None = None
    ytd_total_assets = Decimal("0")
    ytd_total_liabilities = Decimal("0")
    ytd_assets_weighted = Decimal("0")
    ytd_liabilities_weighted = Decimal("0")
    ytd_days = 0

    for month_year, month_number in available_months:
        mkey = (month_year, month_number)
        month_result = _process_single_month(
            month_year,
            month_number,
            ba_by_m.get(mkey, empty_ba),
            bl_by_m.get(mkey, empty_bl),
            iba_by_m.get(mkey, empty_iba),
            ibl_by_m.get(mkey, empty_ibl),
            prev_avg_assets,
            prev_avg_liabilities,
        )
        if month_result is None:
            continue

        ytd_total_assets += Decimal(str(month_result["total_assets"]))
        ytd_total_liabilities += Decimal(str(month_result["total_liabilities"]))
        ytd_assets_weighted += Decimal(str(month_result["total_assets_weighted"]))
        ytd_liabilities_weighted += Decimal(str(month_result["total_liabilities_weighted"]))
        ytd_days += month_result["num_days"]

        month_result.pop("total_assets")
        month_result.pop("total_assets_weighted")
        month_result.pop("total_liabilities")
        month_result.pop("total_liabilities_weighted")

        months_data.append(month_result)
        prev_avg_assets = month_result["avg_assets"]
        prev_avg_liabilities = month_result["avg_liabilities"]

    ytd_asset_yield = compute_weighted_rate(float(ytd_assets_weighted), float(ytd_total_assets))
    ytd_liability_cost = compute_weighted_rate(float(ytd_liabilities_weighted), float(ytd_total_liabilities))

    payload = {
        "year": year,
        "months": months_data,
        "ytd_avg_assets": float(ytd_total_assets / ytd_days) if ytd_days > 0 else 0.0,
        "ytd_avg_liabilities": float(ytd_total_liabilities / ytd_days) if ytd_days > 0 else 0.0,
        "ytd_asset_yield": ytd_asset_yield,
        "ytd_liability_cost": ytd_liability_cost,
        "ytd_nim": compute_nim(ytd_asset_yield, ytd_liability_cost),
        "unit": "percent",
    }
    return payload, source_versions, rule_versions, adb_tables_used


def adb_envelope_for_dates(start_date: str, end_date: str) -> dict[str, Any]:
    settings = get_settings()
    payload, source_versions, rule_versions, adb_tables_used = calculate_adb(
        str(settings.duckdb_path),
        _parse_date(start_date),
        _parse_date(end_date),
    )
    tables_for_calibration = adb_tables_used or [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    ]
    envelope = _build_analytical_envelope(
        result_kind="adb.daily",
        result_payload=payload,
        source_versions=source_versions,
        rule_versions=rule_versions,
        filters_applied={"start_date": start_date, "end_date": end_date},
        tables_used=tables_for_calibration,
    )
    calibration_meta = build_adb_daily_balance_calibration_meta(tables_for_calibration)
    return {
        **envelope,
        "calibration": balance_calibration_meta_to_dict(calibration_meta),
    }


def adb_comparison_envelope(start_date: str, end_date: str, top_n: int = 20) -> dict[str, Any]:
    return _cached_adb_comparison_envelope(str(start_date), str(end_date), int(top_n))


@lru_cache(maxsize=32)
def _cached_adb_comparison_envelope(start_date: str, end_date: str, top_n: int) -> dict[str, Any]:
    return _adb_comparison_envelope_uncached(start_date, end_date, top_n)


def clear_adb_comparison_cache() -> None:
    _cached_adb_comparison_envelope.cache_clear()


def _adb_comparison_envelope_uncached(start_date: str, end_date: str, top_n: int = 20) -> dict[str, Any]:
    settings = get_settings()
    parsed_start_date = _parse_date(start_date)
    parsed_end_date = _parse_date(end_date)
    payload, source_versions, rule_versions, adb_tables_used = get_adb_comparison(
        str(settings.duckdb_path),
        parsed_start_date,
        parsed_end_date,
        top_n=top_n,
    )
    tables_for_calibration = adb_tables_used or [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    ]
    envelope = _build_analytical_envelope(
        result_kind="adb.comparison",
        result_payload=payload,
        source_versions=source_versions,
        rule_versions=rule_versions,
        filters_applied={
            "start_date": start_date,
            "end_date": end_date,
        },
        tables_used=tables_for_calibration,
    )
    calibration_meta = build_adb_daily_balance_calibration_meta(tables_for_calibration)
    return {
        **envelope,
        "calibration": balance_calibration_meta_to_dict(calibration_meta),
    }


def adb_monthly_envelope(year: int) -> dict[str, Any]:
    settings = get_settings()
    payload, source_versions, rule_versions, adb_tables_used = calculate_monthly_adb(
        str(settings.duckdb_path),
        year,
    )
    tables_for_calibration = adb_tables_used or [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    ]
    envelope = _build_analytical_envelope(
        result_kind="adb.monthly",
        result_payload=payload,
        source_versions=source_versions,
        rule_versions=rule_versions,
        filters_applied={"year": year},
        tables_used=tables_for_calibration,
    )
    calibration_meta = build_adb_daily_balance_calibration_meta(tables_for_calibration)
    return {
        **envelope,
        "calibration": balance_calibration_meta_to_dict(calibration_meta),
    }
