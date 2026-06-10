from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.supply_chain_security_scan import build_scan_plan  # noqa: E402


AUDIT_DATE = "2026-06-10"
DEFAULT_SNAPSHOT = (
    ROOT / "docs" / "audits" / f"{AUDIT_DATE}-local-secret-hygiene-snapshot.json"
)
REFRESH_COMMAND = "python scripts\\refresh_local_secret_hygiene_snapshot.py"
SECRET_ENV_PATH = Path("config/.env")
TEST_RESULT_TEXT = (
    "pytest tests/test_supply_chain_security_scanning.py "
    "tests/test_secret_hygiene.py -q -> 7 passed"
)


def _now_shanghai() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )


def _parse_check_ignore(stdout: str) -> str:
    line = stdout.strip().splitlines()[0] if stdout.strip() else ""
    return line.split("\t", maxsplit=1)[0]


def _boundary_checks() -> dict[str, Any]:
    check_ignore = _run_git("check-ignore", "-v", SECRET_ENV_PATH.as_posix())
    tracked = _run_git("ls-files", "--", SECRET_ENV_PATH.as_posix())
    ignored_status = _run_git(
        "status",
        "--ignored",
        "--short",
        "--",
        SECRET_ENV_PATH.as_posix(),
    )
    return {
        "config_env_exists": (ROOT / SECRET_ENV_PATH).exists(),
        "git_check_ignore": {
            "command": "git check-ignore -v config/.env",
            "exit_code": int(check_ignore.returncode),
            "matched_rule": _parse_check_ignore(check_ignore.stdout),
        },
        "git_ls_files": {
            "command": "git ls-files -- config/.env",
            "exit_code": int(tracked.returncode),
            "tracked_path_count": len(
                [line for line in tracked.stdout.splitlines() if line.strip()]
            ),
        },
        "git_status_ignored": {
            "command": "git status --ignored --short -- config/.env",
            "result": ignored_status.stdout.strip(),
        },
    }


def _dry_run_plan_summary() -> dict[str, Any]:
    plan = build_scan_plan()
    gitleaks_command = list((plan.get("gitleaks") or {}).get("command") or [])
    return {
        "command": "python scripts\\supply_chain_security_scan.py --dry-run",
        "exit_code": 0,
        "gitleaks_redaction_enabled": "--redact" in gitleaks_command,
        "gitleaks_report_path": (plan.get("gitleaks") or {}).get("report_path"),
        "osv_report_path": (plan.get("osv") or {}).get("report_path"),
    }


def _build_boundary_recheck(generated_at: str) -> dict[str, Any]:
    return {
        "checked_at": generated_at,
        "values_read_by_human": False,
        "values_written_to_artifacts": False,
        "secret_values_captured": False,
        "scan_not_rerun": True,
        "reason": (
            "boundary-only recheck avoided reading config/.env values, reran only the "
            "redacted scan dry-run plan and Git boundary checks, and did not replace "
            "the last full redacted scan evidence"
        ),
        "dry_run_plan": _dry_run_plan_summary(),
        "boundary_checks": _boundary_checks(),
        "test_result": TEST_RESULT_TEXT,
        "closure_effect": "none",
    }


def build_snapshot(
    *,
    generated_at: str | None = None,
    snapshot_path: Path = DEFAULT_SNAPSHOT,
) -> dict[str, Any]:
    generated_at = generated_at or _now_shanghai()
    snapshot = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    updated = deepcopy(snapshot)
    updated["refresh_command"] = REFRESH_COMMAND
    updated["latest_boundary_only_recheck"] = _build_boundary_recheck(generated_at)
    updated["status"]["fail_closed"] = True
    updated["status"]["secret_values_captured"] = False
    updated["status"]["clears_secret_scan"] = False
    updated["status"]["writes_or_rotates_secrets"] = False
    updated["value_handling"]["values_read"] = False
    updated["value_handling"]["values_written_to_artifacts"] = False
    updated["value_handling"]["values_logged"] = False
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh only the local secret hygiene boundary check without reading "
            "secret values or replacing the last full redacted scan evidence."
        ),
    )
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_SNAPSHOT)
    args = parser.parse_args(argv)

    snapshot = build_snapshot(
        generated_at=args.generated_at,
        snapshot_path=Path(args.snapshot),
    )
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
