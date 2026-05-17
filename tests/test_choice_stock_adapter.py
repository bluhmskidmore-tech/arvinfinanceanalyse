from __future__ import annotations

import json
from pathlib import Path

from backend.app.repositories.choice_client import ChoiceClient
from backend.app.repositories.choice_stock_adapter import (
    CHOICE_STOCK_REQUIRED_INPUT_FAMILIES,
    choice_stock_optional_input_status,
    load_choice_stock_request_plan,
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


def test_choice_stock_catalog_requires_confirmation_metadata(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "catalog_version": "test_missing_confirmation_metadata",
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

    assert readiness.ready is False
    assert readiness.status == "incomplete_catalog"
    assert readiness.missing_input_families == list(CHOICE_STOCK_REQUIRED_INPUT_FAMILIES)
    assert "stock_ohlcv:stock_ohlcv_field" in readiness.unconfirmed_fields


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
                        "confirmation_source": "Choice terminal command generator fixture",
                        "confirmed_at": "2026-04-29",
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


def test_optional_theme_inputs_are_planned_without_becoming_required_gates(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    required_fields = [
        {
            "input_family": family,
            "field_key": f"{family}_field",
            "vendor_indicator": f"{family}_indicator",
            "call": "csd" if family == "stock_ohlcv" else "css",
            "confirmed": True,
            "confirmation_source": "unit test",
            "confirmed_at": "2026-05-11",
        }
        for family in CHOICE_STOCK_REQUIRED_INPUT_FAMILIES
    ]
    catalog_path.write_text(
        json.dumps(
            {
                "catalog_version": "test_optional_theme_inputs",
                "vendor_name": "choice",
                "generated_from": "unit_test",
                "fields": [
                    *required_fields,
                    {
                        "input_family": "concept_membership",
                        "field_key": "choice_concept_membership",
                        "vendor_indicator": "CONCEPTCODE,CONCEPTNAME",
                        "call": "css",
                        "required": False,
                        "confirmed": True,
                        "confirmation_source": "unit test optional concept probe",
                        "confirmed_at": "2026-05-11",
                    },
                    {
                        "input_family": "intraday_movement",
                        "field_key": "choice_intraday_movement",
                        "vendor_indicator": "StockInfo",
                        "call": "ctr",
                        "required": False,
                        "request_options": {
                            "StartDate": "__AS_OF_DATE__",
                            "EndDate": "__AS_OF_DATE__",
                            "Ispandas": 0,
                        },
                        "confirmed": True,
                        "confirmation_source": "unit test optional movement probe",
                        "confirmed_at": "2026-05-11",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    readiness = load_choice_stock_readiness(catalog_path)
    plan = load_choice_stock_request_plan(catalog_path, as_of_date="2026-05-11")

    assert readiness.ready is True
    assert readiness.missing_input_families == []
    planned = {f"{item.input_family}:{item.field_key}" for item in plan.requests}
    assert "concept_membership:choice_concept_membership" in planned
    assert "intraday_movement:choice_intraday_movement" in planned
    movement_request = next(item for item in plan.requests if item.input_family == "intraday_movement")
    assert movement_request.request_arguments == ["StockInfo", ""]
    assert movement_request.request_options_text == "StartDate=2026-05-11,EndDate=2026-05-11,Ispandas=0"


def test_optional_theme_inputs_can_stay_non_blocking_while_reporting_catalog_unconfirmed(tmp_path: Path) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "catalog_version": "test_optional_theme_inputs_unconfirmed",
                "vendor_name": "choice",
                "generated_from": "unit_test",
                "fields": [
                    *[
                        {
                            "input_family": family,
                            "field_key": f"{family}_field",
                            "vendor_indicator": f"{family}_indicator",
                            "call": "csd" if family == "stock_ohlcv" else "css",
                            "confirmed": True,
                            "confirmation_source": "unit test",
                            "confirmed_at": "2026-05-11",
                        }
                        for family in CHOICE_STOCK_REQUIRED_INPUT_FAMILIES
                    ],
                    {
                        "input_family": "concept_membership",
                        "field_key": "choice_concept_membership",
                        "vendor_indicator": "",
                        "call": "css",
                        "required": False,
                        "confirmed": False,
                        "confirmation_source": "",
                        "confirmed_at": "",
                    },
                    {
                        "input_family": "intraday_movement",
                        "field_key": "choice_intraday_movement",
                        "vendor_indicator": "",
                        "call": "ctr",
                        "required": False,
                        "confirmed": False,
                        "confirmation_source": "",
                        "confirmed_at": "",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    readiness = load_choice_stock_readiness(catalog_path)

    assert readiness.ready is True
    assert readiness.status == "ready"
    assert readiness.missing_input_families == []
    assert choice_stock_optional_input_status(readiness, "concept_membership") == "catalog_unconfirmed"
    assert choice_stock_optional_input_status(readiness, "intraday_movement") == "catalog_unconfirmed"


def test_choice_stock_catalog_md_entry_shape_documents_sector_call() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    doc = (repo_root / "docs" / "choice_stock_catalog.md").read_text(encoding="utf-8")
    start = doc.index("## Entry Shape")
    end = doc.index("## Fail-Closed Behavior")
    entry_shape = doc[start:end]
    call_lines = [ln for ln in entry_shape.splitlines() if "`call`" in ln]
    assert call_lines, "expected a `call` bullet in Entry Shape"
    assert any("sector" in ln for ln in call_lines), "call enumeration must include sector (checked-in catalog uses call=sector)"


def test_checked_in_choice_stock_catalog_json_documents_sector_strength_units_and_limit_policy() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    catalog = json.loads((repo_root / "config" / "choice_stock_catalog.json").read_text(encoding="utf-8"))
    fields = {f["field_key"]: f for f in catalog["fields"]}
    rta = fields["daily_return_turnover_amplitude"]
    assert "unit" in rta
    unit_text = rta["unit"]
    assert "percentage point" in unit_text.lower()
    assert "1.2%" in unit_text

    limit_entry = fields["daily_limit_flags"]
    desc = (limit_entry.get("description") or "").lower()
    assert "highlimit" in desc or "limit" in desc
    assert "flag" in desc
    assert "price" in desc

    policy = catalog.get("policy_note") or ""
    policy_l = policy.lower()
    assert "limit_ratio" in policy_l
    assert "tushare" in policy_l

    concept_entry = fields["choice_concept_membership"]
    assert concept_entry["confirmed"] is False

    movement_entry = fields["choice_intraday_movement"]
    assert movement_entry["call"] == "ctr"
    assert movement_entry["vendor_indicator"] == "StockInfo"
    assert movement_entry["request_options"]["StartDate"] == "__AS_OF_DATE__"
    assert movement_entry["request_options"]["EndDate"] == "__AS_OF_DATE__"
    assert movement_entry["confirmed"] is True


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
