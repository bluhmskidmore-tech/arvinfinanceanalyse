from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_native_smoke_script_exists_and_references_native_chain():
    script_path = ROOT / "scripts" / "dev-smoke.ps1"
    assert script_path.exists(), f"Missing smoke script: {script_path}"

    text = script_path.read_text(encoding="utf-8")
    assert "dev-env.ps1" in text
    assert "/health" in text
    assert "ingest_demo_manifest" in text
    assert "materialize_cache_view" in text
