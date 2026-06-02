from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LedgerDashboardData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: str | None
    asset_face_amount: float | None
    liability_face_amount: float | None
    net_face_exposure: float | None
    alert_count: int | None


class LedgerPositionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position_key: str
    batch_id: int | str
    row_no: int
    as_of_date: str
    bond_code: str
    bond_name: str
    portfolio: str
    direction: str
    business_type: str
    business_type_1: str
    account_category_std: str
    cost_center: str
    asset_class_std: str
    channel: str
    currency: str
    face_amount: float | None
    fair_value: float | None
    amortized_cost: float | None
    accrued_interest: float | None
    interest_receivable_payable: float | None
    quantity: float | None
    latest_face_value: float | None
    interest_method: str
    coupon_rate: float | None
    yield_to_maturity: float | None
    interest_start_date: str | None
    maturity_date: str | None
    counterparty_name_cn: str
    legal_customer_name: str
    group_customer_name: str
    trace: dict[str, object]
