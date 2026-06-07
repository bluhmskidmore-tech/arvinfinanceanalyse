from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE = (
    ROOT
    / "docs"
    / "plans"
    / "archive"
    / "2026-06-07-debt-cleanup"
    / "2026-06-06-deep-audit-goal-queue.md"
)


def test_done_child_goals_have_completion_records() -> None:
    text = QUEUE.read_text(encoding="utf-8")
    rows = re.findall(
        r"^\| (G\d+[a-z]?) \|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|([^|]+)\|$",
        text,
        flags=re.MULTILINE,
    )
    completed_ids = set(
        re.findall(r"^## Completed Child Goal: (G\d+[a-z]?)$", text, flags=re.MULTILINE)
    )

    done_without_record = [
        goal_id
        for goal_id, status in rows
        if status.strip().startswith("done")
        and "prior pass" not in status
        and goal_id not in completed_ids
    ]

    assert done_without_record == []


def test_release_critical_prior_pass_auth_goal_has_completion_record() -> None:
    text = QUEUE.read_text(encoding="utf-8")
    completed_ids = set(
        re.findall(r"^## Completed Child Goal: (G\d+[a-z]?)$", text, flags=re.MULTILINE)
    )

    assert "G1" in completed_ids


def test_release_critical_prior_pass_route_policy_goal_has_completion_record() -> None:
    text = QUEUE.read_text(encoding="utf-8")
    completed_ids = set(
        re.findall(r"^## Completed Child Goal: (G\d+[a-z]?)$", text, flags=re.MULTILINE)
    )

    assert "G2" in completed_ids


def test_release_critical_prior_pass_candidate_metadata_goal_has_completion_record() -> None:
    text = QUEUE.read_text(encoding="utf-8")
    completed_ids = set(
        re.findall(r"^## Completed Child Goal: (G\d+[a-z]?)$", text, flags=re.MULTILINE)
    )

    assert "G3" in completed_ids


def test_release_critical_prior_pass_route_trace_bundle_goal_has_completion_record() -> None:
    text = QUEUE.read_text(encoding="utf-8")
    completed_ids = set(
        re.findall(r"^## Completed Child Goal: (G\d+[a-z]?)$", text, flags=re.MULTILINE)
    )

    assert "G4" in completed_ids
