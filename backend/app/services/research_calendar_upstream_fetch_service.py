from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import requests
from backend.app.repositories.raw_zone_repo import RawZoneRepository

MOF_TREASURY_VENDOR = "mof_treasury"
MOF_TREASURY_SOURCE_FAMILY = "research_calendar"
MOF_TREASURY_BASE = "https://zwgls.mof.gov.cn/ywgg/"
ADBC_POLICY_BANK_VENDOR = "adbc_policy_bank"
ADBC_POLICY_BANK_SOURCE_FAMILY = "research_calendar"
ADBC_POLICY_BANK_INDEX = "https://www.adbc.com.cn/n5/n15/index.html"
CHINABOND_POLICY_BANK_VENDOR = "chinabond_policy_bank"
CHINABOND_POLICY_BANK_SOURCE_FAMILY = "research_calendar"
CHINABOND_HOME = "https://www.chinabond.com.cn/"

_TITLE_PATTERN = re.compile(r'ArticleTitle"\s+content="([^"]+)"')
_PUBDATE_PATTERN = re.compile(r'PubDate"\s+content="([^"]+)"')
_AMOUNT_PATTERN = re.compile(r"(?:计划|竞争性招标面值总额|续发行面值金额|发行)(?:[^0-9]{0,12})(\d+(?:\.\d+)?)\s*亿元")
_TERM_PATTERN = re.compile(r"本(?:期|次)(?:续发行)?国债为\s*([0-9]+(?:\.[0-9]+)?(?:年|天))")
_AUCTION_TIME_PATTERN = re.compile(r"招标时间[。:：]?\s*([0-9年月日上下午至\-:：—\s]+)")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ADBC_TITLE_PATTERN = re.compile(r'<div class="[^"]*NewsContentTitle[^"]*"[^>]*>(.*?)</div>', re.I | re.S)
_ADBC_PUBDATE_PATTERN = re.compile(r"发布时间[^0-9]*(20\d{2}-\d{2}-\d{2})")
_ADBC_AMOUNT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)亿元")
_ADBC_TERM_PATTERN = re.compile(r"亿元(?:[^0-9]{0,8})(\d+(?:\.\d+)?)年")
_ADBC_RATE_PATTERN = re.compile(r"发行利率(?:为)?(\d+(?:\.\d+)?)%")
_ADBC_BID_COVER_PATTERN = re.compile(r"认购倍率(?:为)?(\d+(?:\.\d+)?)倍")
_CHINABOND_LINK_PATTERN = re.compile(r"<a href='([^']+)'[^>]*title=\"([^\"]+)\"", re.I)
_CHINABOND_PUBDATE_PATTERN = re.compile(r"发布时间[:：]?\s*(20\d{2})年(\d{2})月(\d{2})日")


class _AnchorTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._current_href: str | None = None
        self._title_parts: list[str] = []
        self.rows: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self._current_href = dict(attrs).get("href")
        self._title_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is None:
            return
        cleaned = " ".join(data.split())
        if cleaned:
            self._title_parts.append(cleaned)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        title = "".join(self._title_parts).strip()
        if title:
            self.rows.append((self._current_href, title))
        self._current_href = None
        self._title_parts = []


def _clean_html_text(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    return _WS_RE.sub("", text)


def _fetch_text(url: str) -> str:
    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    response.raise_for_status()
    apparent_encoding = getattr(response, "apparent_encoding", None)
    if apparent_encoding:
        try:
            return response.content.decode(apparent_encoding, errors="ignore")
        except LookupError:
            pass
    return response.content.decode("utf-8", errors="ignore")


def _iter_listing_urls(page_count: int) -> list[str]:
    urls = [urljoin(MOF_TREASURY_BASE, "index.htm")]
    for index in range(1, max(page_count, 1)):
        urls.append(urljoin(MOF_TREASURY_BASE, f"index_{index}.htm"))
    return urls


def _extract_notice_links(listing_html: str) -> list[tuple[str, str]]:
    matches = re.findall(r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', listing_html)
    rows: list[tuple[str, str]] = []
    for href, title in matches:
        title_text = str(title).strip()
        if "国债" not in title_text:
            continue
        if "发行工作有关事宜的通知" not in title_text and "国债业务公告" not in title_text:
            continue
        rows.append((urljoin(MOF_TREASURY_BASE, href), title_text))
    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url, title in rows:
        if url in seen:
            continue
        seen.add(url)
        deduped.append((url, title))
    return deduped


def _classify_event_kind(title: str) -> str:
    if "发行工作有关事宜的通知" in title:
        return "supply"
    return "auction"


def _severity_from_amount(amount: float | None) -> str:
    if amount is None:
        return "medium"
    if amount >= 1000:
        return "high"
    if amount >= 300:
        return "medium"
    return "low"


def _clean_fragment_text(fragment: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", fragment)).strip()


def _issuer_from_title(title: str) -> str | None:
    if "国家开发银行" in title:
        return "国家开发银行"
    if "中国进出口银行" in title:
        return "中国进出口银行"
    if "中国农业发展银行" in title:
        return "中国农业发展银行"
    return None


def _parse_detail(url: str, title_hint: str) -> dict[str, Any] | None:
    html = _fetch_text(url)
    clean = _clean_html_text(html)

    title_match = _TITLE_PATTERN.search(html)
    title = title_match.group(1).strip() if title_match else title_hint
    pubdate_match = _PUBDATE_PATTERN.search(html)
    pubdate = pubdate_match.group(1).strip() if pubdate_match else ""
    amount_match = _AMOUNT_PATTERN.search(clean)
    term_match = _TERM_PATTERN.search(clean)
    auction_time_match = _AUCTION_TIME_PATTERN.search(clean)

    if not pubdate:
        return None

    amount = float(amount_match.group(1)) if amount_match else None
    event_kind = _classify_event_kind(title)
    title_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    note_parts = [
        "来源: 财政部债务管理司",
        f"招标时间: {auction_time_match.group(1).strip()}" if auction_time_match else "",
    ]
    return {
        "event_id": f"mof-{event_kind}-{title_hash}",
        "event_date": pubdate[:10],
        "event_kind": event_kind,
        "title": title,
        "vendor_name": MOF_TREASURY_VENDOR,
        "source_family": MOF_TREASURY_SOURCE_FAMILY,
        "domain": "other",
        "issuer": "财政部",
        "market": "interbank",
        "instrument_type": "treasury_bond",
        "term_label": term_match.group(1) if term_match else None,
        "amount_numeric": amount,
        "amount_unit": "亿元" if amount is not None else None,
        "currency": "CNY",
        "status": "completed" if event_kind == "auction" else "scheduled",
        "severity": _severity_from_amount(amount),
        "headline_text": "；".join(part for part in note_parts if part),
        "headline_url": url,
        "headline_published_at": pubdate,
        "source_version": None,
        "vendor_version": None,
        "rule_version": "rv_supply_auction_v1",
    }


def _iter_adbc_listing_urls(page_count: int) -> list[str]:
    urls = [ADBC_POLICY_BANK_INDEX]
    for index in range(1, max(page_count, 1)):
        urls.append(urljoin(ADBC_POLICY_BANK_INDEX, f"index_{index}.html"))
    return urls


def _extract_adbc_notice_links(listing_html: str, listing_url: str) -> list[tuple[str, str]]:
    parser = _AnchorTextParser()
    parser.feed(listing_html)
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href, title in parser.rows:
        title_text = title.strip()
        if "债券" not in title_text or "发行" not in title_text:
            continue
        full_url = urljoin(listing_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        rows.append((full_url, title_text))
    return rows


def _parse_adbc_detail(url: str, title_hint: str) -> dict[str, Any] | None:
    html = _fetch_text(url)
    clean = _clean_html_text(html)

    title_match = _ADBC_TITLE_PATTERN.search(html)
    title = _clean_fragment_text(title_match.group(1)) if title_match else title_hint
    pubdate_match = _ADBC_PUBDATE_PATTERN.search(html)
    if pubdate_match is None:
        return None

    pubdate = pubdate_match.group(1)
    amount_match = _ADBC_AMOUNT_PATTERN.search(clean)
    term_match = _ADBC_TERM_PATTERN.search(clean)
    rate_match = _ADBC_RATE_PATTERN.search(clean)
    bid_cover_match = _ADBC_BID_COVER_PATTERN.search(clean)
    amount = float(amount_match.group(1)) if amount_match else None
    title_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]

    note_parts = [
        "来源: 中国农业发展银行",
        f"发行利率: {rate_match.group(1)}%" if rate_match else "",
        f"认购倍率: {bid_cover_match.group(1)}倍" if bid_cover_match else "",
    ]
    return {
        "event_id": f"adbc-auction-{title_hash}",
        "event_date": pubdate,
        "event_kind": "auction",
        "title": title,
        "vendor_name": ADBC_POLICY_BANK_VENDOR,
        "source_family": ADBC_POLICY_BANK_SOURCE_FAMILY,
        "domain": "other",
        "issuer": "中国农业发展银行",
        "market": "interbank",
        "instrument_type": "policy_bank_bond",
        "term_label": f"{term_match.group(1)}年" if term_match else None,
        "amount_numeric": amount,
        "amount_unit": "亿元" if amount is not None else None,
        "currency": "CNY",
        "status": "completed",
        "severity": _severity_from_amount(amount),
        "headline_text": "；".join(part for part in note_parts if part),
        "headline_url": url,
        "headline_published_at": f"{pubdate}T00:00:00",
        "source_version": None,
        "vendor_version": None,
        "rule_version": "rv_supply_auction_v1",
    }


def _extract_chinabond_policy_bank_links(homepage_html: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href, title in _CHINABOND_LINK_PATTERN.findall(homepage_html):
        title_text = title.strip()
        issuer = _issuer_from_title(title_text)
        if issuer not in {"国家开发银行", "中国进出口银行"}:
            continue
        if "金融债券" not in title_text:
            continue
        if "招投标书" not in title_text and "发行情况" not in title_text and "招标情况" not in title_text:
            continue
        full_url = urljoin(CHINABOND_HOME, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        rows.append((full_url, title_text))
    return rows


def _classify_chinabond_event(title: str) -> tuple[str, str]:
    if "招投标书" in title:
        return "supply", "scheduled"
    return "auction", "completed"


def _parse_chinabond_policy_bank_detail(url: str, title_hint: str) -> dict[str, Any] | None:
    html = _fetch_text(url)
    title_match = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
    title = _clean_fragment_text(title_match.group(1)) if title_match else title_hint
    issuer = _issuer_from_title(title)
    if issuer not in {"国家开发银行", "中国进出口银行"}:
        return None
    pubdate_match = _CHINABOND_PUBDATE_PATTERN.search(html)
    if pubdate_match is None:
        return None
    year, month, day = pubdate_match.groups()
    event_kind, status = _classify_chinabond_event(title)
    title_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return {
        "event_id": f"chinabond-{event_kind}-{title_hash}",
        "event_date": f"{year}-{month}-{day}",
        "event_kind": event_kind,
        "title": title,
        "vendor_name": CHINABOND_POLICY_BANK_VENDOR,
        "source_family": CHINABOND_POLICY_BANK_SOURCE_FAMILY,
        "domain": "other",
        "issuer": issuer,
        "market": "interbank",
        "instrument_type": "policy_bank_bond",
        "term_label": None,
        "amount_numeric": None,
        "amount_unit": None,
        "currency": "CNY",
        "status": status,
        "severity": "medium",
        "headline_text": "来源: 中国债券信息网",
        "headline_url": url,
        "headline_published_at": f"{year}-{month}-{day}T00:00:00",
        "source_version": None,
        "vendor_version": None,
        "rule_version": "rv_supply_auction_v1",
    }


def fetch_mof_treasury_supply_auction_rows(
    *,
    page_count: int = 2,
    max_items: int = 20,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for listing_url in _iter_listing_urls(page_count):
        try:
            listing_html = _fetch_text(listing_url)
        except Exception:
            continue
        for detail_url, title_hint in _extract_notice_links(listing_html):
            parsed = _parse_detail(detail_url, title_hint)
            if parsed is None:
                continue
            rows.append(parsed)
            if len(rows) >= max_items:
                return rows
    return rows


def fetch_adbc_policy_bank_supply_auction_rows(
    *,
    page_count: int = 1,
    max_items: int = 20,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for listing_url in _iter_adbc_listing_urls(page_count):
        try:
            listing_html = _fetch_text(listing_url)
        except Exception:
            continue
        for detail_url, title_hint in _extract_adbc_notice_links(listing_html, listing_url):
            try:
                parsed = _parse_adbc_detail(detail_url, title_hint)
            except Exception:
                continue
            if parsed is None:
                continue
            rows.append(parsed)
            if len(rows) >= max_items:
                return rows
    return rows


def fetch_chinabond_policy_bank_supply_auction_rows(
    *,
    max_items: int = 20,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        homepage_html = _fetch_text(CHINABOND_HOME)
    except Exception:
        return rows
    for detail_url, title_hint in _extract_chinabond_policy_bank_links(homepage_html):
        try:
            parsed = _parse_chinabond_policy_bank_detail(detail_url, title_hint)
        except Exception:
            continue
        if parsed is None:
            continue
        rows.append(parsed)
        if len(rows) >= max_items:
            return rows
    return rows


def archive_mof_treasury_supply_auction_raw(
    *,
    raw_zone_repo: RawZoneRepository,
    ingest_batch_id: str,
    page_count: int = 2,
    max_items: int = 20,
) -> dict[str, object]:
    rows = fetch_mof_treasury_supply_auction_rows(page_count=page_count, max_items=max_items)
    payload = {
        "vendor_kind": "research_calendar",
        "source": MOF_TREASURY_VENDOR,
        "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "rows": rows,
    }
    filename = "supply_auction_calendar.json"
    archived = raw_zone_repo.archive_bytes(
        "research_calendar",
        ingest_batch_id,
        filename,
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    )
    return {
        "raw_zone_path": str(archived["raw_zone_path"]),
        "row_count": len(rows),
        "sha256": archived["sha256"],
        "payload": payload,
    }


def fetch_research_calendar_supply_auction_rows(
    *,
    mof_page_count: int = 2,
    adbc_page_count: int = 1,
    max_items: int = 20,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for fetched in (
        fetch_mof_treasury_supply_auction_rows(page_count=mof_page_count, max_items=max_items),
        fetch_adbc_policy_bank_supply_auction_rows(page_count=adbc_page_count, max_items=max_items),
        fetch_chinabond_policy_bank_supply_auction_rows(max_items=max_items),
    ):
        for row in fetched:
            event_id = str(row.get("event_id", "")).strip()
            if not event_id or event_id in seen:
                continue
            seen.add(event_id)
            rows.append(row)
            if len(rows) >= max_items:
                return rows
    return rows


def archive_research_calendar_supply_auction_raw(
    *,
    raw_zone_repo: RawZoneRepository,
    ingest_batch_id: str,
    page_count: int = 2,
    max_items: int = 20,
) -> dict[str, object]:
    rows = fetch_research_calendar_supply_auction_rows(
        mof_page_count=page_count,
        adbc_page_count=1,
        max_items=max_items,
    )
    payload = {
        "vendor_kind": "research_calendar",
        "source": "research_calendar_upstream",
        "sources": [MOF_TREASURY_VENDOR, ADBC_POLICY_BANK_VENDOR, CHINABOND_POLICY_BANK_VENDOR],
        "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "rows": rows,
    }
    filename = "supply_auction_calendar.json"
    archived = raw_zone_repo.archive_bytes(
        "research_calendar",
        ingest_batch_id,
        filename,
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    )
    return {
        "raw_zone_path": str(archived["raw_zone_path"]),
        "row_count": len(rows),
        "sha256": archived["sha256"],
        "payload": payload,
    }
