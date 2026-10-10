from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import cast

from backend.app.config.product_category_mapping import build_product_category_config_for_report_date
from backend.app.core_finance.product_category_pnl import (
    calculate_product_category_interest_spread_metrics,
    calculate_product_category_liability_cost_decomposition,
    calculate_read_model,
)
from backend.app.repositories.product_category_pnl_repo import (
    ProductCategoryPnlRepository,
)
from backend.app.schemas.product_category_pnl import (
    ProductCategoryInterestSpreadPayload,
    ProductCategoryLiabilityCostDecompositionPayload,
    ProductCategoryPnlPayload,
    ProductCategoryPnlRow,
)

PRODUCT_CATEGORY_AVAILABLE_VIEWS = ["monthly", "qtd", "ytd", "year_to_report_month_end"]


def product_category_pnl_payload_from_canonical_ytd_anchor(
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    ftp_rate_pct: float,
) -> ProductCategoryPnlPayload | None:
    """Rebuild missing YTD rows through read-only repositories and the formal calculator."""
    try:
        anchor = date.fromisoformat(report_date)
    except ValueError:
        return None
    if report_date != anchor.isoformat():
        return None

    fallback_rate = Decimal(str(ftp_rate_pct))
    facts_by = ProductCategoryPnlRepository(duckdb_path).fetch_canonical_ytd_facts(anchor)
    if facts_by is None or anchor not in facts_by:
        return None
    # Materialization persists canonical facts after applying approved adjustments.
    # Applying current events here would double DELTA and mix newer edits into an
    # older snapshot. governance_dir remains part of the compatibility interface.

    try:
        config = build_product_category_config_for_report_date(anchor, fallback_rate)
        calc_out = calculate_read_model(facts_by, anchor, "ytd", config)
    except (KeyError, ValueError, TypeError, ArithmeticError):
        return None

    raw_rows = cast(list[dict[str, object]], calc_out["rows"])
    typed_rows = [ProductCategoryPnlRow.model_validate(row) for row in raw_rows]
    interest_earning_assets = next(row for row in typed_rows if row.category_id == "interest_earning_assets")
    credit_linked_notes = next(
        (row for row in typed_rows if row.category_id == "credit_linked_notes"),
        None,
    )
    asset_total = ProductCategoryPnlRow.model_validate(calc_out["asset_total"])
    liability_total = ProductCategoryPnlRow.model_validate(calc_out["liability_total"])
    grand_total = ProductCategoryPnlRow.model_validate(calc_out["grand_total"])
    interest_spread = calculate_product_category_interest_spread_metrics(
        report_date=report_date,
        view="ytd",
        asset_row=asset_total.model_dump(mode="python"),
        liability_row=liability_total.model_dump(mode="python"),
    )
    interest_earning_spread = calculate_product_category_interest_spread_metrics(
        report_date=report_date,
        view="ytd",
        asset_row=interest_earning_assets.model_dump(mode="python"),
        liability_row=liability_total.model_dump(mode="python"),
    )
    liability_cost_decomposition = calculate_product_category_liability_cost_decomposition(
        report_date=report_date,
        view="ytd",
        liability_row=liability_total.model_dump(mode="python"),
        credit_linked_notes_row=(
            None if credit_linked_notes is None else credit_linked_notes.model_dump(mode="python")
        ),
    )
    return ProductCategoryPnlPayload(
        report_date=report_date,
        view="ytd",
        available_views=list(PRODUCT_CATEGORY_AVAILABLE_VIEWS),
        scenario_rate_pct=None,
        rows=typed_rows,
        asset_total=asset_total,
        liability_total=liability_total,
        grand_total=grand_total,
        interest_spread=ProductCategoryInterestSpreadPayload.model_validate(asdict(interest_spread)),
        interest_earning_spread=ProductCategoryInterestSpreadPayload.model_validate(asdict(interest_earning_spread)),
        liability_cost_decomposition=ProductCategoryLiabilityCostDecompositionPayload.model_validate(
            asdict(liability_cost_decomposition)
        ),
    )
