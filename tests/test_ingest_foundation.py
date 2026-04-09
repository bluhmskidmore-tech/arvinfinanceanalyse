import pytest

from tests.helpers import ROOT, load_module


def test_ingest_service_scans_data_input_and_returns_manifest_rows():
    module = load_module("backend.app.services.ingest_service", "backend/app/services/ingest_service.py")
    ingest_service = getattr(module, "IngestService", None)
    if ingest_service is None:
        pytest.fail("backend.app.services.ingest_service must define IngestService")

    service = ingest_service(data_root=ROOT / "data_input")
    rows = service.scan()
    assert rows, "Expected scan() to discover at least one source file under data_input"
    first = rows[0]
    assert {"source_name", "file_name", "file_path", "file_size"} <= set(first)
