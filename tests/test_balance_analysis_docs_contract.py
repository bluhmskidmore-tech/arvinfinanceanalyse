from __future__ import annotations

from pathlib import Path

from tests.helpers import ROOT


def _read_doc(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_balance_analysis_spec_mentions_registered_runtime_path():
    spec = _read_doc("docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md")

    assert "backend/app/core_finance/module_registry.py" in spec
    assert "backend/app/tasks/formal_compute_runtime.py" in spec
    assert "backend/app/services/formal_result_runtime.py" in spec
    assert "API 路由保持显式定义" in spec
    assert "不因为模块注册而自动暴露新路由" in spec


def test_cache_spec_mentions_balance_analysis_basis_scoped_runtime_identity():
    cache_spec = _read_doc("docs/CACHE_SPEC.md")

    assert "balance_analysis:materialize:formal" in cache_spec
    assert "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1" in cache_spec
    assert "不自动推广为其他 formal module 的默认公开接口" in cache_spec


def test_acceptance_tests_track_registry_runtime_and_result_meta_contract_regressions():
    acceptance = _read_doc("docs/acceptance_tests.md")

    assert "tests/test_formal_compute_module_registry.py" in acceptance
    assert "tests/test_formal_compute_runtime_contract.py" in acceptance
    assert "tests/test_formal_compute_result_meta_contract.py" in acceptance
    assert "不构成放宽架构约束的授权" in acceptance
    assert "不得把 snapshot 直读或更多未落地能力写成已完成" in acceptance
