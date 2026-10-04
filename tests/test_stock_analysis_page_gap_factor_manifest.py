from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from backend.app.tasks import stock_analysis_page_gap_factor_manifest as module
from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

CREATED_AT = "2026-08-24T12:00:00Z"


def _cells(*, count: int, unique_date_count: int) -> list[dict[str, Any]]:
    dates = [
        (date(2026, 1, 1) + timedelta(days=index)).isoformat()
        for index in range(unique_date_count)
    ]
    cells: list[dict[str, Any]] = []
    stock_index = 1
    while len(cells) < count:
        stock_code = f"{stock_index:06d}.SH"
        for trade_date in dates:
            if len(cells) == count:
                break
            cells.append(
                {
                    "stock_code": stock_code,
                    "trade_date": trade_date,
                    "status": module.EXPECTED_FACTOR_CELL_STATUS,
                    "cell_statuses": [module.EXPECTED_FACTOR_CELL_STATUS],
                }
            )
        stock_index += 1
    return cells


def _write_page_manifest(
    *,
    page_path: Path,
    db_path: Path,
    count: int,
    unique_date_count: int,
    status: str = "gaps_found",
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    database_sha = module._file_sha256(db_path)
    cells = _cells(count=count, unique_date_count=unique_date_count)
    payload = {
        "manifest_kind": module.EXPECTED_PAGE_MANIFEST_KIND,
        "status": status,
        "page_id": module.EXPECTED_PAGE_ID,
        "page_route": module.EXPECTED_PAGE_ROUTE,
        "page_metric_key": module.EXPECTED_PAGE_METRIC_KEY,
        "canonical_manifest_sha256": "A" * 64,
        "database": {
            "path": str(db_path.resolve()),
            "sha256_before": database_sha,
            "sha256_after": database_sha,
            "unchanged": True,
            "read_only": True,
        },
        "summary": {
            "page_gap_view_count_before": count + 10,
            "mapped_gap_view_count": count + 10,
            "unique_missing_factor_cell_count": count,
            "factor_quality": {
                "missing_required_cell_count": count,
                "invalid_required_cell_count": 0,
                "ambiguous_required_cell_count": 0,
            },
        },
        "missing_factor_cells": cells,
        "blockers": blockers or [],
    }
    page_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _inputs(
    tmp_path: Path, *, count: int = 3_405, unique_date_count: int = 87
) -> tuple[Path, Path, dict[str, Any]]:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"read-only-fixture")
    page_path = tmp_path / "page-gap.json"
    payload = _write_page_manifest(
        page_path=page_path,
        db_path=db_path,
        count=count,
        unique_date_count=unique_date_count,
    )
    return page_path, db_path, payload


def _allow_formal_page_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        module.page_manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda payload: (True, ()),
    )


def _build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    count: int = 3_405,
    unique_date_count: int = 87,
) -> tuple[dict[str, Any], Path, Path]:
    _allow_formal_page_validation(monkeypatch)
    page_path, db_path, _ = _inputs(
        tmp_path, count=count, unique_date_count=unique_date_count
    )
    manifest = module.build_stock_analysis_page_gap_factor_manifest(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        created_at=CREATED_AT,
    )
    return manifest, page_path, db_path


def _rehash(manifest: dict[str, Any]) -> None:
    manifest["canonical_manifest_sha256"] = module._canonical_manifest_sha256(manifest)


def _load_cli_module():
    return load_module(
        "scripts.stock_analysis_page_gap_factor_manifest",
        "scripts/stock_analysis_page_gap_factor_manifest.py",
    )


def test_builds_exact_3405_cell_87_date_contract_from_formal_page_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest, page_path, db_path = _build(monkeypatch, tmp_path)

    assert manifest["manifest_kind"] == module.MANIFEST_KIND
    assert manifest["status"] == "gaps_found"
    assert manifest["blockers"] == []
    assert manifest["target_cell_count"] == 3_405
    assert len(manifest["target_cells"]) == 3_405
    assert manifest["requested_unique_date_count"] == 87
    assert manifest["target_cells"] == sorted(
        manifest["target_cells"],
        key=lambda cell: (cell["trade_date"], cell["stock_code"]),
    )
    assert all(
        set(cell) == {"stock_code", "trade_date"} for cell in manifest["target_cells"]
    )
    assert manifest["target_cells_sha256"] == module._canonical_value_sha256(
        manifest["target_cells"]
    )
    assert manifest["page_manifest_binding"] == {
        "path": str(page_path.resolve()),
        "file_sha256": module._file_sha256(page_path),
        "canonical_manifest_sha256": "A" * 64,
        "manifest_kind": module.EXPECTED_PAGE_MANIFEST_KIND,
        "page_id": module.EXPECTED_PAGE_ID,
        "page_route": module.EXPECTED_PAGE_ROUTE,
        "page_metric_key": module.EXPECTED_PAGE_METRIC_KEY,
        "database_path": str(db_path.resolve()),
        "database_sha256": module._file_sha256(db_path),
        "page_gap_view_count": 3_415,
        "missing_factor_cell_count": 3_405,
    }
    assert manifest["database"] == {
        "path": str(db_path.resolve()),
        "sha256_before": module._file_sha256(db_path),
        "sha256_after": module._file_sha256(db_path),
        "unchanged": True,
        "read_only": True,
    }
    for field_name, expected in (
        ("remediation_only", True),
        ("strict_exact_date_lookup", True),
        ("carry_forward_allowed", False),
        ("fallback_allowed", False),
        ("write_allowed", False),
        ("historical_availability_proven", False),
        ("certification_allowed", False),
        ("downstream_materialization_allowed", False),
    ):
        assert manifest[field_name] is expected
    valid, errors = module.validate_stock_analysis_page_gap_factor_manifest(manifest)
    assert valid, errors


def test_counts_are_derived_from_validated_page_manifest_not_hardcoded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest, _, _ = _build(monkeypatch, tmp_path, count=5, unique_date_count=3)

    assert manifest["status"] == "gaps_found"
    assert manifest["target_cell_count"] == 5
    assert manifest["requested_unique_date_count"] == 3
    assert manifest["page_manifest_binding"]["missing_factor_cell_count"] == 5
    valid, errors = module.validate_stock_analysis_page_gap_factor_manifest(manifest)
    assert valid, errors


@pytest.mark.parametrize(
    "mutation,expected_blocker",
    [
        (
            lambda payload: payload.update(status="ready"),
            "page_manifest_status_mismatch",
        ),
        (
            lambda payload: payload.update(blockers=["source_not_clean"]),
            "page_manifest_has_blockers",
        ),
        (
            lambda payload: payload["summary"].update(
                unique_missing_factor_cell_count=3_404
            ),
            "page_manifest_missing_factor_cells_length_mismatch",
        ),
        (
            lambda payload: payload["missing_factor_cells"][0].update(
                status="invalid_exact_cell"
            ),
            "page_manifest_missing_factor_cell_status_mismatch",
        ),
    ],
)
def test_builder_fails_closed_on_page_status_blockers_count_and_cell_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation,
    expected_blocker: str,
) -> None:
    _allow_formal_page_validation(monkeypatch)
    page_path, db_path, payload = _inputs(tmp_path)
    mutation(payload)
    page_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest = module.build_stock_analysis_page_gap_factor_manifest(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        created_at=CREATED_AT,
    )

    assert manifest["status"] == "blocked"
    assert expected_blocker in manifest["blockers"]
    assert manifest["target_cells"] == []
    assert manifest["target_cell_count"] == 0
    assert manifest["downstream_materialization_allowed"] is False


def test_builder_fails_closed_when_formal_page_validator_rejects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    page_path, db_path, _ = _inputs(tmp_path, count=5, unique_date_count=3)
    monkeypatch.setattr(
        module.page_manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda payload: (False, ("tampered",)),
    )

    manifest = module.build_stock_analysis_page_gap_factor_manifest(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        created_at=CREATED_AT,
    )

    assert manifest["status"] == "blocked"
    assert "page_manifest_formal_validation_failed" in manifest["blockers"]
    assert "page_manifest_validation_error_count:1" in manifest["blockers"]
    assert manifest["target_cells"] == []
    valid, errors = module.validate_stock_analysis_page_gap_factor_manifest(manifest)
    assert valid, errors


@pytest.mark.parametrize("malformed_text", ["{", "[]", "{}"])
def test_malformed_source_returns_self_validating_blocked_manifest(
    tmp_path: Path,
    malformed_text: str,
) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"read-only-fixture")
    page_path = tmp_path / "page-gap.json"
    page_path.write_text(malformed_text, encoding="utf-8")

    manifest = module.build_stock_analysis_page_gap_factor_manifest(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        created_at=CREATED_AT,
    )

    assert manifest["status"] == "blocked"
    assert manifest["target_cells"] == []
    assert manifest["target_cell_count"] == 0
    valid, errors = module.validate_stock_analysis_page_gap_factor_manifest(manifest)
    assert valid, errors


def test_builder_fails_closed_on_database_binding_drift_without_mutating_db(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _allow_formal_page_validation(monkeypatch)
    page_path, db_path, _ = _inputs(tmp_path, count=5, unique_date_count=3)
    db_path.write_bytes(b"changed-after-page-manifest")
    before = db_path.read_bytes()

    manifest = module.build_stock_analysis_page_gap_factor_manifest(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        created_at=CREATED_AT,
    )

    assert manifest["status"] == "blocked"
    assert "page_manifest_database_sha256_drift" in manifest["blockers"]
    assert manifest["write_allowed"] is False
    assert db_path.read_bytes() == before


@pytest.mark.parametrize("drift_source", ["page", "database"])
def test_builder_hash_drift_returns_self_validating_blocked_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    drift_source: str,
) -> None:
    _allow_formal_page_validation(monkeypatch)
    page_path, db_path, _ = _inputs(tmp_path, count=5, unique_date_count=3)
    real_hash = module._file_sha256
    reads = {"page": 0, "database": 0}

    def _hash(path: Path) -> str:
        key = "page" if path == page_path.resolve() else "database"
        reads[key] += 1
        if key == drift_source and reads[key] >= 2:
            return "F" * 64
        return real_hash(path)

    monkeypatch.setattr(module, "_file_sha256", _hash)

    manifest = module.build_stock_analysis_page_gap_factor_manifest(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        created_at=CREATED_AT,
    )

    assert manifest["status"] == "blocked"
    assert manifest["target_cells"] == []
    assert any("changed_during" in blocker for blocker in manifest["blockers"])
    valid, errors = module.validate_stock_analysis_page_gap_factor_manifest(manifest)
    assert valid, errors


@pytest.mark.parametrize(
    "tamper,expected_error",
    [
        (
            lambda payload: payload.update(write_allowed=True),
            "manifest.write_allowed must be false",
        ),
        (
            lambda payload: payload["target_cells"].reverse(),
            "manifest.target_cells must be canonically sorted",
        ),
        (
            lambda payload: payload.update(target_cell_count=4),
            "manifest.target_cell_count mismatch",
        ),
        (
            lambda payload: payload["page_manifest_binding"].update(
                missing_factor_cell_count=4
            ),
            "manifest.target_cell_count does not match page binding",
        ),
    ],
)
def test_validator_rejects_boundary_target_and_binding_tamper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tamper,
    expected_error: str,
) -> None:
    manifest, _, _ = _build(monkeypatch, tmp_path, count=5, unique_date_count=3)
    tampered = copy.deepcopy(manifest)
    tamper(tampered)
    _rehash(tampered)

    valid, errors = module.validate_stock_analysis_page_gap_factor_manifest(tampered)

    assert valid is False
    assert expected_error in errors


def test_validator_rejects_self_hash_tamper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest, _, _ = _build(monkeypatch, tmp_path, count=5, unique_date_count=3)
    manifest["canonical_manifest_sha256"] = "F" * 64

    valid, errors = module.validate_stock_analysis_page_gap_factor_manifest(manifest)

    assert valid is False
    assert "manifest.canonical_manifest_sha256 mismatch" in errors


def test_cli_exclusively_persists_valid_manifest_and_compact_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_cli_module()
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    _allow_formal_page_validation(monkeypatch)
    page_path, db_path, _ = _inputs(trusted_root, count=5, unique_date_count=3)

    result = cli.run_stock_analysis_page_gap_factor_manifest_cli(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="factor-targets.json",
        created_at=CREATED_AT,
    )

    output = trusted_root / "factor-targets.json"
    assert result["status"] == "gaps_found"
    assert result["blockers"] == []
    assert result["target_cell_count"] == 5
    assert result["requested_unique_date_count"] == 3
    assert result["sources_unchanged"] is True
    assert "target_cells" not in result
    persisted = json.loads(output.read_text(encoding="utf-8"))
    valid, errors = module.validate_stock_analysis_page_gap_factor_manifest(persisted)
    assert valid, errors


def test_cli_rejects_page_manifest_outside_trusted_root_before_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_cli_module()
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    page_path, db_path, _ = _inputs(tmp_path, count=5, unique_date_count=3)
    monkeypatch.setattr(
        cli.manifest_task,
        "build_stock_analysis_page_gap_factor_manifest",
        lambda **kwargs: pytest.fail("builder must not run for an untrusted source"),
    )

    result = cli.run_stock_analysis_page_gap_factor_manifest_cli(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="factor-targets.json",
        created_at=CREATED_AT,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["page_manifest_path_outside_trusted_root"]
    assert not (trusted_root / "factor-targets.json").exists()


def test_cli_refuses_overwrite_before_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_cli_module()
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    page_path, db_path, _ = _inputs(trusted_root, count=5, unique_date_count=3)
    output = trusted_root / "factor-targets.json"
    output.write_text("owner-data", encoding="utf-8")
    monkeypatch.setattr(
        cli.manifest_task,
        "build_stock_analysis_page_gap_factor_manifest",
        lambda **kwargs: pytest.fail("builder must not run before overwrite guard"),
    )

    result = cli.run_stock_analysis_page_gap_factor_manifest_cli(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file=output,
        created_at=CREATED_AT,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["output_file_must_be_new"]
    assert output.read_text(encoding="utf-8") == "owner-data"


def test_cli_rejects_output_escape_before_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_cli_module()
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    page_path, db_path, _ = _inputs(trusted_root, count=5, unique_date_count=3)
    monkeypatch.setattr(
        cli.manifest_task,
        "build_stock_analysis_page_gap_factor_manifest",
        lambda **kwargs: pytest.fail("builder must not run for escaped output"),
    )

    result = cli.run_stock_analysis_page_gap_factor_manifest_cli(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file=tmp_path / "outside.json",
        created_at=CREATED_AT,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["output_file_outside_trusted_root"]
    assert not (tmp_path / "outside.json").exists()


def test_cli_rejects_symlink_component_before_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_cli_module()
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    page_path, db_path, _ = _inputs(trusted_root, count=5, unique_date_count=3)
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = trusted_root / "linked"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")
    monkeypatch.setattr(
        cli.manifest_task,
        "build_stock_analysis_page_gap_factor_manifest",
        lambda **kwargs: pytest.fail("builder must not run through a symlink"),
    )

    result = cli.run_stock_analysis_page_gap_factor_manifest_cli(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file=linked / "factor-targets.json",
        created_at=CREATED_AT,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["output_file_contains_symlink_or_junction_component"]
    assert not (outside / "factor-targets.json").exists()


def test_cli_does_not_persist_blocked_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_cli_module()
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    _allow_formal_page_validation(monkeypatch)
    page_path, db_path, payload = _inputs(trusted_root, count=5, unique_date_count=3)
    payload["status"] = "ready"
    page_path.write_text(json.dumps(payload), encoding="utf-8")

    result = cli.run_stock_analysis_page_gap_factor_manifest_cli(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="factor-targets.json",
        created_at=CREATED_AT,
    )

    assert result["status"] == "blocked"
    assert "page_manifest_status_mismatch" in result["blockers"]
    assert not (trusted_root / "factor-targets.json").exists()


def test_cli_removes_new_output_when_database_drifts_after_persistence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_cli_module()
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    _allow_formal_page_validation(monkeypatch)
    page_path, db_path, _ = _inputs(trusted_root, count=5, unique_date_count=3)
    real_hash = cli._file_sha256
    database_reads = 0

    def _hash(path: Path) -> str:
        nonlocal database_reads
        if path == db_path.resolve():
            database_reads += 1
            if database_reads == 3:
                return "F" * 64
        return real_hash(path)

    monkeypatch.setattr(cli, "_file_sha256", _hash)

    result = cli.run_stock_analysis_page_gap_factor_manifest_cli(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="factor-targets.json",
        created_at=CREATED_AT,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["duckdb_hash_changed_during_persistence"]
    assert not (trusted_root / "factor-targets.json").exists()


def test_cli_does_not_delete_replacement_swapped_after_exclusive_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_cli_module()
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    _allow_formal_page_validation(monkeypatch)
    page_path, db_path, _ = _inputs(trusted_root, count=5, unique_date_count=3)
    replacement_text = "replacement-owned-by-another-process"

    def _swap_then_fail(path: Path) -> dict[str, Any]:
        path.unlink()
        path.write_text(replacement_text, encoding="utf-8")
        raise RuntimeError("simulated readback race")

    monkeypatch.setattr(cli, "_load_json_object", _swap_then_fail)

    result = cli.run_stock_analysis_page_gap_factor_manifest_cli(
        page_manifest_path=page_path,
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="factor-targets.json",
        created_at=CREATED_AT,
    )

    replacement = trusted_root / "factor-targets.json"
    assert result["status"] == "error"
    assert replacement.read_text(encoding="utf-8") == replacement_text


def test_cli_help_has_no_write_apply_or_execute_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli_module()

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--page-manifest-path" in help_text
    assert "--apply" not in help_text
    assert "--execute" not in help_text
    assert "--write" not in help_text
