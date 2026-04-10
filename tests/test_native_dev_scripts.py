from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_native_development_scripts_exist():
    expected = [
        ROOT / "scripts" / "dev-api.ps1",
        ROOT / "scripts" / "dev-worker.ps1",
        ROOT / "scripts" / "dev-env.ps1",
    ]

    missing = [str(path) for path in expected if not path.exists()]
    assert not missing, "Missing native development scripts:\n" + "\n".join(missing)
