from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_market_data,
]

_SOURCE_IP = "192.0.2.10"
_TOKEN = "synthetic-secret-token"
_DATE = "2026-09-15"
_COMPACT_DATE = "20260915"


@pytest.fixture
def supplier_check(monkeypatch: pytest.MonkeyPatch):
    import _duckdb
    import duckdb

    database_calls: list[tuple[object, ...]] = []

    def forbidden_database_connect(*args: object, **kwargs: object) -> None:
        database_calls.append((*args, kwargs))
        raise AssertionError("supplier access check must not open DuckDB")

    monkeypatch.setattr(duckdb, "connect", forbidden_database_connect)
    monkeypatch.setattr(_duckdb, "connect", forbidden_database_connect)

    network = importlib.import_module("backend.app.network.source_bound_socks_proxy")
    monkeypatch.setattr(network, "is_bindable_ipv4", lambda _value: True)
    access = importlib.import_module("scripts.check_stock_supplier_access")
    materialize = importlib.import_module("backend.app.tasks.choice_stock_materialize")
    choice_cli = importlib.import_module("scripts.choice_stock_daily_refresh")
    business_calls: list[str] = []

    def forbidden_business_call(name: str):
        def forbidden(*_args: object, **_kwargs: object) -> None:
            business_calls.append(name)
            raise AssertionError(f"supplier access check called forbidden business surface: {name}")

        return forbidden

    for name in (
        "_latest_refresh_record",
        "choice_stock_refresh_status",
        "default_choice_stock_refresh_as_of_date",
        "latest_choice_stock_inflight_refresh",
        "run_choice_stock_refresh",
        "_write_receipt_atomic",
        "build_supply_freshness_report",
        "compute_and_materialize_gate_supplement",
        "sync_livermore_position_snapshot",
    ):
        assert callable(getattr(choice_cli, name))
        monkeypatch.setattr(choice_cli, name, forbidden_business_call(name))
    assert callable(materialize.get_runtime_cache)
    monkeypatch.setattr(
        materialize,
        "get_runtime_cache",
        forbidden_business_call("get_runtime_cache"),
    )
    monkeypatch.setattr(materialize, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        materialize,
        "resolve_tushare_token_with_settings_fallback",
        lambda _settings: _TOKEN,
    )
    yield access, materialize, database_calls
    assert database_calls == []
    assert business_calls == []


def _response(payload: object, *, status_code: int = 200) -> object:
    class FakeResponse:
        history: list[object] = []

        def __init__(self) -> None:
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                import requests

                raise requests.HTTPError("sensitive raw HTTP failure")

        def json(self) -> object:
            return payload

    return FakeResponse()


def _install_fake_post(
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
    *,
    raises: BaseException | None = None,
    status_code: int = 200,
) -> list[dict[str, object]]:
    import requests

    calls: list[dict[str, object]] = []

    def fake_post(
        url: str,
        *,
        json: dict[str, object],
        timeout: object,
        allow_redirects: bool,
        verify: bool,
    ) -> object:
        calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
                "allow_redirects": allow_redirects,
                "verify": verify,
            }
        )
        if raises is not None:
            raise raises
        return _response(payload, status_code=status_code)

    monkeypatch.setattr(requests, "post", fake_post)
    return calls


def _run(
    access: object,
    capsys: pytest.CaptureFixture[str],
    *arguments: str,
) -> tuple[int, dict[str, object], str]:
    exit_code = access.main(list(arguments))
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out), captured.err


def _success_payload(fields: list[str], items: list[list[object]]) -> dict[str, object]:
    return {"code": 0, "msg": "", "data": {"fields": fields, "items": items}}


@pytest.mark.parametrize(
    ("is_open", "expected_state"),
    [
        (0, "matched"),
        (1, "matched"),
        ("0", "matched"),
        ("1", "matched"),
        (True, "invalid_schema"),
        (False, "invalid_schema"),
        (1.0, "invalid_schema"),
        (2, "invalid_schema"),
        (None, "invalid_schema"),
    ],
)
def test_trade_calendar_accepts_vendor_integer_flag_without_coercing_invalid_values(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    is_open: object,
    expected_state: str,
) -> None:
    access, _materialize, _database_calls = supplier_check
    calls = _install_fake_post(
        monkeypatch,
        _success_payload(["cal_date", "is_open"], [[_COMPACT_DATE, is_open]]),
    )
    exit_code, output, stderr = _run(
        access, capsys, "--as-of-date", _DATE, "--vendor-source-ip", _SOURCE_IP,
    )
    assert output["state"] == expected_state
    assert output["count"] == (1 if expected_state == "matched" else None)
    assert exit_code == (0 if expected_state == "matched" else 1)
    assert stderr == ""
    assert len(calls) == 1


def test_trade_calendar_uses_one_exact_https_request_and_restores_scope(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    access, _materialize, _database_calls = supplier_check
    calls = _install_fake_post(
        monkeypatch,
        _success_payload(["cal_date", "is_open"], [[_COMPACT_DATE, "1"]]),
    )
    import urllib3.util.connection as urllib3_connection

    socket_create_connection = socket.create_connection
    urllib3_create_connection = urllib3_connection.create_connection
    previous_proxy_host = os.environ.get("CHOICE_MACRO_SOCKS5_PROXY_HOST")
    previous_proxy_port = os.environ.get("CHOICE_MACRO_SOCKS5_PROXY_PORT")

    exit_code, output, stderr = _run(
        access,
        capsys,
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
    )

    assert exit_code == 0
    assert stderr == ""
    assert output == {
        "state": "matched",
        "date": _DATE,
        "count": 1,
        "elapsed": output["elapsed"],
        "error_class": None,
    }
    assert isinstance(output["elapsed"], int) and output["elapsed"] >= 0
    assert calls == [
        {
            "url": "https://api.tushare.pro",
            "json": {
                "api_name": "trade_cal",
                "token": _TOKEN,
                "params": {
                    "exchange": "SSE",
                    "start_date": _COMPACT_DATE,
                    "end_date": _COMPACT_DATE,
                },
                "fields": "cal_date,is_open",
            },
            "timeout": (10.0, 30.0),
            "allow_redirects": False,
            "verify": True,
        }
    ]
    assert socket.create_connection is socket_create_connection
    assert urllib3_connection.create_connection is urllib3_create_connection
    assert os.environ.get("CHOICE_MACRO_SOCKS5_PROXY_HOST") == previous_proxy_host
    assert os.environ.get("CHOICE_MACRO_SOCKS5_PROXY_PORT") == previous_proxy_port


def test_daily_basic_uses_exact_ticker_date_and_fields(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    access, _materialize, _database_calls = supplier_check
    ticker = "600000.SH"
    calls = _install_fake_post(
        monkeypatch,
        _success_payload(["ts_code", "trade_date"], [[ticker, _COMPACT_DATE]]),
    )

    exit_code, output, stderr = _run(
        access,
        capsys,
        "--operation",
        "daily_basic",
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
        "--ticker",
        ticker,
    )

    assert exit_code == 0
    assert stderr == ""
    assert output["state"] == "matched"
    assert output["count"] == 1
    assert calls[0]["json"] == {
        "api_name": "daily_basic",
        "token": _TOKEN,
        "params": {"ts_code": ticker, "trade_date": _COMPACT_DATE},
        "fields": "ts_code,trade_date",
    }


@pytest.mark.parametrize(
    ("arguments", "expected_state"),
    [
        (("--as-of-date", "20260915", "--vendor-source-ip", _SOURCE_IP), "input_error"),
        (("--as-of-date", _DATE, "--vendor-source-ip", "auto"), "input_error"),
        (
            (
                "--operation",
                "daily_basic",
                "--as-of-date",
                _DATE,
                "--vendor-source-ip",
                _SOURCE_IP,
            ),
            "input_error",
        ),
        (
            (
                "--operation",
                "daily_basic",
                "--as-of-date",
                _DATE,
                "--vendor-source-ip",
                _SOURCE_IP,
                "--ticker",
                "600000.sh",
            ),
            "input_error",
        ),
        (
            (
                "--as-of-date",
                _DATE,
                "--vendor-source-ip",
                _SOURCE_IP,
                "--ticker",
                "600000.SH",
            ),
            "input_error",
        ),
        (("--as-of-date",), "input_error"),
        (("--help",), "input_error"),
        (
            (
                "--oper",
                "daily_basic",
                "--as-of-date",
                _DATE,
                "--vendor-source-ip",
                _SOURCE_IP,
                "--ticker",
                "600000.SH",
            ),
            "input_error",
        ),
    ],
)
def test_invalid_parameters_fail_before_network(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: tuple[str, ...],
    expected_state: str,
) -> None:
    access, _materialize, _database_calls = supplier_check
    calls = _install_fake_post(monkeypatch, _success_payload([], []))

    exit_code, output, stderr = _run(access, capsys, *arguments)

    assert exit_code != 0
    assert stderr == ""
    assert output["state"] == expected_state
    assert output["count"] is None
    assert calls == []


@pytest.mark.parametrize(
    ("payload", "expected_state", "expected_count"),
    [
        ([], "invalid_schema", None),
        ({"msg": "", "data": {}}, "invalid_schema", None),
        ({"code": False, "msg": "", "data": {}}, "invalid_schema", None),
        ({"code": "0", "msg": "", "data": {}}, "invalid_schema", None),
        ({"code": 0, "msg": "", "data": None}, "invalid_schema", None),
        (_success_payload(["cal_date"], []), "invalid_schema", None),
        (_success_payload(["cal_date", "is_open"], []), "empty", 0),
        (
            _success_payload(["cal_date", "is_open"], [[None, "1"]]),
            "invalid_date",
            None,
        ),
        (
            _success_payload(["cal_date", "is_open"], [[{"bad": "value"}, "1"]]),
            "invalid_schema",
            None,
        ),
        (
            _success_payload(["cal_date", "is_open"], [[_COMPACT_DATE, ["1"]]]),
            "invalid_schema",
            None,
        ),
        (
            _success_payload(["cal_date", "is_open"], [["20260914", "1"]]),
            "invalid_date",
            None,
        ),
        (
            _success_payload(
                ["cal_date", "is_open"],
                [[_COMPACT_DATE, "1"], [_COMPACT_DATE, "1"]],
            ),
            "duplicate_rows",
            None,
        ),
        (
            _success_payload(
                ["cal_date", "is_open"],
                [[_COMPACT_DATE, "0"], [_COMPACT_DATE, "1"]],
            ),
            "excess_rows",
            None,
        ),
    ],
)
def test_trade_calendar_response_validation_is_fail_closed(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payload: object,
    expected_state: str,
    expected_count: int | None,
) -> None:
    access, _materialize, _database_calls = supplier_check
    calls = _install_fake_post(monkeypatch, payload)

    exit_code, output, stderr = _run(
        access,
        capsys,
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
    )

    assert exit_code == (0 if expected_state == "empty" else 1)
    assert stderr == ""
    assert output["state"] == expected_state
    assert output["count"] == expected_count
    assert len(calls) == 1


def test_daily_basic_wrong_ticker_is_invalid_identity(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    access, _materialize, _database_calls = supplier_check
    _install_fake_post(
        monkeypatch,
        _success_payload(["ts_code", "trade_date"], [["000001.SZ", _COMPACT_DATE]]),
    )

    exit_code, output, _stderr = _run(
        access,
        capsys,
        "--operation",
        "daily_basic",
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
        "--ticker",
        "600000.SH",
    )

    assert exit_code == 1
    assert output["state"] == "invalid_identity"
    assert output["count"] is None


@pytest.mark.parametrize(
    ("failure_factory", "expected_state", "expected_error_class"),
    [
        (lambda requests: requests.Timeout("raw timeout with secret"), "transport_failure", "Timeout"),
        (
            lambda requests: requests.exceptions.SSLError("raw TLS with secret"),
            "transport_failure",
            "SSLError",
        ),
        (
            lambda requests: requests.ConnectionError("raw connection with secret"),
            "transport_failure",
            "ConnectionError",
        ),
    ],
)
def test_transport_failures_are_classified_without_sensitive_output(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure_factory: Callable[[object], BaseException],
    expected_state: str,
    expected_error_class: str,
) -> None:
    import requests

    access, _materialize, _database_calls = supplier_check
    failure = failure_factory(requests)
    _install_fake_post(monkeypatch, _success_payload([], []), raises=failure)

    exit_code, output, stderr = _run(
        access,
        capsys,
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
    )

    rendered = json.dumps(output, ensure_ascii=False) + stderr
    assert exit_code == 1
    assert output["state"] == expected_state
    assert output["count"] is None
    assert output["error_class"] == expected_error_class
    assert _TOKEN not in rendered
    assert _SOURCE_IP not in rendered
    assert str(failure) not in rendered


def test_supplier_error_does_not_leak_raw_response(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    access, _materialize, _database_calls = supplier_check
    sensitive = f"quota detail {_TOKEN} {_SOURCE_IP}"
    calls = _install_fake_post(
        monkeypatch,
        {"code": 40203, "msg": sensitive, "data": None},
    )

    exit_code, output, stderr = _run(
        access,
        capsys,
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
    )

    rendered = json.dumps(output, ensure_ascii=False) + stderr
    assert exit_code == 1
    assert output["state"] == "supplier_failure"
    assert output["count"] is None
    assert output["error_class"] == "RuntimeError"
    assert sensitive not in rendered
    assert len(calls) == 1


def test_redirect_is_rejected_without_following_or_leaking(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    access, _materialize, _database_calls = supplier_check
    calls = _install_fake_post(
        monkeypatch,
        {"location": f"https://redirect.invalid/{_TOKEN}/{_SOURCE_IP}"},
        status_code=302,
    )

    exit_code, output, stderr = _run(
        access,
        capsys,
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
    )

    rendered = json.dumps(output, ensure_ascii=False) + stderr
    assert exit_code == 1
    assert output["state"] == "supplier_failure"
    assert output["count"] is None
    assert output["error_class"] == "RedirectRejected"
    assert _TOKEN not in rendered
    assert _SOURCE_IP not in rendered
    assert len(calls) == 1


def test_second_http_exchange_is_rejected_and_post_is_restored(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import requests

    access, _materialize, _database_calls = supplier_check
    calls = _install_fake_post(
        monkeypatch,
        _success_payload(["cal_date", "is_open"], [[_COMPACT_DATE, "1"]]),
    )
    fake_post = requests.post

    with pytest.raises(access._RepeatedHttpExchange):
        with access._single_http_exchange():
            requests.post("https://api.tushare.pro", json={}, timeout=(10.0, 30.0))
            requests.post("https://api.tushare.pro", json={}, timeout=(10.0, 30.0))

    assert len(calls) == 1
    assert requests.post is fake_post


def test_missing_credential_and_binding_failure_are_distinct_and_redacted(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    access, materialize, _database_calls = supplier_check
    calls = _install_fake_post(monkeypatch, _success_payload([], []))
    monkeypatch.setattr(
        materialize,
        "resolve_tushare_token_with_settings_fallback",
        lambda _settings: "",
    )

    credential_exit, credential_output, credential_stderr = _run(
        access,
        capsys,
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
    )

    assert credential_exit == 1
    assert credential_output["state"] == "credential_error"
    assert credential_output["count"] is None
    assert credential_stderr == ""
    assert calls == []

    import scripts.choice_stock_daily_refresh as choice_cli

    monkeypatch.setattr(
        choice_cli,
        "resolve_vendor_source_ip",
        lambda _value: (_ for _ in ()).throw(ValueError(f"unassigned {_SOURCE_IP} {_TOKEN}")),
    )
    binding_exit, binding_output, binding_stderr = _run(
        access,
        capsys,
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
    )

    rendered = json.dumps(binding_output) + binding_stderr
    assert binding_exit == 1
    assert binding_output["state"] == "binding_error"
    assert binding_output["count"] is None
    assert _SOURCE_IP not in rendered
    assert _TOKEN not in rendered
    assert calls == []


def test_output_contract_never_claims_pretrade_readiness(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    access, _materialize, _database_calls = supplier_check
    _install_fake_post(
        monkeypatch,
        _success_payload(["cal_date", "is_open"], [[_COMPACT_DATE, "1"]]),
    )

    _exit_code, output, _stderr = _run(
        access,
        capsys,
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
    )

    assert set(output) == {"state", "date", "count", "elapsed", "error_class"}
    assert "ready" not in json.dumps(output).lower()


def test_unexpected_lazy_import_failure_is_redacted_to_five_fields(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    access, _materialize, _database_calls = supplier_check
    sensitive = f"import failure {_TOKEN} {_SOURCE_IP}"

    def fail_run_check(*_args: object, **_kwargs: object) -> None:
        raise ImportError(sensitive)

    monkeypatch.setattr(access, "_run_check", fail_run_check)

    exit_code, output, stderr = _run(
        access,
        capsys,
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
    )

    rendered = json.dumps(output) + stderr
    assert exit_code == 1
    assert output["state"] == "unknown_failure"
    assert output["error_class"] == "ImportError"
    assert set(output) == {"state", "date", "count", "elapsed", "error_class"}
    assert sensitive not in rendered


def test_failure_restores_socket_environment_and_http_scope(
    supplier_check,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import requests
    import urllib3.util.connection as urllib3_connection

    access, _materialize, _database_calls = supplier_check
    _install_fake_post(
        monkeypatch,
        _success_payload([], []),
        raises=requests.Timeout(f"sensitive {_TOKEN} {_SOURCE_IP}"),
    )
    fake_post = requests.post
    socket_create_connection = socket.create_connection
    urllib3_create_connection = urllib3_connection.create_connection
    previous_proxy_host = os.environ.get("CHOICE_MACRO_SOCKS5_PROXY_HOST")
    previous_proxy_port = os.environ.get("CHOICE_MACRO_SOCKS5_PROXY_PORT")

    exit_code, output, _stderr = _run(
        access,
        capsys,
        "--as-of-date",
        _DATE,
        "--vendor-source-ip",
        _SOURCE_IP,
    )

    assert exit_code == 1
    assert output["state"] == "transport_failure"
    assert requests.post is fake_post
    assert socket.create_connection is socket_create_connection
    assert urllib3_connection.create_connection is urllib3_create_connection
    assert os.environ.get("CHOICE_MACRO_SOCKS5_PROXY_HOST") == previous_proxy_host
    assert os.environ.get("CHOICE_MACRO_SOCKS5_PROXY_PORT") == previous_proxy_port


def test_fresh_process_runs_real_diagnostic_with_all_side_effect_spies() -> None:
    code = "\n".join(
        [
            "import contextlib, importlib, io, json, sys",
            "from types import SimpleNamespace",
            "import _pytest_duckdb_guard",
            "import _duckdb",
            "import duckdb",
            "targets = [",
            "  'backend.app.tasks.choice_stock_materialize',",
            "  'scripts.choice_stock_daily_refresh',",
            "]",
            "assert all(name not in sys.modules for name in targets)",
            "calls = []",
            "def forbidden(*args, **kwargs):",
            "  calls.append(1)",
            "  raise AssertionError('DuckDB open during helper import')",
            "duckdb.connect = forbidden",
            "_duckdb.connect = forbidden",
            "network = importlib.import_module('backend.app.network.source_bound_socks_proxy')",
            "network.is_bindable_ipv4 = lambda value: True",
            "access = importlib.import_module('scripts.check_stock_supplier_access')",
            "materialize = importlib.import_module('backend.app.tasks.choice_stock_materialize')",
            "choice_cli = importlib.import_module('scripts.choice_stock_daily_refresh')",
            "business_calls = []",
            "def forbid_business(name):",
            "  def forbidden(*args, **kwargs):",
            "    business_calls.append(name)",
            "    raise AssertionError('forbidden business surface: ' + name)",
            "  return forbidden",
            "business_names = [",
            "  '_latest_refresh_record',",
            "  'choice_stock_refresh_status',",
            "  'default_choice_stock_refresh_as_of_date',",
            "  'latest_choice_stock_inflight_refresh',",
            "  'run_choice_stock_refresh',",
            "  '_write_receipt_atomic',",
            "  'build_supply_freshness_report',",
            "  'compute_and_materialize_gate_supplement',",
            "  'sync_livermore_position_snapshot',",
            "]",
            "for name in business_names:",
            "  assert callable(getattr(choice_cli, name))",
            "  setattr(choice_cli, name, forbid_business(name))",
            "assert callable(materialize.get_runtime_cache)",
            "materialize.get_runtime_cache = forbid_business('get_runtime_cache')",
            "materialize.get_settings = lambda: SimpleNamespace()",
            f"materialize.resolve_tushare_token_with_settings_fallback = lambda settings: {_TOKEN!r}",
            "http_calls = []",
            "class Response:",
            "  status_code = 200",
            "  def raise_for_status(self): return None",
            "  def json(self):",
            "    return {'code': 0, 'msg': '', 'data': {",
            "      'fields': ['ts_code', 'trade_date'],",
            "      'items': [['000001.SZ', '20260915']],",
            "    }}",
            "def fake_post(url, *, json, timeout, allow_redirects, verify):",
            "  http_calls.append(1)",
            "  assert url == 'https://api.tushare.pro'",
            "  assert json['api_name'] == 'daily_basic'",
            "  assert json['params'] == {'ts_code': '000001.SZ', 'trade_date': '20260915'}",
            "  assert json['fields'] == 'ts_code,trade_date'",
            "  assert timeout == (10.0, 30.0)",
            "  assert allow_redirects is False and verify is True",
            "  return Response()",
            "import requests",
            "requests.post = fake_post",
            "stdout = io.StringIO()",
            "with contextlib.redirect_stdout(stdout):",
            "  exit_code = access.main([",
            "    '--operation', 'daily_basic',",
            "    '--as-of-date', '2026-09-15',",
            "    '--vendor-source-ip', '192.0.2.10',",
            "    '--ticker', '000001.SZ',",
            "  ])",
            "output = json.loads(stdout.getvalue())",
            "print(json.dumps({",
            "  'exit_code': exit_code,",
            "  'state': output['state'],",
            "  'count': output['count'],",
            "  'database_calls': len(calls),",
            "  'business_calls': business_calls,",
            "  'http_calls': len(http_calls),",
            "}))",
        ]
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.fspath(Path(__file__).resolve().parents[1]),
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "exit_code": 0,
        "state": "matched",
        "count": 1,
        "database_calls": 0,
        "business_calls": [],
        "http_calls": 1,
    }


def test_direct_script_invocation_returns_only_contract_for_invalid_input() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            os.fspath(repo_root / "scripts" / "check_stock_supplier_access.py"),
            "--as-of-date",
            _DATE,
            "--vendor-source-ip",
            "auto",
        ],
        cwd=os.fspath(repo_root),
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert completed.returncode == 1
    assert completed.stderr == ""
    output = json.loads(completed.stdout)
    assert set(output) == {"state", "date", "count", "elapsed", "error_class"}
    assert output["state"] == "input_error"
    assert output["count"] is None
