"""Synthetic dashboard disclosure contracts with no providers, storage or renderer."""

from __future__ import annotations

import importlib.util
from importlib.machinery import ModuleSpec
from pathlib import Path
import runpy
import socket
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock
import warnings

import duckdb
import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "backend/app/core_finance/macro/toolkit/scripts/credit_bond_dashboard.py"
pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_macro_toolkit]


@pytest.fixture(autouse=True)
def deny_external_io(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Dashboard disclosure tests must not access networks or databases")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket.socket, "sendto", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(duckdb, "connect", denied)


@pytest.fixture()
def dashboard(tmp_path, monkeypatch):
    # Load the actual script with synthetic paths, then record every render call.
    # Do not initialize the real renderer or its font/output caches.
    monkeypatch.setattr(sys, "path", sys.path[:])
    monkeypatch.setitem(sys.modules, "paths", SimpleNamespace(ASSET_DIR=tmp_path))
    original_find_spec = importlib.util.find_spec

    def without_renderer(name, *args, **kwargs):
        return None if name == "matplotlib" else original_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", without_renderer)
    with warnings.catch_warnings():
        namespace = runpy.run_path(str(DASHBOARD), run_name="structural_dashboard_probe")
    globals_ = namespace["generate_dashboard"].__globals__
    axes = [MagicMock(name=f"axis_{index}") for index in range(9)]
    figure = MagicMock(name="figure")
    figure.add_subplot.side_effect = axes
    pyplot = MagicMock(name="pyplot")
    pyplot.rcParams = {}
    pyplot.figure.return_value = figure
    monkeypatch.setitem(globals_, "plt", pyplot)
    monkeypatch.setitem(globals_, "gridspec", MagicMock(name="gridspec"))
    monkeypatch.setitem(globals_, "mpatches", MagicMock(name="mpatches"))
    return SimpleNamespace(namespace=namespace, globals=globals_, axes=axes, figure=figure, plt=pyplot)


class TestSyntheticDashboardDisclosure:
    def test_every_chart_kpi_and_saved_output_has_visible_demo_label(self, dashboard):
        path = dashboard.namespace["generate_dashboard"]()
        title = dashboard.figure.suptitle.call_args.args[0]
        assert "DEMO / SYNTHETIC" in title
        for axis in dashboard.axes[:4]:
            text = " ".join(str(call.args[2]) for call in axis.text.call_args_list)
            assert "DEMO / SYNTHETIC" in text
        for axis in dashboard.axes[4:]:
            assert "DEMO / SYNTHETIC" in axis.set_title.call_args.args[0]
        footer = " ".join(str(call.args[2]) for call in dashboard.figure.text.call_args_list)
        assert "live observations unavailable" in footer.lower()
        assert "Choice" not in footer and "Tushare" not in footer and "Updated" not in footer
        assert "credit_dashboard_demo_" in path.name
        dashboard.plt.savefig.assert_called_once()
        assert dashboard.plt.savefig.call_args.args[0] == path
        assert not path.exists(), "Recording renderer must not create a fake PNG"

    @pytest.mark.parametrize("draw_name", ["draw_spread_chart", "draw_fi_plus_chart"])
    def test_synthetic_series_do_not_move_with_wall_clock(self, dashboard, monkeypatch, draw_name):
        from datetime import datetime

        xs = []
        for year in (2026, 2036):
            monkeypatch.setitem(dashboard.globals, "datetime", SimpleNamespace(today=lambda: datetime(year, 1, 1)))
            axis = MagicMock()
            dashboard.namespace[draw_name](axis)
            xs.append(np.asarray(axis.plot.call_args.args[0]))
            assert "Synthetic observation" in axis.set_xlabel.call_args.args[0]
        np.testing.assert_array_equal(xs[0], xs[1])
        np.testing.assert_array_equal(xs[0], np.arange(1, len(xs[0]) + 1))

    def test_production_mode_is_unavailable_before_any_plot_or_write(self, dashboard):
        with pytest.raises(RuntimeError, match="unavailable.*validated source inputs"):
            dashboard.namespace["generate_dashboard"](data_mode="production")
        dashboard.plt.figure.assert_not_called()
        dashboard.plt.savefig.assert_not_called()

    def test_unknown_mode_never_falls_back_to_synthetic(self, dashboard):
        with pytest.raises(ValueError, match="data_mode"):
            dashboard.namespace["generate_dashboard"](data_mode="prodction")
        dashboard.plt.figure.assert_not_called()

    def test_missing_renderer_remains_explicitly_unavailable(self, dashboard, monkeypatch):
        monkeypatch.setitem(dashboard.globals, "plt", None)
        with pytest.raises(RuntimeError, match="matplotlib is required"):
            dashboard.namespace["generate_dashboard"]()

    def test_cli_production_mode_fails_without_writing_artifacts(self, dashboard, monkeypatch, tmp_path):
        # Execute the real CLI entry point in this process with a recording renderer.
        # The original CLI ignores the flag and renders; no actual artifact is written.
        matplotlib = ModuleType("matplotlib")
        matplotlib.__spec__ = ModuleSpec("matplotlib", loader=None, is_package=True)
        matplotlib.__path__ = []
        matplotlib.use = MagicMock()
        matplotlib.gridspec = dashboard.globals["gridspec"]
        matplotlib.patches = dashboard.globals["mpatches"]
        matplotlib.pyplot = dashboard.plt
        for name, module in (
            ("matplotlib", matplotlib),
            ("matplotlib.gridspec", matplotlib.gridspec),
            ("matplotlib.patches", matplotlib.patches),
            ("matplotlib.pyplot", matplotlib.pyplot),
        ):
            monkeypatch.setitem(sys.modules, name, module)
        original_find_spec = importlib.util.find_spec

        def recording_renderer(name, *args, **kwargs):
            return matplotlib.__spec__ if name == "matplotlib" else original_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", recording_renderer)
        monkeypatch.setattr(sys, "argv", [str(DASHBOARD), "--data-mode", "production"])
        with warnings.catch_warnings(), pytest.raises(RuntimeError, match="unavailable.*validated source inputs"):
            runpy.run_path(str(DASHBOARD), run_name="__main__")
        dashboard.plt.figure.assert_not_called()
        dashboard.plt.savefig.assert_not_called()
        assert not list(tmp_path.rglob("*.png"))
