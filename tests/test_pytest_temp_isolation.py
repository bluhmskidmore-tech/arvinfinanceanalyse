from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from _pytest.tmpdir import TempPathFactory


def _temp_path_factory(given_basetemp: Path | None) -> TempPathFactory:
    return TempPathFactory(
        given_basetemp=given_basetemp,
        retention_count=3,
        retention_policy="all",
        trace=lambda *_args: None,
        _ispytest=True,
    )


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
        "runpy.run_path('tests/conftest.py')\n"
        "from _pytest.tmpdir import TempPathFactory\n"
        "factory = TempPathFactory(None, 3, 'all', lambda *_args: None, _ispytest=True)\n"
        "Path(sys.argv[1]).write_text("
        "f'{os.getpid()}|{factory.getbasetemp()}', encoding='utf-8')\n"
    )
    repo_root = Path(__file__).resolve().parents[1]
    processes: list[tuple[subprocess.Popen[bytes], Path]] = []
    for index in range(2):
        result_path = tmp_path / f"probe-{index}.result"
        process = subprocess.Popen(
            [sys.executable, "-c", probe, str(result_path)],
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes.append((process, result_path))

    process_roots: list[tuple[int, Path]] = []
    for process, result_path in processes:
        process.wait(timeout=20)
        assert process.returncode == 0
        pid_text, path_text = result_path.read_text(encoding="utf-8").split("|", maxsplit=1)
        process_roots.append((int(pid_text), Path(path_text)))

    assert len({path for _, path in process_roots}) == 2
    for pid, path in process_roots:
        assert path.name == f"pytest-basetemp-{pid}"


def test_explicit_pytest_basetemp_override_is_preserved(tmp_path: Path) -> None:
    explicit_basetemp = tmp_path / "caller-selected-basetemp"

    assert _temp_path_factory(explicit_basetemp).getbasetemp() == explicit_basetemp.resolve()
