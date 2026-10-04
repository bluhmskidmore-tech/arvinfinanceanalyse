"""Deterministic frozen-version tuple for the stock-analysis current-rule cohort.

The builder deliberately derives formula/rule versions from the live code and
derives source versions only from persisted PIT source-receipt identities.  It
does not accept caller-supplied overrides for governed constants.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from backend.app.core_finance import cycle_macro_score, gate_macro_overlay
from backend.app.core_finance.livermore_stock_candidates import (
    EXP3B_STOCK_CANDIDATE_POLICY,
)
from backend.app.core_finance.livermore_stock_candidates import (
    FORMULA_VERSION as STOCK_CANDIDATE_FORMULA_VERSION,
)
from backend.app.core_finance.matched_baseline import (
    FORMULA_VERSION as MATCHED_BASELINE_FORMULA_VERSION,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    APPROVED_AUTHORITY_STATUS,
    validate_stock_analysis_calendar_receipt,
)
from backend.app.governance.stock_analysis_current_rule_certificate import (
    ALLOWED_DECISION_METRIC_BASIS,
    CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
    REQUIRED_VERSION_TUPLE_FIELDS,
)
from backend.app.repositories.choice_stock_adapter import ChoiceStockCatalogAsset
from backend.app.services.livermore_signal_confluence_service import (
    LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
)
from backend.app.services.market_data_livermore_service import (
    RULE_VERSION as MARKET_DATA_LIVERMORE_RULE_VERSION,
)
from backend.app.tasks import livermore_candidate_history_materialize
from pydantic import ValidationError

SOURCE_RECEIPT_KIND = "pit_source_availability_v1"
SOURCE_RECEIPT_SCHEMA_VERSION = 1
SOURCE_VERSION_CONTRACT = "stock-analysis-current-rule-source-family-v1"
MARKET_GATE_CONTRACT = "stock-analysis-current-rule-market-gate-v1"
MACRO_FORMULA_CONTRACT = "stock-analysis-current-rule-macro-formula-v1"

CANDIDATE_SOURCE_TABLE_PREFIX = "choice_stock_"
ADJUSTMENT_FACTOR_TABLE = "stock_adjustment_factor"
OBSERVATION_TABLE = "choice_stock_daily_observation"
EXECUTION_MATCHED_REQUIRED_TABLES = frozenset({OBSERVATION_TABLE, ADJUSTMENT_FACTOR_TABLE})
MACRO_SOURCE_TABLE_FRAGMENTS = ("macro", "market", "gate")

_SOURCE_KEY_FIELDS = (
    "table",
    "source_version",
    "vendor_version",
    "rule_version",
    "run_id",
)
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


class CurrentRuleVersionTupleError(ValueError):
    """Raised when governed evidence cannot produce a frozen version tuple."""


def build_stock_analysis_current_rule_version_tuple(
    *,
    approved_calendar_receipt: Mapping[str, object],
    source_availability_receipts: Sequence[Mapping[str, object]],
    choice_catalog_json: str | bytes | Mapping[str, object],
    theme_overlay_fingerprint: str,
) -> dict[str, Any]:
    """Build the complete, deterministic current-rule version tuple.

    Source versions are domain-separated hashes of the normalized source keys
    attested by the supplied receipts.  Receipt ordering and source-row ordering
    therefore cannot change the result.
    """

    _validate_approved_calendar_receipt(approved_calendar_receipt)
    source_keys = _normalize_source_receipt_keys(source_availability_receipts)
    source_versions = _build_source_family_versions(source_keys)

    version_tuple: dict[str, Any] = {
        "candidate_rule_version": livermore_candidate_history_materialize.RULE_VERSION,
        "stock_candidate_selection_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
        "candidate_outcome_formula_version": livermore_candidate_history_materialize.FORMULA_VERSION,
        "execution_formula_version": livermore_candidate_history_materialize.EXECUTION_FORMULA_VERSION,
        "matched_baseline_formula_version": MATCHED_BASELINE_FORMULA_VERSION,
        "market_gate_rule_version": _market_gate_contract_fingerprint(),
        "signal_confluence_rule_version": LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
        "macro_formula_version": _macro_formula_contract_fingerprint(),
        **source_versions,
        "theme_overlay_fingerprint": _sha256_text(
            theme_overlay_fingerprint,
            field_name="theme_overlay_fingerprint",
        ),
        "choice_catalog_fingerprint": _choice_catalog_fingerprint(choice_catalog_json),
        "stock_candidate_selection_policy": EXP3B_STOCK_CANDIDATE_POLICY,
        "decision_metric_basis": ALLOWED_DECISION_METRIC_BASIS,
        "coverage_authority_mode": CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
        "strict_coverage": True,
        "fallback_covered": False,
    }
    if tuple(version_tuple) != REQUIRED_VERSION_TUPLE_FIELDS:
        raise AssertionError("version tuple fields drifted from the certificate contract")
    return version_tuple


def validate_stock_analysis_current_rule_version_tuple(
    version_tuple: Mapping[str, object],
) -> tuple[bool, tuple[str, ...]]:
    """Validate a persisted tuple against the current code-level contract."""

    errors: list[str] = []
    if not isinstance(version_tuple, Mapping):
        return False, ("version_tuple must be a mapping",)

    missing = [field for field in REQUIRED_VERSION_TUPLE_FIELDS if field not in version_tuple]
    unexpected = sorted(set(version_tuple).difference(REQUIRED_VERSION_TUPLE_FIELDS))
    if missing:
        errors.append("version_tuple missing required fields: " + ", ".join(missing))
    if unexpected:
        errors.append("version_tuple contains unexpected fields: " + ", ".join(unexpected))
    if missing:
        return False, tuple(errors)

    expected_values: dict[str, object] = {
        "candidate_rule_version": livermore_candidate_history_materialize.RULE_VERSION,
        "stock_candidate_selection_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
        "candidate_outcome_formula_version": livermore_candidate_history_materialize.FORMULA_VERSION,
        "execution_formula_version": livermore_candidate_history_materialize.EXECUTION_FORMULA_VERSION,
        "matched_baseline_formula_version": MATCHED_BASELINE_FORMULA_VERSION,
        "market_gate_rule_version": _market_gate_contract_fingerprint(),
        "signal_confluence_rule_version": LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
        "macro_formula_version": _macro_formula_contract_fingerprint(),
        "stock_candidate_selection_policy": EXP3B_STOCK_CANDIDATE_POLICY,
        "decision_metric_basis": ALLOWED_DECISION_METRIC_BASIS,
        "coverage_authority_mode": CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
        "strict_coverage": True,
        "fallback_covered": False,
    }
    for field_name, expected in expected_values.items():
        if version_tuple.get(field_name) != expected:
            errors.append(f"version_tuple.{field_name} does not match current contract")

    hash_fields = (
        "candidate_source_version",
        "execution_source_version",
        "matched_baseline_source_version",
        "macro_source_version",
        "theme_overlay_fingerprint",
        "choice_catalog_fingerprint",
    )
    for field_name in hash_fields:
        value = version_tuple.get(field_name)
        if not isinstance(value, str) or len(value) != 64 or any(character not in _HEX_DIGITS for character in value):
            errors.append(f"version_tuple.{field_name} must be a 64-character sha256 hex string")

    for field_name in REQUIRED_VERSION_TUPLE_FIELDS:
        if field_name in {"strict_coverage", "fallback_covered"}:
            if not isinstance(version_tuple.get(field_name), bool):
                errors.append(f"version_tuple.{field_name} must be a boolean")
        elif not isinstance(version_tuple.get(field_name), str) or not str(version_tuple[field_name]).strip():
            errors.append(f"version_tuple.{field_name} must be a non-empty string")
    return not errors, tuple(errors)


def _validate_approved_calendar_receipt(receipt: Mapping[str, object]) -> None:
    if not isinstance(receipt, Mapping):
        raise CurrentRuleVersionTupleError("approved_calendar_receipt must be a mapping")
    valid, errors = validate_stock_analysis_calendar_receipt(receipt)
    if not valid:
        detail = "; ".join(errors) or "unknown validation error"
        raise CurrentRuleVersionTupleError(f"approved_calendar_receipt is invalid: {detail}")
    if receipt.get("authority_status") != APPROVED_AUTHORITY_STATUS:
        raise CurrentRuleVersionTupleError("approved_calendar_receipt authority_status must equal approved")
    if receipt.get("certification_allowed") is not True:
        raise CurrentRuleVersionTupleError("approved_calendar_receipt must allow certification")


def _normalize_source_receipt_keys(
    receipts: Sequence[Mapping[str, object]],
) -> tuple[tuple[str, str, str, str, str], ...]:
    if isinstance(receipts, (str, bytes, bytearray)) or not isinstance(receipts, Sequence):
        raise CurrentRuleVersionTupleError("source_availability_receipts must be a sequence")
    if not receipts:
        raise CurrentRuleVersionTupleError("source_availability_receipts must not be empty")

    normalized: set[tuple[str, str, str, str, str]] = set()
    for receipt_index, receipt in enumerate(receipts):
        if not isinstance(receipt, Mapping):
            raise CurrentRuleVersionTupleError(f"source_availability_receipts[{receipt_index}] must be a mapping")
        if receipt.get("schema_version") != SOURCE_RECEIPT_SCHEMA_VERSION:
            raise CurrentRuleVersionTupleError(
                f"source_availability_receipts[{receipt_index}].schema_version must equal 1"
            )
        if receipt.get("receipt_kind") != SOURCE_RECEIPT_KIND:
            raise CurrentRuleVersionTupleError(f"source_availability_receipts[{receipt_index}].receipt_kind mismatch")
        _timezone_datetime_text(
            receipt.get("captured_at"),
            field_name=f"source_availability_receipts[{receipt_index}].captured_at",
        )
        sources = receipt.get("sources")
        if not isinstance(sources, list) or not sources:
            raise CurrentRuleVersionTupleError(
                f"source_availability_receipts[{receipt_index}].sources must be a non-empty list"
            )
        for source_index, source in enumerate(sources):
            field_prefix = f"source_availability_receipts[{receipt_index}].sources[{source_index}]"
            if not isinstance(source, Mapping):
                raise CurrentRuleVersionTupleError(f"{field_prefix} must be a mapping")
            key = (
                _required_text(source.get("table"), field_name=f"{field_prefix}.table"),
                _required_text(
                    source.get("source_version"),
                    field_name=f"{field_prefix}.source_version",
                ),
                _optional_text(
                    source.get("vendor_version"),
                    field_name=f"{field_prefix}.vendor_version",
                ),
                _optional_text(
                    source.get("rule_version"),
                    field_name=f"{field_prefix}.rule_version",
                ),
                _required_text(source.get("run_id"), field_name=f"{field_prefix}.run_id"),
            )
            _date_text(
                source.get("available_at"),
                field_name=f"{field_prefix}.available_at",
            )
            if key in normalized:
                raise CurrentRuleVersionTupleError("duplicate source availability key across receipts")
            normalized.add(key)
    return tuple(sorted(normalized))


def _build_source_family_versions(
    source_keys: Sequence[tuple[str, str, str, str, str]],
) -> dict[str, str]:
    candidate_keys = tuple(
        key
        for key in source_keys
        if key[0].startswith(CANDIDATE_SOURCE_TABLE_PREFIX) and key[0] != ADJUSTMENT_FACTOR_TABLE
    )
    execution_matched_keys = tuple(key for key in source_keys if key[0] in EXECUTION_MATCHED_REQUIRED_TABLES)
    execution_tables = {key[0] for key in execution_matched_keys}
    missing_execution_tables = sorted(EXECUTION_MATCHED_REQUIRED_TABLES.difference(execution_tables))
    macro_keys = tuple(
        key for key in source_keys if any(fragment in key[0].lower() for fragment in MACRO_SOURCE_TABLE_FRAGMENTS)
    )

    if not candidate_keys:
        raise CurrentRuleVersionTupleError("candidate source family requires at least one choice_stock_* source")
    if missing_execution_tables:
        raise CurrentRuleVersionTupleError(
            "execution/matched source family missing required tables: " + ", ".join(missing_execution_tables)
        )
    if not macro_keys:
        raise CurrentRuleVersionTupleError("macro source family requires at least one macro/market/gate source")

    return {
        "candidate_source_version": _source_family_fingerprint(
            family="candidate",
            keys=candidate_keys,
        ),
        "execution_source_version": _source_family_fingerprint(
            family="execution",
            keys=execution_matched_keys,
        ),
        "matched_baseline_source_version": _source_family_fingerprint(
            family="matched_baseline",
            keys=execution_matched_keys,
        ),
        "macro_source_version": _source_family_fingerprint(
            family="macro",
            keys=macro_keys,
        ),
    }


def _source_family_fingerprint(
    *,
    family: str,
    keys: Sequence[tuple[str, str, str, str, str]],
) -> str:
    return _canonical_sha256(
        {
            "contract": SOURCE_VERSION_CONTRACT,
            "source_family": family,
            "source_keys": [dict(zip(_SOURCE_KEY_FIELDS, key, strict=True)) for key in sorted(keys)],
        }
    )


def _market_gate_contract_fingerprint() -> str:
    return _canonical_sha256(
        {
            "contract": MARKET_GATE_CONTRACT,
            "market_data_livermore_rule_version": MARKET_DATA_LIVERMORE_RULE_VERSION,
            "gate_macro_overlay_formula_version": (gate_macro_overlay.GATE_MACRO_OVERLAY_FORMULA_VERSION),
        }
    )


def _macro_formula_contract_fingerprint() -> str:
    return _canonical_sha256(
        {
            "contract": MACRO_FORMULA_CONTRACT,
            "series_ids": {
                "pmi": cycle_macro_score.PMI_SERIES_ID,
                "credit_impulse_primary": (cycle_macro_score.SOCIAL_FINANCING_YOY_SERIES_ID),
                "credit_impulse_fallback": cycle_macro_score.M2_YOY_SERIES_ID,
                "price_spread_pe": cycle_macro_score.CSI300_PE_SERIES_ID,
                "price_spread_cn10y": cycle_macro_score.CN10Y_SERIES_ID,
            },
            "weights": {
                "pmi": cycle_macro_score.MACRO_WEIGHT_PMI,
                "credit_impulse": cycle_macro_score.MACRO_WEIGHT_CREDIT_IMPULSE,
                "price_spread": cycle_macro_score.MACRO_WEIGHT_PRICE_SPREAD,
            },
            "gate_macro_overlay_formula_version": (gate_macro_overlay.GATE_MACRO_OVERLAY_FORMULA_VERSION),
        }
    )


def _choice_catalog_fingerprint(
    choice_catalog_json: str | bytes | Mapping[str, object],
) -> str:
    parsed: object
    if isinstance(choice_catalog_json, bytes):
        try:
            text = choice_catalog_json.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CurrentRuleVersionTupleError("choice_catalog_json must be UTF-8 JSON") from exc
        parsed = _parse_json_object(text)
    elif isinstance(choice_catalog_json, str):
        parsed = _parse_json_object(choice_catalog_json)
    elif isinstance(choice_catalog_json, Mapping):
        parsed = dict(choice_catalog_json)
    else:
        raise CurrentRuleVersionTupleError("choice_catalog_json must be JSON text, bytes, or a mapping")

    if not isinstance(parsed, Mapping):
        raise CurrentRuleVersionTupleError("choice_catalog_json must contain a JSON object")
    try:
        ChoiceStockCatalogAsset.model_validate(parsed)
    except ValidationError as exc:
        raise CurrentRuleVersionTupleError(
            "choice_catalog_json does not satisfy the Choice stock catalog contract"
        ) from exc
    try:
        return _canonical_sha256(parsed)
    except (TypeError, ValueError) as exc:
        raise CurrentRuleVersionTupleError("choice_catalog_json must contain canonical JSON values") from exc


def _parse_json_object(value: str) -> object:
    try:
        return json.loads(
            value,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_non_finite_json_constant,
        )
    except (json.JSONDecodeError, UnicodeError, ValueError) as exc:
        raise CurrentRuleVersionTupleError("choice_catalog_json must be valid JSON without duplicate keys") from exc


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON constant: {value}")


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _sha256_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise CurrentRuleVersionTupleError(f"{field_name} must be a sha256 string")
    normalized = value.strip()
    if len(normalized) != 64 or any(character not in _HEX_DIGITS for character in normalized):
        raise CurrentRuleVersionTupleError(f"{field_name} must be a 64-character sha256 hex string")
    return normalized.lower()


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CurrentRuleVersionTupleError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: object, *, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CurrentRuleVersionTupleError(f"{field_name} must be a string when set")
    return value.strip()


def _timezone_datetime_text(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CurrentRuleVersionTupleError(f"{field_name} must be an ISO-8601 datetime") from exc
    if parsed.utcoffset() is None:
        raise CurrentRuleVersionTupleError(f"{field_name} must include a timezone")
    return normalized


def _date_text(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name)
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise CurrentRuleVersionTupleError(f"{field_name} must be an ISO-8601 date") from exc
    if parsed.isoformat() != normalized:
        raise CurrentRuleVersionTupleError(f"{field_name} must use canonical YYYY-MM-DD form")
    return normalized
