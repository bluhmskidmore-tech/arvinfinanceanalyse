"""Tests for caliber context enums and ALL_* cell helpers."""

from __future__ import annotations

from enum import StrEnum

from backend.app.core_finance.calibers import (
    ALL_BASIS,
    ALL_CELLS,
    ALL_VIEW,
    Basis,
    Resolution,
    View,
)


def test_basis_is_strenum_with_documented_members_and_lowercase_values() -> None:
    assert issubclass(Basis, StrEnum)
    assert set(Basis) == {Basis.FORMAL, Basis.SCENARIO, Basis.ANALYTICAL}
    assert Basis.FORMAL == "formal"
    assert Basis.SCENARIO == "scenario"
    assert Basis.ANALYTICAL == "analytical"


def test_view_is_strenum_with_documented_members_and_lowercase_values() -> None:
    assert issubclass(View, StrEnum)
    assert set(View) == {
        View.ACCOUNTING,
        View.MANAGEMENT,
        View.EXTERNAL_EXPOSURE,
    }
    assert View.ACCOUNTING == "accounting"
    assert View.MANAGEMENT == "management"
    assert View.EXTERNAL_EXPOSURE == "external_exposure"


def test_resolution_is_strenum_with_documented_members_and_lowercase_values() -> None:
    assert issubclass(Resolution, StrEnum)
    assert set(Resolution) == {
        Resolution.INCLUDE,
        Resolution.EXCLUDE,
        Resolution.MERGE,
        Resolution.SPLIT,
        Resolution.INHERIT_FROM_FORMAL,
        Resolution.NOT_APPLICABLE,
        Resolution.COMPUTE_VIA_CANONICAL,
    }
    assert Resolution.INCLUDE == "include"
    assert Resolution.EXCLUDE == "exclude"
    assert Resolution.MERGE == "merge"
    assert Resolution.SPLIT == "split"
    assert Resolution.INHERIT_FROM_FORMAL == "inherit_from_formal"
    assert Resolution.NOT_APPLICABLE == "not_applicable"
    assert Resolution.COMPUTE_VIA_CANONICAL == "compute_via_canonical"


def test_all_basis_matches_tuple_of_basis_members() -> None:
    assert ALL_BASIS == tuple(Basis)


def test_all_view_matches_tuple_of_view_members() -> None:
    assert ALL_VIEW == tuple(View)


def test_all_cells_has_nine_entries_and_covers_full_cross_product() -> None:
    assert len(ALL_CELLS) == 9
    for basis in Basis:
        for view in View:
            assert (basis, view) in ALL_CELLS
