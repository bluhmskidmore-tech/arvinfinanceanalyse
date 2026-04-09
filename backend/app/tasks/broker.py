import dramatiq
from dramatiq.brokers.redis import RedisBroker

from backend.app.governance.settings import get_settings

settings = get_settings()
broker = RedisBroker(url=settings.redis_dsn)
dramatiq.set_broker(broker)
