from __future__ import annotations

import json
import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import median
from time import perf_counter

import duckdb

from backend.app.repositories.pnl_precompute_state import (
    ensure_pnl_by_business_precompute_state_schema,
    mark_pnl_by_business_precompute_ready_on_connection,
)
from backend.app.repositories.pnl_repo import (
    PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
    PnlRepository,
)


_CUTOFFS = ((2024, "2024-12-31"), (2025, "2025-06-30"), (2025, "2025-12-31"))
_FTP_RATE = Decimal("1.60")
_ADJUSTMENT_VERSION = "sv_pnl_by_business_adjustments_v1:synthetic"


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percentile)))
    return ordered[index]


def _synthetic_payload(cutoff: str) -> dict[str, object]:
    return {
        "as_of_date": cutoff,
        "items": [
            {
                "business_key": f"business-{index:04d}",
                "label": "synthetic fixed-income position",
                "total_pnl": f"{index * 1.25:.2f}",
                "evidence": "x" * 96,
            }
            for index in range(400)
        ],
    }


def _build_synthetic_trusted_read_db(duckdb_path: Path) -> dict[str, int]:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
                report_date varchar,
                instrument_code varchar,
                portfolio_name varchar,
                cost_center varchar,
                accounting_basis varchar,
                currency_basis varchar,
                total_pnl decimal(24, 8)
            )
            """
        )
        fact_rows: list[tuple[object, ...]] = []
        cursor = date(2024, 1, 1)
        end = date(2025, 12, 31)
        while cursor <= end:
            for instrument_index in range(5):
                fact_rows.append(
                    (
                        cursor.isoformat(),
                        f"BOND-{instrument_index}",
                        "SYNTHETIC-BOOK",
                        "SYNTHETIC-CC",
                        "AC",
                        "CNY",
                        str(100 + instrument_index),
                    )
                )
            cursor += timedelta(days=1)
        conn.executemany(
            """
            insert into fact_formal_pnl_fi values (?, ?, ?, ?, ?, ?, ?)
            """,
            fact_rows,
        )
        conn.execute(
            """
            create table fact_pnl_by_business_precompute (
                year integer, as_of_date varchar, result_kind varchar,
                dimension varchar, business_key varchar, payload_json varchar,
                source_version varchar, rule_version varchar, generated_at timestamp
            )
            """
        )
        ensure_pnl_by_business_precompute_state_schema(conn)
        total_payload_bytes = 0
        for year, cutoff in _CUTOFFS:
            payload_json = json.dumps(_synthetic_payload(cutoff), separators=(",", ":"))
            total_payload_bytes += len(payload_json.encode("utf-8"))
            source_version = f"synthetic-source:{cutoff}"
            generated_at = "2026-09-13T00:00:00+00:00"
            conn.execute(
                """
                insert into fact_pnl_by_business_precompute values
                    (?, ?, 'monthly', '', '', ?, ?, ?, ?)
                """,
                [
                    year,
                    cutoff,
                    payload_json,
                    source_version,
                    PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
                    generated_at,
                ],
            )
            mark_pnl_by_business_precompute_ready_on_connection(
                conn,
                year=year,
                as_of_date=cutoff,
                expected_dependency_revision=0,
                source_version=source_version,
                rule_version=PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
                effective_ftp_rate_pct="1.6",
                supplemental_source_version=_ADJUSTMENT_VERSION,
                generated_at=generated_at,
            )
    finally:
        conn.close()
    return {
        "formal_fact_rows": len(fact_rows),
        "precompute_rows": len(_CUTOFFS),
        "payload_bytes": total_payload_bytes,
    }


def test_trusted_reads_do_not_hash_sources_or_mutate_storage(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "trusted-read-no-write.duckdb"
    scale = _build_synthetic_trusted_read_db(duckdb_path)
    repo = PnlRepository(str(duckdb_path))

    def fail_source_hash(**_kwargs):
        raise AssertionError("trusted GET must not calculate the complete source hash")

    monkeypatch.setattr(repo, "pnl_by_business_precompute_source_version", fail_source_hash)
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        before = {
            "facts": conn.execute("select count(*) from fact_formal_pnl_fi").fetchone()[0],
            "results": conn.execute(
                "select count(*) from fact_pnl_by_business_precompute"
            ).fetchone()[0],
            "tables": conn.execute(
                "select count(*) from information_schema.tables where table_schema = 'main'"
            ).fetchone()[0],
        }
    finally:
        conn.close()

    for year, cutoff in _CUTOFFS:
        state = repo.fetch_pnl_by_business_precompute_state(
            year=year,
            as_of_date=cutoff,
            effective_ftp_rate_pct=_FTP_RATE,
            supplemental_source_version=_ADJUSTMENT_VERSION,
        )
        payload = repo.fetch_trusted_pnl_by_business_precompute(
            year=year,
            as_of_date=cutoff,
            result_kind="monthly",
            dimension="",
            business_key="",
            effective_ftp_rate_pct=_FTP_RATE,
            supplemental_source_version=_ADJUSTMENT_VERSION,
        )
        assert state is not None and state["is_ready"] is True
        assert payload is not None and payload["as_of_date"] == cutoff

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        after = {
            "facts": conn.execute("select count(*) from fact_formal_pnl_fi").fetchone()[0],
            "results": conn.execute(
                "select count(*) from fact_pnl_by_business_precompute"
            ).fetchone()[0],
            "tables": conn.execute(
                "select count(*) from information_schema.tables where table_schema = 'main'"
            ).fetchone()[0],
        }
    finally:
        conn.close()
    assert before == after == {
        "facts": scale["formal_fact_rows"],
        "results": scale["precompute_rows"],
        "tables": 5,
    }


def test_trusted_read_latency_30_by_3_rounds(tmp_path) -> None:
    duckdb_path = tmp_path / "trusted-read-performance.duckdb"
    scale = _build_synthetic_trusted_read_db(duckdb_path)
    repo = PnlRepository(str(duckdb_path))

    def read_state(year: int, cutoff: str) -> None:
        state = repo.fetch_pnl_by_business_precompute_state(
            year=year,
            as_of_date=cutoff,
            effective_ftp_rate_pct=_FTP_RATE,
            supplemental_source_version=_ADJUSTMENT_VERSION,
        )
        assert state is not None and state["is_ready"] is True

    def read_payload(year: int, cutoff: str) -> None:
        payload = repo.fetch_trusted_pnl_by_business_precompute(
            year=year,
            as_of_date=cutoff,
            result_kind="monthly",
            dimension="",
            business_key="",
            effective_ftp_rate_pct=_FTP_RATE,
            supplemental_source_version=_ADJUSTMENT_VERSION,
        )
        assert payload is not None and payload["as_of_date"] == cutoff

    cold: dict[str, list[float]] = {"state_ms": [], "payload_ms": []}
    for year, cutoff in _CUTOFFS:
        started = perf_counter()
        read_state(year, cutoff)
        cold["state_ms"].append((perf_counter() - started) * 1000)
        started = perf_counter()
        read_payload(year, cutoff)
        cold["payload_ms"].append((perf_counter() - started) * 1000)

    rounds: list[dict[str, object]] = []
    for round_index in range(3):
        state_times: list[float] = []
        payload_times: list[float] = []
        for sample_index in range(30):
            year, cutoff = _CUTOFFS[sample_index % len(_CUTOFFS)]
            started = perf_counter()
            read_state(year, cutoff)
            state_times.append((perf_counter() - started) * 1000)
            started = perf_counter()
            read_payload(year, cutoff)
            payload_times.append((perf_counter() - started) * 1000)
        rounds.append(
            {
                "round": round_index + 1,
                "samples_per_read": 30,
                "state_ms": {
                    "median": median(state_times),
                    "p95": _percentile(state_times, 0.95),
                    "max": max(state_times),
                },
                "payload_ms": {
                    "median": median(payload_times),
                    "p95": _percentile(payload_times, 0.95),
                    "max": max(payload_times),
                },
            }
        )
    result = {
        "scope": "synthetic_repository_trusted_read",
        "database_path": str(duckdb_path),
        "cutoffs": [cutoff for _year, cutoff in _CUTOFFS],
        "scale": scale,
        "cold": cold,
        "rounds": rounds,
        "limits": (
            "Synthetic local repository timing only; this does not establish a production SLO "
            "or cover HTTP, service, queue, publication, concurrency, or real-data volume."
        ),
    }
    output_path = os.getenv("MOSS_RUNTIME_BENCHMARK_OUTPUT", "").strip()
    if output_path:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    assert all(round_result["state_ms"]["p95"] < 1000 for round_result in rounds)
    assert all(round_result["payload_ms"]["p95"] < 1000 for round_result in rounds)
