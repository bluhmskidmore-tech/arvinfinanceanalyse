from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import duckdb

SUPPORTED_HOME_MACRO_TABLES = {
    "fact_choice_macro_daily",
    "std_external_macro_daily",
}


@dataclass(frozen=True)
class HomeMacroObservation:
    table: str
    series_id: str
    observation_date: date
    value: float | None
    cadence: str | None
    unit: str | None
    source_version: str | None
    vendor_version: str | None
    rule_version: str | None
    vendor_name: str | None = None
    ingest_batch_id: str | None = None
    created_at: datetime | None = None
    quality_flag: str | None = None
    run_id: str | None = None


@dataclass(frozen=True)
class HomeMacroSeriesRead:
    table: str
    series_id: str
    observations: list[HomeMacroObservation]
    error: Literal["relation_missing"] | None = None


class HomeMacroReleaseContextRepository:
    def __init__(self, duckdb_path: str | Path) -> None:
        self._duckdb_path = Path(duckdb_path)

    def read_recent_observations(
        self,
        *,
        table: str,
        series_id: str,
        cutoff_date: date,
        limit: int = 2,
    ) -> HomeMacroSeriesRead:
        if table not in SUPPORTED_HOME_MACRO_TABLES:
            raise ValueError(f"Unsupported home macro table: {table!r}")
        if limit <= 0:
            raise ValueError("limit must be positive")

        conn = duckdb.connect(str(self._duckdb_path), read_only=True)
        try:
            try:
                rows = conn.execute(
                    self._query_for_table(table),
                    [series_id, cutoff_date, limit],
                ).fetchall()
            except duckdb.CatalogException as exc:
                if "does not exist" not in str(exc) and "not found" not in str(exc):
                    raise
                return HomeMacroSeriesRead(
                    table=table,
                    series_id=series_id,
                    observations=[],
                    error="relation_missing",
                )
        finally:
            conn.close()

        observations = [self._observation_from_row(table, row) for row in rows]
        return HomeMacroSeriesRead(
            table=table,
            series_id=series_id,
            observations=observations,
        )

    @staticmethod
    def _query_for_table(table: str) -> str:
        if table == "std_external_macro_daily":
            return """
                with ranked as (
                  select *,
                         row_number() over (
                           partition by series_id, trade_date
                           order by created_at desc, ingest_batch_id desc
                         ) as canonical_rank
                  from std_external_macro_daily
                  where series_id = ? and try_cast(trade_date as date) <= ?
                )
                select
                  series_id,
                  trade_date,
                  value_numeric,
                  frequency,
                  unit,
                  source_version,
                  vendor_version,
                  rule_version,
                  vendor_name,
                  ingest_batch_id,
                  created_at,
                  null as quality_flag,
                  null as run_id
                from ranked
                where canonical_rank = 1
                order by try_cast(trade_date as date) desc
                limit ?
            """
        return """
            with ranked as (
              select *,
                     row_number() over (
                       partition by series_id, trade_date
                       order by
                         regexp_extract(
                           coalesce(run_id, ''),
                           '([0-9]{8}T[0-9]{6}Z)$',
                           1
                         ) desc,
                         coalesce(run_id, '') desc,
                         coalesce(vendor_version, '') desc,
                         coalesce(source_version, '') desc
                     ) as canonical_rank
              from fact_choice_macro_daily
              where series_id = ? and try_cast(trade_date as date) <= ?
            )
            select
              series_id,
              trade_date,
              value_numeric,
              frequency,
              unit,
              source_version,
              vendor_version,
              rule_version,
              null as vendor_name,
              null as ingest_batch_id,
              null as created_at,
              quality_flag,
              run_id
            from ranked
            where canonical_rank = 1
            order by try_cast(trade_date as date) desc
            limit ?
        """

    @staticmethod
    def _observation_from_row(table: str, row: tuple[object, ...]) -> HomeMacroObservation:
        return HomeMacroObservation(
            table=table,
            series_id=str(row[0]),
            observation_date=date.fromisoformat(str(row[1])),
            value=float(row[2]) if row[2] is not None else None,
            cadence=str(row[3]) if row[3] is not None else None,
            unit=str(row[4]) if row[4] is not None else None,
            source_version=str(row[5]) if row[5] is not None else None,
            vendor_version=str(row[6]) if row[6] is not None else None,
            rule_version=str(row[7]) if row[7] is not None else None,
            vendor_name=str(row[8]) if row[8] is not None else None,
            ingest_batch_id=str(row[9]) if row[9] is not None else None,
            created_at=row[10] if isinstance(row[10], datetime) else None,
            quality_flag=str(row[11]) if row[11] is not None else None,
            run_id=str(row[12]) if row[12] is not None else None,
        )
