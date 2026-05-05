from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from backend.app.core_finance.macro.toolkit import DEFAULT_DATA_SOURCES
from backend.app.core_finance.macro.toolkit.paths import OUTPUT_DIR
from backend.app.core_finance.macro.toolkit.runner import (
    OMITTED_SOURCE_SCRIPTS,
    PROJECT_ROOT,
    TOOLKIT_ROOT,
    MacroToolkitScript,
    get_toolkit_script,
    iter_toolkit_scripts,
)
from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_alias
from backend.app.governance.settings import get_settings
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ui/macro/toolkit", tags=["macro-toolkit"])

_SOURCE_CHECK_ALIASES = (
    "sh000300",
    "CU0",
    "DR007.IB",
    "M0067855",
    "S0059747",
    "S0059760",
    "M0041813",
)

_ANALYSIS_INDICATORS = (
    {"key": "hs300", "alias": "sh000300", "label": "沪深300", "unit": "点", "group": "风险资产"},
    {"key": "copper", "alias": "CU0", "label": "铜主力", "unit": "元/吨", "group": "工业需求"},
    {"key": "usdcny", "alias": "M0067855", "label": "美元兑人民币", "unit": "", "group": "汇率"},
    {"key": "dr007", "alias": "DR007.IB", "label": "DR007", "unit": "%", "group": "流动性"},
    {"key": "ncd_3m", "alias": "M0041813", "label": "3M NCD", "unit": "%", "group": "资金利率"},
    {"key": "gov_5y", "alias": "S0059747", "label": "5Y 国债", "unit": "%", "group": "利率"},
    {"key": "gov_10y", "alias": "S0059749", "label": "10Y 国债", "unit": "%", "group": "利率"},
    {"key": "aa_5y", "alias": "S0059760", "label": "5Y AA 信用债", "unit": "%", "group": "信用"},
)


class MacroToolkitRunRequest(BaseModel):
    argv: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=120, ge=5, le=600)


@router.get("/scripts")
def macro_toolkit_scripts() -> dict[str, object]:
    settings = get_settings()
    scripts = [_script_payload(script) for script in iter_toolkit_scripts()]
    return _envelope(
        "macro_toolkit.scripts",
        {
            "default_data_sources": list(DEFAULT_DATA_SOURCES),
            "toolkit_root": str(TOOLKIT_ROOT),
            "output_dir": str(OUTPUT_DIR),
            "scripts": scripts,
            "groups": sorted({str(item["group"]) for item in scripts}),
            "omitted_scripts": OMITTED_SOURCE_SCRIPTS,
            "output_files": _output_files(),
            "source_checks": _source_checks(settings.duckdb_path),
            "warnings": [
                (
                    "cffexmemberrank member-rank data has scripts and CSV output contracts, "
                    "but no formal DuckDB table is materialized yet."
                )
            ],
        },
    )


@router.get("/analysis")
def macro_toolkit_analysis() -> dict[str, object]:
    settings = get_settings()
    indicators = _analysis_indicators(settings.duckdb_path)
    indicator_by_key = {str(item["key"]): item for item in indicators}
    output_files = _output_files()
    signal_cards = _analysis_signal_cards(indicator_by_key, output_files)
    hit_count = sum(1 for item in indicators if item["latest_value"] is not None)
    coverage = {
        "indicator_count": len(indicators),
        "hit_count": hit_count,
        "hit_rate": round(hit_count / len(indicators), 4) if indicators else 0,
        "script_count": len(iter_toolkit_scripts()),
        "output_file_count": len(output_files),
    }
    conclusion = _analysis_conclusion(signal_cards, coverage)
    return _envelope(
        "macro_toolkit.analysis",
        {
            "default_data_sources": list(DEFAULT_DATA_SOURCES),
            "as_of_date": _latest_indicator_date(indicators),
            "conclusion": conclusion,
            "coverage": coverage,
            "indicators": indicators,
            "signal_cards": signal_cards,
            "output_files": output_files,
            "source_checks": _source_checks(settings.duckdb_path),
            "warnings": _analysis_warnings(coverage),
        },
    )


@router.post("/scripts/{name}/run")
def macro_toolkit_run(name: str, request: MacroToolkitRunRequest | None = None) -> dict[str, object]:
    run_request = request or MacroToolkitRunRequest()
    try:
        script = get_toolkit_script(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    env = os.environ.copy()
    existing_python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(TOOLKIT_ROOT), str(PROJECT_ROOT), existing_python_path) if part
    )
    try:
        completed = subprocess.run(
            [sys.executable, str(script.path), *run_request.argv],
            cwd=str(TOOLKIT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=run_request.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "script": _script_payload(script),
            "exit_code": None,
            "stdout": _tail_text(exc.stdout),
            "stderr": _tail_text(exc.stderr),
            "output_files": _output_files(),
            "message": f"script exceeded {run_request.timeout_seconds}s timeout",
        }

    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "script": _script_payload(script),
        "exit_code": completed.returncode,
        "stdout": _tail_text(completed.stdout),
        "stderr": _tail_text(completed.stderr),
        "output_files": _output_files(),
    }


def _script_payload(script: MacroToolkitScript) -> dict[str, object]:
    return {
        "name": script.name,
        "filename": script.filename,
        "group": script.group,
        "default_data_sources": list(script.default_data_sources),
        "optional_dependencies": list(script.optional_dependencies),
        "notes": script.notes,
        "path": str(script.path.relative_to(TOOLKIT_ROOT)),
        "available": script.path.exists(),
    }


def _output_files() -> list[dict[str, object]]:
    if not OUTPUT_DIR.exists():
        return []
    files: list[dict[str, object]] = []
    for path in sorted(OUTPUT_DIR.glob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            }
        )
    return files


def _source_checks(duckdb_path: str | Path) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for alias in _SOURCE_CHECK_ALIASES:
        frame = load_series_by_alias(alias, duckdb_path=duckdb_path)
        latest = None
        if not frame.empty:
            latest_row = frame.sort_values("date").iloc[-1]
            latest = {
                "date": str(latest_row["date"])[:10],
                "series_id": str(latest_row["series_id"]),
                "vendor_name": str(latest_row["vendor_name"]),
                "value": float(latest_row["value"]),
            }
        checks.append({"alias": alias, "row_count": int(len(frame)), "latest": latest})
    return checks


def _analysis_indicators(duckdb_path: str | Path) -> list[dict[str, object]]:
    indicators: list[dict[str, object]] = []
    for config in _ANALYSIS_INDICATORS:
        frame = load_series_by_alias(str(config["alias"]), duckdb_path=duckdb_path)
        indicators.append(_indicator_payload(config, frame))
    return indicators


def _indicator_payload(config: dict[str, str], frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {
            "key": config["key"],
            "alias": config["alias"],
            "label": config["label"],
            "group": config["group"],
            "unit": config["unit"],
            "row_count": 0,
            "latest_date": None,
            "latest_value": None,
            "previous_value": None,
            "change": None,
            "change_pct": None,
            "source": None,
            "series_id": None,
            "quality": "missing",
        }

    ordered = frame.sort_values("date")
    latest = ordered.iloc[-1]
    previous = ordered.iloc[-2] if len(ordered) > 1 else None
    latest_value = float(latest["value"])
    previous_value = float(previous["value"]) if previous is not None else None
    change = latest_value - previous_value if previous_value is not None else None
    change_pct = (
        round((change / abs(previous_value)) * 100, 4)
        if change is not None and previous_value not in (None, 0)
        else None
    )
    return {
        "key": config["key"],
        "alias": config["alias"],
        "label": config["label"],
        "group": config["group"],
        "unit": config["unit"],
        "row_count": int(len(ordered)),
        "latest_date": str(latest["date"])[:10],
        "latest_value": round(latest_value, 4),
        "previous_value": round(previous_value, 4) if previous_value is not None else None,
        "change": round(change, 4) if change is not None else None,
        "change_pct": change_pct,
        "source": str(latest["vendor_name"]),
        "series_id": str(latest["series_id"]),
        "quality": "ok",
    }


def _analysis_signal_cards(
    indicator_by_key: dict[str, dict[str, object]],
    output_files: list[dict[str, object]],
) -> list[dict[str, object]]:
    cards = [
        _liquidity_card(indicator_by_key),
        _risk_appetite_card(indicator_by_key),
        _credit_card(indicator_by_key),
        _script_output_card(output_files),
    ]
    return cards


def _liquidity_card(indicator_by_key: dict[str, dict[str, object]]) -> dict[str, object]:
    dr007 = _number(indicator_by_key.get("dr007"), "latest_value")
    ncd = _number(indicator_by_key.get("ncd_3m"), "latest_value")
    if dr007 is None and ncd is None:
        return _signal_card("liquidity", "流动性", "数据不足", "missing", None, ["DR007 / 3M NCD 未命中"])
    anchor = dr007 if dr007 is not None else ncd
    assert anchor is not None
    if anchor <= 1.9:
        stance, tone, score = "偏松", "positive", 78
    elif anchor >= 2.3:
        stance, tone, score = "偏紧", "negative", 32
    else:
        stance, tone, score = "中性", "neutral", 55
    evidence = []
    if dr007 is not None:
        evidence.append(f"DR007 {dr007:.2f}%")
    if ncd is not None:
        evidence.append(f"3M NCD {ncd:.2f}%")
    return _signal_card("liquidity", "流动性", stance, tone, score, evidence)


def _risk_appetite_card(indicator_by_key: dict[str, dict[str, object]]) -> dict[str, object]:
    hs300_change = _number(indicator_by_key.get("hs300"), "change_pct")
    copper_change = _number(indicator_by_key.get("copper"), "change_pct")
    values = [item for item in (hs300_change, copper_change) if item is not None]
    if not values:
        return _signal_card("risk_appetite", "风险偏好", "数据不足", "missing", None, ["权益 / 工业品缺少可比较序列"])
    average = sum(values) / len(values)
    if average > 0.5:
        stance, tone, score = "改善", "positive", 72
    elif average < -0.5:
        stance, tone, score = "转弱", "negative", 35
    else:
        stance, tone, score = "震荡", "neutral", 52
    evidence = []
    if hs300_change is not None:
        evidence.append(f"沪深300 {hs300_change:+.2f}%")
    if copper_change is not None:
        evidence.append(f"铜主力 {copper_change:+.2f}%")
    return _signal_card("risk_appetite", "风险偏好", stance, tone, score, evidence)


def _credit_card(indicator_by_key: dict[str, dict[str, object]]) -> dict[str, object]:
    gov_5y = _number(indicator_by_key.get("gov_5y"), "latest_value")
    aa_5y = _number(indicator_by_key.get("aa_5y"), "latest_value")
    if gov_5y is None or aa_5y is None:
        return _signal_card("credit", "信用利差", "数据不足", "missing", None, ["5Y 国债 / 5Y AA 信用债未同时命中"])
    spread_bp = (aa_5y - gov_5y) * 100
    if spread_bp >= 90:
        stance, tone, score = "偏宽", "negative", 38
    elif spread_bp <= 45:
        stance, tone, score = "偏窄", "positive", 70
    else:
        stance, tone, score = "中性", "neutral", 55
    return _signal_card("credit", "信用利差", stance, tone, score, [f"AA-国债 5Y {spread_bp:.1f}bp"])


def _script_output_card(output_files: list[dict[str, object]]) -> dict[str, object]:
    if output_files:
        latest = max(output_files, key=lambda item: str(item["modified_at"]))
        return _signal_card(
            "outputs",
            "脚本产物",
            "已生成",
            "positive",
            min(100, 45 + len(output_files) * 5),
            [f"{len(output_files)} 个输出文件", str(latest["name"])],
        )
    return _signal_card(
        "outputs",
        "脚本产物",
        "待生成",
        "neutral",
        45,
        ["尚未在 data/macro_toolkit/output 发现输出文件"],
    )


def _signal_card(
    key: str,
    title: str,
    stance: str,
    tone: str,
    score: int | None,
    evidence: list[str],
) -> dict[str, object]:
    return {
        "key": key,
        "title": title,
        "stance": stance,
        "tone": tone,
        "score": score,
        "evidence": evidence,
    }


def _analysis_conclusion(
    signal_cards: list[dict[str, object]],
    coverage: dict[str, object],
) -> dict[str, object]:
    hit_rate = float(coverage["hit_rate"])
    if hit_rate < 0.6:
        return {
            "stance": "数据不足",
            "tone": "missing",
            "summary": "核心指标命中不足，当前页面只展示可用证据，不形成完整方向判断。",
            "recommended_action": "先补齐缺失的 Choice/Tushare 序列，再运行信号脚本。",
        }

    tones = [str(card["tone"]) for card in signal_cards if card["tone"] != "missing"]
    positive = tones.count("positive")
    negative = tones.count("negative")
    if positive > negative:
        stance, tone = "中性偏积极", "positive"
        summary = "流动性、风险资产或信用信号中积极证据更多，宏观环境暂不构成明显风险压制。"
        action = "维持观察，可优先运行 signal_aggregator / risk_monitor 形成交易层信号。"
    elif negative > positive:
        stance, tone = "中性偏谨慎", "negative"
        summary = "偏紧、转弱或信用压力信号占优，宏观环境需要降低冒进判断。"
        action = "先复核利率、信用和风险偏好序列，再做仓位或组合动作。"
    else:
        stance, tone = "中性观察", "neutral"
        summary = "多空证据接近，当前更适合观察数据延续性，而不是给出单边结论。"
        action = "关注下一批 Choice/Tushare 更新，并运行信号聚合脚本确认。"
    return {"stance": stance, "tone": tone, "summary": summary, "recommended_action": action}


def _analysis_warnings(coverage: dict[str, object]) -> list[str]:
    warnings = [
        (
            "cffexmemberrank member-rank data has scripts and CSV output contracts, "
            "but no formal DuckDB table is materialized yet."
        )
    ]
    if int(coverage["output_file_count"]) == 0:
        warnings.append("No macro toolkit output files have been generated yet; script result panels use live source data only.")
    return warnings


def _latest_indicator_date(indicators: list[dict[str, object]]) -> str | None:
    dates = [str(item["latest_date"]) for item in indicators if item["latest_date"]]
    return max(dates) if dates else None


def _number(item: dict[str, object] | None, field: str) -> float | None:
    if item is None or item.get(field) is None:
        return None
    return float(item[field])


def _tail_text(value: str | bytes | None, limit: int = 12000) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    return text[-limit:]


def _envelope(result_kind: str, result: dict[str, object]) -> dict[str, object]:
    generated_at = datetime.now(UTC).isoformat()
    return {
        "result_meta": {
            "trace_id": f"macro-toolkit-{uuid.uuid4().hex[:12]}",
            "basis": "analytical",
            "result_kind": result_kind,
            "formal_use_allowed": False,
            "source_version": "macro_toolkit_registry",
            "vendor_version": "choice+tushare",
            "rule_version": "rv_macro_toolkit_ui_v1",
            "cache_version": "none",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "scenario_flag": False,
            "generated_at": generated_at,
            "tables_used": [
                "fact_choice_macro_daily",
                "choice_market_snapshot",
                "fx_daily_mid",
                "fact_formal_yield_curve_daily",
                "std_external_macro_daily",
            ],
            "evidence_rows": _evidence_rows(result),
        },
        "result": result,
    }


def _evidence_rows(result: dict[str, object]) -> int | None:
    for key in ("scripts", "indicators"):
        value = result.get(key)
        if isinstance(value, list):
            return len(value)
    return None
