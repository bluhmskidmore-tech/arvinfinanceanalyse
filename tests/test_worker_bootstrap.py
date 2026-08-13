import ast
from pathlib import Path

import dramatiq
import pytest
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker

from tests.helpers import load_module

ROOT = Path(__file__).resolve().parents[1]


def _read_canonical_task_modules() -> tuple[str, ...]:
    bootstrap_path = ROOT / "backend" / "app" / "tasks" / "worker_bootstrap.py"
    tree = ast.parse(bootstrap_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "CANONICAL_TASK_MODULES":
                    return tuple(ast.literal_eval(node.value))
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "CANONICAL_TASK_MODULES"
            and node.value is not None
        ):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("worker_bootstrap.py must define CANONICAL_TASK_MODULES")


def test_worker_bootstrap_declares_canonical_dramatiq_task_modules():
    assert _read_canonical_task_modules() == (
        "backend.app.tasks.dev_health",
        "backend.app.tasks.ingest",
        "backend.app.tasks.materialize",
        "backend.app.tasks.source_preview_refresh",
        "backend.app.tasks.pnl_materialize",
        "backend.app.tasks.balance_analysis_materialize",
        "backend.app.tasks.formal_balance_pipeline",
        "backend.app.tasks.accounting_asset_movement",
        "backend.app.tasks.bond_analytics_materialize",
        "backend.app.tasks.risk_tensor_materialize",
        "backend.app.tasks.product_category_pnl",
        "backend.app.tasks.snapshot_materialize",
        "backend.app.tasks.fx_mid_materialize",
        "backend.app.tasks.commodity_daily_ingest",
        "backend.app.tasks.crisis_score_inputs_refresh",
        "backend.app.tasks.nbs_gdp_release_ingest",
        "backend.app.tasks.choice_macro",
        "backend.app.tasks.tushare_macro_ingest",
        "backend.app.tasks.home_macro_release_refresh",
        "backend.app.tasks.choice_news",
        "backend.app.tasks.stock_factor_refresh",
        "backend.app.tasks.research_calendar_upstream_fetch",
        "backend.app.tasks.choice_stock_refresh",
        "backend.app.tasks.macro_toolkit_refresh",
        "backend.app.tasks.macro_toolkit_freshness_refresh",
        "backend.app.tasks.macro_toolkit_write_refresh",
        "backend.app.tasks.livermore_position_snapshot_materialize",
        "backend.app.tasks.agent_run",
        "backend.app.tasks.agent_run_stream_compaction",
        "backend.app.tasks.livermore_gate_supplement",
        "backend.app.tasks.ledger_import",
    )


def test_worker_bootstrap_loads_canonical_modules_on_import():
    bootstrap_path = ROOT / "backend" / "app" / "tasks" / "worker_bootstrap.py"
    text = bootstrap_path.read_text(encoding="utf-8")
    assert "import_module" in text
    assert "CANONICAL_TASK_MODULES" in text
    assert "get_broker()" in text


def test_worker_bootstrap_includes_task_owned_send_targets():
    modules = set(_read_canonical_task_modules())

    assert "backend.app.tasks.accounting_asset_movement" in modules
    assert "backend.app.tasks.risk_tensor_materialize" in modules


def test_choice_news_task_module_declares_tushare_news_background_actor():
    task_path = ROOT / "backend" / "app" / "tasks" / "choice_news.py"
    text = task_path.read_text(encoding="utf-8")
    assert 'register_actor_once(\n    "ingest_tushare_news_to_choice_news"' in text
    assert "ingest_tushare_news_to_choice_news = register_actor_once" in text



def test_tushare_macro_task_declares_refresh_actor():
    task_path = ROOT / "backend" / "app" / "tasks" / "tushare_macro_ingest.py"
    text = task_path.read_text(encoding="utf-8")
    assert "refresh_tushare_macro = register_actor_once(" in text
    assert '"refresh_tushare_macro"' in text


def test_livermore_gate_supplement_task_disables_hidden_retries():
    task_path = ROOT / "backend" / "app" / "tasks" / "livermore_gate_supplement.py"
    text = task_path.read_text(encoding="utf-8")
    assert 'register_actor_once(\n        "run_livermore_gate_supplement_refresh"' in text
    assert "max_retries=0" in text


def test_broker_uses_redis_broker_in_production_even_under_pytest(monkeypatch):
    broker_module = load_module(
        "backend.app.tasks.broker",
        "backend/app/tasks/broker.py",
    )
    original_dramatiq_broker = dramatiq.get_broker()
    broker_module.broker = None
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    monkeypatch.delenv("MOSS_REDIS_DSN", raising=False)
    dramatiq.set_broker(RedisBroker(url="redis://localhost:6379/0"))

    try:
        active = broker_module.get_broker()
    finally:
        dramatiq.set_broker(original_dramatiq_broker)

    assert active.__class__.__name__ == "RedisBroker"


def test_broker_rejects_preconfigured_stub_broker_in_production(monkeypatch):
    broker_module = load_module(
        "backend.app.tasks.broker",
        "backend/app/tasks/broker.py",
    )
    original_dramatiq_broker = dramatiq.get_broker()
    monkeypatch.setattr(broker_module, "broker", StubBroker())
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    monkeypatch.delenv("MOSS_REDIS_DSN", raising=False)

    try:
        with pytest.raises(RuntimeError, match="production.*StubBroker|StubBroker.*production"):
            broker_module.get_broker()
    finally:
        dramatiq.set_broker(original_dramatiq_broker)


def test_broker_rejects_global_stub_broker_in_production(monkeypatch):
    broker_module = load_module(
        "backend.app.tasks.broker",
        "backend/app/tasks/broker.py",
    )
    original_dramatiq_broker = dramatiq.get_broker()
    monkeypatch.setattr(broker_module, "broker", None)
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    monkeypatch.delenv("MOSS_REDIS_DSN", raising=False)
    dramatiq.set_broker(StubBroker())

    try:
        with pytest.raises(RuntimeError, match="production.*StubBroker|StubBroker.*production"):
            broker_module.get_broker()
    finally:
        dramatiq.set_broker(original_dramatiq_broker)
