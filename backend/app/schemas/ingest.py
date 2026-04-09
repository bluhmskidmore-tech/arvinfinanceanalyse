from pathlib import Path

from pydantic import BaseModel


class IngestManifestRow(BaseModel):
    source_name: str
    file_name: str
    file_path: Path
    file_size: int
