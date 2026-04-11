from __future__ import annotations

from decimal import Decimal

import duckdb

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import ROOT, load_module


def _seed_workbook_snapshot_and_fx_tables(duckdb_path: str) -> None:
    snapshot_mod = load_module(
        "backend.app.repositories.snapshot_repo",
        "backend/app/repositories/snapshot_repo.py",
    )

    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        snapshot_mod.ensure_snapshot_tables(conn)
        conn.execute(
            """
            create table if not exists fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "240001.IB",
                "政策行债A",
                "组合A",
                "CC100",
                "可供出售债券",
                "可供出售类资产",
                "政策性金融债",
                "发行人A",
                "公共管理、社会保障和社会组织",
                "AAA",
                "CNY",
                Decimal("100"),
                Decimal("102"),
                Decimal("99"),
                Decimal("1"),
                Decimal("2.5"),
                Decimal("2.4"),
                "2027-12-31",
                None,
                0,
                False,
                "固定",
                "sv-z-1",
                "rv-snap-1",
                "ib-z-1",
                "trace-z-1",
            ],
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "J11603010202",
                "美元应收投资款项",
                "组合B",
                "CC200",
                "银行账户",
                "应收投资款项",
                "其他",
                "发行人B",
                "未分类",
                None,
                "USD",
                Decimal("50"),
                Decimal("50"),
                Decimal("50"),
                Decimal("0"),
                Decimal("0.0"),
                Decimal("0.0"),
                "2026-06-30",
                None,
                0,
                False,
                "固定",
                "sv-z-1",
                "rv-snap-1",
                "ib-z-1",
                "trace-z-2",
            ],
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "NCD-ISSUE-1",
                "发行类同业存单",
                "负债组合",
                "CC300",
                "发行类债劵",
                "发行类债劵",
                "同业存单",
                "发行人C",
                "金融业",
                None,
                "CNY",
                Decimal("80"),
                Decimal("80"),
                Decimal("80"),
                Decimal("0.2"),
                Decimal("1.8"),
                Decimal("1.8"),
                "2026-03-31",
                None,
                0,
                True,
                "固定",
                "sv-z-1",
                "rv-snap-1",
                "ib-z-1",
                "trace-z-3",
            ],
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "asset-1",
                "拆放同业",
                "asset",
                "城商行A",
                "投融资类",
                "一般",
                "城市商业银行",
                "CNY",
                Decimal("30"),
                Decimal("0.3"),
                Decimal("2.0"),
                "2026-01-31",
                None,
                "sv-t-1",
                "rv-snap-1",
                "ib-t-1",
                "trace-t-1",
            ],
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "liability-1",
                "同业存放",
                "liability",
                "股份行B",
                "清算类",
                "托管账户",
                "股份制银行",
                "CNY",
                Decimal("40"),
                Decimal("0.2"),
                Decimal("1.5"),
                "2026-01-15",
                None,
                "sv-t-1",
                "rv-snap-1",
                "ib-t-1",
                "trace-t-2",
            ],
        )
        conn.execute(
            """
            insert into fx_daily_mid values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "USD",
                "CNY",
                Decimal("7.2"),
                "CFETS",
                True,
                False,
                "sv-fx-1",
            ],
        )
    finally:
        conn.close()


def test_real_zqtz_parse_marks_asset_class_issue_rows_as_issuance_like():
    parse_mod = load_module(
        "backend.app.repositories.snapshot_row_parse",
        "backend/app/repositories/snapshot_row_parse.py",
    )
    source_file = "ZQTZSHOW-20260228.xls"
    rows = parse_mod.parse_zqtz_snapshot_rows_from_bytes(
        file_bytes=(ROOT / "data_input" / source_file).read_bytes(),
        ingest_batch_id="ib-real-zqtz",
        source_version="sv-real-zqtz",
        source_file=source_file,
        rule_version="rv-real-zqtz",
    )
    issue_rows = [row for row in rows if str(row.get("asset_class") or "") == "发行类债劵"]
    assert issue_rows
    assert all(bool(row["is_issuance_like"]) for row in issue_rows[:10])


def test_real_tyw_parse_marks_tongye_cunfang_as_liability():
    parse_mod = load_module(
        "backend.app.repositories.snapshot_row_parse",
        "backend/app/repositories/snapshot_row_parse.py",
    )
    source_file = "TYWLSHOW-20260228.xls"
    rows = parse_mod.parse_tyw_snapshot_rows_from_bytes(
        file_bytes=(ROOT / "data_input" / source_file).read_bytes(),
        ingest_batch_id="ib-real-tyw",
        source_version="sv-real-tyw",
        source_file=source_file,
        rule_version="rv-real-tyw",
    )
    cunfang_rows = [row for row in rows if str(row.get("product_type") or "") == "同业存放"]
    assert cunfang_rows
    assert all(str(row["position_side"]) == "liability" for row in cunfang_rows[:10])


def test_balance_analysis_workbook_api_returns_governed_sections(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_workbook_snapshot_and_fx_tables(str(duckdb_path))

    task_mod = load_module(
        "backend.app.tasks.balance_analysis_materialize",
        "backend/app/tasks/balance_analysis_materialize.py",
    )
    task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/ui/balance-analysis/workbook",
        params={"report_date": "2025-12-31", "position_scope": "all", "currency_basis": "CNY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "balance-analysis.workbook"
    assert payload["result"]["report_date"] == "2025-12-31"
    assert payload["result"]["position_scope"] == "all"
    assert payload["result"]["currency_basis"] == "CNY"

    card_keys = {card["key"] for card in payload["result"]["cards"]}
    assert {
        "bond_assets_excluding_issue",
        "interbank_assets",
        "interbank_liabilities",
        "issuance_liabilities",
        "net_position",
    } <= card_keys
    card_map = {card["key"]: card for card in payload["result"]["cards"]}
    assert Decimal(card_map["issuance_liabilities"]["value"]) > Decimal("0")
    assert Decimal(card_map["bond_assets_excluding_issue"]["value"]) == Decimal("0.015")

    table_keys = {table["key"] for table in payload["result"]["tables"]}
    assert {
        "bond_business_types",
        "maturity_gap",
        "issuance_business_types",
        "currency_split",
        "rating_analysis",
        "rate_distribution",
        "industry_distribution",
        "counterparty_types",
        "campisi_breakdown",
        "cross_analysis",
        "interest_modes",
    } <= table_keys
    table_map = {table["key"]: table for table in payload["result"]["tables"]}
    issuance_rows = table_map["issuance_business_types"]["rows"]
    assert any(row["bond_type"] == "同业存单" for row in issuance_rows)
    counterparty_rows = table_map["counterparty_types"]["rows"]
    liability_row = next(row for row in counterparty_rows if row["counterparty_type"] == "股份制银行")
    assert liability_row["liability_count"] == 1
    bond_rows = table_map["bond_business_types"]["rows"]
    policy_row = next(row for row in bond_rows if row["bond_type"] == "政策性金融债")
    assert Decimal(policy_row["balance_amount"]) < Decimal("1")
    other_row = next(row for row in bond_rows if row["bond_type"] == "其他")
    assert Decimal(other_row["balance_amount"]) == Decimal("0.005")

    get_settings.cache_clear()
