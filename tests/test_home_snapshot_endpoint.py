"""W4.1 tests for /ui/home/snapshot endpoint and home_snapshot_envelope service."""
from __future__ import annotations

import importlib
from unittest.mock import patch

from backend.app.schemas.executive_dashboard import HomeSnapshotPayload
from backend.app.services.executive_service import (
    _compute_unified_report_date,
    _HOME_SNAPSHOT_DOMAINS,
)


def _executive_service():
    """Always use the canonical `sys.modules` entry (golden tests may reload this module)."""
    return importlib.import_module("backend.app.services.executive_service")


class TestComputeUnifiedReportDate:
    def test_strict_intersection_empty_returns_none(self) -> None:
        dates = {"balance": set(), "pnl": set(), "liability": set(), "bond": set()}
        rd, missing, effective = _compute_unified_report_date(
            requested=None, allow_partial=False, domain_dates=dates
        )
        assert rd is None
        assert set(missing) == set(_HOME_SNAPSHOT_DOMAINS)
        assert effective == {}

    def test_strict_intersection_nonempty_picks_max(self) -> None:
        dates = {
            "balance": {"2026-04-08", "2026-04-07"},
            "pnl": {"2026-04-08", "2026-04-07", "2026-04-06"},
            "liability": {"2026-04-08", "2026-04-06"},
            "bond": {"2026-04-08", "2026-04-07"},
        }
        rd, missing, effective = _compute_unified_report_date(
            requested=None, allow_partial=False, domain_dates=dates
        )
        assert rd == "2026-04-08"
        assert missing == []
        assert all(effective[d] == "2026-04-08" for d in _HOME_SNAPSHOT_DOMAINS)

    def test_strict_requested_in_intersection(self) -> None:
        dates = {
            "balance": {"2026-04-08", "2026-04-07"},
            "pnl": {"2026-04-08", "2026-04-07"},
            "liability": {"2026-04-08", "2026-04-07"},
            "bond": {"2026-04-08", "2026-04-07"},
        }
        rd, missing, effective = _compute_unified_report_date(
            requested="2026-04-07", allow_partial=False, domain_dates=dates
        )
        assert rd == "2026-04-07"
        assert missing == []

    def test_strict_requested_not_in_intersection_returns_none(self) -> None:
        dates = {
            "balance": {"2026-04-08"},
            "pnl": {"2026-04-08"},
            "liability": {"2026-04-07"},  # missing 04-08
            "bond": {"2026-04-08"},
        }
        rd, missing, effective = _compute_unified_report_date(
            requested="2026-04-08", allow_partial=False, domain_dates=dates
        )
        assert rd is None
        assert set(missing) == set(_HOME_SNAPSHOT_DOMAINS)

    def test_partial_requested_labels_missing_domains(self) -> None:
        dates = {
            "balance": {"2026-04-08", "2026-04-07"},
            "pnl": {"2026-04-08"},
            "liability": {"2026-04-07"},  # missing 04-08
            "bond": {"2026-04-08", "2026-04-07"},
        }
        rd, missing, effective = _compute_unified_report_date(
            requested="2026-04-08", allow_partial=True, domain_dates=dates
        )
        assert rd == "2026-04-08"
        assert "liability" in missing
        assert effective["balance"] == "2026-04-08"
        assert effective["liability"] == "2026-04-07"  # latest available

    def test_partial_no_requested_uses_union_max(self) -> None:
        dates = {
            "balance": {"2026-04-08"},
            "pnl": {"2026-04-07"},
            "liability": {"2026-04-06"},
            "bond": {"2026-04-05"},
        }
        rd, missing, effective = _compute_unified_report_date(
            requested=None, allow_partial=True, domain_dates=dates
        )
        assert rd == "2026-04-08"
        assert {"pnl", "liability", "bond"} <= set(missing)


class TestHomeSnapshotEnvelope:
    def test_returns_envelope_shape(self) -> None:
        # Run with default env (real duckdb); if repos can't open, it still must
        # return a valid envelope (possibly with empty payload).
        env = _executive_service().home_snapshot_envelope(report_date=None, allow_partial=False)
        assert "result_meta" in env
        assert "result" in env
        # result payload is HomeSnapshotPayload-compatible dict
        result = env["result"]
        assert "report_date" in result
        assert "mode" in result
        assert "source_surface" in result
        assert result["source_surface"] == "executive_analytical"
        assert "overview" in result
        assert "attribution" in result
        assert "domains_missing" in result
        assert "domains_effective_date" in result
        assert env["result_meta"]["result_kind"] == "home.snapshot"

    def test_strict_empty_returns_explicit_miss_envelope(self) -> None:
        es = _executive_service()
        with patch.object(es, "_list_domain_dates") as mock_dates:
            mock_dates.return_value = {
                "balance": set(),
                "pnl": set(),
                "liability": set(),
                "bond": set(),
            }
            env = es.home_snapshot_envelope(report_date=None, allow_partial=False)
            assert env["result_meta"]["quality_flag"] == "error"
            assert env["result_meta"]["vendor_status"] == "vendor_unavailable"
            assert env["result"]["report_date"] == ""
            assert set(env["result"]["domains_missing"]) == set(_HOME_SNAPSHOT_DOMAINS)

    def test_strict_intersection_returns_unified_date(self) -> None:
        es = _executive_service()
        with patch.object(es, "_list_domain_dates") as mock_dates:
            mock_dates.return_value = {
                "balance": {"2026-04-08"},
                "pnl": {"2026-04-08"},
                "liability": {"2026-04-08"},
                "bond": {"2026-04-08"},
            }
            with patch.object(es, "executive_overview") as mock_ov:
                with patch.object(es, "executive_pnl_attribution") as mock_attr:
                    mock_ov.return_value = {
                        "result_meta": {},
                        "result": {"title": "经营总览", "metrics": []},
                    }
                    mock_attr.return_value = {
                        "result_meta": {},
                        "result": {
                            "title": "经营贡献拆解",
                            "total": "+0.00 亿",
                            "segments": [],
                        },
                    }
                    env = es.home_snapshot_envelope(report_date=None, allow_partial=False)
                    assert env["result"]["report_date"] == "2026-04-08"
                    assert env["result"]["mode"] == "strict"
                    assert env["result"]["domains_missing"] == []
                    assert env["result_meta"]["quality_flag"] == "ok"

    def test_partial_mode_labels_missing(self) -> None:
        es = _executive_service()
        with patch.object(es, "_list_domain_dates") as mock_dates:
            mock_dates.return_value = {
                "balance": {"2026-04-08"},
                "pnl": {"2026-04-08"},
                "liability": set(),  # missing entirely
                "bond": {"2026-04-08"},
            }
            with patch.object(es, "executive_overview") as mock_ov:
                with patch.object(es, "executive_pnl_attribution") as mock_attr:
                    mock_ov.return_value = {
                        "result_meta": {},
                        "result": {"title": "经营总览", "metrics": []},
                    }
                    mock_attr.return_value = {
                        "result_meta": {},
                        "result": {
                            "title": "经营贡献拆解",
                            "total": "+0.00 亿",
                            "segments": [],
                        },
                    }
                    env = es.home_snapshot_envelope(
                        report_date="2026-04-08", allow_partial=True
                    )
                    assert env["result"]["mode"] == "partial"
                    assert "liability" in env["result"]["domains_missing"]
                    assert env["result_meta"]["quality_flag"] == "warning"

class TestHomeSnapshotPayloadSchema:
    def test_roundtrip(self) -> None:
        from backend.app.schemas.executive_dashboard import (
            OverviewPayload,
            PnlAttributionPayload,
        )
        from backend.app.schemas.common_numeric import Numeric

        payload = HomeSnapshotPayload(
            report_date="2026-04-08",
            mode="strict",
            source_surface="executive_analytical",
            overview=OverviewPayload(title="经营总览", metrics=[]),
            attribution=PnlAttributionPayload(
                title="经营贡献拆解",
                total=Numeric(
                    raw=0.0,
                    unit="yuan",
                    display="0 亿",
                    precision=0,
                    sign_aware=False,
                ),
                segments=[],
            ),
            domains_missing=[],
            domains_effective_date={
                "balance": "2026-04-08",
                "pnl": "2026-04-08",
                "liability": "2026-04-08",
                "bond": "2026-04-08",
            },
        )
        dumped = payload.model_dump(mode="json")
        restored = HomeSnapshotPayload.model_validate(dumped)
        assert restored.report_date == "2026-04-08"
        assert restored.source_surface == "executive_analytical"
