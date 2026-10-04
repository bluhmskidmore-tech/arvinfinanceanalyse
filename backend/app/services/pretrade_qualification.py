from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from typing import Any

import duckdb

SCHEMA_VERSION = "pretrade_qualification/v1"
SIGNAL_KIND = "factor_screen"
STRATEGY_CALCULATION_MODE = "historical_backfill"
CSI300_SERIES = (
    "CA.CSI300",
    "CA.CSI300_PCT_CHG",
    "CA.CSI300_PE",
)

_SOURCE_SPECS = (
    ("choice_stock_universe", "as_of_date", "through_target", True),
    ("choice_stock_sector_membership", "as_of_date", "through_target", True),
    ("choice_stock_daily_observation", "trade_date", "through_target", True),
    ("choice_stock_limit_quality", "as_of_date", "through_target", True),
    ("choice_stock_factor_snapshot", "as_of_date", "through_target", True),
    ("stock_adjustment_factor", "trade_date", "through_target", True),
    ("stock_limit_price_daily", "trade_date", "through_target", False),
    ("fact_livermore_gate_supplement_daily", "trade_date", "through_target", True),
    ("fact_choice_macro_daily", "trade_date", "through_target", True),
    ("choice_market_snapshot", "trade_date|date", "csi300_through_target", False),
    ("livermore_monitor_append", "", "full_optional", False),
    ("livermore_gate_history", "", "full_optional", False),
    ("livermore_gate_supplement", "", "full_optional", False),
)
_REQUIRED_RULE_KEYS = {
    "candidate_rule_version",
    "checklist_rule_version",
    "export_rule_version",
    "lookback_days",
    "signal_confluence_contract",
    "stale_calendar_days",
    "stock_candidate_policy",
    "strategy_calculation_mode",
    "top_n",
}
_SNAPSHOT_KEYS = {
    "target_date",
    "stock_candidate_policy",
    "signal_kind",
    "csi300_series",
    "sources",
    "external_sources",
    "sha256",
}
_EXTERNAL_PROFILE_KEYS = {"name", "present", "content_sha256"}
_EXTERNAL_SOURCE_NAMES = (
    "choice_stock_catalog",
    "cycle_rotation_macro_official_availability",
    "cycle_rotation_macro_official_releases",
    "macro_adversarial_signal_payload",
)
_SOURCE_PROFILE_KEYS = {
    "table",
    "date_column",
    "target_date",
    "selector",
    "present",
    "row_count",
    "columns",
    "content_sha256",
}


def unavailable_pretrade_qualification(reason: str) -> dict[str, object]:
    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        raise ValueError("unavailable pretrade qualification requires a reason")
    return {
        "schema": SCHEMA_VERSION,
        "status": "unavailable",
        "reason": normalized_reason,
    }


def capture_pretrade_input_snapshot(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_date: str,
    stock_candidate_policy: str,
    external_identity_profiles: object | None = None,
) -> dict[str, object]:
    """Capture the bounded source cut used to qualify one pretrade date.

    Historical readers use windows and latest-on-or-before selections, so the
    source cut deliberately covers each consumed family through ``target_date``
    rather than hashing only the target-day rows. The selector is recorded next
    to every digest and is not caller-configurable.
    """
    normalized_date = _normalize_date(target_date)
    normalized_policy = str(stock_candidate_policy or "").strip()
    if not normalized_policy:
        raise ValueError("stock_candidate_policy is required")
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    profiles = [
        _profile_source(
            conn,
            tables=tables,
            table_name=table_name,
            date_column=date_column,
            selector=selector,
            target_date=normalized_date,
        )
        for table_name, date_column, selector, _required in _SOURCE_SPECS
    ]
    external_profiles = (
        _external_source_profiles()
        if external_identity_profiles is None
        else _validated_external_profiles(external_identity_profiles)
    )
    snapshot: dict[str, object] = {
        "target_date": normalized_date,
        "stock_candidate_policy": normalized_policy,
        "signal_kind": SIGNAL_KIND,
        "csi300_series": list(CSI300_SERIES),
        "sources": profiles,
        "external_sources": external_profiles,
    }
    snapshot["sha256"] = _sha256(snapshot)
    return snapshot


def build_completed_pretrade_qualification(
    *,
    producer_result: Mapping[str, object],
    input_snapshot_before: Mapping[str, object],
    input_snapshot_after: Mapping[str, object],
    confluence_payload: Mapping[str, object],
    export_payload: Mapping[str, object],
    rule_identity: Mapping[str, object],
) -> dict[str, object]:
    """Build completed evidence from the producer's own immutable run values."""
    producer_status = str(producer_result.get("status") or "").strip().lower()
    empty_result = producer_result.get("empty_result") is True
    if producer_status not in {"ok", "completed"}:
        raise ValueError("pretrade producer did not complete")
    producer_run_id = str(producer_result.get("run_id") or "").strip()
    target_date = _normalize_date(
        str(
            producer_result.get("snapshot_as_of_date")
            or producer_result.get("as_of_date")
            or ""
        )
    )
    strategy_payload_sha256 = str(
        producer_result.get("strategy_payload_sha256") or ""
    ).strip()
    candidate_history_sha256 = str(
        producer_result.get("candidate_history_sha256") or ""
    ).strip()
    if (
        not producer_run_id
        or not _is_sha256(strategy_payload_sha256)
        or not _is_sha256(candidate_history_sha256)
    ):
        raise ValueError("producer identity or strategy payload identity is missing")
    before = _validated_snapshot(input_snapshot_before)
    after = _validated_snapshot(input_snapshot_after)
    if before != after:
        raise ValueError("pretrade source cut changed during production")
    if before["target_date"] != target_date:
        raise ValueError("producer and input snapshot dates differ")
    producer_policy = str(producer_result.get("stock_candidate_policy") or "").strip()
    producer_rule_version = str(producer_result.get("rule_version") or "").strip()
    if producer_policy != before["stock_candidate_policy"]:
        raise ValueError("producer and input snapshot policies differ")
    required_sources = {
        table_name
        for table_name, _date_column, _selector, required in _SOURCE_SPECS
        if required
    }
    missing_sources = [
        str(item.get("table") or "")
        for item in _mapping_list(before.get("sources"))
        if item.get("table") in required_sources and item.get("present") is not True
    ]
    if missing_sources:
        raise ValueError(
            "required pretrade sources are missing: " + ", ".join(missing_sources)
        )
    if str(confluence_payload.get("status") or "").strip().lower() != "completed":
        raise ValueError("signal confluence did not complete")
    if not _is_sha256(str(confluence_payload.get("canonical_output_sha256") or "")):
        raise ValueError("signal confluence output identity is missing")
    if str(export_payload.get("as_of_date") or "").strip()[:10] != target_date:
        raise ValueError("export payload date differs from producer date")
    normalized_rules = _normalized_mapping(rule_identity)
    if set(normalized_rules) != _REQUIRED_RULE_KEYS or any(
        value is None or value == "" for value in normalized_rules.values()
    ):
        raise ValueError("rule_identity is incomplete")
    if normalized_rules["stock_candidate_policy"] != before["stock_candidate_policy"]:
        raise ValueError("rule and input snapshot policies differ")
    if producer_rule_version != normalized_rules["candidate_rule_version"]:
        raise ValueError("producer and candidate rule versions differ")
    _validate_rule_identity(normalized_rules)
    candidate_row_count = _strict_nonnegative_int(
        producer_result.get("row_count"), field="candidate_row_count"
    )
    if empty_result != (candidate_row_count == 0):
        raise ValueError("producer empty status and candidate row count differ")
    evidence: dict[str, object] = {
        "schema": SCHEMA_VERSION,
        "status": "ready_empty" if empty_result else "ready",
        "producer_run_id": producer_run_id,
        "target_date": target_date,
        "stock_candidate_policy": str(before["stock_candidate_policy"]),
        "rule_identity": normalized_rules,
        "input_snapshot": before,
        "outputs": {
            "strategy_payload_sha256": strategy_payload_sha256,
            "candidate_history_sha256": candidate_history_sha256,
            "candidate_row_count": candidate_row_count,
            "signal_confluence_sha256": str(
                confluence_payload["canonical_output_sha256"]
            ),
            "pretrade_export_sha256": canonical_pretrade_export_projection_sha256(
                export_payload
            ),
        },
    }
    evidence["evidence_sha256"] = _sha256(evidence)
    return evidence


def normalize_pretrade_qualification(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return unavailable_pretrade_qualification(
            "completed_pretrade_provenance_missing"
        )
    schema = str(value.get("schema") or "").strip()
    status = str(value.get("status") or "").strip().lower()
    if schema != SCHEMA_VERSION:
        return unavailable_pretrade_qualification(
            "pretrade_qualification_schema_unsupported"
        )
    if status == "unavailable":
        reason = str(value.get("reason") or "").strip()
        return unavailable_pretrade_qualification(
            reason or "pretrade_qualification_invalid"
        )
    if status not in {"ready", "ready_empty"}:
        return unavailable_pretrade_qualification(
            "pretrade_qualification_status_invalid"
        )
    normalized = _normalized_mapping(value)
    stored_digest = str(normalized.pop("evidence_sha256", "") or "").strip()
    if not _is_sha256(stored_digest) or _sha256(normalized) != stored_digest:
        return unavailable_pretrade_qualification(
            "pretrade_qualification_digest_mismatch"
        )
    required_text = (
        "producer_run_id",
        "target_date",
        "stock_candidate_policy",
    )
    if any(not str(normalized.get(key) or "").strip() for key in required_text):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_identity_incomplete"
        )
    try:
        snapshot = _validated_snapshot(_as_mapping(normalized.get("input_snapshot")))
    except ValueError:
        return unavailable_pretrade_qualification(
            "pretrade_qualification_input_snapshot_invalid"
        )
    outputs = _as_mapping(normalized.get("outputs"))
    if set(outputs) != {
        "strategy_payload_sha256",
        "candidate_history_sha256",
        "candidate_row_count",
        "signal_confluence_sha256",
        "pretrade_export_sha256",
    } or not all(
        _is_sha256(str(outputs.get(key) or ""))
        for key in (
            "strategy_payload_sha256",
            "candidate_history_sha256",
            "signal_confluence_sha256",
            "pretrade_export_sha256",
        )
    ):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_output_identity_invalid"
        )
    raw_candidate_row_count = outputs.get("candidate_row_count")
    candidate_row_count = (
        raw_candidate_row_count
        if isinstance(raw_candidate_row_count, int)
        and not isinstance(raw_candidate_row_count, bool)
        else -1
    )
    if candidate_row_count < 0 or (status == "ready_empty") != (
        candidate_row_count == 0
    ):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_candidate_count_invalid"
        )
    rules = _as_mapping(normalized.get("rule_identity"))
    if set(rules) != _REQUIRED_RULE_KEYS or any(
        value is None or value == "" for value in rules.values()
    ):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_rule_identity_missing"
        )
    try:
        _validate_rule_identity(rules)
    except ValueError:
        return unavailable_pretrade_qualification(
            "pretrade_qualification_rule_identity_invalid"
        )
    if rules.get("stock_candidate_policy") != normalized.get(
        "stock_candidate_policy"
    ):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_rule_policy_mismatch"
        )
    if snapshot["target_date"] != str(normalized["target_date"]):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_date_mismatch"
        )
    if snapshot["stock_candidate_policy"] != normalized["stock_candidate_policy"]:
        return unavailable_pretrade_qualification(
            "pretrade_qualification_snapshot_policy_mismatch"
        )
    normalized["input_snapshot"] = snapshot
    normalized["outputs"] = _normalized_mapping(outputs)
    normalized["rule_identity"] = _normalized_mapping(rules)
    normalized["evidence_sha256"] = stored_digest
    return normalized


def qualify_pretrade_read_view(
    conn: duckdb.DuckDBPyConnection,
    *,
    evidence: object,
    target_date: str,
    stock_candidate_policy: str,
) -> dict[str, object]:
    normalized = normalize_pretrade_qualification(evidence)
    if normalized["status"] == "unavailable":
        return normalized
    normalized_date = _normalize_date(target_date)
    normalized_policy = str(stock_candidate_policy or "").strip()
    if normalized.get("target_date") != normalized_date:
        return unavailable_pretrade_qualification(
            "pretrade_qualification_target_date_mismatch"
        )
    if normalized.get("stock_candidate_policy") != normalized_policy:
        return unavailable_pretrade_qualification(
            "pretrade_qualification_policy_mismatch"
        )
    try:
        current_snapshot = capture_pretrade_input_snapshot(
            conn,
            target_date=normalized_date,
            stock_candidate_policy=normalized_policy,
        )
        current_candidate_sha256 = capture_pretrade_candidate_identity(
            conn, target_date=normalized_date
        )
    except (ValueError, duckdb.Error):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_current_read_unavailable"
        )
    if current_snapshot != normalized.get("input_snapshot"):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_source_cut_changed"
        )
    outputs = _as_mapping(normalized.get("outputs"))
    if current_candidate_sha256 != outputs.get("candidate_history_sha256"):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_candidate_output_changed"
        )
    return normalized


def qualify_sealed_pretrade_read(
    *,
    evidence: object,
    target_date: str,
    stock_candidate_policy: str,
) -> dict[str, object]:
    """Validate evidence already obtained from a verified sealed generation.

    This deliberately performs no source-table scan. The caller must only pass
    evidence embedded in the selected bundle after validating that bundle's
    manifest digest. Mutable latest receipts are not a valid input authority.
    """
    normalized = normalize_pretrade_qualification(evidence)
    if normalized["status"] == "unavailable":
        return normalized
    if normalized.get("target_date") != _normalize_date(target_date):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_target_date_mismatch"
        )
    if normalized.get("stock_candidate_policy") != str(
        stock_candidate_policy or ""
    ).strip():
        return unavailable_pretrade_qualification(
            "pretrade_qualification_policy_mismatch"
        )
    snapshot = _as_mapping(normalized.get("input_snapshot"))
    try:
        current_external_sources = _external_source_profiles()
    except (OSError, UnicodeError, ValueError):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_external_inputs_unavailable"
        )
    if current_external_sources != snapshot.get("external_sources"):
        return unavailable_pretrade_qualification(
            "pretrade_qualification_external_inputs_changed"
        )
    return normalized


def capture_pretrade_candidate_identity(
    conn: duckdb.DuckDBPyConnection,
    *,
    target_date: str,
) -> str:
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    candidate_profile = _profile_source(
        conn,
        tables=tables,
        table_name="livermore_candidate_history",
        date_column="snapshot_as_of_date",
        selector="through_target",
        target_date=_normalize_date(target_date),
    )
    if candidate_profile["present"] is not True:
        raise ValueError("livermore_candidate_history is unavailable")
    execution_profile = _profile_source(
        conn,
        tables=tables,
        table_name="livermore_candidate_execution_history",
        date_column="signal_date",
        selector="through_target",
        target_date=_normalize_date(target_date),
    )
    return _sha256(
        {
            "candidate_history": candidate_profile,
            "candidate_execution_history": execution_profile,
        }
    )


def canonical_pretrade_output_sha256(value: object) -> str:
    return _sha256(value)


def canonical_pretrade_confluence_projection_sha256(
    envelope: Mapping[str, object],
) -> str:
    meta = _as_mapping(envelope.get("result_meta"))
    stable_meta_fields = (
        "basis",
        "result_kind",
        "cache_version",
        "source_version",
        "rule_version",
        "quality_flag",
        "vendor_version",
        "vendor_status",
        "fallback_mode",
        "filters_applied",
        "tables_used",
        "evidence_rows",
    )
    return _sha256(
        {
            "result": _without_transport_fields(envelope.get("result")),
            "result_meta": {
                key: _without_transport_fields(meta.get(key))
                for key in stable_meta_fields
            },
        }
    )


def canonical_pretrade_export_projection_sha256(
    payload: Mapping[str, object],
) -> str:
    decision_fields = (
        "status",
        "as_of_date",
        "signal_kind",
        "candidate_count",
        "top_n",
        "market_states",
        "data_statuses",
        "freshness",
        "sector_distribution",
        "portfolio_flags",
        "decision",
        "rows",
    )
    return _sha256({key: payload.get(key) for key in decision_fields})


def _without_transport_fields(value: object) -> object:
    excluded = {
        "cache_hit",
        "computed_at",
        "duckdb_path",
        "output_paths",
        "qualification",
        "rerun_result",
        "served_at",
        "trace_id",
    }
    if isinstance(value, Mapping):
        return {
            str(key): _without_transport_fields(item)
            for key, item in value.items()
            if str(key) not in excluded
        }
    if isinstance(value, (list, tuple)):
        return [_without_transport_fields(item) for item in value]
    return value


def _profile_source(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    table_name: str,
    date_column: str,
    selector: str,
    target_date: str,
) -> dict[str, object]:
    profile: dict[str, object] = {
        "table": table_name,
        "date_column": date_column,
        "target_date": target_date,
        "selector": selector,
        "present": table_name in tables,
        "row_count": 0,
        "columns": [],
        "content_sha256": _sha256([]),
    }
    if table_name not in tables:
        return profile
    column_rows = conn.execute(f"pragma table_info('{table_name}')").fetchall()
    columns = [str(row[1]) for row in column_rows]
    profile["columns"] = [
        {"name": str(row[1]), "type": str(row[2]).upper()} for row in column_rows
    ]
    column_names = {column.lower() for column in columns}
    allowed_date_columns = date_column.split("|") if date_column else []
    effective_date_column = next(
        (column for column in allowed_date_columns if column in column_names),
        "",
    )
    if selector != "full_optional" and not effective_date_column:
        profile["present"] = False
        return profile
    if effective_date_column:
        profile["date_column"] = effective_date_column
    where_sql = "true"
    params: list[object] = []
    if selector != "full_optional":
        where_sql = f"try_cast({effective_date_column} as date) <= cast(? as date)"
        params = [target_date]
    if selector == "candidate_exact":
        if "signal_kind" not in {column.lower() for column in columns}:
            profile["present"] = False
            return profile
        where_sql = (
            f"try_cast({effective_date_column} as date) = cast(? as date) "
            "and signal_kind = ?"
        )
        params.append(SIGNAL_KIND)
    elif selector == "date_exact":
        where_sql = f"try_cast({effective_date_column} as date) = cast(? as date)"
        params = [target_date]
    elif selector == "csi300_through_target":
        if "series_id" not in {column.lower() for column in columns}:
            profile["present"] = False
            return profile
        placeholders = ", ".join("?" for _ in CSI300_SERIES)
        where_sql += f" and series_id in ({placeholders})"
        params.extend(CSI300_SERIES)
    cursor = conn.execute(
        f"select * from {table_name} where {where_sql} order by all",
        params,
    )
    digest = hashlib.sha256()
    digest.update(_canonical_json(profile["columns"]))
    digest.update(b"\n")
    row_count = 0
    while rows := cursor.fetchmany(1_000):
        for row in rows:
            digest.update(_canonical_json(list(row)))
            digest.update(b"\n")
            row_count += 1
    profile["row_count"] = row_count
    profile["content_sha256"] = digest.hexdigest()
    return profile


def _validated_snapshot(value: Mapping[str, object]) -> dict[str, object]:
    snapshot = _normalized_mapping(value)
    if set(snapshot) != _SNAPSHOT_KEYS:
        raise ValueError("pretrade input snapshot shape is invalid")
    stored_digest = str(snapshot.pop("sha256", "") or "").strip()
    if not _is_sha256(stored_digest) or _sha256(snapshot) != stored_digest:
        raise ValueError("pretrade input snapshot digest mismatch")
    target_date = _normalize_date(str(snapshot.get("target_date") or ""))
    if not str(snapshot.get("stock_candidate_policy") or "").strip():
        raise ValueError("pretrade input snapshot policy is missing")
    sources = _mapping_list(snapshot.get("sources"))
    external_sources = _validated_external_profiles(snapshot.get("external_sources"))
    if len(sources) != len(_SOURCE_SPECS):
        raise ValueError("pretrade input snapshot source set is incomplete")
    if {str(item.get("table") or "") for item in sources} != {
        spec[0] for spec in _SOURCE_SPECS
    }:
        raise ValueError("pretrade input snapshot source set is invalid")
    if any(not _is_sha256(str(item.get("content_sha256") or "")) for item in sources):
        raise ValueError("pretrade input snapshot source digest is invalid")
    specs = {
        table: (date_column, selector)
        for table, date_column, selector, _required in _SOURCE_SPECS
    }
    for item in sources:
        if set(item) != _SOURCE_PROFILE_KEYS:
            raise ValueError("pretrade input snapshot source shape is invalid")
        table = str(item.get("table") or "")
        expected_date_column, expected_selector = specs[table]
        actual_date_column = str(item.get("date_column") or "")
        valid_date_column = (
            actual_date_column in expected_date_column.split("|")
            if item.get("present") is True and expected_date_column
            else actual_date_column == expected_date_column
        )
        row_count = item.get("row_count")
        if (
            not valid_date_column
            or item.get("selector") != expected_selector
            or item.get("target_date") != target_date
            or not isinstance(item.get("present"), bool)
            or not isinstance(row_count, int)
            or isinstance(row_count, bool)
            or row_count < 0
            or not isinstance(item.get("columns"), list)
            or (
                item.get("present") is True
                and not _valid_column_identity(item.get("columns"))
            )
        ):
            raise ValueError("pretrade input snapshot selector is invalid")
    snapshot["target_date"] = target_date
    snapshot["sources"] = sources
    snapshot["external_sources"] = external_sources
    snapshot["sha256"] = stored_digest
    return snapshot


def _validated_external_profiles(value: object) -> list[dict[str, object]]:
    profiles = _mapping_list(value)
    if tuple(str(item.get("name") or "") for item in profiles) != _EXTERNAL_SOURCE_NAMES:
        raise ValueError("pretrade external input source set is invalid")
    if any(
        set(item) != _EXTERNAL_PROFILE_KEYS
        or not isinstance(item.get("present"), bool)
        or not _is_sha256(str(item.get("content_sha256") or ""))
        for item in profiles
    ):
        raise ValueError("pretrade external input snapshot is invalid")
    return profiles


def _validate_rule_identity(value: Mapping[str, object]) -> None:
    for key in (
        "candidate_rule_version",
        "checklist_rule_version",
        "export_rule_version",
        "signal_confluence_contract",
        "stock_candidate_policy",
        "strategy_calculation_mode",
    ):
        if not str(value.get(key) or "").strip():
            raise ValueError(f"rule identity is missing {key}")
    if value.get("strategy_calculation_mode") != STRATEGY_CALCULATION_MODE:
        raise ValueError("strategy calculation mode is invalid")
    for key in ("lookback_days", "stale_calendar_days", "top_n"):
        raw = value.get(key)
        if not isinstance(raw, int) or isinstance(raw, bool):
            raise ValueError(f"rule identity {key} is invalid")
        parsed = raw
        if parsed < 0 or (key == "top_n" and parsed < 1):
            raise ValueError(f"rule identity {key} is invalid")


def _external_source_profiles() -> list[dict[str, object]]:
    from backend.app.governance.settings import get_settings
    from backend.app.services.market_data_livermore_service import (
        capture_livermore_external_inputs,
    )

    settings = get_settings()
    captured = capture_livermore_external_inputs(
        settings.choice_stock_catalog_file
    )
    return _validated_external_profiles(captured.get("identity_profiles"))


def _strict_nonnegative_int(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} is invalid")
    return value


def _valid_column_identity(value: object) -> bool:
    if not isinstance(value, list) or not value:
        return False
    return all(
        isinstance(item, dict)
        and bool(str(item.get("name") or "").strip())
        and bool(str(item.get("type") or "").strip())
        for item in value
    )


def _normalize_date(value: str) -> str:
    normalized = str(value or "").strip()[:10]
    if not normalized:
        raise ValueError("target_date is required")
    return date.fromisoformat(normalized).isoformat()


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        _json_compatible(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [_normalized_mapping(item) for item in value if isinstance(item, Mapping)]


def _normalized_mapping(value: Mapping[str, object]) -> dict[str, Any]:
    return json.loads(_canonical_json(dict(value)))


def _json_compatible(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
