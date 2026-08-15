from __future__ import annotations

# Governance: DuckDB 查询失败可观测性守卫；同时覆盖 macro_vendor，surface 取 surface_macro_toolkit。
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from backend.app.services import macro_toolkit_service, macro_vendor_service

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


def test_macro_vendor_envelope_marks_query_failure_unlike_missing_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    missing_path = tmp_path / "missing.duckdb"
    missing_envelope = macro_vendor_service.macro_vendor_envelope(str(missing_path))
    assert missing_envelope["result"]["series"] == []
    assert missing_envelope["result_meta"]["source_version"] == "sv_macro_vendor_empty"
    assert missing_envelope["result_meta"].get("filters_applied", {}) == {}

    broken_path = tmp_path / "broken.duckdb"
    broken_path.write_bytes(b"not-a-duckdb")

    def raise_open(*_args: object, **_kwargs: object) -> duckdb.DuckDBPyConnection:
        raise duckdb.IOException("IO Error: simulated corrupt database")

    monkeypatch.setattr(duckdb, "connect", raise_open)
    failed_envelope = macro_vendor_service.macro_vendor_envelope(str(broken_path))

    assert failed_envelope["result"]["series"] == []
    assert failed_envelope["result_meta"]["quality_flag"] == "warning"
    assert failed_envelope["result_meta"]["source_version"] == "sv_macro_vendor_query_failed"
    warnings = failed_envelope["result_meta"]["filters_applied"]["warnings"]
    assert len(warnings) == 1
    assert "phase1_macro_vendor_catalog" in warnings[0]
    assert "IOException" in warnings[0]


def test_macro_toolkit_price_context_distinguishes_query_failure_from_missing_data(
    tmp_path: Path,
    monkeypatch,
) -> None:
    missing = macro_toolkit_service.load_equity_strategy_price_context(tmp_path / "absent.duckdb")
    assert missing is None

    broken_path = tmp_path / "broken-toolkit.duckdb"
    broken_path.write_bytes(b"not-a-duckdb")

    def raise_open(*_args: object, **_kwargs: object) -> duckdb.DuckDBPyConnection:
        raise duckdb.IOException("IO Error: simulated corrupt database")

    monkeypatch.setattr(duckdb, "connect", raise_open)
    failed = macro_toolkit_service.load_equity_strategy_price_context(broken_path)

    assert isinstance(failed, dict)
    assert failed["data_status"] == "unavailable"
    assert failed["prices"] is None
    assert any("DUCKDB_QUERY_FAILED" in item for item in failed["warnings"])
    assert any("choice_stock_daily_observation" in item for item in failed["warnings"])

    risk = macro_toolkit_service.load_a_share_stampede_risk_context(broken_path)
    assert isinstance(risk, dict)
    assert risk["data_status"] == "unavailable"
    assert isinstance(risk["observations"], pd.DataFrame)
    assert risk["observations"].empty
    assert any("DUCKDB_QUERY_FAILED" in item for item in risk["warnings"])
