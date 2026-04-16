from __future__ import annotations

__all__ = ["AnalysisViewTool", "EvidenceTool"]


def __getattr__(name: str):
    if name == "AnalysisViewTool":
        from backend.app.agent.tools.analysis_view_tool import AnalysisViewTool

        return AnalysisViewTool
    if name == "EvidenceTool":
        from backend.app.agent.tools.evidence_tool import EvidenceTool

        return EvidenceTool
    raise AttributeError(name)

