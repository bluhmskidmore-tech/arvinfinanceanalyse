from __future__ import annotations


def __getattr__(name: str):
    if name == "ToolRegistry":
        from backend.app.agent.runtime.tool_registry import ToolRegistry

        return ToolRegistry
    raise AttributeError(name)

__all__ = ["ToolRegistry"]
