from __future__ import annotations

import logging
import threading
import time
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


def test_home_snapshot_prewarm_populates_cache(caplog: pytest.LogCaptureFixture) -> None:
    with patch.object(es, "_compute_home_snapshot_envelope") as mock_compute:
        mock_compute.return_value = _fake_envelope("warm")

        with caplog.at_level(logging.INFO, logger=es.__name__):
            es._warm_home_snapshot_cache_quietly(report_date=None, allow_partial=False)
        warmed = es.home_snapshot_envelope(report_date=None, allow_partial=False)

    assert mock_compute.call_count == 1
    assert warmed["result"]["tag"] == "warm"
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "home_snapshot_prewarm_start" in messages
    assert "home_snapshot_prewarm_done" in messages


def test_home_snapshot_prewarm_can_be_disabled() -> None:
    class Settings:
        home_snapshot_prewarm_enabled = False

    with patch.object(es, "home_snapshot_envelope") as mock_home:
        assert es.warm_home_snapshot_cache_if_configured(Settings()) is False

    mock_home.assert_not_called()
    status = es.home_snapshot_prewarm_status()
    assert status["status"] == "disabled"
    assert status["ok"] is False
    assert status["error"] is None


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
    status = es.home_snapshot_prewarm_status()
    assert status["status"] == "warming"
    assert status["ok"] is False
    assert status["report_date"] is None
    assert status["allow_partial"] is False


def test_home_snapshot_prewarm_status_tracks_ready_and_failure() -> None:
    with patch.object(es, "_compute_home_snapshot_envelope") as mock_compute:
        mock_compute.return_value = _fake_envelope("warm")
        es._warm_home_snapshot_cache_quietly(report_date="2026-04-08", allow_partial=False)

    ready_status = es.home_snapshot_prewarm_status()
    assert ready_status["status"] == "ready"
    assert ready_status["ok"] is True
    assert ready_status["report_date"] == "2026-04-08"
    assert ready_status["allow_partial"] is False
    assert isinstance(ready_status["last_duration_ms"], int)
    assert ready_status["last_duration_ms"] >= 0
    step_durations = ready_status["last_step_durations_ms"]
    assert set(step_durations) == {"cache_lookup", "total"}
    assert all(isinstance(duration_ms, int) for duration_ms in step_durations.values())
    assert all(duration_ms >= 0 for duration_ms in step_durations.values())
    assert ready_status["error"] is None

    with patch.object(es, "home_snapshot_envelope", side_effect=RuntimeError("boom")):
        es._warm_home_snapshot_cache_quietly(report_date=None, allow_partial=True)

    failed_status = es.home_snapshot_prewarm_status()
    assert failed_status["status"] == "failed"
    assert failed_status["ok"] is False
    assert failed_status["report_date"] is None
    assert failed_status["allow_partial"] is True
    assert failed_status["last_step_durations_ms"] == {}
    assert failed_status["error"] == "boom"


def test_home_snapshot_cold_compute_logs_step_timings(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        es,
        "_list_domain_date_context",
        lambda: {
            "balance": ["2026-04-08"],
            "pnl": ["2026-04-08"],
            "liability": ["2026-04-08"],
            "bond": ["2026-04-08"],
        },
    )
    monkeypatch.setattr(
        es,
        "executive_overview",
        lambda **_kwargs: {"result_meta": {}, "result": {"title": "overview", "metrics": []}},
    )
    monkeypatch.setattr(
        es,
        "executive_pnl_attribution",
        lambda **_kwargs: {
            "result_meta": {},
            "result": es._pnl_attribution_unavailable_payload().model_dump(mode="json"),
        },
    )
    monkeypatch.setattr(es, "_build_product_category_ytd_headline", lambda _rd: None)
    monkeypatch.setattr(es, "_build_product_category_monthly_headline", lambda _rd: None)

    with caplog.at_level(logging.INFO, logger=es.__name__):
        env = es.home_snapshot_envelope(report_date="2026-04-08", allow_partial=False)

    assert env["result"]["report_date"] == "2026-04-08"
    messages = "\n".join(
        record.getMessage() for record in caplog.records if "home_snapshot perf" in record.getMessage()
    )
    expected_steps = [
        "cache_lookup",
        "date_context",
        "resolve_report_date",
        "executive_overview",
        "executive_pnl_attribution",
        "payload_validation",
        "product_category_ytd",
        "product_category_monthly",
        "envelope_build",
        "compute_total",
        "total",
    ]
    for step in expected_steps:
        assert f"step={step} " in messages


def test_home_snapshot_prewarm_status_exposes_cold_compute_step_timings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        es,
        "_list_domain_date_context",
        lambda: {
            "balance": ["2026-04-08"],
            "pnl": ["2026-04-08"],
            "liability": ["2026-04-08"],
            "bond": ["2026-04-08"],
        },
    )
    monkeypatch.setattr(
        es,
        "executive_overview",
        lambda **_kwargs: {"result_meta": {}, "result": {"title": "overview", "metrics": []}},
    )
    monkeypatch.setattr(
        es,
        "executive_pnl_attribution",
        lambda **_kwargs: {
            "result_meta": {},
            "result": es._pnl_attribution_unavailable_payload().model_dump(mode="json"),
        },
    )
    monkeypatch.setattr(es, "_build_product_category_ytd_headline", lambda _rd: None)
    monkeypatch.setattr(es, "_build_product_category_monthly_headline", lambda _rd: None)

    es._warm_home_snapshot_cache_quietly(report_date="2026-04-08", allow_partial=False)

    status = es.home_snapshot_prewarm_status()
    step_durations = status["last_step_durations_ms"]
    assert isinstance(step_durations, dict)
    for step in [
        "cache_lookup",
        "date_context",
        "resolve_report_date",
        "executive_overview",
        "executive_pnl_attribution",
        "payload_validation",
        "product_category_ytd",
        "product_category_monthly",
        "envelope_build",
        "compute_total",
        "total",
    ]:
        assert isinstance(step_durations.get(step), int)
        assert step_durations[step] >= 0


def test_home_snapshot_builds_product_category_headlines_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        es,
        "_list_domain_date_context",
        lambda: {
            "balance": ["2026-04-08"],
            "pnl": ["2026-04-08"],
            "liability": ["2026-04-08"],
            "bond": ["2026-04-08"],
        },
    )
    monkeypatch.setattr(
        es,
        "executive_overview",
        lambda **_kwargs: {"result_meta": {}, "result": {"title": "overview", "metrics": []}},
    )
    monkeypatch.setattr(
        es,
        "executive_pnl_attribution",
        lambda **_kwargs: {
            "result_meta": {},
            "result": es._pnl_attribution_unavailable_payload().model_dump(mode="json"),
        },
    )

    ytd_started = threading.Event()
    monthly_started = threading.Event()
    overlap = {"ytd_saw_monthly": False, "monthly_saw_ytd": False}

    def ytd_headline(_report_date: str):
        ytd_started.set()
        overlap["ytd_saw_monthly"] = monthly_started.wait(timeout=0.5)
        return None

    def monthly_headline(_report_date: str):
        monthly_started.set()
        overlap["monthly_saw_ytd"] = ytd_started.wait(timeout=0.5)
        return None

    monkeypatch.setattr(es, "_build_product_category_ytd_headline", ytd_headline)
    monkeypatch.setattr(es, "_build_product_category_monthly_headline", monthly_headline)

    env = es.home_snapshot_envelope(report_date="2026-04-08", allow_partial=False)

    assert env["result"]["report_date"] == "2026-04-08"
    assert overlap["ytd_saw_monthly"]
    assert overlap["monthly_saw_ytd"]


def test_home_snapshot_builds_overview_and_attribution_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        es,
        "_list_domain_date_context",
        lambda: {
            "balance": ["2026-04-08"],
            "pnl": ["2026-04-08"],
            "liability": ["2026-04-08"],
            "bond": ["2026-04-08"],
        },
    )
    monkeypatch.setattr(es, "_build_product_category_ytd_headline", lambda _rd: None)
    monkeypatch.setattr(es, "_build_product_category_monthly_headline", lambda _rd: None)

    overview_started = threading.Event()
    attribution_started = threading.Event()
    overlap = {"overview_saw_attribution": False, "attribution_saw_overview": False}

    def overview(**_kwargs):
        overview_started.set()
        overlap["overview_saw_attribution"] = attribution_started.wait(timeout=0.5)
        return {"result_meta": {}, "result": {"title": "overview", "metrics": []}}

    def attribution(**_kwargs):
        attribution_started.set()
        overlap["attribution_saw_overview"] = overview_started.wait(timeout=0.5)
        return {
            "result_meta": {},
            "result": es._pnl_attribution_unavailable_payload().model_dump(mode="json"),
        }

    monkeypatch.setattr(es, "executive_overview", overview)
    monkeypatch.setattr(es, "executive_pnl_attribution", attribution)

    env = es.home_snapshot_envelope(report_date="2026-04-08", allow_partial=False)

    assert env["result"]["report_date"] == "2026-04-08"
    assert overlap["overview_saw_attribution"]
    assert overlap["attribution_saw_overview"]


def test_home_snapshot_logs_concurrent_step_durations(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        es,
        "_list_domain_date_context",
        lambda: {
            "balance": ["2026-04-08"],
            "pnl": ["2026-04-08"],
            "liability": ["2026-04-08"],
            "bond": ["2026-04-08"],
        },
    )

    def overview(**_kwargs):
        time.sleep(0.05)
        return {"result_meta": {}, "result": {"title": "overview", "metrics": []}}

    def attribution(**_kwargs):
        time.sleep(0.05)
        return {
            "result_meta": {},
            "result": es._pnl_attribution_unavailable_payload().model_dump(mode="json"),
        }

    def ytd_headline(_report_date: str):
        time.sleep(0.05)
        return None

    def monthly_headline(_report_date: str):
        time.sleep(0.05)
        return None

    monkeypatch.setattr(es, "executive_overview", overview)
    monkeypatch.setattr(es, "executive_pnl_attribution", attribution)
    monkeypatch.setattr(es, "_build_product_category_ytd_headline", ytd_headline)
    monkeypatch.setattr(es, "_build_product_category_monthly_headline", monthly_headline)

    with caplog.at_level(logging.INFO, logger=es.__name__):
        env = es.home_snapshot_envelope(report_date="2026-04-08", allow_partial=False)

    assert env["result"]["report_date"] == "2026-04-08"
    step_ms: dict[str, int] = {}
    for record in caplog.records:
        message = record.getMessage()
        if "home_snapshot perf" not in message:
            continue
        parts = dict(
            item.split("=", 1)
            for item in message.split()
            if "=" in item
        )
        step = parts.get("step")
        if step:
            step_ms[step] = int(parts["ms"])

    assert step_ms["executive_overview"] >= 40
    assert step_ms["executive_pnl_attribution"] >= 40
    assert step_ms["product_category_ytd"] >= 40
    assert step_ms["product_category_monthly"] >= 40


def test_home_snapshot_nim_context_cache_reuses_batch_payload_until_invalidated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []
    dates = ["2026-04-08", "2026-03-31", "2026-02-28"]
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_text("stub", encoding="utf-8")

    class Repo(es.LiabilityAnalyticsRepository):
        def __init__(self) -> None:
            super().__init__(str(duckdb_path))

        def fetch_yield_rows_for_dates(self, requested_dates):
            calls.append(("yield-batch", tuple(requested_dates)))
            return (
                {
                    d: [{"source_version": f"sv-z-{d}", "rule_version": "rv-z"}]
                    for d in requested_dates
                },
                {
                    d: [{"source_version": f"sv-t-{d}", "rule_version": "rv-t"}]
                    for d in requested_dates
                },
            )

    monkeypatch.setattr(
        es,
        "compute_liability_yield_metrics",
        lambda report_date, _zqtz_rows, _tyw_rows: {
            "report_date": report_date,
            "kpi": {"nim": {"2026-04-08": 0.003, "2026-03-31": 0.0025, "2026-02-28": 0.002}[report_date]},
        },
    )

    first = es._fetch_nim_context(Repo(), report_dates=dates, current_report_date="2026-04-08", n=3)
    second = es._fetch_nim_context(Repo(), report_dates=dates, current_report_date="2026-04-08", n=3)

    assert calls == [("yield-batch", tuple(dates))]
    assert first == second

    es.invalidate_home_snapshot_cache()
    third = es._fetch_nim_context(Repo(), report_dates=dates, current_report_date="2026-04-08", n=3)

    assert calls == [("yield-batch", tuple(dates)), ("yield-batch", tuple(dates))]
    assert third == first


def test_home_snapshot_nim_context_cache_coalesces_concurrent_cold_requests(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []
    dates = ["2026-04-08", "2026-03-31", "2026-02-28"]
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_text("stub", encoding="utf-8")
    first_fetch_started = threading.Event()
    release_fetch = threading.Event()

    class Repo(es.LiabilityAnalyticsRepository):
        def __init__(self) -> None:
            super().__init__(str(duckdb_path))

        def fetch_yield_rows_for_dates(self, requested_dates):
            calls.append(("yield-batch", tuple(requested_dates)))
            first_fetch_started.set()
            assert release_fetch.wait(timeout=1)
            return (
                {
                    d: [{"source_version": f"sv-z-{d}", "rule_version": "rv-z"}]
                    for d in requested_dates
                },
                {
                    d: [{"source_version": f"sv-t-{d}", "rule_version": "rv-t"}]
                    for d in requested_dates
                },
            )

    monkeypatch.setattr(
        es,
        "compute_liability_yield_metrics",
        lambda report_date, _zqtz_rows, _tyw_rows: {
            "report_date": report_date,
            "kpi": {"nim": {"2026-04-08": 0.003, "2026-03-31": 0.0025, "2026-02-28": 0.002}[report_date]},
        },
    )

    results: list[es._HomeNimContextValue] = []
    errors: list[BaseException] = []

    def load() -> None:
        try:
            results.append(
                es._fetch_nim_context(
                    Repo(),
                    report_dates=dates,
                    current_report_date="2026-04-08",
                    n=3,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    first = threading.Thread(target=load)
    second = threading.Thread(target=load)
    first.start()
    assert first_fetch_started.wait(timeout=1)
    second.start()
    time.sleep(0.05)
    release_fetch.set()
    first.join(timeout=1)
    second.join(timeout=1)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert len(results) == 2
    assert results[0] == results[1]
    assert calls == [("yield-batch", tuple(dates))]
