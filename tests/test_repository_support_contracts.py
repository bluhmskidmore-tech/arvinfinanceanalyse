from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from tests.helpers import load_module


def test_postgres_mask_dsn_username_password():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract",
        "backend/app/repositories/postgres_repo.py",
    )
    dsn = "postgresql://alice:secret@db.example.com:5432/moss"
    masked = postgres_module._mask_dsn(dsn)
    assert masked == "postgresql://alice:***@db.example.com:5432/moss"
    assert "secret" not in masked
    assert "db.example.com:5432" in masked
    assert masked.endswith("/moss")


def test_postgres_mask_dsn_password_only():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_b",
        "backend/app/repositories/postgres_repo.py",
    )
    dsn = "postgresql://:onlypass@10.0.0.5:5432/appdb"
    masked = postgres_module._mask_dsn(dsn)
    assert masked == "postgresql://***@10.0.0.5:5432/appdb"
    assert "onlypass" not in masked


def test_postgres_mask_dsn_unchanged_without_hostname():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_c",
        "backend/app/repositories/postgres_repo.py",
    )
    bare = "postgresql:///moss"
    assert postgres_module._mask_dsn(bare) == bare
    no_scheme = "not-a-url-at-all"
    assert postgres_module._mask_dsn(no_scheme) == no_scheme


def test_missing_bootstrap_tables_order_and_contents():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_d",
        "backend/app/repositories/postgres_repo.py",
    )
    present = {"public.source_version_registry", "public.cache_manifest"}

    class FakeCursor:
        def execute(self, query: str, params=None) -> None:
            self._params = tuple(params or ())

        def fetchone(self):
            key = self._params[0]
            if key in present:
                return (key,)
            return (None,)

    cursor = FakeCursor()
    missing = postgres_module._missing_bootstrap_tables(cursor)
    assert missing == ["rule_version_registry", "cache_build_run", "job_run_state"]


def test_postgres_healthcheck_psycopg_unavailable():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_e",
        "backend/app/repositories/postgres_repo.py",
    )
    with patch.object(postgres_module, "psycopg", None):
        repo = postgres_module.PostgresRepository("postgresql://u:p@127.0.0.1/db")
        result = repo.healthcheck()
    assert result["ok"] is False
    assert result["driver"] == "unavailable"
    assert result["error"] == "psycopg unavailable"


def test_postgres_healthcheck_success_all_bootstrap_visible():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_f",
        "backend/app/repositories/postgres_repo.py",
    )

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query: str, params=None) -> None:
            self._params = tuple(params or ())

        def fetchone(self):
            if self._params == ():
                return (1,)
            return ("public.some_table",)

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    class FakePsycopg:
        @staticmethod
        def connect(dsn: str, *, connect_timeout: float):
            assert connect_timeout == 1.0
            assert "secret" in dsn
            return FakeConnection()

    with patch.object(postgres_module, "psycopg", FakePsycopg):
        repo = postgres_module.PostgresRepository("postgresql://u:secret@127.0.0.1:5432/db")
        result = repo.healthcheck()

    assert result["ok"] is True
    assert result["can_connect"] is True
    assert result["sql_roundtrip"] is True
    assert result["bootstrap_visible"] is True
    assert result["missing_tables"] == []
    assert "secret" not in str(result["dsn"])


def test_postgres_healthcheck_partial_bootstrap():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_g",
        "backend/app/repositories/postgres_repo.py",
    )

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query: str, params=None) -> None:
            self._params = tuple(params or ())

        def fetchone(self):
            if self._params == ():
                return (1,)
            if self._params[0] == "public.source_version_registry":
                return ("public.source_version_registry",)
            return (None,)

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    class FakePsycopg:
        @staticmethod
        def connect(dsn: str, *, connect_timeout: float):
            return FakeConnection()

    with patch.object(postgres_module, "psycopg", FakePsycopg):
        repo = postgres_module.PostgresRepository("postgresql://u:p@h/db")
        result = repo.healthcheck()

    assert result["ok"] is False
    assert result["bootstrap_visible"] is False
    assert result["missing_tables"] == [
        "rule_version_registry",
        "cache_manifest",
        "cache_build_run",
        "job_run_state",
    ]


def test_postgres_healthcheck_connect_exception_message():
    postgres_module = load_module(
        "backend.app.repositories.postgres_support_contract_h",
        "backend/app/repositories/postgres_repo.py",
    )

    class Boom(Exception):
        pass

    class FakePsycopg:
        @staticmethod
        def connect(*args, **kwargs):
            raise Boom("nope")

    with patch.object(postgres_module, "psycopg", FakePsycopg):
        repo = postgres_module.PostgresRepository("postgresql://u:p@127.0.0.1/db")
        result = repo.healthcheck()

    assert result["ok"] is False
    assert "Boom" in str(result["error"])
    assert "nope" in str(result["error"])


def test_redis_healthcheck_parses_host_port_and_success(monkeypatch):
    redis_module = load_module(
        "backend.app.repositories.redis_support_contract",
        "backend/app/repositories/redis_repo.py",
    )
    created: list[tuple] = []

    class _Cm:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_create_connection(address, timeout=0.2):
        created.append((address, timeout))
        return _Cm()

    monkeypatch.setattr(redis_module.socket, "create_connection", fake_create_connection)

    dsn = "redis://cache.internal:6380/0"
    repo = redis_module.RedisRepository(dsn)
    result = repo.healthcheck()

    assert result["ok"] is True
    assert result["dsn"] == dsn
    assert created == [(("cache.internal", 6380), 0.2)]


def test_redis_healthcheck_default_port_6379(monkeypatch):
    redis_module = load_module(
        "backend.app.repositories.redis_support_contract_b",
        "backend/app/repositories/redis_repo.py",
    )
    created: list[tuple] = []

    class _Cm:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_create_connection(address, timeout=0.2):
        created.append((address, timeout))
        return _Cm()

    monkeypatch.setattr(redis_module.socket, "create_connection", fake_create_connection)

    repo = redis_module.RedisRepository("redis://localhost/0")
    assert repo.healthcheck()["ok"] is True
    assert created[0][0] == ("localhost", 6379)


def test_redis_healthcheck_oserror_failure(monkeypatch):
    redis_module = load_module(
        "backend.app.repositories.redis_support_contract_c",
        "backend/app/repositories/redis_repo.py",
    )

    def boom(addr, timeout):
        raise OSError("refused")

    monkeypatch.setattr(redis_module.socket, "create_connection", boom)

    dsn = "redis://127.0.0.1:9/0"
    result = redis_module.RedisRepository(dsn).healthcheck()
    assert result["ok"] is False
    assert result["dsn"] == dsn


def test_duckdb_repository_defaults_and_healthcheck_shape():
    duck_module = load_module(
        "backend.app.repositories.duck_support_contract",
        "backend/app/repositories/duckdb_repo.py",
    )
    repo = duck_module.DuckDBRepository("/data/analytics.duckdb")
    assert repo.read_only is True
    h = repo.healthcheck()
    assert h == {"ok": True, "mode": "read_only", "path": "/data/analytics.duckdb"}


def test_duckdb_healthcheck_ignores_read_only_false_field():
    duck_module = load_module(
        "backend.app.repositories.duck_support_contract_b",
        "backend/app/repositories/duckdb_repo.py",
    )
    repo = duck_module.DuckDBRepository("/tmp/x.duckdb", read_only=False)
    assert repo.read_only is False
    assert repo.healthcheck() == {"ok": True, "mode": "read_only", "path": "/tmp/x.duckdb"}


def test_duckdb_repository_keeps_connections_read_only_for_compat_flag(monkeypatch: pytest.MonkeyPatch):
    duck_module = load_module(
        "backend.app.repositories.duck_support_contract_c",
        "backend/app/repositories/duckdb_repo.py",
    )
    calls: list[tuple[str, object, object | None]] = []

    class FakeConnection:
        def execute(self, query: str, params: list[object]):
            calls.append(("execute", query, tuple(params)))
            return self

        def fetchall(self):
            return [("ok",)]

        def close(self) -> None:
            calls.append(("close", None, None))

    def fake_connect(path: str, *, read_only: bool):
        calls.append(("connect", path, read_only))
        return FakeConnection()

    monkeypatch.setattr(duck_module.duckdb, "connect", fake_connect)

    repo = duck_module.DuckDBRepository("/tmp/compat.duckdb", read_only=False)
    assert repo._fetch_rows("select 1") == [("ok",)]
    assert calls[0] == ("connect", "/tmp/compat.duckdb", True)


def test_duckdb_repository_retries_transient_read_only_open_failure(monkeypatch: pytest.MonkeyPatch):
    duck_module = load_module(
        "backend.app.repositories.duck_support_contract_d",
        "backend/app/repositories/duckdb_repo.py",
    )
    calls: list[tuple[str, object, object | None]] = []

    class FakeConnection:
        def execute(self, query: str, params: list[object]):
            calls.append(("execute", query, tuple(params)))
            return self

        def fetchall(self):
            return [("ok",)]

        def close(self) -> None:
            calls.append(("close", None, None))

    attempts = {"count": 0}

    def fake_connect(path: str, *, read_only: bool):
        attempts["count"] += 1
        calls.append(("connect", path, read_only))
        if attempts["count"] == 1:
            raise OSError("transient wal unavailable")
        return FakeConnection()

    monkeypatch.setattr(duck_module.duckdb, "connect", fake_connect)
    repo = duck_module.DuckDBRepository("/tmp/transient.duckdb", transient_open_retries=2)
    assert repo._fetch_rows("select 1") == [("ok",)]
    assert [call for call in calls if call[0] == "connect"] == [
        ("connect", "/tmp/transient.duckdb", True),
        ("connect", "/tmp/transient.duckdb", True),
    ]


def test_duckdb_guarded_repository_returns_empty_when_read_open_stays_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    duck_module = load_module(
        "backend.app.repositories.duck_support_contract_e",
        "backend/app/repositories/duckdb_repo.py",
    )

    def fake_connect(path: str, *, read_only: bool):
        raise OSError("wal unavailable")

    monkeypatch.setattr(duck_module.duckdb, "connect", fake_connect)
    repo = duck_module.DuckDBRepository("/tmp/optional.duckdb", guard_path_exists=True, transient_open_retries=2)
    assert repo._fetch_rows("select 1") == []
    assert repo._table_exists("optional_table") is False


def test_formal_zqtz_balance_metrics_repository_lists_report_dates(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.formal_zqtz_balance_metrics_repo_contract",
        "backend/app/repositories/formal_zqtz_balance_metrics_repo.py",
    )
    import duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              position_scope varchar,
              currency_basis varchar,
              market_value_amount decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            ('2025-12-31', 'asset', 'CNY', 1),
            ('2025-12-31', 'asset', 'native', 1),
            ('2025-11-30', 'asset', 'CNY', 1)
            """
        )
    finally:
        conn.close()

    repo = repo_module.FormalZqtzBalanceMetricsRepository(str(db_path))
    assert repo.list_report_dates() == ["2025-12-31", "2025-11-30"]
    assert repo.list_report_dates(currency_basis="native") == ["2025-12-31"]


def test_liability_analytics_repository_lists_union_report_dates(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.liability_analytics_repo_contract",
        "backend/app/repositories/liability_analytics_repo.py",
    )
    import duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("create table zqtz_bond_daily_snapshot (report_date date)")
        conn.execute("create table tyw_interbank_daily_snapshot (report_date date)")
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot values
            ('2025-12-31'), ('2025-11-30')
            """
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot values
            ('2025-12-31'), ('2025-10-31')
            """
        )
    finally:
        conn.close()

    repo = repo_module.LiabilityAnalyticsRepository(str(db_path))
    assert repo.list_report_dates() == ["2025-12-31", "2025-11-30", "2025-10-31"]


def test_liability_analytics_batch_rows_match_single_date_rows(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.liability_analytics_repo_batch_contract",
        "backend/app/repositories/liability_analytics_repo.py",
    )
    import duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table zqtz_bond_daily_snapshot (
              report_date date,
              instrument_code varchar,
              instrument_name varchar,
              asset_class varchar,
              bond_type varchar,
              is_issuance_like boolean,
              face_value_native decimal(24, 8),
              market_value_native decimal(24, 8),
              amortized_cost_native decimal(24, 8),
              coupon_rate decimal(18, 8),
              ytm_value decimal(18, 8),
              maturity_date date,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            create table tyw_interbank_daily_snapshot (
              report_date date,
              position_id varchar,
              product_type varchar,
              position_side varchar,
              counterparty_name varchar,
              core_customer_type varchar,
              principal_native decimal(24, 8),
              funding_cost_rate decimal(18, 8),
              maturity_date date,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot values
            ('2025-12-31', 'Z1', 'bond 1', 'rate', 'gov', true, 100, 101, 99, 0.025, 0.026, '2030-01-01', 'sv_z_1', 'rv_z_1'),
            ('2025-11-30', 'Z2', 'bond 2', 'credit', 'corp', false, 200, 202, 198, 0.030, 0.031, '2031-01-01', 'sv_z_2', 'rv_z_2')
            """
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot values
            ('2025-12-31', 'T1', 'repo', 'asset side', 'cp a', 'core', 300, 0.020, '2026-01-01', 'sv_t_1', 'rv_t_1'),
            ('2025-11-30', 'T2', 'repo', 'liability side', 'cp b', 'non-core', 400, 0.022, '2026-02-01', 'sv_t_2', 'rv_t_2')
            """
        )
    finally:
        conn.close()

    repo = repo_module.LiabilityAnalyticsRepository(str(db_path))
    dates = ["2025-12-31", "2025-11-30"]
    zqtz_batch = repo.fetch_zqtz_rows_for_dates(dates)
    tyw_batch = repo.fetch_tyw_rows_for_dates(dates)

    assert zqtz_batch == {d: repo.fetch_zqtz_rows(d) for d in dates}
    assert tyw_batch == {d: repo.fetch_tyw_rows(d) for d in dates}
    assert tyw_batch["2025-12-31"][0]["is_asset_side"] is True
    assert tyw_batch["2025-11-30"][0]["is_asset_side"] is False


def test_liability_analytics_yield_batch_rows_preserve_nim_calculation(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.liability_analytics_repo_yield_batch_contract",
        "backend/app/repositories/liability_analytics_repo.py",
    )
    compute_module = load_module(
        "backend.app.core_finance.liability_analytics_compat_yield_batch_contract",
        "backend/app/core_finance/liability_analytics_compat.py",
    )
    import duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table zqtz_bond_daily_snapshot (
              report_date date,
              instrument_code varchar,
              instrument_name varchar,
              asset_class varchar,
              bond_type varchar,
              is_issuance_like boolean,
              face_value_native decimal(24, 8),
              market_value_native decimal(24, 8),
              amortized_cost_native decimal(24, 8),
              coupon_rate decimal(18, 8),
              ytm_value decimal(18, 8),
              maturity_date date,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            create table tyw_interbank_daily_snapshot (
              report_date date,
              position_id varchar,
              product_type varchar,
              position_side varchar,
              counterparty_name varchar,
              core_customer_type varchar,
              principal_native decimal(24, 8),
              funding_cost_rate decimal(18, 8),
              maturity_date date,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot values
            ('2025-12-31', 'Z1', 'bond 1', '搴旀敹鎶曡祫', 'gov', false, 100, 101, 99, 0.025, 0.026, '2030-01-01', 'sv_z_1', 'rv_z_1'),
            ('2025-12-31', 'Z2', 'cd 1', 'rate', '鍚屼笟瀛樺崟', true, 200, 202, 198, 0.030, 0.031, '2031-01-01', 'sv_z_2', 'rv_z_2')
            """
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot values
            ('2025-12-31', 'T1', 'repo', 'asset side', 'cp a', 'core', 300, 0.020, '2026-01-01', 'sv_t_1', 'rv_t_1'),
            ('2025-12-31', 'T2', 'repo', 'liability side', 'cp b', 'non-core', 400, 0.022, '2026-02-01', 'sv_t_2', 'rv_t_2')
            """
        )
    finally:
        conn.close()

    repo = repo_module.LiabilityAnalyticsRepository(str(db_path))
    full_payload = compute_module.compute_liability_yield_metrics(
        "2025-12-31",
        repo.fetch_zqtz_rows("2025-12-31"),
        repo.fetch_tyw_rows("2025-12-31"),
    )
    yield_payload = compute_module.compute_liability_yield_metrics(
        "2025-12-31",
        repo.fetch_zqtz_yield_rows_for_dates(["2025-12-31"])["2025-12-31"],
        repo.fetch_tyw_yield_rows_for_dates(["2025-12-31"])["2025-12-31"],
    )
    zqtz_combined, tyw_combined = repo.fetch_yield_rows_for_dates(["2025-12-31"])
    combined_payload = compute_module.compute_liability_yield_metrics(
        "2025-12-31",
        zqtz_combined["2025-12-31"],
        tyw_combined["2025-12-31"],
    )

    assert yield_payload["kpi"] == full_payload["kpi"]
    assert combined_payload["kpi"] == full_payload["kpi"]


def test_formal_zqtz_balance_metrics_repo_exposes_combined_formal_overview(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.formal_zqtz_balance_metrics_repo_combined_contract",
        "backend/app/repositories/formal_zqtz_balance_metrics_repo.py",
    )
    import duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              market_value_amount decimal(24, 8),
              amortized_cost_amount decimal(24, 8),
              accrued_interest_amount decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_tyw_balance_daily (
              report_date varchar,
              position_id varchar,
              product_type varchar,
              counterparty_name varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              principal_amount decimal(24, 8),
              accrued_interest_amount decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            ('2025-12-31', 'Z1', 'p', 'c', 'inv', 'acct', 'asset', 'CNY', 100, 100, 0, 'sv_z_1', 'rv_z_1'),
            ('2025-11-30', 'Z2', 'p', 'c', 'inv', 'acct', 'asset', 'CNY', 90, 90, 0, 'sv_z_2', 'rv_z_2')
            """
        )
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily values
            ('2025-12-31', 'T1', 'prod', 'cp', 'inv', 'acct', 'asset', 'CNY', 30, 0, 'sv_t_1', 'rv_t_1'),
            ('2025-10-31', 'T2', 'prod', 'cp', 'inv', 'acct', 'asset', 'CNY', 20, 0, 'sv_t_2', 'rv_t_2')
            """
        )
    finally:
        conn.close()

    repo = repo_module.FormalZqtzBalanceMetricsRepository(str(db_path))
    assert repo.list_formal_overview_report_dates() == ["2025-12-31", "2025-11-30", "2025-10-31"]

    overview = repo.fetch_formal_overview(
        report_date="2025-12-31",
        position_scope="asset",
        currency_basis="CNY",
    )

    assert overview == {
        "report_date": "2025-12-31",
        "position_scope": "asset",
        "currency_basis": "CNY",
        "detail_row_count": 2,
        "summary_row_count": 2,
        "total_market_value_amount": Decimal("130.00000000"),
        "total_amortized_cost_amount": Decimal("130.00000000"),
        "total_accrued_interest_amount": Decimal("0E-8"),
        "asset_total_market_value_amount": Decimal("130.00000000"),
        "liability_total_market_value_amount": 0,
        "asset_total_amortized_cost_amount": Decimal("130.00000000"),
        "liability_total_amortized_cost_amount": 0,
        "asset_total_accrued_interest_amount": Decimal("0E-8"),
        "liability_total_accrued_interest_amount": 0,
        "source_version": "sv_t_1__sv_z_1",
        "rule_version": "rv_t_1__rv_z_1",
    }


def test_formal_zqtz_balance_metrics_batch_history_matches_single_values(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.formal_zqtz_balance_metrics_repo_history_contract",
        "backend/app/repositories/formal_zqtz_balance_metrics_repo.py",
    )
    import duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              market_value_amount decimal(24, 8),
              amortized_cost_amount decimal(24, 8),
              accrued_interest_amount decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_tyw_balance_daily (
              report_date varchar,
              position_id varchar,
              product_type varchar,
              counterparty_name varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              principal_amount decimal(24, 8),
              accrued_interest_amount decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            ('2025-12-31', 'Z1', 'p', 'c', 'inv', 'acct', 'asset', 'CNY', 100, 100, 0, 'sv_z_1', 'rv_z_1'),
            ('2025-11-30', 'Z2', 'p', 'c', 'inv', 'acct', 'asset', 'CNY', 90, 90, 0, 'sv_z_2', 'rv_z_2')
            """
        )
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily values
            ('2025-12-31', 'T1', 'prod', 'cp', 'inv', 'acct', 'asset', 'CNY', 30, 0, 'sv_t_1', 'rv_t_1'),
            ('2025-11-30', 'T2', 'prod', 'cp', 'inv', 'acct', 'asset', 'CNY', 20, 0, 'sv_t_2', 'rv_t_2')
            """
        )
    finally:
        conn.close()

    repo = repo_module.FormalZqtzBalanceMetricsRepository(str(db_path))
    dates = ["2025-12-31", "2025-11-30"]
    history = repo.fetch_formal_overview_history(
        report_dates=dates,
        position_scope="asset",
        currency_basis="CNY",
    )

    assert {d: history[d]["total_market_value_amount"] for d in dates} == {
        d: repo.fetch_formal_overview(
            report_date=d,
            position_scope="asset",
            currency_basis="CNY",
        )["total_market_value_amount"]
        for d in dates
    }


def test_pnl_repository_batch_ytd_sums_match_single_date_sums(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.pnl_repo_batch_contract",
        "backend/app/repositories/pnl_repo.py",
    )
    import duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
              report_date varchar,
              total_pnl decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            create table fact_nonstd_pnl_bridge (
              report_date varchar,
              total_pnl decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
            ('2025-01-31', 10),
            ('2025-02-28', 20),
            ('2025-03-31', 30),
            ('2024-12-31', 999)
            """
        )
        conn.execute(
            """
            insert into fact_nonstd_pnl_bridge values
            ('2025-02-28', 2),
            ('2025-03-31', 3)
            """
        )
    finally:
        conn.close()

    repo = repo_module.PnlRepository(str(db_path))
    dates = ["2025-03-31", "2025-02-28", "2025-01-31"]
    assert repo.sum_formal_total_pnl_through_report_dates(dates) == {
        d: repo.sum_formal_total_pnl_through_report_date(d) for d in dates
    }
    assert repo.sum_nonstd_bridge_total_pnl_through_report_dates(dates) == {
        d: repo.sum_nonstd_bridge_total_pnl_through_report_date(d) for d in dates
    }


def test_bond_analytics_batch_risk_snapshots_match_single_date_snapshots(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.bond_analytics_repo_batch_contract",
        "backend/app/repositories/bond_analytics_repo.py",
    )
    import duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              modified_duration decimal(18, 8),
              market_value decimal(24, 8),
              dv01 decimal(24, 8),
              is_credit boolean,
              years_to_maturity decimal(18, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_bond_analytics_daily values
            ('2025-12-31', 2, 100, 1, false, 3),
            ('2025-12-31', 4, 300, 3, true, 5),
            ('2025-11-30', 1, 200, 2, false, 2)
            """
        )
    finally:
        conn.close()

    repo = repo_module.BondAnalyticsRepository(str(db_path))
    dates = ["2025-12-31", "2025-11-30"]
    snapshots = repo.fetch_risk_overview_snapshots(report_dates=dates)

    assert snapshots == {d: repo.fetch_risk_overview_snapshot(report_date=d) for d in dates}


def test_dashboard_repository_batch_core_metrics_match_single_date_metrics(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.dashboard_repo_batch_contract",
        "backend/app/repositories/dashboard_repo.py",
    )
    import duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              bond_type varchar,
              market_value decimal(24, 8),
              ytm decimal(18, 8)
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_tyw_balance_daily (
              report_date varchar,
              position_id varchar,
              position_side varchar,
              counterparty_name varchar,
              currency_basis varchar,
              principal_amount decimal(24, 8),
              funding_cost_rate decimal(18, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_bond_analytics_daily values
            ('2026-04-30', 'gov', 100, 0.03),
            ('2026-04-30', 'corp', 200, 0.04),
            ('2026-04-29', 'gov', 90, 0.02)
            """
        )
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily values
            ('2026-04-30', 'A1', 'asset side', 'CPA', 'CNY', 300, 2.5),
            ('2026-04-30', 'L1', 'liability side', 'CPL', 'CNY', 400, 3.0),
            ('2026-04-29', 'A2', 'asset side', 'CPA', 'CNY', 250, 2.0),
            ('2026-04-29', 'L2', 'liability side', 'CPL', 'CNY', 350, 2.8)
            """
        )
    finally:
        conn.close()

    repo = repo_module.DashboardRepository(str(db_path))
    dates = ["2026-04-30", "2026-04-29"]

    assert repo.fetch_bond_core_metrics_for_dates(dates) == {
        d: repo.fetch_bond_core_metrics(d) for d in dates
    }
    assert repo.fetch_tyw_core_metrics_for_dates(dates, asset_side=True) == {
        d: repo.fetch_tyw_core_metrics(d, asset_side=True) for d in dates
    }
    assert repo.fetch_tyw_core_metrics_for_dates(dates, asset_side=False) == {
        d: repo.fetch_tyw_core_metrics(d, asset_side=False) for d in dates
    }


def test_dashboard_repository_batch_bond_metrics_falls_back_per_missing_zqtz_date(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.dashboard_repo_batch_fallback_contract",
        "backend/app/repositories/dashboard_repo.py",
    )
    import duckdb

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              bond_type varchar,
              market_value decimal(24, 8),
              ytm decimal(18, 8)
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              bond_type varchar,
              position_scope varchar,
              currency_basis varchar,
              market_value_amount decimal(24, 8),
              ytm_value decimal(18, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_bond_analytics_daily values
            ('2026-04-30', 'analytics-gov', 100, 0.03),
            ('2026-04-30', 'analytics-corp', 300, 4.0)
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            ('2026-04-29', 'formal-gov', 'asset', 'CNY', 200, 3.0)
            """
        )
    finally:
        conn.close()

    repo = repo_module.DashboardRepository(str(db_path))
    results = repo.fetch_bond_core_metrics_for_dates(["2026-04-30", "2026-04-29"])

    current_total, current_yield, current_top, current_has_rows = results["2026-04-30"]
    assert current_has_rows is True
    assert current_total == Decimal("400.00000000")
    assert current_yield == Decimal("0.037500000000")
    assert current_top[0][0] == "analytics-corp"

    previous_total, previous_yield, previous_top, previous_has_rows = results["2026-04-29"]
    assert previous_has_rows is True
    assert previous_total == Decimal("200.00000000")
    assert previous_yield == Decimal("0.030000000000")
    assert previous_top[0][0] == "formal-gov"
