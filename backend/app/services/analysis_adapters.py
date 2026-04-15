from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.bond_analytics.common import resolve_period
from backend.app.repositories.product_category_pnl_repo import ProductCategoryPnlRepository
from backend.app.schemas.analysis_service import (
    AnalysisQuery,
    AnalysisResultEnvelope,
    AnalysisResultPayload,
    AnalysisWarning,
    AttributionSlice,
    DrillTarget,
)
from backend.app.schemas.product_category_pnl import ProductCategoryPnlRow
from backend.app.services.formal_result_runtime import (
    build_formal_result_meta,
    build_scenario_result_meta,
)


PRODUCT_CATEGORY_AVAILABLE_VIEWS = [
    "monthly",
    "qtd",
    "ytd",
    "year_to_report_month_end",
]


class ProductCategoryPnlAnalysisAdapter:
    """Product-category PnL: persisted formal read model + optional in-memory FTP scenario overlay."""

    analysis_key = "product_category_pnl"

    def __init__(self, duckdb_path: str):
        self._repo = ProductCategoryPnlRepository(duckdb_path)

    def execute(self, query: AnalysisQuery) -> AnalysisResultEnvelope:
        if query.basis not in {"formal", "scenario"}:
            raise ValueError(
                f"Unsupported basis={query.basis} for analysis_key={self.analysis_key}"
            )
        if query.scenario_rate_pct is not None and query.basis != "scenario":
            raise ValueError(
                "scenario_rate_pct is only allowed when basis is 'scenario' "
                f"(got basis={query.basis!r} for analysis_key={self.analysis_key})"
            )
        view = query.view or "monthly"
        # Single storage path: formal read model. basis=="scenario" applies core_finance.apply_scenario_to_rows on top.
        rows = self._repo.fetch_rows(query.report_date, view)
        if not rows:
            raise ValueError(
                f"No product-category read model rows for report_date={query.report_date} view={view}"
            )

        typed_rows = [_to_product_category_row(row) for row in rows]
        if query.basis == "scenario" and query.scenario_rate_pct is not None:
            from backend.app.core_finance.product_category_pnl import apply_scenario_to_rows

            typed_rows = [
                _to_product_category_row(item)
                for item in apply_scenario_to_rows(
                    [row.model_dump(mode="python") for row in typed_rows],
                    Decimal(str(query.scenario_rate_pct)),
                )
            ]

        asset_total = next(row for row in typed_rows if row.category_id == "asset_total")
        liability_total = next(row for row in typed_rows if row.category_id == "liability_total")
        grand_total = next(row for row in typed_rows if row.category_id == "grand_total")

        result_kind = (
            "analysis.product_category_pnl"
            if query.consumer == "analysis_service"
            else "product_category_pnl.detail"
        )
        result_meta = (
            build_scenario_result_meta(
                trace_id=f"tr_{query.consumer}_{query.report_date}_{view}",
                result_kind=result_kind,
                source_version=str(rows[0]["source_version"]),
                rule_version=str(rows[0]["rule_version"]),
                cache_version="cv_product_category_pnl_v1",
                quality_flag="ok",
            )
            if query.basis == "scenario"
            else build_formal_result_meta(
                trace_id=f"tr_{query.consumer}_{query.report_date}_{view}",
                result_kind=result_kind,
                source_version=str(rows[0]["source_version"]),
                rule_version=str(rows[0]["rule_version"]),
                cache_version="cv_product_category_pnl_v1",
                quality_flag="ok",
            )
        )
        return AnalysisResultEnvelope(
            result_meta=result_meta,
            result=AnalysisResultPayload(
                report_date=query.report_date,
                analysis_key=self.analysis_key,
                basis=query.basis,
                view=view,
                scenario_rate_pct=query.scenario_rate_pct,
                summary={
                    "available_views": PRODUCT_CATEGORY_AVAILABLE_VIEWS,
                    "asset_total": asset_total.model_dump(mode="json"),
                    "liability_total": liability_total.model_dump(mode="json"),
                    "grand_total": grand_total.model_dump(mode="json"),
                },
                rows=[row.model_dump(mode="json") for row in typed_rows],
                attribution=_build_product_category_attribution(typed_rows, grand_total),
            ),
        )


BOND_ACTION_ATTRIBUTION_KEY = "bond_action_attribution"
BOND_ACTION_ATTRIBUTION_PLACEHOLDER_WARNING = (
    "Trade-level action data not yet available; returning placeholder attribution until trade records are integrated."
)


def build_bond_action_attribution_placeholder_envelope(query: AnalysisQuery) -> AnalysisResultEnvelope:
    """Empty trade-level action attribution until DuckDB trade facts exist.

    Intentionally not registered on :class:`UnifiedAnalysisService` — bond analytics
    calls this directly so the unified bus only lists landed adapters.
    """
    if query.analysis_key != BOND_ACTION_ATTRIBUTION_KEY:
        raise ValueError(
            f"Unexpected analysis_key={query.analysis_key!r} for bond action placeholder"
        )
    if query.basis != "formal":
        raise ValueError(
            f"Unsupported basis={query.basis} for analysis_key={BOND_ACTION_ATTRIBUTION_KEY}"
        )
    report_date = date.fromisoformat(query.report_date)
    period_type = query.view or "MoM"
    period_start, period_end = resolve_period(report_date, period_type)
    warnings = [
        AnalysisWarning(
            code="bond_action_placeholder",
            level="warning",
            message=BOND_ACTION_ATTRIBUTION_PLACEHOLDER_WARNING,
        )
    ]
    result_kind = (
        "analysis.bond_action_attribution"
        if query.consumer == "analysis_service"
        else "bond_analytics.action_attribution"
    )
    return AnalysisResultEnvelope(
        result_meta=build_formal_result_meta(
            trace_id=f"tr_{query.consumer}_{query.report_date}_{period_type}",
            result_kind=result_kind,
            source_version="sv_bond_analytics_v1",
            rule_version="rv_bond_analytics_v1",
            cache_version="cv_none",
            quality_flag="warning",
        ),
        result=AnalysisResultPayload(
            report_date=query.report_date,
            analysis_key=BOND_ACTION_ATTRIBUTION_KEY,
            basis=query.basis,
            view=period_type,
            summary={
                "period_type": period_type,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "total_actions": 0,
                "total_pnl_from_actions": "0",
                "period_start_duration": "0",
                "period_end_duration": "0",
                "duration_change_from_actions": "0",
                "period_start_dv01": "0",
                "period_end_dv01": "0",
                "computed_at": query.report_date,
            },
            facets={
                "by_action_type": [],
                "action_details": [],
            },
            warnings=warnings,
        ),
    )


def _to_product_category_row(row: dict[str, object]) -> ProductCategoryPnlRow:
    return ProductCategoryPnlRow(
        category_id=str(row["category_id"]),
        category_name=str(row["category_name"]),
        side=str(row["side"]),
        level=int(row["level"]),
        view=str(row["view"]),
        report_date=str(row["report_date"]),
        baseline_ftp_rate_pct=Decimal(str(row["baseline_ftp_rate_pct"])),
        cnx_scale=Decimal(str(row["cnx_scale"])),
        cny_scale=Decimal(str(row["cny_scale"])),
        foreign_scale=Decimal(str(row["foreign_scale"])),
        cnx_cash=Decimal(str(row["cnx_cash"])),
        cny_cash=Decimal(str(row["cny_cash"])),
        foreign_cash=Decimal(str(row["foreign_cash"])),
        cny_ftp=Decimal(str(row["cny_ftp"])),
        foreign_ftp=Decimal(str(row["foreign_ftp"])),
        cny_net=Decimal(str(row["cny_net"])),
        foreign_net=Decimal(str(row["foreign_net"])),
        business_net_income=Decimal(str(row["business_net_income"])),
        weighted_yield=None if row["weighted_yield"] is None else Decimal(str(row["weighted_yield"])),
        is_total=bool(row["is_total"]),
        children=list(row.get("children", [])),
        scenario_rate_pct=None if row.get("scenario_rate_pct") is None else Decimal(str(row["scenario_rate_pct"])),
    )


def _build_product_category_attribution(
    typed_rows: list[ProductCategoryPnlRow],
    grand_total: ProductCategoryPnlRow,
) -> list[AttributionSlice]:
    denominator = abs(grand_total.business_net_income)
    slices: list[AttributionSlice] = []
    for row in typed_rows:
        if row.is_total or row.level != 1:
            continue
        share = Decimal("0")
        if denominator != 0:
            share = (row.business_net_income.copy_abs() / denominator) * Decimal("100")
        tone = "neutral"
        if row.business_net_income > 0:
            tone = "positive"
        elif row.business_net_income < 0:
            tone = "negative"
        slices.append(
            AttributionSlice(
                slice_id=row.category_id,
                label=row.category_name,
                dimension="product_category",
                value=str(row.business_net_income),
                share_pct=f"{share.quantize(Decimal('0.01'))}",
                tone=tone,
                drill_targets=[
                    DrillTarget(
                        target_kind="category",
                        target_id=row.category_id,
                        label=row.category_name,
                    )
                ],
            )
        )
    return slices
