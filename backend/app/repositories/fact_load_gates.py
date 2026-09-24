"""Pre-load gates for the governed core ALM facts.

The DuckDB unique indexes added by migration v43 are the durable guarantee, but
they only speak after the ``delete``/``insert`` pair has been assembled and they
answer with an opaque constraint error. These gates run against the in-memory
batch first, so a defective batch is rejected before it touches storage and the
operator is told which natural key collided.

Three gates, matching the data diagnostic that produced the v43 keys:

``A`` uniqueness (blocking)
    Same natural key twice inside one batch. Mirrors the v43 index exactly,
    including its NULL handling: a Python tuple compares ``None`` equal to
    ``None``, which is the same fold the index performs with its sentinel.

``B`` one instrument carrying several maturity dates (warning)
    The only historically observed pattern with a material amount impact. On
    2025-02-28 the source system emitted both the pre-roll and post-roll row for
    one USD position, which passes gate A (the maturity dates differ) yet
    double counted CNY 1.894bn of market value. Over all 519 report dates this
    rule fires exactly once, on that date.

``C`` sign and attribution (warning)
    Negative market value must be seen, and a position carrying real money must
    carry a cost center. The zero-market-value carve-out is what makes C usable:
    without it the missing-cost-center rule fires on ~31 rows every single day
    (bank-counter certificate treasuries legitimately have no cost center and no
    market value) and the gate gets switched off. With it, only 14 of 519 dates
    raise anything at all.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

BOND_ANALYTICS_NATURAL_KEY: tuple[str, ...] = (
    "report_date",
    "instrument_code",
    "portfolio_name",
    "cost_center",
    "accounting_class",
    "maturity_date",
)
ZQTZ_BALANCE_NATURAL_KEY: tuple[str, ...] = (
    "report_date",
    "instrument_code",
    "portfolio_name",
    "cost_center",
    "currency_basis",
    "position_scope",
    "accounting_basis",
    "maturity_date",
)
TYW_BALANCE_NATURAL_KEY: tuple[str, ...] = (
    "report_date",
    "position_id",
    "currency_basis",
    "position_scope",
)
# The bridge fact carries no accounting or currency dimension, so its grain is
# narrower than the formal FI fact it sits beside.
NONSTD_PNL_BRIDGE_NATURAL_KEY: tuple[str, ...] = (
    "report_date",
    "bond_code",
    "portfolio_name",
    "cost_center",
)

# One instrument split across maturity dates only matters when real money rides
# on it; the floor keeps rounding-scale roll artefacts out of the operator's
# inbox. Calibrated on the full 519-date history: 6 hits without it, 1 with it.
GATE_B_ABS_AMOUNT_FLOOR = Decimal("100000000")

_MAX_REPORTED_EXAMPLES = 5


@dataclass(frozen=True)
class GateFinding:
    """One gate observation, carrying enough context to act on it."""

    gate: str
    code: str
    message: str


@dataclass(frozen=True)
class GateOutcome:
    blocking: tuple[GateFinding, ...]
    warnings: tuple[GateFinding, ...]

    @property
    def rejected(self) -> bool:
        return bool(self.blocking)


class FactLoadGateError(RuntimeError):
    """A batch failed a blocking pre-load gate and was not written."""

    def __init__(self, table_name: str, findings: Sequence[GateFinding]) -> None:
        self.table_name = table_name
        self.findings = tuple(findings)
        detail = "; ".join(finding.message for finding in self.findings)
        super().__init__(f"{table_name} rejected by pre-load gate: {detail}")


def _field(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _amount(row: Any, field_name: str) -> Decimal:
    value = _field(row, field_name)
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _format_key(key_fields: Sequence[str], key: Sequence[Any]) -> str:
    return ", ".join(f"{name}={value!r}" for name, value in zip(key_fields, key, strict=True))


def check_natural_key_uniqueness(
    rows: Iterable[Any],
    *,
    table_name: str,
    key_fields: Sequence[str],
) -> list[GateFinding]:
    """Gate A: refuse a batch that carries the same natural key more than once."""
    counts: dict[tuple[Any, ...], int] = defaultdict(int)
    for row in rows:
        counts[tuple(_field(row, name) for name in key_fields)] += 1

    duplicates = [(key, count) for key, count in counts.items() if count > 1]
    if not duplicates:
        return []

    duplicates.sort(key=lambda item: item[1], reverse=True)
    excess = sum(count - 1 for _key, count in duplicates)
    examples = "; ".join(
        f"{_format_key(key_fields, key)} x{count}"
        for key, count in duplicates[:_MAX_REPORTED_EXAMPLES]
    )
    suffix = "" if len(duplicates) <= _MAX_REPORTED_EXAMPLES else f" (+{len(duplicates) - _MAX_REPORTED_EXAMPLES} more)"
    return [
        GateFinding(
            gate="A",
            code="duplicate_natural_key",
            message=(
                f"{table_name}: {len(duplicates)} duplicate natural-key group(s), "
                f"{excess} excess row(s) on ({', '.join(key_fields)}). "
                f"Do not deduplicate; confirm the grain first. Examples: {examples}{suffix}"
            ),
        )
    ]


def check_multi_maturity_exposure(
    rows: Iterable[Any],
    *,
    table_name: str,
    group_fields: Sequence[str] = ("report_date", "instrument_code", "portfolio_name"),
    maturity_field: str = "maturity_date",
    amount_field: str = "market_value",
    amount_floor: Decimal = GATE_B_ABS_AMOUNT_FLOOR,
) -> list[GateFinding]:
    """Gate B: one instrument reported under several maturity dates on one date."""
    maturities: dict[tuple[Any, ...], set[Any]] = defaultdict(set)
    exposure: dict[tuple[Any, ...], Decimal] = defaultdict(Decimal)
    for row in rows:
        group = tuple(_field(row, name) for name in group_fields)
        maturities[group].add(_field(row, maturity_field))
        exposure[group] += abs(_amount(row, amount_field))

    findings: list[GateFinding] = []
    for group, values in sorted(maturities.items(), key=lambda item: exposure[item[0]], reverse=True):
        if len(values) <= 1 or exposure[group] <= amount_floor:
            continue
        rendered = ", ".join(sorted(str(value) for value in values))
        findings.append(
            GateFinding(
                gate="B",
                code="multi_maturity_same_instrument",
                message=(
                    f"{table_name}: {_format_key(group_fields, group)} carries "
                    f"{len(values)} maturity dates ({rendered}) with total abs {amount_field} "
                    f"{exposure[group]:,.2f}. A maturity roll emitted as two rows double counts "
                    "the position; reconcile against the source before publishing."
                ),
            )
        )
    return findings[:_MAX_REPORTED_EXAMPLES]


def check_sign_and_attribution(
    rows: Iterable[Any],
    *,
    table_name: str,
    amount_field: str = "market_value",
    cost_center_field: str = "cost_center",
    instrument_field: str = "instrument_code",
) -> list[GateFinding]:
    """Gate C: negative amounts must be visible; real money must carry a cost center."""
    negative: list[tuple[Any, Decimal]] = []
    unattributed: list[tuple[Any, Decimal]] = []
    for row in rows:
        amount = _amount(row, amount_field)
        if amount < 0:
            negative.append((_field(row, instrument_field), amount))
        # Zero-amount rows without a cost center are a legitimate, permanent
        # population (bank-counter certificate treasuries); alerting on them
        # every day is what gets this gate turned off.
        if amount != 0 and _is_blank(_field(row, cost_center_field)):
            unattributed.append((_field(row, instrument_field), amount))

    findings: list[GateFinding] = []
    if negative:
        total = sum((amount for _code, amount in negative), Decimal("0"))
        examples = ", ".join(
            f"{code}={amount:,.2f}" for code, amount in negative[:_MAX_REPORTED_EXAMPLES]
        )
        findings.append(
            GateFinding(
                gate="C",
                code="negative_amount",
                message=(
                    f"{table_name}: {len(negative)} row(s) with negative {amount_field}, "
                    f"total {total:,.2f}. Confirm these are upstream write-offs rather than "
                    f"short positions. Examples: {examples}"
                ),
            )
        )
    if unattributed:
        total = sum((abs(amount) for _code, amount in unattributed), Decimal("0"))
        examples = ", ".join(
            f"{code}={amount:,.2f}" for code, amount in unattributed[:_MAX_REPORTED_EXAMPLES]
        )
        findings.append(
            GateFinding(
                gate="C",
                code="missing_cost_center",
                message=(
                    f"{table_name}: {len(unattributed)} row(s) with non-zero {amount_field} but no "
                    f"{cost_center_field}, total abs {total:,.2f}. Examples: {examples}"
                ),
            )
        )
    return findings


def evaluate_bond_analytics_load(
    rows: Iterable[Any],
    *,
    table_name: str = "fact_formal_bond_analytics_daily",
) -> GateOutcome:
    """Run gates A (blocking), B and C (warning) over one bond-analytics batch."""
    materialized = list(rows)
    blocking = check_natural_key_uniqueness(
        materialized, table_name=table_name, key_fields=BOND_ANALYTICS_NATURAL_KEY
    )
    warnings = [
        *check_multi_maturity_exposure(materialized, table_name=table_name),
        *check_sign_and_attribution(materialized, table_name=table_name),
    ]
    return GateOutcome(blocking=tuple(blocking), warnings=tuple(warnings))


def evaluate_natural_key_load(
    rows: Iterable[Any],
    *,
    table_name: str,
    key_fields: Sequence[str],
) -> GateOutcome:
    """Run gate A alone, for facts whose grain carries no market-value semantics."""
    blocking = check_natural_key_uniqueness(
        list(rows), table_name=table_name, key_fields=key_fields
    )
    return GateOutcome(blocking=tuple(blocking), warnings=())


def commit_report_date_purge(
    conn: Any,
    *,
    tables: Sequence[str],
    report_date: str,
    date_column: str = "report_date",
) -> None:
    """Delete one report date from each table and commit before re-inserting it.

    DuckDB 1.5.1 keeps the deleted entries in a unique index until the deleting
    transaction commits. Once the v43 natural-key indexes exist, the historical
    ``begin; delete by report_date; insert; commit`` rerun therefore fails with a
    duplicate-key error on the very rows it just removed — measured on a copy of
    the production database, every rerun of every governed fact would break.
    Committing the purge first is what keeps reruns idempotent.

    The cost is that a crash between the two commits leaves the report date
    empty rather than stale. That is the same state the failure path already
    produces deliberately (``invalidate_report_date_facts``), and an empty date
    is visible to the freshness checks in a way stale data is not.
    """
    conn.execute("begin transaction")
    for table_name in tables:
        conn.execute(f"delete from {table_name} where {date_column} = ?", [report_date])
    conn.execute("commit")


def enforce_gate_outcome(outcome: GateOutcome, *, table_name: str) -> None:
    """Log every warning, then raise if any blocking gate fired."""
    for finding in outcome.warnings:
        logger.warning("fact load gate %s (%s): %s", finding.gate, finding.code, finding.message)
    if outcome.blocking:
        for finding in outcome.blocking:
            logger.error("fact load gate %s (%s): %s", finding.gate, finding.code, finding.message)
        raise FactLoadGateError(table_name, outcome.blocking)
