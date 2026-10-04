from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import duckdb
import pytest

from backend.app.tasks import livermore_candidate_history_materialize as legacy_module
from backend.app.tasks import stock_analysis_page_gap_manifest as module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

CREATED_AT = "2026-08-24T12:00:00Z"
EVALUATION = "2026-08-24"
HORIZONS = ("1d", "5d", "10d", "20d")


def _create_db(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              stock_name varchar,
              signal_kind varchar,
              candidate_rank integer,
              market_state varchar,
              signal_close double,
              entry_date varchar,
              entry_price double,
              entry_executable boolean,
              exit_date_1d varchar,
              exit_price_1d double,
              return_1d_net double,
              return_1d_net_adj double,
              exit_date_5d varchar,
              exit_price_5d double,
              return_5d_net double,
              return_5d_net_adj double,
              exit_date_10d varchar,
              exit_price_10d double,
              return_10d_net double,
              return_10d_net_adj double,
              exit_date_20d varchar,
              exit_price_20d double,
              return_20d_net double,
              return_20d_net_adj double,
              data_status varchar,
              formula_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()


def _execution_row(
    *,
    signal_date: str,
    stock_code: str,
    signal_kind: str,
    entry_date: str,
    entry_price: float = 10.0,
    gaps: dict[str, tuple[str, float, float, float | None]],
    data_status: str = "complete",
    formula_version: str = module.LEGACY_EXECUTION_FORMULA_VERSION,
    run_id: str = "run-execution",
) -> tuple[object, ...]:
    values: list[object] = [
        signal_date,
        stock_code,
        f"name-{stock_code}",
        signal_kind,
        1,
        "bull",
        entry_price,
        entry_date,
        entry_price,
        True,
    ]
    for horizon in HORIZONS:
        horizon_values = gaps.get(horizon)
        if horizon_values is None:
            values.extend([None, None, None, None])
        else:
            values.extend(horizon_values)
    values.extend([data_status, formula_version, run_id])
    return tuple(values)


def _insert_execution_rows(path: Path, rows: list[tuple[object, ...]]) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.executemany(
            """
            insert into livermore_candidate_execution_history values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
             ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
             ?, ?, ?)
            """,
            rows,
        )
    finally:
        conn.close()


def _insert_factor_rows(path: Path, rows: list[tuple[object, ...]]) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        conn.close()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _seed_happy_db(path: Path) -> None:
    _create_db(path)
    _insert_execution_rows(
        path,
        [
            _execution_row(
                signal_date="2026-01-02",
                stock_code="600000.SH",
                signal_kind="stock_candidate",
                entry_date="2026-01-05",
                gaps={
                    "1d": ("2026-01-06", 10.2, 0.01, None),
                    "5d": ("2026-01-10", 10.5, 0.04, None),
                },
            ),
            _execution_row(
                signal_date="2026-01-03",
                stock_code="000001.SZ",
                signal_kind="theme_breakout",
                entry_date="2026-01-07",
                gaps={
                    "10d": ("2026-01-21", 20.8, 0.03, None),
                    "20d": ("2026-02-04", 21.2, 0.06, None),
                },
            ),
            _execution_row(
                signal_date="2026-01-20",
                stock_code="600000.SH",
                signal_kind="stock_candidate",
                entry_date="2026-01-10",
                gaps={
                    "20d": ("2026-02-20", 11.0, 0.08, None),
                },
            ),
        ],
    )
    _insert_factor_rows(
        path,
        [
            ("600000.SH", "2026-01-05", 1.0, "fixture", "factor-1"),
            ("000001.SZ", "2026-01-21", 1.1, "fixture", "factor-2"),
            ("000001.SZ", "2026-02-04", 1.2, "fixture", "factor-3"),
        ],
    )


def _build_happy(path: Path) -> dict[str, Any]:
    _seed_happy_db(path)
    return module.build_stock_analysis_page_gap_manifest(
        duckdb_path=path,
        evaluation_as_of_date=EVALUATION,
        created_at=CREATED_AT,
    )


def _rehash(manifest: dict[str, Any]) -> None:
    manifest["canonical_manifest_sha256"] = module._canonical_sha256(manifest)


def test_manifest_ties_out_all_horizons_signal_kinds_cells_and_selector(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "page-gap.duckdb"

    def _forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError(
            "manifest builder must not call repair or effective-target code"
        )

    monkeypatch.setattr(
        legacy_module, "repair_livermore_candidate_execution_gaps", _forbidden
    )
    monkeypatch.setattr(
        legacy_module, "_livermore_candidate_execution_gap_targets", _forbidden
    )
    _seed_happy_db(db_path)
    before = _file_sha(db_path)

    manifest = module.build_stock_analysis_page_gap_manifest(
        duckdb_path=db_path,
        evaluation_as_of_date=EVALUATION,
        created_at=CREATED_AT,
    )

    assert manifest["status"] == "gaps_found"
    assert manifest["page_route"] == "/stock-analysis"
    assert (
        manifest["source_contract"]["integrity_semantics"]
        == "self_consistency_only_no_external_authenticity"
    )
    assert manifest["approval_boundary"]["write_allowed"] is False
    assert manifest["database"]["sha256_before"] == before
    assert manifest["database"]["sha256_after"] == before
    assert manifest["summary"]["page_gap_view_count_before"] == 5
    assert manifest["summary"]["mapped_gap_view_count"] == 5
    assert manifest["summary"]["factor_write_only_projected_gap_view_count"] == 5
    assert manifest["summary"]["factor_write_only_reduction"] == 0
    assert (
        manifest["summary"]["conditional_full_materialization_projected_gap_view_count"]
        == 0
    )
    assert manifest["summary"]["conditional_full_materialization_reduction"] == 5
    assert manifest["summary"]["unique_execution_key_count"] == 3
    assert manifest["summary"]["required_factor_requirement_count"] == 10
    assert manifest["summary"]["unique_required_factor_cell_count"] == 7
    assert manifest["summary"]["present_required_factor_cell_count"] == 3
    assert manifest["summary"]["unique_missing_factor_cell_count"] == 4
    assert manifest["summary"]["missing_factor_requirement_use_count"] == 6
    assert manifest["summary"]["current_recomputable_gap_view_count"] == 0
    assert manifest["summary"]["horizon_counts"] == [
        {"value": "20d", "count": 2},
        {"value": "10d", "count": 1},
        {"value": "1d", "count": 1},
        {"value": "5d", "count": 1},
    ]
    assert manifest["summary"]["signal_kind_counts"] == [
        {"value": "stock_candidate", "count": 3},
        {"value": "theme_breakout", "count": 2},
    ]
    assert manifest["summary"]["missing_factor_role_scope_counts"] == [
        {"value": "exit_only", "count": 2},
        {"value": "both", "count": 1},
        {"value": "entry_only", "count": 1},
    ]
    assert manifest["summary"]["classification_counts_by_horizon"] == {
        "1d": {
            "factors_present_history_unmaterialized": 0,
            "missing_both": 0,
            "missing_entry_only": 0,
            "missing_exit_only": 1,
        },
        "5d": {
            "factors_present_history_unmaterialized": 0,
            "missing_both": 0,
            "missing_entry_only": 0,
            "missing_exit_only": 1,
        },
        "10d": {
            "factors_present_history_unmaterialized": 0,
            "missing_both": 0,
            "missing_entry_only": 1,
            "missing_exit_only": 0,
        },
        "20d": {
            "factors_present_history_unmaterialized": 0,
            "missing_both": 1,
            "missing_entry_only": 1,
            "missing_exit_only": 0,
        },
    }
    assert manifest["legacy_repair_coverage"] == {
        "coverage_kind": "selector_candidate",
        "selector_signal_kind": "stock_candidate",
        "selector_scope_only": True,
        "effective_repair_preview_executed": False,
        "selector_candidate_logical_key_count": 1,
        "covered_gap_view_count": 1,
        "covered_horizon_counts": [{"value": "20d", "count": 1}],
    }
    shared_cell = next(
        cell
        for cell in manifest["missing_factor_cells"]
        if cell["stock_code"] == "600000.SH" and cell["trade_date"] == "2026-01-10"
    )
    assert shared_cell["role_scope"] == "both"
    assert shared_cell["role_use_counts"] == {"entry": 1, "exit": 1}
    assert shared_cell["dependent_gap_count"] == 2
    valid, errors = module.validate_stock_analysis_page_gap_manifest(manifest)
    assert valid, errors
    repeated = module.build_stock_analysis_page_gap_manifest(
        duckdb_path=db_path,
        evaluation_as_of_date=EVALUATION,
        created_at=CREATED_AT,
    )
    assert [view["source_row_sha256"] for view in repeated["gap_views"]] == [
        view["source_row_sha256"] for view in manifest["gap_views"]
    ]


@pytest.mark.parametrize(
    ("field_name", "tampered_value"),
    [
        ("run_id", "tampered-run"),
        ("formula_version", "tampered-formula"),
        ("stock_name", "tampered-name"),
        ("signal_close", 99.0),
    ],
)
def test_validator_recomputes_source_row_sha_after_trace_tamper(
    tmp_path: Path,
    field_name: str,
    tampered_value: object,
) -> None:
    manifest = _build_happy(tmp_path / f"source-row-{field_name}.duckdb")
    tampered = copy.deepcopy(manifest)
    tampered["gap_views"][0][field_name] = tampered_value
    _rehash(tampered)

    valid, errors = module.validate_stock_analysis_page_gap_manifest(tampered)

    assert valid is False
    assert "manifest.gap_views[0].source_row_sha256 mismatch" in errors


@pytest.mark.parametrize(
    ("field_name", "tampered_value", "expected_error"),
    [
        ("stock_name", " ", "must be a non-empty canonical string"),
        ("candidate_rank", "1", "must be an integer"),
        ("signal_close", "10.0", "must be positive finite"),
        ("run_id", "", "must be a non-empty canonical string"),
    ],
)
def test_validator_enforces_trace_field_type_and_nonempty_boundaries(
    tmp_path: Path,
    field_name: str,
    tampered_value: object,
    expected_error: str,
) -> None:
    manifest = _build_happy(tmp_path / f"trace-boundary-{field_name}.duckdb")
    tampered = copy.deepcopy(manifest)
    tampered["gap_views"][0][field_name] = tampered_value
    tampered["gap_views"][0]["source_row_sha256"] = module._source_row_sha256(
        tampered["gap_views"][0]
    )
    _rehash(tampered)

    valid, errors = module.validate_stock_analysis_page_gap_manifest(tampered)

    assert valid is False
    assert any(expected_error in error for error in errors)


def test_factor_cells_are_loaded_in_one_values_batch_for_small_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "factor-batch.duckdb"
    _seed_happy_db(db_path)
    real_connect = duckdb.connect
    factor_query_count = 0
    observed_sql: list[str] = []

    class _ConnectionProxy:
        def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
            self._connection = connection

        def execute(
            self,
            query: str,
            parameters: object = None,
        ) -> duckdb.DuckDBPyConnection:
            nonlocal factor_query_count
            observed_sql.append(query)
            if f"join {module.FACTOR_TABLE} as factor" in query.lower():
                factor_query_count += 1
            if parameters is None:
                return self._connection.execute(query)
            return self._connection.execute(query, parameters)

        def close(self) -> None:
            self._connection.close()

    def _connect(*args: object, **kwargs: object) -> _ConnectionProxy:
        return _ConnectionProxy(real_connect(*args, **kwargs))

    monkeypatch.setattr(module.duckdb, "connect", _connect)

    manifest = module.build_stock_analysis_page_gap_manifest(
        duckdb_path=db_path,
        evaluation_as_of_date=EVALUATION,
        created_at=CREATED_AT,
    )

    assert manifest["summary"]["unique_required_factor_cell_count"] == 7
    assert factor_query_count == 1
    assert all("create temp" not in query.lower() for query in observed_sql)
    valid, errors = module.validate_stock_analysis_page_gap_manifest(manifest)
    assert valid, errors


def test_duplicate_physical_gap_rows_are_retained_and_blocked(tmp_path: Path) -> None:
    db_path = tmp_path / "duplicate-gap.duckdb"
    _create_db(db_path)
    row = _execution_row(
        signal_date="2026-01-02",
        stock_code="600000.SH",
        signal_kind="theme_breakout",
        entry_date="2026-01-05",
        gaps={"1d": ("2026-01-06", 10.2, 0.01, None)},
    )
    _insert_execution_rows(db_path, [row, row])
    _insert_factor_rows(
        db_path,
        [
            ("600000.SH", "2026-01-05", 1.0, "fixture", "factor-entry"),
            ("600000.SH", "2026-01-06", 1.0, "fixture", "factor-exit"),
        ],
    )

    manifest = module.build_stock_analysis_page_gap_manifest(
        duckdb_path=db_path,
        evaluation_as_of_date=EVALUATION,
        created_at=CREATED_AT,
    )

    assert manifest["status"] == "blocked"
    assert manifest["summary"]["page_gap_view_count_before"] == 2
    assert manifest["summary"]["mapped_gap_view_count"] == 2
    assert len(manifest["gap_views"]) == 2
    assert {view["occurrence_ordinal"] for view in manifest["gap_views"]} == {1, 2}
    assert len({view["gap_view_id"] for view in manifest["gap_views"]}) == 2
    assert any(
        blocker.startswith("duplicate_gap_view_key:")
        for blocker in manifest["blockers"]
    )
    assert (
        manifest["summary"]["conditional_full_materialization_projected_gap_view_count"]
        == 2
    )
    valid, errors = module.validate_stock_analysis_page_gap_manifest(manifest)
    assert valid, errors


@pytest.mark.parametrize(
    ("factor_rows", "expected_status", "expected_blocker"),
    [
        (
            [("600000.SH", "2026-01-05", 0.0, "fixture", "factor-invalid")],
            module.FACTOR_INVALID_STATUS,
            "invalid_required_factor_cells:1",
        ),
        (
            [("600000.sh", "2026-01-05", 1.0, "fixture", "factor-bad-code")],
            module.FACTOR_INVALID_STATUS,
            "invalid_required_factor_cells:1",
        ),
        (
            [
                (
                    "600000.SH",
                    "2026-01-05T00:00:00",
                    1.0,
                    "fixture",
                    "factor-bad-date",
                )
            ],
            module.FACTOR_INVALID_STATUS,
            "invalid_required_factor_cells:1",
        ),
        (
            [
                ("600000.SH", "2026-01-05", 1.0, "fixture", "factor-a"),
                ("600000.SH", "2026-01-05", 1.0, "fixture", "factor-b"),
            ],
            module.FACTOR_AMBIGUOUS_STATUS,
            "ambiguous_required_factor_cells:1",
        ),
    ],
)
def test_invalid_or_ambiguous_required_factor_blocks(
    tmp_path: Path,
    factor_rows: list[tuple[object, ...]],
    expected_status: str,
    expected_blocker: str,
) -> None:
    db_path = tmp_path / f"{expected_status}.duckdb"
    _create_db(db_path)
    _insert_execution_rows(
        db_path,
        [
            _execution_row(
                signal_date="2026-01-02",
                stock_code="600000.SH",
                signal_kind="theme_breakout",
                entry_date="2026-01-05",
                gaps={"1d": ("2026-01-06", 10.2, 0.01, None)},
            )
        ],
    )
    _insert_factor_rows(db_path, factor_rows)

    manifest = module.build_stock_analysis_page_gap_manifest(
        duckdb_path=db_path,
        evaluation_as_of_date=EVALUATION,
        created_at=CREATED_AT,
    )

    assert manifest["status"] == "blocked"
    assert manifest["gap_views"][0]["entry_factor"]["status"] == expected_status
    assert expected_blocker in manifest["blockers"]
    valid, errors = module.validate_stock_analysis_page_gap_manifest(manifest)
    assert valid, errors


@pytest.mark.parametrize(
    ("stock_code", "entry_date"),
    [
        ("NOT-A-STOCK", "2026-01-05"),
        ("600000.sh", "2026-01-05"),
        (" 600000.SH ", "2026-01-05"),
        ("600000.SH", "2026-01-05T00:00:00"),
        ("600000.SH", " 2026-01-05 "),
    ],
)
def test_noncanonical_key_or_date_preserves_physical_count_and_blocks(
    tmp_path: Path,
    stock_code: str,
    entry_date: str,
) -> None:
    db_path = tmp_path / "bad-key.duckdb"
    _create_db(db_path)
    _insert_execution_rows(
        db_path,
        [
            _execution_row(
                signal_date="2026-01-02",
                stock_code=stock_code,
                signal_kind="theme_breakout",
                entry_date=entry_date,
                gaps={"1d": ("2026-01-06", 10.2, 0.01, None)},
            )
        ],
    )

    manifest = module.build_stock_analysis_page_gap_manifest(
        duckdb_path=db_path,
        evaluation_as_of_date=EVALUATION,
        created_at=CREATED_AT,
    )

    assert manifest["status"] == "blocked"
    assert manifest["summary"]["page_gap_view_count_before"] == 1
    assert manifest["summary"]["mapped_gap_view_count"] == 0
    assert manifest["gap_views"] == []
    assert "gap_view_contains_noncanonical_key_or_date" in manifest["blockers"]
    assert (
        "page_gap_physical_mapping_mismatch:physical=1:mapped=0" in manifest["blockers"]
    )
    valid, errors = module.validate_stock_analysis_page_gap_manifest(manifest)
    assert valid, errors


def test_missing_schema_returns_valid_blocked_manifest(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.duckdb"
    duckdb.connect(str(db_path)).close()

    manifest = module.build_stock_analysis_page_gap_manifest(
        duckdb_path=db_path,
        evaluation_as_of_date=EVALUATION,
        created_at=CREATED_AT,
    )

    assert manifest["status"] == "blocked"
    assert manifest["summary"]["page_gap_view_count_before"] == 0
    assert any(
        blocker.startswith("manifest_source_unavailable:")
        for blocker in manifest["blockers"]
    )
    valid, errors = module.validate_stock_analysis_page_gap_manifest(manifest)
    assert valid, errors


def test_validator_rejects_tampered_summary_and_canonical_hash(tmp_path: Path) -> None:
    manifest = _build_happy(tmp_path / "tamper-summary.duckdb")
    tampered = copy.deepcopy(manifest)
    tampered["summary"]["page_gap_view_count_before"] = 99
    tampered["canonical_manifest_sha256"] = "F" * 64

    valid, errors = module.validate_stock_analysis_page_gap_manifest(tampered)

    assert valid is False
    assert (
        "manifest.summary.page_gap_view_count_before cannot be below mapped count"
        not in errors
    )
    assert (
        "manifest.summary.factor_write_only_projected_gap_view_count mismatch" in errors
    )
    assert "manifest.canonical_manifest_sha256 mismatch" in errors


def test_validator_recomputes_ids_and_reference_roles_after_rehash(
    tmp_path: Path,
) -> None:
    manifest = _build_happy(tmp_path / "tamper-refs.duckdb")
    tampered_id = copy.deepcopy(manifest)
    tampered_id["gap_views"][0]["gap_view_id"] = "F" * 64
    _rehash(tampered_id)

    valid_id, id_errors = module.validate_stock_analysis_page_gap_manifest(tampered_id)

    assert valid_id is False
    assert "manifest.gap_views[0].gap_view_id mismatch" in id_errors
    assert any("gap_view_references mismatch" in error for error in id_errors)

    tampered_role = copy.deepcopy(manifest)
    tampered_role["missing_factor_cells"][0]["role_use_counts"]["entry"] += 1
    _rehash(tampered_role)

    valid_role, role_errors = module.validate_stock_analysis_page_gap_manifest(
        tampered_role
    )

    assert valid_role is False
    assert any("role_use_counts mismatch" in error for error in role_errors)


def test_validator_rejects_old_shape_noncanonical_stock_and_db_hash_drift(
    tmp_path: Path,
) -> None:
    manifest = _build_happy(tmp_path / "tamper-contract.duckdb")
    tampered = copy.deepcopy(manifest)
    tampered["route"] = tampered.pop("page_route")
    tampered["approvals"] = tampered.pop("approval_boundary")
    tampered["source_contract"]["metric_semantics"] = "drifted"
    tampered["summary"]["factor_write_only_projected_gap_view_count"] = 0
    tampered["gap_views"][0]["stock_code"] = "bad"
    tampered["database"]["sha256_after"] = "A" * 64
    tampered["database"]["unchanged"] = True
    _rehash(tampered)

    valid, errors = module.validate_stock_analysis_page_gap_manifest(tampered)

    assert valid is False
    assert "manifest.page_route mismatch" in errors
    assert "manifest.approval_boundary must be a mapping" in errors
    assert "manifest.source_contract mismatch" in errors
    assert (
        "manifest.summary.factor_write_only_projected_gap_view_count mismatch" in errors
    )
    assert any("canonical A-share stock code" in error for error in errors)
    assert "manifest.database hashes must match" in errors


def test_validator_rejects_string_pseudo_sequences(tmp_path: Path) -> None:
    manifest = _build_happy(tmp_path / "tamper-sequence.duckdb")
    tampered = copy.deepcopy(manifest)
    tampered["gap_views"] = "not-a-list"
    _rehash(tampered)

    valid, errors = module.validate_stock_analysis_page_gap_manifest(tampered)

    assert valid is False
    assert "manifest.gap_views must be a list" in errors
