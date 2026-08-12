from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_CONTRACT_VERSION = "candidate-financial-indicator-period-comparison-v2"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_candidate_period_comparison_contract_version_is_aligned_across_layers() -> None:
    contract_sources = {
        "backend schema": "backend/app/schemas/candidate_financial_indicator_period_comparison.py",
        "backend service": "backend/app/services/candidate_financial_indicator_period_comparison_service.py",
        "frontend contract": "frontend/src/api/contracts/balanceLedger.ts",
        "frontend mock": "frontend/src/mocks/ledgerPnlMocks.ts",
        "frontend parser": "frontend/src/features/ledger-pnl/models/candidatePeriodComparisonModel.ts",
        "page contract": "docs/page_contracts.md",
    }

    for label, relative_path in contract_sources.items():
        source = _read(relative_path)
        assert ACTIVE_CONTRACT_VERSION in source, (
            f"{label} is not aligned with {ACTIVE_CONTRACT_VERSION}"
        )
