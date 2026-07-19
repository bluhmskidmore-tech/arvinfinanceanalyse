from __future__ import annotations

import logging
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_DATA_SOURCES = ("choice", "tushare")

_WARNED_SOURCE_GAPS: set[str] = set()


def _warn_source_gap_once(gap_key: str, message: str, *args: object) -> None:
    if gap_key in _WARNED_SOURCE_GAPS:
        return
    _WARNED_SOURCE_GAPS.add(gap_key)
    logger.warning(message, *args)


def _warn_missing_table_once(table_name: str) -> None:
    _warn_source_gap_once(
        f"table_missing:{table_name}",
        "system macro source table %s is missing; this source contributes an empty frame",
        table_name,
    )

_LEGACY_ALIAS_CANDIDATES: dict[str, tuple[str, ...]] = {
    "000300.sh": ("CA.CSI300", "000300.SH", "index_daily:000300.SH.close"),
    "sh000300": ("CA.CSI300", "000300.SH", "index_daily:000300.SH.close"),
    "000905.sh": ("CA.CSI500", "000905.SH", "index_daily:000905.SH.close"),
    "sh000905": ("CA.CSI500", "000905.SH", "index_daily:000905.SH.close"),
    "cu0": ("CA.COPPER", "CU.SHF", "fut_daily:CU.SHF.close"),
    "cu0.shf": ("CA.COPPER", "CU.SHF", "fut_daily:CU.SHF.close"),
    "al0": ("CA.ALUMINUM", "AL.SHF", "fut_daily:AL.SHF.close"),
    "al0.shf": ("CA.ALUMINUM", "AL.SHF", "fut_daily:AL.SHF.close"),
    "m0000545": ("EMM00008445",),
    "m0000612": ("EMM00072301", "cn_cpi_yoy", "tushare.macro.cn_cpi.monthly"),
    "edb-cpi-yoy": ("cn_cpi_yoy", "tushare.macro.cn_cpi.monthly"),
    "m0001227": ("cn_ppi_yoy", "tushare.macro.cn_ppi.monthly"),
    "edb-ppi-yoy": ("cn_ppi_yoy", "tushare.macro.cn_ppi.monthly"),
    "tushare.macro.cn_ppi.monthly": ("cn_ppi_yoy", "m0001227", "edb-ppi-yoy"),
    "m0001385": ("cn_m2_yoy", "tushare.macro.cn_money.monthly"),
    "edb-m2-yoy": ("cn_m2_yoy", "tushare.macro.cn_money.monthly"),
    "tushare.macro.cn_money.monthly": ("cn_m2_yoy", "m0001385", "edb-m2-yoy"),
    "m5525763": ("EMM00191807",),
    "m0067855": ("EMM00058124", "legacy.fx.choice.USD.CNY", "fx_daily_mid:USD/CNY", "USD/CNY", "USDCNY"),
    "usd/cny": ("EMM00058124", "legacy.fx.choice.USD.CNY", "fx_daily_mid:USD/CNY"),
    "usdcny": ("EMM00058124", "legacy.fx.choice.USD.CNY", "fx_daily_mid:USD/CNY", "USD/CNY"),
    "nh0100.nhf": ("NHCI.NH", "tushare.index_daily.NHCI.NH.close"),
    "nhci.nh": ("NH0100.NHF", "tushare.index_daily.NHCI.NH.close"),
    # 7D OMO reverse-repo: Choice EDB target remains EMM00088132 (crisis backfill vendor
    # code), but the only currently populated runtime series is the legacy external carry
    # source. Prefer the populated series first so alias resolution / source_check evidence
    # does not present an empty Choice code as the primary hit.
    "m0041653": (
        "legacy.wind_market_db.reverse_repo_7d",
        "cn_repo_7d",
        "M001",
        "公开市场7天逆回购利率",
        "EMM00088132",
    ),
    "cn-repo-7d": (
        "legacy.wind_market_db.reverse_repo_7d",
        "M001",
        "m0041653",
        "公开市场7天逆回购利率",
        "EMM00088132",
    ),
    "m001": (
        "legacy.wind_market_db.reverse_repo_7d",
        "cn_repo_7d",
        "m0041653",
        "公开市场7天逆回购利率",
        "EMM00088132",
    ),
    "公开市场7天逆回购利率": (
        "legacy.wind_market_db.reverse_repo_7d",
        "M001",
        "cn_repo_7d",
        "m0041653",
        "EMM00088132",
    ),
    # Manufacturing PMI is not in choice_macro_catalog; it lands in fact_choice_macro_daily
    # via cycle_rotation / NBS PMI release / tushare cn_pmi (see config/cycle_rotation_macro_series.json).
    "m0017126": ("制造业PMI", "pmi", "cn_pmi"),
    "制造业pmi": ("M0017126", "pmi", "cn_pmi"),
    # Keys are looked up after _normalize_alias (underscore -> hyphen).
    "cn-pmi": ("M0017126", "制造业PMI", "pmi"),
    "m0041813": ("NCD.SHIBOR.3M", "shibor:3m"),
    "dr007.ib": ("CA.DR007", "repo_rate_query:FDR007", "DR007.IB"),
    "s0059743": ("EMM00166458", "legacy.yield.choice.treasury.1Y", "legacy.yield.akshare.treasury.1Y"),
    "s0059745": ("EMM00588704", "legacy.yield.choice.treasury.2Y", "legacy.yield.akshare.treasury.2Y"),
    "s0059746": ("EMM00166460", "legacy.yield.choice.treasury.3Y", "legacy.yield.akshare.treasury.3Y"),
    "s0059747": (
        "EMM00166462",
        "legacy.yield.choice.treasury.5Y",
        "legacy.yield.akshare.treasury.5Y",
        "tushare.yc_cb.1001.CB.5Y",
    ),
    "s0059748": ("EMM00166464", "legacy.yield.choice.treasury.7Y", "legacy.yield.akshare.treasury.7Y"),
    "s0059749": ("EMM00166466", "E1000180", "legacy.yield.choice.treasury.10Y", "legacy.yield.akshare.treasury.10Y"),
    "s0059751": ("EMM00166468", "legacy.yield.choice.treasury.20Y", "legacy.yield.akshare.treasury.20Y"),
    "s0059752": ("EMM00166469", "legacy.yield.choice.treasury.30Y", "legacy.yield.akshare.treasury.30Y"),
    "s0059650": ("legacy.yield.choice.aaa_credit.1Y", "EMM00166655"),
    "s0059651": ("legacy.yield.choice.aaa_credit.3Y", "EMM00166657"),
    "s0059652": ("legacy.yield.choice.aaa_credit.5Y", "EMM00166659"),
    "s0059653": ("legacy.yield.choice.aa_plus_credit.1Y",),
    "s0059654": ("legacy.yield.choice.aa_plus_credit.3Y",),
    "s0059655": ("legacy.yield.choice.aa_plus_credit.5Y",),
    "s0059656": ("legacy.yield.choice.aa_credit.1Y", "EMM00166679"),
    "s0059657": ("legacy.yield.choice.aa_credit.3Y", "EMM00166681"),
    "s0059658": ("legacy.yield.choice.aa_credit.5Y", "EMM00166683"),
    "s0059670": ("legacy.yield.moss_derived.credit_spread_aaa.3Y",),
    "s0059671": ("legacy.yield.moss_derived.credit_spread_aa_plus.3Y",),
    "s0059672": ("legacy.yield.moss_derived.credit_spread_aa.3Y",),
    "s0059760": ("legacy.yield.choice.aa_credit.5Y", "EMM00166683", "legacy.yield.wind_legacy_market_db.aa_credit.5Y"),
}

_SOURCE_PRIORITY = {
    "choice": 0,
    "fx_daily_mid": 0,
    "public_bond_zh_us_rate": 0,
    "public_repo_rate_query": 0,
    "akshare": 1,
    "wind_legacy_market_db": 1,
    "tushare": 1,
    "moss_derived": 2,
}


def resolve_system_duckdb_path(duckdb_path: str | Path | None = None) -> Path:
    if duckdb_path is not None:
        return Path(duckdb_path)

    from backend.app.governance.settings import get_settings  # noqa: PLC0415

    return Path(get_settings().duckdb_path)


def load_system_macro_frame(
    duckdb_path: str | Path | None = None,
    *,
    series_ids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Load the concatenated system macro frame.

    ``series_ids`` is an internal pushdown filter: when provided, each source
    query is restricted to those series ids in SQL instead of fetching whole
    tables into pandas. ``None`` keeps the historical full-table behaviour.
    """
    path = resolve_system_duckdb_path(duckdb_path)
    if not path.exists():
        _warn_source_gap_once(
            f"duckdb_missing:{path}",
            "system macro source duckdb file %s is missing; returning empty frame",
            path,
        )
        return _empty_frame()

    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        _warn_source_gap_once(
            f"duckdb_connect_failed:{path}",
            "system macro source duckdb connect failed for %s (%s); returning empty frame",
            path,
            exc,
        )
        return _empty_frame()

    try:
        frames = [
            _load_choice_frame(conn, series_ids=series_ids),
            _load_choice_snapshot_frame(conn, series_ids=series_ids),
            _load_external_macro_frame(conn, series_ids=series_ids),
            _load_commodity_daily_frame(conn, series_ids=series_ids),
            _load_fx_frame(conn, series_ids=series_ids),
            _load_legacy_yield_curve_frame(conn, series_ids=series_ids),
        ]
    finally:
        conn.close()

    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return _empty_frame()

    out = pd.concat(frames, ignore_index=True)
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
    out["value_numeric"] = pd.to_numeric(out["value_numeric"], errors="coerce")
    out = out.dropna(subset=["trade_date", "value_numeric"])
    out["source_priority"] = out["vendor_name"].map(_SOURCE_PRIORITY).fillna(9).astype(int)
    return out.sort_values(["series_id", "trade_date", "source_priority"]).reset_index(drop=True)


def _system_macro_cache_key(duckdb_path: str | Path | None = None) -> tuple[str, int, int] | None:
    path = resolve_system_duckdb_path(duckdb_path)
    if not path.exists():
        _warn_source_gap_once(
            f"duckdb_missing:{path}",
            "system macro source duckdb file %s is missing; returning empty frame",
            path,
        )
        return None
    try:
        stat = path.stat()
    except OSError as exc:
        _warn_source_gap_once(
            f"duckdb_stat_failed:{path}",
            "system macro source duckdb stat failed for %s (%s); returning empty frame",
            path,
            exc,
        )
        return None
    return (str(path.resolve()), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=8)
def _load_alias_triple_index_cache(
    path: str,
    mtime_ns: int,
    size: int,
) -> dict[str, tuple[tuple[str, str, str], ...]]:
    return _build_alias_triple_index(_load_alias_identity_frame(Path(path)))


@lru_cache(maxsize=256)
def _load_series_subset_frame_cache(
    path: str,
    mtime_ns: int,
    size: int,
    series_ids: tuple[str, ...],
) -> pd.DataFrame:
    return load_system_macro_frame(Path(path), series_ids=series_ids)


def clear_system_macro_source_cache() -> None:
    _load_alias_triple_index_cache.cache_clear()
    _load_series_subset_frame_cache.cache_clear()
    _WARNED_SOURCE_GAPS.clear()


def load_series_by_alias(
    alias: str,
    *,
    start: str | None = None,
    end: str | None = None,
    duckdb_path: str | Path | None = None,
) -> pd.DataFrame:
    cache_key = _system_macro_cache_key(duckdb_path)
    if cache_key is None:
        return _empty_series_frame()

    triple_index = _load_alias_triple_index_cache(*cache_key)
    candidates = _candidate_aliases(alias)
    matched_triples = {triple for candidate in candidates for triple in triple_index.get(candidate, ())}
    if not matched_triples:
        return _empty_series_frame()

    series_ids = tuple(sorted({triple[0] for triple in matched_triples}))
    frame = _load_series_subset_frame_cache(*cache_key, series_ids)
    if frame.empty:
        return _empty_series_frame()

    row_matches = [
        (
            _alias_source_text(series_id),
            _alias_source_text(series_name),
            _alias_source_text(vendor_series_code),
        )
        in matched_triples
        for series_id, series_name, vendor_series_code in zip(
            frame["series_id"],
            frame["series_name"],
            frame["vendor_series_code"],
            strict=True,
        )
    ]
    selected = frame[row_matches].copy()
    if selected.empty:
        return _empty_series_frame()

    if start:
        selected = selected[selected["trade_date"] >= pd.to_datetime(start, errors="coerce")]
    if end:
        selected = selected[selected["trade_date"] <= pd.to_datetime(end, errors="coerce")]
    if selected.empty:
        return _empty_series_frame()

    selected = selected.sort_values(["trade_date", "source_priority"]).drop_duplicates("trade_date", keep="first")
    return selected[["trade_date", "value_numeric", "series_id", "vendor_name"]].rename(
        columns={"trade_date": "date", "value_numeric": "value"},
    )


def load_series_by_aliases(
    aliases: Iterable[str],
    *,
    start: str | None = None,
    end: str | None = None,
    duckdb_path: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    requested_aliases = tuple(dict.fromkeys(str(alias) for alias in aliases))
    if not requested_aliases:
        return {}

    cache_key = _system_macro_cache_key(duckdb_path)
    if cache_key is None:
        return {alias: _empty_series_frame() for alias in requested_aliases}

    triple_index = _load_alias_triple_index_cache(*cache_key)
    triples_by_alias: dict[str, set[tuple[str, str, str]]] = {}
    for alias in requested_aliases:
        candidates = _candidate_aliases(alias)
        triples_by_alias[alias] = {
            triple for candidate in candidates for triple in triple_index.get(candidate, ())
        }

    series_ids = tuple(
        sorted({triple[0] for matched_triples in triples_by_alias.values() for triple in matched_triples})
    )
    if not series_ids:
        return {alias: _empty_series_frame() for alias in requested_aliases}

    frame = _load_series_subset_frame_cache(*cache_key, series_ids)
    if frame.empty:
        return {alias: _empty_series_frame() for alias in requested_aliases}

    out: dict[str, pd.DataFrame] = {}
    for alias, matched_triples in triples_by_alias.items():
        if not matched_triples:
            out[alias] = _empty_series_frame()
            continue

        row_matches = [
            (
                _alias_source_text(series_id),
                _alias_source_text(series_name),
                _alias_source_text(vendor_series_code),
            )
            in matched_triples
            for series_id, series_name, vendor_series_code in zip(
                frame["series_id"],
                frame["series_name"],
                frame["vendor_series_code"],
                strict=True,
            )
        ]
        selected = frame[row_matches].copy()
        if start:
            selected = selected[selected["trade_date"] >= pd.to_datetime(start, errors="coerce")]
        if end:
            selected = selected[selected["trade_date"] <= pd.to_datetime(end, errors="coerce")]
        if selected.empty:
            out[alias] = _empty_series_frame()
            continue

        selected = selected.sort_values(["trade_date", "source_priority"]).drop_duplicates("trade_date", keep="first")
        out[alias] = selected[["trade_date", "value_numeric", "series_id", "vendor_name"]].rename(
            columns={"trade_date": "date", "value_numeric": "value"},
        )
    return out


_CHOICE_FACT_SQL = """
select
  series_id, series_name, trade_date, value_numeric,
  frequency, unit, source_version, vendor_version, rule_version, run_id
from fact_choice_macro_daily
"""

_CHOICE_CATALOG_SQL = """
select series_id, max(series_name) as catalog_series_name,
       max(vendor_name) as catalog_vendor_name,
       max(vendor_series_code) as vendor_series_code
from phase1_macro_vendor_catalog
group by series_id
"""

_CHOICE_SNAPSHOT_VENDOR_SQL = """
select series_id, max(vendor_name) as snapshot_vendor_name,
       max(vendor_series_code) as snapshot_vendor_series_code
from choice_market_snapshot
group by series_id
"""

_CHOICE_SNAPSHOT_SQL = """
select
  series_id, series_name, vendor_name, trade_date, value_numeric,
  frequency, unit, source_version, vendor_version, rule_version, run_id,
  vendor_series_code
from choice_market_snapshot
"""

_EXTERNAL_STD_SQL = """
select
  series_id, vendor_name, trade_date, value_numeric, frequency, unit,
  source_version, vendor_version, rule_version, ingest_batch_id as run_id
from std_external_macro_daily
where lower(vendor_name) in ('tushare', 'wind_legacy_market_db', 'moss_derived')
"""

_EXTERNAL_CATALOG_SQL = """
select series_id, max(series_name) as catalog_series_name
from external_data_catalog
where lower(vendor_name) in ('tushare', 'wind_legacy_market_db', 'moss_derived')
group by series_id
"""

_COMMODITY_DAILY_SQL = """
select
  case
    when upper(product_code) = 'NHCI' then 'NHCI.NH'
    when upper(product_code) = 'NHII' then 'NHII.NH'
    when upper(product_code) = 'CU' then 'CA.COPPER'
    when upper(product_code) = 'AL' then 'CA.ALUMINUM'
    else 'COMMODITY.' || upper(product_code)
  end as series_id,
  case
    when upper(product_code) = 'NHCI' then 'Nanhua commodity index'
    when upper(product_code) = 'NHII' then 'Nanhua industrial index'
    else upper(product_code) || ' commodity futures close'
  end as series_name,
  case
    when lower(coalesce(vendor_version, '')) like 'vv_akshare%' then 'akshare'
    else 'tushare'
  end as vendor_name,
  trade_date,
  cast(close_value as double) as value_numeric,
  'daily' as frequency,
  case
    when upper(product_code) in ('NHCI', 'NHII') then 'index'
    else 'price'
  end as unit,
  source_version,
  vendor_version,
  rule_version,
  source_version as run_id,
  case
    when upper(product_code) in ('NHCI', 'NHII')
      then 'tushare.index_daily.' || coalesce(nullif(contract_code, ''), upper(product_code) || '.NH') || '.close'
    else 'fut_daily:' || upper(product_code) || '.' || upper(coalesce(exchange, '')) || '.close'
  end as vendor_series_code
from fact_commodity_futures_daily
where close_value is not null
"""

_FX_SQL = """
select
  case
    when upper(base_currency) = 'USD' and upper(quote_currency) = 'CNY'
      then 'EMM00058124'
    else 'legacy.fx.' || lower(coalesce(vendor_name, 'choice')) || '.'
         || upper(base_currency) || '.' || upper(quote_currency)
  end as series_id,
  'FX mid: ' || upper(base_currency) || '/' || upper(quote_currency) as series_name,
  coalesce(nullif(vendor_name, ''), 'choice') as vendor_name,
  cast(trade_date as varchar) as trade_date,
  cast(mid_rate as double) as value_numeric,
  'daily' as frequency,
  upper(quote_currency) || '/' || upper(base_currency) as unit,
  source_version,
  vendor_version,
  'rv_fx_daily_mid_system_source_v1' as rule_version,
  source_name as run_id,
  coalesce(nullif(vendor_series_code, ''), 'fx_daily_mid:' || upper(base_currency) || '/' || upper(quote_currency))
    as vendor_series_code
from fx_daily_mid
"""

_LEGACY_YIELD_CURVE_SQL = """
select
  'legacy.yield.' || lower(vendor_name) || '.' || curve_type || '.' || tenor as series_id,
  curve_type || ' yield curve ' || tenor as series_name,
  vendor_name,
  trade_date,
  cast(rate_pct as double) as value_numeric,
  'daily' as frequency,
  '%' as unit,
  source_version,
  vendor_version,
  rule_version,
  source_version as run_id,
  'legacy.yield.' || lower(vendor_name) || '.' || curve_type || '.' || tenor as vendor_series_code
from fact_formal_yield_curve_daily
where lower(vendor_name) in ('choice', 'tushare', 'akshare', 'moss_derived')
"""


def _fetch_source_frame(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    series_ids: tuple[str, ...] | None,
) -> pd.DataFrame:
    if series_ids is None:
        return conn.execute(sql).fetchdf()
    if not series_ids:
        return conn.execute(f"select * from ({sql}) src where 1 = 0").fetchdf()
    placeholders = ", ".join("?" for _ in series_ids)
    return conn.execute(
        f"select * from ({sql}) src where src.series_id in ({placeholders})",
        list(series_ids),
    ).fetchdf()


def _load_choice_frame(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_ids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    if not _table_exists(conn, "fact_choice_macro_daily"):
        _warn_missing_table_once("fact_choice_macro_daily")
        return _empty_frame()

    fact = _fetch_source_frame(conn, _CHOICE_FACT_SQL, series_ids)
    if fact.empty:
        return _empty_frame()

    fact = _apply_choice_vendor_merges(conn, fact, series_ids=series_ids)
    return _normalize_frame(fact)


def _apply_choice_vendor_merges(
    conn: duckdb.DuckDBPyConnection,
    fact: pd.DataFrame,
    *,
    series_ids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    fact["vendor_name"] = "choice"
    fact["vendor_series_code"] = ""
    if _table_exists(conn, "phase1_macro_vendor_catalog"):
        catalog = _fetch_source_frame(conn, _CHOICE_CATALOG_SQL, series_ids)
        fact = fact.merge(catalog, on="series_id", how="left")
        fact["series_name"] = fact["series_name"].fillna(fact["catalog_series_name"])
        fact["vendor_name"] = fact["catalog_vendor_name"].fillna(fact["vendor_name"])
        fact["vendor_series_code"] = fact["vendor_series_code_y"].fillna(fact["vendor_series_code_x"]).fillna("")
        fact = fact.drop(
            columns=[
                "catalog_series_name",
                "catalog_vendor_name",
                "vendor_series_code_x",
                "vendor_series_code_y",
            ],
        )

    if _table_exists(conn, "choice_market_snapshot"):
        snapshot = _fetch_source_frame(conn, _CHOICE_SNAPSHOT_VENDOR_SQL, series_ids)
        fact = fact.merge(snapshot, on="series_id", how="left")
        fact["vendor_name"] = fact["snapshot_vendor_name"].fillna(fact["vendor_name"])
        fact["vendor_series_code"] = fact["vendor_series_code"].fillna("")
        fact["vendor_series_code"] = fact["vendor_series_code"].where(
            fact["vendor_series_code"].astype(str) != "",
            fact["snapshot_vendor_series_code"],
        ).fillna("")
        fact = fact.drop(columns=["snapshot_vendor_name", "snapshot_vendor_series_code"])

    return fact


def _load_choice_snapshot_frame(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_ids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    if not _table_exists(conn, "choice_market_snapshot"):
        _warn_missing_table_once("choice_market_snapshot")
        return _empty_frame()

    snapshot = _fetch_source_frame(conn, _CHOICE_SNAPSHOT_SQL, series_ids)
    if snapshot.empty:
        return _empty_frame()
    return _normalize_frame(snapshot)


def _load_external_macro_frame(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_ids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    if not _table_exists(conn, "std_external_macro_daily"):
        _warn_missing_table_once("std_external_macro_daily")
        return _empty_frame()

    std = _fetch_source_frame(conn, _EXTERNAL_STD_SQL, series_ids)
    if std.empty:
        return _empty_frame()

    std["series_name"] = std["series_id"]
    std["vendor_series_code"] = ""
    std = _apply_external_catalog_names(conn, std, series_ids=series_ids)
    return _normalize_frame(std)


def _apply_external_catalog_names(
    conn: duckdb.DuckDBPyConnection,
    std: pd.DataFrame,
    *,
    series_ids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    if _table_exists(conn, "external_data_catalog"):
        catalog = _fetch_source_frame(conn, _EXTERNAL_CATALOG_SQL, series_ids)
        std = std.merge(catalog, on="series_id", how="left")
        std["series_name"] = std["catalog_series_name"].fillna(std["series_name"])
        std = std.drop(columns=["catalog_series_name"])
    return std


def _load_commodity_daily_frame(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_ids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    if not _table_exists(conn, "fact_commodity_futures_daily"):
        _warn_missing_table_once("fact_commodity_futures_daily")
        return _empty_frame()

    commodity = _fetch_source_frame(conn, _COMMODITY_DAILY_SQL, series_ids)
    if commodity.empty:
        return _empty_frame()
    return _normalize_frame(commodity)


def _load_fx_frame(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_ids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    if not _table_exists(conn, "fx_daily_mid"):
        _warn_missing_table_once("fx_daily_mid")
        return _empty_frame()

    fx = _fetch_source_frame(conn, _FX_SQL, series_ids)
    if fx.empty:
        return _empty_frame()
    return _normalize_frame(fx)


def _load_legacy_yield_curve_frame(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_ids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    if not _table_exists(conn, "fact_formal_yield_curve_daily"):
        _warn_missing_table_once("fact_formal_yield_curve_daily")
        return _empty_frame()

    curve = _fetch_source_frame(conn, _LEGACY_YIELD_CURVE_SQL, series_ids)
    if curve.empty:
        return _empty_frame()
    return _normalize_frame(curve)


_IDENTITY_COLUMNS = ("series_id", "series_name", "vendor_series_code")


def _empty_identity_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(_IDENTITY_COLUMNS))


def _load_alias_identity_frame(path: Path) -> pd.DataFrame:
    """Load the distinct (series_id, series_name, vendor_series_code) catalog.

    Alias resolution only depends on these three identity columns, so the
    alias index can be built from a cheap SQL ``distinct`` per source instead
    of fetching every fact row into pandas.
    """
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        _warn_source_gap_once(
            f"duckdb_connect_failed:{path}",
            "system macro source duckdb connect failed for %s (%s); returning empty frame",
            path,
            exc,
        )
        return _empty_identity_frame()

    try:
        frames = [
            _load_choice_identity_frame(conn),
            _load_source_identity_frame(conn, "choice_market_snapshot", _CHOICE_SNAPSHOT_SQL),
            _load_external_identity_frame(conn),
            _load_source_identity_frame(conn, "fact_commodity_futures_daily", _COMMODITY_DAILY_SQL),
            _load_source_identity_frame(conn, "fx_daily_mid", _FX_SQL),
            _load_source_identity_frame(conn, "fact_formal_yield_curve_daily", _LEGACY_YIELD_CURVE_SQL),
        ]
    finally:
        conn.close()

    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return _empty_identity_frame()
    return pd.concat(frames, ignore_index=True)


def _load_choice_identity_frame(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not _table_exists(conn, "fact_choice_macro_daily"):
        _warn_missing_table_once("fact_choice_macro_daily")
        return _empty_identity_frame()

    fact = conn.execute(
        "select distinct series_id, series_name from fact_choice_macro_daily"
    ).fetchdf()
    if fact.empty:
        return _empty_identity_frame()
    fact = _apply_choice_vendor_merges(conn, fact)
    return fact[list(_IDENTITY_COLUMNS)]


def _load_external_identity_frame(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not _table_exists(conn, "std_external_macro_daily"):
        _warn_missing_table_once("std_external_macro_daily")
        return _empty_identity_frame()

    std = conn.execute(
        """
        select distinct series_id
        from std_external_macro_daily
        where lower(vendor_name) in ('tushare', 'wind_legacy_market_db', 'moss_derived')
        """
    ).fetchdf()
    if std.empty:
        return _empty_identity_frame()
    std["series_name"] = std["series_id"]
    std["vendor_series_code"] = ""
    std = _apply_external_catalog_names(conn, std)
    return std[list(_IDENTITY_COLUMNS)]


def _load_source_identity_frame(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    sql: str,
) -> pd.DataFrame:
    if not _table_exists(conn, table_name):
        _warn_missing_table_once(table_name)
        return _empty_identity_frame()

    return conn.execute(
        f"select distinct series_id, series_name, vendor_series_code from ({sql}) src"
    ).fetchdf()


def _alias_source_text(value: object) -> str:
    return str(value or "")


def _build_alias_triple_index(frame: pd.DataFrame) -> dict[str, tuple[tuple[str, str, str], ...]]:
    if frame.empty:
        return {}
    triples_by_alias: dict[str, set[tuple[str, str, str]]] = {}
    seen: set[tuple[str, str, str]] = set()
    for _, row in frame.iterrows():
        triple = (
            _alias_source_text(row.get("series_id")),
            _alias_source_text(row.get("series_name")),
            _alias_source_text(row.get("vendor_series_code")),
        )
        if triple in seen:
            continue
        seen.add(triple)
        for alias in _row_aliases(row):
            triples_by_alias.setdefault(alias, set()).add(triple)
    return {alias: tuple(sorted(triples)) for alias, triples in triples_by_alias.items()}


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    columns = _empty_frame().columns
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out["vendor_name"] = out["vendor_name"].fillna("").astype(str).str.lower()
    return out[list(columns)]


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    try:
        return bool(
            conn.execute(
                "select count(*) from information_schema.tables where table_name = ?",
                [table_name],
            ).fetchone()[0]
        )
    except duckdb.Error as exc:
        _warn_source_gap_once(
            f"table_probe_failed:{table_name}",
            "system macro source table probe failed for %s (%s); treating table as missing",
            table_name,
            exc,
        )
        return False


def _candidate_aliases(alias: str) -> set[str]:
    raw = _normalize_alias(alias)
    candidates = {raw}
    candidates.update(_normalize_alias(item) for item in _LEGACY_ALIAS_CANDIDATES.get(raw, ()))
    if raw.startswith("sh") and len(raw) == 8:
        candidates.add(f"{raw[2:]}.sh")
    if raw.startswith("sz") and len(raw) == 8:
        candidates.add(f"{raw[2:]}.sz")
    return candidates


def _row_aliases(row: pd.Series) -> set[str]:
    values = [
        row.get("series_id", ""),
        row.get("series_name", ""),
        row.get("vendor_series_code", ""),
    ]
    aliases = {_normalize_alias(value) for value in values if str(value or "").strip()}
    for value in values:
        aliases.update(_expanded_vendor_aliases(str(value or "")))
    for alias in tuple(aliases):
        aliases.update(_candidate_aliases(alias))
    return aliases


def _expanded_vendor_aliases(value: str) -> set[str]:
    parts = [str(value or "")]
    if ":" in parts[0]:
        parts.append(parts[0].split(":", 1)[1])

    aliases: set[str] = set()
    for part in parts:
        expansion_parts = {part}
        normalized = _normalize_alias(part)
        if normalized:
            aliases.add(normalized)
        lowered = part.lower()
        for suffix in (".close", ".pct_chg", ".value"):
            if lowered.endswith(suffix):
                stripped = part[: -len(suffix)]
                expansion_parts.add(stripped)
                aliases.add(_normalize_alias(stripped))
        for alias_part in expansion_parts:
            if "." not in alias_part:
                continue
            code, exchange = alias_part.split(".", 1)
            if len(code) == 6:
                aliases.add(_normalize_alias(f"{exchange[:2]}{code}"))
            elif code.isalpha():
                aliases.add(_normalize_alias(f"{code}0"))
                aliases.add(_normalize_alias(f"{code}0.{exchange}"))
    return aliases


def _normalize_alias(value: object) -> str:
    return str(value or "").strip().lower().replace("_", "-")


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "series_id",
            "series_name",
            "vendor_name",
            "trade_date",
            "value_numeric",
            "frequency",
            "unit",
            "source_version",
            "vendor_version",
            "rule_version",
            "run_id",
            "vendor_series_code",
        ]
    )


def _empty_series_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "value", "series_id", "vendor_name"])
