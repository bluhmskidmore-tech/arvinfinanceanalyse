from __future__ import annotations

import sys
from copy import deepcopy

import pytest

from backend.app.agent.runtime import local_request_resolution as resolution_runtime
from backend.app.agent.runtime import ontology_bindings
from backend.app.agent.runtime.local_request_resolution import (
    ONTOLOGY_PARSER_REVISION,
    SEMANTIC_EXECUTION_CONTEXT_KEY,
    pin_semantic_execution_request,
    resolve_local_request,
    validate_semantic_execution_request,
    validate_semantic_execution_snapshot,
)
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.tools.analysis_view_tool import AnalysisViewTool
from backend.app.ontology.loader import load_ontology_index
from backend.app.services import agent_service, pnl_service


pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]

# 本文件在导入期绑定的模块对象，必须与生产代码运行期解析到的模块对象是同一个。
_IDENTITY_PINNED_MODULES = (
    agent_service,
    pnl_service,
    resolution_runtime,
    ontology_bindings,
)


@pytest.fixture(autouse=True)
def _pin_module_identities():
    """把本文件绑定的模块对象钉回 sys.modules，隔离跨文件的模块身份漂移。

    `tests/helpers.load_module` 会按文件路径重新执行模块并把新对象写回 sys.modules
    且不还原（例如 tests/test_agent_intent_routing.py 会重载
    backend.app.services.pnl_service）。此后本文件里 `monkeypatch.setattr(pnl_service,
    "pnl_overview_envelope", ...)` 打在旧对象上，而 agent_service 的函数内
    `from backend.app.services.pnl_service import pnl_overview_envelope` 走 sys.modules
    拿到新对象上的真实函数，替身失效、查询转为读真实 DuckDB，semantic_context
    因此变成 blocked。这里只影响本文件的用例，结束后逐个还原原值。
    """
    originals = {module.__name__: sys.modules.get(module.__name__) for module in _IDENTITY_PINNED_MODULES}
    for module in _IDENTITY_PINNED_MODULES:
        sys.modules[module.__name__] = module
    try:
        yield
    finally:
        for module_name, original in originals.items():
            if original is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = original


def _formal_pnl_overview(report_date: str) -> dict[str, object]:
    return {
        "result": {
            "report_date": report_date,
            "formal_fi_row_count": 2,
            "nonstd_bridge_row_count": 1,
            "interest_income_514": "10.00",
            "fair_value_change_516": "20.00",
            "capital_gain_517": "30.00",
            "manual_adjustment": "0.00",
            "total_pnl": "60.00",
            "reconciliation_checks": {},
        },
        "result_meta": {
            "trace_id": f"tr_pnl_overview_{report_date}",
            "basis": "formal",
            "result_kind": "pnl.overview",
            "formal_use_allowed": True,
            "source_version": "sv_pnl_formal",
            "vendor_version": "vv_none",
            "rule_version": "rv_pnl_formal",
            "cache_version": "cv_pnl_formal",
            "cache_key": "pnl_materialized",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "requested_report_date": report_date,
            "resolved_report_date": report_date,
            "as_of_date": report_date,
            "date_basis": "formal_report_date",
            "fallback_date": None,
            "source_surface": "formal_pnl",
            "amount_currency_basis": "CNY",
            "amount_currency_basis_note": "Test fixture uses the verified CNY basis.",
            "generated_at": "2026-04-01T00:00:00Z",
            "data_built_at": "2026-03-31T23:00:00Z",
        },
    }


def _ontology_pnl_tool(tmp_path) -> AnalysisViewTool:
    return AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers=agent_service._build_intent_handlers(
            "test.duckdb",
            str(tmp_path),
        ),
    )


def test_first_slice_bindings_match_approved_ontology_contract():
    assert ontology_bindings.validate_ontology_metric_bindings() == []
    assert [
        binding.metric_id
        for binding in ontology_bindings.list_ontology_metric_bindings()
    ] == ["MTR-PNL-001", "MTR-PNL-002", "MTR-PNL-005"]


def test_executable_binding_fails_closed_when_metric_contract_drifts(monkeypatch):
    real_index = load_ontology_index()
    entity = real_index.get_entity("MTR-PNL-001")
    assert entity is not None
    invalid_entity = entity.model_copy(update={"precision": 8})

    class DriftedIndex:
        def get_entity(self, entity_id: str):
            if entity_id == "MTR-PNL-001":
                return invalid_entity
            return real_index.get_entity(entity_id)

    monkeypatch.setattr(
        ontology_bindings,
        "load_ontology_index",
        lambda: DriftedIndex(),
    )

    assert ontology_bindings.get_bound_metric_entity("MTR-PNL-001") is None
    assert "MTR-PNL-001: precision must be 2" in (
        ontology_bindings.validate_ontology_metric_bindings()
    )

    monkeypatch.setattr(
        resolution_runtime,
        "ontology_content_revision",
        lambda: "sha256:healthy-ontology",
    )
    pinned, resolution = pin_semantic_execution_request(
        AgentQueryRequest(question="2026-03-31 的利息收入（514）是多少")
    )
    snapshot = pinned.context[SEMANTIC_EXECUTION_CONTEXT_KEY]
    assert resolution.semantic_status == "unavailable"
    assert snapshot["ontology_revision"] == "sha256:healthy-ontology"
    assert validate_semantic_execution_snapshot(snapshot) == snapshot


def test_ontology_resolution_covers_definition_value_clarification_and_unsupported():
    definition = resolve_local_request(AgentQueryRequest(question="正式总损益是什么"))
    assert (definition.intent, definition.metric_id, definition.semantic_operation) == (
        "ontology_definition",
        "MTR-PNL-005",
        "definition",
    )

    value = resolve_local_request(
        AgentQueryRequest(
            question="2026-03-31 的利息收入（514）是多少",
            currency_basis="CNY",
        )
    )
    assert (value.intent, value.metric_id, value.report_date) == (
        "pnl_summary",
        "MTR-PNL-001",
        "2026-03-31",
    )

    clarification = resolve_local_request(AgentQueryRequest(question="收益是多少"))
    assert clarification.semantic_status == "clarification_required"
    assert clarification.metric_candidates == (
        "MTR-PNL-001",
        "MTR-PNL-002",
        "MTR-PNL-005",
    )

    unsupported = resolve_local_request(
        AgentQueryRequest(question="为什么正式总损益下降")
    )
    assert unsupported.semantic_status == "unsupported"
    assert unsupported.semantic_reason_code == "unsupported_comparison_or_attribution"


def test_technical_field_name_value_token_does_not_conflict_with_definition():
    resolution = resolve_local_request(
        AgentQueryRequest(question="what is fair_value_change_516")
    )

    assert resolution.semantic_status == "resolved"
    assert resolution.semantic_operation == "definition"
    assert resolution.metric_id == "MTR-PNL-002"


def test_semantic_snapshot_pins_resolution_and_rejects_stale_versions():
    request = AgentQueryRequest(
        question="2026-03-31 的公允价值变动是多少",
        currency_basis="CNY",
    )
    pinned, resolution = pin_semantic_execution_request(request)
    snapshot = pinned.context[SEMANTIC_EXECUTION_CONTEXT_KEY]

    assert resolution.metric_id == "MTR-PNL-002"
    assert validate_semantic_execution_snapshot(snapshot) == snapshot
    assert resolve_local_request(pinned) == resolution

    stale = dict(snapshot)
    stale["parser_revision"] = f"{ONTOLOGY_PARSER_REVISION}-stale"
    with pytest.raises(ValueError, match="no longer current"):
        validate_semantic_execution_snapshot(stale)

    provider_request = AgentQueryRequest(question="hello, can you help me write a note?")
    unchanged, provider_resolution = pin_semantic_execution_request(provider_request)
    assert provider_resolution.route == "provider"
    assert SEMANTIC_EXECUTION_CONTEXT_KEY not in unchanged.context


def test_workbench_cny_value_request_pins_a_valid_pnl_snapshot():
    request = AgentQueryRequest(
        question="2026-03-31 的公允价值变动是多少",
        basis="formal",
        filters={},
        position_scope="all",
        currency_basis="CNY",
        context={},
        routing_surface="standalone_workbench",
    )

    pinned, resolution = pin_semantic_execution_request(request)
    snapshot = pinned.context[SEMANTIC_EXECUTION_CONTEXT_KEY]

    assert resolution.semantic_status == "resolved"
    assert resolution.intent == "pnl_summary"
    assert resolution.metric_id == "MTR-PNL-002"
    assert snapshot["required_resources"] == ["pnl"]
    assert validate_semantic_execution_snapshot(snapshot) == snapshot


@pytest.mark.parametrize(
    ("question", "currency_basis"),
    [
        ("2026-03-31 的正式总损益是多少", "CNY"),
        ("2026-03-31 人民币正式总损益是多少", "CNY"),
        ("2026-03-31 币种为人民币的正式总损益是多少", "CNY"),
    ],
)
def test_supported_yuan_scope_and_routing_metadata_remain_executable(
    question,
    currency_basis,
):
    resolution = resolve_local_request(
        AgentQueryRequest(
            question=question,
            currency_basis=currency_basis,
            context={"user_id": "web-user", "routing_hint": "local"},
            page_context={
                "page_id": "pnl-attribution",
                "current_filters": {"report_date": "2026-03-31"},
                "selected_rows": [],
            },
        )
    )

    assert resolution.semantic_status == "resolved"
    assert resolution.intent == "pnl_summary"
    assert resolution.metric_id == "MTR-PNL-005"


def test_unsupported_value_snapshot_has_no_executable_resource():
    request = AgentQueryRequest(
        question="2026-03-31 的公允价值变动是多少",
        currency_basis="USD",
    )

    pinned, resolution = pin_semantic_execution_request(request)
    snapshot = pinned.context[SEMANTIC_EXECUTION_CONTEXT_KEY]

    assert resolution.semantic_status == "unsupported"
    assert resolution.intent == "ontology_unsupported"
    assert snapshot["required_resources"] == []
    assert validate_semantic_execution_snapshot(snapshot) == snapshot


def test_explicit_cnx_value_request_fails_closed_before_read(tmp_path):
    """显式声明综本口径（CNX）的取数请求必须在读取前失败关闭。"""

    agent_request = AgentQueryRequest(
        question="2026-03-31 的公允价值变动是多少",
        currency_basis="CNX",
    )
    calls: list[str] = []

    def forbidden_handler(_: AgentQueryRequest) -> dict[str, object]:
        calls.append("called")
        raise AssertionError("CNX requests must stop before formal PnL read")

    pinned, resolution = pin_semantic_execution_request(agent_request)
    snapshot = pinned.context[SEMANTIC_EXECUTION_CONTEXT_KEY]
    assert resolution.semantic_status == "unsupported"
    assert resolution.semantic_reason_code == "unsupported_query_scope"
    assert snapshot["required_resources"] == []
    assert snapshot["request_scope"] is None

    envelope = AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"pnl_summary": forbidden_handler},
    ).execute(agent_request)
    assert envelope.semantic_context is not None
    assert envelope.semantic_context.status == "unsupported"
    assert envelope.semantic_context.result_check == "blocked"
    assert calls == []


@pytest.mark.parametrize(
    "currency_basis_kwargs",
    [{}, {"currency_basis": "CNY"}],
    ids=["schema_default_not_set", "explicit_cny"],
)
def test_unset_or_cny_currency_basis_reaches_the_governed_read(
    tmp_path,
    currency_basis_kwargs,
):
    """`currency_basis` 的 schema 默认值是 CNX，但未显式设置时按 CNY 处理。

    否则任何没传币种的调用方（非工作台入口）都会在取数前被拒。快照里的
    `currency_basis` 必须固化为 CNY，pinned 请求也要带上同一口径，
    这样下游读取链路看到的口径与快照一致。
    """

    agent_request = AgentQueryRequest(
        question="2026-03-31 的公允价值变动是多少",
        **currency_basis_kwargs,
    )
    calls: list[str] = []

    def recording_handler(request: AgentQueryRequest) -> dict[str, object]:
        calls.append(request.currency_basis)
        return {
            "answer": "metric ok",
            "basis": "formal",
            "result_kind": "agent.pnl_summary",
            "formal_use_allowed": True,
            "source_version": "sv_test",
            "quality_flag": "ok",
            "row_count": 1,
            "cards": [],
        }

    pinned, resolution = pin_semantic_execution_request(agent_request)
    snapshot = pinned.context[SEMANTIC_EXECUTION_CONTEXT_KEY]
    assert resolution.semantic_status == "resolved"
    assert resolution.semantic_operation == "value"
    assert resolution.metric_id == "MTR-PNL-002"
    assert snapshot["required_resources"] == ["pnl"]
    assert snapshot["request_scope"]["currency_basis"] == "CNY"
    assert pinned.currency_basis == "CNY"
    assert validate_semantic_execution_snapshot(snapshot) == snapshot

    AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"pnl_summary": recording_handler},
    ).execute(pinned)
    assert calls == ["CNY"]


@pytest.mark.parametrize(
    "agent_request",
    [
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
            context={"current_filters": {"portfolio_name": "portfolio_a"}},
        ),
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
            filters={"min_amount": 0},
        ),
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            basis="scenario",
            currency_basis="CNY",
        ),
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            basis="analytical",
            currency_basis="CNY",
        ),
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
            context={"portfolio_id": "portfolio_a"},
        ),
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
            context={"account_id": "account_123"},
        ),
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
            context={"product_id": "product_x"},
        ),
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
            context={"currency": "EUR"},
        ),
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
            page_context={
                "page_id": "pnl-attribution",
                "selected_rows": [{"portfolio_id": "portfolio_a"}],
            },
        ),
    ],
)
def test_value_scope_constraints_pin_as_non_executable(agent_request):
    pinned, resolution = pin_semantic_execution_request(agent_request)
    snapshot = pinned.context[SEMANTIC_EXECUTION_CONTEXT_KEY]

    assert resolution.semantic_status == "unsupported"
    assert snapshot["required_resources"] == []
    assert validate_semantic_execution_snapshot(snapshot) == snapshot


def test_pinned_value_request_rejects_scope_drift_before_execution():
    pinned, _resolution = pin_semantic_execution_request(
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
        )
    )
    for currency_basis in ("CNX", "USD"):
        tampered = pinned.model_copy(update={"currency_basis": currency_basis})

        with pytest.raises(ValueError, match="scope conflicts"):
            validate_semantic_execution_request(tampered)
        with pytest.raises(ValueError, match="scope conflicts"):
            resolve_local_request(tampered)

    for request_update in (
        {"question": "2026-03-31 组合A的正式总损益是多少"},
        {"context": {**pinned.context, "portfolio_id": "portfolio_a"}},
    ):
        tampered = pinned.model_copy(update=request_update)
        with pytest.raises(ValueError, match="scope conflicts"):
            validate_semantic_execution_request(tampered)
        with pytest.raises(ValueError, match="scope conflicts"):
            resolve_local_request(tampered)


def test_definition_ignores_data_scope_but_explicit_value_intent_requires_resubmit():
    definition = resolve_local_request(
        AgentQueryRequest(
            question="正式总损益是什么",
            basis="scenario",
            currency_basis="USD",
            context={"current_filters": {"portfolio_name": "portfolio_a"}},
        )
    )
    assert definition.semantic_operation == "definition"
    assert definition.semantic_status == "resolved"

    conflict = resolve_local_request(
        AgentQueryRequest(
            question="正式总损益是什么",
            context={"intent": "pnl_summary"},
        )
    )
    assert conflict.semantic_status == "clarification_required"
    assert conflict.semantic_reason_code == "explicit_intent_semantic_conflict"


@pytest.mark.parametrize(
    "question",
    [
        "非标正式总损益是什么",
        "正式FI公允价值变动516是什么",
        "按券的利息收入514如何定义",
        "综本正式总损益口径是什么",
    ],
)
def test_definition_questions_ignore_value_scope_guards(question):
    resolution = resolve_local_request(
        AgentQueryRequest(
            question=question,
            context={"cost_center": "cost_center_a"},
            page_context={
                "page_id": "pnl-attribution",
                "current_filters": {"trading_desk": "desk_a"},
            },
        )
    )

    assert resolution.route == "local"
    assert resolution.semantic_status == "resolved"
    assert resolution.semantic_operation == "definition"


@pytest.mark.parametrize(
    "question",
    [
        "2026-03-31 standardized_total_pnl value",
        "2026-03-31 subtotal_pnl value",
        "2026-03-31 non-total_pnl value",
        "2026-03-31 不是正式总损益是多少",
        "不要查正式总损益是多少",
        "2026-03-31 无需查询正式总损益是多少",
        "2026-03-31 非正式总损益是多少",
        "2026-03-31 BOND514 是多少",
        "请问收益是多少",
        "这个月收益是多少",
        "2026-03-31 收益是多少",
        "2026-03-31 的利息收入是多少",
    ],
)
def test_ambiguous_near_match_and_negated_terms_never_auto_fetch(question):
    resolution = resolve_local_request(AgentQueryRequest(question=question))

    assert resolution.semantic_status == "clarification_required"
    assert resolution.intent == "ontology_clarification"


@pytest.mark.parametrize(
    ("question", "expected_status", "reason_code"),
    [
        (
            "查询截至 2026-03-31 最近30天正式总损益",
            "unsupported",
            "unsupported_period_query",
        ),
        (
            "查询2026-03-01至31日正式总损益",
            "unsupported",
            "unsupported_period_query",
        ),
        (
            "Show total_pnl over the last seven days ending 2026-03-31",
            "unsupported",
            "unsupported_period_query",
        ),
        (
            "Show the YTD total_pnl as of 2026-03-31",
            "unsupported",
            "unsupported_period_query",
        ),
        (
            "2026-03-31 正式总损益占比是多少",
            "unsupported",
            "unsupported_derived_operation",
        ),
        (
            "Show the percentage of total_pnl on 2026-03-31",
            "unsupported",
            "unsupported_derived_operation",
        ),
        (
            "Show the mean of total_pnl as of 2026-03-31",
            "unsupported",
            "unsupported_derived_operation",
        ),
        (
            "查询2026-03-31正式总损益的绝对值",
            "unsupported",
            "unsupported_derived_operation",
        ),
        (
            "Show total_pnl squared for 2026-03-31",
            "unsupported",
            "unsupported_derived_operation",
        ),
        (
            "查询2026-03-31正式总损益并做归一化处理",
            "unsupported",
            "unsupported_query_scope",
        ),
        (
            "查询 2026-03-31 的正式总损益，剔除现金",
            "unsupported",
            "unsupported_query_scope",
        ),
        (
            "查询2026-03-31正式总损益，扣除现金",
            "unsupported",
            "unsupported_query_scope",
        ),
        (
            "Show total_pnl excluding cash as of 2026-03-31",
            "unsupported",
            "unsupported_query_scope",
        ),
        (
            "不要查询 2026-03-31 的正式总损益",
            "clarification_required",
            "negated_metric_reference",
        ),
        (
            "Don't show total_pnl for 2026-03-31",
            "clarification_required",
            "negated_metric_reference",
        ),
    ],
)
def test_non_single_value_operations_are_non_executable(
    tmp_path,
    question,
    expected_status,
    reason_code,
):
    calls: list[str] = []

    def forbidden_handler(_: AgentQueryRequest) -> dict[str, object]:
        calls.append("called")
        raise AssertionError("non-single-value requests must not call the PnL handler")

    request = AgentQueryRequest(question=question, currency_basis="CNY")
    pinned, resolution = pin_semantic_execution_request(request)
    assert resolution.route == "local"
    assert resolution.semantic_status == expected_status
    assert resolution.semantic_reason_code == reason_code
    assert pinned.context[SEMANTIC_EXECUTION_CONTEXT_KEY]["required_resources"] == []

    envelope = AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"pnl_summary": forbidden_handler},
    ).execute(pinned)
    assert envelope.semantic_context is not None
    assert envelope.semantic_context.status == expected_status
    assert envelope.semantic_context.result_check == "blocked"
    assert envelope.semantic_context.reason_code == reason_code
    assert calls == []


@pytest.mark.parametrize(
    ("question", "filters", "metric_id"),
    [
        ("不要514，只查询2026-03-31的516", {}, "MTR-PNL-002"),
        (
            "Do not query 514; show 516 for 2026-03-31",
            {},
            "MTR-PNL-002",
        ),
        ("查询2026-03-31的正式总损益", {}, "MTR-PNL-005"),
        ("show MTR-PNL-005 for 2026-03-31", {}, "MTR-PNL-005"),
        ("查询正式总损益", {"report_date": "2026-03-31"}, "MTR-PNL-005"),
    ],
)
def test_supported_single_value_selection_still_executes_once(
    tmp_path,
    monkeypatch,
    question,
    filters,
    metric_id,
):
    calls: list[str] = []

    def fake_overview(*, report_date: str, **_: object) -> dict[str, object]:
        calls.append(report_date)
        return _formal_pnl_overview(report_date)

    monkeypatch.setattr(pnl_service, "pnl_overview_envelope", fake_overview)
    request = AgentQueryRequest(
        question=question,
        filters=filters,
        currency_basis="CNY",
    )
    pinned, resolution = pin_semantic_execution_request(request)

    assert resolution.semantic_status == "resolved"
    assert resolution.semantic_operation == "value"
    assert resolution.metric_id == metric_id

    envelope = _ontology_pnl_tool(tmp_path).execute(pinned)
    assert envelope.semantic_context is not None
    assert envelope.semantic_context.result_check == "matched"
    assert [card.metric_id for card in envelope.cards if card.type == "metric"] == [
        metric_id
    ]
    assert calls == ["2026-03-31"]


@pytest.mark.parametrize(
    "mutated_question",
    [
        "查询截至 2026-03-31 最近30天正式总损益",
        "2026-03-31 正式总损益占比是多少",
        "查询 2026-03-31 的正式总损益，剔除现金",
        "不要查询 2026-03-31 的正式总损益",
    ],
)
def test_pinned_raw_value_snapshot_rejects_later_question_drift(mutated_question):
    pinned, _resolution = pin_semantic_execution_request(
        AgentQueryRequest(
            question="查询2026-03-31的正式总损益",
            currency_basis="CNY",
        )
    )
    tampered = pinned.model_copy(update={"question": mutated_question})

    with pytest.raises(ValueError, match="meaning conflicts"):
        validate_semantic_execution_request(tampered)


@pytest.mark.parametrize(
    "question",
    [
        "2026-03-31 的 517 是多少",
        "2026-03-31 capital_gain_517 value",
        "2026-03-31 capital gain value",
        "2026-03-31 的资本利得是多少",
        "2026-03-31 的资本收益是多少",
        "2026-03-31 的处置损益是多少",
    ],
)
def test_known_out_of_scope_pnl_metric_stays_local_without_fetch(tmp_path, question):
    calls: list[str] = []

    def forbidden_handler(_: AgentQueryRequest) -> dict[str, object]:
        calls.append("called")
        raise AssertionError("out-of-scope metrics must not call the formal handler")

    resolution = resolve_local_request(AgentQueryRequest(question=question))
    assert resolution.route == "local"
    assert resolution.semantic_status == "unsupported"
    assert resolution.intent == "ontology_unsupported"
    assert resolution.semantic_reason_code == "unsupported_metric"

    envelope = AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"pnl_summary": forbidden_handler},
    ).execute(AgentQueryRequest(question=question))
    assert envelope.semantic_context is not None
    assert envelope.semantic_context.status == "unsupported"
    assert envelope.semantic_context.result_check == "blocked"
    assert envelope.cards == []
    assert calls == []


@pytest.mark.parametrize(
    "question",
    [
        "2026-03-31 组合A的正式总损益是多少",
        "美元的正式总损益是多少",
        "USD正式总损益是多少",
        "EUR正式总损益是多少",
        "JPY正式总损益是多少",
        "HKD正式总损益是多少",
        "GBP正式总损益是多少",
        "欧元的正式总损益是多少",
        "日元的正式总损益是多少",
        "港币的正式总损益是多少",
        "英镑的正式总损益是多少",
        "账户123的利息收入514是多少",
        "产品X的公允价值变动516是多少",
        "固收组合的正式总损益是多少",
        "基金A的正式总损益是多少",
        "资产端正式总损益是多少",
        "负债端正式总损益是多少",
        "固定收益正式总损益是多少",
        "2026-03-31 非标公允价值变动516是多少",
        "2026-03-31 FI公允价值变动516是多少",
        "2026-03-31 正式FI公允价值变动516是多少",
        "2026-03-31 金融投资公允价值变动516是多少",
        "2026-03-31 交易台A的公允价值变动516是多少",
        "2026-03-31 台账A的公允价值变动516是多少",
        "2026-03-31 成本中心A的公允价值变动516是多少",
        "2026-03-31 业务类型为债券的公允价值变动516是多少",
        "2026-03-31 按券查询公允价值变动516是多少",
        "2026-03-31 单券公允价值变动516是多少",
        "2026-03-31 券种公允价值变动516是多少",
        "2026-03-31 综本公允价值变动516是多少",
        "2026-03-31 CNX公允价值变动516是多少",
        "AC账户的正式总损益是多少",
        "FVOCI的正式总损益是多少",
        "FVTPL的正式总损益是多少",
    ],
)
def test_natural_language_scope_is_blocked_without_fetch(tmp_path, question):
    calls: list[str] = []

    def forbidden_handler(_: AgentQueryRequest) -> dict[str, object]:
        calls.append("called")
        raise AssertionError("unsupported scopes must not call the formal handler")

    request = AgentQueryRequest(question=question, currency_basis="CNY")
    resolution = resolve_local_request(request)
    assert resolution.route == "local"
    assert resolution.semantic_status == "unsupported"
    assert resolution.semantic_reason_code == "unsupported_query_scope"

    envelope = AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"pnl_summary": forbidden_handler},
    ).execute(request)
    assert envelope.semantic_context is not None
    assert envelope.semantic_context.status == "unsupported"
    assert envelope.semantic_context.result_check == "blocked"
    assert envelope.cards == []
    assert calls == []


@pytest.mark.parametrize(
    "scope_key",
    [
        "cost_center",
        "source_kind",
        "business_type",
        "trading_desk",
        "instrument",
    ],
)
@pytest.mark.parametrize(
    "scope_container",
    ["context", "context.current_filters", "page_context.current_filters"],
)
def test_context_business_scope_is_blocked_before_formal_read(
    tmp_path,
    scope_key,
    scope_container,
):
    calls: list[str] = []

    def forbidden_handler(_: AgentQueryRequest) -> dict[str, object]:
        calls.append("called")
        raise AssertionError("context scope must stop before formal PnL read")

    request_kwargs: dict[str, object] = {}
    if scope_container == "context":
        request_kwargs["context"] = {scope_key: "scope_a"}
    elif scope_container == "context.current_filters":
        request_kwargs["context"] = {"current_filters": {scope_key: "scope_a"}}
    else:
        request_kwargs["page_context"] = {
            "page_id": "pnl-attribution",
            "current_filters": {scope_key: "scope_a"},
        }
    request = AgentQueryRequest(
        question="2026-03-31 的公允价值变动516是多少",
        currency_basis="CNY",
        **request_kwargs,
    )

    resolution = resolve_local_request(request)
    assert resolution.route == "local"
    assert resolution.semantic_status == "unsupported"
    assert resolution.semantic_reason_code == "unsupported_query_scope"

    envelope = AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"pnl_summary": forbidden_handler},
    ).execute(request)
    assert envelope.semantic_context is not None
    assert envelope.semantic_context.status == "unsupported"
    assert calls == []


def test_malformed_context_current_filters_is_blocked():
    resolution = resolve_local_request(
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
            context={"current_filters": "cost_center=cost_center_a"},
        )
    )

    assert resolution.semantic_status == "unsupported"
    assert resolution.semantic_reason_code == "unsupported_query_scope"


def test_definition_clarification_and_unsupported_do_not_call_financial_handler(tmp_path):
    calls: list[str] = []

    def forbidden_handler(_: AgentQueryRequest) -> dict[str, object]:
        calls.append("called")
        raise AssertionError("semantic no-data paths must not call a financial handler")

    tool = AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"pnl_summary": forbidden_handler},
    )

    definition = tool.execute(AgentQueryRequest(question="正式总损益是什么"))
    assert definition.semantic_context is not None
    assert definition.semantic_context.status == "resolved"
    assert definition.semantic_context.result_check == "not_applicable"
    assert definition.cards[0].metric_id == "MTR-PNL-005"
    assert definition.result_meta.formal_use_allowed is False
    assert definition.evidence.evidence_rows == 0

    clarification = tool.execute(AgentQueryRequest(question="利息收入是多少"))
    assert clarification.semantic_context is not None
    assert clarification.semantic_context.status == "clarification_required"
    assert clarification.semantic_context.result_check == "blocked"

    unsupported = tool.execute(
        AgentQueryRequest(question="为什么公允价值变动下降")
    )
    assert unsupported.semantic_context is not None
    assert unsupported.semantic_context.status == "unsupported"
    assert unsupported.semantic_context.result_check == "blocked"
    assert calls == []


@pytest.mark.parametrize(
    ("question", "metric_id", "source_field", "display_value"),
    [
        (
            "2026-03-31 的利息收入（514）是多少",
            "MTR-PNL-001",
            "interest_income_514",
            "10.00 元",
        ),
        (
            "2026-03-31 的公允价值变动是多少",
            "MTR-PNL-002",
            "fair_value_change_516",
            "20.00 元",
        ),
        (
            "2026-03-31 的正式总损益是多少",
            "MTR-PNL-005",
            "total_pnl",
            "60.00 元",
        ),
    ],
)
def test_metric_value_reuses_formal_overview_and_propagates_metadata(
    tmp_path,
    monkeypatch,
    question,
    metric_id,
    source_field,
    display_value,
):
    captured: dict[str, str] = {}

    def fake_overview(*, duckdb_path: str, governance_dir: str, report_date: str):
        captured.update(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            report_date=report_date,
        )
        return _formal_pnl_overview(report_date)

    monkeypatch.setattr(pnl_service, "pnl_overview_envelope", fake_overview)
    envelope = _ontology_pnl_tool(tmp_path).execute(
        AgentQueryRequest(
            question=question,
            currency_basis="CNY",
            context={"user_id": "user_a"},
        )
    )

    assert captured == {
        "duckdb_path": "test.duckdb",
        "governance_dir": str(tmp_path),
        "report_date": "2026-03-31",
    }
    assert envelope.semantic_context is not None
    assert envelope.semantic_context.status == "resolved"
    assert envelope.semantic_context.result_check == "matched"
    assert envelope.semantic_context.upstream_result_kind == "pnl.overview"
    assert envelope.semantic_context.upstream_trace_id == "tr_pnl_overview_2026-03-31"
    assert len(envelope.cards) == 1
    assert envelope.cards[0].metric_id == metric_id
    assert envelope.cards[0].value == display_value
    assert envelope.cards[0].spec["source_field"] == source_field
    assert envelope.cards[0].spec["raw_unit"] == "yuan"
    assert envelope.cards[0].spec["raw_precision"] == 2
    if metric_id == "MTR-PNL-002":
        assert envelope.cards[0].spec["raw_value"] == "20.00"
        assert envelope.cards[0].spec["raw_value"] != "60.00"
    assert envelope.result_meta.result_kind == "agent.pnl_summary"
    assert envelope.result_meta.formal_use_allowed is True
    assert envelope.result_meta.source_version == "sv_pnl_formal"
    assert envelope.result_meta.rule_version == "rv_pnl_formal"
    assert envelope.result_meta.cache_version == "cv_pnl_formal"
    assert envelope.result_meta.cache_key == "pnl_materialized"
    assert envelope.result_meta.source_surface == "formal_pnl"
    assert envelope.result_meta.amount_currency_basis == "CNY"
    assert envelope.result_meta.data_built_at is not None
    assert envelope.result_meta.generated_at.isoformat().startswith("2026-04-01")
    assert envelope.next_drill == []
    assert envelope.result_meta.next_drill == []
    assert envelope.suggested_actions == []
    assert envelope.evidence.filters_applied["report_date"] == "2026-03-31"
    assert envelope.evidence.filters_applied["requested_position_scope"] == "all"
    assert envelope.evidence.filters_applied["requested_currency_basis"] == "CNY"
    assert "position_scope" not in envelope.evidence.filters_applied
    assert "currency_basis" not in envelope.evidence.filters_applied


def test_legacy_pnl_summary_preserves_existing_drills_and_actions(
    tmp_path,
    monkeypatch,
):
    class StubPnlRepository:
        def __init__(self, path: str):
            assert path == "test.duckdb"

        def list_union_report_dates(self) -> list[str]:
            return ["2026-03-31"]

    monkeypatch.setattr(agent_service, "PnlRepository", StubPnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "pnl_overview_envelope",
        lambda *, report_date, **_: _formal_pnl_overview(report_date),
    )

    envelope = _ontology_pnl_tool(tmp_path).execute(
        AgentQueryRequest(
            question="Summarize PnL",
            context={"intent": "pnl_summary", "user_id": "user_a"},
        )
    )

    assert [drill.dimension for drill in envelope.next_drill] == [
        "instrument",
        "portfolio",
    ]
    assert envelope.result_meta.next_drill == envelope.next_drill
    assert [action.type for action in envelope.suggested_actions] == [
        "inspect_lineage",
        "inspect_drill",
    ]
    assert envelope.suggested_actions[0].payload["metric_key"] == "total_pnl"


@pytest.mark.parametrize(
    "upstream_currency_basis",
    ["CNY", "RMB"],
)
def test_metric_value_matches_normalized_upstream_currency_basis(
    tmp_path,
    monkeypatch,
    upstream_currency_basis,
):
    upstream = _formal_pnl_overview("2026-03-31")
    upstream["result_meta"]["amount_currency_basis"] = upstream_currency_basis
    monkeypatch.setattr(pnl_service, "pnl_overview_envelope", lambda **_: upstream)

    envelope = _ontology_pnl_tool(tmp_path).execute(
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.semantic_context is not None
    assert envelope.semantic_context.result_check == "matched"
    assert envelope.cards[0].metric_id == "MTR-PNL-005"


@pytest.mark.parametrize(
    ("meta_update", "result_update", "reason_code"),
    [
        ({"formal_use_allowed": False}, {}, "upstream_formal_use_not_allowed"),
        ({"fallback_mode": "latest_snapshot"}, {}, "upstream_fallback_not_allowed"),
        ({"basis": "analytical"}, {}, "upstream_basis_mismatch"),
        ({"source_surface": "formal_balance"}, {}, "upstream_source_surface_mismatch"),
        ({"resolved_report_date": "2026-03-30"}, {}, "resolved_report_date_mismatch"),
        ({"trace_id": ""}, {}, "upstream_trace_id_missing"),
        ({"source_version": ""}, {}, "upstream_source_version_missing"),
        ({"rule_version": ""}, {}, "upstream_rule_version_missing"),
        ({"cache_version": ""}, {}, "upstream_cache_version_missing"),
        (
            {"amount_currency_basis": None},
            {},
            "upstream_amount_currency_basis_missing",
        ),
        (
            {"amount_currency_basis": "CNX"},
            {},
            "upstream_amount_currency_basis_mismatch",
        ),
        ({}, {"report_date": "2026-03-30"}, "result_report_date_mismatch"),
    ],
)
def test_metric_binding_mismatch_blocks_fact_value(
    tmp_path,
    monkeypatch,
    meta_update,
    result_update,
    reason_code,
):
    upstream = _formal_pnl_overview("2026-03-31")
    upstream = deepcopy(upstream)
    upstream["result_meta"].update(meta_update)
    upstream["result"].update(result_update)
    monkeypatch.setattr(
        pnl_service,
        "pnl_overview_envelope",
        lambda **_: upstream,
    )

    envelope = _ontology_pnl_tool(tmp_path).execute(
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.semantic_context is not None
    assert envelope.semantic_context.result_check == "blocked"
    assert envelope.semantic_context.reason_code == reason_code
    assert envelope.result_meta.formal_use_allowed is False
    assert all(card.type != "metric" for card in envelope.cards)
    assert "60.00 元" not in envelope.answer


def test_conflicting_dates_clarify_without_calling_formal_overview(tmp_path, monkeypatch):
    calls: list[str] = []

    def forbidden_overview(**_: object):
        calls.append("called")
        raise AssertionError("date conflict must stop before formal PnL read")

    monkeypatch.setattr(pnl_service, "pnl_overview_envelope", forbidden_overview)
    envelope = _ontology_pnl_tool(tmp_path).execute(
        AgentQueryRequest(
            question="查询 2026-03-31 的正式总损益",
            currency_basis="CNY",
            filters={"report_date": "2026-03-30"},
            context={"user_id": "user_a"},
        )
    )

    assert envelope.semantic_context is not None
    assert envelope.semantic_context.status == "clarification_required"
    assert envelope.semantic_context.reason_code == "report_date_conflict"
    assert calls == []


def test_zero_metric_value_is_preserved_as_zero(tmp_path, monkeypatch):
    upstream = _formal_pnl_overview("2026-03-31")
    upstream["result"]["fair_value_change_516"] = "0.00"
    monkeypatch.setattr(
        pnl_service,
        "pnl_overview_envelope",
        lambda **_: upstream,
    )

    envelope = _ontology_pnl_tool(tmp_path).execute(
        AgentQueryRequest(
            question="2026-03-31 的公允价值变动是多少",
            currency_basis="CNY",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.semantic_context is not None
    assert envelope.semantic_context.result_check == "matched"
    assert envelope.cards[0].value == "0.00 元"
    assert envelope.cards[0].spec["raw_value"] == "0.00"


def test_missing_target_metric_field_blocks_without_zero_substitution(
    tmp_path,
    monkeypatch,
):
    upstream = _formal_pnl_overview("2026-03-31")
    del upstream["result"]["interest_income_514"]
    monkeypatch.setattr(
        pnl_service,
        "pnl_overview_envelope",
        lambda **_: upstream,
    )

    envelope = _ontology_pnl_tool(tmp_path).execute(
        AgentQueryRequest(
            question="2026-03-31 的利息收入（514）是多少",
            currency_basis="CNY",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.semantic_context is not None
    assert envelope.semantic_context.result_check == "blocked"
    assert envelope.semantic_context.reason_code == "metric_value_missing"
    assert all(card.type != "metric" for card in envelope.cards)
    assert "0.00 元" not in envelope.answer


@pytest.mark.parametrize(
    ("agent_request", "expected_status", "reason_code"),
    [
        (
            AgentQueryRequest(
                question="2026-02-30 的利息收入（514）是多少",
                currency_basis="CNY",
            ),
            "clarification_required",
            "invalid_report_date",
        ),
        (
            AgentQueryRequest(
                question="2026-03-31 的利息收入（514）是多少",
                currency_basis="CNY",
                filters={"portfolio_name": "portfolio_a"},
            ),
            "unsupported",
            "unsupported_query_scope",
        ),
        (
            AgentQueryRequest(
                question="2026-03-31 的利息收入（514）是多少",
                currency_basis="USD",
            ),
            "unsupported",
            "unsupported_query_scope",
        ),
    ],
)
def test_invalid_date_and_unsupported_scopes_stop_before_formal_read(
    tmp_path,
    agent_request,
    expected_status,
    reason_code,
):
    calls: list[str] = []

    def forbidden_handler(_: AgentQueryRequest) -> dict[str, object]:
        calls.append("called")
        raise AssertionError("invalid or unsupported request must not read formal PnL")

    envelope = AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={"pnl_summary": forbidden_handler},
    ).execute(agent_request)

    assert envelope.semantic_context is not None
    assert envelope.semantic_context.status == expected_status
    assert envelope.semantic_context.reason_code == reason_code
    assert envelope.semantic_context.result_check == "blocked"
    assert calls == []


def test_missing_report_date_data_returns_blocked_semantic_result(tmp_path, monkeypatch):
    def missing_overview(**_: object):
        raise ValueError(
            "No pnl data found for report_date=2026-03-31 in formal sources."
        )

    monkeypatch.setattr(pnl_service, "pnl_overview_envelope", missing_overview)
    envelope = _ontology_pnl_tool(tmp_path).execute(
        AgentQueryRequest(
            question="2026-03-31 的正式总损益是多少",
            currency_basis="CNY",
            context={"user_id": "user_a"},
        )
    )

    assert envelope.semantic_context is not None
    assert envelope.semantic_context.status == "resolved"
    assert envelope.semantic_context.result_check == "blocked"
    assert envelope.semantic_context.reason_code == "upstream_data_unavailable"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.cards[0].type == "status"
    assert all(card.type != "metric" for card in envelope.cards)


def test_ontology_unavailable_snapshot_stays_local_and_requires_retry_after_recovery(
    tmp_path,
    monkeypatch,
):
    def unavailable():
        raise OSError("ontology unavailable")

    monkeypatch.setattr(resolution_runtime, "load_ontology_index", unavailable)
    monkeypatch.setattr(resolution_runtime, "ontology_content_revision", unavailable)
    request = AgentQueryRequest(question="正式总损益是什么")

    pinned, resolution = pin_semantic_execution_request(request)
    snapshot = pinned.context[SEMANTIC_EXECUTION_CONTEXT_KEY]
    assert resolution.semantic_status == "unavailable"
    assert snapshot["ontology_revision"] == "unavailable"
    assert validate_semantic_execution_snapshot(snapshot) == snapshot

    envelope = AnalysisViewTool(
        "test.duckdb",
        str(tmp_path),
        intent_handlers={
            "pnl_summary": lambda _: pytest.fail(
                "unavailable ontology must not call formal PnL"
            )
        },
    ).execute(pinned)
    assert envelope.semantic_context is not None
    assert envelope.semantic_context.status == "unavailable"
    assert envelope.semantic_context.result_check == "blocked"
    assert envelope.evidence.evidence_rows == 0

    monkeypatch.setattr(
        resolution_runtime,
        "ontology_content_revision",
        lambda: "sha256:recovered",
    )
    with pytest.raises(ValueError, match="no longer current"):
        validate_semantic_execution_snapshot(snapshot)


@pytest.mark.parametrize(
    "question",
    [
        "2026-03-31 的 514 是多少",
        "2026-03-31 的 total_pnl 是多少",
    ],
)
def test_ontology_unavailable_technical_aliases_do_not_escape_to_provider(
    monkeypatch,
    question,
):
    monkeypatch.setattr(
        resolution_runtime,
        "load_ontology_index",
        lambda: (_ for _ in ()).throw(OSError("ontology unavailable")),
    )

    resolution = resolve_local_request(AgentQueryRequest(question=question))

    assert resolution.route == "local"
    assert resolution.intent == "ontology_unavailable"
    assert resolution.semantic_status == "unavailable"


def test_semantic_query_writes_context_to_agent_audit(tmp_path, monkeypatch):
    captured = []
    monkeypatch.setattr(
        agent_service,
        "append_agent_audit",
        lambda _repo, payload: captured.append(payload),
    )
    monkeypatch.setattr(
        pnl_service,
        "pnl_overview_envelope",
        lambda *, report_date, **_: _formal_pnl_overview(report_date),
    )

    envelope = agent_service.execute_agent_query(
        AgentQueryRequest(
            question="2026-03-31 的利息收入（514）是多少",
            currency_basis="CNY",
            context={"user_id": "user_a"},
        ),
        "test.duckdb",
        str(tmp_path),
    )

    assert envelope.semantic_context is not None
    assert len(captured) == 1
    semantic_audit = captured[0].result_meta["semantic_context"]
    assert semantic_audit["status"] == "resolved"
    assert semantic_audit["result_check"] == "matched"
    assert semantic_audit["references"][0]["entity_id"] == "MTR-PNL-001"
    assert semantic_audit["upstream_result_kind"] == "pnl.overview"
    assert captured[0].filters_applied["report_date"] == "2026-03-31"
    assert captured[0].filters_applied["requested_position_scope"] == "all"
    assert captured[0].filters_applied["requested_currency_basis"] == "CNY"
    assert "position_scope" not in captured[0].filters_applied
    assert "currency_basis" not in captured[0].filters_applied
