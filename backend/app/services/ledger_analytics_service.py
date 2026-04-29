from __future__ import annotations

import io
import json
from datetime import date
from uuid import uuid4

from backend.app.repositories.ledger_analytics_repo import (
    POSITION_EXPORT_COLUMNS,
    LedgerAnalyticsRepository,
)
from backend.app.schemas.ledger import LedgerDashboardData, LedgerPositionItem
from openpyxl import Workbook

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class LedgerAnalyticsService:
    def __init__(self, duckdb_path: str) -> None:
        self.repo = LedgerAnalyticsRepository(duckdb_path)

    def dates(self) -> dict[str, object]:
        dates = self.repo.list_dates()
        latest = dates[0] if dates else None
        return {
            "data": {"items": [item["as_of_date"] for item in dates]},
            "metadata": _metadata(latest=latest, no_data=not bool(dates)),
            "trace": _trace(batch_id=_batch_id(latest)),
        }

    def dashboard(self, *, requested_as_of_date: str) -> dict[str, object]:
        dashboard = self.repo.dashboard(requested_as_of_date=requested_as_of_date)
        if dashboard is None:
            return {
                "data": LedgerDashboardData(
                    as_of_date=None,
                    asset_face_amount=None,
                    liability_face_amount=None,
                    net_face_exposure=None,
                    alert_count=None,
                ).model_dump(mode="json"),
                "metadata": _metadata(latest=None, no_data=True),
                "trace": _trace(
                    requested_as_of_date=requested_as_of_date,
                    resolved_as_of_date=None,
                    batch_id=None,
                ),
            }
        data = LedgerDashboardData(
            as_of_date=str(dashboard["as_of_date"]),
            asset_face_amount=dashboard["asset_face_amount"],
            liability_face_amount=dashboard["liability_face_amount"],
            net_face_exposure=dashboard["net_face_exposure"],
            alert_count=0,
        ).model_dump(mode="json")
        return {
            "data": data,
            "metadata": _metadata(
                latest=dashboard,
                no_data=False,
                stale=bool(dashboard["stale"]),
                fallback=bool(dashboard["fallback"]),
            ),
            "trace": _trace(
                requested_as_of_date=requested_as_of_date,
                resolved_as_of_date=str(dashboard["as_of_date"]),
                batch_id=dashboard["batch_id"],
            ),
        }

    def positions(
        self,
        *,
        requested_as_of_date: str,
        filters: dict[str, str | None],
        page: int,
        page_size: int,
    ) -> dict[str, object]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 500)
        result = self.repo.list_positions(
            requested_as_of_date=requested_as_of_date,
            filters=filters,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        if result is None:
            return {
                "data": {"items": [], "page": page, "page_size": page_size, "total": 0},
                "metadata": _metadata(latest=None, no_data=True),
                "trace": _trace(
                    requested_as_of_date=requested_as_of_date,
                    resolved_as_of_date=None,
                    batch_id=None,
                    filters={**filters, "page": page, "page_size": page_size},
                ),
            }
        items = [
            LedgerPositionItem(
                **item,
                trace=_position_item_trace(item),
            ).model_dump(mode="json")
            for item in result["items"]
        ]
        no_data = int(result["total"]) == 0
        return {
            "data": {
                "items": items,
                "page": page,
                "page_size": page_size,
                "total": int(result["total"]),
            },
            "metadata": _metadata(
                latest=result,
                no_data=no_data,
                stale=bool(result["stale"]),
                fallback=bool(result["fallback"]),
            ),
            "trace": _trace(
                requested_as_of_date=requested_as_of_date,
                resolved_as_of_date=str(result["as_of_date"]),
                batch_id=result["batch_id"],
                filters={**filters, "page": page, "page_size": page_size},
            ),
        }

    def export_positions(
        self,
        *,
        requested_as_of_date: str,
        filters: dict[str, str | None],
    ) -> tuple[str, bytes, dict[str, str]]:
        result = self.repo.list_positions(
            requested_as_of_date=requested_as_of_date,
            filters=filters,
            limit=None,
            offset=0,
        )
        if result is None:
            workbook = _positions_workbook(
                [],
                metadata={
                    "requested_as_of_date": requested_as_of_date,
                    "resolved_as_of_date": None,
                },
                filters=filters,
            )
            return (
                f"ledger-positions-{requested_as_of_date}.xlsx",
                _workbook_bytes(workbook),
                _export_headers(latest=None, no_data=True),
            )
        workbook = _positions_workbook(
            result["items"],
            metadata={
                **result,
                "requested_as_of_date": requested_as_of_date,
                "resolved_as_of_date": result["as_of_date"],
            },
            filters=filters,
        )
        return (
            f"ledger-positions-{result['as_of_date']}.xlsx",
            _workbook_bytes(workbook),
            _export_headers(
                latest=result,
                no_data=int(result["total"]) == 0,
                stale=bool(result["stale"]),
                fallback=bool(result["fallback"]),
            ),
        )


def normalize_requested_date(*, as_of_date: str | None) -> str:
    requested = (as_of_date or "").strip()
    if not requested:
        raise ValueError("as_of_date is required.")
    try:
        parsed = date.fromisoformat(requested)
    except ValueError as exc:
        raise ValueError("as_of_date must use YYYY-MM-DD format.") from exc
    if requested != parsed.isoformat():
        raise ValueError("as_of_date must use YYYY-MM-DD format.")
    return requested


def normalize_filters(
    *,
    direction: str | None,
    bond_code: str | None,
    portfolio: str | None,
    account_category_std: str | None,
    asset_class_std: str | None,
    cost_center: str | None,
) -> dict[str, str | None]:
    normalized_direction = direction.upper() if direction else None
    if normalized_direction not in {None, "ASSET", "LIABILITY"}:
        raise ValueError("direction must be ASSET or LIABILITY.")
    return {
        "direction": normalized_direction,
        "bond_code": bond_code,
        "portfolio": portfolio,
        "account_category_std": account_category_std,
        "asset_class_std": asset_class_std,
        "cost_center": cost_center,
    }


def _metadata(
    *,
    latest: dict[str, object] | None,
    no_data: bool,
    stale: bool = False,
    fallback: bool = False,
) -> dict[str, object]:
    return {
        "source_version": str(latest["source_version"]) if latest else None,
        "rule_version": str(latest["rule_version"]) if latest else None,
        "batch_id": _batch_id(latest),
        "stale": stale,
        "fallback": fallback,
        "no_data": no_data,
    }


def _trace(
    *,
    requested_as_of_date: str | None = None,
    resolved_as_of_date: str | None = None,
    batch_id: object | None,
    filters: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "request_id": f"req_ledger_{uuid4().hex[:12]}",
        "requested_as_of_date": requested_as_of_date,
        "resolved_as_of_date": resolved_as_of_date,
        "batch_id": batch_id,
        "filters": filters,
    }


def _batch_id(latest: dict[str, object] | None) -> int | str | None:
    if latest is None or latest.get("batch_id") is None:
        return None
    batch_id = latest["batch_id"]
    if isinstance(batch_id, int):
        return batch_id
    text = str(batch_id).strip()
    if text.isdigit():
        return int(text)
    return text


def _position_item_trace(item: dict[str, object]) -> dict[str, object]:
    trace: dict[str, object] = {
        "position_key": item["position_key"],
        "batch_id": item["batch_id"],
        "row_no": item["row_no"],
    }
    if not isinstance(item["batch_id"], int):
        trace["ingest_batch_id"] = item["batch_id"]
    return trace


def _positions_workbook(
    rows: list[dict[str, object]],
    *,
    metadata: dict[str, object],
    filters: dict[str, str | None],
) -> Workbook:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "positions"
    worksheet.append(list(POSITION_EXPORT_COLUMNS))
    for row in rows:
        worksheet.append([row.get(column) for column in POSITION_EXPORT_COLUMNS])

    meta = workbook.create_sheet("metadata")
    meta.append(["key", "value"])
    for key in (
        "batch_id",
        "requested_as_of_date",
        "resolved_as_of_date",
        "as_of_date",
        "source_version",
        "rule_version",
        "stale",
        "fallback",
        "total",
    ):
        meta.append([key, metadata.get(key)])
    meta.append(["filters", json.dumps(filters, ensure_ascii=False, sort_keys=True)])
    return workbook


def _workbook_bytes(workbook: Workbook) -> bytes:
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _export_headers(
    *,
    latest: dict[str, object] | None,
    no_data: bool,
    stale: bool = False,
    fallback: bool = False,
) -> dict[str, str]:
    return {
        "X-Ledger-Source-Version": str(latest["source_version"]) if latest else "",
        "X-Ledger-Rule-Version": str(latest["rule_version"]) if latest else "",
        "X-Ledger-Batch-Id": str(latest["batch_id"]) if latest else "",
        "X-Ledger-Stale": str(stale).lower(),
        "X-Ledger-Fallback": str(fallback).lower(),
        "X-Ledger-No-Data": str(no_data).lower(),
    }
