from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers import load_module


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
