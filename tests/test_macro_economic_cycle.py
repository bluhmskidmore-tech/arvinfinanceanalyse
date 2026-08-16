from __future__ import annotations

from datetime import date

from backend.app.core_finance.macro.economic_cycle import compute_economic_cycle


def _row(
    trade_date: date,
    *,
    pmi: float | None,
    cpi_yoy: float | None = 1.5,
    ppi_yoy: float | None = 0.5,
    m2_yoy: float | None = 8.0,
    social_financing_yoy: float | None = 9.0,
    term_spread_10y_1y: float | None = 60.0,
) -> dict[str, object]:
    return {
        "trade_date": trade_date,
        "pmi": pmi,
        "cpi_yoy": cpi_yoy,
        "ppi_yoy": ppi_yoy,
        "m2_yoy": m2_yoy,
        "social_financing_yoy": social_financing_yoy,
        "term_spread_10y_1y": term_spread_10y_1y,
    }


def test_economic_cycle_warns_missing_and_differs_from_zero_fill() -> None:
    rows_with_missing = [
        _row(date(2026, 6, 30), pmi=52.0),
        _row(date(2026, 5, 31), pmi=None),
        _row(date(2026, 4, 30), pmi=51.0),
        _row(date(2026, 3, 31), pmi=50.0),
        _row(date(2026, 2, 28), pmi=49.0),
        _row(date(2026, 1, 31), pmi=48.0),
    ]
    rows_with_zero = [{**row, "pmi": 0.0 if row.get("pmi") is None else row.get("pmi")} for row in rows_with_missing]

    missing_payload = compute_economic_cycle(rows_with_missing, report_date=date(2026, 6, 30))
    zero_payload = compute_economic_cycle(rows_with_zero, report_date=date(2026, 6, 30))

    assert missing_payload["data_status"] == "degraded"
    assert "PMI_MISSING" in missing_payload["warnings"]
    # 缺失月不得伪装成 0：0 填充会把动量算成 down 并计入 complete 结果；
    # 缺失则动量不可算（None）、追加专属 warning 并降级。
    assert "PMI_MOMENTUM_UNAVAILABLE" in missing_payload["warnings"]
    assert missing_payload["growth_momentum"] is None
    assert zero_payload["growth_momentum"] == "down"
    assert zero_payload["data_status"] == "complete"


# ---------------------------------------------------------------------------
# fail-closed 最小输入门槛（审计 H-1）
# ---------------------------------------------------------------------------


def test_economic_cycle_single_empty_row_fails_closed() -> None:
    """路由侧 _load_macro_wide_rows 在无数据时注入单行空行：不得再输出衰退 + 7-10Y。"""
    payload = compute_economic_cycle([{"trade_date": date(2026, 6, 30)}], report_date=date(2026, 6, 30))

    assert payload["data_status"] == "unavailable"
    assert payload["cycle_phase"] == "unknown"
    assert payload["cycle_phase_cn"] == "数据不足"
    assert payload["strategy"] == {}
    assert payload["growth_score"] is None
    assert payload["inflation_score"] is None
    assert payload["phase_scores"] == {}
    assert "PMI_CORE_INPUT_MISSING" in payload["warnings"]
    assert "CPI_YOY_CORE_INPUT_MISSING" in payload["warnings"]
    assert "MACRO_MONTHLY_SAMPLE_SHORT" in payload["warnings"]
    assert "7-10" not in str(payload["strategy"])


_MONTH_ENDS = [
    date(2026, 6, 30),
    date(2026, 5, 31),
    date(2026, 4, 30),
    date(2026, 3, 31),
    date(2026, 2, 28),
    date(2026, 1, 31),
]


def test_economic_cycle_missing_core_pmi_fails_closed() -> None:
    rows = [_row(d, pmi=None) for d in _MONTH_ENDS]
    payload = compute_economic_cycle(rows, report_date=date(2026, 6, 30))

    assert payload["data_status"] == "unavailable"
    assert payload["cycle_phase"] == "unknown"
    assert payload["strategy"] == {}
    assert "PMI_CORE_INPUT_MISSING" in payload["warnings"]
    # 观察值诚实披露：CPI 有值时仍应出现在 indicators 中
    assert payload["indicators"]["cpi_yoy"] == 1.5


def test_economic_cycle_missing_core_cpi_fails_closed() -> None:
    rows = [_row(d, pmi=52.0, cpi_yoy=None) for d in _MONTH_ENDS]
    payload = compute_economic_cycle(rows, report_date=date(2026, 6, 30))

    assert payload["data_status"] == "unavailable"
    assert payload["cycle_phase"] == "unknown"
    assert payload["strategy"] == {}
    assert "CPI_YOY_CORE_INPUT_MISSING" in payload["warnings"]


def test_economic_cycle_short_monthly_sample_fails_closed() -> None:
    rows = [
        _row(date(2026, 6, 30), pmi=52.0),
        _row(date(2026, 5, 31), pmi=51.0),
    ]
    payload = compute_economic_cycle(rows, report_date=date(2026, 6, 30))

    assert payload["data_status"] == "unavailable"
    assert payload["cycle_phase"] == "unknown"
    assert payload["strategy"] == {}
    assert "MACRO_MONTHLY_SAMPLE_SHORT" in payload["warnings"]


def test_economic_cycle_exactly_three_months_fails_closed() -> None:
    """恰好 3 个月样本：动量窗口（近3月 vs 前一窗口）无法构成，门槛 fail-closed（H-1 残余）。

    旧门槛 =3 时会放行：动量全部 None → 计 0 分、warnings 为空 → 伪装成
    complete，growth 上限只剩 45（<50），通胀温和时必然输出"衰退 + 7-10Y"。
    """
    rows = [_row(d, pmi=52.0) for d in _MONTH_ENDS[:3]]
    payload = compute_economic_cycle(rows, report_date=date(2026, 6, 30))

    assert payload["data_status"] == "unavailable"
    assert payload["cycle_phase"] == "unknown"
    assert payload["strategy"] == {}
    assert "MACRO_MONTHLY_SAMPLE_SHORT" in payload["warnings"]
    assert "7-10" not in str(payload["strategy"])


def test_economic_cycle_four_contiguous_months_minimum_computable() -> None:
    """4 个连续月是动量可算的最小样本：近3月槽位齐全 + 对照窗 1 点 → complete。"""
    pmi = [55.0, 54.0, 53.0, 50.0]
    rows = [_row(d, pmi=pmi[i]) for i, d in enumerate(_MONTH_ENDS[:4])]
    payload = compute_economic_cycle(rows, report_date=date(2026, 6, 30))

    assert payload["data_status"] == "complete"
    assert payload["warnings"] == []
    # 近3月均值 54 vs 对照窗（3 个月前）50 → up
    assert payload["growth_momentum"] == "up"
    # 30(PMI>50) + 25(动量 up) + 0(M2 flat) + 0(社融 flat) + 15(期限利差>50bp)
    assert payload["growth_score"] == 70.0


# ---------------------------------------------------------------------------
# 黄金样本：评分权重手算 + 象限边界 + 改名锁定（审计 M-2）
# ---------------------------------------------------------------------------


def test_economic_cycle_full_score_golden_overheat() -> None:
    """全部增长/通胀分项拉满：growth=30+25+15+15+15=100，inflation=40+20+20+20=100。"""
    pmi = [55.0, 54.0, 53.0, 50.0, 49.0, 48.0]  # 近3月均值54 > 前3月均值49 → up
    cpi = [3.5, 3.4, 3.3, 3.0, 2.9, 2.8]  # up；今值 3.5 > 3
    ppi = [2.5, 2.4, 2.3, 2.0, 1.9, 1.8]  # up；今值 2.5 > 2
    m2 = [10.0, 9.5, 9.0, 8.0, 7.5, 7.0]  # up
    sf = [11.0, 10.5, 10.0, 9.0, 8.5, 8.0]  # up
    rows = [
        _row(
            d,
            pmi=pmi[i],
            cpi_yoy=cpi[i],
            ppi_yoy=ppi[i],
            m2_yoy=m2[i],
            social_financing_yoy=sf[i],
            term_spread_10y_1y=60.0,  # > 50bp → +15
        )
        for i, d in enumerate(_MONTH_ENDS)
    ]

    payload = compute_economic_cycle(rows, report_date=date(2026, 6, 30))

    assert payload["data_status"] == "complete"
    assert payload["growth_score"] == 100.0
    assert payload["inflation_score"] == 100.0
    # 过热象限标识符为 overheat（不再是 expansion，避免与 gate 域 expansion 同名反义）
    assert payload["cycle_phase"] == "overheat"
    assert payload["cycle_phase_cn"] == "过热"
    assert payload["strategy"]["recommended_duration"] == "2-3Y"
    assert set(payload["phase_scores"]) == {"recovery", "overheat", "stagflation", "recession"}
    assert "expansion" not in payload["phase_scores"]
    assert payload["phase_scores"]["overheat"] == 100.0
    assert payload["phase_scores"]["recession"] == 0.0


def _boundary_rows(term_spread: float) -> list[dict[str, object]]:
    """构造 growth/inflation 恰为 50 的样本（term_spread=30 时）。

    growth = 30(PMI 50.5>50) + 0(PMI 动量 down) + 15(M2 up) + 0(社融 down) + 5(期限利差 20-50bp)
    inflation = 40(CPI 3.5>3) + 10(PPI 1.0>0) + 0(CPI 动量 down) + 0(PPI 动量 down)
    """
    pmi = [50.5, 51.0, 52.0, 53.0, 54.0, 55.0]  # down
    cpi = [3.5, 3.6, 3.7, 3.8, 3.9, 4.0]  # down
    ppi = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]  # down
    m2 = [9.0, 8.5, 8.0, 7.5, 7.0, 6.5]  # up
    sf = [8.0, 9.0, 10.0, 11.0, 12.0, 13.0]  # down
    return [
        _row(
            d,
            pmi=pmi[i],
            cpi_yoy=cpi[i],
            ppi_yoy=ppi[i],
            m2_yoy=m2[i],
            social_financing_yoy=sf[i],
            term_spread_10y_1y=term_spread,
        )
        for i, d in enumerate(_MONTH_ENDS)
    ]


def test_economic_cycle_boundary_scores_50_are_high() -> None:
    """growth=50 且 inflation=50：>=50 判 high，边界值落入过热象限。"""
    payload = compute_economic_cycle(_boundary_rows(term_spread=30.0), report_date=date(2026, 6, 30))

    assert payload["growth_score"] == 50.0
    assert payload["inflation_score"] == 50.0
    assert payload["cycle_phase"] == "overheat"
    assert payload["cycle_phase_cn"] == "过热"


def test_economic_cycle_boundary_growth_45_stagflation() -> None:
    """同一样本仅将期限利差降到 20bp 以下（+0 分）：growth=45 < 50 → 滞胀。"""
    payload = compute_economic_cycle(_boundary_rows(term_spread=10.0), report_date=date(2026, 6, 30))

    assert payload["growth_score"] == 45.0
    assert payload["inflation_score"] == 50.0
    assert payload["cycle_phase"] == "stagflation"
    assert payload["strategy"]["recommended_duration"] == "1-2Y"


def test_economic_cycle_gap_month_momentum_slot_aligned_degrades() -> None:
    """缺月不得跨槽拼接（审计 M-1 修复）：近3月窗口缺 4 月时动量不可算并降级。

    旧行为把 [6,5,3] 月拼成"近3月"与 [2,1,12] 月对比，窗口跨度不对称且与
    连续月样本同分。新行为：槽位对齐后动量 None → 专属 warning + degraded，
    growth_momentum 不再伪装成 "flat"，得分与连续月样本区分开。
    """
    gap_month_ends = [
        date(2026, 6, 30),
        date(2026, 5, 31),
        # 缺 2026-04
        date(2026, 3, 31),
        date(2026, 2, 28),
        date(2026, 1, 31),
        date(2025, 12, 31),
    ]
    pmi = [55.0, 54.0, 53.0, 50.0, 49.0, 48.0]
    rows = [_row(d, pmi=pmi[i]) for i, d in enumerate(gap_month_ends)]
    contiguous_rows = [_row(d, pmi=pmi[i]) for i, d in enumerate(_MONTH_ENDS)]

    gap_payload = compute_economic_cycle(rows, report_date=date(2026, 6, 30))
    contiguous_payload = compute_economic_cycle(contiguous_rows, report_date=date(2026, 6, 30))

    assert gap_payload["growth_momentum"] is None
    assert gap_payload["data_status"] == "degraded"
    assert "PMI_MOMENTUM_UNAVAILABLE" in gap_payload["warnings"]
    # 缺月只影响动量分项（计 0 分），水平分项与利差分项保留
    assert gap_payload["growth_score"] == 45.0
    assert contiguous_payload["growth_momentum"] == "up"
    assert contiguous_payload["data_status"] == "complete"
    assert gap_payload["growth_score"] < contiguous_payload["growth_score"]


def test_economic_cycle_phase_scores_clipped_to_0_100() -> None:
    """不对称样本（growth=100、inflation=0）：recovery 原式=150，须 clip 到 100（审计 M-4）。"""
    pmi = [55.0, 54.0, 53.0, 50.0, 49.0, 48.0]  # up → 30+25
    cpi = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]  # down；今值 0.5 <= 1 → +0
    ppi = [-1.0, -0.9, -0.8, -0.7, -0.6, -0.5]  # down；今值 <= 0 → +0
    m2 = [10.0, 9.5, 9.0, 8.0, 7.5, 7.0]  # up → +15
    sf = [11.0, 10.5, 10.0, 9.0, 8.5, 8.0]  # up → +15
    rows = [
        _row(
            d,
            pmi=pmi[i],
            cpi_yoy=cpi[i],
            ppi_yoy=ppi[i],
            m2_yoy=m2[i],
            social_financing_yoy=sf[i],
            term_spread_10y_1y=60.0,  # > 50bp → +15
        )
        for i, d in enumerate(_MONTH_ENDS)
    ]

    payload = compute_economic_cycle(rows, report_date=date(2026, 6, 30))

    assert payload["growth_score"] == 100.0
    assert payload["inflation_score"] == 0.0
    assert payload["cycle_phase"] == "recovery"
    assert payload["phase_scores"]["recovery"] == 100.0  # clip 前为 150
    assert payload["phase_scores"]["stagflation"] == 0.0  # clip 前为 -50
    assert payload["phase_scores"]["recession"] == 50.0
    assert payload["phase_scores"]["overheat"] == 0.0
    assert all(0.0 <= value <= 100.0 for value in payload["phase_scores"].values())
