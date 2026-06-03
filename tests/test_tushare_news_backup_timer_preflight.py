from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import load_module


CHECKLIST = "docs/templates/tushare_news_backup_refresh_go_live_checklist.md"
TIMER_PACKET = "docs/templates/tushare_news_backup_timer_enablement_packet.md"
EVIDENCE = "docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md"
SCREENSHOT = "frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.png"
BROWSER_JSON = "frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.json"


def _load_preflight_module():
    return load_module(
        "scripts.tushare_news_backup_timer_preflight",
        "scripts/tushare_news_backup_timer_preflight.py",
    )


def _write(path: Path, text: str = "evidence") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_fixture_tree(
    root: Path,
    *,
    checklist: str,
    evidence: str,
    timer_packet: str | None = None,
    artifacts: bool = True,
) -> None:
    _write(root / CHECKLIST, checklist)
    _write(root / EVIDENCE, evidence)
    _write(root / TIMER_PACKET, timer_packet if timer_packet is not None else _ready_timer_packet())
    if artifacts:
        _write(root / SCREENSHOT, "png placeholder")
        _write(root / BROWSER_JSON, _page_evidence_json())


def _pending_checklist() -> str:
    return """
# Tushare News Backup Refresh Go-Live Checklist

- Credential owner: `<team/person>`
- Schedule owner: `<team/person>`
- Page acceptance owner: `<team/person>`
- Rollback owner: `<team/person>`
- Evidence location: `<ticket/path/log bundle>`

| `MOSS_TUSHARE_TOKEN` is configured in the scheduled job environment. | `<yes/no>` | `<env proof without exposing token>` |
| Job runs from repo root or explicitly sets repo root. | `<yes/no>` | `<scheduler command/log>` |
| DuckDB path points to intended target. | `<yes/no>` | `<duckdb path>` |
| Refresh window avoids other DuckDB write/materialization jobs. | `<yes/no>` | `<calendar/ops note>` |
| `/ui/news/tushare-npr/ingest` remains reserved. | `<yes/no>` | `<test/output>` |
| `/api/news/tushare-npr/ingest` remains reserved. | `<yes/no>` | `<test/output>` |
| Homepage still reads via `/ui/news/choice-events/latest`. | `<yes/no>` | `<page/API evidence>` |

- Page evidence owner sign-off: `<team/person>`

- Enable timer: `<yes/no>`
- Enabled by: `<team/person>`
- Enabled at: `<timestamp>`
- Timer evidence: `<scheduler screenshot/log/config link>`
"""


def _ready_checklist() -> str:
    return f"""
# Tushare News Backup Refresh Go-Live Checklist

- Credential owner: DataOps
- Schedule owner: PlatformOps
- Page acceptance owner: ProductOps
- Rollback owner: PlatformOps
- Evidence location: {EVIDENCE}

| `MOSS_TUSHARE_TOKEN` is configured in the scheduled job environment. | yes | ops/env-proof |
| Job runs from repo root or explicitly sets repo root. | yes | scheduler command |
| DuckDB path points to intended target. | yes | data/moss.duckdb |
| Refresh window avoids other DuckDB write/materialization jobs. | yes | ops calendar |
| `/ui/news/tushare-npr/ingest` remains reserved. | yes | pytest route output |
| `/api/news/tushare-npr/ingest` remains reserved. | yes | pytest route output |
| Homepage still reads via `/ui/news/choice-events/latest`. | yes | page evidence |

- Page evidence owner sign-off: ProductOps

- Enable timer: yes
- Enabled by: PlatformOps
- Enabled at: 2026-06-03T21:00:00+08:00
- Timer evidence: scheduler/job/tushare-news-backup
"""


def _ready_pre_enable_checklist() -> str:
    return f"""
# Tushare News Backup Refresh Go-Live Checklist

- Credential owner: DataOps
- Schedule owner: PlatformOps
- Page acceptance owner: ProductOps
- Rollback owner: PlatformOps
- Evidence location: {EVIDENCE}

| `MOSS_TUSHARE_TOKEN` is configured in the scheduled job environment. | yes | ops/env-proof |
| Job runs from repo root or explicitly sets repo root. | yes | scheduler command |
| DuckDB path points to intended target. | yes | data/moss.duckdb |
| Refresh window avoids other DuckDB write/materialization jobs. | yes | ops calendar |
| `/ui/news/tushare-npr/ingest` remains reserved. | yes | pytest route output |
| `/api/news/tushare-npr/ingest` remains reserved. | yes | pytest route output |
| Homepage still reads via `/ui/news/choice-events/latest`. | yes | page evidence |

- Page evidence owner sign-off: ProductOps

- Enable timer: yes
- Enabled by: `<team/person>`
- Enabled at: `<timestamp>`
- Timer evidence: `<scheduler screenshot/log/config link>`
"""


def _evidence() -> str:
    return f"""
# Tushare News Backup Refresh Go-Live Evidence

- External timer enablement: not enabled.
- Homepage read API remains `/ui/news/choice-events/latest`.
- `POST /ui/news/tushare-npr/ingest` remains reserved.
- `POST /api/news/tushare-npr/ingest` remains reserved.

status = completed
fetched = 1203
inserted = 1203
purged_expired = 97

`tushare.major_news` | 1600 | `2026-06-03T19:43:00+00:00` | 0 | 0
`tushare.news.sina` | 200 | `2026-06-03T20:19:24+00:00` | 0 | 0
`tushare.npr` | 2 | `2026-05-19T08:50:00+00:00` | 0 | 0
`error_rows` is `0`
`blank_payload_rows` is `0`

## Page Evidence

Browser evidence timestamp: `2026-06-03T12:45:10.381Z`
Screenshot: `{SCREENSHOT}`
Browser/network evidence JSON: `{BROWSER_JSON}`
Visible source label: `Tushare`
Visible refresh label: `read landed data`

- `hasReadLandedCopy`: `true`.
- `hasAutoUpdateCopy`: `false`.
- `hasReservedIngestWriteRequest`: `false`.
- All captured news requests were `GET /ui/news/choice-events/latest`.
- No browser request was sent to `POST /ui/news/tushare-npr/ingest`.
- No browser request was sent to `POST /api/news/tushare-npr/ingest`.
"""


def _post_enable_evidence() -> str:
    return _evidence().replace(
        "- External timer enablement: not enabled.",
        "\n".join(
            (
                "- External timer enablement: enabled",
                "- Timer evidence in go-live bundle: scheduler/job/tushare-news-backup",
            )
        ),
    )


def _page_evidence_json(
    *,
    has_read_landed_copy: bool = True,
    has_auto_update_copy: bool = False,
    has_tushare_copy: bool = True,
    has_news_items: bool = True,
    has_reserved_ingest_write_request: bool = False,
    write_requests: list[dict[str, str]] | None = None,
    news_requests: list[dict[str, str]] | None = None,
) -> str:
    payload = {
        "checks": {
            "hasReadLandedCopy": has_read_landed_copy,
            "hasAutoUpdateCopy": has_auto_update_copy,
            "hasTushareCopy": has_tushare_copy,
            "hasNewsItems": has_news_items,
            "hasReservedIngestWriteRequest": has_reserved_ingest_write_request,
        },
        "newsRequests": news_requests
        if news_requests is not None
        else [
            {
                "method": "GET",
                "url": "http://127.0.0.1:5888/ui/news/choice-events/latest?topic_code=tushare.news.sina",
            }
        ],
        "newsResponses": [
            {
                "status": 200,
                "url": "http://127.0.0.1:5888/ui/news/choice-events/latest?topic_code=tushare.news.sina",
            }
        ],
        "writeRequests": write_requests or [],
    }
    return json.dumps(payload)


def _pending_timer_packet() -> str:
    return """
# Tushare News Backup Timer Enablement Packet

- Credential owner: `<team/person>`
- Schedule owner: `<team/person>`
- Page acceptance owner: `<team/person>`
- Rollback owner: `<team/person>`
- Timer host: `<hostname>`
- Repository root: `<absolute repo path>`
- Python executable: `<absolute python path>`
- DuckDB path: `data/moss.duckdb`
- Log path: `<absolute log path>`
- Refresh window: `<local time and timezone>`
- Write-window exclusion note: `<how this avoids other DuckDB writes>`
- Alert/log retention owner: `<team/person>`

No `schtasks /Create` command is provided here.
No `crontab` install command is provided here.
"""


def _ready_timer_packet() -> str:
    return """
# Tushare News Backup Timer Enablement Packet

- Credential owner: DataOps
- Schedule owner: PlatformOps
- Page acceptance owner: ProductOps
- Rollback owner: PlatformOps
- Timer host: moss-job-01
- Repository root: F:\\MOSS-V3
- Python executable: C:\\Python314\\python.exe
- DuckDB path: `data/moss.duckdb`
- Log path: F:\\MOSS-V3\\logs\\tushare-news-backup-refresh.log
- Refresh window: 08:15 Asia/Shanghai on trading weekdays
- Write-window exclusion note: Runs outside materialization and DuckDB writer windows.
- Alert/log retention owner: PlatformOps

Windows Task Scheduler command draft
Cron command draft
scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina
scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run
scripts/tushare_news_backup_timer_preflight.py
The preflight must return `pass` before enablement.
No `schtasks /Create` command is provided here.
No `crontab` install command is provided here.
POST /ui/news/tushare-npr/ingest
POST /api/news/tushare-npr/ingest
/ui/news/choice-events/latest
"""


def test_timer_preflight_blocks_when_owner_and_scheduler_fields_are_pending(tmp_path: Path) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(tmp_path, checklist=_pending_checklist(), evidence=_evidence())

    report = module.build_timer_preflight_report(repo_root=tmp_path)

    assert report["verdict"] == "blocked"
    assert "owners_filled" in report["blocking_items"]
    assert "boundary_confirmation_filled" in report["blocking_items"]
    assert "page_acceptance_signoff_filled" in report["blocking_items"]
    assert "enable_timer_decision_yes" in report["blocking_items"]
    assert "timer_evidence_filled" in report["blocking_items"]
    assert "timer_enablement_packet_filled" not in report["blocking_items"]
    assert any(
        action["gate"] == "owners_filled"
        and action["path"] == CHECKLIST
        and "Credential owner" in action["action"]
        for action in report["next_actions"]
    )
    assert any(
        action["gate"] == "boundary_confirmation_filled"
        and action["path"] == CHECKLIST
        for action in report["next_actions"]
    )


def test_timer_preflight_passes_only_when_checklist_and_evidence_are_complete(tmp_path: Path) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(tmp_path, checklist=_ready_checklist(), evidence=_post_enable_evidence())

    report = module.build_timer_preflight_report(repo_root=tmp_path)

    assert report["verdict"] == "pass"
    assert report["blocking_items"] == []
    assert report["next_actions"] == []
    assert report["summary"]["blocked"] == 0


def test_timer_preflight_pre_enable_stage_does_not_require_post_enable_timer_evidence(tmp_path: Path) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(
        tmp_path,
        checklist=_ready_pre_enable_checklist(),
        evidence=_evidence(),
    )

    report = module.build_timer_preflight_report(repo_root=tmp_path, stage="pre-enable")

    assert report["verdict"] == "pass"
    assert "timer_evidence_filled" not in report["blocking_items"]
    assert report["stage"] == "pre-enable"


def test_timer_preflight_post_enable_stage_requires_timer_evidence(tmp_path: Path) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(
        tmp_path,
        checklist=_ready_pre_enable_checklist(),
        evidence=_evidence(),
    )

    report = module.build_timer_preflight_report(repo_root=tmp_path, stage="post-enable")

    assert report["verdict"] == "blocked"
    assert "timer_evidence_filled" in report["blocking_items"]
    assert report["stage"] == "post-enable"


def test_timer_preflight_post_enable_stage_blocks_when_evidence_still_says_not_enabled(tmp_path: Path) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(
        tmp_path,
        checklist=_ready_checklist(),
        evidence=_evidence(),
    )

    report = module.build_timer_preflight_report(repo_root=tmp_path, stage="post-enable")

    assert report["verdict"] == "blocked"
    assert "post_enable_evidence_confirms_timer_enabled" in report["blocking_items"]
    gate = next(
        item
        for item in report["gates"]
        if item["name"] == "post_enable_evidence_confirms_timer_enabled"
    )
    assert "still says not enabled" in gate["detail"]


def test_timer_preflight_post_enable_stage_blocks_when_evidence_timer_detail_is_placeholder(tmp_path: Path) -> None:
    module = _load_preflight_module()
    evidence = _post_enable_evidence().replace(
        "- Timer evidence in go-live bundle: scheduler/job/tushare-news-backup",
        "- Timer evidence in go-live bundle: `<scheduler screenshot/log/config link>`",
    )
    _write_fixture_tree(
        tmp_path,
        checklist=_ready_checklist(),
        evidence=evidence,
    )

    report = module.build_timer_preflight_report(repo_root=tmp_path, stage="post-enable")

    assert report["verdict"] == "blocked"
    assert "post_enable_evidence_confirms_timer_enabled" in report["blocking_items"]
    gate = next(
        item
        for item in report["gates"]
        if item["name"] == "post_enable_evidence_confirms_timer_enabled"
    )
    assert "Timer evidence in go-live bundle" in gate["detail"]


def test_timer_preflight_blocks_when_enablement_packet_fields_are_pending(tmp_path: Path) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(
        tmp_path,
        checklist=_ready_checklist(),
        evidence=_evidence(),
        timer_packet=_pending_timer_packet(),
    )

    report = module.build_timer_preflight_report(repo_root=tmp_path)

    assert report["verdict"] == "blocked"
    assert "timer_enablement_packet_filled" in report["blocking_items"]


def test_timer_preflight_blocks_when_enablement_packet_contains_install_commands(tmp_path: Path) -> None:
    module = _load_preflight_module()
    packet = _ready_timer_packet() + """

```powershell
schtasks /Create /TN MOSS-TushareNewsBackup /SC DAILY /TR "python scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina"
```

```sh
crontab tushare-news-backup.cron
```
"""
    _write_fixture_tree(
        tmp_path,
        checklist=_ready_checklist(),
        evidence=_evidence(),
        timer_packet=packet,
    )

    report = module.build_timer_preflight_report(repo_root=tmp_path)

    assert report["verdict"] == "blocked"
    assert "timer_enablement_packet_filled" in report["blocking_items"]
    gate = next(
        item
        for item in report["gates"]
        if item["name"] == "timer_enablement_packet_filled"
    )
    assert "Install commands are not allowed" in gate["detail"]


def test_timer_preflight_blocks_when_enablement_packet_is_missing(tmp_path: Path) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(tmp_path, checklist=_ready_checklist(), evidence=_evidence())
    (tmp_path / TIMER_PACKET).unlink()

    report = module.build_timer_preflight_report(repo_root=tmp_path)

    assert report["verdict"] == "blocked"
    assert "timer_enablement_packet_exists" in report["blocking_items"]


def test_timer_preflight_blocks_when_page_artifacts_are_missing(tmp_path: Path) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(tmp_path, checklist=_ready_checklist(), evidence=_evidence(), artifacts=False)

    report = module.build_timer_preflight_report(repo_root=tmp_path)

    assert report["verdict"] == "blocked"
    assert "page_artifacts_exist" in report["blocking_items"]


def test_timer_preflight_blocks_when_page_evidence_json_contradicts_read_only_fallback(tmp_path: Path) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(tmp_path, checklist=_ready_checklist(), evidence=_evidence())
    _write(
        tmp_path / BROWSER_JSON,
        _page_evidence_json(
            has_read_landed_copy=False,
            has_auto_update_copy=True,
            has_reserved_ingest_write_request=True,
            write_requests=[
                {
                    "method": "POST",
                    "url": "http://127.0.0.1:5888/ui/news/tushare-npr/ingest",
                }
            ],
        ),
    )

    report = module.build_timer_preflight_report(repo_root=tmp_path)

    assert report["verdict"] == "blocked"
    assert "page_evidence_json_confirms_read_only_fallback" in report["blocking_items"]
    gate = next(
        item
        for item in report["gates"]
        if item["name"] == "page_evidence_json_confirms_read_only_fallback"
    )
    assert "hasReadLandedCopy" in gate["detail"]
    assert "reserved ingest write request" in gate["detail"]


def test_timer_preflight_cli_returns_nonzero_when_blocked(tmp_path: Path, capsys) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(tmp_path, checklist=_pending_checklist(), evidence=_evidence())

    exit_code = module.main(["--repo-root", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["verdict"] == "blocked"
    assert "owners_filled" in payload["blocking_items"]


def test_timer_preflight_cli_accepts_pre_enable_stage(tmp_path: Path, capsys) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(
        tmp_path,
        checklist=_ready_pre_enable_checklist(),
        evidence=_evidence(),
    )

    exit_code = module.main(["--repo-root", str(tmp_path), "--stage", "pre-enable"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["verdict"] == "pass"
    assert payload["stage"] == "pre-enable"


def test_timer_preflight_cli_accepts_all_stage_bundle(tmp_path: Path, capsys) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(
        tmp_path,
        checklist=_ready_pre_enable_checklist(),
        evidence=_evidence(),
    )

    exit_code = module.main(["--repo-root", str(tmp_path), "--stage", "all"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["stage"] == "all"
    assert payload["verdict"] == "blocked"
    assert payload["reports"]["pre-enable"]["verdict"] == "pass"
    assert payload["reports"]["post-enable"]["verdict"] == "blocked"
    assert "timer_evidence_filled" in payload["reports"]["post-enable"]["blocking_items"]
    assert payload["ops_gap"]["immediate_stage"] == "pre-enable"
    assert payload["ops_gap"]["deferred_stage"] == "post-enable"
    assert payload["ops_gap"]["deferred_until"] == "pre-enable pass and first scheduled run finishes"
    assert payload["ops_gap"]["ready_to_create_timer"] is True
    assert [
        action["gate"] for action in payload["ops_gap"]["immediate_next_actions"]
    ] == []
    assert [
        action["gate"] for action in payload["ops_gap"]["deferred_post_enable_next_actions"]
    ] == [
        "timer_evidence_filled",
        "post_enable_evidence_confirms_timer_enabled",
    ]


def test_timer_preflight_cli_can_render_all_stage_markdown_status(tmp_path: Path, capsys) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(
        tmp_path,
        checklist=_ready_pre_enable_checklist(),
        evidence=_evidence(),
    )

    exit_code = module.main(
        ["--repo-root", str(tmp_path), "--stage", "all", "--format", "markdown"]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Combined verdict: `blocked`" in output
    assert "Blocking stages: `post-enable`" in output
    assert "Pre-enable summary: `11 pass / 0 blocked`" in output
    assert "Post-enable summary: `11 pass / 2 blocked`" in output
    assert "Machine-readable JSON `ops_gap`:" in output
    assert "`ops_gap.ready_to_create_timer`" in output
    assert "`ops_gap.immediate_next_actions`" in output
    assert "`ops_gap.deferred_post_enable_next_actions`" in output
    assert "`ops_gap.deferred_until`" in output
    assert "Operator Fill Order" in output
    assert "Fill owner fields first" in output
    assert "After the first scheduled run, attach timer evidence" in output
    assert "Activation Sequence" in output
    assert "Immediate stage: `pre-enable`" in output
    assert "Post-enable inputs remain deferred until `pre-enable` returns `pass` and the first scheduled run finishes." in output
    assert "Status timestamp:" in output
    assert "Already Verified Evidence Gates" in output
    assert "`checklist_exists`" in output
    assert "Reserved routes remain reserved:" in output
    assert "POST /ui/news/tushare-npr/ingest" in output
    assert "Homepage read path remains `/ui/news/choice-events/latest`." in output
    assert "`timer_evidence_filled`" in output
    assert "docs/templates/tushare_news_backup_refresh_go_live_checklist.md" in output

    post_enable_section = output.split("## Post-Enable Status", maxsplit=1)[1]
    post_enable_section = post_enable_section.split("## Already Verified Evidence Gates", maxsplit=1)[0]
    assert "Additional post-enable `next_actions`:" in post_enable_section
    assert "`timer_evidence_filled`" in post_enable_section
    assert "`post_enable_evidence_confirms_timer_enabled`" in post_enable_section
    assert "`owners_filled`" not in post_enable_section
    assert "`boundary_confirmation_filled`" not in post_enable_section
    assert "`timer_enablement_packet_filled`" not in post_enable_section
    assert "`page_acceptance_signoff_filled`" not in post_enable_section
    assert "`enable_timer_decision_yes`" not in post_enable_section


def test_timer_preflight_cli_can_render_single_stage_markdown_status(tmp_path: Path, capsys) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(tmp_path, checklist=_pending_checklist(), evidence=_evidence())

    exit_code = module.main(
        ["--repo-root", str(tmp_path), "--stage", "pre-enable", "--format", "markdown"]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Current verdict: `blocked`" in output
    assert "Current blocking items:" in output
    assert "`owners_filled`" in output
    assert "Current `next_actions`:" in output
    assert "docs/templates/tushare_news_backup_refresh_go_live_checklist.md" in output


def test_timer_preflight_cli_can_render_ops_gap_packet(tmp_path: Path, capsys) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(tmp_path, checklist=_pending_checklist(), evidence=_evidence())

    exit_code = module.main(
        ["--repo-root", str(tmp_path), "--stage", "all", "--format", "ops-gap"]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Tushare News Backup Timer Ops Gap Packet" in output
    assert "This packet does not enable the timer" in output
    assert "Do not run a real Tushare refresh from this packet" in output
    assert "External timer remains disabled" in output
    assert "Current verdict: `blocked`" in output
    assert "Blocking stages: `pre-enable`, `post-enable`" in output
    assert "Pre-enable summary:" in output
    assert "Post-enable summary:" in output
    assert "## Activation Sequence" in output
    assert "Immediate stage: `pre-enable`" in output
    assert "Post-enable inputs remain deferred until `pre-enable` returns `pass` and the first scheduled run finishes." in output
    assert "Required External Inputs" in output
    assert "Credential owner" in output
    assert "Timer host" in output
    assert "Python executable" in output
    assert "Write-window exclusion note" in output
    assert "Post-Enable Inputs" in output
    assert "Run `python scripts/tushare_news_backup_timer_preflight.py --stage pre-enable` after filling pre-enable inputs." in output
    assert "Run `python scripts/tushare_news_backup_timer_preflight.py --stage post-enable` after the first scheduled run." in output
    assert "POST /ui/news/tushare-npr/ingest" in output
    assert "/ui/news/choice-events/latest" in output


def test_timer_preflight_ops_gap_packet_lists_current_blockers_and_actions(tmp_path: Path, capsys) -> None:
    module = _load_preflight_module()
    _write_fixture_tree(tmp_path, checklist=_pending_checklist(), evidence=_evidence())

    exit_code = module.main(
        ["--repo-root", str(tmp_path), "--stage", "all", "--format", "ops-gap"]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "## Current Blocking Items" in output
    assert "### Pre-Enable" in output
    assert "- `owners_filled`" in output
    assert "- `boundary_confirmation_filled`" in output
    assert "### Post-Enable" in output
    assert "- `timer_evidence_filled`" in output
    assert "## Immediate `next_actions`" in output
    assert "| `owners_filled` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Fill Credential owner" in output
    assert "## Deferred Post-Enable `next_actions`" in output
    assert "| `timer_evidence_filled` | `docs/templates/tushare_news_backup_refresh_go_live_checklist.md` | Fill Enabled by, Enabled at, and Timer evidence after the first scheduled run. |" in output

    deferred = output.split("## Deferred Post-Enable `next_actions`", maxsplit=1)[1]
    deferred = deferred.split("## Required External Inputs", maxsplit=1)[0]
    assert "`owners_filled`" not in deferred
    assert "`boundary_confirmation_filled`" not in deferred
    assert "`timer_enablement_packet_filled`" not in deferred
    assert "`page_acceptance_signoff_filled`" not in deferred
    assert "`enable_timer_decision_yes`" not in deferred
