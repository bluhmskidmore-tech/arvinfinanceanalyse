from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ChoiceStockInputFamily = Literal[
    "sector_membership",
    "sector_strength",
    "stock_universe",
    "stock_ohlcv",
    "stock_status",
    "limit_up_quality",
    "concept_membership",
    "intraday_movement",
]
ChoiceStockCall = Literal["css", "csd", "ctr", "sector"]
ChoiceStockCatalogStatus = Literal["missing_catalog", "incomplete_catalog", "ready"]
ChoiceStockOptionalInputStatus = Literal["catalog_unconfirmed", "confirmed"]
ChoiceRequestOptionValue: TypeAlias = str | int | float | bool

CHOICE_STOCK_REQUIRED_INPUT_FAMILIES: tuple[ChoiceStockInputFamily, ...] = (
    "sector_membership",
    "sector_strength",
    "stock_universe",
    "stock_ohlcv",
    "stock_status",
    "limit_up_quality",
)
CHOICE_STOCK_OPTIONAL_INPUT_FAMILIES: tuple[ChoiceStockInputFamily, ...] = (
    "concept_membership",
    "intraday_movement",
)
CHOICE_STOCK_HISTORY_CALENDAR_DAYS = 220
STOCK_FACTOR_INPUT_RULE_VERSION = "rv_choice_stock_factor_percent_units_adjusted_prices_v2"


@dataclass(frozen=True)
class StockDailyPriceBasisEvidence:
    source_version: str = ""
    stock_codes: frozenset[str] = frozenset()
    start_date: date | None = None
    end_date: date | None = None


def stock_daily_price_basis_evidence(
    *, source_version: object, request_audits: list[dict[str, object]],
) -> StockDailyPriceBasisEvidence:
    """Parse a historical run once; invalid evidence does not parse large code lists."""
    source = str(source_version or "")
    matching = [
        audit for audit in request_audits
        if audit.get("input_family") == "stock_ohlcv"
        and audit.get("field_key") == "daily_ohlcv_amount"
        and audit.get("status") == "completed"
        and str(audit.get("source_version") or "") == source
    ]
    empty = StockDailyPriceBasisEvidence()
    if len(matching) != 1:
        return empty
    audit = matching[0]
    if str(audit.get("call") or "").lower() != "csd":
        return empty
    try:
        options = json.loads(str(audit.get("request_options_json") or ""), object_pairs_hook=lambda pairs: pairs)
        if not isinstance(options, list) or any(
            not isinstance(pair, tuple) or len(pair) != 2 or not isinstance(pair[0], str)
            for pair in options
        ):
            return empty
        flags = [str(value).strip() for key, value in options if key.lower() == "adjustflag"]
        if len(flags) != 1 or flags[0] != "1":
            return empty
        # OHLCV audits can contain the whole A-share universe. Decode these
        # arguments only after the small options object proves raw prices.
        arguments = json.loads(str(audit.get("request_arguments_json") or ""))
        if not isinstance(arguments, list) or len(arguments) != 4:
            return empty
        indicators = {value.strip().upper() for value in str(arguments[1]).split(",")}
        if not {"OPEN", "HIGH", "LOW", "CLOSE"}.issubset(indicators):
            return empty
        start_date = date.fromisoformat(str(arguments[2]))
        end_date = date.fromisoformat(str(arguments[3]))
        if start_date > end_date:
            return empty
        return StockDailyPriceBasisEvidence(
            source_version=source, stock_codes=frozenset(str(arguments[0]).split(",")),
            start_date=start_date, end_date=end_date,
        )
    except (TypeError, ValueError):
        return empty


def stock_daily_price_basis(
    *,
    vendor_version: object,
    stock_code: str,
    trade_date: str,
    source_version: object,
    request_audits: list[dict[str, object]],
    request_evidence: StockDailyPriceBasisEvidence | None = None,
) -> str:
    """Recognize raw prices only from vendor or historical request evidence.

    A current catalog cannot establish the basis of already-landed native rows.
    Choice AdjustFlag 1/2/3 means raw/backward/forward adjusted (SDK PDF p13).
    """
    vendor = str(vendor_version or "").strip()
    if re.fullmatch(r"vv_choice_tushare_stock_\d{8}_[0-9a-f]{12}", vendor) or re.fullmatch(
        r"vv_livermore_supplement_tushare_sina_\d{8}_[0-9a-f]{12}", vendor
    ):
        return "raw"
    if not re.fullmatch(r"vv_choice_stock_\d{8}_[0-9a-f]{12}", vendor):
        return "unconfirmed"
    evidence = request_evidence if request_evidence is not None else stock_daily_price_basis_evidence(
        source_version=source_version, request_audits=request_audits,
    )
    if (evidence.start_date is None or evidence.end_date is None
            or evidence.source_version != str(source_version or "") or stock_code not in evidence.stock_codes):
        return "unconfirmed"
    try:
        if not evidence.start_date <= date.fromisoformat(trade_date) <= evidence.end_date:
            return "unconfirmed"
    except (TypeError, ValueError):
        return "unconfirmed"
    return "raw"


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
    request_options: dict[str, ChoiceRequestOptionValue] = Field(default_factory=dict)
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
    optional_input_status: dict[ChoiceStockInputFamily, ChoiceStockOptionalInputStatus] = Field(default_factory=dict)
    message: str


class ChoiceStockRequestPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_family: ChoiceStockInputFamily
    field_key: str
    vendor_indicator: str
    call: ChoiceStockCall
    request_arguments: list[str] = Field(default_factory=list)
    request_options: dict[str, ChoiceRequestOptionValue] = Field(default_factory=dict)
    request_options_text: str = ""


class ChoiceStockRequestPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    status: ChoiceStockCatalogStatus
    catalog_path: str
    vendor_name: Literal["choice"] = "choice"
    requests: list[ChoiceStockRequestPlanItem] = Field(default_factory=list)
    missing_input_families: list[ChoiceStockInputFamily] = Field(default_factory=list)
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


def load_choice_stock_request_plan(
    catalog_path: str | Path,
    *,
    as_of_date: str,
    history_start_date: str | None = None,
) -> ChoiceStockRequestPlan:
    normalized_path = str(catalog_path or "").strip()
    readiness = load_choice_stock_readiness(normalized_path)
    if not readiness.ready:
        return ChoiceStockRequestPlan(
            ready=False,
            status=readiness.status,
            catalog_path=readiness.catalog_path,
            missing_input_families=readiness.missing_input_families,
            message=readiness.message,
        )

    path = Path(normalized_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        catalog = ChoiceStockCatalogAsset.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError):
        return ChoiceStockRequestPlan(
            ready=False,
            status="incomplete_catalog",
            catalog_path=str(path),
            missing_input_families=list(CHOICE_STOCK_REQUIRED_INPUT_FAMILIES),
            message=(
                "Choice stock catalog is incomplete; request plan could not be resolved "
                "from the configured catalog."
            ),
        )

    requests = [
        _build_request_plan_item(
            entry=entry,
            as_of_date=as_of_date,
            history_start_date=history_start_date,
        )
        for entry in catalog.fields
        if _entry_is_confirmed(entry)
    ]
    return ChoiceStockRequestPlan(
        ready=True,
        status="ready",
        catalog_path=str(path),
        requests=requests,
        missing_input_families=[],
        message=f"Choice stock request plan is ready for {as_of_date}.",
    )


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
    optional_input_status = {
        family: _optional_input_status_for_family(catalog.fields, family)
        for family in CHOICE_STOCK_OPTIONAL_INPUT_FAMILIES
    }

    if missing_families:
        return _incomplete_readiness(
            catalog_path=catalog_path,
            missing_input_families=missing_families,
            unconfirmed_fields=unconfirmed_fields,
            optional_input_status=optional_input_status,
        )

    return ChoiceStockReadiness(
        ready=True,
        status="ready",
        catalog_path=catalog_path,
        missing_input_families=[],
        unconfirmed_fields=[],
        optional_input_status=optional_input_status,
        message="Choice stock catalog is confirmed for required Livermore stock input families.",
    )


def choice_stock_readiness_missing(catalog_path: str) -> ChoiceStockReadiness:
    return ChoiceStockReadiness(
        ready=False,
        status="missing_catalog",
        catalog_path=catalog_path,
        missing_input_families=list(CHOICE_STOCK_REQUIRED_INPUT_FAMILIES),
        optional_input_status={
            family: "catalog_unconfirmed" for family in CHOICE_STOCK_OPTIONAL_INPUT_FAMILIES
        },
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
    optional_input_status: dict[ChoiceStockInputFamily, ChoiceStockOptionalInputStatus] | None = None,
) -> ChoiceStockReadiness:
    missing = missing_input_families or list(CHOICE_STOCK_REQUIRED_INPUT_FAMILIES)
    fields = unconfirmed_fields or []
    return ChoiceStockReadiness(
        ready=False,
        status="incomplete_catalog",
        catalog_path=catalog_path,
        missing_input_families=missing,
        unconfirmed_fields=fields,
        optional_input_status=optional_input_status
        or {family: "catalog_unconfirmed" for family in CHOICE_STOCK_OPTIONAL_INPUT_FAMILIES},
        message=(
            "Choice stock catalog is incomplete; missing or unconfirmed required input families: "
            f"{_format_families(missing)}."
        ),
    )


def _format_families(families: tuple[ChoiceStockInputFamily, ...] | list[ChoiceStockInputFamily]) -> str:
    return ", ".join(families)


def _build_request_plan_item(
    *,
    entry: ChoiceStockCatalogEntry,
    as_of_date: str,
    history_start_date: str | None = None,
) -> ChoiceStockRequestPlanItem:
    resolved_options = {
        key: _resolve_request_placeholder(value, as_of_date=as_of_date)
        for key, value in entry.request_options.items()
    }
    return ChoiceStockRequestPlanItem(
        input_family=entry.input_family,
        field_key=entry.field_key,
        vendor_indicator=entry.vendor_indicator,
        call=entry.call,
        request_arguments=_request_arguments_for_entry(
            entry,
            as_of_date=as_of_date,
            history_start_date=history_start_date,
        ),
        request_options=resolved_options,
        request_options_text=_serialize_request_options(resolved_options),
    )


def _request_arguments_for_entry(
    entry: ChoiceStockCatalogEntry,
    *,
    as_of_date: str,
    history_start_date: str | None = None,
) -> list[str]:
    if entry.call == "sector":
        return [entry.vendor_indicator, as_of_date]
    if entry.call == "css":
        return ["__STOCK_CODES__", entry.vendor_indicator]
    if entry.call == "csd":
        return [
            "__STOCK_CODES__",
            entry.vendor_indicator,
            history_start_date or choice_stock_history_start_date(as_of_date),
            as_of_date,
        ]
    if entry.call == "ctr":
        return [entry.vendor_indicator, ""]
    return []


def _resolve_request_placeholder(value: ChoiceRequestOptionValue, *, as_of_date: str) -> ChoiceRequestOptionValue:
    if isinstance(value, str):
        return value.replace("__AS_OF_DATE__", as_of_date)
    return value


def choice_stock_history_start_date(as_of_date: str) -> str:
    return (date.fromisoformat(as_of_date) - timedelta(days=CHOICE_STOCK_HISTORY_CALENDAR_DAYS)).isoformat()


def _serialize_request_options(options: dict[str, ChoiceRequestOptionValue]) -> str:
    parts = []
    for key, value in options.items():
        normalized = _serialize_request_option_value(value)
        parts.append(f"{key}={normalized}")
    return ",".join(parts)


def _serialize_request_option_value(value: ChoiceRequestOptionValue) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _entry_is_confirmed(entry: ChoiceStockCatalogEntry) -> bool:
    return (
        entry.confirmed
        and bool(entry.vendor_indicator.strip())
        and bool(entry.confirmation_source.strip())
        and bool(entry.confirmed_at.strip())
    )


def choice_stock_optional_input_status(
    readiness: ChoiceStockReadiness,
    input_family: ChoiceStockInputFamily,
) -> ChoiceStockOptionalInputStatus:
    return readiness.optional_input_status.get(input_family, "catalog_unconfirmed")


def _optional_input_status_for_family(
    fields: list[ChoiceStockCatalogEntry],
    input_family: ChoiceStockInputFamily,
) -> ChoiceStockOptionalInputStatus:
    matching = [entry for entry in fields if entry.input_family == input_family and not entry.required]
    if any(_entry_is_confirmed(entry) for entry in matching):
        return "confirmed"
    return "catalog_unconfirmed"


def _summarize_error(exc: Exception) -> str:
    first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return f"catalog_validation:{first_line}"
