"""版本化的「用户问法 -> 预期本地路由」基准集回归。

基准集本身是 `tests/fixtures/agent_intent_eval_set.v1.json`，作为
`docs/prd-ontology-agent-pnl.md` 第十一节要求的固定问法与路由基线；
本文件只负责逐条回放并在失败时按 intent 汇总错误，便于一次看清回归面。
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

from backend.app.agent.runtime.local_request_resolution import (
    LocalRequestResolution,
    resolve_local_request,
)
from backend.app.agent.schemas.agent_request import AgentQueryRequest

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]

EVAL_SET_PATH = Path(__file__).resolve().parent / "fixtures" / "agent_intent_eval_set.v1.json"
MINIMUM_CASE_COUNT = 80


def _load_eval_set() -> dict[str, Any]:
    return json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))


def _build_request(case: dict[str, Any]) -> AgentQueryRequest:
    kwargs: dict[str, Any] = {"question": case["question"]}
    for key in ("context", "filters", "page_context"):
        if key in case:
            kwargs[key] = case[key]
    return AgentQueryRequest(**kwargs)


def _comparable(
    case: dict[str, Any],
    resolution: LocalRequestResolution,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_case = case["expected"]
    expected: dict[str, Any] = {
        "route": expected_case["route"],
        "clarification_reason": expected_case.get("clarification_reason"),
    }
    actual: dict[str, Any] = {
        "route": resolution.route,
        "clarification_reason": (
            resolution.semantic_reason_code
            if resolution.semantic_status == "clarification_required"
            else None
        ),
    }
    # 澄清用例不断言 intent：澄清复用 ontology_clarification 这一承载意图，
    # 真正的候选业务 intent 在 resolution.intent_candidates 上。
    if expected["clarification_reason"] is None:
        expected["intent"] = expected_case.get("intent")
        actual["intent"] = resolution.intent
    return expected, actual


def test_eval_set_is_well_formed_and_covers_every_local_keyword_intent() -> None:
    from backend.app.agent.runtime.local_request_resolution import _INTENT_PATTERNS

    eval_set = _load_eval_set()
    cases = eval_set["cases"]
    assert eval_set["schema_version"] == 1
    assert len(cases) >= MINIMUM_CASE_COUNT

    case_ids = [case["case_id"] for case in cases]
    assert len(case_ids) == len(set(case_ids)), "case_id 必须唯一"

    for case in cases:
        expected = case["expected"]
        assert case["question"].strip(), case["case_id"]
        assert expected["route"] in {"local", "provider"}, case["case_id"]
        assert (
            expected.get("intent") is not None
            or expected.get("clarification_reason") is not None
            or expected["route"] == "provider"
        ), f"{case['case_id']} 必须给出 intent 或 clarification_reason"
        assert case.get("note", "").strip(), f"{case['case_id']} 需要说明锁定的行为"

    covered = {case["expected"].get("intent") for case in cases}
    missing = [intent for intent, _keywords in _INTENT_PATTERNS if intent not in covered]
    assert missing == [], f"基准集缺少这些 intent 的正例：{missing}"


def test_local_request_routing_matches_the_pinned_eval_set() -> None:
    cases = _load_eval_set()["cases"]
    failures: list[tuple[str, dict[str, Any], dict[str, Any], str]] = []
    for case in cases:
        expected, actual = _comparable(
            case,
            resolve_local_request(_build_request(case)),
        )
        if actual != expected:
            failures.append((case["case_id"], expected, actual, case["question"]))

    if failures:
        grouped: dict[str, list[str]] = defaultdict(list)
        for case_id, expected, actual, question in failures:
            bucket = (
                expected.get("intent")
                or expected["clarification_reason"]
                or expected["route"]
            )
            grouped[bucket].append(
                f"    {case_id} | {question}\n"
                f"      expected={expected}\n"
                f"      actual  ={actual}"
            )
        report = [f"{len(failures)}/{len(cases)} 条基准问法路由不符，按预期结果分组："]
        for bucket in sorted(grouped):
            report.append(f"  [{bucket}] {len(grouped[bucket])} 条")
            report.extend(grouped[bucket])
        pytest.fail("\n".join(report))
