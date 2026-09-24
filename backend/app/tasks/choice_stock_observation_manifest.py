from __future__ import annotations

import hashlib
import re
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheManifestRecord

CHOICE_STOCK_OBSERVATION_CACHE_KEY = "choice_stock.history_and_factor_snapshot"
CHOICE_STOCK_OBSERVATION_CACHE_VERSION = "choice_stock_refresh_v1"
CHOICE_STOCK_OBSERVATION_RULE_VERSION = "rv_choice_stock_materialization_front_layer_v1"
CHOICE_STOCK_OBSERVATION_MANIFEST_LOCK = LockDefinition(
    key="lock:governance:choice-stock-observation-manifest",
    ttl_seconds=60,
)


class ChoiceStockObservationManifestChangedError(ValueError):
    pass


@dataclass(frozen=True)
class ChoiceStockCommittedObservation:
    report_date: str
    materialization_run_id: str
    source_version: str
    vendor_version: str
    rule_version: str
    materialized_row_count: int
    daily_observation_row_count: int
    stock_code_count: int
    daily_by_key: dict[tuple[str, str], dict[str, object]]


def build_choice_stock_observation_manifest(
    *,
    history_result: Mapping[str, object],
    refresh_run_id: str,
    report_date: str,
    daily_observation_row_count: int,
    created_at: str | datetime | None = None,
) -> dict[str, object]:
    """Build a governed anchor for a committed choice-stock observation materialization."""
    normalized_report_date = _iso_date("report_date", report_date)
    materialized_report_date = _iso_date("history_result.as_of_date", history_result.get("as_of_date"))
    if materialized_report_date != normalized_report_date:
        raise ValueError("Choice-stock materialization date does not match refresh report_date")
    if _required_text("history_result.status", history_result.get("status")) != "completed":
        raise ValueError("Choice-stock observation manifest requires a completed materialization")

    materialization_run_id = _required_text(
        "history_result.run_id",
        history_result.get("run_id"),
    )
    source_version = _required_text(
        "history_result.source_version",
        history_result.get("source_version"),
    )
    vendor_version = _daily_landing_vendor_version(history_result)
    materialized_row_count = _positive_int(
        "history_result.row_count",
        history_result.get("row_count"),
    )
    stock_code_count = _positive_int(
        "history_result.stock_code_count",
        history_result.get("stock_code_count"),
    )
    landed_row_count = _positive_int(
        "daily_observation_row_count",
        daily_observation_row_count,
    )
    normalized_refresh_run_id = _required_text("refresh_run_id", refresh_run_id)
    created_at_value = _utc_datetime_or_now(created_at)
    if created_at_value.date() < date.fromisoformat(normalized_report_date):
        raise ValueError("created_at must not be before report_date")
    created_at_text = created_at_value.isoformat().replace("+00:00", "Z")

    return CacheManifestRecord(
        cache_key=CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        cache_version=CHOICE_STOCK_OBSERVATION_CACHE_VERSION,
        source_version=source_version,
        vendor_version=vendor_version,
        rule_version=CHOICE_STOCK_OBSERVATION_RULE_VERSION,
        basis="observational",
        module_name="choice_stock",
        result_kind_family="choice-stock-observation",
        run_id=normalized_refresh_run_id,
        report_date=normalized_report_date,
        input_sources=["choice_stock_materialization"],
        fact_tables=["choice_stock_daily_observation"],
        lineage={
            "materialization_run_id": materialization_run_id,
            "refresh_run_id": normalized_refresh_run_id,
            "materialization_status": "completed",
            "daily_observation_report_date": normalized_report_date,
            "daily_observation_row_count": landed_row_count,
            "materialized_row_count": materialized_row_count,
            "stock_code_count": stock_code_count,
        },
        created_at=created_at_text,
    ).model_dump()


def verify_choice_stock_daily_observation_landing(
    *,
    duckdb_path: str | Path,
    history_result: Mapping[str, object],
    report_date: str,
) -> int:
    """Return the target-day row count only when it matches the committed materialization lineage."""
    path = Path(duckdb_path)
    if not path.is_file():
        raise ValueError(f"Choice-stock DuckDB does not exist: {path}")
    normalized_report_date = _iso_date("report_date", report_date)
    materialization_run_id = _required_text("history_result.run_id", history_result.get("run_id"))
    source_version = _required_text("history_result.source_version", history_result.get("source_version"))
    vendor_version = _daily_landing_vendor_version(history_result)

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if "choice_stock_daily_observation" not in tables:
            raise ValueError("choice_stock_daily_observation is not landed")
        columns = {
            str(row[1]).lower()
            for row in conn.execute("pragma table_info('choice_stock_daily_observation')").fetchall()
        }
        required = {
            "trade_date",
            "source_version",
            "vendor_version",
            "rule_version",
            "run_id",
        }
        missing = sorted(required - columns)
        if missing:
            raise ValueError(f"choice_stock_daily_observation missing columns: {','.join(missing)}")
        row = conn.execute(
            """
            select count(*)::bigint
            from choice_stock_daily_observation
            where try_cast(trade_date as date) = cast(? as date)
              and source_version = ?
              and vendor_version = ?
              and rule_version = ?
              and run_id = ?
            """,
            [
                normalized_report_date,
                source_version,
                vendor_version,
                CHOICE_STOCK_OBSERVATION_RULE_VERSION,
                materialization_run_id,
            ],
        ).fetchone()
    finally:
        conn.close()
    row_count = int(row[0] or 0) if row else 0
    if row_count <= 0:
        raise ValueError("No matching choice-stock daily observations were landed")
    return row_count


def resolve_latest_committed_choice_stock_observation(
    *,
    duckdb_path: str | Path,
    expected_report_date: str,
) -> ChoiceStockCommittedObservation:
    """Resolve the latest daily landing only when one completed run proves its lineage."""
    path = Path(duckdb_path)
    if not path.is_file():
        raise ValueError(f"Choice-stock DuckDB does not exist: {path}")
    expected_date = _iso_date("expected_report_date", expected_report_date)

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        required_tables = {
            "choice_stock_daily_observation",
            "choice_stock_materialize_run",
        }
        missing_tables = sorted(required_tables - tables)
        if missing_tables:
            raise ValueError(f"Choice-stock landing missing tables: {','.join(missing_tables)}")
        _require_table_columns(
            conn,
            table="choice_stock_daily_observation",
            required={
                "trade_date",
                "stock_code",
                "pctchange",
                "source_version",
                "vendor_version",
                "rule_version",
                "run_id",
            },
        )
        _require_table_columns(
            conn,
            table="choice_stock_materialize_run",
            required={
                "run_id",
                "as_of_date",
                "status",
                "source_version",
                "vendor_version",
                "rule_version",
                "row_count",
            },
        )

        latest_row = conn.execute(
            "select max(try_cast(trade_date as date)) from choice_stock_daily_observation"
        ).fetchone()
        if latest_row is None or latest_row[0] is None:
            raise ValueError("Choice-stock daily observations are empty")
        latest_date = latest_row[0].isoformat()
        if expected_date != latest_date:
            raise ValueError(f"expected_report_date must equal the latest daily observation date {latest_date}")

        lineage_rows = conn.execute(
            """
            select
              source_version,
              vendor_version,
              rule_version,
              run_id,
              count(*)::bigint,
              count(distinct nullif(upper(trim(stock_code)), ''))::bigint,
              sum(case when nullif(trim(stock_code), '') is null then 1 else 0 end)::bigint
            from choice_stock_daily_observation
            where try_cast(trade_date as date) = cast(? as date)
            group by source_version, vendor_version, rule_version, run_id
            """,
            [expected_date],
        ).fetchall()
        if len(lineage_rows) != 1:
            raise ValueError("Latest choice-stock daily observations must have one unique lineage tuple")
        lineage = lineage_rows[0]
        source_version = _required_text("daily.source_version", lineage[0])
        vendor_version = _required_text("daily.vendor_version", lineage[1])
        rule_version = _required_text("daily.rule_version", lineage[2])
        materialization_run_id = _required_text("daily.run_id", lineage[3])
        if rule_version != CHOICE_STOCK_OBSERVATION_RULE_VERSION:
            raise ValueError("Latest choice-stock daily observation rule_version is unsupported")
        daily_row_count = _positive_int("daily row_count", lineage[4])
        stock_code_count = _positive_int("daily distinct stock count", lineage[5])
        if _nonnegative_int("daily blank stock count", lineage[6]) != 0:
            raise ValueError("Latest choice-stock daily observations contain blank stock codes")

        run_rows = conn.execute(
            """
            select
              as_of_date,
              status,
              source_version,
              vendor_version,
              rule_version,
              row_count
            from choice_stock_materialize_run
            where run_id = ?
            """,
            [materialization_run_id],
        ).fetchall()
        if len(run_rows) != 1 or (
            _iso_date("materialization_run.as_of_date", run_rows[0][0]) != expected_date
            or _required_text("materialization_run.status", run_rows[0][1]) != "completed"
            or _required_text(
                "materialization_run.source_version",
                run_rows[0][2],
            )
            != source_version
            or not _daily_vendor_matches_run_vendor(
                daily_vendor=vendor_version,
                run_vendor=_required_text(
                    "materialization_run.vendor_version",
                    run_rows[0][3],
                ),
            )
            or _required_text(
                "materialization_run.rule_version",
                run_rows[0][4],
            )
            != rule_version
        ):
            raise ValueError(
                "Latest choice-stock daily lineage requires exactly one matching completed materialization run"
            )
        materialized_row_count = _positive_int(
            "materialized row_count",
            run_rows[0][5],
        )
        if materialized_row_count < daily_row_count:
            raise ValueError("materialized row_count cannot be smaller than daily row_count")

        daily_rows = conn.execute(
            """
            select trade_date, upper(trim(stock_code)), pctchange
            from choice_stock_daily_observation
            where try_cast(trade_date as date) = cast(? as date)
            order by upper(trim(stock_code)), pctchange desc nulls last
            """,
            [expected_date],
        ).fetchall()
    finally:
        conn.close()

    daily_by_key = {
        (expected_date, str(stock_code)): {
            "trade_date": expected_date,
            "stock_code": str(stock_code),
            "pctchange": pctchange,
        }
        for _trade_date, stock_code, pctchange in daily_rows
    }
    if len(daily_by_key) != daily_row_count:
        raise ValueError("Latest choice-stock daily observations contain duplicate stock rows")
    return ChoiceStockCommittedObservation(
        report_date=expected_date,
        materialization_run_id=materialization_run_id,
        source_version=source_version,
        vendor_version=vendor_version,
        rule_version=rule_version,
        materialized_row_count=materialized_row_count,
        daily_observation_row_count=daily_row_count,
        stock_code_count=stock_code_count,
        daily_by_key=daily_by_key,
    )


def ensure_choice_stock_observation_manifest(
    *,
    governance_repo: GovernanceRepository | None,
    observation: ChoiceStockCommittedObservation,
    created_at: str | datetime,
    publish: bool,
) -> tuple[dict[str, object], bool]:
    """Return an exact landing anchor and optionally publish it monotonically."""
    created_at_limit = _required_utc_datetime("created_at", created_at)
    run_digest = hashlib.sha256(observation.materialization_run_id.encode("utf-8")).hexdigest()[:12]
    manifest = build_choice_stock_observation_manifest(
        history_result={
            "status": "completed",
            "run_id": observation.materialization_run_id,
            "as_of_date": observation.report_date,
            "row_count": observation.materialized_row_count,
            "stock_code_count": observation.stock_code_count,
            "source_version": observation.source_version,
            "vendor_version": observation.vendor_version,
        },
        refresh_run_id=(f"choice_stock_observation_repair:{observation.report_date}:{run_digest}"),
        report_date=observation.report_date,
        daily_observation_row_count=observation.daily_observation_row_count,
        created_at=created_at,
    )
    if not publish:
        return manifest, False
    if governance_repo is None:
        raise ValueError("governance_repo is required when publish is enabled")

    appended, selected = _append_with_observation_manifest_lock(
        governance_repo=governance_repo,
        entries=(),
        observation_manifest=manifest,
        equivalent=lambda value: _manifest_matches_observation(
            value,
            observation,
            not_after=created_at_limit,
        ),
    )
    if selected is not None and _manifest_matches_observation(
        selected,
        observation,
        not_after=created_at_limit,
    ):
        return dict(selected), appended
    if (
        selected is not None
        and _iso_date(
            "latest_manifest.report_date",
            selected.get("report_date"),
        )
        > observation.report_date
    ):
        raise ValueError("A newer observation manifest already exists; refusing date regression")
    raise ValueError("The exact committed choice-stock observation manifest was not published")


def append_choice_stock_refresh_completion(
    *,
    governance_repo: GovernanceRepository,
    completed_run_payload: Mapping[str, object],
    observation_manifest: Mapping[str, object] | None,
) -> bool:
    """Atomically append completion and advance the latest observation anchor without date regression."""
    if _required_text("completed_run_payload.status", completed_run_payload.get("status")) != "completed":
        raise ValueError("completed_run_payload must have completed status")
    completed_run_id = _required_text(
        "completed_run_payload.run_id",
        completed_run_payload.get("run_id"),
    )
    completed_report_date = _iso_date(
        "completed_run_payload.report_date",
        completed_run_payload.get("report_date"),
    )
    _require_expected_text(
        "completed_run_payload.cache_key",
        completed_run_payload.get("cache_key"),
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
    )
    _require_expected_text(
        "completed_run_payload.cache_version",
        completed_run_payload.get("cache_version"),
        CHOICE_STOCK_OBSERVATION_CACHE_VERSION,
    )
    _require_expected_text(
        "completed_run_payload.rule_version",
        completed_run_payload.get("rule_version"),
        CHOICE_STOCK_OBSERVATION_RULE_VERSION,
    )

    refresh_history = completed_run_payload.get("refresh_history")
    if observation_manifest is None:
        if refresh_history is not False:
            raise ValueError("History refresh completion requires an observation manifest")
        normalized_manifest = None
    else:
        if refresh_history is False:
            raise ValueError("Factor-only refresh must not publish an observation manifest")
        normalized_manifest = _validate_observation_manifest_pair(
            observation_manifest,
            completed_run_id=completed_run_id,
            completed_report_date=completed_report_date,
        )

    append_manifest, _selected = _append_with_observation_manifest_lock(
        governance_repo=governance_repo,
        entries=((CACHE_BUILD_RUN_STREAM, dict(completed_run_payload)),),
        observation_manifest=normalized_manifest,
    )
    return append_manifest


@contextmanager
def choice_stock_observation_manifest_guard(
    *,
    governance_repo: GovernanceRepository,
    expected_manifest: Mapping[str, object] | None = None,
) -> Iterator[Mapping[str, object] | None]:
    """Hold observation authority while optionally asserting the exact manifest."""
    with acquire_lock(
        CHOICE_STOCK_OBSERVATION_MANIFEST_LOCK,
        base_dir=_observation_manifest_lock_base(governance_repo),
        timeout_seconds=10.0,
    ):
        latest = governance_repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)
        if expected_manifest is not None:
            require_exact_choice_stock_observation_manifest(
                actual_manifest=latest,
                expected_manifest=expected_manifest,
            )
        yield latest


def _append_with_observation_manifest_lock(
    *,
    governance_repo: GovernanceRepository,
    entries: Sequence[tuple[str, dict[str, object]]],
    observation_manifest: dict[str, object] | None,
    equivalent: Callable[[Mapping[str, object]], bool] | None = None,
) -> tuple[bool, Mapping[str, object] | None]:
    with choice_stock_observation_manifest_guard(governance_repo=governance_repo) as latest:
        append_manifest = observation_manifest is not None
        if observation_manifest is not None and latest is not None:
            append_manifest = (
                False
                if equivalent is not None and equivalent(latest)
                else _manifest_order_key(observation_manifest) > _manifest_order_key(latest)
            )
        payloads = list(entries)
        if append_manifest and observation_manifest is not None:
            payloads.append((CACHE_MANIFEST_STREAM, observation_manifest))
        if payloads:
            governance_repo.append_many_atomic(payloads)
        selected = observation_manifest if append_manifest else latest
        return append_manifest, selected


def normalize_choice_stock_observation_manifest(
    manifest_payload: Mapping[str, object],
) -> dict[str, object]:
    manifest = CacheManifestRecord.model_validate(dict(manifest_payload)).model_dump(mode="json")
    _require_expected_text(
        "observation_manifest.cache_key",
        manifest.get("cache_key"),
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
    )
    return manifest


def require_exact_choice_stock_observation_manifest(
    *,
    actual_manifest: Mapping[str, object] | None,
    expected_manifest: Mapping[str, object],
) -> dict[str, object]:
    try:
        expected = normalize_choice_stock_observation_manifest(expected_manifest)
        actual = normalize_choice_stock_observation_manifest(actual_manifest) if actual_manifest is not None else None
    except (TypeError, ValueError) as exc:
        raise ChoiceStockObservationManifestChangedError(
            f"Choice-stock observation manifest is invalid: {exc}"
        ) from exc
    if actual != expected:
        raise ChoiceStockObservationManifestChangedError(
            "Choice-stock observation manifest does not exactly match expected"
        )
    return actual


def _validate_observation_manifest_pair(
    manifest_payload: Mapping[str, object],
    *,
    completed_run_id: str,
    completed_report_date: str,
) -> dict[str, object]:
    manifest = CacheManifestRecord.model_validate(dict(manifest_payload)).model_dump()
    _require_expected_text(
        "observation_manifest.cache_key",
        manifest.get("cache_key"),
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
    )
    _require_expected_text(
        "observation_manifest.cache_version",
        manifest.get("cache_version"),
        CHOICE_STOCK_OBSERVATION_CACHE_VERSION,
    )
    _require_expected_text(
        "observation_manifest.rule_version",
        manifest.get("rule_version"),
        CHOICE_STOCK_OBSERVATION_RULE_VERSION,
    )
    if manifest.get("fact_tables") != ["choice_stock_daily_observation"]:
        raise ValueError("Observation manifest must anchor choice_stock_daily_observation")
    manifest_run_id = _required_text("observation_manifest.run_id", manifest.get("run_id"))
    manifest_report_date = _iso_date(
        "observation_manifest.report_date",
        manifest.get("report_date"),
    )
    if manifest_run_id != completed_run_id:
        raise ValueError("Completion and observation manifest run_id do not match")
    if manifest_report_date != completed_report_date:
        raise ValueError("Completion and observation manifest report_date do not match")

    _required_text("observation_manifest.source_version", manifest.get("source_version"))
    _required_text("observation_manifest.vendor_version", manifest.get("vendor_version"))
    created_at = _required_utc_datetime(
        "observation_manifest.created_at",
        manifest.get("created_at"),
    )
    if created_at.date() < date.fromisoformat(manifest_report_date):
        raise ValueError("Observation manifest created_at must not be before report_date")

    lineage = manifest.get("lineage")
    if not isinstance(lineage, Mapping):
        raise ValueError("Observation manifest lineage is required")
    _required_text("observation_manifest.lineage.materialization_run_id", lineage.get("materialization_run_id"))
    _require_expected_text(
        "observation_manifest.lineage.refresh_run_id",
        lineage.get("refresh_run_id"),
        completed_run_id,
    )
    _require_expected_text(
        "observation_manifest.lineage.materialization_status",
        lineage.get("materialization_status"),
        "completed",
    )
    lineage_report_date = _iso_date(
        "observation_manifest.lineage.daily_observation_report_date",
        lineage.get("daily_observation_report_date"),
    )
    if lineage_report_date != completed_report_date:
        raise ValueError("Observation lineage report_date does not match completion")
    for field_name in (
        "daily_observation_row_count",
        "materialized_row_count",
        "stock_code_count",
    ):
        _positive_int(
            f"observation_manifest.lineage.{field_name}",
            lineage.get(field_name),
        )
    return manifest


def _manifest_matches_observation(
    manifest_payload: Mapping[str, object],
    observation: ChoiceStockCommittedObservation,
    *,
    not_after: datetime | None = None,
) -> bool:
    try:
        manifest = CacheManifestRecord.model_validate(dict(manifest_payload)).model_dump()
        _require_expected_text(
            "manifest.cache_key",
            manifest.get("cache_key"),
            CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        )
        _require_expected_text(
            "manifest.cache_version",
            manifest.get("cache_version"),
            CHOICE_STOCK_OBSERVATION_CACHE_VERSION,
        )
        _require_expected_text(
            "manifest.rule_version",
            manifest.get("rule_version"),
            CHOICE_STOCK_OBSERVATION_RULE_VERSION,
        )
        if manifest.get("fact_tables") != ["choice_stock_daily_observation"]:
            return False
        if _iso_date("manifest.report_date", manifest.get("report_date")) != observation.report_date:
            return False
        if _required_text("manifest.source_version", manifest.get("source_version")) != observation.source_version:
            return False
        if _required_text("manifest.vendor_version", manifest.get("vendor_version")) != observation.vendor_version:
            return False
        manifest_run_id = _required_text("manifest.run_id", manifest.get("run_id"))
        manifest_created_at = _required_utc_datetime("manifest.created_at", manifest.get("created_at"))
        if manifest_created_at.date() < date.fromisoformat(observation.report_date):
            return False
        if not_after is not None and manifest_created_at > not_after:
            return False
        lineage = manifest.get("lineage")
        if not isinstance(lineage, Mapping):
            return False
        if _required_text("manifest.lineage.refresh_run_id", lineage.get("refresh_run_id")) != manifest_run_id:
            return False
        expected = {
            "materialization_run_id": observation.materialization_run_id,
            "materialization_status": "completed",
            "daily_observation_report_date": observation.report_date,
            "daily_observation_row_count": observation.daily_observation_row_count,
            "materialized_row_count": observation.materialized_row_count,
            "stock_code_count": observation.stock_code_count,
        }
        return all(lineage.get(key) == value for key, value in expected.items())
    except (TypeError, ValueError):
        return False


# daily observation 行按 OHLCV 实际来源打标(materialize 任务的 daily_vendor_version),
# run 级 vendor_version 记录整个 run 是否发生过任何 fallback,两者前缀可分叉但共享
# 同一 "_{yyyymmdd}_{hash}" 后缀以证明同一 run 血缘。
_MAIN_VENDOR_LINEAGE_RE = re.compile(r"^vv_choice(?:_tushare)?_stock_(\d{8}_[0-9a-f]{12})$")


def _daily_landing_vendor_version(history_result: Mapping[str, object]) -> str:
    """落地验证/manifest 使用 daily 行的实际 vendor;旧 payload 无该键时回退 run 级 vendor。"""
    daily_vendor = str(history_result.get("daily_vendor_version") or "").strip()
    if daily_vendor:
        return daily_vendor
    return _required_text("history_result.vendor_version", history_result.get("vendor_version"))


def _daily_vendor_matches_run_vendor(*, daily_vendor: str, run_vendor: str) -> bool:
    if daily_vendor == run_vendor:
        return True
    daily_match = _MAIN_VENDOR_LINEAGE_RE.match(daily_vendor)
    run_match = _MAIN_VENDOR_LINEAGE_RE.match(run_vendor)
    return daily_match is not None and run_match is not None and daily_match.group(1) == run_match.group(1)


def _require_table_columns(
    conn: duckdb.DuckDBPyConnection,
    *,
    table: str,
    required: set[str],
) -> None:
    columns = {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{table}')").fetchall()}
    missing = sorted(required - columns)
    if missing:
        raise ValueError(f"{table} missing columns: {','.join(missing)}")


def _observation_manifest_lock_base(governance_repo: GovernanceRepository) -> Path:
    if governance_repo.backend_mode == "jsonl":
        return governance_repo.base_dir
    authority = _required_text("governance_repo.sql_dsn", governance_repo.sql_dsn)
    digest = hashlib.sha256(authority.encode("utf-8")).hexdigest()[:24]
    return Path(tempfile.gettempdir()) / "moss-governance-authority-locks" / digest


def _manifest_order_key(manifest: Mapping[str, object]) -> tuple[str, datetime, str, str, str]:
    return (
        _iso_date("manifest.report_date", manifest.get("report_date")),
        _required_utc_datetime("manifest.created_at", manifest.get("created_at")),
        _required_text("manifest.source_version", manifest.get("source_version")),
        _required_text("manifest.vendor_version", manifest.get("vendor_version")),
        _required_text("manifest.run_id", manifest.get("run_id")),
    )


def _require_expected_text(field_name: str, value: object, expected: str) -> None:
    if _required_text(field_name, value) != expected:
        raise ValueError(f"{field_name} must equal {expected}")


def _required_text(field_name: str, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be blank")
    return text


def _iso_date(field_name: str, value: object) -> str:
    text = _required_text(field_name, value)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc


def _positive_int(field_name: str, value: object) -> int:
    normalized = _nonnegative_int(field_name, value)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive")
    return normalized


def _nonnegative_int(field_name: str, value: object) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    try:
        normalized = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if normalized < 0:
        raise ValueError(f"{field_name} must be nonnegative")
    return normalized


def _required_utc_datetime(field_name: str, value: object) -> datetime:
    if value is None:
        raise ValueError(f"{field_name} must not be blank")
    try:
        return _utc_datetime_or_now(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a timezone-aware ISO-8601 timestamp") from exc


def _utc_datetime_or_now(value: object | None) -> datetime:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, datetime):
        parsed = value
    else:
        text = _required_text("created_at", value)
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("created_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    return parsed.astimezone(UTC)
