from __future__ import annotations

import copy
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

from tests import test_stock_analysis_current_rule_factor_manifest as manifest_fixture
from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

CREATED_AT = "2026-02-01T00:00:00Z"


def _load_module() -> Any:
    return load_module(
        "scripts.stock_analysis_current_rule_factor_vendor_dry_run",
        "scripts/stock_analysis_current_rule_factor_vendor_dry_run.py",
    )


class FakeVendorClient:
    def __init__(
        self,
        responses: dict[str, list[dict[str, object]]],
        *,
        error: Exception | None = None,
        drift_path: Path | None = None,
    ) -> None:
        self.responses = responses
        self.error = error
        self.drift_path = drift_path
        self.calls: list[dict[str, object]] = []
        self._drifted = False

    def adj_factor(self, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(dict(kwargs))
        if self.error is not None:
            raise self.error
        if self.drift_path is not None and not self._drifted:
            with self.drift_path.open("ab") as handle:
                handle.write(b"external-drift")
            self._drifted = True
        return copy.deepcopy(self.responses.get(str(kwargs["trade_date"]), []))


def _governed_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Any, Path, Path, dict[str, Any]]:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    manifest_fixture._create_db(db_path, manifest_fixture._rows("000002.SZ"))
    manifest = manifest_fixture._build(monkeypatch, db_path)
    assert manifest["status"] == "gaps_found"
    assert manifest["summary"]["missing_unique_cell_count"] == 5
    valid, errors = (
        module.manifest_task.validate_stock_analysis_current_rule_factor_manifest(
            manifest
        )
    )
    assert valid, errors
    trusted_root = tmp_path / "evidence"
    trusted_root.mkdir()
    manifest_path = trusted_root / "adjustment-factor-manifest-reviewed.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    return module, db_path, trusted_root, manifest


def _responses(manifest: dict[str, Any]) -> dict[str, list[dict[str, object]]]:
    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for index, cell in enumerate(manifest["missing_unique_cells"]):
        compact = str(cell["trade_date"]).replace("-", "")
        grouped[compact].append(
            {
                "ts_code": cell["stock_code"],
                "trade_date": compact,
                "adj_factor": 1.0 + (index / 100.0),
            }
        )
    for compact in list(grouped):
        grouped[compact].append(
            {
                "ts_code": "600519.SH",
                "trade_date": compact,
                "adj_factor": 99.0,
            }
        )
    return dict(grouped)


def _run(
    module: Any,
    *,
    db_path: Path,
    trusted_root: Path,
    client: object,
    output_file: str | Path = "factor-vendor-receipt.json",
    factor_manifest_file: str | Path = "adjustment-factor-manifest-reviewed.json",
    max_vendor_calls: int = 32,
) -> dict[str, Any]:
    return module.run_current_rule_factor_vendor_dry_run(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        factor_manifest_file=factor_manifest_file,
        output_file=output_file,
        created_at=CREATED_AT,
        max_vendor_calls=max_vendor_calls,
        client=client,
    )


def _first_target_record(
    responses: dict[str, list[dict[str, object]]],
) -> tuple[str, dict[str, object]]:
    compact = sorted(responses)[0]
    return compact, responses[compact][0]


def test_success_fetches_sparse_dates_only_ignores_market_rows_and_persists_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, db_path, trusted_root, manifest = _governed_fixture(
        monkeypatch,
        tmp_path,
    )
    responses = _responses(manifest)
    client = FakeVendorClient(responses)
    before = module.manifest_cli._file_sha256(db_path)

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        client=client,
    )

    requested_cells = len(manifest["missing_unique_cells"])
    unique_dates = len(
        {cell["trade_date"] for cell in manifest["missing_unique_cells"]}
    )
    output = trusted_root / "factor-vendor-receipt.json"
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "ready"
    assert result["blockers"] == []
    assert result["database_unchanged"] is True
    assert result["duckdb_sha256_before"] == result["duckdb_sha256_after"] == before
    assert result["vendor_call_count"] == unique_dates
    assert result["summary"] == {
        "requested_cell_count": requested_cells,
        "returned_cell_count": requested_cells,
        "requested_unique_date_count": unique_dates,
        "vendor_call_count": unique_dates,
        "missing_cell_count": 0,
        "extra_cell_count": 0,
        "duplicate_cell_count": 0,
        "invalid_cell_count": 0,
        "wrong_date_cell_count": 0,
    }
    assert receipt["status"] == module.receipt_task.READY_STATUS
    assert receipt["returned_cell_count"] == requested_cells
    assert {cell["stock_code"] for cell in receipt["returned_cells"]} == {"000001.SZ"}
    assert len(client.calls) == unique_dates
    assert all(
        call
        == {
            "trade_date": call["trade_date"],
            "fields": "ts_code,trade_date,adj_factor",
        }
        for call in client.calls
    )
    assert {str(call["trade_date"]) for call in client.calls} == set(responses)
    assert len(client.calls) < requested_cells * unique_dates


@pytest.mark.parametrize(
    "mutation, expected_summary_field",
    [
        ("missing", "missing_cell_count"),
        ("wrong_date", "wrong_date_row_count"),
        ("duplicate", "duplicate_cell_count"),
        ("conflict", "conflict_cell_count"),
        ("invalid", "invalid_factor_row_count"),
    ],
)
def test_vendor_payload_anomalies_block_without_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
    expected_summary_field: str,
) -> None:
    module, db_path, trusted_root, manifest = _governed_fixture(
        monkeypatch,
        tmp_path,
    )
    responses = _responses(manifest)
    compact, record = _first_target_record(responses)
    if mutation == "missing":
        responses[compact].remove(record)
    elif mutation == "wrong_date":
        record["trade_date"] = "20260131"
    elif mutation == "duplicate":
        responses[compact].append(copy.deepcopy(record))
    elif mutation == "conflict":
        conflicting = copy.deepcopy(record)
        conflicting["adj_factor"] = 123.456
        responses[compact].append(conflicting)
    elif mutation == "invalid":
        record["adj_factor"] = 0
    else:  # pragma: no cover - parametrization invariant
        raise AssertionError(mutation)
    monkeypatch.setattr(
        module.receipt_task,
        "build_stock_analysis_current_rule_factor_vendor_receipt",
        lambda **kwargs: pytest.fail("invalid vendor payload must not reach builder"),
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        client=FakeVendorClient(responses),
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["factor_vendor_exact_match_failed"]
    assert result["database_unchanged"] is True
    assert result["summary"][expected_summary_field] > 0
    assert not (trusted_root / "factor-vendor-receipt.json").exists()


def test_vendor_error_is_redacted_and_creates_no_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, db_path, trusted_root, _manifest = _governed_fixture(
        monkeypatch,
        tmp_path,
    )
    secret = "vendor_token=TOP-SECRET"

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        client=FakeVendorClient({}, error=RuntimeError(secret)),
    )

    assert result["status"] == "error"
    assert result["blockers"] == ["factor_vendor_dry_run_failed_RuntimeError"]
    assert secret not in json.dumps(result)
    assert not (trusted_root / "factor-vendor-receipt.json").exists()


def test_invalid_manifest_blocks_before_vendor_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, db_path, trusted_root, manifest = _governed_fixture(
        monkeypatch,
        tmp_path,
    )
    manifest["canonical_manifest_sha256"] = "0" * 64
    (trusted_root / "adjustment-factor-manifest-reviewed.json").write_text(
        json.dumps(manifest, sort_keys=True),
        encoding="utf-8",
    )
    client = FakeVendorClient({})

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        client=client,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["factor_manifest_validation_failed"]
    assert client.calls == []
    assert not (trusted_root / "factor-vendor-receipt.json").exists()


def test_database_drift_during_vendor_fetch_blocks_and_removes_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, db_path, trusted_root, manifest = _governed_fixture(
        monkeypatch,
        tmp_path,
    )
    before = module.manifest_cli._file_sha256(db_path)

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        client=FakeVendorClient(_responses(manifest), drift_path=db_path),
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["duckdb_hash_changed_during_vendor_fetch"]
    assert result["duckdb_sha256_before"] == before
    assert result["duckdb_sha256_after"] != before
    assert result["database_unchanged"] is False
    assert not (trusted_root / "factor-vendor-receipt.json").exists()


def test_database_drift_after_receipt_write_deletes_new_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, db_path, trusted_root, manifest = _governed_fixture(
        monkeypatch,
        tmp_path,
    )
    real_write = module.manifest_cli._write_json_exclusive

    def write_then_drift(**kwargs: object) -> None:
        real_write(**kwargs)
        with db_path.open("ab") as handle:
            handle.write(b"post-persist-drift")

    monkeypatch.setattr(
        module.manifest_cli,
        "_write_json_exclusive",
        write_then_drift,
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        client=FakeVendorClient(_responses(manifest)),
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["duckdb_hash_changed_during_receipt_persistence"]
    assert result["database_unchanged"] is False
    assert result["output_file"] is None
    assert not (trusted_root / "factor-vendor-receipt.json").exists()


def test_vendor_call_budget_blocks_before_client_creation_or_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, db_path, trusted_root, manifest = _governed_fixture(
        monkeypatch,
        tmp_path,
    )
    client = FakeVendorClient(_responses(manifest))

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        client=client,
        max_vendor_calls=1,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["vendor_call_budget_exceeded"]
    assert result["vendor_call_count"] == 0
    assert client.calls == []


def test_output_escape_and_overwrite_are_rejected_before_vendor_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, db_path, trusted_root, manifest = _governed_fixture(
        monkeypatch,
        tmp_path,
    )
    client = FakeVendorClient(_responses(manifest))

    escaped = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        client=client,
        output_file=tmp_path / "escaped.json",
    )
    assert escaped["status"] == "error"
    assert client.calls == []
    assert not (tmp_path / "escaped.json").exists()

    existing = trusted_root / "existing.json"
    existing.write_text("keep-me", encoding="utf-8")
    overwritten = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        client=client,
        output_file="existing.json",
    )
    assert overwritten["status"] == "error"
    assert existing.read_text(encoding="utf-8") == "keep-me"
    assert client.calls == []


def test_symlink_output_component_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, db_path, trusted_root, manifest = _governed_fixture(
        monkeypatch,
        tmp_path,
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = trusted_root / "linked"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    client = FakeVendorClient(_responses(manifest))

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        client=client,
        output_file="linked/receipt.json",
    )

    assert result["status"] == "error"
    assert client.calls == []
    assert not (outside / "receipt.json").exists()


def test_symlink_database_alias_is_rejected_before_hash_or_vendor_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, db_path, trusted_root, manifest = _governed_fixture(
        monkeypatch,
        tmp_path,
    )
    alias = tmp_path / "alias.duckdb"
    try:
        alias.symlink_to(db_path)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    client = FakeVendorClient(_responses(manifest))

    result = _run(
        module,
        db_path=alias,
        trusted_root=trusted_root,
        client=client,
    )

    assert result["status"] == "error"
    assert client.calls == []
    assert not (trusted_root / "factor-vendor-receipt.json").exists()


def test_receipt_validator_failure_blocks_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, db_path, trusted_root, manifest = _governed_fixture(
        monkeypatch,
        tmp_path,
    )
    monkeypatch.setattr(
        module.receipt_task,
        "build_stock_analysis_current_rule_factor_vendor_receipt",
        lambda **kwargs: {
            "status": module.receipt_task.READY_STATUS,
            "canonical_receipt_sha256": "A" * 64,
        },
    )
    monkeypatch.setattr(
        module.receipt_task,
        "validate_stock_analysis_current_rule_factor_vendor_receipt",
        lambda receipt, **kwargs: (False, ("tampered",)),
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        client=FakeVendorClient(_responses(manifest)),
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["factor_vendor_receipt_validation_failed"]
    assert not (trusted_root / "factor-vendor-receipt.json").exists()


def test_main_uses_compact_stdout_and_ready_only_exit_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    args = [
        "--duckdb-path",
        str(tmp_path / "moss.duckdb"),
        "--trusted-evidence-root",
        str(tmp_path),
        "--factor-manifest-file",
        "manifest.json",
        "--output-file",
        "receipt.json",
    ]
    monkeypatch.setattr(
        module,
        "run_current_rule_factor_vendor_dry_run",
        lambda **kwargs: {"status": "ready", "blockers": []},
    )
    assert module.main(args) == module.EXIT_SUCCESS
    printed = capsys.readouterr().out
    assert json.loads(printed)["status"] == "ready"
    assert "\n  " not in printed

    monkeypatch.setattr(
        module,
        "run_current_rule_factor_vendor_dry_run",
        lambda **kwargs: {
            "status": "error",
            "blockers": ["factor_vendor_dry_run_failed_RuntimeError"],
        },
    )
    assert module.main(args) == module.EXIT_BLOCKED
    assert json.loads(capsys.readouterr().out)["status"] == "error"
