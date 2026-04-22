from __future__ import annotations

from pathlib import Path
from datetime import date
from decimal import Decimal

import duckdb

from backend.app.core_finance.fx_rates import get_usd_cny_rate
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_fx_catalog import (
    classify_fx_series_group,
    discover_formal_fx_candidates,
)
from backend.app.schemas.macro_vendor import (
    ChoiceMacroLatestPayload,
    FxAnalyticalGroup,
    FxAnalyticalPayload,
    FxAnalyticalSeriesPoint,
    FxFormalStatusPayload,
    FxFormalStatusRow,
    ChoiceMacroLatestPoint,
    ChoiceMacroRecentPoint,
    MacroVendorPayload,
    MacroVendorSeries,
)
from backend.app.services.formal_result_runtime import build_result_envelope

RULE_VERSION = "rv_phase1_macro_vendor_v1"
CACHE_VERSION = "cv_phase1_macro_vendor_v1"
LIVE_RULE_VERSION = "rv_choice_macro_thin_slice_v1"
LIVE_CACHE_VERSION = "cv_choice_macro_thin_slice_v1"


def load_macro_vendor_payload(duckdb_path: str) -> MacroVendorPayload:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return MacroVendorPayload(series=[])

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return MacroVendorPayload(series=[])

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "phase1_macro_vendor_catalog" not in tables:
            return MacroVendorPayload(series=[])

        available_columns = {
            str(row[1])
            for row in conn.execute("pragma table_info('phase1_macro_vendor_catalog')").fetchall()
        }
        select_columns = [
            "series_id",
            "series_name",
            "vendor_name",
            "vendor_version",
            "frequency",
            "unit",
            _catalog_column_expr("refresh_tier", available_columns, "NULL"),
            _catalog_column_expr("fetch_mode", available_columns, "NULL"),
            _catalog_column_expr("fetch_granularity", available_columns, "NULL"),
            _catalog_column_expr("policy_note", available_columns, "NULL"),
        ]
        rows = conn.execute(
            f"""
            select
              {", ".join(select_columns)}
            from phase1_macro_vendor_catalog
            order by vendor_name, series_id
            """
        ).fetchall()
    except duckdb.Error:
        return MacroVendorPayload(series=[])
    finally:
        conn.close()

    return MacroVendorPayload(
        series=[
            MacroVendorSeries(
                series_id=str(series_id),
                series_name=str(series_name),
                vendor_name=str(vendor_name),
                vendor_version=str(vendor_version),
                frequency=str(frequency),
                unit=str(unit),
                refresh_tier=_as_optional_string(refresh_tier),
                fetch_mode=_as_optional_string(fetch_mode),
                fetch_granularity=_as_optional_string(fetch_granularity),
                policy_note=_as_optional_string(policy_note),
            )
            for (
                series_id,
                series_name,
                vendor_name,
                vendor_version,
                frequency,
                unit,
                refresh_tier,
                fetch_mode,
                fetch_granularity,
                policy_note,
            ) in rows
        ]
    )


def macro_vendor_envelope(duckdb_path: str) -> dict[str, object]:
    payload = load_macro_vendor_payload(duckdb_path)
    source_version = _load_macro_vendor_source_version(
        duckdb_path,
        series_ids=[item.series_id for item in payload.series],
    )
    vendor_version = _aggregate_lineage_value(
        [item.vendor_version for item in payload.series],
        empty_value="vv_none",
    )
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_preview_macro_foundation",
        result_kind="preview.macro-foundation",
        cache_version=CACHE_VERSION,
        source_version=source_version,
        rule_version=RULE_VERSION,
        quality_flag=_quality_flag_for_presence(payload.series),
        vendor_version=vendor_version,
        vendor_status=_vendor_status_for_presence(payload.series),
        fallback_mode="none",
        result_payload=payload.model_dump(mode="json"),
    )


def _load_macro_vendor_source_version(duckdb_path: str, series_ids: list[str]) -> str:
    if not series_ids:
        return "sv_macro_vendor_empty"

    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return "sv_macro_vendor_empty"

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return "sv_macro_vendor_empty"

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "choice_market_snapshot" not in tables:
            return "sv_macro_vendor_empty"

        placeholders = ", ".join(["?"] * len(series_ids))
        rows = conn.execute(
            f"""
            select distinct source_version
            from choice_market_snapshot
            where series_id in ({placeholders})
              and source_version is not null and source_version <> ''
            order by source_version
            """,
            series_ids,
        ).fetchall()
    except duckdb.Error:
        return "sv_macro_vendor_empty"
    finally:
        conn.close()

    return _aggregate_lineage_value(
        [str(row[0]) for row in rows if row and row[0]],
        empty_value="sv_macro_vendor_empty",
    )


def load_choice_macro_latest_payload(duckdb_path: str) -> ChoiceMacroLatestPayload:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return ChoiceMacroLatestPayload(series=[])

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return ChoiceMacroLatestPayload(series=[])

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "fact_choice_macro_daily" not in tables:
            return ChoiceMacroLatestPayload(series=[])

        recent_rows = _load_choice_macro_recent_rows(conn, tables)
        catalog_by_series = _load_choice_macro_catalog_map(conn, tables)
    except duckdb.Error:
        return ChoiceMacroLatestPayload(series=[])
    finally:
        conn.close()

    if not recent_rows:
        return ChoiceMacroLatestPayload(series=[])

    grouped_rows: dict[str, list[dict[str, object]]] = {}
    for (
        series_id,
        series_name,
        trade_date,
        value_numeric,
        frequency,
        unit,
        source_version,
        vendor_version,
        quality_flag,
        _rn,
    ) in recent_rows:
        grouped_rows.setdefault(str(series_id), []).append(
            {
                "series_id": str(series_id),
                "series_name": str(series_name),
                "trade_date": str(trade_date),
                "value_numeric": float(value_numeric),
                "frequency": str(frequency),
                "unit": str(unit),
                "source_version": str(source_version),
                "vendor_version": str(vendor_version),
                "quality_flag": str(quality_flag),
            }
        )

    series = []
    for series_id in sorted(grouped_rows):
        rows = grouped_rows[series_id]
        latest = rows[0]
        recent_points = [
            ChoiceMacroRecentPoint(
                trade_date=str(row["trade_date"]),
                value_numeric=float(row["value_numeric"]),
                source_version=str(row["source_version"]),
                vendor_version=str(row["vendor_version"]),
                quality_flag=_normalize_quality_flag(str(row["quality_flag"])),
            )
            for row in rows
        ]
        catalog = catalog_by_series.get(
            series_id,
            {
                "frequency": latest["frequency"],
                "unit": latest["unit"],
                "refresh_tier": None,
                "fetch_mode": None,
                "fetch_granularity": None,
                "policy_note": None,
            },
        )
        if catalog.get("refresh_tier") == "isolated":
            continue
        latest_change = None
        if len(rows) > 1:
            latest_change = float(latest["value_numeric"]) - float(rows[1]["value_numeric"])

        series.append(
            ChoiceMacroLatestPoint(
                series_id=series_id,
                series_name=str(latest["series_name"]),
                trade_date=str(latest["trade_date"]),
                value_numeric=float(latest["value_numeric"]),
                frequency=str(catalog["frequency"] or latest["frequency"]),
                unit=str(catalog["unit"] or latest["unit"]),
                source_version=str(latest["source_version"]),
                vendor_version=str(latest["vendor_version"]),
                refresh_tier=_as_optional_string(catalog.get("refresh_tier")),
                fetch_mode=_as_optional_string(catalog.get("fetch_mode")),
                fetch_granularity=_as_optional_string(catalog.get("fetch_granularity")),
                policy_note=_as_optional_string(catalog.get("policy_note")),
                quality_flag=_normalize_quality_flag(str(latest["quality_flag"])),
                latest_change=latest_change,
                recent_points=recent_points,
            )
        )

    return ChoiceMacroLatestPayload(series=series)


def choice_macro_latest_envelope(duckdb_path: str) -> dict[str, object]:
    payload = load_choice_macro_latest_payload(duckdb_path)
    quality_flag = _aggregate_quality_flags([item.quality_flag for item in payload.series])
    source_version = _aggregate_lineage_value(
        [item.source_version for item in payload.series],
        empty_value="sv_choice_macro_empty",
    )
    vendor_version = _aggregate_lineage_value(
        [item.vendor_version for item in payload.series],
        empty_value="vv_none",
    )
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_choice_macro_latest",
        result_kind="macro.choice.latest",
        cache_version=LIVE_CACHE_VERSION,
        source_version=source_version,
        rule_version=LIVE_RULE_VERSION,
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status=_vendor_status_for_macro_latest(payload, quality_flag),
        fallback_mode=_fallback_mode_for_macro_latest(payload, quality_flag),
        result_payload=payload.model_dump(mode="json"),
    )


def load_fx_formal_status_payload(duckdb_path: str) -> FxFormalStatusPayload:
    settings = get_settings()
    try:
        candidates = discover_formal_fx_candidates(
            catalog_path=Path(settings.choice_macro_catalog_file)
        )
    except FileNotFoundError:
        return FxFormalStatusPayload(
            candidate_count=0,
            materialized_count=0,
            latest_trade_date=None,
            carry_forward_count=0,
            rows=[],
        )
    rows_by_pair = _load_latest_fx_mid_rows(
        duckdb_path=duckdb_path,
        base_currencies=[candidate.base_currency for candidate in candidates],
    )

    rows: list[FxFormalStatusRow] = []
    latest_trade_dates: list[str] = []
    carry_forward_count = 0
    materialized_count = 0
    for candidate in candidates:
        current = rows_by_pair.get((candidate.base_currency, candidate.quote_currency))
        status = "ok" if current is not None else "missing"
        if current is not None:
            materialized_count += 1
            if current["trade_date"]:
                latest_trade_dates.append(current["trade_date"])
            if current["is_carry_forward"]:
                carry_forward_count += 1
        rows.append(
            FxFormalStatusRow(
                base_currency=candidate.base_currency,
                quote_currency=candidate.quote_currency,
                pair_label=candidate.pair_label,
                series_id=candidate.series_id,
                series_name=candidate.series_name,
                vendor_series_code=candidate.vendor_series_code,
                trade_date=current["trade_date"] if current is not None else None,
                observed_trade_date=current["observed_trade_date"] if current is not None else None,
                mid_rate=current["mid_rate"] if current is not None else None,
                source_name=current["source_name"] if current is not None else None,
                vendor_name=current["vendor_name"] if current is not None else None,
                vendor_version=current["vendor_version"] if current is not None else None,
                source_version=current["source_version"] if current is not None else None,
                is_business_day=current["is_business_day"] if current is not None else None,
                is_carry_forward=current["is_carry_forward"] if current is not None else None,
                status=status,
            )
        )

    latest_trade_date = max(latest_trade_dates) if latest_trade_dates else None
    return FxFormalStatusPayload(
        candidate_count=len(candidates),
        materialized_count=materialized_count,
        latest_trade_date=latest_trade_date,
        carry_forward_count=carry_forward_count,
        rows=rows,
    )


def fx_formal_status_envelope(duckdb_path: str) -> dict[str, object]:
    payload = load_fx_formal_status_payload(duckdb_path)
    source_version = _aggregate_lineage_value(
        [row.source_version or "" for row in payload.rows if row.status == "ok"],
        empty_value="sv_fx_formal_empty",
    )
    vendor_version = _aggregate_lineage_value(
        [row.vendor_version or "" for row in payload.rows if row.status == "ok"],
        empty_value="vv_none",
    )
    quality_flag = (
        "ok"
        if payload.candidate_count > 0 and payload.candidate_count == payload.materialized_count
        else "warning"
    )
    return build_result_envelope(
        basis="formal",
        trace_id="tr_fx_formal_status",
        result_kind="fx.formal.status",
        cache_version="cv_fx_formal_mid_v1",
        source_version=source_version,
        rule_version="rv_fx_formal_mid_v1",
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status="ok" if payload.materialized_count and payload.candidate_count else "vendor_unavailable",
        fallback_mode="latest_snapshot" if payload.carry_forward_count else "none",
        result_payload=payload.model_dump(mode="json"),
    )


def load_fx_analytical_payload(duckdb_path: str) -> FxAnalyticalPayload:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return FxAnalyticalPayload(groups=[])

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return FxAnalyticalPayload(groups=[])

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "fact_choice_macro_daily" not in tables or "phase1_macro_vendor_catalog" not in tables:
            return FxAnalyticalPayload(groups=[])
        recent_rows = _load_choice_macro_recent_rows(conn, tables)
        catalog_by_series = _load_choice_macro_catalog_map(conn, tables)
        name_by_series = {
            str(row[0]): str(row[1])
            for row in conn.execute(
                """
                select distinct series_id, series_name
                from phase1_macro_vendor_catalog
                """
            ).fetchall()
        }
    except duckdb.Error:
        return FxAnalyticalPayload(groups=[])
    finally:
        conn.close()

    grouped_rows: dict[str, list[dict[str, object]]] = {}
    for (
        series_id,
        series_name,
        trade_date,
        value_numeric,
        frequency,
        unit,
        source_version,
        vendor_version,
        quality_flag,
        _rn,
    ) in recent_rows:
        logical_name = name_by_series.get(str(series_id), str(series_name))
        group_key = classify_fx_series_group(logical_name)
        if group_key is None:
            continue
        grouped_rows.setdefault(str(series_id), []).append(
            {
                "group_key": group_key,
                "series_id": str(series_id),
                "series_name": logical_name,
                "trade_date": str(trade_date),
                "value_numeric": float(value_numeric),
                "frequency": str(frequency),
                "unit": str(unit),
                "source_version": str(source_version),
                "vendor_version": str(vendor_version),
                "quality_flag": str(quality_flag),
            }
        )

    groups: dict[str, list[FxAnalyticalSeriesPoint]] = {}
    for series_id, rows in grouped_rows.items():
        latest = _resolve_fx_analytical_latest_row(rows)
        recent_points = [
            ChoiceMacroRecentPoint(
                trade_date=str(row["trade_date"]),
                value_numeric=float(row["value_numeric"]),
                source_version=str(row["source_version"]),
                vendor_version=str(row["vendor_version"]),
                quality_flag=_normalize_quality_flag(str(row["quality_flag"])),
            )
            for row in rows
        ]
        latest_change = None
        if len(rows) > 1:
            latest_change = float(rows[0]["value_numeric"]) - float(rows[1]["value_numeric"])
        catalog = catalog_by_series.get(
            series_id,
            {
                "refresh_tier": None,
                "fetch_mode": None,
                "fetch_granularity": None,
                "policy_note": None,
            },
        )
        point = FxAnalyticalSeriesPoint(
            group_key=latest["group_key"],
            series_id=series_id,
            series_name=str(latest["series_name"]),
            trade_date=str(latest["trade_date"]),
            value_numeric=float(latest["value_numeric"]),
            frequency=str(latest["frequency"]),
            unit=str(latest["unit"]),
            source_version=str(latest["source_version"]),
            vendor_version=str(latest["vendor_version"]),
            refresh_tier=_as_optional_string(catalog.get("refresh_tier")),
            fetch_mode=_as_optional_string(catalog.get("fetch_mode")),
            fetch_granularity=_as_optional_string(catalog.get("fetch_granularity")),
            policy_note=_as_optional_string(catalog.get("policy_note")),
            quality_flag=_normalize_quality_flag(str(latest["quality_flag"])),
            latest_change=latest_change,
            recent_points=recent_points,
        )
        groups.setdefault(latest["group_key"], []).append(point)

    ordered_groups: list[FxAnalyticalGroup] = []
    for group_key, title, description in (
        ("middle_rate", "Analytical FX: middle-rates", "Catalog-observed middle-rate series remain analytical views and do not redefine the formal seam."),
        ("fx_index", "Analytical FX: indices", "RMB index / estimate index series stay analytical-only and never flow into formal FX."),
        ("fx_swap_curve", "Analytical FX: swap curves", "FX swap / C-Swap series stay analytical-only and never write into formal FX."),
    ):
        points = sorted(groups.get(group_key, []), key=lambda item: item.series_id)
        if not points:
            continue
        ordered_groups.append(
            FxAnalyticalGroup(
                group_key=group_key,
                title=title,
                description=description,
                series=points,
            )
        )
    return FxAnalyticalPayload(groups=ordered_groups)


def _resolve_fx_analytical_latest_row(rows: list[dict[str, object]]) -> dict[str, object]:
    latest = rows[0]
    if not _is_usd_cny_middle_rate(str(latest["series_name"])):
        return latest
    target_date = date.fromisoformat(str(latest["trade_date"]))
    rate, observed_date, warnings = get_usd_cny_rate(
        [
            (date.fromisoformat(str(row["trade_date"])), Decimal(str(row["value_numeric"])))
            for row in rows
        ],
        target_date,
    )
    quality_flag = "warning" if warnings else str(latest["quality_flag"])
    return {
        **latest,
        "trade_date": observed_date.isoformat() if observed_date is not None else str(latest["trade_date"]),
        "value_numeric": float(rate),
        "quality_flag": quality_flag,
    }


def _is_usd_cny_middle_rate(series_name: str) -> bool:
    return "中间价" in series_name and "美元" in series_name and "人民币" in series_name


def fx_analytical_envelope(duckdb_path: str) -> dict[str, object]:
    payload = load_fx_analytical_payload(duckdb_path)
    points = [
        point
        for group in payload.groups
        for point in group.series
    ]
    source_version = _aggregate_lineage_value(
        [point.source_version for point in points],
        empty_value="sv_fx_analytical_empty",
    )
    vendor_version = _aggregate_lineage_value(
        [point.vendor_version for point in points],
        empty_value="vv_none",
    )
    quality_flag = _aggregate_quality_flags([point.quality_flag for point in points])
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_fx_analytical",
        result_kind="fx.analytical.groups",
        cache_version="cv_fx_analytical_v1",
        source_version=source_version,
        rule_version="rv_fx_analytical_v1",
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status=_vendor_status_for_presence(points),
        fallback_mode="latest_snapshot" if any(point.refresh_tier == "fallback" for point in points) else "none",
        result_payload=payload.model_dump(mode="json"),
    )


def _load_latest_fx_mid_rows(
    *,
    duckdb_path: str,
    base_currencies: list[str],
) -> dict[tuple[str, str], dict[str, object]]:
    if not base_currencies:
        return {}
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return {}
    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return {}
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "fx_daily_mid" not in tables:
            return {}
        placeholders = ", ".join(["?"] * len(base_currencies))
        rows = conn.execute(
            f"""
            with ranked as (
              select
                base_currency,
                quote_currency,
                cast(trade_date as varchar) as trade_date,
                cast(observed_trade_date as varchar) as observed_trade_date,
                cast(mid_rate as double) as mid_rate,
                source_name,
                coalesce(vendor_name, '') as vendor_name,
                coalesce(vendor_version, '') as vendor_version,
                source_version,
                is_business_day,
                is_carry_forward,
                row_number() over (
                  partition by upper(base_currency), upper(quote_currency)
                  order by trade_date desc
                ) as rn
              from fx_daily_mid
              where upper(base_currency) in ({placeholders})
                and upper(quote_currency) = 'CNY'
            )
            select
              base_currency,
              quote_currency,
              trade_date,
              observed_trade_date,
              mid_rate,
              source_name,
              vendor_name,
              vendor_version,
              source_version,
              is_business_day,
              is_carry_forward
            from ranked
            where rn = 1
            """,
            [item.upper() for item in base_currencies],
        ).fetchall()
    except duckdb.Error:
        return {}
    finally:
        conn.close()

    result: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row[0]).upper(), str(row[1]).upper())
        result[key] = {
            "base_currency": str(row[0]).upper(),
            "quote_currency": str(row[1]).upper(),
            "trade_date": str(row[2]) if row[2] is not None else None,
            "observed_trade_date": str(row[3]) if row[3] is not None else None,
            "mid_rate": float(row[4]) if row[4] is not None else None,
            "source_name": str(row[5]) if row[5] is not None else None,
            "vendor_name": str(row[6]) if row[6] is not None else None,
            "vendor_version": str(row[7]) if row[7] is not None else None,
            "source_version": str(row[8]) if row[8] is not None else None,
            "is_business_day": bool(row[9]) if row[9] is not None else None,
            "is_carry_forward": bool(row[10]) if row[10] is not None else None,
        }
    return result


_CHOICE_MACRO_RECENT_POINT_LIMIT = 20


def _load_choice_macro_recent_rows(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
) -> list[tuple[object, ...]]:
    if "choice_market_snapshot" in tables:
        snapshot_count = conn.execute(
            "select count(*) from choice_market_snapshot"
        ).fetchone()
        if snapshot_count and int(snapshot_count[0]) > 0:
            return conn.execute(
                f"""
                with active_series as (
                  select distinct series_id
                  from choice_market_snapshot
                ),
                ranked as (
                  select
                    fact.series_id,
                    fact.series_name,
                    fact.trade_date,
                    fact.value_numeric,
                    fact.frequency,
                    fact.unit,
                    fact.source_version,
                    fact.vendor_version,
                    fact.quality_flag,
                    row_number() over(partition by fact.series_id order by fact.trade_date desc) as rn
                  from fact_choice_macro_daily as fact
                  inner join active_series on active_series.series_id = fact.series_id
                )
                select
                  series_id,
                  series_name,
                  trade_date,
                  value_numeric,
                  frequency,
                  unit,
                  source_version,
                  vendor_version,
                  quality_flag,
                  rn
                from ranked
                where rn <= {_CHOICE_MACRO_RECENT_POINT_LIMIT}
                order by series_id, rn
                """
            ).fetchall()

    return conn.execute(
        f"""
        with ranked as (
          select
            series_id,
            series_name,
            trade_date,
            value_numeric,
            frequency,
            unit,
            source_version,
            vendor_version,
            quality_flag,
            row_number() over(partition by series_id order by trade_date desc) as rn
          from fact_choice_macro_daily
        )
        select
          series_id,
          series_name,
          trade_date,
          value_numeric,
          frequency,
          unit,
          source_version,
          vendor_version,
          quality_flag,
          rn
        from ranked
        where rn <= {_CHOICE_MACRO_RECENT_POINT_LIMIT}
        order by series_id, rn
        """
    ).fetchall()


def _load_choice_macro_catalog_map(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
) -> dict[str, dict[str, object]]:
    if "phase1_macro_vendor_catalog" not in tables:
        return {}

    available_columns = {
        str(row[1])
        for row in conn.execute("pragma table_info('phase1_macro_vendor_catalog')").fetchall()
    }
    select_columns = [
        "series_id",
        _catalog_column_expr("refresh_tier", available_columns, "NULL"),
        _catalog_column_expr("fetch_mode", available_columns, "NULL"),
        _catalog_column_expr("fetch_granularity", available_columns, "NULL"),
        _catalog_column_expr("policy_note", available_columns, "NULL"),
        "frequency",
        "unit",
    ]
    rows = conn.execute(
        f"""
        select
          {", ".join(select_columns)}
        from phase1_macro_vendor_catalog
        """
    ).fetchall()

    catalog_by_series: dict[str, dict[str, object]] = {}
    for (
        series_id,
        refresh_tier,
        fetch_mode,
        fetch_granularity,
        policy_note,
        frequency,
        unit,
    ) in rows:
        catalog_by_series[str(series_id)] = {
            "refresh_tier": _as_optional_string(refresh_tier),
            "fetch_mode": _as_optional_string(fetch_mode),
            "fetch_granularity": _as_optional_string(fetch_granularity),
            "policy_note": _as_optional_string(policy_note),
            "frequency": str(frequency or ""),
            "unit": str(unit or ""),
        }
    return catalog_by_series


def _catalog_column_expr(column: str, available_columns: set[str], fallback_sql: str) -> str:
    if column in available_columns:
        return column
    return f"{fallback_sql} as {column}"


def _aggregate_lineage_value(values: list[str], empty_value: str) -> str:
    distinct = sorted({value for value in values if value})
    if not distinct:
        return empty_value
    if len(distinct) == 1:
        return distinct[0]
    return "__".join(distinct)


def _quality_flag_for_presence(series: list[object]) -> str:
    return "ok" if series else "warning"


def _vendor_status_for_presence(series: list[object]) -> str:
    return "ok" if series else "vendor_unavailable"


def _vendor_status_for_macro_latest(payload: ChoiceMacroLatestPayload, quality_flag: str) -> str:
    if not payload.series:
        return "vendor_unavailable"
    if quality_flag == "stale":
        return "vendor_stale"
    return "ok"


def _fallback_mode_for_macro_latest(payload: ChoiceMacroLatestPayload, quality_flag: str) -> str:
    if payload.series and quality_flag == "stale":
        return "latest_snapshot"
    return "none"


def _aggregate_quality_flags(values: list[str]) -> str:
    normalized = {_normalize_quality_flag(value) for value in values if value}
    if not normalized:
        return "warning"
    for flag in ("error", "stale", "warning"):
        if flag in normalized:
            return flag
    return "ok"


def _normalize_quality_flag(value: str) -> str:
    if value in {"ok", "warning", "error", "stale"}:
        return value
    return "warning"


def _as_optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
