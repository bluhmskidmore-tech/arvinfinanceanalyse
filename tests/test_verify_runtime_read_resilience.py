from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from scripts import verify_runtime_read_resilience as probe


class _ProbeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self.send_response(503)
            body = b"unavailable"
        elif self.path == "/health/ready":
            self.send_response(200)
            body = b"0123456789"
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            for byte in body:
                try:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
                time.sleep(0.02)
            return
        elif self.path == "/api/system-read-publication":
            wire = (
                b"HTTP/1.1 200 OK\r\nContent-Length: 17\r\n"
                b"Content-Type: application/json\r\n\r\n"
                b'{"enabled":false}'
            )
            for byte in wire:
                try:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
                time.sleep(0.01)
            return
        elif self.path == "/ui/home/snapshot":
            self.send_response(200)
            body = b"{}"
            self.send_header(probe.GENERATION_HEADER, "system-read-v2")
        else:
            self.send_response(404)
            body = b"missing"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class _DisabledGenerationHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = b'{"enabled":false,"generation":"unexpected"}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _serve(
    handler: type[BaseHTTPRequestHandler] = _ProbeHandler,
) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def test_slow_drip_body_obeys_one_absolute_timeout() -> None:
    server, base_url = _serve()
    try:
        sample = probe._probe_request(
            base_url,
            "/health/ready",
            timeout_seconds=0.06,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert sample["error_category"] == "timeout"
    assert sample["elapsed_ms"] < 180
    assert sample["body_bytes"] == 0


def test_slow_drip_headers_obey_one_absolute_timeout() -> None:
    server, base_url = _serve()
    try:
        sample = probe._probe_request(
            base_url,
            "/api/system-read-publication",
            timeout_seconds=0.06,
            validate_publication=True,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert sample["error_category"] == "timeout"
    assert sample["elapsed_ms"] < 180
    assert sample["status"] is None


def test_expired_overall_deadline_returns_timeout_sample() -> None:
    sample = probe._probe_request(
        "http://127.0.0.1:1",
        "/health",
        timeout_seconds=1,
        overall_deadline=time.perf_counter() - 0.01,
    )

    assert sample["status"] is None
    assert sample["error_category"] == "timeout"
    assert sample["elapsed_ms"] < 50


def test_http_failure_is_classified_after_full_body_read() -> None:
    server, base_url = _serve()
    try:
        sample = probe._probe_request(base_url, "/health", timeout_seconds=1)
    finally:
        server.shutdown()
        server.server_close()

    assert sample == {
        "path": "/health",
        "status": 503,
        "elapsed_ms": sample["elapsed_ms"],
        "body_bytes": len(b"unavailable"),
        "version_consistent": None,
        "error_category": "http_status",
    }


def test_requested_generation_mismatch_is_classified() -> None:
    server, base_url = _serve()
    try:
        sample = probe._probe_request(
            base_url,
            "/ui/home/snapshot",
            timeout_seconds=1,
            requested_generation="system-read-v1",
        )
    finally:
        server.shutdown()
        server.server_close()

    assert sample["status"] == 200
    assert sample["body_bytes"] == 2
    assert sample["version_consistent"] is False
    assert sample["error_category"] == "version_mismatch"


def test_disabled_publication_rejects_non_null_generation() -> None:
    server, base_url = _serve(_DisabledGenerationHandler)
    try:
        sample = probe._probe_request(
            base_url,
            "/api/system-read-publication",
            timeout_seconds=1,
            validate_publication=True,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert sample["status"] == 200
    assert sample["error_category"] == "publication_contract"
