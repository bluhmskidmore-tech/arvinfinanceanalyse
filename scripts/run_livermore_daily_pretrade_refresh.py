from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from contextlib import AbstractContextManager, nullcontext
from datetime import date
from pathlib import Path
from typing import Callable, Literal, NotRequired, SupportsIndex, SupportsInt, TypedDict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock  # noqa: E402
from backend.app.repositories.duckdb_read_context import (  # noqa: E402
    current_duckdb_read_selection,
    resolve_effective_read_path,
)
from backend.app.repositories.duckdb_repo import read_only_connection  # noqa: E402
from backend.app.services.pretrade_qualification import (  # noqa: E402
    STRATEGY_CALCULATION_MODE,
    build_completed_pretrade_qualification,
    canonical_pretrade_confluence_projection_sha256,
    capture_pretrade_candidate_identity,
    capture_pretrade_input_snapshot,
    unavailable_pretrade_qualification,
)

DEFAULT_OUTPUT_DIR = "test_output/livermore_stock_selection"
DEFAULT_SAMPLE_STOCK_CODE = "600582.SH"
REQUIRED_MACRO_SERIES = ("CA.CSI300", "CA.CSI300_PCT_CHG", "CA.CSI300_PE")
_UPSTREAM_PROBE_CHECKS = (
    "choice_stock_inputs",
    "factor_snapshot",
    "csi300_macro",
)


class _CompletedPretradeView(TypedDict):
    signal_confluence: dict[str, object]
    pretrade_payload: NotRequired[dict[str, object]]
    qualification: NotRequired[dict[str, object]]


def _needs_upstream_probe(state: dict[str, object]) -> bool:
    checks = state.get("checks")
    if not isinstance(checks, dict):
        return True
    return any(
        not isinstance(checks.get(name), dict)
        or checks[name].get("ready") is not True
        for name in _UPSTREAM_PROBE_CHECKS
    )


def _check_ready(state: dict[str, object], name: str) -> bool:
    checks = state.get("checks")
    if not isinstance(checks, dict):
        return False
    check = checks.get(name)
    return isinstance(check, dict) and check.get("ready") is True


def run_livermore_daily_pretrade_refresh(
    *,
    duckdb_path: str | Path,
    target_date: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    top_n: int = 10,
    lookback_days: int = 90,
    stock_candidate_policy: str | None = None,
    sample_stock_code: str = DEFAULT_SAMPLE_STOCK_CODE,
    dry_run: bool = False,
    skip_upstream_probe: bool = False,
    theme_overlay_mode: Literal["off", "dry_run", "archive"] = "off",
    export_pretrade: bool = True,
) -> dict[str, object]:
    if theme_overlay_mode not in {"off", "dry_run", "archive"}:
        raise ValueError("theme_overlay_mode must be one of: off, dry_run, archive")
    resolved_path = _resolve_duckdb_path(duckdb_path)
    resolved_date = _normalize_date(target_date or date.today().isoformat())
    initial = inspect_livermore_daily_refresh_state(
        duckdb_path=resolved_path,
        target_date=resolved_date,
    )

    if dry_run:
        would_run_steps = _missing_step_names(initial)
        if theme_overlay_mode != "off":
            choice_step_count = sum(
                step
                in {
                    "materialize_choice_stock_inputs",
                    "materialize_choice_stock_factor_snapshot",
                }
                for step in would_run_steps
            )
            would_run_steps.insert(choice_step_count, "refresh_choice_stock_theme_overlay")
        return {
            "status": "dry_run",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "theme_overlay_mode": theme_overlay_mode,
            "local_state": initial,
            "would_run_steps": [
                *would_run_steps,
                "mature_livermore_candidate_outcomes",
                "verify_signal_confluence_closure",
            ],
        }

    steps: list[dict[str, object]] = []
    if _needs_upstream_probe(initial) and not skip_upstream_probe:
        probe = probe_target_market_data_availability(
            target_date=resolved_date,
            sample_stock_code=sample_stock_code,
        )
        steps.append({"name": "upstream_probe", "result": probe})
        if probe["status"] != "ready":
            return {
                "status": "not_ready",
                "duckdb_path": str(resolved_path),
                "target_date": resolved_date,
                "reason": "target_market_data_not_landed",
                "local_state": initial,
                "steps": steps,
            }

    state = initial
    if not _check_ready(state, "choice_stock_inputs"):
        from backend.app.tasks.choice_stock_materialize import (
            materialize_choice_stock_inputs,
        )

        payload = materialize_choice_stock_inputs(
            as_of_date=resolved_date,
            duckdb_path=str(resolved_path),
        )
        steps.append({"name": "choice_stock_inputs", "result": payload})
        state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)

    if not _check_ready(state, "factor_snapshot"):
        from backend.app.tasks.choice_stock_materialize import (
            materialize_choice_stock_factor_snapshot,
        )

        payload = materialize_choice_stock_factor_snapshot(
            as_of_date=resolved_date,
            duckdb_path=str(resolved_path),
        )
        steps.append({"name": "factor_snapshot", "result": payload})
        state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)

    if not _check_ready(state, "adjustment_factor"):
        return {
            "status": "not_ready",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "reason": "adjustment_factor_not_ready",
            "local_state": state,
            "steps": steps,
        }

    theme_overlay_result: dict[str, object] | None = None
    theme_overlay_failed = False
    if theme_overlay_mode != "off":
        try:
            from backend.app.governance.settings import get_settings
            from backend.app.tasks.choice_stock_observation_manifest import (
                resolve_latest_committed_choice_stock_observation,
            )
            from backend.app.tasks.choice_stock_theme_overlay_refresh import (
                refresh_choice_stock_theme_overlay,
            )

            observation = resolve_latest_committed_choice_stock_observation(
                duckdb_path=resolved_path,
                expected_report_date=resolved_date,
            )
            parent_run_id = observation.materialization_run_id
            digest = hashlib.sha256(f"{parent_run_id}|{resolved_date}".encode()).hexdigest()[:16]
            settings = get_settings()
            theme_overlay_result = refresh_choice_stock_theme_overlay(
                mode=theme_overlay_mode,
                duckdb_path=str(resolved_path),
                governance_dir=str(settings.governance_path),
                archive_root=str(settings.local_archive_path),
                expected_report_date=resolved_date,
                run_id=f"{parent_run_id}:theme-overlay",
                source_version=f"sv_choice_stock_theme_overlay_{digest}",
                vendor_version="vv_tushare_ths_current_overlay_v1",
            )
        except Exception as exc:
            theme_overlay_result = {
                "mode": theme_overlay_mode,
                "status": (
                    "archive_failed"
                    if theme_overlay_mode == "archive"
                    else "dry_run_failed"
                ),
                "overlay_status": (
                    "archive_failed"
                    if theme_overlay_mode == "archive"
                    else "dry_run_failed"
                ),
                "member_count": 0,
                "message": _summarize_error(exc),
            }
        theme_overlay_failed = str(theme_overlay_result.get("status") or "") not in {
            "completed",
            "dry_run",
        }
        steps.append({"name": "theme_overlay", "result": theme_overlay_result})

    if not _check_ready(state, "csi300_macro"):
        from backend.app.tasks.choice_macro import refresh_public_cross_asset_headlines

        payload = refresh_public_cross_asset_headlines(
            duckdb_path=str(resolved_path),
            lookback_days=lookback_days,
            report_date=resolved_date,
        )
        steps.append({"name": "public_cross_asset", "result": payload})
        state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)
        if not _check_ready(state, "csi300_macro"):
            return {
                "status": "not_ready",
                "duckdb_path": str(resolved_path),
                "target_date": resolved_date,
                "reason": "csi300_macro_not_landed_after_refresh",
                "local_state": state,
                "steps": steps,
            }

    if not _check_ready(state, "gate_supplement"):
        from scripts.backfill_livermore_gate_supplement import (
            backfill_livermore_gate_supplement,
        )

        payload = backfill_livermore_gate_supplement(
            duckdb_path=resolved_path,
            as_of_date=date.fromisoformat(resolved_date),
            lookback_days=lookback_days,
        )
        steps.append({"name": "gate_supplement", "result": payload})
        state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)
        if str(payload.get("status") or "") != "completed" or not _check_ready(
            state, "gate_supplement"
        ):
            return {
                "status": "not_ready",
                "duckdb_path": str(resolved_path),
                "target_date": resolved_date,
                "reason": "gate_supplement_not_landed_after_refresh",
                "local_state": state,
                "steps": steps,
            }

    if not _check_ready(state, "position_snapshot"):
        from scripts.sync_livermore_position_snapshot import (
            sync_livermore_position_snapshot,
        )

        payload = sync_livermore_position_snapshot(
            duckdb_path=resolved_path,
            target_as_of=resolved_date,
        )
        steps.append({"name": "position_snapshot", "result": payload})
        state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)

    from backend.app.tasks.livermore_candidate_history_materialize import (
        materialize_livermore_candidate_history,
    )

    candidate_payload = materialize_livermore_candidate_history(
        str(resolved_path),
        as_of_date=resolved_date,
        stock_candidate_policy=stock_candidate_policy,
    )
    steps.append({"name": "candidate_history", "result": candidate_payload})
    state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)
    candidate_materialization_ready = (
        str(candidate_payload.get("status") or "") in {"ok", "completed"}
        and str(candidate_payload.get("snapshot_as_of_date") or resolved_date) == resolved_date
    )
    state = _with_candidate_history_completion(
        state,
        ready=candidate_materialization_ready,
        row_count=_safe_int(candidate_payload.get("row_count")),
    )
    if not _check_ready(state, "candidate_history"):
        return {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "reason": "candidate_history_not_landed_after_refresh",
            "local_state": state,
            "steps": steps,
        }

    try:
        from backend.app.tasks.livermore_candidate_outcome_maturity import (
            mature_livermore_candidate_outcomes,
        )

        maturity_payload = mature_livermore_candidate_outcomes(
            resolved_path,
            evaluation_as_of_date=resolved_date,
        )
        steps.append({"name": "candidate_outcome_maturity", "result": maturity_payload})
    except Exception as exc:
        steps.append(
            {
                "name": "candidate_outcome_maturity",
                "result": {
                    "status": "failed",
                    "evaluation_as_of_date": resolved_date,
                    "error": _summarize_error(exc),
                },
            }
        )
        return {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "reason": "candidate_outcome_maturity_failed",
            "local_state": state,
            "steps": steps,
        }
    if maturity_payload.get("status") != "completed":
        return {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "reason": "candidate_outcome_maturity_not_completed",
            "local_state": state,
            "steps": steps,
        }

    pre_export_state = inspect_livermore_daily_refresh_state(
        duckdb_path=resolved_path,
        target_date=resolved_date,
    )
    pre_export_state = _with_candidate_history_completion(
        pre_export_state,
        ready=candidate_materialization_ready,
        row_count=_safe_int(candidate_payload.get("row_count")),
    )
    if not pre_export_state["ready"]:
        return {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "reason": "refresh_state_incomplete_before_export",
            "local_state": pre_export_state,
            "steps": steps,
        }

    candidate_history_status = (
        "ready_empty"
        if candidate_materialization_ready and _safe_int(candidate_payload.get("row_count")) == 0
        else "ready"
    )
    resolved_policy = str(candidate_payload.get("stock_candidate_policy") or "").strip()
    input_snapshot_before = candidate_payload.get("input_snapshot_before")
    if export_pretrade and not isinstance(input_snapshot_before, dict):
        return {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "candidate_history_status": candidate_history_status,
            "local_state": pre_export_state,
            "steps": steps,
            "reason": "pretrade_qualification_input_snapshot_missing",
            "pretrade_qualification": unavailable_pretrade_qualification(
                "pretrade_qualification_input_snapshot_missing"
            ),
        }
    try:
        qualified_view = (
            _build_completed_pretrade_view(
                duckdb_path=resolved_path,
                target_date=resolved_date,
                candidate_payload=candidate_payload,
                input_snapshot_before=input_snapshot_before,
                candidate_history_status=candidate_history_status,
                stock_candidate_policy=resolved_policy,
                top_n=top_n,
                lookback_days=lookback_days,
            )
            if export_pretrade
            else None
        )
        signal_confluence_result = (
            qualified_view["signal_confluence"]
            if qualified_view is not None
            else _verify_signal_confluence_closure(
                duckdb_path=resolved_path,
                target_date=resolved_date,
            )
        )
    except (OSError, ValueError, duckdb.Error) as exc:
        return {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "candidate_history_status": candidate_history_status,
            "local_state": pre_export_state,
            "steps": steps,
            "reason": "pretrade_qualification_failed",
            "qualification_error": _summarize_error(exc),
            "pretrade_qualification": unavailable_pretrade_qualification(
                "pretrade_qualification_failed"
            ),
        }
    steps.append({"name": "signal_confluence_closure", "result": signal_confluence_result})
    if signal_confluence_result.get("status") != "completed":
        result: dict[str, object] = {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "theme_overlay_mode": theme_overlay_mode,
            "candidate_history_status": candidate_history_status,
            "local_state": pre_export_state,
            "steps": steps,
            "reason": str(
                signal_confluence_result.get("reason") or "signal_confluence_closure_incomplete"
            ),
        }
        if theme_overlay_result is not None:
            result["theme_overlay"] = theme_overlay_result
        return result
    if not export_pretrade:
        result = {
            "status": "partial" if theme_overlay_failed else "completed",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "theme_overlay_mode": theme_overlay_mode,
            "candidate_history_status": candidate_history_status,
            "local_state": pre_export_state,
            "steps": steps,
            "pretrade_qualification": unavailable_pretrade_qualification(
                "pretrade_export_not_requested"
            ),
        }
        if theme_overlay_result is not None:
            result["theme_overlay"] = theme_overlay_result
        if theme_overlay_failed:
            result["reason"] = "theme_overlay_failed"
        return result

    from scripts.export_livermore_pretrade_check import _write_outputs

    assert qualified_view is not None
    assert "pretrade_payload" in qualified_view and "qualification" in qualified_view
    pretrade_payload = qualified_view["pretrade_payload"]
    qualification = qualified_view["qualification"]
    try:
        output_paths = _write_outputs(
            output_dir=Path(output_dir),
            as_of_date=resolved_date,
            rows=_pretrade_rows(pretrade_payload),
            payload=pretrade_payload,
        )
        pretrade_payload["output_paths"] = output_paths
        pretrade_payload["qualification"] = qualification
    except (OSError, ValueError, duckdb.Error) as exc:
        return {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "candidate_history_status": candidate_history_status,
            "local_state": pre_export_state,
            "steps": steps,
            "reason": "pretrade_qualification_failed",
            "qualification_error": _summarize_error(exc),
            "pretrade_qualification": unavailable_pretrade_qualification(
                "pretrade_qualification_failed"
            ),
        }
    steps.append({"name": "pretrade_export", "result": _compact_pretrade_result(pretrade_payload)})
    final_state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)
    final_state = _with_candidate_history_completion(
        final_state,
        ready=candidate_materialization_ready,
        row_count=_safe_int(candidate_payload.get("row_count")),
    )
    result = {
        "status": "partial" if theme_overlay_failed else "completed",
        "duckdb_path": str(resolved_path),
        "target_date": resolved_date,
        "theme_overlay_mode": theme_overlay_mode,
        "candidate_history_status": candidate_history_status,
        "local_state": final_state,
        "steps": steps,
        "pretrade_output_paths": pretrade_payload.get("output_paths"),
        "pretrade_decision": pretrade_payload.get("decision"),
        "pretrade_qualification": qualification,
    }
    if theme_overlay_result is not None:
        result["theme_overlay"] = theme_overlay_result
    if theme_overlay_failed:
        result["reason"] = "theme_overlay_failed"
    return result


def _build_completed_pretrade_view(
    *,
    duckdb_path: Path,
    target_date: str,
    candidate_payload: dict[str, object],
    input_snapshot_before: object,
    candidate_history_status: str,
    stock_candidate_policy: str,
    top_n: int,
    lookback_days: int,
) -> _CompletedPretradeView:
    from scripts.export_livermore_pretrade_check import (
        DEFAULT_MAX_SECTOR_WEIGHT,
        DEFAULT_MIN_AMOUNT,
        DEFAULT_STALE_CALENDAR_DAYS,
        _build_livermore_pretrade_payload_from_connection,
    )
    from scripts.export_livermore_pretrade_check import (
        RULE_VERSION as EXPORT_RULE_VERSION,
    )
    from backend.app.governance.settings import get_settings
    from backend.app.services.market_data_livermore_service import (
        capture_livermore_external_inputs,
        livermore_external_input_identities_match,
    )

    if not isinstance(input_snapshot_before, dict):
        raise ValueError("pretrade qualification input snapshot is missing")
    candidate_external_profiles = candidate_payload.get(
        "external_input_identity_profiles"
    )
    if not isinstance(candidate_external_profiles, list):
        raise ValueError("pretrade producer external input identities are missing")
    choice_stock_catalog_file = get_settings().choice_stock_catalog_file
    captured_external_inputs = capture_livermore_external_inputs(
        choice_stock_catalog_file
    )
    if (
        captured_external_inputs.get("identity_profiles")
        != candidate_external_profiles
    ):
        raise ValueError("pretrade producer external inputs changed before finalization")
    with read_only_connection(str(duckdb_path)) as qualification_conn:
        qualification_conn.execute("begin transaction")
        signal_confluence = _verify_signal_confluence_closure(
            duckdb_path=duckdb_path,
            target_date=target_date,
            conn=qualification_conn,
            choice_stock_catalog_file=choice_stock_catalog_file,
            captured_external_inputs=captured_external_inputs,
        )
        if signal_confluence.get("status") != "completed":
            return {"signal_confluence": signal_confluence}
        final_candidate_history_sha256 = capture_pretrade_candidate_identity(
            qualification_conn,
            target_date=target_date,
        )
        pretrade_payload = _build_livermore_pretrade_payload_from_connection(
            qualification_conn,
            as_of_date=target_date,
            top_n=top_n,
            min_amount=DEFAULT_MIN_AMOUNT,
            max_sector_weight=DEFAULT_MAX_SECTOR_WEIGHT,
            stale_calendar_days=DEFAULT_STALE_CALENDAR_DAYS,
            today=target_date,
            allow_empty=candidate_history_status == "ready_empty",
        )
        pretrade_payload["duckdb_path"] = str(duckdb_path)
        input_snapshot_after = capture_pretrade_input_snapshot(
            qualification_conn,
            target_date=target_date,
            stock_candidate_policy=stock_candidate_policy,
            external_identity_profiles=captured_external_inputs["identity_profiles"],
        )
        if not livermore_external_input_identities_match(
            captured_external_inputs,
            choice_stock_catalog_file=choice_stock_catalog_file,
        ):
            raise ValueError("pretrade external inputs changed during finalization")
        qualified_candidate_payload = {
            **candidate_payload,
            "candidate_history_sha256": final_candidate_history_sha256,
        }
        qualification = build_completed_pretrade_qualification(
            producer_result=qualified_candidate_payload,
            input_snapshot_before=input_snapshot_before,
            input_snapshot_after=input_snapshot_after,
            confluence_payload=signal_confluence,
            export_payload=pretrade_payload,
            rule_identity={
                "candidate_rule_version": str(candidate_payload.get("rule_version") or ""),
                "checklist_rule_version": "rv_pretrade_checklist_v1",
                "export_rule_version": EXPORT_RULE_VERSION,
                "lookback_days": int(lookback_days),
                "signal_confluence_contract": "livermore_signal_confluence/v1",
                "stale_calendar_days": DEFAULT_STALE_CALENDAR_DAYS,
                "stock_candidate_policy": stock_candidate_policy,
                "strategy_calculation_mode": STRATEGY_CALCULATION_MODE,
                "top_n": max(1, int(top_n)),
            },
        )
    return {
        "signal_confluence": signal_confluence,
        "pretrade_payload": pretrade_payload,
        "qualification": qualification,
    }


def monitor_livermore_daily_pretrade_refresh(
    *,
    duckdb_path: str | Path,
    target_date: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    top_n: int = 10,
    lookback_days: int = 90,
    stock_candidate_policy: str | None = None,
    sample_stock_code: str = DEFAULT_SAMPLE_STOCK_CODE,
    dry_run: bool = False,
    skip_upstream_probe: bool = False,
    theme_overlay_mode: Literal["off", "dry_run", "archive"] = "off",
    max_attempts: int = 12,
    poll_interval_seconds: float = 600,
    sleep_func: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    attempt_limit = max(1, int(max_attempts))
    interval = max(0.0, float(poll_interval_seconds))
    last_result: dict[str, object] | None = None
    for attempt in range(1, attempt_limit + 1):
        result = run_livermore_daily_pretrade_refresh(
            duckdb_path=duckdb_path,
            target_date=target_date,
            output_dir=output_dir,
            top_n=top_n,
            lookback_days=lookback_days,
            stock_candidate_policy=stock_candidate_policy,
            sample_stock_code=sample_stock_code,
            dry_run=dry_run,
            skip_upstream_probe=skip_upstream_probe,
            theme_overlay_mode=theme_overlay_mode,
        )
        last_result = result
        attempts.append(_compact_monitor_attempt(attempt, result))
        if result.get("status") != "not_ready":
            monitored = dict(result)
            monitored["attempt_count"] = attempt
            monitored["attempts"] = attempts
            return monitored
        if attempt < attempt_limit:
            sleep_func(interval)
    return {
        "status": "not_ready",
        "reason": "max_attempts_exhausted",
        "attempt_count": attempt_limit,
        "attempts": attempts,
        "last_result": last_result,
    }


def inspect_livermore_daily_refresh_state(
    *,
    duckdb_path: str | Path,
    target_date: str,
) -> dict[str, object]:
    requested_path = Path(duckdb_path)
    if not requested_path.is_absolute():
        requested_path = ROOT / requested_path
    resolved_path = Path(resolve_effective_read_path(requested_path)).resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {resolved_path}")
    selection = current_duckdb_read_selection()
    reads_selected_snapshot = selection is not None and resolved_path == Path(selection.snapshot_path).resolve()
    admission = (
        nullcontext()
        if reads_selected_snapshot
        else acquire_lock(
            resolve_duckdb_writer_lock(resolved_path),
            base_dir=resolved_path.parent,
            timeout_seconds=5.0,
        )
    )
    checks = {
        "choice_stock_inputs": {"ready": False, "row_count": 0},
        "factor_snapshot": {"ready": False, "row_count": 0},
        "adjustment_factor": {
            "ready": False,
            "row_count": 0,
            "required_row_count": 0,
            "missing_code_count": 0,
        },
        "csi300_macro": {"ready": False, "series": {}},
        "gate_supplement": {"ready": False, "row_count": 0},
        "position_snapshot": {"ready": False, "row_count": 0},
        "candidate_history": {"ready": False, "row_count": 0},
    }
    with admission:
        with read_only_connection(str(resolved_path), retries=1) as conn:
            tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
            checks["choice_stock_inputs"] = _choice_stock_input_check(
                conn,
                tables=tables,
                target_date=target_date,
            )
            checks["factor_snapshot"] = _date_count_check(
                conn,
                tables=tables,
                table_name="choice_stock_factor_snapshot",
                date_column="as_of_date",
                target_date=target_date,
            )
            checks["adjustment_factor"] = _adjustment_factor_check(
                conn,
                tables=tables,
                target_date=target_date,
            )
            checks["csi300_macro"] = _macro_series_check(conn, tables=tables, target_date=target_date)
            checks["gate_supplement"] = _gate_supplement_check(
                conn,
                tables=tables,
                target_date=target_date,
            )
            checks["position_snapshot"] = _position_snapshot_check(
                conn,
                tables=tables,
                target_date=target_date,
            )
            checks["candidate_history"] = _candidate_history_check(
                conn,
                tables=tables,
                target_date=target_date,
            )
    missing = [name for name, check in checks.items() if not _check_ready({"checks": checks}, name)]
    return {
        "target_date": target_date,
        "ready": not missing,
        "missing": missing,
        "checks": checks,
    }


def probe_target_market_data_availability(
    *,
    target_date: str,
    sample_stock_code: str = DEFAULT_SAMPLE_STOCK_CODE,
) -> dict[str, object]:
    compact = target_date.replace("-", "")
    try:
        from backend.app.governance.settings import get_settings
        from backend.app.repositories.tushare_adapter import (
            resolve_tushare_token_with_settings_fallback,
        )
        from backend.app.tasks.choice_stock_materialize import _TushareRestApi

        token = resolve_tushare_token_with_settings_fallback(get_settings())
        if not token:
            return {"status": "not_ready", "reason": "missing_tushare_token"}
        pro = _TushareRestApi(token)
        calendar = _records_from_frame(
            pro.trade_cal(exchange="SSE", start_date=compact, end_date=compact)
        )
        is_open = any(_safe_int(record.get("is_open")) == 1 for record in calendar)
        if not is_open:
            return {"status": "not_ready", "reason": "target_date_not_open", "calendar": calendar}
        csi300_rows = _records_from_frame(
            pro.index_daily(ts_code="000300.SH", start_date=compact, end_date=compact)
        )
        if not csi300_rows:
            return {"status": "not_ready", "reason": "missing_csi300_daily", "calendar": calendar}
        stock_rows = _records_from_frame(
            pro.daily(ts_code=sample_stock_code, start_date=compact, end_date=compact)
        )
        if not stock_rows:
            return {
                "status": "not_ready",
                "reason": "missing_stock_daily_sample",
                "calendar": calendar,
                "sample_stock_code": sample_stock_code,
            }
        return {
            "status": "ready",
            "target_date": target_date,
            "calendar": calendar,
            "csi300_row_count": len(csi300_rows),
            "sample_stock_code": sample_stock_code,
            "sample_stock_row_count": len(stock_rows),
        }
    except Exception as exc:
        return {
            "status": "not_ready",
            "reason": "upstream_probe_failed",
            "error": _summarize_error(exc),
        }


def _choice_stock_input_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    target_date: str,
) -> dict[str, object]:
    table_specs = {
        "choice_stock_universe": "as_of_date",
        "choice_stock_sector_membership": "as_of_date",
        "choice_stock_daily_observation": "trade_date",
        "choice_stock_limit_quality": "as_of_date",
    }
    counts = {
        table_name: _count_rows_on_date(conn, tables, table_name, date_column, target_date)
        for table_name, date_column in table_specs.items()
    }
    return {
        "ready": all(count > 0 for count in counts.values()),
        "row_count": counts.get("choice_stock_daily_observation", 0),
        "counts": counts,
    }


def _date_count_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    table_name: str,
    date_column: str,
    target_date: str,
) -> dict[str, object]:
    count = _count_rows_on_date(conn, tables, table_name, date_column, target_date)
    return {"ready": count > 0, "row_count": count}


def _gate_supplement_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    target_date: str,
) -> dict[str, object]:
    table_name = "fact_livermore_gate_supplement_daily"
    row_count = _count_rows_on_date(conn, tables, table_name, "trade_date", target_date)
    if row_count <= 0:
        return {"ready": False, "row_count": 0, "usable_row_count": 0}
    try:
        row = conn.execute(
            f"""
            select count(*)::integer
            from {table_name}
            where trade_date = ?
              and breadth_5d is not null
              and limit_up_quality_ok is not null
            """,
            [target_date],
        ).fetchone()
    except duckdb.Error:
        return {"ready": False, "row_count": row_count, "usable_row_count": 0}
    usable_row_count = int(row[0] or 0) if row else 0
    return {
        "ready": usable_row_count > 0,
        "row_count": row_count,
        "usable_row_count": usable_row_count,
    }


def _position_snapshot_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    target_date: str,
) -> dict[str, object]:
    if "livermore_position_snapshot" not in tables:
        return {"ready": True, "row_count": 0, "status": "not_materialized"}
    row = conn.execute(
        """
        select count(*)::integer
        from livermore_position_snapshot
        where as_of_date = ?
          and upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
        """,
        [target_date],
    ).fetchone()
    count = int(row[0] or 0) if row else 0
    return {"ready": count > 0, "row_count": count}


def _candidate_history_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    target_date: str,
) -> dict[str, object]:
    if "livermore_candidate_history" not in tables:
        return {"ready": False, "row_count": 0}
    row = conn.execute(
        """
        select count(*)::integer
        from livermore_candidate_history
        where snapshot_as_of_date = ?
          and signal_kind = 'factor_screen'
        """,
        [target_date],
    ).fetchone()
    count = int(row[0] or 0) if row else 0
    return {"ready": count > 0, "row_count": count}


def _macro_series_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    target_date: str,
) -> dict[str, object]:
    counts: dict[str, int] = {}
    if "fact_choice_macro_daily" in tables:
        rows = conn.execute(
            """
            select series_id, count(*)::integer
            from fact_choice_macro_daily
            where trade_date = ?
              and series_id in (?, ?, ?)
            group by series_id
            """,
            [target_date, *REQUIRED_MACRO_SERIES],
        ).fetchall()
        counts = {str(series_id): int(count or 0) for series_id, count in rows}
    series = {series_id: counts.get(series_id, 0) for series_id in REQUIRED_MACRO_SERIES}
    return {"ready": all(count > 0 for count in series.values()), "series": series}


def _adjustment_factor_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    target_date: str,
) -> dict[str, object]:
    if "choice_stock_daily_observation" not in tables or "stock_adjustment_factor" not in tables:
        return {
            "ready": False,
            "row_count": 0,
            "required_code_count": 0,
            "missing_code_count": 0,
        }
    observation_columns = _table_columns(conn, "choice_stock_daily_observation")
    factor_columns = _table_columns(conn, "stock_adjustment_factor")
    if not {"trade_date", "stock_code", "close_value"}.issubset(observation_columns):
        return {
            "ready": False,
            "row_count": 0,
            "required_code_count": 0,
            "missing_code_count": 0,
        }
    if not {"trade_date", "stock_code", "adj_factor"}.issubset(factor_columns):
        return {
            "ready": False,
            "row_count": 0,
            "required_code_count": 0,
            "missing_code_count": 0,
        }
    required_row = conn.execute(
        """
        select count(distinct upper(trim(stock_code)))::integer
        from choice_stock_daily_observation
        where trade_date = ?
          and stock_code is not null
          and trim(cast(stock_code as varchar)) <> ''
          and try_cast(close_value as double) > 0
          and isfinite(try_cast(close_value as double))
        """,
        [target_date],
    ).fetchone()
    required_code_count = int(required_row[0] or 0) if required_row else 0
    if required_code_count <= 0:
        return {
            "ready": False,
            "row_count": 0,
            "required_code_count": 0,
            "missing_code_count": 0,
        }
    row = conn.execute(
        """
        with required_codes as (
          select distinct upper(trim(stock_code)) as stock_code
          from choice_stock_daily_observation
          where trade_date = ?
            and stock_code is not null
            and trim(cast(stock_code as varchar)) <> ''
            and try_cast(close_value as double) > 0
            and isfinite(try_cast(close_value as double))
        ),
        landed as (
          select distinct upper(trim(stock_code)) as stock_code
          from stock_adjustment_factor
          where trade_date = ?
            and adj_factor is not null
            and adj_factor > 0
            and isfinite(adj_factor)
        )
        select
          (
            select count(*)::integer
            from required_codes req
            inner join landed using (stock_code)
          ),
          (
            select count(*)::integer
            from required_codes req
            left join landed using (stock_code)
            where landed.stock_code is null
          )
        """,
        [target_date, target_date],
    ).fetchone()
    row_count = int(row[0] or 0) if row else 0
    missing_code_count = int(row[1] or 0) if row else required_code_count
    return {
        "ready": required_code_count > 0 and missing_code_count == 0,
        "row_count": row_count,
        "required_code_count": required_code_count,
        "missing_code_count": missing_code_count,
    }


def _count_rows_on_date(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    table_name: str,
    date_column: str,
    target_date: str,
) -> int:
    if table_name not in tables:
        return 0
    try:
        row = conn.execute(
            f"select count(*)::integer from {table_name} where {date_column} = ?",
            [target_date],
        ).fetchone()
    except duckdb.Error:
        return 0
    return int(row[0] or 0) if row else 0


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}


def _missing_step_names(state: dict[str, object]) -> list[str]:
    mapping = {
        "choice_stock_inputs": "materialize_choice_stock_inputs",
        "factor_snapshot": "materialize_choice_stock_factor_snapshot",
        "csi300_macro": "refresh_public_cross_asset_headlines",
        "gate_supplement": "backfill_livermore_gate_supplement",
        "position_snapshot": "sync_livermore_position_snapshot",
        "candidate_history": "materialize_livermore_candidate_history",
    }
    missing = state.get("missing")
    return [mapping[name] for name in missing if name in mapping] if isinstance(missing, list) else []


def _with_candidate_history_completion(
    state: dict[str, object],
    *,
    ready: bool,
    row_count: int,
) -> dict[str, object]:
    if not ready:
        return state
    state_checks = state.get("checks")
    checks = {
        str(name): dict(check) if isinstance(check, dict) else check
        for name, check in state_checks.items()
    } if isinstance(state_checks, dict) else {}
    checks["candidate_history"] = {
        "ready": True,
        "row_count": row_count,
        "status": "ready_empty" if row_count == 0 else "ready",
    }
    missing = [
        str(name)
        for name, check in checks.items()
        if isinstance(check, dict) and check.get("ready") is not True
    ]
    return {
        **state,
        "checks": checks,
        "missing": missing,
        "ready": not missing,
    }


def _verify_signal_confluence_closure(
    *,
    duckdb_path: str | Path,
    target_date: str,
    choice_stock_catalog_file: str | Path | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
    captured_external_inputs: dict[str, object] | None = None,
) -> dict[str, object]:
    resolved_path = _resolve_duckdb_path(duckdb_path)
    try:
        if choice_stock_catalog_file is None:
            from backend.app.governance.settings import get_settings

            choice_stock_catalog_file = get_settings().choice_stock_catalog_file
        from backend.app.services.livermore_signal_confluence_service import (
            livermore_signal_confluence_envelope,
        )

        envelope = livermore_signal_confluence_envelope(
            duckdb_path=str(resolved_path),
            as_of_date=target_date,
            choice_stock_catalog_file=choice_stock_catalog_file,
            _conn=conn,
            _captured_external_inputs=captured_external_inputs,
        )
    except Exception as exc:
        return {
            "status": "partial",
            "reason": "signal_confluence_read_failed",
            "target_date": target_date,
            "error": _summarize_error(exc),
        }

    result = envelope.get("result") if isinstance(envelope, dict) else None
    meta = envelope.get("result_meta") if isinstance(envelope, dict) else None
    result_payload = result if isinstance(result, dict) else {}
    meta_payload = meta if isinstance(meta, dict) else {}
    macro_context = result_payload.get("macro_context")
    macro_payload = macro_context if isinstance(macro_context, dict) else {}
    state = result_payload.get("closed_loop_state")
    state_payload = state if isinstance(state, dict) else {}
    replay = state_payload.get("replay_status")
    replay_payload = replay if isinstance(replay, dict) else {}
    adversarial_context = result_payload.get("adversarial_context")
    adversarial_payload = adversarial_context if isinstance(adversarial_context, dict) else {}
    strategy_context = result_payload.get("strategy_context")
    strategy_payload = strategy_context if isinstance(strategy_context, dict) else {}

    verified: dict[str, object] = {
        "status": "completed",
        "target_date": target_date,
        "canonical_output_sha256": canonical_pretrade_confluence_projection_sha256(
            envelope
        ),
        "resolved_as_of_date": _optional_text(result_payload.get("as_of_date")),
        "meta": {
            "quality_flag": _optional_text(meta_payload.get("quality_flag")),
            "vendor_status": _optional_text(meta_payload.get("vendor_status")),
            "fallback_mode": _optional_text(meta_payload.get("fallback_mode")),
        },
        "macro": {
            "status": _optional_text(macro_payload.get("status")),
            "authority_status": _optional_text(macro_payload.get("authority_status")),
            "authority_reasons": _string_list(macro_payload.get("authority_reasons")),
        },
        "lineage_status": _optional_text(state_payload.get("lineage_status")),
        "replay": {
            "window_status": _optional_text(replay_payload.get("window_status")),
            "maturity_status": _optional_text(replay_payload.get("maturity_status")),
            "has_decision_usable_completed_stats": replay_payload.get(
                "has_decision_usable_completed_stats"
            )
            is True,
            "completed_dates": _safe_int(replay_payload.get("completed_dates")),
            "blocking_pending_date_count": _safe_int(
                replay_payload.get("blocking_pending_date_count")
            ),
            "unsupported_dates": _safe_int(replay_payload.get("unsupported_dates")),
            "proxy_only_dates": _safe_int(replay_payload.get("proxy_only_dates")),
            "matched_entry_count": _safe_int(replay_payload.get("matched_entry_count")),
            "has_required_horizon_stats": replay_payload.get("has_required_horizon_stats") is True,
        },
        "business_state": {
            "closed_loop_status": _optional_text(state_payload.get("status")),
            "entry_gate": _optional_text(state_payload.get("entry_gate")),
            "adversarial_risk_gate": _optional_text(adversarial_payload.get("risk_gate")),
            "adversarial_status": _optional_text(adversarial_payload.get("status")),
            "allows_new_entry_observations": strategy_payload.get(
                "allows_new_entry_observations"
            )
            is True,
        },
    }

    if not isinstance(result, dict):
        return {
            **verified,
            "status": "partial",
            "reason": "signal_confluence_result_missing",
        }

    resolved_as_of_date = verified.get("resolved_as_of_date")
    if not isinstance(resolved_as_of_date, str) or not resolved_as_of_date:
        return {
            **verified,
            "status": "partial",
            "reason": "signal_confluence_as_of_missing",
        }
    if resolved_as_of_date != target_date:
        return {
            **verified,
            "status": "partial",
            "reason": "signal_confluence_as_of_mismatch",
        }

    meta_value = verified.get("meta")
    meta_payload_compact = meta_value if isinstance(meta_value, dict) else {}
    quality_flag = _optional_text(meta_payload_compact.get("quality_flag"))
    vendor_status = _optional_text(meta_payload_compact.get("vendor_status"))
    fallback_mode = _optional_text(meta_payload_compact.get("fallback_mode")) or "none"
    meta_issues: list[str] = []
    if quality_flag != "ok":
        meta_issues.append(f"quality_flag={quality_flag or 'missing'}")
    if vendor_status != "ok":
        meta_issues.append(f"vendor_status={vendor_status or 'missing'}")
    if fallback_mode != "none":
        meta_issues.append(f"fallback_mode={fallback_mode}")
    if meta_issues:
        return {
            **verified,
            "status": "partial",
            "reason": "signal_confluence_meta_unhealthy",
            "meta_issues": meta_issues,
        }

    macro_value = verified.get("macro")
    macro_payload_compact = macro_value if isinstance(macro_value, dict) else {}
    if _optional_text(macro_payload_compact.get("authority_status")) != "ready":
        return {
            **verified,
            "status": "partial",
            "reason": "signal_confluence_macro_authority_blocked",
        }

    if _optional_text(verified.get("lineage_status")) != "complete":
        return {
            **verified,
            "status": "partial",
            "reason": "signal_confluence_lineage_incomplete",
        }

    replay_value = verified.get("replay")
    replay_payload_compact = replay_value if isinstance(replay_value, dict) else {}
    replay_maturity_status = _optional_text(replay_payload_compact.get("maturity_status"))
    replay_ready = replay_payload_compact.get("has_decision_usable_completed_stats") is True
    if replay_maturity_status != "ready" or not replay_ready:
        return {
            **verified,
            "status": "partial",
            "reason": "signal_confluence_replay_not_ready",
        }

    return verified


def _compact_pretrade_result(payload: dict[str, object]) -> dict[str, object]:
    return {
        "status": payload.get("status"),
        "as_of_date": payload.get("as_of_date"),
        "candidate_count": payload.get("candidate_count"),
        "decision": payload.get("decision"),
        "output_paths": payload.get("output_paths"),
    }


def _pretrade_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    rows = payload.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("pretrade rows are missing or malformed")
    return rows


def _compact_monitor_attempt(attempt: int, payload: dict[str, object]) -> dict[str, object]:
    compact: dict[str, object] = {
        "attempt": attempt,
        "status": payload.get("status"),
    }
    for key in ("target_date", "reason", "pretrade_output_paths", "pretrade_decision"):
        if key in payload:
            compact[key] = payload.get(key)
    return compact


def _resolve_duckdb_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {path}")
    return path


def _normalize_date(value: str) -> str:
    text = str(value or "").strip()
    if len(text) != 10:
        raise ValueError("target_date must be a valid YYYY-MM-DD date.")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError("target_date must be a valid YYYY-MM-DD date.") from exc


def _records_from_frame(frame: object) -> list[dict[str, object]]:
    if frame is None:
        return []
    try:
        if len(frame) == 0:  # type: ignore[arg-type]
            return []
        return list(frame.to_dict(orient="records"))  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        return []


def _summarize_error(exc: Exception) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else exc.__class__.__name__


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = _optional_text(item)
        if text:
            items.append(text)
    return items


def _safe_int(value: object) -> int:
    try:
        return int(value or 0) if isinstance(value, (str, bytes, bytearray, SupportsInt, SupportsIndex)) else 0
    except (TypeError, ValueError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the daily Livermore pretrade refresh pipeline.")
    parser.add_argument("--duckdb-path", default=None, help="Override the configured DuckDB path.")
    parser.add_argument("--target-date", default="", help="YYYY-MM-DD, defaults to today.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--stock-candidate-policy")
    parser.add_argument("--sample-stock-code", default=DEFAULT_SAMPLE_STOCK_CODE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-upstream-probe", action="store_true")
    parser.add_argument("--vendor-source-ip", help="Bind vendor traffic to a local IPv4 address.")
    parser.add_argument(
        "--theme-overlay-mode",
        choices=("off", "dry_run", "archive"),
        default="off",
    )
    parser.add_argument("--monitor", action="store_true", help="Retry until data lands or max attempts is reached.")
    parser.add_argument("--max-attempts", type=int, default=12)
    parser.add_argument("--poll-interval-seconds", type=float, default=600)
    args = parser.parse_args()
    try:
        if args.duckdb_path is None:
            from backend.app.governance.settings import get_settings

            args.duckdb_path = get_settings().duckdb_path
        options = {
            "duckdb_path": args.duckdb_path,
            "target_date": args.target_date.strip() or None,
            "output_dir": args.output_dir,
            "top_n": args.top_n,
            "lookback_days": max(7, int(args.lookback_days)),
            "stock_candidate_policy": args.stock_candidate_policy,
            "sample_stock_code": args.sample_stock_code,
            "dry_run": args.dry_run,
            "skip_upstream_probe": args.skip_upstream_probe,
            "theme_overlay_mode": args.theme_overlay_mode,
        }
        network: AbstractContextManager[None] = nullcontext()
        if args.vendor_source_ip and not args.dry_run:
            from backend.app.network.source_bound_socks_proxy import resolve_vendor_source_ip
            from scripts.choice_stock_daily_refresh import _vendor_source_network

            network = _vendor_source_network(resolve_vendor_source_ip(args.vendor_source_ip))
        with network:
            if args.monitor:
                result = monitor_livermore_daily_pretrade_refresh(
                    **options,
                    max_attempts=args.max_attempts,
                    poll_interval_seconds=args.poll_interval_seconds,
                )
            else:
                result = run_livermore_daily_pretrade_refresh(**options)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") in {"completed", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
