"""Comparison uses valid-date union but retains raw end-date/LOCF evidence."""
from datetime import date

import pandas as pd
import pytest

from backend.app.services import adb_analysis_service as adb

START, END = date(2026, 9, 28), date(2026, 9, 30)


def bonds(rows):
    return pd.DataFrame([dict(report_date=pd.Timestamp(day), market_value=amount,
        market_value_is_valid=valid, is_issued=False, bond_category=category,
        yield_to_maturity=.03, coupon_rate=3, interest_rate=3, asset_class='asset')
        for day, amount, valid, category in rows])


def interbank(rows):
    return pd.DataFrame([dict(report_date=pd.Timestamp(day), amount=amount,
        amount_is_valid=valid, direction='LIABILITY', product_type='synthetic', interest_rate=2)
        for day, amount, valid in rows])


def comparison(monkeypatch, b, i, *, end=END, simulate=False):
    monkeypatch.setattr(adb, '_load_adb_raw_data', lambda *a: (b, i, ['sv_synthetic'], ['rv_synthetic'], 'snapshot_calendar', ['synthetic'], {}))
    return adb.get_adb_comparison('never-opened', START, end, simulate_if_single_snapshot=simulate)[0]


def test_valid_dates_union_includes_zero_and_excludes_invalid_dates(monkeypatch):
    b = bonds([(START, 100, True, 'same'), ('2026-09-29', 0, True, 'same'), (END, 999, False, 'same')])
    i = interbank([('2026-09-29', 40, True), (END, 999, False)])
    payload = comparison(monkeypatch, b, i)
    assert payload['coverage_days'] == 2
    assert payload['total_avg_assets'] == 50 and payload['total_avg_liabilities'] == 20
    assert payload['sample_filled'] is True


@pytest.mark.parametrize('invalid', [None, float('nan'), float('inf'), float('-inf'), 'bad'])
def test_finite_admission_ignores_explicit_valid_flag_for_bad_amount(monkeypatch, invalid):
    b = bonds([(START, 100, True, 'synthetic'), (END, invalid, True, 'synthetic')])
    payload = comparison(monkeypatch, b, pd.DataFrame())
    assert payload['coverage_days'] == 1
    assert payload['total_avg_assets'] == 100


@pytest.mark.parametrize('end_state, expected', [('missing', 100), ('invalid-same', 100), ('different-only', 50)])
def test_raw_end_presence_controls_existing_locf_contract(monkeypatch, end_state, expected):
    rows = [(START, 100, True, 'prior')]
    if end_state == 'invalid-same':
        rows.append((END, None, False, 'prior'))
    if end_state == 'different-only':
        rows.append((END, 50, True, 'different'))
    payload = comparison(monkeypatch, bonds(rows), pd.DataFrame())
    assert payload['total_spot_assets'] == expected


@pytest.mark.parametrize('simulate', [False, True])
def test_single_day_contract_stays_explicit(monkeypatch, simulate):
    payload = comparison(monkeypatch, bonds([(START, 100, True, 'synthetic')]), pd.DataFrame(), end=START, simulate=simulate)
    assert payload['coverage_days'] == 1
    assert payload['simulated'] is simulate
    assert (payload['total_avg_assets'] is None) is (not simulate)


def test_only_two_valid_balance_filters_are_needed(monkeypatch):
    original = adb._comparison_valid_balance_rows
    calls = []
    def count(frame, **kwargs):
        calls.append(kwargs['amount_attr'])
        return original(frame, **kwargs)
    monkeypatch.setattr(adb, '_comparison_valid_balance_rows', count)
    comparison(monkeypatch, bonds([(START, 100, True, 'synthetic')]), interbank([(END, 40, True)]))
    assert calls == ['market_value', 'amount']
