from __future__ import annotations

from pathlib import Path
from typing import Literal

from backend.app.schemas.macro_vendor import ChoiceMacroCatalogAsset
from pydantic import BaseModel, ConfigDict, Field

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CHOICE_DATA_OPPORTUNITY_CATALOG = _REPO_ROOT / "config" / "choice_data_opportunities.json"
DEFAULT_CHOICE_MACRO_CATALOG = _REPO_ROOT / "config" / "choice_macro_catalog.json"
DEFAULT_CHOICE_FUNDING_CONFIRMED_CANDIDATES = (
    _REPO_ROOT / "config" / "choice_funding_confirmed_candidates.json"
)

ChoiceDataPriority = Literal["P0", "P1", "P2", "P3", "avoid"]
ChoiceDataDomain = Literal[
    "fixed_income_macro",
    "bond_events",
    "equity_strategy",
    "calendar_metadata",
    "operations_guardrail",
]
ChoiceDataImplementationState = Literal[
    "landed",
    "partially_landed",
    "candidate",
    "needs_entitlement_probe",
    "avoid",
]
ChoiceApiWrapperStatus = Literal["available", "missing_wrapper"]
ChoiceFundingProbeMode = Literal["date_slice", "latest"]

_CHOICE_CLIENT_WRAPPED_FUNCTIONS = frozenset(
    {
        "cnq",
        "cnqcancel",
        "csd",
        "cfn",
        "cfnquery",
        "css",
        "ctr",
        "edb",
        "edbquery",
        "fut_get_transaction_rankings",
        "sector",
        "tradedates",
    }
)
_FUNDING_KEYWORDS = (
    "dr007",
    "dr001",
    "r007",
    "r001",
    "shibor",
    "lpr",
    "mlf",
    "omo",
    "repo",
    "ncd",
    "\u540c\u4e1a",
    "\u56de\u8d2d",
    "\u8d28\u62bc",
    "\u62c6\u501f",
)


class ChoiceDataOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    priority: ChoiceDataPriority
    domain: ChoiceDataDomain
    title: str
    choice_api_functions: list[str] = Field(min_length=1)
    data_families: list[str] = Field(min_length=1)
    business_surfaces: list[str] = Field(min_length=1)
    landing_targets: list[str] = Field(default_factory=list)
    existing_evidence: list[str] = Field(default_factory=list)
    implementation_state: ChoiceDataImplementationState = "candidate"
    next_step: str
    caveats: list[str] = Field(default_factory=list)


class ChoiceDataOpportunityCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version: str
    vendor_name: Literal["choice"] = "choice"
    generated_from: str
    opportunities: list[ChoiceDataOpportunity] = Field(default_factory=list)


class ChoiceFundingMacroCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    series_name: str
    vendor_series_code: str
    batch_id: str
    frequency: str
    unit: str
    theme: str
    tags: list[str] = Field(default_factory=list)
    refresh_tier: str
    fetch_mode: str
    choice_api_function: Literal["edb"] = "edb"
    landing_targets: list[str] = Field(
        default_factory=lambda: ["fact_choice_macro_daily", "choice_market_snapshot"]
    )
    match_reason: str


class ChoiceFundingEdbProbeBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_index: int
    codes: list[str] = Field(min_length=1)
    series_ids: list[str] = Field(min_length=1)
    request_options: str
    probe_mode: ChoiceFundingProbeMode = "date_slice"


class ChoiceFundingEdbProbePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: Literal["choice_funding_conditions"] = "choice_funding_conditions"
    choice_api_function: Literal["edb"] = "edb"
    wrapper_status: ChoiceApiWrapperStatus
    as_of_date: str
    probe_mode: ChoiceFundingProbeMode = "date_slice"
    total_candidates: int
    landing_targets: list[str] = Field(
        default_factory=lambda: ["fact_choice_macro_daily", "choice_market_snapshot"]
    )
    batches: list[ChoiceFundingEdbProbeBatch] = Field(default_factory=list)


class ChoiceFundingConfirmedSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    series_name: str
    vendor_series_code: str
    frequency: str
    unit: str
    latest_date: str
    latest_value: float
    fetch_mode: ChoiceFundingProbeMode
    first_batch_action: str


class ChoiceFundingConfirmedGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    priority: ChoiceDataPriority
    business_use: str
    probe_result: str
    series: list[ChoiceFundingConfirmedSeries] = Field(default_factory=list)


class ChoiceFundingExcludedProbeHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    series_name: str
    latest_date: str
    reason: str


class ChoiceFundingSelectionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include: list[str] = Field(default_factory=list)
    exclude_from_first_batch: list[str] = Field(default_factory=list)


class ChoiceFundingConfirmedCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version: str
    vendor_name: Literal["choice"] = "choice"
    generated_from: str
    probe_as_of_date: str
    probe_mode: ChoiceFundingProbeMode
    write_performed: bool
    selection_policy: ChoiceFundingSelectionPolicy
    landing_targets: list[str] = Field(default_factory=list)
    candidate_groups: list[ChoiceFundingConfirmedGroup] = Field(default_factory=list)
    excluded_probe_hits: list[ChoiceFundingExcludedProbeHit] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)

    def first_batch_series(self) -> list[ChoiceFundingConfirmedSeries]:
        items: list[ChoiceFundingConfirmedSeries] = []
        for group in self.candidate_groups:
            for series in group.series:
                if series.first_batch_action == "candidate_for_landing":
                    items.append(series)
        return sorted(items, key=lambda item: item.series_id)


def load_choice_data_opportunity_catalog(
    catalog_path: str | Path | None = None,
) -> ChoiceDataOpportunityCatalog:
    path = Path(catalog_path) if catalog_path is not None else DEFAULT_CHOICE_DATA_OPPORTUNITY_CATALOG
    if not path.exists():
        raise FileNotFoundError(f"Choice data opportunity catalog file not found: {path}")

    catalog = ChoiceDataOpportunityCatalog.model_validate_json(path.read_text(encoding="utf-8"))
    _raise_for_duplicate_ids(catalog)
    return catalog


def load_choice_funding_confirmed_candidates(
    catalog_path: str | Path | None = None,
) -> ChoiceFundingConfirmedCatalog:
    path = (
        Path(catalog_path)
        if catalog_path is not None
        else DEFAULT_CHOICE_FUNDING_CONFIRMED_CANDIDATES
    )
    if not path.exists():
        raise FileNotFoundError(f"Choice funding confirmed candidates file not found: {path}")

    return ChoiceFundingConfirmedCatalog.model_validate_json(path.read_text(encoding="utf-8"))


def discover_choice_funding_macro_candidates(
    macro_catalog_path: str | Path | None = None,
) -> list[ChoiceFundingMacroCandidate]:
    path = Path(macro_catalog_path) if macro_catalog_path is not None else DEFAULT_CHOICE_MACRO_CATALOG
    if not path.exists():
        raise FileNotFoundError(f"Choice macro catalog file not found: {path}")

    asset = ChoiceMacroCatalogAsset.model_validate_json(path.read_text(encoding="utf-8"))
    candidates: dict[str, ChoiceFundingMacroCandidate] = {}
    for batch in asset.batches:
        for series in batch.series:
            match_reason = _funding_match_reason(
                series_name=series.series_name,
                series_id=series.series_id,
                theme=series.theme,
                tags=series.tags,
            )
            if match_reason is None:
                continue
            candidates[series.series_id] = ChoiceFundingMacroCandidate(
                series_id=series.series_id,
                series_name=series.series_name,
                vendor_series_code=series.vendor_series_code,
                batch_id=batch.batch_id,
                frequency=series.frequency,
                unit=series.unit,
                theme=series.theme,
                tags=series.tags,
                refresh_tier=batch.refresh_tier,
                fetch_mode=batch.fetch_mode,
                match_reason=match_reason,
            )
    return sorted(candidates.values(), key=lambda item: (item.batch_id, item.series_id))


def build_choice_funding_edb_probe_plan(
    macro_catalog_path: str | Path | None = None,
    *,
    as_of_date: str,
    chunk_size: int = 10,
    probe_mode: ChoiceFundingProbeMode = "date_slice",
) -> ChoiceFundingEdbProbePlan:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if probe_mode not in ("date_slice", "latest"):
        raise ValueError("probe_mode must be one of: date_slice, latest.")

    candidates = discover_choice_funding_macro_candidates(macro_catalog_path)
    batches = []
    for batch_index, start in enumerate(range(0, len(candidates), chunk_size), start=1):
        chunk = candidates[start : start + chunk_size]
        batches.append(
            ChoiceFundingEdbProbeBatch(
                batch_index=batch_index,
                codes=[item.vendor_series_code for item in chunk],
                series_ids=[item.series_id for item in chunk],
                request_options=_choice_edb_probe_options(as_of_date=as_of_date, probe_mode=probe_mode),
                probe_mode=probe_mode,
            )
        )

    return ChoiceFundingEdbProbePlan(
        wrapper_status="available",
        as_of_date=as_of_date,
        probe_mode=probe_mode,
        total_candidates=len(candidates),
        batches=batches,
    )


def list_choice_data_opportunities(
    catalog: ChoiceDataOpportunityCatalog,
    *,
    priority: ChoiceDataPriority | None = None,
    domain: ChoiceDataDomain | None = None,
    include_avoid: bool = False,
) -> list[ChoiceDataOpportunity]:
    items = []
    for item in catalog.opportunities:
        if not include_avoid and (item.priority == "avoid" or item.implementation_state == "avoid"):
            continue
        if priority is not None and item.priority != priority:
            continue
        if domain is not None and item.domain != domain:
            continue
        items.append(item)
    return sorted(items, key=lambda item: (item.priority, item.domain, item.opportunity_id))


def choice_api_wrapper_readiness(
    catalog: ChoiceDataOpportunityCatalog,
    *,
    opportunity_id: str,
) -> dict[str, ChoiceApiWrapperStatus]:
    opportunity = next(
        (item for item in catalog.opportunities if item.opportunity_id == opportunity_id),
        None,
    )
    if opportunity is None:
        raise ValueError(f"Unknown Choice data opportunity id: {opportunity_id}")

    return {
        function_name: (
            "available" if function_name in _CHOICE_CLIENT_WRAPPED_FUNCTIONS else "missing_wrapper"
        )
        for function_name in opportunity.choice_api_functions
    }


def _raise_for_duplicate_ids(catalog: ChoiceDataOpportunityCatalog) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in catalog.opportunities:
        if item.opportunity_id in seen:
            duplicates.add(item.opportunity_id)
        seen.add(item.opportunity_id)

    if duplicates:
        joined = ", ".join(sorted(duplicates))
        raise ValueError(f"Duplicate Choice data opportunity ids: {joined}")


def _choice_edb_probe_options(*, as_of_date: str, probe_mode: ChoiceFundingProbeMode) -> str:
    if probe_mode == "latest":
        options: dict[str, object] = {
            "IsLatest": 1,
            "RowIndex": 1,
            "Ispandas": 1,
            "RECVtimeout": 5,
        }
    else:
        options = {
            "IsLatest": 0,
            "StartDate": as_of_date,
            "EndDate": as_of_date,
            "Ispandas": 1,
            "RECVtimeout": 5,
        }
    return ",".join(
        f"{key}={_choice_request_option_value(value)}"
        for key, value in options.items()
    )


def _choice_request_option_value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _funding_match_reason(
    *,
    series_name: str,
    series_id: str,
    theme: str,
    tags: list[str],
) -> str | None:
    if theme == "money_liquidity":
        return "theme:money_liquidity"

    haystack = " ".join([series_id, series_name, theme, *tags]).lower()
    for keyword in _FUNDING_KEYWORDS:
        if keyword.lower() in haystack:
            return f"keyword:{keyword}"
    return None
