"""WP-A2: envelope-level runtime cache for `pnl_v1_data_envelope`.

These tests exercise the runtime cache layer around
`backend.app.services.pnl_service.pnl_v1_data_envelope` without touching real
DuckDB / xlsx sources. The uncached compute path (`_pnl_v1_data_envelope_compute`)
is monkeypatched to a counting stub so we can assert:

- the second call with identical params reuses the cached envelope and does not
  re-enter the compute path;
- the cache key changes when an input xlsx file mtime changes;
- the cache key changes when a governance JSONL stream mtime changes
  (`cache_build_run`, `cache_manifest`, `source_manifest` are all covered);
- the cache key changes when the archived_path referenced by an eligible
  source_manifest row is updated on disk;
- the cache key is isolated by `report_date`.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection,
    duckdb_read_scope,
)
from backend.app.services import pnl_service


@pytest.fixture(autouse=True)
def _restore_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOSS_DATA_INPUT_ROOT", raising=False)


def _envelope(*, report_date: str, marker: str = "ok") -> dict[str, object]:
    return {
        "result_meta": {
            "trace_id": f"tr_pnl_v1_data_{marker}",
            "result_kind": "pnl.v1_data",
            "cache_version": "cv_pnl_test",
            "source_version": "sv_pnl_test",
            "rule_version": "rv_pnl_test",
        },
        "result": {
            "report_date": report_date,
            "marker": marker,
            "rows": [],
        },
    }


def _write_manifest_row(
    manifest_path: Path,
    *,
    source_family: str,
    status: str,
    archived_path: Path,
    report_date: str = "2026-08-31",
) -> None:
    payload = {
        "source_family": source_family,
        "status": status,
        "archived_path": str(archived_path),
        "report_date": report_date,
        "source_file": archived_path.name,
        "source_version": "sv_pnl_test",
        "ingest_batch_id": "ib_pnl_test",
        "created_at": "2026-08-31T00:00:00Z",
    }
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _install_v1_data_scenario(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, Path, Path, dict[str, int]]:
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_text("seed", encoding="utf-8")
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    # Governance JSONL streams must be valid JSONL so the archived_path
    # fingerprint helper (which parses source_manifest) does not blow up.
    for stream_name in ("source_manifest.jsonl", "cache_build_run.jsonl", "cache_manifest.jsonl"):
        (governance_dir / stream_name).write_text("", encoding="utf-8")
    data_root = tmp_path / "data_input"
    (data_root / "pnl_514").mkdir(parents=True)
    (data_root / "pnl_514" / "pnl_514_202608.xlsx").write_bytes(b"stub-xlsx-1")
    (data_root / "pnl").mkdir()
    (data_root / "pnl" / "pnl_20260831.xls").write_bytes(b"stub-xls-1")

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    pnl_service.get_settings.cache_clear()
    monkeypatch.setattr(pnl_service, "_ensure_formal_pnl_storage_available", lambda _path: None)

    counts: dict[str, int] = {"compute": 0}

    def compute_stub(
        *,
        duckdb_path: str,
        governance_dir: str,
        report_date: str,
        data_root: Path,
    ) -> dict[str, object]:
        counts["compute"] += 1
        return _envelope(report_date=report_date, marker=f"call{counts['compute']}")

    monkeypatch.setattr(pnl_service, "_pnl_v1_data_envelope_compute", compute_stub)
    return duckdb_path, governance_dir, data_root, counts


def test_pnl_v1_data_cache_isolated_by_selected_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    duckdb_path, governance_dir, _data_root, counts = _install_v1_data_scenario(monkeypatch, tmp_path)
    first_snapshot = tmp_path / "snapshot-first.duckdb"
    second_snapshot = tmp_path / "snapshot-second.duckdb"
    first_snapshot.write_bytes(b"first")
    second_snapshot.write_bytes(b"other")
    timestamp_ns = first_snapshot.stat().st_mtime_ns
    for snapshot in (first_snapshot, second_snapshot):
        os.utime(snapshot, ns=(timestamp_ns, timestamp_ns))
    assert first_snapshot.stat().st_size == second_snapshot.stat().st_size
    assert first_snapshot.stat().st_mtime_ns == second_snapshot.stat().st_mtime_ns

    pnl_service.clear_pnl_v1_data_runtime_cache()
    results = []
    try:
        for snapshot in (first_snapshot, second_snapshot, first_snapshot):
            selection = DuckDBReadSelection(
                active_path=duckdb_path,
                snapshot_path=snapshot,
                generation=snapshot.stem,
            )
            with duckdb_read_scope(selection, required_online=True):
                results.append(pnl_service.pnl_v1_data_envelope(
                    duckdb_path=str(duckdb_path),
                    governance_dir=str(governance_dir),
                    report_date="2026-08-31",
                ))
        assert counts["compute"] == 2
        assert [result["result"]["marker"] for result in results] == ["call1", "call2", "call1"]
    finally:
        pnl_service.clear_pnl_v1_data_runtime_cache()


def _bump_mtime(path: Path) -> None:
    original = path.stat().st_mtime_ns
    for delta_ns in (1_000_000, 2_000_000, 5_000_000, 10_000_000, 50_000_000):
        target_ns = original + delta_ns
        try:
            os.utime(path, ns=(target_ns, target_ns))
        except (OSError, NotImplementedError):
            time.sleep(0.02)
            path.write_bytes(path.read_bytes() + b"x")
        if path.stat().st_mtime_ns != original:
            return
    raise RuntimeError(f"failed to bump mtime for {path}")


def test_pnl_v1_data_envelope_runtime_cache_skips_recompute_on_second_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pnl_service.clear_pnl_v1_data_runtime_cache()
    duckdb_path, governance_dir, _data_root, counts = _install_v1_data_scenario(
        monkeypatch, tmp_path
    )

    first = pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )
    second = pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )

    assert counts["compute"] == 1
    assert first["result"]["marker"] == "call1"
    assert second["result"]["marker"] == "call1"
    assert second["result_meta"]["trace_id"] != first["result_meta"]["trace_id"]


def test_pnl_v1_data_envelope_runtime_cache_isolated_by_report_date(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pnl_service.clear_pnl_v1_data_runtime_cache()
    duckdb_path, governance_dir, _data_root, counts = _install_v1_data_scenario(
        monkeypatch, tmp_path
    )

    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )
    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-07-31",
    )
    assert counts["compute"] == 2

    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )
    assert counts["compute"] == 2


def test_pnl_v1_data_envelope_runtime_cache_invalidates_on_input_file_mtime_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pnl_service.clear_pnl_v1_data_runtime_cache()
    duckdb_path, governance_dir, data_root, counts = _install_v1_data_scenario(
        monkeypatch, tmp_path
    )

    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )
    assert counts["compute"] == 1

    subfile = data_root / "pnl_514" / "pnl_514_202608.xlsx"
    _bump_mtime(subfile)

    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )

    assert counts["compute"] == 2


@pytest.mark.parametrize(
    "stream_name",
    ["source_manifest.jsonl", "cache_build_run.jsonl", "cache_manifest.jsonl"],
)
def test_pnl_v1_data_envelope_runtime_cache_invalidates_on_governance_stream_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stream_name: str,
) -> None:
    """Editing any of the three JSONL streams the compute path reads must
    bump the cache key (reuses `_jsonl_file_cache_key` under the hood).
    """
    pnl_service.clear_pnl_v1_data_runtime_cache()
    duckdb_path, governance_dir, _data_root, counts = _install_v1_data_scenario(
        monkeypatch, tmp_path
    )

    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )
    assert counts["compute"] == 1

    stream_path = governance_dir / stream_name
    _bump_mtime(stream_path)

    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )

    assert counts["compute"] == 2


def test_pnl_v1_data_envelope_runtime_cache_invalidates_on_manifest_archived_path_mtime_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """If an archived file referenced by an eligible source_manifest row
    changes mtime, the cache key must move even when the file lives outside
    the pnl `data_root` scan patterns.
    """
    pnl_service.clear_pnl_v1_data_runtime_cache()
    duckdb_path, governance_dir, _data_root, counts = _install_v1_data_scenario(
        monkeypatch, tmp_path
    )

    archived_dir = tmp_path / "archive"
    archived_dir.mkdir()
    archived_file = archived_dir / "pnl_514_202608_v1.xlsx"
    archived_file.write_bytes(b"archived-original")
    _write_manifest_row(
        governance_dir / "source_manifest.jsonl",
        source_family="pnl_514",
        status="completed",
        archived_path=archived_file,
    )

    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )
    assert counts["compute"] == 1

    # Second call with archived file untouched: cache hit.
    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )
    assert counts["compute"] == 1

    _bump_mtime(archived_file)

    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )

    assert counts["compute"] == 2


def test_pnl_v1_data_envelope_runtime_cache_bypassed_when_manifest_archived_path_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A manifest row that points to a non-existent archived_path must
    return a None cache key so the envelope falls back to the uncached
    compute path instead of serving stale bytes.
    """
    pnl_service.clear_pnl_v1_data_runtime_cache()
    duckdb_path, governance_dir, _data_root, counts = _install_v1_data_scenario(
        monkeypatch, tmp_path
    )

    _write_manifest_row(
        governance_dir / "source_manifest.jsonl",
        source_family="pnl_514",
        status="completed",
        archived_path=tmp_path / "archive" / "does_not_exist.xlsx",
    )

    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )
    pnl_service.pnl_v1_data_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )

    # Two calls, both uncached because the key builder returned None.
    assert counts["compute"] == 2
