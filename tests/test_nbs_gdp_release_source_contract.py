from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONFIG = ROOT / "config" / "nbs_gdp_release_source.json"
EVIDENCE_PATH = ROOT / "docs" / "handoff" / "2026-07-17-nbs-gdp-fallback-evidence.md"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "nbs_gdp_release"


def test_nbs_gdp_source_contract_is_automatic_and_lineage_complete() -> None:
    payload = json.loads(SOURCE_CONFIG.read_text(encoding="utf-8"))

    assert payload == {
        "series_id": "nbs.macro.cn_gdp.quarterly",
        "series_name": "China GDP YoY (NBS official release)",
        "listing_url": "https://www.stats.gov.cn/sj/xwfbh/fbhwd/",
        "allowed_hosts": ["stats.gov.cn", "www.stats.gov.cn"],
        "frequency": "quarterly",
        "unit": "pct",
        "rule_version": "rv_nbs_gdp_release_v1",
        "catalog_version": "m2b.nbs_gdp_release.v1",
        "max_document_bytes": 2_000_000,
    }
    text = SOURCE_CONFIG.read_text(encoding="utf-8")
    assert "4.3" not in text
    assert "t20260715" not in text


def test_nbs_gdp_fixtures_are_small_synthetic_documents() -> None:
    listing = (FIXTURE_ROOT / "listing.html").read_text(encoding="utf-8")
    release = (FIXTURE_ROOT / "2026_h1_release.html").read_text(encoding="utf-8")

    assert len(listing.encode()) < 10_000
    assert len(release.encode()) < 10_000
    assert "2026年上半年国民经济运行情况" in listing
    assert "分季度看" in release
    assert "一季度增长5.0%" in release
    assert "二季度增长4.3%" in release


def test_nbs_gdp_evidence_records_diagnostic_and_required_lineage_fields() -> None:
    evidence = EVIDENCE_PATH.read_text(encoding="utf-8")

    for required in (
        "2026-07-17",
        "2026Q1 = 5.0",
        "https://www.stats.gov.cn/sj/xwfbh/fbhwd/202607/t20260715_1964121.html",
        "2026Q2 = 4.3",
        "release_url",
        "content_sha256",
        "rule_version",
        "batch_id",
        "report_period",
        "待实施",
        "待实数核对",
    ):
        assert required in evidence
