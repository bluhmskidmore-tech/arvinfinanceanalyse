from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = Path("test_output/security-scans")
GITLEAKS_CONFIG = Path(".gitleaks.toml")
OSV_LOCKFILES = [
    Path("backend/uv.lock"),
    Path("frontend/package-lock.json"),
]
UNSUPPORTED_MANIFEST_CONTEXT = [
    "backend/pyproject.toml",
]


def _report_dir_path(report_dir: str | Path) -> Path:
    path = Path(report_dir)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _command_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _gitleaks_command(report_dir: Path) -> list[str]:
    return [
        "gitleaks",
        "dir",
        ".",
        "--config",
        GITLEAKS_CONFIG.as_posix(),
        "--report-format",
        "json",
        "--report-path",
        _command_path(report_dir / "gitleaks-report.json"),
        "--no-banner",
        "--redact",
    ]


def _osv_command(report_dir: Path) -> list[str]:
    command = [
        "osv-scanner",
        "scan",
        "source",
        ".",
        f"--output={_command_path(report_dir / 'osv-report.json')}",
        "--format=json",
    ]
    command.extend(
        f"--lockfile={lockfile.as_posix()}"
        for lockfile in OSV_LOCKFILES
    )
    return command


def build_scan_plan(
    *,
    tool: str = "all",
    report_dir: str | Path = DEFAULT_REPORT_DIR,
) -> dict[str, object]:
    report_path = _report_dir_path(report_dir)
    return {
        "default_tool": tool,
        "gitleaks": {
            "config": GITLEAKS_CONFIG.as_posix(),
            "report_path": _command_path(report_path / "gitleaks-report.json"),
            "command": _gitleaks_command(report_path),
        },
        "osv": {
            "lockfiles": [lockfile.as_posix() for lockfile in OSV_LOCKFILES],
            "report_path": _command_path(report_path / "osv-report.json"),
            "command": _osv_command(report_path),
        },
        "notes": {
            "unsupported_manifest_context": UNSUPPORTED_MANIFEST_CONTEXT,
            "tooling": "Install gitleaks and osv-scanner in the runner environment; this repo does not vendor the binaries.",
        },
    }


def _required_executables(tool: str) -> list[str]:
    if tool == "gitleaks":
        return ["gitleaks"]
    if tool == "osv":
        return ["osv-scanner"]
    return ["gitleaks", "osv-scanner"]


def _ensure_tools(tool: str) -> list[str]:
    return [
        executable
        for executable in _required_executables(tool)
        if shutil.which(executable) is None
    ]


def _ensure_inputs_exist() -> None:
    required = [ROOT / GITLEAKS_CONFIG, *(ROOT / lockfile for lockfile in OSV_LOCKFILES)]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required scan input(s):\n" + "\n".join(missing))


def _run_command(command: list[str], *, cwd: Path) -> int:
    completed = subprocess.run(command, cwd=cwd, check=False)
    return int(completed.returncode)


def run_scan(
    *,
    tool: str = "all",
    report_dir: str | Path = DEFAULT_REPORT_DIR,
) -> int:
    missing_tools = _ensure_tools(tool)
    if missing_tools:
        print(
            "Missing required executable(s): " + ", ".join(missing_tools),
            file=sys.stderr,
        )
        return 2

    _ensure_inputs_exist()
    resolved_report_dir = _report_dir_path(report_dir)
    resolved_report_dir.mkdir(parents=True, exist_ok=True)

    commands: list[list[str]] = []
    if tool in {"all", "gitleaks"}:
        commands.append(_gitleaks_command(resolved_report_dir))
    if tool in {"all", "osv"}:
        commands.append(_osv_command(resolved_report_dir))

    exit_code = 0
    for command in commands:
        exit_code = max(exit_code, _run_command(command, cwd=ROOT))
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tool",
        choices=["all", "gitleaks", "osv"],
        default="all",
    )
    parser.add_argument(
        "--report-dir",
        default=str(DEFAULT_REPORT_DIR),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(
            json.dumps(
                build_scan_plan(tool=args.tool, report_dir=args.report_dir),
                ensure_ascii=False,
            )
        )
        return 0

    try:
        return run_scan(tool=args.tool, report_dir=args.report_dir)
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
