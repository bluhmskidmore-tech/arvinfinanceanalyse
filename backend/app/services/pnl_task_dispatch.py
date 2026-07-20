"""PnL task-dispatch identities and lazy actor proxies.

与 backend.app.tasks.pnl_materialize 对齐；只读路径不得 import tasks
（会触发 broker/actor 注册）。常量一致性由
tests/test_lazy_task_import_constants.py 锁定。
"""

from __future__ import annotations

from backend.app.governance.locks import LockDefinition

CACHE_KEY = "pnl:phase2:materialize:formal"
PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY = "pnl:by-business:precompute"
PNL_BY_BUSINESS_PRECOMPUTE_CACHE_VERSION = (
    "cv_pnl_by_business_precompute__rv_pnl_by_business_precompute_v8"
)
PNL_BY_BUSINESS_PRECOMPUTE_JOB_NAME = "pnl_by_business_precompute"
PNL_BY_BUSINESS_PRECOMPUTE_PENDING_SOURCE_VERSION = "sv_pnl_by_business_precompute_pending"
PNL_MATERIALIZE_LOCK = LockDefinition(
    key="lock:duckdb:formal:pnl:phase2:materialize",
    ttl_seconds=900,
)
PNL_RESULT_CACHE_VERSION = "cv_pnl_formal__rv_pnl_phase2_materialize_v3"


class _MaterializePnlFactsProxy:
    def send(self, **kwargs: object) -> object:
        from backend.app.tasks.pnl_materialize import materialize_pnl_facts as _actor

        return _actor.send(**kwargs)

    def __getattr__(self, name: str) -> object:
        from backend.app.tasks.pnl_materialize import materialize_pnl_facts as _actor

        return getattr(_actor, name)


class _RebuildPnlByBusinessPrecomputeProxy:
    def send(self, **kwargs: object) -> object:
        from backend.app.tasks.pnl_materialize import rebuild_pnl_by_business_precompute as _actor

        return _actor.send(**kwargs)

    def __getattr__(self, name: str) -> object:
        from backend.app.tasks.pnl_materialize import rebuild_pnl_by_business_precompute as _actor

        return getattr(_actor, name)

    @property
    def options(self) -> dict[str, object]:
        from backend.app.tasks.pnl_materialize import rebuild_pnl_by_business_precompute as _actor

        return dict(getattr(_actor, "options", {}) or {})


materialize_pnl_facts = _MaterializePnlFactsProxy()
rebuild_pnl_by_business_precompute = _RebuildPnlByBusinessPrecomputeProxy()


def run_pnl_materialize_sync(*args: object, **kwargs: object) -> object:
    from backend.app.tasks.pnl_materialize import run_pnl_materialize_sync as _run

    return _run(*args, **kwargs)
