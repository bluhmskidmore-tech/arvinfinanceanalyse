from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.services.pretrade_qualification import (
    normalize_pretrade_qualification,
    qualify_pretrade_read_view,
    unavailable_pretrade_qualification,
)
from backend.app.tasks.financial_result_publication import FinancialPublicationInvalid
from backend.app.tasks.system_read_publication import (
    publish_preserved_system_read_generation,
    recover_committed_system_read_publication,
)

WORKFLOW = "market_daily"
SCHEMA_VERSION = "market-daily-aggregate/v1"
REQUIRED_CHILDREN = (
    "choice_stock_daily_refresh",
    "stock_adjustment_factor_daily_refresh",
    "stock_limit_price_daily_refresh",
    "macro_toolkit_freshness",
    "livermore_pretrade_candidates",
    "tushare_news_backup",
    "macro_toolkit_daily_chain",
)
_EXPECTED_FRESHNESS_STEPS = frozenset(
    {
        "commodity_daily_ingest",
        "public_cross_asset_headlines",
        "choice_policy_rate_7d",
        "choice_crisis_aa_5y",
        "tushare_ncd_shibor",
        "cffex_member_rank",
    }
)
_NON_TRADING_DEPENDENCY_CHAIN = {
    "stock_adjustment_factor_daily_refresh": "choice_stock_daily_refresh",
    "stock_limit_price_daily_refresh": "stock_adjustment_factor_daily_refresh",
    "livermore_pretrade_candidates": "stock_limit_price_daily_refresh",
}

_POINT_TABLES = (
    ("choice_stock_universe", "as_of_date", True),
    ("choice_stock_sector_membership", "as_of_date", True),
    ("choice_stock_daily_observation", "trade_date", True),
    ("choice_stock_limit_quality", "as_of_date", True),
    ("choice_stock_factor_snapshot", "as_of_date", True),
    ("choice_stock_concept_membership", "as_of_date", False),
    ("choice_stock_intraday_movement_event", "as_of_date", False),
    ("stock_adjustment_factor", "trade_date", True),
    ("stock_limit_price_daily", "trade_date", True),
    ("fact_choice_macro_daily", "trade_date", True),
    ("fact_livermore_gate_supplement_daily", "trade_date", True),
    ("livermore_position_snapshot", "as_of_date", False),
    ("livermore_candidate_history", "snapshot_as_of_date", False),
    ("livermore_stock_candidate_universe_history", "snapshot_as_of_date", False),
    ("livermore_candidate_execution_history", "signal_date", False),
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise FinancialPublicationInvalid(f"Market publication requires {field}.")
    return text


def _normalized_date(value: object, field: str) -> str:
    try:
        return date.fromisoformat(_required_text(value, field)).isoformat()
    except ValueError as exc:
        raise FinancialPublicationInvalid(f"Market publication has invalid {field}.") from exc


def _required_nonnegative_int(payload: Mapping[str, object], field: str, context: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FinancialPublicationInvalid(
            f"{context} requires non-negative integer {field}."
        )
    return value


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FinancialPublicationInvalid(f"Invalid market receipt: {path.name}.") from exc
    if not isinstance(value, dict):
        raise FinancialPublicationInvalid(f"Market receipt is not an object: {path.name}.")
    return value


def _write_json_atomic(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _validate_identity(
    receipt: Mapping[str, object], *, run_id: str, report_date: str
) -> None:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "workflow": WORKFLOW,
        "report_date": report_date,
    }
    if any(str(receipt.get(key) or "") != value for key, value in expected.items()):
        raise FinancialPublicationInvalid("Market aggregate receipt identity mismatch.")


def begin_aggregate(*, receipt_path: Path, run_id: str, report_date: str) -> dict[str, object]:
    normalized_run = _required_text(run_id, "run_id")
    normalized_date = _normalized_date(report_date, "report_date")
    if receipt_path.exists():
        raise FinancialPublicationInvalid("Market aggregate receipt already exists.")
    receipt: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": normalized_run,
        "workflow": WORKFLOW,
        "report_date": normalized_date,
        "status": "running",
        "started_at": _now(),
        "updated_at": _now(),
        "children": [],
    }
    _write_json_atomic(receipt_path, receipt)
    return receipt


def _load_for_update(*, receipt_path: Path, run_id: str, report_date: str) -> dict[str, object]:
    receipt = _read_json(receipt_path)
    _validate_identity(
        receipt,
        run_id=_required_text(run_id, "run_id"),
        report_date=_normalized_date(report_date, "report_date"),
    )
    return receipt


def _children(receipt: Mapping[str, object]) -> list[dict[str, object]]:
    value = receipt.get("children")
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise FinancialPublicationInvalid("Market aggregate child receipts are invalid.")
    return value


def start_child(
    *, receipt_path: Path, run_id: str, report_date: str, child_name: str, child_run_id: str
) -> dict[str, object]:
    receipt = _load_for_update(
        receipt_path=receipt_path, run_id=run_id, report_date=report_date
    )
    if receipt.get("status") != "running":
        raise FinancialPublicationInvalid("Market child cannot start after business completion.")
    if child_name not in REQUIRED_CHILDREN:
        raise FinancialPublicationInvalid("Unknown market aggregate child.")
    children = _children(receipt)
    if any(str(item.get("name") or "") == child_name for item in children):
        raise FinancialPublicationInvalid("Market aggregate child already has a receipt.")
    child: dict[str, object] = {
        "name": child_name,
        "run_id": _required_text(child_run_id, "child_run_id"),
        "status": "running",
        "started_at": _now(),
    }
    children.append(child)
    receipt["updated_at"] = _now()
    _write_json_atomic(receipt_path, receipt)
    return child


def skip_child(
    *,
    receipt_path: Path,
    run_id: str,
    report_date: str,
    child_name: str,
    reason: str,
    child_run_id: str | None = None,
    upstream_child_name: str | None = None,
    upstream_child_run_id: str | None = None,
    upstream_status: str | None = None,
) -> dict[str, object]:
    causal_skip = any(
        value is not None
        for value in (upstream_child_name, upstream_child_run_id, upstream_status)
    )
    if causal_skip and not all(
        str(value or "").strip()
        for value in (upstream_child_name, upstream_child_run_id, upstream_status)
    ):
        raise FinancialPublicationInvalid(
            "Causal market skip requires exact upstream child identity and status."
        )
    normalized_child_run_id = (
        _required_text(child_run_id, "child_run_id")
        if child_run_id is not None
        else f"{run_id}:{child_name}:external-unverified"
    )
    child = start_child(
        receipt_path=receipt_path,
        run_id=run_id,
        report_date=report_date,
        child_name=child_name,
        child_run_id=normalized_child_run_id,
    )
    receipt = _load_for_update(
        receipt_path=receipt_path, run_id=run_id, report_date=report_date
    )
    stored = next(item for item in _children(receipt) if item["name"] == child_name)
    if causal_skip:
        stored.update(
            {
                "status": "not_executed",
                "completed_at": _now(),
                "exit_code": None,
                "reason": _required_text(reason, "skip reason"),
                "result": {
                    "status": "not_executed",
                    "aggregate_run_id": _required_text(run_id, "run_id"),
                    "upstream_child_name": _required_text(
                        upstream_child_name, "upstream child name"
                    ),
                    "upstream_child_run_id": _required_text(
                        upstream_child_run_id, "upstream child run_id"
                    ),
                    "upstream_status": _required_text(
                        upstream_status, "upstream status"
                    ),
                    "no_write": True,
                },
            }
        )
    else:
        stored.update(
            {
                "status": "skipped_external_unverified",
                "completed_at": _now(),
                "reason": _required_text(reason, "skip reason"),
            }
        )
    receipt["updated_at"] = _now()
    _write_json_atomic(receipt_path, receipt)
    return stored


def _extract_json_object(raw: str) -> dict[str, object]:
    stripped = raw.strip()
    try:
        value = json.loads(stripped)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    candidates: list[dict[str, object]] = []
    cursor = 0
    while True:
        index = raw.find("{", cursor)
        if index < 0:
            break
        try:
            value, end = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            cursor = index + 1
            continue
        if isinstance(value, dict):
            candidates.append(value)
        cursor = index + end
    if not candidates:
        raise FinancialPublicationInvalid("Market child emitted no JSON result.")
    return candidates[-1]


def _find_limit_receipt(receipt_dir: Path, child_run_id: str) -> Path | None:
    matches: list[Path] = []
    for candidate in receipt_dir.glob("stock_limit_price_daily_refresh_*.json"):
        try:
            payload = _read_json(candidate)
        except FinancialPublicationInvalid:
            continue
        if str(payload.get("run_id") or "") == child_run_id:
            matches.append(candidate)
    if len(matches) > 1:
        raise FinancialPublicationInvalid("Multiple limit-price receipts match one child run.")
    return matches[0] if matches else None


def finish_child(
    *,
    receipt_path: Path,
    run_id: str,
    report_date: str,
    child_name: str,
    child_run_id: str,
    exit_code: int,
    output_path: Path,
    external_receipt_path: Path | None = None,
    external_receipt_dir: Path | None = None,
) -> dict[str, object]:
    receipt = _load_for_update(
        receipt_path=receipt_path, run_id=run_id, report_date=report_date
    )
    children = _children(receipt)
    matches = [item for item in children if item.get("name") == child_name]
    if len(matches) != 1 or str(matches[0].get("run_id") or "") != child_run_id:
        raise FinancialPublicationInvalid("Market child receipt identity mismatch.")
    child = matches[0]
    if child.get("status") != "running":
        raise FinancialPublicationInvalid("Market child is not running.")
    try:
        raw_output = output_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FinancialPublicationInvalid("Market child output is missing.") from exc
    output_result = _extract_json_object(raw_output) if exit_code == 0 else None
    if external_receipt_dir is not None:
        external_receipt_path = _find_limit_receipt(external_receipt_dir, child_run_id)
    external_receipt: dict[str, object] | None = None
    if external_receipt_path is not None and external_receipt_path.exists():
        external_receipt = _read_json(external_receipt_path)
    result = (
        external_receipt.get("result")
        if isinstance(external_receipt, Mapping) and isinstance(external_receipt.get("result"), Mapping)
        else output_result
    )
    child.update(
        {
            "status": "success" if exit_code == 0 else "failed",
            "completed_at": _now(),
            "exit_code": int(exit_code),
            "output_sha256": _sha256_bytes(raw_output.encode("utf-8")),
            "result": dict(result) if isinstance(result, Mapping) else None,
            "external_receipt": external_receipt,
            "external_receipt_sha256": (
                _sha256_bytes(_canonical_bytes(external_receipt))
                if external_receipt is not None
                else None
            ),
            "external_receipt_path": (
                str(external_receipt_path.resolve())
                if external_receipt_path is not None and external_receipt_path.exists()
                else None
            ),
        }
    )
    receipt["updated_at"] = _now()
    _write_json_atomic(receipt_path, receipt)
    return child


def _child_map(receipt: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    children = _children(receipt)
    names = [str(item.get("name") or "") for item in children]
    if tuple(names) != REQUIRED_CHILDREN:
        raise FinancialPublicationInvalid("Market aggregate requires the ordered seven child receipts.")
    return {name: item for name, item in zip(names, children, strict=True)}


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise FinancialPublicationInvalid(f"Market receipt has no {field} mapping.")
    return value


def _require_status(value: Mapping[str, object], statuses: set[str], field: str) -> str:
    status = str(value.get("status") or "").lower()
    if status not in statuses:
        raise FinancialPublicationInvalid(f"Market {field} is not complete.")
    return status


def _validate_successful_child(name: str, child: Mapping[str, object]) -> None:
    if child.get("status") != "success" or child.get("exit_code") != 0:
        raise FinancialPublicationInvalid(f"Market child {name} did not complete successfully.")
    _required_text(child.get("run_id"), f"{name} run_id")
    _required_text(child.get("output_sha256"), f"{name} output hash")
    _mapping(child.get("result"), f"{name} result")
    external = child.get("external_receipt")
    if isinstance(external, Mapping):
        try:
            generated_at = datetime.fromisoformat(
                _required_text(external.get("generated_at"), f"{name} generated_at")
            )
            started_at = datetime.fromisoformat(
                _required_text(child.get("started_at"), f"{name} started_at")
            )
            completed_at = datetime.fromisoformat(
                _required_text(child.get("completed_at"), f"{name} completed_at")
            )
        except ValueError as exc:
            raise FinancialPublicationInvalid(
                f"Market child {name} has invalid receipt timestamps."
            ) from exc
        if generated_at < started_at - timedelta(minutes=5) or generated_at > completed_at + timedelta(seconds=5):
            raise FinancialPublicationInvalid(
                f"Market child {name} external receipt is not from this invocation."
            )


def _choice_is_verified_non_trading_skip(
    receipt: Mapping[str, object],
    children: Mapping[str, Mapping[str, object]],
) -> bool:
    choice = children["choice_stock_daily_refresh"]
    result = choice.get("result")
    external = choice.get("external_receipt")
    if not isinstance(result, Mapping) or str(result.get("status") or "") != "skipped_non_trading_day":
        return False
    _validate_successful_child("choice_stock_daily_refresh", choice)
    if not isinstance(external, Mapping) or str(external.get("status") or "") != "skipped_non_trading_day":
        raise FinancialPublicationInvalid("Choice non-trading skip lacks its real external receipt.")
    report_date = _normalized_date(receipt.get("report_date"), "report_date")
    if date.fromisoformat(report_date).weekday() < 5:
        raise FinancialPublicationInvalid("Choice non-trading skip is not on a weekend date.")
    if _normalized_date(result.get("as_of_date"), "Choice as_of_date") != report_date:
        raise FinancialPublicationInvalid("Choice non-trading skip date does not match aggregate date.")
    if (
        result.get("no_write") is not True
        or result.get("as_of_date_explicit") is not False
        or result.get("database_write_scope") != []
        or result.get("governance_write_scope") != []
    ):
        raise FinancialPublicationInvalid(
            "Choice non-trading skip does not prove the default-date no-write boundary."
        )
    aggregate_run_id = _required_text(receipt.get("run_id"), "run_id")
    for child_name, upstream_name in _NON_TRADING_DEPENDENCY_CHAIN.items():
        child = children[child_name]
        if child.get("status") != "not_executed" or child.get("exit_code") is not None:
            raise FinancialPublicationInvalid(
                f"Market child {child_name} is not a causal no-write skip."
            )
        child_result = _mapping(child.get("result"), f"{child_name} skip result")
        upstream = children[upstream_name]
        expected_upstream_status = (
            "skipped_non_trading_day"
            if upstream_name == "choice_stock_daily_refresh"
            else "not_executed"
        )
        if (
            child_result.get("status") != "not_executed"
            or child_result.get("no_write") is not True
            or child_result.get("aggregate_run_id") != aggregate_run_id
            or child_result.get("upstream_child_name") != upstream_name
            or child_result.get("upstream_child_run_id") != upstream.get("run_id")
            or child_result.get("upstream_status") != expected_upstream_status
        ):
            raise FinancialPublicationInvalid(
                f"Market child {child_name} causal skip identity is invalid."
            )
    return True


def _validate_children(receipt: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    report_date = _normalized_date(receipt.get("report_date"), "report_date")
    children = _child_map(receipt)
    non_trading_skip = _choice_is_verified_non_trading_skip(receipt, children)
    required_success = (
        {
            "choice_stock_daily_refresh",
            "macro_toolkit_freshness",
            "tushare_news_backup",
            "macro_toolkit_daily_chain",
        }
        if non_trading_skip
        else set(REQUIRED_CHILDREN)
    )
    for name in required_success:
        _validate_successful_child(name, children[name])

    choice = children["choice_stock_daily_refresh"]
    choice_external = _mapping(choice.get("external_receipt"), "Choice external receipt")
    choice_result = _mapping(choice.get("result"), "Choice result")
    if non_trading_skip:
        choice_warnings = [str(item) for item in list(cast(Any, choice_external.get("warnings") or []))]
        unresolved_choice_warnings = [
            item for item in choice_warnings if not item.startswith("commit SHA unavailable:")
        ]
        if unresolved_choice_warnings:
            raise FinancialPublicationInvalid("Choice skip has unresolved receipt warnings.")
    else:
        _require_status(choice_external, {"success"}, "Choice receipt")
        _require_status(choice_result, {"success"}, "Choice result")
        if _normalized_date(choice_result.get("as_of_date"), "Choice as_of_date") != report_date:
            raise FinancialPublicationInvalid("Choice receipt date does not match aggregate date.")
        refresh = _mapping(choice_result.get("refresh"), "Choice refresh")
        _require_status(refresh, {"completed"}, "Choice refresh")
        if _normalized_date(refresh.get("report_date"), "Choice refresh report_date") != report_date:
            raise FinancialPublicationInvalid("Choice refresh date does not match aggregate date.")
        gate = _mapping(choice_result.get("gate_supplement"), "Choice gate supplement")
        _require_status(gate, {"completed"}, "Choice gate supplement")
        position = _mapping(
            choice_result.get("position_snapshot_rollforward"), "Choice position roll-forward"
        )
        _require_status(position, {"completed", "noop"}, "Choice position roll-forward")
        choice_warnings = [str(item) for item in list(cast(Any, choice_external.get("warnings") or []))]
        unresolved_choice_warnings = [
            item for item in choice_warnings if not item.startswith("commit SHA unavailable:")
        ]
        if unresolved_choice_warnings:
            raise FinancialPublicationInvalid("Choice completed with unresolved late-step warnings.")
        overlay_mode = str(refresh.get("theme_overlay_mode") or "")
        overlay_status = str(refresh.get("theme_overlay_status") or "")
        if overlay_mode == "archive" and overlay_status != "completed":
            raise FinancialPublicationInvalid("Choice theme overlay archive is not complete.")

    if not non_trading_skip:
        factor = children["stock_adjustment_factor_daily_refresh"]
        factor_external = _mapping(factor.get("external_receipt"), "adjustment external receipt")
        factor_result = _mapping(factor.get("result"), "adjustment result")
        _require_status(factor_external, {"completed"}, "adjustment receipt")
        _require_status(factor_result, {"completed"}, "adjustment result")
        if _normalized_date(factor_result.get("trade_date"), "adjustment trade_date") != report_date:
            raise FinancialPublicationInvalid("Adjustment receipt date does not match aggregate date.")
        if factor_result.get("required_cells_covered") is not True:
            raise FinancialPublicationInvalid("Adjustment receipt lacks complete required coverage.")
        if str(factor_result.get("table") or "") != "stock_adjustment_factor":
            raise FinancialPublicationInvalid("Adjustment receipt has an unknown write table.")

        limit_child = children["stock_limit_price_daily_refresh"]
        limit_external = _mapping(limit_child.get("external_receipt"), "limit external receipt")
        limit_result = _mapping(limit_child.get("result"), "limit result")
        _require_status(limit_external, {"completed", "completed_with_warnings"}, "limit receipt")
        _require_status(limit_result, {"completed", "completed_with_warnings"}, "limit result")
        if str(limit_external.get("run_id") or "") != str(limit_child.get("run_id") or ""):
            raise FinancialPublicationInvalid("Limit receipt is bound to another child run.")
        if _normalized_date(limit_result.get("start_date"), "limit start_date") != report_date:
            raise FinancialPublicationInvalid("Limit receipt start date mismatch.")
        if _normalized_date(limit_result.get("end_date"), "limit end_date") != report_date:
            raise FinancialPublicationInvalid("Limit receipt end date mismatch.")
        if limit_result.get("required_cells_covered") is not True or list(
            cast(Any, limit_result.get("failed_dates") or [])
        ):
            raise FinancialPublicationInvalid("Limit receipt lacks complete required coverage.")
        dq = _mapping(limit_result.get("dq"), "limit DQ")
        if int(cast(Any, dq.get("hard_violation_count") or 0)) != 0:
            raise FinancialPublicationInvalid("Limit receipt contains hard DQ violations.")

        pretrade = _mapping(children["livermore_pretrade_candidates"].get("result"), "pretrade result")
        _require_status(pretrade, {"completed"}, "pretrade result")
        if _normalized_date(pretrade.get("target_date"), "pretrade target_date") != report_date:
            raise FinancialPublicationInvalid("Pretrade receipt date does not match aggregate date.")
        state = _mapping(pretrade.get("local_state"), "pretrade final state")
        if state.get("ready") is not True or list(cast(Any, state.get("missing") or [])):
            raise FinancialPublicationInvalid("Pretrade final dependency state is incomplete.")
        qualification = normalize_pretrade_qualification(
            pretrade.get("pretrade_qualification")
        )
        if qualification.get("status") not in {"ready", "ready_empty"}:
            raise FinancialPublicationInvalid(
                "Pretrade result has no completed qualification evidence."
            )

    freshness = _mapping(children["macro_toolkit_freshness"].get("result"), "freshness result")
    freshness_external = _mapping(
        children["macro_toolkit_freshness"].get("external_receipt"),
        "freshness external receipt",
    )
    _require_status(freshness_external, {"success", "degraded"}, "macro freshness receipt")
    _require_status(freshness, {"success", "degraded"}, "macro freshness")
    if _normalized_date(freshness.get("report_date"), "freshness report_date") != report_date:
        raise FinancialPublicationInvalid("Macro freshness date does not match aggregate date.")
    steps = freshness.get("steps")
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)):
        raise FinancialPublicationInvalid("Macro freshness has no step receipts.")
    step_names = [
        _required_text(_mapping(step, "freshness step").get("step"), "freshness step name")
        for step in steps
    ]
    if len(step_names) != len(set(step_names)) or set(step_names) != _EXPECTED_FRESHNESS_STEPS:
        raise FinancialPublicationInvalid(
            "Macro freshness does not contain the exact normally-on step set."
        )
    for step in steps:
        step_mapping = _mapping(step, "freshness step")
        step_status = str(step_mapping.get("status") or "")
        if step_status in {"success", "skipped"}:
            continue
        step_result = step_mapping.get("result")
        explicitly_no_write = (
            isinstance(step_result, Mapping)
            and step_result.get("no_write") is True
            and str(step_result.get("publication_scope") or "")
            == "observation_only_no_write"
        )
        if not (step_status == "degraded" and explicitly_no_write):
            raise FinancialPublicationInvalid("Macro freshness contains an incomplete writer step.")

    news = _mapping(children["tushare_news_backup"].get("result"), "news result")
    _require_status(news, {"completed"}, "news result")
    for field in ("inserted", "purged_expired", "purged_expired_warehouse"):
        _required_nonnegative_int(news, field, "News result")

    macro_daily = _mapping(
        children["macro_toolkit_daily_chain"].get("result"), "macro daily result"
    )
    macro_daily_external = _mapping(
        children["macro_toolkit_daily_chain"].get("external_receipt"),
        "macro daily external receipt",
    )
    _require_status(
        macro_daily_external,
        {"completed", "degraded"},
        "macro daily external receipt",
    )
    _require_status(macro_daily, {"completed", "degraded"}, "macro daily result")
    readiness = _mapping(
        _mapping(macro_daily.get("chain"), "macro daily chain").get("readiness_after"),
        "macro daily readiness",
    )
    if readiness.get("observation_only") is not True or readiness.get("formal_use_allowed") is not False:
        raise FinancialPublicationInvalid("Macro daily artifacts crossed the formal-use boundary.")
    return children


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _profile_scope(
    conn: duckdb.DuckDBPyConnection,
    *,
    table_name: str,
    date_column: str,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    columns = conn.execute(
        "select column_name, data_type, is_nullable, ordinal_position "
        "from information_schema.columns where table_schema='main' and table_name=? "
        "order by ordinal_position",
        [table_name],
    ).fetchall()
    if not columns:
        return {
            "table_name": table_name,
            "date_column": date_column,
            "start_date": start_date,
            "end_date": end_date,
            "present": False,
            "row_count": 0,
        }
    column_names = {str(row[0]) for row in columns}
    if date_column not in column_names:
        raise FinancialPublicationInvalid(f"Market source table {table_name} lost its date column.")
    identifiers = ", ".join(_quote_identifier(str(row[0])) for row in columns)
    if start_date == "*" and end_date == "*":
        row = conn.execute(
            f"select count(*), bit_xor(hash({identifiers})), "
            f"sum(cast(hash({identifiers}) as hugeint)) from {_quote_identifier(table_name)}"
        ).fetchone()
    else:
        row = conn.execute(
            f"select count(*), bit_xor(hash({identifiers})), "
            f"sum(cast(hash({identifiers}) as hugeint)) from {_quote_identifier(table_name)} "
            f"where try_cast({_quote_identifier(date_column)} as date) between cast(? as date) and cast(? as date)",
            [start_date, end_date],
        ).fetchone()
    assert row is not None
    return {
        "table_name": table_name,
        "date_column": date_column,
        "start_date": start_date,
        "end_date": end_date,
        "present": True,
        "row_count": int(row[0] or 0),
        "content_hash_xor": str(row[1]),
        "content_hash_sum": str(row[2]),
        "schema_sha256": _sha256_bytes(_canonical_bytes([list(item) for item in columns])),
    }


def _source_scope_specs(
    conn: duckdb.DuckDBPyConnection,
    receipt: Mapping[str, object],
    children: Mapping[str, Mapping[str, object]],
) -> list[tuple[str, str, str, str, bool]]:
    report_date = _normalized_date(receipt.get("report_date"), "report_date")
    non_trading_skip = str(
        _mapping(
            children["choice_stock_daily_refresh"].get("result"), "Choice result"
        ).get("status")
        or ""
    ) == "skipped_non_trading_day"
    specs = (
        []
        if non_trading_skip
        else [
            (table, column, report_date, report_date, required)
            for table, column, required in _POINT_TABLES
        ]
    )
    choice = _mapping(children["choice_stock_daily_refresh"].get("result"), "Choice result")
    if not non_trading_skip:
        history_start = _normalized_date(
            choice.get("history_start_date") or report_date, "Choice history_start_date"
        )
        specs.append(("choice_stock_daily_observation", "trade_date", history_start, report_date, True))
        for table_name, date_column in (
            ("livermore_candidate_history", "snapshot_as_of_date"),
            ("livermore_stock_candidate_universe_history", "snapshot_as_of_date"),
            ("livermore_candidate_execution_history", "signal_date"),
        ):
            specs.append((table_name, date_column, "*", "*", False))
    freshness = _mapping(children["macro_toolkit_freshness"].get("result"), "freshness result")
    latest = _mapping(freshness.get("latest_observation_dates"), "freshness latest dates")
    commodity_date = latest.get("fact_commodity_futures_daily")
    if commodity_date:
        day = _normalized_date(commodity_date, "commodity latest date")
        specs.append(("fact_commodity_futures_daily", "trade_date", day, day, True))
    else:
        specs.append(("fact_commodity_futures_daily", "trade_date", report_date, report_date, True))
    freshness_steps = freshness.get("steps")
    if isinstance(freshness_steps, Sequence) and not isinstance(
        freshness_steps, (str, bytes)
    ):
        commodity_step = next(
            (
                step
                for step in freshness_steps
                if isinstance(step, Mapping)
                and str(step.get("step") or "") == "commodity_daily_ingest"
            ),
            None,
        )
        commodity_result = (
            commodity_step.get("result") if isinstance(commodity_step, Mapping) else None
        )
        if isinstance(commodity_result, Mapping) and commodity_result.get("start_date"):
            commodity_start = _normalized_date(
                commodity_result.get("start_date"), "commodity start_date"
            )
            commodity_end = _normalized_date(
                commodity_result.get("end_date") or report_date,
                "commodity end_date",
            )
            specs.append(
                (
                    "fact_commodity_futures_daily",
                    "trade_date",
                    commodity_start,
                    commodity_end,
                    True,
                )
            )
    macro_start = (date.fromisoformat(report_date) - timedelta(days=120)).isoformat()
    specs.append(("fact_choice_macro_daily", "trade_date", macro_start, report_date, True))
    cffex_date = latest.get("fact_cffex_member_rank_daily")
    if cffex_date:
        day = _normalized_date(cffex_date, "CFFEX latest date")
        specs.append(("fact_cffex_member_rank_daily", "trade_date", day, day, False))
    news_child = children["tushare_news_backup"]
    news_result = _mapping(news_child.get("result"), "news result")
    news_counters = {
        field: _required_nonnegative_int(news_result, field, "News result")
        for field in ("inserted", "purged_expired", "purged_expired_warehouse")
    }
    news_inserted = news_counters["inserted"]
    news_changed = any(value > 0 for value in news_counters.values())
    if news_changed:
        try:
            started_at = datetime.fromisoformat(
                _required_text(news_child.get("started_at"), "news started_at")
            ).astimezone(UTC)
            completed_at = datetime.fromisoformat(
                _required_text(news_child.get("completed_at"), "news completed_at")
            ).astimezone(UTC)
        except ValueError as exc:
            raise FinancialPublicationInvalid("News child has invalid execution timestamps.") from exc
        # The aggregate invokes the checked-in defaults: the widest producer window is
        # three days. Freeze the whole window, not merely the table's latest date.
        news_start = (started_at - timedelta(days=3)).date().isoformat()
        news_end = completed_at.date().isoformat()
        news_tables = (
            ("choice_news_event", "received_at", news_inserted > 0),
            ("fact_news_event", "pub_time", False),
        )
        for table_name, date_column, required in news_tables:
            specs.append((table_name, date_column, "*", "*", required))
            specs.append((table_name, date_column, news_start, news_end, required))
            tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
            if table_name not in tables:
                continue
            rows = conn.execute(
                f"select distinct try_cast({_quote_identifier(date_column)} as date) "
                f"from {_quote_identifier(table_name)} "
                f"where try_cast({_quote_identifier(date_column)} as date) "
                "between cast(? as date) and cast(? as date) and "
                f"try_cast({_quote_identifier(date_column)} as date) is not null order by 1",
                [news_start, news_end],
            ).fetchall()
            for row in rows:
                day = row[0].isoformat()
                specs.append((table_name, date_column, day, day, required))
    unique: dict[tuple[str, str, str, str], tuple[str, str, str, str, bool]] = {}
    for spec in specs:
        key = spec[:4]
        unique[key] = (*key, bool(unique.get(key, spec)[4] or spec[4]))
    return list(unique.values())


def _capture_source_cut_from_connection(
    conn: duckdb.DuckDBPyConnection, receipt: Mapping[str, object]
) -> dict[str, object]:
    children = _validate_children(receipt)
    specs = _source_scope_specs(conn, receipt, children)
    observations = [
        {
            **_profile_scope(
                conn,
                table_name=table,
                date_column=column,
                start_date=start,
                end_date=end,
            ),
            "required": required,
        }
        for table, column, start, end, required in specs
    ]
    for observation in observations:
        if observation["required"] and (
            observation["present"] is not True or cast(int, observation["row_count"]) < 1
        ):
            raise FinancialPublicationInvalid(
                f"Market source table {observation['table_name']} has incomplete coverage."
            )
    non_trading_skip = str(
        _mapping(
            children["choice_stock_daily_refresh"].get("result"), "Choice result"
        ).get("status")
        or ""
    ) == "skipped_non_trading_day"
    required_present_tables = (
        set()
        if non_trading_skip
        else {
            "livermore_candidate_history",
            "livermore_stock_candidate_universe_history",
            "livermore_candidate_execution_history",
        }
    )
    present_by_table = {
        str(item["table_name"]): item.get("present") is True for item in observations
    }
    missing_present = sorted(
        table for table in required_present_tables if not present_by_table.get(table, False)
    )
    if missing_present:
        raise FinancialPublicationInvalid(
            "Market pretrade source tables are missing at aggregate completion."
        )
    pretrade_availability = _qualify_pretrade_availability(
        conn,
        receipt=receipt,
        children=children,
        non_trading_skip=non_trading_skip,
    )
    return {
        "captured_at": _now(),
        "observations": observations,
        "sha256": _sha256_bytes(_canonical_bytes(observations)),
        "pretrade_availability": pretrade_availability,
    }


def _qualify_pretrade_availability(
    conn: duckdb.DuckDBPyConnection,
    *,
    receipt: Mapping[str, object],
    children: Mapping[str, Mapping[str, object]],
    non_trading_skip: bool,
) -> dict[str, object]:
    if non_trading_skip:
        return unavailable_pretrade_qualification(
            "choice_default_weekend_no_write_pretrade_not_executed"
        )
    pretrade = _mapping(
        children["livermore_pretrade_candidates"].get("result"),
        "pretrade result",
    )
    evidence = normalize_pretrade_qualification(
        pretrade.get("pretrade_qualification")
    )
    if evidence.get("status") not in {"ready", "ready_empty"}:
        raise FinancialPublicationInvalid(
            "Pretrade result has no usable qualification evidence."
        )
    report_date = _normalized_date(receipt.get("report_date"), "report_date")
    qualified = qualify_pretrade_read_view(
        conn,
        evidence=evidence,
        target_date=report_date,
        stock_candidate_policy=_required_text(
            evidence.get("stock_candidate_policy"),
            "pretrade stock candidate policy",
        ),
    )
    if qualified.get("status") not in {"ready", "ready_empty"}:
        raise FinancialPublicationInvalid(
            "Pretrade qualification no longer matches the completed aggregate source cut."
        )
    return qualified


def _capture_source_cut(settings: object, receipt: Mapping[str, object]) -> dict[str, object]:
    duckdb_path = getattr(settings, "duckdb_path", None)
    with duckdb.connect(_required_text(duckdb_path, "duckdb_path"), read_only=True) as conn:
        return _capture_source_cut_from_connection(conn, receipt)


def complete_business(
    settings: object, *, receipt_path: Path, run_id: str, report_date: str
) -> dict[str, object]:
    receipt = _load_for_update(
        receipt_path=receipt_path, run_id=run_id, report_date=report_date
    )
    if receipt.get("status") != "running":
        raise FinancialPublicationInvalid("Market aggregate is not running.")
    publication_enabled = bool(
        getattr(settings, "system_read_publication_enabled", False)
    )
    if publication_enabled:
        source_cut = _capture_source_cut(settings, receipt)
        receipt["pretrade_availability"] = source_cut.pop(
            "pretrade_availability"
        )
        receipt["source_cut"] = source_cut
    else:
        _child_map(receipt)
        receipt["source_cut"] = None
    receipt["status"] = "business_completed"
    receipt["business_completed_at"] = _now()
    receipt["updated_at"] = _now()
    _write_json_atomic(receipt_path, receipt)
    return receipt


def fail_aggregate(
    *,
    receipt_path: Path,
    run_id: str,
    report_date: str,
    failure_status: str,
    reason: str,
) -> dict[str, object]:
    if failure_status not in {"business_failed", "qualification_failed"}:
        raise FinancialPublicationInvalid("Unknown market aggregate failure status.")
    receipt = _load_for_update(
        receipt_path=receipt_path, run_id=run_id, report_date=report_date
    )
    if receipt.get("status") != "running":
        raise FinancialPublicationInvalid("Only a running market aggregate can fail.")
    receipt["status"] = failure_status
    receipt["failure_reason"] = _required_text(reason, "failure reason")
    receipt["failed_at"] = _now()
    receipt["updated_at"] = _now()
    _write_json_atomic(receipt_path, receipt)
    return receipt


def _verify_external_receipt_hashes(children: Mapping[str, Mapping[str, object]]) -> None:
    for child in children.values():
        path_value = child.get("external_receipt_path")
        expected_hash = child.get("external_receipt_sha256")
        if path_value is None:
            continue
        path = Path(str(path_value))
        payload = _read_json(path)
        if _sha256_bytes(_canonical_bytes(payload)) != str(expected_hash or ""):
            raise FinancialPublicationInvalid("Market child external receipt changed after completion.")


def _changed_terminal_references(
    children: Mapping[str, Mapping[str, object]], report_date: str
) -> tuple[tuple[str, str, str], ...]:
    choice = _mapping(children["choice_stock_daily_refresh"].get("result"), "Choice result")
    if str(choice.get("status") or "") == "skipped_non_trading_day":
        return ()
    refresh = _mapping(choice.get("refresh"), "Choice refresh")
    run_id = str(refresh.get("run_id") or "").strip()
    cache_key = str(refresh.get("cache_key") or "").strip()
    if run_id and cache_key:
        return ((run_id, cache_key, report_date),)
    return ()


def _changed_table_coverage(source_cut: Mapping[str, object]) -> tuple[tuple[str, str, str, int], ...]:
    raw = source_cut.get("observations")
    if not isinstance(raw, list):
        raise FinancialPublicationInvalid("Market aggregate has no source-cut observations.")
    by_table: dict[str, tuple[str, str, str, int]] = {}
    for item in raw:
        if not isinstance(item, Mapping) or item.get("present") is not True:
            continue
        row_count = int(item.get("row_count") or 0)
        start_date = str(item.get("start_date") or "")
        end_date = str(item.get("end_date") or "")
        if row_count < 1 or start_date != end_date or start_date == "*":
            continue
        table = str(item.get("table_name") or "")
        by_table[table] = (table, str(item.get("date_column") or ""), end_date, 1)
    if not by_table:
        raise FinancialPublicationInvalid("Market aggregate has no positive table coverage.")
    return tuple(by_table[key] for key in sorted(by_table))


def qualify_market_daily_receipt(
    settings: object, receipt: Mapping[str, object]
) -> tuple[
    dict[str, object],
    tuple[tuple[str, str, str, int], ...],
    tuple[tuple[str, str, str], ...],
    dict[str, object],
]:
    if receipt.get("status") not in {"business_completed", "publication_failed"}:
        raise FinancialPublicationInvalid("Market aggregate is not at its publication boundary.")
    children = _validate_children(receipt)
    _verify_external_receipt_hashes(children)
    stored_cut = _mapping(receipt.get("source_cut"), "source cut")
    stored_observations = stored_cut.get("observations")
    if str(stored_cut.get("sha256") or "") != _sha256_bytes(
        _canonical_bytes(stored_observations)
    ):
        raise FinancialPublicationInvalid("Market aggregate source-cut hash is invalid.")
    current_cut = _capture_source_cut(settings, receipt)
    stored_pretrade = normalize_pretrade_qualification(
        receipt.get("pretrade_availability")
    )
    if (
        not isinstance(receipt.get("pretrade_availability"), Mapping)
        or _canonical_bytes(stored_pretrade)
        != _canonical_bytes(receipt.get("pretrade_availability"))
    ):
        raise FinancialPublicationInvalid(
            "Market aggregate pretrade availability is invalid or non-normalized."
        )
    current_pretrade = normalize_pretrade_qualification(
        current_cut.pop("pretrade_availability", None)
    )
    if _canonical_bytes(stored_pretrade) != _canonical_bytes(current_pretrade):
        raise FinancialPublicationInvalid(
            "Market pretrade qualification changed after aggregate completion."
        )
    if _canonical_bytes(stored_observations) != _canonical_bytes(
        current_cut.get("observations")
    ):
        raise FinancialPublicationInvalid("Market source cut changed after aggregate completion.")
    report_date = _normalized_date(receipt.get("report_date"), "report_date")
    writer_receipt = dict(receipt)
    writer_receipt["status"] = "completed"
    writer_receipt["workflow"] = WORKFLOW
    writer_receipt["report_date"] = report_date
    return (
        writer_receipt,
        _changed_table_coverage(stored_cut),
        _changed_terminal_references(children, report_date),
        stored_pretrade,
    )


def _changed_source_validator(
    receipt: Mapping[str, object],
):
    stored_cut = _mapping(receipt.get("source_cut"), "source cut")
    stored_observations = stored_cut.get("observations")
    stored_observation_bytes = _canonical_bytes(stored_observations)
    stored_pretrade = normalize_pretrade_qualification(
        receipt.get("pretrade_availability")
    )

    def validate(conn: duckdb.DuckDBPyConnection) -> Mapping[str, str]:
        children = _validate_children(receipt)
        _verify_external_receipt_hashes(children)
        current_cut = _capture_source_cut_from_connection(conn, receipt)
        current_pretrade = normalize_pretrade_qualification(
            current_cut.pop("pretrade_availability", None)
        )
        if _canonical_bytes(current_pretrade) != _canonical_bytes(stored_pretrade):
            raise FinancialPublicationInvalid(
                "Market pretrade qualification changed inside the publication writer lock."
            )
        current_observation_bytes = _canonical_bytes(current_cut.get("observations"))
        if current_observation_bytes != stored_observation_bytes:
            raise FinancialPublicationInvalid(
                "Market source cut changed inside the publication writer lock."
            )
        external_hashes = sorted(
            str(child.get("external_receipt_sha256") or "")
            for child in children.values()
            if child.get("external_receipt_sha256")
        )
        return {
            "source_cut_sha256": _sha256_bytes(current_observation_bytes),
            "external_receipts_sha256": _sha256_bytes(_canonical_bytes(external_hashes)),
            "pretrade_availability_sha256": _sha256_bytes(
                _canonical_bytes(current_pretrade)
            ),
        }

    return validate


def _receipt_payload(value: object) -> dict[str, object]:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise FinancialPublicationInvalid("Market publisher returned an invalid receipt.")


def publish_aggregate(
    settings: object, *, receipt_path: Path, run_id: str, report_date: str
) -> dict[str, object]:
    receipt = _load_for_update(
        receipt_path=receipt_path, run_id=run_id, report_date=report_date
    )
    if receipt.get("status") not in {"business_completed", "publication_failed"}:
        raise FinancialPublicationInvalid("Exact aggregate run is not recoverable.")
    if not bool(getattr(settings, "system_read_publication_enabled", False)):
        return {"status": "disabled", "run_id": run_id, "workflow": WORKFLOW}
    try:
        writer_receipt, coverage, references, pretrade_availability = (
            qualify_market_daily_receipt(settings, receipt)
        )
        published = publish_preserved_system_read_generation(
            settings,
            writer_run_id=run_id,
            workflow=WORKFLOW,
            report_date=report_date,
            writer_receipt=writer_receipt,
            changed_table_coverage=coverage,
            changed_terminal_references=references,
            changed_source_validator=_changed_source_validator(receipt),
            pretrade_availability=pretrade_availability,
            data_update_run_id=None,
        )
    except Exception:
        receipt["status"] = "publication_failed"
        receipt["publication_failed_at"] = _now()
        receipt["updated_at"] = _now()
        _write_json_atomic(receipt_path, receipt)
        raise
    publication = _receipt_payload(published)
    receipt["status"] = "completed"
    receipt["publication"] = publication
    receipt["completed_at"] = _now()
    receipt["updated_at"] = _now()
    _write_json_atomic(receipt_path, receipt)
    return publication


def recover_or_publish(
    settings: object, *, receipt_path: Path, run_id: str, report_date: str
) -> dict[str, object]:
    receipt = _load_for_update(
        receipt_path=receipt_path, run_id=run_id, report_date=report_date
    )
    if receipt.get("status") not in {"business_completed", "publication_failed"}:
        raise FinancialPublicationInvalid("Exact aggregate run is not recoverable.")
    if not bool(getattr(settings, "system_read_publication_enabled", False)):
        return {"status": "disabled", "run_id": run_id, "workflow": WORKFLOW}
    recovered = recover_committed_system_read_publication(
        settings,
        writer_run_id=run_id,
        report_date=report_date,
        workflow=WORKFLOW,
    )
    if recovered is not None:
        receipt["status"] = "completed"
        receipt["publication"] = dict(recovered)
        receipt["completed_at"] = _now()
        receipt["updated_at"] = _now()
        _write_json_atomic(receipt_path, receipt)
        return dict(recovered)
    return publish_aggregate(
        settings, receipt_path=receipt_path, run_id=run_id, report_date=report_date
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persist and publish a market daily aggregate receipt.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "begin",
        "start-child",
        "skip-child",
        "finish-child",
        "complete-business",
        "fail-aggregate",
        "publish",
        "recover",
    ):
        child = subparsers.add_parser(command)
        child.add_argument("--receipt-path", type=Path, required=True)
        child.add_argument("--run-id", required=True)
        child.add_argument("--report-date", required=True)
        if command in {"start-child", "skip-child", "finish-child"}:
            child.add_argument("--child-name", required=True, choices=REQUIRED_CHILDREN)
        if command in {"start-child", "finish-child"}:
            child.add_argument("--child-run-id", required=True)
        if command == "skip-child":
            child.add_argument("--reason", required=True)
            child.add_argument("--child-run-id")
            child.add_argument("--upstream-child-name", choices=REQUIRED_CHILDREN)
            child.add_argument("--upstream-child-run-id")
            child.add_argument("--upstream-status")
        if command == "finish-child":
            child.add_argument("--exit-code", required=True, type=int)
            child.add_argument("--output-path", type=Path, required=True)
            child.add_argument("--external-receipt-path", type=Path)
            child.add_argument("--external-receipt-dir", type=Path)
        if command == "fail-aggregate":
            child.add_argument(
                "--failure-status",
                required=True,
                choices=("business_failed", "qualification_failed"),
            )
            child.add_argument("--reason", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "receipt_path": args.receipt_path,
        "run_id": args.run_id,
        "report_date": args.report_date,
    }
    try:
        if args.command == "begin":
            result = begin_aggregate(**common)
        elif args.command == "start-child":
            result = start_child(
                **common, child_name=args.child_name, child_run_id=args.child_run_id
            )
        elif args.command == "skip-child":
            result = skip_child(
                **common,
                child_name=args.child_name,
                reason=args.reason,
                child_run_id=args.child_run_id,
                upstream_child_name=args.upstream_child_name,
                upstream_child_run_id=args.upstream_child_run_id,
                upstream_status=args.upstream_status,
            )
        elif args.command == "finish-child":
            result = finish_child(
                **common,
                child_name=args.child_name,
                child_run_id=args.child_run_id,
                exit_code=args.exit_code,
                output_path=args.output_path,
                external_receipt_path=args.external_receipt_path,
                external_receipt_dir=args.external_receipt_dir,
            )
        elif args.command == "complete-business":
            settings = get_settings()
            result = complete_business(settings, **common)
        elif args.command == "fail-aggregate":
            result = fail_aggregate(
                **common,
                failure_status=args.failure_status,
                reason=args.reason,
            )
        elif args.command == "publish":
            settings = get_settings()
            result = publish_aggregate(settings, **common)
        else:
            settings = get_settings()
            result = recover_or_publish(settings, **common)
    except Exception as exc:  # noqa: BLE001 - scheduler needs one bounded failure result
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
