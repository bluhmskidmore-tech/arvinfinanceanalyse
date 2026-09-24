"""两份手工同步的 MCP server 配置的一致性守卫。

`.mcp.json`（顶层 ``mcpServers``，供 Cursor/Claude）与 `.codex/config.toml`
（``[mcp_servers.*]`` 表，供 Codex CLI）之间没有生成机制，只靠人工同步。
本测试断言两边 server 名称集合一致，且每个同名 server 的
command / args / cwd 完全一致；失败消息直接指出哪边缺了什么、哪个字段漂移。
`.codex/config.toml` 中 ``mcp_servers`` 以外的顶层键（如 ``model_verbosity``）忽略。

Verify: python -m pytest tests/test_mcp_config_consistency.py -q
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_JSON_PATH = REPO_ROOT / ".mcp.json"
CODEX_TOML_PATH = REPO_ROOT / ".codex" / "config.toml"

MCP_JSON_LABEL = ".mcp.json[mcpServers]"
CODEX_TOML_LABEL = ".codex/config.toml[mcp_servers]"

COMPARED_FIELDS = ("command", "args", "cwd")

_MISSING = object()


def _load_mcp_json_servers() -> dict[str, dict[str, Any]]:
    data = json.loads(MCP_JSON_PATH.read_text(encoding="utf-8"))
    servers = data.get("mcpServers")
    assert isinstance(servers, dict), f"{MCP_JSON_PATH} 缺少顶层 mcpServers 对象"
    return servers


def _load_codex_toml_servers() -> dict[str, dict[str, Any]]:
    with CODEX_TOML_PATH.open("rb") as file:
        data = tomllib.load(file)
    servers = data.get("mcp_servers")
    assert isinstance(servers, dict), f"{CODEX_TOML_PATH} 缺少 [mcp_servers.*] 表"
    return servers


def _render(value: Any) -> str:
    return "<缺失>" if value is _MISSING else repr(value)


def test_server_name_sets_match() -> None:
    json_names = set(_load_mcp_json_servers())
    toml_names = set(_load_codex_toml_servers())

    problems = []
    only_in_json = sorted(json_names - toml_names)
    only_in_toml = sorted(toml_names - json_names)
    if only_in_json:
        problems.append(
            f"{CODEX_TOML_LABEL} 缺少（仅 {MCP_JSON_LABEL} 定义）: {only_in_json}"
        )
    if only_in_toml:
        problems.append(
            f"{MCP_JSON_LABEL} 缺少（仅 {CODEX_TOML_LABEL} 定义）: {only_in_toml}"
        )
    assert not problems, "MCP server 名称集合漂移 -> " + "; ".join(problems)


def test_server_command_args_cwd_match() -> None:
    json_servers = _load_mcp_json_servers()
    toml_servers = _load_codex_toml_servers()

    drifts = []
    for name in sorted(set(json_servers) & set(toml_servers)):
        for field_name in COMPARED_FIELDS:
            json_value = json_servers[name].get(field_name, _MISSING)
            toml_value = toml_servers[name].get(field_name, _MISSING)
            if json_value != toml_value:
                drifts.append(
                    f"server '{name}' 的 {field_name} 漂移: "
                    f"{MCP_JSON_LABEL}={_render(json_value)} != "
                    f"{CODEX_TOML_LABEL}={_render(toml_value)}"
                )
    assert not drifts, "MCP server 定义漂移:\n  " + "\n  ".join(drifts)
