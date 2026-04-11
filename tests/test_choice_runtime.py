from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace

import pytest

from tests.helpers import load_module


def test_governance_settings_env_files_resolve_under_repo():
    settings_module = load_module(
        "_test_governance_settings_path_check",
        "backend/app/governance/settings.py",
    )
    root = settings_module._REPO_ROOT
    assert (root / "backend" / "app" / "governance" / "settings.py").exists()
    assert settings_module._ENV_FILES == (root / "config" / ".env", root / ".env")


def test_configure_emquant_parent_inserts_parent_and_clears_import_cache(tmp_path, monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )

    em_parent = tmp_path / "EMQuantAPI_Python" / "python3"
    package_dir = em_parent / "EmQuantAPI"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "c.py").write_text("VALUE = 1\n", encoding="utf-8")

    monkeypatch.setenv("CHOICE_EMQUANT_PARENT", str(em_parent))
    sys.modules["EmQuantAPI"] = ModuleType("EmQuantAPI")
    sys.modules["EmQuantAPI.c"] = ModuleType("EmQuantAPI.c")

    runtime_module.configure_emquant_parent(None)

    assert sys.path[0] == str(em_parent)
    assert "EmQuantAPI" not in sys.modules
    assert "EmQuantAPI.c" not in sys.modules


def test_load_settings_reads_yaml_and_env_overrides(tmp_path, monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )

    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        "\n".join(
            [
                "choice:",
                "  emquant_parent: F:/EMQuantAPI_Python/python3",
                "  start_options: UserName=demo,PassWord=demo,ForceLogin=1",
                "  request_options: Ispandas=1,RECVtimeout=5",
                "log_level: INFO",
                "log_path: logs/choice.log",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CHOICE_MACRO_CHOICE_START_OPTIONS", "UserName=env,PassWord=env,ForceLogin=1")
    monkeypatch.setenv("CHOICE_EMQUANT_PARENT", "F:/Custom/EMQuantParent")

    settings = runtime_module.load_settings(settings_file)

    assert settings.choice_emquant_parent == "F:/Custom/EMQuantParent"
    assert settings.choice_start_options == "UserName=env,PassWord=env,ForceLogin=1"
    assert settings.choice_request_options == "Ispandas=1,RECVtimeout=5"
    assert settings.log_level == "INFO"
    assert settings.log_path == "logs/choice.log"


def test_load_settings_reads_choice_runtime_fields_from_governance_settings(monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )

    monkeypatch.delenv("CHOICE_EMQUANT_PARENT", raising=False)
    monkeypatch.delenv("CHOICE_MACRO_CHOICE_START_OPTIONS", raising=False)
    monkeypatch.delenv("CHOICE_MACRO_CHOICE_REQUEST_OPTIONS", raising=False)
    monkeypatch.setattr(
        runtime_module,
        "_load_governance_settings",
        lambda: SimpleNamespace(
            choice_emquant_parent="F:/EMQuantAPI_Python/python3",
            choice_start_options="UserName=governance,PassWord=governance,ForceLogin=1",
            choice_request_options="Ispandas=1,RECVtimeout=9",
            choice_username="",
            choice_password="",
        ),
    )

    settings = runtime_module.load_settings()

    assert settings.choice_emquant_parent == "F:/EMQuantAPI_Python/python3"
    assert settings.choice_start_options == "UserName=governance,PassWord=governance,ForceLogin=1"
    assert settings.choice_request_options == "Ispandas=1,RECVtimeout=9"


def test_load_settings_builds_choice_start_options_from_raw_choice_env(monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )

    monkeypatch.delenv("CHOICE_EMQUANT_PARENT", raising=False)
    monkeypatch.delenv("CHOICE_MACRO_CHOICE_START_OPTIONS", raising=False)
    monkeypatch.delenv("CHOICE_MACRO_CHOICE_REQUEST_OPTIONS", raising=False)
    monkeypatch.setenv("CHOICE_USERNAME", "raw-user")
    monkeypatch.setenv("CHOICE_PASSWORD", "raw-pass")
    monkeypatch.setattr(
        runtime_module,
        "_load_governance_settings",
        lambda: SimpleNamespace(
            choice_emquant_parent="F:/EMQuantAPI_Python/python3",
            choice_start_options="",
            choice_request_options="",
            choice_username="",
            choice_password="",
        ),
    )

    settings = runtime_module.load_settings()

    assert settings.choice_start_options == "UserName=raw-user,PassWord=raw-pass,ForceLogin=1"


def test_load_settings_builds_choice_start_options_from_governance_credentials(monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )

    monkeypatch.delenv("CHOICE_EMQUANT_PARENT", raising=False)
    monkeypatch.delenv("CHOICE_MACRO_CHOICE_START_OPTIONS", raising=False)
    monkeypatch.delenv("CHOICE_MACRO_CHOICE_REQUEST_OPTIONS", raising=False)
    monkeypatch.setattr(
        runtime_module,
        "_load_governance_settings",
        lambda: SimpleNamespace(
            choice_emquant_parent="F:/EMQuantAPI_Python/python3",
            choice_start_options="",
            choice_request_options="Ispandas=1,RECVtimeout=5",
            choice_username="demo-user",
            choice_password="demo-pass",
        ),
    )

    settings = runtime_module.load_settings()

    assert settings.choice_emquant_parent == "F:/EMQuantAPI_Python/python3"
    assert settings.choice_start_options == "UserName=demo-user,PassWord=demo-pass,ForceLogin=1"
    assert settings.choice_request_options == "Ispandas=1,RECVtimeout=5"


def test_load_settings_prefers_env_over_governance_settings(monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )

    monkeypatch.setenv("CHOICE_EMQUANT_PARENT", "F:/Env/EMQuantAPI_Python/python3")
    monkeypatch.setenv("CHOICE_MACRO_CHOICE_START_OPTIONS", "UserName=env,PassWord=env,ForceLogin=1")
    monkeypatch.setenv("CHOICE_MACRO_CHOICE_REQUEST_OPTIONS", "Ispandas=1,RECVtimeout=11")
    monkeypatch.setattr(
        runtime_module,
        "_load_governance_settings",
        lambda: SimpleNamespace(
            choice_emquant_parent="F:/Governance/EMQuantAPI_Python/python3",
            choice_start_options="UserName=governance,PassWord=governance,ForceLogin=1",
            choice_request_options="Ispandas=1,RECVtimeout=5",
            choice_username="governance-user",
            choice_password="governance-pass",
        ),
    )

    settings = runtime_module.load_settings()

    assert settings.choice_emquant_parent == "F:/Env/EMQuantAPI_Python/python3"
    assert settings.choice_start_options == "UserName=env,PassWord=env,ForceLogin=1"
    assert settings.choice_request_options == "Ispandas=1,RECVtimeout=11"


def test_load_settings_reads_real_governance_settings_from_moss_env(monkeypatch):
    governance_module = importlib.import_module("backend.app.governance.settings")
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )

    monkeypatch.delenv("CHOICE_EMQUANT_PARENT", raising=False)
    monkeypatch.delenv("CHOICE_MACRO_CHOICE_START_OPTIONS", raising=False)
    monkeypatch.delenv("CHOICE_MACRO_CHOICE_REQUEST_OPTIONS", raising=False)
    monkeypatch.setenv("MOSS_CHOICE_EMQUANT_PARENT", "F:/Moss/EMQuantAPI_Python/python3")
    monkeypatch.setenv("MOSS_CHOICE_REQUEST_OPTIONS", "Ispandas=1,RECVtimeout=7")
    monkeypatch.setenv("MOSS_CHOICE_USERNAME", "moss-user")
    monkeypatch.setenv("MOSS_CHOICE_PASSWORD", "moss-pass")
    governance_module.get_settings.cache_clear()

    settings = runtime_module.load_settings()

    assert settings.choice_emquant_parent == "F:/Moss/EMQuantAPI_Python/python3"
    assert settings.choice_start_options == "UserName=moss-user,PassWord=moss-pass,ForceLogin=1"
    assert settings.choice_request_options == "Ispandas=1,RECVtimeout=7"

    governance_module.get_settings.cache_clear()


def test_load_governance_settings_returns_none_when_governance_module_is_unavailable(monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "backend.app.governance.settings":
            raise ModuleNotFoundError(
                "No module named 'backend.app.governance.settings'",
                name="backend.app.governance.settings",
            )
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert runtime_module._load_governance_settings() is None


def test_load_governance_settings_propagates_get_settings_failures(monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "backend.app.governance.settings":
            return SimpleNamespace(
                get_settings=lambda: (_ for _ in ()).throw(RuntimeError("settings boom"))
            )
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="settings boom"):
        runtime_module._load_governance_settings()


def test_choice_client_lazy_imports_emquant_c_and_omits_recvtimeout_for_edbquery(tmp_path, monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )
    client_module = load_module(
        "backend.app.repositories.choice_client",
        "backend/app/repositories/choice_client.py",
    )

    em_parent = tmp_path / "EMQuantAPI_Python" / "python3"
    package_dir = em_parent / "EmQuantAPI"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "c.py").write_text(
        "\n".join(
            [
                "calls = []",
                "def start(options, *args, **kwargs):",
                "    calls.append(('start', options))",
                "    return 0",
                "def edbquery(codes, options=''):",
                "    calls.append(('edbquery', codes, options))",
                "    return {'codes': codes, 'options': options}",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CHOICE_EMQUANT_PARENT", str(em_parent))
    monkeypatch.setenv("CHOICE_MACRO_CHOICE_START_OPTIONS", "UserName=demo,PassWord=demo,ForceLogin=1")
    runtime_settings = runtime_module.AppSettings(
        choice_emquant_parent=str(em_parent),
        choice_start_options="UserName=demo,PassWord=demo,ForceLogin=1",
        choice_request_options="Ispandas=1,RECVtimeout=5",
        log_level="INFO",
        log_path="",
    )

    client = client_module.ChoiceClient(settings=runtime_settings)
    client.start()
    response = client.edbquery("EDB_CPI_YOY")
    cmod = runtime_module._get_em_c()

    assert response["codes"] == "EDB_CPI_YOY"
    assert cmod.calls[0] == ("start", "UserName=demo,PassWord=demo,ForceLogin=1")
    assert cmod.calls[1][0] == "edbquery"
    assert "RECVtimeout=" not in cmod.calls[1][2]


def test_choice_client_raises_runtime_error_on_nonzero_emquant_result(tmp_path, monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )
    client_module = load_module(
        "backend.app.repositories.choice_client",
        "backend/app/repositories/choice_client.py",
    )

    em_parent = tmp_path / "EMQuantAPI_Python" / "python3"
    package_dir = em_parent / "EmQuantAPI"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "c.py").write_text(
        "\n".join(
            [
                "class Result:",
                "    def __init__(self, code, msg):",
                "        self.ErrorCode = code",
                "        self.ErrorMsg = msg",
                "def start(options, *args, **kwargs):",
                "    return Result(1001, 'login failed')",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CHOICE_EMQUANT_PARENT", str(em_parent))
    settings = runtime_module.AppSettings(
        choice_emquant_parent=str(em_parent),
        choice_start_options="UserName=demo,PassWord=demo,ForceLogin=1",
        choice_request_options="",
        log_level="INFO",
        log_path="",
    )

    client = client_module.ChoiceClient(settings=settings)

    with pytest.raises(RuntimeError, match="login failed"):
        client.start()


def test_init_runtime_loads_settings_and_configures_emquant_parent(tmp_path, monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )
    monkeypatch.setattr(runtime_module, "_load_governance_settings", lambda: None)

    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        "\n".join(
            [
                "choice:",
                f"  emquant_parent: {tmp_path.as_posix()}",
                "  start_options: UserName=demo,PassWord=demo,ForceLogin=1",
                "log_level: DEBUG",
                "log_path: logs/runtime.log",
            ]
        ),
        encoding="utf-8",
    )

    called: dict[str, object] = {}

    monkeypatch.setattr(
        runtime_module,
        "configure_emquant_parent",
        lambda path: called.setdefault("emquant_parent", path),
    )
    monkeypatch.setattr(
        runtime_module,
        "setup_logging",
        lambda level, path: called.setdefault("logging", (level, path)),
    )

    settings = runtime_module._init_runtime(settings_file)

    assert settings.choice_start_options == "UserName=demo,PassWord=demo,ForceLogin=1"
    assert called["emquant_parent"] == settings.choice_emquant_parent
    assert called["logging"] == ("DEBUG", "logs/runtime.log")
