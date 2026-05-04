"""
CaliberRuleDescriptor — contract object for a unified calculation rule.

Mirrors the shape of `FormalComputeModuleDescriptor` (see
`backend/app/core_finance/module_contracts.py`) but addresses a different
unit: a *calculation rule* whose semantics must remain identical across every
caller in the system.

A descriptor is immutable (`frozen=True`, `slots=True`), validated in
`__post_init__`, and registered exactly once via the `registry` module.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from backend.app.core_finance.calibers.enums import (
    ALL_CELLS,
    Basis,
    Resolution,
    View,
)

_RULE_ID_MIN_LEN = 3
_RULE_VERSION_PREFIX = "v"
_FACT_TABLE_FAMILY_PREFIXES: tuple[str, ...] = (
    "fact_formal_",
    "fact_scenario_",
    "fact_analytical_",
    "vw_",  # views are tolerated for analytical-only rules
)


@dataclass(slots=True, frozen=True)
class CaliberRuleDescriptor:
    """
    Single source of truth for one canonical calculation rule.

    Attributes
    ----------
    rule_id:
        Stable string identifier. Must be unique across the registry.
        Convention: snake_case domain term, e.g. ``"issuance_exclusion"``.
    rule_version:
        Semantic version starting with ``v``, e.g. ``"v1.0"``. Bumped when
        the rule's behaviour changes in a way that affects downstream caches.
    canonical_module:
        Dotted module path that owns the canonical implementation, e.g.
        ``"backend.app.core_finance.config.classification_rules"``.
        All other modules MUST delegate; direct re-implementation triggers a
        DeprecationWarning via ``assert_canonical_callsite``.
    canonical_callable:
        Symbol within ``canonical_module`` that callers should invoke (or, for
        constant rules like 514/516/517 prefixes, the constant they should
        consume). Documentation-only; the registry does not import it.
    matrix:
        Complete mapping of every ``(Basis, View)`` cell to a ``Resolution``.
        Validation rejects any partial matrix — explicit ``NOT_APPLICABLE`` is
        required when a cell intentionally has no behaviour. This forces the
        rule author to think about every context.
    applies_to:
        Tuple of fact-table family prefixes the rule governs. Used by the
        future CI lint to scope its checks. Each entry must start with one of
        ``fact_formal_``, ``fact_scenario_``, ``fact_analytical_``, or ``vw_``.
    rationale:
        One-paragraph plain-language reason the rule exists. Required.
    source_doc:
        Optional pointer to a spec / decision-log file. May be empty.
    """

    rule_id: str
    rule_version: str
    canonical_module: str
    canonical_callable: str
    matrix: Mapping[tuple[Basis, View], Resolution]
    applies_to: tuple[str, ...]
    rationale: str
    source_doc: str = ""
    _frozen_matrix: Mapping[tuple[Basis, View], Resolution] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        self._validate_string("rule_id", self.rule_id, min_length=_RULE_ID_MIN_LEN)
        self._validate_string("canonical_module", self.canonical_module)
        self._validate_string("canonical_callable", self.canonical_callable)
        self._validate_string("rationale", self.rationale)
        self._validate_rule_version(self.rule_version)
        self._validate_applies_to(self.applies_to)
        frozen = self._validate_matrix(self.matrix)
        # Bypass frozen=True to install the read-only view exactly once.
        object.__setattr__(self, "_frozen_matrix", frozen)

    @staticmethod
    def _validate_string(field_name: str, value: object, *, min_length: int = 1) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"CaliberRuleDescriptor.{field_name} must be non-blank string")
        if len(value.strip()) < min_length:
            raise ValueError(
                f"CaliberRuleDescriptor.{field_name} must be at least {min_length} chars"
            )

    @staticmethod
    def _validate_rule_version(value: str) -> None:
        if not isinstance(value, str) or not value.startswith(_RULE_VERSION_PREFIX):
            raise ValueError(
                f"CaliberRuleDescriptor.rule_version must start with '{_RULE_VERSION_PREFIX}', "
                f"got {value!r}"
            )
        tail = value[len(_RULE_VERSION_PREFIX) :]
        if not tail or not tail.replace(".", "").replace("_", "").isalnum():
            raise ValueError(
                f"CaliberRuleDescriptor.rule_version has invalid suffix: {value!r}"
            )

    @staticmethod
    def _validate_applies_to(applies_to: tuple[str, ...]) -> None:
        if not isinstance(applies_to, tuple) or not applies_to:
            raise ValueError("CaliberRuleDescriptor.applies_to must be non-empty tuple")
        for entry in applies_to:
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(
                    "CaliberRuleDescriptor.applies_to entries must be non-blank strings"
                )
            if not any(entry.startswith(prefix) for prefix in _FACT_TABLE_FAMILY_PREFIXES):
                raise ValueError(
                    "CaliberRuleDescriptor.applies_to entries must start with one of "
                    f"{_FACT_TABLE_FAMILY_PREFIXES}, got {entry!r}"
                )

    @staticmethod
    def _validate_matrix(
        matrix: Mapping[tuple[Basis, View], Resolution],
    ) -> Mapping[tuple[Basis, View], Resolution]:
        if not isinstance(matrix, Mapping):
            raise ValueError("CaliberRuleDescriptor.matrix must be a Mapping")
        provided = set(matrix.keys())
        missing = ALL_CELLS - provided
        extra = provided - ALL_CELLS
        if missing:
            raise ValueError(
                "CaliberRuleDescriptor.matrix is incomplete; missing cells: "
                f"{sorted(str(cell) for cell in missing)}"
            )
        if extra:
            raise ValueError(
                "CaliberRuleDescriptor.matrix has unknown cells: "
                f"{sorted(str(cell) for cell in extra)}"
            )
        for cell, resolution in matrix.items():
            if not isinstance(resolution, Resolution):
                raise ValueError(
                    f"CaliberRuleDescriptor.matrix[{cell!r}] must be Resolution, "
                    f"got {type(resolution).__name__}"
                )
        # Snapshot into an immutable read-only mapping.
        return MappingProxyType(dict(matrix))

    @property
    def cells(self) -> Mapping[tuple[Basis, View], Resolution]:
        """Read-only matrix view."""
        return self._frozen_matrix

    def resolve(self, basis: Basis, view: View) -> Resolution:
        """Look up the resolution for a single ``(basis, view)`` cell."""
        return self._frozen_matrix[(basis, view)]
