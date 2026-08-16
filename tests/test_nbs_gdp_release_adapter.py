from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
import requests

from backend.app.repositories.nbs_gdp_release_adapter import (
    NbsGdpReleaseAdapter,
    NbsGdpReleaseError,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "nbs_gdp_release"
LISTING_HTML = (FIXTURE_ROOT / "listing.html").read_bytes()
RELEASE_HTML = (FIXTURE_ROOT / "2026_h1_release.html").read_bytes()


class FakeResponse:
    def __init__(
        self,
        content: bytes,
        *,
        url: str,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.content = content
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.encoding = "utf-8"


def _write_config(
    tmp_path: Path,
    *,
    listing_url: str = "https://www.stats.gov.cn/sj/xwfbh/fbhwd/",
    max_document_bytes: int = 2_000_000,
) -> Path:
    path = tmp_path / "source.json"
    path.write_text(
        json.dumps(
            {
                "series_id": "nbs.macro.cn_gdp.quarterly",
                "series_name": "China GDP YoY (NBS official release)",
                "listing_url": listing_url,
                "allowed_hosts": ["stats.gov.cn", "www.stats.gov.cn"],
                "frequency": "quarterly",
                "unit": "pct",
                "rule_version": "rv_nbs_gdp_release_v1",
                "catalog_version": "m2b.nbs_gdp_release.v1",
                "max_document_bytes": max_document_bytes,
            }
        ),
        encoding="utf-8",
    )
    return path


def _sequence_get(responses: list[FakeResponse]):
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append((url, kwargs))
        return responses[len(calls) - 1]

    return fake_get, calls


def test_discovers_relative_release_and_parses_quarter_end_observations(tmp_path: Path) -> None:
    release_url = "https://www.stats.gov.cn/sj/xwfbh/fbhwd/202607/t20260715_1964121.html"
    fake_get, calls = _sequence_get(
        [
            FakeResponse(LISTING_HTML, url="https://www.stats.gov.cn/sj/xwfbh/fbhwd/"),
            FakeResponse(RELEASE_HTML, url=release_url),
        ]
    )
    adapter = NbsGdpReleaseAdapter(config_path=_write_config(tmp_path), get=fake_get)

    document = adapter.discover_and_fetch(reference_date=date(2026, 7, 17))

    assert document.release_url == release_url
    assert document.fetched_at.tzinfo is UTC
    assert document.html_bytes == RELEASE_HTML
    assert document.observations == [
        {
            "trade_date": "2026-03-31",
            "value": 5.0,
            "source_version": document.observations[0]["source_version"],
        },
        {
            "trade_date": "2026-06-30",
            "value": 4.3,
            "source_version": document.observations[0]["source_version"],
        },
    ]
    assert str(document.observations[0]["source_version"]).startswith(
        "nbs_gdp_release_sha256_"
    )
    assert [call[0] for call in calls] == [
        "https://www.stats.gov.cn/sj/xwfbh/fbhwd/",
        release_url,
    ]
    assert all(call[1]["timeout"] == (5, 20) for call in calls)
    assert all(call[1]["allow_redirects"] is True for call in calls)


def test_rejects_untrusted_initial_or_redirected_host(tmp_path: Path) -> None:
    called = False

    def should_not_fetch(url: str, **_: Any) -> FakeResponse:
        nonlocal called
        called = True
        return FakeResponse(b"", url=url)

    adapter = NbsGdpReleaseAdapter(
        config_path=_write_config(
            tmp_path,
            listing_url="https://stats.gov.cn.evil.example/sj/xwfbh/fbhwd/",
        ),
        get=should_not_fetch,
    )
    with pytest.raises(NbsGdpReleaseError, match="trusted NBS HTTPS host"):
        adapter.discover_and_fetch(reference_date=date(2026, 7, 17))
    assert called is False

    redirect_get, _ = _sequence_get(
        [FakeResponse(LISTING_HTML, url="https://stats.gov.cn.evil.example/listing.html")]
    )
    adapter = NbsGdpReleaseAdapter(config_path=_write_config(tmp_path), get=redirect_get)
    with pytest.raises(NbsGdpReleaseError, match="trusted NBS HTTPS host"):
        adapter.discover_and_fetch(reference_date=date(2026, 7, 17))


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeResponse(b"error", url="https://www.stats.gov.cn/list", status_code=503), "HTTP 503"),
        (
            FakeResponse(
                b"not html",
                url="https://www.stats.gov.cn/list",
                content_type="application/octet-stream",
            ),
            "HTML content type",
        ),
        (FakeResponse(b"x" * 11, url="https://www.stats.gov.cn/list"), "maximum size"),
    ],
)
def test_http_status_content_type_and_size_fail_closed(
    tmp_path: Path,
    response: FakeResponse,
    message: str,
) -> None:
    fake_get, _ = _sequence_get([response])
    adapter = NbsGdpReleaseAdapter(
        config_path=_write_config(tmp_path, max_document_bytes=10),
        get=fake_get,
    )

    with pytest.raises(NbsGdpReleaseError, match=message):
        adapter.discover_and_fetch(reference_date=date(2026, 7, 17))


def test_timeout_fails_closed_as_typed_error(tmp_path: Path) -> None:
    def timeout_get(*_: Any, **__: Any) -> FakeResponse:
        raise requests.Timeout("slow")

    adapter = NbsGdpReleaseAdapter(config_path=_write_config(tmp_path), get=timeout_get)
    with pytest.raises(NbsGdpReleaseError, match="request failed"):
        adapter.discover_and_fetch(reference_date=date(2026, 7, 17))


@pytest.mark.parametrize(
    ("sentence", "message"),
    [
        ("一季度增长5.0%，二季度增长4.3%。", "quarter-by-quarter"),
        ("分季度看，一季度增长5.0%，一季度增长4.9%。", "conflicting"),
        ("分季度看，一季度增长NaN%。", "non-finite"),
        ("分季度看，五季度增长4.3%。", "unsupported quarter"),
    ],
)
def test_invalid_or_ambiguous_quarter_text_fails_closed(
    tmp_path: Path,
    sentence: str,
    message: str,
) -> None:
    listing = b'<a href="202607/t20260715_1964121.html">2026 GDP release</a>'
    release = (
        '<meta name="PubDate" content="2026-07-15">'
        f"<p>{sentence}</p>"
    ).encode()
    release_url = "https://www.stats.gov.cn/sj/xwfbh/fbhwd/202607/t20260715_1964121.html"
    fake_get, _ = _sequence_get(
        [
            FakeResponse(listing, url="https://www.stats.gov.cn/sj/xwfbh/fbhwd/"),
            FakeResponse(release, url=release_url),
        ]
    )
    adapter = NbsGdpReleaseAdapter(config_path=_write_config(tmp_path), get=fake_get)

    with pytest.raises(NbsGdpReleaseError, match=message):
        adapter.discover_and_fetch(reference_date=date(2026, 7, 17))


def test_preserves_zero_and_never_infers_value_from_cumulative_growth(tmp_path: Path) -> None:
    listing = b'<a href="202607/t20260715_1964121.html">2026 GDP release</a>'
    release = (
        '<meta name="PubDate" content="2026-07-15">'
        "<p>上半年国内生产总值同比增长9.9%。</p>"
        "<p>分季度看，一季度增长5.0%，二季度增长0.0%。</p>"
    ).encode()
    release_url = "https://www.stats.gov.cn/sj/xwfbh/fbhwd/202607/t20260715_1964121.html"
    fake_get, _ = _sequence_get(
        [
            FakeResponse(listing, url="https://www.stats.gov.cn/sj/xwfbh/fbhwd/"),
            FakeResponse(release, url=release_url),
        ]
    )
    adapter = NbsGdpReleaseAdapter(config_path=_write_config(tmp_path), get=fake_get)

    document = adapter.discover_and_fetch(reference_date=date(2026, 7, 17))

    assert [row["value"] for row in document.observations] == [5.0, 0.0]
    assert 9.9 not in [row["value"] for row in document.observations]


def test_discovery_is_bounded_to_twenty_newest_candidates(tmp_path: Path) -> None:
    links = "".join(
        f'<a href="202607/t202607{day:02d}_1964{day:03d}.html">GDP release {day}</a>'
        for day in range(31, 6, -1)
    ).encode()
    invalid_release = b'<meta name="PubDate" content="2026-07-15"><p>no GDP detail</p>'
    listing_response = FakeResponse(links, url="https://www.stats.gov.cn/sj/xwfbh/fbhwd/")
    release_responses = [
        FakeResponse(invalid_release, url=f"https://www.stats.gov.cn/release-{index}.html")
        for index in range(20)
    ]
    fake_get, calls = _sequence_get([listing_response, *release_responses])
    adapter = NbsGdpReleaseAdapter(config_path=_write_config(tmp_path), get=fake_get)

    with pytest.raises(NbsGdpReleaseError, match="No valid GDP release"):
        adapter.discover_and_fetch(reference_date=date(2026, 7, 31))
    assert len(calls) == 21


def test_document_fetch_time_is_timezone_aware(tmp_path: Path) -> None:
    release_url = "https://www.stats.gov.cn/sj/xwfbh/fbhwd/202607/t20260715_1964121.html"
    fake_get, _ = _sequence_get(
        [
            FakeResponse(LISTING_HTML, url="https://www.stats.gov.cn/sj/xwfbh/fbhwd/"),
            FakeResponse(RELEASE_HTML, url=release_url),
        ]
    )
    now = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    adapter = NbsGdpReleaseAdapter(
        config_path=_write_config(tmp_path),
        get=fake_get,
        now=lambda: now,
    )

    assert adapter.discover_and_fetch(reference_date=date(2026, 7, 17)).fetched_at == now
