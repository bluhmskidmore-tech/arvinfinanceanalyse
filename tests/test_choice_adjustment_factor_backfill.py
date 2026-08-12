"""Choice 后复权推导回补 stock_adjustment_factor：纯推导 + 脚本端到端。

覆盖：
- 合成除权场景下 rel=hfq/raw 推导与 tushare 尺度锚定的正确性；
- 重叠段两源复权收益一致性校验（不一致要拒写并报差异率）；
- 最小重叠天数门槛（min_anchor_overlap，默认 3）：单日/两日重叠 fail-closed
  拒绝锚定，报告输出 per-code anchor_overlap_count 与低于门槛清单；
- 锚定 reference 排除本脚本自推导行（sv_choice_adj_factor_*），防止级联；
- --execute 与 --allow-unanchored 组合拒绝（scale=1 相对因子不得写入）；
- 脚本 plan（默认 dry-run）/ verify-only / execute 三模式；
- 关键验收：混源因子（signal 日 tushare 行 + forward 日 choice 推导行）
  计算的复权收益与全 hfq 口径一致；
- 既有 tushare 行不可被覆盖、重跑幂等、写守卫必须显式解锁。
"""
from __future__ import annotations

import json

import duckdb
import pytest

from backend.app.core_finance.adjusted_returns import adjusted_return
from backend.app.core_finance.choice_adjustment_factors import (
    STATUS_ANCHORED,
    STATUS_INCONSISTENT_OVERLAP,
    STATUS_INSUFFICIENT_DATA,
    STATUS_INSUFFICIENT_OVERLAP,
    STATUS_UNANCHORED,
    derive_choice_adjustment_factors,
    derive_relative_factors,
)
from tests.helpers import load_module

D1, D2, D3, D4, D5, D6 = (
    "2026-06-15",
    "2026-06-16",
    "2026-06-17",
    "2026-06-18",
    "2026-06-19",
    "2026-06-22",
)
ALL_DATES = [D1, D2, D3, D4, D5, D6]

# 股票 A：D5 除权（真实累计因子 2.0 -> 2.2），Choice 后复权基期常数 k=0.5。
A_CODE = "000001.SZ"
A_TRUE_FACTOR = {D1: 2.0, D2: 2.0, D3: 2.0, D4: 2.0, D5: 2.2, D6: 2.2}
A_RAW_CLOSE = {D1: 10.0, D2: 10.1, D3: 10.2, D4: 10.3, D5: 9.5, D6: 9.6}
A_CHOICE_BASE = 0.5
A_HFQ_CLOSE = {d: A_RAW_CLOSE[d] * A_TRUE_FACTOR[d] * A_CHOICE_BASE for d in ALL_DATES}

# 股票 B：无除权（因子恒 3.0），Choice 基期常数 k=0.25。
B_CODE = "000002.SZ"
B_TRUE_FACTOR = {d: 3.0 for d in ALL_DATES}
B_RAW_CLOSE = {D1: 20.0, D2: 20.2, D3: 20.4, D4: 20.6, D5: 20.8, D6: 21.0}
B_CHOICE_BASE = 0.25
B_HFQ_CLOSE = {d: B_RAW_CLOSE[d] * B_TRUE_FACTOR[d] * B_CHOICE_BASE for d in ALL_DATES}


def _load_script():
    return load_module(
        "scripts.backfill_stock_adjustment_factor_from_choice",
        "scripts/backfill_stock_adjustment_factor_from_choice.py",
    )


# ---------------------------------------------------------------------------
# 纯推导（core_finance）
# ---------------------------------------------------------------------------


def test_relative_factor_derivation_skips_invalid_values() -> None:
    relative = derive_relative_factors(
        {D1: 10.0, D2: None, D3: 0.0, D4: 10.0, D5: 10.0},
        {D1: 5.0, D2: 5.0, D3: 5.0, D4: None, D5: float("nan")},
    )
    assert relative == {D1: 0.5}


def test_anchored_derivation_matches_reference_scale_and_hfq_returns() -> None:
    derivation = derive_choice_adjustment_factors(
        stock_code=A_CODE,
        raw_close_by_date=A_RAW_CLOSE,
        adjusted_close_by_date=A_HFQ_CLOSE,
        reference_factors_by_date={D1: 2.0, D2: 2.0, D3: 2.0},
        requested_dates=[D5, D6],
    )
    assert derivation.status == STATUS_ANCHORED
    assert derivation.scale == pytest.approx(1.0 / A_CHOICE_BASE)
    assert derivation.anchor_overlap_count == 3
    assert derivation.scale_max_rel_deviation == pytest.approx(0.0, abs=1e-12)
    assert derivation.factors[D5] == pytest.approx(2.2)
    assert derivation.factors[D6] == pytest.approx(2.2)
    assert derivation.missing_requested_dates == ()

    # 推导因子与 tushare 因子混用时的复权收益 == 纯 hfq 收益
    mixed = adjusted_return(
        start_price=A_RAW_CLOSE[D1],
        start_adj_factor=2.0,
        end_price=A_RAW_CLOSE[D6],
        end_adj_factor=derivation.factors[D6],
    )
    hfq_expected = A_HFQ_CLOSE[D6] / A_HFQ_CLOSE[D1] - 1.0
    assert mixed == pytest.approx(hfq_expected, abs=1e-12)


def test_overlap_event_pair_is_validated_when_reference_covers_ex_div() -> None:
    # 重叠段覆盖 D5 除权事件：reference 因子在 D4->D5 跳变，choice 比率应匹配。
    derivation = derive_choice_adjustment_factors(
        stock_code=A_CODE,
        raw_close_by_date=A_RAW_CLOSE,
        adjusted_close_by_date=A_HFQ_CLOSE,
        reference_factors_by_date={D3: 2.0, D4: 2.0, D5: 2.2},
        requested_dates=[D6],
    )
    assert derivation.status == STATUS_ANCHORED
    assert derivation.overlap_event_pair_count == 1
    assert derivation.overlap_event_matched_count == 1
    assert derivation.return_consistency_breach_count == 0


def test_inconsistent_overlap_rejected_with_diff_rate() -> None:
    # 在 D2 对 reference 注入 1% 口径偏差：两源重叠段复权收益不一致，必须拒写。
    derivation = derive_choice_adjustment_factors(
        stock_code=A_CODE,
        raw_close_by_date=A_RAW_CLOSE,
        adjusted_close_by_date=A_HFQ_CLOSE,
        reference_factors_by_date={D1: 2.0, D2: 2.0 * 1.01, D3: 2.0},
        requested_dates=[D6],
    )
    assert derivation.status == STATUS_INCONSISTENT_OVERLAP
    assert derivation.factors == {}
    assert derivation.scale_max_rel_deviation is not None
    assert derivation.scale_max_rel_deviation > 0.002
    assert derivation.return_consistency_breach_count >= 1
    assert derivation.return_consistency_max_rel_diff == pytest.approx(0.01, rel=0.05)


def test_min_anchor_overlap_rejects_single_and_two_day_overlap() -> None:
    # 单日重叠 scale_max_rel_deviation ≡ 0、收益一致性 pair 数为 0：校验退化，
    # 默认门槛(3)下必须 fail-closed 拒绝锚定、不输出任何因子。
    for reference in ({D1: 2.0}, {D1: 2.0, D2: 2.0}):
        derivation = derive_choice_adjustment_factors(
            stock_code=A_CODE,
            raw_close_by_date=A_RAW_CLOSE,
            adjusted_close_by_date=A_HFQ_CLOSE,
            reference_factors_by_date=reference,
            requested_dates=[D6],
        )
        assert derivation.status == STATUS_INSUFFICIENT_OVERLAP
        assert derivation.factors == {}
        assert derivation.anchor_overlap_count == len(reference)


def test_min_anchor_overlap_three_days_pass_default_threshold() -> None:
    derivation = derive_choice_adjustment_factors(
        stock_code=A_CODE,
        raw_close_by_date=A_RAW_CLOSE,
        adjusted_close_by_date=A_HFQ_CLOSE,
        reference_factors_by_date={D1: 2.0, D2: 2.0, D3: 2.0},
        requested_dates=[D6],
    )
    assert derivation.status == STATUS_ANCHORED
    assert derivation.anchor_overlap_count == 3
    assert derivation.factors[D6] == pytest.approx(2.2)


def test_min_anchor_overlap_explicit_one_restores_single_day_anchoring() -> None:
    derivation = derive_choice_adjustment_factors(
        stock_code=A_CODE,
        raw_close_by_date=A_RAW_CLOSE,
        adjusted_close_by_date=A_HFQ_CLOSE,
        reference_factors_by_date={D1: 2.0},
        requested_dates=[D6],
        min_anchor_overlap=1,
    )
    assert derivation.status == STATUS_ANCHORED
    assert derivation.anchor_overlap_count == 1
    assert derivation.factors[D6] == pytest.approx(2.2)


def test_min_anchor_overlap_must_be_positive() -> None:
    with pytest.raises(ValueError, match="min_anchor_overlap"):
        derive_choice_adjustment_factors(
            stock_code=A_CODE,
            raw_close_by_date=A_RAW_CLOSE,
            adjusted_close_by_date=A_HFQ_CLOSE,
            reference_factors_by_date={D1: 2.0},
            requested_dates=[D6],
            min_anchor_overlap=0,
        )


def test_insufficient_overlap_not_bypassed_by_allow_unanchored() -> None:
    # 该股票已有 reference 行（只是重叠不足）：allow_unanchored 不得把它降级成
    # scale=1 相对因子输出，否则同表同股票混尺度。
    derivation = derive_choice_adjustment_factors(
        stock_code=A_CODE,
        raw_close_by_date=A_RAW_CLOSE,
        adjusted_close_by_date=A_HFQ_CLOSE,
        reference_factors_by_date={D1: 2.0},
        requested_dates=[D6],
        allow_unanchored=True,
    )
    assert derivation.status == STATUS_INSUFFICIENT_OVERLAP
    assert derivation.factors == {}


def test_unanchored_policy_defaults_to_no_factors() -> None:
    kwargs = dict(
        stock_code=B_CODE,
        raw_close_by_date=B_RAW_CLOSE,
        adjusted_close_by_date=B_HFQ_CLOSE,
        reference_factors_by_date={},
        requested_dates=[D6],
    )
    skipped = derive_choice_adjustment_factors(**kwargs)
    assert skipped.status == STATUS_UNANCHORED
    assert skipped.factors == {}

    written = derive_choice_adjustment_factors(**kwargs, allow_unanchored=True)
    assert written.status == STATUS_UNANCHORED
    assert written.factors[D6] == pytest.approx(B_TRUE_FACTOR[D6] * B_CHOICE_BASE)


def test_insufficient_data_status() -> None:
    derivation = derive_choice_adjustment_factors(
        stock_code=B_CODE,
        raw_close_by_date={},
        adjusted_close_by_date={},
        reference_factors_by_date={D1: 3.0},
        requested_dates=[D6],
    )
    assert derivation.status == STATUS_INSUFFICIENT_DATA
    assert derivation.missing_requested_dates == (D6,)


# ---------------------------------------------------------------------------
# 脚本端到端（tmp DuckDB + 假 Choice 客户端）
# ---------------------------------------------------------------------------


class _FakeCsdResult:
    def __init__(self, codes: list[str], dates: list[str], closes: dict[str, dict[str, float | None]]) -> None:
        self.ErrorCode = 0
        self.ErrorMsg = ""
        self.Codes = list(codes)
        self.Indicators = ["CLOSE"]
        self.Dates = list(dates)
        self.Data = {code: [[closes[code].get(d) for d in dates]] for code in codes}


class _FakeChoiceClient:
    def __init__(
        self,
        raw: dict[str, dict[str, float | None]],
        hfq: dict[str, dict[str, float | None]],
    ) -> None:
        self._raw = raw
        self._hfq = hfq
        self.calls: list[tuple[str, str, str, str, str]] = []

    def csd(self, codes: str, indicators: str, start_date: str, end_date: str, *, options: str) -> object:
        self.calls.append((codes, indicators, start_date, end_date, options))
        assert indicators == "CLOSE"
        source = self._hfq if "AdjustFlag=2" in options else self._raw
        code_list = [item for item in codes.split(",") if item]
        dates = sorted(
            {
                trade_date
                for code in code_list
                for trade_date in source.get(code, {})
                if start_date <= trade_date <= end_date
            }
        )
        closes = {code: {d: source.get(code, {}).get(d) for d in dates} for code in code_list}
        return _FakeCsdResult(code_list, dates, closes)


def _create_fixture_db(db_path: str) -> None:
    conn = duckdb.connect(db_path)
    try:
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar, trade_date varchar, adj_factor double,
              source_version varchar, run_id varchar
            )
            """
        )
        for code, factor_by_date in ((A_CODE, A_TRUE_FACTOR), (B_CODE, B_TRUE_FACTOR)):
            for trade_date in (D1, D2, D3):
                conn.execute(
                    "insert into stock_adjustment_factor values (?, ?, ?, ?, ?)",
                    [code, trade_date, factor_by_date[trade_date], "sv_stock_adjustment_factor_seed", "run-seed"],
                )
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar, stock_code varchar,
              forward_trade_date_20d varchar, return_20d double, return_20d_adj double
            )
            """
        )
        conn.execute(
            "insert into livermore_candidate_history values (?, ?, ?, ?, ?)",
            [D1, A_CODE, D6, A_RAW_CLOSE[D6] / A_RAW_CLOSE[D1] - 1.0, None],
        )
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar, stock_code varchar, entry_date varchar,
              exit_date_20d varchar, return_20d_gross double, return_20d_gross_adj double
            )
            """
        )
        conn.execute(
            "insert into livermore_candidate_execution_history values (?, ?, ?, ?, ?, ?)",
            [D1, B_CODE, D2, D6, B_RAW_CLOSE[D6] / B_RAW_CLOSE[D2] - 1.0, None],
        )
    finally:
        conn.close()


def _fake_client() -> _FakeChoiceClient:
    return _FakeChoiceClient(
        raw={A_CODE: dict(A_RAW_CLOSE), B_CODE: dict(B_RAW_CLOSE)},
        hfq={A_CODE: dict(A_HFQ_CLOSE), B_CODE: dict(B_HFQ_CLOSE)},
    )


def test_plan_mode_reports_missing_cells_without_choice_calls(tmp_path) -> None:
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)
    client = _fake_client()

    result = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=client,
    )

    assert result["status"] == "dry_run"
    assert result["mode"] == "plan"
    # 缺失 cell：A@D6（candidate history forward）与 B@D6（execution exit）
    assert result["missing_cell_count"] == 2
    assert result["code_count"] == 2
    assert result["era_split"] == {"native_era": 2, "tushare_era": 0}
    assert result["codes_without_anchor"] == []
    # 锚定来源构成：两只股票窗口内各 3 行 seed reference，无自推导行被排除。
    assert result["anchor_reference_source_breakdown"] == {"sv_stock_adjustment_factor_seed": 6}
    assert result["excluded_self_derived_reference_row_count"] == 0
    assert client.calls == []

    conn = duckdb.connect(db_path, read_only=True)
    try:
        count = conn.execute("select count(*) from stock_adjustment_factor").fetchone()[0]
    finally:
        conn.close()
    assert count == 6  # 仅 seed 行


def test_verify_only_reports_consistency_without_writes(tmp_path) -> None:
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)
    client = _fake_client()

    result = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=client,
        verify_only=True,
    )

    assert result["status"] == "verified"
    verification = result["verification"]
    assert verification["status_counts"] == {STATUS_ANCHORED: 2}
    assert verification["failed_codes"] == []
    assert verification["missing_vendor_cell_count"] == 0
    assert verification["max_scale_rel_deviation"] == pytest.approx(0.0, abs=1e-12)
    # 每只成功锚定股票输出 anchor_overlap_count；低于门槛清单为空。
    assert verification["min_anchor_overlap"] == 3
    assert verification["anchored_codes"] == [
        {"stock_code": A_CODE, "anchor_overlap_count": 3},
        {"stock_code": B_CODE, "anchor_overlap_count": 3},
    ]
    assert verification["below_min_overlap_codes"] == []
    assert len(client.calls) == 2  # AdjustFlag=1 + AdjustFlag=2 各一次（单 chunk）

    conn = duckdb.connect(db_path, read_only=True)
    try:
        count = conn.execute("select count(*) from stock_adjustment_factor").fetchone()[0]
    finally:
        conn.close()
    assert count == 6


def test_execute_writes_anchored_factors_and_mixed_source_returns_match_hfq(tmp_path) -> None:
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)
    client = _fake_client()

    result = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=client,
        execute=True,
        governance_lock=True,
        skip_outcome_maturity=True,
    )

    assert result["status"] == "completed"
    assert result["inserted_count"] == 2
    assert result["unresolved_cell_count"] == 0
    assert str(result["source_version"]).startswith("sv_choice_adj_factor_")

    conn = duckdb.connect(db_path, read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, trade_date, adj_factor, source_version
            from stock_adjustment_factor where trade_date = ? order by stock_code
            """,
            [D6],
        ).fetchall()
        seed_rows = conn.execute(
            "select count(*) from stock_adjustment_factor where source_version = 'sv_stock_adjustment_factor_seed'"
        ).fetchone()[0]
    finally:
        conn.close()

    assert seed_rows == 6  # 既有 tushare 行不被触碰
    assert [(r[0], r[1]) for r in rows] == [(A_CODE, D6), (B_CODE, D6)]
    factor_by_code = {r[0]: r[2] for r in rows}
    assert factor_by_code[A_CODE] == pytest.approx(2.2, abs=1e-9)
    assert factor_by_code[B_CODE] == pytest.approx(3.0, abs=1e-9)

    # 关键验收：signal 日用 tushare 因子 + forward 日用 choice 推导因子，
    # 复权收益与纯 hfq 口径一致。
    mixed_return = adjusted_return(
        start_price=A_RAW_CLOSE[D1],
        start_adj_factor=A_TRUE_FACTOR[D1],
        end_price=A_RAW_CLOSE[D6],
        end_adj_factor=factor_by_code[A_CODE],
    )
    assert mixed_return == pytest.approx(A_HFQ_CLOSE[D6] / A_HFQ_CLOSE[D1] - 1.0, abs=1e-12)

    # 重跑幂等：缺失 cell 归零，返回 noop，不再新增行。
    rerun = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=client,
        execute=True,
        governance_lock=True,
        skip_outcome_maturity=True,
    )
    assert rerun["status"] == "noop"
    assert rerun["missing_cell_count"] == 0


def test_execute_skips_inconsistent_stock_and_reports_partial(tmp_path) -> None:
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)
    hfq = {A_CODE: dict(A_HFQ_CLOSE), B_CODE: dict(B_HFQ_CLOSE)}
    hfq[B_CODE][D2] = hfq[B_CODE][D2] * 1.01  # B 重叠段口径被污染
    client = _FakeChoiceClient(
        raw={A_CODE: dict(A_RAW_CLOSE), B_CODE: dict(B_RAW_CLOSE)},
        hfq=hfq,
    )

    result = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=client,
        execute=True,
        governance_lock=True,
        skip_outcome_maturity=True,
    )

    assert result["status"] == "partial_completed"
    assert result["inserted_count"] == 1
    assert result["unresolved_cell_count"] == 1
    failed = result["verification"]["failed_codes"]
    assert len(failed) == 1
    assert failed[0]["stock_code"] == B_CODE
    assert failed[0]["status"] == STATUS_INCONSISTENT_OVERLAP
    assert failed[0]["scale_max_rel_deviation"] > 0.002

    conn = duckdb.connect(db_path, read_only=True)
    try:
        written = conn.execute(
            "select stock_code from stock_adjustment_factor where trade_date = ?",
            [D6],
        ).fetchall()
    finally:
        conn.close()
    assert [row[0] for row in written] == [A_CODE]


def test_execute_requires_backup_or_governance_lock(tmp_path) -> None:
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)

    with pytest.raises(RuntimeError, match="target-backup-path or --governance-lock"):
        module.backfill_stock_adjustment_factor_from_choice(
            duckdb_path=db_path,
            client=_fake_client(),
            execute=True,
        )


def _delete_factor_rows(db_path: str, code: str, dates: list[str]) -> None:
    conn = duckdb.connect(db_path)
    try:
        for trade_date in dates:
            conn.execute(
                "delete from stock_adjustment_factor where stock_code = ? and trade_date = ?",
                [code, trade_date],
            )
    finally:
        conn.close()


def test_execute_rejects_stock_below_min_anchor_overlap_and_reports(tmp_path) -> None:
    # A 只剩单日重叠（D1）：默认门槛 3 下 fail-closed 拒写并单列在报告；
    # B 三日重叠正常锚定写入。
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)
    _delete_factor_rows(db_path, A_CODE, [D2, D3])

    result = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=_fake_client(),
        execute=True,
        governance_lock=True,
        skip_outcome_maturity=True,
    )

    assert result["status"] == "partial_completed"
    assert result["inserted_count"] == 1
    assert result["unresolved_cell_count"] == 1
    verification = result["verification"]
    assert verification["min_anchor_overlap"] == 3
    assert verification["status_counts"] == {STATUS_ANCHORED: 1, STATUS_INSUFFICIENT_OVERLAP: 1}
    assert verification["anchored_codes"] == [{"stock_code": B_CODE, "anchor_overlap_count": 3}]
    assert verification["below_min_overlap_codes"] == [
        {"stock_code": A_CODE, "anchor_overlap_count": 1}
    ]
    failed = verification["failed_codes"]
    assert len(failed) == 1
    assert failed[0]["stock_code"] == A_CODE
    assert failed[0]["status"] == STATUS_INSUFFICIENT_OVERLAP
    assert failed[0]["anchor_overlap_count"] == 1

    conn = duckdb.connect(db_path, read_only=True)
    try:
        written = conn.execute(
            "select stock_code from stock_adjustment_factor where trade_date = ? order by 1",
            [D6],
        ).fetchall()
    finally:
        conn.close()
    assert [row[0] for row in written] == [B_CODE]

    # 门槛透传：显式放宽到 1 后，单日重叠的 A 可锚定并补上剩余 cell。
    relaxed = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=_fake_client(),
        execute=True,
        governance_lock=True,
        skip_outcome_maturity=True,
        min_anchor_overlap=1,
    )
    assert relaxed["status"] == "completed"
    assert relaxed["inserted_count"] == 1
    conn = duckdb.connect(db_path, read_only=True)
    try:
        factor = conn.execute(
            "select adj_factor from stock_adjustment_factor where stock_code = ? and trade_date = ?",
            [A_CODE, D6],
        ).fetchone()[0]
    finally:
        conn.close()
    assert factor == pytest.approx(2.2, abs=1e-9)


def test_self_derived_reference_rows_are_excluded_from_anchoring(tmp_path) -> None:
    # 库内混入本脚本此前写入的自推导行（sv_choice_adj_factor_*，值刻意污染）：
    # 未排除时会把中位数容差校验打爆（拒写级联），排除后按 seed 行正常锚定。
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)
    conn = duckdb.connect(db_path)
    try:
        for trade_date in (D4, D5):
            conn.execute(
                "insert into stock_adjustment_factor values (?, ?, ?, ?, ?)",
                [A_CODE, trade_date, 999.0, "sv_choice_adj_factor_prior001", "run-prior"],
            )
    finally:
        conn.close()

    result = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=_fake_client(),
        execute=True,
        governance_lock=True,
        skip_outcome_maturity=True,
    )

    assert result["status"] == "completed"
    assert result["excluded_self_derived_reference_row_count"] == 2
    assert result["anchor_reference_source_breakdown"] == {"sv_stock_adjustment_factor_seed": 6}
    verification = result["verification"]
    assert {"stock_code": A_CODE, "anchor_overlap_count": 3} in verification["anchored_codes"]

    conn = duckdb.connect(db_path, read_only=True)
    try:
        factor = conn.execute(
            """
            select adj_factor from stock_adjustment_factor
            where stock_code = ? and trade_date = ? and source_version <> 'sv_choice_adj_factor_prior001'
            """,
            [A_CODE, D6],
        ).fetchone()[0]
    finally:
        conn.close()
    assert factor == pytest.approx(2.2, abs=1e-9)


def test_execute_with_allow_unanchored_is_refused(tmp_path) -> None:
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)

    with pytest.raises(ValueError, match="allow-unanchored cannot be combined with --execute"):
        module.backfill_stock_adjustment_factor_from_choice(
            duckdb_path=db_path,
            client=_fake_client(),
            execute=True,
            governance_lock=True,
            allow_unanchored=True,
        )


def test_cli_rejects_execute_with_allow_unanchored(tmp_path, capsys) -> None:
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)

    with pytest.raises(SystemExit) as excinfo:
        module.main(
            [
                "--db-path",
                db_path,
                "--execute",
                "--allow-unanchored",
                "--governance-lock",
            ]
        )
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "--allow-unanchored cannot be combined with --execute" in err

    conn = duckdb.connect(db_path, read_only=True)
    try:
        count = conn.execute("select count(*) from stock_adjustment_factor").fetchone()[0]
    finally:
        conn.close()
    assert count == 6  # 仅 seed 行，未发生写入


def test_verify_only_still_allows_allow_unanchored(tmp_path) -> None:
    # 无锚股票的人工评估路径保留：verify-only + allow-unanchored 可出报告、不写库。
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)
    _delete_factor_rows(db_path, B_CODE, [D1, D2, D3])

    result = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=_fake_client(),
        verify_only=True,
        allow_unanchored=True,
    )

    assert result["status"] == "verified"
    assert result["verification"]["unanchored_codes"] == [B_CODE]

    conn = duckdb.connect(db_path, read_only=True)
    try:
        count = conn.execute("select count(*) from stock_adjustment_factor").fetchone()[0]
    finally:
        conn.close()
    assert count == 3  # 仅 A 的 seed 行


def test_cli_accepts_min_anchor_overlap_flag_in_plan_mode(tmp_path, capsys) -> None:
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)

    exit_code = module.main(["--db-path", db_path, "--min-anchor-overlap", "2"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry_run"
    assert payload["mode"] == "plan"


def test_execute_without_skip_triggers_outcome_maturity_wrapper(tmp_path) -> None:
    # 最小 fixture 缺少观测表：maturity 返回 not_ready，脚本如实降级为 partial，
    # 但因子行已写入（写入与成熟触发解耦）。
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)

    result = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=_fake_client(),
        execute=True,
        governance_lock=True,
    )

    assert result["status"] == "partial_completed"
    assert result["inserted_count"] == 2
    assert result["outcome_maturity"]["status"] == "not_ready"


def test_start_date_filter_limits_cells_to_native_era(tmp_path) -> None:
    module = _load_script()
    db_path = str(tmp_path / "moss.duckdb")
    _create_fixture_db(db_path)
    # 追加一条 tushare 代际缺口行（signal 与 forward 都在 2025）
    conn = duckdb.connect(db_path)
    try:
        conn.execute(
            "insert into livermore_candidate_history values (?, ?, ?, ?, ?)",
            ["2025-03-04", "600000.SH", "2025-04-02", 0.01, None],
        )
    finally:
        conn.close()

    unfiltered = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=_fake_client(),
    )
    assert unfiltered["missing_cell_count"] == 4
    assert unfiltered["era_split"] == {"native_era": 2, "tushare_era": 2}

    filtered = module.backfill_stock_adjustment_factor_from_choice(
        duckdb_path=db_path,
        client=_fake_client(),
        start_date="2026-01-05",
    )
    assert filtered["missing_cell_count"] == 2
    assert filtered["era_split"] == {"native_era": 2, "tushare_era": 0}
    # 无锚股票（600000.SH 无既有因子行）只在未过滤计划中出现
    assert unfiltered["codes_without_anchor"] == ["600000.SH"]
    assert filtered["codes_without_anchor"] == []
