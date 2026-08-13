"""Structural guards for server-generated read-only SQL disclosures.

These checks intentionally cover read-only safety plus table/filter drift. They do not
claim that every local intent disclosure is a byte-for-byte execution log.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable

from backend.app.repositories import choice_news_repo
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.bond_analytics_repo import (
    FACT_TABLE as BOND_ANALYTICS_FACT_TABLE,
)
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.market_read_repo import (
    CHOICE_NEWS_EVENTS_SQL as RESEARCH_RADAR_NEWS_SQL,
)
from backend.app.repositories.market_read_repo import MarketReadRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.product_category_pnl_repo import (
    PRODUCT_CATEGORY_PNL_ROWS_SQL,
    ProductCategoryPnlRepository,
)
from backend.app.repositories.risk_tensor_repo import (
    FACT_TABLE as RISK_TENSOR_FACT_TABLE,
)
from backend.app.repositories.risk_tensor_repo import RiskTensorRepository
from backend.app.services import (
    agent_service,
    choice_news_service,
    macro_vendor_service,
    pnl_bridge_service,
    research_radar_service,
)

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_mvp,
]


_WRITE_SQL = re.compile(
    r"\b(insert|update|delete|attach|detach|copy|create|drop|alter|truncate|merge)\b",
    re.IGNORECASE,
)
_ISO_DATE_LITERAL = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
RISK_TENSOR_PROJECTION_QUALITY_FIELDS = (
    "missing_maturity_market_value",
    "missing_maturity_count",
    "floating_rate_proxy_market_value",
    "floating_rate_proxy_count",
    "payment_frequency_fallback_market_value",
    "payment_frequency_fallback_count",
    "bullet_value_date_fallback_market_value",
    "bullet_value_date_fallback_count",
)


def _source(*symbols: Callable[..., object]) -> str:
    return " ".join(inspect.getsource(symbol) for symbol in symbols).lower()


def _disclosure(*statements: str) -> str:
    return " ".join(" ".join(statement.split()) for statement in statements).lower()


def _assert_source_alignment(
    *,
    statements: list[str],
    source: str,
    tables: set[str],
    filters: set[str],
) -> None:
    disclosed = _disclosure(*statements)
    for table in tables:
        assert table in source
        assert table in disclosed
    for filter_name in filters:
        assert filter_name in source
        assert filter_name in disclosed


def test_agent_sql_disclosures_remain_read_only_parameterized_templates():
    disclosures = [
        *agent_service._PORTFOLIO_OVERVIEW_SQL_DISCLOSURE,
        *agent_service._PNL_SUMMARY_SQL_DISCLOSURE,
        *agent_service._CREDIT_EXPOSURE_SQL_DISCLOSURE,
        *agent_service._RISK_TENSOR_SQL_DISCLOSURE,
        *agent_service._PNL_BRIDGE_SQL_DISCLOSURE,
        *agent_service._MARKET_DATA_SQL_DISCLOSURE,
        *agent_service._PRODUCT_PNL_SQL_DISCLOSURE,
        *agent_service._NEWS_SQL_DISCLOSURE,
        RESEARCH_RADAR_NEWS_SQL,
    ]

    assert disclosures
    for statement in disclosures:
        normalized = " ".join(statement.split())
        assert normalized.lower().startswith(("select", "with"))
        assert _WRITE_SQL.search(normalized) is None
        assert _ISO_DATE_LITERAL.search(normalized) is None


def test_portfolio_overview_disclosure_tracks_repository_tables_and_filters():
    _assert_source_alignment(
        statements=agent_service._PORTFOLIO_OVERVIEW_SQL_DISCLOSURE,
        source=_source(BalanceAnalysisRepository.fetch_formal_overview),
        tables={
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
        },
        filters={"report_date", "currency_basis", "position_scope"},
    )


def test_pnl_summary_disclosure_tracks_repository_tables_and_report_date():
    _assert_source_alignment(
        statements=agent_service._PNL_SUMMARY_SQL_DISCLOSURE,
        source=_source(
            PnlRepository.overview_totals,
            PnlRepository.fetch_formal_fi_rows,
            PnlRepository.fetch_nonstd_bridge_rows,
            PnlRepository._fetch_rows,
        ),
        tables={"fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"},
        filters={"report_date"},
    )


def test_credit_disclosure_tracks_bond_repository_filters():
    assert BOND_ANALYTICS_FACT_TABLE in _disclosure(
        *agent_service._CREDIT_EXPOSURE_SQL_DISCLOSURE
    )
    credit_source = _source(
        BondAnalyticsRepository.fetch_credit_summary,
        BondAnalyticsRepository.fetch_bond_analytics_rows,
    )
    assert "report_date" in credit_source
    assert "report_date" in _disclosure(
        *agent_service._CREDIT_EXPOSURE_SQL_DISCLOSURE
    )
    assert "asset_class_std" in credit_source
    assert "asset_class_std" in _disclosure(
        *agent_service._CREDIT_EXPOSURE_SQL_DISCLOSURE
    )


def test_risk_tensor_disclosure_tracks_repository_table_and_report_date():
    source = _source(RiskTensorRepository.fetch_risk_tensor_row)
    disclosed = _disclosure(*agent_service._RISK_TENSOR_SQL_DISCLOSURE)
    duration_source = _source(agent_service._duration_risk_payload)
    assert RISK_TENSOR_FACT_TABLE in disclosed
    assert "risktensorrepository" in duration_source
    assert "_risk_tensor_sql_disclosure" in duration_source
    assert "report_date" in source
    assert "report_date" in disclosed
    for field_name in RISK_TENSOR_PROJECTION_QUALITY_FIELDS:
        assert field_name in source
        assert field_name in disclosed


def test_pnl_bridge_disclosure_tracks_input_tables_and_scope_filters():
    _assert_source_alignment(
        statements=agent_service._PNL_BRIDGE_SQL_DISCLOSURE,
        source=_source(
            pnl_bridge_service.pnl_bridge_envelope,
            PnlRepository.fetch_formal_fi_rows,
            PnlRepository._fetch_rows,
            BalanceAnalysisRepository.fetch_pnl_bridge_zqtz_balance_rows,
            BalanceAnalysisRepository.fetch_formal_zqtz_rows,
        ),
        tables={"fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"},
        filters={"report_date", "position_scope", "currency_basis"},
    )


def test_market_data_disclosure_tracks_macro_and_formal_fx_read_paths():
    macro_source = _source(macro_vendor_service._load_choice_macro_recent_rows)
    fx_source = _source(macro_vendor_service._load_latest_fx_mid_rows)
    disclosed = _disclosure(*agent_service._MARKET_DATA_SQL_DISCLOSURE)

    assert "fact_choice_macro_daily" in macro_source
    assert "fact_choice_macro_daily" in disclosed
    assert "fx_daily_mid" in fx_source
    assert "fx_daily_mid" in disclosed
    assert "upper(quote_currency) = 'cny'" in fx_source
    assert "upper(quote_currency) = 'cny'" in disclosed


def test_product_pnl_disclosure_is_the_repository_execution_template():
    # 披露与执行共用同一常量：任一侧改模板另一侧必然同步，否则此断言先红。
    assert agent_service._PRODUCT_PNL_SQL_DISCLOSURE == [PRODUCT_CATEGORY_PNL_ROWS_SQL]
    assert "product_category_pnl_rows_sql" in _source(ProductCategoryPnlRepository.fetch_rows)

    disclosed = _disclosure(*agent_service._PRODUCT_PNL_SQL_DISCLOSURE)
    assert "from product_category_pnl_formal_read_model" in disclosed
    assert "report_date = ?" in disclosed
    assert "view = ?" in disclosed


def test_news_disclosure_tracks_choice_news_execution_template_and_filters():
    # 静态披露常量与执行链路模板同源渲染：repo 模板或常量任一侧漂移都在此变红。
    assert agent_service._NEWS_SQL_DISCLOSURE == [
        " ".join(
            choice_news_repo.choice_news_latest_events_sql(
                where_clause="{where_clause}",
                include_payload_json=True,
            ).split()
        )
    ]
    # service 层披露函数同样转发 repo 的执行同源模板函数（同模板、不执行）。
    assert "choice_news_latest_sql_text" in _source(
        choice_news_service.choice_news_latest_sql_disclosure
    )
    # 意图 payload 披露受护常量，唯一运行期槽位由执行同源 choice_news_filters 填充。
    news_source = _source(agent_service._news_payload)
    assert "_news_sql_disclosure" in news_source
    assert "choice_news_filters" in news_source

    assert choice_news_repo.RELATION_CHOICE_NEWS_EVENT == "choice_news_event"
    disclosed = _disclosure(*agent_service._NEWS_SQL_DISCLOSURE)
    assert "from choice_news_event {where_clause}" in disclosed
    assert "order by received_at desc" in disclosed
    assert "limit ? offset ?" in disclosed
    # 运行期 where 槽位的同源生成器只产出 `?` 绑定的过滤子句，过滤值不进披露文本。
    filters_source = _source(choice_news_repo.choice_news_filters)
    for clause in ("group_id = ?", "topic_code = ?", "received_at >= ?", "received_at <= ?"):
        assert clause in filters_source


def test_research_radar_disclosure_is_the_market_read_execution_template():
    # 披露与执行共用 market_read_repo 的同一常量（import 别名，不是复制品）。
    assert research_radar_service._CHOICE_NEWS_EVENTS_SQL is RESEARCH_RADAR_NEWS_SQL
    assert "_choice_news_events_sql" in _source(research_radar_service.research_radar_brief_payload)
    assert "choice_news_events_sql" in _source(MarketReadRepository.fetch_choice_news_events)

    disclosed = _disclosure(RESEARCH_RADAR_NEWS_SQL)
    assert "from choice_news_event" in disclosed
    assert "coalesce(error_code, 0) = 0" in disclosed
    assert "order by received_at desc" in disclosed
    assert "limit ?" in disclosed
