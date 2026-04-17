import os

from pathlib import Path

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.object_store_repo import ObjectStoreRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.services.ingest_service import IngestService
from backend.app.tasks.broker import register_actor_once


def resolve_data_input_root() -> Path:
    configured_root = os.getenv("MOSS_DATA_INPUT_ROOT")
    if configured_root:
        return Path(configured_root).expanduser()
    return Path(get_settings().data_input_root).expanduser()


def _ingest_demo_manifest(
    *,
    data_root: str | None = None,
    governance_dir: str | None = None,
    archive_dir: str | None = None,
    source_family_allowlist: list[str] | None = None,
) -> dict[str, object]:
    settings = get_settings()
    governance_path = Path(governance_dir or getattr(settings, "governance_path", Path("data/governance")))
    service = IngestService(
        data_root=Path(data_root) if data_root is not None else resolve_data_input_root(),
        manifest_repo=SourceManifestRepository(
            governance_repo=GovernanceRepository(base_dir=governance_path),
        ),
        object_store_repo=ObjectStoreRepository(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            mode=settings.object_store_mode,
            local_archive_path=str(archive_dir or settings.local_archive_path),
        ),
    )
    service.source_family_allowlist = set(
        source_family_allowlist or {"zqtz", "tyw", "pnl", "pnl_514", "pnl_516", "pnl_517"}
    )
    summary = service.run()
    return summary.model_dump(mode="json")


ingest_demo_manifest = register_actor_once(
    "ingest_demo_manifest",
    _ingest_demo_manifest,
    max_retries=3,
    time_limit_ms=300_000,
)
