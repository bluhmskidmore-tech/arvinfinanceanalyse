"""home_snapshot_envelope 内存 TTL 缓存的单元测试。

验证:
  - 同一 (report_date, allow_partial) 第二次调用命中缓存，不重算
  - 不同 key 各自独立计算
  - 显式 invalidate 后下一次重新计算
  - TTL 过期后自动重新计算
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.app.services import executive_service as es


@pytest.fixture(autouse=True)
def _reset_cache():
    es.invalidate_home_snapshot_cache()
    yield
    es.invalidate_home_snapshot_cache()


def _fake_envelope(tag: str) -> dict[str, object]:
    """构造一个最小可识别的 envelope，便于断言 cache 是否真的命中。"""
    return {
        "result_meta": {"trace_id": tag},
        "result": {"report_date": "2026-04-08", "tag": tag},
    }


def test_second_call_with_same_key_hits_cache_and_skips_computation() -> None:
    with patch.object(es, "_compute_home_snapshot_envelope") as mock_compute:
        mock_compute.return_value = _fake_envelope("first")

        env1 = es.home_snapshot_envelope(report_date=None, allow_partial=False)
        env2 = es.home_snapshot_envelope(report_date=None, allow_partial=False)

        assert mock_compute.call_count == 1
        # 缓存命中应当返回完全相同的 envelope 引用
        assert env1 is env2
        assert env1["result"]["tag"] == "first"


def test_different_keys_are_cached_independently() -> None:
    with patch.object(es, "_compute_home_snapshot_envelope") as mock_compute:
        # 每次调用按当前 call_count 返回不同 envelope
        mock_compute.side_effect = lambda **kwargs: _fake_envelope(
            f"{kwargs['report_date']}|{kwargs['allow_partial']}"
        )

        a = es.home_snapshot_envelope(report_date="2026-04-08", allow_partial=False)
        b = es.home_snapshot_envelope(report_date="2026-04-08", allow_partial=True)
        c = es.home_snapshot_envelope(report_date="2026-04-07", allow_partial=False)

        # 同一 key 第二次命中
        a2 = es.home_snapshot_envelope(report_date="2026-04-08", allow_partial=False)

        assert mock_compute.call_count == 3
        assert a["result"]["tag"] == "2026-04-08|False"
        assert b["result"]["tag"] == "2026-04-08|True"
        assert c["result"]["tag"] == "2026-04-07|False"
        assert a2 is a


def test_invalidate_forces_recomputation() -> None:
    with patch.object(es, "_compute_home_snapshot_envelope") as mock_compute:
        mock_compute.side_effect = [
            _fake_envelope("v1"),
            _fake_envelope("v2"),
        ]

        env1 = es.home_snapshot_envelope(report_date=None, allow_partial=False)
        es.invalidate_home_snapshot_cache()
        env2 = es.home_snapshot_envelope(report_date=None, allow_partial=False)

        assert mock_compute.call_count == 2
        assert env1["result"]["tag"] == "v1"
        assert env2["result"]["tag"] == "v2"


def test_ttl_expiry_triggers_recomputation(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch.object(es, "_compute_home_snapshot_envelope") as mock_compute:
        mock_compute.side_effect = [
            _fake_envelope("v1"),
            _fake_envelope("v2"),
        ]

        # 用一个可控的 monotonic 时钟驱动 TTL
        clock = {"t": 1000.0}
        monkeypatch.setattr(es.time, "monotonic", lambda: clock["t"])

        env1 = es.home_snapshot_envelope(report_date=None, allow_partial=False)
        # 推进到 TTL 之后 1 秒
        clock["t"] += es._HOME_SNAPSHOT_CACHE_TTL_SECONDS + 1
        env2 = es.home_snapshot_envelope(report_date=None, allow_partial=False)

        assert mock_compute.call_count == 2
        assert env1["result"]["tag"] == "v1"
        assert env2["result"]["tag"] == "v2"


def test_within_ttl_window_keeps_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """边界用例：刚好 TTL 即将到期但尚未过期，应当继续命中。"""
    with patch.object(es, "_compute_home_snapshot_envelope") as mock_compute:
        mock_compute.return_value = _fake_envelope("v1")

        clock = {"t": 1000.0}
        monkeypatch.setattr(es.time, "monotonic", lambda: clock["t"])

        env1 = es.home_snapshot_envelope(report_date=None, allow_partial=False)
        clock["t"] += es._HOME_SNAPSHOT_CACHE_TTL_SECONDS - 0.1
        env2 = es.home_snapshot_envelope(report_date=None, allow_partial=False)

        assert mock_compute.call_count == 1
        assert env1 is env2
