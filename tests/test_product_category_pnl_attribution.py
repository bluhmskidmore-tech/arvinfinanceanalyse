from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module

ZERO = Decimal("0")
DAYS_IN_YEAR = Decimal("365")


def test_product_category_attribution_endpoint_closes_scale_rate_day_ftp(tmp_path, monkeypatch) -> None:
    client, duckdb_path = _build_client(tmp_path, monkeypatch)
    _create_read_model(duckdb_path)
    _insert_interest_row_pair(duckdb_path)

    response = client.get(
        "/ui/pnl/product-category/attribution",
        params={"report_date": "2026-02-28", "compare": "mom"},
    )

    assert response.status_code == 200
    envelope = response.json()
    assert envelope["result_meta"]["basis"] == "formal"
    assert envelope["result_meta"]["scenario_flag"] is False
    assert envelope["result_meta"]["result_kind"] == "product_category_pnl.attribution"
    payload = envelope["result"]
    assert payload["state"] == "complete"
    assert payload["current_report_date"] == "2026-02-28"
    assert payload["prior_report_date"] == "2026-01-31"

    row = next(item for item in payload["rows"] if item["category_id"] == "interbank_lending_assets")
    effects = row["effects"]
    expected = _expected_net_effects(
        prior_report_date=date(2026, 1, 31),
        current_report_date=date(2026, 2, 28),
        prior_scale=Decimal("100"),
        current_scale=Decimal("110"),
        prior_cash_rate=Decimal("0.05"),
        current_cash_rate=Decimal("0.06"),
        prior_ftp_rate=Decimal("0.0175"),
        current_ftp_rate=Decimal("0.0160"),
    )
    assert Decimal(str(effects["scale_effect"])) == pytest.approx(expected["scale_effect"])
    assert Decimal(str(effects["rate_effect"])) == pytest.approx(expected["rate_effect"])
    assert Decimal(str(effects["day_effect"])) == pytest.approx(expected["day_effect"])
    assert Decimal(str(effects["ftp_effect"])) == pytest.approx(expected["ftp_effect"])
    assert Decimal(str(effects["direct_effect"])) == ZERO
    assert abs(Decimal(str(effects["closure_error"]))) < Decimal("0.000001")
    assert Decimal(str(payload["totals"]["asset_total"]["effects"]["delta_business_net_income"])) == pytest.approx(
        Decimal(str(effects["delta_business_net_income"]))
    )


def test_product_category_attribution_endpoint_reports_missing_prior_month_as_incomplete(
    tmp_path,
    monkeypatch,
) -> None:
    client, duckdb_path = _build_client(tmp_path, monkeypatch)
    _create_read_model(duckdb_path)
    _insert_row_set(
        duckdb_path,
        report_date="2026-02-28",
        scale=Decimal("110"),
        cash_rate=Decimal("0.06"),
        ftp_rate=Decimal("0.0160"),
        baseline_ftp_rate_pct=Decimal("1.60"),
        source_version="sv_current_only",
    )

    response = client.get(
        "/ui/pnl/product-category/attribution",
        params={"report_date": "2026-02-28", "compare": "mom"},
    )

    assert response.status_code == 200
    envelope = response.json()
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result"]["state"] == "incomplete"
    assert envelope["result"]["reason"] == "no_prior_month"
    assert envelope["result"]["rows"] == []
    assert envelope["result"]["totals"] is None
    assert envelope["result"]["prior_report_date"] == "2026-01-31"


def test_product_category_attribution_endpoint_supports_yoy_compare(tmp_path, monkeypatch) -> None:
    client, duckdb_path = _build_client(tmp_path, monkeypatch)
    _create_read_model(duckdb_path)
    _insert_row_set(
        duckdb_path,
        report_date="2025-02-28",
        scale=Decimal("90"),
        cash_rate=Decimal("0.045"),
        ftp_rate=Decimal("0.0175"),
        baseline_ftp_rate_pct=Decimal("1.75"),
        source_version="sv_yoy_prior",
    )
    _insert_row_set(
        duckdb_path,
        report_date="2026-02-28",
        scale=Decimal("110"),
        cash_rate=Decimal("0.06"),
        ftp_rate=Decimal("0.0160"),
        baseline_ftp_rate_pct=Decimal("1.60"),
        source_version="sv_yoy_current",
    )

    response = client.get(
        "/ui/pnl/product-category/attribution",
        params={"report_date": "2026-02-28", "compare": "yoy"},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["compare"] == "yoy"
    assert payload["state"] == "complete"
    assert payload["current_report_date"] == "2026-02-28"
    assert payload["prior_report_date"] == "2025-02-28"
    row = next(item for item in payload["rows"] if item["category_id"] == "interbank_lending_assets")
    expected = _expected_net_effects(
        prior_report_date=date(2025, 2, 28),
        current_report_date=date(2026, 2, 28),
        prior_scale=Decimal("90"),
        current_scale=Decimal("110"),
        prior_cash_rate=Decimal("0.045"),
        current_cash_rate=Decimal("0.06"),
        prior_ftp_rate=Decimal("0.0175"),
        current_ftp_rate=Decimal("0.0160"),
    )
    assert Decimal(str(row["effects"]["scale_effect"])) == pytest.approx(expected["scale_effect"])
    assert Decimal(str(row["effects"]["rate_effect"])) == pytest.approx(expected["rate_effect"])
    assert abs(Decimal(str(row["effects"]["closure_error"]))) < Decimal("0.000001")


def test_product_category_attribution_yoy_totals_include_direct_child_effects(
    tmp_path,
    monkeypatch,
) -> None:
    client, duckdb_path = _build_client(tmp_path, monkeypatch)
    _create_read_model(duckdb_path)
    _insert_direct_child_under_non_direct_total_pair(duckdb_path)

    response = client.get(
        "/ui/pnl/product-category/attribution",
        params={"report_date": "2026-02-28", "compare": "yoy"},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    asset_effects = payload["totals"]["asset_total"]["effects"]
    grand_effects = payload["totals"]["grand_total"]["effects"]
    assert Decimal(str(asset_effects["delta_business_net_income"])) == Decimal("2")
    assert Decimal(str(asset_effects["direct_effect"])) == Decimal("2")
    assert Decimal(str(grand_effects["delta_business_net_income"])) == Decimal("2")
    assert Decimal(str(grand_effects["direct_effect"])) == Decimal("2")
    assert abs(Decimal(str(grand_effects["closure_error"]))) < Decimal("0.000001")


def test_product_category_attribution_endpoint_reports_missing_yoy_prior_as_incomplete(
    tmp_path,
    monkeypatch,
) -> None:
    client, duckdb_path = _build_client(tmp_path, monkeypatch)
    _create_read_model(duckdb_path)
    _insert_row_set(
        duckdb_path,
        report_date="2026-02-28",
        scale=Decimal("110"),
        cash_rate=Decimal("0.06"),
        ftp_rate=Decimal("0.0160"),
        baseline_ftp_rate_pct=Decimal("1.60"),
        source_version="sv_current_only",
    )

    response = client.get(
        "/ui/pnl/product-category/attribution",
        params={"report_date": "2026-02-28", "compare": "yoy"},
    )

    assert response.status_code == 200
    envelope = response.json()
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result"]["state"] == "incomplete"
    assert envelope["result"]["reason"] == "no_prior_year_same_month"
    assert envelope["result"]["prior_report_date"] == "2025-02-28"


def test_product_category_attribution_totals_do_not_double_count_parent_and_child_rows(
    tmp_path,
    monkeypatch,
) -> None:
    client, duckdb_path = _build_client(tmp_path, monkeypatch)
    _create_read_model(duckdb_path)
    _insert_direct_hierarchy_pair(duckdb_path)

    response = client.get(
        "/ui/pnl/product-category/attribution",
        params={"report_date": "2026-02-28", "compare": "mom"},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert len(payload["rows"]) == 2
    assert Decimal(str(payload["totals"]["asset_total"]["effects"]["delta_business_net_income"])) == Decimal("2")
    assert Decimal(str(payload["totals"]["asset_total"]["effects"]["direct_effect"])) == Decimal("2")
    assert Decimal(str(payload["totals"]["grand_total"]["effects"]["delta_business_net_income"])) == Decimal("2")
    assert Decimal(str(payload["totals"]["grand_total"]["effects"]["direct_effect"])) == Decimal("2")


def test_product_category_attribution_endpoint_rejects_unknown_compare(tmp_path, monkeypatch) -> None:
    client, _ = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/pnl/product-category/attribution",
        params={"report_date": "2026-02-28", "compare": "bad"},
    )

    assert response.status_code == 422
    assert "Unsupported product-category attribution compare='bad'" in response.json()["detail"]


def _build_client(tmp_path: Path, monkeypatch) -> tuple[TestClient, Path]:
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(tmp_path / "data_input"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    main_module = load_module("backend.app.main", "backend/app/main.py")
    return TestClient(main_module.app), duckdb_path


def _create_read_model(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table product_category_pnl_formal_read_model (
              report_date varchar,
              view varchar,
              sort_order integer,
              category_id varchar,
              category_name varchar,
              side varchar,
              level integer,
              baseline_ftp_rate_pct decimal(12, 6),
              cnx_scale decimal(24, 8),
              cny_scale decimal(24, 8),
              foreign_scale decimal(24, 8),
              cnx_cash decimal(24, 8),
              cny_cash decimal(24, 8),
              foreign_cash decimal(24, 8),
              cny_ftp decimal(24, 8),
              foreign_ftp decimal(24, 8),
              cny_net decimal(24, 8),
              foreign_net decimal(24, 8),
              business_net_income decimal(24, 8),
              weighted_yield decimal(24, 8),
              is_total boolean,
              children_json varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
    finally:
        conn.close()


def _insert_interest_row_pair(duckdb_path: Path) -> None:
    _insert_row_set(
        duckdb_path,
        report_date="2026-01-31",
        scale=Decimal("100"),
        cash_rate=Decimal("0.05"),
        ftp_rate=Decimal("0.0175"),
        baseline_ftp_rate_pct=Decimal("1.75"),
        source_version="sv_prior",
    )
    _insert_row_set(
        duckdb_path,
        report_date="2026-02-28",
        scale=Decimal("110"),
        cash_rate=Decimal("0.06"),
        ftp_rate=Decimal("0.0160"),
        baseline_ftp_rate_pct=Decimal("1.60"),
        source_version="sv_current",
    )


def _insert_row_set(
    duckdb_path: Path,
    *,
    report_date: str,
    scale: Decimal,
    cash_rate: Decimal,
    ftp_rate: Decimal,
    baseline_ftp_rate_pct: Decimal,
    source_version: str,
) -> None:
    report_dt = date.fromisoformat(report_date)
    days = Decimal(monthrange(report_dt.year, report_dt.month)[1])
    cash = scale * cash_rate * days / DAYS_IN_YEAR
    ftp = scale * ftp_rate * days / DAYS_IN_YEAR
    net = cash - ftp
    row_values = [
        _row(
            report_date=report_date,
            sort_order=1,
            category_id="interbank_lending_assets",
            category_name="拆放同业",
            side="asset",
            scale=scale,
            cash=cash,
            ftp=ftp,
            net=net,
            weighted_yield=cash_rate * Decimal("100"),
            baseline_ftp_rate_pct=baseline_ftp_rate_pct,
            is_total=False,
            source_version=source_version,
        ),
        _row(
            report_date=report_date,
            sort_order=2,
            category_id="asset_total",
            category_name="资产端合计",
            side="asset",
            scale=scale,
            cash=cash,
            ftp=ftp,
            net=net,
            weighted_yield=cash_rate * Decimal("100"),
            baseline_ftp_rate_pct=baseline_ftp_rate_pct,
            is_total=True,
            source_version=source_version,
        ),
        _row(
            report_date=report_date,
            sort_order=3,
            category_id="liability_total",
            category_name="负债端合计",
            side="liability",
            scale=ZERO,
            cash=ZERO,
            ftp=ZERO,
            net=ZERO,
            weighted_yield=None,
            baseline_ftp_rate_pct=baseline_ftp_rate_pct,
            is_total=True,
            source_version=source_version,
        ),
        _row(
            report_date=report_date,
            sort_order=4,
            category_id="grand_total",
            category_name="grand_total",
            side="all",
            scale=ZERO,
            cash=cash,
            ftp=ftp,
            net=net,
            weighted_yield=None,
            baseline_ftp_rate_pct=baseline_ftp_rate_pct,
            is_total=True,
            source_version=source_version,
        ),
    ]

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.executemany(
            """
            insert into product_category_pnl_formal_read_model (
              report_date,
              view,
              sort_order,
              category_id,
              category_name,
              side,
              level,
              baseline_ftp_rate_pct,
              cnx_scale,
              cny_scale,
              foreign_scale,
              cnx_cash,
              cny_cash,
              foreign_cash,
              cny_ftp,
              foreign_ftp,
              cny_net,
              foreign_net,
              business_net_income,
              weighted_yield,
              is_total,
              children_json,
              source_version,
              rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_values,
        )
    finally:
        conn.close()


def _insert_direct_hierarchy_pair(duckdb_path: Path) -> None:
    for report_date, net in (("2026-01-31", Decimal("10")), ("2026-02-28", Decimal("12"))):
        rows = [
            _row(
                report_date=report_date,
                sort_order=1,
                category_id="bond_investment",
                category_name="债券投资",
                side="asset",
                scale=ZERO,
                cash=net,
                ftp=ZERO,
                net=net,
                weighted_yield=None,
                baseline_ftp_rate_pct=Decimal("1.75"),
                is_total=False,
                source_version=f"sv_{report_date}",
                children_json='["bond_tpl"]',
            ),
            _row(
                report_date=report_date,
                sort_order=2,
                category_id="bond_tpl",
                category_name="TPL",
                side="asset",
                scale=ZERO,
                cash=net,
                ftp=ZERO,
                net=net,
                weighted_yield=None,
                baseline_ftp_rate_pct=Decimal("1.75"),
                is_total=False,
                source_version=f"sv_{report_date}",
            ),
            _row(
                report_date=report_date,
                sort_order=3,
                category_id="asset_total",
                category_name="资产端合计",
                side="asset",
                scale=ZERO,
                cash=net,
                ftp=ZERO,
                net=net,
                weighted_yield=None,
                baseline_ftp_rate_pct=Decimal("1.75"),
                is_total=True,
                source_version=f"sv_{report_date}",
            ),
            _row(
                report_date=report_date,
                sort_order=4,
                category_id="liability_total",
                category_name="负债端合计",
                side="liability",
                scale=ZERO,
                cash=ZERO,
                ftp=ZERO,
                net=ZERO,
                weighted_yield=None,
                baseline_ftp_rate_pct=Decimal("1.75"),
                is_total=True,
                source_version=f"sv_{report_date}",
            ),
            _row(
                report_date=report_date,
                sort_order=5,
                category_id="grand_total",
                category_name="grand_total",
                side="all",
                scale=ZERO,
                cash=net,
                ftp=ZERO,
                net=net,
                weighted_yield=None,
                baseline_ftp_rate_pct=Decimal("1.75"),
                is_total=True,
                source_version=f"sv_{report_date}",
            ),
        ]
        conn = duckdb.connect(str(duckdb_path), read_only=False)
        try:
            conn.executemany(
                """
                insert into product_category_pnl_formal_read_model (
                  report_date,
                  view,
                  sort_order,
                  category_id,
                  category_name,
                  side,
                  level,
                  baseline_ftp_rate_pct,
                  cnx_scale,
                  cny_scale,
                  foreign_scale,
                  cnx_cash,
                  cny_cash,
                  foreign_cash,
                  cny_ftp,
                  foreign_ftp,
                  cny_net,
                  foreign_net,
                  business_net_income,
                  weighted_yield,
                  is_total,
                  children_json,
                  source_version,
                  rule_version
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        finally:
            conn.close()


def _insert_direct_child_under_non_direct_total_pair(duckdb_path: Path) -> None:
    for report_date, direct_net in (("2025-02-28", Decimal("1")), ("2026-02-28", Decimal("3"))):
        source_version = f"sv_{report_date}"
        rows = [
            _row(
                report_date=report_date,
                sort_order=1,
                category_id="interbank_lending_assets",
                category_name="interest row",
                side="asset",
                scale=Decimal("100"),
                cash=Decimal("5"),
                ftp=Decimal("2"),
                net=Decimal("3"),
                weighted_yield=Decimal("5"),
                baseline_ftp_rate_pct=Decimal("2"),
                is_total=False,
                source_version=source_version,
            ),
            _row(
                report_date=report_date,
                sort_order=2,
                category_id="valuation_spread",
                category_name="direct row",
                side="asset",
                scale=ZERO,
                cash=direct_net,
                ftp=ZERO,
                net=direct_net,
                weighted_yield=None,
                baseline_ftp_rate_pct=Decimal("2"),
                is_total=False,
                source_version=source_version,
            ),
            _row(
                report_date=report_date,
                sort_order=3,
                category_id="asset_total",
                category_name="asset total",
                side="asset",
                scale=Decimal("100"),
                cash=Decimal("5") + direct_net,
                ftp=Decimal("2"),
                net=Decimal("3") + direct_net,
                weighted_yield=Decimal("5"),
                baseline_ftp_rate_pct=Decimal("2"),
                is_total=True,
                source_version=source_version,
            ),
            _row(
                report_date=report_date,
                sort_order=4,
                category_id="liability_total",
                category_name="璐熷€虹鍚堣",
                side="liability",
                scale=ZERO,
                cash=ZERO,
                ftp=ZERO,
                net=ZERO,
                weighted_yield=None,
                baseline_ftp_rate_pct=Decimal("2"),
                is_total=True,
                source_version=source_version,
            ),
            _row(
                report_date=report_date,
                sort_order=5,
                category_id="grand_total",
                category_name="grand_total",
                side="all",
                scale=Decimal("100"),
                cash=Decimal("5") + direct_net,
                ftp=Decimal("2"),
                net=Decimal("3") + direct_net,
                weighted_yield=Decimal("5"),
                baseline_ftp_rate_pct=Decimal("2"),
                is_total=True,
                source_version=source_version,
            ),
        ]
        conn = duckdb.connect(str(duckdb_path), read_only=False)
        try:
            conn.executemany(
                """
                insert into product_category_pnl_formal_read_model (
                  report_date,
                  view,
                  sort_order,
                  category_id,
                  category_name,
                  side,
                  level,
                  baseline_ftp_rate_pct,
                  cnx_scale,
                  cny_scale,
                  foreign_scale,
                  cnx_cash,
                  cny_cash,
                  foreign_cash,
                  cny_ftp,
                  foreign_ftp,
                  cny_net,
                  foreign_net,
                  business_net_income,
                  weighted_yield,
                  is_total,
                  children_json,
                  source_version,
                  rule_version
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        finally:
            conn.close()


def _row(
    *,
    report_date: str,
    sort_order: int,
    category_id: str,
    category_name: str,
    side: str,
    scale: Decimal,
    cash: Decimal,
    ftp: Decimal,
    net: Decimal,
    weighted_yield: Decimal | None,
    baseline_ftp_rate_pct: Decimal,
    is_total: bool,
    source_version: str,
    children_json: str = "[]",
) -> tuple[object, ...]:
    return (
        report_date,
        "monthly",
        sort_order,
        category_id,
        category_name,
        side,
        0,
        baseline_ftp_rate_pct,
        scale,
        scale,
        ZERO,
        cash,
        cash,
        ZERO,
        ftp,
        ZERO,
        net,
        ZERO,
        net,
        weighted_yield,
        is_total,
        children_json,
        source_version,
        "rv_product_category_pnl_v1",
    )


def _expected_net_effects(
    *,
    prior_report_date: date,
    current_report_date: date,
    prior_scale: Decimal,
    current_scale: Decimal,
    prior_cash_rate: Decimal,
    current_cash_rate: Decimal,
    prior_ftp_rate: Decimal,
    current_ftp_rate: Decimal,
) -> dict[str, Decimal]:
    prior_days = Decimal(monthrange(prior_report_date.year, prior_report_date.month)[1])
    current_days = Decimal(monthrange(current_report_date.year, current_report_date.month)[1])
    cash_scale = (current_scale - prior_scale) * prior_cash_rate * prior_days / DAYS_IN_YEAR
    cash_rate = current_scale * (current_cash_rate - prior_cash_rate) * prior_days / DAYS_IN_YEAR
    cash_day = current_scale * current_cash_rate * (current_days - prior_days) / DAYS_IN_YEAR
    ftp_scale = (current_scale - prior_scale) * prior_ftp_rate * prior_days / DAYS_IN_YEAR
    ftp_rate = current_scale * (current_ftp_rate - prior_ftp_rate) * prior_days / DAYS_IN_YEAR
    ftp_day = current_scale * current_ftp_rate * (current_days - prior_days) / DAYS_IN_YEAR
    return {
        "scale_effect": cash_scale - ftp_scale,
        "rate_effect": cash_rate,
        "day_effect": cash_day - ftp_day,
        "ftp_effect": -ftp_rate,
    }
