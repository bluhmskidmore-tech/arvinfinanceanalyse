from __future__ import annotations

READ_ONLY_AGENT_TOOLSETS: tuple[str, ...] = ("evidence", "query", "research")


def normalize_read_only_toolsets(toolsets: str) -> str:
    requested = [part.strip().lower() for part in str(toolsets or "").split(",") if part.strip()]
    allowed = set(READ_ONLY_AGENT_TOOLSETS)
    selected = [toolset for toolset in requested if toolset in allowed]
    if not selected:
        selected = list(READ_ONLY_AGENT_TOOLSETS)
    return ",".join(dict.fromkeys(selected))
