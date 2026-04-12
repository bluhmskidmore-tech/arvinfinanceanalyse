from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.config.choice_runtime import AppSettings
from tests.helpers import load_module


def _make_settings(**overrides) -> AppSettings:
    base = {
        "choice_emquant_parent": "/fake/em",
        "choice_start_options": "UserName=x,PassWord=y",
        "choice_request_options": "Ispandas=1,recvTimeout=30",
        "log_level": "INFO",
        "log_path": "",
    }
    base.update(overrides)
    return AppSettings(**base)


def test_choice_client_start_is_idempotent(monkeypatch):
    client_module = load_module(
        "backend.app.repositories.choice_client_contract",
        "backend/app/repositories/choice_client.py",
    )
    start_calls: list[str] = []

    class FakeC:
        def start(self, options: str):
            start_calls.append(options)
            return SimpleNamespace(ErrorCode=0)

    fake_c = FakeC()
    monkeypatch.setattr(client_module, "configure_emquant_parent", lambda _p: None)
    monkeypatch.setattr(client_module, "_get_em_c", lambda: fake_c)

    client = client_module.ChoiceClient(settings=_make_settings())
    r1 = client.start()
    r2 = client.start()

    assert r1.ErrorCode == 0
    assert r2 == 0
    assert start_calls == [client.settings.choice_start_options]


def test_choice_client_start_raises_import_error_when_em_c_unavailable(monkeypatch):
    client_module = load_module(
        "backend.app.repositories.choice_client_contract_b",
        "backend/app/repositories/choice_client.py",
    )
    monkeypatch.setattr(client_module, "configure_emquant_parent", lambda _p: None)
    monkeypatch.setattr(client_module, "_get_em_c", lambda: None)

    client = client_module.ChoiceClient(settings=_make_settings())
    with pytest.raises(ImportError, match="EmQuantAPI.c is unavailable"):
        client.start()


def test_choice_client_start_raises_runtime_error_prefers_errormsg(monkeypatch):
    client_module = load_module(
        "backend.app.repositories.choice_client_contract_c",
        "backend/app/repositories/choice_client.py",
    )

    class FakeC:
        def start(self, options: str):
            return SimpleNamespace(ErrorCode=7, ErrorMsg="login failed")

    monkeypatch.setattr(client_module, "configure_emquant_parent", lambda _p: None)
    monkeypatch.setattr(client_module, "_get_em_c", lambda: FakeC())

    client = client_module.ChoiceClient(settings=_make_settings())
    with pytest.raises(RuntimeError, match="login failed"):
        client.start()


def test_choice_client_start_raises_runtime_error_fallback_when_no_errormsg(monkeypatch):
    client_module = load_module(
        "backend.app.repositories.choice_client_contract_c2",
        "backend/app/repositories/choice_client.py",
    )

    class FakeC:
        def start(self, options: str):
            return SimpleNamespace(ErrorCode=42)

    monkeypatch.setattr(client_module, "configure_emquant_parent", lambda _p: None)
    monkeypatch.setattr(client_module, "_get_em_c", lambda: FakeC())

    client = client_module.ChoiceClient(settings=_make_settings())
    with pytest.raises(RuntimeError, match="Choice start failed: 42"):
        client.start()


def test_choice_client_constructor_uses_load_settings_when_omitted(monkeypatch):
    client_module = load_module(
        "backend.app.repositories.choice_client_contract_ctor",
        "backend/app/repositories/choice_client.py",
    )
    calls: list[object] = []

    def fake_load_settings():
        calls.append(True)
        return _make_settings()

    monkeypatch.setattr(client_module, "load_settings", fake_load_settings)
    client = client_module.ChoiceClient()
    assert calls == [True]
    assert client.settings.choice_start_options == "UserName=x,PassWord=y"


def test_merge_request_options_merges_strips_and_recvtimeout_flag():
    client_module = load_module(
        "backend.app.repositories.choice_client_contract_d",
        "backend/app/repositories/choice_client.py",
    )
    settings = _make_settings(
        choice_request_options="  base=1 ,  recvTimeout=99  ",
    )
    client = client_module.ChoiceClient(settings=settings)

    merged_keep = client._merge_request_options("  extra=2  , ", include_recv_timeout=True)
    assert merged_keep == "base=1 ,  recvTimeout=99,extra=2  ,"

    merged_drop = client._merge_request_options("extra=2", include_recv_timeout=False)
    assert merged_drop == "base=1 ,extra=2"

    only_timeout = client_module.ChoiceClient(
        settings=_make_settings(choice_request_options="recvTimeout=1", choice_start_options="")
    )
    assert only_timeout._merge_request_options("", include_recv_timeout=False) == ""

    empty_both = client_module.ChoiceClient(settings=_make_settings(choice_request_options="  "))
    assert empty_both._merge_request_options("   ", include_recv_timeout=True) == ""
    assert empty_both._merge_request_options("   ", include_recv_timeout=False) == ""


def test_edb_and_edbquery_call_start_and_merge_options(monkeypatch):
    client_module = load_module(
        "backend.app.repositories.choice_client_contract_e",
        "backend/app/repositories/choice_client.py",
    )
    started: list[bool] = []

    class FakeC:
        def start(self, options: str):
            return SimpleNamespace(ErrorCode=0)

        def edb(self, codes, merged: str):
            return ("edb", tuple(codes), merged)

        def edbquery(self, codes: str, merged: str):
            return ("edbquery", codes, merged)

    fake = FakeC()
    monkeypatch.setattr(client_module, "configure_emquant_parent", lambda _p: None)
    monkeypatch.setattr(client_module, "_get_em_c", lambda: fake)

    real_start = client_module.ChoiceClient.start

    def start_tracked(self):
        started.append(True)
        return real_start(self)

    monkeypatch.setattr(client_module.ChoiceClient, "start", start_tracked)

    client = client_module.ChoiceClient(settings=_make_settings(choice_request_options="recvTimeout=9"))
    assert client.edb(["a"], "x=1") == ("edb", ("a",), "recvTimeout=9,x=1")
    assert client.edbquery("codes", "x=1") == ("edbquery", "codes", "x=1")
    assert started == [True, True]


def test_cnq_and_cnqcancel_raise_on_nonzero_error_code(monkeypatch):
    client_module = load_module(
        "backend.app.repositories.choice_client_contract_f",
        "backend/app/repositories/choice_client.py",
    )

    class FakeC:
        def start(self, options: str):
            return SimpleNamespace(ErrorCode=0)

        def cnq(self, codes, content, merged, callback, userparams):
            return SimpleNamespace(ErrorCode=3, ErrorMsg="cnq bad")

        def cnqcancel(self, serial_id: int):
            return SimpleNamespace(ErrorCode=4, ErrorMsg="cancel bad")

    monkeypatch.setattr(client_module, "configure_emquant_parent", lambda _p: None)
    monkeypatch.setattr(client_module, "_get_em_c", lambda: FakeC())

    client = client_module.ChoiceClient(settings=_make_settings())
    with pytest.raises(RuntimeError, match="cnq bad"):
        client.cnq("c", "body", "opt=1")
    with pytest.raises(RuntimeError, match="cancel bad"):
        client.cnqcancel(99)


def test_cfn_cfnquery_pass_merged_options_without_recvtimeout(monkeypatch):
    client_module = load_module(
        "backend.app.repositories.choice_client_contract_g",
        "backend/app/repositories/choice_client.py",
    )
    calls: list[tuple[str, tuple, str]] = []

    class FakeC:
        def start(self, options: str):
            return SimpleNamespace(ErrorCode=0)

        def cfn(self, *args):
            *pos, merged = args
            calls.append(("cfn", tuple(pos), merged))
            return "cfn"

        def cfnquery(self, *args):
            *pos, merged = args
            calls.append(("cfnquery", tuple(pos), merged))
            return "cfnq"

    monkeypatch.setattr(client_module, "configure_emquant_parent", lambda _p: None)
    monkeypatch.setattr(client_module, "_get_em_c", lambda: FakeC())

    client = client_module.ChoiceClient(settings=_make_settings(choice_request_options="recvTimeout=5,a=1"))
    assert client.cfn("x", "y", options="b=2") == "cfn"
    assert client.cfnquery("p", options="b=2") == "cfnq"
    assert calls == [
        ("cfn", ("x", "y"), "a=1,b=2"),
        ("cfnquery", ("p",), "a=1,b=2"),
    ]


def test_tradedates_css_csd_pass_merged_options_with_recvtimeout(monkeypatch):
    client_module = load_module(
        "backend.app.repositories.choice_client_contract_h",
        "backend/app/repositories/choice_client.py",
    )
    calls: list[tuple[str, tuple, str]] = []

    class FakeC:
        def start(self, options: str):
            return SimpleNamespace(ErrorCode=0)

        def tradedates(self, *args):
            *pos, merged = args
            calls.append(("tradedates", tuple(pos), merged))

        def css(self, *args):
            *pos, merged = args
            calls.append(("css", tuple(pos), merged))

        def csd(self, *args):
            *pos, merged = args
            calls.append(("csd", tuple(pos), merged))

    monkeypatch.setattr(client_module, "configure_emquant_parent", lambda _p: None)
    monkeypatch.setattr(client_module, "_get_em_c", lambda: FakeC())

    client = client_module.ChoiceClient(settings=_make_settings(choice_request_options="recvTimeout=3"))
    client.tradedates("2020-01-01", "2020-01-02", options="fmt=1")
    client.css("a", "b", options="fmt=1")
    client.csd("c", "d", options="fmt=1")
    assert calls == [
        ("tradedates", ("2020-01-01", "2020-01-02"), "recvTimeout=3,fmt=1"),
        ("css", ("a", "b"), "recvTimeout=3,fmt=1"),
        ("csd", ("c", "d"), "recvTimeout=3,fmt=1"),
    ]


def test_cnq_passes_merged_options_with_recvtimeout(monkeypatch):
    client_module = load_module(
        "backend.app.repositories.choice_client_contract_i",
        "backend/app/repositories/choice_client.py",
    )
    captured: dict[str, str] = {}

    class FakeC:
        def start(self, options: str):
            return SimpleNamespace(ErrorCode=0)

        def cnq(self, codes, content, merged, callback, userparams):
            captured["merged"] = merged
            return SimpleNamespace(ErrorCode=0)

    monkeypatch.setattr(client_module, "configure_emquant_parent", lambda _p: None)
    monkeypatch.setattr(client_module, "_get_em_c", lambda: FakeC())

    client = client_module.ChoiceClient(settings=_make_settings(choice_request_options="recvTimeout=8"))
    client.cnq("C", "K", "z=1")
    assert captured["merged"] == "recvTimeout=8,z=1"
