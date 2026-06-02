from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

import duckdb
from backend.app.core_finance.livermore_risk_exit import (
    MVP_RULE_LABEL,
    RiskExitSnapshot,
    compute_risk_exit,
)
from backend.app.core_finance.livermore_risk_exit import (
    REQUIRED_INPUTS as RISK_EXIT_REQUIRED_INPUTS,
)
from backend.app.core_finance.livermore_sector_rank import (
    SectorRankConstituent,
    compute_sector_rank,
)
from backend.app.core_finance.livermore_stock_candidates import (
    StockCandidateSnapshot,
    compute_stock_candidates,
)
from backend.app.core_finance.livermore_strategy import (
    BroadIndexObservation,
    MarketGateSupplement,
    evaluate_market_gate,
)
from backend.app.repositories.choice_stock_adapter import (
    ChoiceStockReadiness,
    choice_stock_readiness_missing,
)
from backend.app.repositories.livermore_gate_supplement_repo import fetch_market_gate_supplement
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)
from backend.app.tasks.choice_stock_materialize import (
    ChoiceStockMaterializationCoverage,
    load_choice_stock_materialization_coverage,
)

RULE_VERSION = "rv_livermore_strategy_v1"
CACHE_VERSION = "cv_livermore_strategy_v1"
RESULT_KIND = "market_data.livermore"
STRATEGY_NAME = "Livermore A-Share Defended Trend"
EMPTY_SOURCE_VERSION = "sv_livermore_empty"
EMPTY_VENDOR_VERSION = "vv_none"
BROAD_INDEX_SERIES_ID = "CA.CSI300"
HISTORY_LIMIT = 260
STOCK_CANDIDATE_LIMIT_RATIO_BLOCK_REASON = (
    "No price-field or rule-derived limit_ratio source is available for Livermore stock pivot filters."
)
MAINBOARD_RISK_WARNING_LIMIT_RATIO_10_START = date(2026, 7, 6)
SECTOR_REQUIRED_ITEMS: tuple[tuple[str, str], ...] = (
    ("sector_membership", "sw2021_industry_membership"),
    ("sector_strength", "daily_return_turnover_amplitude"),
)


def livermore_strategy_envelope(
    *,
    duckdb_path: str,
    as_of_date: str | None = None,
    stock_readiness: ChoiceStockReadiness | None = None,
) -> dict[str, object]:
    requested_date = _parse_optional_date(as_of_date)
    payload, meta = load_livermore_strategy_payload(
        duckdb_path=duckdb_path,
        as_of_date=requested_date,
        stock_readiness=stock_readiness,
    )
    filters_applied = {
        "requested_as_of_date": None if requested_date is None else requested_date.isoformat(),
        "as_of_date": payload["as_of_date"],
    }
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=cast(str, meta["source_version"]),
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, meta["quality_flag"]),
        vendor_version=cast(str, meta["vendor_version"]),
        vendor_status=cast(VendorStatus, meta["vendor_status"]),
        fallback_mode=cast(FallbackMode, meta["fallback_mode"]),
        filters_applied=filters_applied,
        tables_used=cast(list[str], meta["tables_used"]),
        evidence_rows=cast(int, meta["evidence_rows"]),
        result_payload=payload,
    )


def load_livermore_strategy_payload(
    *,
    duckdb_path: str,
    as_of_date: date | None,
    stock_readiness: ChoiceStockReadiness | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    resolved_stock_readiness = stock_readiness or choice_stock_readiness_missing("")
    history_rows, broad_index_tables = _load_broad_index_history(
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
    )
    latest_trade_date: date | None = history_rows[-1].trade_date if history_rows else None
    supplement: MarketGateSupplement | None = None
    if latest_trade_date is not None:
        supplement = fetch_market_gate_supplement(duckdb_path=duckdb_path, trade_date=latest_trade_date)

    market_gate = evaluate_market_gate(cast(list[BroadIndexObservation], history_rows), supplement=supplement)
    requested_text = None if as_of_date is None else as_of_date.isoformat()
    resolved_as_of_date = history_rows[-1].trade_date.isoformat() if history_rows else None
    effective_as_of_date = resolved_as_of_date or requested_text
    stock_outputs = _load_choice_stock_outputs(
        duckdb_path=duckdb_path,
        as_of_date=effective_as_of_date,
        market_state=str(market_gate["state"]),
        stock_readiness=resolved_stock_readiness,
    )
    diagnostics = _build_diagnostics(
        requested_as_of_date=requested_text,
        resolved_as_of_date=resolved_as_of_date,
        market_gate=market_gate,
        history_count=len(history_rows),
        stock_readiness=resolved_stock_readiness,
        stock_outputs=stock_outputs,
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    data_gaps = _build_data_gaps(
        market_gate=market_gate,
        history_count=len(history_rows),
        resolved_as_of_date=resolved_as_of_date,
        stock_readiness=resolved_stock_readiness,
        stock_outputs=stock_outputs,
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    rule_readiness = _build_rule_readiness(
        market_gate=market_gate,
        history_count=len(history_rows),
        stock_readiness=resolved_stock_readiness,
        stock_outputs=stock_outputs,
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    supported_outputs, unsupported_outputs = _build_supported_outputs(
        str(market_gate["state"]),
        stock_readiness=resolved_stock_readiness,
        stock_outputs=stock_outputs,
    )
    quality_flag = _quality_flag_for_market_gate(str(market_gate["state"]))
    payload: dict[str, object] = {
        "as_of_date": resolved_as_of_date,
        "requested_as_of_date": requested_text,
        "strategy_name": STRATEGY_NAME,
        "basis": "analytical",
        "market_gate": market_gate,
        "rule_readiness": rule_readiness,
        "data_gaps": data_gaps,
        "diagnostics": diagnostics,
        "supported_outputs": supported_outputs,
        "unsupported_outputs": unsupported_outputs,
    }
    if stock_outputs.sector_rank_payload is not None:
        payload["sector_rank"] = stock_outputs.sector_rank_payload
    if stock_outputs.stock_candidates_payload is not None:
        payload["stock_candidates"] = stock_outputs.stock_candidates_payload
    if stock_outputs.risk_exit_payload is not None:
        payload["risk_exit"] = stock_outputs.risk_exit_payload
    source_versions = [row.source_version for row in history_rows if row.source_version] + stock_outputs.source_versions
    vendor_versions = [row.vendor_version for row in history_rows if row.vendor_version] + stock_outputs.vendor_versions
    tables_used = [*broad_index_tables, *stock_outputs.tables_used]
    if supplement is not None:
        tables_used.append("fact_livermore_gate_supplement_daily")
    meta: dict[str, object] = {
        "quality_flag": quality_flag,
        "vendor_status": _vendor_status_for_state(str(market_gate["state"])),
        "fallback_mode": "latest_snapshot" if quality_flag == "stale" else "none",
        "source_version": _aggregate_lineage(source_versions, empty_value=EMPTY_SOURCE_VERSION),
        "vendor_version": _aggregate_lineage(vendor_versions, empty_value=EMPTY_VENDOR_VERSION),
        "tables_used": _unique_preserving_order(tables_used),
        "evidence_rows": len(history_rows) + stock_outputs.evidence_rows,
    }
    return payload, meta


def _parse_optional_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(str(value))


def _load_broad_index_history(
    *,
    duckdb_path: str,
    as_of_date: date | None,
) -> tuple[list[_LoadedObservation], list[str]]:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return [], []

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return [], []

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        queries: list[str] = []
        params: list[object] = []
        tables_used: list[str] = []
        date_filter = "and cast(trade_date as date) <= ?" if as_of_date is not None else ""
        if "fact_choice_macro_daily" in tables:
            tables_used.append("fact_choice_macro_daily")
            queries.append(
                f"""
                select
                  cast(trade_date as date) as trade_date,
                  cast(value_numeric as double) as close_value,
                  coalesce(source_version, '') as source_version,
                  coalesce(vendor_version, '') as vendor_version,
                  coalesce(quality_flag, 'ok') as quality_flag,
                  0 as source_rank
                from fact_choice_macro_daily
                where series_id = ?
                  and value_numeric is not null
                  {date_filter}
                """
            )
            params.append(BROAD_INDEX_SERIES_ID)
            if as_of_date is not None:
                params.append(as_of_date.isoformat())
        if "choice_market_snapshot" in tables:
            tables_used.append("choice_market_snapshot")
            queries.append(
                f"""
                select
                  cast(trade_date as date) as trade_date,
                  cast(value_numeric as double) as close_value,
                  coalesce(source_version, '') as source_version,
                  coalesce(vendor_version, '') as vendor_version,
                  'ok' as quality_flag,
                  1 as source_rank
                from choice_market_snapshot
                where series_id = ?
                  and value_numeric is not null
                  {date_filter}
                """
            )
            params.append(BROAD_INDEX_SERIES_ID)
            if as_of_date is not None:
                params.append(as_of_date.isoformat())
        if not queries:
            return [], []
        rows = conn.execute(
            f"""
            with unioned as (
              {" union all ".join(queries)}
            ),
            deduped as (
              select
                trade_date,
                close_value,
                source_version,
                vendor_version,
                quality_flag,
                row_number() over (
                  partition by trade_date
                  order by source_rank asc, source_version desc
                ) as rn
              from unioned
            )
            select
              trade_date,
              close_value,
              source_version,
              vendor_version,
              quality_flag
            from deduped
            where rn = 1
            order by trade_date desc
            limit {HISTORY_LIMIT}
            """,
            params,
        ).fetchall()
    except duckdb.Error:
        return [], tables_used if "tables_used" in locals() else []
    finally:
        conn.close()

    ordered = [
        _LoadedObservation(
            trade_date=row[0],
            close=float(row[1]),
            source_version=str(row[2] or ""),
            vendor_version=str(row[3] or ""),
            quality_flag=str(row[4] or "ok"),
        )
        for row in reversed(rows)
        if row[0] is not None and row[1] is not None
    ]
    return ordered, tables_used


class _LoadedObservation(BroadIndexObservation):
    pass


@dataclass(frozen=True)
class _ChoiceStockOutputs:
    sector_coverage: ChoiceStockMaterializationCoverage | None
    stock_coverage: ChoiceStockMaterializationCoverage | None
    sector_rank_payload: dict[str, object] | None
    stock_candidates_payload: dict[str, object] | None
    risk_exit_payload: dict[str, object] | None
    risk_exit_block_reason: str
    stock_candidate_block_reason: str
    tables_used: list[str]
    source_versions: list[str]
    vendor_versions: list[str]
    evidence_rows: int


def _choice_stock_dependency_summary(
    *,
    stock_readiness: ChoiceStockReadiness,
    families: list[str],
    ready_summary: str,
) -> str:
    if stock_readiness.ready:
        return ready_summary

    relevant = [family for family in families if family in stock_readiness.missing_input_families]
    if not relevant:
        relevant = list(stock_readiness.missing_input_families)
    formatted = ", ".join(relevant) if relevant else "stock input families"
    status_text = "missing" if stock_readiness.status == "missing_catalog" else "incomplete"
    return f"Choice stock catalog is {status_text}; missing or unconfirmed required input families: {formatted}."


def _choice_stock_missing_inputs(*, stock_readiness: ChoiceStockReadiness, families: list[str]) -> list[str]:
    relevant = [family for family in families if family in stock_readiness.missing_input_families]
    return [str(family) for family in relevant] or list(families)


def _load_choice_stock_outputs(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
) -> _ChoiceStockOutputs:
    if not stock_readiness.ready or as_of_date is None:
        return _ChoiceStockOutputs(
            sector_coverage=None,
            stock_coverage=None,
            sector_rank_payload=None,
            stock_candidates_payload=None,
            risk_exit_payload=None,
            risk_exit_block_reason="",
            stock_candidate_block_reason="",
            tables_used=[],
            source_versions=[],
            vendor_versions=[],
            evidence_rows=0,
        )

    sector_coverage = load_choice_stock_materialization_coverage(
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
        required_items=SECTOR_REQUIRED_ITEMS,
    )
    stock_coverage = load_choice_stock_materialization_coverage(
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
    )
    tables_used: list[str] = []
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    evidence_rows = 0

    sector_rank_payload: dict[str, object] | None = None
    if sector_coverage.full_coverage:
        sector_rows, sector_tables, sector_sources, sector_vendors = _load_sector_rank_inputs(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
        )
        evidence_rows += len(sector_rows)
        tables_used.extend(sector_tables)
        source_versions.extend(sector_sources)
        vendor_versions.extend(sector_vendors)
        sector_result = compute_sector_rank(as_of_date=as_of_date, rows=sector_rows)
        sector_rank_payload = sector_result.payload if sector_result.ready else None

    stock_candidates_payload: dict[str, object] | None = None
    stock_candidate_block_reason = ""
    if (
        stock_coverage.full_coverage
        and sector_rank_payload is not None
        and market_state not in {"NO_DATA", "PENDING_DATA", "STALE"}
    ):
        snapshots, stock_tables, stock_sources, stock_vendors = _load_stock_candidate_snapshots(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
            sector_rank_payload=sector_rank_payload,
        )
        evidence_rows += len(snapshots)
        tables_used.extend(stock_tables)
        source_versions.extend(stock_sources)
        vendor_versions.extend(stock_vendors)
        if snapshots and not any(_safe_float(snapshot.limit_ratio) is not None for snapshot in snapshots):
            stock_candidate_block_reason = STOCK_CANDIDATE_LIMIT_RATIO_BLOCK_REASON
        else:
            stock_candidates_payload = compute_stock_candidates(
                as_of_date=as_of_date,
                market_state=market_state,
                snapshots=snapshots,
            ).payload

    risk_exit_payload: dict[str, object] | None = None
    risk_exit_block_reason = ""
    if stock_coverage.full_coverage:
        risk_snapshots, risk_tables, risk_sources, risk_vendors = _load_risk_exit_snapshots(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
        )
        if risk_snapshots:
            evidence_rows += len(risk_snapshots)
            tables_used.extend(risk_tables)
            source_versions.extend(risk_sources)
            vendor_versions.extend(risk_vendors)
            risk_exit_payload = compute_risk_exit(
                as_of_date=as_of_date,
                snapshots=risk_snapshots,
            ).payload
        else:
            risk_exit_block_reason = _risk_exit_input_block_reason(
                duckdb_path=duckdb_path,
                as_of_date=as_of_date,
            )

    return _ChoiceStockOutputs(
        sector_coverage=sector_coverage,
        stock_coverage=stock_coverage,
        sector_rank_payload=sector_rank_payload,
        stock_candidates_payload=stock_candidates_payload,
        risk_exit_payload=risk_exit_payload,
        risk_exit_block_reason=risk_exit_block_reason,
        stock_candidate_block_reason=stock_candidate_block_reason,
        tables_used=_unique_preserving_order(tables_used),
        source_versions=source_versions,
        vendor_versions=vendor_versions,
        evidence_rows=evidence_rows,
    )


def _load_sector_rank_inputs(
    *,
    duckdb_path: str,
    as_of_date: str,
) -> tuple[list[SectorRankConstituent], list[str], list[str], list[str]]:
    path = Path(duckdb_path)
    if not path.exists():
        return [], [], [], []
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return [], [], [], []
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required_tables = {"choice_stock_sector_membership", "choice_stock_daily_observation"}
        if not required_tables.issubset(tables):
            return [], [], [], []
        rows = conn.execute(
            """
            select
              membership.stock_code,
              membership.sw2021code,
              membership.sw2021,
              daily.pctchange,
              daily.turn,
              daily.amplitude,
              membership.source_version,
              membership.vendor_version,
              daily.source_version,
              daily.vendor_version
            from choice_stock_sector_membership membership
            join choice_stock_daily_observation daily
              on daily.stock_code = membership.stock_code
             and cast(daily.trade_date as date) = cast(? as date)
            where membership.as_of_date = ?
            """,
            [as_of_date, as_of_date],
        ).fetchall()
    except duckdb.Error:
        return [], ["choice_stock_sector_membership", "choice_stock_daily_observation"], [], []
    finally:
        conn.close()

    constituents = [
        SectorRankConstituent(
            stock_code=str(row[0] or ""),
            sector_code=str(row[1] or ""),
            sector_name=str(row[2] or ""),
            pctchange=row[3],
            turn=row[4],
            amplitude=row[5],
        )
        for row in rows
    ]
    source_versions = [str(value) for row in rows for value in (row[6], row[8]) if value]
    vendor_versions = [str(value) for row in rows for value in (row[7], row[9]) if value]
    return constituents, ["choice_stock_sector_membership", "choice_stock_daily_observation"], source_versions, vendor_versions


def _load_stock_candidate_snapshots(
    *,
    duckdb_path: str,
    as_of_date: str,
    sector_rank_payload: dict[str, object],
) -> tuple[list[StockCandidateSnapshot], list[str], list[str], list[str]]:
    path = Path(duckdb_path)
    if not path.exists():
        return [], [], [], []
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return [], [], [], []
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required_tables = {
            "choice_stock_universe",
            "choice_stock_sector_membership",
            "choice_stock_daily_observation",
            "choice_stock_limit_quality",
        }
        if not required_tables.issubset(tables):
            return [], [], [], []
        current_rows = conn.execute(
            """
            select
              universe.stock_code,
              universe.stock_name,
              membership.sw2021code,
              membership.sw2021,
              daily.open_value,
              daily.high_value,
              daily.low_value,
              daily.close_value,
              daily.turn,
              daily.highlimit,
              daily.lowlimit,
              limits.issurgedlimit,
              universe.source_version,
              universe.vendor_version,
              membership.source_version,
              membership.vendor_version,
              daily.source_version,
              daily.vendor_version,
              limits.source_version,
              limits.vendor_version
            from choice_stock_universe universe
            join choice_stock_sector_membership membership
              on membership.stock_code = universe.stock_code
             and membership.as_of_date = universe.as_of_date
            join choice_stock_daily_observation daily
              on daily.stock_code = universe.stock_code
             and cast(daily.trade_date as date) = cast(? as date)
            join choice_stock_limit_quality limits
              on limits.stock_code = universe.stock_code
             and limits.as_of_date = universe.as_of_date
            where universe.as_of_date = ?
            """,
            [as_of_date, as_of_date],
        ).fetchall()
        stock_codes = [str(row[0]) for row in current_rows if row[0]]
        if not stock_codes:
            return [], list(required_tables), [], []
        placeholders = ",".join("?" for _ in stock_codes)
        history_rows = conn.execute(
            f"""
            select stock_code, close_value, turn
            from choice_stock_daily_observation
            where stock_code in ({placeholders})
              and cast(trade_date as date) <= cast(? as date)
            order by stock_code asc, cast(trade_date as date) asc
            """,
            [*stock_codes, as_of_date],
        ).fetchall()
    except duckdb.Error:
        return [], list(required_tables), [], []
    finally:
        conn.close()

    history_by_code: dict[str, dict[str, list[float]]] = {}
    for row in history_rows:
        stock_code = str(row[0] or "")
        close_value = _safe_float(row[1])
        turn_value = _safe_float(row[2])
        if not stock_code or close_value is None or turn_value is None:
            continue
        history = history_by_code.setdefault(stock_code, {"close": [], "turn": []})
        history["close"].append(close_value)
        history["turn"].append(turn_value)

    sector_rank_by_key: dict[tuple[str, str], int] = {}
    for item in cast(list[dict[str, object]], sector_rank_payload["items"]):
        rank = _safe_int(item.get("rank"))
        if rank is None:
            continue
        sector_rank_by_key[(str(item["sector_code"]), str(item["sector_name"]))] = rank
    snapshots: list[StockCandidateSnapshot] = []
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    for row in current_rows:
        stock_code = str(row[0] or "")
        sector_code = str(row[2] or "")
        sector_name = str(row[3] or "")
        history = history_by_code.get(stock_code, {"close": [], "turn": []})
        prior_close = history["close"][-2] if len(history["close"]) >= 2 else None
        stock_name = str(row[1] or "")
        limit_ratio = _limit_ratio(
            highlimit=row[9],
            lowlimit=row[10],
            prior_close=prior_close,
            stock_code=stock_code,
            stock_name=stock_name,
            as_of_date=as_of_date,
        )
        open_value = _safe_float(row[4])
        high_value = _safe_float(row[5])
        low_value = _safe_float(row[6])
        close_value = _safe_float(row[7])
        one_word_board = (
            open_value is not None
            and high_value is not None
            and low_value is not None
            and close_value is not None
            and abs(open_value - high_value) < 1e-9
            and abs(high_value - low_value) < 1e-9
            and abs(low_value - close_value) < 1e-9
        )
        highlimit = _safe_float(row[9])
        closed_up_limit = bool(_truthy(row[11]) and highlimit is not None and close_value is not None and close_value >= highlimit - 1e-9)
        snapshots.append(
                StockCandidateSnapshot(
                    stock_code=stock_code,
                    stock_name=stock_name,
                sector_code=sector_code,
                sector_name=sector_name,
                sector_rank=sector_rank_by_key.get((sector_code, sector_name)),
                open_value=row[4],
                high_value=row[5],
                low_value=row[6],
                close_value=row[7],
                turnover_free=row[8],
                limit_ratio=limit_ratio,
                one_word_board=one_word_board,
                closed_up_limit=closed_up_limit,
                close_history=history["close"],
                turnover_history=history["turn"],
            )
        )
        source_versions.extend(str(value) for value in (row[12], row[14], row[16], row[18]) if value)
        vendor_versions.extend(str(value) for value in (row[13], row[15], row[17], row[19]) if value)

    tables_used = [
        "choice_stock_universe",
        "choice_stock_sector_membership",
        "choice_stock_daily_observation",
        "choice_stock_limit_quality",
    ]
    return snapshots, tables_used, source_versions, vendor_versions


def _load_risk_exit_snapshots(
    *,
    duckdb_path: str,
    as_of_date: str,
) -> tuple[list[RiskExitSnapshot], list[str], list[str], list[str]]:
    path = Path(duckdb_path)
    if not path.exists():
        return [], [], [], []
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return [], [], [], []
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required_tables = {"livermore_position_snapshot", "choice_stock_daily_observation"}
        if not required_tables.issubset(tables):
            return [], [], [], []
        position_rows = conn.execute(
            """
            select
              stock_code,
              stock_name,
              entry_cost,
              bars_since_entry,
              source_version,
              vendor_version
            from livermore_position_snapshot
            where as_of_date = ?
              and upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
            order by stock_code asc
            """,
            [as_of_date],
        ).fetchall()
        stock_codes = [str(row[0]) for row in position_rows if row[0]]
        if not stock_codes:
            return [], list(required_tables), [], []
        placeholders = ",".join("?" for _ in stock_codes)
        history_rows = conn.execute(
            f"""
            select stock_code, close_value, source_version, vendor_version
            from choice_stock_daily_observation
            where stock_code in ({placeholders})
              and cast(trade_date as date) <= cast(? as date)
            order by stock_code asc, cast(trade_date as date) asc
            """,
            [*stock_codes, as_of_date],
        ).fetchall()
    except duckdb.Error:
        return [], list(required_tables), [], []
    finally:
        conn.close()

    close_history_by_code: dict[str, list[float]] = {}
    history_sources: list[str] = []
    history_vendors: list[str] = []
    for row in history_rows:
        stock_code = str(row[0] or "")
        close_value = _safe_float(row[1])
        if not stock_code or close_value is None:
            continue
        close_history_by_code.setdefault(stock_code, []).append(close_value)
        if row[2]:
            history_sources.append(str(row[2]))
        if row[3]:
            history_vendors.append(str(row[3]))

    snapshots = [
        RiskExitSnapshot(
            stock_code=str(row[0] or ""),
            stock_name=str(row[1] or ""),
            entry_cost=row[2],
            bars_since_entry=row[3],
            close_history=close_history_by_code.get(str(row[0] or ""), []),
        )
        for row in position_rows
        if row[0]
    ]
    position_sources = [str(row[4]) for row in position_rows if row[4]]
    position_vendors = [str(row[5]) for row in position_rows if row[5]]
    return (
        snapshots,
        ["livermore_position_snapshot", "choice_stock_daily_observation"],
        [*position_sources, *history_sources],
        [*position_vendors, *history_vendors],
    )


def _risk_exit_input_block_reason(
    *,
    duckdb_path: str,
    as_of_date: str,
) -> str:
    path = Path(duckdb_path)
    if not path.exists():
        return "DuckDB database is not available, so Livermore position and close-history inputs are not materialized."
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return "DuckDB database is unavailable while checking Livermore position and close-history inputs."
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "livermore_position_snapshot" not in tables:
            return "livermore_position_snapshot table is not materialized for Livermore A-share holdings."
        if "choice_stock_daily_observation" not in tables:
            return "choice_stock_daily_observation close history is not materialized for Livermore risk_exit."
        total_rows, active_rows = conn.execute(
            """
            select
              count(*)::integer,
              sum(case when upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE' then 1 else 0 end)::integer
            from livermore_position_snapshot
            where as_of_date = ?
            """,
            [as_of_date],
        ).fetchone()
        if int(active_rows or 0) <= 0:
            latest_row = conn.execute(
                """
                select max(as_of_date)
                from livermore_position_snapshot
                where upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
                """
            ).fetchone()
            latest_active_date = latest_row[0] if latest_row else None
            if int(total_rows or 0) > 0:
                return f"livermore_position_snapshot has rows but no ACTIVE A-share rows for as_of_date {as_of_date}."
            if latest_active_date:
                return (
                    "livermore_position_snapshot has no ACTIVE A-share rows for as_of_date "
                    f"{as_of_date}; latest ACTIVE as_of_date is {latest_active_date}."
                )
            return f"livermore_position_snapshot has no ACTIVE A-share rows for as_of_date {as_of_date}."
        close_rows = conn.execute(
            """
            select count(*)::integer
            from choice_stock_daily_observation daily
            join livermore_position_snapshot position
              on position.stock_code = daily.stock_code
            where position.as_of_date = ?
              and upper(coalesce(position.position_status, 'ACTIVE')) = 'ACTIVE'
              and cast(daily.trade_date as date) <= cast(? as date)
              and daily.close_value is not null
            """,
            [as_of_date, as_of_date],
        ).fetchone()[0]
        if int(close_rows or 0) <= 0:
            return (
                "livermore_position_snapshot has ACTIVE A-share rows, but choice_stock_daily_observation "
                f"has no close history through {as_of_date} for those stock_codes."
            )
        return ""
    except duckdb.Error:
        return "DuckDB query failed while checking Livermore position and close-history inputs."
    finally:
        conn.close()


def _build_supported_outputs(
    state: str,
    *,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> tuple[list[str], list[dict[str, str]]]:
    sector_reason = _sector_unavailable_reason(stock_readiness=stock_readiness, stock_outputs=stock_outputs)
    stock_reason = _stock_unavailable_reason(
        market_state=state,
        stock_readiness=stock_readiness,
        stock_outputs=stock_outputs,
    )
    supported: list[str] = []
    unsupported: list[dict[str, str]] = []
    if state == "NO_DATA":
        unsupported.append(
            {
                "key": "market_gate",
                "reason": "Broad-index history is unavailable for CA.CSI300.",
            }
        )
    else:
        supported.append("market_gate")
    if stock_outputs.sector_rank_payload is not None:
        supported.append("sector_rank")
    else:
        unsupported.append({"key": "sector_rank", "reason": sector_reason})
    if stock_outputs.stock_candidates_payload is not None:
        supported.append("stock_candidates")
    else:
        unsupported.append({"key": "stock_candidates", "reason": stock_reason})
    if stock_outputs.risk_exit_payload is not None:
        supported.append("risk_exit")
    else:
        unsupported.append(
            {"key": "risk_exit", "reason": _risk_unavailable_reason(stock_outputs.risk_exit_block_reason)}
        )
    return supported, unsupported


def _gate_supplement_breadth_limit(
    *,
    supplement: MarketGateSupplement | None,
    latest_trade_date: date | None,
) -> tuple[bool, bool]:
    if supplement is None or latest_trade_date is None or supplement.trade_date != latest_trade_date:
        return False, False
    return (
        supplement.breadth_5d is not None,
        supplement.limit_up_quality_ok is not None,
    )


def _build_rule_readiness(
    *,
    market_gate: dict[str, object],
    history_count: int,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
    supplement: MarketGateSupplement | None = None,
    latest_trade_date: date | None = None,
) -> list[dict[str, object]]:
    breadth_landed, limit_up_landed = _gate_supplement_breadth_limit(
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    gate_state = str(market_gate["state"])
    if gate_state == "NO_DATA":
        gate_status = "missing"
        gate_summary = "Broad-index history is unavailable, so the market gate cannot be evaluated."
        gate_missing_inputs = ["broad_index_history", "breadth", "limit_up_quality"]
    elif gate_state == "STALE":
        gate_status = "stale"
        gate_summary = "Broad-index history resolved, but the latest landed point is stale."
        gate_missing_inputs = ["breadth", "limit_up_quality"]
    elif gate_state == "PENDING_DATA":
        gate_status = "partial"
        gate_summary = f"Broad-index history is present but only {history_count} observations are landed."
        gate_missing_inputs = ["breadth", "limit_up_quality"]
    else:
        gate_missing_inputs = []
        if not breadth_landed:
            gate_missing_inputs.append("breadth")
        if not limit_up_landed:
            gate_missing_inputs.append("limit_up_quality")
        if gate_missing_inputs:
            gate_status = "partial"
            gate_summary = "Trend market gate is available; supplement breadth and/or limit-up inputs remain missing."
        else:
            gate_status = "ready"
            gate_summary = "All broad-index and supplement gate inputs are landed for the resolved trade date."
    sector_missing_inputs = _sector_missing_inputs(stock_readiness=stock_readiness, stock_outputs=stock_outputs)
    stock_missing_inputs = _stock_missing_inputs(
        market_state=gate_state,
        stock_readiness=stock_readiness,
        stock_outputs=stock_outputs,
    )
    sector_status = _sector_status(stock_readiness=stock_readiness, stock_outputs=stock_outputs)
    stock_status = _stock_status(market_state=gate_state, stock_readiness=stock_readiness, stock_outputs=stock_outputs)
    sector_summary = (
        "Sector ranking is available from landed Choice sector inputs."
        if stock_outputs.sector_rank_payload is not None
        else _sector_unavailable_reason(stock_readiness=stock_readiness, stock_outputs=stock_outputs)
    )
    stock_summary = (
        "Stock pivot candidate screening is available for landed Choice stock inputs."
        if stock_outputs.stock_candidates_payload is not None
        else _stock_unavailable_reason(
            market_state=gate_state,
            stock_readiness=stock_readiness,
            stock_outputs=stock_outputs,
        )
    )
    risk_status = "ready" if stock_outputs.risk_exit_payload is not None else "blocked"
    risk_summary = (
        "Risk and exit output is available from landed position snapshots and close history."
        if stock_outputs.risk_exit_payload is not None
        else _risk_unavailable_reason(stock_outputs.risk_exit_block_reason)
    )
    risk_missing_inputs = [] if stock_outputs.risk_exit_payload is not None else list(RISK_EXIT_REQUIRED_INPUTS)
    return [
        {
            "key": "market_gate",
            "title": "Market gate",
            "status": gate_status,
            "summary": gate_summary,
            "required_inputs": [
                "broad_index_history",
                "breadth",
                "limit_up_quality",
            ],
            "missing_inputs": gate_missing_inputs,
        },
        {
            "key": "sector_rank",
            "title": "Sector ranking",
            "status": sector_status,
            "summary": sector_summary,
            "required_inputs": ["sector_membership", "sector_strength"],
            "missing_inputs": sector_missing_inputs,
        },
        {
            "key": "stock_pivot",
            "title": "Stock pivot filters",
            "status": stock_status,
            "summary": stock_summary,
            "required_inputs": [
                "stock_universe",
                "stock_ohlcv",
                "stock_status",
                "limit_up_quality",
                "sector_rank",
                "market_gate",
            ],
            "missing_inputs": stock_missing_inputs,
        },
        {
            "key": "risk_exit",
            "title": "Risk and exit rules",
            "status": risk_status,
            "summary": risk_summary,
            "required_inputs": list(RISK_EXIT_REQUIRED_INPUTS),
            "missing_inputs": risk_missing_inputs,
        },
    ]


def _build_data_gaps(
    *,
    market_gate: dict[str, object],
    history_count: int,
    resolved_as_of_date: str | None,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
    supplement: MarketGateSupplement | None = None,
    latest_trade_date: date | None = None,
) -> list[dict[str, str]]:
    breadth_landed, limit_up_landed = _gate_supplement_breadth_limit(
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    date_label = resolved_as_of_date or (latest_trade_date.isoformat() if latest_trade_date else "resolved date")
    gaps = []
    if not breadth_landed:
        gaps.append(
            {
                "input_family": "breadth",
                "status": "missing",
                "evidence": "5-day breadth input family is not landed in DuckDB for this slice.",
            }
        )
    elif supplement is not None and supplement.breadth_5d is not None:
        gaps.append(
            {
                "input_family": "breadth",
                "status": "ready",
                "evidence": (
                    f"5-day breadth {supplement.breadth_5d:.4f} landed in "
                    f"fact_livermore_gate_supplement_daily for {date_label}."
                ),
            }
        )

    if not limit_up_landed:
        gaps.append(
            {
            "input_family": "limit_up_quality",
            "status": "missing",
            "evidence": _choice_stock_dependency_summary(
                stock_readiness=stock_readiness,
                families=["limit_up_quality"],
                ready_summary="Choice limit-up quality catalog is confirmed, but DuckDB materialization is not landed.",
            ),
            }
        )
    elif supplement is not None and supplement.limit_up_quality_ok is not None:
        gaps.append(
            {
                "input_family": "limit_up_quality",
                "status": "ready",
                "evidence": (
                    f"Market gate limit-up quality flag ({supplement.limit_up_quality_ok}) landed in "
                    f"fact_livermore_gate_supplement_daily for {date_label}."
                ),
            }
        )
    if stock_outputs.risk_exit_payload is None:
        gaps.append(
            {
                "input_family": "position_risk",
                "status": "missing",
                "evidence": _risk_unavailable_reason(stock_outputs.risk_exit_block_reason),
            }
        )
    if stock_outputs.sector_rank_payload is None:
        gaps.append(
            {
                "input_family": "sector_strength",
                "status": _coverage_gap_status(stock_outputs.sector_coverage),
                "evidence": _sector_unavailable_reason(stock_readiness=stock_readiness, stock_outputs=stock_outputs),
            }
        )
    if stock_outputs.stock_candidates_payload is None:
        gaps.append(
            {
                "input_family": _stock_unavailable_input_family(stock_outputs),
                "status": _coverage_gap_status(stock_outputs.stock_coverage),
                "evidence": _stock_unavailable_reason(
                    market_state=str(market_gate["state"]),
                    stock_readiness=stock_readiness,
                    stock_outputs=stock_outputs,
                ),
            }
        )
    gate_state = str(market_gate["state"])
    if gate_state == "NO_DATA":
        gaps.insert(
            0,
            {
                "input_family": "broad_index_history",
                "status": "missing",
                "evidence": "CA.CSI300 history is unavailable in fact_choice_macro_daily/choice_market_snapshot.",
            },
        )
    elif gate_state == "PENDING_DATA":
        gaps.insert(
            0,
            {
                "input_family": "broad_index_history",
                "status": "partial",
                "evidence": f"CA.CSI300 history has {history_count} observations; 60 are required.",
            },
        )
    elif gate_state == "STALE":
        gaps.insert(
            0,
            {
                "input_family": "broad_index_history",
                "status": "stale",
                "evidence": f"Latest CA.CSI300 input on {resolved_as_of_date} is marked stale.",
            },
        )
    return gaps


def _build_diagnostics(
    *,
    requested_as_of_date: str | None,
    resolved_as_of_date: str | None,
    market_gate: dict[str, object],
    history_count: int,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
    supplement: MarketGateSupplement | None = None,
    latest_trade_date: date | None = None,
) -> list[dict[str, str | None]]:
    diagnostics: list[dict[str, str | None]] = []
    breadth_landed, limit_up_landed = _gate_supplement_breadth_limit(
        supplement=supplement,
        latest_trade_date=latest_trade_date,
    )
    state = str(market_gate["state"])
    if requested_as_of_date is not None and resolved_as_of_date != requested_as_of_date:
        diagnostics.append(
            {
                "severity": "info",
                "code": "LIVERMORE_REQUESTED_DATE_RESOLVED_TO_AVAILABLE",
                "message": (
                    f"Requested {requested_as_of_date}; resolved to latest available broad-index input "
                    f"{resolved_as_of_date}."
                ),
                "input_family": "broad_index_history",
            }
        )
    if state == "NO_DATA":
        diagnostics.append(
            {
                "severity": "error",
                "code": "LIVERMORE_BROAD_INDEX_NO_DATA",
                "message": "CA.CSI300 history is unavailable in landed market-data tables.",
                "input_family": "broad_index_history",
            }
        )
    elif state == "PENDING_DATA":
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_BROAD_INDEX_INSUFFICIENT_HISTORY",
                "message": f"Need at least 60 broad-index observations; found {history_count}.",
                "input_family": "broad_index_history",
            }
        )
    elif state == "STALE":
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_BROAD_INDEX_STALE",
                "message": "Latest CA.CSI300 input is marked stale and cannot be treated as current.",
                "input_family": "broad_index_history",
            }
        )
    if not breadth_landed:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_BREADTH_MISSING",
                "message": "Breadth inputs are unavailable; the market gate is capped at the trend-only slice.",
                "input_family": "breadth",
            }
        )
    if not limit_up_landed:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_LIMIT_UP_QUALITY_MISSING",
                "message": _choice_stock_dependency_summary(
                    stock_readiness=stock_readiness,
                    families=["limit_up_quality"],
                    ready_summary=(
                        "Choice limit-up quality catalog is confirmed, but landed inputs are unavailable; "
                        "the market gate is capped at the trend-only slice."
                    ),
                ),
                "input_family": "limit_up_quality",
            }
        )
    if stock_outputs.risk_exit_payload is None:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_RISK_INPUTS_MISSING",
                "message": _risk_unavailable_reason(stock_outputs.risk_exit_block_reason),
                "input_family": "position_risk",
            }
        )
    if stock_outputs.sector_rank_payload is None:
        diagnostics.append(
            {
                "severity": "warning",
                "code": (
                    "LIVERMORE_SECTOR_RANK_INSUFFICIENT_DATA"
                    if stock_readiness.ready
                    and stock_outputs.sector_coverage is not None
                    and stock_outputs.sector_coverage.full_coverage
                    else "LIVERMORE_SECTOR_INPUTS_MISSING"
                ),
                "message": _sector_unavailable_reason(stock_readiness=stock_readiness, stock_outputs=stock_outputs),
                "input_family": "sector_strength",
            }
        )
    else:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_SECTOR_RANK_PROVISIONAL_FORMULA",
                "message": "Sector rank currently uses the provisional percentile formula over pctchange, turn, and amplitude.",
                "input_family": "sector_strength",
            }
        )
    if stock_outputs.stock_candidates_payload is None:
        stock_reason = _stock_unavailable_reason(
            market_state=state,
            stock_readiness=stock_readiness,
            stock_outputs=stock_outputs,
        )
        if stock_reason:
            diagnostics.append(
                {
                    "severity": "warning",
                    "code": (
                        "LIVERMORE_STOCK_INPUTS_MISSING"
                        if not stock_readiness.ready
                        or stock_outputs.stock_coverage is None
                        or not stock_outputs.stock_coverage.full_coverage
                        else "LIVERMORE_STOCK_PIVOT_BLOCKED"
                    ),
                    "message": stock_reason,
                    "input_family": _stock_unavailable_input_family(stock_outputs),
                }
            )
    elif _safe_int(stock_outputs.stock_candidates_payload.get("candidate_count")) == 0 and (
        _safe_int(stock_outputs.stock_candidates_payload.get("insufficient_history_count")) or 0
    ) > 0:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "LIVERMORE_STOCK_CANDIDATES_INSUFFICIENT_HISTORY",
                "message": "Stock inputs are landed, but some names still lack enough history for the 55-day breakout and MA120 filters.",
                "input_family": "stock_universe",
            }
        )
    return diagnostics


def _sector_unavailable_reason(
    *,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["sector_membership", "sector_strength"],
            ready_summary="",
        )
    if stock_outputs.sector_coverage is None or stock_outputs.sector_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but sector ranking inputs are not materialized yet."
    if not stock_outputs.sector_coverage.full_coverage:
        return stock_outputs.sector_coverage.message
    return "Choice sector inputs are landed, but fewer than three rankable sectors are available."


def _stock_unavailable_reason(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if stock_outputs.stock_candidate_block_reason:
        return stock_outputs.stock_candidate_block_reason
    if not stock_readiness.ready:
        return _choice_stock_dependency_summary(
            stock_readiness=stock_readiness,
            families=["stock_universe", "stock_ohlcv", "stock_status", "limit_up_quality"],
            ready_summary="",
        )
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "Choice stock catalog is confirmed, but stock candidate inputs are not materialized yet."
    if not stock_outputs.stock_coverage.full_coverage:
        return stock_outputs.stock_coverage.message
    if stock_outputs.sector_rank_payload is None:
        return "Sector rank is unavailable, so stock candidates remain blocked."
    if market_state in {"NO_DATA", "PENDING_DATA", "STALE"}:
        return "Market gate is unavailable or stale, so stock candidates cannot be evaluated."
    return ""


def _stock_unavailable_input_family(stock_outputs: _ChoiceStockOutputs) -> str:
    if stock_outputs.stock_candidate_block_reason:
        return "limit_up_quality"
    return "stock_universe"


def _risk_unavailable_reason(specific_reason: str = "") -> str:
    reason = (
        f"The defended-bundle {MVP_RULE_LABEL} MVP remains blocked. Existing formal ledger "
        "position_snapshot/position_snapshot_agg are not accepted for Livermore A-share risk_exit "
        "because their governed schema is bond/ledger-shaped and lacks proven stock_code, "
        "Livermore entry_cost, and bars_since_entry semantics. Current accepted stock holding "
        "fact source remains livermore_position_snapshot plus choice_stock_daily_observation close_history."
    )
    if specific_reason:
        return f"{reason} Current blocker: {specific_reason}"
    return reason


def _coverage_gap_status(coverage: ChoiceStockMaterializationCoverage | None) -> str:
    if coverage is None:
        return "missing"
    if coverage.status == "partial":
        return "partial"
    return "missing"


def _sector_status(
    *,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if stock_outputs.sector_rank_payload is not None:
        return "ready"
    if not stock_readiness.ready:
        return "missing"
    if stock_outputs.sector_coverage is None or stock_outputs.sector_coverage.status == "not_materialized":
        return "missing"
    if not stock_outputs.sector_coverage.full_coverage:
        return "partial"
    return "blocked"


def _stock_status(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> str:
    if stock_outputs.stock_candidates_payload is not None:
        return "ready"
    if not stock_readiness.ready:
        return "blocked"
    if stock_outputs.stock_coverage is None or stock_outputs.stock_coverage.status == "not_materialized":
        return "blocked"
    if not stock_outputs.stock_coverage.full_coverage:
        return "partial"
    if stock_outputs.sector_rank_payload is None or market_state in {"NO_DATA", "PENDING_DATA", "STALE"}:
        return "blocked"
    return "blocked"


def _sector_missing_inputs(
    *,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> list[str]:
    if stock_outputs.sector_rank_payload is not None:
        return []
    if not stock_readiness.ready:
        return _choice_stock_missing_inputs(
            stock_readiness=stock_readiness,
            families=["sector_membership", "sector_strength"],
        )
    if stock_outputs.sector_coverage is None or stock_outputs.sector_coverage.full_coverage:
        return []
    return _missing_families_from_request_items(stock_outputs.sector_coverage.missing_request_items)


def _stock_missing_inputs(
    *,
    market_state: str,
    stock_readiness: ChoiceStockReadiness,
    stock_outputs: _ChoiceStockOutputs,
) -> list[str]:
    if stock_outputs.stock_candidates_payload is not None:
        return []
    missing_inputs: list[str] = []
    if not stock_readiness.ready:
        missing_inputs.extend(
            _choice_stock_missing_inputs(
                stock_readiness=stock_readiness,
                families=["stock_universe", "stock_ohlcv", "stock_status", "limit_up_quality"],
            )
        )
    elif stock_outputs.stock_coverage is not None and not stock_outputs.stock_coverage.full_coverage:
        missing_inputs.extend(_missing_families_from_request_items(stock_outputs.stock_coverage.missing_request_items))
    if stock_outputs.stock_candidate_block_reason and "limit_ratio" not in missing_inputs:
        missing_inputs.append("limit_ratio")
    if stock_outputs.sector_rank_payload is None and "sector_rank" not in missing_inputs:
        missing_inputs.append("sector_rank")
    if market_state in {"NO_DATA", "PENDING_DATA", "STALE"} and "market_gate" not in missing_inputs:
        missing_inputs.append("market_gate")
    return _unique_preserving_order(missing_inputs)


def _missing_families_from_request_items(items: list[str]) -> list[str]:
    families = [str(item).split(":", 1)[0] for item in items if item]
    return _unique_preserving_order(families)


def _limit_ratio(
    *,
    highlimit: object,
    lowlimit: object,
    prior_close: float | None,
    stock_code: str,
    stock_name: str,
    as_of_date: str,
) -> float | None:
    if prior_close is None or prior_close <= 0:
        return None
    high_value = _safe_float(highlimit)
    if high_value is not None and high_value > 0:
        ratio = abs((high_value - prior_close) / prior_close)
        if ratio > 0:
            return ratio
    low_value = _safe_float(lowlimit)
    if low_value is not None and low_value > 0:
        ratio = abs((prior_close - low_value) / prior_close)
        if ratio > 0:
            return ratio
    return _rule_derived_limit_ratio(
        stock_code=stock_code,
        stock_name=stock_name,
        as_of_date=as_of_date,
    )


def _rule_derived_limit_ratio(*, stock_code: str, stock_name: str, as_of_date: str) -> float | None:
    code = stock_code.strip().upper()
    if not code:
        return None
    if code.endswith(".BJ") or code.startswith(("8", "4", "920")):
        return 0.30
    if code.endswith(".SH") and code.startswith(("688", "689")):
        return 0.20
    if code.endswith(".SZ") and code.startswith(("300", "301")):
        return 0.20
    if _is_risk_warning_stock_name(stock_name) and _date_before(as_of_date, MAINBOARD_RISK_WARNING_LIMIT_RATIO_10_START):
        return 0.05
    if code.endswith((".SH", ".SZ")):
        return 0.10
    return None


def _is_risk_warning_stock_name(stock_name: str) -> bool:
    normalized = stock_name.strip().upper()
    return normalized.startswith("*ST") or normalized.startswith("ST")


def _date_before(value: str, threshold: date) -> bool:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed < threshold


def _safe_float(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number


def _safe_int(value: object) -> int | None:
    number = _safe_float(value)
    return None if number is None else int(number)


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _quality_flag_for_market_gate(state: str) -> str:
    if state == "STALE":
        return "stale"
    if state in {"NO_DATA", "PENDING_DATA"}:
        return "warning"
    return "ok"


def _vendor_status_for_state(state: str) -> str:
    if state == "STALE":
        return "vendor_stale"
    if state == "NO_DATA":
        return "vendor_unavailable"
    return "ok"


def _aggregate_lineage(values: list[str], *, empty_value: str) -> str:
    distinct = sorted({value for value in values if value})
    if not distinct:
        return empty_value
    if len(distinct) == 1:
        return distinct[0]
    return "__".join(distinct)
