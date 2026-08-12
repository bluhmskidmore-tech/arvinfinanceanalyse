from __future__ import annotations

import hashlib
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.helpers import load_module


def _load_runner_module():
    return load_module(
        "backend.app.tasks.choice_stock_materialize_run",
        "backend/app/tasks/choice_stock_materialize_run.py",
    )


def test_choice_stock_materialize_run_main_forwards_args_and_emits_json(monkeypatch, capsys) -> None:
    module = _load_runner_module()
    calls: list[dict[str, object]] = []

    def fake_materialize_choice_stock_inputs(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "completed",
            "as_of_date": "2026-04-28",
            "row_count": 7,
        }

    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fake_materialize_choice_stock_inputs)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "choice_stock_materialize_run.py",
            "--as-of-date",
            "2026-04-28",
            "--duckdb-path",
            "tmp/moss.duckdb",
            "--catalog-path",
            "tmp/choice_stock_catalog.json",
        ],
    )

    module.main()

    captured = capsys.readouterr()
    assert calls == [
        {
            "as_of_date": "2026-04-28",
            "duckdb_path": "tmp/moss.duckdb",
            "catalog_path": "tmp/choice_stock_catalog.json",
            "enable_tushare_concept_fallback": False,
        }
    ]
    assert json.loads(captured.out) == {
        "status": "completed",
        "as_of_date": "2026-04-28",
        "row_count": 7,
        "theme_overlay": {
            "mode": "off",
            "status": "off",
            "observation_status": "not_checked",
            "observation_manifest_written": False,
            "overlay_status": "not_run",
        },
    }
    assert captured.err == ""


def test_choice_stock_materialize_run_main_forwards_none_for_omitted_paths(monkeypatch, capsys) -> None:
    module = _load_runner_module()
    calls: list[dict[str, object]] = []

    def fake_materialize_choice_stock_inputs(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {"status": "completed"}

    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fake_materialize_choice_stock_inputs)
    monkeypatch.setattr(
        sys,
        "argv",
        ["choice_stock_materialize_run.py", "--as-of-date", "2026-04-28"],
    )

    module.main()

    captured = capsys.readouterr()
    assert calls == [
        {
            "as_of_date": "2026-04-28",
            "duckdb_path": None,
            "catalog_path": None,
            "enable_tushare_concept_fallback": False,
        }
    ]
    assert json.loads(captured.out) == {
        "status": "completed",
        "theme_overlay": {
            "mode": "off",
            "status": "off",
            "observation_status": "not_checked",
            "observation_manifest_written": False,
            "overlay_status": "not_run",
        },
    }
    assert captured.err == ""


def test_choice_stock_materialize_run_main_can_emit_post_run_coverage(monkeypatch, capsys) -> None:
    module = _load_runner_module()
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_materialize_choice_stock_inputs(**kwargs: object) -> dict[str, object]:
        calls.append(("materialize", dict(kwargs)))
        return {
            "status": "completed",
            "as_of_date": "2026-04-28",
            "row_count": 42,
        }

    def fake_load_choice_stock_materialization_coverage(**kwargs: object) -> object:
        calls.append(("coverage", dict(kwargs)))
        return SimpleNamespace(
            as_of_date="2026-04-28",
            full_coverage=True,
            status="ready",
            completed_request_items=["stock_universe:a_share_universe_sector_001004"],
            missing_request_items=[],
            message="Choice stock inputs are materialized for 2026-04-28.",
        )

    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fake_materialize_choice_stock_inputs)
    monkeypatch.setattr(
        module,
        "load_choice_stock_materialization_coverage",
        fake_load_choice_stock_materialization_coverage,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "choice_stock_materialize_run.py",
            "--as-of-date",
            "2026-04-28",
            "--duckdb-path",
            "tmp/moss.duckdb",
            "--catalog-path",
            "tmp/choice_stock_catalog.json",
            "--verify-coverage",
        ],
    )

    module.main()

    captured = capsys.readouterr()
    assert calls == [
        (
            "materialize",
            {
                "as_of_date": "2026-04-28",
                "duckdb_path": "tmp/moss.duckdb",
                "catalog_path": "tmp/choice_stock_catalog.json",
                "enable_tushare_concept_fallback": False,
            },
        ),
        (
            "coverage",
            {
                "duckdb_path": "tmp/moss.duckdb",
                "as_of_date": "2026-04-28",
            },
        ),
    ]
    assert json.loads(captured.out) == {
        "status": "completed",
        "as_of_date": "2026-04-28",
        "row_count": 42,
        "coverage": {
            "as_of_date": "2026-04-28",
            "full_coverage": True,
            "status": "ready",
            "completed_request_items": ["stock_universe:a_share_universe_sector_001004"],
            "missing_request_items": [],
            "message": "Choice stock inputs are materialized for 2026-04-28.",
        },
        "theme_overlay": {
            "mode": "off",
            "status": "off",
            "observation_status": "not_checked",
            "observation_manifest_written": False,
            "overlay_status": "not_run",
        },
    }
    assert captured.err == ""


def test_choice_stock_materialize_run_main_archives_theme_overlay_with_deterministic_lineage(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = _load_runner_module()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    parent_run_id = "choice_stock_materialize:2026-04-28:fixture"
    materialize_calls: list[dict[str, object]] = []
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        module,
        "materialize_choice_stock_inputs",
        lambda **kwargs: materialize_calls.append(dict(kwargs))
        or {
            "status": "completed",
            "run_id": parent_run_id,
            "as_of_date": "2026-04-28",
            "row_count": 7,
        },
    )
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(
            duckdb_path=duckdb_path,
            governance_path=governance_path,
            local_archive_path=archive_root,
        ),
    )
    monkeypatch.setattr(
        module,
        "refresh_choice_stock_theme_overlay",
        lambda **kwargs: (
            calls.append(dict(kwargs))
            or {
                "mode": "archive",
                "status": "completed",
                "overlay_status": "completed",
                "member_count": 9,
                "run_id": kwargs["run_id"],
            }
        ),
        raising=False,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "choice_stock_materialize_run.py",
            "--as-of-date",
            "2026-04-28",
            "--duckdb-path",
            str(duckdb_path),
            "--theme-overlay-mode",
            "archive",
        ],
    )

    module.main()

    expected_digest = hashlib.sha256(f"{parent_run_id}|2026-04-28".encode()).hexdigest()[:16]
    assert materialize_calls[0]["enable_tushare_concept_fallback"] is False
    assert calls == [
        {
            "mode": "archive",
            "duckdb_path": str(duckdb_path),
            "governance_dir": str(governance_path),
            "archive_root": str(archive_root),
            "expected_report_date": "2026-04-28",
            "run_id": f"{parent_run_id}:theme-overlay",
            "source_version": f"sv_choice_stock_theme_overlay_{expected_digest}",
            "vendor_version": "vv_tushare_ths_current_overlay_v1",
        }
    ]
    output = json.loads(capsys.readouterr().out)
    assert output["theme_overlay"] == {
        "mode": "archive",
        "status": "completed",
        "overlay_status": "completed",
        "member_count": 9,
        "run_id": f"{parent_run_id}:theme-overlay",
    }


def test_choice_stock_materialize_run_main_emits_structured_theme_overlay_failure(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = _load_runner_module()
    parent_run_id = "choice_stock_materialize:2026-04-28:failure-fixture"
    monkeypatch.setattr(
        module,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: {
            "status": "completed",
            "run_id": parent_run_id,
            "as_of_date": "2026-04-28",
        },
    )
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(
            duckdb_path=tmp_path / "moss.duckdb",
            governance_path=tmp_path / "governance",
            local_archive_path=tmp_path / "archive",
        ),
    )
    failure = {
        "mode": "archive",
        "status": "source_failed",
        "overlay_status": "source_failed",
        "member_count": 0,
        "message": "Theme source unavailable.",
        "run_id": f"{parent_run_id}:theme-overlay",
    }
    monkeypatch.setattr(
        module,
        "refresh_choice_stock_theme_overlay",
        lambda **_kwargs: dict(failure),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "choice_stock_materialize_run.py",
            "--as-of-date",
            "2026-04-28",
            "--theme-overlay-mode",
            "archive",
        ],
    )

    module.main()

    assert json.loads(capsys.readouterr().out)["theme_overlay"] == failure


def test_choice_stock_materialize_run_main_theme_overlay_only_reuses_committed_lineage(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = _load_runner_module()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    materialization_run_id = "choice_stock_materialize:2026-04-28:committed"
    observation_calls: list[dict[str, object]] = []
    overlay_calls: list[dict[str, object]] = []

    def fail_materialize(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("theme-overlay-only must not re-run Choice materialization")

    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fail_materialize)
    monkeypatch.setattr(module, "materialize_choice_stock_factor_snapshot", fail_materialize, raising=False)
    monkeypatch.setattr(
        module,
        "resolve_latest_committed_choice_stock_observation",
        lambda **kwargs: observation_calls.append(dict(kwargs))
        or SimpleNamespace(
            report_date="2026-04-28",
            materialization_run_id=materialization_run_id,
            daily_observation_row_count=5208,
            stock_code_count=5208,
        ),
    )
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(
            duckdb_path=duckdb_path,
            governance_path=governance_path,
            local_archive_path=archive_root,
        ),
    )
    monkeypatch.setattr(
        module,
        "refresh_choice_stock_theme_overlay",
        lambda **kwargs: (
            overlay_calls.append(dict(kwargs))
            or {
                "mode": "archive",
                "status": "completed",
                "overlay_status": "completed",
                "member_count": 4321,
                "run_id": kwargs["run_id"],
            }
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "choice_stock_materialize_run.py",
            "--as-of-date",
            "2026-04-28",
            "--duckdb-path",
            str(duckdb_path),
            "--theme-overlay-only",
            "--theme-overlay-mode",
            "archive",
        ],
    )

    module.main()

    expected_digest = hashlib.sha256(f"{materialization_run_id}|2026-04-28".encode()).hexdigest()[:16]
    assert observation_calls == [
        {"duckdb_path": str(duckdb_path), "expected_report_date": "2026-04-28"},
    ]
    assert overlay_calls == [
        {
            "mode": "archive",
            "duckdb_path": str(duckdb_path),
            "governance_dir": str(governance_path),
            "archive_root": str(archive_root),
            "expected_report_date": "2026-04-28",
            "run_id": f"{materialization_run_id}:theme-overlay",
            "source_version": f"sv_choice_stock_theme_overlay_{expected_digest}",
            "vendor_version": "vv_tushare_ths_current_overlay_v1",
        }
    ]
    assert json.loads(capsys.readouterr().out) == {
        "status": "theme_overlay_only",
        "as_of_date": "2026-04-28",
        "run_id": materialization_run_id,
        "daily_observation_row_count": 5208,
        "stock_code_count": 5208,
        "theme_overlay": {
            "mode": "archive",
            "status": "completed",
            "overlay_status": "completed",
            "member_count": 4321,
            "run_id": f"{materialization_run_id}:theme-overlay",
        },
    }


def test_choice_stock_materialize_run_main_theme_overlay_only_binds_source_ip(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = _load_runner_module()
    events: list[str] = []

    @contextmanager
    def fake_source_network(source_ip: str):
        events.append(f"enter:{source_ip}")
        try:
            yield
        finally:
            events.append("exit")

    monkeypatch.setattr(module, "_tushare_source_network", fake_source_network)
    monkeypatch.setattr(
        module,
        "resolve_latest_committed_choice_stock_observation",
        lambda **_kwargs: SimpleNamespace(
            report_date="2026-04-28",
            materialization_run_id="choice_stock_materialize:2026-04-28:committed",
            daily_observation_row_count=5208,
            stock_code_count=5208,
        ),
    )
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(
            duckdb_path=tmp_path / "moss.duckdb",
            governance_path=tmp_path / "governance",
            local_archive_path=tmp_path / "archive",
        ),
    )
    monkeypatch.setattr(
        module,
        "refresh_choice_stock_theme_overlay",
        lambda **_kwargs: events.append("overlay") or {"mode": "archive", "status": "completed"},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "choice_stock_materialize_run.py",
            "--as-of-date",
            "2026-04-28",
            "--theme-overlay-only",
            "--theme-overlay-mode",
            "archive",
            "--theme-overlay-source-ip",
            "172.16.115.248",
        ],
    )

    module.main()

    assert events == ["enter:172.16.115.248", "overlay", "exit"]
    assert json.loads(capsys.readouterr().out)["theme_overlay"] == {
        "mode": "archive",
        "status": "completed",
    }


def test_choice_stock_materialize_run_main_source_ip_requires_theme_overlay_only(monkeypatch, capsys) -> None:
    module = _load_runner_module()

    def fail_materialize(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("argument validation must run before materialization")

    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fail_materialize)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "choice_stock_materialize_run.py",
            "--as-of-date",
            "2026-04-28",
            "--theme-overlay-source-ip",
            "172.16.115.248",
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        module.main()

    assert excinfo.value.code == 2
    assert "--theme-overlay-source-ip requires --theme-overlay-only" in capsys.readouterr().err


def test_choice_stock_materialize_run_main_theme_overlay_only_requires_active_mode(monkeypatch, capsys) -> None:
    module = _load_runner_module()

    def fail_materialize(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("theme-overlay-only must not re-run Choice materialization")

    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fail_materialize)
    monkeypatch.setattr(
        sys,
        "argv",
        ["choice_stock_materialize_run.py", "--as-of-date", "2026-04-28", "--theme-overlay-only"],
    )

    with pytest.raises(SystemExit) as excinfo:
        module.main()

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--theme-overlay-only requires --theme-overlay-mode dry_run or archive" in captured.err


def test_choice_stock_materialize_run_main_can_run_factor_snapshot(monkeypatch, capsys) -> None:
    module = _load_runner_module()
    calls: list[dict[str, object]] = []

    def fake_materialize_choice_stock_factor_snapshot(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "completed",
            "as_of_date": "2026-04-28",
            "table": "choice_stock_factor_snapshot",
            "row_count": 123,
        }

    monkeypatch.setattr(
        module,
        "materialize_choice_stock_factor_snapshot",
        fake_materialize_choice_stock_factor_snapshot,
        raising=False,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "choice_stock_materialize_run.py",
            "--as-of-date",
            "2026-04-28",
            "--duckdb-path",
            "tmp/moss.duckdb",
            "--factor-snapshot",
            "--factor-max-stock-count",
            "750",
        ],
    )

    module.main()

    captured = capsys.readouterr()
    assert calls == [
        {
            "as_of_date": "2026-04-28",
            "duckdb_path": "tmp/moss.duckdb",
            "max_stock_count": 750,
        }
    ]
    assert json.loads(captured.out) == {
        "status": "completed",
        "as_of_date": "2026-04-28",
        "table": "choice_stock_factor_snapshot",
        "row_count": 123,
        "theme_overlay": {
            "mode": "off",
            "status": "off",
            "observation_status": "not_checked",
            "observation_manifest_written": False,
            "overlay_status": "not_run",
        },
    }
    assert captured.err == ""


def test_choice_stock_materialize_run_main_propagates_failures_without_json(monkeypatch, capsys) -> None:
    module = _load_runner_module()

    def fake_materialize_choice_stock_inputs(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("choice materialization failed")

    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fake_materialize_choice_stock_inputs)
    monkeypatch.setattr(
        sys,
        "argv",
        ["choice_stock_materialize_run.py", "--as-of-date", "2026-04-28"],
    )

    with pytest.raises(RuntimeError, match="choice materialization failed"):
        module.main()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
