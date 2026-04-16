from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.app.repositories.currency_codes import normalize_currency_code
from backend.app.schemas.macro_vendor import ChoiceMacroCatalogAsset

_FORMAL_MIDDLE_RATE_PREFIX = "中间价:"
_FORMAL_PAIR_SEPARATOR = "兑"
_CNY_NAME = "人民币"


@dataclass(frozen=True)
class FormalFxCandidate:
    series_id: str
    series_name: str
    vendor_series_code: str
    base_currency: str
    quote_currency: str
    invert_result: bool

    @property
    def pair_label(self) -> str:
        return f"{self.base_currency}/{self.quote_currency}"


def load_choice_fx_catalog_asset(*, catalog_path: Path) -> ChoiceMacroCatalogAsset:
    if not catalog_path.exists():
        raise FileNotFoundError(f"Choice FX catalog file not found: {catalog_path}")
    return ChoiceMacroCatalogAsset.model_validate_json(catalog_path.read_text(encoding="utf-8"))


def discover_formal_fx_candidates(*, catalog_path: Path) -> list[FormalFxCandidate]:
    asset = load_choice_fx_catalog_asset(catalog_path=catalog_path)
    discovered: dict[str, FormalFxCandidate] = {}
    for batch in asset.batches:
        for series in batch.series:
            candidate = parse_formal_fx_candidate(
                series_id=series.series_id,
                series_name=series.series_name,
                vendor_series_code=series.vendor_series_code,
            )
            if candidate is None:
                continue
            discovered[candidate.vendor_series_code] = candidate
    return sorted(discovered.values(), key=lambda item: item.vendor_series_code)


def parse_formal_fx_candidate(
    *,
    series_id: str,
    series_name: str,
    vendor_series_code: str,
) -> FormalFxCandidate | None:
    if not series_name.startswith(_FORMAL_MIDDLE_RATE_PREFIX):
        return None
    pair_text = series_name.split(":", 1)[1].strip()
    if _FORMAL_PAIR_SEPARATOR not in pair_text:
        return None
    left_name, right_name = [part.strip() for part in pair_text.split(_FORMAL_PAIR_SEPARATOR, 1)]
    if not left_name or not right_name:
        return None

    if right_name == _CNY_NAME:
        base_currency = normalize_currency_code(left_name)
        invert_result = False
    elif left_name == _CNY_NAME:
        base_currency = normalize_currency_code(right_name)
        invert_result = True
    else:
        return None

    if not base_currency or base_currency == "CNY":
        return None

    return FormalFxCandidate(
        series_id=series_id,
        series_name=series_name,
        vendor_series_code=vendor_series_code,
        base_currency=base_currency,
        quote_currency="CNY",
        invert_result=invert_result,
    )


def classify_fx_series_group(series_name: str) -> str | None:
    if series_name.startswith(_FORMAL_MIDDLE_RATE_PREFIX):
        return "middle_rate"
    if "掉期" in series_name or "C-Swap" in series_name or "Swap" in series_name:
        return "fx_swap_curve"
    if "人民币指数" in series_name or "汇率预估指数" in series_name or "汇率指数" in series_name:
        return "fx_index"
    return None
