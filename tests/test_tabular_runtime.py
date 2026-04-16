from __future__ import annotations

import tomllib
from pathlib import Path

import pandas as pd

from tests.helpers import ROOT, load_module


def test_backend_runtime_stack_includes_polars_and_runtime_pandas() -> None:
    pyproject_path = ROOT / "backend" / "pyproject.toml"

    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dependencies = data["project"]["dependencies"]

    assert data["project"]["requires-python"] == ">=3.11"
    assert any(dep.startswith("fastapi") for dep in dependencies)
    assert any(dep.startswith("sqlalchemy") for dep in dependencies)
    assert any(dep.startswith("redis") for dep in dependencies)
    assert any(dep.startswith("dramatiq") for dep in dependencies)
    assert any(dep.startswith("polars") for dep in dependencies)
    assert any(dep.startswith("pandas") for dep in dependencies)


def test_records_to_pandas_prefers_polars_and_normalizes_columns() -> None:
    module = load_module(
        "backend.app.services.tabular_runtime",
        "backend/app/services/tabular_runtime.py",
    )

    frame = module.records_to_pandas(
        [
            {
                "report_date": "2025-06-03",
                "market_value": "100.5",
                "interest_rate": "2.4",
                "is_issuance_like": None,
            }
        ],
        date_columns=("report_date",),
        float_columns=("market_value", "interest_rate"),
        bool_columns=("is_issuance_like",),
    )

    assert module.preferred_tabular_backend() == "polars"
    assert isinstance(frame, pd.DataFrame)
    assert str(frame["report_date"].dtype).startswith("datetime64")
    assert frame.loc[0, "market_value"] == 100.5
    assert frame.loc[0, "interest_rate"] == 2.4
    assert bool(frame.loc[0, "is_issuance_like"]) is False


def test_records_to_pandas_falls_back_to_pandas_when_polars_is_unavailable() -> None:
    module = load_module(
        "backend.app.services.tabular_runtime",
        "backend/app/services/tabular_runtime.py",
    )
    original_polars = module.pl
    module.pl = None
    try:
        frame = module.records_to_pandas(
            [{"report_date": "2025-06-03", "amount": "12.5"}],
            date_columns=("report_date",),
            float_columns=("amount",),
        )
    finally:
        module.pl = original_polars

    assert isinstance(frame, pd.DataFrame)
    assert str(frame["report_date"].dtype).startswith("datetime64")
    assert frame.loc[0, "amount"] == 12.5
