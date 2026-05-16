from __future__ import annotations

import threading
from unittest.mock import patch

import pytest

from backend.app.services import executive_service as es


@pytest.fixture(autouse=True)
def _reset_cache():
    es.invalidate_home_snapshot_cache()
    yield
    es.invalidate_home_snapshot_cache()


def _fake_envelope(tag: str) -> dict[str, object]:
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
        assert env1 == env2
        assert env1 is not env2
        assert env1["result"]["tag"] == "first"


def test_different_keys_are_cached_independently() -> None:
    with patch.object(es, "_compute_home_snapshot_envelope") as mock_compute:
        mock_compute.side_effect = lambda **kwargs: _fake_envelope(
            f"{kwargs['report_date']}|{kwargs['allow_partial']}"
        )

        a = es.home_snapshot_envelope(report_date="2026-04-08", allow_partial=False)
        b = es.home_snapshot_envelope(report_date="2026-04-08", allow_partial=True)
        c = es.home_snapshot_envelope(report_date="2026-04-07", allow_partial=False)
        a2 = es.home_snapshot_envelope(report_date="2026-04-08", allow_partial=False)

        assert mock_compute.call_count == 3
        assert a["result"]["tag"] == "2026-04-08|False"
        assert b["result"]["tag"] == "2026-04-08|True"
        assert c["result"]["tag"] == "2026-04-07|False"
        assert a2 == a
        assert a2 is not a


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

        clock = {"t": 1000.0}
        monkeypatch.setattr(es.time, "monotonic", lambda: clock["t"])

        env1 = es.home_snapshot_envelope(report_date=None, allow_partial=False)
        clock["t"] += es._HOME_SNAPSHOT_CACHE_TTL_SECONDS + 1
        env2 = es.home_snapshot_envelope(report_date=None, allow_partial=False)

        assert mock_compute.call_count == 2
        assert env1["result"]["tag"] == "v1"
        assert env2["result"]["tag"] == "v2"


def test_within_ttl_window_keeps_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch.object(es, "_compute_home_snapshot_envelope") as mock_compute:
        mock_compute.return_value = _fake_envelope("v1")

        clock = {"t": 1000.0}
        monkeypatch.setattr(es.time, "monotonic", lambda: clock["t"])

        env1 = es.home_snapshot_envelope(report_date=None, allow_partial=False)
        clock["t"] += es._HOME_SNAPSHOT_CACHE_TTL_SECONDS - 0.1
        env2 = es.home_snapshot_envelope(report_date=None, allow_partial=False)

        assert mock_compute.call_count == 1
        assert env1 == env2
        assert env1 is not env2


def test_cached_snapshot_response_is_defensive_copy() -> None:
    with patch.object(es, "_compute_home_snapshot_envelope") as mock_compute:
        mock_compute.return_value = _fake_envelope("v1")

        env1 = es.home_snapshot_envelope(report_date=None, allow_partial=False)
        env1["result"]["tag"] = "mutated"
        env2 = es.home_snapshot_envelope(report_date=None, allow_partial=False)

        assert mock_compute.call_count == 1
        assert env2["result"]["tag"] == "v1"


def test_equivalent_report_dates_share_normalized_cache_key() -> None:
    with patch.object(es, "_compute_home_snapshot_envelope") as mock_compute:
        mock_compute.return_value = _fake_envelope("v1")

        es.home_snapshot_envelope(report_date="2026-04-08", allow_partial=False)
        es.home_snapshot_envelope(report_date=" 2026-04-08 ", allow_partial=False)

        assert mock_compute.call_count == 1


def test_concurrent_same_key_callers_share_one_producer() -> None:
    producer_entered = threading.Event()
    release_producer = threading.Event()
    results: list[dict[str, object]] = []
    results_lock = threading.Lock()

    def compute(**_kwargs) -> dict[str, object]:
        producer_entered.set()
        release_producer.wait(timeout=1)
        return _fake_envelope("shared")

    def worker() -> None:
        result = es.home_snapshot_envelope(report_date=None, allow_partial=False)
        with results_lock:
            results.append(result)

    with patch.object(es, "_compute_home_snapshot_envelope", side_effect=compute) as mock_compute:
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        assert producer_entered.wait(timeout=1)
        release_producer.set()
        for thread in threads:
            thread.join(timeout=1)

    assert all(not thread.is_alive() for thread in threads)
    assert mock_compute.call_count == 1
    assert len(results) == 4
    assert [result["result"]["tag"] for result in results] == ["shared"] * 4
    assert len({id(result) for result in results}) == 4


def test_invalidate_during_inflight_compute_prevents_stale_cache_writeback() -> None:
    producer_entered = threading.Event()
    release_producer = threading.Event()
    first_result: list[dict[str, object]] = []

    def compute(**_kwargs) -> dict[str, object]:
        producer_entered.set()
        release_producer.wait(timeout=1)
        return _fake_envelope("stale")

    with patch.object(es, "_compute_home_snapshot_envelope", side_effect=compute) as mock_compute:
        thread = threading.Thread(
            target=lambda: first_result.append(
                es.home_snapshot_envelope(report_date=None, allow_partial=False)
            )
        )
        thread.start()
        assert producer_entered.wait(timeout=1)
        es.invalidate_home_snapshot_cache()
        release_producer.set()
        thread.join(timeout=1)

        assert not thread.is_alive()
        assert first_result[0]["result"]["tag"] == "stale"

        mock_compute.side_effect = None
        mock_compute.return_value = _fake_envelope("fresh")
        fresh = es.home_snapshot_envelope(report_date=None, allow_partial=False)

    assert mock_compute.call_count == 2
    assert fresh["result"]["tag"] == "fresh"


def test_home_snapshot_prewarm_can_be_disabled() -> None:
    class Settings:
        home_snapshot_prewarm_enabled = False

    with patch.object(es, "home_snapshot_envelope") as mock_home:
        assert es.warm_home_snapshot_cache_if_configured(Settings()) is False

    mock_home.assert_not_called()


def test_home_snapshot_prewarm_starts_background_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[tuple[object, dict[str, object]]] = []

    class Settings:
        home_snapshot_prewarm_enabled = True

    class FakeThread:
        def __init__(self, *, target, kwargs=None, daemon=False, name=""):
            started.append((target, {"kwargs": kwargs or {}, "daemon": daemon, "name": name}))

        def start(self):
            started.append(("start", {}))

    monkeypatch.setattr(es.threading, "Thread", FakeThread)

    assert es.warm_home_snapshot_cache_if_configured(Settings()) is True
    assert started[0][1] == {
        "kwargs": {"report_date": None, "allow_partial": False},
        "daemon": True,
        "name": "moss-home-snapshot-warmup",
    }
    assert started[1] == ("start", {})
