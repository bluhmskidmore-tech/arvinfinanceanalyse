#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.repositories.choice_data_opportunity_catalog import (  # noqa: E402
    build_choice_funding_edb_probe_plan,
)

ProbeMode = str


def build_choice_funding_probe_payload(
    *,
    as_of_date: str,
    chunk_size: int = 10,
    max_batches: int | None = None,
    macro_catalog_path: str | Path | None = None,
    probe_mode: ProbeMode = "date_slice",
    execute: bool = False,
    preflight: bool = False,
    choice_client: Any | None = None,
    runtime_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if max_batches is not None and max_batches <= 0:
        raise ValueError("max_batches must be positive when provided.")

    plan = build_choice_funding_edb_probe_plan(
        macro_catalog_path,
        as_of_date=as_of_date,
        chunk_size=chunk_size,
        probe_mode=probe_mode,  # type: ignore[arg-type]
    )
    selected_batches = plan.batches[:max_batches] if max_batches is not None else plan.batches
    payload: dict[str, Any] = {
        "status": "dry_run",
        "execute": bool(execute),
        "opportunity_id": plan.opportunity_id,
        "choice_api_function": plan.choice_api_function,
        "wrapper_status": plan.wrapper_status,
        "as_of_date": plan.as_of_date,
        "probe_mode": plan.probe_mode,
        "total_candidates": plan.total_candidates,
        "available_batch_count": len(plan.batches),
        "selected_batch_count": len(selected_batches),
        "batch_count": len(selected_batches),
        "landing_targets": list(plan.landing_targets),
        "batches": [batch.model_dump(mode="json") for batch in selected_batches],
    }
    preflight_payload = runtime_preflight or (
        build_choice_runtime_preflight() if execute or preflight else _skipped_runtime_preflight()
    )
    payload["preflight"] = preflight_payload
    if not execute:
        return payload

    if preflight_payload.get("status") != "config_present":
        payload.update(
            {
                "status": "blocked",
                "completed_batches": 0,
                "failed_batches": 0,
                "probe_results": [],
                "write_performed": False,
            }
        )
        return payload

    client = choice_client
    if client is None:
        from backend.app.repositories.choice_client import ChoiceClient

        client = ChoiceClient()

    probe_results: list[dict[str, Any]] = []
    for batch in selected_batches:
        result: dict[str, Any] = {
            "batch_index": batch.batch_index,
            "codes": list(batch.codes),
            "request_options": batch.request_options,
            "probe_mode": batch.probe_mode,
            "status": "completed",
            "error_code": 0,
            "error_message": "",
            "result_type": "",
            "row_count": 0,
            "date_min": "",
            "date_max": "",
        }
        try:
            raw_result = client.edb(batch.codes, batch.request_options)
            result.update(summarize_choice_probe_result(raw_result))
            if int(result["error_code"]) != 0:
                result["status"] = "failed"
        except Exception as exc:
            result["status"] = "failed"
            result["error_code"] = -1
            result["error_message"] = str(exc)
        probe_results.append(result)

    completed = sum(1 for item in probe_results if item["status"] == "completed")
    failed = len(probe_results) - completed
    payload.update(
        {
            "status": "completed" if failed == 0 else "partial" if completed else "failed",
            "completed_batches": completed,
            "failed_batches": failed,
            "probe_results": probe_results,
            "write_performed": False,
        }
    )
    return payload


def _skipped_runtime_preflight() -> dict[str, Any]:
    return {
        "status": "skipped",
        "choice_emquant_parent_configured": None,
        "choice_start_options_configured": None,
        "choice_request_options_configured": None,
        "emquant_importable": None,
        "starts_choice_session": False,
        "calls_choice_data_api": False,
        "write_performed": False,
        "detail": "Runtime preflight was not requested for this dry run.",
    }


def build_choice_runtime_preflight(
    *,
    settings: Any | None = None,
    configure_emquant_parent_func: Any | None = None,
    get_em_c_func: Any | None = None,
) -> dict[str, Any]:
    if settings is None or configure_emquant_parent_func is None or get_em_c_func is None:
        from backend.app.config import choice_runtime

        if settings is None:
            settings = choice_runtime.load_settings()
        if configure_emquant_parent_func is None:
            configure_emquant_parent_func = choice_runtime.configure_emquant_parent
        if get_em_c_func is None:
            get_em_c_func = choice_runtime._get_em_c

    emquant_parent = str(getattr(settings, "choice_emquant_parent", "") or "").strip()
    start_options = str(getattr(settings, "choice_start_options", "") or "").strip()
    request_options = str(getattr(settings, "choice_request_options", "") or "").strip()
    result: dict[str, Any] = {
        "status": "missing_config",
        "choice_emquant_parent_configured": bool(emquant_parent),
        "choice_start_options_configured": bool(start_options),
        "choice_request_options_configured": bool(request_options),
        "emquant_importable": False,
        "starts_choice_session": False,
        "calls_choice_data_api": False,
        "write_performed": False,
        "detail": "",
    }

    missing = []
    if not emquant_parent:
        missing.append("choice_emquant_parent")
    if not start_options:
        missing.append("choice_start_options")
    if missing:
        result["detail"] = f"Missing Choice runtime setting(s): {', '.join(missing)}."
        return result

    configure_emquant_parent_func(emquant_parent)
    if get_em_c_func() is None:
        result["detail"] = "EmQuantAPI.c could not be imported from the configured parent directory."
        return result

    result.update(
        {
            "status": "config_present",
            "emquant_importable": True,
            "detail": "Choice runtime settings are present and EmQuantAPI.c is importable.",
        }
    )
    return result


def summarize_choice_probe_result(raw_result: Any) -> dict[str, Any]:
    summary = _choice_result_probe_summary(raw_result)
    summary.update(_choice_result_shape_summary(raw_result))
    return summary


def _choice_result_probe_summary(raw_result: Any) -> dict[str, Any]:
    error_code = int(getattr(raw_result, "ErrorCode", 0) or 0)
    error_message = str(getattr(raw_result, "ErrorMsg", "") or "")
    return {
        "error_code": error_code,
        "error_message": error_message,
        "result_type": raw_result.__class__.__name__,
    }


def _choice_result_shape_summary(raw_result: Any) -> dict[str, Any]:
    dates = _choice_result_dates(raw_result)
    return {
        "row_count": _choice_result_row_count(raw_result),
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
        "series_details": _choice_result_series_details(raw_result),
    }


def _choice_result_dates(raw_result: Any) -> list[str]:
    if hasattr(raw_result, "Dates"):
        return sorted(
            {
                _normalize_choice_date(str(item))
                for item in getattr(raw_result, "Dates", [])
                if str(item).strip()
            }
        )

    columns = getattr(raw_result, "columns", [])
    if "DATES" in columns:
        try:
            values = raw_result["DATES"].dropna().astype(str).tolist()
        except Exception:
            values = []
        return sorted({_normalize_choice_date(str(item)) for item in values if str(item).strip()})
    return []


def _choice_result_row_count(raw_result: Any) -> int:
    if hasattr(raw_result, "Data") and hasattr(raw_result, "Dates"):
        dates = list(getattr(raw_result, "Dates", []) or [])
        data = getattr(raw_result, "Data", {}) or {}
        count = 0
        if isinstance(data, dict):
            for values in data.values():
                if not values:
                    continue
                first_indicator = values[0] if isinstance(values, list) else []
                if not isinstance(first_indicator, list):
                    continue
                for value in first_indicator[: len(dates)]:
                    if value is not None:
                        count += 1
        return count

    try:
        return int(len(raw_result))
    except Exception:
        return 0


def _choice_result_series_details(raw_result: Any) -> list[dict[str, Any]]:
    columns = getattr(raw_result, "columns", [])
    if "DATES" not in columns or "RESULT" not in columns or not hasattr(raw_result, "index"):
        return []

    try:
        codes = sorted({str(item) for item in raw_result.index.tolist()})
    except Exception:
        return []

    details = []
    for code in codes:
        try:
            rows = raw_result.loc[[code]]
        except Exception:
            continue
        observed_rows = len(rows)
        valid: list[tuple[str, float]] = []
        for index in range(observed_rows):
            row = rows.iloc[index]
            value = _row_value(row, "RESULT")
            if value is None:
                continue
            date_value = _normalize_choice_date(str(_row_value(row, "DATES") or ""))
            if not date_value:
                continue
            valid.append((date_value, float(value)))
        latest_date = ""
        latest_value: float | None = None
        if valid:
            latest_date, latest_value = sorted(valid, key=lambda item: item[0])[-1]
        details.append(
            {
                "code": code,
                "latest_date": latest_date,
                "latest_value": latest_value,
                "non_null_rows": len(valid),
                "observed_rows": observed_rows,
            }
        )
    return details


def _row_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except Exception:
        return None


def _normalize_choice_date(value: str) -> str:
    return value.strip().replace("/", "-")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a dry-run Choice EDB probe plan for funding-condition macro series."
    )
    parser.add_argument(
        "--as-of-date",
        default=date.today().isoformat(),
        help="Probe date in YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=10,
        help="Maximum Choice EDB codes per dry-run probe batch.",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Limit probe output/execution to the first N batches. Defaults to all batches.",
    )
    parser.add_argument(
        "--macro-catalog",
        default="",
        help="Optional Choice macro catalog path. Defaults to config/choice_macro_catalog.json.",
    )
    parser.add_argument(
        "--probe-mode",
        choices=["date_slice", "latest"],
        default="date_slice",
        help="Choice EDB request mode: date_slice uses the as-of date; latest asks Choice for the latest row.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run a read-only live Choice EDB probe after runtime preflight passes. Does not write DuckDB.",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Include a local runtime preflight in dry-run output without logging in to Choice.",
    )
    parser.add_argument(
        "--output-path",
        default="",
        help="Optional JSON output path for the dry-run or probe result.",
    )
    args = parser.parse_args(argv)

    try:
        date.fromisoformat(str(args.as_of_date))
        payload = build_choice_funding_probe_payload(
            as_of_date=str(args.as_of_date),
            chunk_size=int(args.chunk_size),
            max_batches=int(args.max_batches) if int(args.max_batches) > 0 else None,
            macro_catalog_path=args.macro_catalog or None,
            probe_mode=str(args.probe_mode),
            execute=bool(args.execute),
            preflight=bool(args.preflight),
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output_path:
        output_path = Path(str(args.output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
