from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BuildRunRecord:
    job_name: str
    status: str
    cache_key: str = "phase1.native.cache"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
