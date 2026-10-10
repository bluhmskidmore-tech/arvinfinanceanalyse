from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from backend.app.core_finance.config.product_category_contract import PRODUCT_CATEGORY_RULE_VERSION
from backend.app.services.product_category_pnl_service import product_category_pnl_envelope
from tests.test_product_category_pnl_attribution import (
    _build_client,
    _create_read_model,
    _insert_row_set,
)


def _seed_current_rule_rows(duckdb_path, prior_date: str | None) -> None:
    _create_read_model(duckdb_path)
    dates = [("2026-02-28", Decimal("73000"), Decimal("0.06"))]
    if prior_date is not None:
        dates.append((prior_date, Decimal("36500"), Decimal("0.05")))
    for report_date, scale, cash_rate in dates:
        _insert_row_set(
            duckdb_path,
            report_date=report_date,
            scale=scale,
            cash_rate=cash_rate,
            ftp_rate=Decimal("0.02"),
            baseline_ftp_rate_pct=Decimal("2.00"),
            source_version=f"sv_{report_date}",
        )
    with duckdb.connect(str(duckdb_path)) as conn:
        conn.execute(
            "UPDATE product_category_pnl_formal_read_model SET rule_version = ?",
            [PRODUCT_CATEGORY_RULE_VERSION],
        )
        conn.execute(
            """INSERT INTO product_category_pnl_formal_read_model
            SELECT * REPLACE (
                'interest_earning_assets' AS category_id,
                5 AS sort_order,
                false AS is_total
            ) FROM product_category_pnl_formal_read_model WHERE category_id = 'asset_total'"""
        )


@pytest.mark.parametrize(
    ("compare", "prior_date", "expected_prior_net"),
    [("mom", "2026-01-31", Decimal("105.40")), ("yoy", "2025-02-28", Decimal("91.00"))],
)
def test_attribution_uses_each_report_year_ftp_and_ties_to_detail(
    tmp_path, monkeypatch, compare, prior_date, expected_prior_net
) -> None:
    client, duckdb_path = _build_client(tmp_path, monkeypatch)
    _seed_current_rule_rows(duckdb_path, prior_date)
    response = client.get(
        "/ui/pnl/product-category/attribution",
        params={"report_date": "2026-02-28", "compare": compare},
    )
    assert response.status_code == 200
    envelope = response.json()
    total = envelope["result"]["totals"]["grand_total"]
    # Independently: 73000 * (6% - 1.6%) * 28 / 365 = 246.40 yuan.
    assert Decimal(total["current"]["business_net_income"]) == Decimal("246.40")
    assert Decimal(total["prior"]["business_net_income"]) == expected_prior_net
    assert Decimal(total["effects"]["delta_business_net_income"]) == Decimal("246.40") - expected_prior_net
    for key, report_date in [("current", "2026-02-28"), ("prior", prior_date)]:
        detail = product_category_pnl_envelope(str(duckdb_path), report_date, "monthly")
        assert Decimal(total[key]["business_net_income"]) == Decimal(
            detail["result"]["grand_total"]["business_net_income"]
        )
    assert envelope["result_meta"]["rule_version"] == PRODUCT_CATEGORY_RULE_VERSION
    assert envelope["result_meta"]["quality_flag"] == "ok"
    # A read must never rewrite the persisted baseline.
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        assert conn.execute(
            "SELECT DISTINCT baseline_ftp_rate_pct FROM product_category_pnl_formal_read_model"
        ).fetchall() == [(Decimal("2.00"),)]


@pytest.mark.parametrize("stale_date", ["2026-02-28", "2026-01-31"])
@pytest.mark.parametrize("stale_rule", ["rv_product_category_pnl_v1", ""])
def test_attribution_rejects_any_outdated_period_rule(tmp_path, monkeypatch, stale_date, stale_rule) -> None:
    client, duckdb_path = _build_client(tmp_path, monkeypatch)
    _seed_current_rule_rows(duckdb_path, "2026-01-31")
    with duckdb.connect(str(duckdb_path)) as conn:
        conn.execute(
            """UPDATE product_category_pnl_formal_read_model SET rule_version = ?
            WHERE report_date = ? AND category_id = 'interbank_lending_assets'""",
            [stale_rule, stale_date],
        )
    response = client.get(
        "/ui/pnl/product-category/attribution",
        params={"report_date": "2026-02-28", "compare": "mom"},
    )
    assert response.status_code == 503
    assert "result" not in response.json()


def test_attribution_rejects_old_current_rule_even_without_prior_month(tmp_path, monkeypatch) -> None:
    client, duckdb_path = _build_client(tmp_path, monkeypatch)
    _seed_current_rule_rows(duckdb_path, None)
    with duckdb.connect(str(duckdb_path)) as conn:
        conn.execute(
            "UPDATE product_category_pnl_formal_read_model SET rule_version = 'rv_product_category_pnl_v1'"
        )
    response = client.get(
        "/ui/pnl/product-category/attribution",
        params={"report_date": "2026-02-28", "compare": "mom"},
    )
    assert response.status_code == 503
