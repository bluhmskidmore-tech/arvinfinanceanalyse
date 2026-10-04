from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager

import pytest

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]


@pytest.mark.parametrize("consumer", ["pretrade", "news"])
def test_downstream_vendor_calls_use_existing_https_transport(monkeypatch, consumer):
    from backend.app.tasks import choice_stock_materialize, tushare_news_ingest
    from scripts.run_livermore_daily_pretrade_refresh import probe_target_market_data_availability

    calls = []

    def post(url, *, json, timeout):
        assert url == "https://api.tushare.pro"
        assert json["token"] == "test-market-routing-token"
        assert timeout
        calls.append(json["api_name"])
        if json["api_name"] == "trade_cal":
            data = {"fields": ["cal_date", "is_open"], "items": [["20260916", 1]]}
        else:
            data = {"fields": ["trade_date"], "items": [["20260916"]]}

        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"code": 0, "data": data}

        return Response()

    monkeypatch.setenv("MOSS_TUSHARE_TOKEN", "test-market-routing-token")
    monkeypatch.setattr(choice_stock_materialize.requests, "post", post)
    if consumer == "pretrade":
        result = probe_target_market_data_availability(target_date="2026-09-16")
        assert result["status"] == "ready"
        assert calls == ["trade_cal", "index_daily", "daily"]
    else:
        from backend.app.tasks.choice_news import _ingest_tushare_news_to_choice_news

        def materialize(*, pro, **kwargs):
            return {"status": "completed", "fetched": len(pro.news(src="sina"))}

        monkeypatch.setattr(tushare_news_ingest, "materialize_tushare_news_to_choice_news", materialize)
        result = _ingest_tushare_news_to_choice_news(duckdb_path="unused.duckdb")
        assert result == {"status": "completed", "fetched": 1}
        assert calls == ["news"]


@pytest.mark.parametrize(
    "module_name,operation",
    [
        ("scripts.run_livermore_daily_pretrade_refresh", "run_livermore_daily_pretrade_refresh"),
        ("scripts.refresh_tushare_news_backup", "refresh_tushare_news_backup"),
    ],
)
@pytest.mark.parametrize("fails", [False, True])
def test_downstream_cli_binds_network_and_restores_after_failure(monkeypatch, module_name, operation, fails):
    from backend.app.network import source_bound_socks_proxy
    from scripts import choice_stock_daily_refresh

    module = importlib.import_module(module_name)
    events = []

    @contextmanager
    def network(source_ip):
        assert source_ip == "192.0.2.10"
        events.append("bound")
        try:
            yield
        finally:
            events.append("restored")

    def run(**kwargs):
        assert events == ["bound"]
        events.append("called")
        if fails:
            raise RuntimeError("vendor unavailable")
        return {"status": "completed"}

    monkeypatch.setattr(source_bound_socks_proxy, "resolve_vendor_source_ip", lambda value: value)
    monkeypatch.setattr(choice_stock_daily_refresh, "_vendor_source_network", network)
    monkeypatch.setattr(module, operation, run)
    monkeypatch.setattr(sys, "argv", [module_name, "--vendor-source-ip", "192.0.2.10"])
    if fails and operation == "refresh_tushare_news_backup":
        with pytest.raises(RuntimeError, match="vendor unavailable"):
            module.main()
    else:
        assert module.main() == (2 if fails else 0)
    assert events == ["bound", "called", "restored"]


def test_news_cli_rejects_source_binding_for_separate_worker(monkeypatch):
    from scripts import refresh_tushare_news_backup

    monkeypatch.setattr(
        refresh_tushare_news_backup,
        "refresh_tushare_news_backup",
        lambda **kwargs: pytest.fail("must not enqueue an unbound worker"),
    )
    with pytest.raises(SystemExit) as exc:
        refresh_tushare_news_backup.main(["--vendor-source-ip", "192.0.2.10", "--enqueue"])
    assert exc.value.code == 2
