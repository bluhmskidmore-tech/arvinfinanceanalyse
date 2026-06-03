from __future__ import annotations

from tests.helpers import ROOT, load_module


RUNBOOK_PATH = ROOT / "docs" / "tushare_news_backup_refresh_runbook.md"
SCHEDULER_HANDOFF_PATH = ROOT / "docs" / "templates" / "tushare_news_backup_refresh_scheduler_handoff.md"
GO_LIVE_CHECKLIST_PATH = ROOT / "docs" / "templates" / "tushare_news_backup_refresh_go_live_checklist.md"
TIMER_ENABLEMENT_PACKET_PATH = (
    ROOT / "docs" / "templates" / "tushare_news_backup_timer_enablement_packet.md"
)
HANDOFF_PATH = ROOT / "docs" / "handoff" / "2026-06-03-tushare-news-backup-refresh-handoff.md"
GO_LIVE_EVIDENCE_PATH = (
    ROOT / "docs" / "handoff" / "2026-06-03-tushare-news-backup-refresh-go-live-evidence.md"
)
TIMER_PREFLIGHT_STATUS_PATH = (
    ROOT / "docs" / "handoff" / "2026-06-03-tushare-news-backup-timer-preflight-status.md"
)
TIMER_OPS_GAP_PACKET_PATH = (
    ROOT / "docs" / "handoff" / "2026-06-03-tushare-news-backup-timer-ops-gap-packet.md"
)


def _load_preflight_module():
    return load_module(
        "scripts.tushare_news_backup_timer_preflight",
        "scripts/tushare_news_backup_timer_preflight.py",
    )


def test_tushare_news_backup_refresh_runbook_documents_operator_contract() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert "scripts/refresh_tushare_news_backup.py" in runbook
    assert "--dry-run" in runbook
    assert "--enqueue" in runbook
    assert "MOSS_TUSHARE_TOKEN" in runbook
    assert "ingest_tushare_news_to_choice_news" in runbook
    assert "current_backup_state.status" in runbook
    assert "latest_received_at" in runbook
    assert "error_rows" in runbook
    assert "blank_payload_rows" in runbook
    assert "tushare.major_news" in runbook
    assert "tushare.news.sina" in runbook
    assert "tushare.npr" in runbook
    assert "/ui/news/tushare-npr/ingest" in runbook
    assert "/api/news/tushare-npr/ingest" in runbook
    assert "reserved" in runbook.lower()
    assert "docs/templates/tushare_news_backup_refresh_scheduler_handoff.md" in runbook
    assert "docs/templates/tushare_news_backup_refresh_go_live_checklist.md" in runbook
    assert "docs/templates/tushare_news_backup_timer_enablement_packet.md" in runbook
    assert "docs/handoff/2026-06-03-tushare-news-backup-timer-preflight-status.md" in runbook
    assert "docs/handoff/2026-06-03-tushare-news-backup-timer-ops-gap-packet.md" in runbook
    assert "scripts/tushare_news_backup_timer_preflight.py" in runbook
    assert "--stage all" in runbook
    assert "--format markdown" in runbook
    assert "--format ops-gap" in runbook
    assert "--stage pre-enable" in runbook
    assert "--stage post-enable" in runbook
    assert "timer enablement packet is filled" in runbook
    assert "actual install commands" in runbook
    assert "browser evidence JSON confirms" in runbook
    assert "Go-live evidence must no longer say `not enabled`" in runbook
    assert "Timer evidence in go-live bundle" in runbook
    assert "next_actions" in runbook
    assert "ops_gap.immediate_next_actions" in runbook
    assert "ops_gap.deferred_post_enable_next_actions" in runbook
    assert "ops_gap.deferred_until" in runbook


def test_tushare_news_backup_refresh_scheduler_handoff_keeps_scheduling_out_of_page_path() -> None:
    handoff = SCHEDULER_HANDOFF_PATH.read_text(encoding="utf-8")

    assert "scripts/refresh_tushare_news_backup.py" in handoff
    assert "--dry-run" in handoff
    assert "--enqueue" in handoff
    assert "MOSS_TUSHARE_TOKEN" in handoff
    assert "Windows Task Scheduler" in handoff
    assert "cron" in handoff
    assert "single writer" in handoff
    assert "/ui/news/choice-events/latest" in handoff
    assert "/ui/news/tushare-npr/ingest" in handoff
    assert "/api/news/tushare-npr/ingest" in handoff
    assert "Do not schedule the homepage" in handoff
    assert "scripts/tushare_news_backup_timer_preflight.py" in handoff
    assert "--stage all" in handoff
    assert "--format markdown" in handoff
    assert "--format ops-gap" in handoff
    assert "--stage pre-enable" in handoff
    assert "--stage post-enable" in handoff
    assert "preflight returns `blocked`" in handoff
    assert "docs/templates/tushare_news_backup_timer_enablement_packet.md" in handoff


def test_tushare_news_backup_refresh_go_live_checklist_requires_evidence_before_timer_enablement() -> None:
    checklist = GO_LIVE_CHECKLIST_PATH.read_text(encoding="utf-8")

    assert "MOSS_TUSHARE_TOKEN" in checklist
    assert "credential owner" in checklist.lower()
    assert "schedule owner" in checklist.lower()
    assert "dry-run evidence" in checklist.lower()
    assert "first-run evidence" in checklist.lower()
    assert "post-run dry-run" in checklist.lower()
    assert "page evidence" in checklist.lower()
    assert "latest_received_at" in checklist
    assert "error_rows" in checklist
    assert "blank_payload_rows" in checklist
    assert "/ui/news/choice-events/latest" in checklist
    assert "/ui/news/tushare-npr/ingest" in checklist
    assert "/api/news/tushare-npr/ingest" in checklist
    assert "rollback owner" in checklist.lower()
    assert "Do not enable the timer" in checklist
    assert "scripts/tushare_news_backup_timer_preflight.py" in checklist
    assert "--stage all" in checklist
    assert "--format markdown" in checklist
    assert "--format ops-gap" in checklist
    assert "--stage pre-enable" in checklist
    assert "--stage post-enable" in checklist
    assert "returns `pass`" in checklist
    assert "External timer enablement: enabled" in checklist
    assert "Timer evidence in go-live bundle" in checklist
    assert "docs/templates/tushare_news_backup_timer_enablement_packet.md" in checklist
    assert "Timer enablement packet" in checklist


def test_tushare_news_backup_timer_enablement_packet_is_ops_fillable_not_executable() -> None:
    packet = TIMER_ENABLEMENT_PACKET_PATH.read_text(encoding="utf-8")

    assert "Timer Enablement Packet" in packet
    assert "This packet does not enable the timer" in packet
    assert "Credential owner: `<team/person>`" in packet
    assert "Schedule owner: `<team/person>`" in packet
    assert "Timer host: `<hostname>`" in packet
    assert "Python executable: `<absolute python path>`" in packet
    assert "DuckDB path: `data/moss.duckdb`" in packet
    assert "Log path: `<absolute log path>`" in packet
    assert "Refresh window: `<local time and timezone>`" in packet
    assert "Windows Task Scheduler command draft" in packet
    assert "Cron command draft" in packet
    assert "scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina" in packet
    assert "scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run" in packet
    assert "scripts/tushare_news_backup_timer_preflight.py" in packet
    assert "--stage all" in packet
    assert "--format markdown" in packet
    assert "--format ops-gap" in packet
    assert "--stage pre-enable" in packet
    assert "--stage post-enable" in packet
    assert "preflight must return `pass` before enablement" in packet
    assert "External timer enablement: enabled" in packet
    assert "Timer evidence in go-live bundle" in packet
    assert "docs/handoff/2026-06-03-tushare-news-backup-timer-ops-gap-packet.md" in packet
    assert "timer_enablement_packet_filled" in packet
    assert "No `schtasks /Create` command is provided" in packet
    assert "No `crontab` install command is provided" in packet
    assert "POST /ui/news/tushare-npr/ingest" in packet
    assert "POST /api/news/tushare-npr/ingest" in packet
    assert "/ui/news/choice-events/latest" in packet
    assert "Rollback owner: `<team/person>`" in packet


def test_tushare_news_backup_refresh_handoff_records_delivery_scope_and_verification() -> None:
    handoff = HANDOFF_PATH.read_text(encoding="utf-8")

    assert "buildHomeMacroBriefingModel.ts" in handoff
    assert "backend/app/tasks/choice_news.py" in handoff
    assert "scripts/refresh_tushare_news_backup.py" in handoff
    assert "docs/templates/tushare_news_backup_refresh_scheduler_handoff.md" in handoff
    assert "docs/templates/tushare_news_backup_refresh_go_live_checklist.md" in handoff
    assert "MOSS_TUSHARE_TOKEN" in handoff
    assert "current_backup_state.status" in handoff
    assert "latest_received_at" in handoff
    assert "error_rows" in handoff
    assert "blank_payload_rows" in handoff
    assert "/ui/news/choice-events/latest" in handoff
    assert "/ui/news/tushare-npr/ingest" in handoff
    assert "/api/news/tushare-npr/ingest" in handoff
    assert "No real Tushare call" in handoff
    assert "npm run debt:audit" in handoff


def test_tushare_news_backup_refresh_go_live_evidence_records_first_operator_refresh() -> None:
    evidence = GO_LIVE_EVIDENCE_PATH.read_text(encoding="utf-8")

    assert "current_backup_state.status" in evidence
    assert "status = completed" in evidence
    assert "fetched = 1203" in evidence
    assert "inserted = 1203" in evidence
    assert "purged_expired = 97" in evidence
    assert "tushare.major_news" in evidence
    assert "2026-06-03T19:43:00+00:00" in evidence
    assert "tushare.news.sina" in evidence
    assert "2026-06-03T20:19:24+00:00" in evidence
    assert "error_rows` is `0`" in evidence
    assert "blank_payload_rows` is `0`" in evidence
    assert "Page Evidence" in evidence
    assert "2026-06-03T12:45:10.381Z" in evidence
    assert "frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.png" in evidence
    assert "frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.json" in evidence
    assert "来源：Tushare 宏观快讯（Choice 不可用或偏旧兜底）" in evidence
    assert "来源状态：Tushare 兜底" in evidence
    assert "刷新：随页面查询读取已落库数据" in evidence
    assert "hasAutoUpdateCopy`: `false" in evidence
    assert "hasReservedIngestWriteRequest`: `false" in evidence
    assert "/ui/news/choice-events/latest" in evidence
    assert "/ui/news/tushare-npr/ingest" in evidence
    assert "/api/news/tushare-npr/ingest" in evidence
    assert "External timer enablement: not enabled" in evidence
    assert "scripts/tushare_news_backup_timer_preflight.py" in evidence
    assert "`pass` verdict" in evidence
    assert "schedule owner" in evidence.lower()
    assert "rollback owner" in evidence.lower()


def test_tushare_news_backup_timer_preflight_status_records_current_blockers_and_next_actions() -> None:
    status = TIMER_PREFLIGHT_STATUS_PATH.read_text(encoding="utf-8")

    assert "Tushare News Backup Timer Preflight Status" in status
    assert "External timer is not enabled" in status
    assert "--stage all" in status
    assert "--format markdown" in status
    assert "--format ops-gap" in status
    assert "Combined verdict: `blocked`" in status
    assert "Blocking stages: `pre-enable`, `post-enable`" in status
    assert "Pre-enable summary: `6 pass / 5 blocked`" in status
    assert "Post-enable summary: `6 pass / 7 blocked`" in status
    assert "Operator Fill Order" in status
    assert "Fill owner fields first" in status
    assert "Confirm boundary rows with evidence" in status
    assert "Complete the timer enablement packet" in status
    assert "Record page acceptance sign-off" in status
    assert "Set Enable timer to yes after pre-enable evidence is accepted" in status
    assert "rerun `--stage pre-enable` before creating the external timer" in status
    assert "After the first scheduled run, attach timer evidence" in status
    assert "Activation Sequence" in status
    assert "Immediate stage: `pre-enable`" in status
    status_words = " ".join(status.split())
    assert "Post-enable inputs remain deferred until `pre-enable` returns `pass` and the first scheduled run finishes." in status_words
    assert "Do not create the external timer while `pre-enable` is blocked." in status
    assert "Already Verified Evidence Gates" in status
    assert "`checklist_exists`" in status
    assert "`page_evidence_json_confirms_read_only_fallback`" in status
    assert "Reserved routes remain reserved:" in status
    assert "Homepage read path remains `/ui/news/choice-events/latest`." in status
    assert "pre-enable" in status
    assert "post-enable" in status
    assert "owners_filled" in status
    assert "boundary_confirmation_filled" in status
    assert "timer_enablement_packet_filled" in status
    assert "page_acceptance_signoff_filled" in status
    assert "enable_timer_decision_yes" in status
    assert "timer_evidence_filled" in status
    assert "post_enable_evidence_confirms_timer_enabled" in status
    assert "next_actions" in status
    assert "ops_gap.immediate_next_actions" in status
    assert "ops_gap.deferred_post_enable_next_actions" in status
    assert "ops_gap.deferred_until" in status
    assert "docs/templates/tushare_news_backup_refresh_go_live_checklist.md" in status
    assert "docs/templates/tushare_news_backup_timer_enablement_packet.md" in status
    assert "docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md" in status
    assert "docs/handoff/2026-06-03-tushare-news-backup-timer-ops-gap-packet.md" in status
    assert "Do not enable the timer" in status


def test_tushare_news_backup_timer_preflight_status_matches_current_preflight_report() -> None:
    status = TIMER_PREFLIGHT_STATUS_PATH.read_text(encoding="utf-8")
    module = _load_preflight_module()

    pre_enable = module.build_timer_preflight_report(repo_root=ROOT, stage="pre-enable")
    post_enable = module.build_timer_preflight_report(repo_root=ROOT, stage="post-enable")
    all_stage = module.build_timer_preflight_bundle(repo_root=ROOT)

    assert pre_enable["verdict"] == "blocked"
    assert post_enable["verdict"] == "blocked"
    assert all_stage["verdict"] == "blocked"
    assert all_stage["blocking_stages"] == ["pre-enable", "post-enable"]
    assert f"Combined verdict: `{all_stage['verdict']}`" in status
    assert "Blocking stages: `pre-enable`, `post-enable`" in status
    assert (
        f"Pre-enable summary: `{pre_enable['summary']['pass']} pass / "
        f"{pre_enable['summary']['blocked']} blocked`"
    ) in status
    assert (
        f"Post-enable summary: `{post_enable['summary']['pass']} pass / "
        f"{post_enable['summary']['blocked']} blocked`"
    ) in status

    for item in pre_enable["blocking_items"]:
        assert f"`{item}`" in status

    for item in post_enable["blocking_items"]:
        assert f"`{item}`" in status

    for action in pre_enable["next_actions"] + post_enable["next_actions"]:
        assert f"`{action['gate']}`" in status
        assert f"`{action['path']}`" in status
        assert action["action"] in status

    assert [action["gate"] for action in all_stage["ops_gap"]["immediate_next_actions"]] == [
        "owners_filled",
        "boundary_confirmation_filled",
        "timer_enablement_packet_filled",
        "page_acceptance_signoff_filled",
        "enable_timer_decision_yes",
    ]
    assert [
        action["gate"]
        for action in all_stage["ops_gap"]["deferred_post_enable_next_actions"]
    ] == [
        "timer_evidence_filled",
        "post_enable_evidence_confirms_timer_enabled",
    ]


def test_tushare_news_backup_timer_ops_gap_packet_lists_external_inputs_without_enabling_timer() -> None:
    packet = TIMER_OPS_GAP_PACKET_PATH.read_text(encoding="utf-8")
    module = _load_preflight_module()
    generated = module.render_timer_ops_gap_markdown(
        module.build_timer_preflight_bundle(repo_root=ROOT)
    )

    assert "Tushare News Backup Timer Ops Gap Packet" in packet
    assert "This packet does not enable the timer" in packet
    assert "Do not run a real Tushare refresh from this packet" in packet
    assert "Do not open reserved ingest routes" in packet
    assert "External timer remains disabled" in packet
    assert "--format ops-gap" in packet
    assert "Current verdict: `blocked`" in packet
    assert "Required External Inputs" in packet
    assert "Credential owner" in packet
    assert "Schedule owner" in packet
    assert "Page acceptance owner" in packet
    assert "Rollback owner" in packet
    assert "Timer host" in packet
    assert "Repository root" in packet
    assert "Python executable" in packet
    assert "Log path" in packet
    assert "Refresh window" in packet
    assert "Write-window exclusion note" in packet
    assert "Page evidence owner sign-off" in packet
    assert "Enable timer decision" in packet
    assert "Timer evidence" in packet
    assert "Post-Enable Inputs" in packet
    assert "Run `python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable` after filling pre-enable inputs." in packet
    assert "Run `python scripts/tushare_news_backup_timer_preflight.py --stage post-enable` after the first scheduled run." in packet
    assert "POST /ui/news/tushare-npr/ingest" in packet
    assert "POST /api/news/tushare-npr/ingest" in packet
    assert "/ui/news/choice-events/latest" in packet

    for marker in (
        "Set to yes after pre-enable evidence is accepted, then rerun pre-enable before creating the external timer.",
        "Run `python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable` after filling pre-enable inputs.",
        "Run `python scripts/tushare_news_backup_timer_preflight.py --stage post-enable` after the first scheduled run.",
    ):
        assert marker in generated
        assert marker in packet


def test_tushare_news_backup_timer_ops_gap_packet_matches_current_blockers_and_actions() -> None:
    packet = TIMER_OPS_GAP_PACKET_PATH.read_text(encoding="utf-8")
    module = _load_preflight_module()
    report = module.build_timer_preflight_bundle(repo_root=ROOT)
    generated = module.render_timer_ops_gap_markdown(report)

    for marker in (
        "## Current Blocking Items",
        "### Pre-Enable",
        "### Post-Enable",
        "## Immediate `next_actions`",
        "## Deferred Post-Enable `next_actions`",
        "## Activation Sequence",
        "Immediate stage: `pre-enable`",
        "Do not create the external timer while `pre-enable` is blocked.",
    ):
        assert marker in generated
        assert marker in packet

    generated_words = " ".join(generated.split())
    packet_words = " ".join(packet.split())
    for marker in (
        "Post-enable inputs remain deferred until `pre-enable` returns `pass` and the first scheduled run finishes.",
        "After `pre-enable` passes, create the external timer outside this packet and collect first-run evidence.",
    ):
        assert marker in generated_words
        assert marker in packet_words

    assert "Blocking stages: `pre-enable`, `post-enable`" in generated
    assert "Blocking stages: `pre-enable`, `post-enable`" in packet

    pre_enable = report["reports"]["pre-enable"]
    post_enable = report["reports"]["post-enable"]
    for marker in (
        f"Pre-enable summary: `{pre_enable['summary']['pass']} pass / {pre_enable['summary']['blocked']} blocked`",
        f"Post-enable summary: `{post_enable['summary']['pass']} pass / {post_enable['summary']['blocked']} blocked`",
    ):
        assert marker in generated
        assert marker in packet

    for stage, stage_report in report["reports"].items():
        for item in stage_report["blocking_items"]:
            assert f"- `{item}`" in generated
            assert f"- `{item}`" in packet

        for action in stage_report["next_actions"]:
            row = f"| `{action['gate']}` | `{action['path']}` | {action['action']} |"
            assert row in generated
            assert row in packet

    generated_deferred = generated.split(
        "## Deferred Post-Enable `next_actions`", maxsplit=1
    )[1].split("## Required External Inputs", maxsplit=1)[0]
    packet_deferred = packet.split(
        "## Deferred Post-Enable `next_actions`", maxsplit=1
    )[1].split("## Required External Inputs", maxsplit=1)[0]
    for marker in (
        "`owners_filled`",
        "`boundary_confirmation_filled`",
        "`timer_enablement_packet_filled`",
        "`page_acceptance_signoff_filled`",
        "`enable_timer_decision_yes`",
    ):
        assert marker not in generated_deferred
        assert marker not in packet_deferred
