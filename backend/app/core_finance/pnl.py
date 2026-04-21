from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Literal, Mapping, get_args

from backend.app.core_finance.config.classification_rules import (
    LEDGER_PNL_ACCOUNT_PREFIXES,
    infer_invest_type,
)
from backend.app.core_finance.field_normalization import derive_accounting_basis_value


InvestTypeStd = Literal["H", "A", "T"]
AccountingBasis = Literal["AC", "FVOCI", "FVTPL"]
CurrencyBasis = Literal["CNY", "CNX"]
# W-subject-2026-04-21: Human: caliber-subject_514_516_517_merge-justified.
# typing.Literal[...] requires literal forms (PEP 586), so the three
# prefix strings cannot be sourced from LEDGER_PNL_ACCOUNT_PREFIXES.
# The runtime assert below is the canonical lockstep guard.
JournalType = Literal["514", "516", "517", "adjustment"]
assert set(get_args(JournalType)) - {"adjustment"} == set(LEDGER_PNL_ACCOUNT_PREFIXES), (
    "JournalType prefix members must equal LEDGER_PNL_ACCOUNT_PREFIXES "
    "(caliber rule subject_514_516_517_merge)."
)
# W-subject-2026-04-21: ledger prefixes that flip sign under
# `direct_*` dc_flag normalization. The interest-income prefix
# (LEDGER_PNL_ACCOUNT_PREFIXES[0]) never flips; the fair-value-change
# and investment-income prefixes do. Derived from the canonical tuple
# to keep the set in lockstep without inlining bare prefix literals.
SIGN_FLIP_JOURNAL_TYPES: frozenset[str] = frozenset(LEDGER_PNL_ACCOUNT_PREFIXES) - {
    LEDGER_PNL_ACCOUNT_PREFIXES[0]
}

ZERO = Decimal("0")


@dataclass(slots=True, frozen=True)
class FiPnlRecord:
    """Standardized FI contract aligned to docs/data_contracts.md::fi_pnl_record."""

    report_date: date
    instrument_code: str
    portfolio_name: str
    cost_center: str
    invest_type_raw: str
    invest_type_std: InvestTypeStd
    accounting_basis: AccountingBasis
    interest_income_514: Decimal
    fair_value_change_516: Decimal
    capital_gain_517: Decimal
    manual_adjustment: Decimal = ZERO
    total_pnl: Decimal = ZERO
    currency_basis: CurrencyBasis = "CNY"
    source_version: str = ""
    rule_version: str = ""
    ingest_batch_id: str = ""
    trace_id: str = ""
    approval_status: str = ""
    governance_status: str = ""
    event_type: str = ""
    event_semantics: str = ""
    realized_flag: bool = False


@dataclass(slots=True, frozen=True)
class NonStdJournalEntry:
    """Standardized NonStd contract aligned to docs/data_contracts.md::nonstd_journal_entry."""

    voucher_date: date
    account_code: str
    asset_code: str
    portfolio_name: str
    cost_center: str
    journal_type: JournalType
    signed_amount: Decimal
    dc_flag: str
    event_type: str
    source_file: str
    source_version: str = ""
    rule_version: str = ""
    ingest_batch_id: str = ""
    trace_id: str = ""


@dataclass(slots=True, frozen=True)
class FormalPnlFiFactRow:
    """Future fact_formal_pnl_fi row shape after standardized FI inputs are governed."""

    report_date: date
    instrument_code: str
    portfolio_name: str
    cost_center: str
    invest_type_std: InvestTypeStd
    accounting_basis: AccountingBasis
    currency_basis: CurrencyBasis
    interest_income_514: Decimal
    fair_value_change_516: Decimal
    capital_gain_517: Decimal
    manual_adjustment: Decimal = ZERO
    total_pnl: Decimal = ZERO
    source_version: str = ""
    rule_version: str = ""
    ingest_batch_id: str = ""
    trace_id: str = ""


@dataclass(slots=True, frozen=True)
class NonStdPnlBridgeRow:
    """Future fact_nonstd_pnl_bridge row shape after standardized NonStd inputs are governed."""

    report_date: date
    bond_code: str
    portfolio_name: str
    cost_center: str
    interest_income_514: Decimal
    fair_value_change_516: Decimal
    capital_gain_517: Decimal
    manual_adjustment: Decimal = ZERO
    total_pnl: Decimal = ZERO
    source_version: str = ""
    rule_version: str = ""
    ingest_batch_id: str = ""
    trace_id: str = ""


@dataclass(slots=True, frozen=True)
class RecognizedPnlComponents:
    interest_income_514: Decimal = ZERO
    fair_value_change_516: Decimal = ZERO
    capital_gain_517: Decimal = ZERO
    manual_adjustment: Decimal = ZERO

    @property
    def total_pnl(self) -> Decimal:
        return (
            self.interest_income_514
            + self.fair_value_change_516
            + self.capital_gain_517
            + self.manual_adjustment
        )


def build_formal_pnl_fi_fact_rows(
    fi_records: Iterable[FiPnlRecord],
) -> list[FormalPnlFiFactRow]:
    """Project standardized FI records into the future formal FI fact shape."""
    rows: list[FormalPnlFiFactRow] = []
    for row in fi_records:
        recognized = _recognized_pnl_components(row)
        rows.append(
            FormalPnlFiFactRow(
                report_date=row.report_date,
                instrument_code=row.instrument_code,
                portfolio_name=row.portfolio_name,
                cost_center=row.cost_center,
                invest_type_std=row.invest_type_std,
                accounting_basis=row.accounting_basis,
                currency_basis=row.currency_basis,
                interest_income_514=recognized.interest_income_514,
                fair_value_change_516=recognized.fair_value_change_516,
                capital_gain_517=recognized.capital_gain_517,
                manual_adjustment=recognized.manual_adjustment,
                total_pnl=recognized.total_pnl,
                source_version=row.source_version,
                rule_version=row.rule_version,
                ingest_batch_id=row.ingest_batch_id,
                trace_id=row.trace_id,
            )
        )
    return rows


def build_nonstd_pnl_bridge_rows(
    entries: Iterable[NonStdJournalEntry],
    *,
    target_date: date,
    is_month_end: bool,
) -> list[NonStdPnlBridgeRow]:
    """Aggregate standardized NonStd entries into the future bridge fact shape."""
    filtered = [
        entry
        for entry in entries
        if _entry_in_scope(entry.voucher_date, target_date=target_date, is_month_end=is_month_end)
    ]

    grouped: dict[tuple[str, str, str], list[NonStdJournalEntry]] = {}
    for entry in filtered:
        key = (entry.asset_code or "未标注", entry.portfolio_name, entry.cost_center)
        grouped.setdefault(key, []).append(entry)

    rows: list[NonStdPnlBridgeRow] = []
    for (bond_code, portfolio_name, cost_center), items in sorted(grouped.items()):
        interest_income_514 = ZERO
        fair_value_change_516 = ZERO
        capital_gain_517 = ZERO
        manual_adjustment = ZERO
        source_versions: list[str] = []
        rule_versions: list[str] = []
        ingest_batch_ids: list[str] = []
        trace_ids: list[str] = []

        for item in items:
            if item.journal_type == "514":
                interest_income_514 += item.signed_amount
            elif item.journal_type == "516":
                fair_value_change_516 += item.signed_amount
            elif item.journal_type == "517":
                capital_gain_517 += item.signed_amount
            else:
                manual_adjustment += item.signed_amount

            _append_unique(source_versions, item.source_version)
            _append_unique(rule_versions, item.rule_version)
            _append_unique(ingest_batch_ids, item.ingest_batch_id)
            _append_unique(trace_ids, item.trace_id)

        total_pnl = interest_income_514 + fair_value_change_516 + capital_gain_517 + manual_adjustment
        rows.append(
            NonStdPnlBridgeRow(
                report_date=target_date,
                bond_code=bond_code,
                portfolio_name=portfolio_name,
                cost_center=cost_center,
                interest_income_514=interest_income_514,
                fair_value_change_516=fair_value_change_516,
                capital_gain_517=capital_gain_517,
                manual_adjustment=manual_adjustment,
                total_pnl=total_pnl,
                source_version="__".join(source_versions),
                rule_version="__".join(rule_versions),
                ingest_batch_id=",".join(ingest_batch_ids),
                trace_id=",".join(trace_ids),
            )
        )
    return rows


def normalize_nonstd_journal_entries(
    rows: Iterable[Mapping[str, object]],
    *,
    journal_type: JournalType,
) -> list[NonStdJournalEntry]:
    normalized: list[NonStdJournalEntry] = []
    for row in rows:
        voucher_date = _coerce_date(row["voucher_date"])
        raw_amount = _coerce_decimal(row.get("raw_amount", ZERO))
        dc_flag = str(row.get("dc_flag", ""))
        normalized.append(
            NonStdJournalEntry(
                voucher_date=voucher_date,
                account_code=str(row["account_code"]),
                asset_code=_coerce_optional_text(row.get("asset_code")),
                portfolio_name=str(row["portfolio_name"]),
                cost_center=str(row["cost_center"]),
                journal_type=journal_type,
                signed_amount=_normalize_nonstd_signed_amount(
                    raw_amount=raw_amount,
                    journal_type=journal_type,
                    dc_flag=dc_flag,
                ),
                dc_flag=dc_flag,
                event_type=str(row["event_type"]),
                source_file=str(row["source_file"]),
                source_version=str(row.get("source_version", "")),
                rule_version=str(row.get("rule_version", "")),
                ingest_batch_id=str(row.get("ingest_batch_id", "")),
                trace_id=str(row.get("trace_id", "")),
            )
        )
    return normalized


def normalize_fi_pnl_records(
    rows: Iterable[Mapping[str, object]],
) -> list[FiPnlRecord]:
    normalized: list[FiPnlRecord] = []
    for row in rows:
        report_date = _coerce_date(row["report_date"])
        invest_type_raw = str(row["invest_type_raw"])
        invest_type_std, accounting_basis = _normalize_fi_invest_type(invest_type_raw)
        interest_income_514 = _coerce_decimal(row.get("interest_income_514", ZERO))
        fair_value_change_516 = _coerce_decimal(row.get("fair_value_change_516", ZERO))
        capital_gain_517 = _coerce_decimal(row.get("capital_gain_517", ZERO))
        manual_adjustment = _coerce_decimal(row.get("manual_adjustment", ZERO))
        total_pnl = interest_income_514 + fair_value_change_516 + capital_gain_517 + manual_adjustment

        normalized.append(
            FiPnlRecord(
                report_date=report_date,
                instrument_code=str(row["instrument_code"]),
                portfolio_name=str(row["portfolio_name"]),
                cost_center=str(row["cost_center"]),
                invest_type_raw=invest_type_raw,
                invest_type_std=invest_type_std,
                accounting_basis=accounting_basis,
                interest_income_514=interest_income_514,
                fair_value_change_516=fair_value_change_516,
                capital_gain_517=capital_gain_517,
                manual_adjustment=manual_adjustment,
                total_pnl=total_pnl,
                currency_basis=_normalize_currency_basis(str(row.get("currency_basis", "CNY"))),
                source_version=str(row.get("source_version", "")),
                rule_version=str(row.get("rule_version", "")),
                ingest_batch_id=str(row.get("ingest_batch_id", "")),
                trace_id=str(row.get("trace_id", "")),
                approval_status=_coerce_optional_text(row.get("approval_status")),
                governance_status=_coerce_optional_text(row.get("governance_status")),
                event_type=_coerce_optional_text(row.get("event_type")),
                event_semantics=_coerce_optional_text(row.get("event_semantics")),
                realized_flag=_coerce_bool(row.get("realized_flag", False)),
            )
        )
    return normalized


__all__ = [
    "AccountingBasis",
    "CurrencyBasis",
    "FiPnlRecord",
    "FormalPnlFiFactRow",
    "InvestTypeStd",
    "JournalType",
    "NonStdJournalEntry",
    "NonStdPnlBridgeRow",
    "build_formal_pnl_fi_fact_rows",
    "build_nonstd_pnl_bridge_rows",
    "normalize_fi_pnl_records",
    "normalize_nonstd_journal_entries",
]


def _coerce_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _coerce_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _coerce_optional_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "none" else text


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "y"}


def _normalize_nonstd_signed_amount(
    *,
    raw_amount: Decimal,
    journal_type: JournalType,
    dc_flag: str,
) -> Decimal:
    normalized_dc = dc_flag.strip().lower()
    if normalized_dc.startswith("direct_"):
        if journal_type in SIGN_FLIP_JOURNAL_TYPES:
            return raw_amount * Decimal("-1")
        return raw_amount

    if normalized_dc in {"\u8d37", "credit", "cr"}:
        return raw_amount
    if normalized_dc in {"\u501f", "debit", "dr"}:
        return raw_amount * Decimal("-1")
    return raw_amount


def _normalize_fi_invest_type(value: str) -> tuple[InvestTypeStd, AccountingBasis]:
    """Normalize a fixed-income invest-type label to (H/A/T, accounting basis).

    W-pnl-2026-04-21
    ----------------
    Thin wrapper over canonical ``classification_rules.infer_invest_type``
    (caliber rule ``hat_mapping``). The wrapper preserves the historical
    ``Unsupported invest_type_raw=<value>`` error contract that PnL ledger
    callers depend on.
    """
    if not str(value or "").strip():
        raise ValueError(f"Unsupported invest_type_raw={value}")
    invest_type_std = infer_invest_type(None, value, None)
    if invest_type_std is None:
        raise ValueError(f"Unsupported invest_type_raw={value}")
    return invest_type_std, derive_accounting_basis_value(invest_type_std)  # type: ignore[arg-type]


def _normalize_currency_basis(value: str) -> CurrencyBasis:
    normalized = value.strip().upper()
    if normalized in {"CNY", "CNX"}:
        return normalized  # type: ignore[return-value]
    raise ValueError(f"Unsupported currency_basis={value}")


def _entry_in_scope(entry_date: date, *, target_date: date, is_month_end: bool) -> bool:
    if is_month_end:
        return (
            entry_date.year == target_date.year
            and entry_date.month == target_date.month
            and entry_date <= target_date
        )
    return entry_date == target_date


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _recognized_pnl_components(row: FiPnlRecord) -> RecognizedPnlComponents:
    return RecognizedPnlComponents(
        interest_income_514=row.interest_income_514,
        fair_value_change_516=(
            row.fair_value_change_516 if row.accounting_basis == "FVTPL" else ZERO
        ),
        capital_gain_517=(
            row.capital_gain_517 if _is_517_formal_allowed(row) else ZERO
        ),
        manual_adjustment=(
            row.manual_adjustment if _is_manual_adjustment_formal_allowed(row) else ZERO
        ),
    )


def _is_517_formal_allowed(row: FiPnlRecord) -> bool:
    if not row.realized_flag:
        return False
    return row.event_semantics.strip().lower() in {
        "realized_formal",
        "realized_disposal",
        "realized_redemption",
    }


def _is_manual_adjustment_formal_allowed(row: FiPnlRecord) -> bool:
    return row.approval_status.strip().lower() == "approved" or row.governance_status.strip().lower() == "approved"
