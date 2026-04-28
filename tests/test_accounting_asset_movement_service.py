from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import duckdb

from backend.app.governance.settings import Settings
from backend.app.repositories.accounting_asset_movement_repo import (
    AccountingAssetMovementRepository,
)
import backend.app.services.accounting_asset_movement_service as movement_service
from backend.app.services.accounting_asset_movement_service import (
    accounting_asset_movement_dates_envelope,
    accounting_asset_movement_envelope,
)
from backend.app.tasks.accounting_asset_movement import (
    materialize_accounting_asset_movement_on_connection,
)


def test_refresh_rematerializes_stale_zqtz_formal_window_before_movement(
    monkeypatch,
):
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date varchar,
              report_month varchar,
              currency_basis varchar,
              sort_order integer,
              basis_bucket varchar,
              previous_balance decimal(24, 8),
              current_balance decimal(24, 8),
              balance_change decimal(24, 8),
              change_pct decimal(24, 8),
              contribution_pct decimal(24, 8),
              zqtz_amount decimal(24, 8),
              gl_amount decimal(24, 8),
              reconciliation_diff decimal(24, 8),
              reconciliation_status varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        for report_date, report_month in [
            ("2026-02-28", "2026-02"),
            ("2026-01-31", "2026-01"),
            ("2025-12-31", "2025-12"),
        ]:
            for sort_order, bucket in enumerate(["AC", "OCI", "TPL"], start=1):
                conn.execute(
                    """
                    insert into fact_accounting_asset_movement_monthly values (
                      ?, ?, 'CNX', ?, ?, 0, 1, 1, 0, 0, 1, 1, 0, 'matched', 'sv-old', 'rv-old'
                    )
                    """,
                    [report_date, report_month, sort_order, bucket],
                )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              currency_basis varchar,
              position_scope varchar,
              business_type_primary varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_zqtz_balance_daily values (?, 'CNY', 'asset', ?)",
            [
                ("2026-02-28", "fresh-policy-bond"),
                ("2026-01-31", ""),
                ("2026-01-31", None),
                ("2025-12-31", "fresh-local-bond"),
            ],
        )
    finally:
        conn.close()

    formal_dates: list[str] = []
    formal_fx_paths: list[str | None] = []
    movement_dates: list[str] = []

    def fake_formal_pipeline(**kwargs):
        formal_dates.append(str(kwargs["report_date"]))
        formal_fx_paths.append(kwargs.get("fx_source_path"))
        return {"status": "completed", "report_date": kwargs["report_date"]}

    def fake_movement_window(*, duckdb_path, report_dates, currency_basis):
        del duckdb_path
        movement_dates.extend(report_dates)
        return {
            report_date: {
                "status": "completed",
                "cache_key": "accounting_asset_movement.monthly",
                "report_date": report_date,
                "currency_basis": currency_basis,
                "row_count": 3,
                "source_version": "sv-new",
                "rule_version": "rv_accounting_asset_movement_v2",
            }
            for report_date in report_dates
        }

    monkeypatch.setattr(
        movement_service.run_formal_balance_pipeline,
        "fn",
        fake_formal_pipeline,
    )
    monkeypatch.setattr(
        movement_service,
        "_refresh_missing_product_category_dates",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        movement_service,
        "_materialize_accounting_asset_movement_window",
        fake_movement_window,
    )

    fx_csv_path = duckdb_path.parent / "data_input" / "fx" / "fx_daily_mid.csv"
    fx_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fx_csv_path.write_text(
        "trade_date,base_currency,quote_currency,mid_rate,source_name,is_business_day,is_carry_forward\n"
        "2026-01-31,USD,CNY,7.1,CFETS,true,false\n",
        encoding="utf-8",
    )

    settings = Settings(
        duckdb_path=str(duckdb_path),
        governance_path=duckdb_path.parent / "governance",
        data_input_root=duckdb_path.parent / "data_input",
        local_archive_path=duckdb_path.parent / "archive",
    )

    payload = movement_service.refresh_accounting_asset_movement(
        settings,
        report_date="2026-02-28",
        currency_basis="CNX",
    )

    assert formal_dates == ["2025-12-31", "2026-01-31", "2026-02-28"]
    assert formal_fx_paths == [
        str(fx_csv_path.resolve()),
        str(fx_csv_path.resolve()),
        str(fx_csv_path.resolve()),
    ]
    assert movement_dates == ["2025-12-31", "2026-01-31", "2026-02-28"]
    assert payload["report_date"] == "2026-02-28"
    assert payload["product_category_refreshed_dates"] == []
    assert payload["formal_balance_refreshed_dates"] == [
        "2025-12-31",
        "2026-01-31",
        "2026-02-28",
    ]
    assert payload["movement_refreshed_dates"] == [
        "2025-12-31",
        "2026-01-31",
        "2026-02-28",
    ]


def test_refresh_materializes_missing_product_category_before_movement(monkeypatch):
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date varchar,
              report_month varchar,
              currency_basis varchar,
              sort_order integer,
              basis_bucket varchar,
              previous_balance decimal(24, 8),
              current_balance decimal(24, 8),
              balance_change decimal(24, 8),
              change_pct decimal(24, 8),
              contribution_pct decimal(24, 8),
              zqtz_amount decimal(24, 8),
              gl_amount decimal(24, 8),
              reconciliation_diff decimal(24, 8),
              reconciliation_status varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        for report_date, report_month in [
            ("2026-02-28", "2026-02"),
            ("2026-01-31", "2026-01"),
        ]:
            for sort_order, bucket in enumerate(["AC", "OCI", "TPL"], start=1):
                conn.execute(
                    """
                    insert into fact_accounting_asset_movement_monthly values (
                      ?, ?, 'CNX', ?, ?, 0, 1, 1, 0, 0, 1, 1, 0, 'matched', 'sv-old', 'rv-old'
                    )
                    """,
                    [report_date, report_month, sort_order, bucket],
                )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              currency_basis varchar,
              position_scope varchar,
              business_type_primary varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_zqtz_balance_daily values (?, 'CNY', 'asset', 'fresh')",
            [("2026-02-28",), ("2026-01-31",)],
        )
    finally:
        conn.close()

    data_input_root = duckdb_path.parent / "data_input"
    source_dir = data_input_root / "pnl_总账对账-日均"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "总账对账202601.xlsx").write_bytes(b"placeholder")
    (source_dir / "总账对账202602.xlsx").write_bytes(b"placeholder")

    product_category_calls: list[dict[str, object]] = []
    formal_dates: list[str] = []
    movement_dates: list[str] = []
    missing_product_category_dates = [
        ["2026-01-31", "2026-02-28"],
        [],
    ]

    def fake_product_category_refresh(**kwargs):
        product_category_calls.append(kwargs)
        return {"status": "completed"}

    def fake_formal_pipeline(**kwargs):
        formal_dates.append(str(kwargs["report_date"]))
        return {"status": "completed", "report_date": kwargs["report_date"]}

    def fake_movement_window(*, duckdb_path, report_dates, currency_basis):
        del duckdb_path
        movement_dates.extend(report_dates)
        return {
            report_date: {
                "status": "completed",
                "cache_key": "accounting_asset_movement.monthly",
                "report_date": report_date,
                "currency_basis": currency_basis,
                "row_count": 3,
                "source_version": "sv-new",
                "rule_version": "rv_accounting_asset_movement_v2",
            }
            for report_date in report_dates
        }

    monkeypatch.setattr(
        movement_service.materialize_product_category_pnl,
        "fn",
        fake_product_category_refresh,
    )
    monkeypatch.setattr(
        movement_service.run_formal_balance_pipeline,
        "fn",
        fake_formal_pipeline,
    )
    monkeypatch.setattr(
        movement_service,
        "_missing_product_category_control_dates",
        lambda *args, **kwargs: missing_product_category_dates.pop(0),
    )
    monkeypatch.setattr(
        movement_service,
        "_materialize_accounting_asset_movement_window",
        fake_movement_window,
    )

    settings = Settings(
        duckdb_path=str(duckdb_path),
        governance_path=duckdb_path.parent / "governance",
        data_input_root=data_input_root,
        local_archive_path=duckdb_path.parent / "archive",
    )

    payload = movement_service.refresh_accounting_asset_movement(
        settings,
        report_date="2026-02-28",
        currency_basis="CNX",
    )

    assert len(product_category_calls) == 1
    assert product_category_calls[0]["source_dir"] == str(source_dir.resolve())
    assert formal_dates == ["2026-01-31", "2026-02-28"]
    assert movement_dates == ["2026-01-31", "2026-02-28"]
    assert payload["product_category_refreshed_dates"] == [
        "2026-01-31",
        "2026-02-28",
    ]
    assert payload["formal_balance_refreshed_dates"] == [
        "2026-01-31",
        "2026-02-28",
    ]
    assert payload["movement_refreshed_dates"] == [
        "2026-01-31",
        "2026-02-28",
    ]


def test_refresh_zqtz_source_detection_requires_every_report_date():
    data_root = Path("test_output") / "accounting_asset_movement" / uuid4().hex
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "ZQTZSHOW-20250930.xls").write_bytes(b"placeholder")

    assert not movement_service._has_zqtz_sources_for_dates(
        data_root,
        ["2025-09-30", "2025-10-31"],
    )

    (data_root / "ZQTZSHOW-2025.10.31.xls").write_bytes(b"placeholder")

    assert movement_service._has_zqtz_sources_for_dates(
        data_root,
        ["2025-09-30", "2025-10-31"],
    )


def test_balance_movement_analysis_service_exposes_gl_control_rows():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    refresh_rows = _seed_source_tables_and_materialize(duckdb_path)
    assert len(refresh_rows) == 3

    envelope = accounting_asset_movement_envelope(
        str(duckdb_path),
        report_date="2026-02-28",
        currency_basis="CNX",
    )
    result = envelope["result"]

    assert result["accounting_controls"] == ["141%", "142%", "143%", "1440101%"]
    assert result["excluded_controls"] == ["144020%"]
    assert Decimal(result["summary"]["current_balance_total"]) == Decimal("415.00000000")
    by_bucket = {row["basis_bucket"]: row for row in result["rows"]}
    assert Decimal(by_bucket["AC"]["current_balance"]) == Decimal("225.00000000")
    assert Decimal(by_bucket["AC"]["current_balance_pct"]).quantize(
        Decimal("0.000001")
    ) == Decimal("54.216867")
    assert Decimal(by_bucket["OCI"]["current_balance"]) == Decimal("80.00000000")
    assert Decimal(by_bucket["TPL"]["current_balance"]) == Decimal("110.00000000")
    assert result["summary"]["matched_bucket_count"] == 3
    business_month = result["business_trend_months"][0]
    assert business_month["report_date"] == "2026-02-28"
    business_rows = {row["row_key"]: row for row in business_month["rows"]}
    assert Decimal(business_rows["asset_interbank_lending"]["current_balance"]) == Decimal("80.00000000")
    assert Decimal(business_rows["asset_reverse_repo"]["current_balance"]) == Decimal("90.00000000")
    assert Decimal(business_rows["asset_interbank_current_deposit"]["current_balance"]) == Decimal("35.00000000")
    assert Decimal(business_rows["asset_domestic_interbank_term_deposit"]["current_balance"]) == Decimal("45.00000000")
    assert Decimal(business_rows["asset_overseas_interbank_term_deposit"]["current_balance"]) == Decimal("25.00000000")
    assert Decimal(business_rows["asset_zqtz_interbank_cd"]["current_balance"]) == Decimal("18.00000000")
    assert business_rows["asset_zqtz_interbank_cd"]["source_kind"] == "zqtz"
    assert Decimal(business_rows["liability_interbank_deposits"]["current_balance"]) == Decimal("-90.00000000")
    assert Decimal(business_rows["liability_interbank_borrowings"]["current_balance"]) == Decimal("-35.00000000")
    assert Decimal(business_rows["liability_repo"]["current_balance"]) == Decimal("-95.00000000")
    assert Decimal(business_rows["liability_interbank_cd"]["current_balance"]) == Decimal("-40.00000000")
    assert Decimal(business_month["asset_balance_total"]) == Decimal("293.00000000")
    assert Decimal(business_month["liability_balance_total"]) == Decimal("-260.00000000")
    assert [month["report_date"] for month in result["trend_months"]] == [
        "2026-02-28",
        "2026-01-31",
    ]
    assert Decimal(result["trend_months"][0]["current_balance_total"]) == Decimal(
        "415.00000000"
    )
    trend_ac = next(
        row for row in result["trend_months"][0]["rows"] if row["basis_bucket"] == "AC"
    )
    assert Decimal(trend_ac["current_balance_pct"]).quantize(
        Decimal("0.000001")
    ) == Decimal("54.216867")
    assert envelope["result_meta"]["quality_flag"] == "ok"
    assert envelope["result_meta"]["result_kind"] == "balance-analysis.movement.detail"
    assert set(envelope["result_meta"]["source_version"].split("__")) == {
        "sv-gl",
        "sv-gl-prior",
        "sv-zqtz",
        "sv-zqtz-prior",
    }
    assert set(envelope["result_meta"]["rule_version"].split("__")) == {
        "rv-gl",
        "rv-gl-prior",
        "rv-zqtz",
        "rv-zqtz-prior",
    }
    assert envelope["result_meta"]["evidence_rows"] == 64


def test_balance_movement_analysis_service_uses_cnx_diagnostic_and_ignores_cny_noise():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    _seed_source_tables_and_materialize(duckdb_path)

    envelope = accounting_asset_movement_envelope(
        str(duckdb_path),
        report_date="2026-02-28",
        currency_basis="CNX",
    )

    result = envelope["result"]
    by_bucket = {row["basis_bucket"]: row for row in result["rows"]}
    assert Decimal(by_bucket["TPL"]["current_balance"]) == Decimal("110.00000000")
    assert Decimal(by_bucket["TPL"]["zqtz_amount"]) == Decimal("110.00000000")
    assert Decimal(by_bucket["TPL"]["reconciliation_diff"]) == Decimal("0E-8")
    assert by_bucket["TPL"]["reconciliation_status"] == "matched"
    assert envelope["result_meta"]["quality_flag"] == "ok"


def test_balance_movement_analysis_service_exposes_zqtz_asset_product_rows():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date varchar,
              report_month varchar,
              currency_basis varchar,
              sort_order integer,
              basis_bucket varchar,
              previous_balance decimal(24, 8),
              current_balance decimal(24, 8),
              balance_change decimal(24, 8),
              change_pct decimal(24, 8),
              contribution_pct decimal(24, 8),
              zqtz_amount decimal(24, 8),
              gl_amount decimal(24, 8),
              reconciliation_diff decimal(24, 8),
              reconciliation_status varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_accounting_asset_movement_monthly values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                ("2026-02-28", "2026-02", "CNX", 1, "AC", "90", "100", "10", "11.11111111", "100", "100", "100", "0", "matched", "sv-read", "rv-read"),
                ("2026-02-28", "2026-02", "CNX", 2, "OCI", "0", "0", "0", "0", "0", "0", "0", "0", "matched", "sv-read", "rv-read"),
                ("2026-02-28", "2026-02", "CNX", 3, "TPL", "0", "0", "0", "0", "0", "0", "0", "0", "matched", "sv-read", "rv-read"),
            ],
        )
        conn.execute(
            """
            create table product_category_pnl_canonical_fact (
              report_date varchar,
              account_code varchar,
              currency varchar,
              account_name varchar,
              beginning_balance decimal(24, 8),
              ending_balance decimal(24, 8),
              monthly_pnl decimal(24, 8),
              daily_avg_balance decimal(24, 8),
              annual_avg_balance decimal(24, 8),
              days_in_period integer,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2026-02-28", "14501000001", "CNX", "long equity", "0", "4", "0", "0", "0", 28, "sv-gl", "rv-gl"),
        )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              bond_type varchar,
              instrument_code varchar,
              instrument_name varchar,
              currency_code varchar,
              market_value_amount decimal(24, 8),
              amortized_cost_amount decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_zqtz_balance_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-02-28", "AC", "asset", "CNY", "国债", "T1", "国债A", "CNY", "10", "9", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "凭证式国债", "T2", "凭证式国债A", "CNY", "2", "1", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "地方政府债", "L1", "地方政府债A", "CNY", "20", "19", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "政策性金融债", "P1", "政策性金融债A", "CNY", "30", "29", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "商业银行债", "B1", "商业银行债A", "CNY", "40", "39", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "次级债券", "B2", "次级债券A", "CNY", "5", "4", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "同业存单", "N1", "同业存单A", "CNY", "18", "17", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "信用债券-公用事业", "R1", "22铁道01", "CNY", "7", "6", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "信用债券-企业", "C1", "企业债A", "CNY", "50", "49", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "信用债券-公用事业", "C2", "中期票据A", "CNY", "6", "5", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "信用债券-企业", "F1", "外币企业债A", "USD", "3", "2", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "信用债券-公用事业", "US91282CNT44", "US treasury", "USD", "4", "3", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "信用债券-企业", "C3", "legacy credit one", "CNY", "13", "12", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "信用债券-公用事业", "C4", "legacy credit two", "CNY", "9", "8", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "资产支持证券", "A1", "资产支持证券A", "CNY", "7", "6", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "其他", "SA001", "公募基金A", "CNY", "8", "7", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "其他", "HK0001155867", "GTJA foreign bond", "CNY", "2", "1", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "其他", "J02205260102", "J0 市值法A", "CNY", "9", "8", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "其他", "J02503280102", "J0 市值法B", "CNY", "5", "5", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "其他", "J099990001", "J0 成本法A", "CNY", "4", "4", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "其他", "J1001", "外币委外A", "USD", "10", "10", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "其他", "J4001", "结构化融资券商A", "CNY", "11", "11", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "其他", "G0001", "结构化融资信托A", "CNY", "12", "12", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "其他", "G2001", "旧信托计划A", "CNY", "13", "13", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "其他", "JM001", "债权融资计划A", "CNY", "14", "14", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "其他", "25001", "非银行金融债A", "CNY", "15", "15", "sv-zqtz", "rv-zqtz"),
            ],
        )
    finally:
        conn.close()

    envelope = accounting_asset_movement_envelope(
        str(duckdb_path),
        report_date="2026-02-28",
        currency_basis="CNX",
    )
    business_month = envelope["result"]["business_trend_months"][0]
    business_rows = {row["row_key"]: row for row in business_month["rows"]}

    assert Decimal(business_rows["asset_zqtz_treasury_bond"]["current_balance"]) == Decimal("11.00000000")
    assert Decimal(business_rows["asset_zqtz_railway_bond"]["current_balance"]) == Decimal("7.00000000")
    assert Decimal(business_rows["asset_zqtz_commercial_financial_bond"]["current_balance"]) == Decimal("59.00000000")
    assert Decimal(business_rows["asset_zqtz_interbank_cd"]["current_balance"]) == Decimal("17.00000000")
    assert Decimal(business_rows["asset_zqtz_nonfinancial_enterprise_bond"]["current_balance"]) == Decimal("79.00000000")
    assert Decimal(business_rows["asset_zqtz_foreign_bond"]["current_balance"]) == Decimal("5.00000000")
    assert Decimal(business_rows["asset_zqtz_public_fund"]["current_balance"]) == Decimal("8.00000000")
    assert Decimal(business_rows["asset_zqtz_non_bottom_investment"]["current_balance"]) == Decimal("51.00000000")
    assert Decimal(business_rows["asset_zqtz_detail_trust_plan"]["current_balance"]) == Decimal("12.00000000")
    assert Decimal(business_rows["asset_zqtz_detail_securities_asset_management_plan"]["current_balance"]) == Decimal("39.00000000")
    assert Decimal(business_rows["asset_zqtz_detail_structured_finance_broker"]["current_balance"]) == Decimal("11.00000000")
    assert Decimal(business_rows["asset_zqtz_detail_foreign_currency_delegated"]["current_balance"]) == Decimal("10.00000000")
    assert Decimal(business_rows["asset_zqtz_detail_local_currency_delegated_market_value"]["current_balance"]) == Decimal("14.00000000")
    assert Decimal(business_rows["asset_zqtz_detail_local_currency_special_account_cost"]["current_balance"]) == Decimal("4.00000000")
    assert Decimal(business_rows["asset_zqtz_other_debt_financing"]["current_balance"]) == Decimal("14.00000000")
    assert Decimal(business_rows["asset_long_term_equity_investment"]["current_balance"]) == Decimal("4.00000000")
    assert Decimal(business_month["asset_balance_total"]) == Decimal("309.00000000")


def test_balance_movement_analysis_service_includes_accrued_interest_when_available():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date varchar,
              report_month varchar,
              currency_basis varchar,
              sort_order integer,
              basis_bucket varchar,
              previous_balance decimal(24, 8),
              current_balance decimal(24, 8),
              balance_change decimal(24, 8),
              change_pct decimal(24, 8),
              contribution_pct decimal(24, 8),
              zqtz_amount decimal(24, 8),
              gl_amount decimal(24, 8),
              reconciliation_diff decimal(24, 8),
              reconciliation_status varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_accounting_asset_movement_monthly values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                ("2026-02-28", "2026-02", "CNX", 1, "AC", "0", "0", "0", "0", "0", "0", "0", "0", "matched", "sv-read", "rv-read"),
                ("2026-02-28", "2026-02", "CNX", 2, "OCI", "0", "0", "0", "0", "0", "0", "0", "0", "matched", "sv-read", "rv-read"),
                ("2026-02-28", "2026-02", "CNX", 3, "TPL", "0", "0", "0", "0", "0", "0", "0", "0", "matched", "sv-read", "rv-read"),
            ],
        )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              bond_type varchar,
              instrument_code varchar,
              instrument_name varchar,
              currency_code varchar,
              market_value_amount decimal(24, 8),
              amortized_cost_amount decimal(24, 8),
              accrued_interest_amount decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_zqtz_balance_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-02-28", "AC", "asset", "CNY", "国债", "T1", "国债A", "CNY", "10", "9", "0.5", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "资产支持证券", "A1", "ABS A", "CNY", "7", "6", "0.25", "sv-zqtz", "rv-zqtz"),
            ],
        )
    finally:
        conn.close()

    envelope = accounting_asset_movement_envelope(
        str(duckdb_path),
        report_date="2026-02-28",
        currency_basis="CNX",
    )
    business_rows = {
        row["row_key"]: row
        for row in envelope["result"]["business_trend_months"][0]["rows"]
    }

    assert Decimal(business_rows["asset_zqtz_treasury_bond"]["current_balance"]) == Decimal("9.50000000")
    assert Decimal(business_rows["asset_zqtz_abs"]["current_balance"]) == Decimal("7.25000000")


def test_balance_movement_analysis_service_builds_derived_diagnostics():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date varchar,
              report_month varchar,
              currency_basis varchar,
              sort_order integer,
              basis_bucket varchar,
              previous_balance decimal(24, 8),
              current_balance decimal(24, 8),
              balance_change decimal(24, 8),
              change_pct decimal(24, 8),
              contribution_pct decimal(24, 8),
              zqtz_amount decimal(24, 8),
              gl_amount decimal(24, 8),
              reconciliation_diff decimal(24, 8),
              reconciliation_status varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_accounting_asset_movement_monthly values (
              ?, ?, 'CNX', ?, ?, 0, ?, ?, 0, 0, ?, ?, 0, 'matched', 'sv-read', 'rv-read'
            )
            """,
            [
                ("2026-01-31", "2026-01", 1, "AC", "120", "0", "120", "120"),
                ("2026-01-31", "2026-01", 2, "OCI", "40", "0", "40", "40"),
                ("2026-01-31", "2026-01", 3, "TPL", "15", "0", "15", "15"),
                ("2026-02-28", "2026-02", 1, "AC", "100", "-20", "100", "100"),
                ("2026-02-28", "2026-02", 2, "OCI", "50", "10", "50", "50"),
                ("2026-02-28", "2026-02", 3, "TPL", "25", "10", "25", "25"),
            ],
        )
        conn.execute(
            """
            create table product_category_pnl_canonical_fact (
              report_date varchar,
              account_code varchar,
              currency varchar,
              account_name varchar,
              beginning_balance decimal(24, 8),
              ending_balance decimal(24, 8),
              monthly_pnl decimal(24, 8),
              daily_avg_balance decimal(24, 8),
              annual_avg_balance decimal(24, 8),
              days_in_period integer,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, 'CNX', ?, 0, ?, 0, 0, 0, 28, 'sv-gl', 'rv-gl')",
            [
                ("2026-01-31", "14401010004", "fair value adjustment", "3"),
                ("2026-02-28", "14401010004", "fair value adjustment", "8"),
                ("2026-02-28", "14501000001", "long equity", "20"),
                ("2026-02-28", "14301010001", "voucher treasury cost", "5"),
                ("2026-02-28", "14301010002", "voucher treasury interest", "2"),
            ],
        )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              bond_type varchar,
              business_type_primary varchar,
              instrument_code varchar,
              instrument_name varchar,
              currency_code varchar,
              market_value_amount decimal(24, 8),
              amortized_cost_amount decimal(24, 8),
              accrued_interest_amount decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_zqtz_balance_daily values (?, ?, 'asset', 'CNY', ?, ?, ?, ?, 'CNY', ?, ?, ?, 'sv-zqtz', 'rv-zqtz')",
            [
                ("2026-02-28", "AC", "国债", "国债", "T1", "国债A", "100", "100", "0"),
                ("2026-02-28", "AC", "凭证式国债", "凭证式国债", "V1", "凭证式国债A", "0", "0", "2"),
                ("2026-02-28", "AC", "地方政府债", "地方政府债券", "L1", "地方政府债A", "68", "68", "0"),
            ],
        )
    finally:
        conn.close()

    envelope = accounting_asset_movement_envelope(
        str(duckdb_path),
        report_date="2026-02-28",
        currency_basis="CNX",
    )
    payload = envelope["result"]

    structure = payload["structure_migration_analysis"]
    assert structure["caveat"].startswith("这是汇总会计分类桶的结构信号")
    assert structure["pairs"][0]["dominant_share_increase_bucket"] in {"OCI", "TPL"}
    assert "损益波动暴露" in structure["pairs"][0]["fvtpl_volatility_signal"]
    assert "至少一半" in structure["pairs"][0]["oci_valuation_signal"]

    waterfall = payload["difference_attribution_waterfall"]
    components = {
        component["component_key"]: Decimal(component["amount"])
        for component in waterfall["components"]
    }
    assert Decimal(waterfall["reference_total"]) == Decimal("190.00000000")
    assert Decimal(waterfall["target_total"]) == Decimal("175.00000000")
    assert Decimal(waterfall["net_difference"]) == Decimal("-15.00000000")
    assert components["long_term_equity_investment"] == Decimal("-20.00000000")
    assert components["voucher_treasury_1430101_cost"] == Decimal("5.00000000")
    assert components["voucher_treasury_1430101_accrued_interest"] == Decimal("0E-8")
    assert components["residual_unclassified"] == Decimal("0E-8")
    assert Decimal(waterfall["closing_check"]) == Decimal("0E-8")


def test_difference_attribution_inputs_tolerate_sparse_voucher_schema():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table product_category_pnl_canonical_fact (
              report_date varchar,
              account_code varchar,
              currency varchar,
              ending_balance decimal(24, 8)
            )
            """
        )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?)",
            [
                ("2026-02-28", "14301010001", "CNX", "100"),
                ("2026-02-28", "14301010002", "CNX", "7"),
            ],
        )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              position_scope varchar,
              currency_basis varchar,
              bond_type varchar,
              instrument_name varchar,
              amortized_cost_amount decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values (
              '2026-02-28',
              'asset',
              'CNY',
              '凭证式国债',
              '凭证式国债测试持仓',
              95
            )
            """
        )
    finally:
        conn.close()

    inputs = AccountingAssetMovementRepository(
        str(duckdb_path)
    ).fetch_difference_attribution_inputs(
        report_date="2026-02-28",
        currency_basis="CNX",
    )

    assert inputs["ledger_voucher_cost"] == Decimal("100.00000000")
    assert inputs["ledger_voucher_accrued_interest"] == Decimal("7.00000000")
    assert inputs["formal_voucher_amortized_cost"] == Decimal("95.00000000")
    assert inputs["formal_voucher_accrued_interest"] == Decimal("0")


def test_balance_movement_dates_only_advertise_materialized_read_model_dates():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table product_category_pnl_canonical_fact (
              report_date varchar,
              account_code varchar,
              currency varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date varchar,
              report_month varchar,
              currency_basis varchar,
              sort_order integer,
              basis_bucket varchar,
              previous_balance decimal(24, 8),
              current_balance decimal(24, 8),
              balance_change decimal(24, 8),
              change_pct decimal(24, 8),
              contribution_pct decimal(24, 8),
              zqtz_amount decimal(24, 8),
              gl_amount decimal(24, 8),
              reconciliation_diff decimal(24, 8),
              reconciliation_status varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?)",
            ["2026-02-28", "14101010001", "CNX"],
        )
        conn.execute(
            """
            insert into fact_accounting_asset_movement_monthly values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2026-01-31",
                "2026-01",
                "CNX",
                1,
                "AC",
                "90",
                "100",
                "10",
                "11.11111111",
                "100",
                "100",
                "100",
                "0",
                "matched",
                "sv-read-model",
                "rv-read-model",
            ],
        )
    finally:
        conn.close()

    envelope = accounting_asset_movement_dates_envelope(
        str(duckdb_path),
        currency_basis="CNX",
    )

    assert envelope["result"]["report_dates"] == ["2026-01-31"]
    assert envelope["result_meta"]["tables_used"] == [
        "fact_accounting_asset_movement_monthly"
    ]


def test_balance_movement_dates_source_version_is_currency_scoped():
    duckdb_path = (
        Path("test_output")
        / "accounting_asset_movement"
        / f"{uuid4().hex}.duckdb"
    )
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date varchar,
              report_month varchar,
              currency_basis varchar,
              sort_order integer,
              basis_bucket varchar,
              previous_balance decimal(24, 8),
              current_balance decimal(24, 8),
              balance_change decimal(24, 8),
              change_pct decimal(24, 8),
              contribution_pct decimal(24, 8),
              zqtz_amount decimal(24, 8),
              gl_amount decimal(24, 8),
              reconciliation_diff decimal(24, 8),
              reconciliation_status varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_accounting_asset_movement_monthly values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    "2026-02-28",
                    "2026-02",
                    "CNY",
                    1,
                    "AC",
                    "90",
                    "100",
                    "10",
                    "11.11111111",
                    "100",
                    "100",
                    "100",
                    "0",
                    "matched",
                    "sv-cny-latest",
                    "rv-cny",
                ),
                (
                    "2026-01-31",
                    "2026-01",
                    "CNX",
                    1,
                    "AC",
                    "80",
                    "90",
                    "10",
                    "12.50000000",
                    "100",
                    "90",
                    "90",
                    "0",
                    "matched",
                    "sv-cnx-selected",
                    "rv-cnx",
                ),
            ],
        )
    finally:
        conn.close()

    envelope = accounting_asset_movement_dates_envelope(
        str(duckdb_path),
        currency_basis="CNX",
    )

    assert envelope["result"]["report_dates"] == ["2026-01-31"]
    assert envelope["result_meta"]["source_version"] == "sv-cnx-selected"
    assert envelope["result_meta"]["filters_applied"] == {"currency_basis": "CNX"}


def _seed_source_tables_and_materialize(
    duckdb_path: Path,
) -> list[object]:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              bond_type varchar,
              business_type_primary varchar,
              market_value_amount decimal(24, 8),
              amortized_cost_amount decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            create table product_category_pnl_canonical_fact (
              report_date varchar,
              account_code varchar,
              currency varchar,
              account_name varchar,
              beginning_balance decimal(24, 8),
              ending_balance decimal(24, 8),
              monthly_pnl decimal(24, 8),
              daily_avg_balance decimal(24, 8),
              annual_avg_balance decimal(24, 8),
              days_in_period integer,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_zqtz_balance_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-01-31", "FVTPL", "asset", "CNY", "其他债券", "同业存单", "12", "12", "sv-zqtz-prior", "rv-zqtz-prior"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "其他债券", "同业存单", "18", "18", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "国债", "国债", "999", "999", "sv-zqtz-cny", "rv-balance-cny"),
                ("2026-02-28", "AC", "asset", "CNY", "国债", "国债", "999", "999", "sv-zqtz-cny", "rv-balance-cny"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "国债", "国债", "999", "999", "sv-zqtz-cny", "rv-balance-cny"),
            ],
        )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-01-31", "14101010001", "CNX", "TPL", "90", "100", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14201010001", "CNX", "AC bond", "190", "200", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14301010001", "CNX", "Voucher bond", "4", "4", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14301010002", "CNX", "Voucher accrued", "1", "1", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14401010001", "CNX", "OCI debt", "65", "70", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14402010001", "CNX", "OCI equity", "90", "99", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "12001000001", "CNX", "拆放同业", "35", "40", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "12101000001", "CNX", "拆放同业", "8", "10", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14001000001", "CNX", "买入返售", "65", "70", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14004000001", "CNX", "排除买入返售", "999", "999", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "14005000001", "CNX", "排除买入返售", "999", "999", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "11401000001", "CNX", "同业存放-活期", "25", "30", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "11501000001", "CNX", "存放同业境内-定期", "35", "40", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "11601000001", "CNX", "存放同业境外-定期", "15", "20", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "23401000001", "CNX", "同业存放", "-45", "-50", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "23501000001", "CNX", "同业存放", "-8", "-10", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "24101000001", "CNX", "同业拆入", "-15", "-20", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "24201000001", "CNX", "同业拆入", "-3", "-5", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "25501000001", "CNX", "卖出回购", "-60", "-70", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "27205000001", "CNX", "同业存单", "-10", "-11", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-01-31", "27206000001", "CNX", "同业存单", "-8", "-9", "0", "0", "0", 31, "sv-gl-prior", "rv-gl-prior"),
                ("2026-02-28", "14101010001", "CNX", "TPL", "100", "110", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14201010001", "CNX", "AC bond", "200", "220", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14301010001", "CNX", "Voucher bond", "4", "4", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14301010002", "CNX", "Voucher accrued", "1", "1", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14401010001", "CNX", "OCI debt", "70", "80", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14402010001", "CNX", "OCI equity", "90", "99", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "12001000001", "CNX", "拆放同业", "40", "60", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "12101000001", "CNX", "拆放同业", "10", "20", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14001000001", "CNX", "买入返售", "70", "90", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14004000001", "CNX", "排除买入返售", "999", "999", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "14005000001", "CNX", "排除买入返售", "999", "999", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "11401000001", "CNX", "同业存放-活期", "30", "35", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "11501000001", "CNX", "存放同业境内-定期", "40", "45", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "11601000001", "CNX", "存放同业境外-定期", "20", "25", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "23401000001", "CNX", "同业存放", "-50", "-70", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "23501000001", "CNX", "同业存放", "-10", "-20", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "24101000001", "CNX", "同业拆入", "-20", "-25", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "24201000001", "CNX", "同业拆入", "-5", "-10", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "25501000001", "CNX", "卖出回购", "-70", "-95", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "27205000001", "CNX", "同业存单", "-11", "-25", "0", "0", "0", 28, "sv-gl", "rv-gl"),
                ("2026-02-28", "27206000001", "CNX", "同业存单", "-9", "-15", "0", "0", "0", 28, "sv-gl", "rv-gl"),
            ],
        )
        materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-01-31",
            currency_basis="CNX",
        )
        return materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-02-28",
            currency_basis="CNX",
        )
    finally:
        conn.close()
