from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import duckdb
from backend.app.core_finance.pnl_independent_reconciliation import (
    FACT_MATERIALIZED_ADJUSTMENT_STAGE,
    IndependentPnlReference,
)
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.pnl_precompute_state import (
    PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
    required_pnl_by_business_revision_on_connection,
)

PNL_INDEPENDENT_REFERENCE_STREAM = "pnl_independent_reference"


@dataclass(frozen=True, slots=True)
class PnlFormalFactDependencyBinding:
    report_date: str
    formal_source_version: str
    formal_rule_version: str
    approved_adjustment_version: str
    formal_dependency_revision: int
    formal_dependency_protocol_version: str
    adjustment_stage: str
    formal_fi_row_count: int
    nonstd_bridge_row_count: int


def _digest_version(prefix: str, payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}_{sha256(encoded).hexdigest()[:24]}"


def _canonical_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _supports_current_dependency_protocol(
    connection: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
) -> bool:
    columns = {
        (str(row[0]).lower(), str(row[1]).lower())
        for row in connection.execute(
            """
            select table_name, column_name
            from information_schema.columns
            where lower(table_name) in (
              'fact_pnl_by_business_precompute_invalidation',
              'fact_pnl_by_business_precompute_cutoff_state'
            )
            """
        ).fetchall()
    }
    required_columns = {
        ("fact_pnl_by_business_precompute_invalidation", "event_revision"),
        ("fact_pnl_by_business_precompute_invalidation", "dirty_from_date"),
        ("fact_pnl_by_business_precompute_cutoff_state", "protocol_version"),
        ("fact_pnl_by_business_precompute_cutoff_state", "required_event_revision"),
    }
    if not required_columns.issubset(columns):
        return False
    rows = connection.execute(
        """
        select distinct nullif(trim(protocol_version), '')
        from fact_pnl_by_business_precompute_cutoff_state
        where year = ? and as_of_date = ?
        """,
        [int(report_date[:4]), report_date],
    ).fetchall()
    observed_protocols = {str(row[0]) for row in rows if row[0] is not None}
    return not observed_protocols or observed_protocols == {
        PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION
    }


def _read_formal_fact_dependency_revision_on_connection(
    connection: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
) -> tuple[int, str] | None:
    if not _supports_current_dependency_protocol(connection, report_date=report_date):
        return None
    revision = required_pnl_by_business_revision_on_connection(
        connection,
        year=int(report_date[:4]),
        as_of_date=report_date,
    )
    return revision, PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION


def read_formal_fact_dependency_revision(
    duckdb_path: str | Path,
    *,
    report_date: str,
) -> tuple[int, str] | None:
    """Read the cutoff revision/protocol without scanning formal fact rows."""

    connection = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        return _read_formal_fact_dependency_revision_on_connection(
            connection,
            report_date=report_date,
        )
    finally:
        connection.close()


def read_formal_fact_dependency_binding(
    duckdb_path: str | Path,
    *,
    report_date: str,
) -> PnlFormalFactDependencyBinding | None:
    """Fingerprint the exact formal fact population consumed by overview totals.

    The helper is read-only. It returns ``None`` when either required fact table
    is absent or when the report date has no fact rows, because an empty query
    alone does not prove that an intentionally empty batch was materialized.
    """

    table_columns = {
        "fact_formal_pnl_fi": (
            "instrument_code",
            "portfolio_name",
            "cost_center",
            "invest_type_std",
            "accounting_basis",
            "currency_basis",
            "interest_income_514",
            "fair_value_change_516",
            "capital_gain_517",
            "manual_adjustment",
            "total_pnl",
            "source_version",
            "rule_version",
            "ingest_batch_id",
            "trace_id",
        ),
        "fact_nonstd_pnl_bridge": (
            "bond_code",
            "portfolio_name",
            "cost_center",
            "interest_income_514",
            "fair_value_change_516",
            "capital_gain_517",
            "manual_adjustment",
            "total_pnl",
            "source_version",
            "rule_version",
            "ingest_batch_id",
            "trace_id",
        ),
    }
    connection = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        connection.execute("begin transaction")
        existing_tables = {
            str(row[0]).lower()
            for row in connection.execute(
                "select table_name from information_schema.tables"
            ).fetchall()
        }
        required_tables = {
            *table_columns,
            "fact_pnl_by_business_precompute_invalidation",
        }
        if any(table not in existing_tables for table in required_tables):
            return None
        population: dict[str, list[list[str]]] = {}
        for table, columns in table_columns.items():
            selected = ", ".join(columns)
            raw_rows = connection.execute(
                f"select {selected} from {table} where report_date = ?",  # noqa: S608
                [report_date],
            ).fetchall()
            population[table] = sorted(
                ([_canonical_cell(value) for value in row] for row in raw_rows),
                key=lambda row: tuple(row),
            )
        revision_binding = _read_formal_fact_dependency_revision_on_connection(
            connection,
            report_date=report_date,
        )
        if revision_binding is None:
            connection.execute("rollback")
            return None
        dependency_revision, dependency_protocol = revision_binding
        connection.execute("commit")
    except Exception:
        connection.execute("rollback")
        raise
    finally:
        connection.close()

    formal_count = len(population["fact_formal_pnl_fi"])
    nonstd_count = len(population["fact_nonstd_pnl_bridge"])
    if formal_count + nonstd_count == 0:
        return None
    dependency_sets: dict[str, dict[str, list[str]]] = {}
    adjustment_rows: dict[str, list[dict[str, object]]] = {}
    for table, rows in population.items():
        columns = table_columns[table]
        source_index = columns.index("source_version")
        rule_index = columns.index("rule_version")
        ingest_index = columns.index("ingest_batch_id")
        adjustment_index = columns.index("manual_adjustment")
        trace_index = columns.index("trace_id")
        identity_indexes = tuple(
            index
            for index, column in enumerate(columns)
            if column
            not in {
                "interest_income_514",
                "fair_value_change_516",
                "capital_gain_517",
                "manual_adjustment",
                "total_pnl",
                "source_version",
                "rule_version",
                "ingest_batch_id",
                "trace_id",
            }
        )
        dependency_sets[table] = {
            "source_versions": sorted({row[source_index] for row in rows}),
            "rule_versions": sorted({row[rule_index] for row in rows}),
            "ingest_batch_ids": sorted({row[ingest_index] for row in rows}),
        }
        adjustment_rows[table] = [
            {
                "row_identity": [row[index] for index in identity_indexes],
                "manual_adjustment": row[adjustment_index],
                "source_version": row[source_index],
                "rule_version": row[rule_index],
                "ingest_batch_id": row[ingest_index],
                "trace_id": row[trace_index],
            }
            for row in rows
        ]
    return PnlFormalFactDependencyBinding(
        report_date=report_date,
        formal_source_version=_digest_version(
            "sv_pnl_formal_fact_snapshot_v1",
            {"sets": dependency_sets, "rows": population},
        ),
        formal_rule_version=_digest_version(
            "rv_pnl_formal_fact_rules_v1",
            {table: values["rule_versions"] for table, values in dependency_sets.items()},
        ),
        approved_adjustment_version=_digest_version(
            "av_pnl_fact_materialized_v1",
            adjustment_rows,
        ),
        formal_dependency_revision=dependency_revision,
        formal_dependency_protocol_version=(
            dependency_protocol
        ),
        adjustment_stage=FACT_MATERIALIZED_ADJUSTMENT_STAGE,
        formal_fi_row_count=formal_count,
        nonstd_bridge_row_count=nonstd_count,
    )


@dataclass(frozen=True, slots=True)
class PnlIndependentReferenceRepository:
    governance_dir: Path

    def store_prepared(self, reference: IndependentPnlReference) -> dict[str, object]:
        record = {
            **reference.to_record(),
            "prepared_at": datetime.now(UTC).isoformat(),
        }
        GovernanceRepository(base_dir=self.governance_dir).append(
            PNL_INDEPENDENT_REFERENCE_STREAM,
            record,
        )
        return record

    def load_prepared(
        self,
        *,
        report_date: str,
        formal_dependency_revision: int,
        formal_dependency_protocol_version: str,
    ) -> IndependentPnlReference | None:
        records = GovernanceRepository(base_dir=self.governance_dir).read_all(
            PNL_INDEPENDENT_REFERENCE_STREAM
        )
        for record in reversed(records):
            if str(record.get("report_date") or "") != report_date:
                continue
            try:
                reference = IndependentPnlReference.from_record(record)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"Invalid prepared independent PnL reference for report_date={report_date}"
                ) from exc
            if (
                reference.formal_dependency_revision == formal_dependency_revision
                and reference.formal_dependency_protocol_version
                == formal_dependency_protocol_version
            ):
                return reference
        return None


__all__ = [
    "FACT_MATERIALIZED_ADJUSTMENT_STAGE",
    "PNL_INDEPENDENT_REFERENCE_STREAM",
    "PnlFormalFactDependencyBinding",
    "PnlIndependentReferenceRepository",
    "read_formal_fact_dependency_binding",
    "read_formal_fact_dependency_revision",
]
