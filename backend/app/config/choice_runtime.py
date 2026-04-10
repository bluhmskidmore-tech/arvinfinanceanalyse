from __future__ import annotations

import importlib
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_EM_C: Any | None = None


@dataclass
class AppSettings:
    choice_emquant_parent: str = ""
    choice_start_options: str = ""
    choice_request_options: str = ""
    log_level: str = "INFO"
    log_path: str = ""


def configure_emquant_parent(path: Path | str | None) -> None:
    selected = path or os.environ.get("CHOICE_EMQUANT_PARENT", "").strip()
    if not selected:
        return

    candidate = Path(selected).expanduser()
    if candidate.name == "EmQuantAPI":
        parent = candidate.parent
    elif (candidate / "EmQuantAPI").exists():
        parent = candidate
    else:
        parent = candidate

    resolved = str(parent)
    if resolved in sys.path:
        sys.path.remove(resolved)
    sys.path.insert(0, resolved)

    for module_name in list(sys.modules):
        if module_name == "EmQuantAPI" or module_name.startswith("EmQuantAPI."):
            sys.modules.pop(module_name, None)

    importlib.invalidate_caches()
    global _EM_C
    _EM_C = None


def _get_em_c() -> Any | None:
    global _EM_C
    if _EM_C is not None:
        return _EM_C

    configure_emquant_parent(None)
    try:
        from EmQuantAPI import c as cmod  # type: ignore
    except Exception:
        return None

    _EM_C = cmod
    return _EM_C


def load_settings(yaml_path: Path | None = None) -> AppSettings:
    path = yaml_path or (Path(__file__).resolve().parents[3] / "config" / "settings.yaml")
    data: dict[str, str] = {
        "choice_emquant_parent": "",
        "choice_start_options": "",
        "choice_request_options": "",
        "log_level": "INFO",
        "log_path": "",
    }
    if path.exists():
        data.update(_parse_simple_yaml(path))

    env_parent = os.environ.get("CHOICE_EMQUANT_PARENT", "").strip()
    if env_parent:
        data["choice_emquant_parent"] = env_parent

    env_so = os.environ.get("CHOICE_MACRO_CHOICE_START_OPTIONS", "").strip()
    if env_so:
        data["choice_start_options"] = env_so

    env_req = os.environ.get("CHOICE_MACRO_CHOICE_REQUEST_OPTIONS", "").strip()
    if env_req:
        data["choice_request_options"] = env_req

    return AppSettings(**data)


def setup_logging(level: str, log_path: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))


def _init_runtime(yaml_path: Path | None = None) -> AppSettings:
    settings = load_settings(yaml_path)
    configure_emquant_parent(settings.choice_emquant_parent)
    setup_logging(settings.log_level, settings.log_path)
    return settings


def _parse_simple_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    section = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1].strip()
            continue
        if not line.startswith(" "):
            section = ""
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if section == "choice":
            if key == "emquant_parent":
                data["choice_emquant_parent"] = value
            elif key == "start_options":
                data["choice_start_options"] = value
            elif key == "request_options":
                data["choice_request_options"] = value
        elif key == "log_level":
            data["log_level"] = value
        elif key == "log_path":
            data["log_path"] = value
    return data
