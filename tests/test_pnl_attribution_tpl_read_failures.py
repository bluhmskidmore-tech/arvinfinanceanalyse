"""Synthetic TPL read failures must not become successful zero observations."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pytest
from fastapi import HTTPException

from backend.app.repositories import pnl_repo

REPORT_DATE = "2026-04-30"
PRIOR_DATE = "2026-03-31"
UNAVAILABLE = "Formal pnl storage is unavailable."


@pytest.fixture
def repository():
    return pnl_repo.PnlRepository("synthetic-tpl-read.duckdb")


def _read(repository, batch):
    if batch:
        return repository.fetch_tpl_pnl_summary_by_report_date([REPORT_DATE, PRIOR_DATE])
    return repository.fetch_tpl_pnl_summary(REPORT_DATE)


@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
@pytest.mark.parametrize("phase", ["connect", "execute"])
@pytest.mark.parametrize("message", ["Cannot open database: synthetic failure", "synthetic query failure"])
def test_tpl_read_failure_is_unavailable(repository, monkeypatch, batch, phase, message):
    error = duckdb.Error(message)
    connection = Mock()
    connection.execute.side_effect = error
    connect = Mock(side_effect=error) if phase == "connect" else Mock(return_value=connection)
    monkeypatch.setattr(pnl_repo.duckdb, "connect", connect)

    with pytest.raises(RuntimeError, match=UNAVAILABLE) as raised:
        _read(repository, batch)

    assert raised.value.__cause__ is error
    connect.assert_called_once_with(repository.path, read_only=True)
    if phase == "execute":
        connection.close.assert_called_once_with()


@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
@pytest.mark.parametrize("row_count", [0, 2], ids=["no-rows", "observed-zero"])
def test_successful_tpl_zero_keeps_row_count(repository, monkeypatch, batch, row_count):
    connection = Mock()
    connection.execute.return_value = connection
    connection.fetchone.return_value = (Decimal("0"), Decimal("0"), row_count)
    connection.fetchall.return_value = (
        [(REPORT_DATE, Decimal("0"), Decimal("0"), row_count)] if row_count else []
    )
    monkeypatch.setattr(pnl_repo.duckdb, "connect", Mock(return_value=connection))

    result = _read(repository, batch)
    summary = result[REPORT_DATE] if batch else result

    assert summary == {"tpl_fair_value_change": 0, "tpl_total_pnl": 0, "row_count": row_count}
    if batch:
        assert result[PRIOR_DATE] == {"tpl_fair_value_change": 0, "tpl_total_pnl": 0, "row_count": 0}
    connection.close.assert_called_once_with()


@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
def test_successful_tpl_nonzero_keeps_amounts_and_row_count(repository, monkeypatch, batch):
    connection = Mock()
    connection.execute.return_value = connection
    connection.fetchone.return_value = (Decimal("12.34"), Decimal("-5.67"), 2)
    connection.fetchall.return_value = [
        (REPORT_DATE, Decimal("12.34"), Decimal("-5.67"), 2),
        (PRIOR_DATE, Decimal("-1.25"), Decimal("8.75"), 1),
    ]
    monkeypatch.setattr(pnl_repo.duckdb, "connect", Mock(return_value=connection))

    result = _read(repository, batch)
    summary = result[REPORT_DATE] if batch else result

    assert summary == {
        "tpl_fair_value_change": Decimal("12.34"),
        "tpl_total_pnl": Decimal("-5.67"),
        "row_count": 2,
    }
    if batch:
        assert result[PRIOR_DATE] == {
            "tpl_fair_value_change": Decimal("-1.25"),
            "tpl_total_pnl": Decimal("8.75"),
            "row_count": 1,
        }
    connection.close.assert_called_once_with()


def test_empty_tpl_batch_does_not_open_storage(repository, monkeypatch):
    connect = Mock(side_effect=AssertionError("empty request must not read storage"))
    monkeypatch.setattr(pnl_repo.duckdb, "connect", connect)

    assert repository.fetch_tpl_pnl_summary_by_report_date([]) == {}
    connect.assert_not_called()


@pytest.mark.parametrize("batch", [False, True], ids=["single-compat", "batch"])
def test_summary_rejects_failed_tpl_read_after_dates_succeed(repository, monkeypatch, batch):
    from backend.app.services import pnl_attribution_service as service
    from backend.app.services.runtime_cache import InMemoryTTLCache

    dates = Mock(return_value=[REPORT_DATE, PRIOR_DATE])
    monkeypatch.setattr(repository, "list_formal_fi_report_dates", dates)
    selected_repo = repository if batch else SimpleNamespace(
        list_formal_fi_report_dates=dates,
        fetch_tpl_pnl_summary=repository.fetch_tpl_pnl_summary,
    )
    monkeypatch.setattr(service, "_pnl_repo", lambda: selected_repo)
    monkeypatch.setattr(service, "_curve_repo", lambda: SimpleNamespace(path=""))
    monkeypatch.setattr(service, "_treasury_10y_on_or_before_many", lambda *_args: {})
    volume = Mock(return_value=({}, {"warning": False}, REPORT_DATE, PRIOR_DATE))
    monkeypatch.setattr(service, "_volume_rate_summary_components", volume)
    connect = Mock(side_effect=duckdb.Error("Cannot open database: synthetic failure"))
    monkeypatch.setattr(pnl_repo.duckdb, "connect", connect)
    build = Mock(side_effect=AssertionError("failed storage must not reach the financial builder"))
    monkeypatch.setattr(service.pa_wb, "build_tpl_market_correlation", build)
    # Use a fresh real in-memory cache with a synthetic identity, never settings or disk identity.
    key = ("synthetic-summary-read-failure", batch)
    cache = InMemoryTTLCache(ttl_seconds=300)
    monkeypatch.setattr(service, "_PNL_ATTRIBUTION_CACHE", cache)
    monkeypatch.setattr(service, "_pnl_attribution_cache_key", lambda *_args: key)

    for _attempt in range(2):
        with pytest.raises(RuntimeError, match=UNAVAILABLE):
            service.attribution_analysis_summary_envelope(report_date=REPORT_DATE)

    assert dates.call_count == volume.call_count == connect.call_count == 2
    assert cache.get(key) == (False, None)
    build.assert_not_called()


def test_summary_route_reports_storage_unavailable(monkeypatch):
    from backend.app.api.routes import pnl_attribution as route

    auth = object()
    allowed = Mock()
    monkeypatch.setattr(route, "_ensure_pnl_attribution_read_allowed", allowed)
    failure = RuntimeError(UNAVAILABLE)
    reader = Mock(side_effect=failure)
    monkeypatch.setattr(route, "attribution_analysis_summary_envelope", reader)

    with pytest.raises(HTTPException) as raised:
        route.summary(auth=auth, report_date=REPORT_DATE)

    assert raised.value.status_code == 503
    assert raised.value.detail == UNAVAILABLE
    assert raised.value.__cause__ is failure
    allowed.assert_called_once_with(auth)
    reader.assert_called_once_with(report_date=REPORT_DATE)


def test_summary_route_does_not_misclassify_other_runtime_errors(monkeypatch):
    from backend.app.api.routes import pnl_attribution as route

    monkeypatch.setattr(route, "_ensure_pnl_attribution_read_allowed", Mock())
    failure = RuntimeError("synthetic unrelated programming error")
    monkeypatch.setattr(route, "attribution_analysis_summary_envelope", Mock(side_effect=failure))

    with pytest.raises(RuntimeError) as raised:
        route.summary(auth=object(), report_date=REPORT_DATE)
    assert raised.value is failure


def test_summary_route_preserves_success_and_checks_access_first(monkeypatch):
    from backend.app.api.routes import pnl_attribution as route

    auth = object()
    events = []
    result = {"result": {"synthetic": True}}
    monkeypatch.setattr(route, "_ensure_pnl_attribution_read_allowed", lambda _auth: events.append("auth"))

    def read(*, report_date):
        events.append("read")
        assert report_date == REPORT_DATE
        return result

    monkeypatch.setattr(route, "attribution_analysis_summary_envelope", read)
    assert route.summary(auth=auth, report_date=REPORT_DATE) is result
    assert events == ["auth", "read"]

    denied = HTTPException(status_code=403, detail="synthetic denial")
    monkeypatch.setattr(route, "_ensure_pnl_attribution_read_allowed", Mock(side_effect=denied))
    reader = Mock()
    monkeypatch.setattr(route, "attribution_analysis_summary_envelope", reader)
    with pytest.raises(HTTPException) as raised:
        route.summary(auth=auth, report_date=REPORT_DATE)
    assert raised.value is denied
    reader.assert_not_called()
