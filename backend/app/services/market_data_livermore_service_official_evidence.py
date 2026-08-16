"""从 market_data_livermore_service 拆出的官方发布证据与业务输入版本口径。

门面模块逐名 re-export；行为与拆分前完全一致。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path

from backend.app.core_finance.cycle_macro_score import (
    CN10Y_SERIES_ID,
    CSI300_PE_SERIES_ID,
    M2_YOY_SERIES_ID,
    PMI_SERIES_ID,
    SOCIAL_FINANCING_YOY_SERIES_ID,
)

_CYCLE_INPUT_ROW_CONTRACTS: dict[str, tuple[str, str, bool]] = {
    PMI_SERIES_ID: ("monthly", "index", True),
    SOCIAL_FINANCING_YOY_SERIES_ID: ("monthly", "%", True),
    M2_YOY_SERIES_ID: ("monthly", "%", True),
    CSI300_PE_SERIES_ID: ("daily", "x", False),
    CN10Y_SERIES_ID: ("daily", "%", False),
}
_BACKFILL_RUN_ID_PATTERN = re.compile(r"^backfill_macro_v1:(\d{8})T\d{6}Z$")
_OFFICIAL_AVAILABILITY_MANIFEST_VERSION = "cycle_macro_official_availability.v1"
_OFFICIAL_BACKFILL_RULE_VERSION = "rv_backfill_macro_v1"
_OFFICIAL_MAPPING_VERSION_BY_SOURCE = {
    "nbs_pmi_release": "rv_nbs_pmi_release_v1",
    "pbc_financial_statistics_release": "rv_pbc_financial_statistics_release_v1",
}
_OFFICIAL_VENDOR_VERSION_PATTERN = re.compile(
    r"^vv_backfill_macro_"
    r"(nbs_pmi_release|pbc_financial_statistics_release)_"
    r"\d{8}_([0-9a-f]{16})_[0-9a-f]{16}$"
)
_FULL_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _strict_manifest_date(value: object) -> date | None:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == text else None


def _strict_manifest_timestamp_date(value: object) -> date | None:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.date()


def _pbc_release_evidence_latest_available_date(
    *,
    releases: list[object],
    series_id: str,
    covered_period_start: date,
    covered_period_end: date,
    artifact_manifest_sha256: str,
    artifact_record: dict[str, object],
) -> date | None:
    if covered_period_start.day != 1 or covered_period_end.day != 1:
        return None
    canonical_artifacts: list[dict[str, str]] = []
    observed_months: list[date] = []
    available_dates: list[date] = []
    for raw in releases:
        if not isinstance(raw, dict):
            continue
        if raw.get("source") != "pbc_financial_statistics_release":
            continue
        if raw.get("series_id") != series_id:
            continue
        report_month = str(raw.get("report_month") or "")
        if re.fullmatch(r"\d{4}-\d{2}", report_month) is None:
            return None
        report_date = _strict_manifest_date(f"{report_month}-01")
        if report_date is None:
            return None
        if not covered_period_start <= report_date <= covered_period_end:
            continue
        release_url = str(raw.get("release_url") or "")
        published_at = str(raw.get("published_at") or "")
        available_at = str(raw.get("available_at") or published_at)
        artifact_sha256 = str(raw.get("artifact_sha256") or "")
        published_date = _strict_manifest_timestamp_date(published_at)
        available_date = _strict_manifest_timestamp_date(available_at)
        if (
            not release_url
            or published_date is None
            or available_date is None
            or available_date < published_date
            or _FULL_SHA256_PATTERN.fullmatch(artifact_sha256) is None
        ):
            return None
        observed_months.append(report_date)
        available_dates.append(available_date)
        canonical_artifacts.append(
            {
                "report_month": report_month,
                "release_url": release_url,
                "published_at": published_at,
                "available_at": available_at,
                "artifact_sha256": artifact_sha256,
            }
        )
    if not canonical_artifacts:
        return None
    canonical_artifacts.sort(key=lambda row: row["report_month"])
    observed_months.sort()
    expected_month_count = (
        (covered_period_end.year - covered_period_start.year) * 12
        + covered_period_end.month
        - covered_period_start.month
        + 1
    )
    if (
        len(set(observed_months)) != len(observed_months)
        or len(observed_months) != expected_month_count
        or observed_months[0] != covered_period_start
        or observed_months[-1] != covered_period_end
    ):
        return None
    artifacts_json = json.dumps(
        canonical_artifacts,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    expected_artifact_manifest_sha256 = hashlib.sha256(
        artifacts_json.encode("utf-8")
    ).hexdigest()
    if artifact_manifest_sha256 != expected_artifact_manifest_sha256:
        return None
    if artifact_record.get("artifact_kind") != "artifact_set_manifest":
        return None
    component_hashes = artifact_record.get("component_artifact_sha256s")
    expected_component_hashes = [row["artifact_sha256"] for row in canonical_artifacts]
    if component_hashes != expected_component_hashes:
        return None
    return max(available_dates)


def _nbs_release_evidence_latest_available_date(
    *,
    releases: list[object],
    series_id: str,
    covered_period_start: date,
    covered_period_end: date,
    artifact_manifest_sha256: str,
    artifact_record: dict[str, object],
) -> date | None:
    matching_releases = [
        row
        for row in releases
        if isinstance(row, dict)
        and row.get("source") == "nbs_pmi_release"
        and row.get("series_id") == series_id
        and row.get("artifact_sha256") == artifact_manifest_sha256
        and row.get("covered_period_start") == covered_period_start.isoformat()
        and row.get("covered_period_end") == covered_period_end.isoformat()
    ]
    if len(matching_releases) != 1:
        return None
    if artifact_record.get("artifact_kind") != "official_release_artifact":
        return None
    release = matching_releases[0]
    published_at = str(release.get("published_at") or "")
    available_at = str(release.get("available_at") or published_at)
    published_date = _strict_manifest_timestamp_date(published_at)
    available_date = _strict_manifest_timestamp_date(available_at)
    if (
        published_date is None
        or available_date is None
        or available_date < published_date
    ):
        return None
    return available_date


def _official_release_evidence_latest_available_date(
    *,
    payload: object,
    source: str,
    series_id: str,
    covered_period_start: date,
    covered_period_end: date,
    artifact_manifest_sha256: str,
    artifact_record: dict[str, object],
) -> date | None:
    if not isinstance(payload, dict):
        return None
    releases = payload.get("releases")
    if not isinstance(releases, list):
        return None
    if source == "pbc_financial_statistics_release":
        return _pbc_release_evidence_latest_available_date(
            releases=releases,
            series_id=series_id,
            covered_period_start=covered_period_start,
            covered_period_end=covered_period_end,
            artifact_manifest_sha256=artifact_manifest_sha256,
            artifact_record=artifact_record,
        )
    if source == "nbs_pmi_release":
        return _nbs_release_evidence_latest_available_date(
            releases=releases,
            series_id=series_id,
            covered_period_start=covered_period_start,
            covered_period_end=covered_period_end,
            artifact_manifest_sha256=artifact_manifest_sha256,
            artifact_record=artifact_record,
        )
    return None


def livermore_data_version(duckdb_path: str) -> str:
    """Stable cross-process version fingerprint for persisted Livermore data."""
    path = Path(duckdb_path)
    try:
        stat = path.stat()
    except OSError:
        return "missing"
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _livermore_business_input_signature(path: Path) -> str:
    try:
        payload = path.read_bytes()
    except OSError:
        return "missing"
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
