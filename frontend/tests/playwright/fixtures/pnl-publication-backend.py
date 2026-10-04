from __future__ import annotations

import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import duckdb
import uvicorn
from fastapi import FastAPI

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.api.routes import pnl as pnl_route
from backend.app.config.product_category_mapping import resolve_product_category_ftp_rate_pct
from backend.app.repositories.financial_result_publication_repo import (
    FINANCIAL_PUBLICATION_API_VERSION,
    FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    canonical_json_bytes,
    sha256_bytes,
)
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.pnl_precompute_state import (
    PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
)
from backend.app.repositories.pnl_repo import PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION
from backend.app.security.auth_context import AuthContext
from backend.app.services import pnl_service as pnl_service_module
from backend.app.services.pnl_by_business_adjustments import (
    active_pnl_by_business_manual_adjustments_for_period,
    pnl_by_business_manual_adjustment_source_version,
)
from backend.app.services.pnl_by_business_candidate_insights import FORMAL_RULE_VERSION
from backend.app.services.pnl_task_dispatch import CACHE_KEY
from backend.app.services import pnl_by_business_publication_service as publication_service
from backend.app.tasks import pnl_by_business_page_publication as page_publication
from backend.app.tasks import pnl_materialize
from backend.app.tasks.financial_result_publication import (
    FinancialPublicationPlan,
    FinancialTablePublicationSpec,
    invalidate_financial_generation,
    publish_financial_result,
)

REPORT_DATE = "2026-02-28"
GENERATION = "pnl-page-e2e-001"
SOURCE_VERSION = "source-e2e-v1"


class FixturePnlRepository:
    def __init__(self, _path: str):
        pass

    def max_formal_or_nonstd_report_date_in_year(
        self, *, year: int, as_of_cap: str | None
    ) -> str | None:
        if as_of_cap is not None:
            return as_of_cap
        return REPORT_DATE if year == 2026 else "2025-12-31" if year == 2025 else None

    def pnl_by_business_precompute_dependency_revision(
        self, *, year: int, as_of_date: str
    ) -> int:
        del year, as_of_date
        return 1


def _dependency_versions(settings: SimpleNamespace) -> dict[str, str]:
    versions = {
        "pnl_by_business_page.protocol": publication_service.PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION,
        "pnl_by_business_page.rules": FORMAL_RULE_VERSION,
    }
    for key, requested_date in (
        ("current_ytd", REPORT_DATE),
        ("baseline_ytd", "2025-02-28"),
        ("monthly", REPORT_DATE),
        ("monthly_baseline", "2025-12-31"),
    ):
        dependency_year = date.fromisoformat(requested_date).year
        ftp_rate_pct = resolve_product_category_ftp_rate_pct(
            date(dependency_year, 12, 31),
            settings.ftp_rate_pct,
        )
        adjustments = active_pnl_by_business_manual_adjustments_for_period(
            settings.governance_path,
            year=dependency_year,
            period_end=requested_date,
        )
        prefix = f"pnl_by_business.{key}"
        versions.update(
            {
                f"{prefix}.requested_report_date": requested_date,
                f"{prefix}.resolved_report_date": requested_date,
                f"{prefix}.dependency_revision": "1",
                f"{prefix}.source_version": SOURCE_VERSION,
                f"{prefix}.rule_version": PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
                f"{prefix}.ftp_rate_pct": str(ftp_rate_pct),
                f"{prefix}.adjustment_version": pnl_by_business_manual_adjustment_source_version(
                    adjustments
                ),
                f"{prefix}.protocol_version": PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
            }
        )
    return versions


def _dependency_snapshots(settings: SimpleNamespace) -> tuple[dict[str, object], ...]:
    versions = _dependency_versions(settings)
    snapshots: list[dict[str, object]] = []
    for key, requested_date in (
        ("current_ytd", REPORT_DATE),
        ("baseline_ytd", "2025-02-28"),
        ("monthly", REPORT_DATE),
        ("monthly_baseline", "2025-12-31"),
    ):
        prefix = f"pnl_by_business.{key}"
        snapshots.append(
            {
                "key": key,
                "year": date.fromisoformat(requested_date).year,
                "requested_report_date": requested_date,
                "resolved_report_date": requested_date,
                "dependency_revision": int(versions[f"{prefix}.dependency_revision"]),
                "source_version": versions[f"{prefix}.source_version"],
                "rule_version": versions[f"{prefix}.rule_version"],
                "ftp_rate_pct": versions[f"{prefix}.ftp_rate_pct"],
                "adjustment_version": versions[f"{prefix}.adjustment_version"],
                "protocol_version": versions[f"{prefix}.protocol_version"],
            }
        )
    return tuple(snapshots)


def _golden_envelope(*, hhi_pct: str = "53.13", trace_id: str | None = None) -> dict[str, object]:
    golden_path = (
        REPO_ROOT
        / "tests"
        / "golden_samples"
        / "GS-PNL-BUSINESS-INSIGHTS-A"
        / "response.json"
    )
    envelope = json.loads(golden_path.read_text(encoding="utf-8"))
    envelope["result"]["concentration"]["hhi_pct"] = hhi_pct
    if trace_id is not None:
        envelope["result_meta"]["trace_id"] = trace_id
    return envelope


def _seed_publication(root: Path) -> SimpleNamespace:
    source_path = root / "source.duckdb"
    publication_root = root / "published"
    governance_path = root / "governance"
    governance_path.mkdir(parents=True, exist_ok=True)
    settings = SimpleNamespace(
        financial_publication_enabled=True,
        financial_publication_root=str(publication_root),
        duckdb_path=str(source_path),
        governance_path=governance_path,
        ftp_rate_pct=Decimal("1.75"),
    )
    dependency_versions = _dependency_versions(settings)
    envelope = _golden_envelope()
    payload_bytes = canonical_json_bytes(envelope)
    payload_json = payload_bytes.decode("utf-8")
    dependency_json = json.dumps(
        dependency_versions,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    conn = duckdb.connect(str(source_path))
    try:
        conn.execute(
            f"""
            create table {publication_service.PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE} (
                report_date date not null,
                payload_json varchar not null,
                payload_sha256 varchar not null,
                dependency_revision bigint not null,
                dependency_versions_json varchar not null,
                source_version varchar not null,
                rule_version varchar not null,
                adjustment_version varchar not null,
                protocol_version varchar not null,
                prepared_at varchar not null
            )
            """
        )
        conn.execute(
            f"""
            insert into {publication_service.PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE}
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                REPORT_DATE,
                payload_json,
                sha256_bytes(payload_bytes),
                1,
                dependency_json,
                SOURCE_VERSION,
                FORMAL_RULE_VERSION,
                dependency_versions["pnl_by_business.current_ytd.adjustment_version"],
                publication_service.PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION,
                "2026-03-01T00:00:00Z",
            ],
        )
        conn.execute(
            """
            create table fact_pnl_by_business_precompute_cutoff_state (
                scope_key varchar,
                year integer,
                as_of_date date,
                required_event_revision bigint,
                prepared_event_revision bigint,
                status varchar,
                source_version varchar,
                rule_version varchar,
                effective_ftp_rate_pct varchar,
                supplemental_source_version varchar,
                protocol_version varchar
            )
            """
        )
        for snapshot in _dependency_snapshots(settings):
            conn.execute(
                """
                insert into fact_pnl_by_business_precompute_cutoff_state
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "pnl_by_business",
                    snapshot["year"],
                    snapshot["requested_report_date"],
                    snapshot["dependency_revision"],
                    snapshot["dependency_revision"],
                    "ready",
                    snapshot["source_version"],
                    snapshot["rule_version"],
                    snapshot["ftp_rate_pct"],
                    snapshot["adjustment_version"],
                    snapshot["protocol_version"],
                ],
            )
    finally:
        conn.close()

    plan = FinancialPublicationPlan(
        generation=GENERATION,
        expected_previous_generation=None,
        tables=(
            FinancialTablePublicationSpec(
                name=publication_service.PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE,
                date_column="report_date",
                required_dates=(REPORT_DATE,),
            ),
        ),
        required_steps=("prepare_page", "verify_page"),
        step_receipts=(
            {
                "name": "prepare_page",
                "status": "completed",
                "result": {"status": "completed", "report_date": REPORT_DATE},
            },
            {
                "name": "verify_page",
                "status": "completed",
                "result": {"status": "completed", "check_count": 1},
            },
        ),
        required_dependency_keys=tuple(dependency_versions),
        dependency_versions=dependency_versions,
        coverage_dates={"pnl_by_business_page": (REPORT_DATE,)},
        supported_api_versions=(FINANCIAL_PUBLICATION_API_VERSION,),
        supported_schema_versions=(FINANCIAL_PUBLICATION_SCHEMA_VERSION,),
        quality={"status": "passed", "checks": ({"name": "page_envelope", "status": "passed"},)},
        source_dependency_validator=lambda _conn: dependency_versions,
    )
    publish_financial_result(
        source_duckdb_path=source_path,
        publication_root=publication_root,
        plan=plan,
    )
    GovernanceRepository(base_dir=governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "pnl-materialize-e2e-001",
            "job_name": "pnl_materialize",
            "cache_key": CACHE_KEY,
            "status": "completed",
            "report_date": REPORT_DATE,
            "source_version": SOURCE_VERSION,
            "finished_at": "2026-03-01T00:00:00Z",
        },
    )
    return settings


def create_app() -> FastAPI:
    fixture_root = Path(os.environ["MOSS_PNL_PUBLICATION_FIXTURE_ROOT"]).resolve()
    fixture_root.mkdir(parents=True, exist_ok=True)
    settings = _seed_publication(fixture_root)
    real_service = pnl_route._pnl_service()
    queued_page_request: dict[str, object] = {}

    pnl_service_module.PnlRepository = FixturePnlRepository
    pnl_materialize.PnlRepository = FixturePnlRepository
    pnl_materialize.get_settings = lambda: settings
    page_publication.get_settings = lambda: settings
    page_publication._dependency_snapshot = lambda **_kwargs: _dependency_snapshots(settings)
    page_publication.pnl_by_business_insights_envelope = lambda **_kwargs: _golden_envelope(
        hhi_pct="54.13",
        trace_id="tr_pnl_business_insights_post_rebuild",
    )

    def fake_precompute(*, year: int, as_of_date: str, **_kwargs) -> dict[str, object]:
        return {
            "year": year,
            "as_of_date": as_of_date,
            "records": 1,
            "source_version": SOURCE_VERSION,
            "generated_at": "2026-03-02T00:00:00Z",
        }

    pnl_materialize.precompute_pnl_by_business_payloads = fake_precompute

    class ServiceProxy:
        PnlByBusinessPrecomputeConflictError = real_service.PnlByBusinessPrecomputeConflictError
        PnlByBusinessPrecomputeDispatchError = real_service.PnlByBusinessPrecomputeDispatchError

        def __getattr__(self, name: str):
            return getattr(real_service, name)

        @staticmethod
        def request_pnl_by_business_page_rebuild(_settings, **kwargs):
            payload = real_service.request_pnl_by_business_page_rebuild(
                _settings, **kwargs
            )
            queued_page_request.clear()
            queued_page_request.update(payload)
            run_id = str(payload["page_run_id"])
            intent = next(
                record
                for record in reversed(
                    GovernanceRepository(base_dir=settings.governance_path).read_all(
                        CACHE_BUILD_RUN_STREAM
                    )
                )
                if str(record.get("run_id") or "") == run_id
            )
            queued_page_request["intent"] = dict(intent)
            return payload

    pnl_route.get_settings = lambda: settings
    pnl_route._pnl_service = lambda: ServiceProxy()

    def authorize(*, action: str, **_kwargs) -> None:
        del action

    pnl_route.ensure_user_allowed = authorize
    app = FastAPI()
    app.dependency_overrides[pnl_route.get_auth_context] = lambda: AuthContext(
        user_id="publication-e2e-reader",
        role="viewer",
        identity_source="fixture",
    )
    app.include_router(pnl_route.router)

    @app.get("/__fixture/health")
    def fixture_health() -> dict[str, str]:
        return {"status": "ok", "generation": GENERATION}

    @app.post("/__fixture/revoke/{generation}")
    def revoke_generation(generation: str) -> dict[str, str]:
        invalidate_financial_generation(
            settings.financial_publication_root,
            generation=generation,
            reason="e2e source approval revoked",
        )
        return {"status": "revoked", "generation": generation}

    @app.post("/__fixture/drain-page-rebuild")
    def drain_page_rebuild() -> dict[str, object]:
        if not queued_page_request:
            raise RuntimeError("No page rebuild was queued.")
        intent = queued_page_request["intent"]
        assert isinstance(intent, dict)
        for dependency_run in queued_page_request.get("dependency_runs", []):
            assert isinstance(dependency_run, dict)
            pnl_materialize.rebuild_pnl_by_business_precompute.fn(
                year=int(dependency_run["year"]),
                as_of_dates=list(dependency_run["target_as_of_dates"]),
                duckdb_path=str(settings.duckdb_path),
                governance_dir=str(settings.governance_path),
                run_id=str(dependency_run["run_id"]),
                queued_at=str(intent["queued_at"]),
                trigger_reason="page_dependency_prepare",
                dependency_revision=int(dependency_run["dependency_revision"]),
            )
        receipt = page_publication.prepare_pnl_by_business_page_envelope_actor.fn(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            year=int(intent["target_year"]),
            as_of_date=str(intent["report_date"]),
            run_id=str(intent["run_id"]),
            expected_previous_generation=(
                str(intent["expected_previous_generation"])
                if intent.get("expected_previous_generation") is not None
                else None
            ),
        )
        status = real_service.pnl_by_business_precompute_status(
            settings,
            year=int(intent["target_year"]),
            as_of_date=str(intent["report_date"]),
        )
        return {"receipt": receipt, "status": status}

    return app


if __name__ == "__main__":
    uvicorn.run(
        create_app(),
        host="127.0.0.1",
        port=int(os.environ.get("MOSS_PNL_PUBLICATION_FIXTURE_PORT", "15990")),
        log_level="warning",
    )
