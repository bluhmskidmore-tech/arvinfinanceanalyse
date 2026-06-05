from __future__ import annotations

import runpy
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .system_sources import DEFAULT_DATA_SOURCES

TOOLKIT_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = TOOLKIT_ROOT / "scripts"


def _find_project_root() -> Path:
    for parent in TOOLKIT_ROOT.parents:
        if (parent / "backend").is_dir() and (parent / "frontend").is_dir():
            return parent
    return TOOLKIT_ROOT.parents[4]


PROJECT_ROOT = _find_project_root()


@dataclass(frozen=True, slots=True)
class MacroToolkitScript:
    name: str
    filename: str
    group: str
    default_data_sources: tuple[str, ...] = DEFAULT_DATA_SOURCES
    optional_dependencies: tuple[str, ...] = ()
    notes: str = ""

    @property
    def path(self) -> Path:
        return SCRIPTS_DIR / self.filename


@dataclass(frozen=True, slots=True)
class MacroToolkitRunResult:
    name: str
    path: Path
    globals: dict[str, Any]


_SCRIPT_REGISTRY: tuple[MacroToolkitScript, ...] = (
    MacroToolkitScript(
        "alphaear_news_fetch",
        "alphaear_news_fetch.py",
        "news",
        optional_dependencies=("openclaw alphaear-news", "pandas"),
        notes="Requires the external alphaear-news skill modules expected by the source script.",
    ),
    MacroToolkitScript(
        "backtest_cn",
        "backtest_cn.py",
        "allocation",
        optional_dependencies=("matplotlib", "scipy"),
    ),
    MacroToolkitScript(
        "equity_strategies",
        "equity_strategies.py",
        "allocation",
        optional_dependencies=("numpy", "pandas"),
    ),
    MacroToolkitScript("bond_futures_data", "bond_futures_data.py", "rates", optional_dependencies=("pandas",)),
    MacroToolkitScript("bond_futures_signals", "bond_futures_signals.py", "rates", optional_dependencies=("pandas",)),
    MacroToolkitScript(
        "credit_bond_dashboard",
        "credit_bond_dashboard.py",
        "credit",
        optional_dependencies=("matplotlib", "pandas"),
    ),
    MacroToolkitScript("credit_bond_data", "credit_bond_data.py", "credit", optional_dependencies=("pandas",)),
    MacroToolkitScript("credit_bond_monitor", "credit_bond_monitor.py", "credit", optional_dependencies=("pandas",)),
    MacroToolkitScript("credit_bond_signals", "credit_bond_signals.py", "credit", optional_dependencies=("pandas",)),
    MacroToolkitScript("crisis_score_cn", "crisis_score_cn.py", "macro_signal", optional_dependencies=("pandas",)),
    MacroToolkitScript("crowding_cn", "crowding_cn.py", "rates", optional_dependencies=("pandas",)),
    MacroToolkitScript("cta_trend_cn", "cta_trend_cn.py", "allocation", optional_dependencies=("matplotlib",)),
    MacroToolkitScript("dcc_garch_cn", "dcc_garch_cn.py", "risk", optional_dependencies=("matplotlib", "pandas")),
    MacroToolkitScript("debug_wind", "debug_wind.py", "diagnostic"),
    MacroToolkitScript(
        "evening_report",
        "evening_report.py",
        "report",
        optional_dependencies=("openclaw alphaear-news", "pandas"),
        notes="Requires the external alphaear-news skill modules expected by the source script.",
    ),
    MacroToolkitScript("garch_multi_asset", "garch_multi_asset.py", "risk", optional_dependencies=("pandas",)),
    MacroToolkitScript(
        "generate_bond_macro_report",
        "generate_bond_macro_report.py",
        "report",
        optional_dependencies=("python-docx", "matplotlib"),
    ),
    MacroToolkitScript("merrill_clock_cn", "merrill_clock_cn.py", "macro_signal", optional_dependencies=("pandas",)),
    MacroToolkitScript("performance_metrics_cn", "performance_metrics_cn.py", "allocation", optional_dependencies=("matplotlib",)),
    MacroToolkitScript(
        "read_data",
        "read_data.py",
        "diagnostic",
        optional_dependencies=("pandas",),
        notes="Prints existing toolkit CSV outputs; it does not use a main guard in the source script.",
    ),
    MacroToolkitScript("rebalance_cn", "rebalance_cn.py", "allocation", optional_dependencies=("matplotlib",)),
    MacroToolkitScript("regime_switch_cn", "regime_switch_cn.py", "market_regime", optional_dependencies=("matplotlib",)),
    MacroToolkitScript("risk_monitor", "risk_monitor.py", "risk", optional_dependencies=("pandas",)),
    MacroToolkitScript("risk_parity_cn", "risk_parity_cn.py", "allocation", optional_dependencies=("matplotlib", "scipy")),
    MacroToolkitScript("signal_aggregator", "signal_aggregator.py", "macro_signal", optional_dependencies=("pandas",)),
)

OMITTED_SOURCE_SCRIPTS: dict[str, str] = {
    "credit_bond_portfolio.py": "Source file has a syntax error in the provided toolkit copy.",
    "_gen_dcc.py": "Source helper used to generate scripts, not an executable macro workflow.",
    "_part1.py": "Source fragment, not an executable macro workflow.",
    "_test.py": "Source scratch file, not an executable macro workflow.",
    "_writer.py": "Source helper used to generate scripts, not an executable macro workflow.",
    "_write_cta.py": "Source helper used to generate scripts, not an executable macro workflow.",
}


def iter_toolkit_scripts(group: str | None = None) -> tuple[MacroToolkitScript, ...]:
    if group is None:
        return _SCRIPT_REGISTRY
    return tuple(script for script in _SCRIPT_REGISTRY if script.group == group)


def get_toolkit_script(name: str) -> MacroToolkitScript:
    normalized = name.removesuffix(".py").replace("-", "_")
    for script in _SCRIPT_REGISTRY:
        if script.name == normalized or script.filename.removesuffix(".py") == normalized:
            return script
    raise KeyError(f"Unknown macro toolkit script: {name}")


def run_toolkit_script(name: str, argv: Sequence[str] | None = None) -> MacroToolkitRunResult:
    script = get_toolkit_script(name)
    if not script.path.exists():
        raise FileNotFoundError(script.path)

    old_argv = sys.argv[:]
    old_path = sys.path[:]
    try:
        sys.argv = [str(script.path), *(argv or ())]
        for path in (str(TOOLKIT_ROOT), str(PROJECT_ROOT)):
            if path not in sys.path:
                sys.path.insert(0, path)
        result_globals = runpy.run_path(str(script.path), run_name="__main__")
    finally:
        sys.argv = old_argv
        sys.path = old_path

    return MacroToolkitRunResult(name=script.name, path=script.path, globals=result_globals)
