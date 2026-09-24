from __future__ import annotations

import os
import re

# Agent 子进程由用户提问驱动、且其工具集定义在本仓库之外（Hermes 自己的 MCP 配置），
# 因此必须假定子进程内容可被提示注入操控：任何进入其环境的凭据都等同于已泄漏。
_SECRET_NAME_MARKERS: tuple[str, ...] = (
    "PASSWORD",
    "PASSWD",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "APIKEY",
    "ACCESS_KEY",
    "ACCESSKEY",
    "CREDENTIAL",
    "PRIVATE_KEY",
    "CONNECTION_STRING",
    "DSN",
    "AUTH",
    "COOKIE",
    "SESSION",
    "PASSFILE",
)

# 个人访问令牌常见命名（GITHUB_PAT / GH_PAT）。用后缀而非子串匹配，
# 否则 "_PAT" 会连带剥离所有 "*_PATH" 系统变量。
_SECRET_NAME_SUFFIXES: tuple[str, ...] = ("_PAT",)

# MOSS 自身的配置命名空间整体不传递：子进程从不读取它，而它承载了数据源凭据。
_BLOCKED_NAME_PREFIXES: tuple[str, ...] = ("MOSS_",)

# 值形如 scheme://user:password@host 的内嵌凭据（DATABASE_URL、带认证的代理地址等）。
# 用户名允许为空（redis://:password@host）；不带密码段的普通 URL 不受影响。
# 密码段允许含 "/"（如 postgresql://user:pa/ss@host/db）；字符类排除 "@"，
# 不会吞掉 @ 后的主机段。与 scripts/hermes_bridge_server.py 同款保持同步。
_EMBEDDED_CREDENTIAL_VALUE_PATTERN = re.compile(r"://[^/\s@]*:[^\s@]+@")


def is_sensitive_env_name(name: str) -> bool:
    upper = str(name or "").upper()
    if upper.startswith(_BLOCKED_NAME_PREFIXES):
        return True
    if upper.endswith(_SECRET_NAME_SUFFIXES):
        return True
    return any(marker in upper for marker in _SECRET_NAME_MARKERS)


def is_sensitive_env_value(value: str) -> bool:
    return _EMBEDDED_CREDENTIAL_VALUE_PATTERN.search(str(value or "")) is not None


def build_agent_subprocess_env(**overrides: str) -> dict[str, str]:
    """构造 agent 子进程环境：保留操作系统变量，剥离凭据与 MOSS 配置命名空间。

    保留 OS 变量而非改用严格白名单，是因为 ``wsl.exe`` 与 Linux 侧 CLI 各自依赖
    一长串系统变量，白名单在两种宿主上都容易漏项。
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if not is_sensitive_env_name(key) and not is_sensitive_env_value(value)
    }
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("NO_COLOR", "1")
    for key, value in overrides.items():
        normalized = str(value or "").strip()
        if normalized:
            env[key] = normalized
    return env
