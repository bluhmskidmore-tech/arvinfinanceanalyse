"""BD-024: real synthetic DuckDB reads must agree with a request's generation.

The HTTP harness uses the real publication resolver and middleware and a small
test endpoint over real repositories/services. It does not start the production
app, exercise authentication, or claim financial reconciliation acceptance.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from backend.app.governance.ledger_classification import LEDGER_CLASSIFICATION_RULE_VERSION
from backend.app.main import SystemReadPublicationMiddleware
from backend.app.repositories.accounting_asset_movement_repo import AccountingAssetMovementRepository
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.cashflow_projection_repo import CashflowProjectionRepository
from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection, DuckDBReadSelectionError, active_read_scope, duckdb_read_scope,
)
from backend.app.repositories.financial_result_publication_repo import (
    canonical_json_bytes, sha256_bytes, sha256_file,
)
from backend.app.repositories.ledger_analytics_repo import LedgerAnalyticsRepository, POSITION_EXPORT_COLUMNS
from backend.app.repositories.system_read_publication_repo import (
    SYSTEM_READ_GENERATION_HEADER, system_read_publication_root,
)
from backend.app.services.accounting_asset_movement_service import accounting_asset_movement_dates_envelope
from backend.app.services.ledger_analytics_service import LedgerAnalyticsService
from tests.test_system_online_read_boundary import _bundle, _seal_generation, _settings, _write_pointer

REPORT_DATE = "2026-09-30"
ZQTZ_COLUMNS = """report_date instrument_code instrument_name portfolio_name cost_center
account_category asset_class bond_type sub_type business_type_primary issuer_name
industry_name rating invest_type_std accounting_basis position_scope currency_basis
currency_code face_value_amount market_value_amount amortized_cost_amount
accrued_interest_amount coupon_rate ytm_value maturity_date interest_mode
is_issuance_like overdue_principal_days overdue_interest_days value_date
customer_attribute source_version rule_version ingest_batch_id trace_id""".split()
ZQTZ_NUMBERS = {"face_value_amount", "market_value_amount", "amortized_cost_amount",
                "accrued_interest_amount", "coupon_rate", "ytm_value",
                "overdue_principal_days", "overdue_interest_days"}
POSITION_NUMBERS = {"face_amount", "fair_value", "amortized_cost", "accrued_interest",
                    "interest_receivable_payable", "quantity", "latest_face_value",
                    "coupon_rate", "yield_to_maturity"}


def _insert(conn, table, columns, values):
    conn.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                 [values.get(column) for column in columns])


def _seed(path: Path, generation: str, *, empty: bool = False):
    amount = 100_000_000 if generation == "G1" else 200_000_000
    source = f"sv_synthetic_{generation}"
    selected_date = REPORT_DATE if generation == "G1" else "2026-10-01"
    with duckdb.connect(str(path)) as conn:
        conn.execute("CREATE TABLE fact_formal_zqtz_balance_daily(" + ", ".join(
            f"{column} {'DECIMAL(24,8)' if column in ZQTZ_NUMBERS else 'VARCHAR'}"
            for column in ZQTZ_COLUMNS) + ")")
        conn.execute("""CREATE TABLE fact_formal_tyw_balance_daily(
            report_date VARCHAR, position_id VARCHAR, product_type VARCHAR,
            position_side VARCHAR, counterparty_name VARCHAR, currency_code VARCHAR,
            principal_amount DECIMAL(24,8), funding_cost_rate DECIMAL(24,8),
            maturity_date VARCHAR, source_version VARCHAR, rule_version VARCHAR,
            position_scope VARCHAR, currency_basis VARCHAR)""")
        conn.execute("CREATE TABLE position_snapshot(" + ", ".join(
            f"{column} {'BIGINT' if column in {'batch_id', 'row_no'} else 'DECIMAL(24,8)' if column in POSITION_NUMBERS else 'VARCHAR'}"
            for column in POSITION_EXPORT_COLUMNS) + ", source_version VARCHAR, rule_version VARCHAR)")
        conn.execute("""CREATE TABLE fact_accounting_asset_movement_monthly(
            report_date VARCHAR, currency_basis VARCHAR, source_version VARCHAR, sort_order INTEGER)""")
        conn.execute("CREATE TABLE product_category_pnl_canonical_fact(report_date VARCHAR, currency VARCHAR, account_code VARCHAR)")
        conn.execute("CREATE TABLE fact_formal_bond_analytics_daily(report_date VARCHAR)")
        if empty:
            return
        _insert(conn, "fact_formal_zqtz_balance_daily", ZQTZ_COLUMNS, {
            "report_date": REPORT_DATE, "instrument_code": "SYNTHETIC-BOND",
            "portfolio_name": "synthetic", "cost_center": "synthetic",
            "position_scope": "asset", "currency_basis": "CNY", "currency_code": "CNY",
            "face_value_amount": amount, "market_value_amount": amount,
            "source_version": source, "rule_version": "rv_synthetic",
        })
        conn.execute("INSERT INTO fact_formal_tyw_balance_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     [REPORT_DATE, "synthetic-tywl", "synthetic", "liability", "synthetic", "CNY",
                      amount // 2, 1, "2027-09-30", source, "rv_synthetic", "liability", "CNY"])
        values = {column: "synthetic" for column in POSITION_EXPORT_COLUMNS}
        values.update({column: 0 for column in POSITION_NUMBERS})
        values.update(batch_id=1, row_no=1, as_of_date=selected_date, direction="ASSET", currency="CNY",
                      face_amount=amount, fair_value=amount, interest_start_date=REPORT_DATE,
                      maturity_date="2027-09-30", source_version=source,
                      rule_version=LEDGER_CLASSIFICATION_RULE_VERSION)
        _insert(conn, "position_snapshot", (*POSITION_EXPORT_COLUMNS, "source_version", "rule_version"), values)
        conn.execute("INSERT INTO fact_accounting_asset_movement_monthly VALUES (?, 'CNX', ?, 1)", [selected_date, source])
        conn.execute("INSERT INTO product_category_pnl_canonical_fact VALUES (?, 'CNX', '14101')", [selected_date])
        conn.execute("INSERT INTO fact_formal_bond_analytics_daily VALUES (?)", [selected_date])


@pytest.fixture
def databases(tmp_path):
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "g1.duckdb"
    _seed(active, "G2")
    _seed(snapshot, "G1")
    return SimpleNamespace(active=active, snapshot=snapshot,
                           selection=DuckDBReadSelection(active, snapshot, "G1"))


def _read_values(active):
    cashflow = CashflowProjectionRepository(str(active))
    ledger = LedgerAnalyticsService(str(active))
    return {
        "zqtz": cashflow.fetch_formal_zqtz_rows(report_date=REPORT_DATE),
        "tyw": cashflow.fetch_formal_tyw_liability_rows(report_date=REPORT_DATE),
        "ledger_dates": ledger.dates(),
        "ledger_dashboard": ledger.dashboard(requested_as_of_date="2026-10-01"),
        "ledger_positions": ledger.positions(requested_as_of_date="2026-10-01", filters={}, page=1, page_size=20),
        "movement_dates": accounting_asset_movement_dates_envelope(str(active)),
        "bond_dates": BondAnalyticsRepository(str(active)).list_report_dates(),
    }


def _assert_values(values, generation):
    amount = 100_000_000 if generation == "G1" else 200_000_000
    source = f"sv_synthetic_{generation}"
    selected_date = REPORT_DATE if generation == "G1" else "2026-10-01"
    assert values["zqtz"][0]["face_value_amount"] == amount
    assert values["zqtz"][0]["source_version"] == source
    assert values["tyw"][0]["principal_amount"] == amount // 2
    assert values["tyw"][0]["source_version"] == source
    assert values["ledger_dates"]["data"]["items"] == [selected_date]
    assert values["ledger_dates"]["metadata"]["source_version"] == source
    assert values["ledger_dashboard"]["data"]["currency_breakdown"][0]["asset_face_amount"] == amount / 100_000_000
    assert values["ledger_dashboard"]["metadata"]["source_version"] == source
    assert values["ledger_positions"]["data"]["items"][0]["face_amount"] == amount
    assert values["ledger_positions"]["metadata"]["source_version"] == source
    assert values["movement_dates"]["result"]["report_dates"] == [selected_date]
    assert values["movement_dates"]["result"]["upstream_control_report_dates"] == [selected_date]
    assert values["movement_dates"]["result_meta"]["source_version"] == source
    assert values["bond_dates"] == [selected_date]


def test_real_repositories_and_consumers_use_pin_and_restore_active(databases):
    _assert_values(_read_values(databases.active), "G2")
    with duckdb_read_scope(databases.selection, required_online=True):
        _assert_values(_read_values(databases.active), "G1")
        with active_read_scope():
            _assert_values(_read_values(databases.active), "G2")
        _assert_values(_read_values(databases.active), "G1")
    _assert_values(_read_values(databases.active), "G2")


def test_ledger_existing_snapshot_works_without_active_database(databases):
    databases.active.unlink()
    with duckdb_read_scope(databases.selection, required_online=True):
        _assert_values(_read_values(databases.active), "G1")


def test_ledger_workbook_values_dates_and_metadata_share_pin(databases):
    with duckdb_read_scope(databases.selection, required_online=True):
        filename, content, headers = LedgerAnalyticsService(str(databases.active)).export_positions(
            requested_as_of_date="2026-10-01", filters={})
    assert filename == f"ledger-positions-{REPORT_DATE}.xlsx"
    assert headers["X-Ledger-Source-Version"] == "sv_synthetic_G1"
    workbook = load_workbook(io.BytesIO(content), read_only=True)
    try:
        rows = list(workbook["positions"].values)
        assert rows[1][rows[0].index("face_amount")] == 100_000_000
        assert rows[1][rows[0].index("as_of_date")] == REPORT_DATE
        metadata = dict(workbook["metadata"].values)
        assert metadata["source_version"] == "sv_synthetic_G1"
        assert metadata["resolved_as_of_date"] == REPORT_DATE
    finally:
        workbook.close()


READERS = [
    lambda path: CashflowProjectionRepository(str(path)).fetch_formal_zqtz_rows(report_date=REPORT_DATE),
    lambda path: CashflowProjectionRepository(str(path)).fetch_formal_tyw_liability_rows(report_date=REPORT_DATE),
    lambda path: LedgerAnalyticsRepository(str(path)).list_dates(),
    lambda path: LedgerAnalyticsRepository(str(path)).dashboard(requested_as_of_date=REPORT_DATE),
    lambda path: LedgerAnalyticsRepository(str(path)).list_positions(requested_as_of_date=REPORT_DATE, filters={}, limit=20, offset=0),
    lambda path: AccountingAssetMovementRepository(str(path)).list_report_dates(),
    lambda path: AccountingAssetMovementRepository(str(path)).list_control_report_dates(),
    lambda path: AccountingAssetMovementRepository(str(path)).latest_source_version(),
    lambda path: BondAnalyticsRepository(str(path)).list_report_dates(),
]


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("missing", ["selection", "deleted_snapshot"])
def test_missing_pin_fails_closed_before_any_active_read(databases, reader, missing):
    selection = databases.selection if missing == "deleted_snapshot" else None
    with duckdb_read_scope(selection, required_online=True, active_path=databases.active):
        if missing == "deleted_snapshot":
            databases.snapshot.unlink()
        with pytest.raises(DuckDBReadSelectionError):
            reader(databases.active)


def test_valid_empty_snapshot_never_falls_back_to_populated_active(tmp_path):
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "empty.duckdb"
    _seed(active, "G2")
    _seed(snapshot, "G1", empty=True)
    with duckdb_read_scope(DuckDBReadSelection(active, snapshot, "empty"), required_online=True):
        for reader in READERS[:3] + READERS[5:7] + READERS[8:]:
            assert reader(active) == []
        assert READERS[3](active) is None
        assert READERS[4](active) is None
        assert READERS[7](active) == "sv_accounting_asset_movement_empty"


def test_unbound_missing_database_behavior_is_unchanged(tmp_path):
    missing = tmp_path / "missing.duckdb"
    assert READERS[0](missing) == []
    assert READERS[1](missing) == []
    assert READERS[2](missing) == []
    assert READERS[3](missing) is None
    assert READERS[4](missing) is None
    with pytest.raises(duckdb.IOException):
        READERS[5](missing)
    assert not missing.exists()


def test_movement_scoped_cursor_keeps_owner_alive_and_rejects_context_change(databases):
    repo = AccountingAssetMovementRepository(str(databases.active))
    with duckdb_read_scope(databases.selection, required_online=True):
        with repo.scoped_connection() as owner:
            assert repo.list_report_dates() == [REPORT_DATE]
            assert repo.latest_source_version() == "sv_synthetic_G1"
            assert owner.execute("SELECT 1").fetchone() == (1,)
            with active_read_scope():
                with pytest.raises(RuntimeError, match="read context changed"):
                    repo.list_report_dates()
            assert repo.list_report_dates() == [REPORT_DATE]


@pytest.mark.parametrize("repository", [CashflowProjectionRepository, LedgerAnalyticsRepository, AccountingAssetMovementRepository])
def test_connections_remain_read_only(databases, repository):
    from backend.app.repositories.cashflow_projection_repo import _connect_read_only
    with duckdb_read_scope(databases.selection, required_online=True):
        repo = repository(str(databases.active))
        conn = _connect_read_only(repo.path) if repository is CashflowProjectionRepository else repo._connect()
        try:
            with pytest.raises(duckdb.Error):
                conn.execute("CREATE TABLE forbidden_write(value INTEGER)")
        finally:
            conn.close()


def _business_generation(root, label, settings, pnl_digest):
    generation = f"system-read-2026-09-15-{label[-1] * 20}"
    _seal_generation(root, generation, generation, system_read_bundle=_bundle(settings, "pnl-synthetic", pnl_digest))
    database = root / "generations" / f"{generation}.duckdb"
    _seed(database, label)
    manifest_path = root / "generations" / f"{generation}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest["database"].update(size_bytes=database.stat().st_size, sha256=sha256_file(database))
    content = canonical_json_bytes(manifest)
    manifest_path.write_bytes(content)
    return generation, sha256_bytes(content)


def test_http_generation_header_values_and_sources_agree(tmp_path):
    settings = _settings(tmp_path)
    _seed(Path(settings.duckdb_path), "G2")
    pnl_root = Path(settings.financial_publication_root)
    pnl_digest = _seal_generation(pnl_root, "pnl-synthetic", "SYNTHETIC")
    _write_pointer(pnl_root, "pnl-synthetic", [("pnl-synthetic", pnl_digest)])
    root = system_read_publication_root(settings)
    g1 = _business_generation(root, "G1", settings, pnl_digest)
    g2 = _business_generation(root, "G2", settings, pnl_digest)
    _write_pointer(root, g2[0], [g2, g1])
    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)

    @app.get("/synthetic-read-boundaries")
    def read_boundaries():
        return _read_values(settings.duckdb_path)

    with TestClient(app) as client:
        for label, generation in (("G1", g1[0]), ("G2", g2[0]), ("G1", g1[0])):
            response = client.get("/synthetic-read-boundaries", headers={SYSTEM_READ_GENERATION_HEADER: generation})
            assert response.status_code == 200
            assert response.headers[SYSTEM_READ_GENERATION_HEADER] == generation
            _assert_values(response.json(), label)
        (root / "generations" / f"{g1[0]}.duckdb").unlink()
        rejected = client.get("/synthetic-read-boundaries", headers={SYSTEM_READ_GENERATION_HEADER: g1[0]})
        assert rejected.status_code == 503
        assert SYSTEM_READ_GENERATION_HEADER not in rejected.headers
