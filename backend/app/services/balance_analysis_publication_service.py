from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import duckdb
from pydantic import ValidationError

from backend.app.governance.locks import acquire_lock
from backend.app.governance.settings import Settings
from backend.app.repositories.balance_analysis_publication_state import (
    BALANCE_ANALYSIS_BASIS_BREAKDOWN_COVERAGE_KEY,
    BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE,
    BALANCE_ANALYSIS_OVERVIEW_COVERAGE_KEY,
    BALANCE_ANALYSIS_OVERVIEW_TABLE,
    BALANCE_ANALYSIS_PORTFOLIO_CONTRACT_VERSION,
    BALANCE_ANALYSIS_PUBLICATION_API_VERSION,
    BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION,
    BalanceAnalysisPublicationUnavailable,
    configured_balance_analysis_publication_root,
)
from backend.app.repositories.financial_result_publication_repo import (
    FinancialPublicationError,
    ResolvedFinancialPublication,
    canonical_json_bytes,
    open_financial_generation,
    resolve_financial_generation,
    sha256_bytes,
)
from backend.app.repositories.source_manifest_repo import (
    AUG31_SOURCE_MANIFEST_DATE,
    AUG31_SOURCE_MANIFEST_DEPENDENCY_KEY,
    aug31_source_manifest_lock,
    selected_aug31_source_manifest_hash,
)
from backend.app.schemas.balance_analysis import (
    BalanceAnalysisBasisBreakdownEnvelope,
    BalanceAnalysisOverviewEnvelope,
)

_SNAPSHOT_V3_REQUIRED_REPORT_DATE = "2026-08-31"
_SNAPSHOT_V3_RULE_VERSION = "rv_snapshot_zqtz_tyw_v3"


class BalanceAnalysisPublicationConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class PublishedBalanceAnalysisOverview:
    generation: str
    envelope: dict[str, object]


def balance_analysis_publication_root(settings: Settings) -> Path:
    if not settings.balance_analysis_publication_enabled:
        raise BalanceAnalysisPublicationUnavailable(
            "Balance-analysis publication is disabled."
        )
    root = configured_balance_analysis_publication_root(settings)
    if root is None:
        raise BalanceAnalysisPublicationUnavailable(
            "Balance-analysis publication root is not configured."
        )
    return root


def read_published_balance_analysis_overview(
    settings: Settings,
    *,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"],
    currency_basis: Literal["native", "CNY"],
    generation: str,
) -> PublishedBalanceAnalysisOverview:
    return _read_published_balance_analysis_envelope(
        settings, report_date=report_date, position_scope=position_scope,
        currency_basis=currency_basis, generation=generation, surface="overview",
    )


def read_published_balance_analysis_basis_breakdown(
    settings: Settings,
    *,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"],
    currency_basis: Literal["native", "CNY"],
    generation: str,
) -> PublishedBalanceAnalysisOverview:
    return _read_published_balance_analysis_envelope(
        settings, report_date=report_date, position_scope=position_scope,
        currency_basis=currency_basis, generation=generation, surface="basis_breakdown",
    )


def _read_published_balance_analysis_envelope(
    settings: Settings,
    *,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"],
    currency_basis: Literal["native", "CNY"],
    generation: str,
    surface: Literal["overview", "basis_breakdown"],
) -> PublishedBalanceAnalysisOverview:
    if report_date != AUG31_SOURCE_MANIFEST_DATE:
        return _read_published_balance_analysis_overview_unlocked(
            settings,
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
            generation=generation,
            surface=surface,
        )
    try:
        with acquire_lock(
            aug31_source_manifest_lock(settings.governance_path),
            base_dir=settings.governance_path,
            timeout_seconds=5.0,
        ):
            return _read_published_balance_analysis_overview_unlocked(
                settings,
                report_date=report_date,
                position_scope=position_scope,
                currency_basis=currency_basis,
                generation=generation,
                surface=surface,
            )
    except TimeoutError as exc:
        raise BalanceAnalysisPublicationConflict(
            "2026-08-31 selected source manifest cannot be checked while it is locked."
        ) from exc


def _read_published_balance_analysis_overview_unlocked(
    settings: Settings,
    *,
    report_date: str,
    position_scope: Literal["asset", "liability", "all"],
    currency_basis: Literal["native", "CNY"],
    generation: str,
    surface: Literal["overview", "basis_breakdown"],
) -> PublishedBalanceAnalysisOverview:
    root = balance_analysis_publication_root(settings)
    if not str(generation or "").strip():
        raise BalanceAnalysisPublicationConflict(
            "A pinned balance-analysis publication generation is required."
        )
    try:
        with open_financial_generation(
            root,
            generation=generation,
            reader_api_version=BALANCE_ANALYSIS_PUBLICATION_API_VERSION,
            reader_schema_version=BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION,
        ) as (conn, resolved):
            _require_overview_coverage(resolved, report_date=report_date)
            _require_complete_portfolio_rows(conn, report_date=report_date)
            table = (
                BALANCE_ANALYSIS_OVERVIEW_TABLE if surface == "overview"
                else BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE
            )
            row = conn.execute(
                f"""
                select payload_json, payload_sha256, dependency_versions_json
                from {table}
                where report_date = ? and position_scope = ? and currency_basis = ?
                """,
                [report_date, position_scope, currency_basis],
            ).fetchone()
            if row is None:
                raise BalanceAnalysisPublicationConflict(
                    "The pinned balance-analysis publication does not cover the requested filters."
                )
            validate = (
                _validated_overview_envelope if surface == "overview"
                else _validated_basis_breakdown_envelope
            )
            envelope = validate(
                payload_json=str(row[0] or ""),
                payload_sha256=str(row[1] or ""),
                report_date=report_date,
                position_scope=position_scope,
                currency_basis=currency_basis,
            )
            row_dependencies = _json_string_map(
                str(row[2] or ""),
                label="published balance-analysis dependency versions",
            )
            manifest_dependencies = _manifest_dependency_versions(resolved)
            if row_dependencies != manifest_dependencies:
                raise BalanceAnalysisPublicationConflict(
                    "Published balance-analysis row dependencies do not match the sealed manifest."
                )
            _require_current_rule_version(manifest_dependencies)
            _require_snapshot_v3_for_report_date(
                manifest_dependencies,
                report_date=report_date,
            )
            _require_current_aug31_source_manifest(
                manifest_dependencies,
                settings=settings,
                report_date=report_date,
            )
            # The sealed business payload is unchanged; serving identity comes
            # from the verified manifest rather than the mutable active database.
            meta = envelope.get("result_meta")
            if isinstance(meta, dict):
                meta["filters_applied"] = {
                    **(meta.get("filters_applied") or {}),
                    "generation": resolved.generation,
                    "manifest_sha256": resolved.manifest_sha256,
                    "serving_mode": "published",
                }
            return PublishedBalanceAnalysisOverview(
                generation=resolved.generation,
                envelope=envelope,
            )
    except BalanceAnalysisPublicationConflict:
        raise
    except (FinancialPublicationError, duckdb.Error) as exc:
        raise BalanceAnalysisPublicationConflict(str(exc)) from exc


def balance_analysis_publication_status(settings: Settings) -> dict[str, object]:
    if not settings.balance_analysis_publication_enabled:
        return {
            "enabled": False,
            "available": False,
            "generation": None,
            "report_dates": [],
            "manifest_sha256": None,
            "quality_flag": "stale",
            "reason": "Balance-analysis publication is disabled.",
        }
    try:
        root = balance_analysis_publication_root(settings)
        resolved = resolve_financial_generation(
            root,
            generation=None,
            reader_api_version=BALANCE_ANALYSIS_PUBLICATION_API_VERSION,
            reader_schema_version=BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION,
        )
        dependencies = _manifest_dependency_versions(resolved)
        _require_current_rule_version(dependencies)
        report_dates = _manifest_overview_dates(resolved)
        available_dates: list[str] = []
        blocked_reason: BalanceAnalysisPublicationConflict | None = None
        for report_date in report_dates:
            try:
                _require_snapshot_v3_for_report_date(dependencies, report_date=report_date)
                if report_date == AUG31_SOURCE_MANIFEST_DATE:
                    with acquire_lock(
                        aug31_source_manifest_lock(settings.governance_path),
                        base_dir=settings.governance_path,
                        timeout_seconds=5.0,
                    ):
                        _require_current_aug31_source_manifest(
                            dependencies,
                            settings=settings,
                            report_date=report_date,
                        )
                with open_financial_generation(
                    root,
                    generation=resolved.generation,
                    reader_api_version=BALANCE_ANALYSIS_PUBLICATION_API_VERSION,
                    reader_schema_version=BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION,
                ) as (conn, confirmed):
                    if confirmed.manifest_sha256 != resolved.manifest_sha256:
                        raise BalanceAnalysisPublicationConflict(
                            "Balance-analysis publication manifest changed during the status check."
                        )
                    _require_complete_portfolio_rows(conn, report_date=report_date)
            except TimeoutError:
                blocked_reason = BalanceAnalysisPublicationConflict(
                    "2026-08-31 selected source manifest cannot be checked while it is locked."
                )
            except BalanceAnalysisPublicationConflict as exc:
                blocked_reason = exc
            else:
                available_dates.append(report_date)
        if not available_dates:
            raise blocked_reason or BalanceAnalysisPublicationConflict(
                "Balance-analysis publication has no readable overview dates."
            )
        return {
            "enabled": True,
            "available": True,
            "generation": resolved.generation,
            "report_dates": available_dates,
            "manifest_sha256": resolved.manifest_sha256,
            "quality_flag": "ok",
            "reason": None,
        }
    except (
        BalanceAnalysisPublicationConflict,
        BalanceAnalysisPublicationUnavailable,
        FinancialPublicationError,
    ) as exc:
        return {
            "enabled": True,
            "available": False,
            "generation": None,
            "report_dates": [],
            "manifest_sha256": None,
            "quality_flag": "stale",
            "reason": str(exc),
        }


def _validated_overview_envelope(
    *,
    payload_json: str,
    payload_sha256: str,
    report_date: str,
    position_scope: str,
    currency_basis: str,
) -> dict[str, object]:
    return _validated_balance_envelope(
        payload_json=payload_json, payload_sha256=payload_sha256,
        report_date=report_date, position_scope=position_scope,
        currency_basis=currency_basis, surface="overview",
    )


def _validated_basis_breakdown_envelope(
    *,
    payload_json: str,
    payload_sha256: str,
    report_date: str,
    position_scope: str,
    currency_basis: str,
) -> dict[str, object]:
    return _validated_balance_envelope(
        payload_json=payload_json, payload_sha256=payload_sha256,
        report_date=report_date, position_scope=position_scope,
        currency_basis=currency_basis, surface="basis_breakdown",
    )


def _validated_balance_envelope(
    *,
    payload_json: str,
    payload_sha256: str,
    report_date: str,
    position_scope: str,
    currency_basis: str,
    surface: Literal["overview", "basis_breakdown"],
) -> dict[str, object]:
    if sha256_bytes(payload_json.encode("utf-8")) != payload_sha256:
        raise BalanceAnalysisPublicationConflict(
            f"Published balance-analysis {surface} payload digest does not match."
        )
    try:
        raw = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise BalanceAnalysisPublicationConflict(
            f"Published balance-analysis {surface} payload is not valid JSON."
        ) from exc
    if not isinstance(raw, dict):
        raise BalanceAnalysisPublicationConflict(
            f"Published balance-analysis {surface} payload must be an object."
        )
    if canonical_json_bytes(raw).decode("utf-8") != payload_json:
        raise BalanceAnalysisPublicationConflict(
            f"Published balance-analysis {surface} payload is not canonical JSON."
        )
    try:
        model = (
            BalanceAnalysisOverviewEnvelope if surface == "overview"
            else BalanceAnalysisBasisBreakdownEnvelope
        )
        validated = model.model_validate(raw)
    except ValidationError as exc:
        raise BalanceAnalysisPublicationConflict(
            f"Published balance-analysis {surface} payload violates the response contract."
        ) from exc
    result = validated.result
    if (
        result.report_date != report_date
        or result.position_scope != position_scope
        or result.currency_basis != currency_basis
    ):
        raise BalanceAnalysisPublicationConflict(
            f"Published balance-analysis {surface} identity does not match the request."
        )
    return validated.model_dump(mode="json")


def _require_overview_coverage(
    resolved: ResolvedFinancialPublication,
    *,
    report_date: str,
) -> None:
    if report_date not in _manifest_overview_dates(resolved):
        raise BalanceAnalysisPublicationConflict(
            "The pinned balance-analysis publication does not cover the requested report date."
        )


def _require_complete_portfolio_rows(
    conn: duckdb.DuckDBPyConnection, *, report_date: str,
) -> None:
    expected = {
        (scope, currency) for scope in ("asset", "liability", "all")
        for currency in ("native", "CNY")
    }
    for table in (BALANCE_ANALYSIS_OVERVIEW_TABLE, BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE):
        try:
            rows = conn.execute(
                f"select position_scope, currency_basis from {table} where report_date = ?",
                [report_date],
            ).fetchall()
        except duckdb.Error as exc:
            raise BalanceAnalysisPublicationConflict(
                "Balance-analysis publication is missing a required portfolio envelope table."
            ) from exc
        if len(rows) != len(expected) or set(rows) != expected:
            raise BalanceAnalysisPublicationConflict(
                "Balance-analysis publication does not contain all overview/basis filter combinations."
            )


def _manifest_overview_dates(resolved: ResolvedFinancialPublication) -> list[str]:
    sealed = resolved.manifest.get("sealed_payload")
    if not isinstance(sealed, Mapping):
        raise BalanceAnalysisPublicationConflict(
            "Balance-analysis publication has no sealed payload."
        )
    coverage = sealed.get("coverage_dates")
    if not isinstance(coverage, Mapping):
        raise BalanceAnalysisPublicationConflict(
            "Balance-analysis publication has no coverage declaration."
        )
    raw_dates = coverage.get(BALANCE_ANALYSIS_OVERVIEW_COVERAGE_KEY)
    if not isinstance(raw_dates, list) or not raw_dates:
        raise BalanceAnalysisPublicationConflict(
            "Balance-analysis publication has no overview coverage."
        )
    basis_dates = coverage.get(BALANCE_ANALYSIS_BASIS_BREAKDOWN_COVERAGE_KEY)
    if not isinstance(basis_dates, list) or not basis_dates:
        raise BalanceAnalysisPublicationConflict(
            "Balance-analysis publication has no basis-breakdown coverage."
        )
    common_dates = [str(item) for item in raw_dates if item in basis_dates]
    if not common_dates:
        raise BalanceAnalysisPublicationConflict(
            "Balance-analysis overview and basis-breakdown coverage have no common report date."
        )
    return common_dates


def _manifest_dependency_versions(
    resolved: ResolvedFinancialPublication,
) -> dict[str, str]:
    sealed = resolved.manifest.get("sealed_payload")
    if not isinstance(sealed, Mapping):
        raise BalanceAnalysisPublicationConflict(
            "Balance-analysis publication has no sealed payload."
        )
    dependencies = sealed.get("dependency_versions")
    if not isinstance(dependencies, Mapping) or not dependencies:
        raise BalanceAnalysisPublicationConflict(
            "Balance-analysis publication has no dependency versions."
        )
    normalized = {str(key): str(value) for key, value in dependencies.items()}
    if any(not key or not value for key, value in normalized.items()):
        raise BalanceAnalysisPublicationConflict(
            "Balance-analysis publication dependency versions are incomplete."
        )
    return normalized


def _json_string_map(payload: str, *, label: str) -> dict[str, str]:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise BalanceAnalysisPublicationConflict(f"{label} is not valid JSON.") from exc
    if not isinstance(raw, dict) or not raw:
        raise BalanceAnalysisPublicationConflict(f"{label} must be a non-empty object.")
    normalized = {str(key): str(value) for key, value in raw.items()}
    if any(not key or not value for key, value in normalized.items()):
        raise BalanceAnalysisPublicationConflict(f"{label} is incomplete.")
    return normalized


def _require_current_rule_version(dependencies: Mapping[str, str]) -> None:
    from backend.app.services.balance_analysis_service import RULE_VERSION

    if dependencies.get("balance.rule_version") != RULE_VERSION:
        raise BalanceAnalysisPublicationConflict(
            "Balance-analysis publication rule version is incompatible with this reader."
        )
    if dependencies.get("balance.publication_contract_version") != BALANCE_ANALYSIS_PORTFOLIO_CONTRACT_VERSION:
        raise BalanceAnalysisPublicationConflict(
            "Balance-analysis publication overview/basis contract version is incompatible with this reader."
        )


def _require_snapshot_v3_for_report_date(
    dependencies: Mapping[str, str], *, report_date: str
) -> None:
    if report_date != _SNAPSHOT_V3_REQUIRED_REPORT_DATE:
        return

    for family in ("zqtz", "tyw"):
        raw_versions = dependencies.get(f"balance.{family}.rule_versions")
        try:
            versions = json.loads(raw_versions) if raw_versions is not None else None
        except (TypeError, json.JSONDecodeError):
            versions = None
        if versions != [_SNAPSHOT_V3_RULE_VERSION]:
            raise BalanceAnalysisPublicationConflict(
                "Published balance-analysis snapshot rule version is incompatible "
                f"for report_date={report_date}, family={family}."
            )


def _require_current_aug31_source_manifest(
    dependencies: Mapping[str, str], *, settings: Settings, report_date: str
) -> None:
    if report_date != AUG31_SOURCE_MANIFEST_DATE:
        return
    expected = dependencies.get(AUG31_SOURCE_MANIFEST_DEPENDENCY_KEY)
    if not expected:
        raise BalanceAnalysisPublicationConflict(
            "Published 2026-08-31 balance-analysis source manifest digest is missing."
        )
    try:
        actual = selected_aug31_source_manifest_hash(settings.governance_path)
    except ValueError as exc:
        raise BalanceAnalysisPublicationConflict(
            "2026-08-31 selected source manifest is unavailable."
        ) from exc
    if actual != expected:
        raise BalanceAnalysisPublicationConflict(
            "Published 2026-08-31 balance-analysis source manifest is stale."
        )
