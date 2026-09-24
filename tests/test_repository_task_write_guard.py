from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from backend.app.repositories.cffex_member_rank_repo import (
    CffexMemberRankRow,
    replace_member_rank_rows,
)
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.news_warehouse_repo import (
    ensure_news_warehouse_schema,
    upsert_news_event,
)

ROOT = Path(__file__).resolve().parents[1]
SERVICES_DIR = ROOT / "backend" / "app" / "services"

# Write SQL must live in repositories/tasks so `require_repository_task_write_scope`
# can gate it; a service embedding these keywords bypasses that guard entirely.
SERVICE_WRITE_SQL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("insert into", r"\binsert\s+(?:or\s+\w+\s+)?into\b"),
    ("delete from", r"\bdelete\s+from\b"),
    ("update ... set", r"\bupdate\s+[\"'`]?[a-z_][a-z0-9_.]*[\"'`]?\s+set\b"),
    ("create table", r"\bcreate\s+(?:or\s+replace\s+)?(?:temp(?:orary)?\s+)?table\b"),
    ("create view", r"\bcreate\s+(?:or\s+replace\s+)?view\b"),
    ("drop table/view", r"\bdrop\s+(?:table|view)\b"),
    ("truncate table", r"\btruncate\s+table\b"),
    ("alter table", r"\balter\s+table\b"),
)

# Escape hatch for prose/log literals that legitimately read like write SQL.
# Entries are ``"<path relative to repo root>::<pattern label>"``.
SERVICE_WRITE_SQL_ALLOWLIST: frozenset[str] = frozenset()


def _service_sources() -> list[Path]:
    return sorted(path for path in SERVICES_DIR.rglob("*.py") if path.is_file())


def _string_literals(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(lineno, value)`` for every string literal, so comments cannot trip the scan."""
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def _write_sql_literal_violations(text: str) -> list[tuple[str, int, str]]:
    violations: list[tuple[str, int, str]] = []
    for lineno, literal in _string_literals(text):
        for label, pattern in SERVICE_WRITE_SQL_PATTERNS:
            match = re.search(pattern, literal, flags=re.IGNORECASE)
            if match is not None:
                violations.append((label, lineno, match.group(0)))
    return violations


def test_service_layer_embeds_no_write_sql_keywords() -> None:
    violations: list[str] = []
    for path in _service_sources():
        relative = path.relative_to(ROOT).as_posix()
        for label, lineno, snippet in _write_sql_literal_violations(
            path.read_text(encoding="utf-8-sig")
        ):
            if f"{relative}::{label}" in SERVICE_WRITE_SQL_ALLOWLIST:
                continue
            violations.append(f"{relative}:{lineno}: {label} -> {snippet!r}")
    assert not violations, (
        "Write SQL must live in backend/app/repositories or backend/app/tasks so the "
        "repository task write scope can gate it:\n" + "\n".join(violations)
    )


def test_service_write_sql_scan_detects_each_keyword_and_ignores_comments() -> None:
    detected = {
        label
        for label, _lineno, _snippet in _write_sql_literal_violations(
            '''
"""Docstring without SQL."""
# delete from commented_table
A = "insert into t values (?)"
B = "insert or replace into t values (?)"
C = "delete from t where id = ?"
D = "update t set c = 1"
E = "create table if not exists t (a integer)"
F = "create or replace view v as select 1"
G = "drop table t"
H = "truncate table t"
I = "alter table t add column c integer"
J = "select * from t where id = ?"
'''
        )
    }
    assert detected == {label for label, _pattern in SERVICE_WRITE_SQL_PATTERNS}
    assert _write_sql_literal_violations("# delete from commented_table\nX = 1\n") == []
    assert _write_sql_literal_violations('X = "select * from t"\n') == []


def test_pnl_precompute_writer_does_not_swallow_duckdb_open_error(tmp_path, monkeypatch) -> None:
    from backend.app.repositories import pnl_repo as pnl_repo_module
    from backend.app.repositories.pnl_repo import PnlRepository
    from backend.app.repositories.task_write_guard import repository_task_write_scope

    duckdb_error = duckdb.IOException

    def fail_connect(*_args, **_kwargs):
        raise duckdb_error("Cannot open database file")

    monkeypatch.setattr(pnl_repo_module.duckdb, "connect", fail_connect)

    with repository_task_write_scope("backend.app.tasks.pnl_precompute_test"):
        with pytest.raises(RuntimeError, match="Formal pnl storage is unavailable"):
            PnlRepository(str(tmp_path / "blocked.duckdb")).replace_pnl_by_business_precompute(
                year=2026,
                as_of_date="2026-06-30",
                records=[],
            )


def test_high_risk_repository_writers_require_task_write_scope(tmp_path) -> None:
    from backend.app.repositories.task_write_guard import repository_task_write_scope

    db = tmp_path / "guard.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        ensure_news_warehouse_schema(conn)

        with pytest.raises(PermissionError, match="task write scope"):
            upsert_news_event(
                conn,
                source="tushare_news",
                source_kind="news",
                title="blocked",
                url=None,
                content=None,
                summary="blocked outside task",
                pub_time_iso="2026-04-21T10:00:00+00:00",
                extra={},
            )

        row = CffexMemberRankRow(
            trade_date="2026-04-21",
            contract="T.CFE",
            product_code="T",
            exchange="CFFEX",
            member_name="Member A",
            source_vendor="choice",
        )
        with pytest.raises(PermissionError, match="task write scope"):
            replace_member_rank_rows(conn, [row])

        with repository_task_write_scope("backend.app.tasks.repository_guard_test"):
            assert (
                upsert_news_event(
                    conn,
                    source="tushare_news",
                    source_kind="news",
                    title="allowed",
                    url=None,
                    content=None,
                    summary="allowed inside task",
                    pub_time_iso="2026-04-21T11:00:00+00:00",
                    extra={},
                )
                is True
            )
            assert replace_member_rank_rows(conn, [row]) == 1
    finally:
        conn.close()


def test_cffex_member_rank_replace_rolls_back_delete_when_insert_fails(tmp_path) -> None:
    from backend.app.repositories.task_write_guard import repository_task_write_scope

    db = tmp_path / "cffex-atomic-replace.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    old_row = CffexMemberRankRow(
        trade_date="2026-04-21",
        contract="T.CFE",
        product_code="T",
        exchange="CFFEX",
        member_name="Member A",
        source_vendor="choice",
        volume=100.0,
    )
    duplicate_new_rows = [
        CffexMemberRankRow(
            trade_date="2026-04-21",
            contract="T.CFE",
            product_code="T",
            exchange="CFFEX",
            member_name="Member A",
            source_vendor="choice",
            volume=200.0 + index,
        )
        for index in range(2)
    ]
    try:
        with repository_task_write_scope("backend.app.tasks.cffex_atomic_replace_test"):
            assert replace_member_rank_rows(conn, [old_row]) == 1
            with pytest.raises(duckdb.Error):
                replace_member_rank_rows(conn, duplicate_new_rows)

        assert conn.execute(
            """
            select member_name, volume
            from fact_cffex_member_rank_daily
            where trade_date = '2026-04-21'
              and contract = 'T.CFE'
              and source_vendor = 'choice'
            """
        ).fetchall() == [("Member A", 100.0)]
    finally:
        conn.close()


def test_formal_repository_replace_writers_require_task_write_scope(tmp_path) -> None:
    from backend.app.core_finance.risk_tensor import PortfolioRiskTensor
    from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
    from backend.app.repositories.pnl_repo import PnlRepository
    from backend.app.repositories.risk_tensor_repo import RiskTensorRepository
    from backend.app.repositories.snapshot_repo import (
        delete_tyw_snapshots_for_batches,
        delete_tyw_snapshots_for_report_dates,
        delete_zqtz_snapshots_for_batches,
        delete_zqtz_snapshots_for_report_dates,
        replace_tyw_snapshot_rows,
        replace_zqtz_snapshot_rows,
    )
    from backend.app.repositories.task_write_guard import repository_task_write_scope
    from backend.app.repositories.yield_curve_repo import YieldCurveRepository
    from backend.app.schemas.yield_curve import YieldCurvePoint, YieldCurveSnapshot

    duckdb_path = tmp_path / "formal-writers.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)

    with pytest.raises(PermissionError, match="task write scope"):
        BalanceAnalysisRepository(str(duckdb_path)).replace_formal_balance_rows(
            report_date="2026-03-31",
            zqtz_rows=[],
            tyw_rows=[],
        )

    with pytest.raises(PermissionError, match="task write scope"):
        replace_zqtz_snapshot_rows(
            conn,
            [],
            ingest_batch_ids=[],
        )

    with pytest.raises(PermissionError, match="task write scope"):
        replace_tyw_snapshot_rows(
            conn,
            [],
            ingest_batch_ids=[],
        )

    for writer in (
        lambda: delete_zqtz_snapshots_for_batches(conn, ["ib"]),
        lambda: delete_zqtz_snapshots_for_report_dates(conn, ["2026-03-31"]),
        lambda: delete_tyw_snapshots_for_batches(conn, ["ib"]),
        lambda: delete_tyw_snapshots_for_report_dates(conn, ["2026-03-31"]),
    ):
        with pytest.raises(PermissionError, match="task write scope"):
            writer()

    with pytest.raises(PermissionError, match="task write scope"):
        BondAnalyticsRepository(str(duckdb_path)).replace_bond_analytics_rows(
            report_date="2026-03-31",
            rows=[],
        )

    curve_snapshot = YieldCurveSnapshot(
        curve_type="treasury",
        trade_date="2026-03-31",
        points=[YieldCurvePoint("1Y", "1.50")],
        vendor_name="choice",
        vendor_version="vv_guard",
        source_version="sv_guard",
    )
    with pytest.raises(PermissionError, match="task write scope"):
        YieldCurveRepository(str(duckdb_path)).replace_curve_snapshots(
            trade_date="2026-03-31",
            snapshots=[curve_snapshot],
            rule_version="rv_guard",
        )

    with pytest.raises(PermissionError, match="task write scope"):
        PnlRepository(str(duckdb_path)).replace_pnl_by_business_precompute(
            year=2026,
            as_of_date="2026-03-31",
            records=[],
        )

    tensor = PortfolioRiskTensor(
        report_date=curve_snapshot.trade_date,
        portfolio_dv01="0",
        regulatory_dv01="0",
        krd_1y="0",
        krd_3y="0",
        krd_5y="0",
        krd_7y="0",
        krd_10y="0",
        krd_30y="0",
        cs01="0",
        portfolio_convexity="0",
        portfolio_modified_duration="0",
        issuer_concentration_hhi="0",
        issuer_top5_weight="0",
        asset_cashflow_30d="0",
        asset_cashflow_90d="0",
        liability_cashflow_30d="0",
        liability_cashflow_90d="0",
        liquidity_gap_30d="0",
        liquidity_gap_90d="0",
        liquidity_gap_30d_ratio="0",
        total_market_value="0",
        bond_count=0,
        quality_flag="warning",
        warnings=[],
    )
    with pytest.raises(PermissionError, match="task write scope"):
        RiskTensorRepository(str(duckdb_path)).replace_risk_tensor_row(
            report_date="2026-03-31",
            tensor=tensor,
            source_version="sv_guard",
            upstream_source_version="sv_guard",
            upstream_rule_version="rv_guard",
            upstream_cache_version="cv_guard",
            liability_source_version="sv_guard",
            liability_rule_version="rv_guard",
            rule_version="rv_guard",
            cache_version="cv_guard",
            trace_id="tr_guard",
        )

    with repository_task_write_scope("backend.app.tasks.repository_guard_test"):
        BalanceAnalysisRepository(str(duckdb_path)).replace_formal_balance_rows(
            report_date="2026-03-31",
            zqtz_rows=[],
            tyw_rows=[],
        )
        assert (
            replace_zqtz_snapshot_rows(
                conn,
                [],
                ingest_batch_ids=[],
            )
            == 0
        )
        assert (
            replace_tyw_snapshot_rows(
                conn,
                [],
                ingest_batch_ids=[],
            )
            == 0
        )
        delete_zqtz_snapshots_for_batches(conn, ["ib"])
        delete_zqtz_snapshots_for_report_dates(conn, ["2026-03-31"])
        delete_tyw_snapshots_for_batches(conn, ["ib"])
        delete_tyw_snapshots_for_report_dates(conn, ["2026-03-31"])
        YieldCurveRepository(str(duckdb_path)).replace_curve_snapshots(
            trade_date="2026-03-31",
            snapshots=[curve_snapshot],
            rule_version="rv_guard",
        )
        BondAnalyticsRepository(str(duckdb_path)).replace_bond_analytics_rows(
            report_date="2026-03-31",
            rows=[],
        )
        PnlRepository(str(duckdb_path)).replace_pnl_by_business_precompute(
            year=2026,
            as_of_date="2026-03-31",
            records=[],
        )
        RiskTensorRepository(str(duckdb_path)).replace_risk_tensor_row(
            report_date="2026-03-31",
            tensor=tensor,
            source_version="sv_guard",
            upstream_source_version="sv_guard",
            upstream_rule_version="rv_guard",
            upstream_cache_version="cv_guard",
            liability_source_version="sv_guard",
            liability_rule_version="rv_guard",
            rule_version="rv_guard",
            cache_version="cv_guard",
            trace_id="tr_guard",
        )
    conn.close()


def test_external_std_repository_writers_require_task_write_scope(tmp_path) -> None:
    from datetime import UTC, datetime

    from backend.app.repositories.external_std_calendar_repo import (
        StdSupplyAuctionCalendarRow,
        upsert_supply_auction_calendar_rows,
    )
    from backend.app.repositories.external_std_macro_repo import (
        StdExternalMacroDailyRow,
        upsert_macro_daily_rows,
    )
    from backend.app.repositories.task_write_guard import repository_task_write_scope

    conn = duckdb.connect(str(tmp_path / "external-std.duckdb"), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        now = datetime.now(UTC).replace(microsecond=0)
        macro_row = StdExternalMacroDailyRow(
            series_id="tushare.macro.guard",
            vendor_name="tushare",
            domain="macro",
            trade_date="2026-04-21",
            value_numeric=1.0,
            frequency="monthly",
            unit="pct",
            source_version="sv_guard",
            vendor_version="vv_guard",
            rule_version="rv_guard",
            ingest_batch_id="ib_guard",
            raw_zone_path="data/raw/guard.json",
            created_at=now,
        )
        calendar_row = StdSupplyAuctionCalendarRow(
            series_id="research.calendar.guard",
            event_id="evt_guard",
            vendor_name="choice",
            source_family="research_calendar",
            domain="macro",
            event_date="2026-04-21",
            event_kind="auction",
            title="Guard auction",
            issuer=None,
            market=None,
            instrument_type=None,
            term_label=None,
            amount_numeric=None,
            amount_unit=None,
            currency=None,
            status=None,
            severity=None,
            headline_text=None,
            headline_url=None,
            headline_published_at=None,
            source_version="sv_guard",
            vendor_version="vv_guard",
            rule_version="rv_guard",
            ingest_batch_id="ib_guard",
            created_at=now,
        )

        with pytest.raises(PermissionError, match="task write scope"):
            upsert_macro_daily_rows(conn, [macro_row])
        with pytest.raises(PermissionError, match="task write scope"):
            upsert_supply_auction_calendar_rows(conn, [calendar_row])

        with repository_task_write_scope("backend.app.tasks.repository_guard_test"):
            assert upsert_macro_daily_rows(conn, [macro_row]) == 1
            assert upsert_supply_auction_calendar_rows(conn, [calendar_row]) == 1
    finally:
        conn.close()


def test_external_data_catalog_register_requires_task_write_scope(tmp_path) -> None:
    from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
    from backend.app.repositories.task_write_guard import repository_task_write_scope
    from backend.app.schemas.external_data import ExternalDataCatalogEntry

    entry = ExternalDataCatalogEntry(
        series_id="guard.series",
        series_name="Guard series",
        vendor_name="tushare",
        source_family="tushare_macro",
        domain="macro",
        frequency="monthly",
        unit="pct",
        refresh_tier="on_demand",
        fetch_mode="batch_materialize",
        raw_zone_path="data/raw/guard.json",
        standardized_table="std_external_macro_daily",
        view_name="vw_external_macro_daily",
        access_path="select 1",
        catalog_version="guard.v1",
        created_at="2026-04-21T00:00:00+00:00",
    )
    conn = duckdb.connect(str(tmp_path / "catalog-guard.duckdb"), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        repo = ExternalDataCatalogRepository(conn=conn)
        with pytest.raises(PermissionError, match="task write scope"):
            repo.register(entry)
        with repository_task_write_scope("backend.app.tasks.repository_guard_test"):
            repo.register(entry)
        assert repo.get_by_series_id("guard.series") is not None
    finally:
        conn.close()


def test_ledger_classification_backfill_writer_requires_task_scope(tmp_path) -> None:
    from backend.app.repositories.ledger_import_repo import LedgerImportRepository

    with pytest.raises(PermissionError, match="task write scope"):
        LedgerImportRepository(str(tmp_path / "ledger.duckdb")).attest_classification_rule_versions(
            batch_ids=[1],
            from_rule_versions={1: "position_key_contract_v1"},
            target_rule_version="rv_ledger_classification_v2",
            expected_immutable_evidence_digest="not-reached",
        )
