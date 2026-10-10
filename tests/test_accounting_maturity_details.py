from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.app.core_finance.accounting_asset_movement import classify_accounting_maturity
from backend.app.services.accounting_asset_movement_service import _build_zqtz_maturity_structure


@pytest.mark.parametrize('days,expected', [(-1, 'overdue_or_matured'), (0, '<=30d'),
    (30, '<=30d'), (31, '31-90d'), (90, '31-90d'), (91, '91d-1y'),
    (365, '91d-1y'), (366, '1-3y'), (1095, '1-3y'), (1096, '3-5y'),
    (1825, '3-5y'), (1826, '>5y')])
def test_maturity_boundaries(days, expected):
    report = date(2026, 8, 31)
    assert classify_accounting_maturity(maturity_date=report + timedelta(days=days),
        report_date=report, instrument_code='BOND', bond_type='国债') == expected


def test_fund_missing_date_and_recorded_overdue_are_distinct():
    rows = [
        dict(instrument_code='SA1', bond_type='其他', amount='100', maturity_date=None),
        dict(instrument_code='B1', bond_type='国债', amount='20', maturity_date='invalid'),
        dict(instrument_code='B2', bond_type='国债', amount='30', maturity_date='2026-08-01',
             overdue_principal_days='30', overdue_interest_days='0'),
        dict(instrument_code='B3', bond_type='国债', amount='40', maturity_date='2026-08-01'),
        dict(instrument_code='SA2', bond_type='其他', amount='10', maturity_date='2026-09-01'),
    ]
    result = _build_zqtz_maturity_structure(report_date='2026-08-31', prior_report_date=None,
        currency_basis='CNX', drilldown_result={'rows': [dict(r, report_date='2026-08-31') for r in rows]})
    buckets = {b.maturity_bucket: b for b in result.buckets}
    assert buckets['fund_no_maturity'].current_amount == 100
    assert buckets['unknown'].current_amount == 20
    assert buckets['<=30d'].current_amount == 10
    assert result.meta.coverage_pct == 40
    assert result.meta.unknown_total == 120
    assert sum(b.current_amount for b in result.buckets) == result.meta.eligible_total == 200
    for bucket in result.buckets:
        assert sum((item.current_amount for item in bucket.items), Decimal(0)) == bucket.current_amount
        assert len(bucket.items) == bucket.item_count
    expired = {i.instrument_code: i for i in buckets['overdue_or_matured'].items}
    assert buckets['overdue_or_matured'].bucket_label == '到期日已过'
    assert expired['B2'].overdue_principal_days == 30
    assert expired['B2'].overdue_interest_days == 0
    assert expired['B3'].overdue_principal_days is None


def test_missing_source_date_column_is_not_reclassified_as_fund():
    result = _build_zqtz_maturity_structure(report_date='2026-08-31', prior_report_date=None,
        currency_basis='CNX', drilldown_result={'missing_columns': ['maturity_date'],
        'rows': [dict(report_date='2026-08-31', instrument_code='SA1', bond_type='其他', amount='100')]})
    buckets = {b.maturity_bucket: b for b in result.buckets}
    assert result.meta.status == 'unsupported_missing_columns'
    assert buckets['unknown'].current_amount == 100
    assert buckets['fund_no_maturity'].current_amount == 0
