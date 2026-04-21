"""Tests for CaliberRuleDescriptor validation and immutability."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from backend.app.core_finance.calibers import (
    Basis,
    CaliberRuleDescriptor,
    Resolution,
    View,
)


def _matrix_all_na() -> dict[tuple[Basis, View], Resolution]:
    return {(b, v): Resolution.NOT_APPLICABLE for b in Basis for v in View}


def _descriptor(**overrides: object) -> CaliberRuleDescriptor:
    payload: dict[str, object] = {
        "rule_id": "test_rule_descriptor_helper",
        "rule_version": "v1.0",
        "canonical_module": "backend.app.test_canonical.module",
        "canonical_callable": "dummy_callable",
        "matrix": _matrix_all_na(),
        "applies_to": ("fact_formal_test_daily",),
        "rationale": "Helper-built descriptor for unit tests.",
    }
    payload.update(overrides)
    return CaliberRuleDescriptor(**payload)


def test_descriptor_resolve_returns_expected_cell_and_cells_has_nine_entries() -> None:
    matrix = _matrix_all_na()
    matrix[(Basis.FORMAL, View.ACCOUNTING)] = Resolution.INCLUDE
    descriptor = _descriptor(matrix=matrix)
    assert descriptor.resolve(Basis.FORMAL, View.ACCOUNTING) == Resolution.INCLUDE
    assert len(descriptor.cells) == 9


def test_descriptor_rejects_blank_rule_id() -> None:
    with pytest.raises(ValueError, match="rule_id"):
        _descriptor(rule_id="")


def test_descriptor_rejects_short_two_char_rule_id() -> None:
    with pytest.raises(ValueError, match="rule_id"):
        _descriptor(rule_id="ab")


def test_descriptor_rejects_rule_version_without_v_prefix() -> None:
    with pytest.raises(ValueError, match="rule_version"):
        _descriptor(rule_version="1.0")


def test_descriptor_rejects_blank_canonical_module() -> None:
    with pytest.raises(ValueError, match="canonical_module"):
        _descriptor(canonical_module="")


def test_descriptor_rejects_blank_canonical_callable() -> None:
    with pytest.raises(ValueError, match="canonical_callable"):
        _descriptor(canonical_callable="")


def test_descriptor_rejects_blank_rationale() -> None:
    with pytest.raises(ValueError, match="rationale"):
        _descriptor(rationale="")


def test_descriptor_rejects_empty_applies_to_tuple() -> None:
    with pytest.raises(ValueError, match="applies_to"):
        _descriptor(applies_to=())


def test_descriptor_rejects_applies_to_with_disallowed_prefix() -> None:
    with pytest.raises(ValueError, match="applies_to"):
        _descriptor(applies_to=("random_table",))


def test_descriptor_rejects_incomplete_matrix_missing_cell() -> None:
    matrix = _matrix_all_na()
    del matrix[(Basis.SCENARIO, View.MANAGEMENT)]
    with pytest.raises(ValueError, match="incomplete"):
        _descriptor(matrix=matrix)


def test_descriptor_rejects_matrix_with_extra_unknown_cell_string_keys() -> None:
    matrix: dict[tuple[str, str], Resolution] = {
        (str(b), str(v)): Resolution.NOT_APPLICABLE for b in Basis for v in View
    }
    matrix[("formal", "not_a_valid_view_axis")] = Resolution.MERGE
    with pytest.raises(ValueError, match="unknown cells"):
        _descriptor(matrix=matrix)


def test_descriptor_rejects_matrix_value_not_resolution_instance() -> None:
    matrix = _matrix_all_na()
    matrix[(Basis.FORMAL, View.ACCOUNTING)] = "include"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Resolution"):
        _descriptor(matrix=matrix)


def test_descriptor_is_frozen_rejects_assignment_to_rule_id() -> None:
    descriptor = _descriptor()
    with pytest.raises(FrozenInstanceError):
        descriptor.rule_id = "x"  # type: ignore[misc]


def test_descriptor_cells_mapping_is_read_only() -> None:
    descriptor = _descriptor()
    with pytest.raises(TypeError):
        descriptor.cells[(Basis.FORMAL, View.ACCOUNTING)] = Resolution.EXCLUDE  # type: ignore[index]
