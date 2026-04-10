import dramatiq
from dramatiq.brokers.redis import RedisBroker

from backend.app.governance.settings import get_settings

settings = get_settings()
broker = RedisBroker(url=settings.redis_dsn)
dramatiq.set_broker(broker)


def register_actor_once(actor_name: str, fn):
    existing = broker.actors.get(actor_name)
    if existing is not None:
        existing.fn = fn
        return existing
    return dramatiq.actor(fn, actor_name=actor_name)
