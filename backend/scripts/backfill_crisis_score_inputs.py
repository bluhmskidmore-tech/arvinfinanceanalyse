from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_alias  # noqa: E402
from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.tasks.commodity_daily_ingest import run_commodity_daily_ingest  # noqa: E402
from backend.app.tasks.macro_backfill import BackfillRow, _fetch_from_choice_edb  # noqa: E402
from backend.scripts.backfill_cross_asset_macro_environment import (  # noqa: E402
    CHOICE_SERIES,
    MacroRow,
    SeriesMeta,
    fetch_public_dr007_rows,
    persist_macro_environment_rows,
)

RULE_VERSION = "rv_crisis_score_inputs_backfill_v1"
DEFAULT_START_DATE = "2024-06-11"


class BackfillKind(StrEnum):
    CHOICE_EDB = "choice_edb"
    PUBLIC_DR007 = "public_dr007"
    TUSHARE_CSI300 = "tushare_csi300"
    COMMODITY_NHCI = "commodity_nhci"


def fetch_reverse_repo_7d_carry_forward_rows(
    *,
    duckdb_path: Path,
    start_date: str,
    end_date: str,
) -> list[MacroRow]:
    """Carry forward the latest known 7D OMO rate when Choice Wind legacy EDB codes are unavailable."""
    frame = load_series_by_alias("M0041653", duckdb_path=duckdb_path)
    if frame.empty:
        return []

    frame = frame.sort_values("date")
    last_row = frame.iloc[-1]
    last_date = date.fromisoformat(str(last_row["date"])[:10])
    last_value = float(last_row["value"])
    fill_start = max(date.fromisoformat(start_date), last_date + timedelta(days=1))
    fill_end = date.fromisoformat(end_date)
    if fill_start > fill_end:
        return []

    vendor_version = (
        f"vv_policy_rate_carry_{last_date.isoformat().replace('-', '')}_"
        f"{fill_start.isoformat().replace('-', '')}_{fill_end.isoformat().replace('-', '')}"
    )
    rows: list[MacroRow] = []
    current = fill_start
    while current <= fill_end:
        rows.append(
            MacroRow(
                series_id="cn_repo_7d",
                series_name="公开市场7天逆回购利率",
                vendor_series_code="policy_rate_carry:M0041653",
                vendor_name="moss_derived",
                trade_date=current.isoformat(),
                value_numeric=last_value,
                frequency="daily",
                unit="%",
                source_version="sv_crisis_score_reverse_repo_7d_carry",
                vendor_version=vendor_version,
            )
        )
        current += timedelta(days=1)
    return rows


@dataclass(frozen=True)
class CrisisInputSpec:
    field: str
    alias: str
    kind: BackfillKind
    series_id: str
    series_name: str
    vendor_series_code: str
    vendor_name: str
    frequency: str
    unit: str


# Mirrors backend/app/api/routes/macro_toolkit.py::_CRISIS_SCORE_INPUTS
CRISIS_SCORE_INPUT_SPECS: tuple[CrisisInputSpec, ...] = (
    CrisisInputSpec(
        field="hs300",
        alias="sh000300",
        kind=BackfillKind.TUSHARE_CSI300,
        series_id="CA.CSI300",
        series_name="沪深300指数收盘价",
        vendor_series_code="index_daily:000300.SH.close",
        vendor_name="tushare",
        frequency="daily",
        unit="index",
    ),
    CrisisInputSpec(
        field="aa_5y",
        alias="S0059760",
        kind=BackfillKind.CHOICE_EDB,
        series_id="EMM00166683",
        series_name="中债企业债到期收益率(AA):5年",
        vendor_series_code="EMM00166683",
        vendor_name="choice",
        frequency="daily",
        unit="%",
    ),
    CrisisInputSpec(
        field="gov_5y",
        alias="S0059747",
        kind=BackfillKind.CHOICE_EDB,
        series_id="EMM00166462",
        series_name="中债国债到期收益率:5年",
        vendor_series_code="EMM00166462",
        vendor_name="choice",
        frequency="daily",
        unit="%",
    ),
    CrisisInputSpec(
        field="usdcny",
        alias="M0067855",
        kind=BackfillKind.CHOICE_EDB,
        series_id="EMM00058124",
        series_name="中间价:美元兑人民币",
        vendor_series_code="EMM00058124",
        vendor_name="choice",
        frequency="daily",
        unit="CNY/USD",
    ),
    CrisisInputSpec(
        field="nanhua",
        alias="NH0100.NHF",
        kind=BackfillKind.COMMODITY_NHCI,
        series_id="NHCI.NH",
        series_name="Nanhua commodity index",
        vendor_series_code="tushare.index_daily.NHCI.NH.close",
        vendor_name="tushare",
        frequency="daily",
        unit="index",
    ),
    CrisisInputSpec(
        field="dr007",
        alias="DR007.IB",
        kind=BackfillKind.PUBLIC_DR007,
        series_id="CA.DR007",
        series_name="存款类机构质押式回购加权利率:DR007",
        vendor_series_code="repo_rate_query:FDR007",
        vendor_name="public_repo_rate_query",
        frequency="daily",
        unit="%",
    ),
    CrisisInputSpec(
        field="reverse_repo_7d",
        alias="M0041653",
        kind=BackfillKind.CHOICE_EDB,
        series_id="EMM00088132",
        series_name="公开市场操作:逆回购:7天:中标利率",
        vendor_series_code="EMM00088132",
        vendor_name="choice",
        frequency="daily",
        unit="%",
    ),
)


def backfill_crisis_score_inputs(
    *,
    duckdb_path: str | None = None,
    start_date: str = DEFAULT_START_DATE,
    end_date: str | None = None,
    dry_run: bool = False,
    aliases: list[str] | None = None,
) -> dict[str, object]:
    settings = get_settings()
    resolved_end = end_date or date.today().isoformat()
    _validate_iso_date(start_date, field_name="start_date")
    _validate_iso_date(resolved_end, field_name="end_date")
    if resolved_end < start_date:
        raise ValueError("end_date must be on or after start_date.")

    db_path = Path(duckdb_path or settings.duckdb_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    selected = _select_specs(aliases)
    run_id = f"crisis_score_inputs_backfill:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"

    if dry_run:
        return {
            "dry_run": True,
            "duckdb_path": str(db_path),
            "start_date": start_date,
            "end_date": resolved_end,
            "input_count": len(selected),
            "inputs": [_dry_run_plan(spec, start_date=start_date, end_date=resolved_end) for spec in selected],
            "coverage_before": _coverage_snapshot(selected, db_path),
        }

    results: dict[str, object] = {}
    errors: dict[str, str] = {}
    for spec in selected:
        try:
            results[spec.alias] = _backfill_input(
                spec,
                duckdb_path=db_path,
                start_date=start_date,
                end_date=resolved_end,
                run_id=run_id,
            )
        except Exception as exc:
            errors[spec.alias] = str(exc)
            results[spec.alias] = {"status": "error", "error": str(exc)}

    return {
        "dry_run": False,
        "duckdb_path": str(db_path),
        "start_date": start_date,
        "end_date": resolved_end,
        "run_id": run_id,
        "input_count": len(selected),
        "results": results,
        "errors": errors,
        "coverage_after": _coverage_snapshot(selected, db_path),
    }


def _backfill_input(
    spec: CrisisInputSpec,
    *,
    duckdb_path: Path,
    start_date: str,
    end_date: str,
    run_id: str,
) -> dict[str, object]:
    if spec.kind == BackfillKind.COMMODITY_NHCI:
        payload = run_commodity_daily_ingest(
            start_date=start_date,
            end_date=end_date,
            duckdb_path=str(duckdb_path),
            products=("NHCI",),
            dry_run=False,
        )
        return {
            "status": str(payload.get("status") or "completed"),
            "kind": spec.kind.value,
            "field": spec.field,
            "alias": spec.alias,
            "series_id": spec.series_id,
            "row_count": int(payload.get("row_count") or 0),
            "table": payload.get("table"),
        }

    if spec.kind == BackfillKind.TUSHARE_CSI300:
        rows = _fetch_csi300_rows(start_date=start_date, end_date=end_date)
    elif spec.kind == BackfillKind.PUBLIC_DR007:
        rows = fetch_public_dr007_rows(start_date=start_date, end_date=end_date)
    elif spec.kind == BackfillKind.CHOICE_EDB:
        rows = _fetch_choice_edb_rows(spec, start_date=start_date, end_date=end_date)
    else:
        raise ValueError(f"Unsupported crisis score backfill kind: {spec.kind}")

    macro_rows = _to_macro_rows(rows, spec=spec, start_date=start_date, end_date=end_date)
    if not macro_rows:
        return {
            "status": "no_rows",
            "kind": spec.kind.value,
            "field": spec.field,
            "alias": spec.alias,
            "series_id": spec.series_id,
            "written_rows": 0,
        }

    meta = _series_meta(spec)
    written = persist_macro_environment_rows(
        duckdb_path=duckdb_path,
        rows=macro_rows,
        metas={spec.series_id: meta},
        run_id=run_id,
        start_date=start_date,
        end_date=end_date,
    )
    return {
        "status": "completed",
        "kind": spec.kind.value,
        "field": spec.field,
        "alias": spec.alias,
        "series_id": spec.series_id,
        "written_rows": written,
    }


def _fetch_choice_edb_rows(
    spec: CrisisInputSpec,
    *,
    start_date: str,
    end_date: str,
) -> list[BackfillRow]:
    return _fetch_from_choice_edb(
        series_id=spec.series_id,
        series_name=spec.series_name,
        vendor_series_code=spec.vendor_series_code,
        start_date=start_date,
        end_date=end_date,
        frequency=spec.frequency,
        unit=spec.unit,
    )


def _fetch_csi300_rows(*, start_date: str, end_date: str) -> list[dict[str, Any]]:
    from backend.app.tasks.choice_macro import _fetch_tushare_cross_asset_history_rows  # noqa: PLC0415

    report_date = date.fromisoformat(end_date)
    lookback_days = max(1, (report_date - date.fromisoformat(start_date)).days + 1)
    raw_rows = _fetch_tushare_cross_asset_history_rows(
        duckdb_path="",
        report_date=report_date,
        lookback_days=lookback_days,
    )
    return [
        row
        for row in raw_rows
        if str(row.get("series_id")) == "CA.CSI300"
        and start_date <= str(row.get("trade_date")) <= end_date
    ]


def _to_macro_rows(
    rows: list[BackfillRow] | list[MacroRow] | list[dict[str, Any]],
    *,
    spec: CrisisInputSpec,
    start_date: str,
    end_date: str,
) -> list[MacroRow]:
    vendor_version = f"vv_crisis_score_{spec.series_id}_{start_date.replace('-', '')}_{end_date.replace('-', '')}"
    out: list[MacroRow] = []
    for row in rows:
        if isinstance(row, MacroRow):
            if row.trade_date < start_date or row.trade_date > end_date:
                continue
            out.append(
                MacroRow(
                    series_id=row.series_id,
                    series_name=row.series_name,
                    vendor_series_code=row.vendor_series_code or spec.vendor_series_code,
                    vendor_name=row.vendor_name,
                    trade_date=row.trade_date,
                    value_numeric=row.value_numeric,
                    frequency=row.frequency,
                    unit=row.unit,
                    source_version=row.source_version,
                    vendor_version=row.vendor_version,
                )
            )
            continue
        if isinstance(row, BackfillRow):
            if row.trade_date < start_date or row.trade_date > end_date:
                continue
            out.append(
                MacroRow(
                    series_id=row.series_id,
                    series_name=row.series_name,
                    vendor_series_code=spec.vendor_series_code,
                    vendor_name=spec.vendor_name,
                    trade_date=row.trade_date,
                    value_numeric=row.value_numeric,
                    frequency=row.frequency,
                    unit=row.unit,
                    source_version=f"sv_crisis_score_{spec.field}",
                    vendor_version=vendor_version,
                )
            )
            continue

        trade_date = str(row.get("trade_date") or "")
        value = row.get("value_numeric")
        if trade_date < start_date or trade_date > end_date or value is None:
            continue
        out.append(
            MacroRow(
                series_id=spec.series_id,
                series_name=spec.series_name,
                vendor_series_code=spec.vendor_series_code,
                vendor_name=spec.vendor_name,
                trade_date=trade_date,
                value_numeric=float(value),
                frequency=spec.frequency,
                unit=spec.unit,
                source_version=str(row.get("source_version") or f"sv_crisis_score_{spec.field}"),
                vendor_version=str(row.get("vendor_version") or vendor_version),
            )
        )
    return out


def _series_meta(spec: CrisisInputSpec) -> SeriesMeta:
    if spec.series_id in CHOICE_SERIES:
        return CHOICE_SERIES[spec.series_id]
    request_options = "IsLatest=0,StartDate=__START_DATE__,EndDate=__END_DATE__,Ispandas=1,RECVtimeout=20"
    return SeriesMeta(
        series_id=spec.series_id,
        series_name=spec.series_name,
        vendor_name=spec.vendor_name,
        vendor_series_code=spec.vendor_series_code,
        frequency=spec.frequency,
        unit=spec.unit,
        theme="crisis_score_inputs",
        tags=("crisis_score", "backfill"),
        refresh_tier="stable",
        request_options=request_options,
        fetch_mode="date_slice",
        fetch_granularity="batch",
        policy_note=f"Crisis Score input backfill for alias {spec.alias}.",
    )


def _select_specs(aliases: list[str] | None) -> tuple[CrisisInputSpec, ...]:
    if not aliases:
        return CRISIS_SCORE_INPUT_SPECS
    wanted = {str(alias).strip().lower() for alias in aliases if str(alias).strip()}
    selected = tuple(spec for spec in CRISIS_SCORE_INPUT_SPECS if spec.alias.lower() in wanted)
    if not selected:
        known = ", ".join(spec.alias for spec in CRISIS_SCORE_INPUT_SPECS)
        raise ValueError(f"No crisis score inputs matched aliases={sorted(wanted)}; known aliases: {known}")
    return selected


def _dry_run_plan(spec: CrisisInputSpec, *, start_date: str, end_date: str) -> dict[str, object]:
    return {
        "field": spec.field,
        "alias": spec.alias,
        "kind": spec.kind.value,
        "series_id": spec.series_id,
        "vendor_series_code": spec.vendor_series_code,
        "start_date": start_date,
        "end_date": end_date,
    }


def _coverage_snapshot(specs: tuple[CrisisInputSpec, ...], duckdb_path: Path) -> list[dict[str, object]]:
    coverage: list[dict[str, object]] = []
    for spec in specs:
        frame = load_series_by_alias(spec.alias, duckdb_path=duckdb_path)
        if frame.empty:
            coverage.append(
                {
                    "field": spec.field,
                    "alias": spec.alias,
                    "row_count": 0,
                    "earliest": None,
                    "latest": None,
                    "series_id": None,
                }
            )
            continue
        frame = frame.sort_values("date")
        coverage.append(
            {
                "field": spec.field,
                "alias": spec.alias,
                "row_count": int(len(frame)),
                "earliest": str(frame.iloc[0]["date"])[:10],
                "latest": str(frame.iloc[-1]["date"])[:10],
                "series_id": str(frame.iloc[-1]["series_id"]),
            }
        )
    return coverage


def _validate_iso_date(value: str, *, field_name: str) -> None:
    date.fromisoformat(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Crisis Score input series into DuckDB.")
    parser.add_argument("--duckdb-path", default=None)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--aliases",
        nargs="+",
        default=None,
        help="Optional subset of crisis score aliases, e.g. sh000300 S0059747",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = backfill_crisis_score_inputs(
        duckdb_path=args.duckdb_path,
        start_date=args.start_date,
        end_date=args.end_date,
        dry_run=args.dry_run,
        aliases=args.aliases,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
