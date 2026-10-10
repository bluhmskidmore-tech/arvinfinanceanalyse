"""Synthetic-only regressions for pinned batches and PnL cache source identity."""
from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelectionError,
    duckdb_read_scope,
    resolve_effective_read_path,
)
from backend.app.repositories.system_read_publication_repo import (
    _system_read_context_scope,
    current_system_read_context,
)
from backend.app.security.auth_context import AuthContext
from backend.app.services import pnl_v1_cache_support as cache
from backend.app.services import product_category_pnl_service as product
from backend.app.services.runtime_cache import InMemoryTTLCache


def _changed_same_stat(path: Path) -> None:
    before = path.stat()
    path.write_bytes(path.read_bytes().replace(b"100", b"200"))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size
    assert path.stat().st_mtime_ns == before.st_mtime_ns


def _cache_inputs(tmp_path: Path, source_kind: str):
    data = tmp_path / "inputs"
    data.mkdir()
    governance = tmp_path / "governance"
    governance.mkdir()
    database = tmp_path / "identity-only.duckdb"
    database.write_bytes(b"synthetic identity only; not a database")
    source = (data if source_kind == "direct" else tmp_path) / "synthetic.xls"
    source.write_bytes(b"synthetic amount=100")
    if source_kind == "archive":
        (governance / "source_manifest.jsonl").write_text(
            json.dumps({
                "source_family": "pnl",
                "status": "completed",
                "archived_path": str(source),
            }) + "\n",
            encoding="utf-8",
        )
    kwargs = dict(
        duckdb_path=str(database),
        governance_dir=str(governance),
        report_date="2026-09-30",
        data_root=data,
    )
    return source, kwargs


@pytest.mark.parametrize("source_kind", ["direct", "archive"])
def test_v1_full_cache_key_changes_with_source_bytes(tmp_path, source_kind):
    source, kwargs = _cache_inputs(tmp_path, source_kind)
    key_before = cache._pnl_v1_data_cache_key(**kwargs)
    assert key_before is not None
    values = InMemoryTTLCache(ttl_seconds=900)
    assert values.get_or_set(key_before, source.read_bytes) == b"synthetic amount=100"
    _changed_same_stat(source)
    key_after = cache._pnl_v1_data_cache_key(**kwargs)
    assert key_after is not None
    assert key_before != key_after
    assert values.get_or_set(key_after, source.read_bytes) == b"synthetic amount=200"


@pytest.mark.parametrize("source_kind", ["direct", "archive"])
def test_unreadable_source_bypasses_cache_instead_of_reusing_an_old_key(
    tmp_path, monkeypatch, source_kind,
):
    _source, kwargs = _cache_inputs(tmp_path, source_kind)

    def unreadable(_path):
        raise OSError("synthetic unreadable source")

    monkeypatch.setattr(cache, "sha256_file", unreadable)
    assert cache._pnl_v1_data_cache_key(**kwargs) is None


@pytest.mark.parametrize("count", [1, 2, 6])
def test_product_batch_reads_frozen_amount_and_system_identity(tmp_path, count):
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "snapshot.duckdb"
    for path, amount in [(active, 200), (snapshot, 100)]:
        with duckdb.connect(str(path)) as conn:
            conn.execute("CREATE TABLE synthetic_amount(amount INTEGER)")
            conn.execute("INSERT INTO synthetic_amount VALUES (?)", [amount])
    context = SimpleNamespace(
        publication=SimpleNamespace(database_path=snapshot, generation="G1"),
        generation="G1",
    )
    ready = Barrier(count)

    def read_period(report_date):
        # Force overlapping Context entries so a single shared copy cannot pass.
        ready.wait(timeout=5)
        with duckdb.connect(resolve_effective_read_path(active), read_only=True) as conn:
            amount = conn.execute("SELECT amount FROM synthetic_amount").fetchone()[0]
        system = current_system_read_context()
        return {
            "date": report_date,
            "amount": amount,
            "generation": system.generation if system else None,
        }

    dates = [f"2026-{month:02d}-01" for month in range(1, count + 1)]
    outer_system_context = current_system_read_context()
    with _system_read_context_scope(SimpleNamespace(duckdb_path=active), context):
        rows = product._map_product_category_batch(read_period, dates)
        assert current_system_read_context() is context
    assert rows == [{"date": d, "amount": 100, "generation": "G1"} for d in dates]
    assert current_system_read_context() is outer_system_context


@pytest.mark.parametrize("count", [1, 2, 6])
def test_product_batch_cannot_bypass_required_snapshot(tmp_path, count):
    active = tmp_path / "active.duckdb"
    with duckdb_read_scope(None, required_online=True, active_path=active):
        with pytest.raises(DuckDBReadSelectionError):
            product._map_product_category_batch(
                lambda _date: {"path": resolve_effective_read_path(active)},
                ["2026-09-30"] * count,
            )


@pytest.mark.parametrize("count", [1, 2, 6])
def test_product_batch_rejects_snapshot_loss_after_selection(tmp_path, count):
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "snapshot.duckdb"
    snapshot.write_bytes(b"synthetic selection marker")
    context = SimpleNamespace(
        publication=SimpleNamespace(database_path=snapshot, generation="G1"),
    )
    with _system_read_context_scope(SimpleNamespace(duckdb_path=active), context):
        snapshot.unlink()
        with pytest.raises(DuckDBReadSelectionError):
            product._map_product_category_batch(
                lambda _date: {"path": resolve_effective_read_path(active)},
                ["2026-09-30"] * count,
            )


def _period_meta(source, quality="ok", scenario=False):
    return {
        "trace_id": "synthetic",
        "source_version": source,
        "rule_version": "synthetic-rule",
        "cache_version": "synthetic-cache",
        "quality_flag": quality,
        "basis": "scenario" if scenario else "formal",
        "formal_use_allowed": not scenario,
        "scenario_flag": scenario,
    }


def _read_history(kind, dates, monkeypatch, detail):
    if kind == "history":
        monkeypatch.setattr(product, "product_category_pnl_envelope", detail)
        return product.product_category_history_envelope("unused", dates, "monthly")
    monkeypatch.setattr(product, "product_category_attribution_envelope", detail)
    return product.product_category_attribution_history_envelope("unused", dates, "mom")


@pytest.mark.parametrize("rate", [0.0, 2.5])
def test_product_history_preserves_scenario_and_all_period_lineage(monkeypatch, rate):
    def detail(_path, *, report_date, **_kwargs):
        return {
            "result": None,
            "result_meta": _period_meta("sv_" + report_date, scenario=True),
        }

    monkeypatch.setattr(product, "product_category_pnl_envelope", detail)
    result = product.product_category_history_envelope(
        "unused", ["2026-08-31", "2026-09-30"], "monthly", rate,
    )
    meta = result["result_meta"]
    assert meta["basis"] == "scenario"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is True
    assert meta["source_version"] == "sv_2026-08-31__sv_2026-09-30"
    assert meta["rule_version"] == "synthetic-rule"
    assert meta["filters_applied"]["scenario_rate_pct"] == rate


@pytest.mark.parametrize("kind", ["history", "attribution-history"])
@pytest.mark.parametrize("quality", ["warning", "stale", "error"])
def test_product_history_does_not_hide_period_quality(monkeypatch, kind, quality):
    result = _read_history(kind, ["2026-09-30"], monkeypatch, lambda *_a, **_k: {
        "result": None,
        "result_meta": _period_meta("sv_synthetic", quality),
    })
    assert result["result_meta"]["quality_flag"] == quality


@pytest.mark.parametrize("kind", ["history", "attribution-history"])
@pytest.mark.parametrize("worst", ["warning", "stale", "error"])
def test_product_batch_quality_and_lineage_are_order_independent(monkeypatch, kind, worst):
    def detail(_path, *, report_date, **_kwargs):
        meta = _period_meta("sv_" + report_date, worst if report_date.endswith("31") else "ok")
        meta["rule_version"] = "rv_" + report_date
        return {"result": None, "result_meta": meta}

    dates = ["2026-08-31", "2026-09-30"]
    first = _read_history(kind, dates, monkeypatch, detail)
    second = _read_history(kind, dates[::-1], monkeypatch, detail)
    for field in ["quality_flag", "source_version", "rule_version"]:
        assert first["result_meta"][field] == second["result_meta"][field]
    assert first["result_meta"]["quality_flag"] == worst
    assert first["result_meta"]["source_version"] == "sv_2026-08-31__sv_2026-09-30"
    assert first["result_meta"]["rule_version"] == "rv_2026-08-31__rv_2026-09-30"
    assert [item["report_date"] for item in first["result"]["items"]] == dates


@pytest.mark.parametrize("kind", ["history", "attribution-history"])
def test_missing_period_does_not_reduce_an_error_to_warning(monkeypatch, kind):
    def detail(_path, *, report_date, **_kwargs):
        if report_date == "2026-08-31":
            raise product.ProductCategoryReadModelNotFoundError("synthetic missing period")
        return {"result": None, "result_meta": _period_meta("sv_synthetic", "error")}

    result = _read_history(kind, ["2026-08-31", "2026-09-30"], monkeypatch, detail)
    assert [item["status"] for item in result["result"]["items"]] == ["not_found", "ok"]
    assert result["result_meta"]["quality_flag"] == "error"


@pytest.mark.parametrize("kind", ["history", "attribution-history"])
def test_empty_batch_keeps_existing_formal_empty_identity(monkeypatch, kind):
    def unexpected_read(*_args, **_kwargs):
        pytest.fail("An empty batch must not read a period")

    result = _read_history(kind, [], monkeypatch, unexpected_read)
    assert result["result"]["items"] == []
    assert result["result_meta"]["quality_flag"] == "ok"
    assert result["result_meta"]["source_version"] == "sv_none"
    assert result["result_meta"]["rule_version"] == product.RULE_VERSION


def test_zero_scenario_and_worst_period_quality_survive_history_json(monkeypatch, tmp_path):
    from backend.app.api.routes import product_category_pnl as route

    # Exercise the actual history service and response model; storage/auth are stubbed.
    monkeypatch.setattr(route, "get_settings", lambda: SimpleNamespace(duckdb_path=tmp_path / "unused.duckdb"))
    monkeypatch.setattr(route, "_ensure_product_category_pnl_read_allowed", lambda *_a: None)

    def detail(_path, *, report_date, scenario_rate_pct, **_kwargs):
        assert scenario_rate_pct == 0.0
        meta = _period_meta("sv_" + report_date, "stale" if report_date.endswith("31") else "ok", True)
        meta["rule_version"] = "rv_" + report_date
        return {"result": None, "result_meta": meta}

    # Earlier tests can replace the canonical service module after collection.
    # Stub reads in the globals used by the route-bound history function.
    monkeypatch.setitem(
        route.product_category_history_envelope.__globals__,
        "product_category_pnl_envelope",
        detail,
    )
    app = FastAPI()
    app.dependency_overrides[route.get_auth_context] = lambda: AuthContext(user_id="synthetic-history")
    app.include_router(route.router)
    with TestClient(app) as client:
        response = client.get("/ui/pnl/product-category/history", params={
            "report_dates": "2026-08-31,2026-09-30",
            "view": "monthly",
            "scenario_rate_pct": 0,
        })
    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["basis"] == "scenario"
    assert body["result_meta"]["formal_use_allowed"] is False
    assert body["result_meta"]["scenario_flag"] is True
    assert body["result_meta"]["quality_flag"] == "stale"
    assert body["result_meta"]["source_version"] == "sv_2026-08-31__sv_2026-09-30"
    assert body["result_meta"]["rule_version"] == "rv_2026-08-31__rv_2026-09-30"
    assert body["result"]["scenario_rate_pct"] == 0.0
    assert [item["report_date"] for item in body["result"]["items"]] == ["2026-08-31", "2026-09-30"]
