"""Schedulable orchestration for macro-toolkit price/commodity freshness.

Keeps the observation cards (CTA / DCC / risk parity / crisis inputs) readable by
refreshing, in a single-writer sequence:

1. commodity futures + Nanhua index daily bars
2. public cross-asset headlines (CSI300/500, copper CA.*, DR007, …)
3. CFFEX member-rank for the latest weekday (soft-fail on weekends / vendor gaps)

Does not change formal-use policy; observation cards remain non-formal.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Sequence

from backend.app.governance.settings import get_settings
from backend.app.services.cffex_member_rank_service import materialize_cffex_member_rank
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.choice_macro import refresh_public_cross_asset_headlines
from backend.app.tasks.commodity_daily_ingest import run_commodity_daily_ingest

logger = logging.getLogger(__name__)

DEFAULT_COMMODITY_LOOKBACK_DAYS = 14
DEFAULT_PUBLIC_HEADLINE_LOOKBACK_DAYS = 120
SOURCE_VERSION = "macro_toolkit_freshness_refresh_v1"

# Core legs for CTA/DCC/RP observation cards plus common toolkit commodities.
DEFAULT_COMMODITY_PRODUCTS: tuple[str, ...] = (
    "CU",
    "AL",
    "AU",
    "SC",
    "NHCI",
    "NHII",
    "RB",
    "HC",
    "I",
    "JM",
    "J",
    "ZN",
    "TA",
    "MA",
    "M",
    "P",
    "AG",
    "TS",
    "TF",
    "T",
    "TL",
)


def _new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"macro-toolkit-freshness-{stamp}-{uuid.uuid4().hex[:8]}"


def _latest_weekday_on_or_before(day: date) -> date:
    cursor = day
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


def refresh_macro_toolkit_freshness(
    *,
    dry_run: bool = False,
    today: date | None = None,
    duckdb_path: str | Path | None = None,
    commodity_lookback_days: int = DEFAULT_COMMODITY_LOOKBACK_DAYS,
    public_headline_lookback_days: int = DEFAULT_PUBLIC_HEADLINE_LOOKBACK_DAYS,
    commodity_products: Sequence[str] | None = None,
    include_cffex: bool = True,
) -> dict[str, object]:
    """Run the freshness pipeline synchronously (or plan it in dry-run)."""
    settings = get_settings()
    report_date = today or date.today()
    resolved_duckdb = str(Path(duckdb_path or settings.duckdb_path))
    products = tuple(commodity_products) if commodity_products is not None else DEFAULT_COMMODITY_PRODUCTS
    start_date = (report_date - timedelta(days=max(commodity_lookback_days, 1))).isoformat()
    end_date = report_date.isoformat()
    run_id = _new_run_id()
    steps: list[dict[str, object]] = []

    if dry_run:
        commodity_plan = run_commodity_daily_ingest(
            start_date=start_date,
            end_date=end_date,
            duckdb_path=resolved_duckdb,
            products=products,
            dry_run=True,
        )
        steps.append(
            {
                "step": "commodity_daily_ingest",
                "status": "dry_run",
                "result": commodity_plan,
            }
        )
        steps.append(
            {
                "step": "public_cross_asset_headlines",
                "status": "dry_run",
                "lookback_days": public_headline_lookback_days,
                "report_date": end_date,
            }
        )
        if include_cffex:
            steps.append(
                {
                    "step": "cffex_member_rank",
                    "status": "dry_run",
                    "trade_date": _latest_weekday_on_or_before(report_date).isoformat(),
                }
            )
        return {
            "status": "dry_run",
            "run_id": run_id,
            "source_version": SOURCE_VERSION,
            "report_date": end_date,
            "duckdb_path": resolved_duckdb,
            "steps": steps,
        }

    commodity_result = run_commodity_daily_ingest(
        start_date=start_date,
        end_date=end_date,
        duckdb_path=resolved_duckdb,
        products=products,
        dry_run=False,
    )
    commodity_status = str(commodity_result.get("status") or "unknown")
    steps.append(
        {
            "step": "commodity_daily_ingest",
            "status": "success" if commodity_status in {"completed", "success"} else commodity_status,
            "result": {
                "status": commodity_result.get("status"),
                "row_count": commodity_result.get("row_count"),
                "product_count": commodity_result.get("product_count"),
                "start_date": commodity_result.get("start_date"),
                "end_date": commodity_result.get("end_date"),
            },
        }
    )

    headlines_result = refresh_public_cross_asset_headlines(
        duckdb_path=resolved_duckdb,
        lookback_days=public_headline_lookback_days,
        report_date=end_date,
    )
    headlines_status = str(headlines_result.get("status") or "unknown")
    steps.append(
        {
            "step": "public_cross_asset_headlines",
            "status": "success" if headlines_status in {"completed", "success"} else headlines_status,
            "result": {
                "status": headlines_result.get("status"),
                "row_count": headlines_result.get("row_count"),
                "series_count": headlines_result.get("series_count"),
                "run_id": headlines_result.get("run_id"),
                "warnings": headlines_result.get("warnings") or [],
            },
        }
    )

    if include_cffex:
        cffex_trade_date = _latest_weekday_on_or_before(report_date)
        try:
            cffex_result = materialize_cffex_member_rank(
                trade_date=cffex_trade_date.isoformat(),
                duckdb_path=resolved_duckdb,
                sources=("tushare",),
            )
            steps.append(
                {
                    "step": "cffex_member_rank",
                    "status": "success",
                    "trade_date": cffex_trade_date.isoformat(),
                    "result": {
                        "row_count": cffex_result.get("row_count")
                        if isinstance(cffex_result, dict)
                        else None,
                        "payload_keys": sorted(cffex_result.keys())
                        if isinstance(cffex_result, dict)
                        else [],
                    },
                }
            )
        except Exception as exc:  # noqa: BLE001 - keep pipeline resilient on weekend/vendor gaps
            logger.warning(
                "macro toolkit freshness: cffex step soft-failed trade_date=%s err=%s",
                cffex_trade_date.isoformat(),
                exc,
            )
            steps.append(
                {
                    "step": "cffex_member_rank",
                    "status": "soft_failed",
                    "trade_date": cffex_trade_date.isoformat(),
                    "reason": str(exc),
                }
            )

    hard_failures = [
        step for step in steps if step["step"] != "cffex_member_rank" and step["status"] not in {"success"}
    ]
    status = "success" if not hard_failures else "failed"
    return {
        "status": status,
        "run_id": run_id,
        "source_version": SOURCE_VERSION,
        "report_date": end_date,
        "duckdb_path": resolved_duckdb,
        "steps": steps,
    }


refresh_macro_toolkit_freshness_actor = register_actor_once(
    "refresh_macro_toolkit_freshness",
    refresh_macro_toolkit_freshness,
    time_limit_ms=3_600_000,
)
