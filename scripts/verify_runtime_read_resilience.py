"""Bounded, read-only localhost probe for runtime read resilience.

The probe uses only fixed GET endpoints and records transport metadata. It
does not retain response bodies or business values. Redirects are not
followed. One absolute deadline covers connection, response headers, and the
complete response body so a slow byte stream cannot extend a request forever.
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import socket
import statistics
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

GENERATION_HEADER = "X-MOSS-Read-Generation"
ENDPOINTS = (
    "/health",
    "/health/ready",
    "/api/system-read-publication",
    "/ui/home/snapshot",
)
VERSIONED_ENDPOINTS = frozenset(
    {"/api/system-read-publication", "/ui/home/snapshot"}
)
POST_HEALTH_ENDPOINTS = ("/health", "/health/ready")
MAX_CONCURRENCY = 4
MAX_REQUESTS = 120
MAX_DURATION_SECONDS = 90.0


def _validated_origin(base_url: str) -> tuple[str, int]:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("base URL must be a bare loopback HTTP origin")
    try:
        port = parsed.port or 80
    except ValueError as exc:
        raise ValueError("base URL has an invalid port") from exc
    return parsed.hostname, port


def _remaining(deadline: float) -> float:
    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        raise TimeoutError("absolute request deadline exceeded")
    return remaining


def _arm_deadline(
    request_socket: socket.socket,
    deadline: float,
) -> tuple[threading.Timer, threading.Event]:
    expired = threading.Event()

    def interrupt() -> None:
        expired.set()
        try:
            request_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            # A completed peer close can win the race with the deadline timer.
            return

    timer = threading.Timer(_remaining(deadline), interrupt)
    timer.daemon = True
    timer.start()
    return timer, expired


def _probe_request(
    base_url: str,
    path: str,
    *,
    timeout_seconds: float,
    requested_generation: str | None = None,
    validate_publication: bool = False,
    overall_deadline: float | None = None,
) -> dict[str, Any]:
    """Fetch one fixed path and return transport-only observations."""

    if path not in ENDPOINTS:
        raise ValueError(f"unsupported probe path: {path}")
    host, port = _validated_origin(base_url)
    started = time.perf_counter()
    deadline = started + timeout_seconds
    if overall_deadline is not None:
        deadline = min(deadline, overall_deadline)
    sample: dict[str, Any] = {
        "path": path,
        "status": None,
        "elapsed_ms": None,
        "body_bytes": 0,
        "version_consistent": None,
        "error_category": None,
    }
    connection: http.client.HTTPConnection | None = None
    response: http.client.HTTPResponse | None = None
    deadline_timer: threading.Timer | None = None
    deadline_expired = threading.Event()
    try:
        connection = http.client.HTTPConnection(host, port, timeout=_remaining(deadline))
        connection.connect()
        request_socket = connection.sock
        if request_socket is None:
            raise ConnectionError("HTTP connection did not expose a connected socket")
        deadline_timer, deadline_expired = _arm_deadline(request_socket, deadline)
        headers = {"Accept": "application/json", "Connection": "close"}
        if requested_generation is not None:
            headers[GENERATION_HEADER] = requested_generation
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        sample["status"] = response.status
        response_generation = response.getheader(GENERATION_HEADER)
        body = response.read()
        if deadline_expired.is_set() or time.perf_counter() > deadline:
            sample["error_category"] = "timeout"
            return sample
        sample["body_bytes"] = len(body)

        if response.status != 200:
            sample["error_category"] = "http_status"
            return sample

        if requested_generation is not None:
            if not response_generation:
                sample["version_consistent"] = False
                sample["error_category"] = "missing_version_header"
            elif response_generation != requested_generation:
                sample["version_consistent"] = False
                sample["error_category"] = "version_mismatch"
            else:
                sample["version_consistent"] = True

        if validate_publication:
            try:
                payload = json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                sample["error_category"] = sample["error_category"] or "invalid_publication_json"
                return sample
            if not isinstance(payload, dict) or not isinstance(payload.get("enabled"), bool):
                sample["error_category"] = sample["error_category"] or "publication_contract"
                return sample
            enabled = payload["enabled"]
            sample["_publication_enabled"] = enabled
            if enabled:
                body_generation = payload.get("generation")
                sample["_publication_generation"] = body_generation
                expected_generation = requested_generation or body_generation
                if not isinstance(body_generation, str) or not body_generation:
                    sample["version_consistent"] = False
                    sample["error_category"] = sample["error_category"] or "publication_contract"
                elif not response_generation:
                    sample["version_consistent"] = False
                    sample["error_category"] = sample["error_category"] or "missing_version_header"
                elif response_generation != expected_generation or body_generation != expected_generation:
                    sample["version_consistent"] = False
                    sample["error_category"] = sample["error_category"] or "version_mismatch"
                elif sample["error_category"] is None:
                    sample["version_consistent"] = True
            elif requested_generation is not None:
                sample["version_consistent"] = False
                sample["error_category"] = sample["error_category"] or "version_mismatch"
            elif payload.get("generation") is not None:
                sample["error_category"] = sample["error_category"] or "publication_contract"
        return sample
    except TimeoutError:
        sample["error_category"] = "timeout"
        return sample
    except (ConnectionError, OSError, http.client.HTTPException):
        sample["error_category"] = (
            "timeout"
            if deadline_expired.is_set() or time.perf_counter() >= deadline
            else "connection_error"
        )
        return sample
    finally:
        if deadline_timer is not None:
            deadline_timer.cancel()
        if response is not None:
            # Deadline shutdown can make a second close report an OS error.
            with suppress(OSError):
                response.close()
        if connection is not None:
            connection.close()
        sample["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)


def _interaction(
    base_url: str,
    *,
    timeout_seconds: float,
    generation: str | None,
    overall_deadline: float,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for path in ENDPOINTS:
        samples.append(
            _probe_request(
                base_url,
                path,
                timeout_seconds=timeout_seconds,
                requested_generation=(generation if path in VERSIONED_ENDPOINTS else None),
                validate_publication=path == "/api/system-read-publication",
                overall_deadline=overall_deadline,
            )
        )
    return samples


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * percentile) - 1]


def _summarize(samples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for path in ENDPOINTS:
        rows = [sample for sample in samples if sample["path"] == path]
        elapsed = [float(row["elapsed_ms"]) for row in rows]
        sizes = [int(row["body_bytes"]) for row in rows]
        checked = [row for row in rows if row["version_consistent"] is not None]
        errors = Counter(
            str(row["error_category"])
            for row in rows
            if row["error_category"] is not None
        )
        summary[path] = {
            "requests": len(rows),
            "status_counts": dict(sorted(Counter(str(row["status"]) for row in rows).items())),
            "p50_ms": round(statistics.median(elapsed), 3) if elapsed else None,
            "p95_ms": _nearest_rank(elapsed, 0.95),
            "max_ms": max(elapsed) if elapsed else None,
            "body_bytes_min": min(sizes) if sizes else None,
            "body_bytes_max": max(sizes) if sizes else None,
            "version_checks": len(checked),
            "version_consistent": sum(row["version_consistent"] is True for row in checked),
            "failure_categories": dict(sorted(errors.items())),
            "error_rate": round(sum(errors.values()) / len(rows), 6) if rows else None,
        }
    return summary


def _markdown_report(result: dict[str, Any], command: str) -> str:
    load_errors = sum(
        sum(row["failure_categories"].values())
        for row in result["summary"].values()
    )
    error_rate = load_errors / result["load_sample_count"]
    lines = [
        "# MOSS runtime read resilience — round 2",
        "",
        (
            f"Bounded localhost GET sample: concurrency {result['clients']}, "
            f"rounds {result['rounds']}, load requests {result['load_sample_count']}, "
            f"total requests {result['total_sample_count']}, elapsed "
            f"{result['elapsed_seconds']:.3f}s."
        ),
        f"Load errors: {load_errors}/{result['load_sample_count']} ({error_rate:.3%}).",
        "",
        (
            "Publication mode was enabled and pinned to the handshake generation."
            if result["publication_enabled"]
            else "Publication mode was disabled; version pin checks were not applicable."
        ),
        "",
        "| Endpoint | N | Status counts | p50 ms | p95 ms | max ms | Body bytes min-max | Version checks | Error rate | Errors |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for path in ENDPOINTS:
        row = result["summary"][path]
        status = json.dumps(row["status_counts"], sort_keys=True, separators=(",", ":"))
        errors = json.dumps(row["failure_categories"], sort_keys=True, separators=(",", ":"))
        version = f"{row['version_consistent']}/{row['version_checks']}"
        lines.append(
            f"| `{path}` | {row['requests']} | `{status}` | {row['p50_ms']} | "
            f"{row['p95_ms']} | {row['max_ms']} | "
            f"{row['body_bytes_min']}-{row['body_bytes_max']} | {version} | "
            f"{row['error_rate']:.3%} | `{errors}` |"
        )
    lines.extend(
        [
            "",
            "## Ending health",
            "",
            "| Endpoint | Status | Elapsed ms | Body bytes | Failure category |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for sample in result["post_health"]:
        lines.append(
            f"| `{sample['path']}` | {sample['status']} | {sample['elapsed_ms']} | "
            f"{sample['body_bytes']} | {sample['error_category'] or ''} |"
        )
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            f"`{command}`",
            "",
            "This is a short, bounded sample of one local runtime. It does not establish whole-site performance, peak capacity, or all-day stability.",
            "",
        ]
    )
    return "\n".join(lines)


def run_measurement(
    *,
    base_url: str,
    clients: int,
    rounds: int,
    timeout_seconds: float,
    duration_seconds: float,
) -> dict[str, Any]:
    _validated_origin(base_url)
    if not 1 <= clients <= MAX_CONCURRENCY:
        raise ValueError(f"clients must be between 1 and {MAX_CONCURRENCY}")
    if rounds < 1:
        raise ValueError("rounds must be positive")
    if not 0 < timeout_seconds <= 30:
        raise ValueError("timeout seconds must be greater than 0 and at most 30")
    if not 0 < duration_seconds <= MAX_DURATION_SECONDS:
        raise ValueError(
            f"duration seconds must be greater than 0 and at most {MAX_DURATION_SECONDS:g}"
        )
    planned_requests = 1 + clients * rounds * len(ENDPOINTS) + len(POST_HEALTH_ENDPOINTS)
    if planned_requests > MAX_REQUESTS:
        raise ValueError(
            f"planned requests ({planned_requests}) exceed the {MAX_REQUESTS} request limit"
        )

    started = time.perf_counter()
    overall_deadline = started + duration_seconds
    handshake = _probe_request(
        base_url,
        "/api/system-read-publication",
        timeout_seconds=timeout_seconds,
        validate_publication=True,
        overall_deadline=overall_deadline,
    )
    if handshake["error_category"] is not None:
        raise RuntimeError(f"publication handshake failed: {handshake['error_category']}")
    publication_enabled = bool(handshake.get("_publication_enabled"))
    generation = handshake.get("_publication_generation") if publication_enabled else None

    load_samples: list[dict[str, Any]] = []
    for _round in range(rounds):
        if time.perf_counter() >= overall_deadline:
            break
        with ThreadPoolExecutor(max_workers=clients) as pool:
            futures = [
                pool.submit(
                    _interaction,
                    base_url,
                    timeout_seconds=timeout_seconds,
                    generation=generation,
                    overall_deadline=overall_deadline,
                )
                for _ in range(clients)
            ]
            for future in futures:
                load_samples.extend(future.result())

    post_health = [
        _probe_request(
            base_url,
            path,
            timeout_seconds=timeout_seconds,
            overall_deadline=overall_deadline,
        )
        for path in POST_HEALTH_ENDPOINTS
    ]
    all_samples = [handshake, *load_samples, *post_health]
    return {
        "clients": clients,
        "rounds": rounds,
        "publication_enabled": publication_enabled,
        "load_sample_count": len(load_samples),
        "total_sample_count": len(all_samples),
        "elapsed_seconds": time.perf_counter() - started,
        "summary": _summarize(load_samples),
        "post_health": post_health,
        "has_failures": any(sample["error_category"] is not None for sample in all_samples),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:7888")
    parser.add_argument("--clients", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--duration-seconds", type=float, default=60.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".codex-tmp/resilience-round2-load.md"),
    )
    args = parser.parse_args()
    try:
        result = run_measurement(
            base_url=args.base_url.rstrip("/"),
            clients=args.clients,
            rounds=args.rounds,
            timeout_seconds=args.timeout_seconds,
            duration_seconds=args.duration_seconds,
        )
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    command = (
        ".\\.venv\\Scripts\\python.exe scripts\\verify_runtime_read_resilience.py "
        f"--base-url {args.base_url.rstrip('/')} --clients {args.clients} "
        f"--rounds {args.rounds} --timeout-seconds {args.timeout_seconds:g} "
        f"--duration-seconds {args.duration_seconds:g} --output {args.output}"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_markdown_report(result, command), encoding="utf-8")
    compact = {
        "load_sample_count": result["load_sample_count"],
        "total_sample_count": result["total_sample_count"],
        "elapsed_seconds": round(result["elapsed_seconds"], 3),
        "publication_enabled": result["publication_enabled"],
        "summary": result["summary"],
        "post_health": result["post_health"],
        "output": str(args.output),
    }
    print(json.dumps(compact, sort_keys=True, separators=(",", ":")))
    return int(result["has_failures"])


if __name__ == "__main__":
    raise SystemExit(main())
