from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class BuildRunRecord:
    job_name: str
    status: str
    cache_key: str = "phase1.native.cache"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
