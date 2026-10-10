from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.run_fable_extension_study import load_study_contract


def _contract_payload() -> dict[str, Any]:
    source = Path("docs/stock_analysis_fable_extension_study_contract.json")
    return json.loads(source.read_text(encoding="utf-8"))


def _write_contract(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "invalid-contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_contract_rejects_unmapped_required_promotion_evidence(tmp_path: Path) -> None:
    payload = _contract_payload()
    payload["promotion"]["required_evidence"].append("unmapped_future_gate")

    with pytest.raises(ValueError, match="unsupported promotion required_evidence"):
        load_study_contract(_write_contract(tmp_path, payload))


def test_contract_rejects_omitted_required_promotion_evidence(tmp_path: Path) -> None:
    payload = _contract_payload()
    payload["promotion"]["required_evidence"].remove(
        "primary_adjusted_coverage_gate_passes"
    )

    with pytest.raises(ValueError, match="promotion required_evidence must match"):
        load_study_contract(_write_contract(tmp_path, payload))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("confidence_interval", 0.90, "confidence_interval"),
        ("bootstrap_unit", "stock_code", "bootstrap_unit"),
        ("continuous_effect_scale", "raw_slope", "continuous_effect_scale"),
        ("holdout_method", "random_split", "holdout_method"),
    ],
)
def test_contract_rejects_inference_settings_not_implemented_by_runner(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    payload = _contract_payload()
    payload["inference"][field] = value

    with pytest.raises(ValueError, match=message):
        load_study_contract(_write_contract(tmp_path, payload))
