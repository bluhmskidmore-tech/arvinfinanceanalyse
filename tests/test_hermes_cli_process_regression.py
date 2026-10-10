from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time

import pytest

from backend.app.services import hermes_agent_service as service

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_agent_mvp]


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_cli_drains_large_output_before_process_exit(stream):
    completed = service._run_hermes_cli_with_cancel(
        args=[sys.executable, "-c", f"import sys; sys.{stream}.write('x' * 1048576)"],
        command=sys.executable,
        wsl_distro="",
        timeout_seconds=5,
        env=dict(os.environ),
        cancel_event=threading.Event(),
    )
    assert completed.returncode == 0
    assert getattr(completed, stream) == "x" * 1048576


@pytest.mark.parametrize("cancel", [True, False])
def test_cli_interrupts_real_process_while_draining_both_pipes(monkeypatch, cancel):
    popen = subprocess.Popen
    processes = []

    def tracked_popen(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(service.subprocess, "Popen", tracked_popen)
    event = threading.Event()
    timer = threading.Timer(0.2, event.set)
    if cancel:
        timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(service.HermesRuntimeError if cancel else subprocess.TimeoutExpired) as exc:
            service._run_hermes_cli_with_cancel(
                args=[sys.executable, "-c", "import sys,time; sys.stdout.write('x'*1048576); "
                      "sys.stdout.flush(); sys.stderr.write('y'*1048576); "
                      "sys.stderr.flush(); time.sleep(30)"],
                command=sys.executable,
                wsl_distro="",
                timeout_seconds=1,
                env=dict(os.environ),
                cancel_event=event,
            )
        if cancel:
            assert exc.value.error_code == "hermes_cancelled"
        assert time.monotonic() - started < 5
        assert len(processes) == 1
        assert processes[0].poll() is not None
    finally:
        timer.cancel()
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=2)


def test_two_wsl_cli_instances_have_disjoint_cleanup_targets(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service.subprocess, "run", lambda args, **kwargs: calls.append(args)
    )
    commands = [service._build_hermes_command(
        command="wsl.exe", wsl_distro="HermesUbuntu", hermes_home="", model="",
        toolsets="evidence", max_turns=1, prompt="synthetic", instance_id=instance,
    ) for instance in ["first-instance", "second-instance"]]
    for instance in ["first-instance", "second-instance"]:
        service._cleanup_wsl_cli_instance(
            command="wsl.exe", wsl_distro="HermesUbuntu", instance_id=instance,
        )
    assert commands[0] != commands[1]
    for command in commands:
        offset = command.index("setsid")
        assert command[offset:offset + 3] == ["setsid", "--wait", "env"]
    assert "MOSS_HERMES_CLI_INSTANCE=first-instance" in commands[0]
    assert "MOSS_HERMES_CLI_INSTANCE=second-instance" in commands[1]
    assert calls[0][-1] == "first-instance"
    assert calls[1][-1] == "second-instance"
    assert all("pkill" not in args for args in calls)

    # Execute the exact cleanup program against a synthetic /proc inventory.
    # No subprocess or real signal is used here.
    class Entry:
        def __init__(self, pid, instance):
            self.name, self.instance = str(pid), instance

        def __truediv__(self, _name):
            return self

        def read_bytes(self):
            return f"MOSS_HERMES_CLI_INSTANCE={self.instance}\0".encode()

    entries = [Entry(10, "first-instance"), Entry(11, "first-instance"),
               Entry(20, "second-instance")]
    killed = []
    monkeypatch.setattr("pathlib.Path.iterdir", lambda _path: iter(entries))
    monkeypatch.setattr(os, "getpgid", lambda pid: 10 if pid in {10, 11} else 20, raising=False)
    monkeypatch.setattr(os, "killpg", lambda pid, _sig: killed.append(pid), raising=False)
    monkeypatch.setattr(signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(sys, "argv", ["cleanup", *calls[0][-2:]])
    exec(calls[0][calls[0].index("-c") + 1], {})
    assert killed == [10]
    killed.clear()
    monkeypatch.setattr(sys, "argv", ["cleanup", *calls[1][-2:]])
    exec(calls[1][calls[1].index("-c") + 1], {})
    assert killed == [20]


def test_cli_cleanup_without_instance_never_calls_external_command(monkeypatch):
    monkeypatch.setattr(service.subprocess, "run", lambda *a, **kw: pytest.fail("cleanup ran"))
    service._cleanup_wsl_cli_instance(command="wsl.exe", wsl_distro="", instance_id="")
    service._cleanup_wsl_processes(command="wsl.exe", wsl_distro="", pattern="")
