from __future__ import annotations

import json

import pytest

from scripts import home_macro_release_refresh as cli

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_data,
]


class _Message:
    message_id = "message-1"


class _Actor:
    actor_name = "refresh_home_macro_release_sources"

    def __init__(self) -> None:
        self.sent = 0
        self.ran = 0
        self.sent_kwargs: dict[str, object] = {}
        self.run_kwargs: dict[str, object] = {}

    def send(self, **kwargs: object) -> _Message:
        self.sent += 1
        self.sent_kwargs = kwargs
        return _Message()

    def fn(self, **kwargs: object) -> dict[str, object]:
        self.ran += 1
        self.run_kwargs = kwargs
        return {"status": "success", "run_id": "run-1", "series": []}


def test_cli_supports_dry_run_enqueue_and_run_once(monkeypatch, capsys) -> None:
    actor = _Actor()
    monkeypatch.setattr(cli, "refresh_home_macro_release_sources_actor", actor)
    monkeypatch.setattr(
        cli,
        "refresh_home_macro_release_sources",
        lambda **kwargs: {"status": "dry_run", "run_id": "dry-1", "series": [], **kwargs},
    )

    assert cli.main(["--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "dry_run"
    assert cli.main(["--enqueue"]) == 0
    queued = json.loads(capsys.readouterr().out)
    assert queued == {
        "status": "queued",
        "actor": "refresh_home_macro_release_sources",
        "message_id": "message-1",
    }
    assert actor.sent == 1
    assert actor.sent_kwargs == {}
    assert cli.main(["--run-once"]) == 0
    assert json.loads(capsys.readouterr().out)["run_id"] == "run-1"
    assert actor.ran == 1
    assert actor.run_kwargs == {}


def test_cli_passes_validated_nbs_source_ip_to_sync_and_enqueue(
    monkeypatch,
    capsys,
) -> None:
    actor = _Actor()
    monkeypatch.setattr(cli, "refresh_home_macro_release_sources_actor", actor)
    monkeypatch.setattr(cli, "resolve_vendor_source_ip", lambda value: f"resolved:{value}")

    assert (
        cli.main(
            ["--run-once", "--nbs-inflation-source-ip", "192.0.2.10"]
        )
        == 0
    )
    capsys.readouterr()
    assert actor.run_kwargs == {"nbs_inflation_source_ip": "resolved:192.0.2.10"}

    assert (
        cli.main(
            ["--enqueue", "--nbs-inflation-source-ip", "192.0.2.10"]
        )
        == 0
    )
    capsys.readouterr()
    assert actor.sent_kwargs == {"nbs_inflation_source_ip": "resolved:192.0.2.10"}


@pytest.mark.parametrize("status", ["partial", "blocked", "error"])
def test_cli_returns_nonzero_for_non_success_terminal_status(monkeypatch, status, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "refresh_home_macro_release_sources_actor",
        type(
            "Actor",
            (),
            {"fn": staticmethod(lambda **_kwargs: {"status": status})},
        )(),
    )

    assert cli.main(["--run-once"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == status


def test_cli_requires_exactly_one_execution_mode() -> None:
    with pytest.raises(SystemExit):
        cli.main([])
    with pytest.raises(SystemExit):
        cli.main(["--dry-run", "--run-once"])
