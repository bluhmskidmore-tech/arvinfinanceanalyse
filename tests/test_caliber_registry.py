"""Tests for the process-global caliber rule registry."""

from __future__ import annotations

import warnings

import pytest

from backend.app.core_finance.calibers import (
    Basis,
    CaliberCalibrationViolation,
    CaliberRuleDescriptor,
    CaliberRuleRegistryError,
    Resolution,
    View,
    assert_canonical_callsite,
    clear_caliber_rules,
    ensure_caliber_rule,
    get_caliber_rule,
    list_caliber_rules,
    register_caliber_rule,
    replay_caliber_rules,
    resolve_caliber,
)

pytestmark = pytest.mark.usefixtures("clean_registry")


@pytest.fixture
def clean_registry() -> object:
    snapshot = list_caliber_rules()
    yield None
    replay_caliber_rules(snapshot)


def _matrix_all_na() -> dict[tuple[Basis, View], Resolution]:
    return {(b, v): Resolution.NOT_APPLICABLE for b in Basis for v in View}


def _registry_descriptor(*, rule_id: str, canonical_module: str, **overrides: object) -> CaliberRuleDescriptor:
    payload: dict[str, object] = {
        "rule_id": rule_id,
        "rule_version": "v1.0",
        "canonical_module": canonical_module,
        "canonical_callable": "dummy_callable",
        "matrix": _matrix_all_na(),
        "applies_to": ("fact_formal_test_daily",),
        "rationale": "Registry test descriptor.",
    }
    payload.update(overrides)
    return CaliberRuleDescriptor(**payload)


def test_register_then_get_round_trip() -> None:
    descriptor = _registry_descriptor(
        rule_id="test_register_roundtrip_rule",
        canonical_module="backend.app.registry_test.owner_a",
    )
    register_caliber_rule(descriptor)
    assert get_caliber_rule("test_register_roundtrip_rule") is descriptor


def test_register_rejects_duplicate_rule_id_with_different_descriptor() -> None:
    first = _registry_descriptor(
        rule_id="test_dup_rule_id",
        canonical_module="backend.app.registry_test.owner_dup_a",
    )
    second = _registry_descriptor(
        rule_id="test_dup_rule_id",
        canonical_module="backend.app.registry_test.owner_dup_b",
        rationale="Different rationale forces a distinct descriptor instance.",
    )
    register_caliber_rule(first)
    with pytest.raises(CaliberRuleRegistryError, match="rule_id"):
        register_caliber_rule(second)


def test_register_rejects_duplicate_canonical_callable_pair_for_different_rule() -> None:
    shared_module = "backend.app.registry_test.shared_canonical"
    register_caliber_rule(
        _registry_descriptor(
            rule_id="test_canon_owner_a",
            canonical_module=shared_module,
            canonical_callable="shared_callable",
        )
    )
    other = _registry_descriptor(
        rule_id="test_canon_owner_b",
        canonical_module=shared_module,
        canonical_callable="shared_callable",
    )
    with pytest.raises(CaliberRuleRegistryError, match="Canonical implementation"):
        register_caliber_rule(other)


def test_register_allows_same_module_with_distinct_callables() -> None:
    """
    Two rules may share a canonical module as long as they bind to
    distinct callables inside it. This matches the codebase reality where
    ``classification_rules.py`` legitimately hosts several canonical
    pieces (``LEDGER_PNL_ACCOUNT_PREFIXES`` / ``is_bond_liability`` /
    ``infer_invest_type``).
    """
    shared_module = "backend.app.registry_test.multi_callable_module"
    register_caliber_rule(
        _registry_descriptor(
            rule_id="test_multi_callable_a",
            canonical_module=shared_module,
            canonical_callable="callable_alpha",
        )
    )
    register_caliber_rule(
        _registry_descriptor(
            rule_id="test_multi_callable_b",
            canonical_module=shared_module,
            canonical_callable="callable_beta",
        )
    )
    rule_ids = {d.rule_id for d in list_caliber_rules()}
    assert {"test_multi_callable_a", "test_multi_callable_b"}.issubset(rule_ids)


def test_ensure_is_idempotent_for_same_descriptor() -> None:
    descriptor = _registry_descriptor(
        rule_id="test_ensure_idempotent",
        canonical_module="backend.app.registry_test.ensure_owner",
    )
    baseline = len(list_caliber_rules())
    ensure_caliber_rule(descriptor)
    count_after_ensure_once = len(list_caliber_rules())
    ensure_caliber_rule(descriptor)
    count_after_ensure_twice = len(list_caliber_rules())
    assert count_after_ensure_once == baseline + 1
    assert count_after_ensure_twice == count_after_ensure_once


def test_ensure_rejects_divergent_descriptor_for_existing_rule_id() -> None:
    first = _registry_descriptor(
        rule_id="test_ensure_divergent",
        canonical_module="backend.app.registry_test.divergent_owner",
        rule_version="v1.0",
    )
    second = _registry_descriptor(
        rule_id="test_ensure_divergent",
        canonical_module="backend.app.registry_test.divergent_owner",
        rule_version="v2.0",
    )
    ensure_caliber_rule(first)
    with pytest.raises(CaliberRuleRegistryError, match="different descriptor"):
        ensure_caliber_rule(second)


def test_resolve_caliber_returns_matrix_cell() -> None:
    matrix = _matrix_all_na()
    matrix[(Basis.ANALYTICAL, View.MANAGEMENT)] = Resolution.SPLIT
    descriptor = _registry_descriptor(
        rule_id="test_resolve_matrix",
        canonical_module="backend.app.registry_test.resolve_owner",
        matrix=matrix,
    )
    register_caliber_rule(descriptor)
    assert (
        resolve_caliber("test_resolve_matrix", Basis.ANALYTICAL, View.MANAGEMENT)
        == Resolution.SPLIT
    )


def test_get_caliber_rule_unknown_id_raises_key_error() -> None:
    with pytest.raises(KeyError, match="not registered"):
        get_caliber_rule("definitely_missing_rule_id_xyz")


def test_list_caliber_rules_returns_sorted_tuple() -> None:
    register_caliber_rule(
        _registry_descriptor(rule_id="zzz_last_rule", canonical_module="backend.app.registry_test.z")
    )
    register_caliber_rule(
        _registry_descriptor(rule_id="aaa_first_rule", canonical_module="backend.app.registry_test.a")
    )
    register_caliber_rule(
        _registry_descriptor(rule_id="mmm_mid_rule", canonical_module="backend.app.registry_test.m")
    )
    rules = list_caliber_rules()
    ids = [d.rule_id for d in rules]
    assert isinstance(rules, tuple)
    assert ids == sorted(ids)


def test_assert_canonical_callsite_silent_when_module_matches() -> None:
    descriptor = _registry_descriptor(
        rule_id="test_callsite_ok",
        canonical_module="backend.app.registry_test.canonical_ok",
    )
    register_caliber_rule(descriptor)
    with warnings.catch_warnings():
        warnings.simplefilter("error", CaliberCalibrationViolation)
        assert_canonical_callsite(descriptor.rule_id, descriptor.canonical_module)


def test_assert_canonical_callsite_warns_for_other_module() -> None:
    descriptor = _registry_descriptor(
        rule_id="test_callsite_warn",
        canonical_module="backend.app.registry_test.canonical_warn",
    )
    register_caliber_rule(descriptor)
    with pytest.warns(CaliberCalibrationViolation, match="non-canonical"):
        assert_canonical_callsite(descriptor.rule_id, "other.module")


def test_clear_caliber_rules_empties_state() -> None:
    clear_caliber_rules()
    assert list_caliber_rules() == ()


def test_replay_caliber_rules_restores_full_set() -> None:
    snapshot = list_caliber_rules()
    clear_caliber_rules()
    assert list_caliber_rules() == ()
    register_caliber_rule(
        _registry_descriptor(
            rule_id="test_replay_temp",
            canonical_module="backend.app.registry_test.replay_temp",
        )
    )
    assert len(list_caliber_rules()) == 1
    replay_caliber_rules(snapshot)
    assert list_caliber_rules() == snapshot
