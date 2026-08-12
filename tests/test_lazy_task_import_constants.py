"""锁住 service/repo 内联身份常量与对应 task 模块一致（延迟导入回归）。"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_risk_tensor_service_identity_constants_match_task_module() -> None:
    import backend.app.services.risk_tensor_service as service
    import backend.app.tasks.risk_tensor_materialize as task

    assert service.CACHE_KEY == task.CACHE_KEY
    assert service.CACHE_VERSION == task.CACHE_VERSION
    assert service.RULE_VERSION == task.RULE_VERSION


def test_risk_tensor_repo_bond_analytics_cache_key_matches_task_module() -> None:
    import backend.app.repositories.risk_tensor_repo as repo
    import backend.app.tasks.bond_analytics_materialize as task

    assert repo.BOND_ANALYTICS_CACHE_KEY == task.CACHE_KEY


def test_executive_service_cache_keys_match_task_modules() -> None:
    import backend.app.services.executive_service as service
    import backend.app.tasks.bond_analytics_materialize as bond_task
    import backend.app.tasks.pnl_materialize as pnl_task

    assert service.BOND_ANALYTICS_CACHE_KEY == bond_task.CACHE_KEY
    assert service.PNL_CACHE_KEY == pnl_task.CACHE_KEY


def test_bond_analytics_service_identity_constants_match_task_modules() -> None:
    import backend.app.services.bond_analytics_service as service
    import backend.app.tasks.bond_analytics_materialize as bond_task
    import backend.app.tasks.yield_curve_materialize as yield_task

    assert service.CACHE_KEY == bond_task.CACHE_KEY
    assert service.CACHE_VERSION == bond_task.CACHE_VERSION
    assert service.RULE_VERSION == bond_task.RULE_VERSION
    assert service.BOND_ANALYTICS_LOCK.key == bond_task.BOND_ANALYTICS_LOCK.key
    assert service.BOND_ANALYTICS_LOCK.ttl_seconds == bond_task.BOND_ANALYTICS_LOCK.ttl_seconds
    assert service.YIELD_CURVE_CACHE_VERSION == yield_task.CACHE_VERSION


def test_bond_dashboard_service_rule_version_matches_task_module() -> None:
    import backend.app.services.bond_dashboard_service as service
    import backend.app.tasks.bond_analytics_materialize as bond_task

    assert service.BOND_ANALYTICS_RULE_VERSION == bond_task.RULE_VERSION


def test_pnl_service_identity_constants_match_task_module() -> None:
    import backend.app.services.pnl_service as service
    import backend.app.tasks.pnl_materialize as task

    assert service.CACHE_KEY == task.CACHE_KEY
    assert service.PNL_RESULT_CACHE_VERSION == task.PNL_RESULT_CACHE_VERSION
    assert service.PNL_MATERIALIZE_LOCK.key == task.PNL_MATERIALIZE_LOCK.key
    assert service.PNL_MATERIALIZE_LOCK.ttl_seconds == task.PNL_MATERIALIZE_LOCK.ttl_seconds
    assert service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY == task.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY
    assert service.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION == task.PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION
    assert service.PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME == task.PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME
    assert (
        service.PNL_BY_BUSINESS_PRECOMPUTE_PENDING_SOURCE_VERSION
        == task.PNL_BY_BUSINESS_PRECOMPUTE_PENDING_SOURCE_VERSION
    )


def test_pnl_bridge_service_identity_constants_match_task_modules() -> None:
    import backend.app.services.pnl_bridge_service as service
    import backend.app.tasks.balance_analysis_materialize as balance_task
    import backend.app.tasks.pnl_materialize as pnl_task
    import backend.app.tasks.yield_curve_materialize as yield_task

    assert service.BALANCE_ANALYSIS_CACHE_KEY == balance_task.CACHE_KEY
    assert service.BALANCE_ANALYSIS_CACHE_VERSION == balance_task.CACHE_VERSION
    assert service.BALANCE_ANALYSIS_RULE_VERSION == balance_task.RULE_VERSION
    assert service.PNL_CACHE_KEY == pnl_task.CACHE_KEY
    assert service.PNL_RESULT_CACHE_VERSION == pnl_task.PNL_RESULT_CACHE_VERSION
    assert service.YIELD_CURVE_CACHE_VERSION == yield_task.CACHE_VERSION


def test_product_category_pnl_service_identity_constants_match_task_module() -> None:
    import backend.app.services.product_category_pnl_service as service
    import backend.app.tasks.product_category_pnl as task

    assert service.PRODUCT_CATEGORY_ADJUSTMENT_STREAM == task.PRODUCT_CATEGORY_ADJUSTMENT_STREAM
    assert service.PRODUCT_CATEGORY_PNL_LOCK.key == task.PRODUCT_CATEGORY_PNL_LOCK.key
    assert service.PRODUCT_CATEGORY_PNL_LOCK.ttl_seconds == task.PRODUCT_CATEGORY_PNL_LOCK.ttl_seconds


def test_source_preview_refresh_service_identity_constants_match_task_module() -> None:
    import backend.app.services.source_preview_refresh_service as service
    import backend.app.tasks.source_preview_refresh as task

    assert service.SOURCE_PREVIEW_REFRESH_JOB_NAME == task.SOURCE_PREVIEW_REFRESH_JOB_NAME
    assert service.SOURCE_PREVIEW_REFRESH_CACHE_KEY == task.SOURCE_PREVIEW_REFRESH_CACHE_KEY
    assert service.SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES == task.SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES


def test_macro_toolkit_service_import_does_not_load_tasks_modules() -> None:
    """冷导入 macro_toolkit_service 不得经 cffex 等路径加载 backend.app.tasks*。"""
    code = (
        "import sys; "
        "import backend.app.services.macro_toolkit_service; "
        "loaded = sorted(m for m in sys.modules if m.startswith('backend.app.tasks')); "
        "assert not loaded, loaded"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr


def test_lazy_actor_proxies_delegate_fn_and_allow_instance_override() -> None:
    proxy_specs = (
        (
            "backend.app.services.pnl_task_dispatch",
            "materialize_pnl_facts",
            "backend.app.tasks.pnl_materialize",
            "materialize_pnl_facts",
        ),
        (
            "backend.app.services.pnl_task_dispatch",
            "rebuild_pnl_by_business_precompute",
            "backend.app.tasks.pnl_materialize",
            "rebuild_pnl_by_business_precompute",
        ),
        (
            "backend.app.services.balance_analysis_service",
            "materialize_balance_analysis_facts",
            "backend.app.tasks.balance_analysis_materialize",
            "materialize_balance_analysis_facts",
        ),
        (
            "backend.app.api.routes.adb_analysis",
            "materialize_balance_analysis_facts",
            "backend.app.tasks.balance_analysis_materialize",
            "materialize_balance_analysis_facts",
        ),
        (
            "backend.app.services.bond_analytics_service",
            "materialize_bond_analytics_facts",
            "backend.app.tasks.bond_analytics_materialize",
            "materialize_bond_analytics_facts",
        ),
        (
            "backend.app.services.accounting_asset_movement_service",
            "refresh_accounting_asset_movement_window",
            "backend.app.tasks.accounting_asset_movement",
            "refresh_accounting_asset_movement_window",
        ),
        (
            "backend.app.services.macro_toolkit_service",
            "run_commodity_daily_ingest_task",
            "backend.app.tasks.commodity_daily_ingest",
            "run_commodity_daily_ingest_task",
        ),
        (
            "backend.app.services.product_category_pnl_service",
            "materialize_product_category_pnl",
            "backend.app.tasks.product_category_pnl",
            "materialize_product_category_pnl",
        ),
        (
            "backend.app.services.source_preview_refresh_service",
            "refresh_source_preview_cache",
            "backend.app.tasks.source_preview_refresh",
            "refresh_source_preview_cache",
        ),
    )
    replacement = object()

    for proxy_module_name, proxy_name, actor_module_name, actor_name in proxy_specs:
        proxy = getattr(importlib.import_module(proxy_module_name), proxy_name)
        actor = getattr(importlib.import_module(actor_module_name), actor_name)

        assert proxy.fn is actor.fn
        setattr(proxy, "fn", replacement)
        try:
            assert proxy.fn is replacement
        finally:
            delattr(proxy, "fn")
        assert proxy.fn is actor.fn
