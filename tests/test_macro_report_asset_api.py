from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.api.routes.macro_toolkit import router as macro_toolkit_router
from backend.app.services import macro_report_asset_service


def _write_bundle(bundle_dir: Path, *, content: bytes = b"downloadable report") -> None:
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "report.pdf").write_bytes(content)
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
        "validation": {
            "passed": 93,
            "failed": 0,
            "scope": "交付物一致性校验，不构成外部市场真值复核",
        },
        "warnings": ["研究材料，只读观察，不构成正式指标或交易信号。"],
        "artifacts": [
            {
                "id": "full-report",
                "filename": "report.pdf",
                "label": "完整报告",
                "kind": "report",
                "media_type": "application/pdf",
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ],
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )


def test_macro_report_bundle_download_serves_only_verified_manifest_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "output"
    content = b"downloadable report"
    _write_bundle(output_dir / macro_report_asset_service.BUNDLE_DIRNAME, content=content)
    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", output_dir)
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    response = client.get("/ui/macro/toolkit/report-bundle/full-report")
    unknown = client.get("/ui/macro/toolkit/report-bundle/not-in-manifest")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"].startswith("application/pdf")
    assert "report.pdf" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert unknown.status_code == 404


def test_macro_report_bundle_download_checks_read_permission_before_file_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "output"
    _write_bundle(output_dir / macro_report_asset_service.BUNDLE_DIRNAME)
    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", output_dir)

    def deny_read(*_args: object, **_kwargs: object) -> None:
        raise HTTPException(status_code=403, detail="macro_toolkit read denied")

    monkeypatch.setattr(macro_toolkit_route, "_ensure_macro_toolkit_read_allowed", deny_read)
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    response = client.get("/ui/macro/toolkit/report-bundle/full-report")

    assert response.status_code == 403
    assert response.json()["detail"] == "macro_toolkit read denied"
