import os
import sys

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker

from backend.app.governance.settings import get_settings

broker: StubBroker | RedisBroker | None = None


def _should_use_stub_broker() -> bool:
    if str(get_settings().environment).lower() == "production":
        return False
    if os.getenv("MOSS_REDIS_DSN"):
        return False
    return "pytest" in sys.modules or bool(os.getenv("PYTEST_CURRENT_TEST"))


def get_broker() -> StubBroker | RedisBroker:
    global broker

    if broker is None:
        broker = StubBroker() if _should_use_stub_broker() else RedisBroker(url=get_settings().redis_dsn)
        if str(get_settings().environment).lower() == "production" and isinstance(broker, StubBroker):
            raise RuntimeError("Production worker bootstrap cannot use StubBroker.")
        dramatiq.set_broker(broker)
    return broker


def register_actor_once(actor_name: str, fn):
    active_broker = get_broker()
    existing = active_broker.actors.get(actor_name)
    if existing is not None:
        existing.fn = fn
        return existing
    return dramatiq.actor(fn, actor_name=actor_name)
