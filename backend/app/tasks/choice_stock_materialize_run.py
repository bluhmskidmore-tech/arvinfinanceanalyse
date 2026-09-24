from __future__ import annotations

import argparse
import functools
import hashlib
import json
import socket
import sys
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext

from backend.app.governance.settings import get_settings
from backend.app.tasks.choice_stock_materialize import (
    ChoiceStockMaterializationCoverage,
    load_choice_stock_materialization_coverage,
    materialize_choice_stock_factor_snapshot,
    materialize_choice_stock_inputs,
)
from backend.app.tasks.choice_stock_observation_manifest import (
    resolve_latest_committed_choice_stock_observation,
)
from backend.app.tasks.choice_stock_theme_overlay_refresh import (
    refresh_choice_stock_theme_overlay,
)


def _emit_json_payload(payload: dict[str, object]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered, file=sys.stdout)


def _bind_source_address(original, source_ip: str):
    """Wrap a create_connection-style callable so unpinned calls egress from source_ip."""

    @functools.wraps(original)
    def source_bound_create_connection(address, *args, **kwargs):
        # create_connection(address, timeout, source_address, ...); only inject
        # when the caller did not pin a source address itself.
        if len(args) < 2 and kwargs.get("source_address") is None:
            kwargs["source_address"] = (source_ip, 0)
        return original(address, *args, **kwargs)

    return source_bound_create_connection


@contextmanager
def _tushare_source_network(source_ip: str) -> Iterator[None]:
    """Bind Tushare HTTP sockets to source_ip when the default route breaks the TLS handshake."""
    import urllib3.util.connection as urllib3_connection

    original_create_connection = socket.create_connection
    # urllib3 (requests -> Tushare) ships its own create_connection and never
    # calls socket.create_connection, so both entry points must be bound.
    original_urllib3_create_connection = urllib3_connection.create_connection
    socket.create_connection = _bind_source_address(original_create_connection, source_ip)
    urllib3_connection.create_connection = _bind_source_address(original_urllib3_create_connection, source_ip)
    try:
        yield
    finally:
        socket.create_connection = original_create_connection
        urllib3_connection.create_connection = original_urllib3_create_connection


def _theme_overlay_only_payload(*, as_of_date: str, duckdb_path: str) -> dict[str, object]:
    """Anchor an overlay-only run on the already committed materialization for the same date."""
    observation = resolve_latest_committed_choice_stock_observation(
        duckdb_path=duckdb_path,
        expected_report_date=as_of_date,
    )
    return {
        "status": "theme_overlay_only",
        "as_of_date": observation.report_date,
        # Reuse the committed materialization run so overlay lineage matches the in-line path.
        "run_id": observation.materialization_run_id,
        "daily_observation_row_count": observation.daily_observation_row_count,
        "stock_code_count": observation.stock_code_count,
    }


def _coverage_payload(coverage: ChoiceStockMaterializationCoverage) -> dict[str, object]:
    return {
        "as_of_date": coverage.as_of_date,
        "full_coverage": coverage.full_coverage,
        "status": coverage.status,
        "completed_request_items": coverage.completed_request_items,
        "missing_request_items": coverage.missing_request_items,
        "message": coverage.message,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Choice stock materialization into DuckDB.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--duckdb-path")
    parser.add_argument("--catalog-path")
    parser.add_argument("--verify-coverage", action="store_true")
    parser.add_argument("--factor-snapshot", action="store_true")
    parser.add_argument("--factor-max-stock-count", type=int)
    parser.add_argument(
        "--theme-overlay-mode",
        choices=("off", "dry_run", "archive"),
        default="off",
    )
    parser.add_argument(
        "--theme-overlay-only",
        action="store_true",
        help="Skip Choice materialization and refresh only the theme overlay for an already committed as-of date.",
    )
    parser.add_argument(
        "--theme-overlay-source-ip",
        help=(
            "Bind theme-overlay Tushare sockets to this IPv4 source address (bypasses a TLS-breaking default route)."
        ),
    )
    args = parser.parse_args()

    if args.theme_overlay_source_ip and not args.theme_overlay_only:
        parser.error("--theme-overlay-source-ip requires --theme-overlay-only")

    if args.theme_overlay_only:
        if args.theme_overlay_mode == "off":
            parser.error("--theme-overlay-only requires --theme-overlay-mode dry_run or archive")
        if args.factor_snapshot:
            parser.error("--theme-overlay-only cannot be combined with --factor-snapshot")
        payload = _theme_overlay_only_payload(
            as_of_date=args.as_of_date,
            duckdb_path=str(args.duckdb_path or get_settings().duckdb_path),
        )
    elif args.factor_snapshot:
        payload = materialize_choice_stock_factor_snapshot(
            as_of_date=args.as_of_date,
            duckdb_path=args.duckdb_path,
            max_stock_count=args.factor_max_stock_count,
        )
    else:
        payload = materialize_choice_stock_inputs(
            as_of_date=args.as_of_date,
            duckdb_path=args.duckdb_path,
            catalog_path=args.catalog_path,
            enable_tushare_concept_fallback=False,
        )
        if args.verify_coverage:
            coverage_duckdb_path = args.duckdb_path or str(get_settings().duckdb_path)
            coverage = load_choice_stock_materialization_coverage(
                duckdb_path=coverage_duckdb_path,
                as_of_date=args.as_of_date,
            )
            payload["coverage"] = _coverage_payload(coverage)

    if args.theme_overlay_mode == "off":
        theme_overlay = refresh_choice_stock_theme_overlay(mode="off")
    else:
        settings = get_settings()
        parent_run_id = str(payload.get("run_id") or "").strip()
        if not parent_run_id:
            raise ValueError("Choice stock materialization result is missing run_id")
        digest = hashlib.sha256(f"{parent_run_id}|{args.as_of_date}".encode()).hexdigest()[:16]
        source_network = (
            _tushare_source_network(args.theme_overlay_source_ip) if args.theme_overlay_source_ip else nullcontext()
        )
        with source_network:
            theme_overlay = refresh_choice_stock_theme_overlay(
                mode=args.theme_overlay_mode,
                duckdb_path=str(args.duckdb_path or settings.duckdb_path),
                governance_dir=str(settings.governance_path),
                archive_root=str(settings.local_archive_path),
                expected_report_date=args.as_of_date,
                run_id=f"{parent_run_id}:theme-overlay",
                source_version=f"sv_choice_stock_theme_overlay_{digest}",
                vendor_version="vv_tushare_ths_current_overlay_v1",
            )
    payload["theme_overlay"] = theme_overlay
    _emit_json_payload(payload)


if __name__ == "__main__":
    main()
