from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import uuid
from datetime import UTC, date, datetime
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
    run_toolkit_script,
)
from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_alias
from backend.app.governance.settings import get_settings
from backend.app.repositories.cffex_member_rank_repo import DEFAULT_CFFEX_CONTRACTS, table_stats
from backend.app.services.cffex_member_rank_service import materialize_cffex_member_rank
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ui/macro/toolkit", tags=["macro-toolkit"])

_SOURCE_CHECK_ALIASES = (
    "sh000300",
    "CU0",
    "DR007.IB",
    "M0067855",
    "M0000612",
    "S0059747",
    "S0059749",
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

_CAPABILITY_DEFINITIONS = (
    {
        "key": "monetary_policy_stance",
        "legacy_module": "M7",
        "label": "货币政策立场",
        "group": "政策与资金面",
        "implementation_status": "library_ready",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("DR007.IB", "S0059743", "S0059749", "S0059760"),
        "next_step": "封装 /api/macro/monetary-policy-stance，并在本页接入政策立场卡。",
    },
    {
        "key": "yield_curve_shape",
        "legacy_module": "M8",
        "label": "收益率曲线形态",
        "group": "曲线",
        "implementation_status": "partial",
        "route_status": "partial",
        "frontend_status": "partial",
        "data_aliases": ("S0059743", "S0059747", "S0059749"),
        "next_step": "复用正式曲线表，把曲线形态纯函数输出接到宏观工具箱。",
    },
    {
        "key": "credit_spread_risk",
        "legacy_module": "M9",
        "label": "信用利差预警",
        "group": "信用",
        "implementation_status": "partial",
        "route_status": "partial",
        "frontend_status": "partial",
        "data_aliases": ("S0059652", "S0059670", "S0059760"),
        "next_step": "把信用利差风险/分位结果合并到本页信用信号区。",
    },
    {
        "key": "leading_indicator",
        "legacy_module": "M10",
        "label": "宏观领先指标",
        "group": "增长与通胀",
        "implementation_status": "library_ready",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("M0000612", "M0001385", "CU0", "S0059670"),
        "next_step": "补 PMI/M2/社融映射后输出领先指标指数。",
    },
    {
        "key": "liquidity_stress",
        "legacy_module": "M11",
        "label": "流动性压力测试",
        "group": "压力测试",
        "implementation_status": "library_ready",
        "route_status": "partial",
        "frontend_status": "partial",
        "data_aliases": ("DR007.IB", "M0041813"),
        "next_step": "接入资产/负债期限桶，避免只用市场代理指标。",
    },
    {
        "key": "cross_market_linkage",
        "legacy_module": "M12",
        "label": "跨市场联动",
        "group": "联动",
        "implementation_status": "library_ready",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("sh000300", "CU0", "M0067855"),
        "next_step": "把跨资产纯函数输出为联动矩阵和主导变量。",
    },
    {
        "key": "rate_turning_point",
        "legacy_module": "M13",
        "label": "利率拐点判断",
        "group": "曲线",
        "implementation_status": "library_ready",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("DR007.IB", "S0059747", "S0059749"),
        "next_step": "用正式曲线和资金利率输出拐点概率。",
    },
    {
        "key": "economic_cycle",
        "legacy_module": "M14",
        "label": "经济周期定位",
        "group": "增长与通胀",
        "implementation_status": "library_ready",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("M0000612", "M0001227", "M0001385", "CU0"),
        "next_step": "补齐增长/通胀宽表后输出周期象限。",
    },
    {
        "key": "macro_portfolio_impact",
        "legacy_module": "M15",
        "label": "宏观情景组合影响",
        "group": "组合影响",
        "implementation_status": "library_ready",
        "route_status": "partial",
        "frontend_status": "partial",
        "data_aliases": ("S0059749", "S0059760", "M0067855"),
        "next_step": "把组合暴露输入与宏观情景结果合并展示。",
    },
    {
        "key": "decision_summary",
        "legacy_module": "M16",
        "label": "宏观决策摘要",
        "group": "决策摘要",
        "implementation_status": "not_wired",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("DR007.IB", "S0059749", "sh000300", "M0067855"),
        "next_step": "聚合 M7-M15 后生成一屏决策摘要，而不是前端拼文案。",
    },
)


class MacroToolkitRunRequest(BaseModel):
    argv: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=120, ge=5, le=600)


class CffexMemberRankRefreshRequest(BaseModel):
    trade_date: str | None = None
    contracts: list[str] = Field(default_factory=lambda: list(DEFAULT_CFFEX_CONTRACTS))
    sources: list[str] = Field(default_factory=lambda: ["choice", "tushare"])


@router.get("/scripts")
def macro_toolkit_scripts() -> dict[str, object]:
    settings = get_settings()
    scripts = [_script_payload(script) for script in iter_toolkit_scripts()]
    source_checks = _source_checks(settings.duckdb_path)
    cffex_status = _cffex_member_rank_status(
        settings.duckdb_path,
        reference_date=_latest_source_check_date(source_checks),
    )
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
            "source_checks": source_checks,
            "capabilities": _capability_plan(settings.duckdb_path),
            "cffex_member_rank": cffex_status,
            "warnings": _script_warnings(cffex_status),
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
            "capabilities": _capability_plan(settings.duckdb_path),
            "cffex_member_rank": _cffex_member_rank_status(
                settings.duckdb_path,
                reference_date=_latest_indicator_date(indicators),
            ),
            "warnings": _analysis_warnings(coverage),
        },
    )


@router.post("/cffex-member-rank/refresh")
def macro_toolkit_refresh_cffex_member_rank(
    request: CffexMemberRankRefreshRequest | None = None,
) -> dict[str, object]:
    refresh_request = request or CffexMemberRankRefreshRequest()
    settings = get_settings()
    result = materialize_cffex_member_rank(
        duckdb_path=settings.duckdb_path,
        trade_date=refresh_request.trade_date,
        contracts=tuple(refresh_request.contracts or DEFAULT_CFFEX_CONTRACTS),
        sources=tuple(refresh_request.sources or ["choice", "tushare"]),
    )
    return _envelope(
        "macro_toolkit.cffex_member_rank_refresh",
        {
            "refresh": result,
            "cffex_member_rank": _cffex_member_rank_status(settings.duckdb_path),
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
    except OSError as exc:
        stdout_text, stderr_text, exit_code = _run_toolkit_script_inline(script.name, run_request.argv)
        return {
            "status": "completed" if exit_code == 0 else "failed",
            "script": _script_payload(script),
            "exit_code": exit_code,
            "stdout": _tail_text(stdout_text),
            "stderr": _tail_text(f"{stderr_text}\nsubprocess fallback: {exc}".strip()),
            "output_files": _output_files(),
        }
    stdout_text = completed.stdout
    stderr_text = completed.stderr

    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "script": _script_payload(script),
        "exit_code": completed.returncode,
        "stdout": _tail_text(stdout_text),
        "stderr": _tail_text(stderr_text),
        "output_files": _output_files(),
    }


def _run_toolkit_script_inline(name: str, argv: list[str]) -> tuple[str, str, int]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            run_toolkit_script(name, argv)
    except Exception as exc:  # pragma: no cover - returned to UI as script stderr
        stderr.write(f"\ninline runner failed: {exc}")
        return stdout.getvalue(), stderr.getvalue(), 1
    return stdout.getvalue(), stderr.getvalue(), 0


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
    return [_source_check(alias, duckdb_path) for alias in _SOURCE_CHECK_ALIASES]


def _source_check(alias: str, duckdb_path: str | Path) -> dict[str, object]:
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
    return {"alias": alias, "row_count": int(len(frame)), "latest": latest}


def _latest_source_check_date(checks: list[dict[str, object]]) -> str | None:
    dates = [
        str(latest["date"])
        for check in checks
        if isinstance((latest := check.get("latest")), dict) and latest.get("date")
    ]
    return max(dates) if dates else None


def _cffex_member_rank_status(
    duckdb_path: str | Path,
    *,
    reference_date: str | None = None,
) -> dict[str, object]:
    stats = table_stats(duckdb_path)
    latest_trade_date = str(stats.get("latest_trade_date") or "")[:10] or None
    return {
        **stats,
        **_cffex_freshness(latest_trade_date, reference_date),
    }


def _cffex_freshness(latest_trade_date: str | None, reference_date: str | None) -> dict[str, object]:
    if not latest_trade_date:
        return {
            "freshness_status": "missing",
            "reference_date": reference_date,
            "stale_days": None,
        }
    if not reference_date:
        return {
            "freshness_status": "unknown",
            "reference_date": None,
            "stale_days": None,
        }
    try:
        latest = date.fromisoformat(latest_trade_date[:10])
        reference = date.fromisoformat(reference_date[:10])
    except ValueError:
        return {
            "freshness_status": "unknown",
            "reference_date": reference_date,
            "stale_days": None,
        }
    stale_days = (reference - latest).days
    if stale_days <= 1:
        status = "current"
    elif stale_days <= 7:
        status = "lagging"
    else:
        status = "stale"
    return {
        "freshness_status": status,
        "reference_date": reference.isoformat(),
        "stale_days": stale_days,
    }


def _script_warnings(cffex_status: dict[str, object]) -> list[str]:
    if cffex_status.get("freshness_status") == "stale":
        latest = cffex_status.get("latest_trade_date") or "缺失"
        reference = cffex_status.get("reference_date") or "当前分析日"
        stale_days = cffex_status.get("stale_days")
        return [
            f"中金所席位排名已落库但最新交易日 {latest}，落后宏观分析日 {reference} {stale_days} 天；"
            "可使用刷新席位补齐 Choice/Tushare 数据。"
        ]
    if int(cffex_status.get("row_count") or 0) > 0:
        return []
    if cffex_status.get("materialized") is True:
        return ["中金所席位排名表已创建但暂无数据；运行 CFFEX refresh 后可用 Choice/Tushare 补齐。"]
    return ["中金所席位排名表尚未初始化；运行 CFFEX refresh 会创建正式表并用 Choice/Tushare 补齐。"]


def _capability_plan(duckdb_path: str | Path) -> list[dict[str, object]]:
    return [_capability_payload(item, duckdb_path) for item in _CAPABILITY_DEFINITIONS]


def _capability_payload(definition: dict[str, object], duckdb_path: str | Path) -> dict[str, object]:
    aliases = tuple(str(alias) for alias in definition["data_aliases"])
    checks = [_source_check(alias, duckdb_path) for alias in aliases]
    hit_count = sum(1 for check in checks if check["latest"])
    required_count = len(checks)
    if required_count == 0:
        data_status = "not_required"
    elif hit_count == required_count:
        data_status = "ready"
    elif hit_count > 0:
        data_status = "partial"
    else:
        data_status = "missing"
    return {
        "key": definition["key"],
        "legacy_module": definition["legacy_module"],
        "label": definition["label"],
        "group": definition["group"],
        "implementation_status": definition["implementation_status"],
        "route_status": definition["route_status"],
        "frontend_status": definition["frontend_status"],
        "data_status": data_status,
        "data_hit_count": hit_count,
        "data_required_count": required_count,
        "evidence": [
            {
                "alias": check["alias"],
                "row_count": check["row_count"],
                "latest_date": check["latest"]["date"] if check["latest"] else None,
                "series_id": check["latest"]["series_id"] if check["latest"] else None,
            }
            for check in checks
        ],
        "next_step": definition["next_step"],
    }


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
    if float(coverage["hit_rate"]) < 0.6:
        return ["核心宏观指标命中不足，当前结论只展示可用证据，不形成完整方向判断。"]
    return []


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
                "fact_cffex_member_rank_daily",
                "vw_cffex_member_rank_daily",
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
