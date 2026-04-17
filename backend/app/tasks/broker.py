import os
import sys

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker

from backend.app.governance.settings import get_settings

broker: StubBroker | RedisBroker | None = None
DEFAULT_MAX_RETRIES = 20
DEFAULT_MIN_BACKOFF_MS = 15_000
DEFAULT_TIME_LIMIT_MS = 600_000


def _is_pytest_process() -> bool:
    return "pytest" in sys.modules or bool(os.getenv("PYTEST_CURRENT_TEST"))


def _is_production_environment() -> bool:
    env_value = os.getenv("MOSS_ENVIRONMENT")
    if env_value is not None:
        return str(env_value).lower() == "production"
    if _is_pytest_process():
        return False
    return str(get_settings().environment).lower() == "production"


def _should_use_stub_broker() -> bool:
    if os.getenv("MOSS_REDIS_DSN"):
        return False
    if _is_production_environment():
        return False
    if _is_pytest_process():
        return True
    return str(get_settings().environment).lower() != "production"


def get_broker() -> StubBroker | RedisBroker:
    global broker

    if isinstance(broker, StubBroker) and _is_production_environment():
        raise RuntimeError("production environment cannot use a preconfigured StubBroker for task execution")
    if isinstance(dramatiq.get_broker(), StubBroker) and _is_production_environment():
        raise RuntimeError("production environment cannot use a global StubBroker for task execution")

    if broker is None:
        broker = StubBroker() if _should_use_stub_broker() else RedisBroker(url=get_settings().redis_dsn)
        dramatiq.set_broker(broker)
    return broker


def register_actor_once(
    actor_name: str,
    fn,
    max_retries: int = 3,
    time_limit_ms: int = 3_600_000,
):
    active_broker = get_broker()
    options = {
        "max_retries": max_retries,
        "min_backoff": DEFAULT_MIN_BACKOFF_MS,
        "time_limit": time_limit_ms,
    }
    existing = active_broker.actors.get(actor_name)
    if existing is not None:
        existing.fn = fn
        existing.options.update(options)
        return existing
    return dramatiq.actor(fn, actor_name=actor_name, **options)
