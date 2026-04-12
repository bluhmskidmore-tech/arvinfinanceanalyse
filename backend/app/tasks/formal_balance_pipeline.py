from __future__ import annotations

import argparse
import json
import os
from contextlib import contextmanager
from typing import Iterator

from backend.app.tasks.balance_analysis_materialize import materialize_balance_analysis_facts
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.ingest import ingest_demo_manifest
from backend.app.tasks.snapshot_materialize import materialize_standard_snapshots


@contextmanager
def _temporary_env(overrides: dict[str, str | None]) -> Iterator[None]:
    previous: dict[str, str | None] = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_formal_balance_pipeline(
    *,
    report_date: str,
    data_root: str | None = None,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    archive_dir: str | None = None,
    fx_source_path: str | None = None,
) -> dict[str, object]:
    with _temporary_env(
        {
            "MOSS_DATA_INPUT_ROOT": data_root,
            "MOSS_FX_OFFICIAL_SOURCE_PATH": fx_source_path,
        }
    ):
        ingest_payload = ingest_demo_manifest.fn(
            data_root=data_root,
            governance_dir=governance_dir,
            archive_dir=archive_dir,
        )
        source_families = [
            source_family
            for source_family in ingest_payload.get("source_families", [])
            if source_family in {"zqtz", "tyw"}
        ] or ["zqtz", "tyw"]
        snapshot_payload = materialize_standard_snapshots.fn(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            source_families=source_families,
            report_date=report_date,
        )
        balance_payload = materialize_balance_analysis_facts.fn(
            report_date=report_date,
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
        )
    return {
        "status": "completed",
        "report_date": report_date,
        "steps": {
            "ingest": ingest_payload,
            "snapshot": snapshot_payload,
            "balance": balance_payload,
        },
    }


run_formal_balance_pipeline = register_actor_once(
    "run_formal_balance_pipeline",
    _run_formal_balance_pipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the formal balance pipeline.")
    parser.add_argument("--report-date", required=True)
    parser.add_argument("--data-root")
    parser.add_argument("--duckdb-path")
    parser.add_argument("--governance-dir")
    parser.add_argument("--archive-dir")
    parser.add_argument("--fx-source-path")
    args = parser.parse_args()

    payload = run_formal_balance_pipeline.fn(
        report_date=args.report_date,
        data_root=args.data_root,
        duckdb_path=args.duckdb_path,
        governance_dir=args.governance_dir,
        archive_dir=args.archive_dir,
        fx_source_path=args.fx_source_path,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
