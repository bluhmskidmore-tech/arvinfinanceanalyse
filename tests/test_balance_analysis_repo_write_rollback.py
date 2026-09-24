"""replace_formal_balance_rows 异常路径：无活动事务时不得因盲目 rollback 掩盖原始异常。

旧实现 `except Exception: conn.execute("rollback"); raise`：当异常发生在两段事务
之间（如 purge 阶段，无活动事务）时，rollback 自身抛出 TransactionException，
替换掉原始异常。修复后对齐 bond_analytics_repo 的 transaction_started 标志模式。
"""
from __future__ import annotations

import pytest

from backend.app.repositories import balance_analysis_repo as repo_module
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.task_write_guard import repository_task_write_scope


def test_replace_formal_balance_rows_propagates_original_error_when_no_txn_active(
    tmp_path, monkeypatch
) -> None:
    def _boom(*_args, **_kwargs):
        raise RuntimeError("purge boom")

    monkeypatch.setattr(repo_module, "commit_report_date_purge", _boom)

    with repository_task_write_scope("backend.app.tasks.balance_analysis_repo_test"):
        with pytest.raises(RuntimeError, match="purge boom"):
            BalanceAnalysisRepository(
                str(tmp_path / "rollback-mask.duckdb")
            ).replace_formal_balance_rows(
                report_date="2026-03-31",
                zqtz_rows=[],
                tyw_rows=[],
            )
