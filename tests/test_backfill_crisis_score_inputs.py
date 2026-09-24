from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest

from backend.app.tasks.macro_backfill import BackfillRow
from backend.scripts.backfill_crisis_score_inputs import (
    CRISIS_SCORE_INPUT_SPECS,
    backfill_crisis_score_inputs,
    fetch_reverse_repo_7d_carry_forward_rows,
)
from backend.scripts.backfill_cross_asset_macro_environment import MacroRow


def test_dry_run_lists_all_crisis_inputs(tmp_path: Path) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.touch()

    payload = backfill_crisis_score_inputs(
        duckdb_path=str(db_path),
        start_date="2024-06-11",
        end_date="2024-06-30",
        dry_run=True,
    )

    assert payload["dry_run"] is True
    assert payload["input_count"] == len(CRISIS_SCORE_INPUT_SPECS)
    assert [item["alias"] for item in payload["inputs"]] == [spec.alias for spec in CRISIS_SCORE_INPUT_SPECS]
    assert payload["inputs"][0]["field"] == "hs300"
    assert payload["inputs"][0]["kind"] == "tushare_csi300"
    reverse_repo = next(item for item in payload["inputs"] if item["alias"] == "M0041653")
    assert reverse_repo["vendor_series_code"] == "EMM00088132"
    assert reverse_repo["series_id"] == "EMM00088132"


def test_dry_run_aliases_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.touch()

    payload = backfill_crisis_score_inputs(
        duckdb_path=str(db_path),
        start_date="2024-06-11",
        end_date="2024-06-30",
        dry_run=True,
        aliases=["S0059747", "DR007.IB"],
    )

    assert payload["input_count"] == 2
    assert [item["alias"] for item in payload["inputs"]] == ["S0059747", "DR007.IB"]


def test_invalid_alias_raises() -> None:
    with pytest.raises(ValueError, match="No crisis score inputs matched"):
        backfill_crisis_score_inputs(
            duckdb_path="missing.duckdb",
            dry_run=True,
            aliases=["unknown.alias"],
        )


def test_end_before_start_raises() -> None:
    with pytest.raises(ValueError, match="end_date must be on or after start_date"):
        backfill_crisis_score_inputs(
            duckdb_path="missing.duckdb",
            start_date="2026-06-01",
            end_date="2026-05-01",
            dry_run=True,
        )


def test_backfill_choice_edb_writes_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"

    mocked_rows = [
        BackfillRow(
            series_id="EMM00166462",
            series_name="中债国债到期收益率:5年",
            trade_date="2024-06-11",
            value_numeric=2.31,
            frequency="daily",
            unit="%",
        ),
        BackfillRow(
            series_id="EMM00166462",
            series_name="中债国债到期收益率:5年",
            trade_date="2024-06-12",
            value_numeric=2.33,
            frequency="daily",
            unit="%",
        ),
    ]

    with patch(
        "backend.scripts.backfill_crisis_score_inputs._fetch_from_choice_edb",
        return_value=mocked_rows,
    ):
        payload = backfill_crisis_score_inputs(
            duckdb_path=str(db_path),
            start_date="2024-06-11",
            end_date="2024-06-12",
            aliases=["S0059747"],
        )

    assert payload["errors"] == {}
    result = payload["results"]["S0059747"]
    assert result["status"] == "completed"
    assert result["written_rows"] == 2

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        count = conn.execute(
            """
            select count(*)
            from fact_choice_macro_daily
            where series_id = 'EMM00166462'
              and trade_date between '2024-06-11' and '2024-06-12'
            """
        ).fetchone()[0]
    finally:
        conn.close()
    assert int(count) == 2


def test_backfill_public_dr007_writes_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    mocked_rows = [
        MacroRow(
            series_id="CA.DR007",
            series_name="存款类机构质押式回购加权利率:DR007",
            vendor_series_code="repo_rate_hist:FDR007",
            vendor_name="public_repo_rate_query",
            trade_date="2024-06-11",
            value_numeric=1.82,
            frequency="daily",
            unit="%",
            source_version="sv_public_repo_dr007_test",
            vendor_version="vv_public_repo_dr007_test",
        )
    ]

    with patch(
        "backend.scripts.backfill_crisis_score_inputs.fetch_public_dr007_rows",
        return_value=mocked_rows,
    ):
        payload = backfill_crisis_score_inputs(
            duckdb_path=str(db_path),
            start_date="2024-06-11",
            end_date="2024-06-11",
            aliases=["DR007.IB"],
        )

    assert payload["errors"] == {}
    result = payload["results"]["DR007.IB"]
    assert result["status"] == "completed"
    assert result["written_rows"] == 1


def test_fetch_reverse_repo_7d_carry_forward_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
                series_id varchar,
                series_name varchar,
                vendor_name varchar,
                vendor_series_code varchar,
                trade_date date,
                value_numeric double,
                frequency varchar,
                unit varchar,
                source_version varchar,
                vendor_version varchar,
                rule_version varchar,
                quality_flag varchar,
                run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('legacy.wind_market_db.reverse_repo_7d', 'Open market reverse repo 7D', 'moss_derived',
             'legacy.wind_market_db.reverse_repo_7d', '2026-04-30', 1.4763, 'daily', '%',
             'sv_test', 'vv_test', 'rv_test', 'ok', 'run_test')
            """
        )
    finally:
        conn.close()

    rows = fetch_reverse_repo_7d_carry_forward_rows(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-03",
    )

    assert len(rows) == 3
    assert [row.trade_date for row in rows] == ["2026-05-01", "2026-05-02", "2026-05-03"]
    assert all(row.value_numeric == 1.4763 for row in rows)
    assert all(row.series_id == "cn_repo_7d" for row in rows)


def test_backfill_reverse_repo_does_not_silently_carry_forward(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
                series_id varchar,
                series_name varchar,
                vendor_name varchar,
                vendor_series_code varchar,
                trade_date date,
                value_numeric double,
                frequency varchar,
                unit varchar,
                source_version varchar,
                vendor_version varchar,
                rule_version varchar,
                quality_flag varchar,
                run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('legacy.wind_market_db.reverse_repo_7d', 'Open market reverse repo 7D', 'moss_derived',
             'legacy.wind_market_db.reverse_repo_7d', '2026-04-30', 1.4763, 'daily', '%',
             'sv_test', 'vv_test', 'rv_test', 'ok', 'run_test')
            """
        )
    finally:
        conn.close()

    with patch(
        "backend.scripts.backfill_crisis_score_inputs._fetch_choice_edb_rows",
        side_effect=RuntimeError("no data"),
    ), patch(
        "backend.scripts.backfill_crisis_score_inputs.fetch_reverse_repo_7d_carry_forward_rows",
    ) as carry_mock, patch(
        "backend.scripts.backfill_crisis_score_inputs.persist_macro_environment_rows",
    ) as persist_mock:
        payload = backfill_crisis_score_inputs(
            duckdb_path=str(db_path),
            start_date="2026-05-01",
            end_date="2026-05-03",
            aliases=["M0041653"],
        )

    assert payload["errors"] == {"M0041653": "no data"}
    assert payload["results"]["M0041653"]["status"] == "error"
    carry_mock.assert_not_called()
    persist_mock.assert_not_called()


def test_backfill_reverse_repo_persists_real_choice_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    choice_rows = [
        BackfillRow(
            series_id="EMM00088132",
            series_name="公开市场操作:逆回购:7天:中标利率",
            trade_date="2026-05-02",
            value_numeric=1.4,
            frequency="daily",
            unit="%",
        )
    ]

    with patch(
        "backend.scripts.backfill_crisis_score_inputs._fetch_choice_edb_rows",
        return_value=choice_rows,
    ), patch(
        "backend.scripts.backfill_crisis_score_inputs.persist_macro_environment_rows",
        return_value=1,
    ) as persist_mock:
        payload = backfill_crisis_score_inputs(
            duckdb_path=str(db_path),
            start_date="2026-05-01",
            end_date="2026-05-03",
            aliases=["M0041653"],
        )

    assert payload["errors"] == {}
    assert payload["results"]["M0041653"]["status"] == "completed"
    assert payload["results"]["M0041653"]["written_rows"] == 1
    assert persist_mock.call_count == 1


def test_cli_dry_run_argparse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.touch()
    captured: dict[str, object] = {}

    def fake_backfill(**kwargs):
        captured.update(kwargs)
        return {"dry_run": True, "input_count": 1}

    monkeypatch.setattr(
        "backend.scripts.backfill_crisis_score_inputs.backfill_crisis_score_inputs",
        fake_backfill,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "backfill_crisis_score_inputs.py",
            "--duckdb-path",
            str(db_path),
            "--start-date",
            "2024-06-11",
            "--end-date",
            date.today().isoformat(),
            "--dry-run",
            "--aliases",
            "sh000300",
        ],
    )

    from backend.scripts import backfill_crisis_score_inputs as module

    module.main()

    assert captured["dry_run"] is True
    assert captured["start_date"] == "2024-06-11"
    assert captured["aliases"] == ["sh000300"]
