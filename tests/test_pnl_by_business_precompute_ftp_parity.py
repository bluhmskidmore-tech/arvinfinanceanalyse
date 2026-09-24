from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext

import pytest

from backend.app.core_finance.config.product_category_mapping import (
    resolve_product_category_ftp_rate_pct,
)
from backend.app.core_finance.pnl import compute_pnl_by_business_yield_and_ftp
from tests.helpers import load_module

precompute_module = load_module(
    "backend.app.tasks.pnl_by_business_precompute",
    "backend/app/tasks/pnl_by_business_precompute.py",
)
pnl_repo_module = load_module(
    "backend.app.repositories.pnl_repo",
    "backend/app/repositories/pnl_repo.py",
)
pnl_service_module = load_module(
    "backend.app.services.pnl_service",
    "backend/app/services/pnl_service.py",
)


def test_precompute_rule_version_tracks_current_analysis_contract() -> None:
    assert pnl_repo_module.PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION == (
        "rv_pnl_by_business_precompute_v8"
    )


def test_precompute_source_fingerprint_tracks_canonical_effective_ftp_rate(tmp_path) -> None:
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(duckdb_path), read_only=False).close()
    repo = pnl_repo_module.PnlRepository(str(duckdb_path))

    fixed_rate_from_default_a = resolve_product_category_ftp_rate_pct(
        date(2026, 12, 31), Decimal("9.99")
    )
    fixed_rate_from_default_b = resolve_product_category_ftp_rate_pct(
        date(2026, 12, 31), Decimal("0.25")
    )
    fixed_source_a = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-12-31",
        effective_ftp_rate_pct=fixed_rate_from_default_a,
    )
    fixed_source_b = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-12-31",
        effective_ftp_rate_pct=fixed_rate_from_default_b,
    )

    canonical_source_a = repo.pnl_by_business_precompute_source_version(
        year=2027,
        as_of_date="2027-12-31",
        effective_ftp_rate_pct=Decimal("1.60"),
    )
    canonical_source_b = repo.pnl_by_business_precompute_source_version(
        year=2027,
        as_of_date="2027-12-31",
        effective_ftp_rate_pct=Decimal("1.6000"),
    )
    changed_source = repo.pnl_by_business_precompute_source_version(
        year=2027,
        as_of_date="2027-12-31",
        effective_ftp_rate_pct=Decimal("1.61"),
    )

    assert fixed_rate_from_default_a == fixed_rate_from_default_b == Decimal("1.60")
    assert fixed_source_a == fixed_source_b
    assert canonical_source_a == canonical_source_b
    assert canonical_source_a != changed_source
    assert canonical_source_a.startswith("sv_pnl_by_business_precompute_v5:")
    assert '"effective_ftp_rate_pct":"1.6"' in canonical_source_a
    assert pnl_repo_module._canonical_decimal_text(Decimal("-0.000")) == "0"
    assert pnl_repo_module._canonical_decimal_text(Decimal("-1.6000")) == "-1.6"


def test_effective_ftp_rate_canonicalization_is_decimal_context_independent() -> None:
    rate = Decimal("1.23456789012345678901234567890123456789")
    canonical_by_precision: dict[int, str] = {}

    for precision in (8, 28, 40):
        with localcontext() as context:
            context.prec = precision
            canonical_by_precision[precision] = pnl_repo_module._canonical_decimal_text(rate)

    assert set(canonical_by_precision.values()) == {
        "1.23456789012345678901234567890123456789"
    }


@pytest.mark.parametrize("non_finite", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_effective_ftp_rate_canonicalization_rejects_non_finite_values(
    non_finite: Decimal,
) -> None:
    with pytest.raises(ValueError, match="must be finite"):
        pnl_repo_module._canonical_decimal_text(non_finite)


def test_precompute_fetch_and_metadata_reject_changed_effective_ftp_rate(tmp_path) -> None:
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    duckdb.connect(str(duckdb_path), read_only=False).close()
    stored_source_version = repo.pnl_by_business_precompute_source_version(
        year=2027,
        as_of_date="2027-12-31",
        effective_ftp_rate_pct=Decimal("1.60"),
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_pnl_by_business_precompute (
                year integer, as_of_date varchar, result_kind varchar,
                dimension varchar, business_key varchar,
                payload_json varchar, source_version varchar, rule_version varchar,
                generated_at timestamp
            )
            """
        )
        conn.execute(
            """
            insert into fact_pnl_by_business_precompute values (
                2027, '2027-12-31', 'monthly', '', '',
                '{"current": true}', ?, ?, current_timestamp
            )
            """,
            [stored_source_version, pnl_repo_module.PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION],
        )
    finally:
        conn.close()

    assert repo.fetch_pnl_by_business_precompute(
        year=2027,
        as_of_date="2027-12-31",
        result_kind="monthly",
        dimension="",
        business_key="",
        effective_ftp_rate_pct=Decimal("1.6000"),
    ) == {"current": True}
    assert repo.fetch_pnl_by_business_precompute(
        year=2027,
        as_of_date="2027-12-31",
        result_kind="monthly",
        dimension="",
        business_key="",
        effective_ftp_rate_pct=Decimal("1.61"),
    ) is None
    stale_metadata = repo.fetch_pnl_by_business_precompute_metadata(
        year=2027,
        as_of_date="2027-12-31",
        effective_ftp_rate_pct=Decimal("1.61"),
    )
    assert stale_metadata is not None
    assert stale_metadata["is_current"] is False


def test_precompute_read_helper_forwards_effective_ftp_rate() -> None:
    received: list[dict[str, object]] = []

    class FakeRepository:
        def fetch_pnl_by_business_precompute(self, **kwargs):
            received.append(kwargs)
            return None

    pnl_service_module._fetch_pnl_by_business_precompute(
        FakeRepository(),
        governance_dir="missing-governance-dir",
        year=2027,
        as_of_date="2027-12-31",
        result_kind="monthly",
        dimension="",
        business_key="",
        effective_ftp_rate_pct=Decimal("1.6000"),
    )

    assert received[0]["effective_ftp_rate_pct"] == Decimal("1.6000")


def test_precompute_classification_matches_live_when_only_formal_metadata_is_available() -> None:
    pnl_row = {
        "source_kind": "formal_fi",
        "report_date": "2026-06-30",
        "instrument_code": "P001",
        "instrument_name": "政策性金融债测试券",
        "portfolio_name": "FI Desk",
        "cost_center": "CC-POLICY",
        "currency_basis": "CNY",
        "invest_type_std": "T",
        "accounting_basis": "FVTPL",
        "asset_class": "政策性金融债",
    }
    kwargs = {
        "pnl_row": pnl_row,
        "balance_lookup": {},
        "historical_balance_lookup": {},
        "sub_type_by_date_code": {},
        "fallback_date": "2026-06-30",
    }

    live = pnl_service_module._analysis_classification_for_pnl_row(**kwargs)
    precomputed = precompute_module._analysis_classification_for_pnl_row(**kwargs)

    assert precomputed == live
    assert precomputed["asset_class"] == "政策性金融债"
    assert precomputed["instrument_name"] == "政策性金融债测试券"


@pytest.mark.parametrize(
    ("instrument_code", "currency_code", "expected"),
    [
        ("XS2707583121", "USD", ("USD", "美元（折人民币）")),
        ("250001.IB", "CNY", ("CNY", "人民币")),
        ("J11603010202", "", ("USD", "美元（折人民币）")),
    ],
)
def test_live_and_precompute_currency_dimension_prefers_formal_original_currency(
    instrument_code: str,
    currency_code: str,
    expected: tuple[str, str],
) -> None:
    pnl_row = {"instrument_code": instrument_code}
    classification = {"currency_code": currency_code}
    balance_row = {
        "instrument_code": instrument_code,
        "currency_code": currency_code,
    }

    assert pnl_service_module._analysis_dimension_for_pnl_row(
        pnl_row,
        classification,
        "currency",
    ) == expected
    assert precompute_module._analysis_dimension_for_pnl_row(
        pnl_row,
        classification,
        "currency",
    ) == expected
    assert pnl_service_module._analysis_dimension_for_balance_row(
        balance_row,
        "currency",
        {},
    ) == expected
    assert precompute_module._analysis_dimension_for_balance_row(
        balance_row,
        "currency",
        {},
    ) == expected


@pytest.mark.parametrize(
    ("instrument_code", "fx_base_currency", "expected"),
    [
        ("XS2707583121", "USD", ("USD", "美元（折人民币）")),
        ("J11603010202", "", ("USD", "美元（折人民币）")),
    ],
)
def test_live_and_precompute_currency_dimension_preserves_unmatched_pnl_fallback(
    instrument_code: str,
    fx_base_currency: str,
    expected: tuple[str, str],
) -> None:
    pnl_row = {
        "report_date": "2026-06-30",
        "instrument_code": instrument_code,
        "currency_basis": "CNY",
        "fx_base_currency": fx_base_currency,
        "source_kind": "formal_fi",
        "invest_type_std": "非金融企业债券",
    }

    for module in (pnl_service_module, precompute_module):
        classification = module._analysis_classification_for_pnl_row(
            pnl_row=pnl_row,
            balance_lookup={},
            sub_type_by_date_code={},
            fallback_date="2026-06-30",
        )
        assert module._analysis_dimension_for_pnl_row(
            pnl_row,
            classification,
            "currency",
        ) == expected


@pytest.mark.parametrize(
    ("report_year", "expected_rate_pct"),
    [
        (2025, Decimal("1.75")),
        (2026, Decimal("1.60")),
    ],
)
def test_precompute_ftp_values_match_core_finance_function(report_year, expected_rate_pct):
    total_pnl = Decimal("130000")
    avg_balance = Decimal("100000000")
    calendar_days = 31

    ftp_rate_pct = resolve_product_category_ftp_rate_pct(
        date(report_year, 12, 31), Decimal("9.99")
    )
    assert ftp_rate_pct == expected_rate_pct

    annualized_yield_pct = precompute_module._analysis_annualized_yield_pct(
        total_pnl,
        avg_balance,
        calendar_days,
        ftp_rate_pct,
    )
    ftp_values = precompute_module._analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )

    expected = compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )

    assert annualized_yield_pct == expected.annualized_yield_pct
    assert ftp_values["ftp_rate_pct"] == expected.ftp_rate_pct
    assert ftp_values["ftp_cost"] == expected.ftp_cost
    assert ftp_values["ftp_net_pnl"] == expected.ftp_net_pnl
    assert ftp_values["ftp_net_annualized_yield_pct"] == expected.ftp_net_annualized_yield_pct


def test_precompute_ftp_values_match_core_finance_function_without_denominator():
    total_pnl = Decimal("130000")
    avg_balance = Decimal("0")
    calendar_days = 31
    ftp_rate_pct = Decimal("1.75")

    annualized_yield_pct = precompute_module._analysis_annualized_yield_pct(
        total_pnl,
        avg_balance,
        calendar_days,
        ftp_rate_pct,
    )
    ftp_values = precompute_module._analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )

    expected = compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )

    assert annualized_yield_pct is None
    assert ftp_values["ftp_cost"] is None
    assert ftp_values["ftp_net_pnl"] is None
    assert ftp_values["ftp_net_annualized_yield_pct"] is None
    assert expected.annualized_yield_pct is None


def test_fetch_precompute_returns_none_when_rule_version_mismatches(tmp_path):
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_pnl_by_business_precompute (
                year integer, as_of_date varchar, result_kind varchar,
                dimension varchar, business_key varchar,
                payload_json varchar, source_version varchar, rule_version varchar,
                generated_at timestamp
            )
            """
        )
        conn.execute(
            """
            insert into fact_pnl_by_business_precompute values (
                2025, '2025-12-31', 'monthly', '', '',
                '{"stale": true}', 'sv-anything', 'rv_pnl_by_business_precompute_v4',
                current_timestamp
            )
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    result = repo.fetch_pnl_by_business_precompute(
        year=2025,
        as_of_date="2025-12-31",
        result_kind="monthly",
        dimension="",
        business_key="",
        effective_ftp_rate_pct=Decimal("1.75"),
        expected_rule_version=pnl_repo_module.PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
    )

    assert result is None
    assert pnl_repo_module.PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION != "rv_pnl_by_business_precompute_v4"


def test_formal_fact_rule_gate_rejects_stale_2026_h1_rows(tmp_path) -> None:
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
                report_date varchar,
                interest_income_514 decimal(24, 8),
                fair_value_change_516 decimal(24, 8),
                capital_gain_517 decimal(24, 8),
                manual_adjustment decimal(24, 8),
                total_pnl decimal(24, 8),
                rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values (
                '2026-04-30', 106, 0, 0, 0, 106, 'rv_pnl_phase2_materialize_v1'
            )
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    assert hasattr(repo, "require_formal_pnl_rule_version")
    with pytest.raises(RuntimeError, match="rv_pnl_phase2_materialize_v1"):
        repo.require_formal_pnl_rule_version(
            start_date="2026-01-01",
            end_date="2026-06-30",
            expected_rule_version="rv_pnl_phase2_materialize_v3",
        )


def test_precompute_source_fingerprint_includes_fact_rule_version(tmp_path) -> None:
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
                report_date varchar,
                interest_income_514 decimal(24, 8),
                fair_value_change_516 decimal(24, 8),
                capital_gain_517 decimal(24, 8),
                manual_adjustment decimal(24, 8),
                total_pnl decimal(24, 8),
                rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values (
                '2026-04-30', 100, 0, 0, 0, 100, 'rv_pnl_phase2_materialize_v1'
            )
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    stale_source_version = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            "update fact_formal_pnl_fi set rule_version = 'rv_pnl_phase2_materialize_v3'"
        )
    finally:
        conn.close()

    current_source_version = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
    )
    adjusted_source_version = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
        supplemental_source_version="sv_pnl_by_business_adjustments_v1:test-change",
    )

    assert stale_source_version.startswith("sv_pnl_by_business_precompute_v5:")
    assert current_source_version.startswith("sv_pnl_by_business_precompute_v5:")
    assert stale_source_version != current_source_version
    assert current_source_version != adjusted_source_version
    assert "sv_pnl_by_business_adjustments_v1:test-change" in adjusted_source_version
    assert "rv_pnl_phase2_materialize_v1" in stale_source_version
    assert "rv_pnl_phase2_materialize_v3" in current_source_version


def test_precompute_source_fingerprint_changes_when_balance_currency_changes(tmp_path) -> None:
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
                report_date varchar,
                instrument_code varchar,
                portfolio_name varchar,
                cost_center varchar,
                currency_basis varchar,
                currency_code varchar,
                position_scope varchar,
                market_value_amount decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values (
                '2026-06-30', 'XS2707583121', 'FIOA', 'CC',
                'CNY', 'CNY', 'asset', 100
            )
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    cny_source_version = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            "update fact_formal_zqtz_balance_daily set currency_code = 'USD'"
        )
    finally:
        conn.close()

    usd_source_version = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
    )

    assert cny_source_version != usd_source_version
    assert '"metadata_signature"' in usd_source_version


def test_precompute_source_fingerprint_changes_when_balance_amounts_are_redistributed(
    tmp_path,
) -> None:
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
                report_date varchar,
                instrument_code varchar,
                portfolio_name varchar,
                cost_center varchar,
                currency_basis varchar,
                currency_code varchar,
                position_scope varchar,
                market_value_amount decimal(24, 8)
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
                ('2026-06-30', '250001.IB', 'FIOA', 'CC', 'CNY', 'CNY', 'asset', 100),
                ('2026-06-30', 'XS2707583121', 'FIOA', 'CC', 'CNY', 'USD', 'asset', 200)
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    original_source_version = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set market_value_amount = case
                when currency_code = 'CNY' then market_value_amount + 50
                else market_value_amount - 50
            end
            """
        )
    finally:
        conn.close()

    redistributed_source_version = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
    )

    assert original_source_version != redistributed_source_version


def test_precompute_source_fingerprint_changes_when_pnl_is_redistributed_between_currencies(
    tmp_path,
) -> None:
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
                report_date varchar,
                instrument_code varchar,
                currency_basis varchar,
                fx_base_currency varchar,
                interest_income_514 decimal(24, 8),
                fair_value_change_516 decimal(24, 8),
                capital_gain_517 decimal(24, 8),
                manual_adjustment decimal(24, 8),
                total_pnl decimal(24, 8),
                rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
                ('2026-06-30', '250001.IB', 'CNY', 'CNY', 100, 0, 0, 0, 100,
                 'rv_pnl_phase2_materialize_v3'),
                ('2026-06-30', 'XS2707583121', 'CNY', 'USD', 200, 0, 0, 0, 200,
                 'rv_pnl_phase2_materialize_v3')
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    original_source_version = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_pnl_fi
            set interest_income_514 = case
                    when fx_base_currency = 'CNY' then interest_income_514 + 50
                    else interest_income_514 - 50
                end,
                total_pnl = case
                    when fx_base_currency = 'CNY' then total_pnl + 50
                    else total_pnl - 50
                end
            """
        )
    finally:
        conn.close()

    redistributed_source_version = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-06-30",
        effective_ftp_rate_pct=Decimal("1.60"),
    )

    assert original_source_version != redistributed_source_version
