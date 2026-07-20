from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backend.app.tasks import macro_toolkit_freshness_refresh as freshness


def test_latest_weekday_skips_weekend() -> None:
    assert freshness._latest_weekday_on_or_before(date(2026, 7, 19)) == date(2026, 7, 17)
    assert freshness._latest_weekday_on_or_before(date(2026, 7, 17)) == date(2026, 7, 17)


def test_refresh_macro_toolkit_freshness_dry_run(monkeypatch) -> None:
    calls: list[str] = []

    def fake_commodity(**kwargs):
        calls.append("commodity")
        assert kwargs["dry_run"] is True
        return {"status": "dry_run", "row_count": 0, "product_count": 3}

    def boom(*_args, **_kwargs):
        raise AssertionError("live writers must not run during dry-run")

    monkeypatch.setattr(freshness, "run_commodity_daily_ingest", fake_commodity)
    monkeypatch.setattr(freshness, "refresh_public_cross_asset_headlines", boom)
    monkeypatch.setattr(freshness, "materialize_cffex_member_rank", boom)
    monkeypatch.setattr(freshness, "get_settings", lambda: type("S", (), {"duckdb_path": "F:/tmp/moss.duckdb"})())

    result = freshness.refresh_macro_toolkit_freshness(
        dry_run=True,
        today=date(2026, 7, 20),
        commodity_products=("CU", "NHCI"),
    )
    assert result["status"] == "dry_run"
    assert calls == ["commodity"]
    assert [step["step"] for step in result["steps"]] == [
        "commodity_daily_ingest",
        "public_cross_asset_headlines",
        "cffex_member_rank",
    ]


def test_refresh_macro_toolkit_freshness_run_once_soft_fails_cffex(monkeypatch) -> None:
    monkeypatch.setattr(
        freshness,
        "run_commodity_daily_ingest",
        lambda **kwargs: {"status": "completed", "row_count": 12, "product_count": 2, **kwargs},
    )
    monkeypatch.setattr(
        freshness,
        "refresh_public_cross_asset_headlines",
        lambda **kwargs: {
            "status": "completed",
            "row_count": 100,
            "series_count": 10,
            "run_id": "public-1",
            "warnings": [],
            **kwargs,
        },
    )
    monkeypatch.setattr(
        freshness,
        "materialize_cffex_member_rank",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("vendor offline")),
    )
    monkeypatch.setattr(freshness, "get_settings", lambda: type("S", (), {"duckdb_path": "F:/tmp/moss.duckdb"})())

    result = freshness.refresh_macro_toolkit_freshness(today=date(2026, 7, 20))
    assert result["status"] == "success"
    cffex = next(step for step in result["steps"] if step["step"] == "cffex_member_rank")
    assert cffex["status"] == "soft_failed"
    assert cffex["trade_date"] == "2026-07-20"


def test_actor_registered() -> None:
    assert freshness.refresh_macro_toolkit_freshness_actor.actor_name == (
        "refresh_macro_toolkit_freshness"
    )


def test_cli_modes(monkeypatch, capsys) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    class _Message:
        message_id = "m-1"

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def send(self, **kwargs):
            assert kwargs.get("include_cffex") is True
            return _Message()

        def fn(self, **kwargs):
            return {"status": "success", "run_id": "r-1", "steps": [], **kwargs}

    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(
        cli,
        "refresh_macro_toolkit_freshness",
        lambda **kwargs: {"status": "dry_run", "run_id": "d-1", "steps": [], **kwargs},
    )

    assert cli.main(["--dry-run"]) == 0
    assert cli.main(["--enqueue"]) == 0
    assert cli.main(["--run-once"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 3
