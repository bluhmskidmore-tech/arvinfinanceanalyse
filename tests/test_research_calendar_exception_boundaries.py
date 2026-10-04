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

_HEAD_DETAIL_FETCH_CASES = (
    ("adbc", service.fetch_adbc_policy_bank_supply_auction_rows),
    ("chinabond", service.fetch_chinabond_policy_bank_supply_auction_rows),
)


def _call_fetch(fetch: FetchRows) -> list[dict[str, Any]]:
    if fetch is service.fetch_chinabond_policy_bank_supply_auction_rows:
        return fetch(max_items=1)
    return fetch(page_count=1, max_items=1)


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
def test_network_failure_preserves_rows_only_shape(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    fetch: FetchRows,
) -> None:
    del source

    def _network_failure(_url: str) -> str:
        raise requests.ConnectionError("upstream unavailable")

    monkeypatch.setattr(service, "_fetch_text", _network_failure)

    assert _call_fetch(fetch) == []


@pytest.mark.parametrize(("source", "fetch"), _HEAD_DETAIL_FETCH_CASES)
def test_expected_detail_parse_failure_preserves_rows_only_shape(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    fetch: FetchRows,
) -> None:
    _configure_single_detail(monkeypatch, source)

    def _invalid_payload(*_args: object) -> None:
        raise ValueError("invalid upstream number")

    monkeypatch.setattr(service, _detail_parser_name(source), _invalid_payload)

    assert _call_fetch(fetch) == []


@pytest.mark.parametrize("error_type", [RuntimeError, TypeError, AttributeError])
@pytest.mark.parametrize(("source", "fetch"), _FETCH_CASES)
def test_listing_programming_errors_propagate(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    fetch: FetchRows,
    error_type: type[Exception],
) -> None:
    del source

    def _programming_error(_url: str) -> str:
        raise error_type("unexpected implementation failure")

    monkeypatch.setattr(service, "_fetch_text", _programming_error)

    with pytest.raises(error_type, match="unexpected implementation failure"):
        _call_fetch(fetch)


@pytest.mark.parametrize("error_type", [RuntimeError, TypeError, AttributeError])
@pytest.mark.parametrize(("source", "fetch"), _HEAD_DETAIL_FETCH_CASES)
def test_detail_programming_errors_propagate(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    fetch: FetchRows,
    error_type: type[Exception],
) -> None:
    _configure_single_detail(monkeypatch, source)

    def _programming_error(*_args: object) -> None:
        raise error_type("unexpected implementation failure")

    monkeypatch.setattr(service, _detail_parser_name(source), _programming_error)

    with pytest.raises(error_type, match="unexpected implementation failure"):
        _call_fetch(fetch)
