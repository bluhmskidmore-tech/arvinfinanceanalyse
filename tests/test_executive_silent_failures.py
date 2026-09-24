"""A3-1 / B11 回归：executive_service 历史静默失败点位必须 fail-visible。

覆盖四个点位：
1. `_read_recent_cache_build_runs_for_executive_overview` 坏行 `continue`
   （原先无计数无告警）→ 计数 + 首例记录 + 每来源去重 warning；
2. `_fetch_product_category_home_headline_values` 异常时静默 `return {}`
   → 形状兼容的显式 degraded 标记 + warning 日志；
3. `_build_product_category_ytd_headline` 兜底解析异常时静默 `return None`
   → 显式 `_DegradedProductCategoryHeadline` 标记，且原因透出到
   home snapshot envelope 的 `filters_applied.degraded_reasons`；
4. `_build_product_category_monthly_headline` 兜底解析异常时静默 `return None`
   → 与 ytd 同款 warning 日志 + degraded 标记 + degraded_reasons 透出。
"""
from __future__ import annotations

import importlib
import json
import logging

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_executive,
]

_LOGGER_NAME = "backend.app.services.executive_service"


def _executive_service():
    """与既有 home snapshot 测试一致：始终取 `sys.modules` 中的规范条目。"""
    return importlib.import_module("backend.app.services.executive_service")


@pytest.fixture(autouse=True)
def _fresh_home_snapshot_cache():
    _executive_service().invalidate_home_snapshot_cache()
    yield
    _executive_service().invalidate_home_snapshot_cache()


class TestCacheBuildRunBadRowsVisible:
    def _write_stream(self, directory, lines: list[str]):
        es = _executive_service()
        target = directory / f"{es.CACHE_BUILD_RUN_STREAM}.jsonl"
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target

    def test_bad_rows_counted_with_first_example_and_warning(self, tmp_path, caplog) -> None:
        es = _executive_service()
        good_row = {"cache_key": "k1", "job_name": "job", "status": "completed"}
        target = self._write_stream(
            tmp_path,
            [json.dumps(good_row), "{broken-json", json.dumps([1, 2, 3]), json.dumps(good_row)],
        )

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            rows = es._read_recent_cache_build_runs_for_executive_overview(str(tmp_path))

        assert rows is not None
        assert list(rows) == [good_row, good_row]
        assert rows.bad_row_count == 2
        assert rows.first_bad_row_preview == "{broken-json"
        warning_messages = [
            record.getMessage()
            for record in caplog.records
            if record.levelno == logging.WARNING and "malformed" in record.getMessage()
        ]
        assert len(warning_messages) == 1
        assert "2 malformed row(s)" in warning_messages[0]
        assert str(target) in warning_messages[0]
        assert "{broken-json" in warning_messages[0]

    def test_clean_stream_reports_zero_bad_rows(self, tmp_path, caplog) -> None:
        es = _executive_service()
        good_row = {"cache_key": "k1", "job_name": "job", "status": "completed"}
        self._write_stream(tmp_path, [json.dumps(good_row)])

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            rows = es._read_recent_cache_build_runs_for_executive_overview(str(tmp_path))

        assert rows is not None
        assert rows.bad_row_count == 0
        assert rows.first_bad_row_preview is None
        assert not [r for r in caplog.records if "malformed" in r.getMessage()]

    def test_bad_row_warning_deduplicated_per_source(self, tmp_path, caplog) -> None:
        es = _executive_service()
        first_dir = tmp_path / "gov-a"
        second_dir = tmp_path / "gov-b"
        first_dir.mkdir()
        second_dir.mkdir()
        self._write_stream(first_dir, ["{broken-json"])
        self._write_stream(second_dir, ["{other-broken"])

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            es._read_recent_cache_build_runs_for_executive_overview(str(first_dir))
            repeat_rows = es._read_recent_cache_build_runs_for_executive_overview(str(first_dir))
            es._read_recent_cache_build_runs_for_executive_overview(str(second_dir))

        # 计数每次读取仍然透出，仅告警按来源去重。
        assert repeat_rows is not None
        assert repeat_rows.bad_row_count == 1
        warning_messages = [
            r.getMessage() for r in caplog.records if "malformed" in r.getMessage()
        ]
        assert len(warning_messages) == 2
        assert any("gov-a" in message for message in warning_messages)
        assert any("gov-b" in message for message in warning_messages)


class TestProductCategoryHeadlineFastPathDegraded:
    def test_exception_returns_marked_empty_dict_not_silent(
        self, monkeypatch: pytest.MonkeyPatch, caplog
    ) -> None:
        es = _executive_service()

        class _ExplodingRepo:
            def __init__(self, _duck_path: str) -> None:
                pass

            def fetch_home_headline_values(self, **_kwargs):
                raise RuntimeError("duckdb unavailable for headline")

        monkeypatch.setattr(es, "ProductCategoryPnlRepository", _ExplodingRepo)

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            values = es._fetch_product_category_home_headline_values(
                "duck.db", "2026-04-08", ["ytd", "monthly"]
            )

        # 形状兼容：消费端 `.get(view, {})` 行为不变。
        assert values == {}
        assert values.degraded is True
        assert "RuntimeError" in values.degraded_reason
        assert "duckdb unavailable for headline" in values.degraded_reason
        assert any(
            "duckdb unavailable for headline" in record.getMessage()
            for record in caplog.records
        )

    def test_success_path_is_not_marked_degraded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        es = _executive_service()

        class _OkRepo:
            def __init__(self, _duck_path: str) -> None:
                pass

            def fetch_home_headline_values(self, **_kwargs):
                return {"ytd": {"grand_total": 1.0}}

        monkeypatch.setattr(es, "ProductCategoryPnlRepository", _OkRepo)
        values = es._fetch_product_category_home_headline_values("duck.db", "2026-04-08", ["ytd"])
        assert values == {"ytd": {"grand_total": 1.0}}
        assert getattr(values, "degraded", False) is False


class TestProductCategoryYtdHeadlineDegraded:
    def test_resolver_exception_returns_explicit_degraded_marker(
        self, monkeypatch: pytest.MonkeyPatch, caplog
    ) -> None:
        es = _executive_service()
        monkeypatch.setattr(
            es, "_fetch_product_category_home_headline_values", lambda *_a, **_k: {}
        )

        def exploding_resolver(*_args, **_kwargs):
            raise RuntimeError("ytd fallback resolver failed")

        monkeypatch.setattr(
            es, "resolve_product_category_ytd_payload_for_home_snapshot", exploding_resolver
        )

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            headline = es._build_product_category_ytd_headline("2026-04-08")

        assert isinstance(headline, es._DegradedProductCategoryHeadline)
        assert headline.degraded is True
        assert headline.component == "product_category_ytd"
        assert "RuntimeError" in headline.reason
        assert "ytd fallback resolver failed" in headline.reason
        assert any(
            "ytd fallback resolver failed" in record.getMessage()
            for record in caplog.records
        )


class TestProductCategoryMonthlyHeadlineDegraded:
    def test_fallback_exception_returns_explicit_degraded_marker(
        self, monkeypatch: pytest.MonkeyPatch, caplog
    ) -> None:
        es = _executive_service()
        monkeypatch.setattr(
            es, "_fetch_product_category_home_headline_values", lambda *_a, **_k: {}
        )

        def exploding_envelope(*_args, **_kwargs):
            raise RuntimeError("monthly fallback envelope failed")

        monkeypatch.setattr(es, "product_category_pnl_envelope", exploding_envelope)

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            headline = es._build_product_category_monthly_headline("2026-04-08")

        assert isinstance(headline, es._DegradedProductCategoryHeadline)
        assert headline.degraded is True
        assert headline.component == "product_category_monthly"
        assert "RuntimeError" in headline.reason
        assert "monthly fallback envelope failed" in headline.reason
        assert any(
            "monthly fallback envelope failed" in record.getMessage()
            for record in caplog.records
        )


def _patch_home_snapshot_context(es, monkeypatch: pytest.MonkeyPatch) -> None:
    dates = ["2026-04-08"]
    monkeypatch.setattr(
        es,
        "_list_domain_date_context",
        lambda: {"balance": dates, "pnl": dates, "liability": dates, "bond": dates},
    )
    monkeypatch.setattr(
        es,
        "executive_overview",
        lambda **_kwargs: {"result_meta": {}, "result": {"title": "overview", "metrics": []}},
    )
    monkeypatch.setattr(
        es,
        "executive_pnl_attribution",
        lambda report_date=None: {
            "result_meta": {},
            "result": {"title": "attribution", "total": "0", "segments": []},
        },
    )


class TestHomeSnapshotDegradedReasonVisible:
    def test_snapshot_filters_expose_degraded_reason(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        es = _executive_service()
        _patch_home_snapshot_context(es, monkeypatch)
        marker = es._DegradedProductCategoryHeadline(
            "product_category_ytd", "RuntimeError: ytd fallback resolver failed"
        )
        monkeypatch.setattr(
            es,
            "_build_product_category_headlines",
            lambda _report_date: (marker, None, 0, 0),
        )

        env = es.home_snapshot_envelope(report_date=None, allow_partial=False)

        # 标记不泄漏进 payload：归一化回 None，缺数依旧显式。
        assert env["result"]["product_category_ytd"] is None
        filters = env["result_meta"]["filters_applied"]
        assert "product_category_ytd" in filters["degraded_components"]
        assert filters["degraded_reasons"] == {
            "product_category_ytd": "RuntimeError: ytd fallback resolver failed"
        }
        assert env["result_meta"]["quality_flag"] == "warning"

    def test_snapshot_filters_expose_monthly_degraded_reason(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        es = _executive_service()
        _patch_home_snapshot_context(es, monkeypatch)
        marker = es._DegradedProductCategoryHeadline(
            "product_category_monthly", "RuntimeError: monthly fallback envelope failed"
        )
        monkeypatch.setattr(
            es,
            "_build_product_category_headlines",
            lambda _report_date: (None, marker, 0, 0),
        )

        env = es.home_snapshot_envelope(report_date=None, allow_partial=False)

        assert env["result"]["product_category_monthly"] is None
        filters = env["result_meta"]["filters_applied"]
        assert "product_category_monthly" in filters["degraded_components"]
        assert filters["degraded_reasons"] == {
            "product_category_monthly": "RuntimeError: monthly fallback envelope failed"
        }
        assert env["result_meta"]["quality_flag"] == "warning"
