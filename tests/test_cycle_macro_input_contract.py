from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.cycle_macro_score import M2_YOY_SERIES_ID
from backend.app.services.market_data_livermore_service import (
    _load_cycle_input_evidence,
)
from backend.app.services.market_data_livermore_service import _cycle_input_row_issue


def _create_macro_table(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()


def _insert_rows(path: Path, rows: list[tuple[object, ...]]) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        conn.close()


def _macro_row(
    series_id: str,
    trade_date: str,
    value: float,
    *,
    frequency: str,
    unit: str,
    quality_flag: str = "ok",
    run_id: str = "backfill_macro_v1:20260502T120000Z",
    source_version: str = "backfill_macro_v1",
    vendor_version: str = "vv_test",
    rule_version: str = "rv_test",
) -> tuple[object, ...]:
    return (
        series_id,
        series_id,
        trade_date,
        value,
        frequency,
        unit,
        source_version,
        vendor_version,
        rule_version,
        quality_flag,
        run_id,
    )


_OFFICIAL_PBC_ARTIFACTS = [
    {
        "report_month": "2026-04",
        "release_url": "https://www.pbc.gov.cn/releases/2026-04.html",
        "published_at": "2026-05-14T17:00:02+08:00",
        "available_at": "2026-05-14T17:03:10+08:00",
        "artifact_sha256": "1" * 64,
    },
    {
        "report_month": "2026-05",
        "release_url": "https://www.pbc.gov.cn/releases/2026-05.html",
        "published_at": "2026-06-12T17:00:01+08:00",
        "available_at": "2026-06-12T17:05:23+08:00",
        "artifact_sha256": "2" * 64,
    },
]
_OFFICIAL_ARTIFACT_MANIFEST_SHA256 = hashlib.sha256(
    json.dumps(
        _OFFICIAL_PBC_ARTIFACTS,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()
_OFFICIAL_VENDOR_VERSION = (
    "vv_backfill_macro_pbc_financial_statistics_release_20260710_"
    f"{_OFFICIAL_ARTIFACT_MANIFEST_SHA256[:16]}_{'b' * 16}"
)
_REPO_ROOT = Path(__file__).resolve().parents[1]
_PRODUCTION_AVAILABILITY_MANIFEST_PATH = (
    _REPO_ROOT / "config" / "cycle_rotation_macro_official_availability.json"
)
_PRODUCTION_RELEASES_MANIFEST_PATH = (
    _REPO_ROOT / "config" / "cycle_rotation_macro_official_releases.json"
)


def _write_official_availability_sidecar(
    path: Path,
    *,
    binding_overrides: dict[str, object] | None = None,
    artifact_overrides: dict[str, object] | None = None,
) -> None:
    binding: dict[str, object] = {
        "source": "pbc_financial_statistics_release",
        "series_id": M2_YOY_SERIES_ID,
        "vendor_version": _OFFICIAL_VENDOR_VERSION,
        "covered_period_start": "2026-04-01",
        "covered_period_end": "2026-05-01",
        "artifact_manifest_sha256": _OFFICIAL_ARTIFACT_MANIFEST_SHA256,
        "mapping_version": "rv_pbc_financial_statistics_release_v1",
        "rule_version": "rv_backfill_macro_v1",
        "first_usable_trade_date": "2026-06-15",
    }
    binding.update(binding_overrides or {})
    artifact: dict[str, object] = {
        "source": "pbc_financial_statistics_release",
        "artifact_kind": "artifact_set_manifest",
        "artifact_manifest_sha256": _OFFICIAL_ARTIFACT_MANIFEST_SHA256,
        "component_artifact_sha256s": [
            row["artifact_sha256"] for row in _OFFICIAL_PBC_ARTIFACTS
        ],
    }
    artifact.update(artifact_overrides or {})
    path.write_text(
        json.dumps(
            {
                "manifest_version": "cycle_macro_official_availability.v1",
                "artifacts": [artifact],
                "bindings": [binding],
            }
        ),
        encoding="utf-8",
    )
    _write_official_releases_manifest(_official_releases_path(path))


def _official_releases_path(sidecar_path: Path) -> Path:
    return sidecar_path.with_name("cycle_rotation_macro_official_releases.json")


def _write_official_releases_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "manifest_version": "test.official-releases.v1",
                "releases": [
                    {
                        "source": "pbc_financial_statistics_release",
                        "series_id": M2_YOY_SERIES_ID,
                        **artifact,
                    }
                    for artifact in _OFFICIAL_PBC_ARTIFACTS
                ],
            }
        ),
        encoding="utf-8",
    )


def test_cycle_input_evidence_reports_m2_as_actual_credit_fallback_source(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    _create_macro_table(db_path)
    _insert_rows(
        db_path,
        [
            _macro_row("M0001385", "2026-03-01", 8.5, frequency="monthly", unit="%"),
            _macro_row("M0001385", "2026-04-01", 9.2, frequency="monthly", unit="%"),
        ],
    )

    evidence = _load_cycle_input_evidence(
        duckdb_path=str(db_path), as_of_date=date(2026, 5, 8)
    )

    assert evidence.credit_impulse_ready is True
    assert evidence.macro_snapshot is not None
    assert (
        evidence.macro_snapshot.lineage["credit_impulse"]["series_id"]
        == M2_YOY_SERIES_ID
    )
    assert M2_YOY_SERIES_ID in evidence.credit_impulse_evidence


def test_cycle_input_evidence_falls_back_to_m2_when_social_financing_months_are_invalid(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    _create_macro_table(db_path)
    _insert_rows(
        db_path,
        [
            _macro_row("M5525763", "2026-02-01", 8.3, frequency="monthly", unit="%"),
            _macro_row("M5525763", "2026-04-01", 9.2, frequency="monthly", unit="%"),
            _macro_row("M0001385", "2026-03-01", 8.5, frequency="monthly", unit="%"),
            _macro_row("M0001385", "2026-04-01", 9.0, frequency="monthly", unit="%"),
        ],
    )

    evidence = _load_cycle_input_evidence(
        duckdb_path=str(db_path), as_of_date=date(2026, 5, 8)
    )

    assert evidence.credit_impulse_ready is True
    assert evidence.macro_snapshot is not None
    assert (
        evidence.macro_snapshot.lineage["credit_impulse"]["series_id"]
        == M2_YOY_SERIES_ID
    )


@pytest.mark.parametrize(
    ("frequency", "unit", "quality_flag"),
    [
        ("weekly", "index", "ok"),
        ("monthly", "%", "ok"),
        ("monthly", "index", "error"),
    ],
)
def test_cycle_input_evidence_rejects_invalid_pmi_contract_rows(
    tmp_path: Path,
    frequency: str,
    unit: str,
    quality_flag: str,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    _create_macro_table(db_path)
    _insert_rows(
        db_path,
        [
            _macro_row(
                "M0017126",
                "2026-04-01",
                50.2,
                frequency=frequency,
                unit=unit,
                quality_flag=quality_flag,
            )
        ],
    )

    evidence = _load_cycle_input_evidence(
        duckdb_path=str(db_path), as_of_date=date(2026, 5, 8)
    )

    assert evidence.pmi_ready is False


def test_cycle_input_evidence_rejects_unproven_monthly_availability(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    _create_macro_table(db_path)
    _insert_rows(
        db_path,
        [
            _macro_row(
                "M0017126",
                "2026-04-01",
                50.2,
                frequency="monthly",
                unit="index",
                run_id="vendor-run-without-availability-date",
            )
        ],
    )

    evidence = _load_cycle_input_evidence(
        duckdb_path=str(db_path), as_of_date=date(2026, 5, 8)
    )

    assert evidence.pmi_ready is False
    assert "availability" in evidence.pmi_evidence


def test_cycle_input_evidence_rejects_spoofed_backfill_run_id(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    _create_macro_table(db_path)
    _insert_rows(
        db_path,
        [
            _macro_row(
                "M0017126",
                "2026-04-01",
                50.2,
                frequency="monthly",
                unit="index",
                source_version="vendor_source_v1",
                run_id="backfill_macro_v1:20260502T120000Z",
            )
        ],
    )

    evidence = _load_cycle_input_evidence(
        duckdb_path=str(db_path), as_of_date=date(2026, 5, 8)
    )

    assert evidence.pmi_ready is False
    assert "source_version" in evidence.pmi_evidence


def test_cycle_input_row_issue_fails_closed_for_invalid_date() -> None:
    issue = _cycle_input_row_issue(
        series_id="M0017126",
        trade_date="20261340",
        frequency="monthly",
        unit="index",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        run_id="backfill_macro_v1:20260502T120000Z",
        as_of_date=date(2026, 5, 8),
    )

    assert issue == "M0017126 has an invalid business date."


def test_cycle_input_row_issue_fails_closed_for_invalid_run_id_date() -> None:
    issue = _cycle_input_row_issue(
        series_id="M0017126",
        trade_date="2026-05-01",
        frequency="monthly",
        unit="index",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        run_id="backfill_macro_v1:20261340T120000Z",
        as_of_date=date(2026, 5, 8),
    )

    assert issue == "M0017126 availability date in materialization run_id is invalid."


def test_new_orders_series_cannot_satisfy_manufacturing_pmi(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    _create_macro_table(db_path)
    _insert_rows(
        db_path,
        [
            _macro_row(
                "M0017127", "2026-04-01", 51.4, frequency="monthly", unit="index"
            ),
        ],
    )

    evidence = _load_cycle_input_evidence(
        duckdb_path=str(db_path), as_of_date=date(2026, 5, 8)
    )

    assert evidence.pmi_ready is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_cycle_input_evidence_rejects_non_finite_values(
    tmp_path: Path, value: float
) -> None:
    db_path = tmp_path / "macro.duckdb"
    _create_macro_table(db_path)
    _insert_rows(
        db_path,
        [
            _macro_row(
                "M0017126",
                "2026-05-01",
                value,
                frequency="monthly",
                unit="index",
            )
        ],
    )

    evidence = _load_cycle_input_evidence(
        duckdb_path=str(db_path), as_of_date=date(2026, 5, 8)
    )

    assert evidence.pmi_ready is False
    assert evidence.macro_snapshot is not None
    assert "PMI" in evidence.macro_snapshot.missing_inputs


def test_official_availability_sidecar_bypasses_only_future_materialization_date(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "cycle_rotation_macro_official_availability.json"
    _write_official_availability_sidecar(sidecar_path)

    issue = _cycle_input_row_issue(
        series_id=M2_YOY_SERIES_ID,
        trade_date="2026-05-01",
        frequency="monthly",
        unit="%",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        vendor_version=_OFFICIAL_VENDOR_VERSION,
        rule_version="rv_backfill_macro_v1",
        run_id="backfill_macro_v1:20260712T120000Z",
        as_of_date=date(2026, 7, 10),
        availability_manifest_path=sidecar_path,
        official_releases_manifest_path=_official_releases_path(sidecar_path),
    )

    assert issue is None


def test_official_availability_rejects_synchronized_full_sha_tail_tampering(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "cycle_rotation_macro_official_availability.json"
    tampered_sha256 = _OFFICIAL_ARTIFACT_MANIFEST_SHA256[:16] + ("c" * 48)
    _write_official_availability_sidecar(
        sidecar_path,
        binding_overrides={"artifact_manifest_sha256": tampered_sha256},
        artifact_overrides={"artifact_manifest_sha256": tampered_sha256},
    )

    issue = _cycle_input_row_issue(
        series_id=M2_YOY_SERIES_ID,
        trade_date="2026-05-01",
        frequency="monthly",
        unit="%",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        vendor_version=_OFFICIAL_VENDOR_VERSION,
        rule_version="rv_backfill_macro_v1",
        run_id="backfill_macro_v1:20260712T120000Z",
        as_of_date=date(2026, 7, 10),
        availability_manifest_path=sidecar_path,
        official_releases_manifest_path=_official_releases_path(sidecar_path),
    )

    assert issue == (
        "M0001385 availability date 2026-07-12 is after evaluation date 2026-07-10."
    )


def test_official_availability_rejects_pbc_component_artifact_hash_tampering(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "cycle_rotation_macro_official_availability.json"
    _write_official_availability_sidecar(
        sidecar_path,
        artifact_overrides={
            "component_artifact_sha256s": ["9" * 64, "2" * 64],
        },
    )

    issue = _cycle_input_row_issue(
        series_id=M2_YOY_SERIES_ID,
        trade_date="2026-05-01",
        frequency="monthly",
        unit="%",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        vendor_version=_OFFICIAL_VENDOR_VERSION,
        rule_version="rv_backfill_macro_v1",
        run_id="backfill_macro_v1:20260712T120000Z",
        as_of_date=date(2026, 7, 10),
        availability_manifest_path=sidecar_path,
        official_releases_manifest_path=_official_releases_path(sidecar_path),
    )

    assert issue == (
        "M0001385 availability date 2026-07-12 is after evaluation date 2026-07-10."
    )


def test_official_availability_rejects_first_usable_not_after_release_availability(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "cycle_rotation_macro_official_availability.json"
    _write_official_availability_sidecar(
        sidecar_path,
        binding_overrides={"first_usable_trade_date": "2026-06-12"},
    )

    issue = _cycle_input_row_issue(
        series_id=M2_YOY_SERIES_ID,
        trade_date="2026-05-01",
        frequency="monthly",
        unit="%",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        vendor_version=_OFFICIAL_VENDOR_VERSION,
        rule_version="rv_backfill_macro_v1",
        run_id="backfill_macro_v1:20260712T120000Z",
        as_of_date=date(2026, 7, 10),
        availability_manifest_path=sidecar_path,
        official_releases_manifest_path=_official_releases_path(sidecar_path),
    )

    assert issue == (
        "M0001385 availability date 2026-07-12 is after evaluation date 2026-07-10."
    )


def test_official_availability_sidecar_does_not_bypass_before_first_usable_trade_date(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "cycle_rotation_macro_official_availability.json"
    _write_official_availability_sidecar(sidecar_path)

    issue = _cycle_input_row_issue(
        series_id=M2_YOY_SERIES_ID,
        trade_date="2026-05-01",
        frequency="monthly",
        unit="%",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        vendor_version=_OFFICIAL_VENDOR_VERSION,
        rule_version="rv_backfill_macro_v1",
        run_id="backfill_macro_v1:20260712T120000Z",
        as_of_date=date(2026, 6, 12),
        availability_manifest_path=sidecar_path,
        official_releases_manifest_path=_official_releases_path(sidecar_path),
    )

    assert issue == (
        "M0001385 availability date 2026-07-12 is after evaluation date 2026-06-12."
    )


@pytest.mark.parametrize(
    "binding_overrides",
    [
        {"series_id": "M5525763"},
        {
            "vendor_version": "vv_backfill_macro_pbc_financial_statistics_release_tampered"
        },
        {"covered_period_end": "2026-04-01"},
        {"artifact_manifest_sha256": "c" * 64},
        {"mapping_version": "rv_unapproved_mapping_v1"},
        {"rule_version": "rv_unapproved_rule_v1"},
    ],
    ids=[
        "series-mismatch",
        "vendor-mismatch",
        "coverage-mismatch",
        "artifact-full-sha-mismatch",
        "mapping-version-mismatch",
        "rule-version-mismatch",
    ],
)
def test_official_availability_sidecar_binding_mismatch_falls_back_to_run_id_gate(
    tmp_path: Path,
    binding_overrides: dict[str, object],
) -> None:
    sidecar_path = tmp_path / "cycle_rotation_macro_official_availability.json"
    _write_official_availability_sidecar(
        sidecar_path,
        binding_overrides=binding_overrides,
    )

    issue = _cycle_input_row_issue(
        series_id=M2_YOY_SERIES_ID,
        trade_date="2026-05-01",
        frequency="monthly",
        unit="%",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        vendor_version=_OFFICIAL_VENDOR_VERSION,
        rule_version="rv_backfill_macro_v1",
        run_id="backfill_macro_v1:20260712T120000Z",
        as_of_date=date(2026, 7, 10),
        availability_manifest_path=sidecar_path,
        official_releases_manifest_path=_official_releases_path(sidecar_path),
    )

    assert issue == (
        "M0001385 availability date 2026-07-12 is after evaluation date 2026-07-10."
    )


def test_missing_official_availability_sidecar_falls_back_to_run_id_gate(
    tmp_path: Path,
) -> None:
    issue = _cycle_input_row_issue(
        series_id=M2_YOY_SERIES_ID,
        trade_date="2026-05-01",
        frequency="monthly",
        unit="%",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        vendor_version=_OFFICIAL_VENDOR_VERSION,
        rule_version="rv_backfill_macro_v1",
        run_id="backfill_macro_v1:20260712T120000Z",
        as_of_date=date(2026, 7, 10),
        availability_manifest_path=tmp_path / "missing-sidecar.json",
    )

    assert issue == (
        "M0001385 availability date 2026-07-12 is after evaluation date 2026-07-10."
    )


def test_cycle_input_evidence_uses_exact_official_availability_binding(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    sidecar_path = tmp_path / "cycle_rotation_macro_official_availability.json"
    _create_macro_table(db_path)
    _write_official_availability_sidecar(sidecar_path)
    _insert_rows(
        db_path,
        [
            _macro_row(
                M2_YOY_SERIES_ID,
                "2026-04-01",
                8.5,
                frequency="monthly",
                unit="%",
                vendor_version=_OFFICIAL_VENDOR_VERSION,
                rule_version="rv_backfill_macro_v1",
                run_id="backfill_macro_v1:20260712T120000Z",
            ),
            _macro_row(
                M2_YOY_SERIES_ID,
                "2026-05-01",
                8.9,
                frequency="monthly",
                unit="%",
                vendor_version=_OFFICIAL_VENDOR_VERSION,
                rule_version="rv_backfill_macro_v1",
                run_id="backfill_macro_v1:20260712T120000Z",
            ),
        ],
    )

    evidence = _load_cycle_input_evidence(
        duckdb_path=str(db_path),
        as_of_date=date(2026, 7, 10),
        availability_manifest_path=sidecar_path,
        official_releases_manifest_path=_official_releases_path(sidecar_path),
    )

    assert evidence.credit_impulse_ready is True
    assert evidence.macro_snapshot is not None
    assert (
        evidence.macro_snapshot.lineage["credit_impulse"]["series_id"]
        == M2_YOY_SERIES_ID
    )


def test_nbs_official_availability_requires_exact_release_coverage(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "cycle_rotation_macro_official_availability.json"
    payload = json.loads(
        _PRODUCTION_AVAILABILITY_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    nbs_binding = next(
        row for row in payload["bindings"] if row["series_id"] == "M0017126"
    )
    nbs_binding["covered_period_start"] = "2025-07-01"
    sidecar_path.write_text(json.dumps(payload), encoding="utf-8")

    issue = _cycle_input_row_issue(
        series_id="M0017126",
        trade_date="2026-06-01",
        frequency="monthly",
        unit="index",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        vendor_version=(
            "vv_backfill_macro_nbs_pmi_release_20260710_"
            "204801316c86ecf8_e6c278bdb0d88252"
        ),
        rule_version="rv_backfill_macro_v1",
        run_id="backfill_macro_v1:20260712T120000Z",
        as_of_date=date(2026, 7, 10),
        availability_manifest_path=sidecar_path,
        official_releases_manifest_path=_PRODUCTION_RELEASES_MANIFEST_PATH,
    )

    assert issue == (
        "M0017126 availability date 2026-07-12 is after evaluation date 2026-07-10."
    )


@pytest.mark.parametrize(
    ("series_id", "trade_date", "unit", "vendor_version"),
    [
        (
            "M0001385",
            "2026-05-01",
            "%",
            "vv_backfill_macro_pbc_financial_statistics_release_20260710_"
            "3b3cce029f072f21_d6a4ad7591ceacd2",
        ),
        (
            "M5525763",
            "2026-05-01",
            "%",
            "vv_backfill_macro_pbc_financial_statistics_release_20260710_"
            "3b3cce029f072f21_1866fb4d34d45fb1",
        ),
        (
            "M0017126",
            "2026-06-01",
            "index",
            "vv_backfill_macro_nbs_pmi_release_20260710_"
            "204801316c86ecf8_e6c278bdb0d88252",
        ),
    ],
    ids=["pbc-m2", "pbc-social-financing", "nbs-pmi"],
)
def test_production_official_availability_exact_pins_are_golden(
    series_id: str,
    trade_date: str,
    unit: str,
    vendor_version: str,
) -> None:
    issue = _cycle_input_row_issue(
        series_id=series_id,
        trade_date=trade_date,
        frequency="monthly",
        unit=unit,
        quality_flag="ok",
        source_version="backfill_macro_v1",
        vendor_version=vendor_version,
        rule_version="rv_backfill_macro_v1",
        run_id="backfill_macro_v1:20260712T120000Z",
        as_of_date=date(2026, 7, 10),
        availability_manifest_path=_PRODUCTION_AVAILABILITY_MANIFEST_PATH,
        official_releases_manifest_path=_PRODUCTION_RELEASES_MANIFEST_PATH,
    )

    assert issue is None


@pytest.mark.parametrize(
    ("series_id", "vendor_version"),
    [
        (
            "M0001385",
            "vv_backfill_macro_pbc_financial_statistics_release_20260722_"
            "dfe636f3083ab76e_6a071d961fab615c",
        ),
        (
            "M5525763",
            "vv_backfill_macro_pbc_financial_statistics_release_20260722_"
            "dfe636f3083ab76e_0ebbce6d30220d11",
        ),
    ],
    ids=["pbc-june-m2", "pbc-june-social-financing"],
)
def test_production_june_official_availability_matches_stock_analysis_target(
    series_id: str,
    vendor_version: str,
) -> None:
    issue = _cycle_input_row_issue(
        series_id=series_id,
        trade_date="2026-06-01",
        frequency="monthly",
        unit="%",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        vendor_version=vendor_version,
        rule_version="rv_backfill_macro_v1",
        run_id="backfill_macro_v1:20260723T120000Z",
        as_of_date=date(2026, 7, 22),
        availability_manifest_path=_PRODUCTION_AVAILABILITY_MANIFEST_PATH,
        official_releases_manifest_path=_PRODUCTION_RELEASES_MANIFEST_PATH,
    )

    assert issue is None
