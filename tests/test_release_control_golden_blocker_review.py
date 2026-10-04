from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

import pytest

from scripts.release_control_golden_blocker_review import (
    BLOCKER_SPECS,
    EVIDENCE_SCOPE,
    ROOT,
    TARGET_TEST,
    _approval_metadata,
    _display_path,
    _safe_output_path,
    build_review_packet,
    write_packet_exclusive,
)


SCRIPT = ROOT / "scripts" / "release_control_golden_blocker_review.py"


@pytest.fixture
def repo_local_junit_dir() -> Iterator[Path]:
    repo_root = ROOT.resolve(strict=True)
    temp_parent = ROOT / ".codex-tmp"
    if not temp_parent.exists():
        temp_parent = ROOT / "tests"
    resolved_parent = temp_parent.resolve(strict=True)
    if not resolved_parent.is_dir() or not resolved_parent.is_relative_to(repo_root):
        raise AssertionError("temporary JUnit parent must stay inside repository")

    junit_dir = Path(tempfile.mkdtemp(prefix="release-golden-junit-", dir=temp_parent))
    try:
        yield junit_dir
    finally:
        if junit_dir.resolve(strict=True).parent != resolved_parent:
            raise AssertionError("temporary JUnit directory escaped its parent")
        shutil.rmtree(junit_dir)


def _write_junit(
    path: Path,
    *,
    statuses: dict[str, str] | None = None,
    omit: set[str] | None = None,
) -> None:
    statuses = statuses or {}
    omit = omit or set()
    suite = ET.Element("testsuite")
    for sample_id, spec in BLOCKER_SPECS.items():
        if sample_id in omit:
            continue
        case = ET.SubElement(
            suite,
            "testcase",
            name=f"{TARGET_TEST}[{sample_id}]",
        )
        status = statuses.get(sample_id, "failed")
        if status == "failed":
            path_tuple = tuple(spec["expected_assertion_path"].split("."))
            failure = ET.SubElement(
                case,
                "failure",
                message=f"AssertionError: {path_tuple!r}",
            )
            failure.text = "SECRET-ACTUAL-VALUE != SECRET-EXPECTED-VALUE"
        elif status == "error":
            ET.SubElement(case, "error", message="private infrastructure error")
        elif status == "skipped":
            ET.SubElement(case, "skipped", message="private skip reason")
        elif status != "passed":
            raise AssertionError(status)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def test_build_review_packet_is_sanitized_fail_closed_and_digest_bound(
    repo_local_junit_dir: Path,
) -> None:
    junit = repo_local_junit_dir / "result.xml"
    _write_junit(junit)

    packet = build_review_packet(
        junit_xml=junit,
        generated_at="2026-08-31T00:00:00+08:00",
    )

    assert packet["report_kind"] == "release_control_golden_blocker_review"
    assert packet["status"] == "blocked"
    assert packet["release_eligible"] is False
    assert packet["sample_count"] == 9
    assert packet["observation"]["complete"] is True
    assert packet["observation"]["counts"]["failed"] == 9
    assert packet["observation"]["junit_xml_path"].endswith("/result.xml")
    assert not Path(packet["observation"]["junit_xml_path"]).is_absolute()
    assert packet["evidence_scope"] == EVIDENCE_SCOPE
    assert all(value is False for value in packet["evidence_scope"].values())

    rows = {row["sample_id"]: row for row in packet["samples"]}
    assert rows["GS-PNL-DATA-A"]["observed_assertion_path"] == (
        "result_meta.rule_version"
    )
    insights = rows["GS-PNL-BUSINESS-INSIGHTS-A"]
    assert insights["captured_approval_status"] == "approved"
    assert insights["approval_revalidation_required"] is True
    assert rows["GS-PNL-OVERVIEW-A"]["coupled_samples"] == ["GS-PNL-DATA-A"]
    assert all(
        len(digest) == 64
        for row in rows.values()
        for digest in row["artifact_sha256"].values()
    )

    serialized = json.dumps(packet, ensure_ascii=False)
    assert "SECRET-ACTUAL-VALUE" not in serialized
    assert "SECRET-EXPECTED-VALUE" not in serialized
    assert "private infrastructure error" not in serialized


def test_missing_junit_case_remains_blocked(tmp_path: Path) -> None:
    junit = tmp_path / "result.xml"
    _write_junit(junit, omit={"GS-RISK-WARN-B"})

    packet = build_review_packet(junit_xml=junit)

    assert packet["status"] == "blocked"
    assert packet["observation"]["complete"] is False
    assert packet["observation"]["counts"]["missing"] == 1
    row = next(
        item for item in packet["samples"] if item["sample_id"] == "GS-RISK-WARN-B"
    )
    assert row["test_status"] == "missing"


def test_all_tests_passing_still_cannot_approve_or_release(tmp_path: Path) -> None:
    junit = tmp_path / "result.xml"
    _write_junit(
        junit,
        statuses={sample_id: "passed" for sample_id in BLOCKER_SPECS},
    )

    packet = build_review_packet(junit_xml=junit)

    assert packet["status"] == "awaiting_owner_decisions"
    assert packet["observation"]["all_targeted_tests_passed"] is True
    assert packet["release_eligible"] is False
    assert packet["evidence_scope"]["captures_approval"] is False


def test_approval_metadata_only_extracts_status_and_owner(tmp_path: Path) -> None:
    approval = tmp_path / "approval.md"
    approval.write_text(
        "# Approval\n- Status: `approved`\n- Owner: `Owner A`\nsecret=do-not-copy\n",
        encoding="utf-8",
    )

    assert _approval_metadata(approval) == {
        "status": "approved",
        "owner": "Owner A",
    }


def test_external_junit_path_is_redacted(tmp_path: Path) -> None:
    repo = tmp_path / "nested-repo"
    repo.mkdir()

    assert _display_path(tmp_path / "outside.xml", repo_root=repo) == (
        "<external-junit-xml>"
    )


def test_output_path_is_exclusive_and_limited_to_safe_repo_dirs(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    output_dir = repo / "output"
    docs_dir = repo / "docs"
    output_dir.mkdir(parents=True)
    docs_dir.mkdir()
    packet = {"release_eligible": False}
    safe = output_dir / "packet.json"

    assert _safe_output_path(safe, repo_root=repo) == safe.resolve()
    assert (
        write_packet_exclusive(
            output=safe,
            packet=packet,
            repo_root=repo,
        )
        == safe.resolve()
    )
    assert json.loads(safe.read_text(encoding="utf-8")) == packet
    with pytest.raises(FileExistsError):
        write_packet_exclusive(output=safe, packet=packet, repo_root=repo)
    with pytest.raises(ValueError, match="output/ or .tmp"):
        _safe_output_path(docs_dir / "packet.json", repo_root=repo)
    with pytest.raises(ValueError, match=".json"):
        _safe_output_path(output_dir / "packet.txt", repo_root=repo)


def test_cli_outputs_sanitized_json_without_running_pytest(tmp_path: Path) -> None:
    junit = tmp_path / "result.xml"
    _write_junit(junit)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--junit-xml",
            str(junit),
            "--generated-at",
            "2026-08-31T00:00:00+08:00",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    packet = json.loads(completed.stdout)
    assert packet["status"] == "blocked"
    assert packet["observation"]["counts"]["failed"] == 9
    assert "SECRET-ACTUAL-VALUE" not in completed.stdout
