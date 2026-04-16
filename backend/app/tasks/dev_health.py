from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from backend.app.tasks.broker import register_actor_once


def _write_dev_worker_heartbeat(*, heartbeat_path: str, token: str) -> dict[str, object]:
    target = Path(heartbeat_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "token": token,
        "pid": os.getpid(),
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


write_dev_worker_heartbeat = register_actor_once(
    "write_dev_worker_heartbeat",
    _write_dev_worker_heartbeat,
)
