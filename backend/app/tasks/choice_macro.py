from __future__ import annotations

import dramatiq
import duckdb
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from backend.app.config.choice_runtime import _init_runtime
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_adapter import VendorAdapter
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    VENDOR_SNAPSHOT_MANIFEST_STREAM,
    VENDOR_VERSION_REGISTRY_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.object_store_repo import ObjectStoreRepository
from backend.app.schemas.macro_vendor import (
    ChoiceMacroBatchConfig,
    ChoiceMacroCatalogAsset,
    ChoiceMacroSeriesConfig,
    ChoiceMacroSnapshot,
)
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.tasks.build_runs import BuildRunRecord


CHOICE_MACRO_LOCK = LockDefinition(key="lock:duckdb:choice-macro", ttl_seconds=900)
RULE_VERSION = "rv_choice_macro_thin_slice_v1"
STABLE_DATE_SLICE_LOOKBACK_DAYS = 7


@dramatiq.actor
def refresh_choice_macro_snapshot(
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
) -> dict[str, object]:
    _init_runtime()
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    repo = GovernanceRepository(base_dir=governance_path)
    object_store = ObjectStoreRepository(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        mode=settings.object_store_mode,
        local_archive_path=str(settings.local_archive_path),
    )

    run = BuildRunRecord(
        job_name="choice_macro_refresh",
        status="running",
        cache_key="choice_macro.latest",
    )
    run_id = f"{run.job_name}:{run.created_at}"
    source_version = "sv_choice_macro_pending"
    vendor_version = "vv_none"

    try:
        batches = load_choice_macro_batches(settings)
        series_registry = _build_choice_series_registry(batches)
        fetch_plan = _build_choice_macro_fetch_plan(batches)

        adapter = VendorAdapter()
        batch_snapshots: list[ChoiceMacroSnapshot] = []
        for batch in fetch_plan:
            try:
                snapshot = _fetch_choice_macro_batch_snapshot(
                    adapter=adapter,
                    batch=batch,
                    timeout_seconds=settings.choice_timeout_seconds,
                )
            except RuntimeError as exc:
                if _is_choice_no_data_error(exc):
                    continue
                raise
            batch_snapshots.append(snapshot)
        snapshot = merge_choice_macro_snapshots(batch_snapshots)
        vendor_version = snapshot.vendor_version
        source_version = _build_source_version(snapshot.raw_payload)

        archived = object_store.archive_bytes(
            payload=json.dumps(snapshot.raw_payload, ensure_ascii=False).encode("utf-8"),
            source_name="choice-macro",
            source_key=f"choice/macro/{snapshot.vendor_version}.json",
            ingest_batch_id=run_id.replace(":", "_"),
        )
        vendor_snapshot_manifest = object_store.build_vendor_snapshot_manifest(
            vendor_name=snapshot.vendor_name,
            vendor_version=snapshot.vendor_version,
            archived_path=str(archived["archived_path"]),
            snapshot_kind="macro",
            capture_mode="live",
        )
        vendor_version_registry = {
            "vendor_name": snapshot.vendor_name,
            "vendor_version": snapshot.vendor_version,
            "source_version": source_version,
            "run_id": run_id,
            "registered_at": run.created_at,
        }

        with acquire_lock(CHOICE_MACRO_LOCK, base_dir=duckdb_file.parent):
            conn = duckdb.connect(str(duckdb_file), read_only=False)
            try:
                _ensure_tables(conn)
                conn.execute("begin transaction")
                conn.execute("delete from choice_market_snapshot")
                conn.execute("delete from fact_choice_macro_daily")
                conn.execute("delete from phase1_macro_vendor_catalog")

                for point in snapshot.series:
                    conn.execute(
                        """
                        insert into choice_market_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            point.series_id,
                            point.series_name,
                            point.vendor_series_code,
                            point.vendor_name,
                            point.trade_date,
                            point.value_numeric,
                            point.frequency,
                            point.unit,
                            source_version,
                            point.vendor_version,
                            RULE_VERSION,
                            run_id,
                        ],
                    )
                    conn.execute(
                        """
                        insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            point.series_id,
                            point.series_name,
                            point.trade_date,
                            point.value_numeric,
                            point.frequency,
                            point.unit,
                            source_version,
                            point.vendor_version,
                            RULE_VERSION,
                            "ok",
                            run_id,
                        ],
                    )
                point_vendor_versions = {
                    point.series_id: point.vendor_version
                    for point in snapshot.series
                }
                for series_id in sorted(series_registry):
                    registry_entry = series_registry[series_id]
                    conn.execute(
                        """
                        insert into phase1_macro_vendor_catalog (
                          series_id,
                          series_name,
                          vendor_name,
                          vendor_version,
                          frequency,
                          unit,
                          vendor_series_code,
                          batch_id,
                          catalog_version,
                          theme,
                          is_core,
                          tags_json,
                          request_options,
                          fetch_mode,
                          fetch_granularity,
                          refresh_tier,
                          policy_note
                        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            series_id,
                            str(registry_entry["series_name"]),
                            str(registry_entry["vendor_name"]),
                            str(point_vendor_versions.get(series_id, snapshot.vendor_version)),
                            str(registry_entry["frequency"]),
                            str(registry_entry["unit"]),
                            str(registry_entry["vendor_series_code"]),
                            str(registry_entry["batch_id"]),
                            registry_entry["catalog_version"],
                            str(registry_entry["theme"]),
                            bool(registry_entry["is_core"]),
                            str(registry_entry["tags_json"]),
                            str(registry_entry["request_options"]),
                            str(registry_entry["fetch_mode"]),
                            str(registry_entry["fetch_granularity"]),
                            str(registry_entry["refresh_tier"]),
                            registry_entry["policy_note"],
                        ],
                    )
                conn.execute("commit")
            except Exception:
                conn.execute("rollback")
                raise
            finally:
                conn.close()

        repo.append_many_atomic(
            [
                (
                    VENDOR_SNAPSHOT_MANIFEST_STREAM,
                    vendor_snapshot_manifest,
                ),
                (
                    VENDOR_VERSION_REGISTRY_STREAM,
                    vendor_version_registry,
                ),
                (
                    CACHE_MANIFEST_STREAM,
                    CacheManifestRecord(
                        cache_key=run.cache_key,
                        source_version=source_version,
                        vendor_version=snapshot.vendor_version,
                        rule_version=RULE_VERSION,
                    ).model_dump(),
                ),
                (
                    CACHE_BUILD_RUN_STREAM,
                    CacheBuildRunRecord(
                        run_id=run_id,
                        job_name=run.job_name,
                        status="completed",
                        cache_key=run.cache_key,
                        lock=CHOICE_MACRO_LOCK.key,
                        source_version=source_version,
                        vendor_version=snapshot.vendor_version,
                    ).model_dump(),
                ),
            ]
        )
    except Exception as exc:
        failed_run = CacheBuildRunRecord(
            run_id=run_id,
            job_name=run.job_name,
            status="failed",
            cache_key=run.cache_key,
            lock=CHOICE_MACRO_LOCK.key,
            source_version=source_version,
            vendor_version=vendor_version,
        )
        try:
            repo.append(CACHE_BUILD_RUN_STREAM, failed_run.model_dump())
        except Exception as append_error:
            raise RuntimeError("Failed to append failed choice_macro lineage") from append_error
        raise exc

    return {
        "status": "completed",
        "run_id": run_id,
        "series_count": len(snapshot.series),
        "vendor_version": snapshot.vendor_version,
        "source_version": source_version,
        "cache_key": run.cache_key,
    }


def _build_source_version(raw_payload: dict[str, object]) -> str:
    digest = hashlib.sha256(
        json.dumps(raw_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"sv_choice_macro_{digest}"


def load_choice_macro_batches(settings) -> list[ChoiceMacroBatchConfig]:
    run_date = _choice_macro_run_date()
    catalog_path = _resolve_choice_macro_catalog_path(settings)
    if catalog_path is not None and catalog_path.exists():
        return _normalize_choice_macro_batches(
            load_choice_macro_batches_from_catalog(catalog_path),
            run_date=run_date,
        )

    if settings.choice_macro_commands_file:
        return _normalize_choice_macro_batches(
            load_choice_macro_batches_from_file(Path(settings.choice_macro_commands_file)),
            run_date=run_date,
        )

    series = [
        ChoiceMacroSeriesConfig(**item)
        for item in json.loads(settings.choice_macro_series_json or "[]")
    ]
    return _normalize_choice_macro_batches(
        [
            ChoiceMacroBatchConfig(
                batch_id="default",
                request_options="IsPublishDate=1,RowIndex=1,Ispandas=1,RECVtimeout=5",
                series=series,
            )
        ],
        run_date=run_date,
    )


def load_choice_macro_batches_from_catalog(path: Path) -> list[ChoiceMacroBatchConfig]:
    asset = ChoiceMacroCatalogAsset.model_validate_json(path.read_text(encoding="utf-8"))
    return [
        ChoiceMacroBatchConfig(
            batch_id=batch.batch_id,
            request_options=_serialize_choice_request_options(batch.request_options),
            series=batch.series,
            catalog_version=asset.catalog_version,
            fetch_mode=batch.fetch_mode,
            fetch_granularity=batch.fetch_granularity,
            refresh_tier=batch.refresh_tier,
            policy_note=batch.policy_note,
        )
        for batch in asset.batches
    ]


def load_choice_macro_batches_from_file(path: Path) -> list[ChoiceMacroBatchConfig]:
    lines = path.read_text(encoding="utf-8").splitlines()
    batches: list[ChoiceMacroBatchConfig] = []
    current_metadata: dict[str, str] = {}
    current_batch_id = ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            current_batch_id, current_metadata = _parse_choice_batch_comment(line)
            continue
        if line.startswith("data=c.edb("):
            codes, options = _parse_choice_edb_command(line)
            batches.append(
                ChoiceMacroBatchConfig(
                    batch_id=current_batch_id or f"batch{len(batches)+1}",
                    request_options=options,
                    series=[
                        ChoiceMacroSeriesConfig(
                            series_id=code,
                            series_name=current_metadata.get(code, code),
                            vendor_series_code=code,
                            frequency="unknown",
                            unit="unknown",
                            theme="unknown",
                            is_core=False,
                            tags=[],
                        )
                        for code in codes
                    ],
                )
            )
    return batches


def _parse_choice_batch_comment(line: str) -> tuple[str, dict[str, str]]:
    content = line.lstrip("#").strip()
    if " " not in content:
        return content, {}
    batch_id, remainder = content.split(" ", 1)
    mapping: dict[str, str] = {}
    for part in remainder.split(","):
        item = part.strip()
        if not item:
            continue
        code, _, name = item.partition(" ")
        mapping[code.strip()] = name.strip() or code.strip()
    return batch_id.strip(), mapping


def _parse_choice_edb_command(line: str) -> tuple[list[str], str]:
    prefix = 'data=c.edb("'
    mid = '", "'
    suffix = '")'
    codes_part = line[len(prefix):]
    codes_text, _, options_text = codes_part.partition(mid)
    options = options_text[:-len(suffix)] if options_text.endswith(suffix) else options_text
    codes = [code.strip() for code in codes_text.split(",") if code.strip()]
    return codes, options


def _resolve_choice_macro_catalog_path(settings) -> Path | None:
    if not getattr(settings, "choice_macro_catalog_file", ""):
        return None
    return Path(settings.choice_macro_catalog_file)


def _normalize_choice_macro_batches(
    batches: list[ChoiceMacroBatchConfig],
    run_date: str,
) -> list[ChoiceMacroBatchConfig]:
    return [
        batch.model_copy(
            update={
                "request_options": _normalize_choice_batch_request_options(batch, run_date=run_date),
            }
        )
        for batch in batches
    ]


def _normalize_choice_batch_request_options(batch: ChoiceMacroBatchConfig, run_date: str) -> str:
    batch_id = batch.batch_id.strip().lower()
    if batch.fetch_mode == "latest" or batch_id in {"cmd2", "catalog_cmd2"}:
        return "IsLatest=1,RowIndex=1,Ispandas=1,RECVtimeout=5"
    request_options = batch.request_options or "IsPublishDate=1,RowIndex=1,Ispandas=1,RECVtimeout=5"
    return request_options.replace("__RUN_DATE__", run_date)


def _fetch_choice_macro_batch_snapshot(
    adapter: VendorAdapter,
    batch: ChoiceMacroBatchConfig,
    timeout_seconds: float,
) -> ChoiceMacroSnapshot:
    last_error: RuntimeError | None = None
    for request_options in _iter_choice_batch_request_options(batch):
        try:
            return adapter.fetch_macro_snapshot(
                series=batch.series,
                timeout_seconds=timeout_seconds,
                request_options=request_options,
            )
        except RuntimeError as exc:
            if not _is_choice_no_data_error(exc):
                raise
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise RuntimeError("Choice batch fetch produced no attempts.")


def _iter_choice_batch_request_options(batch: ChoiceMacroBatchConfig) -> list[str]:
    if not _should_retry_previous_trading_day(batch):
        return [batch.request_options]

    parsed = _parse_choice_request_options_string(batch.request_options)
    start_date = parsed.get("StartDate")
    end_date = parsed.get("EndDate")
    if not start_date or not end_date or start_date != end_date:
        return [batch.request_options]

    base_date = date.fromisoformat(start_date)
    return [
        _replace_choice_date_range(batch.request_options, base_date - timedelta(days=offset))
        for offset in range(STABLE_DATE_SLICE_LOOKBACK_DAYS + 1)
    ]


def _should_retry_previous_trading_day(batch: ChoiceMacroBatchConfig) -> bool:
    return batch.refresh_tier == "stable" and batch.fetch_mode == "date_slice"


def _is_choice_no_data_error(exc: RuntimeError) -> bool:
    text = str(exc).lower()
    return "no data" in text or "no rows" in text


def _parse_choice_request_options_string(request_options: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in request_options.split(","):
        item = part.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _replace_choice_date_range(request_options: str, target_date: date) -> str:
    target_text = target_date.isoformat()
    parts: list[str] = []
    for part in request_options.split(","):
        item = part.strip()
        if item.startswith("StartDate="):
            parts.append(f"StartDate={target_text}")
            continue
        if item.startswith("EndDate="):
            parts.append(f"EndDate={target_text}")
            continue
        parts.append(item)
    return ",".join(parts)


def _build_choice_macro_fetch_plan(
    batches: list[ChoiceMacroBatchConfig],
) -> list[ChoiceMacroBatchConfig]:
    plan: list[ChoiceMacroBatchConfig] = []
    for batch in batches:
        batch_id = batch.batch_id.strip().lower()
        if batch.refresh_tier == "isolated":
            continue
        if batch.fetch_granularity == "single" or batch_id in {"cmd2", "catalog_cmd2"}:
            for series in batch.series:
                plan.append(
                    batch.model_copy(
                        update={
                            "series": [series],
                        }
                    )
                )
            continue
        plan.append(batch)
    return plan


def _serialize_choice_request_options(options: dict[str, object]) -> str:
    return ",".join(
        f"{key}={_serialize_choice_request_option_value(value)}"
        for key, value in options.items()
    )


def _serialize_choice_request_option_value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _choice_macro_run_date() -> str:
    return date.today().isoformat()


def _build_choice_series_registry(
    batches: list[ChoiceMacroBatchConfig],
) -> dict[str, dict[str, object]]:
    registry: dict[str, dict[str, object]] = {}
    for batch in batches:
        for series in batch.series:
            registry[series.series_id] = {
                "series_name": series.series_name,
                "vendor_name": "choice",
                "frequency": series.frequency,
                "unit": series.unit,
                "vendor_series_code": series.vendor_series_code,
                "batch_id": batch.batch_id,
                "catalog_version": batch.catalog_version,
                "theme": series.theme,
                "is_core": series.is_core,
                "tags_json": json.dumps(series.tags, ensure_ascii=False, separators=(",", ":")),
                "request_options": batch.request_options,
                "fetch_mode": batch.fetch_mode,
                "fetch_granularity": batch.fetch_granularity,
                "refresh_tier": batch.refresh_tier,
                "policy_note": batch.policy_note,
            }
    return registry


def merge_choice_macro_snapshots(snapshots: list[ChoiceMacroSnapshot]) -> ChoiceMacroSnapshot:
    if not snapshots:
        raise ValueError("No Choice macro snapshots were fetched.")
    if len(snapshots) == 1:
        return snapshots[0]

    series = []
    raw_batches = []
    vendor_versions = []
    captured_at = snapshots[0].captured_at
    for snapshot in snapshots:
        series.extend(
            [
                point.model_dump(mode="json") if hasattr(point, "model_dump") else point
                for point in snapshot.series
            ]
        )
        raw_batches.append(snapshot.raw_payload)
        vendor_versions.append(snapshot.vendor_version)
        if snapshot.captured_at > captured_at:
            captured_at = snapshot.captured_at

    vendor_version = vendor_versions[0] if len(set(vendor_versions)) == 1 else "__".join(vendor_versions)
    return ChoiceMacroSnapshot(
        vendor_name="choice",
        vendor_version=vendor_version,
        captured_at=captured_at,
        series=series,
        raw_payload={"batches": raw_batches},
    )


def _ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table if not exists choice_market_snapshot (
          series_id varchar,
          series_name varchar,
          vendor_series_code varchar,
          vendor_name varchar,
          trade_date varchar,
          value_numeric double,
          frequency varchar,
          unit varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    conn.execute(
        """
        create table if not exists fact_choice_macro_daily (
          series_id varchar,
          series_name varchar,
          trade_date varchar,
          value_numeric double,
          frequency varchar,
          unit varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          quality_flag varchar,
          run_id varchar
        )
        """
    )
    conn.execute(
        """
        create table if not exists phase1_macro_vendor_catalog (
          series_id varchar,
          series_name varchar,
          vendor_name varchar,
          vendor_version varchar,
          frequency varchar,
          unit varchar,
          vendor_series_code varchar,
          batch_id varchar,
          catalog_version varchar,
          theme varchar,
          is_core boolean,
          tags_json varchar,
          request_options varchar,
          fetch_mode varchar,
          fetch_granularity varchar,
          refresh_tier varchar,
          policy_note varchar
        )
        """
    )
    conn.execute("alter table phase1_macro_vendor_catalog add column if not exists vendor_series_code varchar")
    conn.execute("alter table phase1_macro_vendor_catalog add column if not exists batch_id varchar")
    conn.execute("alter table phase1_macro_vendor_catalog add column if not exists catalog_version varchar")
    conn.execute("alter table phase1_macro_vendor_catalog add column if not exists theme varchar")
    conn.execute("alter table phase1_macro_vendor_catalog add column if not exists is_core boolean")
    conn.execute("alter table phase1_macro_vendor_catalog add column if not exists tags_json varchar")
    conn.execute("alter table phase1_macro_vendor_catalog add column if not exists request_options varchar")
    conn.execute("alter table phase1_macro_vendor_catalog add column if not exists fetch_mode varchar")
    conn.execute("alter table phase1_macro_vendor_catalog add column if not exists fetch_granularity varchar")
    conn.execute("alter table phase1_macro_vendor_catalog add column if not exists refresh_tier varchar")
    conn.execute("alter table phase1_macro_vendor_catalog add column if not exists policy_note varchar")
