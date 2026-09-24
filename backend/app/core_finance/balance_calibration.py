from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Literal

PositionScopeCalib = Literal["asset", "liability", "all"]
CurrencyBasisCalib = Literal["native", "CNY"]
SourceFamilyCalib = Literal["zqtz", "tyw"]
DataBasisCalib = Literal["formal_facts", "snapshot", "mixed"]

TYW_PRINCIPAL_AS_MARKET_AND_AMORT_SEMANTICS = "principal_as_market_and_amortized"

_SCOPE_LABEL: dict[PositionScopeCalib, str] = {
    "asset": "资产",
    "liability": "负债",
    "all": "资产负债",
}
_CURRENCY_LABEL: dict[CurrencyBasisCalib, str] = {
    "native": "原币",
    "CNY": "人民币",
}

_FACT_ZQTZ = "fact_formal_zqtz_balance_daily"
_FACT_TYW = "fact_formal_tyw_balance_daily"
_SNAP_ZQTZ = "zqtz_bond_daily_snapshot"
_SNAP_TYW = "tyw_interbank_daily_snapshot"


@dataclass(frozen=True)
class BalanceCalibrationMeta:
    position_scope: PositionScopeCalib
    currency_basis: CurrencyBasisCalib
    source_families: list[SourceFamilyCalib]
    tyw_amount_semantics: str
    data_basis: DataBasisCalib
    calibration_note: str


def build_calibration_meta(
    *,
    position_scope: PositionScopeCalib,
    currency_basis: CurrencyBasisCalib,
    source_families: list[SourceFamilyCalib],
    data_basis: DataBasisCalib,
    tyw_amount_semantics: str = TYW_PRINCIPAL_AS_MARKET_AND_AMORT_SEMANTICS,
) -> BalanceCalibrationMeta:
    scope_text = _SCOPE_LABEL[position_scope]
    currency_text = _CURRENCY_LABEL[currency_basis]

    uniq = tuple(dict.fromkeys(source_families))

    if "tyw" in uniq:
        base_note = f"{scope_text}范围，{currency_text}币种，含同业（同业以本金计）"
    elif uniq == ("zqtz",):
        base_note = f"{scope_text}范围，{currency_text}币种，仅债券投资"
    else:
        base_note = f"{scope_text}范围，{currency_text}币种"

    if data_basis == "mixed":
        base_note += "（部分日期使用快照数据）"

    return BalanceCalibrationMeta(
        position_scope=position_scope,
        currency_basis=currency_basis,
        source_families=list(uniq),
        tyw_amount_semantics=tyw_amount_semantics,
        data_basis=data_basis,
        calibration_note=base_note,
    )


def balance_calibration_meta_to_dict(meta: BalanceCalibrationMeta) -> dict[str, object]:
    return asdict(meta)


def build_adb_daily_balance_calibration_meta(
    adb_tables_used: list[str] | None,
    *,
    snapshot_fx_conversion: dict[str, object] | None = None,
) -> BalanceCalibrationMeta:
    """ADB 日均口径校准元数据。

    ``snapshot_fx_conversion`` 是快照回退行的 FX 处理摘要（converted_rows / dropped_rows）：
    快照回退行的外币金额已按当日 formal 中间价折算为 CNY 后才并入（calc_rules §12.4），
    缺当日中间价的外币行被剔除；两种降级都必须在 calibration_note 中显式披露（§14）。
    """
    tables = list(adb_tables_used or [])
    has_formal_zqtz = _FACT_ZQTZ in tables
    has_formal_tyw = _FACT_TYW in tables
    has_snap_zqtz = _SNAP_ZQTZ in tables
    has_snap_tyw = _SNAP_TYW in tables
    has_formal = has_formal_zqtz or has_formal_tyw
    has_snapshot = has_snap_zqtz or has_snap_tyw

    if has_formal and has_snapshot:
        data_basis: DataBasisCalib = "mixed"
    elif has_formal:
        data_basis = "formal_facts"
    elif has_snapshot:
        data_basis = "snapshot"
    else:
        data_basis = "formal_facts"

    families: list[SourceFamilyCalib] = []
    if has_formal_zqtz or has_snap_zqtz:
        families.append("zqtz")
    if has_formal_tyw or has_snap_tyw:
        families.append("tyw")
    if not families:
        families = ["zqtz", "tyw"]

    meta = build_calibration_meta(
        position_scope="all",
        currency_basis="CNY",
        source_families=families,
        data_basis=data_basis,
    )

    fx_note = _snapshot_fx_conversion_note(snapshot_fx_conversion)
    if fx_note:
        meta = replace(meta, calibration_note=meta.calibration_note + fx_note)
    return meta


def _snapshot_fx_conversion_note(snapshot_fx_conversion: dict[str, object] | None) -> str:
    if not snapshot_fx_conversion:
        return ""
    converted_rows = int(snapshot_fx_conversion.get("converted_rows") or 0)  # type: ignore[arg-type]
    dropped_rows = int(snapshot_fx_conversion.get("dropped_rows") or 0)  # type: ignore[arg-type]
    parts: list[str] = []
    if converted_rows > 0:
        parts.append(f"快照外币行已按当日中间价折算为人民币（{converted_rows} 行）")
    if dropped_rows > 0:
        parts.append(f"缺当日中间价的外币快照行已剔除（{dropped_rows} 行）")
    if not parts:
        return ""
    return "；" + "，".join(parts)
