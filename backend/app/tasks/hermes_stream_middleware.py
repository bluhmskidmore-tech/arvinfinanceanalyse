from __future__ import annotations

import logging
from typing import Any

from backend.app.governance.settings import get_settings
from backend.app.services.hermes_agent_service import (
    stop_managed_hermes_stream,
    warm_hermes_stream_if_configured,
)
from dramatiq.middleware import Middleware

_LOGGER = logging.getLogger(__name__)


class HermesStreamRuntimeMiddleware(Middleware):
    """Own the Lab-only resident Hermes runner inside each worker process."""

    def after_process_boot(self, broker: Any) -> None:
        del broker
        try:
            warmed = warm_hermes_stream_if_configured(get_settings())
        except Exception as exc:  # noqa: BLE001 - warmup must not block worker boot
            _LOGGER.warning(
                "Hermes stream prewarm failed error_type=%s "
                "error_code=hermes_stream_prewarm_failed",
                exc.__class__.__name__,
            )
            return
        if warmed:
            _LOGGER.info("Hermes stream runtime ready")

    def before_worker_shutdown(self, broker: Any, worker: Any) -> None:
        del broker, worker
        try:
            stop_managed_hermes_stream()
        except Exception as exc:  # noqa: BLE001 - shutdown cleanup is best effort
            _LOGGER.warning(
                "Hermes stream shutdown failed error_type=%s "
                "error_code=hermes_stream_shutdown_failed",
                exc.__class__.__name__,
            )


def register_hermes_stream_runtime_middleware(broker: Any) -> bool:
    if any(isinstance(item, HermesStreamRuntimeMiddleware) for item in broker.middleware):
        return False
    broker.add_middleware(HermesStreamRuntimeMiddleware())
    return True
