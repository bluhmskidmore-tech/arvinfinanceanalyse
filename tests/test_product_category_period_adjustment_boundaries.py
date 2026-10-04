from __future__ import annotations

import importlib
from calendar import monthrange
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core_finance.config.product_category_contract import PRODUCT_CATEGORY_RULE_VERSION
from backend.app.core_finance.config.product_category_mapping import build_default_product_category_config
from backend.app.core_finance.product_category_pnl import (
    CanonicalFactRow,
    apply_manual_adjustments,
    calculate_read_model,
)
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.schemas.product_category_pnl import ProductCategoryManualAdjustmentUpdateRequest
from backend.app.services import analysis_adapters
from backend.app.services import product_category_pnl_service as service
from backend.app.tasks import product_category_pnl as task


def _append_adjustment(
    repo: GovernanceRepository,
    *,
    report_date: str,
    created_at: str,
    status: str = "approved",
    adjustment_id: str | None = "adj-moved",
    amount: str = "10",
) -> None:
    record = {
        "event_type": "edited",
        "created_at": created_at,
        "report_date": report_date,
        "operator": "DELTA",
        "approval_status": status,
        "account_code": "50204000001",
        "currency": "CNX",
        "monthly_pnl": amount,
    }
    if adjustment_id is not None:
        record["adjustment_id"] = adjustment_id
    repo.append(task.PRODUCT_CATEGORY_ADJUSTMENT_STREAM, record)


def _facts(report_date: date, *, scale: str = "36500") -> list[CanonicalFactRow]:
    return [
        CanonicalFactRow(
            report_date=report_date,
            account_code=code,
            currency=currency,
            account_name="test account",
            beginning_balance=Decimal("0"),
            ending_balance=Decimal("0"),
            monthly_pnl=Decimal(cash),
            daily_avg_balance=Decimal(average),
            annual_avg_balance=Decimal(average),
            days_in_period=monthrange(report_date.year, report_date.month)[1],
        )
        for currency in ("CNX", "CNY")
        for code, cash, average in (("120", "0", scale), ("50204000001", "100", "0"))
    ]


@pytest.mark.parametrize("latest_status,expected_cash", [("approved", "210"), ("rejected", "200")])
def test_historical_adjustment_move_does_not_survive_in_old_month(
    tmp_path: Path, latest_status: str, expected_cash: str,
) -> None:
    repo = GovernanceRepository(base_dir=tmp_path)
    # Append out of order: version selection must use event time across all months.
    _append_adjustment(
        repo, report_date="2026-02-28", created_at="2026-03-02T00:00:00Z", status=latest_status,
    )
    _append_adjustment(repo, report_date="2026-01-31", created_at="2026-03-01T00:00:00Z")

    january, february = date(2026, 1, 31), date(2026, 2, 28)
    facts_by_date = {
        day: apply_manual_adjustments(_facts(day, scale="0"), task._load_manual_adjustments(tmp_path, day))
        for day in (january, february)
    }
    model = calculate_read_model(
        facts_by_date, february, "ytd", build_default_product_category_config(Decimal("1.6")),
    )

    assert task._load_manual_adjustments(tmp_path, january) == []
    assert model["grand_total"]["cnx_cash"] == Decimal(expected_cash)
    assert model["grand_total"]["business_net_income"] == Decimal(expected_cash)


def test_adjustment_month_filter_preserves_independent_legacy_records(tmp_path: Path) -> None:
    repo = GovernanceRepository(base_dir=tmp_path)
    _append_adjustment(repo, report_date="2026-01-31", created_at="", adjustment_id=None, amount="3")
    _append_adjustment(repo, report_date="2026-01-31", created_at="", adjustment_id=None, amount="4")
    _append_adjustment(repo, report_date="2026-02-28", created_at="", adjustment_id=None, amount="9")

    adjustments = task._load_manual_adjustments(tmp_path, date(2026, 1, 31))

    assert [item.monthly_pnl for item in adjustments] == [Decimal("3"), Decimal("4")]


@pytest.mark.parametrize("new_date", ["2026-02-28", "2025-12-31"])
def test_adjustment_edit_rejects_report_date_change_without_appending(
    tmp_path: Path, new_date: str,
) -> None:
    repo = GovernanceRepository(base_dir=tmp_path)
    _append_adjustment(repo, report_date="2026-01-31", created_at="2026-02-01T00:00:00Z")
    before = repo.read_all(task.PRODUCT_CATEGORY_ADJUSTMENT_STREAM)
    request = ProductCategoryManualAdjustmentUpdateRequest(
        report_date=new_date, account_code="50204000001", currency="CNX", monthly_pnl=Decimal("20"),
    )

    with pytest.raises(ValueError, match="report_date"):
        service.update_product_category_manual_adjustment(
            SimpleNamespace(governance_path=tmp_path), "adj-moved", request,
        )

    assert repo.read_all(task.PRODUCT_CATEGORY_ADJUSTMENT_STREAM) == before


def test_adjustment_edit_keeps_same_month_editable(tmp_path: Path) -> None:
    repo = GovernanceRepository(base_dir=tmp_path)
    _append_adjustment(repo, report_date="2026-01-31", created_at="2026-02-01T00:00:00Z")
    request = ProductCategoryManualAdjustmentUpdateRequest(
        report_date="2026-01-31", account_code="50204000001", currency="CNX", monthly_pnl=Decimal("20"),
    )

    updated = service.update_product_category_manual_adjustment(
        SimpleNamespace(governance_path=tmp_path), "adj-moved", request,
    )

    assert updated["monthly_pnl"] == "20"
    assert updated["report_date"] == "2026-01-31"
    assert len(repo.read_all(task.PRODUCT_CATEGORY_ADJUSTMENT_STREAM)) == 2


@pytest.mark.parametrize("adjustment_id,report_date,expected_status", [
    ("adj-moved", "2026-02-28", 422),
    ("missing-id", "2026-01-31", 404),
])
def test_adjustment_edit_api_rejects_invalid_change_without_new_events(
    tmp_path: Path, monkeypatch, adjustment_id: str, report_date: str, expected_status: int,
) -> None:
    route = importlib.import_module("backend.app.api.routes.product_category_pnl")
    repo = GovernanceRepository(base_dir=tmp_path)
    _append_adjustment(repo, report_date="2026-01-31", created_at="2026-02-01T00:00:00Z")
    before = repo.read_all(task.PRODUCT_CATEGORY_ADJUSTMENT_STREAM)
    monkeypatch.setattr(route, "get_settings", lambda: SimpleNamespace(governance_path=tmp_path))
    monkeypatch.setattr(route, "ensure_user_allowed", lambda **kwargs: None)
    app = FastAPI()
    app.include_router(route.router)

    response = TestClient(app).post(
        f"/ui/pnl/product-category/manual-adjustments/{adjustment_id}/edit",
        json={
            "report_date": report_date, "account_code": "50204000001",
            "currency": "CNX", "monthly_pnl": "20",
        },
    )

    assert response.status_code == expected_status
    assert repo.read_all(task.PRODUCT_CATEGORY_ADJUSTMENT_STREAM) == before
    if expected_status == 422:
        assert "report_date" in response.json()["detail"]


@pytest.mark.parametrize("view", ["qtd", "ytd", "year_to_report_month_end"])
def test_incomplete_period_warns_without_fabricating_missing_month_values(monkeypatch, view: str) -> None:
    report_date = date(2026, 8, 31)
    model = calculate_read_model(
        {report_date: _facts(report_date)}, report_date, view,
        build_default_product_category_config(Decimal("1.6")),
    )
    rows = [
        {**row, "source_version": "sv_partial_period_test", "rule_version": PRODUCT_CATEGORY_RULE_VERSION}
        for row in model["rows"]
    ]

    class ReadRepository:
        def __init__(self, path):
            pass

        def fetch_rows(self, requested_date, requested_view):
            assert requested_date == report_date.isoformat()
            assert requested_view == view
            return rows

        def list_report_dates(self):
            return [report_date.isoformat()]

    monkeypatch.setattr(service, "ProductCategoryPnlRepository", ReadRepository)
    monkeypatch.setattr(analysis_adapters, "ProductCategoryPnlRepository", ReadRepository)

    envelope = service.product_category_pnl_envelope("unused", report_date.isoformat(), view)
    row = next(item for item in envelope["result"]["rows"] if item["category_id"] == "interbank_lending_assets")

    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert Decimal(row["cnx_cash"]) == Decimal("100")
    assert Decimal(row["cny_ftp"]) == Decimal("49.6")
    assert Decimal(row["business_net_income"]) == Decimal("50.4")
    if view == "qtd":
        assert Decimal(row["cnx_scale"]) == Decimal("18250")


@pytest.mark.parametrize("report_date,available,view,expected", [
    ("2026-08-31", ["2026-07-31", "2026-08-31"], "qtd", False),
    ("2026-09-30", ["2026-07-31", "2026-09-30"], "qtd", True),
    ("2026-07-31", ["2026-07-31"], "qtd", False),
    ("2026-01-31", ["2026-01-31"], "qtd", False),
    ("2026-08-31", ["2026-08-31"], "monthly", False),
    ("2026-08-31", ["2026-07-31", "2026-08-31"], "ytd", True),
])
def test_period_coverage_uses_the_requested_period_start(report_date, available, view, expected) -> None:
    assert service._is_partial_ytd_view(report_dates=available, report_date=report_date, view=view) is expected
