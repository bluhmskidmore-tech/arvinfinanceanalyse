# GS-PORTFOLIO-HOME-A Assertions

This pack is a supporting-only governance sample for `PAGE-PORTFOLIO-HOME-001`.
It is not a capture-ready API sample and it is not business-owner approval.

Required assertions:

- `page_id == "PAGE-PORTFOLIO-HOME-001"`
- `frontend_route == "/portfolio"`
- `decision_anchor_date == "2026-05-31"`
- `governance_status.basis == "mixed_source_or_observational"`
- `formal_use_allowed=false`
- `governance_status.proves_page_execution == false`
- `governance_status.approves_metric_or_page == false`
- `frontend_gate_observation.core_render_ready == true`
- `frontend_gate_observation.decision_evidence_ready == true`
- `risk_evidence.risk_closure_ready == true`
- `risk_evidence.risk_report_date == "2026-05-31"`
- `risk_evidence.risk_result_meta_date == "2026-05-31"`
- `risk_evidence.decision_anchor_date == "2026-05-31"`

Boundary assertions:

- Real downstream values may render when their own result metadata is valid.
- The portfolio page must not claim page-level formal approval from this sample.
- Same-day risk date closure does not make this sample capture-ready and does not approve the page or any standalone `MTR-*`.
- The warning-quality risk tensor payload remains separate downstream evidence and must not be restated as `quality=ok` page-level decision evidence.
- The portfolio page must keep downstream truth ownership with balance, bond dashboard, positions, PnL attribution, and risk tensor pages.
