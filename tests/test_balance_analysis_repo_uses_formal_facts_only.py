from __future__ import annotations

from tests.helpers import load_module


def test_balance_analysis_outward_repo_queries_read_governed_formal_facts_only():
    repo_mod = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    repo = repo_mod.BalanceAnalysisRepository("placeholder.duckdb")

    observed_queries: list[str] = []

    def fake_fetch_rows(query: str, params=None):
        observed_queries.append(query)
        normalized = " ".join(query.split())
        if "count(*) from summary_rows" in normalized:
            return [(0,)]
        if "select report_date, instrument_code" in normalized:
            return []
        if "select report_date, position_id" in normalized:
            return []
        if "cross join tyw" in normalized:
            if "asset_total_market_value_amount" in normalized:
                return [
                    (
                        "2025-12-31",
                        "all",
                        "CNY",
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        "",
                        "",
                    )
                ]
            return [("2025-12-31", "all", "CNY", 0, 0, 0, 0, 0, "", "")]
        if "as basis_rows" in normalized:
            return []
        return []

    repo._fetch_rows = fake_fetch_rows  # type: ignore[method-assign]

    repo.list_report_dates()
    repo.fetch_formal_zqtz_rows(report_date="2025-12-31")
    repo.fetch_formal_tyw_rows(report_date="2025-12-31")
    repo.fetch_formal_overview(report_date="2025-12-31")
    repo.fetch_formal_summary_table(report_date="2025-12-31")
    repo.fetch_formal_basis_breakdown(report_date="2025-12-31")

    assert observed_queries, "Expected outward balance-analysis repo methods to execute queries"
    for query in observed_queries:
        normalized = " ".join(query.split())
        assert " zqtz_bond_daily_snapshot " not in f" {normalized} "
        assert " tyw_interbank_daily_snapshot " not in f" {normalized} "
    assert any("fact_formal_zqtz_balance_daily" in query for query in observed_queries)
    assert any("fact_formal_tyw_balance_daily" in query for query in observed_queries)
