from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import requests

from backend.app.services import research_calendar_upstream_fetch_service as service


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_data,
]

FetchRows = Callable[..., list[dict[str, Any]] | dict[str, Any]]

_FETCH_CASES = (
    ("mof", service.fetch_mof_treasury_supply_auction_rows),
    ("adbc", service.fetch_adbc_policy_bank_supply_auction_rows),
    ("chinabond", service.fetch_chinabond_policy_bank_supply_auction_rows),
)


def _call_fetch(fetch: FetchRows) -> dict[str, Any]:
    if fetch is service.fetch_chinabond_policy_bank_supply_auction_rows:
        result = fetch(max_items=1, include_status=True)
    else:
        result = fetch(page_count=1, max_items=1, include_status=True)
    assert isinstance(result, dict)
    return result


def _configure_single_detail(monkeypatch: pytest.MonkeyPatch, source: str) -> None:
    monkeypatch.setattr(service, "_fetch_text", lambda _url: "<html></html>")
    if source == "mof":
        monkeypatch.setattr(service, "_iter_listing_urls", lambda _count: ["listing"])
        monkeypatch.setattr(service, "_extract_notice_links", lambda _html: [("detail", "title")])
    elif source == "adbc":
        monkeypatch.setattr(service, "_iter_adbc_listing_urls", lambda _count: ["listing"])
        monkeypatch.setattr(
            service,
            "_extract_adbc_notice_links",
            lambda _html, _url: [("detail", "title")],
        )
    else:
        monkeypatch.setattr(
            service,
            "_extract_chinabond_policy_bank_links",
            lambda _html: [("detail", "title")],
        )


def _detail_parser_name(source: str) -> str:
    return {
        "mof": "_parse_detail",
        "adbc": "_parse_adbc_detail",
        "chinabond": "_parse_chinabond_policy_bank_detail",
    }[source]


@pytest.mark.parametrize(("source", "fetch"), _FETCH_CASES)
def test_network_failure_is_disclosed_as_failed(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    fetch: FetchRows,
) -> None:
    del source

    def _network_failure(_url: str) -> str:
        raise requests.ConnectionError("upstream unavailable")

    monkeypatch.setattr(service, "_fetch_text", _network_failure)

    result = _call_fetch(fetch)
    assert result["rows"] == []
    assert result["status"] == "failed"
    assert result["warnings"]


@pytest.mark.parametrize(("source", "fetch"), _FETCH_CASES)
def test_expected_detail_parse_failure_is_disclosed_as_partial(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    fetch: FetchRows,
) -> None:
    _configure_single_detail(monkeypatch, source)

    def _invalid_payload(*_args: object) -> None:
        raise ValueError("invalid upstream number")

    monkeypatch.setattr(service, _detail_parser_name(source), _invalid_payload)

    result = _call_fetch(fetch)
    assert result["rows"] == []
    assert result["status"] == "partial"
    assert result["warnings"]


def test_mof_detail_programming_errors_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_single_detail(monkeypatch, "mof")

    def _programming_error(*_args: object) -> None:
        raise RuntimeError("unexpected implementation failure")

    monkeypatch.setattr(service, "_parse_detail", _programming_error)

    with pytest.raises(RuntimeError, match="unexpected implementation failure"):
        _call_fetch(service.fetch_mof_treasury_supply_auction_rows)
