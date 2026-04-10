from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolRegistry:
    tools: dict[str, object] = field(default_factory=dict)

    def register(self, name: str, tool: object) -> None:
        self.tools[name] = tool

    def get(self, name: str) -> object:
        return self.tools[name]

