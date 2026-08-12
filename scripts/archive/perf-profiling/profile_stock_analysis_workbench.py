from __future__ import annotations

import gc
import hashlib
import json
import os
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.api.routes import market_data_livermore as route_module  # noqa: E402
from backend.app.governance.settings import get_settings  # noqa: E402


ROUNDS = int(os.environ.get("STOCK_WORKBENCH_PROFILE_ROUNDS", "7"))
AS_OF_DATE = os.environ.get("STOCK_WORKBENCH_PROFILE_AS_OF_DATE") or None
INCLUDE = os.environ.get("STOCK_WORKBENCH_PROFILE_INCLUDE") or None
SECTOR_WINDOW_DAYS = int(os.environ.get("STOCK_WORKBENCH_PROFILE_SECTOR_WINDOW_DAYS", "20"))
TOP_K = int(os.environ.get("STOCK_WORKBENCH_PROFILE_TOP_K", "10"))


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((percentile_value / 100) * len(ordered) + 0.999999) - 1))
    return round(ordered[index], 3)


def summarize(values: list[float]) -> dict[str, float | None]:
    return {
        "min": percentile(values, 0),
        "median": round(statistics.median(values), 3) if values else None,
        "p95": percentile(values, 95),
        "max": percentile(values, 100),
    }


def canonical_payload(payload: dict[str, object]) -> tuple[str, int]:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    result_meta = normalized.get("result_meta")
    if isinstance(result_meta, dict):
        result_meta.pop("generated_at", None)
    result = normalized.get("result")
    modules = result.get("modules") if isinstance(result, dict) else None
    main = modules.get("main") if isinstance(modules, dict) else None
    meta = main.get("meta") if isinstance(main, dict) else None
    if isinstance(meta, dict):
        meta.pop("trace_id", None)

    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), len(encoded)


def sample(settings: object, *, invalidate: bool) -> dict[str, Any]:
    if invalidate:
        route_module.market_home_response_cache.invalidate()
        gc.collect()

    tracemalloc.start()
    started_at = time.perf_counter()
    payload, cache_status, compute_ms, overlay_ms, cache_ms = route_module._cached_stock_analysis_workbench(
        settings=settings,
        as_of_date=AS_OF_DATE,
        include=INCLUDE,
        sector_window_days=SECTOR_WINDOW_DAYS,
        top_k=TOP_K,
    )
    total_ms = (time.perf_counter() - started_at) * 1000
    _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    payload_hash, payload_bytes = canonical_payload(payload)
    return {
        "kind": "cold" if invalidate else "warm",
        "cacheStatus": cache_status,
        "totalMs": round(total_ms, 3),
        "computeMs": round(compute_ms, 3),
        "overlayMs": round(overlay_ms, 3),
        "cacheMs": round(cache_ms, 3),
        "payloadBytes": payload_bytes,
        "peakPythonBytes": peak_bytes,
        "payloadHash": payload_hash,
        "resolvedAsOfDate": payload.get("result", {}).get("as_of_date")
        if isinstance(payload.get("result"), dict)
        else None,
    }


def main() -> int:
    if ROUNDS < 1:
        raise ValueError(f"STOCK_WORKBENCH_PROFILE_ROUNDS must be positive, got {ROUNDS}")
    settings = get_settings()
    samples: list[dict[str, Any]] = []
    failures: list[str] = []
    for _round in range(ROUNDS):
        cold = sample(settings, invalidate=True)
        warm = sample(settings, invalidate=False)
        samples.extend([cold, warm])
        if cold["cacheStatus"] != "produce":
            failures.append(f"cold sample returned cache status {cold['cacheStatus']}")
        if warm["cacheStatus"] != "hit":
            failures.append(f"warm sample returned cache status {warm['cacheStatus']}")
        if cold["payloadHash"] != warm["payloadHash"]:
            failures.append("cold/warm canonical payload hash mismatch")

    payload_hashes = {sample_row["payloadHash"] for sample_row in samples}
    if len(payload_hashes) != 1:
        failures.append(f"canonical payload changed across rounds: {len(payload_hashes)} hashes")

    cold_samples = [sample_row for sample_row in samples if sample_row["kind"] == "cold"]
    warm_samples = [sample_row for sample_row in samples if sample_row["kind"] == "warm"]
    report = {
        "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "parameters": {
            "asOfDate": AS_OF_DATE or "default",
            "include": INCLUDE or "default(main,evidence_summary)",
            "sectorWindowDays": SECTOR_WINDOW_DAYS,
            "topK": TOP_K,
            "rounds": ROUNDS,
            "cacheClear": "process-local market_home_response_cache.invalidate() before each cold sample",
        },
        "summary": {
            "coldTotalMs": summarize([sample_row["totalMs"] for sample_row in cold_samples]),
            "coldComputeMs": summarize([sample_row["computeMs"] for sample_row in cold_samples]),
            "coldOverlayMs": summarize([sample_row["overlayMs"] for sample_row in cold_samples]),
            "warmTotalMs": summarize([sample_row["totalMs"] for sample_row in warm_samples]),
            "warmCacheMs": summarize([sample_row["cacheMs"] for sample_row in warm_samples]),
            "coldPeakPythonBytes": summarize(
                [float(sample_row["peakPythonBytes"]) for sample_row in cold_samples]
            ),
            "payloadBytes": sorted({sample_row["payloadBytes"] for sample_row in samples}),
            "payloadHashes": sorted(payload_hashes),
            "resolvedAsOfDates": sorted(
                {str(sample_row["resolvedAsOfDate"]) for sample_row in samples}
            ),
        },
        "samples": samples,
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
