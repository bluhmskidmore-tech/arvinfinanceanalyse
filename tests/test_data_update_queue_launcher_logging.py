from __future__ import annotations

import os
import json
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "scripts" / "scheduling" / "drain_data_updates.ps1"
UTF8_BOM = b"\xef\xbb\xbf"


def _powershell() -> str:
    executable = shutil.which("powershell.exe") or shutil.which("powershell")
    if executable is None:
        pytest.skip("Windows PowerShell is required for this launcher test")
    return executable


def _prepare_isolated_repo(
    tmp_path: Path, *, python_layout: str | None = "root"
) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scheduling = scripts / "scheduling"
    scheduling.mkdir(parents=True)
    launcher = scheduling / LAUNCHER.name
    launcher.write_bytes(LAUNCHER.read_bytes())

    if python_layout is not None:
        python_dir = (
            repo
            / ("backend/.venv" if python_layout == "backend" else ".venv")
            / "Scripts"
        )
        python_dir.mkdir(parents=True)
        (python_dir / "python.exe").write_bytes(b"")

    (scripts / "dev-runtime-common.ps1").write_text(
        """
function Assert-DevRuntimeAllowed {
  if ($env:TEST_FAILURE_STAGE -eq "guard") {
    $message = -join ([char[]]@(0x5B88, 0x62A4, 0x68C0, 0x67E5, 0x5931, 0x8D25))
    throw $message
  }
}

function Invoke-DevRuntimeProcess {
  param([Parameter(Mandatory = $true)][string[]]$Command)
  $payload = @{ argv = @($Command); path = $env:PATH } | ConvertTo-Json -Compress
  [IO.File]::WriteAllText($env:TEST_COMMAND_CAPTURE, $payload, [Text.UTF8Encoding]::new($false))
  & $env:TEST_POWERSHELL -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $env:TEST_WORKER_SCRIPT
  if ($LASTEXITCODE -ne 0) {
    throw "Guarded runtime process exited with code $LASTEXITCODE"
  }
}
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    (scripts / "dev-env.ps1").write_text(
        """
if ($env:TEST_FAILURE_STAGE -eq "startup") {
  $message = -join ([char[]]@(0x542F, 0x52A8, 0x5931, 0x8D25))
  throw $message
}
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    worker = tmp_path / "fake-worker.ps1"
    worker.write_text(
        """
[IO.File]::WriteAllText($env:TEST_WORKER_MARKER, "ran", [Text.UTF8Encoding]::new($false))
$stdout = -join ([char[]]@(0x4E2D, 0x6587, 0x6807, 0x51C6, 0x8F93, 0x51FA))
$stderr = -join ([char[]]@(0x4E2D, 0x6587, 0x6807, 0x51C6, 0x9519, 0x8BEF))
if ($env:TEST_LOCK_LOG_DURING_OUTPUT -eq "1") {
  $queueLogPath = [IO.Directory]::GetFiles($env:TEST_QUEUE_LOG_DIRECTORY, "data-update-queue-*.log")[0]
  $lease = [IO.File]::Open($queueLogPath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
  try {
    [Console]::Out.WriteLine($stdout)
    Start-Sleep -Milliseconds 300
  } finally {
    $lease.Dispose()
  }
  exit 0
}
if (-not [string]::IsNullOrWhiteSpace($env:TEST_SECRET_TEXT)) {
  [Console]::Error.WriteLine($env:TEST_SECRET_TEXT)
}
[Console]::Out.WriteLine($stdout)
[Console]::Error.WriteLine($stderr)
exit [int]$env:TEST_WORKER_EXIT_CODE
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    return launcher, worker


def _run_launcher(
    tmp_path: Path,
    *,
    worker_exit_code: int = 0,
    failure_stage: str = "",
    make_log_path_unwritable: bool = False,
    lock_log_during_output: bool = False,
    secret_text: str = "",
    python_layout: str | None = "root",
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    launcher, worker = _prepare_isolated_repo(tmp_path, python_layout=python_layout)
    marker = tmp_path / "worker-ran.txt"
    log_directory = launcher.parent / "logs"
    if make_log_path_unwritable:
        log_directory.write_text("not a directory", encoding="ascii")

    env = os.environ.copy()
    env.update(
        {
            "TEST_FAILURE_STAGE": failure_stage,
            "TEST_POWERSHELL": _powershell(),
            "TEST_WORKER_EXIT_CODE": str(worker_exit_code),
            "TEST_WORKER_MARKER": str(marker),
            "TEST_WORKER_SCRIPT": str(worker),
            "TEST_LOCK_LOG_DURING_OUTPUT": "1" if lock_log_during_output else "0",
            "TEST_QUEUE_LOG_DIRECTORY": str(log_directory),
            "TEST_SECRET_TEXT": secret_text,
            "TEST_COMMAND_CAPTURE": str(tmp_path / "command.json"),
        }
    )
    completed = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(launcher),
        ],
        cwd=launcher.parents[2],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed, log_directory, marker


@pytest.mark.parametrize("python_layout", ["root", "backend"])
def test_launcher_selects_repo_python_and_module_without_running_real_worker(
    tmp_path: Path, python_layout: str
) -> None:
    completed, _, marker = _run_launcher(tmp_path, python_layout=python_layout)

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert marker.exists()
    captured = json.loads((tmp_path / "command.json").read_text(encoding="utf-8"))
    venv = "backend/.venv" if python_layout == "backend" else ".venv"
    expected = tmp_path / "repo" / venv / "Scripts" / "python.exe"
    assert captured["argv"] == [
        str(expected),
        "-m",
        "backend.app.tasks.data_update_center",
    ]
    assert captured["path"].split(os.pathsep)[0] == str(expected.parent)


def test_launcher_fails_before_worker_when_repo_python_is_missing(
    tmp_path: Path,
) -> None:
    completed, log_directory, marker = _run_launcher(tmp_path, python_layout=None)

    assert completed.returncode == 1
    assert not marker.exists()
    assert not (tmp_path / "command.json").exists()
    _, text = _read_single_log(log_directory)
    assert "stage=startup status=failed" in text
    assert "Repository Python not found" in text


def _read_single_log(log_directory: Path) -> tuple[bytes, str]:
    logs = list(log_directory.glob("data-update-queue-*.log"))
    assert len(logs) == 1
    raw = logs[0].read_bytes()
    return raw, raw.decode("utf-8")


def test_launcher_logs_success_and_preserves_chinese_streams(tmp_path: Path) -> None:
    completed, log_directory, marker = _run_launcher(tmp_path)

    raw, text = _read_single_log(log_directory)
    assert completed.returncode == 0
    assert marker.exists()
    assert not raw.startswith(UTF8_BOM)
    assert "stream=stdout \u4e2d\u6587\u6807\u51c6\u8f93\u51fa" in text
    assert "stream=stderr \u4e2d\u6587\u6807\u51c6\u9519\u8bef" in text
    assert "exit_code=0" in text


def test_launcher_preserves_worker_nonzero_exit_code(tmp_path: Path) -> None:
    completed, log_directory, marker = _run_launcher(tmp_path, worker_exit_code=7)

    _, text = _read_single_log(log_directory)
    assert completed.returncode == 7
    assert marker.exists()
    assert "Guarded runtime process exited with code 7" in text
    assert "exit_code=7" in text


@pytest.mark.parametrize(
    ("failure_stage", "expected_message"),
    [
        ("guard", "\u5b88\u62a4\u68c0\u67e5\u5931\u8d25"),
        ("startup", "\u542f\u52a8\u5931\u8d25"),
    ],
)
def test_launcher_logs_guard_and_startup_failures(
    tmp_path: Path, failure_stage: str, expected_message: str
) -> None:
    completed, log_directory, marker = _run_launcher(
        tmp_path, failure_stage=failure_stage
    )

    _, text = _read_single_log(log_directory)
    assert completed.returncode == 1
    assert not marker.exists()
    assert expected_message in text
    assert "exit_code=1" in text


def test_launcher_does_not_run_worker_when_log_cannot_be_created(
    tmp_path: Path,
) -> None:
    completed, _, marker = _run_launcher(tmp_path, make_log_path_unwritable=True)

    assert completed.returncode != 0
    assert not marker.exists()


def test_launcher_reports_failure_when_output_logging_fails_mid_run(
    tmp_path: Path,
) -> None:
    completed, log_directory, marker = _run_launcher(
        tmp_path, lock_log_during_output=True
    )

    _, text = _read_single_log(log_directory)
    assert completed.returncode == 1
    assert marker.exists()
    assert "status=failed failure_kind=log_write exit_code=1" in text
    assert "status=completed" not in text


def test_launcher_redacts_credentials_from_worker_output(tmp_path: Path) -> None:
    secret = "postgresql://moss:topsecret@localhost/db MOSS_TOKEN=hunter2"
    completed, log_directory, _ = _run_launcher(tmp_path, secret_text=secret)

    _, text = _read_single_log(log_directory)
    assert completed.returncode == 0
    assert "topsecret" not in text
    assert "hunter2" not in text
    assert "postgresql://moss:***@localhost/db MOSS_TOKEN=***" in text
