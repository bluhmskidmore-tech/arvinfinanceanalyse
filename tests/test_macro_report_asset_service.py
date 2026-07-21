from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.app.services import macro_report_asset_service


def _write_bundle(
    bundle_dir: Path,
    *,
    content: bytes = b"macro report",
    filename: str = "report.pdf",
    artifact_id: str = "full-report",
    formal_use_allowed: bool = False,
    observation_only: bool = True,
    sha256: str | None = None,
    size_bytes: int | None = None,
) -> None:
    bundle_dir.mkdir(parents=True)
    artifact_path = bundle_dir / filename
    if Path(filename).name == filename:
        artifact_path.write_bytes(content)
    manifest = {
        "schema_version": "macro-report-bundle-v1",
        "bundle_id": "china-macro-rates-2026-07-20",
        "title": "2026 中国宏观与利率策略",
        "basis": "analytical",
        "as_of_date": "2026-07-20",
        "curve_date": "2026-07-17",
        "account_report_date": "2026-06-30",
        "observation_only": observation_only,
        "formal_use_allowed": formal_use_allowed,
        "validation": {
            "passed": 93,
            "failed": 0,
            "scope": "交付物一致性校验，不构成外部市场真值复核",
        },
        "warnings": ["研究材料，只读观察，不构成正式指标或交易信号。"],
        "artifacts": [
            {
                "id": artifact_id,
                "filename": filename,
                "label": "完整报告",
                "kind": "report",
                "media_type": "application/pdf",
                "size_bytes": len(content) if size_bytes is None else size_bytes,
                "sha256": hashlib.sha256(content).hexdigest() if sha256 is None else sha256,
            }
        ],
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )


def test_report_bundle_is_missing_without_manifest(tmp_path: Path) -> None:
    payload = macro_report_asset_service.load_report_bundle(tmp_path / "missing")

    assert payload == {
        "status": "missing",
        "reason": "manifest_missing",
        "basis": "analytical",
        "observation_only": True,
        "formal_use_allowed": False,
        "artifacts": [],
        "warnings": ["宏观报告资产包尚未发布。"],
    }


@pytest.mark.parametrize(
    ("formal_use_allowed", "observation_only", "filename", "reason"),
    [
        (True, True, "report.pdf", "formal_use_not_allowed"),
        (False, False, "report.pdf", "observation_only_required"),
        (False, True, "../report.pdf", "invalid_artifact_filename"),
    ],
)
def test_report_bundle_fails_closed_on_policy_and_path_violations(
    tmp_path: Path,
    formal_use_allowed: bool,
    observation_only: bool,
    filename: str,
    reason: str,
) -> None:
    bundle_dir = tmp_path / "bundle"
    _write_bundle(
        bundle_dir,
        formal_use_allowed=formal_use_allowed,
        observation_only=observation_only,
        filename=filename,
    )

    payload = macro_report_asset_service.load_report_bundle(bundle_dir)

    assert payload["status"] == "invalid"
    assert payload["reason"] == reason
    assert payload["formal_use_allowed"] is False
    assert payload["observation_only"] is True
    assert payload["artifacts"] == []


def test_report_bundle_rejects_integrity_mismatch(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    _write_bundle(bundle_dir, sha256="0" * 64)

    payload = macro_report_asset_service.load_report_bundle(bundle_dir)

    assert payload["status"] == "invalid"
    assert payload["reason"] == "artifact_hash_mismatch"
    with pytest.raises(macro_report_asset_service.ReportBundleInvalidError):
        macro_report_asset_service.read_report_artifact(bundle_dir, "full-report")


def test_report_bundle_exposes_sanitized_metadata_and_verified_bytes(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    content = b"verified report bytes"
    _write_bundle(bundle_dir, content=content)

    payload = macro_report_asset_service.load_report_bundle(bundle_dir)
    artifact = macro_report_asset_service.read_report_artifact(bundle_dir, "full-report")

    assert payload["status"] == "ready"
    assert payload["formal_use_allowed"] is False
    assert payload["observation_only"] is True
    assert payload["validation"]["passed"] == 93
    assert payload["validation"]["failed"] == 0
    assert payload["artifacts"] == [
        {
            "id": "full-report",
            "filename": "report.pdf",
            "label": "完整报告",
            "kind": "report",
            "media_type": "application/pdf",
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    ]
    assert "path" not in payload["artifacts"][0]
    assert artifact.filename == "report.pdf"
    assert artifact.media_type == "application/pdf"
    assert artifact.content == content


def test_report_bundle_rejects_symlinked_artifact_when_supported(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"outside")
    bundle_dir.mkdir()
    link = bundle_dir / "report.pdf"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable on this Windows host")
    manifest = {
        "schema_version": "macro-report-bundle-v1",
        "bundle_id": "china-macro-rates-2026-07-20",
        "title": "2026 中国宏观与利率策略",
        "basis": "analytical",
        "as_of_date": "2026-07-20",
        "curve_date": "2026-07-17",
        "account_report_date": "2026-06-30",
        "observation_only": True,
        "formal_use_allowed": False,
        "validation": {"passed": 93, "failed": 0, "scope": "delivery consistency"},
        "warnings": [],
        "artifacts": [
            {
                "id": "full-report",
                "filename": "report.pdf",
                "label": "完整报告",
                "kind": "report",
                "media_type": "application/pdf",
                "size_bytes": len(b"outside"),
                "sha256": hashlib.sha256(b"outside").hexdigest(),
            }
        ],
    }
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    payload = macro_report_asset_service.load_report_bundle(bundle_dir)

    assert payload["status"] == "invalid"
    assert payload["reason"] == "artifact_symlink_not_allowed"
