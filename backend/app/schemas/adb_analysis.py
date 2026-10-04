from __future__ import annotations

from typing import Any, Literal

from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, ConfigDict, RootModel


class _StrictAdbModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdbAnalysisEnvelope(_StrictAdbModel):
    result_meta: ResultMeta
    result: dict[str, Any]
    calibration: dict[str, Any]


class AdbInsightsEnvelope(_StrictAdbModel):
    result_meta: ResultMeta
    result: dict[str, Any]


class AdbCoverageTable(_StrictAdbModel):
    dates_count: int
    dates: list[str]
    error: Literal["table_not_found"] | None = None


class AdbSnapshotCoverage(_StrictAdbModel):
    zqtz_snapshot: AdbCoverageTable
    tyw_snapshot: AdbCoverageTable


class AdbFormalCoverage(_StrictAdbModel):
    formal_zqtz: AdbCoverageTable
    formal_tyw: AdbCoverageTable


class AdbCoverageResponse(_StrictAdbModel):
    start_date: str
    end_date: str
    calendar_days: int
    snapshot_tables: AdbSnapshotCoverage
    formal_tables: AdbFormalCoverage
    snapshot_date_count: int
    formal_date_count: int
    missing_dates: list[str]
    missing_count: int
    coverage_pct: float


class AdbBackfillFailure(_StrictAdbModel):
    date: str
    error_code: Literal["ADB_BACKFILL_DISPATCH_FAILED"]
    error_summary: Literal["补建任务派发失败。"]


class AdbBackfillNoActionResponse(_StrictAdbModel):
    status: Literal["no_action"]
    message: Literal["指定区间没有需要补建的日期。"]
    snapshot_dates: int
    formal_dates: int


class AdbBackfillDispatchResponse(_StrictAdbModel):
    status: Literal["queued", "failed"]
    total_missing: int
    queued_count: int
    failed_count: int
    failed: list[AdbBackfillFailure]
    message: Literal[
        "补建任务已全部派发。",
        "补建任务已派发，部分日期派发失败。",
        "补建任务派发失败。",
    ]


class AdbBackfillResponse(
    RootModel[AdbBackfillNoActionResponse | AdbBackfillDispatchResponse]
):
    pass
