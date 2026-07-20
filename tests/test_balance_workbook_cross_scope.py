# 回归：position_scope=asset/liability 时，跨口径表（期限缺口/监管阈值/现金流日历/
# 利率分布/对手方类型/概览卡片/右栏运营区块）必须使用全量口径数据构建，
# 不得把负债/缺口/利差静默降级为 0。单口径表仍按用户 scope 过滤。
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.balance_analysis import (
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
)
from backend.app.core_finance.balance_analysis_workbook import (
    build_balance_analysis_workbook_payload,
)
from backend.app.core_finance.balance_workbook import (
    build_balance_analysis_workbook_payload as build_modular_balance_workbook_payload,
)

RD = date(2026, 3, 31)
MAT = date(2027, 3, 31)

CROSS_SCOPE_TABLE_KEYS = (
    "maturity_gap",
    "regulatory_limits",
    "cashflow_calendar",
    "rate_distribution",
    "counterparty_types",
)
CROSS_SCOPE_SECTION_KEYS = (
    "decision_items",
    "event_calendar",
    "risk_alerts",
)


def _zqtz_asset() -> FormalZqtzBalanceFactRow:
    return FormalZqtzBalanceFactRow(
        report_date=RD,
        instrument_code="A0001",
        instrument_name="资产债券",
        portfolio_name="P",
        cost_center="C",
        account_category="可供出售类资产",
        asset_class="信用债",
        bond_type="企业债",
        issuer_name="发行人A",
        industry_name="工业",
        rating="AAA",
        invest_type_std="A",
        accounting_basis="FVOCI",
        position_scope="asset",
        currency_basis="native",
        currency_code="CNY",
        face_value_amount=Decimal("100000000"),
        market_value_amount=Decimal("101000000"),
        amortized_cost_amount=Decimal("100000000"),
        accrued_interest_amount=Decimal("0"),
        # 百分数口径：3.20 = 3.20%（2026-07-19 审计取证 1 裁决）
        coupon_rate=Decimal("3.20"),
        ytm_value=Decimal("3.20"),
        maturity_date=MAT,
        interest_mode="固定",
        is_issuance_like=False,
    )


def _zqtz_issuance() -> FormalZqtzBalanceFactRow:
    return FormalZqtzBalanceFactRow(
        report_date=RD,
        instrument_code="L0001",
        instrument_name="发行类债券",
        portfolio_name="P",
        cost_center="C",
        account_category="发行类债劵",
        asset_class="债券类",
        bond_type="同业存单",
        issuer_name="本行",
        industry_name="金融业",
        rating="",
        invest_type_std="A",
        accounting_basis="FVOCI",
        position_scope="liability",
        currency_basis="native",
        currency_code="CNY",
        face_value_amount=Decimal("40000000"),
        market_value_amount=Decimal("40000000"),
        amortized_cost_amount=Decimal("40000000"),
        accrued_interest_amount=Decimal("0"),
        coupon_rate=Decimal("2.50"),
        ytm_value=Decimal("2.50"),
        maturity_date=MAT,
        interest_mode="固定",
        is_issuance_like=True,
    )


def _tyw_asset() -> FormalTywBalanceFactRow:
    return FormalTywBalanceFactRow(
        report_date=RD,
        position_id="TA1",
        product_type="拆放同业",
        position_side="asset",
        counterparty_name="银行A",
        account_type="资产账户",
        special_account_type="一般",
        core_customer_type="股份制银行",
        invest_type_std="H",
        accounting_basis="AC",
        position_scope="asset",
        currency_basis="native",
        currency_code="CNY",
        principal_amount=Decimal("30000000"),
        accrued_interest_amount=Decimal("0"),
        funding_cost_rate=Decimal("2.10"),
        maturity_date=MAT,
    )


def _tyw_liability() -> FormalTywBalanceFactRow:
    return FormalTywBalanceFactRow(
        report_date=RD,
        position_id="TL1",
        product_type="同业存放",
        position_side="liability",
        counterparty_name="银行B",
        account_type="负债账户",
        special_account_type="一般",
        core_customer_type="股份制银行",
        invest_type_std="H",
        accounting_basis="AC",
        position_scope="liability",
        currency_basis="native",
        currency_code="CNY",
        principal_amount=Decimal("50000000"),
        accrued_interest_amount=Decimal("0"),
        funding_cost_rate=Decimal("1.80"),
        maturity_date=MAT,
    )


def _table(payload: dict, key: str) -> dict:
    for table in payload["tables"]:
        if table["key"] == key:
            return table
    raise AssertionError(f"table {key} not found")


def _all_zqtz() -> list[FormalZqtzBalanceFactRow]:
    return [_zqtz_asset(), _zqtz_issuance()]


def _all_tyw() -> list[FormalTywBalanceFactRow]:
    return [_tyw_asset(), _tyw_liability()]


def _build(*, position_scope, zqtz_rows, tyw_rows, zqtz_full_rows, tyw_full_rows):
    return build_balance_analysis_workbook_payload(
        report_date=RD,
        position_scope=position_scope,
        currency_basis="native",
        zqtz_rows=zqtz_rows,
        tyw_rows=tyw_rows,
        zqtz_full_rows=zqtz_full_rows,
        tyw_full_rows=tyw_full_rows,
    )


def test_asset_scope_cross_scope_tables_match_all_scope():
    reference = build_balance_analysis_workbook_payload(
        report_date=RD,
        position_scope="all",
        currency_basis="native",
        zqtz_rows=_all_zqtz(),
        tyw_rows=_all_tyw(),
    )
    scoped = _build(
        position_scope="asset",
        zqtz_rows=[_zqtz_asset()],
        tyw_rows=[_tyw_asset()],
        zqtz_full_rows=_all_zqtz(),
        tyw_full_rows=_all_tyw(),
    )

    for key in CROSS_SCOPE_TABLE_KEYS:
        assert _table(scoped, key)["rows"] == _table(reference, key)["rows"], key
    for section in scoped["tables"]:
        if section["key"] in CROSS_SCOPE_SECTION_KEYS:
            ref_section = next(t for t in reference["tables"] if t["key"] == section["key"])
            assert section["rows"] == ref_section["rows"], section["key"]
    assert scoped["cards"] == reference["cards"]


def test_public_modular_entrypoint_delegates_to_authoritative_full_scope_builder():
    kwargs = {
        "report_date": RD,
        "position_scope": "asset",
        "currency_basis": "native",
        "zqtz_rows": [_zqtz_asset()],
        "tyw_rows": [_tyw_asset()],
        "zqtz_full_rows": _all_zqtz(),
        "tyw_full_rows": _all_tyw(),
    }

    assert build_modular_balance_workbook_payload(**kwargs) == (
        build_balance_analysis_workbook_payload(**kwargs)
    )


def test_asset_scope_maturity_gap_exposes_liability_columns_not_zero():
    scoped = _build(
        position_scope="asset",
        zqtz_rows=[_zqtz_asset()],
        tyw_rows=[_tyw_asset()],
        zqtz_full_rows=_all_zqtz(),
        tyw_full_rows=_all_tyw(),
    )
    gap = _table(scoped, "maturity_gap")
    liability_total = sum(Decimal(str(r["interbank_liabilities_amount"])) for r in gap["rows"])
    issuance_total = sum(Decimal(str(r["issuance_amount"])) for r in gap["rows"])
    assert liability_total == Decimal("5000")  # 50,000,000 元 -> 万元
    assert issuance_total == Decimal("4000")  # 40,000,000 元 -> 万元


def test_asset_scope_single_scope_liability_table_stays_scoped_empty():
    scoped = _build(
        position_scope="asset",
        zqtz_rows=[_zqtz_asset()],
        tyw_rows=[_tyw_asset()],
        zqtz_full_rows=_all_zqtz(),
        tyw_full_rows=_all_tyw(),
    )
    assert _table(scoped, "issuance_business_types")["rows"] == []


def test_service_fetches_full_scope_rows_and_wires_them_under_asset_scope():
    from tests.helpers import load_module

    workbook_service = load_module(
        "backend.app.services.balance_analysis_workbook_service",
        "backend/app/services/balance_analysis_workbook_service.py",
    )

    def _native_zqtz(scope: str) -> dict:
        return {
            "report_date": "2026-03-31",
            "instrument_code": "A0001" if scope != "liability" else "L0001",
            "instrument_name": "债券",
            "portfolio_name": "P",
            "cost_center": "C",
            "account_category": "可供出售类资产",
            "asset_class": "信用债",
            "bond_type": "企业债",
            "sub_type": "",
            "business_type_primary": "",
            "issuer_name": "发行人A",
            "industry_name": "工业",
            "rating": "AAA",
            "invest_type_std": "A",
            "accounting_basis": "FVOCI",
            "position_scope": scope,
            "currency_basis": "native",
            "currency_code": "CNY",
            "face_value_amount": "100.00000000",
            "market_value_amount": "100.00000000",
            "amortized_cost_amount": "90.00000000",
            "accrued_interest_amount": "0.00000000",
            "coupon_rate": "3.00000000",
            "ytm_value": "3.10000000",
            "maturity_date": "2027-03-31",
            "interest_mode": "固定",
            "is_issuance_like": scope == "liability",
            "overdue_principal_days": 0,
            "overdue_interest_days": 0,
            "value_date": "2026-03-31",
            "customer_attribute": "internal",
            "source_version": "sv",
            "rule_version": "rv",
            "ingest_batch_id": "ib",
            "trace_id": "tr",
        }

    calls: list[tuple[str, str, str]] = []

    class FakeRepo:
        def __init__(self, duckdb_path: str) -> None:
            self.duckdb_path = duckdb_path

        def list_report_dates(self):
            return ["2026-03-31"]

        def fetch_formal_zqtz_rows(self, **kwargs):
            calls.append(("zqtz", kwargs["position_scope"], kwargs["currency_basis"]))
            basis = kwargs["currency_basis"]
            if kwargs["position_scope"] == "all":
                rows = [_native_zqtz("asset"), _native_zqtz("liability")]
            else:
                rows = [_native_zqtz(kwargs["position_scope"])]
            # Echo requested basis so callers can assert currency_basis honor.
            for row in rows:
                row["currency_basis"] = basis
            return rows

        def fetch_formal_tyw_rows(self, **kwargs):
            calls.append(("tyw", kwargs["position_scope"], kwargs["currency_basis"]))
            return []

    captured: dict[str, object] = {}

    class FakeWorkbookModule:
        @staticmethod
        def build_balance_analysis_workbook_payload(**kwargs):
            captured.update(kwargs)
            return {
                "report_date": str(kwargs["report_date"]),
                "position_scope": kwargs["position_scope"],
                "currency_basis": kwargs["currency_basis"],
                "cards": [],
                "tables": [],
            }

    workbook_service._build_balance_workbook_payload(
        duckdb_path="ignored.duckdb",
        governance_dir="ignored-governance",
        report_date="2026-03-31",
        position_scope="asset",
        currency_basis="CNY",
        cache_key="ck",
        job_name="job",
        resolve_completed_formal_build_lineage_fn=lambda **_kwargs: None,
        repo_cls=FakeRepo,
        import_module_fn=lambda _name: FakeWorkbookModule,
        reload_module_fn=lambda module: module,
    )

    # H-2: requested CNY must drive main/full-row fetches (not hardcoded native).
    assert ("zqtz", "asset", "CNY") in calls
    assert ("zqtz", "all", "CNY") in calls
    assert ("tyw", "all", "CNY") in calls
    assert ("zqtz", "all", "native") not in calls
    # Full rows handed to the builder include both asset and liability zqtz rows.
    full_scopes = {row.position_scope for row in captured["zqtz_full_rows"]}
    assert full_scopes == {"asset", "liability"}
    # Scoped rows stay asset-only and keep CNY basis.
    assert {row.position_scope for row in captured["zqtz_rows"]} == {"asset"}
    assert {row.currency_basis for row in captured["zqtz_rows"]} == {"CNY"}
    assert captured["currency_basis"] == "CNY"


def test_liability_scope_cross_scope_tables_match_all_scope():
    reference = build_balance_analysis_workbook_payload(
        report_date=RD,
        position_scope="all",
        currency_basis="native",
        zqtz_rows=_all_zqtz(),
        tyw_rows=_all_tyw(),
    )
    scoped = _build(
        position_scope="liability",
        zqtz_rows=[_zqtz_issuance()],
        tyw_rows=[_tyw_liability()],
        zqtz_full_rows=_all_zqtz(),
        tyw_full_rows=_all_tyw(),
    )
    for key in CROSS_SCOPE_TABLE_KEYS:
        assert _table(scoped, key)["rows"] == _table(reference, key)["rows"], key
    assert scoped["cards"] == reference["cards"]
    assert _table(scoped, "bond_business_types")["rows"] == []
