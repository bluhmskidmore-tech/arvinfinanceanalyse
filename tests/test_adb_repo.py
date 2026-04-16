from __future__ import annotations

import shutil
import uuid
from datetime import date
from inspect import signature
from pathlib import Path

import duckdb

from tests.helpers import load_module
from tests.test_adb_analysis_api import (
    BOND_CORP,
    POSITION_ASSET,
    _ensure_tables,
    _insert_tyw,
    _insert_zqtz,
    _materialize_balance_analysis,
)


def _repo_tmp_dir() -> Path:
    base_dir = Path.home() / ".codex" / "memories" / "tmp_pytest"
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"adb-repo-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def test_adb_repo_exports_load_raw_data_contract() -> None:
    repo_mod = load_module(
        "backend.app.repositories.adb_repo",
        "backend/app/repositories/adb_repo.py",
    )
    repo = repo_mod.AdbRepository("placeholder.duckdb")

    assert repo.__class__.__name__ == "AdbRepository"
    assert list(signature(repo.load_raw_data).parameters) == ["start_date", "end_date"]


def test_adb_repo_reads_formal_facts_into_two_frames(monkeypatch) -> None:
    tmp_path = _repo_tmp_dir()
    try:
        duckdb_path = tmp_path / "adb-repo.duckdb"
        governance_dir = tmp_path / "governance"
        conn = duckdb.connect(str(duckdb_path))
        try:
            _ensure_tables(conn)
            _insert_zqtz(
                conn,
                report_date="2025-06-03",
                instrument_code="B-REPO-1",
                bond_type=BOND_CORP,
                market_value=100,
                is_issuance_like=False,
            )
            _insert_tyw(
                conn,
                report_date="2025-06-03",
                position_id="TYW-REPO-1",
                product_type="拆放同业",
                position_side=POSITION_ASSET,
                principal=50,
                rate=2.5,
            )
        finally:
            conn.close()

        _materialize_balance_analysis(
            duckdb_path,
            governance_dir,
            monkeypatch,
            report_dates=["2025-06-03"],
        )

        repo_mod = load_module(
            "backend.app.repositories.adb_repo",
            "backend/app/repositories/adb_repo.py",
        )
        repo = repo_mod.AdbRepository(str(duckdb_path))

        bonds_df, ib_df, source_versions, rule_versions = repo.load_raw_data(
            date(2025, 6, 3),
            date(2025, 6, 3),
        )

        assert list(bonds_df.columns) == [
            "report_date",
            "market_value",
            "yield_to_maturity",
            "coupon_rate",
            "interest_rate",
            "asset_class",
            "sub_type",
            "is_issuance_like",
        ]
        assert list(ib_df.columns) == [
            "report_date",
            "amount",
            "interest_rate",
            "product_type",
            "direction",
        ]
        assert bonds_df["report_date"].dt.strftime("%Y-%m-%d").tolist() == ["2025-06-03"]
        assert ib_df["report_date"].dt.strftime("%Y-%m-%d").tolist() == ["2025-06-03"]
        assert bonds_df["sub_type"].tolist() == [BOND_CORP]
        assert ib_df["direction"].tolist() == ["ASSET"]
        assert source_versions == ["sv-adb", "sv-adb"]
        assert rule_versions == ["rv-adb", "rv-adb"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
