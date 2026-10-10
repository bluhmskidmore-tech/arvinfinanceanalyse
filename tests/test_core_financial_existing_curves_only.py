from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from tests.helpers import load_module


def _manifest() -> list[dict[str, str]]:
    return [
        {
            "anchor_date": "2026-08-31",
            "curve_type": curve_type,
            "snapshot_date": "2026-08-31",
            "source_version": f"source_{curve_type}",
            "vendor_name": "fixture_vendor",
            "vendor_version": f"vendor_{curve_type}",
            "rule_version": "rule_fixture",
        }
        for curve_type in ("treasury", "cdb", "aaa_credit")
    ]


def _load_global_module():
    return load_module(
        "scripts.run_global_data_refresh",
        "scripts/run_global_data_refresh.py",
    )


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        duckdb_path="data/moss.duckdb",
        governance_path="data/governance",
        data_input_root="data/input",
        local_archive_path="data/archive",
        financial_publication_enabled=False,
    )


@pytest.mark.parametrize(
    ("build_kwargs", "expects_existing_flag"),
    [
        ({}, False),
        (
            {
                "use_existing_curves_only": True,
                "expected_curve_snapshots": _manifest(),
            },
            True,
        ),
    ],
)
def test_global_bond_step_only_injects_existing_curves_flag_when_true(
    monkeypatch,
    build_kwargs,
    expects_existing_flag,
):
    module = _load_global_module()
    bond_module = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        bond_module.materialize_bond_analytics_facts,
        "fn",
        lambda **kwargs: calls.append(dict(kwargs)) or {"status": "completed"},
    )

    steps = module._build_refresh_steps(
        settings=_settings(),
        report_date="2026-08-31",
        run_id="global-test",
        fx_source_path=None,
        **build_kwargs,
    )
    dict(steps)["bond_analytics"]()

    if expects_existing_flag:
        assert calls[0]["use_existing_curves_only"] is True
        assert calls[0]["expected_curve_snapshots"] == _manifest()
    else:
        assert "use_existing_curves_only" not in calls[0]
        assert "expected_curve_snapshots" not in calls[0]


@pytest.mark.parametrize("invalid", [0, 1, "true", None])
def test_global_rejects_non_boolean_existing_curves_flag(invalid):
    module = _load_global_module()

    with pytest.raises(TypeError, match="use_existing_curves_only must be a bool"):
        module.run_global_data_refresh(
            report_date="2026-08-31",
            use_existing_curves_only=invalid,
            dry_run=True,
        )


def test_global_pairs_existing_curves_mode_with_manifest():
    module = _load_global_module()

    with pytest.raises(ValueError, match="requires expected_curve_snapshots"):
        module.run_global_data_refresh(
            report_date="2026-08-31",
            use_existing_curves_only=True,
            dry_run=True,
        )
    with pytest.raises(ValueError, match="requires use_existing_curves_only=True"):
        module.run_global_data_refresh(
            report_date="2026-08-31",
            expected_curve_snapshots=_manifest(),
            dry_run=True,
        )


def test_curve_recovery_normalizer_strips_and_stably_sorts_manifest():
    from backend.app.schemas.curve_recovery import normalize_curve_recovery_options

    manifest = list(reversed(_manifest()))
    manifest[0] = {key: f" {value} " for key, value in manifest[0].items()}

    normalized = normalize_curve_recovery_options(
        use_existing_curves_only=True,
        expected_curve_snapshots=manifest,
    )

    assert normalized is not None
    assert [item["curve_type"] for item in normalized] == [
        "aaa_credit",
        "cdb",
        "treasury",
    ]
    assert all(value == value.strip() for item in normalized for value in item.values())


def test_curve_recovery_options_pair_mode_and_manifest():
    from backend.app.schemas.curve_recovery import normalize_curve_recovery_options

    assert (
        normalize_curve_recovery_options(
            use_existing_curves_only=False,
            expected_curve_snapshots=None,
        )
        is None
    )
    with pytest.raises(ValueError, match="requires use_existing_curves_only=True"):
        normalize_curve_recovery_options(
            use_existing_curves_only=False,
            expected_curve_snapshots=_manifest(),
        )
    with pytest.raises(ValueError, match="requires expected_curve_snapshots"):
        normalize_curve_recovery_options(
            use_existing_curves_only=True,
            expected_curve_snapshots=None,
        )
    with pytest.raises(ValueError, match="must not be empty"):
        normalize_curve_recovery_options(
            use_existing_curves_only=True,
            expected_curve_snapshots=[],
        )


@pytest.mark.parametrize(
    ("field", "invalid", "error_type"),
    [
        ("anchor_date", "20260831", ValueError),
        ("snapshot_date", "2026-02-30", ValueError),
        ("curve_type", "shibor", ValueError),
        ("source_version", " ", ValueError),
        ("vendor_name", 7, TypeError),
    ],
)
def test_curve_recovery_normalizer_rejects_invalid_fields(field, invalid, error_type):
    from backend.app.schemas.curve_recovery import normalize_curve_recovery_options

    manifest = _manifest()
    manifest[0][field] = invalid
    with pytest.raises(error_type, match=field):
        normalize_curve_recovery_options(
            use_existing_curves_only=True,
            expected_curve_snapshots=manifest,
        )


def test_curve_recovery_normalizer_rejects_invalid_keys_and_duplicate_grains():
    from backend.app.schemas.curve_recovery import normalize_curve_recovery_options

    missing_key = _manifest()
    missing_key[0].pop("rule_version")
    with pytest.raises(ValueError, match="invalid keys"):
        normalize_curve_recovery_options(
            use_existing_curves_only=True,
            expected_curve_snapshots=missing_key,
        )

    duplicate = _manifest()
    duplicate.append(dict(duplicate[0]))
    with pytest.raises(ValueError, match="duplicate anchor_date/curve_type"):
        normalize_curve_recovery_options(
            use_existing_curves_only=True,
            expected_curve_snapshots=duplicate,
        )


def test_global_curve_mode_dry_run_and_callbacks_record_normalized_manifest(monkeypatch):
    module = _load_global_module()
    expected = list(reversed(_manifest()))
    dry_run = module.run_global_data_refresh(
        report_date="2026-08-31",
        use_existing_curves_only=True,
        expected_curve_snapshots=expected,
        dry_run=True,
    )
    assert dry_run["curve_input_mode"] == "existing_canonical"
    assert dry_run["use_existing_curves_only"] is True
    assert [item["curve_type"] for item in dry_run["expected_curve_snapshots"]] == [
        "aaa_credit",
        "cdb",
        "treasury",
    ]

    settings = SimpleNamespace(
        duckdb_path="data/moss.duckdb",
        financial_publication_enabled=False,
        financial_publication_root="",
    )
    build_calls: list[dict[str, object]] = []
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "acquire_lock", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(
        module,
        "_build_refresh_steps",
        lambda **kwargs: build_calls.append(dict(kwargs))
        or [("formal_balance", lambda: {"status": "completed"})],
    )
    callbacks: list[dict[str, object]] = []
    receipt = module.run_global_data_refresh(
        report_date="2026-08-31",
        use_existing_curves_only=True,
        expected_curve_snapshots=expected,
        on_progress=lambda payload: callbacks.append(dict(payload)),
    )

    assert receipt["curve_input_mode"] == "existing_canonical"
    assert receipt["expected_curve_snapshots"] == dry_run["expected_curve_snapshots"]
    assert build_calls[0]["expected_curve_snapshots"] == dry_run["expected_curve_snapshots"]
    assert callbacks
    assert all(item["curve_input_mode"] == "existing_canonical" for item in callbacks)
    assert all(
        item["expected_curve_snapshots"] == dry_run["expected_curve_snapshots"]
        for item in callbacks
    )


def test_global_curve_failure_receipt_records_manifest(monkeypatch):
    module = _load_global_module()
    settings = SimpleNamespace(
        duckdb_path="data/moss.duckdb",
        financial_publication_enabled=False,
        financial_publication_root="",
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "acquire_lock", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(
        module,
        "_build_refresh_steps",
        lambda **_kwargs: [("bond_analytics", lambda: {"status": "failed"})],
    )

    with pytest.raises(module.GlobalDataRefreshFailed) as caught:
        module.run_global_data_refresh(
            report_date="2026-08-31",
            use_existing_curves_only=True,
            expected_curve_snapshots=_manifest(),
        )

    assert caught.value.receipt["curve_input_mode"] == "existing_canonical"
    assert caught.value.receipt["expected_curve_snapshots"] is not None
