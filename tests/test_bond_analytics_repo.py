from datetime import date
from decimal import Decimal

import duckdb

from backend.app.core_finance.bond_analytics.engine import compute_bond_analytics_rows
from backend.app.repositories.bond_analytics_repo import (
    _ANALYTICS_COLUMNS,
    BondAnalyticsRepository,
)
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.repositories.snapshot_repo import ensure_snapshot_tables


REPORT_DATE = "2026-03-31"


def _analytics_row():
    return compute_bond_analytics_rows(
        [
            {
                "report_date": date.fromisoformat(REPORT_DATE),
                "instrument_code": "BOND-VALUE-DATE",
                "currency_code": "CNY",
                "face_value_native": Decimal("100"),
                "market_value_native": Decimal("99"),
                "amortized_cost_native": Decimal("98"),
                "accrued_interest_native": Decimal("1"),
                "coupon_rate": Decimal("3"),
                "ytm_value": Decimal("3.5"),
                "value_date": date(2023, 4, 20),
                "maturity_date": date(2026, 4, 20),
                "interest_mode": "bullet",
                "is_issuance_like": False,
            }
        ],
        date.fromisoformat(REPORT_DATE),
    )[0]


def test_replace_and_fetch_bond_analytics_preserves_value_date(tmp_path):
    path = str(tmp_path / "moss.duckdb")
    repo = BondAnalyticsRepository(path)

    with repository_task_write_scope("backend.app.tasks.bond_analytics_repo_test"):
        repo.replace_bond_analytics_rows(report_date=REPORT_DATE, rows=[_analytics_row()])

    rows = repo.fetch_bond_analytics_rows(report_date=REPORT_DATE)
    rows_for_dates = repo.fetch_bond_analytics_rows_for_dates(report_dates=[REPORT_DATE])

    assert rows[0]["value_date"] == date(2023, 4, 20)
    assert rows_for_dates[REPORT_DATE][0]["value_date"] == date(2023, 4, 20)


def test_load_snapshot_rows_reads_value_date(tmp_path):
    path = str(tmp_path / "snapshot.duckdb")
    conn = duckdb.connect(path, read_only=False)
    try:
        ensure_snapshot_tables(conn)
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, value_date, maturity_date, is_issuance_like
            ) values (?, ?, ?, ?, false)
            """,
            [REPORT_DATE, "BOND-SNAPSHOT", "2023-04-20", "2026-04-20"],
        )
    finally:
        conn.close()

    rows = BondAnalyticsRepository(path).load_snapshot_rows(REPORT_DATE)

    assert rows[0]["value_date"] == date(2023, 4, 20)


def test_fetch_bond_analytics_treats_missing_legacy_value_date_column_as_null(tmp_path):
    path = str(tmp_path / "legacy.duckdb")
    conn = duckdb.connect(path, read_only=False)
    try:
        legacy_columns = [column for column in _ANALYTICS_COLUMNS if column != "value_date"]
        empty_projection = ", ".join(
            f'cast(null as varchar) as "{column}"' for column in legacy_columns
        )
        conn.execute(
            f"""
            create table fact_formal_bond_analytics_daily as
            select {empty_projection}
            where false
            """
        )
        conn.execute(
            """
            insert into fact_formal_bond_analytics_daily (report_date, instrument_code)
            values (?, ?)
            """,
            [REPORT_DATE, "LEGACY-BOND"],
        )
    finally:
        conn.close()

    repo = BondAnalyticsRepository(path)

    assert repo.fetch_bond_analytics_rows(report_date=REPORT_DATE)[0]["value_date"] is None
    assert (
        repo.fetch_bond_analytics_rows_for_dates(report_dates=[REPORT_DATE])[REPORT_DATE][0]["value_date"]
        is None
    )


def test_v35_upgrades_pre_value_date_fact_before_replace_and_reads_date(tmp_path):
    path = str(tmp_path / "pre-v35.duckdb")
    conn = duckdb.connect(path, read_only=False)
    try:
        legacy_columns = [column for column in _ANALYTICS_COLUMNS if column != "value_date"]
        empty_projection = ", ".join(
            f'cast(null as varchar) as "{column}"' for column in legacy_columns
        )
        conn.execute(
            f"""
            create table fact_formal_bond_analytics_daily as
            select {empty_projection}
            where false
            """
        )
        conn.execute(
            """
            create table _schema_migrations (
              version integer primary key,
              description text not null,
              applied_at timestamp default current_timestamp
            )
            """
        )
        conn.executemany(
            "insert into _schema_migrations (version, description) values (?, ?)",
            [(version, "already applied") for version in range(1, 35)],
        )

        apply_pending_migrations_on_connection(conn)
        migration_row = conn.execute(
            "select description from _schema_migrations where version = 35"
        ).fetchone()
        value_date_column = conn.execute(
            """
            select data_type
            from information_schema.columns
            where table_schema = 'main'
              and table_name = 'fact_formal_bond_analytics_daily'
              and column_name = 'value_date'
            """
        ).fetchone()
    finally:
        conn.close()

    assert migration_row == ("Preserve bond analytics value date",)
    assert value_date_column == ("DATE",)

    repo = BondAnalyticsRepository(path)
    with repository_task_write_scope("backend.app.tasks.bond_analytics_repo_test"):
        repo.replace_bond_analytics_rows(report_date=REPORT_DATE, rows=[_analytics_row()])

    assert repo.fetch_bond_analytics_rows(report_date=REPORT_DATE)[0]["value_date"] == date(
        2023, 4, 20
    )
    assert repo.fetch_bond_analytics_rows_for_dates(report_dates=[REPORT_DATE])[REPORT_DATE][0][
        "value_date"
    ] == date(2023, 4, 20)
