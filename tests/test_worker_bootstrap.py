import ast
from pathlib import Path

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
    broker_module.broker = None
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    monkeypatch.delenv("MOSS_REDIS_DSN", raising=False)

    active = broker_module.get_broker()

    assert active.__class__.__name__ == "RedisBroker"
