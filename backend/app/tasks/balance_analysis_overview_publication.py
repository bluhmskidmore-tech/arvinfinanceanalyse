from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping
from contextlib import closing, nullcontext
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import duckdb

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import Settings, get_settings
from backend.app.repositories.balance_analysis_publication_state import (
    BalanceAnalysisPublicationNotReady,
    _overview_coverage_dates,
)
from backend.app.repositories.balance_analysis_publication_state import (
    invalidate_balance_analysis_publications_before_fact_change as invalidate_balance_analysis_publications_before_fact_change,
)
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.financial_result_publication_repo import (
    canonical_json_bytes,
    generation_manifest_path,
    read_publication_pointer,
    sha256_bytes,
)
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.source_manifest_repo import (
    AUG31_SOURCE_MANIFEST_DATE,
    AUG31_SOURCE_MANIFEST_DEPENDENCY_KEY,
    aug31_source_manifest_lock,
    selected_aug31_source_manifest_hash,
)
from backend.app.services.balance_analysis_publication_service import (
    BALANCE_ANALYSIS_BASIS_BREAKDOWN_COVERAGE_KEY,
    BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE,
    BALANCE_ANALYSIS_OVERVIEW_COVERAGE_KEY,
    BALANCE_ANALYSIS_OVERVIEW_TABLE,
    BALANCE_ANALYSIS_PORTFOLIO_CONTRACT_VERSION,
    BALANCE_ANALYSIS_PUBLICATION_API_VERSION,
    BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION,
    BalanceAnalysisPublicationConflict,
    _require_snapshot_v3_for_report_date,
    balance_analysis_publication_root,
)
from backend.app.services.balance_analysis_service import (
    BALANCE_ANALYSIS_JOB_NAME,
    CACHE_KEY,
    RULE_VERSION,
    _balance_analysis_basis_breakdown_envelope_uncached,
    _balance_analysis_overview_envelope_uncached,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.financial_result_publication import (
    FinancialPublicationPlan,
    FinancialPublicationReceipt,
    FinancialTablePublicationSpec,
    publish_financial_result,
)

_POSITION_SCOPES: tuple[Literal["asset", "liability", "all"], ...] = (
    "asset",
    "liability",
    "all",
)
_CURRENCY_BASES: tuple[Literal["native", "CNY"], ...] = ("native", "CNY")
_FACT_TABLES = (
    ("zqtz", "fact_formal_zqtz_balance_daily"),
    ("tyw", "fact_formal_tyw_balance_daily"),
)
BALANCE_ANALYSIS_OVERVIEW_PUBLICATION_JOB_NAME = (
    "balance_analysis_overview_publication"
)


class BalanceAnalysisSnapshotRuleIncompatible(BalanceAnalysisPublicationNotReady):
    pass


class BalanceAnalysisSnapshotCohortStale(BalanceAnalysisPublicationNotReady):
    pass


@dataclass(frozen=True)
class _BalancePublicationAttempt:
    series_run_id: str
    run_id: str
    number: int
    expected_previous_generation: str | None


@dataclass(frozen=True)
class _BalancePublicationOutcome:
    receipt: FinancialPublicationReceipt
    attempt: _BalancePublicationAttempt


def publish_balance_analysis_overview(
    settings: Settings,
    *,
    report_date: str,
    run_id: str,
    expected_previous_generation: str | None,
) -> FinancialPublicationReceipt:
    return _publish_balance_analysis_overview(
        settings,
        report_date=report_date,
        run_id=run_id,
        expected_previous_generation=expected_previous_generation,
        expected_source_build_run_id=None,
    ).receipt


def _publish_balance_analysis_overview(
    settings: Settings,
    *,
    report_date: str,
    run_id: str,
    expected_previous_generation: str | None,
    expected_source_build_run_id: str | None,
) -> _BalancePublicationOutcome:
    normalized_date = date.fromisoformat(report_date).isoformat()
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        raise ValueError("Balance-analysis publication requires a run_id.")
    publication_root = balance_analysis_publication_root(settings)
    publication_root.mkdir(parents=True, exist_ok=True)
    active_path = Path(settings.duckdb_path).resolve()
    if not active_path.is_file():
        raise FileNotFoundError(f"Balance-analysis source DuckDB does not exist: {active_path}")
    writer_lock = resolve_duckdb_writer_lock(active_path, ttl_seconds=7200)
    # Keep the active database open read-only until the publication pointer CAS
    # completes. DuckDB rejects an uncoordinated read-write connection while this
    # anchor is alive, closing the migration/write gap after the final snapshot.
    with acquire_lock(writer_lock, base_dir=active_path.parent), closing(
        duckdb.connect(str(active_path), read_only=True)
    ):
        _reject_historical_current_regression(publication_root, normalized_date)
        dependencies = _active_dependency_snapshot(
            duckdb_path=active_path,
            governance_dir=str(settings.governance_path),
            report_date=normalized_date,
        )
        try:
            _require_snapshot_v3_for_report_date(
                dependencies,
                report_date=normalized_date,
            )
        except BalanceAnalysisPublicationConflict as exc:
            raise BalanceAnalysisSnapshotRuleIncompatible(str(exc)) from exc
        _require_current_aug31_snapshot_cohort(
            duckdb_path=active_path,
            governance_dir=Path(settings.governance_path),
            report_date=normalized_date,
            dependencies=dependencies,
        )
        if normalized_date == AUG31_SOURCE_MANIFEST_DATE:
            dependencies[AUG31_SOURCE_MANIFEST_DEPENDENCY_KEY] = (
                selected_aug31_source_manifest_hash(settings.governance_path)
            )
        if (
            expected_source_build_run_id is not None
            and dependencies["balance.build.run_id"]
            != expected_source_build_run_id
        ):
            raise BalanceAnalysisPublicationNotReady(
                "Balance-analysis publication message no longer matches the latest source build."
            )
        attempt = (
            _resolve_or_reserve_publication_attempt(
                settings,
                publication_root=publication_root,
                report_date=normalized_date,
                source_build_run_id=expected_source_build_run_id,
            )
            if expected_source_build_run_id is not None
            else _BalancePublicationAttempt(
                series_run_id=normalized_run_id,
                run_id=normalized_run_id,
                number=1,
                expected_previous_generation=expected_previous_generation,
            )
        )
        with tempfile.TemporaryDirectory(
            prefix=".balance-overview-stage-",
            dir=publication_root,
        ) as stage_dir:
            stage_path = Path(stage_dir) / "balance-overview-source.duckdb"
            prepare_receipt = _build_stage_database(
                stage_path=stage_path,
                duckdb_path=active_path,
                governance_dir=str(settings.governance_path),
                report_date=normalized_date,
                dependencies=dependencies,
                run_id=attempt.run_id,
            )
            cohort_lock = (
                acquire_lock(
                    aug31_source_manifest_lock(settings.governance_path),
                    base_dir=settings.governance_path,
                )
                if normalized_date == AUG31_SOURCE_MANIFEST_DATE
                else nullcontext()
            )
            with cohort_lock:
                after = _active_dependency_snapshot(
                    duckdb_path=active_path,
                    governance_dir=str(settings.governance_path),
                    report_date=normalized_date,
                )
                _require_current_aug31_snapshot_cohort(
                    duckdb_path=active_path,
                    governance_dir=Path(settings.governance_path),
                    report_date=normalized_date,
                    dependencies=after,
                )
                if normalized_date == AUG31_SOURCE_MANIFEST_DATE:
                    after[AUG31_SOURCE_MANIFEST_DEPENDENCY_KEY] = (
                        selected_aug31_source_manifest_hash(settings.governance_path)
                    )
                if (
                    normalized_date == AUG31_SOURCE_MANIFEST_DATE
                    and after[AUG31_SOURCE_MANIFEST_DEPENDENCY_KEY]
                    != dependencies[AUG31_SOURCE_MANIFEST_DEPENDENCY_KEY]
                ):
                    raise BalanceAnalysisSnapshotCohortStale(
                        "2026-08-31 selected source manifest changed while the overview publication was prepared."
                    )
                if after != dependencies:
                    raise BalanceAnalysisPublicationNotReady(
                        "Balance-analysis dependencies changed while the overview publication was prepared."
                    )
                plan = _build_publication_plan(
                    report_date=normalized_date,
                    run_id=attempt.run_id,
                    expected_previous_generation=attempt.expected_previous_generation,
                    dependencies=dependencies,
                    prepare_receipt=prepare_receipt,
                )
                return _BalancePublicationOutcome(
                    receipt=publish_financial_result(
                        source_duckdb_path=stage_path,
                        publication_root=publication_root,
                        plan=plan,
                    ),
                    attempt=attempt,
                )


def schedule_balance_analysis_overview_publication(
    settings: Settings,
    *,
    report_date: str,
    source_build_run_id: str,
    duckdb_path: Path | str,
    governance_dir: Path | str,
) -> dict[str, object]:
    if not settings.balance_analysis_publication_enabled:
        return {"status": "disabled"}
    if Path(duckdb_path).resolve() != Path(settings.duckdb_path).resolve():
        raise RuntimeError("Balance-analysis publication source path does not match active settings.")
    if Path(governance_dir).resolve() != Path(settings.governance_path).resolve():
        raise RuntimeError(
            "Balance-analysis publication governance path does not match active settings."
        )
    normalized_date = date.fromisoformat(report_date).isoformat()
    normalized_source_run_id = str(source_build_run_id or "").strip()
    if not normalized_source_run_id:
        raise ValueError("Balance-analysis publication dispatch requires a source build run_id.")
    publication_run_id = _publication_run_id(normalized_source_run_id)
    queued_receipt: dict[str, object] = {
        "status": "queued",
        "job_name": BALANCE_ANALYSIS_OVERVIEW_PUBLICATION_JOB_NAME,
        "cache_key": BALANCE_ANALYSIS_OVERVIEW_PUBLICATION_JOB_NAME,
        "run_id": publication_run_id,
        "source_build_run_id": normalized_source_run_id,
        "report_date": normalized_date,
        "expected_previous_generation": None,
        "predecessor_resolution": "reserved_by_publication_actor",
        "queued_at": datetime.now().astimezone().isoformat(),
    }
    governance = GovernanceRepository(base_dir=Path(settings.governance_path))
    governance.append(CACHE_BUILD_RUN_STREAM, queued_receipt)
    try:
        message = publish_balance_analysis_overview_actor.send(
            report_date=normalized_date,
            source_build_run_id=normalized_source_run_id,
        )
    except Exception as exc:
        governance.append(
            CACHE_BUILD_RUN_STREAM,
            {
                **queued_receipt,
                "status": "failed",
                "failure_category": "publication_dispatch_failed",
                "error_message": str(exc),
                "finished_at": datetime.now().astimezone().isoformat(),
            },
        )
        raise
    return {
        **queued_receipt,
        "message_id": str(message.message_id),
    }


def _publish_balance_analysis_overview_actor(
    *,
    report_date: str,
    source_build_run_id: str,
) -> dict[str, object]:
    settings = get_settings()
    normalized_date = date.fromisoformat(report_date).isoformat()
    normalized_source_run_id = str(source_build_run_id or "").strip()
    if not normalized_source_run_id:
        raise ValueError("Balance-analysis publication actor requires a source build run_id.")
    publication_run_id = _publication_run_id(normalized_source_run_id)
    started_at = datetime.now().astimezone().isoformat()
    try:
        outcome = _publish_balance_analysis_overview(
            settings,
            report_date=normalized_date,
            run_id=publication_run_id,
            expected_previous_generation=None,
            expected_source_build_run_id=normalized_source_run_id,
        )
    except Exception as exc:
        if isinstance(exc, BalanceAnalysisSnapshotRuleIncompatible):
            failure_category = "snapshot_rule_incompatible"
        elif isinstance(exc, BalanceAnalysisSnapshotCohortStale):
            failure_category = "snapshot_cohort_stale"
        else:
            failure_category = "publication_failed"
        failed = {
            "status": "failed",
            "job_name": BALANCE_ANALYSIS_OVERVIEW_PUBLICATION_JOB_NAME,
            "cache_key": BALANCE_ANALYSIS_OVERVIEW_PUBLICATION_JOB_NAME,
            "run_id": publication_run_id,
            "source_build_run_id": normalized_source_run_id,
            "report_date": normalized_date,
            **_latest_publication_attempt_fields(
                settings,
                series_run_id=publication_run_id,
            ),
            "failure_category": failure_category,
            "error_message": str(exc),
            "started_at": started_at,
            "finished_at": datetime.now().astimezone().isoformat(),
        }
        _append_publication_run_receipt(settings, failed)
        if failure_category != "publication_failed":
            return failed
        raise
    receipt = outcome.receipt
    attempt = outcome.attempt
    completed = {
        "status": "completed",
        "job_name": BALANCE_ANALYSIS_OVERVIEW_PUBLICATION_JOB_NAME,
        "cache_key": BALANCE_ANALYSIS_OVERVIEW_PUBLICATION_JOB_NAME,
        "run_id": attempt.run_id,
        "publication_series_run_id": publication_run_id,
        "publication_attempt": attempt.number,
        "source_build_run_id": normalized_source_run_id,
        "report_date": normalized_date,
        "expected_previous_generation": attempt.expected_previous_generation,
        "generation": receipt.generation,
        "manifest_sha256": receipt.manifest_sha256,
        "publication_status": receipt.status,
        "recovered_after_commit": receipt.recovered_after_commit,
        "publication_outcome": (
            "already_published" if receipt.recovered_after_commit else "published"
        ),
        "started_at": started_at,
        "finished_at": datetime.now().astimezone().isoformat(),
    }
    _append_publication_run_receipt(settings, completed)
    return completed


def _publication_run_id(source_build_run_id: str) -> str:
    return (
        f"{BALANCE_ANALYSIS_OVERVIEW_PUBLICATION_JOB_NAME}:"
        f"{source_build_run_id}"
    )


def _publication_generation(report_date: str, run_id: str) -> str:
    identity = canonical_json_bytes({
        "run_id": run_id,
        "publication_contract_version": BALANCE_ANALYSIS_PORTFOLIO_CONTRACT_VERSION,
    })
    return (
        f"balance-overview-{report_date.replace('-', '')}-"
        f"{sha256_bytes(identity)[:16]}"
    )


def _resolve_or_reserve_publication_attempt(
    settings: Settings,
    *,
    publication_root: Path,
    report_date: str,
    source_build_run_id: str,
) -> _BalancePublicationAttempt:
    series_run_id = _publication_run_id(source_build_run_id)
    governance = GovernanceRepository(base_dir=Path(settings.governance_path))
    latest = _latest_publication_attempt(
        governance,
        series_run_id=series_run_id,
        report_date=report_date,
        source_build_run_id=source_build_run_id,
    )
    pointer = read_publication_pointer(publication_root, require_valid=False)
    current_generation = str(pointer["generation"]) if pointer is not None else None
    if latest is not None:
        target_generation = _publication_generation(report_date, latest.run_id)
        if current_generation in {
            latest.expected_previous_generation,
            target_generation,
        }:
            return latest
        attempt_number = latest.number + 1
    else:
        attempt_number = 1
    attempt_run_id = (
        series_run_id
        if attempt_number == 1
        else f"{series_run_id}:attempt-{attempt_number}"
    )
    attempt = _BalancePublicationAttempt(
        series_run_id=series_run_id,
        run_id=attempt_run_id,
        number=attempt_number,
        expected_previous_generation=current_generation,
    )
    governance.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "status": "running",
            "phase": "publication_attempt_reserved",
            "job_name": BALANCE_ANALYSIS_OVERVIEW_PUBLICATION_JOB_NAME,
            "cache_key": BALANCE_ANALYSIS_OVERVIEW_PUBLICATION_JOB_NAME,
            "run_id": attempt.run_id,
            "publication_series_run_id": attempt.series_run_id,
            "publication_attempt": attempt.number,
            "source_build_run_id": source_build_run_id,
            "report_date": report_date,
            "expected_previous_generation": attempt.expected_previous_generation,
            "started_at": datetime.now().astimezone().isoformat(),
        },
    )
    return attempt


def _latest_publication_attempt(
    governance: GovernanceRepository,
    *,
    series_run_id: str,
    report_date: str,
    source_build_run_id: str,
) -> _BalancePublicationAttempt | None:
    for row in reversed(governance.read_all(CACHE_BUILD_RUN_STREAM)):
        if row.get("phase") != "publication_attempt_reserved":
            continue
        if str(row.get("publication_series_run_id") or "") != series_run_id:
            continue
        if str(row.get("report_date") or "") != report_date:
            raise BalanceAnalysisPublicationNotReady(
                "Balance-analysis publication attempt report date does not match its series."
            )
        if str(row.get("source_build_run_id") or "") != source_build_run_id:
            raise BalanceAnalysisPublicationNotReady(
                "Balance-analysis publication attempt source build does not match its series."
            )
        run_id = str(row.get("run_id") or "").strip()
        raw_number = row.get("publication_attempt")
        if isinstance(raw_number, bool) or not isinstance(raw_number, int):
            raise BalanceAnalysisPublicationNotReady(
                "Balance-analysis publication attempt number is invalid."
            )
        number = raw_number
        if not run_id or number < 1:
            raise BalanceAnalysisPublicationNotReady(
                "Balance-analysis publication attempt receipt is incomplete."
            )
        expected = row.get("expected_previous_generation")
        return _BalancePublicationAttempt(
            series_run_id=series_run_id,
            run_id=run_id,
            number=number,
            expected_previous_generation=str(expected) if expected is not None else None,
        )
    return None


def _latest_publication_attempt_fields(
    settings: Settings,
    *,
    series_run_id: str,
) -> dict[str, object]:
    for row in reversed(
        GovernanceRepository(base_dir=Path(settings.governance_path)).read_all(
            CACHE_BUILD_RUN_STREAM
        )
    ):
        if (
            row.get("phase") == "publication_attempt_reserved"
            and str(row.get("publication_series_run_id") or "") == series_run_id
        ):
            return {
                "run_id": str(row.get("run_id") or series_run_id),
                "publication_series_run_id": series_run_id,
                "publication_attempt": row.get("publication_attempt"),
                "expected_previous_generation": row.get(
                    "expected_previous_generation"
                ),
            }
    return {
        "run_id": series_run_id,
        "publication_series_run_id": series_run_id,
        "publication_attempt": None,
        "expected_previous_generation": None,
    }


def _append_publication_run_receipt(
    settings: Settings,
    payload: Mapping[str, object],
) -> None:
    GovernanceRepository(base_dir=Path(settings.governance_path)).append(
        CACHE_BUILD_RUN_STREAM,
        dict(payload),
    )


def _reject_historical_current_regression(
    publication_root: Path,
    report_date: str,
) -> None:
    pointer = read_publication_pointer(publication_root, require_valid=False)
    if pointer is None:
        return
    generation = str(pointer.get("generation") or "")
    manifest_path = generation_manifest_path(publication_root, generation)
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise BalanceAnalysisPublicationNotReady(
            "Current balance-analysis publication manifest is unreadable."
        ) from exc
    if not isinstance(manifest, Mapping):
        raise BalanceAnalysisPublicationNotReady(
            "Current balance-analysis publication manifest is invalid."
        )
    if sha256_bytes(manifest_bytes) != str(pointer.get("manifest_sha256") or ""):
        raise BalanceAnalysisPublicationNotReady(
            "Current balance-analysis publication manifest digest does not match its pointer."
        )
    current_dates = _overview_coverage_dates(manifest)
    if not current_dates:
        raise BalanceAnalysisPublicationNotReady(
            "Current balance-analysis publication has no overview coverage date."
        )
    if report_date < max(current_dates):
        raise BalanceAnalysisPublicationNotReady(
            "A historical balance-analysis report date cannot replace the current publication."
        )


def _active_dependency_snapshot(
    *,
    duckdb_path: Path,
    governance_dir: str,
    report_date: str,
) -> dict[str, str]:
    dependencies: dict[str, str] = {
        "balance.rule_version": RULE_VERSION,
        "balance.publication_contract_version": BALANCE_ANALYSIS_PORTFOLIO_CONTRACT_VERSION,
    }
    fact_source_versions: set[str] = set()
    currencies: set[str] = set()
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        for family, table_name in _FACT_TABLES:
            row_count = _query_count(
                conn,
                f"select count(*) from {table_name} where cast(report_date as varchar) = ?",
                [report_date],
            )
            if row_count <= 0:
                raise BalanceAnalysisPublicationNotReady(
                    f"Balance-analysis {family} facts are missing for report_date={report_date}."
                )
            source_versions = _single_complete_lineage_values(
                conn,
                table_name=table_name,
                column_name="source_version",
                report_date=report_date,
            )
            fact_source_versions.update(source_versions)
            dependencies[f"balance.{family}.source_versions"] = _canonical_string_list(
                source_versions
            )
            dependencies[f"balance.{family}.ingest_batch_ids"] = _canonical_string_list(
                _single_complete_lineage_values(
                    conn,
                    table_name=table_name,
                    column_name="ingest_batch_id",
                    report_date=report_date,
                )
            )
            # Fact rule_version identifies the selected source snapshot rule. The
            # balance materializer rule is independently bound by build/manifest below.
            rule_versions = _single_complete_lineage_values(
                conn,
                table_name=table_name,
                column_name="rule_version",
                report_date=report_date,
            )
            dependencies[f"balance.{family}.rule_versions"] = _canonical_string_list(
                rule_versions
            )
            currencies.update(
                _distinct_non_empty(
                    conn,
                    table_name=table_name,
                    column_name="currency_code",
                    report_date=report_date,
                    extra_where="currency_basis = 'native'",
                )
            )
    finally:
        conn.close()

    repo = BalanceAnalysisRepository(str(duckdb_path))
    fx_versions = {
        repo.lookup_formal_fx_rate(report_date=report_date, base_currency=currency).source_version
        for currency in currencies
    }
    dependencies["balance.fx.source_versions"] = _canonical_string_list(
        sorted(value for value in fx_versions if value)
    )
    expected_combined_source_version = "__".join(
        sorted(
            fact_source_versions
            | {value for value in fx_versions if value and value != "sv_fx_identity"}
        )
    )
    if not expected_combined_source_version:
        raise BalanceAnalysisPublicationNotReady(
            "Balance-analysis combined source version is empty."
        )
    dependencies["balance.combined_source_version"] = expected_combined_source_version

    governance = GovernanceRepository(base_dir=governance_dir)
    completed = governance.read_latest_completed_run(
        CACHE_KEY,
        job_name=BALANCE_ANALYSIS_JOB_NAME,
        report_date=report_date,
        require_source_version=True,
    )
    manifest = governance.read_latest_manifest(CACHE_KEY, report_date=report_date)
    if completed is None or manifest is None:
        raise BalanceAnalysisPublicationNotReady(
            f"Balance-analysis completed build evidence is missing for report_date={report_date}."
        )
    if str(completed.get("status") or "").lower() != "completed":
        raise BalanceAnalysisPublicationNotReady(
            f"Balance-analysis build is not completed for report_date={report_date}."
        )
    for prefix, evidence in (("build", completed), ("manifest", manifest)):
        for key in ("run_id", "source_version", "rule_version"):
            value = str(evidence.get(key) or "").strip()
            if not value:
                raise BalanceAnalysisPublicationNotReady(
                    f"Balance-analysis {prefix} evidence is missing {key}."
                )
            dependencies[f"balance.{prefix}.{key}"] = value
    finished_at = str(completed.get("finished_at") or "").strip()
    if not finished_at:
        raise BalanceAnalysisPublicationNotReady(
            "Balance-analysis completed build evidence has no finished_at timestamp."
        )
    dependencies["balance.build.finished_at"] = finished_at
    dependencies["balance.manifest.sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    if dependencies["balance.build.run_id"] != dependencies["balance.manifest.run_id"]:
        raise BalanceAnalysisPublicationNotReady(
            "Balance-analysis build and manifest belong to different runs."
        )
    if (
        dependencies["balance.build.source_version"]
        != expected_combined_source_version
        or dependencies["balance.manifest.source_version"]
        != expected_combined_source_version
    ):
        raise BalanceAnalysisPublicationNotReady(
            "Balance-analysis fact and FX versions do not match the completed build evidence."
        )
    if dependencies["balance.build.rule_version"] != RULE_VERSION:
        raise BalanceAnalysisPublicationNotReady(
            "Balance-analysis completed build rule version is incompatible."
        )
    if dependencies["balance.manifest.rule_version"] != RULE_VERSION:
        raise BalanceAnalysisPublicationNotReady(
            "Balance-analysis manifest rule version is incompatible."
        )
    if report_date == AUG31_SOURCE_MANIFEST_DATE:
        from backend.app.tasks.balance_analysis_materialize import (
            _DIRECT_SNAPSHOT_GUARD_RULE_VERSION,
            _recorded_materialize_run_identity,
        )

        identity = _recorded_materialize_run_identity(
            governance,
            run_id=dependencies["balance.build.run_id"],
        )
        if (
            identity is None
            or identity.get("job_name") != BALANCE_ANALYSIS_JOB_NAME
            or identity.get("cache_key") != CACHE_KEY
            or identity.get("report_date") != report_date
            or identity.get("snapshot_rule_version_guard")
            != _DIRECT_SNAPSHOT_GUARD_RULE_VERSION
        ):
            raise BalanceAnalysisSnapshotRuleIncompatible(
                "2026-08-31 completed balance-analysis build lacks the current snapshot rule guard."
            )
    return dependencies


def _require_current_aug31_snapshot_cohort(
    *,
    duckdb_path: Path,
    governance_dir: Path,
    report_date: str,
    dependencies: Mapping[str, str],
) -> None:
    if report_date != "2026-08-31":
        return

    # Materialization imports this publication task for dispatch, so keep the
    # reciprocal read-only cohort check local to the publishing call.
    from backend.app.tasks.balance_analysis_materialize import (
        _load_direct_aug31_snapshot_rows,
        _require_direct_aug31_completed_facts,
    )

    try:
        repo, zqtz_batch, tyw_batch, zqtz_rows, tyw_rows = (
            _load_direct_aug31_snapshot_rows(
                duckdb_file=duckdb_path,
                governance_path=governance_dir,
                requested_ingest_batch_id=None,
            )
        )
    except ValueError as exc:
        raise BalanceAnalysisSnapshotCohortStale(
            "2026-08-31 selected snapshot lineage is unavailable for publication."
        ) from exc
    try:
        _require_direct_aug31_completed_facts(
            repo=repo,
            zqtz_snapshots=zqtz_rows,
            tyw_snapshots=tyw_rows,
        )
    except RuntimeError as exc:
        raise BalanceAnalysisSnapshotCohortStale(
            "2026-08-31 balance-analysis facts do not match the selected snapshot cohort."
        ) from exc

    for family, batch_id, rows in (
        ("zqtz", zqtz_batch, zqtz_rows),
        ("tyw", tyw_batch, tyw_rows),
    ):
        expected_lineage = {
            f"balance.{family}.ingest_batch_ids": _canonical_string_list([batch_id]),
            f"balance.{family}.source_versions": _canonical_string_list(
                sorted({row.source_version for row in rows})
            ),
        }
        if any(dependencies.get(key) != value for key, value in expected_lineage.items()):
            raise BalanceAnalysisSnapshotCohortStale(
                f"2026-08-31 {family} published dependencies do not match the selected snapshot cohort."
            )


def _build_stage_database(
    *,
    stage_path: Path,
    duckdb_path: Path,
    governance_dir: str,
    report_date: str,
    dependencies: Mapping[str, str],
    run_id: str,
) -> dict[str, object]:
    dependency_json = canonical_json_bytes(dict(dependencies)).decode("utf-8")
    rows_by_table: dict[str, list[tuple[str, str, str, str, str, str, str]]] = {
        BALANCE_ANALYSIS_OVERVIEW_TABLE: [],
        BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE: [],
    }
    quality_checks: list[dict[str, str]] = []
    for position_scope in _POSITION_SCOPES:
        for currency_basis in _CURRENCY_BASES:
            for surface, table, build_envelope in (
                (
                    "overview", BALANCE_ANALYSIS_OVERVIEW_TABLE,
                    _balance_analysis_overview_envelope_uncached,
                ),
                (
                    "basis_breakdown", BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE,
                    _balance_analysis_basis_breakdown_envelope_uncached,
                ),
            ):
                envelope = build_envelope(
                    duckdb_path=str(duckdb_path),
                    governance_dir=governance_dir,
                    report_date=report_date,
                    position_scope=position_scope,
                    currency_basis=currency_basis,
                )
                meta = envelope.get("result_meta")
                if not isinstance(meta, Mapping):
                    raise BalanceAnalysisPublicationNotReady(
                        f"Balance-analysis {surface} envelope has no result metadata."
                    )
                if (
                    meta.get("basis") != "formal"
                    or meta.get("formal_use_allowed") is not True
                    or meta.get("quality_flag") != "ok"
                    or meta.get("fallback_mode") not in (None, "none")
                ):
                    raise BalanceAnalysisPublicationNotReady(
                        f"Balance-analysis {surface} is not eligible for formal publication."
                    )
                payload_json = canonical_json_bytes(envelope).decode("utf-8")
                rows_by_table[table].append(
                    (
                        report_date,
                        position_scope,
                        currency_basis,
                        payload_json,
                        sha256_bytes(payload_json.encode("utf-8")),
                        dependency_json,
                        BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION,
                    )
                )
                quality_checks.append(
                    {"name": f"{surface}_{position_scope}_{currency_basis}", "status": "passed"}
                )
    conn = duckdb.connect(str(stage_path))
    try:
        for table, rows in rows_by_table.items():
            conn.execute(
                f"""
                create table {table} (
                  report_date varchar not null,
                  position_scope varchar not null,
                  currency_basis varchar not null,
                  payload_json varchar not null,
                  payload_sha256 varchar not null,
                  dependency_versions_json varchar not null,
                  schema_version varchar not null,
                  primary key (report_date, position_scope, currency_basis)
                )
                """
            )
            conn.executemany(
                f"insert into {table} values (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        conn.execute("checkpoint")
    finally:
        conn.close()
    return {
        "status": "completed",
        "name": "balance_analysis_overview_prepare",
        "run_id": run_id,
        "report_date": report_date,
        "records": sum(len(rows) for rows in rows_by_table.values()),
        "dependency_versions": dict(dependencies),
        "quality_checks": quality_checks,
        "prepared_at": datetime.now().astimezone().isoformat(),
    }


def _build_publication_plan(
    *,
    report_date: str,
    run_id: str,
    expected_previous_generation: str | None,
    dependencies: Mapping[str, str],
    prepare_receipt: Mapping[str, object],
) -> FinancialPublicationPlan:
    raw_quality_checks = prepare_receipt.get("quality_checks")
    if not isinstance(raw_quality_checks, list) or any(
        not isinstance(item, Mapping) for item in raw_quality_checks
    ):
        raise BalanceAnalysisPublicationNotReady(
            "Balance-analysis preparation quality checks are invalid."
        )
    quality_checks = tuple(dict(item) for item in raw_quality_checks)
    generation = _publication_generation(report_date, run_id)
    build_result = {
        "status": "completed",
        "report_date": report_date,
        "run_id": dependencies["balance.build.run_id"],
        "source_version": dependencies["balance.build.source_version"],
        "rule_version": dependencies["balance.build.rule_version"],
        "finished_at": dependencies["balance.build.finished_at"],
    }
    stable_prepare_result = {
        key: prepare_receipt[key]
        for key in (
            "status",
            "name",
            "run_id",
            "report_date",
            "records",
            "dependency_versions",
            "quality_checks",
        )
    }
    return FinancialPublicationPlan(
        generation=generation,
        expected_previous_generation=expected_previous_generation,
        tables=(
            FinancialTablePublicationSpec(
                name=BALANCE_ANALYSIS_OVERVIEW_TABLE,
                date_column="report_date",
                required_dates=(report_date,),
                minimum_rows_per_date=len(_POSITION_SCOPES) * len(_CURRENCY_BASES),
                minimum_total_rows=len(_POSITION_SCOPES) * len(_CURRENCY_BASES),
            ),
            FinancialTablePublicationSpec(
                name=BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE,
                date_column="report_date",
                required_dates=(report_date,),
                minimum_rows_per_date=len(_POSITION_SCOPES) * len(_CURRENCY_BASES),
                minimum_total_rows=len(_POSITION_SCOPES) * len(_CURRENCY_BASES),
            ),
        ),
        required_steps=("balance_analysis_materialize", "balance_analysis_overview_prepare"),
        step_receipts=(
            {
                "name": "balance_analysis_materialize",
                "status": "completed",
                "result": build_result,
            },
            {
                "name": "balance_analysis_overview_prepare",
                "status": "completed",
                "result": stable_prepare_result,
            },
        ),
        required_dependency_keys=tuple(sorted(dependencies)),
        dependency_versions=dict(dependencies),
        coverage_dates={
            BALANCE_ANALYSIS_OVERVIEW_COVERAGE_KEY: (report_date,),
            BALANCE_ANALYSIS_BASIS_BREAKDOWN_COVERAGE_KEY: (report_date,),
        },
        supported_api_versions=(BALANCE_ANALYSIS_PUBLICATION_API_VERSION,),
        supported_schema_versions=(BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION,),
        quality={
            "status": "passed",
            "checks": quality_checks,
        },
        source_dependency_validator=_stage_dependency_validator(dict(dependencies)),
    )


def _stage_dependency_validator(
    expected: dict[str, str],
):
    def validate(conn: duckdb.DuckDBPyConnection) -> Mapping[str, str]:
        rows = conn.execute(
            f"select dependency_versions_json from {BALANCE_ANALYSIS_OVERVIEW_TABLE} "
            f"union select dependency_versions_json from {BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE}"
        ).fetchall()
        if len(rows) != 1:
            raise BalanceAnalysisPublicationNotReady(
                "Balance-analysis stage contains inconsistent dependency snapshots."
            )
        raw = json.loads(str(rows[0][0] or ""))
        if not isinstance(raw, dict):
            raise BalanceAnalysisPublicationNotReady(
                "Balance-analysis stage dependency snapshot is invalid."
            )
        normalized = {str(key): str(value) for key, value in raw.items()}
        if normalized != expected:
            raise BalanceAnalysisPublicationNotReady(
                "Balance-analysis stage dependency snapshot changed before sealing."
            )
        return normalized

    return validate


def _distinct_non_empty(
    conn: duckdb.DuckDBPyConnection,
    *,
    table_name: str,
    column_name: str,
    report_date: str,
    extra_where: str | None = None,
) -> list[str]:
    predicate = f" and {extra_where}" if extra_where else ""
    rows = conn.execute(
        f"""
        select distinct cast({column_name} as varchar)
        from {table_name}
        where cast(report_date as varchar) = ?{predicate}
          and trim(coalesce(cast({column_name} as varchar), '')) <> ''
        order by 1
        """,
        [report_date],
    ).fetchall()
    values = [str(row[0]) for row in rows]
    if not values:
        raise BalanceAnalysisPublicationNotReady(
            f"Balance-analysis dependency {table_name}.{column_name} is missing."
        )
    return values


def _canonical_string_list(values: list[str]) -> str:
    if not values:
        raise BalanceAnalysisPublicationNotReady(
            "Balance-analysis dependency version list cannot be empty."
        )
    return canonical_json_bytes(values).decode("utf-8")


def _single_complete_lineage_values(
    conn: duckdb.DuckDBPyConnection,
    *,
    table_name: str,
    column_name: str,
    report_date: str,
) -> list[str]:
    values = _distinct_non_empty(
        conn,
        table_name=table_name,
        column_name=column_name,
        report_date=report_date,
    )
    missing_count = _query_count(
        conn,
        f"""
        select count(*)
        from {table_name}
        where cast(report_date as varchar) = ?
          and ({column_name} is null or trim(cast({column_name} as varchar)) = '')
        """,
        [report_date],
    )
    if missing_count or len(values) != 1:
        raise BalanceAnalysisPublicationNotReady(
            f"Balance-analysis {table_name}.{column_name} must be complete and single-valued."
        )
    return values


def _query_count(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    parameters: list[str],
) -> int:
    row = conn.execute(sql, parameters).fetchone()
    if (
        row is None
        or len(row) != 1
        or isinstance(row[0], bool)
        or not isinstance(row[0], int)
    ):
        raise BalanceAnalysisPublicationNotReady(
            "Balance-analysis dependency count query returned an invalid row."
        )
    return row[0]


publish_balance_analysis_overview_actor = register_actor_once(
    "publish_balance_analysis_overview",
    _publish_balance_analysis_overview_actor,
    max_retries=8,
    time_limit_ms=3_600_000,
)
