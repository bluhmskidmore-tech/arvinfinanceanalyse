from __future__ import annotations

import duckdb
import pytest

from backend.app.repositories.cffex_member_rank_repo import (
    CffexMemberRankRow,
    replace_member_rank_rows,
)
from backend.app.repositories.news_warehouse_repo import (
    ensure_news_warehouse_schema,
    upsert_news_event,
)


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


def test_ledger_classification_backfill_writer_requires_task_scope(tmp_path) -> None:
    from backend.app.repositories.ledger_import_repo import LedgerImportRepository

    with pytest.raises(PermissionError, match="task write scope"):
        LedgerImportRepository(str(tmp_path / "ledger.duckdb")).attest_classification_rule_versions(
            batch_ids=[1],
            from_rule_versions={1: "position_key_contract_v1"},
            target_rule_version="rv_ledger_classification_v2",
            expected_immutable_evidence_digest="not-reached",
        )
