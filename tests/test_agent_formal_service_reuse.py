"""Agent 本地 intent 复用正式 service 时的治理元数据一致性护栏。

覆盖范围限于既有落地行为：复用正式 service 的 intent 必须直接沿用上游
``result_meta`` 的治理版本与降级标记，不得自拼版本串、不得把上游的
``formal_use_allowed=false`` 放宽为 true，也不得把白名单之外的上游字段
带进 Agent 契约。不新增任何业务行为。
"""

from __future__ import annotations

import importlib
from pathlib import Path

import duckdb
import pytest

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import CACHE_MANIFEST_STREAM, GovernanceRepository

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_mvp,
]

REPORT_DATE = "2026-03-31"

# 复用正式 service 的 intent -> (上游 service 模块, envelope 函数名)。
_REUSED_UPSTREAM = {
    "portfolio_overview": ("backend.app.services.balance_analysis_service", "balance_analysis_overview_envelope"),
    "pnl_summary": ("backend.app.services.pnl_service", "pnl_overview_envelope"),
    "duration_risk": ("backend.app.services.risk_tensor_service", "risk_tensor_envelope"),
    "pnl_bridge": ("backend.app.services.pnl_bridge_service", "pnl_bridge_envelope"),
    "product_pnl": ("backend.app.services.product_category_pnl_service", "product_category_pnl_envelope"),
    "risk_tensor": ("backend.app.services.risk_tensor_service", "risk_tensor_envelope"),
}
_GOVERNANCE_META_FIELDS = (
    "basis",
    "source_version",
    "vendor_version",
    "rule_version",
    "cache_version",
    "vendor_status",
    "fallback_mode",
)


def _module(module_name: str):
    """按名字解析当前模块对象，而不是在导入期绑定。

    `tests/helpers.load_module` 会重新执行模块并把新对象写回 sys.modules，导入期
    绑定的对象可能不再是被测代码运行期解析到的那一个。
    """
    return importlib.import_module(module_name)


def _numeric(raw: float, unit: str, display: str) -> dict[str, object]:
    return {
        "raw": raw,
        "unit": unit,
        "display": display,
        "precision": 2,
        "sign_aware": True,
    }


def _upstream_meta(result_kind: str, source_surface: str) -> dict[str, object]:
    return {
        "trace_id": f"tr_upstream_{result_kind}",
        "basis": "formal",
        "result_kind": result_kind,
        "formal_use_allowed": True,
        "source_version": "sv_upstream_formal",
        "vendor_version": "vv_upstream",
        "rule_version": "rv_upstream_formal",
        "cache_version": "cv_upstream_formal",
        "cache_key": "ck_upstream_formal",
        "quality_flag": "ok",
        "vendor_status": "ok",
        "fallback_mode": "none",
        "requested_report_date": REPORT_DATE,
        "resolved_report_date": REPORT_DATE,
        "as_of_date": REPORT_DATE,
        "date_basis": "formal_report_date",
        "fallback_date": None,
        "source_surface": source_surface,
        "amount_currency_basis": "CNY",
        "amount_currency_basis_note": "fixture uses the verified CNY basis.",
        "generated_at": "2026-04-01T00:00:00Z",
        "data_built_at": "2026-03-31T23:00:00Z",
    }


_UPSTREAM_RESULTS: dict[str, dict[str, object]] = {
    "pnl.overview": {
        "report_date": REPORT_DATE,
        "formal_fi_row_count": 2,
        "nonstd_bridge_row_count": 1,
        "interest_income_514": "10.00",
        "fair_value_change_516": "20.00",
        "capital_gain_517": "30.00",
        "manual_adjustment": "0.00",
        "total_pnl": "60.00",
        "reconciliation_checks": {},
    },
    "balance-analysis.overview": {
        "report_date": REPORT_DATE,
        "position_scope": "all",
        "currency_basis": "CNY",
        "detail_row_count": 2,
        "summary_row_count": 2,
        "total_market_value_amount": "1500.00000000",
        "total_amortized_cost_amount": "1450.00000000",
        "total_accrued_interest_amount": "20.00000000",
    },
    "product_category_pnl.overview": {
        "report_date": REPORT_DATE,
        "view": "monthly",
        "available_views": ["monthly"],
        "rows": [
            {"category_id": "asset_total", "business_net_income": "25.0"},
            {"category_id": "liability_total", "business_net_income": "15.0"},
            {"category_id": "grand_total", "business_net_income": "40.0"},
        ],
        "asset_total": {"category_id": "asset_total", "business_net_income": "25.0"},
        "liability_total": {"category_id": "liability_total", "business_net_income": "15.0"},
        "grand_total": {"category_id": "grand_total", "business_net_income": "40.0"},
    },
    "risk-tensor.overview": {
        "report_date": REPORT_DATE,
        "bond_count": 4,
        "portfolio_modified_duration": _numeric(3.5, "years", "3.50"),
        "portfolio_dv01": _numeric(1200.0, "dv01", "1,200.00"),
        "portfolio_convexity": _numeric(0.5, "ratio", "0.50"),
        "rate_risk_market_value": _numeric(100.0, "yuan", "100.00"),
        "duration_excluded_market_value": _numeric(0.0, "yuan", "0.00"),
        "duration_excluded_count": 0,
        "cs01": _numeric(11.0, "dv01", "11.00"),
        "quality_flag": "ok",
    },
    "pnl.bridge": {
        "summary": {
            "total_explained_pnl": _numeric(60.0, "yuan", "60.00"),
            "total_actual_pnl": _numeric(60.0, "yuan", "60.00"),
            "total_residual": _numeric(0.0, "yuan", "0.00"),
            "row_count": 2,
        }
    },
}
_UPSTREAM_RESULT_KIND = {
    "portfolio_overview": ("balance-analysis.overview", "formal_balance"),
    "pnl_summary": ("pnl.overview", "formal_pnl"),
    "duration_risk": ("risk-tensor.overview", "risk_tensor"),
    "pnl_bridge": ("pnl.bridge", "formal_pnl"),
    "product_pnl": ("product_category_pnl.overview", "formal_pnl"),
    "risk_tensor": ("risk-tensor.overview", "risk_tensor"),
}


class _DateOnlyRepository:
    """只回答 report_date 列表的仓库替身：数值与治理元数据全部来自上游 service。"""

    def __init__(self, path: str) -> None:
        self.path = path

    def list_report_dates(self) -> list[str]:
        return [REPORT_DATE]

    def list_union_report_dates(self) -> list[str]:
        return [REPORT_DATE]

    def list_formal_fi_report_dates(self) -> list[str]:
        return [REPORT_DATE]

    def fetch_formal_overview(self, **_: object) -> dict[str, object]:
        return {
            **_UPSTREAM_RESULTS["balance-analysis.overview"],
            "lineage_row_count": 2,
            "source_version_missing_count": 0,
            "rule_version_missing_count": 0,
        }


def _run_reusing_intent(
    monkeypatch,
    tmp_path,
    intent: str,
    *,
    meta_overrides: dict[str, object] | None = None,
    dropped_meta_fields: tuple[str, ...] = (),
) -> tuple[dict[str, object], dict[str, object]]:
    """用固定的上游 envelope 替身跑一个复用正式 service 的 intent。

    返回 (上游 result_meta, Agent payload)。
    """
    result_kind, source_surface = _UPSTREAM_RESULT_KIND[intent]
    meta = _upstream_meta(result_kind, source_surface)
    meta.update(meta_overrides or {})
    for field_name in dropped_meta_fields:
        meta.pop(field_name, None)
    upstream = {"result": _UPSTREAM_RESULTS[result_kind], "result_meta": meta}

    agent_service = _module("backend.app.services.agent_service")
    monkeypatch.setattr(agent_service, "BalanceAnalysisRepository", _DateOnlyRepository)
    monkeypatch.setattr(agent_service, "PnlRepository", _DateOnlyRepository)
    monkeypatch.setattr(agent_service, "ProductCategoryPnlRepository", _DateOnlyRepository)
    monkeypatch.setattr(agent_service, "RiskTensorRepository", _DateOnlyRepository)
    upstream_module_name, envelope_name = _REUSED_UPSTREAM[intent]
    monkeypatch.setattr(
        _module(upstream_module_name),
        envelope_name,
        lambda *_, **__: upstream,
    )

    handlers = agent_service._build_intent_handlers("test.duckdb", str(tmp_path))
    payload = handlers[intent](
        AgentQueryRequest(
            question=intent,
            currency_basis="CNY",
            context={"user_id": "user_a"},
        )
    )
    return meta, payload


@pytest.mark.parametrize("intent", sorted(_REUSED_UPSTREAM))
def test_reusing_intent_inherits_upstream_governance_metadata(monkeypatch, tmp_path, intent):
    meta, payload = _run_reusing_intent(monkeypatch, tmp_path, intent)

    for field_name in _GOVERNANCE_META_FIELDS:
        assert payload[field_name] == meta[field_name], field_name
    # 上游血缘的可选字段存在时必须透传，不能在 Agent 层丢失。
    assert payload["cache_key"] == meta["cache_key"]
    assert payload["data_built_at"] == meta["data_built_at"]
    assert payload["formal_use_allowed"] is True
    assert payload["result_kind"] == f"agent.{intent}"


@pytest.mark.parametrize("intent", sorted(_REUSED_UPSTREAM))
def test_reusing_intent_never_upgrades_upstream_formal_use_allowed(monkeypatch, tmp_path, intent):
    _meta, payload = _run_reusing_intent(
        monkeypatch,
        tmp_path,
        intent,
        meta_overrides={"formal_use_allowed": False},
    )
    assert payload["formal_use_allowed"] is False

    # 上游连口径标记都没有时同样 fail-closed，不得默认放行。
    _missing_meta, missing_marker_payload = _run_reusing_intent(
        monkeypatch,
        tmp_path,
        intent,
        dropped_meta_fields=("formal_use_allowed",),
    )
    assert missing_marker_payload["formal_use_allowed"] is False


@pytest.mark.parametrize("intent", sorted(_REUSED_UPSTREAM))
def test_reusing_intent_omits_optional_lineage_fields_absent_upstream(monkeypatch, tmp_path, intent):
    _meta, payload = _run_reusing_intent(
        monkeypatch,
        tmp_path,
        intent,
        dropped_meta_fields=("cache_key", "data_built_at"),
    )
    assert payload.get("cache_key") is None
    assert payload.get("data_built_at") is None


@pytest.mark.parametrize("intent", sorted(_REUSED_UPSTREAM))
def test_reusing_intent_does_not_copy_non_whitelisted_upstream_fields(monkeypatch, tmp_path, intent):
    _meta, payload = _run_reusing_intent(
        monkeypatch,
        tmp_path,
        intent,
        meta_overrides={
            "upstream_internal_token": "must-not-leak",
            "evidence_rows": 999,
            "tables_used": ["upstream_table_should_not_leak"],
        },
    )
    assert "upstream_internal_token" not in payload
    # Agent 的证据字段由 handler 自己披露，不能被上游 result_meta 覆盖。
    assert payload["row_count"] != 999
    assert "upstream_table_should_not_leak" not in payload["tables_used"]
    # trace_id / result_kind 属于 Agent 自身契约，不从上游继承。
    assert "trace_id" not in payload
    assert payload["result_kind"].startswith("agent.")


def _seed_formal_pnl(duckdb_path: Path, governance_dir: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              currency_basis varchar,
              interest_income_514 decimal(38, 2),
              fair_value_change_516 decimal(38, 2),
              capital_gain_517 decimal(38, 2),
              manual_adjustment decimal(38, 2),
              total_pnl decimal(38, 2),
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_nonstd_pnl_bridge (
              report_date varchar,
              bond_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              interest_income_514 decimal(38, 2),
              fair_value_change_516 decimal(38, 2),
              capital_gain_517 decimal(38, 2),
              manual_adjustment decimal(38, 2),
              total_pnl decimal(38, 2),
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
            (?, 'BOND-001', 'PORTFOLIO-A', 'CC100', 'H', 'AC', 'CNY', 10, 5, 2, 0, 17,
             'sv_fi_1', 'rv_pnl_phase2_materialize_v7', 'batch-1', 'tr-fi-1')
            """,
            [REPORT_DATE],
        )
        conn.execute(
            """
            insert into fact_nonstd_pnl_bridge values
            (?, 'NONSTD-001', 'PORTFOLIO-A', 'CC100', 3, 1, 0, 0, 4,
             'sv_nonstd_1', 'rv_pnl_phase2_materialize_v7', 'batch-2', 'tr-nonstd-1')
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()
    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_MANIFEST_STREAM,
        {
            "cache_key": "pnl:phase2:materialize:formal",
            "cache_version": "cv_pnl_formal__rv_pnl_phase2_materialize_v7",
            "source_version": "sv_agent_reuse_pnl_1",
            "vendor_version": "vv_none",
            "rule_version": "rv_pnl_phase2_materialize_v7",
            "report_date": REPORT_DATE,
        },
    )


def _seed_formal_balance(
    duckdb_path: Path,
    governance_dir: Path,
    *,
    source_version: str | None = "sv_balance_zqtz_1",
) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
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
              market_value_amount decimal(38, 8),
              amortized_cost_amount decimal(38, 8),
              accrued_interest_amount decimal(38, 8),
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
              counterparty_name varchar,
              product_type varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              principal_amount decimal(38, 8),
              accrued_interest_amount decimal(38, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            (?, 'BOND-001', 'PORTFOLIO-A', 'CC100', 'H', 'AC', 'asset', 'CNY',
             1000, 950, 12, ?, 'rv_balance_1')
            """,
            [REPORT_DATE, source_version],
        )
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily values
            (?, 'TYW-001', 'COUNTERPARTY-A', 'repo', 'H', 'AC', 'asset', 'CNY',
             500, 8, 'sv_balance_tyw_1', 'rv_balance_1')
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()
    balance_service = _module("backend.app.services.balance_analysis_service")
    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_MANIFEST_STREAM,
        {
            "cache_key": balance_service.CACHE_KEY,
            "cache_version": balance_service.CACHE_VERSION,
            "source_version": "sv_agent_reuse_balance_1",
            "vendor_version": "vv_none",
            "rule_version": balance_service.RULE_VERSION,
            "report_date": REPORT_DATE,
        },
    )


def _seed_product_pnl_read_model(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table product_category_pnl_formal_read_model (
              sort_order integer,
              category_id varchar,
              category_name varchar,
              side varchar,
              level integer,
              view varchar,
              report_date varchar,
              baseline_ftp_rate_pct double,
              cnx_scale double,
              cny_scale double,
              foreign_scale double,
              cnx_cash double,
              cny_cash double,
              foreign_cash double,
              cny_ftp double,
              foreign_ftp double,
              cny_net double,
              foreign_net double,
              business_net_income double,
              weighted_yield double,
              is_total boolean,
              children_json varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into product_category_pnl_formal_read_model values
            (1, 'asset_total', 'Asset Total', 'asset', 0, 'monthly', ?, 1.75, 100, 80, 20, 1000, 800, 200, 10, 3, 20, 5, 25, 2.5, true, '[]', 'sv_product_1', 'rv_product_category_pnl_v2'),
            (2, 'interest_earning_assets', 'Interest Earning Assets', 'asset', 1, 'monthly', ?, 1.75, 90, 70, 20, 900, 700, 200, 9, 3, 18, 5, 23, 2.4, false, '[]', 'sv_product_1', 'rv_product_category_pnl_v2'),
            (3, 'liability_total', 'Liability Total', 'liability', 0, 'monthly', ?, 1.75, 50, 40, 10, 500, 400, 100, 8, 2, 12, 3, 15, 1.5, true, '[]', 'sv_product_1', 'rv_product_category_pnl_v2'),
            (4, 'grand_total', 'Grand Total', 'all', 0, 'monthly', ?, 1.75, 150, 120, 30, 1500, 1200, 300, 18, 5, 32, 8, 40, 2.0, true, '[]', 'sv_product_1', 'rv_product_category_pnl_v2')
            """,
            [REPORT_DATE, REPORT_DATE, REPORT_DATE, REPORT_DATE],
        )
    finally:
        conn.close()


def _assert_key_meta_matches(payload: dict[str, object], upstream_meta: dict[str, object]) -> None:
    for field_name in (
        "formal_use_allowed",
        "quality_flag",
        "source_version",
        "rule_version",
        "cache_version",
        "fallback_mode",
    ):
        assert payload[field_name] == upstream_meta[field_name], field_name
    for field_name in ("resolved_report_date", "requested_report_date", "as_of_date"):
        if upstream_meta.get(field_name) is not None:
            assert payload[field_name] == upstream_meta[field_name], field_name


def test_pnl_summary_meta_and_numbers_match_formal_pnl_service_envelope(monkeypatch, tmp_path):
    duckdb_path = tmp_path / "moss-agent-reuse-pnl.duckdb"
    governance_dir = tmp_path / "governance-agent-reuse-pnl"
    _seed_formal_pnl(duckdb_path, governance_dir)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    pnl_service = _module("backend.app.services.pnl_service")
    agent_service = _module("backend.app.services.agent_service")
    upstream = pnl_service.pnl_overview_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date=REPORT_DATE,
    )
    upstream_meta = dict(upstream["result_meta"])
    upstream_result = dict(upstream["result"])

    handlers = agent_service._build_intent_handlers(str(duckdb_path), str(governance_dir))
    payload = handlers["pnl_summary"](
        AgentQueryRequest(
            question="PnL summary",
            currency_basis="CNY",
            context={"user_id": "user_a"},
        )
    )

    assert upstream_meta["formal_use_allowed"] is True
    for field_name in (
        "formal_use_allowed",
        "quality_flag",
        "source_version",
        "rule_version",
        "cache_version",
        "vendor_version",
        "fallback_mode",
        "basis",
        "resolved_report_date",
        "requested_report_date",
        "as_of_date",
    ):
        assert payload[field_name] == upstream_meta[field_name], field_name

    total_pnl_card = next(card for card in payload["cards"] if card["title"] == "Total PnL")
    assert total_pnl_card["value"] == str(upstream_result["total_pnl"])
    assert payload["row_count"] == (
        int(upstream_result["formal_fi_row_count"]) + int(upstream_result["nonstd_bridge_row_count"])
    )


def test_pnl_summary_keeps_formal_use_closed_when_formal_service_refuses(monkeypatch, tmp_path):
    duckdb_path = tmp_path / "moss-agent-reuse-pnl-blocked.duckdb"
    governance_dir = tmp_path / "governance-agent-reuse-pnl-blocked"
    _seed_formal_pnl(duckdb_path, governance_dir)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    pnl_service = _module("backend.app.services.pnl_service")
    agent_service = _module("backend.app.services.agent_service")
    real_envelope = pnl_service.pnl_overview_envelope

    def refusing_envelope(**kwargs):
        envelope = real_envelope(**kwargs)
        meta = dict(envelope["result_meta"])
        meta["formal_use_allowed"] = False
        return {**envelope, "result_meta": meta}

    monkeypatch.setattr(pnl_service, "pnl_overview_envelope", refusing_envelope)

    handlers = agent_service._build_intent_handlers(str(duckdb_path), str(governance_dir))
    payload = handlers["pnl_summary"](
        AgentQueryRequest(
            question="PnL summary",
            currency_basis="CNY",
            context={"user_id": "user_a"},
        )
    )

    assert payload["formal_use_allowed"] is False
    assert payload["quality_flag"] != "ok"
    assert "formal_use_allowed=false" in payload["answer"]


def test_portfolio_overview_meta_and_numbers_match_formal_balance_service_envelope(
    monkeypatch,
    tmp_path,
):
    duckdb_path = tmp_path / "moss-agent-reuse-balance.duckdb"
    governance_dir = tmp_path / "governance-agent-reuse-balance"
    _seed_formal_balance(duckdb_path, governance_dir)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    balance_service = _module("backend.app.services.balance_analysis_service")
    agent_service = _module("backend.app.services.agent_service")
    upstream = balance_service.balance_analysis_overview_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date=REPORT_DATE,
        position_scope="all",
        currency_basis="CNY",
    )
    upstream_meta = dict(upstream["result_meta"])
    upstream_result = dict(upstream["result"])

    handlers = agent_service._build_intent_handlers(str(duckdb_path), str(governance_dir))
    payload = handlers["portfolio_overview"](
        AgentQueryRequest(
            question="portfolio overview",
            currency_basis="CNY",
            context={"user_id": "user_a"},
        )
    )

    _assert_key_meta_matches(payload, upstream_meta)
    market_value_card = next(card for card in payload["cards"] if card["title"] == "Total Market Value")
    assert market_value_card["spec"]["raw_value"] == str(upstream_result["total_market_value_amount"])
    assert payload["row_count"] == upstream_result["detail_row_count"]


def test_product_pnl_meta_and_numbers_match_formal_service_envelope(monkeypatch, tmp_path):
    duckdb_path = tmp_path / "moss-agent-reuse-product.duckdb"
    governance_dir = tmp_path / "governance-agent-reuse-product"
    _seed_product_pnl_read_model(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    product_service = _module("backend.app.services.product_category_pnl_service")
    agent_service = _module("backend.app.services.agent_service")
    upstream = product_service.product_category_pnl_envelope(
        str(duckdb_path),
        report_date=REPORT_DATE,
        view="monthly",
    )
    upstream_meta = dict(upstream["result_meta"])
    upstream_result = dict(upstream["result"])

    handlers = agent_service._build_intent_handlers(str(duckdb_path), str(governance_dir))
    payload = handlers["product_pnl"](
        AgentQueryRequest(
            question="product pnl",
            filters={"view": "monthly"},
            context={"user_id": "user_a"},
        )
    )

    _assert_key_meta_matches(payload, upstream_meta)
    assert payload["resolved_report_date"] == upstream_result["report_date"]
    assert payload["as_of_date"] == upstream_result["report_date"]
    grand_total_card = next(card for card in payload["cards"] if card["title"] == "Grand Total")
    assert grand_total_card["value"] == str(upstream_result["grand_total"]["business_net_income"])
    assert payload["row_count"] == len(upstream_result["rows"])


def test_portfolio_overview_agent_row_lineage_gate_can_degrade_formal_service_result(
    monkeypatch,
    tmp_path,
):
    duckdb_path = tmp_path / "moss-agent-reuse-balance-row-lineage.duckdb"
    governance_dir = tmp_path / "governance-agent-reuse-balance-row-lineage"
    _seed_formal_balance(duckdb_path, governance_dir, source_version=None)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    balance_service = _module("backend.app.services.balance_analysis_service")
    agent_service = _module("backend.app.services.agent_service")
    upstream = balance_service.balance_analysis_overview_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date=REPORT_DATE,
        position_scope="all",
        currency_basis="CNY",
    )

    handlers = agent_service._build_intent_handlers(str(duckdb_path), str(governance_dir))
    payload = handlers["portfolio_overview"](
        AgentQueryRequest(
            question="portfolio overview",
            currency_basis="CNY",
            context={"user_id": "user_a"},
        )
    )

    assert upstream["result_meta"]["formal_use_allowed"] is True
    assert upstream["result_meta"]["quality_flag"] == "ok"
    assert payload["formal_use_allowed"] is False
    assert payload["quality_flag"] == "warning"
    assert "Agent 侧行级受治理 lineage" in payload["answer"]
    assert not any(card["type"] == "metric" for card in payload["cards"])
