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
    return Path(__file__).resolve().parents[3] / "data_input"


def _ingest_demo_manifest() -> dict[str, object]:
    settings = get_settings()
    governance_path = getattr(settings, "governance_path", Path("data/governance"))
    service = IngestService(
        data_root=resolve_data_input_root(),
        manifest_repo=SourceManifestRepository(
            governance_repo=GovernanceRepository(base_dir=governance_path),
        ),
        object_store_repo=ObjectStoreRepository(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            mode=settings.object_store_mode,
            local_archive_path=str(settings.local_archive_path),
        ),
    )
    service.source_family_allowlist = {"zqtz", "tyw", "pnl", "pnl_514", "pnl_516", "pnl_517"}
    summary = service.run()
    return summary.model_dump(mode="json")


ingest_demo_manifest = register_actor_once("ingest_demo_manifest", _ingest_demo_manifest)
