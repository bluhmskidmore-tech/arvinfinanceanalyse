from __future__ import annotations

import base64
import binascii

from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.services.ledger_import_service import MAX_LEDGER_IMPORT_BYTES, LedgerImportService
from backend.app.tasks.broker import register_actor_once

MAX_LEDGER_IMPORT_BASE64_CHARS = 4 * ((MAX_LEDGER_IMPORT_BYTES + 2) // 3)


def _run_ledger_import(
    *,
    file_name: str,
    content_base64: str,
    duckdb_path: str,
    run_id: str,
) -> dict[str, object]:
    with repository_task_write_scope(__name__):
        if len(content_base64) > MAX_LEDGER_IMPORT_BASE64_CHARS:
            raise ValueError("Ledger import payload is too large.")
        try:
            content = base64.b64decode(content_base64.encode("ascii"), validate=True)
        except (binascii.Error, UnicodeEncodeError) as exc:
            raise ValueError("Ledger import content must be valid base64 ASCII.") from exc
        if len(content) > MAX_LEDGER_IMPORT_BYTES:
            raise ValueError("Ledger import payload is too large.")
        payload = LedgerImportService(duckdb_path).import_file(
            file_name=file_name,
            content=content,
        )
        payload["data"]["run_id"] = run_id
        payload["trace"]["run_id"] = run_id
        return payload


run_ledger_import = register_actor_once("run_ledger_import", _run_ledger_import)
