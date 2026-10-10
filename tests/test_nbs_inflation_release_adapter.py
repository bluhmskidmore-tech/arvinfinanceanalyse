from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from backend.app.repositories.nbs_inflation_catalog_seed import (
    NBS_CPI_SERIES_ID,
    NBS_PPI_SERIES_ID,
)
from backend.app.repositories.nbs_inflation_release_adapter import (
    NbsInflationReleaseAdapter,
    NbsInflationReleaseError,
    _SourceAddressHTTPAdapter,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_data,
]

LISTING_URL = "https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/"
URLS = {
    (NBS_CPI_SERIES_ID, "2026-08"): (
        "https://www.stats.gov.cn/zwfwck/sjfb/202609/t20260909_1965263.html"
    ),
    (NBS_PPI_SERIES_ID, "2026-08"): (
        "https://www.stats.gov.cn/sj/zxfbhjd/202609/t20260909_1965262.html"
    ),
    (NBS_CPI_SERIES_ID, "2026-07"): (
        "https://www.stats.gov.cn/zwfwck/sjfb/202608/t20260809_1965008.html"
    ),
    (NBS_PPI_SERIES_ID, "2026-07"): (
        "https://www.stats.gov.cn/sj/zxfbhjd/202608/t20260809_1965007.html"
    ),
}


class _Response:
    def __init__(
        self,
        content: bytes,
        url: str,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.content = content
        self.url = url
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}


def _listing_html() -> bytes:
    links = [
        (URLS[(NBS_CPI_SERIES_ID, "2026-08")], "2026年8月份居民消费价格同比上涨0.8%"),
        (URLS[(NBS_PPI_SERIES_ID, "2026-08")], "2026年8月份工业生产者出厂价格同比上涨3.8%"),
        (URLS[(NBS_CPI_SERIES_ID, "2026-07")], "2026年7月份居民消费价格同比上涨0.5%"),
        (URLS[(NBS_PPI_SERIES_ID, "2026-07")], "2026年7月份工业生产者出厂价格同比上涨3.5%"),
    ]
    return "".join(f'<a href="{url}">{title}</a>' for url, title in links).encode()


def _release_html(series_id: str, reference_month: str) -> bytes:
    year, month = reference_month.split("-")
    month_number = int(month)
    value = {
        (NBS_CPI_SERIES_ID, "2026-08"): "0.8",
        (NBS_PPI_SERIES_ID, "2026-08"): "3.8",
        (NBS_CPI_SERIES_ID, "2026-07"): "0.5",
        (NBS_PPI_SERIES_ID, "2026-07"): "3.5",
    }[(series_id, reference_month)]
    label = (
        "全国居民消费价格"
        if series_id == NBS_CPI_SERIES_ID
        else "全国工业生产者出厂价格"
    )
    return (
        f"<html><p>{year}年{month_number}月份，{label}同比上涨"
        f"<span>{value}</span>%。</p></html>"
    ).encode()


def _write_config(
    tmp_path: Path,
    *,
    listing_urls: list[str] | None = None,
) -> Path:
    config_path = tmp_path / "source.json"
    config: dict[str, object] = {
        "listing_url": LISTING_URL,
        "allowed_hosts": ["stats.gov.cn", "www.stats.gov.cn"],
        "max_document_bytes": 2_000_000,
        "series": [
            {
                "series_id": NBS_CPI_SERIES_ID,
                "title_marker": "居民消费价格同比",
            },
            {
                "series_id": NBS_PPI_SERIES_ID,
                "title_marker": "工业生产者出厂价格同比",
            },
        ],
    }
    if listing_urls is not None:
        config["listing_urls"] = listing_urls
    config_path.write_text(
        json.dumps(config, ensure_ascii=False),
        encoding="utf-8",
    )
    return config_path


def _adapter(
    tmp_path: Path,
    *,
    calls: list[tuple[str, dict[str, Any]]],
) -> NbsInflationReleaseAdapter:
    responses = {LISTING_URL: _Response(_listing_html(), LISTING_URL)}
    for key, url in URLS.items():
        responses[url] = _Response(_release_html(*key), url)

    def fake_get(url: str, **kwargs: Any) -> _Response:
        calls.append((url, kwargs))
        return responses[url]

    return NbsInflationReleaseAdapter(
        config_path=_write_config(tmp_path),
        get=fake_get,
        now=lambda: datetime(2026, 9, 16, tzinfo=UTC),
    )


def test_default_fetches_latest_two_complete_months_and_parses_split_text(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    documents = _adapter(tmp_path, calls=calls).discover_and_fetch(
        reference_date=date(2026, 9, 16)
    )

    assert [document.reference_month for document in documents] == [
        "2026-08",
        "2026-08",
        "2026-07",
        "2026-07",
    ]
    assert [document.observation["value"] for document in documents] == [0.8, 3.8, 0.5, 3.5]
    assert [document.observation["trade_date"] for document in documents] == [
        "2026-08-01",
        "2026-08-01",
        "2026-07-01",
        "2026-07-01",
    ]
    assert all(call[1]["verify"] is True for call in calls)
    assert all(call[1]["timeout"] == (5, 20) for call in calls)
    assert all(call[1]["allow_redirects"] is False for call in calls)


def test_explicit_reference_month_limits_fetch_to_one_cpi_ppi_pair(tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    documents = _adapter(tmp_path, calls=calls).discover_and_fetch(
        reference_date=date(2026, 9, 16),
        reference_month="2026-08",
    )

    assert [(document.series_id, document.reference_month) for document in documents] == [
        (NBS_CPI_SERIES_ID, "2026-08"),
        (NBS_PPI_SERIES_ID, "2026-08"),
    ]
    assert len(calls) == 3


@pytest.mark.parametrize(
    ("series_id", "sentence", "expected"),
    [
        (NBS_CPI_SERIES_ID, "2026年8月份，全国居民消费价格同比下降0.4%。", -0.4),
        (NBS_PPI_SERIES_ID, "2026年8月份，全国工业生产者出厂价格同比持平。", 0.0),
    ],
)
def test_direction_is_preserved(series_id: str, sentence: str, expected: float) -> None:
    observation = NbsInflationReleaseAdapter._parse_observation(
        series_id,
        f"<p>{sentence}</p>".encode(),
        expected_month="2026-08",
    )
    assert observation["value"] == expected


def test_redirect_is_not_followed(tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_get(url: str, **kwargs: Any) -> _Response:
        calls.append((url, kwargs))
        return _Response(
            b"",
            url,
            status_code=302,
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "Location": "https://example.com/untrusted",
            },
        )

    adapter = NbsInflationReleaseAdapter(
        config_path=_write_config(tmp_path),
        get=fake_get,
    )

    with pytest.raises(NbsInflationReleaseError, match="HTTP 302"):
        adapter.discover_and_fetch(reference_date=date(2026, 9, 16))

    assert calls[0][1]["allow_redirects"] is False


def test_external_release_url_is_rejected_before_fetch(tmp_path: Path) -> None:
    listing = (
        '<a href="https://example.com/t20260909_1.html">'
        "2026年8月份居民消费价格同比上涨0.8%</a>"
    ).encode()

    def fake_get(url: str, **_: Any) -> _Response:
        return _Response(listing, url)

    adapter = NbsInflationReleaseAdapter(
        config_path=_write_config(tmp_path),
        get=fake_get,
    )

    with pytest.raises(NbsInflationReleaseError, match="trusted NBS HTTPS host"):
        adapter.discover_and_fetch(reference_date=date(2026, 9, 16))


@pytest.mark.parametrize(
    "release_body",
    [
        "2026年7月份，全国居民消费价格同比上涨0.8%。",
        (
            "2026年8月份，全国居民消费价格同比上涨0.8%。"
            "2026年8月份，全国居民消费价格同比上涨0.9%。"
        ),
    ],
)
def test_wrong_month_or_conflicting_values_are_rejected(
    tmp_path: Path,
    release_body: str,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    adapter = _adapter(tmp_path, calls=calls)
    original_get = adapter._get

    def fake_get(url: str, **kwargs: Any) -> _Response:
        if url == URLS[(NBS_CPI_SERIES_ID, "2026-08")]:
            calls.append((url, kwargs))
            return _Response(f"<p>{release_body}</p>".encode(), url)
        return original_get(url, **kwargs)

    adapter._get = fake_get

    with pytest.raises(NbsInflationReleaseError, match="missing or conflicting"):
        adapter.discover_and_fetch(
            reference_date=date(2026, 9, 16),
            reference_month="2026-08",
        )


def test_incomplete_month_and_future_release_are_excluded(tmp_path: Path) -> None:
    listing = (
        f'<a href="{URLS[(NBS_CPI_SERIES_ID, "2026-08")]}">'
        "2026年8月份居民消费价格同比上涨0.8%</a>"
        '<a href="https://www.stats.gov.cn/sj/zxfbhjd/202610/'
        't20261009_9999999.html">'
        "2026年8月份工业生产者出厂价格同比上涨3.8%</a>"
    ).encode()

    def fake_get(url: str, **_: Any) -> _Response:
        return _Response(listing, url)

    adapter = NbsInflationReleaseAdapter(
        config_path=_write_config(tmp_path),
        get=fake_get,
    )

    with pytest.raises(NbsInflationReleaseError, match="incomplete"):
        adapter.discover_and_fetch(
            reference_date=date(2026, 9, 16),
            reference_month="2026-08",
        )


def test_newest_release_date_wins_across_listing_pages(tmp_path: Path) -> None:
    first_listing_url = LISTING_URL
    second_listing_url = f"{LISTING_URL}index_1.html"
    old_cpi_url = "https://www.stats.gov.cn/sj/zxfb/202609/t20260908_1111111.html"
    new_cpi_url = URLS[(NBS_CPI_SERIES_ID, "2026-08")]
    ppi_url = URLS[(NBS_PPI_SERIES_ID, "2026-08")]
    responses = {
        first_listing_url: _Response(
            (
                f'<a href="{new_cpi_url}">2026年8月份居民消费价格同比上涨0.8%</a>'
                f'<a href="{ppi_url}">2026年8月份工业生产者出厂价格同比上涨3.8%</a>'
            ).encode(),
            first_listing_url,
        ),
        second_listing_url: _Response(
            f'<a href="{old_cpi_url}">2026年8月份居民消费价格同比上涨0.7%</a>'.encode(),
            second_listing_url,
        ),
        new_cpi_url: _Response(_release_html(NBS_CPI_SERIES_ID, "2026-08"), new_cpi_url),
        ppi_url: _Response(_release_html(NBS_PPI_SERIES_ID, "2026-08"), ppi_url),
    }
    calls: list[str] = []

    def fake_get(url: str, **_: Any) -> _Response:
        calls.append(url)
        return responses[url]

    adapter = NbsInflationReleaseAdapter(
        config_path=_write_config(
            tmp_path,
            listing_urls=[first_listing_url, second_listing_url],
        ),
        get=fake_get,
    )

    adapter.discover_and_fetch(
        reference_date=date(2026, 9, 16),
        reference_month="2026-08",
    )

    assert new_cpi_url in calls
    assert old_cpi_url not in calls


def test_source_address_adapter_scopes_binding_to_its_pool() -> None:
    adapter = _SourceAddressHTTPAdapter("192.0.2.10")

    assert adapter.poolmanager.connection_pool_kw["source_address"] == (
        "192.0.2.10",
        0,
    )


def test_source_ip_cannot_be_silently_ignored_by_custom_get(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="custom HTTP getter"):
        NbsInflationReleaseAdapter(
            config_path=_write_config(tmp_path),
            get=lambda *_args, **_kwargs: None,
            source_ip="192.0.2.10",
        )
