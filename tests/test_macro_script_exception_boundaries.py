"""Isolated failure contracts for the delegated macro/script BLE001 boundaries.

Only selected source functions are loaded. System sources, model fits and task
writes are replaced, so these tests do not collect or materialize business data.
"""
from __future__ import annotations

import ast
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import duckdb
import numpy as np
import pandas as pd
import pytest

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_macro_toolkit]

ROOT = Path(__file__).resolve().parents[1]
TOOLKIT_SCRIPTS = "backend/app/core_finance/macro/toolkit/scripts/"


def _function(path, name, **namespace):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
    namespace = {"pd": pd, "np": np, "duckdb": duckdb, "Path": Path, **namespace}
    exec(compile(ast.Module(body=[node], type_ignores=[]), path, "exec"), namespace)
    return namespace[name]


def _raise(error):
    raise error


@pytest.mark.parametrize("error", [OSError("unreadable"), UnicodeError("bad encoding"), pd.errors.ParserError("bad csv")])
def test_risk_csv_known_read_failure_is_a_monitor_gap(tmp_path, monkeypatch, capsys, error):
    path = tmp_path / "garch_results.csv"
    path.touch()
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: _raise(error))
    load = _function(TOOLKIT_SCRIPTS + "risk_monitor.py", "_load_output_csv")
    assert load(path.name, tmp_path) is None
    assert "[WARN]" in capsys.readouterr().out


def test_risk_csv_unknown_failure_is_not_a_monitor_gap(tmp_path, monkeypatch):
    path = tmp_path / "garch_results.csv"
    path.touch()
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: _raise(RuntimeError("reader defect")))
    load = _function(TOOLKIT_SCRIPTS + "risk_monitor.py", "_load_output_csv")
    with pytest.raises(RuntimeError, match="reader defect"):
        load(path.name, tmp_path)


@pytest.mark.parametrize("error", [OSError("unreadable"), pd.errors.ParserError("bad csv"), ValueError("bad weight"), TypeError("duplicate weight")])
def test_weight_known_failure_is_explicit_equal_weight(tmp_path, monkeypatch, capsys, error):
    path = tmp_path / "risk_parity_results.csv"
    path.touch()
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: _raise(error))
    load = _function(TOOLKIT_SCRIPTS + "performance_metrics_cn.py", "load_risk_parity_weights", os=SimpleNamespace(path=SimpleNamespace(exists=lambda path: True)))
    expected = np.array([0.5, 0.5])
    actual, label = load(path, ["a", "b"], expected)
    np.testing.assert_equal(actual, expected)
    assert label == "风险平价(等权替代)"
    assert "警告" in capsys.readouterr().out


def test_weight_unknown_failure_is_not_equal_weight(tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: _raise(RuntimeError("reader defect")))
    load = _function(TOOLKIT_SCRIPTS + "performance_metrics_cn.py", "load_risk_parity_weights", os=SimpleNamespace(path=SimpleNamespace(exists=lambda path: True)))
    with pytest.raises(RuntimeError, match="reader defect"):
        load(tmp_path / "weights.csv", ["a", "b"], np.array([0.5, 0.5]))


@pytest.mark.parametrize("frame", [
    pd.DataFrame({"资产": ["a", "b"], "风险平价权重%": ["not-numeric", 50]}),
    pd.DataFrame({"资产": ["a", "a", "b"], "风险平价权重%": [20, 30, 50]}),
])
def test_invalid_weight_cells_do_not_become_a_normal_risk_parity_result(monkeypatch, capsys, frame):
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: frame)
    load = _function(TOOLKIT_SCRIPTS + "performance_metrics_cn.py", "load_risk_parity_weights", os=SimpleNamespace(path=SimpleNamespace(exists=lambda path: True)))
    weights, label = load("synthetic.csv", ["a", "b"], np.array([0.5, 0.5]))
    np.testing.assert_equal(weights, np.array([0.5, 0.5]))
    assert label == "风险平价(等权替代)"
    assert "警告" in capsys.readouterr().out


def _garch_function(name, build):
    return _function(
        TOOLKIT_SCRIPTS + "garch_multi_asset.py", name,
        MODELS={"GARCH": {"vol": "Garch", "p": 1, "o": 0, "q": 1}},
        DISTS=["normal"], _build_arch_model=build,
        compute_persistence=lambda *args: 0.9, check_constraints=lambda *args: "通过",
    )


@pytest.mark.parametrize("error", [ValueError("invalid sample"), np.linalg.LinAlgError("singular sample")])
def test_garch_known_fit_failure_is_reported(capsys, error):
    fit = _garch_function("fit_single_asset", lambda *args: _raise(error))
    assert fit(pd.Series([0.1, -0.2, 0.3]), "synthetic") is None
    output = capsys.readouterr().out
    assert "GARCH / normal" in output
    assert str(error) in output
    assert "所有模型拟合失败" in output


def test_garch_unknown_fit_failure_is_not_an_excluded_model():
    fit = _garch_function("fit_single_asset", lambda *args: _raise(RuntimeError("model defect")))
    with pytest.raises(RuntimeError, match="model defect"):
        fit(pd.Series([0.1, -0.2, 0.3]), "synthetic")


def test_garch_failed_refit_reports_cached_parameter_use(capsys):
    fits = 0

    class FakeModel:
        def fit(self, **kwargs):
            nonlocal fits
            fits += 1
            if fits > 1:
                raise ValueError("refit sample rejected")
            return SimpleNamespace(params={"cached": 1})

        def fix(self, params):
            assert params == {"cached": 1}
            return SimpleNamespace(forecast=lambda **kwargs: SimpleNamespace(variance=SimpleNamespace(values=np.array([[0.2]]))))

    evaluate = _garch_function("out_of_sample_test", lambda *args: FakeModel())
    evaluate(pd.Series(np.linspace(-1, 1, 80)), {"model": "GARCH", "dist": "normal"}, "synthetic", train_ratio=0.5)
    output = capsys.readouterr().out
    assert "refit sample rejected" in output
    assert "cached_params" in output


def test_garch_unknown_refit_failure_is_not_a_missing_forecast():
    evaluate = _garch_function("out_of_sample_test", lambda *args: _raise(RuntimeError("refit defect")))
    with pytest.raises(RuntimeError, match="refit defect"):
        evaluate(pd.Series(np.linspace(-1, 1, 80)), {"model": "GARCH", "dist": "normal"}, "synthetic")


def _backtest_load(monkeypatch, wind_error=None, backup_error=None):
    dates = pd.bdate_range("2024-01-02", periods=5)
    frame = pd.DataFrame({"date": dates, "close": np.arange(100.0, 105.0), "日期": dates, "收盘价": np.arange(100.0, 105.0)})
    wind = ModuleType("WindPy")
    wind.w = SimpleNamespace(start=lambda **kwargs: _raise(wind_error) if wind_error is not None else SimpleNamespace(ErrorCode=1))
    monkeypatch.setitem(sys.modules, "WindPy", wind)
    ak = SimpleNamespace(
        stock_zh_index_daily=lambda **kwargs: frame.copy(), futures_main_sina=lambda **kwargs: frame.copy(),
        fund_etf_hist_em=lambda **kwargs: _raise(backup_error) if backup_error is not None else pd.DataFrame(columns=["日期", "收盘"]),
    )
    return _function(TOOLKIT_SCRIPTS + "backtest_cn.py", "load_prices", ak=ak, datetime=datetime, sys=sys, __package__="")


@pytest.mark.parametrize("boundary", ["wind", "backup"])
def test_backtest_known_source_failure_keeps_explicit_reduced_asset_pool(monkeypatch, capsys, boundary):
    load = _backtest_load(monkeypatch, **{boundary + "_error": OSError("source unavailable")})
    prices = load()
    assert list(prices.columns) == ["hs300", "csi500", "gold", "copper", "crude_oil"]
    assert prices.notna().all().all()
    assert "警告" in capsys.readouterr().out


@pytest.mark.parametrize("boundary", ["wind", "backup"])
def test_backtest_unknown_source_failure_does_not_exclude_assets(monkeypatch, boundary):
    load = _backtest_load(monkeypatch, **{boundary + "_error": RuntimeError("source defect")})
    with pytest.raises(RuntimeError, match="source defect"):
        load()


@pytest.mark.parametrize("script", ["diagnose_adb_coverage", "diagnose_balance_diff"])
def test_archived_diagnostic_settings_failure_does_not_select_another_database(monkeypatch, script):
    settings = ModuleType("backend.app.governance.settings")
    settings.get_settings = lambda: _raise(ValueError("invalid settings"))
    monkeypatch.setitem(sys.modules, settings.__name__, settings)
    resolve = _function("backend/scripts/archive/adb-recon-2026-05/" + script + ".py", "_resolve_duckdb_path", __file__=str(ROOT / "backend/scripts/archive/adb-recon-2026-05" / (script + ".py")))
    with pytest.raises(ValueError, match="invalid settings"):
        resolve()


@pytest.mark.parametrize("error", [ImportError("dependency unavailable"), RuntimeError("startup defect")])
def test_credit_startup_only_dependency_failure_is_empty_output(monkeypatch, capsys, error):
    path = TOOLKIT_SCRIPTS + "credit_bond_data.py"
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    startup = next(item for item in tree.body if isinstance(item, ast.Try))
    wind = ModuleType("WindPy")
    wind.w = SimpleNamespace(start=lambda: _raise(error))
    monkeypatch.setitem(sys.modules, "WindPy", wind)
    namespace = {"__package__": ""}
    code = compile(ast.Module(body=[startup], type_ignores=[]), path, "exec")
    if isinstance(error, ImportError):
        exec(code, namespace)
        assert namespace["WIND_AVAILABLE"] is False
        assert "output will be empty" in capsys.readouterr().out
    else:
        with pytest.raises(RuntimeError, match="startup defect"):
            exec(code, namespace)


def test_crisis_batch_unknown_failure_is_an_error_receipt(tmp_path):
    spec = SimpleNamespace(alias="synthetic")
    backfill = _function(
        "backend/scripts/backfill_crisis_score_inputs.py", "backfill_crisis_score_inputs",
        DEFAULT_START_DATE="2024-01-01", UTC=UTC, date=date, datetime=datetime,
        get_settings=lambda: SimpleNamespace(duckdb_path=tmp_path / "synthetic.duckdb"),
        _validate_iso_date=lambda *args, **kwargs: None,
        _select_specs=lambda *args: [spec], _backfill_input=lambda *args, **kwargs: _raise(TypeError("task defect")),
        _coverage_snapshot=lambda *args: [],
    )
    result = backfill(duckdb_path=str(tmp_path / "synthetic.duckdb"), end_date="2024-01-02")
    assert result["results"] == {"synthetic": {"status": "error", "error": "task defect"}}
    assert result["errors"] == {"synthetic": "task defect"}
    assert not (tmp_path / "synthetic.duckdb").exists()
