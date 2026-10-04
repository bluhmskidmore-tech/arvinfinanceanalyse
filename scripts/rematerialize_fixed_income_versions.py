"""Operator entry point: bring historical fixed-income facts to the configured-current
rule versions.

For every report date in ``fact_formal_bond_analytics_daily`` (or an explicit
selection) the script checks the latest *completed* governance build of
``bond_analytics_materialize`` and ``risk_tensor_materialize``; dates whose build is
not at ``FIXED_INCOME_VERSION_SET`` (``rv_bond_analytics_formal_materialize_v5`` /
``rv_risk_tensor_formal_materialize_v11``) are re-materialized through the registered
task actors (``.fn``), bond first, then risk tensor.

Boundaries: writes only via ``backend.app.tasks`` actors; no API/service write path;
no schema change. The run is resumable — dates already at the current version are
skipped, every date outcome is appended to a JSONL receipt, and a failed date does not
stop the loop unless ``--stop-on-failure`` is given. Historical dates default to
``use_existing_curves_only`` so no vendor fetch is triggered.

Usage (from repo root, repo venv):
  .\\.venv\\Scripts\\python.exe scripts/rematerialize_fixed_income_versions.py --dry-run
  .\\.venv\\Scripts\\python.exe scripts/rematerialize_fixed_income_versions.py --dates 2026-07-31
  .\\.venv\\Scripts\\python.exe scripts/rematerialize_fixed_income_versions.py --limit 50
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.fixed_income_version_set import (  # noqa: E402
    FIXED_INCOME_VERSION_SET,
    MaterializeModuleVersion,
)

MODULE_ORDER: tuple[str, ...] = ("bond_analytics", "risk_tensor")
BOUNDARY = {
    "operator_entrypoint": True,
    "writes_duckdb_via_task": True,
    "uses_api_or_service_write_path": False,
    "changes_schema": False,
}

LineageResolver = Callable[[str, MaterializeModuleVersion], dict[str, object] | None]
Runner = Callable[[str, str], dict[str, object]]


@dataclass(frozen=True)
class DatePlan:
    report_date: str
    modules: tuple[str, ...]
    current_versions: dict[str, str | None] = field(default_factory=dict)


def module_versions() -> dict[str, MaterializeModuleVersion]:
    return {
        "bond_analytics": FIXED_INCOME_VERSION_SET.bond_analytics,
        "risk_tensor": FIXED_INCOME_VERSION_SET.risk_tensor,
    }


BLOCKED_BOND_STALE = "blocked_bond_stale"


def plan_dates(
    report_dates: Iterable[str],
    *,
    modules: Sequence[str],
    resolve_lineage: LineageResolver,
    force: bool = False,
) -> list[DatePlan]:
    """Select (date, modules) pairs whose completed build is not at the current version.

    Risk tensor is always re-run when bond analytics is re-run for the same date:
    its inputs are the bond facts, so a stale risk tensor over fresh bond facts would
    misreport lineage even if its own rule_version already matched. Conversely, when
    only ``risk_tensor`` is requested, a date whose bond facts are not at the current
    version is planned as ``blocked_bond_stale`` instead of stacking a current risk tensor on
    stale bond facts; the executor records it without running anything.
    """

    versions = module_versions()
    requested = set(modules)
    ordered_modules = tuple(name for name in MODULE_ORDER if name in requested)
    plans: list[DatePlan] = []
    for report_date in report_dates:
        current: dict[str, str | None] = {}
        pending: list[str] = []
        bond_version = versions["bond_analytics"]
        bond_lineage = resolve_lineage(report_date, bond_version)
        bond_observed = str((bond_lineage or {}).get("rule_version") or "").strip() or None
        current["bond_analytics"] = bond_observed
        for name in ordered_modules:
            version = versions[name]
            if name == "bond_analytics":
                observed = bond_observed
            else:
                lineage = resolve_lineage(report_date, version)
                observed = str((lineage or {}).get("rule_version") or "").strip() or None
                current[name] = observed
            bond_pending = "bond_analytics" in pending
            if name == "risk_tensor" and "bond_analytics" not in requested and bond_observed != bond_version.rule_version:
                pending.append(BLOCKED_BOND_STALE)
                continue
            if force or observed != version.rule_version or (name == "risk_tensor" and bond_pending):
                pending.append(name)
        if pending:
            plans.append(DatePlan(report_date=report_date, modules=tuple(pending), current_versions=current))
    return plans


def _governance_lineage_resolver(governance_dir: str) -> LineageResolver:
    from backend.app.governance.formal_compute_lineage import resolve_completed_formal_build_lineage

    def resolve(report_date: str, version: MaterializeModuleVersion) -> dict[str, object] | None:
        return resolve_completed_formal_build_lineage(
            governance_dir=governance_dir,
            cache_key=version.cache_key,
            job_name=version.job_name,
            report_date=report_date,
        )

    return resolve


class DuckDBUnavailableError(RuntimeError):
    """The database could not be opened read-only (typically another process holds it)."""


def _fact_report_dates(duckdb_path: str) -> list[str]:
    import duckdb

    try:
        conn = duckdb.connect(duckdb_path, read_only=True)
    except duckdb.Error as exc:
        raise DuckDBUnavailableError(
            f"cannot open {duckdb_path} read-only ({exc}). Stop the API/worker/keepalive processes "
            "that hold the file, or pass --dates explicitly."
        ) from exc
    try:
        rows = conn.execute(
            "select distinct cast(report_date as varchar) from fact_formal_bond_analytics_daily order by 1"
        ).fetchall()
    finally:
        conn.close()
    return [str(row[0])[:10] for row in rows if row and row[0]]


def _normalize_iso_date(value: str, *, field_name: str) -> str:
    """Strict YYYY-MM-DD: strptime alone accepts '2026-7-1', which would then sort
    lexicographically against zero-padded fact dates and silently mis-filter."""
    text = str(value or "").strip()
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD, got {value!r}") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{field_name} must be YYYY-MM-DD (zero-padded), got {value!r}")
    return text


def _task_runner(*, duckdb_path: str, governance_dir: str, prepare_curves: bool) -> Runner:
    from backend.app.tasks.bond_analytics_materialize import materialize_bond_analytics_facts
    from backend.app.tasks.risk_tensor_materialize import materialize_risk_tensor_facts

    def run(module_name: str, report_date: str) -> dict[str, object]:
        stamp = datetime.now(UTC).isoformat()
        if module_name == "bond_analytics":
            return materialize_bond_analytics_facts.fn(
                report_date=report_date,
                duckdb_path=duckdb_path,
                governance_dir=governance_dir,
                run_id=f"rematerialize:bond_analytics_materialize:{report_date}:{stamp}",
                use_existing_curves_only=not prepare_curves,
            )
        if module_name == "risk_tensor":
            return materialize_risk_tensor_facts.fn(
                report_date=report_date,
                duckdb_path=duckdb_path,
                governance_dir=governance_dir,
                run_id=f"rematerialize:risk_tensor_materialize:{report_date}:{stamp}",
            )
        raise ValueError(f"unknown module: {module_name}")

    return run


def execute_plans(
    plans: Sequence[DatePlan],
    *,
    run: Runner,
    receipt_path: Path | None,
    stop_on_failure: bool,
    emit: Callable[[str], None] = print,
) -> dict[str, object]:
    versions = module_versions()
    summary = {"dates": len(plans), "completed": 0, "failed": 0, "skipped_dependents": 0, "failures": []}
    started = time.perf_counter()
    for index, plan in enumerate(plans, start=1):
        bond_failed = False
        for module_name in plan.modules:
            if module_name == BLOCKED_BOND_STALE:
                summary["skipped_dependents"] += 1
                _append_receipt(receipt_path, {
                    "report_date": plan.report_date,
                    "module": "risk_tensor",
                    "status": BLOCKED_BOND_STALE,
                    "previous_rule_version": plan.current_versions.get("risk_tensor"),
                    "target_rule_version": versions["risk_tensor"].rule_version,
                    "bond_rule_version": plan.current_versions.get("bond_analytics"),
                })
                emit(f"[{index}/{len(plans)}] {plan.report_date} risk_tensor {BLOCKED_BOND_STALE} (bond facts not at {versions['bond_analytics'].rule_version})")
                continue
            if module_name == "risk_tensor" and bond_failed:
                summary["skipped_dependents"] += 1
                _append_receipt(receipt_path, {
                    "report_date": plan.report_date,
                    "module": module_name,
                    "status": "skipped_bond_failed",
                    "previous_rule_version": plan.current_versions.get(module_name),
                    "target_rule_version": versions[module_name].rule_version,
                })
                continue
            module_started = time.perf_counter()
            try:
                result = run(module_name, plan.report_date)
                status = str(result.get("status") or "")
            except Exception as exc:  # noqa: BLE001 — recorded per date, loop continues
                result = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
                status = "failed"
            elapsed = round(time.perf_counter() - module_started, 2)
            record = {
                "report_date": plan.report_date,
                "module": module_name,
                "status": status,
                "previous_rule_version": plan.current_versions.get(module_name),
                "target_rule_version": versions[module_name].rule_version,
                "elapsed_seconds": elapsed,
            }
            if status != "completed":
                record["error"] = str(result.get("error") or result.get("error_message") or result)[:500]
                summary["failed"] += 1
                summary["failures"].append({"report_date": plan.report_date, "module": module_name})
                if module_name == "bond_analytics":
                    bond_failed = True
            else:
                summary["completed"] += 1
            _append_receipt(receipt_path, record)
            emit(f"[{index}/{len(plans)}] {plan.report_date} {module_name} {status} ({elapsed}s)")
            if status != "completed" and stop_on_failure:
                summary["stopped_early"] = True
                summary["elapsed_seconds"] = round(time.perf_counter() - started, 1)
                return summary
    summary["elapsed_seconds"] = round(time.perf_counter() - started, 1)
    return summary


def _append_receipt(path: Path | None, record: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({**record, "recorded_at": datetime.now(UTC).isoformat()}, ensure_ascii=False))
        handle.write("\n")


def _select_dates(dates: list[str], *, date_from: str | None, date_to: str | None) -> list[str]:
    """Inclusive ISO-date range filter; callers normalize inputs to YYYY-MM-DD first."""
    return [d for d in dates if (date_from is None or d >= date_from) and (date_to is None or d <= date_to)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--duckdb-path")
    parser.add_argument("--governance-dir")
    parser.add_argument("--dates", nargs="*", help="Explicit report dates (YYYY-MM-DD); default: all bond fact dates.")
    parser.add_argument("--from", dest="date_from", help="Inclusive lower bound (YYYY-MM-DD).")
    parser.add_argument("--to", dest="date_to", help="Inclusive upper bound (YYYY-MM-DD).")
    parser.add_argument("--limit", type=int, help="Stop after this many pending dates.")
    parser.add_argument(
        "--modules",
        default=",".join(MODULE_ORDER),
        help="Comma-separated subset of bond_analytics,risk_tensor (bond always runs before risk).",
    )
    parser.add_argument("--force", action="store_true", help="Re-materialize even when already at the current version.")
    parser.add_argument("--prepare-curves", action="store_true", help="Allow yield-curve preparation (may fetch vendor data).")
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument("--receipt", help="JSONL receipt path (default .codex-tmp/rematerialize/<timestamp>.jsonl).")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without writing data.")
    args = parser.parse_args(argv)

    from backend.app.governance.settings import get_settings

    settings = get_settings()
    duckdb_path = str(Path(args.duckdb_path) if args.duckdb_path else settings.duckdb_path)
    governance_dir = str(Path(args.governance_dir) if args.governance_dir else settings.governance_path)
    modules = [name.strip() for name in str(args.modules).split(",") if name.strip()]
    unknown = sorted(set(modules) - set(MODULE_ORDER))
    if unknown:
        parser.error(f"unknown modules: {unknown}")
    try:
        explicit_dates = [_normalize_iso_date(d, field_name="--dates") for d in (args.dates or [])]
        date_from = _normalize_iso_date(args.date_from, field_name="--from") if args.date_from else None
        date_to = _normalize_iso_date(args.date_to, field_name="--to") if args.date_to else None
    except ValueError as exc:
        parser.error(str(exc))
    if date_from and date_to and date_from > date_to:
        parser.error(f"--from {date_from} is after --to {date_to}")

    try:
        all_dates = explicit_dates or _fact_report_dates(duckdb_path)
    except DuckDBUnavailableError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    candidate_dates = _select_dates(all_dates, date_from=date_from, date_to=date_to)
    plans = plan_dates(
        candidate_dates,
        modules=modules,
        resolve_lineage=_governance_lineage_resolver(governance_dir),
        force=args.force,
    )
    if args.limit is not None:
        plans = plans[: args.limit]

    versions = module_versions()
    header = {
        "duckdb_path": duckdb_path,
        "governance_dir": governance_dir,
        "target_versions": {name: versions[name].rule_version for name in modules},
        "candidate_dates": len(candidate_dates),
        "pending_dates": len(plans),
        "pending_modules": sum(len(plan.modules) for plan in plans),
        "prepare_curves": bool(args.prepare_curves),
        "boundary": dict(BOUNDARY),
    }
    if args.dry_run:
        print(json.dumps({
            **header,
            "status": "dry_run",
            "plan": [
                {"report_date": p.report_date, "modules": list(p.modules), "current": p.current_versions}
                for p in plans
            ],
        }, ensure_ascii=False, indent=2, default=str))
        return 0

    receipt_path = Path(args.receipt) if args.receipt else (
        ROOT / ".codex-tmp" / "rematerialize" / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    )
    print(json.dumps({**header, "receipt": str(receipt_path)}, ensure_ascii=False, default=str), flush=True)
    summary = execute_plans(
        plans,
        run=_task_runner(duckdb_path=duckdb_path, governance_dir=governance_dir, prepare_curves=bool(args.prepare_curves)),
        receipt_path=receipt_path,
        stop_on_failure=bool(args.stop_on_failure),
        emit=lambda line: print(line, flush=True),
    )
    print(json.dumps({"status": "completed" if not summary["failed"] else "completed_with_failures", **summary}, ensure_ascii=False, default=str))
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
