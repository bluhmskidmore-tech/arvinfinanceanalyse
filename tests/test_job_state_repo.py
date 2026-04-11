from __future__ import annotations

from pathlib import Path


from tests.helpers import load_module


def _repo(tmp_path):
    repo_module = load_module(
        "backend.app.repositories.job_state_repo",
        "backend/app/repositories/job_state_repo.py",
    )
    dsn = f"sqlite:///{(tmp_path / 'job-state.db').as_posix()}"
    return repo_module, repo_module.JobStateRepository(dsn)


def test_job_state_repo_records_and_reads_latest_lifecycle(tmp_path):
    repo_module, repo = _repo(tmp_path)

    repo.record_transition(
        run_id="run-1",
        job_name="source_preview_refresh",
        cache_key="source_preview.foundation",
        status="queued",
        report_date=None,
        source_version="sv_pending",
        vendor_version="vv_none",
        queued_at="2026-04-11T10:00:00+00:00",
    )
    repo.record_transition(
        run_id="run-1",
        job_name="source_preview_refresh",
        cache_key="source_preview.foundation",
        status="running",
        report_date=None,
        source_version="sv_running",
        vendor_version="vv_none",
        started_at="2026-04-11T10:00:05+00:00",
    )
    repo.record_transition(
        run_id="run-1",
        job_name="source_preview_refresh",
        cache_key="source_preview.foundation",
        status="completed",
        report_date=None,
        source_version="sv_done",
        vendor_version="vv_none",
        finished_at="2026-04-11T10:00:10+00:00",
    )

    latest = repo.get_latest_run("run-1")

    assert latest is not None
    assert latest["run_id"] == "run-1"
    assert latest["status"] == "completed"
    assert latest["source_version"] == "sv_done"
    assert latest["queued_at"] == "2026-04-11T10:00:00+00:00"
    assert latest["started_at"] == "2026-04-11T10:00:05+00:00"
    assert latest["finished_at"] == "2026-04-11T10:00:10+00:00"


def test_job_state_repo_reports_latest_inflight_by_workload_key(tmp_path):
    _repo_module, repo = _repo(tmp_path)

    repo.record_transition(
        run_id="run-old",
        job_name="balance_analysis_materialize",
        cache_key="balance_analysis:materialize:formal",
        status="queued",
        report_date="2025-12-31",
        source_version="sv_old",
        vendor_version="vv_none",
        queued_at="2026-04-11T10:00:00+00:00",
    )
    repo.record_transition(
        run_id="run-old",
        job_name="balance_analysis_materialize",
        cache_key="balance_analysis:materialize:formal",
        status="failed",
        report_date="2025-12-31",
        source_version="sv_old",
        vendor_version="vv_none",
        finished_at="2026-04-11T10:01:00+00:00",
    )
    repo.record_transition(
        run_id="run-live",
        job_name="balance_analysis_materialize",
        cache_key="balance_analysis:materialize:formal",
        status="running",
        report_date="2025-12-31",
        source_version="sv_live",
        vendor_version="vv_none",
        started_at="2026-04-11T10:02:00+00:00",
    )
    repo.record_transition(
        run_id="run-other",
        job_name="balance_analysis_materialize",
        cache_key="balance_analysis:materialize:formal",
        status="queued",
        report_date="2026-01-31",
        source_version="sv_other",
        vendor_version="vv_none",
        queued_at="2026-04-11T10:03:00+00:00",
    )

    latest = repo.find_latest_inflight(
        job_name="balance_analysis_materialize",
        cache_key="balance_analysis:materialize:formal",
        report_date="2025-12-31",
    )

    assert latest is not None
    assert latest["run_id"] == "run-live"
    assert latest["status"] == "running"


def test_job_state_repo_can_mark_failed_with_error_message(tmp_path):
    _repo_module, repo = _repo(tmp_path)

    repo.record_transition(
        run_id="run-failed",
        job_name="pnl_materialize",
        cache_key="pnl:phase2:materialize:formal",
        status="failed",
        report_date="2026-02-28",
        source_version="sv_failed",
        vendor_version="vv_none",
        error_message="broker timeout",
        finished_at="2026-04-11T10:05:00+00:00",
    )

    latest = repo.get_latest_run("run-failed")

    assert latest is not None
    assert latest["status"] == "failed"
    assert latest["error_message"] == "broker timeout"
    assert latest["finished_at"] == "2026-04-11T10:05:00+00:00"
