from dataclasses import dataclass


@dataclass
class BuildRunRecord:
    job_name: str
    status: str
