from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.app.repositories.governance_repo import GovernanceRepository

BALANCE_ANALYSIS_DECISION_STATUS_STREAM = "balance_analysis_decision_status"


@dataclass
class BalanceAnalysisDecisionRepository:
    governance_dir: Path | str

    def __post_init__(self) -> None:
        self.governance_dir = Path(self.governance_dir).resolve()

    def list_latest_statuses(
        self,
        *,
        report_date: str,
        position_scope: str,
        currency_basis: str,
    ) -> dict[str, dict[str, object]]:
        latest: dict[str, dict[str, object]] = {}
        for record in GovernanceRepository(base_dir=self.governance_dir).read_all(
            BALANCE_ANALYSIS_DECISION_STATUS_STREAM
        ):
            if str(record.get("report_date")) != report_date:
                continue
            if str(record.get("position_scope")) != position_scope:
                continue
            if str(record.get("currency_basis")) != currency_basis:
                continue
            decision_key = str(record.get("decision_key") or "").strip()
            if not decision_key:
                continue
            latest[decision_key] = {
                "decision_key": decision_key,
                "status": str(record.get("status") or "pending"),
                "updated_at": record.get("updated_at"),
                "updated_by": record.get("updated_by"),
                "comment": record.get("comment"),
            }
        return latest

    def append_status(self, payload: dict[str, object]) -> dict[str, object]:
        GovernanceRepository(base_dir=self.governance_dir).append(
            BALANCE_ANALYSIS_DECISION_STATUS_STREAM,
            payload,
        )
        return payload
