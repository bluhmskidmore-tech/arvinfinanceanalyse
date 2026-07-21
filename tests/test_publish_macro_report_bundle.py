from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.app.services import macro_report_asset_service

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publish_macro_toolkit_report_bundle.py"

PUBLIC_ASSETS = {
    "report.pdf": b"full report",
    "onepager.pdf": b"one page pdf",
    "onepager.png": b"one page png",
    "speaker_notes.md": "speaker notes".encode(),
    "redteam_findings.md": "red-team findings".encode(),
    "README.md": "read me".encode(),
}


def _write_source(source_dir: Path, *, omit: str | None = None) -> None:
    source_dir.mkdir()
    for filename, content in PUBLIC_ASSETS.items():
        if filename != omit:
            (source_dir / filename).write_bytes(content)
    (source_dir / "internal_data.json").write_text('{"private": true}', encoding="utf-8")
    (source_dir / "portfolio_source.xlsx").write_bytes(b"private workbook")


def _run_publish(
    source_dir: Path,
    output_dir: Path,
    *,
    extra_args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-dir",
            str(source_dir),
            "--output-dir",
            str(output_dir),
            "--as-of-date",
            "2026-07-20",
            "--curve-date",
            "2026-07-17",
            "--account-report-date",
            "2026-06-30",
            "--validation-passed",
            "93",
            "--validation-failed",
            "0",
            *extra_args,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_publish_macro_report_bundle_copies_only_allowlisted_verified_assets(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "bundle"
    _write_source(source_dir)

    completed = _run_publish(source_dir, output_dir)

    assert completed.returncode == 0, completed.stderr
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["formal_use_allowed"] is False
    assert manifest["observation_only"] is True
    assert manifest["basis"] == "analytical"
    assert manifest["validation"]["passed"] == 93
    assert manifest["validation"]["failed"] == 0
    assert {item["id"] for item in manifest["artifacts"]} == {
        "full-report",
        "one-page-pdf",
        "one-page-preview",
        "speaker-notes",
        "red-team-findings",
        "readme",
    }
    assert {path.name for path in output_dir.iterdir()} == {*PUBLIC_ASSETS, "manifest.json"}
    assert not (output_dir / "internal_data.json").exists()
    assert not (output_dir / "portfolio_source.xlsx").exists()
    assert macro_report_asset_service.load_report_bundle(output_dir)["status"] == "ready"


def test_publish_macro_report_bundle_fails_before_writing_when_required_asset_is_missing(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "bundle"
    _write_source(source_dir, omit="redteam_findings.md")

    completed = _run_publish(source_dir, output_dir)

    assert completed.returncode != 0
    assert "redteam_findings.md" in completed.stderr
    assert not (output_dir / "manifest.json").exists()


def test_publish_macro_report_bundle_rejects_blank_title_before_writing(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "bundle"
    _write_source(source_dir)

    completed = _run_publish(source_dir, output_dir, extra_args=("--title", "   "))

    assert completed.returncode != 0
    assert "title must not be blank" in completed.stderr
    assert not (output_dir / "manifest.json").exists()
