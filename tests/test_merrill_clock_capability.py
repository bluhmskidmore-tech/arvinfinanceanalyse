"""Merrill Clock (中国版) library + capability surface tests."""

from __future__ import annotations

import importlib.util
from datetime import date

import pandas as pd
import pytest

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.core_finance.macro import compute_merrill_clock_payload
from backend.app.core_finance.macro.merrill_clock import (
    MERRILL_CLOCK_RULE_VERSION,
    compute_asset_scores,
    compute_growth_momentum,
    compute_inflation_momentum,
    compute_liquidity_momentum,
    compute_momentum,
    get_regime_label,
)
from backend.app.core_finance.macro.toolkit import get_toolkit_script


def _legacy_merrill_module(monkeypatch):
    toolkit_root = get_toolkit_script("merrill_clock_cn").path.parent.parent
    monkeypatch.syspath_prepend(str(toolkit_root))
    script = get_toolkit_script("merrill_clock_cn")
    spec = importlib.util.spec_from_file_location("_legacy_merrill_clock_cn_capability", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    return legacy


def _synthetic_clock_frame(periods: int = 24) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="MS")
    # 增长加速、通胀升温、流动性宽松 → 过热，偏好股票/商品
    return pd.DataFrame(
        {
            "pmi": [48 + i * 0.15 for i in range(periods)],
            "industrial_va": [3.0 + i * 0.1 for i in range(periods)],
            "cpi_yoy": [0.5 + i * 0.05 for i in range(periods)],
            "ppi_yoy": [-1.0 + i * 0.12 for i in range(periods)],
            "m2_yoy": [8.0 + i * 0.05 for i in range(periods)],
            "social_financing": [9.0 + i * 0.04 for i in range(periods)],
        },
        index=index,
    )


def test_merrill_clock_helpers_match_legacy_script(monkeypatch) -> None:
    legacy = _legacy_merrill_module(monkeypatch)
    frame = _synthetic_clock_frame()

    assert compute_momentum(frame["pmi"]).iloc[-1] == pytest.approx(
        legacy.compute_momentum(frame["pmi"]).iloc[-1]
    )
    assert compute_growth_momentum(frame).iloc[-1] == pytest.approx(
        legacy.compute_growth_momentum(frame).iloc[-1]
    )
    assert compute_inflation_momentum(frame).iloc[-1] == pytest.approx(
        legacy.compute_inflation_momentum(frame).iloc[-1]
    )
    assert compute_liquidity_momentum(frame).iloc[-1] == pytest.approx(
        legacy.compute_liquidity_momentum(frame).iloc[-1]
    )

    g = float(compute_growth_momentum(frame).iloc[-1])
    i = float(compute_inflation_momentum(frame).iloc[-1])
    liq = float(compute_liquidity_momentum(frame).iloc[-1])
    scores = compute_asset_scores(g, i, liq)
    legacy_scores = legacy.compute_asset_scores(g, i, liq)
    for asset in scores:
        assert scores[asset] == pytest.approx(legacy_scores[asset])
    assert get_regime_label(g, i) == legacy.get_regime_label(g, i)


def test_merrill_clock_payload_matches_script_latest_snapshot(monkeypatch) -> None:
    legacy = _legacy_merrill_module(monkeypatch)
    frame = _synthetic_clock_frame()
    report_date = frame.index[-1].date()

    growth = legacy.compute_growth_momentum(frame)
    inflation = legacy.compute_inflation_momentum(frame)
    liquidity = legacy.compute_liquidity_momentum(frame)
    merged = pd.DataFrame(
        {
            "growth_momentum": growth,
            "inflation_momentum": inflation,
            "liquidity_momentum": liquidity,
        }
    ).dropna()
    latest = merged.iloc[-1]
    g = float(latest["growth_momentum"])
    i = float(latest["inflation_momentum"])
    liq = float(latest["liquidity_momentum"])
    expected_scores = legacy.compute_asset_scores(g, i, liq)
    expected_regime = legacy.get_regime_label(g, i)

    payload = compute_merrill_clock_payload(frame, report_date=report_date)

    assert payload["rule_version"] == MERRILL_CLOCK_RULE_VERSION
    assert payload["data_status"] in {"complete", "degraded"}
    assert payload["growth_momentum"] == pytest.approx(round(g, 4))
    assert payload["inflation_momentum"] == pytest.approx(round(i, 4))
    assert payload["liquidity_momentum"] == pytest.approx(round(liq, 4))
    assert payload["regime_label"] == expected_regime
    assert payload["asset_scores"]["股票"] == pytest.approx(round(expected_scores["股票"], 4))
    assert payload["top_asset"] in expected_scores
    assert isinstance(payload["warnings"], list)
    # 系统源未覆盖的可选增长代理应提示，但不单独阻断 complete
    assert "PMI_NEW_ORDERS_UNAVAILABLE" in payload["warnings"]


def test_merrill_clock_payload_from_wide_rows_maps_aliases() -> None:
    start = date(2024, 1, 1)
    wide_rows = []
    for month in range(18):
        sample_date = date(start.year + (start.month + month - 1) // 12, (start.month + month - 1) % 12 + 1, 1)
        wide_rows.append(
            {
                "trade_date": sample_date,
                "biz_date": sample_date,
                "pmi": 49.0 + month * 0.1,
                "industrial_yoy": 4.0 + month * 0.05,
                "cpi_yoy": 0.8 + month * 0.02,
                "ppi_yoy": -0.5 + month * 0.04,
                "m2_yoy": 8.5 + month * 0.03,
                "social_financing_yoy": 9.2 + month * 0.02,
            }
        )
    # 宽表约定为降序
    wide_rows = list(reversed(wide_rows))
    payload = compute_merrill_clock_payload(wide_rows, report_date=date(2025, 6, 1))
    assert payload["data_status"] in {"complete", "degraded"}
    assert payload["regime_label"] in {"复苏", "过热", "滞胀", "衰退"}
    assert payload["asset_scores"]
    assert "INDUSTRIAL_VA_MISSING" not in payload["warnings"]


def test_merrill_clock_stalled_growth_inputs_degrade_instead_of_fake_stagflation() -> None:
    # 增长代理停更（常数序列 → rolling std=0 → 动量 NaN）时，
    # 不得把 NaN 当 0 输出"滞胀/衰退"，必须显式不可用。
    periods = 14
    index = pd.date_range("2025-01-01", periods=periods, freq="MS")
    frame = pd.DataFrame(
        {
            "pmi": [50.0] * periods,
            "industrial_va": [4.0] * periods,
            "cpi_yoy": [0.5 + i * 0.05 for i in range(periods)],
            "ppi_yoy": [-1.0 + i * 0.12 for i in range(periods)],
            "m2_yoy": [8.0 + i * 0.05 for i in range(periods)],
            "social_financing": [9.0 + i * 0.04 for i in range(periods)],
        },
        index=index,
    )

    growth = compute_growth_momentum(frame)
    assert growth.dropna().empty

    payload = compute_merrill_clock_payload(frame, report_date=index[-1].date())
    assert payload["data_status"] == "unavailable"
    assert payload["regime_label"] == "不可用"
    assert "MERRILL_CLOCK_MOMENTUM_INSUFFICIENT" in payload["warnings"]


def test_growth_momentum_normalizes_by_row_available_weight() -> None:
    # industrial_va 全 NaN 时，增长动量应等于 PMI 单指标动量，
    # 而不是被列级总权重 (0.30+0.25) 压缩约 45%。
    periods = 24
    index = pd.date_range("2024-01-01", periods=periods, freq="MS")
    pmi = pd.Series([48 + i * 0.15 for i in range(periods)], index=index)
    frame = pd.DataFrame({"pmi": pmi, "industrial_va": [float("nan")] * periods}, index=index)

    growth = compute_growth_momentum(frame)
    pmi_only = compute_momentum(pmi)

    assert growth.iloc[-1] == pytest.approx(float(pmi_only.iloc[-1]))


def test_merrill_clock_payload_unavailable_without_inputs() -> None:
    payload = compute_merrill_clock_payload([], report_date=date(2026, 7, 10))
    assert payload["data_status"] == "unavailable"
    assert payload["regime_label"] == "不可用"
    assert payload["growth_momentum"] is None
    assert "NO_MERRILL_CLOCK_INPUTS" in payload["warnings"]
    assert payload["observation_only"] is True
    assert payload["formal_use_allowed"] is False


def test_merrill_clock_payload_marks_observation_only_flags() -> None:
    frame = _synthetic_clock_frame()
    payload = compute_merrill_clock_payload(frame, report_date=frame.index[-1].date())
    assert payload["data_status"] in {"complete", "degraded"}
    assert payload["observation_only"] is True
    assert payload["formal_use_allowed"] is False


def test_merrill_clock_capability_card_surfaces_regime_and_top_asset() -> None:
    frame = _synthetic_clock_frame()
    raw = compute_merrill_clock_payload(frame, report_date=frame.index[-1].date())
    definition = next(
        item for item in macro_toolkit_route._CAPABILITY_DEFINITIONS if item["key"] == "merrill_clock_cn"
    )
    card = macro_toolkit_route._capability_result_card(definition, raw)

    assert definition["route_status"] == "wired"
    assert definition["frontend_status"] == "visible"
    assert definition["legacy_module"] == "Merrill"
    assert set(definition["data_aliases"]) == {
        "M0017126",
        "M0000545",
        "M0000612",
        "M0001227",
        "M0001385",
        "M5525763",
    }
    assert card["key"] == "merrill_clock_cn"
    assert card["status"] in {"complete", "degraded"}
    assert card["primary_metric"]["label"] == "象限"
    assert card["primary_metric"]["value"] == raw["regime_label"]
    assert raw["regime_label"] in str(card["headline"])
    assert raw["top_asset"] in str(card["headline"])
    assert any(item.startswith("regime=") for item in card["evidence"])
    assert any(item.startswith("top=") for item in card["evidence"])
    assert card["score"] == pytest.approx(raw["top_asset_score"], abs=1e-3)


def test_macro_capability_results_surfaces_merrill_clock_cn(monkeypatch) -> None:
    frame = _synthetic_clock_frame()
    report_date = frame.index[-1].date()
    expected = compute_merrill_clock_payload(frame, report_date=report_date)

    monkeypatch.setattr(macro_toolkit_route, "_parse_report_date", lambda value: report_date)
    monkeypatch.setattr(
        macro_toolkit_route,
        "_load_macro_capability_context",
        lambda *_args, **_kwargs: ([], None, []),
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "load_series_by_aliases",
        lambda *_args, **_kwargs: {},
    )

    def fake_wide_rows(*_args, **_kwargs):
        rows = []
        for ts, row in frame.iterrows():
            rows.append(
                {
                    "trade_date": ts.date(),
                    "biz_date": ts.date(),
                    "pmi": float(row["pmi"]),
                    "industrial_yoy": float(row["industrial_va"]),
                    "cpi_yoy": float(row["cpi_yoy"]),
                    "ppi_yoy": float(row["ppi_yoy"]),
                    "m2_yoy": float(row["m2_yoy"]),
                    "social_financing_yoy": float(row["social_financing"]),
                }
            )
        return list(reversed(rows))

    monkeypatch.setattr(macro_toolkit_route, "_load_macro_wide_rows", fake_wide_rows)
    monkeypatch.setattr(
        macro_toolkit_route,
        "_risk_tensor_to_liquidity_inputs",
        lambda *_args, **_kwargs: ([], [], None),
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "build_bond_portfolio_profile",
        lambda *_args, **_kwargs: {"total_mv": 0.0, "weighted_duration": 0.0, "positions": []},
    )
    monkeypatch.setattr(macro_toolkit_route, "_current_gov_curve", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        macro_toolkit_route,
        "_with_capability_input_evidence",
        lambda key, result, **_kwargs: result,
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "_source_checks_for_aliases",
        lambda *_args, **_kwargs: {},
    )
    # 避免无关能力拖垮组装：只验证 merrill 进入结果集
    monkeypatch.setattr(
        macro_toolkit_route,
        "_run_capability",
        lambda key, fn: fn() if key == "merrill_clock_cn" else {"data_status": "unavailable", "warnings": ["skipped"]},
    )

    cards = macro_toolkit_route._macro_capability_results("unused.duckdb", report_date=report_date.isoformat())
    by_key = {item["key"]: item for item in cards}
    assert "merrill_clock_cn" in by_key
    card = by_key["merrill_clock_cn"]
    assert card["status"] in {"complete", "degraded"}
    assert card["result"]["regime_label"] == expected["regime_label"]
    assert card["result"]["rule_version"] == MERRILL_CLOCK_RULE_VERSION
    assert card["headline"]
    assert by_key["decision_summary"]["primary_metric"]["unit"] == f"/{len(macro_toolkit_route._CAPABILITY_DEFINITIONS) - 1}"


def test_decision_summary_denominator_includes_merrill_clock() -> None:
    non_decision = len(macro_toolkit_route._CAPABILITY_DEFINITIONS) - 1
    assert any(item["key"] == "merrill_clock_cn" for item in macro_toolkit_route._CAPABILITY_DEFINITIONS)
    cards = [
        {
            "key": f"m{index}",
            "legacy_module": "X",
            "label": "x",
            "group": "t",
            "status": "complete",
            "tone": "neutral",
            "headline": "ok",
        }
        for index in range(non_decision)
    ]
    definition = next(
        item for item in macro_toolkit_route._CAPABILITY_DEFINITIONS if item["key"] == "decision_summary"
    )
    card = macro_toolkit_route._decision_summary_card(definition, cards, date(2026, 7, 10))
    assert card["primary_metric"]["unit"] == f"/{non_decision}"
    assert non_decision >= 11  # M7-M15 + Crisis + Merrill


def test_merrill_clock_industrial_va_missing_is_non_blocking() -> None:
    # M-2: industrial_va 与路由 required=False 对齐，缺失只提示不可用。
    periods = 24
    index = pd.date_range("2024-01-01", periods=periods, freq="MS")
    frame = pd.DataFrame(
        {
            "pmi": [48 + i * 0.15 for i in range(periods)],
            "cpi_yoy": [0.5 + i * 0.05 for i in range(periods)],
            "ppi_yoy": [-1.0 + i * 0.12 for i in range(periods)],
            "m2_yoy": [8.0 + i * 0.05 for i in range(periods)],
            "social_financing": [9.0 + i * 0.04 for i in range(periods)],
        },
        index=index,
    )
    payload = compute_merrill_clock_payload(frame, report_date=index[-1].date())
    assert "INDUSTRIAL_VA_MISSING" not in payload["warnings"]
    assert "INDUSTRIAL_VA_UNAVAILABLE" in payload["warnings"]
    assert payload["data_status"] == "complete"
    assert payload["regime_label"] in {"复苏", "过热", "滞胀", "衰退"}


def test_merrill_clock_social_financing_warning_matches_route_spelling() -> None:
    # M-2: 社融 warning 与路由 SOCIAL_FINANCING_YOY_MISSING 对齐。
    periods = 24
    index = pd.date_range("2024-01-01", periods=periods, freq="MS")
    frame = pd.DataFrame(
        {
            "pmi": [48 + i * 0.15 for i in range(periods)],
            "industrial_va": [3.0 + i * 0.1 for i in range(periods)],
            "cpi_yoy": [0.5 + i * 0.05 for i in range(periods)],
            "ppi_yoy": [-1.0 + i * 0.12 for i in range(periods)],
            "m2_yoy": [8.0 + i * 0.05 for i in range(periods)],
        },
        index=index,
    )
    payload = compute_merrill_clock_payload(frame, report_date=index[-1].date())
    assert "SOCIAL_FINANCING_MISSING" not in payload["warnings"]
    assert "SOCIAL_FINANCING_YOY_MISSING" in payload["warnings"]
    assert payload["data_status"] == "degraded"


def test_wide_ffill_stops_after_monthly_stale_cap() -> None:
    # H-1: 月频 PMI 停更后，日频轴继续延伸不得超过 65 天 carry。
    report_date = date(2026, 7, 10)
    pmi_last = date(2026, 4, 1)  # ~100 天前，超过 monthly 65d 上限
    frames_by_alias = {
        alias: pd.DataFrame(columns=["date", "value", "series_id", "vendor_name"])
        for _, alias in macro_toolkit_route._WIDE_SERIES_ALIASES
    }
    frames_by_alias["M0017126"] = pd.DataFrame(
        {
            "date": pd.to_datetime([pmi_last]),
            "value": [50.2],
            "series_id": ["M0017126"],
            "vendor_name": ["choice"],
        }
    )
    frames_by_alias["DR007.IB"] = pd.DataFrame(
        {
            "date": pd.to_datetime([date(2026, 4, 1) + pd.Timedelta(days=i) for i in range(0, 101, 5)]),
            "value": [1.8 + i * 0.001 for i in range(21)],
            "series_id": ["CA.DR007"] * 21,
            "vendor_name": ["choice"] * 21,
        }
    )

    wide_rows = macro_toolkit_route._load_macro_wide_rows(
        "unused.duckdb",
        report_date,
        [],
        frames_by_alias=frames_by_alias,
    )
    assert wide_rows
    late_rows = [
        row
        for row in wide_rows
        if row.get("trade_date") is not None
        and (row["trade_date"] - pmi_last).days
        > macro_toolkit_route._WIDE_FFILL_MAX_STALE_DAYS["monthly"]
    ]
    assert late_rows
    assert all("pmi" not in row for row in late_rows)
    early_rows = [
        row
        for row in wide_rows
        if row.get("trade_date") is not None
        and 0 < (row["trade_date"] - pmi_last).days
        <= macro_toolkit_route._WIDE_FFILL_MAX_STALE_DAYS["monthly"]
    ]
    assert early_rows
    assert any("pmi" in row for row in early_rows)


def test_capability_input_evidence_marks_stale_required_inputs() -> None:
    # M-4: 两年前一条记录仍 available，但必须标 stale 并降级。
    report_date = date(2026, 7, 10)
    source_check_cache: dict[str, dict[str, object]] = {}
    for requirement in macro_toolkit_route._CAPABILITY_INPUT_REQUIREMENTS["merrill_clock_cn"]:
        for alias in requirement["aliases"]:
            source_check_cache[str(alias)] = {
                "alias": str(alias),
                "row_count": 0,
                "latest": None,
            }
    source_check_cache["M0017126"] = {
        "alias": "M0017126",
        "row_count": 1,
        "latest": {
            "date": "2024-06-01",
            "series_id": "M0017126",
            "vendor_name": "choice",
            "value": 50.0,
        },
    }

    item = macro_toolkit_route._capability_input_evidence_item(
        {
            "field": "pmi",
            "label": "PMI",
            "aliases": ("M0017126",),
            "warning": "PMI_MISSING",
            "required": True,
            "cadence": "monthly",
        },
        duckdb_path="unused.duckdb",
        report_date=report_date,
        wide_rows=[],
        source_check_cache=source_check_cache,
    )
    assert item["available"] is True
    assert item["stale"] is True
    assert item["stale_days"] is not None and item["stale_days"] > 45

    enriched = macro_toolkit_route._with_capability_input_evidence(
        "merrill_clock_cn",
        {"data_status": "complete", "warnings": []},
        duckdb_path="unused.duckdb",
        report_date=report_date,
        wide_rows=[],
        source_check_cache=source_check_cache,
    )
    assert enriched["data_status"] == "degraded"
    assert "PMI_STALE" in enriched["warnings"]
    assert "PMI_STALE" in enriched["input_evidence"]["stale_inputs"]
    # 其他 required 输入缺失会进入 missing_inputs，但不把 PMI 误判为 missing。
    assert "PMI_MISSING" not in enriched["input_evidence"]["missing_inputs"]
