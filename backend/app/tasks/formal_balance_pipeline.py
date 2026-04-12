from __future__ import annotations

import argparse
import json

from backend.app.tasks.balance_analysis_materialize import materialize_balance_analysis_facts
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.ingest import ingest_demo_manifest
from backend.app.tasks.snapshot_materialize import materialize_standard_snapshots


def _run_formal_balance_pipeline(
    *,
    report_date: str,
    data_root: str | None = None,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    archive_dir: str | None = None,
    fx_source_path: str | None = None,
) -> dict[str, object]:
    source_families = ["zqtz", "tyw"]
    ingest_payload = ingest_demo_manifest.fn(
        data_root=data_root,
        governance_dir=governance_dir,
        archive_dir=archive_dir,
        source_family_allowlist=source_families,
    )
    ingest_batch_id = str(ingest_payload.get("ingest_batch_id") or "").strip()
    if not ingest_batch_id:
        raise ValueError("Formal balance pipeline requires a non-empty ingest_batch_id from ingest.")
    snapshot_payload = materialize_standard_snapshots.fn(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        source_families=source_families,
        ingest_batch_id=ingest_batch_id,
        report_date=report_date,
    )
    balance_payload = materialize_balance_analysis_facts.fn(
        report_date=report_date,
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        ingest_batch_id=ingest_batch_id,
        data_root=data_root,
        fx_source_path=fx_source_path,
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
