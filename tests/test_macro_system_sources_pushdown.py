"""Equivalence tests for the alias-lookup SQL pushdown in system_sources.

``load_series_by_alias`` no longer materializes the full system macro frame;
it resolves aliases through a distinct-identity catalog and loads only the
matched series ids from SQL. These tests pin that the pushdown result is
row-for-row identical to the historical full-frame algorithm (load everything,
match aliases per row, then filter/sort/dedupe), and that cache keys follow
the (path, mtime, size, series_ids) parameters without cross-alias leakage.
"""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest

import backend.app.core_finance.macro.toolkit.system_sources as system_sources
from backend.app.core_finance.macro.toolkit.system_sources import (
    load_series_by_alias,
    load_series_by_aliases,
    load_system_macro_frame,
)
from tests.test_macro_toolkit_scripts import _seed_choice_tushare_macro_db

_FULL_FRAME_COLUMNS = [
    "series_id",
    "series_name",
    "vendor_name",
    "trade_date",
    "value_numeric",
    "frequency",
    "unit",
    "source_version",
    "vendor_version",
    "rule_version",
    "run_id",
    "vendor_series_code",
    "source_priority",
]

# Aliases covering every source table and alias-resolution mode: direct
# series_id, series_name, vendor_series_code, legacy alias candidates,
# and expanded vendor aliases (six-digit code / futures product forms).
_ALIAS_BATTERY = (
    "sh000300",
    "000300.SH",
    "CA.CSI300",
    "CU0",
    "cu0.shf",
    "M0067855",
    "USD/CNY",
    "S0059747",
    "S0059760",
    "M0041653",
    "M0001227",
    "M0001385",
    "cn_cpi_yoy",
    "CA.DR007",
    "NH0100.NHF",
    "unknown-alias-without-rows",
)


def _reference_series_by_alias(
    alias: str,
    *,
    duckdb_path,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Historical full-frame algorithm, kept as the equivalence oracle."""
    frame = load_system_macro_frame(duckdb_path)
    if frame.empty:
        return system_sources._empty_series_frame()
    candidates = system_sources._candidate_aliases(alias)
    row_positions = [
        position
        for position, (_, row) in enumerate(frame.iterrows())
        if candidates & system_sources._row_aliases(row)
    ]
    if not row_positions:
        return system_sources._empty_series_frame()
    selected = frame.iloc[row_positions].copy()
    if start:
        selected = selected[selected["trade_date"] >= pd.to_datetime(start, errors="coerce")]
    if end:
        selected = selected[selected["trade_date"] <= pd.to_datetime(end, errors="coerce")]
    if selected.empty:
        return system_sources._empty_series_frame()
    selected = selected.sort_values(["trade_date", "source_priority"]).drop_duplicates("trade_date", keep="first")
    return selected[["trade_date", "value_numeric", "series_id", "vendor_name"]].rename(
        columns={"trade_date": "date", "value_numeric": "value"},
    )


def _seed_commodity_table(path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_commodity_futures_daily (
              trade_date varchar not null,
              product_code varchar not null,
              contract_code varchar,
              exchange varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              settle_value double,
              volume double,
              open_interest double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar default 'rv_commodity_daily_v1',
              created_at timestamp default current_timestamp,
              primary key (trade_date, product_code)
            )
            """
        )
        conn.execute(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange,
              open_value, high_value, low_value, close_value, settle_value,
              volume, open_interest, source_version, vendor_version, rule_version
            ) values
              ('2026-04-09', 'NHCI', 'NHCI.NH', 'NH',
               2980.0, 3005.0, 2970.0, 2989.18, null,
               null, null, 'sv_tushare_index_daily_nhci', 'vv_tushare_index_daily_NHCI_20260410',
               'rv_commodity_daily_v1'),
              ('2026-04-09', 'CU', 'CU2606.SHF', 'SHF',
               81000.0, 81500.0, 80800.0, 81200.0, 81150.0,
               120.0, 300.0, 'sv_tushare_fut_daily_cu', 'vv_tushare_fut_daily_CU_20260410',
               'rv_commodity_daily_v1')
            """
        )
    finally:
        conn.close()


@pytest.fixture()
def seeded_duckdb(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    _seed_commodity_table(duckdb_path)
    system_sources.clear_system_macro_source_cache()
    yield duckdb_path
    system_sources.clear_system_macro_source_cache()


@pytest.mark.parametrize("alias", _ALIAS_BATTERY)
def test_pushdown_alias_lookup_matches_full_frame_reference(seeded_duckdb, alias) -> None:
    pushed = load_series_by_alias(alias, duckdb_path=seeded_duckdb)
    reference = _reference_series_by_alias(alias, duckdb_path=seeded_duckdb)

    pd.testing.assert_frame_equal(
        pushed.reset_index(drop=True),
        reference.reset_index(drop=True),
        check_dtype=False,
    )
    assert list(pushed.columns) == ["date", "value", "series_id", "vendor_name"]


def test_pushdown_alias_lookup_matches_reference_with_date_bounds(seeded_duckdb) -> None:
    for start, end in (("2026-04-10", None), (None, "2026-04-09"), ("2026-04-01", "2026-04-30")):
        pushed = load_series_by_alias("sh000300", duckdb_path=seeded_duckdb, start=start, end=end)
        reference = _reference_series_by_alias("sh000300", duckdb_path=seeded_duckdb, start=start, end=end)
        pd.testing.assert_frame_equal(
            pushed.reset_index(drop=True),
            reference.reset_index(drop=True),
            check_dtype=False,
        )


def test_batch_alias_lookup_matches_single_alias_results(seeded_duckdb) -> None:
    aliases = ("sh000300", "CU0", "M0067855", "S0059747", "unknown-alias-without-rows")
    batch = load_series_by_aliases(
        aliases,
        duckdb_path=seeded_duckdb,
        start="2026-04-01",
        end="2026-04-30",
    )

    assert set(batch) == set(aliases)
    for alias in aliases:
        single = load_series_by_alias(
            alias,
            duckdb_path=seeded_duckdb,
            start="2026-04-01",
            end="2026-04-30",
        )
        pd.testing.assert_frame_equal(
            batch[alias].reset_index(drop=True),
            single.reset_index(drop=True),
            check_dtype=False,
        )


def test_batch_alias_lookup_loads_one_subset_frame(seeded_duckdb, monkeypatch) -> None:
    original_load_system_macro_frame = system_sources.load_system_macro_frame
    calls: list[tuple[str, ...] | None] = []

    def counting_load_system_macro_frame(duckdb_path=None, *, series_ids=None):
        calls.append(series_ids)
        return original_load_system_macro_frame(duckdb_path, series_ids=series_ids)

    monkeypatch.setattr(system_sources, "load_system_macro_frame", counting_load_system_macro_frame)
    system_sources.clear_system_macro_source_cache()

    batch = load_series_by_aliases(("sh000300", "CU0", "M0067855"), duckdb_path=seeded_duckdb)

    assert all(not batch[alias].empty for alias in ("sh000300", "CU0", "M0067855"))
    assert len(calls) == 1
    assert calls[0] is not None
    assert len(calls[0]) > 1


def test_filtered_frame_matches_full_frame_slice_and_keeps_all_columns(seeded_duckdb) -> None:
    full = load_system_macro_frame(seeded_duckdb)
    subset = load_system_macro_frame(seeded_duckdb, series_ids=("CA.CSI300",))

    assert list(subset.columns) == list(full.columns) == _FULL_FRAME_COLUMNS
    expected = full[full["series_id"] == "CA.CSI300"].reset_index(drop=True)
    pd.testing.assert_frame_equal(subset.reset_index(drop=True), expected, check_dtype=False)


def test_alias_lookups_do_not_cross_contaminate_cached_subsets(seeded_duckdb) -> None:
    copper_before = load_series_by_alias("CU0", duckdb_path=seeded_duckdb)
    hs300 = load_series_by_alias("sh000300", duckdb_path=seeded_duckdb)
    copper_after = load_series_by_alias("CU0", duckdb_path=seeded_duckdb)

    assert hs300["series_id"].tolist() == ["CA.CSI300"]
    pd.testing.assert_frame_equal(
        copper_before.reset_index(drop=True),
        copper_after.reset_index(drop=True),
    )
    # Cached subset frames stay immutable for later full-frame consumers.
    full = load_system_macro_frame(seeded_duckdb)
    assert {"CA.CSI300", "CA.COPPER"}.issubset(set(full["series_id"]))


def test_alias_lookup_isolates_different_duckdb_paths(tmp_path) -> None:
    path_a = tmp_path / "a.duckdb"
    path_b = tmp_path / "b.duckdb"
    _seed_choice_tushare_macro_db(path_a)
    _seed_choice_tushare_macro_db(path_b)
    system_sources.clear_system_macro_source_cache()

    conn = duckdb.connect(str(path_b), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('ONLY.IN.B', 'Only in database B', '2026-06-01', 12.5, 'daily', 'index',
               'sv_b', 'vv_b', 'rv_b', 'ok', 'run-b')
            """
        )
    finally:
        conn.close()

    in_a = load_series_by_alias("ONLY.IN.B", duckdb_path=path_a)
    in_b = load_series_by_alias("ONLY.IN.B", duckdb_path=path_b)

    assert in_a.empty
    assert in_b["value"].tolist() == [12.5]
    system_sources.clear_system_macro_source_cache()
