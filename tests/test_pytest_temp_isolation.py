from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _pytest.tmpdir import TempPathFactory


CONFTEST_PATH = Path(__file__).with_name("conftest.py").resolve()


def _temp_path_factory(given_basetemp: Path | None) -> TempPathFactory:
    return TempPathFactory(
        given_basetemp=given_basetemp,
        retention_count=3,
        retention_policy="all",
        trace=lambda *_args: None,
        _ispytest=True,
    )


def _basetemp_probe(
    workdir: Path,
    result_path: Path,
    *,
    precreate_current: bool = False,
) -> tuple[int, Path, bool]:
    probe = (
        "import os, runpy, sys\n"
        "from pathlib import Path\n"
        "current = Path.cwd() / '.codex-tmp' / f'pytest-basetemp-{os.getpid()}'\n"
        "sentinel = current / 'stale-from-reused-pid.txt'\n"
        "if sys.argv[3] == 'precreate':\n"
        "    current.mkdir(parents=True)\n"
        "    sentinel.write_text('stale', encoding='utf-8')\n"
        "runpy.run_path(sys.argv[1])\n"
        "from _pytest.tmpdir import TempPathFactory\n"
        "factory = TempPathFactory(None, 3, 'all', lambda *_args: None, _ispytest=True)\n"
        "Path(sys.argv[2]).write_text(\n"
        "    f'{os.getpid()}|{factory.getbasetemp()}|{int(sentinel.exists())}',\n"
        "    encoding='utf-8',\n"
        ")\n"
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            probe,
            str(CONFTEST_PATH),
            str(result_path),
            "precreate" if precreate_current else "clean",
        ],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    pid_text, path_text, sentinel_text = result_path.read_text(encoding="utf-8").split(
        "|", maxsplit=2
    )
    return int(pid_text), Path(path_text), sentinel_text == "1"


def test_default_pytest_basetemp_is_process_scoped(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    if request.config.option.basetemp is not None:
        pytest.skip("An explicit --basetemp intentionally overrides the process-scoped default.")

    assert tmp_path_factory.getbasetemp().name == f"pytest-basetemp-{os.getpid()}"


def test_default_pytest_basetemp_differs_across_processes(tmp_path: Path) -> None:
    probe = (
        "import os, runpy, sys\n"
        "from pathlib import Path\n"
        "runpy.run_path(sys.argv[1])\n"
        "from _pytest.tmpdir import TempPathFactory\n"
        "factory = TempPathFactory(None, 3, 'all', lambda *_args: None, _ispytest=True)\n"
        "Path(sys.argv[2]).write_text("
        "f'{os.getpid()}|{factory.getbasetemp()}', encoding='utf-8')\n"
    )
    workdir = tmp_path / "concurrent-probes"
    workdir.mkdir()
    processes: list[tuple[subprocess.Popen[str], Path]] = []
    for index in range(2):
        result_path = tmp_path / f"probe-{index}.result"
        process = subprocess.Popen(
            [sys.executable, "-c", probe, str(CONFTEST_PATH), str(result_path)],
            cwd=workdir,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        processes.append((process, result_path))

    process_roots: list[tuple[int, Path]] = []
    for process, result_path in processes:
        _stdout, stderr = process.communicate(timeout=20)
        assert process.returncode == 0, stderr
        pid_text, path_text = result_path.read_text(encoding="utf-8").split("|", maxsplit=1)
        process_roots.append((int(pid_text), Path(path_text)))

    assert len({path for _, path in process_roots}) == 2
    for pid, path in process_roots:
        assert path.name == f"pytest-basetemp-{pid}"


def test_default_pytest_basetemp_prunes_stale_dead_pid_directory(tmp_path: Path) -> None:
    workdir = tmp_path / "stale-pid"
    stale_basetemp = workdir / ".codex-tmp" / "pytest-basetemp-2147483647"
    stale_basetemp.mkdir(parents=True)
    (stale_basetemp / "stale.txt").write_text("stale", encoding="utf-8")

    _basetemp_probe(workdir, tmp_path / "stale-pid.result")

    assert not stale_basetemp.exists()


def test_default_pytest_basetemp_resets_reused_current_pid_directory(tmp_path: Path) -> None:
    workdir = tmp_path / "reused-current-pid"
    workdir.mkdir()

    pid, basetemp, stale_sentinel_survived = _basetemp_probe(
        workdir,
        tmp_path / "reused-current-pid.result",
        precreate_current=True,
    )

    assert basetemp.name == f"pytest-basetemp-{pid}"
    assert not stale_sentinel_survived


def test_default_pytest_basetemp_recreates_removed_cached_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workdir = tmp_path / "removed-cached-root"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    basetemp = _temp_path_factory(None).getbasetemp()
    shutil.rmtree(basetemp)

    replacement_factory = _temp_path_factory(None)

    assert replacement_factory.getbasetemp() == basetemp
    assert replacement_factory.mktemp("case").is_dir()


def test_default_pytest_basetemp_preserves_live_other_pid_directory(tmp_path: Path) -> None:
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import os, sys; print(os.getpid(), flush=True); sys.stdin.read(1)",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        holder_pid = int(holder.stdout.readline())
        workdir = tmp_path / "live-pid"
        live_basetemp = workdir / ".codex-tmp" / f"pytest-basetemp-{holder_pid}"
        live_basetemp.mkdir(parents=True)
        sentinel = live_basetemp / "live.txt"
        sentinel.write_text("live", encoding="utf-8")

        _basetemp_probe(workdir, tmp_path / "live-pid.result")

        assert holder.poll() is None
        assert sentinel.read_text(encoding="utf-8") == "live"
    finally:
        if holder.stdin is not None:
            holder.stdin.write("x")
            holder.stdin.flush()
        holder.wait(timeout=20)


def test_explicit_pytest_basetemp_override_is_preserved(tmp_path: Path) -> None:
    explicit_basetemp = tmp_path / "caller-selected-basetemp"

    assert _temp_path_factory(explicit_basetemp).getbasetemp() == explicit_basetemp.resolve()
