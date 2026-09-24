import ast
import logging
from pathlib import Path
from types import SimpleNamespace

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
        "backend.app.tasks.yield_curve_materialize",
        "backend.app.tasks.tushare_stock_disclosure",
        "backend.app.tasks.risk_coupon_window_repair",
        "backend.app.tasks.bond_dv01_limit_config_import",
        "backend.app.tasks.fx_mid_backfill",
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


def test_newly_canonical_task_modules_import_and_expose_send_targets():
    """B5 审计修复：这 5 个 actor 模块必须能被 worker bootstrap 无副作用导入。"""
    from importlib import import_module

    expectations = {
        "backend.app.tasks.yield_curve_materialize": (
            "materialize_yield_curve",
            "materialize_yield_curve_month_end_backfill",
        ),
        "backend.app.tasks.tushare_stock_disclosure": ("refresh_stock_official_disclosures",),
        "backend.app.tasks.risk_coupon_window_repair": ("repair_risk_coupon_window",),
        "backend.app.tasks.bond_dv01_limit_config_import": ("import_bond_dv01_limit_config",),
        "backend.app.tasks.fx_mid_backfill": ("backfill_fx_mid_history",),
    }
    canonical_modules = set(_read_canonical_task_modules())
    for module_path, actor_attrs in expectations.items():
        assert module_path in canonical_modules
        module = import_module(module_path)
        for attr in actor_attrs:
            actor = getattr(module, attr)
            assert hasattr(actor, "send"), f"{module_path}.{attr} must be a Dramatiq send target"


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


def _fake_settings(redis_dsn: str, fields_set: set[str], environment: str = "development"):
    return SimpleNamespace(
        redis_dsn=redis_dsn,
        model_fields_set=fields_set,
        environment=environment,
    )


def test_broker_uses_redis_when_settings_redis_dsn_configured_outside_pytest(monkeypatch):
    """.env 里的 MOSS_REDIS_DSN（pydantic dotenv 不回写 os.environ）必须被识别。"""
    broker_module = load_module(
        "backend.app.tasks.broker",
        "backend/app/tasks/broker.py",
    )
    monkeypatch.delenv("MOSS_REDIS_DSN", raising=False)
    monkeypatch.delenv("MOSS_ENVIRONMENT", raising=False)
    monkeypatch.setattr(broker_module, "_is_pytest_process", lambda: False)
    monkeypatch.setattr(
        broker_module,
        "get_settings",
        lambda: _fake_settings("redis://127.0.0.1:6399/7", {"redis_dsn"}),
    )

    assert broker_module._should_use_stub_broker() is False


def test_broker_keeps_stub_when_redis_dsn_left_default_outside_pytest(monkeypatch):
    broker_module = load_module(
        "backend.app.tasks.broker",
        "backend/app/tasks/broker.py",
    )
    monkeypatch.delenv("MOSS_REDIS_DSN", raising=False)
    monkeypatch.delenv("MOSS_ENVIRONMENT", raising=False)
    monkeypatch.setattr(broker_module, "_is_pytest_process", lambda: False)
    monkeypatch.setattr(
        broker_module,
        "get_settings",
        lambda: _fake_settings("redis://localhost:6379/0", set()),
    )

    assert broker_module._should_use_stub_broker() is True


def test_broker_keeps_stub_under_pytest_even_when_dotenv_configures_redis(monkeypatch):
    broker_module = load_module(
        "backend.app.tasks.broker",
        "backend/app/tasks/broker.py",
    )
    monkeypatch.delenv("MOSS_REDIS_DSN", raising=False)
    monkeypatch.delenv("MOSS_ENVIRONMENT", raising=False)
    monkeypatch.setattr(
        broker_module,
        "get_settings",
        lambda: _fake_settings("redis://127.0.0.1:6399/7", {"redis_dsn"}),
    )

    assert broker_module._should_use_stub_broker() is True


def test_stub_broker_send_warns_outside_pytest(monkeypatch, caplog):
    broker_module = load_module(
        "backend.app.tasks.broker",
        "backend/app/tasks/broker.py",
    )
    stub = broker_module._DevStubBroker()
    actor = dramatiq.actor(lambda: None, actor_name="b5_stub_send_probe", broker=stub)
    monkeypatch.setattr(broker_module, "_is_pytest_process", lambda: False)

    with caplog.at_level(logging.WARNING, logger="backend.app.tasks.broker"):
        actor.send()

    warnings = [record for record in caplog.records if "b5_stub_send_probe" in record.getMessage()]
    assert warnings, "expected a StubBroker send warning outside pytest"
    assert "background worker" in warnings[0].getMessage()


def test_stub_broker_send_stays_quiet_under_pytest(caplog):
    broker_module = load_module(
        "backend.app.tasks.broker",
        "backend/app/tasks/broker.py",
    )
    stub = broker_module._DevStubBroker()
    actor = dramatiq.actor(lambda: None, actor_name="b5_stub_quiet_probe", broker=stub)

    with caplog.at_level(logging.WARNING, logger="backend.app.tasks.broker"):
        actor.send()

    assert not [record for record in caplog.records if "b5_stub_quiet_probe" in record.getMessage()]


def test_choice_macro_declares_refresh_actor_via_register_actor_once():
    task_path = ROOT / "backend" / "app" / "tasks" / "choice_macro.py"
    text = task_path.read_text(encoding="utf-8")
    assert "@dramatiq.actor" not in text
    assert 'refresh_choice_macro_snapshot = register_actor_once(\n    "refresh_choice_macro_snapshot"' in text


def test_choice_macro_refresh_actor_uses_project_channel_options():
    from backend.app.tasks import choice_macro

    actor = choice_macro.refresh_choice_macro_snapshot
    assert actor.actor_name == "refresh_choice_macro_snapshot"
    assert actor.options["max_retries"] == 3
    assert actor.options["time_limit"] == 3_600_000
    assert callable(actor.fn)
