"""Pure arithmetic for the formal-product versus system operating PnL basis bridge."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

MONEY_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class PnlBasisBridgeComponentCalculation:
    code: str
    amount: Decimal
    evidence_status: str


@dataclass(frozen=True)
class PnlBasisBridgeCalculation:
    system_identity_residual: Decimal
    product_identity_residual: Decimal
    gross_components: tuple[PnlBasisBridgeComponentCalculation, ...]
    gross_closure_residual: Decimal
    net_components: tuple[PnlBasisBridgeComponentCalculation, ...]
    net_closure_residual: Decimal


def calculate_pnl_basis_bridge(
    *,
    system_gross_pnl: Decimal,
    system_manual_adjustment: Decimal,
    system_unallocated_pnl: Decimal,
    system_ftp_cost: Decimal,
    system_ftp_net_pnl: Decimal,
    formal_recognized_pnl: Decimal,
    product_gross_cash_income: Decimal,
    product_ftp_cost: Decimal,
    product_ftp_net_income: Decimal,
) -> PnlBasisBridgeCalculation:
    """Build two exact bridges without inventing a product-to-business crosswalk.

    The system-to-formal gross bridge is source traced. The formal-to-product
    gross difference remains an explicit mapping residual until an approved
    product/account/business crosswalk exists.
    """

    system_identity_residual = system_gross_pnl - system_ftp_cost - system_ftp_net_pnl
    product_identity_residual = (
        product_gross_cash_income - product_ftp_cost - product_ftp_net_income
    )
    _require_closed("system gross - FTP = FTP net", system_identity_residual)
    _require_closed("product gross cash - FTP = product net", product_identity_residual)

    remove_manual = -system_manual_adjustment
    rounding_alignment = formal_recognized_pnl - (
        system_gross_pnl + remove_manual + system_unallocated_pnl
    )
    _require_closed("system-to-formal rounding alignment", rounding_alignment)
    gross_components = (
        PnlBasisBridgeComponentCalculation(
            code="remove_system_manual_adjustment",
            amount=remove_manual,
            evidence_status="source_traced",
        ),
        PnlBasisBridgeComponentCalculation(
            code="restore_unallocated_formal_pnl",
            amount=system_unallocated_pnl,
            evidence_status="source_traced",
        ),
        PnlBasisBridgeComponentCalculation(
            code="rounding_alignment",
            amount=rounding_alignment,
            evidence_status="rounding_control",
        ),
    )
    gross_closure_residual = (
        system_gross_pnl
        + sum((component.amount for component in gross_components), Decimal("0"))
        - formal_recognized_pnl
    )
    _require_closed("system-to-formal gross bridge", gross_closure_residual)

    formal_to_product_scope = product_gross_cash_income - formal_recognized_pnl
    ftp_method_difference = system_ftp_cost - product_ftp_cost
    net_components = (
        *gross_components,
        PnlBasisBridgeComponentCalculation(
            code="formal_to_product_gross_scope_mapping_residual",
            amount=formal_to_product_scope,
            evidence_status="mapping_pending",
        ),
        PnlBasisBridgeComponentCalculation(
            code="ftp_method_and_denominator_difference",
            amount=ftp_method_difference,
            evidence_status="source_derived",
        ),
    )
    # This is the algebraic difference of the two identity residuals checked above,
    # not an independent validation; its detection bound is therefore about 0.02 yuan.
    net_closure_residual = (
        system_ftp_net_pnl
        + sum((component.amount for component in net_components), Decimal("0"))
        - product_ftp_net_income
    )
    _require_closed("system-to-product FTP-net bridge", net_closure_residual)

    return PnlBasisBridgeCalculation(
        system_identity_residual=system_identity_residual,
        product_identity_residual=product_identity_residual,
        gross_components=gross_components,
        gross_closure_residual=gross_closure_residual,
        net_components=net_components,
        net_closure_residual=net_closure_residual,
    )


def _require_closed(label: str, residual: Decimal) -> None:
    if abs(residual) > MONEY_TOLERANCE:
        raise ValueError(f"{label} does not close within {MONEY_TOLERANCE}: residual={residual}")
