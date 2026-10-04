from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from backend.app.tasks import choice_macro as task

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_macro_data]
TABLES = ('fact_choice_macro_daily', 'choice_market_snapshot', 'phase1_macro_vendor_catalog', 'market_data_series_category')


@pytest.fixture
def fx_scope(tmp_path, monkeypatch):
    import akshare
    path = tmp_path / 'fx.duckdb'
    with duckdb.connect(str(path)) as conn:
        task._ensure_tables(conn)
    records = [{'日期': '2026-09-15', '美元': 676.7}, {'日期': '2026-09-16', '美元': 676.28}, {'日期': '2026-09-17', '美元': 677.0}]
    monkeypatch.setattr(akshare, 'currency_boc_safe', lambda: pd.DataFrame(records))
    def prohibited(*args, **kwargs):
        pytest.fail('FX recovery must not fetch unrelated sources or run migrations')
    monkeypatch.setattr(task, '_load_public_cross_asset_history_rows', prohibited)
    monkeypatch.setattr(task, '_ensure_tables', prohibited)
    return path, records


def state(path):
    with duckdb.connect(str(path), read_only=True) as conn:
        return {t: conn.execute(f'select * from {t} order by all').fetchall() for t in TABLES}


def run(path, **kwargs):
    return task.refresh_public_cross_asset_headlines(duckdb_path=str(path), report_date='2026-09-16', fx_only=True, **kwargs)


def test_fx_recovery_keeps_exact_date_unit_and_source(fx_scope):
    path, _ = fx_scope
    r = run(path)
    assert r['status'] == 'completed'
    assert r['row_count'] == r['series_count'] == r['snapshot_row_count'] == 1
    assert r['scope']['series_ids'] == ['EMM00058124']
    assert r['scope']['value_basis'] == 'CNY per USD'
    with duckdb.connect(str(path), read_only=True) as conn:
        row = conn.execute('select series_id,trade_date,value_numeric,unit,vendor_version from fact_choice_macro_daily').fetchone()
        snapshot = conn.execute('select vendor_name,vendor_series_code from choice_market_snapshot').fetchone()
        catalog = conn.execute('select vendor_name,vendor_series_code,policy_note from phase1_macro_vendor_catalog').fetchone()
    assert snapshot == ('public_currency_boc_safe', 'currency_boc_safe:USD/CNY')
    assert catalog[:2] == snapshot
    assert 'SAFE' in catalog[2] and '100 USD' in catalog[2]
    assert row[:2] == ('EMM00058124', '2026-09-16')
    assert row[2] == pytest.approx(6.7628)
    assert row[3:] == ('CNY/USD', 'vv_public_currency_boc_safe_20260916')


def test_fx_recovery_preserves_history_unrelated_series_and_newer_snapshot(fx_scope):
    path, _ = fx_scope
    run(path)
    with duckdb.connect(str(path)) as conn:
        for table in TABLES:
            conn.execute(f"insert into {table} select * replace ('unrelated' as series_id) from {table}")
        conn.execute("update fact_choice_macro_daily set trade_date='2026-09-15' where series_id='EMM00058124'")
        conn.execute("update choice_market_snapshot set trade_date='2026-09-17' where series_id='EMM00058124'")
    before = state(path)
    assert run(path)['snapshot_row_count'] == 0
    after = state(path)
    assert all(row in after[TABLES[0]] for row in before[TABLES[0]])
    assert len(after[TABLES[0]]) == len(before[TABLES[0]]) + 1
    for table in TABLES[1:]:
        assert after[table] == before[table]
    run(path)
    assert state(path) == after


@pytest.mark.parametrize('invalid', ['missing', 'duplicate', 'null', 'zero', 'negative', 'nan', 'infinite'])
def test_fx_recovery_invalid_source_cannot_write(fx_scope, invalid):
    path, records = fx_scope
    run(path)
    before = state(path)
    if invalid == 'missing':
        records.pop(1)
    elif invalid == 'duplicate':
        records.append(dict(records[1]))
    else:
        records[1]['美元'] = {'null': None, 'zero': 0, 'negative': -1, 'nan': float('nan'), 'infinite': float('inf')}[invalid]
    with pytest.raises(ValueError, match='FX recovery'):
        run(path)
    assert state(path) == before


def test_fx_recovery_requires_date_and_single_scope(fx_scope):
    path, _ = fx_scope
    with pytest.raises(ValueError, match='report_date'):
        task.refresh_public_cross_asset_headlines(duckdb_path=str(path), fx_only=True)
    with pytest.raises(ValueError, match='one single-date'):
        run(path, csi300_only=True)


def test_fx_recovery_rolls_back_all_tables_on_failure(fx_scope, monkeypatch):
    path, records = fx_scope
    run(path)
    before = state(path)
    records[1]['美元'] = 700
    def fail(*args, **kwargs):
        raise RuntimeError('catalog write failed')
    monkeypatch.setattr(task, '_insert_market_data_series_category', fail)
    with pytest.raises(RuntimeError, match='catalog write'):
        run(path)
    assert state(path) == before
