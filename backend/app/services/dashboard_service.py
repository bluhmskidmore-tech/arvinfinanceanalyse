"""Consolidated dashboard KPIs — analytical basis, reads formal facts + DuckDB aggregates."""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import FACT_TABLE
from backend.app.repositories.dashboard_repo import TYW_FACT, DashboardRepository
from backend.app.schemas.common_numeric import Numeric, null_numeric, numeric_from_raw
from backend.app.schemas.dashboard import (
    CoreMetricsCardData,
    CoreMetricsPayload,
    DailyChangePeriod,
    DailyChangesPayload,
)
from backend.app.services.formal_result_runtime import build_result_envelope

Q8 = Decimal("0.00000001")

_DASHBOARD_CACHE_VERSION = "cv_dashboard_analytical_v1"
_DASHBOARD_RULE_VERSION = "rv_dashboard_read_v1"
_DASHBOARD_SOURCE_VERSION = "sv_dashboard_duckdb"

_PeriodLiteral = Literal["day", "week", "month"]


def _repo() -> DashboardRepository:
    return DashboardRepository(str(get_settings().duckdb_path))


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _pct_numeric_from_fraction(frac: Decimal | None, *, precision: int = 8) -> Numeric:
    if frac is None:
        return null_numeric(unit="pct", precision=precision, sign_aware=False)
    pct = frac * Decimal("100")
    return numeric_from_raw(
        raw=float(pct),
        unit="pct",
        precision=precision,
        sign_aware=False,
        signed_format=False,
    )


def _yuan_numeric(val: Decimal, *, sign_aware: bool) -> Numeric:
    return numeric_from_raw(
        raw=float(val),
        unit="yuan",
        precision=8,
        sign_aware=sign_aware,
        signed_format=sign_aware,
    )


def _pct_change_numeric(chg_amt: Decimal, prev: Decimal) -> Numeric:
    if prev <= 0:
        return null_numeric(unit="pct", precision=8, sign_aware=True)
    pct = (chg_amt / prev) * Decimal("100")
    return numeric_from_raw(
        raw=float(pct),
        unit="pct",
        precision=8,
        sign_aware=True,
        signed_format=True,
    )


def _fmt813(value: Decimal) -> str:
    return format(value.quantize(Q8, rounding=ROUND_HALF_UP), "f")


def _top_3_detail_rows(
    rows: list[tuple[str, Decimal, Decimal | None]],
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for name, amt, rte in rows:
        frac = rte if rte is not None else Decimal("0")
        out.append({"name": name, "amount": _fmt813(amt), "rate": _fmt813(frac)})
    return out


def _prior_by_offset(canonical_desc: list[str], anchor: str, offset: int) -> str | None:
    if anchor not in canonical_desc:
        return None
    i = canonical_desc.index(anchor)
    j = i + offset
    return canonical_desc[j] if j < len(canonical_desc) else None


def _first_in_month(merged_asc: list[str], anchor: str) -> str | None:
    """First (earliest) merged date in anchor's calendar month, not later than anchor."""
    if len(anchor) < 7:
        return None
    ym = anchor[:7]
    in_month = sorted([d for d in merged_asc if d.startswith(ym) and d <= anchor])
    return in_month[0] if in_month else None


def _prior_for_period(canonical_desc: list[str], anchor: str, kind: _PeriodLiteral) -> str | None:
    if not canonical_desc:
        return None
    asc = sorted(canonical_desc, reverse=False)
    desc_newest_first = sorted(canonical_desc, reverse=True)
    if anchor not in desc_newest_first:
        return None
    if kind == "day":
        return _prior_by_offset(desc_newest_first, anchor, 1)
    if kind == "week":
        return _prior_by_offset(desc_newest_first, anchor, 5)
    if kind == "month":
        return _first_in_month(asc, anchor)
    return None


def _build_one_core_card(
    cur_tot: Decimal,
    cur_wr: Decimal | None,
    prev_tot: Decimal,
    top: list[tuple[str, Decimal, Decimal | None]],
) -> CoreMetricsCardData:
    chg_amt = cur_tot - prev_tot
    return CoreMetricsCardData(
        total_amount=_yuan_numeric(cur_tot, sign_aware=False),
        weighted_avg_rate=_pct_numeric_from_fraction(cur_wr),
        change_amount=_yuan_numeric(chg_amt, sign_aware=True),
        change_pct=_pct_change_numeric(chg_amt, prev_tot),
        top_3_details=_top_3_detail_rows(top),
    )


def _dashboard_anchor(report_date: str | None, canonical_desc: list[str]) -> str | None:
    s = "" if report_date is None else str(report_date).strip()
    if s != "":
        return s
    if canonical_desc:
        return canonical_desc[0]
    return None


def _zeroed_metrics_card() -> CoreMetricsCardData:
    zero = Decimal("0")
    return CoreMetricsCardData(
        total_amount=_yuan_numeric(zero, sign_aware=False),
        weighted_avg_rate=_pct_numeric_from_fraction(None),
        change_amount=_yuan_numeric(zero, sign_aware=True),
        change_pct=null_numeric(unit="pct", precision=8, sign_aware=True),
        top_3_details=[],
    )


def get_core_metrics(report_date: str | None = None) -> dict[str, object]:
    repo = _repo()
    canonical = sorted(repo.list_merged_report_dates())
    canonical_desc = sorted(canonical, reverse=True)
    anchor = _dashboard_anchor(report_date, canonical_desc)
    trace = _trace_id()

    zcard = _zeroed_metrics_card()
    if anchor is None:
        payload = CoreMetricsPayload(
            report_date="",
            bond_investments=zcard.model_copy(deep=True),
            interbank_assets=zcard.model_copy(deep=True),
            interbank_liabilities=zcard.model_copy(deep=True),
        ).model_dump(mode="json")
        return build_result_envelope(
            basis="analytical",
            trace_id=trace,
            result_kind="dashboard.core_metrics",
            cache_version=_DASHBOARD_CACHE_VERSION,
            source_version=_DASHBOARD_SOURCE_VERSION,
            rule_version=_DASHBOARD_RULE_VERSION,
            quality_flag="warning",
            result_payload=payload,
            tables_used=[FACT_TABLE, TYW_FACT],
            evidence_rows=0,
        )

    prev_day = (
        _prior_for_period(canonical_desc, anchor, "day") if anchor in canonical_desc else None
    )

    if prev_day is None:
        b_prev = Decimal("0")
        a_prev = Decimal("0")
        l_prev = Decimal("0")
    else:
        b_prev_t, _, _ = repo.fetch_bond_core_metrics(prev_day)
        a_prev_t, _, _ = repo.fetch_tyw_core_metrics(prev_day, asset_side=True)
        l_prev_t, _, _ = repo.fetch_tyw_core_metrics(prev_day, asset_side=False)
        b_prev, a_prev, l_prev = b_prev_t, a_prev_t, l_prev_t

    b_cur, b_wy, b_top = repo.fetch_bond_core_metrics(anchor)

    a_cur, a_wy, a_top = repo.fetch_tyw_core_metrics(anchor, asset_side=True)

    l_cur, l_wy, l_top = repo.fetch_tyw_core_metrics(anchor, asset_side=False)

    body = CoreMetricsPayload(
        report_date=anchor,
        bond_investments=_build_one_core_card(b_cur, b_wy, b_prev, b_top),
        interbank_assets=_build_one_core_card(a_cur, a_wy, a_prev, a_top),
        interbank_liabilities=_build_one_core_card(l_cur, l_wy, l_prev, l_top),
    )

    return build_result_envelope(
        basis="analytical",
        trace_id=trace,
        result_kind="dashboard.core_metrics",
        cache_version=_DASHBOARD_CACHE_VERSION,
        source_version=_DASHBOARD_SOURCE_VERSION,
        rule_version=_DASHBOARD_RULE_VERSION,
        quality_flag="ok",
        result_payload=body.model_dump(mode="json"),
        tables_used=[FACT_TABLE, TYW_FACT],
        evidence_rows=len(b_top) + len(a_top) + len(l_top),
    )


def _triple_balances(
    repo: DashboardRepository, rd: str | None
) -> tuple[Decimal, Decimal, Decimal] | None:
    if rd is None:
        return None
    bt, _, _ = repo.fetch_bond_core_metrics(rd)
    at, _, _ = repo.fetch_tyw_core_metrics(rd, asset_side=True)
    lt, _, _ = repo.fetch_tyw_core_metrics(rd, asset_side=False)
    return bt, at, lt


def _null_yuan_changes() -> tuple[Numeric, Numeric, Numeric, Numeric]:
    z = null_numeric(unit="yuan", precision=8, sign_aware=True)
    return z, z, z, z


def get_daily_changes(report_date: str | None = None) -> dict[str, object]:
    repo = _repo()
    canonical = sorted(repo.list_merged_report_dates())
    canonical_desc = sorted(canonical, reverse=True)
    anchor = _dashboard_anchor(report_date, canonical_desc)
    trace = _trace_id()

    if anchor is None:
        payload = DailyChangesPayload(report_date="", periods=[]).model_dump(mode="json")
        return build_result_envelope(
            basis="analytical",
            trace_id=trace,
            result_kind="dashboard.daily_changes",
            cache_version=_DASHBOARD_CACHE_VERSION,
            source_version=_DASHBOARD_SOURCE_VERSION,
            rule_version=_DASHBOARD_RULE_VERSION,
            quality_flag="warning",
            result_payload=payload,
            tables_used=[FACT_TABLE, TYW_FACT],
            evidence_rows=0,
        )

    zs_b, zs_a, zs_l, zs_n = _null_yuan_changes()
    periods_out: list[DailyChangePeriod] = []
    for label in ("day", "week", "month"):
        base_rd = (
            _prior_for_period(canonical_desc, anchor, label)
            if anchor in canonical_desc
            else None
        )
        cur_triple = _triple_balances(repo, anchor)
        base_triple = _triple_balances(repo, base_rd) if base_rd else None

        if cur_triple is None or base_triple is None or base_rd is None:
            periods_out.append(
                DailyChangePeriod(
                    period=label,
                    bond_investments_change=zs_b,
                    interbank_assets_change=zs_a,
                    interbank_liabilities_change=zs_l,
                    net_change=zs_n,
                )
            )
            continue

        bn, an, ln = cur_triple
        bp, ap, lp = base_triple
        bd = bn - bp
        ad = an - ap
        ld = ln - lp
        net_d = bd + ad + ld
        periods_out.append(
            DailyChangePeriod(
                period=label,
                bond_investments_change=_yuan_numeric(bd, sign_aware=True),
                interbank_assets_change=_yuan_numeric(ad, sign_aware=True),
                interbank_liabilities_change=_yuan_numeric(ld, sign_aware=True),
                net_change=_yuan_numeric(net_d, sign_aware=True),
            )
        )

    payload = DailyChangesPayload(report_date=anchor, periods=periods_out).model_dump(mode="json")
    return build_result_envelope(
        basis="analytical",
        trace_id=trace,
        result_kind="dashboard.daily_changes",
        cache_version=_DASHBOARD_CACHE_VERSION,
        source_version=_DASHBOARD_SOURCE_VERSION,
        rule_version=_DASHBOARD_RULE_VERSION,
        quality_flag="ok",
        result_payload=payload,
        tables_used=[FACT_TABLE, TYW_FACT],
        evidence_rows=len(periods_out),
    )
