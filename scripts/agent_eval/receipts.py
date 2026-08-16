"""Call-receipt log writer for MOSS agent evaluation.

A receipt log is an append-only jsonl file written by the *trusted harness
middle layer* that proxies MCP calls (for example the receipt hook in
`scripts/mcp/moss_project_mcp.py`, enabled via `MOSS_MCP_RECEIPT_LOG`).
The agent under evaluation must never hold write access to this file:
`collect.py` cross-checks evidence artifacts against it, so an agent-writable
log degrades the receipt check back to self-report.

Each line records one call: `server`, `tool`, `params_digest`,
`response_sha256`, and a UTC timestamp. `response_sha256` is the sha256 of the
exact response bytes handed to `append_receipt`; callers that hash a JSON
response object should serialize it with `canonical_json_bytes` so the
artifact writer can recompute the same digest from the response it received.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_receipt(
    log_path: str | Path,
    server: str,
    tool: str,
    params_digest: str,
    response_bytes: bytes,
) -> None:
    """Append one call receipt to `log_path`, creating parent dirs as needed."""

    record = {
        "server": server,
        "tool": tool,
        "params_digest": params_digest,
        "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize a JSON-compatible payload to the canonical bytes both the
    receipt writer and the artifact writer hash (sorted keys, compact
    separators, UTF-8, non-ASCII preserved)."""

    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def digest_params(params: Any) -> str:
    """Digest call parameters for the receipt's `params_digest` field."""

    return hashlib.sha256(canonical_json_bytes(params)).hexdigest()
