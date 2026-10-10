"""Discover and parse quarterly China GDP YoY from official NBS releases."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "nbs_gdp_release_source.json"
)
_RELEASE_PATH_PATTERN = re.compile(r"t(?P<date>20\d{6})_\d+\.html(?:$|[?#])", re.IGNORECASE)
_QUARTER_PATTERN = re.compile(
    r"(?P<quarter>[一二三四])季度(?:国内生产总值)?(?:同比)?增长"
    r"(?P<value>[+-]?\d+(?:\.\d+)?)%"
)
_ANY_QUARTER_PATTERN = re.compile(r"([一二三四五六七八九十])季度")
_SENTENCE_PATTERN = re.compile(r"分季度看[^。；;]*(?:[。；;]|$)")
_QUARTER_ENDS = {
    "一": "03-31",
    "二": "06-30",
    "三": "09-30",
    "四": "12-31",
}


class NbsGdpReleaseError(RuntimeError):
    """Raised when official GDP discovery or parsing cannot be trusted."""


@dataclass(frozen=True)
class NbsGdpReleaseDocument:
    release_url: str
    fetched_at: datetime
    html_bytes: bytes
    observations: list[dict[str, object]]


class NbsGdpReleaseAdapter:
    vendor_name = "nbs"

    def __init__(
        self,
        *,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        get: Callable[..., Any] = requests.get,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self._get = get
        self._now = now or (lambda: datetime.now(UTC))
        self._allowed_hosts = frozenset(str(host) for host in self._config["allowed_hosts"])
        self._max_document_bytes = int(self._config["max_document_bytes"])

    def discover_and_fetch(
        self,
        *,
        reference_date: date,
        before_parse: Callable[[str, bytes], None] | None = None,
    ) -> NbsGdpReleaseDocument:
        listing_url = str(self._config["listing_url"])
        listing_response = self._fetch_html(listing_url)
        candidates = self._listing_candidates(
            listing_response.content,
            base_url=str(listing_response.url),
            reference_date=reference_date,
        )[:20]
        if not candidates:
            raise NbsGdpReleaseError("No NBS GDP release candidates were found")

        missing_marker_error: NbsGdpReleaseError | None = None
        for release_url in candidates:
            release_response = self._fetch_html(release_url)
            if before_parse is not None:
                before_parse(str(release_response.url), bytes(release_response.content))
            try:
                observations = self._parse_observations(
                    release_response.content,
                    release_url=str(release_response.url),
                )
            except NbsGdpReleaseError as exc:
                if "quarter-by-quarter" not in str(exc):
                    raise
                missing_marker_error = exc
                continue
            return NbsGdpReleaseDocument(
                release_url=str(release_response.url),
                fetched_at=self._now(),
                html_bytes=bytes(release_response.content),
                observations=observations,
            )

        if len(candidates) == 1 and missing_marker_error is not None:
            raise missing_marker_error
        raise NbsGdpReleaseError("No valid GDP release was found in the newest 20 candidates")

    def _fetch_html(self, url: str) -> Any:
        self._validate_url(url)
        try:
            response = self._get(
                url,
                headers={"User-Agent": "MOSS official macro ingest/1.0"},
                timeout=(5, 20),
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            raise NbsGdpReleaseError(f"NBS request failed: {exc}") from exc

        self._validate_url(str(response.url))
        if int(response.status_code) != 200:
            raise NbsGdpReleaseError(f"NBS request returned HTTP {response.status_code}")
        content_type = str(response.headers.get("Content-Type", "")).lower()
        if not (
            content_type.startswith("text/html")
            or content_type.startswith("application/xhtml+xml")
        ):
            raise NbsGdpReleaseError("NBS response must use an HTML content type")
        if len(response.content) > self._max_document_bytes:
            raise NbsGdpReleaseError("NBS response exceeds the configured maximum size")
        return response

    def _validate_url(self, value: str) -> None:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.hostname not in self._allowed_hosts:
            raise NbsGdpReleaseError(f"URL is not on a trusted NBS HTTPS host: {value}")
        if parsed.username is not None or parsed.password is not None:
            raise NbsGdpReleaseError(f"URL is not on a trusted NBS HTTPS host: {value}")

    def _listing_candidates(
        self,
        html_bytes: bytes,
        *,
        base_url: str,
        reference_date: date,
    ) -> list[str]:
        soup = BeautifulSoup(self._decode_html(html_bytes), "html.parser")
        dated_urls: list[tuple[date, str]] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            resolved = urljoin(base_url, str(anchor["href"]))
            match = _RELEASE_PATH_PATTERN.search(resolved)
            if match is None or resolved in seen:
                continue
            release_date = datetime.strptime(match.group("date"), "%Y%m%d").date()
            if release_date > reference_date:
                continue
            self._validate_url(resolved)
            seen.add(resolved)
            dated_urls.append((release_date, resolved))
        dated_urls.sort(key=lambda row: row[0], reverse=True)
        return [url for _, url in dated_urls]

    def _parse_observations(
        self,
        html_bytes: bytes,
        *,
        release_url: str,
    ) -> list[dict[str, object]]:
        html = self._decode_html(html_bytes)
        soup = BeautifulSoup(html, "html.parser")
        text = "".join(soup.get_text(" ", strip=True).split())
        sentence_match = _SENTENCE_PATTERN.search(text)
        if sentence_match is None:
            raise NbsGdpReleaseError(
                "NBS GDP quarter-by-quarter marker '分季度看' is missing"
            )
        sentence = sentence_match.group(0)
        if re.search(r"(?:nan|inf(?:inity)?|∞)", sentence, re.IGNORECASE):
            raise NbsGdpReleaseError("NBS GDP quarter value is non-finite")
        unsupported = {
            quarter for quarter in _ANY_QUARTER_PATTERN.findall(sentence) if quarter not in _QUARTER_ENDS
        }
        if unsupported:
            raise NbsGdpReleaseError("NBS GDP sentence contains an unsupported quarter")

        year = self._release_year(soup, release_url=release_url)
        values_by_quarter: dict[str, float] = {}
        for match in _QUARTER_PATTERN.finditer(sentence):
            quarter = match.group("quarter")
            value = float(match.group("value"))
            if not math.isfinite(value):
                raise NbsGdpReleaseError("NBS GDP quarter value is non-finite")
            existing = values_by_quarter.get(quarter)
            if existing is not None and existing != value:
                raise NbsGdpReleaseError("NBS GDP sentence contains conflicting quarter values")
            values_by_quarter[quarter] = value
        if not values_by_quarter:
            raise NbsGdpReleaseError("NBS GDP sentence contains no supported quarter values")

        source_version = f"nbs_gdp_release_sha256_{hashlib.sha256(html_bytes).hexdigest()}"
        return [
            {
                "trade_date": f"{year}-{_QUARTER_ENDS[quarter]}",
                "value": value,
                "source_version": source_version,
            }
            for quarter, value in sorted(
                values_by_quarter.items(),
                key=lambda item: tuple(_QUARTER_ENDS).index(item[0]),
            )
        ]

    @staticmethod
    def _decode_html(html_bytes: bytes) -> str:
        try:
            return html_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise NbsGdpReleaseError("NBS HTML is not valid UTF-8") from exc

    @staticmethod
    def _release_year(soup: BeautifulSoup, *, release_url: str) -> int:
        meta = soup.find("meta", attrs={"name": re.compile(r"^PubDate$", re.IGNORECASE)})
        if meta is not None:
            match = re.search(r"20\d{2}", str(meta.get("content", "")))
            if match is not None:
                return int(match.group(0))
        url_match = _RELEASE_PATH_PATTERN.search(release_url)
        if url_match is not None:
            return int(url_match.group("date")[:4])
        raise NbsGdpReleaseError("NBS GDP release year is missing")
