"""Discover and parse official NBS monthly CPI and PPI release pages."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from backend.app.repositories.nbs_inflation_catalog_seed import (
    NBS_CPI_SERIES_ID,
    NBS_INFLATION_SERIES_IDS,
    NBS_PPI_SERIES_ID,
)
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "nbs_inflation_release_source.json"
)
_RELEASE_PATH_PATTERN = re.compile(r"t(?P<date>20\d{6})_\d+\.html(?:$|[?#])", re.IGNORECASE)
_PERIOD_PATTERN = re.compile(r"(?P<year>20\d{2})年(?P<month>1[0-2]|[1-9])月份")
_VALUE_PATTERN = r"(?:(?P<direction>上涨|下降)(?P<value>\d+(?:\.\d+)?)%|(?P<flat>持平))"
_OBSERVATION_PATTERNS = {
    NBS_CPI_SERIES_ID: re.compile(
        rf"(?P<year>20\d{{2}})年(?P<month>1[0-2]|[1-9])月份，?"
        rf"全国居民消费价格(?:（CPI）)?同比{_VALUE_PATTERN}"
    ),
    NBS_PPI_SERIES_ID: re.compile(
        rf"(?P<year>20\d{{2}})年(?P<month>1[0-2]|[1-9])月份，?"
        rf"全国工业生产者出厂价格同比{_VALUE_PATTERN}"
    ),
}


class NbsInflationReleaseError(RuntimeError):
    """Raised when official inflation release discovery or parsing is not trustworthy."""


@dataclass(frozen=True)
class NbsInflationReleaseDocument:
    series_id: str
    reference_month: str
    release_url: str
    fetched_at: datetime
    html_bytes: bytes
    observation: dict[str, object]


@dataclass(frozen=True)
class _ReleaseCandidate:
    series_id: str
    reference_month: str
    release_date: date
    release_url: str


class _SourceAddressHTTPAdapter(HTTPAdapter):
    """Bind one requests session to an explicitly selected local IPv4 address."""

    def __init__(self, source_ip: str) -> None:
        self._source_address = (source_ip, 0)
        super().__init__()

    def init_poolmanager(
        self,
        connections: int,
        maxsize: int,
        block: bool = False,
        **pool_kwargs: Any,
    ) -> None:
        pool_kwargs["source_address"] = self._source_address
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


def _session_get(
    url: str,
    *,
    source_ip: str | None = None,
    **kwargs: Any,
) -> requests.Response:
    session = requests.Session()
    session.trust_env = False
    if source_ip is not None:
        session.mount("https://", _SourceAddressHTTPAdapter(source_ip))
    try:
        return session.get(url, **kwargs)
    finally:
        session.close()


class NbsInflationReleaseAdapter:
    vendor_name = "nbs"

    def __init__(
        self,
        *,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        get: Callable[..., Any] | None = None,
        source_ip: str | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if get is not None and source_ip is not None:
            raise ValueError("source_ip cannot be combined with a custom HTTP getter")
        self._config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self._get = get or partial(_session_get, source_ip=source_ip)
        self._now = now or (lambda: datetime.now(UTC))
        self._allowed_hosts = frozenset(str(host) for host in self._config["allowed_hosts"])
        self._max_document_bytes = int(self._config["max_document_bytes"])
        self._title_markers = {
            str(item["series_id"]): str(item["title_marker"])
            for item in self._config["series"]
        }
        if set(self._title_markers) != set(NBS_INFLATION_SERIES_IDS):
            raise ValueError("NBS inflation source config must declare CPI and PPI series")

    def discover_and_fetch(
        self,
        *,
        reference_date: date,
        reference_month: str | None = None,
        before_parse: Callable[[str, str, bytes], None] | None = None,
    ) -> list[NbsInflationReleaseDocument]:
        requested_month = self._normalize_reference_month(reference_month)
        listing_urls = self._config.get("listing_urls")
        if not isinstance(listing_urls, list) or not listing_urls:
            listing_urls = [self._config["listing_url"]]
        candidates: list[_ReleaseCandidate] = []
        for listing_url in listing_urls:
            listing_response = self._fetch_html(str(listing_url))
            candidates.extend(
                self._listing_candidates(
                    listing_response.content,
                    base_url=str(listing_response.url),
                    reference_date=reference_date,
                )
            )
        candidates = self._deduplicate_candidates(candidates)
        selected_months = (
            [requested_month]
            if requested_month is not None
            else self._latest_complete_months(candidates, limit=2)
        )
        selected = {
            (candidate.series_id, candidate.reference_month): candidate
            for candidate in candidates
            if candidate.reference_month in selected_months
        }
        for selected_month in selected_months:
            missing = [
                series_id
                for series_id in NBS_INFLATION_SERIES_IDS
                if (series_id, selected_month) not in selected
            ]
            if missing:
                raise NbsInflationReleaseError(
                    f"NBS inflation release {selected_month} is incomplete for: "
                    f"{', '.join(missing)}"
                )

        documents: list[NbsInflationReleaseDocument] = []
        for selected_month in selected_months:
            for series_id in NBS_INFLATION_SERIES_IDS:
                candidate = selected[(series_id, selected_month)]
                response = self._fetch_html(candidate.release_url)
                payload = bytes(response.content)
                release_url = str(response.url)
                if before_parse is not None:
                    before_parse(series_id, release_url, payload)
                observation = self._parse_observation(
                    series_id,
                    payload,
                    expected_month=selected_month,
                )
                documents.append(
                    NbsInflationReleaseDocument(
                        series_id=series_id,
                        reference_month=selected_month,
                        release_url=release_url,
                        fetched_at=self._now(),
                        html_bytes=payload,
                        observation=observation,
                    )
                )
        return documents

    def _fetch_html(self, url: str) -> Any:
        self._validate_url(url)
        try:
            response = self._get(
                url,
                headers={"User-Agent": "MOSS official macro ingest/1.0"},
                timeout=(5, 20),
                allow_redirects=False,
                verify=True,
            )
        except requests.RequestException as exc:
            raise NbsInflationReleaseError(f"NBS request failed: {exc}") from exc

        self._validate_url(str(response.url))
        if int(response.status_code) != 200:
            raise NbsInflationReleaseError(f"NBS request returned HTTP {response.status_code}")
        content_type = str(response.headers.get("Content-Type", "")).lower()
        if not (
            content_type.startswith("text/html")
            or content_type.startswith("application/xhtml+xml")
        ):
            raise NbsInflationReleaseError("NBS response must use an HTML content type")
        if len(response.content) > self._max_document_bytes:
            raise NbsInflationReleaseError("NBS response exceeds the configured maximum size")
        return response

    def _validate_url(self, value: str) -> None:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.hostname not in self._allowed_hosts:
            raise NbsInflationReleaseError(
                f"URL is not on a trusted NBS HTTPS host: {value}"
            )
        if parsed.username is not None or parsed.password is not None:
            raise NbsInflationReleaseError(
                f"URL is not on a trusted NBS HTTPS host: {value}"
            )

    def _listing_candidates(
        self,
        html_bytes: bytes,
        *,
        base_url: str,
        reference_date: date,
    ) -> list[_ReleaseCandidate]:
        soup = BeautifulSoup(self._decode_html(html_bytes), "html.parser")
        by_key: dict[tuple[str, str], _ReleaseCandidate] = {}
        for anchor in soup.find_all("a", href=True):
            title = "".join(anchor.get_text(" ", strip=True).split())
            period_match = _PERIOD_PATTERN.search(title)
            if period_match is None:
                continue
            series_id = next(
                (
                    candidate_series_id
                    for candidate_series_id, marker in self._title_markers.items()
                    if marker in title
                ),
                None,
            )
            if series_id is None:
                continue
            release_url = urljoin(base_url, str(anchor["href"]))
            release_match = _RELEASE_PATH_PATTERN.search(release_url)
            if release_match is None:
                continue
            release_date = datetime.strptime(release_match.group("date"), "%Y%m%d").date()
            if release_date > reference_date:
                continue
            self._validate_url(release_url)
            reference_month = (
                f"{period_match.group('year')}-{int(period_match.group('month')):02d}"
            )
            candidate = _ReleaseCandidate(
                series_id=series_id,
                reference_month=reference_month,
                release_date=release_date,
                release_url=release_url,
            )
            key = (series_id, reference_month)
            existing = by_key.get(key)
            if existing is None or candidate.release_date > existing.release_date:
                by_key[key] = candidate
        return sorted(
            by_key.values(),
            key=lambda item: (item.reference_month, item.release_date),
            reverse=True,
        )

    @staticmethod
    def _deduplicate_candidates(
        candidates: list[_ReleaseCandidate],
    ) -> list[_ReleaseCandidate]:
        by_key: dict[tuple[str, str], _ReleaseCandidate] = {}
        for candidate in candidates:
            key = (candidate.series_id, candidate.reference_month)
            existing = by_key.get(key)
            if existing is None or candidate.release_date > existing.release_date:
                by_key[key] = candidate
        return sorted(
            by_key.values(),
            key=lambda item: (item.reference_month, item.release_date),
            reverse=True,
        )

    @staticmethod
    def _latest_complete_months(
        candidates: list[_ReleaseCandidate],
        *,
        limit: int,
    ) -> list[str]:
        months_by_series = {
            series_id: {
                candidate.reference_month
                for candidate in candidates
                if candidate.series_id == series_id
            }
            for series_id in NBS_INFLATION_SERIES_IDS
        }
        complete = set.intersection(*(months_by_series.values()))
        if not complete:
            raise NbsInflationReleaseError(
                "No complete NBS CPI/PPI release month was found on the listing"
            )
        return sorted(complete, reverse=True)[: max(1, limit)]

    @staticmethod
    def _parse_observation(
        series_id: str,
        html_bytes: bytes,
        *,
        expected_month: str,
    ) -> dict[str, object]:
        pattern = _OBSERVATION_PATTERNS[series_id]
        soup = BeautifulSoup(NbsInflationReleaseAdapter._decode_html(html_bytes), "html.parser")
        text = re.sub(r"\s+", "", soup.get_text(" ", strip=True))
        matches = list(pattern.finditer(text))
        if not matches:
            raise NbsInflationReleaseError(
                f"NBS inflation release contains no supported observation for {series_id}"
            )
        parsed: set[tuple[str, float]] = set()
        for match in matches:
            reference_month = f"{match.group('year')}-{int(match.group('month')):02d}"
            if reference_month != expected_month:
                continue
            if match.group("flat"):
                value = 0.0
            else:
                value = float(match.group("value"))
                if match.group("direction") == "下降":
                    value = -value
            if not math.isfinite(value):
                raise NbsInflationReleaseError("NBS inflation value is non-finite")
            parsed.add((reference_month, value))
        if len(parsed) != 1:
            raise NbsInflationReleaseError(
                f"NBS inflation release has missing or conflicting values for {series_id}"
            )
        reference_month, value = parsed.pop()
        source_version = (
            "nbs_inflation_release_sha256_"
            f"{hashlib.sha256(html_bytes).hexdigest()}"
        )
        return {
            "trade_date": f"{reference_month}-01",
            "value": value,
            "source_version": source_version,
        }

    @staticmethod
    def _normalize_reference_month(value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])", text):
            raise ValueError("reference_month must use YYYY-MM")
        return text

    @staticmethod
    def _decode_html(html_bytes: bytes) -> str:
        try:
            return html_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise NbsInflationReleaseError("NBS HTML is not valid UTF-8") from exc
