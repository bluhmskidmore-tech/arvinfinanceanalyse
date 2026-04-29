from __future__ import annotations

import json
from pathlib import Path

from backend.app.repositories.choice_client import ChoiceClient
from backend.app.repositories.choice_stock_adapter import (
    CHOICE_STOCK_REQUIRED_INPUT_FAMILIES,
    load_choice_stock_readiness,
)


def test_missing_choice_stock_catalog_is_fail_closed(tmp_path: Path) -> None:
    readiness = load_choice_stock_readiness(tmp_path / "missing-choice-stock-catalog.json")

    assert readiness.ready is False
    assert readiness.status == "missing_catalog"
    assert readiness.missing_input_families == list(CHOICE_STOCK_REQUIRED_INPUT_FAMILIES)
    assert "Choice stock catalog is missing" in readiness.message


def test_empty_choice_stock_catalog_is_incomplete_without_choice_calls(tmp_path: Path, monkeypatch) -> None:
    def fail_choice_call(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Choice stock API should not be called while catalog is incomplete.")

    monkeypatch.setattr(ChoiceClient, "css", fail_choice_call)
    monkeypatch.setattr(ChoiceClient, "csd", fail_choice_call)
    catalog_path = tmp_path / "choice_stock_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "catalog_version": "test_empty",
                "vendor_name": "choice",
                "generated_from": "unit_test",
                "fields": [],
            }
        ),
        encoding="utf-8",
    )

    readiness = load_choice_stock_readiness(catalog_path)

    assert readiness.ready is False
    assert readiness.status == "incomplete_catalog"
    assert readiness.missing_input_families == list(CHOICE_STOCK_REQUIRED_INPUT_FAMILIES)
    assert "missing or unconfirmed required input families" in readiness.message


def test_choice_stock_catalog_requires_confirmed_indicator_for_every_required_family(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "catalog_version": "test_unconfirmed",
                "vendor_name": "choice",
                "generated_from": "unit_test",
                "fields": [
                    {
                        "input_family": "sector_membership",
                        "field_key": "sector_name",
                        "vendor_indicator": "",
                        "call": "css",
                        "confirmed": True,
                    },
                    {
                        "input_family": "stock_ohlcv",
                        "field_key": "close",
                        "vendor_indicator": "CLOSE",
                        "call": "csd",
                        "confirmed": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    readiness = load_choice_stock_readiness(catalog_path)

    assert readiness.ready is False
    assert readiness.status == "incomplete_catalog"
    assert "sector_membership:sector_name" in readiness.unconfirmed_fields
    assert "stock_ohlcv:close" in readiness.unconfirmed_fields
    assert "sector_membership" in readiness.missing_input_families
    assert "stock_ohlcv" in readiness.missing_input_families


def test_confirmed_choice_stock_catalog_is_ready(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "catalog_version": "test_ready",
                "vendor_name": "choice",
                "generated_from": "unit_test",
                "fields": [
                    {
                        "input_family": family,
                        "field_key": f"{family}_field",
                        "vendor_indicator": f"{family}_indicator",
                        "call": "csd" if family == "stock_ohlcv" else "css",
                        "confirmed": True,
                    }
                    for family in CHOICE_STOCK_REQUIRED_INPUT_FAMILIES
                ],
            }
        ),
        encoding="utf-8",
    )

    readiness = load_choice_stock_readiness(catalog_path)

    assert readiness.ready is True
    assert readiness.status == "ready"
    assert readiness.missing_input_families == []
    assert readiness.unconfirmed_fields == []


def test_invalid_choice_stock_catalog_is_incomplete(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "catalog_version": "test_invalid",
                "vendor_name": "choice",
                "fields": [{"input_family": "not_a_family", "field_key": "bad"}],
            }
        ),
        encoding="utf-8",
    )

    readiness = load_choice_stock_readiness(catalog_path)

    assert readiness.ready is False
    assert readiness.status == "incomplete_catalog"
    assert readiness.missing_input_families == list(CHOICE_STOCK_REQUIRED_INPUT_FAMILIES)
    assert readiness.unconfirmed_fields[0].startswith("catalog_validation:")
