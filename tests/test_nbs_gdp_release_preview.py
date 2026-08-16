from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from backend.app.repositories.nbs_gdp_release_adapter import NbsGdpReleaseDocument
from scripts.nbs_gdp_release_preview import preview_nbs_gdp_release


def test_preview_reports_official_receipt_without_write_dependencies(tmp_path: Path) -> None:
    html = b"<html>official release</html>"
    config_path = tmp_path / "nbs.json"
    config_path.write_text(
        json.dumps(
            {
                "series_id": "nbs.macro.cn_gdp.quarterly",
                "rule_version": "rv_nbs_gdp_release_v1",
            }
        ),
        encoding="utf-8",
    )

    class AdapterStub:
        def discover_and_fetch(self, *, reference_date: date):
            assert reference_date == date(2026, 7, 17)
            return NbsGdpReleaseDocument(
                release_url="https://www.stats.gov.cn/release.html",
                fetched_at=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
                html_bytes=html,
                observations=[
                    {
                        "trade_date": "2026-06-30",
                        "value": 4.3,
                        "source_version": "nbs_gdp_release_sha256_test",
                    }
                ],
            )

    result = preview_nbs_gdp_release(
        reference_date=date(2026, 7, 17),
        adapter=AdapterStub(),
        config_path=config_path,
    )

    assert result == {
        "status": "success",
        "reference_date": "2026-07-17",
        "release_url": "https://www.stats.gov.cn/release.html",
        "fetched_at": "2026-07-17T12:00:00+00:00",
        "content_sha256": hashlib.sha256(html).hexdigest(),
        "series_id": "nbs.macro.cn_gdp.quarterly",
        "rule_version": "rv_nbs_gdp_release_v1",
        "observations": [{"report_period": "2026-06-30", "value": 4.3}],
        "writes_performed": False,
    }

    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "nbs_gdp_release_preview.py"
    ).read_text(encoding="utf-8")
    assert "duckdb" not in script.lower()
    assert "RawZoneRepository" not in script
    assert "before_parse" not in script


def test_preview_script_runs_directly_from_repository_root() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "nbs_gdp_release_preview.py").read_text(encoding="utf-8")
    assert "sys.path.insert(0, str(ROOT))" in script
    assert script.index("sys.path.insert") < script.index("from backend.app")
