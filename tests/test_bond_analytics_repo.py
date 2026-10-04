from datetime import date, timedelta
from decimal import Decimal

import duckdb
import pytest

from backend.app.core_finance.bond_analytics.engine import compute_bond_analytics_rows
from backend.app.core_finance.risk_tensor import compute_portfolio_risk_tensor
from backend.app.repositories.bond_analytics_repo import (
    _ANALYTICS_COLUMNS,
    BondAnalyticsRepository,
)
from backend.app.repositories.duckdb_migrations import (
    apply_pending_migrations_on_connection,
    ensure_bond_analytics_input_quality_columns,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.repositories.snapshot_repo import ensure_snapshot_tables


REPORT_DATE = "2026-03-31"


def _analytics_row(report_date: str = REPORT_DATE):
    return compute_bond_analytics_rows(
        [
            {
                "report_date": date.fromisoformat(report_date),
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
        date.fromisoformat(report_date),
    )[0]


def test_replace_and_fetch_bond_analytics_preserves_value_date(tmp_path):
    path = str(tmp_path / "moss.duckdb")
    repo = BondAnalyticsRepository(path)

    with repository_task_write_scope("backend.app.tasks.bond_analytics_repo_test"):
        repo.replace_bond_analytics_rows(report_date=REPORT_DATE, rows=[_analytics_row()])

    rows = repo.fetch_bond_analytics_rows(report_date=REPORT_DATE)
    rows_for_dates = repo.fetch_bond_analytics_rows_for_dates(report_dates=[REPORT_DATE])

    assert rows[0]["value_date"] == date(2023, 4, 20)
    assert rows[0]["interest_payment_frequency_fallback_used"] is False
    assert rows_for_dates[REPORT_DATE][0]["value_date"] == date(2023, 4, 20)
    assert rows_for_dates[REPORT_DATE][0]["interest_payment_frequency_fallback_used"] is False


def test_replace_and_fetch_bond_analytics_preserves_input_quality_provenance(tmp_path):
    path = str(tmp_path / "input-quality.duckdb")
    report_day = date.fromisoformat(REPORT_DATE)
    analytics_row = compute_bond_analytics_rows(
        [
            {
                "report_date": report_day,
                "instrument_code": "BOND-PAR-FALLBACK",
                "currency_code": "CNY",
                "face_value_native": Decimal("100"),
                "market_value_native": Decimal("99"),
                "amortized_cost_native": Decimal("98"),
                "accrued_interest_native": Decimal("1"),
                "coupon_rate": Decimal("3"),
                "ytm_value": None,
                "maturity_date": date(2031, 3, 31),
                "interest_mode": "annual",
                "is_issuance_like": False,
            }
        ],
        report_day,
    )[0]
    repo = BondAnalyticsRepository(path)

    with repository_task_write_scope("backend.app.tasks.bond_analytics_repo_test"):
        repo.replace_bond_analytics_rows(report_date=REPORT_DATE, rows=[analytics_row])

    expected = {
        "coupon_rate_input_status": "observed",
        "ytm_input_status": "missing",
        "duration_quality_flag": "ytm_par_fallback",
    }
    assert {
        key: repo.fetch_bond_analytics_rows(report_date=REPORT_DATE)[0][key]
        for key in expected
    } == expected
    assert {
        key: repo.fetch_bond_analytics_rows_for_dates(report_dates=[REPORT_DATE])[
            REPORT_DATE
        ][0][key]
        for key in expected
    } == expected


def test_bond_analytics_input_quality_column_migration_is_idempotent(tmp_path):
    path = str(tmp_path / "legacy-input-quality.duckdb")
    conn = duckdb.connect(path, read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              instrument_code varchar
            )
            """
        )
        conn.execute(
            "insert into fact_formal_bond_analytics_daily values (?, ?)",
            [REPORT_DATE, "LEGACY-BOND"],
        )

        ensure_bond_analytics_input_quality_columns(conn)
        ensure_bond_analytics_input_quality_columns(conn)

        columns = {
            str(row[1]): str(row[2])
            for row in conn.execute(
                "pragma table_info('fact_formal_bond_analytics_daily')"
            ).fetchall()
        }
        legacy_values = conn.execute(
            """
            select coupon_rate_input_status, ytm_input_status, duration_quality_flag
            from fact_formal_bond_analytics_daily
            """
        ).fetchone()
    finally:
        conn.close()

    assert columns["coupon_rate_input_status"] == "VARCHAR"
    assert columns["ytm_input_status"] == "VARCHAR"
    assert columns["duration_quality_flag"] == "VARCHAR"
    assert legacy_values == (None, None, None)


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


def test_load_snapshot_rows_fails_closed_for_duplicate_formal_cny_with_partial_null(tmp_path):
    """Two formal-CNY rows in one aggregation group must not mask a partial row via SUM(NULL).

    The two rows differ only by accounting basis, which is the real shape of this
    collision: one bond is carried in two books at once, and the snapshot join key
    does not carry accounting_basis, so both land in the same aggregation group.
    """

    from tests.test_bond_analytics_materialize_flow import (
        _seed_bond_snapshot_rows,
        _seed_formal_zqtz_balance_for_cb001,
    )

    path = str(tmp_path / "duplicate-formal-cny.duckdb")
    _seed_bond_snapshot_rows(path)
    _seed_formal_zqtz_balance_for_cb001(
        path,
        market_value_amount=Decimal("1900"),
        face_value_amount=Decimal("2000"),
        amortized_cost_amount=Decimal("1880"),
        accrued_interest_amount=Decimal("20"),
        accounting_basis="FVOCI",
    )
    _seed_formal_zqtz_balance_for_cb001(
        path,
        market_value_amount=Decimal("1901"),
        face_value_amount=Decimal("2001"),
        amortized_cost_amount=Decimal("1881"),
        accrued_interest_amount=Decimal("21"),
        accounting_basis="AC",
    )

    conn = duckdb.connect(path, read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set accrued_interest_amount = NULL
            where report_date = ?
              and instrument_code = ?
              and market_value_amount = ?
            """,
            [REPORT_DATE, "CB-001", Decimal("1901")],
        )
    finally:
        conn.close()

    row = next(
        row
        for row in BondAnalyticsRepository(path).load_snapshot_rows(REPORT_DATE)
        if row["instrument_code"] == "CB-001"
    )

    assert row["face_value_cny"] is None
    assert row["market_value_cny"] is None
    assert row["amortized_cost_cny"] is None
    assert row["accrued_interest_cny"] is None


_BALANCE_FACT_DDL = """
    create table if not exists fact_formal_zqtz_balance_daily (
      report_date varchar,
      instrument_code varchar,
      instrument_name varchar,
      portfolio_name varchar,
      cost_center varchar,
      account_category varchar,
      asset_class varchar,
      bond_type varchar,
      sub_type varchar,
      business_type_primary varchar,
      issuer_name varchar,
      industry_name varchar,
      rating varchar,
      invest_type_std varchar,
      accounting_basis varchar,
      position_scope varchar,
      currency_basis varchar,
      currency_code varchar,
      face_value_amount decimal(24, 8),
      market_value_amount decimal(24, 8),
      amortized_cost_amount decimal(24, 8),
      accrued_interest_amount decimal(24, 8),
      coupon_rate decimal(18, 8),
      ytm_value decimal(18, 8),
      maturity_date varchar,
      interest_mode varchar,
      is_issuance_like boolean,
      source_version varchar,
      rule_version varchar,
      ingest_batch_id varchar,
      trace_id varchar
    )
"""


def test_load_snapshot_rows_keeps_cny_amounts_per_maturity_leg(tmp_path):
    """展期/重分类的同券两腿仅 maturity_date 不同：每腿只对上自己的 balance CNY 金额。

    balance fact 天然键含 maturity_date（fact_load_gates.ZQTZ_BALANCE_NATURAL_KEY）；
    分组与连接若缺它，每条腿会拿到两腿合计（本例互相抵消为 0）。
    """
    path = str(tmp_path / "multi-leg.duckdb")
    conn = duckdb.connect(path, read_only=False)
    try:
        ensure_snapshot_tables(conn)
        conn.executemany(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, portfolio_name, cost_center, account_category,
              asset_class, bond_type, issuer_name, industry_name, rating, currency_code,
              face_value_native, market_value_native, maturity_date, is_issuance_like
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, false)
            """,
            [
                (
                    REPORT_DATE, "ROLL-001", "P1", "CC1", "持有至到期投资",
                    "利率债", "国债", "发行人展期", "政府", "AAA", "USD",
                    Decimal("100"), Decimal("99"), "2026-10-31",
                ),
                (
                    REPORT_DATE, "ROLL-001", "P1", "CC1", "持有至到期投资",
                    "利率债", "国债", "发行人展期", "政府", "AAA", "USD",
                    Decimal("-100"), Decimal("-99"), "2026-12-31",
                ),
            ],
        )
        conn.execute(_BALANCE_FACT_DDL)
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, account_category,
              asset_class, bond_type, issuer_name, industry_name, rating, accounting_basis,
              position_scope, currency_basis, currency_code, face_value_amount,
              market_value_amount, amortized_cost_amount, accrued_interest_amount,
              maturity_date, is_issuance_like
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'asset', 'CNY', 'USD', ?, ?, ?, ?, ?, false)
            """,
            [
                (
                    REPORT_DATE, "ROLL-001", "P1", "CC1", "持有至到期投资",
                    "利率债", "国债", "发行人展期", "政府", "AAA", "AC",
                    Decimal("700"), Decimal("696.5"), Decimal("686"), Decimal("7"),
                    "2026-10-31",
                ),
                (
                    REPORT_DATE, "ROLL-001", "P1", "CC1", "持有至到期投资",
                    "利率债", "国债", "发行人展期", "政府", "AAA", "AC",
                    Decimal("-700"), Decimal("-696.5"), Decimal("-686"), Decimal("-7"),
                    "2026-12-31",
                ),
            ],
        )
    finally:
        conn.close()

    rows = {
        str(row["maturity_date"]): row
        for row in BondAnalyticsRepository(path).load_snapshot_rows(REPORT_DATE)
        if row["instrument_code"] == "ROLL-001"
    }

    assert set(rows) == {"2026-10-31", "2026-12-31"}
    assert rows["2026-10-31"]["market_value_cny"] == Decimal("696.5")
    assert rows["2026-10-31"]["face_value_cny"] == Decimal("700")
    assert rows["2026-12-31"]["market_value_cny"] == Decimal("-696.5")
    assert rows["2026-12-31"]["face_value_cny"] == Decimal("-700")
    assert rows["2026-10-31"]["accounting_basis"] == "AC"


def test_load_snapshot_rows_nulls_accounting_basis_when_dual_books_disagree(tmp_path):
    """同键双账簿（仅 accounting_basis 不同）合入一组：金额求和，basis 不再跨腿任取一。"""
    from tests.test_bond_analytics_materialize_flow import (
        _seed_bond_snapshot_rows,
        _seed_formal_zqtz_balance_for_cb001,
    )

    path = str(tmp_path / "dual-book-basis.duckdb")
    _seed_bond_snapshot_rows(path)
    _seed_formal_zqtz_balance_for_cb001(
        path, market_value_amount=Decimal("1900"), accounting_basis="FVOCI"
    )
    _seed_formal_zqtz_balance_for_cb001(
        path, market_value_amount=Decimal("1901"), accounting_basis="AC"
    )

    cb001_rows = [
        row
        for row in BondAnalyticsRepository(path).load_snapshot_rows(REPORT_DATE)
        if row["instrument_code"] == "CB-001"
    ]

    assert len(cb001_rows) == 1
    assert cb001_rows[0]["market_value_cny"] == Decimal("3801")
    assert cb001_rows[0]["accounting_basis"] is None


def test_invalidate_report_date_facts_removes_only_target_bond_and_risk_rows(tmp_path):
    path = str(tmp_path / "target-date-invalidation.duckdb")
    repo = BondAnalyticsRepository(path)
    other_report_date = "2026-02-28"

    with repository_task_write_scope("backend.app.tasks.bond_analytics_repo_test"):
        repo.replace_bond_analytics_rows(
            report_date=REPORT_DATE,
            rows=[_analytics_row(REPORT_DATE)],
        )
        repo.replace_bond_analytics_rows(
            report_date=other_report_date,
            rows=[_analytics_row(other_report_date)],
        )

    conn = duckdb.connect(path, read_only=False)
    try:
        conn.executemany(
            "insert into fact_formal_risk_tensor_daily (report_date) values (?)",
            [(REPORT_DATE,), (other_report_date,)],
        )
    finally:
        conn.close()

    with repository_task_write_scope("backend.app.tasks.bond_analytics_repo_test"):
        repo.invalidate_report_date_facts(report_date=REPORT_DATE)

    assert repo.fetch_bond_analytics_rows(report_date=REPORT_DATE) == []
    assert len(repo.fetch_bond_analytics_rows(report_date=other_report_date)) == 1
    conn = duckdb.connect(path, read_only=True)
    try:
        risk_rows = conn.execute(
            "select report_date from fact_formal_risk_tensor_daily order by report_date"
        ).fetchall()
    finally:
        conn.close()
    assert risk_rows == [(other_report_date,)]


def test_fetch_bond_analytics_treats_missing_legacy_value_date_column_as_null(tmp_path):
    path = str(tmp_path / "legacy.duckdb")
    conn = duckdb.connect(path, read_only=False)
    try:
        legacy_columns = [
            column
            for column in _ANALYTICS_COLUMNS
            if column
            not in {
                "value_date",
                "interest_payment_frequency_fallback_used",
                "coupon_rate_input_status",
                "ytm_input_status",
                "duration_quality_flag",
            }
        ]
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

    assert (
        repo.fetch_bond_analytics_rows(report_date=REPORT_DATE)[0][
            "interest_payment_frequency_fallback_used"
        ]
        is None
    )
    assert (
        repo.fetch_bond_analytics_rows_for_dates(report_dates=[REPORT_DATE])[REPORT_DATE][0][
            "interest_payment_frequency_fallback_used"
        ]
        is None
    )
    for field_name in (
        "coupon_rate_input_status",
        "ytm_input_status",
        "duration_quality_flag",
    ):
        assert repo.fetch_bond_analytics_rows(report_date=REPORT_DATE)[0][field_name] is None
        assert (
            repo.fetch_bond_analytics_rows_for_dates(report_dates=[REPORT_DATE])[
                REPORT_DATE
            ][0][field_name]
            is None
        )



def test_v35_upgrades_pre_value_date_fact_before_replace_and_reads_date(tmp_path):
    path = str(tmp_path / "pre-v35.duckdb")
    conn = duckdb.connect(path, read_only=False)
    try:
        legacy_columns = [
            column
            for column in _ANALYTICS_COLUMNS
            if column not in {"value_date", "interest_payment_frequency_fallback_used"}
        ]
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


def test_v37_adds_payment_frequency_fallback_provenance_without_backfilling_unknown(tmp_path):
    path = str(tmp_path / "pre-v37.duckdb")
    conn = duckdb.connect(path, read_only=False)
    try:
        legacy_columns = [
            column
            for column in _ANALYTICS_COLUMNS
            if column != "interest_payment_frequency_fallback_used"
        ]
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
            [REPORT_DATE, "LEGACY-PROVENANCE"],
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
            [(version, "already applied") for version in range(1, 37)],
        )

        apply_pending_migrations_on_connection(conn)
        migration_row = conn.execute(
            "select description from _schema_migrations where version = 37"
        ).fetchone()
        column = conn.execute(
            """
            select data_type
            from information_schema.columns
            where table_schema = 'main'
              and table_name = 'fact_formal_bond_analytics_daily'
              and column_name = 'interest_payment_frequency_fallback_used'
            """
        ).fetchone()
        legacy_value = conn.execute(
            """
            select interest_payment_frequency_fallback_used
            from fact_formal_bond_analytics_daily
            where instrument_code = 'LEGACY-PROVENANCE'
            """
        ).fetchone()
    finally:
        conn.close()

    assert migration_row == ("Preserve bond payment-frequency fallback provenance",)
    assert column == ("BOOLEAN",)
    assert legacy_value == (None,)


def test_engine_repo_risk_chain_preserves_frequency_fallback_scale(tmp_path):
    report_day = date.fromisoformat(REPORT_DATE)
    analytics_row = compute_bond_analytics_rows(
        [
            {
                "report_date": report_day,
                "instrument_code": "BOND-FIXED-FALLBACK",
                "currency_code": "CNY",
                "face_value_native": Decimal("100"),
                "market_value_native": Decimal("90"),
                "coupon_rate": Decimal("3"),
                "ytm_value": Decimal("3.5"),
                "maturity_date": date(2027, 3, 31),
                "interest_mode": "fixed",
                "is_issuance_like": False,
            }
        ],
        report_day,
    )[0]
    repo = BondAnalyticsRepository(str(tmp_path / "provenance.duckdb"))
    with repository_task_write_scope("backend.app.tasks.bond_analytics_repo_test"):
        repo.replace_bond_analytics_rows(report_date=REPORT_DATE, rows=[analytics_row])

    formal_rows = repo.fetch_bond_analytics_rows(report_date=REPORT_DATE)
    tensor = compute_portfolio_risk_tensor(formal_rows, report_day)

    assert formal_rows[0]["interest_payment_frequency_fallback_used"] is True
    assert tensor.payment_frequency_fallback_count == 1
    assert tensor.payment_frequency_fallback_market_value == Decimal("90")


def test_fetch_dashboard_headline_kpis_returns_null_amounts_for_a_no_evidence_date(tmp_path):
    """A report_date with zero fact rows must not collapse total_market_value /
    unrealized_pnl / weighted_coupon / total_dv01 into a real Decimal("0") (缺失≠0);
    another date in the same fact table carries real rows, proving the null is keyed
    off evidence_rows for *that* date rather than "table missing" alone.
    """
    repo = BondAnalyticsRepository(str(tmp_path / "headline-no-evidence.duckdb"))
    with repository_task_write_scope("backend.app.tasks.bond_analytics_repo_test"):
        repo.replace_bond_analytics_rows(report_date=REPORT_DATE, rows=[_analytics_row()])

    no_evidence_date = "2026-04-30"
    empty = repo.fetch_dashboard_headline_kpis(no_evidence_date)["current"]
    assert empty["bond_count"] == 0
    assert empty["total_market_value"] is None
    assert empty["unrealized_pnl"] is None
    assert empty["weighted_coupon"] is None
    assert empty["total_dv01"] is None
    assert empty["weighted_ytm"] is None
    assert empty["weighted_duration"] is None
    assert empty["credit_spread_median"] is None

    with_evidence = repo.fetch_dashboard_headline_kpis(REPORT_DATE)["current"]
    assert with_evidence["bond_count"] == 1
    assert with_evidence["total_market_value"] is not None
    assert with_evidence["total_market_value"] > 0


def test_fetch_dashboard_maturity_structure_uses_full_one_year_boundary(tmp_path):
    path = str(tmp_path / "maturity-structure.duckdb")
    conn = duckdb.connect(path, read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              instrument_code varchar,
              bond_type varchar,
              maturity_date date,
              years_to_maturity decimal(18, 8),
              market_value decimal(18, 2)
            )
            """
        )
        maturity_days = [90, 91, 100, 101, 365, 366]
        conn.executemany(
            """
            insert into fact_formal_bond_analytics_daily
              (report_date, instrument_code, bond_type, maturity_date, years_to_maturity, market_value)
            values (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    REPORT_DATE,
                    f"BOND-{days}D",
                    "国债",
                    date.fromisoformat(REPORT_DATE) + timedelta(days=days),
                    Decimal(days) / Decimal("365"),
                    Decimal("100"),
                )
                for days in maturity_days
            ],
        )
    finally:
        conn.close()

    rows = BondAnalyticsRepository(path).fetch_dashboard_maturity_structure(REPORT_DATE)
    buckets = {row["maturity_bucket"]: row for row in rows}

    assert buckets["31-90天"]["bond_count"] == 1
    assert buckets["91天-1年"]["bond_count"] == 4
    assert buckets["91天-1年"]["total_market_value"] == Decimal("400.00")
    assert buckets["1-3年"]["bond_count"] == 1


def test_fetch_business_type_metrics_passes_formal_negative_decimal_ytm_through(tmp_path):
    """正式事实的 ytm 已由 engine 归一为小数（含合法负收益率）：−0.005 原样进入加权，
    不被读侧 `>1 and <=100` 启发式改写，也不被当作脏值剔除。"""
    path = str(tmp_path / "negative-decimal-ytm.duckdb")
    conn = duckdb.connect(path, read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              instrument_code varchar,
              bond_type varchar,
              market_value decimal(24, 8),
              ytm decimal(18, 8),
              modified_duration decimal(18, 8)
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_bond_analytics_daily values (?, ?, ?, ?, ?, ?)",
            [
                (REPORT_DATE, "BOND-POS", "gov", Decimal("100"), Decimal("0.03"), Decimal("2")),
                (REPORT_DATE, "BOND-NEG", "gov", Decimal("100"), Decimal("-0.005"), Decimal("2")),
            ],
        )
    finally:
        conn.close()

    rows = BondAnalyticsRepository(path).fetch_business_type_metrics(REPORT_DATE)

    assert [row["name"] for row in rows] == ["gov"]
    # (0.03 * 100 + −0.005 * 100) / 200
    assert float(rows[0]["weighted_avg_ytm"]) == pytest.approx(0.0125)
    assert float(rows[0]["weighted_avg_ytm_coverage_ratio"]) == pytest.approx(1.0)
