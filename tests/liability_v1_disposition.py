from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.helpers import load_module
from tests.liability_v1_harness import MANIFEST_PATH, compatibility_diffs, load_json_file, sample_cases_from_manifest

DISPOSITION_CATEGORIES = {
    "implementation-defect",
    "data-issue",
    "historical-compatibility",
    "pending-confirmation",
    "architecture-invalid",
    "transitional-seam",
}


def _build_client() -> TestClient:
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    return TestClient(main_mod.app)


def _diff_path(diff: str) -> str:
    return diff.split(":", 1)[0].strip()


def _approx_equal(left: object, right: object, *, tolerance: float = 1e-9) -> bool:
    try:
        return abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return False


def monthly_tie_order_residual_paths(
    actual_payload: dict[str, Any],
    expected_payload: dict[str, Any],
) -> dict[str, str]:
    paths: dict[str, str] = {}
    actual_months = actual_payload.get("months")
    expected_months = expected_payload.get("months")
    if not isinstance(actual_months, list) or not isinstance(expected_months, list):
        return paths

    for month_index, (actual_month, expected_month) in enumerate(zip(actual_months, expected_months, strict=False)):
        if not isinstance(actual_month, dict) or not isinstance(expected_month, dict):
            continue
        for field_name in ("counterparty_details", "counterparty_top10"):
            actual_rows = actual_month.get(field_name)
            expected_rows = expected_month.get(field_name)
            if not isinstance(actual_rows, list) or not isinstance(expected_rows, list):
                continue

            start = 0
            while start < len(expected_rows):
                expected_row = expected_rows[start]
                if not isinstance(expected_row, dict):
                    start += 1
                    continue
                tie_value = expected_row.get("avg_value")
                end = start + 1
                while end < len(expected_rows):
                    next_row = expected_rows[end]
                    if not isinstance(next_row, dict) or not _approx_equal(next_row.get("avg_value"), tie_value):
                        break
                    end += 1

                if end - start > 1 and end <= len(actual_rows):
                    expected_slice = expected_rows[start:end]
                    actual_slice = actual_rows[start:end]
                    if all(isinstance(row, dict) for row in actual_slice):
                        expected_names = [str(row.get("name", "")) for row in expected_slice]
                        actual_names = [str(row.get("name", "")) for row in actual_slice]
                        if expected_names != actual_names and set(expected_names) == set(actual_names):
                            if all(_approx_equal(row.get("avg_value"), tie_value) for row in actual_slice):
                                for row_index in range(start, end):
                                    base_path = f"$.months[{month_index}].{field_name}[{row_index}]"
                                    for suffix in (".name", ".type", ".weighted_cost"):
                                        paths[f"{base_path}{suffix}"] = "equal-value-tie-order"
                start = end

    return paths


def classify_diff(interface: str, diff: str) -> str:
    path = _diff_path(diff)
    normalized = diff.lower()

    if "unexpected field" in normalized or "missing in actual payload" in normalized:
        if any(token in path for token in (".pct", ".amount_yi", ".weighted_rate", ".amount")):
            return "transitional-seam"
        if "by_type" in path and ".name" in path:
            return "historical-compatibility"

    if interface == "yield_metrics":
        return "pending-confirmation"

    if interface == "liabilities_monthly":
        if any(token in path for token in (".avg_", ".mom_", ".num_days", "ytd_avg_", ".proportion")):
            return "pending-confirmation"
        return "transitional-seam"

    if interface == "liabilities_counterparty":
        if "by_type" in path:
            return "historical-compatibility"
        if any(token in path for token in (".weighted_cost", ".value", ".name", ".type")):
            return "pending-confirmation"
        return "transitional-seam"

    if interface == "risk_buckets":
        if any(token in path for token in (".bucket", "term_buckets")):
            return "historical-compatibility"
        if any(token in path for token in (".amount", ".name")):
            return "pending-confirmation"
        return "transitional-seam"

    return "pending-confirmation"


def generate_semantic_disposition_report(manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = load_json_file(manifest_path)
    client = _build_client()
    interfaces: list[dict[str, Any]] = []

    for case in sample_cases_from_manifest(manifest):
        response = client.get(case.spec.path, params=case.request)
        actual_payload = response.json()
        diffs = compatibility_diffs(actual_payload, case.compatibility_payload)
        tie_order_paths = (
            monthly_tie_order_residual_paths(actual_payload, case.compatibility_payload)
            if case.interface == "liabilities_monthly"
            else {}
        )
        classified = []
        for diff in diffs:
            path = _diff_path(diff)
            category = classify_diff(case.interface, diff)
            finding: dict[str, Any] = {"category": category, "diff": diff}
            residual_kind = tie_order_paths.get(path)
            if residual_kind is not None:
                finding["category"] = "transitional-seam"
                finding["residual_kind"] = residual_kind
            classified.append(finding)
        counts = Counter(item["category"] for item in classified)
        residual_counts = Counter(
            str(item["residual_kind"])
            for item in classified
            if item.get("residual_kind")
        )
        interfaces.append(
            {
                "sample_id": case.sample_id,
                "interface": case.interface,
                "path": case.spec.path,
                "request": case.request,
                "http_status": response.status_code,
                "diff_count": len(diffs),
                "category_counts": dict(counts),
                "residual_kind_counts": dict(residual_counts),
                "representative_findings": classified[:20],
            }
        )

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "manifest_path": str(manifest_path),
        "manifest_status": manifest.get("status"),
        "interfaces": interfaces,
    }
