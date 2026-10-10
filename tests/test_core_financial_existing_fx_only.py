from __future__ import annotations

import sys

import pytest

from tests.helpers import load_module


def _load_pipeline_module():
    module = sys.modules.get("backend.app.tasks.formal_balance_pipeline")
    if module is None:
        module = load_module(
            "backend.app.tasks.formal_balance_pipeline",
            "backend/app/tasks/formal_balance_pipeline.py",
        )
    return module


def _patch_minimal_pipeline(pipeline_mod, monkeypatch, balance_calls):
    monkeypatch.setattr(
        pipeline_mod.ingest_demo_manifest,
        "fn",
        lambda **_kwargs: {"status": "completed"},
    )
    monkeypatch.setattr(
        pipeline_mod.materialize_standard_snapshots,
        "fn",
        lambda **_kwargs: {"status": "completed"},
    )

    def _capture_balance(**kwargs):
        balance_calls.append(dict(kwargs))
        return {"status": "completed"}

    monkeypatch.setattr(pipeline_mod.materialize_balance_analysis_facts, "fn", _capture_balance)


@pytest.mark.parametrize(
    ("flag_kwargs", "expected"),
    [
        ({}, False),
        ({"use_existing_fx_only": False}, False),
        ({"use_existing_fx_only": True}, True),
    ],
)
def test_private_pipeline_forwards_existing_fx_choice(
    monkeypatch,
    flag_kwargs,
    expected,
):
    pipeline_mod = _load_pipeline_module()
    balance_calls: list[dict[str, object]] = []
    _patch_minimal_pipeline(pipeline_mod, monkeypatch, balance_calls)

    payload = pipeline_mod._run_formal_balance_pipeline(
        report_date="2026-08-31",
        include_analytics=False,
        **flag_kwargs,
    )

    assert payload["status"] == "completed"
    assert len(balance_calls) == 1
    assert balance_calls[0]["use_existing_fx_only"] is expected


def test_sync_wrapper_preserves_default_omission_and_forwards_true(monkeypatch):
    pipeline_mod = _load_pipeline_module()
    calls: list[dict[str, object]] = []

    def _capture(**kwargs):
        calls.append(dict(kwargs))
        return {"status": "completed"}

    monkeypatch.setattr(pipeline_mod, "_run_formal_balance_pipeline", _capture)

    pipeline_mod.run_formal_balance_pipeline_sync(report_date="2026-08-31")
    pipeline_mod.run_formal_balance_pipeline_sync(
        report_date="2026-08-31",
        use_existing_fx_only=False,
    )
    pipeline_mod.run_formal_balance_pipeline_sync(
        report_date="2026-08-31",
        use_existing_fx_only=True,
        expected_fx_source_version=" sv_fx_choice_fixture ",
    )

    assert "use_existing_fx_only" not in calls[0]
    assert "use_existing_fx_only" not in calls[1]
    assert calls[2]["use_existing_fx_only"] is True
    assert calls[2]["expected_fx_source_version"] == "sv_fx_choice_fixture"


def test_private_pipeline_forwards_normalized_expected_source_version(monkeypatch):
    pipeline_mod = _load_pipeline_module()
    balance_calls: list[dict[str, object]] = []
    _patch_minimal_pipeline(pipeline_mod, monkeypatch, balance_calls)

    pipeline_mod._run_formal_balance_pipeline(
        report_date="2026-08-31",
        include_analytics=False,
        use_existing_fx_only=True,
        expected_fx_source_version=" sv_fx_choice_fixture ",
    )

    assert balance_calls[0]["use_existing_fx_only"] is True
    assert balance_calls[0]["expected_fx_source_version"] == "sv_fx_choice_fixture"


@pytest.mark.parametrize("invalid", ["", " ", 123])
def test_pipeline_rejects_invalid_expected_source_version(invalid):
    pipeline_mod = _load_pipeline_module()
    expected_error = TypeError if invalid == 123 else ValueError

    with pytest.raises(expected_error, match="expected_fx_source_version"):
        pipeline_mod._run_formal_balance_pipeline(
            report_date="2026-08-31",
            use_existing_fx_only=True,
            expected_fx_source_version=invalid,
        )
    with pytest.raises(expected_error, match="expected_fx_source_version"):
        pipeline_mod.run_formal_balance_pipeline_sync(
            report_date="2026-08-31",
            use_existing_fx_only=True,
            expected_fx_source_version=invalid,
        )


@pytest.mark.parametrize(
    "entrypoint",
    ["_run_formal_balance_pipeline", "run_formal_balance_pipeline_sync"],
)
def test_pipeline_rejects_expected_source_version_without_existing_mode(entrypoint):
    pipeline_mod = _load_pipeline_module()

    with pytest.raises(ValueError, match="requires use_existing_fx_only=True"):
        getattr(pipeline_mod, entrypoint)(
            report_date="2026-08-31",
            expected_fx_source_version="sv_fx_choice_fixture",
        )


@pytest.mark.parametrize("invalid", [0, 1, "false", None])
def test_pipeline_rejects_non_boolean_existing_fx_choice_before_work(invalid):
    pipeline_mod = _load_pipeline_module()

    with pytest.raises(TypeError, match="use_existing_fx_only must be a bool"):
        pipeline_mod._run_formal_balance_pipeline(
            report_date="2026-08-31",
            use_existing_fx_only=invalid,
        )
    with pytest.raises(TypeError, match="use_existing_fx_only must be a bool"):
        pipeline_mod.run_formal_balance_pipeline_sync(
            report_date="2026-08-31",
            use_existing_fx_only=invalid,
        )
