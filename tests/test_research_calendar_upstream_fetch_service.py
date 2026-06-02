from __future__ import annotations

import json
from pathlib import Path

from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.services.research_calendar_upstream_fetch_service import (
    archive_research_calendar_supply_auction_raw,
    archive_mof_treasury_supply_auction_raw,
    fetch_adbc_policy_bank_supply_auction_rows,
    fetch_chinabond_policy_bank_supply_auction_rows,
    fetch_mof_treasury_supply_auction_rows,
)


class _FakeResponse:
    def __init__(self, body: str, status_code: int = 200) -> None:
        self.content = body.encode("utf-8")
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_fetch_mof_treasury_supply_auction_rows_parses_listing_and_detail(monkeypatch) -> None:
    listing_html = """
    <html><body>
      <a href="202601/t20260116_3982047.htm">关于2026年记账式附息（三期）国债发行工作有关事宜的通知</a>
      <a href="202602/t20260224_3983989.htm">国债业务公告2026年第26号</a>
    </body></html>
    """
    detail_supply = """
    <html><head>
      <meta name="ArticleTitle" content="关于2026年记账式附息（三期）国债发行工作有关事宜的通知"/>
      <meta name="PubDate" content="2026-01-19 16:32:00"/>
    </head><body>
      一、债券要素 （一）品种。本期国债为5年期固定利率附息债。
      （二）发行数量。本期国债竞争性招标面值总额1500亿元。
      （三）票面利率。本期国债票面利率通过竞争性招标确定。
      （四）招标时间。2026年1月21日上午10:35至11:35。
    </body></html>
    """
    detail_result = """
    <html><head>
      <meta name="ArticleTitle" content="国债业务公告2026年第26号"/>
      <meta name="PubDate" content="2026-02-24 16:32:00"/>
    </head><body>
      2026年记账式附息（五期）国债已完成招标工作。
      一、本期国债计划发行1350亿元，实际发行面值金额1350亿元。
      二、本期国债期限10年，经招标确定的票面利率为1.75%。
    </body></html>
    """

    def _fake_get(url: str, timeout: int = 20, **kwargs):
        if url.endswith("index.htm"):
            return _FakeResponse(listing_html)
        if url.endswith("t20260116_3982047.htm"):
            return _FakeResponse(detail_supply)
        if url.endswith("t20260224_3983989.htm"):
            return _FakeResponse(detail_result)
        raise AssertionError(url)

    monkeypatch.setattr(
        "backend.app.services.research_calendar_upstream_fetch_service.requests.get",
        _fake_get,
    )

    rows = fetch_mof_treasury_supply_auction_rows(page_count=1, max_items=10)

    assert len(rows) == 2
    assert rows[0]["event_kind"] == "supply"
    assert rows[0]["term_label"] == "5年"
    assert rows[0]["amount_numeric"] == 1500.0
    assert rows[1]["event_kind"] == "auction"
    assert rows[1]["amount_numeric"] == 1350.0


def test_archive_mof_treasury_supply_auction_raw_writes_raw_zone(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.research_calendar_upstream_fetch_service.fetch_mof_treasury_supply_auction_rows",
        lambda page_count=2, max_items=20: [
            {
                "event_id": "evt-1",
                "event_date": "2026-01-19",
                "event_kind": "supply",
                "title": "关于2026年记账式附息（三期）国债发行工作有关事宜的通知",
                "severity": "high",
            }
        ],
    )
    raw = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))

    result = archive_mof_treasury_supply_auction_raw(
        raw_zone_repo=raw,
        ingest_batch_id="research-calendar-fetch-batch",
    )

    payload = json.loads(Path(result["raw_zone_path"]).read_text(encoding="utf-8"))
    assert result["row_count"] == 1
    assert payload["source"] == "mof_treasury"
    assert payload["rows"][0]["event_id"] == "evt-1"


def test_fetch_adbc_policy_bank_supply_auction_rows_parses_listing_and_detail(monkeypatch) -> None:
    listing_html = """
    <html><body>
      <a href="../../n5/n15/c712589/content.html">农发行成功发行“绿动湖北”主题绿色债券</a>
      <a href="../../n5/n15/c713026/content.html">农发行与乌兹别克斯坦农业银行举行会谈 落实合作共识 深化金融交往</a>
    </body></html>
    """
    detail_html = """
    <html><body>
      <div class="NewsContentTitle">农发行成功发行“绿动湖北”主题绿色债券</div>
      <div class="NewsInfo">发布时间：2026-04-13</div>
      <div class="TRS_Editor">
        4月13日，中国农业发展银行在中央结算公司以公开招标方式，成功发行“绿动湖北”主题绿色债券40亿元3年，
        发行利率为1.47%，认购倍率为5.36倍。
      </div>
    </body></html>
    """

    def _fake_get(url: str, timeout: int = 20, **kwargs):
        if url.endswith("/n5/n15/index.html"):
            return _FakeResponse(listing_html)
        if url.endswith("/n5/n15/c712589/content.html"):
            return _FakeResponse(detail_html)
        raise AssertionError(url)

    monkeypatch.setattr(
        "backend.app.services.research_calendar_upstream_fetch_service.requests.get",
        _fake_get,
    )

    rows = fetch_adbc_policy_bank_supply_auction_rows(page_count=1, max_items=10)

    assert len(rows) == 1
    assert rows[0]["event_kind"] == "auction"
    assert rows[0]["issuer"] == "中国农业发展银行"
    assert rows[0]["instrument_type"] == "policy_bank_bond"
    assert rows[0]["amount_numeric"] == 40.0
    assert rows[0]["term_label"] == "3年"
    assert "认购倍率" in rows[0]["headline_text"]


def test_fetch_chinabond_policy_bank_supply_auction_rows_parses_homepage_and_detail(
    monkeypatch,
) -> None:
    homepage_html = """
    <html><body>
      <a href='./xxpl/.../fxjg_zgnyfzyhzq/202604/t20260423_855053131.html'
         title="中国农业发展银行关于2026年第五十八次金融债券发行情况的公告">ignored</a>
      <a href='./xxpl/.../fxwj_gjkfyhzq/202604/t20260423_855053051.html'
         title="国家开发银行金融债券招投标书（增发2025年第十三期和2026年第一、三、五期金融债券）">matched</a>
      <a href='./xxpl/.../fxjg_zgjckyh/202604/t20260423_855053777.html'
         title="中国进出口银行关于2026年第四十二次金融债券发行情况的公告">matched</a>
    </body></html>
    """
    cdb_detail_html = """
    <html><head>
      <title>国家开发银行金融债券招投标书（增发2025年第十三期和2026年第一、三、五期金融债券）</title>
    </head><body>
      <div>发布时间：2026年04月23日</div>
    </body></html>
    """
    exim_detail_html = """
    <html><head>
      <title>中国进出口银行关于2026年第四十二次金融债券发行情况的公告</title>
    </head><body>
      <div>发布时间：2026年04月23日</div>
    </body></html>
    """

    def _fake_get(url: str, timeout: int = 20, **kwargs):
        if url == "https://www.chinabond.com.cn/":
            return _FakeResponse(homepage_html)
        if url.endswith("t20260423_855053051.html"):
            return _FakeResponse(cdb_detail_html)
        if url.endswith("t20260423_855053777.html"):
            return _FakeResponse(exim_detail_html)
        raise AssertionError(url)

    monkeypatch.setattr(
        "backend.app.services.research_calendar_upstream_fetch_service.requests.get",
        _fake_get,
    )

    rows = fetch_chinabond_policy_bank_supply_auction_rows(max_items=10)

    assert len(rows) == 2
    assert rows[0]["issuer"] == "国家开发银行"
    assert rows[0]["event_kind"] == "supply"
    assert rows[0]["status"] == "scheduled"
    assert rows[0]["event_date"] == "2026-04-23"
    assert rows[1]["issuer"] == "中国进出口银行"
    assert rows[1]["event_kind"] == "auction"
    assert rows[1]["status"] == "completed"


def test_archive_research_calendar_supply_auction_raw_merges_multiple_sources(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "backend.app.services.research_calendar_upstream_fetch_service.fetch_mof_treasury_supply_auction_rows",
        lambda page_count=2, max_items=20: [
            {
                "event_id": "mof-evt-1",
                "event_date": "2026-04-17",
                "event_kind": "supply",
                "title": "财政部公告",
                "severity": "high",
                "vendor_name": "mof_treasury",
            }
        ],
    )
    monkeypatch.setattr(
        "backend.app.services.research_calendar_upstream_fetch_service.fetch_adbc_policy_bank_supply_auction_rows",
        lambda page_count=1, max_items=20: [
            {
                "event_id": "adbc-evt-1",
                "event_date": "2026-04-13",
                "event_kind": "auction",
                "title": "农发行绿色债券",
                "severity": "low",
                "vendor_name": "adbc_policy_bank",
            }
        ],
    )
    monkeypatch.setattr(
        "backend.app.services.research_calendar_upstream_fetch_service.fetch_chinabond_policy_bank_supply_auction_rows",
        lambda max_items=20: [
            {
                "event_id": "chinabond-evt-1",
                "event_date": "2026-04-23",
                "event_kind": "supply",
                "title": "国家开发银行金融债券招投标书",
                "severity": "medium",
                "vendor_name": "chinabond_policy_bank",
            }
        ],
    )
    raw = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))

    result = archive_research_calendar_supply_auction_raw(
        raw_zone_repo=raw,
        ingest_batch_id="research-calendar-fetch-batch",
    )

    payload = json.loads(Path(result["raw_zone_path"]).read_text(encoding="utf-8"))
    assert result["row_count"] == 3
    assert payload["source"] == "research_calendar_upstream"
    assert payload["sources"] == ["mof_treasury", "adbc_policy_bank", "chinabond_policy_bank"]
    assert {row["event_id"] for row in payload["rows"]} == {
        "mof-evt-1",
        "adbc-evt-1",
        "chinabond-evt-1",
    }
