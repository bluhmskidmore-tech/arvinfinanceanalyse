"""数据健康总览：service 逐项检查逻辑（合成 DuckDB）+ 路由契约。

- service 层用合成库验证：三张供数表新鲜度阈值（ok/warn/stale/missing）、
  复权因子缺口分视角计数与因子悬崖、formula_version 旧版存量、概念区间
  陈旧度（§4.11）、涨跌停数值表回填、tradestatus 未知非空词值占比
  （§4.10 观察点）、schtasks 解析与降级、单项失败不拖垮整体、整体状态
  取最差项。
- 路由层验证 404（数据面缺失）、403（无读权限）、200（envelope）契约。

schtasks 在所有 envelope 级测试中均被替换为固定 CSV/异常，测试不依赖
宿主机调度器状态，也可在非 Windows CI 上运行。
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.core_finance.matched_baseline import (
    FORMULA_VERSION as MATCHED_BASELINE_FORMULA_VERSION,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.services import data_health_service
from backend.app.services.data_health_service import data_health_envelope
from backend.app.tasks.livermore_candidate_history_materialize import (
    EXECUTION_FORMULA_VERSION,
)
from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]

FRESH_DATE = "2026-08-11"
TODAY_FRESH = "2026-08-12"  # 落后 1 天 → ok
TODAY_WARN = "2026-08-14"  # 落后 3 天 → warn
TODAY_STALE = "2026-08-20"  # 落后 9 天 → stale

#: 本地化表头 + 非 MOSS 任务 + 多触发器重复行，覆盖列序解析/过滤/去重。
SCHTASKS_CSV_HEALTHY = (
    '"主机名","任务名","下次运行时间","模式","登录模式","上次运行时间","上次结果","创建者","要运行的任务"\n'
    '"HOST","\\Microsoft\\Windows\\Foo","2026-08-13 03:00:00","就绪","交互","2026-08-12 03:00:00","0","MS","x"\n'
    '"HOST","\\MOSS-DailyDataRefresh","2026-08-13 17:30:00","就绪","后台","2026-08-12 17:30:00","0","u","y"\n'
    '"HOST","\\MOSS-DailyDataRefresh","2026-08-13 17:30:00","就绪","后台","2026-08-12 17:30:00","0","u","y"\n'
    '"HOST","\\MOSS-MonthlyWalkForward","2026-09-05 09:00:00","正在运行","后台","2026-08-01 09:00:00","267009","u","z"\n'
)

SCHTASKS_CSV_FAILING = (
    '"HostName","TaskName","Next Run Time","Status","Logon Mode","Last Run Time","Last Result","Author","Task To Run"\n'
    '"HOST","\\MOSS-DailyDataRefresh","2026-08-13 17:30:00","Ready","Background","2026-08-12 17:30:00","1","u","y"\n'
    '"HOST","\\MOSS-MonthlyWalkForward","2026-09-05 09:00:00","Ready","Background","N/A","267011","u","z"\n'
)


def _create_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          tradestatus varchar
        )
        """
    )
    conn.execute("create table fact_market_breadth_daily (trade_date varchar, total_count integer)")
    conn.execute("create table fact_livermore_gate_supplement_daily (trade_date varchar, breadth_5d double)")
    conn.execute(
        """
        create table livermore_candidate_execution_history (
          signal_date varchar,
          return_1d_net double, return_1d_net_adj double,
          return_5d_net double, return_5d_net_adj double,
          return_10d_net double, return_10d_net_adj double,
          return_20d_net double, return_20d_net_adj double,
          formula_version varchar
        )
        """
    )
    conn.execute("create table livermore_matched_baseline_history (signal_date varchar, formula_version varchar)")
    conn.execute("create table stock_adjustment_factor (stock_code varchar, trade_date varchar, adj_factor double)")
    conn.execute(
        """
        create table choice_stock_concept_membership_interval (
          stock_code varchar, concept_code varchar, concept_source varchar,
          valid_from varchar, valid_to varchar, last_observed_date varchar
        )
        """
    )
    conn.execute(
        """
        create table stock_limit_price_daily (
          trade_date varchar, stock_code varchar, up_limit double, down_limit double
        )
        """
    )


def _build_healthy_db(path: Path) -> None:
    """全部 section 为 ok 的合成库（today=TODAY_FRESH 视角）。"""
    conn = duckdb.connect(str(path))
    try:
        _create_tables(conn)
        # 20 行观测，全部空串/白名单词值 → 未知非空 0 行。
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?)",
            [(FRESH_DATE, f"6000{index:02d}.SH", "" if index % 2 else "交易") for index in range(20)],
        )
        conn.execute("insert into fact_market_breadth_daily values (?, 5000)", [FRESH_DATE])
        conn.execute("insert into fact_livermore_gate_supplement_daily values (?, 0.6)", [FRESH_DATE])
        # 执行历史 2 行：net 与 net_adj 成对齐全，且为当前公式版本。
        conn.executemany(
            "insert into livermore_candidate_execution_history values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (FRESH_DATE, 0.01, 0.01, 0.02, 0.02, 0.03, 0.03, 0.04, 0.04, EXECUTION_FORMULA_VERSION),
                (FRESH_DATE, -0.01, -0.01, None, None, None, None, None, None, EXECUTION_FORMULA_VERSION),
            ],
        )
        conn.executemany(
            "insert into livermore_matched_baseline_history values (?, ?)",
            [(FRESH_DATE, MATCHED_BASELINE_FORMULA_VERSION)] * 3,
        )
        conn.execute("insert into stock_adjustment_factor values ('600001.SH', ?, 1.23)", [FRESH_DATE])
        conn.execute(
            "insert into choice_stock_concept_membership_interval values "
            "('600001.SH', 'BK001', 'choice', '2026-05-13', null, ?)",
            [FRESH_DATE],
        )
        conn.execute("insert into stock_limit_price_daily values (?, '600001.SH', 11.0, 9.0)", [FRESH_DATE])
    finally:
        conn.close()


def _build_sick_db(path: Path) -> None:
    """带病合成库：陈旧观测、缺表、空表、复权缺口、旧公式版本、词表异常。"""
    conn = duckdb.connect(str(path))
    try:
        _create_tables(conn)
        conn.execute("drop table fact_market_breadth_daily")  # 表缺失 → missing
        # 观测最新 2026-08-05，today=2026-08-12 → 落后 7 天 stale；
        # 10 行中 2 行未知非空词值（"1"/"未交易"）→ 占比 20% > 5% warn。
        rows = [("2026-08-05", f"6000{index:02d}.SH", "交易") for index in range(8)]
        rows += [("2026-08-05", "600098.SH", "1"), ("2026-08-05", "600099.SH", "未交易")]
        conn.executemany("insert into choice_stock_daily_observation values (?, ?, ?)", rows)
        # 门控补充表存在但 0 行 → missing。
        # 执行历史：20d 视角 2 行缺 adj、5d 视角 1 行缺 adj；1 行旧公式版本。
        conn.executemany(
            "insert into livermore_candidate_execution_history values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-08-05", 0.01, 0.01, 0.02, None, 0.03, 0.03, 0.04, None, EXECUTION_FORMULA_VERSION),
                ("2026-08-05", 0.01, 0.01, 0.02, 0.02, 0.03, 0.03, 0.04, None, "fv_livermore_candidate_execution_v1"),
            ],
        )
        # matched_baseline：v3 之外再压 2 行旧版 v2。
        conn.executemany(
            "insert into livermore_matched_baseline_history values (?, ?)",
            [
                ("2026-08-05", MATCHED_BASELINE_FORMULA_VERSION),
                ("2026-08-05", "fv_livermore_matched_baseline_v2"),
                ("2026-08-05", "fv_livermore_matched_baseline_v2"),
            ],
        )
        # 因子表最新 2026-08-01，today=2026-08-12 → 距今 11 天：缺口 + 因子陈旧 → stale。
        conn.execute("insert into stock_adjustment_factor values ('600001.SH', '2026-08-01', 1.0)")
        # 概念区间表 0 行 → missing；涨跌停表 0 行 → missing。
    finally:
        conn.close()


def _sections_by_key(envelope: dict[str, object]) -> dict[str, dict[str, object]]:
    sections = envelope["result"]["sections"]
    return {str(section["key"]): section for section in sections}


@pytest.mark.unit
def test_healthy_db_reports_all_sections_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "health.duckdb"
    _build_healthy_db(db_path)
    monkeypatch.setattr(data_health_service, "_run_schtasks_query", lambda: SCHTASKS_CSV_HEALTHY)

    envelope = data_health_envelope(duckdb_path=db_path, today=TODAY_FRESH)
    assert envelope is not None
    payload = envelope["result"]
    sections = _sections_by_key(envelope)

    assert payload["as_of_date"] == TODAY_FRESH
    assert payload["overall_status"] == "ok"
    assert set(sections) == {
        "observation_freshness",
        "market_breadth_freshness",
        "gate_supplement_freshness",
        "adjustment_factor_gap",
        "stale_formula_rows",
        "concept_interval_staleness",
        "limit_price_backfill",
        "tradestatus_vocabulary",
        "scheduled_tasks",
    }
    assert all(section["status"] == "ok" for section in sections.values())

    observation = sections["observation_freshness"]
    assert observation["as_of"] == FRESH_DATE
    assert observation["metric"] == f"{FRESH_DATE} · 落后 1 天"

    adjustment = sections["adjustment_factor_gap"]
    assert adjustment["metric"] == "0 行缺复权"
    assert adjustment["as_of"] == FRESH_DATE

    formula = sections["stale_formula_rows"]
    assert formula["metric"] == "0 行旧版"
    assert EXECUTION_FORMULA_VERSION in formula["detail"]
    assert MATCHED_BASELINE_FORMULA_VERSION in formula["detail"]

    vocabulary = sections["tradestatus_vocabulary"]
    assert vocabulary["metric"] == "0 行 · 0.00%"

    # 本地化表头列序解析 + 非 MOSS 任务过滤 + 多触发器去重；267009（运行中）视为正常。
    scheduled = sections["scheduled_tasks"]
    assert scheduled["metric"] == "2/2 正常"
    assert "MOSS-DailyDataRefresh" in scheduled["detail"]
    assert "Microsoft" not in scheduled["detail"]

    meta = envelope["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["result_kind"] == "data_health.overview"
    assert meta["quality_flag"] == "ok"


@pytest.mark.unit
def test_freshness_thresholds_step_ok_warn_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "health.duckdb"
    _build_healthy_db(db_path)
    monkeypatch.setattr(data_health_service, "_run_schtasks_query", lambda: SCHTASKS_CSV_HEALTHY)

    warn_sections = _sections_by_key(data_health_envelope(duckdb_path=db_path, today=TODAY_WARN))
    assert warn_sections["observation_freshness"]["status"] == "warn"  # 落后 3 天
    assert warn_sections["concept_interval_staleness"]["status"] == "warn"

    stale_sections = _sections_by_key(data_health_envelope(duckdb_path=db_path, today=TODAY_STALE))
    assert stale_sections["observation_freshness"]["status"] == "stale"  # 落后 9 天
    assert stale_sections["market_breadth_freshness"]["status"] == "stale"
    assert stale_sections["limit_price_backfill"]["status"] == "stale"


@pytest.mark.unit
def test_sick_db_reports_gaps_and_worst_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "sick.duckdb"
    _build_sick_db(db_path)
    monkeypatch.setattr(data_health_service, "_run_schtasks_query", lambda: SCHTASKS_CSV_FAILING)

    envelope = data_health_envelope(duckdb_path=db_path, today=TODAY_FRESH)
    payload = envelope["result"]
    sections = _sections_by_key(envelope)

    assert sections["observation_freshness"]["status"] == "stale"  # 2026-08-05 → 落后 7 天
    assert sections["market_breadth_freshness"]["status"] == "missing"  # 表缺失
    assert sections["gate_supplement_freshness"]["status"] == "missing"  # 0 行

    adjustment = sections["adjustment_factor_gap"]
    assert adjustment["status"] == "stale"  # 缺口存在且因子表落后 11 天
    assert adjustment["metric"] == "3 行缺复权"  # 5d 1 + 20d 2（各视角独立计数）
    assert "5d 视角 1" in adjustment["detail"]
    assert "20d 视角 2" in adjustment["detail"]
    assert adjustment["as_of"] == "2026-08-01"

    formula = sections["stale_formula_rows"]
    assert formula["status"] == "stale"
    assert formula["metric"] == "3 行旧版"  # execution 1 + matched_baseline 2
    assert "execution: 旧版 1/2" in formula["detail"]
    assert "matched_baseline: 旧版 2/3" in formula["detail"]

    assert sections["concept_interval_staleness"]["status"] == "missing"
    assert sections["concept_interval_staleness"]["metric"] == "0 行"
    assert sections["limit_price_backfill"]["status"] == "missing"
    assert sections["limit_price_backfill"]["metric"] == "0 行"

    vocabulary = sections["tradestatus_vocabulary"]
    assert vocabulary["status"] == "warn"  # 2/10 = 20% > 5%
    assert vocabulary["metric"] == "2 行 · 20.00%"
    assert "未交易 1" in vocabulary["detail"]

    scheduled = sections["scheduled_tasks"]
    assert scheduled["status"] == "warn"  # LastResult 1 与 267011 均不健康
    assert scheduled["metric"] == "0/2 正常"

    # 最差项决定整体：missing(3) > stale(2) > warn(1)。
    assert payload["overall_status"] == "missing"
    assert envelope["result_meta"]["quality_flag"] == "warning"


@pytest.mark.unit
def test_single_section_failure_degrades_without_breaking_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "health.duckdb"
    _build_healthy_db(db_path)
    monkeypatch.setattr(data_health_service, "_run_schtasks_query", lambda: SCHTASKS_CSV_HEALTHY)

    def _boom(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("synthetic section failure")

    monkeypatch.setattr(data_health_service, "_tradestatus_section", _boom)

    envelope = data_health_envelope(duckdb_path=db_path, today=TODAY_FRESH)
    sections = _sections_by_key(envelope)

    failed = sections["tradestatus_vocabulary"]
    assert failed["status"] == "error"
    assert "synthetic section failure" in failed["detail"]
    # 其余 section 不受拖累。
    assert sections["observation_freshness"]["status"] == "ok"
    assert sections["scheduled_tasks"]["status"] == "ok"
    assert envelope["result"]["overall_status"] == "error"


@pytest.mark.unit
def test_schtasks_failure_and_empty_results_degrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise() -> str:
        raise FileNotFoundError("schtasks not found")

    monkeypatch.setattr(data_health_service, "_run_schtasks_query", _raise)
    section = data_health_service._scheduled_tasks_section()
    assert section["status"] == "error"
    assert "schtasks not found" in section["detail"]
    assert section["metric"] is None  # 失败降级为字段缺省

    monkeypatch.setattr(
        data_health_service,
        "_run_schtasks_query",
        lambda: '"HostName","TaskName","Next Run Time"\n',
    )
    section = data_health_service._scheduled_tasks_section()
    assert section["status"] == "missing"
    assert section["metric"] == "0 个任务"


@pytest.mark.unit
def test_envelope_none_when_db_file_missing(tmp_path: Path) -> None:
    assert data_health_envelope(duckdb_path=tmp_path / "absent.duckdb") is None


def _data_health_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    with_db: bool = True,
    grant_read: bool = True,
) -> TestClient:
    db_path = tmp_path / "moss.duckdb"
    if with_db:
        _build_healthy_db(db_path)
    monkeypatch.setattr(data_health_service, "_run_schtasks_query", lambda: SCHTASKS_CSV_HEALTHY)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    sqlite_path = tmp_path / "data-health-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_USER_ID", "data-health-test-user")
    get_settings.cache_clear()
    if grant_read:
        UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
            user_id="*",
            role=None,
            resource="data_health",
            action="read",
        )
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    return TestClient(load_module("backend.app.main", "backend/app/main.py").app)


def test_data_health_route_returns_404_when_db_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _data_health_client(tmp_path, monkeypatch, with_db=False)
    response = client.get("/api/data-health")
    assert response.status_code == 404
    assert "not available" in response.json()["detail"]


def test_data_health_route_forbidden_without_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _data_health_client(tmp_path, monkeypatch, grant_read=False)
    response = client.get("/api/data-health")
    assert response.status_code == 403


def test_data_health_route_returns_overview_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _data_health_client(tmp_path, monkeypatch)
    response = client.get("/api/data-health")
    assert response.status_code == 200
    payload = response.json()

    meta = payload["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["result_kind"] == "data_health.overview"

    result = payload["result"]
    assert result["overall_status"] in {"ok", "warn", "stale", "missing", "error"}
    assert len(result["sections"]) == 9
    # 路由级只断言结构（状态随 date.today() 推移漂移，阈值行为由 service 测试用显式 today 钉住）。
    for section in result["sections"]:
        assert {"key", "label", "status", "metric", "detail", "as_of"} <= set(section)
