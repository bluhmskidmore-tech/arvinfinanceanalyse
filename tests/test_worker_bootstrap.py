import ast
from pathlib import Path
import sys

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
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "CANONICAL_TASK_MODULES":
                return tuple(ast.literal_eval(node.value))
    raise AssertionError("worker_bootstrap.py must define CANONICAL_TASK_MODULES")


def _clear_worker_bootstrap_runtime_modules() -> None:
    sys.modules.pop("backend.app.tasks.worker_bootstrap", None)
    sys.modules.pop("backend.app.tasks.broker", None)
    for module_name in _read_canonical_task_modules():
        sys.modules.pop(module_name, None)


def test_worker_bootstrap_declares_canonical_dramatiq_task_modules():
    assert _read_canonical_task_modules() == (
        "backend.app.tasks.dev_health",
        "backend.app.tasks.ingest",
        "backend.app.tasks.materialize",
        "backend.app.tasks.source_preview_refresh",
        "backend.app.tasks.pnl_materialize",
        "backend.app.tasks.balance_analysis_materialize",
        "backend.app.tasks.formal_balance_pipeline",
        "backend.app.tasks.bond_analytics_materialize",
        "backend.app.tasks.product_category_pnl",
        "backend.app.tasks.snapshot_materialize",
        "backend.app.tasks.fx_mid_materialize",
        "backend.app.tasks.fx_mid_backfill",
        "backend.app.tasks.risk_tensor_materialize",
        "backend.app.tasks.yield_curve_materialize",
        "backend.app.tasks.choice_macro",
        "backend.app.tasks.choice_news",
    )


def test_worker_bootstrap_loads_canonical_modules_on_import():
    bootstrap_path = ROOT / "backend" / "app" / "tasks" / "worker_bootstrap.py"
    text = bootstrap_path.read_text(encoding="utf-8")
    assert "import_module" in text
    assert "CANONICAL_TASK_MODULES" in text
    assert "get_broker()" in text


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


def test_worker_bootstrap_registers_all_canonical_actor_surfaces():
    _clear_worker_bootstrap_runtime_modules()

    worker_bootstrap = load_module(
        "backend.app.tasks.worker_bootstrap",
        "backend/app/tasks/worker_bootstrap.py",
    )
    broker_module = sys.modules["backend.app.tasks.broker"]
    active_broker = broker_module.get_broker()

    assert worker_bootstrap.LOADED_TASK_MODULES
    assert "backfill_fx_mid_history" in active_broker.actors
    assert "materialize_risk_tensor_facts" in active_broker.actors
    assert "materialize_yield_curve" in active_broker.actors


def test_worker_bootstrap_actors_set_explicit_retry_and_time_limit_defaults():
    _clear_worker_bootstrap_runtime_modules()

    load_module(
        "backend.app.tasks.worker_bootstrap",
        "backend/app/tasks/worker_bootstrap.py",
    )
    broker_module = sys.modules["backend.app.tasks.broker"]
    active_broker = broker_module.get_broker()

    for actor_name, actor in active_broker.actors.items():
        assert actor.options.get("max_retries") == 20, actor_name
        assert actor.options.get("min_backoff") == 15000, actor_name
        assert actor.options.get("time_limit") == 600000, actor_name


def test_register_actor_once_refreshes_existing_actor_defaults(monkeypatch):
    broker_module = load_module(
        "backend.app.tasks.broker",
        "backend/app/tasks/broker.py",
    )
    original_dramatiq_broker = dramatiq.get_broker()
    monkeypatch.setattr(broker_module, "broker", None)
    monkeypatch.delenv("MOSS_ENVIRONMENT", raising=False)
    monkeypatch.delenv("MOSS_REDIS_DSN", raising=False)

    def first_impl():
        return "first"

    def replacement_impl():
        return "replacement"

    try:
        actor = broker_module.register_actor_once("test_refresh_existing_actor", first_impl)
        actor.options["max_retries"] = 1
        actor.options["min_backoff"] = 2
        actor.options["time_limit"] = 3

        refreshed = broker_module.register_actor_once("test_refresh_existing_actor", replacement_impl)
    finally:
        dramatiq.set_broker(original_dramatiq_broker)

    assert refreshed is actor
    assert refreshed.fn is replacement_impl
    assert refreshed.options["max_retries"] == 20
    assert refreshed.options["min_backoff"] == 15000
    assert refreshed.options["time_limit"] == 600000
