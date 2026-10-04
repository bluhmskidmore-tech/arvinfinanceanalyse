"""Synthetic regressions for cache, amount, date and archive boundaries."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("with_dependency", [False, True])
def test_ledger_cache_tracks_primary_content_with_same_size_and_mtime(tmp_path, monkeypatch, with_dependency):
    from backend.app.services import ledger_pnl_service as service

    primary = tmp_path / "ledger.xlsx"
    primary.write_bytes(b"100")
    dependency = tmp_path / "prior.xlsx"
    dependency.write_bytes(b"050")
    average = tmp_path / "average.xlsx"
    average.write_bytes(b"synthetic-average")
    pair = SimpleNamespace(
        ledger_path=primary,
        avg_path=average,
        ledger_dependencies=(dependency,) if with_dependency else (),
    )
    calls = []

    def build_facts(source_pair):
        amount = source_pair.ledger_path.read_bytes()
        calls.append(amount)
        return [amount]

    monkeypatch.setattr(service, "_FACTS_CACHE", {})
    monkeypatch.setattr(service, "build_ledger_only_facts", build_facts)
    assert service._cached_ledger_only_facts(pair) == [b"100"]
    assert service._cached_ledger_only_facts(pair) == [b"100"]
    assert calls == [b"100"]
    stat = primary.stat()
    primary.write_bytes(b"200")
    os.utime(primary, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert primary.stat().st_size == stat.st_size
    assert primary.stat().st_mtime_ns == stat.st_mtime_ns
    assert service._cached_ledger_only_facts(pair) == [b"200"]
    assert calls == [b"100", b"200"]


def test_ledger_cache_preserves_dependency_hash_and_ignores_average_only_change(tmp_path, monkeypatch):
    from backend.app.services import ledger_pnl_service as service

    primary, prior, average = [tmp_path / name for name in ("ledger.xlsx", "prior.xlsx", "average.xlsx")]
    primary.write_bytes(b"100")
    prior.write_bytes(b"050")
    average.write_bytes(b"aaa")
    pair = SimpleNamespace(ledger_path=primary, avg_path=average, ledger_dependencies=(prior,))
    calls = []

    def build_facts(source_pair):
        value = source_pair.ledger_path.read_bytes() + source_pair.ledger_dependencies[0].read_bytes()
        calls.append(value)
        return [value]

    monkeypatch.setattr(service, "_FACTS_CACHE", {})
    monkeypatch.setattr(service, "build_ledger_only_facts", build_facts)
    assert service._cached_ledger_only_facts(pair) == [b"100050"]
    average.write_bytes(b"bbb")
    assert service._cached_ledger_only_facts(pair) == [b"100050"]
    assert len(calls) == 1
    stat = prior.stat()
    prior.write_bytes(b"060")
    os.utime(prior, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert service._cached_ledger_only_facts(pair) == [b"100060"]


@pytest.mark.parametrize("value", ["1,2", "1,,234", "12,34.56", "1234,567", ",123", "123,"])
@pytest.mark.parametrize("family", ["zqtz", "tyw"])
def test_required_amount_rejects_ambiguous_comma_grouping(monkeypatch, family, value):
    from tests.test_snapshot_row_parse import _parse_synthetic_amount_sheet, _synthetic_amount_sheet

    rows = _synthetic_amount_sheet(family)
    rows[2][1] = value
    with pytest.raises(ValueError, match=r"required amount invalid:.*row=3, column=2"):
        _parse_synthetic_amount_sheet(monkeypatch, family, rows)


@pytest.mark.parametrize("value", ["1,234.56", "-1,234,567.89", "+1,234", " 1,234.50 ", "0", "1234.56"])
@pytest.mark.parametrize("family", ["zqtz", "tyw"])
def test_required_amount_keeps_valid_grouping_and_decimal_precision(monkeypatch, family, value):
    from decimal import Decimal

    from tests.test_snapshot_row_parse import _parse_synthetic_amount_sheet, _synthetic_amount_sheet

    rows = _synthetic_amount_sheet(family)
    rows[2][1] = value
    parsed = _parse_synthetic_amount_sheet(monkeypatch, family, rows)
    amount_key = "face_value_native" if family == "zqtz" else "principal_native"
    assert parsed[0][amount_key] == Decimal(value.strip().replace(",", ""))


@pytest.mark.parametrize("surface", ["carry", "spread", "krd", "campisi"])
def test_attribution_before_all_snapshots_never_reads_future_positions(monkeypatch, surface):
    from backend.app.services import pnl_attribution_service as service

    class FutureOnlyRepository:
        def list_report_dates(self):
            return ["2026-06-30", "2026-05-31"]

        def fetch_bond_analytics_rows(self, **kwargs):
            pytest.fail("A request before all snapshots must not read future positions")

    repo = FutureOnlyRepository()
    monkeypatch.setattr(service, "_bond_repo", lambda: repo)
    monkeypatch.setattr(service, "_curve_repo", lambda: repo)
    requested = "2026-04-30"
    if surface == "carry":
        envelope = service._carry_roll_down_envelope_uncached(report_date=requested, ftp_rate_pct=0)
    elif surface == "spread":
        envelope = service._spread_attribution_envelope_uncached(report_date=requested, lookback_days=30)
    elif surface == "krd":
        envelope = service._krd_attribution_envelope_uncached(report_date=requested, lookback_days=30)
    else:
        envelope = service._campisi_attribution_envelope_uncached(
            start_date="2026-03-31", end_date=requested, lookback_days=30,
        )
    meta = envelope["result_meta"]
    assert meta["quality_flag"] == "warning"
    assert meta["formal_use_allowed"] is False
    assert meta["requested_report_date"] == requested
    assert meta.get("resolved_report_date") is None
    assert envelope["result"]["report_date"] == requested


@pytest.mark.parametrize(
    ("requested", "expected"),
    [("2026-05-31", "2026-05-31"), ("2026-06-15", "2026-05-31"), ("2026-07-31", "2026-06-30"), (None, "2026-05-31")],
)
def test_attribution_keeps_eligible_and_default_date_selection(monkeypatch, requested, expected):
    from backend.app.services import pnl_attribution_service as service

    monkeypatch.setattr(service, "_latest_formal_report_date", lambda: "2026-05-31")
    assert service._resolve_bond_report_date(["2026-06-30", "2026-05-31"], requested) == expected


def _synthetic_ingest(tmp_path):
    from backend.app.repositories.object_store_repo import ObjectStoreRepository
    from backend.app.repositories.source_manifest_repo import SourceManifestRepository
    from backend.app.services.ingest_service import IngestService

    root = tmp_path / "inputs"
    root.mkdir()
    source = root / "synthetic.csv"
    source.write_bytes(b"amount\n100\n")
    manifest = SourceManifestRepository()
    store = ObjectStoreRepository(
        endpoint="unused", access_key="synthetic", secret_key="synthetic", bucket="synthetic",
        mode="local", local_archive_path=str(tmp_path / "archive"),
    )
    return IngestService(root, manifest, store), source


def test_ingest_rejects_changed_content_after_scan_before_manifest(tmp_path, monkeypatch):
    service, source = _synthetic_ingest(tmp_path)
    original_scan = service.scan

    def changed_after_scan(*args, **kwargs):
        rows = original_scan(*args, **kwargs)
        source.write_bytes(b"amount\n200\n")
        return rows

    monkeypatch.setattr(service, "scan", changed_after_scan)
    with pytest.raises(ValueError, match="changed after scan"):
        service.scan_and_archive()
    assert service.manifest_repo.rows == []


def test_ingest_hash_and_archive_share_content_despite_change_during_archive(tmp_path, monkeypatch):
    service, source = _synthetic_ingest(tmp_path)
    original_content = source.read_bytes()
    original_name = service.object_store_repo._build_archived_filename

    def mutate_during_archive(*args, **kwargs):
        source.write_bytes(b"amount\n200\n")
        return original_name(*args, **kwargs)

    monkeypatch.setattr(service.object_store_repo, "_build_archived_filename", mutate_during_archive)
    rows = service.scan_and_archive()
    archived = Path(rows[0]["archived_path"]).read_bytes()
    assert archived == original_content
    assert rows[0]["source_version"] == "sv_" + hashlib.sha256(archived).hexdigest()[:12]
    assert rows[0]["file_size"] == len(archived)
    assert service.manifest_repo.rows[0]["source_version"] == rows[0]["source_version"]
