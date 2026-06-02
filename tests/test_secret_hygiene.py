from __future__ import annotations

import subprocess

from tests.helpers import ROOT


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_local_secret_env_files_are_ignored_and_untracked():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        ".env",
        ".env.*",
        "config/.env",
        "frontend/.env.local",
    ):
        assert pattern in gitignore

    ignored = _run_git("check-ignore", "-v", "config/.env")
    assert ignored.returncode == 0, ignored.stderr or ignored.stdout
    assert "config/.env" in ignored.stdout

    tracked = _run_git("ls-files", "--", "config/.env")
    assert tracked.returncode == 0, tracked.stderr
    assert tracked.stdout.strip() == ""
