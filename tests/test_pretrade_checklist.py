"""盘前操作清单：service 组装逻辑（合成 DuckDB）+ 路由契约。

- service 层用合成库验证：候选取数窗口、停牌共享口径、涨跌停三态
  （stk_limit 数值价 / observation try_cast / 布尔位降级 / unknown）、
  金额门槛（元口径 fail-closed）、复权因子缺口标记、仓位建议透传、
  门控敞口轻读与降级、stale/empty 语义。
- 路由层验证 404（数据面缺失）、403（无读权限）、200（envelope）契约。
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.core_finance.strategy_policy import POLICY
from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.services.pretrade_checklist_service import (
    pretrade_checklist_envelope,
)
from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]

AS_OF = "2026-08-10"
TODAY_FRESH = "2026-08-12"
TODAY_STALE = "2026-08-31"
GATE_EVIDENCE = '{"market_gate": {"state": "WARM", "exposure": 0.5}}'
#: choice_native 代际 vendor（amount 已是元口径，经 amount_rmb_sql 原样透传）。
NATIVE_VENDOR = "vv_choice_stock_20260810_ab12"


def _create_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table livermore_candidate_history (
          snapshot_as_of_date varchar,
          stock_code varchar,
          stock_name varchar,
          candidate_rank integer,
          sector_name varchar,
          selection_close double,
          ema10 double,
          market_state varchar,
          data_status varchar,
          closed_up_limit boolean,
          signal_kind varchar,
          signal_evidence_json varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double,
          amount double,
          tradestatus varchar,
          highlimit varchar,
          lowlimit varchar,
          vendor_version varchar
        )
        """
    )
    conn.execute(
        """
        create table stock_limit_price_daily (
          trade_date varchar,
          stock_code varchar,
          up_limit double,
          down_limit double
        )
        """
    )
    conn.execute(
        """
        create table stock_adjustment_factor (
          stock_code varchar,
          trade_date varchar,
          adj_factor double
        )
        """
    )


def _insert_candidate(
    conn: duckdb.DuckDBPyConnection,
    *,
    rank: int,
    code: str,
    name: str,
    close: float = 10.0,
    ema10: float | None = 9.6,
    closed_up_limit: bool = False,
    signal_kind: str = "factor_screen",
) -> None:
    conn.execute(
        """
        insert into livermore_candidate_history values
        (?, ?, ?, ?, '合成板块', ?, ?, 'WARM', 'completed', ?, ?, ?)
        """,
        [AS_OF, code, name, rank, close, ema10, closed_up_limit, signal_kind, GATE_EVIDENCE],
    )


def _build_synthetic_db(path: Path) -> None:
    """七票覆盖全部三态与检查分支的合成库。

    - 600001 正常可买：stk_limit 数值价内、金额正常、有复权因子；
    - 600002 停牌（共享 is_tradestatus_halted 口径）；
    - 600003 贴涨停板（stk_limit 数值价，close >= up_limit*0.999）；
    - 600004 贴跌停板（新表无行，observation try_cast 数值降级）；
    - 600005 布尔位降级（observation 标志"是"，数值皆缺）；
    - 600006 无当日观测行（数据缺）；
    - 600007 金额无法定标（vendor_version 空 → 元口径 fail-closed NULL）。
    """
    conn = duckdb.connect(str(path))
    try:
        _create_tables(conn)
        _insert_candidate(conn, rank=1, code="600001.SH", name="正常股", close=10.0)
        _insert_candidate(conn, rank=2, code="600002.SH", name="停牌股", close=20.0)
        _insert_candidate(conn, rank=3, code="600003.SH", name="涨停股", close=11.0)
        _insert_candidate(conn, rank=4, code="600004.SH", name="跌停股", close=9.0)
        _insert_candidate(conn, rank=5, code="600005.SH", name="标志股", close=8.0, ema10=None)
        _insert_candidate(conn, rank=6, code="600006.SH", name="缺观测股", close=7.0)
        _insert_candidate(conn, rank=7, code="600007.SH", name="缺金额股", close=6.0)
        # 另一 signal_kind 的行不得进入清单。
        _insert_candidate(conn, rank=1, code="600099.SH", name="其他信号", signal_kind="theme_breakout")

        daily_rows = [
            (AS_OF, "600001.SH", 10.0, 5_000_000.0, "交易", None, None, NATIVE_VENDOR),
            (AS_OF, "600002.SH", 20.0, 1_000_000.0, "停牌一天", None, None, NATIVE_VENDOR),
            (AS_OF, "600003.SH", 11.0, 8_000_000.0, "交易", None, None, NATIVE_VENDOR),
            # tushare 代际旧数值：observation 列可 try_cast 出正数值价。
            (AS_OF, "600004.SH", 9.0, 3_000_000.0, "交易", "11.0", "9.0", NATIVE_VENDOR),
            # choice 代际布尔位："是/否" 无法 cast，降级布尔位判定。
            (AS_OF, "600005.SH", 8.0, 2_000_000.0, "交易", "是", "否", NATIVE_VENDOR),
            (AS_OF, "600007.SH", 6.0, 4_000_000.0, "交易", None, None, None),
        ]
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?)",
            daily_rows,
        )
        conn.executemany(
            "insert into stock_limit_price_daily values (?, ?, ?, ?)",
            [
                (AS_OF, "600001.SH", 11.0, 9.0),
                (AS_OF, "600003.SH", 11.0, 9.0),
            ],
        )
        # 600003 故意不给复权因子 → adj_factor_missing 标记。
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?)",
            [
                ("600001.SH", AS_OF, 1.23),
                ("600002.SH", AS_OF, 1.0),
                ("600004.SH", AS_OF, 1.0),
                ("600005.SH", AS_OF, 1.0),
                ("600006.SH", AS_OF, 1.0),
                ("600007.SH", AS_OF, 1.0),
            ],
        )
    finally:
        conn.close()


def _items_by_code(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {str(item["stock_code"]): item for item in payload["items"]}


@pytest.mark.unit
def test_checklist_assembles_tri_state_and_checks(tmp_path: Path) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)

    envelope = pretrade_checklist_envelope(duckdb_path=db_path, today=TODAY_FRESH)
    assert envelope is not None
    payload = envelope["result"]

    assert payload["as_of_date"] == AS_OF
    assert payload["signal_kind"] == "factor_screen"
    assert payload["checklist_status"] == "ok"
    assert payload["candidate_count"] == 7  # 其他 signal_kind 的行不进入
    items = _items_by_code(payload)
    assert set(items) == {
        "600001.SH", "600002.SH", "600003.SH", "600004.SH",
        "600005.SH", "600006.SH", "600007.SH",
    }

    normal = items["600001.SH"]
    assert normal["buyable_status"] == "buyable"
    assert normal["block_reasons"] == []
    assert normal["limit_check"] == {
        "status": "none", "price_source": "stk_limit", "up_limit": 11.0, "down_limit": 9.0,
    }
    assert normal["amount_rmb"] == 5_000_000.0
    assert normal["adj_factor_missing"] is False

    suspended = items["600002.SH"]
    assert suspended["buyable_status"] == "blocked_suspended"
    assert suspended["is_suspended"] is True
    assert "suspended" in suspended["block_reasons"]

    limit_up = items["600003.SH"]
    assert limit_up["buyable_status"] == "blocked_limit"
    assert limit_up["limit_check"]["status"] == "limit_up"
    assert limit_up["limit_check"]["price_source"] == "stk_limit"
    assert limit_up["adj_factor_missing"] is True
    assert "adj_factor_missing" in limit_up["data_flags"]

    limit_down = items["600004.SH"]
    assert limit_down["buyable_status"] == "blocked_limit"
    assert limit_down["limit_check"]["status"] == "limit_down"
    assert limit_down["limit_check"]["price_source"] == "observation_cast"

    flag_row = items["600005.SH"]
    assert flag_row["buyable_status"] == "blocked_limit"
    assert flag_row["limit_check"]["status"] == "limit_up"
    assert flag_row["limit_check"]["price_source"] == "observation_flag"

    missing_daily = items["600006.SH"]
    assert missing_daily["buyable_status"] == "data_missing"
    assert "missing_daily_observation" in missing_daily["block_reasons"]

    missing_amount = items["600007.SH"]
    assert missing_amount["buyable_status"] == "data_missing"
    assert missing_amount["amount_rmb"] is None  # vendor 无法定标 → 元口径 fail-closed
    assert "missing_amount" in missing_amount["block_reasons"]
    assert "limit_price_missing" in missing_amount["data_flags"]

    summary = payload["summary"]
    assert summary == {
        "buyable_count": 1,
        "blocked_count": 4,  # 停牌 1 + 涨跌停 3
        "review_count": 0,
        "data_missing_count": 2,
    }


@pytest.mark.unit
def test_checklist_position_hint_passthrough_and_gate(tmp_path: Path) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)

    envelope = pretrade_checklist_envelope(duckdb_path=db_path, today=TODAY_FRESH)
    payload = envelope["result"]

    # 仓位建议块透传 position_sizing 当前函数输出（政策口径不在本服务复制）。
    hint = payload["position_size_hint"]
    assert hint["policy_version"] == POLICY.sizing.policy_version
    assert hint["sizing_mode"] == POLICY.sizing.sizing_mode
    assert len(hint["items"]) == 7
    hint_by_code = {item["stock_code"]: item for item in hint["items"]}
    # close=10, ema10=9.6 → stop=4% → rpt/stop 与 compute_position_size_hint_item 同源。
    normal_hint = hint_by_code["600001.SH"]
    assert normal_hint["stop_basis"] == "ema10_stop_ref"
    assert normal_hint["stop_distance_pct"] == pytest.approx(0.04)
    # 门控敞口 0.5 已传入：等权主口径 = 敞口/候选数 = 0.5/7。
    assert normal_hint["equal_weight"] == pytest.approx(0.5 / 7, abs=1e-6)
    assert hint["equal_weight_gate_exposure"] == 0.5
    assert hint["equal_weight_candidate_count"] == 7
    # 每票行内透传同一 hint 对象。
    items = _items_by_code(payload)
    assert items["600001.SH"]["position_hint"] == normal_hint
    # ema10 缺失票种走 fallback 止损距离。
    assert hint_by_code["600005.SH"]["stop_basis"] == "fallback"

    # 门控敞口来自候选历史 signal_evidence_json 的持久化点位。
    assert payload["gate"] == {
        "status": "available",
        "state": "WARM",
        "exposure": 0.5,
        "source": "persisted:livermore_candidate_history",
        "note": None,
    }


@pytest.mark.unit
def test_checklist_stale_empty_min_amount_and_missing_surface(tmp_path: Path) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)

    # 信号日距 today 超过 5 个自然日 → stale。
    stale_payload = pretrade_checklist_envelope(duckdb_path=db_path, today=TODAY_STALE)["result"]
    assert stale_payload["checklist_status"] == "stale"
    assert stale_payload["staleness"]["status"] == "stale"
    assert stale_payload["staleness"]["calendar_gap_days"] == 21

    # 请求的信号日没有候选行 → empty（不硬造行）。
    empty_payload = pretrade_checklist_envelope(
        duckdb_path=db_path, as_of_date="2026-01-05", today=TODAY_FRESH
    )["result"]
    assert empty_payload["checklist_status"] == "empty"
    assert empty_payload["items"] == []

    # 金额门槛（人民币元）：低于阈值降级 review，不拦截。
    threshold_payload = pretrade_checklist_envelope(
        duckdb_path=db_path, today=TODAY_FRESH, min_amount=6_000_000.0
    )["result"]
    threshold_items = _items_by_code(threshold_payload)
    assert threshold_items["600001.SH"]["buyable_status"] == "review"
    assert "low_liquidity" in threshold_items["600001.SH"]["block_reasons"]

    # 库文件缺失 / 候选历史表缺失 → None（路由 404）。
    assert pretrade_checklist_envelope(duckdb_path=tmp_path / "absent.duckdb") is None
    bare_db = tmp_path / "bare.duckdb"
    conn = duckdb.connect(str(bare_db))
    conn.execute("create table unrelated (x integer)")
    conn.close()
    assert pretrade_checklist_envelope(duckdb_path=bare_db) is None


def _pretrade_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    with_db: bool = True,
    grant_read: bool = True,
) -> TestClient:
    db_path = tmp_path / "moss.duckdb"
    if with_db:
        _build_synthetic_db(db_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    sqlite_path = tmp_path / "pretrade-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_USER_ID", "pretrade-checklist-test-user")
    get_settings.cache_clear()
    if grant_read:
        UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
            user_id="*",
            role=None,
            resource="pretrade_checklist",
            action="read",
        )
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    return TestClient(load_module("backend.app.main", "backend/app/main.py").app)


def test_pretrade_route_returns_404_when_db_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _pretrade_client(tmp_path, monkeypatch, with_db=False)
    response = client.get("/api/pretrade-checklist")
    assert response.status_code == 404
    assert "not available" in response.json()["detail"]


def test_pretrade_route_forbidden_without_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _pretrade_client(tmp_path, monkeypatch, grant_read=False)
    response = client.get("/api/pretrade-checklist")
    assert response.status_code == 403


def test_pretrade_route_returns_checklist_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _pretrade_client(tmp_path, monkeypatch)
    response = client.get("/api/pretrade-checklist")
    assert response.status_code == 200
    payload = response.json()

    meta = payload["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["result_kind"] == "pretrade_checklist.today"

    result = payload["result"]
    assert result["as_of_date"] == AS_OF
    assert len(result["items"]) == 7
    assert result["gate"]["state"] == "WARM"
    assert result["position_size_hint"]["items"]
