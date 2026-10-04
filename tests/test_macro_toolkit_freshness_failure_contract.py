from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


def _read_receipt(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_terminal_failure(
    receipt: dict[str, object],
    *,
    expected_category: str,
) -> None:
    assert receipt["status"] == "failed"
    assert receipt["exit_code"] == 1
    assert receipt["failure_category"] == expected_category
    result = receipt["result"]
    assert isinstance(result, dict)
    assert result["status"] == "failed"
    assert result["failure_category"] == expected_category
    assert result["source_version"] == "macro_toolkit_freshness_refresh_v4"
    assert isinstance(result["steps"], list)
    assert isinstance(result["latest_observation_dates"], dict)
    assert str(result["failure_message"]).strip()
    assert receipt["failure_message"] == result["failure_message"]


def test_scheduled_proxy_configuration_error_replaces_running_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    actor_called = False

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def fn(self, **_kwargs: object) -> dict[str, object]:
            nonlocal actor_called
            actor_called = True
            return {"status": "success"}

    @contextmanager
    def invalid_proxy(_source_ip: str):
        raise ValueError("source_ip 192.0.2.10 is not assigned to this host")
        yield

    receipt_path = tmp_path / "scheduled.json"
    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(cli, "_choice_source_proxy_environment", invalid_proxy)
    monkeypatch.setattr(cli, "_resolve_commit_sha", lambda: ("abc123", None))

    exit_code = cli.main(
        [
            "--run-once",
            "--run-kind",
            "scheduled",
            "--choice-source-ip",
            "192.0.2.10",
            "--receipt-path",
            str(receipt_path),
        ]
    )

    assert exit_code == 1
    assert actor_called is False
    receipt = _read_receipt(receipt_path)
    _assert_terminal_failure(
        receipt,
        expected_category="scheduler_configuration_error",
    )
    assert receipt["invocation_mode"] == "run_once"
    assert "not assigned" in str(receipt["result"]["failure_message"])


@pytest.mark.parametrize(
    ("mode", "expected_invocation_mode"),
    [
        pytest.param("--dry-run", "dry_run", id="dry-run"),
        pytest.param("--enqueue", "enqueue", id="enqueue"),
        pytest.param("--run-once", "run_once", id="run-once"),
    ],
)
def test_execution_exception_writes_generic_terminal_failure_for_every_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str,
    expected_invocation_mode: str,
) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def send(self, **_kwargs: object) -> object:
            raise RuntimeError("refresh exploded")

        def fn(self, **_kwargs: object) -> dict[str, object]:
            raise RuntimeError("refresh exploded")

    def fail_refresh(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("refresh exploded")

    receipt_path = tmp_path / f"{expected_invocation_mode}.json"
    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness", fail_refresh)
    monkeypatch.setattr(cli, "_resolve_commit_sha", lambda: (None, None))

    exit_code = cli.main([mode, "--receipt-path", str(receipt_path)])

    assert exit_code == 1
    receipt = _read_receipt(receipt_path)
    _assert_terminal_failure(
        receipt,
        expected_category="refresh_execution_failure",
    )
    assert receipt["invocation_mode"] == expected_invocation_mode


def test_timeout_exception_is_classified_as_upstream_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def fn(self, **_kwargs: object) -> dict[str, object]:
            raise TimeoutError("vendor connection timed out")

    receipt_path = tmp_path / "timeout.json"
    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(cli, "_resolve_commit_sha", lambda: (None, None))

    assert cli.main(["--run-once", "--receipt-path", str(receipt_path)]) == 1

    _assert_terminal_failure(
        _read_receipt(receipt_path),
        expected_category="upstream_unavailable",
    )


@pytest.mark.parametrize(
    ("steps", "expected_category"),
    [
        pytest.param(
            [
                {
                    "step": "choice_policy_rate_7d",
                    "status": "failed",
                    "result": {
                        "errors": {
                            "M0041653": "Choice ErrorCode=10001012: insufficient user access"
                        }
                    },
                }
            ],
            "external_dependency_pending",
            id="choice-entitlement",
        ),
        pytest.param(
            [
                {
                    "step": "public_cross_asset_headlines",
                    "status": "failed",
                    "reason": "ConnectionError: remote disconnected",
                }
            ],
            "upstream_unavailable",
            id="upstream-connection",
        ),
        pytest.param(
            [
                {
                    "step": "commodity_daily_ingest",
                    "status": "failed",
                    "reason": "unexpected result shape",
                }
            ],
            "refresh_execution_failure",
            id="generic-failure",
        ),
    ],
)
def test_actor_returned_failure_receives_stable_category(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    steps: list[dict[str, object]],
    expected_category: str,
) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def fn(self, **_kwargs: object) -> dict[str, object]:
            return {
                "status": "failed",
                "source_version": cli.SOURCE_VERSION,
                "steps": steps,
                "latest_observation_dates": {},
            }

    receipt_path = tmp_path / f"{expected_category}.json"
    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(cli, "_resolve_commit_sha", lambda: (None, None))

    assert cli.main(["--run-once", "--receipt-path", str(receipt_path)]) == 1

    receipt = _read_receipt(receipt_path)
    _assert_terminal_failure(receipt, expected_category=expected_category)
    assert receipt["result"]["steps"] == steps
    step_reason = steps[0].get("reason")
    if step_reason is not None:
        assert receipt["failure_message"] == step_reason
    else:
        assert "10001012" in str(receipt["failure_message"])


@pytest.mark.parametrize(
    "raw_result",
    [
        pytest.param({"status": "error"}, id="unexpected-status"),
        pytest.param({}, id="missing-status"),
    ],
)
def test_non_success_actor_status_is_normalized_to_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    raw_result: dict[str, object],
) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def fn(self, **_kwargs: object) -> dict[str, object]:
            return raw_result

    receipt_path = tmp_path / "non-success.json"
    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(cli, "_resolve_commit_sha", lambda: (None, None))

    assert cli.main(["--run-once", "--receipt-path", str(receipt_path)]) == 1

    _assert_terminal_failure(
        _read_receipt(receipt_path),
        expected_category="refresh_execution_failure",
    )


@pytest.mark.parametrize(
    "control_flow_exception",
    [pytest.param(KeyboardInterrupt(), id="keyboard-interrupt"), pytest.param(SystemExit(7), id="system-exit")],
)
def test_control_flow_exceptions_are_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
    control_flow_exception: BaseException,
) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def fn(self, **_kwargs: object) -> dict[str, object]:
            raise control_flow_exception

    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())

    with pytest.raises(type(control_flow_exception)):
        cli.main(["--run-once"])


def test_running_receipt_failure_still_aborts_before_business_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from scripts import macro_toolkit_freshness_refresh as cli

    actor_called = False

    class _Actor:
        actor_name = "refresh_macro_toolkit_freshness"

        def fn(self, **_kwargs: object) -> dict[str, object]:
            nonlocal actor_called
            actor_called = True
            return {"status": "success"}

    def fail_write(_path: Path, _receipt: dict[str, object]) -> None:
        raise OSError("running receipt is not writable")

    monkeypatch.setattr(cli, "refresh_macro_toolkit_freshness_actor", _Actor())
    monkeypatch.setattr(cli, "_write_receipt_atomic", fail_write)

    exit_code = cli.main(
        [
            "--run-once",
            "--run-kind",
            "scheduled",
            "--receipt-path",
            str(tmp_path / "receipt.json"),
        ]
    )

    assert exit_code == 1
    assert actor_called is False
