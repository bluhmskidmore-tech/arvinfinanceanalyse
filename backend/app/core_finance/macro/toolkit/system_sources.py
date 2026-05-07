from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

DEFAULT_DATA_SOURCES = ("choice", "tushare")

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
    "m0001385": ("cn_m2_yoy", "tushare.macro.cn_money.monthly"),
    "edb-m2-yoy": ("cn_m2_yoy", "tushare.macro.cn_money.monthly"),
    "m5525763": ("EMM00191807",),
    "m0067855": ("EMM00058124", "legacy.fx.choice.USD.CNY", "fx_daily_mid:USD/CNY", "USD/CNY", "USDCNY"),
    "usd/cny": ("EMM00058124", "legacy.fx.choice.USD.CNY", "fx_daily_mid:USD/CNY"),
    "usdcny": ("EMM00058124", "legacy.fx.choice.USD.CNY", "fx_daily_mid:USD/CNY", "USD/CNY"),
    "m0041653": ("cn_repo_7d",),
    "m0041813": ("NCD.SHIBOR.3M", "shibor:3m"),
    "dr007.ib": ("CA.DR007", "repo_rate_query:FDR007", "DR007.IB"),
    "s0059743": ("EMM00166458", "legacy.yield.choice.treasury.1Y"),
    "s0059745": ("EMM00588704", "legacy.yield.choice.treasury.2Y"),
    "s0059746": ("EMM00166460", "legacy.yield.choice.treasury.3Y"),
    "s0059747": ("EMM00166462", "legacy.yield.choice.treasury.5Y"),
    "s0059748": ("EMM00166464", "legacy.yield.choice.treasury.7Y"),
    "s0059749": ("EMM00166466", "E1000180", "legacy.yield.choice.treasury.10Y"),
    "s0059751": ("EMM00166468", "legacy.yield.choice.treasury.20Y"),
    "s0059752": ("EMM00166469", "legacy.yield.choice.treasury.30Y"),
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
    "s0059760": ("legacy.yield.choice.aa_credit.5Y", "EMM00166683"),
}

_SOURCE_PRIORITY = {
    "choice": 0,
    "fx_daily_mid": 0,
    "public_bond_zh_us_rate": 0,
    "public_repo_rate_query": 0,
    "tushare": 1,
    "moss_derived": 2,
}


def resolve_system_duckdb_path(duckdb_path: str | Path | None = None) -> Path:
    if duckdb_path is not None:
        return Path(duckdb_path)

    from backend.app.governance.settings import get_settings  # noqa: PLC0415

    return Path(get_settings().duckdb_path)


def load_system_macro_frame(duckdb_path: str | Path | None = None) -> pd.DataFrame:
    path = resolve_system_duckdb_path(duckdb_path)
    if not path.exists():
        return _empty_frame()

    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return _empty_frame()

    try:
        frames = [
            _load_choice_frame(conn),
            _load_choice_snapshot_frame(conn),
            _load_tushare_frame(conn),
            _load_fx_frame(conn),
            _load_legacy_yield_curve_frame(conn),
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


def load_series_by_alias(
    alias: str,
    *,
    start: str | None = None,
    end: str | None = None,
    duckdb_path: str | Path | None = None,
) -> pd.DataFrame:
    frame = load_system_macro_frame(duckdb_path)
    if frame.empty:
        return _empty_series_frame()

    candidates = _candidate_aliases(alias)
    mask = frame.apply(lambda row: bool(_row_aliases(row) & candidates), axis=1)
    selected = frame.loc[mask].copy()
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


def _load_choice_frame(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not _table_exists(conn, "fact_choice_macro_daily"):
        return _empty_frame()

    fact = conn.execute(
        """
        select
          series_id, series_name, trade_date, value_numeric,
          frequency, unit, source_version, vendor_version, rule_version, run_id
        from fact_choice_macro_daily
        """
    ).fetchdf()
    if fact.empty:
        return _empty_frame()

    fact["vendor_name"] = "choice"
    fact["vendor_series_code"] = ""
    if _table_exists(conn, "phase1_macro_vendor_catalog"):
        catalog = conn.execute(
            """
            select series_id, max(series_name) as catalog_series_name,
                   max(vendor_name) as catalog_vendor_name,
                   max(vendor_series_code) as vendor_series_code
            from phase1_macro_vendor_catalog
            group by series_id
            """
        ).fetchdf()
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
        snapshot = conn.execute(
            """
            select series_id, max(vendor_name) as snapshot_vendor_name,
                   max(vendor_series_code) as snapshot_vendor_series_code
            from choice_market_snapshot
            group by series_id
            """
        ).fetchdf()
        fact = fact.merge(snapshot, on="series_id", how="left")
        fact["vendor_name"] = fact["snapshot_vendor_name"].fillna(fact["vendor_name"])
        fact["vendor_series_code"] = fact["vendor_series_code"].fillna("")
        fact["vendor_series_code"] = fact["vendor_series_code"].where(
            fact["vendor_series_code"].astype(str) != "",
            fact["snapshot_vendor_series_code"],
        ).fillna("")
        fact = fact.drop(columns=["snapshot_vendor_name", "snapshot_vendor_series_code"])

    return _normalize_frame(fact)


def _load_choice_snapshot_frame(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not _table_exists(conn, "choice_market_snapshot"):
        return _empty_frame()

    snapshot = conn.execute(
        """
        select
          series_id, series_name, vendor_name, trade_date, value_numeric,
          frequency, unit, source_version, vendor_version, rule_version, run_id,
          vendor_series_code
        from choice_market_snapshot
        """
    ).fetchdf()
    if snapshot.empty:
        return _empty_frame()
    return _normalize_frame(snapshot)


def _load_tushare_frame(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not _table_exists(conn, "std_external_macro_daily"):
        return _empty_frame()

    std = conn.execute(
        """
        select
          series_id, vendor_name, trade_date, value_numeric, frequency, unit,
          source_version, vendor_version, rule_version, ingest_batch_id as run_id
        from std_external_macro_daily
        where lower(vendor_name) = 'tushare'
        """
    ).fetchdf()
    if std.empty:
        return _empty_frame()

    std["series_name"] = std["series_id"]
    std["vendor_series_code"] = ""
    if _table_exists(conn, "external_data_catalog"):
        catalog = conn.execute(
            """
            select series_id, max(series_name) as catalog_series_name
            from external_data_catalog
            where lower(vendor_name) = 'tushare'
            group by series_id
            """
        ).fetchdf()
        std = std.merge(catalog, on="series_id", how="left")
        std["series_name"] = std["catalog_series_name"].fillna(std["series_name"])
        std = std.drop(columns=["catalog_series_name"])

    return _normalize_frame(std)


def _load_fx_frame(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not _table_exists(conn, "fx_daily_mid"):
        return _empty_frame()

    fx = conn.execute(
        """
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
    ).fetchdf()
    if fx.empty:
        return _empty_frame()
    return _normalize_frame(fx)


def _load_legacy_yield_curve_frame(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not _table_exists(conn, "fact_formal_yield_curve_daily"):
        return _empty_frame()

    curve = conn.execute(
        """
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
        where lower(vendor_name) in ('choice', 'tushare', 'moss_derived')
        """
    ).fetchdf()
    if curve.empty:
        return _empty_frame()
    return _normalize_frame(curve)


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
    except duckdb.Error:
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
    return aliases


def _expanded_vendor_aliases(value: str) -> set[str]:
    parts = [str(value or "")]
    if ":" in parts[0]:
        parts.append(parts[0].split(":", 1)[1])

    aliases: set[str] = set()
    for part in parts:
        normalized = _normalize_alias(part)
        if normalized:
            aliases.add(normalized)
        lowered = part.lower()
        for suffix in (".close", ".pct_chg", ".value"):
            if lowered.endswith(suffix):
                aliases.add(_normalize_alias(part[: -len(suffix)]))
        if "." not in part:
            continue
        code, exchange = part.split(".", 1)
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
