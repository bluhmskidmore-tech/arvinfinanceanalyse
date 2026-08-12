from __future__ import annotations

import argparse
import json
import logging
import sys
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services import executive_service as es  # noqa: E402


class _PerfLogCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[dict[str, object]] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if " perf: " not in message:
            return
        parsed: dict[str, object] = {"message": message}
        for token in message.split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            if key == "ms":
                try:
                    parsed[key] = int(value)
                except ValueError:
                    parsed[key] = value
            else:
                parsed[key] = value
        if "step" in parsed and "ms" in parsed:
            self.records.append(parsed)


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((percentile / 100) * len(ordered) + 0.999999) - 1))
    return ordered[index]


def _timed_snapshot(report_date: str | None, allow_partial: bool) -> tuple[dict[str, object], int]:
    started_at = time.perf_counter()
    envelope = es.home_snapshot_envelope(report_date=report_date, allow_partial=allow_partial)
    return envelope, int((time.perf_counter() - started_at) * 1000)


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile home snapshot service cold and warm paths.")
    parser.add_argument("--report-date", default=None)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--samples", type=int, default=7)
    args = parser.parse_args()

    bounded_samples = max(1, min(args.samples, 30))
    es.invalidate_home_snapshot_cache()
    collector = _PerfLogCollector()
    service_logger = logging.getLogger(es.__name__)
    previous_level = service_logger.level
    service_logger.addHandler(collector)
    service_logger.setLevel(logging.INFO)
    try:
        es._warm_home_snapshot_cache_quietly(
            report_date=args.report_date,
            allow_partial=bool(args.allow_partial),
        )
    finally:
        service_logger.removeHandler(collector)
        service_logger.setLevel(previous_level)
    prewarm_status = es.home_snapshot_prewarm_status()

    samples: list[dict[str, object]] = []
    for index in range(1, bounded_samples + 1):
        envelope, duration_ms = _timed_snapshot(args.report_date, bool(args.allow_partial))
        result = envelope.get("result") if isinstance(envelope, dict) else {}
        result_meta = envelope.get("result_meta") if isinstance(envelope, dict) else {}
        samples.append(
            {
                "index": index,
                "duration_ms": duration_ms,
                "report_date": result.get("report_date") if isinstance(result, dict) else None,
                "result_kind": result_meta.get("result_kind") if isinstance(result_meta, dict) else None,
                "source_version": result_meta.get("source_version") if isinstance(result_meta, dict) else None,
            }
        )

    durations = [int(sample["duration_ms"]) for sample in samples]
    step_durations = prewarm_status.get("last_step_durations_ms")
    slowest_steps = []
    if isinstance(step_durations, dict):
        slowest_steps = [
            {"step": str(step), "duration_ms": int(duration)}
            for step, duration in sorted(
                step_durations.items(),
                key=lambda item: int(item[1]),
                reverse=True,
            )
        ]

    summary = {
        "mode": "in-process-service",
        "request": {
            "report_date": args.report_date,
            "allow_partial": bool(args.allow_partial),
            "samples": bounded_samples,
        },
        "prewarm": prewarm_status,
        "slowest_prewarm_steps": slowest_steps[:10],
        "detail_perf_steps": sorted(
            collector.records,
            key=lambda item: int(item.get("ms", 0)),
            reverse=True,
        ),
        "samples": samples,
        "warm_stats": {
            "min_ms": min(durations) if durations else None,
            "p50_ms": int(statistics.median(durations)) if durations else None,
            "p95_ms": _percentile(durations, 95),
            "max_ms": max(durations) if durations else None,
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if prewarm_status.get("status") == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
