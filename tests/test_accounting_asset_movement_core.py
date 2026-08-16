from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.accounting_asset_movement import (
    DEFAULT_RELATIVE_TOLERANCE,
    POSITION_SOURCE_UNAVAILABLE,
    GlAccountingAssetBalance,
    ZqtzAccountingAssetBalance,
    apply_chain_continuity_status,
    build_accounting_asset_movement_rows,
    build_accounting_asset_movement_summary,
    effective_tolerance,
    evaluate_chain_continuity,
)


def test_monthly_accounting_asset_movement_uses_gl_control_and_excludes_oci_equity():
    report_date = date(2026, 2, 28)
    rows = build_accounting_asset_movement_rows(
        report_date=report_date,
        zqtz_rows=[
            ZqtzAccountingAssetBalance(
                report_date=report_date,
                accounting_basis="FVTPL",
                market_value_amount=Decimal("110"),
                amortized_cost_amount=Decimal("100"),
            ),
            ZqtzAccountingAssetBalance(
                report_date=report_date,
                accounting_basis="AC",
                market_value_amount=Decimal("260"),
                amortized_cost_amount=Decimal("265"),
            ),
            ZqtzAccountingAssetBalance(
                report_date=report_date,
                accounting_basis="FVOCI",
                market_value_amount=Decimal("80"),
                amortized_cost_amount=Decimal("75"),
            ),
        ],
        gl_rows=[
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14101010001",
                beginning_balance=Decimal("100"),
                ending_balance=Decimal("110"),
            ),
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14201010001",
                beginning_balance=Decimal("200"),
                ending_balance=Decimal("220"),
            ),
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14301010001",
                beginning_balance=Decimal("40"),
                ending_balance=Decimal("52.2054"),
            ),
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14301010002",
                beginning_balance=Decimal("2"),
                ending_balance=Decimal("3.0419"),
            ),
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14301040001",
                beginning_balance=Decimal("8"),
                ending_balance=Decimal("0"),
            ),
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14401010001",
                beginning_balance=Decimal("70"),
                ending_balance=Decimal("80"),
            ),
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14402010001",
                beginning_balance=Decimal("5"),
                ending_balance=Decimal("6"),
            ),
        ],
    )

    by_bucket = {row.basis_bucket: row for row in rows}

    assert by_bucket["TPL"].previous_balance == Decimal("100")
    assert by_bucket["TPL"].current_balance == Decimal("110")
    assert by_bucket["TPL"].balance_change == Decimal("10")
    assert by_bucket["TPL"].zqtz_amount == Decimal("110")
    assert by_bucket["TPL"].gl_amount == Decimal("110")
    assert by_bucket["TPL"].reconciliation_status == "matched"

    assert by_bucket["AC"].current_balance == Decimal("275.2473")
    assert by_bucket["AC"].balance_change == Decimal("25.2473")
    assert by_bucket["AC"].zqtz_amount == Decimal("265")
    assert by_bucket["AC"].reconciliation_diff == Decimal("-10.2473")
    assert by_bucket["AC"].reconciliation_status == "mismatch"

    assert by_bucket["OCI"].current_balance == Decimal("80")
    assert by_bucket["OCI"].balance_change == Decimal("10")
    assert by_bucket["OCI"].zqtz_amount == Decimal("80")
    assert by_bucket["OCI"].reconciliation_status == "matched"

    summary = build_accounting_asset_movement_summary(rows)
    assert summary.previous_balance_total == Decimal("420")
    assert summary.current_balance_total == Decimal("465.2473")
    assert summary.balance_change_total == Decimal("45.2473")
    assert summary.zqtz_amount_total == Decimal("455")
    assert summary.reconciliation_diff_total == Decimal("-10.2473")
    assert summary.matched_bucket_count == 2
    assert summary.bucket_count == 3


def test_monthly_accounting_asset_movement_flags_zqtz_diagnostic_mismatch():
    report_date = date(2026, 2, 28)
    rows = build_accounting_asset_movement_rows(
        report_date=report_date,
        zqtz_rows=[
            ZqtzAccountingAssetBalance(
                report_date=report_date,
                accounting_basis="FVTPL",
                market_value_amount=Decimal("111"),
                amortized_cost_amount=Decimal("100"),
            ),
        ],
        gl_rows=[
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14101010001",
                beginning_balance=Decimal("100"),
                ending_balance=Decimal("110"),
            ),
        ],
        tolerance=Decimal("0.01"),
    )

    tpl = next(row for row in rows if row.basis_bucket == "TPL")
    assert tpl.zqtz_amount == Decimal("111")
    assert tpl.gl_amount == Decimal("110")
    assert tpl.reconciliation_diff == Decimal("1")
    assert tpl.reconciliation_status == "mismatch"


def test_effective_tolerance_scales_with_position_size():
    # 小额：绝对下限占优。
    assert effective_tolerance(left=Decimal("100"), right=Decimal("110")) == Decimal("0.01")
    # 千亿级：相对容差占优，1e-6 * 1.5e11 = 150000。
    assert effective_tolerance(
        left=Decimal("150000000000"),
        right=Decimal("150000000000"),
    ) == Decimal("150000.000000")
    # 单边为 0 时用较大的一侧做基数，容差不会塌回绝对下限。
    assert effective_tolerance(left=Decimal("0"), right=Decimal("150000000000")) == Decimal(
        "150000.000000"
    )
    assert DEFAULT_RELATIVE_TOLERANCE == Decimal("0.000001")


def test_missing_position_source_never_reports_matched():
    """两侧同时为 0 时旧逻辑判 matched；头寸源整体缺失必须落到 gl_only。"""
    report_date = date(2026, 2, 28)
    rows = build_accounting_asset_movement_rows(
        report_date=report_date,
        zqtz_rows=[],
        gl_rows=[
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14101010001",
                beginning_balance=Decimal("0"),
                ending_balance=Decimal("0"),
            ),
        ],
        position_source_available=False,
    )

    assert {row.reconciliation_status for row in rows} == {"gl_only"}
    assert build_accounting_asset_movement_summary(rows).matched_bucket_count == 0
    # 缺失当期必须写哨兵值，读取端才能把 zqtz_amount / reconciliation_diff 当作
    # "无对手方"而不是真实差额呈现。
    assert {row.position_source_basis for row in rows} == {POSITION_SOURCE_UNAVAILABLE}


def test_position_source_basis_records_the_currency_basis_actually_used():
    report_date = date(2026, 2, 28)
    rows = build_accounting_asset_movement_rows(
        report_date=report_date,
        zqtz_rows=[
            ZqtzAccountingAssetBalance(
                report_date=report_date,
                accounting_basis="FVTPL",
                market_value_amount=Decimal("110"),
                amortized_cost_amount=Decimal("0"),
            ),
        ],
        gl_rows=[
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14101010001",
                beginning_balance=Decimal("100"),
                ending_balance=Decimal("110"),
            ),
        ],
        position_source_basis="CNY",
    )

    assert {row.position_source_basis for row in rows} == {"CNY"}


def test_chain_continuity_flags_month_over_month_gap():
    report_date = date(2026, 2, 28)
    rows = build_accounting_asset_movement_rows(
        report_date=report_date,
        zqtz_rows=[],
        gl_rows=[
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14101010001",
                beginning_balance=Decimal("100"),
                ending_balance=Decimal("110"),
            ),
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14201010001",
                beginning_balance=Decimal("200"),
                ending_balance=Decimal("220"),
            ),
        ],
    )

    breaches = evaluate_chain_continuity(
        rows=rows,
        prior_report_date="2026-01-31",
        prior_current_balances={
            "TPL": Decimal("140"),
            "AC": Decimal("200"),
            "OCI": Decimal("0"),
        },
    )

    by_bucket = {breach.basis_bucket: breach for breach in breaches}
    assert set(by_bucket) == {"TPL"}
    assert by_bucket["TPL"].prior_report_date == "2026-01-31"
    assert by_bucket["TPL"].prior_current_balance == Decimal("140")
    assert by_bucket["TPL"].reported_previous_balance == Decimal("100")
    assert by_bucket["TPL"].gap == Decimal("-40")


def _chain_status_fixture_rows(report_date: date):
    """TPL 对得上、AC 对不平、OCI 只有总账——三种横截面结论各一行。"""
    return build_accounting_asset_movement_rows(
        report_date=report_date,
        zqtz_rows=[
            ZqtzAccountingAssetBalance(
                report_date=report_date,
                accounting_basis="FVTPL",
                market_value_amount=Decimal("110"),
                amortized_cost_amount=Decimal("0"),
            ),
            ZqtzAccountingAssetBalance(
                report_date=report_date,
                accounting_basis="AC",
                market_value_amount=Decimal("0"),
                amortized_cost_amount=Decimal("300"),
            ),
        ],
        gl_rows=[
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14101010001",
                beginning_balance=Decimal("100"),
                ending_balance=Decimal("110"),
            ),
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14201010001",
                beginning_balance=Decimal("200"),
                ending_balance=Decimal("220"),
            ),
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14401010001",
                beginning_balance=Decimal("70"),
                ending_balance=Decimal("80"),
            ),
        ],
        position_source_basis="CNY",
    )


def test_chain_break_downgrades_matched_but_keeps_richer_verdicts():
    """gl_only / mismatch / chain_broken 必须是三个可区分的结论。

    跨月断裂不得让"真的对不平"和"根本没有对手方"塌成同一个词：只有原本会显示
    成已对平的行才被降级，其余保留信息量更大的横截面判决。
    """
    report_date = date(2026, 2, 28)
    rows = _chain_status_fixture_rows(report_date)
    prior_balances = {
        "TPL": Decimal("140"),
        "AC": Decimal("400"),
        "OCI": Decimal("70"),
    }
    breaches = evaluate_chain_continuity(
        rows=rows,
        prior_report_date="2026-01-31",
        prior_current_balances=prior_balances,
    )

    updated = apply_chain_continuity_status(
        rows,
        breaches=breaches,
        prior_report_date="2026-01-31",
        prior_current_balances=prior_balances,
    )
    by_bucket = {row.basis_bucket: row for row in updated}

    assert by_bucket["TPL"].reconciliation_status == "chain_broken"
    assert by_bucket["TPL"].chain_status == "broken"
    assert by_bucket["AC"].reconciliation_status == "mismatch"
    assert by_bucket["AC"].chain_status == "broken"
    assert by_bucket["OCI"].reconciliation_status == "gl_only"
    assert by_bucket["OCI"].chain_status == "continuous"
    assert build_accounting_asset_movement_summary(updated).matched_bucket_count == 0


def test_chain_status_is_no_prior_month_without_a_comparable_baseline():
    report_date = date(2026, 1, 31)
    rows = _chain_status_fixture_rows(report_date)

    updated = apply_chain_continuity_status(
        rows,
        breaches=[],
        prior_report_date=None,
        prior_current_balances={},
    )

    assert {row.chain_status for row in updated} == {"no_prior_month"}
    # 没有可比基准不是"断裂"，横截面判决不得被改写。
    assert {row.basis_bucket: row.reconciliation_status for row in updated} == {
        "TPL": "matched",
        "AC": "mismatch",
        "OCI": "gl_only",
    }


def test_chain_status_skips_buckets_absent_from_the_prior_month():
    """判定口径必须与 evaluate_chain_continuity 的跳过规则一致。"""
    report_date = date(2026, 2, 28)
    rows = _chain_status_fixture_rows(report_date)
    prior_balances = {"TPL": Decimal("100")}

    updated = apply_chain_continuity_status(
        rows,
        breaches=evaluate_chain_continuity(
            rows=rows,
            prior_report_date="2026-01-31",
            prior_current_balances=prior_balances,
        ),
        prior_report_date="2026-01-31",
        prior_current_balances=prior_balances,
    )
    by_bucket = {row.basis_bucket: row.chain_status for row in updated}

    assert by_bucket == {
        "TPL": "continuous",
        "AC": "no_prior_month",
        "OCI": "no_prior_month",
    }


def test_chain_continuity_is_silent_without_a_prior_month():
    report_date = date(2026, 1, 31)
    rows = build_accounting_asset_movement_rows(
        report_date=report_date,
        zqtz_rows=[],
        gl_rows=[
            GlAccountingAssetBalance(
                report_date=report_date,
                account_code="14101010001",
                beginning_balance=Decimal("100"),
                ending_balance=Decimal("110"),
            ),
        ],
    )

    assert (
        evaluate_chain_continuity(
            rows=rows,
            prior_report_date=None,
            prior_current_balances={},
        )
        == []
    )
