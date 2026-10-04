import ast
import logging
from pathlib import Path
from threading import Event, Thread, current_thread
from types import SimpleNamespace

import dramatiq
import pytest
from dramatiq.broker import MessageProxy
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker
from dramatiq.middleware import Retries

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
        "backend.app.tasks.pnl_by_business_page_publication",
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
        "backend.app.tasks.stock_adjustment_factor_daily_refresh",
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
    assert text.index("LOADED_TASK_MODULES =") < text.index(
        "register_worker_recovery_middleware(active_broker)"
    )


def test_expired_ack_maintenance_uses_broker_dispatch_and_restores_probability():
    from backend.app.tasks.broker import run_expired_redis_ack_maintenance

    class FakeRedisBroker:
        maintenance_chance = 1000
        delay_queues = {"default.DQ"}

        def __init__(self):
            self.calls: list[tuple[str, int]] = []

        def get_declared_queues(self):
            return {"default"}

        def do_qsize(self, queue_name):
            self.calls.append((queue_name, self.maintenance_chance))
            return 2

    broker = FakeRedisBroker()

    result = run_expired_redis_ack_maintenance(broker)  # type: ignore[arg-type]

    assert broker.calls == [
        ("default", 1_000_000),
        ("default.DQ", 1_000_000),
    ]
    assert broker.maintenance_chance == 1000
    assert result == {
        "status": "completed",
        "queue_count": 2,
        "observed_sizes": {"default": 2, "default.DQ": 2},
    }


def test_worker_recovery_separates_intent_recovery_from_ack_maintenance(monkeypatch):
    from backend.app.tasks import worker_recovery

    class FakeRedisBroker:
        heartbeat_timeout = 20

    recovered = Event()
    maintained = Event()
    events: list[str] = []
    middleware = worker_recovery.WorkerRecoveryMiddleware(
        recovery=lambda: events.append("intent") or recovered.set() or 0,
        ack_maintenance=lambda _broker: (
            events.append("ack") or maintained.set() or {"queue_count": 1}
        ),
        maintenance_grace_seconds=0,
    )
    monkeypatch.setattr(worker_recovery, "RedisBroker", FakeRedisBroker)

    middleware.after_worker_boot(FakeRedisBroker(), object())

    assert recovered.wait(0.1)
    assert maintained.wait(1)
    assert events == ["intent", "ack"]


def test_worker_recovery_persists_successful_page_actor_receipt(tmp_path):
    from backend.app.repositories.governance_repo import (
        CACHE_BUILD_RUN_STREAM,
        GovernanceRepository,
    )
    from backend.app.tasks import worker_recovery

    governance_dir = tmp_path / "governance"
    message = SimpleNamespace(
        actor_name="prepare_pnl_by_business_page_envelope",
        kwargs={
            "run_id": "page-run-completed",
            "governance_dir": str(governance_dir),
            "year": 2026,
            "as_of_date": "2026-08-31",
        },
    )

    persisted = worker_recovery.persist_pnl_by_business_page_completion(
        message,
        {
            "status": "completed",
            "run_id": "page-run-completed",
            "year": 2026,
            "report_date": "2026-08-31",
            "generation": "financial-20260831-example",
            "publication_status": "published",
            "resource_limits": {"status": "within_budget"},
        },
    )

    assert persisted is True
    record = GovernanceRepository(base_dir=governance_dir).read_all(
        CACHE_BUILD_RUN_STREAM
    )[-1]
    assert record["status"] == "completed"
    assert record["generation"] == "financial-20260831-example"
    assert record["protocol_version"] == "pnl_by_business_page_intent/v1"
    assert record["resource_limits"] == {"status": "within_budget"}


def test_worker_recovery_persists_failure_only_after_retries_exhausted(tmp_path):
    from backend.app.repositories.governance_repo import (
        CACHE_BUILD_RUN_STREAM,
        GovernanceRepository,
    )
    from backend.app.tasks import worker_recovery

    governance_dir = tmp_path / "governance"
    broker = StubBroker(middleware=[Retries()])
    actor = dramatiq.actor(
        lambda **_kwargs: None,
        actor_name="prepare_pnl_by_business_page_envelope",
        broker=broker,
        max_retries=1,
    )
    middleware = worker_recovery.register_worker_recovery_middleware(broker)
    message = MessageProxy(
        actor.message_with_options(
            kwargs={
                "run_id": "page-run-failed",
                "governance_dir": str(governance_dir),
                "year": 2026,
                "as_of_date": "2026-08-31",
            }
        )
    )
    failure = RuntimeError("publication failed")

    broker.emit_after("process_message", message, exception=failure)

    assert message.failed is False
    assert GovernanceRepository(base_dir=governance_dir).read_all(
        CACHE_BUILD_RUN_STREAM
    ) == []

    broker.emit_after("process_message", message, exception=failure)

    assert message.failed is True
    records = GovernanceRepository(base_dir=governance_dir).read_all(
        CACHE_BUILD_RUN_STREAM
    )
    assert len(records) == 1
    assert records[0]["status"] == "failed"
    assert records[0]["failure_category"] == "actor_terminal_failure"
    assert records[0]["terminal_reason"] == "retries_exhausted"
    assert records[0]["retries"] == 2
    assert records[0]["max_retries"] == 1
    assert not worker_recovery.persist_pnl_by_business_page_terminal_failure(
        message,
        failure,
        broker=broker,
    )
    assert len(
        GovernanceRepository(base_dir=governance_dir).read_all(
            CACHE_BUILD_RUN_STREAM
        )
    ) == 1
    assert broker.middleware.index(middleware) < next(
        index
        for index, item in enumerate(broker.middleware)
        if isinstance(item, Retries)
    )


@pytest.mark.parametrize(
    ("actor_options", "failure", "terminal_reason"),
    (
        ({"throws": (ValueError,)}, ValueError("invalid input"), "declared_non_retryable"),
        (
            {"retry_when": lambda _retries, _exception: False},
            RuntimeError("retry policy rejected"),
            "retry_policy_rejected",
        ),
    ),
)
def test_worker_recovery_classifies_other_terminal_failures(
    tmp_path,
    actor_options,
    failure,
    terminal_reason,
):
    from backend.app.repositories.governance_repo import (
        CACHE_BUILD_RUN_STREAM,
        GovernanceRepository,
    )
    from backend.app.tasks import worker_recovery

    governance_dir = tmp_path / terminal_reason
    broker = StubBroker(middleware=[Retries()])
    actor = dramatiq.actor(
        lambda **_kwargs: None,
        actor_name="prepare_pnl_by_business_page_envelope",
        broker=broker,
        **actor_options,
    )
    worker_recovery.register_worker_recovery_middleware(broker)
    message = MessageProxy(
        actor.message_with_options(
            kwargs={
                "run_id": f"page-run-{terminal_reason}",
                "governance_dir": str(governance_dir),
                "year": 2026,
                "as_of_date": "2026-08-31",
            }
        )
    )

    broker.emit_after("process_message", message, exception=failure)

    assert message.failed is True
    records = GovernanceRepository(base_dir=governance_dir).read_all(
        CACHE_BUILD_RUN_STREAM
    )
    assert len(records) == 1
    assert records[0]["failure_category"] == "actor_terminal_failure"
    assert records[0]["terminal_reason"] == terminal_reason


def test_worker_ack_recovery_retries_and_can_restart_after_thread_exit(monkeypatch):
    from backend.app.tasks import worker_recovery

    class FakeRedisBroker:
        heartbeat_timeout = 0

    attempts: list[int] = []
    first_pass_completed = Event()
    second_pass_completed = Event()

    def maintain(_broker):
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            raise ConnectionError("redis temporarily unavailable")
        if len(attempts) == 2:
            first_pass_completed.set()
        else:
            second_pass_completed.set()
        return {"queue_count": 1}

    middleware = worker_recovery.WorkerRecoveryMiddleware(
        recovery=lambda: 0,
        ack_maintenance=maintain,
        maintenance_grace_seconds=0,
        maintenance_retry_seconds=0.01,
    )
    monkeypatch.setattr(worker_recovery, "RedisBroker", FakeRedisBroker)

    middleware.after_worker_boot(FakeRedisBroker(), object())
    assert first_pass_completed.wait(1)
    first_thread = middleware._maintenance_thread
    if first_thread is not None:
        first_thread.join(1)
    assert middleware._maintenance_thread is None

    middleware.after_worker_boot(FakeRedisBroker(), object())
    assert second_pass_completed.wait(1)
    second_thread = middleware._maintenance_thread
    if second_thread is not None:
        second_thread.join(1)
    assert middleware._maintenance_thread is None
    assert attempts == [1, 2, 3]


def test_stale_failure_callback_does_not_override_completed_page_receipt(tmp_path):
    from backend.app.repositories.governance_repo import (
        CACHE_BUILD_RUN_STREAM,
        GovernanceRepository,
    )
    from backend.app.tasks import worker_recovery

    governance_dir = tmp_path / "governance"
    message = SimpleNamespace(
        actor_name="prepare_pnl_by_business_page_envelope",
        kwargs={
            "run_id": "page-run-completed-before-failure",
            "governance_dir": str(governance_dir),
            "year": 2026,
            "as_of_date": "2026-08-31",
        },
        options={"retries": 2, "max_retries": 1},
        failed=True,
    )
    assert worker_recovery.persist_pnl_by_business_page_completion(
        message,
        {
            "status": "completed",
            "run_id": "page-run-completed-before-failure",
            "year": 2026,
            "report_date": "2026-08-31",
            "generation": "financial-20260831-complete",
        },
    )

    assert not worker_recovery.persist_pnl_by_business_page_terminal_failure(
        message,
        RuntimeError("late duplicate failed"),
    )

    records = GovernanceRepository(base_dir=governance_dir).read_all(
        CACHE_BUILD_RUN_STREAM
    )
    assert len(records) == 1
    assert records[0]["status"] == "completed"


def test_page_receipt_lock_serializes_failure_before_success(tmp_path, monkeypatch):
    from backend.app.repositories.governance_repo import (
        CACHE_BUILD_RUN_STREAM,
        GovernanceRepository,
    )
    from backend.app.tasks import worker_recovery

    governance_dir = tmp_path / "governance"
    run_id = "page-run-concurrent-terminal-callbacks"
    repository = GovernanceRepository(base_dir=governance_dir)
    repository.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": "pnl_by_business_page_prepare",
            "cache_key": "pnl_by_business_page_prepare",
            "status": "queued",
        },
    )
    failure_read_complete = Event()
    release_failure = Event()
    success_done = Event()
    errors: list[BaseException] = []
    original_latest = worker_recovery._latest_page_run_status

    def paused_latest(active_repository, *, run_id):
        status = original_latest(active_repository, run_id=run_id)
        if current_thread().name == "failure-receipt":
            failure_read_complete.set()
            assert release_failure.wait(2)
        return status

    monkeypatch.setattr(worker_recovery, "_latest_page_run_status", paused_latest)
    message = SimpleNamespace(
        actor_name="prepare_pnl_by_business_page_envelope",
        kwargs={
            "run_id": run_id,
            "governance_dir": str(governance_dir),
            "year": 2026,
            "as_of_date": "2026-08-31",
        },
        options={"retries": 2, "max_retries": 1},
        failed=True,
    )

    def write_failure():
        try:
            worker_recovery.persist_pnl_by_business_page_terminal_failure(
                message,
                RuntimeError("terminal failure"),
            )
        except BaseException as exc:
            errors.append(exc)

    def write_success():
        try:
            worker_recovery.persist_pnl_by_business_page_completion(
                message,
                {
                    "status": "completed",
                    "run_id": run_id,
                    "year": 2026,
                    "report_date": "2026-08-31",
                    "generation": "financial-20260831-concurrent",
                },
            )
        except BaseException as exc:
            errors.append(exc)
        finally:
            success_done.set()

    failure_thread = Thread(target=write_failure, name="failure-receipt")
    success_thread = Thread(target=write_success, name="success-receipt")
    failure_thread.start()
    assert failure_read_complete.wait(1)
    success_thread.start()
    try:
        assert not success_done.wait(0.2)
    finally:
        release_failure.set()
    failure_thread.join(2)
    success_thread.join(2)

    assert not failure_thread.is_alive()
    assert not success_thread.is_alive()
    assert errors == []
    records = [
        record
        for record in repository.read_by_cache_keys(
            CACHE_BUILD_RUN_STREAM,
            ("pnl_by_business_page_prepare",),
        )
        if record.get("run_id") == run_id
    ]
    assert [record["status"] for record in records] == [
        "queued",
        "failed",
        "completed",
    ]


def test_page_receipt_status_lookup_uses_cache_key_scope():
    from backend.app.tasks import worker_recovery

    calls: list[tuple[str, tuple[str, ...]]] = []

    class ScopedRepository:
        def read_by_cache_keys(self, stream, cache_keys):
            calls.append((stream, tuple(cache_keys)))
            return [
                {
                    "run_id": "target-run",
                    "job_name": "pnl_by_business_page_prepare",
                    "status": "completed",
                }
            ]

        def read_all(self, _stream):
            raise AssertionError("receipt lookup must not scan the full governance stream")

    assert (
        worker_recovery._latest_page_run_status(
            ScopedRepository(),  # type: ignore[arg-type]
            run_id="target-run",
        )
        == "completed"
    )
    assert calls == [
        (
            "cache_build_run",
            ("pnl_by_business_page_prepare",),
        )
    ]


def test_worker_ack_recovery_uses_capped_backoff_and_throttled_logs(
    caplog,
):
    from backend.app.tasks import worker_recovery

    class FakeRedisBroker:
        pass

    class FakeShutdown:
        def __init__(self):
            self.waits: list[float] = []

        def wait(self, seconds):
            self.waits.append(seconds)
            return len(self.waits) == 5

        def is_set(self):
            return False

    shutdown = FakeShutdown()
    middleware = worker_recovery.WorkerRecoveryMiddleware(
        recovery=lambda: 0,
        ack_maintenance=lambda _broker: (_ for _ in ()).throw(
            ConnectionError("redis unavailable")
        ),
        maintenance_retry_seconds=1,
        maintenance_max_retry_seconds=4,
    )
    middleware._shutdown = shutdown  # type: ignore[assignment]

    with caplog.at_level(logging.WARNING, logger="backend.app.tasks.worker_recovery"):
        middleware._maintain_after_heartbeat_timeout(FakeRedisBroker(), 0)  # type: ignore[arg-type]

    assert shutdown.waits == [0, 1, 2, 4, 4]
    warnings = [
        record
        for record in caplog.records
        if "Redis ACK maintenance failed" in record.getMessage()
    ]
    assert len(warnings) == 3
    assert "attempt 1" in warnings[0].getMessage()
    assert "attempt 2" in warnings[1].getMessage()
    assert "attempt 4" in warnings[2].getMessage()


def test_worker_startup_requests_intent_recovery_without_pending_dirty(monkeypatch):
    from backend.app.tasks import data_update_center, worker_recovery

    settings = object()
    calls: list[tuple[object, bool]] = []

    def recover(active_settings, *, include_pending_dirty=True):
        calls.append((active_settings, include_pending_dirty))
        return 0

    monkeypatch.setattr(worker_recovery, "get_settings", lambda: settings)
    monkeypatch.setattr(
        data_update_center,
        "_recover_pending_pnl_by_business_precompute",
        recover,
    )

    assert worker_recovery.recover_durable_business_intents() == 0
    assert calls == [(settings, False)]


def test_startup_intent_recovery_keeps_adjustment_and_page_without_dirty_scan(
    tmp_path,
    monkeypatch,
):
    from backend.app.repositories import pnl_repo
    from backend.app.services import pnl_by_business_page_lifecycle, pnl_service
    from backend.app.tasks.data_update_center import (
        _recover_pending_pnl_by_business_precompute,
    )

    calls: list[str] = []

    class UnexpectedDirtyRepository:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("startup must not scan pending dirty state")

    monkeypatch.setattr(pnl_repo, "PnlRepository", UnexpectedDirtyRepository)
    monkeypatch.setattr(
        pnl_service,
        "recover_pending_pnl_by_business_precompute",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("startup must not dispatch pending dirty state")
        ),
    )
    monkeypatch.setattr(
        pnl_service,
        "recover_pending_pnl_by_business_adjustment_handoffs",
        lambda _settings: calls.append("adjustment") or [],
    )
    monkeypatch.setattr(
        pnl_by_business_page_lifecycle,
        "recover_pending_pnl_by_business_page_rebuilds",
        lambda _settings: calls.append("page") or {"failed_count": 0},
    )
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        governance_path=tmp_path / "governance",
    )

    assert (
        _recover_pending_pnl_by_business_precompute(
            settings,
            include_pending_dirty=False,
        )
        == 0
    )
    assert calls == ["adjustment", "page"]


def test_worker_bootstrap_includes_task_owned_send_targets():
    modules = set(_read_canonical_task_modules())

    assert "backend.app.tasks.accounting_asset_movement" in modules
    assert "backend.app.tasks.risk_tensor_materialize" in modules


def test_newly_canonical_task_modules_import_and_expose_send_targets():
    """审计修复：新增 canonical actor 模块必须能被 worker bootstrap 无副作用导入。"""
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
        "backend.app.tasks.stock_adjustment_factor_daily_refresh": (
            "refresh_stock_adjustment_factors_for_trade_date_task",
        ),
        "backend.app.tasks.pnl_by_business_page_publication": (
            "prepare_pnl_by_business_page_envelope_actor",
        ),
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
