from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from backend.app.repositories.nbs_gdp_release_adapter import (
    NbsGdpReleaseAdapter,
    NbsGdpReleaseError,
)


class _Response:
    def __init__(self, content: bytes, url: str) -> None:
        self.content = content
        self.url = url
        self.status_code = 200
        self.headers = {"Content-Type": "text/html; charset=utf-8"}


def test_adapter_calls_archive_hook_before_parsing_release(tmp_path: Path) -> None:
    release_url = "https://www.stats.gov.cn/sj/xwfbh/fbhwd/202607/t20260715_1964121.html"
    listing = f'<a href="{release_url}">GDP release</a>'.encode()
    invalid_release = b'<meta name="PubDate" content="2026-07-15"><p>invalid</p>'
    responses = [
        _Response(listing, "https://www.stats.gov.cn/sj/xwfbh/fbhwd/"),
        _Response(invalid_release, release_url),
    ]

    def fake_get(*_: Any, **__: Any) -> _Response:
        return responses.pop(0)

    config_path = tmp_path / "source.json"
    config_path.write_text(
        json.dumps(
            {
                "listing_url": "https://www.stats.gov.cn/sj/xwfbh/fbhwd/",
                "allowed_hosts": ["stats.gov.cn", "www.stats.gov.cn"],
                "max_document_bytes": 2_000_000,
            }
        ),
        encoding="utf-8",
    )
    archived: list[tuple[str, bytes]] = []
    adapter = NbsGdpReleaseAdapter(config_path=config_path, get=fake_get)

    with pytest.raises(NbsGdpReleaseError, match="quarter-by-quarter"):
        adapter.discover_and_fetch(
            reference_date=date(2026, 7, 17),
            before_parse=lambda url, payload: archived.append((url, payload)),
        )

    assert archived == [(release_url, invalid_release)]
