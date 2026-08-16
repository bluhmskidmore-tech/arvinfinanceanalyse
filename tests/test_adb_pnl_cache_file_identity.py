"""无 TTL 读缓存的 DuckDB 文件身份失效（mtime_ns + size 折入缓存键）。

物化任务可能在另一进程（RedisBroker worker）重写 DuckDB，worker 内的
cache_clear 钩子清不到 API 进程的 lru_cache；缓存键折入文件身份后，
文件重写 -> 键变化 -> 旧条目自然不再命中，无需跨进程清理。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.governance.settings import get_settings

pytestmark = [pytest.mark.integration]


def _point_settings_at(monkeypatch, db_path: Path) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
    get_settings.cache_clear()


def test_adb_comparison_cache_invalidates_when_duckdb_file_changes(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "adb-cache-comparison.duckdb"
    db_path.write_bytes(b"v1")
    _point_settings_at(monkeypatch, db_path)
    from backend.app.services import adb_analysis_service as svc

    svc.clear_adb_comparison_cache()
    calls: list[tuple[str, str, int]] = []

    def _fake_uncached(start_date, end_date, top_n=20):
        calls.append((start_date, end_date, top_n))
        return {"result": {"call_count": len(calls)}}

    monkeypatch.setattr(svc, "_adb_comparison_envelope_uncached", _fake_uncached)
    try:
        first = svc.adb_comparison_envelope("2026-01-01", "2026-01-31", top_n=5)
        second = svc.adb_comparison_envelope("2026-01-01", "2026-01-31", top_n=5)
        assert first == second
        assert len(calls) == 1  # 文件未变：命中缓存

        db_path.write_bytes(b"v2-rewritten-longer")  # 重写文件（size/mtime 变化）
        third = svc.adb_comparison_envelope("2026-01-01", "2026-01-31", top_n=5)
        assert len(calls) == 2  # 文件身份变化：旧缓存键不再命中
        assert third["result"]["call_count"] == 2
    finally:
        svc.clear_adb_comparison_cache()


def test_adb_insights_cache_invalidates_when_duckdb_file_changes(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "adb-cache-insights.duckdb"
    db_path.write_bytes(b"v1")
    _point_settings_at(monkeypatch, db_path)
    from backend.app.services import adb_analysis_service as svc

    svc.clear_adb_insights_cache()
    calls: list[tuple[str, str]] = []

    def _fake_uncached(start_date, end_date):
        calls.append((start_date, end_date))
        return {"result": {"call_count": len(calls)}}

    monkeypatch.setattr(svc, "_adb_insights_envelope_uncached", _fake_uncached)
    try:
        svc.adb_insights_envelope("2026-01-01", "2026-01-31")
        svc.adb_insights_envelope("2026-01-01", "2026-01-31")
        assert len(calls) == 1

        db_path.write_bytes(b"v2-rewritten-longer")
        svc.adb_insights_envelope("2026-01-01", "2026-01-31")
        assert len(calls) == 2
    finally:
        svc.clear_adb_insights_cache()


def test_pnl_by_business_analysis_inputs_cache_invalidates_when_file_changes(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "pnl-cache-inputs.duckdb"
    db_path.write_bytes(b"v1")
    from backend.app.services import pnl_service

    pnl_service._clear_pnl_by_business_analysis_cache()
    fetch_calls: list[str] = []

    class _FakePnlRepository:
        def __init__(self, path: str) -> None:
            self.path = path

        def fetch_by_business_analysis_pnl_rows(self, *, year: int, as_of_date: str):
            fetch_calls.append(f"pnl:{year}:{as_of_date}")
            return [{"business_type": "bond", "total_pnl": "1"}]

        def fetch_by_business_analysis_balance_rows(self, *, start_date: str, end_date: str):
            return [{"report_date": start_date, "balance": "1"}]

    monkeypatch.setattr(pnl_service, "PnlRepository", _FakePnlRepository)
    try:
        first = pnl_service._pnl_by_business_analysis_inputs(
            str(db_path), 2026, "2026-01-01", "2026-03-31"
        )
        second = pnl_service._pnl_by_business_analysis_inputs(
            str(db_path), 2026, "2026-01-01", "2026-03-31"
        )
        assert first == second
        assert len(fetch_calls) == 1  # 文件未变：命中缓存

        db_path.write_bytes(b"v2-rewritten-longer")
        pnl_service._pnl_by_business_analysis_inputs(
            str(db_path), 2026, "2026-01-01", "2026-03-31"
        )
        assert len(fetch_calls) == 2  # 物化重写后：缓存自动失效
    finally:
        pnl_service._clear_pnl_by_business_analysis_cache()
