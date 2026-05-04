from __future__ import annotations

from backend.app.core_finance.balance_calibration import (
    TYW_PRINCIPAL_AS_MARKET_AND_AMORT_SEMANTICS,
    build_adb_daily_balance_calibration_meta,
    build_calibration_meta,
    balance_calibration_meta_to_dict,
)


def test_calibration_note_only_zqtz_zh():
    meta = build_calibration_meta(
        position_scope="asset",
        currency_basis="native",
        source_families=["zqtz"],
        data_basis="formal_facts",
    )
    assert meta.calibration_note == "资产范围，原币币种，仅债券投资"


def test_calibration_note_includes_tyw_zh():
    meta = build_calibration_meta(
        position_scope="liability",
        currency_basis="CNY",
        source_families=["zqtz", "tyw"],
        data_basis="formal_facts",
    )
    assert meta.calibration_note == "负债范围，人民币币种，含同业（同业以本金计）"


def test_calibration_note_appends_when_mixed_basis():
    meta = build_calibration_meta(
        position_scope="liability",
        currency_basis="CNY",
        source_families=["zqtz", "tyw"],
        data_basis="mixed",
    )
    assert meta.calibration_note.endswith("（部分日期使用快照数据）")


def test_tyw_semantics_fixed_constant():
    meta = build_calibration_meta(
        position_scope="all",
        currency_basis="CNY",
        source_families=["tyw"],
        data_basis="formal_facts",
    )
    assert meta.tyw_amount_semantics == TYW_PRINCIPAL_AS_MARKET_AND_AMORT_SEMANTICS


def test_serializes_to_plain_dict_json_friendly_keys():
    meta = build_calibration_meta(
        position_scope="asset",
        currency_basis="CNY",
        source_families=["zqtz", "tyw"],
        data_basis="snapshot",
    )
    dumped = balance_calibration_meta_to_dict(meta)
    assert set(dumped.keys()) >= {
        "position_scope",
        "currency_basis",
        "source_families",
        "tyw_amount_semantics",
        "data_basis",
        "calibration_note",
    }


def test_adb_derives_basis_from_tables_used_only_formal_facts():
    meta = build_adb_daily_balance_calibration_meta(
        ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"]
    )
    assert meta.data_basis == "formal_facts"
    assert meta.position_scope == "all"
    assert meta.currency_basis == "CNY"


def test_adb_mixed_when_formal_and_snapshot_tables():
    meta = build_adb_daily_balance_calibration_meta(
        [
            "fact_formal_zqtz_balance_daily",
            "tyw_interbank_daily_snapshot",
        ]
    )
    assert meta.data_basis == "mixed"
    assert "zqtz" in meta.source_families and "tyw" in meta.source_families
