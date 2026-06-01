"""Regulatory DV01 inclusion rules for formal bond analytics rows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RegulatoryDv01ScopeRule:
    rule_id: str
    rule_version: str
    include: bool
    match_fields: dict[str, tuple[str, ...]]


DEFAULT_REGULATORY_DV01_SCOPE_RULE = RegulatoryDv01ScopeRule(
    rule_id="reg_dv01_include_all_formal_bond_analytics_v1",
    rule_version="v1",
    include=True,
    match_fields={},
)
DEFAULT_REGULATORY_DV01_SCOPE_RULES = (DEFAULT_REGULATORY_DV01_SCOPE_RULE,)


def row_in_regulatory_dv01_scope(
    row: dict[str, Any],
    rules: tuple[RegulatoryDv01ScopeRule, ...] = DEFAULT_REGULATORY_DV01_SCOPE_RULES,
) -> bool:
    included = False
    for rule in rules:
        if _matches(row, rule):
            if not rule.include:
                return False
            included = True
    return included


def _matches(row: dict[str, Any], rule: RegulatoryDv01ScopeRule) -> bool:
    if not rule.match_fields:
        return True
    return all(
        _normalized(row.get(field_name)) in {_normalized(value) for value in allowed_values}
        for field_name, allowed_values in rule.match_fields.items()
    )


def _normalized(value: object) -> str:
    return str(value or "").strip()
