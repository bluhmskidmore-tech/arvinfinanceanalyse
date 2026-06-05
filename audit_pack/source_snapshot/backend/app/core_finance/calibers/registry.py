"""
Caliber rule registry.

Mirrors the conventions of `backend.app.core_finance.module_registry` but
governs `CaliberRuleDescriptor` instances rather than fact-table modules.

Two uniqueness invariants are enforced:

1. ``rule_id`` is unique across the registry — no two descriptors may claim
   the same rule.
2. The pair ``(canonical_module, canonical_callable)`` is unique across the
   registry — exactly one rule may own any given canonical implementation.
   A single module (e.g. ``classification_rules``) is therefore allowed to
   host several rules as long as each rule binds to a *distinct* callable
   inside it; this matches the codebase reality where shared utility
   modules legitimately expose multiple canonical pieces.

Direct callers should use ``ensure_caliber_rule`` (idempotent) for module
import-time registration. ``register_caliber_rule`` is reserved for tests
that want strict "fail-on-duplicate" behaviour.
"""

from __future__ import annotations

import threading
import warnings
from collections.abc import Iterable

from backend.app.core_finance.calibers.descriptor import CaliberRuleDescriptor
from backend.app.core_finance.calibers.enums import Basis, Resolution, View


class CaliberRuleRegistryError(RuntimeError):
    """Raised when registry invariants are violated."""


class CaliberCalibrationViolation(DeprecationWarning):
    """
    Emitted when a non-canonical module performs work that the canonical
    rule owner should perform. Surfaced as ``DeprecationWarning`` so existing
    callers continue to function while migration proceeds.
    """


_LOCK = threading.RLock()
_RULES: dict[str, CaliberRuleDescriptor] = {}
_CANONICAL_CALLABLES: dict[tuple[str, str], str] = {}


def register_caliber_rule(descriptor: CaliberRuleDescriptor) -> CaliberRuleDescriptor:
    """
    Register a descriptor strictly. Raises if either ``rule_id`` or the
    ``(canonical_module, canonical_callable)`` pair is already claimed by
    a different descriptor.
    """
    if not isinstance(descriptor, CaliberRuleDescriptor):
        raise CaliberRuleRegistryError(
            "register_caliber_rule expects a CaliberRuleDescriptor; "
            f"got {type(descriptor).__name__}"
        )
    with _LOCK:
        existing = _RULES.get(descriptor.rule_id)
        if existing is not None and existing is not descriptor:
            raise CaliberRuleRegistryError(
                f"Caliber rule_id {descriptor.rule_id!r} already registered by "
                f"{existing.canonical_module!r}; refusing to overwrite with "
                f"{descriptor.canonical_module!r}"
            )
        canonical_key = (descriptor.canonical_module, descriptor.canonical_callable)
        owner = _CANONICAL_CALLABLES.get(canonical_key)
        if owner is not None and owner != descriptor.rule_id:
            raise CaliberRuleRegistryError(
                f"Canonical implementation "
                f"{descriptor.canonical_module}.{descriptor.canonical_callable} "
                f"is already claimed by rule {owner!r}; refusing to attach to "
                f"{descriptor.rule_id!r}"
            )
        _RULES[descriptor.rule_id] = descriptor
        _CANONICAL_CALLABLES[canonical_key] = descriptor.rule_id
    return descriptor


def ensure_caliber_rule(descriptor: CaliberRuleDescriptor) -> CaliberRuleDescriptor:
    """
    Idempotent registration helper for module-import-time wiring.

    Re-registering the *same* descriptor instance (or one structurally equal
    to the existing entry) is a no-op. A divergent descriptor for an existing
    ``rule_id`` raises.
    """
    with _LOCK:
        existing = _RULES.get(descriptor.rule_id)
        if existing is None:
            return register_caliber_rule(descriptor)
        if existing == descriptor:
            return existing
        raise CaliberRuleRegistryError(
            f"Caliber rule {descriptor.rule_id!r} already registered with a "
            "different descriptor; ensure_caliber_rule cannot overwrite. "
            "Bump rule_version or remove the duplicate definition."
        )


def get_caliber_rule(rule_id: str) -> CaliberRuleDescriptor:
    """Fetch a registered descriptor; raises KeyError if absent."""
    with _LOCK:
        try:
            return _RULES[rule_id]
        except KeyError as exc:
            raise KeyError(f"Caliber rule not registered: {rule_id!r}") from exc


def list_caliber_rules() -> tuple[CaliberRuleDescriptor, ...]:
    """Return all registered descriptors in stable rule_id order."""
    with _LOCK:
        return tuple(_RULES[k] for k in sorted(_RULES))


def list_canonical_modules() -> tuple[str, ...]:
    """
    Return all currently-claimed canonical *modules* in sorted order
    (deduplicated; a module appears once even if it hosts multiple rules).
    """
    with _LOCK:
        return tuple(sorted({module for module, _ in _CANONICAL_CALLABLES}))


def list_canonical_callables() -> tuple[tuple[str, str], ...]:
    """
    Return all currently-claimed ``(module, callable)`` pairs in sorted
    order. This is the actual uniqueness key enforced by
    :func:`register_caliber_rule`.
    """
    with _LOCK:
        return tuple(sorted(_CANONICAL_CALLABLES))


def resolve_caliber(rule_id: str, basis: Basis, view: View) -> Resolution:
    """Convenience: descriptor lookup + matrix cell resolution."""
    descriptor = get_caliber_rule(rule_id)
    return descriptor.resolve(basis, view)


def assert_canonical_callsite(
    rule_id: str,
    calling_module: str,
    *,
    stacklevel: int = 2,
) -> None:
    """
    Emit a ``CaliberCalibrationViolation`` warning if ``calling_module`` is
    not the registered ``canonical_module`` for ``rule_id``.

    Use at the head of any function that re-implements a caliber rule —
    typically a legacy implementation marked for migration. The warning is
    a ``DeprecationWarning`` subclass so it does not break existing callers
    but is visible in tests via ``pytest -W error::DeprecationWarning``.
    """
    descriptor = get_caliber_rule(rule_id)
    if calling_module == descriptor.canonical_module:
        return
    warnings.warn(
        (
            f"Caliber rule {rule_id!r} is being applied from non-canonical "
            f"module {calling_module!r}; canonical owner is "
            f"{descriptor.canonical_module!r} ({descriptor.canonical_callable!r}). "
            "Migrate the call site or move the implementation."
        ),
        category=CaliberCalibrationViolation,
        stacklevel=stacklevel,
    )


def clear_caliber_rules() -> None:
    """
    Reset registry state. **Test-only**; do not call from production code.
    Mirrors ``module_registry.clear_formal_modules`` ergonomics.
    """
    with _LOCK:
        _RULES.clear()
        _CANONICAL_CALLABLES.clear()


def replay_caliber_rules(descriptors: Iterable[CaliberRuleDescriptor]) -> None:
    """
    Test helper: clear and re-register a defined set of descriptors. Used by
    fixtures that want a deterministic registry snapshot.
    """
    with _LOCK:
        clear_caliber_rules()
        for descriptor in descriptors:
            register_caliber_rule(descriptor)
