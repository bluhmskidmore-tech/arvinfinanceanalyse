from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import date
from pathlib import Path

import duckdb

from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    SNAPSHOT_BUILD_RUN_STREAM,
    SNAPSHOT_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.object_store_repo import ObjectStoreRepository
from backend.app.repositories.snapshot_repo import (
    ensure_snapshot_tables,
    merge_zqtz_rows_by_grain,
    merge_tyw_rows_by_grain,
    replace_tyw_snapshot_rows,
    replace_zqtz_snapshot_rows,
)
from backend.app.repositories.snapshot_row_parse import (
    parse_tyw_snapshot_rows_from_bytes,
    parse_zqtz_snapshot_rows_from_bytes,
)
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.schemas.snapshot import (
    SnapshotBuildRunRecord,
    SnapshotManifestRecord,
    SourceLinkage,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.build_runs import BuildRunRecord

logger = logging.getLogger(__name__)

SNAPSHOT_RULE_VERSION = "rv_snapshot_zqtz_tyw_v1"
TYW_LOCF_RULE_VERSION = f"{SNAPSHOT_RULE_VERSION}__locf"
SNAPSHOT_SCHEMA_VERSION = "snapshot.schema.v1"
CANONICAL_GRAIN_VERSION = "cgv_v1"
SNAPSHOT_KEY = "snapshot.zqtz_tyw.standardized"


def resolve_snapshot_lock(duckdb_file: Path) -> LockDefinition:
    canonical_path = os.path.normcase(str(duckdb_file.resolve()))
    digest = hashlib.sha256(canonical_path.encode("utf-8")).hexdigest()[:12]
    return LockDefinition(
        key=f"lock:duckdb:snapshot-materialize:{digest}",
        ttl_seconds=900,
    )


def _locf_tyw_snapshot_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
) -> dict[str, object] | None:
    target_date = date.fromisoformat(report_date)
    prior_row = conn.execute(
        """
        select report_date
        from tyw_interbank_daily_snapshot
        where report_date < ?::date
        group by report_date
        having count(*) > 0
        order by report_date desc
        limit 1
        """,
        [target_date.isoformat()],
    ).fetchone()
    if prior_row is None:
        return None

    prior_date = prior_row[0]
    prior_date_text = prior_date.isoformat()
    source_versions = [
        str(row[0])
        for row in conn.execute(
            """
            select distinct source_version
            from tyw_interbank_daily_snapshot
            where report_date = ?::date
              and coalesce(trim(source_version), '') <> ''
            order by source_version
            """,
            [prior_date_text],
        ).fetchall()
    ]
    digest = hashlib.sha256(
        "|".join([target_date.isoformat(), prior_date_text, *source_versions]).encode("utf-8")
    ).hexdigest()[:12]
    locf_source_version = f"sv_tyw_locf_{digest}"
    locf_ingest_batch_id = f"locf:{prior_date_text}"

    conn.execute(
        "delete from tyw_interbank_daily_snapshot where report_date = ?::date",
        [target_date.isoformat()],
    )
    row_count = conn.execute(
        """
        insert into tyw_interbank_daily_snapshot (
          report_date,
          position_id,
          product_type,
          position_side,
          counterparty_name,
          account_type,
          special_account_type,
          core_customer_type,
          currency_code,
          principal_native,
          accrued_interest_native,
          funding_cost_rate,
          maturity_date,
          pledged_bond_code,
          source_version,
          rule_version,
          ingest_batch_id,
          trace_id
        )
        select
          ?::date as report_date,
          position_id,
          product_type,
          position_side,
          counterparty_name,
          account_type,
          special_account_type,
          core_customer_type,
          currency_code,
          principal_native,
          accrued_interest_native,
          funding_cost_rate,
          maturity_date,
          pledged_bond_code,
          ? as source_version,
          ? as rule_version,
          ? as ingest_batch_id,
          concat('locf:', ?, ':from:', ?,
                 case when coalesce(trim(trace_id), '') = '' then '' else concat(':', trace_id) end) as trace_id
        from tyw_interbank_daily_snapshot
        where report_date = ?::date
        """,
        [
            target_date.isoformat(),
            locf_source_version,
            TYW_LOCF_RULE_VERSION,
            locf_ingest_batch_id,
            target_date.isoformat(),
            prior_date_text,
            prior_date_text,
        ],
    ).fetchone()[0]
    return {
        "row_count": int(row_count or 0),
        "source_version": locf_source_version,
        "prior_report_date": prior_date_text,
        "ingest_batch_id": locf_ingest_batch_id,
    }


def _materialize_standard_snapshots(
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    ingest_batch_id: str | None = None,
    source_families: list[str] | None = None,
    report_date: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    gov_repo = GovernanceRepository(base_dir=governance_path)
    manifest_repo = SourceManifestRepository(governance_repo=gov_repo)
    store = ObjectStoreRepository(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        mode=settings.object_store_mode,
        local_archive_path=str(settings.local_archive_path),
    )

    run = BuildRunRecord(job_name="snapshot_materialize", status="running")
    run_id = f"{run.job_name}:{run.created_at}"
    snapshot_run_id = str(uuid.uuid4())
    lock = resolve_snapshot_lock(duckdb_file)

    selected = manifest_repo.select_for_snapshot_materialization(
        source_families=source_families,
        report_date=report_date,
        ingest_batch_id=ingest_batch_id,
    )
    if store.mode == "local" and selected:
        before = len(selected)
        selected = [
            row
            for row in selected
            if row.get("archived_path") and Path(str(row["archived_path"])).is_file()
        ]
        dropped = before - len(selected)
        if dropped:
            logger.warning(
                "snapshot_materialize skipped %s manifest row(s) pointing at missing archive files",
                dropped,
            )
    if not selected:
        combined_sv = "sv_snapshot_empty"
        completed = SnapshotBuildRunRecord(
            run_id=run_id,
            job_name=run.job_name,
            status="completed",
            snapshot_key=SNAPSHOT_KEY,
            lock=lock.key,
            source_version=combined_sv,
            vendor_version="vv_none",
        ).model_dump()
        gov_repo.append(SNAPSHOT_BUILD_RUN_STREAM, completed)
        return {
            "status": "completed",
            "run_id": run_id,
            "snapshot_run_id": snapshot_run_id,
            "zqtz_rows": 0,
            "tyw_rows": 0,
            "ingest_batch_ids": [],
            "lock": lock.key,
        }

    selected_source_versions = {
        str(row.get("source_version", ""))
        for row in selected
        if row.get("source_version")
    }
    extra_source_versions: set[str] = set()
    combined_sv = "__".join(sorted(selected_source_versions)) or "sv_snapshot_empty"

    zqtz_manifests = [row for row in selected if str(row.get("source_family")) == "zqtz"]
    tyw_manifests = [row for row in selected if str(row.get("source_family")) == "tyw"]

    manifest_payloads: list[tuple[str, dict[str, object]]] = []

    try:
        with acquire_lock(lock, base_dir=duckdb_file.parent):
            conn = duckdb.connect(str(duckdb_file), read_only=False)
            try:
                conn.execute("begin transaction")
                ensure_snapshot_tables(conn)

                zqtz_total = 0
                tyw_total = 0
                if zqtz_manifests:
                    z_batches = sorted({str(m["ingest_batch_id"]) for m in zqtz_manifests})
                    z_report_dates = sorted(
                        {
                            str(m.get("report_date") or "").strip()
                            for m in zqtz_manifests
                            if str(m.get("report_date") or "").strip()
                        }
                    )
                    ordered_rows: list[dict[str, object]] = []
                    for manifest_row in sorted(
                        zqtz_manifests,
                        key=lambda item: str(item.get("archived_path", "")),
                    ):
                        archived_path = str(manifest_row["archived_path"])
                        payload = store.read_archived_bytes(archived_path)
                        ib = str(manifest_row["ingest_batch_id"])
                        sv = str(manifest_row["source_version"])
                        sf = str(manifest_row.get("source_file") or Path(archived_path).name)
                        parsed = parse_zqtz_snapshot_rows_from_bytes(
                            file_bytes=payload,
                            ingest_batch_id=ib,
                            source_version=sv,
                            source_file=sf,
                            rule_version=SNAPSHOT_RULE_VERSION,
                        )
                        linkage = SourceLinkage(
                            ingest_batch_id=ib,
                            source_family="zqtz",
                            source_file=sf,
                            source_version=sv,
                            archived_path=archived_path,
                        )
                        manifest_payloads.append(
                            (
                                "zqtz_bond_daily_snapshot",
                                SnapshotManifestRecord(
                                    snapshot_run_id=snapshot_run_id,
                                    target_table="zqtz_bond_daily_snapshot",
                                    schema_version=SNAPSHOT_SCHEMA_VERSION,
                                    canonical_grain_version=CANONICAL_GRAIN_VERSION,
                                    source_linkage=linkage,
                                    rule_version=SNAPSHOT_RULE_VERSION,
                                    produced_row_count=len(parsed),
                                    status="completed",
                                ).model_dump(mode="json"),
                            )
                        )
                        ordered_rows.extend(parsed)
                    merged_z = merge_zqtz_rows_by_grain(ordered_rows)
                    zqtz_total = replace_zqtz_snapshot_rows(
                        conn,
                        merged_z,
                        ingest_batch_ids=z_batches,
                        report_dates=z_report_dates,
                        replace_all_for_report_dates=bool(report_date),
                    )
                    if zqtz_total <= 0:
                        raise ValueError(
                            "Fail closed: zqtz manifest rows matched this materialization run but standardized "
                            f"snapshot wrote 0 rows (report_dates={z_report_dates!r}, ingest_batch_ids={z_batches!r})."
                        )

                if tyw_manifests:
                    t_batches = sorted({str(m["ingest_batch_id"]) for m in tyw_manifests})
                    t_report_dates = sorted(
                        {
                            str(m.get("report_date") or "").strip()
                            for m in tyw_manifests
                            if str(m.get("report_date") or "").strip()
                        }
                    )
                    ordered_tyw: list[dict[str, object]] = []
                    for manifest_row in sorted(
                        tyw_manifests,
                        key=lambda item: str(item.get("archived_path", "")),
                    ):
                        archived_path = str(manifest_row["archived_path"])
                        payload = store.read_archived_bytes(archived_path)
                        ib = str(manifest_row["ingest_batch_id"])
                        sv = str(manifest_row["source_version"])
                        sf = str(manifest_row.get("source_file") or Path(archived_path).name)
                        parsed = parse_tyw_snapshot_rows_from_bytes(
                            file_bytes=payload,
                            ingest_batch_id=ib,
                            source_version=sv,
                            source_file=sf,
                            rule_version=SNAPSHOT_RULE_VERSION,
                        )
                        linkage = SourceLinkage(
                            ingest_batch_id=ib,
                            source_family="tyw",
                            source_file=sf,
                            source_version=sv,
                            archived_path=archived_path,
                        )
                        manifest_payloads.append(
                            (
                                "tyw_interbank_daily_snapshot",
                                SnapshotManifestRecord(
                                    snapshot_run_id=snapshot_run_id,
                                    target_table="tyw_interbank_daily_snapshot",
                                    schema_version=SNAPSHOT_SCHEMA_VERSION,
                                    canonical_grain_version=CANONICAL_GRAIN_VERSION,
                                    source_linkage=linkage,
                                    rule_version=SNAPSHOT_RULE_VERSION,
                                    produced_row_count=len(parsed),
                                    status="completed",
                                ).model_dump(mode="json"),
                            )
                        )
                        ordered_tyw.extend(parsed)
                    merged_t = merge_tyw_rows_by_grain(ordered_tyw)
                    tyw_total = replace_tyw_snapshot_rows(
                        conn,
                        merged_t,
                        ingest_batch_ids=t_batches,
                        report_dates=t_report_dates,
                        replace_all_for_report_dates=bool(report_date),
                    )
                    if tyw_total <= 0:
                        raise ValueError(
                            "Fail closed: tyw manifest rows matched this materialization run but standardized "
                            f"snapshot wrote 0 rows (report_dates={t_report_dates!r}, ingest_batch_ids={t_batches!r})."
                        )
                elif report_date and zqtz_manifests and (
                    source_families is None or "tyw" in set(source_families)
                ):
                    locf_payload = _locf_tyw_snapshot_rows(conn, report_date=report_date)
                    if locf_payload is not None:
                        tyw_total = int(locf_payload["row_count"])
                        extra_source_versions.add(str(locf_payload["source_version"]))
                        manifest_payloads.append(
                            (
                                "tyw_interbank_daily_snapshot",
                                SnapshotManifestRecord(
                                    snapshot_run_id=snapshot_run_id,
                                    target_table="tyw_interbank_daily_snapshot",
                                    schema_version=SNAPSHOT_SCHEMA_VERSION,
                                    canonical_grain_version=CANONICAL_GRAIN_VERSION,
                                    source_linkage=SourceLinkage(
                                        ingest_batch_id=str(locf_payload["ingest_batch_id"]),
                                        source_family="tyw",
                                        source_file=f"locf:TYWLSHOW:{report_date}",
                                        source_version=str(locf_payload["source_version"]),
                                        archived_path=(
                                            "locf://tyw_interbank_daily_snapshot/"
                                            f"{locf_payload['prior_report_date']}"
                                        ),
                                    ),
                                    rule_version=TYW_LOCF_RULE_VERSION,
                                    produced_row_count=tyw_total,
                                    status="completed",
                                ).model_dump(mode="json"),
                            )
                        )

                conn.execute("commit")
            except Exception:
                conn.execute("rollback")
                raise
            finally:
                conn.close()

        combined_sv = "__".join(sorted(selected_source_versions | extra_source_versions)) or "sv_snapshot_empty"
        build_completed = SnapshotBuildRunRecord(
            run_id=run_id,
            job_name=run.job_name,
            status="completed",
            snapshot_key=SNAPSHOT_KEY,
            lock=lock.key,
            source_version=combined_sv,
            vendor_version="vv_none",
        ).model_dump()
        entries: list[tuple[str, dict[str, object]]] = [(SNAPSHOT_BUILD_RUN_STREAM, build_completed)]
        for _table, payload in manifest_payloads:
            entries.append((SNAPSHOT_MANIFEST_STREAM, payload))
        gov_repo.append_many_atomic(entries)

        batch_ids = sorted({str(r.get("ingest_batch_id")) for r in selected})
        return {
            "status": "completed",
            "run_id": run_id,
            "snapshot_run_id": snapshot_run_id,
            "zqtz_rows": zqtz_total,
            "tyw_rows": tyw_total,
            "ingest_batch_ids": batch_ids,
            "lock": lock.key,
        }
    except Exception as exc:
        failed = SnapshotBuildRunRecord(
            run_id=run_id,
            job_name=run.job_name,
            status="failed",
            snapshot_key=SNAPSHOT_KEY,
            lock=lock.key,
            source_version=combined_sv,
            vendor_version="vv_none",
        ).model_dump()
        failed["error_message"] = str(exc)
        gov_repo.append(SNAPSHOT_BUILD_RUN_STREAM, failed)
        raise


materialize_standard_snapshots = register_actor_once(
    "materialize_standard_snapshots",
    _materialize_standard_snapshots,
)
