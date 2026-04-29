from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ChoiceStockInputFamily = Literal[
    "sector_membership",
    "sector_strength",
    "stock_universe",
    "stock_ohlcv",
    "stock_status",
    "limit_up_quality",
]
ChoiceStockCall = Literal["css", "csd", "ctr"]
ChoiceStockCatalogStatus = Literal["missing_catalog", "incomplete_catalog", "ready"]

CHOICE_STOCK_REQUIRED_INPUT_FAMILIES: tuple[ChoiceStockInputFamily, ...] = (
    "sector_membership",
    "sector_strength",
    "stock_universe",
    "stock_ohlcv",
    "stock_status",
    "limit_up_quality",
)


class ChoiceStockCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_family: ChoiceStockInputFamily
    field_key: str
    vendor_indicator: str = ""
    call: ChoiceStockCall = "css"
    confirmed: bool = False
    confirmation_source: str = ""
    confirmed_at: str = ""
    required: bool = True
    unit: str | None = None
    description: str | None = None


class ChoiceStockCatalogAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version: str
    vendor_name: Literal["choice"] = "choice"
    generated_from: str = ""
    policy_note: str | None = None
    fields: list[ChoiceStockCatalogEntry] = Field(default_factory=list)


class ChoiceStockReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    status: ChoiceStockCatalogStatus
    catalog_path: str
    vendor_name: Literal["choice"] = "choice"
    missing_input_families: list[ChoiceStockInputFamily]
    unconfirmed_fields: list[str] = Field(default_factory=list)
    message: str


def load_choice_stock_readiness(catalog_path: str | Path) -> ChoiceStockReadiness:
    normalized_path = str(catalog_path or "").strip()
    if not normalized_path:
        return choice_stock_readiness_missing("")
    path = Path(normalized_path)
    if not path.exists():
        return choice_stock_readiness_missing(str(path))

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        catalog = ChoiceStockCatalogAsset.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return _incomplete_readiness(
            catalog_path=str(path),
            unconfirmed_fields=[_summarize_error(exc)],
        )

    return build_choice_stock_readiness(catalog=catalog, catalog_path=str(path))


def build_choice_stock_readiness(
    *,
    catalog: ChoiceStockCatalogAsset,
    catalog_path: str,
) -> ChoiceStockReadiness:
    confirmed_families = {
        entry.input_family
        for entry in catalog.fields
        if entry.required and _entry_is_confirmed(entry)
    }
    missing_families = [
        family for family in CHOICE_STOCK_REQUIRED_INPUT_FAMILIES if family not in confirmed_families
    ]
    unconfirmed_fields = [
        f"{entry.input_family}:{entry.field_key}"
        for entry in catalog.fields
        if entry.required and not _entry_is_confirmed(entry)
    ]

    if missing_families:
        return _incomplete_readiness(
            catalog_path=catalog_path,
            missing_input_families=missing_families,
            unconfirmed_fields=unconfirmed_fields,
        )

    return ChoiceStockReadiness(
        ready=True,
        status="ready",
        catalog_path=catalog_path,
        missing_input_families=[],
        unconfirmed_fields=[],
        message="Choice stock catalog is confirmed for required Livermore stock input families.",
    )


def choice_stock_readiness_missing(catalog_path: str) -> ChoiceStockReadiness:
    return ChoiceStockReadiness(
        ready=False,
        status="missing_catalog",
        catalog_path=catalog_path,
        missing_input_families=list(CHOICE_STOCK_REQUIRED_INPUT_FAMILIES),
        message=(
            "Choice stock catalog is missing; required input families are blocked: "
            f"{_format_families(CHOICE_STOCK_REQUIRED_INPUT_FAMILIES)}."
        ),
    )


def _incomplete_readiness(
    *,
    catalog_path: str,
    missing_input_families: list[ChoiceStockInputFamily] | None = None,
    unconfirmed_fields: list[str] | None = None,
) -> ChoiceStockReadiness:
    missing = missing_input_families or list(CHOICE_STOCK_REQUIRED_INPUT_FAMILIES)
    fields = unconfirmed_fields or []
    return ChoiceStockReadiness(
        ready=False,
        status="incomplete_catalog",
        catalog_path=catalog_path,
        missing_input_families=missing,
        unconfirmed_fields=fields,
        message=(
            "Choice stock catalog is incomplete; missing or unconfirmed required input families: "
            f"{_format_families(missing)}."
        ),
    )


def _format_families(families: tuple[ChoiceStockInputFamily, ...] | list[ChoiceStockInputFamily]) -> str:
    return ", ".join(families)


def _entry_is_confirmed(entry: ChoiceStockCatalogEntry) -> bool:
    return (
        entry.confirmed
        and bool(entry.vendor_indicator.strip())
        and bool(entry.confirmation_source.strip())
        and bool(entry.confirmed_at.strip())
    )


def _summarize_error(exc: Exception) -> str:
    first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return f"catalog_validation:{first_line}"
