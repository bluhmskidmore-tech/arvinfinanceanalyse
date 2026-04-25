from __future__ import annotations

import csv
import hashlib
import inspect
import json
import logging
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

import dramatiq
import duckdb
import requests
from backend.app.config.choice_runtime import _init_runtime
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_adapter import VendorAdapter
from backend.app.repositories.duckdb_migrations import (
    apply_pending_migrations_on_connection,
    ensure_choice_macro_schema_if_missing,
)
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    VENDOR_SNAPSHOT_MANIFEST_STREAM,
    VENDOR_VERSION_REGISTRY_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.object_store_repo import ObjectStoreRepository
from backend.app.repositories.tushare_adapter import (
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)
from backend.app.schemas.macro_vendor import (
    ChoiceMacroBatchConfig,
    ChoiceMacroCatalogAsset,
    ChoiceMacroSeriesConfig,
    ChoiceMacroSnapshot,
)
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.tasks.build_runs import BuildRunRecord

logger = logging.getLogger(__name__)


CHOICE_MACRO_LOCK = LockDefinition(key="lock:duckdb:choice-macro", ttl_seconds=900)
RULE_VERSION = "rv_choice_macro_thin_slice_v1"
STABLE_DATE_SLICE_SHORT_LOOKBACK_DAYS = 7
STABLE_DATE_SLICE_EXTENDED_LOOKBACK_DAYS = 31
PUBLIC_HEADLINE_RULE_VERSION = "rv_public_cross_asset_headline_v1"
PUBLIC_HEADLINE_BATCH_ID = "public_cross_asset_headline"
PUBLIC_HEADLINE_LOOKBACK_DAYS = 90
PUBLIC_HEADLINE_CATALOG_VERSION = "2026-04-21.public-cross-asset-headline.v1"
FRED_BRENT_SERIES_ID = "DCOILBRENTEU"
NCD_SHIBOR_RULE_VERSION = "rv_tushare_ncd_shibor_proxy_v1"
NCD_SHIBOR_BATCH_ID = "tushare_ncd_shibor_proxy"
NCD_SHIBOR_LOOKBACK_DAYS = 10
NCD_SHIBOR_CATALOG_VERSION = "2026-04-25.tushare-ncd-shibor-proxy.v1"
NCD_SHIBOR_TENORS: dict[str, dict[str, str]] = {
    "1M": {
        "series_id": "NCD.SHIBOR.1M",
        "series_name": "SHIBOR:1M",
        "vendor_series_code": "shibor:1m",
        "column": "1m",
    },
    "3M": {
        "series_id": "NCD.SHIBOR.3M",
        "series_name": "SHIBOR:3M",
        "vendor_series_code": "shibor:3m",
        "column": "3m",
    },
    "6M": {
        "series_id": "NCD.SHIBOR.6M",
        "series_name": "SHIBOR:6M",
        "vendor_series_code": "shibor:6m",
        "column": "6m",
    },
    "9M": {
        "series_id": "NCD.SHIBOR.9M",
        "series_name": "SHIBOR:9M",
        "vendor_series_code": "shibor:9m",
        "column": "9m",
    },
    "1Y": {
        "series_id": "NCD.SHIBOR.1Y",
        "series_name": "SHIBOR:1Y",
        "vendor_series_code": "shibor:1y",
        "column": "1y",
    },
}

_PUBLIC_HEADLINE_SERIES_META: dict[str, dict[str, object]] = {
    "E1000180": {
        "series_name": "中债国债到期收益率:10年",
        "vendor_name": "public_bond_zh_us_rate",
        "vendor_series_code": "bond_zh_us_rate:china_10y",
        "frequency": "daily",
        "unit": "%",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["public", "macro", "market", "rates", "chinabond", "cross_asset"],
        "policy_note": "public cross-asset headline supplement via Eastmoney bond_zh_us_rate",
    },
    "EMM00166466": {
        "series_name": "中债国债到期收益率:10年",
        "vendor_name": "public_bond_zh_us_rate",
        "vendor_series_code": "bond_zh_us_rate:china_10y",
        "frequency": "daily",
        "unit": "%",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["public", "macro", "market", "rates", "chinabond", "cross_asset"],
        "policy_note": "public cross-asset headline supplement via Eastmoney bond_zh_us_rate",
    },
    "E1003238": {
        "series_name": "美国国债收益率:10年",
        "vendor_name": "public_bond_zh_us_rate",
        "vendor_series_code": "bond_zh_us_rate:us_10y",
        "frequency": "daily",
        "unit": "%",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["public", "macro", "market", "rates", "us_treasury", "cross_asset"],
        "policy_note": "public cross-asset headline supplement via Eastmoney bond_zh_us_rate",
    },
    "EMG00001310": {
        "series_name": "美国:国债收益率:10年",
        "vendor_name": "public_bond_zh_us_rate",
        "vendor_series_code": "bond_zh_us_rate:us_10y",
        "frequency": "daily",
        "unit": "%",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["public", "macro", "market", "rates", "us_treasury", "cross_asset"],
        "policy_note": "public cross-asset headline supplement via Eastmoney bond_zh_us_rate",
    },
    "EM1": {
        "series_name": "中美国债利差(10Y)",
        "vendor_name": "public_bond_zh_us_rate",
        "vendor_series_code": "bond_zh_us_rate:cn_us_spread_10y",
        "frequency": "daily",
        "unit": "bp",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["public", "macro", "market", "rates", "spreads", "cross_asset"],
        "policy_note": "public cross-asset headline supplement computed from Eastmoney bond_zh_us_rate",
    },
    "CA.DR007": {
        "series_name": "存款类机构质押式回购加权利率:DR007",
        "vendor_name": "public_repo_rate_query",
        "vendor_series_code": "repo_rate_query:FDR007",
        "frequency": "daily",
        "unit": "%",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["public", "macro", "market", "rates", "liquidity", "cross_asset"],
        "policy_note": "public fallback headline lane via repo_rate_query FDR007; not the exact Choice weighted interbank lending 7D series",
    },
    "CA.BRENT": {
        "series_name": "Brent spot price",
        "vendor_name": "fred",
        "vendor_series_code": FRED_BRENT_SERIES_ID,
        "frequency": "daily",
        "unit": "USD/bbl",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["public", "macro", "market", "commodity", "oil", "cross_asset"],
        "policy_note": "public cross-asset headline supplement via FRED Brent spot series",
    },
    "CA.CSI300": {
        "series_name": "沪深300指数收盘价",
        "vendor_name": "tushare",
        "vendor_series_code": "index_daily:000300.SH.close",
        "frequency": "daily",
        "unit": "index",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["tushare", "market", "equity", "csi300", "cross_asset"],
        "policy_note": "Tushare index_daily supplement for CSI300 cross-asset risk sentiment",
    },
    "CA.CSI300_PCT_CHG": {
        "series_name": "沪深300指数涨跌幅",
        "vendor_name": "tushare",
        "vendor_series_code": "index_daily:000300.SH.pct_chg",
        "frequency": "daily",
        "unit": "%",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["tushare", "market", "equity", "csi300", "cross_asset"],
        "policy_note": "Tushare index_daily pct_chg supplement for CSI300 cross-asset momentum",
    },
    "CA.CSI300_PE": {
        "series_name": "沪深300市盈率",
        "vendor_name": "tushare",
        "vendor_series_code": "index_dailybasic:000300.SH.pe",
        "frequency": "daily",
        "unit": "x",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["tushare", "market", "equity", "valuation", "cross_asset"],
        "policy_note": "Tushare index_dailybasic PE supplement for CSI300 equity-bond spread",
    },
    "CA.MEGA_CAP_WEIGHT": {
        "series_name": "沪深300前十大权重合计",
        "vendor_name": "tushare",
        "vendor_series_code": "index_weight:000300.SH.top10_weight",
        "frequency": "daily",
        "unit": "%",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["tushare", "market", "equity", "mega_cap", "cross_asset"],
        "policy_note": "Tushare index_weight top10 concentration supplement for mega-cap equity leadership",
    },
    "CA.MEGA_CAP_TOP5_WEIGHT": {
        "series_name": "沪深300前五大权重合计",
        "vendor_name": "tushare",
        "vendor_series_code": "index_weight:000300.SH.top5_weight",
        "frequency": "daily",
        "unit": "%",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["tushare", "market", "equity", "mega_cap", "cross_asset"],
        "policy_note": "Tushare index_weight top5 concentration supplement for mega-cap equity leadership",
    },
    "CA.STEEL": {
        "series_name": "螺纹钢现货价格",
        "vendor_name": "public_spot_price_qh",
        "vendor_series_code": "spot_price_qh:螺纹钢:现货价格",
        "frequency": "daily",
        "unit": "CNY/t",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["public", "macro", "market", "commodity", "steel", "cross_asset"],
        "policy_note": "public cross-asset headline supplement via 99qh spot_price_qh",
    },
    "EMM00058124": {
        "series_name": "中间价:美元兑人民币",
        "vendor_name": "fx_daily_mid",
        "vendor_series_code": "fx_daily_mid:USD/CNY",
        "frequency": "daily",
        "unit": "CNY/USD",
        "theme": "macro_market",
        "is_core": True,
        "tags": ["public", "macro", "market", "fx", "cross_asset"],
        "policy_note": "cross-asset headline history supplement from local fx_daily_mid materialized table",
    },
}


@dramatiq.actor
def refresh_choice_macro_snapshot(
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    backfill_days: int = 0,
) -> dict[str, object]:
    logger.info("starting refresh_choice_macro_snapshot, backfill_days=%s", backfill_days)
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
        if backfill_days > 1:
            snapshot, series_registry = _fetch_backfill_snapshots(
                settings=settings,
                backfill_days=backfill_days,
            )
        else:
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
            capture_mode="live" if backfill_days <= 1 else "backfill",
        )
        vendor_version_registry = {
            "vendor_name": snapshot.vendor_name,
            "vendor_version": snapshot.vendor_version,
            "source_version": source_version,
            "run_id": run_id,
            "registered_at": run.created_at,
        }

        backfill_trade_dates: set[str] = set()
        if backfill_days > 1:
            for point in snapshot.series:
                if point.trade_date:
                    backfill_trade_dates.add(str(point.trade_date))

        with acquire_lock(CHOICE_MACRO_LOCK, base_dir=duckdb_file.parent):
            conn = duckdb.connect(str(duckdb_file), read_only=False)
            try:
                _ensure_tables(conn)
                conn.execute("begin transaction")
                choice_series_ids = _choice_managed_series_ids(conn, series_registry)
                _delete_choice_managed_rows(
                    conn,
                    series_ids=choice_series_ids,
                    trade_dates=sorted(backfill_trade_dates) if backfill_days > 1 and backfill_trade_dates else None,
                )

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
                    _insert_market_data_series_category(
                        conn,
                        series_id=series_id,
                        registry_entry=registry_entry,
                        run_id=run_id,
                        updated_at=run.created_at,
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


def refresh_public_cross_asset_headlines(
    duckdb_path: str | None = None,
    lookback_days: int = PUBLIC_HEADLINE_LOOKBACK_DAYS,
    report_date: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    target_date = date.fromisoformat(report_date) if report_date else date.today()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    history_rows = _load_public_cross_asset_history_rows(
        duckdb_path=str(duckdb_file),
        report_date=target_date,
        lookback_days=lookback_days,
        warnings=warnings,
    )
    if not history_rows:
        raise RuntimeError("No public cross-asset headline rows were fetched.")

    latest_rows = _latest_public_cross_asset_rows(history_rows)
    series_ids = sorted({row["series_id"] for row in history_rows})
    run_id = f"public_cross_asset_refresh:{target_date.isoformat()}"

    with acquire_lock(CHOICE_MACRO_LOCK, base_dir=duckdb_file.parent):
        conn = duckdb.connect(str(duckdb_file), read_only=False)
        try:
            _ensure_tables(conn)
            conn.execute("begin transaction")
            placeholders = ", ".join(["?"] * len(series_ids))
            conn.execute(
                f"delete from fact_choice_macro_daily where series_id in ({placeholders})",
                series_ids,
            )
            conn.execute(
                f"delete from choice_market_snapshot where series_id in ({placeholders})",
                series_ids,
            )
            conn.execute(
                f"delete from phase1_macro_vendor_catalog where series_id in ({placeholders})",
                series_ids,
            )
            conn.execute(
                f"delete from market_data_series_category where series_id in ({placeholders})",
                series_ids,
            )

            for row in history_rows:
                meta = _PUBLIC_HEADLINE_SERIES_META[row["series_id"]]
                conn.execute(
                    """
                    insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row["series_id"],
                        str(meta["series_name"]),
                        row["trade_date"],
                        row["value_numeric"],
                        str(meta["frequency"]),
                        str(meta["unit"]),
                        row["source_version"],
                        row["vendor_version"],
                        PUBLIC_HEADLINE_RULE_VERSION,
                        "ok",
                        run_id,
                    ],
                )

            for row in latest_rows:
                meta = _PUBLIC_HEADLINE_SERIES_META[row["series_id"]]
                conn.execute(
                    """
                    insert into choice_market_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row["series_id"],
                        str(meta["series_name"]),
                        str(meta["vendor_series_code"]),
                        str(meta["vendor_name"]),
                        row["trade_date"],
                        row["value_numeric"],
                        str(meta["frequency"]),
                        str(meta["unit"]),
                        row["source_version"],
                        row["vendor_version"],
                        PUBLIC_HEADLINE_RULE_VERSION,
                        run_id,
                    ],
                )
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
                        row["series_id"],
                        str(meta["series_name"]),
                        str(meta["vendor_name"]),
                        row["vendor_version"],
                        str(meta["frequency"]),
                        str(meta["unit"]),
                        str(meta["vendor_series_code"]),
                        PUBLIC_HEADLINE_BATCH_ID,
                        PUBLIC_HEADLINE_CATALOG_VERSION,
                        str(meta["theme"]),
                        bool(meta["is_core"]),
                        json.dumps(meta["tags"], ensure_ascii=False, separators=(",", ":")),
                        f"lookback_days={lookback_days}",
                        "latest",
                        "batch",
                        "stable",
                        str(meta["policy_note"]),
                    ],
                )
                _insert_market_data_series_category(
                    conn,
                    series_id=str(row["series_id"]),
                    registry_entry={
                        "refresh_tier": "stable",
                        "fetch_mode": "latest",
                        "fetch_granularity": "batch",
                        "policy_note": str(meta["policy_note"]),
                        "catalog_version": PUBLIC_HEADLINE_CATALOG_VERSION,
                        "batch_id": PUBLIC_HEADLINE_BATCH_ID,
                    },
                    run_id=run_id,
                    updated_at=target_date.isoformat(),
                )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
        finally:
            conn.close()

    return {
        "status": "completed",
        "run_id": run_id,
        "series_count": len(latest_rows),
        "row_count": len(history_rows),
        "warnings": warnings,
    }


def refresh_tushare_ncd_shibor_proxy(
    duckdb_path: str | None = None,
    lookback_days: int = NCD_SHIBOR_LOOKBACK_DAYS,
    report_date: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    target_date = date.fromisoformat(report_date) if report_date else date.today()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)

    history_rows = _fetch_tushare_ncd_shibor_history_rows(
        duckdb_path=str(duckdb_file),
        report_date=target_date,
        lookback_days=lookback_days,
    )
    if not history_rows:
        raise RuntimeError("No Tushare Shibor rows were fetched for NCD proxy refresh.")

    latest_rows = _latest_public_cross_asset_rows(history_rows)
    series_ids = sorted({str(meta["series_id"]) for meta in NCD_SHIBOR_TENORS.values()})
    latest_series_ids = {str(row["series_id"]) for row in latest_rows}
    missing_series_ids = sorted(set(series_ids) - latest_series_ids)
    if missing_series_ids:
        raise RuntimeError(f"Incomplete Tushare Shibor refresh; missing series: {', '.join(missing_series_ids)}")
    run_id = f"tushare_ncd_shibor_refresh:{target_date.isoformat()}"

    with acquire_lock(CHOICE_MACRO_LOCK, base_dir=duckdb_file.parent):
        conn = duckdb.connect(str(duckdb_file), read_only=False)
        try:
            _ensure_tables(conn)
            conn.execute("begin transaction")
            placeholders = ", ".join(["?"] * len(series_ids))
            conn.execute(
                f"delete from fact_choice_macro_daily where series_id in ({placeholders})",
                series_ids,
            )
            conn.execute(
                f"delete from choice_market_snapshot where series_id in ({placeholders})",
                series_ids,
            )
            conn.execute(
                f"delete from phase1_macro_vendor_catalog where series_id in ({placeholders})",
                series_ids,
            )
            conn.execute(
                f"delete from market_data_series_category where series_id in ({placeholders})",
                series_ids,
            )

            for row in history_rows:
                meta = _ncd_shibor_meta_by_series_id(str(row["series_id"]))
                conn.execute(
                    """
                    insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row["series_id"],
                        meta["series_name"],
                        row["trade_date"],
                        row["value_numeric"],
                        "daily",
                        "%",
                        row["source_version"],
                        row["vendor_version"],
                        NCD_SHIBOR_RULE_VERSION,
                        "ok",
                        run_id,
                    ],
                )

            for row in latest_rows:
                meta = _ncd_shibor_meta_by_series_id(str(row["series_id"]))
                conn.execute(
                    """
                    insert into choice_market_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row["series_id"],
                        meta["series_name"],
                        meta["vendor_series_code"],
                        "tushare",
                        row["trade_date"],
                        row["value_numeric"],
                        "daily",
                        "%",
                        row["source_version"],
                        row["vendor_version"],
                        NCD_SHIBOR_RULE_VERSION,
                        run_id,
                    ],
                )
                registry_entry = {
                    "refresh_tier": "stable",
                    "fetch_mode": "date_slice",
                    "fetch_granularity": "batch",
                    "policy_note": "Tushare Shibor fixing supplement for NCD funding proxy; quote medians remain unavailable.",
                    "catalog_version": NCD_SHIBOR_CATALOG_VERSION,
                    "batch_id": NCD_SHIBOR_BATCH_ID,
                }
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
                        row["series_id"],
                        meta["series_name"],
                        "tushare",
                        row["vendor_version"],
                        "daily",
                        "%",
                        meta["vendor_series_code"],
                        NCD_SHIBOR_BATCH_ID,
                        NCD_SHIBOR_CATALOG_VERSION,
                        "money_market",
                        True,
                        json.dumps(["tushare", "shibor", "ncd", "funding_proxy"], separators=(",", ":")),
                        f"lookback_days={lookback_days}",
                        "date_slice",
                        "batch",
                        "stable",
                        registry_entry["policy_note"],
                    ],
                )
                _insert_market_data_series_category(
                    conn,
                    series_id=str(row["series_id"]),
                    registry_entry=registry_entry,
                    run_id=run_id,
                    updated_at=target_date.isoformat(),
                )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
        finally:
            conn.close()

    return {
        "status": "completed",
        "run_id": run_id,
        "series_count": len(latest_rows),
        "row_count": len(history_rows),
    }


def _ncd_shibor_meta_by_series_id(series_id: str) -> dict[str, str]:
    for meta in NCD_SHIBOR_TENORS.values():
        if meta["series_id"] == series_id:
            return meta
    raise KeyError(series_id)


def _insert_market_data_series_category(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_id: str,
    registry_entry: dict[str, object],
    run_id: str,
    updated_at: str,
) -> None:
    category_key = str(registry_entry.get("refresh_tier") or "stable")
    category_label = {
        "stable": "Stable governed series",
        "fallback": "Fallback latest-only series",
        "isolated": "Isolated vendor-pending series",
    }.get(category_key, category_key)
    conn.execute(
        """
        insert into market_data_series_category (
          series_id,
          category_key,
          category_label,
          source_surface,
          fetch_mode,
          fetch_granularity,
          policy_note,
          catalog_version,
          batch_id,
          updated_at,
          run_id
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            series_id,
            category_key,
            category_label,
            "choice_macro",
            str(registry_entry.get("fetch_mode") or "date_slice"),
            str(registry_entry.get("fetch_granularity") or "batch"),
            _optional_string(registry_entry.get("policy_note")),
            _optional_string(registry_entry.get("catalog_version")),
            _optional_string(registry_entry.get("batch_id")),
            updated_at,
            run_id,
        ],
    )


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _build_source_version(raw_payload: dict[str, object]) -> str:
    digest = hashlib.sha256(
        json.dumps(raw_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"sv_choice_macro_{digest}"


def load_choice_macro_batches(settings, run_date: str | None = None) -> list[ChoiceMacroBatchConfig]:
    effective_run_date = _resolve_choice_macro_run_date(run_date)
    catalog_path = _resolve_choice_macro_catalog_path(settings)
    if catalog_path is not None and catalog_path.exists():
        return _normalize_choice_macro_batches(
            load_choice_macro_batches_from_catalog(catalog_path),
            run_date=effective_run_date,
        )

    if settings.choice_macro_commands_file:
        return _normalize_choice_macro_batches(
            load_choice_macro_batches_from_file(Path(settings.choice_macro_commands_file)),
            run_date=effective_run_date,
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
        run_date=effective_run_date,
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
            if _is_choice_mixed_ids_error(exc) and len(batch.series) > 1:
                return merge_choice_macro_snapshots(
                    [
                        _fetch_choice_macro_batch_snapshot(
                            adapter=adapter,
                            batch=batch.model_copy(
                                update={
                                    "series": [series],
                                    "fetch_granularity": "single",
                                }
                            ),
                            timeout_seconds=timeout_seconds,
                        )
                        for series in batch.series
                    ]
                )
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
    offsets = list(range(STABLE_DATE_SLICE_SHORT_LOOKBACK_DAYS + 1))
    offsets.extend(
        range(
            STABLE_DATE_SLICE_SHORT_LOOKBACK_DAYS + 1,
            STABLE_DATE_SLICE_EXTENDED_LOOKBACK_DAYS + 1,
        )
    )
    return [
        _replace_choice_date_range(batch.request_options, base_date - timedelta(days=offset))
        for offset in offsets
    ]


def _should_retry_previous_trading_day(batch: ChoiceMacroBatchConfig) -> bool:
    return batch.refresh_tier == "stable" and batch.fetch_mode == "date_slice"


def _is_choice_no_data_error(exc: RuntimeError) -> bool:
    text = str(exc).lower()
    return "no data" in text or "no rows" in text


def _is_choice_mixed_ids_error(exc: RuntimeError) -> bool:
    text = str(exc).lower()
    return "parameter error" in text or "can't be mixed" in text or "cannot be mixed" in text


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


def _choice_macro_run_date(override_date: str | None = None) -> str:
    if override_date:
        return override_date
    return date.today().isoformat()


def _resolve_choice_macro_run_date(run_date: str | None = None) -> str:
    parameter_count = len(inspect.signature(_choice_macro_run_date).parameters)
    if parameter_count == 0:
        return _choice_macro_run_date()
    return _choice_macro_run_date(run_date)


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
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)
    ensure_choice_macro_schema_if_missing(conn)


def _choice_managed_series_ids(
    conn: duckdb.DuckDBPyConnection,
    series_registry: dict[str, dict[str, object]],
) -> list[str]:
    rows = conn.execute(
        "select distinct series_id from phase1_macro_vendor_catalog where lower(vendor_name) = 'choice'"
    ).fetchall()
    managed = {str(row[0]) for row in rows if row and row[0]}
    managed.update(series_registry.keys())
    return sorted(managed)


def _delete_choice_managed_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_ids: list[str],
    trade_dates: list[str] | None,
) -> None:
    if not series_ids:
        return
    series_placeholders = ", ".join(["?"] * len(series_ids))
    if trade_dates:
        date_placeholders = ", ".join(["?"] * len(trade_dates))
        params = [*series_ids, *trade_dates]
        conn.execute(
            f"""
            delete from choice_market_snapshot
            where series_id in ({series_placeholders}) and trade_date in ({date_placeholders})
            """,
            params,
        )
        conn.execute(
            f"""
            delete from fact_choice_macro_daily
            where series_id in ({series_placeholders}) and trade_date in ({date_placeholders})
            """,
            params,
        )
    else:
        conn.execute(f"delete from choice_market_snapshot where series_id in ({series_placeholders})", series_ids)
        conn.execute(f"delete from fact_choice_macro_daily where series_id in ({series_placeholders})", series_ids)
    conn.execute(f"delete from phase1_macro_vendor_catalog where series_id in ({series_placeholders})", series_ids)
    conn.execute(f"delete from market_data_series_category where series_id in ({series_placeholders})", series_ids)


def _fetch_backfill_snapshots(
    *,
    settings,
    backfill_days: int,
) -> tuple[ChoiceMacroSnapshot, dict[str, dict[str, object]]]:
    """Fetch Choice macro data for each of the last *backfill_days* calendar days.

    Returns the merged snapshot and the series registry (from the latest day's batches).
    """
    adapter = VendorAdapter()
    all_snapshots: list[ChoiceMacroSnapshot] = []
    series_registry: dict[str, dict[str, object]] = {}
    today = date.today()

    for offset in range(backfill_days):
        target_date = (today - timedelta(days=offset)).isoformat()
        batches = load_choice_macro_batches(settings, run_date=target_date)
        if offset == 0:
            series_registry = _build_choice_series_registry(batches)
        fetch_plan = _build_choice_macro_fetch_plan(batches)

        day_snapshots: list[ChoiceMacroSnapshot] = []
        for batch in fetch_plan:
            try:
                snap = _fetch_choice_macro_batch_snapshot(
                    adapter=adapter,
                    batch=batch,
                    timeout_seconds=settings.choice_timeout_seconds,
                )
            except RuntimeError as exc:
                if _is_choice_no_data_error(exc):
                    continue
                raise
            day_snapshots.append(snap)

        if day_snapshots:
            all_snapshots.extend(day_snapshots)

    merged = merge_choice_macro_snapshots(all_snapshots)
    return merged, series_registry


def _load_public_cross_asset_history_rows(
    *,
    duckdb_path: str,
    report_date: date,
    lookback_days: int,
    warnings: list[str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for loader in (
        _fetch_public_bond_zh_us_history_rows,
        _fetch_public_dr007_history_rows,
        _fetch_tushare_cross_asset_history_rows,
        _fetch_public_brent_history_rows,
        _fetch_public_steel_history_rows,
        _fetch_public_fx_history_rows,
    ):
        try:
            rows.extend(
                loader(
                    duckdb_path=duckdb_path,
                    report_date=report_date,
                    lookback_days=lookback_days,
                )
            )
        except Exception as exc:
            warnings.append(f"{loader.__name__}: {exc}")
    deduped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        deduped[(str(row["series_id"]), str(row["trade_date"]))] = row
    return sorted(deduped.values(), key=lambda item: (str(item["series_id"]), str(item["trade_date"])))


def _fetch_public_bond_zh_us_history_rows(
    *,
    duckdb_path: str,
    report_date: date,
    lookback_days: int,
) -> list[dict[str, object]]:
    del duckdb_path
    import akshare as ak  # type: ignore

    start_date = (report_date - timedelta(days=max(lookback_days, 45) * 2)).strftime("%Y%m%d")
    frame = ak.bond_zh_us_rate(start_date=start_date)
    rows: list[dict[str, object]] = []
    vendor_version = f"vv_public_bond_zh_us_rate_{report_date.isoformat().replace('-', '')}"
    source_version = f"sv_public_bond_zh_us_rate_{report_date.isoformat().replace('-', '')}"
    for record in frame.to_dict(orient="records"):
        trade_date = _coerce_public_trade_date(record.get("日期"))
        if trade_date is None or trade_date > report_date.isoformat():
            continue
        cn10y = _coerce_public_number(record.get("中国国债收益率10年"))
        us10y = _coerce_public_number(record.get("美国国债收益率10年"))
        if cn10y is not None:
            rows.append(_public_history_row("E1000180", trade_date, cn10y, vendor_version, source_version))
            rows.append(_public_history_row("EMM00166466", trade_date, cn10y, vendor_version, source_version))
        if us10y is not None:
            rows.append(_public_history_row("E1003238", trade_date, us10y, vendor_version, source_version))
            rows.append(_public_history_row("EMG00001310", trade_date, us10y, vendor_version, source_version))
        if cn10y is not None and us10y is not None:
            rows.append(
                _public_history_row(
                    "EM1",
                    trade_date,
                    round((cn10y - us10y) * 100, 6),
                    vendor_version,
                    source_version,
                )
            )
    return rows


def _fetch_public_dr007_history_rows(
    *,
    duckdb_path: str,
    report_date: date,
    lookback_days: int,
) -> list[dict[str, object]]:
    del duckdb_path, lookback_days
    import akshare as ak  # type: ignore

    frame = ak.repo_rate_query(symbol="\u94f6\u94f6\u95f4\u56de\u8d2d\u5b9a\u76d8\u5229\u7387")
    vendor_version = f"vv_public_repo_rate_query_{report_date.isoformat().replace('-', '')}"
    source_version = f"sv_public_repo_rate_query_{report_date.isoformat().replace('-', '')}"
    rows: list[dict[str, object]] = []
    for record in frame.to_dict(orient="records"):
        trade_date = _coerce_public_trade_date(record.get("date"))
        if trade_date is None or trade_date > report_date.isoformat():
            continue
        value = _coerce_public_number(record.get("FDR007"))
        if value is None:
            continue
        rows.append(_public_history_row("CA.DR007", trade_date, value, vendor_version, source_version))
    return rows


def _fetch_public_brent_history_rows(
    *,
    duckdb_path: str,
    report_date: date,
    lookback_days: int,
) -> list[dict[str, object]]:
    del duckdb_path
    start_date = (report_date - timedelta(days=max(lookback_days, 45) * 2)).isoformat()
    response = requests.get(
        f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={FRED_BRENT_SERIES_ID}",
        timeout=20,
    )
    response.raise_for_status()
    reader = csv.DictReader(StringIO(response.text))
    vendor_version = f"vv_public_fred_{FRED_BRENT_SERIES_ID}_{report_date.isoformat().replace('-', '')}"
    source_digest = hashlib.sha256(response.text.encode("utf-8")).hexdigest()[:12]
    source_version = f"sv_public_fred_{source_digest}"
    rows: list[dict[str, object]] = []
    for record in reader:
        trade_date = _coerce_public_trade_date(record.get("observation_date"))
        if trade_date is None or trade_date > report_date.isoformat() or trade_date < start_date:
            continue
        value = _coerce_public_number(record.get(FRED_BRENT_SERIES_ID))
        if value is None:
            continue
        rows.append(_public_history_row("CA.BRENT", trade_date, value, vendor_version, source_version))
    return rows


def _fetch_tushare_cross_asset_history_rows(
    *,
    duckdb_path: str,
    report_date: date,
    lookback_days: int,
) -> list[dict[str, object]]:
    del duckdb_path
    settings = get_settings()
    token = resolve_tushare_token_with_settings_fallback(settings)
    if not token:
        raise RuntimeError("MOSS_TUSHARE_TOKEN is not configured.")

    ts = import_tushare_pro()
    pro = ts.pro_api(token)
    start_date = (report_date - timedelta(days=max(lookback_days, 45) * 2)).strftime("%Y%m%d")
    weight_start_date = (report_date - timedelta(days=max(lookback_days, 90) * 2)).strftime("%Y%m%d")
    end_date = report_date.strftime("%Y%m%d")
    daily_records = _records_from_tushare_frame(
        pro.index_daily(ts_code="000300.SH", start_date=start_date, end_date=end_date)
    )
    basic_records = _records_from_tushare_frame(
        pro.index_dailybasic(ts_code="000300.SH", start_date=start_date, end_date=end_date)
    )
    weight_records = _records_from_tushare_frame(
        pro.index_weight(index_code="000300.SH", start_date=weight_start_date, end_date=end_date)
    )

    rows: list[dict[str, object]] = []
    daily_vendor_version = f"vv_tushare_index_daily_000300SH_{end_date}"
    daily_source_version = _source_version_from_records("tushare_index_daily", daily_records)
    for record in daily_records:
        trade_date = _coerce_public_trade_date(record.get("trade_date"))
        if trade_date is None or trade_date > report_date.isoformat():
            continue
        close = _coerce_public_number(record.get("close"))
        pct_chg = _coerce_public_number(record.get("pct_chg"))
        if close is not None:
            rows.append(_public_history_row("CA.CSI300", trade_date, close, daily_vendor_version, daily_source_version))
        if pct_chg is not None:
            rows.append(
                _public_history_row("CA.CSI300_PCT_CHG", trade_date, pct_chg, daily_vendor_version, daily_source_version)
            )

    basic_vendor_version = f"vv_tushare_index_dailybasic_000300SH_{end_date}"
    basic_source_version = _source_version_from_records("tushare_index_dailybasic", basic_records)
    for record in basic_records:
        trade_date = _coerce_public_trade_date(record.get("trade_date"))
        if trade_date is None or trade_date > report_date.isoformat():
            continue
        pe = _coerce_public_number(record.get("pe"))
        if pe is None:
            pe = _coerce_public_number(record.get("pe_ttm"))
        if pe is not None and pe > 0:
            rows.append(_public_history_row("CA.CSI300_PE", trade_date, pe, basic_vendor_version, basic_source_version))

    weight_vendor_version = f"vv_tushare_index_weight_000300SH_{end_date}"
    weight_source_version = _source_version_from_records("tushare_index_weight", weight_records)
    weights_by_date: dict[str, list[float]] = {}
    for record in weight_records:
        trade_date = _coerce_public_trade_date(record.get("trade_date"))
        if trade_date is None or trade_date > report_date.isoformat():
            continue
        weight = _coerce_public_number(record.get("weight"))
        if weight is None:
            continue
        weights_by_date.setdefault(trade_date, []).append(weight)

    for trade_date, weights in sorted(weights_by_date.items()):
        ordered = sorted(weights, reverse=True)
        top10 = sum(ordered[:10])
        top5 = sum(ordered[:5])
        if top10 > 0:
            rows.append(
                _public_history_row("CA.MEGA_CAP_WEIGHT", trade_date, top10, weight_vendor_version, weight_source_version)
            )
        if top5 > 0:
            rows.append(
                _public_history_row(
                    "CA.MEGA_CAP_TOP5_WEIGHT",
                    trade_date,
                    top5,
                    weight_vendor_version,
                    weight_source_version,
                )
            )

    return rows


def _fetch_tushare_ncd_shibor_history_rows(
    *,
    duckdb_path: str,
    report_date: date,
    lookback_days: int,
) -> list[dict[str, object]]:
    del duckdb_path
    settings = get_settings()
    token = resolve_tushare_token_with_settings_fallback(settings)
    if not token:
        raise RuntimeError("MOSS_TUSHARE_TOKEN is not configured.")

    ts = import_tushare_pro()
    pro = ts.pro_api(token)
    start_date_value = report_date - timedelta(days=max(lookback_days, 1))
    start_date = start_date_value.strftime("%Y%m%d")
    start_date_iso = start_date_value.isoformat()
    end_date = report_date.strftime("%Y%m%d")
    records = _records_from_tushare_frame(pro.shibor(start_date=start_date, end_date=end_date))
    vendor_version = f"vv_tushare_shibor_{end_date}"
    source_version = _source_version_from_records("tushare_shibor", records)

    rows: list[dict[str, object]] = []
    for record in records:
        trade_date = _coerce_public_trade_date(record.get("date"))
        if trade_date is None or trade_date > report_date.isoformat() or trade_date < start_date_iso:
            continue
        for meta in NCD_SHIBOR_TENORS.values():
            value = _coerce_public_number(record.get(meta["column"]))
            if value is None:
                continue
            rows.append(_public_history_row(meta["series_id"], trade_date, value, vendor_version, source_version))
    return rows


def _fetch_public_steel_history_rows(
    *,
    duckdb_path: str,
    report_date: date,
    lookback_days: int,
) -> list[dict[str, object]]:
    del duckdb_path
    start_date = (report_date - timedelta(days=max(lookback_days, 45) * 2)).isoformat()
    import akshare as ak  # type: ignore

    frame = ak.spot_price_qh(symbol="\u87ba\u7eb9\u94a2")
    vendor_version = f"vv_public_spot_price_qh_{report_date.isoformat().replace('-', '')}"
    source_version = f"sv_public_spot_price_qh_{report_date.isoformat().replace('-', '')}"
    rows: list[dict[str, object]] = []
    for record in frame.to_dict(orient="records"):
        trade_date = _coerce_public_trade_date(record.get("日期"))
        if trade_date is None or trade_date > report_date.isoformat() or trade_date < start_date:
            continue
        value = _coerce_public_number(record.get("现货价格"))
        if value is None:
            continue
        rows.append(_public_history_row("CA.STEEL", trade_date, value, vendor_version, source_version))
    return rows


def _fetch_public_fx_history_rows(
    *,
    duckdb_path: str,
    report_date: date,
    lookback_days: int,
) -> list[dict[str, object]]:
    del duckdb_path
    start_date = (report_date - timedelta(days=max(lookback_days, 45) * 2)).isoformat()
    import akshare as ak  # type: ignore

    frame = ak.currency_boc_safe()
    vendor_version = f"vv_public_currency_boc_safe_{report_date.isoformat().replace('-', '')}"
    source_version = f"sv_public_currency_boc_safe_{report_date.isoformat().replace('-', '')}"
    result: list[dict[str, object]] = []
    for record in frame.to_dict(orient="records"):
        trade_date = _coerce_public_trade_date(record.get("日期"))
        if trade_date is None or trade_date > report_date.isoformat() or trade_date < start_date:
            continue
        value = _coerce_public_number(record.get("美元"))
        if value is None:
            continue
        result.append(
            _public_history_row(
                "EMM00058124",
                trade_date,
                round(value / 100, 6),
                vendor_version,
                source_version,
            )
        )
    return result


def _records_from_tushare_frame(frame: object) -> list[dict[str, object]]:
    if frame is None:
        return []
    try:
        if len(frame) == 0:  # type: ignore[arg-type]
            return []
        return list(frame.to_dict(orient="records"))  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        return []


def _source_version_from_records(prefix: str, records: list[dict[str, object]]) -> str:
    digest = hashlib.sha256(
        json.dumps(records, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return f"sv_{prefix}_{digest}"


def _public_history_row(
    series_id: str,
    trade_date: str,
    value_numeric: float,
    vendor_version: str,
    source_version: str,
) -> dict[str, object]:
    return {
        "series_id": series_id,
        "trade_date": trade_date,
        "value_numeric": float(value_numeric),
        "vendor_version": vendor_version,
        "source_version": source_version,
    }


def _latest_public_cross_asset_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for row in rows:
        current = latest.get(str(row["series_id"]))
        if current is None or str(row["trade_date"]) > str(current["trade_date"]):
            latest[str(row["series_id"])] = row
    return [latest[key] for key in sorted(latest)]


def _coerce_public_trade_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    normalized = text.replace("/", "-")
    if len(normalized) >= 10 and normalized[4] == "-" and normalized[7] == "-":
        return normalized[:10]
    return normalized


def _coerce_public_number(value: object) -> float | None:
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"} or text == ".":
        return None
    return float(text)
