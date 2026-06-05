from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.app.services.tushare_news_ingest_service import ingest_tushare_npr_to_choice_news


class _FakeFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def __len__(self) -> int:
        return len(self._rows)

    def to_dict(self, orient: str) -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError(orient)
        return list(self._rows)


class _FakePro:
    """Mock Tushare client. `pro.npr` = National Policy Repository (政策法规库)."""

    def __init__(
        self,
        *,
        policy_rows: list[dict[str, object]] | None = None,
        news_rows: list[dict[str, object]] | None = None,
        cctv_rows_by_date: dict[str, list[dict[str, object]]] | None = None,
        major_rows: list[dict[str, object]] | None = None,
        research_rows: list[dict[str, object]] | None = None,
    ) -> None:
        self._policy_rows = policy_rows or []
        self._news_rows = news_rows or []
        self._cctv_by_date = cctv_rows_by_date or {}
        self._major_rows = major_rows or []
        self._research_rows = research_rows or []

    def npr(self, **_kwargs: object) -> _FakeFrame:
        return _FakeFrame(self._policy_rows)

    def news(self, **_kwargs: object) -> _FakeFrame:
        return _FakeFrame(self._news_rows)

    def cctv_news(self, *, date: str) -> _FakeFrame:
        return _FakeFrame(self._cctv_by_date.get(date, []))

    def major_news(self, **_kwargs: object) -> _FakeFrame:
        return _FakeFrame(self._major_rows)

    def research_report(self, **_kwargs: object) -> _FakeFrame:
        return _FakeFrame(self._research_rows)


def _install_fake(monkeypatch: pytest.MonkeyPatch, pro: _FakePro) -> None:
    class _FakeTushare:
        @staticmethod
        def pro_api(_token: str) -> _FakePro:
            return pro

    monkeypatch.setitem(sys.modules, "tushare", _FakeTushare())


def test_ingest_writes_all_five_streams(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOSS_TUSHARE_TOKEN", "test-token")
    monkeypatch.setitem(
        ingest_tushare_npr_to_choice_news.__globals__,
        "_resolve_tushare_token",
        lambda: "test-token",
    )
    today = datetime.now().date()
    recent_day = today.strftime("%Y-%m-%d")

    policy_rows = [
        {
            "pubtime": "2026-04-21 10:00:00",
            "title": "政策一",
            "pcode": "国发〔2026〕1号",
            "puborg": "国务院",
            "url": "https://example.gov/policy/1",
        }
    ]
    news_rows = [
        {"datetime": "2026-04-21 11:00:00", "title": "NEWS标题", "content": "正文"}
    ]
    cctv_rows_by_date: dict[str, list[dict[str, object]]] = {}
    for offset in range(3):
        d = (today - timedelta(days=offset)).strftime("%Y%m%d")
        cctv_rows_by_date[d] = [{"date": d, "title": f"联播{offset}", "content": "联播正文"}]
    major_rows = [
        {
            "title": "长篇标题",
            "content": "长篇正文",
            "pub_time": "2026-04-21 09:00:00",
            "src": "新浪财经",
        }
    ]
    research_rows = [
        {
            "title": "研报标题",
            "url": "https://example.com/report.pdf",
            "pub_date": "2026-04-21",
            "org": "某券商",
            "rating": "买入",
        }
    ]
    policy_rows[0]["pubtime"] = f"{recent_day} 10:00:00"
    news_rows[0]["datetime"] = f"{recent_day} 11:00:00"
    major_rows[0]["pub_time"] = f"{recent_day} 09:00:00"
    research_rows[0]["pub_date"] = recent_day

    pro = _FakePro(
        policy_rows=policy_rows,
        news_rows=news_rows,
        cctv_rows_by_date=cctv_rows_by_date,
        major_rows=major_rows,
        research_rows=research_rows,
    )
    _install_fake(monkeypatch, pro)

    db = tmp_path / "news.duckdb"
    result = ingest_tushare_npr_to_choice_news(
        str(db),
        limit=5,
        news_limit=10,
        cctv_lookback_days=3,
        major_lookback_hours=24,
        research_lookback_days=2,
    )

    assert result["status"] == "completed"
    for kind in ("policy", "news", "cctv", "major", "research"):
        assert kind in result, kind
        assert result[kind]["fetched"] >= 1, kind
        assert "error" not in result[kind], (kind, result[kind])

    conn = duckdb.connect(str(db), read_only=True)
    try:
        groups = {
            str(row[0])
            for row in conn.execute("select distinct group_id from choice_news_event").fetchall()
        }
        assert {
            "tushare_policy",
            "tushare_news",
            "tushare_cctv",
            "tushare_major",
            "tushare_research",
        } <= groups
        # research / policy 都应当带 _url（下游前端凭它出"查看原文"按钮）
        for group_id in ("tushare_research", "tushare_policy"):
            payload_json = conn.execute(
                "select payload_json from choice_news_event where group_id = ? limit 1",
                [group_id],
            ).fetchone()
            assert payload_json is not None, group_id
            assert '"_url"' in str(payload_json[0]), group_id
        wh_count = conn.execute("select count(*) from fact_news_event").fetchone()
        assert int(wh_count[0]) >= 5
    finally:
        conn.close()


def test_ingest_strips_html_from_news_payload_and_warehouse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOSS_TUSHARE_TOKEN", "test-token")
    monkeypatch.setitem(
        ingest_tushare_npr_to_choice_news.__globals__,
        "_resolve_tushare_token",
        lambda: "test-token",
    )
    recent_day = datetime.now().date().strftime("%Y-%m-%d")
    pro = _FakePro(
        news_rows=[
            {
                "datetime": f"{recent_day} 11:00:00",
                "title": "<span>Rates &amp; Credit</span>",
                "content": "<p>Yield&nbsp;<b>down</b></p>",
            }
        ]
    )
    _install_fake(monkeypatch, pro)

    db = tmp_path / "news-html.duckdb"
    result = ingest_tushare_npr_to_choice_news(
        str(db),
        limit=1,
        news_limit=1,
        cctv_lookback_days=1,
        major_lookback_hours=1,
        research_lookback_days=1,
    )

    assert result["news"]["inserted"] == 1
    conn = duckdb.connect(str(db), read_only=True)
    try:
        payload_text = conn.execute(
            "select payload_text from choice_news_event where group_id = 'tushare_news'"
        ).fetchone()[0]
        assert "<" not in str(payload_text)
        assert ">" not in str(payload_text)
        assert "Rates & Credit" in str(payload_text)
        assert "Yield down" in str(payload_text)

        title, content, summary = conn.execute(
            """
            select title, content, summary
            from fact_news_event
            where source = 'tushare_news'
            limit 1
            """
        ).fetchone()
        warehouse_text = " ".join(str(value or "") for value in (title, content, summary))
        assert "<" not in warehouse_text
        assert ">" not in warehouse_text
        assert "Rates & Credit" in warehouse_text
        assert "Yield down" in warehouse_text
    finally:
        conn.close()


def test_one_block_failure_does_not_break_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOSS_TUSHARE_TOKEN", "test-token")
    monkeypatch.setitem(
        ingest_tushare_npr_to_choice_news.__globals__,
        "_resolve_tushare_token",
        lambda: "test-token",
    )
    recent_day = datetime.now().date().strftime("%Y-%m-%d")

    class _BrokenResearch(_FakePro):
        def research_report(self, **_kwargs: object) -> _FakeFrame:
            raise RuntimeError("research_report: 权限不足")

    pro = _BrokenResearch(
        policy_rows=[
            {"pubtime": f"{recent_day} 10:00:00", "title": "T", "pcode": "P", "puborg": "X"}
        ],
    )
    _install_fake(monkeypatch, pro)

    result = ingest_tushare_npr_to_choice_news(
        str(tmp_path / "x.duckdb"),
        limit=2,
        news_limit=2,
        cctv_lookback_days=1,
        major_lookback_hours=1,
        research_lookback_days=1,
    )

    assert result["status"] == "completed"
    assert result["policy"]["inserted"] == 1
    assert "error" in result["research"]
    assert "权限不足" in str(result["research"]["error"])


def test_ingest_requires_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOSS_TUSHARE_TOKEN", raising=False)
    # Also neutralise the Settings fallback (config/.env may carry a token in dev environments).
    import backend.app.services.tushare_news_ingest_service as mod

    monkeypatch.setattr(mod, "_resolve_tushare_token", lambda: "")
    monkeypatch.setitem(
        ingest_tushare_npr_to_choice_news.__globals__,
        "_resolve_tushare_token",
        lambda: "",
    )
    with pytest.raises(RuntimeError, match="MOSS_TUSHARE_TOKEN"):
        ingest_tushare_npr_to_choice_news(str(tmp_path / "x.duckdb"), limit=1)
